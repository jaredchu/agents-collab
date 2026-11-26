# Agents Collab verification history

These dated checkpoints record source, validation and publication observations
as of each entry. Commands, test totals and release status described here refer
to those snapshots. See the [project context](project-context.md) for current
status and open work, the [CLI guide](cli.md) for current backend behavior, and
the [release notes](releases/v0.1.1.md) for the published package.

## Publication, setup wizard and site (8–9 November 2026)

On 2026-11-08 the owner selected the MIT License and
https://github.com/jaredchu/agents-collab as the public repository
(license URL: https://github.com/jaredchu/agents-collab/blob/main/LICENSE).
On the same date the repository was published publicly and GitHub recognized
its MIT License. https://agents-collab.com serves the public website with an
active custom-domain certificate. The initial publication preceded the
first versioned release.

Root and package `LICENSE` files exist, and the website and documentation link
the repository and its license. At publication the download archive held nine
files.

`tests/` holds the portable suite (validator tests ported without the
private-profile test, plus setup-wizard, privacy, license, website and build
checks). On 2026-11-08, before the setup wizard, all 70 tests passed. The
eight workflow-file hashes matched the validated source, and the deterministic
download contained those eight files and the identical MIT notice; documented
ZIP and checkout installation flows preserve existing installations and profiles.

The package now also ships `scripts/setup_profile.py`, an offline,
standard-library profile wizard run explicitly after installation. It keeps the
lead as `host`/`current`/`inherit`, asks for a writer, zero or more reviewers
and per-agent reasoning requests, uses neutral access and advisory bounds,
reuses the unchanged validator, previews, and writes only after confirmation
(mode 0600, atomic, preserving existing profiles and rejecting symlink or
nonregular targets). A generated profile does not establish model availability,
supported effort, access or records-path isolation. At the setup-wizard
publication, the download archive held ten files. On 2026-11-08 all 90 tests passed after the addition and cleanup-error correction, with
profile writes tested only at temporary output paths. Skill metadata validation,
the website build, both manual install paths and installation of all ten files
through Skills CLI 1.7.6 passed. The installed wizard produced a valid profile
with mode 0600; a terminal run exercised a writer and two reviewers, and Ctrl-C
at a prompt left no target file. All writes used temporary test paths. These checks establish configuration behavior, not model availability
or runtime reasoning support. Local browser checks at 1440px and 390px passed, including the wizard command
copy buttons and content without JavaScript. Independent review found and resolved one staging-cleanup reporting issue;
the focused follow-up independently passed all 19 wizard tests. At that
publication the live package matched the checked ten-file build; its downloaded wizard created a
valid mode-0600 profile at a temporary output path, and the published home/guide
setup-command copy buttons passed desktop/mobile checks. A saved profile
with incomplete staging cleanup now reports its saved state and remaining file
with exit 3, rather than claiming a clean save or raising an uncaught error.

The complete Markdown setup was also exercised for ZIP and checkout installs
with both solo and writer/reviewer templates, including expected placeholder
rejection and structural validation with synthetic model IDs. These checks
do not establish actual provider access.

`scripts/build_website.py` builds `website/` into `dist/`, the static directory
in the hosting configuration. The build and internal links pass. Bounded local
Chrome checks cover all five routes at 1440px and 390px, page overflow,
code-copy success and denial, keyboard skip/navigation and content without
JavaScript. These checks are not a complete accessibility audit. Private
evidence and diagnostics remain outside this project. Public checks on
2026-11-08 repeated the five-route browser checks in fresh anonymous sessions;
the downloadable ZIP, checksums and profile example matched the validated build.
DNS and HTTPS were verified after configuration through Cloudflare.

The README and website offer a user-level Codex installation command through
Vercel’s Skills CLI, with Node.js 22.20+ and Git needed for installation and
Python 3.9+ for profile setup and validation. The CLI can replace existing skill
files on a repeat run. The guarded manual route preserves them. In the
2026-11-08 pre-wizard test, Skills CLI 1.7.6 installed all nine matching
package files in a temporary home-directory API fixture and
preserved a separate test profile. Other leads remain unvalidated.

All five website pages reference the generated abstract evergreen/rust favicon,
with 16/32/48px ICO entries, a 32px PNG and a 180px Apple touch icon. The 512px
source mark is retained with the static website assets.

## Public routing study (9 November 2026)

The [frozen protocol and results](../evals/automatic-routing/2026-11-09/report.md)
use public ProcLease commit 37975b5 and authored tickets in disposable snapshots.
The protocol was published at e0cbaa3 before outcomes; initial independent review
and its one focused follow-up resolved three harness/fixture findings.
Ordinary prompts matched 1/3 expected routes: routine solo passed, substantial
writer/review and consequential review stayed solo. The 36-run comparison did
not start. Separate explicit-skill diagnostics loaded the skill and matched
all three routes without model names in the prompts. Available provider usage,
selected sanitized receipts and patches are recorded with all 36 unstarted rows.
No disabled-skill comparison or general effectiveness claim follows. Raw runs
are not fully independently auditable. Task changes stayed in disposable snapshots.

The study-only RPC recorder lives in `evals/`, outside the distributable package.
Activation/discovery remains the concrete unresolved product issue; that
study’s full usefulness comparison remains unperformed. Installation alone still provides
no dependable automatic-routing guarantee.

## Quality pilot: withdrawal and completed recovery (9 November 2026)

The unfinished study was removed from current public files at the owner's
request after an access interruption. Final grading was still incomplete. After access returned, a reviewed recovery amendment allowed only
the six missing anonymous assessments to resume, with new private labels,
restricted file tools and prior call time subtracted from grading allowances.
All source outputs and original criteria stayed frozen. Earlier failed attempts,
withdrawn operator observations and the recovery are retained in the
[completed report](../evals/quality/2026-11-09/report.md).

Both review paths fixed a reproduced no-option script regression missed by
self-check. The frozen primary rule gives B/A and C/A two wins; C/B has one
minor-test win and does not establish an added skill advantage. A sensitivity
excluding untargeted existing-test failures leaves only one initially material
draft, below the frozen floor, so the primary review advantage is not robust.
Q4's contradictory runtime wording remains disputed; two concrete test weaknesses
count minor. The final report supersedes earlier certainty about a quarantine
safety defect, preserves original failures and maintains actual grader ratings.

This does not establish general gains, reliable implicit activation or optimized
communication. Follow the [interruption policy](../CONTRIBUTING.md#interrupted-experiments)
for future blocked work: final results wait for all required stages.

## Rust CLI prototype (9 November 2026)

The owner authorized the [plan's](plans/rust-cli-prototype.md) first local
record-and-packet deliverable and meaningful offline fault/concurrency validation.
The separate source-only `cli/` crate now implements per-task SQLite state,
immutable selected artifacts/common packets, host receipt/result import,
revision/idempotency gates, separate writer-context and review packets, review
rounds, finding dispositions and checked completion. It neither dispatches models nor changes the distributable skill.

[CLI documentation](cli.md) is canonical for commands and current limits.
The implementation chooses bundled SQLite and runtime-limited local APFS/macOS
support; other storage is refused. Cooperative repeated-scan capture does not
prove atomic multi-file snapshots. Imported identity, truth, independence and
authority remain declarations; strong required timing/effort guarantees are
refused without a validated supervisor. Recovery preserves uncertainty and
original evidence, with no automatic retries, deadline resets or substitutions.

Synthetic offline tests cover normal and repaired handoffs, two required initial
reviewers, blocked/unknown recovery, invalid results, mixed Git state, concurrent
calls, abrupt process exits, simulated write exhaustion and corrupted/unavailable
storage. Independent review resolved five findings, including recovery-time
writer exclusivity; all 24 offline integration tests pass. The local core's
implementation review is complete. See [validation status](cli.md#validation-status)
for coverage and limits.

Only Rust/Cargo 1.99.1 on macOS/local APFS was exercised; process-crash checks are
not power-loss testing. No model quality, usage savings or usefulness conclusion
follows.

At this prototype stage (9 November 2026), live comparisons, dispatch, MCP and a
daemon remained unperformed and separately authorized work. The live comparison
was later completed as the [CLI usefulness comparison](#cli-usefulness-comparison-9-november-2026);
dispatch, MCP and a daemon remain unperformed. No artificial experiment usage
budget is imposed. Profile timing
semantics and real access interruptions remain distinct from those measurements.

## CLI usefulness comparison (9 November 2026)

The [completed report](../evals/cli-usefulness/2026-11-09/report.md) follows
preregistration at `8b18301`: three public-source tasks, six workflows, the same
skill and Sol/Astra requests, with or without the pinned local CLI. All final
code passed the required grouped checks (61/48/52 per arm), and both controlled
receipt gaps recovered the original invocation and timing. The CLI demonstrated
no added usefulness under the frozen rule. One shared coordinator provenance
mistake affected two CLI rows; originals and corrections remain visible.

The report is canonical for outcomes, baseline/execution deviations, first-use
coordination costs and unavailable usage. Those limits prevent a general quality,
speed, cost or equivalence claim. The skill, saved configuration and CLI under
test were unchanged; experimental validator patches were not merged into the
product. Source reproduction is public; raw execution evidence stays private.

## Optional backend integration (9 November 2026)

The skill now includes a reusable adapter and offline installer for the separate
macOS arm64 CLI package. Missing backend settings keep the manual workflow.
Explicit enablement uses `~/.config/agents-collab/backend.json`; the saved
collaboration profile is preserved. The [CLI guide](cli.md#optional-backend-installation)
is canonical for installation and the [backend reference](../skills/agents-collab/references/backend.md)
for host-led lifecycle use and limits. Readable packets currently support
selected regular UTF-8 files. No dispatcher, supervisor or automatic skill
activation is added.

The checked skill ZIP contains thirteen files. All 114 Python tests passed,
including five explicit real-CLI/APFS flows; the static build and skill metadata
validation passed. Independent review found no material implementation issue;
its minor stale-installer documentation finding was corrected. A separately
checked release archive installed successfully and its version probe passed.
That integration step made no versioned public binary release or website deployment.

An ordinary documentation task then corrected the CLI guide's stale live-validation
status through the installed adapter: declared scope and checks, frozen writer
and neutral review packets, actual independent review, imported original result,
retained check evidence and completed record with integrity verified. The task
preserved the other 344 source files and required no per-task lifecycle helper.
This verifies one supported operational path, not a quality or efficiency gain.

## Site discovery and Cloudflare hosting (9 November 2026)

Production at https://agents-collab.com now serves the checked static build
directly from Cloudflare Pages. `wrangler.toml` selects `dist/`; there are no
Pages Functions or application server. The custom domain, HTTPS, all nineteen
served files and downloads, a genuine 404 response, and cache headers were verified at deployment.

Cloudflare's Always Use HTTPS setting is enabled. A proxied `www` CNAME and
an exact-host Single Redirect permanently send `www.agents-collab.com` to
`https://agents-collab.com`, preserving paths and query strings. The HTTP apex
and both `www` variants reached the canonical HTTPS page in one redirect in
live checks, with valid TLS. These settings live in Cloudflare, outside `dist/`.

Five canonical pages have descriptive search/social metadata, visible project
credit/update dates and linked project/page data. `robots.txt`, `sitemap.xml`,
`llms.txt` and `manifest.json` expose consistent navigation and evidence limits.
The source remains readable without JavaScript and adds no external assets,
analytics or forms. All 119 local tests passed, including five real CLI flows;
desktop/mobile, keyboard and no-JavaScript checks passed. Independent source
review passed without findings. These checks establish implementation behavior,
not search indexing, rankings or AI citation gains.

The implementation follows relevant [NavSEO canonical guidance](https://navseo.com/learn/technical-seo/canonical-tags-and-duplicate-content/),
[entity clarity](https://navseo.com/learn/ai-citation-seo/structured-data-and-ai-visibility/)
and [research citation guidance](https://navseo.com/learn/ai-citation-seo/original-research-as-citation-assets/),
checked against [Google's AI search guidance](https://developers.google.com/search/docs/appearance/ai-features).
Keep visible claims and metadata consistent; discovery maps are navigation aids,
not special search requirements or indexing guarantees.

The [deployment workflow](../.github/workflows/deploy-site.yml) runs portable
tests and the static build on pull requests and pushes. Only a successful main
push or explicit main workflow run reaches Wrangler deployment. Official action
commits and Wrangler are pinned. GitHub token permission is read-only. Deploy
credentials are scoped to the guarded step. The five macOS/APFS runtime tests
require their explicit binary and do not run on Linux.
Immediately before deployment and again before live verification, canonical-main
lookups reject stale commits, including old reruns; lookup errors fail closed.
If `main` advances during upload, the later gate skips verification of the old build.
The post-deploy step compares every public `dist/` file with its HTTPS response,
mapping directory indexes to
their public routes and checking an unknown URL for the built 404 body and status.
Cloudflare configuration files are excluded. Mismatches or request failures retry
up to twelve passes within a three-minute step limit, then fail the workflow.
The Actions run, live-file check and Cloudflare deployment receipt establish each
release outcome; this single-run check is not continuous availability monitoring.

## Skill clarity and helper observation fixes (9 November 2026)

Two independent source reviews of the skill requested changes; the owner
approved fixing them. `SKILL.md` is now a short five-step decision flow that
links to canonical detail. [Assignment timing](../skills/agents-collab/references/configuration.md#assignment-timing)
is defined once, with a worked example: an advisory overrun is recorded and
reported rather than stopping work; a retry keeps its assignment and deadline;
a fix is a new assignment within the unchanged review cap. The
[backend reference](../skills/agents-collab/references/backend.md) is usable
without the source checkout, including conservative CLI limits and recovery
after partial helper failure.

The helper's `observe` no longer marks observations reconciled by default.
`--reconciled` and `--absence-established` are explicit host assertions that need
a reason; contradictory flags fail before any mutation. Callers that relied on
the old implicit reconciliation must now pass `--reconciled --reason`. The
source changes passed both independent reviews and their focused follow-up.
All 126 local tests passed, including eight real-CLI cases. The published
13-file package passed 20 backend tests in an isolated installed-only fixture;
automatic deployment verified all 19 public files. These checks establish
implementation behavior; no runtime quality or efficiency gain is claimed.

## Activation study draft, regression gate and backend clarifications (10 November 2026)

The owner confirmed implicit activation as the required product target and
authorized preparation, not execution. The [draft protocol](plans/implicit-activation-study.md)
specifies one frozen baseline description and one description-only candidate on
the original R1/S1/C1 tickets (18 lead runs). It requires independent method
review, owner execution approval and immutable preregistration before any call.
No installed skill, product description, profile or global instruction changed,
and the cancelled 36 comparison rows stay cancelled.

`scripts/check_cli.py` is a maintained local regression gate, not CI. From a
clean checkout it archives one pinned commit into new caller-selected scratch
outside Git, runs offline formatting, locked build, Clippy, Cargo tests and the
full Python suite against a frozen copy of the fresh binary, and refuses skipped
or missing real-engine coverage. See [the CLI guide](cli.md#local-regression-gate)
for use and evidence limits. The backend reference and helper help now state that
`evidence` runs a reconcile (quarantining incomplete staging, refusing unattached
launches) and that no finding disposition completes a task over a current
`changes_required` verdict. Lifecycle semantics are unchanged.

Local validation of `51bb150` passed on 10 November 2026: the maintained gate
completed formatting, locked build, Clippy with warnings denied, all 24 Rust
integration tests and all 139 Python tests, including ten real-engine cases.
The website build and affected documentation links passed. Independent source
and method review passed after a focused protocol correction for uncertain
launches and mandatory launch supervision. These results cover the local
implementation and draft method, not live supervisor feasibility, study
execution, achieved implicit activation or a production release.

## Quota-aware continuation source increment (10 November 2026)

The source adds an explicit host-led interrupted Claude-to-Codex continuation.
The skill presents Wait for Claude / Continue with an available configured Codex
model; an unavailable Codex lead checkpoints and stops. The record-only engine
requires retained decision evidence, latest reconciled original absence and the
same sealed stage, preserves original observations/results and review accounting,
and snapshots current partial writer source without restoring old files. Actual
quota diagnosis, user prompting, dispatch, approval and absence verification stay
with the host. See the [end-to-end contract](../skills/agents-collab/references/backend.md#quota-aware-continuation).

A task-local explicit Codex identity can supplement the frozen profile without
changing defaults. First handoff upgrades the record to format 2 so old CLIs
refuse new semantics; ordinary format-1 records remain compatible. Original
deadlines and review caps stay fixed. Frozen experiments remain interrupted or
amended/separately labelled, never silently substituted matched results. This
source increment does not establish publication, installation or provider runtime
behavior; validation and independent review are reported separately.

### Continuation session freshness correction (10 November 2026)

Invocation observations now reject reuse across assignments whenever either
assignment is a continuation, regardless of which records the invocation first.
Repeated observations within the same assignment remain valid. This checks
host-declared identities; it does not attest actual session independence.

A regression exercises both reviewer orders, rejects shared identities without
changing recorded state, and completes with distinct identities. It fails against
the previous implementation. Local dirty-source validation passed formatting,
locked offline build, Clippy with warnings denied, all 32 Rust integration tests
and 140 Python tests, including all 11 real-engine cases without skips. This is
not a clean-commit run of the maintained regression gate. The correction does
not change saved configuration or establish installation or publication.

## Skill parity and contract clarification (10 November 2026)

The source skill now carries the experimental proactive activation description
and the explicit backend-selector rule: a task-local profile does not select a
different backend configuration, and an absent scratch selector must not be
invented to enter manual mode. The description is an experimental routing
instruction, not evidence of dependable activation or broader model support.

The review packet template points to the canonical typed CLI return contract.
It distinguishes string fields from arrays and ordinary session descriptions
from the exact invocation string required by quota-continuation reviews. The
backend guide also distinguishes the host's obligation to retain a real decision
from the engine's check of registered object references. No engine, dispatcher,
profile preference or execution permission changes follow from these wording
clarifications. The activation draft retains its original descriptions and
records that current source and prior exposure need reconciliation before any
future preregistration. No experiment or publication is authorized here.

## Dotted project names (11 November 2026)

The adapter and Rust task validator now accept safe dot-separated project names
as one exact storage directory. Task and other identifiers retain their previous
rules. The [adapter contract](../skills/agents-collab/references/backend.md#identities-and-arguments)
defines the grammar and compatibility requirement. Configured-root resolution,
project/task symlink rejection, traversal checks and repository separation remain
in place. No symlink workaround is required for domain-style names.

Local source validation passed formatting, locked offline Cargo tests, Clippy
with warnings denied and all 143 Python tests, including all 12 real-engine cases
without skips. All 35 Rust integration tests passed. New coverage checks exact
dotted layouts, record reopening and the complete adapter lifecycle, invalid
names and the 40-character limit, and regular/dangling project and task symlink
rejection before creation. The new dotted lifecycle regression fails against the
previous executable at project validation. These results validate the source
change; they do not establish installation or publication.

## Task review allowance source increment (11 November 2026)

The source adds explicit owner-authorized task review amendments through
`task extend-review` and helper `extend-review`. At-cap reporting remains the
default. Each retained amendment adds exactly one round after every required
reviewer finishes the capped round and no invocation remains nonterminal.
The engine preserves the frozen profile/hash and prior history, derives both
packet and capture ceilings from the amendments, and retains existing approval
and completion gates. Authority/evidence are host declarations, not human
authentication. See the [operation contract](../skills/agents-collab/references/backend.md#task-review-allowance-amendment).

First amendment upgrades SQL and state to format 3 so previous engines refuse
new semantics; later quota handoffs preserve that format. Unamended format-1/2
records remain readable. This is a source increment, not evidence of installation,
publication, owner authentication or provider runtime behavior.

## Analytics injection disabled (11 November 2026)

The owner requested disabling the Cloudflare analytics beacon. The Pages
project's analytics fields were already unset; the injection came from enabled
zone-level Web Analytics/RUM. The project's RUM ruleset was disabled. The
[Cloudflare RUM update API](https://developers.cloudflare.com/api/resources/rum/subresources/site_info/methods/update/)
controls this separately from Pages analytics and site assets.

After propagation, all nineteen served files matched the deployed `4a71aa8`
build byte-for-byte, including the skill ZIP, checksums and genuine 404 response.
All six HTML files also matched under a browser user-agent: twenty-five HTTP
checks passed without a beacon or response normalization. This resolves the
earlier injected-script difference without requiring a new deployment. These
are point-in-time checks of the observed responses, not continuous monitoring.

## Backend selection gate (12 November 2026)

The source skill now resolves the backend before assignment planning or task
state creation. It explicitly branches on successful selector status: enabled
CLI records remain required with native model transport; only absent settings
permit manual records; an error stops collaboration. Status reports the selected
configuration path in both modes and a next-action reminder. These are host
workflow instructions, not executable enforcement that an agent reads or obeys
them. No dispatcher or implicit-activation guarantee is added.

Isolated regressions verify that a task-local profile cannot redirect default
backend selection, selected absent settings do not trigger a search elsewhere,
and status performs no task writes. All 146 Python tests passed, including the
thirteen real-engine cases without skips, and the static/package build passed.
No Rust engine behavior changed. This verifies local source behavior; installed
files, saved defaults, publication and participant routing were not changed or
remeasured by this increment.

## Selector argument handling and native identity guidance (12 November 2026)

The backend helper now accepts its shared `--config`, `--profile` and `--actor`
options before or after the command. Repeated identical values are accepted;
conflicting values fail before probing a binary or writing state. A
collaboration-profile-shaped file passed as `--config` gets a specific
`--profile` recovery message, with no automatic selector change or manual
fallback. A task-local profile still leaves the default selector unchanged.
The skill and [backend contract](../skills/agents-collab/references/backend.md#identities-and-arguments)
show that distinction explicitly, including generically supplied workflow files.

The [observation guidance](../skills/agents-collab/references/backend.md#observations-and-retries)
also distinguishes canonical native invocation paths from thread UUIDs. Hosts
must retain both and join receipts through unique, proven child source/parent
metadata, without guessing aliases or supplying missing dispatch evidence.
The record-only engine and its stored invocation strings are unchanged.

All 151 Python tests passed, including thirteen real-engine cases without skips.
New selector tests exercise option placement, profile misuse without probing or
writes, conflicting values and preservation of command argument values. These
checks establish the helper behavior; model adherence and future live receipt
availability remain unmeasured. This source increment does not install or
publish changes or rerun historical experiments.

## Exact sentinel argument correction (12 November 2026)

The shared-option normalizer now rejects the exact `--` scalar value with a
controlled argument error (exit 2), before hashing values, probing the backend
or writing state. This handles Python 3.9.6 argparse returning a nested empty
list for inputs such as `--actor=--`; the literal string is also rejected for
consistent behavior on runtimes that preserve it. The same rule applies to
`--config` and `--profile`. Other leading-dash values, command argument values,
option positions, identical repetitions and conflict rejection are preserved.
See the [argument contract](../skills/agents-collab/references/backend.md#identities-and-arguments).

All 154 Python tests passed, including thirteen real-engine cases without skips,
and the package/static build passed. New regressions cover all three shared
options in both positions, repetition/conflict cases, controlled exit without
backend activity or writes, and unaffected non-sentinel values. No Rust engine,
saved settings, installed skill or historical experiment was changed by this
source repair. These are local implementation checks, not participant-runtime
or implicit-activation evidence.

## Profile storage preview (12 November 2026)

The helper adds a read-only `storage` command that reports the selected profile,
resolved records root and exact task `record`/`host` paths using the same path
validation as `start`. It creates no task directories or operation traces and
does not test write permission or grant authority. The skill requires checking
the supplied profile and comparing both paths with actual host constraints
before declaring a storage conflict. A real conflict or denied operation still
blocks required collaboration; it does not justify silently dropping review.
See the [path preview contract](../skills/agents-collab/references/backend.md#identities-and-arguments).

Local checks pass all 158 Python tests, including fifteen real-engine cases
without skips, and the static/package build. New cases verify a supplied profile
with a different default, symlink-root resolution, preview/start path agreement,
no preview writes, and rejection of missing or repository-overlapping roots.
Portable stub-executable cases also cover explicit/default profiles, an existing
record path and absent-selector refusal without engine execution or fallback.
These checks establish path handling, not model adherence or write permission.
At this checkpoint, the increment had source validation only.

## Native dispatch identity rendering (12 November 2026)

The helper adds read-only `native-dispatch` for ordinary native assignments with
recorded launching intent. It renders the exact assignment, packet and artifact
identities plus registered immutable context into one message, with a UTF-8
digest. The lead passes that message string verbatim to the native host with
the recorded controls. The command refuses stale, non-native, already-observed,
terminal and quota-continuation cases and verifies record/object integrity.
It creates no state or workers and cannot authorize a launch, lease a worker,
check actual liveness or prove delivery. See the
[dispatch contract](../skills/agents-collab/references/backend.md#observations-and-retries).

Guidance now distinguishes readable input from opaque transport observations:
missing visible hashes in an opaque field do not prove missing plaintext
hashes. A local preview is not a delivery receipt, and an original spawn does
not bind a later assignment. Hosts need independent identity-bound input
evidence or must leave binding unverified; no decryption or key access follows.

Local validation passed 164 Python tests, including seventeen real-engine cases
without skips, and the package/static build. The new checks cover immutable
writer/reviewer message rendering, explicit identities and UTF-8 digest,
stale/uncertain state refusal, corrupt objects, mutable context-file replacement
and no writes during preview. This increment was uninstalled and unpublished at
that checkpoint. The checks establish message construction behavior. Native
delivery requires separate evidence.

## Reviewed commit acceptance source increment (13 November 2026)

The low-level CLI adds explicit `task accept-commit` for approved staged work
that has subsequently been committed. It verifies the full frozen index against
the complete current commit tree, including omitted paths, checks tracked
working bytes directly and preserves selected bytes/types/modes. The original
artifact, review identity, history and caps remain intact. It appends a binding;
ordinary strict checks remain unchanged without that explicit operation.

The [CLI operation contract](cli.md#explicit-acceptance-of-a-reviewed-commit)
defines decision declarations, source checks, rejected cases and coordinated-scan
limits. Acceptance permits active/blocked tasks with passing required reviews and
resolved gates; it neither activates nor completes them. Bound lifecycle checks
reject subsequent source drift. New artifacts invalidate the active binding
without removing its history or transferring approval.

First acceptance upgrades SQL and enclosing state transactionally to format 4.
Formats 1–3 remain readable; prior binaries refuse format 4, and subsequent review
amendments or quota handoffs cannot downgrade it. This source increment does not
establish installation, publication, atomic capture or authenticated authority.

## Review coverage, native task identity and final-output contracts (14 November 2026)

Independent review and validation covered the review coverage guard, native
task identity and final-output contracts. The reviewed source was integrated
into the working checkout on 14 November and is included in commit `4d2a1b0`. Installation requires separate owner or user
authorization.

Local implementation validation on 14 November 2026 passed 216 Python tests,
including 27 opt-in real-engine cases, with no skips. Those results precede the
documentation-only status corrections; implementation tests were not rerun for
these wording edits.

The increment integrates reviewed helper and skill text
into the five package files that differed (`SKILL.md`, `scripts/backend.py`,
`references/backend.md`, `references/review-protocol.md`,
`assets/review-packet.md`) while retaining the earlier selector, argument,
storage-preview and native-rendering corrections. The other eight package files
are unchanged. No Rust engine behavior, capture or evidence policy changes.

- **Review coverage guard.** Before any workflow trace, record object or output
  write, review `context` requires every staged, unstaged and untracked
  non-ignored change since HEAD inside the frozen editable scope to be selected.
  Scoped deletions and selected absent, binary, symlinked or non-UTF-8 inputs
  are refused because the readable helper cannot present them. Directory-shaped
  scoped Git entries, such as an untracked nested repository, get an explicit
  pre-write refusal directing the host to another authorized review path;
  they are neither traversed nor skipped. A directory-shaped entry containing a
  scope entry is treated as scoped for that refusal, so an unrelated declaration
  cannot cover it; ordinary ancestor files and prefix-only names keep the normal
  outside-scope rule. A scoped staged gitlink (no trailing slash) keeps the
  ordinary coverage/regular-file refusals. A staged gitlink above a directory
  or absent scope entry instead remains outside scope: it requires a genuinely
  unrelated-work declaration and can then remain an explicit omission while
  selected regular source is frozen and sealed. Synthetic cases with the tested
  engine observe that boundary; omitted nested content is not reviewed, and task
  work must never be declared unrelated. No nested-repository support is added.
  Directory-scoped writer content beneath a gitlink is not enumerated by the
  path guard and can leave its coverage report unchanged. If the writer may
  have written there, the gitlink must not be declared unrelated; another
  authorized review path is needed. An existing exact scoped regular file
  beneath the gitlink still requires selection. A synthetic actual-engine case
  observes that selecting that file with the gitlink declared unrelated passes
  preflight but fails at freeze after a helper trace, with no artifact, packet,
  output or record-revision change. The omitted-content case
  also checks rendered output directly for exclusion of nested-source text.
  Changed paths
  outside scope must be selected or explicitly declared with
  `--unrelated-changes`, recorded per path in frozen omissions; no flag admits a
  scoped omission. After freezing and before sealing, the helper recomputes the
  change set and compares frozen objects with live selected bytes; drift leaves
  the artifact as evidence and seals no packet. Writer context is unchanged.
  Scope at `start` should therefore cover docs and tests the writer may add.
  Follow-up guidance refreshes selection against the current full change set,
  including new docs/tests, and reassesses unrelated-change declarations.
  The guard sees only changes Git reports against the current HEAD: index flags
  or Git-normalized differences can hide tracked changes, and task work already
  committed is not discovered. These limits are documented, not enforced.
- **Nested-repository engine observations.** Two paths pass the helper
  preflight: an outside-scope untracked nested repository declared unrelated,
  and writer context with an untracked nested repository. Synthetic
  actual-engine cases with the tested engine build observe the exact
  trailing-slash name passed as an omission. The helper writes a workflow and
  freeze-operation trace, then the engine rejects the freeze: no artifact,
  packet or output, and the record revision is unchanged. These are bounded
  observations, not nested-repository support; the shared path parser and
  engine are unchanged.
- **Native task identity.** `native-dispatch` returns a deterministic
  `task_name` digest of the exact assignment, packet and artifact identities
  and adds it to the message header; existing header lines are unchanged. Hosts
  pass it exactly. A matching name alone proves no delivery. A host receipt
  joining the exact call with an equal opaque first-turn payload establishes at
  most opaque delivery, narrower than plaintext or full-context attestation.
- **Role-specific final output.** For ordinary `codex-native` assignments the
  constructed message carries a reviewer contract (the complete identity-filled
  review JSON as the terminal final message, superseding conflicting format
  requests) or a writer work-report contract, never reviewer JSON. Other
  transports still need the contract in sealed review instructions; the binary
  never inserts a schema. The initial-cycle example explicitly uses
  `native-dispatch` for ordinary native reviewers and passes its exact message,
  task name and controls to the host; it is written as a transport conditional
  so other transports do not run it as a universal command. A constructed
  message, written file, preview or self-report is not terminal or delivery
  evidence.

Portable regressions use disposable Git fixtures and stub engines for scope
coverage, refusal before writes, freeze drift, nested-repository containment,
staged gitlinks, identity edge cases and contract fields; opt-in real-engine
cases, including the nested-repository observations, need an explicit test
binary. Stub results are
not real-engine evidence. The helper still dispatches and supervises no model,
and implicit activation remains unestablished.

## v0.1.0 release (21 November 2026)

The [first experimental release](https://github.com/jaredchu/agents-collab/releases/tag/v0.1.0)
was built from `2481df2`. The local regression gate passed 48 Rust and 220
Python tests on the released source. An isolated installation completed one
explicit opt-in task with a passing independent review and a verified format 6
record. The release includes the skill ZIP, the macOS arm64 CLI and checksums.

## v0.1.1 release (23 November 2026)

The [release](https://github.com/jaredchu/agents-collab/releases/tag/v0.1.1)
was built from `fb2dfa2`. The candidate passed 48 Rust and 224 Python tests
on macOS arm64, and the two published archives matched their checksums.
The release adds private-storage and saved-output checks and the Claude CLI
review renderer. The [release notes](releases/v0.1.1.md) describe the changes
and the scope of the isolated opt-in verification.
