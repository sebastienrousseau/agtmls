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

# Vetting a skill before install

**Trigger.** Someone wants to add a skill, plugin, marketplace or skills
repository that this registry did not produce: `/plugin install`, a
`git clone` into `.claude/skills` or `.agents/skills`, `import-skill`, or
"can I trust this repo?".

A skill is code the agent runs with your permissions. Its instructions are
read as instructions, its hooks run on events you did not trigger, and its
scripts run with your shell. Popularity is not a control: packs with
hundreds of thousands of installs have shipped under names copied from
better-known projects.

## The loop

### 1. Pin exactly what you would install

- Resolve the source to a **40-hex commit**. A branch or tag can move
  between the audit and the install, so it is not what you audited.
- Check the owner and repository name against the project you meant.
  A look-alike name with a large star count is the common squatting shape.
- Note the licence. No licence means no permission to copy it.

### 2. Audit every skill and what ships beside them

```bash
agtmls audit --foreign https://github.com/<owner>/<repo>@<commit>
agtmls audit --foreign /path/to/checkout --format json   # the same, for a local copy
```

Read three parts of the report, not only the verdict:

- **Findings**, by severity. CRITICAL or HIGH fails the audit. Read each
  one against the file it names: a prompt injection quoted under an
  "attack" heading is reported at MEDIUM, and a real one at HIGH.
- **Policy.** A skill with no `metadata.json` is audited against a
  *provisional* policy inferred from its `allowed-tools`. A skill that
  declares a policy and grants more than it declares is an escalation.
- **Coverage.** `NOT AUDITED` lists auditable files outside any skill, and
  names agent configuration (`hooks.json`, `settings.json`, `.mcp.json`,
  `plugin.json`, `CLAUDE.md`, `AGENTS.md`) one by one. `DIVERGENT` means
  copies of one skill differ between agents. The audit's silence about a
  file it did not read is not a pass.

### 3. Read what the audit cannot judge

Open, by hand, everything the coverage section names, and anything that
runs without being asked:

| Look at | Why |
| --- | --- |
| Hooks (`hooks.json`, `settings.json` `hooks`) | They run on lifecycle events, and their output can add context you never see |
| Install and setup scripts | Download-then-execute, `curl \| sh`, `chmod +x`, checksums from the same place as the download |
| MCP server entries | The command they launch, its version pin, and whether a tool runs shell commands |
| `portability:` notes | Claude Code-only syntax that other agents show as text |

Static analysis cannot see what a script fetches at run time, what a binary
does, or an instruction phrased so that no rule matches it. Say so.

### 4. Decide, and record why

- **Install**: no CRITICAL or HIGH finding, every `NOT AUDITED` config read,
  nothing runs unasked that you would not run yourself. Install the
  audited commit, not the branch.
- **Mirror**: worth having, but you want control of updates. Fork or copy it
  at the audited commit and install from there; re-audit before taking an
  upstream change.
- **Refuse**: a finding you cannot explain away, hooks or scripts you have
  not read, or a source you cannot pin.

Record the source, the commit, the audit command and the decision where the
team will find it (the PR that adds the skill, or the repository's
decision log).

### 5. After installing

An install through `agtmls` is recorded in `.agtmls/manifest.json`, and
`agtmls verify <agent> --target .` shows later drift. A plugin installed by
an agent's own plugin manager is not: keep the commit you audited, and
audit again before every update.

## Report

State the commit, the command, the counts, what you read by hand, what the
audit could not cover, and the decision. For example:

> `example-org/example-skills@3f1c…` audited with `agtmls audit --foreign`:
> 12 skills, 0 findings; hooks.json read by hand (one `SessionStart` hook
> printing a banner). Not covered: the `bin/` binary. Decision: mirror at
> this commit.

## When not to use

- Auditing this registry's own skills: `agtmls audit --all`.
- Reviewing ordinary code changes: that is code review, not supply-chain vetting.
- The source is already mirrored and pinned, and nothing changed since its audit.
