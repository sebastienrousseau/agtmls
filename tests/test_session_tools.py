# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The skill-evolution tools: they read transcripts and write local records.

`propose-skill-from-session.py`, `evolve-session.py` and `record-evidence.py`
are the only scripts that take a user's own session text as input. Their one
safety property is redaction: a transcript routinely contains a token pasted
into a shell, and a proposal that copies it verbatim into `.agtmls/` has moved
a secret somewhere nobody thinks to look for one. The rest is that they refuse
bad input before writing anything, and write where they say they did.

Every write here lands in a temporary tree. The default output directory is
derived from ROOT, so each module is retargeted before it runs, and the
defaults are exercised only against that copy.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from .support import load_script, retarget, run_main

TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0"
BLOB = "QWxhZGRpbjpvcGVuIHNlc2FtZQ" + "Zm9vYmFyYmF6cXV4"  # 42 base64 characters
TRANSCRIPT = f"""Working on the parser today.
$ make test
> python3 scripts/check-parser.py --strict
export API_KEY={"x" * 20}
pushed with {TOKEN} and signed {BLOB}
edited src/parser/lexer.py and docs/guide.md, then src/parser/lexer.py again
parser parser parser lexer
"""


class SessionToolBase(unittest.TestCase):
    """A throwaway ROOT holding an index.json and a transcript."""

    root: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._workspace = tempfile.mkdtemp(prefix="agtmls-session-")
        cls.root = (Path(cls._workspace) / "tree").resolve()
        cls.root.mkdir()
        (cls.root / "index.json").write_text(json.dumps({"skills": [
            {"name": "alpha", "safety_policy": {"network_access": "none", "risk_level": "low"}},
            {"name": "beta"},
        ]}), encoding="utf-8")
        cls.transcript = cls.root / "transcript.md"
        cls.transcript.write_text(TRANSCRIPT, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def setUp(self) -> None:
        self.addCleanup(shutil.rmtree, self.root / ".agtmls", True)
        out = tempfile.mkdtemp(prefix="out-", dir=self._workspace)
        self.addCleanup(shutil.rmtree, out, True)
        self.out = Path(out)

    def module(self, script: str):
        module = load_script(script)
        retarget(module, self.root)
        return module


class ProposeSkillTests(SessionToolBase):
    """propose-skill-from-session.py -- a draft SKILL.md from a transcript."""

    def propose(self, *args: str) -> tuple[int, str]:
        return run_main(self.module("propose-skill-from-session.py"), *args)

    def test_each_secret_shape_is_redacted_and_the_key_name_is_kept(self) -> None:
        module = self.module("propose-skill-from-session.py")
        clean = module.redact(TRANSCRIPT)
        for secret in ("x" * 20, TOKEN, BLOB):
            self.assertNotIn(secret, clean)
        # Keeping the variable name is what lets a reviewer see a key was used.
        self.assertIn("API_KEY=[REDACTED]", clean)
        self.assertIn("pushed with [REDACTED] and signed [REDACTED]", clean)

    def test_a_proposal_summarises_commands_paths_and_terms(self) -> None:
        code, output = self.propose(str(self.transcript), "--skill-name", "parser-work",
                                    "--out-dir", str(self.out))
        self.assertEqual(code, 0, output)
        written = self.out / "parser-work.md"
        # Outside ROOT, the path is reported as given rather than relativised.
        self.assertEqual(output.strip(), f"wrote {written}")
        text = written.read_text(encoding="utf-8")
        self.assertIn("# Skill Proposal: parser-work", text)
        self.assertIn("Status: draft, human review required", text)
        self.assertIn("name: parser-work", text)
        self.assertIn("Commands seen: 2", text)
        self.assertIn("make test\npython3 scripts/check-parser.py --strict\n", text)
        # Three path mentions, two distinct paths listed once each, sorted.
        self.assertIn("docs/guide.md\nscripts/check-parser.py\nsrc/parser/lexer.py\n", text)
        self.assertIn("around parser,", text)
        self.assertNotIn(TOKEN, text)
        self.assertIn("evals/cases/parser-work.json", text)

    def test_the_default_destination_is_under_the_root_and_reported_relatively(self) -> None:
        code, output = self.propose(str(self.transcript), "--skill-name", "parser-work")
        self.assertEqual(code, 0, output)
        self.assertEqual(output.strip(), "wrote .agtmls/proposals/parser-work.md")
        self.assertTrue((self.root / ".agtmls" / "proposals" / "parser-work.md").is_file())

    def test_an_empty_transcript_still_renders_with_explicit_placeholders(self) -> None:
        empty = self.out / "empty.md"
        empty.write_text("", encoding="utf-8")
        code, _ = self.propose(str(empty), "--skill-name", "blank", "--out-dir", str(self.out))
        self.assertEqual(code, 0)
        text = (self.out / "blank.md").read_text(encoding="utf-8")
        self.assertIn("Top terms: none", text)
        self.assertEqual(text.count("(none detected)"), 2)
        self.assertIn("observed in this transcript around blank.", text)

    def test_a_name_that_is_not_kebab_case_is_refused_before_writing(self) -> None:
        code, output = self.propose(str(self.transcript), "--skill-name", "Parser_Work",
                                    "--out-dir", str(self.out))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: --skill-name must be kebab-case", output)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_a_missing_transcript_is_refused_before_writing(self) -> None:
        missing = self.out / "nope.md"
        code, output = self.propose(str(missing), "--skill-name", "parser-work",
                                    "--out-dir", str(self.out / "sub"))
        self.assertEqual(code, 1)
        self.assertIn(f"FAIL: transcript not found: {missing}", output)
        self.assertFalse((self.out / "sub").exists())


class EvolveSessionTests(SessionToolBase):
    """evolve-session.py -- a machine-readable proposal plus the redacted text."""

    def evolve(self, *args: str) -> tuple[int, str]:
        return run_main(self.module("evolve-session.py"), *args)

    def test_a_proposal_records_redactions_and_the_digest_of_what_it_kept(self) -> None:
        transcript = self.out / "session.txt"
        transcript.write_bytes(
            b"key sk-abcdefghijklmnop used\npassword: hunter2\nplain line \xff\n"
        )
        code, output = self.evolve(str(transcript), "--skill-name", "My Skill!",
                                   "--out-dir", str(self.out / "evo"))
        self.assertEqual(code, 0, output)
        proposal_path = self.out / "evo" / "my-skill.json"
        self.assertEqual(output.strip(), str(proposal_path))
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        clean = (self.out / "evo" / "my-skill.redacted.txt").read_text(encoding="utf-8")

        self.assertEqual(proposal["redactions"], 2)
        self.assertNotIn("sk-abcdefghijklmnop", clean)
        self.assertNotIn("hunter2", clean)
        self.assertEqual(clean.count("[REDACTED]"), 2)
        # Undecodable bytes are replaced, not fatal: transcripts are not curated.
        self.assertIn("plain line �", clean)
        # The digest covers the redacted text, so it never fingerprints a secret.
        self.assertEqual(proposal["source_sha256"], hashlib.sha256(clean.encode()).hexdigest())
        self.assertEqual(proposal["status"], "candidate")
        self.assertIs(proposal["human_review_required"], True)
        self.assertIn("human approval", proposal["regression_requirements"])

    def test_a_name_with_no_usable_characters_falls_back_to_a_placeholder(self) -> None:
        code, _ = self.evolve(str(self.transcript), "--skill-name", "!!!",
                              "--out-dir", str(self.out))
        self.assertEqual(code, 0)
        proposal = json.loads((self.out / "candidate-skill.json").read_text(encoding="utf-8"))
        self.assertEqual(proposal["skill_name"], "candidate-skill")

    def test_the_default_destination_is_under_the_root(self) -> None:
        code, output = self.evolve(str(self.transcript), "--skill-name", "parser")
        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), str(self.root / ".agtmls" / "evolution" / "parser.json"))


