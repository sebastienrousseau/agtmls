#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate the registry's capability card.

This was described as "A2A-style" and was not an A2A AgentCard: it put the
skill list under `capabilities`, where the A2A schema defines an object of
protocol feature flags, and omitted `protocolVersion`, `url`,
`defaultInputModes`, `defaultOutputModes` and `provider`. Every A2A validator
rejected it.

It is not made into one, because A2A's `url` is a live service endpoint and
AgtMLS has none: the registry is installed, and its server surface is
agtmls-mcp over stdio. Emitting an A2A card would mean inventing a URL, which
is the guessed-registry-URL claim AGENTS.md section 7.1 forbids, and a
document that lies about where it can be reached is worse than one that does
not claim the standard.

So the card declares what it is. `kind` names the schema, `skills` holds the
skills, and `interfaces` says how the registry is actually reached. If a
hosted A2A endpoint ever exists, `a2a_endpoint` in providers.json turns this
into a real AgentCard and the shape below becomes the fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "agent-card.json"
KIND = "agtmls-registry-card"
SCHEMA_VERSION = 1
#: A2A protocol version to declare if and when an endpoint is configured.
A2A_PROTOCOL_VERSION = "0.3.0"


def registry() -> tuple[dict, dict]:
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    providers = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
    return index, providers


def skills_of(index: dict) -> list[dict]:
    return [
        {
            "id": skill["name"],
            "name": skill["name"],
            "description": skill["description"],
            "tags": skill.get("tags", []),
            "risk": skill.get("safety_policy", {}).get("risk_level"),
            "quality": skill.get("quality", {}).get("score"),
        }
        for skill in index["skills"]
    ]


def render() -> dict:
    index, providers = registry()
    endpoint = providers.get("a2a_endpoint")
    skills = skills_of(index)

    if endpoint:
        # A real AgentCard, only once there is a real endpoint to name.
        return {
            "protocolVersion": A2A_PROTOCOL_VERSION,
            "name": "agtmls",
            "description": index["description"],
            "url": endpoint,
            "preferredTransport": "JSONRPC",
            "version": index["registry_version"],
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": False,
            },
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/markdown"],
            "provider": {
                "organization": "Sebastien Rousseau",
                "url": "https://github.com/sebastienrousseau/agtmls",
            },
            "skills": skills,
        }

    return {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "name": "agtmls",
        "description": index["description"],
        "version": index["registry_version"],
        # Deliberately not "capabilities": that name belongs to A2A's feature
        # flags, and using it for a skill list is what made this document
        # unreadable to every A2A consumer that tried.
        "skills": skills,
        "interfaces": ["skills", "provider-adapted-markdown", "mcp-resources"],
        "providers": sorted(providers.get("export_targets", {})),
        "not_a2a": (
            "A2A requires `url`, a live service endpoint. AgtMLS is installed "
            "rather than called, and its server surface is agtmls-mcp over "
            "stdio. Set `a2a_endpoint` in providers.json to publish a real "
            "AgentCard instead of this."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="write agent-card.json")
    parser.add_argument("--check", action="store_true", help="fail if agent-card.json is stale")
    args = parser.parse_args()

    text = json.dumps(render(), indent=2, sort_keys=True) + "\n"
    if args.write:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("FAIL: agent-card.json is stale; run generate-agent-card.py --write")
            return 1
        print("OK: agent card is current")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
