# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Signing and verifying attestations (agtmls-spec 10.7).

The release signs every attestation under `agtmls-attestation@v1`, as it
signs the index. These tests use a throwaway key, made here and discarded,
listed in a throwaway ALLOWED_SIGNERS: the release key never leaves CI.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import load_script, run_main


@unittest.skipIf(shutil.which("ssh-keygen") is None, "ssh-keygen is not installed")
class SignAttestationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agtmls-sign-att-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.key = self.root / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", str(self.key)], check=True)
        public = (self.root / "key.pub").read_text(encoding="utf-8").strip()
        (self.root / "ALLOWED_SIGNERS").write_text(
            f'agtmls-release namespaces="agtmls-attestation@v1" {public}\n', encoding="utf-8")
        for skill in ("one", "two"):
            folder = self.root / "attestations" / skill
            folder.mkdir(parents=True)
            (folder / "manifest.intoto.json").write_text(f'{{"skill": "{skill}"}}\n', encoding="utf-8")
        self.script = load_script("sign-attestations.py")

    def run_script(self, *args: str) -> tuple[int, str]:
        return run_main(self.script, "--root", str(self.root), *args)

    def test_signed_attestations_verify(self) -> None:
        code, out = self.run_script("--key", str(self.key))
        self.assertEqual(code, 0, out)
        self.assertIn("OK: signed and verified 2 attestation(s)", out)
        self.assertTrue((self.root / "attestations/one/manifest.intoto.json.sig").is_file())
        code, out = self.run_script("--verify")
        self.assertEqual((code, out.strip()), (0, "OK: 2 attestation(s) verify against ALLOWED_SIGNERS"))

    def test_a_changed_or_unsigned_attestation_is_named(self) -> None:
        self.run_script("--key", str(self.key))
        (self.root / "attestations/one/manifest.intoto.json").write_text('{"skill": "edited"}\n', encoding="utf-8")
        (self.root / "attestations/two/manifest.intoto.json.sig").unlink()
        code, out = self.run_script("--verify")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: attestations/one/manifest.intoto.json: bad_signature", out)
        self.assertIn("FAIL: attestations/two/manifest.intoto.json: unsigned", out)

    def test_a_signature_by_a_key_nobody_trusts_fails(self) -> None:
        other = self.root / "other"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(other)], check=True)
        self.assertEqual(self.run_script("--key", str(other))[0], 1)

    def test_nothing_to_sign_is_an_error(self) -> None:
        shutil.rmtree(self.root / "attestations")
        code, out = self.run_script("--verify")
        self.assertEqual((code, out.strip()), (1, "FAIL: no attestations under attestations/"))

    def test_signing_that_fails_stops_with_what_ssh_keygen_said(self) -> None:
        code, out = self.run_script("--key", str(self.root / "no-such-key"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: could not sign attestations/one/manifest.intoto.json", out)

    def test_no_ssh_keygen_is_an_error_not_a_verdict(self) -> None:
        with mock.patch.object(self.script.shutil, "which", return_value=None):
            code, out = self.run_script("--verify")
        self.assertEqual((code, out.strip()), (1, "FAIL: ssh-keygen is not installed; signatures cannot be verified"))



@unittest.skipIf(shutil.which("ssh-keygen") is None, "ssh-keygen is not installed")
class ReleaseAuditTests(unittest.TestCase):
    """release-audit.py checks the attestations the published wheel carries."""

    COMMIT = "c" * 40

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agtmls-audit-att-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        key = self.root / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        public = (self.root / "key.pub").read_text(encoding="utf-8").strip()
        self.signers = f'agtmls-release namespaces="agtmls-attestation@v1" {public}\n'.encode()
        self.files = {"attestations/one/manifest.intoto.json": b'{"skill": "one"}\n',
                      "attestations/one/efficacy.intoto.json": b'{"meets_bar": true}\n'}
        self.sigs = {}
        for rel, data in self.files.items():
            path = self.root / "sign" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", "agtmls-attestation@v1",
                            str(path)], check=True)
            self.sigs[rel + ".sig"] = path.with_name(path.name + ".sig").read_bytes()
        self.mod = load_script("release-audit.py")
        self.signing_era = True
        self.wheel = self.make_wheel({**self.files, **self.sigs})

    def make_wheel(self, members: dict[str, bytes]) -> bytes:
        import io
        import zipfile
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as wheel:
            wheel.writestr("agtmls/__init__.py", "")
            for rel, data in members.items():
                wheel.writestr("agtmls/_registry/" + rel, data)
        return buffer.getvalue()

    def fetch(self, *cmd: str) -> bytes | None:
        if cmd[:2] == ("git", "show"):
            rel = cmd[2].split(":", 1)[1]
            if rel == "scripts/sign-attestations.py":
                return b"#!" if self.signing_era else None
            return self.signers if rel == "ALLOWED_SIGNERS" else self.files.get(rel)
        if cmd[:2] == ("git", "ls-tree"):
            return "".join(f"{rel}\n" for rel in self.files).encode()
        return self.wheel if cmd[-1].endswith("/7") else None

    def audit(self, assets: list[dict] | None = None) -> list[str]:
        assets = [{"name": "agtmls-0.0.20-py3-none-any.whl", "id": 7}] if assets is None else assets
        with mock.patch.object(self.mod, "fetch_bytes", self.fetch):
            return self.mod.audit_attestations(self.COMMIT, "o/r", assets)

    def test_the_commits_attestations_signed_in_the_wheel_pass(self) -> None:
        self.assertEqual(self.audit(), [])

    def test_a_release_from_before_attestations_were_signed_is_not_asked(self) -> None:
        self.signing_era = False
        self.assertEqual(self.audit([]), [])

    def test_no_wheel_or_an_unreadable_one_is_named(self) -> None:
        self.assertIn("no wheel", self.audit([])[0])
        self.assertIn("could not be read back", self.audit([{"name": "x.whl", "id": 8}])[0])

    def test_an_unsigned_or_altered_attestation_in_the_wheel_fails(self) -> None:
        altered = {**self.files, "attestations/one/efficacy.intoto.json": b'{"meets_bar": false}\n'}
        self.wheel = self.make_wheel({**altered, **self.sigs})
        errors = self.audit()
        self.assertTrue(any("efficacy.intoto.json differs from the commit" in e for e in errors), errors)
        self.assertTrue(any("efficacy.intoto.json: bad_signature" in e for e in errors), errors)
        self.wheel = self.make_wheel({**self.files, "attestations/one/manifest.intoto.json.sig":
                                      self.sigs["attestations/one/manifest.intoto.json.sig"]})
        self.assertTrue(any("efficacy.intoto.json: unsigned" in e for e in self.audit()))

    def test_a_wheel_missing_one_of_the_commits_attestations_fails(self) -> None:
        self.wheel = self.make_wheel({"attestations/one/manifest.intoto.json": self.files["attestations/one/manifest.intoto.json"],
                                      "attestations/one/manifest.intoto.json.sig": self.sigs["attestations/one/manifest.intoto.json.sig"]})
        self.assertIn("attestations/one/efficacy.intoto.json is not in the wheel", " ".join(self.audit()))

if __name__ == "__main__":
    unittest.main()
