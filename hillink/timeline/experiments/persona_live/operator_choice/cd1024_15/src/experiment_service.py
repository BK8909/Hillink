"""Local-only CD-1024-15 execution interface; no web/API calls or product writes."""
from __future__ import annotations
import copy, hashlib, json, sys
from pathlib import Path
from datetime import datetime
from offer_eligibility import check_offer

ROOT=Path(__file__).resolve().parents[1]
CATALOG_PATH=ROOT/'offer_catalog.json'
CD14_ROOT=Path('/private/tmp/hillink-cd1024-14-private-20261024')
ENGINE_CODE=Path('/private/tmp/hillink-cd1023-09-private-20261023/code_v3/timeline/experiments/persona_live')
PRODUCT_WORKTREE=Path('/Users/tk/Downloads/워커힐/wh_turn_isolation_fix_20261023')
EXPECTED_ENGINE_VERSION='0939cb89f9217fd521d2079186c2359b876937d4'
EXPECTED_CATALOG_VERSION='cd1024-15-isolated-v1'
MARGIN_NARROW=0.01
MARGIN_LOW=0.20

sys.path.insert(0,str(ENGINE_CODE))
from operator_choice.operator_world_v1 import engine as EN
from operator_choice.operator_world_v1 import world as WD
from operator_choice.operator_world_v1.__main__ import PRESETS
from operator_choice.operator_world_v1_1.turn_candidate import turn_world
from operator_choice.operator_world_v1_1.turn_view import common_baseline,split_reason
from operator_choice.operator_world_v1_1.candidate import candidate_engine


def _sha(data):
    raw=data if isinstance(data,bytes) else json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def _file_sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def _load_catalog(): return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))

def _load_profiles():
    d=ENGINE_CODE/'operator_choice/operator_world_v1_1'
    p=json.loads((d/'turn_personas_rbase.json').read_text())['personas']
    p.update(json.loads((d/'turn_personas_ext.json').read_text())['personas'])
    local=PRODUCT_WORKTREE/'timeline/experiments/persona_live/operator_choice/operator_world_v1_1/turn_personas_ext.local.json'
    p.update(json.loads(local.read_text())['personas'])
    return p

def _validate_request(req,catalog,profiles):
    required=['scenario_id','simulation_date','meal_period','start_time','duration_minutes','party_size','party_composition','stay_status','reservation_assumption','seat_type','selected_persona_ids','offer_overrides','catalog_version','engine_version','is_public_holiday']
    missing=[k for k in required if k not in req]
    if missing: raise ValueError('missing_required_fields:'+','.join(missing))
    if req['catalog_version']!=catalog.get('catalog_version'): raise ValueError('catalog_version_mismatch')
    if req['engine_version']!=EXPECTED_ENGINE_VERSION: raise ValueError('engine_version_mismatch')
    if req['meal_period']!='dinner': raise ValueError('unsupported_meal_period')
    if not isinstance(req['duration_minutes'],int) or req['duration_minutes']<1: raise ValueError('invalid_duration_minutes')
    if not isinstance(req['party_size'],int) or req['party_size']<1: raise ValueError('invalid_party_size')
    comp=req['party_composition']
    if not isinstance(comp,dict) or not all(isinstance(comp.get(k),int) and comp[k]>=0 for k in ('adults','children')) or comp['adults']+comp['children']!=req['party_size']:
        raise ValueError('party_composition_must_match_party_size')
    if req['stay_status'] not in ('staying','non_staying','unknown'): raise ValueError('invalid_stay_status')
    if not isinstance(req['reservation_assumption'],bool): raise ValueError('reservation_assumption_must_be_boolean')
    if not isinstance(req['is_public_holiday'],bool): raise ValueError('is_public_holiday_must_be_boolean')
    ids=req['selected_persona_ids']
    if not isinstance(ids,list) or not ids: raise ValueError('selected_persona_ids_must_be_nonempty_list')
    if len(ids)!=len(set(ids)): raise ValueError('duplicate_persona_id')
    unknown=[x for x in ids if x not in profiles]
    if unknown: raise ValueError('unknown_persona_ids:'+','.join(unknown))
    if not isinstance(req['offer_overrides'],dict): raise ValueError('offer_overrides_must_be_object')
    offer_ids={x['offer_id'] for x in catalog['offers']}
    unknown_offers=set(req['offer_overrides'])-offer_ids
    if unknown_offers: raise ValueError('unknown_offer_override:'+','.join(sorted(unknown_offers)))
    for oid,ov in req['offer_overrides'].items():
        if not isinstance(ov,dict): raise ValueError('invalid_offer_override:'+oid)
        if 'discount_amount' in ov and 'price_amount' in ov: raise ValueError('choose_price_or_discount_override:'+oid)
        if 'discount_amount' in ov:
            if not isinstance(ov['discount_amount'],(int,float)) or ov['discount_amount']<0: raise ValueError('invalid_discount_amount:'+oid)
            if ov.get('discount_unit') not in ('per_person','per_party'): raise ValueError('discount_unit_required:'+oid)
            offer=next(x for x in catalog['offers'] if x['offer_id']==oid)
            if offer.get('price_amount') is not None and offer.get('price_basis') in ('per_person_course','per_adult'):
                per_person=float(ov['discount_amount'])/(req['party_size'] if ov['discount_unit']=='per_party' else 1)
                if per_person>float(offer['price_amount']): raise ValueError('discount_exceeds_catalog_price:'+oid)
        if 'price_amount' in ov:
            if not isinstance(ov['price_amount'],(int,float)) or ov['price_amount']<0: raise ValueError('invalid_price_amount:'+oid)
            if ov.get('price_unit') not in ('per_person','per_party'): raise ValueError('price_unit_required:'+oid)
    return None

