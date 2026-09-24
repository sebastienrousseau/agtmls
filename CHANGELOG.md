<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Changelog

All notable changes to AgtMLS are recorded here.

## Unreleased

## 0.0.9 - 2026-09-24

### Added

- Releases sign `index.json` (agtmls-spec chapter 9). A `sign-index` job
  in `release.yml` runs in the protected `release` environment, signs the
  exact bytes with the release key, and verifies the signature against
  the tag's `ALLOWED_SIGNERS`; the wheel carries `index.json.sig` beside
  `index.json` through a build hook, the signature is a checksummed
  release asset, and the installed wheel's copy is verified before
  anything is published. `release-audit.py` requires a verifying
  `index.json.sig` for every tag whose commit trusts `ALLOWED_SIGNERS`,
  so releases before signing still audit clean.
- `ALLOWED_SIGNERS` holds the release signing key (`agtmls-release`,
  Ed25519, valid from 2026-09-24) for the index, attestation and
  advisory namespaces, and ships in the wheel. The private half lives
  only in the protected `release` environment, deployable from `v0.0.*`
  tags with the maintainer's approval.
- `verify --signatures` requires `index.json` to carry an OpenSSH
  signature under `agtmls-index@v1` that verifies against
  `ALLOWED_SIGNERS` (agtmls-spec chapter 9), and `verify` consults a
  signed advisory feed (chapter 11): an installed digest a live advisory
  lists exits `6` and names the advisory; a feed that does not verify is
  never consulted. New exit codes `4` unsigned, `5` bad signature, `6`
  revoked, with the spec's precedence `5`, `3`, `6`, `4`. The spec's
  signature and advisory vectors are reproduced in the unit suite. The
  registry itself is not signed yet.
- Per-skill attestations (agtmls-spec chapter 10), the first
  implementation of it: `generate-skill-manifests.py` writes
  `attestations/<skill>/manifest.intoto.json` (the skill digest's own
  file list) and `capabilities.intoto.json` (declared policy, granted
  tools, escalations) for every skill, canonically rendered and outside
  the skill directory; `--check` joins the gate. The spec's four vectors
  are reproduced byte for byte in the unit suite.
- The tool-to-capability table is read from the spec snapshot's
  `AGT-CAP-001` instead of a copy kept here; a snapshot without it is
  refused. The snapshot follows agtmls-spec `295d699`.
- A `*.json` file is escape-decoded before the normalised rules run
  (agtmls-spec 4.3): `Ignore previous\n instructions` in an MCP tool
  description is the phrase a model reads, and `ig\u200bnore` decodes to
  a zero-width space that is then stripped. Escaped whitespace becomes a
  space, so line numbers still point into the source. Three corpus cases.
- Pattern rules run only where their `applies_to` selectors say
  (agtmls-spec 4.11), and the snapshot follows the spec commit that
  defines and widens them: injection rules cover every file, so an
  instruction override in a JSON MCP tool description is caught, and
  execution rules cover JSON, YAML and TOML. A Python test naming an MCP
  tool is no longer flagged as one. Any file beginning with `#!` is
  audited even with no extension or execute bit. The corpus mirrors four
  new cases, 101 in all.
- The rule snapshot follows agtmls-spec `5741d6d`: `AGT-HOOK-003`
  (MEDIUM, repository hooks run on a lifecycle event without a trust
  gate) and `AGT-POLICY-006` (HIGH, an unscoped tool family in
  `permissions.allow`). 33 rules; the corpus mirrors four new cases.
- Emoji context for steganography (agtmls-spec 4.10): a variation
  selector directly after an emoji base, and a well-formed subdivision
  flag, are `AGT-STEG-002` at LOW rather than `AGT-STEG-001` at
  CRITICAL. The selector is reported only with the new `audit
  --pedantic`; the flag always. Everything else, including a run of two
  selectors, a selector after a letter and the variation selectors
  supplement, stays CRITICAL. The line is data on the spec's rule, and
  the analyzer behaves as before until the snapshot carries it.
- The rule snapshot follows agtmls-spec `eb99f7a`, which carries that
  table, `AGT-STEG-002` and the variation selectors supplement
  (U+E0100 to U+E01EF) in `AGT-STEG-001`'s ranges. The corpus mirrors
  the spec's seven new cases, 93 in all, and the registry audits clean.

### Fixed

- The test fixture copied everything at the repository root, so with a
  release signature present its signing tests waited forever for
  `ssh-keygen` to be told it may overwrite `index.json.sig`: the release
  job's gate would have hung. The fixture leaves the signature out, and
  test signing never reads stdin and times out.

## 0.0.8 - 2026-09-24

### Added

