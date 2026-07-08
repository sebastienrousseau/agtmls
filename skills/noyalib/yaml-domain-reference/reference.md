# YAML domain reference — extended tables

Complements `SKILL.md` in this directory. Load when the terse SKILL.md summary
is not enough — spec-conformance work, cross-checking `resolve_plain_ext`,
tracing directive-regression IDs, verifying block-scalar chomping edge cases,
or drafting the official-suite integration.

Date-stamp: 2026-07-08.

---

## R1. Full `resolve_plain_ext` table (verbatim, source-order)

This is *the* table. Every plain scalar in a noyalib parse walks
`resolve_plain_ext` (`crates/noyalib/src/streaming.rs:1620`). The literal
match arms, in source order:

| Lexical form | Type | Notes |
|--------------|------|-------|
| `""`, `~`, `null`, `Null`, `NULL` | `Null` | Five null forms |
| `true` | `Bool(true)` | Canonical |
| `false` | `Bool(false)` | Canonical |
| `True`, `TRUE` | `Bool(true)` | Only when `!strict` |
| `False`, `FALSE` | `Bool(false)` | Only when `!strict` |
| `.inf`, `.Inf`, `.INF`, `+.inf`, `+.Inf`, `+.INF` | `Float(f64::INFINITY)` | Six forms |
| `-.inf`, `-.Inf`, `-.INF` | `Float(f64::NEG_INFINITY)` | Three forms |
| `.nan`, `.NaN`, `.NAN` | `Float(f64::NAN)` | Three forms |
| `yes`, `Yes`, `YES`, `y`, `Y` | `Bool(true)` | Only under `legacy_booleans` |
| `no`, `No`, `NO`, `n`, `N` | `Bool(false)` | Only under `legacy_booleans` (**Norway problem**) |
| `on`, `On`, `ON` | `Bool(true)` | Only when `!strict && legacy_booleans` |
| `off`, `Off`, `OFF` | `Bool(false)` | Only when `!strict && legacy_booleans` |
| decimal integer, `0x…`, `0o…` | `Int(i64)` / `Uint(u64)` under `lossless_u64` | See integer forms below |
| bare `0`-prefix octal (e.g. `0644`) | `Int` | Only under `legacy_octal_numbers` |
| `H:MM` / `H:MM:SS` | `Int` / `Float` | Only under `legacy_sexagesimal` |
| anything `s.parse::<f64>()` accepts | `Float(f64)` | **Fallback** — see nan-key gotcha in SKILL.md §4 |
| everything else | `Str(Cow::Borrowed(s))` | |

**Precedence order:** null → bool → hard-coded inf/nan → legacy booleans →
integer parse → sexagesimal (if enabled) → **f64 fallback** → string.

**Integer forms.**
- `0xDEAD` / `0XDEAD` — hex (both cases).
- `0o755` / `0O755` — YAML 1.2 explicit octal.
- `0644` — YAML 1.1 bare octal, gated behind `legacy_octal_numbers`.
- Under `lossless_u64` (feature-gated), integers in
  `(i64::MAX, u64::MAX]` become `Uint(u64)` instead of falling
  through to `Float(f64)`.

**Sexagesimal.** `60:00` → 3600, `1:30:00` → 5400. Base-60,
components other than the first must be `0..=59`. Gated behind
`legacy_sexagesimal`.

**Schema-strict mode.** Setting `no_schema = true` short-circuits
the entire table — every plain scalar surfaces as
`Scalar::Str(Cow::Borrowed(s))`. Useful when you want the file's
literal text with zero coercion.

---

## R2. Directive regression case list

Cases pinned in `crates/noyalib/src/parser/scanner.rs`, cited inline with
§ from YAML 1.2.2:

| Case ID | Rule enforced | Behaviour |
|---------|---------------|-----------|
| **9MMA** | §6.8: directive must be followed by explicit `---` | Pending directive at stream end → error |
| **B63P** | §6.8: directive must be followed by explicit `---` | Pending directive at stream end → error |
| **RHX7** | §6.8 / §9.1.2: no directive after content without `...` | Post-content directive → error |
| **EB22** | §6.8 / §9.1.2: no directive after content without `...` | Post-content directive → error |
| **9HCY** | §6.8 / §9.1.2: no directive after content without `...` | Post-content directive → error |
| **MUS6:1** | §6.8 / §9.1.2: no directive after content without `...` | Post-content directive → error |
| **ZYU8** | `%YAML 1.1 1.2` (extra numeric token) tolerated | Accepted — spec productions allow it |

**Policy reminder (ADR-0002).** `%YAML 1.1` is *recorded but not honoured* —
it does not auto-flip `legacy_*` flags. Silently honouring a stale `%YAML 1.1`
directive would reintroduce the Norway problem.

---

## R3. Block-scalar chomping — worked-example matrix

Base fragment (spaces marked `·`, newlines marked `↵`):

```
literal: |·
··line1↵
··line2↵
··↵
··↵
```

| Header | Name | Result string | Trailing newlines kept |
|--------|------|---------------|------------------------|
| `|`    | clip | `"line1↵line2↵"` | exactly one |
| `|-`   | strip | `"line1↵line2"` | zero |
| `|+`   | keep | `"line1↵line2↵↵↵"` | all trailing blanks |
| `>`    | clip (folded) | `"line1 line2↵"` | folded; one final |
| `>-`   | strip (folded) | `"line1 line2"` | folded; zero |
| `>+`   | keep (folded) | `"line1 line2↵↵↵"` | folded; all kept |

**noyalib span gotcha (v0.0.14 fix).** For keep-chomped (`|+` / `>+`) block
scalars, `Document::span_at` now includes the *kept trailing blank lines* in
the returned span. Earlier releases truncated the span at the last non-blank
byte — byte-faithful for the *value* but not for the *span*, which broke
editor diagnostics that highlighted keep-chomped blocks.

