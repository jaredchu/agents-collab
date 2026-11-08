"""Unit tests for skills/agents-collab/scripts/validate_profile.py and package assets.

Run from the repository root:

    python3 -m unittest discover -s tests -v

Temporary files go to the system temporary area (honouring TMPDIR) and are
removed afterwards. No network, credentials, model calls or installs are used.
Requires Python 3.9+ and no third-party packages.
"""

import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "skills" / "agents-collab"
SCRIPT = PACKAGE / "scripts" / "validate_profile.py"
EXAMPLE = PACKAGE / "examples" / "profile.example.json"

# Do not leave a __pycache__ inside the distributable package.
_previous_flag = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    _spec = importlib.util.spec_from_file_location("validate_profile", SCRIPT)
    vp = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(vp)
finally:
    sys.dont_write_bytecode = _previous_flag


def base_profile():
    """A neutral, fully populated valid profile (placeholder model IDs)."""
    return {
        "version": 1,
        "name": "test-profile",
        "agents": {
            "lead": {"model": "current", "transport": "host", "reasoning": "inherit"},
            "writer": {"model": "vendor-a-model-1", "transport": "claude-cli", "reasoning": "high"},
            "rev1": {"model": "vendor-b-model-2", "transport": "codex-native", "reasoning": "medium"},
            "rev2": {"model": "vendor-a-model-3", "transport": "claude-cli", "reasoning": "inherit"},
        },
        "routing": {"small_writer": "current-session", "substantial_writer": "writer"},
        "review": {
            "on_consequential_work": "single",
            "candidates": ["rev1", "rev2"],
            "prefer_different_model": True,
            "recipes": {"pair": ["rev1", "rev2"]},
            "max_followup_rounds": 1,
        },
        "effort_check": "supported-control",
        "access": "existing-subscriptions",
        "bounds": {
            "enforcement": "required",
            "writer_minutes": 20,
            "reviewer_minutes": 5,
            "review_output_words": 600,
        },
        "records_root": "/var/tmp/agents-collab-records",
    }


class ValidatorCase(unittest.TestCase):
    def paths(self, data):
        return [issue.path for issue in vp.validate_profile(data)]

    def assertValid(self, data):
        issues = vp.validate_profile(data)
        self.assertEqual(issues, [], "\n".join(str(i) for i in issues))

    def assertIssueAt(self, data, path):
        found = self.paths(data)
        self.assertIn(path, found, f"expected an issue at {path}; got {found}")

    def assertOnlyIssuesAt(self, data, *paths):
        self.assertEqual(sorted(self.paths(data)), sorted(paths))


class ShippedProfiles(ValidatorCase):
    def test_generic_example_is_valid(self):
        self.assertEqual(vp.check_file(str(EXAMPLE)), [])

    def test_base_fixture_is_valid(self):
        self.assertValid(base_profile())


class NoMutation(ValidatorCase):
    def test_inherit_and_named_levels_are_not_rewritten(self):
        data = base_profile()
        before = copy.deepcopy(data)
        self.assertValid(data)
        self.assertEqual(data, before)
        self.assertEqual(data["agents"]["rev2"]["reasoning"], "inherit")
        self.assertEqual(data["agents"]["lead"]["model"], "current")

    def test_invalid_profile_is_not_repaired(self):
        data = base_profile()
        data["review"]["max_followup_rounds"] = True
        before = copy.deepcopy(data)
        self.assertTrue(vp.validate_profile(data))
        self.assertEqual(data, before)
        self.assertIs(data["review"]["max_followup_rounds"], True)


