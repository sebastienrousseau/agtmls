# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Chapters 9 and 11: index signatures and revocation, against the spec's vectors."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT, load_script, registry_fixture, retarget, run_main

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import advisories, lockfile, signatures  # needs the scripts path first

SIG = ROOT / "tests" / "fixtures" / "spec-signatures"
ADV = ROOT / "tests" / "fixtures" / "spec-advisories"


class SignatureVectorTests(unittest.TestCase):
    def test_every_spec_signature_vector(self) -> None:
        spec = json.loads((SIG / "cases.json").read_text(encoding="utf-8"))
        for case in spec["cases"]:
            with self.subTest(case=case["name"]):
                got = signatures.verify(
                    SIG / case["index"], SIG / case["signature"] if case["signature"] else SIG / "absent.sig",
                    SIG / spec["allowed_signers"], spec["namespace"], verify_time=case["verify_time"],
                )
                self.assertEqual(got, case["expected"])

    def test_a_missing_ssh_keygen_is_an_error_not_a_verdict(self) -> None:
        with mock.patch.object(signatures.shutil, "which", return_value=None), self.assertRaises(signatures.ToolMissing):
            signatures.verify(SIG / "index.json", SIG / "current.sig", SIG / "allowed_signers", "agtmls-index@v1")

    def test_a_missing_trust_file_is_unsigned(self) -> None:
        self.assertEqual(signatures.verify(SIG / "index.json", SIG / "current.sig", SIG / "absent", "agtmls-index@v1"), "unsigned")


class AdvisoryVectorTests(unittest.TestCase):
    def test_every_spec_advisory_vector(self) -> None:
        spec = json.loads((ADV / "cases.json").read_text(encoding="utf-8"))
        feed = json.loads((ADV / spec["feed"]).read_text(encoding="utf-8"))
        self.assertEqual(advisories.feed_problems(feed), [])
        for case in spec["cases"]:
            with self.subTest(case=case["name"]):
                sig = ADV / case["signature"] if case["signature"] else ADV / "absent.sig"
                status = signatures.verify(ADV / spec["feed"], sig, ADV / spec["allowed_signers"], spec["namespace"], verify_time=spec["verify_time"])
                if status != "verified":
                    self.assertEqual((status, []), (case["expected"], case["advisories"]))
                    continue
                ids = sorted({i for _, _, found in advisories.revoked(feed, case["lockfile"]) for i in found})
                self.assertEqual(("revoked" if ids else "clean", ids), (case["expected"], case["advisories"]))

    def test_malformed_advisories_are_named(self) -> None:
        bad = {"advisories": [
            {"id": "CVE-1", "published": "yesterday", "affected": []},
            {"id": "AGT-ADV-2026-001", "modified": "2026-09-24T00:00:00Z", "affected": [{"package": {"ecosystem": "PyPI"}, "ecosystem_specific": {"digests": ["md5:x"]}}]},
            {"id": "AGT-ADV-2026-001", "modified": "2026-09-24T00:00:00Z", "affected": [{"package": {"ecosystem": "AgtMLS"}, "ecosystem_specific": {"digests": ["sha256:" + "0" * 64]}}]},
        ]}
        problems = " | ".join(advisories.feed_problems(bad))
        for text in ("not AGT-ADV-YYYY-NNN", "published is not", "OSV requires modified", "no affected", "ecosystem is not AgtMLS", "sha256: digests", "not unique"):
            self.assertIn(text, problems)


