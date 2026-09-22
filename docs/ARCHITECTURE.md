<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Architecture

AgtMLS is a registry, not a runtime. It holds skills, commands, subagents and
system prompts, and ships the stdlib-only tooling that validates, indexes,
content-addresses, audits, exports and installs them. Nothing here runs inside
an agent session; the runtimes (Claude Code, Codex, Antigravity, Aider and the
export targets) read the files it installs.

## Principles

1. **Flat skill tree.** Every skill is a leaf directory, `skills/<name>/`,
   holding `SKILL.md` and `metadata.json` (ADR 0001). Runtimes scan skill
   directories non-recursively, so nesting would hide skills.
2. **Zero runtime dependencies.** `scripts/` and `src/` use the standard
   library only, so `uvx agtmls` has nothing to resolve. Tools that need a
   package (coverage, SBOM validators, `skills-ref`) run in CI, outside the
   offline gate.
3. **Derived, never hand-edited.** Frontmatter, `index.json`, `CATALOG.md`,
   the docs site, plugin manifests, `mcp-resources.json`, the SBOMs,
   `provenance.json`, the completions, the analyzer's rule snapshot and the
   measured passages of `BENCHMARKS.md` are generated. Each generator has a
   `--check` that the gate runs.
4. **One source per fact.** `providers.json` names the native agents, and the
   CLI, completions and installer paths are derived from it. `checks.json`
   names the gate. The analyzer's rules come from `agtmls-spec`.
5. **Guarded patch-line releases.** Versions move by exactly `0.0.1`
   (`VERSIONING.md`); `bump-version.py` is the only thing that edits them.

## Modules

| Layer | Files | Role |
|---|---|---|
| Package shim | `src/agtmls/cli.py` | `uvx`/`pipx` entry point. Finds the registry (`AGTMLS_HOME`, a checkout, or the copy bundled in the wheel) and runs the dispatcher |
| Command surface | `scripts/_lib/cli_parser.py` | Every subcommand and flag, declared once. Read by `validate-cli-surface.py`, the completions generator and the unit tests |
| Dispatcher | `scripts/agtmls.py` | Handles `list`, `search`, `show`, `stats`, `verify` and `uninstall` in-process; every other subcommand runs its script |
| Integrity | `scripts/_lib/digest.py`, `scripts/_lib/lockfile.py` | The per-skill content digest (`agtmls-spec` §3) and the install lockfile with its exit-code taxonomy (§6) |
| Analyzer | `scripts/_lib/analyzer.py`, `scripts/_lib/rules.py`, `scripts/_lib/rules.json`, `scripts/audit-skill.py` | Static checks for hidden Unicode, injection phrasing, unsafe execution, exfiltration, capability escalation and policy honesty. `rules.json` is a snapshot of a pinned `agtmls-spec` commit taken by `sync-spec-rules.py`; `audit-skill.py` is the command line |
| Installer | `scripts/setup-workspace.sh` | Links or copies skills, commands and agents into a runtime's dot-directory and writes its prompt file, refusing to overwrite a prompt it did not generate |
| Generators | `scripts/generate-*.py`, `scripts/sync-*.py` | The derived artifacts in principle 3 |
| Gate | `scripts/run-all-checks.py`, `checks.json` | Every validator, generator check, eval and smoke test, run as independent processes in a pool |

## Data flow

```
skills/<name>/{SKILL.md, metadata.json, reference.md}      authored
   │
   ├─ sync-skill-frontmatter.py   metadata.json → portable frontmatter (ADR 0002)
   ├─ generate-skill-index.py     index.json: per-skill integrity = sha256 digest,
   │                              last_changed_version, safety_policy, allowed_tools
   ├─ other generators            CATALOG.md, site/, plugin manifests,
   │                              mcp-resources.json, SBOMs, provenance.json
   │
   ├─ install   recompute every digest against index.json; any mismatch → exit 3
   │            before copying → setup-workspace.sh → <target>/.agtmls/manifest.json
   ├─ verify    compare the installed tree to the lockfile: modified, missing,
   │            drifted or unmanaged files
   ├─ export    provider-adapted bundles for the 13 export targets
   └─ audit     analyzer over every file of a skill, plus its metadata
```

The digest is a SHA-256 over the sorted list of `(path, sha256(content))`
pairs of a skill's files. The release version is not part of any skill, so a
version bump changes no digest, and `index.json` carries
`last_changed_version` forward while a digest is unchanged.

## Consumption modes

- **Native install** for `aider`, `antigravity`, `claude` and `codex`: skills
  are linked or copied into the runtime's directory and recorded in a
  lockfile that `verify` checks.
- **Plugin manifests** for six plugin ecosystems, generated from
  `.claude-plugin/plugin.json` and the skill tree.
- **Export bundles** for 13 providers, produced by `export-registry.py`.

## Trust model

Which of these protections are structural and which are heuristic is set out
in [`SECURITY.md`](../SECURITY.md#boundaries-and-heuristics). In short: the
digest, install verification and the lockfile establish that installed files
are the ones this registry published; the analyzer and the policy checks are
first-stage triage.

## Related repositories

The normative spec, the Rust core, the WASM build, the GitHub Action, the MCP
server and the LSP server live in their own repositories; their status is in
[`ECOSYSTEM.md`](ECOSYSTEM.md#01-ecosystem-status).