class Reasoning(ValidatorCase):
    def test_explicit_named_levels_accepted_per_agent(self):
        data = base_profile()
        data["agents"]["rev1"]["reasoning"] = "xhigh"
        data["agents"]["writer"]["reasoning"] = "max"
        data["agents"]["lead"]["reasoning"] = "high"  # explicitly required lead effort
        self.assertValid(data)

    def test_ambiguous_or_malformed_levels_rejected(self):
        for value in ("default", "current", "High", "", "very high", "-high"):
            with self.subTest(value=value):
                data = base_profile()
                data["agents"]["writer"]["reasoning"] = value
                self.assertOnlyIssuesAt(data, "agents.writer.reasoning")

    def test_non_string_level_rejected(self):
        for value in (3, None, True, ["high"]):
            with self.subTest(value=value):
                data = base_profile()
                data["agents"]["writer"]["reasoning"] = value
                self.assertOnlyIssuesAt(data, "agents.writer.reasoning")


class DuplicateKeys(ValidatorCase):
    def test_top_level_duplicate(self):
        text = json.dumps(base_profile())[:-1] + ', "access": "existing-subscriptions"}'
        self.assertIn("access", [i.path for i in vp.check_text(text)])

    def test_nested_duplicate_inside_agent(self):
        text = json.dumps(base_profile()).replace(
            '"reasoning": "high"}', '"reasoning": "high", "reasoning": "low"}', 1)
        self.assertIn("agents.writer.reasoning", [i.path for i in vp.check_text(text)])

    def test_duplicate_agent_name(self):
        text = json.dumps(base_profile()).replace(
            '"agents": {', '"agents": {"rev1": {"model": "x-1", "transport": "claude-cli", "reasoning": "low"}, ', 1)
        self.assertIn("agents.rev1", [i.path for i in vp.check_text(text)])


class KeysAndTypes(ValidatorCase):
    def test_unknown_keys_rejected_at_each_level(self):
        cases = [
            ((), "fallback"),
            (("agents", "writer"), "api_key"),
            (("routing",), "consequential_writer"),
            (("review",), "max_rounds"),
            (("bounds",), "deadline"),
        ]
        for parents, key in cases:
            with self.subTest(key=key):
                data = base_profile()
                target = data
                for part in parents:
                    target = target[part]
                target[key] = "x"
                expected = ".".join(parents + (key,))
                self.assertOnlyIssuesAt(data, expected)

    def test_missing_keys_rejected(self):
        for parents, key in [((), "records_root"), (("agents", "rev1"), "transport"),
                             (("review",), "recipes"), (("bounds",), "enforcement"),
                             (("routing",), "small_writer")]:
            with self.subTest(key=key):
                data = base_profile()
                target = data
                for part in parents:
                    target = target[part]
                del target[key]
                self.assertIssueAt(data, ".".join(parents + (key,)))

    def test_bools_are_not_integers(self):
        for parents, key in [(("review",), "max_followup_rounds"), (("bounds",), "writer_minutes"),
                             (("bounds",), "reviewer_minutes"), (("bounds",), "review_output_words")]:
            for value in (True, False):
                with self.subTest(key=key, value=value):
                    data = base_profile()
                    target = data
                    for part in parents:
                        target = target[part]
                    target[key] = value
                    self.assertOnlyIssuesAt(data, ".".join(parents + (key,)))

    def test_integers_are_not_bools(self):
        for value in (1, 0, "true"):
            with self.subTest(value=value):
                data = base_profile()
                data["review"]["prefer_different_model"] = value
                self.assertOnlyIssuesAt(data, "review.prefer_different_model")

    def test_numeric_ranges_and_floats(self):
        for key, value in [("writer_minutes", 0), ("reviewer_minutes", -5),
                           ("writer_minutes", 30.0), ("review_output_words", "800")]:
            with self.subTest(key=key, value=value):
                data = base_profile()
                data["bounds"][key] = value
                self.assertOnlyIssuesAt(data, "bounds." + key)
        data = base_profile()
        data["review"]["max_followup_rounds"] = 0
        self.assertValid(data)
        data["review"]["max_followup_rounds"] = -1
        self.assertOnlyIssuesAt(data, "review.max_followup_rounds")

    def test_wrong_container_types(self):
        for key, value in [("agents", []), ("routing", "lead"), ("review", None), ("bounds", [1])]:
            with self.subTest(key=key):
                data = base_profile()
                data[key] = value
                self.assertIssueAt(data, key)


