#!/usr/bin/env python3
"""Private hidden grader for the ProcLease quality pilot (2026-11-09).

Standard library only. Every check is derived from the public acceptance
criteria in evals/quality/2026-11-09/tasks.json; no check adds semantics.

    python3 -I grader.py --binary /abs/proclease --task Q1 --root /short/fresh/dir \
        [--source /abs/checkout]
    python3 -I grader.py --list-checks --task Q1

All writes go under --root (created 0700; must be fresh or empty, <= 60 bytes
after resolution so ProcLease socket paths stay below the Unix limit). Seeded
records use keeper_pid 0 and no guardian, so neither ProcLease nor the grader
probes or signals any PID copied from disk. "Running" records are backed by a
grader-owned Unix socket that accepts and closes connections. Only Q6 launches
real jobs: /usr/bin/true and pwd -P under a 30 s lease, then waits for them to
finish and stops (via ProcLease's own socket) anything still active.

Output: one JSON object with per-check status pass | fail | not_run plus
evidence, causal groups, dependency-aware counting hints and a fatal flag.
Evidence may contain fixture paths under --root; sanitize before publishing.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import socket
import stat
import subprocess
import threading
import time
from process_guard import run as supervised_run,cleanup_fixtures
from pathlib import Path

GRADER_VERSION = "2026-11-09.1"
TIMEOUT = 10
HOUR = 3_600_000
MAX_ROOT = 60
ACTIVE = frozenset({"starting", "running", "stopping"})
TERMINAL = frozenset({"stopped", "expired", "exited", "failed", "interrupted"})
STATES = ("starting", "running", "stopping", "stopped", "expired", "exited",
          "failed", "interrupted", "unknown")
LIST_KEYS = {"schema_version", "jobs", "warnings"}
LOG_KEYS = {"schema_version", "id", "lines", "logs_truncated"}
PRUNE_KEYS = {"schema_version", "dry_run", "max_age_hours", "max_finished",
              "deferred", "candidates", "removed", "warnings"}
RUN_KEYS = {"schema_version", "job", "reused"}
REASON = {"exited": "command_exit", "failed": "command_exit", "stopped": "requested",
          "expired": "deadline", "interrupted": "signal", "stopping": "requested"}
SEVERITY_RANK = {"blocker": 3, "major": 2, "minor": 1}


class Fail(Exception):
    """Observed binary behaviour violates the check."""


class NotRun(Exception):
    """The check could not be evaluated (missing input or failed setup)."""


def now_ms():
    return int(time.time() * 1000)


def jid(n):
    return f"{n:012x}"


def J(*numbers):
    return [jid(n) for n in numbers]


def short(value, limit=300):
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


def same(label, got, expected):
    ok = got == expected
    return ok, f"{label}: {'ok' if ok else 'expected ' + short(expected) + ', got ' + short(got)}"


def combine(*parts):
    return all(ok for ok, _ in parts), "; ".join(text for _, text in parts)


# ---------------------------------------------------------------- check specs

def S(cid, group, severity, base, criteria, text, depends_on=None):
    return {"id": cid, "group": group, "severity": severity, "base_expectation": base,
            "criteria": criteria, "depends_on": depends_on, "description": text}


SPECS = {
    "Q1": [
        S("q1.match.all_history", "state-match", "major", "fail", [2, 3],
          "--all --state exited selects exactly the retained exited jobs"),
        S("q1.match.observed_state", "observed-state", "major", "fail", [2],
          "running matches only the reachable running job; a running record without supervisor matches unknown"),
        S("q1.match.repeat_or", "repeat-or", "major", "fail", [1, 2],
          "repeated --state values are ORed; duplicates have no extra effect"),
        S("q1.match.empty", "state-match", "minor", "fail", [2],
          "a valid state with no matching jobs yields an empty jobs array, exit 0"),
        S("q1.enum.accepts_all", "enum", "major", "fail", [1],
          "each of the nine exact state names is accepted"),
        S("q1.window_after_filter", "window-after-filter", "major", "fail", [3],
          "default view shows matching unverified jobs plus the five newest matching recent finished jobs"),
        S("q1.order", "order", "minor", "fail", [4],
          "filtered output keeps the existing rank/creation order"),
        S("q1.warnings", "warnings", "major", "fail", [4],
          "an unreadable record still produces a warning under a filter"),
        S("q1.reject", "validation", "major", "pass", [1],
          "invalid spellings, aliases, empty and comma lists fail nonzero without a job list"),
        S("q1.compat.default", "compat", "major", "pass", [5],
          "unfiltered default list: exact ids, order and envelope"),
        S("q1.compat.all", "compat", "major", "pass", [5],
          "unfiltered list --all: exact ids and order"),
        S("q1.compat.watch", "compat", "minor", "pass", [5],
          "watch --once JSON unchanged"),
        S("q1.human", "human", "major", "fail", [4],
          "human output shows only matching jobs"),
        S("q1.readonly", "read-only", "blocker", "pass", [6],
          "filtered reads leave every job file byte-identical and the endpoint in place"),
    ],
    "Q2": [
        S("q2.head.select", "head-select", "major", "fail", [1, 2],
          "--head 1, 3 and 500 return the first N escaped lines"),
        S("q2.head.short_log", "head-select", "minor", "fail", [1],
          "--head larger than the log returns every line"),
        S("q2.envelope", "envelope", "minor", "fail", [4],
          "JSON keys unchanged with --head"),
        S("q2.truncation", "truncation", "major", "fail", [4],
          "logs_truncated and the human stderr note are preserved with --head"),
        S("q2.escape_human", "escaping", "major", "fail", [1, 4],
          "human --head output escapes terminal controls exactly as --tail does"),
        S("q2.reject.range", "validation", "major", "pass", [2],
          "--head 0, 501, -1 and non-numeric fail without lines"),
        S("q2.reject.conflict", "conflict", "major", "pass", [3],
          "--head with any explicit --tail (including 50) fails without lines"),
        S("q2.compat.tail", "compat", "major", "pass", [3, 4],
          "default last 50 lines and --tail bounds unchanged"),
        S("q2.symlink.head", "symlink-disclosure", "blocker", "pass", [5],
          "--head prints none of a symlink target's bytes"),
        S("q2.symlink.default", "symlink-disclosure", "blocker", "pass", [5],
          "default logs prints none of a symlink target's bytes"),
        S("q2.symlink.head.refusal", "symlink-head-status", "major", "pass", [5],
          "--head returns nonzero promptly for a symlink"),
        S("q2.symlink.default.refusal", "symlink-default-status", "major", "pass", [5],
          "default logs returns nonzero promptly for a symlink"),
        S("q2.symlink.head.error", "symlink-head-status", "minor", "fail", [5],
          "--head symlink refusal has exit1 and the JSON error envelope", depends_on="q2.symlink.head.refusal"),
        S("q2.symlink.default.error", "symlink-default-status", "minor", "pass", [5],
          "default symlink refusal has exit1 and the JSON error envelope", depends_on="q2.symlink.default.refusal"),
    ],
    "Q3": [
        S("q3.live_first", "live-first", "major", "fail", [3],
          "active then unverified groups lead both sorts, by creation then ID"),
        S("q3.order.finished", "finished-order", "major", "fail", [4],
          "finished segment is newest-finish first (ties checked separately)"),
        S("q3.order.created", "created-order", "major", "fail", [4],
          "finished segment is creation ascending (ties checked separately)"),
        S("q3.tiebreak", "tie-break", "minor", "fail", [3, 4],
          "equal sort times are broken by job ID ascending"),
        S("q3.window", "window", "major", "fail", [2],
          "--sort never changes which jobs the default window shows"),
        S("q3.compat", "compat", "major", "pass", [1],
          "without --sort, default and --all sets and rank/creation order unchanged"),
        S("q3.human", "human", "major", "fail", [5],
          "human --all --sort finished prints rows in the JSON order"),
        S("q3.envelope", "envelope", "minor", "fail", [5],
          "JSON envelope and per-job fields unchanged with --sort"),
        S("q3.reject", "validation", "minor", "pass", [2],
          "invalid --sort values fail without a job list"),
        S("q3.watch", "compat", "minor", "pass", [5],
          "watch rejects --sort and its JSON is unchanged"),
        S("q3.readonly", "read-only", "blocker", "pass", [6],
          "sorted reads leave job files byte-identical"),
    ],
    "Q4": [
        S("q4.compat.default_dry", "compat", "major", "pass", [1],
          "prune --dry-run without --keep: only the 24h-old job, max_finished 100"),
        S("q4.dry.selection", "dry-run", "major", "fail", [2, 4],
          "--dry-run --keep 2 lists exactly the old job plus the four oldest collectable jobs"),
        S("q4.dry.no_delete", "dry-run-safety", "blocker", "pass", [4],
          "--dry-run --keep 2 and --keep 0 delete or change nothing"),
        S("q4.keep.count", "keep-count", "major", "fail", [2],
          "--keep 2 removes exactly the expected five and keeps the two newest"),
        S("q4.dry.identical", "dry-real-identity", "major", "fail", [4],
          "dry-run candidates equal the real removal set for the same state"),
        S("q4.keep.zero", "keep-count", "major", "fail", [2],
          "--keep 0 removes every collectable job"),
        S("q4.age_rule", "age-rule", "major", "fail", [2],
          "--keep 100 still removes the job finished more than 24h ago, nothing else"),
        S("q4.protected", "protection", "blocker", "pass", [3],
          "unknown, null-finish, unverifiable-supervisor and stopping jobs survive every prune unchanged"),
        S("q4.not_persistent", "per-invocation", "major", "fail", [5],
          "a later plain prune uses the normal limit", "q4.keep.count"),
        S("q4.deferred.no_delete", "in-progress-protection", "blocker", "pass", [3],
          "while a shared retention lock is held, prune --keep 0 deletes nothing"),
        S("q4.deferred.report", "in-progress-protection", "major", "fail", [3, 4],
          "deferral reported; dry-run under protection lists candidates; release allows collection"),
        S("q4.reject.no_delete", "validation-safety", "blocker", "pass", [1],
          "invalid --keep values delete nothing"),
        S("q4.reject.exit", "validation", "minor", "pass", [1],
          "invalid --keep values fail nonzero without a report"),
        S("q4.envelope", "envelope", "minor", "fail", [6],
          "JSON keys unchanged; max_finished reports N; max_age_hours 24", "q4.keep.count"),
        S("q4.human", "human", "minor", "fail", [6],
          "human dry-run summary line and candidate IDs"),
    ],
    "Q5": [
        S("q5.shape", "shape", "major", "fail", [3],
          "JSON summary has exactly the documented keys and integer counts, no jobs"),
        S("q5.counts.default", "counts", "major", "fail", [1, 2],
          "selected/retained counts for the default window", "q5.shape"),
        S("q5.counts.all", "counts-all", "major", "fail", [2, 6],
          "with --all selected equals retained", "q5.shape"),
        S("q5.human", "human", "major", "fail", [4],
          "exact two stdout lines and stderr warning"),
        S("q5.warnings", "warnings", "major", "fail", [3],
          "unreadable record warning is preserved in summary JSON"),
        S("q5.privacy.env", "privacy-env", "blocker", "pass", [5],
          "no environment value appears in summary output"),
        S("q5.privacy.fields", "privacy-fields", "major", "pass", [5],
          "no per-job field appears in summary output"),
        S("q5.bounded", "bounded", "major", "fail", [5],
          "summary size does not grow with 62 retained jobs", "q5.shape"),
        S("q5.reject.resources", "validation", "minor", "pass", [6],
          "--summary --resources fails nonzero without output"),
        S("q5.compat", "compat", "major", "pass", [6],
          "list without --summary unchanged"),
        S("q5.readonly", "read-only", "blocker", "pass", [1],
          "summary reads leave job files byte-identical and the endpoint in place"),
    ],
    "Q6": [
        S("q6.cwd.absolute", "launch-dir", "major", "fail", [1, 6],
          "absolute --cwd: recorded canonical cwd and the command runs there"),
        S("q6.cwd.relative", "relative-cwd", "major", "fail", [1],
          "relative --cwd resolves against the caller directory"),
        S("q6.cwd.symlink", "canonical", "major", "fail", [1],
          "symlinked --cwd is recorded and used canonically"),
        S("q6.relative_command", "relative-command", "major", "fail", [4],
          "./cmd resolves in the launch directory, not the caller directory"),
        S("q6.validate", "validation", "major", "fail", [2],
          "missing, file and empty --cwd fail before any job directory exists"),
        S("q6.default_unchanged", "compat", "major", "pass", [6],
          "without --cwd: canonical caller cwd, unchanged envelope"),
        S("q6.retry.equivalent", "retry-identity", "major", "fail", [3],
          "inherited D, --cwd D and --cwd link-to-D are the same keyed context"),
        S("q6.retry.mismatch", "retry-mismatch", "blocker", "pass", [3],
          "keyed retry with a different canonical --cwd is rejected without a new job, even from the original caller directory"),
    ],
}


class Checks:
    def __init__(self, specs):
        self.specs = specs
        self.index = {spec["id"]: spec for spec in specs}
        self.results = {}

    def run(self, cid, fn):
        if cid not in self.index or cid in self.results:
            raise RuntimeError(f"undeclared or repeated check {cid}")
        try:
            outcome = fn()
            ok, evidence = outcome if isinstance(outcome, tuple) else (bool(outcome), "")
            self.results[cid] = ("pass" if ok else "fail", evidence)
        except Fail as error:
            self.results[cid] = ("fail", str(error))
        except NotRun as error:
            self.results[cid] = ("not_run", str(error))
        except Exception as error:  # harness problem, never scored as a defect
            self.results[cid] = ("not_run", f"harness error: {type(error).__name__}: {error}")

    def mark_all(self, status, evidence):
        for spec in self.specs:
            self.results.setdefault(spec["id"], (status, evidence))

    def report(self):
        rows = []
        for spec in self.specs:
            status, evidence = self.results.get(spec["id"], ("not_run", "not reached"))
            rows.append({**spec, "status": status, "evidence": short(evidence, 1500)})
        status = {row["id"]: row["status"] for row in rows}
        for row in rows:
            dep = row["depends_on"]
            row["dependent_symptom"] = bool(row["status"] == "fail" and dep and status.get(dep) == "fail")
        groups = {}
        for row in rows:
            group = groups.setdefault(row["group"], {"checks": [], "failed": [], "severity": None})
            group["checks"].append(row["id"])
            if row["status"] == "fail" and not row["dependent_symptom"]:
                group["failed"].append(row["id"])
                if group["severity"] is None or SEVERITY_RANK[row["severity"]] > SEVERITY_RANK[group["severity"]]:
                    group["severity"] = row["severity"]
        for group in groups.values():
            group["status"] = "fail" if group["failed"] else (
                "pass" if all(status[c] == "pass" for c in group["checks"]) else "incomplete")
        counts = {key: sum(1 for row in rows if row["status"] == key) for key in ("pass", "fail", "not_run")}
        return rows, groups, counts


# ------------------------------------------------------------------ fixtures

def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def replace_private(path, data):
    temporary = path.with_name("grader-rewrite.partial")
    write_private(temporary, data)
    os.replace(temporary, path)


def dumps(value):
    return (json.dumps(value) + "\n").encode()


def seed(state, number, st, created, finished=None, *, owner="grader", task=None,
         argv=("/usr/bin/true",), cwd="/", name=None, url=None, error=None,
         reason="default", exit_code="default", log=None, capture=None):
    """Commit launch.json and record.json for a job with no process behind it."""
    ident = jid(number)
    directory = state / ident
    os.mkdir(directory, 0o700)
    os.chmod(directory, 0o700)
    if reason == "default":
        reason = REASON.get(st)
    if exit_code == "default":
        exit_code = 0 if st == "exited" else (1 if st == "failed" and reason == "command_exit" else None)
    expires = now_ms() + HOUR if st in ACTIVE else created + HOUR
    record = dict(schema_version=1, id=ident, argv=list(argv), cwd=cwd, owner=owner, task=task,
                  name=name, url=url, created_at_ms=created, expires_at_ms=expires, state=st,
                  reason=reason, keeper_pid=0, guardian_pid=None, command_pid=None,
                  exit_code=exit_code, finished_at_ms=finished, log_limit_bytes=1_048_576,
                  logs_truncated=False, error=error)
    launch = dict(id=ident, argv=list(argv), cwd=cwd, owner=owner, task=task, name=name, url=url,
                  key=None, fingerprint="v2:" + "0" * 64, created_at_ms=created,
                  expires_at_ms=expires, grace_ms=100, log_limit_bytes=1_048_576)
    write_private(directory / ".quality-simulated-fixture", b"no process behind this record")
    write_private(directory / "launch.json", dumps(launch))
    write_private(directory / "record.json", dumps(record))
    if log is not None:
        write_private(directory / "output.log", log)
    if capture is not None:
        write_private(directory / "capture.status", capture)
    return ident


def malformed(state, number):
    ident = jid(number)
    os.mkdir(state / ident, 0o700)
    os.chmod(state / ident, 0o700)
    write_private(state / ident / "record.json", b"{not json")
    return ident


def refresh(state, relative):
    """Re-anchor recent finish times to now so 30 s windows are not timing-fragile."""
    base = now_ms()
    for ident, offset in relative.items():
        path = state / ident / "record.json"
        record = json.loads(path.read_bytes())
        record["finished_at_ms"] = base - offset
        replace_private(path, dumps(record))


def is_job_name(name):
    return len(name) == 12 and all(c in "0123456789abcdef" for c in name)


def job_dirs(state):
    return {entry.name for entry in state.iterdir() if is_job_name(entry.name)}


def snapshot(state):
    out = {}
    for entry in sorted(state.iterdir()):
        if not is_job_name(entry.name):
            continue
        mode = os.lstat(entry).st_mode
        if not stat.S_ISDIR(mode):
            out[entry.name] = "non-directory"
            continue
        for item in sorted(entry.iterdir()):
            mode = os.lstat(item).st_mode
            key = f"{entry.name}/{item.name}"
            if stat.S_ISREG(mode):
                out[key] = hashlib.sha256(item.read_bytes()).hexdigest()
            elif stat.S_ISSOCK(mode):
                out[key] = "socket"
            elif stat.S_ISLNK(mode):
                out[key] = "link:" + os.readlink(item)
            else:
                out[key] = "other"
    return out


def diff(before, after):
    keys = sorted(set(before) | set(after))
    changed = [k for k in keys if before.get(k) != after.get(k)]
    return changed


class SocketStub:
    """Grader-owned endpoint that keeps a seeded record observably running."""

    def __init__(self, path):
        self.path = path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(path))
        self.sock.listen(64)
        self.sock.settimeout(0.05)
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while not self.stopping.is_set():
            try:
                connection, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            connection.close()

    def close(self):
        self.stopping.set()
        self.thread.join(2)
        self.sock.close()
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass


class Result:
    def __init__(self, label, code, out, err, timed_out):
        self.label, self.code, self.out, self.err, self.timed_out = label, code, out, err, timed_out
        self.text = out.decode("utf-8", "replace")
        self.etext = err.decode("utf-8", "replace")

    def desc(self):
        return f"[{' '.join(self.label)}] exit {self.code}{' (timeout)' if self.timed_out else ''}"

    def json(self):
        if self.timed_out:
            raise Fail(f"{self.desc()}: timed out after {TIMEOUT}s")
        try:
            value = json.loads(self.text)
        except ValueError:
            raise Fail(f"{self.desc()}: stdout not JSON: {short(self.text)} stderr: {short(self.etext)}")
        if not isinstance(value, dict):
            raise Fail(f"{self.desc()}: JSON is not an object")
        return value

    def ok_json(self):
        value = self.json()
        if self.code != 0:
            raise Fail(f"{self.desc()}: {short(self.text)} stderr: {short(self.etext)}")
        return value

    def rejected(self):
        """Nonzero, not a timeout."""
        return self.code not in (0, None) and not self.timed_out


class Context:
    def __init__(self, binary, root, source):
        self.binary, self.root, self.source = binary, root, source
        self.stubs, self.locks, self.launched = [], [], []
        self.cleanup = {}
        self.command_group_states = []

    def state(self, name):
        path = self.root / name
        os.mkdir(path, 0o700)
        os.chmod(path, 0o700)
        return path

    def run(self, state, *args, json_mode=True, cwd=None, extra_env=None, timeout=TIMEOUT):
        env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "COLUMNS": "120", "NO_COLOR": "1",
               "PROCLEASE_HOME": str(state)}
        env.update(extra_env or {})
        argv = [str(self.binary), "--state-dir", str(state), "--color", "never"]
        argv += (["--json"] if json_mode else []) + [str(a) for a in args]
        label = (["--json"] if json_mode else []) + [str(a) for a in args]
        done=supervised_run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=str(cwd or self.root),timeout=timeout)
        self.command_group_states.append(done["owned_process_group"])
        return Result(label,None if done["timed_out"] else done["exit_code"],done["stdout"] or b"",done["stderr"] or b"",done["timed_out"])

    def stub(self, state, ident):
        stub = SocketStub(state / ident / "ctl.sock")
        self.stubs.append(stub)
        return stub

    def close(self):
        for stub in self.stubs:
            stub.close()
        for fd in self.locks:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
        self.locks = []
        self.cleanup['command_groups']={'count':len(self.command_group_states),'all_absent':all(s=='absent' for s in self.command_group_states)}
        trusted=os.environ.get('STUDY_CLEANUP_BINARY')
        self.cleanup['detached_fixture_inventory']=cleanup_fixtures(self.root,Path(trusted)) if trusted else {'observable_cleanup_complete':False,'reason':'trusted cleanup binary not supplied'}


def ids_of(value):
    jobs = value.get("jobs")
    if not isinstance(jobs, list):
        raise Fail(f"no jobs array: {short(value)}")
    return [job.get("id") for job in jobs]


def rank(job):
    if job.get("state") in ACTIVE:
        return 0
    if job.get("state") == "unknown" or job.get("finished_at_ms") is None:
        return 1
    return 2


def grouped(sequence, groups):
    index = 0
    for group in groups:
        if set(sequence[index:index + len(group)]) != set(group):
            return False
        index += len(group)
    return index == len(sequence)


# --------------------------------------------------------------------- tasks

def task_q1(ctx, c):
    st = ctx.state("s")
    base = now_ms()
    recent = {}
    endpoint = ctx.stub(st, seed(st, 0x101, "running", base - 600_000)).path
    seed(st, 0x102, "stopping", base - 590_000)
    seed(st, 0x103, "unknown", base - 580_000)
    seed(st, 0x104, "running", base - 570_000)  # no endpoint: observed unknown
    for i in range(7):
        recent[seed(st, 0x111 + i, "exited", base - 500_000 + i * 1000, base)] = 16_000 - i * 1000
    for i, offset in enumerate((3000, 2000)):
        recent[seed(st, 0x121 + i, "failed", base - 400_000 + i * 1000, base)] = offset
    seed(st, 0x118, "exited", base - 450_000, base - HOUR)
    seed(st, 0x119, "exited", base - 440_000, None)
    seed(st, 0x131, "stopped", base - 300_000, base - 2 * HOUR)
    malformed(st, 0x1ff)
    exited_all = J(*range(0x111, 0x11A))
    default_ids = J(0x101, 0x102, 0x103, 0x104, 0x119, 0x115, 0x116, 0x117, 0x121, 0x122)
    all_ids = J(0x101, 0x102, 0x103, 0x104, 0x119, *range(0x111, 0x119), 0x121, 0x122, 0x131)

    def L(*flags, json_mode=True):
        refresh(st, recent)
        return ctx.run(st, "list", *flags, json_mode=json_mode)

    def ids(*flags):
        return ids_of(L(*flags).ok_json())

    def readonly():
        refresh(st, recent)
        before = snapshot(st)
        for flags in (("--all", "--state", "exited"), ("--state", "running"), ("--all", "--state", "unknown"),
                      ("--all", "--state", "failed", "--state", "stopping")):
            ctx.run(st, "list", *flags)
            ctx.run(st, "list", *flags, json_mode=False)
        changed = diff(before, snapshot(st))
        return combine((not changed, f"changed files: {changed}"),
                       (endpoint.is_socket(), "endpoint present"))

    c.run("q1.readonly", readonly)
    c.run("q1.match.all_history", lambda: same("--all --state exited",
                                                sorted(ids("--all", "--state", "exited")), exited_all))
    c.run("q1.match.observed_state", lambda: combine(
        same("running", sorted(ids("--all", "--state", "running")), J(0x101)),
        same("unknown", sorted(ids("--all", "--state", "unknown")), J(0x103, 0x104))))
    c.run("q1.match.repeat_or", lambda: combine(
        same("stopping|failed", sorted(ids("--all", "--state", "stopping", "--state", "failed")),
             J(0x102, 0x121, 0x122)),
        same("running twice", ids("--all", "--state", "running", "--state", "running"), J(0x101))))
    c.run("q1.match.empty", lambda: combine(
        same("starting", ids("--all", "--state", "starting"), []),
        same("interrupted", ids("--state", "interrupted"), [])))

    def accepts_all():
        bad = []
        for name in STATES:
            r = L("--all", "--state", name)
            try:
                ids_of(r.ok_json())
            except Fail as error:
                bad.append(f"{name}: {error}")
        return not bad, "rejected: " + short(bad) if bad else "all nine accepted"

    c.run("q1.enum.accepts_all", accepts_all)
    c.run("q1.window_after_filter", lambda: same(
        "--state exited (default window)", sorted(ids("--state", "exited")),
        J(0x113, 0x114, 0x115, 0x116, 0x117, 0x119)))
    c.run("q1.order", lambda: same(
        "--all --state unknown --state exited", ids("--all", "--state", "unknown", "--state", "exited"),
        J(0x103, 0x104, 0x119, *range(0x111, 0x119))))

    def warnings():
        bad = []
        for flags in (("--state", "exited"), ("--all", "--state", "running")):
            value = L(*flags).ok_json()
            found = value.get("warnings")
            if not (isinstance(found, list) and any(jid(0x1FF) in str(w) for w in found)):
                bad.append(f"{flags}: warnings {short(found)}")
        return not bad, "; ".join(bad) or "warning for unreadable record present"

    c.run("q1.warnings", warnings)

    def reject():
        bad = []
        for value in ("Running", "RUNNING", "active", "unverified", "", "exited,failed"):
            r = L("--state", value)
            if not r.rejected() or '"jobs"' in r.text:
                bad.append(f"{value!r}: {r.desc()}")
        return not bad, "accepted: " + short(bad) if bad else "all rejected"

    c.run("q1.reject", reject)

    def compat_default():
        value = L().ok_json()
        return combine(same("keys", set(value), LIST_KEYS), same("ids", ids_of(value), default_ids))

    c.run("q1.compat.default", compat_default)
    c.run("q1.compat.all", lambda: same("list --all", ids("--all"), all_ids))

    def watch():
        refresh(st, recent)
        value = ctx.run(st, "watch", "--once").ok_json()
        return combine(same("keys", set(value), LIST_KEYS), same("ids", ids_of(value), default_ids))

    c.run("q1.compat.watch", watch)

    def human():
        r = L("--all", "--state", "exited", json_mode=False)
        missing = [i for i in exited_all if i not in r.text]
        extra = [i for i in J(0x101, 0x103, 0x121, 0x131) if i in r.text]
        return (r.code == 0 and not missing and not extra,
                f"{r.desc()} missing={missing} extra={extra}")

    c.run("q1.human", human)


def task_q2(ctx, c):
    st = ctx.state("s")
    base = now_ms()
    lines = [f"line-{i:03d}" for i in range(1, 601)]
    lines[1] = "line-002 \x1b[31mred\x1b[0m"
    shown = list(lines)
    shown[1] = "line-002 \\u{1b}[31mred\\u{1b}[0m"
    big = seed(st, 0x201, "exited", base - 120_000, base - 60_000,
               log=("\n".join(lines) + "\n").encode())
    small = seed(st, 0x202, "exited", base - 110_000, base - 50_000, log=b"a\nb\nc", capture=b"1")
    link = seed(st, 0x203, "exited", base - 100_000, base - 40_000)
    marker = ctx.root / "marker.txt"
    write_private(marker, b"GRADER-MARKER-Q2\n")
    os.symlink(marker, st / link / "output.log")

    def logs(ident, *flags, json_mode=True):
        return ctx.run(st, "logs", ident, *flags, json_mode=json_mode)

    def got(ident, *flags):
        value = logs(ident, *flags).ok_json()
        if not isinstance(value.get("lines"), list):
            raise Fail(f"no lines array: {short(value)}")
        return value["lines"]

    c.run("q2.head.select", lambda: combine(
        same("--head 3", got(big, "--head", "3"), shown[:3]),
        same("--head 1", got(big, "--head", "1"), shown[:1]),
        same("--head 500 (first/last/len)", (lambda x: (x[:1], x[-1:], len(x)))(got(big, "--head", "500")),
             (shown[:1], shown[499:500], 500))))
    c.run("q2.head.short_log", lambda: same("--head 10 on 3-line log", got(small, "--head", "10"), ["a", "b", "c"]))

    def envelope():
        value = logs(big, "--head", "3").ok_json()
        return combine(same("keys", set(value), LOG_KEYS), same("id", value.get("id"), big),
                       same("logs_truncated", value.get("logs_truncated"), False))

    c.run("q2.envelope", envelope)

    def truncation():
        value = logs(small, "--head", "2").ok_json()
        human = logs(small, "--head", "2", json_mode=False)
        return combine(same("json logs_truncated", value.get("logs_truncated"), True),
                       same("json lines", value.get("lines"), ["a", "b"]),
                       (human.code == 0 and "byte cap" in human.etext, f"human {human.desc()} stderr={short(human.etext)}"))

    c.run("q2.truncation", truncation)

    def escape_human():
        r = logs(big, "--head", "2", json_mode=False)
        expected = ("line-001\n" + shown[1] + "\n").encode()
        return combine((r.code == 0, r.desc()), same("stdout bytes", r.out, expected),
                       (b"\x1b" not in r.out, "no raw ESC"))

    c.run("q2.escape_human", escape_human)

    def reject(cases):
        bad = []
        for flags in cases:
            r = logs(big, *flags)
            if not r.rejected() or '"lines"' in r.text or "line-001" in r.text:
                bad.append(f"{flags}: {r.desc()}")
        return not bad, "accepted: " + short(bad) if bad else "all rejected"

    c.run("q2.reject.range", lambda: reject((("--head", "0"), ("--head", "501"), ("--head", "-1"), ("--head", "x"))))
    c.run("q2.reject.conflict", lambda: reject((("--head", "2", "--tail", "5"), ("--head", "2", "--tail", "50"),
                                                ("--tail", "50", "--head", "2"))))
    c.run("q2.compat.tail", lambda: combine(
        same("default", got(big), shown[-50:]), same("--tail 3", got(big, "--tail", "3"), shown[-3:]),
        reject((("--tail", "0"), ("--tail", "501")))))

    def symlink(flags):
        r=logs(link,*flags);h=logs(link,*flags,json_mode=False)
        privacy=combine((b"GRADER-MARKER" not in r.out+r.err,"JSON target bytes absent"),
                        (b"GRADER-MARKER" not in h.out+h.err,"human target bytes absent"))
        refusal=combine((r.rejected(),f"json {r.desc()}"),(h.rejected(),f"human {h.desc()}"))
        try:envelope="error" in r.json()
        except Fail:envelope=False
        error=combine((r.code==1 and h.code==1,"required exit1 in both modes"),(envelope,"JSON error envelope"))
        return privacy,refusal,error
    for mode,flags in [("head",("--head","5")),("default",())]:
        privacy,refusal,error=symlink(flags)
        c.run("q2.symlink."+mode,lambda value=privacy:value)
        c.run("q2.symlink."+mode+".refusal",lambda value=refusal:value)
        c.run("q2.symlink."+mode+".error",lambda value=error:value)


def task_q3(ctx, c):
    st = ctx.state("s")
    base = now_ms()
    endpoint = ctx.stub(st, seed(st, 0x302, "running", base - 600_000)).path
    seed(st, 0x301, "stopping", base - 590_000)
    seed(st, 0x304, "exited", base - 580_000, None)
    seed(st, 0x303, "unknown", base - 570_000)
    recent = {}
    for number, created, offset in ((0x311, 500_000, 12_000), (0x312, 495_000, 4_000), (0x313, 490_000, 12_000),
                                    (0x314, 485_000, 20_000), (0x316, 475_000, 8_000), (0x317, 475_000, 16_000)):
        recent[seed(st, number, "exited", base - created, base)] = offset
    seed(st, 0x315, "exited", base - 480_000, base - HOUR)
    live = J(0x302, 0x301, 0x304, 0x303)
    window = set(live + J(0x312, 0x316, 0x313, 0x311, 0x317))
    every = set(window | set(J(0x314, 0x315)))

    def L(*flags, json_mode=True):
        refresh(st, recent)
        return ctx.run(st, "list", *flags, json_mode=json_mode)

    def jobs(*flags):
        value = L(*flags).ok_json()
        ids_of(value)
        return value

    def segment(value):
        return [job["id"] for job in value["jobs"] if rank(job) == 2]

    def readonly():
        refresh(st, recent)
        before = snapshot(st)
        for flags in (("--all", "--sort", "finished"), ("--all", "--sort", "created")):
            ctx.run(st, "list", *flags)
            ctx.run(st, "list", *flags, json_mode=False)
        changed = diff(before, snapshot(st))
        return combine((not changed, f"changed files: {changed}"), (endpoint.is_socket(), "endpoint present"))

    c.run("q3.readonly", readonly)

    def live_first():
        parts = []
        for flags in (("--sort", "finished"), ("--all", "--sort", "finished"),
                      ("--sort", "created"), ("--all", "--sort", "created")):
            parts.append(same(" ".join(flags), ids_of(jobs(*flags))[:4], live))
        return combine(*parts)

    c.run("q3.live_first", live_first)

    def order_finished():
        a = segment(jobs("--all", "--sort", "finished"))
        d = segment(jobs("--sort", "finished"))
        return combine((grouped(a, [J(0x312), J(0x316), J(0x311, 0x313), J(0x317), J(0x314), J(0x315)]),
                        f"--all finished segment {a}"),
                       (grouped(d, [J(0x312), J(0x316), J(0x311, 0x313), J(0x317)]), f"default finished segment {d}"))

    c.run("q3.order.finished", order_finished)

    def order_created():
        a = segment(jobs("--all", "--sort", "created"))
        d = segment(jobs("--sort", "created"))
        return combine((grouped(a, [J(0x311), J(0x312), J(0x313), J(0x314), J(0x315), J(0x316, 0x317)]),
                        f"--all created segment {a}"),
                       (grouped(d, [J(0x311), J(0x312), J(0x313), J(0x316, 0x317)]), f"default created segment {d}"))

    c.run("q3.order.created", order_created)

    def tiebreak():
        f = segment(jobs("--all", "--sort", "finished"))
        k = segment(jobs("--all", "--sort", "created"))
        def before(seq, x, y):
            return x in seq and y in seq and seq.index(x) < seq.index(y)
        return combine((before(f, jid(0x311), jid(0x313)), f"finished tie 311<313 in {f}"),
                       (before(k, jid(0x316), jid(0x317)), f"created tie 316<317 in {k}"))

    c.run("q3.tiebreak", tiebreak)
    c.run("q3.window", lambda: combine(
        same("--sort finished set", set(ids_of(jobs("--sort", "finished"))), window),
        same("--sort created set", set(ids_of(jobs("--sort", "created"))), window)))

    def compat():
        parts = []
        for flags, expected in (((), window), (("--all",), every)):
            value = jobs(*flags)
            keys = [(rank(j), j.get("created_at_ms")) for j in value["jobs"]]
            parts += [same(f"{flags} keys", set(value), LIST_KEYS), same(f"{flags} set", set(ids_of(value)), expected),
                      (keys == sorted(keys), f"{flags} rank/creation order {'ok' if keys == sorted(keys) else ids_of(value)}")]
        return combine(*parts)

    c.run("q3.compat", compat)

    def human():
        r = L("--all", "--sort", "finished", json_mode=False)
        if r.code != 0:
            raise Fail(r.desc() + " " + short(r.etext))
        pos = {i: r.text.find(i) for i in every}
        if min(pos.values()) < 0:
            raise Fail(f"ids missing from human output: {[i for i, p in pos.items() if p < 0]}")
        chain = J(0x302, 0x301, 0x304, 0x303, 0x312, 0x316)
        ordered = all(pos[a] < pos[b] for a, b in zip(chain, chain[1:]))
        ties = all(pos[jid(0x316)] < pos[jid(t)] < pos[jid(0x317)] for t in (0x311, 0x313))
        tail = pos[jid(0x317)] < pos[jid(0x314)] < pos[jid(0x315)]
        return ordered and ties and tail, f"positions {sorted(pos, key=pos.get)}"

    c.run("q3.human", human)

    def envelope():
        value = jobs("--all", "--sort", "finished")
        plain = jobs("--all")
        want = {frozenset(j) for j in plain["jobs"]}
        have = {frozenset(j) for j in value["jobs"]}
        return combine(same("envelope", set(value), LIST_KEYS), same("job field sets", have, want))

    c.run("q3.envelope", envelope)

    def reject():
        bad = []
        for value in ("name", "Finished", "", "finished,created"):
            r = L("--sort", value)
            if not r.rejected() or '"jobs"' in r.text:
                bad.append(f"{value!r}: {r.desc()}")
        return not bad, "accepted: " + short(bad) if bad else "all rejected"

    c.run("q3.reject", reject)

    def watch():
        refresh(st, recent)
        r = ctx.run(st, "watch", "--once", "--sort", "finished")
        refresh(st, recent)
        value = ctx.run(st, "watch", "--once").ok_json()
        keys = [(rank(j), j.get("created_at_ms")) for j in value["jobs"]]
        return combine((r.rejected(), f"watch --sort {r.desc()}"), same("watch set", set(ids_of(value)), window),
                       (keys == sorted(keys), "watch order"))

    c.run("q3.watch", watch)


def seed_q4(st, base):
    lf = dict(reason="launch_failed", exit_code=None, error="grader fixture: launch failed")
    collectable = [seed(st, 0x407, "failed", base - 26 * HOUR, base - 25 * HOUR, **lf)]
    collectable += [seed(st, 0x401 + i, "failed", base - 200_000 + i * 1000, base - 70_000 + i * 1000, **lf)
                    for i in range(6)]
    protected = [seed(st, 0x408, "unknown", base - 100_000),
                 seed(st, 0x409, "failed", base - 99_000, None, **lf),
                 seed(st, 0x40A, "exited", base - 98_000, base - 60_000),
                 seed(st, 0x40B, "stopping", base - 97_000)]
    return collectable, protected


def task_q4(ctx, c):
    base = now_ms()
    roots, initial = {}, {}
    for name in "abcdef":
        st = ctx.state(name)
        roots[name] = st
        seed_q4(st, base)
        initial[name] = snapshot(st)
    protected = J(0x408, 0x409, 0x40A, 0x40B)
    collectable = J(0x407, *range(0x401, 0x407))
    keep2 = set(J(0x407, 0x401, 0x402, 0x403, 0x404))
    shared = {}

    def P(name, *flags, json_mode=True):
        return ctx.run(roots[name], "prune", *flags, json_mode=json_mode)

    def present(name, ids):
        return {i for i in ids if (roots[name] / i).is_dir()}

    def default_dry():
        v = P("a", "--dry-run").ok_json()
        return combine(same("candidates", v.get("candidates"), J(0x407)), same("removed", v.get("removed"), []),
                       same("max_finished", v.get("max_finished"), 100), same("deferred", v.get("deferred"), False))

    c.run("q4.compat.default_dry", default_dry)

    def dry_selection():
        v = P("a", "--dry-run", "--keep", "2").ok_json()
        shared["dry"] = v.get("candidates")
        return combine(same("candidates", set(v.get("candidates") or []), keep2), same("removed", v.get("removed"), []))

    c.run("q4.dry.selection", dry_selection)

    def dry_no_delete():
        P("a", "--dry-run", "--keep", "0")
        P("a", "--dry-run", "--keep", "2", json_mode=False)
        changed = diff(initial["a"], snapshot(roots["a"]))
        return not changed, f"changed after dry runs: {changed}"

    c.run("q4.dry.no_delete", dry_no_delete)

    def keep_count():
        v = P("a", "--keep", "2").ok_json()
        shared["real"] = v
        removed = set(v.get("removed") or [])
        return combine(same("removed", removed, keep2), same("gone", present("a", keep2), set()),
                       same("kept newest", present("a", J(0x405, 0x406)), set(J(0x405, 0x406))))

    c.run("q4.keep.count", keep_count)

    def identical():
        if "dry" not in shared or "real" not in shared:
            raise Fail("dry-run or real --keep 2 produced no report")
        return same("dry candidates vs real removed", set(shared["dry"] or []),
                    set(shared["real"].get("removed") or []))

    c.run("q4.dry.identical", identical)

    def envelope():
        if "real" not in shared:
            raise Fail("no --keep 2 report")
        v = shared["real"]
        return combine(same("keys", set(v), PRUNE_KEYS), same("max_finished", v.get("max_finished"), 2),
                       same("max_age_hours", v.get("max_age_hours"), 24))

    c.run("q4.envelope", envelope)

    def not_persistent():
        lf = dict(reason="launch_failed", exit_code=None)
        for i in range(3):
            seed(roots["a"], 0x40C + i, "failed", base - 50_000 + i * 1000, now_ms() - 30_000 + i * 1000, **lf)
        v = P("a", "--dry-run").ok_json()
        return combine(same("candidates", v.get("candidates"), []), same("max_finished", v.get("max_finished"), 100))

    c.run("q4.not_persistent", not_persistent)

    def keep_zero():
        v = P("b", "--keep", "0").ok_json()
        return combine(same("removed", set(v.get("removed") or []), set(collectable)),
                       same("remaining collectable", present("b", collectable), set()))

    c.run("q4.keep.zero", keep_zero)

    def age_rule():
        v = P("c", "--keep", "100").ok_json()
        return combine(same("removed", v.get("removed"), J(0x407)),
                       same("recent kept", present("c", J(*range(0x401, 0x407))), set(J(*range(0x401, 0x407)))))

    c.run("q4.age_rule", age_rule)

    # In-progress retention protection: hold the same shared flock a bulk stop holds.
    guard_path = roots["d"] / ".retention"
    fd = os.open(guard_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    os.fchmod(fd, 0o600)
    ctx.locks.append(fd)
    fcntl.flock(fd, fcntl.LOCK_SH)
    held_real = P("d", "--keep", "0")
    held_dry = P("d", "--dry-run", "--keep", "0")
    held_snapshot = snapshot(roots["d"])

    def deferred_no_delete():
        changed = diff(initial["d"], held_snapshot)
        return not changed, f"{held_real.desc()}; changed while protected: {changed}"

    c.run("q4.deferred.no_delete", deferred_no_delete)
    fcntl.flock(fd, fcntl.LOCK_UN)
    ctx.locks.remove(fd)
    os.close(fd)

    def deferred_report():
        real = held_real.ok_json()
        dry = held_dry.ok_json()
        after = P("d", "--keep", "0").ok_json()
        return combine(same("held deferred", real.get("deferred"), True), same("held removed", real.get("removed"), []),
                       same("held dry deferred", dry.get("deferred"), True),
                       same("held dry candidates", set(dry.get("candidates") or []), set(collectable)),
                       same("released removed", set(after.get("removed") or []), set(collectable)))

    c.run("q4.deferred.report", deferred_report)

    invalid = [P("e", *flags) for flags in (("--keep", "101"), ("--keep", "-1"), ("--keep", "abc"), ("--keep", ""),
                                            ("--keep", "1.5"), ("--dry-run", "--keep", "101"))]

    def reject_no_delete():
        changed = diff(initial["e"], snapshot(roots["e"]))
        return not changed, f"changed after invalid values: {changed}"

    c.run("q4.reject.no_delete", reject_no_delete)
    c.run("q4.reject.exit", lambda: (all(r.rejected() and '"removed"' not in r.text for r in invalid),
                                     "; ".join(r.desc() for r in invalid)))

    def human():
        r = P("f", "--dry-run", "--keep", "2", json_mode=False)
        first = r.text.splitlines()[:1]
        missing = [i for i in keep2 if i not in r.text]
        return combine((r.code == 0, r.desc()), same("first line", first, ["Would remove 5 finished jobs."]),
                       (not missing, f"missing ids {missing}"))

    c.run("q4.human", human)

    def protected_check():
        bad = []
        for name, st in roots.items():
            now = snapshot(st)
            for key, digest in initial[name].items():
                if key.split("/")[0] in protected and now.get(key) != digest:
                    bad.append(f"{name}:{key}")
        return not bad, f"protected files changed or removed: {bad}"

    c.run("q4.protected", protected_check)


def task_q5(ctx, c):
    st = ctx.state("s")
    base = now_ms()
    secret = dict(owner="SECRET-OWNER-Q5", task="SECRET-TASK-Q5", argv=("/usr/bin/true", "SECRET-ARG-Q5"),
                  cwd="/SECRET-CWD-Q5", name="SECRET-NAME-Q5", url="http://127.0.0.1:9/SECRET-URL-Q5")
    endpoint = ctx.stub(st, seed(st, 0x501, "running", base - 600_000, **secret)).path
    seed(st, 0x502, "stopping", base - 590_000, **secret)
    seed(st, 0x503, "unknown", base - 580_000, error="SECRET-ERROR-Q5", **secret)
    seed(st, 0x504, "exited", base - 570_000, None, **secret)
    seed(st, 0x505, "running", base - 560_000, **secret)  # observed unknown
    recent = {}
    for i in range(7):
        recent[seed(st, 0x511 + i, "exited", base - 500_000 + i * 1000, base, **secret)] = 16_000 - i * 1000
    seed(st, 0x518, "exited", base - 450_000, base - HOUR, **secret)
    seed(st, 0x519, "exited", base - 440_000, base - 2 * HOUR, **secret)
    malformed(st, 0x5FF)
    env = {"Q5_SECRET_ENV": "SECRET-ENV-Q5"}
    sel = {"total": 10, "active": 2, "unverified": 3, "finished": 5}
    ret = {"total": 14, "active": 2, "unverified": 3, "finished": 9}
    outputs = []

    def L(*flags, json_mode=True, state=st):
        refresh(st, recent)
        r = ctx.run(state, "list", *flags, json_mode=json_mode, extra_env=env)
        if "--summary" in flags:
            outputs.append(r)
        return r

    def readonly():
        refresh(st, recent)
        before = snapshot(st)
        for flags in (("--summary",), ("--summary", "--all")):
            ctx.run(st, "list", *flags, extra_env=env)
            ctx.run(st, "list", *flags, json_mode=False, extra_env=env)
        changed = diff(before, snapshot(st))
        return combine((not changed, f"changed files: {changed}"), (endpoint.is_socket(), "endpoint present"))

    c.run("q5.readonly", readonly)

    def shape():
        v = L("--summary").ok_json()
        parts = [same("keys", set(v), {"schema_version", "selected", "retained", "warnings"}),
                 same("schema_version", v.get("schema_version"), 1)]
        for key in ("selected", "retained"):
            block = v.get(key)
            ok = isinstance(block, dict) and set(block) == {"total", "active", "unverified", "finished"} and all(
                isinstance(x, int) and not isinstance(x, bool) for x in block.values())
            parts.append((ok, f"{key} block {short(block)}"))
        parts.append((isinstance(v.get("warnings"), list), "warnings array"))
        return combine(*parts)

    c.run("q5.shape", shape)

    def counts_default():
        v = L("--summary").ok_json()
        return combine(same("selected", v.get("selected"), sel), same("retained", v.get("retained"), ret))

    c.run("q5.counts.default", counts_default)

    def counts_all():
        v = L("--summary", "--all").ok_json()
        return combine(same("selected", v.get("selected"), ret), same("retained", v.get("retained"), ret))

    c.run("q5.counts.all", counts_all)

    def human():
        r = L("--summary", json_mode=False)
        expected = ["selected: 10 (active 2, unverified 3, finished 5)",
                    "retained: 14 (active 2, unverified 3, finished 9)"]
        return combine((r.code == 0, r.desc()), same("stdout lines", r.text.splitlines(), expected),
                       ("Warning:" in r.etext and jid(0x5FF) in r.etext, f"stderr {short(r.etext)}"))

    c.run("q5.human", human)

    def warnings():
        v = L("--summary").ok_json()
        found = v.get("warnings")
        return (isinstance(found, list) and any(jid(0x5FF) in str(w) for w in found), f"warnings {short(found)}")

    c.run("q5.warnings", warnings)

    def bounded():
        big = ctx.state("t")
        for i in range(60):
            seed(big, 0x600 + i, "exited", base - 900_000 + i, base - HOUR - i)
        seed(big, 0x6F0, "unknown", base - 800_000)
        seed(big, 0x6F1, "unknown", base - 799_000)
        r = L("--summary", "--all", state=big)
        v = r.ok_json()
        body = {k: v[k] for k in v if k != "warnings"}
        size = len(json.dumps(body))
        return combine((size < 400, f"summary size without warnings {size} bytes"), ("jobs" not in v, "no jobs key"),
                       same("retained total", (v.get("retained") or {}).get("total"), 62))

    c.run("q5.bounded", bounded)

    r = L("--summary", "--resources")
    c.run("q5.reject.resources", lambda: (r.rejected() and '"selected"' not in r.text and '"jobs"' not in r.text,
                                          r.desc()))

    def compat():
        v = L().ok_json()
        a = L("--all").ok_json()
        expected = set(J(0x501, 0x502, 0x503, 0x504, 0x505, *range(0x513, 0x518)))
        return combine(same("keys", set(v), LIST_KEYS), same("default ids", set(ids_of(v)), expected),
                       same("--all count", len(ids_of(a)), 14), same("--all keys", set(a), LIST_KEYS))

    c.run("q5.compat", compat)

    # Collect summary outputs from a fixed set of invocations regardless of earlier failures.
    for flags, mode in ((("--summary",), True), (("--summary",), False), (("--summary", "--all"), True),
                        (("--summary", "--all"), False)):
        L(*flags, json_mode=mode)
    blob = b"".join(x.out + x.err for x in outputs)
    c.run("q5.privacy.env", lambda: (b"SECRET-ENV-Q5" not in blob, f"{len(outputs)} summary outputs scanned"))
    fields = [m for m in (b"SECRET-OWNER", b"SECRET-TASK", b"SECRET-ARG", b"SECRET-CWD", b"SECRET-NAME",
                          b"SECRET-URL", b"SECRET-ERROR") if m in blob]
    c.run("q5.privacy.fields", lambda: (not fields, f"per-job markers found: {[f.decode() for f in fields]}"))


def task_q6(ctx, c):
    st = ctx.state("st")
    work = ctx.state("w")
    d, e, caller = work / "d", work / "e", work / "c"
    for path in (d, e, caller, caller / "sub"):
        os.mkdir(path, 0o700)
    os.symlink("d", work / "link")
    write_private(work / "file", b"not a directory\n")
    os.symlink("/usr/bin/true", d / "rel-true")
    os.symlink("/usr/bin/true", caller / "only-caller")
    canon_d, canon_c = os.path.realpath(d), os.path.realpath(caller)
    canon_sub = os.path.realpath(caller / "sub")
    pwd = next((p for p in ("/bin/pwd", "/usr/bin/pwd") if os.access(p, os.X_OK)), None)

    def launch(cwd, flags, command):
        r = ctx.run(st, "run", "--ttl", "30s", "--grace", "100ms", *flags, "--", *command, cwd=cwd)
        try:
            value = r.json()
        except Fail:
            value = None
        ident = ((value or {}).get("job") or {}).get("id")
        if ident and ident not in ctx.launched:
            ctx.launched.append(ident)
        return r, value, ident

    def wait_terminal(ids, budget=8.0):
        deadline = time.monotonic() + budget
        while True:
            states = {}
            try:
                for job in ctx.run(st, "list", "--all", cwd=caller).json().get("jobs", []):
                    if job.get("id") in ids:
                        states[job["id"]] = job.get("state")
            except Fail:
                pass
            if all(states.get(i) in TERMINAL for i in ids) or time.monotonic() > deadline:
                return states
            time.sleep(0.1)

    def probe(cwd, flags, expected):
        if pwd is None:
            raise NotRun("no pwd executable at /bin/pwd or /usr/bin/pwd")
        r, value, ident = launch(cwd, flags, [pwd, "-P"])
        if r.code != 0 or not ident:
            raise Fail(f"{r.desc()}: {short(r.text)} {short(r.etext)}")
        state = wait_terminal([ident]).get(ident)
        lines = ctx.run(st, "logs", ident, cwd=caller).ok_json().get("lines")
        return combine(same("job.cwd", value["job"].get("cwd"), expected), same("final state", state, "exited"),
                       same("pwd output", lines, [expected]))

    c.run("q6.cwd.absolute", lambda: probe(caller, ["--cwd", str(d)], canon_d))
    c.run("q6.cwd.relative", lambda: probe(caller, ["--cwd", "sub"], canon_sub))
    c.run("q6.cwd.symlink", lambda: probe(caller, ["--cwd", str(work / "link")], canon_d))

    def relative_command():
        r1, _, good = launch(caller, ["--cwd", str(d)], ["./rel-true"])
        r2, _, bad = launch(caller, ["--cwd", str(d)], ["./only-caller"])
        states = wait_terminal([i for i in (good, bad) if i])
        first = (bool(good) and states.get(good) == "exited", f"./rel-true in launch dir: {r1.desc()} {states.get(good)}")
        second = ((bad is None and r2.rejected()) or (bad is not None and states.get(bad) == "failed"),
                  f"./only-caller (caller dir only): {r2.desc()} {states.get(bad)}")
        return combine(first, second)

    c.run("q6.relative_command", relative_command)

    def validate():
        parts = []
        for target, need_json_error in ((str(work / "nope"), True), (str(work / "file"), True), ("", False)):
            before = job_dirs(st)
            r, value, _ = launch(caller, ["--cwd", target], ["/usr/bin/true"])
            after = job_dirs(st)
            ok = r.rejected() and after == before
            if need_json_error:
                ok = ok and r.code == 1 and isinstance(value, dict) and "error" in value
            parts.append((ok, f"{target or 'empty'}: {r.desc()} new dirs {sorted(after - before)}"))
        return combine(*parts)

    c.run("q6.validate", validate)

    def default_unchanged():
        if pwd is None:
            raise NotRun("no pwd executable")
        r, value, ident = launch(caller, [], [pwd, "-P"])
        if r.code != 0 or not ident:
            raise Fail(f"{r.desc()}: {short(r.text)}")
        wait_terminal([ident])
        lines = ctx.run(st, "logs", ident, cwd=caller).ok_json().get("lines")
        return combine(same("keys", set(value), RUN_KEYS), same("reused", value.get("reused"), False),
                       same("job.cwd", value["job"].get("cwd"), canon_c), same("pwd output", lines, [canon_c]))

    c.run("q6.default_unchanged", default_unchanged)

    setup, _, original = launch(d, ["--key", "grader-q6-key"], ["/usr/bin/true"])

    def equivalent():
        if setup.code != 0 or not original:
            raise NotRun(f"keyed setup run from D failed: {setup.desc()} {short(setup.text)}")
        parts = []
        for label, flags in (("--cwd D", ["--cwd", str(d)]), ("--cwd link", ["--cwd", str(work / "link")])):
            r, value, ident = launch(caller, ["--key", "grader-q6-key", *flags], ["/usr/bin/true"])
            parts.append((r.code == 0 and ident == original and (value or {}).get("reused") is True,
                          f"{label}: {r.desc()} id={ident} reused={(value or {}).get('reused')}"))
        return combine(*parts)

    c.run("q6.retry.equivalent", equivalent)

    def mismatch():
        if setup.code != 0 or not original:
            raise NotRun(f"keyed setup run from D failed: {setup.desc()}")
        parts = []
        for label, cwd, flags in (("caller C, --cwd E", caller, ["--cwd", str(e)]),
                                  ("caller D, --cwd E", d, ["--cwd", str(e)]),
                                  ("caller C, inherited", caller, [])):
            before = job_dirs(st)
            r, value, ident = launch(cwd, ["--key", "grader-q6-key", *flags], ["/usr/bin/true"])
            after = job_dirs(st)
            parts.append((r.rejected() and after == before and ident is None,
                          f"{label}: {r.desc()} id={ident} new dirs {sorted(after - before)}"))
        return combine(*parts)

    c.run("q6.retry.mismatch", mismatch)

    # Cleanup of the grader's own jobs: wait, stop survivors via their sockets, report.
    states = wait_terminal(list(ctx.launched)) if ctx.launched else {}
    stopped = []
    for ident in ctx.launched:
        if states.get(ident) not in TERMINAL:
            stopped.append({ident: ctx.run(st, "stop", ident, cwd=caller).desc()})
    if stopped:
        states = wait_terminal(list(ctx.launched), budget=14.0)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and any((st / i / "ctl.sock").exists() for i in ctx.launched):
        time.sleep(0.1)
    ctx.cleanup = {"launched": len(ctx.launched), "final_states": states, "stop_requests": stopped,
                   "sockets_remaining": [i for i in ctx.launched if (st / i / "ctl.sock").exists()],
                   "all_terminal": all(states.get(i) in TERMINAL for i in ctx.launched)}


TASKS = {"Q1": task_q1, "Q2": task_q2, "Q3": task_q3, "Q4": task_q4, "Q5": task_q5, "Q6": task_q6}


# ---------------------------------------------------------------- entrypoint

def prepare_root(root):
    root = Path(root)
    if not root.is_absolute():
        raise ValueError("--root must be absolute")
    if root.is_symlink():
        raise ValueError("--root must not be a symlink")
    if root.exists():
        if not root.is_dir() or any(root.iterdir()):
            raise ValueError("--root must be a fresh path or an empty directory")
    else:
        os.mkdir(root, 0o700)
    os.chmod(root, 0o700)
    if os.lstat(root).st_uid != os.geteuid():
        raise ValueError("--root must be owned by the current user")
    real = Path(os.path.realpath(root))
    if len(str(real).encode()) > MAX_ROOT:
        raise ValueError(f"--root resolves to more than {MAX_ROOT} bytes; choose a shorter path")
    return real


def binary_problem(binary):
    if not binary.is_file() or not os.access(binary, os.X_OK):
        return "binary missing or not executable (unbuildable or not supplied)"
    done=supervised_run([str(binary),"--version"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={"PATH":"/usr/bin:/bin"},timeout=TIMEOUT)
    if done["timed_out"] or done["owned_process_group"]!="absent":return "--version timeout or unresolved process group"
    if done["exit_code"]!=0 or b"proclease" not in (done["stdout"] or b""):
        return f"--version exit {done['exit_code']}: {short((done['stdout'] or b'').decode('utf-8','replace'))}"

    return None


def evaluate(binary, root, task, source=None):
    """Grade one built binary for one task. Returns a JSON-serialisable dict."""
    if task not in TASKS:
        raise ValueError(f"task must be one of {sorted(TASKS)}")
    started = time.monotonic()
    binary = Path(os.path.abspath(binary))
    checks = Checks(SPECS[task])
    result = {"grader_version": GRADER_VERSION, "task": task, "binary_sha256": None, "fatal": False,
              "fatal_evidence": None, "harness_error": None, "cleanup": {}}
    problem = binary_problem(binary)
    if problem:
        if "timeout" in problem:result.update(harness_error=problem)
        else:result.update(fatal=True,fatal_evidence=problem)
        checks.mark_all("not_run",problem)
    else:
        result["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        real_root = prepare_root(root)
        ctx = Context(binary, real_root, Path(source).resolve() if source else None)
        try:
            TASKS[task](ctx, checks)
        except Exception as error:
            result["harness_error"] = f"{type(error).__name__}: {error}"
        finally:
            ctx.close()
            result["cleanup"] = ctx.cleanup
        checks.mark_all("not_run", "harness stopped before this check: " + str(result["harness_error"]))
    rows, groups, counts = checks.report()
    result.update(checks=rows, groups=groups, counts=counts, duration_s=round(time.monotonic() - started, 2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--task", choices=sorted(TASKS), required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--source", type=Path, help="checkout of the graded tree (Q6 static check)")
    parser.add_argument("--list-checks", action="store_true")
    args = parser.parse_args()
    if args.list_checks:
        print(json.dumps(SPECS[args.task], indent=2))
        return 0
    if args.binary is None or args.root is None:
        parser.error("--binary and --root are required unless --list-checks")
    try:
        print(json.dumps(evaluate(args.binary, args.root, args.task, args.source), indent=2, sort_keys=True))
    except (ValueError, OSError) as error:
        print(json.dumps({"task": args.task, "invocation_error": f"{type(error).__name__}: {error}"}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
