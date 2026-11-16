<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# vetting-a-skill-before-install after the licence relabel

vetting-a-skill-before-install still helps on both agents and stays
`hardened`. Claude Code goes from 84% to 100% (+16 points) at 1.05x the
tokens of the task without it, and Codex from 92% to 96% (+4 points) at
1.01x.

Why it was re-run: v0.0.31 changed the skill's frontmatter from
`license: MIT` to `license: Apache-2.0 OR MIT`. Its efficacy attestation
binds to the skill's digest, so the edit dropped the attestation until a
run measured the new bytes (`sha256:a4f3d071…6ad9`). Nothing else in the
skill changed.

The run used the case frozen on 29 September, 5 trials per arm per
agent, 20 runs: Claude Code on its default model, Codex on
`gpt-6-astra`, the same as the 30 September runs. Claude's runs cost
USD 1.08 in total; Codex reports no cost.

| Skill | Agent | Without | With | Delta | Tokens | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| vetting-a-skill-before-install | claude | 84% | 100% | +16 pts | 1.05x | helps |
| vetting-a-skill-before-install | codex | 92% | 96% | +4 pts | 1.01x | helps |

The gain sits in one finding: pinning the source to a commit before
installing. Without the skill Claude names it in 20% of runs and Codex
in 60%; with it, 100% and 80%. The other four findings are found in
every run either way.

The results file records commit `cc13ac5`, the branch commit the run
measured. Raw results: [uplift-2026-11-16-vetting.json](uplift-2026-11-16-vetting.json).
