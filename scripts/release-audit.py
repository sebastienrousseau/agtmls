#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Read a published release back from where it was published.

AGENTS.md section 3: a green workflow is not evidence that the release is
right. This reads each published location independently and fails on any
disagreement:

  * the tag on the remote is the tag object checked locally, so the pushed
    tag is the signed one, and it points at the intended commit;
  * the GitHub release body has a user-visible summary, and its Checksums
    section equals the SHA256SUMS asset published beside it;
  * every file PyPI serves for the version has the digest SHA256SUMS lists.

    python3 scripts/release-audit.py --tag v0.0.6 --commit <sha>
    python3 scripts/release-audit.py --tag v0.0.6 --commit <sha> --before-pypi

--before-pypi skips the PyPI check, for the point between the GitHub release
and approving the publish job.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib.checksums import parse_sums  # noqa: E402  (needs the scripts path first)
from _lib.release_notes import notes_problems  # noqa: E402  (same)

REPO = "sebastienrousseau/agtmls"
PACKAGE = "agtmls"


def run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=ROOT, text=True, capture_output=True, check=False)


def fetch_json(url: str) -> dict | None:
    """JSON from `url`, or None when it is not there (yet)."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def audit_tag(tag: str, commit: str) -> list[str]:
    local = run("git", "rev-parse", tag).stdout.strip()
    expected = run("git", "rev-parse", f"{commit}^{{commit}}").stdout.strip()
    listed = run("git", "ls-remote", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    refs = dict(reversed(line.split("\t", 1)) for line in listed.stdout.splitlines() if "\t" in line)
    remote, peeled = refs.get(f"refs/tags/{tag}"), refs.get(f"refs/tags/{tag}^{{}}")
    if remote is None:
        return [f"{tag} is not on the remote"]
    errors = []
    if remote != local:
        errors.append(f"remote {tag} is object {remote[:12]}, not the local signed tag {local[:12] or '(none)'}")
    if peeled != expected:
        errors.append(f"remote {tag} points at {(peeled or '')[:12]}, not the release commit {expected[:12]}")
    return errors


def audit_release(tag: str, repo: str) -> tuple[list[str], str | None]:
    """(problems, SHA256SUMS text) for the GitHub release."""
    view = run("gh", "release", "view", tag, "--repo", repo, "--json", "body,isDraft")
    if view.returncode != 0:
        return [f"no GitHub release for {tag}: {view.stderr.strip()}"], None
    release = json.loads(view.stdout)
    errors = []
    if release.get("isDraft"):
        errors.append(f"the {tag} release is still a draft")
    with tempfile.TemporaryDirectory(prefix="agtmls-audit-") as raw:
        got = run("gh", "release", "download", tag, "--repo", repo, "--pattern", "SHA256SUMS", "--dir", raw)
        sums_path = Path(raw) / "SHA256SUMS"
        if got.returncode != 0 or not sums_path.exists():
            return [*errors, f"the {tag} release has no SHA256SUMS asset"], None
        sums = sums_path.read_text(encoding="utf-8")
    errors += notes_problems(f"{tag} release body", release.get("body") or "", sums)
    return errors, sums


def audit_pypi(version: str, sums: str) -> list[str]:
    data = fetch_json(f"https://pypi.org/pypi/{PACKAGE}/{version}/json")
    if data is None:
        return [f"{PACKAGE} {version} is not on PyPI"]
    listed, _ = parse_sums(sums)
    files = {item["filename"]: item["digests"]["sha256"] for item in data.get("urls", [])}
    errors = []
    if not any(name.endswith(".whl") for name in files) or not any(name.endswith(".tar.gz") for name in files):
        errors.append(f"PyPI {version} should carry a wheel and an sdist; it has {sorted(files) or 'nothing'}")
    for name, digest in sorted(files.items()):
        if listed.get(name) != digest:
            errors.append(f"PyPI {name} has sha256 {digest[:12]}, which SHA256SUMS does not list")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True, help="the commit the release must be")
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--before-pypi", action="store_true", help="skip the PyPI check")
    args = parser.parse_args()

    errors = audit_tag(args.tag, args.commit)
    release_errors, sums = audit_release(args.tag, args.repo)
    errors += release_errors
    if not args.before_pypi:
        if sums is None:
            errors.append("PyPI not checked: there is no SHA256SUMS to check it against")
        else:
            errors += audit_pypi(args.tag.removeprefix("v"), sums)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} published-release issue(s) for {args.tag}")
        return 1
    where = "the tag and the GitHub release" if args.before_pypi else "the tag, the GitHub release and PyPI"
    print(f"OK: {args.tag} read back from {where}; all agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
