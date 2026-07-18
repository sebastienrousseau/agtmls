<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# AgtMLS Registry Schema

`index.json` is a generated discovery surface for tools that need to inspect
the catalog without loading every skill body.

## Top-level fields

- `schema_version` — integer schema version. Increment only for incompatible
  structural changes.
- `name` — registry name.
- `description` — registry summary.
- `registry_version` — release version copied from `.claude-plugin/plugin.json`.
- `generated_by` — script that produced the file.
- `skill_count` — number of discovered `SKILL.md` files.
- `command_count` — number of installable command Markdown files.
- `coverage` — routing and behavioral eval coverage counts.
- `bundles` — skill counts by bundle, with `_general` for top-level reusable
  skills.
- `skills` — sorted skill records.
- `commands` — sorted command records.

## Skill fields

- `name` — skill name from frontmatter.
- `description` — flattened router description.
- `path` — repo-relative skill directory.
- `kind` — `general` or `project`.
- `bundle` — project bundle name, or `null` for general skills.
- `license` — explicit frontmatter license or repo default.
- `date` — optional frontmatter date.
- `metadata_path` — `metadata.json` source, either skill-local or inherited
  from a bundle.
- `version`, `owner`, `maturity`, `supported_agents`, `required_tools` —
  optional metadata loaded from `metadata.json`.
- `compatibility` — portable skill compatibility statement.
- `tags` — generated taxonomy tags.
- `references`, `scripts`, `assets` — repo-local adjunct files.
- `evals.routing` — whether `evals/cases/<skill>.json` exists.
- `evals.behavioral` — whether `evals/behavioral/cases/<skill>.json` exists.

## Command fields

- `name` — command file stem.
- `description` — command frontmatter description.
- `path` — repo-relative command Markdown path.

## Regeneration

Run:

```sh
python3 scripts/generate-skill-index.py --write
```

CI checks freshness with:

```sh
python3 scripts/generate-skill-index.py --check
```

Do not edit `index.json` manually.

## Lifecycle Metadata

`lifecycle.json` records the expected progression from local proposal to
published skill. Validate it with:

```sh
python3 scripts/validate-lifecycle.py
```

## Safety Policy

Each skill entry includes `safety_policy`, inherited from the skill metadata
file or bundle metadata file:

- `network_access`: `none`, `optional`, or `required`.
- `writes_files`: whether normal use edits files.
- `executes_commands`: whether normal use runs shell/tool commands.
- `handles_secrets`: whether the skill is expected to inspect or transform secrets.
- `requires_human_review`: whether results should be reviewed before publication or high-impact action.
- `risk_level`: `low`, `medium`, or `high`; high-risk skills must require human review.

## Providers and Profiles

`providers.json` defines native installer layouts and provider-neutral export
targets. `profiles.json` defines named subsets consumed by `agtmls.py install`
and `agtmls.py export`. These files are validated independently so adding a new
provider or profile is an intentional registry change.
