#!/usr/bin/env python3
"""Local regression gate for the Rust CLI and the Python suite (no CI).

Builds an immutable `git archive` snapshot of one clean, pinned commit inside a
new caller-selected scratch directory, then runs cargo fmt --check, a locked
build, clippy (all targets, warnings denied), cargo test and the full Python
suite against a frozen copy of the freshly built binary. Every source, build,
temporary and log file stays inside that scratch directory. Cargo runs offline;
fetch locked dependencies separately beforehand (see docs/cli.md).

The result is `result.json` in the scratch directory: source revision/tree,
archive and binary SHA-256, tool versions, commands, logs, exit statuses and
any incomplete step. Python 3.9+, standard library only. No model calls, no
network access requested, no global configuration changes.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
SCHEMA = "agents-collab-check-cli/1"
# Test classes that exercise the real engine; each must run, never skip.
REAL_ENGINE_CLASSES = ("test_backend.RealBackendTests",)
# Test-only fault hooks must never leak into a gate run.
STRIPPED_ENV = ("AGENTS_COLLAB_FAULT", "AGENTS_COLLAB_CAPTURE_PAUSE", "AGENTS_COLLAB_TEST_BINARY")


class Refused(Exception):
    """Precondition failure before any scratch write."""


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(source, *args):
    result = subprocess.run(["git", "-C", str(source), *args], capture_output=True)
    if result.returncode:
        raise Refused("git " + " ".join(args) + " failed: " + result.stderr.decode(errors="replace").strip())
    return result.stdout.decode().strip()


def overlaps(a, b):
    return a == b or a in b.parents or b in a.parents


def inside_git(path):
    probe = path
    while not probe.exists():
        probe = probe.parent
    return subprocess.run(["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
                          capture_output=True).returncode == 0


def check_platform():
    """Supported gate: macOS arm64. Engine tests separately refuse unsupported storage."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise Refused(f"unsupported gate platform {platform.system()} {platform.machine()}; supported: macOS arm64")


def storage_observation(path):
    """Report the mount type of `path` from df/mount; refuse unless local APFS."""
    df = subprocess.run(["df", "-P", str(path)], capture_output=True, text=True)
    lines = df.stdout.strip().splitlines()
    if df.returncode or len(lines) < 2:
        raise Refused("cannot determine scratch filesystem")
    mount_point = lines[-1].split(None, 5)[-1]
    mounts = subprocess.run(["mount"], capture_output=True, text=True).stdout
    entry = next((line for line in mounts.splitlines() if f" on {mount_point} (" in line), "")
    options = entry.rpartition("(")[2].rstrip(")").split(", ") if entry else []
    if not options or options[0] != "apfs" or "local" not in options:
        raise Refused(f"scratch must be on local APFS; observed {options or 'unknown'} at its mount point")
    return {"mount_options": options, "note": "df/mount preflight; the engine performs its own runtime storage check"}


def preflight(source, scratch, revision):
    """Validate everything before the first write. Returns the pinned commit and tree."""
    source = Path(source).resolve()
    if not Path(scratch).is_absolute():
        raise Refused("scratch must be an absolute path")
    scratch = Path(os.path.abspath(scratch))
    parent = scratch.parent
    if not parent.is_dir():
        raise Refused("scratch parent must already exist; the gate never creates caller directories")
    scratch = parent.resolve() / scratch.name
    if os.path.lexists(scratch):
        raise Refused("scratch already exists; choose a new directory (results are never reused or replaced)")
    if git(source, "rev-parse", "--show-toplevel") != str(source):
        raise Refused("source must be the Git checkout root")
    if overlaps(scratch, source):
        raise Refused("scratch overlaps the source checkout")
    if inside_git(parent):
        raise Refused("scratch must be outside every Git repository")
    status = git(source, "status", "--porcelain", "--untracked-files=normal")
    if status:
        raise Refused("source checkout is not clean; commit or stash changes first:\n" + status)
    commit = git(source, "rev-parse", "--verify", revision + "^{commit}")
    tree = git(source, "rev-parse", "--verify", commit + "^{tree}")
    return source, scratch, commit, tree


