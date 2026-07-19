#!/usr/bin/env python3
"""Generate SLSA-style provenance metadata for the current registry state."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'provenance.json'
MATERIALS=['index.json','checks.json','agent-card.json','mcp-resources.json','SBOM.spdx.json']
def material_digest():
    h=hashlib.sha256()
    for name in MATERIALS:
        p=ROOT/name
        h.update(name.encode())
        h.update(b'\0')
        h.update(p.read_bytes())
        h.update(b'\0')
    return h.hexdigest()
def render():
    idx=json.loads((ROOT/'index.json').read_text(encoding='utf-8'))
    return {'schema_version':1,'predicateType':'https://slsa.dev/provenance/v1','subject':[{'name':'agtmls','version':idx['registry_version']}],'builder':{'id':'scripts/agtmls.py check'},'materials':[{'uri':'agtmls:registry-state','digest':{'sha256':material_digest()}}],'metadata':{'generated_at':'1970-01-01T00:00:00Z','checks':json.loads((ROOT/'checks.json').read_text())['checks']}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--write',action='store_true'); ap.add_argument('--check',action='store_true'); a=ap.parse_args(); text=json.dumps(render(),indent=2,sort_keys=True)+'\n'
    if a.write: OUT.write_text(text,encoding='utf-8'); print(f'wrote {OUT.relative_to(ROOT)}'); return 0
    if a.check:
        cur=OUT.read_text(encoding='utf-8') if OUT.exists() else ''
        if cur!=text: print('FAIL: provenance.json is stale; run generate-provenance.py --write'); return 1
        print('OK: provenance is current'); return 0
    print(text,end=''); return 0
if __name__=='__main__': sys.exit(main())
