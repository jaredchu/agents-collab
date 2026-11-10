"""Optional backend invariants; real engine lifecycle is opt-in and offline."""
import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills/agents-collab/scripts"
sys.path.insert(0, str(SCRIPTS))
import backend
import install_backend as safe


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = self.root / "backend.json"

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = backend.main(["--config", str(self.config), *args])
        return code, out.getvalue(), err.getvalue()

    def test_absent_config_is_manual_without_writes(self):
        code, out, err = self.invoke("status")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["mode"], "manual")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_configured_missing_binary_fails_without_fallback(self):
        self.config.write_text(json.dumps({"version": 1, "mode": "cli", "binary": str(self.root / "missing")}))
        code, out, err = self.invoke("status")
        self.assertEqual(code, 1)
        self.assertIn("no manual fallback", err)
        self.assertEqual(out, "")

    def test_status_probes_only_explicit_configured_binary(self):
        binary = self.root / "agents-collab"
        binary.write_text("#!/bin/sh\nprintf 'agents-collab 0.1.0\\n'\n")
        binary.chmod(0o700)
        self.config.write_text(json.dumps({"version": 1, "mode": "cli", "binary": str(binary)}))
        code, out, err = self.invoke("status")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["version"], "agents-collab 0.1.0")
        binary.write_text("#!/bin/sh\nexit 2\n")
        code, out, err = self.invoke("status")
        self.assertEqual(code, 1)
        self.assertIn("no manual fallback", err)

    def test_scope_and_identity_traversal_rejected(self):
        for value in ("../file", "/absolute", ".git/config", "a//b", "a/./b", "a\\b"):
            with self.subTest(path=value), self.assertRaises(ValueError):
                backend.relative(value)
        for value in ("../task", "a/b", "", "a.b"):
            with self.subTest(task=value), self.assertRaises(ValueError):
                backend.component(value)

    def test_overlap_rejected_before_private_directories(self):
        repo = self.root / "repo"
        repo.mkdir()
        records = repo / "records"
        records.mkdir()
        with self.assertRaisesRegex(ValueError, "overlaps"):
            backend.storage_paths({"records_root": str(records)}, "project", "task", repo)
        self.assertEqual(list(records.iterdir()), [])

    def test_configured_symlink_root_resolves_but_task_symlink_is_rejected(self):
        actual = self.root / "records"
        actual.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(actual, target_is_directory=True)
        record, host = backend.storage_paths({"records_root": str(alias)}, "project", "task", self.root / "repo")
        self.assertEqual(record, actual / "project/task/collaboration")
        self.assertEqual(host, actual / "project/task/host")
        self.assertEqual(list(actual.iterdir()), [])
        (actual / "project").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            backend.storage_paths({"records_root": str(alias)}, "project", "task", self.root / "repo")

    def test_source_output_cannot_escape_private_host(self):
        instance = object.__new__(backend.Backend)
        instance.host = self.root / "records/project/task/host"
        with self.assertRaisesRegex(ValueError, "private host"):
            instance.output_path(self.root / "repo/context.txt")
        self.assertFalse(instance.host.exists())

    @staticmethod
    def observation(state, *flags):
        return backend.parser().parse_args(["observe", "--record", "/unused", "--assignment", "review-1",
                                            "--state", state, "--boundary-observations", "Fresh native session; no isolation",
                                            *flags])

    def test_native_observation_does_not_invent_attestation_exit_or_reconciliation(self):
        for state in ("completed", "unknown", "interrupted", "blocked"):
            with self.subTest(state=state):
                args = self.observation(state, "--invocation", "host-session-1")
                backend.check_observation(args)
                value = backend.receipt(args, {})
                self.assertIsNone(value["exit_code"])
                self.assertIsNone(value["process_start"])
                self.assertIsNone(value["observed_model"])
                self.assertIsNone(value["observed_effort"])
                self.assertFalse(value["reconciled"])
                self.assertFalse(value["absence_established"])
                self.assertNotIn("Host reconciled", value["reason"])

    def test_explicit_reconciliation_and_absence_are_recorded_as_host_assertions(self):
        args = self.observation("running", "--invocation", "host-session-2", "--process-start", "pid 42 at 10:12Z",
                                "--reconciled", "--absence-established",
                                "--reason", "Supervisor log shows host-session-1 exited; no matching process remains")
        backend.check_observation(args)
        value = backend.receipt(args, {})
        self.assertTrue(value["reconciled"])
        self.assertTrue(value["absence_established"])
        self.assertEqual(value["process_start"], "pid 42 at 10:12Z")
        self.assertIn("Supervisor log", value["reason"])

    def test_assignment_launch_intent_receipt_is_unchanged(self):
        args = argparse.Namespace(id="write-1")
        value = backend.receipt(args, {}, launching=True)
        self.assertEqual((value["assignment"], value["state"], value["invocation"]), ("write-1", "launching", None))
        self.assertFalse(value["reconciled"])
        self.assertFalse(value["absence_established"])

    def test_invalid_observation_and_command_flags_fail_before_any_cli_call(self):
        log = self.root / "calls.log"
        binary = self.root / "agents-collab"
        binary.write_text(f"#!/bin/sh\necho \"$@\" >> '{log}'\nexit 1\n")
        binary.chmod(0o700)
        self.config.write_text(json.dumps({"version": 1, "mode": "cli", "binary": str(binary)}))
        before = sorted(self.root.iterdir())
        base = ("observe", "--record", str(self.root / "record"), "--assignment", "write-1",
                "--boundary-observations", "Host observation")
        cases = {
            "absence without reconciliation": ("--state", "running", "--invocation", "b", "--absence-established",
                                               "--reason", "Host checked"),
            "reconciliation without reason": ("--state", "interrupted", "--invocation", "a", "--reconciled"),
            "absence without reason": ("--state", "running", "--invocation", "b", "--reconciled", "--absence-established"),
            "blank reason": ("--state", "running", "--invocation", "b", "--reconciled", "--reason", "  "),
            "launch with invocation": ("--state", "launching", "--invocation", "a"),
            "launch with reconciliation": ("--state", "launching", "--reconciled", "--reason", "Host checked"),
        }
        for label, flags in cases.items():
            with self.subTest(case=label):
                code, out, err = self.invoke(*base, *flags)
                self.assertEqual(code, 1)
                self.assertEqual(out, "")
                self.assertEqual(json.loads(err)["fallback"], "none")
        code, out, err = self.invoke("command", "--record", str(self.root / "record"), "--entity", "finding",
                                     "--action", "complete", "--input", str(self.config))
        self.assertEqual(code, 1)
        self.assertIn("generic mutation limited", err)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            backend.parser().parse_args(["command", "--record", "r", "--entity", "task", "--action", "create",
                                         "--input", "f"])
        self.assertFalse(log.exists())
        self.assertEqual(sorted(self.root.iterdir()), before)

    def test_shipped_retry_attempt_creation_is_exclusive_private_and_validated(self):
        text = (SCRIPTS.parent / "references/backend.md").read_text()
        intent = next(json.loads(b) for b in re.findall(r"```json\n(.*?)```", text, re.S)
                      if "agents-collab-retry-intent" in b)
        self.assertEqual((intent["state"], intent["new_invocation"]), ("launching", None))
        self.assertTrue(intent["attempt"].startswith(intent["assignment"] + ".attempt-"))
        for key in ("packet", "agent", "original_target", "previous_invocation", "previous_absence_evidence"):
            self.assertTrue(isinstance(intent[key], str) and intent[key].strip(), key)
        for key in ("original_deadline", "created_at"):
            self.assertIsInstance(intent[key], int, key)
        launched = json.loads(re.search(r'`(\{"attempt":[^`]*\})`', text).group(1))
        self.assertEqual((launched["attempt"], launched["state"]), (intent["attempt"], "running"))
        self.assertTrue(launched["new_invocation"])
        [create] = [b for b in re.findall(r"```sh\n(.*?)```", text, re.S) if "O_EXCL" in b]
        target = intent["attempt"] + ".json"
        self.assertIn(target, create)

        def run(host, draft, command=create):
            env = {**os.environ, "HOST": str(host), "DRAFT": str(draft)}
            return subprocess.run(["sh", "-c", command], env=env, capture_output=True, text=True).returncode

        host = self.root / "host"
        host.mkdir()
        draft = host / "draft.json"
        draft.write_text(json.dumps(intent))
        self.assertEqual(run(host, draft), 0)
        attempt = host / "retries" / target
        original = attempt.read_bytes()
        self.assertEqual(json.loads(original), intent)
        self.assertEqual(attempt.stat().st_mode & 0o777, 0o600)

        draft.write_text(json.dumps({**intent, "previous_invocation": "overwrite"}))
        self.assertNotEqual(run(host, draft), 0)
        self.assertEqual(attempt.read_bytes(), original)

        draft.write_text(json.dumps(launched))
        marker = host / "retries" / (intent["attempt"] + ".launched.json")
        self.assertEqual(run(host, draft, create.replace(target, marker.name)), 0)
        self.assertEqual(json.loads(marker.read_bytes()), launched)
        self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
        self.assertEqual(attempt.read_bytes(), original)

        fresh = self.root / "fresh-host"
        fresh.mkdir()
        malformed = fresh / "draft.json"
        malformed.write_text('{"kind": "agents-collab-retry-intent",')
        self.assertNotEqual(run(fresh, malformed), 0)
        self.assertEqual(list((fresh / "retries").iterdir()), [])


