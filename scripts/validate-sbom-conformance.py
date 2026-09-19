#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validate the SBOM against the real SPDX toolchain, and against the wheel.

Two independent failure modes, both of which shipped:

  * the document called itself SPDX 2.3 but omitted `creationInfo`, so no
    validator would accept it; and
  * it described four directories while the wheel ships nine, so it was an
    accurate bill of materials for an artifact nobody distributes.

spdx-tools is an optional dev dependency, matching validate-spec-conformance.
Structural checks always run; the upstream validator runs when available.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPDX = ROOT / "SBOM.spdx.json"
CYCLONEDX = ROOT / "SBOM.cyclonedx.json"


def wheel_paths() -> set[str]:
    """Top-level paths pyproject.toml force-includes into the wheel."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = text.split("[tool.hatch.build.targets.wheel.force-include]", 1)
    if len(block) < 2:
        return set()
    names: set[str] = set()
    for line in block[1].splitlines():
        line = line.strip()
        if line.startswith("["):
            break
        if "=" in line and line.startswith('"'):
            source = line.split("=", 1)[0].strip().strip('"')
            if not source.startswith("."):
                names.add(source.split("/")[0])
    return names


def main() -> int:
    errors: list[str] = []

    if not SPDX.exists():
        print("FAIL: SBOM.spdx.json is missing")
        return 1
    document = json.loads(SPDX.read_text(encoding="utf-8"))

    for field in ("spdxVersion", "SPDXID", "creationInfo", "name", "documentNamespace", "dataLicense"):
        if field not in document:
            errors.append(f"SBOM.spdx.json: missing mandatory field {field!r}")
    creation = document.get("creationInfo", {})
    if not creation.get("created"):
        errors.append("SBOM.spdx.json: creationInfo.created is required")
    if creation.get("created", "").startswith("1970-01-01"):
        errors.append("SBOM.spdx.json: creationInfo.created is the epoch placeholder, not a real date")
    if not creation.get("creators"):
        errors.append("SBOM.spdx.json: creationInfo.creators is required")
    if "example.invalid" in document.get("documentNamespace", ""):
        errors.append("SBOM.spdx.json: documentNamespace is still a placeholder")
    if not document.get("packages"):
        errors.append("SBOM.spdx.json: no packages section, so it describes no artifact")
    if not document.get("relationships"):
        errors.append("SBOM.spdx.json: no relationships, so nothing is DESCRIBES-linked")
    for entry in document.get("files", []):
        if "SPDXID" not in entry:
            errors.append(f"SBOM.spdx.json: file {entry.get('fileName')} has no SPDXID")
            break
        algorithms = {c["algorithm"] for c in entry.get("checksums", [])}
        if "SHA1" not in algorithms:
            errors.append(f"SBOM.spdx.json: file {entry.get('fileName')} lacks the mandatory SHA1 checksum")
            break

    # The SBOM must cover every directory the wheel ships.
    covered = {
        entry["fileName"].lstrip("./").split("/")[0]
        for entry in document.get("files", [])
    }
    missing = sorted(wheel_paths() - covered)
    if missing:
        errors.append(f"SBOM.spdx.json omits shipped wheel paths: {', '.join(missing)}")

    if not CYCLONEDX.exists():
        errors.append("SBOM.cyclonedx.json is missing")
    else:
        cyclone = json.loads(CYCLONEDX.read_text(encoding="utf-8"))
        if cyclone.get("bomFormat") != "CycloneDX" or not cyclone.get("specVersion"):
            errors.append("SBOM.cyclonedx.json is not a CycloneDX document")

    # Upstream validator, when the optional dev dependency is present.
    validator = "skipped (spdx-tools not installed)"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "spdx_tools.spdx.clitools.pyspdxtools", "-i", str(SPDX)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if "No module named" in proc.stdout:
            raise FileNotFoundError
        if proc.returncode != 0 or "must" in proc.stdout:
            errors.append(f"spdx-tools rejected the document:\n{proc.stdout[:2000]}")
        else:
            validator = "spdx-tools: valid"
    except (FileNotFoundError, OSError):
        pass

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} SBOM conformance issue(s)")
        return 1
    print(f"OK: SBOM conformant — {len(document.get('files', []))} files, {len(covered)} shipped paths, {validator}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
