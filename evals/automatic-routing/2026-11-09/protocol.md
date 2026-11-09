# Automatic-routing study protocol

**Status: frozen for public publication before gate execution.**
Independent review and one focused follow-up completed; all three material
findings resolved. See the review record below.
No participant or gate run has been performed. Capability and fixture
preflight observations are recorded separately in `preflight.json`. The protocol becomes binding only when the frozen
package (this file, `tasks.json`, `profile.example.json`, `seeds/` with
computed hashes, the run schedule and the harness commit) is committed
publicly, before any gate or participant outcome exists.

## Question

When the Agents Collab skill is *available* to a fresh lead session, but the
prompt contains only an ordinary engineering ticket, does the lead load the
skill and route work as the profile intends (solo for routine work, delegated
writer plus review for substantial work, independent review for consequential
work), and what happens to correctness, scope and effort compared with the
same lead without the skill? The study is descriptive. Six authored tasks
cannot support general quality, speed or cost claims.

## Materials

- Source: ProcLease public commit
  `37975b5245fcb5cac7b16fac74efd01269dff5d8`, read-only. Each run uses a
  fresh private snapshot built as described in `tasks.json` (`case_setup`):
  identical commit message in every case, no remotes or future refs.
- Tasks: six authored evaluation tickets in `tasks.json`, none of them an
  existing public ProcLease issue. Categories, two tasks each:
  routine small test-only (R1, R2), substantial implementation (S1, S2),
  consequential narrow fix or audit (C1, C2).
- Seeds: `seeds/c1-logs-symlink.seed.patch` (applied to the C1 snapshot) and
  `seeds/c2-proposed-change.input.patch` (C2 audit input, copied outside the
  repository, never applied). Exact, reversible, recorded in
  `seeds/manifest.json`; hashes must be computed before freeze.
- Expected routes are a rubric in `tasks.json`, never part of a prompt.
  Prompts contain no skill, model, role or collaboration wording.
- Benchmark profile: `profile.example.json`. Its agent IDs are experiment
  conditions, not recommended defaults. Requested or accepted model and
  effort are not runtime attestation.

## Conditions

| | A (control) | B (treatment) |
| --- | --- | --- |
| Agents Collab skill | unavailable for this invocation | available for this invocation |
| Everything else | identical | identical |

Held identical: lead CLI and model fixed by the lead at `gpt-6.1-sol` with
`high` reasoning from the currently configured host; task prompt bytes;
snapshot; tool set and permission ceiling; dependency cache and case
environment; time limits; harness version; the per-invocation instruction
that makes the benchmark profile location known (identical neutral wording
in both conditions, delivered through the harness instruction channel, not
the task prompt).

Rules: skill availability is switched per invocation only. No edits to global
settings, installed skills or the owner's current profile; no `HOME` or
`CODEX_HOME` rerooting; no API-key fallback, model substitution or spending
fallback. If no per-invocation mechanism exists for the switch or for the
profile location, that is a preflight blocker. The owner's default profile
remains readable in B; a dispatch matching it rather than the benchmark
profile is recorded as contamination.

## Preflight (lead; blockers, not scores)

1. App-server/CLI schema and RPC behaviour checked from the generated schema;
   per-invocation skill switch and profile-location channel confirmed.
2. Benchmark profile passes `validate_profile.py` (structure only).
3. Access to every required route: lead `gpt-6.1-sol`/high, writer
   `claude-opus-5-5`/high via Claude CLI, reviewer `gpt-6-astra`/high
   native. A required model or transport that is unavailable or refused is a
   preflight blocker: the study stops; it is never scored as task quality or
   as zero usage.
4. Seeds verified per `seeds/manifest.json`; hashes filled in.
5. Base and seeded fixture results recorded. All mutation find strings are unique.
   Before any scored comparison, verify participant-added tests and manually
   grade the remaining declared objective checks. The feature fixtures detect
   missing functionality on base; no reference S1/S2 implementation is supplied.
