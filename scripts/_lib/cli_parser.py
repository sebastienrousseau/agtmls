# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The command surface, declared in one place.

Every subcommand and flag agtmls accepts. Separated from the dispatch so
the surface can be read -- and parsed -- without wading through what each
command then does. validate-cli-surface.py reads this file to check the
surface against docs/cli.md, and run-unit-tests.py reads it to check that
every declared subcommand has a dispatch case.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROVIDERS = Path(__file__).resolve().parents[2] / "providers.json"
PLUGIN = Path(__file__).resolve().parents[2] / ".claude-plugin" / "plugin.json"
INDEX = Path(__file__).resolve().parents[2] / "index.json"


def registry_version() -> str:
    """The version `--version` prints.

    plugin.json is the one authored copy, but `make install` ships the
    registry without it; index.json restates the version and is shipped
    everywhere. Read only when asked, so no other command pays for it.
    """
    for path, key in ((PLUGIN, "version"), (INDEX, "registry_version")):
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8")).get(key)
            if value:
                return str(value)
    return "unknown"


class _Version(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print(f"agtmls {registry_version()}")
        parser.exit()


def native_agents() -> list[str]:
    """The agents `install`, `verify` and friends accept, from providers.json.

    Hand-kept copies of this list drifted: the installer script accepted
    `antigravity` while every `choices=` here rejected it.
    """
    data = json.loads(PROVIDERS.read_text(encoding="utf-8"))
    return sorted(data["native_agents"])


def build_parser() -> argparse.ArgumentParser:
    """Every subcommand agtmls accepts."""
    parser = argparse.ArgumentParser(prog="agtmls")
    # `agtmls --version` used to be a usage error.
    parser.add_argument("--version", action=_Version, nargs=0, help="print the registry version and exit")
    agents = native_agents()
    # dest must not collide with any subparser option dest: `evidence --command`
    # used to overwrite the subcommand name with its own (list) value, which made
    # every dispatch comparison below fail. See CliDispatchTests.
    sub = parser.add_subparsers(dest="subcommand", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--target", type=Path)
    doctor.add_argument("--agent", choices=agents)
    doctor.add_argument("--skills-only", action="store_true")
    doctor.add_argument("--bundle", action="append", default=[])
    doctor.add_argument("--installed", action="store_true")

    status = sub.add_parser("status")
    status.add_argument("--target", type=Path)
    status.add_argument("--agent", choices=agents)
    status.add_argument("--skills-only", action="store_true")
    status.add_argument("--bundle", action="append", default=[])
    status.add_argument("--installed", action="store_true")

    sub.add_parser("check")

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("kind", nargs="?", choices=["skills", "commands"], default="skills")
    list_cmd.add_argument("--bundle")
    list_cmd.add_argument("--json", action="store_true")

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--json", action="store_true")

    show = sub.add_parser("show")
    show.add_argument("name")
    show.add_argument("--json", action="store_true")

    stats_cmd = sub.add_parser("stats")
    stats_cmd.add_argument("--json", action="store_true")

    profiles_cmd = sub.add_parser("profiles")
    profiles_cmd.add_argument("--json", action="store_true")

    providers_cmd = sub.add_parser("providers")
    providers_cmd.add_argument("--json", action="store_true")

    export_cmd = sub.add_parser("export")
    export_cmd.add_argument("--provider", default="generic")
    export_cmd.add_argument("--profile")
    export_cmd.add_argument("--bundle", action="append", default=[])
    export_cmd.add_argument("--out-dir", type=Path)

    docs_site = sub.add_parser("docs-site")
    docs_site.add_argument("--write", action="store_true")
    docs_site.add_argument("--check", action="store_true")

    release_pack = sub.add_parser("release-pack")
    release_pack.add_argument("--out-dir", type=Path)
    release_pack.add_argument("--profile")
    release_pack.add_argument("--provider", action="append", default=[])

    next_version = sub.add_parser("next-version")
    next_version.add_argument("--tag", action="store_true")
    next_version.add_argument("--json", action="store_true")

    bump_version = sub.add_parser("bump-version")
    bump_version.add_argument("--version")
    bump_version.add_argument("--date")
    bump_version.add_argument("--check", action="store_true")

    release_dry_run = sub.add_parser("release-dry-run")
    release_dry_run.add_argument("--version")
    release_dry_run.add_argument("--skip-check", action="store_true")
    release_dry_run.add_argument("--profile")
    release_dry_run.add_argument("--provider", action="append", default=[])

    verify_release_assets = sub.add_parser("verify-release-assets")
    verify_release_assets.add_argument("--tag", default="v0.0.1")
    verify_release_assets.add_argument("--repo")
    verify_release_assets.add_argument("--out-dir", type=Path)

    evolve = sub.add_parser("evolve")
    evolve.add_argument("transcript", type=Path)
    evolve.add_argument("--skill-name", required=True)

    evidence = sub.add_parser("evidence")
    evidence.add_argument("--skill", required=True)
    evidence.add_argument("--command", dest="evidence_commands", action="append", default=[])
    evidence.add_argument("--file", action="append", default=[])
    evidence.add_argument("--outcome", default="recorded")


    mcp_resources = sub.add_parser("mcp-resources")
    mcp_resources.add_argument("--write", action="store_true")
    mcp_resources.add_argument("--check", action="store_true")

    plugin_manifests = sub.add_parser("plugin-manifests")
    plugin_manifests.add_argument("--write", action="store_true")
    plugin_manifests.add_argument("--check", action="store_true")

    sbom = sub.add_parser("sbom")
    sbom.add_argument("--write", action="store_true")
    sbom.add_argument("--check", action="store_true")

    provenance = sub.add_parser("provenance")
    provenance.add_argument("--write", action="store_true")
    provenance.add_argument("--check", action="store_true")

    provider_install = sub.add_parser("provider-install")
    provider_install.add_argument("--provider", required=True)
    provider_install.add_argument("--target", type=Path, required=True)
    provider_install.add_argument("--profile")
    provider_install.add_argument("--check", action="store_true")

    sub.add_parser("bench")

    diff_cmd = sub.add_parser("diff")
    diff_cmd.add_argument("--from", dest="old", required=True)
    diff_cmd.add_argument("--to", dest="new", help="defaults to this registry's index.json")
    diff_cmd.add_argument("--json", action="store_true")

    sub.add_parser("release-check")

    audit_cmd = sub.add_parser("audit", help="statically audit skills for prompt injection, steganography, and security risks")
    audit_cmd.add_argument("path", nargs="?", type=Path, help="path to skill directory or markdown file")
    audit_cmd.add_argument("--all", action="store_true", help="audit all skills in registry")
    audit_cmd.add_argument("--strict", action="store_true", help="fail on warnings")
    audit_cmd.add_argument("--json", action="store_true", help="output JSON")

    import_cmd = sub.add_parser("import-skill")
    import_cmd.add_argument("source", type=Path)
    import_cmd.add_argument("--name")
    import_cmd.add_argument("--bundle")

    index = sub.add_parser("index")
    index.add_argument("--write", action="store_true")
    index.add_argument("--check", action="store_true")

    install = sub.add_parser("install")
    install.add_argument("language")
    install.add_argument("agent", choices=agents)
    install.add_argument("--target", type=Path, default=Path.cwd())
    install.add_argument("--skills-only", action="store_true")
    install.add_argument(
        "--copy",
        action="store_true",
        help="copy skills instead of symlinking (required when the hub is a packaged wheel)",
    )
    install.add_argument("--bundle", action="append", default=[])
    install.add_argument("--profile")
    install.add_argument(
        "--force",
        action="store_true",
        help="back up and overwrite a prompt file AgtMLS did not generate",
    )
    install.add_argument(
        "--dry-run",
        action="store_true",
        help="print every planned change and exit without touching disk",
    )
    install.add_argument(
        "--no-verify",
        action="store_true",
        help="skip the integrity check against index.json (not recommended)",
    )

    verify = sub.add_parser(
        "verify", help="check an installed tree against its .agtmls/manifest.json lockfile"
    )
    verify.add_argument("agent", choices=agents)
    verify.add_argument("--target", type=Path, default=Path.cwd())
    verify.add_argument("--json", action="store_true")

    remove = sub.add_parser("uninstall")
    remove.add_argument("agent", choices=agents)
    remove.add_argument("--target", type=Path, default=Path.cwd())
    remove.add_argument("--remove-prompt", action="store_true")

    propose = sub.add_parser("propose-skill")
    propose.add_argument("transcript", type=Path)
    propose.add_argument("--skill-name", required=True)

    scaffold = sub.add_parser("scaffold-skill")
    scaffold.add_argument("name")
    scaffold.add_argument("--bundle")
    scaffold.add_argument("--title")
    return parser
