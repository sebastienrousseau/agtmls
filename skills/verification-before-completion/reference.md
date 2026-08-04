<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Verification before completion — reference

Depth for `SKILL.md`. Load when the four-question loop is not enough: you
need the exhaustive claim→evidence mapping, the rationalization catalogue
with counter-moves, or a worked transcript to compare against.

## Claim → evidence, in full

Each row is a claim you might make and the observation that justifies it.
"Insufficient" lists what people offer instead.

| Claim | Sufficient evidence | Insufficient |
| --- | --- | --- |
| "It compiles" | Build command exit 0 | Editor shows no squiggles |
| "Types check" | Type-checker exit 0 on the whole project | One file checked |
| "Tests pass" | Runner summary from this tree, after the last edit | A run from before the edit |
| "The bug is fixed" | Regression test failing pre-fix, passing post-fix | The new test passes |
| "Nothing else broke" | Full suite green | Touched-file tests green |
| "Behaviour changed" | Before/after outputs for the same input | The diff looks correct |
| "It's faster" | N runs each side, median + spread, same machine and load | One timed run |
| "Memory use dropped" | Profiler or RSS measurement with a baseline | Fewer allocations in the source |
| "The endpoint works" | A real request with status + body | The route is registered |
| "Deploy succeeded" | Service healthy and serving traffic | The deploy tool exited 0 |
| "Config is valid" | The system loaded it and started | The file parses |
| "The migration works" | Applied to a copy of real-shaped data, then verified | The SQL is syntactically valid |
| "Docs are accurate" | Every command in them executed | They read well |
| "The script is idempotent" | Ran twice, compared end states | It looks idempotent |
| "The race is fixed" | Stress/repeat run, or a reasoned proof of exclusion | It stopped reproducing once |
| "Dependency upgrade is safe" | Full suite plus changelog review for breaking changes | It installed |

### The pre-fix failure requirement

The single highest-value row is *bug fixed*. A regression test that was never
observed failing on the unfixed tree does not prove the fix — it may test the
wrong thing, be trivially true, or not run at all.

The check is cheap and takes one command:

```sh
git stash            # remove the fix, keep the test
<run the new test>   # MUST fail, and fail for the stated reason
git stash pop
<run the new test>   # MUST pass
```

Read the failure message. A test that fails with `ImportError` or
`fixture 'db' not found` has not demonstrated anything about the bug.

## Rationalization catalogue

Each entry: what it sounds like, why it is seductive, and the counter-move.

### "This edge case won't happen"

*Sounds like:* "Nobody passes an empty list here."
*Seductive because:* it is often true, and testing it costs time.
*Counter-move:* if it cannot happen, the cost of writing that down is one
comment and it becomes a durable invariant. If you cannot write down why,
you do not know it cannot happen — test it.

### "I'll add the test in a follow-up"

*Sounds like:* "Let me ship the fix and backfill coverage."
*Seductive because:* it feels like sequencing, not skipping.
*Counter-move:* the follow-up is written by someone without today's context,
if at all. Same turn, or it did not happen.

### "The linter is wrong here"

*Sounds like:* "This rule doesn't understand the pattern."
*Seductive because:* sometimes true.
*Counter-move:* a specific inline suppression with a reason comment is a
justified engineering decision. A blanket disable, a config-level exclusion,
or `--no-verify` is you overruling the gate without argument.

### "Close enough"

*Sounds like:* "The refactor is equivalent."
*Seductive because:* equivalence usually holds.
*Counter-move:* claimed equivalence is a testable proposition. Run both, diff
the outputs on real inputs. If you will not, say "believed equivalent, not
differentially tested".

### "It worked before"

*Sounds like:* "I ran this earlier and it was fine."
*Seductive because:* you did observe something.
*Counter-move:* evidence is scoped to a tree state. Every edit invalidates it.

### "The user is waiting"

*Sounds like:* urgency justifying a shortcut.
*Seductive because:* responsiveness is a real value.
*Counter-move:* the user is waiting for a *correct* answer. Delivering a
wrong one fast means they debug it, then wait again. If time genuinely
forces a cut, say which verification you skipped.

### "I can't run it in this environment"

*Sounds like:* a blocker.
*Seductive because:* it is frequently legitimate.
*Counter-move:* legitimate — and it changes the report, not the claim. Label
the work unverified, say precisely what you could not run, and hand over the
command that would confirm it. This is the honest path, not a failure.

## Worked transcripts

### Fails the gate

> I've fixed the timeout issue. The client now retries with exponential
> backoff, so transient failures should be handled correctly.

Three defects. "Should be handled" is a prediction. No test is mentioned. No
observation of the old failure or the new behaviour. The reader cannot tell
whether anything was executed.

### Passes the gate

> Fixed. `tests/test_client.py::test_retries_on_timeout` fails on the pre-fix
> tree with `ConnectionTimeout` after one attempt, and passes now with three
> attempts at 1s/2s/4s (asserted on the mock clock). Full suite: 88 passed.
>
> Not checked: behaviour against the real upstream — the integration suite
> needs credentials I don't have here. `make test-integration` covers it.

Same work. The difference is that a reader knows exactly what is established,
what is assumed, and what to run next.

### Passes the gate while unable to verify

> **Unverified — I could not execute this.** The change adds `timeout` to the
> `Session` constructor at `client/session.py:42`, following the pattern used
> for `retries` two lines up. I have no Python toolchain in this environment,
> so I have neither run the tests nor imported the module. Confirm with
> `pytest tests/test_client.py`.

Nothing was verified, and the report is still trustworthy — because it says
so first, and hands over the exact next step.

## Interaction with other skills

- `systematic-debugging` runs **before** this: it produces the fix and the
  failing-first regression test that this gate then demands evidence of.
- `test-driven-development` makes the gate cheap: if the test was written
  red-first, the pre-fix failure has already been observed.
- A project skill that defines a repo's own evidence bar (required gates,
  coverage floors, doctest rules) **overrides** the general habit here. This
  skill is the floor, not the ceiling.
