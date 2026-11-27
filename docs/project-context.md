# Project context

## Purpose

Agents Collab is an experimental skill for configured model collaboration and
independent review. The [public journal](https://agents-collab.com) describes
the design and experiments. [Project history](history.md)

The owner-confirmed product target is dependable implicit activation for
appropriate teamwork. The [public routing gate](../evals/automatic-routing/2026-11-09/report.md)
missed both required collaboration routes on ordinary prompts. Separate
explicit-invocation diagnostics matched all three expected routes. Explicit
invocation remains the supported fallback.

## Boundaries

- The MIT-licensed [skill package](../skills/agents-collab/SKILL.md)
  includes the profile wizard, workflow and optional backend helpers. The
  verified workflow uses a Codex lead, with Claude CLI available as a review
  transport. Other leads and adapters remain unvalidated. [License](../LICENSE) · [Installation](guide.md)
- The optional Rust backend records sealed packets, reviews and task state.
  The host owns dispatch, worker supervision, deadline enforcement and receipt
  reconciliation. Interface-accepted effort does not attest runtime effort,
  and a fresh session does not establish filesystem isolation.
  [Backend scope and limits](cli.md#storage-and-failure-limits)
- Publish sanitized summaries with their provenance and limitations. Keep
  profiles, credentials, raw traces and client details private.
  [Project rules](../AGENTS.md) · [Evidence policy](../CONTRIBUTING.md)
- The project keeps analytics injection disabled on the static public site.
  [Site verification](verification-history.md#analytics-injection-disabled-11-november-2026)

## Current status

### Current overview

Routine work defaults to solo. A compatible backend can explicitly opt a
routine task into independent review. The workflow binds the writer's receipt
and reviewer verdict to the same final artifact. One fresh isolated install
completed this path with a passing independent review and a verified format 6
record. [Explicit opt-in workflow](../skills/agents-collab/references/backend.md#explicit-opt-in-for-routine-tasks)

Unreleased source adds [opt-in automatic reviewer effort](../skills/agents-collab/references/configuration.md#opt-in-automatic-review-effort).
The rule selects Medium for one exact scoped file that matches the sealed
file and High for broader reviews. It works with the optional CLI adapter
and manual workflow. Explicit levels and inherited settings remain available.

### v0.1.1 release

The [v0.1.1 experimental release](https://github.com/jaredchu/agents-collab/releases/tag/v0.1.1)
was published on 23 November 2026. It pairs the skill with an optional macOS
arm64 CLI for local APFS storage. The release adds checks for private record and
host storage, revalidates saved output paths, and prepares Claude CLI review
messages from sealed packets.
The Rust engine and supported record formats are unchanged from v0.1.0.
Published archives matched their checksums. [Release checks](verification-history.md#v011-release-23-november-2026) ·
[Release notes](releases/v0.1.1.md)

## Evidence and limits

- Two early five-task pilots missed their coordination-benefit thresholds.
  [Earlier pilots](experiments.md#earlier-private-pilots)
- The quality pilot's primary results favored review on its frozen cases.
  The sensitivity analysis left too few material drafts for a robust result.
  The CLI usefulness comparison was inconclusive.
  [Quality report](../evals/quality/2026-11-09/report.md) ·
  [CLI comparison](experiments.md#4-same-skill-with-and-without-the-rust-cli)
- A [matched review-effort pilot](experiments.md#5-matched-review-effort-pilot)
  found all three synthetic defects in both arms, with lower total time and
  output tokens for the bounded cases under the rule. Three duplicate finding
  IDs blocked imports. A [ten-case follow-up](experiments.md#6-harder-matched-review-effort-trial)
  found all eleven seeds in both arms, and all twenty original responses
  imported with assignment-prefixed IDs. The trials informed the opt-in rule.
- Routing detection, structural validation and release checks measure
  different outcomes. The completed checks do not establish general
  productivity gains or dependable implicit activation. Raw trial evidence
  is private, which limits independent auditing.
  [Verification history](verification-history.md)

## Progress

- [x] Publish and verify the [experimental skill and optional CLI](releases/v0.1.1.md).
- [x] Run the [initial routing gate](../evals/automatic-routing/2026-11-09/report.md).
  The gate failed, so all 36 planned comparison runs stayed unstarted.
- [ ] Reconcile current source and prior exploratory exposure before freezing and
  preregistering the proposed 18-run implicit-activation study. Earlier method
  review applies to the prior draft. Execution still requires owner approval
  and supervised launches. [Draft study](plans/implicit-activation-study.md)
- [ ] Establish dependable implicit activation before running a new effectiveness
  comparison.

## Documents

| Document | Role |
| --- | --- |
| [README](../README.md) and [guide](guide.md) | Status, installation, profiles and invocation |
| [Research](research.md) and [experiments](experiments.md) | Design evidence, pilot outcomes and limits |
| [History](history.md) and [verification history](verification-history.md) | Project origins and dated implementation evidence |
| [Rust CLI guide](cli.md) and [original prototype plan](plans/rust-cli-prototype.md) | Current backend contract and retained design rationale |
| [Contributing](../CONTRIBUTING.md) | Contribution and evidence rules |
