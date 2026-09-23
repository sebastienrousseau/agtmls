#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Prove the local tier does not touch the network.

"No telemetry" was true and unverifiable. Absence of a telemetry client today
is a code review, not a control: the next dependency, the next convenience
call to check for updates, the next well-meant crash reporter all pass a code
review that nobody runs again. For a local-first tool whose entire positioning
is that your skills never reach us, that gap is the one worth closing.

So this runs the consumer-facing surface with the network taken away, and
fails if anything reaches for it.

How the block works
-------------------

A `sitecustomize` module is written into a temporary directory and put on
`PYTHONPATH`. Python imports it automatically at interpreter startup, before
any of our code runs, and it replaces the socket entry points with versions
that record the attempt and raise. `PYTHONPATH` is inherited, so every Python
subprocess the CLI spawns is blocked too -- which matters, because most of
this CLI's work happens in subprocesses.

What it does not cover, stated plainly: a non-Python child process. `git` and
`make` are invoked by some commands and would not see the patched socket. The
commands exercised below are the consumer path, which shells out to neither.

The harness tests itself
------------------------

A block that silently stopped working would make every run pass. The last
check is a positive control: a command that *does* open a socket must be
refused and recorded. If the control is not blocked, the run fails even though
everything else was clean.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"

SITECUSTOMIZE = '''\
"""Record and refuse every outbound socket. Injected by smoke-offline.py."""
import os
import socket

_LOG = os.environ.get("AGTMLS_OFFLINE_LOG")


def _record(what, target):
    if _LOG:
        with open(_LOG, "a", encoding="utf-8") as handle:
            handle.write(f"{what} {target!r}\\n")


def _refuse(what):
    def blocked(*args, **kwargs):
        _record(what, args[1] if what == "connect" and len(args) > 1 else args[:1])
        raise OSError("network disabled by smoke-offline.py")
    return blocked


socket.socket.connect = _refuse("connect")
socket.socket.connect_ex = _refuse("connect_ex")
socket.create_connection = _refuse("create_connection")
socket.getaddrinfo = _refuse("getaddrinfo")
'''

#: The surface a person runs locally. Each must work with no network at all.
COMMANDS: list[list[str]] = [
    ["list"],
    ["list", "commands"],
    ["search", "review"],
    ["show", "handoff"],
    ["stats", "--json"],
    ["profiles"],
    ["providers"],
    ["index", "--check"],
    ["audit", "--all", "--strict"],
]


def blocked_environment(injected: Path, log: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(injected)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env["AGTMLS_OFFLINE_LOG"] = str(log)
    # Any of these would let a library reach out through a proxy the socket
    # patch is not on the far side of.
    for variable in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(variable, None)
    return env


def attempts(log: Path) -> list[str]:
    if not log.exists():
        return []
    return [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="agtmls-offline-") as raw:
        workspace = Path(raw)
        injected = workspace / "inject"
        injected.mkdir()
        (injected / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
        log = workspace / "attempts.log"
        env = blocked_environment(injected, log)

        target = workspace / "consumer"
        target.mkdir()
        runs = COMMANDS + [
            ["install", "rust", "claude", "--target", str(target), "--copy"],
            ["verify", "claude", "--target", str(target), "--json"],
            ["uninstall", "claude", "--target", str(target)],
        ]

        for argv in runs:
            proc = subprocess.run(
                [sys.executable, str(CLI), *argv],
                cwd=ROOT, env=env, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            if proc.returncode != 0:
                errors.append(
                    f"`agtmls {' '.join(argv)}` exited {proc.returncode} without a "
                    f"network:\n{proc.stdout.rstrip()}"
                )

        reached_out = attempts(log)
        if reached_out:
            errors.append(
                f"{len(reached_out)} outbound socket attempt(s) from the local "
                f"surface: {reached_out[:3]}"
            )

        # Positive control. A block that stopped working would make every
        # check above pass, so prove it still refuses something.
        control_log = workspace / "control.log"
        control_env = blocked_environment(injected, control_log)
        control = subprocess.run(
            [sys.executable, "-c",
             "import urllib.request; urllib.request.urlopen('http://example.com', timeout=2)"],
            cwd=ROOT, env=control_env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if control.returncode == 0:
            errors.append("the control reached the network: the block is not working")
        elif not attempts(control_log):
            errors.append(
                "the control failed but recorded no attempt: the block is not the "
                "thing that stopped it, so a real call might not be recorded either"
            )

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} offline issue(s)")
        return 1
    print(
        f"OK: {len(COMMANDS) + 3} local command(s) ran with the network refused, "
        "0 outbound attempts, control blocked"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
