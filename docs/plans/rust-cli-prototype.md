# Local Rust CLI prototype

**Retained original proposal.** The current implementation, commands and limits
are documented in the [CLI guide](../cli.md); the status below summarizes what
was built. The proposal text was originally marked:

> **PROPOSED — 9 November 2026.** This is an implementation proposal, not an
> approved architecture, implemented feature or authorization to run experiments.
> Model and reasoning choices remain external preferences.

## Implementation status (9 November 2026)

The owner subsequently authorized the first local record-and-packet deliverable
and offline fault/concurrency validation, without authorizing live comparisons.
The separate source-only `cli/` crate implements that core; see the
[executable contracts and limits](../cli.md). It uses bundled SQLite with a
versioned enclosing state, immutable objects, revision/idempotency transactions,
and cooperative snapshots. Runtime storage support is deliberately limited to
local APFS on macOS. Interface and imported authority claims remain untrusted
observations; record validation is not proof of their truth.

Offline tests exercise synthetic handoffs, repair, interruption, malformed input,
source identity, conflicts, abrupt process exits and object/storage failures.
Independent review resolved five implementation findings; all 24 offline
integration tests pass. See the canonical [validation status](../cli.md#validation-status)
for review coverage and evidence limits. Process-crash checks do not establish
power-loss guarantees.
Initial-packet replacement/restart, restoration,
independent timing/effort supervisors and other platforms are not implemented;
stronger required timing/attestation and atomic-snapshot guarantees are refused.
The CLI cannot prevent policy evasion through a newly named task or verify a
human's authority from an actor string. No installed skill, profile, website,
model transport or live experiment is changed by this implementation.

The proposal below is retained as the original acceptance scope and rationale;
its future-phase and authorization wording describes the original proposal.
Phase 3 has since run as the separately authorized
[CLI usefulness comparison](../../evals/cli-usefulness/2026-11-09/report.md)
(inconclusive under its frozen rule). An optional skill adapter for local
records now exists; it is not the model/host transport of phase 4. See the
[CLI guide](../cli.md#optional-backend-installation).

## Problem and intended outcome

The prompt-led skill leaves the lead responsible for freezing inputs, tracking
assignments and reconciling reviews. Its configuration helpers cannot enforce
those operations. The [six-task pilot](../../evals/quality/2026-11-09/report.md)
established no added quality advantage over matched manual coordination. Its
recovery exposed incomplete identity checks, ambiguous requirements, formatting
reconciliation and the danger of declaring interrupted work complete.

Build a small local record-and-packet tool to make these handoffs inspectable and
recoverable. Success means preserving requirements and evidence, rejecting stale
reviews, and recovering without duplicate assignments or false completion.
Faster coordination and lower model usage are hypotheses, not promised outcomes.
A server cannot transfer a model's internal context or eliminate necessary
reading. The [routing study](../../evals/automatic-routing/2026-11-09/report.md)
also leaves implicit activation unresolved.

## First deliverable and alternatives

Deliver one locally built Rust binary, provisionally `agents-collab`, with a
versioned record schema, snapshot/packet creation, result import, dispositions,
status and recovery inspection. It neither launches models nor edits source.
The lead continues dispatching through its existing authorized host, then imports
receipts. No installer, background process, automatic routing, profile rewrite,
website change or global configuration belongs in this deliverable.

Propose one SQLite database per private task directory, plus immutable,
content-addressed artifact and packet files. SQLite needs no intermediary server
([official explanation](https://www.sqlite.org/serverless.html)). Keep JSON export
available for inspection and portability; avoid a global task registry initially.

Alternatives remain legitimate: tighten the current templates with a small Python
validator, or use atomic JSON files with an explicit single-writer lock. Both
reduce implementation cost. Rust plus SQLite is justified only if concurrent
updates, typed transitions and recovery are useful enough to outweigh another
binary and schema migrations. Do not translate the experimental harness wholesale
into production code.

## Commands and normal flow

Commands return readable output or stable `--json` envelopes containing IDs,
revision, state, blockers and next permitted operations. Mutations take an
idempotency key and expected task revision; contradictory repeats fail.
Illustrative flow, using explicitly supplied private input files:

```sh
agents-collab task create --spec task.json --profile profile.json
agents-collab artifact freeze TASK --selection selection.json
agents-collab packet seal TASK --artifact ARTIFACT --input packet.json
agents-collab assignment prepare TASK --packet PACKET --spec reviewer.json
# The authorized host dispatches; the CLI itself calls no model.
agents-collab assignment observe ASSIGNMENT --receipt invocation.json
agents-collab review import ASSIGNMENT --result review.json
agents-collab finding resolve FINDING --decision disposition.json
agents-collab task check TASK
agents-collab task complete TASK --evidence completion.json
```

`task show`, `task export` and `task reconcile` expose records and uncertainty.
`packet show` previews exact inputs before sealing. Repeat preparation/import for
each required reviewer. After material fixes, freeze a new artifact and prepare
the permitted follow-up; never overwrite the original packet. `complete` is a
checked transition, not a force flag. Explicit lifecycle commands, including
blocking and cancellation, retain reasons and actor attribution.

## Records, lifecycle and completion

All records have schema version, stable ID, timestamps and provenance. Unknown
observations remain explicitly unknown. The existing
[task-state template](../../skills/agents-collab/assets/task-state.json) informs
the schema but is not already a machine-enforced contract.

| Record | Required content |
| --- | --- |
| Task | Scope revision; verbatim requirements and criteria with source IDs; authority boundaries; resolved writer/reviewers; follow-up limit; state, revision, blockers and next operation |
| Artifact | Kind; base/head; exact selected path inventory, file types, modes, sizes and hashes; symlink targets; deletions; staged/unstaged/untracked provenance; supporting inputs and omissions |
| Packet | Artifact ID; requirement coverage map; instructions and evidence references; access policy; round; immutable common-body hash; separate recipient envelope |
| Assignment | Role and editable scope; packet/round; requested, interface-accepted and observed model/effort separately; boundary observations; timing; invocation identities and states |
| Review | Assignment and artifact/packet hashes; verdict; complete result hash; verification performed and limits; validation status |
| Finding | Source reviews; location or requirement; scenario; evidence/reasoning; uncertainty and materiality; recommendation; disposition, decision authority and evidence |
| Event | Operation ID; actor; previous/new revision; reason; referenced immutable objects; observation time |

Task states are `prepared`, `active`, `blocked`, `completed` or `cancelled`.
Assignment states distinguish `prepared`, `launching`, `running`, `completed`,
`interrupted`, `blocked` and `unknown`; invocation exit and valid task output are
separate facts. Every observation records its age. A stale `running` observation
does not prove that a worker is still alive.

Permit only one registered writer for overlapping editable scope. Follow the
[review protocol](../../skills/agents-collab/references/review-protocol.md): one
initial round plus the configured follow-ups, without resets through renamed
tasks or replacement reviewers. Material changes invalidate old approval; an
unusable old snapshot leaves its unfinished round incomplete, not transferable.

Completion requires complete required results on the appropriate identities,
all material findings resolved or explicitly deferred by authorized authority,
required checks and approvals recorded, and no unresolved active/unknown
invocation. An authorized deferral does not waive an incompatible acceptance
criterion. A zero exit code, reviewer agreement, exhausted round allowance or
subscription interruption cannot satisfy these gates. Schema validation checks
record structure; it cannot establish that evidence is true or a person is
authorized merely because an import says so.

## Snapshot and context contract

Capture selected working-tree bytes, not HEAD alone: preserve staged and
unstaged provenance, included untracked files, deletions, executable modes and
symlink target bytes. Include required surrounding source, tests and lockfiles.
Ignored files require explicit selection; never sweep credentials into a packet.
Record omitted paths and why they are irrelevant. Unsupported special files,
submodules or missing external content block sealing until explicitly represented.

Require coordinated writer quiescence or an immutable input tree during capture.
Copy into staging without modifying the checkout; compare complete inventories
and hashes before and after, then verify the stored copy. Reject detected drift.
Repeated scans alone cannot prove an atomic multi-file view against an external
editor: disclose that limitation and require stronger snapshot facilities where
the task requires them. All reviewers consume the same sealed copy, even if the
live checkout subsequently changes. Restoration validates paths and never writes
through symlinks or follows external targets implicitly.

External inputs need captured bytes and hashes where permitted, otherwise a
revision/URL, retrieval time and explicit mutable/unavailable status. Tests and
services remain environment evidence, not frozen simply because source is hashed.

The lead selects context. Map every requirement and safeguard to supplied text
or an accessible frozen reference; missing coverage blocks sealing. Summaries may
navigate evidence but cannot replace requirements or silently drop exceptions.
Retain source claims, verified observations, interpretations and reviewer opinions
as different categories. Contradictory criteria become open questions, following
the pilot's Q4 lesson; do not manufacture an oracle to settle them.

Diagnose handoff overhead through supplied bytes, repeated source excerpts,
observed file rereads, clarification/repair calls and available provider usage.
Distinguish necessary independent reading from avoidable duplication; neither
source references nor Rust transport transfer internal model memory. Select
writer/reviewer context for its role while preserving the common initial-review
packet. Repeated summarization and ambiguous instructions are candidate causes
of redo work, not established explanations for subscription consumption.

Initial packets exclude writer transcripts, persuasive reports and other reviews.
All required initial reviewers receive the same substantive packet before any
review-driven repair. Only recipient and output destination vary. Fresh sessions,
automatic memory/hooks and tool boundaries are recorded honestly; packet policy
is not filesystem isolation. Results import only against their declared artifact.
Preserve malformed originals; allow a documented deterministic wrapper extraction,
never silent content repair or an automatic model retry.

## Persistence, concurrency and recovery

Store task records under the existing external
`records_root/{project}/{task}/collaboration` convention. Resolve full paths,
including symlinks, and reject repository overlap or traversal before writing.
Read the selected version-1 profile without changing it; snapshot resolved
preferences and their provenance privately. Preserve existing records and require
explicit migration. Unsupported storage or an unavailable required volume blocks
creation; never fall back to another location silently.

Use short SQLite transactions, foreign keys, uniqueness constraints and revision
checks. Concurrent CLI callers serialize mutations; busy/conflict responses are
actionable, not permission to overwrite. Stage files exclusively, flush them,
publish immutable objects atomically on the same filesystem, then commit database
references. A crash may leave an unreferenced object, but must never leave a
committed record pointing at unpublished bytes. Reconciliation verifies hashes
and quarantines incomplete staging; no automatic destructive garbage collection.
Choose and test journaling/durability settings on supported local storage before
claiming crash safety; network-volume compatibility is not assumed.

Persist launch intent before host dispatch and attach its invocation identity
promptly. A crash between those operations produces `unknown`, not a fresh slot.
Reconcile with the host, reattach or wait if running, and retain prior valid
results. Do not redispatch until absence/completion is established. PID alone is
insufficient identity; use available session IDs and process-start evidence.
Idempotent local commands cannot guarantee exactly-once external launch without
host cooperation. Record that gap rather than promising away uncertainty.

## Access, timing and host limits

Honor the existing profile's required/advisory timing semantics: original launch
time and absolute deadline survive interruption and retry; a follow-up is a
separate assignment within the existing round cap. Required timing needs a
validated supervisor before launch; the record-only CLI cannot supply one.
Future supervision uses monotonic elapsed time while alive and persisted UTC
deadlines for recovery; clock discontinuities require reconciliation. Terminating
a local process does not prove remote provider workers stopped.

Subscription, quota, permissions or access exhaustion leaves affected work blocked
and unfinished. Preserve inputs, outputs and failed receipts; wait for restored
access and reconcile before an explicitly authorized continuation. No automatic
repeat, account reset, model substitution, new paid path or deadline reset.

Do not introduce artificial call, token, context or quota budgets for the proposed
usefulness comparison. Experience normal collaboration at the agreed scope;
measure available usage and latency as outcomes. Actual remaining subscription
quota and billed cost stay unknown when unavailable. Token counts, estimates and
configured allowances are not provider quota measurements. Existing profile
bounds remain unchanged. This plan authorizes no live calls or experiments.

An external Rust process cannot automatically invoke tools belonging to the
current desktop assistant session. First integration is export/import operated
by that host. A future adapter must validate actual capabilities, permissions,
fresh-session behavior, effort controls and cancellation. Codex documents a
[JSON-RPC app-server interface](https://learn.chatgpt.com/docs/app-server), but
that is not evidence that every current desktop-native capability is accessible.
Likewise, an optional [MCP stdio interface](https://ts.sdk.modelcontextprotocol.io/v2/serving/stdio)
would expose record operations to a connected host; it would not grant model
access or make the skill activate reliably.

Use private directory/file permissions and minimal receipts. Exclude credentials,
login output and full transcripts. Export only explicitly selected sanitized
records. OS access controls and host permissions remain authoritative; neither
hashes nor a controlled packet provide whole-filesystem isolation.

## Phases and acceptance

1. **Contract and offline core.** Specify JSON schemas, transitions and compatibility
   fixtures; implement the commands above using synthetic records only. Acceptance:
   a complete manual handoff can be imported/exported without lost requirements,
   evidence or unknown states; invalid transitions give precise reasons.
2. **Snapshot and fault hardening.** Test mixed Git state, binary files, modes,
   symlinks, deletions, path collisions/traversal, external-input drift and changing
   capture inputs. Inject crashes around each file/database boundary; simulate
   concurrent imports, duplicate keys, full disks, damaged objects and missing
   volumes. Acceptance: no false completion, overwritten evidence or duplicate
   assignment after recovery. Extend the meaningful cases in the
   [existing harness tests](../../evals/quality/2026-11-09/check_harness.py), without
   treating their passes as proof of a different implementation.
3. **Usefulness assessment, separately authorized.** Predeclare three representative
   handoffs: clean review, dirty artifact with material repair, and interrupted
   review with uncertain invocation. Compare current manual coordination with
   the CLI using the same requirements, artifacts, roles, review coverage and
   completion rules. Assess correctness and recovery first; record operator work,
   latency and available model usage second. No extra model grader is required.
   Preserve every failure and incomplete stage. Do not claim savings from reduced
   work or present a small observation as general effectiveness.
4. **Optional adapters.** Only after the core proves useful, propose one host or
   CLI transport and validate it offline with fake children/events before any
   separately authorized live check. MCP is a separate delivery decision.

For the small comparison, accept usefulness only with no material correctness
regression and a demonstrated reduction in handoff/recovery mistakes or operator
repair work on at least one case. Declare inconclusive when no such difference
appears; retain the simpler workflow. This does not establish statistical parity.

## Decisions still open

Confirm Rust/SQLite versus a smaller helper, supported filesystems/platforms,
snapshot consistency requirements, schema migration policy and the first host
integration before implementation. Main risks are false confidence in imported
evidence, capture races, sensitive data accumulation and maintenance exceeding
the coordination benefit.

A persistent daemon merits a separate proposal only after measured demand for
supervision across client exits, background reconciliation or multi-client event
delivery cannot be served adequately by short-lived CLI calls. It would require
explicit lifecycle, authentication, shutdown and upgrade design. Nothing in the
current evidence requires that service yet.
