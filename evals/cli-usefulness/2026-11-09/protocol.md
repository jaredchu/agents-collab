# CLI usefulness preregistration

Prepared 9 November 2026. **Unstarted protocol; no results or effectiveness claim.**
Freeze and publish this directory, its SHA-256 manifest and independent protocol
review disposition before any experimental arm calls. Protocol-preparation/review
calls are outside the six experimental rows and must be accounted for separately.
If criteria or fixtures change after publication, preserve the original and
declare the deviation before the affected arm; never silently revise an outcome.

## Question and controlled comparison

Does the frozen local Rust record-and-packet CLI reduce coordination mistakes or
operator repair in three representative handoffs without a material correctness
regression, compared with using the **same Agents Collab skill manually**?

- A: the installed skill, its templates and prompt-led procedure, with ordinary
  Git, hashing, copying, shell commands and manually maintained private records.
  The lead chooses and records transitions; no new baseline lifecycle, round,
  review-validity or completion enforcement script is permitted.
- B: the same skill and host, using the Rust CLI for task/assignment records,
  frozen artifacts, sealed packets, review imports, dispositions and gates.
  The binary neither dispatches nor supervises models. The lead supplies truthful
  inputs, inspects outputs and makes the same substantive decisions as A.

Both use requested `gpt-6.1-sol` / `high` for actual writing and repair, and fresh
independent `gpt-6-astra` / `high` for review. The native host dispatches both
arms. Record requested controls, accepted controls and actual observations
separately; runtime effort attestation remains unknown unless independently
available. No Claude, provider API, paid fallback, model grader or extra reviewer.
The operator/lead is the same. This is a small same-operator comparison, not a
blind or randomized trial and not evidence of statistical parity.

## Fixed inputs, cases and order

Source and CLI implementation are frozen at public commit
`94e57237e48eaee5c1583c95bbd9b408a4b803bc`; no implementation fixes, rebuild from a
changed tree, installation or skill/profile/global change during the comparison.
Record binary SHA-256, source tree hash, toolchain, OS/filesystem and installed
skill file hashes before arm calls. The owner profile stays untouched. Both arms
use the same derived study configuration: the explicit Sol/Astra requests and
external study records root, preserving the owner's timing, access, effort-check
and follow-up policy. Record that neutral derivation privately, not as a change
to the installed owner profile. Freeze the installed skill equally for both arms.
The source copies are disposable experimental targets,
never upstream edits. [Tasks](tasks.md) are the complete common requirements.
[Starting identities](starting-identities.json) freeze fixture bytes and Git state.

| Sequence | Case | Arm order | Model stages |
| --- | --- | --- | --- |
| 1–2 | H1 clean JSON diagnostic feature | A then B | Sol writes; fresh Astra initial review |
| 3–4 | H2 identical seeded mixed-state draft | B then A | fresh Astra initial review; Sol repairs; fresh Astra focused follow-up |
| 5–6 | H3 supported-version feature and missing launch receipt | A then B | Sol writes; fresh Astra initial review; coordinator reconciles that same invocation |

H1/H3 have actual writing; H2 starts with identical pre-authored staged docs,
unstaged code and an untracked test. Its material defect is disclosed only in the
[coordinator oracle](oracle.md). H3 deliberately omits the returned real initial
reviewer invocation receipt from the normal durable record while retaining a
private recovery envelope. It is a host-record fault, **not** an observed provider
outage. Recovery must reconcile the same real invocation without cancellation,
reroll, replacement, duplicate dispatch or clock reset.

Same starting bytes, requirements, roles, source access, fresh initial reviewer
context, review contract and acceptance checks in each pair. H1/H3 model outputs
may differ; initial reviews assess their own arm's frozen output, not an asserted
identical generated artifact. H2 initial reviews assess identical working bytes
and Git provenance. No arm may consume its paired arm's output or findings.
Fresh sessions and instructions do not create filesystem isolation.

## Common execution and review procedure

1. Materialize the paired copies before dispatch. Verify their complete working
   inventories, HEAD, index/status and staged/unstaged hashes against the frozen
   identities. Preserve original copies and receipts. Capture only public source
   and sanitized task requirements in packets; keep oracle/checker/other-arm
   outputs and persuasive writer reports out of initial review context.
