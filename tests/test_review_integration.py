"""Review coverage guard, native task identity and role final-output contracts.

Synthetic data only. Portable cases use disposable Git repositories (synthetic
fixture commits) and stub engines; a stub is not real-engine evidence. Real
engine cases are opt-in through AGENTS_COLLAB_TEST_BINARY and call no model.
"""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills/agents-collab/scripts"
sys.path.insert(0, str(SCRIPTS))
import backend
import install_backend as safe

HEX = re.compile(r"[0-9a-f]{64}")


def inventory(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


# Fixture Git commands ignore system/global configuration and inherited repository
# redirection, through this subprocess environment only; no setting is changed.
# The helper and engine under test still run Git with the inherited environment.
_FIXTURE_GIT_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                     "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS",
                     "GIT_CONFIG_COUNT")


def fixture_git_env():
    env = {key: value for key, value in os.environ.items()
           if key not in _FIXTURE_GIT_DROP and not key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          env=fixture_git_env())


def commit(repo, message="fixture"):
    git(repo, "-c", "user.name=Synthetic Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-qm", message)


def make_repo(root, files):
    repo = root / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(repo, "add", "-A")
    commit(repo)
    return repo


def make_nested_repo(repo, path="tests/embedded"):
    """Real Git fixture: the outer repository reports this as a directory name."""
    nested = repo / path
    nested.mkdir(parents=True)
    git(nested, "init", "-q")
    (nested / "source.txt").write_text("synthetic nested source\n")
    git(nested, "add", "source.txt")
    commit(nested)
    return path + "/"


def documented_review_schema():
    """Field names of the review contract example shipped in the skill reference."""
    text = (SCRIPTS.parent / "references/backend.md").read_text()
    section = text.split("## Review contract", 1)[1]
    block = re.search(r"```json\n(.*?)```", section, re.S).group(1)
    return json.loads(block)


