---
name: using-agtmls
description: >-
  Meta-router for the AgtMLS skill catalog — read this first when you are
  unsure which AgtMLS skill (if any) to load for a task, when several skills
  look like they might apply, or when onboarding to how this hub's skills and
  shared references fit together. Points at the cross-language-port skill for
  porting/translating code between languages, at project bundles (e.g. the
  noyalib/ family) for project-specific work, and at references/ for the
  shared Definition of Done. Use when the question is "which skill do I use
  for X" or "how do AgtMLS skills work".
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

2. **Working inside a specific project that has its own bundle?**
   → load that project's skills. The **`noyalib/`** family (14 skills) is the
   worked example; its `noyalib/README.md` is a router for change control,
   CI/release, debugging, architecture, YAML domain, config, coverage, docs,
   positioning, validation, and research. Start there for any noyalib task.

3. **None of the above?** Don't force a skill. Do the task directly using the
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
