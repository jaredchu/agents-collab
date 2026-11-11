# Optional local CLI backend

Use this procedure when `scripts/backend.py status` reports an enabled CLI.
Missing settings select the manual workflow. Backend settings are separate from
the collaboration profile: `~/.config/agents-collab/backend.json` contains only
`version`, `mode` and an absolute `binary` path. Never install or enable it
implicitly. Installation does not edit the profile, shell or project instructions.

Contents: installation, conservative limits, identities, initial cycle,
follow-up round, observations and retries, review contract, dispositions and
completion, partial helper failure.

## Installation

Install a trusted macOS arm64 archive with its expected SHA-256:

```sh
python3 <skill-dir>/scripts/install_backend.py --archive <archive.tar.gz> --sha256 <expected-sha256> --enable
python3 <skill-dir>/scripts/backend.py status
```

The default binary location is `~/.local/bin/agents-collab`; the adapter uses its
absolute path even without a PATH entry. The digest is an integrity check against
the selected archive, not a publisher signature. The engine supports local APFS
on macOS; the current package supports arm64 only.

The installer rejects symlink targets and ancestors. If an approved installation
directory is a symlink, verify its canonical destination and supply that path
explicitly with `--bin-dir`; do not remove the link or relax the guard.

## Conservative limits

Once a task starts, it keeps this backend and record through completion. Where
the CLI is stricter than the manual protocol, report the limit; do not switch the
task to a manual record, rename it or launch extra workers to get around it.

- `start` fixes logical reviewer slots. Completed results cannot be replaced;
  an unfinished interrupted Claude slot may use the explicit continuation below.
- If the profile's `review.on_consequential_work` is `single`, `start` requires a
  reviewer even for work not classified consequential. Include one or report the
  limit. Routine solo work needs no task record at all.
- A sealed initial (`round 0`) review packet cannot be replaced, even before any
  result is recorded. Finish the initial round on it, or block/cancel the task
  and report; a new task does not reset rounds.
- Required timing and `runtime-attestation` are refused at launch intent,
  because the record-only CLI cannot validate a supervisor or runtime effort.
  There is no manual fallback; resolve the requirement before starting.
- `context` renders only selected regular UTF-8 files. Binary, symlink and
  deleted selections need another authorized path. Snapshots are not
  filesystem isolation or frozen external services.

## Identities and arguments

Project names may contain dots, for example `example.com`. They are 1–40 ASCII
characters total, with nonempty dot-separated segments; each segment starts with
a letter or digit and otherwise uses letters, digits, `_` or `-`. Leading,
trailing and consecutive dots are rejected. Task and other IDs retain their
existing letters/digits/underscore/hyphen rules. Dots do not create directories:
the project name is one exact directory component. The configured records root
may resolve through a symlink, but project/task paths beneath it must not contain
symlinks, including dangling links. Both the adapter and CLI must support dotted
projects; updating only the adapter leaves an older CLI unable to create them.

`start` returns `record` (`records_root/{project}/{task}/collaboration`) and
`host`, its private sibling for inputs, outputs, receipts and traces. Pass
`--record` to every later command and keep all `--output`/`--output-destination`
files inside `host/`. `context` returns `artifact` and `packet` hashes; reviewers
must echo both. Assignment IDs are new for every writing or review job; there is
one logical slot per agent and packet. Only the explicit handoff below can link
a replacement execution to an unfinished slot.

Global `--config`, `--profile` and `--actor` precede the subcommand. `--actor`
(default `lead`) is attribution on every mutation and, at `start`, the task's
only declared decision authority. It authenticates no one: naming a person as
actor is not their approval. Real human approvals need actual evidence through
the low-level completion contract below; the helper never infers them.