6. RPC capability probes confirm model/effort observations and per-invocation
   enable/disable controls. `check_materials.py` checks schedule, seed identities,
   prompt separation and receipt parsing without model calls. Child history and
   CLI writer receipt completeness remain per-run observations, never assumed.

## Gate

Before the 36-run study, run condition B once on R1, S1 and C1 (one per
category), fresh sessions, with the frozen package. R1 passes when no writer or reviewer is dispatched; skill loading is measured
but optional for routine solo work. S1 and C1 pass only if receipts show both
skill loading and their expected route: S1 uses the configured writer then
configured independent reviewer; C1 uses the configured independent reviewer.
Exact configured model, transport and accepted high-effort controls are required.
Unknown evidence cannot satisfy a required gate condition. Fresh-history
controls and frozen review packets must also be evidenced; a distinct child ID
alone does not establish no-history review. Claimed
intentions, plans and model self-reports are not receipts. Gate runs are
reported separately and never pooled with study runs.

If any gate case fails, the 36-run study does not start. Record the stop
reason. A separately labelled **explicit-skill diagnostic** may then run the
same three cases in B with one added sentence naming the skill (no model
names, roles or routes). Diagnostic results are never pooled with, or
presented as, implicit-activation results.

## Study design

- 6 tasks x 3 repetitions x 2 conditions = 36 runs, each a fresh lead
  session with fresh child sessions.
- 18 task-repetition pairs. Order within each pair is counterbalanced: 9 pairs
  A-first, 9 B-first, assigned by a seeded shuffle; blocks by repetition
  (all six tasks of repetition 1, then 2, then 3). The schedule and seed are
  committed in `schedule.json` with the frozen package.
- Hard wall-clock stop per run: 60 minutes (profile bounds stay advisory).
  The operator does not intervene except for actions the permission ceiling
  requires; every intervention is logged and counted.
- All participant workspaces, outputs and logs live under the operator
  `--work-root`, outside Git. Only sanitized inputs, harness and results are
  published, after privacy review.

## Execution and receipts

The study-only `run.py` uses Codex app-server JSON-RPC, not a dispatcher added
to the skill. It runs one task per invocation. Python 3.12+ is required for
archive extraction filtering. Example (paths supplied by each operator):

```sh
python3 run.py --work-root "$EVAL_WORK" --source "$PROCLEASE_SOURCE" \
  --toolchain "$RUST_BIN" --cache "$PUBLIC_CARGO_CACHE" \
  --fixture-root "$SHORT_FIXTURES" --task R1 --run-id gate-R1-B --condition B
```

The source must contain the exact public base commit. Build the credential-free
public crates cache once; use a short fixture root outside the repository. The
runner never changes HOME, CODEX_HOME, installed skills or the default profile.
It creates a rendered benchmark profile for each case and delivers its path
through identical developer metadata in A/B. The neutral metadata also forbids
commits, publishing, other checkouts and grader access. C2 gets three rendered
file paths; gate and study prompts otherwise use exact stored bytes. The
explicit diagnostic adds only `Use $agents-collab for this task.`

Full RPC events are temporary private diagnostics. `subAgentActivity` starts
provide actual native dispatch model/effort observations. Successful command
reads containing the skill text establish loading; merely listing skills does
not. Claude command events need CLI process/final receipts to establish actual
model selection. Native child metadata is queried when available; missing
no-history evidence stays unknown. Requests and accepted controls do not attest
internal runtime effort. Observer classification retains event references and
sanitized excerpts; raw transcripts, local paths and private profiles are never
published. The runner sends SIGTERM then checks group survival independently of parent
exit, sends SIGKILL to a surviving owned group, and records whether the group
is absent, still present or unknown. External provider worker cleanup remains
unverified unless separately observed.

`fixtures.py` supplies process-free S1/S2/C1 acceptance probes. Remaining checks
(including mutation/revert tests and human review of scope, README/help and
findings) follow `tasks.json` verbatim. Automated fixture checks alone do not
establish full correctness. Quality is graded separately after routing.

