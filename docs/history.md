# How Agents Collab emerged

A short history in broad phases. Dates are given where records support them.

## 1. Per-project model collaboration (13–15 October 2026)

The earlier Model Collaboration skill used per-project setup and local agreements
for task choices and review boundaries. A recorded setup check dated 13 October 2026 verified that both
the Codex and Claude clients discovered and loaded it. That check covered loading
only, not real review work or effectiveness. The setup was retired on
15 October 2026. Afterwards, standalone model policies were copied directly into
project instruction files instead.

That worked locally, but the same personal defaults now appeared in many places.
Small edits in one project did not reach the others, so the copies drifted. It
became hard to tell which lines were genuine project requirements and which were
one person's habits.

## 2. Researching fixed teams (7 November 2026)

The next idea was a fixed architect/builder/reviewer team as a skill. Research
showed that teams of that kind, fresh-context reviewers and capped review loops
already existed in native features and open projects. The useful remaining
problem was narrower: keep personal configuration and execution records out of
project knowledge. See [research](research.md).

## 3. A configurable profile and private records (8 November 2026)

The design that followed:

- a personal profile outside projects for models, routing, review recipes and
  limits;
- one writer per artifact and independent reviewers with neutral packets;
- a private records directory for receipts and findings;
- only durable outcomes handed back to the project;
- honest labels: requested is not attested, fresh is not isolated, advisory is
  not enforced.

The package was implemented and structurally validated the same day.

## 4. Two small trials (8 November 2026)

A documentation pilot (skill added alongside existing rules) and a code-task
pilot (skill replacing cleaned rules) each compared five task pairs. Neither met
its coordination-benefit threshold. Results were mixed and in places negative.
See [experiments](experiments.md).

## 5. Installation and cleanup (8 November 2026, after the trials)

The skill was then installed for personal use, and duplicated model clauses were
removed from personal global instructions. Fresh-session discovery was checked.

The cleanup across existing projects was the painful part, and the most
instructive:

- Matching personal policy text turned up in instruction files across several
  repositories. Each needed individual review, not bulk deletion.
- Publication, privacy, approval and genuine product constraints had to survive
  the migration. Earlier personal model choices were superseded by the current
  owner decision; removing them did not authorize changing product behavior.
- Historical decisions and evidence that mention earlier model assignments had to
  survive. Cleaning up must not rewrite the record.
- Some personal defaults had spread beyond prose into **runtime checks**, so
  removing them meant changing behavior, not just editing documentation.
- Project adoption metadata is not a personal setting. A project's record of
  which documentation method it adopted, when, and where its entry point is must
  survive when personal settings are removed. Otherwise later sessions lose
  track of how the project is maintained.

That is the clearest argument for the boundary this project draws: if personal
preferences never enter project files, there is nothing to migrate later.

## Where it stands

Experimental and pre-release. Public owner and license are not decided. The
evidence supports the configuration boundary as a workable idea; it does not
show general productivity gains or a novel orchestration method.
