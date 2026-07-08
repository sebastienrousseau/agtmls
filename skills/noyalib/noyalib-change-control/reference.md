# noyalib-change-control — Reference material

Complements `SKILL.md` in the same directory. Load this when you need the
exhaustive change-classification table, the full CI gate inventory, the
long-form v0.0.9 → v0.0.11 cache-poisoning narrative, or the jargon
glossary. `SKILL.md` keeps the rulebook (non-negotiables, unwritten laws,
review flow); this file keeps the reference matter.

Volatile facts date-stamped **2026-07-08**, release branch
**`feat/v0.0.14`**. Re-verify against source with the one-liners in
`SKILL.md` § *Provenance and maintenance* (that section covers both
files).

---

## R1. Jargon glossary

Defined once, used throughout both `SKILL.md` and this file.

- **ADR** — Architecture Decision Record, a numbered markdown file in
  `doc/adr/` (template at `doc/adr/TEMPLATE.md`).
- **MSRV** — Minimum Supported Rust Version. `noyalib` core **1.85.0**
  (`crates/noyalib/Cargo.toml` `rust-version = "1.85.0"` is
  authoritative; `doc/POLICIES.md` §1 and `CONTRIBUTING.md` still
  say 1.75.0 — those are stale, not a core-vs-satellite split);
  satellites (`noya-cli`, `noyalib-lsp`, `noyalib-wasm`) **1.85.0**.
- **Release branch** — the long-lived `feat/v0.0.X` branch PRs target.
  Currently `feat/v0.0.14` (2026-07-08).
- **Non-negotiable** — a rule that fails CI or fails review, period.
- **Satellite crate** — a `noyalib-*` crate other than `noyalib` core:
  `noyalib-wasm`, `noyalib-mcp`, `noyalib-lsp`, `noya-cli`. Post
  workspace split (ADR-0005, v0.0.12–13) they ship from their own
  repos in strict `=X.Y.Z` lockstep.

---

## R2. Full change-classification table

`SKILL.md` §1 keeps a compact 3-row summary. The complete 9-row taxonomy
lives here. Every change belongs to exactly one row — pick the row before
you write code, because the row tells you which gates you must satisfy
and whether an ADR is required.

| Class | Trigger | Branch prefix | ADR required? | Extra gates beyond default |
|---|---|---|---|---|
| **Bug fix** | Observable-behaviour bug against YAML 1.2, docs, or a documented API contract. | `fix/` | No | Regression test in same commit. |
| **Feature** | New user-visible behaviour or new public API surface. | `feat/` | **Yes** — parse-output shape, public API, feature-flag shape. | Design discussion in an Issue first; changelog entry; example in `crates/noyalib/examples/` if adding a public entry point. |
| **Security / DoS fix** | CVE, RUSTSEC, resource-limit bypass, panic on untrusted input, supply-chain issue. | `fix/` (private disclosure path per `SECURITY.md`; do not open a public issue) | Yes if it changes the parser's accept set or introduces a new limit knob. | Regression test that fires the guard; explicit changelog note under "Security". Fix beats every unrelated deadline (see `SKILL.md` §3 unwritten law e). |
| **Restructure / refactor** | Rename module, move file, extract helper — no behaviour change intended. | `refactor/` | Yes if it changes public re-exports, the feature-flag matrix, or workspace `members =`. | Reviewer sees a diff that reads as pure motion; behaviour tests unchanged. Big Move rule: file-moves-only commit, no formatting, no comment edits (PLAN.md § Locked decisions row *Restructure cadence*) so `git blame --follow` stays sharp. |
| **Release** | Version bump, changelog roll, tag prep. | `feat/v0.0.<next>` (the release branch itself) | No (unless the release lands an ADR-worthy change, in which case that ADR lands *inside* the release). | The full "release audit" checklist in `SKILL.md` §5. All satellites checked for stale version refs. |
| **CI / build / packaging** | Workflow, toolchain pin, wrangler for build tooling. | `ci/` | Yes if it changes the required-checks set. | Every new specialised cargo job **MUST** set its own `CARGO_TARGET_DIR` (see R4 cache-poisoning incident). |
| **Docs only** | Prose, examples, docstrings; no compiled behaviour change. | `docs/` | No. Exception: `docs/adr/*` is itself an ADR. | Doctests still run under `docs-strict`. Fabricated example code is a P0 — every code block gets tried locally before commit (`SKILL.md` §2 non-negotiable *no fabrication*). |
| **Dependency bump** | Cargo dep add / bump / drop. | `chore/` (or Dependabot) | Yes only if the bump crosses MSRV, drops a feature, or changes the transitive `unsafe` surface. | One-line rationale in commit body per `CONTRIBUTING.md` § *Code standards*; `cargo vet`, `cargo deny`, `cargo audit` all pass. |
| **Performance** | Speedup with no observable behaviour change. | `perf/` | Yes if the win depends on a new `unsafe` (rejected — see ADR-0003), a new SIMD path, or a public API to opt into it. | Criterion benchmark in the same PR — see `SKILL.md` §3 unwritten law g. |

