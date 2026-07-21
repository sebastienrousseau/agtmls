#!/usr/bin/env python3
"""Optional live API smoke tests for provider backends.

The script exits successfully when no provider credentials are configured. When a
credential or endpoint is present, it performs a low-cost metadata request so CI
can prove credentials, routing, and provider availability without generating text.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 20


@dataclass(frozen=True)
class Probe:
    name: str
    env: str
    url: str
    headers: dict[str, str]
    query_env: str | None = None


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def probes() -> list[Probe]:
    openai = os.environ.get("OPENAI_API_KEY", "")
    anthropic = os.environ.get("ANTHROPIC_API_KEY", "")
    gemini = os.environ.get("GEMINI_API_KEY", "")
    mistral = os.environ.get("MISTRAL_API_KEY", "")
    deepseek = os.environ.get("DEEPSEEK_API_KEY", "")
    qwen = os.environ.get("QWEN_API_KEY", "")
    ollama = os.environ.get("OLLAMA_BASE_URL", "").rstrip("/")
    return [
        Probe("openai", "OPENAI_API_KEY", "https://api.openai.com/v1/models", bearer(openai)),
        Probe("anthropic", "ANTHROPIC_API_KEY", "https://api.anthropic.com/v1/models", {"x-api-key": anthropic, "anthropic-version": "2023-06-01"}),
        Probe("google-gemini", "GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/models", {}, "GEMINI_API_KEY"),
        Probe("mistral", "MISTRAL_API_KEY", "https://api.mistral.ai/v1/models", bearer(mistral)),
        Probe("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com/models", bearer(deepseek)),
        Probe("qwen", "QWEN_API_KEY", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models", bearer(qwen)),
        Probe("ollama", "OLLAMA_BASE_URL", f"{ollama}/api/tags" if ollama else "", {}),
    ]


def request_url(probe: Probe) -> str:
    if probe.query_env:
        token = os.environ.get(probe.query_env, "")
        return f"{probe.url}?{urllib.parse.urlencode({'key': token})}"
    return probe.url


def configured(probe: Probe) -> bool:
    return bool(os.environ.get(probe.env, ""))


def run_probe(probe: Probe) -> str | None:
    url = request_url(probe)
    request = urllib.request.Request(url, headers={k: v for k, v in probe.headers.items() if v})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read(1024 * 256)
            if response.status < 200 or response.status >= 300:
                return f"{probe.name}: HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return f"{probe.name}: HTTP {exc.code}: {exc.read(512).decode('utf-8', errors='replace')}"
    except urllib.error.URLError as exc:
        return f"{probe.name}: network error: {exc.reason}"
    except TimeoutError:
        return f"{probe.name}: request timed out"
    try:
        json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return f"{probe.name}: response was not JSON: {exc}"
    return None


def main() -> int:
    available = [probe for probe in probes() if configured(probe)]
    if not available:
        print("OK: live provider smoke skipped; no provider credentials/endpoints configured")
        return 0
    errors: list[str] = []
    for probe in available:
        error = run_probe(probe)
        if error:
            errors.append(error)
        else:
            print(f"OK: live provider reachable: {probe.name}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} live provider smoke issue(s)")
        return 1
    print(f"OK: live provider smoke passed for {len(available)} provider(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
