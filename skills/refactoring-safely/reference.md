<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Refactoring safely — reference

Depth for `SKILL.md`. Load when you need the characterisation-net recipe,
the safe sequence for a specific refactoring, or strategy for a restructure
too large to land in one branch.

## Building a characterisation net

The goal is not coverage. It is a net that **fails when behaviour changes**.

1. **Find the seams.** What can you call from a test today without standing up
   the world? Pure functions first, then anything you can reach with cheap
   fakes.
2. **Record current behaviour.** Not what it should do — what it does. Feed it
   real inputs and assert the actual outputs, including the ones that look
   wrong. Add a comment where you believe behaviour is a bug, and leave it
   asserted.
3. **Golden-file it when output is large.** Serialise the result, commit it as
   a fixture, and diff against it. Cheaper than hand-writing assertions for a
   large structure, and far more sensitive.
4. **Sabotage it.** The step that makes the rest meaningful:

   ```sh
   # invert a condition, return a constant, delete a branch
   # then run the suite — it MUST go red
   ```

   If the suite stays green, your net has holes exactly where you are about to
   work. Add tests until sabotage is caught.
5. **Commit the net separately**, before any restructuring. It is independently
   valuable and it proves the baseline.

For code with no seam at all, make the smallest structural change that creates
one — extract a function, inject a dependency, pass a clock instead of calling
`now()` — and treat that micro-change as its own reviewed step.

## Safe sequences for common refactorings

### Rename a widely-used symbol

1. Introduce the new name as an alias of the old.
2. Migrate call sites in batches, green after each.
3. Delete the alias.

Deprecation-warn on the old name between 2 and 3 if it is public API.

### Extract a function

1. Copy the block into a new function; leave the original in place.
2. Call the new function from the original site; delete the inlined copy.
3. Run tests. Any behaviour change here means the block was not as
   self-contained as it looked — usually a closed-over variable or an early
   `return` that no longer returns from the outer function.

Watch for: `return`, `break`, `continue`, `yield`, and mutation of outer
scope. These are what make an "obvious" extraction change behaviour.

### Change a function signature

1. Add the new parameter with a default that preserves current behaviour.
2. Migrate callers to pass it explicitly.
3. Remove the default, or the old parameter.

### Move a module

1. Move the file; leave a re-export at the old path.
2. Migrate importers.
3. Delete the re-export.

### Replace a conditional with polymorphism

1. Add the type hierarchy alongside; do not wire it in.
2. Move one branch's body into a method; call it from that branch.
3. Repeat per branch until the conditional only dispatches.
4. Replace the dispatch with a lookup or virtual call.

Green at every step, and revertible at every step.

### Deduplicate

Resist merging code that merely *looks* the same. Two blocks with identical
text and different reasons to change should stay separate — merging them
couples two callers whose requirements will diverge, and the eventual
un-merging is worse than the duplication.

Merge when the two copies must change together, by definition.

## Large-scale restructures

For work too big for one branch:

**Strangler pattern.** Build the new structure beside the old, route a slice
of callers to it, widen the slice, delete the old. Every intermediate state
ships.

**Branch by abstraction.** Introduce an interface both implementations
satisfy, switch behind a flag, migrate, remove the flag and the old
implementation.

**Never**: a long-lived refactor branch. It accumulates conflicts faster than
it accumulates value, and the merge is a single unreviewable event.

Two supporting practices:

- **Automate the mechanical part.** `comby`, `ast-grep`, codemods, or your
  IDE's structural search across hundreds of sites. A scripted transformation
  is auditable and re-runnable; four hundred hand edits are neither.
- **Land mechanical and semantic separately, always.** Even in a large
  programme, one commit renames, another changes behaviour.

## How to describe a refactor in review

Tell the reviewer what they may skip:

> Mechanical only. `extract_headers()` pulled out of `parse()` verbatim — no
> logic changed, confirmed by `pytest tests/test_parse.py` (41 passed, same as
> before). The only non-mechanical line is 88, where the early `return` became
> a `raise` because the extracted function cannot return from the caller.

That last sentence is the entire value of the description: it points at the
one place behaviour could have changed.

## Interaction with other skills

- `test-driven-development` covers the case where behaviour *should* change;
  the net here is the same discipline turned backwards.
- `verification-before-completion` demands evidence that behaviour held —
  same test counts before and after is the cheapest form.
- `giving-code-review` benefits most from the mechanical/semantic split; say
  which kind each commit is.
- `writing-plans` should schedule mechanical and semantic steps separately.
