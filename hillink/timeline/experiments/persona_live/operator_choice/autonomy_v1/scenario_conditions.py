"""C01 condition/candidate plumbing. Existing planner weights and pick stay intact."""
import copy
from contextlib import contextmanager,ExitStack
from unittest.mock import patch
from . import candidate_services as C
AD=C.AD;SP=C.SP;M=C.M4

def session_evaluations(snapshot,day,t,travel=0):
 """Keep declared event sessions separate from existing facility opening."""
 facility=C.windows(snapshot['venue_id'],day)
 results=[]
 for i,(begin,end) in enumerate(snapshot['sessions'] or []):
  start,close=AD.hm(begin),AD.hm(end);fits=[]
  for w in facility:
   opening=w.open_at.hour*60+w.open_at.minute;closing=w.close_at.hour*60+w.close_at.minute
   at=max(t+travel,start,opening);until=min(close,closing)
   if at+snapshot['duration_min']<=until:fits.append((at,until,opening,closing))
  best=min(fits) if fits else None
  results.append(dict(session_index=i+3 if snapshot['event_card_id']=='SANTA_KIDS_VILLAGE_2026' else i+1,declared_session=[begin,end],
   session_time_source='OFFICIAL_PACKAGE_SESSIONS_2026' if snapshot['event_card_id']=='SANTA_KIDS_VILLAGE_2026' else 'EXISTING_EXPLICIT_VIRTUAL_SCENARIO_NOT_OFFICIAL_CLOCKS',
   facility_windows=[[w.open_at.strftime('%H:%M'),w.close_at.strftime('%H:%M')] for w in facility],
   facility_source='EXISTING_C01_DATED_VENUE_WINDOW',travel_min=travel,
   candidate_available_at=best[0] if best else None,finish_at=best[0]+snapshot['duration_min'] if best else None,
   eligible_window=bool(best),planning_viability=('FUTURE_SERVICE_ONLY' if best[0]>t+travel else 'AVAILABLE_ON_ARRIVAL') if best else 'BLOCKED',
   blocked_reason=None if best else 'FACILITY_AND_SESSION_HAVE_NO_REMAINING_COMPLETE_ACTIVITY_WINDOW'))
 return results

def apply_session(o,s,day,t,travel=0):
 evaluations=session_evaluations(s,day,t,travel);fitting=[r for r in evaluations if r['eligible_window']]
 chosen=min(fitting,key=lambda r:r['candidate_available_at']) if fitting else evaluations[-1] if evaluations else None
 if chosen:o['window']={'start':chosen['declared_session'][0],'end':chosen['declared_session'][1]}
 o['service_contract'].update(service_window=copy.deepcopy(o.get('window')),session_evaluations=evaluations,event_session_index=chosen['session_index'] if chosen else None,
  candidate_available_at=chosen['candidate_available_at'] if chosen else None,
  planning_viability=chosen['planning_viability'] if chosen else 'BLOCKED')
 if not fitting:o.update(available=False,status='NO_COMPLETE_FACILITY_EVENT_SESSION')
 return o

