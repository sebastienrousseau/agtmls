#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Check that a built wheel's index and attestations are signed and verify.

    verify-wheel-signatures.py dist/agtmls-<version>-py3-none-any.whl
    verify-wheel-signatures.py <wheel> --signers ALLOWED_SIGNERS

The release runs this on the wheel it built, before anything is published:
the signatures are made in another job and reach the wheel through the
sdist. By default the wheel is judged by the ALLOWED_SIGNERS it ships;
`--signers` names other keys to judge it by.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import signatures, wheel_signatures  # noqa: E402  (scripts path first)


def check(data: bytes, signers: Path | None) -> tuple[int, list[str]]:
    """(attestations found, problems) for one wheel's bytes."""
    with tempfile.TemporaryDirectory(prefix="agtmls-wheel-") as raw:
        registry = wheel_signatures.extract_registry(data, Path(raw))
        count = len(signatures.attestation_files(registry))
        errors = [] if count else ["the wheel carries no attestations"]
        return count, errors + wheel_signatures.problems(registry, signers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--signers", type=Path, help="keys to judge by instead of the wheel's own")
    args = parser.parse_args(argv)
    try:
        count, errors = check(args.wheel.read_bytes(), args.signers)
    except (OSError, zipfile.BadZipFile, signatures.ToolMissing) as exc:
        errors, count = [f"cannot read {args.wheel}: {exc}"], 0
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        return 1
    print(f"OK: index.json and {count} attestation(s) in {args.wheel.name} verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
