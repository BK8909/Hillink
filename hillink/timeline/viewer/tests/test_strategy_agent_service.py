import copy
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger
import strategy_agent_service as S


def sample(start=980):
    request=dict(personas=['X'],seed=17,start_date='2026-09-10',duration='stay_1',scenario={'event':'fixed'})
    scene=dict(consume=True,meal='dinner',visit_date='2026-09-10',t0=start,t1=start+90,loc='PIZZA_HILL')
    flow=dict(visit_id='visit',plans={'X':{'scenes':[scene]}},ledger=dict(run_id='r'*64,checks={'receipts_equal_L4_L3_L2_L1':True}))
    goal=dict(basis='ACTUAL_RUN',target_venue='THE_BUFFET',source_action=dict(date=scene['visit_date'],start=start,venue='PIZZA_HILL'))
    return flow,request,goal


def test_price_experiment_cannot_bypass_closed_target_at_selected_meal():
    f,r,g=sample()
    contracts,holds=S.contracts(f,r,'X',g)
    assert contracts==[] and 'TIME_COMPATIBILITY_REVIEW_BEFORE_PRICE' in holds
    f,r,g=sample(1080)
    contracts,holds=S.contracts(f,r,'X',g)
    assert contracts and not holds
    assert all(c['source_run_id']=='visit' and c['sku_ids'] for c in contracts)


def test_source_snapshot_is_server_owned_and_never_mutated_by_client():
    f,r,_=sample();S.remember(f,r);f['plans'].clear();r['seed']=999
    got=S.source('r'*64)
    assert got['request']['seed']==17 and got['flow']['plans']['X']
    got['request']['seed']=999
    assert S.source('r'*64)['request']['seed']==17
    with pytest.raises(ValueError,match='EXPIRED'):S.source('not-issued')


def test_jobs_deduplicate_repeated_clicks_and_keep_provider_errors_private():
    jobs=S.Jobs();ready=threading.Event();release=threading.Event();calls=[]
    def work():
        calls.append(1);ready.set();release.wait(2);return {'ok':True}
    a=jobs.submit('same',['X'],work);assert ready.wait(2)
    b=jobs.submit('same',['X'],work);assert a['job_id']==b['job_id']
    release.set();jobs.worker.shutdown(wait=True)
    assert len(calls)==1 and jobs.get(a['job_id'])['status']=='DONE'
    jobs=S.Jobs()
    def fail():raise RuntimeError('SECRET_PROVIDER_BODY')
    j=jobs.submit('failure',['X'],fail);jobs.worker.shutdown(wait=True)
    assert 'SECRET' not in str(jobs.get(j['job_id']))
    assert jobs.get(j['job_id'])['status']=='ERROR'


def test_assumptions_do_not_acquire_actual_experiment_rights():
    f,r,g=sample(1080);g['basis']='OPERATOR_ASSUMPTION'
    assert S.contracts(f,r,'X',g)[0]==[]


def test_pair_changes_only_supported_price_and_keeps_event_customer_policy():
    f,r,g=sample(1080);r['hybrid_policy']='LLM_AUTONOMOUS_CUSTOMER_V3';S.remember(f,r)
    contracts,_=S.contracts(f,r,'X',g);c=contracts[0]
    idea=dict(id='i',experiment_supported=True,experiment_contract_id=c['id'])
    job=dict(status='DONE',result=dict(customers=[dict(customer_id='X',strategies=[idea],experiment_contracts=contracts)]))
    cfg=dict(analysis_job_id='j',customer='X',strategy_id='i',run_id='r'*64,percent=20)
    with patch.object(S.JOBS,'get',return_value=job):a,b,_=S.pair(cfg)
    assert a==r
    changed=copy.deepcopy(b);changed.pop('catalog_options')
    assert changed==a
    assert b['catalog_options']=={'discount_percent':{c['sku_ids'][0]:20}}
    idea['experiment_supported']=False
    with patch.object(S.JOBS,'get',return_value=job),pytest.raises(ValueError,match='UNSUPPORTED'):S.pair(cfg)


def test_group_membership_comes_from_actual_personal_strategies_not_fact_count():
    import strategy_agent as Agent
    results=[dict(customer_id=pid,strategies=[dict(id='i',customer_id=pid,controllable_lever='catalog_discount_percent',supporting_fact_ids=['F1','F1','F2'],experiment_supported=True)]) for pid in ['X','Y']]
    answer=dict(groups=[dict(title='same intervention',lever='catalog_discount_percent',strategy_refs=['X:i','Y:i','X:i'],common_reason='same recorded condition',operator_action='existing input',exclusions=[],uncertainties=[])],conclusion='untested')
    with patch.object(Agent.P,'request',return_value=(answer,{'execution':'SYNTHETIC_TEST'})):
        group=S.group_proposals(results,{})['groups'][0]
    assert group['customer_count']==2 and group['fact_ids']['X']==['F1','F2']
    assert not group['group_experiment_executed'] and group['measured_effect'] is None
    answer['groups'][0]['strategy_refs']=['X:i','INVENTED:i']
    with patch.object(Agent.P,'request',return_value=(answer,{})):
        assert S.group_proposals(results,{})['status']=='VALIDATION_HOLD'


def pair_fixture():
    a=dict(personas=['X'],seed=17,hybrid_policy='LLM_AUTONOMOUS_CUSTOMER_V6')
    b=dict(a,catalog_options={'discount_percent':{'SKU':20}})
    f=dict(plans={'X':{'autonomous_decisions':[dict(policy=a['hybrid_policy'],world_policy='WORLD',execution_state='EXECUTED',
        implementation_sha256='fixture-implementation',profile_evidence_sha256='fixture-profile',
        attempts=[dict(provider=dict(execution='LIVE_RESPONSES',model='model'))])]}},
        ledger=dict(checks={k:True for k in ('receipts_equal_L4_L3_L2_L1','day_totals_equal_visit_total','room_nights_equal_duration','date_rows_unique')}))
    return f,copy.deepcopy(f),a,b,dict(sku_ids=['SKU'])


