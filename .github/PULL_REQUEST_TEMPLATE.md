<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->

<!--
PR description template. Global rule: see ~/Code/AGENTS.md "PR Descriptions"
and "Release Page Format" (aligned with https://github.com/sebastienrousseau/passmcp/releases/tag/v0.0.5).
Rules baked into this shape:
  - A two-line BLUF (bottom line up front) that announces the PR: line 1 begins
    "This PR " and says what it does; line 2 says why it matters or the outcome.
    Separate line 1 and line 2 each with a blank line: a single newline soft-wraps
    into one paragraph in Markdown, so a blank line is what makes each render on
    its own line. No paragraph above.
  - Never use the em dash character in the body. Use commas, colons, parentheses,
    or a spaced hyphen instead.
  - Write like a person wrote it: direct, concrete, friendly, no filler, no AI tells.
  - For external upstream maintainers, open with a bare-name greeting on its
    own line: exactly "Hi <name>," and nothing more, no thanks or extra clause.
    If the repository is the user's own (Sebastien), omit the greeting entirely
    and start directly with the BLUF.
  - No "Generated with Claude Code" or other tool-attribution footer.
Keep the sections and their order. Fill every placeholder from real evidence.
-->

This PR <!-- announces what it does, in one plain line -->.

<!-- why it matters or the outcome, in one plain line -->

## Highlights ⭐️

* **<!-- HEADLINE -->**: <!-- one or two plain sentences on what changed for the user -->.
* **<!-- HEADLINE -->**: <!-- one or two plain sentences -->.
* **<!-- HEADLINE -->**: <!-- one or two plain sentences -->.

## What's Changed

* `<!-- COMMIT_SUBJECT -->` by @<!-- AUTHOR -->

## Validation

* `python3 scripts/run-all-checks.py`: <!-- result, e.g. 73 check(s) passed -->.
* `python3 scripts/run-coverage.py --scope unit`: <!-- unit test coverage percentage -->.

## Checksums

<!-- SHA-256 of artifacts produced on this branch, in a fenced text block -->

**Full Changelog**: https://github.com/sebastienrousseau/agtmls/compare/<!-- PREVIOUS_TAG -->...<!-- CURRENT_TAG -->
