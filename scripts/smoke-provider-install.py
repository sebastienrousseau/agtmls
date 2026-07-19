#!/usr/bin/env python3
"""Smoke-test provider adapter installation."""
from __future__ import annotations
import subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def main():
    with tempfile.TemporaryDirectory(prefix='agtmls-provider-') as td:
        t=Path(td)
        cmd=[sys.executable,str(ROOT/'scripts'/'provider-install.py'),'--provider','cursor','--target',str(t),'--profile','polyglot']
        p=subprocess.run(cmd,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        if p.returncode: print('FAIL:',p.stdout); return 1
        c=subprocess.run(cmd+['--check'],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        if c.returncode: print('FAIL:',c.stdout); return 1
    print('OK: provider install smoke test passed'); return 0
if __name__=='__main__': sys.exit(main())
