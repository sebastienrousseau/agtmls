<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Systematic debugging — reference

Depth for `SKILL.md`. Load when the four phases need technique: which
localization method fits the symptom, how to handle a bug that will not
reproduce reliably, and how to instrument without drowning in output.

## Localization by symptom class

### Crash / exception with a stack trace

The trace names the location; it rarely names the cause. Work outward:

1. Read the **innermost frame you own**. Library frames are usually
   downstream of your bad input.
2. At that frame, print every input. The bug is nearly always "this value is
   not what I assumed".
3. Walk up one frame at a time until you find where the bad value was born.

### Wrong value, no crash

Bisect the call stack with assertions. Pick the midpoint of the pipeline and
assert the invariant you believe holds:

```python
assert isinstance(rows, list) and all("id" in r for r in rows), rows[:3]
```

Correct at the midpoint means the bug is downstream; incorrect means
upstream. Repeat. This finds the transition point in log₂(depth) steps.

### Hang or timeout

Get a stack dump of the live process rather than guessing:

| Runtime | Method |
| --- | --- |
| Python | `py-spy dump --pid <pid>`, or `faulthandler.dump_traceback_later` |
| Rust | `gdb -p <pid>` then `thread apply all bt` |
| Go | `SIGQUIT` dumps all goroutine stacks |
| Node | `kill -SIGUSR1 <pid>` then attach the inspector |
| JVM | `jstack <pid>` |

Two dumps a few seconds apart tell you whether it is spinning (stack moves)
or blocked (stack identical).

### Regression after a change

`git bisect` is the fastest correct answer, and it is scriptable:

```sh
git bisect start <bad-commit> <good-commit>
git bisect run ./repro.sh     # exit 0 = good, non-zero = bad
```

Write `repro.sh` first and confirm it exits non-zero on the bad commit and
zero on the good one. A bisect driven by a flaky script produces a confident
wrong answer.

### Works locally, fails in CI

The difference is always environmental. Enumerate deltas rather than
guessing: OS and architecture, language version, dependency lockfile
resolution, environment variables, filesystem case sensitivity, timezone and
locale, available cores (concurrency bugs surface on different core counts),
network access, and test ordering or parallelism.

Reproduce the CI environment locally (container image, same command line) or
add instrumentation to the CI run that prints the delta candidates.

## Intermittent failures

A bug that fails 1-in-N needs different handling. Do not proceed to Phase 2
with a 30% reproduction — you will misread noise as signal.

**First, raise the failure rate.** You need something near-deterministic:

- Loop it: `for i in $(seq 200); do ./repro || break; done`
- Increase concurrency, shrink timeouts, reduce buffer sizes.
- Randomize test order and run with a fixed seed you can replay.
- Add contention: run under load, or pin to one core.
- Use a race detector: `go test -race`, `-fsanitize=thread`, Miri for Rust.

**Then classify.** Intermittent bugs are almost always one of:

| Class | Signature | Confirm by |
| --- | --- | --- |
| Race | Fails more under load or more cores | Race detector; forced interleaving |
| Ordering | Fails only in some test orders | Fixed-seed shuffle, then replay |
| Time | Fails near midnight, month ends, DST | Freeze the clock and replay |
| Resource | Fails after N runs | Watch fds, memory, connections over time |
| External | Fails when a network/service is slow | Stub the dependency |
| Uninitialized | Fails on some machines only | Sanitizer / valgrind |

**Never** conclude a race is fixed because it stopped reproducing. Either the
explanation shows the interleaving is now impossible, or run the amplified
reproduction long enough that absence is meaningful — and say which.

## Instrumentation that stays readable

- **Print values, not milestones.** `print("here")` tells you control flow
  you could have read. `print(f"{key=} {len(rows)=}")` tells you state.
- **Include identity.** In concurrent code, log the thread/task/request id or
  the interleaving is unreadable.
- **Log the boundary, not the middle.** Entry and exit of the suspect region,
  with inputs and outputs. Then bisect inward.
- **Diff two runs.** For "works with A, fails with B", log both to files and
  `diff` them. The first divergent line is the localization.
- **Remove it before committing** — or promote it to a real log line with a
  level. Debug prints in a diff are noise a reviewer must evaluate.

## The explanation, written down

The Phase 3 artifact is worth keeping. A good explanation has four parts:

1. **Trigger** — the input or condition that starts it.
2. **Mechanism** — the specific code path, with file and line.
3. **Symptom** — how the mechanism surfaces to the user.
4. **Prediction** — what else must therefore fail, and what must not.

Example:

> **Trigger:** any config key containing `:`.
> **Mechanism:** `config.py:88` uses `line.split(":")[0]` as the key,
> truncating at the first colon.
> **Symptom:** `db:host` is stored as `db`, so the lookup at `config.py:140`
> misses and silently returns the default `localhost`.
> **Prediction:** `log:level` and `cache:ttl` are also silently defaulted;
> `db_host` (underscore) is unaffected.

Checking the prediction is what separates an explanation from a story. Both
predicted cases took one command each to confirm.

## Interaction with other skills

- `verification-before-completion` is the gate **after** Phase 4: it demands
  the failing-first evidence this process produces.
- `test-driven-development` shares Phase 4's discipline — the regression test
  is a red test written before the fix.
- A project-specific debugging playbook (symptom tables, subsystem routing)
  should be loaded **first** when one exists; it short-circuits Phase 2 for
  known-shaped bugs. Return here when the symptom is not in its table.
