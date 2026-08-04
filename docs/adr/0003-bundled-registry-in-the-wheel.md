<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# 0003. Bundled registry in the wheel

- **Status:** accepted
- **Date:** 2026-08-04

## Context

Installing AgtMLS required cloning the repository. Every comparable project
offers a one-line install (`npx`, `pipx`, a plugin marketplace), and the clone
requirement is a real adoption barrier.

The 68 registry scripts each resolve their root as
`Path(__file__).resolve().parent.parent` and operate on sibling directories.
Making them work from a wheel by rewriting that resolution would have touched
every script.

## Decision

Ship the registry verbatim inside the wheel at `agtmls/_registry/`, using
hatchling `force-include`. Because that mirrors the repo layout one directory
down, `_registry/scripts/agtmls.py` resolves `_registry/` as the registry root
with **no script change at all**. `src/agtmls/cli.py` is a thin shim that
locates the root and forwards argv.

Root resolution order: `AGTMLS_HOME` → repo checkout → bundled registry.

## Consequences

- `uvx agtmls` and `pipx install agtmls` work with zero dependencies, because
  every script is stdlib-only.
- The layout is load-bearing and non-obvious. `scripts/validate-packaging.py`
  asserts it, including that `scripts` maps to `<prefix>/scripts`.
- Repository-maintenance commands need git history and CI config, so they
  refuse to run from a package and point at `AGTMLS_HOME`.
- Wheel size carries the whole catalog. Acceptable while the registry is text;
  revisit if binary assets are ever added.
