# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Packing, rehearsing and auditing a release, with nothing published.

`release-pack.py` writes the artifacts and their checksums, `release-dry-run.py`
rehearses the whole sequence, `release-check.py` chains the release gates, and
`verify-release-assets.py` reads a published release back. The gate runs none
of them, and the audit one only ever runs *after* a release is public -- which
is the worst moment to learn that it cannot tell a corrupted asset from a good
one.

Every subprocess and download is faked. What is under test is the decision
each script makes about what it was handed, not the network or `gh`.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import load_script, retarget, run_main

#: What a provider tarball must contain for verify-release-assets to accept it.
MEMBERS = ("agtmls/index.json", "agtmls/export-manifest.json", "agtmls/ADAPTERS.md")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tarball(path: Path, members: tuple[str, ...] = MEMBERS) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tf:
        for name in members:
            data = f"{name}\n".encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


def write_release(out_dir: Path, providers: list[str], profile: str = "polyglot") -> list[Path]:
    """What a correct release-pack run leaves behind."""
    artifacts = [tarball(out_dir / f"agtmls-{p}-{profile}.tar.gz") for p in providers]
    (out_dir / "SHA256SUMS").write_text(
        "".join(f"{digest(a)}  {a.name}\n" for a in artifacts), encoding="utf-8"
    )
    manifest = {"artifacts": [{"file": a.name, "sha256": digest(a)} for a in artifacts]}
    (out_dir / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return artifacts


def minimal_tree(root: Path, version: str = "0.0.3") -> Path:
    """Only the two files these scripts read; a full registry copy buys nothing."""
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "agtmls", "version": version}), encoding="utf-8"
    )
    (root / "providers.json").write_text(
        json.dumps({"export_targets": {"openai": {}, "generic": {}}}), encoding="utf-8"
    )
    return root


class TreeCase(unittest.TestCase):
    """One throwaway tree per class, and a scratch directory per test."""

    tree: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._base = Path(tempfile.mkdtemp(prefix="agtmls-pipe-")).resolve()
        cls.tree = minimal_tree(cls._base / "tree")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._base, ignore_errors=True)

    def scratch(self) -> Path:
        path = Path(tempfile.mkdtemp(prefix="scratch-", dir=self._base))
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def script(self, name: str):
        """Loaded once per class; cases patch attributes, never assign them."""
        cache = self.__class__.__dict__.get("_loaded")
        if cache is None:
            cache = self.__class__._loaded = {}
        if name not in cache:
            module = load_script(name)
            retarget(module, self.tree)
            cache[name] = module
        return cache[name]


