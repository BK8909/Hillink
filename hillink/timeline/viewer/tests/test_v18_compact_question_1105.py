"""V18 question-design variants B/C/D: candidate-centred evidence and the minimal output contract.

Synthetic personas and rows; nothing here is model-quality evidence.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hotel_ledger  # noqa: F401
from operator_choice.autonomy_v1 import autonomous_agent as A
from operator_choice.autonomy_v1 import compact_question as CQ

PERSONAL = dict(
    citable_fact_ids=['F-PIZ', 'F-FOOT', 'F-SPA', 'F-OTHER', 'F-BF', 'F-TRAVEL'],
    profile=dict(customer_type='미식', summary='테스트 고객 요약', review_confirmed={'x': 1}),
    evidence_grades={'F-SPA': [dict(facet='warm_rest', grade='rep')], 'F-TRAVEL': [dict(facet='novelty', grade='rep')]},
    evidence_records=[
        dict(fact_ids=['F-PIZ'], summary='피자힐 피자를 포장해 객실에서 먹었다.', source_scope='wh'),
        dict(fact_ids=['F-FOOT'], summary='추운 날 족욕을 하며 한강을 봤다.', source_scope='wh'),
        dict(fact_ids=['F-SPA'], summary='욕조가 있는 객실을 골랐다.', source_scope='wh'),
        dict(fact_ids=['F-OTHER'], summary='다른 호텔 룸서비스가 비싸 밖에서 사 먹었다.', source_scope='other'),
        dict(fact_ids=['F-BF'], summary='조식 뷔페를 일찍 먹었다.', source_scope='wh'),
        dict(fact_ids=['F-TRAVEL'], summary='해외 여행에서 야시장을 돌았다.', source_scope='other')])


def rows():
    return [dict(action_id='meal:PIZZA_HILL', type='MEAL', m4=dict(direct_evidence_fact_ids=['F-PIZ'], evidence_fact_ids=[], trait_terms=[]),
                 basket_groups=[dict(label='피자', experience_fact_ids=['F-PIZ'], options=[dict(basket_id='meal:PIZZA_HILL#1', experience_fact_ids=['F-PIZ'])])]),
            dict(action_id='activity:footbath:SKU', type='ACTIVITY', m4=dict(direct_evidence_fact_ids=['F-FOOT'], evidence_fact_ids=['F-FOOT'], trait_terms=[dict(trait='warm_rest')])),
            dict(action_id='end_day_in_room', type='DAY_END', m4=dict(trait_terms=[]))]


def base():
    return dict(personal=PERSONAL, visit=dict(date='2026-12-18', party_size=2), state=dict(time='17:51', fatigue_scale=dict(level='여유')),
                activity_experiences=[dict(date='2026-12-18', start_time='16:30', end_time='16:45', label='호텔 도착', domain='체류', action='arrive')],
                meal_experiences=[], memory=dict(pending_intentions=['족욕']))


def test_compact_evidence_keeps_candidate_links_and_drops_unrelated_records():
    ctx, cite, cov = CQ.build(NS(N=2), 1071, base(), rows(), None)
    pb = ctx['personal']
    sent = {f for r in pb['evidence_records'] for f in r['fact_ids']}
    assert {'F-PIZ', 'F-FOOT'} <= sent, 'the records tied to shown candidates are sent whole'
    assert 'F-SPA' in sent, 'a graded record for a trait the candidates read is sent'
    assert 'F-TRAVEL' not in sent and 'F-BF' not in sent, 'unrelated records stay out of the request'
    assert set(cite) == sent == set(pb['citable_fact_ids']) and cov['full_citable'] == 6 and cov['sent_facts'] == len(sent)
    assert cov['candidate_links_sent'] == {'meal:PIZZA_HILL': True, 'activity:footbath:SKU': True, 'end_day_in_room': True}
    assert all(r in PERSONAL['evidence_records'] for r in pb['evidence_records']), 'records are sent whole, never truncated or rewritten'
    assert ctx['candidates'] == rows() and '없었던 사실' in pb['evidence_scope']['note'] and pb['evidence_scope']['mode'] == CQ.SCOPE_CANDIDATE
    assert set(pb['evidence_grades']) == {'F-SPA'} and pb['profile']['summary'] == '테스트 고객 요약'
    # same keys as the full block (plus evidence_scope, which A carries too); every other block passes through unchanged
    full = CQ.with_full_scope(PERSONAL)
    assert list(pb) == list(full) and pb['evidence_scope'].keys() == full['evidence_scope'].keys()
    b = base()
    assert {k: v for k, v in ctx.items() if k not in ('personal', 'candidates')} == {k: v for k, v in b.items() if k != 'personal'}


def test_filtered_profile_keeps_nesting_and_only_sent_evidence_items():
    personal = dict(PERSONAL, profile=dict(customer_type='미식', summary='요약', companion=None,
        review_confirmed=dict(more=[dict(fact_ids=['F-PIZ', 'F-TRAVEL'], what='피자', where='워커힐'), dict(fact_ids=['F-TRAVEL'], what='야시장', where='다른 곳')], menu=[]),
        profile_inference=dict(behavior_hypotheses=[dict(if_='x', then='y', status='검증 전 가설')], judgment_patterns=[dict(pattern='p', but=['b'], when=['w'])])))
    ctx, _, _ = CQ.build(NS(N=2), 1071, dict(base(), personal=personal), rows(), None)
    prof = ctx['personal']['profile']
    assert prof['review_confirmed']['more'] == [dict(fact_ids=['F-PIZ'], what='피자', where='워커힐')], 'only sent ids, item otherwise whole'
    assert prof['review_confirmed']['menu'] == [] and prof['profile_inference'] == dict(behavior_hypotheses=[], judgment_patterns=[]), \
        'persona-level inferences without Fact ids are not candidate evidence; the keys stay'
    assert list(prof) == list(personal['profile'])


def test_unconfirmed_source_scope_is_kept_as_recorded():
    personal = dict(PERSONAL, citable_fact_ids=PERSONAL['citable_fact_ids'] + ['F-U'],
                    evidence_records=PERSONAL['evidence_records'] + [dict(fact_ids=['F-U'], summary='족욕을 했다.', source_scope='UNRESOLVED')])
    ctx, cite, cov = CQ.build(NS(N=2), 1071, dict(base(), personal=personal), rows(), None)
    rec = next(r for r in ctx['personal']['evidence_records'] if 'F-U' in r['fact_ids'])
    assert rec['source_scope'] == 'UNRESOLVED', 'the scope the full block carries, never promoted to this hotel'


def test_breakfast_adds_breakfast_records_and_no_evidence_says_so():
    ctx, cite, _ = CQ.build(NS(N=2), 490, base(), [dict(action_id='BREAKFAST_BUFFET', type='BREAKFAST', m4={})], None, 'BREAKFAST')
    assert 'F-BF' in cite
    empty = dict(base(), personal=dict(PERSONAL, evidence_records=[], evidence_grades={}, citable_fact_ids=[]))
    ctx, cite, _ = CQ.build(NS(N=2), 1071, empty, rows(), None)
    note = ctx['personal']['evidence_scope']['note']
    assert ctx['personal']['evidence_records'] == [] and cite == [] and '일반적인 상황 판단' in note and '개인 취향으로 설명하지' in note


def test_minimal_output_is_expanded_with_engine_defaults_labelled_as_such():
    trace = dict(fit={'meal:PIZZA_HILL': dict(basket_index={'meal:PIZZA_HILL#1': dict(sku_id='P1', label='피자', total_krw=69000, items=[dict(sku_id='P1', quantity=1)])})})
    acts = {'meal:PIZZA_HILL': dict(execution='MEAL'), 'end_day_in_room': dict(execution='END_DAY', items=[], order_total_krw=0)}
    spec = A.POLICIES[A.POLICY_V18BD]
    plan, alt = A.expand_answer(dict(selected_action_id='meal:PIZZA_HILL', selected_basket_id='meal:PIZZA_HILL#1', fact_ids=['F-PIZ'], reason='피자를 먹는다.',
                                     rejected_action_id='end_day_in_room', need='HUNGRY'), rows(), acts, {}, trace, NS(N=2), spec)
    assert plan['items'] == [dict(sku_id='P1', quantity=1)] and plan['order_total_krw'] == 69000 and plan['supporting_fact_ids'] == ['F-PIZ']
    assert plan['meal_assessment']['modeled_diners'] == 2 and '모델 진술 아님' in plan['sharing_plan'] and plan['output_contract'].startswith('V18D_MINIMAL')
    assert plan['current_need_assessment']['state'] == 'HUNGRY' and plan['why_not_other_plans'].startswith('end_day_in_room')
    assert plan['meal_assessment']['uncertainties'] == ['ENGINE_DEFAULT_NOT_MODEL_STATEMENT'] and '모델 진술 아님' in plan['meal_assessment']['intake_assumption']
    assert 'meal_assessment' in plan['engine_default_fields']
    # a drink platter chosen under D is recorded as a beverage, never as a full meal
    drink_rows = [dict(rows()[0], basket_groups=[dict(label='음료·안주: BEER', role='DRINK_SNACK', experience_fact_ids=[], options=[dict(basket_id='meal:PIZZA_HILL#1', experience_fact_ids=[])])])] + rows()[1:]
    beer, _ = A.expand_answer(dict(selected_action_id='meal:PIZZA_HILL', selected_basket_id='meal:PIZZA_HILL#1', fact_ids=[], reason='한잔.',
                                   rejected_action_id=None, need='FULL'), drink_rows, acts, {}, trace, NS(N=2), spec)
    assert beer['meal_assessment']['kind'] == 'BEVERAGE'
    A.X.validate_assessment(plan, 2, True)
    rest, _ = A.expand_answer(dict(selected_action_id='end_day_in_room', selected_basket_id=None, fact_ids=[], reason='마친다.', rejected_action_id=None, need='FULL'),
                              rows(), acts, {}, trace, NS(N=2), spec)
    assert rest['meal_assessment'] is None and rest['current_need_assessment']['state'] == 'FULL'


FIXTURE = '''import json,sys,os
sys.path.insert(0,sys.argv[1])
import flow_run, jsonschema
from operator_choice.autonomy_v1 import autonomous_agent as A
POLICY=os.environ['HL_TEST_POLICY']
def answer(**kw):
 c=kw['context']; rows=c['candidates']; prior=c.get('previous_rejection'); by={r['action_id']:r for r in rows}
 assert kw['policy']==POLICY and c['personal']['evidence_scope']['mode']=='CANDIDATE_RELATED_EVIDENCE' and 'facts' not in c and 'menus' not in c
 assert kw['prefix_message']=='personal'
 meals=[r for r in rows if r['type']=='MEAL']; acts=[r for r in rows if r['type']=='ACTIVITY']; rests=[r for r in rows if r['type']=='REST']
 basket=None; meal=False
 if kw['purpose']=='BREAKFAST_SELECTION':
  sel=next((r['action_id'] for r in rows if r['type']=='BREAKFAST'),rows[0]['action_id']); meal=sel!='SKIP_BREAKFAST'; alt='SKIP_BREAKFAST'
 elif prior and 'end_day_in_room' in by:
  sel='end_day_in_room'; alt=(acts or rests or meals)[0]['action_id']
 elif 'end_day_in_room' in by: sel='end_day_in_room'; alt=None
 elif 'leave_visit' in by: sel='leave_visit'; alt=None
 elif meals: sel=meals[0]['action_id']; basket=meals[0]['basket_groups'][0]['options'][0]['basket_id']; meal=True; alt=None
 else: sel=rows[0]['action_id']; alt=None
 fact=c['personal']['citable_fact_ids'][:1]
 if 'fact_ids' in kw['schema']['properties']:
  out=dict(selected_action_id=sel,selected_basket_id=basket,fact_ids=fact,reason='합성',rejected_action_id=alt,need='COMFORTABLE')
 else:
  out=dict(selected_action_id=sel,selected_basket_id=basket,reason='합성',supporting_fact_ids=fact,counterevidence_fact_ids=[],rejected_alternative=dict(action_id=alt or '',reason='합성'),
   next_intent=None,current_need_assessment=dict(state='COMFORTABLE',reason='합성'),
   meal_assessment=dict(kind='FULL_MEAL',modeled_diners=2,sharing_plan='합성',quantity_reason='합성',expected_satiety='UNCERTAIN') if meal else None)
 jsonschema.validate(out,kw['schema'])
 return out,dict(execution='SYNTHETIC_TEST',input_sha256='fixture')
A.P.request=answer
flow_run.main()
'''


@pytest.mark.parametrize('policy', [A.POLICY_V18B, A.POLICY_V18BD])
def test_compact_variants_run_a_visit_end_to_end(tmp_path, policy):
    import visit_run as V
    script = tmp_path / 'fixture.py'; script.write_text(FIXTURE)
    with patch.dict(os.environ, dict(HILLINK_AUTONOMOUS_AGENT='1', HILLINK_NATIVE_HYBRID='1', HILLINK_V12Z_COMMON='1', HL_TEST_POLICY=policy,
                                     HILLINK_HYBRID='replay', HILLINK_LLM_ENABLED='0', HILLINK_LLM_EXTERNAL_OPT_IN='0', HILLINK_ISOLATED_CUSTOMERS='0')):
        request = dict(personas=['A05'], duration='stay_1', event_mode='none', seed=62, start_date='2026-11-09', environment=dict(arrival_time='14:30'),
                       behavior_engine='m4_c01', catalog_policy=A.H.POLICY, hybrid_policy=policy)
        with patch.object(V, 'FLOW', [sys.executable, str(script), str(Path(__file__).resolve().parents[1])]):
            flow = V.run_visit(request)
    assert 'error' not in flow, flow
    decs = flow['plans']['A05']['autonomous_decisions']
    assert decs and all(d['policy'] == policy and d['execution_state'] == 'EXECUTED' for d in decs), [d.get('fallback_reason') for d in decs]
    llm = [d for d in decs if d.get('attempts')]
    assert llm and all(d.get('evidence_coverage', {}).get('policy') == CQ.POLICY for d in llm)
    # a cited Fact must be one that was sent (validated against the compact citable set)
    for d in llm:
        cited = set(d['selected_plan']['supporting_fact_ids'])
        assert cited <= set(sum(d['evidence_coverage']['per_candidate'].values(), [])) | set(d['evidence_coverage']['reasons'])
    ends = [d for d in decs if d['selected_plan']['action_id'] == 'end_day_in_room']
    assert ends and any(d.get('day_end_review', {}).get('first_choice_rejected') for d in ends), 'the early day end is still reviewed under the compact question'


def test_provider_capture_records_the_exact_body_and_does_not_change_the_identity(monkeypatch):
    import json as _j
    from operator_choice.autonomy_v1 import agent_provider as P
    sent = {}
    class Resp:
        def read(self): return _j.dumps(dict(id='resp_1', model='gpt-6-luna', status='completed', usage=dict(input_tokens=10, output_tokens=5),
                                             output=[dict(type='message', content=[dict(type='output_text', text='{"x":1}')])])).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def urlopen(req, timeout, context):
        sent['body'] = _j.loads(req.data); sent['auth'] = req.headers.get('Authorization'); return Resp()
    import types
    monkeypatch.setattr(P.urllib.request, 'urlopen', urlopen)
    monkeypatch.setitem(sys.modules, 'openai_credentials', types.SimpleNamespace(load_openai_api_key=lambda: 'sk-test-secret'))
    monkeypatch.setattr(P, 'configured_budget', lambda: NS(reserve=lambda m, meta: 'rid', settle=lambda rid, **kw: dict(kw, charged_upper_usd=0)))
    schema = {'type': 'object', 'properties': {'x': {'type': 'integer'}}, 'required': ['x'], 'additionalProperties': False}
    kw = dict(policy='T', system='s', context=dict(personal={'a': 1}, state={'b': 2}), schema=schema, purpose='TEST', effort='medium', stable_prefix=True, prefix_message=None)
    seen = []
    with patch.dict(os.environ, dict(HILLINK_AGENT_MODE='live', HILLINK_LLM_EXTERNAL_OPT_IN='1', HILLINK_AGENT_CACHE='')):
        answer, trace = P.request(**kw, capture=lambda stage, value: seen.append((stage, value)))
        answer2, trace2 = P.request(**kw)
    stages = dict(seen)
    assert [s for s, _ in seen] == ['request', 'response']
    assert stages['request']['request_body'] == sent['body'], 'the captured body is exactly what was sent'
    assert 'sk-test-secret' not in _j.dumps(seen) and sent['auth'] == 'Bearer sk-test-secret', 'credentials stay in the header only'
    assert stages['request']['input_sha256'] == trace['input_sha256'] == trace2['input_sha256'], 'capture does not change the request identity'
    body = P.build_payload(system='s', context=kw['context'], schema=schema, model='gpt-6-luna', effort='medium', max_output=6000, stable_prefix=True)
    assert body == sent['body'] and P.request_identity('T', 'TEST', body) == trace['input_sha256']
    assert stages['response']['response_body']['id'] == 'resp_1' and stages['response']['answer'] == {'x': 1}
