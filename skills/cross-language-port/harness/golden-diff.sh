#!/usr/bin/env bash
# Reusable differential golden-I/O runner for cross-language ports.
#
# Proves behavioural equivalence in two steps:
#   1. the SOURCE still reproduces the committed golden output (guards the
#      reference against drift), then
#   2. the PORT produces the SAME output on the same corpus.
# Exits non-zero (with a unified diff) on any drift or divergence.
#
# Usage:
#   golden-diff.sh <input> <golden> <source-cmd> <port-cmd>
# where <source-cmd> and <port-cmd> are shell command strings that read
# stdin and write stdout (build your binary first, then pass its path).
#
# Example (from an example's verify.sh, after compiling ./port to $bin):
#   ../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
#       "python3 reference.py" "$bin"
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: golden-diff.sh <input> <golden> <source-cmd> <port-cmd>" >&2
  exit 2
fi

in="$1"
golden="$2"
source_cmd="$3"
port_cmd="$4"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

eval "$source_cmd" <"$in" >"$tmp/ref.out"
if ! diff -u "$golden" "$tmp/ref.out"; then
  echo "FAIL: source drifted from golden ($golden)" >&2
  exit 1
fi

eval "$port_cmd" <"$in" >"$tmp/port.out"
if ! diff -u "$golden" "$tmp/port.out"; then
  echo "DIVERGENCE: port disagrees with the source on the corpus" >&2
  exit 1
fi

echo "OK: source and port agree on $(grep -c . "$in") inputs."
