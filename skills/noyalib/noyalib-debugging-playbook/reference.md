# noyalib debugging playbook — reference material

Complements `SKILL.md` in the same directory (`noyalib-debugging-playbook`).
Date-stamp: 2026-07-08. Load this file when the cardinal triage and the
runbook path in `SKILL.md` haven't pinned the bug and you need the
exhaustive tables, verbatim excerpts, and the full trap set.

Provenance covering both `SKILL.md` and this file lives in
`SKILL.md` §"Provenance and maintenance". Re-verify against the source
tree before trusting any claim here.

## §routing-full — full loader routing table

Referenced from `SKILL.md` §"THE cardinal triage question" (routing
table). The three primary rows live in SKILL.md; the full six-row
matrix follows.

| T                          | Config knobs                                       | Path                                 | Where                                           |
| -------------------------- | -------------------------------------------------- | ------------------------------------ | ----------------------------------------------- |
| any typed `T` (not `Value`) | all defaults                                       | **streaming** (`streaming.rs`)       | `de.rs` `stream_eligible == true`               |
| `Value`                    | `tag_registry.is_none()` (i.e. no registry active) | **`NoSpanLoader`** (span-free)       | `de.rs:454` `is_value_target::<T>()` fast path  |
| `Value`                    | `tag_registry.is_some()`                           | **streaming** (registry strips tags) | `value_target_bypass == false`                  |
| any typed `T`              | any non-default config knob above                  | **`Loader`** (span-full) then serde  | `de.rs:472` `#[cfg(feature = "std")]` block     |
| `Spanned<T>`               | anything                                           | **`Loader`** (needs the SpanTree)    | same span-full block                            |
| `cst::parse_document`      | n/a — separate entrypoint                          | **CST green-tree** parser            | `crates/noyalib/src/cst/document.rs`            |

Nuance you will hit: **v0.0.14 excludes `Value`-target from streaming
unless a TagRegistry is active.** The rationale is embedded in the
comment at `de.rs:405-414`: serde's streaming path asks for `String`
keys, which stringifies typed scalars before `ValueVisitor::visit_map`
can tell `1` from `"1"` — the distinct-typed `KeyCollision` guard is
unreachable there. The `NoSpanLoader` owns that check plus the DoS
budgets. See `bc8f798 fix(loader): plug distinct-typed key collision
on Value fast path` for the fix that made this so.

## §symptom-full — full symptom table

Referenced from `SKILL.md` §"Symptom table". The top-5 most-common
rows live in SKILL.md; the complete set follows here (including the
top-5, so this table is self-contained).

Each row cites the file/test/commit that pins the behaviour so you can
verify against source, not against my memory.

| Symptom | Likely cause | First check | Verify against |
| ------- | ------------ | ----------- | -------------- |
| "Parses but data missing (some keys gone)" | `DuplicateKeyPolicy` collapsing genuine duplicates, or (pre-0.0.14) distinct-typed collision silently overwriting | Set `config.duplicate_key_policy = DuplicateKeyPolicy::Error` and re-run | `tests/dup_key_spans.rs::distinct_typed_keys_collide_loudly` (`crates/noyalib/tests/dup_key_spans.rs:186`) |
| "Works as `struct T`, fails as `Value`" (or vice versa) | Loader divergence — streaming vs `NoSpanLoader` vs `Loader` | Run the discriminating experiment above | `tests/no_span_loader_parity.rs` (`crates/noyalib/tests/no_span_loader_parity.rs`) |
| "Span points at wrong bytes" | CST walker; five separate fixes landed in v0.0.14 cycle | `git log --oneline -20 -- crates/noyalib/src/cst/` | Commits `f8fe929`, `1f76951`, `af7a9bd`, `1d72687` |
| Span includes trailing blanks | `span_at` trims trailing blanks; raw event spans don't | Compare `doc.span_at(path)` vs `Spanned<T>` extents | `tests/dup_key_spans.rs::spanned_fields_stay_aligned_after_duplicate_key` |
| "Alias resolves to alias indicator, not the anchored value" | Fixed in `f8fe929 fix(cst): resolve alias references through to the anchor value span` | `git show f8fe929` | v0.0.14 |
| "Block-collection value span drops the first line's indent" | Fixed in `1f76951` | `git show 1f76951` | v0.0.14 |
| "Kept trailing blanks vanish from a `\|+` scalar's span" | Fixed in `af7a9bd fix(cst): keep-chomped block scalars retain kept trailing blanks in span_at` | `git show af7a9bd` | v0.0.14 |
| "Implicit-null span returns the `:` indicator's bytes" | Fixed in `1d72687` — implicit-null now reports `None` | `git show 1d72687` | v0.0.14 |
| `no_std` build broken but CI green | Cache poisoning — see `feedback_ci_cache_poisoning` memory + `noyalib-ci-and-release` §2 (THE cache-poisoning doctrine) | `grep -n "CARGO_TARGET_DIR" .github/workflows/*.yml` | `.github/workflows/security.yml:58` header comment ("per-matrix-target CARGO_TARGET_DIR") |
| Column desync, spurious indent errors on real files | Scanner line-break handling: lone CR (classic-Mac) or leading BOM | `git show 70c77cb` (lone-CR fix), `git show 3304f4c` (BOM v0.0.10) | scanner tests |
| "Budget error unexpectedly" | One of the 12 `ParserConfig` budget knobs fired (only **6** flow into `BudgetBreach`; the others surface as `RecursionLimitExceeded`, `RepetitionLimitExceeded`, `Serialize`, or `Parse` — see §budget-full below) | Read the error — see §budget-full below | `crates/noyalib/src/error.rs:161` `BudgetBreach` enum |
| `Error::Serialize("sequence length limit exceeded")` on **parse** | Wart: `max_sequence_length` / `max_mapping_keys` still use `Error::Serialize` spelling on the parse side | See "budget error spelling wart" in §budget-full | `crates/noyalib/src/parser/loader.rs:575, 675, 1063, 1135` |
| `next_value_seed called after MapAccess exhausted` | Serde caller misused MapAccess — same `depth` leak class as issue #46 | Fix the caller | `crates/noyalib/src/streaming.rs:1363` |
| `RecursionLimitExceeded` on shallow-but-wide document (e.g. `pnpm-lock.yaml`) | Old bug from `{}` leaking depth — fixed | Confirm you're on v0.0.14+ | `tests/issue_46.rs` (`crates/noyalib/tests/issue_46.rs`) |

