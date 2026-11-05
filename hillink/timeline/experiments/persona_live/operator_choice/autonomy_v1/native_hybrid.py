"""Native selective review; source facts and native score coefficients are unchanged."""
import copy,hashlib,inspect,json,math,os,tempfile
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
from . import hybrid_review as R
from . import final_selection as F,review_identity as RI
POLICY='SELECTIVE_V12Z_NATIVE_V1'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,default=list).encode()).hexdigest()
def configuration():
 return dict(policy=POLICY,mode=os.environ.get('HILLINK_HYBRID','off'),arb=os.environ.get('HILLINK_HYBRID_ARB','adopt'),
  boundary_version='FINAL_SELECTION_BOUNDARY_V2',source_sha256={name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in [('native_hybrid',__file__),('hybrid_review',R.__file__),('review_identity',RI.__file__),('final_selection',F.__file__)]})

def valid_answer(answer):
 return isinstance(answer,dict) and answer.get('verdict') in ('agree','disagree') and isinstance(answer.get('choice'),str) and bool(answer['choice']) and type(answer.get('confidence')) in (int,float) and math.isfinite(answer['confidence']) and 0<=answer['confidence']<=1 and isinstance(answer.get('reasons'),list) and all(isinstance(reason,dict) and reason.get('type') in ('후기 근거','상황','업장 정보','일반 지식(미검증)') and isinstance(reason.get('text'),str) and isinstance(reason.get('fact_ids',[]),list) and all(isinstance(f,str) for f in reason.get('fact_ids',[])) for reason in answer['reasons'])

def active(a):return os.environ.get('HILLINK_NATIVE_HYBRID')=='1' and os.environ.get('HILLINK_V12Z_COMMON')=='1' and a.sc.get('hybrid_policy')==POLICY

def setup(a):
 R.STATE.setdefault('root',str(Path(__file__).resolve().parents[5]))
 if not R.STATE.get('out'):
  R.STATE['out']=tempfile.mkdtemp(prefix='hillink-hybrid-private-')
 R.STATE.setdefault('events',{})[a.pid]=copy.deepcopy(a.visit_history.get('m4_history') or [])

def remember(a,entry,offers,rule_choice,phase,minute):
 return F.prepare(a,entry,offers,rule_choice=rule_choice,phase=phase,minute=minute)

