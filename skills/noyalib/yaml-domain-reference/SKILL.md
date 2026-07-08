---
name: yaml-domain-reference
description: YAML 1.2.2 spec knowledge as noyalib implements it — scalar resolution (resolve_plain_ext table), documents/streams/directives (§6.8, §9.1.2), block vs flow, block-scalar chomping (|/>/-/+), line breaks (§5.4 LF/CR/CRLF), anchors/aliases/merge keys with DoS budgets (max_alias_expansions, alias_anchor_ratio, max_merge_keys), tags (!!str/!!int/!!bool/!!null/!!binary → RFC 4648), YAML 1.1 vs 1.2 flags (legacy_booleans/octal/sexagesimal), the Norway problem, MergeKeyPolicy Auto/AsOrdinary/Error, and official-suite conformance arithmetic. Load when reasoning about YAML semantics, plain-scalar coercion, or spec-conformance work. Use for "explain merge keys / anchors / chomping / tags", "how do I resolve a plain scalar", "why does `no` parse as false", "does noyalib accept `nan` / `.inf` / octal `0o7`", "how many cases does the official YAML suite cover".
date: 2026-07-08
---

# YAML domain reference

> **Reference material** (full `resolve_plain_ext` table, directive
> regression case list, block-scalar chomping worked-example matrix,
> official-suite integration walkthrough, YAML 1.1 vs 1.2 long-form flag
> matrix): see `reference.md` in this directory. Load when the terse
> summaries below are insufficient — spec-conformance work, tracing a
> case ID back to its rule, or verifying chomping edge cases.

**Purpose.** Domain-theory pack — the YAML 1.2.2 subset noyalib
implements, plus the gotchas that hit real code.

**When NOT to use.** Parser/CST internals →
`noyalib-architecture-contract`. Config flags in depth →
`noyalib-config-and-flags`. Historical incidents →
`noyalib-failure-archaeology`.

**Ground truth files** (re-read if you doubt any claim):
`GLOSSARY.md`; `doc/adr/0002-yaml-1.2-default.md`;
`crates/noyalib/src/streaming.rs` (`resolve_plain_ext` at L1620
is *the* scalar table); `crates/noyalib/src/parser/scanner.rs`
(§5.4, §6.8, §9.1.2 rules cited inline);
`crates/noyalib/src/de/config.rs` (every flag + default);
`crates/noyalib/tests/official_suite.rs` +
`crates/noyalib/tests/yaml_compliance_report.rs` (conformance
arithmetic).

**Provenance re-verify (one-liners):**
```bash
grep -n '"\.nan"\|"\.inf"' crates/noyalib/src/streaming.rs
grep -n 'yaml_version: YamlVersion::V1_2' crates/noyalib/src/de/config.rs
grep -n 'max_alias_expansions:\|alias_anchor_ratio:\|max_merge_keys:' crates/noyalib/src/de/config.rs
grep -n '§5\.4\|§6\.8\|§9\.1\.2' crates/noyalib/src/parser/scanner.rs
grep -n 'SKIP_LIST' crates/noyalib/tests/official_suite.rs
```

---

## 1. Documents and streams

A YAML **stream** is zero or more **documents**, bounded by
optional `---` (start) and `...` (end) markers. The first `---`
is optional; markers become mandatory between documents once
directives, `!!binary`-tag context, or a preceding `...` appear.

**Directives** are `%`-prefixed head lines: `%YAML 1.2` sets
version, `%TAG !x! tag:example.com,2026:` binds a tag-shorthand
prefix. Only one `%YAML` per document (§6.8.1).

**noyalib's strict rules** (scanner.rs, § cited inline):
- **§6.8:** directive *must* be followed by explicit `---`.
  Pending directive at stream end → error.
- **§6.8 / §9.1.2:** directive *must not* appear after content
  without intervening `...`.
- **ADR-0002:** `%YAML 1.1` is *recorded but not honoured* — no
  auto-flip of `legacy_*` flags. Silently honouring it would
  reintroduce the Norway problem, which 1.2 was created to fix.

> Regression case IDs (9MMA, B63P, RHX7, EB22, 9HCY, MUS6:1,
> ZYU8): see **reference.md §R2**.

---

## 2. Block vs flow, indentation, column tracking