@contextmanager
def install(sc,oid):
 s=sc['scenario_snapshot'];santa=s['event_card_id'] in ('SANTA_KIDS_VILLAGE_2025','SANTA_KIDS_VILLAGE_2026')
 original_init=AD.Agent.__init__;original_ok=AD.plan_ok;original_do=AD.plan_do;original_scope=M._step_scope;original_finish=AD.finish;original_snapshot=M.M4Context.snapshot
 def init(a,*args,**kwargs):
  original_init(a,*args,**kwargs)
  if s.get('arrival_time') and a.phase in ('checkin','visit'):a.t=AD.hm(s['arrival_time'])
  a.scenario_candidate_evaluations=[]
 def context(stage,a,t):
  value=original_snapshot(stage,a,t)
  value['scenario_inputs']=dict(scenario_id=s['scenario_id'],snapshot_sha256=s['snapshot_sha256'],
   date=sc['date'],weather=copy.deepcopy(s['weather']),arrival_time=s.get('arrival_time'),
   source='OPERATOR_VIRTUAL_CONDITIONS_NOT_CUSTOMER_OBSERVATIONS',
   weather_policy='ADVISORY_ONLY_UNLESS_AN_EXPLICIT_SOURCE_RULE_BLOCKS_THIS_PROGRAM')
  return value
 def candidate(a,world,t):return next(o for o in AD.engine_world_for(a,world,t)['offers'] if o['id']==oid)
 booked_map=(s.get('assumptions') or {}).get('booked_sessions') or {}
 session_end={x:y for x,y in ((s.get('assumptions') or {}).get('sessions') or [])}
 before_checkin=(s.get('assumptions') or {}).get('santa_before_checkin') or 'operator_virtual_allowed'
 def recommend(a):
  # 11/03: package sessions 3부 15:20 / 4부 16:30 recommended from this family's arrival, check-in (15:00 · 20분),
  # unpacking (35분) and walking time — the same obligations the engine executes. Not a preference score.
  if hasattr(a,'_santa_auto'):return a._santa_auto
  arrive=next((AD.hm(x['t']) for x in a.log if x.get('act')=='arrive'),a.t)
  venue=s['venue_id'];lobby=SP.lobby(a.B) if a.B else 'HOTEL_GATE'
  ready=arrive+15
  checkin_start=max(ready+SP.travel_min('HOTEL_GATE',lobby),AD.hm('15:00'))
  settled=checkin_start+20+SP.travel_min(lobby,a.room or lobby)+35
  pre_ok=before_checkin=='operator_virtual_allowed' and ready+SP.travel_min('HOTEL_GATE',venue)+60<=AD.hm('15:30')
  if pre_ok:pick,why='15:20','도착 후 체크인 전 3부 입장 가능(체크인 전 행사장 입장은 운영자 가상 허용 조건)'
  elif settled+SP.travel_min(a.room or lobby,venue)<=AD.hm('16:30'):pick,why='16:30',f'체크인·짐 정리 뒤 {AD.mh(settled)} 이후라 4부 권장'+('' if before_checkin=='operator_virtual_allowed' else ' · 체크인 전 입장 불가 조건')
  else:pick,why=None,f'도착 {AD.mh(arrive)} · 체크인·짐 정리 뒤 {AD.mh(settled)} — 4부(16:30) 시작 이후. 도착을 15:00 이전으로 앞당기면 4부 가능'
  a._santa_auto=(pick,why)
  a.scenario_candidate_evaluations.append(dict(customer_id=a.pid,date=a.sc['date'],minute=arrive,candidate_id=oid,booking_recommendation=pick,reason=why,
   before_checkin=before_checkin,arrival=AD.mh(arrive),settled_after_checkin=AD.mh(settled),score_contract='OPERATOR_BOOKED_SESSION_ASSUMPTION; RECOMMENDED_FROM_TIME_OBLIGATIONS'))
  return a._santa_auto
 def booking(a):
  # Operator assumption only: a booked session fixes when this family goes; it is not a predicted choice.
  b=booked_map.get(a.pid) if santa else None
  if not b or b['date']!=a.sc['date'] or oid in a.used:return None
  start=b['start']
  if start=='auto':
   start=recommend(a)[0]
   if not start:return None
  if before_checkin=='not_allowed' and not a.checked_in:return None   # wait for check-in; the engine still decides if it can make it
  return AD.hm(start),AD.hm(session_end[start])
 def plan_ok(a,code,t,world,why_out,revisit=False):
  if not santa or code!=oid:return original_ok(a,code,t,world,why_out,revisit)
  o=candidate(a,world,t);contract=o['service_contract'];arrival=t+SP.travel_min(a.loc,s['venue_id'])
  if not o['available']:why_out[code]=o.get('status','EVENT_UNAVAILABLE');return None
  bk=booking(a)
  if bk:
   start,end=bk
   if arrival>start:why_out[code]='BOOKED_SESSION_MISSED_ARRIVAL_AFTER_START';return None
   if start+o['duration_min']>end:why_out[code]='BOOKED_SESSION_CANNOT_FINISH';return None
   # A booked ticket is admission to this event venue only (same exception as the explicit admission condition).
   blocked=AD.LG.blocked
   with patch.object(AD.LG,'blocked',lambda actor,place:None if actor is a and place==s['venue_id'] else blocked(actor,place)):
    return original_ok(a,code,t,world,why_out,revisit)
  if arrival<AD.hm(o['window']['start']):why_out[code]='EVENT_SESSION_NOT_STARTED; FUTURE_PLANNING_ONLY';return None
  if arrival+o['duration_min']>AD.hm(o['window']['end']):why_out[code]='EVENT_SESSION_CANNOT_FINISH_AFTER_TRAVEL';return None
  if s['assumptions'].get('admission_allowed_as_virtual_condition') is True or (s['event_card_id']=='SANTA_KIDS_VILLAGE_2026' and a.pid in s['entitlements']):
   blocked=AD.LG.blocked
   # An explicit event-only scenario exception, never a general park policy.
   with patch.object(AD.LG,'blocked',lambda actor,place:None if actor is a and place==s['venue_id'] else blocked(actor,place)):
    return original_ok(a,code,t,world,why_out,revisit)
  return original_ok(a,code,t,world,why_out,revisit)
 def plan_do(a,code,loc,t,weights,rej,source='planner_rules',note=None):
  if not santa or code!=oid:return original_do(a,code,loc,t,weights,rej,source,note)
  o=candidate(a,AD.World(a.sc),t);why={}
  if not AD.plan_ok(a,code,t,AD.World(a.sc),why):raise ValueError('EVENT_PLAN_EXECUTION_BECAME_INELIGIBLE')
  bk=booking(a)
  if bk:
   rec=a.add('activity',code,o['label'],loc,t,o['duration_min'],'행사','operator_booking',
    f"이 가족은 {AD.mh(bk[0])} 회차를 사전 예약한 것으로 운영자가 가정했습니다. 예약 시각에 맞춰 이동합니다.",
    [dict(type='불확실',about='운영자 가정 · 사전 예약 회차. 고객이 스스로 산타를 고른다는 예측이 아님. 가상 회차이며 실제 예약 기록 아님')],
    dict(weights=weights,rejected=rej,note=note,c01_event_service=copy.deepcopy(o['service_contract']),booked_session=dict(start=AD.mh(bk[0]),end=AD.mh(bk[1])),
     score_contract='OPERATOR_BOOKED_SESSION_ASSUMPTION; NO_PREFERENCE_SCORE_USED'),offer=o,start_at=bk[0])
   a.used.add(code)
   return rec
  rec=a.add('activity',code,o['label'],loc,t,o['duration_min'],'행사','planner_rules',
   '가족권·시설·가상 회차·이동 후 완료 조건이 맞는 행사 후보를 기존 계획기의 다른 활동과 비교해 선택합니다. 행사별 개인 선호는 별도로 확인되지 않았습니다.',
   [dict(type='불확실',about='행사별 개인 선호식 미확인; 기존 계획기의 일반 활동 가중치와 현재 피로를 사용. 가상 회차이며 실제 예약 아님')],
   dict(weights=weights,rejected=rej,note=note,c01_event_service=copy.deepcopy(o['service_contract']),
    score_contract='EXISTING_PLANNER_GENERIC_ACTIVITY_AND_PACE; NO_NEW_PERSONAL_EVENT_COEFFICIENT'),offer=o)
  a.used.add(code)
  return rec
 @contextmanager
 def scope(stage):
  with original_scope(stage):
   original_plan=AD.plan_choose
   def plan(a,t,world,codes,wfn,domain_hint=None):
    bk=booking(a) if santa else None
    # Walk-in Santa planning stops at 15:30; a held booking keeps its own start (e.g. package 4부 16:30).
    if not santa or (t>=AD.hm('15:30') and not (bk and t<bk[0])):return original_plan(a,t,world,codes,wfn,domain_hint)
    if bk:
     start=bk[0];why={};location=AD.plan_ok(a,oid,t,world,why)
     def fits(c):
      try:loc=SP.ACT[c][1](a.B);dur=SP.ACT[c][3]
      except Exception:return False
      return t+SP.travel_min(a.loc,loc)+dur+SP.travel_min(loc,s['venue_id'])<=start
     free=[c for c in codes if c!=oid and fits(c)]
     record=dict(customer_id=a.pid,date=a.sc['date'],minute=t,candidate_id=oid,booked=True,booked_start=AD.mh(start),
      eligible=bool(location),blocked_reason=why.get(oid),excluded_for_booking=sorted(c for c in codes if c!=oid and c not in free),
      score_contract='OPERATOR_BOOKED_SESSION_ASSUMPTION; NO_PREFERENCE_SCORE_USED')
     if location and not free:
      record['selected']=True;a.scenario_candidate_evaluations.append(record);a._booking_selected=oid
      return (oid,location,{}),{}
     result=original_plan(a,t,world,free,wfn,domain_hint) if free else (None,{})
     if location and not result[0]:
      # Nothing else the engine would do before the booked start: go to the booking rather than an idle wait.
      record.update(selected=True,reason='NO_OTHER_ENGINE_CHOICE_BEFORE_BOOKED_START');a.scenario_candidate_evaluations.append(record);a._booking_selected=oid
      return (oid,location,{}),{}
     record['selected']=False;a.scenario_candidate_evaluations.append(record)
     return result
    o=candidate(a,world,t);why={};location=AD.plan_ok(a,oid,t,world,why)
    record=dict(customer_id=a.pid,date=a.sc['date'],minute=t,candidate_id=oid,
     eligible=bool(location),blocked_reason=why.get(oid),service_contract=copy.deepcopy(o['service_contract']),
     price_contract=copy.deepcopy(o['sku_contract']),
     weight=AD.pace_w(a,oid) if location else None,
     score_contract='EXISTING_PLANNER_GENERIC_ACTIVITY_AND_PACE; NO_NEW_PERSONAL_EVENT_COEFFICIENT')
    before=len(stage.decisions)
    result=original_plan(a,t,world,list(dict.fromkeys([*codes,oid])),lambda c:AD.pace_w(a,oid) if c==oid else wfn(c),domain_hint)
    record['selected']=bool(result and result[0]==oid)
    if len(stage.decisions)>before:
     packet=stage.decisions[-1]['packet']
     for row in packet['candidates']:
      if row['candidate_id']==oid:row.update(service_contract=record['service_contract'],price_contract=record['price_contract'],score_contract=record['score_contract'])
     packet['packet_sha256']=M.digest({k:v for k,v in packet.items() if k!='packet_sha256'});record['packet_sha256']=packet['packet_sha256']
    a.scenario_candidate_evaluations.append(record)
    return result
   with patch.object(AD,'plan_choose',plan):yield
 def booked_after_handoff(a,world,t):
  # The 15:30 engine handoff would otherwise skip a held later session (4부 16:30). Operator assumption, no preference score.
  bk=booking(a)
  if not bk or t>=bk[0]:return False
  why={};location=AD.plan_ok(a,oid,t,world,why)
  record=dict(customer_id=a.pid,date=a.sc['date'],minute=t,candidate_id=oid,booked=True,booked_start=AD.mh(bk[0]),eligible=bool(location),blocked_reason=why.get(oid),
   selected=bool(location),reason='BOOKED_SESSION_AFTER_15_30_ENGINE_HANDOFF',score_contract='OPERATOR_BOOKED_SESSION_ASSUMPTION; NO_PREFERENCE_SCORE_USED')
  a.scenario_candidate_evaluations.append(record)
  if not location:return False
  AD.plan_do(a,oid,location,t,{},{},source='operator_booking',note='사전 예약 회차(운영자 가정)');return True
 def finish(a):
  result=original_finish(a);result['scenario_candidate_evaluations']=copy.deepcopy(a.scenario_candidate_evaluations);return result
 with ExitStack() as stack:
  for obj,key,value in [(AD.Agent,'__init__',init),(AD,'plan_ok',plan_ok),(AD,'plan_do',plan_do),(M,'_step_scope',scope),(AD,'finish',finish),(M.M4Context,'snapshot',context)]:stack.enter_context(patch.object(obj,key,value))
  if santa and booked_map:stack.enter_context(patch.object(AD,'BOOKED_HOOK',booked_after_handoff))
  if santa:stack.enter_context(patch.dict(SP.ACT,{oid:(s['sources'][0]['record']['행사 · 상품명'],lambda b:s['venue_id'],'culture',s['duration_min'] or 1,False,False)}))
  yield
