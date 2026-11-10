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

- `start` fixes the reviewer set. Reviewers cannot be added or replaced later.
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

`start` returns `record` (`records_root/{project}/{task}/collaboration`) and
`host`, its private sibling for inputs, outputs, receipts and traces. Pass
`--record` to every later command and keep all `--output`/`--output-destination`
files inside `host/`. `context` returns `artifact` and `packet` hashes; reviewers
must echo both. Assignment IDs are new for every writing or review job; there is
one assignment per agent and packet.

Global `--config`, `--profile` and `--actor` precede the subcommand. `--actor`
(default `lead`) is attribution on every mutation and, at `start`, the task's
only declared decision authority. It authenticates no one: naming a person as
actor is not their approval. Real human approvals need actual evidence through
the low-level completion contract below; the helper never infers them.

`--requirement` and `--criterion` take `ID=TEXT` (IDs use letters, digits, `_`,
`-`). `--instructions` is a UTF-8 **file**, not inline text. `--round` is `0` for
initial writing and the initial review; `N` for the repair `writer_context` and
follow-up review after every reviewer finished round `N-1`. The profile's
`max_followup_rounds` caps `N`; a follow-up review must name a changed artifact.
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

The reviewer returns this JSON with the identities from `context` and
`assignment`:

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
forward is a changed artifact and a follow-up round, within
`max_followup_rounds`, in which all required reviewers pass. A follow-up packet
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