## Measures

Primary:

- actual skill load (receipt);
- routing per dispatch: target agent, transport, model and effort requested,
  model and effort accepted by the interface, fresh session (yes/no/unknown);
- route match against the rubric (solo / writer+review / independent review;
  over- and under-routing recorded separately);
- user or operator interventions;
- correctness: task objective checks and common acceptance;
- regressions: full suite result;
- out-of-scope changes: paths outside `allowed_paths`, dependency or
  repository-history changes.

Secondary: wall-clock task time; summed provider time (reported separately,
never summed into wall clock); commands run; rework (edit cycles after a
failed check, review follow-up rounds); timeouts; usage completeness per
session (known / partial / unknown).

Unknown child usage or cost is recorded as unknown, never zero. External
grader cost and time are recorded separately from participant collaboration.

## Grading

Deterministic checks first (`tasks.json` `objective_checks`, mutants,
fixtures, revert checks). The correctness grader sees the diff against the recorded immutable initial
commit, check outputs, sanitized untracked content and scope/history evidence,
and for C2 the review JSON, not transcripts or condition. The initial commit
and tree IDs are recorded before execution; final HEAD is compared separately.
Deleted/corrupt Git metadata is an evidence error, never an empty passing diff.
Routing is classified from receipts by a separate step that cannot be
condition-blind. Rubric judgments that remain (C2 finding acceptance,
unsupported findings, scope judgments) use the stated `accept_if` text.

Run record contract (one JSON object per planned run, including runs not
started):

```json
{
  "run_id": "R1-rep1-B",
  "task": "R1", "repetition": 1, "condition": "B", "order_in_pair": 1,
  "status": "completed | timeout | permission_failure | harness_error | preflight_blocked | not_started_gate_stop",
  "skill_loaded": {"value": true, "receipt": "<event reference>"},
  "dispatches": [{"role": "writer", "transport": "claude-cli",
    "model_requested": "", "model_accepted": "", "effort_requested": "",
    "effort_accepted": "", "fresh_session": "yes | no | unknown",
    "receipt": "<event reference>"}],
  "route_observed": "solo | writer+review | review-only | writer-only | other",
  "route_expected": "solo",
  "interventions": 0,
  "checks": {"fmt": "pass", "clippy": "pass", "test": "pass",
    "objective": {"<check id>": "pass | fail | not_run"}},
  "out_of_scope_paths": [],
  "wall_clock_s": null, "provider_time_s": null,
  "commands": null, "rework_cycles": null,
  "usage": {"lead": "known | partial | unknown", "children": "known | partial | unknown"},
  "notes": ""
}
```

Timeouts, permission failures and harness errors stay in the data with their
status and are graded on the final state. No planned run is dropped.

## Analysis

Task-level paired summaries: for each task, the 3 A runs versus the 3 B runs
on route match, correctness, regressions, scope and interventions, plus
secondary measures as medians with ranges. Repetitions are not independent
task units; the unit of comparison is the task (n = 6), reported per task and
by category. No significance test is used to support a general effect.

## Limits

- Six authored tasks in one Rust project by one owner; not representative.
- The profile location instruction is visible in both conditions and may cue
  collaboration in A; it is held identical to isolate availability.
- The owner's default profile cannot be hidden without rerooting; misuse is
  detected, not prevented.
- Participants can read the machine; the public study package is outside the
  case directory but readable. Transcript access to it is recorded as
  contamination.
- Interface acceptance of a model or effort is not runtime attestation.
- Fresh child sessions are not filesystem isolation.

## Protocol review record

The draft and study-only harness received an independent Astra review and one
focused follow-up before freeze. The initial findings concerned surviving child
processes, relative symlink-fixture paths and incomplete final Git evidence.
All three were fixed and the seven offline checks passed in the follow-up.
This review did not execute providers or participant tasks and does not approve
any future outcome or product claim. Protocol drafting used an Opus writer;
the lead authored the measurement harness and integrated the corrections.
