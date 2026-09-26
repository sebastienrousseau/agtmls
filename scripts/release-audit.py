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
  * every file PyPI serves for the version has the digest SHA256SUMS lists;
  * every release asset carries keyless build provenance (SLSA v1, signed
    through Sigstore) from this repository's release.yml at the tag, on a
    GitHub-hosted runner, when the release commit's workflow attests; and
    the attached provenance bundle, when there is one, verifies offline.

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
from _lib import signatures  # noqa: E402  (same)
from _lib.checksums import parse_sums  # noqa: E402  (needs the scripts path first)
from _lib.release_notes import notes_problems  # noqa: E402  (same)

REPO = "sebastienrousseau/agtmls"
PACKAGE = "agtmls"


def run(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), cwd=ROOT, text=True, capture_output=True, check=False)


def fetch_bytes(*cmd: str) -> bytes | None:
    """A command's exact output bytes, or None if it failed: git show and
    asset downloads, where a text round-trip could change what is verified."""
    proc = subprocess.run(list(cmd), cwd=ROOT, capture_output=True, check=False)
    return proc.stdout if proc.returncode == 0 else None


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


def audit_release(tag: str, repo: str, commit: str) -> tuple[list[str], str | None]:
    """(problems, SHA256SUMS text) for the GitHub release.

    Assets are listed and downloaded by id. For v0.0.6, the asset list GitHub
    embeds in the release -- which `gh release view`, `gh release download`
    and the tag and list endpoints all read -- showed none of its 17 assets,
    while the release's assets endpoint showed every one.
    """
    view = run("gh", "release", "view", tag, "--repo", repo, "--json", "body,isDraft,databaseId")
    if view.returncode != 0:
        return [f"no GitHub release for {tag}: {view.stderr.strip()}"], None
    release = json.loads(view.stdout)
    errors = []
    if release.get("isDraft"):
        errors.append(f"the {tag} release is still a draft")
    listed = run("gh", "api", f"repos/{repo}/releases/{release['databaseId']}/assets?per_page=100")
    assets = json.loads(listed.stdout or "[]") if listed.returncode == 0 else []
    sums_asset = next((asset for asset in assets if asset["name"] == "SHA256SUMS"), None)
    if sums_asset is None:
        return [*errors, f"the {tag} release has no SHA256SUMS asset"], None
    sums = run(
        "gh", "api", "-H", "Accept: application/octet-stream",
        f"repos/{repo}/releases/assets/{sums_asset['id']}",
    ).stdout
    errors += notes_problems(f"{tag} release body", release.get("body") or "", sums)
    errors += audit_assets(assets, sums)
    errors += audit_signature(commit, repo, assets)
    errors += audit_provenance(commit, repo, tag, assets)
    return errors, sums


def audit_signature(commit: str, repo: str, assets: list[dict]) -> list[str]:
    """index.json.sig on the release verifies against the release commit's
    ALLOWED_SIGNERS (agtmls-spec chapter 9).

    Only a commit that trusts a key is asked for a signature, so the releases
    published before signing began still audit clean. The keys and the index
    come from the commit, never from the release that is being checked.
    """
    signers = fetch_bytes("git", "show", f"{commit}:ALLOWED_SIGNERS")
    if signers is None:
        return []
    asset = next((a for a in assets if a["name"] == "index.json.sig"), None)
    if asset is None:
        return ["the release commit trusts ALLOWED_SIGNERS but the release has no index.json.sig"]
    index = fetch_bytes("git", "show", f"{commit}:index.json")
    sig = fetch_bytes("gh", "api", "-H", "Accept: application/octet-stream", f"repos/{repo}/releases/assets/{asset['id']}")
    if index is None or sig is None:
        return ["index.json or index.json.sig could not be read back to verify"]
    with tempfile.TemporaryDirectory(prefix="agtmls-audit-") as raw:
        work = Path(raw)
        for name, data in (("ALLOWED_SIGNERS", signers), ("index.json", index), ("index.json.sig", sig)):
            (work / name).write_bytes(data)
        status = signatures.verify(work / "index.json", work / "index.json.sig", work / "ALLOWED_SIGNERS",
                                   signatures.INDEX_NAMESPACE)
    if status != "verified":
        return [f"index.json.sig does not verify against the release commit's ALLOWED_SIGNERS ({status})"]
    print("OK: index.json.sig verifies against the release commit's ALLOWED_SIGNERS")
    return []


WORKFLOW = ".github/workflows/release.yml"
BUNDLE_SUFFIX = ".intoto.jsonl"