def extract(archive, target):
    """Extract only regular files and directories with safe relative names."""
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            name = member.name
            parts = name.split("/")
            if name.startswith("/") or ".." in parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"unsupported archive member {name!r}")
        for member in tar.getmembers():
            path = target / member.name
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, open(path, "xb") as dst:
                shutil.copyfileobj(src, dst)
            os.chmod(path, 0o755 if member.mode & 0o111 else 0o644)


def analyze_cargo_test(text):
    results = re.findall(r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored", text, re.M)
    if not results:
        return "no cargo test result lines"
    if any(r[0] != "ok" or int(r[2]) for r in results):
        return "cargo test reported failures"
    if any(int(r[3]) for r in results):
        return "cargo test ignored tests; ignored coverage is not a pass"
    if sum(int(r[1]) for r in results) == 0:
        return "cargo test ran no tests"
    return None


def analyze_unittest(text, required=REAL_ENGINE_CLASSES):
    ran = re.search(r"^Ran (\d+) tests? in ", text, re.M)
    if not ran or int(ran.group(1)) == 0:
        return "Python suite ran no tests"
    lines = text.rstrip().splitlines()
    if not lines or lines[-1].strip() != "OK":
        return "Python suite did not finish with a plain OK (failures, errors or skips)"
    if re.search(r"\.\.\. skipped", text) or "skipped=" in text:
        return "Python suite skipped tests"
    for name in required:
        # Python 3.9 prints "(module.Class)", 3.11+ "(module.Class.test)"; a docstring adds a line.
        line = r"^test_\w+ \(" + re.escape(name) + r"(?:\.test_\w+)?\)(?:\n[^\n]*)? \.\.\. ok$"
        if not re.search(line, text, re.M):
            return f"missing real-engine coverage from {name}"
    return None


def plan(snapshot, scratch, binary):
    manifest = str(snapshot / "cli/Cargo.toml")
    cargo = ["cargo"]
    return [
        ("cargo-fmt", cargo + ["fmt", "--manifest-path", manifest, "--check"], {}, None),
        ("cargo-build", cargo + ["build", "--locked", "--offline", "--manifest-path", manifest], {}, None),
        ("cargo-clippy", cargo + ["clippy", "--locked", "--offline", "--manifest-path", manifest,
                                  "--all-targets", "--", "-D", "warnings"], {}, None),
        ("cargo-test", cargo + ["test", "--locked", "--offline", "--manifest-path", manifest], {}, analyze_cargo_test),
        ("python-suite", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
         {"AGENTS_COLLAB_TEST_BINARY": str(binary)}, analyze_unittest),
    ]


TOOLS = {"python": [sys.executable, "--version"], "git": ["git", "--version"],
         "rustc": ["rustc", "--version"], "cargo": ["cargo", "--version"],
         "rustfmt": ["cargo", "fmt", "--version"], "clippy": ["cargo", "clippy", "--version"],
         "os": ["uname", "-srm"]}


def tool_versions(env):
    found = {}
    for name, argv in TOOLS.items():
        try:
            out = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=60)
            found[name] = (out.stdout or out.stderr).strip() if out.returncode == 0 else f"unavailable (exit {out.returncode})"
        except (OSError, subprocess.SubprocessError) as exc:
            found[name] = f"unavailable ({exc.__class__.__name__})"
    return found


