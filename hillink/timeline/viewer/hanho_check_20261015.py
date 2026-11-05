"""재계산 보조 · 적용 중인 기본 모델/입력은 수정하지 않음.

화면 범위: 새 체크인 집단의 당일 + 익일 중식 대리(더뷔페 조식 제외).
달력일 범위: 기본 앞 3일 생성, 2박 이월 공급 차감과 좌석 공유, 목표 날짜 행동만 집계.
럭스바·르파사쥬는 결제 상품 수량만 집계하며 착석 인원을 더하지 않는다.
잔·병·바스켓의 원래 단위를 따로 기록한다. 음료 수량 합을 실제 잔 수로 바꾸지 않는다.
interest: 비투숙 규모 1을 유지하고 피자힐 선호만 바꿈. 방문 예측 아님.
검색 배율 r는 내부 가중2와 anomaly_k=r-1로 구현되어 최종 1+(2-1)*(r-1)=r.
표 후보의 가중r, anomaly_k=1과 같은 설정이다. 출력은 로컬 전용.
"""
import sys,os,json,copy,random,contextlib,io,argparse,hashlib,csv
from pathlib import Path
from datetime import datetime,timedelta
from collections import Counter,defaultdict
parser=argparse.ArgumentParser(description='한호 10/15 추가 날짜·이월·검색 선호 실험. 한 호출당 새 프로세스. 원문 후기는 재실행하지 않음.')
parser.add_argument('kind',choices=['screen','operating','interest'])
parser.add_argument('date')
parser.add_argument('seed',type=int)
parser.add_argument('--ratio',type=float,help='interest 모드: 검색 배율. 방문 전환율 아님')
parser.add_argument('--output',type=Path,required=True,help='저장소 밖 로컬 결과 폴더')
parser.add_argument('--warmup',type=int,default=3,help='operating: 목표일 이전 생성 일수(기본 3일, 과거 조건 재확인은 2일)')
a=parser.parse_args()
if a.kind=='interest' and (a.ratio is None or a.ratio<=1):parser.error('interest 모드는 --ratio 1 초과 필요')
if a.warmup<0:parser.error('--warmup은 0 이상이어야 함')
R=Path(__file__).resolve().parent.parent.parent;O=a.output.resolve();O.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(R/'timeline'),str(R/'timeline/viewer')]
os.environ['WH_PURPOSE_MIX']='onto';os.environ['WH_ROOM_FORMULA']='1'
from viewer import engine as E
import generate as G,revenue,agent_v4
from capacity import Capacity
kind,target,seed=a.kind,a.date,a.seed; th=dict(E.V4,seed=seed)
E.CACHE=O/'cache';E.CACHE.mkdir(exist_ok=True)
if kind in ('screen','interest'):
 if kind=='interest':
  ratio=a.ratio;th.update(anomaly=4,anomaly_k=ratio-1);original=E.load_anomalies
  def experimental_table(name='anomaly_scenarios.csv'):
   rows=original(name)
   if name=='anomaly_scenarios.csv':
    for row in rows:
     if str(row['ID'])=='4':
      row['비투숙 배율']='1';row['가고 싶음 배율']='PIZZA_HILL:2';row['크기 출처 (signal_stats · 문서)']='S01W · 검색 피크/직전4주 · 관심을 선호에 그대로 옮기는 가정';row['설명']='검색 관심 크기만 선호 가중에 옮기는 조건부 실험 · 비투숙 수요 증가 없음'
   return rows
  E.load_anomalies=experimental_table
 with contextlib.redirect_stdout(io.StringIO()): d=E.day(target,'none',1,th)
 if not isinstance(d,dict): d=json.loads((E.CACHE/(E.day_key(target,'none',1,th)+'.json')).read_text(encoding='utf-8'))
 vals={}
 for loc,v in d['venue_detail'].items():
  if loc in ['LUX_BAR','LE_PASSAGE']: vals[loc]=sum(v['l4_qty_day'].values());continue
  same=[w for w in v['windows'] if '익일' not in w['name'] and w['kind']!='조식']; nxt=[w for w in v['windows'] if '익일' in w['name'] and w['kind']=='중식']
  vals[loc]=sum(w['persons'] for w in same+nxt)
 out={'frame':'화면 범위(당일 체크인 + 익일 중식 대리)','date':target,'seed':seed,'key':d['key'],'counts':vals,'n':d['n'],'model_ver':d['model_ver'],'input_ver':d['input_ver'],'versions_current':True,'experiment_ratio':a.ratio if kind=='interest' else None,'screen_total':d['total'],'hotel_total_excluding_theatre':d['total']-d['by_l3'].get('빛의 시어터',0),'by_l3':d['by_l3'],'pizza_detail':d['venue_detail'].get('PIZZA_HILL'),'theta':th,'experimental_table_override':kind=='interest'}
