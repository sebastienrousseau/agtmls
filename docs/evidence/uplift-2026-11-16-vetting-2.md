<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# vetting-a-skill-before-install after the Markdown lint

vetting-a-skill-before-install still helps on both agents and stays
`hardened`. Claude Code goes from 88% to 100% (+12 points) at 1.05x the
tokens of the task without it, and Codex from 92% to 96% (+4 points) at
1.06x.

Why it was re-run: v0.0.32 rewrapped one line of its `reference.md` to fit
80 columns, which moved the skill's digest
(`sha256:e52990f5…a3ae`) and dropped its efficacy attestation. Nothing else
in the skill changed.

Same case and settings as the run earlier the same day
([uplift-2026-11-16-vetting.md](uplift-2026-11-16-vetting.md)): 5 trials per
arm per agent, 20 runs, Claude Code's default model and Codex on
`gpt-6-astra`. Claude's runs cost USD 1.06; Codex reports no cost. The
results record commit `64c63d0`.

| Skill | Agent | Without | With | Delta | Tokens | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| vetting-a-skill-before-install | claude | 88% | 100% | +12 pts | 1.05x | helps |
| vetting-a-skill-before-install | codex | 92% | 96% | +4 pts | 1.06x | helps |

Raw results: [uplift-2026-11-16-vetting-2.json](uplift-2026-11-16-vetting-2.json).
