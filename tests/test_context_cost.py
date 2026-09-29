# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What an install puts in front of an agent in every session.

Skill descriptions and the prompt file are read in every session, used or
not. `doctor` reports that cost for an install, and `verify --live` warns
when the agent shows a description shorter than the skill's own: the
agent's listing budget is the real ceiling, so it is observed, not guessed.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT, load_script

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import context_cost, liveness  # needs the scripts path first


def _skill(root: Path, name: str, frontmatter: str) -> Path:
    path = root / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\n{frontmatter}\n---\n\n# {name}\n", encoding="utf-8")
    return path


class DescriptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agtmls-ctx-"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_quoted_forms_are_read_as_the_agent_reads_them(self) -> None:
        cases = {
            'description: "Use when \\"quoted\\" words matter."': 'Use when "quoted" words matter.',
            "description: 'Use when single-quoted.'": "Use when single-quoted.",
            "description: Use when plain.": "Use when plain.",
            'description: "broken \\q escape"': "broken \\q escape",
        }
        for index, (line, expected) in enumerate(cases.items()):
            self.assertEqual(context_cost.description(_skill(self.root, f"s{index}", line)), expected, line)

    def test_nothing_to_read_is_empty(self) -> None:
        self.assertEqual(context_cost.description(self.root / "absent" / "SKILL.md"), "")
        no_field = _skill(self.root, "bare", "license: MIT")
        self.assertEqual(context_cost.description(no_field), "")
        no_frontmatter = self.root / "raw" / "SKILL.md"
        no_frontmatter.parent.mkdir()
        no_frontmatter.write_text("# no frontmatter\n", encoding="utf-8")
        self.assertEqual(context_cost.description(no_frontmatter), "")
        (self.root / "bin" / "SKILL.md").parent.mkdir()
        (self.root / "bin" / "SKILL.md").write_bytes(b"\xff\xfe")
        self.assertEqual(context_cost.description(self.root / "bin" / "SKILL.md"), "")

    def test_install_cost_counts_names_descriptions_and_the_prompt(self) -> None:
        _skill(self.root, "ab", 'description: "12345678"')
        _skill(self.root, "cd", "description: 1234")
        prompt = self.root / "CLAUDE.md"
        prompt.write_text("x" * 40, encoding="utf-8")
        cost = context_cost.install_cost(self.root, ["ab", "cd"], prompt)
        self.assertEqual(cost, context_cost.Cost(2, 16, 40))
        self.assertEqual((context_cost.approx_tokens(cost.description_chars), context_cost.approx_tokens(41)), (4, 11))
        self.assertEqual(context_cost.install_cost(self.root, [], self.root / "none.md"), context_cost.Cost(0, 0, 0))

    def test_only_a_shorter_listing_is_reported(self) -> None:
        _skill(self.root, "full", 'description: "Use when the whole text is shown."')
        _skill(self.root, "cut", 'description: "Use when the listing budget runs out early."')
        listed = {"full": "Use when the whole  text is shown.", "cut": "Use when the listing…",
                  "unknown": None, "missing-file": "anything"}
        self.assertEqual(context_cost.shortened(self.root, listed), [("cut", 21, 43)])


CODEX_PROMPT = [{"type": "message", "content": [{"type": "input_text", "text": (
    "<skills_instructions> ## Skills\n### Available skills\n"
    "- agtmls:using-agtmls: Meta-router for the catalog. (file: r0/using-agtmls/SKILL.md)\n"
    "- imagegen: Images. (file: r1/imagegen/SKILL.md)\n</skills_instructions>")}]}]


