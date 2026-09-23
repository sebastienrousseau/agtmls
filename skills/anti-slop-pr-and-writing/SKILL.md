---
name: anti-slop-pr-and-writing
description: "Eliminate AI slop, clichés, sycophancy, and robotic filler from PR descriptions, commit messages, code comments, and technical documentation. Load when reviewing or authoring PRs, drafting release notes, or stripping conversational apologies and binary contrasts while preserving human voice and technical facts."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit"
metadata:
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "false"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Anti-slop PR and writing

**Trigger.** You are writing or reviewing Pull Request descriptions, git commit messages, architecture documentation, or release notes. Also load whenever text has accumulated conversational filler, robotic clichés, superficial summaries, or sycophantic phrasing.

> **Reference material** (the 20+ specific slop catalog, before-and-after tables, and diff cleaning patterns): see `reference.md`.

## The core doctrine

> **Engineers read diffs to understand intent and mechanics. AI slop obscures intent, wastes review attention, and destroys credibility.**

Good technical writing is dense, precise, and human. When editing with or through an agent, eliminate artificial mannerisms without flattening the author's voice or stripping technical context.

## Five patterns to strip on sight

### 1. Conversational sycophancy and robotic apologies
- **Strip**: "Certainly!", "I would be delighted to help with that!", "As an AI language model...", "I apologize for the oversight."
- **Replace with**: Direct statements of action, findings, or code changes.

### 2. Throat-clearing openers
- **Strip**: Temporal clichés about fast-paced eras, "Here's the thing...", "Let's dive in...", "It goes without saying that..."
- **Replace with**: The actual subject, problem, or decision in sentence one.

### 3. Binary contrasts and fake profundity
- **Strip**: "It's not X. It's Y.", "The future isn't coming; it's already here.", "This changes everything."
- **Replace with**: Concrete technical trade-offs and empirical measurements.

### 4. Fluffy PR summaries and emoji theater
- **Strip**: Rocket emojis (`🚀`), party poppers (`🎉`), and bulleted lists that merely re-state trivial git diff filenames.
- **Replace with**: The *Why* (the underlying problem or issue) and the *What* (the architectural choice made).

### 5. Defensive and trivial code comments
- **Strip**: Comments that repeat obvious syntax (e.g. `// increment i`, `// set status to true`, `// handle error`).
- **Replace with**: Comments explaining *invariants* and non-obvious *rationale*, or no comment if the code is self-documenting.

## The Human-Voice Preservation Checklist

When cleaning text:
1. **Preserve technical density**: Never replace a specific error code, function name, or metric with vague prose.
2. **Keep the author's cadence**: Do not normalize unique idioms into generic corporate-speak.
3. **Wrap strictly**: Commit bodies at 72 characters, headers at 50 characters, following Conventional Commits.
