---
name: noyalib-build-and-env
description: Recreate a working noyalib development environment from scratch on a fresh machine, resolve toolchain / MSRV / "command not found" errors, and avoid the known Apple-Silicon, no_std, and workspace-boundary traps. Load when a new engineer or AI session is bootstrapping, when `cargo build`, `cargo test`, `make`, cargo-fuzz, Miri, or coverage runs fail before the code is even in scope, or when the answer is "install X" / "run from repo root" / "use `--target aarch64-apple-darwin`".
---

# noyalib — build & environment

Date-stamped 2026-07-08. noyalib is at v0.0.14 on branch `feat/v0.0.14`.

Purpose: recreate the working environment from scratch on a new
machine, and know every trap that has bitten past sessions.

Sibling skills — do not duplicate them here:
- CI internals, release plumbing, shared-workflow SHA pinning → `noyalib-ci-and-release`.
- Running benches / fuzzers / coverage in anger → `noyalib-diagnostics-and-tooling`.

## Provenance (verified 2026-07-08)

```sh
$ cat rust-toolchain.toml
[toolchain]
channel = "stable"
components = ["rustfmt", "clippy"]

$ grep rust-version crates/noyalib/Cargo.toml
rust-version = "1.85.0"

$ grep edition crates/noyalib/Cargo.toml | head -1
edition = "2024"
```

`Cargo.toml` is the authoritative MSRV. `CONTRIBUTING.md` still
says "Rust 1.75.0+ for the core crate" — that is stale, ignore it
(the real floor moved to 1.85.0 when edition-2024 landed).

## 1. Toolchain

### Stable (default channel from `rust-toolchain.toml`)

Rustup picks this up automatically the first time you `cd` into
the repo:

```sh
rustup show          # verifies the stable pin + components
rustc --version      # >= 1.85.0 required by edition 2024 + rust-version
```

Components pulled in by `rust-toolchain.toml`: `rustfmt`, `clippy`.

### Nightly (required for specific tasks)

Install once, then pin nothing — the scripts spell `cargo +nightly`
explicitly:

```sh
rustup toolchain install nightly --profile minimal
rustup component add --toolchain nightly rust-src rustfmt clippy \
                                          llvm-tools-preview miri
```

Nightly is needed for:

- `make miri` / `make miri-full` / `make miri-bigendian` (Stacked
  Borrows + strict-provenance verification of unsafe deps —
  noyalib itself forbids unsafe).
- `make coverage-gap` and `./scripts/coverage-gap-report.sh`
  (`cargo +nightly llvm-cov` with the workspace threshold gate).
- `cargo +nightly fuzz run …` (cargo-fuzz needs a nightly rustc).
- The `nightly-simd` cargo feature (`core::simd` / `portable_simd`
  is still unstable).

### Extra targets worth having

```sh
rustup target add wasm32-unknown-unknown
```

The `shared-no-std.yml` bare-metal proof runs
`cargo check --no-default-features --lib --target wasm32-unknown-unknown`.
Add this target locally so you can reproduce the exact CI leg.

## 2. Extra tooling inventory

Each of these is invoked by the Makefile, a script under
`scripts/`, or a workflow under `.github/workflows/`. Install with
`cargo install --locked <name>` unless noted.

| Tool                | Invoked by                                                       | Purpose                                             |
|---------------------|------------------------------------------------------------------|-----------------------------------------------------|
| `cargo-deny`        | `make deny`, `shared-cargo-deny.yml`                             | License / advisory / source supply-chain gate.      |
| `cargo-vet`         | `shared-cargo-vet.yml`                                           | Auditable dep-trust chain; exemptions in `supply-chain/`. |
| `cargo-machete`     | `shared-cargo-machete.yml`                                       | Detects unused dependencies.                        |
| `cargo-semver-checks` | `ci.yml` (pre-publish gate)                                    | Blocks accidental SemVer breaks.                    |
| `cargo-about`       | `make notice` (auto-installs on demand)                          | Regenerates the NOTICE file for release tarballs.   |
| `cargo-llvm-cov`    | `make coverage-gap`, `shared-coverage.yml`                       | Nightly-only coverage engine.                       |
| `cargo-fuzz`        | `security.yml`, ad-hoc local runs                                | libFuzzer harness for `fuzz/` targets.              |
| REUSE tool          | `shared-reuse.yml` (via `fsfe/reuse-action` in CI)               | SPDX header + `REUSE.toml` compliance.              |

Local install of REUSE for offline checks: `pipx install reuse`.

`actionlint` is **not** wired into this repo (no config, no
workflow). Do not add it as part of a build fix — file a separate
proposal instead.

## 3. First-build sequence

From a fresh clone on a machine that already has rustup + git
signing configured:

```sh
git clone https://github.com/sebastienrousseau/noyalib.git
cd noyalib

# rustup auto-installs the stable channel per rust-toolchain.toml
cargo build -p noyalib

# Full test suite: 3,686 tests + ~431 doctests. Expect ~110s on
# M-series Apple Silicon on a warm cache.
cargo test -p noyalib

# Full local gate (check + clippy + test).
make all
```

Then optionally:

```sh
make fmt              # rustfmt --check
make deny             # supply-chain gate
make doc              # rustdoc, --no-deps --all-features
```

## 4. Makefile map

Verified against the checked-in `Makefile`. Every target below
exists in that file; one line each.

| Target             | What it does                                                                  |
|--------------------|-------------------------------------------------------------------------------|
| `all` (default)    | Runs `check`, `clippy`, `test` in sequence — the local pre-push gate.         |
| `check`            | `cargo check --all-features --all-targets`.                                   |
| `clippy`           | `cargo clippy --all-features --all-targets`.                                  |
| `test`             | `cargo test --all-features`.                                                  |
| `compliance`       | Runs the YAML-compliance integration test with `--nocapture`.                 |
| `fmt`              | `cargo fmt --check` (does not rewrite; use `cargo fmt` for that).             |
| `deny`             | `cargo deny check` — licenses + advisories + sources.                         |
| `doc`              | `cargo doc --no-deps --all-features`.                                         |
| `miri`             | Focused Miri suite via `scripts/miri.sh` (nightly).                           |
| `miri-full`        | `cargo +nightly miri test --lib` — full slow pass.                            |
| `miri-bigendian`   | Same as `miri` but with `MIRI_TARGET=mips64-unknown-linux-gnuabi64`.          |
| `sbom`             | Emits `SBOM.txt` via `cargo tree --edges normal`.                             |
| `notice`           | Regenerates NOTICE via cargo-about; auto-installs cargo-about if absent.      |
| `vendor`           | `cargo vendor --versioned-dirs vendor` for offline / FIPS builds.             |
| `vendor-build`     | Full sanity: vendors, writes `.cargo/config.vendor.toml`, builds `--offline`. |
| `msrv-per-crate`   | `./scripts/msrv-per-crate.sh` — installs each crate's declared MSRV and checks. |
| `coverage-gap`     | `./scripts/coverage-gap-report.sh` — prints files below the threshold (default 98%). |
| `examples`         | Runs the curated example roster sequentially, red/green per line.             |
| `clean`            | `cargo clean`.                                                                |

## 5. Known traps (each verified in-repo)

### (a) cargo-fuzz on Apple Silicon

cargo-fuzz's default target is `x86_64-apple-darwin`. On M-series
Macs that target is usually *not* installed, and the failure mode
is a cryptic linker error before any fuzz work runs. Always spell
the target explicitly:

```sh
cargo +nightly fuzz run fuzz_parse --target aarch64-apple-darwin
```

Applies to every target in `fuzz/fuzz_targets/` (`fuzz_parse`,
`fuzz_roundtrip`, `fuzz_from_value`, `fuzz_multi_doc`,
`fuzz_strict`, `fuzz_diff`, `fuzz_borrowed_alias`,
`fuzz_yaml_v1_1`, `fuzz_double_quoted`, `fuzz_no_span_loader`).

### (b) `cd fuzz/` leaves you in a non-workspace manifest

The root workspace excludes `fuzz` (see `Cargo.toml`,
`exclude = ["crates/noyalib/examples/wasm", "fuzz"]`). Once your
shell is inside `fuzz/`, workspace-scoped commands break with:

> `requires dev-dependencies and is not a member of the workspace`

Rule: run `cargo bench`, `cargo test`, `cargo check`, `cargo doc`
from the repo root using `-p noyalib`, not from `fuzz/`. Only
`cargo +nightly fuzz …` should be run with `fuzz/` context, and
even then via the cargo-fuzz plumbing rather than a bare `cd`.

### (c) MSRV job cannot use `--all-features`

Optional deps like `miette`, `garde`, and the ICU-driven schema
validators declare higher rustc floors than 1.85.0. That is why
the shared MSRV workflow (`shared-msrv-core.yml`) intentionally
splits its legs into `--no-default-features --lib`, default-features
`cargo check`, and `cargo clippy --lib` — never `--all-features`.
If you catch yourself adding `--all-features` to an MSRV job you
are about to break the release. Feature-matrix `--all-features`
verification lives in `shared-test-matrix.yml` on stable.

### (d) no_std local check must use an isolated CARGO_TARGET_DIR

The `Swatinem/rust-cache` + shared `target/` combination can serve
a stale-but-passing fingerprint from a previous `std`-on `cargo
check`, masking real no_std regressions (this is exactly the
cache-poisoning bug that hid missing imports in `doc_boundary.rs`
and `de.rs` through v0.0.9–v0.0.10). Reproduce the CI leg locally:

```sh
CARGO_TARGET_DIR=/tmp/nostd \
    cargo check -p noyalib --no-default-features --lib --locked
```