def _eligibility(req,catalog):
    reservation_confirmed=True if req['reservation_assumption'] else False
    er=[]; eligible=[]
    for offer in catalog['offers']:
        ans=check_offer(offer,req,allow_scenario=bool(req.get('allow_scenario_offers',False)),reservation_confirmed=reservation_confirmed)
        row={'venue_id':offer['venue_id'],'offer_id':offer['offer_id'],'offer_name':offer['offer_name'],'verification_status':offer['verification_status'],'scenario_only':bool(offer.get('scenario_only')),'eligibility_status':ans['status'],'reasons':ans['reasons'],'price_amount':offer.get('price_amount'),'price_basis':offer.get('price_basis'),'valid_from':offer.get('valid_from'),'valid_to':offer.get('valid_to'),'source_checked_at':offer.get('source_checked_at'),'source_url':offer.get('source_url'),'reservation_basis':'operator_assumes_offer_reservation_conditions_met_not_live_inventory' if offer.get('reservation_required') and req['reservation_assumption'] else ('operator_assumes_reservation_unavailable' if offer.get('reservation_required') else 'not_required')}
        ov=req['offer_overrides'].get(offer['offer_id'],{})
        if ov:
            row['operator_override']={k:ov.get(k) for k in ('price_amount','price_unit','discount_amount','discount_unit','scenario_label') if k in ov}
            row['operator_override_is_scenario']=True
            party=req['party_size']
            calc={}
            if 'discount_amount' in ov:
                per_person=float(ov['discount_amount'])/(party if ov['discount_unit']=='per_party' else 1)
                calc.update({'discount_effective_krw_per_person':per_person,'discount_effective_krw_for_party':per_person*party})
            if 'price_amount' in ov:
                per_person=float(ov['price_amount'])/(party if ov['price_unit']=='per_party' else 1)
                calc.update({'price_effective_krw_per_person':per_person,'price_effective_krw_for_party':per_person*party})
            row['override_price_calculation']=calc
        er.append(row)
        if ans['status']=='ELIGIBLE': eligible.append(offer['offer_id'])
    return er,eligible

def _engine_world(req,eligible,overrides):
    preset=next(p for p in PRESETS if p['id']=='closed')
    base=copy.deepcopy(preset['levers'])
    product_levers={}
    party=req['party_size']
    for oid in eligible:
        ov=overrides.get(oid,{})
        target=oid
        if 'discount_amount' in ov:
            amt=float(ov['discount_amount'])
            if ov['discount_unit']=='per_party': amt=amt/party
            base.setdefault(target,{})['guest_discount_krw']=amt
        if 'price_amount' in ov:
            amt=float(ov['price_amount'])
            if ov['price_unit']=='per_party': amt=amt/party
            base.setdefault(target,{})['price_pp_krw']=amt
    world,excluded=turn_world('dinner','historical',party,product_levers=product_levers,base_levers=base)
    by={o['id']:o for o in world['offers']}
    absent=[x for x in eligible if x not in by]
    if absent: return None,absent,excluded
    world=dict(world,offers=[by[x] for x in eligible])
    return world,[],excluded

