<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Release Checklist

AgtMLS is a registry, so a release is valid only when the generated discovery
surface, plugin metadata, and validation gates agree.

1. Update `CHANGELOG.md`.
2. Update `.claude-plugin/plugin.json` version.
3. Update any changed `metadata.json` versions.
4. Regenerate the index:

   ```sh
   python3 scripts/agtmls.py index --write
   ```

5. Run the release dry-run:

   ```sh
   python3 scripts/release-dry-run.py --version $(python3 scripts/next-version.py)
   ```

6. Run the full gate:

   ```sh
   python3 scripts/agtmls.py check
   ```

7. Inspect consumer install behavior if setup changed:

   ```sh
   python3 scripts/agtmls.py status --target /path/to/repo --agent codex --skills-only
   ```

8. Confirm `VERSIONING.md`: versions increment by exactly `0.0.1`; the next release after `v0.0.1` is `v0.0.2`, and `v0.1.0` is forbidden until `v0.0.999` exists.
9. Tag only after CI is green.

## Tag protection

Treat published `v*` tags as immutable. Repository settings should protect `v*` tags from deletion or force-push where GitHub tag protection/rulesets are available.