2. Resolve one writer, the fixed reviewer and their exact scopes. Persist stable
   assignment ID, launch intent, requested controls, original start/deadline,
   advisory enforcement and next operation before each actual dispatch. Attach
   host invocation identity promptly except the explicitly injected H3 gap.
   Common helpers may materialize/copy/hash/log/check behavior; they must not
   implement the CLI's state machine for A or dispatch either arm's models.
3. For H1/H3, record writing completion, inspect permitted scope and freeze output
   while the writer is quiescent. For H2 freeze the supplied mixed-state draft
   directly. Include relevant surrounding source/tests and all task safeguards;
   record omitted inputs. Store packet bytes/hash and source inventory before
   launching the initial reviewer, using A's manual files or B's CLI objects.
   Materialize an equivalent read-only-intent full source snapshot for actual
   review access in both arms; B's CLI has no restore command. Copy/mode/hash
   verification is common host work and counted in each arm. Keep staged/base
   provenance alongside that working tree rather than pretending a plain copy
   alone preserves the index.
4. Use a fresh no-history reviewer context. Give the case requirements, applicable
   source instructions, exact artifact/packet identity, read-only scope, permitted
   local checks and the common finding contract. Do not give writer transcripts,
   verdict suggestions, the other arm's review or oracle. Store the artifact-bound
   original review before sharing dispositions. A structured review must state
   verdict, findings with location/scenario/evidence/materiality/recommendation,
   checks and limits, freshness, automatic context and actual tool boundaries.
   Both arms request the same substantive fields; any CLI serialization wrapper
   is treatment overhead and its bytes/actions are counted.
5. Validate findings against source and acceptance. Record addressed/rejected/
   deferred/unresolved with evidence. Only Sol makes material source repairs.
   H2 necessarily receives its scheduled repair and focused follow-up; H1/H3
   receive a repair/follow-up only for confirmed material issues. One initial
   review plus **at most one** focused follow-up per arm, no reset through new
   tasks/reviewers. A follow-up uses a fresh reviewer, the new frozen identity,
   prior findings/disposition and affected requirements. Do not add model calls
   merely to equalize stochastic extra work: disclose unequal calls/coverage.
6. Run the same offline behavioral checker and existing focused suites on both
   final outputs. Inspect scope, documentation, source/privacy and review quality
   manually as specified below. Finish only with current-identity required review
   coverage, resolved material issues, passing criteria/checks and no unresolved
   active/unknown invocation. CLI structure/exit-zero is not truthful evidence.
   Record invalid imports, refusals and operator corrections without repairing or
   replacing original evidence. A malformed model output is preserved; any
   coordinator transcription into CLI JSON is disclosed as operator work and
   may not change its substantive verdict, claims or findings.

The existing advisory policy is unchanged: 30 minutes per writer, 8 minutes per
reviewer, 800-word review target, one follow-up maximum. These are not technically
enforced deadlines or new token/call/quota budgets. Keep original launch times
and absolute targets through reconciliation; report target overruns. There is
no experiment timeout, artificial usage cap or automatic access retry. A genuine
subscription, quota, permission or required-access interruption leaves the study
unfinished; retain evidence and keep final results unpublished until all required
stages can finish through an authorized continuation.

## Checks and quality rubric

`build_fixtures.py` deterministically constructs inputs; `check_case.py` runs
observable acceptance cases plus the existing validator and setup-wizard suites.
The checker is coordinator-only, not a hidden requirement source or model grader.
Workers receive all requirements, can inspect existing tests, and run their own
checks. The coordinator runs the held-out checker after required review/repair,
so it cannot silently replace review in one arm. If it reveals an issue with a
remaining allowed follow-up, record the discovery and use that remaining round;
otherwise report failure/unresolved work. Do not fix the binary during the study.

For each row record separately:

- **Artifact correctness:** all stated requirements, privacy/read safety,
  default/API compatibility, docs, scope and meaningful test coverage. A material
  defect violates required behavior, loses/misidentifies evidence, breaks the
  strict contract, or could authorize false completion/duplicate invocation.
  Minor means cosmetic or clarity-only with no acceptance consequence.
- **Review correctness:** actual material findings, misses and unsupported claims,
  compared with reproducible evidence. Unsupported means a claim lacking support;
  it is not automatically a demonstrated artifact defect. Reviewer agreement and
  structural validity are not quality or runtime-attestation evidence.
