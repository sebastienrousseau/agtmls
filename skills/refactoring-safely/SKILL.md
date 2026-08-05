---
name: refactoring-safely
description: "Change the shape of code without changing what it does. Load when you extract, rename, move, deduplicate, or restructure a module safely across its call sites, and whenever a diff mixes restructuring with new behaviour. Requires a characterisation net before the first edit and keeps structural and behavioural changes in separate commits."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit Bash"
metadata:
  agtmls-version: "0.0.4"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "true"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Refactoring safely

**Trigger.** You are about to restructure working code: extract a function,
rename across call sites, move a module, collapse duplication, replace a
conditional with polymorphism, split a class. Also load it when you notice a
diff doing restructuring *and* a fix at the same time.

> **Reference material** (the net-building recipe, sequences for the common
> refactorings, large-scale and cross-repo strategy): see `reference.md`.

## The rule

> **A refactor that changes behaviour is not a refactor. It is an
> undocumented change wearing a refactor's diff.**

The value of the word is that it tells a reviewer *they do not need to reason
about behaviour*. The moment that stops being true, you have spent their
trust and hidden a real change inside a large mechanical diff — the single
easiest place for a defect to survive review.

## Before the first edit

### 1. Say why

"It's messy" is not a reason; it is taste, and taste alone does not justify
churn or merge conflicts. A reason is concrete:

- a change you need to make is hard in the current shape;
- the same logic has diverged in three places and drifted;
- the structure allows an illegal state that keeps causing bugs;
- new people consistently misread it the same way.

No concrete reason means leave it alone.

### 2. Build the net

**You cannot refactor code you cannot test.** If coverage is thin, write
characterisation tests first — tests that assert what the code does *today*,
including behaviour you think is wrong.

They pass immediately, which is expected: they are a net, not a
specification. So verify the net actually catches things:

```sh
# Break the implementation on purpose — invert a condition, return a
# constant — and confirm the suite goes red. A net that survives sabotage
# is not protecting anything.
```

This step is the one people skip, and skipping it is how "pure refactors"
ship defects.

### 3. Check nobody is building on it

A large restructure of a file someone else has open is a merge conflict you
chose. Check for in-flight work; land or coordinate first.

## The loop

1. **One transformation at a time.** Extract *or* rename *or* move — not all
   three. Compound refactors cannot be bisected when they go wrong.
2. **Run the tests after each.** Not at the end. The whole point is a short
   distance between "green" and "red" so the cause is obvious.
3. **Prefer the tool.** Your IDE's rename and extract are mechanical and will
   not typo one of forty call sites. Hand-editing across many files is where
   errors enter.
4. **Commit each step.** Small, green, revertible commits. A twelve-file
   mechanical commit is reviewable; a twelve-file mixed one is not.
5. **Never mix in behaviour.** Spot a bug mid-refactor? Note it, finish the
   refactor, then fix it in its own commit with its own failing test.

That last rule is the one that pays. A reviewer can skim a mechanical diff in
a minute and read a three-line behavioural one carefully — but not a
four-hundred-line diff where the behavioural change is on line 213.

## Keeping the tree green

Sequence so every intermediate state builds and passes:

- **Renaming a public symbol?** Add the new name as an alias, migrate call
  sites, then remove the old one — three commits, all green.
- **Changing a signature?** Add the parameter with a default, migrate, then
  make it required.
- **Moving a module?** Move it, leave a re-export, migrate importers, delete
  the re-export.

The expand–migrate–contract shape works for almost every restructure and
means you can stop at any point without leaving the tree broken.

## Anti-patterns

- **The rewrite in disguise.** "Refactor" that deletes and reimplements. That
  is a rewrite; call it one and test it like one.
- **Refactoring to no purpose.** Restructuring because you are in the file.
- **The big-bang branch.** Two weeks of restructuring merged at once. It will
  conflict, and nobody can review it.
- **Changing tests to match.** If the tests fail, behaviour changed. Fix the
  code, or admit it is a behavioural change.
- **Refactoring under deadline pressure**, alongside the fix you actually
  need. Ship the fix; restructure after.

## When not to use

- You are adding or changing behaviour — that is `test-driven-development`.
- The code is going to be deleted shortly.
- You do not have and cannot build a test net, and the code is
  business-critical. Say so; propose adding characterisation tests as work in
  its own right.
