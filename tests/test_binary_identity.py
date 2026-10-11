# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Tests for binary identity and runtime environment verification."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _lib.binary_identity import (
    RuntimeIdentity,
    current_runtime_identity,
    detect_virtual_env,
    hash_file,
    verify_binary,
    verify_runtime_environment,
)


class HashFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_hash_file_computes_sha256(self) -> None:
        test_file = self.tmp_path / "hello.bin"
        content = b"test binary payload \x00\x01\x02"
        test_file.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        self.assertEqual(hash_file(test_file), expected)

    def test_hash_file_raises_on_missing_file(self) -> None:
        missing = self.tmp_path / "nonexistent.bin"
        with self.assertRaises(FileNotFoundError):
            hash_file(missing)

    def test_hash_file_resolves_symlink(self) -> None:
        target = self.tmp_path / "target.txt"
        target.write_text("symlink-target-content", encoding="utf-8")
        link = self.tmp_path / "link.txt"
        link.symlink_to(target)
        self.assertEqual(hash_file(link), hash_file(target))


class VirtualEnvDetectionTests(unittest.TestCase):
    def test_detect_virtual_env_from_env_var(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.dict(os.environ, {"VIRTUAL_ENV": tmpdir}),
        ):
            self.assertEqual(detect_virtual_env(), str(Path(tmpdir).resolve()))

    def test_detect_virtual_env_none_when_empty_and_matching(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(sys, "prefix", "/usr"),
            patch.object(sys, "base_prefix", "/usr"),
        ):
            self.assertIsNone(detect_virtual_env())

    def test_detect_virtual_env_from_prefix_fallback(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(sys, "prefix", "/env/path"),
            patch.object(sys, "base_prefix", "/usr"),
        ):
            self.assertEqual(detect_virtual_env(), "/env/path")

    def test_detect_virtual_env_nonexistent_env_var(self) -> None:
        with (
            patch.dict(os.environ, {"VIRTUAL_ENV": "/nonexistent/venv"}),
            patch.object(sys, "prefix", "/usr"),
            patch.object(sys, "base_prefix", "/usr"),
        ):
            self.assertIsNone(detect_virtual_env())


class CurrentRuntimeIdentityTests(unittest.TestCase):
    def test_current_runtime_identity_structure(self) -> None:
        identity = current_runtime_identity()
        self.assertIsInstance(identity, RuntimeIdentity)
        self.assertTrue(Path(identity.executable_path).exists())
        self.assertEqual(len(identity.executable_sha256), 64)
        as_dict = identity.to_dict()
        self.assertIn("executable_path", as_dict)
        self.assertIn("executable_sha256", as_dict)
        self.assertIn("python_version", as_dict)


class VerifyBinaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_verify_binary_success(self) -> None:
        binary = self.tmp_path / "tool"
        binary.write_bytes(b"content")
        valid_digest = hashlib.sha256(b"content").hexdigest()
        ok, msg = verify_binary(binary, valid_digest)
        self.assertTrue(ok)
        self.assertIn("matches", msg)

    def test_verify_binary_mismatch(self) -> None:
        binary = self.tmp_path / "tool"
        binary.write_bytes(b"content")
        ok, msg = verify_binary(binary, "0000000000000000000000000000000000000000000000000000000000000000")
        self.assertFalse(ok)
        self.assertIn("Hash mismatch", msg)

    def test_verify_binary_missing_file(self) -> None:
        missing = self.tmp_path / "missing"
        ok, msg = verify_binary(missing, "any")
        self.assertFalse(ok)
        self.assertIn("Failed to inspect executable", msg)


class VerifyRuntimeEnvironmentTests(unittest.TestCase):
    def test_verify_runtime_environment_all_pass(self) -> None:
        identity = RuntimeIdentity(
            executable_path="/usr/bin/python3",
            executable_sha256="abc12345",
            python_version="3.12.0",
            platform_system="Linux",
            platform_machine="x86_64",
            virtual_env=None,
        )
        expected = {
            "python_version": "3.12.0",
            "platform_system": "Linux",
            "platform_machine": "x86_64",
            "executable_sha256": "abc12345",
        }
        ok, mismatches = verify_runtime_environment(expected, identity)
        self.assertTrue(ok)
        self.assertEqual(mismatches, [])

    def test_verify_runtime_environment_mismatches(self) -> None:
        identity = RuntimeIdentity(
            executable_path="/usr/bin/python3",
            executable_sha256="abc12345",
            python_version="3.12.0",
            platform_system="Linux",
            platform_machine="x86_64",
            virtual_env=None,
        )
        expected = {
            "python_version": "3.14.0",
            "platform_system": "Darwin",
        }
        ok, mismatches = verify_runtime_environment(expected, identity)
        self.assertFalse(ok)
        self.assertEqual(len(mismatches), 2)
        self.assertIn("python_version", mismatches[0])
        self.assertIn("platform_system", mismatches[1])
