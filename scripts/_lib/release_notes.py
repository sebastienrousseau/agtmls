# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What a release's notes must say, judged the same way before and after.

release-preflight.py reads the prepared notes before the tag is pushed;
release-audit.py reads the published release body afterwards. Both need the
same answer to "is there a user-visible summary, and do the checksums equal
the artifacts?" -- AGENTS.md section 3 -- so it is answered once, here.

The page layout is the portfolio's Release Page Format: the hand-written
Highlights, then GitHub's generated What's Changed (and New Contributors),
then Checksums, then the Full Changelog link. Only the Highlights and the
Checksums placeholder are prepared; release-body.py composes the rest.
"""

from __future__ import annotations

import re

from .checksums import parse_sums

HIGHLIGHTS = "Highlights ⭐️"
CHANGED = "What's Changed"
CONTRIBUTORS = "New Contributors"
CHECKSUMS = "Checksums"
HIGHLIGHT = re.compile(r"^\* \*\*[^*\n]+\*\*: \S")
CHANGE = re.compile(r"^\* .+ by @\S+ in https://\S+$")
FULL_CHANGELOG = re.compile(r"^\*\*Full Changelog\*\*: https://\S+$")


def section(text: str, heading: str) -> str | None:
    """The body of a `## heading` section, or None if there is none."""
    match = re.search(
        rf"^## {re.escape(heading)}[ \t]*\n(.*?)(?=^## |^\*\*Full Changelog\*\*|\Z)",
        text, re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else None


def title(version: str) -> str:
    """The release page title: `AgtMLS 0.0.N`, the version without the `v`."""
    return f"AgtMLS {version}"


def highlight_problems(name: str, text: str) -> list[str]:
    """Two to four `* **Feature**: sentence` bullets under `## Highlights ⭐️`."""
    highlights = section(text, HIGHLIGHTS)
    if highlights is None:
        return [f"{name}: needs a `## {HIGHLIGHTS}` section of user-visible changes"]
    bullets = [line for line in highlights.splitlines() if line.startswith(("* ", "- "))]
    errors = []
    if not 2 <= len(bullets) <= 4:
        errors.append(f"{name}: `## {HIGHLIGHTS}` needs two to four bullets, not {len(bullets)}")
    errors += [
        f"{name}: highlight {line[:40]!r} is not `* **<Feature>**: <sentence>`"
        for line in bullets if not HIGHLIGHT.match(line)
    ]
    return errors


def page_problems(name: str, text: str) -> list[str]:
    """The generated parts of a published page, and the order of all of them."""
    errors = []
    changed = section(text, CHANGED)
    if changed is None or not any(CHANGE.match(line) for line in changed.splitlines()):
        errors.append(f"{name}: needs a generated `## {CHANGED}` list, `* <title> by @<author> in <url>`")
    headings = re.findall(r"^## (.+?)[ \t]*$", text, re.MULTILINE)
    expected = [HIGHLIGHTS, CHANGED, *([CONTRIBUTORS] if CONTRIBUTORS in headings else []), CHECKSUMS]
    if headings != expected:
        errors.append(f"{name}: sections are {headings}, not {expected}")
    lines = text.strip().splitlines()
    if not lines or not FULL_CHANGELOG.match(lines[-1]):
        errors.append(f"{name}: last line must be `**Full Changelog**: <compare URL>`")
    return errors


def notes_problems(
    name: str, text: str, sums: str | None, pending: bool = False, published: bool = False
) -> list[str]:
    """Everything missing from release notes `text`, called `name` in messages.

    `sums` is the SHA256SUMS text the Checksums section must equal. Without
    it, `pending` accepts a Checksums section that says so -- for a release
    whose artifacts are built only after its tag is pushed. `published`
    also requires the generated sections of a composed release page.
    """
    errors = highlight_problems(name, text)
    checksums = section(text, CHECKSUMS)
    if checksums is None:
        errors.append(f"{name}: needs a `## {CHECKSUMS}` section")
    elif sums is not None:
        expected, problems = parse_sums(sums)
        errors.extend(problems)
        listed, _ = parse_sums(checksums.replace("```", ""))
        if listed != expected:
            errors.append(f"{name}: Checksums section does not equal SHA256SUMS")
    elif not pending:
        errors.append(f"{name}: no SHA256SUMS to check the Checksums section against")
    elif "pending" not in checksums.lower():
        errors.append(f"{name}: pending checksums must be marked `pending` in the Checksums section")
    if published:
        errors += page_problems(name, text)
    return errors
