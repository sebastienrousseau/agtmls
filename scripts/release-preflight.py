#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Prove a release tag is the release before it is pushed.

AGENTS.md section 3 makes this blocking: a tag must not be pushed until an
automated check proves that it targets the intended commit, is an annotated
tag signed by a key in KEYS.asc, is titled exactly `AgtMLS v<version>`, that
every packaged version at that commit is <version>, and that the prepared
release notes carry a user-visible summary and the artifact checksums.
Published tags are protected from deletion, so a wrong one is permanent.

    python3 scripts/release-preflight.py --tag v0.0.7 --commit <sha> \\
        --notes docs/release-notes/v0.0.7.md --sums dist/release/SHA256SUMS

Checksums exist only once the artifacts are built. `--pending-checksums`
accepts a notes file whose Checksums section says `pending`, for a release
whose artifacts are built after the tag is pushed; the checksums must then be
added and checked with --sums before the release is approved. It is the
exception, and the output says so.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib.release_notes import notes_problems  # noqa: E402  (scripts path first)

PROJECT = "AgtMLS"
KEYS = ROOT / "KEYS.asc"
TAG = re.compile(r"^v(0\.0\.\d+)$")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)


def versions_at(commit: str) -> dict[str, str]:
    """Every packaged statement of the version, as the commit holds it."""
    found: dict[str, str] = {}
    pyproject = git("show", f"{commit}:pyproject.toml").stdout
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    found["pyproject.toml"] = match.group(1) if match else ""
    for path, key in ((".claude-plugin/plugin.json", "version"), ("index.json", "registry_version")):
        shown = git("show", f"{commit}:{path}")
        found[path] = str(json.loads(shown.stdout).get(key, "")) if shown.returncode == 0 else ""
    init = git("show", f"{commit}:src/agtmls/__init__.py").stdout
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    found["src/agtmls/__init__.py"] = match.group(1) if match else ""
    return found


def check_tag(tag: str, version: str, commit: str) -> list[str]:
    errors: list[str] = []
    kind = git("cat-file", "-t", tag)
    if kind.returncode != 0:
        return [f"tag {tag} does not exist locally; create it with `git tag -s {tag} <commit>`"]
    if kind.stdout.strip() != "tag":
        errors.append(f"{tag} is a lightweight tag; release tags must be annotated and signed (`git tag -s`)")
    target = git("rev-parse", f"{tag}^{{commit}}").stdout.strip()
    expected = git("rev-parse", f"{commit}^{{commit}}").stdout.strip()
    if not expected:
        errors.append(f"expected commit {commit} does not exist")
    elif target != expected:
        errors.append(f"{tag} points at {target[:12]}, not the intended release commit {expected[:12]}")
    subject = git("for-each-ref", f"refs/tags/{tag}", "--format=%(contents:subject)").stdout.strip()
    if subject != f"{PROJECT} v{version}":
        errors.append(f"{tag} message is {subject!r}; it must be exactly '{PROJECT} v{version}'")
    verified = git("-c", f"gpg.ssh.allowedSignersFile={KEYS}", "verify-tag", tag)
    if verified.returncode != 0:
        errors.append(f"{tag} is not signed by a key in KEYS.asc: {verified.stderr.strip() or 'no signature'}")
    for path, found in versions_at(expected or commit).items():
        if found != version:
            errors.append(f"{path} at the release commit says {found or 'nothing'}, not {version}")
    return errors


def check_notes(notes: Path, sums: Path | None, pending: bool) -> list[str]:
    if not notes.is_file():
        return [f"release notes missing: {notes}"]
    return notes_problems(
        notes.name, notes.read_text(encoding="utf-8"),
        sums.read_text(encoding="utf-8") if sums is not None else None, pending,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="e.g. v0.0.7")
    parser.add_argument("--commit", required=True, help="the commit the tag must point at")
    parser.add_argument("--notes", type=Path, required=True, help="the prepared release notes")
    parser.add_argument("--sums", type=Path, help="SHA256SUMS of the built artifacts")
    parser.add_argument("--pending-checksums", action="store_true",
                        help="accept notes whose checksums are added after CI builds the artifacts")
    args = parser.parse_args()

    match = TAG.match(args.tag)
    if not match:
        print(f"FAIL: {args.tag} is not a release tag of the form v0.0.N")
        return 1
    version = match.group(1)
    errors = check_tag(args.tag, version, args.commit)
    errors += check_notes(args.notes, args.sums, args.pending_checksums)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} release preflight issue(s); do not push {args.tag}")
        return 1
    if args.pending_checksums and args.sums is None:
        print("WARN: checksums are pending; add them from CI's SHA256SUMS and re-run with --sums "
              "before approving the publish")
    print(f"OK: {args.tag} is a signed, correctly titled tag of {version} at the intended commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
