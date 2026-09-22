# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The eval runners and the schema check that feeds them, driven to failure.

The gate runs `run-trigger-evals.py`, `run-behavioral-evals.py`,
`validate-eval-cases.py` and `check-skill-collisions.py` once each, against a
registry that passes. That shows they can say OK. An eval runner that can only
say OK is a routing regression waiting to ship, so each case here builds a
small registry, confirms the runner accepts it, then breaks one thing and
requires the runner to say which.

The registry is synthetic rather than a copy of the real one: the runners only
read `skills/` and `evals/`, and five hand-written skills make every expected
ranking and similarity knowable in advance. A copy of the whole tree would
cost two seconds per class and prove less.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from .support import load_script, retarget, run_main

# Five skills chosen to reach every branch of the description extractor both
# runners share: a folded multi-line value followed by another key, a value
# that is the last key in the block, a nested bundle directory, a file with no
# frontmatter and a frontmatter with no description.
SKILLS = {
    "skills/yaml-anchors/SKILL.md": (
        "---\nname: yaml-anchors\n"
        "description: Use when parsing yaml anchors and aliases in documents.\n"
        "license: MIT\n---\n\n# YAML anchors\n\nResolve every alias.\n"
    ),
    "skills/yaml-anchors/reference.md": "# Reference\n\nThe anchor table lists each alias.\n",
    "skills/bundle/rust-port/SKILL.md": (
        "---\nname: rust-port\ndescription: >-\n  Use when porting rust code\n"
        "  to python with a golden harness.\nlicense: MIT\n---\n\n# Port\n\nbody\n"
    ),
    "skills/release-notes/SKILL.md": (
        "---\nname: release-notes\n"
        "description: Use when writing release notes and changelog entries for tags.\n"
        "---\n\n# Notes\n\nbody\n"
    ),
    "skills/no-frontmatter/SKILL.md": "# Missing frontmatter\n\nbody\n",
    "skills/no-description/SKILL.md": "---\nname: no-description\n---\n\n# Bare\n\nbody\n",
}
NAMES = sorted(
    ["yaml-anchors", "rust-port", "release-notes", "no-frontmatter", "no-description"]
)

# Negatives are prompts that clearly belong to a *different* skill, so the
# owner can never rank first. A prompt with no vocabulary at all would tie
# every skill at zero and put the alphabetically last one on top.
ROUTING = {
    "yaml-anchors": {"positive": ["parse yaml anchors"], "negative": ["port rust code"]},
    "rust-port": {"positive": ["port rust to python"], "negative": ["yaml aliases"]},
    "release-notes": {"positive": ["write changelog notes"], "negative": ["yaml anchors"]},
    "no-frontmatter": {"positive": ["anything"], "negative": ["yaml anchors"]},
    "no-description": {"positive": ["anything"], "negative": ["yaml anchors"]},
}

BEHAVIORAL = {
    "yaml-anchors": {
        "requires": {
            "files_exist": ["reference.md"],
            "skill_contains": ["Resolve every alias"],
            "reference_contains": ["anchor table"],
        },
        "forbids": {"skill_contains": ["TODO"]},
    },
    **{name: {"requires": {"files_exist": ["SKILL.md"]}} for name in NAMES if name != "yaml-anchors"},
}


def build_registry(root: Path) -> Path:
    """Write the synthetic registry: skills plus a passing case for each."""
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    for relative, text in SKILLS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    routing = root / "evals" / "cases"
    behavioral = root / "evals" / "behavioral" / "cases"
    routing.mkdir(parents=True)
    behavioral.mkdir(parents=True)
    for name, case in ROUTING.items():
        (routing / f"{name}.json").write_text(json.dumps({"skill": name, **case}), encoding="utf-8")
    for name, case in BEHAVIORAL.items():
        (behavioral / f"{name}.json").write_text(json.dumps({"skill": name, **case}), encoding="utf-8")
    return root


