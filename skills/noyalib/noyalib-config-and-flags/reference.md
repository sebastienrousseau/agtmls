# noyalib — Configuration and Flags · Reference tables

Complements `SKILL.md` (noyalib-config-and-flags). Split-off date:
**2026-07-08**, verified against **noyalib v0.0.14**
(`crates/noyalib/Cargo.toml` line 3).

Contents:

1. Full Cargo feature matrix (24 rows).
2. Full `ParserConfig` DoS-budget table (12 rows) — every default and
   `strict()` value verified against source.
3. Full `ParserConfig` behavioural-toggles table (16 rows).
4. Full `SerializerConfig` field table (13 rows).
5. FlowStyle-ignored (#84) cautionary tale — extended narrative.

For doctrine (how to add a Cargo feature, how to add a `ParserConfig`
axis), the streaming-fast-path bypass list, preset-constructor summary,
the default set, MSRV rules, and drift re-checks: see `SKILL.md`.

---

## 1. Cargo feature matrix (full)

Source of truth: `crates/noyalib/Cargo.toml` lines 488–616. Every row
below was verified on 2026-07-08 at v0.0.14. **Defaults:**
`["std", "fast-int", "fast-float", "strict-deserialise"]` (line 489).

| Feature | What it enables | Deps pulled in | Default? | Prod/Exp | MSRV / toolchain note |
|---|---|---|---|---|---|
| `std` | Sync serde's std mode; enables `std::error::Error` on `de::Error`. Required for many other features. | `serde/std` | Yes | Prod | 1.85 baseline. |
| `fast-int` | Branchless int formatting via `itoa` (~10x faster than `Display::fmt`). Falls back to `core::fmt` if off. | `itoa` | Yes | Prod | 1.85. |
| `fast-float` | Branchless float formatting via `ryu` (Grisu). Falls back to `{:?}` if off — preserves float-ness but no auto scientific notation for very large magnitudes. | `ryu` | Yes | Prod | 1.85. |
| `strict-deserialise` | `from_str_strict` / `from_slice_strict` / `from_reader_strict` — surface unknown keys as `Error::UnknownField`. | `serde_ignored` | Yes | Prod | 1.85. |
| `minimal` | Meta-feature: `std` only, no formatting accelerators, no `strict-deserialise`. Intended one-flag opt-in for FIPS / embedded / audit-heavy dep budgets. Equivalent to `default-features = false, features = ["std"]`. | — | No | Prod | 1.85. |
| `miette` | Rich diagnostic reporter integration. | `miette` | No | Prod | 1.85. |
| `ariadne` | Alternative rich diagnostic reporter. | `ariadne` | No | Prod | 1.85. |
| `robotics` | Robotics/URDF-adjacent conveniences (`crate::robotics`). | — | No | Prod | 1.85. |
| `include` | `!include` directive walker; post-parse walk consults a caller-supplied `IncludeResolver`. Pairs with `max_include_depth`. | — | No | Prod | 1.85. |
| `include_fs` | Bundled `SafeFileResolver` (root sandbox, symlink policy). Implies `include` + `std`. | — | No | Prod | 1.85. |
| `garde` | Post-deserialise validation via `garde` derives. | `garde` | No | Prod | 1.85. |
| `validator` | Post-deserialise validation via `validator` derives. | `validator` | No | Prod | 1.85. |
| `schema` | JSON Schema codegen via `schemars`. `#[derive(noyalib::JsonSchema)]`, `schema_for::<T>()`, `schema_for_yaml::<T>()`. | `schemars`, `serde_json` | No | Prod | 1.85. |
| `validate-schema` | JSON Schema 2020-12 validation of parsed YAML. Implies `schema`. | `schema` + `jsonschema` | No | Prod | 1.85. |
| `figment` | `figment::Provider` shim. `noyalib::figment::Yaml` drops into layering chains alongside `Toml` / `Json`. Implies `std`. | `figment` | No | Prod | 1.85. |
| `simd` | SIMD-friendly multi-byte search primitives (`noyalib::simd`), vectorised via `memchr` SSE2/NEON arity-1/2/3, SWAR for needle sets of 4+, scalar fallback. Pure-safe Rust (preserves `unsafe_code = "forbid"`). | — | No | Prod | 1.85. |
| `nightly-simd` | Portable-SIMD (`std::simd`) 16/32/64-byte-wide `SimdScanner`. Implies `simd`. | — | No | Exp | **Requires nightly** (`#![feature(portable_simd)]`); guarded by `build.rs` `noyalib_nightly` cfg. Stable builds still ship the `memchr`/SWAR fallback. |
| `compare-saphyr` | Dev/bench: cross-library comparison against `serde-saphyr`. | `serde-saphyr` (dev) | No | Exp | Saphyr requires Rust 2024 edition (Cargo 1.85+). Off by default so the crate's public MSRV isn't dragged forward by a dev-dep. |
| `tokio` | Native async stream parsing on `tokio::io::AsyncRead`: `from_async_reader`, `from_async_reader_multi`, `YamlDecoder` for `tokio_util::codec::Framed`. Implies `std`. | `tokio`, `tokio-util`, `bytes` | No | Prod | 1.85. |
| `sval` | Zero-allocation streaming serialization adapter (`impl sval::Value for Value`, `to_sval_writer`). Serde remains the default. | `sval` | No | Prod | 1.85. |
| `recovery` | Error-recovering parser for LSP/IDE partial-parse pipelines: `parse_lenient`, `parse_lenient_with`, `ParseResult` carrying best-effort tree + collected errors. Implies `std`. | — | No | Prod | 1.85. |
| `parallel` | Rayon-backed multi-document deserialisation: `parallel::parse<T>`, `parallel::values`, `parallel::split`. Pre-scans `---` boundaries on one thread then deserialises per-document in the Rayon global pool. Implies `std`. | `rayon` | No | Prod | 1.85. |
| `lossless-u64` | Opt-in unsigned-integer model for `!!int` scalars in the `i64::MAX+1..=u64::MAX` range. Exposes an additional public `Number` variant → API-additive surface, hence opt-in. | — | No | Prod | 1.85. |
| `compat-serde-yaml` | Drop-in surface compatible with `serde_yaml` 0.9 (`noyalib::compat::serde_yaml`). Every type is a noyalib-native re-export, **not** a re-export of the archived upstream crate. | — | No | Prod | 1.85. |
| `wasm-opt` | Wasm-specific optimisations gate. | — | No | Prod | 1.85. |
| `noyavalidate` | Turnkey validation profile: `std + miette + miette/fancy + validate-schema`. Composes the diagnostic renderer, schema validator, and codegen halves for the CLI-adjacent surface. | (transitively: `miette`, `schemars`, `serde_json`, `jsonschema`) | No | Prod | 1.85. |

**MSRV baseline** is `rust-version = "1.85.0"` (`Cargo.toml` line 5) and
`edition = "2024"` (line 4). Only `nightly-simd` requires a
non-stable toolchain today; `compare-saphyr` pulls a dev-dep that
itself demands 2024-edition Cargo (1.85+).

**Additive-only contract.** Every feature is additive: enabling a
feature must not silently remove functionality or types available with
it disabled. `minimal` is not a suppress-others switch — it's a
convenience label for "no defaults + `std`".

---

## 2. `ParserConfig` — DoS budgets (full)

Source: `crates/noyalib/src/de/config.rs`. Struct is `#[non_exhaustive]`
(line 66), so downstream must construct with builders / defaults, not
exhaustive struct-literals.

`default()` and `strict()` were both re-verified at
`crates/noyalib/src/de/config.rs` lines 251–288 and 317–356.

| Field | Type | `default()` | `strict()` | Notes |
|---|---|---:|---:|---|
| `max_depth` | `usize` | **128** | **64** | Nested-collection recursion cap. |
| `max_document_length` | `usize` | **64 MB** (`1024 * 1024 * 64`) | **1 MB** | Enforced inline in streaming path; re-checked before the AST loader if streaming is bypassed (`de.rs` ~L436). |
| `max_alias_expansions` | `usize` | **1024** | **100** | Prevents billion-laughs style expansion attacks. |
| `max_mapping_keys` | `usize` | **65 536** (`1024 * 64`) | **1 024** | Per-mapping key-count cap. |
| `max_sequence_length` | `usize` | **65 536** | **1 024** | Per-sequence item-count cap. |
| `max_events` | `usize` | **1 000 000** | **100 000** | Whole-document parser-event cap. |
| `max_nodes` | `usize` | **250 000** | **25 000** | Whole-document node-count cap. |
| `max_total_scalar_bytes` | `usize` | **64 MB** | **1 MB** | Cumulative scalar-payload cap. |
| `max_documents` | `usize` | **1 000** | **100** | Multi-doc stream cap. |
| `max_merge_keys` | `usize` | **10 000** | **1 000** | Total `<<` merge-key expansions in a document. |
| `alias_anchor_ratio` | `Option<f64>` | **`Some(10.0)`** | **`Some(5.0)`** | Ratio of alias uses to anchors declared; `None` disables the ratio check. |
| `max_include_depth` (`feature = "include"`) | `usize` | **24** | **8** | Per-walk `!include` recursion cap. Paired with a visited-set for cycle detection independent of depth. |

**Loader parity.** As of v0.0.14, every one of the twelve budgets above
is enforced uniformly by both the span-tracking `Loader` and the
`NoSpanLoader` used by the `Value`-target fast path. `ParseConfig` (in
`crates/noyalib/src/parser/loader.rs` lines 29–81) mirrors the public
`ParserConfig` and is constructed via a hand-written `From<&ParserConfig>`
impl (lines 96–130). Any new budget you add on `ParserConfig` must
land in **both** `ParseConfig` fields *and* the `From` impl or the
NoSpan path silently ignores it.

---

## 3. `ParserConfig` — behavioural toggles (full)

| Field | Type | Default | Effect | Streaming fast-path? |
|---|---|---|---|---|
| `yaml_version` | `YamlVersion` | `V1_2` | Chooses YAML 1.2 vs 1.1 plain-scalar resolution (`yes`/`no`, bare octal, sexagesimal, …). `version()` is a preset over the three `legacy_*` toggles below. | Streaming-eligible. |
| `duplicate_key_policy` | `DuplicateKeyPolicy` | **`Last`** (YAML 1.2 default) | `First`: keep first; `Last`: keep last; `Error`: reject. `strict()` sets `Error`. | Streaming-eligible. |
| `merge_key_policy` | `MergeKeyPolicy` | **`Auto`** (YAML 1.2 merge semantics for `<<:`) | `AsOrdinary`: treat `<<` as literal string key; `Error`: reject any doc containing `<<`. | **Non-`Auto` bypasses streaming** (`de.rs` L416). |
| `strict_booleans` | `bool` | `false` (default) / `true` (`strict()`) | Only accept spec booleans in the active `yaml_version`. | Streaming-eligible. |
| `legacy_booleans` | `bool` | `false` | Independent of version, additionally accept `yes/no/on/off` as booleans. | Streaming-eligible. |
| `legacy_octal_numbers` | `bool` | `false` | Parse bare `0644` as octal (YAML 1.1 behaviour) even when `yaml_version = V1_2`. | Streaming-eligible. |
| `legacy_sexagesimal` | `bool` | `false` | Parse `60:00` as `3600` (YAML 1.1 behaviour). | Streaming-eligible. |
| `no_schema` | `bool` | `false` | Suppress the plain-scalar resolver — every plain scalar stays a string. | Streaming-eligible. |
| `ignore_binary_tag_for_string` | `bool` | `false` | Treat `!!binary` scalars as strings during deserialisation into `String` targets (interop with senders that mis-tag). | **`true` bypasses streaming** (`de.rs` L417). |
| `lossless_u64_integers` (`feature = "lossless-u64"`) | `bool` | `false` | Preserve `u64` values in the `i64::MAX+1..=u64::MAX` band as `Number::UInt` instead of coercing to float. | Streaming-eligible. |
| `require_indent` | `RequireIndent` | **`Unchecked`** (default) / **`Even`** (`strict()`) | House-style indent discipline: `Unchecked`, `Even`, `Divisible(N)`, `Uniform(Some(N))`, `Uniform(None)` (first delta sets the standard). | Streaming-eligible. |
| `policies` | `Vec<Arc<dyn Policy>>` | empty | Pluggable Safe-YAML policies inspecting parser events and the post-parse `Value` tree. Any `Err` aborts the parse. | **Non-empty bypasses streaming** (`de.rs` L418) so the policy contract holds uniformly. |
| `tag_registry` | `Option<Arc<TagRegistry>>` | `None` | Registered tags strip off scalars on the streaming path. | Presence steers `is_value_target` bypass, not the streaming gate. |
| `properties` (`feature = "std"`) | `Option<Arc<HashMap<String, String>>>` | `None` | `${KEY}` / `${KEY:-default}` post-parse substitution on every scalar. Also supports `${{`, `$$`, `}}` escapes. | **`Some(_)` bypasses streaming** (`de.rs` L419) so the substitution walk runs uniformly. |
| `strict_properties` (`feature = "std"`) | `bool` | `false` (default) / `true` (`strict()`) | On unknown placeholders: `true` errors with `Error::Custom`; `false` empty-substitutes (matches `Value::interpolate_properties_lossy`). | Only meaningful when `properties` is set (already bypasses streaming). |
| `include_resolver` (`feature = "include"`) | `Option<IncludeResolver>` | `None` | Post-parse `!include` node substitution. | **`Some(_)` bypasses streaming** (`de.rs` L420) so `apply_includes` can walk the tree. |

---

## 4. `SerializerConfig` (full)

Source: `crates/noyalib/src/ser.rs` lines 66–116. Also
`#[non_exhaustive]` (line 65).

| Field | Default | What it does |
|---|---:|---|
| `indent` | **2** | Spaces per indentation level. |
| `document_start` | `false` | Emit `---` before the first document. |
| `document_end` | `false` | Emit `...` after each document. |
| `block_scalars` | `true` | Allow `|` / `>` block-scalar style for multi-line strings. |
| `block_scalar_threshold` | **1** | Minimum newlines to trigger block-scalar style. |
| `flow_style` | `FlowStyle::Block` | Collection style preference: `Block`, `Flow`, or `Auto` (flow for small collections). |
| `scalar_style` | `ScalarStyle::Auto` | String quoting preference: `Auto`, `DoubleQuoted`, `SingleQuoted`, `Literal` (`|`), `Folded` (`>`), `Plain`. |
| `flow_threshold` | **4** | In `Auto` flow, use flow style for ≤ N items. |
| `quote_all` | `false` | Force-quote every string scalar. |
| `compact_list_indent` | `false` | Sequence items align with their mapping key (no extra indent level). |
| `folded_wrap_chars` | **80** | Line width for folded (`>`) block scalars. |
| `min_fold_chars` | **80** | Minimum string length before block-scalar style is considered. |
| `max_depth` | **128** | Nesting-depth cap. Exceeding it returns `Error::DepthLimit`. |

---

## 5. Cautionary tale — issue #84 (`flow_style` ignored)

Fixed in v0.0.8. For several releases `SerializerConfig::flow_style`
was accepted by the builder but *no emitter code read the field*.
Serialisers happily ignored the caller's intent; unit tests only
asserted the config value round-tripped, not that emitted YAML changed.

Failure mode in detail:

- Builder method `flow_style(FlowStyle)` compiled, was `#[must_use]`,
  had rustdoc with an example.
- Round-trip tests asserted `cfg.flow_style == FlowStyle::Flow` after
  `.flow_style(FlowStyle::Flow)`.
- No test compared the emitted bytes for `FlowStyle::Block` vs
  `FlowStyle::Flow`. The emitter was hardwired to block style for
  collections.
- Callers relied on flow output for CI diff readability and got block
  output. Silent behavioural regression.

Rule extracted:

> A config axis is **not done** until something reads it **and** a
> test proves it changes the emitted bytes / parsed value.

Every new field on either config struct must land with a test that
exercises two distinct values and asserts a distinct outcome. This is
the two-value differential test rule cited by the `ParserConfig`
checklist in `SKILL.md`.
