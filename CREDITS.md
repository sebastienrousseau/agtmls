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
| A plugin review rubric over hooks, MCP servers and pinning | `scripts/_lib/agent_config.py` (inventory), AGT-HOOK-006 | [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) | Apache-2.0 |
| Stripping channels a reader never sees (HTML comments, alt text) before a model reads them | AGT-RENDER-001 | [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action) | MIT |
| Warning on a suppression that no longer suppresses anything | AGT-SCAN-002, `scripts/_lib/analyzer.py` | [swamp-club/swamp](https://github.com/swamp-club/swamp) | AGPL-3.0; idea only, no code or text |
| A tool pre-approving its own destructive subcommands, as a risk to flag | AGT-PERM-002 | [swamp-club/swamp](https://github.com/swamp-club/swamp) | AGPL-3.0; idea only, no code or text |

The other rules added in 0.0.34 (AGT-HOOK-007, AGT-MCP-003, AGT-MCP-004,
AGT-PERSIST-001, AGT-SUPPRESS-001, AGT-ATTR-001, AGT-INST-001,
AGT-SUPPLY-004) detect patterns observed in the projects below rather than
ideas taken from them. [`evals/security/foreign-acceptance.json`](evals/security/foreign-acceptance.json)
pins the commit of each where an audit must still report them.

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
