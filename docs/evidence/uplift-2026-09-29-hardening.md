<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# hardening-agent-config, second uplift run

hardening-agent-config showed no meaningful gain on a harder case either,
and used 1.23x to 1.76x the tokens, so it is retired.

The first run ([`uplift-2026-09-29.md`](uplift-2026-09-29.md)) used a
fixture whose flaws any capable agent spots, and both arms found almost
all of them. This case (`platform-api`) hides only what the skill
teaches: a committed `settings.local.json` that bypasses permissions,
`enableAllProjectMcpServers` starting a wildcard shell MCP server, a hook
running `npx -y` on an unpinned package, Aider's `yes-always`, and no deny
rule for `.env`.

- Commit `ce4487f`, 5 trials per arm, 20 runs, 0 errors.
- Claude Code: `claude-opus-5-5`. Codex: `gpt-6-astra`, default reasoning.
- Claude Code cost USD 1.53 for its runs.
- Raw results: [`uplift-2026-09-29-hardening.json`](uplift-2026-09-29-hardening.json).

Tables below are `run-uplift-evals.py --render` output.

| Skill | Agent | Without | With | Delta | Tokens | Skill read | Errors | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| hardening-agent-config | claude | 100% | 97% | -3 pts | 1.76x | 100% | 0 | no gain |
| hardening-agent-config | codex | 93% | 97% | +3 pts | 1.23x | 100% | 0 | helps |

Meets the hardened bar: none.

| hardening-agent-config | claude without | claude with | codex without | codex with |
| --- | ---: | ---: | ---: | ---: |
| local-bypass | 100% | 100% | 100% | 100% |
| enable-all-mcp | 100% | 100% | 100% | 100% |
| shell-mcp | 100% | 100% | 100% | 100% |
| hook-package-runner | 100% | 80% | 60% | 80% |
| aider-yes-always | 100% | 100% | 100% | 100% |
| deny-secrets | 100% | 100% | 100% | 100% |

## What it shows

Without the skill, Claude Code found all six flaws in every run and Codex
found 93% of them. The skill lowered Claude Code's score by 3 points and
raised Codex's by 3, one flaw in one of five runs; both are within the
noise of five trials. Codex's `helps` verdict rests on that one flaw.

Across two cases and 40 measured runs, the agents already know what this
skill teaches. It adds cost without a gain worth the name, and the plan
retires a skill that shows no gain rather than keeping it.

Patterns were frozen before this run (`ce4487f`); the misses on
`hook-package-runner` were not read by hand.

## Correction: one fixture file is not in the commit

The run read the fixture from the working tree. Its
`.claude/settings.local.json` was never committed: a global git ignore
rule for that name dropped it, so `ce4487f` has the fixture without the
file behind the `local-bypass` flaw. To reproduce the run from that
commit, add it back as `evals/uplift/fixtures/platform-api/.claude/settings.local.json`:

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
```

`run-uplift-evals.py --check` now fails on any fixture file git ignores.
