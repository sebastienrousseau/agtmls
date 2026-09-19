#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Report what still stands between this ecosystem and a published release.

Trusted Publishing has a repository side and a registry side. This checks the
repository side -- that each release workflow exists, mints an OIDC token, and
names the environment the registry will be told about. The registry side is a
browser form; see docs/PUBLISHING.md.

Checked rather than assumed because the failure is quiet: a workflow missing
`id-token: write` runs fine until the publish step, which fails with an
authentication error that reads like a bad token rather than a missing
permission.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIBLINGS = ROOT.parent.parent

# (package, repo directory, registry, expected environment)
PACKAGES = [
    ("agtmls", ROOT, "PyPI", "pypi"),
    ("agtmls-core + agtmls-cli", SIBLINGS / "Rust" / "agtmls-core", "crates.io", "crates-io"),
    ("@agtmls/wasm", SIBLINGS / "Rust" / "agtmls-wasm", "npmjs", "npm"),
]


def check(name: str, repo: Path, registry: str, environment: str) -> list[str]:
    problems: list[str] = []
    workflow = repo / ".github" / "workflows" / "release.yml"
    if not repo.exists():
        return [f"repository not found at {repo}"]
    if not workflow.exists():
        return [f"no release workflow at {workflow.relative_to(repo)}"]

    text = workflow.read_text(encoding="utf-8")
    if "id-token: write" not in text:
        problems.append("workflow does not declare `id-token: write`; OIDC will fail at publish")
    if f"environment: {environment}" not in text:
        problems.append(f"workflow does not use `environment: {environment}`")
    if "dry_run" not in text:
        problems.append("no dry_run input; there is no way to rehearse")

    # A tag that does not match the version publishes the wrong thing under the
    # right name, which is worse than failing.
    if not re.search(r"does not match|tag.*version|version.*tag", text, re.IGNORECASE):
        problems.append("workflow does not appear to check the tag against the version")

    unpinned = [
        line.strip()
        for line in text.splitlines()
        if "uses:" in line and "@" in line and not re.search(r"@[a-f0-9]{40}", line)
    ]
    if unpinned:
        problems.append(f"{len(unpinned)} action(s) not pinned to a SHA: {unpinned[0]}")
    return problems


def main() -> int:
    print("Repository side of Trusted Publishing:\n")
    total = 0
    for name, repo, registry, environment in PACKAGES:
        problems = check(name, repo, registry, environment)
        total += len(problems)
        mark = "ok  " if not problems else "FAIL"
        print(f"  {mark}  {name:<26} -> {registry} (environment: {environment})")
        for problem in problems:
            print(f"          {problem}")

    print()
    print("Registry side -- confirm each in a browser, see docs/PUBLISHING.md:")
    for name, _, registry, environment in PACKAGES:
        print(f"  [ ] {registry:<10} trusted publisher for {name}, environment {environment}")
    print("  [ ] GitHub environment created, with a required reviewer, in each repository")
    print()
    if total:
        print(f"FAIL: {total} repository-side issue(s)")
        return 1
    print("OK: every release workflow is ready; the registry side is manual")
    return 0


if __name__ == "__main__":
    sys.exit(main())
