---
name: verification-before-completion
description: "The gate between doing work and claiming it is done. Load before saying finished, fixed, working, or ready, before marking a task complete, and before reporting an outcome to a human. Converts each claim into the observation that would justify it, and names the rationalizations that let unverified work ship. Not the project's own evidence bar or test taxonomy."
license: MIT
compatibility: "Tested with Claude Code, Codex, and Aider skill layouts"
allowed-tools: "Read Glob Grep Bash"
metadata:
  agtmls-version: "0.0.5"
  agtmls-owner: "Sebastien Rousseau"
  agtmls-maturity: "hardened"
  agtmls-risk-level: "low"
  agtmls-network-access: "none"
  agtmls-writes-files: "false"
  agtmls-executes-commands: "true"
  agtmls-handles-secrets: "false"
  agtmls-requires-human-review: "true"
---

# Verification before completion

**Trigger.** You are about to write *done*, *fixed*, *working*, *should
work*, *ready*, *that's it*, *all set*, or to mark a task complete — or a
human asked whether something is finished.

> **Reference material** (the full claim→evidence table, the rationalization
> catalogue with counter-moves, and worked pass/fail transcripts): see
> `reference.md` in this directory. This file is the gate and the loop.

## The rule

> **A claim you have not observed is a guess. Report it as one, or go and
> observe it.**

This is not about being slow or hedging. It is about the difference between
*I ran it and saw X* and *it should do X*. The first is a report. The second
is a prediction wearing a report's clothes, and it is the single most common
way agent work goes wrong: not a bad edit, but a **correct-looking edit
reported as verified when nobody looked**.

## The loop

Run this before every completion claim. It is four questions, in order.

### 1. What exactly am I claiming?

Write the claim as one sentence, in the form a reader will act on. Vague
claims cannot be verified, so sharpen first:

| Vague | Sharp |
| --- | --- |
| "the tests pass" | "`pytest tests/` exited 0 with 214 passed, 0 failed" |
| "I fixed the bug" | "the reported input now returns 3 instead of raising" |
| "it builds" | "`cargo build --all-features` exited 0 with no warnings" |
| "the API works" | "`GET /health` returned 200 with `{\"ok\":true}`" |

### 2. What observation would justify it?

For each claim, name the artifact that proves it — a command's exit code and
output, a file's content, a screenshot, a log line. If you cannot name one,
the claim is not verifiable as stated: go back to step 1.

The mapping is mechanical. The full table is in `reference.md`; the
load-bearing rows:

| Claim | Required observation |
| --- | --- |
| Behaviour changed | The new behaviour executed, **and** evidence it differed before |
| Bug fixed | A test that **fails on the pre-fix tree** and passes now |
| Tests pass | The runner's own summary line, from this working tree |
| Nothing else broke | The full suite, not the file you touched |
| Performance improved | A measurement with a stated baseline and variance |
| Config/deploy works | The system started and served, not that YAML parsed |

### 3. Did I actually observe it — in this state of the tree?

The trap is *stale* evidence: a green run from three edits ago, a test seen
passing before the last refactor, output from a different branch. Evidence
expires the moment the tree changes.

Ask literally: *did I run this, after my last edit?* If the answer is "I ran
something like it earlier", the answer is no.

### 4. What did I not check?

Name it explicitly in the report. An honest gap is information; a silent gap
is a defect you handed to someone else. See **Reporting** below.

## Red flags — none of these is verification

Each of these has been mistaken for evidence. None of them is:

- **"It compiles" / "it typechecks."** Necessary, never sufficient. The
  compiler proves shape, not behaviour.
- **"It looks right."** Reading a diff is not running it. You are checking
  your own intent against itself.
- **"The test passes."** Did you see it fail first? A test that never failed
  proves the harness runs, not that the behaviour is pinned.
- **"Green on my machine."** Not the full gate. Partial runs hide
  cross-module breakage.
- **"The linter is wrong here."** Maybe. Justify a specific, inline
  suppression, never a blanket one.
- **A delta inside noise.** A 3% benchmark change with 8% run-to-run variance
  is not an improvement. State the variance or make no claim.
- **The tool reported success.** Tools report *their* success. `git push`
  succeeding says nothing about CI.

## Rationalizations to reject

These are the sentences that talk you past the gate. Each has a counter-move;
the full catalogue with worked examples is in `reference.md`.

| Rationalization | Counter-move |
| --- | --- |
| "This edge case won't happen" | Test it, or write down why it cannot occur |
| "I'll verify in a follow-up" | Same turn, or it did not happen |
| "It's a trivial change" | Trivial changes are cheap to verify — so verify |
| "The user is waiting" | A wrong answer costs them more than 30 seconds |
| "It worked last time" | Different tree, different answer |
| "Close enough" | Prove the equivalence or state the difference |
| "I can't run it here" | Then say so, and label the claim unverified |

That last row is the important one. **Being unable to verify is an
acceptable outcome. Claiming verification you do not have is not.**

## Reporting

State what you did, what you observed, and what you skipped. Three shapes:

**Verified.** Say it plainly, with the observation. No hedging — hedging a
verified result is its own failure mode.

> Fixed. `pytest tests/test_parser.py` now passes (14 passed); it failed with
> `KeyError: 'root'` before the change. Full suite: 214 passed, 0 failed.

**Partly verified.** Lead with what holds, then the gap.

> The parser change works — the failing input now returns 3, confirmed by the
> new test. I have not run the integration suite; it needs a live database I
> can't reach from here.

**Unverified.** Say so first, before the description.

> **Unverified:** I could not run this. The change follows the pattern in
> `handlers/auth.py:88` and should make the timeout configurable, but I have
> not executed it. Run `make test-integration` to confirm.

## When not to use

- The project defines its own evidence bar, gates, or test taxonomy — follow
  that first; this skill is the general habit underneath it.
- Pure discussion, brainstorming, or exploration with no completion claim.
- You are debugging and do not yet have a fix to verify — that is
  `systematic-debugging`.
