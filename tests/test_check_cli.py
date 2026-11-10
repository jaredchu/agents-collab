"""Portable failure/safety checks for the local CLI regression gate (synthetic Git, fake commands)."""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_cli", REPO / "scripts/check_cli.py")
check_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_cli)

GOOD_UNITTEST = ("test_a (test_x.Plain) ... ok\n"
                 "test_real (test_backend.RealBackendTests) ... ok\n"
                 "\n----------------------------------------------------------------------\n"
                 "Ran 2 tests in 0.1s\n\nOK\n")
GOOD_CARGO = ("running 0 tests\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured\n"
              "running 2 tests\ntest result: ok. 2 passed; 0 failed; 0 ignored; 0 measured\n")


def py(code):
    return [sys.executable, "-c", code]


def fake_plan(build_ok=True, suite_output=GOOD_UNITTEST, suite_code=0):
    build = ("import os,pathlib;d=pathlib.Path(os.environ['CARGO_TARGET_DIR'],'debug');"
             "d.mkdir(parents=True);(d/'agents-collab').write_bytes(b'fake-binary')") if build_ok else "pass"
    suite = ("import os,sys;assert os.environ['AGENTS_COLLAB_TEST_BINARY'].endswith('bin/agents-collab');"
             f"sys.stderr.write({suite_output!r});sys.exit({suite_code})")
    return lambda snapshot, scratch, binary: [
        ("cargo-fmt", py("pass"), {}, None),
        ("cargo-build", py(build), {}, None),
        ("cargo-test", py(f"print({GOOD_CARGO!r})"), {}, check_cli.analyze_cargo_test),
        ("python-suite", py(suite), {"AGENTS_COLLAB_TEST_BINARY": str(binary)}, check_cli.analyze_unittest),
    ]


class AnalyzerTests(unittest.TestCase):
    def test_unittest_success_requires_real_engine_coverage_and_no_skips(self):
        self.assertIsNone(check_cli.analyze_unittest(GOOD_UNITTEST))
        modern = GOOD_UNITTEST.replace("(test_backend.RealBackendTests)",
                                       "(test_backend.RealBackendTests.test_real)")
        self.assertIsNone(check_cli.analyze_unittest(modern))
        docstring = GOOD_UNITTEST.replace("(test_backend.RealBackendTests) ... ok",
                                          "(test_backend.RealBackendTests)\nReal engine flow. ... ok")
        self.assertIsNone(check_cli.analyze_unittest(docstring))
        refused = {
            "skip": GOOD_UNITTEST.replace("Plain) ... ok", "Plain) ... skipped 'no binary'").replace(
                "\nOK\n", "\nOK (skipped=1)\n"),
            "real class skipped": GOOD_UNITTEST.replace("RealBackendTests) ... ok",
                                                        "RealBackendTests) ... skipped 'set binary'"),
            "no real class": GOOD_UNITTEST.replace("test_backend.RealBackendTests", "test_backend.BackendTests"),
            "zero tests": "\nRan 0 tests in 0.0s\n\nOK\n",
            "failure": GOOD_UNITTEST.replace("\nOK\n", "\nFAILED (failures=1)\n"),
            "truncated": GOOD_UNITTEST.replace("\nOK\n", "\n"),
        }
        for label, text in refused.items():
            with self.subTest(case=label):
                self.assertIsNotNone(check_cli.analyze_unittest(text))

    def test_cargo_success_requires_nonzero_unignored_passes(self):
        self.assertIsNone(check_cli.analyze_cargo_test(GOOD_CARGO))
        for label, text in {"none": "", "ignored": GOOD_CARGO.replace("0 ignored; 0 measured\nrunning 2",
                                                                      "1 ignored; 0 measured\nrunning 2"),
                            "zero passed": GOOD_CARGO.replace("2 passed", "0 passed"),
                            "failed": GOOD_CARGO.replace("ok. 2 passed; 0 failed", "FAILED. 1 passed; 1 failed")}.items():
            with self.subTest(case=label):
                self.assertIsNotNone(check_cli.analyze_cargo_test(text))


class GateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic@example.com")
        (self.source / "cli").mkdir()
        (self.source / "cli/Cargo.toml").write_text("[package]\nname = \"fake\"\n")
        (self.source / "run.sh").write_text("#!/bin/sh\n")
        (self.source / "run.sh").chmod(0o755)
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.outside = self.root / "outside"
        self.outside.mkdir()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.source), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def main(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(check_cli, "check_platform"), \
                mock.patch.object(check_cli, "storage_observation", return_value={"mount_options": ["test"]}):
            code = check_cli.main(["--source", str(self.source), *args])
        return code, err.getvalue()

    def assert_refused_without_writes(self, scratch, fragment, *extra):
        before = sorted(p for p in self.root.rglob("*") if ".git" not in p.parts)
        code, err = self.main("--scratch", str(scratch), *extra)
        self.assertEqual(code, 2, err)
        self.assertIn("refused before writing", err)
        self.assertIn(fragment, err)
        self.assertEqual(sorted(p for p in self.root.rglob("*") if ".git" not in p.parts), before)

    def test_scratch_overlap_existing_relative_and_git_locations_are_refused(self):
        self.assert_refused_without_writes(self.source / "scratch", "overlaps")
        self.assert_refused_without_writes(self.outside, "already exists")
        self.assert_refused_without_writes(self.root / "missing/scratch", "parent must already exist")
        self.assert_refused_without_writes(Path("relative-scratch"), "absolute")
        other = self.root / "other-repo"
        other.mkdir()
        subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
        self.assert_refused_without_writes(other / "scratch", "outside every Git repository")

    def test_existing_scratch_contents_are_never_replaced(self):
        marker = self.outside / "result.json"
        marker.write_text("caller file")
        self.assert_refused_without_writes(self.outside, "already exists")
        self.assertEqual(marker.read_text(), "caller file")

    def test_dirty_source_and_unknown_revision_are_refused_before_writes(self):
        (self.source / "untracked.txt").write_text("dirty")
        self.assert_refused_without_writes(self.outside / "run", "not clean")
        (self.source / "untracked.txt").unlink()
        (self.source / "run.sh").write_text("#!/bin/sh\necho changed\n")
        self.assert_refused_without_writes(self.outside / "run", "not clean")
        self.git("checkout", "--", "run.sh")
        self.assert_refused_without_writes(self.outside / "run", "failed", "--revision", "no-such-revision")

    def gate(self, factory):
        scratch = self.outside / "run"
        with mock.patch.object(check_cli, "plan", factory):
            code, err = self.main("--scratch", str(scratch))
        return code, scratch, json.loads((scratch / "result.json").read_text())

    def test_passing_gate_records_pinned_snapshot_binary_and_logs(self):
        code, scratch, result = self.gate(fake_plan())
        self.assertEqual((code, result["status"], result["failure"]), (0, "passed", None))
        self.assertEqual(result["source"]["revision"], self.git("rev-parse", "HEAD"))
        self.assertEqual(result["source"]["tree"], self.git("rev-parse", "HEAD^{tree}"))
        self.assertEqual(result["source"]["archive_sha256"], check_cli.sha256(scratch / "source.tar"))
        self.assertEqual(result["binary"]["sha256"], check_cli.sha256(scratch / "bin/agents-collab"))
        self.assertTrue(os.access(scratch / "source/run.sh", os.X_OK))
        self.assertEqual([s["status"] for s in result["steps"]], ["passed"] * 4)
        for step in result["steps"]:
            self.assertEqual(step["exit_status"], 0)
            self.assertTrue((scratch / step["stdout"]).is_file())
        self.assertEqual(result["environment"]["TMPDIR"], str(scratch / "tmp"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_failing_command_stops_and_keeps_incomplete_evidence(self):
        def factory(snapshot, scratch, binary):
            steps = fake_plan()(snapshot, scratch, binary)
            steps[0] = ("cargo-fmt", py("import sys;print('diff');sys.exit(1)"), {}, None)
            return steps
        code, scratch, result = self.gate(factory)
        self.assertEqual((code, result["status"]), (1, "failed"))
        self.assertIn("cargo-fmt exited 1", result["failure"])
        self.assertEqual([(s["name"], s["status"], s["exit_status"]) for s in result["steps"]],
                         [("cargo-fmt", "failed", 1)])
        self.assertIn("diff", (scratch / result["steps"][0]["stdout"]).read_text())

    def test_exit_zero_with_skipped_tests_is_not_success(self):
        skipped = GOOD_UNITTEST.replace("\nOK\n", "\nOK (skipped=5)\n")
        code, _, result = self.gate(fake_plan(suite_output=skipped))
        self.assertEqual((code, result["status"]), (1, "failed"))
        self.assertEqual(result["steps"][-1]["exit_status"], 0)
        self.assertIn("skip", result["steps"][-1]["analysis"])

    def test_build_without_binary_fails_before_python_suite(self):
        code, _, result = self.gate(fake_plan(build_ok=False))
        self.assertEqual((code, result["status"]), (1, "failed"))
        self.assertIn("no binary", result["failure"])
        self.assertNotIn("python-suite", [s["name"] for s in result["steps"]])

    def test_unsupported_platform_refused(self):
        with mock.patch.object(check_cli.platform, "system", return_value="Linux"):
            with self.assertRaisesRegex(check_cli.Refused, "macOS arm64"):
                check_cli.check_platform()

    def test_symlink_archive_member_rejected(self):
        os.symlink("/etc/passwd", self.source / "link")
        self.git("add", "link")
        self.git("commit", "-qm", "symlink")
        code, scratch, result = self.gate(fake_plan())
        self.assertEqual((code, result["status"]), (1, "failed"))
        self.assertIn("unsupported archive member", result["failure"])
        self.assertFalse((scratch / "source/link").exists())


if __name__ == "__main__":
    unittest.main()