class ReleasePackTests(TreeCase):
    """The checksums a release publishes are only as good as what wrote them."""

    def fake_export(self, failing: str | None = None):
        """Stand in for export-registry.py: write the tarball it would write."""
        calls: list[list[str]] = []

        def call(cmd, cwd=None):
            calls.append(cmd)
            provider = cmd[cmd.index("--provider") + 1]
            if provider == failing:
                return 3
            out = Path(cmd[cmd.index("--out-dir") + 1])
            profile = cmd[cmd.index("--profile") + 1]
            tarball(out / f"agtmls-{provider}-{profile}.tar.gz")
            return 0

        return calls, call

    def test_sums_and_manifest_describe_exactly_the_artifacts_written(self) -> None:
        module = self.script("release-pack.py")
        out = self.scratch() / "release"
        calls, call = self.fake_export()
        with mock.patch.object(module.subprocess, "call", side_effect=call):
            code, output = run_main(module, "--out-dir", str(out))
        self.assertEqual(code, 0, output)
        self.assertEqual(output.strip(), str(out))
        # Providers default to the registry's export targets, sorted.
        self.assertEqual([c[c.index("--provider") + 1] for c in calls], ["generic", "openai"])
        self.assertTrue(all(Path(c[1]).name == "export-registry.py" for c in calls))
        lines = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        expected = [f"{digest(out / n)}  {n}" for n in
                    ("agtmls-generic-polyglot.tar.gz", "agtmls-openai-polyglot.tar.gz")]
        self.assertEqual(lines, expected)
        manifest = json.loads((out / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["profile"], "polyglot")
        self.assertEqual(
            [(a["file"], a["sha256"]) for a in manifest["artifacts"]],
            [tuple(line.split("  ")[::-1]) for line in lines],
        )

    def test_an_explicit_provider_and_profile_are_honoured(self) -> None:
        module = self.script("release-pack.py")
        out = self.scratch() / "release"
        calls, call = self.fake_export()
        with mock.patch.object(module.subprocess, "call", side_effect=call):
            code, output = run_main(module, "--out-dir", str(out), "--profile", "minimal",
                                    "--provider", "openai")
        self.assertEqual(code, 0, output)
        self.assertEqual(len(calls), 1)
        manifest = json.loads((out / "release-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([a["file"] for a in manifest["artifacts"]],
                         ["agtmls-openai-minimal.tar.gz"])

    def test_a_failed_export_stops_before_any_checksum_is_written(self) -> None:
        """Summing a partial set would publish a release missing a provider."""
        module = self.script("release-pack.py")
        out = self.scratch() / "release"
        _, call = self.fake_export(failing="generic")
        with mock.patch.object(module.subprocess, "call", side_effect=call):
            code, _ = run_main(module, "--out-dir", str(out))
        self.assertEqual(code, 3)
        self.assertFalse((out / "SHA256SUMS").exists())
        self.assertFalse((out / "release-manifest.json").exists())

    def test_a_registry_with_no_export_targets_is_refused(self) -> None:
        module = self.script("release-pack.py")
        for targets in ({}, ["openai"]):
            providers = self.scratch() / "providers.json"
            providers.write_text(json.dumps({"export_targets": targets}), encoding="utf-8")
            with mock.patch.object(module, "PROVIDERS", providers), \
                    self.assertRaises(SystemExit) as caught:
                module.default_providers()
            self.assertIn("export_targets", str(caught.exception))


class ReleaseCheckTests(TreeCase):
    """The release gate is a chain; a broken link must stop it."""

    def test_every_release_check_runs_in_order_from_the_registry_root(self) -> None:
        module = self.script("release-check.py")
        with mock.patch.object(module.subprocess, "call", return_value=0) as call:
            code, output = run_main(module)
        self.assertEqual(code, 0, output)
        self.assertIn("OK: release check passed", output)
        ran = [(Path(c.args[0][1]).name, c.args[0][2:]) for c in call.call_args_list]
        self.assertEqual(ran, [(c[0], c[1:]) for c in module.CHECKS])
        self.assertTrue(all(c.kwargs["cwd"] == self.tree for c in call.call_args_list))

    def test_the_first_failure_stops_the_chain_and_is_its_exit_code(self) -> None:
        module = self.script("release-check.py")
        with mock.patch.object(module.subprocess, "call", side_effect=[0, 0, 5, 0]) as call:
            code, output = run_main(module)
        self.assertEqual(code, 5)
        self.assertEqual(call.call_count, 3, "checks kept running after one failed")
        self.assertNotIn("OK:", output)


class VerifySumsTests(TreeCase):
    """The dry run's own reading of what release-pack wrote."""

    def setUp(self) -> None:
        self.mod = self.script("release-dry-run.py")
        self.out = self.scratch()

    def test_a_consistent_release_has_no_issues(self) -> None:
        write_release(self.out, ["openai", "generic"])
        self.assertEqual(self.mod.verify_sums(self.out), [])

    def test_missing_checksums_are_the_only_thing_reported(self) -> None:
        self.assertEqual(self.mod.verify_sums(self.out), ["SHA256SUMS missing"])

    def test_a_missing_manifest_is_reported(self) -> None:
        write_release(self.out, ["openai"])
        (self.out / "release-manifest.json").unlink()
        self.assertEqual(self.mod.verify_sums(self.out), ["release-manifest.json missing"])

    def test_an_artifact_listed_but_absent_is_reported(self) -> None:
        artifact = write_release(self.out, ["openai"])[0]
        artifact.unlink()
        errors = self.mod.verify_sums(self.out)
        self.assertEqual(errors, [f"artifact listed in SHA256SUMS is missing: {artifact.name}"])

    def test_a_tampered_artifact_is_reported(self) -> None:
        artifact = write_release(self.out, ["openai"])[0]
        artifact.write_bytes(b"not the tarball that was summed")
        errors = self.mod.verify_sums(self.out)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].startswith(f"checksum mismatch for {artifact.name}"))

    def test_a_blank_line_in_the_checksums_is_not_a_crash(self) -> None:
        write_release(self.out, ["openai"])
        sums = self.out / "SHA256SUMS"
        sums.write_text("\n" + sums.read_text(encoding="utf-8") + "\nbroken\n", encoding="utf-8")
        self.assertEqual(self.mod.verify_sums(self.out),
                         ["SHA256SUMS line 4 is not '<sha256>  <file>': 'broken'"])

    def test_a_manifest_disagreeing_with_the_checksums_is_reported(self) -> None:
        write_release(self.out, ["openai", "generic"])
        manifest = self.out / "release-manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["artifacts"].pop()
        manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.mod.verify_sums(self.out),
                         ["release manifest artifact list does not match SHA256SUMS"])


