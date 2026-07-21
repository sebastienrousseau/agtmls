<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Repository Protection

Published AgtMLS release tags are immutable, and `main` requires a green validation check before changes land. Protect both surfaces with GitHub rulesets before making routine releases.

## Recommended Tag Ruleset

1. Open **Settings > Rules > Rulesets**.
2. Create a new tag ruleset.
3. Target tags matching `v*`.
4. Block tag deletion.
5. Block force updates.
6. Require signed tags when available for the repository.
7. Restrict bypass permissions to repository administrators.
8. Save the ruleset and verify `v0.0.1` cannot be deleted or moved by a normal
   maintainer token.

## Recommended Main Branch Ruleset

1. Open **Settings > Rules > Rulesets**.
2. Create a new branch ruleset.
3. Target branches matching `main`.
4. Block branch deletion.
5. Block force pushes / non-fast-forward updates.
6. Require the `validate-skills` status check.
7. Enable strict status-check policy so branches must be current before merge.
8. Restrict bypass permissions to repository administrators.

## Release Rule

The next tag after `v0.0.2` is `v0.0.3`. The release workflow,
`scripts/validate-version-policy.py`, and `scripts/bump-version.py` all enforce
that public releases advance by exactly `0.0.1` on the `0.0.x` line.

## Ruleset Status

Active repository ruleset: `Protect release tags` (`19381166`) targeting `refs/tags/v*`. It blocks deletion and non-fast-forward updates.

Ruleset URL: https://github.com/sebastienrousseau/agtmls/rules/19381166

Active repository ruleset: `Require validate on main` (`19410401`) targeting `refs/heads/main`. It blocks deletion, blocks non-fast-forward updates, and requires the `validate-skills` check with strict update policy.

Ruleset URL: https://github.com/sebastienrousseau/agtmls/rules/19410401
