# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Open Cybersecurity Schema Framework (OCSF) exporter for AgtMLS findings.

Maps static security analysis findings to the OCSF Security Finding event
schema (Class UID: 2001, Category UID: 2) v1.3.0 for ingestion by SIEM,
SOAR, and security data lake platforms.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .findings import Finding

OCSF_VERSION = "1.3.0"
CLASS_UID = 2001  # Security Finding
CATEGORY_UID = 2  # Findings
ACTIVITY_CREATE = 1  # Create

SEVERITY_MAP: dict[str, tuple[int, str]] = {
    "CRITICAL": (5, "Critical"),
    "HIGH": (4, "High"),
    "MEDIUM": (3, "Medium"),
    "LOW": (2, "Low"),
}

STATUS_NEW = (1, "New")
STATUS_SUPPRESSED = (4, "Suppressed")


def severity_to_ocsf(severity: str) -> tuple[int, str]:
    """Map AgtMLS severity string to OCSF severity ID and label."""
    return SEVERITY_MAP.get(severity.upper(), (0, "Unknown"))


def generate_finding_uid(rule: str, path: str, line: int, message: str) -> str:
    """Generate a deterministic UUID v5 for reproducible finding tracking."""
    seed = f"{rule}:{path}:{line}:{message}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://agtmls.dev/findings/{seed}"))


def extract_finding_fields(finding: Finding | Mapping[str, Any]) -> dict[str, Any]:
    """Normalize finding fields from Finding namedtuple or dictionary."""
    if isinstance(finding, Finding):
        return {
            "file_path": str(finding.file_path),
            "line": finding.line,
            "severity": finding.severity,
            "category": finding.category,
            "message": finding.message,
            "rule": finding.rule,
            "suppressed": finding.suppressed,
        }
    return {
        "file_path": str(finding.get("file_path", "")),
        "line": int(finding.get("line", 0)),
        "severity": str(finding.get("severity", "LOW")),
        "category": str(finding.get("category", "general")),
        "message": str(finding.get("message", "")),
        "rule": str(finding.get("rule", "AGT-UNKNOWN")),
        "suppressed": finding.get("suppressed"),
    }


def finding_to_ocsf(
    finding: Finding | Mapping[str, Any],
    skill_name: str = "",
    agtmls_version: str = "0.0.22",
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """Transform an individual AgtMLS finding into an OCSF Security Finding event."""
    fields = extract_finding_fields(finding)
    now = timestamp or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    now_ms = int(now.timestamp() * 1000)

    sev_id, sev_name = severity_to_ocsf(fields["severity"])
    status_id, status_name = STATUS_SUPPRESSED if fields["suppressed"] else STATUS_NEW
    uid = generate_finding_uid(fields["rule"], fields["file_path"], fields["line"], fields["message"])

    return {
        "activity_id": ACTIVITY_CREATE,
        "activity_name": "Create",
        "category_uid": CATEGORY_UID,
        "category_name": "Findings",
        "class_uid": CLASS_UID,
        "class_name": "Security Finding",
        "metadata": {
            "version": OCSF_VERSION,
            "product": {
                "name": "AgtMLS",
                "vendor_name": "Sebastien Rousseau",
                "version": agtmls_version,
            },
            "profiles": ["security_control"],
        },
        "time": now_ms,
        "time_dt": now_iso,
        "status_id": status_id,
        "status": status_name,
        "severity_id": sev_id,
        "severity": sev_name,
        "finding_info": {
            "uid": uid,
            "title": f"AgtMLS Rule {fields['rule']}",
            "desc": fields["message"],
            "types": ["Static Analysis", fields["category"].replace("_", " ").title()],
            "src_url": f"https://agtmls.dev/rules/{fields['rule']}",
        },
        "resources": [
            {
                "name": skill_name or Path(fields["file_path"]).name,
                "type": "Skill",
                "data": {
                    "file_path": fields["file_path"],
                    "line": fields["line"],
                    "rule": fields["rule"],
                    "category": fields["category"],
                    "suppressed": fields["suppressed"],
                },
            }
        ],
    }


def to_ocsf_batch(
    findings: list[Finding | Mapping[str, Any]],
    skill_name: str = "",
    agtmls_version: str = "0.0.22",
    timestamp: datetime | None = None,
) -> list[dict[str, Any]]:
    """Convert a sequence of findings to an OCSF event list."""
    return [
        finding_to_ocsf(
            finding=f,
            skill_name=skill_name,
            agtmls_version=agtmls_version,
            timestamp=timestamp,
        )
        for f in findings
    ]


def export_ocsf_json(
    findings: list[Finding | Mapping[str, Any]],
    skill_name: str = "",
    agtmls_version: str = "0.0.22",
    indent: int = 2,
) -> str:
    """Format findings as a JSON-encoded OCSF event array."""
    batch = to_ocsf_batch(findings, skill_name=skill_name, agtmls_version=agtmls_version)
    return json.dumps(batch, indent=indent, sort_keys=True)
