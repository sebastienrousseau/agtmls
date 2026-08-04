---
name: agent-loop-design
description: Use when turning repeated agent work into a loop with trigger conditions, evidence, stopping criteria, uninstall state, validation checks, and reviewable artifacts.
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit"
metadata:
  agtmls-version: "0.0.4"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-bundle: "loops"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "false"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Agent Loop Design

Use this skill to design repeatable agent workflows that can run manually, on a schedule, or from a hook.

## Workflow

1. Define the trigger: manual, file change, schedule, failed check, or user phrase.
2. Define scope, permissions, and stopping criteria before execution.
3. Record evidence: inputs, commands, files touched, outputs, and verification.
4. Make installation reversible with a manifest of every path created.
5. Add a dry-run path and at least one smoke test.
6. Promote the loop only after it passes validation and a human review gate.

