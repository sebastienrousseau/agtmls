<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Vetting a skill before install: reference

## Where each agent looks for skills

Knowing where a skill will land tells you what else sits beside it.

| Agent | Project | User |
| --- | --- | --- |
| Claude Code | `.claude/skills` | `~/.claude/skills` |
| Codex | `.agents/skills` (`.codex/skills` also read) | `~/.agents/skills`, `~/.codex/skills` |
| Antigravity | `.agents/skills` | `~/.gemini/config/skills` |
| Cursor | `.agents/skills`, `.cursor/skills` | `~/.cursor/skills` |
| GitHub Copilot | `.github/skills`, `.agents/skills` | `~/.copilot/skills` |
| Gemini CLI | `.agents/skills`, `.gemini/skills` | `~/.gemini/skills` |

## Red flags, and what each means

| Seen | Meaning |
| --- | --- |
| A hook whose output sets `additionalContext` | Text injected into the model's context on every matching event, invisible to you (`AGT-HOOK-004`) |
| A hook that reads `transcript_path` | Reads the whole session, including anything pasted into it (`AGT-HOOK-005`) |
| `curl … \| sh`, or a download then `chmod +x` | Runs code that was not in the commit you audited (`AGT-SUPPLY-002`) |
| A checksum fetched from the same place as the file | Proves the download was not corrupted, not who made it (`AGT-SUPPLY-003`) |
| Settings that switch approval prompts off | Every other safety policy becomes advisory (`AGT-PERM-001`) |
| Content framed as the output of a tool call | Untrusted text dressed as trusted tool output (`AGT-INJ-007`) |
| `allowed-tools` wider than the declared policy | Capability escalation (`AGT-CAP-001`) |
| Repository name one character from a popular one | Name squatting; check the owner |

## Worked outcomes

**Install.** 4 skills, 0 findings, no hooks, no scripts, MIT licence,
commit pinned. Installed at that commit.

**Mirror.** 20 skills, 2 MEDIUM findings (quoted attack examples in a
security skill), one `SessionStart` hook that runs a package runner with
no version pin. The skills are useful; the unpinned runner is not. Forked at the commit,
hook removed, installed from the fork.

**Refuse.** 1 HIGH injection in a skill description, and an install script
that downloads a binary and checks it against a `.sha256` from the same
release. No way to pin the binary. Refused.
