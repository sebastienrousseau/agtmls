#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Regenerate the hash-pinned CI tool requirements from their .in files.
# CI installs them with `pip install --require-hashes -r`, so a tool and
# every one of its dependencies is fixed to bytes that were seen here
# (OpenSSF Scorecard Pinned-Dependencies). The .txt files are generated:
# edit the .in file and rerun this script, never the .txt.
set -euo pipefail
cd "$(dirname "$0")"

# The lowest Python each file must install on. skills-ref needs 3.11, and
# the jobs that install it skip 3.10.
floor() {
  case "$1" in
    skills-ref|coverage) echo 3.11 ;;
    *) echo 3.10 ;;
  esac
}

for input in *.in; do
  name="${input%.in}"
  body="$(uv pip compile --universal --python-version "$(floor "$name")" \
    --generate-hashes --no-header -q "$input")"
  {
    echo "# SPDX-FileCopyrightText: 2026 Sebastien Rousseau"
    echo "# SPDX-License-Identifier: Apache-2.0 OR MIT"
    echo "#"
    echo "# Generated from $input by .github/requirements/compile.sh; do not edit."
    printf '%s\n' "$body"
  } > "$name.txt"
done