@unittest.skipUnless(os.environ.get("AGENTS_COLLAB_TEST_BINARY"), "set explicit real CLI path for offline macOS/APFS integration")
class RealBackendTests(unittest.TestCase):
    def setUp(self):
        BackendTests.setUp(self)
        self.binary = Path(os.environ["AGENTS_COLLAB_TEST_BINARY"]).resolve()
        self.config.write_text(json.dumps({"version": 1, "mode": "cli", "binary": str(self.binary)}))
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic@example.com")
        (self.repo / "source.txt").write_text("original frozen input\n")
        (self.repo / "other.txt").write_text("outside selected scope\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.records = self.root / "records"
        self.records.mkdir()
        profile = json.loads((SCRIPTS.parent / "examples/profile.example.json").read_text())
        alias = self.root / "records-alias"
        alias.symlink_to(self.records, target_is_directory=True)
        profile["records_root"] = str(alias)
        self.profile = self.root / "profile.json"
        self.profile.write_text(json.dumps(profile))
        self.original_profile = self.profile.read_bytes()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def invoke(self, *args):
        return BackendTests.invoke(self, "--profile", str(self.profile), *args)

    def begin_task(self, task="test", extra=()):
        code, out, err = self.invoke("start", "--repository", str(self.repo), "--project", "fixture", "--task", task,
                                     "--writer", "current-session", "--scope", "source.txt",
                                     "--requirement", "R1=Preserve exact frozen source", "--criterion", "C1=Task check passes",
                                     "--boundary", "No external actions", "--check", "offline", *extra)
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        return result["record"], Path(result["host"])

    def test_real_frozen_context_assignment_evidence_completion(self):
        record, host = self.begin_task()
        instructions = self.root / "instructions.txt"
        instructions.write_text("Inspect the complete requirements and frozen source.")
        code, out, err = self.invoke("context", "--record", record, "--purpose", "writer_context", "--paths", "source.txt",
                                     "--omit-other-paths", "Other file outside selected context", "--quiescence", "Writer stopped; host has turn",
                                     "--instructions", str(instructions), "--output", str(host / "writer-context.txt"))
        self.assertEqual(code, 0, err)
        frozen = json.loads(out)
        actual_output = (host / "writer-context.txt").read_text()
        self.assertIn("original frozen input", actual_output)
        self.assertIn("Preserve exact frozen source", actual_output)
        self.assertIn("No external actions", actual_output)
        self.assertNotIn("outside selected scope", actual_output)
        code, out, err = self.invoke("assignment", "--record", record, "--id", "write-1", "--packet", frozen["packet"],
                                     "--agent", "current-session", "--role", "writer", "--output-destination", str(host / "writer-output.txt"))
        self.assertEqual(code, 0, err)
        code, out, err = self.invoke("observe", "--record", record, "--assignment", "write-1", "--state", "completed",
                                     "--invocation", "synthetic-host-session-1", "--boundary-observations", "Host completed; no isolation claimed")
        self.assertEqual(code, 0, err)
        report = self.root / "evidence.txt"
        report.write_bytes(b"offline check: PASS\nall declared criteria covered\n")
        code, out, err = self.invoke("evidence", "--record", record, "--input", str(report))
        self.assertEqual(code, 0, err)
        evidence = json.loads(out)["evidence"]
        retained = json.loads((Path(record) / "objects" / evidence).read_text())
        self.assertTrue(retained["reason"].endswith(report.read_text()))
        code, out, err = self.invoke("complete", "--record", record, "--evidence", evidence, "--reason", "Fixture checks and criteria satisfied")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["result"]["state"], "completed")
        self.assertEqual(self.profile.read_bytes(), self.original_profile)
        code, out, err = self.invoke("check", "--record", record)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["integrity"], "verified")
        for path in host.rglob("*"):
            if path.is_file():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_context_refuses_unacknowledged_omission_and_keeps_incomplete_record(self):
        record, host = self.begin_task()
        instructions = self.root / "instructions.txt"
        instructions.write_text("Inspect frozen source")
        code, out, err = self.invoke("context", "--record", record, "--purpose", "review", "--paths", "source.txt",
                                     "--quiescence", "Writer stopped", "--instructions", str(instructions), "--output", str(host / "context.txt"))
        self.assertEqual(code, 1)
        self.assertIn("--omit-other-paths", err)
        workflow = Path(json.loads(err)["incomplete_workflow"])
        self.assertEqual(json.loads(workflow.read_text())["status"], "incomplete")
        self.assertFalse((host / "context.txt").exists())
        code, out, err = self.invoke("show", "--record", record)
        self.assertEqual(json.loads(out)["record"]["artifacts"], [])

    def test_declared_approval_is_preserved_and_helper_cannot_invent_it(self):
        record, host = self.begin_task(extra=("--approval", "owner"))
        code, out, err = self.invoke("show", "--record", record)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["record"]["spec"]["required_approvals"], ["owner"])
        code, out, err = self.invoke("complete", "--record", record, "--evidence", "0" * 64,
                                     "--reason", "Should not fabricate approval")
        self.assertEqual(code, 1)
        self.assertIn("actual approval evidence", err)

    def test_revision_conflict_is_retained_without_retry(self):
        record, host = self.begin_task()
        args = argparse.Namespace(config=str(self.config), profile=str(self.profile), actor="lead")
        instance = backend.Backend(args)
        instance.bind(record)
        instance.begin("conflict-test")
        with mock.patch.object(instance, "call", return_value={"revision": 0}) as read:
            with self.assertRaisesRegex(ValueError, "stale revision"):
                instance.mutation("task", "block", {"reason": "Synthetic stale operation"})
            read.assert_called_once_with("task", "show")
        workflow = json.loads(instance.workflow.read_text())
        self.assertEqual(workflow["status"], "incomplete")
        self.assertEqual(len(workflow["steps"]), 1)
        trace = Path(workflow["steps"][0]["trace"])
        self.assertIn("stale revision", (trace / "stdout").read_text())
        self.assertTrue((trace / "input.json").is_file())
        code, out, err = self.invoke("show", "--record", record)
        self.assertEqual(json.loads(out)["state"], "active")

    def use_profile(self, **changes):
        profile = json.loads(self.profile.read_text())
        for key, value in changes.items():
            profile[key] = value
        self.profile.write_text(json.dumps(profile))
        self.original_profile = self.profile.read_bytes()

    def show(self, record):
        code, out, err = self.invoke("show", "--record", record)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def context(self, record, host, purpose, round_number, name):
        instructions = self.root / (name + "-instructions.txt")
        instructions.write_text("Assess the complete requirements against the frozen source.")
        return self.invoke("context", "--record", record, "--purpose", purpose, "--round", str(round_number),
                           "--paths", "source.txt", "--omit-other-paths", "Unrelated fixture file",
                           "--quiescence", "Writer stopped; host has turn", "--instructions", str(instructions),
                           "--output", str(host / (name + ".txt")))

    def ok(self, result):
        code, out, err = result
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def shipped_example(self, key):
        """Return the first JSON example from the installed skill's backend reference containing key."""
        text = (SCRIPTS.parent / "references/backend.md").read_text()
        for block in re.findall(r"```json\n(.*?)```", text, re.S):
            value = json.loads(block)
            if key in value and (key != "decision" or "finding" in value):
                return value
        self.fail("shipped backend reference lacks a JSON example with " + key)

    def test_new_invocation_needs_declared_absence_and_keeps_original_timing(self):
        record, host = self.begin_task()
        packet = self.ok(self.context(record, host, "writer_context", 0, "writer"))["packet"]
        self.ok(self.invoke("assignment", "--record", record, "--id", "write-1", "--packet", packet, "--agent",
                            "current-session", "--role", "writer", "--output-destination", str(host / "w.txt")))
        original = self.show(record)["record"]["assignments"][0]
        self.assertIsNotNone(original["deadline"])
        boundary = ("--boundary-observations", "Host session; no isolation claimed")
        self.ok(self.invoke("observe", "--record", record, "--assignment", "write-1", "--state", "running",
                            "--invocation", "session-a", *boundary))
        self.ok(self.invoke("observe", "--record", record, "--assignment", "write-1", "--state", "interrupted",
                            "--invocation", "session-a", *boundary))
        latest = self.show(record)["record"]["assignments"][0]["observations"][-1]["receipt"]
        self.assertFalse(latest["reconciled"])
        self.assertFalse(latest["absence_established"])
        revision = self.show(record)["revision"]
        code, out, err = self.invoke("observe", "--record", record, "--assignment", "write-1", "--state", "running",
                                     "--invocation", "session-b", "--reconciled",
                                     "--reason", "Host checked session-a", *boundary)
        self.assertEqual(code, 1)
        self.assertIn("reconciled absence", err)
        self.assertEqual(self.show(record)["revision"], revision)
        self.ok(self.invoke("observe", "--record", record, "--assignment", "write-1", "--state", "running",
                            "--invocation", "session-b", "--reconciled", "--absence-established",
                            "--reason", "Host process table and session list show session-a exited before relaunch",
                            *boundary))
        self.ok(self.invoke("observe", "--record", record, "--assignment", "write-1", "--state", "completed",
                            "--invocation", "session-b", *boundary))
        state = self.show(record)["record"]
        self.assertEqual(len(state["assignments"]), 1)
        retried = state["assignments"][0]
        self.assertEqual((retried["spec"]["id"], retried["launch_at"], retried["deadline"]),
                         (original["spec"]["id"], original["launch_at"], original["deadline"]))
        self.assertEqual(retried["state"], "completed")

    def test_quota_writer_and_reviewer_continuations_use_explicit_local_selection(self):
        for role in ("writer", "reviewer"):
            with self.subTest(role=role):
                profile = json.loads(self.profile.read_text())
                self.use_profile(agents={**profile["agents"], "quota-worker": {
                    "model": "synthetic-claude", "transport": "claude-cli", "reasoning": "inherit"}})
                extra = ("--reviewer", "quota-worker") if role == "reviewer" else ()
                # Writer must be explicitly assigned at start; avoid altering saved defaults.
                start_args = ["start", "--repository", str(self.repo), "--project", "fixture", "--task", "quota-" + role,
                              "--writer", "quota-worker" if role == "writer" else "current-session", "--scope", "source.txt",
                              "--requirement", "R1=Preserve frozen contract", "--criterion", "C1=Offline checks pass",
                              "--boundary", "No provider calls", "--check", "offline", *extra]
                started = self.ok(self.invoke(*start_args))
                record, host = started["record"], Path(started["host"])
                initial = self.ok(self.context(record, host, "writer_context" if role == "writer" else "review", 0, role))
                self.ok(self.invoke("assignment", "--record", record, "--id", "old", "--packet", initial["packet"],
                                    "--agent", "quota-worker", "--role", role, "--output-destination", str(host / "old.json")))
                boundary = ("--boundary-observations", "Synthetic quota failure; no provider ran")
                self.ok(self.invoke("observe", "--record", record, "--assignment", "old", "--state", "unknown",
                                    "--invocation", "old-session", *boundary))
                evidence_file = host / "decision.txt"
                evidence_file.write_text("Synthetic explicit owner choice: Continue with configured available Codex model; amend frozen condition.\n")
                evidence = self.ok(self.invoke("evidence", "--record", record, "--input", str(evidence_file)))["evidence"]
                h = {"assignment": "old", "replacement": "replacement", "packet": initial["packet"], "agent": "task-codex",
                     "selection": {"model": "synthetic-codex", "transport": "codex-native", "reasoning": "inherit"},
                     "output_destination": str(host / "replacement.json"), "decision": "continue_with_codex", "authority": "lead",
                     "decision_evidence": [evidence], "reason": "Owner chose continuation after synthetic quota receipt",
                     "previous_invocation": "old-session", "timing": "preserve_deadline",
                     "instructions": "Continue current partial source; reviewer uses neutral frozen packet only in fresh session", "partial_work": None}
                handoff_file = host / "handoff.json"
                def handoff(value):
                    handoff_file.write_text(json.dumps(value))
                    return self.invoke("handoff", "--record", record, "--input", str(handoff_file))
                code, out, err = handoff(h)
                self.assertEqual(code, 1)
                self.assertIn("only an interrupted", err)
                self.ok(self.invoke("observe", "--record", record, "--assignment", "old", "--state", "interrupted",
                                    "--invocation", "old-session", "--reconciled", "--reason", "Host checked quota failure", *boundary))
                code, out, err = handoff(h)
                self.assertEqual(code, 1)
                self.assertIn("absence", err)
                self.ok(self.invoke("observe", "--record", record, "--assignment", "old", "--state", "interrupted",
                                    "--invocation", "old-session", "--reconciled", "--absence-established",
                                    "--reason", "Synthetic supervisor confirms original worker exited and no worker remains", *boundary))
                original = self.show(record)["record"]
                self.assertIn("assignment old blocked", " ".join(self.show(record)["blockers"]))
                code, out, err = handoff({**h, "decision_evidence": []})
                self.assertEqual(code, 1)
                self.assertIn("evidence references required", err)
                if role == "writer":
                    (self.repo / "source.txt").write_text("retained unfinished source\n")
                    h["partial_work"] = {"paths": ["source.txt"], "omissions": {"other.txt": "outside writer scope"},
                                         "acknowledged_sensitive": [], "quiescence": "Original invocation absent", "atomic_required": False, "base": "HEAD"}
                result = self.ok(handoff(h))
                self.assertEqual(result["result"]["result"]["logical_slot"], "quota-worker")
                changed = self.show(record)["record"]
                self.assertEqual(changed["schema_version"], 2)
                self.assertEqual(changed["profile"], original["profile"])
                self.assertEqual(changed["assignments"][0]["observations"], original["assignments"][0]["observations"])
                self.assertEqual(changed["assignments"][0]["state"], "superseded")
                self.assertEqual(changed["assignments"][1]["deadline"], original["assignments"][0]["deadline"])
                self.assertEqual(self.profile.read_bytes(), self.original_profile)
                code, out, err = handoff(h)
                self.assertEqual(code, 1)
                self.assertIn("replacement identity already used", err)
                self.ok(self.invoke("observe", "--record", record, "--assignment", "replacement", "--state", "launching", *boundary))
                self.ok(self.invoke("observe", "--record", record, "--assignment", "replacement", "--state", "completed",
                                    "--invocation", "replacement-session-" + role, *boundary))
                code, out, err = self.invoke("observe", "--record", record, "--assignment", "old", "--state", "running",
                                             "--invocation", "old-session", "--reconciled", "--reason", "Cannot resume old worker", *boundary)
                self.assertEqual(code, 1)
                self.assertIn("superseded", err)
                if role == "reviewer":
                    review = self.shipped_example("verdict")
                    review.update(assignment="replacement", artifact=initial["artifact"], packet=initial["packet"],
                                  fresh_session="replacement-session-reviewer")
                    review["verification"][0]["object"] = initial["artifact"]
                    (host / "replacement.json").write_text(json.dumps(review))
                    self.assertTrue(self.ok(self.invoke("import-review", "--record", record, "--input", str(host / "replacement.json")))["valid_review"])
                    self.ok(self.invoke("complete", "--record", record, "--evidence", evidence, "--reason", "Same packet slot completed"))
                else:
                    self.assertEqual((self.repo / "source.txt").read_text(), "retained unfinished source\n")
                    self.assertIsNotNone(changed["assignments"][1]["continuation"]["preserved_work"])
                    # Restore the fixture source for the next independent role scenario.
                    (self.repo / "source.txt").write_text("original frozen input\n")

    def test_required_timing_refuses_launch_intent_without_fallback(self):
        profile = json.loads(self.profile.read_text())
        self.use_profile(bounds={**profile["bounds"], "enforcement": "required"})
        record, host = self.begin_task()
        packet = self.ok(self.context(record, host, "writer_context", 0, "writer"))["packet"]
        code, out, err = self.invoke("assignment", "--record", record, "--id", "write-1", "--packet", packet,
                                     "--agent", "current-session", "--role", "writer",
                                     "--output-destination", str(host / "w.txt"))
        self.assertEqual(code, 1)
        self.assertIn("required timing", err)
        workflow = json.loads(Path(json.loads(err)["incomplete_workflow"]).read_text())
        self.assertEqual([s["status"] for s in workflow["steps"]], ["committed", "incomplete"])
        assignment = self.show(record)["record"]["assignments"][0]
        self.assertEqual((assignment["state"], assignment["launch_at"]), ("prepared", None))

    def test_followup_round_one_and_shipped_disposition_complete_task(self):
        profile = json.loads(self.profile.read_text())
        agents = {**profile["agents"], "reviewer": {"model": "synthetic-reviewer-1", "transport": "claude-cli",
                                                    "reasoning": "inherit"}}
        self.use_profile(agents=agents, review={**profile["review"], "on_consequential_work": "single",
                                                "candidates": ["reviewer"], "max_followup_rounds": 1})
        record, host = self.begin_task(extra=("--reviewer", "reviewer"))
        boundary = ("--boundary-observations", "Fresh synthetic session; tool-less; no isolation claimed")

        initial = self.ok(self.context(record, host, "review", 0, "review-0"))
        self.ok(self.invoke("assignment", "--record", record, "--id", "review-1", "--packet", initial["packet"],
                            "--agent", "reviewer", "--role", "reviewer", "--output-destination", str(host / "r1.json")))
        self.ok(self.invoke("observe", "--record", record, "--assignment", "review-1", "--state", "completed",
                            "--invocation", "review-session-1", "--exit-code", "0", *boundary))
        review = self.shipped_example("verdict")
        review.update(assignment="review-1", artifact=initial["artifact"], packet=initial["packet"],
                      verdict="changes_required")
        review["verification"][0]["object"] = initial["artifact"]
        review["findings"] = [{"id": "F1", "location": "source.txt", "scenario": "Stale wording",
                               "evidence": "Frozen line reads original", "uncertainty": "Low",
                               "recommendation": "Update the line", "material": True}]
        (host / "r1.json").write_text(json.dumps(review))
        result = self.ok(self.invoke("import-review", "--record", record, "--input", str(host / "r1.json")))
        self.assertTrue(result["valid_review"])

        # Round 0 writer context is refused after review; freeze committed first (non-atomic helper).
        code, out, err = self.context(record, host, "writer_context", 0, "fix-wrong-round")
        self.assertEqual(code, 1)
        steps = json.loads(Path(json.loads(err)["incomplete_workflow"]).read_text())["steps"]
        self.assertEqual([(s["command"], s["status"]) for s in steps],
                         [("artifact freeze", "committed"), ("packet seal", "incomplete")])
        fix = self.ok(self.context(record, host, "writer_context", 1, "fix-context"))
        self.ok(self.invoke("assignment", "--record", record, "--id", "fix-1", "--packet", fix["packet"],
                            "--agent", "current-session", "--role", "writer", "--output-destination", str(host / "fix.txt")))
        (self.repo / "source.txt").write_text("repaired frozen input\n")
        self.ok(self.invoke("observe", "--record", record, "--assignment", "fix-1", "--state", "completed",
                            "--invocation", "lead-fix-session", *boundary))

        followup = self.ok(self.context(record, host, "review", 1, "review-1"))
        self.assertNotEqual(followup["artifact"], initial["artifact"])
        self.ok(self.invoke("assignment", "--record", record, "--id", "review-2", "--packet", followup["packet"],
                            "--agent", "reviewer", "--role", "reviewer", "--output-destination", str(host / "r2.json")))
        self.ok(self.invoke("observe", "--record", record, "--assignment", "review-2", "--state", "completed",
                            "--invocation", "review-session-2", *boundary))
        review = self.shipped_example("verdict")
        review.update(assignment="review-2", artifact=followup["artifact"], packet=followup["packet"])
        review["verification"][0]["object"] = followup["artifact"]
        (host / "r2.json").write_text(json.dumps(review))
        self.assertTrue(self.ok(self.invoke("import-review", "--record", record, "--input", str(host / "r2.json")))["valid_review"])

        report = self.root / "check.txt"
        report.write_text("offline check: PASS\nF1 addressed in follow-up artifact\n")
        evidence = self.ok(self.invoke("evidence", "--record", record, "--input", str(report)))["evidence"]
        disposition = self.shipped_example("decision")
        disposition.update(finding="F1", evidence=[evidence])
        (host / "disposition.json").write_text(json.dumps(disposition))
        self.ok(self.invoke("command", "--record", record, "--entity", "finding", "--action", "resolve",
                            "--input", str(host / "disposition.json")))
        done = self.ok(self.invoke("complete", "--record", record, "--evidence", evidence,
                                   "--reason", "Follow-up passed and criteria covered"))
        self.assertEqual(done["result"]["state"], "completed")
        self.assertEqual(self.profile.read_bytes(), self.original_profile)

    def test_evidence_is_a_reconcile_that_quarantines_staging_and_refuses_unattached_launch(self):
        record, host = self.begin_task()
        packet = self.ok(self.context(record, host, "writer_context", 0, "writer"))["packet"]
        self.ok(self.invoke("assignment", "--record", record, "--id", "write-1", "--packet", packet, "--agent",
                            "current-session", "--role", "writer", "--output-destination", str(host / "w.txt")))
        report = self.root / "check.txt"
        report.write_text("offline check: PASS\n")
        revision = self.show(record)["revision"]
        code, out, err = self.invoke("evidence", "--record", record, "--input", str(report))
        self.assertEqual(code, 1)
        self.assertIn("unattached launches unknown", err)
        state = self.show(record)
        self.assertEqual((state["revision"], state["record"]["assignments"][0]["state"]), (revision, "launching"))
        self.ok(self.invoke("observe", "--record", record, "--assignment", "write-1", "--state", "completed",
                            "--invocation", "synthetic-host-session-1", "--boundary-observations", "Host session"))
        leftover = Path(record) / "staging" / "interrupted-write.tmp"
        leftover.write_bytes(b"partial object bytes")
        result = self.ok(self.invoke("evidence", "--record", record, "--input", str(report)))
        self.assertEqual(result["result"]["result"]["quarantined"], ["interrupted-write.tmp"])
        self.assertFalse(leftover.exists())
        self.assertEqual((Path(record) / "quarantine" / leftover.name).read_bytes(), b"partial object bytes")

    def test_rejected_or_deferred_findings_cannot_complete_over_changes_required(self):
        profile = json.loads(self.profile.read_text())
        agents = {**profile["agents"], "reviewer": {"model": "synthetic-reviewer-1", "transport": "claude-cli",
                                                    "reasoning": "inherit"}}
        self.use_profile(agents=agents, review={**profile["review"], "on_consequential_work": "single",
                                                "candidates": ["reviewer"], "max_followup_rounds": 1})
        record, host = self.begin_task(extra=("--reviewer", "reviewer"))
        initial = self.ok(self.context(record, host, "review", 0, "review-0"))
        self.ok(self.invoke("assignment", "--record", record, "--id", "review-1", "--packet", initial["packet"],
                            "--agent", "reviewer", "--role", "reviewer", "--output-destination", str(host / "r1.json")))
        self.ok(self.invoke("observe", "--record", record, "--assignment", "review-1", "--state", "completed",
                            "--invocation", "review-session-1", "--boundary-observations", "Fresh synthetic session"))
        review = self.shipped_example("verdict")
        review.update(assignment="review-1", artifact=initial["artifact"], packet=initial["packet"],
                      verdict="changes_required")
        review["verification"][0]["object"] = initial["artifact"]
        review["findings"] = [{"id": "F1", "location": "source.txt", "scenario": "Disputed wording",
                               "evidence": "Reviewer reading", "uncertainty": "Medium",
                               "recommendation": "Reword", "material": True}]
        (host / "r1.json").write_text(json.dumps(review))
        self.assertTrue(self.ok(self.invoke("import-review", "--record", record, "--input", str(host / "r1.json")))["valid_review"])
        report = self.root / "rebuttal.txt"
        report.write_text("Owner evidence that the original wording satisfies R1\n")
        evidence = self.ok(self.invoke("evidence", "--record", record, "--input", str(report)))["evidence"]
        for decision in ("rejected", "deferred"):
            with self.subTest(decision=decision):
                disposition = self.shipped_example("decision")
                disposition.update(finding="F1", decision=decision, evidence=[evidence], criterion_compatible=True,
                                   reason=f"Lead {decision} F1 with retained evidence")
                path = host / f"disposition-{decision}.json"
                path.write_text(json.dumps(disposition))
                self.ok(self.invoke("command", "--record", record, "--entity", "finding", "--action", "resolve",
                                    "--input", str(path)))
                revision = self.show(record)["revision"]
                code, out, err = self.invoke("complete", "--record", record, "--evidence", evidence,
                                             "--reason", "Attempted completion over changes_required")
                self.assertEqual(code, 1)
                self.assertIn("did not approve current artifact", err)
                state = self.show(record)
                self.assertEqual((state["state"], state["revision"]), ("active", revision))
        # No same-artifact adjudication: a follow-up review of the unchanged source is refused.
        code, out, err = self.context(record, host, "review", 1, "same-artifact")
        self.assertEqual(code, 1)
        self.assertIn("changed artifact", err)
        self.assertEqual(self.show(record)["state"], "active")

    def test_invalid_review_is_not_success(self):
        record, host = self.begin_task()
        invalid = self.root / "invalid.json"
        invalid.write_text('{"wrong": "contract"}')
        code, out, err = self.invoke("import-review", "--record", record, "--input", str(invalid))
        self.assertEqual(code, 1, out + err)
        self.assertFalse(json.loads(out)["valid_review"])
        self.assertEqual(json.loads(out)["result"]["result"]["validation"], "rejected")


if __name__ == "__main__":
    unittest.main()
