#!/usr/bin/env python3
"""Offline behavioral oracle, not a model grader or collaboration-state gate."""

import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
from build_fixtures import BASE, BOUNDARY, DOC, VALIDATOR, digest, git


def load_tests(repo):
    spec = importlib.util.spec_from_file_location("fixture_validator_tests",
                                                repo / "tests/test_validate_profile.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(case, repo, start, scratch):
    tests = load_tests(repo)
    checks = []

    def record(name, passed, detail=""):
        checks.append({"check": name, "pass": bool(passed), "detail": detail})

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(scratch))

    def cli(*args):
        return subprocess.run([sys.executable, "-I", "-B", str(repo / VALIDATOR), *args],
                              cwd=scratch, env=env, text=True, capture_output=True)

    def write(name, raw):
        path = scratch / name
        path.write_bytes(raw)
        return str(path)

    base = tests.base_profile()
    valid = write("valid.json", json.dumps(base).encode())
    original = Path(valid).read_bytes()
    human = cli(valid)
    record("ordinary valid human mode", human.returncode == 0 and human.stderr == ""
           and human.stdout == "valid v1 profile structure (model availability, runtime controls, "
           "permissions and resolved storage were not checked)\n")
    record("validator never changes input", Path(valid).read_bytes() == original)
    record("frozen source base", git(repo, "rev-parse", "HEAD").decode().strip() == BASE)
    for pattern in ("test_validate_profile.py", "test_setup_profile.py"):
        run = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
                              "-p", pattern, "-v"], cwd=repo, env=env,
                             text=True, capture_output=True)
        record("existing suite " + pattern, run.returncode == 0, run.stderr)

    new_test = {"H1": "tests/test_json_diagnostics.py", "H2": BOUNDARY,
                "H3": "tests/test_supported_version.py"}[case]
    allowed = {VALIDATOR, DOC, new_test} if case != "H2" else {VALIDATOR, DOC, BOUNDARY}
    changed = set(git(repo, "diff", "HEAD", "--name-only", "-z").decode().split("\0")) - {""}
    changed.update(set(git(repo, "ls-files", "--others", "--exclude-standard", "-z")
                       .decode().split("\0")) - {""})
    record("editable scope", changed <= allowed, ", ".join(sorted(changed - allowed)))
    record("task test exists", (repo / new_test).is_file())
    if (repo / new_test).is_file():
        run = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
                              "-p", Path(new_test).name, "-v"], cwd=repo, env=env,
                             text=True, capture_output=True)
        record("task tests pass", run.returncode == 0, run.stderr)

    # Independent matrix exercises actual validator behavior, not its source spelling.
    for section, key, minimum in (("review", "max_followup_rounds", 0),
                                 ("bounds", "writer_minutes", 1),
                                 ("bounds", "reviewer_minutes", 1),
                                 ("bounds", "review_output_words", 1)):
        for value in (False, True, -1, 0, 1, 2, 1.0, "1", None):
            data = copy.deepcopy(base)
            data[section][key] = value
            paths = [issue.path for issue in tests.vp.validate_profile(data)]
            expected_valid = type(value) is int and value >= minimum
            record("strict integer " + section + "." + key + "=" + repr(value),
                   ((section + "." + key) not in paths) == expected_valid)

    if case == "H1":
        secret = "PRIVATE_VALUE_MARKER_93d2"
        bad = copy.deepcopy(base)
        bad["agents"]["writer"]["model"] = "bad model " + secret
        bad["private key " + secret] = secret
        invalid = write("invalid.json", json.dumps(bad).encode())
        duplicate = json.dumps(base).replace('"version": 1', '"version": 1, "version": 1')
        inputs = [("valid", valid, 0, True), ("invalid", invalid, 1, False),
                  ("duplicate", write("dup.json", duplicate.encode()), 1, False),
                  ("malformed", write("malformed.json", b"{"), 1, False),
                  ("utf8", write("utf8.json", b"\xff"), 1, False),
                  ("oversized", write("big.json", b" " * (256 * 1024 + 1)), 1, False),
                  ("missing", str(scratch / "missing.json"), 2, None),
                  ("directory", str(scratch), 2, None)]
        for name, path, code, valid_value in inputs:
            result = cli("--json", path)
            try:
                obj = json.loads(result.stdout)
                shape = (type(obj) is dict and set(obj) == {"schema_version", "valid", "issues", "scope"}
                         and type(obj["schema_version"]) is int and obj["schema_version"] == 1
                         and obj["valid"] is valid_value and obj["scope"] == "structure-only"
                         and type(obj["issues"]) is list
                         and all(type(i) is dict and set(i) == {"path", "message"}
                                 and all(type(v) is str for v in i.values()) for i in obj["issues"])
                         and (bool(obj["issues"]) == (code != 0))
                         and (code != 2 or obj["issues"][0]["path"] == "(file)"))
            except (ValueError, KeyError, TypeError, IndexError):
                shape = False
            record("JSON " + name, result.returncode == code and result.stderr == "" and shape)
            record("JSON privacy " + name, secret not in result.stdout + result.stderr)
        record("JSON documented", "--json" in (repo / DOC).read_text())

    if case == "H2":
        if start is None:
            record("initial manifest supplied", False)
        else:
            record("index preserved", digest(git(repo, "ls-files", "--stage", "-z")) == start["index_sha256"])
            before = {item["path"]: item for item in start["files"]}
            for path in (DOC, BOUNDARY):
                record("existing bytes preserved " + path,
                       (repo / path).is_file() and digest((repo / path).read_bytes()) == before[path]["sha256"])
            status = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").decode().split("\0")
            record("staged documentation and untracked test provenance preserved",
                   "M  " + DOC in status and "?? " + BOUNDARY in status)

    if case == "H3":
        result = cli("--print-supported-version")
        record("version only", result.returncode == 0 and result.stdout == "1\n" and result.stderr == "")
        for path in (str(scratch / "does-not-exist.json"), valid, str(scratch)):
            result = cli("--print-supported-version", path)
            record("version/profile usage conflict " + Path(path).name,
                   result.returncode == 2 and result.stdout == "" and "usage:" in result.stderr)
        result = cli()
        record("no argument usage", result.returncode == 2 and result.stdout == "")
        result = cli("--help")
        record("help", result.returncode == 0 and "--print-supported-version" in result.stdout)
        record("version documented", "--print-supported-version" in (repo / DOC).read_text())
        # Rebind the public constant in memory to distinguish the real source of truth
        # from a hard-coded print literal. No source file is modified.
        tests.vp.SUPPORTED_VERSION = 7
        import contextlib
        import io
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = tests.vp.main(["--print-supported-version"])
        except SystemExit as exc:
            code = exc.code
        record("version constant used", code == 0 and stdout.getvalue() == "7\n" and stderr.getvalue() == "")

    return {"case": case, "pass": all(item["pass"] for item in checks), "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=("H1", "H2", "H3"))
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--start", type=Path, help="private starting manifest, required for H2")
    parser.add_argument("--scratch", required=True, type=Path, help="existing private scratch directory")
    args = parser.parse_args()
    start = json.loads(args.start.read_text()) if args.start else None
    with tempfile.TemporaryDirectory(prefix="oracle-", dir=args.scratch.resolve(strict=True)) as temp:
        result = check(args.case, args.repo.resolve(strict=True), start, Path(temp))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
