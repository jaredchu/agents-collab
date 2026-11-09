# Collaboration profile contract

This is the version 1 contract. The executing agent interprets it; neither
Codex nor Claude automatically applies these JSON fields as native settings.
The package includes a structural validator (`scripts/validate_profile.py`), an
interactive setup wizard (`scripts/setup_profile.py`), inert templates and
optional backend/installer helpers. No helper dispatches or supervises models.

## Interactive setup

On explicit user request, never silently during other work:

```sh
python3 path/to/agents-collab/scripts/setup_profile.py [--output PATH] [--dry-run] [--replace]
```

The wizard keeps the lead as `host`/`current`/`inherit` and asks for a writer
(current lead or a delegated model ID with `codex-native` or `claude-cli`), zero
or more reviewers, each agent's reasoning request (`inherit`, a common level or
a custom lowercase level), a profile label and `records_root`. It uses
`supported-control`, `existing-authorized-access`, advisory example bounds and
one follow-up round; edit the file to change them. With reviewers, default
consequential review is `single`; with several, it adds a named recipe listing
all of them, which applies only when requested. It validates with the bundled
validator, previews, and writes only after confirmation (default
`~/.config/agents-collab/profile.json`, mode 0600, atomic, no backups). It
keeps an existing profile unless `--replace` is given and confirmed, and never
follows or replaces a symlink or nonregular target. It requests no credentials
and calls no model. A generated profile establishes structure only, not model
availability, supported effort, access or records-path isolation.

## Location and loading

Optional executable-backend preferences live separately in
`~/.config/agents-collab/backend.json`; they are not v1 collaboration-profile
fields. The backend installer can enable an explicitly installed CLI without
rewriting the profile. See [the backend procedure](backend.md). With no backend
setting, this skill keeps its manual procedure. Do not add backend keys to this
profile or silently migrate it.

Use an explicit profile path supplied by the user; otherwise use
`~/.config/agents-collab/profile.json`. Read only that file. User defaults
remain outside project repositories and outside the distributed skill. A team
may explicitly select a shared profile in its own project; keep credentials,
private paths and individual preferences out of that shared configuration.
Never export a user's profile into a project automatically. Example profiles
are templates, never executable defaults or auto-selected policy.

Resolve `~` for the current owner, not a repository author. Derive project/task
directory names from safe single path components and create unique task IDs.
Never accept traversal, separator injection or a task-selected storage root.
Respect existing storage rules; unavailable required storage is not permission
to fall back elsewhere. Avoid personal/account identifiers in project outputs.

## Fields

| Key | Meaning |
| --- | --- |
| `version` | Integer `1`; stop profile resolution on another version |
| `name` | Profile label, not a model instruction |
| `agents` | Named entries: exact model, transport, reasoning selection |
| `routing.small_writer` | Agent name or `current-session` |
| `routing.substantial_writer` | Agent name or `current-session` |
| `review.on_consequential_work` | `single` or `none`; project/task requirements still apply |
| `review.candidates` | Ordered configured agents for default review selection |
| `review.prefer_different_model` | Choose an available different model by default; never replace explicit names |
| `review.recipes` | Named lists of reviewers, activated by explicit request or applicable policy |
| `review.max_followup_rounds` | Nonnegative integer after one initial round |
| `effort_check` | `supported-control` or the stronger `runtime-attestation` requirement |
| `access` | `existing-subscriptions` or `existing-authorized-access`; no new access or fallback |
| `bounds.enforcement` | `required` for a supervised deadline, or `advisory` for a labeled target; binding task/project limits still apply |
| `bounds.writer_minutes` | Positive integer, per delegated writing/implementation assignment |
| `bounds.reviewer_minutes` | Positive integer, per reviewer assignment |
| `bounds.review_output_words` | Positive integer, target for concise findings |
| `records_root` | Private root outside the project repository |

Reject missing required keys, unknown keys, invalid types or agent references
before dispatch. Run the validator on the selected profile before any dispatch:

```sh
python3 path/to/agents-collab/scripts/validate_profile.py PROFILE.json
```

Exit status 0 means the structure matches this contract. Status 1 means invalid
profile content: malformed JSON, invalid UTF-8, a file over the size limit or
an invalid structure, listed by field where possible. Status 2 means an OS
error, unreadable or nonregular input (such as a directory or FIFO) or a
command-line usage error. A symlink to a regular file is followed. Treat any nonzero result as a
configuration issue to resolve with the user. Do not repair or rewrite the
profile silently. The validator reads JSON only. It does not check model
availability, credentials, reasoning controls, permissions or the resolved
records location, and it does not expand `~`. If Python is unavailable, apply
the same rules manually and report that mechanical validation did not run.

Every top-level key listed above is required. Every listed section field is
required. Empty candidates/recipes are valid only when no review is configured.
`on_consequential_work: single` needs at least one candidate. Duplicate keys,
booleans in integer fields and non-integer numbers are errors. Each agent has
exactly `model`, `transport`, `reasoning`. Agent and recipe names use 1-40
letters, digits, `_` or `-`; `current-session` is reserved for routing. Recipe
names map to nonempty, unique lists of configured agents. Duplicate agents in a
recipe are configuration errors, not two independent reviewers. Candidates and
recipe members cannot be a `host` agent, because the lead is not a fresh reviewer.