For the bare-metal-grade proof (catches transitive deps silently
enabling `std` via feature unification):

```sh
CARGO_TARGET_DIR=/tmp/nostd-wasm \
    cargo check -p noyalib --no-default-features --lib --locked \
    --target wasm32-unknown-unknown
```

### (e) Commit hooks and signing

- The `commit-msg` hook (installed globally under
  `~/.config/git/hooks/`, not in-repo) appends the
  `Assisted-by: Claude:claude-opus-4-7` trailer. Commits made
  without that hook will still pass — the trailer is not enforced.
- CI **does** enforce signed commits via `shared-verify-signatures.yml`
  which iterates every PR commit and asserts a verified GPG/SSH
  signature. Always `git commit -S`. If a signed commit fails
  because the local ssh-agent is unreachable from a hosted
  session, hand the commit off to the user rather than dropping
  the `-S`.
- `main` branch protection additionally requires `required_signatures: true`.

### (f) Hand-run commands go into script FILES, not fenced blocks

If a session produces shell steps the maintainer must run themselves
(signed-commit flows where the AI's Bash tool cannot reach the local
ssh-agent, interactive prompts, anything destructive that needs eyes
first), hand them over as one runnable script file, not a
copy-pasteable fence:

- Write to disk under `.git/<name>.sh` for repo-local work, or an
  absolute path outside the tree.
- `chmod +x` and give the maintainer `./.git/<name>.sh` to invoke.
- Shebang `#!/usr/bin/env bash`; first body line
  `set -euo pipefail`.
- Quote heredocs (`<<'EOF'`) so commit messages don't interpolate.
- Normalise cwd up front:
  `cd "$(git rev-parse --show-toplevel)"` or an absolute path.
- One script per multi-phase job with labelled sections, not a
  chain of scripts.

A fenced ```bash block in chat is a copy-paste instruction, not a
runnable artefact. See `noyalib-change-control` §3(h) for the same
rule as project law.

## 6. Satellites live in separate repos

Since ADR-0005 (workspace split, v0.0.12–v0.0.13), the satellites
are their own GitHub repositories and are **not** under `crates/`
here:

- `noyalib-wasm` → https://github.com/sebastienrousseau/noyalib-wasm
- `noyalib-mcp`  → https://github.com/sebastienrousseau/noyalib-mcp
- `noyalib-lsp`  → https://github.com/sebastienrousseau/noyalib-lsp
- `noya-cli`     → https://github.com/sebastienrousseau/noya-cli

Do not `grep -r noyalib-mcp crates/` and conclude the satellite is
missing — it lives elsewhere and releases in strict lockstep at
the same `=0.0.X` version as this workspace. Note the stray
`crates/noyalib-wasm/` folder in the working tree contains only
generated artefacts (`Cargo.lock`, `pkg/`) and is not a workspace
member (see the `exclude` list in the root `Cargo.toml`).

The workspace is single-member (`members = ["crates/noyalib"]`);
`fuzz/` and `crates/noyalib/examples/wasm/` are the explicit
excludes. The `[workspace]` table is retained transitionally and
will collapse to a plain single-crate repo post-v0.0.14 per #134.

## 7. Fast fixes for common "command not found"

| Symptom                                                    | Fix                                                                 |
|------------------------------------------------------------|---------------------------------------------------------------------|
| `error: no such subcommand: 'deny'`                        | `cargo install --locked cargo-deny`                                 |
| `error: no such subcommand: 'about'`                       | `make notice` (auto-installs) or `cargo install --locked cargo-about` |
| `error: no such subcommand: 'llvm-cov'`                    | `cargo install --locked cargo-llvm-cov` + nightly + `llvm-tools-preview` |
| `error: no such subcommand: 'fuzz'`                        | `cargo install --locked cargo-fuzz` + nightly                        |
| `error: no such subcommand: 'vet'` / `'machete'` / `'semver-checks'` | `cargo install --locked cargo-<name>`                       |
| `error: component 'miri' … not installed`                  | `rustup component add --toolchain nightly miri rust-src`            |
| `error[E0658]: use of unstable library feature 'portable_simd'` | Switch off `nightly-simd` feature or use `+nightly`.            |
| Miri run reports stacked-borrows on memchr SSE2            | Expected false positive; `scripts/miri.sh` already sets flags to avoid it. |
| REUSE compliance failure locally                           | `pipx install reuse && reuse lint` from repo root.                  |

## 8. When to reach for a different skill

- CI-workflow structure, shared-workflow SHA pinning, release
  pipeline, Dependabot posture → **noyalib-ci-and-release**.
- Running benches (`cargo bench -p noyalib`), fuzz corpus
  triage, coverage percentage triage → **noyalib-diagnostics-and-tooling**.
- Editing shared-workflow files (they're consumed by satellites
  by SHA) → **noyalib-change-control**.
