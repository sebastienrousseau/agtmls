# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Run one uplift task in one agent, isolated from the user's own setup.

Both arms must see the same agent. A user's own skills, instructions and
MCP servers would reach both, and some overlap the skill being measured
(`ai-supply-chain-security` and `vetting-a-skill-before-install`, say), so
they are shut out:

* Claude Code loads project settings only (`--setting-sources project`), so
  no user-level skills, CLAUDE.md or hooks, and no MCP servers
  (`--strict-mcp-config`). Its own login still works, which a separate HOME
  would lose.
* Codex gets a fresh CODEX_HOME holding only a link to the user's
  `auth.json`: no user skills, AGENTS.md, config or memories.

Claude runs with a short read-only allowlist and every writing or network
tool denied. Codex runs in its `workspace-write` sandbox, network off: the
workspace is a throwaway copy, and `read-only` stops `agtmls audit` creating
its temporary files, which would penalise only the arm the skill sends to
the audit. `agtmls` on PATH is this checkout, so the arms and the skill
agree on what it does.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

CLAUDE_ALLOWED = "Read,Glob,Grep,Skill,Bash(agtmls:*),Bash(ls:*),Bash(cat:*),Bash(head:*),Bash(grep:*),Bash(wc:*)"
CLAUDE_DENIED = "Write,Edit,NotebookEdit,WebFetch,WebSearch"
MAX_TURNS = "40"


class Options(NamedTuple):
    root: Path
    model: str | None = None
    budget_usd: float = 2.0
    timeout: int = 900


class Outcome(NamedTuple):
    answer: str
    skill_used: bool
    tokens: int | None
    cost_usd: float | None
    model: str | None
    error: str | None


class Agent(NamedTuple):
    binary: str
    skills_dir: str
    command: Callable[[str, Path, Options], tuple[list[str], dict[str, str]]]
    parse: Callable[[str, str, Options], Outcome]


def _events(stdout: str) -> list[dict]:
    events = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _claude_command(prompt: str, work: Path, options: Options) -> tuple[list[str], dict[str, str]]:
    argv = [
        "claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
        "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
        "--max-turns", MAX_TURNS, "--max-budget-usd", str(options.budget_usd),
        "--allowedTools", CLAUDE_ALLOWED, "--disallowedTools", CLAUDE_DENIED,
    ]
    return argv + (["--model", options.model] if options.model else []), {}


def _claude_reads_skill(block: dict, skill: str) -> bool:
    tool, given = block.get("name"), block.get("input") or {}
    if tool == "Skill":
        return given.get("skill") == skill
    return tool == "Read" and f"/{skill}/" in str(given.get("file_path", ""))


def _claude_used(events: list[dict], skill: str) -> bool:
    for event in events:
        content = (event.get("message") or {}).get("content") if event.get("type") == "assistant" else None
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and _claude_reads_skill(block, skill):
                return True
    return False


def _tokens(usage: object, keys: tuple[str, ...] | None = None) -> int | None:
    """Tokens a run reported: the named fields, or every `*tokens` field."""
    if not isinstance(usage, dict):
        return None
    chosen = keys or tuple(key for key in usage if key.endswith("tokens"))
    return sum(value for key in chosen if isinstance(value := usage.get(key), int)) or None


def _claude_parse(stdout: str, skill: str, options: Options) -> Outcome:
    events = _events(stdout)
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    model = init.get("model") or options.model
    if result is None:
        return Outcome("", False, None, None, model, "claude printed no result")
    error = f"claude: {result.get('subtype')}" if result.get("is_error") else None
    return Outcome(str(result.get("result") or ""), _claude_used(events, skill), _tokens(result.get("usage")),
                   result.get("total_cost_usd"), model, error)


def codex_auth() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "auth.json"


def _codex_command(prompt: str, work: Path, options: Options) -> tuple[list[str], dict[str, str]]:
    home = work.parent / "codex-home"
    home.mkdir(exist_ok=True)
    (home / "auth.json").symlink_to(codex_auth())
    argv = ["codex", "exec", "--json", "--skip-git-repo-check", "--sandbox", "workspace-write"]
    argv += ["--model", options.model] if options.model else []
    return argv + [prompt], {"CODEX_HOME": str(home)}


def _codex_message(event: dict) -> str:
    error = event.get("error")
    return str(event.get("message") or (error.get("message") if isinstance(error, dict) else error))


def _codex_event(event: dict, skill: str, state: dict) -> None:
    """Fold one `codex exec --json` event into the run's state."""
    kind, item = event.get("type"), event.get("item")
    item = item if isinstance(item, dict) else {}
    if kind == "item.completed" and item.get("type") == "agent_message":
        state["answer"] = str(item.get("text") or "")
    elif item.get("type") == "command_execution":
        state["used"] = state["used"] or f"{skill}/SKILL.md" in str(item.get("command", ""))
    elif kind == "turn.completed":
        state["tokens"] = _tokens(event.get("usage"), ("input_tokens", "output_tokens"))
    elif kind in ("error", "turn.failed"):
        state["error"] = f"codex: {_codex_message(event)}"


def _codex_parse(stdout: str, skill: str, options: Options) -> Outcome:
    state: dict = {"answer": "", "used": False, "tokens": None, "error": None}
    for event in _events(stdout):
        _codex_event(event, skill, state)
    if not state["answer"] and state["error"] is None:
        state["error"] = "codex printed no answer"
    return Outcome(state["answer"], state["used"], state["tokens"], None,
                   options.model or "codex default", state["error"])


AGENTS = {
    "claude": Agent("claude", ".claude/skills", _claude_command, _claude_parse),
    "codex": Agent("codex", ".codex/skills", _codex_command, _codex_parse),
}


def agtmls_shim(work: Path, root: Path) -> Path:
    """A bin directory whose `agtmls` is this checkout's CLI."""
    bin_dir = work.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    shim = bin_dir / "agtmls"
    shim.write_text(f'#!/bin/sh\nexec python3 "{root / "scripts" / "agtmls.py"}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    return bin_dir


def run(agent: Agent, prompt: str, skill: str, work: Path, options: Options) -> tuple[Outcome, float, str]:
    """(what the agent answered, seconds taken, its raw output)."""
    argv, extra = agent.command(prompt, work, options)
    env = {**os.environ, **extra, "PATH": f"{agtmls_shim(work, options.root)}{os.pathsep}{os.environ.get('PATH', '')}"}
    start = time.monotonic()
    try:
        proc = subprocess.run(argv, cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=options.timeout, check=False)
    except subprocess.TimeoutExpired:
        return Outcome("", False, None, None, options.model, f"timed out after {options.timeout}s"), \
            time.monotonic() - start, ""
    seconds = time.monotonic() - start
    outcome = agent.parse(proc.stdout, skill, options)
    if outcome.error is None and proc.returncode != 0:
        outcome = outcome._replace(error=f"{agent.binary} exited {proc.returncode}")
    return outcome, seconds, proc.stdout
