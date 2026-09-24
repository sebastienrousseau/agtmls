# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The advisory feed (agtmls-spec chapter 11): shape, and what it revokes.

Matching is on digest only, never name or version, so a fixed release of
the same skill is not revoked; an advisory with `withdrawn` revokes nothing.
Whether the feed may be consulted at all is the caller's decision, made on
its signature first.
"""

from __future__ import annotations

import re

ADVISORY_ID = re.compile(r"^AGT-ADV-\d{4}-\d{3,}$")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def feed_problems(feed: dict) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for advisory in feed.get("advisories", []):
        name = advisory.get("id", "?")
        if not ADVISORY_ID.match(name):
            problems.append(f"{name}: id is not AGT-ADV-YYYY-NNN")
        if name in seen:
            problems.append(f"{name}: id is not unique")
        seen.add(name)
        for field in ("modified", "published", "withdrawn"):
            if field in advisory and not TIMESTAMP.match(advisory[field]):
                problems.append(f"{name}: {field} is not an RFC 3339 UTC timestamp")
        if "modified" not in advisory:
            problems.append(f"{name}: OSV requires modified")
        affected = advisory.get("affected") or []
        if not affected:
            problems.append(f"{name}: no affected entries")
        for entry in affected:
            if entry.get("package", {}).get("ecosystem") != "AgtMLS":
                problems.append(f"{name}: affected ecosystem is not AgtMLS")
            digests = entry.get("ecosystem_specific", {}).get("digests") or []
            if not digests or not all(DIGEST.match(d) for d in digests):
                problems.append(f"{name}: affected needs one or more sha256: digests")
    return problems


def revoked(feed: dict, lock: dict) -> list[tuple[str, str, list[str]]]:
    """(skill, digest, advisory ids) for every installed digest a live advisory lists."""
    by_digest: dict[str, list[str]] = {}
    for advisory in feed.get("advisories", []):
        if "withdrawn" in advisory:
            continue
        for entry in advisory.get("affected", []):
            for digest in entry.get("ecosystem_specific", {}).get("digests", []):
                by_digest.setdefault(digest, []).append(advisory["id"])
    return [
        (skill["name"], skill["integrity"], sorted(by_digest[skill["integrity"]]))
        for skill in lock.get("skills", [])
        if skill.get("integrity") in by_digest
    ]
