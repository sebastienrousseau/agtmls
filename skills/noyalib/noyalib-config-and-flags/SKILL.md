---
name: noyalib-config-and-flags
description: >
  Catalog of every configuration axis in noyalib — Cargo features
  (defaults, deps, production vs experimental, MSRV interactions),
  `ParserConfig` DoS budgets and behavioural toggles, `SerializerConfig`
  emission style, and the two preset constructors (`ParserConfig::new`,
  `ParserConfig::strict`). Use when asked "what does feature `X` do",
  "how do I limit `Y`", "what's the default for `max_depth` /
  `max_document_length` / alias expansions", "how do I add a Cargo
  feature", "how do I add a `ParserConfig` axis", "which toggle disables
  the streaming fast path", "does the minimal profile drop `serde_ignored`",
  "does `strict()` reject duplicate keys". Also the checklist for adding a
  new axis without repeating the FlowStyle-ignored (#84) or the
  Loader/NoSpanLoader budget-drift class of bug.
---

# noyalib — Configuration and Flags

Date-stamped: **2026-07-08**, verified against **noyalib v0.0.14**
(`crates/noyalib/Cargo.toml` line 3).

Flags drift. Numbers drift. Before quoting anything from this file,
re-run the drift re-checks in the **Provenance** section at the bottom
and update rows that no longer match.

> **Reference tables** — full 24-row Cargo feature matrix, 12-row
> `ParserConfig` DoS-budget table, 16-row behavioural-toggles table,
> 13-row `SerializerConfig` table, and the extended #84 tale live in
> [`reference.md`](reference.md). This file keeps doctrine (checklists),
> the streaming-gate list, compact preset summary, defaults, MSRV rules.

## When to use this skill

- "What does feature X do / what's the default for Y" questions.
- PR reviews adding a Cargo feature, `ParserConfig` field,
  `SerializerConfig` field, or preset constructor.
- Explaining streaming vs AST loader routing based on caller config.
- Sizing ingestion-pipeline security posture (which knobs, which
  preset).

## When NOT to use

- Architecture rationale ("why three loaders", "why zero unsafe") →
  `noyalib-architecture-contract`.
- YAML semantics of a toggle (1.1 vs 1.2) → `yaml-domain-reference`.
- Release / branch / CI mechanics → `noyalib-change-control`.

---

## 1. Cargo feature matrix — orientation

Source of truth: `crates/noyalib/Cargo.toml` lines 488–616. Full 24-row
matrix (enables / deps / default / prod vs exp / MSRV) in
[`reference.md` §1](reference.md#1-cargo-feature-matrix-full).

**Default set** (Cargo.toml line 489):
`["std", "fast-int", "fast-float", "strict-deserialise"]`.

- `std` — serde std mode; `std::error::Error` on `de::Error`.
- `fast-int` — `itoa` int formatting (~10x `Display`).
- `fast-float` — `ryu` float formatting.
- `strict-deserialise` — `from_str_strict` etc. surface unknown keys as
  `Error::UnknownField` via `serde_ignored`.

**MSRV / edition** (Cargo.toml lines 4–5):
`edition = "2024"`, `rust-version = "1.85.0"`.

- Only `nightly-simd` needs non-stable toolchain (guarded by `build.rs`
  `noyalib_nightly` cfg; stable builds still get the `memchr` / SWAR
  fallback via `simd`).
- `compare-saphyr` is a dev-dep gate — off by default so the public
  MSRV isn't dragged forward by a benchmarking comparator.

**Additive-only contract.** Enabling a feature must not silently remove
functionality or types available with it disabled. `minimal` is not a
suppress-others switch — it's the label for "no defaults + `std`".

---

## 2. `ParserConfig` — DoS budgets (orientation)

Source: `crates/noyalib/src/de/config.rs`. `#[non_exhaustive]` (line
66). `default()` / `strict()` verified at lines 251–288 and 317–356.

Twelve enforced budgets today. Full default-vs-`strict()` table
(`max_depth`, `max_document_length`, `max_alias_expansions`,
`max_mapping_keys`, `max_sequence_length`, `max_events`, `max_nodes`,
`max_total_scalar_bytes`, `max_documents`, `max_merge_keys`,
`alias_anchor_ratio`, `max_include_depth`) in
[`reference.md` §2](reference.md#2-parserconfig--dos-budgets-full).

Headline pair: `max_depth` 128 → 64; `max_document_length` 64 MB → 1
MB. Every other budget in `strict()` is halved-or-tighter.

**Loader parity.** As of v0.0.14 every budget is enforced uniformly by
both the span-tracking `Loader` and the `NoSpanLoader` (Value-target
fast path). `ParseConfig` (`crates/noyalib/src/parser/loader.rs` lines
29–81) mirrors `ParserConfig` via a hand-written
`From<&ParserConfig>` impl (lines 96–130). Any new budget you add on
`ParserConfig` must land in **both** `ParseConfig` fields *and* the
`From` impl or the NoSpan path silently ignores it.

---

## 3. `ParserConfig` — behavioural toggles (orientation)

Sixteen toggles. Full field-by-field table (type / default / effect /
streaming-eligibility) in
[`reference.md` §3](reference.md#3-parserconfig--behavioural-toggles-full).

### Streaming-fast-path bypass list

Verified at `de.rs` lines 416–421 (`stream_eligible`). Streaming is
skipped when **any** of these is true:

- `merge_key_policy != Auto` (`de.rs` L416).
- `ignore_binary_tag_for_string == true` (L417).
- `policies` is non-empty (L418).
- `properties` is `Some(_)` (L419).
- `include_resolver` is `Some(_)` (L420).
- `T == Value` and no `tag_registry` — separate `value_target_bypass`
  route that runs `NoSpanLoader` directly.

Flipping any of these changes **which code runs**, not just how it
configures. Note that in a PR review — you're now on the AST loader,
so budget parity (§2) and post-parse walk correctness matter.

Remaining toggles (`yaml_version`, `duplicate_key_policy`,
`strict_booleans`, `legacy_booleans`, `legacy_octal_numbers`,
`legacy_sexagesimal`, `no_schema`, `lossless_u64_integers`,
`require_indent`, `tag_registry` presence, `strict_properties`) are
streaming-eligible.

---

## 4. Preset constructors

Compact summary — `default()` vs `strict()` at a glance. For the
budget numbers, see §2; for full field semantics, see §3.

| Preset | Budgets | `duplicate_key_policy` | `strict_booleans` | `require_indent` | `strict_properties` | `max_include_depth` |
|---|---|---|---|---|---|---|
| `ParserConfig::new()` / `default()` | Permissive (§2, "default" column) | `Last` | `false` | `Unchecked` | `false` | `24` |
| `ParserConfig::strict()` | Halved-or-tighter across all twelve (§2) | `Error` | `true` | `Even` | `true` | `8` |

Doc tests assert `default().max_depth == 128` and
`strict().max_depth == 64` — those are the two smoke checks to run if
you suspect either preset drifted.

Other constructors:

- `ParserConfig::version(YamlVersion)` — preset over the three
  `legacy_*` toggles matching the target spec version.
- `ParserConfig::with_policy(P)` — registers a policy; every call
  after the first appends.

There is currently **no** `permissive()` or `lax()` preset — extend
carefully if one is added because policy expectations (streaming vs
AST — see §3 bypass list) must be re-audited.

---

## 5. `SerializerConfig` — orientation

Source: `crates/noyalib/src/ser.rs` lines 66–116. `#[non_exhaustive]`
(line 65). Thirteen fields. Full table in
[`reference.md` §4](reference.md#4-serializerconfig-full).

Most-asked defaults: `indent = 2`, `max_depth = 128`,
`flow_style = Block`, `flow_threshold = 4`, `scalar_style = Auto`,
`quote_all = false`, `block_scalars = true`,
`block_scalar_threshold = 1`, `folded_wrap_chars = 80`,
`min_fold_chars = 80`.

**Cautionary tale — issue #84 (`flow_style` ignored)**, fixed in
v0.0.8. Builder accepted the field; no emitter code read it. Round-trip
tests asserted the value stuck; none compared emitted bytes. Rule:

> A config axis is **not done** until something reads it **and** a
> test proves it changes the emitted bytes / parsed value.

Every new field on either config struct must land with a two-value
differential test. Full narrative in
[`reference.md` §5](reference.md#5-cautionary-tale--issue-84-flow_style-ignored).

---

## 6. Adding a new Cargo feature — checklist

1. **Design it additive.** Enabling the feature adds capability; it
   must not remove or shadow anything visible with the feature off.
2. **Manifest entry with an inline comment** in `Cargo.toml`'s
   `[features]` block: what it enables, what dep(s) it pulls, whether
   any implied features are chained, and — if experimental — the
   toolchain/edition/MSRV caveat. Match the existing prose style.
3. **`dep:` prefix** any optional dep in the value expression (see
   `fast-int`, `sval`, `parallel`); this suppresses the implicit
   feature that Cargo would otherwise auto-generate from an optional
   dep.
4. **Wire into the feature-matrix CI job** if the feature produces a
   distinct compile surface. **Scope `CARGO_TARGET_DIR` per matrix
   leg** — the cache-poisoning doctrine: Swatinem's cache + sub-2 s
   `cargo check` can mask a broken no_std build if two legs write to
   the same target dir. Isolated dir per leg is non-negotiable.
5. **Add a runnable example** in `examples/` with
   `required-features = ["your-feature"]` in `Cargo.toml`'s
   `[[example]]` block. Examples double as smoke tests during
   `cargo publish` verify.
6. **README feature list** — update the feature table so the
   documented catalog stays authoritative.
7. **CHANGELOG entry** — under the release the feature lands in.
   Additive but visible.
8. **docs.rs**: no change required, `all-features = true` +
   `rustdoc-args = ["--cfg", "docsrs"]` are already set (Cargo.toml
   lines 618–620). If your gated items need `#[doc(cfg(...))]`
   annotations, add them so the docs.rs badge renders.
9. **Nightly / non-baseline toolchain**: gate the code with
   `#[cfg(feature = "…")]` **and** either `noyalib_nightly` (per
   `build.rs`) or a rustc-version probe. Do not silently break
   stable-toolchain callers who compose features.

---

## 7. Adding a new `ParserConfig` axis — checklist

1. **Field** on `ParserConfig` in `crates/noyalib/src/de/config.rs`.
   `#[non_exhaustive]` protects you from a breaking-change bump *only*
   if downstream never constructed the struct exhaustively — that
   contract is documented in the struct's rustdoc; keep it that way.
2. **Builder method** on `impl ParserConfig` returning `Self` with
   `#[must_use]`. Match the existing prose style.
3. **Default value** in `impl Default for ParserConfig` and,
   independently, in `ParserConfig::strict()`. If your axis is a
   security budget, `strict()` should be at least as tight as
   `default()`.
4. **Loader-parity mirror.** Add the field to `ParseConfig` in
   `crates/noyalib/src/parser/loader.rs` **and** to the
   `From<&ParserConfig> for ParseConfig` impl. Missing this is how
   NoSpanLoader silently drops budgets. Every axis must be enforced
   in every loader that walks user input, or the rustdoc must
   explicitly document *why not*.
5. **Streaming-path decision.** If the axis changes semantics of
   already-parsed data, mirror it into `crate::streaming` too. If the
   axis needs a post-parse walk (properties / includes / policies),
   add it to the streaming-gate expression at `de.rs` ~L416 (see §3
   bypass list) so the streaming path is bypassed when the toggle is
   active.
6. **Tests on every affected path.** Two-value differential test:
   default value vs non-default value produces distinct behaviour on
   `from_str`, `from_slice`, `from_reader`, and — if applicable —
   the `Value`-target fast path. Missing any leg leaves a #84-shaped
   hole (see
   [`reference.md` §5](reference.md#5-cautionary-tale--issue-84-flow_style-ignored)).
7. **Rustdoc with `# Examples`.** The existing fields all carry
   compilable doc-tests; new ones must too. `missing_docs = "warn"`
   is set at the workspace level (Cargo.toml line 638).
8. **CHANGELOG entry** under the release; note it as additive.

---

## 8. Provenance and drift re-checks

Tables here and in `reference.md` verified 2026-07-08 against v0.0.14.
Re-run these before quoting:

```sh
# Version + defaults.
grep -n '^version\|^rust-version\|^edition\|^default' crates/noyalib/Cargo.toml

# Feature list (reference.md §1).
awk '/^\[features\]/,/^\[/' crates/noyalib/Cargo.toml | head -160

# ParserConfig defaults (reference.md §2).
grep -n 'max_depth\|max_document_length\|max_alias_expansions\|max_events\|max_nodes' \
    crates/noyalib/src/de/config.rs | head -20
grep -n 'max_depth\|max_document_length\|max_events' \
    crates/noyalib/src/parser/loader.rs | head -6

# strict() presets.
awk '/pub fn strict/,/^    }/' crates/noyalib/src/de/config.rs

# Loader-parity: does ParseConfig mirror every ParserConfig field?
diff \
  <(grep -E '^    pub [a-z_]+:' crates/noyalib/src/de/config.rs | sort) \
  <(grep -E '^    pub [a-z_]+:' crates/noyalib/src/parser/loader.rs | sort)

# Streaming-gate: which toggles bypass streaming?
grep -n 'stream_eligible' crates/noyalib/src/de.rs

# SerializerConfig fields + defaults.
awk '/pub struct SerializerConfig/,/^impl SerializerConfig/' crates/noyalib/src/ser.rs
```

Any drift → update **both files** in the same PR per the #84 rule (§5):
a config axis is not done until something reads it, a test proves it,
and the docs match reality.

---

## Key file references

- `crates/noyalib/Cargo.toml` L488–616 — `[features]` block.
- `crates/noyalib/src/de/config.rs` — `ParserConfig`, `YamlVersion`,
  `DuplicateKeyPolicy`, `MergeKeyPolicy`, `RequireIndent`.
- `crates/noyalib/src/de.rs` L~400–500 — streaming vs AST gate;
  `apply_includes` / `apply_properties` post-parse walk.
- `crates/noyalib/src/parser/loader.rs` L27–130 — `ParseConfig` mirror
  + `From<&ParserConfig>` impl (loader-parity contract).
- `crates/noyalib/src/ser.rs` L64–236 — `SerializerConfig` struct,
  defaults, builders.
- `crates/noyalib/src/streaming.rs` — streaming path (called only when
  `stream_eligible == true`).
- [`reference.md`](reference.md) — full matrices for §§1–4 + the #84
  narrative (§5).
