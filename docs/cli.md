<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# CLI reference

`scripts/agtmls.py` is the dispatcher for every registry operation. From an
installed package the same surface is available as `agtmls ...`; see the
install section of the README for which commands need a checkout.

```bash
python3 scripts/agtmls.py check
python3 scripts/agtmls.py list
python3 scripts/agtmls.py list commands
python3 scripts/agtmls.py search yaml
python3 scripts/agtmls.py show cross-language-port
python3 scripts/agtmls.py stats
python3 scripts/agtmls.py profiles
python3 scripts/agtmls.py providers
python3 scripts/agtmls.py export --provider openai --profile polyglot --out-dir dist
python3 scripts/agtmls.py docs-site --write
python3 scripts/agtmls.py release-pack --profile polyglot --out-dir dist/release
python3 scripts/agtmls.py next-version
python3 scripts/agtmls.py bump-version --check --version 0.0.2
python3 scripts/agtmls.py release-dry-run --version 0.0.1 --skip-check
python3 scripts/agtmls.py verify-release-assets --tag v0.0.1
python3 scripts/agtmls.py evolve transcript.txt --skill-name candidate-skill
python3 scripts/agtmls.py evidence --skill cross-language-port --command pytest --file src/example.py
python3 scripts/agtmls.py agent-card --write
python3 scripts/agtmls.py mcp-resources --write
python3 scripts/agtmls.py plugin-manifests --write
python3 scripts/agtmls.py sbom --write
python3 scripts/agtmls.py provenance --write
python3 scripts/agtmls.py provider-install --provider cursor --target /path/to/repo --profile polyglot
python3 scripts/agtmls.py bench
python3 scripts/agtmls.py diff --from index.json --to index.json
python3 scripts/agtmls.py release-check
python3 scripts/agtmls.py import-skill /path/to/external/skill --name candidate-skill
python3 scripts/agtmls.py index --check
python3 scripts/agtmls.py status
python3 scripts/agtmls.py status --target /path/to/repo --agent codex --skills-only
python3 scripts/agtmls.py install rust claude --target /path/to/repo --skills-only --bundle noyalib
python3 scripts/agtmls.py install rust codex --target /path/to/repo --skills-only --profile noyalib
python3 scripts/agtmls.py uninstall claude --target /path/to/repo --remove-prompt
python3 scripts/agtmls.py propose-skill transcript.txt --skill-name candidate-skill
python3 scripts/agtmls.py scaffold-skill candidate-skill
```
