# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Ship index.json.sig in the wheel when the release workflow has made one.

The signature is produced in CI after the tag is pushed (agtmls-spec
chapter 9), so it is never committed and a plain force-include would fail
every local build. Present, it goes beside index.json in the registry;
absent, the wheel is built exactly as before.
"""

from __future__ import annotations

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        signature = Path(self.root) / "index.json.sig"
        if self.target_name == "wheel" and signature.is_file():
            build_data["force_include"][str(signature)] = "agtmls/_registry/index.json.sig"
