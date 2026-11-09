# Quality-first three-way pilot — 9 November 2026

**Result: incomplete/inconclusive for A–B, A–C and B–C.** All six initial
drafts and 18 finishing runs completed and were preserved. Deterministic checks
and targeted reproductions are available. The required blind grader hit its
subscription limit; none of its six calls returned an assessment. No registered
quality advantage, equivalence, speed or cost result is established.

There are useful concrete observations: both independent-review paths fixed a
script-invocation regression missed by self-check. Manual review also fixed a
protected-history deletion that the skill path left present. Those findings
support the usefulness of these particular reviews, not a completed comparison
or a skill-specific quality advantage.

## What was frozen

The [protocol](protocol.md), [six authored tickets](tasks.json),
[rubric and success criteria](rubric.json), [counterbalanced schedule](schedule.json),
[benchmark profile](profile.example.json), recorder, grading harness and hidden
checker commitment were [published before any participant draft](https://github.com/jaredchu/agents-collab/commit/b5d53f0).
The [six actual initial drafts](initial-drafts/manifest.json) were then
[published before any finishing branch](https://github.com/jaredchu/agents-collab/commit/a4cc020).
The committed input hashes remain unchanged. No draft was selected, rerolled or
replaced on the basis of hidden results, and no bug was inserted into it.

The source was public [ProcLease commit 37975b5](https://github.com/jaredchu/proclease/tree/37975b5245fcb5cac7b16fac74efd01269dff5d8),
in disposable snapshots. These are authored evaluation tickets, not existing
ProcLease issues or submitted product changes. Its active checkout was unchanged.
This explicitly invoked study is separate from the earlier
[failed automatic-routing gate](../../automatic-routing/2026-11-09/report.md);
the cancelled 36-run study remains cancelled.

## Matched draft, three finishing paths

One genuine Opus draft per task was frozen once. Each task's A, B and C started
from the identical commit and source tree. All used a Sol 6.1 lead, High effort
requests, the same source permissions and a 40-minute branch ceiling.

| Path | Finishing procedure |
| --- | --- |
| A | Fresh same-model Opus 5.5 self-check and one repair pass |
| B | One fresh Astra independent review, then Opus repair if justified |
| C | Explicit `$agents-collab`; profile selects the same Astra and Opus roles |

The initial writer and revision writer were `claude-opus-5-5`; the independent
reviewer was `gpt-6-astra`; the lead was `gpt-6.1-sol`. The required blind grader
was `claude-fable-5-1`. Every role requested High. Native/CLI interface receipts
and provider model IDs establish interface observations, not independent runtime
effort attestation. Existing subscription access was used, with no API or paid
fallback. Fresh context does not establish filesystem isolation. A used a fresh
same-model session, rather than preserving the initial author's conversation.

All six C leads read the skill and dispatched the configured independent
reviewer. The lead and reviewer were read-only with respect to source; assigned
Opus calls owned source repair. B/C could leave a draft unchanged after a clean
review. Four B/C branches needed source repairs; C-Q6 also used a separate fresh
writer call for a precise formatting correction within its original repair
assignment/deadline. This extra call is disclosed rather than collapsed into one.

## Completion and blind-grading failure

| Stage | Planned | Recorded outcome |
| --- | ---: | --- |
| Initial drafts | 6 | 6 completed, frozen once |
| Finishing runs | 18 | 18 completed, no ceiling hits |
| Distinct source artifacts | — | 12; identical trees share one deterministic grade |
| Anonymous Fable assessments | 6 | 6 provider failures, 0 completed assessments |
| Maintainability grades | 24 states | Unknown for every state |

The first three anonymous calls have partial provider usage; all returned the
five-hour subscription-limit error. The next three also failed with that error
and empty usage objects; their usage is **unknown**, not zero. See
[all blind call outcomes](blind-assessments.json) and the
[anonymous packets](blind-packets/). No replacement model, reset, replay or new
grading attempt was used. The operator's later corroboration is non-blind and
cannot replace the missing registered stage.

## Deterministic checks, including failures

Every artifact compiled and passed formatting and Clippy. Across the 24 state
labels, full `cargo test` passed in 21 and failed in 3. There were two actual
failed test executions: Q4-I/A shared the same tree and grade; Q6-A was separate.
Both failed the existing `slow_partial_control_request_cannot_starve_expiry`
test with `ConnectionRefused` after its 700 ms lease expired before command
startup. The test is unchanged from the public base. Concurrent grading and
host load are a plausible confound; these failures are retained as major common
acceptance observations under the rubric, without attributing them to edits or
calling them proven source-induced regressions. No passing rerun replaces them.

The frozen hidden checker produced 292 state-level outcomes: 290 pass, 2 fail,
0 not-run. Both failures were the same defective oracle in Q4-B/C. After the
prespecified exclusion below, **288 valid hidden outcomes pass**, across all
states. Passing these checks did not catch the independently reproduced script
or quarantine cases. Every distinct grade, original failure and common-check
log is in [the grading index](grading-index.json) and [grading/](grading/).

### Post-freeze oracle defect

`q4.deferred.report` expects a protected explicit-keep dry run to list ordinary
history candidates, even though a real call against that same protected state
removes none. This contradicts ticket Q4 criterion 4's exact preview/removal
equivalence. The original draft and A follow the oracle and pass; B/C honor the
written criterion and fail it.

Under the frozen post-freeze rule, this entire check is **invalid for every Q4
state in the primary analysis**. Original outputs and committed checker bytes
are preserved. No silent correction was made. The separate
[post-freeze corroboration script](posthoc-probes.py) and
[all nine probe outcomes](supplementary-probes.json) exercise the disputed
preview and review allegations on all distinct Q4/Q6 trees plus the pinned
base. They are additional, non-blind evidence, not replacement frozen scores.

## Confirmed observations and remaining defects

This table covers corroborated material cases, not complete task scores.
`I` means initial draft; “present” means the exact reproduction fails the ticket.
Unknown defects and maintainability remain unknown because blind grading failed.

| Task / defect | I | A | B | C |
| --- | --- | --- | --- | --- |
| Q4: protected preview disagrees with actual removal — major | Present | Present | Corrected | Corrected |
| Q4: quarantine history deleted during retention protection — blocker | Present | Present | Corrected | Present |
| Q6: no-option shebang script invocation name changes — major | Present | Present | Corrected | Corrected |

Q4's quarantine behavior also exists at the pinned public base; it is not an
introduced regression. It violates the new ticket's explicit “nothing deleted”
requirement. A private reserved quarantine directory was deleted in I, A and C
while `deferred=true`; B preserved it. The probe touched only owned fixtures.

For Q6, an executable `./probe` script prints its `$0`. The pinned base, B and C
print `./probe`; I and A print the absolute execution filename. Unconditionally
rewriting the command path caused this unchanged-behavior regression; setting
`arg0` did not preserve the interpreter-visible script name. Both independent
reviews found it without running a reproduction, and their writers fixed it.
The operator later reproduced the exact claim across all four distinct trees
and the base. Self-check changed documentation/tests and retained the runtime bug.

Other corroborated minor observations: C fixed a guardian-safeguard fixture
that was already rejected by its keeper predicate, so the guardian check was
not independently exercised. A qualified an unconditional README inheritance
claim for `--cwd`; B/C retain that wording. These are a test weakness and a
documentation issue, respectively, not further runtime failures.

Q1 (state filter), Q3 (sort) and Q5 (summary) have identical I/A/B/C source
identities. Q2-A improved fixture seeding; no initial log-window runtime defect
was demonstrated. Its allegation that the ticket bans a short template process
is unsupported by the wording; hypothetical slow-host failure remains
unconfirmed. Model findings were not automatically counted as bugs.

[Defect records and partial observations](defects.json) preserve criterion,
scenario, evidence, corrections and persistence for all 24 states. Registered
complete scores and maintainability are null. No causal merge or judge score
was invented to fill the missing assessments.

## Finding reconciliation

| Path | Corroborated findings | Material corrections | Other findings |
| --- | ---: | ---: | --- |
| A | 1 minor documentation issue | 0 | Unconfirmed timing concerns; fixture, formatting and boundary-test suggestions |
| B | 3 material issues | 3 | No further reported defects |
| C | 2 material issues and 1 minor test weakness | 2 | Quarantine defect remained unreported/unfixed |

The [complete reconciliation](finding-reconciliation.json) distinguishes
true positives, unconfirmed claims and scope suggestions, with dispositions.
There are no claimed false positives from unrelated passing checks. Blind-grader
unique catches are unknown. “No findings” in a review is not proof of correctness.

## Success criteria and conclusion

The frozen rule required at least two task wins, more wins than losses, a
validated major/blocker correction still present in the comparator, no new
blocker, no increased summed majors and complete grading of every compared
state. Fewer than two initially material drafts would have been insufficient.
The corroborated material cases occur in two initial drafts, but the required
blind-grading completion condition was not met.

| Registered comparison | Result |
| --- | --- |
| B versus A: independent review versus self-check | Incomplete/inconclusive |
| C versus A: skill-coordinated review versus self-check | Incomplete/inconclusive |
| C versus B: skill-specific effect | Incomplete/inconclusive |

No win/loss total is presented as a registered result. The observations show
useful independent catches in this sample and one safety issue missed by the
skill path. They do not establish that Agents Collab improves quality beyond
manual coordination with the same models, or that either process is generally
better. The skill successfully coordinated explicit invocation here; reliable
implicit activation remains unestablished.

## Secondary measurements and execution limits

| Path | Sum of six branch wall times | Median branch | Range |
| --- | ---: | ---: | ---: |
| A | 1,807.253 s | 313.189 s | 235.129–332.650 s |
| B | 1,411.214 s | 181.132 s | 146.469–369.003 s |
| C | 1,872.081 s | 241.032 s | 167.101–540.261 s |

Branches overlapped, so sums are not elapsed study time or human time. Initial
drafting, harness preparation and grading are separate. Available lead/native
thread tokens and CLI provider usage are in [selected receipts](selected-receipts.json);
coverage is partial and provider populations differ. No combined billed cost is
known, and list-price estimates are not treated as subscription spending.

Matched requested permissions produced different actual CLI outcomes. Q1-A's
report/helper and Q4-A's report writes were denied; coordinators retained writer
output and ran authorized verification without source repair. Q3-A stopped
before its proposed paragraph-spacing change because report writing was denied;
the unchanged draft was retained. Some `git -C` forms were denied while plain
read-only Git worked. No bypass or substitute writer was used. This operational
confound limits attribution even apart from missing blind grading.

There were no root-operator interventions in participant runs. Coordinator
handling of denied report/check steps is recorded separately, not hidden behind
that counter. Source/history audit found no out-of-scope changes or actor commits.
Owned check groups were absent and known fixture jobs were cleaned. Deleted
metadata/external provider workers prevent a universal process-absence guarantee.
Owner profile/global instructions and installed package hashes were unchanged.

Six authored tasks, one Rust project, one macOS host, no repetitions, shared
machine/cache contention and non-blind operator corroboration limit inference.
Participant reads are not fully observable in CLI final receipts; contamination
cannot be ruled out universally. No reference implementation calibrated positive
checks before freeze, which allowed the Q4 oracle defect to survive preflight.

## Inspect and reproduce

- [Commitments](frozen.json), [protocol preflight](preflight.json), [all state records](state-ledger.json), [scope audit](scope-audit.json)
- [Frozen initial drafts](initial-drafts/manifest.json), [all 24 artifact patches/manifests](artifacts/)
- [Original deterministic grades/logs](grading/), [opaque identity aliases](grading-index.json)
- [Revealed exact hidden checker](revealed-grader.py), [revealed precommitted mapping](revealed-mapping.json)
- [Blind assessment failures](blind-assessments.json), [anonymous packets](blind-packets/)
- [Corroboration script](posthoc-probes.py), [outcomes](supplementary-probes.json), [defects](defects.json), [finding dispositions](finding-reconciliation.json), [analysis](analysis.json)

To reconstruct a state, export the pinned base, apply its
`artifacts/<state>/complete.patch`, restore any recorded untracked files and
verify `final-files.json` including executable modes and symlinks. The offline
[grade.py](grade.py) does this with `--artifact`, `--source` (a checkout containing
the pinned base), `--grader revealed-grader.py`, `--toolchain`, a credential-free
`--cache`, a new short `--fixture-root`, `--python` (3.12+) and
`--cleanup-binary` (trusted pinned-base build), plus `--output` and `--task`.
Use disposable directories, not the active project registry. Re-running model
calls needs the specified existing authenticated CLIs; it cannot reproduce
identical nondeterministic outputs.

For the additional probes, supply `posthoc-probes.py --binaries <map.json>
--fixture-root <new-short-owned-root> --cleanup-binary <trusted-base-binary>
--output <results.json>`, with a map of task to artifact ID to built executable
path. `base` is optional. Original probes used all distinct Q4/Q6 artifacts plus
base. No participant outputs were edited after freezing.

Published receipts are selected and sanitized; raw conversations, account
metadata and private paths remain private. The public artifacts allow source
reconstruction and deterministic rechecking, not independent end-to-end audit
of the original provider execution. The supplementary findings are openly
operator-reviewed; they are not passed off as blinded judgments.
