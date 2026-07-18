#!/usr/bin/env python3
"""Flag skill descriptions that have drifted into each other.

The router picks skills by description. As a catalog grows, two descriptions
can become so similar that the router can't tell them apart — the dominant
real-world failure mode for a bundle like noyalib's. This computes pairwise
TF-IDF cosine similarity across every skill `description` and flags pairs that
are too close.

Zero-dependency (stdlib only). WARN at >= WARN_AT, FAIL at >= FAIL_AT.
Idea adopted from addyosmani/agent-skills (MIT); implementation original.
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from pathlib import Path

WARN_AT = 0.50
FAIL_AT = 0.75

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

# Terms shared by every skill in a single-project family carry no signal and
# would inflate similarity; drop the obvious stopwords + project boilerplate.
STOP = set(
    """a an the and or of to in on for with when this that is are be it its as at by from into
    you your load use uses using skill covers see also not need needs which what how do does
    noyalib repo v0 0 14 date stamped branch feat release""".split()
)
TOKEN = re.compile(r"[a-z0-9_]+")


def frontmatter_description(text: str) -> str:
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not m:
        return ""
    block = m.group(1)
    dm = re.search(r"^description:[ \t]*(.*)$", block, re.MULTILINE)
    if not dm:
        return ""
    # capture inline value + any indented continuation lines
    start = dm.start()
    lines = block[start:].split("\n")
    out = [re.sub(r"^description:[ \t]*[|>+-]*[ \t]*", "", lines[0])]
    for line in lines[1:]:
        if re.match(r"^[A-Za-z0-9_-]+:", line):
            break
        out.append(line.strip())
    return " ".join(out).strip()


def vector(desc: str) -> Counter:
    toks = [t for t in TOKEN.findall(desc.lower()) if t not in STOP and len(t) > 1]
    return Counter(toks)


def tfidf(vectors: list[Counter]) -> list[dict[str, float]]:
    n = len(vectors)
    df: Counter = Counter()
    for v in vectors:
        df.update(v.keys())
    out = []
    for v in vectors:
        total = sum(v.values()) or 1
        vec = {}
        for term, count in v.items():
            idf = math.log((n + 1) / (df[term] + 1)) + 1.0
            vec[term] = (count / total) * idf
        out.append(vec)
    return out


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def main() -> int:
    skills = sorted(SKILLS_DIR.glob("**/SKILL.md"))
    names = [s.parent.name for s in skills]
    descs = [frontmatter_description(s.read_text(encoding="utf-8")) for s in skills]
    vecs = tfidf([vector(d) for d in descs])

    pairs = []
    for i in range(len(skills)):
        for j in range(i + 1, len(skills)):
            pairs.append((cosine(vecs[i], vecs[j]), names[i], names[j]))
    pairs.sort(reverse=True)

    warns = [p for p in pairs if p[0] >= WARN_AT]
    fails = [p for p in pairs if p[0] >= FAIL_AT]

    print(f"Top description similarities ({len(skills)} skills):")
    for sim, a, b in pairs[:8]:
        flag = "FAIL" if sim >= FAIL_AT else "warn" if sim >= WARN_AT else "ok"
        print(f"  {sim:.2f} [{flag}]  {a}  <->  {b}")

    print()
    if fails:
        print(f"FAIL: {len(fails)} pair(s) >= {FAIL_AT:.2f} — descriptions too similar to route between")
        return 1
    if warns:
        print(f"WARN: {len(warns)} pair(s) >= {WARN_AT:.2f} (advisory) — watch for drift")
    print("OK: no description collisions above the fail threshold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
