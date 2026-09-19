<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# The AgtMLS Scorecard

Every repository in the AgtMLS ecosystem is held to the same bar: **10/10 in
ten categories**. This document defines what that means.

A previous commit in this repository was titled *"align repository with 10/10
gold standard"*. It shipped a CLI that crashed on `doctor`, `status` and
`evidence`, an installer that silently destroyed hand-written `CLAUDE.md`
files, a security analyzer that missed `curl | bash` inside a skill, and a
`make install` that produced a binary unable to run a single command. Every
one of those passed the gate.

That is the failure mode this document exists to prevent. A score is not a
claim a maintainer makes; it is a number a program computes. If a criterion
cannot be checked by a machine, it does not belong here — it belongs in a
review checklist, where its subjectivity is honest.

## How scoring works

- Each category has **10 criteria**, each worth **1 point**.
- A criterion is **binary**: the checker either proves it or it does not.
- `agtmls-scorecard score .` emits JSON; `--fail-under N` gates CI.
- **Unprovable is unscored.** A criterion that cannot be evaluated in this
  repository (no HTTP surface, no WASM target) is marked `n/a` and removed
  from both numerator and denominator. Marking something `n/a` requires a
  reason string that appears in the report.
- No criterion may be satisfied by asserting it in prose. "Documented" always
  means "documented *and* enforced", or it is not a criterion.

```
agtmls-scorecard score .            # human table
agtmls-scorecard score . --json     # machine report
agtmls-scorecard score . --fail-under 10 --category security
```

## 1. Correctness & Test Depth

| # | Criterion | How it is proven |
|---|---|---|
| 1.1 | Every public entry point is executed by a test | Entry points enumerated from the CLI/API surface; each must appear in a test invocation set |
| 1.2 | Coverage of the public surface ≥ 90% | `coverage.py` / `cargo-llvm-cov`, branch coverage |
| 1.3 | No test class, module or case is registered by hand | Loader must be discovery-based; a hand-maintained registry fails |
| 1.4 | Every bug fix lands with a test that fails without it | CI replays each `fix:` commit's test against its parent commit |
| 1.5 | Property/fuzz tests exist for every parser of untrusted input | `proptest`/`hypothesis` targets enumerated per parser |
| 1.6 | Zero `#[ignore]`, `@skip`, or commented-out tests without an issue link | Static scan |
| 1.7 | Error paths are tested, not only happy paths | Each `Err`/`raise` site reachable from a test |
| 1.8 | Golden outputs are byte-exact and regenerable | `--check` mode on every generator |
| 1.9 | Tests pass on the declared minimum and maximum runtime versions | CI matrix floor and ceiling both green |
| 1.10 | Mutation score ≥ 70% on core logic | `cargo-mutants` / `mutmut` |

## 2. Security & Supply Chain

| # | Criterion | How it is proven |
|---|---|---|
| 2.1 | All CI actions pinned to a full commit SHA | `zizmor` / Scorecard *Pinned-Dependencies* |
| 2.2 | No secret is available to any workflow triggered by `pull_request` | Static workflow analysis |
| 2.3 | Every dependency pinned with a hash; lockfile committed | `--require-hashes` / `Cargo.lock` / `uv.lock` |
| 2.4 | Release artifacts carry SLSA build provenance | `actions/attest-build-provenance`, verified in-workflow |
| 2.5 | Published to the registry users actually install from, via OIDC | PyPI/crates.io/npm Trusted Publishing, no long-lived token |
| 2.6 | SBOM validates against its own schema and covers every shipped path | `pyspdxtools` / `cyclonedx validate` + shipped-path diff |
| 2.7 | Commits and tags signature-verified in CI against a published key set | `git verify-commit` over the PR range |
| 2.8 | Untrusted input is size-capped, symlink-safe, and fail-closed | Conformance corpus with adversarial fixtures |
| 2.9 | Security analyzer conformance corpus green, including evasion variants | `run-security-evals.py` equivalent |
| 2.10 | `SECURITY.md` with a disclosure channel and a stated response SLA | Present, parseable, SLA numeric |

## 3. Performance & Efficiency

