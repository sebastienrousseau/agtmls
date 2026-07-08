# noyalib-architecture-contract — reference material

Complements `SKILL.md` in this directory. Date-stamp: **2026-07-08**.

Load this alongside SKILL.md when you need the exhaustive citations,
verbatim code snippets, detailed rustdoc excerpts, or the full
known-weak-points rationale. SKILL.md carries the doctrine and terse
summary; this file carries the ground-truth detail.

---

## R1. Three-loader architecture — verbatim routing detail

Cross-ref: SKILL.md §1.

### R1.1 The `stream_eligible` conjunction (verbatim)

The router lives in `from_str_with_config` (`de.rs:392`). The decision
proceeds in this order:

```rust
// de.rs:415-421 — verbatim excerpt
let value_target_bypass = is_value_target::<T>() && config.tag_registry.is_none();
let stream_eligible = config.merge_key_policy == MergeKeyPolicy::Auto
    && !config.ignore_binary_tag_for_string
    && config.policies.is_empty()
    && properties_inactive(config)
    && includes_inactive(config)
    && !value_target_bypass;
if stream_eligible {
    if let Some(res) = crate::streaming::from_str_streaming(s, config) {
        return res;
    }
}
```

### R1.2 `value_target_bypass` — why it's a conjunction, not a single check

`is_value_target::<T>() && config.tag_registry.is_none()` is
deliberately two clauses:

- `is_value_target::<T>()` — `TypeId::of::<T>() == TypeId::of::<Value>()`
  (`de.rs:170`). If the caller wants a `Value`, we can skip streaming
  and skip the span-full loader because `Value::deserialize` never
  consults the span context.
- `config.tag_registry.is_none()` — a populated tag registry can
  synthesise typed values from `!Custom` tags. The `Value` fast path
  cannot honour that; if a registry is present, we must go through the
  full loader so tag resolution runs.

Both must be true to bypass streaming for a `Value` target.

### R1.3 Router flow after `stream_eligible`

Then, unconditionally (`de.rs:436-441`), it re-checks
`max_document_length` because the streaming path enforces the same limit
inline and the skip-streaming branches don't get that for free.

Then (`de.rs:454-470`), if `is_value_target::<T>()` — a
`TypeId::of::<T>() == TypeId::of::<Value>()` check at `de.rs:170` — it
goes through `parse_one_value` (which routes to `NoSpanLoader`) and
safely downcasts `Box<dyn Any>` back to `T`. Fast path: no SpanTree,
no serde re-walk of a `Value` it already has.

Otherwise (`de.rs:472+`, `std` build) it runs `parse_one` → span-full
`Loader` → `build_span_map` → `set_span_context` → serde deserialise
pulling from the TLS-backed `SpanContext`.

`no_std` builds (`de.rs:494+`) always take `parse_one_value` →
`NoSpanLoader` and skip the TLS wiring entirely — `Spanned<T>` is
`std`-only anyway.

### R1.4 Why three (not one) — extended rationale

1. **Streaming exists for the 95% case.** `from_str::<MyConfig>(...)`
   on well-formed input is the dominant workload. Building a `Value`
   AST + `SpanTree` + span map + doing a second serde walk is pure
   waste when nobody consults them.
2. **Span-full loader exists for `Spanned<T>` and policies.**
   `Spanned<T>` deserialise reads the TLS span context populated by
   `build_span_map`. `Policy::check_value(&value)` needs a materialised
   tree to walk. Neither is possible while streaming.
3. **Span-free loader exists because `from_str::<Value>` doesn't need
   spans either.** `Value::deserialize` never consults the span context
   (there is no `Spanned` wrapper around it), so building a `SpanTree`
   for a `Value` target is just as wasteful as building a `Value` for a
   typed target.

### R1.5 Parity incident — `typed_keys` as the canonical example

