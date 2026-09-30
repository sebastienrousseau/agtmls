# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A built wheel carries a signed index and signed attestations.

The release signs in one job and builds in another, from the sdist. A
signature that never reaches the wheel, or a wheel built from files that
were not the signed ones, used to show up only after publishing. The
release now checks the wheel itself before anything is published, with the
same code these tests drive, and release-audit reads the published wheel
the same way.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from .support import ROOT, load_script, run_main

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import wheel_signatures  # needs the scripts path first

REG = "agtmls/_registry/"


@unittest.skipIf(shutil.which("ssh-keygen") is None, "ssh-keygen is not installed")
class WheelSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="agtmls-wheel-sig-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.key = self.root / "key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        public = (self.root / "key.pub").read_text(encoding="utf-8").strip()
        self.signers = (f'agtmls-release namespaces="agtmls-index@v1,agtmls-attestation@v1" {public}\n').encode()
        self.members = {"index.json": b'{"skills": []}\n', "ALLOWED_SIGNERS": self.signers,
                        "attestations/one/manifest.intoto.json": b'{"one": 1}\n'}
        for rel, namespace in (("index.json", "agtmls-index@v1"),
                               ("attestations/one/manifest.intoto.json", "agtmls-attestation@v1")):
            self.members[rel + ".sig"] = self.sign(self.members[rel], namespace)

    def sign(self, data: bytes, namespace: str) -> bytes:
        path = self.root / "tosign"
        path.write_bytes(data)
        Path(str(path) + ".sig").unlink(missing_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(self.key), "-n", namespace, str(path)], check=True)
        return Path(str(path) + ".sig").read_bytes()

    def wheel(self, members: dict[str, bytes] | None = None) -> Path:
        path = self.root / "agtmls-0.0.20-py3-none-any.whl"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("agtmls/__init__.py", "")
            for rel, data in (self.members if members is None else members).items():
                archive.writestr(REG + rel, data)
        path.write_bytes(buffer.getvalue())
        return path

    def test_a_fully_signed_wheel_passes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry = wheel_signatures.extract_registry(self.wheel().read_bytes(), Path(raw))
            self.assertEqual(wheel_signatures.problems(registry), [])
        code, out = run_main(load_script("verify-wheel-signatures.py"), str(self.wheel()))
        self.assertEqual(code, 0, out)
        self.assertIn("OK: index.json and 1 attestation(s) in agtmls-0.0.20-py3-none-any.whl verify", out)

    def test_every_missing_or_bad_signature_is_named(self) -> None:
        members = {**self.members, "index.json": b'{"skills": ["changed"]}\n'}
        del members["attestations/one/manifest.intoto.json.sig"]
        code, out = run_main(load_script("verify-wheel-signatures.py"), str(self.wheel(members)))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: index.json: bad_signature", out)
        self.assertIn("FAIL: attestations/one/manifest.intoto.json: unsigned", out)

    def test_other_keys_can_be_named_to_judge_by(self) -> None:
        stranger = self.root / "stranger"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(stranger)], check=True)
        signers = self.root / "signers"
        signers.write_text('agtmls-release namespaces="agtmls-index@v1,agtmls-attestation@v1" '
                           + (self.root / "stranger.pub").read_text(encoding="utf-8"), encoding="utf-8")
        code, out = run_main(load_script("verify-wheel-signatures.py"), str(self.wheel()), "--signers", str(signers))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: index.json: bad_signature", out)

    def test_a_wheel_with_nothing_attested_or_no_wheel_is_refused(self) -> None:
        bare = {rel: data for rel, data in self.members.items() if not rel.startswith("attestations/")}
        code, out = run_main(load_script("verify-wheel-signatures.py"), str(self.wheel(bare)))
        self.assertEqual((code, "FAIL: the wheel carries no attestations" in out), (1, True))
        code, out = run_main(load_script("verify-wheel-signatures.py"), str(self.root / "none.whl"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: cannot read", out)

    def test_the_release_signing_script_signs_what_the_wheel_checks(self) -> None:
        tree = self.root / "tree"
        (tree / "attestations" / "one").mkdir(parents=True)
        (tree / "scripts").mkdir()
        shutil.copy(ROOT / "scripts" / "sign-attestations.py", tree / "scripts")
        shutil.copytree(ROOT / "scripts" / "_lib", tree / "scripts" / "_lib")
        for rel in ("index.json", "ALLOWED_SIGNERS", "attestations/one/manifest.intoto.json"):
            (tree / rel).write_bytes(self.members[rel])
        proc = subprocess.run(["bash", str(ROOT / "scripts" / "sign-release.sh"), str(self.key)],
                              cwd=tree, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue((tree / "index.json.sig").is_file())
        self.assertEqual(wheel_signatures.problems(tree), [])


if __name__ == "__main__":
    unittest.main()
