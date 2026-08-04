<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Contributing to AgtMLS

AgtMLS is a registry, so the bar is unusual: a bad skill does not crash, it
quietly makes every agent that loads it worse. Most of the process below
exists to catch that.

## The one command

```bash
python3 scripts/agtmls.py check
```

57 checks. It is the same gate CI runs — `validate-check-manifest.py` fails
if `checks.json`, `scripts/run-all-checks.py`, and
`.github/workflows/validate.yml` ever disagree, so a green local run means a
green CI run.

Two checks need optional extras and skip cleanly without them:

| Check | Extra | Install |
| --- | --- | --- |
| `validate-spec-conformance.py` | reference validator | `pip install skills-ref` |
| `smoke-live-providers.py` | provider credentials | export the relevant `*_API_KEY` |

CI installs `skills-ref`, so spec conformance is always enforced on a pull
request even if you skipped it locally.

## Adding a skill

```bash
python3 scripts/agtmls.py scaffold-skill my-skill            # general
python3 scripts/agtmls.py scaffold-skill my-skill --bundle x # project-scoped
```

That writes `skills/my-skill/` with `SKILL.md`, `reference.md`,
`metadata.json`, and both eval cases. Then:

1. **Write the description first.** It is the whole routing surface — the
   model decides whether to load your skill from it alone. Say what the skill
   does *and when to load it*, using words a user would actually type.
2. **Write the body.** Keep `SKILL.md` under 500 lines and put depth in
   `reference.md`. The body is loaded in full on activation; the reference is
   loaded only when the skill asks for it.
3. **Fill in `metadata.json`**, especially `safety_policy`. It is generated
   into portable frontmatter, so it is what a Cursor or Gemini user sees.
   Never hand-edit `license`, `compatibility`, `allowed-tools`, or `metadata`
   in `SKILL.md` — run `sync-skill-frontmatter.py --write`.
4. **Write the eval cases.** Routing positives are prompts that *must* reach
   your skill; negatives are prompts that must not. Behavioral cases assert
   that load-bearing content stays present.
5. **Regenerate and check:**

   ```bash
   python3 scripts/sync-skill-frontmatter.py --write
   python3 scripts/generate-skill-index.py --write
   python3 scripts/agtmls.py check
   ```

### What a good skill looks like

- **One rule, stated once.** The best skills have a single load-bearing
  sentence that the rest of the body serves.
- **Triggers, not topics.** "Load when X happens" beats "about X".
- **A `When not to use` section.** Skills that never decline get loaded
  wrongly and dilute the router.
- **Concrete over abstract.** Commands, tables, worked examples.
- **Defers to project bundles.** A general skill states the floor; a project
  skill overrides it on specifics.

## Skill lifecycle

Skills move through four stages (`lifecycle.json`), each with exit criteria:

| Stage | Requires | Exit criteria |
| --- | --- | --- |
| proposal | `.agtmls/proposals/<skill>.md` | human-reviewed trigger and safety boundaries |
| draft | `SKILL.md`, routing eval | validator, routing eval, collision check pass |
| hardened | behavioral eval | behavioral eval passes, index regenerated |
| published | `index.json` | doctor clean, CI green, docs updated |

External skills enter as drafts via `agtmls.py import-skill`, never directly
as hardened.

## Architecture decisions

Load-bearing or hard-to-reverse changes need an ADR in `docs/adr/` — the skill
contract, the on-disk layout, distribution, or the permission posture. See
`docs/adr/README.md` for when one is required and the template. Routine work
does not need one.

## Changing the tooling

`scripts/` is covered by `scripts/run-unit-tests.py`. If you change a
validator's logic, add a test that fails without your change: the gate checks
repository *data*, so a checker that always returns 0 is invisible to it.
Tests run on Python 3.10–3.13 across Linux and macOS in CI.

## Style

- **Python: stdlib only.** The zero-dependency guarantee is what makes
  `uvx agtmls` a single fast download; `validate-packaging.py` enforces it.
- **Shell:** `set -euo pipefail`, 2-space indent.
- **Licence on every file.** Markdown gets an SPDX header — except `SKILL.md`
  and `commands/*.md`, which must begin with `---` at byte 0 and declare
  `license:` in frontmatter instead. `validate-licence-headers.py` enforces
  whichever form applies.
- **Conventional Commits.**

## Never edit by hand

These are generated and drift-checked:

`index.json` · `CATALOG.md` · `site/index.html` · `agent-card.json` ·
`mcp-resources.json` · `SBOM.spdx.json` · `provenance.json` ·
`plugin.json` · `gemini-extension.json` · `GEMINI.md` ·
`.codex-plugin/` · `.cursor-plugin/` · `.kimi-plugin/` · `.agents/` ·
`.opencode/INSTALL.md` · the generated frontmatter fields in every `SKILL.md`

## Reporting security issues

See `SECURITY.md`. Do not open a public issue for a vulnerability.
