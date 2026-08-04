<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Changelog

All notable changes to AgtMLS are recorded here.

## Unreleased

### Added

- **A real unit-test suite for the tooling** — 65 tests across 12 cases
  covering the spec validator, collision maths, frontmatter derivation,
  packaging layout, manifest generation, index parsing, and the packaged CLI.
  The 57-check gate validates repository *data*; these validate the
  validators, which is the failure mode the gate cannot see.
- `validate-spec-conformance.py`, running the Agent Skills **reference**
  implementation (`skills-ref`) over every skill. Skips cleanly when the
  optional dependency is absent; CI installs it, so it always runs on a PR.
- `validate-licence-headers.py`, enforcing an SPDX header on every file that
  can carry one and `license:` frontmatter on the two classes that cannot
  (`SKILL.md`, `commands/*.md` must start with `---` at byte 0).
- `docs/adr/` with the first four architecture decision records, applying to
  AgtMLS the ADR discipline it already requires of the projects it serves.
- `.github/CODEOWNERS`, `docs/cli.md`, `docs/checks.md`.
- Signed build provenance on releases via `actions/attest-build-provenance`,
  plus a post-build step that installs the wheel and asserts it reports the
  released version.
- **Six discipline skills**, general (`"bundle": null`) so they install in
  every repo: `writing-plans`, `test-driven-development`,
  `systematic-debugging`, `verification-before-completion`,
  `receiving-code-review`, and `handoff`. They are
  language- and project-agnostic, compose in phase order, and defer to a
  project bundle's own rules on specifics. Adds a `discipline` install/export
  profile; the `polyglot`, `noyalib`, `security`, and `research` profiles now
  carry them too.
- **PyPI packaging**: `uvx agtmls ...` / `pipx install agtmls`, with the whole
  registry bundled in the wheel under `agtmls/_registry/` and no runtime
  dependencies. `scripts/validate-packaging.py` gates the force-include list
  so a wheel cannot ship a registry the CLI can't find.
- `--copy` on `setup-workspace.sh` and `agtmls install`, materialising real
  files instead of symlinks. Package installs default to it, because a wheel
  in an ephemeral uvx cache cannot be the target of a durable symlink.
- `.claude-plugin/marketplace.json`, so the registry is installable with
  `/plugin marketplace add sebastienrousseau/agtmls`.
- `scripts/sync-skill-frontmatter.py`, which mirrors `metadata.json` into the
  spec's `compatibility`, `metadata`, and `allowed-tools` frontmatter fields.
  Runs `--check` in CI so the sidecar and the frontmatter cannot drift.
- `allowed_tools` in `index.json`, derived from each skill's `safety_policy`.
- A `plugin_targets` section in `providers.json` for runtimes that consume a
  plugin manifest rather than a symlink install or a Markdown export:
  Antigravity, Codex, Cursor, Gemini CLI, Kimi Code, and OpenCode.
- `scripts/generate-plugin-manifests.py` (and `agtmls.py plugin-manifests`),
  which generates all eight manifests from `.claude-plugin/plugin.json` and
  the skill tree so no runtime drifts behind a version bump or a new bundle.
  Runs `--check` in CI.

### Changed

- CI runs a matrix of Python 3.10-3.13 across Linux and macOS. It previously
  tested one interpreter on one OS while declaring `requires-python >=3.10`,
  so the 3.10 code path had never executed.
- README split: the command reference and the check list moved to
  `docs/cli.md` and `docs/checks.md`; CONTRIBUTING rewritten around the gate,
  the skill lifecycle, and what a good skill looks like.
- **The skill tree is now flat**: every skill is `skills/<name>/SKILL.md`.
  Bundle membership moved from a parent directory to a `bundle` field in each
  skill's `metadata.json` (`null` for general skills). Agent runtimes scan
  their skills path *non-recursively*, so nested skills were invisible to any
  runtime without array-valued `skills` support — Codex, Cursor, Gemini CLI,
  and Antigravity among them. Every manifest now points at a single
  `./skills`. `--bundle` scoping in `setup-workspace.sh` is unchanged in
  behaviour and now resolves through metadata.
- `skills/noyalib/README.md` moved to `references/noyalib-bundle.md`.
- `validate-version-policy.py` and `bump-version.py` derive their metadata
  file lists from the skill tree instead of hardcoding them, so a new skill
  cannot escape the version gate.
- `validate-skills.py` now enforces the agentskills.io Agent Skills spec: the
  closed six-key frontmatter set, the `name` length and hyphen rules, the
  `compatibility` length cap, flat string `metadata`, and a 500-line
  `SKILL.md` budget.
- `validate-plugin-manifest.py` also validates the marketplace catalog, and
  fails if a nested skill ever reappears — such a skill would be invisible to
  every runtime. Before the tree was flattened, `plugin.json`'s single
  `./skills` path exposed only the two top-level skills; the other 18 never
  loaded for anyone installing as a plugin.

### Fixed

- `generate-skill-index.py` did not unquote the **last** frontmatter key —
  only the mid-loop flush was patched. Invisible for skills (where `metadata`
  is last) but wrong for `commands/*.md`, where `description` is the only key.
  Found by the new unit tests.
- Three checks (`validate-packaging.py`, `sync-skill-frontmatter.py`,
  `generate-plugin-manifests.py`) were in `checks.json` and the local runner
  but **absent from CI**, which enumerates steps by hand.
  `validate-check-manifest.py` now enforces manifest/runner/CI parity.
- `generate-skill-index.py` unquotes YAML scalars, so quoted descriptions no
  longer carry their quotes into `index.json` and every downstream export.
- `agtmls-doctor.py` handles array-valued `skills`/`commands` manifest paths.

### Removed

- Non-spec `date:` frontmatter keys from three noyalib skills, and the dead
  `date` field from the `index.json` schema.

## 0.0.3 - 2026-07-21

### Changed

- Bumped release metadata through the guarded patch-line release flow.


## 0.0.2 - 2026-07-21

### Changed

- Bumped release metadata through the guarded patch-line release flow.


## 0.0.1 - 2026-07-20

### Added

- Registry `index.json` generation and validation.
- Full routing eval coverage for all current skills.
- Behavioral smoke evals for all current skills.
- Local `agtmls` dispatcher for registry checks, install flows, provider export,
  evolution proposals, evidence recording, benchmarks, SBOM, provenance, MCP
  resources, and agent-card generation.
- Doctor checks for registry health and consumer-repo installs.
- Skill metadata sidecars with bundle inheritance.
- Lifecycle metadata and validation.
- Command validation and plugin command-path consistency checks.
- Security and contribution policy documents.
- Provider export/install adapters for Claude, Codex, Aider, Cursor, GitHub
  Copilot, Continue, Windsurf, Zed, OpenAI, Anthropic, and Google Gemini
  style targets.
- Generated `CATALOG.md`, docs site, `agent-card.json`, `mcp-resources.json`,
  `SBOM.spdx.json`, and deterministic `provenance.json`.
- Governance, release, smoke, behavioral, routing, and benchmark checks in the
  release gate.
- 2026-ready skill bundles for agent loop design, AI supply-chain security, web
  research/source triage, PR/release workflow, and project-specific noyalib
  operations.
