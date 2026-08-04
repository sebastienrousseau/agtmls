# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: MIT
"""Console entry point for the packaged AgtMLS registry.

`uvx agtmls ...` must behave exactly like `python3 scripts/agtmls.py ...` in a
checkout, so this is a shim rather than a reimplementation: it locates the
registry and hands the argv straight to the same dispatcher.

The registry is shipped under `agtmls/_registry/`, which mirrors the repo
layout one directory down. Every script resolves its root as
`Path(__file__).resolve().parent.parent`, so `_registry/scripts/agtmls.py`
sees `_registry/` as the registry root with no code change.

Resolution order:

1. ``AGTMLS_HOME`` — point at a checkout to run the installed CLI against
   your own working tree.
2. A repo checkout containing this file (editable install / running from src).
3. The bundled ``_registry/``.

Installing from a wheel defaults `install` to ``--copy``: the wheel lives in
an ephemeral uvx/pipx cache, and symlinking into a cache that is about to be
garbage-collected leaves a target repo full of dangling links.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

_PACKAGED = Path(__file__).resolve().parent / "_registry"
# Commands that need the full development tree (git history, CI config,
# release tooling). Refusing them with a clear message beats failing deep
# inside a script that assumed a checkout.
_CHECKOUT_ONLY = {
    "bump-version",
    "check",
    "diff",
    "next-version",
    "release-check",
    "release-dry-run",
    "release-pack",
    "verify-release-assets",
}


def registry_root() -> tuple[Path, bool]:
    """Return (root, is_packaged)."""
    override = os.environ.get("AGTMLS_HOME")
    if override:
        root = Path(override).expanduser().resolve()
        if not (root / "scripts" / "agtmls.py").exists():
            raise SystemExit(f"AGTMLS_HOME is not an AgtMLS checkout: {root}")
        return root, False

    # src/agtmls/cli.py -> src/agtmls -> src -> <repo>
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "scripts" / "agtmls.py").exists():
        return checkout, False

    if (_PACKAGED / "scripts" / "agtmls.py").exists():
        return _PACKAGED, True

    raise SystemExit(
        "AgtMLS registry not found. Reinstall the package, or set AGTMLS_HOME "
        "to a checkout of https://github.com/sebastienrousseau/agtmls"
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    root, packaged = registry_root()
    command = next((arg for arg in argv if not arg.startswith("-")), None)

    if packaged and command in _CHECKOUT_ONLY:
        raise SystemExit(
            f"`agtmls {command}` needs a repository checkout, not an installed "
            "package. Clone https://github.com/sebastienrousseau/agtmls and run "
            f"`python3 scripts/agtmls.py {command}`, or set AGTMLS_HOME to a checkout."
        )

    # A wheel's skills disappear with the cache; copy them instead of linking.
    if packaged and command == "install" and "--copy" not in argv:
        argv.append("--copy")

    target = root / "scripts" / "agtmls.py"
    sys.argv = [str(target), *argv]
    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
