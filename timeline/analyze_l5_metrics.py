"""L5 지표와 체류별 업장 공동 이용 집계. 에이전트 실행·원본 수정 없음."""
import argparse,csv,json,math,re,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from itertools import combinations
from datetime import date,timedelta

ROOMS={"그랜드","비스타","더글라스"}
FNB={"금룡","피자힐","더뷔페","온달","르파사쥬","명월관","파빌리온","모에기"}
COMPARABLE=FNB|{"럭스바"}
CODES={"GEUMRYONG":"금룡","PIZZA_HILL":"피자힐","THE_BUFFET":"더뷔페","ONDAL":"온달","LE_PASSAGE":"르파사쥬","MYONGWOLGWAN":"명월관","THE_PAVILION":"파빌리온","MOEGI":"모에기","LUX_BAR":"럭스바","DOUGLAS_LOUNGE":"더글라스 라운지","GRAND_CLUB_LOUNGE":"그랜드 클럽 라운지"}
def read(p):
 with Path(p).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def write(p,rows,fields):
 with Path(p).open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def blob(p):
 b=Path(p).read_bytes();return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def ratio(a,b):return a/b if b else None
def dayvisitor(id):return "D#" in id
def party(r):
 m=re.search(r"(\d+)인",r["구성·방문 목적"])
 if not m:raise ValueError("인원수 없는 체류: "+r["체류"])
 return int(m.group(1))
def purpose(r):return r["구성·방문 목적"].split(" · ")[0]
def teams(rows):
 t={}
 for r in rows:
  k=r["체류"];n=party(r)
  info=(n,purpose(r),r["AI 유형"],dayvisitor(k))
  if k in t and t[k]["info"]!=info:raise ValueError("체류 내 구성 불일치: "+k)
  t.setdefault(k,dict(info=info,net=0,venues=set(),fb=False))
  t[k]["net"]+=int(r["순매출"]);t[k]["venues"].add(r["업장"])
  if r["업장"] in FNB:t[k]["fb"]=True
 return t
def metrics(rows,start,end,rooms):
 t=teams(rows);guests=[v for v in t.values() if not v["info"][3]]
 total=sum(int(r["순매출"]) for r in rows)
 fb=sum(int(r["순매출"]) for r in rows if r["부문"]=="F&B")
 outside=sum(int(r["순매출"]) for r in rows if r["부문"]=="F&B" and dayvisitor(r["체류"]))
 top=sorted((v["net"] for v in t.values()),reverse=True);k=math.ceil(len(top)*.2)
 roomnet=sum(int(r["순매출"]) for r in rows if r["업장"] in ROOMS)
 days=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
 return dict(start=start,end=end,days=days,rows=len(rows),stays=len(t),guest_stays=len(guests),day_stays=len(t)-len(guests),
  net_total=total,room_net=roomnet,fnb_net=fb,day_fnb_net=outside,
  trevpar_daily_average=total/(rooms*days),trevpar_rooms=rooms,
  capture_observed_teams=ratio(sum(v["fb"] for v in guests),len(guests)),
  capture_observed_persons=ratio(sum(v["info"][0] for v in guests if v["fb"]),sum(v["info"][0] for v in guests)),
  guest_persons=sum(v["info"][0] for v in guests),
  guest_fnb_stays=sum(v["fb"] for v in guests),
  guest_fnb_persons=sum(v["info"][0] for v in guests if v["fb"]),
  day_fnb_share=ratio(outside,fb),top20_count=k,top20_net=sum(top[:k]),top20_share=ratio(sum(top[:k]),total))
def groups(t,axis):
 d=defaultdict(lambda:dict(n=0,persons=0,net=0))
 for v in t.values():
  key=v["info"][axis] or "미설정";d[key]["n"]+=1;d[key]["persons"]+=v["info"][0];d[key]["net"]+=v["net"]
 expected=(["커플·기념일","가족·친족","비즈니스·접대","친구·모임","혼자 휴식","휴식·산책 동행","골프·스포츠 모임","미식 방문","공항 이동·여행"] if axis==1 else ["FOAC","FOHE","HEFO","ACFO","FOFO","HEAC","HEHE","ACAC","ACHE"])
 for key in expected:d[key]
 total=sum(v["net"] for v in t.values());persons=sum(v["info"][0] for v in t.values())
 return [dict(축="목적" if axis==1 else "AI유형",값=k,체류수=v["n"],인원수=v["persons"],손님팀비중=v["n"]/len(t),손님인원비중=v["persons"]/persons,순매출=v["net"],매출비중=ratio(v["net"],total)) for k,v in sorted(d.items())]
