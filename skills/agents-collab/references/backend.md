# Optional local CLI backend

Use this procedure when `scripts/backend.py status` reports an enabled CLI.
Inspect status before creating task state or launching a collaborator. A successful
`mode: cli` selects CLI records even when model dispatch uses native subagents;
handwritten state cannot substitute for `start`, `context` and `assignment`.
The status includes the selected `config` path and a `next_action` reminder.
Only a successful `mode: manual` permits manual records. Errors stop the affected
collaboration; they never select manual mode. Missing settings select the manual workflow. Backend settings are separate from
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
- A review `context` refuses a task whose scoped change includes a deletion,
  binary or symlink, because this helper cannot present it. Report the limit
  and use another authorized review path; do not omit the change.
- A trailing-slash, directory-shaped Git entry (for example an untracked nested
  repository) inside the scope, or containing a scope entry, gets an explicit
  pre-write refusal that no selection or `--unrelated-changes` bypasses. A
  scoped staged gitlink has no trailing slash and gets the ordinary
  coverage/regular-file refusal instead. These entries cannot be presented as
  reviewed nested source; no traversal is added. A staged gitlink above a
  directory or absent scope entry instead follows the outside-scope declaration
  rule described in the coverage guard below.

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

Before deciding that storage conflicts with a host constraint, inspect the
selected profile and preview the same layout used by `start`:

```sh
python3 <skill-dir>/scripts/backend.py --profile /absolute/task/profile.json storage \
  --repository /absolute/source/repo --project demo --task guide-fix-1
```

`storage` requires the enabled CLI selector, reads the supplied profile and Git
root, and validates the existing records root, repository separation and symlink
guards. It returns the effective `profile`, `records_root`, `record` and `host`
paths without creating directories, task state or operation traces. Compare both
task paths with the host-authorized writable roots. It does not test filesystem
write permission, reserve a task, dispatch work or approve a location. `start`
revalidates current inputs. Do not replace a supplied profile with defaults,
rewrite its root or silently skip required review because temporary files have
a different designated directory. A real conflict or denied write remains a
blocker to report; the preview supplies no fallback or additional authority.

Shared `--config`, `--profile` and `--actor` options are accepted before or after
the subcommand. Repeated identical values are accepted; conflicting values are
refused before selecting a backend or writing task state. All three shared scalar
options reject the exact `--` value with a normal argument error (exit 2), before
probing the backend or writing state. Other leading-dash text values keep their
existing parsing behavior; downstream validation still applies. `--profile` always
means the collaboration profile, and never redirects the backend selector.
For a supplied task-local profile, check status without a selector override:

```sh
python3 <skill-dir>/scripts/backend.py --profile /absolute/task/profile.json status
```

A collaboration profile supplied as `--config` is rejected with an explicit
`--profile` recovery message. This error does not select manual mode or rewrite
configuration; correct the invocation rather than creating another selector.
 `--actor`
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

## Explicit opt-in for routine tasks

Use the route after classifying routine work and checking applicable review
requirements. With no flag, this command returns `route: solo` without opening
a profile, probing the backend or creating a record.

```sh
python3 <skill-dir>/scripts/backend.py route
```

For an explicitly flagged task, first resolve the configured CLI as usual.
Pass the exact editable scope and exactly one distinct reviewer from the saved
profile.

```sh
python3 <skill-dir>/scripts/backend.py route --review-required \
  --repository "$REPO" --project demo --task guide-fix-1 \
  --writer current-session --reviewer reviewer-a --scope docs/guide.md \
  --criterion "C1=Update the documented argument" --boundary "Local edit only"
```

The flagged command creates a record and returns `route: review`. This opt-in
record requires a CLI that supports record format 6. A missing or incompatible
backend fails the flagged route. The existing `start` command and its profile
and review-round behavior still apply to ordinary recorded collaboration.

