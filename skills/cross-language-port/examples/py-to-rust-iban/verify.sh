#!/usr/bin/env bash
# Differential golden-I/O proof for the Python -> Rust IBAN port.
# 1. reference.py must reproduce the committed golden output.
# 2. port.rs must produce the SAME output on the same corpus.
# Exits non-zero on any drift or divergence.
set -euo pipefail
cd "$(dirname "$0")"

in="corpus/input.txt"
golden="corpus/expected.txt"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# 1. Source reproduces the golden (guards against the reference drifting).
python3 reference.py <"$in" >"$tmp/ref.out"
if ! diff -u "$golden" "$tmp/ref.out"; then
  echo "FAIL: reference.py drifted from golden $golden" >&2
  exit 1
fi

# 2. Port matches the golden (the equivalence proof).
rustc --edition 2021 -O port.rs -o "$tmp/port" 2>"$tmp/build.log" || {
  cat "$tmp/build.log" >&2
  exit 1
}
"$tmp/port" <"$in" >"$tmp/port.out"
if ! diff -u "$golden" "$tmp/port.out"; then
  echo "DIVERGENCE: port.rs disagrees with the source on the corpus" >&2
  exit 1
fi

echo "OK: reference.py and port.rs agree on $(grep -c . "$in") inputs."
