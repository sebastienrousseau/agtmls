---
name: systematic-debugging
description: "Find the root cause of a defect before changing anything. Load when something crashes, hangs, returns the wrong value, fails intermittently, or broke after a change, and the cause is not yet known. Drives reproduce, localize by bisection, explain the mechanism, then fix with a failing-first regression test. Replaces guess-and-check editing."
license: MIT
compatibility: "Requires a reproduction command. Tested with Claude Code, Codex, and Aider skill layouts"
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

# Systematic debugging

**Trigger.** Something is broken and you do not yet know why: a crash, a
wrong result, a hang, a flake, a test that fails only in CI, a regression
after an upgrade. Also load it when you catch yourself about to change code
in the hope that it helps.

> **Reference material** (localization techniques per symptom class,
> intermittent-failure playbook, and the instrumentation recipes): see
> `reference.md` in this directory.

## The rule

> **No edit before an explanation.** You must be able to say *this input
> reaches this line, which does this wrong thing, which produces this
> symptom* — before you touch the code.

Guess-and-check feels faster and is not. Each speculative edit changes the
system you are trying to understand, and a "fix" that removes a symptom
without an explanation has usually moved the bug somewhere less visible.

## Four phases

Do not skip forward. Each phase has an exit condition; if you cannot meet it,
you are still in that phase.

### Phase 1 — Reproduce

**Exit condition: one command that fails, reliably, on demand.**

1. Get the exact failure: full error, stack trace, exit code, wrong output.
   Not a paraphrase — the literal text.
2. Establish the environment: branch, commit, dependency versions, config,
   platform. Bugs that "only happen for them" are usually environment deltas.
3. Reduce the trigger to the smallest input and shortest command you can.
4. Run it three times. If it fails 3/3, continue. If it fails 1/3, you have
   an intermittent bug — see `reference.md` §intermittent before proceeding.

If you cannot reproduce it, **say so and stop**. Debugging a failure you
cannot observe is writing fiction. Ask for the input, the logs, the version.

### Phase 2 — Localize

**Exit condition: the smallest region of code where correct input goes in
and incorrect output comes out.**

Bisection is the workhorse — over *anything* ordered:

| Axis | Method |
| --- | --- |
| Time | `git bisect` between a known-good and known-bad commit |
| Call stack | Assert or log the invariant at the top, middle, and bottom |
| Input | Halve the input until the failure disappears |
| Config | Disable half the flags/plugins; repeat on the failing half |
| Data | Halve the dataset; find the minimal failing record |

The discipline is the same every time: **form a binary question, answer it by
observation, halve the space.** Ten halvings cover a thousand candidates.

Two rules that keep this honest:

- **Verify the boundary.** When you think you have found the transition
  point, confirm both sides: correct just before, incorrect just after.
- **Instrument, don't infer.** Print the actual value. A variable you
  *believe* holds `3` is the reason the bug survived this long.

### Phase 3 — Explain

**Exit condition: a written sentence that connects cause to symptom, which
predicts something you have not yet tested.**

Write it out:

> *When `parse()` receives a key containing `:`, the split on line 88 takes
> the first segment only, so the map is built with a truncated key, so the
> lookup on line 140 misses and returns the default.*

Then **test the prediction**. A correct explanation predicts more than the
one failure you have: it says which *other* inputs fail, and which
superficially similar ones do not. Check one of each. If the prediction is
wrong, your explanation is wrong — return to Phase 2.

This is the step people skip, and skipping it is how you get a fix that
works on the reported input and nothing else.

### Phase 4 — Fix and pin

**Exit condition: a regression test observed failing before the fix and
passing after.**

1. **Write the test first**, from the explanation, and watch it fail with the
   real symptom — not `ImportError`, not a missing fixture.
2. Make the smallest change the explanation calls for. If the explanation
   does not call for it, it is not part of the fix.
3. Watch the test pass.
4. Run the full suite. A fix that breaks two other things is not a fix.
5. Check the explanation for **siblings**: if `split(':')` was wrong here, is
   the same pattern wrong in the three other places it appears?

## Anti-patterns

- **Shotgun editing.** Changing several things at once, then testing. If it
  works you have learned nothing; if it does not, you have a bigger space.
- **Fixing the symptom.** Wrapping the crash in try/except, clamping the bad
  value, adding a retry. Legitimate only when the explanation says the
  condition is genuinely expected — and then it is not a bug fix.
- **Blaming the platform.** The compiler, the runtime, the standard library.
  Occasionally right; assume it last, and only with a minimal reproduction.
- **Trusting the comment.** Comments describe intent at writing time. Read
  the code.
- **Stopping at "it stopped happening."** Especially for intermittent bugs.
  Absence of a symptom over ten runs is weak evidence about a race.
- **Rewriting to make the bug go away.** Now you have an unexplained bug and
  a large diff.

## When not to use

- The project has a symptom-indexed triage playbook for its own subsystems —
  use that first; it will localize faster than a generic bisection.
- You already know the cause and are just making the change.
- The task is adding new behaviour, not restoring intended behaviour — that
  is `test-driven-development`.
