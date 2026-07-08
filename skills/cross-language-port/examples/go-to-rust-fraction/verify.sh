#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bin="$(mktemp -u)"; trap 'rm -f "$bin"' EXIT
rustc --edition 2021 -O port.rs -o "$bin"
exec ../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
  "go run reference.go" "$bin"
