import copy
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import strategy_agent as S


def fixture():
    bundle=dict(customer_id='X',facts=[dict(id='F1',summary='음식을 비교한 경험',features=['food_exploration'],posts=['P1'])],
                facet_evidence={'food_specific':dict(evidence=[dict(fact_id='F1',grade='rep')])})
    context=S.build_context('X',bundle,None,dict(target_venue='THE_BUFFET',basis='PROFILE_HYPOTHESIS'))
    idea=dict(title='메뉴 비교',kind='food',problem='미선택 원인 미확인',supporting_fact_ids=['F1'],counterevidence_fact_ids=[],
        decision_refs=[],controllable_lever='메뉴 안내',proposed_intervention='등록 메뉴 비교 안내',expected_behavior_hypothesis='방문 고려',
        referenced_sku_ids=[context['target_products'][0]['sku_id']],experiment_contract_id='',required_conditions=['메뉴 확인'],uncertainties=['효과 미검증'])
    answer=dict(current_choice_analysis='실제 방문 연결 없음',nonselection_analysis='미확인',nonselection_basis='NO_EVIDENCE',comparison_refs=[],
                strategies=[idea],operator_recommendation='메뉴 확인 후 검토',hold_reasons=[])
    return bundle,context,answer


def test_hypothesis_never_becomes_effect_or_executable_contract():
    _,c,a=fixture();out=S.validate_answer(a,c);idea=out['strategies'][0]
    assert not idea['experiment_supported']
    assert idea['measured_effect'] is None
    assert idea['human_review']=='PENDING'
    assert 'measured_effect' not in a['strategies'][0]


@pytest.mark.parametrize('change,reason',[
    ({'supporting_fact_ids':['OTHER_PERSON']},'UNKNOWN_OR_EXCLUDED_FACT'),
    ({'referenced_sku_ids':['INVENTED']},'UNKNOWN_OR_OTHER_VENUE_SKU'),
    ({'experiment_contract_id':'MODEL_GRANTS_ITSELF_ACCESS'},'EXPERIMENT_CONTRACT_NOT_VERIFIED'),
    ({'supporting_fact_ids':[]},'PERSONAL_STRATEGY_REQUIRES_SUPPORT')])
def test_invalid_model_references_cannot_enter_strategy(change,reason):
    _,c,a=fixture();a['strategies'][0].update(change)
    with pytest.raises(ValueError,match=reason):S.validate_answer(a,c)


def test_excluded_and_weak_evidence_remain_excluded():
    bundle,_,_=fixture()
    for grade in ('exclude','weak'):
        bundle['facet_evidence']['food_specific']['evidence'][0]['grade']=grade
        assert S.safe_facts(bundle)==[]


def test_cross_facet_rep_does_not_override_relevant_exclusion():
    _,c,a=fixture()
    c['evidence'][0]['grades']=[dict(facet='benefit',grade='rep'),dict(facet='food_specific',grade='exclude')]
    with pytest.raises(ValueError,match='FACT_GRADE_NOT_VALID'):S.validate_answer(a,c)


def test_private_urls_other_customers_and_corpus_are_not_projected():
    b,_,_=fixture();b['facts'][0].update(quote='PRIVATE_ORIGINAL',source_links=['PRIVATE_URL'],summary='요약 https://example.com/private')
    flow=dict(visit_id='run',plans={'X':dict(scenes=[dict(consume=True,visit_date='2026-09-10',t0=1080,loc='PIZZA_HILL')])},visit=dict(hotel_price_snapshot='ENTIRE_CATALOG',
        resolved_conditions={'X':dict(party_size=2),'OTHER':dict(private='OTHER_PERSON')},
        scenario_snapshot=dict(assumptions=dict(booked_sessions={'OTHER':'OTHER_BOOKING','X':{'start':'16:40'}}))))
    c=S.build_context('X',b,flow,dict(target_venue='THE_BUFFET',basis='ACTUAL_RUN',source_action=dict(date='2026-09-10',start=1080,venue='PIZZA_HILL')))
    wire=str(c)
    for forbidden in ('PRIVATE_ORIGINAL','PRIVATE_URL','https://','OTHER_PERSON','OTHER_BOOKING','ENTIRE_CATALOG'):
        assert forbidden not in wire


def test_no_valid_evidence_does_not_call_provider():
    b,c,a=fixture();b['facts']=[]
    with patch.object(S.P,'request',side_effect=AssertionError('must not call')):
        assert S.recommend('X',b,None,dict(target_venue='THE_BUFFET',basis='PROFILE_HYPOTHESIS'))['status']=='EVIDENCE_HOLD'


def test_assumption_cannot_be_reported_as_recorded_comparison():
    _,c,a=fixture();a.update(nonselection_basis='RECORDED_COMPARISON')
    with pytest.raises(ValueError,match='ACTUAL_EVIDENCE'):S.validate_answer(a,c)


def test_actual_analysis_requires_one_selected_consumption():
    b,_,_=fixture()
    flow=dict(visit_id='run',plans={'X':dict(scenes=[])})
    with pytest.raises(ValueError,match='SELECTED_ACTUAL_CONSUMPTION_REQUIRED'):
        S.build_context('X',b,flow,dict(target_venue='THE_BUFFET',basis='ACTUAL_RUN'))
    with pytest.raises(ValueError,match='SOURCE_CONSUMPTION_NOT_UNIQUE'):
        S.build_context('X',b,flow,dict(target_venue='THE_BUFFET',basis='ACTUAL_RUN',source_action=dict(date='2026-09-10',start=1080,venue='PIZZA_HILL')))


def test_dinner_strategy_does_not_receive_old_or_breakfast_tariffs_as_eligible():
    b,_,_=fixture()
    flow=dict(visit_id='run',plans={'X':dict(scenes=[dict(consume=True,meal='dinner',visit_date='2026-09-10',t0=1080,loc='PIZZA_HILL')])})
    c=S.build_context('X',b,flow,dict(target_venue='THE_BUFFET',basis='ACTUAL_RUN',source_action=dict(date='2026-09-10',start=1080,venue='PIZZA_HILL')))
    assert c['target_products']
    assert all(p['label'].startswith('석식') for p in c['target_products'])
    assert all(not p['valid_until'] or p['valid_until']>='2026-09-10' for p in c['target_products'])
    assert any('DATE_OR_SALE_DAY' in p['reasons'] for p in c['target_product_exclusions'])
    assert all(p['eligibility_status']=='DATE_PERIOD_SCREENED_OTHER_CONDITIONS_UNCONFIRMED' for p in c['target_products'])
    assert c['verified_experiment_contracts']==[]


def test_experiment_cannot_approve_different_lever_or_unspecified_product():
    _,context,answer=fixture();idea=answer['strategies'][0]
    context['verified_experiment_contracts']=[dict(id='price',lever='catalog_discount_percent',sku_ids=idea['referenced_sku_ids'][:])]
    idea['experiment_contract_id']='price'
    with pytest.raises(ValueError,match='LEVER_MISMATCH'):S.validate_answer(answer,context)
    idea['controllable_lever']='catalog_discount_percent'
    assert S.validate_answer(answer,context)['strategies'][0]['experiment_supported']
    idea['referenced_sku_ids']=[]
    with pytest.raises(ValueError,match='EXPLICIT_SKU'):S.validate_answer(answer,context)
