#!/usr/bin/env python3
"""Optional local record backend; host retains all model dispatch and decisions.

Absent backend.json means manual mode. No automatic installation, dispatch,
retry or fallback. Outputs and operation traces stay in the task's private host/
folder alongside the CLI's collaboration/ record. Python 3.9+, standard library.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import install_backend as safe
import validate_profile as validator

DEFAULT_PROFILE = Path.home() / ".config/agents-collab/profile.json"
MAX_INPUT = 8 * 1024 * 1024


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def nonempty(value):
    if not value or not value.strip():
        raise ValueError("nonempty text is required")
    return value


def component(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}", value):
        raise ValueError("project/task/requirement names must use letters, digits, '_' or '-'")
    return value


def relative(value):
    if (not value or value.startswith("/") or "\\" in value
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or any(p in {"", ".", "..", ".git"} for p in value.split("/"))):
        raise ValueError("expected exact normalized relative source path")
    return value


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if result.returncode:
        raise ValueError("Git inspection failed")
    return result.stdout


def repository(path):
    if not Path(path).is_absolute():
        raise ValueError("repository must be canonical absolute Git root")
    path = safe.safe_path(path)
    if not path.is_dir() or path.resolve() != path:
        raise ValueError("repository must be canonical absolute Git root")
    if git(path, "rev-parse", "--show-toplevel").decode().strip() != str(path):
        raise ValueError("repository must be Git root")
    git(path, "rev-parse", "--verify", "HEAD")
    return path


def overlap(left, right):
    return left == right or left in right.parents or right in left.parents


def storage_paths(profile, project, task, repo):
    # The configured root may intentionally be a symlink to an existing volume.
    # Resolve it once; every task/host child still rejects symlink ancestry.
    base = Path(profile["records_root"]).expanduser().resolve(strict=True)
    safe.safe_path(base)
    if not base.is_dir() or base == Path.home().resolve():
        raise ValueError("configured records root must already exist and be dedicated")
    task_root = safe.safe_path(base / component(project) / component(task))
    if overlap(task_root, repo):
        raise ValueError("private task storage overlaps the source repository")
    ancestor = task_root
    while not ancestor.exists():
        ancestor = ancestor.parent
    probe = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
                           capture_output=True)
    if probe.returncode == 0:
        raise ValueError("private task storage must be outside every Git repository")
    record = safe.safe_path(task_root / "collaboration")
    host = safe.safe_path(task_root / "host")
    return record, host


def load_profile(path):
    text = validator.read_profile_text(str(path))
    issues = validator.check_text(text)
    if issues:
        raise ValueError("invalid saved profile: " + "; ".join(str(issue) for issue in issues))
    return validator.parse_text(text)


def selected_backend(config):
    path = safe.safe_path(config)
    if not path.exists():
        return None
    data = safe.read_config(path)
    binary = safe.safe_path(data["binary"])
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError("configured CLI binary is unavailable; no manual fallback")
    return binary


def decode_response(result):
    try:
        response = safe.strict_json(result.stdout)
    except (ValueError, UnicodeError):
        raise ValueError("CLI returned non-JSON output; inspect retained operation traces") from None
    if result.returncode != 0 or not response.get("ok"):
        message = response.get("error", {}).get("message", "CLI operation rejected")
        raise ValueError(message + "; no retry was attempted")
    return response["data"]


class Backend:
    def __init__(self, args):
        self.args = args
        self.binary = selected_backend(args.config)
        if self.binary is None:
            raise ValueError("manual mode: explicitly install/enable the optional CLI before backend commands")
        self.record = None
        self.host = None
        self.workflow = None
        self.steps = []

    def call(self, entity, action, record=None):
        target = record or self.record
        result = subprocess.run([str(self.binary), entity, action, "--record", str(target), "--json"],
                                capture_output=True)
        return decode_response(result)

    def bind(self, record):
        self.record = safe.safe_path(record)
        state = self.call("task", "show")["record"]
        spec = state["spec"]
        # Inspection may work without the live checkout; overlap uses original path.
        repo = safe.safe_path(spec["repository"])
        expected, self.host = storage_paths(state["profile"], spec["project"], spec["task"], repo)
        if self.record != expected:
            raise ValueError("record does not match saved profile task layout")
        return state

    def begin(self, command):
        safe.private_dir(self.host)
        self.workflow = self.host / ("workflow-" + uuid.uuid4().hex + ".json")
        self.workflow_data = {"command": command, "status": "incomplete", "steps": self.steps,
                              "note": "A multi-operation helper is not atomic. Inspect steps before continuing."}
        self.save_workflow()

    def save_workflow(self):
        safe.atomic_write(self.workflow, encoded(self.workflow_data), replace=self.workflow.exists())

    def finish(self):
        self.workflow_data["status"] = "finished"
        self.save_workflow()

    def output_path(self, value):
        path = safe.safe_path(value)
        if self.host not in path.parents:
            raise ValueError("output must be inside this task's private host directory")
        if path.exists():
            raise ValueError("output already exists; choose a new private output path")
        return path

    def mutation(self, entity, action, value=None, raw=None, create=False):
        if raw is None:
            raw = encoded(value)
        # Read revision immediately before each mutation; never retry a conflict.
        operation = uuid.uuid4().hex
        folder = safe.private_dir(self.host / ("operation-" + operation))
        input_path = folder / "input.json"
        safe.atomic_write(input_path, raw)
        revision = 0 if create else self.call("task", "show")["revision"]
        argv = [str(self.binary), entity, action, "--record", str(self.record),
                "--input", str(input_path), "--actor", self.args.actor, "--key", operation,
                "--expect", str(revision), "--json"]
        if create:
            argv += ["--profile", str(safe.safe_path(self.args.profile))]
        safe.atomic_write(folder / "request.json", encoded({"argv": argv, "input_sha256": safe.digest(raw)}))
        self.steps.append({"operation": operation, "command": f"{entity} {action}",
                           "trace": str(folder), "status": "incomplete"})
        self.save_workflow()
        # Store stdout/stderr even on a rejected operation or interrupted helper.
        out_fd = os.open(folder / "stdout", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        err_fd = os.open(folder / "stderr", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(out_fd, "wb") as out, os.fdopen(err_fd, "wb") as err:
            result = subprocess.run(argv, stdout=out, stderr=err)
        self.steps[-1]["exit_code"] = result.returncode
        self.save_workflow()
        stdout = safe.read_regular(folder / "stdout", 64 * 1024 * 1024)
        response = decode_response(subprocess.CompletedProcess(argv, result.returncode, stdout))
        self.steps[-1]["status"] = "committed"
        self.save_workflow()
        return response

    def frozen(self, object_id):
        if not re.fullmatch(r"[0-9a-f]{64}", object_id):
            raise ValueError("invalid immutable object identity")
        raw = safe.read_regular(self.record / "objects" / object_id, 64 * 1024 * 1024)
        if safe.digest(raw) != object_id:
            raise ValueError("immutable object hash mismatch")
        return raw


def start(backend, args):
    profile = load_profile(args.profile)  # unchanged validator, before writes
    repo = repository(args.repository)
    requirements = []
    for kind, values in (("requirement", args.requirement), ("criterion", args.criterion)):
        for value in values:
            name, sep, text = value.partition("=")
            if not sep:
                raise ValueError("requirement/criterion must be ID=TEXT")
            requirements.append({"id": component(name), "kind": kind, "text": nonempty(text),
                                 "source": "explicit host task input"})
    if len({r["id"] for r in requirements}) != len(requirements):
        raise ValueError("duplicate requirement/criterion ID")
    if args.writer != "current-session" and args.writer not in profile["agents"]:
        raise ValueError("writer must resolve from the saved profile or be current-session")
    if (len(set(args.reviewer)) != len(args.reviewer)
            or any(name not in profile["agents"] or name == args.writer
                   or profile["agents"][name]["transport"] == "host" for name in args.reviewer)):
        raise ValueError("reviewer must be a distinct saved non-host agent")
    if profile["review"]["on_consequential_work"] == "single" and not args.reviewer:
        raise ValueError("saved profile requires an independent reviewer")
    spec = {"schema_version": 1, "project": component(args.project), "task": component(args.task),
            "repository": str(repo), "requirements": requirements,
            "authority_boundaries": [nonempty(x) for x in args.boundary], "writer": args.writer,
            "editable_scope": [relative(x) for x in args.scope], "reviewers": args.reviewer,
            "required_checks": args.check, "required_approvals": args.approval, "decision_authorities": [args.actor]}
    if not spec["authority_boundaries"] or not requirements:
        raise ValueError("at least one explicit boundary and requirement/criterion are required")
    backend.record, backend.host = storage_paths(profile, args.project, args.task, repo)
    if backend.record.exists():
        raise ValueError("task record already exists; inspect it rather than restarting")
    backend.begin("start")
    created = backend.mutation("task", "create", spec, create=True)
    activated = backend.mutation("task", "activate", {"reason": "Host explicitly started the bounded task"})
    return {"record": str(backend.record), "host": str(backend.host), "created": created, "activated": activated}


def context(backend, args, state):
    output = backend.output_path(args.output)
    instructions = safe.read_regular(args.instructions, MAX_INPUT).decode("utf-8")
    paths = [relative(value) for value in args.paths]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate selected source path")
    repo = repository(state["spec"]["repository"])
    inventory = set(git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().rstrip("\0").split("\0"))
    inventory |= set(git(repo, "ls-tree", "-r", "--name-only", "-z", "HEAD").decode().rstrip("\0").split("\0"))
    inventory.discard("")
    omitted = inventory - set(paths)
    if omitted and not args.omit_other_paths:
        raise ValueError("unselected inventory needs explicit --omit-other-paths REASON")
    # Bounded wrapper support: no binary, symlink or deleted source presentation.
    for path in paths:
        raw = safe.read_regular(repo / path, MAX_INPUT)
        if b"\0" in raw:
            raise ValueError("binary selected source unsupported by readable context helper")
        raw.decode("utf-8")
    selection = {"paths": paths, "omissions": {p: nonempty(args.omit_other_paths) for p in sorted(omitted)},
                 "acknowledged_sensitive": [], "quiescence": nonempty(args.quiescence),
                 "atomic_required": False, "base": "HEAD"}
    artifact = backend.mutation("artifact", "freeze", selection)["result"]["artifact"]
    packet = {"purpose": args.purpose, "artifact": artifact, "round": args.round,
              "instructions": nonempty(instructions),
              "access_policy": "Host controls dispatch and tool restrictions; frozen source is supplied below; report actual limits",
              "coverage": {r["id"]: [artifact] for r in state["spec"]["requirements"]},
              "evidence": [{"category": "source_claim", "description": "Exact selected frozen source", "object": artifact}],
              "neutral_initial": args.purpose == "review"}
    packet_id = backend.mutation("packet", "seal", packet)["result"]["packet"]
    sealed = safe.strict_json(backend.frozen(packet_id))
    manifest = safe.strict_json(backend.frozen(artifact))
    body = b"# Frozen collaboration context\n\n" + encoded(sealed)
    for entry in manifest["entries"]:
        if entry["kind"] != "file" or not entry["object"]:
            raise ValueError("frozen nonregular/deleted source cannot be rendered; inspect retained artifact")
        raw = backend.frozen(entry["object"])
        if b"\0" in raw:
            raise ValueError("frozen binary source cannot be rendered; inspect retained artifact")
        raw.decode("utf-8")
        body += (f'\n--- Frozen source {json.dumps(entry["path"])}; SHA-256 {entry["object"]}; {len(raw)} bytes ---\n').encode() + raw + b"\n"
    safe.atomic_write(output, body)
    return {"artifact": artifact, "packet": packet_id, "output": str(output),
            "limits": "Exact frozen UTF-8 regular files; host must assess neutral instructions and actual isolation"}


def receipt(args, state, launching=False):
    return {"schema_version": 1, "assignment": args.id if launching else args.assignment,
            "state": "launching" if launching else args.state,
            "invocation": None if launching else args.invocation, "process_start": None,
            "interface_model": None if launching else args.interface_model,
            "interface_effort": None if launching else args.interface_effort,
            "observed_model": None, "observed_effort": None,
            "boundary_observations": "Host dispatch has not occurred; restrictions remain unobserved" if launching else nonempty(args.boundary_observations),
            "exit_code": None if launching else args.exit_code,
            "reason": "Persist intent before authorized host dispatch" if launching else nonempty(args.reason),
            "reconciled": False if launching else args.state != "launching",
            "absence_established": False}


def run_bound(backend, args, state):
    if args.command == "context":
        return context(backend, args, state)
    if args.command == "assignment":
        value = {"id": args.id, "packet": args.packet, "agent": args.agent, "role": args.role,
                 "editable_scope": state["spec"]["editable_scope"] if args.role == "writer" else [],
                 "output_destination": str(backend.output_path(args.output_destination))}
        prepared = backend.mutation("assignment", "prepare", value)
        intent = backend.mutation("assignment", "observe", receipt(args, state, launching=True))
        return {"prepared": prepared, "launch_intent": intent, "dispatch": "Host may now dispatch the authorized assignment"}
    if args.command == "observe":
        return backend.mutation("assignment", "observe", receipt(args, state))
    if args.command == "import-review":
        result = backend.mutation("review", "import", raw=safe.read_regular(args.input, MAX_INPUT))
        return {"result": result, "valid_review": result["result"].get("validation") == "valid_structure_only",
                "limits": "Command success alone is not a valid review or truth attestation"}
    if args.command == "evidence":
        if any(a["state"] == "launching" for a in state["assignments"]):
            raise ValueError("evidence reconciliation would mark unattached launches unknown; observe them first")
        raw = safe.read_regular(args.input, MAX_INPUT)
        text = raw.decode("utf-8")
        evidence = encoded({"reason": "Host supplied evidence; original UTF-8 bytes SHA-256 " + safe.digest(raw) + "\n" + text})
        result = backend.mutation("task", "reconcile", raw=evidence)
        return {"evidence": safe.digest(evidence), "input_sha256": safe.digest(raw), "result": result,
                "limits": "Evidence retained verbatim inside operation reason; truth and authorization are host responsibilities"}
    if args.command == "complete":
        if state["spec"]["required_approvals"]:
            raise ValueError("helper cannot supply actual approval evidence; use explicit CLI completion contract")
        value = {"artifact": state["current_artifact"],
                 "criteria": {r["id"]: args.evidence for r in state["spec"]["requirements"] if r["kind"] == "criterion"},
                 "checks": {name: args.evidence for name in state["spec"]["required_checks"]},
                 "approvals": {}, "reason": nonempty(args.reason)}
        return backend.mutation("task", "complete", value)
    if args.command == "command":
        command = (args.entity, args.action)
        allowed = {("finding", "resolve"), ("task", "block"), ("task", "activate"),
                   ("task", "cancel"), ("task", "reconcile"), ("task", "complete")}
        if command not in allowed:
            raise ValueError("generic mutation limited to finding resolve and task block/activate/cancel/reconcile/complete")
        return backend.mutation(*command, raw=safe.read_regular(args.input, MAX_INPUT))
    raise ValueError("unknown helper command")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", default=str(safe.DEFAULT_CONFIG), help="separate backend selector")
    result.add_argument("--profile", default=str(DEFAULT_PROFILE), help="saved profile, read only at start")
    result.add_argument("--actor", default="lead", help="actor and task decision authority; no authentication")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="manual when absent, otherwise probe configured CLI --version")
    start_parser = commands.add_parser("start", help="validate unchanged profile, create and activate bounded task")
    for flag in ("repository", "project", "task", "writer"):
        start_parser.add_argument("--" + flag, required=True)
    for flag in ("reviewer", "scope", "requirement", "criterion", "boundary", "check", "approval"):
        start_parser.add_argument("--" + flag, action="append", default=[])
    for name in ("context", "assignment", "observe", "import-review", "evidence", "complete", "show", "check", "packet", "command"):
        p = commands.add_parser(name)
        p.add_argument("--record", required=True)
        if name == "context":
            p.add_argument("--purpose", choices=("writer_context", "review"), required=True)
            p.add_argument("--paths", action="append", required=True, help="one exact source path per flag")
            p.add_argument("--omit-other-paths", help="explicit reason applying to all unselected inventory")
            p.add_argument("--quiescence", required=True, help="host declaration that writer has stopped")
            p.add_argument("--instructions", required=True)
            p.add_argument("--round", type=int, default=0)
            p.add_argument("--output", required=True, help="new file inside task host/")
        elif name == "assignment":
            for flag in ("id", "packet", "agent", "output-destination"):
                p.add_argument("--" + flag, required=True)
            p.add_argument("--role", choices=("writer", "reviewer"), required=True)
        elif name == "observe":
            p.add_argument("--assignment", required=True)
            p.add_argument("--state", required=True, choices=("launching", "running", "completed", "interrupted", "blocked", "unknown"))
            for flag in ("invocation", "interface-model", "interface-effort"):
                p.add_argument("--" + flag)
            p.add_argument("--exit-code", type=int, help="leave absent when native host does not expose it")
            p.add_argument("--boundary-observations", required=True)
            p.add_argument("--reason", default="Host reconciled the observed assignment state")
        elif name in ("import-review", "evidence", "command"):
            p.add_argument("--input", required=True)
            if name == "command":
                p.add_argument("--entity", choices=("task", "finding"), required=True)
                p.add_argument("--action", required=True)
        elif name == "complete":
            p.add_argument("--evidence", action="append", required=True, help="known object covering all declared criteria/checks")
            p.add_argument("--reason", required=True)
        elif name == "packet":
            p.add_argument("--packet", required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    backend = None
    try:
        if args.command == "status":
            binary = selected_backend(args.config)
            if binary is None:
                value = {"mode": "manual", "config": str(safe.safe_path(args.config))}
            else:
                probe = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=15)
                if probe.returncode or not re.fullmatch(r"agents-collab [0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?\s*", probe.stdout):
                    raise ValueError("configured CLI version probe failed; no manual fallback")
                value = {"mode": "cli", "binary": str(binary), "version": probe.stdout.strip()}
        else:
            backend = Backend(args)
            if args.command == "start":
                value = start(backend, args)
            else:
                state = backend.bind(args.record)
                if args.command in {"show", "check"}:
                    value = backend.call("task", args.command)
                elif args.command == "packet":
                    value = safe.strict_json(backend.frozen(args.packet))
                    if args.packet not in {packet["id"] for packet in state["packets"]}:
                        raise ValueError("object is not a registered sealed packet")
                else:
                    backend.begin(args.command)
                    value = run_bound(backend, args, state)
            if backend.workflow:
                backend.finish()
                value["workflow"] = str(backend.workflow)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        # Imported invalid originals are retained; expose non-success to hosts.
        return 1 if args.command == "import-review" and not value["valid_review"] else 0
    except (ValueError, OSError, KeyError, UnicodeError, subprocess.SubprocessError) as exc:
        error = {"error": str(exc), "fallback": "none"}
        if backend and backend.workflow:
            error["incomplete_workflow"] = str(backend.workflow)
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