def _score_persona(pid,req,world,profiles):
    traits=profiles[pid]['traits']
    visit=dict(WD.default_visit(pid),party_size=req['party_size'])
    visit['purpose']=f"CD1024-15 {req['stay_status']} operating scenario (assumption)"
    visit['checkin']=req['start_time']
    state={'used':set(),'hunger':1.0,'_depth':99}
    t=EN.hm(req['start_time']); candidates=[]
    for o in world['offers']:
        with candidate_engine(c1=True,c2='venue_visits',c3=True):
            blocked=EN.feasible(o,t,state,visit)
            terms=EN.score(o,t,state,visit,traits,world) if not blocked else []
        if blocked: continue
        base_terms=common_baseline(o,visit,world,'dinner')
        parts=[split_reason({'factor':x['factor'],'value':x['value'],'facet':x.get('facet'),'fact_ids':x.get('fact_ids',[]),'note':x.get('note','')},o,base_terms) for x in terms]
        cand={'offer_id':o['id'],'venue_id':o['venue'],'offer_name':o['label'],'score':round(sum(x['value'] for x in terms),4),'price_pp_krw':o['price_pp_krw'],'common_contribution':round(sum(x['common'] for x in parts),4),'personal_contribution':round(sum(x['review'] for x in parts),4),'assumption_contribution':round(sum(x['assumption'] for x in parts),4),'fact_ids':sorted({f for x in terms for f in x.get('fact_ids',[])}),'terms':[{'factor':x['factor'],'value':round(x['value'],4),'kind':x.get('kind'),'facet':x.get('facet'),'fact_ids':x.get('fact_ids',[])} for x in terms]}
        candidates.append(cand)
    return sorted(candidates,key=lambda x:(-x['score'],x['offer_id']))

def _pick(rows): return rows[0] if rows else None

def _margin_flag(m):
    if m is None: return 'NO_ALTERNATIVE'
    if m<=MARGIN_NARROW: return 'NARROW_MARGIN'
    if m<=MARGIN_LOW: return 'LOW_MARGIN'
    return 'MARGIN_NOT_NARROW'

def _run_arm(req,eligible,profiles,overrides):
    world,absent,excluded=_engine_world(req,eligible,overrides)
    if absent:
        return {'status':'BLOCKED_ENGINE_MAPPING','reason':'eligible_catalog_offer_missing_engine_mapping','missing_offer_ids':absent,'customers':[],'excluded_engine_offers':excluded}
    customers=[]
    for pid in req['selected_persona_ids']:
        ranking=_score_persona(pid,req,world,profiles)
        if not ranking:
            customers.append({'persona_id':pid,'status':'NO_FEASIBLE_ENGINE_CANDIDATE','candidates':[],'chosen':None})
            continue
        top=ranking[0]; runner=ranking[1] if len(ranking)>1 else None
        margin=round(top['score']-runner['score'],4) if runner else None
        customers.append({'persona_id':pid,'status':'COMPLETED','chosen':top,'runner_up':runner,'margin':margin,'margin_diagnostic':_margin_flag(margin),'candidates':ranking})
    return {'status':'COMPLETED' if any(c['status']=='COMPLETED' for c in customers) else 'NO_FEASIBLE_CANDIDATES','customers':customers,'excluded_engine_offers':excluded}

def _aggregates(before,after,eligible_rows):
    b={x['persona_id']:x.get('chosen') for x in before};a={x['persona_id']:x.get('chosen') for x in after}
    venues=sorted({x['venue_id'] for x in list(b.values())+list(a.values()) if x} | {x['venue_id'] for x in eligible_rows})
    output=[]
    for venue in venues:
        b_ids=[pid for pid,ch in b.items() if ch and ch['venue_id']==venue]
        a_ids=[pid for pid,ch in a.items() if ch and ch['venue_id']==venue]
        output.append({'venue_id':venue,'baseline_selected_count':len(b_ids),'scenario_selected_count':len(a_ids),'delta':len(a_ids)-len(b_ids),'inflow_persona_ids':sorted(set(a_ids)-set(b_ids)),'outflow_persona_ids':sorted(set(b_ids)-set(a_ids)),'same_venue_menu_change_persona_ids':sorted(pid for pid in set(b_ids)&set(a_ids) if b[pid]['offer_id']!=a[pid]['offer_id']),'excluded_offer_ids':[x['offer_id'] for x in eligible_rows if x['venue_id']==venue and x['eligibility_status']!='ELIGIBLE'],'interpretation':'conditional rule-engine result; not demand forecast'})
    return output