class ListingTests(unittest.TestCase):
    def test_codex_listing_keeps_each_description(self) -> None:
        self.assertEqual(liveness.codex_listing(CODEX_PROMPT),
                         {"using-agtmls": "Meta-router for the catalog.", "imagegen": "Images."})

    def test_listed_skills_is_what_each_probe_reports(self) -> None:
        with mock.patch.dict(liveness.PROBES, {"claude-init": ("sh", lambda cwd: {"a": None})}):
            self.assertEqual(liveness.listed_skills({"live_probe": "claude-init"}, Path(".")), {"a": None})
            self.assertEqual(liveness.loaded_skills({"live_probe": "claude-init"}, Path(".")), {"a"})


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = load_script("agtmls.py")
        self.root = Path(tempfile.mkdtemp(prefix="agtmls-ctx-live-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        skills = self.root / ".codex" / "skills"
        _skill(skills, "one", 'description: "Use when the full text of one is needed."')
        lock = {"entries": [{"name": "one", "agents": ["codex"], "integrity": "sha256:x"}]}
        (self.root / ".agtmls").mkdir()
        (self.root / ".agtmls" / "manifest.json").write_text(json.dumps(lock), encoding="utf-8")

    def test_live_check_names_a_shortened_description(self) -> None:
        listed = {"one": "Use when the full…"}
        with mock.patch.object(self.cli.lockfile, "entries_for", return_value=[{"name": "one"}]), \
             mock.patch.object(liveness, "listed_skills", return_value=listed):
            result = self.cli.live_check(self.root, "codex")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["shortened"], [["one", 18, 40]])

    def test_print_live_warns_without_failing(self) -> None:
        from _lib import verify_report
        out = captured(verify_report.print_live, "codex",
                                   {"expected": 1, "missing": [], "shortened": [["one", 18, 40]]})
        self.assertIn("SHORTENED    one  codex shows 18 of 40 description characters", out)
        self.assertIn("OK: codex loads all 1 installed skill(s)", out)
        self.assertEqual(verify_report.with_live(0, {"missing": [], "shortened": [["one", 18, 40]]}), 0)


def captured(function, *args) -> str:
    """What `function` printed, on either stream."""
    import contextlib
    import io
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        function(*args)
    return buffer.getvalue()


class DoctorTests(unittest.TestCase):
    def test_doctor_reports_what_an_install_loads_every_session(self) -> None:
        doctor = load_script("agtmls-doctor.py")
        root = Path(tempfile.mkdtemp(prefix="agtmls-ctx-doc-"))
        self.addCleanup(shutil.rmtree, root, True)
        _skill(root / ".claude" / "skills", "one", 'description: "' + "d" * 397 + '"')
        (root / "CLAUDE.md").write_text("p" * 800, encoding="utf-8")
        reporter = doctor.Reporter()
        out = captured(doctor.check_context, reporter, root, ".claude", "CLAUDE.md")
        self.assertIn("context: 1 skill description(s), about 100 tokens, and CLAUDE.md,"
                      " about 200 tokens, load in every session", out)
        (root / "CLAUDE.md").unlink()
        out = captured(doctor.check_context, reporter, root, ".claude", "CLAUDE.md")
        self.assertIn("context: 1 skill description(s), about 100 tokens, load in every session (no CLAUDE.md)", out)
        self.assertIn("context: 0 skill description(s), about 0 tokens, load in every session (no CLAUDE.md)",
                      captured(doctor.check_context, reporter, root / "empty", ".claude", "CLAUDE.md"))



class CacheTests(unittest.TestCase):
    """A provider caches a repeated prompt prefix; text that changes every
    release or day in an always-loaded file breaks that prefix."""

    def test_dates_and_our_version_are_volatile_other_versions_are_not(self) -> None:
        text = "Released 2026-09-30 as v0.0.19 (0.0.19). Follows YAML 1.2.2; not 10.0.190."
        self.assertEqual(context_cost.volatile(text, "0.0.19"), ["2026-09-30", "v0.0.19", "0.0.19"])
        self.assertEqual(context_cost.volatile(text, None), ["2026-09-30"])
        self.assertEqual(context_cost.volatile_problems("x", "YAML 1.2.2", "0.0.19"), [])
        self.assertIn("x holds 2026-09-30, which changes", context_cost.volatile_problems("x", "on 2026-09-30", None)[0])

    def test_the_registry_version_is_read_or_absent(self) -> None:
        index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(context_cost.registry_version(ROOT), index["registry_version"])
        self.assertIsNone(context_cost.registry_version(ROOT / "no-such-dir"))

    def test_validate_skills_refuses_a_dated_description(self) -> None:
        validator = load_script("validate-skills.py")
        root = Path(tempfile.mkdtemp(prefix="agtmls-ctx-vs-"))
        self.addCleanup(shutil.rmtree, root, True)
        skill = _skill(root, "dated", 'description: "Use when the 2026-09-30 cutover is due."\nlicense: MIT')
        self.assertTrue(any("2026-09-30, which changes" in e for e in validator.check(skill)))

    def test_validate_system_prompts_refuses_our_version_in_a_prompt(self) -> None:
        validator = load_script("validate-system-prompts.py")
        prompts = Path(tempfile.mkdtemp(prefix="agtmls-ctx-sp-"))
        self.addCleanup(shutil.rmtree, prompts, True)
        version = context_cost.registry_version(ROOT)
        (prompts / "_base.md").write_text(f"# Base\n\nAgtMLS v{version} rules.\n", encoding="utf-8")
        (prompts / "python.md").write_text("# Python\n\nUpdated 2026-09-30.\n", encoding="utf-8")
        with mock.patch.object(validator, "PROMPTS", prompts):
            self.assertIn(f"v{version}", validator.base_problems()[0])
            self.assertIn("2026-09-30", validator.language_problems("python")[0])

    def test_the_adapter_says_what_to_put_first(self) -> None:
        text = load_script("export-registry.py").adapter_text("openai", None, 3)
        self.assertIn("Prompt caching:", text)
        self.assertIn("static text first", text)

if __name__ == "__main__":
    unittest.main()
