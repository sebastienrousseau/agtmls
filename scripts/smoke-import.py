#!/usr/bin/env python3
"""Smoke-test external skill import normalization."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "import-skill.py"


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-import-smoke-") as td:
        tmp = Path(td)
        source = tmp / "external"
        source.mkdir()
        (source / "SKILL.md").write_text("# External Skill\n\nUse when testing imports.\n", encoding="utf-8")
        out_root = tmp / "repo"
        proc = subprocess.run([sys.executable, str(SCRIPT), str(source), "--name", "External Skill", "--out-root", str(out_root)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if proc.returncode != 0:
            errors.append(f"import failed:\n{proc.stdout}")
        target = out_root / "skills" / "imported" / "external-skill"
        if not (target / "SKILL.md").exists():
            errors.append("import missing SKILL.md")
        if not (target / "reference.md").exists():
            errors.append("import missing generated reference.md")
        meta_path = target / "metadata.json"
        if not meta_path.exists():
            errors.append("import missing metadata.json")
        else:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("maturity") != "draft" or not meta.get("safety_policy", {}).get("requires_human_review"):
                errors.append(f"import metadata should be draft and review-gated: {meta}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} import smoke issue(s)")
        return 1
    print("OK: import smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
