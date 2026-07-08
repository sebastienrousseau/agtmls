<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Definition of Done (shared reference)

A standing checklist that any skill's **Verification** section can link to
instead of restating it. If a change can't tick these, it isn't done.

## Every change

- [ ] **It runs.** The change was exercised end-to-end and observed to do
      what it claims — not just "it compiles / typechecks / looks right".
- [ ] **Tests prove it.** New behaviour ships with a test in the same commit;
      a bug fix ships with a test that *fails on the pre-fix tree*.
      Coverage-only tests that execute code without asserting semantics do
      not count ("wrong-but-green" is the enemy).
- [ ] **Green toolchain.** Formatter, linter, and type/compile checks pass
      with the project's own tools (no blanket lint suppression to dodge a
      warning).
- [ ] **No secrets.** No API keys, passwords, or tokens introduced into
      source; all read from env or a vault.
- [ ] **Docs match reality.** Any user-visible change updates the docs of
      record in the same change, not as a follow-up.
- [ ] **One logical change.** The diff is a single reviewable unit; unrelated
      refactors go in their own change.
- [ ] **Conventional, signed commit** with an `Assisted-by:` trailer when an
      AI assistant contributed.

## Claims

- [ ] **No performance claim without a benchmark** in the same change, on a
      stated machine/toolchain, reproducible by a third party.
- [ ] **No capability/uniqueness claim** that isn't backed by a test, a CI
      gate, or a cited artifact. Unproven statements are labelled
      `candidate` / `planned`, or omitted.

## Cross-path & boundaries

- [ ] **Parity where two paths share semantics.** If a behaviour is
      implemented by more than one code path (streaming vs materialised,
      borrowed vs owned, SIMD vs scalar, a port vs its source), a test
      exercises **both against the same input** and asserts they agree.
- [ ] **Contracts at seams.** Anything crossing a language/process boundary
      uses a structured contract (JSON / protobuf / a fixed CLI contract),
      with integer-width, encoding, and error-propagation tested — never
      ad-hoc string parsing.

Skills MAY add stricter, domain-specific gates on top of this list; they MUST
NOT weaken it.
