#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Trigger-routing evals: does each skill's description attract its own
prompts and repel others?

For every case file in evals/cases/*.json, rank all skill descriptions by
TF-IDF cosine similarity to the prompt. A positive prompt must rank its
owning skill in the top-K; a negative prompt must NOT rank it #1.
Deterministic, zero-dependency.

This is a cheap router *proxy* — not the model's judgment, but it catches a
description that has stopped attracting its own obvious prompts (the early
symptom of drift). Idea adopted from addyosmani/agent-skills (MIT);
implementation original.
"""

from __future__ import annotations

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
STOP = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "when", "this", "that", "is", "are", "be", "it", "its", "as", "at", "by", "from", "into", "you", "your", "load", "use", "uses", "using", "skill", "covers", "see", "also", "not", "need", "needs", "which", "what", "how", "do", "does", "my"
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


def toks(s: str) -> list[str]:
    return [t for t in TOKEN.findall(s.lower()) if t not in STOP and len(t) > 1]


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


def case_results(cf: Path, router: Router) -> tuple[int, int]:
    """(failures, checks) for one case file, printing each failure."""
    case = load_case(cf)
    if case is None:
        return 1, 0
    skill = case.get("skill")
    if not isinstance(skill, str) or skill not in router.names:
        print(f"✗ {cf.name}: unknown skill {skill!r}")
        return 1, 0
    positive, negative = prompts(case, skill, "positive"), prompts(case, skill, "negative")
    fails = (positive is None) + (negative is None)
    checks = 0
    for p in positive or []:
        checks += 1
        top = router.rank(p)[:TOP_K]
        if skill not in top:
            print(f"✗ [{skill}] positive not in top-{TOP_K}: {p!r} -> {top[:3]}…")
            fails += 1
    for p in negative or []:
        checks += 1
        if router.rank(p)[0] == skill:
            print(f"✗ [{skill}] negative ranked #1: {p!r}")
            fails += 1
    return fails, checks


def main() -> int:
    skills = skill_roots.skill_files(ROOT)
    router = Router([s.parent.name for s in skills], [description_of(s) for s in skills])

    case_files = sorted(CASES_DIR.glob("*.json")) if CASES_DIR.exists() else []
    if not case_files:
        print("no eval cases under evals/cases/ — nothing to check")
        return 0

    fails = 0
    checks = 0
    for cf in case_files:
        failed, checked = case_results(cf, router)
        fails += failed
        checks += checked

    print()
    if fails:
        print(f"FAIL: {fails}/{checks} routing checks failed across {len(case_files)} case file(s)")
        return 1
    print(f"OK: {checks} routing checks passed across {len(case_files)} case file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