def lifts(pop,allowed=None):
 n=len(pop);freq=Counter();joint=Counter()
 for venues in pop.values():
  vs=venues if allowed is None else venues & allowed
  freq.update(vs);joint.update(combinations(sorted(vs),2))
 out=[]
 for (a,b),ab in joint.items():
  out.append(dict(A=a,B=b,N=n,A수=freq[a],B수=freq[b],공동수=ab,P_A=freq[a]/n,P_B=freq[b]/n,P_AB=ab/n,lift=ab*n/(freq[a]*freq[b]),희소경고="공동 5건 미만" if ab<5 else ""))
 return sorted(out,key=lambda r:(-r["lift"],-r["공동수"],r["A"],r["B"]))
def reviews(types,orders):
 pop={r["blog"]:set() for r in types if r["AI유형"] and r["목적"]}
 unknown=[]
 for r in types:
  if r["blog"] not in pop:continue
  m=re.match(r"식당=([^;]+);",r["근거"])
  if m:
   for token in m[1].split(","):
    code=token.strip()
    if code in CODES:pop[r["blog"]].add(CODES[code])
    else:unknown.append(dict(blog=r["blog"],항목=code,이유="코드 또는 건물 미확정"))
 for r in orders:
  if r["blog"] not in pop:continue
  if r["확신도"]=="추정":continue
  for code in r["방문식당"].split(";"):
   if code in CODES:pop[r["blog"]].add(CODES[code])
 return pop,unknown