class ReleaseDryRunTests(TreeCase):
    """A rehearsal that passes when the release would fail is worse than none."""

    def drive(self, *args: str, next_rc: int = 0, next_out: str = "0.0.3\n",
              tag_exists: bool = False, failing: str | None = None,
              corrupt: bool = False) -> tuple[int, str, list[list[str]]]:
        module = self.script("release-dry-run.py")
        calls: list[list[str]] = []

        def run(cmd, **kwargs):
            if Path(cmd[-1]).name == "next-version.py":
                return subprocess.CompletedProcess(cmd, next_rc, next_out, "no tags" if next_rc else "")
            self.assertEqual(cmd[:4], ["git", "rev-parse", "--verify", "--quiet"])
            return subprocess.CompletedProcess(cmd, 0 if tag_exists else 1)

        def call(cmd, cwd=None):
            calls.append(cmd)
            self.assertEqual(cwd, self.tree)
            name = Path(cmd[1]).name
            if name == failing:
                return 7
            if name == "release-pack.py":
                out = Path(cmd[cmd.index("--out-dir") + 1])
                out.mkdir(parents=True)
                providers = [cmd[i + 1] for i, x in enumerate(cmd) if x == "--provider"]
                artifacts = write_release(out, providers, cmd[cmd.index("--profile") + 1])
                if corrupt:
                    artifacts[0].write_bytes(b"tampered")
            return 0

        with mock.patch.object(module.subprocess, "run", side_effect=run), \
                mock.patch.object(module.subprocess, "call", side_effect=call):
            code, output = run_main(module, *args)
        return code, output, calls

    def test_a_clean_rehearsal_runs_every_gate_then_packs(self) -> None:
        code, output, calls = self.drive()
        self.assertEqual(code, 0, output)
        self.assertIn("OK: release dry-run passed for 0.0.3 with 2 artifact(s)", output)
        self.assertEqual(
            [Path(c[1]).name for c in calls],
            ["run-all-checks.py", "validate-version-policy.py", "release-check.py", "release-pack.py"],
        )
        self.assertIn("$ ", output, "commands were not echoed before running")
        pack = calls[-1]
        self.assertEqual(pack[pack.index("--profile") + 1], "minimal")

    def test_skip_check_drops_only_the_full_gate(self) -> None:
        code, output, calls = self.drive("--skip-check", "--provider", "zed", "--profile", "p")
        self.assertEqual(code, 0, output)
        names = [Path(c[1]).name for c in calls]
        self.assertNotIn("run-all-checks.py", names)
        self.assertIn("validate-version-policy.py", names)
        self.assertIn("with 1 artifact(s)", output)

    def test_a_version_that_is_not_next_and_not_tagged_is_refused(self) -> None:
        code, output, calls = self.drive("--version", "0.0.5")
        self.assertEqual(code, 1)
        self.assertIn("FAIL: requested 0.0.5; next allowed release is 0.0.3", output)
        self.assertEqual(calls, [], "gates ran for a version that may not be released")

    def test_an_already_tagged_version_may_be_rehearsed_again(self) -> None:
        """Re-verifying a shipped release is what the dry run is for after the fact."""
        code, output, _ = self.drive("--version", "0.0.2", tag_exists=True)
        self.assertEqual(code, 0, output)
        self.assertIn("passed for 0.0.2", output)

    def test_a_failing_next_version_is_surfaced_with_its_exit_code(self) -> None:
        code, output, calls = self.drive(next_rc=4)
        self.assertEqual(code, 4)
        self.assertIn("no tags", output)
        self.assertEqual(calls, [])

    def test_a_failing_gate_stops_the_rehearsal_before_packing(self) -> None:
        code, _, calls = self.drive(failing="release-check.py")
        self.assertEqual(code, 7)
        self.assertNotIn("release-pack.py", [Path(c[1]).name for c in calls])

    def test_a_failing_pack_is_its_exit_code(self) -> None:
        code, output, _ = self.drive(failing="release-pack.py")
        self.assertEqual(code, 7)
        self.assertNotIn("OK:", output)

    def test_a_pack_whose_checksums_do_not_hold_fails_the_rehearsal(self) -> None:
        code, output, _ = self.drive(corrupt=True)
        self.assertEqual(code, 1)
        self.assertIn("FAIL: checksum mismatch for agtmls-generic-minimal.tar.gz", output)
        self.assertIn("FAIL: 1 release dry-run issue(s)", output)


