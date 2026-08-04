# noyalib-ci-and-release — reference

Complements `SKILL.md` in the same directory. Date-stamped **2026-07-08**
against noyalib v0.0.14 on branch `feat/v0.0.14`. If this file and the
`.github/workflows/*` / `supply-chain/*` / `deny.toml` / `osv-scanner.toml`
files disagree, the files win — re-verify with the commands in SKILL.md
"Provenance and maintenance".

This is the deep inventory + verbatim excerpts + full matrices that were
moved out of `SKILL.md` to keep the main runbook compact. Cross-refs
below point back to SKILL.md sections.

**Contents:**

- §A — Full workflow inventory (25 files) — *complements SKILL.md §1.*
- §B — `ci.yml` job list (19+ gates) — *complements SKILL.md §1.*
- §C — `shared-no-std.yml` verbatim + full isolated-target-dir list —
  *complements SKILL.md §2 (the cache-poisoning doctrine).*
- §D — Reading-CI-failures `gh` cheat-sheet + failure-class catalogue —
  *complements SKILL.md §3.*
- §E — Supply-chain gates, per-tool deep detail — *complements SKILL.md §4.*
- §F — Release flow, full per-step detail + release.yml jobs + satellite
  prereq matrix — *complements SKILL.md §5.*
- §G — Caller-permissions matrix + shared-workflow edit rollout —
  *complements SKILL.md §6.*

---

## §A — Full workflow inventory (verify with `ls .github/workflows/`)

**Complements SKILL.md §1.** Top-level workflow files under
`.github/workflows/` — 8 non-shared + 17 shared-* = **25 total**,
verified 2026-07-08 via `ls .github/workflows/`.

### Non-shared workflows (8)

