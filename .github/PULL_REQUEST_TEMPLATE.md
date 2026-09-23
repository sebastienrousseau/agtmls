<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

## Summary

<!-- What does this PR change and why? One or two sentences. -->

## Related issue

<!-- e.g. "Fixes #123". Use "N/A" if none. -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature or skill (non-breaking)
- [ ] Security hardening or policy update
- [ ] Breaking change (API, CLI, or manifest schema)
- [ ] Tooling, documentation, or CI only

## Checklist

- [ ] `make check` (every check in `checks.json`) passes cleanly
- [ ] `make test` (unit tests) passes
- [ ] `make bench` (routing and behavioral benchmark) passes 100%
- [ ] `make doctor` reports 0 warnings and 0 failures
- [ ] Generated artifacts updated via `scripts/sync-skill-frontmatter.py` and generators
- [ ] Commits follow Conventional Commits (header <= 50 chars, wrapped body <= 72 chars)
- [ ] Commits are signed with SSH or GPG key (`git commit -s`)
