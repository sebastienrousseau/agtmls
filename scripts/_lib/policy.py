# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A skill's declared safety policy, and whether the skill keeps to it.

load_policy reads metadata.json's safety_policy; the capability-escalation
and honesty checks compare it with the tools the skill asks for and what its
text says it does. The per-file detectors live in analyzer.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .findings import Finding, read_capped
from .rules import TOOL_CAPABILITIES

# Which runtimes grant a skill's allowed-tools and which only read them.
PROVIDERS = Path(__file__).resolve().parents[2] / "providers.json"


TOOL_TOKEN = re.compile(r"[^\s,()'\"\[\]]+(?:\([^)]*\))?")


def frontmatter_tools(skill_md: Path) -> list[str]:
    """allowed-tools declared in SKILL.md frontmatter, if any.

    The Agent Skills spec writes the field space-separated, and every skill
    here does: `allowed-tools: "Read Glob Bash"`. This split on commas only,
    so that string came back as a single tool named "Read Glob Bash" that
    granted nothing, and AGT-CAP-001 could not fire on a real skill. Commas
    and YAML list brackets are still accepted.
    """
    text = read_capped(skill_md) or ""
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not match:
        return []
    field = re.search(r"^allowed-tools:[ \t]*(.*)$", match.group(1), re.MULTILINE)
    if not field:
        return []
    return TOOL_TOKEN.findall(field.group(1))


def load_policy(skill_dir: Path) -> tuple[dict, list[Finding]]:
    """Return (safety_policy, findings).

    Fail closed. A missing or unparseable metadata.json used to return no
    findings at all, so the cheapest way to defeat every policy check was to
    delete the file that declared the policy.
    """
    skill_md = skill_dir / "SKILL.md"
    metadata_json = skill_dir / "metadata.json"

    if not metadata_json.exists():
        return {}, [
            Finding(
                file_path=skill_md if skill_md.exists() else skill_dir,
                line=1,
                severity="HIGH",
                category="policy_honesty",
                message=(
                    "Skill declares no metadata.json, so its safety policy cannot be "
                    "verified; an unattested skill is not a safe skill"
                ),
                rule="AGT-POLICY-001",
            )
        ]
    try:
        meta = json.loads(metadata_json.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [
            Finding(
                file_path=metadata_json,
                line=1,
                severity="HIGH",
                category="policy_honesty",
                message=f"metadata.json is unparseable, so its safety policy cannot be verified: {exc}",
                rule="AGT-POLICY-002",
            )
        ]
    policy = meta.get("safety_policy", {})
    if not isinstance(policy, dict):
        return {}, [
            Finding(
                file_path=metadata_json,
                line=1,
                severity="HIGH",
                category="policy_honesty",
                message="metadata.json safety_policy is not an object",
                rule="AGT-POLICY-003",
            )
        ]
    return policy, []


def allowed_tools_semantics() -> dict[str, list[str]]:
    """Native agents grouped by what allowed-tools means to them.

    From providers.json: `grant` (the runtime pre-approves the tools, as
    Claude Code does), `declaration` (read, granting nothing, as the Agent
    Skills spec defines the field) or `ignored`. Without the table the
    caller falls back to the generic wording.
    """
    try:
        agents = json.loads(PROVIDERS.read_text(encoding="utf-8"))["native_agents"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    groups: dict[str, list[str]] = {}
    for name in sorted(agents):
        semantics = agents[name].get("allowed_tools_semantics") if isinstance(agents[name], dict) else None
        if isinstance(semantics, str):
            groups.setdefault(semantics, []).append(name)
    return groups


def escalation_rationale() -> str:
    """Who grants a denied capability, per target, so the finding is about
    effective escalation rather than a claim about every runtime."""
    groups = allowed_tools_semantics()
    if not groups:
        return "runtimes that pre-approve allowed-tools, such as Claude Code, will grant it"
    parts = []
    if groups.get("grant"):
        parts.append(f"runtimes that pre-approve allowed-tools grant it: {', '.join(groups['grant'])}")
    if groups.get("declaration"):
        parts.append(f"these read it as a declaration: {', '.join(groups['declaration'])}")
    if groups.get("ignored"):
        parts.append(f"these ignore it: {', '.join(groups['ignored'])}")
    return "; ".join(parts)


def check_capability_escalation(skill_dir: Path, policy: dict) -> list[Finding]:
    """Frontmatter must not grant a capability the safety policy denies.

    This is the capability the runtime actually honours: a skill can swear in
    metadata.json that it never shells out while handing the agent Bash in its
    own frontmatter, and nothing checked the two against each other.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return []
    findings: list[Finding] = []
    rationale = escalation_rationale()
    for tool in frontmatter_tools(skill_md):
        # `Bash(git log:*)` narrows Bash; it still grants executes_commands.
        capability = TOOL_CAPABILITIES.get(tool.split("(", 1)[0])
        if capability is None:
            continue
        if capability == "network_access":
            granted = policy.get("network_access") in {"optional", "required"}
        else:
            granted = bool(policy.get(capability))
        if not granted:
            findings.append(
                Finding(
                    file_path=skill_md,
                    line=1,
                    severity="HIGH",
                    category="capability_escalation",
                    message=f"Frontmatter grants '{tool}' but safety_policy denies {capability}; {rationale}",
                    rule="AGT-CAP-001",
                )
            )
    return findings


def check_skill_honesty(skill_dir: Path) -> list[Finding]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return []

    policy, findings = load_policy(skill_dir)
    findings.extend(check_capability_escalation(skill_dir, policy))
    body = read_capped(skill_md) or ""

    if policy.get("executes_commands") is False and re.search(
        r"(?i)\brun\s+(?:the\s+following|this)\s+(?:script|command|bash)", body
    ):
        findings.append(
            Finding(
                file_path=skill_md,
                line=1,
                severity="MEDIUM",
                category="policy_honesty",
                message="Skill claims executes_commands=false but text instructs agent to run commands",
                rule="AGT-POLICY-004",
            )
        )

    if policy.get("network_access") == "none" and re.search(
        r"(?i)\b(?:fetch|download|curl|wget)\s+https?://", body
    ):
        findings.append(
            Finding(
                file_path=skill_md,
                line=1,
                severity="MEDIUM",
                category="policy_honesty",
                message="Skill claims network_access=none but text contains instructions to fetch URLs",
                rule="AGT-POLICY-005",
            )
        )

    return findings
