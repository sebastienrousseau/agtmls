#!/usr/bin/env bash
# Differential golden-I/O proof for the Bash -> Python PATH-dedupe port.
# 1. reference.sh must reproduce the committed golden output.
# 2. port.py must produce the SAME output on the same corpus.
# Exits non-zero on any drift or divergence.
set -euo pipefail
cd "$(dirname "$0")"

in="corpus/input.txt"
golden="corpus/expected.txt"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

bash reference.sh <"$in" >"$tmp/ref.out"
if ! diff -u "$golden" "$tmp/ref.out"; then
  echo "FAIL: reference.sh drifted from golden $golden" >&2
  exit 1
fi

python3 port.py <"$in" >"$tmp/port.out"
if ! diff -u "$golden" "$tmp/port.out"; then
  echo "DIVERGENCE: port.py disagrees with the source on the corpus" >&2
  exit 1
fi

echo "OK: reference.sh and port.py agree on $(grep -c . "$in") inputs."
