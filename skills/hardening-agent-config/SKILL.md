---
name: hardening-agent-config
description: "Use when setting up or reviewing a coding agent's configuration in a repository or a home directory: approval modes, permission rules, hooks, MCP servers and where each setting lives, for Claude Code, Codex, Aider and Antigravity. Also when agtmls doctor warns that an agent runs tools without asking. Not for vetting a third-party skill (vetting-a-skill-before-install)."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit Bash"
metadata:
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "draft"
  agtmls-risk-level: "medium"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "true"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Hardening agent configuration

**Trigger.** You are writing or reviewing `.claude/settings.json`,
`.codex/config.toml`, `.aider.conf.yml`, a `hooks` block or an `.mcp.json`;
a repository is being set up for agents; or `agtmls doctor` has warned
about approval posture.

Every skill's safety policy (no network, no file writes, no commands) is
only as real as the agent's own settings. An agent set to run tools without
asking turns each of those policies into a suggestion.

## 1. Find out what is in force

```bash
agtmls doctor --target . --agent claude     # or codex, aider, antigravity
```

The doctor reads each agent's settings in every scope and names the file
and value when the agent runs tools without asking. Settings merge across
scopes, so check all of them:

| Agent | Files, narrowest scope first | Unattended when |
| --- | --- | --- |
| Claude Code | `.claude/settings.local.json`, `.claude/settings.json`, `~/.claude/settings.json` | `permissions.defaultMode` is `bypassPermissions` or `dontAsk`. `auto` hands each decision to a safety classifier: not unattended, but not you either |
| Codex | `.codex/config.toml`, `~/.codex/config.toml` | `approval_policy = "never"`, or `sandbox_mode = "danger-full-access"` |
| Aider | `.aider.conf.yml`, `~/.aider.conf.yml` | `yes-always: true` |
| Antigravity | none that AgtMLS knows | Say so; do not assume it asks |

A committed project file (`.claude/settings.json`, `.codex/config.toml`)
applies to everyone who opens the repository. Put personal choices in the
local or user file.

## 2. Keep approval on for anything that leaves the directory

- Leave the default mode asking. Widen it for a session, not in a
  committed file.
- Grant narrowly. Name the command, not the tool: `Bash(npm test)`, not
  `Bash`; an unscoped `Bash`, `Write` or `Edit` in `permissions.allow` is
  what `AGT-POLICY-006` flags.
- Deny reads of secrets outright (`.env`, key files, cloud credentials),
  rather than trusting each request to be refused.
- For Codex, pair an approval policy that asks with a `workspace-write` or
  `read-only` sandbox; `danger-full-access` removes the sandbox entirely.

## 3. Treat hooks as code that runs unasked

A hook runs on an event, not on a request, with your permissions.

- Every hook in a committed file needs a reviewer who has read it.
- No hook that approves tool calls on the agent's behalf, fetches from the
  network, or runs `curl … | sh`.
- A hook's output that adds context to the model (`additionalContext`) is
  text the model reads and you never see; a hook that reads the session
  transcript sees everything pasted into it. Both need a reason.
- Pin what a hook runs: a script in the repository, not a package runner
  that fetches whatever release is newest when the hook fires.

## 4. Pin and scope MCP servers

- Pin each server's version; `@latest` changes what runs without a commit.
- Read each tool's description: a description is instructions the model
  follows, and poisoned descriptions are an attack surface.
- Prefer servers with narrow tools to one that runs arbitrary commands.
- Do not let a project's `.mcp.json` start servers without asking you.

## 5. Check it again

```bash
agtmls doctor --target . --agent <agent>
agtmls audit --foreign .     # hooks, permission and MCP rules over the repository's own config
```

`audit --foreign` names agent configuration it did not audit; read those
files by hand.

## Report

Name each file and scope you checked, what was unattended or unscoped, what
you changed, and what you could not check (for example, Antigravity's
settings).

## When not to use

- Deciding whether to install someone else's skill or plugin:
  `vetting-a-skill-before-install`.
- Securing the application the agent is working on: that is ordinary
  security review.
