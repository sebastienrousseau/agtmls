#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate an SPDX 2.3 SBOM, and a CycloneDX 1.6 equivalent, for the registry.

The previous document called itself SPDX 2.3 while omitting `creationInfo`,
which is mandatory, along with `packages`, `relationships` and per-file
`SPDXID`; its `documentNamespace` was `https://example.invalid/...`. It failed
every SPDX validator. It also covered four directories while the wheel ships
nine, so `agents/`, `evals/`, `references/`, `templates/` and `src/` had no
coverage at all -- an SBOM that did not describe the artifact it accompanied.

Determinism: `created` is when the described content last changed, kept in
the SBOM itself (see `_lib/stamp.py`). It moves exactly when the content
moves -- unlike the hardcoded epoch before it, which was deterministic by
being false, and unlike the commit date after that, which a squash merge
moved without any content moving at all.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _lib import stamp  # noqa: E402  (ROOT must be on the path first)
from _lib.covered import (
    SBOM_FILES as COVERED_FILES,
)
from _lib.covered import (
    SOURCE_DIRS as COVERED_DIRS,
)

OUT_SPDX = ROOT / "SBOM.spdx.json"
OUT_CYCLONEDX = ROOT / "SBOM.cyclonedx.json"

SKIP_NAMES = {".DS_Store"}
SKIP_PARTS = {"__pycache__"}
NAMESPACE_BASE = "https://github.com/sebastienrousseau/agtmls/spdx"
# Stable per-document UUID seed: the namespace must be unique per document but
# must not change unless the document does.
NAMESPACE_UUID = uuid.UUID("6f1d1f3a-2a6d-5e55-9b7a-0c3a4f2b1d88")


def checksums(path: Path) -> dict[str, str]:
    """SHA-256 for integrity, SHA-1 because SPDX 2.3 requires it.

    A FileChecksum must include SHA1 or the document fails validation. SHA-1
    is present for schema conformance only; nothing in AgtMLS trusts it.
    """
    sha256 = hashlib.sha256()
    sha1 = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            sha256.update(chunk)
            sha1.update(chunk)
    return {"SHA256": sha256.hexdigest(), "SHA1": sha1.hexdigest()}


def included(path: Path) -> bool:
    return (
        path.is_file()
        and not path.is_symlink()
        and path.name not in SKIP_NAMES
        and not (SKIP_PARTS & set(path.parts))
    )


def covered_paths() -> list[Path]:
    paths: list[Path] = []
    for name in COVERED_DIRS:
        base = ROOT / name
        if base.exists():
            paths.extend(p for p in base.rglob("*") if included(p))
    for name in COVERED_FILES:
        candidate = ROOT / name
        if candidate.exists():
            paths.append(candidate)
    return sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix())


def version() -> str:
    plugin = ROOT / ".claude-plugin" / "plugin.json"
    return json.loads(plugin.read_text(encoding="utf-8"))["version"]


def spdx_id(relative: str) -> str:
    # SPDXID allows only letters, digits, '.' and '-'.
    safe = "".join(ch if ch.isalnum() or ch in ".-" else "-" for ch in relative)
    return f"SPDXRef-File-{safe}"


def render_spdx(paths: list[Path], created: str) -> dict:
    release = version()
    files = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        files.append({
            "SPDXID": spdx_id(relative),
            "fileName": f"./{relative}",
            "checksums": [
                {"algorithm": algorithm, "checksumValue": value}
                for algorithm, value in sorted(checksums(path).items())
            ],
            "licenseConcluded": "Apache-2.0 OR MIT",
            "copyrightText": "Copyright 2026 Sebastien Rousseau",
        })
    package_id = "SPDXRef-Package-agtmls"
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"agtmls-{release}",
        "documentNamespace": f"{NAMESPACE_BASE}/{release}/{NAMESPACE_UUID}",
        "creationInfo": {
            "created": created,
            "creators": [
                "Tool: agtmls-generate-sbom",
                "Person: Sebastien Rousseau",
                "Organization: AgtMLS",
            ],
            "licenseListVersion": "3.24",
        },
        "packages": [{
            "SPDXID": package_id,
            "name": "agtmls",
            "versionInfo": release,
            "downloadLocation": "https://pypi.org/project/agtmls/",
            "filesAnalyzed": True,
            "licenseConcluded": "Apache-2.0 OR MIT",
            "licenseDeclared": "Apache-2.0 OR MIT",
            "copyrightText": "Copyright 2026 Sebastien Rousseau",
            "supplier": "Person: Sebastien Rousseau",
            "externalRefs": [{
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:pypi/agtmls@{release}",
            }],
            "hasFiles": [f["SPDXID"] for f in files],
        }],
        "files": files,
        "relationships": [
            {"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES",
             "relatedSpdxElement": package_id},
        ],
    }


def render_cyclonedx(paths: list[Path], created: str) -> dict:
    """CycloneDX 1.6 is what most enterprise scanners ingest."""
    release = version()
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{NAMESPACE_UUID}",
        "version": 1,
        "metadata": {
            "timestamp": created,
            "tools": {"components": [
                {"type": "application", "name": "agtmls-generate-sbom", "version": release}
            ]},
            "authors": [{"name": "Sebastien Rousseau"}],
            "component": {
                "type": "application",
                "bom-ref": f"pkg:pypi/agtmls@{release}",
                "name": "agtmls",
                "version": release,
                "purl": f"pkg:pypi/agtmls@{release}",
                "licenses": [{"expression": "Apache-2.0 OR MIT"}],
            },
        },
        # CycloneDX has no top-level `files`: the schema sets
        # additionalProperties false, so the previous shape was rejected by
        # every 1.6 validator. Files are components of type "file", which is
        # how the spec models them. The package still has no runtime
        # dependencies -- that is stated by the absence of any component of
        # type "library", not by an empty list.
        "components": [
            {
                "type": "file",
                "bom-ref": p.relative_to(ROOT).as_posix(),
                "name": p.relative_to(ROOT).as_posix(),
                "hashes": [{"alg": "SHA-256", "content": checksums(p)["SHA256"]}],
            }
            for p in paths
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--format", choices=["spdx", "cyclonedx"], default="spdx")
    args = parser.parse_args()

    paths = covered_paths()
    targets = [
        (OUT_SPDX, lambda created: render_spdx(paths, created),
         lambda doc: doc["creationInfo"]["created"]),
        (OUT_CYCLONEDX, lambda created: render_cyclonedx(paths, created),
         lambda doc: doc["metadata"]["timestamp"]),
    ]

    if args.write:
        for out, render, locate in targets:
            out.write_text(stamp.settle(out, render, locate), encoding="utf-8")
            print(f"wrote {out.relative_to(ROOT)} ({len(paths)} files)")
        return 0
    if args.check:
        stale = [out.name for out, render, locate in targets if not stamp.current(out, render, locate)]
        if stale:
            print(f"FAIL: {', '.join(stale)} stale; run generate-sbom.py --write")
            return 1
        print(f"OK: SBOM is current ({len(paths)} files, SPDX 2.3 + CycloneDX 1.6)")
        return 0
    out, render, locate = targets[0] if args.format == "spdx" else targets[1]
    print(stamp.settle(out, render, locate), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
