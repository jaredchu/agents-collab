# Quality-first pilot: completed grading after an access interruption

**The recovered grading is complete. No skill-specific quality advantage over
manual coordination was established.** Both independent-review paths fixed a
reproduced script-invocation regression missed by self-check. The formal
observed-acceptance rule favors both review paths over self-check, but its
required second initially material draft depends on an untargeted failure in an
existing test. Removing those failures in a disclosed sensitivity retains two
task wins, but leaves too little initial material error to meet the frozen floor.

This is six authored tasks in one Rust project, with one draft per task and no
repetitions. It supports a concrete example of useful independent review, not
a general quality, speed, cost or equivalence claim. Communication and handoff
methods were held fixed; this was not an optimization experiment for them.

## Design and commitments

The [protocol](protocol.md), [tickets](tasks.json), [rubric](rubric.json),
[schedule](schedule.json), profile and checker commitments were
[published before drafting](https://github.com/jaredchu/agents-collab/commit/b5d53f0).
All [six genuine initial drafts](initial-drafts/manifest.json) were
[published before finishing](https://github.com/jaredchu/agents-collab/commit/a4cc020).
No draft or finishing state was selected, rerolled or changed using hidden
results. Every task's A/B/C branch started from the same commit and tree.

The target was public [ProcLease commit 37975b5](https://github.com/jaredchu/proclease/tree/37975b5245fcb5cac7b16fac74efd01269dff5d8),
exported into disposable repositories. These are evaluation tickets, not existing
ProcLease issues or product changes. The study did not edit the active checkout.
It is separate from the [failed routing gate](../../automatic-routing/2026-11-09/report.md);
that gate's cancelled 36-run comparison remains cancelled.

| Path | Finishing procedure |
| --- | --- |
| A | Fresh same-model self-check and one justified repair pass |
| B | Manual independent review, then writer repair if justified |
| C | Explicit `$agents-collab`, choosing the same reviewer/writer from the benchmark profile |

Roles: `gpt-6.1-sol` lead, `claude-opus-5-5` initial/revision writer,
`gpt-6-astra` B/C reviewer, `claude-fable-5-1` anonymous grader; all requested
High. These are experimental conditions, not product defaults. Native/CLI
interface acceptance and provider model IDs do not independently attest runtime
effort. A used a fresh same-model session, not its original author's transcript.

The lead and reviewer were read-only for source; Opus owned source repair.
All six C leads read the skill and dispatched the configured reviewer. Four B/C
branches needed repair. C-Q6 used an extra fresh Opus call for an exact formatting
correction within the original repair assignment/deadline; that call is retained.
No API, substitute model, paid fallback or account reset was used.

## Interruption, withdrawal and recovery

All six drafts and 18 finishing runs completed. Deterministic grading covered
24 states, deduplicated to 12 source identities including executable modes and
symlink targets. The first six required Fable grading calls failed on a
subscription limit and returned no assessments. The initial publication was
premature: an access limit did not finish the experiment. At the owner's request,
its current public files and website presentation were withdrawn. Earlier Git
history was retained.

After the owner reported restored access, a small exact-model preflight passed.
The [recovery amendment](recovery/amendment.md) was written, privately committed
by hash and independently reviewed before the missing assessments resumed.
It preserves source, rubric, criteria and earlier failures. Prior call wall time
was subtracted from the original 480-second advisory/720-second outer grading
allowances; blocked waiting was explicitly excluded. It does not pretend the
original assignments continued uninterrupted. No participant work was repeated.

Because the old anonymous mapping had already been public, recovery used new
private labels and random order. Source identities were rechecked. Packets
excluded previous findings, condition labels, lookup fingerprints and timings.
Fresh CLI calls used safe mode, restricted file tools (Read/Glob/Grep), strict
empty MCP and no session persistence. The audit records 102 tool calls with
no outside-packet path attempts or unexpected tools. This is observed access
control, not proof that previously published source could never be recognized.

Independent recovery-method review found and fixed three issues before grading:
elapsed times remained in logs; complete mode/link/path/budget identity was not
enforced at dispatch; and remaining advisory time was not supplied to graders.
Its single focused follow-up cleared the amended identity. The original failed
attempts and recovery receipts are retained separately.

All six recovery calls returned complete assessments of the 12 distinct trees,
with maintainability scores for every state through identity aliases. Two
responses had a prose preface before a complete JSON object. That object was
parsed deterministically without content changes or a model retry; original
responses/parser states and the [format disposition](recovery/format-reconciliation.json)
are retained. Complete grading is not inferred from a successful process exit.

## Original deterministic outcomes

Every state built and passed formatting and Clippy. Full `cargo test` passed
for 21/24 state labels and failed for 3: Q4-I and Q4-A share one tree and one
failed execution; Q6-A had the other failed execution. Both failed the existing
`slow_partial_control_request_cannot_starve_expiry` test with `ConnectionRefused`
and expiration before command startup under its 700 ms lease. Its code is
unchanged from the pinned base. Load/concurrency is a hypothesis, not an
established cause. No passing rerun replaces these failures.

The frozen hidden checker produced 292 state-level outcomes: 290 pass, 2 fail,
0 not-run. Both failures were `q4.deferred.report` in B/C. That whole check is
invalidated for every Q4 state under the frozen post-freeze rule, leaving 288
valid passing outcomes. Original checker bytes, results and logs remain intact.
Passing checks did not catch the script-invocation case later reproduced.

[All grades and aliases](grading-index.json), [original logs](grading/),
[all 24 patches/manifests](artifacts/) and [state records](state-ledger.json)
are available. Zero counted defects below means zero corroborated defects under
this evidence, not proof of correctness.

## Specification dispute: Q4 cannot carry a settled safety claim

Q4 criterion 3 requests protected deferral “exactly as today” with a parenthetical
“nothing deleted”; criterion 4 requests exactly the candidates that a real call
would remove from the same state. Yet the base previews hypothetical ordinary
candidates while protected and still retries deletion of already-quarantined
history. The wording does not uniquely resolve those inherited behaviors.

The initial operator record called I/A's preview a major defect and I/A/C's
quarantine deletion a blocker. Recovered anonymous grading challenged that
certainty and instead suggested B's quarantine preservation might diverge from
“exactly as today.” The [reproductions](supplementary-probes.json) settle what
each tree does, but cannot settle a contradictory authored requirement.

Both opposing allegations are therefore recorded as **unconfirmed requirement
disputes**, not counted as settled defects or validated corrections. The checker
is excluded because its chosen interpretation is not a unique oracle. No
criterion is rewritten and no actor is rerun. The prior operator-only record
is retained in [interruption/](interruption/), with its overconfident classification
explicitly superseded here. This also corrects the earlier description of a
confirmed safety defect left by C.

## Counted findings and rubric dispositions

- **Q6 script invocation — major:** without `--cwd`, unconditional absolute-path
  rewriting changes a shebang script's `$0`. An executable `./probe` prints an
  absolute pathname in I/A, while the pinned base and B/C print `./probe`.
  Both independent reviews found it; their writers fixed it. Self-check retained
  the runtime code. The anonymous grader suggested minor severity; the frozen
  rubric explicitly classifies unchanged-behavior regressions as major.
- **Q6 README rendering — minor:** the metadata paragraph becomes a lazy
  continuation of the final `--cwd` bullet. Rendering all four trees with
  `marked` in non-GFM mode confirms it in I/B/C and its correction in A.
- **Q4/Q6 full-suite outcomes — major:** retained under the frozen common
  acceptance rule. Q4 fails in I/A; Q6 fails only in A. These are observed
  acceptance failures, without a claim that edits introduced the old test's
  failure. Fable's suspicion that A's new parser test caused its failure is
  contradicted by the named failure in the original log.

Two additional Q4 test weaknesses count minor under the frozen rubric:
I/A/B's keeper-absence check masks guardian coverage (C corrects it), and I/A
omit protected preview-candidate assertions (B/C correct them). Neither requires
inventing a runtime failure or resolving disputed candidate semantics. Remaining
anonymous findings were notes, unconfirmed risks or the Q4 dispute. Q2-A's process-free fixture is not a demonstrated
correction of an initial log behavior defect. The inheritance qualifier in A's
README is a clarification, not a second counted documentation defect.

[Defects and state transitions](defects.json), [every anonymous-finding disposition](blind-finding-dispositions.json),
and [actor finding reconciliation](finding-reconciliation.json) separate
corroboration from model opinion. No unrelated passing check is used to declare
a finding false. No unique additional confirmed source defect was discovered
only by blind grading; the README issue had already been identified by A.

## Per-task scores

Score is `(fatal + blockers, majors, minors)`; lower wins lexicographically.
`M` is the anonymous maintainability score (0–4), descriptive only.

| Task | I | A | B | C |
| --- | --- | --- | --- | --- |
| Q1 state filter | (0,0,0), M3 | (0,0,0), M3 | (0,0,0), M3 | (0,0,0), M3 |
| Q2 log head | (0,0,0), M3 | (0,0,0), M3 | (0,0,0), M3 | (0,0,0), M3 |
| Q3 list sort | (0,0,0), M3 | (0,0,0), M3 | (0,0,0), M3 | (0,0,0), M3 |
| Q4 prune keep | (0,1,2), M3 | (0,1,2), M3 | (0,0,1), M2 | (0,0,0), M3 |
| Q5 summary | (0,0,0), M3 | (0,0,0), M3 | (0,0,0), M3 | (0,0,0), M3 |
| Q6 launch directory | (0,1,1), M3 | (0,2,0), M2 | (0,0,1), M3 | (0,0,1), M3 |

Maintainability values are the grader's actual values, including qualifications.
For A-Q6 its explanation partly speculates about the wrong failing test;
that causal explanation is corrected above, and the descriptive score is
preserved rather than silently regraded. Maintainability differences never count
as task wins.

## Registered rule and sensitivity

The rule requires ≥2/6 wins, more wins than losses, a winning task with a
validated major/blocker correction still present in the comparator, no new
blocker, no increased summed majors and complete grading. Fewer than two
initial material drafts would be insufficient. All six assessments and evidence
reconciliation are now complete; unconfirmed disputes do not become counted
issues just to fill a score.

| Comparison | Primary wins/losses/ties | Frozen observed-acceptance rule |
| --- | --- | --- |
| B vs A | 2 / 0 / 4 | Met; second material initial draft depends on existing-suite outcome |
| C vs A | 2 / 0 / 4 | Met; same material-draft-floor dependency |
| C vs B | 1 / 0 / 5 | Not met; Q4 minor-test win only; no skill-specific advantage established |

There are two initially material task units in this primary ledger: Q4's
full-suite failure and Q6's script regression. Only Q6 supplies a corroborated
material **source** correction; Q4 provides two minor test-coverage corrections. Major totals across finals are A=3, B=0, C=0;
no corroborated introduced blocker is present. An observed test-outcome transition
is not a proven code-caused regression or repair.

A disclosed **post-hoc sensitivity** excludes only the two untargeted existing
test failures. Original primary observations remain published, with no reruns.
B and C still each win Q4 (minor test coverage) and Q6 against A (2/0/4), but
only one initial task has a confirmed material source defect. Both therefore
fail the frozen two-initial-material-draft floor. C vs B still has one minor-test
win and five ties, below threshold. Thus the formal primary advantage is not
robust to these existing-test outcomes, and cannot justify a broad quality claim. No result establishes equivalence or harm-free parity.

[Machine-readable criteria checks and sensitivity](analysis.json) retain each
condition, task win and count. No speed or token saving offsets a quality issue.

## Measurements and operational limits

| Path | Sum of six branch wall times | Median | Range |
| --- | ---: | ---: | ---: |
| A | 1,807.253 s | 313.189 s | 235.129–332.650 s |
| B | 1,411.214 s | 181.132 s | 146.469–369.003 s |
| C | 1,872.081 s | 241.032 s | 167.101–540.261 s |

Branches overlapped; sums are not elapsed study or human time. Drafting,
recovery waiting, grading and preparation are separate. [Initial receipts](initial-receipts.json),
[selected finishing receipts](selected-receipts.json), [native context observations](native-context-receipts.json)
and [recovered grading receipts](blind-assessments.json) expose available usage.
The first three failed grading calls have partial usage; the next three have
unknown usage, not zero. Billed subscription cost is unknown; list-price
estimates are not subscription spending.

Requested permissions were matched, but actual CLI outcomes differed. Q1-A's
report/helper and Q4-A's reports were denied; coordinators retained output and
ran authorized verification without source edits. Q3-A retained its draft after
a report-write denial prevented a proposed paragraph-spacing edit. Some `git -C`
forms were denied while plain read-only Git worked. These are attribution
confounds, not reasons to drop a state or bypass permissions.

The [scope audit](scope-audit.json) distinguishes zero root-operator interventions
from coordinator handling. No actor commit or out-of-scope source change was
observed. Owner configuration and installed skill hashes were unchanged.
Owned command groups were absent and known fixture jobs cleaned; deleted
metadata/external provider workers prevent a universal process-absence claim.

The recovery amendment was reviewed and hashed privately before resumed calls,
not publicly preregistered at that point. Earlier public mappings/observations,
shared host/cache contention, no reference implementation, incomplete visibility
of original participant reads, subjective static grading and authored-task
ambiguity limit inference. New private labels, fresh restricted contexts and
an access audit reduce accidental unblinding; they cannot prove it impossible.

## Inspect and reproduce

- [Frozen inputs](frozen.json), [protocol](protocol.md), [preflight](preflight.json), [all 24 artifacts](artifacts/), [initial drafts](initial-drafts/manifest.json)
- [Original deterministic outputs](grading/), [identity aliases](grading-index.json), [exact revealed checker](revealed-grader.py), [original revealed mapping](revealed-mapping.json)
- [Recovered anonymous assessments and amendment](recovery/), [recovered receipts](blind-assessments.json), [every disposition](blind-finding-dispositions.json), [complete ledger](defects.json)
- [Original failed attempts and withdrawn observations](interruption/), [supplementary probes](supplementary-probes.json), [portable probe utility](posthoc-probes.py)

[grade.py](grade.py) reconstructs a preserved artifact from the pinned base,
its complete patch and any untracked manifest, verifies source/mode/link identity,
and runs checks in a new short private fixture root. It requires Python 3.12+,
a compatible Rust toolchain, a credential-free offline Cargo cache, and a trusted
pinned-base cleanup binary. Use disposable state, never the user's live registry.
The report's earlier reconstruction commands remain in the frozen utility help.

Source and outcomes can be rechecked; model outputs are nondeterministic.
Receipts and packets are selected and sanitized, so original provider execution
is not independently auditable end to end. Recovery commitments bind private
packet bytes; sanitized path metadata is a derivative. Source manifests remain
publicly verifiable. No global profile change, skill rewrite or participant
reroll was used to obtain the recovered results.
