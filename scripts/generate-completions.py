#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate Bash, Zsh, and Fish shell completions for the agtmls CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
COMPLETIONS_DIR = ROOT / "completions"

from _lib.cli_parser import (  # noqa: E402  (needs the scripts path first)
    build_parser,
    native_agents,
)


def subcommands() -> list[str]:
    """Every subcommand, read from the parser that defines them.

    This was a hand-maintained list, and it had gone one command stale:
    `verify` -- which checks an installed tree against its lockfile -- was
    absent, so shell completion never offered the integrity check to anyone
    who had installed the completions. Completions that disagree with the CLI
    are worse than none, because they teach the wrong surface.
    """
    parser = build_parser()
    # `_subparsers` is None when none were added, so this has to be checked
    # rather than walked: a traceback here would tell the reader about
    # argparse internals instead of about their parser.
    group = parser._subparsers  # noqa: SLF001  (argparse exposes no public accessor)
    for action in getattr(group, "_group_actions", []):  # no public accessor either
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001  (the class is private too)
            return sorted(action.choices)
    raise SystemExit(
        "FAIL: the parser declares no subcommands, so the completions would be "
        "empty; check build_parser() in scripts/_lib/cli_parser.py"
    )


SUBCOMMANDS = subcommands()


def render_bash() -> str:
    subs = " ".join(SUBCOMMANDS)
    agents = " ".join(native_agents())
    return f"""# bash completion for agtmls -*- shell-script -*-
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT

_agtmls_completions() {{
    local cur prev words cword
    _init_completion || return

    local subcommands="{subs}"

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${{subcommands}}" -- "$cur") )
        return 0
    fi

    case "${{words[1]}}" in
        install)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "python rust typescript go ruby generic" -- "$cur") )
            elif [[ $cword -eq 3 ]]; then
                COMPREPLY=( $(compgen -W "{agents}" -- "$cur") )
            fi
            ;;
        uninstall)
            if [[ $cword -eq 2 ]]; then
                COMPREPLY=( $(compgen -W "{agents}" -- "$cur") )
            fi
            ;;
        audit|show)
            _filedir
            ;;
        *)
            ;;
    esac
}}

complete -F _agtmls_completions agtmls
"""


def render_zsh() -> str:
    lines = ["#compdef agtmls", "# SPDX-FileCopyrightText: 2026 Sebastien Rousseau", "# SPDX-License-Identifier: Apache-2.0 OR MIT", ""]
    lines.append("_agtmls() {")
    lines.append("    local -a commands")
    lines.append("    commands=(")
    for sub in SUBCOMMANDS:
        lines.append(f"        '{sub}:{sub} command'")
    lines.append("    )")
    lines.append("    _arguments -C \\")
    lines.append("        '1: :->command' \\")
    lines.append("        '*: :->args'")
    lines.append("    case $state in")
    lines.append("        command)")
    lines.append("            _describe -t commands 'agtmls command' commands")
    lines.append("            ;;")
    lines.append("    esac")
    lines.append("}")
    lines.append("compdef _agtmls agtmls")
    return "\n".join(lines) + "\n"


def render_fish() -> str:
    lines = [
        "# fish completion for agtmls",
        "# SPDX-FileCopyrightText: 2026 Sebastien Rousseau",
        "# SPDX-License-Identifier: Apache-2.0 OR MIT",
        "",
        "complete -c agtmls -f",
    ]
    for sub in SUBCOMMANDS:
        lines.append(f'complete -c agtmls -n "__fish_use_subcommand" -a "{sub}" -d "{sub} command"')
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write completions to completions/")
    parser.add_argument("--check", action="store_true", help="verify completions are up to date")
    args = parser.parse_args()

    files = {
        COMPLETIONS_DIR / "agtmls.bash": render_bash(),
        COMPLETIONS_DIR / "_agtmls": render_zsh(),
        COMPLETIONS_DIR / "agtmls.fish": render_fish(),
    }

    if args.write:
        COMPLETIONS_DIR.mkdir(parents=True, exist_ok=True)
        for path, content in files.items():
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
        return 0

    if args.check:
        stale = []
        for path, content in files.items():
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.name)
        if stale:
            print(f"FAIL: stale shell completions: {', '.join(stale)} (run generate-completions.py --write)", file=sys.stderr)
            return 1
        print(f"OK: shell completions are current ({len(files)} files)")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
