#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Push the release branch feat/v0.0.22 and open the pull request targeting main.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "Pushing branch feat/v0.0.22 to origin..."
git push origin feat/v0.0.22

echo "Opening release pull request..."
gh pr create --base main --head feat/v0.0.22 --title "chore: bump AgtMLS to 0.0.22" --body-file - <<'EOF'
This PR bumps AgtMLS to 0.0.22, adds binary provenance identity and OCSF export, and introduces a local SQLite context store.

Once merged, the squash commit is what the signed v0.0.22 tag points at, establishing cryptographic environment validation and SIEM integration.

## Highlights ⭐️

* **Cryptographic binary and runtime identity**: Bounded SHA-256 verification of Python host binaries and execution environments, protecting against tampering and hostile execution wrappers.
* **Open Cybersecurity Schema Framework (OCSF) export**: Maps static skill analysis findings to OCSF v1.3.0 Security Finding schema (Class UID 2001) for SIEM, SOAR, and data lake ingestion.
* **Local SQLite context and full-text search store**: Zero-dependency SQLite FTS5 store with BM25 relevance ranking for agent context indexing and fast skill retrieval.
* **Prompt statusline utility**: Pure shell statusline script supporting plain, tmux, and JSON output modes for shell prompts and multiplexers.

## What's Changed

* `chore: bump AgtMLS to 0.0.22` by @sebastienrousseau
* `feat: add binary identity and OCSF export` by @sebastienrousseau
* `feat: add SQLite context store and statusline` by @sebastienrousseau

## Validation

* `python3 scripts/release-dry-run.py --version 0.0.22`: passes with 2 artifacts.
* `python3 scripts/run-all-checks.py`: 72 of 72 passed with 0 failures and 0 warnings.
* `python3 scripts/check-complexity.py`: 0 functions and 0 files over ceilings.
* `ruff check .`: all checks passed.

## Checksums

SHA-256 of the artifacts produced on this branch:

```text
094a40687c44b7161cdac000bda8430cb1840d0258b43ad6b52f0c1b5139040d  dist/agtmls-0.0.22.tar.gz
c251934daf27b788e8e52a8551f5690910c3ad287bd2c7355e67515f31fa5f95  dist/agtmls-0.0.22-py3-none-any.whl
```

**Full Changelog**: https://github.com/sebastienrousseau/agtmls/compare/v0.0.21...feat/v0.0.22
EOF
