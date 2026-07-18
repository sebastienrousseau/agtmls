<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# commands/

Slash-command bundles for agent clients that support a command directory.

This directory is intentionally present so `.claude-plugin/plugin.json` can
declare a stable commands path. Add command files here when a workflow should be
invoked explicitly instead of discovered through a `SKILL.md` description.
