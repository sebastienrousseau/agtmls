---
name: pr-review-and-release
description: Use when preparing a pull request, reviewing implementation risk, writing release notes, checking CI, packaging artifacts, or deciding whether a repository is ready to ship.
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit Bash"
metadata:
  agtmls-version: "0.0.3"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-bundle: "engineering"
  agtmls-risk-level: "medium"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "true"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# PR Review And Release

Use this skill for release readiness and review discipline.

## Workflow

1. Inspect the diff and identify behavior, documentation, generated artifacts, and tests.
2. Run the full local gate before claiming readiness.
3. Check release metadata, changelog, provenance, checksums, and docs freshness.
4. Summarize user-facing changes and operational risks.
5. Keep findings specific, file-backed, and ordered by severity.
6. Do not publish if tests, docs, provenance, or security checks are stale.

