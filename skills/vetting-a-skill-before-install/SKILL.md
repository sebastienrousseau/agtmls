---
name: vetting-a-skill-before-install
description: "Use before installing, importing or enabling a third-party skill, plugin, marketplace or skills repository in Claude Code, Codex, Antigravity, Cursor or any agent. Pins the source to a commit, audits every skill and the agent configuration it ships, reads what the audit could not cover, and ends in install, mirror or refuse. Not for auditing this registry's own skills."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Bash WebFetch WebSearch"
metadata:
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "draft"
  agtmls-risk-level: "medium"
  agtmls-network-access: "optional"
  agtmls-writes-files: "false"
  agtmls-executes-commands: "true"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---
---

# Vetting a skill before install

**Trigger.** Someone wants to add a skill, plugin, marketplace or skills
repository this registry did not produce: `/plugin install`, a clone into
`.claude/skills` or `.agents/skills`, `import-skill`, or "can I trust this
repo?". A skill runs with your permissions: its text is read as
instructions, its hooks run on events you did not trigger, its scripts run
in your shell. Install counts are not a control.

Keep tool calls few: every call re-sends the conversation so far. Start
with the audit, which answers the first questions for you.

## Steps

1. **Audit.** `agtmls audit --foreign <path, or url@commit>`, with
   `--format json` to parse it. A CRITICAL or HIGH finding fails. Its
   coverage section states the source, and lists every `NOT AUDITED` file:
   agent configuration it did not judge (`hooks.json`, `settings.json`,
   `.mcp.json`, `plugin.json`, `CLAUDE.md`, `AGENTS.md`) and scripts outside
   any skill. Silence about a file is not a pass.
2. **Pin.** Take the **40-hex commit** from the audit's `source:` line; a
   branch or tag can move between the audit and the install. If it says the
   source is not a git checkout, it cannot be pinned: count that against it
   rather than searching further. Check the owner and name against the
   project you meant; note the licence.
3. **Read what runs unasked, in one call.** Read every file the audit
   lists as `NOT AUDITED` at once: one `cat` of them all, or all the reads in
   a single turn. Look for hooks
   that fetch and run code or send data out (`curl | sh`, a transcript
   upload), MCP servers not pinned to a version or able to run any command,
   and checksums fetched from the same place as the download. Say what
   reading cannot show, such as what a download does when it runs.
4. **Decide.**
   - **Install**: no CRITICAL or HIGH finding, every `NOT AUDITED` file
     read, nothing runs unasked that you would not run yourself. Install
     the audited commit, not the branch.
   - **Mirror**: worth having, but you want control of updates. Copy it at
     the audited commit; re-audit before taking an upstream change.
   - **Refuse**: a finding you cannot explain away, hooks or scripts you
     have not read, or a source you cannot pin.

An install through `agtmls` is recorded, and `agtmls verify` shows later
drift. A plugin manager's install is not: audit again before each update.

## Report

Open with the source: the commit you would install, or that it cannot be
pinned and so cannot be installed as audited. Then the audit command and its
counts, what you read by hand, what could not be checked, and the decision
with its reason. `reference.md` has worked outcomes and the red flags.

## When not to use

- Auditing this registry's own skills: `agtmls audit --all`.
- Reviewing ordinary code changes: that is code review.
- The source is already mirrored and pinned, and unchanged since its audit.
