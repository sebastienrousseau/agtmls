# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Does a skill change what an agent does? The same task, with and without it.

Routing evals prove a description attracts its prompts; behavioural evals
prove a SKILL.md still says what it must. Neither shows the skill helps. A
skill a model reads and then ignores, or that makes the agent worse, passes
both. This module runs one task twice per trial, once with the skill
installed and once without, and grades both answers the same way.

A case (`evals/uplift/cases/<skill>.json`) names a fixture with known flaws
planted in it, a prompt, and one expectation per flaw: a regular expression
the answer must match to count as having found it. Grading is deterministic,
so a delta is the agent's, not a judge's.

The fixture is copied to `repo/` inside a throwaway working directory, never
into the directory the agent runs in: a fixture holding a bad
`.claude/settings.json` must not configure the agent reading it.
"""

from __future__ import annotations

import json
import re
import shutil
import statistics
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

CASES = Path("evals/uplift/cases")
FIXTURES = Path("evals/uplift/fixtures")
ARMS = ("with", "without")
FIELDS = ("id", "means", "pattern")


class Expectation(NamedTuple):
    id: str
    means: str
    pattern: re.Pattern[str]


class Case(NamedTuple):
    skill: str
    fixture: Path
    prompt: str
    expectations: tuple[Expectation, ...]


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _expectation_problems(where: str, item: object, seen: set[str]) -> list[str]:
    if not isinstance(item, dict) or not all(_text(item.get(key)) for key in FIELDS):
        return [f"{where}: needs id, means and pattern strings"]
    errors = [f"{where}: duplicate id {item['id']!r}"] if item["id"] in seen else []
    seen.add(item["id"])
    try:
        re.compile(item["pattern"])
    except re.error as exc:
        errors.append(f"{where}: pattern does not compile: {exc}")
    return errors


def expectations_problems(label: str, items: object) -> list[str]:
    """A non-empty list of {id, means, pattern}, ids unique, patterns valid."""
    if not isinstance(items, list) or not items:
        return [f"{label}: expectations must be a non-empty list"]
    seen: set[str] = set()
    errors: list[str] = []
    for index, item in enumerate(items):
        errors += _expectation_problems(f"{label}: expectations[{index}]", item, seen)
    return errors


def _fixture_ok(root: Path, fixture: object) -> bool:
    # One directory name, so a case cannot point the copy anywhere else.
    return _text(fixture) and "/" not in fixture and not fixture.startswith(".") \
        and (root / FIXTURES / fixture).is_dir()


def case_problems(path: Path, case: object, root: Path, skills: set[str]) -> list[str]:
    """Why a loaded case file cannot be run, or []."""
    label = path.relative_to(root).as_posix()
    if not isinstance(case, dict):
        return [f"{label}: case must be a JSON object"]
    skill = case.get("skill")
    errors = []
    if not isinstance(skill, str) or skill not in skills:
        errors.append(f"{label}: unknown skill {skill!r}")
    if path.stem != skill:
        errors.append(f"{label}: filename must match skill")
    if not _fixture_ok(root, case.get("fixture")):
        errors.append(f"{label}: fixture must name a directory in {FIXTURES.as_posix()}")
    if not _text(case.get("prompt")):
        errors.append(f"{label}: prompt must be a non-empty string")
    return errors + expectations_problems(label, case.get("expectations"))


def _case(root: Path, raw: dict) -> Case:
    expectations = tuple(
        Expectation(item["id"], item["means"], re.compile(item["pattern"], re.IGNORECASE))
        for item in raw["expectations"]
    )
    return Case(raw["skill"], root / FIXTURES / raw["fixture"], raw["prompt"], expectations)


def load_cases(root: Path, skills: set[str]) -> tuple[list[Case], list[str]]:
    """Every case under `root`, and every reason one cannot run."""
    cases: list[Case] = []
    errors: list[str] = []
    for path in sorted((root / CASES).glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:  # bad JSON, or not UTF-8
            errors.append(f"{path.relative_to(root).as_posix()}: unreadable: {exc}")
            continue
        problems = case_problems(path, raw, root, skills)
        errors += problems
        if not problems:
            cases.append(_case(root, raw))
    if not cases and not errors:
        errors.append(f"no cases in {CASES.as_posix()}")
    return cases, errors


@contextmanager
def workspace(case: Case, skill_dir: Path | None, skills_dir: str) -> Iterator[Path]:
    """A throwaway working directory holding the fixture at `repo/`.

    With `skill_dir`, the skill is installed where the agent reads project
    skills (`skills_dir`, from providers.json). The directory's parent is
    private to the run; agents keep their isolated homes there.
    """
    top = Path(tempfile.mkdtemp(prefix="agtmls-uplift-"))
    try:
        work = top / "work"
        shutil.copytree(case.fixture, work / "repo", symlinks=True)
        if skill_dir is not None:
            shutil.copytree(skill_dir, work / skills_dir / skill_dir.name, symlinks=True)
        yield work
    finally:
        shutil.rmtree(top, ignore_errors=True)


def grade(case: Case, answer: str) -> list[str]:
    """The ids of the expectations the answer meets."""
    return [item.id for item in case.expectations if item.pattern.search(answer)]


def schedule(skills: list[str], agents: list[str], trials: int) -> list[tuple[str, str, int, str]]:
    """(skill, agent, trial, arm) for every run; arms alternate first by trial,
    so drift over a long run does not favour one arm."""
    runs = []
    for skill in skills:
        for agent in agents:
            for trial in range(trials):
                order = ARMS if trial % 2 == 0 else ARMS[::-1]
                runs += [(skill, agent, trial, arm) for arm in order]
    return runs


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 3) if values else None


def _mean_of(runs: list[dict], key: str) -> float | None:
    """The mean of a numeric field, over the runs that reported it."""
    return _mean([run[key] for run in runs if run[key] is not None])


def _arm(runs: list[dict], ids: list[str]) -> dict:
    ok = [run for run in runs if not run["error"]]
    return {
        "runs": len(runs),
        "errors": len(runs) - len(ok),
        "score": _mean_of(ok, "score"),
        "found": {key: _mean([float(key in run["hits"]) for run in ok]) for key in ids},
        "skill_used": _mean([float(run["skill_used"]) for run in ok]),
        "tokens": _mean_of(ok, "tokens"),
        "cost_usd": _mean_of(ok, "cost_usd"),
        "seconds": _mean_of(ok, "seconds"),
    }


def _row(skill: str, agent: str, runs: list[dict], ids: list[str]) -> dict:
    arms = {arm: _arm([run for run in runs if run["arm"] == arm], ids) for arm in ARMS}
    scores = (arms["with"]["score"], arms["without"]["score"])
    delta = None if None in scores else round(scores[0] - scores[1], 3)
    return {"skill": skill, "agent": agent, "delta": delta, **arms}


def summarise(cases: list[Case], runs: list[dict]) -> list[dict]:
    """Per skill and agent: each arm's mean score and per-flaw find rate, and
    the difference the skill made."""
    ids = {case.skill: [item.id for item in case.expectations] for case in cases}
    pairs = dict.fromkeys((run["skill"], run["agent"]) for run in runs)
    return [
        _row(skill, agent, [run for run in runs if (run["skill"], run["agent"]) == (skill, agent)], ids[skill])
        for skill, agent in pairs
    ]


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _flaw_table(rows: list[dict]) -> list[str]:
    """How often each arm found each planted flaw, for one skill."""
    columns = [(row, arm) for row in rows for arm in ARMS[::-1]]
    lines = [
        "",
        f"| {rows[0]['skill']} | " + " | ".join(f"{row['agent']} {arm}" for row, arm in columns) + " |",
        "| --- |" + " ---: |" * len(columns),
    ]
    for flaw in rows[0]["with"]["found"]:
        lines.append(f"| {flaw} | " + " | ".join(_pct(row[arm]["found"].get(flaw)) for row, arm in columns) + " |")
    return lines


def render(summary: list[dict]) -> str:
    """The summary as Markdown: one row per skill and agent, then each
    skill's planted flaws and how often each arm found them."""
    lines = [
        "| Skill | Agent | Without | With | Delta | Skill read | Errors |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary:
        without, with_ = row["without"], row["with"]
        delta = "n/a" if row["delta"] is None else f"{row['delta'] * 100:+.0f} pts"
        errors = without["errors"] + with_["errors"]
        lines.append(
            f"| {row['skill']} | {row['agent']} | {_pct(without['score'])} | {_pct(with_['score'])}"
            f" | {delta} | {_pct(with_['skill_used'])} | {errors} |"
        )
    for skill in dict.fromkeys(row["skill"] for row in summary):
        lines += _flaw_table([row for row in summary if row["skill"] == skill])
    return "\n".join(lines) + "\n"
