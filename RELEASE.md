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