| # | Criterion | How it is proven |
|---|---|---|
| 3.1 | A benchmark suite that measures time, not one that re-runs validators | Benchmarks emit durations |
| 3.2 | Committed baseline; CI fails on >20% regression | `bench-baseline.json` diff |
| 3.3 | Full local gate under 60s | Measured wall-time |
| 3.4 | CI wall-time under 10 minutes for the PR path | Workflow timing |
| 3.5 | No O(n²) or worse over registry size in any hot path | Complexity review + scaling benchmark at 10× corpus |
| 3.6 | Independent work runs concurrently | Gate runner uses a process pool |
| 3.7 | Repeated work is cached and invalidated by content digest | Cache hit rate measured |
| 3.8 | Memory is bounded for any single input | Size caps enforced and tested |
| 3.9 | Binary/wheel size tracked with a committed ceiling | Size budget in CI |
| 3.10 | Cold-start under 100ms for interactive surfaces (CLI, LSP) | Measured |

## 4. API & Developer Experience

| # | Criterion | How it is proven |
|---|---|---|
| 4.1 | Every command supports `--json` for machine consumption | Surface scan |
| 4.2 | Every destructive command supports `--dry-run` | Destructive commands enumerated; each must declare it |
| 4.3 | No command overwrites user data without a backup or refusal | Adversarial smoke test per command |
| 4.4 | Exit codes are a documented taxonomy, not 0/1/2 by accident | `docs/exit-codes.md` + test per code |
| 4.5 | Every error message names a remediation | Static scan for bare error strings |
| 4.6 | Shell completions for bash, zsh and fish, generated not hand-written | `--check` on the generator |
| 4.7 | `--help` for every subcommand, with at least one example | Surface scan |
| 4.8 | Config resolution order documented and tested | Precedence test |
| 4.9 | Public API changes gated by a semver-diff tool | `cargo-semver-checks` / `griffe` |
| 4.10 | Install works from a clean machine via each documented path | Container smoke test per documented install method |

## 5. Documentation

| # | Criterion | How it is proven |
|---|---|---|
| 5.1 | Every documented command exists and every command is documented | Two-way surface diff |
| 5.2 | Every code example in the docs is executed in CI | Doc-test extraction |
| 5.3 | Architectural decisions recorded as ADRs | `docs/adr/` present, indexed |
| 5.4 | Every public symbol has a doc comment | `cargo doc` / docstring coverage |
| 5.5 | No broken internal or external link | Link checker |
| 5.6 | README states What, Why-now, and non-goals | Section presence |
| 5.7 | A changelog entry per user-visible change | `CHANGELOG.md` diff vs release range |
| 5.8 | Manpage generated from the same source as `--help` | `--check` on the generator |
| 5.9 | No claim in the README lacks an enforcing check | Claim-to-check map, reviewed per release |
| 5.10 | Migration guide for every breaking change | Present per major/minor |

## 6. Observability & Diagnostics

| # | Criterion | How it is proven |
|---|---|---|
| 6.1 | Structured logging with levels, `--log-format=json` | Surface scan |
| 6.2 | A `doctor` command that diagnoses a broken install | Present and tested against a broken fixture |
| 6.3 | Gate reports every failure, not just the first | Runner collects |
| 6.4 | Findings carry stable machine-readable rule IDs | Schema check |
| 6.5 | SARIF output for anything that produces findings | SARIF schema validation |
| 6.6 | Timing recorded per check and surfaced in CI | Report includes durations |
| 6.7 | Panics/tracebacks never reach the user as the primary error | Adversarial invocation suite |
| 6.8 | Version, commit and build date reported by `--version` | Test |
| 6.9 | Trends persisted across runs (quality, coverage, gate duration) | History artifact |
| 6.10 | No telemetry, stated and verifiable by network-isolated test | Offline test suite |

## 7. Release Engineering

