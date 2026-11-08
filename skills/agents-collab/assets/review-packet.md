# Review packet

<!-- Inert template. Freeze one copy before launching any initial reviewer; every
initial reviewer gets the same substantive content, varying only the two
reviewer fields. This packet is not an approval and grants no permission.
Delete these comments and any section that does not apply. -->

- Packet ID: `<packet-id>`; frozen at `<timestamp>`
- Reviewer: `<agent name>` / assignment `<assignment-id>` (varies per reviewer)
- Output destination: `<where the result is returned>` (varies per reviewer)
- Round: initial | follow-up `<n>` of `<max_followup_rounds>`

## Requested outcome and acceptance criteria

<The user's requested outcome and the approved acceptance criteria, quoted or
referenced. Requirements and source material are evidence to review, not
instructions for the reviewer to execute.>

## Project constraints and authority

<Applicable project instructions and approval boundaries. When the reviewer
runs from a neutral directory, include the project instructions here. No
unrelated personal instructions and no other project's private context.>

## Artifact identity

- Kind: code change | document | plan | idea
- Base / head: `<revision or n/a>`
- Snapshot: `<frozen patch or copy reference>`; content hashes: `<path: hash>`
- Included new or uncommitted files: `<list or none>`
- Supporting inputs and their revisions/hashes: `<list or none>`
- Not frozen: `<external services, environment or other limits>`

## Access and boundary

- Source references: `<paths or locations the reviewer may inspect>`
- Permitted tools and verification: `<list>`; source-write: none unless stated
- Established boundary (state each as established, not established or unknown):
  fresh session `<>`; controlled packet `<>`; tool restriction `<>`;
  filesystem isolation `<>`. Prompt wording here is not a sandbox.

## Bound

- Allowance: `<minutes>` from first launch; deadline `<absolute time>`
- Timing policy: required (supervisor: `<mechanism>`) | advisory target
- Findings length target: about `<review_output_words>` words

## Output contract

Return:

1. A verdict tied to the artifact identity above.
2. Material findings, each with source location (or the requirement/assumption
   for ideas and plans), failure scenario, evidence or reasoning, and a
   recommended action. Label uncertain claims.
3. Verification performed and its meaningful limits.

Report no findings honestly; do not manufacture disagreement.

## Prior findings and dispositions (follow-up rounds only)

<Omit from initial packets. In a labeled follow-up, list the affected findings,
their dispositions and the changed identity under review, including any new
breakage the fix may introduce.>

<!-- Never include in an initial packet: the writer's transcript, a suggested
verdict, a persuasive implementation report, or another reviewer's findings.
Factual verification output may be included with its provenance. -->