else:
 agent_v4.THETA_FIT.update(th);G.SEED=20261001+seed;revenue.SEED=20260930+seed;revenue.RNG_TEAM=True
 os.environ['WH_SEARCH_WEIGHT']='0'
 for envkey in ('WH_POSTING_K','WH_TREND','WH_WD'):os.environ.pop(envkey,None)
 for prop,n in [('GRAND',507),('VISTA',244),('DOUGLAS',50)]: G.ROOMS[prop]['n']=n
 E.apply_scenario('none',target)
 grid,factors=G.load_grid(),G.load_factors();pm=G.load_mix(R/'timeline/purpose_mix.csv');am=G.load_mix(R/'timeline/age_mix.csv',key='연령');tm=G.load_type_mix();bc=G.load_day_scenarios()
 cap=Capacity();cap.cap['모에기']=40;catch=E.Catch();carry={};counts=Counter();groups=defaultdict(Counter);occupied={};warm=[]
 bar_seated=Counter();bar_seated_groups=defaultdict(Counter);paid_units=defaultdict(Counter);product_units=defaultdict(set);product_qty=Counter();dining_kinds=defaultdict(Counter)
 for row in csv.DictReader((R/'timeline/menu.csv').open(encoding='utf-8-sig',newline='')):product_units[(row['업장'],row['상품'])].add(row['단위'])
 for ix in range(-a.warmup,1):
  dt=datetime.fromisoformat(target)+timedelta(days=ix);day=dt.date().isoformat(); E.apply_scenario('none',day); cap.prune(dt); cfg=copy.deepcopy(bc)
  if agent_v4.is_weekday(dt.date()):cfg['scenarios']['base']=round(cfg['scenarios']['base']*.5)
  with contextlib.redirect_stdout(io.StringIO()):stays=G.guests_for(day,grid,factors,scale=1,purpose_mix=pm,type_mix=tm,carry=carry,day_scenario='base',day_config=cfg,age_mix=am)
  random.Random(G.SEED+7).shuffle(stays);new=Counter(m.PERSONA.property for _,_,m in stays if m.PERSONA.is_guest);occupied[day]={p:new[p]+carry.get(p,0) for p in G.ROOMS};nxt=Counter()
  for gid,_,m in stays:
   p=m.PERSONA;lines=revenue.spend_lines(m,k=1,capacity=cap)
   if p.is_guest and p.nights>=2:nxt[p.property]+=1
   segs,traces=catch.last;det=E.detail_json(p,m.START_AT,segs,traces,lines);g=('당일투숙' if day==target else '이전투숙') if p.is_guest else '비투숙'
   for s in det['steps']:
    if s['t_in'][:10]!=target:continue
    if s['kind']=='meal' and s.get('state')!='TAKEOUT_ORDER' and s.get('venue') and not(s['venue']=='THE_BUFFET' and '조식' in s['label']):
     if s['venue'] in ('LUX_BAR','LE_PASSAGE'):
      bar_seated[s['venue']]+=p.party_size;bar_seated_groups[s['venue']][g]+=p.party_size
     else:
      counts[s['venue']]+=p.party_size;groups[s['venue']][g]+=p.party_size
      t=datetime.fromisoformat(s['t_in']);slot=next((w['kind'] for w in E.venue_windows(s['venue'],t.date()) if w['t0']<=t<w['t1']),'창 밖')
      dining_kinds[s['venue']][slot]+=p.party_size
    for sp in s['spend']:
     loc={'럭스바':'LUX_BAR','르파사쥬':'LE_PASSAGE'}.get(sp['l3'])
     if loc:
      counts[loc]+=sp['qty'];groups[loc][g]+=sp['qty']
      units=product_units.get((sp['l3'],sp['product']),set())
      unit=next(iter(units)) if len(units)==1 else ('1잔(가격표 대리)' if s['key']=='lux' and sp['product']=='lux' else '단위 미확정')
      paid_units[loc][unit]+=sp['qty'];product_qty[(loc,sp['product'],unit)]+=sp['qty']
  print('완료한 생성일',day,flush=True)
  carry=dict(nxt);warm.append({'date':day,'new_rooms':sum(new.values()),'occupied_rooms':sum(occupied[day].values()),'new_teams':len(stays)})
 assert all(sum(g.values())==counts[loc] for loc,g in groups.items())
 assert all(sum(q.values())==counts[loc] for loc,q in paid_units.items())
 out={'frame':f'운영일 범위(앞 {a.warmup}일 이어 생성·이월 포함)','date':target,'seed':seed,'counts':counts,'groups':groups,'warmup':warm,'warmup_days':a.warmup,'max_nights':2,'model_ver':E._version.model_ver(),'input_ver':E._version.input_ver(),'initial_carry':f'워밍업 시작일 이월 0 · 이전 {a.warmup}일 생성의 목표일 행동 포함','counting_revision':'착석 인원과 결제 수량 분리 · 럭스바/르파사쥬 결제만 합산','bar_meal_seated_excluded':bar_seated,'bar_meal_seated_groups_excluded':bar_seated_groups,'payment_quantity_by_original_unit':paid_units,'payment_product_quantities':[dict(venue=loc,product=prod,unit=unit,qty=q) for (loc,prod,unit),q in sorted(product_qty.items())],'dining_kind_person_visits':dining_kinds,'legacy_mixed_counter_diagnostic':{loc:counts[loc]+bar_seated[loc] for loc in ('LUX_BAR','LE_PASSAGE')}}
if kind=='interest':
 # 실험용 표 덮어쓰기는 기본 입력 해시에 잡히지 않으므로 독립 입력 해시와 표시를 남긴다.
 out['versions_current']=False;out['base_input_ver']=out['input_ver']
 out['input_ver']='custom-'+hashlib.sha256(json.dumps({'ratio':ratio,'external':1,'pref_reference':2},sort_keys=True).encode()).hexdigest()[:8]
 cache=E.CACHE/(out['key']+'.json');md=json.loads(cache.read_text(encoding='utf-8'))
 md.update(base_input_ver=out['base_input_ver'],input_ver=out['input_ver'],experimental_table_override=True)
 cache.write_text(json.dumps(md,ensure_ascii=False),encoding='utf-8')
(O/(f'{kind}_{target}_{seed}'+(f'_{ratio:.6f}' if kind=='interest' else '')+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'done':kind,'date':target,'seed':seed,'counts':out['counts']},ensure_ascii=True))
