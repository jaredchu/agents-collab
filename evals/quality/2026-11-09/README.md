# Quality-first pilot data

Read the [full report](report.md) first. All registered comparisons are
incomplete/inconclusive because the required blind grader returned no completed
assessments. Operator corroborations are separate from blinded grading.

- Frozen inputs: [protocol](protocol.md), [tickets](tasks.json), [rubric](rubric.json), [schedule](schedule.json), [commitments](frozen.json), [preflight](preflight.json).
- Outputs: [initial manifest](initial-drafts/manifest.json), [24-state ledger](state-ledger.json), [all patches/manifests](artifacts/), [deterministic grades](grading/), [identity aliases](grading-index.json).
- Provider evidence: [initial receipts](initial-receipts.json), [selected finishing receipts](selected-receipts.json), [native context metadata](native-context-receipts.json), [failed blind calls](blind-assessments.json), [anonymous packets](blind-packets/).
- Analysis: [defects/partial observations](defects.json), [finding reconciliation](finding-reconciliation.json), [inconclusive comparisons](analysis.json), [supplementary reproductions](supplementary-probes.json).
- Rechecking: [offline grading utility](grade.py), [exact revealed checker](revealed-grader.py), [revealed mapping](revealed-mapping.json), [post-freeze probe utility](posthoc-probes.py).
- Publication: [scope audit](scope-audit.json), [checks](publication-checks.json), [independent publication review](publication-review.json).

Source manifests preserve executable modes and symlink targets. Empty untracked
manifests mean there are no untracked source payloads to restore. Raw provider
conversations and account details are private; public source artifacts can be
reconstructed and rechecked, but provider execution is not fully replayable.