class Enums(ValidatorCase):
    def test_timing_enforcement_enum(self):
        for value in ("Required", "hard", "enforced", True, None):
            with self.subTest(value=value):
                data = base_profile()
                data["bounds"]["enforcement"] = value
                self.assertOnlyIssuesAt(data, "bounds.enforcement")
        data = base_profile()
        data["bounds"]["enforcement"] = "advisory"
        self.assertValid(data)

    def test_other_enums(self):
        cases = [
            (("effort_check",), "attested"),
            (("access",), "api"),
            (("review", "on_consequential_work"), "pair"),
            (("agents", "rev1", "transport"), "openai-api"),
        ]
        for keys, value in cases:
            with self.subTest(keys=keys):
                data = base_profile()
                target = data
                for part in keys[:-1]:
                    target = target[part]
                target[keys[-1]] = value
                self.assertOnlyIssuesAt(data, ".".join(keys))


class References(ValidatorCase):
    def test_routing_must_reference_configured_agent(self):
        data = base_profile()
        data["routing"]["substantial_writer"] = "writr"
        self.assertOnlyIssuesAt(data, "routing.substantial_writer")

    def test_current_session_allowed_only_in_routing(self):
        data = base_profile()
        data["review"]["candidates"] = ["current-session"]
        self.assertOnlyIssuesAt(data, "review.candidates[0]")
        data = base_profile()
        data["agents"]["current-session"] = data["agents"].pop("rev2")
        data["review"]["candidates"] = ["rev1"]
        data["review"]["recipes"] = {}
        self.assertOnlyIssuesAt(data, "agents.current-session")

    def test_candidate_and_recipe_references(self):
        data = base_profile()
        data["review"]["candidates"] = ["rev1", "ghost"]
        self.assertOnlyIssuesAt(data, "review.candidates[1]")
        data = base_profile()
        data["review"]["recipes"]["pair"] = ["rev1", "ghost"]
        self.assertOnlyIssuesAt(data, "review.recipes.pair[1]")

    def test_duplicate_reviewers_rejected(self):
        data = base_profile()
        data["review"]["recipes"]["pair"] = ["rev1", "rev1"]
        self.assertOnlyIssuesAt(data, "review.recipes.pair[1]")
        data = base_profile()
        data["review"]["candidates"] = ["rev2", "rev2"]
        self.assertOnlyIssuesAt(data, "review.candidates[1]")

    def test_empty_recipe_and_bad_recipe_name(self):
        data = base_profile()
        data["review"]["recipes"] = {"pair": []}
        self.assertOnlyIssuesAt(data, "review.recipes.pair")
        data = base_profile()
        data["review"]["recipes"] = {"bad name": ["rev1"]}
        self.assertEqual(len(vp.validate_profile(data)), 1)

    def test_lead_cannot_be_fresh_reviewer(self):
        data = base_profile()
        data["review"]["candidates"] = ["lead", "rev1"]
        self.assertOnlyIssuesAt(data, "review.candidates[0]")
        data = base_profile()
        data["review"]["recipes"]["pair"] = ["rev1", "lead"]
        self.assertOnlyIssuesAt(data, "review.recipes.pair[1]")

    def test_single_review_needs_a_candidate(self):
        data = base_profile()
        data["review"]["candidates"] = []
        self.assertOnlyIssuesAt(data, "review.candidates")
        data["review"]["on_consequential_work"] = "none"
        data["review"]["recipes"] = {}
        self.assertValid(data)

    def test_no_agents(self):
        data = base_profile()
        data["agents"] = {}
        self.assertIssueAt(data, "agents")


