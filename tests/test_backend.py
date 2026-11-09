"""Optional backend invariants; real engine lifecycle is opt-in and offline."""
import argparse
import contextlib
import io
import json
import os
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

    def test_native_observation_does_not_invent_attestation_or_exit(self):
        args = argparse.Namespace(assignment="review-1", state="completed", invocation="host-session-1",
                                  interface_model=None, interface_effort=None,
                                  boundary_observations="Fresh native session; filesystem is not isolated",
                                  exit_code=None, reason="Host observed completion")
        value = backend.receipt(args, {})
        self.assertIsNone(value["exit_code"])
        self.assertIsNone(value["observed_model"])
        self.assertIsNone(value["observed_effort"])
        self.assertTrue(value["reconciled"])
        self.assertFalse(value["absence_established"])


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
