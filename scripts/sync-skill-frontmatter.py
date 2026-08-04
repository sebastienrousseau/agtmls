#!/usr/bin/env python3
"""Mirror metadata.json into spec-portable SKILL.md frontmatter.

`metadata.json` is an AgtMLS-private sidecar: Claude Code, Cursor, Gemini
CLI and every other runtime read `SKILL.md` and nothing else, so a consumer
installing a skill through the plugin marketplace or a Markdown export gets
no risk signal at all. The Agent Skills spec reserves three fields for
exactly this, and this script is the one-way bridge into them:

    required_tools  ->  compatibility   (what the skill needs to run)
    safety_policy   ->  metadata        (what the skill is allowed to touch)
    safety_policy   ->  allowed-tools   (the tool surface it implies)

`metadata.json` stays the source of truth; the frontmatter is generated.
Run with --check in CI (drift fails) and --write to regenerate.

  python3 scripts/sync-skill-frontmatter.py --check
  python3 scripts/sync-skill-frontmatter.py --write

`allowed-tools` is experimental and runtimes disagree on its meaning: some
read it as a pre-approval (no permission prompt while the skill is active),
others as a restriction (the skill may use nothing else). CAPABILITY mode
declares the full surface the safety policy implies, which is correct under
the restriction reading and pre-approves under the other. READONLY mode
declares only non-mutating tools, which never widens permissions but breaks
skills under a restriction-reading runtime. Flip ALLOWED_TOOLS_MODE to
choose; the trade-off is a deliberate posture decision, not a default.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

ALLOWED_TOOLS_MODE = "capability"  # "capability" | "readonly"

# Keys this script owns. Anything else in the frontmatter is preserved
# verbatim, so hand-authored `name`/`description` survive regeneration.
GENERATED = ("license", "compatibility", "allowed-tools", "metadata")

READ_ONLY_TOOLS = ["Read", "Glob", "Grep"]
DEFAULT_COMPAT = "Tested with Claude Code, Codex, and Aider skill layouts"
MAX_COMPAT = 500


def load_metadata(skill_dir: Path) -> dict[str, object]:
    """A skill's own metadata.json. The tree is flat, so there is no bundle
    directory to inherit from — `bundle` is a field on this file."""
    direct = skill_dir / "metadata.json"
    return json.loads(direct.read_text(encoding="utf-8")) if direct.exists() else {}


def derive_allowed_tools(policy: dict[str, object]) -> list[str]:
    tools = list(READ_ONLY_TOOLS)
    if ALLOWED_TOOLS_MODE == "readonly":
        return tools
    if policy.get("writes_files"):
        tools += ["Write", "Edit"]
    if policy.get("executes_commands"):
        tools.append("Bash")
    if policy.get("network_access") in {"optional", "required"}:
        tools += ["WebFetch", "WebSearch"]
    return tools


def derive_compatibility(metadata: dict[str, object]) -> str:
    required = [str(tool) for tool in metadata.get("required_tools", []) if str(tool).strip()]
    compat = f"Requires {', '.join(required)}. {DEFAULT_COMPAT}" if required else DEFAULT_COMPAT
    if len(compat) > MAX_COMPAT:
        compat = compat[: MAX_COMPAT - 1].rstrip() + "…"
    return compat


def derive_metadata(metadata: dict[str, object]) -> list[tuple[str, str]]:
    """Flat string key/value pairs, namespaced to avoid collisions with
    other publishers' metadata as the spec recommends."""
    policy = metadata.get("safety_policy", {})
    if not isinstance(policy, dict):
        policy = {}
    pairs = [
        ("agtmls-version", str(metadata.get("version", ""))),
        ("agtmls-owner", str(metadata.get("owner", ""))),
        ("agtmls-maturity", str(metadata.get("maturity", ""))),
        ("agtmls-bundle", str(metadata.get("bundle") or "")),
        ("agtmls-risk-level", str(policy.get("risk_level", ""))),
        ("agtmls-network-access", str(policy.get("network_access", ""))),
        ("agtmls-writes-files", json.dumps(bool(policy.get("writes_files")))),
        ("agtmls-executes-commands", json.dumps(bool(policy.get("executes_commands")))),
        ("agtmls-handles-secrets", json.dumps(bool(policy.get("handles_secrets")))),
        ("agtmls-requires-human-review", json.dumps(bool(policy.get("requires_human_review")))),
    ]
    return [(key, value) for key, value in pairs if value]


def quote(value: str) -> str:
    """YAML-safe scalar. Booleans and versions must stay strings per spec."""
    return json.dumps(value)


def split_frontmatter(text: str) -> tuple[list[str], str] | None:
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not match:
        return None
    return match.group(1).split("\n"), text[match.end() :]


def preserved_blocks(lines: list[str]) -> list[str]:
    """Frontmatter lines minus the keys this script regenerates, keeping
    each surviving key's continuation lines with it."""
    kept: list[str] = []
    dropping = False
    for line in lines:
        top = re.match(r"^([A-Za-z0-9_-]+):", line)
        if top and not line.startswith((" ", "\t", "-")):
            dropping = top.group(1) in GENERATED
        if not dropping:
            kept.append(line)
    return kept


def render(skill_md: Path) -> str | None:
    text = skill_md.read_text(encoding="utf-8")
    parts = split_frontmatter(text)
    if parts is None:
        return None
    lines, body = parts
    metadata = load_metadata(skill_md.parent)
    if not metadata:
        return None

    policy = metadata.get("safety_policy", {})
    policy = policy if isinstance(policy, dict) else {}

    out = preserved_blocks(lines)
    while out and not out[-1].strip():
        out.pop()
    out.append(f"license: {metadata.get('license', 'MIT')}")
    out.append(f"compatibility: {quote(derive_compatibility(metadata))}")
    out.append(f"allowed-tools: {quote(' '.join(derive_allowed_tools(policy)))}")
    out.append("metadata:")
    out.extend(f"  {key}: {quote(value)}" for key, value in derive_metadata(metadata))

    return "---\n" + "\n".join(out) + "\n---\n" + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="fail if any SKILL.md is stale")
    group.add_argument("--write", action="store_true", help="regenerate frontmatter in place")
    args = parser.parse_args()

    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not skill_files:
        print(f"no SKILL.md files found under {SKILLS_DIR}", file=sys.stderr)
        return 1

    stale: list[str] = []
    written = 0
    for skill_md in skill_files:
        rel = skill_md.relative_to(ROOT).as_posix()
        wanted = render(skill_md)
        if wanted is None:
            print(f"FAIL: {rel}: unparseable frontmatter or missing metadata.json")
            return 1
        if wanted == skill_md.read_text(encoding="utf-8"):
            continue
        if args.write:
            skill_md.write_text(wanted, encoding="utf-8")
            written += 1
        else:
            stale.append(rel)

    if args.write:
        print(f"OK: {written} of {len(skill_files)} SKILL.md frontmatter block(s) regenerated")
        return 0
    if stale:
        for rel in stale:
            print(f"FAIL: {rel}: frontmatter out of sync with metadata.json")
        print()
        print(f"FAIL: {len(stale)} stale skill(s); run sync-skill-frontmatter.py --write")
        return 1
    print(f"OK: {len(skill_files)} SKILL.md frontmatter block(s) in sync with metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