> **When in doubt on ADR:** CONTRIBUTING.md gives the litmus test —
> *"would I want a future contributor to read this before proposing the
> opposite?"* If yes, ADR. If no, commit message suffices.

---

## R3. Complete CI gate inventory

`SKILL.md` §5 tells the reviewer that every `jobs:` entry in
`.github/workflows/ci.yml` must pass. This section enumerates the
current gate set (2026-07-08, release branch `feat/v0.0.14`). Treat this
as inventory, not doctrine — re-derive from `ci.yml` if the pipeline has
moved on:

```sh
grep -nE '^\s{2}[a-z][a-z0-9-]*:$' .github/workflows/ci.yml
```

Current gates:

- `ci` — Rust CI: clippy `-D warnings`, fmt, `cargo audit`.
- `test-matrix` — os × toolchain product matrix.
- `miri-focused` — Miri over a curated hot-path set.
- `miri-full` — Miri over the full library test suite.
- `cargo-deny` — licence + advisory + ban policy.
- `fuzz-diff` — fuzz differential against reference corpora.
- `cargo-semver-checks` — public-API diff (activates once the crate is
  on crates.io).
- `cargo-vet` — supply-chain audit against the vetted exemptions.
- `cargo-machete` — unused-dependency check.
- `reuse-lint` — SPDX / licence-header compliance.
- `msrv-1-85-core` — three sub-checks (no_std, default, clippy), each
  in its own isolated `CARGO_TARGET_DIR`.
- `coverage-gate` — floor: fn 96 / line 94 / region 93.
- `vendor-build` — offline vendored build reproduction.
- `msrv-per-crate` — each workspace member re-checked at its declared
  `rust-version` floor.
- `no-std` — noyalib core built with `--no-default-features`, exercising
  the `alloc`-only surface.
- `readme-examples` — every README code block compiled and run.
- `docs-strict` — rustdoc with strict lints (`-D rustdoc::all`) plus
  doctests.
- `verify-signatures` — commit-signature check against the merge base.
- `lossless-u64-matrix` — two legs, both with isolated
  `CARGO_TARGET_DIR` (see R4).

If any of the above is red on your PR, apply `SKILL.md` §3 unwritten law
(a): fix in this session.

---

## R4. v0.0.9 → v0.0.11 cache-poisoning incident — long form

`SKILL.md` §4 keeps a 3-line summary and cross-references
`noyalib-failure-archaeology`. This section keeps the long-form narrative
so a reviewer of a `ci/` PR (or a future maintainer wondering why every
specialised job carries its own `CARGO_TARGET_DIR`) can read the whole
story in one place.

### R4.1 What happened

For two full releases (v0.0.9 shipped, v0.0.10 shipped), the
`no_std (alloc-only) build` CI job reported green in ~1.89s while
`cargo check -p noyalib --no-default-features --lib --locked` from a
clean target dir actually failed with **8 errors**:
`crates/noyalib/src/doc_boundary.rs` used `Vec` / `vec![]` without
importing them from `crate::prelude`. Those symbols are reachable under
`std` (via the prelude) but not under `no_std`. Real regression.

