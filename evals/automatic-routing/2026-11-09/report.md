# Public automatic-routing gate — 9 November 2026

**Ordinary prompts did not trigger the required collaboration. Explicit skill
invocation matched the three expected routes in this sample.** The planned
36-run comparison was stopped under the published gate rule. This study does
not establish a quality, productivity or cost benefit.

## What was frozen and executed

The [protocol](protocol.md), [six authored tickets](tasks.json),
[benchmark profile](profile.example.json), seeds, schedule and measurement
harness were published in
[commit e0cbaa3](https://github.com/jaredchu/agents-collab/commit/e0cbaa38adf8a7b582312c148869510ab3af006d)
before any gate outcome. The [frozen manifest](frozen.json) identifies their
bytes. Those inputs and the installed skill were unchanged during execution.

The target was the public [ProcLease source at 37975b5](https://github.com/jaredchu/proclease/tree/37975b5245fcb5cac7b16fac74efd01269dff5d8).
Its project instructions contain no model-collaboration policy. Each run used a
fresh disposable source snapshot and session. Configuration stayed outside the
project. The owner's global instructions, private profile, installed skill and
active ProcLease checkout were unchanged.

These are authored evaluation tickets, not existing issues or pull requests.
C1 deliberately introduces a defect through a published seed patch: the public
ProcLease base already refuses symlinked logs. None of the trial changes was
applied or published to ProcLease.

Only R1, S1 and C1 were executed, once with ordinary prompts and once as a
separate explicit-skill diagnostic. R2, S2 and C2 were prepared but not run.
There are three task units and six executions, not six independent tasks.

## Ordinary-prompt gate

No task prompt named a skill, model, writer, reviewer or collaboration route.
The skill was enabled in the per-invocation catalog. Routine solo work did not
require a skill load; the other cases required both a load receipt and the
configured dispatches.

| Case | Expected route | Observed route | Skill-read receipt | Route result |
| --- | --- | --- | --- | --- |
| R1: lease-extension tests | Solo | Solo | None observed | Pass |
| S1: list/watch filters | Opus writer, then Astra review | Solo | None observed | Fail |
| C1: seeded symlink fix | Independent Astra review | Solo | None observed | Fail |

**Gate: 1/3 expected routes.** No configured collaborator was dispatched in any
ordinary run. The stop rule was applied before starting the comparison.
All 36 scheduled comparison rows remain in [runs.jsonl](runs.jsonl) as
`not_started_gate_stop`, with unmeasured values left null.

## Separate explicit-skill diagnostic

Each fresh session received the same ticket plus one sentence:

> Use $agents-collab for this task.

No model names or role assignments were added. All three sessions produced a
successful skill-read receipt and matched their expected route:

| Case | Observed route | Selection evidence |
| --- | --- | --- |
| R1 | Solo | No collaborator dispatch; routine classification |
| S1 | Opus writer, then Astra review | Claude provider receipt identifies `claude-opus-5-5`; executed CLI requests High; native reviewer metadata reports `gpt-6-astra` / High |
| C1 | Astra review | Native dispatch and reviewer metadata report `gpt-6-astra` / High |

Both native reviewers had distinct ephemeral child sessions with
`forkedFromId: null`, plus separate frozen review artifacts and recorded
review results. The CLI writer used a fresh process without session persistence.
These are exposed interface and artifact observations, not filesystem isolation
or independent attestation of provider internals. Requested/accepted High effort
is not proof of the internal reasoning level applied.

Both reviews returned no material findings. They are participant reviews, not
independent proof that either implementation is defect-free.

## Recorded task measurements

Wall time is measured by the recorder, including cleanup. Commands include
observed lead and native-child command events. These are descriptive gate and
diagnostic measurements, not the cancelled A/B comparison.

| Case | Mode | Wall time | Commands observed | Full suite passed |
| --- | --- | ---: | ---: | ---: |
| R1 | Ordinary | 87.870 s | 7 | 67 tests |
| S1 | Ordinary | 317.827 s | 19 | 66 tests |
| C1 | Ordinary | 97.517 s | 14 | 63 tests |
| R1 | Explicit diagnostic | 98.483 s | 12 | 68 tests |
| S1 | Explicit diagnostic | 782.153 s | 50 | 64 tests |
| C1 | Explicit diagnostic | 198.578 s | 30 | 63 tests |

External checks of each final output passed formatting, Clippy with warnings
denied and the full suite. Both R1 outputs killed all three specified mutants
and left production code unchanged. Both S1 outputs passed the process-free
filter fixtures, record-preservation checks and six unfiltered JSON comparisons
against the base binary. Both C1 outputs passed symlink-refusal and ordinary-log
fixtures; each new regression failed when its production fix was reverted.
Observed changed paths stayed within each ticket's allowlist; HEAD did not
change. No operator intervention was needed in the six runs.

These auxiliary checks are not a blinded full correctness score. Manual criteria
were not comprehensively scored, ignored files and external filesystem writes
were not fully audited, and no condition-A output exists. Test counts alone do
not measure quality. Native provider token totals and available Claude writer
usage are included in the ledger; **billed cost is unknown**. Provider time is
not equated with user time or summed into wall time.

## Reproduce and inspect

- [Protocol and run command](protocol.md#execution-and-receipts)
- [Frozen task definitions and objective checks](tasks.json)
- [Seed identities](seeds/manifest.json) and [preflight calibration](preflight.json)
- [Study-only RPC recorder](run.py), [offline checks](check_materials.py),
  [CLI fixtures](fixtures.py)
- [All 42 run records](runs.jsonl): three gates, three diagnostics, 36 not started
- [Selected sanitized receipts](evidence.json)
- Final working-tree patches: [ordinary R1](patches/gate-R1-B.patch),
  [ordinary S1](patches/gate-S1-B.patch), [ordinary C1](patches/gate-C1-B.patch),
  [diagnostic R1](patches/diag-R1-B.patch), [diagnostic S1](patches/diag-S1-B.patch),
  [diagnostic C1](patches/diag-C1-B.patch)

Apply a patch to the corresponding task snapshot, including C1's seed, not to an
active checkout. Use the stated case environment and the objective checks in
`tasks.json`. For example, `fixtures.py --binary <built-binary> --root
<new-short-private-fixture-root> --task S1` prints the filter-check results.
No provider credentials are included. Re-running participant tasks requires the
specified authenticated CLIs and models; model output is not deterministic.

The receipts are selected and sanitized by the operator. Full raw conversations,
account metadata and personal paths are not published, so the original execution
is not independently auditable end to end. Public inputs and code support
rerunning the method, not replaying identical model outputs.

## Limits and conclusion

One host, one public Rust project, three authored tasks, one execution per mode.
The external profile path was supplied through identical developer metadata,
which could cue collaboration; this does not test untouched default-profile
discovery. Temporary-artifact instructions also took precedence over the
profile's records directory, while keeping records outside the project.

Some login-shell invocations dropped supplied test environment variables; the
explicit routine session detected that and used a non-login shell. This is an
additional environment-control limitation for future comparisons. Before the
freeze, the first baseline test attempt also hit macOS's Unix-socket path limit;
the shortened fixture root passed all 62 baseline tests. Calibration failures
and corrections are distinct from participant outcomes.

The gate and diagnostic sessions ran concurrently within each phase and may
have shared machine/cache contention. No timing difference is attributed to the
skill. A comparison against the disabled skill was never executed. Cleanup
reported each owned process group absent; external provider-worker cleanup
remained unverified.

The supported use in this sample is **explicitly invoking the skill while
letting the profile choose the models**. Reliable activation from ordinary
prompts remains unestablished and missed both required collaboration routes
here. The next product issue is activation/discovery; the 36-run usefulness
comparison remains unperformed. No installed skill, profile or global
instruction was changed to make these results pass.
