# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Detached OpenSSH signatures (agtmls-spec chapter 9).

Delegates to `ssh-keygen -Y verify`, which the spec names as the reference:
the standard library has no Ed25519, and reimplementing SSHSIG to avoid a
system tool would be the riskiest line in the registry.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PRINCIPAL = "agtmls-release"
INDEX_NAMESPACE = "agtmls-index@v1"
ADVISORY_NAMESPACE = "agtmls-advisory@v1"


def is_verify_time(value: str) -> bool:
    """Whether `value` is a YYYYMMDD verification time. Checked before it
    reaches ssh-keygen, which would otherwise read it as an option."""
    return len(value) == 8 and value.isascii() and value.isdigit()


class ToolMissing(RuntimeError):
    """ssh-keygen is not installed, so nothing can be concluded."""


def verify(data: Path, signature: Path, allowed_signers: Path, namespace: str,
           principal: str = PRINCIPAL, verify_time: str | None = None) -> str:
    """"verified", "bad_signature" or "unsigned" (spec 9.5).

    No signature file, or no allowed_signers to judge it by, is unsigned:
    there is nothing to verify, which is not the same as a signature that
    fails. A missing ssh-keygen is an error, never a verdict.
    """
    if verify_time is not None and not is_verify_time(verify_time):
        raise ValueError(f"verify time {verify_time!r} is not YYYYMMDD")
    if not signature.exists() or not allowed_signers.exists():
        return "unsigned"
    if shutil.which("ssh-keygen") is None:
        raise ToolMissing("ssh-keygen is not installed; signatures cannot be verified")
    argv = ["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers), "-I", principal,
            "-n", namespace, "-s", str(signature)]
    if verify_time is not None:
        argv.append(f"-Overify-time={verify_time}")
    with data.open("rb") as handle:
        proc = subprocess.run(argv, stdin=handle, capture_output=True, check=False)
    return "verified" if proc.returncode == 0 else "bad_signature"
