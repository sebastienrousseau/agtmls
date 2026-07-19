#!/usr/bin/env python3
"""Run AgtMLS benchmark aggregate checks."""
from __future__ import annotations
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CHECKS=[['run-trigger-evals.py'],['run-behavioral-evals.py'],['validate-skill-index.py']]
def main():
    passed=0
    for c in CHECKS:
        rc=subprocess.call([sys.executable,str(ROOT/'scripts'/c[0]),*c[1:]],cwd=ROOT)
        if rc: return rc
        passed+=1
    idx=json.loads((ROOT/'index.json').read_text()); print(f"OK: benchmark passed {passed} suites; quality={idx.get('quality',{}).get('average_score',0)} coverage={idx['coverage']}"); return 0
if __name__=='__main__': sys.exit(main())
