#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Compact AgtMLS statusline indicator for bash, zsh, and tmux prompts.
# Usage:
#   scripts/agtmls-statusline.sh [--plain | --tmux | --json]
set -euo pipefail

MODE="${1:---plain}"

find_repo_root() {
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git rev-parse --show-toplevel
    else
        pwd
    fi
}

ROOT="$(find_repo_root)"
INDEX_FILE="${ROOT}/index.json"

count_skills() {
    if [[ -f "${INDEX_FILE}" ]]; then
        if command -v jq >/dev/null 2>&1; then
            jq -r '.skills | length' "${INDEX_FILE}" 2>/dev/null || echo "0"
        elif command -v python3 >/dev/null 2>&1; then
            python3 -c "import json, sys; data=json.load(open(sys.argv[1])); print(len(data.get('skills', [])))" "${INDEX_FILE}" 2>/dev/null || echo "0"
        else
            grep -c '"name":' "${INDEX_FILE}" || echo "0"
        fi
    elif [[ -d "${ROOT}/skills" ]]; then
        find "${ROOT}/skills" -maxdepth 2 -name "SKILL.md" 2>/dev/null | wc -l | tr -d ' '
    else
        echo "0"
    fi
}

SKILL_COUNT="$(count_skills)"

case "${MODE}" in
    --json)
        cat <<EOF
{"skills": ${SKILL_COUNT}, "status": "ok"}
EOF
        ;;
    --tmux)
        echo "#[fg=colour75,bold]AgtMLS:#[default] #[fg=colour255]${SKILL_COUNT} skills#[default]"
        ;;
    --plain|*)
        echo "AgtMLS: ${SKILL_COUNT} skills"
        ;;
esac
