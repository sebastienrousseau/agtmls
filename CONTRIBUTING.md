<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Contributing to AgtMLS

AgtMLS is a skill and prompt hub. Contributions should preserve the two core
properties of the repo: portable `SKILL.md` files and deterministic local
validation.

## Before opening a PR

Run the full local gate:

```sh
python3 scripts/validate-skills.py
python3 scripts/check-skill-collisions.py
python3 scripts/run-trigger-evals.py
python3 scripts/run-behavioral-evals.py
python3 scripts/generate-skill-index.py --check
python3 scripts/agtmls-doctor.py
```

## Adding or editing a skill

- Prefer the scaffold command for new skills:

```sh
python3 scripts/agtmls.py scaffold-skill candidate-skill
```

- Put the skill in its own directory containing `SKILL.md`.
- Keep `name` kebab-case and equal to the directory name.
- Keep `description` at or below 1024 characters and include clear trigger
  wording such as `Use when...` or `Load when...`.
- Keep core operating instructions in `SKILL.md`; move deep tables, long
  examples, and background material to `reference.md`.
- Add or update `evals/cases/<skill>.json` so routing drift is caught in CI.
- Add a behavioral eval when a workflow has load-bearing phrases, required
  files, or forbidden shortcuts.
- Add or inherit `metadata.json`; project bundles can carry shared metadata for
  all skills beneath them.
- Rebuild `index.json` with:

```sh
python3 scripts/generate-skill-index.py --write
```

## Review bar

Good changes are small, evidence-backed, and keep generated/local artifacts out
of application repos. Do not weaken validation to make a skill pass; fix the
skill or the eval case instead.