- The analyzer runs every rule but steganography on the text an agent
  reads: hidden code points are stripped and compatibility forms folded
  (NFKC) before matching. A keyword split by a zero-width space or a tag
  character, or spelt in fullwidth letters, matched no rule; the hidden
  bytes were reported and the instruction went unnamed, and the
  fullwidth spelling escaped both. Five corpus cases pin this.
- An injection quoted in a fenced block or blockquote under a heading
  that says "example", "attack" or "do not" is reported at MEDIUM rather
  than HIGH: a skill that quotes an attack to teach against it is not
  attacking. It still appears and still fails `--strict`.
- In-source suppressions: `<!-- agtmls-ignore AGT-INJ-001: reason -->`
  covers the next line only, needs a reason, and never covers
  steganography. Suppressed findings are listed, not counted, and
  emitted in SARIF under `suppressions`.
- `audit --format sarif` (SARIF 2.1.0), `--write-baseline FILE` and
  `--baseline FILE`, so a CI gate fails on new findings only. Findings
  carry a fingerprint over rule, file and message, not the line.
- `agtmls --version` prints the registry version. It was a usage error.
- `providers.json` says what each native agent does with a skill's
  `allowed-tools`: `grant` (Claude Code pre-approves them), `declaration`
  (the Agent Skills spec's reading: aider, antigravity, codex) or
  `ignored`. AGT-CAP-001 now reports effective escalation per target
  from that table instead of a generic claim about runtimes.
- The security corpus grows from 22 to 73 cases: one or more per rule,
  in scripts and configs as well as Markdown, and twelve benign
  negatives every detector must stay silent on. `run-security-evals.py`
  now reports precision and recall and holds them to
  `evals/security/floor.json` (1.0 and 1.0), which `--update` may raise
  and never lower; a miss within the floor is a warning. A
  `must_not_detect` entry may name a severity, so a quoted attack can
  require "nothing at HIGH" without requiring silence.
- The analyzer runs every pattern rule in the spec snapshot with the
  category, severity and scope the rule declares, instead of three
  hard-coded categories at HIGH. The Rust implementation already did;
  a rule of a category Python never named fired there and not here,
  which the differential conformance run would have caught only after
  the rule shipped. With today's nineteen rules nothing changes.
- The rule snapshot follows agtmls-spec `f298cc6`: eleven new pattern
  rules over the surfaces an agent actually runs, in six new classes.
  `AGT-HOOK-001` and `-002` (hooks that auto-approve or fetch),
  `AGT-CAP-002` (wildcard tool grants), `AGT-SUPPLY-001` (unpinned
  runners), `AGT-EXEC-005` to `-007` (self-install, permission-bypass
  flags, model output interpolated into a shell string), `AGT-MCP-001`
  (command-running MCP tools), `AGT-PACK-001` (decode-and-execute
  payloads), `AGT-SOCIAL-001` (paste-this-command prose) and
  `AGT-SEL-001` (selection gaming). `AGT-EXEC-002` now matches `rm -fr /`.
  The corpus mirrors the spec's thirteen new cases, 86 in all. Eleven
  more rules are eleven more passes over every file: `audit --all
  --strict` moves from 264 ms to 383 ms P50 on the laptop, and both
  bench baselines are re-recorded for the new rule count rather than
  the regression budget widened.
- `audit --foreign <path|git-url@sha>` audits every skill in a repository
  that is not this registry: a Claude marketplace, a plugin manifest or a
  skills directory, per plugin and skill, against the skill's own policy
  or a provisional one inferred from `allowed-tools`. A root `SKILL.md`
  is refused as a repository, not a skill. Fetching is opt-in by URL and
  only by exact commit.

### Fixed

- `uninstall` removed nothing after a `uvx agtmls install`: the wheel's
  install copies (its cache is ephemeral) and uninstall knew only symlinks
  into a checkout. It now removes the copied skills the lockfile records,
  and copied commands and agents that still equal the registry's; a skill
  edited since install is left in place, as `verify` reports it rather
  than repairs it. Linked agents are removed too, and a lockfile with
  nothing left to describe goes with them.
- `uvx agtmls doctor` reported 30 failures from a healthy install, every
  one a repository document, workflow or check the wheel never ships.
  The packaged entry point now runs the doctor with `--installed`, which
  inspects the registry and the target and skips the checkout
  inspections and the gate; and copied skills recorded in the lockfile
  are no longer "missing links".
- `doctor --target .` inspected the registry, not the caller's repository:
  the doctor runs with the registry as its working directory, and a
  relative target was forwarded unresolved. It is resolved against the
  caller's directory first, as `diff` already was.
- The doctor expected every bundled skill in a target and reported
  eighteen missing after a plain install. It now expects the general
  skills plus the bundles named with `--bundle`, the installer's rule.

## 0.0.7 - 2026-09-23

### Breaking

- `agtmls agent-card` and `agent-card.json` are removed. The file declared
  itself `not_a2a`, nothing consumed it, and it could not conform to A2A v1.0
  without a service endpoint.

### Added

- `antigravity` is a native agent for `install`, `verify` and `uninstall`,
  installing into `.agents/`. `setup-workspace.sh` already accepted it; the
  CLI rejected it.
- Benchmarks: nine workloads measured in fresh processes with every raw
  sample committed under `benchmarks/results/`, a regression gate, and a
  scaling measurement at ten times the registry.
- `smoke-offline.py` proves the local tier never opens a network socket.
- CodeQL scans the Python and the workflows (`codeql.yml`, security-extended
  queries), on every pull request, on main, and weekly.
- CI lints `scripts/` and `tests/` with a pinned ruff (`conformance.yml`).
  `pyproject.toml` enables E402 and SLF001, the rules the code already
  carried reasoned `noqa` directives for; without them each directive was
  itself a finding, and 26 of them made a clean run impossible.
- Coverage measurement, with the library core held at 100% of lines and
  branches. The security analyzer now sits inside that floor.
- Unit-test coverage of every script is held at or above 98% of lines and
  branches (`run-coverage.py --scope unit`, run in CI); it stands at 100%.
- SECURITY.md separates boundaries (digests, install verification, the
  lockfile, signed tags) from heuristics (the analyzer, policy checks, evals).
- `scripts/release-preflight.py` refuses to let a release tag be pushed unless
  it is signed by a key in `KEYS.asc`, titled `AgtMLS v<version>`, on the
  intended commit, matched by every packaged version, and accompanied by notes
  with a summary and checksums. `scripts/release-audit.py` reads a published
  release back from the tag, the GitHub release and PyPI -- including every
  asset's digest. RELEASE.md describes the flow.
- The release workflow builds once and publishes those exact files to both the
  GitHub release and PyPI. It attaches assets to a draft, publishes only when
  GitHub holds all of them, writes the release body from the prepared notes
  plus the real checksums, and audits the result before PyPI is approved.
  It can also publish the wheel and sdist already attached to a public
  release (`publish_existing`), which is how v0.0.6 reached PyPI.
- Release assets are counted, listed and downloaded through each release's
  assets endpoint. For about 40 minutes after v0.0.6 was published, the asset
  list GitHub embeds in a release -- read by `gh release view`,
  `gh release download` and the tag and list endpoints -- showed none of its 17
  assets. That was misread at the time as a failed upload, and v0.0.6's first
  PyPI deployment was rejected on that basis; the assets had been attached,
  and the rebuilt wheel and sdist would have been byte-identical.

### Changed

- README.md follows the portfolio template: its seventeen sections in the
  template's order, checked by `validate-readme.py` in the gate. Stale
  counts are corrected (4 native agents, 6 plugin targets and 13 export
  targets, not 3, 5 and 8), the provenance description matches what
  `provenance.json` now pins, and the benchmark table is generated from
  `benchmarks/results/` like BENCHMARKS.md. `docs/POLICIES.md` states the
  toolchain floor. VERSIONING.md no longer lists the removed agent card.
- A skill's digest no longer includes the release version, so a release
  moves no content address unless the skill itself changed.
- The analyzer's rules are a snapshot of a pinned `agtmls-spec` commit
  (`scripts/_lib/rules.json`), checked for self-consistency in the gate and
  against the spec in CI, instead of a hand-kept copy.
- Every measured number in BENCHMARKS.md is generated from the raw results
  and stamped with their hashes. The scaling section had drifted: it now
  reports x7.02 (digest) and x110.62 (pairwise) for ten times the registry.
- README and SECURITY.md describe the analyzer as first-stage triage rather
  than a defence, and the gate rejects absolute security claims.
- The `security` and `research` profiles install their own bundles; general
  profiles no longer pull in the `noyalib` project bundle.
- The gate audits the shipped registry with `--strict` and runs in parallel;
  it is now 66 checks.
- `export` selects skills the way `install` does: without a profile it
  exports the general skills, and `--bundle NAME` adds that bundle to them.
  It used to export every bundle when unfiltered, and only the named bundle
  with `--bundle`.

### Fixed

- `docs/checks.md` listed 47 of the gate's checks in another order and one  check-count:historical
  invocation the gate does not run. It is now generated from `checks.json`
  (`generate-checks-doc.py`, itself a gate check). The manpage and the pull
  request template still called the gate "57-gate"; prose throughout now  check-count:historical
  says "every check in `checks.json`", so adding a check edits no prose,
  and `validate-check-manifest.py` scans six more files for a number
  creeping back.
- Main's CI failed after every squash merge while every pull request check
  passed. The SBOMs and `provenance.json` were stamped with the date of the
  last commit touching the described files, and provenance named that
  commit; a squash merge lands the same tree as a new commit, so the files
  were stale on arrival. The stamp is now when the described content last
  changed, kept in each file and preserved by `--write` while nothing else
  moves; provenance pins its source by the SBOM's digest instead of a commit
  hash. Neither generator reads git, so the verdict depends on the tree
  alone. The old stamp was also off by the committer's UTC offset: it
  printed the commit's local time with a `Z` suffix.
- AGT-CAP-001 could not fire on any real skill: `allowed-tools` is
  space-separated and was split on commas only.
- The licence gate counted `.py` and `.sh` files without reading them; 87
  files lacked an SPDX header.
- `mcp-resources.json` used `agtmls://skills/` while agtmls-mcp serves
  `agtmls://skill/`.
- The spec-conformance check passed silently in CI when `skills-ref` failed
  to install.
- SBOM.cyclonedx.json did not validate against CycloneDX 1.6.
- Error messages name the command that fixes the problem.
- `install` refused a tampered skill only if the index gave it a digest; an
  entry without one is now refused too.
- `agtmls doctor --agent antigravity` was rejected, and the doctor counted a
  link into a sibling checkout as an AgtMLS skill.
- `scaffold-skill` crashed and left a half-created skill when an eval case
  already existed; it now writes every file or none.
- `validate-skill-metadata` crashed on malformed `metadata.json`.
- Behavioral evals now enforce `forbids.reference_contains`.
- `agtmls diff` looked up relative paths from the checkout rather than the
  caller's directory, and failed outside it without `--to`.
- A blank or malformed line in `SHA256SUMS` crashed the release checks, and a
  tampered artifact was reported three times.
- The SBOM check treated any validator output containing "must" as a
  rejection, and crashed on a checksum entry without an algorithm.
- On Python 3.10 the packaging check skipped the name, console-script and
  no-dependencies checks.
- `bump-version` left two blank lines between changelog sections.
- `bump-version` did not move `CITATION.cff` or regenerate the manpage,
  so both still said 0.0.6 after the bump to 0.0.7. It does now, and
  `generate-manpage.py --check` joins the gate.
- AGT-CAP-001 no longer says every runtime grants the tools in
  `allowed-tools`; Claude Code does, Apache Maka does not.

## 0.0.6 - 2026-09-19

### Added

- Dual licensing under Apache-2.0 and MIT: added `LICENSE-APACHE` and `LICENSE-MIT` (merging #17).

### Changed

- Updated packaging and manifest validation tooling (`pyproject.toml`, `validate-packaging.py`, `validate-plugin-manifest.py`, `agtmls-doctor.py`, `export-registry.py`) to support dual license declarations.
- Bumped release metadata through the guarded patch-line release flow to `v0.0.6`.

## 0.0.5 - 2026-08-04

### Added

- Four general skills: `brainstorming` (pin down a vague ask before planning),
  `giving-code-review` (the complement to `receiving-code-review`),
  `refactoring-safely` (shape changes under a characterisation net), and
  `incident-response` (mitigate first, diagnose after). General skills go from
  8/26 to 12/30; the noyalib share drops from 53% to 46%.
- **Subagents**: an `agents/` directory with `skill-author` and
  `registry-auditor`, wired through `plugin.json`, the marketplace catalog,
  every generated plugin manifest, `providers.json` (`agents_dir` per native
  agent), the installer, and the wheel.
- Three commands — `agtmls-new-skill`, `agtmls-audit`, `agtmls-release` —
  taking the catalog from 1 to 4.
- Five index tags the taxonomy lacked: `refactoring`, `review`, `planning`,
  `incident`, `continuity`.

### Fixed

- `bump-version.py` did not update `.claude-plugin/marketplace.json`, which
  pins the version twice; the catalog would have advertised the previous
  release.
- `validate-licence-headers.py` did not know `agents/*.md` is frontmatter-first
  like `SKILL.md`, so it demanded a leading comment that would have broken
  agent parsing.
- `bump-version.py` inserted its boilerplate *above* the accumulated
  `Unreleased` entries, so a release adding four skills was headlined "bumped
  release metadata". It now moves the accumulated entries into the new
  version.

### Changed

- CI actions moved off the deprecated Node 20 runtime: `actions/checkout` v4
  to v7, `actions/setup-python` v5 to v7, `actions/attest-build-provenance`
  v2 to v4.

## 0.0.4 - 2026-08-04

### Fixed

- `bump-version.py` did not update `.claude-plugin/marketplace.json`, which
  pins the version twice. The catalog would have shipped advertising the
  previous release. Caught by the manifest parity check.

### Changed

- Bumped release metadata through the guarded patch-line release flow.

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
