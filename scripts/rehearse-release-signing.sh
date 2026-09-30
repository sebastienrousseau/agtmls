#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
#
# Rehearse the release's signing end to end, with a throwaway key.
#
# The release key lives only in the protected release environment, which
# deploys only from a v0.0.* tag, so the real signing runs first on a tag.
# This runs the same steps on a copy of the tracked tree: trust a throwaway
# key as agtmls-release, sign with scripts/sign-release.sh (the script
# release.yml runs), build the sdist and the wheel from it as the release
# does, then check the wheel with scripts/verify-wheel-signatures.py (the
# check release.yml runs before publishing). Nothing leaves the copy.
#
#   scripts/rehearse-release-signing.sh
#   BUILD="uvx --from build pyproject-build" scripts/rehearse-release-signing.sh
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir "$work/tree"

# The tracked tree, as the release checks it out.
(cd "$repo" && git ls-files -z | xargs -0 tar -cf -) | tar -C "$work/tree" -xf -

ssh-keygen -q -t ed25519 -N "" -C "release rehearsal" -f "$work/key"
printf 'agtmls-release namespaces="agtmls-index@v1,agtmls-attestation@v1,agtmls-advisory@v1" %s\n' \
  "$(cat "$work/key.pub")" > "$work/tree/ALLOWED_SIGNERS"

cd "$work/tree"
scripts/sign-release.sh "$work/key"
# shellcheck disable=SC2086  # BUILD is a command line, split on purpose
${BUILD:-python3 -m build} --outdir dist . >/dev/null
python3 scripts/verify-wheel-signatures.py dist/*.whl
echo "OK: release signing rehearsed end to end with a throwaway key"
