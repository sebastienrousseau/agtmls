# noyalib-validation-and-qa — reference material

Complements `SKILL.md` in this directory. Date-stamped 2026-07-07,
crate v0.0.14. Load this when you need the full test-file taxonomy,
the certified / golden inventory (official YAML Test Suite mechanics +
bench fixtures), or the read-only provenance one-liners. `SKILL.md`
keeps the evidence bar, the how-to-add-a-test checklists, the
acceptance thresholds, and the "what does NOT count" list.

Ground truth: `crates/noyalib/tests/`, `doc/TESTING.md`,
`CONTRIBUTING.md`, `Makefile`. If a count here disagrees with the tree,
the tree wins — re-verify with §R3.

---

## R1. Test taxonomy

`crates/noyalib/tests/` holds **130 top-level integration test files**
(list with `ls crates/noyalib/tests/*.rs | wc -l`). Every file has an
SPDX header (verified 130 / 130). Naming conventions — match one of
these families when adding a new file:

| Prefix / family              | What it locks                                           | Files |
|------------------------------|---------------------------------------------------------|------:|
| `coverage_*`                 | llvm-cov gap closure (23 files)                         |    23 |
| `cst_*`                      | Green-tree, round-trip, span, mutation (17 files)       |    17 |
| `spec/*` + `spec.rs`         | YAML-spec-area organisation (anchors_aliases, block_scalars, comments, edge_cases, errors, flow_collections, mappings, multi_document, nested, null_bool, numbers, scalars, sequences, special_keys, tags) | 15 modules |
| `official_suite.rs`          | The conformance gate — pass-rate assertion (see §R2)    |     1 |
| `yaml_compliance_report.rs`  | Honest markdown gap report; **no assertions** — a report, not a net; run via `make compliance` |     1 |
| `proptest.rs`, `properties_interpolation.rs`, `property_interpolation.rs` | Property-based generation (parse∘emit round-trips, totality) |     3 |
| `competitive_features*.rs`, `competitor_bugs.rs` | Cross-crate interop + other crates' bugs kept as regression fixtures against silent divergence |     3 |
| `de*.rs`, `ser*.rs`, `serde*.rs` | Serde surface: `Deserializer`, `Serializer`, ecosystem |     ~8 |
| `issue_*.rs`                 | Incident regressions (e.g. `issue_46.rs` — pnpm-lock parsing) — one file per public incident |     ≥1 |
| `panic_free.rs`, `scanner_panic_regressions.rs`, `edge_audit.rs` | Fuzz-discovered panic corpora, locked in by hand |     3 |

Doctests: **~480 runnable `# Examples` blocks** across the crate (the
`doc/TESTING.md` figure at line 11 says ~384; the live count is higher
after v0.0.14 doc-comment additions — recount with `cargo test --doc
-p noyalib --all-features 2>&1 | grep "^test result"`). Every public
item in the crate carries a runnable example; the `README.md` is also
wired in via `#[cfg(doctest)] #[doc = include_str!("../README.md")]`.

---

## R2. Certified / golden inventory

### R2.1 Official YAML Test Suite

- **Location:** `crates/noyalib/tests/yaml-test-suite/` — 351 `.yaml`
  case files, upstream from `github.com/yaml/yaml-test-suite`.
- **Runner:** `tests/official_suite.rs` — the conformance gate.
- **Skip list:** `SKIP_LIST` inside `official_suite.rs` (currently
  empty). Every skip is `(id, reason)`, audited, and mirrored in
  `yaml_compliance_report.rs::SKIP_LIST` — the two lists **must stay
  in sync** (comment in `yaml_compliance_report.rs:29–32`).
- **Marker decoder:** `decode_test_suite_markers` in
  `official_suite.rs:16` handles the visual whitespace alphabet
  (`␣` → space, `⇥` / `»` / `———»` → tab, `↵` → LF, `↓` → CR,
  `⇔` → BOM, `∎` → strip-to-EOL). Do not re-implement — reuse.
- **Assertion arithmetic (verbatim from `official_suite.rs:295–314`):**

  ```rust
  let total = pass + fail + skip;
  let compliance = if total > skip {
      (pass as f64 / (total - skip) as f64) * 100.0
  } else { 100.0 };
  // ...
  assert!(
      compliance >= 94.0,
      "Compliance dropped below 94% threshold: {compliance:.1}%"
  );
  ```

  The `94.0` floor is what actually gates CI. **Ground truth
  lives in the test files:** `SKIP_LIST = &[]` (both
  `official_suite.rs:164` and `yaml_compliance_report.rs:32`), 351
  wrapper `.yaml` files under `tests/yaml-test-suite/`, and the
  `compliance >= 94.0` assertion above. `README.md` claims
  "387/387 attempted, 19 deliberately skipped out of 406" and
  `doc/BENCHMARKS.md` claims "406/406, 0 skipped" — those two
  numbers are documentation drift; the compiled tests say
  otherwise. Any drop in loaded-case pass count against the tests
  as they stand is a release blocker; the 94% floor exists as a
  hard backstop, not as the target.
- **Companion report:** `tests/yaml_compliance_report.rs` writes
  `target/yaml-compliance-report.md` with the per-case verdict and
  the reason for each failure/skip. Run with:

  ```sh
  make compliance
  # or: cargo test --test yaml_compliance_report -- --nocapture
  ```

### R2.2 Bench fixtures

`crates/noyalib/benches/fixtures/*.yaml` — the standard workloads:

| Fixture                | Represents                              |
|------------------------|-----------------------------------------|
| `github_actions.yaml`  | Realistic CI-config surface             |
| `k8s_deployment.yaml`  | Container manifest — anchors, multi-doc |
| `large_list.yaml`      | Big flat sequence — throughput scaling  |

These are golden inputs. Do not delete or mutate without a paired
Criterion baseline update. Benchmarks that use them run on CodSpeed
per PR; regressions block merge (see `doc/TESTING.md:138–140`).

---

## R3. Provenance (read-only one-liners, run to re-verify)

```sh
# Integration test file count (expected: 130 top-level .rs files)
ls crates/noyalib/tests/*.rs | wc -l

# SPDX header coverage in tests (expected: 130 / 130)
grep -l "^// SPDX-License-Identifier" crates/noyalib/tests/*.rs | wc -l

# Official YAML Test Suite case count (expected: 351 .yaml files)
ls crates/noyalib/tests/yaml-test-suite/*.yaml | wc -l

# The conformance floor as literally coded
grep -n "compliance >=" crates/noyalib/tests/official_suite.rs

# Live pass arithmetic — read the eprintln! block
grep -n "═══ YAML Test Suite Compliance ═══" crates/noyalib/tests/official_suite.rs

# Doctest count (read the "test result" line)
cargo test --doc -p noyalib --all-features 2>&1 | grep "^test result"

# Full-suite result (integration)
cargo test -p noyalib --all-features 2>&1 | grep "^test result"

# Coverage gate thresholds as currently wired
grep -rn "fail-under" .github/workflows/ Makefile 2>/dev/null

# Bench fixture inventory
ls crates/noyalib/benches/fixtures/
```

All commands above are read-only. The `cargo test` calls will build if
the target directory is cold — use `--no-run` if you want purely the
listing without exercising the suite.

**Date-stamp:** 2026-07-07 · **Crate version:** v0.0.14 · **Ground
truth:** `crates/noyalib/tests/`, `doc/TESTING.md`, `CONTRIBUTING.md`,
`Makefile`.
