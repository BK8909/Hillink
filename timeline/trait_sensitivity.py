"""성향이 동선을 바꾸나 — 성향 하나만 0.2 ↔ 0.8 로 바꿔 간 곳이 달라지는지 (개발용 체류 전부 · 에이전트 v2)

  python3 trait_sensitivity.py
"""
import importlib, glob, re, dataclasses, io, contextlib
from datetime import datetime
from collections import Counter
import agent_v2
F=("PERSONA","START_AT")
class Alt:
    def __init__(s,m):
        for f in F:
            if hasattr(m,f+"_ALT"): setattr(s,f,getattr(m,f+"_ALT"))
from sealed import SEALED_WAIT, unusable
nums=sorted(n for f in glob.glob("persona_blog[0-9][0-9].py") if (n:=int(re.search(r"(\d\d)",f).group(1))) not in SEALED_WAIT)
stays=[]
for n in nums:
    m=importlib.import_module(f"persona_blog{n:02d}")
    if unusable(m): continue
    stays.append((f"{n:02d}",m))
    if hasattr(m,"PERSONA_ALT"): stays.append((f"{n:02d}b",Alt(m)))
def route(P,start):
    with contextlib.redirect_stdout(io.StringIO()):
        segs,_=agent_v2.run_agent(P,start,verbose=False)
    return frozenset(s.venue or s.location for s in segs)
traits=list(stays[0][1].PERSONA.traits)
chg=Counter(); tot=0; anych=Counter()
for key,m in stays:
    P0=m.PERSONA; st=getattr(m,"START_AT",datetime(2025,1,31,14))
    for k in traits:
        lo=dataclasses.replace(P0,traits={**P0.traits,k:0.2}); hi=dataclasses.replace(P0,traits={**P0.traits,k:0.8})
        a,b=route(lo,st),route(hi,st)
        if a!=b: chg[k]+=1; anych[key]+=1
    tot+=1
print(f"체류 {tot}개 · 성향 하나만 0.2 ↔ 0.8 로 바꿨을 때 간 곳이 달라진 체류 수")
for k in traits: print(f"  {k:8s} {chg[k]:2d}/{tot}")
print(f"  어떤 성향이든 하나라도 바꿔서 동선이 달라진 체류 {sum(1 for k,_ in stays if anych[k])}/{tot}")
# all extreme: every trait 0.2 vs every trait 0.8
d=0
for key,m in stays:
    P0=m.PERSONA; st=getattr(m,"START_AT",datetime(2025,1,31,14))
    a=route(dataclasses.replace(P0,traits={k:0.2 for k in traits}),st); b=route(dataclasses.replace(P0,traits={k:0.8 for k in traits}),st)
    d+= a!=b
print(f"  성향 7개를 한꺼번에 전부 0.2 ↔ 전부 0.8: 달라진 체류 {d}/{tot}")
