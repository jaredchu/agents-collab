# Implicit-activation study protocol

**DRAFT (10 November 2026); execution not approved; inputs not preregistered;
independent method review required before any calls.**
No call described here has been made and none may be made yet. Before any lead
or collaborator call, this protocol needs (1) a passed independent method
review, (2) the owner's explicit execution approval and (3) an immutable public
preregistration commit containing every frozen input listed below. Drafting it
changes no installed skill, product description, profile or global setting,
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
  2026-11-09 recorder, adding variant catalogs and the mandatory launch
  supervisor defined [below](#launch-supervision-and-limits), with offline
  checks. The 2026-11-09 files remain frozen and unchanged.

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
stop, no added runs. No retries, rerolls or condition tuning. Launch identity,
when a row counts as started, and the single permitted dispatch of an unstarted
row are defined under [launch supervision](#launch-supervision-and-limits). A
row whose lead invocation exists is never rerun.

## Freeze before outcomes

The preregistration commit records, before any run: lead host application/CLI
version, lead model and reasoning request, writer and reviewer identities and
transports, profile bytes, both variant tree hashes, ticket and seed hashes,
the ProcLease commit, OS version, Rust/Cargo, Python and Git versions, harness
commit and offline-check results, the launch supervisor's commit, counting and
reconciliation rules and fault-check results, the schedule above and preflight
receipts.
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
- In a completed run, any required element that is `no` or `unknown`, a
  non-configured collaborator, or a collaborator launch request beyond the
  limit fails the run. A participant timeout whose liveness reconciliation
  succeeds is a completed run evaluated on its receipts. Incomplete rows are
  defined under [interruptions](#interruptions-stops-and-liveness) and are not
  scored as route failures.

**Gate rule:** the candidate passes the activation gate if and only if all nine
candidate runs are completed and pass. Any completed candidate run that fails
makes the gate **fail**. If no completed candidate run failed but one or more
candidate runs are incomplete (including access interruption, unknown liveness,
an unresolved launch attempt or a prelaunch stop), the gate is **incomplete**: neither passed nor a
negative result. Baseline runs are scored by the same criteria and reported
descriptively. If both conditions pass 9/9, activation is observed in both and
nothing is attributed to the description change. A failed candidate leaves
implicit activation unachieved; a different candidate needs a new reviewed
protocol, not a repeat of this one.

## Launch supervision and limits

**Lead launches.** Before requesting any lead invocation, the harness durably
records (written and flushed before the request) a launch intent with a unique
launch-attempt identity (row and attempt ordinal), the row's frozen-input
hashes and the intent time. The row's 60-minute deadline is fixed at its first
intent. If an earlier attempt is established as not launched, a later attempt
retains that same deadline. The request carries that identity in a form the supervisor can later
query on the host. A returned lead-session identity binds the attempt to an
existing invocation. A missing, failed or ambiguous acknowledgement makes the
attempt **unknown**; it is never permission to request another invocation.
An unknown attempt is reconciled either to the existing invocation it created,
which then continues as that row under the original deadline and receipts, or
to `not launched`, which needs positive host evidence that no invocation was
created and no process carrying the identity exists. A missing response is not
such evidence. Until one of these holds, no lead is requested for that or any
later row.

A row is **unstarted** only if no lead launch request was issued for it, or
every issued attempt is positively established as not launched. Only an
unstarted row may be dispatched, with a fresh attempt identity. A failure
before any launch request (for example, snapshot construction) may be fixed and
the row dispatched, with the fix logged, provided no frozen input changes. A
row whose invocation exists is never rerun, so each row has at most one lead
session and the study at most 18. Every lead launch attempt and its
reconciliation is reported.

**Collaborator limits (required).** Each row allows at most **four admitted
collaborator launch attempts** (slots reserved before forwarding to the host), and the study
at most **72**. These are
required launch limits enforced before a fifth child starts, not advisory
bounds. They match `max_followup_rounds: 1`: one initial writer, one initial
reviewer, one repair writer and one follow-up reviewer. What counts: every
request by the lead, or by anything it starts, to start a collaborator (native
child agent, CLI writer or reviewer process, or any other model-backed worker)
is recorded, whatever its role, path or outcome. Reserving a slot admits one
attempt; failure, host refusal or a lost acknowledgement still consumes that
slot. A reserved attempt whose forwarding is unknown also consumes its slot;
unknowns are
retained in reporting, never dropped. The lead session is not one of the four.
Roles are classified from receipts for scoring; the limit applies to the total
regardless of role. Neither the harness nor the supervisor makes hidden
transport retries: each launch request is forwarded at most once, and any
re-request by the lead needs a new slot.

The supervisor sits on every native and CLI launch path, keeps one counter per
row across both paths, durably reserves a slot and records the child attempt
identity before forwarding a request, and refuses any request once four are
counted, so no fifth child starts. Concurrent requests are serialized and
cannot share a slot. A refused request beyond four is recorded and fails the
run as exceeding the limit; it is not forwarded or counted as a fifth admitted
attempt. Incoming requests can exceed four: all are reported separately from
the bounded admitted attempts and actual invocations. No other call, token or quota budget is imposed;
usage is recorded where available and unknown usage stays unknown, never zero.

**Mandatory supervisor preflight.** Before preregistration the supervisor must
pass offline fault-injection checks, recorded in the preregistration, covering
at least:

- *lost acknowledgement:* a lead or child launch succeeds but its response is
  lost; the supervisor reconciles to the existing invocation and issues no
  second launch;
- *uncertain launch:* without positive evidence the schedule stays blocked;
  with positive not-launched evidence the row stays unstarted and may be
  dispatched once;
- *racing requests:* concurrent child requests for the last slot, across
  native and CLI paths, grant at most one;
- *blocked fifth launch* on each path, with no child session or process
  created;
- *interruption and timeout liveness:* a surviving lead, native child or CLI
  process group after an interruption or timeout is detected, and unknown
  liveness blocks the next row;
- *receipt reconciliation:* after interrupted transport and recovery, receipts
  bind to the original attempt identities, counts and deadline, none of which
  is reset or extended;
- *supervised wall stop:* at the deadline the lead, native children and CLI
  process groups are stopped and confirmed terminal;
- *no hidden retry:* an injected transport failure produces no second
  forwarded request.

If the host offers no point at which native child starts can be intercepted
before they start, or any check fails or cannot be run, execution is refused.
There is no advisory fallback. A design without these enforced limits would be
a different protocol needing its own review and explicit approval.

## Interruptions, stops and liveness

After any access interruption, transport loss, participant timeout, wall stop
or other stop, and before the next row is dispatched, the supervisor reconciles
every lead, native child and CLI process group the row created or may have
created. Each must be confirmed terminal, or definitely absent with positive
host evidence. Unknown liveness blocks the schedule; no fallback route,
duplicate or new lead may bypass it. Original attempt identities, launch
counts, elapsed allowance, deadline and receipts are preserved through
interrupted transport and recovery; recovery never resets the clock or the
counts.

A subscription, quota, rate or access interruption is recorded with its
receipts, marks the run `interrupted_access` and **pauses** the schedule. No
run starts until access returns and the liveness reconciliation above
succeeds; then the next unstarted row proceeds in order. The interrupted row
is not rerun under this protocol. Any continuation of it needs a reviewed
amendment fixed before the call, stating how preserved partial observations are
treated. The study stays blocked and unfinished meanwhile, and final results
wait until every required stage completes.

A scored row must have a positively identified lead invocation that actually
ran. An attempt proved not launched is not a completed row and cannot pass the
routine-solo control. If its original deadline expires before a lead runs, retain
the row as `incomplete_prelaunch_stop`; it cannot be restarted with a new clock.
Any continuation needs a reviewed amendment before another call.

A row is **completed** when its identified lead and every collaborator are confirmed
terminal or absent (including after a participant timeout or wall stop) and its
receipts are collected; it is then scored under the route criteria, and a
completed row that fails is a **completed route failure**. An
`interrupted_access` row, or a row with unknown liveness or an unresolved
launch attempt, is **incomplete**: it is not a completed route failure merely
because receipts are missing, and its partial observations are preserved.

## Reporting and limits

Report all 18 rows, including incomplete or failed ones, with completed and
incomplete status kept distinct, discovery and dispatch shown separately per
route and condition, lead launch attempts and their reconciliation,
collaborator launch-attempt counts with unknowns retained, interventions, wall
time and usage completeness. Never pool these runs with the
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
