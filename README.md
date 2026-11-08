# Agents Collab

An experimental skill for configured model collaboration and independent review,
plus the lab notebook of how it came about.

> **Status: experimental, pre-release.** The skill comes from a Codex-led pilot.
> Licensed under the [MIT License](LICENSE).
> [Source](https://github.com/jaredchu/agents-collab) ·
> [Website and experiment journal](https://agents-collab.com).
> No versioned release has been made.

## What it is

`skills/agents-collab/` is an agent skill: Markdown instructions, a reference
contract, inert templates, one dependency-free validator script and a copy of
the MIT `LICENSE`. It helps a
lead assistant session:

- choose a writer and independent reviewers from a **personal profile** kept
  outside every project (`~/.config/agents-collab/profile.json`);
- send reviewers a neutral packet and the same frozen artifact, not the writer's
  conversation or each other's first findings;
- cap review rounds, record dispositions, and keep execution records in a
  **private records directory** rather than in project documentation;
- hand only durable outcomes (decisions, verified behavior, risks, remaining
  work) back to the project.

## What it is not

Read these before relying on it:

- **Prompt-led, not a runtime.** The lead follows written instructions. The only
  code is a structural profile validator. There is no automatic dispatcher, no
  snapshot freezing, no hard-deadline implementation and no enforcement layer.
- **Codex-led pilot only.** The design targets a Codex lead with native subagents
  and optional Claude CLI dispatch. Other lead assistants and adapters are not
  validated; loading the Markdown elsewhere does not establish support.
- **Accepted effort is not attested effort.** An interface accepting a requested
  model or reasoning level differs from runtime attestation. A model's claim
  about itself is not evidence.
- **Fresh context is not isolation.** A fresh reviewer session with a controlled
  packet is not filesystem isolation.
- **The validator checks structure only.** It does not check that a model exists,
  that you can access it, that a reasoning level is supported, permissions, or
  where records actually resolve.
- **Small evidence.** Two five-task pilots by one owner gave mixed results and did
  not meet their coordination-benefit thresholds. See
  [experiments](docs/experiments.md). No general productivity, quality or cost
  claim follows.

## Quick start

1. Install only the package folder `skills/agents-collab/` into your host's user
   skills location, not this whole repository.
2. Keep any existing profile. If none exists, copy an example to
   `~/.config/agents-collab/profile.json` and replace every placeholder model.
3. Validate the structure:
   `python3 ~/.agents/skills/agents-collab/scripts/validate_profile.py ~/.config/agents-collab/profile.json`
4. Ask for it explicitly: `Use $agents-collab to implement this change with independent review.`

The full procedure, with guarded copy commands and examples, is in the
[installation and usage guide](docs/guide.md).

## Repository map

| Path | Purpose |
| --- | --- |
| [`skills/agents-collab/`](skills/agents-collab/SKILL.md) | The distributable skill package (nine files: eight workflow files plus `LICENSE`) |
| [`LICENSE`](LICENSE) | MIT License for the repository |
| [`docs/guide.md`](docs/guide.md) | Installation, profile setup, invocation and limits |
| [`docs/examples/`](docs/examples/writer-review.profile.example.json) | Illustrative profile with deliberate placeholders |
| [`docs/research.md`](docs/research.md) | Sanitized research notes |
| [`docs/experiments.md`](docs/experiments.md) | Summaries of the validation and two pilots |
| [`docs/history.md`](docs/history.md) | How the project emerged |
| [`docs/project-context.md`](docs/project-context.md) | Current facts, limits and progress |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contribution and evidence guidelines |
| `tests/` | Dependency-free unit and repository checks |
| `website/`, `scripts/build_website.py` | Static website sources and build |

## Checks

Python 3.9+ with the standard library only; no network, credentials or model calls.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_website.py   # writes dist/ only
```

Tests create temporary files in the system temporary area. Results are reported
by whoever runs them; this README does not pre-claim a pass count.

## Website

`website/` is buildless HTML, CSS and a small optional script. Pages are readable
without JavaScript. The build copies it to `dist/`, adds a reproducible zip of the
nine package files (including `LICENSE`) with SHA-256 sums, and checks internal
links.

## License

Agents Collab is licensed under the [MIT License](LICENSE), copyright 2026
Jared Chu. The skill package carries an identical copy,
[`skills/agents-collab/LICENSE`](skills/agents-collab/LICENSE), so the notice
travels with every installation and with the website download. That copy is the
only package addition; the eight workflow files are unchanged. The license
covers the code and text; it does not change the experimental status or the
evidence limits above. The license is also available at
https://github.com/jaredchu/agents-collab/blob/main/LICENSE.
