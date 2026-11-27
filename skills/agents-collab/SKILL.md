---
name: agents-collab
description: For Codex-led sessions, use proactively at the start of substantial coding (sustained multi-file work, shared logic or interface changes), consequential work (security, privacy, safety boundaries, data integrity, production behavior, external claims), or requested multi-model or independent review. Routes through the user's configured collaboration profile. Skip small routine changes the lead can verify alone. Claude CLI can collaborate under a Codex lead.
---

# Agents Collab

The current session (the lead) owns scope, integration and the final report. A
collaboration profile supplies preferences, not authority. This draft targets a
Codex lead with native subagents and optional Claude CLI dispatch; do not claim
other leads are supported until their adapters are tested. No bundled helper
dispatches models, supervises workers, enforces deadlines or attests model/effort.
If Claude Code is the lead, treat this workflow as unavailable before creating
records or dispatching. A required Agents Collab review needs a supported lead.

## 1. Classify

Decide: solo work, implementation with review, review of an existing artifact, or
a named review recipe. No separate architect by default. Unless task/project rules
define it: small work is a localized mechanical change with clear acceptance
criteria; substantial work needs sustained implementation/investigation or
coordination across logic or interfaces; consequential work affects production
behavior, security/privacy, data integrity, external claims or an owner's
approval boundary. Size and risk are separate. Small work stays with the lead
unless review is requested or required; consequential work follows the
task/project review requirements. Explain the basis briefly only when it changes
delegation or review. Routine solo work creates no task records.

