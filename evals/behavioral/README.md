<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# evals/behavioral/

Deterministic behavioral smoke checks for skill contracts. These are not LLM
grades; they assert that a skill still contains the load-bearing instructions,
references, and forbidden-shortcut fences that make the workflow safe to run.

Case files live in `cases/*.json`:

```json
{
  "skill": "cross-language-port",
  "requires": {
    "skill_contains": ["golden-I/O corpus"],
    "files_exist": ["reference.md"]
  },
  "forbids": {
    "skill_contains": ["eyeball equivalence"]
  }
}
```

Use these for invariants that should survive rewrites. Routing belongs in
`evals/cases/`; execution-quality checks that require a model remain a future
runner.
