# Quality pilot protocol: self-check, independent review and explicit Agents Collab

**Status: frozen before participant work.** No initial draft, review, revision or grading
has run. The protocol becomes binding only after independent review of this
package and the private grader, grader calibration on the base build, a public
commit of this directory with the grader's SHA-256, and a public push. All of
that happens **before any initial draft is generated**. Until then, criteria
may only be made stricter.

This is a separate explicit-invocation study. It does not restart, alter or
replace the [automatic-routing study](../../automatic-routing/2026-11-09/protocol.md),
whose gate failed and whose 36-run comparison stays stopped.

## Question

Given one frozen initial draft per task, does one independent review plus one
revision (B), or the same models coordinated through explicit `$agents-collab`
(C), produce higher-quality final code than the same writer's single
self-check and repair (A)? Is C better than B? Quality means confirmed defects,
missed requirements, regressions, maintainability and real blind-spot catches.
Time and tokens are secondary. The study is descriptive: with six authored
tasks, no general quality, speed or cost claim follows.

## Materials

- Source: ProcLease public commit `37975b5245fcb5cac7b16fac74efd01269dff5d8`,
  read-only. Snapshots follow `tasks.json` `case_setup`.
- Tasks: six new authored tickets (`tasks.json`, Q1-Q6). Each requests a
  feature that is absent at the base commit. None reuses the earlier study's
  tickets or seeds. Allowed paths: `src/`, `tests/`, `README.md`.
- Rubric: `rubric.json` (severity, causal deduplication, blind grading,
  comparison criteria).
- Benchmark profile: `profile.example.json`. Its model IDs record experiment
  conditions; they are not product defaults or recommendations. Requested or
  accepted effort is not runtime attestation.
- Hidden grader: private standard-library Python. Only its SHA-256 is
  published at freeze. The code is published after every output is frozen.
  Every check derives from a numbered public criterion; the check-group to
  criterion map is in `tasks.json`. The grader seeds records with no process
  behind them (keeper PID 0, no guardian), so neither ProcLease nor the grader
  probes or signals a PID copied from disk. Q6 launches only `/usr/bin/true`
  and `pwd -P` under a 30-second lease, waits for them to finish, and stops
  survivors only through ProcLease's own control socket.

## Fixed roles

| Role | Model and effort | Used for |
| --- | --- | --- |
| Lead | `gpt-6.1-sol`, high | Harness operation; A/B/C coordination only |
| Writer | `claude-opus-5-5`, high | Initial draft; A self-check/repair; B and C revision |
| Reviewer | `gpt-6-astra`, high | B and C review |
| Blind grader | `claude-fable-5-1`, high | Grading only; never a participant |

Every call is a fresh session with no transcript inheritance. If an exact
model, effort control, transport or per-invocation skill switch is unavailable,
the study stops before drafting: no fallback model, API-key route or spending
substitute.

## Procedure per task

1. **Initial draft (once).** A fresh writer call, with the skill disabled,
   receives the task prompt plus the frozen stage-control constraints in `run.py`.
   Its hard wall-clock ceiling is 30 minutes. Its final working tree is
   committed once and its tree hash recorded, whatever its quality. No
   selection, reroll, test-based filtering or seeded bug.
2. **Branch.** Three byte-identical copies of the draft commit: A, B and C.
   Each branch has the same permissions, base, task text, draft, benchmark
   profile and a hard 40-minute ceiling from branch start, enforced by a
   subprocess supervisor. At most one review or check and one repair pass;
   no iterative reviewer loop.

| | A: self-check | B: manual independent review | C: explicit Agents Collab |
| --- | --- | --- | --- |
| Skill | disabled per invocation | disabled per invocation | installed skill enabled; prompt invokes `$agents-collab` |
| Calls | one writer call: check and repair (max 28 min) | one reviewer call (target 8 min), then one writer revision (target 20 min) | fresh lead coordinates one reviewer call, then one writer revision |
| Review input | its own draft | task prompt, draft diff, neutral review instructions | whatever the lead's packet provides; draft frozen before review |
| Source writes | writer | writer only | writer only; the lead writes no source |

   The B/C revision fixes only findings it judges justified and may keep the
   draft unchanged after normal checks. In C the review of the frozen draft
   precedes any revision. All leads receive the same benchmark-profile path in common developer
   metadata. A/B receive explicit fixed model assignments in their stage prompt;
   C receives only the skill invocation and resolves those choices from the profile.
3. **Retention.** Every branch, partial edit, timeout and unfinished call is
   kept and graded. The final state is the working tree at completion or at
   the ceiling.

## Preflight (blockers, not scores)

1. Exact model/effort/transport access for all four roles; per-invocation skill
   enable/disable; benchmark profile passes the skill's structural validator.
2. Base snapshot builds offline; fmt, clippy and the full suite pass with the
   case environment.
3. Grader calibration: run each task's grader against the base build in a
   fresh short root, twice. Every check marked `base_expectation: pass` must
   pass and every positive check must fail cleanly (fail, not not_run or
   timeout). Record both runs. A mismatch is fixed before freeze or the check is
   removed and disclosed.