## §budget-full — full budget inventory (which cap fired)

Referenced from `SKILL.md` §"Symptom table" and the runbook. SKILL.md
keeps a short summary; the complete mapping across the 12 knobs, 6
`BudgetBreach` variants, and the `Serialize` / `RecursionLimitExceeded`
/ `RepetitionLimitExceeded` / `Parse` overflows follows.

`BudgetBreach` in `crates/noyalib/src/error.rs:161`:

- `MaxEvents { limit, observed }`
- `MaxNodes { limit, observed }`
- `MaxTotalScalarBytes { limit, observed }`
- `MaxDocuments { limit, observed }`
- `MaxMergeKeys { limit, observed }` — the merge parity test at
  `no_span_loader_parity.rs:126` matches on this variant directly
- `AliasAnchorRatio { ratio, anchors, aliases }` — billion-laughs guard

`Error::Budget(BudgetBreach::...)` for the six above.
`ParserConfig` has **12** budget knobs (`max_depth`,
`max_document_length`, `max_alias_expansions`, `max_mapping_keys`,
`max_sequence_length`, `max_events`, `max_nodes`,
`max_total_scalar_bytes`, `max_documents`, `max_merge_keys`,
`alias_anchor_ratio`, `max_include_depth`) but only the **6**
`BudgetBreach` variants above flow through `Error::Budget`. The
others surface as:

- `max_depth` → `Error::RecursionLimitExceeded { depth }`
  (see `tests/issue_46.rs:127`).
- `max_alias_expansions` → `Error::RepetitionLimitExceeded`
  (NOT `BudgetBreach::MaxAliasExpansions` — that variant does
  not exist).
- `max_mapping_keys` / `max_sequence_length` →
  `Error::Serialize("mapping key limit exceeded" /
  "sequence length limit exceeded")` — the wart documented below.
- `max_document_length` → `Error::Parse`.
- `max_include_depth` → include-feature specific.

**Budget error spelling wart.** `max_sequence_length` and
`max_mapping_keys` are enforced by the loader with the message
`"sequence length limit exceeded"` / `"mapping key limit exceeded"`
wrapped in **`Error::Serialize`**, not `Error::Budget`. This mismatch
is real and callers pattern-match on message text (see
`no_span_loader_parity.rs:82` — `msg.contains("sequence length limit")`).
Don't "fix" it without checking the callers first; it's tracked
policy, not an oversight.

## §traps-extended — additional traps with stories

Referenced from `SKILL.md` §"Traps with stories". The top-3 most
operationally-hit traps stay in SKILL.md; the remaining two follow.

### (d) `NaN` key equality is a landmine for the collision check

**Trap:** `Value::Number(Float(NaN)) != Value::Number(Float(NaN))`
(IEEE-754 semantics).

**Why it bites:** the typed-key collision check in
`NoSpanLoader::MappingKey::typed_keys` compares by `Value` equality.
Two `NaN` keys would appear "different" and never collide, but they
both stringify to `.nan` and so overwrite via the string-key map.
`Float(NaN)` also breaks any `HashSet<Value>` you might reach for.
Loader scalar resolution at `parser/loader.rs:1364` recognises
`.nan/.NaN/.NAN` — verify before assuming an input parses.

**Avoid:** don't add `HashSet<Value>` deduping for keys; the
`typed_keys` parallel-vec design at `parser/loader.rs:843` exists
because equality on `Value` is not universally reflexive.

### (e) `cargo vet fmt` strips TOML comments — rationale goes in the commit

**Trap:** you write the reason for a `supply-chain/config.toml`
exemption inline as a `#` comment. `cargo vet fmt` (or the normal
sort) drops it. Reviewers later ask why the exemption exists and there
is no answer.

**Why it bites:** exemption context evaporates silently.

**Avoid:** put the rationale in the commit message. The recent
`chore(supply-chain): update cargo-vet exemptions for the Dependabot
bumps` (`5c41ef3`) commit body is the model — a paragraph per
crate/version explaining *why* the exemption is safe.
