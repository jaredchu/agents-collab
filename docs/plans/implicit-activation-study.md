# Implicit-activation study protocol

**DRAFT — 10 November 2026. Not reviewed, not approved, not preregistered.**
No call described here has been made and none may be made yet. Before any lead
or collaborator call, this protocol needs (1) an independent method review,
(2) the owner's explicit execution approval and (3) an immutable public
preregistration commit containing every frozen input listed below. Drafting
it changes no installed skill, product description, profile or global setting,
and it does not claim to solve activation.

## Why

The owner-confirmed product target is that a lead agent uses Agents Collab for
appropriate configured teamwork **without the user naming the skill**. That
target is required; explicit invocation is a supported fallback, not a
substitute. The [9 November routing gate](../../evals/automatic-routing/2026-11-09/report.md)
found ordinary prompts matched 1/3 expected routes: routine solo passed, and
both collaboration routes stayed solo without a skill-read receipt. The separate
explicit diagnostic matched all three. Its 36-row comparison was cancelled under
its gate rule and stays cancelled; this study neither resumes those rows nor
reruns that study to improve its outcome.

Question: on the same tickets, does a description-only change to the skill
make a fresh lead discover the skill and dispatch the configured collaborators
where expected, while staying solo on routine work? This is an activation
diagnostic. It compares no effectiveness, quality, speed or cost. An
effectiveness comparison needs its own protocol and may be proposed only after
an activation gate passes.

## Conditions

Both conditions use the same skill package except one line.

- **Baseline:** the product `skills/agents-collab/` package at the
  preregistration commit. At drafting (commit `aa7b6bc`) its `SKILL.md`
  frontmatter description is:

  > Coordinate configured model collaboration and independent reviews in a
  > Codex-led workflow, separating execution records from durable project
  > knowledge. Use for requested multi-model work, independent review, or an
  > applicable configured collaboration workflow. This draft targets a
  > Codex-led pilot; other leads need adapter validation.

