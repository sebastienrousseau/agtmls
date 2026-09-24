# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Per-skill in-toto attestations (agtmls-spec chapter 10).

An attestation is a pure function of the skill and the rule data, rendered
canonically, so re-running is byte-identical and the spec's vectors can be
reproduced exactly. The subject is the skill digest; the manifest predicate
is the digest's own file list, so a verifier can recompute it and name the
file that differs.
"""

from __future__ import annotations

import json
from pathlib import Path

from .analyzer import frontmatter_tools
from .digest import digest_from_manifest, manifest
from .rules import TOOL_CAPABILITIES

STATEMENT = "https://in-toto.io/Statement/v1"
MANIFEST = "https://agtmls.dev/manifest/v1"
CAPABILITIES = "https://agtmls.dev/capabilities/v1"


def render(statement: dict) -> str:
    """Spec 10.2: sorted keys, two-space indent, UTF-8 unescaped, one newline."""
    return json.dumps(statement, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _subject(name: str, digest: str) -> list[dict]:
    return [{"name": name, "digest": {"sha256": digest.removeprefix("sha256:")}}]


def manifest_statement(name: str, skill_dir: Path) -> dict:
    entries = manifest(skill_dir)
    return {
        "_type": STATEMENT,
        "subject": _subject(name, digest_from_manifest(entries)),
        "predicateType": MANIFEST,
        "predicate": {
            "digest_algorithm": "agtmls-skill-digest-v1",
            "files": [{"path": path, "digest": {"sha256": sha}} for path, sha in entries],
        },
    }


def capabilities_statement(name: str, skill_dir: Path, digest: str | None = None) -> dict:
    """Declared policy, granted tools, and escalations: the AGT-CAP-001 judgement."""
    metadata = skill_dir / "metadata.json"
    policy = json.loads(metadata.read_text(encoding="utf-8")).get("safety_policy", {}) if metadata.exists() else {}
    tools = frontmatter_tools(skill_dir / "SKILL.md")
    escalations = []
    for tool in tools:
        capability = TOOL_CAPABILITIES.get(tool.split("(", 1)[0])
        if capability is None:
            continue
        if capability == "network_access":
            granted = policy.get(capability) in {"optional", "required"}
        else:
            granted = bool(policy.get(capability))
        if not granted:
            escalations.append({"tool": tool, "capability": capability})
    return {
        "_type": STATEMENT,
        "subject": _subject(name, digest if digest is not None else digest_from_manifest(manifest(skill_dir))),
        "predicateType": CAPABILITIES,
        "predicate": {"declared_policy": policy, "allowed_tools": tools, "escalations": escalations},
    }