class RecordEvidenceTests(SessionToolBase):
    """record-evidence.py -- one JSON record per skill invocation."""

    def record(self, *args: str) -> tuple[int, str]:
        return run_main(self.module("record-evidence.py"), *args)

    def test_a_record_carries_the_skills_safety_policy_and_every_repeat_flag(self) -> None:
        code, output = self.record(
            "--skill", "alpha", "--out-dir", str(self.out),
            "--command", "make test", "--command", "make lint",
            "--file", "src/a.py", "--outcome", "passed",
        )
        self.assertEqual(code, 0, output)
        path = Path(output.strip())
        self.assertEqual(path.parent, self.out)
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(path.stem, record["run_id"])
        self.assertEqual(record["skill"], "alpha")
        self.assertEqual(record["commands"], ["make test", "make lint"])
        self.assertEqual(record["files"], ["src/a.py"])
        self.assertEqual(record["outcome"], "passed")
        self.assertEqual(record["safety_policy"], {"network_access": "none", "risk_level": "low"})

    def test_a_skill_without_a_policy_records_an_empty_one(self) -> None:
        code, output = self.record("--skill", "beta")
        self.assertEqual(code, 0, output)
        path = Path(output.strip())
        self.assertEqual(path.parent, self.root / ".agtmls" / "runs")
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(record["safety_policy"], {})
        self.assertEqual(record["outcome"], "recorded")
        self.assertEqual(record["commands"], [])

    def test_an_unknown_skill_is_refused_before_writing(self) -> None:
        code, output = self.record("--skill", "ghost", "--out-dir", str(self.out / "runs"))
        self.assertEqual(code, 1)
        self.assertIn("unknown skill: ghost", output)
        self.assertFalse((self.out / "runs").exists())


if __name__ == "__main__":
    unittest.main()