- **Candidate:** the identical package with only the `description:` value
  replaced by this exact text (one line, 607 characters, no model names; the
  quote's line breaks are wrapping only):

  > Use proactively, without being asked, at the start of any coding task that
  > is substantial (sustained multi-file implementation, shared logic or
  > interface changes) or consequential (security, privacy, safety boundaries,
  > data integrity, production behavior, external claims), and whenever
  > multi-model work or independent review is requested. It routes the task
  > through the user's configured collaboration profile, which selects a writer
  > and/or a fresh independent reviewer. Skip it for small routine changes the
  > lead can verify alone. This draft targets a Codex-led pilot; other leads
  > need adapter validation.

The candidate is a study variant only. It is not applied to the product skill,
installed skill or website now. Preflight checks that the two variant trees
differ in exactly that line, that both pass skill metadata validation, and
records both tree hashes. `name`, body, references, scripts and
`agents/openai.yaml` stay byte-identical. If the product package changes before
preregistration, the baseline text and hashes here must be updated and reviewed
again. No other variant, wording or tuning is part of this protocol.

## Materials

- **Tickets:** the original public R1, S1 and C1 tickets from the
  [2026-11-09 routing protocol](../../evals/automatic-routing/2026-11-09/protocol.md),
  using the exact prompt bytes in its [`tasks.json`](../../evals/automatic-routing/2026-11-09/tasks.json)
  (hash recorded in its [frozen manifest](../../evals/automatic-routing/2026-11-09/frozen.json)).
  R1 is the routine solo control; S1 expects the configured writer then the
  configured independent reviewer; C1 expects the configured independent
  reviewer (a writer dispatch is allowed, not required). R2, S2 and C2 are not
  used. Prompts contain no skill, model, role or collaboration wording.
- **Source:** public ProcLease commit
  `37975b5245fcb5cac7b16fac74efd01269dff5d8`, one fresh disposable snapshot per
  run built by that protocol's `case_setup`, with the published C1 seed patch.
- **Profile:** a rendered benchmark profile. Its lead, writer and reviewer
  model, transport and reasoning identities are experimental conditions,
  selected and frozen before preregistration; this draft selects none. They
  are not product defaults: the product's model/profile choice stays
  user-configured. The profile location reaches the lead through the same
  neutral per-invocation instruction in both conditions, as in 2026-11-09.
- **Harness:** a new study-only directory under `evals/` derived from the
  2026-11-09 recorder, adding variant catalogs and launch counting, with
  offline checks. The 2026-11-09 files remain frozen and unchanged.

## Design

3 routes (R1, S1, C1) × 3 repeats × 2 conditions = **18 lead runs**, executed
one at a time (the 2026-11-09 concurrent runs shared machine contention).

Every run uses a fresh lead session (no resumed or forked thread), a fresh
source snapshot and fresh collaborator sessions. Each invocation gets an
invocation-local skill catalog containing **only** its assigned variant,
installed under the name `agents-collab`; no other skill is enabled for it. No
global instruction, installed skill, owner profile, `HOME` or `CODEX_HOME`
changes. If the host cannot provide such a catalog per invocation, that is a
preflight blocker, not a reason to edit global configuration.

Fixed order, generated with Python 3.9.6 by
`random.Random(f"20261110-block-{rep}").shuffle(block)` over each repeat's six
runs listed as R1, S1, C1 × baseline, candidate:

| # | Run | # | Run | # | Run |
| ---: | --- | ---: | --- | ---: | --- |
| 1 | R1-rep1-baseline | 7 | C1-rep2-baseline | 13 | S1-rep3-candidate |
| 2 | S1-rep1-baseline | 8 | S1-rep2-candidate | 14 | C1-rep3-candidate |
| 3 | C1-rep1-baseline | 9 | S1-rep2-baseline | 15 | R1-rep3-candidate |
| 4 | S1-rep1-candidate | 10 | R1-rep2-baseline | 16 | C1-rep3-baseline |
| 5 | R1-rep1-candidate | 11 | C1-rep2-candidate | 17 | R1-rep3-baseline |
| 6 | C1-rep1-candidate | 12 | R1-rep2-candidate | 18 | S1-rep3-baseline |

All 18 runs execute in this order regardless of earlier outcomes: no early
stop, no added runs. No retries, rerolls or condition tuning. A run starts when
the host returns a lead-session identity. A failure before that start (for
example, snapshot construction) may be fixed and the row started once, with the
fix logged, provided no frozen input changes; after start, a row is never rerun.

## Freeze before outcomes

The preregistration commit records, before any run: lead host application/CLI
version, lead model and reasoning request, writer and reviewer identities and
transports, profile bytes, both variant tree hashes, ticket and seed hashes,
the ProcLease commit, OS version, Rust/Cargo, Python and Git versions, harness
commit and offline-check results, the schedule above and preflight receipts.
A change to any of these after preregistration voids the affected runs and
needs a reviewed amendment before further calls.

## Receipts: discovery is not dispatch

Two outcomes are recorded separately for every run:

- **Skill discovery:** a successful read of the variant's `SKILL.md` content in
  the event stream. A catalog listing, plan or self-report is not a receipt.
- **Configured dispatch:** collaborator launch receipts showing the configured
  model, transport and accepted reasoning control, fresh-history evidence and a
  frozen artifact or packet for review. Requested or accepted effort is not
  runtime attestation; a distinct child ID alone does not show a fresh history.

A run may discover the skill and still stay solo, or dispatch without a read.
Each element is `yes`, `no` or `unknown`. Unknown observations are preserved
and are never converted to `no` or `yes`.

## Route criteria and gate rule

Per run, against the frozen benchmark profile:

- **R1 passes** when no writer or reviewer is dispatched. Discovery is recorded
  but not required. Any collaborator dispatch is over-routing and fails.
- **S1 passes** only with a discovery receipt, a configured writer dispatch,
  and then a configured independent reviewer dispatch on the frozen writer
  output, all required elements `yes`.
- **C1 passes** only with a discovery receipt and a configured independent
  reviewer dispatch on the frozen fix before completion, all required elements
  `yes`. A configured writer dispatch is permitted.
- Any required element that is `no` or `unknown`, a non-configured collaborator,
  or exceeding the collaborator bound fails the run. A participant timeout is
  evaluated on its receipts.

**Gate rule:** the candidate passes the activation gate if and only if all nine
candidate runs pass. Any completed candidate run that fails makes the gate
**fail**. If no completed candidate run failed but one or more candidate runs
are access-interrupted, the gate is **incomplete**: neither passed nor a
negative result. Baseline runs are scored by the same criteria and reported
descriptively. If both conditions pass 9/9, activation is observed in both and
nothing is attributed to the description change. A failed candidate leaves
implicit activation unachieved; a different candidate needs a new reviewed
protocol, not a repeat of this one.

## Collaborator bound and interruptions

Each run allows one initial review plus at most one repair/follow-up, matching
`max_followup_rounds: 1`: at most one writer, one initial review, one repair
writer and one follow-up review, so **four collaborator invocations per run**.
The total is at most 72 collaborator invocations plus 18 lead sessions. The
lead under test chooses its own dispatches, so this bound is enforceable only
with host launch supervision that counts native child starts and CLI writer
processes and stops a run before a fifth launch. If the preregistration claims
the bound as required, preflight must validate that supervision; otherwise the
bound is advisory and any excess is a recorded deviation that fails the run.
Each run also has a supervised 60-minute wall-clock stop. No other call, token
or quota budget is imposed; usage is recorded where available and unknown
usage stays unknown, never zero.

A subscription, quota, rate or access interruption is recorded with its
receipts, marks the run `interrupted_access` and **pauses** the schedule. No
run starts until access returns; then the next unstarted row proceeds in order.
The interrupted row is not rerun under this protocol. Any continuation of it
needs a reviewed amendment fixed before the call, stating how preserved partial
observations are treated. The study stays blocked and unfinished meanwhile,
and final results wait until every required stage completes.

## Reporting and limits

Report all 18 rows, including interrupted or failed ones, with discovery and
dispatch shown separately per route and condition, collaborator counts,
interventions, wall time and usage completeness. Never pool these runs with the
2026-11-09 gate or diagnostic, or present an explicit-invocation result as
implicit activation. Final-state checks may be noted for scope safety but are
not graded outcomes.

This is a small diagnostic, not a reliability or efficacy estimate. Three
repeats per cell support no statistics: a lead that succeeds independently with
probability 0.75 per run would still pass 9/9 about 7.5% of the time, and at
0.9 about 39%. One host, one project, three authored tickets and one owner
limit generality. The profile-location instruction may cue collaboration in
both conditions. Description-only means the `SKILL.md` description; other host
discovery signals stay unchanged and untested. Fresh sessions are not
filesystem isolation, and selected sanitized receipts are not fully
independently auditable.

## Review bound for this protocol

Method review is one initial independent review plus at most one focused
follow-up on the changed draft. Unresolved material findings leave the protocol
DRAFT; they do not authorize execution.
