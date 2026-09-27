# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What `agtmls verify` concludes and prints (agtmls-spec 6, 9 and 11).

The checks themselves live in scripts/agtmls.py, which gathers the lockfile
problems, the signature statuses, the revocations and the live result; this
decides the exit code from them and reports them as JSON or as text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from _lib import lockfile


def verify_code(statuses: tuple[str, str], integrity: list, hits: list, require_signed: bool) -> int:
    """Exit precedence (11.4): 5, then 3, then 6, then 4."""
    if "bad_signature" in statuses:
        return lockfile.EXIT_BAD_SIGNATURE
    if integrity:
        return lockfile.EXIT_INTEGRITY_FAILURE
    if hits:
        return lockfile.EXIT_REVOKED
    if require_signed and "unsigned" in statuses:
        return lockfile.EXIT_UNSIGNED
    return lockfile.EXIT_OK


def with_live(code: int, live_result: dict | None) -> int:
    """The exit code once the agent has been asked (`verify --live`)."""
    # A skill the agent does not load is never used, but it is not an
    # integrity failure: it keeps every spec exit code and fails as an error.
    if live_result is not None and code == lockfile.EXIT_OK and (live_result.get("error") or live_result["missing"]):
        return lockfile.EXIT_ERROR
    return code


def print_verify_json(target: Path, code: int, problems: list, statuses: tuple[str, str], hits: list,
                      notes: list[str], live_result: dict | None) -> None:
    print(json.dumps(
        {"target": str(target), "ok": code == lockfile.EXIT_OK,
         "problems": [{"skill": n, "status": s, "detail": d} for n, s, d in problems],
         "index_signature": statuses[0], "advisory_feed": statuses[1],
         "revoked": [{"skill": n, "digest": d, "advisories": ids} for n, d, ids in hits],
         "notes": notes, **({"live": live_result} if live_result is not None else {})},
        indent=2, sort_keys=True,
    ))


# (source, status) -> (stream, line). The stream is named, not held: a
# reference to sys.stdout taken at import would miss a later redirection.
SIGNATURE_LINES = {
    ("index", "verified"): ("stdout", "OK: index.json signature verified"),
    ("index", "bad_signature"): ("stderr", "BAD_SIGNATURE index.json.sig does not verify against ALLOWED_SIGNERS"),
    ("index", "unsigned"): ("stderr", "UNSIGNED     index.json has no signature, or there is no ALLOWED_SIGNERS"),
    ("feed", "bad_signature"): ("stderr", "BAD_SIGNATURE advisories.json.sig does not verify; the feed is not consulted"),
}


def print_signatures(statuses: tuple[str, str]) -> None:
    """One line for each signature worth reporting; stdout for a verified
    index, stderr for everything that is wrong."""
    for source, status in zip(("index", "feed"), statuses):
        line = SIGNATURE_LINES.get((source, status))
        if line is not None:
            print(line[1], file=getattr(sys, line[0]))


def print_live(agent: str, live_result: dict | None) -> None:
    if live_result is None:
        return
    if live_result.get("error"):
        print(f"LIVE         {agent} could not be asked which skills it loads: {live_result['error']}", file=sys.stderr)
        return
    for name in live_result["missing"]:
        print(f"{'NOT LOADED':<12} {name}  installed, but {agent} does not list it", file=sys.stderr)
    if not live_result["missing"]:
        print(f"OK: {agent} loads all {live_result['expected']} installed skill(s)")


def print_findings(problems: list, hits: list, notes: list[str]) -> None:
    """Lockfile problems, revocations and notes, one line each, on stderr."""
    for name, status, detail in problems:
        print(f"{status.upper():<12} {name or '-'}  {detail}", file=sys.stderr)
    for name, digest, ids in hits:
        print(f"{'REVOKED':<12} {name}  {digest} by {', '.join(ids)}", file=sys.stderr)
    for note in notes:
        print(f"note: {note}", file=sys.stderr)


def print_verify_text(target: Path, agent: str, code: int, problems: list, statuses: tuple[str, str],
                      hits: list, notes: list[str], live_result: dict | None) -> None:
    print_findings(problems, hits, notes)
    print_signatures(statuses)
    print_live(agent, live_result)
    integrity = [p for p in problems if p[1] != "unmanaged"]
    if code == lockfile.EXIT_OK and not integrity:
        lock = lockfile.read(target) or {}
        print(f"OK: {len(lockfile.entries_for(lock, agent))} skill(s) match the lockfile in {target}")
    elif integrity:
        print(f"\nFAIL: {len(integrity)} integrity problem(s)", file=sys.stderr)
