<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Release Checklist

AgtMLS is a registry, so a release is valid only when the generated discovery
surface, plugin metadata, and validation gates agree.

1. Run `python3 scripts/bump-version.py --version $(python3 scripts/next-version.py)` to update release metadata, changelog, and generated artifacts.
2. Inspect the generated diff.
3. Regenerate the index if any manual correction was needed:

   ```sh
   python3 scripts/agtmls.py index --write
   ```

4. Run the release dry-run:

   ```sh
   python3 scripts/release-dry-run.py --version $(python3 scripts/next-version.py)
   ```

5. Run the full gate:

   ```sh
   python3 scripts/agtmls.py check
   ```

6. Inspect consumer install behavior if setup changed:

   ```sh
   python3 scripts/agtmls.py status --target /path/to/repo --agent codex --skills-only
   ```

7. Confirm `VERSIONING.md`: versions increment by exactly `0.0.1`; the next release after `v0.0.1` is `v0.0.2`, and `v0.1.0` is forbidden until `v0.0.999` exists.
8. Tag only after CI is green.

## Tagging, publishing and the audit

A pushed `v*` tag cannot be deleted or moved, so nothing is pushed until
`scripts/release-preflight.py` passes, and nothing counts as released until
`scripts/release-audit.py` reads it back from every place it was published.

1. Write the release notes in `docs/release-notes/v<version>.md`: a
   `## Summary` of user-visible changes as bullets, and a `## Checksums`
   section. A commit list is not a summary.
2. Create the signed, annotated tag on the release commit:

   ```sh
   git tag -s v<version> <commit> -m "AgtMLS v<version>"
   ```

3. Run the preflight. It checks the tag is signed by a key in `KEYS.asc`,
   titled exactly `AgtMLS v<version>`, points at `<commit>`, and that every
   packaged version at that commit is `<version>`:

   ```sh
   python3 scripts/release-preflight.py --tag v<version> --commit <commit> \
       --notes docs/release-notes/v<version>.md --sums <SHA256SUMS>
   ```

   The artifacts are built by `release.yml` after the tag is pushed. Until the
   workflow creates a draft release before building, the notes' Checksums
   section says `pending` and the preflight runs with `--pending-checksums`;
   the checksums are added from the release's `SHA256SUMS` before the next
   step.
4. Push the tag. `release.yml` builds, creates the GitHub release, and stops
   at the `pypi` environment, which needs a maintainer's approval.
5. Replace the release body with the finished notes
   (`gh release edit v<version> --notes-file docs/release-notes/v<version>.md`)
   and check what was published so far:

   ```sh
   python3 scripts/release-audit.py --tag v<version> --commit <commit> --before-pypi
   ```

6. Approve the `pypi` deployment in the Actions run, then run the audit again
   without `--before-pypi`. The release is done when it passes.

## Tag protection

Treat published `v*` tags as immutable. See `docs/tag-protection.md`. Repository settings should protect `v*` tags from deletion or force-push where GitHub tag protection/rulesets are available.
