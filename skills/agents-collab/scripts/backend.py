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

# A script invocation may be a read-only probe or renderer.
if __name__ == "__main__":
    sys.dont_write_bytecode = True

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


def project_component(value):
    if (len(value) > 40 or not all(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", part)
            for part in value.split("."))):
        raise ValueError("project names must be 1-40 characters: dot-separated segments starting with a letter or digit and containing letters, digits, '_' or '-'")
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


def require_outside_git(path):
    """Accept ordinary Git absence only, including for a prospective directory."""
    if os.environ.get("GIT_DIR") or os.environ.get("GIT_WORK_TREE"):
        raise ValueError("explicit GIT_DIR or GIT_WORK_TREE prevents private storage validation")
    ancestor = path
    while True:
        try:
            ancestor.stat()
        except FileNotFoundError:
            ancestor = ancestor.parent
        else:
            break
    for directory in (ancestor, *ancestor.parents):
        try:
            (directory / ".git").lstat()
        except FileNotFoundError:
            continue
        raise ValueError("private task storage must be outside every Git repository")

    # Probe the actual path with no inherited Git discovery ceiling. Git also
    # detects bare repositories.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(LC_ALL="C", GIT_OPTIONAL_LOCKS="0", GIT_DISCOVERY_ACROSS_FILESYSTEM="1")
    probe = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--git-dir"],
                           capture_output=True, env=env, timeout=10)
    if probe.returncode == 0:
        raise ValueError("private task storage must be outside every Git repository")
    if (probe.returncode != 128 or probe.stdout or probe.stderr.strip() !=
            b"fatal: not a git repository (or any of the parent directories): .git"):
        raise ValueError(f"could not establish private task storage is outside Git: {path}")


def storage_paths(profile, project, task, repo):
    # The configured root may intentionally be a symlink to an existing volume.
    # Resolve it once; every task/host child still rejects symlink ancestry.
    base = Path(profile["records_root"]).expanduser().resolve(strict=True)
    safe.safe_path(base)
    if not base.is_dir() or base == Path.home().resolve():
        raise ValueError("configured records root must already exist and be dedicated")
    task_root = safe.safe_path(base / project_component(project) / component(task))
    if overlap(task_root, repo):
        raise ValueError("private task storage overlaps the source repository")
    record = safe.safe_path(task_root / "collaboration")
    host = safe.safe_path(task_root / "host")
    require_outside_git(record)
    require_outside_git(host)
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
    try:
        data = safe.read_config(path)
    except ValueError:
        supplied = safe.strict_json(safe.read_regular(path, 16384))
        if isinstance(supplied, dict) and "agents" in supplied:
            raise ValueError(
                "collaboration profile supplied as --config; pass it with --profile FILE. "
                "--config selects only backend.json; omit --config to use the default "
                "backend selector. Nothing was selected or changed; no manual fallback"
            ) from None
        raise
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
                              "note": "A multi-operation helper is not atomic. Inspect show/check and the last committed step before continuing; never rerun the whole helper blindly."}
        self.save_workflow()

    def save_workflow(self):
        safe.atomic_write(self.workflow, encoded(self.workflow_data), replace=self.workflow.exists())

    def finish(self):
        self.workflow_data["status"] = "finished"
        self.save_workflow()

    def output_path(self, value, *, registered=False):
        path = safe.safe_path(value)
        if self.host not in path.parents:
            raise ValueError("output must be inside this task's private host directory")
        if any(part.casefold() == ".git" for part in path.relative_to(self.host).parts):
            raise ValueError("output path may not use a .git component")
        if registered and str(path) != value:
            raise ValueError("registered output destination must be a canonical absolute path")
        if path.exists():
            if registered:
                raise ValueError("registered output destination already exists; reconcile worker state before dispatch")
            raise ValueError("output already exists; choose a new private output path")
        require_outside_git(path.parent)
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
    profile = load_profile(args.profile)  # validate before writes
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
    spec = {"schema_version": 1, "project": project_component(args.project), "task": component(args.task),
            "repository": str(repo), "requirements": requirements,
            "authority_boundaries": [nonempty(x) for x in args.boundary], "writer": args.writer,
            "editable_scope": [relative(x) for x in args.scope], "reviewers": args.reviewer,
            "required_checks": args.check, "required_approvals": args.approval, "decision_authorities": [args.actor]}
    if args.command == "route":
        spec["review_required"] = True
    if not spec["authority_boundaries"] or not requirements:
        raise ValueError("at least one explicit boundary and requirement/criterion are required")
    backend.record, backend.host = storage_paths(profile, args.project, args.task, repo)
    if backend.record.exists():
        raise ValueError("task record already exists; inspect it rather than restarting")
    backend.begin("start")
    created = backend.mutation("task", "create", spec, create=True)
    activated = backend.mutation("task", "activate", {"reason": "Host explicitly started the bounded task"})
    return {"record": str(backend.record), "host": str(backend.host), "created": created, "activated": activated}


def storage(args):
    """Preview the same profile-derived layout as start, without creating it."""
    profile = load_profile(args.profile)
    repo = repository(args.repository)
    record, host = storage_paths(profile, args.project, args.task, repo)
    return {"mode": "cli", "config": str(safe.safe_path(args.config)),
            "profile": str(Path(args.profile).expanduser().resolve(strict=True)),
            "records_root": str(Path(profile["records_root"]).expanduser().resolve(strict=True)),
            "record": str(record), "host": str(host), "writes": False,
            "limits": "Path preview only: compare both paths with host-authorized writable roots. "
                      "This does not check write access, authorize writes, reserve a task or create state; start revalidates."}


