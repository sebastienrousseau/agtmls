---
name: noyalib-ci-and-release
description: |
  Load this when operating noyalib's CI or shipping a release. Covers the workflow
  graph (ci.yml orchestrator, shared-* reusables, security.yml, scorecard.yml,
  release.yml), THE cache-poisoning doctrine (isolated CARGO_TARGET_DIR per compile
  surface — the v0.0.9-v0.0.11 lesson), reading CI failures fast with gh, the
  supply-chain gate constellation (cargo-vet, cargo-deny, cargo-machete,
  cargo-semver-checks, REUSE, osv-scanner mirror rule), the tag-driven release flow
  (version bump → CHANGELOG → RELEASE-NOTES → version-refs audit → squash-merge →
  tag push → release.yml → satellite lockstep), and the shared-workflow
  caller-permissions trap (union callee scopes or the run startup-fails with 0 jobs,
  no annotation). Triggers: "CI is red", "release prep", "how do I tag", "cargo-vet
  failure", "cargo-deny advisory", "workflow permissions", "cache poisoning", "MSRV
  job broke", "satellite didn't publish". Sibling: noyalib-change-control (which
  gates apply). Date-stamped 2026-07-08; branch feat/v0.0.14.
---

# noyalib — CI and release runbook

> **See also `reference.md`** for the full workflow inventory (25 files),
> the exhaustive `ci.yml` job list, the `shared-no-std.yml` verbatim
> triad, the deep per-tool supply-chain detail, the `gh` cheat-sheet, the
> satellite lockstep matrix, and the caller-permissions table. This file
> keeps the doctrine and the compact runbook; reference.md holds the
> inventory.

Repo: `github.com/sebastienrousseau/noyalib` — pure-Rust YAML 1.2
library, `#![forbid(unsafe_code)]`, single-crate workspace after ADR-0005
splits (`noyalib-wasm` at v0.0.12, `noyalib-mcp` at v0.0.13, `noyalib-lsp`
+ `noya-cli` at v0.0.14+ per RELEASE-NOTES-v0.0.13.md). Current release
branch: `feat/v0.0.14`. Ground truth: `.github/workflows/*`, `Makefile`,
`supply-chain/config.toml`, `deny.toml`, `RELEASE-NOTES-v0.0.13.md`,
`RELEASE-NOTES-v0.0.14.md`, `doc/adr/0005-workspace-split.md`. If this
skill and those files disagree, the files win — re-verify with the
commands in "Provenance and maintenance" at the bottom.

Jargon (used everywhere below):

- **Orchestrator** — `.github/workflows/ci.yml` on push / PR / nightly.
- **Shared workflow** — a `.github/workflows/shared-*.yml` file with a
  `workflow_call:` trigger; consumed by the orchestrator via `uses:
  ./.github/workflows/shared-*.yml` and by satellite repos via
  `uses: sebastienrousseau/noyalib/.github/workflows/shared-*.yml@<sha>`.
- **Compile surface** — the tuple `(toolchain, features, target,
  RUSTFLAGS/RUSTDOCFLAGS, cfg gates, sanitiser)`. Two jobs that share a
  compile surface can share a target/; jobs that differ MUST NOT.
- **Satellite** — a downstream repo that publishes a `noyalib-*`
  crate at exact-match `=X.Y.Z` in lockstep with `noyalib`. Post-split:
  `noyalib-wasm`, `noyalib-mcp`, `noyalib-lsp`, `noya-cli`.

## 1. Workflow graph (at a glance)

Under `.github/workflows/` there are 8 non-shared workflows + 17
`shared-*` reusables = **25 total** (verified 2026-07-08). The
orchestrator `ci.yml` wires 19+ jobs — the local `shared-*` reusables,
one external `rust-ci.yml` reusable, and two inline jobs
(`cargo-semver-checks`, `lossless-u64-matrix`).

**Full inventory + per-workflow purpose + `ci.yml` job list are in
`reference.md` §A/§B.** Re-derive locally with:

```bash
ls .github/workflows/
grep -E '^  [a-z-]+:$' .github/workflows/ci.yml
```

Concurrency on `ci.yml`: `${{ github.workflow }}-${{ github.ref }}`
with `cancel-in-progress: true`.

## 2. THE cache-poisoning doctrine (v0.0.9-v0.0.11 lesson)

**The one commandment:**

> A green check is only trustworthy if its fingerprint cannot be
> satisfied by another compile-surface's artefacts.

