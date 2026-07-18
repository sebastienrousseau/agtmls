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

7. Tag only after CI is green.
