#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Sign what a release ships, then verify it: index.json under
# agtmls-index@v1 (agtmls-spec chapter 9) and every attestation under
# agtmls-attestation@v1 (chapter 10), against this tree's ALLOWED_SIGNERS.
# release.yml runs it with the release key; rehearse-release-signing.sh
# runs it with a throwaway key, so the rehearsal is this exact code.
#
#   scripts/sign-release.sh <private key>     # from the repository root
set -euo pipefail
key="${1:?usage: scripts/sign-release.sh <private key>}"

# ssh-keygen asks before overwriting a signature, and nobody is there to answer.
rm -f index.json.sig
ssh-keygen -q -Y sign -f "$key" -n agtmls-index@v1 index.json
python3 scripts/sign-attestations.py --key "$key"

ssh-keygen -Y verify -f ALLOWED_SIGNERS -I agtmls-release \
  -n agtmls-index@v1 -s index.json.sig < index.json
python3 scripts/sign-attestations.py --verify
