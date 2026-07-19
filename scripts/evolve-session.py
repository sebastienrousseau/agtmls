#!/usr/bin/env python3
"""Create a redacted skill-evolution proposal from a session transcript."""
from __future__ import annotations
import argparse, hashlib, json, re, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SECRET_PATTERNS=[re.compile(r"sk-[A-Za-z0-9_-]{12,}"), re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+")]
def slug(v:str)->str:
    return re.sub(r"[^a-z0-9]+","-",v.lower()).strip('-') or 'candidate-skill'
def redact(text:str)->tuple[str,int]:
    count=0
    for p in SECRET_PATTERNS:
        text,n=p.subn('[REDACTED]',text); count+=n
    return text,count
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('transcript',type=Path); ap.add_argument('--skill-name',required=True); ap.add_argument('--out-dir',type=Path,default=ROOT/'.agtmls'/'evolution')
    a=ap.parse_args(); raw=a.transcript.read_text(encoding='utf-8',errors='replace'); clean,n=redact(raw); name=slug(a.skill_name)
    a.out_dir.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(clean.encode()).hexdigest()
    proposal={'schema_version':1,'skill_name':name,'status':'candidate','human_review_required':True,'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source_sha256':digest,'redactions':n,'summary':'Candidate skill proposal generated from a redacted local transcript.','regression_requirements':['routing positive case','routing negative case','behavioral contract case','human approval']}
    out=a.out_dir/f'{name}.json'; out.write_text(json.dumps(proposal,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (a.out_dir/f'{name}.redacted.txt').write_text(clean,encoding='utf-8')
    print(out); return 0
if __name__=='__main__': sys.exit(main())
