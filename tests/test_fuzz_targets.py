# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The fuzz targets, replayed without Atheris.

fuzz.py drives them with libFuzzer on Linux in CI. Here each target sees its
seed corpus, the inputs fuzzing has already broken the code with, and a
seeded stream of random inputs built from the characters the parsers care
about, so a target that raises fails the ordinary suite on every platform.
"""

from __future__ import annotations

import random
import sys
import unittest

from .support import ROOT

sys.path.insert(0, str(ROOT / "fuzz"))
import targets

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import advisories

CORPUS = ROOT / "fuzz" / "corpus"
ALPHABET = ["\\", "u", "n", "t", "\"", "0", "d", "8", "3", "D", "C", "{", "}", "[", "]", ":", ",", "a", " ",
            "\n", "\u200b", "\ufe0f", "\u2028", "\uff29", "\ufb01", "\U000e0041", "sha256:", "-", "#", "`"]


class FuzzTargetReplayTests(unittest.TestCase):
    def test_every_target_has_a_seed_corpus(self) -> None:
        self.assertEqual(sorted(p.name for p in CORPUS.iterdir() if p.is_dir()), sorted(targets.TARGETS))

    def test_every_seed_passes_its_target(self) -> None:
        for name, target in targets.TARGETS.items():
            for seed in sorted((CORPUS / name).iterdir()):
                with self.subTest(target=name, seed=seed.name):
                    target(seed.read_bytes())

    def test_seeded_random_inputs_pass_every_target(self) -> None:
        rng = random.Random(20260926)
        for name, target in targets.TARGETS.items():
            for _ in range(1500):
                text = "".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 80)))
                with self.subTest(target=name, text=text):
                    target(text.encode("utf-8"))

    def test_invalid_utf8_is_decoded_not_raised(self) -> None:
        for target in targets.TARGETS.values():
            target(b"\xff\xfe\xc3(\x80")


class AdvisoryShapeRegressionTests(unittest.TestCase):
    """Feeds fuzzing broke: every shape is judged, never raised on."""

    def test_non_list_advisories_are_a_problem(self) -> None:
        self.assertEqual(advisories.feed_problems({"advisories": {"a": 1}}), ["advisories is not a list"])

    def test_each_malformed_advisory_is_named(self) -> None:
        problems = advisories.feed_problems({"advisories": [
            1,
            {"id": 3, "affected": "x"},
            {"id": "AGT-ADV-2026-001", "modified": 5, "affected": [7, {"package": "p", "ecosystem_specific": {"digests": [1]}}]},
        ]})
        self.assertIn("advisory 0: not an object", problems)
        self.assertIn("?: id is not AGT-ADV-YYYY-NNN", problems)
        self.assertIn("?: no affected entries", problems)
        self.assertIn("AGT-ADV-2026-001: modified is not an RFC 3339 UTC timestamp", problems)
        self.assertIn("AGT-ADV-2026-001: affected ecosystem is not AgtMLS", problems)
        self.assertIn("AGT-ADV-2026-001: affected needs one or more sha256: digests", problems)

    def test_wrong_shapes_revoke_nothing(self) -> None:
        feed = {"advisories": [
            "x", {"affected": [{"ecosystem_specific": {"digests": ["sha256:a"]}}]},
            {"id": "AGT-ADV-2026-001", "affected": [5, {"ecosystem_specific": {"digests": [1, "sha256:b"]}}]},
        ]}
        lock = {"skills": [1, {"name": "list", "integrity": ["sha256:b"]}, {"name": "a", "integrity": "sha256:a"},
                           {"name": "b", "integrity": "sha256:b"}]}
        self.assertEqual(advisories.revoked(feed, lock), [("b", "sha256:b", ["AGT-ADV-2026-001"])])
        self.assertEqual(advisories.revoked({"advisories": "x"}, {"skills": "y"}), [])


if __name__ == "__main__":
    unittest.main()
