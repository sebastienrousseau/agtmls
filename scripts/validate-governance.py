#!/usr/bin/env python3
"""Validate publication governance rules."""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def main():
    idx=json.loads((ROOT/'index.json').read_text()); errors=[]
    for s in idx['skills']:
        q=s.get('quality',{}).get('score',0); pol=s.get('safety_policy',{})
        if s.get('maturity') in {'hardened','project'} and q < 75: errors.append(f"{s['name']}: mature skill below quality threshold")
        if pol.get('risk_level') in {'medium','high'} and not pol.get('requires_human_review'): errors.append(f"{s['name']}: elevated risk must require review")
    if not (ROOT/'SBOM.spdx.json').exists(): errors.append('SBOM.spdx.json missing')
    if not (ROOT/'provenance.json').exists(): errors.append('provenance.json missing')
    if errors:
        [print('FAIL:',e) for e in errors]; print(); print(f'FAIL: {len(errors)} governance issue(s)'); return 1
    print('OK: governance policy valid'); return 0
if __name__=='__main__': sys.exit(main())
