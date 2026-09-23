#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: MIT
set -euo pipefail
cd "$(dirname "$0")"
exec ../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
  "python3 reference.py" "go run port.go"
