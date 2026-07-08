#!/usr/bin/env bash
# Differential golden-I/O proof for Python -> Go duration parser.
set -euo pipefail
cd "$(dirname "$0")"
in="corpus/input.txt"; golden="corpus/expected.txt"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
python3 reference.py <"$in" >"$tmp/ref.out"
diff -u "$golden" "$tmp/ref.out" || { echo "FAIL: reference.py drifted" >&2; exit 1; }
go run port.go <"$in" >"$tmp/port.out"
diff -u "$golden" "$tmp/port.out" || { echo "DIVERGENCE: port.go vs source" >&2; exit 1; }
echo "OK: reference.py and port.go agree on $(grep -c . "$in") inputs."
