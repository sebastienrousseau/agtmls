<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# evals/uplift/: does the skill help?

Routing cases (`evals/cases/`) show that a description attracts its prompts.
Behavioural cases (`evals/behavioral/`) show that a `SKILL.md` still says what
it must. Neither shows that the skill changes what an agent does. A skill can
pass both and still be ignored, or make the agent worse. An uplift case runs
the same task in real agents with and without the skill, and grades both
answers the same way.

A skill is `draft` until its uplift run on at least two agents (Claude Code
and Codex) shows that it helps. A skill that shows no gain is retired, not
kept (`authoring-portable-skills`, "Draft until measured").

## Case format (`cases/<skill>.json`)

```json
{
  "skill": "vetting-a-skill-before-install",
  "fixture": "acme-skills",
  "prompt": "Should we install the plugin in ./repo? ...",
  "expectations": [
    {"id": "transcript-egress", "means": "names the hook that uploads the transcript", "pattern": "transcript"}
  ]
}
```

- `fixture` is a directory in `fixtures/` with known flaws planted in it. Each
  run gets a fresh copy at `./repo`, never in the directory the agent runs
  in, so a fixture's bad `.claude/settings.json` cannot configure the agent
  reading it. Fixture scripts are inert: every host they name ends in
  `.invalid`.
- Each `expectation` is one planted flaw. The answer finds it when `pattern`
  (a case-insensitive regular expression) matches. Grading is deterministic,
  so a difference between the arms comes from the agent, not from a judge.

## Running

```console
python3 scripts/run-uplift-evals.py --check      # validate cases; the gate runs this
python3 scripts/run-uplift-evals.py --agent claude --agent codex --trials 5 \
    --codex-model <model> --jobs 4 --out results.json --transcripts /tmp/tx
python3 scripts/run-uplift-evals.py --render results.json
```

A run spends tokens on the agents' own logins, so it is never part of the
gate. Each trial runs both arms, alternating which goes first. Both arms are
cut off from the user's own setup: Claude Code loads project settings only
(no user skills, CLAUDE.md, hooks or MCP servers), and Codex gets a fresh
`CODEX_HOME` holding only its login. The "with" arm installs the skill where
`agtmls install` would (`.claude/skills`, `.codex/skills`). `Skill read`
reports how often the agent actually opened it.

The results file records the commit, each skill's digest, each run's answer
and which flaws it found, so any grade can be checked again later. Results
are kept under `docs/evidence/`, not here, because `evals/` ships in the
wheel.

## Limits

- A pattern can miss a flaw described in words it does not anticipate. The
  patterns were calibrated on one trial per agent and arm, widened only where
  an answer named a flaw in other words, and frozen before the measured run.
  That calibration run is not part of any result.
- Five trials per arm show a large effect, not a small one. Nothing here
  claims statistical significance.
- A skill that already appears in the agent's training, or a flaw that an
  agent finds without help, leaves little room for a gain. A delta of zero
  on a case every arm aces says the case is too easy, not that the skill is
  useless.
