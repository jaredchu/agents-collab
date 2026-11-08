# Installation and usage guide

Agents Collab is an experimental, prompt-led skill. Read the limits in the
[README](../README.md#what-it-is-not) first. This guide covers a Codex-led setup,
the only lead the pilot targeted.

## 1. Install the package folder

Install only the skill package. In a repository checkout it is
`skills/agents-collab/`; the downloadable ZIP extracts to `agents-collab/`.
The website, tests and notes are not part of the skill.

The package is licensed under the MIT License and includes its own `LICENSE`
file; keep it with the installed folder when you copy or redistribute it. The
source repository is https://github.com/jaredchu/agents-collab
(license: https://github.com/jaredchu/agents-collab/blob/main/LICENSE).

Codex discovers user skills from a documented user skills directory. OpenAI's
[Build skills documentation](https://learn.chatgpt.com/docs/build-skills#how-chatgpt-and-codex-use-skills)
describes locations and selection; check it for your version.

Choose **one** package source, then run the shared copy block in the same shell.

### From the website ZIP

Save the ZIP from the project website,
https://agents-collab.com/downloads/agents-collab-skill.zip. From the folder
where you saved it, extract into a fresh system temporary directory:

```sh
collab_unpack="$(mktemp -d)"
python3 -m zipfile -e agents-collab-skill.zip "$collab_unpack"
collab_source="$collab_unpack/agents-collab"
```

The ZIP contains exactly the nine package files under `agents-collab/`: the
eight workflow files plus `LICENSE`, the MIT notice. Compare the ZIP's SHA-256
hash with its entry in https://agents-collab.com/downloads/SHA256SUMS.

### From a repository checkout

From the checkout root, select the package directory instead:

```sh
collab_source="skills/agents-collab"
```

### Copy to the user skills directory

Continue in the **same shell** so `collab_source` remains set. This block uses
`~/.agents/skills` and preserves an existing installation, including a symlink:

```sh
collab_skills_root="$HOME/.agents/skills"
if [ ! -f "$collab_source/SKILL.md" ]; then
  echo "Choose a package source first; nothing was copied" >&2
elif [ -e "$collab_skills_root/agents-collab" ] || [ -L "$collab_skills_root/agents-collab" ]; then
  echo "agents-collab already installed; compare before replacing" >&2
else
  mkdir -p "$collab_skills_root"
  cp -R "$collab_source" "$collab_skills_root/agents-collab"
fi
```

Check the skills catalog after installing. Codex detects skill changes
automatically; if the skill does not appear, restart the host or try a fresh
session. Seeing it listed confirms discovery, not that it will be chosen
automatically.

## 2. Create or keep a profile

The profile holds personal choices: models, transports, reasoning requests,
routing, review recipes, time targets and a private records root. It lives
outside every project:

```text
~/.config/agents-collab/profile.json
```

Two templates exist:

- **Solo** (`examples/profile.example.json`, inside the installed package): the
  lead works alone, with no delegated agents and no default review. It is
  included in both the ZIP and the checkout, so no extra download is needed, and
  it passes validation as shipped.
- **Writer plus review** (`writer-review.profile.example.json`): a delegated
  writer plus one reviewer for consequential work. It is **not** in the package.
  Its model fields are `<writer-model-id>` and `<reviewer-model-id>`. Those
  angle-bracket placeholders deliberately **fail** validation until you replace
  them with exact model identifiers that you actually have access to.

### Choose one template

Run **one** of these selection lines, in the shell where you will run the copy
block below.

Solo template, for either package source (any working directory; uses the
installed copy from step 1, so adjust the path if you installed elsewhere):

```sh
collab_profile_example="$HOME/.agents/skills/agents-collab/examples/profile.example.json"
```

Writer-plus-review template, ZIP route: save
https://agents-collab.com/downloads/writer-review.profile.example.json (its
SHA-256 entry is in the same `SHA256SUMS` file), then run this from the folder
where you saved it:

```sh
collab_profile_example="writer-review.profile.example.json"
```

Writer-plus-review template, checkout route: run this from the checkout root,
where the file is
[`docs/examples/writer-review.profile.example.json`](examples/writer-review.profile.example.json):

```sh
collab_profile_example="docs/examples/writer-review.profile.example.json"
```

### Copy the template only if no profile exists

**Preserve an existing profile.** Continue in the **same shell and working
directory** so `collab_profile_example` remains set and resolves:

```sh
mkdir -p ~/.config/agents-collab
if [ ! -f "$collab_profile_example" ]; then
  echo "Choose a profile template first; nothing was copied" >&2
elif [ -e ~/.config/agents-collab/profile.json ] || [ -L ~/.config/agents-collab/profile.json ]; then
  echo "profile exists; leaving it unchanged" >&2
else
  cp "$collab_profile_example" ~/.config/agents-collab/profile.json
  chmod 600 ~/.config/agents-collab/profile.json
fi
```

Then edit `~/.config/agents-collab/profile.json`. With the writer-plus-review
template, replace both placeholders before validating. Its full contents are:

```json
{
  "version": 1,
  "name": "writer-plus-review-example",
  "agents": {
    "lead": {"model": "current", "transport": "host", "reasoning": "inherit"},
    "writer": {"model": "<writer-model-id>", "transport": "claude-cli", "reasoning": "inherit"},
    "reviewer": {"model": "<reviewer-model-id>", "transport": "codex-native", "reasoning": "inherit"}
  },
  "routing": {"small_writer": "current-session", "substantial_writer": "writer"},
  "review": {
    "on_consequential_work": "single",
    "candidates": ["reviewer"],
    "prefer_different_model": true,
    "recipes": {},
    "max_followup_rounds": 1
  },
  "effort_check": "supported-control",
  "access": "existing-authorized-access",
  "bounds": {"enforcement": "advisory", "writer_minutes": 30, "reviewer_minutes": 10, "review_output_words": 800},
  "records_root": "~/.local/state/agents-collab"
}
```

Notes on the fields that cause the most confusion:

- `"model": "current"` with `"transport": "host"` means the lead session you are
  already in. The skill cannot switch the lead's model or reasoning level.
- `reasoning` is `inherit` or a lowercase level that the interface documents for
  that model. `inherit` does not mean "high".
- To add an explicitly requested pair of reviewers, add a second reviewer agent
  and a recipe such as `"recipes": {"pair": ["reviewer", "reviewer2"]}`. A recipe
  is used when you name it or an applicable policy calls for it.
- `bounds.enforcement: "advisory"` labels time targets as advisory. `"required"`
  means each assignment needs a real supervisor, such as a subprocess timeout;
  a prompt is not enforcement.
- `records_root` must be outside your projects. Before creating records, the lead
  must resolve the final task directory and confirm it does not overlap the
  project. The validator cannot check that.

The full contract is in
[`references/configuration.md`](../skills/agents-collab/references/configuration.md).

## 3. Validate the structure

The validator ships in the installed package, so the same command works for the
ZIP and checkout routes from any working directory:

```sh
python3 ~/.agents/skills/agents-collab/scripts/validate_profile.py ~/.config/agents-collab/profile.json
```

An unedited solo template exits 0. An unedited writer-plus-review template exits
1 and names the two placeholder model fields; it exits 0 once you replace them
with exact model identifiers and the rest of the structure is valid.

| Exit | Meaning |
| --- | --- |
| 0 | The file matches the v1 structure |
| 1 | Invalid content: malformed JSON, invalid UTF-8, too large, or structural issues listed by field |
| 2 | Unreadable or nonregular input, or a usage error |

A pass is **structural only**. It does not check that a model identifier exists,
that you can access it, that a reasoning level is supported, permissions, or
where records resolve. Diagnostics name fields without echoing their values.

## 4. Invoke it

Explicit invocation is the reliable path:

```text
Use $agents-collab to implement the export change, with independent review before I merge.
```

```text
Use $agents-collab with the "pair" recipe to review docs/proposal.md. Do not edit it.
```

```text
Use $agents-collab with profile ~/.config/agents-collab/team-review.json for this refactor.
```

Automatic selection depends on the skill's description and on how your host
chooses skills for a task. It is not an always-on hook, and the pilots did not
establish reliable unprompted routing. Small solo work should normally stay with
the lead and create no records.

## 5. Native settings stay separate

Your host's own configuration sets the lead model, reasoning level and subagent
defaults. The profile tells the skill what to **request and check** for delegated
work; it does not edit host settings or change the running lead. Using the skill
should never require changing global configuration or bypassing permissions.

## 6. What to expect in a run

1. The lead reads project instructions and the profile, then validates it.
2. It classifies the task. Small work stays solo unless review is required.
3. For delegated work, it confirms model, access and controls before launch, and
   records requested settings separately from what the interface accepted.
4. Reviewers get a neutral packet and the same frozen artifact.
5. The writer handles findings. Rounds stop at the configured cap; unresolved
   material issues are reported, not waived.
6. Private records go under `records_root`; the project receives durable outcomes.

If a required model, effort or access path is unavailable, the lead reports it
instead of silently substituting another model or paid access.

## Uninstall

Remove `~/.agents/skills/agents-collab` (or wherever you installed it). Your
profile and private records are separate; delete them only if you no longer want
them.
