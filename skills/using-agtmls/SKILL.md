---
name: using-agtmls
description: "Meta-router for the AgtMLS skill catalog. Read first when unsure which AgtMLS skill applies, when several look relevant, when asking 'is there a skill for porting or noyalib work', or when onboarding to how the hub's skills and shared references fit together."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep"
metadata:
  agtmls-version: "0.0.3"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "false"
  agtmls-executes-commands: "false"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "false"
---

# Using AgtMLS — the meta-router

AgtMLS is a hub of agent skills. This page is the discovery flowchart: it
helps you pick the right skill (or decide none applies) before loading one.

## Pick a skill

1. **Porting / translating / rewriting code between languages?**
   → load **`cross-language-port`** (Rust, Python, Go, C++, Swift, TS, JS,
   Ruby, Bash). It preserves behaviour and *proves* equivalence.
   Micro-snippets (a few lines): do inline, don't load it. In-language
   migrations (Py2→3, ES5→ESNext, C++17→23) and behaviour-changing
   redesigns: not this skill.

2. **Doing ordinary engineering work — building, fixing, or finishing?**
   → load the discipline skill for the phase you are in. These apply in any
   repo, any language, and are always installed:

   | Phase | Skill | Load when |
   | --- | --- | --- |
   | Decompose | **`writing-plans`** | Work spans several files or sessions and needs steps with done-conditions |
   | Build | **`test-driven-development`** | Adding or changing behaviour — red test first |
   | Diagnose | **`systematic-debugging`** | Something is broken and the cause is unknown |
   | Finish | **`verification-before-completion`** | About to claim done, fixed, or working |
   | Review | **`receiving-code-review`** | A reviewer left comments or requested changes |
   | Pause | **`handoff`** | Work is unfinished and continuity is about to break |

   They compose in that order and hand off to each other. A project bundle's
   own rules (evidence bar, gates, test taxonomy) override them on specifics.

3. **Working inside a specific project that has its own bundle?**
   → load that project's skills. The **`noyalib/`** family (14 skills) is the
   worked example; the `references/noyalib-bundle.md` index is a router for change control,
   CI/release, debugging, architecture, YAML domain, config, coverage, docs,
   positioning, validation, and research. Start there for any noyalib task.

4. **None of the above?** Don't force a skill. Do the task directly using the
   universal engineering standards in the assembled system prompt
   (`system-prompts/_base.md` + the language profile).

## How the pieces fit

- **`skills/<name>/SKILL.md`** — a skill's spine: frontmatter (`name` +
  a trigger-rich `description` the router reads) and a ≤~200-line body.
- **`skills/<name>/reference.md`** — deep material, loaded only when the
  spine isn't enough (progressive disclosure).
- **`references/`** — *shared* standing docs many skills link to, notably
  `references/definition-of-done.md` (the cross-skill Definition of Done).
- **`system-prompts/`** — assembled into the repo-root system-prompt file at
  setup; always in context.

## The contract every skill honours

Enforced by `scripts/validate-skills.py` in CI: valid frontmatter, `name`
== directory (kebab-case), a `description` ≤1024 chars with a trigger cue,
and a top-level heading. Descriptions are also checked for mutual collision
(`scripts/check-skill-collisions.py`) and trigger-routing
(`scripts/run-trigger-evals.py`). When you add or edit a skill, run those
locally before pushing.

## When NOT to use this skill

- Once you know which skill you need — load it directly; this router is only
  for the "which one?" moment.
- For authoring a *new* skill, see the README's "Adding a skill" contract.
