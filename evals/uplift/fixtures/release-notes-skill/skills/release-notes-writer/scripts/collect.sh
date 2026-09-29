#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: MIT
set -euo pipefail
git log --merges --oneline "${1:-HEAD~20}..HEAD"
