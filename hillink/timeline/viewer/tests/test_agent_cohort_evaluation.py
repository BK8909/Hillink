import copy
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import agent_cohort_evaluation as C


def pair():
    base=dict(request=dict(personas=['P'],duration='stay_1',seed=4),configuration=dict(
        policy='LLM_AUTONOMOUS_CUSTOMER_V14',model='model',effort='high',source_sha256={'a':'123'},
        world_policy='w',needs_policy='n',memory='m'),result=dict(plans={'P':dict(autonomous_decisions=[dict(
            execution_state='EXECUTED',profile_evidence_sha256='profile',implementation_sha256='impl',
            attempts=[dict(provider=dict(execution='LIVE_RESPONSES',model_returned='model'))])])},
            ledger=dict(totals=dict(paid_krw=100),receipts={'P':dict(rows=[dict(venue_id='V',sku_id='SKU',paid_krw=100,quantity=1)])})))
    treatment=copy.deepcopy(base);treatment['request']['catalog_options']={'discount_percent':{'SKU':20}}
    treatment['result']['ledger']['totals']['paid_krw']=80
    treatment['result']['ledger']['receipts']['P']['rows'][0]['paid_krw']=80
    return base,treatment


def compare(pairs):
    with patch.object(C.E,'audit',return_value={'contract_status':'CHECKED_NO_CONTRACT_ISSUE'}):
        return C.compare(pairs,sku_id='SKU',discount_percent=20,venue_id='V')


def test_paired_delta_never_becomes_a_causal_claim():
    result=compare([pair()])
    assert result['paired_customers']==1 and result['aggregate_delta']['hotel_paid_krw']==-20
    assert result['causal_effect']=='NOT_ESTABLISHED' and not result['human_semantic_approval']
    assert result['aggregate_delta']['target_sku_selected']==0


def test_changed_visit_seed_policy_and_duplicate_customer_are_held():
    a,b=pair();b['request']['seed']=5
    assert compare([(a,b)])['holds'][0]['codes']==['MORE_THAN_DECLARED_DISCOUNT_CHANGED']
    a,b=pair();b['configuration']['policy']='OLD'
    assert 'CONFIGURATION_MISMATCH:policy' in compare([(a,b)])['holds'][0]['codes']
    result=compare([pair(),pair()])
    assert result['paired_customers']==1 and result['status']=='HOLD_INCOMPARABLE_PAIRS'


def test_mock_and_fixed_choice_repricing_do_not_qualify():
    a,b=pair();b['result']['plans']['P']['autonomous_decisions'][0]['attempts'][0]['provider']['execution']='MOCK'
    assert compare([(a,b)])['paired_customers']==0
    a,b=pair();b['result']['plans']['P']['autonomous_decisions']=[]
    assert 'NO_AUTONOMOUS_DECISIONS' in compare([(a,b)])['holds'][0]['codes']


def test_same_request_with_different_profile_evidence_is_not_comparable():
    a,b=pair();b['result']['plans']['P']['autonomous_decisions'][0]['profile_evidence_sha256']='changed'
    assert 'PROFILE_EVIDENCE_MISMATCH_OR_MISSING' in compare([(a,b)])['holds'][0]['codes']
