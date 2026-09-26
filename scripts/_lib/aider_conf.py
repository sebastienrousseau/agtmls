# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Add or remove one file in the top-level `read:` list of .aider.conf.yml.

Aider does not read CONVENTIONS.md on its own; install registers it under
`read:`, and uninstall takes it out again. The installer used to append a
`read:` block to the file whatever it held, so a config with its own `read:`
list gained a second `read:` key -- a YAML error, or a list that replaced
the user's, depending on the parser.

Only the forms a hand-written config uses are edited, line by line so every
other byte stays: a block list (`read:` then `- item` lines), a flow list
(`read: [a, b]`) and a single scalar (`read: a`). Any other shape, or two
top-level `read:` keys, is left alone and reported. Stdlib only, and no YAML
parser: the installer must not resolve packages (AGENTS.md invariant 2).

    python3 aider_conf.py register|unregister <.aider.conf.yml> <file>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

KEY = re.compile(r"^read:[ \t]*(?P<value>[^#\n]*?)[ \t]*(?:#.*)?$")
ITEM = re.compile(r"^(?P<indent>[ \t]*)- [ \t]*(?P<value>[^#\n]*?)[ \t]*(?:#.*)?$")


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _find(lines: list[str]) -> tuple[int, str, list[int]] | str | None:
    """(key line, kind, item lines) for the top-level `read:`, None when
    there is none, or a reason string when it cannot be edited safely."""
    keys = [number for number, line in enumerate(lines) if KEY.match(line)]
    if not keys:
        return None
    if len(keys) > 1:
        return "it has more than one top-level `read:` key"
    start = keys[0]
    value = KEY.match(lines[start]).group("value")
    if value.startswith("["):
        return (start, "flow", []) if value.endswith("]") else "its `read:` flow list spans lines"
    if value:
        return start, "scalar", []
    items = []
    for number in range(start + 1, len(lines)):
        line = lines[number]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ITEM.match(line):
            items.append(number)
            continue
        if line[0] in " \t":
            return "its `read:` list holds something other than `- <file>` items"
        break
    return start, "block", items


def _flow_items(value: str) -> list[str]:
    inner = value.strip()[1:-1]
    return [_unquote(part) for part in inner.split(",") if part.strip()]


def listed(text: str, name: str) -> bool:
    """Whether `name` is already in the top-level `read:` list."""
    lines = text.splitlines()
    found = _find(lines)
    if not isinstance(found, tuple):
        return False
    start, kind, items = found
    value = KEY.match(lines[start]).group("value")
    if kind == "flow":
        return name in _flow_items(value)
    if kind == "scalar":
        return _unquote(value) == name
    return any(_unquote(ITEM.match(lines[number]).group("value")) == name for number in items)


def register(text: str, name: str) -> tuple[str | None, str]:
    """(new text, or None when it must stay as it is; what was done)."""
    if listed(text, name):
        return None, f"{name} is already in read:"
    lines = text.splitlines()
    found = _find(lines)
    if isinstance(found, str):
        return None, f"not changed: {found}; add {name} to read: yourself"
    if found is None:
        prefix = text if not text or text.endswith("\n") else text + "\n"
        return f"{prefix}read:\n  - {name}\n", f"added read: {name}"
    start, kind, items = found
    value = KEY.match(lines[start]).group("value")
    if kind == "flow":
        entries = [*_flow_items(value), name]
        lines[start] = f"read: [{', '.join(entries)}]"
    elif kind == "scalar":
        lines[start : start + 1] = ["read:", f"  - {_unquote(value)}", f"  - {name}"]
    else:
        indent = ITEM.match(lines[items[-1]]).group("indent") if items else "  "
        lines.insert((items[-1] if items else start) + 1, f"{indent}- {name}")
    return "\n".join(lines) + "\n", f"added {name} to read:"


def unregister(text: str, name: str) -> tuple[str | None, bool]:
    """(new text, or None when the file should go; whether anything changed)."""
    if not listed(text, name):
        return text, False
    lines = text.splitlines()
    start, kind, items = _find(lines)
    value = KEY.match(lines[start]).group("value")
    if kind == "flow":
        rest = [entry for entry in _flow_items(value) if entry != name]
        lines[start : start + 1] = [f"read: [{', '.join(rest)}]"] if rest else []
    elif kind == "scalar":
        del lines[start]
    else:
        ours = [number for number in items if _unquote(ITEM.match(lines[number]).group("value")) == name]
        for number in reversed(ours):
            del lines[number]
        if len(ours) == len(items):
            del lines[start]
    remaining = "\n".join(lines).strip()
    return (remaining + "\n" if remaining else None), True


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in {"register", "unregister"}:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    action, conf, name = argv[1], Path(argv[2]), argv[3]
    text = conf.read_text(encoding="utf-8") if conf.is_file() else ""
    if action == "register":
        new, message = register(text, name)
        if new is not None:
            conf.write_text(new, encoding="utf-8")
        print(message)
        return 0
    new, changed = unregister(text, name)
    if changed:
        if new is None:
            conf.unlink()
        else:
            conf.write_text(new, encoding="utf-8")
    print(f"removed {name} from read:" if changed else f"{name} was not in read:")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
