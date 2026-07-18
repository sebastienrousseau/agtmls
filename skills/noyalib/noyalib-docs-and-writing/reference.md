<!-- SPDX-FileCopyrightText: 2026 Noyalib -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->

# noyalib-docs-and-writing — reference material

Complements `SKILL.md` in this directory. Repo v0.0.14, skill
date-stamp **2026-07-08**. Load this when you need the exact SPDX
header shapes per file type, the ADR process and skeleton, or the
release-notes template. `SKILL.md` keeps the docs-of-record inventory,
rustdoc / commit-message house style, the writing rules, and the
pre-PR self-check.

---

## R1. SPDX / REUSE discipline

REUSE 3.3. Every file is licensed inline or via `REUSE.toml` blanket
annotations. CI has a REUSE gate.

Header shapes by file type — use verbatim:

**Rust (`.rs`)** — before `//!` module docs:

```rust
// SPDX-License-Identifier: MIT OR Apache-2.0
// Copyright (c) 2026 Noyalib. All rights reserved.
```

**YAML (`.yml`, `.yaml`)** — before the first key:

```yaml
# SPDX-FileCopyrightText: 2026 Noyalib
# SPDX-License-Identifier: MIT OR Apache-2.0
```

**Release-notes Markdown** — first two lines:

```markdown
<!-- SPDX-FileCopyrightText: 2026 Noyalib -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
```

**Top-level Markdown** (README.md, CHANGELOG.md, GETTING_STARTED.md,
MIGRATION.md, GLOSSARY.md, GOVERNANCE.md, CODE_OF_CONDUCT.md,
SECURITY.md, SUPPORT.md) — covered by REUSE.toml blanket. For NEW
top-level `.md`, prefer inline headers if the file will travel
standalone (release notes); otherwise extend REUSE.toml.

**Config, fixtures, generated artefacts** — covered by REUSE.toml
wildcards. New fixture directories either match an existing wildcard or
get a fresh `[[annotations]]` block.

Copyright year is the current release year. Don't rewrite history on
rollover — only new files get the new year.

---

## R2. ADR process

Live under `doc/adr/`. Format is Nygard's shape: Context / Decision /
Consequences / Alternatives considered / References. Verify against
`doc/adr/TEMPLATE.md` and the in-tree ADRs (0001-0005).

**When to add one** (from `doc/adr/README.md`):

- Change to data model, public API surface, dependency floor, or a core
  invariant (unsafe policy, MSRV, YAML-version default).
- Change to what parsers or loaders output on a given input.
- A decision with plausible alternatives a future contributor might
  propose the opposite of.

**When *not* to**: type-system-encoded decisions, well-known Rust idiom,
routine implementation choices (those go in commit bodies and code
comments).

**Numbering**: next integer, zero-padded to 4. Confirm with
`ls doc/adr/` — currently through 0005.

**Status lifecycle**: `proposed` → `accepted` → optionally `superseded
by [NNNN]` or `deprecated`. Immutable once accepted, except:

- **Post-implementation updates** — when a `proposed` ADR is piloted,
  append an inline "Concrete results from the pilot" section rather than
  editing Context/Decision. See `0005-workspace-split.md`: after the
  v0.0.12 (`noyalib-wasm`) and v0.0.13 (`noyalib-mcp`) pilots, the ADR
  gained a concrete-outcomes section. It stays authoritative for the
  whole split project; only `superseded by` on rollback rewrites the
  status.

Skeleton (verified against `TEMPLATE.md`):

```markdown
# NNNN. Title (imperative, one line)

- **Status:** proposed | accepted | superseded by `NNNN` | deprecated
- **Date:** YYYY-MM-DD
- **Authors:** Name

## Context

Forces at play — technical, organisational, social. Cite code,
benchmarks, dependencies. The reader should understand *why* a
decision is even being made.

## Decision

Directive form: "We will…", "noyalib does X…". No hedging.

## Consequences

- **Positive:** what this enables
- **Negative:** what this costs
- **Neutral:** what changes shape without being obviously good or bad

## Alternatives considered

Each rejected option gets a short sub-section: "would have looked
like X; rejected because Y". Leaves a paper trail.

## References

Issues, PRs, prior art, design notes, external papers.
```

After adding a new ADR, update the index table in `doc/adr/README.md`.

---

## R3. Release-notes template

One file per release, SPDX headers inline. Shape from `v0.0.14`
(loader-parity cut) and `v0.0.13` (noyalib-mcp satellite split):

```markdown
<!-- SPDX-FileCopyrightText: 2026 Noyalib -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->

# noyalib vX.Y.Z Release Notes

The **<one-phrase headline>** cut. <2-sentence pitch: what this
release closes / adds / fixes. Cite the concrete user-visible
change — not "internal cleanup".>

No breaking API changes. No MSRV change (still 1.85). No new
runtime dependencies.
<Adjust honestly if any of these three IS the release story.>

## Why this release exists

<Prose. The specific problem this cut solves, with a code sample
of the failing YAML / reproducer where applicable. Cite the
observation that motivated the fix — user report, CI signal,
fuzz finding.>

## What changed

### <Category 1 — e.g., Loader-parity (security)>
- <bullet with `Error::Variant` / `Type::method` / config-field
  spellings. Cite the file that changed.>

### <Category 2 — e.g., API additions>
- <bullet>

### Testing / tooling
- <new tests, benches, fuzz targets and what they guard>

## What did not change

- No breaking API changes. `Error` / `ErrorKind` are `#[non_exhaustive]`.
- No MSRV change. Still `rust-version = "1.85.0"`.
- No new runtime dependencies.
- `#![forbid(unsafe_code)]` intact at every crate root.
<List explicitly. Fights oversell.>

## Follow-ups noted for vX.Y.(Z+1)

- <known limitation, small enough to defer, big enough to name>
```

Lockstep-satellite section (when a satellite ships in the same cut,
per v0.0.13):

```markdown
## What ships from <satellite> repo

[`sebastienrousseau/<name>@vX.Y.Z`](https://…) publishes across
<N> channels, each with its own attestation:

1. **crates.io** — …
2. **npm** — …
3. **GHCR** — …
4. **MCP Registry** — …
```
