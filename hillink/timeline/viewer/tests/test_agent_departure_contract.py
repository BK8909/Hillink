"""Compare actual executor movement with the input seen before breakfast choice."""
import os
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
from test_agent_world_choices import A
import visit_run as V


@pytest.mark.parametrize('building',['GRAND','VISTA','DOUGLAS'])
def test_breakfast_departure_and_wait_match_executor_in_all_buildings(tmp_path,building):
    script=tmp_path/'fixture.py'
    script.write_text('''import sys
sys.path.insert(0,sys.argv[1])
import flow_run
from operator_choice.autonomy_v1 import autonomous_agent as A
def answer(**kw):
 actions=kw['context']['actions']
 chosen=next((x for x in actions if x['kind']=='BREAKFAST' and x['action_id']!='SKIP_BREAKFAST'),None)
 if chosen is None:
  chosen=next((x for key in ['end_day_in_room','leave_visit','public_rest'] for x in actions if x['action_id']==key),actions[0])
 order=chosen.get('existing_orders',[dict(items=chosen.get('items',[]),total_krw=chosen.get('order_total_krw',0))])[0]
 meal=chosen['kind'] in ('MEAL','BREAKFAST') and chosen['action_id']!='SKIP_BREAKFAST'
 p=dict(action_id=chosen['action_id'],items=order['items'],order_total_krw=order['total_krw'],
  supporting_fact_ids=[],counterevidence_fact_ids=[],decision_summary='SYNTHETIC_EXECUTOR_CONTRACT',assumptions=['SYNTHETIC'],
  meal_assessment=dict(kind='FULL_MEAL',modeled_diners=2,intake_assumption='model',quantity_reason='contract',expected_satiety='UNCERTAIN',uncertainties=[]) if meal else None,
  sharing_plan='model',schedule_impact='',why_not_other_plans='',pending_intentions=[])
 return dict(plans=[p],selected_index=0),dict(execution='SYNTHETIC_TEST',input_sha256='fixture')
A.P.request=answer
flow_run.main()
''')
    env=dict(HILLINK_AUTONOMOUS_AGENT='1',HILLINK_NATIVE_HYBRID='1',HILLINK_V12Z_COMMON='1',
             HILLINK_HYBRID='off',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',HILLINK_ISOLATED_CUSTOMERS='0')
    request=dict(personas=['A05'],duration='stay_1',event_mode='none',seed=55,start_date='2026-11-07',
        environment={'arrival_time':'16:30'},behavior_engine='m4_c01',catalog_policy=A.H.POLICY,hybrid_policy=A.POLICY,
        visit_conditions={'A05':dict(building=building,party_size=2,
            party_composition=dict(adult_count=2,children=[]),breakfast_plan='breakfast_included')})
    with patch.dict(os.environ,env),patch.object(V,'FLOW',[sys.executable,str(script),str(Path(__file__).resolve().parents[1])]):
        flow=V.run_visit(request)
    assert 'error' not in flow,flow
    plan=flow['plans']['A05'];ds=plan['autonomous_decisions']
    d=next(d for d in ds if d.get('phase')=='breakfast')
    chosen=d['selected_plan']['action_id'];assert chosen!='SKIP_BREAKFAST'
    action=next(x for x in d['input_context']['actions'] if x['action_id']==chosen)
    s=action['schedule'];day=d['date']
    breakfast=next(x for x in plan['scenes'] if x.get('visit_date')==day and
        (x.get('basis',{}).get('autonomous_decision') or {}).get('phase')=='breakfast')
    moves=[x for x in plan['autonomous_memory']['activity_experiences'] if x['date']==day and x['action']=='move'
           and d['minute']<=x['start'] and x['end']<=breakfast['t0']]
    assert moves
    assert A.X.clock(moves[0]['start'])==s['departure_time']
    assert A.X.clock(moves[-1]['start'])==s['final_leg_departure_time']
    assert A.X.clock(moves[-1]['end'])==s['arrival_time']==s['start_time']
    assert A.X.clock(breakfast['t1'])==s['end_time']
    if s['wait_minutes']:
        waits=[x for x in plan['autonomous_memory']['activity_experiences'] if x['date']==day and x['action']=='wait'
               and x['start']>=d['minute'] and x['end']<=moves[0]['start']]
        assert len(waits)==1 and waits[0]['location']==building+'_ROOM'
        assert action['wait']['location']==waits[0]['location']
        assert action['wait']['end_time']==s['departure_time']
    import agent_evaluation as E
    assert E.breakfast_schedule_audit(plan)==[]
    # A valid execution must not hide a corrupted pre-choice departure claim.
    action['schedule']['departure_time']='00:00'
    assert any(x['code']=='BREAKFAST_INPUT_EXECUTION_SCHEDULE_MISMATCH' for x in E.breakfast_schedule_audit(plan))


def test_unknown_party_keeps_adult_rate_assumption_separate_from_actual_age():
    from test_agent_world_choices import actor
    a,_=actor();a.C=dict(a.C,kids=False)
    v=A.X.visit(a)
    assert v['party'] is None and v['party_status']=='COMPOSITION_AND_AGES_UNCONFIRMED'
    assert v['contract_party_assumption']['source']=='LEGACY_ALL_ADULT_PRICE_REFERENCE'
    assert v['contract_party_assumption']['operational_eligibility'].startswith('REVIEW_REQUIRED')