Follow the initial cycle below, including the writer context and assignment
before the edit. Complete the writer observation before freezing the final
artifact. The sealed review packet binds the capture revision and artifact to
the writer assignment, invocation and terminal receipt. A fresh capture can
reuse an artifact hash when the source is already correct. The CLI requires
a passing review from the one configured reviewer on that exact packet with a distinct recorded
invocation. The route allows the initial writer and review only. If either
cannot finish, retain the record and report the outcome.

The host owns the flag, launch and observations. The CLI checks structural
identity and completion. It does not infer the flag from the ticket, launch a
model, or attest runtime identity or independence.

## Initial cycle

```sh
B="python3 <skill-dir>/scripts/backend.py"
$B start --repository "$REPO" --project demo --task guide-fix-1 \
  --writer current-session --reviewer reviewer-a --scope docs/guide.md --scope tests \
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

# Initial review on the finished source (neutral instructions only); select every
# changed scoped path, e.g. the edited guide and the writer's new test.
$B context --record "$RECORD" --purpose review --round 0 --paths docs/guide.md \
  --paths tests/test_guide.py \
  --omit-other-paths "Unrelated to this edit" --quiescence "Writer stopped" \
  --instructions "$HOST/review.txt" --output "$HOST/review-0.txt"   # -> ARTIFACT, PACKET
$B assignment --record "$RECORD" --id review-1 --packet "$PACKET" \
  --agent reviewer-a --role reviewer --output-destination "$HOST/review-1.json"
# Transport-conditional dispatch. REVIEWER_TRANSPORT is review-1's recorded
# requested transport (`show`: record.assignments[], select spec.id == "review-1",
# then read requested.transport). Set REVIEWER_TRANSPORT to that value first;
# a continuation assignment uses the quota-continuation procedure instead.
: "${REVIEWER_TRANSPORT:?Set review-1 recorded transport from show first}"
if [ "$REVIEWER_TRANSPORT" = "codex-native" ]; then
  # Ordinary codex-native reviewer only: render the identity-bound message.
  $B native-dispatch --record "$RECORD" --assignment review-1
  # Pass its message verbatim, exact task_name and requested model/effort and
  # fresh-session controls to the native host tool. Do not pass only review-0.txt.
elif [ "$REVIEWER_TRANSPORT" = "claude-cli" ]; then
  $B claude-dispatch --record "$RECORD" --assignment review-1
  # Pass its message verbatim on stdin and capture the exact terminal result.
else
  printf '%s\n' 'Unsupported reviewer transport' >&2
  exit 1
fi
# Dispatch the fresh reviewer, retain its terminal result, then:
# Add --exit-code only when the host exposes an actual code; native hosts may not.
$B observe --record "$RECORD" --assignment review-1 --state completed \
  --invocation "$REVIEW_SESSION" \
  --boundary-observations "$ACTUAL_REVIEW_BOUNDARIES"
$B import-review --record "$RECORD" --input "$HOST/review-1.json"
```

Writer context consumes no review round. Keep initial review packets neutral: no
writer transcript, persuasive report or other initial findings. Select enough
source for adequate context; a diff alone is not enough, and no implicit file
sweep is authorized. `--omit-other-paths` gives one reason for all unselected
inventory.

### Review coverage guard

Scope at `start` must name every path the task may change: docs, CLI entry
points and tests as well as the main source. Use a directory scope (for example
`tests`) when the writer may add files; the frozen scope cannot be widened later.
Freeze review context only after the writer's completion is observed, so the
reviewer receives the complete final source.

