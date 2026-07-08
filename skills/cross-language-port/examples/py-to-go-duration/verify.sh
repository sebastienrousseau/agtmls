#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec ../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
  "python3 reference.py" "go run port.go"