4. Independent review of this package and the grader against the public
   criteria. Record findings and dispositions below.
5. Freeze: commit this directory with the grader SHA-256 and push publicly.

## Grading

Order: build and common acceptance; hidden grader (`--binary --task --root`,
with `--source` for Q6's static check) in a fresh root per state; blind Fable
review of anonymous states; separate non-blind reconciliation of every
self-check and reviewer finding. Details, severities, deduplication and
maintainability anchors are in `rubric.json`. A fatal (unbuildable) state gets
one fatal flag; its downstream checks are not_run, not separate defects.

After freeze a discovered grader defect is documented with its affected check
IDs. The primary frozen analysis marks those checks invalid for every state,
retains original outputs, and reports any impact on the conclusion. A corrected
grader may be applied to every frozen state as an explicitly post-hoc sensitivity
analysis; it never silently replaces the primary grader or changes actor outputs.

## Comparison criteria (frozen with this file)

Per task, score = (fatal + blocker, major, minor) for the final state; lower
wins lexicographically. B over A, C over A and C over B each establish a
quality advantage only if the first branch wins at least 2 of 6 tasks, wins
more tasks than it loses, at least one win includes a validated major or
blocker correction that the other final still has, it introduces no new
blocker, its summed majors do not exceed the other branch's, and all
compared states are complete and gradable. Maintainability breaks ties only
in the descriptive table; it is never a win. If fewer than two initial drafts
have a confirmed major or blocker defect, the result is inconclusive. Failing
the criteria means "no quality advantage established", never equivalence.
Missing access or an ungradable planned state makes the comparison
incomplete or inconclusive. No state is dropped and no usage is recorded as
zero.

## Check supervision and artifact identity

The recorder preserves Git-relevant executable bits and symlink targets in its
source manifest and untracked capture. Grading reconstructs the final tree and
verifies it against that manifest before running acceptance; deletion and
mode-only changes are part of identity. Identical-tree grading therefore uses
source content, executable modes and link targets, not file bytes alone.

`process_guard.py` starts each acceptance command in an owned process group,
terminates surviving group members after completion or timeout, and records the
observed group state. A timeout or unresolved group stops subsequent common
check scheduling and produces an incomplete result, not proof of unbuildability.
Known detached ProcLease jobs are inventoried only within the explicitly owned
fixture root and stopped through their sockets using a trusted pinned-base
binary supplied as `--cleanup-binary`. Simulated seeded records are explicitly
marked and excluded. Deleted metadata or unrelated detached process groups
prevent a universal process-absence guarantee; unresolved known jobs are
reported rather than signalled by copied PIDs.

The hidden grader imports the same frozen supervision module; its source hash
is included in the commitment as well. Symlink target disclosure, refusal and
exit/envelope conformance have distinct severities, and read-only record writes
are blockers consistently across tasks.

## Records

Per state: tree hash, diff, check outputs, defects with unique issue IDs,
transitions from I, maintainability, scope audit. Per branch: calls, wall
clock, provider usage as known/partial/unknown, timeouts, interventions.
Raw transcripts, local paths and private profiles stay private; published
summaries are sanitized.

## Limits

- Six authored tasks in one Rust project by one owner; one draft per task;
  no repetitions. Model nondeterminism is not controlled.
- A uses a fresh same-model self-check, without the initial writer transcript.
  This is a stronger cold-context baseline than continuation of the author session.
- Common profile metadata can cue workflows; A/B/C receive it identically.
- A's single call may combine check and repair; B and C use two calls. Call
  structure therefore differs by design, along with reviewer identity.
- C's packet is built by the skill-led lead; B's uses a fixed neutral template.
  C vs B measures the whole explicit-skill workflow, not packet wording alone.
- The blind grader is a model. Its defects count only with reproduction or conclusive code analysis
  tied to a written criterion and an executable failure scenario. Hidden checks cover only what the fixtures exercise.
- The grader has been calibrated only against the base build. No reference
  implementation exists, so a positive check that misreads a criterion would
  surface only at grading. It would then be handled under the post-freeze rule
  above.
- Participants can read the machine. Observed access to this package or to the private
  grader is recorded as contamination. CLI tool reads are not fully exposed by
  final JSON receipts, so absence of contamination cannot be proved.
- Interface-accepted effort is not runtime attestation; fresh sessions are not
  filesystem isolation.

## Review record

The package and private grader were drafted by an Opus writer; the lead owns
harness, integration, preflight and analysis. Independent Astra initial review
found three material issues: artifact modes/symlink restoration, severity
alignment and descendant cleanup. The fixes passed four offline regressions
and two full base calibrations. The single focused follow-up found a sibling
cleanup-scope regression; its unfinished assessment was interrupted, the exact
case-root correction was frozen, and assessment resumed within the original
allowance. The focused verdict cleared the amended identity with no unresolved
blocking finding. No participant draft or provider task was used in this review.