Any check added to one loader MUST be evaluated for the other two, and
a cross-path test added. Concrete example: `typed_keys` (the
`Vec<Value>` parallel to a mapping's `IndexMap<String, Value>`) exists
to detect distinct-typed key collisions (`1` then `"1"` — both
stringify to `"1"` and would silently collapse). It lives in both:

- `Loader::Frame::MappingKey` (`loader.rs:215, 227`)
- `NoSpanLoader::NoSpanFrame::MappingKey` (`loader.rs:843, 850`)

Both `push_value` implementations have a
`debug_assert_eq!(map.len(), typed_keys.len(), "typed_keys must remain
parallel to map")` (`loader.rs:1170-1174`). Adding a new mapping-side
invariant in one loader but not the other will pass tests until a
`from_str::<Value>` caller trips the residual gap in production.

The streaming path does NOT do distinct-typed key collision detection
for typed targets — see §R5.2 below.

---

## R2. Exhaustive invariant table (with every file:line citation)

Cross-ref: SKILL.md §2. SKILL.md keeps the top 3-5 invariants; this
table is the full list every future edit must verify.

| Invariant | Where enforced | Failure mode if broken |
|---|---|---|
| `typed_keys` stays parallel to `Mapping` in both loaders | `loader.rs:1170-1174` (`debug_assert_eq!` in `NoSpanLoader::push_value`); mirror in span-full loader arms around `loader.rs:701-731` | Distinct-typed collision misfires — either false positives (rejecting a genuine duplicate as a collision) or silent merges of `1` and `"1"`. |
| `depth += 1` on Sequence/Mapping-Start is matched by `depth = depth.saturating_sub(1)` on **both** Ok and Err paths | `loader.rs:464, 480, 511, 529, 990, 1004, 1015, 1031`; streaming counterpart tagged with `issue #46` at `streaming.rs:663, 681, 942, 979, 1183` | Depth leaks upward across sibling collections. `max_depth` fires spuriously on shallow-but-numerous documents. |
| Scanner never consumes blank runs into content tokens | `scanner.rs` — trivia (whitespace, newline, comment) is captured as its own token kind with byte spans; comments go through `ScannedComment` | CST round-trip breaks: `Document::to_string()` != input. The `cst_round_trip.rs` per-PR test guards this on every YAML-test-suite case. |
| Panic-free contract on well-formed input | POLICIES.md §8. Only two sanctioned panic sites in the library: `crate::error::invariant_violated(msg) -> !` (`error.rs:1697`, `#[cold]`, `#[inline(never)]`) and allocator OOM. Scanner's `slice_str` defensively clamps via `floor_char_boundary` (`scanner.rs:588-595, 2070+`) precisely so a defective upstream advance produces a degraded slice, never a panic. | Any panic on a well-formed input is a bug and must ship with a regression test in the same PR. Two `panic!` sites exist in scanner.rs (`:2104, :2148`) but they are inside `#[cfg(test)]` helper functions — safe. |
| Alias budgets checked on **every** alias dereference | `loader.rs:352-400`: `alias_count += 1` then compare to `config.max_alias_expansions`; `alias_bytes += estimate_value_size(&value)` then compare to `min(config.max_document_length, MAX_ALIAS_BYTES)`. `MAX_ALIAS_BYTES = 32 MB` is the hard cap (`loader.rs:19`). Ratio heuristic `alias_anchor_ratio` at `loader.rs:359-368`. Same shape in `NoSpanLoader` at `loader.rs:917-950`. Streaming has its own equivalent. | Billion-laughs regression. Add-a-checkpoint-to-only-one-loader is the canonical parity incident. |
| `Mapping<String, Value>` — keys ARE strings; distinct-typed collisions must error loudly | `loader.rs:684-696` (span-full), `loader.rs:1143-1152` (span-free). Both return `Error::KeyCollision(key)` before falling through to `DuplicateKeyPolicy`. | Silent data loss: `1: a\n"1": b\n` collapses to one entry. **Streaming path does not have this check for typed targets** — see §R5.2. |
| Anchor byte accumulation uses `saturating_add` | `loader.rs:308, 327`; identical in streaming path | Integer wrap escape — a crafted overflow input trips the cap cleanly rather than resetting to zero. |
| `set_span_context` guard clears TLS on drop | `span_context.rs:78-85` (`impl Drop for SpanContextGuard`) | Leakage across `from_str` calls and across threads. The TLS is `RefCell<Option<SpanContext>>`; the guard replaces `None` on drop. |

---

## R3. CST `span_at` semantics — detailed subtleties

Cross-ref: SKILL.md §3.

`Document::span_at(path) -> Option<(usize, usize)>` (`document.rs:193`)
resolves a JSON-path-shaped selector to a byte span. Three subtleties
every future edit must preserve:

1. **`trim_value_span`** (`document.rs:1544`) trims trailing separator
   whitespace/newlines from the returned span so `span_at("k")` on
   `k: v\n` returns the range of `v`, not `v\n`.
2. **Keep-chomped retention** — `is_keep_chomped_block_scalar`
   (`document.rs:1558`) short-circuits `trim_value_span`. `|+` and
   `>+` block scalars preserve trailing blanks as *content*, not
   separation; trimming them would yield a slice that re-parses to a
   shorter, different value.
3. **`extend_to_line_start`** (`document.rs:1340`) — block collection
   values include the indent of their first line so the returned span
   re-parses standalone.

### Typed-cache fallback

`Document` keeps a lazy typed cache (`Value` + `SpanTree`) alongside
the green tree. When the green-tree walker cannot decode a key (the
canonical case: double-quoted keys whose green-tree bytes carry
escapes) the code path falls back to the typed cache — see the
"typed cache" comments at `document.rs:1201, 1223, 1279, 1426`. Alias
references in `entry_value`/`item_value` explicitly `return None`
(`document.rs:1422-1429, 1476-1479`) so the caller falls through to the
typed cache, whose `SpanTree` resolves the alias to its anchor's
self-contained value span.

### CST performance is intentionally slower than `Value`

CST throughput measures at roughly **21 MB/s** parse; the plain-`Value`
path measures at roughly **36 MB/s**. This 40% overhead is the
ADR-0001 trade-off — trivia retention is not free. `parse_document`
is bounded at ≤2× `from_str::<Value>` per the design note's performance
contract; do not "optimise" the CST by dropping trivia.

---

## R4. SemVer / API contract — detailed rustdoc excerpts

Cross-ref: SKILL.md §4. Source of truth is `lib.rs` §"API stability
and SemVer policy" at `lib.rs:111-157`.

- **Pre-1.0 breaking axis is the patch number** during the `0.0.x`
  series. A `0.0.14 → 0.0.15` bump *is* the breaking bump. Do not
  "save up" breaking changes for a mythical `0.1.0`; the memory
  `project_v001_launch_posture` frames the current runway explicitly
  as `0.0.x → 0.0.99 → 0.0.999 → 0.1.0`.
- **`#[non_exhaustive]` is applied to every public configuration
  struct and every error type** — `ParserConfig`, `SerializerConfig`,
  `Error`, `ErrorKind`, `BudgetBreach` (`error.rs:160`),
  `MergeKeyPolicy`, `DuplicateKeyPolicy`, `FlowStyle`, `ScalarStyle`,
  `YamlVersion`. Adding a field or variant is **not** a breaking
  change; external code cannot use exhaustive struct-literal syntax.
  When adding a new config field, do not remove `#[non_exhaustive]`
  "because it's convenient."
- **The deserialise target bound is
  `T: for<'de> Deserialize<'de> + 'static`.** The `'static` half is
  documented explicitly (`lib.rs:139-147`) because it is what the
  `is_value_target::<T>()` `TypeId` check needs. A small number of
  external trait signatures (notably `figment::Format::from_str`)
  drop `'static`; for those, the feature-gated
  `from_str_typed_no_tag_preserve` (`de.rs:189`) exists as an internal
  escape hatch that never engages the `Value`-tag-preserving fast
  path.
- **CI enforces the surface** via `cargo semver-checks` on every PR.

---

## R5. Known-weak points — detailed rationale

Cross-ref: SKILL.md §5.

### R5.1 `max_sequence_length` / `max_mapping_keys` surface as `Error::Serialize`, not `Error::Budget`

Verify: `loader.rs:574-577`, `loader.rs:674-676`, and mirrors at
`loader.rs:1062-1066, 1134-1136`:

```rust
return Err(Error::Serialize("sequence length limit exceeded".to_owned()));
```

These are DoS budgets that fire during parsing and belong under
`Error::Budget(BudgetBreach::…)`. Classifier wart carried over from
v0.0.13.

**Noted for v0.0.15**: add `BudgetBreach::MaxMappingKeys` and
`BudgetBreach::MaxSequenceLength` variants (allowed under
`#[non_exhaustive]`), reroute both call sites in both loaders, add
cross-path parity tests. Do not "clean this up quietly" — it changes
`ErrorKind` classification, which is public.

### R5.2 Streaming path cannot do distinct-typed key collision detection for typed targets

The streaming path asks serde for `String` keys (`ValueVisitor::visit_map`
receives them as strings), which stringifies typed scalars *before*
the collision check could distinguish `1` from `"1"`. Documented at
`de.rs:406-414`. The `value_target_bypass` conjunction routes `Value`
targets around the streaming path so the `NoSpanLoader` (which owns
the check) sees them. Typed targets like `HashMap<String, T>` on the
streaming path **do not get** `KeyCollision` — a known residual gap.
Any user who needs the guard on a typed target must route through
`Value` first, or disable streaming via one of the streaming-eligibility
escape hatches.

### R5.3 Coverage below the 98% target

Current gates: 96% functions / 94% lines / 93% regions (live in
`.github/workflows/ci.yml:160-162` and `shared-coverage.yml`
defaults). `doc/TESTING.md` still cites `95 / 93 / 92` — that
document is stale; trust the workflow files. PLAN.md Phase 7
target: 98/98/98. Do not lower the gates to make a PR pass. Add
tests for the newly-uncovered lines instead.

### R5.4 Single-maintainer bus factor

GOVERNANCE.md sets a 1.0-gate criterion: at least one
non-@sebastienrousseau maintainer with commit rights and
release-signing capability. Until then, the project's bus factor is
1. Any architectural change that adds surface (new public function,
new config axis, new subsystem) must clear the "would a second
maintainer understand this from the docs and code alone?" bar.

### R5.5 CST throughput ~21 MB/s vs `Value` ~36 MB/s

Not a bug — an ADR-0001 trade-off. Documented so future perf work
does not chase this as regression.
