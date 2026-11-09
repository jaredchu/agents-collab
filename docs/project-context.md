# Project context

## Purpose

Agents Collab is a reusable, experimental agent skill for configured model
collaboration and independent review, together with a public journal at
https://agents-collab.com explaining Jared Chu's research, the earlier per-project
model-collaboration approach, the experiments and why personal workflow settings
were separated from project knowledge.

## Boundaries

- The distributable skill is the curated file list in
  `scripts/build_website.py` (all files in `skills/agents-collab/`): workflow
  files, configuration and optional backend helpers, and `LICENSE`. Users
  install that folder, not this repository. `LICENSE` is byte-identical to the
  root `LICENSE`. Through the 2026-11-08 license and publication preparation the
  eight original workflow files stayed byte-for-byte unchanged from the
  validated source; adding the setup wizard later changed `SKILL.md` and
  `references/configuration.md`, so that byte-identity no longer holds for them.
- The project is licensed under the MIT License, copyright 2026 Jared Chu
  ([LICENSE](../LICENSE)). The license does not change the experimental status
  or evidence limits.
- Personal profiles, credentials, raw traces, private or client project
  information and machine-specific paths stay outside this repository and site.
- The manual workflow uses a structural profile validator and interactive setup
  wizard. The optional adapter uses a separately installed Rust executable for
  snapshots, sealed packets and local structural gates. No helper dispatches or
  supervises models, enforces deadlines or attests truthful model observations.
- The pilot targeted a Codex lead. Other leads and adapters are unvalidated.

## Evidence and limits

- Structural pre-install validation passed privately (52 unit tests; nine plus
  two simulated scenarios). Simulation is not production safety evidence.
- Two five-task pilots, both before installation, missed their
  coordination-benefit thresholds; results are mixed. Details and confounds:
  [experiments](experiments.md).
- Installation later verified fresh-session discovery and profile structure, not
  future automatic routing or runtime effort.
- Interface-accepted effort is not runtime attestation; fresh reviewer context is
  not filesystem isolation.
- Public summaries are sanitized; raw evidence is private and not independently
  auditable.

## Documents

| Document | Role |
| --- | --- |
| [README](../README.md) | Entry point, status and limits |
| [Guide](guide.md) | Installation, profile, invocation |
| [Research](research.md) | Sanitized research notes |
| [Experiments](experiments.md) | Validation and pilot summaries |
| [History](history.md) | How the project emerged |
| [Rust CLI backend](cli.md) | Optional installation, executable commands, storage bounds and checks |
| [Rust CLI prototype plan](plans/rust-cli-prototype.md) | Original acceptance scope, rationale and implementation status |
| [Contributing](../CONTRIBUTING.md) | Contribution and evidence guidelines |
| [License](../LICENSE) | MIT License (identical copy in the skill package) |

## Current status

