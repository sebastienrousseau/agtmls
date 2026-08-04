<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Architecture decision records

AgtMLS ships a skill that requires ADRs for load-bearing decisions in the
projects it serves. This directory applies that rule to AgtMLS itself.

## When an ADR is required

Write one when a decision is **hard to reverse** or **non-obvious from the
code**:

- a change to the skill contract or the on-disk layout;
- a change to how the registry is distributed or installed;
- a security or permission posture (what a skill may do by default);
- adopting or dropping an external standard;
- anything a future reader would otherwise re-litigate.

Routine work — a new skill, a doc fix, a version bump — does not need one.

## Format

`NNNN-kebab-title.md`, numbered in order, using this shape:

```markdown
# NNNN. Title

- **Status:** accepted | superseded by NNNN | rejected
- **Date:** YYYY-MM-DD

## Context
<The forces. What was true that made this a decision rather than a default.>

## Decision
<What was chosen, stated actively.>

## Consequences
<What this makes easy, what it makes hard, and what it forecloses.>
```

Status is updated in place when a later ADR supersedes one; records are never
deleted.

## Index

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-flat-skill-tree.md) | Flat skill tree | accepted |
| [0002](0002-generated-portable-frontmatter.md) | Generated portable frontmatter | accepted |
| [0003](0003-bundled-registry-in-the-wheel.md) | Bundled registry in the wheel | accepted |
| [0004](0004-allowed-tools-declares-full-capability.md) | `allowed-tools` declares full capability | accepted |
