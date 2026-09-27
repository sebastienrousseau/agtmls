<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Authoring portable skills: reference

## Where agents read skills

Installing into `.claude/skills` and `.agents/skills` reaches every agent
below except Aider, which takes a file with `--read`.

| Agent | Project | User | Notes |
| --- | --- | --- | --- |
| Claude Code | `.claude/skills` | `~/.claude/skills` | Does not read `.agents/skills` |
| Codex | `.agents/skills` (`.codex/skills` also read) | `~/.agents/skills`, `~/.codex/skills` | Names skills `<plugin>:<skill>` when installed as a plugin |
| Antigravity | `.agents/skills` | `~/.gemini/config/skills` | Documents `name` and `description` only |
| Cursor | `.agents/skills`, `.cursor/skills` | `~/.cursor/skills` | Honours `paths` and `disable-model-invocation` |
| GitHub Copilot | `.github/skills`, `.agents/skills` | `~/.copilot/skills` | Its own tool names in `allowed-tools` |
| Gemini CLI | `.agents/skills`, `.gemini/skills` | `~/.gemini/skills` | Asks for consent on each activation |
| OpenCode | `.agents/skills`, `.opencode/skills` | global equivalents | Ignores unknown fields |
| Aider | none | none | `aider --read SKILL.md` |

## What validate-skills.py fails on

| Problem | Fix |
| --- | --- |
| A frontmatter key outside the spec's six | Move it to `metadata.json`, or drop it |
| `name` differs from the directory | Rename one |
| No trigger cue in `description` | Add "Use when…" or "Load before…" |
| `SKILL.md` over 500 lines, or body over about 5,000 tokens | Move catalogues and tables to `reference.md` |
| A `!` before a code span, a fence opened with `!`, or a `CLAUDE_*` variable | Name the command or relative path in prose instead |
| A reference linking to another reference | Link both from `SKILL.md` |

## Before and after

Before, Claude Code only: the body put `!` in front of a code span holding
`git branch --show-current`, so Claude Code ran it and pasted the branch
name in, and it named a script by a path built from the `CLAUDE_SKILL_DIR`
variable. Every other agent showed the raw text and a path that did not
exist.

After, portable:

```text
Find the current branch with `git branch --show-current`.
Run `scripts/check.sh` from this skill's directory.
```
