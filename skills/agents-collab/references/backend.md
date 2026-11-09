# Optional local CLI backend

Use this procedure when `scripts/backend.py status` reports an enabled CLI.
Missing settings select the manual workflow. Backend settings are separate from
the collaboration profile: `~/.config/agents-collab/backend.json` contains only
`version`, `mode` and an absolute `binary` path. Never install or enable it
implicitly. Installation does not edit the profile, shell or project instructions.

Install a trusted macOS arm64 archive with its expected SHA-256:

```sh
python3 <skill-dir>/scripts/install_backend.py --archive <archive.tar.gz> --sha256 <expected-sha256> --enable
python3 <skill-dir>/scripts/backend.py status
```

The default binary location is `~/.local/bin/agents-collab`; the adapter uses its
absolute path even without a PATH entry. The digest is an integrity check against
the selected archive, not a publisher signature. The engine supports local APFS
on macOS; the current package supports arm64 only. Required supervised timing and
runtime effort attestation remain unsupported. Resolve required capabilities
before dispatch rather than silently downgrading them.

The installer rejects symlink targets and ancestors. If an approved installation
directory is a symlink, verify its canonical destination and supply that path
explicitly with `--bin-dir`; do not remove the link or relax the guard.

## Task and packet preparation

Read project rules, validate the unchanged profile and resolve agent assignments
as usual. `start --help` supplies the repository, project/task IDs, writer,
reviewers, exact editable scope, requirements, criteria, boundaries and checks.
Named agents must exist in the profile; `current-session` can be the writer.
Global `--config`, `--profile` and `--actor` options precede the subcommand.
Do not add models to a profile, waive project rules or infer human approvals.

The returned record is `records_root/{project}/{task}/collaboration`; adapter
inputs, receipts and rendered packets live in its private sibling `host/`.
Keep the same task identity on resumption. Each mutation reads its revision;
conflicts require reconciliation, not automatic retries or renamed tasks.

Use `context` with explicit `--paths`, `--instructions`, `--purpose`, `--round`,
`--quiescence` and `--output` under that task's `host/` directory.
`--omit-other-paths` supplies an explicit reason for excluding the remaining Git
inventory. Review the selection for adequate context; a diff alone is not enough.
No implicit file sweep is authorized. The adapter renders selected UTF-8 source
from stored frozen bytes, with complete requirements and boundaries. Its text
mode rejects binary, symlink and deleted-file selections; resolve another
authorized low-level path if those are necessary. Source snapshots are not
filesystem isolation or frozen external services.

Initial source writing uses `writer_context`; review uses `review`. Writer
context consumes no review round. Keep initial review packets neutral: no writer
transcript, persuasive report or other initial findings. The fixed reviewer set,
independence requirements and follow-up cap still apply.

## Host dispatch and results

Before dispatch, `assignment` prepares the assigned agent and persists launch
intent. The host launches native agents or fresh Claude CLI processes, then
attaches the actual invocation using `observe`. Record interface model/effort
separately from unknown runtime attestation. Omit `--exit-code` for native
notifications that expose no process exit. Actual Claude process exit can be
recorded, but it alone proves no valid review. Reconcile uncertain workers and
original deadlines before retrying; the backend never cancels a worker.

`import-review` accepts the low-level review contract in the source repository's
`docs/cli.md`. Have the reviewer return that contract with exact artifact, packet
and assignment identities, meaningful verification limits and findings. Original
bytes are retained. Inspect `validation`: only `valid_structure_only` covers the
required review; exit zero can accompany a rejected or incomplete result.
Preserve originals and disclose any explicit host adaptation; do not silently
rewrite a result to make it valid. Structural validity attests neither truth nor
authority. The generic `command` route exposes existing low-level contracts for
dispositions and reconciliation without bypassing their gates.

For an installed skill without the source checkout, the review contract is:

```json
{
  "schema_version": 1,
  "assignment": "ASSIGNMENT_ID",
  "artifact": "ARTIFACT_HASH",
  "packet": "PACKET_HASH",
  "verdict": "pass",
  "verification": [{"category":"reviewer_opinion","description":"What was inspected","object":"ARTIFACT_HASH"}],
  "limits": "Checks not run and limits of supplied evidence",
  "findings": [],
  "fresh_session": "Observed session boundary or uncertainty",
  "automatic_context": "Observed instructions, memory, hooks and plugins",
  "tool_boundary": "Actual available tools and source-write restriction"
}
```

The host supplies the three identities from `context` and `assignment` as a
recipient envelope. Verdicts are `pass`, `changes_required` or `blocked`.
Verification categories are `source_claim`, `verified_observation`,
`interpretation`, `reviewer_opinion`, `unknown` and `unavailable`.
Each finding requires nonempty `id`, `location`, `scenario`, `evidence`,
`uncertainty` and `recommendation`, plus boolean `material`. Finding IDs remain
unique across rounds. A pass cannot contain material findings. These declarations
are evidence to assess, not proof of truth or independence.

## Evidence and completion

`evidence --input` retains actual UTF-8 check output or disposition text in a
reconciliation-input object; the prototype has no separate evidence-upload
command. Use its returned hash in `complete --evidence`. Keep private output
private. A stored assertion alone does not prove that a check ran. Completion
fills the declared criterion/check coverage and delegates final source/review
gates to the engine. Real human approvals require actual evidence and explicit
low-level coverage; the helper must not infer them.

A read-only writer disposition can remain host-tracked without becoming a new
source-writing assignment. Preserve its original output as evidence. Material
source fixes require recorded writing, a new artifact and applicable follow-up.
Use `show`, `check` and `packet` for resumption. Backend selection does not enable
automatic skill discovery or establish quality, token or productivity gains.
