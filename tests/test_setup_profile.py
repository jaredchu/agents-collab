"""Tests for skills/agents-collab/scripts/setup_profile.py, the profile wizard.

Run from the repository root:

    python3 -m unittest discover -s tests -v

Every path lives in a fresh system temporary directory (TMPDIR is honoured).
Subprocess runs use explicit temporary --output paths without changing HOME.
Default-location tests override the wizard's default target in-process, so
the real home directory and profile are never touched.
Model IDs are synthetic. No network, credentials or model calls.
Requires Python 3.9+ and no third-party packages.
"""

import errno
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "agents-collab" / "scripts"
SCRIPT = SCRIPTS / "setup_profile.py"
VALIDATOR = SCRIPTS / "validate_profile.py"

_previous_flag = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    _spec = importlib.util.spec_from_file_location("setup_profile", SCRIPT)
    sp = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(sp)
finally:
    sys.dont_write_bytecode = _previous_flag
vp = sp.vp

# label, writer choice, writer model/transport/reasoning, reviewer count,
# two reviewers (the second with a custom level), default review, recipe name,
# records root, final confirmation.
TEAM_ANSWERS = [
    "synthetic-team", "2", "vendor-a-model-1", "2", "4",
    "2",
    "vendor-b-model-2", "1", "1",
    "vendor-c-model-3", "2", "5", "deep-think",
    "", "", "", "yes",
]
TEAM_PROFILE = {
    "version": 1,
    "name": "synthetic-team",
    "agents": {
        "lead": {"model": "current", "transport": "host", "reasoning": "inherit"},
        "writer": {"model": "vendor-a-model-1", "transport": "claude-cli", "reasoning": "high"},
        "reviewer1": {"model": "vendor-b-model-2", "transport": "codex-native", "reasoning": "inherit"},
        "reviewer2": {"model": "vendor-c-model-3", "transport": "claude-cli", "reasoning": "deep-think"},
    },
    "routing": {"small_writer": "current-session", "substantial_writer": "writer"},
    "review": {
        "on_consequential_work": "single",
        "candidates": ["reviewer1", "reviewer2"],
        "prefer_different_model": True,
        "recipes": {"all-reviewers": ["reviewer1", "reviewer2"]},
        "max_followup_rounds": 1,
    },
    "effort_check": "supported-control",
    "access": "existing-authorized-access",
    "bounds": {"enforcement": "advisory", "writer_minutes": 30,
               "reviewer_minutes": 10, "review_output_words": 800},
    "records_root": "~/.local/state/agents-collab",
}
# label, writer (current lead), zero reviewers, records root, confirmation.
SOLO_ANSWERS = ["", "", "", "", "y"]


class ScriptedInput:
    """A stdin stand-in: answers in order, optional hooks before a given answer."""

    def __init__(self, answers, hooks=None, interrupt_at=None):
        self.answers = list(answers)
        self.hooks = hooks or {}
        self.interrupt_at = interrupt_at
        self.count = 0

    def readline(self):
        index = self.count
        self.count += 1
        if index == self.interrupt_at:
            raise KeyboardInterrupt
        if index in self.hooks:
            self.hooks[index]()
        return self.answers[index] + "\n" if index < len(self.answers) else ""


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class WizardCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="agents-collab-setup-")
        self.tmp = Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.out = self.tmp / "profiles" / "profile.json"

    def tearDown(self):
        self._tmp.cleanup()

    def run_main(self, args, answers=(), stdin=None):
        if "--output" not in args and "--help" not in args and "-h" not in args:
            self.assertTrue(sp.resolve_output(None).is_relative_to(self.tmp))
        stdout, stderr = io.StringIO(), io.StringIO()
        code = sp.main(list(args), stdin or ScriptedInput(answers), stdout, stderr)
        return code, stdout.getvalue(), stderr.getvalue()

    def run_cli(self, args, answers=(), bytecode=False, timeout=30):
        self.assertIn("--output", args, "Subprocess tests require a temporary output target")
        command = [sys.executable, "-I"] + ([] if bytecode else ["-B"])
        return subprocess.run(
            command + [str(SCRIPT), *args], input="".join(a + "\n" for a in answers),
            cwd=str(self.tmp), capture_output=True, text=True, timeout=timeout,
            env=dict(os.environ, TMPDIR=str(self.tmp)),
        )

    def load(self, path):
        issues = vp.check_file(str(path))
        self.assertEqual(issues, [], "\n".join(map(str, issues)))
        return json.loads(path.read_text(encoding="utf-8"))

    def assertOnlyEntries(self, directory, names):
        self.assertEqual(sorted(p.name for p in directory.iterdir()), sorted(names))