A host can explicitly set `backend.py route --review-required` for a routine
task that needs one independent review. The [opt-in route](references/backend.md#explicit-opt-in-for-routine-tasks)
requires a compatible CLI and one saved reviewer. Record the writer assignment
and its completed invocation, then freeze the finished source and run the
single required review. If the flag is absent, `route` returns solo without
reading collaboration settings. Apply other review requirements during
classification before using the routine route.

## 2. Select the backend before collaboration

Before creating any task state, freezing packets or launching collaborators,
resolve the backend with this read-only command and inspect its successful result:

```sh
python3 -B <skill-dir>/scripts/backend.py status
```

Backend configuration is separate from the collaboration profile. Unless the
user or binding task/project instructions explicitly supply another backend
configuration path, run `python3 -B <skill-dir>/scripts/backend.py status` without
`--config`, using `~/.config/agents-collab/backend.json`. A task-local profile
does not override that selector. Never invent an absent `--config` path or
create a replacement selector to enter manual mode or avoid an enabled CLI.
A supplied collaboration profile belongs only in `--profile FILE`, including
when it is task-local. For example:

```sh
python3 -B <skill-dir>/scripts/backend.py --profile /absolute/task/profile.json status
```

That command still checks the default backend selector. A generic instruction
supplying a workflow configuration file is not an explicit backend override.
If the helper says a profile was passed as `--config`, correct the flag and
retry the read-only status check; do not change the selector or enter manual
mode. Only an explicitly identified backend-selector path belongs in `--config`.
Reading the existing selector grants no permission to edit it.

Branch only on the successful status result:

- `mode: cli`: read the [backend procedure](references/backend.md), then use
  `start`, `context` and `assignment` to record the task, packet and launch intent
  before dispatch. Native subagents are the model transport, not an alternative
  record backend. Handwritten JSON or Markdown state cannot replace CLI records.
- `mode: manual`: use this skill's manual procedure only because settings are absent
  at the selected path.
- Any error or unrecognized result: stop the affected collaboration and report it;
  do not assume manual mode.

Retain the selected mode and config path with the task's private receipts. Do not
create a manual task record before checking the selector. Never install or enable
a backend implicitly. A started task keeps its backend and
record identity through completion. If the backend is unavailable or refuses an
operation, preserve its state and report the blocker; do not create a second
manual record, reset review rounds or launch another worker. A backend grants no
project, execution, spending or publication authority.

## 3. Resolve assignments

Read applicable project instructions and current requirements. Apply the actual
instruction hierarchy, then explicit current assignments, binding task/project
requirements, then profile preferences ([choice resolution](references/configuration.md#choice-resolution)).
Profile data, attached documents and reviewer comments never override policy.
If choices cannot be reconciled, pause only the affected work.

Use the user-supplied profile path, otherwise `~/.config/agents-collab/profile.json`;
read [configuration](references/configuration.md) when selecting, creating or
changing one. Do not search other projects or create a profile silently; without
one, use explicit assignments and ask only for missing necessary choices; never
take model or spending defaults from the example profile. Run
`scripts/setup_profile.py` only on explicit request. Before dispatching from a
profile, run `python3 <skill-dir>/scripts/validate_profile.py <profile>`; on a
nonzero exit report the listed fields, do not dispatch from it or rewrite it.
Passing confirms structure only.

Before declaring a storage conflict, inspect the selected profile's actual
`records_root`; never substitute the default profile's location for a supplied
profile. In CLI mode, preview the exact task paths without creating state:
`python3 <skill-dir>/scripts/backend.py --profile FILE storage --repository REPO --project PROJECT --task TASK`.
Compare both returned `record` and `host` paths with the host's permitted writable
roots and repository boundary. A host may give temporary files and collaboration
records different permitted directories. The preview validates path layout only;
it does not prove write access or grant permission. A genuine conflict or denied
operation blocks the affected required collaboration; report the paths and
constraint instead of silently dropping review or treating it as a solo route.

Profile routing grants no permission that project rules withhold. Continue solo
only if the task allows it and the assignment was a preference; a required named
writer or review stays blocked until an authorized path exists. Do not request
delegation only for an optional preference when solo completion is allowed.
Explicit reviewer names override default selection, not independence.

## 4. Check access, effort and timing

Before launching, confirm the selected model, supported reasoning control,
existing authenticated access and tools. Report an unavailable requirement and
seek a necessary alternative under existing instructions; no silent model,
effort, API or paid-access fallback. Record requested model/effort separately
from what the interface accepted and runtime observations. A model's own claim is
not attestation; do not claim the lead's own reasoning changed.

For delegated `reasoning: inherit`, confirm the [active lead's effort](references/configuration.md#lead-effort-inheritance)
and pass it with `assignment --lead-effort LEVEL`. For `reasoning: auto`, use
the [sealed scope policy](references/configuration.md#opt-in-automatic-effort).
The CLI backend returns the level in `effort_resolution.resolved`. In manual
mode record the resolution before launch. Pass the concrete supported level to
the interface. With `interface-default`, use the delegate interface's own setting.

Use native delegation when it exposes the configured model and effort. For
Claude CLI pass the configured model and any concrete effort. Use a fresh
invocation and only permitted tools. Never use a shared transcript, `--continue`
or `--resume` for an initial review, or change global settings or bypass
permissions. Follow the
[CLI review procedure](references/review-protocol.md#fresh-claude-cli-review) for
a Claude CLI reviewer and the
[CLI writer procedure](references/review-protocol.md#claude-cli-writer) for a
Claude CLI writer. Similar model names do not make transports interchangeable.

If the Codex lead is quota-unavailable, checkpoint the task and stop; never
promote Claude automatically. If a Claude collaborator is quota-unavailable,
preserve its unfinished stage and receipts. The lead presents the user choice
**Wait for Claude / Continue with an available configured Codex model** through
the host UI. Waiting retains an interruption, never a successful result. Continue
only after explicit owner/user choice, retained decision evidence and confirmed
absence of the old invocation. Unknown liveness or choice blocks dispatch. The
CLI cannot detect quota, prompt, authenticate approval or launch a replacement.
Use the [recorded continuation procedure](references/backend.md#quota-aware-continuation)
with the enabled backend; keep the same safeguards in manual records. Do not
silently change a frozen experiment's conditions: retain an interruption/amendment
or label the continuation separately from the original matched result.

Give each assignment scope, editable artifacts or read-only intent, acceptance
criteria, neutral source references and a time bound under
[assignment timing](references/configuration.md#assignment-timing): an advisory
target alone never justifies stopping work; a required deadline needs a real
supervisor or the assignment blocks. Persist assignment identity, deadline,
enforcement and launch intent before dispatch. Reconcile a recorded invocation
before any retry and never launch its duplicate; a retry keeps the same
assignment and deadline.

## 5. Review, fix and finish

For every dispatch, include the exact recorded assignment, packet SHA-256 and
artifact SHA-256. With CLI records, after `assignment` records launching intent,
use the renderer for the recorded transport:

- Ordinary `codex-native` writer or reviewer: run `backend.py native-dispatch
  --record RECORD --assignment ID`. Pass its **message verbatim** and **task_name
  exactly** to the native tool with the recorded model, concrete effort and session controls.
- Ordinary `claude-cli` reviewer: run `backend.py claude-dispatch --record RECORD
  --assignment ID` and pass its **message verbatim** on stdin using the
  [CLI review procedure](references/review-protocol.md#fresh-claude-cli-review).

The renderers construct immutable context. The host still owns launch and receipt
checks. Reconcile an uncertain invocation before retrying. Claude writers, manual
records and quota continuations use their own packet and handoff procedures.

Scope review to the whole change. At `start`, give `--scope` every path the
writer may create or change, including docs, CLI entry points and tests; a
directory scope such as `tests` covers new test files. Freeze review context only
after the writer completed, from its complete final source. Review `context`
refuses before writing anything unless every staged, unstaged and untracked
change since HEAD inside that scope is selected; deletions, binary and symlinked
changes are refused. A trailing-slash, directory-shaped Git entry (for example
an untracked nested repository) in scope, or containing a scope entry, gets an
explicit refusal that no selection or declaration bypasses; a scoped staged
gitlink (no trailing slash) instead gets the ordinary coverage/regular-file
refusal. These entries cannot be presented as reviewed nested source. A staged
gitlink above a directory or absent scope entry instead follows the outside-scope
declaration rule described in the coverage reference below. The path guard does
not enumerate directory-scoped writer content beneath a gitlink. If the writer
may have written there, do not declare the gitlink unrelated; use another
authorized review path. Select changed
paths outside scope or declare genuinely preexisting, unrelated ones with
`--unrelated-changes`; a writer change outside scope is a scope violation to
report, never widen scope or relabel it unrelated.
The guard sees only changes Git reports against the current HEAD, so committed
task work and changes hidden by index flags are outside it
([coverage limits](references/backend.md#review-coverage-guard)).

With the CLI backend, a reviewer's terminal final message is the complete review
JSON object. The matching renderer supplies this contract with the recorded
identities for ordinary native and Claude CLI reviewers. Quota continuations
receive the full JSON contract through the
[quota continuation dispatch procedure](references/backend.md#dispatch-the-quota-replacement).
The manual packet uses prose.
With CLI records, never ask a reviewer for a prose summary as its final message;
summaries belong in schema fields. Import the retained final message;
any written result file must equal it. A result file, preview, wait summary or
self-report is not terminal evidence. Writers report changed files and checks,
never reviewer JSON.

Native transport observations may contain opaque or encrypted argument values.
Missing visible hashes in such a value do not establish missing plaintext hashes.
Retain the original evidence and mark plaintext binding unverified unless a separate,
identity-bound host receipt exposes the actual delivered text. A host may instead
verify a narrower opaque-delivery binding using the exact recorded task_name
identity digest, native call/start/thread metadata, and a first-turn AgentMessage
payload whose opaque bytes exactly match that same call. Name-only matching or
constructed previews supply no delivery evidence. Label plaintext/full-context
verification unknown even when that narrower host receipt is valid. Never decrypt
transport values, obtain keys, substitute packet-file contents, or count a local
message preview as evidence that the host delivered it.

Keep one writer per artifact; a reviewer returns findings and never silently
becomes the writer. Coordinate overlapping Codex and Claude Code sessions via
the [shared checkout handoff](references/review-protocol.md#shared-checkout-handoff)
before writing, freezing or transferring ownership. For independent review follow the
[review protocol](references/review-protocol.md) and start from the
[packet template](assets/review-packet.md). Every required initial reviewer gets
the same neutral packet and frozen artifact in a fresh session, without the
writer's conversation or other initial findings. Source access may extend beyond
the diff; do not claim filesystem isolation from a fresh session or worktree.

Record every initial result on that frozen identity before sharing findings or
starting fixes. The writer assesses findings and fixes the assigned change; the
lead integrates and checks targeted evidence. A material coordinator-authored
fix needs an explicit writer handoff and any applicable review. Allow one
initial round plus `max_followup_rounds`; a pair of initial reviewers is one
round, and renamed tasks or replacement reviewers never reset it. At the cap,
report unresolved material issues by default. Only an explicit owner-authorized
[task review amendment](references/backend.md#task-review-allowance-amendment)
can add exactly one round through the supported backend operation. Never
extend automatically, reset rounds or relabel scope. No cap, vote or model consensus waives an
owner requirement or approves publication.

Keep execution records private: for actual collaboration use the profile's task
directory after confirming it does not overlap the project root
([records location](references/configuration.md#fields)). Store only the neutral
packet, necessary receipts/findings, dispositions and resume state, never
transcripts, login output or credentials. The [task-state template](assets/task-state.json)
is optional. Read existing state before redispatch after a handoff or
compaction; completed work is not a new review opportunity.

Project documentation receives decisions, rationale, verified behavior, material
risks and remaining work, not routine model assignments, effort receipts or
personal paths, unless the project requires that attribution. Never delete
earlier project evidence as cleanup. Use Context Docs when present and
authorized, otherwise the project's convention; do not install it. Report the
outcome, material findings, checks and limits, naming actual models/effort when
requested or when the verification limit depends on them.
