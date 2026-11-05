"""One reviewed selection, one execution. Quoted order is immutable at commit."""
import copy,hashlib,json
from . import review_identity as RI

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=list).encode()).hexdigest()
def quote(offer):return copy.deepcopy((offer or {}).get('sku_contract'))

def prepare(actor,entry,offers,*,rule_choice,phase,minute):
    if not entry:return None
    if pending(actor):raise ValueError('REVIEW_COMMIT_ALREADY_PENDING')
    e=copy.deepcopy(entry);e['review_rule_choice']=e.get('rule_choice');e['native_rule_choice']=rule_choice
    e['review_rule_label']=e.get('rule_label');e['review_final_label']=e.get('final_label')
    e['rule_choice']=rule_choice;e['phase']=phase;e['decision_minute']=minute
    e['review_raw_choice']=(e.get('llm') or {}).get('choice')
    e['join_scope']=['run_id','customer_id','selection_id']
    proposed=e.get('final');adopted='ADOPTED' in str(e.get('outcome'))
    facts={f for r in (e.get('llm') or {}).get('reasons',[]) for f in r.get('fact_ids',[])}
    allowed=set(actor.traits.get('evidence_index') or {})
    packet_facts=(e.get('call') or {}).get('citable_fact_ids')
    if packet_facts is not None:allowed &= set(packet_facts)
    unknown=facts-allowed
    if unknown:e['validation_error']='REVIEW_FACT_NOT_IN_INPUT';e['unknown_fact_ids']=sorted(unknown)
    if adopted:
        if proposed not in offers:e['validation_error']='REVIEW_FINAL_NOT_IN_INPUT_CANDIDATES'
        elif offers[proposed].get('available') is False:e['validation_error']='REVIEW_FINAL_NOT_EXECUTABLE'
        elif proposed=='ROOM_REST' and not actor.stay:e['validation_error']='NON_GUEST_ROOM_REST_EXECUTION_NOT_SUPPORTED'
        elif RI.execution(e)['review_execution'] not in ('CACHE_REPLAY','LIVE_REVIEW','SYNTHETIC_TEST'):
            e['validation_error']='REVIEW_ORIGIN_NOT_VERIFIED'
        if e.get('validation_error'):
            e['review_proposed_final']=proposed;e['outcome']=e['validation_error']+'_RULE_KEPT';adopted=False
    if e.get('validation_error') and not adopted:
        e['outcome']=e['validation_error']+'_RULE_KEPT'
    if not adopted:e['final']=rule_choice
    e['rule_label']=(offers.get(rule_choice) or {}).get('label') or e.get('rule_label')
    e['final_label']=(offers.get(e['final']) or {}).get('label') or e.get('final_label')
    e.update(RI.execution(e));e['execution_state']='PENDING_REVIEWED_CHOICE' if adopted else 'RULE_PROPOSAL'
    e['selection_id']=digest(dict(customer=actor.pid,date=actor.sc['date'],time=minute,phase=phase,
        seed=actor.sc.get('seed'),rule=rule_choice,final=e['final'],input_sha=e.get('call',{}).get('input_sha256'),
        scenario=actor.sc.get('visit_resolution')))[:24]
    actor._native_review=e
    actor.__dict__.setdefault('_native_review_attempts',[]).append(e)
    if adopted:
        offer=copy.deepcopy(offers[e['final']]);actor._native_commit=dict(entry=e,offer=offer,quote_sha256=digest(quote(offer)),
            customer_id=actor.pid,date=actor.sc['date'],minute=minute,actor_clock=actor.t,phase=phase)
    else:actor._native_commit=None
    return e

def pending(actor):
    c=getattr(actor,'_native_commit',None)
    if c and (c['customer_id']!=actor.pid or c['date']!=actor.sc['date'] or c['actor_clock']!=actor.t):
        raise ValueError('REVIEW_COMMIT_CONTEXT_CHANGED')
    return c

def verify(actor,offer,code):
    c=pending(actor)
    if not c:return
    if (offer is not None and offer.get('id')!=c['entry']['final']) or (offer is None and code!=c['entry']['final']):
        raise ValueError('REVIEW_FINAL_REPLACED_BEFORE_EXECUTION')
    if digest(quote(offer))!=c['quote_sha256']:
        raise ValueError('REVIEW_ORDER_CHANGED_BEFORE_EXECUTION')

def consumed(actor,actual_id):
    e=getattr(actor,'_native_review',None)
    if e:e.update(execution_state='EXECUTED',actual_candidate_id=actual_id)
    actor._native_commit=None;actor._native_review=None