class Flows(WizardCase):
    def test_delegated_writer_and_reviewers_through_the_script(self):
        result = self.run_cli(["--output", str(self.out)], TEAM_ANSWERS)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.load(self.out)
        self.assertEqual(data, TEAM_PROFILE)
        self.assertEqual(tuple(data), vp.TOP_KEYS)
        self.assertEqual(mode(self.out), 0o600)
        self.assertEqual(mode(self.out.parent), 0o700)
        self.assertOnlyEntries(self.out.parent, ["profile.json"])
        self.assertIn("not run automatically", result.stdout)
        self.assertIn("Not checked: model availability", result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        # End to end with the unchanged validator command.
        check = subprocess.run([sys.executable, "-I", "-B", str(VALIDATOR), str(self.out)],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_solo_profile_at_the_default_location(self):
        config = self.home / ".config"
        config.mkdir(mode=0o755)
        os.chmod(config, 0o755)
        target = config / "agents-collab" / "profile.json"
        with mock.patch.object(sp, "DEFAULT_OUTPUT", str(target)):
            code, _, err = self.run_main([], SOLO_ANSWERS)
        self.assertEqual(code, 0, err)
        data = self.load(target)
        self.assertEqual(data["name"], "personal")
        self.assertEqual(data["agents"], {"lead": {"model": "current", "transport": "host",
                                                   "reasoning": "inherit"}})
        self.assertEqual(data["routing"], {"small_writer": "current-session",
                                           "substantial_writer": "current-session"})
        self.assertEqual(data["review"]["on_consequential_work"], "none")
        self.assertEqual(data["review"]["candidates"], [])
        self.assertEqual(data["review"]["recipes"], {})
        self.assertEqual(data["records_root"], "~/.local/state/agents-collab")
        self.assertEqual(mode(target), 0o600)
        self.assertEqual(mode(target.parent), 0o700)  # created
        self.assertEqual(mode(config), 0o755)  # existing: unchanged

    def test_invalid_answers_reprompt_and_choices_are_recorded(self):
        answers = [
            "", "3", "x", "2",
            "bad model", "current", "-flag", "vendor-a-model-1",
            "0", "1",
            "5", "High", "default", "max-effort",
            "9", "1",
            "vendor-b-model-2", "2", "3",
            "maybe", "n",
            "relative/records", "~", "~/../x", "~/records/agents-collab-test",
            "y",
        ]
        code, out, err = self.run_main(["--output", str(self.out)], answers)
        self.assertEqual(code, 0, err)
        for message in ("Enter a number from 1 to 2", "exact ID", "'current' means the lead",
                        "lowercase level", "ambiguous", "from 0 to 8", "Answer y or n",
                        "records_root must"):
            with self.subTest(message=message):
                self.assertIn(message, out)
        data = self.load(self.out)
        self.assertEqual(data["agents"]["writer"], {"model": "vendor-a-model-1",
                                                    "transport": "codex-native",
                                                    "reasoning": "max-effort"})
        self.assertEqual(data["agents"]["reviewer1"], {"model": "vendor-b-model-2",
                                                       "transport": "claude-cli",
                                                       "reasoning": "medium"})
        self.assertEqual(data["review"]["on_consequential_work"], "none")
        self.assertEqual(data["review"]["candidates"], ["reviewer1"])
        self.assertEqual(data["review"]["recipes"], {})  # one reviewer: no recipe prompt
        self.assertEqual(data["records_root"], "~/records/agents-collab-test")

    def test_repeated_invalid_answers_cancel(self):
        code, _, err = self.run_main(["--output", str(self.out)], ["", "9", "9", "9", "9", "9"])
        self.assertEqual(code, 1)
        self.assertIn("nothing was written", err)
        self.assertFalse(self.out.parent.exists())


class NoWrite(WizardCase):
    def test_dry_run_writes_nothing(self):
        result = self.run_cli(["--dry-run", "--output", str(self.out)], TEAM_ANSWERS[:-1])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Dry run: nothing was written", result.stdout)
        self.assertIn('"vendor-c-model-3"', result.stdout)
        self.assertOnlyEntries(self.home, [])

    def test_dry_run_with_existing_profile_leaves_it(self):
        self.out.parent.mkdir()
        self.out.write_text("keep", encoding="utf-8")
        code, out, err = self.run_main(["--output", str(self.out), "--dry-run"], SOLO_ANSWERS[:-1])
        self.assertEqual(code, 0, err)
        self.assertIn("leaves it unchanged", out)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "keep")

    def test_decline_end_of_input_and_interrupt_write_nothing(self):
        for name, answers in (("declined", SOLO_ANSWERS[:-1] + ["n"]),
                              ("default no", SOLO_ANSWERS[:-1] + [""])):
            with self.subTest(case=name):
                code, out, _ = self.run_main(["--output", str(self.out)], answers)
                self.assertEqual(code, 1)
                self.assertIn("nothing was written", out)
                self.assertFalse(self.out.parent.exists())
        result = self.run_cli(["--output", str(self.out)], TEAM_ANSWERS[:4])
        self.assertEqual(result.returncode, 1)
        self.assertIn("nothing was written", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.out.parent.exists())
        for index in (0, len(SOLO_ANSWERS) - 1):
            with self.subTest(interrupt_at=index):
                code, _, err = self.run_main(
                    ["--output", str(self.out)],
                    stdin=ScriptedInput(SOLO_ANSWERS, interrupt_at=index))
                self.assertEqual(code, 130)
                self.assertIn("Interrupted; nothing was written", err)
                self.assertNotIn("Traceback", err)
                self.assertFalse(self.out.parent.exists())

    def test_no_bytecode_cache_in_the_skill_scripts(self):
        cache = SCRIPTS / "__pycache__"
        existed = cache.exists()
        result = self.run_cli(["--dry-run", "--output", str(self.out)], SOLO_ANSWERS[:-1], bytecode=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        if not existed:
            self.assertFalse(cache.exists(), "the wizard wrote a bytecode cache")


class Targets(WizardCase):
    def make_existing(self, text="old profile"):
        self.out.parent.mkdir()
        os.chmod(self.out.parent, 0o755)
        self.out.write_text(text, encoding="utf-8")
        os.chmod(self.out, 0o644)

    def test_existing_profile_preserved_without_replace(self):
        self.make_existing()
        result = self.run_cli(["--output", str(self.out)], SOLO_ANSWERS)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--replace", result.stderr)
        self.assertNotIn("Profile label", result.stdout)  # refused before any question
        self.assertEqual(self.out.read_text(encoding="utf-8"), "old profile")
        default = self.home / ".config" / "agents-collab" / "profile.json"
        default.parent.mkdir(parents=True)
        default.write_text("default keep", encoding="utf-8")
        with mock.patch.object(sp, "DEFAULT_OUTPUT", str(default)):
            code, _, _ = self.run_main([], SOLO_ANSWERS)
        self.assertEqual(code, 2)
        self.assertEqual(default.read_text(encoding="utf-8"), "default keep")

    def test_confirmed_replace_and_declined_replace(self):
        self.make_existing()
        code, _, _ = self.run_main(["--output", str(self.out), "--replace"],
                                   SOLO_ANSWERS[:-1] + ["n"])
        self.assertEqual(code, 1)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "old profile")
        code, out, err = self.run_main(["--output", str(self.out), "--replace"], SOLO_ANSWERS)
        self.assertEqual(code, 0, err)
        self.assertIn("Replace the existing profile", out)
        self.assertEqual(self.load(self.out)["name"], "personal")
        self.assertEqual(mode(self.out), 0o600)
        self.assertEqual(mode(self.out.parent), 0o755)  # existing parent unchanged
        self.assertOnlyEntries(self.out.parent, ["profile.json"])  # no backup or staging file

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks not available")
    def test_symlinks_are_rejected_and_not_followed(self):
        self.out.parent.mkdir()
        pointee = self.tmp / "pointee.json"
        pointee.write_text("pointee", encoding="utf-8")
        missing = self.tmp / "missing.json"
        for name, destination in (("to file", pointee), ("dangling", missing)):
            with self.subTest(link=name):
                try:
                    os.symlink(str(destination), str(self.out))
                except OSError as exc:
                    self.skipTest(f"cannot create symlink: {exc}")
                for flags in ([], ["--replace"], ["--dry-run"]):
                    code, out, err = self.run_main(["--output", str(self.out), *flags], SOLO_ANSWERS)
                    self.assertEqual(code, 2)
                    self.assertIn("symbolic link", err)
                    self.assertEqual(out, "")
                self.assertTrue(self.out.is_symlink())
                self.assertEqual(os.readlink(str(self.out)), str(destination))
                self.out.unlink()
        self.assertEqual(pointee.read_text(encoding="utf-8"), "pointee")
        self.assertFalse(missing.exists())

    def test_nonregular_targets_are_rejected(self):
        self.out.mkdir(parents=True)  # a directory at the output path
        code, _, err = self.run_main(["--output", str(self.out), "--replace"], SOLO_ANSWERS)
        self.assertEqual(code, 2)
        self.assertIn("not a regular file", err)
        blocker = self.tmp / "plain-file"
        blocker.write_text("x", encoding="utf-8")
        code, _, err = self.run_main(["--output", str(blocker / "profile.json")], SOLO_ANSWERS)
        self.assertEqual(code, 2)
        self.assertIn("not a directory", err)
        if hasattr(os, "mkfifo"):
            fifo = self.tmp / "profile.fifo"
            os.mkfifo(str(fifo))
            code, _, err = self.run_main(["--output", str(fifo), "--replace"], SOLO_ANSWERS)
            self.assertEqual(code, 2)
            self.assertTrue(stat.S_ISFIFO(os.lstat(fifo).st_mode))

    def test_target_appearing_during_the_wizard_is_not_clobbered(self):
        def appear():
            self.out.parent.mkdir()
            self.out.write_text("concurrent", encoding="utf-8")

        stdin = ScriptedInput(SOLO_ANSWERS, hooks={len(SOLO_ANSWERS) - 1: appear})
        code, _, err = self.run_main(["--output", str(self.out)], stdin=stdin)
        self.assertEqual(code, 2)
        self.assertIn("appeared", err)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "concurrent")
        self.assertOnlyEntries(self.out.parent, ["profile.json"])

    def test_changed_replacement_target_is_not_replaced(self):
        self.make_existing()

        def change():
            self.out.write_text("edited elsewhere meanwhile", encoding="utf-8")

        stdin = ScriptedInput(SOLO_ANSWERS, hooks={len(SOLO_ANSWERS) - 1: change})
        code, _, err = self.run_main(["--output", str(self.out), "--replace"], stdin=stdin)
        self.assertEqual(code, 2)
        self.assertIn("changed or disappeared", err)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "edited elsewhere meanwhile")
        self.assertOnlyEntries(self.out.parent, ["profile.json"])

    def test_failed_publication_leaves_no_partial_target(self):
        failure = OSError(errno.EIO, "synthetic failure")
        with mock.patch.object(sp.os, "link", side_effect=failure):
            code, _, err = self.run_main(["--output", str(self.out)], SOLO_ANSWERS)
        self.assertEqual(code, 2)
        self.assertIn("Nothing was written", err)
        self.assertOnlyEntries(self.out.parent, [])  # created parent stays empty
        self.out.write_text("old profile", encoding="utf-8")
        with mock.patch.object(sp.os, "replace", side_effect=failure):
            code, _, err = self.run_main(["--output", str(self.out), "--replace"], SOLO_ANSWERS)
        self.assertEqual(code, 2)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "old profile")
        self.assertOnlyEntries(self.out.parent, ["profile.json"])