class ModelTransport(ValidatorCase):
    def test_current_requires_host(self):
        for transport in ("claude-cli", "codex-native"):
            with self.subTest(transport=transport):
                data = base_profile()
                data["agents"]["rev1"] = {"model": "current", "transport": transport, "reasoning": "inherit"}
                self.assertOnlyIssuesAt(data, "agents.rev1.model")

    def test_host_cannot_switch_model(self):
        data = base_profile()
        data["agents"]["lead"]["model"] = "vendor-a-model-1"
        self.assertOnlyIssuesAt(data, "agents.lead.model")

    def test_single_host_agent(self):
        data = base_profile()
        data["agents"]["lead2"] = {"model": "current", "transport": "host", "reasoning": "high"}
        self.assertOnlyIssuesAt(data, "agents")

    def test_profile_without_host_agent_is_valid(self):
        data = base_profile()
        del data["agents"]["lead"]
        self.assertValid(data)

    def test_unsafe_model_identifiers(self):
        for value in ("--dangerously-skip-permissions", "-m", "model a", "model\n", "", "x" * 200, 7):
            with self.subTest(value=value):
                data = base_profile()
                data["agents"]["writer"]["model"] = value
                self.assertOnlyIssuesAt(data, "agents.writer.model")

    def test_exact_identifier_forms_accepted(self):
        for value in ("provider/model-1.5", "model-x[1m]", "model@2026-01-01", "m:tag"):
            with self.subTest(value=value):
                data = base_profile()
                data["agents"]["writer"]["model"] = value
                self.assertValid(data)

    def test_angle_bracket_placeholders_are_rejected(self):
        # The guide's placeholders rely on this: an unreplaced <model-id> fails.
        data = base_profile()
        data["agents"]["writer"]["model"] = "<writer-model-id>"
        self.assertOnlyIssuesAt(data, "agents.writer.model")


class RecordsRoot(ValidatorCase):
    def test_rejected_paths(self):
        for value in ("records", "./records", "~", "~/", "/", "//", "~other/records",
                      "/srv/../etc", "~/a/./b", "/srv/x\x00y", " /srv/x", "", "$HOME/records", 5):
            with self.subTest(value=value):
                data = base_profile()
                data["records_root"] = value
                self.assertOnlyIssuesAt(data, "records_root")

    def test_accepted_paths(self):
        for value in ("~/records", "~/.local/state/agents-collab", "/srv/collab-records"):
            with self.subTest(value=value):
                data = base_profile()
                data["records_root"] = value
                self.assertValid(data)


class Versions(ValidatorCase):
    def test_unsupported_versions_stop_interpretation(self):
        for value in (2, 0, "1", 1.0, True):
            with self.subTest(value=value):
                data = base_profile()
                data["version"] = value
                data["surprise"] = "ignored until version is understood"
                self.assertOnlyIssuesAt(data, "version")

    def test_missing_version(self):
        data = base_profile()
        del data["version"]
        self.assertOnlyIssuesAt(data, "version")


class Parsing(ValidatorCase):
    def test_non_object_root(self):
        self.assertEqual([i.path for i in vp.check_text("[]")], ["(root)"])

    def test_invalid_json_reports_position_not_content(self):
        issues = vp.check_text('{"version": 1, "name": "secret-value-123",}')
        self.assertEqual(len(issues), 1)
        self.assertIn("line 1", issues[0].message)
        self.assertNotIn("secret-value-123", issues[0].message)

    def test_non_finite_numbers_rejected(self):
        text = json.dumps(base_profile()).replace('"writer_minutes": 20', '"writer_minutes": NaN')
        self.assertEqual([i.path for i in vp.check_text(text)], ["(file)"])


