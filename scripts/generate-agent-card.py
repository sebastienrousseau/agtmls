#!/usr/bin/env python3
"""Generate an A2A-style agent card from registry metadata."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'agent-card.json'
def render():
    idx=json.loads((ROOT/'index.json').read_text(encoding='utf-8')); providers=json.loads((ROOT/'providers.json').read_text(encoding='utf-8'))
    return {'schema_version':1,'name':'agtmls','description':idx['description'],'version':idx['registry_version'],'capabilities':[{'name':s['name'],'description':s['description'],'risk':s.get('safety_policy',{}).get('risk_level'),'quality':s.get('quality',{}).get('score')} for s in idx['skills']], 'providers': sorted(providers.get('export_targets',{})), 'interfaces':['skills','provider-adapted-markdown','mcp-resources']}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--write',action='store_true'); ap.add_argument('--check',action='store_true'); a=ap.parse_args(); text=json.dumps(render(),indent=2,sort_keys=True)+'\n'
    if a.write: OUT.write_text(text,encoding='utf-8'); print(f'wrote {OUT.relative_to(ROOT)}'); return 0
    if a.check:
        cur=OUT.read_text(encoding='utf-8') if OUT.exists() else ''
        if cur!=text: print('FAIL: agent-card.json is stale; run generate-agent-card.py --write'); return 1
        print('OK: agent card is current'); return 0
    print(text,end=''); return 0
if __name__=='__main__': sys.exit(main())
