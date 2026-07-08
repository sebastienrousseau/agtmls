# noyalib-build-and-env — reference material

Complements `SKILL.md` in this directory. Date-stamped 2026-07-08,
noyalib v0.0.14 on branch `feat/v0.0.14`. Load this when you need the
full tooling inventory, the complete Makefile target map, or the
"command not found" fast-fix table. `SKILL.md` keeps the toolchain
bootstrap, the first-build sequence, the known traps, and the
satellite topology; this file keeps the lookup tables.

Re-verify the tables against the checked-in `Makefile`, `scripts/`,
and `.github/workflows/` before trusting a row — the tree is truth.

---

## R1. Extra tooling inventory

Each of these is invoked by the Makefile, a script under `scripts/`,
or a workflow under `.github/workflows/`. Install with
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

---

## R2. Makefile map

Verified against the checked-in `Makefile`. Every target below exists
in that file; one line each.

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

---

## R3. Fast fixes for common "command not found"

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