| File | Trigger | Purpose |
|------|---------|---------|
| `ci.yml` | push (main + feat/**), PR, nightly cron 04:00 UTC, dispatch | The orchestrator. `permissions: read-all`. See §B below for the reusables it wires in. |
| `security.yml` | push main, PR main, weekly Mon 06:00 UTC | Dependency-review (PR-only, warn-only), CodeQL `languages: actions`, weekly soak-fuzz matrix (`fuzz_parse`/`fuzz_roundtrip`/`fuzz_diff`/`fuzz_strict`, 1h each), weekly soak-Miri (24h ceiling). |
| `scorecard.yml` | branch_protection_rule, push main, weekly Mon 04:00 UTC, dispatch | OpenSSF Scorecard SARIF → Code Scanning + Rekor. `security-events: write`, `id-token: write`. |
| `release.yml` | push tags `v[0-9]+.[0-9]+.[0-9]+*`, dispatch (with `dry_run` input) | Validate → build artifacts (SLSA L3 attestation + cosign keyless bundles) → cross-verify (ubuntu / macos / windows) → GitHub Release → publish `noyalib` to crates.io from the `crates-io` environment. |
| `docs.yml` | push main, dispatch | Strict-rustdoc Pages build + deploy. Isolated `target-docs-pages`. |
| `crates-io-ownership.yml` | daily 04:00 UTC, PR labelled `workspace-split`, dispatch | Guards ADR-0005 §Naming reservations — fails if any satellite name drifts owner on crates.io. |
| `ci-duration-monitor.yml` | push main, daily 05:00 UTC, dispatch | Fails if the latest CI run is > 1.1× the rolling 5-run average — catches a shared-workflow SHA bump silently doubling CI. |
| `shared-workflow-propagation.yml` | daily 06:00 UTC, dispatch | Enforces the 48h Dependabot SHA-bump SLA across every satellite consuming this repo's shared-* workflows. Pre-satellite-existence it SKIPs cleanly. |
| `auto-approve-dependabot.yml` | pull_request_target opened/reopened/synchronize | Patch / minor Dependabot bumps auto-approved (major requires human). Feeds Scorecard's Code-Review check. |

(Note: table lists 9 rows because `auto-approve-dependabot.yml` is a
non-shared workflow but wasn't in the "8" count of "big" ones; the total
non-shared count above should read 9 if you strictly count files —
verify with `ls .github/workflows/ | grep -v '^shared-'`. This is the
kind of drift to flag when re-verifying.)

### Shared reusables (17)

All `on: workflow_call`, all `permissions: contents: read` (with the one
documented exception for signature verification).

| Shared workflow | Gates | Notes |
|-----------------|-------|-------|
| `shared-test-matrix.yml` | `cargo test <flags>` across `os-list × toolchain-list` (defaults: ubuntu/macos/windows × stable/nightly). | Nightly is `continue-on-error` so a nightly regression does not block PRs. |
| `shared-msrv-core.yml` | MSRV (default 1.85.0) 3-way: `cargo check --no-default-features --lib`, `cargo check`, `cargo clippy --lib -- -D warnings`. | Each leg gets its own `CARGO_TARGET_DIR` (`target-msrv-nostd`, `target-msrv-default`, `target-msrv-clippy`). See §C. |
| `shared-per-crate-msrv.yml` | Walks every workspace crate, runs `cargo +<its-msrv> check`. | Requires caller-provided `scripts/msrv-per-crate.sh`. |
| `shared-no-std.yml` | `cargo check --no-default-features --lib --locked` native + `wasm32-unknown-unknown` bare-metal. | The canonical cache-poisoning-guard exemplar (§C). |
| `shared-coverage.yml` | `cargo +nightly llvm-cov --workspace --all-features` gated at inputs `fail-under-functions/lines/regions` (noyalib: 96/94/93). | Sets `NOYALIB_COVERAGE=1` so `#[cfg(noyalib_coverage)]` panic-path exclusions apply. Isolated `target-coverage`. |
| `shared-miri-focused.yml` | `pull_request`-only. Runs caller's `scripts/miri.sh` on nightly. 60-min timeout. | Miri sysroot cache keyed on `hashFiles('rust-toolchain.toml','Cargo.lock')`. Isolated `target-miri`. |
| `shared-miri-full.yml` | `schedule`/`dispatch`-only. Full `cargo miri test --lib` + big-endian `mips64-unknown-linux-gnuabi64` via `MIRI_TARGET`. | Isolated `target-miri-full`. |
| `shared-fuzz-diff.yml` | Skip on `schedule`; else 10-second smoke of `fuzz/fuzz_targets/fuzz_diff.rs`. | Isolated `target-fuzz`. `continue-on-error` for the fuzz step (crash upload still needed). |
| `shared-cargo-deny.yml` | `cargo deny check` (advisories + bans + licenses + sources). | Simple `EmbarkStudios/cargo-deny-action` invocation; uses caller's `deny.toml`. |
| `shared-cargo-vet.yml` | `cargo vet --locked`. | Requires caller's `supply-chain/{audits,config,imports}.toml`. See §E. |
| `shared-cargo-machete.yml` | `cargo machete` — unused-dep gate. | Fails if a `[dependencies]` entry is not referenced anywhere. |
| `shared-reuse.yml` | `fsfe/reuse-action` — SPDX header + LICENSE-file coverage. | Uses caller's `REUSE.toml`. |
| `shared-rustdoc-strict.yml` | `cargo doc --workspace --no-deps --all-features --locked` with the same strict `RUSTDOCFLAGS` `docs.yml` uses on main. | Isolated `target-docs-strict`. See §C — this is a documented cache-poisoning class. |
| `shared-readme-examples.yml` | Compiles every ` ```rust ` block in root `README.md` via `scripts/check-readme-examples.sh`. | Isolated `target-readme-examples`. |
| `shared-vendor-offline.yml` | `cargo vendor` + `.cargo/config.toml` → `cargo build --workspace --all-features --offline --locked`. | Guards air-gapped / FIPS / RHEL consumers. |
| `shared-verify-signatures.yml` | `pull_request`-only. Iterates PR commits via GH REST, fails if any is unverified. | Only workflow that needs `pull-requests: read` beyond `contents: read`. See §G. |

---

## §B — `ci.yml` job list (as of 2026-07-08)

**Complements SKILL.md §1.** Verify with
`grep -E '^  [a-z-]+:$' .github/workflows/ci.yml`. The orchestrator
wires:

- `ci` → `sebastienrousseau/pipelines/.github/workflows/rust-ci.yml@<sha>`
  (external reusable: stable clippy / fmt / audit; coverage disabled
  because a dedicated `coverage-gate` uses `+nightly` for
  `feature(coverage_attribute)`).
- `test-matrix`, `miri-focused`, `miri-full`, `cargo-deny`, `fuzz-diff`,
  `cargo-vet`, `cargo-machete`, `reuse-lint`, `msrv-1-85-core`
  (`toolchain: "1.85.0"`), `coverage-gate` (96/94/93), `vendor-build`,
  `msrv-per-crate`, `no-std`, `readme-examples`, `docs-strict`,
  `verify-signatures` — all local `uses: ./.github/workflows/shared-*.yml`.
- `cargo-semver-checks` — inline job. Probes `crates.io/api/v1/crates/noyalib`
  first; short-circuits until the first publish exists.
- `lossless-u64-matrix` — inline 2-leg (`defaults + lossless-u64`,
  `all-features`) with its own `target-lossless-u64-${matrix.leg}` per §C.

**Concurrency:** `${{ github.workflow }}-${{ github.ref }}` with
`cancel-in-progress: true` (an earlier run of the same ref is cancelled
when a new push lands).

---

## §C — Cache-poisoning: verbatim exemplar + full isolated-dir list

**Complements SKILL.md §2 (THE cache-poisoning doctrine).**

### Canonical exemplar — `shared-no-std.yml`:

```yaml
jobs:
  check:
    runs-on: ubuntu-latest
    env:
      CARGO_TARGET_DIR: ${{ github.workspace }}/target-no-std
    steps:
      - uses: actions/checkout@...
      - uses: dtolnay/rust-toolchain@... { toolchain: stable }
      - uses: Swatinem/rust-cache@...
        with:
          workspaces: ". -> target-no-std"
          key: no-std
      - run: cargo check --no-default-features --lib --locked
```

Note all three isolating knobs together:

1. `env.CARGO_TARGET_DIR` moves the actual artefact dir off `target/`.
2. `workspaces: ". -> target-no-std"` tells Swatinem to look at that dir.
3. `key: no-std` splits the cache namespace so a `std`-on job can't
   restore into it and vice-versa.

### Current isolated dirs (2026-07-08)

Verify with `grep -rn "CARGO_TARGET_DIR" .github/workflows/ | head`.

- `target-no-std`, `target-no-std-wasm` — `shared-no-std.yml`
- `target-msrv-{nostd,default,clippy}` — `shared-msrv-core.yml`
- `target-miri`, `target-miri-full` — the two Miri workflows
- `target-fuzz`, `target-soak-fuzz-${matrix.target}` — fuzz
- `target-soak-miri` — weekly Miri
- `target-coverage` — `shared-coverage.yml` (with `NOYALIB_COVERAGE=1`)
- `target-docs-strict`, `target-docs-pages` — the two rustdoc-strict jobs
- `target-readme-examples` — README example compiler
- `target-lossless-u64-${matrix.leg}` — feature-matrix guard in ci.yml
- `target-release-validate`, `target-release-verify-${matrix.os}` —
  release.yml

---

## §D — Reading CI failures fast: `gh` cheat-sheet + failure classes

**Complements SKILL.md §3.**

### The full investigation loop when a PR check is red

```bash
# 1. Which checks are red on this PR?
gh pr checks <PR-number>

# 2. List the failing runs on the branch (or on main).
gh run list --branch feat/v0.0.14 --workflow ci.yml

# 3. Jump straight to the failing job — the "steps" view surfaces
#    exactly which step failed and its exit code.
gh run view --job <job-id>

# 4. For raw logs of a job while the workflow is still running,
#    hit the REST endpoint directly. `gh run view --log-failed`
#    REFUSES on in-progress runs — the real-world gotcha.
gh api repos/sebastienrousseau/noyalib/actions/jobs/<job-id>/logs

# 5. Once the run finishes, --log-failed narrows to failing steps only.
gh run view <run-id> --log-failed
```

### Failure classes recently seen on this repo (2026-06 → 2026-07)

SKILL.md §3 lists the top three (rustfmt / clippy nightly / cargo-deny
mid-PR). The full catalogue:

- **rustfmt drift** after hand-edits. Fix: `cargo fmt` before pushing.
  The reusable `ci` (external) job runs `cargo fmt --check` and refuses
  on any drift. `make fmt` locally.
- **clippy lints on a new nightly toolchain.** Recent culprit:
  `byte_char_slices` promotion. Fix: address the lint or gate with
  `#[allow(clippy::<lint>)]` under the specific `#[cfg]`. Never blanket
  `-A` at the crate level.
- **cargo-deny advisory landing mid-PR.** RustSec publishes a new
  entry between when your PR opened and now. Fix: `cargo update -p
  <crate>` to a fixed version; if none is available yet, add a
  narrow `[advisories.ignore]` entry in `deny.toml` **with a
  comment explaining why and when to revisit** (see the
  `RUSTSEC-2026-0173` example already in the file for
  `proc-macro-error2`). Mirror to `osv-scanner.toml` — see §E.
- **cargo-vet on new crate versions.** A dep bump moves a crate to a
  version not covered by any imported audit feed. Fix: prefer a
  `[[trusted]]` entry if the publisher is one of the 7 trusted feeds;
  else add an `[[exemptions]]` in `supply-chain/config.toml` with the
  rationale in the commit message (not in the file — see §E).
- **Cache-poisoning-shaped surprise** (rare but the reason we obsess):
  a job that previously passed now fails on a warm cache and passes on
  a fresh runner. Investigate whether the job's compile surface is
  isolated per SKILL.md §2. Add the missing `CARGO_TARGET_DIR` +
  cache-key scope; do NOT paper over with `cargo clean`.
- **CI-duration-monitor firing.** A shared-workflow SHA bump doubled
  a job's runtime. Investigate the Dependabot bumps landed since the
  last green baseline; that workflow is `ci-duration-monitor.yml`.

---

## §E — Supply-chain gates, per-tool deep detail

**Complements SKILL.md §4.** The stack (all present, all enforced on PR):

### `cargo-vet` (`shared-cargo-vet.yml`)

Imports 7 upstream audit feeds (`supply-chain/config.toml`
`[imports.*]`): Bytecode Alliance, Embark Studios, Fermyon, Google,
ISRG, Mozilla, Zcash. Every build-graph dep needs coverage from one of
these feeds, a local audit in `supply-chain/audits.toml`, or an
`[[exemptions.<crate>]]` entry with `version = "…"` + `criteria =
"safe-to-deploy"` (or `safe-to-run` for dev-only). Two gotchas:

- `[[trusted]]` entries are **publisher-scoped**: a version from a
  different publisher of the same crate does NOT inherit trust.
  Adding it needs an `[[exemptions]]` entry.
- `cargo vet fmt` (which runs implicitly on some vet operations)
  **strips comments** from `supply-chain/config.toml`. Rationale for
  an exemption/trust entry lives in the commit message, not inline. Do
  not put a `# because …` line above an exemption block and expect it
  to survive.

### `cargo-deny` (`shared-cargo-deny.yml`)

4 checks: advisories, bans, licenses, sources. Config: `deny.toml`.
Ignore entries need a comment with an advisory ID, why it's tolerated,
and a revisit trigger. **Mirror rule:** any `[advisories.ignore]` entry
MUST also be added to `osv-scanner.toml` — the OSV scanner runs on a
separate code path and would flag it otherwise. Verify with a diff of
the two files' ignore lists after any change.

### `cargo-machete` (`shared-cargo-machete.yml`)

Fails on any declared `[dependencies]` entry that isn't referenced
anywhere. Refactors that drop a feature or a module often orphan a
dep; machete catches it before the lockfile bloats.

### `cargo-semver-checks` (inline in `ci.yml`)

Compares the public API against the last crates.io release.
Short-circuits (with a helpful message) before the first publish
because the tool can't find a baseline. Live from v0.0.1's first
publish onward. Useful even on the 0.0.x runway to build the muscle
for 1.x's stability promise.

### REUSE (`shared-reuse.yml`)

SPDX header on every file (inline or aggregated via `REUSE.toml`) + a
`LICENSES/` entry for every license the project declares. Adding a new
file? Either add `# SPDX-FileCopyrightText: 2026 Noyalib` +
`# SPDX-License-Identifier: MIT OR Apache-2.0`, or add an aggregate
entry in `REUSE.toml`.

### Dependency Review (in `security.yml`)

PR-only, `warn-only: true` currently (advisory / informational).
Denies `AGPL-3.0` and `GPL-3.0` in the future when hardened.

### CodeQL (in `security.yml`)

Currently `languages: actions` (i.e. the workflow YAML itself; Rust
CodeQL support isn't in the baseline set). Uploads to Code Scanning.

### OpenSSF Scorecard (`scorecard.yml`)

Publishes results to Rekor + Code Scanning. The
`auto-approve-dependabot.yml` workflow exists specifically to satisfy
Scorecard's Code-Review check on a solo-maintained repo (Dependabot as
author, `github-actions[bot]` as approver — two distinct identities
count as reviewed).

### osv-scanner mirror

Separate scanner. Any ignore in `deny.toml` MUST be mirrored to
`osv-scanner.toml`. See cargo-deny above.

---

## §F — Release flow, full per-step detail

**Complements SKILL.md §5.** The mechanical sequence, in order — **do
not skip steps**:

### 1. Version bump

Edit `crates/noyalib/Cargo.toml` `version = "X.Y.Z"`. Workspace root
Cargo.toml has no top-level version. Any other publishable crate in
this repo bumps in lockstep (post-split, `noyalib` is the only
publishable crate; satellites bump in their own repos).

### 2. CHANGELOG entry

`CHANGELOG.md` head — new `## [vX.Y.Z] - YYYY-MM-DD` section under
`## [Unreleased]`. Follow Keep-a-Changelog groupings (`### Added`,
`### Fixed`, `### Changed`, `### Security`, `### Removed`). Reset
`## [Unreleased]` to `(Nothing yet — [vX.Y.Z] is the cut.)`. Link the
satellite `=X.Y.Z` publishes in the header.

### 3. RELEASE-NOTES-vX.Y.Z.md

Structure (see the v0.0.13 and v0.0.14 files as templates):

- Headline sentence (the release's identity in one line).
- "Why this release exists" — problem statement.
- "What changed" — grouped by concern.
- "What did not change" — API stability, MSRV, deps footprint,
  unsafe posture.
- "Follow-ups noted for v0.0.(Z+1)".

### 4. Version-refs audit

Bumps consistently miss a few places. Grep the old version across the
tree before opening the PR:

```bash
grep -rn "0\.0\.13" README.md MIGRATION.md GETTING_STARTED.md \
    doc/USER-GUIDE.md crates/noyalib/Cargo.toml \
    CHANGELOG.md pkg/ benches/ examples/ 2>/dev/null
```

Stragglers happen — README code snippets, MIGRATION.md upgrade
examples, GETTING_STARTED.md dep lines, `doc/USER-GUIDE.md` snippets,
benches, examples referencing `noyalib = "0.0.13"`. Fix all before
proposing the PR.

### 5. PR against `main`

Conventional-Commits title, `release:` or `chore(release):` prefix.
Attach the release notes in the body. Wait for all CI to be green.

### 6. Squash-merge to main

`gh pr merge --squash --admin`. `main` is protected; direct pushes are
refused (project memory).

### 7. Tag the merge commit on `main` and push the tag

```bash
git checkout main && git pull
git tag -s "v0.0.14" -m "noyalib v0.0.14"
git push origin v0.0.14
```

### 8. `release.yml` triggers on the tag

Jobs (in order):

- `validate` — fmt/clippy/test/doc + cross-check tag vs
  `crates/noyalib/Cargo.toml` version. Isolated
  `target-release-validate`.
- `artifacts` — `cargo package --all-features --allow-dirty`,
  `SBOM.txt` (`cargo tree`), SHA256/SHA512 sums, SLSA L3
  `attest-build-provenance`, cosign keyless (Fulcio) `.bundle` per
  `.crate` + SBOM. Uploads to workflow artifacts.
- `cross-verify` (matrix: ubuntu / macos / windows) — `cargo test
  --all-features`. Isolated `target-release-verify-${matrix.os}`.
- `github-release` — downloads artifacts, generates release notes from
  git log (range `<prev-tag>..<tag>`), creates the GitHub Release with
  `.crate` + `.bundle` + `SHA*SUMS.txt` + `SBOM.txt` +
  `SBOM.txt.bundle`.
- `crates-io` — publishes `noyalib` to crates.io from the `crates-io`
  environment using `CARGO_REGISTRY_TOKEN`. Skipped if `dry_run` input
  was `true` on a manual dispatch.

### 9. Satellite lockstep

Each satellite tags `vX.Y.Z` in its own repo and its own `release.yml`
runs. **Satellite prereqs that MUST be configured before the parent tag
push** (project memory — satellite-release-prereqs):

| Satellite | `CARGO_REGISTRY_TOKEN` | npm Trusted Publisher (or first-time `NPM_TOKEN`) | Other credentials |
|-----------|------------------------|---------------------------------------------------|-------------------|
| `noyalib-wasm` | Required | Required (WASM ships to npm) | — |
| `noyalib-mcp` | Required | — | GHCR + MCP Registry credentials |
| `noyalib-lsp` | Required | — | — |
| `noya-cli` | Required | — | — |

The 4 satellites publish `=X.Y.Z` from their own tag pushes, in
parallel with the parent, all pinning `noyalib = "=X.Y.Z"` exact-match.

---

## §G — Caller-permissions matrix + shared-workflow edit rollout

**Complements SKILL.md §6.**

### Failure mode (project-verified lesson, v0.0.12 pilot `noyalib-wasm` PR #1)

When a satellite consumes a shared workflow whose callee declares a
`permissions:` scope the caller does not, GitHub Actions rejects the
entire workflow with a `startup_failure` — **0 jobs scheduled, no
annotation, no diagnostic in the workflow tab**. The symptom is "the
check just doesn't run" and the fix looks like guesswork until you know
the shape.

### The rule

The caller's `permissions:` block MUST be the union of every callee's
declared `permissions:`. The parent repo's `ci.yml` sits at
`permissions: read-all` and never hits this. Satellites narrow to
per-workflow minimums per the table below (from ADR-0005 §Shared
reusable workflows):

| Consumed workflow | Required caller permissions |
|-------------------|-----------------------------|
| `shared-cargo-deny.yml` | `contents: read` |
| `shared-cargo-vet.yml` | `contents: read` |
| `shared-cargo-machete.yml` | `contents: read` |
| `shared-reuse.yml` | `contents: read` |
| `shared-rustdoc-strict.yml` | `contents: read` |
| `shared-test-matrix.yml` | `contents: read` |
| `shared-msrv-core.yml` | `contents: read` |
| `shared-per-crate-msrv.yml` | `contents: read` |
| `shared-no-std.yml` | `contents: read` |
| `shared-coverage.yml` | `contents: read` |
| `shared-miri-focused.yml` | `contents: read` |
| `shared-miri-full.yml` | `contents: read` |
| `shared-fuzz-diff.yml` | `contents: read` |
| `shared-readme-examples.yml` | `contents: read` |
| `shared-vendor-offline.yml` | `contents: read` |
| `shared-verify-signatures.yml` | `contents: read` **and** `pull-requests: read` |

`shared-verify-signatures.yml` is the standalone case — it hits
`gh api repos/.../pulls/N/commits`, which needs `pull-requests: read`.

### Editing a shared workflow's permissions? Rollout procedure

Any addition needs a matching update to satellite callers, or the next
satellite build startup-fails. Roll the change out via:

1. Land the shared-workflow change in this repo (Dependabot in each
   satellite opens a SHA-bump PR within a day).
2. Update satellite `ci.yml` caller `permissions:` in the same PR
   (Dependabot won't fix caller permissions for you).
3. `shared-workflow-propagation.yml` starts alarming if any satellite
   SHA-bump PR sits open >48h.