def in_scope(scope, path):
    """Engine scope shape: an exact path, or a directory entry covering descendants."""
    return any(path == entry or path.startswith(entry + "/") for entry in scope)


def git_names(repo, *args):
    # -z output is unquoted; a non-UTF-8 name raises UnicodeError and fails closed.
    return {name for name in git(repo, *args).decode("utf-8").split("\0") if name}


DIFF_NAMES = ("--name-only", "--no-renames", "--no-ext-diff", "--ignore-submodules=none", "-z")


def review_coverage(repo, scope):
    """Task-scoped Git changes a review artifact must contain.

    Baseline: the HEAD commit, the same base the artifact freeze records. Changed
    paths are the union of unstaged and staged tracked differences from HEAD
    (deletions included, renames split into both paths) and untracked files not
    ignored by Git. Existing exact scope entries that Git ignores are required too,
    matching the engine's partial-work rule. Ignored descendants of directory
    scopes are reported, never discovered or attributed. A directory-shaped Git
    entry (trailing slash, such as an untracked nested repository) that contains a
    scope entry is required as well, so the explicit directory refusal applies and
    no unrelated declaration can cover scoped work beneath it. The entry keeps its
    exact Git spelling and is not traversed; ordinary ancestor names stay unscoped.
    Read-only.
    """
    head = git(repo, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    unstaged = git_names(repo, "diff", *DIFF_NAMES, head, "--")
    staged = git_names(repo, "diff", "--cached", *DIFF_NAMES, head, "--")
    untracked = git_names(repo, "ls-files", "--others", "--exclude-standard", "-z")
    known = (git_names(repo, "ls-files", "--cached", "-z") | untracked |
             git_names(repo, "ls-tree", "-r", "--name-only", "-z", head))
    ignored = {name.rstrip("/") for name in git_names(
        repo, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")}
    changed = unstaged | staged | untracked
    required = {path for path in changed if in_scope(scope, path)}
    # Only trailing-slash entries participate in this containment rule.
    required |= {path for path in changed
                 if path.endswith("/") and any(entry.startswith(path) for entry in scope)}
    for entry in scope:
        target = repo / entry
        if (entry not in known and os.path.lexists(target)
                and (os.path.islink(target) or not os.path.isdir(target))):
            required.add(entry)
    ignored_in_scope = {name for name in ignored
                        if in_scope(scope, name) or any(entry.startswith(name + "/") for entry in scope)}
    return {"head": head, "changed": changed, "required": required,
            "unscoped": changed - required, "ignored_in_scope": ignored_in_scope}


def listed(paths, limit=20):
    paths = sorted(paths)
    text = json.dumps(paths[:limit], ensure_ascii=False)
    return text + (f" (+{len(paths) - limit} more)" if len(paths) > limit else "")


def readable_sources(repo, paths):
    # Bounded wrapper support: no binary, symlink or deleted source presentation.
    for path in paths:
        raw = safe.read_regular(repo / path, MAX_INPUT)
        if b"\0" in raw:
            raise ValueError("binary selected source unsupported by readable context helper")
        raw.decode("utf-8")


def review_preflight(args, state):
    """Read-only review coverage guard, run before any workflow, record or output write.

    Writer context is deliberately unaffected. Every changed path inside the
    frozen editable scope must be selected; deletions and unsupported inputs fail;
    changed paths outside scope must be selected or explicitly declared unrelated
    (recorded per path in frozen omissions). No override admits a scoped omission.
    """
    if args.purpose != "review":
        if getattr(args, "unrelated_changes", None) is not None:
            raise ValueError("--unrelated-changes applies only to review context; writer context is unchanged")
        return None
    if state["spec"].get("review_required"):
        writers = [entry for entry in state["assignments"] if entry["spec"]["role"] == "writer"]
        if len(writers) != 1 or writers[0]["state"] != "completed":
            raise ValueError("opt-in review requires one completed writer before freezing review source")
        if args.round != 0 or any(packet["spec"]["purpose"] == "review" for packet in state["packets"]):
            raise ValueError("opt-in route permits one review round on one final artifact")
    paths = [relative(value) for value in args.paths]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate selected source path")
    repo = repository(state["spec"]["repository"])
    scope = list(state["spec"].get("editable_scope") or [])
    coverage = review_coverage(repo, scope)
    # Git can report an untracked nested repository as one trailing-slash name.
    # It is not a selectable regular file; do not traverse or normalize it away.
    directories = {path for path in coverage["required"] if path.endswith("/")}
    if directories:
        raise ValueError("review coverage guard refused before freeze: unsupported directory-shaped task change(s) " +
                         listed(directories) + "; Git may report an untracked nested repository this way. "
                         "The readable review helper cannot present these entries; use another authorized review path. "
                         "Nothing was frozen, sealed or written")
    selected = set(paths)
    problems = []
    absent = sorted(p for p in coverage["required"] | selected if not os.path.lexists(repo / p))
    if absent:
        problems.append("deleted or absent task/selected path(s) " + listed(absent) +
                        " cannot be presented by the readable review helper; use another authorized review path")
    missing = coverage["required"] - selected
    if missing:
        problems.append("review selection omits task-scoped change(s) since HEAD " + coverage["head"] + ": " +
                        listed(missing) + "; select every changed path inside the editable scope")
    unrelated = coverage["unscoped"] - selected
    declaration = getattr(args, "unrelated_changes", None)
    if unrelated and not (declaration and declaration.strip()):
        problems.append("changed path(s) outside the editable scope " + listed(unrelated) +
                        " are neither selected nor declared with --unrelated-changes REASON; a task change "
                        "outside scope is a scope violation to report, not something to declare unrelated")
    if problems:
        raise ValueError("review coverage guard refused before freeze: " + "; ".join(problems) +
                         ". Nothing was frozen, sealed or written")
    readable_sources(repo, paths)
    return {"repo": repo, "paths": paths, "scope": scope, "coverage": coverage, "unrelated": unrelated}


def verify_frozen_review(backend, plan, artifact):
    """After freeze and before seal: same Git state, and frozen bytes equal live selected bytes."""
    again = review_coverage(plan["repo"], plan["scope"])
    before = plan["coverage"]
    if any(again[key] != before[key] for key in ("head", "changed", "required")):
        raise ValueError("source changed during review freeze; artifact retained as evidence, no packet sealed. "
                         "Re-establish writer quiescence and inspect show before continuing")
    manifest = safe.strict_json(backend.frozen(artifact))
    entries = {}
    for entry in manifest["entries"]:
        if entry["path"] in entries:
            raise ValueError("duplicate frozen artifact entry; no packet sealed")
        entries[entry["path"]] = entry
    for path in plan["paths"]:
        entry = entries.get(path)
        if (entry is None or entry.get("kind") != "file" or
                entry.get("object") != safe.digest(safe.read_regular(plan["repo"] / path, MAX_INPUT))):
            raise ValueError("frozen artifact does not match selected live source " + json.dumps(path) +
                             "; artifact retained as evidence, no packet sealed")
    if not before["required"] <= set(entries):
        raise ValueError("frozen artifact omits task-scoped change; no packet sealed")


def context(backend, args, state, plan=None):
    if plan is None:
        plan = review_preflight(args, state)
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
    unrelated = (plan["unrelated"] & omitted) if plan else set()
    if omitted - unrelated and not args.omit_other_paths:
        raise ValueError("unselected inventory needs explicit --omit-other-paths REASON")
    readable_sources(repo, paths)
    omissions = {}
    for p in sorted(omitted):
        omissions[p] = ("Declared unrelated change outside editable scope: " + nonempty(args.unrelated_changes)
                        if p in unrelated else nonempty(args.omit_other_paths))
    selection = {"paths": paths, "omissions": omissions,
                 "acknowledged_sensitive": [], "quiescence": nonempty(args.quiescence),
                 "atomic_required": False, "base": "HEAD"}
    artifact = backend.mutation("artifact", "freeze", selection)["result"]["artifact"]
    if plan:
        verify_frozen_review(backend, plan, artifact)
    packet = {"purpose": args.purpose, "artifact": artifact, "round": args.round,
              "instructions": nonempty(instructions),
              "access_policy": "Host controls dispatch and tool restrictions; frozen source is supplied below; report actual limits",
              "coverage": {r["id"]: [artifact] for r in state["spec"]["requirements"]},
              "evidence": [{"category": "source_claim", "description": "Exact selected frozen source", "object": artifact}],
              "neutral_initial": args.purpose == "review"}
    packet_id = backend.mutation("packet", "seal", packet)["result"]["packet"]
    body = render_context(backend, packet_id, artifact)
    require_outside_git(output.parent)
    safe.atomic_write(output, body)
    value = {"artifact": artifact, "packet": packet_id, "output": str(output),
             "limits": "Exact frozen UTF-8 regular files; host must assess neutral instructions and actual isolation"}
    if plan:
        coverage = plan["coverage"]
        value["coverage"] = {
            "baseline": "HEAD " + coverage["head"],
            "editable_scope": plan["scope"],
            "task_changes_selected": sorted(coverage["required"]),
            "declared_unrelated_changes": sorted(plan["unrelated"]),
            "ignored_in_scope_not_inspected": sorted(coverage["ignored_in_scope"]),
            "limits": ("Staged, unstaged and untracked non-ignored changes from HEAD inside the frozen editable "
                       "scope are all selected. No changes means no task change set was found, not that review is "
                       "unnecessary. Ignored descendants and paths outside scope are not attributed to this task; "
                       "declared unrelated paths are the lead's explicit assertion, not proof. Only changes Git "
                       "reports are seen: assume-unchanged or skip-worktree index flags and Git-normalized "
                       "differences can hide tracked changes, and task work already committed before this "
                       "HEAD baseline is not discovered.")}
    return value


REVIEW_FIELDS = ("schema_version", "assignment", "artifact", "packet", "verdict", "verification", "limits",
                 "findings", "fresh_session", "automatic_context", "tool_boundary")


def review_output_template(assignment, packet, artifact):
    """Backend review schema with the exact registered identities filled in."""
    return {"schema_version": 1, "assignment": assignment, "artifact": artifact, "packet": packet,
            "verdict": "REPLACE: pass, changes_required or blocked",
            "verification": [{"category": "reviewer_opinion", "description": "REPLACE: what you inspected",
                              "object": artifact}],
            "limits": "REPLACE: summary, checks not run and limits of supplied evidence",
            "findings": [],
            "fresh_session": "REPLACE: observed session boundary or uncertainty",
            "automatic_context": "REPLACE: observed instructions, memory, hooks and plugins",
            "tool_boundary": "REPLACE: actual available tools and source-write restriction"}


REVIEWER_CONTRACT = "agents-collab-reviewer-final-json-v1"
WRITER_CONTRACT = "agents-collab-writer-report-v1"


def output_contract(role, assignment, packet, artifact):
    """Role-specific final-output instructions placed after the identity header."""
    if role == "writer":
        return WRITER_CONTRACT, None, (
            f"Final output contract {WRITER_CONTRACT} (writer).\n"
            "Use the frozen context below within the host's instructions and the assignment's editable scope. "
            "Do not return reviewer JSON. In your final message list every changed, new and deleted file, "
            "including docs and tests; checks run with results; and checks blocked or skipped with reasons. "
            "A blocked check is never reported as passing.")
    template = review_output_template(assignment, packet, artifact)
    return REVIEWER_CONTRACT, template, (
        f"Final output contract {REVIEWER_CONTRACT} (reviewer). This contract governs your final message and "
        "supersedes any conflicting output-format request in the frozen context below.\n"
        "Your final message must be exactly one JSON object with exactly these fields and nothing else: no "
        "prose, heading, Markdown fence or text before or after it. Keep schema_version, assignment, artifact "
        "and packet exactly as shown; replace every REPLACE value. Put any summary in limits, verification "
        "descriptions and findings. verdict is pass, changes_required or blocked. verification is a nonempty "
        "array of objects with exactly the string fields category, description and object; category is "
        "source_claim, verified_observation, interpretation, reviewer_opinion, unknown or unavailable; object "
        "is the artifact hash shown unless the host supplied another registered evidence hash. Each finding "
        "has nonempty string fields id, location, scenario, evidence, uncertainty and recommendation plus "
        "boolean material; a pass has no material findings. limits, fresh_session, automatic_context and "
        "tool_boundary are nonempty strings.\n"
        "The host retains your final message for the output destination. If you also write that file, it "
        "must contain this same JSON object; a written file, preview, progress note or wait summary never "
        "replaces the final message.\n"
        + json.dumps(template, ensure_ascii=False, indent=2))


def render_context(backend, packet_id, artifact):
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
    return body


def native_task_name(assignment, packet, artifact):
    """Observable identity carrier, not plaintext or dispatch authorization."""
    if (not isinstance(assignment, str) or not 0 < len(assignment) <= 512 or
            not all(isinstance(x, str) and len(x) == 64 and all(c in "0123456789abcdef" for c in x) for x in (packet, artifact))):
        raise ValueError("invalid native binding identity")
    raw = json.dumps(["agents-collab-native-task-v1", assignment, packet, artifact], ensure_ascii=True, separators=(",", ":")).encode()
    return safe.digest(raw)


def launching_assignment(state, assignment_id, label):
    if state["state"] != "active":
        raise ValueError(f"{label} requires an active task")
    matches = [a for a in state["assignments"] if a["spec"]["id"] == assignment_id]
    if len(matches) != 1:
        raise ValueError(f"{label} requires one registered assignment")
    assignment = matches[0]
    if assignment["state"] != "launching" or any(
            observation.get("receipt", {}).get("invocation") for observation in assignment.get("observations", [])):
        raise ValueError(f"{label} requires recorded launching intent without an invocation; inspect actual worker state, never redispatch blindly")
    return assignment


def dispatch_packet(state, assignment):
    packet_id = assignment["spec"]["packet"]
    packets = [p for p in state["packets"] if p["id"] == packet_id]
    if len(packets) != 1:
        raise ValueError("assignment packet is not uniquely registered")
    packet = packets[0]["spec"]
    artifact_id = packet["artifact"]
    if artifact_id != state["current_artifact"]:
        raise ValueError("assignment artifact is stale; inspect current task, do not launch")
    if packet["purpose"] != {"writer": "writer_context", "reviewer": "review"}.get(assignment["spec"]["role"]):
        raise ValueError("packet purpose disagrees with assignment role")
    return packet_id, packet


LEAD_EFFORT_POLICY = "lead-effort-v1"
LEAD_EFFORT_PREFIX = "Host supplied the lead's effort for this assignment: "


def resolve_assignment_effort(backend, state, requested, role, packet_id, *,
                              lead_effort=None, new_intent=False):
    delegates = requested.get("transport") in {"codex-native", "claude-cli"}
    if requested.get("reasoning") == validator.INHERIT and delegates:
        if lead_effort is None:
            if new_intent:
                raise ValueError("inherit requires the active lead's concrete effort in --lead-effort")
            # Existing launch intents may predate lead inheritance.
            return None
        if (not validator.LEVEL_RE.fullmatch(lead_effort) or
                lead_effort in {"auto", validator.INHERIT, validator.INTERFACE_DEFAULT,
                                *validator.AMBIGUOUS_LEVELS}):
            raise ValueError("--lead-effort must name the lead's concrete effort level")
        return {"requested": validator.INHERIT, "resolved": lead_effort,
                "policy": LEAD_EFFORT_POLICY, "basis": "lead effort supplied by the host at launch intent"}
    if lead_effort is not None:
        raise ValueError("--lead-effort applies only to delegates configured with inherit")
    if requested.get("reasoning") != "auto":
        return None
    if not delegates or role not in {"writer", "reviewer"}:
        raise ValueError("auto reasoning is only available for delegated writers and reviewers")
    purpose = "writer_context" if role == "writer" else "review"
    packets = [p["spec"] for p in state["packets"] if p["id"] == packet_id]
    if len(packets) != 1 or packets[0]["purpose"] != purpose:
        raise ValueError(f"auto reasoning for {role} requires a registered sealed {purpose} packet")
    entries = safe.strict_json(backend.frozen(packets[0]["artifact"]))["entries"]
    bounded = (len(entries) == 1 and entries[0]["kind"] == "file"
               and state["spec"]["editable_scope"] == [entries[0]["path"]])
    return {"requested": "auto", "resolved": "medium" if bounded else "high",
            "policy": "bounded-writer-v1" if role == "writer" else "bounded-review-v1",
            "basis": "one exact scoped file and one matching frozen file" if bounded
            else "scope or frozen source does not match one exact file"}


def assignment_effort(backend, state, assignment, *, lead_effort=None, new_intent=False):
    for observation in assignment["observations"]:
        launch = observation.get("receipt", {})
        reason = launch.get("reason") or ""
        if launch.get("state") == "launching" and reason.startswith(LEAD_EFFORT_PREFIX):
            saved = reason.removeprefix(LEAD_EFFORT_PREFIX).split("\n", 1)[0]
            if lead_effort is not None and lead_effort != saved:
                raise ValueError("--lead-effort must match the effort recorded for this assignment")
            lead_effort = saved
            break
    spec = assignment["spec"]
    return resolve_assignment_effort(backend, state, assignment.get("requested") or {},
                                     spec["role"], spec["packet"], lead_effort=lead_effort,
                                     new_intent=new_intent)


def check_replacement_output(backend, args, state):
    """Revalidate the immutable destination of a pending quota replacement."""
    assignment = launching_assignment(state, args.assignment, "replacement output check")
    if not assignment.get("continuation"):
        raise ValueError("replacement output check requires a recorded quota replacement")
    packet_id, packet = dispatch_packet(state, assignment)
    if backend.call("task", "check").get("integrity") != "verified":
        raise ValueError("record integrity is not verified")
    destination = backend.output_path(assignment["spec"]["output_destination"], registered=True)
    result = {"assignment": args.assignment, "packet": packet_id, "artifact": packet["artifact"],
            "output_destination": str(destination), "writes": False, "dispatch": "none",
            "limits": "Point-in-time storage check only. Host owns launch, worker reconciliation and receipt checks."}
    effort = assignment_effort(backend, state, assignment)
    if effort is not None:
        result["effort_resolution"] = effort
    return result


def render_dispatch(backend, args, state, transport):
    """Render an ordinary dispatch from registered immutable objects; never launch."""
    native = transport == "codex-native"
    label = "native dispatch" if native else "Claude CLI dispatch"
    assignment = launching_assignment(state, args.assignment, label)
    if assignment.get("continuation"):
        raise ValueError(f"{label} does not render quota continuations; use check-replacement-output and the documented handoff instructions")
    requested = assignment.get("requested") or {}
    if requested.get("transport") != transport:
        raise ValueError(f"{label} supports only a configured {transport} assignment")
    role = assignment["spec"]["role"]
    if not native and role != "reviewer":
        raise ValueError("Claude CLI dispatch renderer supports only reviewer assignments")
    packet_id, packet = dispatch_packet(state, assignment)
    artifact_id = packet["artifact"]
    if backend.call("task", "check").get("integrity") != "verified":
        raise ValueError("record integrity is not verified")
    sealed = safe.strict_json(backend.frozen(packet_id))
    if sealed["packet"] != packet:
        raise ValueError("registered packet differs from immutable packet object")
    body = render_context(backend, packet_id, artifact_id).decode("utf-8")
    contract, template, instructions = output_contract(role, args.assignment, packet_id, artifact_id)
    identity = f"Assignment: {args.assignment}\nPacket-SHA256: {packet_id}\nArtifact-SHA256: {artifact_id}\n"
    if native:
        task_name = native_task_name(args.assignment, packet_id, artifact_id)
        title = "Agents Collab native dispatch v1"
        transport_header = f"Native-Task-Name: {task_name}\n"
        transport_fields = {"task_name": task_name}
        launch = ("Pass task_name exactly as the native task_name and message verbatim to the native tool "
                  "with the requested controls. Transport may expose opaque text; never infer its plaintext.")
    else:
        title = "Agents Collab Claude CLI dispatch v1"
        transport_header = ""
        transport_fields = {}
        launch = ("Pass message verbatim as UTF-8 on standard input to a fresh Claude CLI process "
                  "with the requested controls. Retain the CLI-reported terminal message exactly.")
    destination = backend.output_path(assignment["spec"]["output_destination"], registered=True)
    effort = assignment_effort(backend, state, assignment)
    message = (f"{title}\n{identity}{transport_header}Role: {role}\n"
               f"Output destination: {destination}\n\n"
               + instructions + "\n\n" + body)
    return {"assignment": args.assignment, "packet": packet_id, "artifact": artifact_id, **transport_fields,
            "role": role, "final_output": {"contract": contract, "template": template},
            "requested": requested, **({"effort_resolution": effort} if effort is not None else {}),
            "message": message, "message_sha256": safe.digest(message.encode("utf-8")),
            "writes": False, "dispatch": "none",
            "limits": "Read-only message construction, not permission, a lease, delivery evidence or a worker-liveness check. "
                      "The host must verify authorized launch state. " + launch + " "
                      "Do not replace the message with a file path or retry an uncertain invocation. "
                      "A reviewer's terminal final message must itself be the complete review JSON; import that retained message, "
                      "and treat a result file, preview, wait summary or self-report as no terminal evidence."}


def native_dispatch(backend, args, state):
    return render_dispatch(backend, args, state, "codex-native")


LAUNCH_REASON = "Persist intent before authorized host dispatch"


def check_observation(args):
    """Reject contradictory observation flags before any record or trace is written."""
    reconciled = getattr(args, "reconciled", False)
    absent = getattr(args, "absence_established", False)
    if args.state == "launching":
        if args.invocation or reconciled or absent or args.exit_code is not None or getattr(args, "process_start", None):
            raise ValueError("launching records intent only: omit --invocation, --exit-code, --process-start, --reconciled and --absence-established")
        return
    if getattr(args, "lead_effort", None) is not None:
        raise ValueError("--lead-effort can be supplied only when recording launch intent")
    if absent and not reconciled:
        raise ValueError("--absence-established requires --reconciled")
    if (reconciled or absent) and not (args.reason and args.reason.strip()):
        raise ValueError("--reconciled/--absence-established require an explicit --reason stating the host evidence")


def receipt(args, state, launching=False, effort=None):
    """Build a host receipt. Flags are host assertions; nothing here proves them."""
    if launching or args.state == "launching":
        reason = LAUNCH_REASON if launching or not args.reason else nonempty(args.reason)
        if effort and effort["policy"] == LEAD_EFFORT_POLICY:
            reason = LEAD_EFFORT_PREFIX + effort["resolved"] + "\n" + reason
        return {"schema_version": 1, "assignment": args.id if launching else args.assignment,
                "state": "launching", "invocation": None, "process_start": None,
                "interface_model": None, "interface_effort": None,
                "observed_model": None, "observed_effort": None,
                "boundary_observations": "Host dispatch has not occurred; restrictions remain unobserved" if launching else nonempty(args.boundary_observations),
                "exit_code": None, "reason": reason,
                "reconciled": False, "absence_established": False}
    reconciled = bool(getattr(args, "reconciled", False))
    absent = bool(getattr(args, "absence_established", False))
    reason = args.reason if args.reason else f"Host reported {args.state} observation; not declared reconciled"
    return {"schema_version": 1, "assignment": args.assignment, "state": args.state,
            "invocation": args.invocation, "process_start": getattr(args, "process_start", None),
            "interface_model": args.interface_model, "interface_effort": args.interface_effort,
            "observed_model": None, "observed_effort": None,
            "boundary_observations": nonempty(args.boundary_observations),
            "exit_code": args.exit_code, "reason": nonempty(reason),
            "reconciled": reconciled, "absence_established": absent}


GENERIC_COMMANDS = {("finding", "resolve"), ("task", "block"), ("task", "activate"),
                    ("task", "cancel"), ("task", "reconcile"), ("task", "complete")}


def check_command(args):
    if (args.entity, args.action) not in GENERIC_COMMANDS:
        raise ValueError("generic mutation limited to finding resolve and task block/activate/cancel/reconcile/complete")


def run_bound(backend, args, state, plan=None):
    if args.command == "context":
        return context(backend, args, state, plan)
    if args.command == "assignment":
        requested = state["profile"]["agents"].get(args.agent, {})
        effort = resolve_assignment_effort(backend, state, requested, args.role, args.packet,
                                           lead_effort=args.lead_effort, new_intent=True)
        if effort is not None:
            backend.workflow_data["effort_resolution"] = effort
        value = {"id": args.id, "packet": args.packet, "agent": args.agent, "role": args.role,
                 "editable_scope": state["spec"]["editable_scope"] if args.role == "writer" else [],
                 "output_destination": str(backend.output_path(args.output_destination))}
        prepared = backend.mutation("assignment", "prepare", value)
        intent = backend.mutation("assignment", "observe", receipt(args, state, launching=True, effort=effort))
        result = {"prepared": prepared, "launch_intent": intent, "dispatch": "Host may now dispatch the authorized assignment"}
        if effort is not None:
            result["effort_resolution"] = effort
        return result
    if args.command == "extend-review":
        return backend.mutation("task", "extend-review", raw=safe.read_regular(args.input, MAX_INPUT))
    if args.command == "handoff":
        value = safe.strict_json(safe.read_regular(args.input, MAX_INPUT))
        value["output_destination"] = str(backend.output_path(value["output_destination"]))
        result = backend.mutation("assignment", "handoff", value)
        return {"result": result,
                "dispatch": "None. Inspect show and record observe launching. Run check-replacement-output "
                            "immediately before launch. Use a fresh execution identity and the retained instructions."}
    if args.command == "observe":
        check_observation(args)
        effort = None
        assignment = next((a for a in state["assignments"] if a["spec"]["id"] == args.assignment), None)
        if assignment is not None and args.state in {"launching", "running", "completed"}:
            effort = assignment_effort(backend, state, assignment, lead_effort=args.lead_effort,
                                       new_intent=args.state == "launching")
            if effort is not None:
                if args.state != "launching" and args.interface_effort != effort["resolved"]:
                    raise ValueError(f"{effort['requested']} reasoning resolved to {effort['resolved']}; record the accepted level with --interface-effort or reconcile the invocation")
                backend.workflow_data["effort_resolution"] = effort
        return backend.mutation("assignment", "observe", receipt(args, state, effort=effort))
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
        check_command(args)
        return backend.mutation(args.entity, args.action, raw=safe.read_regular(args.input, MAX_INPUT))
    raise ValueError("unknown helper command")


HELP = {
    "extend-review": "record an explicit task-only review ceiling amendment; never changes the profile or approves work",
    "context": ("freeze selected source and seal a writer_context or review packet; a review first requires every "
                "changed path in the editable scope since HEAD (staged, unstaged, untracked) to be selected"),
    "assignment": "prepare one writer/reviewer assignment and persist its launch intent",
    "handoff": "record an explicitly approved interrupted Claude-to-Codex continuation from a JSON file; never dispatches",
    "observe": "attach a host observation to an existing assignment (flags default false)",
    "import-review": "import a reviewer JSON result; exit 1 unless valid_structure_only",
    "evidence": ("retain a UTF-8 check/disposition text file and return its object hash; runs task reconcile, "
                 "which also quarantines incomplete staging files; refused while any launch intent is unattached"),
    "complete": ("complete the task with evidence covering every declared criterion/check; every required reviewer "
                 "must pass the current artifact, and no finding disposition overrides a changes_required verdict"),
    "show": "read the current record (revision, assignments, packets, blockers)",
    "check": "verify record integrity and list completion blockers",
    "packet": "print one registered sealed packet",
    "native-dispatch": "read-only identity-bound message for a launching codex-native assignment; does not dispatch",
    "claude-dispatch": "read-only identity-bound message for a launching claude-cli reviewer; does not dispatch",
    "check-replacement-output": "revalidate the saved output path for a launching quota replacement; read-only",
    "command": "send a JSON file to one supported low-level command: finding resolve or task block/activate/cancel/reconcile/complete",
}


class BackendArgumentParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        # Normalize only the three shared options. The ordinary parser still
        # validates command flags/values; no selector or profile is inferred.
        shared = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        for name in ("config", "profile", "actor"):
            shared.add_argument("--" + name, action="append")
        options, remaining = shared.parse_known_args(args)
        prefix = []
        for name in ("config", "profile", "actor"):
            values = getattr(options, name)
            if values:
                # Python 3.9 argparse represents an attached exact '--' value
                # as [] even for a scalar action. Reject it before hashing;
                # reject the literal string too for consistent newer runtimes.
                if any(not isinstance(value, str) or value == "--" for value in values):
                    self.error("--" + name + " requires text other than the exact '--' sentinel")
                if len(set(values)) != 1:
                    self.error("conflicting --" + name + " values; supply one explicit value")
                prefix.append("--" + name + "=" + values[0])
        return super().parse_args(prefix + remaining, namespace)


def parser():
    result = BackendArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument("--config", default=str(safe.DEFAULT_CONFIG), metavar="FILE", help="backend selector only; accepted before or after the command")
    result.add_argument("--profile", default=str(DEFAULT_PROFILE), metavar="FILE", help="collaboration profile, read by storage/start; never a backend selector")
    result.add_argument("--actor", default="lead", metavar="NAME",
                        help="attribution on each mutation, declared as decision authority at start; not authentication or human approval")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="manual when absent, otherwise probe configured CLI --version")
    storage_parser = commands.add_parser("storage", help="read-only profile-derived record/host path preview; no task creation or write-access claim")
    storage_parser.add_argument("--repository", required=True, metavar="DIR", help="canonical absolute Git root")
    storage_parser.add_argument("--project", required=True, metavar="ID")
    storage_parser.add_argument("--task", required=True, metavar="ID")
    start_parser = commands.add_parser("start", help="validate unchanged profile, create and activate bounded task")
    route_parser = commands.add_parser("route", allow_abbrev=False,
                                      help="select the routine solo route or explicitly require one independent review")
    route_parser.add_argument("--review-required", action="store_true",
                              help="create a task bound to one writer and one independent review")
    for task_parser in (start_parser, route_parser):
        required = task_parser is start_parser
        task_parser.add_argument("--repository", required=required, metavar="DIR", help="canonical absolute Git root")
        task_parser.add_argument("--project", required=required, metavar="ID")
        task_parser.add_argument("--task", required=required, metavar="ID", help="unique task ID; never reused to reset rounds")
        task_parser.add_argument("--writer", required=required, metavar="AGENT", help="profile agent or current-session")
        for flag, metavar, description in (
            ("reviewer", "AGENT", "fixed reviewer; opt-in route requires exactly one"),
            ("scope", "PATH", "exact editable relative path; repeat"),
            ("requirement", "ID=TEXT", "requirement, e.g. R1='Preserve API'; repeat"),
            ("criterion", "ID=TEXT", "acceptance criterion, e.g. C1='Tests pass'; repeat"),
            ("boundary", "TEXT", "authority boundary; at least one"),
            ("check", "NAME", "required check covered at completion; repeat"),
            ("approval", "NAME", "required real approval; helper cannot complete such tasks"),
        ):
            task_parser.add_argument("--" + flag, action="append", default=[], metavar=metavar, help=description)
    for name in ("context", "assignment", "native-dispatch", "claude-dispatch", "check-replacement-output",
                 "extend-review", "handoff", "observe", "import-review", "evidence", "complete",
                 "show", "check", "packet", "command"):
        p = commands.add_parser(name, help=HELP[name])
        p.add_argument("--record", required=True, metavar="DIR", help="collaboration record returned by start")
        if name == "context":
            p.add_argument("--purpose", choices=("writer_context", "review"), required=True)
            p.add_argument("--paths", action="append", required=True, metavar="PATH", help="one exact source path per flag")
            p.add_argument("--omit-other-paths", metavar="REASON", help="explicit reason applying to all unselected inventory")
            p.add_argument("--unrelated-changes", metavar="REASON",
                           help="review only: declare unselected changed paths outside the editable scope as unrelated "
                                "preexisting work (recorded per path); never use for task changes, never omits scoped changes")
            p.add_argument("--quiescence", required=True, metavar="TEXT", help="host declaration that writer has stopped")
            p.add_argument("--instructions", required=True, metavar="FILE", help="UTF-8 instruction file (a path, not inline text)")
            p.add_argument("--round", type=int, default=0, metavar="N",
                           help="0 for initial writing and initial review; N for repair writer_context and its follow-up review after round N-1 finished")
            p.add_argument("--output", required=True, metavar="FILE", help="new file inside task host/")
        elif name == "assignment":
            p.add_argument("--id", required=True, metavar="ID", help="new stable assignment ID; one per agent/packet")
            p.add_argument("--packet", required=True, metavar="HASH", help="packet hash returned by context")
            p.add_argument("--agent", required=True, metavar="AGENT")
            p.add_argument("--output-destination", required=True, metavar="FILE", help="new file inside task host/")
            p.add_argument("--role", choices=("writer", "reviewer"), required=True)
            p.add_argument("--lead-effort", metavar="LEVEL", help="active lead effort for a delegate using inherit")
        elif name in ("native-dispatch", "claude-dispatch", "check-replacement-output"):
            p.add_argument("--assignment", required=True, metavar="ID")
        elif name == "observe":
            p.add_argument("--assignment", required=True, metavar="ID")
            p.add_argument("--state", required=True, choices=("launching", "running", "completed", "interrupted", "blocked", "unknown"),
                           help="launching only re-records missing intent for a prepared assignment")
            p.add_argument("--invocation", metavar="ID", help="host session/invocation identity; required for running/completed")
            p.add_argument("--process-start", metavar="TEXT", help="optional supplementary process start evidence")
            p.add_argument("--interface-model", metavar="MODEL")
            p.add_argument("--interface-effort", metavar="LEVEL")
            p.add_argument("--lead-effort", metavar="LEVEL", help="active lead effort for inherited launch intent if not already recorded")
            p.add_argument("--exit-code", type=int, metavar="N", help="leave absent when native host does not expose it")
            p.add_argument("--boundary-observations", required=True, metavar="TEXT")
            p.add_argument("--reason", metavar="TEXT", help="required with --reconciled; state the host evidence")
            p.add_argument("--reconciled", action="store_true",
                           help="host asserts it checked this assignment's actual state (default false)")
            p.add_argument("--absence-established", action="store_true",
                           help="host asserts the previous invocation is actually absent; needs --reconciled and --reason; not proof (default false)")
        elif name in ("import-review", "evidence", "command", "handoff", "extend-review"):
            kind = {"extend-review": "explicit review allowance JSON contract (see backend reference)", "handoff": "explicit handoff JSON contract (see backend reference)", "import-review": "review result JSON file", "evidence": "UTF-8 text file with actual output",
                    "command": "low-level JSON input file"}[name]
            p.add_argument("--input", required=True, metavar="FILE", help=kind)
            if name == "evidence":
                p.epilog = ("The text is stored as the reason of a task reconcile mutation. Reconcile also moves "
                            "incomplete files from the record's staging/ to quarantine/ and would mark unattached "
                            "launch intents unknown, so attach every launched invocation with observe first. "
                            "Stored evidence is not proof that a check ran.")
            if name == "command":
                p.add_argument("--entity", choices=("task", "finding"), required=True)
                p.add_argument("--action", required=True, choices=("resolve", "block", "activate", "cancel", "reconcile", "complete"),
                               help="finding: resolve; task: block, activate, cancel, reconcile or complete")
        elif name == "complete":
            p.epilog = ("Rejected or deferred findings cannot complete a task while any current review is "
                        "changes_required. Only a changed artifact with a follow-up round in which every required "
                        "reviewer passes can; the same artifact cannot be re-reviewed or adjudicated.")
            p.add_argument("--evidence", action="append", required=True, metavar="HASH",
                           help="known object covering all declared criteria/checks; repeat")
            p.add_argument("--reason", required=True, metavar="TEXT")
        elif name == "packet":
            p.add_argument("--packet", required=True, metavar="HASH")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    backend = None
    try:
        if args.command == "route" and not args.review_required:
            value = {"route": "solo", "review_required": False, "record": None}
        elif args.command == "status":
            binary = selected_backend(args.config)
            if binary is None:
                value = {"mode": "manual", "config": str(safe.safe_path(args.config)),
                         "next_action": "Use the skill manual procedure; settings are absent at this selected path."}
            else:
                probe = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=15)
                if probe.returncode or not re.fullmatch(r"agents-collab [0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?\s*", probe.stdout):
                    raise ValueError("configured CLI version probe failed; no manual fallback")
                value = {"mode": "cli", "config": str(safe.safe_path(args.config)),
                         "binary": str(binary), "version": probe.stdout.strip(),
                         "next_action": "Read references/backend.md, then use start/context/assignment before dispatch; native transport does not select manual records."}
        else:
            # Invalid flag combinations fail before any record, trace or workflow write.
            if args.command == "route":
                if not all((args.repository, args.project, args.task, args.writer, args.scope)) or len(args.reviewer) != 1:
                    raise ValueError("--review-required needs --repository, --project, --task, --writer, --scope "
                                     "and exactly one --reviewer")
            elif args.command == "observe":
                check_observation(args)
            elif args.command == "command":
                check_command(args)
            backend = Backend(args)
            if args.command in ("start", "route"):
                value = start(backend, args)
                if args.command == "route":
                    value.update(route="review", review_required=True)
            elif args.command == "storage":
                value = storage(args)
            else:
                state = backend.bind(args.record)
                if args.command in {"show", "check"}:
                    value = backend.call("task", args.command)
                elif args.command == "packet":
                    value = safe.strict_json(backend.frozen(args.packet))
                    if args.packet not in {packet["id"] for packet in state["packets"]}:
                        raise ValueError("object is not a registered sealed packet")
                elif args.command == "native-dispatch":
                    value = native_dispatch(backend, args, state)
                elif args.command == "claude-dispatch":
                    value = render_dispatch(backend, args, state, "claude-cli")
                elif args.command == "check-replacement-output":
                    value = check_replacement_output(backend, args, state)
                else:
                    # Review coverage is checked read-only before any workflow trace or mutation.
                    plan = review_preflight(args, state) if args.command == "context" else None
                    backend.begin(args.command)
                    value = run_bound(backend, args, state, plan)
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
