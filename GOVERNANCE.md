<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

# Governance

How decisions get made in AgtMLS.

## Current model: single maintainer (BDFL)

`agtmls` is maintained by [Sebastien Rousseau](https://github.com/sebastienrousseau), who has final say on scope, design, and releases.

The maintainer commits to:

- Responding to security reports within the SLA in [SECURITY.md](SECURITY.md).
- Giving clear rationale when a contribution or proposed skill is declined.
- Documenting architectural decisions in [`docs/adr/`](docs/adr/).
- Keeping `main` continuously releasable with CI green at every merge.

## Contribution criteria

Contributions are evaluated against these priorities:

1. **Does it preserve the dependency-free contract?** AgtMLS scripts must remain stdlib-only.
2. **Is it cross-agent compatible?** Skills must adhere to the Agent Skills specification and pass behavioral/routing evals across supported providers.
3. **Does it maintain strict quality standards?** Every skill must pass frontmatter validation, collision checks (< 0.75 threshold), and licensing requirements.