class Gate:
    def __init__(self, source, scratch, commit, tree):
        self.source, self.scratch = source, scratch
        self.snapshot, self.logs = scratch / "source", scratch / "logs"
        self.binary = scratch / "bin/agents-collab"
        self.result = {"schema": SCHEMA, "status": "incomplete", "failure": None, "started_at": now(),
                       "finished_at": None,
                       "source": {"revision": commit, "tree": tree, "clean_checkout": True,
                                  "snapshot": "git archive of the pinned commit"},
                       "offline": True, "steps": []}

    def save(self):
        temp = self.scratch / "result.json.partial"
        temp.write_text(json.dumps(self.result, indent=2) + "\n")
        os.replace(temp, self.scratch / "result.json")

    def fail(self, reason):
        self.result.update(status="failed", failure=reason, finished_at=now())
        self.save()
        return 1

    def env(self):
        env = {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV}
        env.update(CARGO_TARGET_DIR=str(self.scratch / "target"), TMPDIR=str(self.scratch / "tmp"),
                   PYTHONDONTWRITEBYTECODE="1", CARGO_NET_OFFLINE="true", CARGO_TERM_COLOR="never")
        return env

    def run(self, steps=None):
        os.mkdir(self.scratch, 0o700)  # exclusive: never reuses an existing directory
        for name in ("logs", "tmp", "bin"):
            os.mkdir(self.scratch / name, 0o700)
        self.save()
        try:
            return self._run(steps)
        except KeyboardInterrupt:
            self.result.update(status="interrupted", failure="interrupted by caller", finished_at=now())
            self.save()
            return 130

    def _run(self, steps):
        archive = self.scratch / "source.tar"
        with open(archive, "xb") as out:
            done = subprocess.run(["git", "-C", str(self.source), "archive", "--format=tar",
                                   self.result["source"]["revision"]], stdout=out, stderr=subprocess.PIPE)
        if done.returncode:
            return self.fail("git archive failed: " + done.stderr.decode(errors="replace").strip())
        self.result["source"]["archive_sha256"] = sha256(archive)
        os.mkdir(self.snapshot, 0o700)
        try:
            extract(archive, self.snapshot)
        except (ValueError, tarfile.TarError, OSError) as exc:
            return self.fail(f"snapshot extraction failed: {exc}")
        env = self.env()
        self.result["tools"] = tool_versions(env)
        self.result["environment"] = {k: env.get(k) for k in ("CARGO_TARGET_DIR", "TMPDIR", "CARGO_HOME",
                                                             "CARGO_NET_OFFLINE", "PYTHONDONTWRITEBYTECODE")}
        self.save()
        for index, (name, argv, extra, analyze) in enumerate(steps or plan(self.snapshot, self.scratch, self.binary), 1):
            if name == "python-suite" and not self.binary.is_file():
                return self.fail("no frozen binary for the Python suite")
            step = {"name": name, "argv": argv, "cwd": "source", "extra_env": extra, "status": "running",
                    "started_at": now(), "stdout": f"logs/{index:02d}-{name}.stdout",
                    "stderr": f"logs/{index:02d}-{name}.stderr"}
            self.result["steps"].append(step)
            self.save()
            with open(self.scratch / step["stdout"], "xb") as out, open(self.scratch / step["stderr"], "xb") as err:
                try:
                    code = subprocess.run(argv, cwd=self.snapshot, env={**env, **extra},
                                          stdout=out, stderr=err).returncode
                except OSError as exc:
                    code = None
                    step["launch_error"] = str(exc)
            step.update(exit_status=code, finished_at=now())
            if code != 0:
                step["status"] = "failed"
                return self.fail(f"{name} exited {code}")
            if analyze:
                text = (self.scratch / step["stdout"]).read_text(errors="replace")
                text += "\n" + (self.scratch / step["stderr"]).read_text(errors="replace")
                problem = analyze(text)
                if problem:
                    step.update(status="failed", analysis=problem)
                    return self.fail(f"{name}: {problem}")
            step["status"] = "passed"
            if name == "cargo-build":
                built = self.scratch / "target/debug/agents-collab"
                if not built.is_file():
                    return self.fail("build reported success but produced no binary")
                with open(built, "rb") as src, open(self.binary, "xb") as dst:
                    shutil.copyfileobj(src, dst)
                os.chmod(self.binary, 0o700)
                self.result["binary"] = {"path": "bin/agents-collab", "sha256": sha256(self.binary),
                                         "built_from": "target/debug/agents-collab"}
            self.save()
        if self.result.get("binary") and sha256(self.binary) != self.result["binary"]["sha256"]:
            return self.fail("frozen binary changed during the gate")
        self.result.update(status="passed", finished_at=now())
        self.save()
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scratch", required=True, metavar="DIR",
                        help="new absolute directory to create (parent must exist, outside every Git repository)")
    parser.add_argument("--revision", default="HEAD", metavar="REV", help="commit to snapshot (default HEAD)")
    parser.add_argument("--source", default=str(SOURCE), metavar="DIR", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        check_platform()
        source, scratch, commit, tree = preflight(args.source, args.scratch, args.revision)
        storage = storage_observation(scratch.parent)
    except Refused as exc:
        print(f"check_cli: refused before writing: {exc}", file=sys.stderr)
        return 2
    gate = Gate(source, scratch, commit, tree)
    gate.result["storage"] = storage
    code = gate.run()
    print(json.dumps({"status": gate.result["status"], "failure": gate.result["failure"],
                      "result": str(scratch / "result.json")}, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
