"""Public search and posting signals: opt-in preference experiments, not visitor counts."""
from __future__ import annotations
import csv,math
from collections import defaultdict
from pathlib import Path
VENUES={'금룡':'GEUMRYONG','피자힐':'PIZZA_HILL','더뷔페':'THE_BUFFET','온달':'ONDAL','르파사쥬':'LE_PASSAGE','명월관':'MYONGWOLGWAN','파빌리온':'THE_PAVILION','모에기':'MOEGI','럭스바':'LUX_BAR'}

def _replace(dining, replacements):
    out={}
    for purpose,rows in dining.items():
        old=dict(rows); a=replacements.get(purpose)
        if a is None:out[purpose]=list(rows);continue
        before=old.get('PIZZA_HILL',0); rest=sum(v for k,v in rows if k!='PIZZA_HILL')
        if rest<=0 and a<1:raise ValueError('피자힐 외 선호 배분이 없어 보정할 수 없습니다')
        out[purpose]=[(k,a if k=='PIZZA_HILL' else v*(1-a)/rest) for k,v in rows]
    return out

def search_dining(dining, factors, weight):
    weight=float(weight)
    if not math.isfinite(weight) or not 0<=weight<=1:raise ValueError('검색 신호 강도는 0~1입니다')
    if weight==0:return dining
    out={}
    for purpose,rows in dining.items():
        vals=[]
        for venue,prob in rows:
            mult=float(factors.get('search_'+venue,1))
            if not math.isfinite(mult) or mult<=0:raise ValueError('검색 신호 배율은 양수여야 합니다')
            vals.append((venue,prob*mult**weight))
        total=sum(v for _,v in vals)
        if total<=0:raise ValueError('식당 선호 가중 합계가 0입니다')
        out[purpose]=[(k,v/total) for k,v in vals]
    return out

def nonstay_pizza(dining, rows, weights, posting_k, source=None):
    posting_k=float(posting_k)
    if not math.isfinite(posting_k) or posting_k<1:raise ValueError('미식 게시 배수 가정은 1 이상입니다')
    source=Path(source or Path(__file__).parent/'trend_signals.csv');counts=defaultdict(float)
    for r in csv.DictReader(source.open(encoding='utf-8-sig')):
        if r['업장']=='PIZZA_HILL' and r.get('출처유형','문장형')=='문장형':counts[r['목적']]+=float(r['건수'])
    gourmet=counts['미식 방문']; other=sum(counts.values())-gourmet
    if gourmet<=0 or other<=0:raise ValueError('게시 성향 보정에 필요한 피자힐 분류 건수가 없습니다')
    target=(gourmet/posting_k)/(other+gourmet/posting_k)
    pm=defaultdict(float)
    for r,w in zip(rows,weights):pm[r['목적']]+=w
    total=sum(pm.values());pm={p:w/total for p,w in pm.items()}
    c=sum(pm.get(p,0)*dict(rs).get('PIZZA_HILL',0) for p,rs in dining.items())
    gm=pm.get('미식 방문',0)
    if gm<=0:return dining
    old_g=dict(dining['미식 방문']).get('PIZZA_HILL',0);new_g=min(.8,c*target/gm)
    rest=c-gm*old_g; remaining=c-gm*new_g
    if rest<=0:return dining
    replacements={p:(new_g if p=='미식 방문' else dict(rs).get('PIZZA_HILL',0)*remaining/rest) for p,rs in dining.items() if p in pm}
    return _replace(dining,replacements)
