#!/usr/bin/env python3
"""Install provider-specific adapter files into a target directory."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
ADAPTERS={'cursor':'.cursor/rules/agtmls.mdc','github-copilot':'.github/copilot-instructions.md','continue':'.continue/rules/agtmls.md','windsurf':'.windsurfrules','zed':'.rules/agtmls.md','openai':'AGENTS.md','anthropic':'CLAUDE.md','google-gemini':'GEMINI.md'}
def body(provider,profile): return f"# AgtMLS {provider} Adapter\n\nProfile: `{profile or 'all'}`. Load skills from `{ROOT}/skills` and respect `{ROOT}/index.json` safety policies.\n"
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--provider',required=True); ap.add_argument('--target',type=Path,required=True); ap.add_argument('--profile'); ap.add_argument('--check',action='store_true'); a=ap.parse_args()
    rel=ADAPTERS.get(a.provider)
    if not rel: print(f'unsupported install provider: {a.provider}',file=sys.stderr); return 1
    dst=a.target/rel; expected=body(a.provider,a.profile)
    if a.check:
        if dst.exists() and dst.read_text(encoding='utf-8')==expected: print('OK: provider adapter installed'); return 0
        print(f'FAIL: provider adapter missing or stale: {dst}'); return 1
    dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text(expected,encoding='utf-8'); print(dst); return 0
if __name__=='__main__': sys.exit(main())