def test_balanced_incomplete_visit_never_reports_an_ab_effect():
    left,right,a,b,c=pair_fixture()
    assert S.pair_readiness(left,right,a,b,c)['comparable']
    for state in ('EXECUTION_HOLD','RULE_FALLBACK'):
        right['plans']['X']['autonomous_decisions'][0]['execution_state']=state
        gate=S.pair_readiness(left,right,a,b,c)
        assert not gate['comparable'] and 'B:PARTIAL_OR_FALLBACK_VISIT' in gate['reasons']


def test_matching_missing_identities_do_not_make_a_comparable_pair():
    for field,reason in (('implementation_sha256','IMPLEMENTATION_IDENTITY_MISSING'),('profile_evidence_sha256','PROFILE_EVIDENCE_IDENTITY_MISSING')):
        left,right,a,b,c=pair_fixture()
        for side in (left,right):side['plans']['X']['autonomous_decisions'][0].pop(field)
        gate=S.pair_readiness(left,right,a,b,c)
        assert not gate['comparable'] and 'A:'+reason in gate['reasons'] and 'B:'+reason in gate['reasons']


def test_pair_rejects_hidden_inputs_model_or_policy_changes_and_mock():
    for mutation,reason in (
        (lambda r,b:b.update(seed=99),'NON_EXPERIMENT_INPUT_CHANGED'),
        (lambda r,b:r['plans']['X']['autonomous_decisions'][0].update(policy='OLD'),'POLICY_OR_MODEL_CHANGED'),
        (lambda r,b:r['plans']['X']['autonomous_decisions'][0]['attempts'][0]['provider'].update(execution='MOCK'),'B:UNVERIFIED_PROVIDER')):
        left,right,a,b,c=pair_fixture();mutation(right,b)
        assert reason in S.pair_readiness(left,right,a,b,c)['reasons']


def test_price_arithmetic_preserves_included_rights_and_is_not_behavior_change():
    H=hotel_ledger.H;sku='HC-MENU-119';price=H.BY[sku]['unit_price_krw']
    rows=[dict(product_sku_id=sku,billing_quantity=2,paid_krw=price*2,purchase_status='SIMULATED_CHARGE'),
          dict(product_sku_id=sku,billing_quantity=2,paid_krw=0,purchase_status='PACKAGE_INCLUDED')]
    flow=dict(ledger=dict(receipts={'X':dict(rows=rows)}));snapshot=copy.deepcopy(flow)
    out=S.fixed_choice_repricing(flow,{},dict(catalog_options={'discount_percent':{sku:20}}),dict(sku_ids=[sku]))
    assert len(out['rows'])==1 and out['delta_krw']==-price*2*.2
    assert out['customer_conversion'] is None and not out['behavior_reinferred'] and not out['creates_purchase']
    assert snapshot==flow
    rows[0]['paid_krw']-=1
    assert S.fixed_choice_repricing(flow,{},dict(catalog_options={'discount_percent':{sku:20}}),dict(sku_ids=[sku]))['delta_krw'] is None


def test_individual_button_cannot_silently_run_full_original_cohort():
    f,r,g=sample(1080);r['personas']=['X','Y'];S.remember(f,r)
    cs,_=S.contracts(f,r,'X',g);idea=dict(id='i',experiment_supported=True,experiment_contract_id=cs[0]['id'])
    job=dict(status='DONE',result=dict(customers=[dict(customer_id='X',strategies=[idea],experiment_contracts=cs)]))
    with patch.object(S.JOBS,'get',return_value=job),pytest.raises(ValueError,match='SINGLE_CUSTOMER_SOURCE'):
        S.pair(dict(analysis_job_id='j',customer='X',strategy_id='i',run_id='r'*64,percent=20))


def test_breakfast_right_is_not_dinner_attraction_and_repeat_dinner_counts_once():
    scene=dict(visit_date='2026-11-06',meal='breakfast',loc='THE_BUFFET')
    row=dict(visit_date=scene['visit_date'],meal='breakfast',venue_id='THE_BUFFET',paid_krw=0,quantity=2,sku_id='BF')
    before=dict(plans={'X':{'scenes':[scene]}},ledger={'receipts':{'X':{'rows':[row]}}})
    after=copy.deepcopy(before)
    contract=dict(source_scope=dict(customer_id='X',date='2026-11-05',meal='dinner'),target_venue='THE_BUFFET',sku_ids=['DINNER'])
    source=copy.deepcopy(before)
    first=S.target_meal_comparison(before,after,contract)
    assert first['before']['selected_teams']==first['after']['selected_teams']==0
    assert first['entering_customers']==[] and first['delta_krw']==0
    for amount in [100,50]:
        after['plans']['X']['scenes'].append(dict(visit_date='2026-11-05',meal='dinner',loc='THE_BUFFET'))
        after['ledger']['receipts']['X']['rows'].append(dict(visit_date='2026-11-05',meal='dinner',venue_id='THE_BUFFET',paid_krw=amount,quantity=1,sku_id='DINNER'))
    result=S.target_meal_comparison(before,after,contract)
    assert result['after']['selected_teams']==1 and result['entering_customers']==['X']
    assert result['after']['intervention_sku_quantity']==2 and result['delta_krw']==150
    assert before==source and result['causal_effect_verified'] is False
    assert S.target_meal_comparison(before,after,{})['status']=='SCOPE_UNRECORDED_HOLD'
