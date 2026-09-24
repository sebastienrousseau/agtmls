# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Shared fixtures for the unit suite.

These tests validate the *validators*: the failure mode the gate cannot see
is a checker that always returns 0. Every case is written to fail if the logic
it covers is weakened, not merely if it raises.

They lived in one 1,248-line module until the file-length ceiling caught it.
Splitting them changed no assertion; `scripts/run-unit-tests.py` discovers
this package instead of holding them.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"


def load_script(name: str):
    path = ROOT / "scripts" / name
    # Prefixed: scripts/agtmls.py would otherwise register as "agtmls" and
    # shadow the real package in src/, which PackagedCliTests imports.
    module_name = "_agtmls_script_" + name.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: dataclasses resolves a field's type through
    # sys.modules[cls.__module__], which is None for a module that was built
    # from a spec and never registered. Without this, load_script raises on
    # any script that declares a @dataclass.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[module_name]
        raise
    return module


def skill_text(frontmatter: str, body: str = "# Heading\n\ncontent\n") -> str:
    return f"---\n{frontmatter.strip()}\n---\n\n{body}"


def registry_fixture(destination: Path) -> Path:
    """A working copy of the registry's *data*, without its scripts.

    Validators resolve their paths from ROOT at import time, so a test that
    wants to see one fail needs a tree to break. Copying the data and leaving
    the scripts behind keeps the copy small and keeps the code under test the
    real code, which is what `retarget` then points at this.
    """

    skip = {".git", "__pycache__", ".agtmls", ".ruff_cache", "dist", "node_modules"}
    destination.mkdir(parents=True, exist_ok=True)
    # Resolved, because validators resolve() their link targets and macOS maps
    # /var onto /private/var. An unresolved root makes every link in the tree
    # look like it escapes the repository.
    destination = destination.resolve()
    for path in ROOT.iterdir():
        # The coverage gate runs checks in parallel and writes `.coverage.*`
        # data files beside the tree; one vanished between this listing and
        # its copy and took a whole test module down with it.
        # index.json.sig is made by the release workflow after the tag; a copy
        # in a fixture would make its tests' own signing prompt to overwrite
        # it, and that prompt hung the gate.
        if path.name in skip or path.name.startswith(".coverage") or path.name == "index.json.sig":
            continue
        try:
            if path.is_dir():
                shutil.copytree(
                    path, destination / path.name, symlinks=True,
                    ignore=shutil.ignore_patterns(*skip),
                )
            else:
                shutil.copy2(path, destination / path.name)
        except FileNotFoundError:
            continue  # gone since the listing: not part of the registry
    return destination


def _retarget_value(value, fixture: Path):
    """Rewrite any repository path inside `value`, however it is wrapped."""
    if isinstance(value, Path):
        return fixture / value.relative_to(ROOT) if value.is_relative_to(ROOT) else value
    if isinstance(value, list):
        return [_retarget_value(item, fixture) for item in value]
    if isinstance(value, tuple):
        return tuple(_retarget_value(item, fixture) for item in value)
    if isinstance(value, set):
        return {_retarget_value(item, fixture) for item in value}
    if isinstance(value, dict):
        return {key: _retarget_value(item, fixture) for key, item in value.items()}
    return value


def real_paths(module) -> list[str]:
    """Module attributes still pointing inside the repository.

    The guard for the mistake this helper made once: an earlier version
    rewrote only bare Path attributes, and `bump-version.py` keeps its targets
    in lists. Driving it wrote a test's version number into the actual
    pyproject.toml, plugin.json and __init__.py. A test that edits the
    repository it is testing is worse than no test.
    """
    found = []
    for name, value in vars(module).items():
        for candidate in _walk_paths(value):
            if candidate.is_relative_to(ROOT):
                found.append(f"{name} -> {candidate}")
    return found


def _walk_paths(value):
    if isinstance(value, Path):
        yield value
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _walk_paths(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_paths(item)


def retarget(module, fixture: Path) -> None:
    """Point a script's module-level paths at `fixture` instead of the repo.

    Every validator derives its constants from `ROOT = __file__/../..` at
    import time, so patching ROOT alone leaves SKILLS_DIR and friends aimed at
    the real tree. This rewrites every repository path reachable from a
    module attribute -- including the ones inside lists, which is where this
    helper first went wrong -- and then refuses to return if any is left.

    Running the copy as a subprocess would be simpler and would measure a
    different file; this keeps the coverage on the code that ships.
    """
    for name, value in list(vars(module).items()):
        if name.startswith("__"):
            continue
        rewritten = _retarget_value(value, fixture)
        if rewritten is not value:
            setattr(module, name, rewritten)
    leftover = real_paths(module)
    if leftover:
        raise AssertionError(
            f"{getattr(module, '__name__', module)} still points at the repository: "
            f"{leftover[:4]}. Driving it would edit the tree under test."
        )


def run_main(module, *args: str) -> tuple[int, str]:
    """Call a script's main() and capture what it said."""
    import contextlib
    import io

    buffer = io.StringIO()
    argv = sys.argv
    sys.argv = [getattr(module, "__file__", "script"), *args]
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            try:
                code = module.main()
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
    finally:
        sys.argv = argv
    return code, buffer.getvalue()
