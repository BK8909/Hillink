"""Whitelist-only anonymous Santa audit export. No engine execution or source prose.

Usage: python3 research/santa_audit/export.py --input DIR --output DIR
Original IDs are written only to INPUT/customer_mapping.private.json.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

VERSION = 'anonymous-santa-audit-v2-pr129'

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def pick(value, keys):
    return {k:value[k] for k in keys.split() if k in (value or {})}

def factrefs(ids):
    return ['F-'+digest(str(x)) for x in ids or []]

def contract(c):
    if not isinstance(c,dict): return None
    out=pick(c,'label sku_id pricing_parent_sku_id reference_sku_id venue_id role category unit_price_krw total_krw list_amount_krw billing_quantity billing_unit price_tier price_status included included_benefit original_list_unit_price_krw discount_krw price_unknown selection_id parent_order_id component_index catalog_sha256 source_sha256 order_origin party_cohort age_band current_sale_confirmed reservation_confirmed transaction_confirmed quantity_observed')
    trace=c.get('price_trace') or {}
    if trace:
        out['price_trace']=pick(trace,'catalog_unit_price_krw scenario_unit_price_before_discount_krw discount_percent effective_unit_price_krw rounding')
        out['original_list_unit_price_krw']=trace.get('scenario_unit_price_before_discount_krw',c.get('original_list_unit_price_krw'))
    out.update(pick(c,'facility_id sauna_policy price_key guest_building source_checked_at service_date date_specific_tariff_confirmed historical_tariff_confirmed sauna_eligible_people party_total_people participant_scope'))
    if 'components' in c:out['components']=[contract(p) for p in c['components']]
    return out

def service(c):
    out = pick(c,'venue_id service_window candidate_available_at planning_viability reservation_state source_sha256 price_status catalog_sha256 scenario_weather weather_effect scenario_id')
    if isinstance(out.get('service_window'),dict):out['service_window']=pick(out['service_window'],'start end')
    if isinstance(out.get('scenario_weather'),dict):out['scenario_weather']=pick(out['scenario_weather'],'condition temperature rain_mm wind_speed humidity')
    return out

def candidate(c):
    out=pick(c,'candidate_label product_label candidate_id product_id venue_id map_loc base_score score context_adjustment final_score final_with_lookahead world_allowed feasible duration_min travel_min meal_fraction')
    # Price objects may contain provenance prose: numeric and boolean values only.
    if isinstance(c.get('price'),dict):out['price']={k:v for k,v in c['price'].items() if k in ('krw','total_krw','unit_price_krw','per_person_krw','in_package','included') and (v is None or isinstance(v,(bool,int,float)))}
    out['terms']=[dict(term_index=i,factor=t.get('factor'),**{k:v for k,v in t.items() if k in ('value','weight','coefficient','raw_value') and isinstance(v,(int,float))},fact_refs=factrefs(t.get('fact_ids'))) for i,t in enumerate(c.get('terms') or [])]
    out['candidate_fact_refs']=factrefs(c.get('candidate_fact_ids'))
    for key in ('product_quote','sku_contract'):
        if c.get(key):out[key]=contract(c[key])
    if c.get('service_contract'):out['service_contract']=service(c['service_contract'])
    return out

def day_flows(flow):
    days=flow.get('visit_days') or []
    return [(d.get('date'),d.get('day_index'),d.get('flow') or {}) for d in days] if days else [(flow.get('visit',{}).get('start_date'),1,flow)]

def rows_of(flow):
    return [dict(r,customer_id=pid) for pid,receipt in (flow.get('ledger',{}).get('receipts') or {}).items() for r in receipt.get('rows',[])]

def sku(row):return row.get('product_sku_id') or row.get('sku_id') or row.get('product_id')

def request_config(request):
    out=pick(request,'duration seed start_date event_mode behavior_engine simulation_mode catalog_policy breakfast_policy hybrid_policy package_id')
    out['personas']=list(request.get('personas') or [])
    out['environment']=pick(request.get('environment') or {},'weather temperature rain_mm wind_speed humidity')
    out['catalog_options']={}
    for k in ('room_products','discount_percent','price_overrides'):
        if k in (request.get('catalog_options') or {}):out['catalog_options'][k]=request['catalog_options'][k]
    out['visit_conditions']={}
    for pid,v in (request.get('visit_conditions') or {}).items():
        z=pick(v,'building party_size club breakfast_plan')
        if v.get('party_composition') is not None:
            p=v['party_composition'];z['party_composition']={'adult_count':p.get('adult_count'),'children':[pick(c,'age_months school_stage') for c in p.get('children',[])]}
        out['visit_conditions'][pid]=z
    s=request.get('scenario') or {};out['scenario']=pick(s,'event_card_id arrival_time')
    out['scenario']['assumptions']=pick(s.get('assumptions') or {},'sessions duration_min historical_model_prices_acknowledged booked_sessions')
    out['scenario']['entitlements']={pid:pick(v,'selected_package included_people') for pid,v in (s.get('entitlements') or {}).items()}
    return out

def clean_identifiers(value,mapping):
    """Replace internal customer IDs even inside decision/selection identifiers."""
    if isinstance(value,dict):return {clean_identifiers(k,mapping):clean_identifiers(v,mapping) for k,v in value.items()}
    if isinstance(value,list):return [clean_identifiers(v,mapping) for v in value]
    if isinstance(value,str):
        for old,new in sorted(mapping.items(),key=lambda x:-len(x[0])):value=value.replace(old,new)
    return value

def scene_link(row,scene_index):
    if row.get('action_id')=='room_night':return {'status':'NOT_APPLICABLE_ROOM_CONTRACT'}
    key=(row.get('customer_id'),row.get('visit_date'),row.get('scene_index'))
    s=scene_index.get(key)
    if not s:return {'status':'HOLD','reason':'DAILY_SCENE_INDEX_UNRESOLVED'}
    # Index is engine supplied, but verify it really points at the same action.
    checks=[row.get(k)==s.get(k) for k in ('t0','t1','loc','act') if row.get(k) is not None]
    if not checks or not all(checks):return {'status':'HOLD','reason':'SCENE_FIELDS_NOT_CONFIRMED'}
    return {'status':'EXACT_ENGINE_SCENE_INDEX','date':row.get('visit_date'),'scene_index':row['scene_index']}

def check(status,**details):return dict(status=status,**details)

def reconcile(flow,raw_rows,scene_index):
    ledger=flow.get('ledger') or {};total=sum(r.get('paid_krw') or 0 for r in raw_rows);levels={}
    for level in ('L4','L3','L2','L1'):
        rr=(ledger.get('levels') or {}).get(level)
        levels[level]=check('HOLD',reason='LEVEL_MISSING') if rr is None else check('PASS' if sum(r.get('paid_krw') or 0 for r in rr)==total else 'FAIL',paid_krw=sum(r.get('paid_krw') or 0 for r in rr))
    ids=[r.get('row_id') for r in raw_rows];dups=[i for i,n in Counter(ids).items() if i and n>1]
    free=[r.get('row_id') for r in raw_rows if (r.get('purchase_status') in ('PACKAGE_INCLUDED','FREE_USE') or r.get('status') in ('포함','무료') or r.get('included_benefit')) and (r.get('paid_krw') or 0)!=0]
    missing_price=[r.get('row_id') for r in raw_rows if r.get('unit_price_krw') is None or r.get('quantity') is None or r.get('paid_krw') is None]
    arithmetic=[r.get('row_id') for r in raw_rows if r.get('unit_price_krw') is not None and r.get('quantity') is not None and r.get('paid_krw') is not None and r['unit_price_krw']*r['quantity']!=r['paid_krw']]
    links=[{'row_id':r.get('row_id'),**scene_link(r,scene_index)} for r in raw_rows]
    holds=[r['row_id'] for r in links if r['status']=='HOLD']
    legacy_free=[r.get('row_id') for r in raw_rows if not r.get('sku_contract') and r.get('action_id') in ('FOREST_WALK','library') and r.get('paid_krw')==0 and r.get('purchase_status') in ('PACKAGE_INCLUDED','FREE_USE')]
    missing_contract=[r.get('row_id') for r in raw_rows if not (r.get('sku_contract') or {}).get('sku_id') and r.get('action_id')!='room_night' and r.get('row_id') not in legacy_free]
    consumed=[];nonpurchase=[]
    linked={(r.get('customer_id'),r.get('visit_date'),r.get('scene_index')) for r in raw_rows if scene_link(r,scene_index)['status']=='EXACT_ENGINE_SCENE_INDEX'}
    for key,scene in scene_index.items():
        quote=((scene.get('basis') or {}).get('charge') or {}).get('sku_contract') or scene.get('product_quote')
        charge=(scene.get('basis') or {}).get('charge') or {}
        if scene.get('act') in ('lunch_skip','SKIP_BREAKFAST') and charge.get('status')=='구매 없음' and not quote:
            nonpurchase.append(dict(customer_id=key[0],date=key[1],scene_index=key[2],action_id=scene.get('act'),classification='EXPLICIT_SKIP_NO_PURCHASE; CONSUME_FLAG_IS_NOT_A_CONFIRMED_ORDER'))
            continue
        if (scene.get('consume') or quote) and key not in linked:
            consumed.append(dict(customer_id=key[0],date=key[1],scene_index=key[2],reason='CONSUMED_SCENE_OR_PRODUCT_QUOTE_WITHOUT_CONFIRMED_L5'))
    mismatch_contract=[];scene_quote_mismatch=[]
    for r in raw_rows:
        c=r.get('sku_contract') or {};known={c.get('sku_id')}|{x.get('sku_id') for x in c.get('components',[])}
        if c and sku(r) not in known:mismatch_contract.append(r.get('row_id'))
        scene=scene_index.get((r.get('customer_id'),r.get('visit_date'),r.get('scene_index'))) or {}
        quote=((scene.get('basis') or {}).get('charge') or {}).get('sku_contract') or scene.get('product_quote') or {}
        quote_ids={quote.get('sku_id')}|{x.get('sku_id') for x in quote.get('components',[])}
        if quote and sku(r) not in quote_ids:scene_quote_mismatch.append(r.get('row_id'))
    billed=defaultdict(list)
    for r in raw_rows:
        if r.get('parent_order_id') and r.get('component_index') is not None:
            billed[(r.get('customer_id'),r.get('visit_date'),r['parent_order_id'],r['component_index'])].append(r.get('row_id'))
    billed_twice=[{'key':list(k),'row_ids':ids} for k,ids in billed.items() if len(ids)>1]
    result={'order_components_not_billed_twice':check('FAIL' if billed_twice else 'PASS',violations=billed_twice,compared_groups=len(billed),unkeyed_rows=len(raw_rows)-sum(len(x) for x in billed.values()),scope='EXPLICIT_CUSTOMER_DATE_PARENT_ORDER_COMPONENT_KEYS_ONLY'), 'consumed_scene_to_L5':check('HOLD' if consumed else 'PASS' if raw_rows else 'HOLD',unconfirmed=consumed),'nonpurchase_consumption_flags':nonpurchase,'legacy_free_service_rows_without_saleable_sku':legacy_free,'price_unconfirmed_rows':[pick(r,'row_id product_id product_sku_id price_status purchase_status quantity unit_price_krw paid_krw') for r in raw_rows if r.get('row_id') in missing_price],'row_count':len(raw_rows),'paid_L5_krw':total,'levels':levels,
        'L5_equals_total':check('HOLD' if not raw_rows or 'paid_krw' not in ledger.get('totals',{}) else 'PASS' if total==ledger['totals']['paid_krw'] else 'FAIL'),
        'duplicate_rows':check('FAIL' if dups else 'HOLD' if None in ids or not ids else 'PASS',duplicate_row_ids=dups),
        'included_free_paid_zero':check('FAIL' if free else 'PASS' if raw_rows else 'HOLD',violations=free),
        'quantity_times_unit_equals_paid':check('HOLD' if arithmetic or missing_price else 'PASS' if raw_rows else 'HOLD',unconfirmed=missing_price+arithmetic,scope='ROW_NET_UNIT_PRICE; INCLUDED_OR_DISCOUNT_SEMANTICS_REQUIRE_REVIEW_ON_MISMATCH'),
        'scene_links':links,'scene_link_check':check('HOLD' if holds else 'PASS' if raw_rows else 'HOLD',unconfirmed=holds),
        'order_product_contract':check('FAIL' if mismatch_contract else 'HOLD' if missing_contract or scene_quote_mismatch or not raw_rows else 'PASS',unconfirmed=missing_contract,sku_mismatches=mismatch_contract,scene_quote_sku_unconfirmed=scene_quote_mismatch)}
    result['overall']='FAIL' if any(v.get('status')=='FAIL' for v in list(levels.values())+[x for x in result.values() if isinstance(x,dict)]) else 'HOLD' if any(v.get('status')=='HOLD' for v in list(levels.values())+[x for x in result.values() if isinstance(x,dict)]) else 'PASS'
    return result

def export_run(flow,meta,mapping):
    scenes=[];decisions=[];activities=[];choices=[];scene_index={};activity_keys=set()
    for date,day_index,day in day_flows(flow):
        for pid,plan in (day.get('plans') or {}).items():
            for i,s in enumerate(plan.get('scenes') or []):
                scene_index[(pid,date,i)]=s
                scenes.append(dict(customer_id=pid,date=date,visit_day=day_index,scene_index=i,**pick(s,'t0 t1 act loc meal turn consume'),consumed_product_contract=contract(((s.get('basis') or {}).get('charge') or {}).get('sku_contract') or s.get('product_quote'))))
            m4=plan.get('m4') or {}
            for a in m4.get('activity_history') or []:
                actual_date=a.get('date')
                # The engine preserves cumulative history. Export each occurrence on its own day.
                if actual_date and actual_date!=date:continue
                event=pick(a,'event_id start end start_minute end_absolute action_id venue_id location_id kind meal_slot fraction intake_status')
                occurrence_date=actual_date or date
                key=(pid,occurrence_date,a.get('event_id'),a.get('end_absolute'))
                if key in activity_keys:continue
                activity_keys.add(key)
                activities.append(dict(customer_id=pid,date=occurrence_date,visit_day=day_index,occurrence_key=digest([mapping.get(pid,pid),*key[1:]]),event_id_semantics='ENGINE_OCCURRENCE_HASH_CUSTOMER_DATE_START_ACTION_LOCATION',date_status='ENGINE_EVENT_DATE' if actual_date else 'LEGACY_SNAPSHOT_DATE_UNCONFIRMED',**event))
            for index,d in enumerate(m4.get('decisions') or []):
                p=d.get('packet') or {};selected=d.get('selected_action');sid=selected.get('candidate_id') if isinstance(selected,dict) else selected
                decisions.append(dict(customer_id=pid,date=date,visit_day=day_index,decision_index=index,selected_candidate_id=sid,actual_next_event_id=d.get('actual_next_event_id'),execution_status=d.get('execution_status'),packet_sha256=p.get('packet_sha256'),kind=p.get('kind'),context=pick(p.get('context_factors') or {},'date time'),candidates=[candidate(c) for c in p.get('candidates',[])]))
    for run in flow.get('runs') or []:
        customers=run.get('customers') or []
        if isinstance(customers,dict):customers=[dict(v,persona_id=k) for k,v in customers.items()]
        for c in customers:
            choices.append(dict(customer_id=c.get('persona_id'),**pick(run,'turn time visit_day visit_date day_phase'),choice=candidate(c.get('choice') or {}),not_chosen=[candidate(x) for x in c.get('not_chosen') or []]))
    raw_rows=rows_of(flow);rows=[];orders=[]
    for r in raw_rows:
        z=pick(r,'product row_id customer_id department venue venue_id product_id action_id time status quantity unit_price_krw billing_quantity billing_unit participant_count paid_krw assumption_addition_krw amount_status purchase_status tax_status scene_index loc act turn decision_id package_entitlement_id t0 t1 meal parent_order_id component_index sku_id visit_id visit_day visit_date day_phase event_available selection_id product_sku_id price_status current_sale_confirmed reservation_confirmed price_tier catalog_sha256 discount_krw included_benefit quantity_observed')
        if not z.get('sku_id') and (r.get('sku_contract') or {}).get('sku_id'):
            z.update(sku_id=r['sku_contract']['sku_id'],sku_identity_source='EXISTING_CONTRACT_NO_NEW_SKU')
        z['product_classification']='UNPRICED_PRODUCT' if (r.get('sku_contract') or {}).get('price_unknown') else 'INCLUDED_BENEFIT' if r.get('purchase_status')=='PACKAGE_INCLUDED' else 'NONSALE_FREE_SERVICE' if r.get('paid_krw')==0 and r.get('purchase_status')=='FREE_USE' else 'PRICED_VIRTUAL_PRODUCT' if r.get('paid_krw',0)>0 else 'UNCONFIRMED_OR_NONPURCHASE'
        if not z.get('product_sku_id') and (r.get('sku_contract') or {}).get('sku_id'):
            z.update(product_sku_id=r['sku_contract']['sku_id'],sku_identity_source='EXISTING_CONTRACT_NO_NEW_SKU')
        z['fact_refs']=factrefs(r.get('fact_ids'));z['sku_contract']=contract(r.get('sku_contract'));z['scene_link']=scene_link(r,scene_index);rows.append(z)
        orders.append(dict(customer_id=r['customer_id'],row_id=r.get('row_id'),date=r.get('visit_date'),parent_order_id=r.get('parent_order_id'),component_index=r.get('component_index'),selection_id=r.get('selection_id'),contract=contract(r.get('sku_contract')),link_status='EXACT_LEDGER_CONTRACT' if r.get('sku_contract') else 'LEGACY_FREE_SERVICE_NO_SALEABLE_SKU' if r.get('action_id') in ('FOREST_WALK','library') and r.get('paid_krw')==0 and r.get('purchase_status') in ('PACKAGE_INCLUDED','FREE_USE') else 'HOLD'))
    customers=[]
    for pid,receipt in (flow.get('ledger',{}).get('receipts') or {}).items():
        resolved=(flow.get('visit',{}).get('resolved_conditions') or {}).get(pid) or {}
        visit=(flow.get('visits') or {}).get(pid) or {}
        condition={k:resolved.get(k,visit.get(k,'UNKNOWN')) for k in ('building','party_size','stay','nights','breakfast_plan','breakfast_plan_source','selected_room_sku_id','party_composition')}
        customers.append(dict(customer_id=pid,**condition))
    aggregates={level:[pick(r,'key quantity paid_krw assumption_addition_krw with_assumptions_krw unknown_count tax_unknown_count') for r in rr] for level,rr in (flow.get('ledger',{}).get('levels') or {}).items() if level in ('L4','L3','L2','L1')}
    config=dict(version=VERSION,source_commit=meta.get('source_commit'),source_fingerprint={'sha256':digest(meta['source_fingerprint']),'entry_count':len(meta['source_fingerprint'])} if meta.get('source_fingerprint') else None,registry_sha=meta.get('registry_sha'),raw_sha256=meta.get('raw_sha256'),run_id=meta.get('run_id') or flow.get('ledger',{}).get('run_id'),paid_llm_calls=meta.get('paid_llm_calls'),request=request_config(meta.get('request') or {}),resolved_policy=pick(flow.get('visit') or {},'breakfast_policy catalog_policy hotel_catalog_sha256 behavior_engine simulation_mode start_date duration room_price_policy'),price_versions=pick(flow.get('ledger',{}).get('context') or {},'price_version room_valuation_version room_price_source_sha256 engine_version'),resolved_weather=pick((flow.get('visit',{}).get('scenario_snapshot') or {}).get('weather') or {},'condition temperature rain_mm wind_speed humidity'))
    return clean_identifiers({'scenario_config':config,'customer_flow':{'customers':customers,'scenes':scenes,'activity_history':activities},'decisions':{'packets':decisions,'run_choices':choices},'order_lines':orders,'ledger_L5':rows,'aggregates':aggregates,'reconciliation':reconcile(flow,raw_rows,scene_index)},mapping)

def compare_runs(a,b,target_sku):
    ar=a['ledger_L5'];br=b['ledger_L5'];key=lambda r:(r.get('customer_id'),r.get('visit_date'),sku(r),r.get('billing_unit'))
    aa=defaultdict(set);bb=defaultdict(set)
    for r in ar:
        if sku(r)!=target_sku and (r.get('sku_contract') or {}).get('pricing_parent_sku_id')!=target_sku:aa[key(r)].add(r.get('unit_price_krw'))
    for r in br:
        if sku(r)!=target_sku and (r.get('sku_contract') or {}).get('pricing_parent_sku_id')!=target_sku:bb[key(r)].add(r.get('unit_price_krw'))
    common=aa.keys()&bb.keys();bad=[list(k) for k in common if aa[k]!=bb[k]];unmatched=len(aa.keys()^bb.keys())
    def choices(x):
        n=defaultdict(int);out={}
        for r in x['decisions']['run_choices']:
            base=(r['customer_id'],r.get('visit_date'),r.get('turn'));n[base]+=1
            out[base+(n[base],)]=pick(r['choice'],'product_id venue_id')
        return out
    ac=choices(a);bc=choices(b);moves=[{'customer_id':k[0],'date':k[1],'turn':k[2],'occurrence':k[3],'A':ac[k],'B':bc[k],'alignment':'CUSTOMER_DATE_TURN_OCCURRENCE_NOT_CAUSAL_PROOF'} for k in ac.keys()&bc.keys() if ac[k]!=bc[k]]
    amounts=[]
    for pid in sorted({r['customer_id'] for r in ar+br}):
        before=sum(r.get('paid_krw') or 0 for r in ar if r['customer_id']==pid);after=sum(r.get('paid_krw') or 0 for r in br if r['customer_id']==pid)
        if before!=after:amounts.append(dict(customer_id=pid,A_paid_krw=before,B_paid_krw=after,delta_krw=after-before))
    ra=a['scenario_config']['request'];rb=b['scenario_config']['request'];rbc=json.loads(json.dumps(rb));discounts=rbc.get('catalog_options',{}).get('discount_percent',{});base_discounts=ra.get('catalog_options',{}).get('discount_percent',{})
    if target_sku in base_discounts:discounts[target_sku]=base_discounts[target_sku]
    else:discounts.pop(target_sku,None)
    if not discounts:rbc.get('catalog_options',{}).pop('discount_percent',None)
    same=ra==rbc
    return {'target_sku':target_sku,'same_conditions_except_target_discount':check('PASS' if same else 'FAIL'),
        'source_fingerprint_equal':check('PASS' if a['scenario_config']['source_fingerprint'] and a['scenario_config']['source_fingerprint']==b['scenario_config']['source_fingerprint'] else 'HOLD'),
        'resolved_policy_equal':check('PASS' if a['scenario_config']['resolved_policy']==b['scenario_config']['resolved_policy'] else 'FAIL'),
        'source_commit_equal':check('PASS' if a['scenario_config']['source_commit'] and a['scenario_config']['source_commit']==b['scenario_config']['source_commit'] else 'HOLD'),
        'non_target_unit_price':check('FAIL' if bad else 'HOLD' if not common else 'PASS',violations=bad,compared_groups=len(common),unmatched_groups=unmatched,scope='COMMON_CUSTOMER_DATE_SKU_UNIT_ONLY; UNMATCHED_ARE_NOT_ASSERTED_UNCHANGED'),
        'choice_changes':moves,'choice_changed_customers':sorted({m['customer_id'] for m in moves}),'unmatched_choices':len(ac.keys()^bc.keys()),'amount_changes':amounts,'hotel_paid_delta_krw':sum(r.get('paid_krw') or 0 for r in br)-sum(r.get('paid_krw') or 0 for r in ar)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    metas={name:json.loads((args.input/(name+'.meta.private.json')).read_text()) for name in ('A','S1','S2')}
    ids=sorted({pid for m in metas.values() for pid in (m.get('request') or {}).get('personas',[])})
    if not ids:raise ValueError('META_PERSONAS_REQUIRED_FOR_ANONYMOUS_MAPPING')
    mapping={pid:f'C{i:03}' for i,pid in enumerate(ids,1)}
    (args.input/'customer_mapping.private.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
    results={}
    for name in ('A','S1','S2'):
        raw=args.input/(name+'.flow.private.json.gz');hasher=hashlib.sha256()
        with raw.open('rb') as fp:
            for block in iter(lambda:fp.read(1024*1024),b''):hasher.update(block)
        expected=metas[name].get('raw_sha256')
        if expected and hasher.hexdigest()!=expected:raise ValueError(name+': RAW_SHA256_MISMATCH')
        with gzip.open(raw,'rt') as fp:flow=json.load(fp)
        if set(flow.get('ledger',{}).get('receipts',{}))-set(mapping):raise ValueError(name+': CUSTOMER_NOT_IN_METADATA')
        results[name]=export_run(flow,metas[name],mapping)
        del flow
    args.output.mkdir(parents=True,exist_ok=True)
    for kind in ('scenario_config','customer_flow','decisions','order_lines','ledger_L5','aggregates','reconciliation'):
        value={name:r[kind] for name,r in results.items()}
        if kind=='reconciliation':value['comparisons']={name:compare_runs(results['A'],results[name],target) for name,target in [('S1','HC-MENU-142'),('S2','HC-MENU-092')]}
        (args.output/(kind+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    (args.output/'README.md').write_text('# 산타 공식 14:10 · 조식 V2 검수 전달팩\n\n고객은 C001부터 익명화했습니다. 원래 ID 매핑은 입력 비공개 폴더에만 보존합니다. 후기·프로필·계정·원문·why/basis·가격 출처 원문은 포함하지 않습니다. Fact는 해시 참조만 제공합니다.\n\nscenario_config: 재현 조건과 SHA. customer_flow: 장면/활동. decisions: 실제 후보 숫자와 선택. order_lines: L5 계약. ledger_L5: 전체 행의 허용 필드. aggregates: 실제 L4~L1 집계. reconciliation: 집계·중복·무료·단가·연결 검사 및 선택/금액 변화.\n\nEXACT는 엔진 장면 인덱스와 시간·행동 필드 확인 또는 동일 L5 계약에만 사용합니다. 발생순 결정 비교는 인과 증명이 아닙니다. 누락/미확인은 HOLD, 실패는 FAIL이며 전체 통과로 숨기지 않습니다. 가상 소비이며 실제 호텔 매출이나 고객 구매 예측이 아닙니다.\n')
    print(json.dumps({'customers':len(mapping),'runs':{n:r['reconciliation']['overall'] for n,r in results.items()},'output':str(args.output)},ensure_ascii=False))

if __name__=='__main__':main()
