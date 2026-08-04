<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# 0002. Generated portable frontmatter

- **Status:** accepted
- **Date:** 2026-08-04

## Context

Per-skill operational metadata — `safety_policy`, `maturity`, `owner`,
`required_tools` — lived only in `metadata.json`, an AgtMLS-private sidecar.
No other runtime reads it. A consumer installing through the plugin
marketplace or a Markdown export therefore received **no risk signal at all**:
not that a skill executes commands, writes files, or reaches the network.

The Agent Skills spec reserves three optional frontmatter fields for exactly
this purpose: `compatibility`, `metadata`, and `allowed-tools`.

## Decision

Keep `metadata.json` as the source of truth and **generate** the spec fields
from it with `scripts/sync-skill-frontmatter.py`, run as `--check` in the
gate. `required_tools` becomes `compatibility`; `safety_policy` becomes
namespaced `agtmls-*` keys under `metadata` plus a derived `allowed-tools`.

## Consequences

- The risk signal travels with the skill into every runtime and every export.
- Frontmatter is generated, so hand-editing those four fields is a check
  failure — the sidecar and the published metadata cannot drift.
- Frontmatter grows by ~10 lines per skill. Only `name` and `description` are
  hoisted at router startup, so the routing budget is unaffected.
- `metadata` values must be strings; booleans are emitted as `"true"`/`"false"`
  per the spec's string-map requirement.
