<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# templates/

Starting points for new AgtMLS registry artifacts.

Prefer `python3 scripts/agtmls.py scaffold-skill <name>` over copying these by
hand. The scaffold command replaces placeholder names and creates matching
routing, behavioral, and metadata files.

Skill metadata templates include a conservative `safety_policy`; update it before publishing a scaffolded skill.
