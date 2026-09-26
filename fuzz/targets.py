# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Fuzz targets for every parser that reads untrusted input.

Each target takes raw bytes, must never raise, and asserts a property of its
parser rather than only surviving it. They are plain stdlib functions: the
Atheris harness (fuzz.py) drives them on Linux in CI, and
tests/test_fuzz_targets.py replays seeds and seeded random inputs through
them everywhere, so a target is exercised even where Atheris cannot install.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import advisories, analyzer  # noqa: E402  (needs the scripts path first)
from _lib.checksums import parse_sums  # noqa: E402  (same)


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def json_escapes(data: bytes) -> None:
    """spec 4.3: decoding JSON escapes never creates or removes a line."""
    text = _text(data)
    assert analyzer.decode_json_escapes(text).count("\n") == text.count("\n")


def normalize(data: bytes) -> None:
    """Stripping invisibles and NFKC keep every line, so line numbers survive."""
    text = _text(data)
    assert analyzer.normalize(text).count("\n") == text.count("\n")


def audit_content(data: bytes) -> None:
    """Every rule, over hostile text, in each file type rules select on."""
    text = _text(data)
    for name in ("SKILL.md", "tools.json", "run.sh", "hook.py"):
        for finding in analyzer.audit_file_content(Path(name), text):
            assert finding.line >= 1


def advisory_feed(data: bytes) -> None:
    """A feed is signature-checked before use, but its parser must still
    reject any JSON shape without raising."""
    try:
        feed = json.loads(_text(data))
    except ValueError:
        return
    if not isinstance(feed, dict):
        return
    advisories.feed_problems(feed)
    advisories.revoked(feed, {"skills": [{"name": "s", "integrity": "sha256:" + "0" * 64}]})


def checksums(data: bytes) -> None:
    """SHA256SUMS parsing never raises, and every accepted digest is hex."""
    sums, _ = parse_sums(_text(data))
    for digest in sums.values():
        assert all(c in "0123456789abcdef" for c in digest)


TARGETS = {
    "json_escapes": json_escapes,
    "normalize": normalize,
    "audit_content": audit_content,
    "advisory_feed": advisory_feed,
    "checksums": checksums,
}
