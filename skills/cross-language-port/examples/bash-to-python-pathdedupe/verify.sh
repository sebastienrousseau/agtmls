#!/usr/bin/env bash
# Bash -> Python PATH dedupe. No build; run the shared golden-diff proof.
set -euo pipefail
cd "$(dirname "$0")"
exec ../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
  "bash reference.sh" "python3 port.py"
