# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Which skills an install or an export carries: one rule for both.

Without a profile: every general skill (no bundle), plus the skills of each
bundle asked for. With a profile: only the general skills its `skills` list
names, plus its bundles and any asked for. `install --profile` used to read
only the bundles, so `--profile minimal` installed every general skill.
"""

from __future__ import annotations

import json
from pathlib import Path


class UnknownProfile(KeyError):
    """A profile name profiles.json does not define."""


def resolve(root: Path, profile: str | None, bundles: list[str]) -> tuple[set[str] | None, set[str]]:
    """(skills the profile lists, or None for no profile; bundles to include)."""
    wanted_bundles = set(bundles)
    if profile is None:
        return None, wanted_bundles
    profiles = json.loads((root / "profiles.json").read_text(encoding="utf-8")).get("profiles", {})
    chosen = profiles.get(profile)
    if not isinstance(chosen, dict):
        raise UnknownProfile(profile)
    return set(chosen.get("skills", [])), wanted_bundles | set(chosen.get("bundles", []))


def wanted(name: str, bundle: str | None, skills: set[str] | None, bundles: set[str]) -> bool:
    """Whether skill `name`, in `bundle` (None for general), is carried."""
    if bundle and bundle in bundles:
        return True
    return name in skills if skills is not None else not bundle
