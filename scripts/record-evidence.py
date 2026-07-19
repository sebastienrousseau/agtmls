#!/usr/bin/env python3
"""Record a local skill invocation evidence event."""
from __future__ import annotations
import argparse,json,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--skill',required=True); ap.add_argument('--out-dir',type=Path,default=ROOT/'.agtmls'/'runs'); ap.add_argument('--command',action='append',default=[]); ap.add_argument('--file',action='append',default=[]); ap.add_argument('--outcome',default='recorded')
    a=ap.parse_args(); idx=json.loads((ROOT/'index.json').read_text(encoding='utf-8')); skills={s['name']:s for s in idx['skills']}
    if a.skill not in skills: print(f'unknown skill: {a.skill}',file=sys.stderr); return 1
    a.out_dir.mkdir(parents=True,exist_ok=True); rid=str(uuid.uuid4())
    rec={'schema_version':1,'run_id':rid,'skill':a.skill,'recorded_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'commands':a.command,'files':a.file,'outcome':a.outcome,'safety_policy':skills[a.skill].get('safety_policy',{})}
    out=a.out_dir/f'{rid}.json'; out.write_text(json.dumps(rec,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(out); return 0
if __name__=='__main__': sys.exit(main())
