---
name: ai-supply-chain-security
description: Use when auditing AI-agent supply chain risk, prompt or skill provenance, dependency trust, SBOM/SLSA evidence, MCP tool-poisoning, package provenance, or agent runtime guardrails before release.
license: MIT
---

# AI Supply Chain Security

Use this skill to audit agentic supply-chain risk before shipping an AI-enabled repository or skill pack.

## Workflow

1. Identify generated artifacts, skills, prompts, tools, MCP servers, and provider adapters.
2. Check provenance: source commit, generator script, checksum, license, and owner.
3. Check package risk: dependency confusion, typosquatting, unsigned artifacts, unpinned install commands, and shell-pipe installers.
4. Check agent risk: prompt injection, MCP tool poisoning, unreviewed network access, file-write authority, and secret handling.
5. Require release evidence: `SBOM.spdx.json`, `provenance.json`, `SHA256SUMS`, and green `agtmls.py check`.
6. Report blocking issues before publishing or installing globally.

## Evidence

Record reviewed files, commands run, and residual risks in the evidence log when available.

