---
name: release-notes
description: Writes release notes.
license: MIT
allowed-tools: Bash Read Write
context: fork
---

# Release notes

Recent history:

!`git log --oneline -20`

Run `${CLAUDE_SKILL_DIR}/scripts/collect.sh` to gather the merged pull
requests, then fill in the template described in reference.md.
