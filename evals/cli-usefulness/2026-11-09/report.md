# Same skill, with and without the Rust CLI

9 November 2026. **Six workflows finished; no added CLI usefulness demonstrated.**
This is a three-case feasibility pilot, with one execution per arm. Final code
passed the required checks in both arms. The CLI did not reduce observed
handoff/recovery mistakes or operator correction work. The frozen rule therefore
returns **inconclusive**; retain the simpler workflow for these handoffs. This
is not evidence of equivalence or that the CLI cannot help on other work.

## What was compared

The [protocol, tasks, rubric and starting identities](protocol.md) were published
at [`8b18301`](https://github.com/jaredchu/agents-collab/commit/8b18301dbf3750d8521f0ff305dc202713546fe0)
before arm calls. [Independent protocol review](protocol-review.md) found no
material issue. Both arms used the same frozen Agents Collab skill, host,
requirements, required checks and model requests: `gpt-6.1-sol` / High for writing
and repair; fresh `gpt-6-astra` / High for each initial or focused review.
Requests were accepted by the native interface; runtime model/effort attestation
is unavailable. No Claude, external model API, paid fallback or model grader was
used. Profile timing targets remained advisory; no new usage budget was imposed.

A used prompt-led manual records and ordinary copy/hash/Git operations. B added
the source-only Rust CLI pinned at public commit `94e5723`. The host still
dispatched models and supplied readable neutral envelopes in both arms. Both
materialized full frozen source views: the CLI has no restore command. This tests
record/packet bookkeeping, not automated routing, context selection, model-memory
transfer or a cross-provider transport.

Targets were disposable copies of this public repository. The experimental
validator changes were not merged into the product, installed skill or website
download. The saved owner profile, global instructions and installed skill were
preserved. Detailed observations and artifact hashes are in [results.json](results.json);
[final patches](artifacts/README.md) are public.

## Work quality and recovery

| Case | Manual skill A | Same skill + CLI B | Final grouped checks per arm |
| --- | --- | --- | --- |
| H1: opt-in JSON diagnostics | One material initial finding; repaired; focused review passed | Same independently found defect; repaired; focused review passed | 61/61 |
| H2: identical dirty integer-check draft | Seeded boolean regression found; repaired; focused review passed | Same seeded defect found; repaired; focused review passed | 48/48 |
| H3: version option and missing reviewer receipt | Initial review passed; same real invocation recovered | Initial review passed; same real invocation recovered | 52/52 |

These are grouped behavioral/compatibility checks, including suite results;
**322 grouped checks across the six rows are not 322 distinct test functions**.
No material final code finding remained in the required reviews. This small
observation does not establish general quality superiority or statistical parity.

H1's intended clean handoff naturally required repair in both arms. Both writers
serialized an existing diagnostic that echoed a rejected numeric schema version,
contradicting the new JSON no-echo requirement. Each fresh reviewer independently
reproduced it; the repair removed the value from JSON while preserving the old
human/API behavior. Those unplanned artifact repairs are retained, not rerolled
or relabeled as a CLI benefit.

H2 began from the same authored staged documentation, unstaged validator change
and untracked boundary test. The defect was a deliberate benchmark seed, not an
upstream vulnerability or a spontaneous writer error. Both repairs preserved the
document/test bytes and initial staged path/blob/mode entries. Their final full
working inventories are identical (`80ef5f5235746e70ddc3fad40006ea2fe428e0999522fc54419744bf04ab8353`).

H3 withheld the returned initial reviewer's identity from ordinary records while
retaining a private recovery envelope. In each arm the ordinary assignment was
recorded unknown, the existing host invocation was found running, and that same
identity was reconciled. Unknown snapshots and original start/deadline evidence
were preserved through result acceptance. Neither arm cancelled, rerolled or
launched a replacement reviewer. This was a controlled host-record fault,
**not a provider outage or a test of remote cancellation**. Correct manual
withholding and correct CLI handling count equally.

## Bookkeeping correction, retained rather than hidden

One shared coordinator mapping mistake affected H1-B and H2-B: four native
completion receipts in H1-B and the initial reviewer receipt in H2-B supplied
`exit_code: 0`, although the native host exposes completion but no process exit
code. That numeric assertion was unsupported. Actual host finals and valid
artifact-bound results were separately observed; no false task completion or
source/identity loss was observed.

Original receipts were retained. Each affected row received a correction sidecar,
a CLI reconciliation note and an explicit coordinator annotation interpreting the
numeric code as unknown/null. Later native receipts used null. The public data
counts **one unique incident affecting two rows**, not two independent incidents.
Each row's corrective bundle contained an annotation write, reconciliation input,
CLI reconciliation call and coordinator status update. This is operator input
error and first-use integration friction, not proof of a SQLite engine defect.
It also demonstrates why schema validation cannot attest the truth of a receipt.
The affected coordination outcomes remain qualified despite passing final code.

A had no observed spontaneous coordination correction. B had no case with fewer
mistakes or less avoidable correction work. The seeded H2 repair and planned H3
recovery are excluded from that primary score. No invalid-transition probes were
required or credited as improvement.

## Observed work, with units kept separate

| Row | Delegated model turns | Manual state-file writes | CLI invocations | Common source views / files copied | Readable envelope bytes | Observed row span, seconds |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| H1-A | 4 | 13 | 0 | 3 / 962 | 30,733 | 826.309 |
| H1-B | 4 | 0 | 31 | 3 / 962 | 30,035 | 1,309.528 |
| H2-A | 3 | 10 | 0 | 2 / 642 | 27,936 | 650.053 |
| H2-B | 3 | 0 | 25 | 2 / 642 | 27,424 | 898.561 |
| H3-A | 2 | 8 | 0 | 2 / 641 | 8,840 | 378.441 |
| H3-B | 2 | 0 | 22 | 2 / 641 | 8,840 | 727.615 |

There were **18 delegated arm turns: nine per arm**. The two protocol preparation/
review turns are separate setup; publication evidence review is reported outside
the arms. The coordinator's own inference, thinking and tools are additional and
unmetered. Repairs reused each arm's writer session; every reviewer was fresh.

The table is not a total operator-action or productivity score. A state-file
write, a CLI call, a source copy and a model turn are different units. CLI calls
include JSON preparation/receipt work elsewhere in the ledger; the common source
materialization also performs Git and hash work in both arms. The observed
categories are reproducible from retained wrapper records, but unwrapped reads,
waits, cognitive work and model-internal tools are not a complete census. No
command-count percentage or operator-time saving is inferred.

**No speed claim:** spans include coordinator reasoning, first-use client glue,
user clarification, and publication/browser preparation during model waits.
Self-check workloads also varied: for example, one H1 writer ran the full suite,
the other ran focused suites. H1-B's late provenance correction is included in
its operation total but occurred after its initial row closure. These are
execution spans, not measured model inference time or causal CLI latency.
Preparation cost is additional, not free. Envelope bytes include findings in
repair/follow-up context; differences are not a context-optimization result.
Tokens, task-attributable quota and billed cost remain **unknown**. A shared-account
quota snapshot obtained after H1-A cannot supply paired run usage, and bytes are
not converted to tokens.

## Execution qualifications and reproducibility

- Fixed counterbalanced order was H1 A/B, H2 B/A, H3 A/B. One operator carried
  learning across rows. Only three authored cases in one familiar public project,
  on one macOS/APFS host, were tested. H1/H3 generated drafts and voluntary checks
  differ; H2 initial bytes are identical. These are not randomized repetitions.
- H1-A used ad-hoc artifact/status assertions before manual record writes, including
  completion preconditions. No assertion fired; later manual rows used inspected
  diagnostic output and an explicit lead decision. This is a deviation from a
  strict unautomated eligibility baseline and may strengthen A. It prevents a
  clean causal comparison of added guard protection; it is not silently waived
  or corrected by rerunning completed outputs.
- Original review JSON, SQLite/object files, absolute paths, raw logs and account
  details stay private. Public summaries, hashes, check names and patches support
  source reproduction, but not independent auditing of every original model call.
  Fresh native sessions and read-only intent are not filesystem isolation.
- Native completion is not a process exit code; requested/accepted controls are
  not runtime attestation. Corruption hashes are not proof of truthful evidence
  or human authority. This was not a security audit, encrypted storage evaluation,
  power-loss test, provider outage or cross-provider experiment.
- The CLI, owner configuration and frozen criteria were not fixed mid-trial.
  All failures, required repairs and the provenance correction are retained.

Reproduce inputs with the frozen [builder](build_fixtures.py), apply an arm's
[final patch](artifacts/README.md) to `94e5723`, then run the frozen
[checker](check_case.py). H2's staged documentation needs the same staged entry
when checking its provenance. Experimental patches are evidence, not released
product features. Raw evidence is private. Final evidence-review coverage and
patch-reproduction checks are recorded in [publication review](publication-review.md).
