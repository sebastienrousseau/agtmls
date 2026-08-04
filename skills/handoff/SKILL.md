---
name: handoff
description: "Write the note that lets someone else — or a later session — resume work in progress without re-deriving it. Load when context is running out, when pausing unfinished work, when switching who or what continues it, and when asked where things stand. Records tree state, evidence, the next concrete action, and the dead ends. Not a summary of what you did."
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

# Handoff

**Trigger.** Work is unfinished and continuity is about to break: context is
running out, the session is ending, someone else is taking over, you are
parking a branch, or a human asked *where are we with this?*

> **Reference material** (the template, worked good/bad handoffs, and what to
> capture for long-running or multi-agent work): see `reference.md` in this
> directory.

## The rule

> **A handoff is judged by one thing: can the reader take the next action
> without asking you a question?**

Not by how much it covers. A handoff that narrates three hours of work and
leaves the reader unsure which command to run has failed; four lines that
name the next command have succeeded.

The default failure is writing a **diary** instead of a **state report**.
"First I looked at the parser, then I tried adding a guard, then I realised…"
is your experience. The reader needs where things *are*, not how they got
there — except where the journey contains traps (see below).

## What a handoff must contain

Six parts. Omit any and the reader has to reconstruct it.

### 1. Goal

One sentence, in terms of the observable outcome. Not the ticket title — what
"done" looks like.

### 2. State of the tree

The part people forget, and the one that costs the most when missing:

- Branch name, and what it is based on.
- Uncommitted changes — and whether they are coherent or mid-edit.
- Anything half-applied: a partial migration, a rename stopped halfway, a
  dependency bumped but not rebuilt.
- Anything stashed, and what is in it.

If the tree is in a state that will not build, **say so first**. A reader who
discovers that by running the tests has already lost the thread.

### 3. What is done — with evidence

Not "the parser is done" but "the parser change is done: `pytest
tests/test_parser.py` reports 14 passed; it reported 2 failed before." A
claim without evidence has to be re-verified by the reader, which means it
was not really handed over. See `verification-before-completion`.

### 4. The next action

**A command or an edit, not a direction.** The single highest-value line in
the document.

| Weak | Strong |
| --- | --- |
| "Continue with the API layer" | "Add the `/health` route in `app/routes.py`, mirroring `/status` at line 40" |
| "Fix the failing test" | "`pytest tests/test_auth.py::test_expiry` fails on line 88 — the mock clock is not advancing" |
| "Finish the migration" | "Run `alembic upgrade head` against the dev DB; steps 1–3 of 5 are applied" |

### 5. Dead ends and traps

**The most valuable section, and the one always cut for length.** Anything
that cost you more than a few minutes and would cost the reader the same:

> Do not try `--parallel` on the test runner: it passes locally and hangs in
> CI. Spent 40 minutes on it; the fixtures share a temp dir.

Without this, your successor repeats your mistakes at full price. It is the
only part of the document that cannot be reconstructed from the code.

### 6. Open questions

Decisions that are not yours to make, with who owns them and what is blocked
until they are answered. Distinguish **blocking** from **nice to know**.

## Anti-patterns

- **The diary.** Chronological narration of your process.
- **"Should be straightforward."** Either it is, and you should have finished
  it, or it is not, and you have mislabelled the hard part.
- **Unstated assumptions.** You chose an approach for a reason; if it is not
  written down, the reader will re-litigate or silently reverse it.
- **Omitting the failures.** A handoff listing only what worked implies the
  obvious approaches are untried.
- **Stale evidence.** "Tests pass" from before the last three edits. Re-run,
  or say when it was last observed.
- **Linking without stating.** "See the thread" makes the reader do the
  synthesis you were supposed to do.

## When not to use

- The work is finished — that is a completion report, not a handoff.
- Nothing is in flight and there is no tree state to describe.
- The project has its own status or session-continuity format; use that.