class VerifyCommandTests(unittest.TestCase):
    """agtmls verify with --signatures and a feed, over a signed fixture registry."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._workspace = Path(tempfile.mkdtemp(prefix="agtmls-trust-"))
        cls.fixture = registry_fixture(cls._workspace / "tree")
        cls.key = cls._workspace / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", str(cls.key)], check=True)
        pub = " ".join(cls.key.with_suffix(".pub").read_text().split()[:2])
        (cls.fixture / "ALLOWED_SIGNERS").write_text(
            f'agtmls-release namespaces="agtmls-index@v1,agtmls-advisory@v1" {pub}\n', encoding="utf-8",
        )
        cls.cli = load_script("agtmls.py")
        retarget(cls.cli, cls.fixture)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def setUp(self) -> None:
        self.target = Path(tempfile.mkdtemp(prefix="agtmls-trust-target-"))
        self.addCleanup(shutil.rmtree, self.target, True)
        skill = self.fixture / "skills" / "using-agtmls"
        installed = self.target / ".claude" / "skills" / "using-agtmls"
        shutil.copytree(skill, installed)
        self.digest = lockfile.build(self.target, self.fixture, ["using-agtmls"], "copy", "0.0.0")["skills"][0]["integrity"]
        lockfile.write(self.target, lockfile.build(self.target, self.fixture, ["using-agtmls"], "copy", "0.0.0"))
        for name in ("index.json.sig", "advisories.json", "advisories.json.sig"):
            self.addCleanup((self.fixture / name).unlink, True)

    def sign(self, name: str, namespace: str) -> None:
        # ssh-keygen asks before overwriting a .sig and waits on stdin forever.
        (self.fixture / f"{name}.sig").unlink(missing_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(self.key), "-n", namespace, str(self.fixture / name)],
                       check=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=30)

    def feed(self, digest: str, withdrawn: bool = False) -> None:
        advisory = {"id": "AGT-ADV-2026-001", "modified": "2026-09-24T00:00:00Z",
                    "affected": [{"package": {"ecosystem": "AgtMLS", "name": "using-agtmls"}, "ecosystem_specific": {"digests": [digest]}}]}
        if withdrawn:
            advisory["withdrawn"] = "2026-09-24T00:00:00Z"
        (self.fixture / "advisories.json").write_text(json.dumps({"schema_version": 1, "advisories": [advisory]}), encoding="utf-8")

    def verify(self, *extra: str) -> tuple[int, str]:
        return run_main(self.cli, "verify", "claude", "--target", str(self.target), *extra)

    def test_signatures_required_and_absent_is_unsigned(self) -> None:
        code, output = self.verify("--signatures")
        self.assertEqual(code, 4, output)
        self.assertIn("UNSIGNED", output)

    def test_a_signed_index_verifies(self) -> None:
        self.sign("index.json", "agtmls-index@v1")
        code, output = self.verify("--signatures")
        self.assertEqual(code, 0, output)
        self.assertIn("index.json signature verified", output)

    def test_a_signature_in_the_wrong_namespace_is_bad(self) -> None:
        self.sign("index.json", "agtmls-advisory@v1")
        code, output = self.verify("--signatures")
        self.assertEqual(code, 5, output)

    def test_a_revoked_install_exits_6_and_names_the_advisory(self) -> None:
        self.feed(self.digest)
        self.sign("advisories.json", "agtmls-advisory@v1")
        code, output = self.verify()
        self.assertEqual(code, 6, output)
        self.assertIn("REVOKED", output)
        self.assertIn("AGT-ADV-2026-001", output)

    def test_a_withdrawn_advisory_revokes_nothing(self) -> None:
        self.feed(self.digest, withdrawn=True)
        self.sign("advisories.json", "agtmls-advisory@v1")
        self.assertEqual(self.verify()[0], 0)

    def test_an_unverified_feed_is_not_consulted(self) -> None:
        self.feed(self.digest)
        code, output = self.verify()
        self.assertEqual(code, 0, output)
        self.assertIn("advisories.json is not signed; not consulted", output)
        code, output = self.verify("--signatures")
        self.assertEqual(code, 4, "an unsigned feed under --signatures is unsigned")

    def test_a_tampered_feed_outranks_the_revocation_it_carries(self) -> None:
        self.feed(self.digest)
        self.sign("advisories.json", "agtmls-advisory@v1")
        (self.fixture / "advisories.json").write_text((self.fixture / "advisories.json").read_text() + " ", encoding="utf-8")
        code, output = self.verify()
        self.assertEqual(code, 5, output)

    def test_integrity_outranks_revocation(self) -> None:
        self.feed(self.digest)
        self.sign("advisories.json", "agtmls-advisory@v1")
        installed = self.target / ".claude" / "skills" / "using-agtmls" / "SKILL.md"
        installed.write_text(installed.read_text() + "edited\n", encoding="utf-8")
        self.assertEqual(self.verify()[0], 3)

    def test_json_output_carries_signature_and_revocations(self) -> None:
        self.feed(self.digest)
        self.sign("advisories.json", "agtmls-advisory@v1")
        code, output = self.verify("--json")
        data = json.loads(output)
        self.assertEqual(code, 6)
        self.assertEqual(data["revoked"], [{"skill": "using-agtmls", "digest": self.digest, "advisories": ["AGT-ADV-2026-001"]}])
        self.assertEqual(data["advisory_feed"], "verified")

    def test_a_missing_ssh_keygen_is_an_error(self) -> None:
        self.sign("index.json", "agtmls-index@v1")
        with mock.patch.object(signatures.shutil, "which", return_value=None):
            code, output = self.verify("--signatures")
        self.assertEqual(code, 1, output)
        self.assertIn("ssh-keygen", output)


if __name__ == "__main__":
    unittest.main()


class TrustCheckTests(unittest.TestCase):
    """trust-check.py: one judgement per call, for the spec's conformance runner."""

    def setUp(self) -> None:
        self.mod = load_script("trust-check.py")

    def run_check(self, *args: str) -> tuple[int, str]:
        return run_main(self.mod, *args)

    def test_every_signature_vector_exits_as_the_spec_says(self) -> None:
        spec = json.loads((SIG / "cases.json").read_text(encoding="utf-8"))
        exits = {"verified": 0, "bad_signature": 5, "unsigned": 4}
        for case in spec["cases"]:
            with self.subTest(case=case["name"]):
                sig = SIG / case["signature"] if case["signature"] else SIG / "absent.sig"
                code, out = self.run_check(
                    "signature", str(SIG / case["index"]), "--sig", str(sig),
                    "--allowed-signers", str(SIG / spec["allowed_signers"]),
                    "--namespace", spec["namespace"], "--verify-time", case["verify_time"], "--json")
                self.assertEqual((code, json.loads(out)), (exits[case["expected"]], {"status": case["expected"]}))

    def test_every_advisory_vector_exits_as_the_spec_says(self) -> None:
        spec = json.loads((ADV / "cases.json").read_text(encoding="utf-8"))
        exits = {"clean": 0, "revoked": 6, "bad_signature": 5, "unsigned": 4}
        with tempfile.TemporaryDirectory() as raw:
            for case in spec["cases"]:
                with self.subTest(case=case["name"]):
                    lock = Path(raw) / f"{case['name']}.json"
                    lock.write_text(json.dumps(case["lockfile"]), encoding="utf-8")
                    sig = ADV / case["signature"] if case["signature"] else ADV / "absent.sig"
                    code, out = self.run_check(
                        "advisories", str(ADV / spec["feed"]), "--sig", str(sig),
                        "--allowed-signers", str(ADV / spec["allowed_signers"]),
                        "--lockfile", str(lock), "--verify-time", spec["verify_time"], "--json")
                    got = json.loads(out)
                    ids = sorted({i for hit in got["revoked"] for i in hit["advisories"]})
                    self.assertEqual((code, ids), (exits[case["expected"]], case["advisories"]))

    def test_the_feed_signature_defaults_to_its_sibling(self) -> None:
        spec = json.loads((ADV / "cases.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as raw:
            lock = Path(raw) / "lock.json"
            lock.write_text(json.dumps(spec["cases"][0]["lockfile"]), encoding="utf-8")
            code, out = self.run_check(
                "advisories", str(ADV / spec["feed"]), "--allowed-signers", str(ADV / spec["allowed_signers"]),
                "--lockfile", str(lock), "--verify-time", spec["verify_time"])
        self.assertEqual(code, 6)
        self.assertIn("REVOKED compromised-skill", out)
        self.assertTrue(out.startswith("verified"))

    def test_text_output_of_a_signature(self) -> None:
        code, out = self.run_check(
            "signature", str(SIG / "index.json"), "--sig", str(SIG / "absent.sig"),
            "--allowed-signers", str(SIG / "allowed_signers"), "--namespace", "agtmls-index@v1")
        self.assertEqual((code, out.strip()), (4, "unsigned"))

    def test_a_verify_time_that_is_not_a_date_is_a_usage_error(self) -> None:
        code, out = self.run_check(
            "signature", str(SIG / "index.json"), "--sig", str(SIG / "current.sig"),
            "--allowed-signers", str(SIG / "allowed_signers"), "--namespace", "n", "--verify-time=-Oprint")
        self.assertEqual(code, 2)
        self.assertIn("is not YYYYMMDD", out)

    def test_the_library_refuses_a_malformed_verify_time(self) -> None:
        with self.assertRaises(ValueError):
            signatures.verify(SIG / "index.json", SIG / "current.sig", SIG / "allowed_signers", "n", verify_time="2026")

    def test_nothing_concluded_exits_1(self) -> None:
        with mock.patch.object(signatures.shutil, "which", return_value=None):
            code, out = self.run_check(
                "signature", str(SIG / "index.json"), "--sig", str(SIG / "current.sig"),
                "--allowed-signers", str(SIG / "allowed_signers"), "--namespace", "agtmls-index@v1")
        self.assertEqual(code, 1)
        self.assertIn("ssh-keygen", out)
        with tempfile.TemporaryDirectory() as raw:
            bad = Path(raw) / "lock.json"
            bad.write_text("{not json", encoding="utf-8")
            code, out = self.run_check(
                "advisories", str(ADV / "feed.json"), "--allowed-signers", str(ADV / "allowed_signers"),
                "--lockfile", str(bad))
        self.assertEqual(code, 1)
