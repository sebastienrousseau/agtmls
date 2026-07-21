<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Tag Protection

Published AgtMLS release tags are immutable. Protect every `v*` tag with a
GitHub ruleset before making routine releases.

## Recommended GitHub Ruleset

1. Open **Settings > Rules > Rulesets**.
2. Create a new tag ruleset.
3. Target tags matching `v*`.
4. Block tag deletion.
5. Block force updates.
6. Require signed tags when available for the repository.
7. Restrict bypass permissions to repository administrators.
8. Save the ruleset and verify `v0.0.1` cannot be deleted or moved by a normal
   maintainer token.

## Release Rule

The next tag after `v0.0.1` is `v0.0.2`. The release workflow,
`scripts/validate-version-policy.py`, and `scripts/bump-version.py` all enforce
that public releases advance by exactly `0.0.1` on the `0.0.x` line.

## Ruleset status

Active repository ruleset: `Protect release tags` (`19381166`) targeting `refs/tags/v*`. It blocks deletion and non-fast-forward updates.

Ruleset URL: https://github.com/sebastienrousseau/agtmls/rules/19381166