Concretely: any job that compiles with a distinct feature set, distinct
target, distinct sanitiser, distinct MIRIFLAGS, distinct
RUSTDOCFLAGS, or a distinct `--cfg` — i.e. anything the Swatinem
cache key does not already discriminate — MUST set its own
`CARGO_TARGET_DIR` AND its own Swatinem `workspaces`/`key`. Belt and
braces: the `CARGO_TARGET_DIR` is the real guarantee; the cache key
prevents cross-restore on cold runners.

**How the incident manifested (v0.0.9 and v0.0.10):** the no_std leg
shared the default `target/` with `std`-on jobs. `cargo check
--no-default-features` on a warm Swatinem restore would find pre-built
artefacts from an earlier `std`-on job and short-circuit — silently
returning success while `crate::prelude::Vec` / the missing `vec`
import in `doc_boundary.rs` and the unused `crate::span_context` import
in `de.rs` remained broken. Two releases shipped with a broken no_std
surface before the v0.0.11 CI-integrity cut.

**Canonical exemplar** — `shared-no-std.yml`'s env/workspaces/key triad
is quoted verbatim in `reference.md` §C. The three isolating knobs are:

1. `env.CARGO_TARGET_DIR` moves the artefact dir off `target/`.
2. `workspaces: ". -> target-no-std"` points Swatinem at that dir.
3. `key: no-std` splits the cache namespace so cross-restore can't
   happen.

**Every job compiling a distinct surface follows the pattern.** Full
list of isolated dirs in `reference.md` §C. Verify with:

```bash
grep -rn "CARGO_TARGET_DIR" .github/workflows/ | head
```

When you add a new job, the check is: does it compile something with
inputs the default cache key can't tell apart from an existing job? If
yes, isolate. If in doubt, isolate — the cost is a cold rebuild, the
cost of a false green is a shipped bug (see v0.0.9 / v0.0.10).

## 3. Reading CI failures fast (triage)

Baseline loop (full `gh` cheat-sheet in `reference.md` §D):

```bash
gh pr checks <PR-number>
gh run list --branch feat/v0.0.14 --workflow ci.yml
gh run view --job <job-id>
```

**The three most-common failure classes** on this repo — check these
first before deep-diving:

1. **rustfmt drift** after hand-edits. `cargo fmt` before pushing; the
   external `ci` reusable runs `cargo fmt --check` and refuses on any
   drift. `make fmt` locally.
2. **clippy lints on a new nightly toolchain** (recent culprit:
   `byte_char_slices` promotion). Address the lint or gate with
   `#[allow(clippy::<lint>)]` under the specific `#[cfg]` — never
   blanket `-A` at the crate level.
3. **cargo-deny advisory landing mid-PR.** RustSec published a new
   entry between PR open and now. `cargo update -p <crate>` to a fixed
   version; if none exists, add a narrow `[advisories.ignore]` entry
   in `deny.toml` with a comment (advisory ID, why tolerated, revisit
   trigger) — **and mirror to `osv-scanner.toml`** (§4).

Full failure-class catalogue including the cache-poisoning shape and
the CI-duration-monitor firing is in `reference.md` §D.

## 4. Supply-chain gates (compact)

The stack, all enforced on PR: `cargo-vet`, `cargo-deny`,
`cargo-machete`, `cargo-semver-checks`, REUSE, Dependency Review,
CodeQL (`languages: actions`), OpenSSF Scorecard.

**The two rules that bite most often:**

- **cargo-deny ↔ osv-scanner mirror rule.** Any `[advisories.ignore]`
  entry in `deny.toml` MUST also land in `osv-scanner.toml` — OSV runs
  a separate code path and would otherwise flag it. Diff the two ignore
  lists after any change.
- **`cargo vet fmt` strips comments** from `supply-chain/config.toml`.
  Rationale for exemptions/trust entries goes in the **commit
  message**, not inline in the file.

Full per-tool detail (feed list, publisher scoping, semver-check
short-circuit, REUSE.toml aggregation, Scorecard's Code-Review
mechanism) in `reference.md` §E.

## 5. Release flow (compact 9-step)

**Doctrine before mechanics:**

- **Security > velocity.** A red security scan (Scorecard, cargo-deny
  advisory, CodeQL alert, cosign-verify) always trumps the release
  schedule. CI integrity IS a security control. Do not tag with a
  known-red gate; do not merge a workaround that dodges the gate for
  "release-day expedience".
- **Don't pre-emptively phase.** If the user framed this release as
  category-defining, fix the security / correctness / MSRV /
  version-refs stragglers in THIS release rather than deferring to
  `v0.0.(Z+1)`. Splitting a bang launch across two tags costs
  credibility that a slightly-later tag does not.

