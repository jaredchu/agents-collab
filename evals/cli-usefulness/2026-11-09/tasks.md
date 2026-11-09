# Frozen task specifications

Each case starts at public Agents Collab commit
`94e57237e48eaee5c1583c95bbd9b408a4b803bc`. These are experimental changes in
disposable copies, not proposed upstream changes. Both arms receive the same
case text and applicable source instructions. Do not send the other cases,
protocol, builder, checker or oracle to workers. This is a context policy, not
filesystem isolation.

## H1 — JSON diagnostics

Requested outcome: add opt-in `--json` diagnostics to
`skills/agents-collab/scripts/validate_profile.py`.

- R1: `validate_profile.py --json PROFILE` emits exactly one JSON object on
  stdout and no stderr for a valid invocation, with exactly `schema_version`
  (integer `1`), `valid`, `issues`, and `scope` (`"structure-only"`). Each issue
  has exactly string `path` and `message` fields.
- R2: A valid profile returns exit 0, `valid: true`, and no issues. Invalid
  structure, malformed JSON, invalid UTF-8, duplicate keys and oversized content
  return exit 1, `valid: false`, and nonempty issues. Unreadable/nonregular input
  returns exit 2, `valid: null`, and a nonempty content-free issue at `(file)`.
  Argument-usage errors retain argparse's exit 2 and need not be JSON.
- R3: Keep the existing default human output, exit codes, importable validation
  API, bounded/nonblocking input reader and field-value redaction. JSON is
  serialization of safe diagnostics, never an echo of rejected values.
- C1: Existing validator and setup-wizard tests pass; add focused JSON CLI tests
  for success, content failure and an OS/nonregular failure. Use no dependencies.
- S1: Edit only the validator, `tests/test_json_diagnostics.py` (new), and
  `skills/agents-collab/references/configuration.md`. Add concise usage docs.
  No commits, external services, installs, global/profile edits or publication.

Initial writer: implement and self-check. Independent reviewer: inspect the
frozen output and relevant surrounding source/tests against every requirement;
run meaningful focused checks. Return artifact-bound findings and limits.

## H2 — Review and repair an existing integer-check refactor

Requested outcome: independently review the supplied mixed-state draft of a
small integer-check refactor, then repair confirmed material defects while
preserving the existing strict v1 contract.

- R1: Integer fields accept actual Python/JSON integers only, excluding booleans,
  floats, strings and null. `review.max_followup_rounds` allows zero; all three
  numeric bounds require positive integers. Preserve version checks and all
  existing diagnostics/API/privacy behavior.
- R2: Preserve the staged documentation addition and the untracked
  `tests/test_integer_boundaries.py` byte-for-byte. Preserve the initial Git index
  staged path/blob/mode entries exactly (`git ls-files --stage -z`, not raw index
  stat-cache bytes); do not stage, reset, stash, clean, commit or delete existing work.
  Only the validator is editable during repair.
- C1: Existing validator and setup-wizard tests and the supplied boundary test
  pass. Cover false/true, zero, positive, negative, float, string and null values
  across the four numeric fields when verifying the repair.
- S1: Initial review is read-only. The assigned writer repairs only after that
  review is durably recorded. Freeze the repaired output for one focused review
  of the fix and its consequences. No upstream, external, global or profile work.

There is no initial model writing stage: both arms start from the identical
pre-authored draft. Initial reviewer: assess the draft as supplied, without a
suggested verdict or defect description. Repair writer receives the recorded
findings and the same requirements. Follow-up reviewer receives the new identity,
prior findings and disposition; check the material fix and possible regressions.

## H3 — Supported-version option

Requested outcome: add `--print-supported-version` to the validator CLI.

- R1: `validate_profile.py --print-supported-version` prints exactly `1\n` to
  stdout, emits no stderr, exits 0 and neither requires nor reads a profile.
  Obtain the number from `SUPPORTED_VERSION`, rather than duplicating a literal.
- R2: Supplying both that option and any positional profile is a usage error:
  exit 2, no stdout, and no profile read. No-argument usage remains exit 2;
  `--help` remains exit 0. Ordinary profile validation is unchanged.
- C1: Existing validator and setup-wizard tests pass. Add focused tests for the
  option alone, conflict with a missing path, no arguments and ordinary validation.
- S1: Edit only the validator, `tests/test_supported_version.py` (new), and
  `skills/agents-collab/references/configuration.md`. Add concise usage docs.
  No commits, external services, installs, global/profile edits or publication.

Initial writer: implement and self-check. Independent reviewer: assess the frozen
output and surrounding integration against every requirement. The coordinator's
record-recovery exercise does not alter this software task or permit a duplicate
model invocation.
