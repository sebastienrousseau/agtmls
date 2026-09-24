<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Benchmarks

What AgtMLS costs, how that was measured, and what the measurement does not
support. Every number here is produced by `scripts/bench.py` and every raw
sample is committed under [`benchmarks/results/`](benchmarks/results).

```console
python3 scripts/bench.py                  # measure and print
python3 scripts/bench.py --smoke          # one iteration; what the gate runs
python3 scripts/bench.py --check          # fail on a regression
python3 scripts/bench.py --write-baseline # re-record bench-baseline.json
python3 scripts/bench.py --scaling        # growth at 10x registry size
python3 scripts/bench.py --scaling --record  # ...and publish it to benchmarks/results/
```

## Method

- Every sample is a **fresh process**. Nothing is measured warm that a user
  would pay for cold.
- **3 warmup iterations, then 20 timed**, per workload.
- Timing is wall clock around the subprocess and **includes interpreter
  startup and imports**. That is what a person waiting at a prompt pays, and
  it is the basis on which the 100ms cold-start budget is stated.
- **P50 and P95 are nearest-rank percentiles**, not interpolated. An
  interpolated P95 reports a duration nobody observed.
- Throughput is not reported. None of these workloads is a throughput problem.
- Full-gate wall time is **not** a workload here. `run-all-checks.py` records
  its own duration on every run under `.agtmls/runs/`.

## Results

<!-- generated:latency sources="benchmarks/results/latency.json:3b9160518cdaa8c5b1c7dfc661b26339d81d012597f92e531feb67c67e3abaf3,bench-baseline.json:fef0199f5aec186e3c4c40d1ede0fe7d3f699c0bef5a6a2864c0c35dc8cb3ae0" -->
Recorded on the machine named in `bench-baseline.json`: macOS 26.7, arm64, Python 3.12.14.
One machine, 5 suite runs. No claim is made about any other machine.

| Workload | min ms | P50 ms | P95 ms | × calibration |
|---|---:|---:|---:|---:|
| `calibration` (bare interpreter) | 13.88 | 15.16 | 18.10 | 1.00 |
| `cli-list` | 41.98 | 44.74 | 46.04 | 3.03 |
| `cli-search` | 42.43 | 44.34 | 46.98 | 3.06 |
| `cli-show` | 42.34 | 45.65 | 88.28 | 3.05 |
| `cli-stats` | 43.26 | 46.07 | 55.40 | 3.12 |
| `digest-registry` (every skill) | 61.36 | 68.20 | 76.55 | 4.42 |
| `route-rank` (TF-IDF over every description) | 43.54 | 44.77 | 50.73 | 3.14 |
| `audit-all` (`--all --strict`) | 358.34 | 382.85 | 507.12 | 25.83 |
| `index-check` | 83.16 | 105.36 | 171.87 | 5.99 |

The 4 `cli-*` commands are the interactive surface: P50 between **44ms** and **46ms**, against the 100ms budget of scorecard criterion 3.10. About 15ms of that is the interpreter itself — the calibration row — so AgtMLS's own share of the fastest command is about 29ms.
<!-- /generated:latency -->

## Regression detection, and its limits

A baseline in absolute milliseconds is meaningless on a different machine, so
each workload is also recorded as a **ratio to the calibration workload**: a
bare interpreter, in its own fresh process. Ratios are taken over **minimum**
samples, because noise only ever adds time.

The threshold is **not** a round number picked in advance.
`--write-baseline` runs the whole suite five times, records each workload's
spread across those runs, and `--check` allows `max(20%, 3 × spread)`.

<!-- generated:thresholds sources="bench-baseline.json:fef0199f5aec186e3c4c40d1ede0fe7d3f699c0bef5a6a2864c0c35dc8cb3ae0" -->
On the recorded machine the spreads are 4.9% to 14.1%, so 4 of 9 workloads are gated at the full 20% of criterion 3.2 and `audit-all` at 21% and `cli-stats` at 25% and `digest-registry` at 35% and `index-check` at 42% and `route-rank` at 35%.
<!-- /generated:thresholds -->

`--check` measures **the same way the baseline was recorded**: three full
suite runs, minimum ratio per workload. Comparing a single run against a
minimum-of-five baseline is comparing two different statistics, and it shows.

Five designs were discarded, each on measurement rather than argument:

| Tried | Measured | Why it was dropped |
|---|---|---|
| sha256 loop as calibration | own min ranged 105–728ms across five idle rounds (CV 111%) | `cli-list / hash-loop` came out at CV 41%, worse than no normalisation at all |
| median-to-median ratios | calibration P50 moved 24.0 → 19.7ms between consecutive idle runs | swung a steady 240ms workload from 9.16× to 12.32× — a 34% move with nothing changed |
| interleaving calibration with every iteration | cli-list CV 6.6% against 5.6% unchanged | the residual spread is intrinsic per workload, not an artefact of sampling order |
| one suite run per `--check` | flagged `route-rank` at +33% on a run that touched nothing | false alarms teach people to ignore the gate |
| re-measuring only the suspects to confirm | **cleared a deliberately injected 25% regression** | a five-workload rerun loads the machine differently from a nine-workload one, so the confirmation is not the same measurement |

Verified in both directions on the recorded machine: a clean tree passes with
all eight workloads inside 20%, and a 10ms sleep injected into `cli-list`
fails with exactly one finding (`+37%`) and no false positives.

**The audit's cost is the rule count.** Every pattern rule is one pass of
the regex engine over every auditable file, about 7 ms per rule over the
registry's 145 files on the laptop, and case-insensitive matching is about
a third of that. Moving from 19 to 30 rules (agtmls-spec `6afdcd0`) took
`audit --all --strict` from 264 ms to 383 ms P50, and both baselines were
re-recorded rather than the budget widened: the 20% allowance is for the
same work getting slower, not for more work. A combined alternation of
every pattern was measured and costs the same as separate passes, so the
next step down is a prefilter or parallel files, not regex tuning.

**Ratios do not transfer between machines.** The ratio to calibration was
meant to make a baseline portable; it does not travel from a laptop to a CI
runner. The first CI run of `--check` against the laptop baseline flagged
every workload at +37–64% with nothing changed, while the same check passed
on the laptop. CI therefore runs `--check --baseline bench-baseline.ci.json`,
recorded on the runner itself by dispatching the `bench` workflow with
`record: true`. The laptop baseline, and everything in this document, stays
the published measurement.

**What this still does not survive: a thermally saturated machine.** Running
`--check` immediately after several back-to-back suite runs reported every
workload 47–106% slower, with nothing changed. Under sustained throttling the
CPU-bound workloads degrade further than the spawn-bound calibration, so the
ratio is not invariant. `--check` therefore belongs on an idle machine or a
dedicated CI job, and **not** inside the check gate — which runs `--smoke`
instead: one iteration per workload, asserting only that each still runs.

## Scaling

Criterion 3.5 asks that no hot path be worse than linear in registry size.
`--scaling` builds a synthetic registry of ten copies of every shipped skill
and measures against the real one. Raw numbers in
[`benchmarks/results/scaling.json`](benchmarks/results/scaling.json).

<!-- generated:scaling sources="benchmarks/results/scaling.json:d94f51561b37cb0fb5d397202ebb95c05b968ddd3610e1b34623d52e3040e8ad" -->
| Skills | `skill_digest` over all | Pairwise description scoring |
|---:|---:|---:|
| 31 | 29.69 ms | 1.89 ms |
| 310 | 208.49 ms | 209.07 ms |
| **growth for ×10** | **×7.02** | **×110.62** |

`skill_digest` measured ×7.02 for ×10 the corpus. Pairwise scoring measured ×110.62; at 31 skills it costs 1.89ms, and extrapolating quadratically from 310 skills it reaches roughly 2.2s at 1,000 skills and 19.6s at 3,000.
<!-- /generated:scaling -->

`skill_digest` is O(bytes), so it should grow no faster than the corpus; the
check fails if it ever grows more than 1.5× faster than the registry.

Pairwise description scoring — what `check-skill-collisions.py` does — is
**O(n²) by construction**: it compares every description with every other one,
and the growth row above is that curve. It is measured and reported rather than
asserted against a linear bound, because the comparison *is* the check. It is
not on a hot path — it runs once per gate, never per request. The extrapolation
above is the point at which it needs blocking or approximate nearest-neighbours,
and this table is how that will be noticed rather than discovered.

## What these numbers are not

- One machine, one operating system, one Python version.
- No claim about cross-device performance, sustained load, or CI runners.
- `audit-all` scales with the *content* of the registry, not only the skill
  count, so its cost moves when skills grow, not only when they multiply.
- The baseline was recorded on a laptop with frequency scaling. A runner with
  stable frequency will record smaller spreads and gate harder.
