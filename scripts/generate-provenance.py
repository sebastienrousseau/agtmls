#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate an in-toto Statement carrying SLSA provenance for the registry.

The previous document set `generated_at` to `1970-01-01T00:00:00Z` -- a
hardcoded epoch, so that the `--check` determinism gate would pass. The intent
(reproducibility) was right; the method made the field false. A timestamp
derived from the commit that last touched a material is deterministic *and*
true, which is the property actually wanted.

It also claimed `predicateType: https://slsa.dev/provenance/v1` without an
in-toto Statement envelope, and named `scripts/agtmls.py check` as the
builder. Neither is what a SLSA verifier expects. The authoritative provenance
for a release is what actions/attest-build-provenance signs in release.yml;
this file is the in-repo, unsigned statement of registry state, and now says
so rather than implying more.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _lib.covered import SOURCE_DIRS, SOURCE_FILES  # noqa: E402
OUT = ROOT / "provenance.json"
MATERIALS = [
    "index.json",
    "checks.json",
    "agent-card.json",
    "mcp-resources.json",
    "SBOM.spdx.json",
    "SBOM.cyclonedx.json",
]
REPO = "https://github.com/sebastienrousseau/agtmls"


def material_digest() -> str:
    """One digest over every material, path-bound so a rename is visible."""
    digest = hashlib.sha256()
    for name in MATERIALS:
        path = ROOT / name
        if not path.exists():
            raise SystemExit(f"provenance material is missing: {name}")
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def built_at() -> str:
    """Commit date of the last commit touching AUTHORED content.

    Not the materials: those include SBOM.spdx.json, which is regenerated
    alongside this file. Deriving the date from a generated artifact meant
    committing the regenerated SBOM moved this timestamp, so the pair never
    settled. Authored paths are not written by any generator, so one
    regeneration converges.
    """
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    proc = subprocess.run(
        ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%dT%H:%M:%SZ",
         "--", *SOURCE_DIRS, *SOURCE_FILES],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return proc.stdout.strip() or "1970-01-01T00:00:00Z"


def source_ref() -> str:
    """The commit that last changed authored content.

    Not HEAD. A file that records the current commit hash can never be
    committed and remain current: committing it changes HEAD, so the next
    --check regenerates a different value, forever. Naming the commit that
    last changed the described content is both stable and more accurate --
    this document describes registry state, not the commit that happened to
    write it.
    """
    proc = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", *SOURCE_DIRS, *SOURCE_FILES],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return proc.stdout.strip() or "unknown"


def render() -> dict:
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    version = index["registry_version"]
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{
            "name": f"agtmls-{version}",
            "digest": {"sha256": material_digest()},
        }],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": f"{REPO}/registry-state/v1",
                "externalParameters": {
                    "repository": REPO,
                    "registryVersion": version,
                },
                "resolvedDependencies": [
                    {"uri": f"git+{REPO}", "digest": {"gitCommit": source_ref()}}
                ],
            },
            "runDetails": {
                # Unsigned and locally produced. The signed, verifiable
                # provenance for a release is emitted by release.yml via
                # actions/attest-build-provenance; this statement describes
                # registry state, and must not be mistaken for that.
                "builder": {"id": f"{REPO}/.github/workflows/validate.yml"},
                "metadata": {
                    "invocationId": "local",
                    "startedOn": built_at(),
                    "finishedOn": built_at(),
                },
            },
        },
        "agtmls": {
            "schema_version": 2,
            "signed": False,
            "materials": MATERIALS,
            "checks": json.loads((ROOT / "checks.json").read_text(encoding="utf-8"))["checks"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(render(), indent=2, sort_keys=True) + "\n"

    if args.write:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("FAIL: provenance.json is stale; run generate-provenance.py --write")
            return 1
        print("OK: provenance is current")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
