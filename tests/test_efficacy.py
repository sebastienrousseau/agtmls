# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Efficacy attestations: a skill's measured gain, bound to its exact bytes.

An efficacy attestation exists only while an uplift run measured the skill
as it is now: its subject is the skill digest, and its evidence is the run
whose recorded digest matches. Edit the skill and the attestation goes,
until a new run measures it. A claim cannot outlive what it was about.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT, load_script, retarget, run_main

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import attestations, digest, efficacy  # needs the scripts path first


def _row(agent: str, delta: float, with_tokens: float, without_tokens: float = 100.0, skill: str = "s") -> dict:
    return {"skill": skill, "agent": agent, "delta": delta,
            "with": {"score": 0.5 + delta, "tokens": with_tokens},
            "without": {"score": 0.5, "tokens": without_tokens}}


def _results(skill_digest: str, rows: list[dict], date: str = "2026-09-30T10:00:00Z") -> dict:
    runs = [{"agent": row["agent"], "arm": "with", "model": f"{row['agent']}-model"} for row in rows]
    return {"meta": {"date": date, "commit": "a" * 40, "trials": 5, "skills": {"s": skill_digest}},
            "summary": rows, "runs": runs}


class StatementTests(unittest.TestCase):
    def test_the_statement_carries_the_bar_the_evidence_and_each_agent(self) -> None:
        results = _results("sha256:" + "b" * 64, [_row("codex", 0.12, 133.0), _row("claude", 0.2, 132.0)])
        statement = efficacy.statement("s", "sha256:" + "b" * 64, results, "docs/evidence/r.json", "c" * 64)
        self.assertEqual(statement["predicateType"], "https://agtmls.dev/efficacy/v1")
        self.assertEqual(statement["subject"], [{"name": "s", "digest": {"sha256": "b" * 64}}])
        predicate = statement["predicate"]
        self.assertEqual(predicate["bar"], {"agents": 2, "big_gain": 0.2, "token_ceiling": 1.5})
        self.assertEqual(predicate["evidence"], {"path": "docs/evidence/r.json", "digest": {"sha256": "c" * 64},
                                                 "commit": "a" * 40, "date": "2026-09-30T10:00:00Z", "trials": 5})
        self.assertEqual([a["agent"] for a in predicate["agents"]], ["claude", "codex"])
        self.assertEqual(predicate["agents"][1], {"agent": "codex", "model": "codex-model", "score_without": 0.5,
                                                  "score_with": 0.62, "delta": 0.12, "token_ratio": 1.33,
                                                  "verdict": "helps"})
        self.assertTrue(predicate["meets_bar"])
        self.assertEqual(attestations.render(statement), attestations.render(statement))

    def test_a_costly_agent_means_the_bar_is_not_met(self) -> None:
        results = _results("sha256:" + "b" * 64, [_row("claude", 0.12, 160.0), _row("codex", 0.12, 110.0)])
        predicate = efficacy.statement("s", "sha256:" + "b" * 64, results, "p", "c" * 64)["predicate"]
        self.assertEqual([a["verdict"] for a in predicate["agents"]], ["too costly", "helps"])
        self.assertFalse(predicate["meets_bar"])


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agtmls-efficacy-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        (self.root / efficacy.EVIDENCE).mkdir(parents=True)

    def put(self, name: str, body: object) -> None:
        text = body if isinstance(body, str) else json.dumps(body)
        (self.root / efficacy.EVIDENCE / name).write_text(text, encoding="utf-8")

    def test_the_newest_run_of_these_exact_bytes_is_chosen(self) -> None:
        now = "sha256:" + "1" * 64
        self.put("old.json", _results(now, [_row("claude", 0.1, 100.0)], date="2026-09-01T00:00:00Z"))
        self.put("new.json", _results(now, [_row("claude", 0.2, 100.0)], date="2026-09-30T00:00:00Z"))
        self.put("other-bytes.json", _results("sha256:" + "2" * 64, [], date="2026-10-01T00:00:00Z"))
        self.put("broken.json", "{not json")
        self.put("not-results.json", {"hello": "world"})
        self.put("wrong-shape.json", {"meta": [], "summary": {}, "runs": []})
        found = efficacy.find_evidence(self.root, "s", now)
        self.assertIsNotNone(found)
        self.assertEqual(found[0], "docs/evidence/new.json")
        self.assertEqual(found[1]["summary"][0]["delta"], 0.2)

    def test_no_run_of_these_bytes_means_no_evidence(self) -> None:
        self.put("other.json", _results("sha256:" + "2" * 64, []))
        self.assertIsNone(efficacy.find_evidence(self.root, "s", "sha256:" + "1" * 64))
        shutil.rmtree(self.root / efficacy.EVIDENCE)
        self.assertIsNone(efficacy.find_evidence(self.root, "s", "sha256:" + "1" * 64))