The nine steps, in order — **do not skip**:

1. **Version bump** — `crates/noyalib/Cargo.toml` `version = "X.Y.Z"`.
2. **CHANGELOG** — new `## [vX.Y.Z] - YYYY-MM-DD` under `## [Unreleased]`,
   Keep-a-Changelog groupings, reset `[Unreleased]`.
3. **RELEASE-NOTES-vX.Y.Z.md** — headline + why + what changed + what
   did not change + follow-ups (see v0.0.13/v0.0.14 as templates).
4. **Version-refs audit** — grep the old version across README,
   MIGRATION.md, GETTING_STARTED.md, `doc/USER-GUIDE.md`, Cargo.toml,
   CHANGELOG, `pkg/`, `benches/`, `examples/`. Fix all stragglers.
5. **PR against `main`** with Conventional-Commits title
   (`release:` or `chore(release):`); wait for all CI green.
6. **Squash-merge** via `gh pr merge --squash --admin` (`main` is
   protected; direct pushes refused).
7. **Tag and push** — `git tag -s "vX.Y.Z" -m "noyalib vX.Y.Z" && git
   push origin vX.Y.Z`.
8. **`release.yml` triggers** on the tag: validate → artifacts (SLSA
   L3 + cosign keyless) → cross-verify matrix → github-release →
   crates-io publish.
9. **Satellite lockstep** — each satellite tags `vX.Y.Z` in its own
   repo; all pin `noyalib = "=X.Y.Z"`.

Full per-step detail (release.yml job order, cosign bundle layout,
per-satellite prereq matrix incl. `CARGO_REGISTRY_TOKEN` and npm
Trusted Publisher requirements) in `reference.md` §F.

## 6. Shared-workflow caller-permissions trap (one-paragraph doctrine)

When a satellite consumes a shared workflow whose callee declares a
`permissions:` scope the caller does not, GitHub Actions rejects the
whole workflow with a `startup_failure` — **0 jobs scheduled, no
annotation, no diagnostic in the workflow tab.** The symptom is "the
check just doesn't run." The rule: **the caller's `permissions:` block
MUST be the union of every callee's declared `permissions:`.** The
parent `ci.yml` sits at `permissions: read-all` and never hits this;
satellites narrow to per-workflow minimums. `shared-verify-signatures.yml`
is the standalone case — needs `pull-requests: read` on top of
`contents: read` because it hits `gh api repos/.../pulls/N/commits`.
**Full caller-permissions matrix** and rollout procedure in
`reference.md` §G.

## 7. When NOT to use this skill

- Deciding whether a change belongs in this release, what its risk
  class is, whether it needs an ADR, whether it's `[Fixed]` vs
  `[Changed]` in the CHANGELOG → **`noyalib-change-control`**.
- Local toolchain / MSRV / build env setup, why `cargo +nightly` is
  required for coverage, how to run Miri locally →
  **`noyalib-build-and-env`**.
- Debugging parser / loader / CST correctness at the code level →
  **`noyalib-debugging-playbook`**.
- Editing README / MIGRATION / USER-GUIDE / RELEASE-NOTES prose →
  **`noyalib-docs-and-writing`**.

This skill is the runbook for the workflow files under
`.github/workflows/` and the shape of a release. It does not decide
what should be in a release or how the code inside should behave.

## Provenance and maintenance

Volatile facts date-stamped 2026-07-08 against noyalib v0.0.14 on
branch `feat/v0.0.14`. To re-verify before trusting anything in this
skill:

```bash
# The full workflow list this skill describes.
ls .github/workflows/

# The cache-poisoning-guard footprint. Every match should either be
# an env var setting or a documented reason for the pattern.
grep -rn "CARGO_TARGET_DIR" .github/workflows/ | head

# Jobs wired into the orchestrator (compare to reference.md §B).
grep -E '^  [a-z-]+:$' .github/workflows/ci.yml

# The 7 trusted audit feeds cargo-vet imports.
grep -E '^\[imports\.' supply-chain/config.toml

# The advisories that cargo-deny ignores + mirror to osv-scanner.
grep -A2 '^\[advisories\]' deny.toml
grep -B1 -A2 '^ignore' osv-scanner.toml 2>/dev/null

# The release-note templates to model the next one on.
ls RELEASE-NOTES-v0.0.*.md
```

If any of the workflow names, isolated-target-dir names, permission
tables, or release-flow steps drift from what these commands surface,
the files win — update this skill (and `reference.md`).
