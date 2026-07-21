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

## Tag protection

Treat published `v*` tags as immutable. See `docs/tag-protection.md`. Repository settings should protect `v*` tags from deletion or force-push where GitHub tag protection/rulesets are available.
