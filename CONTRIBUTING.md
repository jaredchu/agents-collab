# Contributing

Thanks for your interest. The project is pre-release and licensed under the
[MIT License](LICENSE). Source repository: https://github.com/jaredchu/agents-collab.
Any contribution you submit is offered under the same MIT License. These
guidelines describe how changes and evidence are handled.

## Ground rules

- **Keep the skill generic.** `skills/agents-collab/` must contain no personal
  model choices, reasoning defaults, storage conventions, account details or
  machine paths. Examples use placeholders or synthetic identifiers.
- **No private material.** Never commit profiles, credentials, `.env` files, raw
  logs or transcripts, or details of private or client projects.
- **One writer per change.** Review findings go to the author; reviewers do not
  silently rewrite the change.
- **Keep the skill helpers dependency-free.** The validator, setup wizard, Python
  tests and website build script use the Python 3.9+ standard library only. The
  separate `cli/` Rust crate has its own locked dependencies, including bundled
  SQLite, and is not distributed with the skill.

## Checks before proposing a change

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_website.py
```

For Rust changes, also run the [CLI build and checks](docs/cli.md#build-and-checks)
with external build/temporary directories. No provider, account or live model
is needed for its offline suite.

The repository tests include privacy guards for absolute home paths, e-mail
addresses and credential-shaped strings. Maintainers can add private terms
without committing them: set `AGENTS_COLLAB_PRIVATE_TERMS_FILE` to a file outside
the repository with one literal term per line. Failures report file and line,
never the term.

Tests write temporary files only to the system temporary area.

Package changes also need the [configuration contract](skills/agents-collab/references/configuration.md),
validator, setup wizard, examples and guide to stay consistent, and `skills/agents-collab/LICENSE`
must stay byte-identical to the root `LICENSE`. Website changes need a check
without JavaScript, at narrow and wide widths, and with keyboard navigation.

## Evidence guidelines

Claims about behavior need evidence matched to the claim.

| Claim | Minimum evidence | Not sufficient |
| --- | --- | --- |
| Profile structure is valid | Validator exit 0 | — |
| A model or effort was used | Runtime evidence from the interface | Validator pass; the model saying so; interface accepting a request |
| A reviewer was independent | Fresh session, neutral packet, recorded before dispositions | Same session; shared transcript |
| A reviewer was isolated | Technical filesystem or permission isolation | Fresh session or a worktree alone |
| A deadline was enforced | A supervisor that can stop the process | A prompt or a periodic check |
| An adapter or lead is supported | End-to-end runs on that host | Loading the Markdown there |
| Productivity or quality improved | Repeated, controlled comparisons with stated limits | One small pilot |

When reporting an experiment:

- state task count, executions per arm, what was matched and what was not;
- say what durations measure (for example, summed model-call time) and what they
  exclude;
- keep unknown values unknown, not zero;
- report thresholds that were missed and negative results as prominently as
  positive ones;
- publish only sanitized summaries; say plainly that raw evidence is private if
  it is.

## Interrupted experiments

A subscription, rate or temporary access limit is an infrastructure blocker,
not an experimental result or completion condition. Leave required work pending
and wait for the existing authorized access path. Do not silently substitute
models, spend on another path, or publish final conclusions to close the task.

Preserve frozen tasks, rubric, outputs and failed-attempt receipts. On recovery,
resume only unfinished work and disclose the interruption; do not reroll completed
outputs or change success criteria. Reconcile any running invocation before retry.
If interruption requires a protocol amendment, disclose it before resumption.
Check that anonymous grading remains valid, especially if mappings or findings
were already revealed publicly.

Keep final results unpublished until all required stages are complete. If partial
results have already been shared, mark them clearly as interim/on hold and leave
the experiment unfinished. Withdrawing a results page must not silently erase
preregistration, failed attempts or prior public claims from the research record.

## Documentation

`docs/project-context.md` is the current project context. Update it when project
facts, decisions, limits or next actions change, and keep its progress list
current. Do not add a second tracker.