class ExplicitRouteTests(unittest.TestCase):
    def test_default_solo_skips_backend_and_profile(self):
        out = io.StringIO()
        with mock.patch.object(backend, "selected_backend", side_effect=AssertionError("unexpected selector read")), \
             mock.patch.object(backend, "load_profile", side_effect=AssertionError("unexpected profile read")), \
             contextlib.redirect_stdout(out):
            self.assertEqual(backend.main(["route"]), 0)
        self.assertEqual(json.loads(out.getvalue()),
                         {"route": "solo", "review_required": False, "record": None})

    def test_flag_requires_one_reviewer_before_backend_selection(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(backend, "selected_backend", side_effect=AssertionError("unexpected selector read")), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(backend.main(["route", "--review-required"]), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("exactly one --reviewer", json.loads(err.getvalue())["error"])


BASE_FILES = {
    ".gitignore": "*.log\nbuild/\n",
    "src/app.py": "print('original')\n",
    "docs/guide.md": "# Guide\n",
    "tests/test_old.py": "# old synthetic test\n",
    "other/notes.txt": "unrelated preexisting notes\n",
}
SCOPE = ["src/app.py", "docs", "tests"]


class CoverageFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = make_repo(self.root, BASE_FILES)
        self.state = {"state": "active",
                      "spec": {"repository": str(self.repo), "project": "fixture", "task": "review",
                               "editable_scope": list(SCOPE),
                               "requirements": [{"id": "R1", "kind": "requirement", "text": "Synthetic",
                                                 "source": "test"}]}}

    def args(self, *paths, purpose="review", unrelated=None):
        return argparse.Namespace(purpose=purpose, paths=list(paths), unrelated_changes=unrelated)

    def change_every_kind(self):
        """Staged edit, unstaged edit, untracked new test, staged new doc, all in scope."""
        (self.repo / "src/app.py").write_text("print('staged')\n")
        git(self.repo, "add", "src/app.py")
        (self.repo / "docs/guide.md").write_text("# Guide\nunstaged edit\n")
        (self.repo / "tests/test_new.py").write_text("# new untracked test\n")
        (self.repo / "docs/new.md").write_text("new staged doc\n")
        git(self.repo, "add", "docs/new.md")
        return {"src/app.py", "docs/guide.md", "tests/test_new.py", "docs/new.md"}


class ReviewCoverageTests(CoverageFixture):
    def test_every_changed_scoped_path_is_required_and_selection_passes(self):
        changed = self.change_every_kind()
        before = inventory(self.root)
        coverage = backend.review_coverage(self.repo, SCOPE)
        self.assertEqual(coverage["required"], changed)
        self.assertEqual(coverage["unscoped"], set())
        self.assertEqual(coverage["head"], git(self.repo, "rev-parse", "HEAD").stdout.decode().strip())
        plan = backend.review_preflight(self.args(*sorted(changed)), self.state)
        self.assertEqual(set(plan["paths"]), changed)
        self.assertEqual(plan["unrelated"], set())
        self.assertEqual(before, inventory(self.root))

    def test_any_scoped_omission_refuses_and_names_the_path(self):
        changed = self.change_every_kind()
        for missing in sorted(changed):
            with self.subTest(missing=missing):
                with self.assertRaises(ValueError) as caught:
                    backend.review_preflight(self.args(*sorted(changed - {missing})), self.state)
                self.assertIn("omits task-scoped", str(caught.exception))
                self.assertIn(json.dumps(missing), str(caught.exception))
                self.assertIn("Nothing was frozen", str(caught.exception))

    def test_declaring_unrelated_never_admits_a_scoped_omission(self):
        changed = self.change_every_kind()
        (self.repo / "other/notes.txt").write_text("outside change\n")
        selection = sorted(changed - {"tests/test_new.py"})
        with self.assertRaisesRegex(ValueError, "omits task-scoped"):
            backend.review_preflight(self.args(*selection, unrelated="Preexisting work"), self.state)

    def test_outside_scope_dirty_work_needs_selection_or_explicit_declaration(self):
        (self.repo / "src/app.py").write_text("print('task change')\n")
        (self.repo / "other/notes.txt").write_text("preexisting unrelated edit\n")
        (self.repo / "scratch.txt").write_text("untracked outside scope\n")
        outside = {"other/notes.txt", "scratch.txt"}
        for declaration in (None, "", "   "):
            with self.subTest(declaration=declaration), self.assertRaises(ValueError) as caught:
                backend.review_preflight(self.args("src/app.py", unrelated=declaration), self.state)
            self.assertIn("outside the editable scope", str(caught.exception))
            for path in outside:
                self.assertIn(json.dumps(path), str(caught.exception))
        plan = backend.review_preflight(self.args("src/app.py", unrelated="Preexisting owner work"), self.state)
        self.assertEqual(plan["unrelated"], outside)
        # Selecting outside paths instead also satisfies the guard, with nothing declared.
        plan = backend.review_preflight(self.args("src/app.py", *sorted(outside)), self.state)
        self.assertEqual(plan["unrelated"], set())

    def test_deleted_scoped_paths_refuse_whether_staged_or_unstaged(self):
        for staged in (False, True):
            with self.subTest(staged=staged):
                git(self.repo, "reset", "-q", "--hard")
                if staged:
                    git(self.repo, "rm", "-q", "tests/test_old.py")
                else:
                    (self.repo / "tests/test_old.py").unlink()
                for paths in ((), ("tests/test_old.py",)):
                    with self.assertRaises(ValueError) as caught:
                        backend.review_preflight(self.args("src/app.py", *paths), self.state)
                    self.assertIn("deleted or absent", str(caught.exception))
                    self.assertIn(json.dumps("tests/test_old.py"), str(caught.exception))

    def test_rename_inside_directory_scope_requires_both_sides_and_refuses_deletion(self):
        state = copy.deepcopy(self.state)
        state["spec"]["editable_scope"] = ["tests"]
        git(self.repo, "mv", "tests/test_old.py", "tests/test_renamed.py")
        coverage = backend.review_coverage(self.repo, ["tests"])
        self.assertEqual(coverage["required"], {"tests/test_old.py", "tests/test_renamed.py"})
        with self.assertRaisesRegex(ValueError, "deleted or absent"):
            backend.review_preflight(self.args("tests/test_renamed.py"), state)

    def test_selected_absent_path_refuses(self):
        with self.assertRaisesRegex(ValueError, "deleted or absent"):
            backend.review_preflight(self.args("docs/never-existed.md", "src/app.py"), self.state)

    def test_nested_repository_git_entry_refuses_omitted_and_normalized_selections(self):
        entry = make_nested_repo(self.repo)
        self.assertEqual(git(self.repo, "ls-files", "--others", "--exclude-standard", "-z").stdout,
                         (entry + "\0").encode())
        self.assertEqual(backend.review_coverage(self.repo, SCOPE)["required"], {entry})
        before = inventory(self.root)
        for paths in (("src/app.py",), ("src/app.py", entry.rstrip("/"))):
            with self.subTest(paths=paths), self.assertRaises(ValueError) as caught:
                backend.review_preflight(self.args(*paths, unrelated="Cannot bypass scoped work"), self.state)
            message = str(caught.exception)
            self.assertIn("unsupported directory-shaped task change(s)", message)
            self.assertIn(json.dumps(entry), message)
            self.assertIn("nested repository", message)
            self.assertIn("another authorized review path", message)
            self.assertNotIn("select every changed path", message)
        self.assertEqual(before, inventory(self.root))

    def test_raw_trailing_slash_selection_keeps_relative_path_validation_boundary(self):
        entry = make_nested_repo(self.repo)
        before = inventory(self.root)
        with mock.patch.object(backend, "review_coverage") as coverage:
            with self.assertRaisesRegex(ValueError, "expected exact normalized relative source path"):
                backend.review_preflight(self.args(entry), self.state)
        coverage.assert_not_called()
        self.assertEqual(before, inventory(self.root))

    def test_nested_repository_outside_scope_keeps_unrelated_declaration_behavior(self):
        entry = make_nested_repo(self.repo, "other/embedded")
        before = inventory(self.root)
        with self.assertRaisesRegex(ValueError, "outside the editable scope"):
            backend.review_preflight(self.args("src/app.py"), self.state)
        plan = backend.review_preflight(self.args("src/app.py", unrelated="Preexisting outside work"), self.state)
        self.assertEqual(plan["unrelated"], {entry})
        self.assertEqual(plan["coverage"]["required"], set())
        self.assertEqual(before, inventory(self.root))

    def scoped_state(self, *scope):
        state = copy.deepcopy(self.state)
        state["spec"]["editable_scope"] = list(scope)
        return state

    def test_directory_shaped_entry_containing_scope_entry_is_scoped_and_refused(self):
        entry = make_nested_repo(self.repo, "vendor/lib")
        self.assertEqual(git(self.repo, "ls-files", "--others", "--exclude-standard", "-z").stdout,
                         (entry + "\0").encode())
        before = inventory(self.root)
        for inner in ("vendor/lib/source.txt", "vendor/lib/pending", "vendor/lib/pending/new.txt"):
            state = self.scoped_state("src/app.py", inner)
            coverage = backend.review_coverage(self.repo, state["spec"]["editable_scope"])
            self.assertIn(entry, coverage["required"])
            self.assertNotIn(entry, coverage["unscoped"])
            selections = [("src/app.py",), ("src/app.py", entry.rstrip("/"))]
            if os.path.isfile(self.repo / inner):
                selections.append(("src/app.py", inner))
            for paths in selections:
                for declaration in (None, "Declared unrelated cannot cover scoped work"):
                    with self.subTest(scope=inner, paths=paths, declaration=declaration), \
                            self.assertRaises(ValueError) as caught:
                        backend.review_preflight(self.args(*paths, unrelated=declaration), state)
                    self.assertIn("directory-shaped", str(caught.exception))
                    self.assertIn(json.dumps(entry), str(caught.exception))
        self.assertEqual(before, inventory(self.root))

    def test_containing_rule_leaves_prefix_names_and_ordinary_ancestor_files_unscoped(self):
        entry = make_nested_repo(self.repo, "vendor/lib")
        (self.repo / "other/pending").write_text("ordinary untracked file\n")
        state = self.scoped_state("src/app.py", "vendor/library/x.txt", "other/pending/child.txt")
        coverage = backend.review_coverage(self.repo, state["spec"]["editable_scope"])
        self.assertEqual(coverage["required"], set())
        self.assertEqual(coverage["unscoped"], {entry, "other/pending"})
        with self.assertRaisesRegex(ValueError, "outside the editable scope"):
            backend.review_preflight(self.args("src/app.py"), state)
        plan = backend.review_preflight(self.args("src/app.py", unrelated="Preexisting outside work"), state)
        self.assertEqual(plan["unrelated"], {entry, "other/pending"})

    def test_staged_gitlink_keeps_generic_refusals_and_is_not_admitted(self):
        make_nested_repo(self.repo)
        git(self.repo, "add", "tests/embedded")
        self.assertTrue(git(self.repo, "ls-files", "--stage", "tests/embedded").stdout.startswith(b"160000 "))
        coverage = backend.review_coverage(self.repo, SCOPE)
        self.assertEqual(coverage["required"], {"tests/embedded"})
        before = inventory(self.root)
        for declaration in (None, "Declared unrelated cannot cover scoped work"):
            with self.subTest(declaration=declaration):
                with self.assertRaisesRegex(ValueError, "omits task-scoped"):
                    backend.review_preflight(self.args("src/app.py", unrelated=declaration), self.state)
                with self.assertRaises((ValueError, OSError)):
                    backend.review_preflight(self.args("src/app.py", "tests/embedded", unrelated=declaration),
                                             self.state)
        self.assertEqual(before, inventory(self.root))

    def test_writer_context_bypasses_nested_repository_review_guard(self):
        make_nested_repo(self.repo)
        before = inventory(self.root)
        self.assertIsNone(backend.review_preflight(self.args("src/app.py", purpose="writer_context"), self.state))
        self.assertEqual(before, inventory(self.root))

    def test_staged_gitlink_above_directory_or_absent_scope_entry_needs_unrelated_declaration(self):
        nested = self.repo / "vendor/lib"
        make_nested_repo(self.repo, "vendor/lib")
        (nested / "pending").mkdir()
        git(self.repo, "add", "vendor/lib")
        self.assertTrue(git(self.repo, "ls-files", "--stage", "vendor/lib").stdout.startswith(b"160000 "))
        before = inventory(self.root)
        for entry in ("vendor/lib/pending", "vendor/lib/future"):
            with self.subTest(scope=entry):
                state = self.scoped_state("src/app.py", entry)
                coverage = backend.review_coverage(self.repo, state["spec"]["editable_scope"])
                self.assertEqual(coverage["required"], set())
                self.assertEqual(coverage["unscoped"], {"vendor/lib"})
                with self.assertRaisesRegex(ValueError, "outside the editable scope"):
                    backend.review_preflight(self.args("src/app.py"), state)
                plan = backend.review_preflight(
                    self.args("src/app.py", unrelated="Preexisting unrelated gitlink"), state)
                self.assertEqual(plan["unrelated"], {"vendor/lib"})
                self.assertEqual(plan["paths"], ["src/app.py"])
        self.assertEqual(before, inventory(self.root))

    def test_unsupported_scoped_sources_refuse_before_writes(self):
        cases = {
            "binary": lambda p: p.write_bytes(b"\x00\x01binary"),
            "non-utf8": lambda p: p.write_bytes(b"\xff\xfe not utf-8\n"),
            "symlink": lambda p: p.symlink_to(self.repo / "src/app.py"),
        }
        for label, make in cases.items():
            with self.subTest(kind=label):
                target = self.repo / "tests" / ("unsupported_" + label + ".py")
                make(target)
                before = inventory(self.root)
                with self.assertRaises((ValueError, OSError)):
                    backend.review_preflight(self.args(target.relative_to(self.repo).as_posix()), self.state)
                self.assertEqual(before, inventory(self.root))
                target.unlink()

    def test_directory_scoped_writer_content_under_staged_gitlink_is_not_enumerated(self):
        make_nested_repo(self.repo, "vendor/lib")
        pending = self.repo / "vendor/lib/pending"
        pending.mkdir()
        git(self.repo, "add", "vendor/lib")
        state = self.scoped_state("src/app.py", "vendor/lib/pending")
        before_coverage = backend.review_coverage(self.repo, state["spec"]["editable_scope"])
        (pending / "writer.txt").write_text("synthetic writer content beneath gitlink\n")
        after_coverage = backend.review_coverage(self.repo, state["spec"]["editable_scope"])
        self.assertEqual(before_coverage, after_coverage)
        self.assertEqual(after_coverage["required"], set())
        self.assertEqual(after_coverage["unscoped"], {"vendor/lib"})
        before = inventory(self.root)
        with self.assertRaisesRegex(ValueError, "outside the editable scope"):
            backend.review_preflight(self.args("src/app.py"), state)
        # Adversarial synthetic declaration demonstrates the attribution limit.
        plan = backend.review_preflight(
            self.args("src/app.py", unrelated="Synthetic incorrect declaration despite writer content"), state)
        self.assertEqual(plan["unrelated"], {"vendor/lib"})
        self.assertEqual(plan["paths"], ["src/app.py"])
        self.assertEqual(before, inventory(self.root))

    def test_ignored_paths_are_reported_not_attributed_except_exact_scope_entries(self):
        (self.repo / "tests/cache.log").write_text("ignored descendant\n")
        (self.repo / "build").mkdir()
        (self.repo / "build/out.txt").write_text("ignored exact scope input\n")
        scope = SCOPE + ["build/out.txt"]
        coverage = backend.review_coverage(self.repo, scope)
        self.assertNotIn("tests/cache.log", coverage["required"])
        self.assertIn("build/out.txt", coverage["required"])
        self.assertIn("tests/cache.log", coverage["ignored_in_scope"])
        self.assertIn("build", coverage["ignored_in_scope"])

    def test_clean_scope_reports_empty_change_set_without_refusal(self):
        coverage = backend.review_coverage(self.repo, SCOPE)
        self.assertEqual((coverage["changed"], coverage["required"]), (set(), set()))
        plan = backend.review_preflight(self.args("src/app.py"), self.state)
        self.assertEqual(plan["paths"], ["src/app.py"])

    def test_writer_context_is_unaffected_by_the_review_guard(self):
        self.change_every_kind()
        (self.repo / "other/notes.txt").write_text("outside change\n")
        (self.repo / "tests/test_old.py").unlink()
        # Scoped omissions, a deletion and outside dirt do not refuse writer context.
        self.assertIsNone(backend.review_preflight(self.args("src/app.py", purpose="writer_context"), self.state))
        with self.assertRaisesRegex(ValueError, "applies only to review"):
            backend.review_preflight(self.args("src/app.py", purpose="writer_context", unrelated="x"), self.state)


class StubEngineMainTests(CoverageFixture):
    """Through main(): refusals happen after one read-only `task show`, before any helper write."""

    def setUp(self):
        super().setUp()
        self.records = self.root / "records"
        self.records.mkdir()
        self.log = self.root / "engine-calls.log"
        response = self.show_response = self.root / "show.json"
        self.write_show(self.state)
        self.binary = self.root / "stub-engine"
        self.binary.write_text("#!/bin/sh\n"
                               f"printf '%s\\n' \"$*\" >> {shlex.quote(str(self.log))}\n"
                               f"if [ \"$1 $2\" = 'task show' ]; then cat {shlex.quote(str(response))}; exit 0; fi\n"
                               "exit 1\n")
        self.binary.chmod(0o700)
        self.config = self.root / "backend.json"
        self.config.write_text(json.dumps({"version": 1, "mode": "cli", "binary": str(self.binary)}))
        self.record = self.records / "fixture/review/collaboration"
        self.host = self.records / "fixture/review/host"
        self.instructions = self.root / "instructions.txt"
        self.instructions.write_text("Neutral review instructions.")

    def write_show(self, state):
        state = copy.deepcopy(state)
        state["profile"] = {"records_root": str(self.records)}
        self.show_response.write_text(json.dumps({"schema_version": 1, "ok": True,
                                                  "data": {"record": state, "revision": 2}}))

    def context(self, *paths, extra=()):
        argv = ["--config", str(self.config), "context", "--record", str(self.record), "--purpose", "review",
                "--omit-other-paths", "Clean unrelated inventory", "--quiescence", "Writer stopped",
                "--instructions", str(self.instructions), "--output", str(self.host / "review.txt"), *extra]
        for path in paths:
            argv += ["--paths", path]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = backend.main(argv)
        return code, out.getvalue(), err.getvalue()

    def assert_refused_before_writes(self, *paths, extra=(), expect):
        records_before = inventory(self.records)
        code, out, err = self.context(*paths, extra=extra)
        self.assertEqual((code, out), (1, ""))
        error = json.loads(err)
        self.assertIn("review coverage guard refused before freeze", error["error"])
        self.assertIn(expect, error["error"])
        self.assertEqual(error["fallback"], "none")
        self.assertNotIn("incomplete_workflow", error)
        self.assertFalse(self.host.exists())
        self.assertEqual(inventory(self.records), records_before)
        calls = self.log.read_text().splitlines()
        self.assertTrue(calls and all(line.startswith("task show") for line in calls), calls)
        self.log.unlink()

    def test_scoped_omission_deletion_and_outside_dirt_refuse_before_trace_record_or_output(self):
        changed = self.change_every_kind()
        self.assert_refused_before_writes("src/app.py", expect="omits task-scoped")
        (self.repo / "other/notes.txt").write_text("outside change\n")
        # A blanket --omit-other-paths reason is not an unrelated-change declaration.
        self.assert_refused_before_writes(*sorted(changed), expect="--unrelated-changes")
        (self.repo / "tests/test_old.py").unlink()
        self.assert_refused_before_writes(*sorted(changed), extra=("--unrelated-changes", "Preexisting"),
                                          expect="deleted or absent")

    def test_nested_repository_refuses_before_trace_record_or_output_with_stub_engine(self):
        entry = make_nested_repo(self.repo)
        for paths in (("src/app.py",), ("src/app.py", entry.rstrip("/"))):
            with self.subTest(paths=paths):
                self.assert_refused_before_writes(*paths, expect="unsupported directory-shaped task change(s)")

    def test_nested_repository_containing_scope_entry_refuses_before_writes_with_stub_engine(self):
        entry = make_nested_repo(self.repo, "vendor/lib")
        state = copy.deepcopy(self.state)
        state["spec"]["editable_scope"] = ["src/app.py", "vendor/lib/source.txt"]
        self.write_show(state)
        for paths in (("src/app.py", "vendor/lib/source.txt"), ("src/app.py", entry.rstrip("/"))):
            with self.subTest(paths=paths):
                self.assert_refused_before_writes(*paths, extra=("--unrelated-changes", "Cannot cover scoped work"),
                                                  expect=json.dumps(entry))

    def test_shared_options_after_command_keep_new_flag_values(self):
        args = backend.parser().parse_args([
            "context", "--record", "/synthetic/record", "--purpose", "review", "--paths", "a",
            "--quiescence", "q", "--instructions", "/synthetic/i", "--output", "/synthetic/o",
            "--unrelated-changes=--profile", "--profile", "/synthetic/profile.json", "--actor", "lead"])
        self.assertEqual(args.unrelated_changes, "--profile")
        self.assertEqual(args.profile, "/synthetic/profile.json")

    def test_shared_sentinel_still_refuses_context_before_engine_activity(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err, \
                self.assertRaises(SystemExit) as result:
            backend.main(["--config", str(self.config), "context", "--record", str(self.record),
                          "--purpose", "review", "--paths", "src/app.py", "--quiescence", "q",
                          "--instructions", str(self.instructions), "--output", str(self.host / "o.txt"),
                          "--unrelated-changes", "x", "--actor=--"])
        self.assertEqual(result.exception.code, 2)
        self.assertIn("exact '--' sentinel", err.getvalue())
        self.assertFalse(self.log.exists())
        self.assertFalse(self.host.exists())


class FakeEngine(backend.Backend):
    """Content-addressed stub of freeze/seal; optional drift after the engine capture."""

    def __init__(self, root, repo, drift=None, drop=None):
        self.record = root / "record"
        (self.record / "objects").mkdir(parents=True)
        self.host = root / "host"
        self.host.mkdir()
        self.repo, self.drift, self.drop, self.calls = repo, drift, drop, []
        self.workflow = None

    def store(self, raw):
        key = safe.digest(raw)
        (self.record / "objects" / key).write_bytes(raw)
        return key

    def mutation(self, entity, action, value=None, raw=None, create=False):
        self.calls.append((entity + " " + action, value))
        if (entity, action) == ("artifact", "freeze"):
            entries = [{"path": p, "kind": "file", "object": self.store((self.repo / p).read_bytes())}
                       for p in value["paths"] if p != self.drop]
            artifact = self.store(backend.encoded({"entries": entries}))
            if self.drift:
                self.drift()
            return {"result": {"artifact": artifact}}
        if (entity, action) == ("packet", "seal"):
            return {"result": {"packet": self.store(backend.encoded({"packet": value}))}}
        raise AssertionError("unexpected stub mutation " + entity + " " + action)


class FreezeDriftTests(CoverageFixture):
    def run_context(self, engine, *paths, purpose="review", unrelated=None):
        instructions = self.root / "instructions.txt"
        instructions.write_text("Neutral instructions")
        args = argparse.Namespace(purpose=purpose, paths=list(paths), unrelated_changes=unrelated,
                                  omit_other_paths="Clean unrelated inventory", quiescence="Writer stopped",
                                  instructions=str(instructions), round=0, output=str(engine.host / "ctx.txt"))
        return backend.context(engine, args, self.state)

    def test_matching_freeze_seals_and_records_declared_unrelated_per_path(self):
        changed = self.change_every_kind()
        (self.repo / "other/notes.txt").write_text("outside change\n")
        engine = FakeEngine(self.root / "engine", self.repo)
        value = self.run_context(engine, *sorted(changed), unrelated="Preexisting owner work")
        self.assertEqual([c for c, _ in engine.calls], ["artifact freeze", "packet seal"])
        omissions = engine.calls[0][1]["omissions"]
        self.assertTrue(omissions["other/notes.txt"].startswith("Declared unrelated change outside editable scope"))
        self.assertIn("Preexisting owner work", omissions["other/notes.txt"])
        self.assertEqual(omissions["tests/test_old.py"], "Clean unrelated inventory")
        self.assertEqual(value["coverage"]["task_changes_selected"], sorted(changed))
        self.assertEqual(value["coverage"]["declared_unrelated_changes"], ["other/notes.txt"])
        self.assertTrue((engine.host / "ctx.txt").exists())

    def assert_no_seal(self, engine, *paths, expect):
        with self.assertRaisesRegex(ValueError, expect):
            self.run_context(engine, *paths)
        self.assertEqual([c for c, _ in engine.calls], ["artifact freeze"])
        self.assertFalse((engine.host / "ctx.txt").exists())

    def test_live_byte_drift_after_freeze_refuses_seal(self):
        changed = self.change_every_kind()
        engine = FakeEngine(self.root / "engine", self.repo,
                            drift=lambda: (self.repo / "docs/guide.md").write_text("# Guide\ndrifted\n"))
        self.assert_no_seal(engine, *sorted(changed), expect="does not match selected live source")

    def test_new_scoped_change_after_freeze_refuses_seal(self):
        changed = self.change_every_kind()
        engine = FakeEngine(self.root / "engine", self.repo,
                            drift=lambda: (self.repo / "tests/test_late.py").write_text("late\n"))
        self.assert_no_seal(engine, *sorted(changed), expect="source changed during review freeze")

    def test_nested_repository_appearing_over_scope_entry_after_freeze_refuses_seal(self):
        self.state["spec"]["editable_scope"] = SCOPE + ["vendor/lib/pending"]
        (self.repo / "src/app.py").write_text("print('task change')\n")
        engine = FakeEngine(self.root / "engine", self.repo,
                            drift=lambda: make_nested_repo(self.repo, "vendor/lib"))
        self.assert_no_seal(engine, "src/app.py", expect="source changed during review freeze")

    def test_manifest_missing_selected_entry_refuses_seal(self):
        changed = self.change_every_kind()
        engine = FakeEngine(self.root / "engine", self.repo, drop="tests/test_new.py")
        self.assert_no_seal(engine, *sorted(changed), expect="does not match selected live source")

    def test_writer_context_is_not_drift_checked(self):
        engine = FakeEngine(self.root / "engine", self.repo,
                            drift=lambda: (self.repo / "src/app.py").write_text("print('drift')\n"))
        value = self.run_context(engine, "src/app.py", purpose="writer_context")
        self.assertEqual([c for c, _ in engine.calls], ["artifact freeze", "packet seal"])
        self.assertNotIn("coverage", value)


class DispatchFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "objects").mkdir()
        self.engine = backend.Backend.__new__(backend.Backend)
        self.engine.record = self.root
        self.engine.call = lambda entity, action: {"integrity": "verified"}

    def store(self, value):
        raw = backend.encoded(value) if isinstance(value, dict) else value
        key = safe.digest(raw)
        (self.root / "objects" / key).write_bytes(raw)
        return key

    def state(self, role="reviewer", ids=("job-1",), destination="result.json", model="synthetic"):
        source = self.store(b"frozen synthetic source\n")
        artifact = self.store({"entries": [{"path": "source.txt", "kind": "file", "object": source}]})
        packet = {"purpose": "review" if role == "reviewer" else "writer_context", "artifact": artifact,
                  "instructions": "Return a JSON file plus a concise prose summary."}
        packet_id = self.store({"packet": packet})
        assignments = [{"spec": {"id": name, "packet": packet_id, "role": role,
                                 "output_destination": str(self.root / destination)},
                        "state": "launching", "observations": [{"receipt": {"invocation": None}}],
                        "requested": {"transport": "codex-native", "model": model, "reasoning": "medium"}}
                       for name in ids]
        return {"state": "active", "current_artifact": artifact,
                "packets": [{"id": packet_id, "spec": packet}], "assignments": assignments}

    def dispatch(self, state, assignment="job-1"):
        return backend.native_dispatch(self.engine, argparse.Namespace(assignment=assignment), state)


class NativeTaskNameTests(DispatchFixture):
    def test_task_name_is_deterministic_and_bound_to_all_three_identities(self):
        a, p, r = "review-1", "a" * 64, "b" * 64
        name = backend.native_task_name(a, p, r)
        self.assertRegex(name, HEX)
        self.assertEqual(name, backend.native_task_name(a, p, r))
        variants = {backend.native_task_name("review-2", p, r), backend.native_task_name(a, "c" * 64, r),
                    backend.native_task_name(a, p, "c" * 64), backend.native_task_name(a, r, p)}
        self.assertNotIn(name, variants)
        self.assertEqual(len(variants), 4)

    def test_delimiter_like_assignment_text_cannot_collide(self):
        p, r = "a" * 64, "b" * 64
        names = {backend.native_task_name(x, p, r) for x in
                 ("job", "job,", 'job","' + p, "job\n", "jöb", "job" + p)}
        self.assertEqual(len(names), 6)

    def test_adverse_identities_are_refused(self):
        good = "a" * 64
        for assignment, packet, artifact in (("", good, good), ("x" * 513, good, good), (None, good, good),
                                             (7, good, good), ("job", "A" * 64, good), ("job", good, "a" * 63),
                                             ("job", good, "a" * 65), ("job", "g" * 64, good),
                                             ("job", good.encode(), good), ("job", None, good)):
            with self.subTest(assignment=assignment, packet=packet, artifact=artifact):
                with self.assertRaisesRegex(ValueError, "invalid native binding identity"):
                    backend.native_task_name(assignment, packet, artifact)

    def test_dispatch_header_carries_exact_task_name_and_keeps_identity_lines(self):
        state = self.state()
        result = self.dispatch(state)
        lines = result["message"].split("\n")
        self.assertEqual(lines[:4], ["Agents Collab native dispatch v1", "Assignment: job-1",
                                     "Packet-SHA256: " + result["packet"],
                                     "Artifact-SHA256: " + result["artifact"]])
        self.assertEqual(lines[4], "Native-Task-Name: " + result["task_name"])
        self.assertEqual(result["task_name"],
                         backend.native_task_name("job-1", result["packet"], result["artifact"]))
        self.assertNotEqual(result["task_name"], result["message_sha256"])
        self.assertIn("task_name exactly", result["limits"])

    def test_task_name_ignores_destination_and_controls_but_not_assignment(self):
        first = self.dispatch(self.state(destination="a.json", model="m1"))
        second = self.dispatch(self.state(destination="b.json", model="m2"))
        self.assertEqual(first["task_name"], second["task_name"])
        self.assertNotEqual(first["message_sha256"], second["message_sha256"])
        pair = self.state(ids=("job-1", "job-2"))
        names = {self.dispatch(pair, name)["task_name"] for name in ("job-1", "job-2")}
        self.assertEqual(len(names), 2)

    def test_refused_dispatch_yields_no_task_name_and_no_writes(self):
        state = self.state()
        state["assignments"][0]["observations"].append({"receipt": {"invocation": "already-started"}})
        before = inventory(self.root)
        with self.assertRaises(ValueError):
            self.dispatch(state)
        self.assertEqual(before, inventory(self.root))


class FinalOutputContractTests(DispatchFixture):
    @staticmethod
    def contract_segment(message):
        header, rest = message.split("\n\n", 1)
        return rest.split("# Frozen collaboration context", 1)[0]

    def test_reviewer_contract_has_exact_schema_fields_and_registered_identities(self):
        result = self.dispatch(self.state())
        schema = documented_review_schema()
        template = result["final_output"]["template"]
        self.assertEqual(result["role"], "reviewer")
        self.assertEqual(set(template), set(schema))
        self.assertEqual(len(template), len(schema))
        self.assertEqual((template["assignment"], template["packet"], template["artifact"]),
                         ("job-1", result["packet"], result["artifact"]))
        self.assertEqual(template["schema_version"], schema["schema_version"])
        self.assertEqual(template["verification"][0]["object"], result["artifact"])
        self.assertEqual(set(template["verification"][0]), set(schema["verification"][0]))
        for key in ("limits", "fresh_session", "automatic_context", "tool_boundary"):
            self.assertIsInstance(template[key], str)
        self.assertEqual(template["findings"], [])

    def test_reviewer_message_embeds_the_same_template_before_the_frozen_context(self):
        result = self.dispatch(self.state())
        segment = self.contract_segment(result["message"])
        embedded, _ = json.JSONDecoder().raw_decode(segment[segment.index("{"):])
        self.assertEqual(embedded, result["final_output"]["template"])
        self.assertIn(result["final_output"]["contract"], segment)
        self.assertIn("final message", segment)
        self.assertIn("supersedes", segment)
        # The conflicting packet instruction remains in the frozen context; the contract precedes it.
        message = result["message"]
        self.assertLess(message.index(result["final_output"]["contract"]), message.index("concise prose summary"))

    def test_filled_template_matches_documented_types(self):
        template = self.dispatch(self.state())["final_output"]["template"]
        filled = json.loads(json.dumps(template).replace("REPLACE: pass, changes_required or blocked", "pass"))
        filled = json.loads(re.sub(r'"REPLACE: [^"]*"', '"Synthetic observation"', json.dumps(filled)))
        self.assertNotIn("REPLACE", json.dumps(filled))
        self.assertIn(filled["verdict"], ("pass", "changes_required", "blocked"))
        schema = documented_review_schema()
        self.assertEqual({k: type(v) for k, v in filled.items()}, {k: type(v) for k, v in schema.items()})

    def test_writer_gets_report_contract_never_reviewer_json(self):
        result = self.dispatch(self.state(role="writer"))
        self.assertEqual(result["role"], "writer")
        self.assertIsNone(result["final_output"]["template"])
        self.assertNotEqual(result["final_output"]["contract"], backend.REVIEWER_CONTRACT)
        segment = self.contract_segment(result["message"])
        self.assertNotIn("{", segment)
        self.assertNotIn("schema_version", segment)
        for phrase in ("changed", "deleted file", "tests", "skipped"):
            self.assertIn(phrase, segment)

    def test_contracts_claim_no_delivery_or_launch(self):
        for role in ("reviewer", "writer"):
            with self.subTest(role=role):
                result = self.dispatch(self.state(role=role))
                self.assertEqual((result["dispatch"], result["writes"]), ("none", False))
                self.assertIn("not permission", result["limits"])
                self.assertIn("delivery evidence", result["limits"])
                self.assertNotRegex(result["message"].lower(), r"\bwas delivered\b|\bdelivery confirmed\b")


@unittest.skipUnless(os.environ.get("AGENTS_COLLAB_TEST_BINARY"), "set explicit real CLI for offline engine tests")
class RealEngineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = make_repo(self.root, {"source.txt": "original source\n", "other.txt": "outside scope\n",
                                          "tests/test_old.py": "# old\n"})
        (self.root / "records").mkdir()
        self.config = self.root / "backend.json"
        self.config.write_text(json.dumps({"version": 1, "mode": "cli",
                                           "binary": str(Path(os.environ["AGENTS_COLLAB_TEST_BINARY"]).resolve())}))
        profile = json.loads((SCRIPTS.parent / "examples/profile.example.json").read_text())
        profile["records_root"] = str(self.root / "records")
        profile["agents"].update({name: {"model": "synthetic-native", "transport": "codex-native",
                                         "reasoning": "medium"} for name in ("writer", "reviewer")})
        profile["review"]["candidates"] = ["reviewer"]
        self.profile = self.root / "profile.json"
        self.profile.write_text(json.dumps(profile))

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = backend.main(["--config", str(self.config), "--profile", str(self.profile), *args])
        return code, out.getvalue(), err.getvalue()

    def ok(self, *args):
        code, out, err = self.invoke(*args)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def start(self, task, extra_scope=()):
        scope_args = [part for path in extra_scope for part in ("--scope", path)]
        started = self.ok("start", "--repository", str(self.repo), "--project", "fixture", "--task", task,
                          "--writer", "writer", "--reviewer", "reviewer", "--scope", "source.txt",
                          "--scope", "tests", "--requirement", "R1=Synthetic scope", "--criterion", "C1=Check",
                          "--boundary", "No model invocation", "--check", "offline", *scope_args)
        instructions = Path(started["host"]) / "instructions.txt"
        instructions.write_text("Synthetic neutral review instructions; no model is called.")
        return started["record"], Path(started["host"]), instructions

    def review_context(self, record, host, instructions, *paths, extra=()):
        argv = ["context", "--record", record, "--purpose", "review", "--omit-other-paths", "Clean inventory",
                "--quiescence", "Synthetic writer stopped", "--instructions", str(instructions),
                "--output", str(host / "review.txt"), *extra]
        for path in paths:
            argv += ["--paths", path]
        return self.invoke(*argv)

    def test_real_review_guard_refuses_before_writes_then_freezes_complete_change(self):
        record, host, instructions = self.start("coverage")
        (self.repo / "source.txt").write_text("changed source\n")
        (self.repo / "tests/test_new.py").write_text("# writer added test\n")
        (self.repo / "other.txt").write_text("preexisting outside edit\n")
        refusals = ((("source.txt",), (), "omits task-scoped"),
                    (("source.txt", "tests/test_new.py"), (), "--unrelated-changes"))
        for paths, extra, expect in refusals:
            with self.subTest(paths=paths):
                before = inventory(self.root)
                code, out, err = self.review_context(record, host, instructions, *paths, extra=extra)
                self.assertEqual((code, out), (1, ""))
                self.assertIn(expect, json.loads(err)["error"])
                self.assertNotIn("incomplete_workflow", json.loads(err))
                self.assertEqual(before, inventory(self.root))
        (self.repo / "tests/test_old.py").unlink()
        before = inventory(self.root)
        code, _, err = self.review_context(record, host, instructions, "source.txt", "tests/test_new.py",
                                           extra=("--unrelated-changes", "Preexisting"))
        self.assertIn("deleted or absent", json.loads(err)["error"])
        self.assertEqual(before, inventory(self.root))
        git(self.repo, "checkout", "--", "tests/test_old.py")

        value = self.ok("context", "--record", record, "--purpose", "review", "--paths", "source.txt",
                        "--paths", "tests/test_new.py", "--omit-other-paths", "Clean inventory",
                        "--unrelated-changes", "Preexisting synthetic edit", "--quiescence", "Synthetic writer stopped",
                        "--instructions", str(instructions), "--output", str(host / "review.txt"))
        self.assertEqual(value["coverage"]["task_changes_selected"], ["source.txt", "tests/test_new.py"])
        self.assertEqual(value["coverage"]["declared_unrelated_changes"], ["other.txt"])
        rendered = (host / "review.txt").read_text()
        self.assertIn("# writer added test", rendered)
        self.assertNotIn("preexisting outside edit", rendered)
        workflow = json.loads(Path(value["workflow"]).read_text())
        freeze = json.loads((Path(workflow["steps"][0]["trace"]) / "input.json").read_text())
        self.assertTrue(freeze["omissions"]["other.txt"].startswith("Declared unrelated change"))
        self.assertEqual(freeze["omissions"]["tests/test_old.py"], "Clean inventory")

    def test_real_reviewer_template_imports_as_valid_terminal_result(self):
        record, host, instructions = self.start("final")
        context = self.ok("context", "--record", record, "--purpose", "review", "--paths", "source.txt",
                          "--omit-other-paths", "Clean inventory", "--quiescence", "Synthetic",
                          "--instructions", str(instructions), "--output", str(host / "review.txt"))
        self.ok("assignment", "--record", record, "--id", "review-1", "--packet", context["packet"],
                "--agent", "reviewer", "--role", "reviewer", "--output-destination", str(host / "review-1.json"))
        first = self.ok("native-dispatch", "--record", record, "--assignment", "review-1")
        again = self.ok("native-dispatch", "--record", record, "--assignment", "review-1")
        self.assertEqual(first["task_name"], again["task_name"])
        self.assertEqual(first["task_name"], backend.native_task_name("review-1", context["packet"], context["artifact"]))
        template = first["final_output"]["template"]
        filled = json.loads(re.sub(r'"REPLACE: pass, changes_required or blocked"', '"pass"', json.dumps(template)))
        filled = json.loads(re.sub(r'"REPLACE: [^"]*"', '"Synthetic stub; no model ran"', json.dumps(filled)))
        self.ok("observe", "--record", record, "--assignment", "review-1", "--state", "completed",
                "--invocation", "synthetic-terminal", "--boundary-observations", "Synthetic; no worker launched")
        (host / "review-1.json").write_text(json.dumps(filled))
        result = self.ok("import-review", "--record", record, "--input", str(host / "review-1.json"))
        self.assertTrue(result["valid_review"])

    def test_real_nested_repository_refuses_before_trace_record_or_output(self):
        record, host, instructions = self.start("nested")
        entry = make_nested_repo(self.repo)
        self.assertEqual(git(self.repo, "ls-files", "--others", "--exclude-standard", "-z").stdout,
                         (entry + "\0").encode())
        for paths in (("source.txt",), ("source.txt", entry.rstrip("/"))):
            with self.subTest(paths=paths):
                before = inventory(self.root)
                code, out, err = self.review_context(record, host, instructions, *paths)
                self.assertEqual((code, out), (1, ""))
                error = json.loads(err)
                self.assertIn("unsupported directory-shaped task change(s)", error["error"])
                self.assertIn(json.dumps(entry), error["error"])
                self.assertIn("Nothing was frozen, sealed or written", error["error"])
                self.assertNotIn("incomplete_workflow", error)
                self.assertFalse((host / "review.txt").exists())
                self.assertEqual(before, inventory(self.root))

    def context_argv(self, record, host, instructions, purpose, output, extra=()):
        return ["context", "--record", record, "--purpose", purpose, "--paths", "source.txt",
                "--omit-other-paths", "Clean inventory", "--quiescence", "Synthetic writer stopped",
                "--instructions", str(instructions), "--output", str(host / output), *extra]

    def test_explicit_route_binds_one_writer_to_one_final_review(self):
        ticket = "Update source.txt to say Relay accepts one destination."
        expected = "Relay accepts one destination.\n"
        args = ("--repository", str(self.repo), "--project", "fixture", "--task", "relay",
                "--writer", "writer", "--reviewer", "reviewer", "--scope", "source.txt",
                "--criterion", "C1=" + ticket, "--boundary", "Synthetic offline fixture", "--check", "exact-text")
        solo_root = self.root / "solo"
        solo_root.mkdir()
        solo = make_repo(solo_root, {"source.txt": (self.repo / "source.txt").read_text(encoding="utf-8")})
        self.assertEqual(self.ok("route", "--repository", str(solo), *args[2:])["route"], "solo")
        (solo / "source.txt").write_text(expected, encoding="utf-8")
        self.assertEqual((solo / "source.txt").read_text(encoding="utf-8"), expected)
        self.assertEqual(list((self.root / "records").iterdir()), [])

        value = self.ok("route", "--review-required", *args)
        self.assertEqual(value["route"], "review")
        record, host = value["record"], Path(value["host"])
        instructions = host / "instructions.txt"
        instructions.write_text(ticket, encoding="utf-8")
        code, _, err = self.invoke(*self.context_argv(record, host, instructions, "review", "too-early.txt"))
        self.assertEqual(code, 1)
        self.assertIn("one completed writer", err)
        self.assertFalse((host / "too-early.txt").exists())

        writer = self.ok(*self.context_argv(record, host, instructions, "writer_context", "writer-context.txt"))
        self.ok("assignment", "--record", record, "--id", "write-1", "--packet", writer["packet"],
                "--agent", "writer", "--role", "writer", "--output-destination", str(host / "write-1.txt"))
        (self.repo / "source.txt").write_text(expected, encoding="utf-8")
        self.ok("observe", "--record", record, "--assignment", "write-1", "--state", "completed",
                "--invocation", "relay-writer", "--boundary-observations", "Synthetic recorded writer identity")
        final = self.ok(*self.context_argv(record, host, instructions, "review", "review-context.txt"))
        sealed = self.ok("packet", "--record", record, "--packet", final["packet"])
        state = self.ok("show", "--record", record)
        self.assertEqual(state["record"]["schema_version"], 6)
        self.assertEqual(state["effective_review_limit"], 0)
        binding = sealed["writer_binding"]
        self.assertEqual(binding["writer_assignment"], "write-1")
        self.assertEqual(binding["writer_invocation"], "relay-writer")
        self.assertEqual(binding["artifact"], final["artifact"])
        self.assertEqual(binding["writer_receipt"], state["record"]["assignments"][0]["observations"][-1]["raw"])
        self.assertEqual(state["record"]["events"][binding["capture_revision"] - 1]["command"], "artifact freeze")
        self.assertNotEqual(writer["artifact"], final["artifact"])

        code, _, err = self.invoke("complete", "--record", record, "--evidence", final["artifact"], "--reason", "too early")
        self.assertEqual(code, 1)
        self.assertIn("required reviewers have not completed", err)
        terminal = host / "review-1.json"
        self.ok("assignment", "--record", record, "--id", "review-1", "--packet", final["packet"],
                "--agent", "reviewer", "--role", "reviewer", "--output-destination", str(terminal))
        options = ("observe", "--record", record, "--assignment", "review-1", "--state", "completed",
                   "--boundary-observations", "Synthetic recorded reviewer identity")
        code, _, err = self.invoke(*options, "--invocation", "relay-writer")
        self.assertEqual(code, 1)
        self.assertIn("stable, distinct writer and reviewer", err)
        dispatch = self.ok("native-dispatch", "--record", record, "--assignment", "review-1")
        self.assertIn('"writer_invocation": "relay-writer"', dispatch["message"])
        self.ok(*options, "--invocation", "relay-reviewer")

        passing = dispatch["final_output"]["template"]
        passing.update(verdict="pass", limits="Synthetic exact text comparison", fresh_session="Synthetic",
                       automatic_context="Synthetic", tool_boundary="Synthetic")
        passing["verification"][0]["description"] = "Fixture output matched the ticket."
        terminal.write_text(json.dumps(passing), encoding="utf-8")
        self.assertTrue(self.ok("import-review", "--record", record, "--input", str(terminal))["valid_review"])
        self.assertEqual((self.repo / "source.txt").read_text(encoding="utf-8"), expected)
        self.ok("complete", "--record", record, "--evidence", final["artifact"], "--reason", "Fixture passed")
        checked = self.ok("check", "--record", record)
        self.assertEqual((checked["state"], checked["integrity"], checked["completion_blockers"]),
                         ("completed", "verified", []))
        self.assertEqual(len(self.ok("show", "--record", record)["record"]["reviews"]), 1)

    def test_opted_in_freeze_must_follow_completed_writer_even_for_identical_source(self):
        route = self.ok("route", "--review-required", "--repository", str(self.repo), "--project", "fixture",
                        "--task", "already-correct", "--writer", "writer", "--reviewer", "reviewer",
                        "--scope", "source.txt", "--criterion", "C1=Confirm exact source",
                        "--boundary", "Synthetic offline fixture")
        record, host = route["record"], Path(route["host"])
        instructions = host / "instructions.txt"
        instructions.write_text("Confirm the already-correct source.", encoding="utf-8")
        writer = self.ok(*self.context_argv(record, host, instructions, "writer_context", "writer-context.txt"))
        self.ok("assignment", "--record", record, "--id", "writer", "--packet", writer["packet"],
                "--agent", "writer", "--role", "writer", "--output-destination", str(host / "writer.txt"))
        observe = ("observe", "--record", record, "--assignment", "writer", "--invocation", "same-writer",
                   "--boundary-observations", "Synthetic invocation")
        self.ok(*observe, "--state", "interrupted")

        def mutate(entity, action, payload):
            revision = self.ok("show", "--record", record)["revision"]
            path = host / f"probe-{entity}-{action}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [os.environ["AGENTS_COLLAB_TEST_BINARY"], entity, action, "--record", record, "--input", str(path),
                 "--actor", "lead", "--expect", str(revision), "--key", f"test-{entity}-{action}", "--json"],
                capture_output=True, text=True, check=False, env=fixture_git_env(),
            )

        failed = mutate("artifact", "freeze", {"paths": ["source.txt"],
                        "omissions": {"other.txt": "Clean inventory", "tests/test_old.py": "Clean inventory"},
                        "acknowledged_sensitive": [], "quiescence": "Already interrupted",
                        "atomic_required": False, "base": "HEAD"})
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("one completed writer", failed.stdout)
        self.ok(*observe, "--state", "completed", "--reconciled", "--reason", "Same synthetic invocation reconciled")
        writer_completed_revision = self.ok("show", "--record", record)["revision"]
        failed = mutate("packet", "seal", {"purpose": "review", "artifact": writer["artifact"], "round": 0,
                        "instructions": "Review unchanged source", "access_policy": "Read only",
                        "coverage": {"C1": [writer["artifact"]]}, "evidence": [], "neutral_initial": True})
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("capture after writer completion", failed.stdout)

        final = self.ok(*self.context_argv(record, host, instructions, "review", "review-context.txt"))
        self.assertEqual(final["artifact"], writer["artifact"])
        binding = self.ok("packet", "--record", record, "--packet", final["packet"])["writer_binding"]
        self.assertGreater(binding["capture_revision"], writer_completed_revision)
        self.assertEqual(binding["artifact"], writer["artifact"])

    def engine_freeze_refusal(self, record, host, argv, output):
        """Observed outcome when helper preflight passes but the engine refuses the freeze."""
        revision = self.ok("show", "--record", record)["revision"]
        code, out, err = self.invoke(*argv)
        self.assertEqual((code, out), (1, ""))
        # After preflight: the helper wrote its workflow and freeze-operation trace.
        workflow_path = Path(json.loads(err)["incomplete_workflow"])
        self.assertEqual(workflow_path.parent, host)
        workflow = json.loads(workflow_path.read_text())
        self.assertEqual(workflow["status"], "incomplete")
        self.assertEqual([(s["command"], s["status"]) for s in workflow["steps"]],
                         [("artifact freeze", "incomplete")])
        trace = Path(workflow["steps"][0]["trace"])
        self.assertFalse(json.loads((trace / "stdout").read_text())["ok"])
        # The engine committed nothing: no artifact, no packet seal, no rendered output.
        shown = self.ok("show", "--record", record)
        self.assertEqual(shown["revision"], revision)
        self.assertEqual((shown["record"]["artifacts"], shown["record"]["packets"]), ([], []))
        self.assertIsNone(shown["record"]["current_artifact"])
        self.assertFalse((host / output).exists())
        return json.loads((trace / "input.json").read_text())["omissions"]

    def test_real_outside_scope_nested_repository_declared_unrelated_is_refused_by_engine_freeze(self):
        record, host, instructions = self.start("nested-outside")
        entry = make_nested_repo(self.repo, "other/embedded")
        declare = ("--unrelated-changes", "Preexisting outside work")
        omissions = self.engine_freeze_refusal(
            record, host, self.context_argv(record, host, instructions, "review", "review.txt", declare), "review.txt")
        # The exact Git entry reached the engine as a declared omission; it was not filtered or normalized.
        self.assertTrue(omissions[entry].startswith("Declared unrelated change outside editable scope"))
        self.assertNotIn(entry.rstrip("/"), omissions)
        # Control: without the nested repository the same request freezes and seals.
        shutil.rmtree(self.repo / "other/embedded")
        value = self.ok(*self.context_argv(record, host, instructions, "review", "control.txt", declare))
        self.assertEqual(value["coverage"]["declared_unrelated_changes"], [])
        self.assertTrue((host / "control.txt").exists())

    def test_real_writer_context_with_nested_repository_is_refused_by_engine_freeze(self):
        record, host, instructions = self.start("nested-writer")
        entry = make_nested_repo(self.repo)
        omissions = self.engine_freeze_refusal(
            record, host, self.context_argv(record, host, instructions, "writer_context", "write.txt"), "write.txt")
        self.assertEqual(omissions[entry], "Clean inventory")
        self.assertNotIn(entry.rstrip("/"), omissions)
        shutil.rmtree(self.repo / "tests/embedded")
        value = self.ok(*self.context_argv(record, host, instructions, "writer_context", "control.txt"))
        self.assertNotIn("coverage", value)
        self.assertTrue((host / "control.txt").exists())

    def frozen_manifest(self, record, artifact):
        raw = (Path(record) / "objects" / artifact).read_bytes()
        self.assertEqual(safe.digest(raw), artifact)
        return {entry["path"]: entry for entry in json.loads(raw)["entries"]}

    def test_real_staged_gitlink_above_directory_or_absent_scope_is_omitted_not_reviewed(self):
        make_nested_repo(self.repo, "vendor/lib")
        (self.repo / "vendor/lib/pending").mkdir()
        git(self.repo, "add", "vendor/lib")
        for label, entry in (("directory", "vendor/lib/pending"), ("absent", "vendor/lib/future")):
            with self.subTest(scope=entry):
                record, host, instructions = self.start("gitlink-" + label, extra_scope=(entry,))
                before = inventory(self.root)
                code, out, err = self.review_context(record, host, instructions, "source.txt")
                self.assertEqual((code, out), (1, ""))
                self.assertIn("outside the editable scope", json.loads(err)["error"])
                self.assertNotIn("incomplete_workflow", json.loads(err))
                self.assertEqual(before, inventory(self.root))

                code, out, err = self.review_context(
                    record, host, instructions, "source.txt",
                    extra=("--unrelated-changes", "Preexisting unrelated gitlink"))
                self.assertEqual(code, 0, err)
                value = json.loads(out)
                self.assertEqual(value["coverage"]["declared_unrelated_changes"], ["vendor/lib"])
                self.assertEqual(value["coverage"]["task_changes_selected"], [])
                manifest = json.loads((Path(record) / "objects" / value["artifact"]).read_text())
                self.assertEqual([item["path"] for item in manifest["entries"]], ["source.txt"])
                self.assertEqual(manifest["omissions"]["vendor/lib"],
                                 "Declared unrelated change outside editable scope: Preexisting unrelated gitlink")
                shown = self.ok("show", "--record", record)["record"]
                self.assertEqual(len(shown["artifacts"]), 1)
                self.assertEqual(len(shown["packets"]), 1)
                workflow = json.loads(Path(value["workflow"]).read_text())
                self.assertEqual([(step["command"], step["status"]) for step in workflow["steps"]],
                                 [("artifact freeze", "committed"), ("packet seal", "committed")])
                self.assertTrue((host / "review.txt").exists())

                rendered = (host / "review.txt").read_text()
                self.assertIn("original source", rendered)
                self.assertNotIn("synthetic nested source", rendered)

    def test_real_directory_scoped_writer_content_under_gitlink_is_omitted_by_incorrect_declaration(self):
        make_nested_repo(self.repo, "vendor/lib")
        pending = self.repo / "vendor/lib/pending"
        pending.mkdir()
        git(self.repo, "add", "vendor/lib")
        record, host, instructions = self.start("gitlink-hidden", extra_scope=("vendor/lib/pending",))
        scope = self.ok("show", "--record", record)["record"]["spec"]["editable_scope"]
        before_coverage = backend.review_coverage(self.repo, scope)
        sentinel = "SYNTHETIC_WRITER_CONTENT_UNDER_GITLINK"
        (pending / "writer.txt").write_text(sentinel + "\n")
        self.assertEqual(backend.review_coverage(self.repo, scope), before_coverage)
        before = inventory(self.root)
        code, out, err = self.review_context(record, host, instructions, "source.txt")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("outside the editable scope", json.loads(err)["error"])
        self.assertNotIn("incomplete_workflow", json.loads(err))
        self.assertEqual(before, inventory(self.root))
        # Adversarial synthetic input: the real workflow forbids this declaration.
        reason = "Synthetic incorrect declaration despite writer content"
        code, out, err = self.review_context(record, host, instructions, "source.txt",
                                           extra=("--unrelated-changes", reason))
        self.assertEqual(code, 0, err)
        value = json.loads(out)
        self.assertEqual(value["coverage"]["task_changes_selected"], [])
        self.assertEqual(value["coverage"]["declared_unrelated_changes"], ["vendor/lib"])
        manifest = json.loads((Path(record) / "objects" / value["artifact"]).read_text())
        self.assertEqual([item["path"] for item in manifest["entries"]], ["source.txt"])
        self.assertEqual(manifest["omissions"]["vendor/lib"],
                         "Declared unrelated change outside editable scope: " + reason)
        rendered = (host / "review.txt").read_text()
        self.assertIn("original source", rendered)
        self.assertNotIn(sentinel, rendered)
        self.assertNotIn("synthetic nested source", rendered)
        workflow = json.loads(Path(value["workflow"]).read_text())
        self.assertEqual([(step["command"], step["status"]) for step in workflow["steps"]],
                         [("artifact freeze", "committed"), ("packet seal", "committed")])

    def test_real_exact_scoped_regular_file_under_gitlink_requires_selection_then_engine_refuses(self):
        make_nested_repo(self.repo, "vendor/lib")
        git(self.repo, "add", "vendor/lib")
        inner = "vendor/lib/source.txt"
        record, host, instructions = self.start("gitlink-exact", extra_scope=(inner,))
        declaration = ("--unrelated-changes", "Preexisting unrelated gitlink")
        before = inventory(self.root)
        code, out, err = self.review_context(record, host, instructions, "source.txt", extra=declaration)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("omits task-scoped", json.loads(err)["error"])
        self.assertIn(inner, json.loads(err)["error"])
        self.assertNotIn("incomplete_workflow", json.loads(err))
        self.assertEqual(before, inventory(self.root))
        argv = self.context_argv(record, host, instructions, "review", "review.txt",
                                 extra=("--paths", inner, *declaration))
        omissions = self.engine_freeze_refusal(record, host, argv, "review.txt")
        self.assertEqual(omissions["vendor/lib"],
                         "Declared unrelated change outside editable scope: Preexisting unrelated gitlink")

    def test_real_staged_then_unstaged_edit_freezes_working_bytes_with_index_and_head_blobs(self):
        record, host, instructions = self.start("staged")
        original = (self.repo / "source.txt").read_bytes()
        staged, working = b"index-only staged text\n", b"working-tree final text\n"
        (self.repo / "source.txt").write_bytes(staged)
        git(self.repo, "add", "source.txt")
        (self.repo / "source.txt").write_bytes(working)
        value = self.ok("context", "--record", record, "--purpose", "review", "--paths", "source.txt",
                        "--omit-other-paths", "Clean inventory", "--quiescence", "Synthetic writer stopped",
                        "--instructions", str(instructions), "--output", str(host / "review.txt"))
        self.assertEqual(value["coverage"]["task_changes_selected"], ["source.txt"])
        entry = self.frozen_manifest(record, value["artifact"])["source.txt"]
        self.assertEqual(entry["kind"], "file")
        self.assertEqual(entry["object"], safe.digest(working))
        self.assertEqual(entry["index_object"], safe.digest(staged))
        self.assertEqual(entry["head_object"], safe.digest(original))
        rendered = (host / "review.txt").read_text()
        self.assertIn("working-tree final text", rendered)
        self.assertNotIn("index-only staged text", rendered)
        # Neither the helper nor the engine changed the staged or working source.
        self.assertEqual(git(self.repo, "show", ":source.txt").stdout, staged)
        self.assertEqual((self.repo / "source.txt").read_bytes(), working)
        steps = json.loads(Path(value["workflow"]).read_text())["steps"]
        self.assertEqual([(s["command"], s["status"]) for s in steps],
                         [("artifact freeze", "committed"), ("packet seal", "committed")])

    def test_real_selected_file_drift_between_freeze_and_seal_retains_artifact_without_packet(self):
        record, host, instructions = self.start("drift")
        frozen_bytes, drifted = b"reviewed source bytes\n", b"edited after freeze\n"
        (self.repo / "source.txt").write_bytes(frozen_bytes)
        actual_mutation = backend.Backend.mutation
        seen = []

        def drift_after_actual_freeze(instance, entity, action, *args, **kwargs):
            seen.append(entity + " " + action)
            response = actual_mutation(instance, entity, action, *args, **kwargs)
            if (entity, action) == ("artifact", "freeze"):
                (self.repo / "source.txt").write_bytes(drifted)
            return response

        with mock.patch.object(backend.Backend, "mutation", drift_after_actual_freeze):
            code, out, err = self.review_context(record, host, instructions, "source.txt")
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(seen, ["artifact freeze"])
        error = json.loads(err)
        self.assertIn("does not match selected live source", error["error"])
        self.assertIn("artifact retained as evidence, no packet sealed", error["error"])
        workflow = json.loads(Path(error["incomplete_workflow"]).read_text())
        self.assertEqual(workflow["status"], "incomplete")
        self.assertEqual([(s["command"], s["status"]) for s in workflow["steps"]],
                         [("artifact freeze", "committed")])
        frozen = json.loads((Path(workflow["steps"][0]["trace"]) / "stdout").read_text())
        artifact = frozen["data"]["result"]["artifact"]
        self.assertEqual(self.frozen_manifest(record, artifact)["source.txt"]["object"], safe.digest(frozen_bytes))
        self.assertFalse((host / "review.txt").exists())
        state = self.ok("show", "--record", record)["record"]
        self.assertEqual([a["id"] for a in state["artifacts"]], [artifact])
        self.assertEqual(state["current_artifact"], artifact)
        self.assertEqual(state["packets"], [])
        self.assertEqual((self.repo / "source.txt").read_bytes(), drifted)


if __name__ == "__main__":
    unittest.main()
