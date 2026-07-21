<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Changelog

All notable changes to AgtMLS are recorded here.

## Unreleased

## 0.0.2 - 2026-07-21

### Changed

- Bumped release metadata through the guarded patch-line release flow.


## 0.0.1 - 2026-07-20

### Added

- Registry `index.json` generation and validation.
- Full routing eval coverage for all current skills.
- Behavioral smoke evals for all current skills.
- Local `agtmls` dispatcher for registry checks, install flows, provider export,
  evolution proposals, evidence recording, benchmarks, SBOM, provenance, MCP
  resources, and agent-card generation.
- Doctor checks for registry health and consumer-repo installs.
- Skill metadata sidecars with bundle inheritance.
- Lifecycle metadata and validation.
- Command validation and plugin command-path consistency checks.
- Security and contribution policy documents.
- Provider export/install adapters for Claude, Codex, Aider, Cursor, GitHub
  Copilot, Continue, Windsurf, Zed, OpenAI, Anthropic, and Google Gemini
  style targets.
- Generated `CATALOG.md`, docs site, `agent-card.json`, `mcp-resources.json`,
  `SBOM.spdx.json`, and deterministic `provenance.json`.
- Governance, release, smoke, behavioral, routing, and benchmark checks in the
  release gate.
- 2026-ready skill bundles for agent loop design, AI supply-chain security, web
  research/source triage, PR/release workflow, and project-specific noyalib
  operations.
