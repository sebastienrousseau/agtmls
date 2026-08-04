---
name: web-research-and-source-triage
description: Use when gathering current web evidence, comparing sources, triaging credibility, reading GitHub repositories, checking docs, or deciding whether a claim needs live verification.
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep WebFetch WebSearch"
metadata:
  agtmls-version: "0.0.4"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-bundle: "web-reach"
  agtmls-risk-level: "low"
  agtmls-network-access: "optional"
  agtmls-writes-files: "false"
  agtmls-executes-commands: "false"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Web Research And Source Triage

Use this skill for current-source research and source credibility checks.

## Workflow

1. Classify the claim as stable, current, high-stakes, or vendor-specific.
2. Prefer primary sources: official docs, repositories, standards bodies, papers, patents, and release notes.
3. Cross-check volatile claims against at least two independent sources when possible.
4. Capture dates, versions, and source URLs in the answer or evidence record.
5. Flag uncertainty explicitly when sources disagree or only secondary sources are available.
6. Avoid copying long passages; summarize and cite.

