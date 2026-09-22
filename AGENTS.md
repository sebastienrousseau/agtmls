<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# AGENTS.md

Invariants for AI-assisted contributions to AgtMLS. Read this before changing anything.

Everything here also applies to humans. It is addressed to agents because agents are fast enough to violate all of it before anyone notices.

## The core invariants

1. **Strict SemVer sequencing policy**: Public releases stay on the `0.0.x` line and increment strictly by `0.0.1`. Never manually edit version numbers; use `python3 scripts/bump-version.py`. `v0.1.0` is forbidden until `v0.0.999` exists.
2. **Zero external dependencies**: All scripts in `scripts/` must remain stdlib-only so that `uvx agtmls` and standalone script invocations are instant without resolving packages.
3. **Never hand-edit generated artifacts**: Artifacts including `index.json`, `CATALOG.md`, `site/index.html`, `agent-card.json`, `mcp-resources.json`, `SBOM.spdx.json`, `provenance.json`, and plugin manifests are derived. Regenerate them with their respective generator scripts (`--write`).
4. **Preserve dual licensing**: The repository is dual-licensed under Apache-2.0 OR MIT. All files must declare an SPDX license header.

## Before you claim to be done

The repository has 64 validation gates and tests. Before concluding any task, run:

```console
python3 scripts/run-all-checks.py
```

All unit tests, behavioral evals, routing checks, and doctor inspections must pass with 0 failures and 0 warnings. State what you ran and what you observed.