@contextmanager
def install(C):
 if os.environ.get('HILLINK_NATIVE_HYBRID')!='1':
  yield;return
 A=C.AD;E=C.EN;H=C.HR
 from . import llm_layer as LL
 from ..operator_world_v1_1 import turn_candidate as T
 original_call=R.call
 def checked_call(packet,config):
  try:answer,record=original_call(packet,dict(config,native_policy=POLICY+'+FINAL_SELECTION_BOUNDARY_V2'))
  except (ValueError,TypeError,KeyError,OSError) as error:
   return None,dict(skipped='INVALID_REVIEW_RULE_KEPT',error_type=type(error).__name__,cache_hit=False)
  record=dict(record,citable_fact_ids=packet.get('customer',{}).get('citable_fact_ids'))
  record.setdefault('input_sha256',RI.sha(packet))
  if answer is not None and not valid_answer(answer):
   return None,dict(record,skipped='INVALID_REVIEW_RULE_KEPT',rejected_answer=answer)
  return answer,record
 original_step=A.engine_step;original_add=A.Agent.add;original_breakfast=A.breakfast_step;original_turn=T.decide_turn;original_choose=H.choose;original_annotate=C.M4._annotate;original_plan_choose=A.plan_choose
 def plan_choose(a,t,*args,**kwargs):
  locked=F.pending(a)
  if locked and locked['phase']=='engine':
   return None,{'reviewed_selection':'Final reviewed action is committed; no planner redraw'}
  return original_plan_choose(a,t,*args,**kwargs)
 breakfast_stack=[];signature=inspect.signature(original_add);actors={}
 def blocked(a,t,rule,turn):
  actors[a.pid]=a
  try:R.cfg();return None
  except ValueError as error:
   if str(error) not in ('HYBRID_PAID_PROVIDER_NOT_AUTHORIZED','HYBRID_EXPLICIT_BUDGET_NOT_AUTHORIZED'):raise
   return dict(version=R.VERSION,customer_id=a.pid,date=a.sc['date'],time=A.mh(t),turn=turn,
    rule_choice=rule,final=rule,llm=None,outcome='REVIEW_AUTHORIZATION_BLOCKED_RULE_KEPT',
    triggers=[],call=dict(skipped='authorization',error=str(error),network_attempted=False,cache_hit=False))
 def step(a,world,t):
  d,w=original_step(a,world,t)
  if not d or not active(a):return d,w
  t=a.t  # A source closure inquiry may have advanced the clock before scoring.
  setup(a);by={o['id']:o for o in w['offers']};rows=[]
  selected={'offer':d['chosen'],'feasible':True,'score':d['score'],'total':d.get('total',d['score']),'terms':d.get('terms') or [],'next':d.get('next_plan')}
  for row in [selected]+list(d.get('rejected') or []):
   x=copy.deepcopy(row);o=by[x['offer']];x.setdefault('kind',o['kind']);x.setdefault('terms',E.score(o,t,dict(used=set(a.used),hunger=a.hunger_e),a.visit_e,a.traits,w) if x.get('feasible') else []);rows.append(x)
  no_call=blocked(a,t,d['chosen'],'engine')
  ev={'hybrid_review':no_call} if no_call else R.review(a,{'selected':d['chosen'],'candidates':rows},w,t,R.STATE['root'],R.STATE['out'],LL)
  record=remember(a,ev.get('hybrid_review'),by,d['chosen'],'engine',t)
  if record:
   d=copy.deepcopy(d);d['hybrid_review']=record
   if R.adopted(record):
    key=record['final'];o=by[key];q=next(x for x in rows if x['offer']==key);start=max(t,A.hm(o['window']['start'])) if o.get('window') else t
    d.update(rule_chosen=d['chosen'],chosen=key,label=o['label'],kind=o['kind'],score=q['score'],total=q['total'],terms=q['terms'],reasons=E.reasons_from_terms(q['terms'],a.traits),starts=A.mh(start),ends=A.mh(start+o['duration_min']),food_fraction=o['food']['meal_fraction'],out_of_pocket_pp=E.out_of_pocket(o),next_plan=q.get('next'),stage='선택')
  return d,w
 def breakfast(a,world,t):
  if not active(a):return original_breakfast(a,world,t)
  setup(a);breakfast_stack.append((a,t))
  try:return original_breakfast(a,world,t)
  finally:breakfast_stack.pop()
 def turn(*args,**kwargs):
  d=original_turn(*args,**kwargs)
  if not breakfast_stack:return d
  a,t=breakfast_stack[-1];w=args[2] if len(args)>2 else kwargs['world'];rule=d['chosen']['id'];before=copy.deepcopy(d);no_call=blocked(a,t,rule,'breakfast');d=dict(d,hybrid_review=no_call) if no_call else R.review_turn(a,d,w,t,'breakfast',LL);record=remember(a,d.get('hybrid_review'),{o['id']:o for o in w['offers']},rule,'breakfast',t)
  if record and record.get('validation_error'):before['hybrid_review']=record;return before
  if record:d['hybrid_review']=record
  return d
 def choose(a,choices,t,duration,world):
  locked=F.pending(a)
  if locked:
   offers=[H.offer(a,c,t,duration,world) for c in choices];offer=next((o for o in offers if o['id']==locked['entry']['final']),None)
   if offer is None:raise ValueError('REVIEW_FINAL_NOT_IN_EXECUTION_OPTIONS')
   F.verify(a,offer,offer['id']);return offer,dict(selected=offer['id'],hybrid_review=locked['entry'],selection_locked=True,candidates=[])
  o,tr=original_choose(a,choices,t,duration,world)
  if not o or not active(a) or not choices or choices[0].get('service_period')!='lunch':return o,tr
  setup(a);offers=[H.offer(a,c,t,duration,world) for c in choices];by={x['id']:x for x in offers};weights={x['candidate_id']:x['score'] for x in tr['candidates']}
  alts=[dict(id=x['id'],code=x['id'],label=x['label'],venue=x['venue'],price_pp=x['price_pp_krw'],weight=weights[x['id']],kind=x['kind']) for x in offers]
  chosen=next(x for x in alts if x['id']==o['id']);no_call=blocked(a,t,o['id'],'lunch');adopted,record=(None,no_call) if no_call else R.review_lunch(a,t,'lunch',chosen,alts,by,LL)
  record=remember(a,record,by,o['id'],'lunch',t)
  if record and R.adopted(record):o=by[record['final']];tr=copy.deepcopy(tr);tr['selected']=record['final']
  if record:tr=copy.deepcopy(tr);tr['hybrid_review']=record
  return o,tr
 def add(a,*args,**kwargs):
  entry=getattr(a,'_native_review',None)
  if not entry:return original_add(a,*args,**kwargs)
  bound=signature.bind(a,*args,**kwargs);v=bound.arguments;offer=v.get('offer');code=v.get('code')
  if (offer or {}).get('id')!=entry['final'] and code!=entry['final']:
   if F.pending(a):F.verify(a,offer,code)
   return original_add(a,*args,**kwargs)
  F.verify(a,offer,code)
  internal=copy.deepcopy(v.get('internal') or {});review=R.scene_record(entry);review.update(review_time=entry['time'],date=entry['date'],customer_id=a.pid,turn=entry.get('turn','engine'),selection_id=entry['selection_id'],llm=entry.get('llm'),call=entry.get('call'),rule_label=entry.get('rule_label'),final_label=entry.get('final_label'))
  if R.adopted(entry):
   why,ids,adopted_record=R.scene_explain(entry,set(a.traits.get('evidence_index') or {}));review.update(adopted_record,**RI.execution(entry));review['decided_by']='SYNTHETIC_REVIEW_ADOPTED' if entry['review_execution']=='SYNTHETIC_TEST' else 'LLM_REVIEW_ADOPTED';v['why']=why;v['evidence']=a.ev_review(ids,'LLM 검토가 인용한 후기 사실',target={entry['final'],v.get('loc')},strict=True,slot=A.LG.meal_slot(v.get('t0',a.t))) or [dict(type='프로파일 기반 추론',traits=[],about='검토된 상황·업장 정보')]
  internal['decision_trace']=review;internal['selection_id']=entry['selection_id'];v['internal']=internal
  if offer:
   offer=copy.deepcopy(offer)
   if offer.get('sku_contract'):
    offer['sku_contract']['selection_id']=entry['selection_id']
    offer['sku_contract']['final_candidate_id']=entry['final']
   v['offer']=offer
  result=original_add(*bound.args,**bound.kwargs);review.update(execution_state='EXECUTED',actual_candidate_id=(offer or {}).get('id') or code);F.consumed(a,(offer or {}).get('id') or code);return result
 def annotate(result,stage,pid,scenario,inputs):
  result=original_annotate(result,stage,pid,scenario,inputs)
  result['native_review_attempts']=copy.deepcopy(getattr(actors.get(pid),'_native_review_attempts',[]))
  if actors.get(pid) and F.pending(actors[pid]):raise ValueError('REVIEW_FINAL_NOT_EXECUTED_BEFORE_DAY_END')
  result['m4']['review_attempts']=result['native_review_attempts']
  reviews=[x['internal']['decision_trace'] for x in result['log'] if (x.get('internal') or {}).get('decision_trace')]
  if reviews:
   result['native_hybrid_reviews']=reviews
   for review in reviews:
    minute=A.hm(review['review_time'])
    for record in result['m4']['decisions']:
     ctx=record['packet']['context_factors']
     if ctx['date']==review['date'] and ctx['time']==minute:
      record['selection_id']=review['selection_id'];record['hybrid_review']=review
      if review['decided_by'] in ('LLM_REVIEW_ADOPTED','SYNTHETIC_REVIEW_ADOPTED'):
       record['rule_selected_action']=review['rule_choice'];record['selected_action']=review['final'];record['rule_decision_mode']=record['decision_mode']
       record['decision_mode']='SYNTHETIC_TEST_REVIEW' if review['decided_by']=='SYNTHETIC_REVIEW_ADOPTED' else 'LLM_CACHE_REPLAY' if review['review_execution']=='CACHE_REPLAY' else 'LIVE_LLM_REVIEW'
       record['llm_choice']=None if review['decided_by']=='SYNTHETIC_REVIEW_ADOPTED' else review['final']
       if record.get('actual_next_action')==review['final']:record['execution_status']='EXECUTED'
  for record in result['m4']['decisions']:
   record.update(RI.execution(record.get('hybrid_review')))
  return result
 with patch.object(R,'call',checked_call),patch.object(A,'engine_step',step),patch.object(A,'plan_choose',plan_choose),patch.object(A,'breakfast_step',breakfast),patch.object(T,'decide_turn',turn),patch.object(H,'choose',choose),patch.object(A.Agent,'add',add),patch.object(C.M4,'_annotate',annotate):
  yield
