#!/usr/bin/env python3
"""Install provider-specific adapter files into a target directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_targets() -> dict[str, list[str]]:
    providers = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
    targets: dict[str, list[str]] = {}
    for provider, item in providers.get("export_targets", {}).items():
        adapters = item.get("adapter_files", [])
        if isinstance(adapters, list):
            targets[provider] = [str(path) for path in adapters]
    return targets


def install_rel(provider: str, adapter_file: str) -> Path:
    prefix = f"adapters/{provider}/"
    if adapter_file.startswith(prefix):
        return Path(adapter_file[len(prefix):])
    return Path(adapter_file)


def body(provider: str, profile: str | None) -> str:
    return (
        f"# AgtMLS {provider} Adapter\n\n"
        f"Profile: `{profile or 'all'}`. Load skills from `{ROOT}/skills` "
        f"and respect `{ROOT}/index.json` safety policies.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--profile")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    targets = load_targets()
    adapters = targets.get(args.provider)
    if not adapters:
        print(f"unsupported install provider: {args.provider}", file=sys.stderr)
        return 1

    expected = body(args.provider, args.profile)
    installed: list[Path] = []
    for adapter in adapters:
        dst = args.target / install_rel(args.provider, adapter)
        if args.check:
            if not dst.exists() or dst.read_text(encoding="utf-8") != expected:
                print(f"FAIL: provider adapter missing or stale: {dst}")
                return 1
            installed.append(dst)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(expected, encoding="utf-8")
        installed.append(dst)

    if args.check:
        print(f"OK: provider adapter installed for {args.provider}")
    else:
        for path in installed:
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
