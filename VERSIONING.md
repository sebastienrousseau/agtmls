<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# Versioning Policy

AgtMLS uses a deliberately conservative pre-1.0 patch-line release policy.

## Current Rule

- The only valid public release line is `0.0.x`.
- Versions increment by exactly `0.0.1`.
- After `v0.0.1`, the next release is `v0.0.2`; skipping directly to
  `v0.0.999`, `v0.1.0`, or any larger jump is invalid.
- `v0.0.999` is the last patch release in the runway before any future
  `v0.1.0`. It is not a shortcut release target.
- `v0.1.0` is forbidden until `v0.0.999` has been released and tagged.

## Metadata Contract

The same version must appear in the plugin manifest, generated registry index,
agent card, provenance subject, bundle metadata, and changelog release heading.
Generated artifacts must be regenerated after every version change.

## Enforcement

`python3 scripts/validate-version-policy.py` enforces this policy. CI fetches
tags before running validators so the script can reject release jumps relative
to the latest published `v0.0.x` tag.
