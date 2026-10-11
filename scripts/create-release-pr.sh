#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Push the release branch feat/v0.0.21 and open the pull request targeting main.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "Pushing branch feat/v0.0.21 to origin..."
git push origin feat/v0.0.21

echo "Opening release pull request..."
gh pr create --base main --head feat/v0.0.21 --title "chore: bump AgtMLS to 0.0.21" --body-file - <<'EOF'
This PR bumps AgtMLS to 0.0.21 and adds cross-platform portability enhancements and security hardening.

Once merged, the squash commit is what the signed v0.0.21 tag points at, establishing shell-free workspace setup and bounded memory execution.

## Highlights ⭐️

* **Native cross-platform workspace installer**: Pure Python installer module replaces dependency on bash and handles environments lacking symlink privileges with automatic copy fallbacks.
* **Bounded streaming digest calculation**: File hashing streams in 64 KiB chunks, preventing memory spikes on large skill artifacts and embedded targets.
* **Supply chain and traversal hardening**: Bit-for-bit reproducible packaging with normalized tar metadata, recursive symlink rejection during skill imports, and resilient gate diagnostic persistence.
* **Complexity ceiling headroom**: Uninstallation prompt and lockfile routines extracted from scripts/agtmls.py into scripts/_lib/uninstall_steps.py, bringing file complexity well below the 500-line ceiling.

## What's Changed

* `chore: bump AgtMLS to 0.0.21` by @sebastienrousseau
* `refactor: harden portability and cross-platform I/O` by @sebastienrousseau

## Validation

* `python3 scripts/release-dry-run.py --version 0.0.21`: passes with 2 artifacts.
* `python3 scripts/run-all-checks.py`: 72 of 72 passed with 0 failures and 0 warnings.
* `python3 scripts/run-coverage.py --scope core`: 100.0% (2559 statements, 848 branches).
* `python3 scripts/run-coverage.py --scope unit`: 100.0% (8768 statements, 2928 branches).
* `python3 scripts/check-complexity.py`: 0 functions and 0 files over ceilings.
* `ruff check .`: all checks passed.

## Checksums

SHA-256 of the artifacts produced on this branch:

```text
c9d29e417eb1a354722827df0499a6721e190655db686e60f0eb5b0bc56a5f14  dist/agtmls-0.0.21.tar.gz
2b2cd6650b09779155021c651006c00b0f7ccfd5f75df01171ba116f15728b01  dist/agtmls-0.0.21-py3-none-any.whl
```

**Full Changelog**: https://github.com/sebastienrousseau/agtmls/compare/v0.0.20...feat/v0.0.21
EOF