class RegistryBase(unittest.TestCase):
    """One synthetic registry per class; every test restores what it broke."""

    fixture: Path
    script: str

    @classmethod
    def setUpClass(cls) -> None:
        cls._workspace = tempfile.mkdtemp(prefix="agtmls-evals-")
        cls.fixture = build_registry(Path(cls._workspace) / "tree")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def restore_later(self, relative: str) -> Path:
        path = self.fixture / relative
        original = path.read_bytes() if path.is_file() else None

        def restore() -> None:
            if original is None:
                if path.is_file():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)

        self.addCleanup(restore)
        return path

    def write_json(self, relative: str, payload) -> None:
        path = self.restore_later(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = payload if isinstance(payload, str) else json.dumps(payload)
        path.write_text(text, encoding="utf-8")

    def hide_directory(self, relative: str) -> None:
        """Move a directory aside for one test and put it back afterwards."""
        path = self.fixture / relative
        aside = path.with_name(path.name + ".aside")
        path.rename(aside)
        self.addCleanup(aside.rename, path)

    def module(self):
        module = load_script(self.script)
        retarget(module, self.fixture)
        return module

    def run_script(self, *args: str, module=None) -> tuple[int, str]:
        return run_main(module or self.module(), *args)


class BehavioralEvalTests(RegistryBase):
    """run-behavioral-evals.py -- the contract each skill promises to keep.

    A behavioral case pins text a skill must (or must not) contain. If the
    runner stopped reading any one kind of requirement, every case of that
    kind would pass vacuously and the gate would still say OK.
    """

    script = "run-behavioral-evals.py"
    CASE = "evals/behavioral/cases/yaml-anchors.json"

    def break_case(self, **changes) -> str:
        case = {"skill": "yaml-anchors", **BEHAVIORAL["yaml-anchors"], **changes}
        self.write_json(self.CASE, case)
        code, output = self.run_script()
        self.assertEqual(code, 1, output)
        return output

    def test_a_registry_that_keeps_its_contracts_passes_with_a_count(self) -> None:
        # yaml-anchors contributes four checks, the other four skills one each.
        code, output = self.run_script()
        self.assertEqual(code, 0, output)
        self.assertIn("OK: 8 behavioral checks passed across 5 case file(s)", output)

    def test_no_cases_directory_is_reported_rather_than_passed_silently(self) -> None:
        self.hide_directory("evals/behavioral/cases")
        code, output = self.run_script()
        self.assertEqual(code, 0)
        self.assertIn("nothing to check", output)

    def test_a_case_for_an_unknown_skill_is_caught(self) -> None:
        self.write_json("evals/behavioral/cases/ghost.json", {"skill": "ghost", "requires": {}})
        code, output = self.run_script()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: ghost.json: unknown skill 'ghost'", output)
        self.assertIn("FAIL: 1 behavioral issue(s) across 6 case file(s)", output)

    def test_a_missing_required_file_is_caught(self) -> None:
        output = self.break_case(requires={"files_exist": ["scripts/run.sh"]})
        self.assertIn("required file missing: scripts/run.sh", output)

    def test_a_missing_skill_phrase_is_caught(self) -> None:
        output = self.break_case(requires={"skill_contains": ["Never resolve aliases"]})
        self.assertIn("SKILL.md missing 'Never resolve aliases'", output)

    def test_a_phrase_only_in_the_skill_does_not_satisfy_a_reference_requirement(self) -> None:
        """reference_contains reads reference*.md, not SKILL.md."""
        output = self.break_case(requires={"reference_contains": ["Resolve every alias"]})
        self.assertIn("reference.md missing 'Resolve every alias'", output)

    def test_a_forbidden_phrase_in_the_skill_is_caught(self) -> None:
        output = self.break_case(forbids={"skill_contains": ["Resolve every alias"]})
        self.assertIn("SKILL.md contains forbidden 'Resolve every alias'", output)

    def test_a_forbidden_phrase_in_the_reference_is_caught(self) -> None:
        """validate-eval-cases.py accepts forbids.reference_contains, and the
        runner never read it: a case could forbid a phrase that was present
        and still pass."""
        output = self.break_case(forbids={"reference_contains": ["anchor table"]})
        self.assertIn("reference.md contains forbidden 'anchor table'", output)


class TriggerEvalTests(RegistryBase):
    """run-trigger-evals.py -- does each description still attract its prompts?

    The two directions fail differently: a positive that drifts out of the
    top-K means a skill has stopped being found, a negative ranked first means
    it has started stealing another skill's prompts.
    """

    script = "run-trigger-evals.py"

    def test_a_registry_whose_prompts_route_correctly_passes(self) -> None:
        code, output = self.run_script()
        self.assertEqual(code, 0, output)
        self.assertIn("OK: 10 routing checks passed across 5 case file(s)", output)

    def test_no_cases_directory_is_reported_rather_than_passed_silently(self) -> None:
        self.hide_directory("evals/cases")
        code, output = self.run_script()
        self.assertEqual(code, 0)
        self.assertIn("nothing to check", output)

    def test_a_positive_prompt_that_routes_elsewhere_is_caught(self) -> None:
        # TOP_K narrowed to 1: with five skills every one is in the default top
        # 5. At 1 the two description-less skills fail too, which is correct:
        # a skill with no description can never be ranked first on merit.
        self.write_json(
            "evals/cases/rust-port.json",
            {"skill": "rust-port", "positive": ["parse yaml anchors"], "negative": ["yaml aliases"]},
        )
        module = self.module()
        module.TOP_K = 1
        code, output = self.run_script(module=module)
        self.assertEqual(code, 1)
        self.assertIn("[rust-port] positive not in top-1: 'parse yaml anchors'", output)
        self.assertIn("FAIL: 3/10 routing checks failed across 5 case file(s)", output)

    def test_a_negative_prompt_the_skill_wins_is_caught(self) -> None:
        self.write_json(
            "evals/cases/yaml-anchors.json",
            {"skill": "yaml-anchors", "positive": ["yaml"], "negative": ["yaml anchors and aliases"]},
        )
        code, output = self.run_script()
        self.assertEqual(code, 1)
        self.assertIn("[yaml-anchors] negative ranked #1", output)

    def test_a_case_for_an_unknown_skill_is_caught(self) -> None:
        self.write_json("evals/cases/ghost.json", {"skill": "ghost", "positive": ["x"]})
        code, output = self.run_script()
        self.assertEqual(code, 1)
        self.assertIn("ghost.json: unknown skill 'ghost'", output)

    def test_a_folded_description_is_read_across_its_continuation_lines(self) -> None:
        """The second line of a `>-` value carries half the routing vocabulary."""
        module = self.module()
        text = module.description_of(self.fixture / "skills/bundle/rust-port/SKILL.md")
        self.assertIn("golden harness", text)
        self.assertNotIn("MIT", text)

    def test_skills_with_no_description_contribute_an_empty_one(self) -> None:
        module = self.module()
        for name in ("no-frontmatter", "no-description"):
            self.assertEqual(module.description_of(self.fixture / f"skills/{name}/SKILL.md"), "")


class EvalSchemaTests(RegistryBase):
    """validate-eval-cases.py -- the schema both runners trust without checking.

    A runner skips keys it does not know and treats a missing case file as
    nothing to do, so a typo in a case or a skill with no case at all passes
    the runner. This is the check that notices.
    """

    script = "validate-eval-cases.py"
    BEHAVIORAL_CASE = "evals/behavioral/cases/yaml-anchors.json"

    def failures(self) -> str:
        code, output = self.run_script()
        self.assertEqual(code, 1, output)
        return output

    def test_a_complete_registry_passes(self) -> None:
        code, output = self.run_script()
        self.assertEqual(code, 0, output)
        self.assertIn("OK: eval schemas valid for 5 skill(s)", output)

    def test_a_second_routing_case_for_the_same_skill_is_caught(self) -> None:
        self.write_json("evals/cases/zzz.json", {"skill": "rust-port", **ROUTING["rust-port"]})
        output = self.failures()
        self.assertIn("evals/cases/zzz.json: duplicate routing case for rust-port", output)
        self.assertIn("evals/cases/zzz.json: filename must match skill", output)

    def test_a_routing_case_that_cannot_be_used_is_caught(self) -> None:
        self.write_json("evals/cases/yaml-anchors.json", "{not json")
        self.write_json("evals/cases/ghost.json", {"skill": "ghost", "positive": [], "negative": "x"})
        output = self.failures()
        self.assertIn("evals/cases/yaml-anchors.json: invalid JSON", output)
        self.assertIn("evals/cases/ghost.json: unknown skill 'ghost'", output)
        self.assertIn("ghost.json: positive must be a non-empty string list", output)
        self.assertIn("ghost.json: negative must be a non-empty string list", output)
        # The unparseable file no longer counts as yaml-anchors' case.
        self.assertIn("missing routing cases: yaml-anchors", output)

    def test_a_skill_without_a_behavioral_case_is_caught(self) -> None:
        self.restore_later("evals/behavioral/cases/rust-port.json").unlink()
        self.assertIn("missing behavioral cases: rust-port", self.failures())

    def test_an_unparseable_behavioral_case_is_caught(self) -> None:
        self.write_json(self.BEHAVIORAL_CASE, "{not json")
        self.assertIn("yaml-anchors.json: invalid JSON", self.failures())

    def test_a_behavioral_case_for_an_unknown_misnamed_duplicate_skill_is_caught(self) -> None:
        self.write_json(
            "evals/behavioral/cases/zzz.json",
            {"skill": "ghost", "requires": {"files_exist": ["SKILL.md"]}},
        )
        self.write_json(
            "evals/behavioral/cases/zzzz.json",
            {"skill": "ghost", "requires": {"files_exist": ["SKILL.md"]}},
        )
        output = self.failures()
        self.assertIn("zzz.json: unknown skill 'ghost'", output)
        self.assertIn("zzz.json: filename must match skill", output)
        self.assertIn("zzzz.json: duplicate behavioral case for ghost", output)

    def test_empty_or_malformed_requires_and_forbids_are_caught(self) -> None:
        self.write_json(self.BEHAVIORAL_CASE, {"skill": "yaml-anchors", "requires": {}, "forbids": []})
        output = self.failures()
        self.assertIn("requires must be a non-empty object", output)
        self.assertIn("forbids must be an object", output)

    def test_unknown_keys_and_non_string_values_are_caught(self) -> None:
        self.write_json(
            self.BEHAVIORAL_CASE,
            {
                "skill": "yaml-anchors",
                "requires": {"skill_mentions": ["x"], "files_exist": []},
                "forbids": {"files_exist": ["x"], "skill_contains": [""]},
            },
        )
        output = self.failures()
        self.assertIn("unsupported requires key 'skill_mentions'", output)
        self.assertIn("requires.files_exist must be a non-empty string list", output)
        self.assertIn("unsupported forbids key 'files_exist'", output)
        self.assertIn("forbids.skill_contains must be a string list", output)
        self.assertIn("FAIL: 4 eval schema issue(s)", output)

    def test_an_empty_forbids_list_is_allowed(self) -> None:
        """forbids is optional content; only requires must say something."""
        self.write_json(
            self.BEHAVIORAL_CASE,
            {"skill": "yaml-anchors", "requires": {"files_exist": ["SKILL.md"]}, "forbids": {"skill_contains": []}},
        )
        code, output = self.run_script()
        self.assertEqual(code, 0, output)


class CollisionRunnerTests(RegistryBase):
    """check-skill-collisions.py, run end to end over a registry.

    The pairwise math is covered in test_skill_contract.py. What is not is the
    band between the thresholds: a pair above WARN_AT but below FAIL_AT must be
    reported and must not fail the gate, or every near-miss would block a
    release and the warning would be switched off.
    """

    script = "check-skill-collisions.py"

    def test_distinct_descriptions_pass_without_a_warning(self) -> None:
        code, output = self.run_script()
        self.assertEqual(code, 0, output)
        self.assertIn("Top description similarities (5 skills):", output)
        self.assertNotIn("WARN:", output)
        self.assertIn("OK: no description collisions above the fail threshold", output)

    def test_a_pair_between_the_thresholds_warns_but_passes(self) -> None:
        path = self.restore_later("skills/release-notes/SKILL.md")
        path.write_text(
            "---\nname: release-notes\n"
            "description: Use when parsing yaml anchors and aliases in changelog notes.\n"
            "---\n\n# N\n",
            encoding="utf-8",
        )
        module = self.module()
        code, output = self.run_script(module=module)
        self.assertEqual(code, 0, output)
        line = next(item for item in output.splitlines() if "[warn]" in item)
        score = float(line.split()[0])
        self.assertGreaterEqual(score, module.WARN_AT)
        self.assertLess(score, module.FAIL_AT)
        self.assertIn("release-notes  <->  yaml-anchors", line)
        self.assertIn("WARN: 1 pair(s) >= 0.50 (advisory)", output)

    def test_a_pair_above_the_fail_threshold_fails_and_is_named(self) -> None:
        path = self.restore_later("skills/release-notes/SKILL.md")
        path.write_text(
            "---\nname: release-notes\n"
            "description: Use when parsing yaml anchors and aliases in documents.\n"
            "---\n\n# N\n",
            encoding="utf-8",
        )
        code, output = self.run_script()
        self.assertEqual(code, 1, output)
        self.assertIn("1.00 [FAIL]  release-notes  <->  yaml-anchors", output)
        self.assertIn("FAIL: 1 pair(s) >= 0.75", output)
        self.assertNotIn("OK:", output)

    def test_descriptions_are_extracted_the_same_way_the_router_reads_them(self) -> None:
        module = self.module()

        def read(relative: str) -> str:
            text = (self.fixture / relative).read_text(encoding="utf-8")
            return module.frontmatter_description(text)

        self.assertEqual(
            read("skills/bundle/rust-port/SKILL.md"),
            "Use when porting rust code to python with a golden harness.",
        )
        self.assertEqual(read("skills/no-frontmatter/SKILL.md"), "")
        self.assertEqual(read("skills/no-description/SKILL.md"), "")


if __name__ == "__main__":
    unittest.main()
