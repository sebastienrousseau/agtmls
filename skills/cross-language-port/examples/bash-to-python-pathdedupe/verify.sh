#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: MIT
# Bash -> Python PATH dedupe. No build; run the shared golden-diff proof.
set -euo pipefail
cd "$(dirname "$0")"
exec ../../harness/golden-diff.sh corpus/input.txt corpus/expected.txt \
  "bash reference.sh" "python3 port.py"
