<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# 0004. `allowed-tools` declares full capability

- **Status:** accepted
- **Date:** 2026-08-04

## Context

The spec's `allowed-tools` field is marked experimental, and runtimes
disagree on its meaning. Some read it as a **pre-approval** — tools listed
there skip the permission prompt while the skill is active. Others read it as
a **restriction** — the skill may use nothing else.

The two readings invert the safe choice. Declaring the full capability
surface is correct under the restriction reading and permissive under the
pre-approval one. Declaring only read-only tools never widens permissions but
breaks skills under a restriction-reading runtime.

## Decision

Derive `allowed-tools` as the **full capability surface** the skill's
`safety_policy` implies: `Read Glob Grep` always, plus `Write Edit` when it
writes files, `Bash` when it executes commands, and `WebFetch WebSearch` when
network access is not `none`.

## Consequences

- The declaration is honest: it states what the skill needs, which is a
  registry's job.
- On a pre-approval runtime this skips permission prompts for the declared
  tools while the skill is active, including bare `Bash` for skills with
  `executes_commands: true`. Every skill also carries
  `requires_human_review: true`, and installation is deliberate.
- The posture is one constant: `ALLOWED_TOOLS_MODE` in
  `scripts/sync-skill-frontmatter.py`. Setting it to `"readonly"` switches the
  whole catalog to the conservative reading.
- Bare `Bash` is coarse. The spec allows scoped forms such as `Bash(git:*)`,
  but the registry cannot know a skill's commands; scoping would need a new
  per-skill metadata field. Revisit if the field stabilises.
