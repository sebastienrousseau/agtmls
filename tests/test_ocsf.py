# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Tests for OCSF (Open Cybersecurity Schema Framework) export."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _lib.findings import Finding
from _lib.ocsf import (
    export_ocsf_json,
    finding_to_ocsf,
    generate_finding_uid,
    severity_to_ocsf,
    to_ocsf_batch,
)


class OCSFMappingTests(unittest.TestCase):
    def test_severity_mapping(self) -> None:
        self.assertEqual(severity_to_ocsf("CRITICAL"), (5, "Critical"))
        self.assertEqual(severity_to_ocsf("HIGH"), (4, "High"))
        self.assertEqual(severity_to_ocsf("MEDIUM"), (3, "Medium"))
        self.assertEqual(severity_to_ocsf("LOW"), (2, "Low"))
        self.assertEqual(severity_to_ocsf("UNKNOWN"), (0, "Unknown"))

    def test_deterministic_uid(self) -> None:
        uid1 = generate_finding_uid("AGT-EXEC-001", "setup.sh", 10, "curl | bash")
        uid2 = generate_finding_uid("AGT-EXEC-001", "setup.sh", 10, "curl | bash")
        uid3 = generate_finding_uid("AGT-EXEC-001", "setup.sh", 11, "curl | bash")
        self.assertEqual(uid1, uid2)
        self.assertNotEqual(uid1, uid3)
        self.assertEqual(len(uid1), 36)

    def test_finding_to_ocsf_from_namedtuple(self) -> None:
        ts = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
        finding = Finding(
            file_path=Path("SKILL.md"),
            line=42,
            severity="HIGH",
            category="prompt_injection",
            message="Suspicious directive found",
            rule="AGT-INJ-001",
        )
        record = finding_to_ocsf(finding, skill_name="test-skill", timestamp=ts)
        self.assertEqual(record["class_uid"], 2001)
        self.assertEqual(record["class_name"], "Security Finding")
        self.assertEqual(record["category_uid"], 2)
        self.assertEqual(record["activity_id"], 1)
        self.assertEqual(record["severity_id"], 4)
        self.assertEqual(record["severity"], "High")
        self.assertEqual(record["status_id"], 1)
        self.assertEqual(record["status"], "New")
        self.assertEqual(record["time"], 1791720000000)
        self.assertEqual(record["finding_info"]["title"], "AgtMLS Rule AGT-INJ-001")
        self.assertIn("Prompt Injection", record["finding_info"]["types"])
        self.assertEqual(record["resources"][0]["name"], "test-skill")
        self.assertEqual(record["resources"][0]["data"]["line"], 42)

    def test_finding_to_ocsf_suppressed(self) -> None:
        dict_finding = {
            "file_path": "script.sh",
            "line": 15,
            "severity": "CRITICAL",
            "category": "unsafe_execution",
            "message": "Dangerous command",
            "rule": "AGT-EXEC-002",
            "suppressed": "Verified internal script",
        }
        record = finding_to_ocsf(dict_finding)
        self.assertEqual(record["severity_id"], 5)
        self.assertEqual(record["status_id"], 4)
        self.assertEqual(record["status"], "Suppressed")
        self.assertEqual(record["resources"][0]["data"]["suppressed"], "Verified internal script")
        self.assertEqual(record["resources"][0]["name"], "script.sh")

    def test_finding_to_ocsf_dict_defaults(self) -> None:
        minimal_dict: dict[str, Any] = {}
        record = finding_to_ocsf(minimal_dict)
        self.assertEqual(record["severity"], "Low")
        self.assertEqual(record["finding_info"]["title"], "AgtMLS Rule AGT-UNKNOWN")
        self.assertEqual(record["resources"][0]["name"], "")

    def test_batch_and_json_export(self) -> None:
        findings = [
            Finding(Path("a.sh"), 1, "LOW", "supply_chain", "msg", "AGT-SUPPLY-001"),
            {"file_path": "b.md", "line": 2, "severity": "MEDIUM", "message": "msg2"},
        ]
        batch = to_ocsf_batch(findings, skill_name="my-skill")
        self.assertEqual(len(batch), 2)

        json_out = export_ocsf_json(findings, skill_name="my-skill")
        parsed = json.loads(json_out)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["class_uid"], 2001)
