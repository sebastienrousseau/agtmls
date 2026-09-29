# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Efficacy attestations (agtmls-spec chapter 10, draft `efficacy/v1`).

A skill is hardened only when a run with and without it shows that it helps
on two agents within the token ceiling (evals/uplift/README.md). This turns
that run into an in-toto statement about the skill: its subject is the skill
digest, and its evidence is the committed results file whose recorded digest
for the skill is that same digest. When the skill changes, no results file
matches and no attestation is written, so a measurement never vouches for
bytes it did not measure.

Signing is the release's: the release workflow signs every attestation under
`agtmls-attestation@v1` with the key in ALLOWED_SIGNERS (spec 10.7).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import uplift
from .attestations import STATEMENT, _subject

EFFICACY = "https://agtmls.dev/efficacy/v1"
EVIDENCE = Path("docs/evidence")


def _results(path: Path) -> dict | None:
    """A results file written by run-uplift-evals.py, or None."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    shaped = isinstance(data, dict) and isinstance(data.get("meta"), dict) \
        and isinstance(data.get("summary"), list) and isinstance(data.get("runs"), list)
    return data if shaped else None


def find_evidence(root: Path, name: str, skill_digest: str) -> tuple[str, dict] | None:
    """(path, results) of the newest run that measured `name` at exactly
    `skill_digest`, or None."""
    matches = []
    for path in sorted((root / EVIDENCE).glob("*.json")):
        data = _results(path)
        skills = data["meta"].get("skills") if data else None
        if isinstance(skills, dict) and skills.get(name) == skill_digest:
            matches.append((str(data["meta"].get("date", "")), path.relative_to(root).as_posix(), data))
    if not matches:
        return None
    _, rel, data = max(matches, key=lambda match: (match[0], match[1]))
    return rel, data


def _model(results: dict, agent: str) -> str | None:
    return next((run.get("model") for run in results["runs"]
                 if run.get("agent") == agent and run.get("model")), None)


def _agent(results: dict, row: dict) -> dict:
    with_, without = row["with"], row["without"]
    ratio = with_["tokens"] / without["tokens"] if with_.get("tokens") and without.get("tokens") else None
    return {
        "agent": row["agent"],
        "model": _model(results, row["agent"]),
        "score_without": without["score"],
        "score_with": round(with_["score"], 3) if with_["score"] is not None else None,
        "delta": row["delta"],
        "token_ratio": round(ratio, 2) if ratio is not None else None,
        "verdict": uplift.verdict(row),
    }


def statement(name: str, skill_digest: str, results: dict, evidence_path: str, evidence_sha256: str) -> dict:
    """The efficacy statement for one skill, from one results file."""
    # A results file can hold several skills (the 29 September run held three).
    rows = sorted((row for row in results["summary"] if row.get("skill") == name), key=lambda row: row["agent"])
    agents = [_agent(results, row) for row in rows]
    meta = results["meta"]
    return {
        "_type": STATEMENT,
        "subject": _subject(name, skill_digest),
        "predicateType": EFFICACY,
        "predicate": {
            "bar": {"agents": uplift.HARDENED_AGENTS, "token_ceiling": uplift.TOKEN_CEILING,
                    "big_gain": uplift.BIG_GAIN},
            "evidence": {"path": evidence_path, "digest": {"sha256": evidence_sha256},
                         "commit": meta.get("commit"), "date": meta.get("date"), "trials": meta.get("trials")},
            "agents": agents,
            "meets_bar": sum(agent["verdict"] == "helps" for agent in agents) >= uplift.HARDENED_AGENTS,
        },
    }


def efficacy_statement(root: Path, name: str, skill_digest: str) -> dict | None:
    """The statement for `name` at `skill_digest`, if a run measured it."""
    found = find_evidence(root, name, skill_digest)
    if found is None:
        return None
    rel, results = found
    sha = hashlib.sha256((root / rel).read_bytes()).hexdigest()
    return statement(name, skill_digest, results, rel, sha)
