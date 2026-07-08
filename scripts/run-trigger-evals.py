#!/usr/bin/env python3
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
SKILLS_DIR = ROOT / "skills"
CASES_DIR = ROOT / "evals" / "cases"
STOP = set(
    """a an the and or of to in on for with when this that is are be it its as at by from into
    you your load use uses using skill covers see also not need needs which what how do does my""".split()
)
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


def main() -> int:
    skills = sorted(SKILLS_DIR.glob("**/SKILL.md"))
    names = [s.parent.name for s in skills]
    docs = [Counter(toks(description_of(s))) for s in skills]
    n = len(docs)
    df: Counter = Counter()
    for d in docs:
        df.update(d.keys())

    def idf(t: str) -> float:
        return math.log((n + 1) / (df[t] + 1)) + 1.0

    def vectorize(counter: Counter) -> dict[str, float]:
        total = sum(counter.values()) or 1
        return {t: (c / total) * idf(t) for t, c in counter.items()}

    skill_vecs = [vectorize(d) for d in docs]

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        common = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in common)
        na = math.sqrt(sum(x * x for x in a.values()))
        nb = math.sqrt(sum(x * x for x in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    def rank(prompt: str) -> list[str]:
        pv = vectorize(Counter(toks(prompt)))
        sims = sorted(((cosine(pv, skill_vecs[i]), names[i]) for i in range(n)), reverse=True)
        return [nm for _, nm in sims]

    case_files = sorted(CASES_DIR.glob("*.json")) if CASES_DIR.exists() else []
    if not case_files:
        print("no eval cases under evals/cases/ — nothing to check")
        return 0

    fails = 0
    checks = 0
    for cf in case_files:
        case = json.loads(cf.read_text(encoding="utf-8"))
        skill = case["skill"]
        if skill not in names:
            print(f"✗ {cf.name}: unknown skill {skill!r}")
            fails += 1
            continue
        for p in case.get("positive", []):
            checks += 1
            top = rank(p)[:TOP_K]
            if skill not in top:
                print(f"✗ [{skill}] positive not in top-{TOP_K}: {p!r} -> {top[:3]}…")
                fails += 1
        for p in case.get("negative", []):
            checks += 1
            if rank(p)[0] == skill:
                print(f"✗ [{skill}] negative ranked #1: {p!r}")
                fails += 1

    print()
    if fails:
        print(f"FAIL: {fails}/{checks} routing checks failed across {len(case_files)} case file(s)")
        return 1
    print(f"OK: {checks} routing checks passed across {len(case_files)} case file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
