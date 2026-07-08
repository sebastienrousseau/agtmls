# cross-language-port — trigger & routing corpus

A fixture that pins *when this skill should load*. Each prompt has an
expected verdict:

- **FIRE** — load the skill and run the six-phase loop.
- **DEFER** — a micro-port; do it inline in the conversation, don't load the
  skill.
- **ROUTE** — not a behaviour-preserving cross-language port; hand off (the
  target is named).

**Acceptance test:** a cold reader (or a fresh model) classifies all 20
correctly using **only** the skill's frontmatter `description` plus its
`## When NOT to use this skill` section. Any misclassification is a
*description bug* — fix the frontmatter, not the corpus.

## FIRE (load the skill)

| # | Prompt | Why it fires |
|---|--------|--------------|
| 1 | "Port this Python IBAN validator to Rust." | explicit "port … to <lang>", multi-function module |
| 2 | "Translate this Bash deploy script to Python." | "translate to <lang>", a whole script |
| 3 | "Rewrite this Go rate limiter in Rust." | "rewrite in <lang>", preserves behaviour |
| 4 | "Give me the TypeScript equivalent of this JS module." | "give me the <lang> equivalent of existing code" |
| 5 | "Convert this Ruby CSV parser to Python." | "convert this to <lang>" |
| 6 | "Reimplement this C++ colour parser in Swift." | "reimplement <X> in <lang>" |
| 7 | "I need this Python service's core loop in Go." | cross-language port of an existing unit |

## DEFER (micro-port — inline, don't load the skill)

| # | Prompt | Why it defers |
|---|--------|---------------|
| 8 | "Port this 3-line helper to Rust." | micro-snippet — "do those inline" |
| 9 | "What's the Python equivalent of Rust's `unwrap_or`?" | single-expression idiom lookup, not a module port |
| 10 | "Give me the Go one-liner for this `map`+`filter`." | one expression; inline |
| 11 | "How would you write this two-line function in TypeScript?" | trivial size; inline |

## ROUTE (not a behaviour-preserving cross-language port)

| # | Prompt | Verdict | Route to |
|---|--------|---------|----------|
| 12 | "Modernize this C++17 code to C++23." | ROUTE | in-language migration — general coding, not this skill |
| 13 | "Upgrade this module from Python 2 to Python 3." | ROUTE | in-language migration |
| 14 | "Convert this ES5 file to modern ESNext." | ROUTE | in-language migration |
| 15 | "Refactor this Rust module for readability." | ROUTE | same-language refactor |
| 16 | "Port this to Rust but also add caching and metrics." | ROUTE | behaviour-changing — clarify new contract first (redesign) |
| 17 | "Rewrite this in Rust with a faster new algorithm." | ROUTE | redesign — the algorithm/behaviour changes, so equivalence (Phase 5) doesn't apply |
| 18 | "Translate this README from English to French." | ROUTE | natural-language translation, not code |
| 19 | "Wrap this C library with a Python binding." | ROUTE | FFI/binding, not a reimplementation port (boundary rules apply, but the code isn't re-authored) |
| 20 | "Split this monolith into microservices." | ROUTE | architecture change, not a port |

## Boundary notes (the calls a description must make cleanly)

- **DEFER vs FIRE** turns on *size*: a few lines → inline; a module / script /
  CLI / non-trivial function → FIRE. Row 8 vs row 1.
- **ROUTE vs FIRE** turns on *behaviour preservation*: if the ask changes the
  contract (add features, new algorithm, in-language upgrade), it is not a
  port — rows 16/17 vs row 3.
- **Row 19 (bindings)** is the subtlest: wrapping a library via FFI keeps the
  original code and adds a seam — that's the §"Data-boundary & interop rules"
  territory, but it is *not* re-authoring the logic in the target language,
  so the skill does not own it.

## Result (last run: 2026-07-08)

Classified all 20 from the frontmatter `description` + `## When NOT to use
this skill` alone: **20/20 correct.** The description's trigger verbs cover
FIRE; "Not for micro-snippets (do those inline)" covers DEFER; "behaviour-
changing redesigns (that's a rewrite, clarify intent first)" plus the
When-NOT bullets on redesigns and in-language migration cover ROUTE. No
description change required.
