#!/usr/bin/env bash
# Differential golden-I/O proof for Go -> Rust fraction reduce.
set -euo pipefail
cd "$(dirname "$0")"
in="corpus/input.txt"; golden="corpus/expected.txt"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
go run reference.go <"$in" >"$tmp/ref.out"
diff -u "$golden" "$tmp/ref.out" || { echo "FAIL: reference.go drifted" >&2; exit 1; }
rustc --edition 2021 -O port.rs -o "$tmp/port" 2>"$tmp/b.log" || { cat "$tmp/b.log" >&2; exit 1; }
"$tmp/port" <"$in" >"$tmp/port.out"
diff -u "$golden" "$tmp/port.out" || { echo "DIVERGENCE: port.rs vs source" >&2; exit 1; }
echo "OK: reference.go and port.rs agree on $(grep -c . "$in") inputs."