class PublishedAssetTests(TreeCase):
    """Reading a published release back, the audit AGENTS.md makes blocking.

    `gh release download` is faked by copying a prepared release into the
    directory it was asked to fill, so each case is a statement about the
    files a release carries and nothing else.
    """

    PROVIDERS = ("agtmls-generic-polyglot.tar.gz", "agtmls-openai-polyglot.tar.gz")

    def setUp(self) -> None:
        self.mod = self.script("verify-release-assets.py")
        self.source = self.scratch()
        self.artifacts = write_release(self.source, ["generic", "openai"])

    def resum(self) -> None:
        """Re-derive SHA256SUMS and the manifest, so only one thing is wrong."""
        (self.source / "SHA256SUMS").write_text(
            "".join(f"{digest(a)}  {a.name}\n" for a in self.artifacts), encoding="utf-8"
        )
        manifest = {"artifacts": [{"file": a.name, "sha256": digest(a)} for a in self.artifacts]}
        (self.source / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def verify(self, *args: str, gh: str | None = "/usr/bin/gh", gh_rc: int = 0,
               latest: str = "v0.0.2") -> tuple[int, str, list[list[str]]]:
        commands: list[list[str]] = []

        def run(cmd, **kwargs):
            commands.append(cmd)
            if cmd[1:3] == ["release", "view"]:
                return subprocess.CompletedProcess(cmd, 0, latest + "\n")
            if gh_rc:
                return subprocess.CompletedProcess(cmd, gh_rc, "HTTP 404: release not found\n")
            target = Path(cmd[cmd.index("--dir") + 1])
            for path in self.source.iterdir():
                shutil.copy2(path, target / path.name)
            return subprocess.CompletedProcess(cmd, 0, "")

        with mock.patch.object(self.mod.shutil, "which", return_value=gh), \
                mock.patch.object(self.mod.subprocess, "run", side_effect=run), \
                mock.patch.object(self.mod, "provider_assets", return_value=list(self.PROVIDERS)):
            code, output = run_main(self.mod, *args)
        return code, output, commands

    def failures(self, output: str) -> list[str]:
        return [line[len("FAIL: "):] for line in output.splitlines() if line.startswith("FAIL: ")]

    def test_an_intact_release_verifies(self) -> None:
        code, output, commands = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 0, output)
        self.assertIn("OK: verified sebastienrousseau/agtmls v0.0.2 release assets", output)
        download = commands[-1]
        self.assertEqual(download[1:4], ["release", "download", "v0.0.2"])
        self.assertIn("--clobber", download)

    def test_latest_is_resolved_to_a_tag_before_downloading(self) -> None:
        code, output, commands = self.verify("--repo", "o/r", latest="v0.0.5")
        self.assertEqual(code, 0, output)
        self.assertEqual(commands[0][1:5], ["release", "view", "--repo", "o/r"])
        self.assertEqual(commands[1][3], "v0.0.5")

    def test_an_explicit_out_dir_keeps_the_assets(self) -> None:
        out = self.scratch() / "kept"
        code, output, _ = self.verify("--tag", "v0.0.2", "--out-dir", str(out))
        self.assertEqual(code, 0, output)
        self.assertTrue((out / "SHA256SUMS").exists())

    def test_a_failed_download_is_its_exit_code(self) -> None:
        code, output, _ = self.verify("--tag", "v9.9.9", gh_rc=2)
        self.assertEqual(code, 2)
        self.assertIn("HTTP 404", output)
        self.assertNotIn("OK:", output)

    def test_without_gh_every_required_asset_is_fetched_over_https(self) -> None:
        fetched: list[str] = []

        def download(url: str, path: Path) -> None:
            fetched.append(url)
            shutil.copy2(self.source / url.rsplit("/", 1)[1], path)

        with mock.patch.object(self.mod, "download", side_effect=download):
            code, output, commands = self.verify("--tag", "v0.0.2", gh=None)
        self.assertEqual(code, 0, output)
        self.assertEqual(commands, [])
        base = "https://github.com/sebastienrousseau/agtmls/releases/download/v0.0.2/"
        self.assertEqual(fetched, [base + n for n in
                                   [*self.PROVIDERS, "release-manifest.json", "SHA256SUMS"]])

    def test_a_required_asset_absent_from_the_release_is_reported(self) -> None:
        self.artifacts[1].unlink()
        code, output, _ = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 1)
        self.assertEqual(self.failures(output), [
            "release asset missing after download: agtmls-openai-polyglot.tar.gz",
            "1 release asset issue(s)",
        ])

    def test_a_manifest_entry_with_no_file_is_reported(self) -> None:
        manifest = self.source / "release-manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["artifacts"].append({"file": "agtmls-ghost-polyglot.tar.gz", "sha256": "0"})
        manifest.write_text(json.dumps(data), encoding="utf-8")
        code, output, _ = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 1)
        self.assertIn("manifest artifact missing: agtmls-ghost-polyglot.tar.gz", self.failures(output))

    def test_a_tampered_artifact_fails_both_checksum_sources(self) -> None:
        tarball(self.artifacts[0], MEMBERS + ("agtmls/extra.md",))
        code, output, _ = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 1)
        name = self.artifacts[0].name
        failures = self.failures(output)
        self.assertIn(f"SHA256SUMS mismatch for {name}", failures)
        self.assertIn(f"release-manifest checksum mismatch for {name}", failures)
        # Reported once per source, not a third time by the whole-file sweep,
        # which exists for summed files the manifest does not list.
        self.assertNotIn(f"checksum mismatch for {name}", failures)

    def test_a_blank_or_malformed_checksum_line_is_reported_not_raised(self) -> None:
        with (self.source / "SHA256SUMS").open("a", encoding="utf-8") as fh:
            fh.write("\nnot a checksum line\n")
        code, output, _ = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 1)
        self.assertEqual(self.failures(output), [
            "SHA256SUMS line 4 is not '<sha256>  <file>': 'not a checksum line'",
            "1 release asset issue(s)",
        ])

    def test_an_artifact_that_is_not_a_tarball_is_reported(self) -> None:
        self.artifacts[0].write_bytes(b"<html>rate limited</html>")
        self.resum()
        code, output, _ = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 1)
        failures = self.failures(output)
        self.assertTrue(failures[0].startswith(f"invalid tarball {self.artifacts[0].name}"), failures)

    def test_a_tarball_missing_a_required_member_is_reported(self) -> None:
        tarball(self.artifacts[1], MEMBERS[:2])
        self.resum()
        code, output, _ = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 1)
        self.assertEqual(self.failures(output)[0],
                         f"{self.artifacts[1].name} missing agtmls/ADAPTERS.md")

    def test_a_summed_file_outside_the_manifest_that_matches_passes(self) -> None:
        """The sweep reports mismatches, not every file it reads."""
        import hashlib

        notes = self.source / "NOTES.md"
        notes.write_text("notes\n", encoding="utf-8")
        digest = hashlib.sha256(notes.read_bytes()).hexdigest()
        with (self.source / "SHA256SUMS").open("a", encoding="utf-8") as fh:
            fh.write(f"{digest}  NOTES.md\n")
        code, output, _ = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 0, output)

    def test_every_summed_file_is_checked_not_only_manifest_ones(self) -> None:
        """A self-referencing SHA256SUMS line is skipped, not compared to itself."""
        (self.source / "NOTES.md").write_text("notes\n", encoding="utf-8")
        with (self.source / "SHA256SUMS").open("a", encoding="utf-8") as fh:
            fh.write(f"{'0' * 64}  NOTES.md\n{'0' * 64}  SHA256SUMS\n")
        code, output, _ = self.verify("--tag", "v0.0.2")
        self.assertEqual(code, 1)
        self.assertEqual(self.failures(output),
                         ["checksum mismatch for NOTES.md", "1 release asset issue(s)"])


