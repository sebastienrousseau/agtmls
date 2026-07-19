#!/usr/bin/env python3
"""Smoke-test redacted skill proposal generation."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPOSE = ROOT / "scripts" / "propose-skill-from-session.py"
SECRET = "sk" + "_test_" + "abcdefghijklmnopqrstuvwxyz" + "123456"


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-proposal-") as td:
        tmp = Path(td)
        transcript = tmp / "session.txt"
        out_dir = tmp / "out"
        transcript.write_text(
            f"$ python3 scripts/agtmls.py check\napi_key = {SECRET}\n"
            "Worked on repeated catalog validation and proposal generation.\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(PROPOSE),
                str(transcript),
                "--skill-name",
                "proposal-smoke",
                "--out-dir",
                str(out_dir),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if proc.returncode != 0:
            errors.append(f"proposal command failed:\n{proc.stdout}")
        proposal = out_dir / "proposal-smoke.md"
        if not proposal.exists():
            errors.append("proposal file was not written")
        else:
            text = proposal.read_text(encoding="utf-8")
            if SECRET in text:
                errors.append("proposal contains unredacted secret")
            if "[REDACTED]" not in text:
                errors.append("proposal did not include redaction marker")
            if "python3 scripts/agtmls.py check" not in text:
                errors.append("proposal did not capture command signal")
            if "human review required" not in text:
                errors.append("proposal missing human-review status")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} proposal smoke issue(s)")
        return 1
    print("OK: proposal smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