**Block style** is the indentation-driven form:
```yaml
db:
  host: localhost
  port: 5432
```
**Flow style** is the JSON-shaped inline form: `db: {host: localhost, port: 5432}`. YAML mixes freely — flow can nest inside block and vice versa.

Indentation is *structure*, not decoration: a mapping value at
column *N+2* is a child of a key at column *N*. This is why
**column tracking is load-bearing** — every byte offset must
map to the correct visual column, or nesting silently mis-parses.

Two column-desync incidents shaped this code (see
`noyalib-failure-archaeology` for the full stories):
- **BOM incident** — UTF-8 BOM is three bytes, zero visual
  columns. Fix: `advance_by(3)` over the BOM *without* touching
  `col` (scanner.rs L1150–L1181).
- **Lone-CR incident** — classic-Mac `\r`-only breaks left column
  state stale. Fix (v0.0.14): recognise LF, CR, CRLF per §5.4
  (see §5 below).

---

## 3. Scalars and block-scalar chomping

Five scalar styles:
- **Plain** — no quotes, resolved by the plain-scalar table
  (§4): `port: 8080`.
- **Single-quoted** — `'literal ''with'' apostrophes'`. Only
  `''` escape.
- **Double-quoted** — full backslash-escape alphabet plus
  `\uXXXX` (paired for surrogates).
- **Literal block** (`|`) — every newline byte preserved.
- **Folded block** (`>`) — non-empty lines joined with a space;
  blank lines preserved as paragraph breaks.

**Chomping** on block scalars (stacked as `|-`, `>+`, etc.):
`-` = strip all trailing newlines; *(none)* = clip to one;
`+` = keep every trailing newline / blank line.

**noyalib gotcha (v0.0.14 fix).** For keep-chomped (`|+` / `>+`)
block scalars, `Document::span_at` now includes the *kept
trailing blank lines* in the returned span. Earlier releases
truncated at the last non-blank byte — byte-faithful for the
*value* but not for the *span*, breaking editor diagnostics.

> Worked-example matrix (six header combinations with literal
> byte-level output including folding rules): see **reference.md §R3**.

---

## 4. The plain-scalar resolution table (as implemented)

Every plain scalar walks `resolve_plain_ext`
(`streaming.rs:1620`). ~17 rows covering five null forms,
canonical + non-strict + legacy booleans, 12 inf/nan forms,
integer variants (decimal, `0x`, `0o`, bare-`0` octal, `u64` under
`lossless_u64`), sexagesimal, f64 fallback, then string.

**Precedence:** null → bool → hard-coded inf/nan → legacy booleans
→ integer parse → sexagesimal → **f64 fallback** → string.

> Full row-by-row table (verbatim source order): see
> **reference.md §R1**.

**The Norway problem.** YAML 1.1 boolean lexicon includes
`yes`/`no`/`on`/`off`; `country: NO` (Norway's ISO 3166) was
silently coerced to `false` for a decade in Ruby/pyyaml. YAML
1.2 narrowed the lexicon to `true`/`false` only. noyalib
defaults to 1.2; `legacy_booleans` opt-in reintroduces the
hazard.

**The bare-`nan` gotcha.** Nothing in the match table lists bare
`nan` — but the f64 fallback (`s.parse::<f64>()`) accepts
`"nan"`, `"inf"`, `"+inf"`, `"-inf"` case-insensitively (Rust
stdlib). So bare `nan` resolves to `NaN` even under strict 1.2.
This bit **mapping keys**: `{nan: 1, nan: 2}` collided because
both stringified to the same `NaN` bucket. The distinct-typed
KeyCollision guard (§8) catches similar collisions but the f64
fallback route was the surprise.

**Schema-strict mode.** `no_schema = true` short-circuits the
table — every plain scalar surfaces as
`Scalar::Str(Cow::Borrowed(s))`.

---

## 5. Line breaks (§5.4)

Per §5.4 a line break is **LF (`\n`), CR (`\r`), or CRLF
(`\r\n`)**. All three valid; parser normalises on input. CRLF
counts as one break (scanner.rs L554). Lone-CR (classic-Mac) was
added v0.0.14 (scanner.rs L1769).

**Gotcha.** Downstream code assuming `\n`-only (naive
`split('\n')`) mis-counts columns on CR-only input. External
consumers of `Document::source()` should re-normalise if they
care.

---

## 6. Anchors, aliases, merge keys — and DoS budgets

**Anchor** (`&name`) labels a node. **Alias** (`*name`) references
it inside the same document. Per §7.1 each document has its own
namespace; noyalib clears the anchor table on `DocumentEnd`.

**Merge key** (`<<`) — when the value is a mapping or a sequence
of mappings, merged keys are inherited unless overridden locally.

**Billion-laughs DoS.** Nested aliases
(`c: &c [*b, *b, *b, ...]` where `b` references `a` etc.)
multiply expanded size by 9 per level; ten levels ≈ 3.5 billion
terminal nodes from ~50 lines. Libyaml has historically crashed
on such inputs.

**noyalib's budgets** (`ParserConfig`, defaults from
`de/config.rs`):

