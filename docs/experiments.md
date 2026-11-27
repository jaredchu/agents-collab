# Experiments

The public [automatic-routing gate and explicit-skill diagnostic](../evals/automatic-routing/2026-11-09/report.md)
ran on 9 November 2026. The ordinary gate matched 1/3 expected routes; all
three explicit diagnostics matched their routes. The 36-run comparison stopped
under its published rule. Inputs, selected receipts, patches and every planned
run status are public; raw executions are not fully independently auditable.
No quality, speed or cost benefit was established.

## Completed quality-first pilot (9 November 2026)

The [six-task three-way pilot](../evals/quality/2026-11-09/report.md) now has all
required anonymous assessments. A quota interruption left it unfinished; the
interim presentation was withdrawn, then grading resumed on the same frozen
outputs after a reviewed recovery amendment. No participant work was repeated.
Original failed attempts, old observations and new grading remain visible.

A was fresh same-model self-check, B manual independent review, and C explicit
Agents Collab with matched models. Both review paths corrected a reproduced
script-invocation regression missed by A. C also improved one guardian fixture
that B retained. Two separate weak Q4 tests count minor under the frozen rubric.
Conflicting Q4 runtime requirements remain unconfirmed; earlier operator-only
certainty about a quarantine safety defect is explicitly superseded.

Primary wins/losses/ties are B/A 2/0/4, C/A 2/0/4, C/B 1/0/5. The first two meet
the frozen observed-acceptance rule; C/B does not establish a skill-specific
advantage. Excluding untargeted failures of an existing test in a disclosed
sensitivity retains two review-versus-A wins, but leaves only one initially
material draft, below the frozen floor. The formal primary advantage is therefore
not robust to those test outcomes. No general quality, speed, cost or equivalence
claim follows. This was not a comparison of optimized communication methods.

See the report for every source artifact, check, disposition, maintainability
score, interruption/anonymity limit and criteria calculation. The separate
failed automatic-routing gate and its cancelled comparison remain unchanged.

## Earlier private pilots

The following entries summarize checks and trials run on 8 November 2026.
Raw evidence (receipts, transcripts, task sources) stays private because it
involves private projects. These summaries are therefore **not independently
auditable**; they are the owner's account, with limits stated.

All of these 8 November checks happened **before** the skill was installed for personal use. Later
real use and policy migration are a separate story (see [history](history.md))
and are not controlled experiments.

## Common limits of both pilots

- Five paired real tasks, one owner, related tasks, **one execution per arm**.
- No statistical inference and no general causal claim.
- Durations are **summed observed model-call elapsed time**. They are not human
  minutes or end-to-end wall-clock time. Shared parent work and native review
  durations are outside these figures.
- Unknown usage (for example, native subagent usage) is unknown, not zero. No
  complete cost measurement was made.
- Each pilot had a decision rule fixed locally before execution: the skill should cut coordinator
  time or coordinator command count by at least 20%. Neither met it.
- Reviewers saw opaque bundles without condition labels, but could plausibly
  infer style differences; blinding was not guaranteed.

## Trial conditions (8 November 2026)

Both pilots used the same roles and requests in **both arms**:

| Role | Model ID | Requested effort | Sessions |
| --- | --- | --- | --- |
| Lead (coordinator) | `gpt-6.1-sol` | High | fresh CLI session per run |
| Writer | `claude-opus-5-5` | High | fresh sessions via subscription CLI |
| Independent reviewer | `gpt-6-astra` | High | fresh native sessions, no history |
| Independent reviewer | `claude-fable-5-1` | High | fresh CLI sessions |

Every assessment was paired: each output was reviewed by both reviewers.

- "High" means the effort was **requested and accepted by the interface**.
  Independent runtime attestation of the effort actually applied was not
  established.
- The writer usage for the timed-out baseline correction (below) is unknown.
- These were the conditions of these trials on that date. They are **not
  recommended model or effort defaults**. The skill and its examples stay
  model-neutral; choose your own in your private profile.

## 0. Structural pre-install validation

Before any pilot, the candidate package was checked privately:

