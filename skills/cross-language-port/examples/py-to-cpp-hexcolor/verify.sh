#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: MIT
set -euo pipefail
cd "$(dirname "$0")"
bin="$(mktemp -u)"; trap 'rm -f "$bin"' EXIT
c++ -std=c++23 -O2 -Wall -Wextra port.cpp -o "$bin"
exec ../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
  "python3 reference.py" "$bin"