### R4.2 Why CI missed it

Every other job in the pipeline runs `--all-features` (or `--default`),
populates the workspace-default `target/`, and the shared
`Swatinem/rust-cache` action then served the no_std job a
matching-fingerprint **cache hit** without exercising the no_std code
path. The gate was cache-poisoned — the "success" verdict was about the
cache, not the code. Two releases sat on top of the poison before the
regression surfaced.

### R4.3 Verification trail

```sh
git log --all --oneline --grep='cache-poisoning' -i
```

Points at the run of commits under PR #124 *"release: v0.0.11 (CI
integrity + no_std fix + strict rustdoc PR gate + cache-poisoning guard
+ …)"*. Full narrative in `RELEASE-NOTES-v0.0.11.md` §*Why this release
exists*.

### R4.4 The rule that came out of it

Mandatory for every new specialised CI job. Every workflow whose cargo
invocation uses a non-default feature set or non-default toolchain
**MUST**:

1. Set an isolated `CARGO_TARGET_DIR`
   (e.g. `${{ github.workspace }}/target-<job-name>`).
2. Pass a scoped `Swatinem/rust-cache` namespace matching the target
   dir (`workspaces:` + `key:`).

Verify the current CI already applies this discipline:

```sh
grep -n CARGO_TARGET_DIR .github/workflows/ci.yml
```

Live examples in `ci.yml`: `lossless-u64-matrix` sets
`target-lossless-u64-<leg>`; the shared `no-std`, `docs-strict`,
`miri-focused`, `miri-full`, `coverage-gate`, `msrv-per-crate`, and
`readme-examples` jobs each carry their own isolation inside their
shared workflow file.

### R4.5 What "CI green" means now

"CI green" now means "green from a clean fingerprint." A green verdict
from a shared-cache fingerprint hit is not evidence — the gate has to
actually rebuild in isolation to count. This is why every new
specialised CI job in this repo sets its own `CARGO_TARGET_DIR`, and
why a reviewer of a `ci/` PR checks for that isolation before
approving.

### R4.6 Cross-reference

For related failure archaeology (community-PR takeover fumbles, release-
audit misses, prior CI regressions), see the sibling skill
`noyalib-failure-archaeology`. This section is the canonical write-up
for the cache-poisoning strand specifically.

---

## R5. Zero-`unsafe` policy — full exemption list and escape guidance

Cross-refs `SKILL.md` §2.1. The compact rule is `#![forbid(unsafe_code)]`
at every crate root, workspace-wide, and no escape hatch. Detail:

- **No profile relaxes it.** Not `dev`, not `release`, not `bench`,
  not `test`, not any custom profile. `forbid` is a lint attribute
  applied at crate root; profiles do not override lint attributes.
- **No crate is exempt.** Every workspace member — `noyalib` core,
  `xtask`, `noyalib-wasm`, `noya-cli`, `noyalib-lsp`, `noyalib-mcp`,
  benchmarks, examples — carries the attribute. New crates added to
  the workspace must carry it before their first commit lands.
- **"But I need `unsafe` for X"** — no. The workspace has already
  vetted `memchr` (SIMD byte-search), `smallvec` (inline-storage
  vectors), `bytemuck` (safe transmute), `zerocopy` (safe casts),
  and a small handful of others precisely so contributors never need
  to reach for `unsafe`. If your use case isn't covered by an
  already-vetted dep, open an ADR proposing a new vetted dep — not
  a `#[allow(unsafe_code)]`.
- **ADR precedent.** The `forbid`-vs-`deny` choice is spelled out in
  `doc/adr/0003-zero-unsafe-policy.md` §*Alternatives considered →
  deny(unsafe_code) instead of forbid*. Read it before proposing any
  relaxation.

---

## R6. MSRV — stale-drift diagnosis and adoption backstory