`model` is an exact identifier or `current`. `current` with `transport: host`
means the existing lead; it does not request a model switch or a fresh reviewer.
In v1 `current` is valid only with `host`, and `host` requires `current`: the
skill cannot switch the lead's model. State a required lead model in task or
project instructions instead. At most one agent may use `host`. Model
identifiers contain no whitespace and cannot start with `-`.
Allowed transports are `host`, `codex-native`, `claude-cli`. The first design
targets a Codex lead: `codex-native` requires native delegation tools, and
`claude-cli` requires the installed authenticated CLI. Unsupported transports
block the affected assignment; do not silently substitute an adapter.
Codex-led is the first pilot target, not an already validated runtime. Loading
the Markdown from another lead does not establish adapter support.

`reasoning` is `inherit` or a named level the selected model actually supports,
written in lowercase as the interface documents it. `default` and `current` are
rejected as ambiguous. The validator checks only the format, not whether a model
supports that level. Never assume identical effort vocabularies across providers. `inherit` explicitly
allows the current supported setting; it does not mean High. For a named level,
support and acceptance of the control must be checked. With `supported-control`,
record unavailable runtime effort as unknown. With `runtime-attestation`, stop
the affected run unless independent runtime evidence establishes the level.
This stronger option may be unusable on a particular interface; a model's own
assertion cannot satisfy it. An inherited lead setting needs no invented dispatch
control; an explicitly required lead effort must still be checked or resolved.

The private directory layout is fixed as `{project}/{task}/collaboration` under
`records_root`. Project handoff always contains durable outcomes. Neither is a
configurable policy switch in v1. Fallback behavior is deliberately absent: an
unavailable required assignment needs a new authorized choice, not an automatic
alternative. The portable example's storage location is illustrative; choose a
root compatible with the actual owner's storage rules before running it.

`records_root` must be absolute or start with `~/`. It cannot be relative, use a
`~user` form, contain `.`/`..` components or control characters, or be the
filesystem root or home directory itself. These are lexical checks. Before
creating records, the executing agent must expand `~` for the current owner,
resolve the actual directory and confirm it is outside the project and any
shared repository. A symlink can defeat a lexical check.

That confirmation is a dynamic lead check on the final target, not something the
validator enforces. Resolve the full task directory
(`{records_root}/{project}/{task}/collaboration`), following symlinks in every
existing component, and the actual project root. Reject the target if either
path contains the other. A `records_root` that is merely an ancestor of
project trees is not a collision by itself; the final task directory decides.
Complete this check before creating any directory, file or symlink, and stop
if either path cannot be resolved.

Create the task record only when collaboration actually begins. The
[task-state template](../assets/task-state.json) is a starting point, not a
schema or a requirement to record solo work.

## Choice resolution

1. Apply the actual system/organization/project/user instruction hierarchy.
2. Within remaining choices, honor explicit current model, effort and review recipe.
3. Use binding task/project requirements, then personal profile defaults.
4. Use host defaults only for fields explicitly set to `current` or `inherit`.

This list is a preference-resolution procedure, not a replacement instruction
hierarchy. If a project mandates a writer and the profile prefers another, use
the mandated writer. If an explicit user request conflicts with another binding
rule and its authority is uncertain, surface that conflict without silently
rewriting project policy. Profiles never authorize production or publication.

For default single review, choose the first usable candidate different from the
writer model when preferred. Do not use the current lead as a fresh reviewer.
Compare canonical model IDs where the interface supplies them, otherwise exact
requested IDs. Different IDs establish only model selection diversity, not
different vendors, architectures or statistically independent errors. If the
actual writer identity is unknown, do not claim this comparison was established.
If only the writer's model is usable and different-model selection was merely a
preference, disclose that limitation and use a fresh session only when permitted;
if diversity is required by the task/project, stop. Explicit pairs retain the
requested models. A same-model fresh review is session-independent, not evidence
of model diversity. Do not count a writer's own session as independent review.

## Configuration versus native defaults

Codex's native model/subagent settings and Claude's CLI flags set actual runtime
preferences. This profile tells the skill which settings to request and check.
It cannot retroactively change the active lead's effort or enforce permissions.
Do not edit a host configuration as an incidental part of using this skill.

Choose model entries, reasoning settings, storage and bounds for the actual user
or team. No particular model, vendor pair, effort level or storage convention is
mandatory. The example's numeric bounds are illustrative, not universal limits.
Profile settings do not relax an existing instruction requiring stronger proof.

## Assignment timing

Minute values are wall-clock allowances from the assignment's first launch,
including time spent interrupted or awaiting resume. Retries keep the original
deadline; they do not receive a fresh allowance. A new focused follow-up is a
separate assignment with its own budget within the existing review-round cap.

With `bounds.enforcement: required`, establish an available supervisor before
launch. For example, a parent process can use a subprocess timeout to terminate
a CLI invocation; it must also account for any surviving worker processes before
retry. A supported harness deadline is another valid mechanism. A deadline field,
prompt instruction or periodic manual check alone is not enforcement. If the
transport cannot meet a required deadline, block that assignment until a compatible
path or explicit authorized timing change exists. Do not claim that every native
subagent interface provides this control.

With `advisory`, record and report the target as advisory, monitor where practical,
and honor any stricter task/project requirement. Do not label such a run time-limited
by technical enforcement. Persist the effective timing policy and supervisor with
the invocation state described in the review protocol. The example profiles use
advisory targets; a task/project hard deadline still requires supervision. A user
can select required timing in the profile without changing the skill.