def run_request(request):
    catalog=_load_catalog(); profiles=_load_profiles()
    _validate_request(request,catalog,profiles)
    req=copy.deepcopy(request); req['selected_persona_ids']=list(req['selected_persona_ids'])
    eligibility,eligible=_eligibility(req,catalog)
    req_hash=_sha(req)
    result={'schema_version':'cd1024-15-output-v1','experiment':{'scenario_id':req['scenario_id'],'run_status':None,'scenario_input_sha256':req_hash,'catalog_version':catalog['catalog_version'],'engine_version':EXPECTED_ENGINE_VERSION,'request_engine_version':req['engine_version'],'profile_ids':req['selected_persona_ids'],'profile_input_sha256':_sha({pid:_sha(profiles[pid]) for pid in req['selected_persona_ids']}),'selected_condition':{k:req[k] for k in ('simulation_date','meal_period','start_time','duration_minutes','party_size','party_composition','stay_status','reservation_assumption','is_public_holiday','seat_type')},'reservation_interpretation':'reservation_assumption is an operator input; no live inventory or reservation API was queried','live_seat_inventory':'NOT_CHECKED','actual_or_scenario_overrides':{k:v for k,v in req['offer_overrides'].items()},'profile_visit_alignment':'NOT_ASSESSED; same requested synthetic condition applied to selected profiles','scenario_only_overrides':True},'eligibility':eligibility,'baseline':None,'scenario':None,'customers':[],'venue_aggregates':[],'data_gaps':[],'comparison_available':False}
    eligible_offer_rows=[x for x in eligibility if x['eligibility_status']=='ELIGIBLE']
    result['data_gaps']=[{'offer_id':x['offer_id'],'reasons':x['reasons']} for x in eligibility if x['eligibility_status']=='INSUFFICIENT_DATA']
    if not eligible:
        result['experiment']['run_status']='NO_ELIGIBLE_OFFERS'
        result['baseline']={'status':'NOT_RUN_NO_ELIGIBLE_OFFERS','customers':[]}
        result['scenario']={'status':'NOT_RUN_NO_ELIGIBLE_OFFERS','customers':[]}
        return result
    baseline=_run_arm(req,eligible,profiles,{})
    scenario=_run_arm(req,eligible,profiles,req['offer_overrides'])
    result['baseline']=baseline;result['scenario']=scenario
    if baseline['status']!='COMPLETED' or scenario['status']!='COMPLETED':
        result['experiment']['run_status']='BLOCKED_ENGINE_RUN'
        return result
    bm={x['persona_id']:x for x in baseline['customers']};sm={x['persona_id']:x for x in scenario['customers']}
    compared=[]
    for pid in req['selected_persona_ids']:
        b,s=bm[pid],sm[pid]
        bc,sc=b.get('chosen'),s.get('chosen')
        locked=None
        if sc:
            lock_body={'scenario_input_sha256':req_hash,'persona_id':pid,'offer_id':sc['offer_id'],'venue_id':sc['venue_id'],'start_time':req['start_time'],'duration_minutes':req['duration_minutes'],'party_size':req['party_size']}
            locked={'decision_id':_sha(lock_body),'decision_type':'dinner_consumption','offer_id':sc['offer_id'],'venue_id':sc['venue_id'],'start_time':req['start_time'],'duration_minutes':req['duration_minutes'],'party_size':req['party_size'],'participation':True,'mutable_by_planner':False,'decision_source':'frozen_quantitative_engine'}
        compared.append({'persona_id':pid,'status':'COMPLETED' if bc and sc else 'NO_FEASIBLE_ENGINE_CANDIDATE','baseline_choice':bc,'scenario_choice':sc,'locked_decision':locked,'choice_changed':bool(bc and sc and bc['offer_id']!=sc['offer_id']),'score_changed_without_choice_change':bool(bc and sc and bc['offer_id']==sc['offer_id'] and ({x['offer_id']:x['score'] for x in b['candidates']}!={x['offer_id']:x['score'] for x in s['candidates']} or b.get('margin')!=s.get('margin'))),'baseline_margin':b.get('margin'),'scenario_margin':s.get('margin'),'scenario_margin_diagnostic':s.get('margin_diagnostic'),'candidate_scores_before':[{'offer_id':x['offer_id'],'venue_id':x['venue_id'],'score':x['score']} for x in b['candidates']],'candidate_scores_after':[{'offer_id':x['offer_id'],'venue_id':x['venue_id'],'score':x['score']} for x in s['candidates']],'personal_contribution':sc['personal_contribution'] if sc else None,'common_contribution':sc['common_contribution'] if sc else None,'assumption_contribution':sc['assumption_contribution'] if sc else None,'fact_ids':sc['fact_ids'] if sc else []})
    result['customers']=compared
    result['venue_aggregates']=_aggregates(baseline['customers'],scenario['customers'],eligible_offer_rows)
    result['comparison_available']=True
    result['experiment']['run_status']='COMPLETED'
    result['experiment']['selected_offer_ids']=eligible
    result['experiment']['all_selected_reservation_is_assumption']=bool(req['reservation_assumption'])
    return result

def default_request():
    return {'scenario_id':'CD14_BASELINE','simulation_date':'2026-10-27','meal_period':'dinner','start_time':'18:30','duration_minutes':90,'party_size':2,'stay_status':'staying','reservation_assumption':True,'party_composition':{'adults':2,'children':0},'is_public_holiday':False,'seat_type':'hall','selected_persona_ids':['A02','A04','A05','A07','A10','blog41','blog42','blog43','A01','A03','A08'],'offer_overrides':{},'catalog_version':EXPECTED_CATALOG_VERSION,'engine_version':EXPECTED_ENGINE_VERSION,'allow_scenario_offers':False}
