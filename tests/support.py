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

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
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
