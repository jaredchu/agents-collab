#!/usr/bin/env python3
"""Materialize six disposable public-source copies; no model or record runtime."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

BASE = "94e57237e48eaee5c1583c95bbd9b408a4b803bc"
VALIDATOR = "skills/agents-collab/scripts/validate_profile.py"
DOC = "skills/agents-collab/references/configuration.md"
BOUNDARY = "tests/test_integer_boundaries.py"
DOC_ADDITION = """
## Integer contract

Numeric bounds require positive integers; the follow-up allowance permits zero.
Booleans are not integers in the v1 profile contract.
"""
BOUNDARY_TEXT = '''"""Ordinary integer boundaries for the existing v1 contract."""
import unittest
from test_validate_profile import base_profile, vp


class IntegerBoundaries(unittest.TestCase):
    def test_followup_zero_is_valid(self):
        data = base_profile()
        data["review"]["max_followup_rounds"] = 0
        self.assertEqual(vp.validate_profile(data), [])

    def test_bounds_zero_is_invalid_and_one_is_valid(self):
        for key in ("writer_minutes", "reviewer_minutes", "review_output_words"):
            for value, valid in ((0, False), (1, True)):
                with self.subTest(key=key, value=value):
                    data = base_profile()
                    data["bounds"][key] = value
                    paths = [issue.path for issue in vp.validate_profile(data)]
                    self.assertEqual("bounds." + key not in paths, valid)
'''


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-c", "core.autocrlf=false", "-c", "core.hooksPath=/dev/null",
         "-C", str(repo), *args], stderr=subprocess.PIPE,
    )


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def inventory(repo):
    names = sorted(set(git(repo, "ls-files", "-z", "--cached", "--others",
                           "--exclude-standard").split(b"\0")) - {b""})
    result = []
    for name in names:
        path = repo / os.fsdecode(name)
        if path.is_symlink():
            raw, mode = os.fsencode(os.readlink(path)), "120000"
        elif path.is_file():
            raw = path.read_bytes()
            mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        else:
            raise ValueError("unsupported/missing fixture path: " + os.fsdecode(name))
        result.append({"path": os.fsdecode(name), "mode": mode,
                       "bytes": len(raw), "sha256": digest(raw)})
    return result


def identity(repo):
    files = inventory(repo)
    status = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    staged = git(repo, "diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv")
    unstaged = git(repo, "diff", "--binary", "--no-ext-diff", "--no-textconv")
    index = git(repo, "ls-files", "--stage", "-z")
    return {"source_commit": BASE, "head": git(repo, "rev-parse", "HEAD").decode().strip(),
            "working_inventory_sha256": digest(canonical(files)), "files": files,
            "status_entries": status.decode().split("\0")[:-1],
            "status_sha256": digest(status), "index_sha256": digest(index),
            "staged_patch_sha256": digest(staged), "unstaged_patch_sha256": digest(unstaged)}


def seed_h2(repo):
    doc = repo / DOC
    doc.write_bytes(doc.read_bytes() + DOC_ADDITION.encode())
    git(repo, "add", "--", DOC)
    script = repo / VALIDATOR
    original = b"if type(value) is not int:  # bool is a subclass of int; reject it explicitly"
    replacement = b"if not isinstance(value, int):  # use a common numeric predicate"
    raw = script.read_bytes()
    if raw.count(original) != 1:
        raise ValueError("seed anchor changed")
    script.write_bytes(raw.replace(original, replacement))
    (repo / BOUNDARY).write_bytes(BOUNDARY_TEXT.encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path,
                        help="new private directory, outside source and all Git trees")
    args = parser.parse_args()
    source, out = args.source.resolve(strict=True), args.out.resolve()
    git(source, "cat-file", "-e", BASE + "^{commit}")
    if out == source or source in out.parents:
        parser.error("output must be outside source")
    # Refuse a containing Git tree; do not create artifacts in another checkout.
    parent = out.parent
    while not parent.exists():
        parent = parent.parent
    probe = subprocess.run(["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
                           capture_output=True)
    if probe.returncode == 0:
        parser.error("output must be outside every Git tree")
    out.mkdir(parents=True, exist_ok=False)
    manifests = {}
    for case in ("H1", "H2", "H3"):
        for arm in ("A", "B"):
            name = case + "-" + arm
            repo = out / name
            subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout",
                            str(source), str(repo)], check=True)
            git(repo, "checkout", "--quiet", "--detach", BASE)
            if case == "H2":
                seed_h2(repo)
            manifests[name] = identity(repo)
            (out / (name + ".start.json")).write_bytes(canonical(manifests[name]) + b"\n")
        if manifests[case + "-A"] != manifests[case + "-B"]:
            raise ValueError(case + " starting copies differ")
    (out / "start-manifest.json").write_bytes(canonical(manifests) + b"\n")
    print(json.dumps({"source_commit": BASE, "pairs_equal": True,
                      "identities": {k: v["working_inventory_sha256"]
                                     for k, v in manifests.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
