#!/usr/bin/env python3
"""Smoke-test profile installs through the agtmls CLI across native agents."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"
AGENTS = {
    "claude": (".claude", "CLAUDE.md"),
    "codex": (".codex", "AGENTS.md"),
    "aider": (".aider", "CONVENTIONS.md"),
}


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_agent(agent: str, tmp: Path, errors: list[str]) -> None:
    dot, prompt = AGENTS[agent]
    target = tmp / f"{agent}-noyalib"
    target.mkdir()
    proc = run(["install", "rust", agent, "--target", str(target), "--skills-only", "--profile", "noyalib"], ROOT)
    expect(proc.returncode == 0, f"{agent} profile install failed:\n{proc.stdout}", errors)
    expect((target / dot / "skills" / "using-agtmls").is_symlink(), f"{agent} missing general profile skill", errors)
    expect((target / dot / "skills" / "cross-language-port").is_symlink(), f"{agent} missing cross-language-port", errors)
    expect((target / dot / "skills" / "noyalib-ci-and-release").is_symlink(), f"{agent} missing noyalib bundle skill", errors)
    expect((target / dot / "commands" / "agtmls.md").is_symlink(), f"{agent} missing command link", errors)
    expect(not (target / prompt).exists(), f"{agent} skills-only profile wrote {prompt}", errors)


def check_unknown_profile(tmp: Path, errors: list[str]) -> None:
    target = tmp / "unknown"
    target.mkdir()
    proc = run(["install", "rust", "codex", "--target", str(target), "--skills-only", "--profile", "missing-profile"], ROOT)
    expect(proc.returncode != 0, "unknown profile install should fail", errors)
    expect("unknown profile" in proc.stdout, f"unknown profile message missing:\n{proc.stdout}", errors)


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-profile-install-") as td:
        tmp = Path(td)
        for agent in AGENTS:
            check_agent(agent, tmp, errors)
        check_unknown_profile(tmp, errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} install profile smoke issue(s)")
        return 1
    print("OK: install profile smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