def pct(v):return "미상" if v is None else f"{v*100:.2f}%"
def mdtable(rows,fields):
 return "\n".join(["| "+" | ".join(fields)+" |","|"+"---|"*len(fields)]+["| "+" | ".join(str(r.get(k,"")) for k in fields)+" |" for r in rows])
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--l5",required=True);ap.add_argument("--types",required=True);ap.add_argument("--orders",required=True)
 ap.add_argument("--start",default="2026-10-01");ap.add_argument("--end",default="2026-10-31");ap.add_argument("--rooms",type=int,default=875);ap.add_argument("--out",required=True)
 ap.add_argument("--types-source-sha");ap.add_argument("--orders-source-sha")
 args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 if args.rooms<=0 or args.start>args.end:raise ValueError("기간/객실 수 확인 필요")
 original=read(args.l5);rows=[r for r in original if args.start<=r["구매 날짜"]<=args.end]
 if not rows:raise ValueError("선택 기간 기록 없음")
 expected_days=(date.fromisoformat(args.end)-date.fromisoformat(args.start)).days+1
 if len({r["구매 날짜"] for r in rows})!=expected_days:raise ValueError("기간 중 기록 없는 날짜가 있음. 미수집을 0으로 계산하지 않도록 --start/--end 확인 필요")
 t=teams(rows);m=metrics(rows,args.start,args.end,args.rooms)
 daily=[]
 d=date.fromisoformat(args.start)
 while d<=date.fromisoformat(args.end):
  s=d.isoformat();rr=[r for r in rows if r["구매 날짜"]==s]
  daily.append(metrics(rr,s,s,args.rooms));d+=timedelta(days=1)
 group=groups(t,1)+groups(t,2)
 typ=read(args.types);ordered=read(args.orders);rev,unknown=reviews(typ,ordered)
 genpop={k:v["venues"] for k,v in t.items()}
 allpairs=lifts(genpop);common=lifts(genpop,COMPARABLE);rp=lifts(rev,COMPARABLE)
 # 전체 체류 분모 유지. 식당 기록 없는 체류도 제거하지 않는다.
 ri={(r["A"],r["B"]):r for r in rp};gi={(r["A"],r["B"]):r for r in common}
 comparison=[]
 for a,b in sorted(set(ri)|set(gi)):
  g=gi.get((a,b));r=ri.get((a,b))
  comparison.append(dict(A=a,B=b,생성N=len(genpop),생성공동수=g["공동수"] if g else 0,생성lift=g["lift"] if g else 0,
   후기N=len(rev),후기공동수=r["공동수"] if r else 0,후기lift=r["lift"] if r else 0,
   주의="후기 미기록은 미방문 아님; 후기 단위는 글, 생성 단위는 체류"))
 comparison.sort(key=lambda x:(-x["생성lift"],-x["생성공동수"]))
 review_joint=[r for r in comparison if r["후기공동수"]>0]
 reproduced=sum(r["생성공동수"]>0 for r in review_joint)
 geummoegi=next((r for r in comparison if {r["A"],r["B"]}=={"금룡","모에기"}),None)
 rare_note=(f'금룡·모에기는 후기 공동 {geummoegi["후기공동수"]}건, 후기 lift {geummoegi["후기lift"]:.3f}, 생성 lift {geummoegi["생성lift"]:.3f}이다.' if geummoegi else "")
 assert sum(r["순매출"] for r in group if r["축"]=="목적")==m["net_total"]
 assert sum(d["net_total"] for d in daily)==m["net_total"]
 assert abs(sum(r["손님팀비중"] for r in group if r["축"]=="목적")-1)<1e-12
 assert m["guest_stays"]+m["day_stays"]==m["stays"]
 for x in allpairs:
  assert abs(x["lift"]-x["P_AB"]/(x["P_A"]*x["P_B"]))<1e-10
 write(out/"daily_metrics.csv",daily,list(daily[0]))
 write(out/"purpose_type_shares.csv",group,list(group[0]))
 for name,data in [("lift_all.csv",allpairs),("lift_dining.csv",common),("lift_review.csv",rp),("lift_compare.csv",comparison)]:
  if data:write(out/name,data,list(data[0]))
 if unknown:write(out/"review_unmapped.csv",unknown,list(unknown[0]))
 metadata=dict(l5_blob=blob(args.l5),types_blob=args.types_source_sha or blob(args.types),orders_blob=args.orders_source_sha or blob(args.orders),types_local_blob=blob(args.types),orders_local_blob=blob(args.orders),all_rows=len(original),outside_period=len(original)-len(rows),
  purchase_min=min(r["구매 날짜"] for r in original),purchase_max=max(r["구매 날짜"] for r in original),review_total=len(typ),review_used=len(rev),review_excluded=len(typ)-len(rev))
 (out/"metrics.json").write_text(json.dumps(dict(metadata=metadata,metrics=m,daily=daily),ensure_ascii=False,indent=2),encoding="utf-8")
 ten=next((d for d in daily if d["start"]=="2026-10-10"),None)
 headline=[dict(지표="1. TRevPAR(일평균)",값=f'{m["trevpar_daily_average"]:,.0f}원',산식=f"기간 순매출 ÷ 기간 일수 ÷ {args.rooms}실"),
  dict(지표="2. 관측 투숙 체류 F&B 캡처율",값=pct(m["capture_observed_teams"]),산식=f'{m["guest_fnb_stays"]} / {m["guest_stays"]}체류 · 전체 투숙객 캡처율은 미상'),
  dict(지표="3. 비투숙 F&B 매출 비중",값=pct(m["day_fnb_share"]),산식="D# 체류 F&B 순매출 ÷ 전체 F&B 순매출"),
  dict(지표="4. 목적·유형별 손님 비중 vs 매출 비중",값="아래 9목적·9유형 표",산식="관측 체류·인원 비중과 순매출 비중을 별도 산출"),
  dict(지표="5. 지출 상위 20% 체류 매출 비중",값=pct(m["top20_share"]),산식=f'{m["top20_count"]} / {m["stays"]}체류 · 상위 수 올림')]
 shown=[]
 for r in group:shown.append(dict(축=r["축"],값=r["값"],체류수=r["체류수"],손님팀비중=pct(r["손님팀비중"]),손님인원비중=pct(r["손님인원비중"]),매출비중=pct(r["매출비중"])))
 top=[]
 for r in allpairs[:10]:top.append(dict(A=r["A"],B=r["B"],공동수=r["공동수"],lift=round(r["lift"],3),주의=r["희소경고"]))
 compare=[]
 for r in comparison[:10]:compare.append(dict(A=r["A"],B=r["B"],생성공동수=r["생성공동수"],생성lift=round(r["생성lift"],3),후기공동수=r["후기공동수"],후기lift=round(r["후기lift"],3)))
 text=f"""# 업계 지표 · 행동 검증 — 2026-10-06

## 우리가 세운 질문
생성된 손님은 어느 고객군에서 매출을 만들고, 후기에서 함께 방문한 식당 조합을 재현하는가?

## 집계 기준
구매 날짜 {args.start}~{args.end}, {m['rows']:,}행, 관측 체류 {m['stays']:,}개. 원본 {len(original):,}행 중 기간 밖 {metadata['outside_period']:,}행을 제외했다. 조회 시점의 합본 파일이며 실행 날짜는 파일만으로 확정할 수 없다. 새 L5가 올라오면 입력만 바꿔 재집계한다.

**진행 상태: 기존 L5 집계·후기 대조 완료 / 새 L5 재집계 미완료.** 이번 보고서의 입력 SHA를 최신 합본과 대조한 뒤 새 파일 여부를 판단해야 한다. 새 파일을 받기 전에는 오후 작업 전체 완료로 표시하지 않는다.

- 체류 ID에 D#가 있으면 비투숙. 고객 한 명과 체류 한 팀을 구분한다.
- 인원 캡처율은 F&B 방문 팀의 일행 전원이 이용했다고 보는 인원 가중 지표다. 개인별 이용 여부는 L5만으로 알 수 없다.
- 전체 생성 명단이 없어 **실제 전체 투숙객 캡처율은 미상**이다. 여기서는 L5에 기록된 투숙 체류만 분모로 쓴다.
- F&B 업장은 합본 부문 정의를 따른다. 럭스바·IRD는 ROOM, 포함 라운지는 객실 패키지다. 별도 F&B 매출로 옮기지 않았다.
- 0원 포함 끼니도 식당 방문에 포함한다. IRD 0원 객실 식사는 호텔 식당 방문에 넣지 않는다.
- 객실 패키지 금액은 체크인 구매 날짜에 몰릴 수 있다. TRevPAR는 구매 기록 기준의 지표이며 회계상 일별 수익 인식으로 확정한 값이 아니다.
- 상위 20%는 관측 체류의 기간 내 지출을 합산하고 ceil(N×0.2)개를 택한다. 월 경계 밖 지출은 포함하지 않아 완결 체류 총지출과 다를 수 있다.

## 지표 다섯
{mdtable(headline,['지표','값','산식'])}

인원 가중 보조값: {m['guest_fnb_persons']:,}/{m['guest_persons']:,} = {pct(m['capture_observed_persons'])}. 식당 이용 팀의 동반 인원 전원이 이용했다고 보는 추정값이며 개인별 실제 캡처율로 발표하지 않는다.

목적·유형별 손님 비중과 매출 비중:
{mdtable(shown,['축','값','체류수','손님팀비중','손님인원비중','매출비중'])}

## 업장 공동 이용 lift 상위 10쌍
같은 체류에서 A와 B가 기록됐는지를 이진화한다. 반복 구매는 방문 수를 늘리지 않는다.
lift = (공동 체류 수/N) ÷ ((A 체류 수/N)×(B 체류 수/N)).
이는 **같은 시각의 동시 이용을 뜻하지 않는다**. 원본 L5에는 이용 시작·종료 시각이 없다. 객실과 무료 시설도 포함한 전체 업장 순위이며, 적은 공동 표본은 별도 표시했다.

{mdtable(top,['A','B','공동수','lift','주의'])}

## 후기와 같은 식당 범위로 대조
후기 분류 46편 중 분류가 확정된 {len(rev)}편만 사용, 유보·시험용·못 쓰는 글 {len(typ)-len(rev)}편 제외. 제외 파일의 원문·정답은 읽지 않았고 에이전트도 실행하지 않았다.
blog_types의 식당 근거와 주문 근거표의 방문식당을 합쳐 사용한다. 상품명이 미상이어도 방문식당은 쓸 수 있지만, 장소 추정 행은 제외한다. 비교 범위는 공통 식당 8곳과 럭스바 1곳이다. 럭스바를 비교에 포함하더라도 합본의 ROOM 귀속은 바꾸지 않는다.
라운지는 후기에는 있지만 L5에서 별도 업장 이용 행이 없어 같은 기준으로 lift를 산출할 수 없다. 전시 카페·미확정 라운지·후기의 시설 이용 전체도 이 두 근거표만으로는 대조하지 못한다. 해당 범위를 미방문 0으로 채우지 않는다.
생성 쪽은 체류, 후기 쪽은 글 단위이며 한 글에 여러 체류가 있을 수 있다. 후기 미기록은 미방문이라고 확정하지 않는다. 두 분모의 lift 차이를 정확도나 통계적 유의성으로 해석하지 않는다.

{mdtable(compare,['A','B','생성공동수','생성lift','후기공동수','후기lift'])}

## 후기에서 관측된 식당 조합 전체
{mdtable([dict(A=r['A'],B=r['B'],생성공동수=r['생성공동수'],생성lift=round(r['생성lift'],3),후기공동수=r['후기공동수'],후기lift=round(r['후기lift'],3)) for r in comparison if r['후기공동수']>0],['A','B','생성공동수','생성lift','후기공동수','후기lift'])}

## 멘토링에 가져갈 해석
- 높은 lift가 있어도 공동 표본 수를 함께 봐야 한다. 드문 업장 쌍의 높은 순위를 강한 행동 근거로 단정하지 않는다.
- 고객 목적·유형별 팀 비중과 매출 비중이 다른 이유는 지출 규모·동반 인원·박수·선택 상품을 함께 확인해야 한다. 목적이 매출을 직접 일으켰다는 인과 결론은 내리지 않는다.
- 생성에는 공동 방문이 있지만 후기에는 없는 쌍은 “미재현” 확정 대신 미기록·표본 부족·생성 과잉 후보로 남긴다.
- 후기의 공동 관측 {len(review_joint)}쌍 중 {reproduced}쌍은 생성 기록에도 있다. {rare_note} 높은 후기 lift 하나로 개선 목표를 정하면 안 된다.
- 생성에만 공동 기록이 있는 식당 쌍은 추가 확인 후보다. 상품·예약 조건·체류 길이를 맞추기 전에는 고객 재현 여부를 확정하지 않는다.
- 업계 벤치마크와 대조하려면 캡처율의 전체 투숙객/관측 체류/동반 인원 분모 및 포함 끼니·바 범위를 먼저 맞춰야 한다.

## 검수 · 재실행
기간별 합 = 일별 합, 목적별 매출 합 = 전체 매출, 목적 비중 합 = 1, 투숙+비투숙 = 전체 체류, lift 산식 일치 검사를 통과했다.
에이전트·생성기·상품표·정답·봉인 데이터 변경 없음. 실행 없이 CSV 집계만 했다.
입력 blob: L5 {metadata['l5_blob']}; blog_types {metadata['types_blob']}; 주문 근거표 {metadata['orders_blob']}.
대표님 모델 절대 금액 및 비밀번호 사이트 주소를 포함하지 않는다. 로컬 입력의 줄바꿈이 달라질 수 있어 원격 출처 SHA와 로컬 파일 SHA를 metrics.json에 따로 기록했다.
"""
 if ten:
  text+="\n## 10/10 하루 참고\n"+mdtable([dict(지표="TRevPAR",값=f'{ten["trevpar_daily_average"]:,.0f}원'),dict(지표="관측 투숙 인원 F&B 캡처율",값=pct(ten["capture_observed_persons"])),dict(지표="비투숙 F&B 비중",값=pct(ten["day_fnb_share"])),dict(지표="상위 20% 체류 매출 비중",값=pct(ten["top20_share"]))],["지표","값"])+"\n"
 (out/"업계지표_행동검증_20261006.md").write_text(text,encoding="utf-8")
 print(json.dumps(dict(metadata=metadata,metrics=m,day1010=ten,top_lift=top[:3],review_pairs=len(rp)),ensure_ascii=False))
if __name__=="__main__":main()

