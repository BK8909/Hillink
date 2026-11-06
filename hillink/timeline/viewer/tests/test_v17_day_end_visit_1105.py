"""V17 end-to-end with a synthetic provider that always tries to end the day early.

The stored V16 path is untouched; this exercises the V17 request format, the
day-end review, the replan contract and the recorded review outcome. Synthetic
answers are not model-quality evidence.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger  # noqa: F401
from operator_choice.autonomy_v1 import autonomous_agent as A

FIXTURE='''import json,sys
sys.path.insert(0,sys.argv[1])
import flow_run
from operator_choice.autonomy_v1 import autonomous_agent as A, agent_provider as P
LOG=[]
def answer(**kw):
 c=kw['context']; actions=c['actions']; keys=list(c)
 assert kw['policy']==A.POLICY_V17 and kw['stable_prefix'] is True and keys[:2]==['personal','visit'], (kw['policy'],keys[:3])
 if kw['purpose']=='CUSTOMER_ACTION_PLAN': assert 'fatigue_scale' in c['state'] and 'today_remaining' in c['state']
 wire=P.serialize_context(c,True); assert wire.startswith('{"personal":')
 prior=c.get('previous_rejection')
 end=next((x for x in actions if x['action_id']=='end_day_in_room'),None)
 meal=next((x for x in actions if x['kind']=='MEAL'),None)
 if end and not prior:
  plan=dict(action_id='end_day_in_room',items=[],order_total_krw=0,decision_summary='합성: 바로 오늘을 마친다',why_not_other_plans='')
 elif end and prior and 'MEAL_REVIEW' in prior['reason'] and meal:
  order=meal.get('existing_orders',[dict(items=meal.get('items',[]),total_krw=meal.get('order_total_krw',0))])[0]
  plan=dict(action_id=meal['action_id'],items=order.get('items',[]),order_total_krw=order.get('total_krw',0),decision_summary='합성: 거절 사유를 보고 저녁을 먹는다',why_not_other_plans='end_day_in_room은 저녁 전이라 미룸')
 elif end and prior:
  others=[x['action_id'] for x in actions if x['action_id'] not in ('end_day_in_room','room_rest','ROOM_REST','public_rest','wait_reconsider')]
  plan=dict(action_id='end_day_in_room',items=[],order_total_krw=0,decision_summary='합성: 비교 후 종료',why_not_other_plans='비교한 후보: '+', '.join(others[:3]))
 else:
  selected=meal or actions[0]
  order=selected.get('existing_orders',[dict(items=selected.get('items',[]),total_krw=selected.get('order_total_krw',0))])[0]
  plan=dict(action_id=selected['action_id'],items=order.get('items',[]),order_total_krw=order.get('total_krw',0),decision_summary='합성',why_not_other_plans='')
 meal_plan=plan['action_id'].startswith('meal:') or plan['action_id']=='BREAKFAST_BUFFET' or (plan['items'] and plan['action_id']!='end_day_in_room' and next((x for x in actions if x['action_id']==plan['action_id']),{}).get('kind') in ('MEAL','BREAKFAST'))
 plan.update(supporting_fact_ids=[],counterevidence_fact_ids=[],assumptions=['TEST'],sharing_plan='합성',schedule_impact='',pending_intentions=[],
  current_need_assessment=dict(state='COMFORTABLE',reason='합성'),
  meal_assessment=dict(kind='FULL_MEAL',modeled_diners=c['visit'].get('party_size') or 2,intake_assumption='합성',quantity_reason='합성',expected_satiety='UNCERTAIN',uncertainties=[]) if meal_plan else None)
 return dict(plans=[plan],selected_index=0),dict(execution='SYNTHETIC_TEST',input_sha256='fixture')
A.P.request=answer
flow_run.main()
'''


def test_v17_visit_reviews_the_early_day_end_and_records_the_outcome(tmp_path):
    import visit_run as V
    script=tmp_path/'fixture.py';script.write_text(FIXTURE)
    with patch.dict(os.environ,dict(HILLINK_AUTONOMOUS_AGENT='1',HILLINK_NATIVE_HYBRID='1',HILLINK_V12Z_COMMON='1',
        HILLINK_HYBRID='replay',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0',HILLINK_ISOLATED_CUSTOMERS='0')):
        request=dict(personas=['A05'],duration='stay_1',event_mode='none',seed=62,start_date='2026-11-09',environment=dict(arrival_time='14:30'),
            behavior_engine='m4_c01',catalog_policy=A.H.POLICY,hybrid_policy=A.POLICY_V17)
        with patch.object(V,'FLOW',[sys.executable,str(script),str(Path(__file__).resolve().parents[1])]):
            flow=V.run_visit(request)
    assert 'error' not in flow,flow
    decs=flow['plans']['A05']['autonomous_decisions']
    assert decs and all(d['policy']==A.POLICY_V17 for d in decs)
    assert flow['plans']['A05']['trace']['planner_backend']==A.POLICY_V17
    ends=[d for d in decs if (d.get('selected_plan') or {}).get('action_id')=='end_day_in_room']
    assert ends,'the synthetic provider always tries to end the day; one review must have let it through after a named comparison'
    for d in ends:
        assert d['day_end_review']['accepted_on']=='REPLAN_AFTER_REVIEW' and d['day_end_review']['first_choice_rejected']
        reasons=[a['validation_rejection'] for a in d['attempts'] if a.get('validation_rejection')]
        assert reasons and reasons[0].startswith('EARLY_DAY_END')
        assert d['day_end_review']['fatigue']['level'] in ('여유','조금 피곤','피곤')
    # Every early-end attempt went through the review; none passed on the first try.
    assert all(len(d['attempts'])==2 for d in ends)
    scenes=flow['plans']['A05']['scenes']
    assert all('취침' not in (s.get('label') or '') for s in scenes)
