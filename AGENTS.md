# Project instructions

Read `README.md` and `docs/project-context.md` before changes.

## Scope and evidence

- Keep the reusable skill in `skills/agents-collab/` generic and configured through external profiles. Project documentation has no personal model or reasoning defaults.
- Keep private profiles, credentials, raw execution traces, private project details and personal filesystem paths out of this repository and website. Use synthetic examples and sanitized summaries.
- Preserve historical experiment qualifications, negative results, unknown measurements and the distinction between structural validation and runtime evidence. Do not claim universal support, autonomous enforcement or general productivity/cost gains from the limited trials.
- Keep public notes authoritative for their purpose and source links useful. Product code and website changes need appropriate local checks; documentation edits need diff/link and information-preservation checks. Preserve unrelated work.
- Test with isolated synthetic data. Work on this project grants no authority to alter global configuration, unrelated projects, saved automations or paid access paths.

## Checks

- `python3 -m unittest discover -s tests -v` runs the dependency-free suite; temporary files belong in the system temporary area, not the repository.
- `python3 scripts/build_website.py` rebuilds `dist/` only. Keep `website/` buildless, readable without JavaScript and free of external services.

## Context maintenance

```text
Method: context-docs
Adopted: 2026-11-08
Entry point: docs/project-context.md
```

Use the context-docs skill for documentation audits and after meaningful changes to project facts, decisions, procedures, blockers or next actions. Read the skill before maintenance. Preserve project rules, document roles, decision status and evidence limits. Update affected canonical sections and check the diff, links and information preservation. Keep the existing progress view current without duplicate tracking. Keep audit-only requests read-only and leave documents unchanged when nothing durable changed. Logging is off.
