<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Architecture

AgtMLS is designed as a universal, polyglot skills registry and distribution hub for autonomous coding agents (Claude Code, OpenAI Codex, Google Antigravity, Aider, and compatible runtimes).

## Core Principles

1. **Flat Skill Hierarchy**: Every skill lives as a leaf directory directly under `skills/<name>/` containing `SKILL.md` and `metadata.json`. Runtimes scan skill directories non-recursively, making deep nesting undiscoverable.
2. **Zero Runtime Dependencies**: Every management and validation script in `scripts/` is written using Python's standard library only. Consumers downloading via `uvx agtmls` or installing in CI environments encounter zero dependency resolution overhead.
3. **Derived Manifests as Source of Truth**: Hand-writing manifests across 8+ agent platforms leads to inevitable drift. Instead, `scripts/generate-plugin-manifests.py` and sibling generators derive `plugin.json`, `index.json`, `CATALOG.md`, `agent-card.json`, `mcp-resources.json`, `SBOM.spdx.json`, and `provenance.json` from the canonical skill metadata.
4. **Guarded Patch-Line Releases**: The registry enforces an incremental `0.0.x` patch-line lifecycle where releases increment by exactly `0.0.1` and `v0.1.0` requires completing `v0.0.999`.

## Pipeline Flow

```
skills/<name>/ (SKILL.md + metadata.json)
        │
        ├──> sync-skill-frontmatter.py    (synchronizes YAML frontmatter)
        ├──> generate-skill-index.py      (produces index.json)
        ├──> generate-catalog.py          (produces CATALOG.md)
        ├──> generate-plugin-manifests.py (generates Claude, Antigravity, Codex, Cursor, Kimi, OpenCode manifests)
        ├──> generate-mcp-resources.py    (MCP resource publication)
        ├──> generate-sbom.py             (SPDX 2.3 SBOM)
        └──> generate-provenance.py       (SLSA-aligned provenance subject)
```

## Provider Adaptation

AgtMLS supports three consumption modes:
- **Native Symlinks** (`setup-workspace.sh`): Symlinks skills into `.claude/`, `.codex/`, `.aider/`, or `.agents/`.
- **Plugin Manifests**: Supported via `plugin.json` (Antigravity), `.claude-plugin/plugin.json`, `.cursor-plugin/`, `.kimi-plugin/`, and `gemini-extension.json`.
- **Standalone Export Bundles**: Packaged provider-adapted Markdown export archives produced by `scripts/export-registry.py`.
