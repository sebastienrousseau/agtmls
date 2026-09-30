# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The signatures a wheel carries: its index and every attestation.

The release signs in one job and builds the wheel in another, from the
sdist, so a signature can be lost on the way. The release checks the built
wheel with this before publishing (verify-wheel-signatures.py), and
release-audit.py reads the published wheel the same way.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from . import signatures

REGISTRY = "agtmls/_registry/"
SIGNED = ("index.json", "index.json.sig", "ALLOWED_SIGNERS")


def extract_registry(data: bytes, into: Path) -> Path:
    """Unpack the index, its signature, the trusted keys and the attestations
    of a wheel into `into`; the registry root."""
    with zipfile.ZipFile(io.BytesIO(data)) as wheel:
        wanted = {REGISTRY + name for name in SIGNED}
        members = [name for name in wheel.namelist()
                   if name in wanted or name.startswith(REGISTRY + "attestations/")]
        wheel.extractall(into, members=members)
    return into / REGISTRY


def problems(registry: Path, signers: Path | None = None) -> list[str]:
    """Each signature under `registry` that is missing or does not verify,
    against `signers` or the registry's own ALLOWED_SIGNERS."""
    signers = registry / "ALLOWED_SIGNERS" if signers is None else signers
    status = signatures.verify(registry / "index.json", registry / "index.json.sig", signers,
                               signatures.INDEX_NAMESPACE)
    errors = [] if status == "verified" else [f"index.json: {status}"]
    return errors + signatures.unverified_attestations(registry, signers)
