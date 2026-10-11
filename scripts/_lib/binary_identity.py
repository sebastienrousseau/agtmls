# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Binary and runtime environment identity verification.

Verifies the cryptographic provenance of the host binary, python runtime,
and execution environment to detect binary tampering or unauthorized
execution wrappers.
"""

from __future__ import annotations

import hashlib
import os
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CHUNK_SIZE = 65536


def hash_file(path: str | Path, chunk_size: int = CHUNK_SIZE) -> str:
    """Compute the SHA-256 digest of a file in streaming chunks.

    Follows symlinks to verify the actual underlying binary executable.
    Raises FileNotFoundError if the path does not exist.
    """
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"File not found: {resolved}")
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def detect_virtual_env() -> str | None:
    """Detect whether a virtual environment is active, returning its root path."""
    env_dir = os.environ.get("VIRTUAL_ENV")
    if env_dir and Path(env_dir).is_dir():
        return str(Path(env_dir).resolve())
    prefix = Path(sys.prefix).resolve()
    base_prefix = Path(getattr(sys, "base_prefix", sys.prefix)).resolve()
    if prefix != base_prefix:
        return str(prefix)
    return None


@dataclass(frozen=True)
class RuntimeIdentity:
    """Cryptographic provenance descriptor for the active runtime."""

    executable_path: str
    executable_sha256: str
    python_version: str
    platform_system: str
    platform_machine: str
    virtual_env: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert runtime identity to a JSON-serializable dictionary."""
        return asdict(self)


def current_runtime_identity() -> RuntimeIdentity:
    """Collect the runtime identity of the current executing Python process."""
    exec_path = str(Path(sys.executable).resolve())
    exec_hash = hash_file(exec_path)
    return RuntimeIdentity(
        executable_path=exec_path,
        executable_sha256=exec_hash,
        python_version=platform.python_version(),
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        virtual_env=detect_virtual_env(),
    )


def verify_binary(
    executable_path: str | Path,
    expected_sha256: str,
) -> tuple[bool, str]:
    """Verify that an executable matches the expected SHA-256 hash.

    Returns (is_valid, message).
    """
    try:
        actual_hash = hash_file(executable_path)
    except (FileNotFoundError, PermissionError, OSError) as err:
        return False, f"Failed to inspect executable: {err}"

    normalized_expected = expected_sha256.strip().lower()
    if actual_hash.lower() == normalized_expected:
        return True, "Executable SHA-256 matches expected digest."
    return False, f"Hash mismatch: expected {normalized_expected}, got {actual_hash}."


def verify_runtime_environment(
    expected: dict[str, Any],
    current: RuntimeIdentity | None = None,
) -> tuple[bool, list[str]]:
    """Verify current environment against expected runtime requirements.

    Keys supported in expected:
      - 'python_version': exact string match (e.g. '3.14.8')
      - 'platform_system': exact match (e.g. 'Darwin', 'Linux')
      - 'platform_machine': exact match (e.g. 'arm64', 'x86_64')
      - 'executable_sha256': exact hash match
    """
    identity = current or current_runtime_identity()
    mismatches: list[str] = []

    checks = (
        ("python_version", identity.python_version),
        ("platform_system", identity.platform_system),
        ("platform_machine", identity.platform_machine),
        ("executable_sha256", identity.executable_sha256),
    )

    for field, actual_val in checks:
        if field in expected:
            exp_val = str(expected[field]).strip().lower()
            if actual_val.strip().lower() != exp_val:
                mismatches.append(f"{field}: expected {exp_val}, got {actual_val.lower()}")

    return (len(mismatches) == 0, mismatches)
