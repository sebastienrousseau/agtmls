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
  "positive": ["prompts that SHOULD route to this skill"],
  "negative": ["prompts that should NOT rank this skill #1"]
}
```

- **positive** — each prompt must rank the owning skill in the top-K
  (TF-IDF cosine of the prompt against every skill description).
- **negative** — each prompt must NOT rank the owning skill #1.

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
