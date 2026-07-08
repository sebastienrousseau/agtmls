#!/usr/bin/env bash
# Differential golden-I/O proof for Rust -> Swift op evaluator.
set -euo pipefail
cd "$(dirname "$0")"
in="corpus/input.txt"; golden="corpus/expected.txt"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
rustc --edition 2021 -O reference.rs -o "$tmp/ref" 2>"$tmp/b.log" || { cat "$tmp/b.log" >&2; exit 1; }
"$tmp/ref" <"$in" >"$tmp/ref.out"
diff -u "$golden" "$tmp/ref.out" || { echo "FAIL: reference.rs drifted" >&2; exit 1; }
swift port.swift <"$in" >"$tmp/port.out"
diff -u "$golden" "$tmp/port.out" || { echo "DIVERGENCE: port.swift vs source" >&2; exit 1; }
echo "OK: reference.rs and port.swift agree on $(grep -c . "$in") inputs."
