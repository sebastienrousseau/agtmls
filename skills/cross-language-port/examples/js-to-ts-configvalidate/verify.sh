#!/usr/bin/env bash
# Differential golden-I/O proof for JS -> TS config validation.
set -euo pipefail
cd "$(dirname "$0")"
in="corpus/input.txt"; golden="corpus/expected.txt"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
node reference.js <"$in" >"$tmp/ref.out"
diff -u "$golden" "$tmp/ref.out" || { echo "FAIL: reference.js drifted" >&2; exit 1; }
node port.ts <"$in" >"$tmp/port.out"
diff -u "$golden" "$tmp/port.out" || { echo "DIVERGENCE: port.ts vs source" >&2; exit 1; }
echo "OK: reference.js and port.ts agree on $(grep -c . "$in") inputs."
