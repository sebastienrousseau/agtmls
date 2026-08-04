---
name: writing-plans
description: "Turn a vague or multi-step request into an ordered list of small steps, each with its own done-condition and verification. Load before starting work that touches several files, has unclear scope, or spans more than one session, and when a request needs decomposing before any code is written. Produces a plan a reviewer can check against, not a to-do list."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit"
metadata:
  agtmls-version: "0.0.4"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "false"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Writing plans

**Trigger.** The work ahead is larger than one obvious edit: several files, an
unclear boundary, a migration, a feature with sub-parts, or anything you
would otherwise start by "having a look around and seeing".

> **Reference material** (the plan template, sizing heuristics, worked
> examples of a bad plan rewritten, and how to revise mid-execution): see
> `reference.md` in this directory.

## The rule

> **A step is done when something observable changes. If you cannot say what
> would be observed, it is not a step — it is a wish.**

The purpose of a plan is not to look organized. It is to (a) surface the
decisions and unknowns *before* they are expensive, and (b) produce
checkpoints where someone can tell whether progress is real.

## Before planning: resolve the scope

Do not plan against a guess. Spend the first pass on the request itself:

1. **Restate the goal** in one sentence, in terms of the observable outcome.
2. **List the unknowns.** Anything where two readings lead to materially
   different work.
3. **Decide or ask.** For a routine judgment call, decide and record the
   assumption in the plan. For a fork that would waste the work if wrong,
   ask now — not after step 4.
4. **Establish the baseline.** What currently works? Run the tests *before*
   changing anything, so a later failure is attributable.

A plan built on an unresolved ambiguity is a plan to do the work twice.

## Writing the steps

Each step gets three things:

| Field | Requirement |
| --- | --- |
| **Action** | One concrete change, in one place, in one sitting |
| **Done-condition** | The observation that proves it landed |
| **Verification** | The command or check that produces that observation |

A step without a done-condition is the failure mode this skill exists to
prevent. Compare:

| Weak step | Strong step |
| --- | --- |
| "Refactor the parser" | "Extract `tokenize()` from `parse()`; `pytest tests/test_parser.py` still passes (14 tests)" |
| "Add error handling" | "`load()` raises `ConfigError` on missing file; new test `test_load_missing_raises` goes red→green" |
| "Update the docs" | "README install section runs clean on a fresh clone; every command executed" |
| "Make it faster" | "Replace the O(n²) scan at `index.py:88`; benchmark median drops below 200ms over 20 runs" |

### Sizing

Aim for steps that are individually **revertible** and individually
**verifiable**. A useful test: if the step fails review, can it be undone
without unpicking the next three? If not, it is too big.

Too small is also a cost — a fifteen-step plan where every step is "add one
import" is noise. The right grain is *one coherent change with one check*.

### Ordering

- **Riskiest unknown first.** If a step might invalidate the plan, do it
  early, while the plan is cheap to change. Do not save the hard part.
- **Keep the tree green between steps.** Order so each step lands with the
  suite passing. A plan whose middle six steps are all broken cannot be
  checkpointed or handed over.
- **Separate mechanical from semantic.** A rename touching 200 files and a
  behaviour change should never be the same step; the review cost differs by
  an order of magnitude.

## Recording what you will not do

State the out-of-scope explicitly. Two lines here prevent the most common
plan failure — quiet scope drift — and they let a reviewer correct you before
the work, not after:

> **Not in scope:** migrating the legacy `v1/` handlers, changing the wire
> format, touching the deploy config.

Also record **assumptions** you decided rather than asked about, so a wrong
one is visible and cheap to fix.

## Executing the plan

- Work the steps in order. If you discover the plan is wrong, **stop and
  revise it** — do not silently improvise past it. A plan you abandoned
  without saying so is worse than no plan, because the reader still believes
  it.
- Mark each step done only when its done-condition is observed. See
  `verification-before-completion`.
- When a step reveals new work, add it to the plan explicitly rather than
  folding it into the current step.

## When not to use

- A single obvious edit. Writing a plan for a one-line fix is ceremony.
- The project has its own planning or change-control process — follow that.
- You are still diagnosing a defect and do not yet know what needs changing;
  that is `systematic-debugging`. Plan the fix once you have the explanation.