Cross-refs `SKILL.md` §2.6. The compact rule is: core MSRV bump is a
minor-version event; current floor 1.85.0 authoritative in
`crates/noyalib/Cargo.toml`. Detail:

### R6.1 Stale-drift map

Two files still cite the old floor and will confuse a first-time
reader:

- `doc/POLICIES.md` §1 — cites 1.75.0. Stale.
- `CONTRIBUTING.md` — cites 1.75.0 in the toolchain section. Stale.

Diagnose with:

```sh
grep -n rust-version crates/noyalib/Cargo.toml         # authoritative: 1.85.0
sed -n '34,58p' doc/POLICIES.md                        # shows the stale 1.75.0
```

This is **drift**, not a deliberate core-vs-satellite split. A future
docs-only PR should reconcile the prose files with the manifest; until
then, treat the manifest as ground truth.

### R6.2 Why the 1.85.0 floor

The 1.85.0 floor arrived with `edition = "2024"`. `edition = "2024"`
requires a 1.85+ toolchain, and the workspace opted into the new
edition deliberately (ADR track, see release notes for the release
that bumped edition).

### R6.3 Adoption backstory — why we treat bumps as breaking

Enterprise / RHEL / FIPS shops on older toolchains had adopted
`noyalib` on the earlier 1.75.0 promise. The 1.85.0 bump was a
deliberate, versioned move that gave those shops a semver signal to
pin against. Any further bump gets the same minor-version treatment —
this is the contract that keeps enterprise adopters willing to depend
on `noyalib` at all.

---

## R7. Unwritten laws — rationale and worked-example prose

Cross-refs `SKILL.md` §3. The rule statements live there; the "why"
and the historical worked-example for each law lives here.

**(a) Same-session green — rationale.** The fix is cheapest while the
change is in your head; deferred red rot normalises broken windows.
Every hour a red job sits open, another PR piles on top and the
diagnosis surface widens.

**(b) Version-refs audit — rationale.** Users copy install snippets
from the README; a stale version renders on crates.io and confuses
adoption. The version string appears in more places than intuition
suggests — the enumerated sweep list in `SKILL.md` §3 (b) exists
because every prior release found at least one straggler.

**(c) `main` protected — rationale.** Uniform gate = uniform history.
A single "just this once" direct push breaks the guarantee that every
`main` commit has been through CI, and once broken the guarantee is
gone for good — no post-hoc audit can restore it.

**(d) No pre-emptive phasing — rationale.** Splitting a promised-
complete release erodes trust. If the maintainer said "v0.0.11 is the
CI-integrity release," landing half the CI fixes in v0.0.11 and half
in "v0.0.12 next week" reframes v0.0.11 as incomplete after the
promise — worse than if the release had never been promised complete.

**(e) Security > velocity — rationale.** Shipping known-broken costs
more downstream than shipping late costs upstream. Every downstream
crate that pulls in a known-broken `noyalib` release inherits the bug;
holding the release for 24 hours costs upstream one changelog reroll
and one recut.

**(f) Community-PR takeover — worked examples.** This is how
`feat(lossless-u64)` #117 landed as `bbf0b9c` (canardleteer's PR
rebased and merged with authorship preserved) and how the `zoosky`
fix landed via v0.0.13 (`a472e14`). The takeover protocol — never
leave to rot, never merge unreviewed, always credit — is what keeps
external contributors sending PRs at all.

**(g) No perf claim without Criterion — rationale.** Perf claims
outlive the PR; context (CPU, corpus, feature flags) evaporates fast.
A number in the README that nobody can reproduce six months later is
worse than no number at all — it undermines every other README claim
by proxy.

**(h) Scripts, not snippets — rationale.** A fenced ```bash block in
chat is a copy-paste instruction, not a script. Copy-paste breaks on
quoting, line wraps, and IDE auto-formatting; a script file on disk
with `set -euo pipefail` fails loudly at the first broken step.
Signed-commit flows, in particular, need the maintainer's ssh-agent
which the tool cannot reach — so the tool writes the script and the
maintainer runs it.
