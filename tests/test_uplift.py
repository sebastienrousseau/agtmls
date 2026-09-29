# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The with/without-skill uplift runner, driven by fake agents.

A real run spends tokens, so the unit suite never makes one. Fake `claude`
and `codex` executables on PATH print what the real ones print (stream-json,
`codex exec --json`), read the skill only when it was installed, and answer
with more of the planted flaws when they did. That fixes every expected
grade in advance, so a runner that mixed up the arms, graded the wrong
answer or leaked the user's setup into a run would fail here.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT, load_script, run_main

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import uplift, uplift_agents  # needs the scripts path first

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "sleep":
    time.sleep(5)
skills = sorted(Path(".claude/skills").glob("*/SKILL.md"))
events = [{"type": "system", "subtype": "init", "model": "fake-claude", "skills": []}]
if skills:
    events.append({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "reading"},
        {"type": "tool_use", "name": "Read", "input": {"file_path": str(skills[0].resolve())}}]}})
answer = "Do not install it: curl | sh on start, the transcript is uploaded, acme-mcp@latest."
if skills:
    answer += " Pin the exact commit first."
if mode != "noresult":
    events.append({"type": "result", "subtype": "success", "is_error": False, "result": answer,
                   "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5, "service_tier": "x"}})
print("not json")
for event in events:
    print(json.dumps(event))
sys.exit(3 if mode == "exit" else 0)
'''

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
home = Path(os.environ["CODEX_HOME"])
assert (home / "auth.json").is_symlink(), "auth.json must be linked into the isolated home"
skills = sorted(Path(".codex/skills").glob("*/SKILL.md"))
print(json.dumps({"type": "thread.started"}))
if skills:
    print(json.dumps({"type": "item.completed", "item": {"type": "command_execution",
                      "command": "sed -n 1,200p " + str(skills[0])}}))
answer = "Refuse: it pipes a download into sh and posts the transcript; acme-mcp@latest."
answer += " Pin a 40-character commit." if skills else ""
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": answer}}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}}))
'''


def _executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class FakeAgents(unittest.TestCase):
    """Fake claude and codex first on PATH, and a fake Codex login."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-uplift-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        _executable(bin_dir / "claude", FAKE_CLAUDE)
        _executable(bin_dir / "codex", FAKE_CODEX)
        codex_home = self.tmp / "codex"
        codex_home.mkdir()
        (codex_home / "auth.json").write_text("{}", encoding="utf-8")
        env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "CODEX_HOME": str(codex_home)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)


def _case(root: Path, name: str, body: object) -> Path:
    path = root / uplift.CASES / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return path


GOOD = {"skill": "alpha", "fixture": "fx", "prompt": "Review ./repo.",
        "expectations": [{"id": "curl", "means": "the pipe", "pattern": r"curl \| sh"}]}


class CaseLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agtmls-uplift-cases-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        (self.root / uplift.FIXTURES / "fx").mkdir(parents=True)

    def load(self) -> tuple[list[uplift.Case], list[str]]:
        return uplift.load_cases(self.root, {"alpha", "beta"})

    def test_a_good_case_loads_with_compiled_case_blind_patterns(self) -> None:
        _case(self.root, "alpha", GOOD)
        cases, errors = self.load()
        self.assertEqual(errors, [])
        self.assertEqual(cases[0].fixture, self.root / uplift.FIXTURES / "fx")
        self.assertEqual(uplift.grade(cases[0], "run CURL | SH now"), ["curl"])

    def test_no_cases_is_an_error(self) -> None:
        self.assertEqual(self.load(), ([], ["no cases in evals/uplift/cases"]))

    def test_each_broken_field_is_named(self) -> None:
        _case(self.root, "alpha", {"skill": "gamma", "fixture": "../fx", "prompt": " ", "expectations": []})
        _case(self.root, "beta", {**GOOD, "skill": "beta", "fixture": ".hidden", "expectations": [
            "x", {"id": "a", "means": "m", "pattern": "("}, {"id": "a", "means": "m", "pattern": "b"}]})
        _, errors = self.load()
        text = "\n".join(errors)
        for needle in ("unknown skill 'gamma'", "filename must match skill", "fixture must name",
                       "prompt must be", "expectations must be a non-empty list",
                       "expectations[0]: needs id, means and pattern", "does not compile",
                       "expectations[2]: duplicate id 'a'"):
            self.assertIn(needle, text)
        self.assertEqual(text.count("fixture must name"), 2)

    def test_unreadable_and_non_object_cases(self) -> None:
        _case(self.root, "alpha", "{not json")
        _case(self.root, "beta", "[1]")
        (self.root / uplift.CASES / "gamma.json").write_bytes(b"\xff\xfe")
        _, errors = self.load()
        self.assertEqual(len(errors), 3)
        self.assertIn("alpha.json: unreadable", errors[0])
        self.assertIn("beta.json: case must be a JSON object", errors[1])
        self.assertIn("gamma.json: unreadable", errors[2])

    def test_missing_fixture_directory(self) -> None:
        _case(self.root, "alpha", {**GOOD, "fixture": "absent"})
        self.assertIn("fixture must name", self.load()[1][0])


class WorkspaceAndScheduleTests(unittest.TestCase):
    def test_fixture_goes_under_repo_and_the_skill_only_in_the_with_arm(self) -> None:
        case = uplift.Case("vetting-a-skill-before-install", ROOT / uplift.FIXTURES / "acme-skills", "p", ())
        skill = ROOT / "skills" / "vetting-a-skill-before-install"
        with uplift.workspace(case, skill, ".claude/skills") as work:
            self.assertTrue((work / "repo" / "hooks" / "hooks.json").is_file())
            self.assertTrue((work / ".claude/skills/vetting-a-skill-before-install/SKILL.md").is_file())
            # The fixture's own agent config is under repo/, never where the agent runs.
            self.assertFalse((work / ".mcp.json").exists())
        self.assertFalse(work.parent.exists())
        with uplift.workspace(case, None, ".claude/skills") as work:
            self.assertFalse((work / ".claude").exists())

    def test_arms_alternate_which_runs_first(self) -> None:
        plan = uplift.schedule(["s"], ["claude"], 3)
        self.assertEqual([arm for *_, arm in plan], ["with", "without", "without", "with", "with", "without"])
        self.assertEqual(len(uplift.schedule(["a", "b"], ["claude", "codex"], 5)), 40)


def _run(arm: str, hits: list[str], error: str | None = None, **extra) -> dict:
    return {"skill": "s", "agent": "claude", "arm": arm, "hits": hits, "score": len(hits) / 2,
            "skill_used": arm == "with", "tokens": 100, "cost_usd": 0.5, "seconds": 3.0,
            "error": error, **extra}


class SummaryTests(unittest.TestCase):
    CASE = uplift.Case("s", Path("."), "p", (uplift.Expectation("a", "", None), uplift.Expectation("b", "", None)))

    def test_delta_found_rates_and_errors(self) -> None:
        runs = [_run("with", ["a", "b"]), _run("with", ["a"]), _run("with", [], error="boom"),
                _run("without", ["a"], tokens=None, cost_usd=None)]
        (row,) = uplift.summarise([self.CASE], runs)
        self.assertEqual(row["delta"], 0.25)
        self.assertEqual((row["with"]["runs"], row["with"]["errors"]), (3, 1))
        self.assertEqual(row["with"]["found"], {"a": 1.0, "b": 0.5})
        self.assertEqual(row["without"]["tokens"], None)
        text = uplift.render([row])
        self.assertIn("| s | claude | 50% | 75% | +25 pts | n/a | 100% | 1 | no token data |", text)
        self.assertIn("| b | 0% | 50% |", text)
        with_tokens = uplift.summarise([self.CASE], [_run("with", ["a"], tokens=300), _run("without", ["a"])])
        self.assertIn("| +0 pts | 3.00x | 100% | 0 | no gain |", uplift.render(with_tokens))

    def test_an_arm_with_only_errors_has_no_delta(self) -> None:
        (row,) = uplift.summarise([self.CASE], [_run("with", ["a"]), _run("without", [], error="x")])
        self.assertIsNone(row["delta"])
        self.assertIn("| s | claude | n/a | 50% | n/a | n/a | 100% | 1 | no data |", uplift.render([row]))


class VerdictTests(unittest.TestCase):
    """A skill helps on an agent when it gains, within the token ceiling:
    at most 1.5x the tokens, unless it gains 20 points or more."""

    @staticmethod
    def row(delta: float | None, with_tokens: float | None, without_tokens: float | None = 100.0) -> dict:
        return {"delta": delta, "with": {"tokens": with_tokens}, "without": {"tokens": without_tokens}}

    def test_each_verdict(self) -> None:
        cases = [
            (self.row(0.1, 150.0), "helps"),            # exactly at the ceiling
            (self.row(0.1, 151.0), "too costly"),       # over it, small gain
            (self.row(0.2, 400.0), "helps"),            # over it, but a large gain pays
            (self.row(0.19, 400.0), "too costly"),
            (self.row(0.0, 90.0), "no gain"),
            (self.row(-0.1, 90.0), "no gain"),
            (self.row(None, 90.0), "no data"),
            (self.row(0.1, None), "no token data"),
            (self.row(0.1, 90.0, None), "no token data"),
        ]
        for row, expected in cases:
            self.assertEqual(uplift.verdict(row), expected, row)

    def test_hardened_needs_two_agents_that_help(self) -> None:
        rows = [{"skill": "a", "verdict": "helps"}, {"skill": "a", "verdict": "helps"},
                {"skill": "b", "verdict": "helps"}, {"skill": "b", "verdict": "too costly"}]
        self.assertEqual(uplift.meets_hardened(rows), ["a"])


class ParseTests(unittest.TestCase):
    OPTIONS = uplift_agents.Options(ROOT, "m")

    def test_claude_counts_the_skill_tool_and_reports_errors(self) -> None:
        events = [{"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "name": "Skill", "input": {"skill": "other"}},
                      {"type": "tool_use", "name": "Skill", "input": {"skill": "s"}}]}},
                  {"type": "assistant", "message": {"content": "plain"}},
                  {"type": "result", "subtype": "error_max_turns", "is_error": True, "result": None}]
        out = uplift_agents.AGENTS["claude"].parse("\n".join(map(json.dumps, events)) + "\n[1]", "s", self.OPTIONS)
        self.assertEqual((out.answer, out.skill_used, out.tokens, out.model), ("", True, None, "m"))
        self.assertEqual(out.error, "claude: error_max_turns")

    def test_claude_without_a_result(self) -> None:
        self.assertEqual(uplift_agents.AGENTS["claude"].parse("", "s", self.OPTIONS).error, "claude printed no result")

    def test_claude_command_passes_the_model_only_when_given(self) -> None:
        argv, env = uplift_agents.AGENTS["claude"].command("p", Path("."), self.OPTIONS)
        self.assertEqual((argv[-2:], env), (["--model", "m"], {}))
        self.assertIn("--strict-mcp-config", argv)
        self.assertNotIn("--model", uplift_agents.AGENTS["claude"].command("p", Path("."), uplift_agents.Options(ROOT))[0])

    def test_codex_errors_and_silence(self) -> None:
        failed = [{"type": "turn.failed", "error": {"message": "quota"}}]
        self.assertEqual(uplift_agents.AGENTS["codex"].parse(json.dumps(failed[0]), "s", self.OPTIONS).error, "codex: quota")
        error = json.dumps({"type": "error", "message": "bad"})
        self.assertEqual(uplift_agents.AGENTS["codex"].parse(error, "s", self.OPTIONS).error, "codex: bad")
        silent = uplift_agents.AGENTS["codex"].parse(json.dumps({"type": "turn.completed"}), "s", uplift_agents.Options(ROOT))
        self.assertEqual((silent.error, silent.tokens, silent.model), ("codex printed no answer", None, "codex default"))

    def test_codex_auth_follows_codex_home(self) -> None:
        with mock.patch.dict(os.environ, {"CODEX_HOME": "/x"}):
            self.assertEqual(uplift_agents.codex_auth(), Path("/x/auth.json"))
        with mock.patch.dict(os.environ, {"CODEX_HOME": ""}), mock.patch.object(Path, "home", return_value=Path("/h")):
            self.assertEqual(uplift_agents.codex_auth(), Path("/h/.codex/auth.json"))


class RunTests(FakeAgents):
    CASE = uplift.Case("vetting-a-skill-before-install", ROOT / uplift.FIXTURES / "acme-skills", "p", ())

    def outcome(self, agent: str, arm: str, **options) -> tuple[uplift_agents.Outcome, float, str]:
        chosen = uplift_agents.AGENTS[agent]
        skill = ROOT / "skills" / self.CASE.skill if arm == "with" else None
        with uplift.workspace(self.CASE, skill, chosen.skills_dir) as work:
            return uplift_agents.run(chosen, "p", self.CASE.skill, work,
                                     uplift_agents.Options(ROOT, **options))

    def test_each_agent_reads_the_skill_only_when_installed(self) -> None:
        for agent in uplift_agents.AGENTS:
            with_skill, _, raw = self.outcome(agent, "with")
            without, _, _ = self.outcome(agent, "without")
            self.assertEqual((with_skill.skill_used, without.skill_used, with_skill.error), (True, False, None), agent)
            self.assertIn("commit", with_skill.answer)
            self.assertNotIn("commit", without.answer)
            self.assertEqual(with_skill.tokens, 15 if agent == "claude" else 10)
            self.assertTrue(raw)

    def test_the_agtmls_on_path_is_this_checkout(self) -> None:
        with uplift.workspace(self.CASE, None, ".claude/skills") as work:
            shim = uplift_agents.agtmls_shim(work, ROOT) / "agtmls"
            self.assertIn(str(ROOT / "scripts" / "agtmls.py"), shim.read_text(encoding="utf-8"))
            self.assertTrue(os.access(shim, os.X_OK))

    def test_a_non_zero_exit_and_a_timeout_are_errors(self) -> None:
        with mock.patch.dict(os.environ, {"FAKE_MODE": "exit"}):
            self.assertEqual(self.outcome("claude", "without")[0].error, "claude exited 3")
        with mock.patch.dict(os.environ, {"FAKE_MODE": "sleep"}):
            self.assertEqual(self.outcome("claude", "without", timeout=1)[0].error, "timed out after 1s")


class ScriptTests(FakeAgents):
    def setUp(self) -> None:
        super().setUp()
        self.script = load_script("run-uplift-evals.py")

    def test_check_validates_the_real_cases(self) -> None:
        code, out = run_main(self.script, "--check")
        self.assertEqual((code, out.strip()), (0, "OK: 2 uplift case(s) valid"))

    def test_an_unknown_skill_fails(self) -> None:
        code, out = run_main(self.script, "--check", "--skill", "nope")
        self.assertEqual((code, out.strip()), (1, "FAIL: no uplift case for nope"))

    def test_a_run_writes_results_and_renders_them(self) -> None:
        out, transcripts = self.tmp / "results.json", self.tmp / "tx"
        code, text = run_main(self.script, "--out", str(out), "--skill", "vetting-a-skill-before-install",
                              "--trials", "2", "--jobs", "2", "--transcripts", str(transcripts))
        self.assertEqual(code, 0, text)
        results = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(results["runs"]), 8)
        self.assertEqual(set(results["meta"]["agents"]), {"claude", "codex"})
        self.assertRegex(results["meta"]["skills"]["vetting-a-skill-before-install"], r"^sha256:")
        by_arm = {(row["agent"]): row for row in results["summary"]}
        self.assertEqual((by_arm["claude"]["without"]["score"], by_arm["claude"]["with"]["score"]), (0.8, 1.0))
        self.assertEqual(by_arm["codex"]["delta"], 0.2)
        self.assertEqual(len(list(transcripts.iterdir())), 8)
        self.assertEqual(run_main(self.script, "--render", str(out))[1], uplift.render(results["summary"]))

    def test_a_run_without_transcripts_keeps_none(self) -> None:
        out = self.tmp / "one.json"
        code, _ = run_main(self.script, "--out", str(out), "--agent", "claude", "--trials", "1",
                           "--skill", "authoring-portable-skills", "--claude-model", "m")
        self.assertEqual(code, 0)
        results = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual((len(results["runs"]), results["meta"]["agents"]), (2, {"claude": "m"}))
        self.assertEqual(sorted(path.name for path in self.tmp.iterdir()), ["bin", "codex", "one.json"])

    def test_render_refuses_a_file_that_is_not_results(self) -> None:
        bad = self.tmp / "bad.json"
        bad.write_text("[]", encoding="utf-8")
        code, out = run_main(self.script, "--render", str(bad))
        self.assertEqual(code, 1)
        self.assertIn("not a results file", out)

    def test_a_missing_agent_or_login_stops_the_run(self) -> None:
        os.environ["CODEX_HOME"] = str(self.tmp / "nowhere")
        with mock.patch.object(self.script.shutil, "which", return_value=None):
            code, out = run_main(self.script, "--out", str(self.tmp / "r.json"))
        self.assertEqual(code, 1)
        for needle in ("claude is not installed", "codex is not installed", "codex is not logged in"):
            self.assertIn(needle, out)


if __name__ == "__main__":
    unittest.main()
