#!/usr/bin/env python3
"""Validate provider compatibility metadata."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = ROOT / "providers.json"
NATIVE = {"claude", "codex", "aider"}
REQUIRED_EXPORTS = {"generic", "openai", "anthropic", "google-gemini", "mistral", "deepseek", "qwen", "ollama", "github-copilot", "cursor", "windsurf", "zed", "continue"}
# Runtimes that consume a plugin manifest rather than a symlink install or
# a Markdown export. Each entry's manifest_files must exist in the repo.
REQUIRED_PLUGIN_TARGETS = {"antigravity", "codex", "cursor", "gemini-cli", "kimi", "opencode"}


def main() -> int:
    errors: list[str] = []
    try:
        data = json.loads(PROVIDERS.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"FAIL: providers.json invalid or missing: {exc}")
        return 1
    if data.get("schema_version") != 1:
        errors.append("providers.json schema_version must be 1")
    native = data.get("native_agents", {})
    if set(native) != NATIVE:
        errors.append(f"native_agents must be exactly {sorted(NATIVE)}")
    for name, item in native.items():
        if not isinstance(item, dict):
            errors.append(f"native agent {name} must be an object")
            continue
        for key in ["prompt_file", "skills_dir", "commands_dir", "install_mode"]:
            if not isinstance(item.get(key), str) or not item.get(key):
                errors.append(f"native agent {name} missing {key}")
        if item.get("install_mode") != "symlink":
            errors.append(f"native agent {name} install_mode must be symlink")
    plugins = data.get("plugin_targets", {})
    if not isinstance(plugins, dict):
        errors.append("plugin_targets must be an object")
        plugins = {}
    for name in sorted(REQUIRED_PLUGIN_TARGETS - set(plugins)):
        errors.append(f"missing plugin target: {name}")
    for name, item in plugins.items():
        if not isinstance(item, dict):
            errors.append(f"plugin target {name} must be an object")
            continue
        for key in ["description", "install"]:
            if not isinstance(item.get(key), str) or not item[key].strip():
                errors.append(f"plugin target {name} must have {key}")
        manifests = item.get("manifest_files")
        if not isinstance(manifests, list) or not manifests:
            errors.append(f"plugin target {name} must have manifest_files")
            continue
        for rel in manifests:
            if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
                errors.append(f"plugin target {name} manifest_files must be safe relative paths")
            elif not (ROOT / rel).exists():
                errors.append(f"plugin target {name} manifest missing: {rel}")

    exports = data.get("export_targets", {})
    missing = sorted(REQUIRED_EXPORTS - set(exports)) if isinstance(exports, dict) else sorted(REQUIRED_EXPORTS)
    for name in missing:
        errors.append(f"missing export target: {name}")
    if isinstance(exports, dict):
        for name, item in exports.items():
            if not isinstance(item, dict) or not isinstance(item.get("description"), str) or not item["description"].strip():
                errors.append(f"export target {name} must have description")
                continue
            adapters = item.get("adapter_files")
            if not isinstance(adapters, list) or not adapters or not all(isinstance(path, str) and path for path in adapters):
                errors.append(f"export target {name} must have adapter_files")
            elif any(path.startswith("/") or ".." in Path(path).parts for path in adapters):
                errors.append(f"export target {name} adapter_files must be safe relative paths")
    else:
        errors.append("export_targets must be an object")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} provider metadata issue(s)")
        return 1
    print(
        f"OK: provider metadata valid with {len(native)} native agent(s), "
        f"{len(plugins)} plugin target(s), {len(exports)} export target(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
