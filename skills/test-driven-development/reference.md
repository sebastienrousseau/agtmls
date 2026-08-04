<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Test-driven development — reference

Depth for `SKILL.md`. Load when you need to confirm a red is legitimate in a
specific runner, choose test granularity or a double, or apply the loop to
code that has no tests yet.

## Observing red, per runner

The goal is always the same: run **only the new test**, and read the message.

| Runner | Single-test invocation |
| --- | --- |
| pytest | `pytest tests/test_x.py::test_name -x` |
| unittest | `python -m unittest tests.test_x.TestX.test_name` |
| cargo | `cargo test test_name -- --exact --nocapture` |
| go | `go test -run '^TestName$' ./pkg/...` |
| jest / vitest | `npx jest -t "test name"` / `npx vitest -t "test name"` |
| JUnit (maven) | `mvn test -Dtest=ClassName#methodName` |
| RSpec | `bundle exec rspec path/to/spec.rb:42` |
| ctest | `ctest -R '^test_name$' --output-on-failure` |

Two runner-specific traps:

- **Silent skips.** A test that is skipped is not a red. pytest reports `s`,
  Go prints `--- SKIP`, RSpec shows `*`. Check the summary counts, not just
  the absence of `FAILED`.
- **Zero collected.** `1 passed` and `no tests ran` look similar in a fast
  scroll. If the count is 0, your selector did not match — the test you think
  you are watching never executed.

## Granularity

Choose the smallest scope that can observe the behaviour.

| Scope | Use when | Cost |
| --- | --- | --- |
| Unit | Logic with few collaborators | Fast, precise, most numerous |
| Integration | The behaviour *is* the interaction (SQL, serialization, HTTP) | Slower, catches real contracts |
| End-to-end | A user-visible path must hold | Slowest and flakiest; keep few |

The common failure is testing at the wrong level: mocking a database to test
a query builder proves your mock's shape, not that the SQL runs. Anything
whose correctness depends on an external system's behaviour needs a real one
(or a high-fidelity fake) at least once.

## Test doubles

| Double | Purpose | Risk |
| --- | --- | --- |
| Stub | Return canned values | Drifts from the real dependency |
| Fake | Working lightweight implementation (in-memory store) | Best default; costs maintenance |
| Mock | Assert on interactions | Couples the test to implementation |
| Spy | Record calls, delegate to the real thing | Usually preferable to a mock |

Rules of thumb: prefer fakes to mocks; never assert only on interactions when
you could assert on an outcome; and if a test needs more than about three
doubles, the unit under test has too many collaborators — that is a design
signal, not a testing problem.

## Applying the loop to untested code

You cannot write a red test for behaviour that already exists, so invert it:
**characterize first, then change.**

1. **Pin current behaviour.** Write tests that assert what the code does
   today, including the parts you believe are wrong. These pass immediately —
   that is expected; they are a net, not a specification.
2. **Verify the net.** Break the implementation deliberately (invert a
   condition, return a constant) and confirm tests fail. A characterization
   suite that survives sabotage is not protecting anything.
3. **Now do TDD** for the change: red test for the *new* behaviour, then
   the code, then refactor under the net.

For code that is hard to test at all, make the smallest structural change
that creates a seam — extract a function, inject a dependency, pass a clock
instead of calling `now()`. Do that under the characterization net, as a
pure refactor, before changing behaviour.

## What a good test name says

The name is documentation that runs. It should survive being read in a
failure summary with no other context.

| Weak | Strong |
| --- | --- |
| `test_parse` | `test_parse_rejects_duplicate_keys` |
| `test_user` | `test_user_lookup_returns_none_when_deleted` |
| `test_edge_case` | `test_split_handles_empty_input` |
| `test_bug_412` | `test_config_key_with_colon_is_not_truncated` |

Encode the condition and the expectation. `test_bug_412` is a lookup task for
whoever hits it in three years.

## Deciding when a failing test means "update the test"

After a change, a red test is a question, not an answer. Two legitimate
outcomes:

- **Behaviour intentionally changed.** Update the test, and say so
  explicitly in the change description. An unannounced test edit is
  indistinguishable from silencing a failure.
- **You broke something.** Fix the code.

The dangerous third path is updating the test *because it is red*, without
deciding which case you are in. If you cannot articulate why the old
assertion is now wrong, you are in case two.

## Interaction with other skills

- `systematic-debugging` produces the explanation that a bug-fix red test is
  written from. Do not write the test until you have the explanation.
- `verification-before-completion` consumes the output of this loop: a test
  observed failing then passing is exactly the evidence it demands.
- A project skill defining the repo's test taxonomy, naming conventions, or
  coverage floors takes precedence on those specifics.
