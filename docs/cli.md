# Local record-and-packet CLI

**Experimental local backend, 9 November 2026.** The separate `cli/` crate
builds `agents-collab`; its executable is packaged separately from the skill.
It stores local records and frozen inputs. An authorized host still performs all
writing, dispatch, supervision and review. This binary calls no models, launches
no workers and changes no profile, source checkout or global settings.

## Optional backend installation

The skill includes a reusable adapter and offline archive installer. Installing
the skill alone keeps the manual workflow. Package an already built native
release executable, using a selected private output directory:

```sh
python3 scripts/package_cli.py --binary "$CARGO_TARGET_DIR/release/agents-collab" --output-dir "$collab_package"
```

The archive contains the executable, MIT notice and a version/platform/binary-hash
manifest; `SHA256SUMS` accompanies it. Only macOS arm64 packaging is currently
supported. See [build instructions](#build-and-checks) below. There is no published
cross-platform release channel.

Install a trusted archive using its expected digest, then explicitly enable it:

```sh
python3 ~/.agents/skills/agents-collab/scripts/install_backend.py --archive "$collab_archive" --sha256 "$collab_sha256" --enable
python3 ~/.agents/skills/agents-collab/scripts/backend.py status
```

The variables name your selected archive and its SHA-256. The default binary
location is `~/.local/bin/agents-collab`. Separate preferences in
`~/.config/agents-collab/backend.json` record the absolute binary path and enabled
mode. The profile, shell PATH and project instructions are not rewritten.
Unrelated existing targets require explicit replacement authorization.

The [backend procedure](../skills/agents-collab/references/backend.md) is
self-contained for installed skills: initial and follow-up command examples,
observation and retry receipts, review and disposition JSON, conservative CLI
limits and recovery after a partial helper failure. Helper subcommand help
describes its flags. Low-level contracts below remain available.

## Validation status

On 9 November 2026, independent review and focused follow-ups resolved five
findings: cached-response integrity, detached record inspection, Git
file/directory transitions, recorded writer handoff, and a writer recovery/launch
guard. The last correction used one explicitly authorized additional review
cycle. No material implementation-review finding remains from that cycle.
All 24 offline integration tests pass.

New writer launch intent rechecks every other writer's current state in the
serialized mutation transaction. Prepared, launching, running or unknown writers
block that intent. Truthful observations of existing workers remain recordable,
including conflicting activity; original invocation identities and deadlines
are preserved. Recovery tests check refusal without mutation and successful
handoff after prior work is reconciled as terminal.

This validates the local record-and-packet core within its documented platform
and evidence limits. A later [six-workflow live pilot](../evals/cli-usefulness/2026-11-09/report.md)
compared the same skill with and without the CLI. Both paths produced passing
final code and recovered the same reviewer invocation after a controlled missing
receipt. No added CLI usefulness was demonstrated; the frozen rule returned
inconclusive. One coordinator provenance mistake affected two CLI rows and
required correction. These small observations establish no general quality,
speed, token, cost or equivalence advantage. The host still dispatches models;
the CLI records the handoff rather than providing a model transport.

## Build and checks

Rust/Cargo 1.99 or newer and a C compiler are required; only Rust/Cargo 1.99.1 on
macOS with local APFS was tested. SQLite is bundled in the crate build; no SQLite
server or system installation is needed. First build may download public crates.
The crate includes a lockfile. Python helpers remain standard-library only.

Set an external build and temporary directory in accordance with your storage
policy; the following uses an already selected private scratch directory:

```sh
export CARGO_TARGET_DIR="$SCRATCH/target"
export TMPDIR="$SCRATCH/tmp"
mkdir -p "$TMPDIR"
cargo build --locked --manifest-path cli/Cargo.toml
CLI="$CARGO_TARGET_DIR/debug/agents-collab"
"$CLI" --help
cargo fmt --manifest-path cli/Cargo.toml --check
cargo clippy --locked --manifest-path cli/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path cli/Cargo.toml
```

The integration suite executes the real binary against disposable synthetic Git
repositories and private records under the system temporary directory. Its full
handoff, repair and interruption scenarios need no provider or credentials. It
also invokes the unchanged Python profile validator for compatibility cases.
These tests establish offline structural behavior, not real review quality,
provider access, effort attestation, faster coordination or token savings.

### Local regression gate

`scripts/check_cli.py` (Python 3.9+, standard library) runs all of the above
plus the full Python suite against the freshly built binary, from one pinned
commit. It is a maintained local check, not CI and not a release. Only macOS
arm64 with scratch on local APFS is supported; anything else is refused.

Cargo runs offline. Fetch the locked public crates once beforehand, into a cache
you select (setting `CARGO_HOME` per command changes no global configuration):

```sh
CARGO_HOME="$CARGO_CACHE" cargo fetch --locked --manifest-path cli/Cargo.toml
```

Then, from a **clean** checkout, name a new scratch directory whose parent exists:

```sh
CARGO_HOME="$CARGO_CACHE" python3 scripts/check_cli.py --scratch "$SCRATCH/gate-1"
```

`--revision REV` selects another commit (default `HEAD`). Before writing anything,
the gate refuses a dirty working tree (tracked changes or nonignored untracked
files), an unknown revision, a relative path, an existing scratch path, a
missing parent, scratch overlapping the source or inside any Git repository, an
unsupported platform and storage that `df`/`mount` do not report as local APFS.
It never deletes or replaces caller files; remove old scratch yourself.

The gate creates the scratch directory exclusively, writes `source.tar` with
`git archive` and extracts it to `source/` (regular files and directories only).
It then runs, in order and stopping at the first failure:

1. `cargo fmt --check`;
2. `cargo build --locked --offline`, then copies the binary to `bin/agents-collab`;
3. `cargo clippy --locked --offline --all-targets -- -D warnings`;
4. `cargo test --locked --offline`;
5. `python3 -m unittest discover -s tests -v` in the snapshot, with
   `AGENTS_COLLAB_TEST_BINARY` set to the frozen binary copy.

`CARGO_TARGET_DIR`, `TMPDIR` and all logs stay in scratch, with
`PYTHONDONTWRITEBYTECODE=1` and `CARGO_NET_OFFLINE=true`; test fault hooks are
removed from the environment. A zero exit is not enough: Cargo test output must
show passing tests, none failed or ignored. The Python suite must end with a
plain `OK`, skip nothing and run `test_backend.RealBackendTests`, the real-engine
cases. A missing binary or a binary changed during the run also fails.

`result.json` records the status (`incomplete`, `passed`, `failed` or
`interrupted`), failure reason, revision, tree, archive and binary SHA-256, tool
versions, selected environment, each command with its exit status and times,
and `logs/` paths. A step left `running` marks an interrupted run. Exit codes
are 0 passed, 1 failed, 2 refused before writing and 130 interrupted.

Limits: the snapshot contains committed files only, so uncommitted work is never
checked. The debug binary hash identifies the bytes tested; it embeds build paths, so it
is not a reproducible-build identity. Tool versions are recorded, not pinned; the environment (`PATH`,
`CARGO_HOME`, toolchain manager settings) is inherited. Cargo may update its own
cache metadata in `CARGO_HOME`. The storage preflight inspects mount metadata;
the real-engine tests separately exercise the engine's runtime storage check in
scratch `TMPDIR`. The gate makes no model, provider or API calls. The website
build is a separate check. Results are unsigned local
evidence reported by whoever runs the gate: they establish offline structural
behavior on that machine, not provider access, review quality or other platforms.

## Invocation and output

Every command takes two words (`task show`, for example). All record operations
use `--record "$RECORD"`. Inputs are explicit regular UTF-8 JSON files supplied
with `--input FILE`; duplicate keys and unknown contract fields are rejected.
There is no inferred active task, global registry or profile auto-discovery.
Input files are limited to 16 MiB (profiles to 256 KiB); repository paths must
be UTF-8. Large frozen objects can still require substantial memory/storage.

Every mutation requires `--actor NAME --key UNIQUE_OPERATION --expect REVISION`.
Creation expects revision 0; its returned revision is 1. Subsequent mutations
use the last returned revision. A repeated key returns its original response
only for the identical command, actor, input bytes and expected revision. A
contradictory repeat or stale revision fails. Cached success is returned only
after current committed object integrity and record location are checked; the
returned operation receipt remains historical, including its source observation.
Callers must inspect the current
record and reconcile, rather than overwriting on conflict. Distinct input
formatting counts as distinct bytes. No automatic retries occur.

`--json` returns `{ "schema_version": 1, "ok": true, "data": ... }`, or
`{ "schema_version": 1, "ok": false, "error": { "kind":
"operation_rejected", "message": "..." } }` with exit 1. Human output is indented
JSON. Mutation data contains `revision`, `state`, `result`, and `blockers`.
`task show` also includes the private record and possible operation names; these
names are candidates, whose input-dependent gates still apply. Observation times
are Unix UTC seconds; compare them with current time to assess age. A historical
`running` receipt proves no present liveness.

**Import success is separate from result validity.** `review import` durably
preserves malformed or invalid originals and returns exit 0 with
`result.validation: "rejected"` or `"incomplete"`. Only
`"valid_structure_only"` counts toward review coverage. No exit code or imported
claim establishes truthful evidence, identity, independence or authority.

## Task creation and profile

Project names support nonempty dot-separated segments such as `example.com`,
with a 40-character total limit. Each segment follows the existing name rule:
start with an ASCII letter or digit, then use ASCII letters, digits, `_` or `-`.
Leading, trailing and consecutive dots are rejected. Task, requirement, agent
and assignment IDs keep their existing validation. The complete dotted project
name remains one storage directory; symlink and traversal guards still apply.
See the [adapter contract](../skills/agents-collab/references/backend.md#identities-and-arguments)
for adapter/CLI compatibility and records-root handling.

Create the configured `records_root` on the intended volume first. Supply the
selected existing v1 profile explicitly; the CLI never writes it:

```sh
"$CLI" task create --profile "$PROFILE" --input "$INPUT/task.json" \
  --actor owner --key create-1 --expect 0 --json
```

The returned `record` is
`records_root/{project}/{task}/collaboration`; use it as `$RECORD` below.
`--record` is optional on creation and, if given, must match that exact target.
`task` is a safe 1–40-character name beginning with an ASCII letter/digit and
containing only ASCII letters/digits, `_` or `-`; project names follow the dotted
name rule above.
An existing task cannot be overwritten. The CLI cannot detect a human creating
a differently named task to evade policy; renamed tasks do not authorize resets.

`task.json` has exactly these fields (replace the illustrative absolute path):

```json
{
  "schema_version": 1,
  "project": "synthetic",
  "task": "change-1",
  "repository": "/absolute/synthetic/repository",
  "requirements": [
    {"id":"R1","kind":"requirement","text":"Verbatim requested behavior","source":"ticket"},
    {"id":"C1","kind":"criterion","text":"Acceptance condition","source":"ticket"},
    {"id":"S1","kind":"safeguard","text":"No external publication","source":"policy"}
  ],
  "authority_boundaries": ["Owner approval required before publication"],
  "writer": "writer",
  "editable_scope": ["src/file.rs"],
  "reviewers": ["reviewer"],
  "required_checks": ["offline-tests"],
  "required_approvals": ["owner"],
  "decision_authorities": ["owner"]
}
```

The repository must be a canonical absolute Git root with an existing HEAD.
Requirement IDs are unique safe names, with nonempty verbatim text and source;
`kind` is `requirement`, `criterion` or `safeguard`. Boundaries and declared
request/disposition authorities are mandatory. Writer and reviewers resolve from
the profile; `current-session` is allowed only as writer. The fixed reviewer set
cannot include the writer or a host entry. The task registers exactly one writer
and its editable scope. Empty reviewer lists are allowed only when the profile
allows no consequential review. Empty check/approval lists must reflect actual
policy; declaring them does not waive external requirements.

Native profile checks follow the existing v1 contract: required/unknown fields,
references, names, bounds, transports and enums, including duplicate JSON keys.
JSON integer fields use Rust's unsigned 64-bit range (Python accepts larger
integers); deadlines also must fit checked arithmetic. The private profile bytes
and resolved preferences are frozen in the record. They are not credentials,
authority, actual model availability or runtime evidence.

## Freeze and seal

Stop the writer cooperatively before capture. `selection.json` lists individual
paths, never directories or globs:

```json
{
  "paths": ["src/file.rs", "Cargo.lock", "removed.txt"],
  "omissions": {"unrelated.txt":"Outside the approved change and its context"},
  "acknowledged_sensitive": [],
  "quiescence": "Writer has stopped; coordinator holds the editing turn",
  "atomic_required": false,
  "base": "HEAD"
}
```

```sh
"$CLI" artifact freeze --record "$RECORD" --input "$INPUT/selection.json" \
  --actor owner --key freeze-1 --expect 1 --json
```

Every tracked, base/HEAD-deleted or nonignored untracked file needs explicit selection
or a reasoned omission. Ignored files are never swept; they require an explicit
path. Sensitive-looking names additionally require a matching acknowledgement.
This name heuristic is not a secret scanner: inspect every selected input.
Include necessary surrounding source, tests and lockfiles; coverage is a host
responsibility, not inferred from file extensions.

The artifact identity is the SHA-256 of its versioned manifest. It captures HEAD,
resolved base, complete Git status/index objects, selected working bytes, selected
base/HEAD/index blobs and their modes (including pre-deletion bytes), lengths,
binary files, deletion markers and literal symlink
target bytes. File/directory replacements record the old tracked blob path as a
deletion and new file/child paths separately, for staged and unstaged changes.
Symlink targets are not followed. Paths with a symlink ancestor,
traversal, Git metadata, special files, unmerged entries and submodules are
rejected. An ordinary directory cannot be selected; a historical tracked blob
path now occupied by a directory is represented only as a deletion. Unsupported external content must be represented as explicit selected
regular evidence bytes, or a selected document stating URL/revision, retrieval
time and mutable/unavailable limits. External services and test environments are
not frozen by source hashing.

Capture scans before and after publication, verifies stored bytes and rejects
detected drift. Repeated scans cannot prove an atomic multi-file view against an
external editor. `atomic_required: true` is refused: arrange an independently
established immutable snapshot and resolve the stronger requirement outside this
prototype. No restore command exists; objects are inert bytes, never a checkout.

A `packet.json` references the returned artifact hash (`ARTIFACT` below):

```json
{
  "purpose": "review",
  "artifact": "ARTIFACT",
  "round": 0,
  "instructions": "Inspect frozen source against the complete requirements",
  "access_policy": "Fresh read-only review; report automatic context and tool boundaries",
  "coverage": {"R1":["ARTIFACT"],"C1":["ARTIFACT"],"S1":["ARTIFACT"]},
  "evidence": [{"category":"source_claim","description":"Supplied frozen tree","object":"ARTIFACT"}],
  "neutral_initial": true
}
```

All coverage lists must refer to known immutable objects and cover every ID
exactly. The packet embeds the complete verbatim requirements and boundaries;
coverage references navigate them, not replace them. Evidence categories are
`source_claim`, `verified_observation`, `interpretation`, `reviewer_opinion`,
`unknown`, and `unavailable`; categories are declarative, not truth validation.
Initial neutrality excludes writer transcripts, persuasive reports and other
reviews. The schema cannot recognize such material hidden in arbitrary text;
the host must inspect the preview.

```sh
"$CLI" packet preview --record "$RECORD" --input "$INPUT/packet.json" --json
"$CLI" packet seal --record "$RECORD" --input "$INPUT/packet.json" \
  --actor owner --key seal-1 --expect 2 --json
"$CLI" packet show --record "$RECORD" --input "$INPUT/packet-id.json" --json
```

`packet-id.json` is `{ "packet": "PACKET" }`. `packet show` returns
`sealed_packet` (the exact decoded frozen common body) and `live_source`
(inspection metadata, outside that body). The sealed packet hash identifies
the exact common body, including requirements and boundaries. Recipient envelope
fields live only in assignments. `purpose` is `review` (the default when omitted)
or `writer_context`. Only review packets consume review rounds. The initial
review packet cannot be replaced in place,
even before a result: this conservative prototype requires reconciliation and
reports a blocker instead of implementing initial-round restart. All required
reviewers receive this same identity. After every required review result is
recorded, repair creates a new artifact and the next sequential packet round.
Each follow-up requires the full fixed reviewer set and a changed artifact.
The frozen profile supplies the baseline follow-up cap; no replacement reviewer
resets it. Only an explicit owner-authorized [task review amendment](../skills/agents-collab/references/backend.md#task-review-allowance-amendment)
adds exactly one round through `task extend-review` (helper `extend-review`).
`task show` reports the baseline, effective limit and retained amendments.
Both packet validation and artifact capture use that effective limit. Round
numbers, existing results and completion safeguards remain unchanged.

## Recorded writing before initial review

To record the initial writer, first freeze its selected input context and seal a
packet with `purpose: "writer_context"`, `round: 0`. It has the same complete
requirements/coverage contract, but its instructions serve the writer rather than
claiming neutral independent review (`neutral_initial` may be false). Prepare
a writer assignment naming that context packet, the registered writer and exact
editable scope. Persist launch intent before the host writes, then observe and
reconcile completion as below. Active/unknown/prepared assignments block capture.
For example, a writer assignment input is:

```json
{"id":"write-1","packet":"WRITER_CONTEXT","agent":"writer","role":"writer","editable_scope":["src/file.rs"],"output_destination":"private-writer-output"}
```

Use the same `assignment prepare` and `assignment observe` commands below with
this input and the current returned revision.

Once the writer is terminal and its launch state is reconciled, freeze its output
and seal a **new** `purpose: "review"`, `round: 0` packet. Every required initial
reviewer consumes this same output identity. The writer's input packet does not
consume an initial review, and cannot be assigned to a reviewer.

For review-driven repair, first finish every required reviewer on the existing
review packet. Seal a `writer_context` packet against the current artifact with
`round` equal to the next permitted review round, record the writer assignment,
then freeze the repaired output and seal the next review packet. Preparing repair
writing, sealing a writer context or freezing an output cannot bypass the fixed
reviewer set, unfinished prior reviews or follow-up cap. An old writer context
cannot be reused to reset rounds. A writer cannot be assigned a review packet.

## Assignments and observations

`assignment.json` has exactly:

```json
{"id":"review-1","packet":"PACKET","agent":"reviewer","role":"reviewer","editable_scope":[],"output_destination":"private-result-1"}
```

```sh
"$CLI" assignment prepare --record "$RECORD" --input "$INPUT/assignment.json" \
  --actor owner --key prepare-1 --expect 3 --json
```

A reviewer has no editable source scope. A writer assignment must name the
registered writer and exact scope; only one writer can remain nonterminal.
There is one logical assignment slot per agent/packet. An explicit interrupted
backend handoff may create one linked replacement execution; it never adds a
review slot.
The requested model/effort is stored separately from later interface-accepted
and observed values, which remain null/unknown until reported.

Before dispatch, record `receipt.json` with `state: "launching"` and
`invocation: null`. Only after that mutation commits may the host launch:

```json
{
  "schema_version":1,"assignment":"review-1","state":"launching",
  "invocation":null,"process_start":null,
  "interface_model":null,"interface_effort":null,
  "observed_model":null,"observed_effort":null,
  "boundary_observations":"Freshness, automatic memory/hooks and restrictions are not yet observed",
  "exit_code":null,"reason":"Persist intent before authorized host dispatch",
  "reconciled":false,"absence_established":false
}
```

```sh
"$CLI" assignment observe --record "$RECORD" --input "$INPUT/receipt.json" \
  --actor owner --key intent-1 --expect 4 --json
```

Attach the host's session/invocation identity promptly with a new receipt and
operation key. States are `launching`, `running`, `completed`, `interrupted`,
`blocked` and `unknown`, in addition to the initial `prepared`. An explicit
handoff marks the original assignment `superseded`; it cannot receive further
observations or valid results, even with reconciliation flags. `running` and
`completed` require an invocation identity; PID alone is insufficient.
`process_start` is optional supplementary evidence. Any uncertain, interrupted,
blocked or terminal state needs an explicit `reconciled: true` receipt to change.
Invocation identity changes require recorded reconciled absence; that declaration
does not technically establish absence. This CLI never initiates a redispatch.

The skill helper's `observe` sets `reconciled` and `absence_established` only
from explicit `--reconciled` and `--absence-established` flags, both false by
default. Either flag needs an explicit `--reason`, absence needs reconciliation,
and `--process-start` fills the optional field. Contradictory flags fail before
any record mutation. A retry of the same assignment attaches the new invocation
with both flags. That happens only after the host establishes the earlier
invocation's absence and durably saves its own uniquely labelled pending retry
attempt before relaunch. The CLI records neither the second launch intent nor
absence. Without such host bookkeeping or supervision, retry stays blocked. See
the backend procedure's retry section.

The first launch UTC time and absolute advisory deadline persist through every
observation, interruption and recovery; they never reset. A handoff preserves
that original assignment and deadline; its replacement records its own actual
launch time while inheriting the original deadline. A follow-up is a new
assignment within the existing cap. Required timing blocks launch because this
record-only CLI cannot validate a supervisor. `runtime-attestation` likewise
blocks launch, rather than accepting an imported model assertion as proof.
Advisory targets are not enforced deadlines; the skill's
[assignment timing](../skills/agents-collab/references/configuration.md#assignment-timing)
defines overrun, retry and fix-assignment handling. External supervision, monotonic
time, clock-discontinuity detection and cancellation are not implemented.

## Results and findings

A review input has exactly these fields:

```json
{
  "schema_version":1,"assignment":"review-1","artifact":"ARTIFACT","packet":"PACKET",
  "verdict":"pass",
  "verification":[{"category":"unknown","description":"No external test evidence available","object":"ARTIFACT"}],
  "limits":"Describe checks not run and unavailable evidence",
  "findings":[],
  "fresh_session":"Observed fresh session or explicit uncertainty",
  "automatic_context":"Memory, instructions, hooks, plugins and tool observations",
  "tool_boundary":"Actual restrictions; fresh context alone is not isolation"
}
```

`limits`, `fresh_session`, `automatic_context` and `tool_boundary` are nonempty
strings, not arrays. For a quota-continuation review, `fresh_session` must equal
the completed invocation string exactly; put explanatory boundary text in
`limits` or `tool_boundary`. For ordinary reviews it remains a free-text session
observation. The installed [backend review contract](../skills/agents-collab/references/backend.md#review-contract)
describes the complete shape. Include it in the review instructions before
sealing; the helper does not append it automatically.

```sh
"$CLI" review import --record "$RECORD" --input "$INPUT/review.json" \
  --actor owner --key import-1 --expect 6 --json
```

The assignment must first have a `completed` invocation observation; exit zero
alone is insufficient. Artifact and packet identities must match the current
sealed copy. Only one valid result per assignment is accepted. Verdicts are
`pass`, `changes_required`, or `blocked`. A blocked verdict is retained as
incomplete, sets the assignment blocked and does not consume a valid result;
reconcile that existing assignment after restored access. Invalid and malformed
original bytes remain immutable and appear in `invalid_results`; no wrapper
extraction, content repair or model retry is implemented.

A finding has `id`, `location` (source or requirement), `scenario`,
`evidence` (reasoning), `uncertainty`, `material` (boolean) and `recommendation`.
All textual fields are required and nonempty. IDs remain unique across rounds;
source review and artifact provenance is retained. A pass cannot include a
material finding. Import all required initial results before starting repairs.

`disposition.json` records one finding decision:

```json
{"finding":"F1","decision":"addressed","reason":"Explain the fix","evidence":["OBJECT"],"authority":"owner","criterion_compatible":true}
```

```sh
"$CLI" finding resolve --record "$RECORD" --input "$INPUT/disposition.json" \
  --actor owner --key resolve-1 --expect 7 --json
```

Decisions are `addressed`, `rejected`, `deferred`, `unresolved`. The actor must
match a declared decision authority and reference frozen evidence. This is
attribution, not authentication. Addressed material findings require a new
artifact and required follow-up reviews; rejected findings require evidence;
deferred findings require declared authority and must remain compatible with
acceptance. No declaration can silently change criteria. Every earlier decision
input remains in the append-only operation evidence.

## Lifecycle, completion and recovery

```sh
"$CLI" task show --record "$RECORD" --json
"$CLI" task check --record "$RECORD" --json
"$CLI" task activate --record "$RECORD" --input "$INPUT/reason.json" \
  --actor owner --key activate-1 --expect 8 --json
"$CLI" task block --record "$RECORD" --input "$INPUT/reason.json" \
  --actor owner --key block-1 --expect 9 --json
"$CLI" task reconcile --record "$RECORD" --input "$INPUT/reason.json" \
  --actor owner --key reconcile-1 --expect 10 --json
"$CLI" task cancel --record "$RECORD" --input "$INPUT/reason.json" \
  --actor owner --key cancel-1 --expect 11 --json
```

`reason.json` is `{ "reason": "Concrete actor-attributed reason" }`. These
commands illustrate separate transitions, not a script to run in sequence.
States are `prepared`, `active`, `blocked`, `completed`, `cancelled`.
Activation permits prepared/blocked tasks. Completed/cancelled tasks cannot
reopen or mutate except reconciliation. Cancellation does not claim worker
termination. `check` verifies committed object integrity and reports structural
completion blockers; it does not itself complete a task or validate liveness.
Frozen-record inspection, selected export and packet access
remain available when the original live checkout is removed or unavailable.
Their `live_source` observation reports that condition explicitly. Unbound
reconciliation also remains available. A commit-bound task requires source
verification before reconciliation or activation. Capture and new completion
still require the canonical live source, and `check` reports its
unavailability as a completion blocker. Stored original path overlap checks and
any currently resolvable source alias remain enforced.

`reconcile` turns unattached launch intents into `unknown`, preserves other
observations and moves incomplete staging files into quarantine. It never
relaunches, deletes objects, resets deadlines or declares a worker stopped.

Real access, subscription, quota or permission interruption leaves affected work
blocked and unfinished. Preserve failed receipts. If the Codex lead is
unavailable, checkpoint and stop. For a Claude collaborator, the skill presents
Wait for Claude / Continue with an available configured Codex model. The explicit
`assignment handoff` contract and Python helper `handoff --input FILE` are
specified end to end in [quota-aware continuation](../skills/agents-collab/references/backend.md#quota-aware-continuation).
The host must retain the actual owner decision and establish original absence.
The engine requires an interrupted unfinished slot, reconciled absence receipts
and nonempty `decision_evidence` references to registered objects. It does not
verify those objects' type, decision content or human authority; an unrelated
artifact hash satisfies the reference check without proving consent. It can
then record continuation on the exact packet. The operation
preserves observations, results, current partial writer source, deadlines and
review caps; it records a distinct requested model and execution identity.
Waiting is not completion. No automatic substitution, alternate account, paid
path or retry exists. Unknown provider usage remains unknown; the record imposes no experiment
call, token, context or quota budgets.

A completion input has the current artifact and exact evidence coverage:

```json
{"artifact":"ARTIFACT","criteria":{"C1":["OBJECT"]},"checks":{"offline-tests":["OBJECT"]},"approvals":{"owner":["OBJECT"]},"reason":"Explain why the approved criteria are met"}
```

```sh
"$CLI" task complete --record "$RECORD" --input "$INPUT/completion.json" \
  --actor owner --key complete-1 --expect 12 --json
"$CLI" task export --record "$RECORD" --input "$INPUT/export.json" --json
```

Completion requires active state, required current-identity reviewer passes,
resolved compatible material findings (a disposition never overrides a current
`changes_required` verdict; only a changed artifact and passing follow-up can), no prepared/launching/running/unknown or
blocked/interrupted assignment, all declared criterion/check/approval references and unchanged
live source identity. Imported evidence may be false; structure cannot establish
real authorization or truthful test outcomes. Evidence bytes should contain the
actual check/approval, not merely a coordinator's assertion.

`export.json` is, for example, `{ "fields": ["state", "revision", "reviews"] }`.
Allowed explicit fields are `spec`, `state`, `revision`, `artifacts`,
`current_artifact`, `packets`, `assignments`, `reviews`, `findings`,
`invalid_results`, `events`, `completion`, `review_extensions`,
`commit_acceptances`, `current_commit_acceptance`. Profiles and raw object directories
are not exported automatically. **Selection is not sanitization:** these records
can contain private paths, model preferences and text. Inspect/redact them before
sharing; the binary cannot determine the intended audience.

## Explicit acceptance of a reviewed commit

A normal Git commit changes HEAD and status even when it commits exactly the
reviewed staged work. Ordinary `check` and `complete` keep their strict frozen
identity checks. The low-level `task accept-commit` operation explicitly binds
the current approved artifact to one exact current descendant commit:

```json
{"artifact":"ARTIFACT","commit":"FULL_CURRENT_HEAD_HASH","authority":"owner","decision_evidence":["OBJECT"],"reason":"Explain the authorized acceptance of the reviewed staged tree"}
```

```sh
"$CLI" task accept-commit --record "$RECORD" --input "$INPUT/accept-commit.json" \
  --actor owner --key accept-commit-1 --expect 12 --json
```

Use the actual revision from the preceding response. The actor must match a
registered decision authority, the reason must be nonempty, and decision evidence
must reference retained objects. These checks establish a declared decision and
attribution, not human authentication or the truth of those evidence bytes. The
host must establish the real authorization and coordinate a quiescent source.

Acceptance requires active or blocked state, all required current-artifact
reviews passing, no unfinished/blocked/interrupted assignment, and resolved
compatible material findings. It does not activate or complete the task. A
blocked task may then be explicitly activated and completed using the original
artifact and existing completion evidence. A disposition cannot override a
current `changes_required` verdict.

Verification requires all of the following on repeated scans:

- The supplied full hash is current HEAD and a strict descendant of frozen HEAD.
- The **complete** current index matches the frozen index, and the entire HEAD
  tree matches that index, including omitted paths.
- Every tracked index path has its committed bytes, type and Git mode in the
  worktree; direct reads detect changes hidden by assume-unchanged or skip-worktree
  flags. Status must also contain no tracked or nonignored untracked changes.
- Every selected working entry still has its reviewed bytes, length, type and
  exact filesystem mode, and is represented by the frozen staged version.
  Selected ignored or unstaged-only evidence cannot be accepted merely because
  other files were committed. Deleted selected entries must remain deleted.

Submodules, unmerged indexes, unsafe paths, case-aliased index paths and
distinct paths resolving to the same filesystem object (including hardlinks)
are refused. Filters or checkout transformations whose working bytes differ from
Git blobs are conservatively refused. This performs no Git writes. The repeated
scans detect observed drift but do not establish an atomic snapshot against an
external editor; coordinated quiescence remains necessary.

The operation appends a content-addressed binding and audit event. Original
artifacts, packets, assignments, reviews, findings, profile, caps and earlier
objects/events remain unchanged. No replacement snapshot or review reset is
needed. `check`, `activate`, `reconcile` and `complete` subsequently verify the
bound post-commit identity and reject later drift (including a later commit with
identical contents). `check` reports drift as a completion blocker. Frozen
inspection and export remain available without the source. A genuinely new
artifact invalidates the active binding and requires its own reviews; historical
bindings remain retained and cannot authorize the new artifact.

Only one active binding is allowed. Identical operation-key retries return the
original receipt under the existing revision/idempotency contract, even after
later source changes; they do not revalidate the source. Use `check` for a fresh
verification. A different request using the same key fails.

## Storage and failure limits

Each task has `state.sqlite3`, `objects/`, `staging/` and `quarantine/`.
Format 1 records include stable identifiers, actor/provenance and UTC times under
a versioned enclosing task state. The first explicit `assignment handoff`
transaction upgrades both SQL marker and enclosing state to format 2; ordinary
records stay format 1. The first explicit `task extend-review` upgrades SQL and
enclosing state to format 3, retaining append-only review allowances separately
from the frozen profile. The first explicit `task accept-commit` upgrades SQL
and enclosing state transactionally to format 4, retaining its post-commit
binding separately from original artifacts. Later handoffs and review amendments
preserve the highest format. This engine reads formats 1–4; older engines refuse
unsupported formats before decoding their semantics. JSON response envelopes remain
schema 1. There is no downgrade or silent profile migration. SQLite stores the
complete typed state in one row with revision and operation-key constraints; references are checked in the
application, not independent relational foreign-key tables. Apart from the
explicit handoff/review-amendment/commit-acceptance upgrades, incompatible formats
require an explicit supported migration; preserve originals.

Runtime checks currently allow only local APFS on macOS. Network storage, other
filesystems and other platforms are refused. The configured root must exist;
missing volumes never cause a fallback. Full record paths are resolved and
checked against the source repository and any containing Git repository;
traversal, symlink ancestry and overlapping source/storage targets fail before
record creation. New private directories use 0700 and objects/database use 0600.
This is OS access control, not isolation against the same user or root.

Short SQLite immediate transactions serialize callers, with a five-second busy
wait and revision conflicts requiring inspection. `DELETE` journal mode with
`synchronous=FULL` is used. Exclusive staging writes are flushed, published with
an atomic same-filesystem hard link without replacement, and directory-synced
before database references commit. A crash may leave orphan objects or staging;
committed records must not refer to unpublished bytes. Missing/corrupted objects
block reads/mutations and completion; reconciliation does not fabricate repair.
Keep originals for manual recovery, including uncertain operation responses.

Tests abruptly exit subprocesses after write, flush, publication, before commit
and after commit; retry after a committed-but-unacknowledged operation returns
its cached response. They also inject an ENOSPC error, conflicting concurrent
mutations/imports and external capture drift. Test-only environment hooks are
`AGENTS_COLLAB_FAULT=crash:object-written|crash:object-synced|crash:object-published|crash:before-commit|crash:after-commit`,
`AGENTS_COLLAB_FAULT=no-space`, the same boundary names without `crash:` for
ordinary error injection, and `AGENTS_COLLAB_CAPTURE_PAUSE=test` for a short
capture-race handshake. Leave these unset in normal use. Abrupt process tests
are not power-loss testing or a universal hardware/filesystem durability claim.

No exactly-once external launch guarantee exists without host cooperation. The
optional skill adapter and offline installer integrate local records with the
host-led procedure. They add no model dispatcher, deadline supervisor, filesystem
sandbox, source restore, implicit routing, daemon or MCP server.
