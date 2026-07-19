#!/usr/bin/env python3
"""Generate a lightweight SPDX SBOM for registry files."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/'SBOM.spdx.json'
def sha(p):
    h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
def render():
    files=[]
    for base in ['skills','scripts','commands','system-prompts']:
        for p in sorted((ROOT/base).glob('**/*')):
            if p.is_file() and '__pycache__' not in p.parts:
                files.append({'fileName':p.relative_to(ROOT).as_posix(),'checksums':[{'algorithm':'SHA256','checksumValue':sha(p)}]})
    return {'spdxVersion':'SPDX-2.3','dataLicense':'CC0-1.0','SPDXID':'SPDXRef-DOCUMENT','name':'agtmls','documentNamespace':'https://example.invalid/agtmls/sbom','files':files}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--write',action='store_true'); ap.add_argument('--check',action='store_true'); a=ap.parse_args(); text=json.dumps(render(),indent=2,sort_keys=True)+'\n'
    if a.write: OUT.write_text(text,encoding='utf-8'); print(f'wrote {OUT.relative_to(ROOT)}'); return 0
    if a.check:
        cur=OUT.read_text(encoding='utf-8') if OUT.exists() else ''
        if cur!=text: print('FAIL: SBOM.spdx.json is stale; run generate-sbom.py --write'); return 1
        print('OK: SBOM is current'); return 0
    print(text,end=''); return 0
if __name__=='__main__': sys.exit(main())