class LatestReleaseTagTests(TreeCase):
    """Which release `latest` means, with and without the gh CLI."""

    def setUp(self) -> None:
        self.mod = self.script("verify-release-assets.py")

    def api(self, payload: dict):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        return mock.patch.object(self.mod.urllib.request, "urlopen", return_value=response)

    def test_gh_answers_first(self) -> None:
        done = subprocess.CompletedProcess([], 0, "v0.0.2\n")
        with mock.patch.object(self.mod.shutil, "which", return_value="/bin/gh"), \
                mock.patch.object(self.mod.subprocess, "run", return_value=done), \
                self.api({"tag_name": "wrong"}) as urlopen:
            self.assertEqual(self.mod.latest_release_tag("o/r"), "v0.0.2")
        urlopen.assert_not_called()

    def test_a_failing_gh_falls_back_to_the_api(self) -> None:
        failed = subprocess.CompletedProcess([], 1, "auth required")
        with mock.patch.object(self.mod.shutil, "which", return_value="/bin/gh"), \
                mock.patch.object(self.mod.subprocess, "run", return_value=failed), \
                self.api({"tag_name": "v0.0.4"}) as urlopen:
            self.assertEqual(self.mod.latest_release_tag("o/r"), "v0.0.4")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/o/r/releases/latest")

    def test_an_api_answer_with_no_tag_is_refused(self) -> None:
        with mock.patch.object(self.mod.shutil, "which", return_value=None), \
                self.api({"message": "Not Found"}), self.assertRaises(SystemExit) as caught:
            self.mod.latest_release_tag("o/r")
        self.assertIn("could not resolve latest release tag for o/r", str(caught.exception))

    def test_download_writes_the_response_body(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "asset"
            with self.api({"k": 1}) as urlopen:
                self.mod.download("https://example.invalid/a", target)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"k": 1})
        self.assertEqual(urlopen.call_args.args[0], "https://example.invalid/a")

    def test_a_malformed_provider_registry_yields_no_assets(self) -> None:
        """Rather than inventing asset names from a shape it does not understand."""
        with mock.patch.object(self.mod.json, "loads", return_value={"export_targets": ["openai"]}):
            self.assertEqual(self.mod.provider_assets(), [])

