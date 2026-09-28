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


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list:
    return value if isinstance(value, list) else []


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _affected_problems(name: str, affected: list) -> list[str]:
    """Each affected entry names the AgtMLS ecosystem and one or more digests."""
    problems = [] if affected else [f"{name}: no affected entries"]
    for entry in affected:
        entry = _mapping(entry)
        if _mapping(entry.get("package")).get("ecosystem") != "AgtMLS":
            problems.append(f"{name}: affected ecosystem is not AgtMLS")
        digests = _items(_mapping(entry.get("ecosystem_specific")).get("digests"))
        if not digests or not all(DIGEST.match(d) for d in digests if isinstance(d, str)) \
                or not all(isinstance(d, str) for d in digests):
            problems.append(f"{name}: affected needs one or more sha256: digests")
    return problems


def _advisory_problems(advisory: dict, seen: set[str]) -> list[str]:
    """One advisory's id, timestamps and affected entries; records its id in `seen`."""
    problems = []
    name = _string(advisory.get("id")) or "?"
    if not ADVISORY_ID.match(name):
        problems.append(f"{name}: id is not AGT-ADV-YYYY-NNN")
    if name in seen:
        problems.append(f"{name}: id is not unique")
    seen.add(name)
    for field in ("modified", "published", "withdrawn"):
        if field in advisory and not TIMESTAMP.match(_string(advisory[field]) or ""):
            problems.append(f"{name}: {field} is not an RFC 3339 UTC timestamp")
    if "modified" not in advisory:
        problems.append(f"{name}: OSV requires modified")
    return problems + _affected_problems(name, _items(advisory.get("affected")))


def feed_problems(feed: object) -> list[str]:
    """Every way a feed breaks spec 11.2, whatever JSON shape it has.

    A feed is only read after its signature verifies, but a validator that
    raises on a list where a dict belongs reports nothing about the feed it
    was asked to judge; fuzzing found exactly that.
    """
    if not isinstance(feed, dict):
        return ["feed is not an object"]
    problems: list[str] = []
    seen: set[str] = set()
    advisories = feed.get("advisories", [])
    if not isinstance(advisories, list):
        return ["advisories is not a list"]
    for index, advisory in enumerate(advisories):
        if not isinstance(advisory, dict):
            problems.append(f"advisory {index}: not an object")
            continue
        problems += _advisory_problems(advisory, seen)
    return problems


def _digests(entry: object) -> list[str]:
    """The digest strings an affected entry lists."""
    return [d for d in _items(_mapping(_mapping(entry).get("ecosystem_specific")).get("digests")) if isinstance(d, str)]


def _live_digests(feed: object) -> dict[str, list[str]]:
    """Advisory ids by digest, for every advisory that is not withdrawn."""
    by_digest: dict[str, list[str]] = {}
    for advisory in _items(_mapping(feed).get("advisories")):
        advisory = _mapping(advisory)
        advisory_id = _string(advisory.get("id"))
        if "withdrawn" in advisory or advisory_id is None:
            continue
        for entry in _items(advisory.get("affected")):
            for digest in _digests(entry):
                by_digest.setdefault(digest, []).append(advisory_id)
    return by_digest


def revoked(feed: object, lock: object) -> list[tuple[str, str, list[str]]]:
    """(skill, digest, advisory ids) for every installed digest a live advisory lists.

    Entries of the wrong shape revoke nothing: matching is on a digest
    string and an advisory id string, and anything else is not a match.
    """
    by_digest = _live_digests(feed)
    installed = [_mapping(skill) for skill in _items(_mapping(lock).get("skills"))]
    # An entry without a name is still reported: dropping it would hide
    # a revocation of something installed.
    return [
        (skill.get("name", "?"), skill["integrity"], sorted(by_digest[skill["integrity"]]))
        for skill in installed
        if isinstance(skill.get("integrity"), str) and skill["integrity"] in by_digest
    ]