**Folding rules (`>`):**
- Consecutive non-empty lines join with a single space.
- Blank lines are preserved as literal newlines (paragraph breaks).
- More-indented lines (relative to the block's indent) are NOT folded — they
  keep their own line breaks.

---

## R4. Official YAML Test Suite — full integration walkthrough

**What it is.** The
[yaml/yaml-test-suite](https://github.com/yaml/yaml-test-suite) canonical
corpus. Each case is a wrapper document with `yaml:` (source), `json:`
(expected data-model projection), `fail:` (true if the input is invalid),
and `tags:`. Case IDs are four-character codes like `9MMA`, `RHX7`, `ZYU8`.

**Wrapper markers.** The suite uses visual whitespace markers that noyalib
decodes in `official_suite.rs::decode_test_suite_markers` and
`yaml_compliance_report.rs::decode_markers`:

| Marker | Codepoint | Meaning |
|--------|-----------|---------|
| `␣` | U+2423 | space |
| `⇥` | U+21E5 | tab |
| `↵` | U+21B5 | LF |
| `↓` | U+2193 | CR |
| `⇔` | U+21D4 | BOM |
| `∎` | U+220E | strip rest of line |
| `»` / `———»` chains | U+00BB | tab |

**How noyalib integrates it.**
- `tests/yaml-test-suite/` — vendored corpus.
- `tests/official_suite.rs` — the regression-net. Passes are scored as
  `pass / (total − skip)`. Asserts `compliance >= 94.0`.
- `tests/yaml_compliance_report.rs` — the *gap report*. Classifies every
  case into six outcomes:
  1. `Pass`
  2. `Skip`
  3. `FailParseError`
  4. `FailValueMismatch`
  5. `FailLenient`
  6. `FailNonScalarKey`

  Writes `target/yaml-compliance-report.md`. No assertions — it is a report,
  not a regression net. Includes a hard floor (`total >= 350`) so a
  wrapper-parse regression can't silently vacuously pass at 0/0.

**The conformance claim — what the code actually says.**
- `official_suite.rs::SKIP_LIST` — currently **`&[]`** (empty). Both
  categories in the file (`Stricter rejection still missing`, `Block parser
  corners`) are present as comments with zero entries.
- `yaml_compliance_report.rs::SKIP_LIST` — currently **`&[]`** (empty).
- Threshold in `official_suite.rs`: `compliance >= 94.0` (not 100 — the
  assertion floor).

**Drift alert.** The top-level `README.md` claims "100% strict compliance —
387/387 attempted, 0 failures, 19 deliberately skipped" (L359–L362, L423).
The crate `README.md` (`crates/noyalib/README.md`) repeats the same
`387/387` / `19 skipped` phrasing. But the test files carry an **empty**
SKIP_LIST and a **94%** assertion floor. Report what the TEST FILES say
(`total = pass + fail + skip`, skip = 0 today) when reasoning about
conformance — the README numbers are aspirational / prose and may lag the
code.

**Suite value at a glance.**
```
official_suite.rs::SKIP_LIST     = &[]        # zero entries
yaml_compliance_report.rs::SKIP  = &[]        # zero entries
compliance floor                 = 94.0%      # assertion
total-cases floor                = 350        # regression guard
```

---

## R5. YAML 1.1 vs 1.2 — long-form flag matrix

Per ADR-0002, **noyalib defaults to YAML 1.2 strict semantics.** The three
1.1 legacy behaviours are opt-in as fine-grained flags on `ParserConfig`.

| Flag | Off (1.2 default) | On (1.1 opt-in) | Hazard |
|------|-------------------|------------------|--------|
| `legacy_booleans` | `yes`/`no`/`on`/`off` → string | → bool | Norway problem: `country: NO` → `false` |
| `legacy_octal_numbers` | `0644` → int 644 (decimal) | → int 420 (octal) | Silent value drift for UNIX file-mode literals |
| `legacy_sexagesimal` | `60:00` → string | → int 3600 | Time literals silently coerced to base-60 |
| `strict_booleans` | `True`/`TRUE` → bool | `True`/`TRUE` → string | Narrows *1.2* lexicon further; strict-lowercase only |
| `no_schema` | Plain-scalar table (§4) applies | Table bypassed — everything → string | Loses coercion entirely |

**Version bundle.** Setting `ParserConfig::version(YamlVersion::V1_1)` flips
`legacy_booleans`, `legacy_octal_numbers`, and `legacy_sexagesimal` on as a
bundle. The fine-grained flags remain callable individually — e.g. "1.1
booleans but reject octal `0644`" is a valid configuration.

**Ordering of precedence.**
- `no_schema = true` short-circuits everything else — scalars never reach
  the resolution table.
- `strict_booleans = true` filters the boolean-canonical output *after* the
  legacy lookup — so `legacy_booleans + strict_booleans` is coherent
  (accept `yes/no`, reject `True/TRUE`).
- Legacy octal and sexagesimal are independent of the boolean axis.

---

## Cross-references (back to SKILL.md)

- Terse concept overview (documents/streams, block vs flow, scalars,
  anchors, tags, keys): **SKILL.md §§1–3, 6–8**.
- Load-bearing gotchas (Norway problem, nan-key trap, KeyCollision,
  alias budgets): **SKILL.md §§4, 6, 8**.
- `MergeKeyPolicy` variants and DoS-budget table: **SKILL.md §6**.
- Ground-truth reminders (`SKIP_LIST = &[]`, 94% floor):
  **SKILL.md §10** (summary) and **R4** above (walkthrough).