- 52 unit tests passed for the validator and package assets (the private suite
  included one test of a personal profile; the public suite in `tests/` omits it,
  adds repository checks, and its result is reported by whoever runs it);
- nine simulated initial scenarios and two focused follow-up scenarios passed,
  covering solo work without Git, unsupported required effort, exhausted review
  caps, resuming a running assignment, delegation restrictions, unenforceable
  deadlines, records overlap and changed review inputs;
- two independent reviewers completed one initial round and one focused
  follow-up with no remaining material finding.

Capability responses in those scenarios were **simulated**. This is evidence
that the procedure is coherent, not proof of production safety or of a runtime.

## 1. Additive documentation pilot

**Setup.** Five unfinished documentation and decision-support tasks from one
project, each done twice: the existing mature workflow versus the same workflow
**plus** the skill and a private profile. Writers, reviewers, sources, acceptance
criteria, word limits and round caps were matched; writer order alternated.

| Measure | Existing workflow | With skill | Difference |
| --- | ---: | ---: | ---: |
| Coordinator call time, summed | 404.4 s | 535.9 s | +32.5% |
| Coordinator commands | 36 | 49 | +36.1% |
| Writer call time, summed | 507.0 s | 388.4 s | −23.4% |
| Coordinator + writer | 911.4 s | 924.2 s | +1.4% |
| First-pass tasks without material findings | 4/5 | 4/5 | equal |
| Final tasks with material findings addressed | 5/5 | 5/5 | equal |
| Final tasks within the word ceiling | 3/5 | 4/5 | one more |

**Result: coordination-benefit threshold not met.** Coordinator time and commands
both rose. Material findings in both arms were concentrated in one task and were
addressed after one bounded correction round. One extra task met the word
ceiling in the skill arm; three drafts in total stayed slightly over it.

**Important qualifier.** The skill was **added alongside** existing instructions.
Removing duplicated policy, which was the original motivation, was not measured.

## 2. Replacement code-task pilot

**Setup.** Five real implementation tasks in one application, each started from
the same frozen code. The baseline used the existing instructions; the skill arm
used cleaned copies of the instructions with personal model clauses removed,
plus the skill and a private profile. Models and reasoning requests were
explicitly matched, and both arms received the same paired independent review.

| Measure | Existing workflow | With skill | Difference |
| --- | ---: | ---: | ---: |
| Coordinator call time, summed | 378.5 s | 369.1 s | −2.49% |
| Coordinator commands | 29 | 41 | +41.38% |
| Writer call time, summed | 1,759.3 s | 1,199.1 s | −31.84% |
| Coordinator + writer | 2,137.8 s | 1,568.2 s | −26.65% |
| Initial tasks without confirmed material findings | 4/5 | 3/5 | one fewer |
| Final scoped tasks ready | 5/5 | 5/5 | equal, after bounded repairs |

**Result: coordination-benefit threshold not met.**

**Why the 26.65% is not a productivity claim:**

- One baseline correction hit its supervised **480.510-second** deadline and was
  stopped, so its usage receipt is incomplete.
- Identical narrow tool allowlists produced different permission outcomes for
  generated in-writer test commands, giving the two arms different check
  workloads.
- One execution per pair, related tasks.

These confounds prohibit attributing the apparent reduction to the skill.

**Other observations.**

- A pre-existing integration race in the application stayed open in both arms.
  Not every product risk was resolved.
- The skill arm's coordinator followed the profile's single-review default; the
  parent imposed the paired review on both arms. Automatic or named-recipe
  routing was **not** established by this trial.
- Within this explicit setup, moving personal policy out of project files did not
  break the workflow, and project-facing handoffs passed a limited scan for
  model and private-path details. That scan is not a privacy guarantee.

## 3. Installation and discovery check

After the pilots, the unchanged package was installed for personal use with the
existing private profile. A fresh session's native skill catalog listed it, the
profile passed structural validation, and installed file hashes matched. This
verifies **discovery and profile structure** at that time. It does not guarantee
future routing, automatic selection for every task, or runtime effort.