`--requirement` and `--criterion` take `ID=TEXT` (IDs use letters, digits, `_`,
`-`). `--instructions` is a UTF-8 **file**, not inline text. `--round` is `0` for
initial writing and the initial review; `N` for the repair `writer_context` and
follow-up review after every reviewer finished round `N-1`. The profile's
`max_followup_rounds` supplies the baseline cap for `N`; only an explicit
[task review amendment](#task-review-allowance-amendment) changes the effective
cap. A follow-up review must name a changed artifact.
`<command> --help` shows every flag.

## Initial cycle

```sh
B="python3 <skill-dir>/scripts/backend.py"
$B start --repository "$REPO" --project demo --task guide-fix-1 \
  --writer current-session --reviewer reviewer-a --scope docs/guide.md \
  --requirement "R1=Keep documented commands accurate" \
  --criterion "C1=Unit tests pass" --boundary "No publication" --check unit-tests
# -> {"record": RECORD, "host": HOST, ...}

# Optional recorded writing; skip when the change already exists.
$B context --record "$RECORD" --purpose writer_context --round 0 \
  --paths docs/guide.md --omit-other-paths "Unrelated to this edit" \
  --quiescence "No writer active" --instructions "$HOST/write.txt" \
  --output "$HOST/write-context.txt"            # -> packet WRITER_PACKET
$B assignment --record "$RECORD" --id write-1 --packet "$WRITER_PACKET" \
  --agent current-session --role writer --output-destination "$HOST/write-1.txt"
# Launch only after assignment succeeds, then attach the real invocation:
$B observe --record "$RECORD" --assignment write-1 --state completed \
  --invocation "$SESSION" --boundary-observations "Lead session; no isolation"

# Initial review on the finished source (neutral instructions only).
$B context --record "$RECORD" --purpose review --round 0 --paths docs/guide.md \
  --omit-other-paths "Unrelated to this edit" --quiescence "Writer stopped" \
  --instructions "$HOST/review.txt" --output "$HOST/review-0.txt"   # -> ARTIFACT, PACKET
$B assignment --record "$RECORD" --id review-1 --packet "$PACKET" \
  --agent reviewer-a --role reviewer --output-destination "$HOST/review-1.json"
# Dispatch a fresh reviewer with review-0.txt, then:
$B observe --record "$RECORD" --assignment review-1 --state completed \
  --invocation "$REVIEW_SESSION" --exit-code 0 \
  --boundary-observations "Fresh CLI process; tools disabled; memory may load"
$B import-review --record "$RECORD" --input "$HOST/review-1.json"
```

Writer context consumes no review round. Keep initial review packets neutral: no
writer transcript, persuasive report or other initial findings. Select enough
source for adequate context; a diff alone is not enough, and no implicit file
sweep is authorized. `--omit-other-paths` gives one reason for all unselected
inventory.

## Follow-up round

After every required reviewer has a recorded result on the current packet:

```sh
$B context --record "$RECORD" --purpose writer_context --round 1 ... \
  --output "$HOST/fix-context.txt"              # -> FIX_PACKET
$B assignment --record "$RECORD" --id fix-1 --packet "$FIX_PACKET" \
  --agent current-session --role writer --output-destination "$HOST/fix-1.txt"
# Write the fix, observe fix-1 completed, then freeze the changed source:
$B context --record "$RECORD" --purpose review --round 1 ... \
  --output "$HOST/review-r1.txt"                # -> new ARTIFACT, PACKET
$B assignment --record "$RECORD" --id review-2 --packet "$PACKET" \
  --agent reviewer-a --role reviewer --output-destination "$HOST/review-2.json"
```

`...` repeats the same `--paths`, `--omit-other-paths`, `--quiescence` and
`--instructions` choices. The fix is a new assignment; see
[assignment timing](configuration.md#assignment-timing). A follow-up packet may
include prior findings, labeled as follow-up input.

## Task review allowance amendment

At the cap, report unresolved issues and keep the task blocked by default. Only
an explicit owner-authorized task amendment can add exactly one follow-up round.
Never extend automatically, reset round numbers, rename the task or relabel its
scope to bypass the ceiling. This operation grants no review pass,
implementation, release, waiver or policy approval.

Retain the actual owner decision as evidence first (`evidence --input FILE`),
then provide explicit JSON using the latest **review** packet identity and the
current effective limit reported by `show`:

```json
{
  "packet": "LATEST_REVIEW_PACKET_HASH",
  "previous_limit": 1,
  "new_limit": 2,
  "authority": "lead",
  "decision_evidence": ["REGISTERED_OWNER_DECISION_OBJECT_HASH"],
  "reason": "Owner explicitly permits one further review to resolve the retained capped findings."
}
```

```sh
$B --actor lead extend-review --record "$RECORD" --input "$HOST/extension.json"
```

The low-level command is `task extend-review` with the ordinary `--actor`,
`--key`, `--expect` and `--input` mutation arguments. `authority` must be a
`spec.decision_authorities` identity and equal `--actor`. The engine checks
nonempty registered `decision_evidence` references and a nonempty reason;
these are host declarations, not human authentication or proof of consent.
The host must retain a concrete decision and verify its scope.

The latest reviewed round must be complete for every fixed reviewer and equal
the effective cap. Every invocation must be terminal; completed/cancelled tasks
refuse amendments. A stale packet, stale previous limit or any increase other
than exactly one fails. Normal CAS and idempotency rules apply. The helper
retains one operation receipt and never retries a conflict automatically.

`show` reports `baseline_review_limit`, `effective_review_limit` and the retained
`review_extensions`. The engine derives the effective ceiling from append-only
amendments while preserving the frozen profile/hash, requirements, approvals,
safeguards, reviewer set and all earlier assignments, deadlines and results.
After extension use the next sequential round, changed source and fresh review
through the ordinary workflow. Existing completion gates still apply.

The first amendment upgrades SQL marker and state body to **format 3** in the
same transaction, so older CLIs refuse it before interpreting the new allowance.
A later quota handoff preserves format 3. This engine also reads unchanged
format-1/2 records. No saved profile or backend selector is written.

## Quota-aware continuation

The host owns quota diagnosis, the user prompt and actual dispatch. If the Codex
lead lacks quota, checkpoint and stop; do not promote Claude. For an unavailable
Claude collaborator, retain the packet, partial outputs and failed receipt and
present **Wait for Claude / Continue with an available configured Codex model**.
Waiting leaves the stage interrupted. Never silently substitute, use another
account or select a paid access path. Required named models or diversity still
need an explicit authorized amendment; a preference permits same-model fresh
review. A frozen experiment remains interrupted/amended or gets a separately
labelled continuation, never an original matched result.

1. Reconcile the original invocation with the host/supervisor. If absence is
   unknown, stop. Record `observe --state interrupted --invocation OLD_SESSION
   --reconciled --absence-established --reason "Actual absence evidence"` with
   the actual boundary observations. Preserve prior receipts and partial results.
2. Retain the explicit owner/user decision (quote or receipt, chosen available
   Codex identity/model/reasoning, reason, access check, condition amendment if
   needed) in a private UTF-8 file. Use `evidence --input FILE` to get its object
   hash. This retains evidence; it authenticates no human and proves no liveness.
   The engine requires nonempty references to registered objects, but does not
   check their type or whether their content records that decision. The host
   must supply actual decision evidence; an unrelated artifact hash can pass
   the structural reference check without establishing consent.
3. Prepare the handoff JSON below. `authority` must equal the acting declared
   decision authority (`lead` by default). `agent` is the execution identity;
   choose an existing frozen-profile Codex entry with `selection: null`, or a
   **new** task-local identity with explicit `selection`. The latter never
   rewrites saved defaults, the frozen profile or an existing alias. Each new
   task-local identity is unique; another handoff must not redefine it. Use a
   distinct output destination to preserve every original partial result.
4. Run `$B handoff --record "$RECORD" --input "$HOST/handoff.json"`. This is a
   single CAS mutation and records a new assignment ID linked to the old logical
   slot, original requested model, exact packet/artifact, evidence and timing.
   Inspect `show` after any uncertain response; never repeat the whole workflow
   blindly. The old assignment becomes `superseded` and cannot resume or import
   a second result. A race loses through CAS or the already-used slot.
5. Record `observe --assignment NEW_ID --state launching` before dispatch. Use a
   fresh invocation with the chosen model/effort and attach its real identity.
   A reviewer receives the same neutral frozen packet and no writer transcript;
   it must not reuse the writer's or original reviewer's session. Its review
   `fresh_session` must equal the completed invocation string exactly, with no
   explanatory prefix or suffix. Put boundary observations in `limits` or
   `tool_boundary`. The backend checks retained identities, not actual context
   isolation.

Example reviewer handoff (replace symbolic hashes and paths with actual values):

```json
{
  "assignment": "review-1", "replacement": "review-1-continuation",
  "packet": "PACKET", "agent": "continuation-reviewer",
  "selection": {"model": "codex-model-id", "transport": "codex-native", "reasoning": "inherit"},
  "output_destination": "HOST/review-1-continuation.json",
  "decision": "continue_with_codex", "authority": "lead",
  "decision_evidence": ["DECISION_OBJECT"],
  "reason": "Owner explicitly chose available Codex after quota interruption",
  "previous_invocation": "OLD_SESSION", "timing": "preserve_deadline",
  "instructions": "Fresh review of the same neutral frozen packet; no writer transcript; report actual model and context limits",
  "partial_work": null
}
```

For a writer, `instructions` must say this is a continuation using **current
partial source**, not fresh writing from an old snapshot. Supply `partial_work`
as the existing artifact-selection contract, for example:

```json
{
  "paths": ["source.txt"], "omissions": {"other.txt": "Outside this task"},
  "acknowledged_sensitive": [], "quiescence": "Original invocation absent; source quiescent",
  "atomic_required": false, "base": "HEAD"
}
```

Select every Git inventory path within each editable scope, including tracked
deletions and newly created partial files. Directory scopes cover descendants;
a future path need not exist yet. Omitting any scoped inventory fails. Existing
exact scoped inputs must be selected even if ignored by Git. Ignored descendants
of a directory scope are outside inventory: the host must explicitly select any
such partial inputs; this helper does not discover them or prove their absence.
The engine snapshots that partial work into immutable objects without changing
the current artifact or restoring files;
retain any other partial outputs as well. Give the writer the snapshot reference,
current working source and retained continuation instructions. A reviewer must
have `partial_work: null`; do not attach writer continuation material to its packet.

Only `interrupted`, incomplete Claude assignments qualify. A completed valid
`pass` or `changes_required` review cannot be superseded; blocked/invalid receipts
stay retained. Replacement fills the same unfinished slot and consumes no new
review round or repair allowance. `spec.agent` is the original **logical slot**;
`requested` and `continuation.handoff.agent` identify the actual replacement.
The only supported timing treatment is explicit `preserve_deadline`: original
deadline, retry timing and review cap stay unchanged. Required timing still
blocks because this engine cannot validate a supervisor. An advisory overrun is
reported and is not a stop condition on its own.

The first handoff explicitly upgrades the task's SQL and enclosing state format
to **2** in the same transaction (or retains format 3 after a review amendment).
Ordinary records remain format 1; this CLI reads formats 1–3. Older CLIs refuse
unsupported formats before interpreting them. Keep using a compatible
binary; no downgrade or automatic backend switch is supported. No quota API,
dispatcher, GUI prompt, absence detection or authority attestation is provided.

## Observations and retries

`assignment` prepares the assignment, then records `launching` intent with no
invocation. Dispatch only after both steps commit. `observe` then attaches what
the host actually saw. Record interface model/effort separately; runtime
attestation stays unknown. Omit `--exit-code` when a native host exposes none;
an exit code alone proves no valid review. The backend never cancels a worker.

`--reconciled` and `--absence-established` default to false and are recorded
host assertions, not proof. Use them only after checking the host or
supervisor, and give that evidence in `--reason`. The engine requires
`--reconciled` to change an `unknown`, `interrupted`, `blocked` or `completed`
assignment, and both flags to attach a different invocation identity. The
helper rejects contradictory flags (absence without reconciliation, either flag
without a reason, launching with an invocation) before writing anything; the
engine's own refusals leave the record unchanged. `--process-start` is optional
supporting evidence.

### Retrying an assignment

A retry keeps the same assignment ID, packet, original target and deadline; it
gets no fresh deadline, cap or assignment ID. The record-only CLI cannot record a
second launch intent and does not prove that a worker is gone. Without host
bookkeeping or a supervisor that can do both steps below, do not relaunch: the
retry stays blocked.

1. Record the old state, for example `$B observe --record "$RECORD"
   --assignment write-1 --state interrupted --invocation session-a
   --boundary-observations "Lead session; no isolation"`.
2. Establish from the host or supervisor that `session-a` is actually gone. If
   that is not possible, do not relaunch. Reattach, wait or report the assignment
   as uncertain.
3. **Before spawning anything**, durably create a new pending-attempt record
   under `$HOST/retries/`. Number labels in sequence (`write-1.attempt-2`,
   `write-1.attempt-3`, ...). Never reuse or overwrite an earlier attempt file.
4. Launch. Then promptly record the actual new invocation in a
   `<label>.launched.json` file (same exclusive creation) **and** with `observe`.

Pending attempt `$HOST/retries/write-1.attempt-2.json` (times are Unix UTC
seconds, deadline values copied from `show`):

```json
{
  "kind": "agents-collab-retry-intent",
  "attempt": "write-1.attempt-2",
  "assignment": "write-1",
  "packet": "WRITER_PACKET",
  "agent": "current-session",
  "original_target": "advisory 30 minutes",
  "original_deadline": 1794220200,
  "previous_invocation": "session-a",
  "previous_absence_evidence": "Supervisor log: session-a exited 1794218950; process list empty at 1794219010",
  "state": "launching",
  "new_invocation": null,
  "created_at": 1794219020
}
```

The file is private host bookkeeping. It is not an engine receipt and does not
show whether a worker is alive. A private copy of the skill's
`assets/task-state.json` invocation entry may hold the same fields instead. Write
the draft JSON to a file `$DRAFT` inside the private `$HOST/` but outside
`$HOST/retries/`, then create the attempt file. Creation rejects invalid JSON,
fails if the label already exists and syncs the file before you launch:

```sh
mkdir -p "$HOST/retries"
python3 -c 'import json,os,sys
d=open(sys.argv[1],"rb").read(); json.loads(d)
f=os.open(sys.argv[2],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
os.write(f,d); os.fsync(f); os.close(f)
g=os.open(os.path.dirname(sys.argv[2]),os.O_RDONLY); os.fsync(g); os.close(g)' \
  "$DRAFT" "$HOST/retries/write-1.attempt-2.json"
```

Use the same command to create `write-1.attempt-2.launched.json`, for example
`{"attempt":"write-1.attempt-2","state":"running","new_invocation":"session-b","observed_at":1794219040}`.
Only after both steps, attach the replacement:

```sh
$B observe --record "$RECORD" --assignment write-1 --state running \
  --invocation session-b --reconciled --absence-established \
  --reason "Attempt write-1.attempt-2: supervisor log and process list show session-a exited before relaunch" \
  --boundary-observations "Lead session; no isolation"
```

**On resume**, an attempt file without a matching `.launched.json` is a pending
intent. Before any new worker starts, check the host or supervisor for that
attempt. If it launched, record its invocation as in step 4. If it definitely did
not launch, create `<label>.not-launched.json` with that evidence. Then a later
attempt, under the next label, may begin at step 2. If you cannot tell whether it
launched, start nothing. Report the uncertainty and block the task
(`command --entity task --action block`); never risk a duplicate worker.
A `<label>.launched.json` whose invocation `show` does not list means step 4's
`observe` did not commit. Reconcile the actual host or process, then attach that
invocation with its actually observed state and the step 4 flags and reason;
launch nothing. Unknown liveness still blocks any further launch.
`observe --state launching` only re-records missing intent for a still-prepared
assignment.

## Review contract

Copy this contract, with identity placeholders, into the review instructions
before sealing the packet. At dispatch, supply the actual artifact/packet hashes
returned by `context` and the prepared assignment ID; do not edit a sealed packet
to insert its own hash. The helper renders the supplied instructions and sources;
it does not automatically add a return schema. The reviewer returns only this
JSON, without prose or fences:

```json
{
  "schema_version": 1,
  "assignment": "ASSIGNMENT_ID",
  "artifact": "ARTIFACT_HASH",
  "packet": "PACKET_HASH",
  "verdict": "pass",
  "verification": [{"category":"reviewer_opinion","description":"What was inspected","object":"ARTIFACT_HASH"}],
  "limits": "Checks not run and limits of supplied evidence",
  "findings": [],
  "fresh_session": "Observed session boundary or uncertainty",
  "automatic_context": "Observed instructions, memory, hooks and plugins",
  "tool_boundary": "Actual available tools and source-write restriction"
}
```

All shown top-level fields are required and extra fields are refused.
`schema_version` is integer `1`; `verification` is a nonempty array and `findings`
is an array. `limits`, `fresh_session`, `automatic_context` and `tool_boundary`
are nonempty **strings**, never lists. Each verification item has exactly the
string fields `category`, `description` and `object`; its object must be a
registered evidence hash, not an invented test-output hash.

For an ordinary assignment, `fresh_session` describes the session boundary or
uncertainty. For a quota-continuation assignment, replace it with the **exact
completed invocation string**, with no surrounding explanation. Record the
session-boundary narrative in `limits` or `tool_boundary` instead.

Verdicts are `pass`, `changes_required` or `blocked`. Verification categories are
`source_claim`, `verified_observation`, `interpretation`, `reviewer_opinion`,
`unknown` and `unavailable`. Each finding has nonempty `id`, `location`,
`scenario`, `evidence`, `uncertainty` and `recommendation`, plus boolean
`material`. Finding IDs stay unique across rounds; a pass cannot contain material
findings. The assignment must first be observed `completed`.

`import-review` retains original bytes and exits 1 unless `valid_review` is true
(`validation: "valid_structure_only"`); rejected or incomplete results stay as
evidence. Disclose any explicit host adaptation; do not silently rewrite a result
to make it valid. Structural validity attests neither truth nor authority.

## Dispositions and completion

`evidence --input FILE` retains actual UTF-8 check output or disposition text and
returns its object hash (`EVIDENCE_HASH`). A stored assertion alone does not prove
that a check ran. The helper stores the text as the reason of a `task reconcile`
mutation, so the call is also a reconciliation: incomplete files in the record's
`staging/` move to `quarantine/` (listed as `quarantined` in the result; nothing
is deleted). Because reconcile would turn an unattached launch intent into
`unknown`, `evidence` refuses while any assignment is still `launching`; attach
the launched invocation with `observe` first. Record each finding decision
through the generic command with this `disposition.json`:

```json
{"finding":"F1","decision":"addressed","reason":"Follow-up review of the changed artifact passed","evidence":["EVIDENCE_HASH"],"authority":"lead","criterion_compatible":true}
```

```sh
$B command --record "$RECORD" --entity finding --action resolve --input "$HOST/disposition.json"
$B complete --record "$RECORD" --evidence "$EVIDENCE_HASH" --reason "Criteria and checks covered"
```

Decisions are `addressed`, `rejected`, `deferred` or `unresolved`; `authority`
must equal `--actor`. Addressed material findings need a changed artifact and a
passing follow-up; rejections need evidence. `complete` maps the evidence to every
declared criterion and check. Tasks with `--approval` need the low-level contract
via `command --entity task --action complete` and an input such as
`{"artifact":"ARTIFACT_HASH","criteria":{"C1":["EVIDENCE_HASH"]},"checks":{"unit-tests":["EVIDENCE_HASH"]},"approvals":{"owner":["APPROVAL_EVIDENCE_HASH"]},"reason":"..."}`,
where the approval object contains the person's actual approval.

Completion follows verdicts, not dispositions. The latest review packet must name
the current artifact, and every required reviewer's result on it must be `pass`.
While any current result is `changes_required`, `complete` is refused even if
every finding is `rejected` with evidence or compatibly `deferred`. The only path
forward is a changed artifact and a follow-up round, within the
effective task review limit, in which all required reviewers pass. Its baseline
is `max_followup_rounds`; only an explicit [task amendment](#task-review-allowance-amendment)
can increase it. A follow-up packet
on the same artifact is refused and there is no adjudication command for it. A
disagreement with a finding therefore needs a changed artifact and new reviews,
or the task stays blocked: report it, then block or cancel. Do not start a new
task to reset rounds. Material findings also keep needing a resolved,
criterion-compatible disposition after the follow-up passes.

`task block`, `activate`, `cancel` and `reconcile` take `{"reason": "Concrete
reason"}` through `command`. `reconcile` marks unattached launch intents
`unknown`; it never relaunches, resets deadlines or declares a worker stopped.
A read-only writer disposition can remain host-tracked as evidence without a new
source-writing assignment.

## Partial helper failure

`start`, `context` and `assignment` each run several engine mutations and are not
atomic. On failure, stderr names `incomplete_workflow`; that JSON lists each step
as `committed` or `incomplete` with a trace folder holding its request, input,
stdout and stderr. Before continuing:

1. Run `show` and `check`; compare the revision, artifacts, packets and
   assignments with the last committed step.
2. Establish whether any worker was launched and which packet it received.
3. Continue only the missing step. After a committed `assignment prepare`,
   re-record the intent:

   ```sh
   $B observe --record "$RECORD" --assignment write-1 --state launching \
     --boundary-observations "Host dispatch has not occurred"
   ```

   After a committed freeze but rejected seal, rerun `context` with corrected
   flags. The helper has no seal-only step, so this freezes again; the earlier
   committed freeze stays in the record as evidence. Inspect `show` and the new
   workflow JSON afterwards.

Never repeat `start` or `assignment` blindly, and never rerun any helper under
new task/assignment IDs. Rejected operations are not retried automatically;
revision conflicts need inspection. Use `show`, `check` and `packet` for
resumption. Backend selection does not enable automatic skill discovery or
establish quality, token or productivity gains.
