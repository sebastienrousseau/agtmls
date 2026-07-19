#!/usr/bin/env python3
"""Generate MCP-style resource descriptors for AgtMLS skills."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'mcp-resources.json'
def render():
    idx=json.loads((ROOT/'index.json').read_text(encoding='utf-8'))
    return {'schema_version':1,'resources':[{'uri':f"agtmls://skills/{s['name']}",'name':s['name'],'description':s['description'],'mimeType':'text/markdown','path':s['path']+'/SKILL.md'} for s in idx['skills']]}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--write',action='store_true'); ap.add_argument('--check',action='store_true'); a=ap.parse_args(); text=json.dumps(render(),indent=2,sort_keys=True)+'\n'
    if a.write: OUT.write_text(text,encoding='utf-8'); print(f'wrote {OUT.relative_to(ROOT)}'); return 0
    if a.check:
        cur=OUT.read_text(encoding='utf-8') if OUT.exists() else ''
        if cur!=text: print('FAIL: mcp-resources.json is stale; run generate-mcp-resources.py --write'); return 1
        print('OK: MCP resources are current'); return 0
    print(text,end=''); return 0
if __name__=='__main__': sys.exit(main())