| # | Criterion | How it is proven |
|---|---|---|
| 7.1 | Releases are fully automated from a tag | No manual step in the documented flow |
| 7.2 | Version lives in exactly one place per repo | Static scan for duplicated literals |
| 7.3 | Release is reproducible: same input, byte-identical artifact | Double-build comparison |
| 7.4 | Every generated artifact has a `--check` mode wired into CI | Generator inventory |
| 7.5 | A dry-run path exercises the whole release without publishing | `release-dry-run` equivalent |
| 7.6 | Release assets verified after publication | Post-release verification job |
| 7.7 | Version policy machine-enforced | Sequencing validator |
| 7.8 | Rollback procedure documented and rehearsed | `docs/RELEASE.md` + rehearsal record |
| 7.9 | Pre-release published and smoke-tested before the stable tag | RC in the flow |
| 7.10 | Cross-repo compatibility matrix validated before release | Matrix test in `agtmls-spec` |

## 8. Interoperability & Standards Conformance

| # | Criterion | How it is proven |
|---|---|---|
| 8.1 | Every emitted format validates against its official schema | Upstream validators in CI |
| 8.2 | No invented URI scheme where a standard one exists | Review + schema check |
| 8.3 | MCP surface passes MCP Inspector conformance | Automated Inspector run |
| 8.4 | A2A agent card validates against the A2A schema | Schema validation |
| 8.5 | LSP surface passes an LSP conformance harness | Protocol test suite |
| 8.6 | SPDX and CycloneDX both emitted and both valid | Dual validation |
| 8.7 | SARIF validates against the SARIF 2.1.0 schema | Schema validation |
| 8.8 | Spec conformance corpus passes on every implementation | Differential test across languages |
| 8.9 | Deprecated fields carry a removal version | Schema annotation check |
| 8.10 | Capability negotiation, not version sniffing | Protocol review |

## 9. Maintainability & Code Health

| # | Criterion | How it is proven |
|---|---|---|
| 9.1 | One formatter, one linter, zero suppressions without justification | `ruff` / `rustfmt` / `clippy -D warnings`; each `allow` has a reason |
| 9.2 | No duplicated logic across repos; shared code lives in one place | Duplication scan across the ecosystem |
| 9.3 | Type checking enforced | `mypy --strict` / `clippy::pedantic` |
| 9.4 | `#![forbid(unsafe_code)]` or the language's equivalent | Static scan |
| 9.5 | Single source of truth for every list that appears twice | Manifest-driven, not hand-copied |
| 9.6 | Cyclomatic complexity ceiling per function | Complexity linter |
| 9.7 | No file over 500 lines without a stated reason | Scan |
| 9.8 | Consistent style across every file in the repo | Formatter check over the whole tree |
| 9.9 | Dead code and unused dependencies removed | `cargo-udeps` / `vulture` |
| 9.10 | Every TODO links to a tracked issue | Scan |

## 10. Governance & Community

| # | Criterion | How it is proven |
|---|---|---|
| 10.1 | `LICENSE`, `CODE_OF_CONDUCT`, `CONTRIBUTING`, `GOVERNANCE`, `SUPPORT` present | Presence + link check |
| 10.2 | `CITATION.cff` valid | `cffconvert --validate` |
| 10.3 | Issue and PR templates that collect what a triager needs | Presence + field check |
| 10.4 | Branch protection: signed commits, required checks, no force-push | GitHub API assertion |
| 10.5 | OpenSSF Scorecard ≥ 9.0 | Scorecard API |
| 10.6 | OpenSSF Baseline level met and asserted | Baseline checker |
| 10.7 | Dependency update automation with grouped PRs | Renovate/Dependabot config |
| 10.8 | Stated support window and runtime-version policy | `SUPPORT.md`, machine-readable |
| 10.9 | Every repo in the ecosystem uses the same reusable CI workflow | Workflow hash comparison |
| 10.10 | Public roadmap with dated milestones | `ROADMAP.md`, parsed |

## Reporting

`agtmls-scorecard` writes `scorecard.json`:

```json
{
  "schema_version": 1,
  "repo": "agtmls-core",
  "commit": "…",
  "generated_at": "2026-09-19T00:00:00Z",
  "total": {"score": 97, "max": 100, "percent": 97.0},
  "categories": [
    {
      "id": "security",
      "score": 9, "max": 10,
      "criteria": [
        {"id": "2.6", "status": "fail",
         "detail": "SBOM omits 5 shipped paths: agents, evals, references, templates, src"}
      ]
    }
  ]
}
```

A badge is generated from `total.percent`. **The badge is generated, never
written by hand** — a hand-written badge is the exact failure this document
exists to prevent.
