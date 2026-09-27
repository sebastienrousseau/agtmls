<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Hardening agent configuration: reference

## Approval settings the doctor reads

The source of truth is `approval_settings` in `providers.json`, checked by
`validate-providers.py`; this table is a reading aid.

| Agent | Key | Values that mean "runs without asking" |
| --- | --- | --- |
| Claude Code | `permissions.defaultMode` | `bypassPermissions`, `dontAsk` (and `auto` is classifier-approved) |
| Codex | `approval_policy` | `never` |
| Codex | `sandbox_mode` | `danger-full-access` |
| Aider | `yes-always` | `true` |

## Rules that watch configuration

| Rule | Flags |
| --- | --- |
| `AGT-PERM-001` | Settings or instructions that switch approval prompts off |
| `AGT-POLICY-006` | An unscoped `Bash`, `Write` or `Edit` in `permissions.allow` |
| `AGT-HOOK-003` | A repository hook that runs on a lifecycle event without a trust gate |
| `AGT-HOOK-004` | Hook output that adds `additionalContext` |
| `AGT-HOOK-005` | Hook code that reads `transcript_path` |
| `AGT-SUPPLY-002` | A script that downloads a file and makes it executable |

## A reviewed Claude Code project file

```json
{
  "permissions": {
    "defaultMode": "default",
    "allow": ["Bash(npm test)", "Bash(git status)", "Bash(git diff *)"],
    "deny": ["Read(./.env)", "Read(./.env.*)", "Read(./secrets/**)"]
  }
}
```

Personal widening (`acceptEdits` for a long refactor, extra `allow` rules)
goes in `.claude/settings.local.json`, which stays out of version control.

## A reviewed Codex project file

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
```