- **Coordination correctness:** requirement coverage, exact dirty-state capture,
  frozen packet/source identity, fresh reviewer context, round accounting,
  truthful dispositions, original invocation/timing and no false completion.
- **Recovery correctness:** H3's original real invocation and deadline survive;
  retain the missing-receipt state and subsequent host observations. Correctly
  withholding completion/refusing dispatch under uncertainty counts equally in A
  and B. H2's unrelated staged/untracked work and index survive repair; restoring
  validator bytes to HEAD is allowed and can remove its unstaged marker.

A row is **completed/pass**, **completed/fail** (required behavior/check or
coordination violation demonstrated), **incomplete** (a required stage cannot
finish), or **unsupported** (required capability cannot be exercised). Unsupported
is not a passing negative control; interrupted work is not an effectiveness
failure or a completed negative result. Retain the reason and partial stages.
If final artifact fails despite coordination succeeding, record both facts.

Distinguish the predeclared H2 seed and H3 gap from spontaneous mistakes.
Optional invalid-transition probes must be labeled injected and scheduled
identically in both arms; they are not part of the primary usefulness score.
No such additional probes are required. A manual lead correctly refusing an
invalid action under the same policy has the same correctness outcome as CLI
refusal. A tool gate's refusal alone is not a spontaneous-error reduction.

## Measurements and decision rule

Keep an append-only private action ledger with UTC observation, row/stage, actor,
operation, tool/host call or manual file operation, object identity, result and
whether planned, injected, spontaneous mistake, or repair. Count real actions,
including input preparation, record edits, Git/hash/copy operations, CLI
mutations/reads, dispatch/wait/reconciliation, imports, invalid inputs, repeated
operations, format transcription and completion checks. Batch calls retain their
component operations. Report operational totals by category and raw unit;
an arbitrary shell grouping is not a measured productivity unit. Do not conceal
CLI bookkeeping or manually automate A into a new competing runtime.

Primary comparison: spontaneous handoff/recovery mistakes and avoidable operator
repair actions, with concrete incident descriptions. Planned feature repair from
the seeded H2 defect and planned H3 reconciliation are case work, not spontaneous
mistakes. Count extra corrections caused by mishandling them separately. A
correctly refused injected request is not a benefit by itself.

Secondary observations: total operator actions, elapsed coordination span from
row preparation to last required completion check (including model waits), model
call count/spans when observed, bytes and SHA-256 for source/packet/result bodies,
repeated source excerpts or observed rereads, and available native usage/cost.
Record clock/latency limits and any unobserved time. Provider tokens, remaining
quota and billed cost stay **unknown** if unavailable; never convert bytes to
tokens or calls/elapsed time to cost. Distinguish necessary independent reading
from avoidable duplication. Pre-study fixture/checker development is a separate
setup cost, not attributed to either arm; arm-specific packet/record preparation
belongs to its row.

Accept usefulness only if every required stage finishes, B has **no material
correctness regression relative to A** on any case, and B shows fewer spontaneous
handoff/recovery mistakes or less avoidable operator repair in at least one case.
A material B regression fails that rule even if another case improves. If all
complete and no qualifying benefit appears, declare **inconclusive** and retain
the simpler workflow. Do not infer parity, general effectiveness, autonomous
enforcement, quality superiority, token/quota/cost savings or broad speed gains.
An incomplete/unsupported required row leaves the comparison unfinished, not
inconclusive completed evidence. Report stochastic output differences, same
operator learning/carryover, counterbalanced but fixed order, only three cases,
one owner/host/platform, and unavailable measurements prominently.

## Reproduction boundary

Build and inspect the CLI according to [the frozen CLI guide](../../../docs/cli.md).
Use `build_fixtures.py --source SOURCE --out PRIVATE_NEW_DIRECTORY` to materialize
paired copies. Run `check_case.py --case H1 --repo COPY --scratch PRIVATE_TMP`
(substitute H2/H3); add `--start ROW.start.json` for H2. Output is raw private
diagnostic evidence and can contain local paths; sanitize before publication.
Neither helper dispatches a model or manages collaboration lifecycle. Public
summary publication requires separate root integration and evidence review.
