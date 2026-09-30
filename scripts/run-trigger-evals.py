#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Trigger-routing evals: does each skill's description attract its own
prompts and repel others?

For every case file in evals/cases/*.json, rank all skill descriptions by
TF-IDF cosine similarity to the prompt. A positive prompt must rank its
skill in the top-K. A negative prompt names the skill that should win it
(`owner`), and the owner must rank above the case's skill. The share of
prompts whose intended skill ranks first is held to evals/routing-floor.json,
which only rises (`--update` records a better share). Deterministic,
zero-dependency.

This is a cheap router *proxy* — not the model's judgment, but it catches a
description that has stopped attracting its own obvious prompts (the early
symptom of drift). Idea adopted from addyosmani/agent-skills (MIT);
implementation original.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

TOP_K = 5  # lenient: TF-IDF on a short prompt is noisy; #1 for negatives is the sharp test

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import skill_roots  # noqa: E402  (scripts path first)

SKILLS_DIR = ROOT / "skills"
CASES_DIR = ROOT / "evals" / "cases"
FLOOR = ROOT / "evals" / "routing-floor.json"
FLOOR_SHAPE = 'evals/routing-floor.json must be {"rank1": <share from 0 to 1>}'
STOP = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "when", "this", "that", "is", "am", "are", "be", "it", "its", "as", "at", "by", "from", "into", "you", "your", "load", "use", "uses", "using", "skill", "covers", "see", "also", "not", "need", "needs", "which", "what", "how", "do", "does", "my"
}
TOKEN = re.compile(r"[a-z0-9_]+")


def description_of(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    block = m.group(1) if m else ""
    dm = re.search(r"^description:[ \t]*(.*)$", block, re.MULTILINE)
    if not dm:
        return ""
    lines = block[dm.start():].split("\n")
    out = [re.sub(r"^description:[ \t]*[|>+-]*[ \t]*", "", lines[0])]
    for line in lines[1:]:
        if re.match(r"^[A-Za-z0-9_-]+:", line):
            break
        out.append(line.strip())
    return " ".join(out)


SUFFIXES = ("ing", "ed", "es", "s")


def stem(word: str) -> str:
    """A light stemmer, so word forms meet: crash and crashes, write and
    writing. A model reads them as one word, and a proxy that did not let a
    debugging skill naming "crashes" lose "why does this crash"."""
    for suffix in SUFFIXES:
        if word.endswith(suffix) and not word.endswith("ss") and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 3 else word


def toks(s: str) -> list[str]:
    return [stem(t) for t in TOKEN.findall(s.lower()) if t not in STOP and len(t) > 1]


class Router:
    """TF-IDF over the skill descriptions: rank skills by a prompt."""

    def __init__(self, names: list[str], descriptions: list[str]) -> None:
        self.names = names
        docs = [Counter(toks(d)) for d in descriptions]
        self.n = len(docs)
        self.df: Counter = Counter()
        for d in docs:
            self.df.update(d.keys())
        self.skill_vecs = [self.vectorize(d) for d in docs]

    def idf(self, t: str) -> float:
        return math.log((self.n + 1) / (self.df[t] + 1)) + 1.0

    def vectorize(self, counter: Counter) -> dict[str, float]:
        total = sum(counter.values()) or 1
        return {t: (c / total) * self.idf(t) for t, c in counter.items()}

    @staticmethod
    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        common = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in common)
        na = math.sqrt(sum(x * x for x in a.values()))
        nb = math.sqrt(sum(x * x for x in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    def rank(self, prompt: str) -> list[str]:
        pv = self.vectorize(Counter(toks(prompt)))
        sims = sorted(((self.cosine(pv, self.skill_vecs[i]), self.names[i]) for i in range(self.n)), reverse=True)
        return [nm for _, nm in sims]


def load_case(cf: Path) -> dict | None:
    """The case, or None after printing why it cannot be read as an object."""
    try:
        case = json.loads(cf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"✗ {cf.name}: invalid JSON: {exc}")
        return None
    if not isinstance(case, dict):
        print(f"✗ {cf.name}: not a JSON object")
        return None
    return case


def prompts(case: dict, skill: str, kind: str) -> list[str] | None:
    """The case's positive or negative prompts, or None after printing that
    they are not a list of strings (a string would run letter by letter)."""
    value = case.get(kind, [])
    if isinstance(value, list) and all(isinstance(p, str) for p in value):
        return value
    print(f"✗ [{skill}] {kind} must be a list of prompts")
    return None


def negatives(case: dict, skill: str) -> list[dict] | None:
    """The case's negative {prompt, owner} pairs, or None after printing that
    they are not."""
    value = case.get("negative", [])
    if isinstance(value, list) and all(
        isinstance(n, dict) and isinstance(n.get("prompt"), str) and isinstance(n.get("owner"), str) for n in value
    ):
        return value
    print(f"✗ [{skill}] negative must be a list of {{prompt, owner}}")
    return None


class Tally:
    """Failures, checks and rank-1 hits across every case."""

    def __init__(self) -> None:
        self.fails = self.checks = self.rank1 = 0

    def record(self, ok: bool, first: bool, message: str) -> None:
        self.checks += 1
        self.rank1 += first
        if not ok:
            print(message)
            self.fails += 1


def check_positives(skill: str, positive: list[str], router: Router, tally: Tally) -> None:
    for p in positive:
        ranked = router.rank(p)
        tally.record(skill in ranked[:TOP_K], ranked[0] == skill,
                     f"✗ [{skill}] positive not in top-{TOP_K}: {p!r} -> {ranked[:3]}…")


def check_negatives(skill: str, negative: list[dict], router: Router, tally: Tally) -> None:
    for n in negative:
        prompt, owner = n["prompt"], n["owner"]
        if owner not in router.names:
            tally.record(False, False, f"✗ [{skill}] negative's owner {owner!r} is not a skill")
            continue
        ranked = router.rank(prompt)
        tally.record(ranked.index(owner) < ranked.index(skill), ranked[0] == owner,
                     f"✗ [{skill}] negative's owner {owner} ranks below {skill}: {prompt!r} -> {ranked[:3]}…")


def case_results(cf: Path, router: Router, tally: Tally) -> None:
    """Check one case file into `tally`, printing each failure."""
    case = load_case(cf)
    if case is None:
        tally.fails += 1
        return
    skill = case.get("skill")
    if not isinstance(skill, str) or skill not in router.names:
        print(f"✗ {cf.name}: unknown skill {skill!r}")
        tally.fails += 1
        return
    positive, negative = prompts(case, skill, "positive"), negatives(case, skill)
    tally.fails += (positive is None) + (negative is None)
    check_positives(skill, positive or [], router, tally)
    check_negatives(skill, negative or [], router, tally)


def read_floor() -> float | None:
    """The committed rank-1 floor, or None after printing that it is unusable."""
    try:
        floor = json.loads(FLOOR.read_text(encoding="utf-8"))["rank1"]
    except (OSError, ValueError, KeyError, TypeError):
        floor = None
    if isinstance(floor, (int, float)) and not isinstance(floor, bool) and 0 <= floor <= 1:
        return float(floor)
    print(f"FAIL: {FLOOR_SHAPE}")
    return None


def floor_problems(tally: Tally, floor: float, update: bool) -> int:
    """Compare the rank-1 share with the floor; with `update`, raise the floor."""
    share = round(tally.rank1 / tally.checks, 3) if tally.checks else 0.0
    print(f"rank-1: {tally.rank1}/{tally.checks} ({share:.1%}), floor {floor:.1%}")
    if share < floor:
        print(f"FAIL: rank-1 share {share:.1%} is below the floor of {floor:.1%}")
        return 1
    if share > floor and update:
        FLOOR.write_text(json.dumps({"rank1": share}) + "\n", encoding="utf-8")
        print(f"recorded the rank-1 floor at {share:.1%}")
    elif share > floor:
        print(f"note: the floor could rise to {share:.1%} (run with --update)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update", action="store_true", help="raise the rank-1 floor to the current share")
    update = parser.parse_args().update
    skills = skill_roots.skill_files(ROOT)
    router = Router([s.parent.name for s in skills], [description_of(s) for s in skills])

    case_files = sorted(CASES_DIR.glob("*.json")) if CASES_DIR.exists() else []
    if not case_files:
        print("no eval cases under evals/cases/ — nothing to check")
        return 0

    tally = Tally()
    for cf in case_files:
        case_results(cf, router, tally)
    floor = read_floor()

    print()
    if tally.fails:
        print(f"FAIL: {tally.fails}/{tally.checks} routing checks failed across {len(case_files)} case file(s)")
        return 1
    if floor is None or floor_problems(tally, floor, update):
        return 1
    print(f"OK: {tally.checks} routing checks passed across {len(case_files)} case file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
