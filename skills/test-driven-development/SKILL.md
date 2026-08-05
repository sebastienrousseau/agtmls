---
name: test-driven-development
description: "Write the failing test first, then the code that makes it pass. Load when adding behaviour, changing behaviour, or pinning a bug, and whenever a test was authored after the code it covers. Enforces red-green-refactor with an observed red phase, so a test that never failed is never mistaken for proof."
license: MIT
compatibility: "Requires a test runner. Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Write Edit Bash"
metadata:
  agtmls-version: "0.0.5"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "true"
  agtmls-executes-commands: "true"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Test-driven development

**Trigger.** You are about to add or change behaviour — a feature, an edge
case, a bug fix, a refactor with a semantic change. Also load it when you
notice you have written code and are about to write its test.

> **Reference material** (what a legitimate red looks like per runner, test
> granularity and doubles, applying the loop to legacy code without tests):
> see `reference.md` in this directory.

## The rule

> **A test you have not seen fail proves nothing.**

This is the whole discipline in one line. A test written after the code
passes on its first run, which means you have observed exactly one fact: the
test executes. You have not observed that it tests *your* behaviour, that it
would catch a regression, or that its assertions are reachable.

Tests that were never red are the most common form of coverage theatre: the
number goes up, the safety does not.

## The loop

### RED — write a failing test

1. Name the behaviour in one sentence: *given X, the system does Y*.
2. Write the smallest test that asserts it.
3. **Run it. Watch it fail.**
4. **Read the failure message.** This is the step that carries the value.

A legitimate red fails *for the reason you intended*:

| Failure | Verdict |
| --- | --- |
| `AssertionError: expected 3, got 0` | Legitimate — the behaviour is absent |
| `AttributeError: no attribute 'parse'` | Legitimate for new API surface |
| `ImportError` / `fixture not found` | **Not a red** — the harness is broken |
| `SyntaxError` | **Not a red** — fix the test |
| Passes immediately | **Not a red** — see below |

If it passes immediately, one of three things is true, and you must find out
which: the behaviour already exists (then why are you writing it?), the test
asserts nothing meaningful (`assert result` on a truthy object), or it is
testing the wrong code path. Break the implementation deliberately and
confirm the test notices.

### GREEN — make it pass, minimally

Write the least code that turns the test green. Not the general solution, not
the version with the config knob you anticipate wanting. Resisting this is
the point: the next test drives the generalization, and if no next test
demands it, you did not need it.

Run the test. Watch it pass. Then run the **full suite** — green on the new
test while two others broke is not green.

### REFACTOR — clean up under a green bar

Now improve the code: naming, duplication, structure. The tests are your
safety net, so change one thing at a time and re-run. If the suite goes red
during a refactor, you have changed behaviour, not structure — revert and
separate the two.

Refactor the *tests* here too. Duplicated setup and unclear names rot faster
in test code than anywhere else.

## Applying it to bug fixes

This is where the discipline pays best, and it is the same loop:

1. Reproduce the bug (see `systematic-debugging` if the cause is unknown).
2. Write a test asserting the **correct** behaviour for the reported input.
3. Run it against the **unfixed** tree. It must fail with the real symptom.
4. Fix. Watch it pass. Run the full suite.

Step 3 is not optional and takes one command:

```sh
git stash && <run the test>; git stash pop && <run the test>
```

A regression test that was never observed failing may be testing the wrong
thing entirely — and it will sit in the suite for years looking like
protection.

## What to test

Test **behaviour through the public surface**, not implementation shape.

| Test this | Not this |
| --- | --- |
| Return values and raised errors | Which private method was called |
| Observable state after the call | Internal field layout |
| Contracts at module boundaries | The order of internal steps |
| Edge cases: empty, one, many, max | Every branch for its own sake |
| Error paths users can trigger | Unreachable defensive branches |

A test coupled to implementation fails on every refactor and passes when
behaviour breaks — exactly backwards.

## Anti-patterns

- **Assertion-free tests.** Calling the function and checking nothing. It
  passes until the function raises, and covers lines while proving nothing.
- **Testing the mock.** Asserting that your stub returned what you told it
  to. The system under test never ran.
- **One test, twelve assertions.** The first failure hides the rest. Split by
  behaviour.
- **Writing tests to raise coverage.** Coverage is a symptom of testing, not
  its goal. Chasing the number produces tests nobody trusts.
- **Skipping red because "it obviously fails."** It obviously fails until it
  obviously does not, and you find out in six months.
- **Changing the test to match the code.** When a test fails after a change,
  decide deliberately: did behaviour intentionally change (update the test,
  and say so) or did you break it (fix the code)?

## When not to use

- The project defines its own test taxonomy, evidence bar, or coverage gates
  — follow that; this is the authoring loop underneath it.
- Pure exploration or a throwaway spike, where the code will be deleted. Say
  it is a spike, and re-do it test-first if it survives.
- Formatting, comments, or renames with no semantic change.
