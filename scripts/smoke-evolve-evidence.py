#!/usr/bin/env python3
"""Smoke-test evolution proposals and evidence logging."""
from __future__ import annotations
import json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def main():
    errs=[]
    with tempfile.TemporaryDirectory(prefix='agtmls-evolve-') as td:
        t=Path(td); tr=t/'session.txt'; tr.write_text('User asked to port code. api_key=SECRET123456789\n',encoding='utf-8')
        p=subprocess.run([sys.executable,str(ROOT/'scripts'/'evolve-session.py'),str(tr),'--skill-name','Port Helper','--out-dir',str(t/'evo')],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=ROOT)
        if p.returncode: errs.append(p.stdout)
        prop=t/'evo'/'port-helper.json'
        if not prop.exists(): errs.append('proposal missing')
        elif json.loads(prop.read_text()).get('redactions',0)<1: errs.append('redaction not recorded')
        e=subprocess.run([sys.executable,str(ROOT/'scripts'/'record-evidence.py'),'--skill','cross-language-port','--out-dir',str(t/'runs'),'--command','pytest','--file','x.py'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=ROOT)
        if e.returncode: errs.append(e.stdout)
        if not list((t/'runs').glob('*.json')): errs.append('evidence missing')
    if errs:
        [print('FAIL:',e) for e in errs]; return 1
    print('OK: evolve/evidence smoke test passed'); return 0
if __name__=='__main__': sys.exit(main())
