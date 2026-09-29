#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Measure what a skill changes: each task run with and without it, per agent.

    run-uplift-evals.py --check
    run-uplift-evals.py --agent claude --agent codex --trials 5 --out results.json
    run-uplift-evals.py --render results.json

`--check` validates the cases and calls no model; the gate runs it. A run
spends real tokens on the agents' own logins, so it is never part of the
gate: it is run by hand, and its results file is the evidence a skill needs
before it is called hardened (evals/uplift/README.md).
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import (  # noqa: E402  (scripts path first)
    digest,
    skill_roots,
    uplift,
    uplift_agents,
)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate the cases; run nothing")
    mode.add_argument("--out", type=Path, help="run, and write the results here")
    mode.add_argument("--render", type=Path, help="print a results file as Markdown")
    parser.add_argument("--agent", action="append", choices=sorted(uplift_agents.AGENTS))
    parser.add_argument("--skill", action="append", help="only this skill's case (repeatable)")
    parser.add_argument("--trials", type=int, default=5, help="runs per arm per agent (default 5)")
    parser.add_argument("--jobs", type=int, default=1, help="runs at once (default 1)")
    parser.add_argument("--claude-model")
    parser.add_argument("--codex-model")
    parser.add_argument("--budget-usd", type=float, default=2.0, help="Claude's cap per run (default 2)")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per run (default 900)")
    parser.add_argument("--transcripts", type=Path, help="keep each run's raw output here")
    return parser.parse_args(argv)


def ignored_fixture_files() -> list[str]:
    """Fixture files git ignores. A run reads them from the working tree, but
    they never reach the commit, so the run cannot be reproduced from it: a
    global ignore rule once dropped a fixture's .claude/settings.local.json."""
    argv = ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--", uplift.FIXTURES.as_posix()]
    try:
        proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return []  # no git, as in a wheel install: nothing to compare against
    return [f"{line} is ignored by git and would not be committed; force-add it or rename it"
            for line in proc.stdout.splitlines() if line]


def load(only: list[str] | None) -> tuple[list[uplift.Case], list[str]]:
    names = {path.name for path in skill_roots.skill_dirs(ROOT)}
    cases, errors = uplift.load_cases(ROOT, names)
    errors += ignored_fixture_files()
    if only:
        unknown = sorted(set(only) - {case.skill for case in cases})
        errors += [f"no uplift case for {name}" for name in unknown]
        cases = [case for case in cases if case.skill in only]
    return cases, errors


def missing_agents(agents: list[str]) -> list[str]:
    errors = [f"{name} is not installed" for name in agents if shutil.which(name) is None]
    if "codex" in agents and not uplift_agents.codex_auth().is_file():
        errors.append("codex is not logged in (no auth.json)")
    return errors


def run_one(case: uplift.Case, agent_name: str, trial: int, arm: str, args: argparse.Namespace) -> dict:
    agent = uplift_agents.AGENTS[agent_name]
    model = getattr(args, f"{agent_name}_model")
    options = uplift_agents.Options(ROOT, model, args.budget_usd, args.timeout)
    skill_dir = skill_roots.find(ROOT, case.skill) if arm == "with" else None
    with uplift.workspace(case, skill_dir, agent.skills_dir) as work:
        outcome, seconds, raw = uplift_agents.run(agent, case.prompt, case.skill, work, options)
    if args.transcripts:
        args.transcripts.mkdir(parents=True, exist_ok=True)
        (args.transcripts / f"{case.skill}.{agent_name}.{arm}.{trial}.jsonl").write_text(raw, encoding="utf-8")
    hits = uplift.grade(case, outcome.answer)
    print(f"{case.skill} {agent_name} {arm} #{trial}: {len(hits)}/{len(case.expectations)}"
          f"{' ERROR ' + outcome.error if outcome.error else ''}", file=sys.stderr, flush=True)
    return {"skill": case.skill, "agent": agent_name, "arm": arm, "trial": trial, "hits": hits,
            "score": round(len(hits) / len(case.expectations), 3), "skill_used": outcome.skill_used,
            "tokens": outcome.tokens, "output_tokens": outcome.output_tokens, "cost_usd": outcome.cost_usd, "seconds": round(seconds, 1),
            "model": outcome.model, "error": outcome.error, "answer": outcome.answer}


def commit() -> str | None:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return proc.stdout.strip() or None


def meta(cases: list[uplift.Case], args: argparse.Namespace) -> dict:
    return {
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit(),
        "trials": args.trials,
        "agents": {name: getattr(args, f"{name}_model") for name in args.agent},
        "skills": {case.skill: digest.skill_digest(skill_roots.find(ROOT, case.skill)) for case in cases},
    }


def run(cases: list[uplift.Case], args: argparse.Namespace) -> int:
    by_skill = {case.skill: case for case in cases}
    plan = uplift.schedule(list(by_skill), args.agent, args.trials)
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        runs = list(pool.map(lambda item: run_one(by_skill[item[0]], *item[1:], args), plan))
    summary = uplift.summarise(cases, runs)
    results = {"meta": meta(cases, args), "summary": summary, "runs": runs}
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(uplift.render(summary), end="")
    return 0


def render(path: Path) -> int:
    try:
        results = json.loads(path.read_text(encoding="utf-8"))
        print(uplift.render(results["summary"]), end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {path}: not a results file: {exc}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.render:
        return render(args.render)
    cases, errors = load(args.skill)
    if not args.check:
        args.agent = args.agent or sorted(uplift_agents.AGENTS)
        errors += missing_agents(args.agent)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    if args.check:
        print(f"OK: {len(cases)} uplift case(s) valid")
        return 0
    return run(cases, args)


if __name__ == "__main__":
    sys.exit(main())