def _verify_provenance(path: Path, repo: str, tag: str, bundle: Path | None = None) -> str | None:
    """None if `path` has provenance from release.yml at `tag`, else gh's reason."""
    cmd = ["gh", "attestation", "verify", str(path), "--repo", repo,
           "--signer-workflow", f"{repo}/{WORKFLOW}", "--source-ref", f"refs/tags/{tag}",
           "--deny-self-hosted-runners", "--format", "json"]
    if bundle is not None:
        cmd += ["--bundle", str(bundle)]
    proc = run(*cmd)
    if proc.returncode == 0:
        return None
    reason = (proc.stderr or proc.stdout).strip().splitlines()
    return reason[-1] if reason else "verification failed"


def audit_provenance(commit: str, repo: str, tag: str, assets: list[dict]) -> list[str]:
    """Every asset's keyless build provenance verifies (Elevation Plan P2.6).

    release.yml attests the release's files with actions/attest-build-provenance:
    an SLSA v1 statement signed through Sigstore with the workflow's OIDC
    identity. `gh attestation verify` checks that signature against the
    public-good transparency log and pins who made it: this repository's
    release.yml, at this tag, on a GitHub-hosted runner. Required only when
    the release commit's workflow attests, so older releases audit as before.

    Two files are not themselves attested: SHA256SUMS, written after the
    attestation and checked against the notes and the release body instead,
    and the provenance bundle (`*.intoto.jsonl`), which a workflow that ships
    one must attach, and which must verify the wheel offline.
    """
    workflow = fetch_bytes("git", "show", f"{commit}:{WORKFLOW}")
    if workflow is None or b"attest-build-provenance" not in workflow:
        return []
    errors = []
    attested = [a for a in assets if a["name"] != "SHA256SUMS" and not a["name"].endswith(BUNDLE_SUFFIX)]
    bundles = [a for a in assets if a["name"].endswith(BUNDLE_SUFFIX)]
    with tempfile.TemporaryDirectory(prefix="agtmls-provenance-") as raw:
        local: dict[str, Path] = {}
        for asset in sorted(attested + bundles, key=lambda a: a["name"]):
            data = fetch_bytes("gh", "api", "-H", "Accept: application/octet-stream",
                               f"repos/{repo}/releases/assets/{asset['id']}")
            if data is None:
                errors.append(f"release asset {asset['name']} could not be downloaded to check its provenance")
                continue
            local[asset["name"]] = Path(raw) / Path(asset["name"]).name
            local[asset["name"]].write_bytes(data)
        for asset in sorted(attested, key=lambda a: a["name"]):
            if asset["name"] not in local:
                continue
            reason = _verify_provenance(local[asset["name"]], repo, tag)
            if reason is not None:
                errors.append(f"release asset {asset['name']} has no build provenance from {WORKFLOW} at {tag}: {reason}")
        if BUNDLE_SUFFIX.encode() in workflow and not bundles:
            errors.append(f"the release commit's workflow ships a provenance bundle, but the {tag} release has no *{BUNDLE_SUFFIX}")
        wheel = next((a["name"] for a in attested if a["name"].endswith(".whl") and a["name"] in local), None)
        for bundle in bundles:
            if bundle["name"] not in local:
                continue
            if wheel is None:
                errors.append(f"{bundle['name']} cannot be checked: the release has no wheel to verify against it")
                continue
            reason = _verify_provenance(local[wheel], repo, tag, local[bundle["name"]])
            if reason is not None:
                errors.append(f"{bundle['name']} does not verify {wheel} offline: {reason}")
    if not errors:
        print(f"OK: {len(attested)} release asset(s) carry build provenance from {WORKFLOW} at {tag}"
              + (f"; {', '.join(b['name'] for b in bundles)} verifies offline" if bundles else ""))
    return errors


def audit_assets(assets: list[dict], sums: str) -> list[str]:
    """Every file SHA256SUMS lists is attached, byte for byte, and nothing else."""
    listed, _ = parse_sums(sums)
    attached = {
        asset["name"]: str(asset.get("digest") or "").removeprefix("sha256:")
        for asset in assets if asset["name"] != "SHA256SUMS"
    }
    errors = []
    for name, digest in sorted(attached.items()):
        if name not in listed:
            errors.append(f"release asset {name} is not listed in SHA256SUMS")
        elif digest != listed[name]:
            errors.append(f"release asset {name} has sha256 {digest[:12]}, not the one SHA256SUMS lists")
    errors += [
        f"{name} is in SHA256SUMS but not attached to the release"
        for name in sorted(set(listed) - set(attached))
    ]
    return errors


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
    release_errors, sums = audit_release(args.tag, args.repo, args.commit)
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