| Knob | Default | Strict | Trip |
|------|--------:|-------:|------|
| `max_alias_expansions` | 1 024 | 100 | `Error::RepetitionLimitExceeded` (not `BudgetBreach`) |
| `max_document_length` | 64 MB | 1 MB | `Error::Parse` (also caps `alias_bytes` post-expansion) |
| `max_total_scalar_bytes` | 64 MB | 1 MB | `BudgetBreach::MaxTotalScalarBytes` |
| `max_merge_keys` | 10 000 | 1 000 | `BudgetBreach::MaxMergeKeys` |
| `alias_anchor_ratio` | `Some(10.0)` | `Some(5.0)` | `BudgetBreach::AliasAnchorRatio` (`aliases > ratio × anchors`) |
| `max_events` | 1 000 000 | 100 000 | `BudgetBreach::MaxEvents` |
| `max_nodes` | 250 000 | 25 000 | `BudgetBreach::MaxNodes` |
| `max_depth` | 128 | 64 | `Error::RecursionLimitExceeded` (not `BudgetBreach`) |

**Only six `BudgetBreach` variants exist** in `error.rs`:
`MaxEvents`, `MaxNodes`, `MaxTotalScalarBytes`, `MaxDocuments`,
`MaxMergeKeys`, `AliasAnchorRatio`. `max_alias_expansions` and
`max_depth` surface as top-level `Error::Repetition-` /
`Error::RecursionLimitExceeded`; `max_mapping_keys` and
`max_sequence_length` surface as `Error::Serialize(...)` (wart
documented in `noyalib-architecture-contract` §5.1).

`alias_anchor_ratio` is the *early-warning* signal — real files
rarely exceed 2–3 aliases per anchor; above 10 (5 in strict) is
bomb-shaped. Set to `None` to disable.

**MergeKeyPolicy** (`de/config.rs:973`, note real variants):
- **`Auto`** *(default)* — YAML 1.2 semantics: `<<` triggers
  automatic merge of the value into the enclosing mapping.
- **`AsOrdinary`** — treat `<<` as a plain string key. The
  mapping keeps a literal `<<` entry. Useful for round-tripping
  files where `<<` is a data key, not a merge instruction.
- **`Error`** — refuse any document containing `<<` with
  `Error::Custom`. For schema-strict pipelines.

> Note: GLOSSARY.md drift — it lists `{Auto, Disabled, Strict}`.
> The source of truth is `de/config.rs` — `{Auto, AsOrdinary,
> Error}`. Trust the code.

---

## 7. Tags

Explicit type annotations. Three families:
- **Core-schema tags** — `!!str`, `!!int`, `!!float`, `!!bool`,
  `!!null`, `!!seq`, `!!map`, `!!binary`. noyalib **never
  strips** these — they carry semantics (`!!str 42` forces
  string).
- **Custom tags** — `!shopping`, `!myapp/config`. Carried through
  as `Value::Tagged`; a `TagRegistry` can transform them inline
  on the streaming path.
- **Verbatim tags** — `!<tag:yaml.org,2002:str>` (rare).

**Shorthand.** `!!x` expands to `tag:yaml.org,2002:x` (§6.8.2).
Custom prefixes come from `%TAG !x! tag:example.com,2026:`.

**`!!binary`** — RFC 4648 base64 (§10.4). Decoded on the
streaming path (`streaming.rs` L1095–L1115); failure →
`Error::Deserialize("!!binary: {why}")`. Deserialising into a
`String` target defaults to tag-mismatch error; set
`ignore_binary_tag_for_string = true` for pyyaml-style advisory
behaviour (returns the literal base64 source).

