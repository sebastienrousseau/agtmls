<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Credits

AgtMLS takes ideas from other projects and writes its own code and text for
them. Nothing here is copied: every file in the registry is offered under
`Apache-2.0 OR MIT` ([ADR 0005](docs/adr/0005-one-licence-expression.md)), and
pasted third-party text would carry its own licence instead. This file
records where an idea came from, so a reader can follow it to the original.

## Ideas in use

| Idea | In AgtMLS | Source | Licence |
| --- | --- | --- | --- |
| Flagging skill descriptions too similar to tell apart (TF-IDF) | `scripts/check-skill-collisions.py` | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | MIT |
| Ranking descriptions against prompts as a routing proxy (TF-IDF) | `scripts/run-trigger-evals.py` | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | MIT |

## Projects studied for the roadmap

These were read, without running anything from them, on 2026-11-16 at the
commits listed. When a release adopts one of their ideas, it is added to the
table above with the AgtMLS file that carries it.

| Project | Commit | Licence |
| --- | --- | --- |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | `4680893` | MIT |
| [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action) | `9fa6885` | MIT |
| [mattpocock/skills](https://github.com/mattpocock/skills) | `5863806` | MIT |
| [Gentleman-Programming/gentle-ai](https://github.com/Gentleman-Programming/gentle-ai) | `1ab243c` | MIT; its skill files say Apache-2.0 |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | `39b723c` | MIT |
| [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) | `c1c8a8c` | MIT |
| [stablyai/orca](https://github.com/stablyai/orca) | `cbd75eb0` | MIT |
| [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) | `e91a134` | Apache-2.0 |
