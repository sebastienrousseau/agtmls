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

<!-- generated:latency sources="benchmarks/results/latency.json:242aed18de0eedae2c2cdf5ba07788a02a17a820ca6fdb09e1b812ad84be1050,bench-baseline.json:85c6d792e846854288665de208f9ca1029f7c769b01dcbae06ce2545fc4dcc35" -->
Recorded on the machine named in `bench-baseline.json`: macOS 26.7, arm64, Python 3.12.14.
One machine, 5 suite runs. No claim is made about any other machine.

| Workload | min ms | P50 ms | P95 ms | × calibration |
|---|---:|---:|---:|---:|
| `calibration` (bare interpreter) | 11.75 | 12.55 | 14.67 | 1.00 |
| `cli-list` | 36.05 | 37.52 | 45.42 | 3.07 |
| `cli-search` | 36.05 | 37.41 | 43.04 | 3.07 |
| `cli-show` | 37.99 | 47.28 | 64.55 | 3.23 |
| `cli-stats` | 34.51 | 48.40 | 65.65 | 2.94 |
| `digest-registry` (every skill) | 44.15 | 47.73 | 59.47 | 3.76 |
| `route-rank` (TF-IDF over every description) | 33.41 | 37.98 | 41.68 | 2.84 |
| `audit-all` (`--all --strict`) | 206.70 | 263.98 | 392.56 | 17.59 |
| `index-check` | 64.08 | 82.78 | 120.88 | 5.45 |

The 4 `cli-*` commands are the interactive surface: P50 between **37ms** and **48ms**, against the 100ms budget of scorecard criterion 3.10. About 13ms of that is the interpreter itself — the calibration row — so AgtMLS's own share of the fastest command is about 25ms.
<!-- /generated:latency -->

## Regression detection, and its limits

A baseline in absolute milliseconds is meaningless on a different machine, so
each workload is also recorded as a **ratio to the calibration workload**: a
bare interpreter, in its own fresh process. Ratios are taken over **minimum**
samples, because noise only ever adds time.

The threshold is **not** a round number picked in advance.
`--write-baseline` runs the whole suite five times, records each workload's
spread across those runs, and `--check` allows `max(20%, 3 × spread)`.

<!-- generated:thresholds sources="bench-baseline.json:85c6d792e846854288665de208f9ca1029f7c769b01dcbae06ce2545fc4dcc35" -->
On the recorded machine the spreads are 1.2% to 7.5%, so 8 of 9 workloads are gated at the full 20% of criterion 3.2 and `cli-search` at 23%.
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

**What this still does not survive: a thermally saturated machine.** Running
`--check` immediately after several back-to-back suite runs reported every
workload 47–106% slower, with nothing changed. Under sustained throttling the
CPU-bound workloads degrade further than the spawn-bound calibration, so the
ratio is not invariant. `--check` therefore belongs on an idle machine or a
dedicated CI job, and **not** inside the 66-check gate — which runs `--smoke`
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