## What the evidence supports

- Separating personal collaboration settings from project files is workable in a
  Codex-led setup.
- In these small samples the skill did **not** reduce coordination effort.
- Writer time and a few quality signals moved in different directions across the
  two pilots; they are too narrow and confounded to generalize.

## What it does not support

General productivity, quality or cost improvements; other lead assistants;
reliable automatic routing; runtime effort attestation; filesystem isolation; or
demand for the tool.

## 4. Same skill, with and without the Rust CLI

The [completed three-case report](../evals/cli-usefulness/2026-11-09/report.md)
retains the [preregistered protocol](../evals/cli-usefulness/2026-11-09/protocol.md),
six final patches, grouped check results and execution qualifications. Both arms
used the same skill and Sol/Astra requests. All six code outputs passed the
required checks; same-invocation receipt recovery succeeded in both arms.

No added CLI benefit was demonstrated. One shared coordinator error supplied an
unsupported native process exit code in two CLI rows; originals and corrections
are retained. Manual baseline assertions, first-use setup, operator carryover
and incomplete work accounting limit inference. Timings are not a speed claim;
tokens, task-attributable quota and cost remain unknown. The local CLI stays
experimental and separate from the distributable skill.

## 5. Matched review-effort pilot

On November 27, 2026, eight fresh Opus 5.5 CLI sessions reviewed four synthetic
cases. Each pair used the same sealed source, instructions and model. Fixed
High was compared with an experiment-only rule that used Medium for the three
one-file cases and High for the cross-file case. Arm order was randomized within
each pair. The lead scored the original findings before revealing the effort
assignments.

| Measure | Fixed High | Medium/High rule |
| --- | ---: | ---: |
| Material seeds found | 3/3 | 3/3 |
| Unsupported material findings | 0 | 0 |
| Elapsed time across the three bounded cases | 53.72 s | 42.27 s |
| Reported output tokens across the three bounded cases | 4,858 | 3,641 |

Both reviewers passed the clean control. The rule used less total time and
fewer output tokens across the bounded cases. One bounded case took longer
at Medium. The cross-file case used High in both arms.

All eight sessions returned terminal results. The backend imported five. The
prompt omitted assignment-specific IDs, and in three pairs both reviewers used
the same finding ID. The backend retained and rejected each duplicate import.
The blind quality scores use the original terminal text. The planned import
check passed only for the clean-control pair.

The pilot covers one model, one run per condition per case and already-routed
assignments. It leaves runtime effort attestation, real-work performance and
automatic activation open. The result supports further testing of a bounded
effort rule. At the time of this trial, fixed effort and `inherit` were the
supported profile choices.

## 6. Harder matched review-effort trial

On November 27, 2026, twenty fresh Opus 5.5 CLI sessions reviewed ten new
synthetic cases. The fixtures covered boundaries, state ordering, idempotence,
mutation and cross-file behavior. Eight cases were one-file reviews, including
two clean controls. The two cross-file cases used High in both arms. Within
each case the model and sealed packet matched, and arm order was randomized.
The lead scored findings against the verified seeds before revealing effort.

| Measure | Fixed High | Medium/High rule |
| --- | ---: | ---: |
| Seeded defects found | 11/11 | 11/11 |
| Unsupported material findings | 0 | 0 |
| Summed reviewer elapsed time for eight one-file cases | 186.05 s | 157.28 s |
| Reported output tokens for eight one-file cases | 15,977 | 13,091 |
| Terminal reviews imported | 10/10 | 10/10 |

Both arms passed both clean controls. Medium found all eight one-file seeds.
It took less time on seven of the eight one-file cases and used 18.1% fewer
total output tokens. All 23 finding IDs used their assigned prefixes. The
backend imported all twenty original terminal responses and verified record
integrity for every pair.

This trial used one model, one run per effort per case and preselected review
assignments. Up to three cases ran concurrently, so the timing is a sum of
individual invocations in that environment. The result supports an opt-in
effort rule for further testing. It does not establish runtime effort, accuracy
on production reviews or a reason to change the default profile.
