<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# 0001. Flat skill tree

- **Status:** accepted
- **Date:** 2026-08-04

## Context

Skills were nested by bundle: `skills/noyalib/noyalib-debugging-playbook/`.
The nesting expressed grouping and kept the top level tidy, and `--bundle`
scoping in `setup-workspace.sh` read directly from it.

Every agent runtime scans its configured skills path **non-recursively**,
looking for `<name>/SKILL.md`. Nesting therefore made 18 of 20 skills
invisible to any runtime that did not support an array-valued `skills` field.
This was not theoretical: `.claude-plugin/plugin.json` declared
`"skills": "./skills"`, so every plugin install exposed exactly two skills.
Only Claude Code's array support is verified against a shipping
implementation; Codex, Cursor, Gemini CLI, Kimi, and Antigravity are not.

## Decision

Flatten the tree. Every skill is `skills/<name>/SKILL.md`. Bundle membership
becomes a `bundle` field in each skill's `metadata.json`, `null` for general
skills.

## Consequences

- Every manifest points at a single `./skills` path, so no runtime needs
  array support to see the whole catalog.
- `metadata.json` is per-skill; bundle-level inheritance is gone, and each
  skill's metadata is self-contained and independently editable.
- `--bundle` scoping is preserved but resolves through metadata, which adds a
  `python3` dependency to `setup-workspace.sh` — already required elsewhere
  in the toolchain.
- Skill directory names must be globally unique. They already were, and
  `name` must equal the directory name, so the contract enforces it.
- `validate-plugin-manifest.py` fails if a nested skill reappears, since one
  would be silently invisible rather than loudly broken.
