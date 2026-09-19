#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Prove `make install` produces a working binary, not just files on disk.

The README advertises the standard Unix packaging contract (PREFIX, DESTDIR).
The target used to install scripts/agtmls.py alone into BINDIR, but that
script resolves its registry as Path(__file__).parent.parent -- so the
installed binary looked for $PREFIX/index.json and every command died with
FileNotFoundError. `make install` exited 0 the whole time, because nothing
ever ran what it installed.

validate-packaging.py covers the wheel. This covers the Makefile.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if shutil.which("make") is None:
        print("SKIP: make is not available")
        return 0

    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agtmls-make-install-") as raw:
        prefix = Path(raw) / "opt"
        proc = subprocess.run(
            ["make", "install", f"PREFIX={prefix}"],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if proc.returncode != 0:
            print(f"FAIL: make install failed:\n{proc.stdout}")
            return 1

        binary = prefix / "bin" / "agtmls"
        if not binary.exists():
            print(f"FAIL: no binary at {binary}")
            return 1

        # The point of the test: the installed binary must actually run.
        stats = subprocess.run(
            [str(binary), "stats", "--json"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if stats.returncode != 0:
            errors.append(f"installed binary cannot run `stats`:\n{stats.stdout}")
        else:
            try:
                payload = json.loads(stats.stdout)
            except json.JSONDecodeError as exc:
                errors.append(f"installed binary emitted invalid JSON: {exc}\n{stats.stdout}")
            else:
                expected = json.loads(
                    (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
                )["version"]
                if payload.get("registry_version") != expected:
                    errors.append(
                        f"installed registry_version {payload.get('registry_version')!r} "
                        f"!= {expected!r}"
                    )
                if not payload.get("skills"):
                    errors.append("installed binary reports zero skills")

        for relative in [
            "share/man/man1/agtmls.1",
            "share/bash-completion/completions/agtmls",
            "share/zsh/site-functions/_agtmls",
            "share/fish/vendor_completions.d/agtmls.fish",
        ]:
            if not (prefix / relative).exists():
                errors.append(f"missing installed file: {relative}")

        # uninstall must remove everything it installed.
        subprocess.run(
            ["make", "uninstall", f"PREFIX={prefix}"],
            cwd=ROOT, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        left = [p for p in prefix.rglob("*") if p.is_file()]
        if left:
            errors.append(f"make uninstall left {len(left)} file(s), e.g. {left[0]}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} make-install issue(s)")
        return 1
    print("OK: make install produces a working binary; uninstall is clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
