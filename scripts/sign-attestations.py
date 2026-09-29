#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Sign every attestation, or verify that each one is signed (spec 10.7).

    sign-attestations.py --key <private key>      # the release, in CI
    sign-attestations.py --verify [--root DIR]    # anyone, offline

An attestation is signed as the index is, in a sibling `.sig`, under the
namespace `agtmls-attestation@v1`, by a key ALLOWED_SIGNERS lists for it.
The release workflow signs with the key only its protected environment
holds, then verifies what it signed before anything ships. `--verify` checks
a tree against that tree's own ALLOWED_SIGNERS: this checkout, or the
registry inside an installed wheel.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import signatures  # noqa: E402  (scripts path first)

NAMESPACE = signatures.ATTESTATION_NAMESPACE


def sign(root: Path, key: Path, files: list[Path]) -> list[str]:
    """Sign each file; the reason for the first that fails, or []."""
    for path in files:
        signatures.attestation_signature(path).unlink(missing_ok=True)  # ssh-keygen will not overwrite one
        proc = subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(path)],
                              capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            return [f"could not sign {path.relative_to(root).as_posix()}: {proc.stderr.strip()}"]
    return []


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--key", type=Path, help="sign with this private key, then verify")
    mode.add_argument("--verify", action="store_true", help="verify only")
    parser.add_argument("--root", type=Path, default=ROOT, help="the tree holding attestations/ and ALLOWED_SIGNERS")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    files = signatures.attestation_files(args.root)
    if not files:
        print("FAIL: no attestations under attestations/")
        return 1
    if shutil.which("ssh-keygen") is None:
        print("FAIL: ssh-keygen is not installed; signatures cannot be verified")
        return 1
    problems = sign(args.root, args.key, files) if args.key else []
    problems = problems or signatures.unverified_attestations(args.root)
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        return 1
    if args.key:
        print(f"OK: signed and verified {len(files)} attestation(s)")
    else:
        print(f"OK: {len(files)} attestation(s) verify against ALLOWED_SIGNERS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
