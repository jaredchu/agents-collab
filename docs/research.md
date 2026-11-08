# Research notes

Sanitized notes from the research behind Agents Collab, mostly from
7 November 2026. They record what was looked at and how the question changed.
They are not a market survey, and third-party figures from that research are
not repeated here because they were not independently verified.

## The starting question: a fixed team

The first idea was broad. Working with one coding assistant is one person, one
project, one agent. Could a skill turn that into one person, one project and a
small **team** inside the same harness?

After a first pass, the idea narrowed to a fixed trio coordinated by the lead
session:

| Role | Intended job | Not allowed |
| --- | --- | --- |
| Architect | Short spec and acceptance criteria; split work; arbitrate | Editing code |
| Builder | Implement code and tests against the spec | Editing the spec; self-approval |
| Reviewer | Read spec and diff; run checks; report findings | Editing source |

Three rules were judged essential for review to catch anything:

1. The reviewer never inherits the builder's conversation.
2. The reviewer should, where possible, use a different model or prompt frame.
3. The fix loop has a cap.

Names and job titles were kept only as handles. Role prompts should carry scope,
tool rights, file ownership and done criteria, not personality.

## What already existed

The answer to "does this exist?" was yes, in several forms:

- **Native features.** Claude Code has subagents and an experimental agent-teams
  mode. Codex has subagents with custom agent definitions and parent-to-child
  coordination. See [Claude Code subagents](https://code.claude.com/docs/en/sub-agents.md)
  and [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).
- **Community and vendor projects.** Skill frameworks, persona collections,
  orchestrators and review plugins already cover implementer/reviewer loops,
  fresh-context reviewers, capped fix loops and per-role model selection. For
  example, [superpowers](https://github.com/obra/superpowers) includes a
  subagent-driven development workflow, and
  [codex-plugin-cc](https://github.com/openai/codex-plugin-cc) provides
  cross-model review commands from inside Claude Code.

Feature details in the original notes came partly from page summaries and could
have changed since. Check current documentation rather than relying on this list.

## What practitioners reported

The research also collected practitioner write-ups and preprints. Recurring
themes, treated here as hypotheses rather than established facts:

- Orchestration can cost substantially more tokens, often from re-reading history.
- Context gets lost or distorted at handoffs; a reviewer that inherits the
  builder's misunderstanding tends to confirm it.
- For small tasks a single agent is usually cheaper and faster than a team.
- Clear file ownership and explicit handoff points work better than free-form
  messaging.
- Some sources argue for cross-vendor review because models have different blind
  spots. This was not tested here.

## How the question changed

The research concluded that building another general team framework was not
worthwhile. That pushed attention to a narrower problem visible in personal use:

- **Configuration lived in the wrong place.** Personal model choices, reasoning
  levels and review habits had been copied into several projects' instruction
  files, where they repeated, drifted and mixed with genuine project rules.
- **Execution records leaked into project knowledge.** Dispatch receipts, model
  assignments and review transcripts were ending up near project documentation.
- **Evidence was easy to overstate.** "Requested high effort" was easy to report
  as "ran at high effort", and "fresh session" as "isolated".

So the design goal changed from *a fixed team* to *a configurable personal
profile, one writer per artifact, independent reviewers on demand, and private
records separated from durable project context*. No compulsory architect: the
lead keeps scope and integration.

## Design decisions that came out of it

- The profile is a small JSON document outside projects, read as data and
  validated structurally. It contains no credentials.
- The skill ships no personal defaults. Example profiles are templates.
- Requested, interface-accepted and runtime-observed settings are recorded
  separately; unknown stays unknown.
- Deadlines are either supervised by a real mechanism or labeled advisory.
- Profile preferences only fill choices that the actual instruction hierarchy
  leaves open. They never authorize production or publication.
- A runner would be justified only for repeated mechanics such as snapshot
  hashing, deadline enforcement or receipts. Version 1 deliberately has none.

## What this research does not show

It does not show that Agents Collab is the first, only or best approach to model
collaboration. Neighbouring projects solve overlapping problems, often more
completely. The contribution here is narrow: a configuration and records
boundary, plus an honest account of trying it.

Next: [experiments](experiments.md) · [history](history.md)
