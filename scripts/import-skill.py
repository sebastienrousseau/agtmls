#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Import an external Markdown skill into the AgtMLS draft area.

This is the registry's untrusted-input boundary, so it is the one place where
the security analyzer must run by default. It previously did three things that
inverted the threat model:

  * it copied arbitrary third-party content without auditing it;
  * it deleted the source's own metadata.json; and
  * it wrote a replacement asserting network_access=none, executes_commands=
    false and risk_level=low -- an attestation of harmlessness that nothing
    had checked, which then propagated into index.json, the agent card and
    the published SBOM.

An import is now audited first, keeps the source's claims as evidence, and is
marked high-risk and review-gated until a human says otherwise. Capability
fields stay restrictive: they drive derive_allowed_tools(), so widening them
would hand the imported skill more tools, not fewer.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "scripts" / "audit-skill.py"
BLOCKING_SEVERITIES = {"CRITICAL", "HIGH"}
# An external skill has no AgtMLS metadata.json by definition, and this script
# is what writes one. Blocking on its absence would block every import; the
# rest of the policy rules still apply, and the generated metadata is marked
# unattested rather than claiming the check passed.
NOT_APPLICABLE_TO_IMPORT = {"AGT-POLICY-001"}


def registry_version() -> str:
    """The canonical version, read rather than hardcoded.

    A literal here drifted every release and had to be patched by
    bump-version.py, which meant the importer's idea of the version was only
    ever correct because another script kept rewriting it.
    """
    plugin = ROOT / ".claude-plugin" / "plugin.json"
    return json.loads(plugin.read_text(encoding="utf-8"))["version"]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "imported-skill"


def source_skill_md(source: Path) -> Path:
    if source.is_dir():
        candidate = source / "SKILL.md"
        if candidate.exists():
            return candidate
        markdown = sorted(source.glob("*.md"))
        if markdown:
            return markdown[0]
    if source.is_file():
        return source
    raise SystemExit(f"no Markdown skill found in {source}")


def title_from(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def audit(source: Path) -> tuple[list[dict], str]:
    """Run the analyzer over the import candidate."""
    proc = subprocess.run(
        [sys.executable, str(AUDIT), str(source), "--strict", "--format", "json"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    try:
        return json.loads(proc.stdout).get("findings", []), proc.stdout
    except json.JSONDecodeError:
        raise SystemExit(f"could not audit {source}: {proc.stdout}\n{proc.stderr}")


def safe_copy(source: Path, target: Path, skill_md: Path) -> None:
    """Copy the source tree without following symlinks out of it.

    copytree's default resolves symlinks and copies their *contents*, so a
    hostile import containing `notes.md -> ~/.ssh/id_ed25519` would have
    copied a private key into the registry.
    """
    for item in source.iterdir():
        if item.is_symlink():
            print(f"   skipped symlink: {item.name}", file=sys.stderr)
            continue
        if item.name == "metadata.json":
            shutil.copy2(item, target / "metadata.source.json")
            continue
        dst = target / ("SKILL.md" if item == skill_md else item.name)
        if item.is_dir():
            shutil.copytree(item, dst, symlinks=True, ignore_dangling_symlinks=True)
        elif item.is_file():
            shutil.copy2(item, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", maxsplit=1)[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--bundle", default="imported",
                        help="bundle label recorded in metadata.json (the skill tree is flat)")
    parser.add_argument("--out-root", type=Path, default=ROOT)
    parser.add_argument(
        "--force-unsafe",
        action="store_true",
        help="import despite CRITICAL/HIGH findings; the findings are recorded in metadata.json",
    )
    parser.add_argument("--skip-audit", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    skill_md = source_skill_md(args.source)
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    name = slugify(args.name or title_from(text, skill_md.stem))
    out_root = args.out_root.resolve()
    target = out_root / "skills" / name
    if target.exists():
        raise SystemExit(f"target skill already exists: {target}")

    findings: list[dict] = []
    if not args.skip_audit:
        findings, report = audit(args.source)
        blocking = [
            f for f in findings
            if f["severity"] in BLOCKING_SEVERITIES
            and f.get("rule") not in NOT_APPLICABLE_TO_IMPORT
        ]
        if blocking:
            print(f"Refusing to import {name}: {len(blocking)} blocking finding(s).", file=sys.stderr)
            for finding in blocking:
                print(
                    f"  [{finding['severity']}] {finding['file']}:{finding['line']} "
                    f"({finding['category']}): {finding['message']}",
                    file=sys.stderr,
                )
            if not args.force_unsafe:
                print(
                    "\nReview the source, or re-run with --force-unsafe to import it "
                    "quarantined with these findings recorded.",
                    file=sys.stderr,
                )
                return 1
            print("\n--force-unsafe: importing anyway; findings recorded in metadata.json", file=sys.stderr)

    target.mkdir(parents=True)
    if args.source.is_dir():
        safe_copy(args.source, target, skill_md)
    else:
        shutil.copy2(skill_md, target / "SKILL.md")
    if not (target / "reference.md").exists():
        (target / "reference.md").write_text(
            f"# {name} Reference\n\nImported draft. Review and expand before publication.\n",
            encoding="utf-8",
        )

    meta = {
        "bundle": args.bundle,
        "version": registry_version(),
        "owner": "unassigned",
        "maturity": "draft",
        "supported_agents": ["claude", "codex", "aider"],
        "required_tools": [],
        # Capabilities stay closed because derive_allowed_tools() reads them:
        # a reviewer opens them deliberately, the importer never guesses.
        "safety_policy": {
            "network_access": "none",
            "writes_files": False,
            "executes_commands": False,
            "handles_secrets": False,
            "requires_human_review": True,
            # Unvetted third-party content is high risk until a human says
            # otherwise. Asserting "low" here was an attestation nobody made.
            "risk_level": "high",
        },
        "provenance": {
            "imported_from": str(args.source),
            "attested": False,
            "audit_findings": findings,
            "source_metadata": "metadata.source.json" if (target / "metadata.source.json").exists() else None,
            "review_required": (
                "Capabilities and risk_level are placeholders set by import-skill.py, "
                "not claims verified by anyone. Review before publication."
            ),
        },
    }
    (target / "metadata.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(target.relative_to(out_root).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