class GeneratorTests(unittest.TestCase):
    """generate-skill-manifests.py writes, checks and drops efficacy attestations."""

    def setUp(self) -> None:
        from .support import registry_fixture

        self.workspace = Path(tempfile.mkdtemp(prefix="agtmls-efficacy-gen-"))
        self.addCleanup(shutil.rmtree, self.workspace, True)
        self.fixture = registry_fixture(self.workspace / "tree")
        self.module = load_script("generate-skill-manifests.py")
        retarget(self.module, self.fixture)
        self.skill = next(p for p in sorted((self.fixture / "skills").iterdir()) if (p / "SKILL.md").exists())
        shutil.rmtree(self.fixture / efficacy.EVIDENCE, ignore_errors=True)
        (self.fixture / efficacy.EVIDENCE).mkdir(parents=True)
        rows = [_row("claude", 0.2, 120.0, skill=self.skill.name), _row("codex", 0.1, 110.0, skill=self.skill.name),
                _row("claude", 0.3, 100.0, skill="some-other-skill")]
        results = _results(digest.skill_digest(self.skill), rows)
        results["meta"]["skills"] = {self.skill.name: results["meta"]["skills"]["s"]}
        (self.fixture / efficacy.EVIDENCE / "run.json").write_text(json.dumps(results), encoding="utf-8")
        self.attestation = self.fixture / "attestations" / self.skill.name / "efficacy.intoto.json"

    def test_a_measured_skill_gets_an_attestation_that_check_holds(self) -> None:
        self.assertEqual(run_main(self.module, "--write")[0], 0)
        statement = json.loads(self.attestation.read_text(encoding="utf-8"))
        self.assertEqual(statement["predicate"]["evidence"]["path"], "docs/evidence/run.json")
        self.assertTrue(statement["predicate"]["meets_bar"])
        self.assertEqual([a["delta"] for a in statement["predicate"]["agents"]], [0.2, 0.1])  # its own rows only
        self.assertEqual(run_main(self.module, "--check")[0], 0)

    def test_editing_the_skill_drops_its_attestation(self) -> None:
        run_main(self.module, "--write")
        (self.skill / "SKILL.md").write_text((self.skill / "SKILL.md").read_text(encoding="utf-8") + "\nedited\n",
                                             encoding="utf-8")
        code, output = run_main(self.module, "--check")
        self.assertEqual(code, 1)
        self.assertIn(f"attestations/{self.skill.name}/efficacy.intoto.json belongs to no current skill", output)
        run_main(self.module, "--write")
        self.assertFalse(self.attestation.exists())



class HardenedGateTests(unittest.TestCase):
    """A skill with an uplift case is hardened only on an attestation that meets the bar."""

    def setUp(self) -> None:
        from unittest import mock

        self.root = Path(tempfile.mkdtemp(prefix="agtmls-efficacy-gate-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.validator = load_script("validate-skill-metadata.py")
        patcher = mock.patch.object(self.validator, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.root / "evals/uplift/cases").mkdir(parents=True)
        (self.root / "evals/uplift/cases/measured.json").write_text("{}", encoding="utf-8")

    def attest(self, meets_bar: bool) -> None:
        path = self.root / "attestations/measured/efficacy.intoto.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"predicate": {"meets_bar": meets_bar}}), encoding="utf-8")

    def test_each_case(self) -> None:
        hardened = {"maturity": "hardened"}
        self.assertIn("efficacy attestation", self.validator.hardened_problems("measured", hardened)[0])
        self.attest(False)
        self.assertIn("does not meet the bar", self.validator.hardened_problems("measured", hardened)[0])
        self.attest(True)
        self.assertEqual(self.validator.hardened_problems("measured", hardened), [])
        self.assertEqual(self.validator.hardened_problems("measured", {"maturity": "draft"}), [])
        self.assertEqual(self.validator.hardened_problems("unmeasured", hardened), [])  # no uplift case yet
        (self.root / "attestations/measured/efficacy.intoto.json").write_text("{broken", encoding="utf-8")
        self.assertIn("efficacy attestation", self.validator.hardened_problems("measured", hardened)[0])

if __name__ == "__main__":
    unittest.main()
