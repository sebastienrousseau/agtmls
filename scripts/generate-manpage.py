#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate Unix manpage (agtmls.1) for the agtmls CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAN_FILE = ROOT / "share" / "man" / "man1" / "agtmls.1"

MANPAGE_TEMPLATE = """.\\" SPDX-FileCopyrightText: 2026 Sebastien Rousseau
.\\" SPDX-License-Identifier: Apache-2.0 OR MIT
.TH AGTMLS 1 "March 2026" "agtmls 0.0.6" "User Commands"
.SH NAME
agtmls \\- The universal agent skills registry
.SH SYNOPSIS
.B agtmls
[\\fIcommand\\fR] [\\fIoptions...\\fR]
.SH DESCRIPTION
\\fBagtmls\\fR is the zero-dependency CLI and registry for managing and deploying polyglot
engineering skills, system prompts, commands, and subagents across AI coding runtimes including
Claude Code, OpenAI Codex, Aider, Google Antigravity, Gemini CLI, Cursor, and Windsurf.
.SH SUBCOMMANDS
.TP
\\fBdoctor\\fR
Run the AgtMLS full diagnostic suite verifying configuration, skills, and tools.
.TP
\\fBstatus\\fR
Inspect local workspace installation status and symlinked skills.
.TP
\\fBcheck\\fR
Run the 57-gate validation suite guarding registry integrity.
.TP
\\fBaudit\\fR [\\fIpath\\fR] [\\fB\\-\\-\\-all\\fR] [\\fB\\-\\-\\-strict\\fR]
Statically scan skills for prompt injection, hidden unicode steganography, and dangerous execution.
.TP
\\fBlist\\fR [\\fIcommands\\fR]
List available skills or commands in the registry.
.TP
\\fBsearch\\fR \\fIquery\\fR
Search skills and commands by keyword or tag.
.TP
\\fBshow\\fR \\fIname\\fR
Display detailed metadata and prompt instructions for a skill.
.TP
\\fBinstall\\fR \\fIlanguage\\fR \\fIagent\\fR [\\fB\\-\\-\\-target\\fR \\fIdir\\fR]
Install skills and conventions for the chosen agent and language.
.TP
\\fBuninstall\\fR \\fIagent\\fR [\\fB\\-\\-\\-target\\fR \\fIdir\\fR]
Remove AgtMLS-managed symlinks and prompt conventions from the workspace.
.TP
\\fBbench\\fR
Run routing and behavioral benchmark evaluation test suites.
.SH AUTHORS
Sebastien Rousseau
.SH COPYRIGHT
Apache-2.0 OR MIT
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write manpage to share/man/man1/agtmls.1")
    parser.add_argument("--check", action="store_true", help="verify manpage is up to date")
    args = parser.parse_args()

    if args.write:
        MAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        MAN_FILE.write_text(MANPAGE_TEMPLATE, encoding="utf-8")
        print(f"wrote {MAN_FILE.relative_to(ROOT)}")
        return 0

    if args.check:
        if not MAN_FILE.exists() or MAN_FILE.read_text(encoding="utf-8") != MANPAGE_TEMPLATE:
            print(f"FAIL: stale manpage at {MAN_FILE.relative_to(ROOT)} (run generate-manpage.py --write)", file=sys.stderr)
            return 1
        print("OK: manpage is current")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
