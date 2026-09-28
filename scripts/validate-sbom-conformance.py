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
INVALID_BANNER = "The document is invalid"


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


MANDATORY = ("spdxVersion", "SPDXID", "creationInfo", "name", "documentNamespace", "dataLicense")


def creation_problems(creation: object) -> list[str]:
    creation = creation if isinstance(creation, dict) else {}
    created = creation.get("created")
    errors = []
    if not created or not isinstance(created, str):
        errors.append("SBOM.spdx.json: creationInfo.created is required")
    elif created.startswith("1970-01-01"):
        errors.append("SBOM.spdx.json: creationInfo.created is the epoch placeholder, not a real date")
    if not creation.get("creators"):
        errors.append("SBOM.spdx.json: creationInfo.creators is required")
    return errors


def namespace_problems(namespace: object) -> list[str]:
    if not isinstance(namespace, str):
        return ["SBOM.spdx.json: documentNamespace must be a string"]
    if "example.invalid" in namespace:
        return ["SBOM.spdx.json: documentNamespace is still a placeholder"]
    return []


def document_problems(document: dict) -> list[str]:
    """The SPDX fields a validator requires, and placeholders left in them."""
    errors = [f"SBOM.spdx.json: missing mandatory field {field!r}" for field in MANDATORY if field not in document]
    errors += creation_problems(document.get("creationInfo", {}))
    errors += namespace_problems(document.get("documentNamespace", ""))
    if not document.get("packages"):
        errors.append("SBOM.spdx.json: no packages section, so it describes no artifact")
    if not document.get("relationships"):
        errors.append("SBOM.spdx.json: no relationships, so nothing is DESCRIBES-linked")
    return errors


def checksum_algorithms(entry: dict) -> set[str | None] | None:
    """The file's checksum algorithms, or None when the list is malformed."""
    checksums = entry.get("checksums", [])
    # An entry with no algorithm names none (and the file then lacks SHA1);
    # one that is not an object, or names a non-string, is malformed.
    if not isinstance(checksums, list) or not all(
        isinstance(c, dict) and isinstance(c.get("algorithm", ""), str) for c in checksums
    ):
        return None
    return {c.get("algorithm") for c in checksums}


def entry_problem(i: int, entry: object) -> str | None:
    if not isinstance(entry, dict) or not isinstance(entry.get("fileName"), str):
        return f"SBOM.spdx.json: file entry {i} must be an object with a fileName"
    if "SPDXID" not in entry:
        return f"SBOM.spdx.json: file {entry['fileName']} has no SPDXID"
    algorithms = checksum_algorithms(entry)
    if algorithms is None:
        return f"SBOM.spdx.json: file {entry['fileName']} has malformed checksums (each needs a string algorithm)"
    if "SHA1" not in algorithms:
        return f"SBOM.spdx.json: file {entry['fileName']} lacks the mandatory SHA1 checksum"
    return None


def file_problems(files: object) -> list[str]:
    """The first malformed file entry: one complaint, since a systematic
    fault is one fault."""
    if not isinstance(files, list):
        return ["SBOM.spdx.json: files must be a list"]
    for i, entry in enumerate(files):
        problem = entry_problem(i, entry)
        if problem is not None:
            return [problem]
    return []


def cyclonedx_problems() -> list[str]:
    if not CYCLONEDX.exists():
        return ["SBOM.cyclonedx.json is missing"]
    try:
        cyclone = json.loads(CYCLONEDX.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"SBOM.cyclonedx.json is not valid JSON: {exc}"]
    if not isinstance(cyclone, dict) or cyclone.get("bomFormat") != "CycloneDX" or not cyclone.get("specVersion"):
        return ["SBOM.cyclonedx.json is not a CycloneDX document"]
    return []


def upstream_validation() -> tuple[list[str], str]:
    """(spdx-tools' rejection, if any; what it said), when the optional dev
    dependency is present."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "spdx_tools.spdx.clitools.pyspdxtools", "-i", str(SPDX)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if "No module named" in proc.stdout:
            raise FileNotFoundError
        # pyspdxtools 0.8.3 exits 1 on every rejection path. Its own banner is
        # a second, exact signal; matching any output containing "must" was a
        # guess that would fail the gate on an informational line.
        if proc.returncode != 0 or INVALID_BANNER in proc.stdout:
            return [f"spdx-tools rejected the document:\n{proc.stdout[:2000]}"], "skipped (spdx-tools not installed)"
        return [], "spdx-tools: valid"
    except (FileNotFoundError, OSError):
        return [], "skipped (spdx-tools not installed)"


def load_spdx() -> dict | str:
    """The SPDX document, or why it cannot be read as one."""
    try:
        document = json.loads(SPDX.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"SBOM.spdx.json is not valid JSON: {exc}"
    return document if isinstance(document, dict) else "SBOM.spdx.json must be a JSON object"


def main() -> int:
    if not SPDX.exists():
        print("FAIL: SBOM.spdx.json is missing")
        return 1
    document = load_spdx()
    if isinstance(document, str):
        print(f"FAIL: {document}")
        return 1
    files = document.get("files", [])
    errors = document_problems(document) + file_problems(files)

    # The SBOM must cover every directory the wheel ships.
    covered = {
        entry["fileName"].lstrip("./").split("/")[0]
        for entry in (files if isinstance(files, list) else [])
        if isinstance(entry, dict) and isinstance(entry.get("fileName"), str)
    }
    missing = sorted(wheel_paths() - covered)
    if missing:
        errors.append(f"SBOM.spdx.json omits shipped wheel paths: {', '.join(missing)}")

    errors += cyclonedx_problems()
    # Upstream validator, when the optional dev dependency is present.
    rejected, validator = upstream_validation()
    errors += rejected

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} SBOM conformance issue(s)")
        return 1
    print(f"OK: SBOM conformant — {len(files)} files, {len(covered)} shipped paths, {validator}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
