---
name: authoring-portable-skills
description: "Use when writing or editing a SKILL.md that more than one agent will read (Claude Code, Codex, Antigravity, Cursor, Copilot, Gemini CLI, OpenCode). Keeps the shared file to what every agent honours, sizes the body, checks it with validate-skills.py and the agents themselves, and requires evidence before calling it hardened. Not for choosing what a skill should teach."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit Bash"
metadata:
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "draft"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "true"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Authoring portable skills

**Trigger.** You are creating a skill, editing a `SKILL.md`, adding frontmatter,
or porting a skill written for one agent so others can use it.

The same `SKILL.md` is read by many agents, each honouring a different set
of extras. A skill that works in the agent it was written in and silently
degrades in the others is the common failure, and nobody sees it, because
each author tests in one agent.

## The shared file

**Frontmatter.** Only what every agent reads:

| Field | Rule |
| --- | --- |
| `name` | kebab-case, at most 64 characters, equal to the directory name |
| `description` | at most 1,024 characters; what it does **and when to load it**, trigger words first, since some agents shorten long descriptions in their listing |
| `license`, `compatibility` | optional, plain strings |
| `metadata` | optional, flat string key/value pairs |

Agent-specific fields (Claude Code `allowed-tools`, `context`, `paths`;
Codex `agents/openai.yaml`) belong to that agent's install, not to the
shared text. In this registry `allowed-tools` is generated from
`metadata.json` by `sync-skill-frontmatter.py`; never write it by hand.

**Body.**

- Under about 5,000 tokens and 500 lines. The body loads whole on
  activation; detail goes in a reference file the body names.
- References one level deep: `SKILL.md` may send the agent to
  `reference.md`, but `reference.md` must not send it on to a third file.
  Agents follow chains unevenly.
- Nothing only Claude Code understands: no `!` placed before a code span
  to run a command, no code fence opened with a `!`, and no path built from
  the `CLAUDE_SKILL_DIR` variable. Other agents show them as literal text or
  a path that does not exist. Refer to bundled scripts by relative path and
  say what to run.

## Write it from a real procedure

A skill earns its place when it carries steps the agent would not otherwise
take, with outputs someone can check. Skills a model writes for itself, with
no procedure behind them, measure worse than no skill. Generic advice
("write clean code") changes nothing.

- One job per skill. If the description needs "and" twice, split it.
- Every mandatory step must pay for itself on every use. Heavy verification
  rituals and long pipelines are the most common ways a skill makes an agent
  worse; make expensive steps conditional on the risk.
- Say when **not** to use it, naming the skill that does.

## Check it

```bash
python3 scripts/validate-skills.py            # spec, trigger cue and portability
agtmls audit skills/<name>                    # security rules on every file
agtmls audit --foreign /path/to/repo          # portability notes for a repo that is not this registry
```

Then add its evals, which this registry requires: routing cases
(`evals/cases/<name>.json`, prompts that should and should not load it) and
a behavioural case (`evals/behavioral/cases/<name>.json`, text the skill
must and must not contain).

Then check the agents actually load it:

```bash
agtmls install <language> claude --target /tmp/try && agtmls verify claude --target /tmp/try --live
agtmls install <language> codex --target /tmp/try && agtmls verify codex --target /tmp/try --live
```

`--live` asks the agent which skills it loads (Claude Code through one
headless session, Codex through its rendered prompt, no model call) and
fails naming any installed skill it does not list.

## Draft until measured

A new skill ships as `draft`. It becomes `hardened` when a run of the same
tasks with and without it, on at least two agents, shows it helps
(`scripts/run-uplift-evals.py`), and a skill that shows no gain is retired
rather than kept. Helping includes cost: on each agent the skill may use at
most 1.5 times the tokens of the task without it, unless it gains 20 points
or more. Passing the validators proves the file is well-formed, not that it
helps.

## When not to use

- Deciding what a skill should teach, or whether it should exist: that is the
  domain expert's call. This skill is the form, not the content.
- Installing someone else's skill: `vetting-a-skill-before-install`.