class CleanupFailures(WizardCase):
    """Staging-file removal refused (EACCES): reported, never hidden or crashing."""

    def refuse_unlink(self, refused):
        def refuse(path, *args, **kwargs):
            refused.append(Path(path))
            raise PermissionError(errno.EACCES, "Permission denied", os.fspath(path))
        return mock.patch.object(sp.os, "unlink", side_effect=refuse)

    def assertLeftover(self, refused, err, entries):
        self.assertEqual(len(refused), 1)
        leftover = refused[0]
        self.assertEqual(leftover.parent, self.out.parent)
        self.assertTrue(leftover.name.startswith(".profile.json."))
        self.assertIn(f"(Permission denied): {leftover}", err)
        self.assertIn("Delete it manually", err)
        self.assertNotIn("nothing was written", err.lower())
        self.assertNotIn("Traceback", err)
        self.assertOnlyEntries(self.out.parent, entries + [leftover.name])
        self.assertEqual(mode(leftover), 0o600)
        return leftover

    def test_after_publication_saved_but_not_clean_success(self):
        refused = []
        with self.refuse_unlink(refused):
            code, out, err = self.run_main(["--output", str(self.out)], SOLO_ANSWERS)
        self.assertEqual(code, 3)
        self.assertEqual(self.load(self.out)["name"], "personal")  # valid, complete target
        self.assertEqual(mode(self.out), 0o600)
        self.assertIn(f"Saved {self.out} (mode 0600).", out)
        self.assertIn("error: the profile was saved, but cleanup is incomplete", err)
        self.assertIn("does not affect the saved profile", err)
        leftover = self.assertLeftover(refused, err, ["profile.json"])
        self.assertTrue(os.path.samefile(leftover, self.out))  # same private data
        leftover.unlink()
        self.assertEqual(self.load(self.out)["name"], "personal")

    def test_before_new_publication_keeps_the_original_cause(self):
        refused = []
        with mock.patch.object(sp.os, "link", side_effect=OSError(errno.EIO, "synthetic failure")), \
                self.refuse_unlink(refused):
            code, out, err = self.run_main(["--output", str(self.out)], SOLO_ANSWERS)
        self.assertEqual(code, 2)
        self.assertIn("error: cannot publish without risking an overwrite here "
                      "(synthetic failure)", err)
        self.assertIn("The profile was not saved.", err)
        self.assertNotIn("Saved", out)
        self.assertFalse(os.path.lexists(self.out))
        self.assertLeftover(refused, err, [])

    def test_before_replacement_keeps_the_original_cause(self):
        self.out.parent.mkdir()
        self.out.write_text("old profile", encoding="utf-8")
        refused = []
        with mock.patch.object(sp.os, "replace", side_effect=OSError(errno.EIO, "synthetic failure")), \
                self.refuse_unlink(refused):
            code, out, err = self.run_main(["--output", str(self.out), "--replace"], SOLO_ANSWERS)
        self.assertEqual(code, 2)
        self.assertIn("error: cannot write the profile: synthetic failure.", err)
        self.assertIn("The profile was not saved.", err)
        self.assertNotIn("Saved", out)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "old profile")
        self.assertLeftover(refused, err, ["profile.json"])

    def test_interrupted_publication_reports_a_remaining_staging_file(self):
        with mock.patch.object(sp.os, "link", side_effect=KeyboardInterrupt):
            code, _, err = self.run_main(["--output", str(self.out)], SOLO_ANSWERS)
        self.assertEqual(code, 130)
        self.assertIn("Interrupted; nothing was written.", err)
        self.assertOnlyEntries(self.out.parent, [])
        refused = []
        with mock.patch.object(sp.os, "link", side_effect=KeyboardInterrupt), \
                self.refuse_unlink(refused):
            code, _, err = self.run_main(["--output", str(self.out)], SOLO_ANSWERS)
        self.assertEqual(code, 130)
        self.assertIn("Interrupted; the profile was not saved.", err)
        self.assertFalse(os.path.lexists(self.out))
        self.assertLeftover(refused, err, [])


if __name__ == "__main__":
    unittest.main()