class CommandLine(unittest.TestCase):
    def setUp(self):
        # System temporary area (TMPDIR is honoured); never inside the repository.
        self._tmp = tempfile.TemporaryDirectory(prefix="agents-collab-test-")
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args, timeout=30):
        return subprocess.run(
            [sys.executable, "-I", "-B", str(SCRIPT), *args],
            cwd=str(self.tmp), capture_output=True, text=True, timeout=timeout,
            env=dict(os.environ, TMPDIR=str(self.tmp)),
        )

    def write(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_profile_exit_zero_and_nothing_written(self):
        path = self.write("p.json", json.dumps(base_profile()))
        before_bytes = path.read_bytes()
        result = self.run_cli(str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("were not checked", result.stdout)
        self.assertEqual(path.read_bytes(), before_bytes)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["p.json"])

    def test_invalid_profile_exit_one_without_echoing_values(self):
        secret = "sk-test-0123456789abcdefghijklmnopqrstuvwxyz"
        data = base_profile()
        data["agents"]["writer"]["model"] = "bad model " + secret
        data["review"]["token"] = secret
        data[secret] = "x"
        path = self.write("p.json", json.dumps(data))
        result = self.run_cli(str(path))
        self.assertEqual(result.returncode, 1)
        output = result.stdout + result.stderr
        self.assertNotIn(secret, output)
        self.assertIn("agents.writer.model", output)
        self.assertIn("review.token", output)
        self.assertIn("<redacted key>", output)

    def test_unreadable_input_exit_two(self):
        self.assertEqual(self.run_cli(str(self.tmp / "missing.json")).returncode, 2)
        self.assertEqual(self.run_cli(str(self.tmp)).returncode, 2)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFOs not available")
    def test_fifo_exit_two_without_blocking(self):
        # No writer ever opens the FIFO: a blocking open/read would hang here.
        # The short subprocess timeout turns such a regression into a failure.
        fifo = self.tmp / "profile.fifo"
        os.mkfifo(str(fifo))
        link = self.tmp / "fifo-link.json"
        os.symlink(str(fifo), str(link))
        for target in (fifo, link):
            with self.subTest(target=target.name):
                try:
                    result = self.run_cli(str(target), timeout=10)
                except subprocess.TimeoutExpired:
                    self.fail("validator blocked on a FIFO instead of rejecting it")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("not a regular file", result.stderr)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks not available")
    def test_symlink_to_regular_profile_is_followed(self):
        path = self.write("real.json", json.dumps(base_profile()))
        link = self.tmp / "link.json"
        try:
            os.symlink(str(path), str(link))
        except OSError as exc:
            self.skipTest(f"cannot create symlink: {exc}")
        result = self.run_cli(str(link))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_usage_error_exit_two(self):
        self.assertEqual(self.run_cli().returncode, 2)

    def test_malformed_and_non_utf8_exit_one(self):
        self.assertEqual(self.run_cli(str(self.write("bad.json", "{"))).returncode, 1)
        path = self.tmp / "latin1.json"
        path.write_bytes(b'{"name": "\xff"}')
        self.assertEqual(self.run_cli(str(path)).returncode, 1)

    def test_oversized_profile_exit_one(self):
        path = self.write("big.json", " " * (vp.MAX_BYTES + 1) + "{}")
        self.assertEqual(self.run_cli(str(path)).returncode, 1)


class PackageContents(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        link = re.compile(r"\]\(([^)\s]+)\)")
        for path in PACKAGE.rglob("*.md"):
            for target in link.findall(path.read_text(encoding="utf-8")):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue
                with self.subTest(file=path.name, target=target):
                    self.assertTrue((path.parent / target.split("#")[0]).exists())

    def test_task_state_template_is_inert(self):
        text = (PACKAGE / "assets" / "task-state.json").read_text(encoding="utf-8")
        # Reuse the validator's parser so duplicate keys in the template are caught.
        data = vp.parse_text(text)
        dups = []
        vp._collect_duplicates(data, "", dups)
        self.assertEqual(dups, [])
        for key in ("artifacts", "assignments", "reviews", "findings"):
            self.assertEqual(data[key], [], key)
        cycle = data["review_cycle"]
        self.assertIsNone(cycle["initial_identity"])
        self.assertFalse(cycle["initial_complete"])
        self.assertEqual(cycle["followups_used"], 0)
        observed = data["item_templates"]["assignment"]["runtime_observed"]
        self.assertEqual(set(observed.values()), {"unknown"})

    def test_skill_metadata_names_the_package(self):
        text = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        front = text.split("---", 2)[1]
        self.assertIn("name: agents-collab", front)
        self.assertRegex(front, r"\ndescription: \S")


if __name__ == "__main__":
    unittest.main()
