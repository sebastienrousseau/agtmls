#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: MIT
# Python -> Rust IBAN. Build the port, then run the shared golden-diff proof.
set -euo pipefail
cd "$(dirname "$0")"
bin="$(mktemp -u)"
trap 'rm -f "$bin"' EXIT
rustc --edition 2021 -O port.rs -o "$bin"
exec ../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
  "python3 reference.py" "$bin"
