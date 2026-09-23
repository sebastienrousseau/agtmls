#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate an in-toto Statement carrying SLSA provenance for the registry.

The previous document set `generated_at` to `1970-01-01T00:00:00Z` -- a
hardcoded epoch, so that the `--check` determinism gate would pass. The intent
(reproducibility) was right; the method made the field false. Its successor
took the date and hash of the last commit touching authored content, which a
squash merge replaced without any content changing, so main's copy was always
stale. The timestamp is now when the materials last changed, kept in the
statement itself (see `_lib/stamp.py`), and the source is pinned by the SBOM's
digest -- which hashes every described file -- rather than by a commit.

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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _lib import stamp  # noqa: E402  (ROOT must be on the path first)

OUT = ROOT / "provenance.json"
MATERIALS = [
    "index.json",
    "checks.json",
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


def sbom_digest() -> str:
    """SHA-256 of the SPDX SBOM, which lists every described file by hash."""
    return hashlib.sha256((ROOT / "SBOM.spdx.json").read_bytes()).hexdigest()


def built_on(statement: dict) -> object:
    """Where the statement keeps its stamp."""
    return statement["predicate"]["runDetails"]["metadata"]["startedOn"]


def render(built: str) -> dict:
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
                # Pinned by content, not by commit: a squash merge gives the
                # same tree a new commit, and the branch commit named here
                # would then exist nowhere on main.
                "resolvedDependencies": [{
                    "name": "SBOM.spdx.json",
                    "uri": f"git+{REPO}",
                    "digest": {"sha256": sbom_digest()},
                }],
            },
            "runDetails": {
                # Unsigned and locally produced. The signed, verifiable
                # provenance for a release is emitted by release.yml via
                # actions/attest-build-provenance; this statement describes
                # registry state, and must not be mistaken for that.
                "builder": {"id": f"{REPO}/.github/workflows/validate.yml"},
                "metadata": {
                    "invocationId": "local",
                    "startedOn": built,
                    "finishedOn": built,
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
    if args.write:
        OUT.write_text(stamp.settle(OUT, render, built_on), encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0
    if args.check:
        if not stamp.current(OUT, render, built_on):
            print("FAIL: provenance.json is stale; run generate-provenance.py --write")
            return 1
        print("OK: provenance is current")
        return 0
    print(stamp.settle(OUT, render, built_on), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
