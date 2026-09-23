# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Growth against registry size, for criterion 3.5.

A different experiment from the latency suite in bench.py: different
inputs, a different statistic, and a different question -- not how long
something takes, but how that time moves when the registry gets ten times
bigger. It lives here so each file answers one question.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
RESULTS = ROOT / "benchmarks" / "results"


def environment() -> dict[str, str]:
    import platform

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
    }


def synthetic_registry(target: Path, factor: int) -> int:
    """`factor` copies of every shipped skill, for a scaling measurement."""
    source = ROOT / "skills"
    originals = sorted(p for p in source.iterdir() if p.is_dir())
    count = 0
    for index in range(factor):
        for skill in originals:
            shutil.copytree(skill, target / f"{skill.name}-{index:03d}")
            count += 1
    return count


def scaling() -> int:
    """Criterion 3.5: growth against registry size, measured rather than argued."""
    sys.path.insert(0, str(SCRIPTS))
    from _lib.digest import skill_digest


    spec = importlib.util.spec_from_file_location(
        "_bench_collisions", SCRIPTS / "check-skill-collisions.py"
    )
    collisions = importlib.util.module_from_spec(spec)
    sys.modules["_bench_collisions"] = collisions
    spec.loader.exec_module(collisions)

    rows = []
    with tempfile.TemporaryDirectory(prefix="agtmls-scaling-") as raw:
        for factor in (1, 10):
            tree = Path(raw) / f"x{factor}"
            tree.mkdir()
            size = synthetic_registry(tree, factor)

            started = time.perf_counter()
            for skill in sorted(p for p in tree.iterdir() if p.is_dir()):
                skill_digest(skill)
            digest_ms = (time.perf_counter() - started) * 1000

            descriptions = [
                collisions.frontmatter_description((p / "SKILL.md").read_text(encoding="utf-8"))
                for p in sorted(tree.iterdir())
                if (p / "SKILL.md").exists()
            ]
            started = time.perf_counter()
            vectors = collisions.tfidf([collisions.vector(d) for d in descriptions])
            for i in range(len(vectors)):
                for j in range(i + 1, len(vectors)):
                    collisions.cosine(vectors[i], vectors[j])
            pairwise_ms = (time.perf_counter() - started) * 1000

            rows.append({
                "factor": factor,
                "skills": size,
                "digest_ms": round(digest_ms, 2),
                "pairwise_ms": round(pairwise_ms, 2),
            })

    size_growth = rows[1]["skills"] / rows[0]["skills"]
    digest_growth = rows[1]["digest_ms"] / rows[0]["digest_ms"]
    pairwise_growth = rows[1]["pairwise_ms"] / rows[0]["pairwise_ms"]

    print(f"  {'skills':>8}{'digest ms':>12}{'pairwise ms':>14}")
    for row in rows:
        print(f"  {row['skills']:>8}{row['digest_ms']:>12.1f}{row['pairwise_ms']:>14.1f}")
    print()
    print(f"  size x{size_growth:.0f}  ->  digest x{digest_growth:.1f}, pairwise x{pairwise_growth:.1f}")

    report = {
        "schema_version": 1,
        "generated_by": "scripts/bench.py --scaling",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": environment(),
        "rows": rows,
        "growth": {
            "size": round(size_growth, 2),
            "digest": round(digest_growth, 2),
            "pairwise": round(pairwise_growth, 2),
        },
        # Pairwise description scoring compares every skill with every other,
        # so it is quadratic by definition. It runs once per gate and never
        # per request, which is what makes that acceptable -- and saying so
        # here rather than only in BENCHMARKS.md is what lets a checker tell
        # a deliberate curve from an accidental one.
        "cold_paths": ["pairwise"],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "scaling.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Digest is O(bytes) and must stay linear. Pairwise scoring is O(n^2) by
    # construction -- it compares every description with every other -- so it
    # is measured and reported, not asserted against a linear bound.
    if digest_growth > size_growth * 1.5:
        print(f"\nFAIL: digest grew x{digest_growth:.1f} for x{size_growth:.0f} the registry")
        return 1
    print(f"\nOK: digest is linear in registry size; pairwise is x{pairwise_growth:.1f} "
          f"for x{size_growth:.0f} (quadratic by design, see BENCHMARKS.md)")
    return 0