Before writing any workflow trace, record object or output, a review `context`
computes changes against the HEAD commit (the artifact's recorded base): staged
and unstaged tracked differences, including deletions and both sides of a rename,
plus untracked files Git does not ignore. Then it requires:

- every changed path inside the editable scope (exact path or directory
  descendant) to be selected; existing exact scope entries ignored by Git count;
- no scoped deletion and no selected absent, binary, symlinked or non-UTF-8 input;
- every changed path outside scope to be selected, or declared with
  `--unrelated-changes REASON`. Use that only for preexisting or unrelated work
  you have not attributed to the task; it is recorded per path in the frozen
  omissions and cannot omit a scoped change. A task change outside scope is a
  scope violation: report it rather than declaring it unrelated.

Directory-shaped scoped changes reported by Git (for example `tests/embedded/`
for an untracked nested repository) are explicitly refused before any write.
The helper neither traverses nor skips them; use another authorized review path
for such task work. Omitting the entry or selecting its name without the trailing
slash still gets that refusal. A raw trailing-slash `--paths` value fails the
shared normalized-relative-path validation first; it is not a supported selection.
A directory-shaped entry that contains a scope entry (scope
`vendor/lib/source.txt` beneath an untracked nested repository listed as
`vendor/lib/`) is treated as scoped for this refusal, so `--unrelated-changes`
cannot cover it. Only the trailing-slash shape is treated this way; an ordinary
file whose name is an ancestor of a scope entry, or a name that merely shares a
prefix such as `vendor/library`, keeps the normal outside-scope rule. Nested
repositories are not traversed or supported.

A **staged** nested repository is a gitlink, which Git lists without a trailing
slash. In scope it receives the ordinary refusals instead: an omission is a
missing task-scoped selection, and a selection is refused as not a regular file.
It is unsupported, not silently admitted.

A staged gitlink **above** a directory or absent scope entry follows a different
rule. For example, Git reports `vendor/lib` without a slash when the scope names
`vendor/lib/pending`. The trailing-slash containment rule does not apply, so that
gitlink is outside scope. Without an unrelated-work declaration the helper
refuses; with a genuinely preexisting unrelated-work declaration, synthetic
cases with the tested engine build freeze and seal the selected regular source
while retaining the gitlink as an explicit omission. The omission includes no
reviewed content beneath the gitlink and adds no nested-repository support.
Task work must never be declared unrelated to use this boundary.

The path guard does not enumerate directory-scoped content beneath a gitlink.
Adding writer content there can leave its reported coverage unchanged; this is
not a claim that Git status metadata is unchanged. A preexisting gitlink does
not establish that the writer did no work beneath it. If the writer may have
written there, do not declare the gitlink unrelated; use another authorized
review path. Adversarial synthetic cases demonstrate the visibility limit, not
permission to make an incorrect declaration.

An existing exact scoped regular file beneath the gitlink must still be
selected: omitting it is refused before writes, even with a declaration. In a
synthetic case with the tested engine build, selecting that file while declaring
the gitlink unrelated passes helper preflight, then the engine refuses the
freeze after the helper writes its workflow and freeze-operation trace. No
artifact, packet or rendered output is created and the record revision is
unchanged. This observation adds no support for selecting nested content; use
another authorized review path rather than treating the declaration as a
workaround.

Observed actual-engine outcomes for two paths that pass this preflight, using
synthetic fixtures with the engine build tested at preparation: an untracked
nested repository outside scope declared with `--unrelated-changes`, and any
untracked nested repository during writer context. The helper passes the exact
trailing-slash Git name to the engine as an omission. The helper first writes
its workflow and freeze-operation trace in `host/`; the engine then rejects the
freeze, with no artifact, packet or output and an unchanged record revision.
Stderr names `incomplete_workflow`. This is an observation of that engine build,
not a support claim; treat such a refusal as a nested-repository limit, not a
reason to delete or hide the entry.

Git errors and non-UTF-8 path names fail closed. After freezing and before
sealing, the helper recomputes the same change set and compares every frozen
manifest object with the live selected bytes; drift fails without a packet,
leaving the frozen artifact as evidence (see partial helper failure). The result's
`coverage` lists the baseline, scope, selected task changes, declared unrelated
paths and ignored in-scope paths that were not inspected. An empty change set
means no task change was found, not that review is unnecessary. Ignored files
under a directory scope are not discovered; select them explicitly when they are
task inputs. There is no flag that skips the guard. Writer context is unchanged.

Coverage limits: the guard sees only what Git reports as changed. Tracked paths
carrying assume-unchanged or skip-worktree index flags, and differences Git
normalizes away (for example through line-ending or clean filters), can hide a
tracked change from it. The baseline is the HEAD current at review time, so
task work already committed before review is not discovered. Keep the writer
from committing, inspect such flags and filters when they may apply, and
select those paths yourself. The guard does not attribute arbitrary changes to
a task; it enforces selection of the change set Git reports.

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

Replace `...` with choices for this round. Refresh review `--paths` against the
**current full change set**, including newly added or edited docs and tests;
copying the initial selection can omit the fix's work. Select every changed
scoped path and enough additional source for review. Use `--unrelated-changes`
only when actual preexisting or unrelated outside-scope changes remain unselected;
it cannot excuse a scoped omission. Reassess `--omit-other-paths`, writer
quiescence and the `--instructions` for the new packet. Dispatch its new reviewer
assignment using the same transport-specific procedure as the initial cycle.
The fix is a new assignment; see
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
A record already at format 4 (after a low-level `task accept-commit`) stays at
format 4. Later quota handoffs and amendments never downgrade the format. This
procedure applies to ordinary records in formats 1–4. No saved profile or
backend selector is written.

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
5. Dispatch through the [replacement procedure](#dispatch-the-quota-replacement).

Example reviewer handoff (replace symbolic hashes and paths with actual values):

```json
{
  "assignment": "review-1", "replacement": "review-1-continuation",
  "packet": "PACKET", "agent": "continuation-reviewer",
  "selection": {"model": "codex-model-id", "transport": "codex-native", "reasoning": "interface-default"},
  "output_destination": "HOST/handoff-output/review-1-continuation.json",
  "decision": "continue_with_codex", "authority": "lead",
  "decision_evidence": ["DECISION_OBJECT"],
  "reason": "Owner explicitly chose available Codex after quota interruption",
  "previous_invocation": "OLD_SESSION", "timing": "preserve_deadline",
  "instructions": "Fresh review of the original neutral frozen packet. Follow the complete replacement review contract supplied at dispatch. Wait for the exact invocation ID if needed before returning the final JSON.",
  "partial_work": null
}
```

### Dispatch the quota replacement

Prepare the message below and record launch intent. Run the read-only check
against the saved destination of the replacement assignment immediately before
starting the fresh invocation.

```sh
$B observe --record "$RECORD" --assignment "$NEW_ID" --state launching \
  --boundary-observations "Replacement launch intent recorded"
$B check-replacement-output --record "$RECORD" --assignment "$NEW_ID"
```

On success, use the returned `output_destination` for that assignment. The
check uses the same path rules as the ordinary renderers and leaves the
record unchanged. A successful check describes the location at that moment.
Repeat it if the launch is delayed or the location changes. Launch with the
selected model and effort and attach the actual invocation identity once the
host exposes it.

For a replacement configured with `inherit`, pass the active `--lead-effort LEVEL`
to `observe --state launching`. Use `effort_resolution.resolved` from the
replacement output check when applying effort to the new invocation.

Pause dispatch after any refusal. For a missing launch intent, stale artifact,
unverified record integrity or inactive task, follow the reported error and
reconcile the record before repeating the check. If an invocation is already
attached, reconcile that worker through `observe` before any further action.

For a destination or storage refusal, use the read-only `show` command to
check whether the helper can still bind the same record. Inspect host or
supervisor evidence to establish whether a worker ran.

If storage validation fails for the record or its `host/` directory, the
binding step also refuses `show`, `observe`, and `evidence`. Keep dispatch
paused and retain host observations in authorized private storage outside
the affected record, host directory, and any Git checkout. The recorded
intent stays as it was. Resume record operations only once authorized
recovery restores the saved layout and `show` and `check` verify the same
record. Then reconcile the actual worker state before recording evidence
or repeating preflight.

If Git covers either task directory, leave the repository and its metadata
intact. An owner-approved storage repair may relocate the conflicting
checkout intact to private storage and restore the original private task
directories from verified copies at their recorded paths. A probe or
environment error needs an authorized correction that allows storage
validation to succeed. If the original layout cannot be restored safely,
leave the task unresolved and retain the observations outside the record.

If the helper can still bind the record and the refusal applies only to
the destination, use the following recovery steps.

- If the host confirms that none ran, keep the registered destination fixed.
  For a stray file or directory layout problem outside Git, restore safe
  storage only with authorization, preserving unexpected files in private
  storage. Then repeat `check-replacement-output` using the original recorded
  launch intent. If Git covers only the output subdirectory, leave that
  repository and its metadata in place and record the replacement as
  `blocked` with the reason.
  Record the same outcome if safe storage otherwise cannot be restored.
- If a worker ran, use `observe` to attach its actual invocation and state.
  If liveness is uncertain, record `unknown` and keep dispatch paused pending
  reconciliation.

An indeterminate Git probe or an explicit Git worktree override is a storage
refusal. Repeat the check only after an authorized correction establishes the
actual private path. The check is for pending launch intents. For an
`unknown` or `blocked` replacement, record the actual host observations and
keep the slot unresolved if no invocation can be safely attached. Preserve the
existing intent history.

Keep host evidence privately while the intent is unresolved. The `evidence`
command refuses while any assignment remains in `launching` state.

For a reviewer, send the original neutral sealed packet and its frozen source
with the **complete [review contract](#review-contract)**, including the JSON
object and its formatting and field rules. Populate `assignment` with the
replacement ID and `packet` and `artifact` with the original registered hashes.
Use that artifact hash for the default verification `object`. Keep the original
packet unchanged. The lead assembles this message because the ordinary
renderers refuse quota continuations.

The reviewer's `fresh_session` must exactly equal the actual replacement
invocation string that the lead records on completion. Use a host path that
can supply that string to the reviewer before its final response. If the
identity becomes available only after launch, instruct the reviewer to wait
for it before finalizing. Attach the real identity and send it to the same
replacement session. Keep boundary observations in `limits` or
`tool_boundary`, and keep the writer transcript and old reviewer session out
of the replacement.

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
to **2** in the same transaction; a record already at format 3 (review amendment)
or format 4 (low-level `task accept-commit`, which explicitly binds approved
staged work to its later commit) keeps its higher format. Ordinary records remain
format 1. This procedure applies to ordinary records in formats 1–4. The CLI
reads format 6 for the opt-in route and refuses unsupported formats before
interpreting them. Keep using a compatible
binary; no downgrade or automatic backend switch is supported. No quota API,
dispatcher, GUI prompt, absence detection or authority attestation is provided.

## Observations and retries

For delegated `auto`, the helper resolves the [scope policy](configuration.md#opt-in-automatic-effort)
after the packet is sealed. For delegated `inherit`, give `assignment` the
[active lead's effort](configuration.md#lead-effort-inheritance) in `--lead-effort LEVEL`.
If preparation committed before launch intent, provide that level when recording
`observe --state launching`. The helper keeps the captured value in the launch
receipt, including across retries. Already recorded launch intents from older
versions retain their original behavior.

Use `effort_resolution.resolved` from the assignment output or a supported
dispatch renderer or replacement check as the interface effort. The original
profile preference stays in `requested.reasoning`. For running and completed
observations, pass the accepted concrete level in `--interface-effort`. The
helper checks it against the same resolution. Reconcile an unexpected interface
result before further dispatch.

For an ordinary `codex-native` assignment with recorded `launching` intent,
construct the dispatch body from the registered immutable objects:

```sh
python3 <skill-dir>/scripts/backend.py native-dispatch --record RECORD --assignment review-1
```

The read-only result includes assignment/packet/artifact identities, requested
controls, a deterministic `task_name` identity digest, a `message` string containing the explicit hashes, the
role's [final-output contract](#review-contract) and the full frozen context, its
`final_output` (contract name and, for reviewers, the identity-filled schema
template) and its UTF-8 `message_sha256`. The identity header lines are unchanged. Pass that message string verbatim to the
native tool with its returned task_name exactly and the required model/effort
and fresh-session controls. Do not substitute a free-form name. The digest uses
all three exact identities with a versioned domain; it is not a message digest
or authorization. A host may join that exact observed call/start/path with a
first-turn opaque AgentMessage payload equal to the same call bytes. This proves
only native invocation identity and opaque delivery, not plaintext/full-context
equality. A name alone, model summary, preview or reconstructed packet proves no
delivery; absent received-input provenance remains unverified. The helper
has no transport-specific payload-size guarantee: the host must confirm that its
interface accepts the complete message and stop if it cannot. Do not truncate
context to preserve just the header. The message_sha256 describes constructed message bytes;
it does not attest delivery or complete delivered-context equality. Do not
send only a context-file path or substitute an older assignment's message for a
new packet. The renderer checks active task, launching/no-invocation state,
native transport, current artifact, role/purpose, immutable record integrity and
the registered output destination's private storage boundary.
It creates no directories, traces, assignments or workers. Rendering is not
permission, a lease, a liveness check or delivery evidence; inspect the host
before any uncertain dispatch and never retry blindly. Quota continuations are
refused here because their dedicated instructions/partial-work handoff must be
preserved. The existing continuation procedure remains authoritative.

For an ordinary `claude-cli` reviewer, `claude-dispatch --record RECORD
--assignment ID` applies the same state, identity and immutable-context
checks with the Claude transport. Its `message` includes the reviewer contract
and full frozen context, and its `message_sha256` identifies those exact intended
stdin bytes. Use the [Claude review procedure](review-protocol.md#fresh-claude-cli-review)
for launch, timing and terminal capture. Confirm the interface accepts the entire
message. If it does not fit, stop and reconcile the launch intent. The renderer runs no process or transport
and does not attest delivery. Use the existing writer and continuation procedures
for their respective assignments.

Raw native argument fields can be opaque. An envelope-shaped message without
visible hashes cannot establish what plaintext the caller sent or the child
received. A local preview also proves no delivery. Preserve the original field
and distinguish readable-but-unbound from opaque/unavailable. Only a separate
host-owned, exactly identity-bound delivered-input receipt can supply readable
text when available; do not decrypt, read keys or infer it from packet contents
or participant summaries. Unknown binding remains unverified.

`assignment` prepares the assignment, then records `launching` intent with no
invocation. Dispatch only after both steps commit. `observe` then attaches what
the host actually saw. Record interface model/effort separately; runtime
attestation stays unknown. Omit `--exit-code` when a native host exposes none;
an exit code alone proves no valid review. The backend never cancels a worker.

Native hosts can expose a canonical invocation path separately from a thread
UUID. Retain both identities and use an exact, unique mapping from host-owned
child source/parent metadata before joining lifecycle or review receipts. Do not
match a nickname, role or path suffix, guess a UUID, or use the writer and reviewer
aliases to hide one shared thread. Ambiguous, conflicting or unproven mappings
remain unverified. Resolving identity supplies no missing spawn request,
packet/artifact binding, accepted controls or terminal reviewer output.

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

The reviewer's terminal final message is this complete JSON object and nothing
else: no prose, heading or fences before or after it. Any summary belongs in
`limits`, verification descriptions or findings. If the reviewer also writes the
assigned output file, the file holds the same JSON object as the final message.
For an ordinary `codex-native` or `claude-cli` reviewer, the matching renderer
places this contract,
with the exact recorded assignment, packet and artifact identities, after the
identity header and before the frozen context (`final_output` in its result);
writer messages get a report contract instead and are never asked for this JSON.
Manual mode uses its own output contract. For a quota replacement, the lead
supplies this complete contract using the
[replacement dispatch procedure](#dispatch-the-quota-replacement).

Review instructions must not ask for a different final output, such as "a JSON
file plus a concise summary". Ask for findings in the schema fields. The native
contract states that it supersedes a conflicting request, but a contradictory
packet still wastes the review. A result file, preview, wait summary,
progress note or self-report is not terminal evidence: import the host-retained
terminal final message, and if a written file differs from it, retain both and
treat the review as unresolved. The schema:

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
