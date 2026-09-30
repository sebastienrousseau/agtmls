<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# evals/ — trigger-routing checks

Deterministic, zero-token checks that each skill's `description` actually
attracts its own prompts and repels others — the early-warning system for
description drift as the catalog grows. Run by `scripts/run-trigger-evals.py`
in CI.

## Case format (`cases/<skill-name>.json`)

```json
{
  "skill": "noyalib-ci-and-release",
  "positive": ["at least three prompts that SHOULD route to this skill"],
  "negative": [
    {"prompt": "a prompt another skill owns", "owner": "the skill that should win it"}
  ]
}
```

- **positive** — at least three prompts, each ranking the case's skill in
  the top-K (TF-IDF cosine of the prompt against every skill description).
- **negative** — at least two prompts, each naming the skill that should win
  it (`owner`); the owner must rank above the case's skill. A prompt no
  skill should win has no owner, so it cannot be a negative.
- **rank-1 floor** — the share of prompts whose intended skill ranks first
  (the case's skill for a positive, the owner for a negative) is held to
  `routing-floor.json`. It may only rise: `run-trigger-evals.py --update`
  records a better share.

Words are compared after light stemming, so "crash" meets "crashes" and
"write" meets "writing", as a model would read them.

This is a cheap *proxy* for the model's real routing judgment; it catches a
description that has stopped matching its own obvious prompts, not subtle
preference. Add a case file when you add a skill.

## Forward-compatible schema (behavioural evals)

For future behavioural evals (grading an execution trace, not just routing),
shape richer cases to Anthropic's skill-creator `evals.json` schema so
external tooling works unmodified:

```json
{ "id": "…", "prompt": "…", "expected_output": "…", "expectations": ["…"] }
```

The token-spending runner for those is intentionally deferred — the routing
proxy here is the free, always-on gate.

## Coverage

Starter cases cover a representative subset of the noyalib bundle. Filling in
one case file per skill is a standing task; every new skill SHOULD ship with
its case file.