Pre-release. On 2026-11-08 the owner selected the MIT License and
https://github.com/jaredchu/agents-collab as the public repository
(license URL: https://github.com/jaredchu/agents-collab/blob/main/LICENSE).
On the same date the repository was published publicly and GitHub recognized
its MIT License. https://agents-collab.com serves the public website with an
active custom-domain certificate. No versioned release has been made.

The five website pages carry a quiet creator credit linking Jared Chu to his
canonical CV (2026-11-09). The notebook byline, experimental status, methodological
limits and project source/license links remain the context for the work.

Root and package `LICENSE` files exist, and the website and documentation link
the repository and its license. At publication the download archive held nine
files.

`tests/` holds the portable suite (validator tests ported without the
private-profile test, plus setup-wizard, privacy, license, website and build
checks). On 2026-11-08, before the setup wizard, all 70 tests passed, including
checks against a separate unpublished private-identifier list. At that point the
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
at a prompt left no target file. No real user profile or HOME environment was
changed. These checks establish configuration behavior, not model availability
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
Python 3.9+ for profile setup and validation. Profile setup remains separate; the CLI can replace existing skill files on a repeat run, while
the guarded manual route preserves them. On 2026-11-08 Skills CLI 1.7.6 installed
all nine matching package files in a temporary home-directory API fixture and
preserved a separate existing profile. This test did not change the real HOME
environment or the owner's installed skill/profile. Other leads remain unvalidated.

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
are not fully independently auditable. Global instructions, the owner's profile,
installed skill and the active target checkout were unchanged.

The study-only RPC recorder lives in `evals/`, outside the distributable package.
Activation/discovery remains the concrete unresolved product issue; that
study’s full usefulness comparison remains unperformed. Installation alone still provides
no dependable automatic-routing guarantee.

## Quality pilot: withdrawal and completed recovery (9 November 2026)

The unfinished study was removed from current public files at the owner's
request after a subscription interruption. An access limit did not constitute
completion. After access returned, a reviewed recovery amendment allowed only
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

Live comparisons, dispatch, MCP and a daemon remain unperformed and separately
authorized work. No artificial experiment usage budget is imposed. Profile timing
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
source changes await independent review; no runtime quality or efficiency gain
is claimed.

## Site discovery and Cloudflare hosting (9 November 2026)

Production at https://agents-collab.com now serves the checked static build
directly from Cloudflare Pages. `wrangler.toml` selects `dist/`; there are no
Pages Functions or application server. The custom domain, HTTPS, all nineteen
served files and downloads, a genuine 404 response, cache headers and preservation
of the three other DNS records were verified. The owner retained deletion of
the former ChatGPT-hosted Site; no deletion by the agent is claimed.

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
commits and Wrangler are pinned; GitHub token permission is read-only. The
Cloudflare account ID and account-scoped Pages Write token are repository secrets
supplied only to the guarded deploy step. CI has no DNS credential. The five
macOS/APFS runtime tests require their explicit binary and do not run on Linux.
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

## Progress

- [x] Preserve the eight-file validated package as the initial source.
- [x] Draft reusable documentation, portable tests and sanitized experiment summaries.
- [x] Draft the static website and build script.
- [x] Run local tests, website build, bounded browser and privacy checks.
- [x] Complete independent source review of the private prototype.
- [x] Owner selects repository owner and license (MIT; jaredchu/agents-collab).
- [x] Add root and package LICENSE, nine-file download and repository/license links.
- [x] Rerun tests, build, installation and browser checks after the license additions.
- [x] Resolve the Markdown ZIP profile-setup finding and complete focused source review.
- [x] Publish the MIT repository and deploy agents-collab.com; verify public access and downloads.
- [x] Draft the interactive profile setup wizard, its tests, package and documentation updates.
- [x] Run the suite, build, metadata, installation and interactive checks for the setup wizard.
- [x] Check browser layout, copy buttons and content without JavaScript.
- [x] Complete independent review and the focused cleanup-error correction.
- [x] Publish and verify the updated package and setup instructions.

- [x] Publish a reviewed protocol before public routing measurements.
- [x] Execute the routing gate and separately labelled explicit diagnostics.
- [x] Record the failed gate and all 36 comparison runs as not started.
- [ ] Establish reliable implicit activation before attempting the cancelled usefulness comparison.

- [x] Complete recovered quality grading and evidence reconciliation without participant rerolls.
- [x] Publish primary criteria, sensitivity, corrected dispositions and interruption limits.

- [x] Implement the source-only Rust local record-and-packet core.
- [x] Exercise synthetic workflow, source identity, fault and concurrency cases.
- [x] Complete independent implementation review and required focused corrections.
- [x] Complete and report the three-case manual-versus-CLI comparison, retaining qualifications.
- [x] Package the CLI and integrate an optional backend without changing the profile contract.
- [x] Review, install and verify the adapter on an ordinary documentation task.
- [x] Add checked SEO/AI-search discovery resources and direct Cloudflare Pages hosting.
- [x] Implement owner-approved skill clarity and helper observation fixes.
- [ ] Complete independent review of those fixes, then publish and update the installed skill.
