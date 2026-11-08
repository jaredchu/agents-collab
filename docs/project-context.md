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
  files, the profile validator and setup wizard scripts, and `LICENSE`. Users
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
- The package is a prompt-led workflow with two configuration helpers: a
  structural profile validator and an interactive setup wizard that writes a
  profile only after confirmation. Neither calls a model. It has no dispatcher,
  snapshot freezing, deadline implementation or enforcement.
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
| [Contributing](../CONTRIBUTING.md) | Contribution and evidence guidelines |
| [License](../LICENSE) | MIT License (identical copy in the skill package) |

## Current status

Pre-release. On 2026-11-08 the owner selected the MIT License and
https://github.com/jaredchu/agents-collab as the public repository
(license URL: https://github.com/jaredchu/agents-collab/blob/main/LICENSE).
On the same date the repository was published publicly and GitHub recognized
its MIT License. https://agents-collab.com serves the public website with an
active custom-domain certificate. No versioned release has been made.

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
supported effort, access or records-path isolation. The download archive now
holds ten files. On 2026-11-08 all 90 tests passed after the addition and cleanup-error correction, with
profile writes tested only at temporary output paths. Skill metadata validation,
the website build, both manual install paths and installation of all ten files
through Skills CLI 1.7.6 passed. The installed wizard produced a valid profile
with mode 0600; a terminal run exercised a writer and two reviewers, and Ctrl-C
at a prompt left no target file. No real user profile or HOME environment was
changed. These checks establish configuration behavior, not model availability
or runtime reasoning support. Local browser checks at 1440px and 390px passed, including the wizard command
copy buttons and content without JavaScript. Independent review found and resolved one staging-cleanup reporting issue;
the focused follow-up independently passed all 19 wizard tests. The live
package matches the checked ten-file build; its downloaded wizard created a
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