---

## 8. Keys — and the KeyCollision guard

YAML permits any node type as a mapping key, including complex
keys (`? key\n: value`). noyalib exposes two mapping types:

- **`Mapping`** — string-keyed (`IndexMap<String, Value>`).
  Default, JSON-compatible.
- **`MappingAny`** — `Value`-keyed. Use when non-string keys
  matter for fidelity.

When YAML produces a non-string key (`1`, `true`, `null`) and the
target is `Mapping`, the key is **stringified on entry**. This is
where the **distinct-typed KeyCollision guard** lives
(`error.rs:509`, `Error::KeyCollision(String)`). Given
`1: one` and `"1": two`, both stringify to `"1"`; silently
dropping one is data loss, so noyalib rejects with
`KeyCollision("1")` at parse time.

Streaming path bypass (`de.rs:405-421`): serde asks the streaming
deserializer for `String` keys, stringifying typed scalars
*before* `ValueVisitor::visit_map` can distinguish `1` from
`"1"`. The `Value` target therefore routes through the AST
loader (which owns the collision check and DoS budgets).

**DuplicateKeyPolicy** (unrelated axis — same string key twice):
`First` (keep first) / **`Last`** *(default, YAML 1.2)* /
`Error` (reject).

---

## 9. YAML 1.1 vs 1.2 — the flags that matter

Per ADR-0002, **noyalib defaults to YAML 1.2 strict semantics.**
Three 1.1 legacy behaviours are opt-in on `ParserConfig`:

- **`legacy_booleans`** — off: `yes`/`no`/`on`/`off` → string;
  on: → bool (Norway problem).
- **`legacy_octal_numbers`** — off: `0644` → int 644; on: → 420.
- **`legacy_sexagesimal`** — off: `60:00` → string; on: → int 3600.

`ParserConfig::version(YamlVersion::V1_1)` flips all three as a
bundle; fine-grained flags remain callable individually.

- **`strict_booleans`** — narrows 1.2 further: only `true`/`false`
  (lowercase) are boolean; `True`/`TRUE` become strings. Off by
  default.
- **`no_schema`** — every plain scalar surfaces as string;
  table (§4) bypassed entirely.

> Long-form matrix with hazard column, precedence ordering, and
> flag-interaction notes: see **reference.md §R5**.

---

## 10. Official YAML Test Suite

The [yaml/yaml-test-suite](https://github.com/yaml/yaml-test-suite)
corpus. Each case is a wrapper with `yaml:`, `json:`, `fail:`,
`tags:`. IDs are four-character codes (`9MMA`, `RHX7`, `ZYU8`).

- `tests/yaml-test-suite/` — vendored corpus.
- `tests/official_suite.rs` — regression-net. Scores
  `pass / (total − skip)`, asserts `compliance >= 94.0`.
- `tests/yaml_compliance_report.rs` — the *gap report*. No
  assertions; writes `target/yaml-compliance-report.md`. Hard
  floor `total >= 350` guards against vacuous 0/0.

**Ground-truth reminders (assert every time you cite them):**
```
official_suite.rs::SKIP_LIST     = &[]        # zero entries
yaml_compliance_report.rs::SKIP  = &[]        # zero entries
compliance floor                 = 94.0%      # assertion
total-cases floor                = 350        # regression guard
```

**Drift alert.** Top-level and crate READMEs claim "100% strict
compliance — 387/387 attempted, 0 failures, 19 skipped". Test
files carry **empty** SKIP_LIST and **94%** floor. Report what
the TEST FILES say (skip = 0 today) — README numbers are
aspirational and may lag.

> Wrapper-marker table, six report classifications, full
> walkthrough: see **reference.md §R4**.

---

## Cross-references

- **Extended tables** (full `resolve_plain_ext`, directive cases,
  chomping matrix, official-suite walkthrough, 1.1/1.2 long
  matrix): `reference.md` here.
- **Flags in depth** (`ParserConfig`, presets): `noyalib-config-and-flags`.
- **Parser/CST internals** (green tree, event stream, streaming
  vs loader): `noyalib-architecture-contract`.
- **Historical fixes** (BOM, lone-CR, span_at): `noyalib-failure-archaeology`.
- **Change control** (spec-conformance PRs): `noyalib-change-control`.
