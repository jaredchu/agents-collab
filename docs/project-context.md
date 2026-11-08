# Project context

## Purpose

Agents Collab is a reusable, experimental agent skill for configured model
collaboration and independent review, together with a public journal (planned
for agents-collab.com) explaining Jared Chu's research, the earlier per-project
model-collaboration approach, the experiments and why personal workflow settings
were separated from project knowledge.

## Boundaries

- The distributable skill is the eight files in `skills/agents-collab/`. Users
  install that folder, not this repository. In this release preparation those
  files stay byte-for-byte unchanged from the validated source.
- Personal profiles, credentials, raw traces, private or client project
  information and machine-specific paths stay outside this repository and site.
- The package is a prompt-led workflow with a structural profile validator. It
  has no dispatcher, snapshot freezing, deadline implementation or enforcement.
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

## Current status

Pre-release. Public repository owner and license are pending the owner's
decision; no license file exists and no public repository, release, domain
ownership or custom-domain deployment has been verified. `tests/` holds the portable suite
(validator tests ported without the private-profile test, plus privacy, website
and build checks). Local validation on 2026-11-08 passed all 65 tests, including
private-identifier checks using a separate, unpublished terms list. The eight
distributable package hashes match the validated source.
`scripts/build_website.py` builds `website/` into `dist/`, the static directory
the hosting configuration declares; its internal-link and reproducible-download
checks pass. Local Chrome checks covered all five routes at 1440px and 390px,
page overflow, code-copy success and denial, keyboard skip/navigation, and content
with JavaScript disabled. These are bounded browser checks, not a complete
accessibility audit. Private evidence and diagnostics remain outside this project.

## Progress

- [x] Preserve the eight-file validated package as the initial source.
- [x] Draft reusable documentation, portable tests and sanitized experiment summaries.
- [x] Draft the static website and build script.
- [x] Run local tests, website build, bounded browser and privacy checks.
- [x] Complete independent source review of the private prototype; public release choices remain pending.
- [ ] Owner selects repository owner and license; then add LICENSE and repository links.
