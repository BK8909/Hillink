"""V19LS (stabilised LS): stance/flags, candidate links, repeat signal, diagnostics, integrity, policy wiring.

Synthetic requests built from the shapes of the 2026-11-06 LS calls; summaries paraphrase the de-identified
records. Nothing here is model-quality evidence: it checks what is sent and what is recorded.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v18_shortlist_selection_1105 import A  # noqa: E402
from operator_choice.autonomy_v1 import ls_stability as LSS  # noqa: E402

REFUSED = '공간·서비스·가격은 인정했지만 피자를 좋아하지 않는 본인에게 가격 대비 만족이 낮아 다음에는 오지 않겠다고 결론냈다.'
MIXED = '피자힐은 매우 비싸지만 맛은 있었음 (치즈 · 오이피클이 좋았음) — 가격 대비로는 아쉬움'
CONDITIONAL_REFUSAL = '너무 비싸서 특별한 날이 아니면 피자힐은 다시 안 갈 것 같다고 함'
LEFTOVER = '성인 3명이 트리플세트를 주문해 먹고 남은 피자 두 조각을 포장했다.'
NOT_LEFTOVER = '두 사람이 지쳐 객실 사진도 거의 남기지 못한 채 쉬었다.'
BELOW = '이전 좋은 식사를 계기로 다시 찾았지만 코스 전반의 품질이 기대에 못 미쳤다고 적었다.'


def lean(records, candidates=None, recent=None, party=3):
    cands = candidates or [
        dict(action_id='meal:PIZZA_HILL', type='MEAL', label='피자힐', location='PIZZA_HILL', conditions=dict(wait_minutes=0),
             basket_groups=[dict(label='파스타 + 피자', role='MEAL', options=[dict(basket_id='meal:PIZZA_HILL#14', label='L + 파스타', total_krw=127000, meal_equivalents=4, items=[dict(label='피자 L', quantity=1), dict(label='파스타', quantity=1)])])]),
        dict(action_id='meal:THE_PAVILION', type='MEAL', label='THE_PAVILION', location='THE_PAVILION', conditions=dict(wait_minutes=0),
             basket_groups=[dict(label='샌드위치', role='MEAL', options=[dict(basket_id='meal:THE_PAVILION#4', label='클럽샌드위치', total_krw=123000, meal_equivalents=None, items=[dict(label='클럽샌드위치', quantity=3)])])]),
        dict(action_id='room_rest', type='REST', label='객실 휴식', location='ROOM'),
    ]
    recs = [dict(fact_ids=ids, summary=s, source_scope=scope) for ids, s, scope in records]
    return dict(personal=dict(records=recs, citable_fact_ids=sorted(f for r in recs for f in r['fact_ids'])),
                visit=dict(party_size=party, purpose=dict(status='UNCONFIRMED')), candidates=cands, recent_decisions=recent or [])


def test_stance_reads_refusal_mixed_conditional_and_leftover_without_inventing_dislike():
    assert LSS.stance(REFUSED)[0] == 'MIXED' and 'REVISIT_REFUSAL' in LSS.stance(REFUSED)[1]
    assert LSS.stance(MIXED)[0] == 'MIXED'
    s, f, _ = LSS.stance(CONDITIONAL_REFUSAL)
    assert s == 'NEGATIVE' and {'REVISIT_REFUSAL', 'CONDITIONAL'} <= set(f)
    s, f, _ = LSS.stance(LEFTOVER)
    assert s == 'NEUTRAL' and f == ['LEFTOVER'], 'a leftover is a quantity record, not a dislike'
    assert 'LEFTOVER' not in LSS.stance(NOT_LEFTOVER)[1], '"사진을 남기지 못함" is not food left over'
    assert LSS.stance(BELOW)[0] in ('NEGATIVE', 'MIXED')
    assert LSS.stance('부모와 요가 두 가지를 신청해 참여했다.')[0] == 'NEUTRAL'
    assert LSS.stance('예약을 취소했다.', kind='decline')[0] == 'NEGATIVE'


def test_annotate_links_this_hotel_records_and_marks_unconfirmed_named_sources():
    out = LSS.annotate(lean([(['F18'], REFUSED, 'wh'), (['F17'], MIXED, 'UNRESOLVED'), (['F90'], '다른 호텔 룸서비스가 편했다.', 'other')]),
                       venue_links={'meal:PIZZA_HILL': {'F18'}})
    r = {x['fact_ids'][0]: x for x in out['personal']['records']}
    assert r['F18']['about'] == ['meal:PIZZA_HILL'] and r['F18']['stance'] == '혼합' and '재방문 거부' in r['F18']['flags']
    assert r['F17']['about'] == ['meal:PIZZA_HILL'] and r['F17']['about_scope'].startswith('UNCONFIRMED'), 'a named venue is kept, with its source marked'
    assert 'about' not in r['F90'], 'another hotel room service is not this hotel'
    assert out['personal']['stance_note'] and 'stance' not in lean([])['personal'], 'annotation works on a copy'
    # the summaries, ids and scopes the model gets are the ones in the evidence
    full = dict(evidence_records=[dict(fact_ids=['F18'], summary=REFUSED, source_scope='wh'), dict(fact_ids=['F17'], summary=MIXED, source_scope='UNRESOLVED'),
                                  dict(fact_ids=['F90'], summary='다른 호텔 룸서비스가 편했다.', source_scope='other')])
    assert LSS.integrity(full, out) == []
    broken = copy.deepcopy(out); broken['personal']['records'][0]['source_scope'] = 'other'; del broken['personal']['records'][1]['stance']
    codes = {c for c, _ in LSS.integrity(full, broken)}
    assert {'SCOPE_CHANGED', 'NO_STANCE'} <= codes


def answer(sel='meal:PIZZA_HILL', basket='meal:PIZZA_HILL#14', reason='늦은 점심으로 피자와 파스타를 고릅니다.', counter=(), support=(), note=None, qty='3명이 나눕니다.'):
    return dict(selected_action_id=sel, selected_basket_id=basket, reason=reason, supporting_fact_ids=list(support), counterevidence_fact_ids=list(counter),
                tradeoff_note=note, meal_assessment=dict(quantity_reason=qty))


def test_diagnose_reproduces_the_a02_and_wh00532_defects_and_accepts_explained_choices():
    l = LSS.annotate(lean([(['F18'], REFUSED, 'wh'), (['F14'], LEFTOVER, 'wh')]), venue_links={'meal:PIZZA_HILL': {'F18', 'F14'}})
    codes = {d['code']: d for d in LSS.diagnose(answer(counter=['F18']), l, 3)}
    assert codes['NEGATIVE_RECORD_ON_SELECTED_UNEXPLAINED']['detail']['clean_same_type_alternatives'] == ['meal:THE_PAVILION']
    assert codes['QUANTITY_ABOVE_PARTY_DESPITE_LEFTOVER']['detail']['equivalents'] == 4
    ok = {d['code'] for d in LSS.diagnose(answer(counter=['F18'], note='다른 식당은 135분 대기라 지금 가능한 피자힐을 고름'), l, 3)}
    assert 'NEGATIVE_RECORD_ON_SELECTED_EXPLAINED' in ok, 'a stated current condition plus the cited record is a reviewed trade-off'
    assert LSS.diagnose(answer(sel='meal:THE_PAVILION', basket='meal:THE_PAVILION#4'), l, 3) == []
    m = LSS.annotate(lean([(['F17'], MIXED, 'wh')]), venue_links={'meal:PIZZA_HILL': {'F17'}})
    one = LSS.diagnose(answer(sel='room_rest', basket=None, reason='피자힐은 가격 대비 아쉬워 객실에서 쉽니다.', counter=['F17']), m, 3)
    assert [d['code'] for d in one] == ['MIXED_RECORD_ONE_SIDED']
    both = LSS.diagnose(answer(sel='room_rest', basket=None, reason='피자힐은 맛은 좋았지만 가격이 아쉬워 객실에서 쉽니다.', counter=['F17']), m, 3)
    assert both == []
    assert LSS.diagnose(answer(counter=['F99']), m, 3)[0]['code'] == 'CITED_NOT_SENT'


def test_repeat_signal_is_information_not_a_forced_choice():
    rec = [dict(time='12:10', action_id='wait_reconsider', reason='점심 대기', need='UNCERTAIN'), dict(time='12:40', action_id='wait_reconsider', reason='점심 대기', need='UNCERTAIN')]
    out = LSS.annotate(lean([], recent=rec))
    assert out['repeat_signal']['action_id'] == 'wait_reconsider' and '정상' in out['repeat_signal']['note']
    assert [c['action_id'] for c in out['candidates']] == ['meal:PIZZA_HILL', 'meal:THE_PAVILION', 'room_rest'], 'no candidate is added, dropped or reordered'
    assert LSS.diagnose(answer(sel='wait_reconsider', basket=None), out, 3)[0]['code'] == 'REPEATED_WAIT_AFTER_SIGNAL'
    assert 'repeat_signal' not in LSS.annotate(lean([], recent=[rec[0], dict(rec[1], action_id='room_rest')]))


def test_policy_is_registered_as_separate_development_policy_and_v17_is_unchanged():
    spec = A.POLICIES[A.POLICY_V19LS]
    assert A.POLICY_V19LS == 'LLM_AUTONOMOUS_CUSTOMER_V19LS' and spec['stance'] and spec['stability'] and spec['effort'] == 'medium'
    sys_text = spec['system_for']([dict(type='MEAL'), dict(type='REST')])
    assert '긍정·부정은 표시돼 있지 않으니' not in sys_text and 'tradeoff_note' in sys_text and '재방문 거부' in sys_text
    assert sys_text.index('응답 작성:') > sys_text.index('repeat_signal'), 'stability rules sit before the output block'
    assert 'tradeoff_note' in spec['schema']['properties'] and 'tradeoff_note' in spec['schema']['required']
    assert 'tradeoff_note' not in A.SELECTION_V18['properties'], 'the V18 schema is not modified'
    v17 = A.POLICIES[A.POLICY_V17]
    assert not v17.get('stance') and not v17.get('stability') and v17['context'] == 'AUTONOMOUS_CONTEXT_V17'


def test_provider_failures_are_classified_and_only_malformed_answers_are_reasked():
    c = A.provider_failure_class
    assert c('JSONDecodeError') == c('ValidationError') == c('RESPONSE_INCOMPLETE') == 'MALFORMED_OR_INCOMPLETE_RESPONSE'
    assert c('HTTP_429') == 'RATE_LIMITED' and c('HTTP_503') == 'PROVIDER_SERVER_ERROR'
    assert c('TimeoutError') == 'DELIVERY_UNCERTAIN', 'uncertain delivery is held, never re-sent'
    assert c('REPLAY_MISS') == 'REPLAY_MISMATCH' and c('EXTERNAL_CALL_NOT_AUTHORIZED') == 'NOT_AUTHORIZED'
    assert 'MALFORMED_OR_INCOMPLETE_RESPONSE' not in {c(x) for x in ('HTTP_429', 'HTTP_500', 'TimeoutError', 'URLError', 'BUDGET_EXCEEDED')}


def test_v19ls_visit_runs_end_to_end_with_annotated_requests_one_safe_reask_and_no_duplicate_orders(tmp_path):
    """Synthetic provider (no key, no cost): every request must carry stance-annotated records and the
    stability rules; the first call of each meal decision returns a malformed answer once. The visit must
    still execute every decision, re-ask exactly once there, and keep orders = ledger."""
    import os
    from unittest.mock import patch
    import visit_run as V
    from test_v18_shortlist_selection_1105 import FIXTURE
    fx = FIXTURE.replace("assert kw['policy']==A.POLICY_V18 and", "assert kw['policy']==A.POLICY_V19LS and")
    fx = fx.replace(" jsonschema.validate(out,kw['schema'])",
                    " out['tradeoff_note']=None\n"
                    " assert 'tradeoff_note' in kw['system'] and all('stance' in r for r in c['personal'].get('records',[]))\n"
                    " assert 'selection_reasons' not in (c['personal'].get('evidence_scope') or {})\n"
                    " key=(c['state']['time'],sel)\n"
                    " if meal and key not in SEEN and not prior:\n"
                    "  SEEN.add(key); raise P.ProviderUnavailable('JSONDecodeError')\n"
                    " jsonschema.validate(out,kw['schema'])")
    fx = fx.replace("def answer(**kw):", "SEEN=set()\ndef answer(**kw):")
    assert fx.count('POLICY_V19LS') == 1 and 'SEEN.add' in fx
    script = tmp_path / 'fixture.py'; script.write_text(fx)
    with patch.dict(os.environ, dict(HILLINK_AUTONOMOUS_AGENT='1', HILLINK_NATIVE_HYBRID='1', HILLINK_V12Z_COMMON='1',
                                     HILLINK_HYBRID='replay', HILLINK_LLM_ENABLED='0', HILLINK_LLM_EXTERNAL_OPT_IN='0', HILLINK_ISOLATED_CUSTOMERS='0')):
        request = dict(personas=['A05'], duration='stay_1', event_mode='none', seed=62, start_date='2026-11-09', environment=dict(arrival_time='14:30'),
                       behavior_engine='m4_c01', catalog_policy=A.H.POLICY, hybrid_policy=A.POLICY_V19LS)
        with patch.object(V, 'FLOW', [sys.executable, str(script), str(Path(__file__).resolve().parents[1])]):
            flow = V.run_visit(request)
    assert 'error' not in flow, flow
    decs = flow['plans']['A05']['autonomous_decisions']
    assert decs and all(d['policy'] == A.POLICY_V19LS for d in decs)
    assert all(d['execution_state'] == 'EXECUTED' for d in decs), [(d['execution_state'], d.get('hold_reason'), d.get('fallback_reason'), d.get('selection_owner'), [{k: x.get(k) for k in ('error', 'failure_class', 'validation_rejection')} for x in d.get('attempts', [])]) for d in decs if d['execution_state'] != 'EXECUTED']
    llm = [d for d in decs if d.get('selection_owner', '').startswith('LLM')]
    act = [d for d in llm if d['selection_owner'] == 'LLM_SELECTION_FROM_M4_SHORTLIST']   # breakfast keeps its fixed-option path
    assert act and all(d.get('stability_policy') == LSS.POLICY and isinstance(d.get('selection_diagnostics'), list) for d in act)
    assert all(d.get('evidence_integrity') == [] for d in act), [d.get('evidence_integrity') for d in act]
    reasked = [d for d in llm if any(x.get('failure_class') == 'MALFORMED_OR_INCOMPLETE_RESPONSE' for x in d['attempts'])]
    assert reasked, 'the synthetic malformed answers must have been re-asked'
    for d in reasked:
        assert len(d['attempts']) == 2 and d['attempts'][0].get('failure_class') and 'selection' in d['attempts'][1]
    # one executed order per decision: the re-ask never produced a second order (orders = ledger)
    sm = flow['plans']['A05'].get('summary') or {}
    ordered = sum((d.get('selected_plan') or {}).get('order_total_krw') or 0 for d in decs if d['execution_state'] == 'EXECUTED')
    assert sm.get('spent_krw') == ordered, (sm.get('spent_krw'), ordered)


def test_p5_plan_stays_within_the_approval_and_separates_cause_from_product_comparison():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/v18_batch'))
    import batch as B
    jobs = B.plan_v19()
    assert len(jobs) == 36 and round(sum(j['max_usd'] for j in jobs), 3) <= 5.00 and B.V19['max_calls'] == 200
    assert sum(B.V19['pools'].values()) == B.V19['max_calls']
    prod = [j for j in jobs if j['exp'] == 'B']; cause = [j for j in jobs if j['exp'] == 'A']
    assert {j['policy'] for j in prod} == {'V17', 'V19LS'} and {j['rep'] for j in prod} == {1, 2}
    first = {r: [j['policy'] for j in prod if j['rep'] == r][0] for r in (1, 2)}
    assert first == {1: 'V17', 2: 'V19LS'}, 'run order is crossed between repetitions'
    a07 = [j for j in prod if j['pid'] == 'A07']
    assert a07 and all('"visit_purpose": "anniversary"' in ' '.join(j['args']) for j in a07), 'the anniversary purpose is given by the operator scenario'
    assert {j['pid'] for j in prod} == {'N03', 'WH-00532', 'A02', 'A07', 'A19', 'A05'}
    med = [j for j in cause if j['policy'] == 'V17M']
    assert med and all(j['env'] == {'HILLINK_AGENT_EFFORT': 'medium'} for j in med)
    assert all(j['env'] == {} for j in cause if j['policy'] in ('LS', 'V19LS')), 'LS policies carry their own effort'


ACTS = {'meal:ROOM_MEAL': dict(label='객실 룸서비스', execution='MEAL'), 'activity:LIBRARY': dict(label='더 라이브러리', execution='ACTIVITY'),
        'meal:PIZZA_HILL': dict(label='피자힐', execution='MEAL'), 'end_day_in_room': dict(label='객실에서 하루 마치기', execution='END_DAY')}
OTHERS = ['meal:ROOM_MEAL', 'activity:LIBRARY']


def test_day_end_match_accepts_real_comparisons_normal_cases():
    """P5 saved second answers (paraphrased): a comparison that names the candidate by a distinctive word."""
    for text in ('추가 룸서비스 식사보다 오늘을 마치는 편이 적절합니다',
                 '저녁을 먹은 지 두 시간이 안 돼 룸서비스는 필요하지 않습니다',
                 '라이브러리는 내일 들르고 오늘은 여기서 마칩니다',
                 'meal:ROOM_MEAL: 배가 불러 추가 주문 없음 오늘을 마칩니다',
                 '객실 룸서비스까지 비교했지만 오늘을 마칩니다'):
        assert LSS.names_compared(text, ACTS, OTHERS), text
    assert LSS.compared_by('meal:ROOM_MEAL: 배가 부름', ACTS, OTHERS) == 'STRUCTURED_ALTERNATIVE'
    assert LSS.compared_by('room_rest: 이미 쉼 meal:ROOM_MEAL은 필요 없음', ACTS, OTHERS) == 'ID'
    assert LSS.compared_by('room_rest: 이미 쉼', ACTS, OTHERS) is None   # a rest alternative is not a remaining candidate
    assert LSS.compared_by('객실 룸서비스는 생략', ACTS, OTHERS) == 'LABEL'
    assert LSS.compared_by('룸서비스 대신 오늘을 마칩니다', ACTS, OTHERS) == 'DISTINCTIVE_WORD_IN_COMPARISON'


def test_day_end_match_boundaries():
    # 3+ characters only, generic place words never count, candidate not in the remaining list never counts
    assert not LSS.names_compared('객실에서 쉬었고 식사도 마쳤으니 오늘은 필요 없습니다', ACTS, OTHERS)
    assert not LSS.names_compared('피자힐보다 오늘을 마치는 편이 낫습니다', ACTS, OTHERS)
    assert not LSS.names_compared('', ACTS, OTHERS)
    assert LSS.label_words('더 라이브러리') == ['라이브러리'] and LSS.label_words('객실 룸서비스') == ['룸서비스']
    assert LSS.label_words('객실 휴식') == []


def test_day_end_match_rejects_bare_or_unrelated_mentions_misrecognition():
    for text in ('룸서비스 룸서비스', '룸서비스', '룸서비스가 맛있었다 그리고 이제 오늘을 마칩니다',
                 '어제 라이브러리에서 음악을 들었다. 오늘은 마칩니다', '룸서비스 메뉴판을 봤다'):
        assert not LSS.names_compared(text, ACTS, OTHERS), text


def test_reviewed_day_end_tolerant_match_is_v19ls_only_and_first_rejection_is_kept():
    import inspect
    from operator_choice.autonomy_v1 import autonomous_agent as AG
    assert inspect.signature(AG.v18_day_end_reasons).parameters['loose'].default is False
    assert AG.POLICIES[AG.POLICY_V19LS].get('stability') and not AG.POLICIES[AG.POLICY_V18LS].get('stability')
    assert not AG.POLICIES[AG.POLICY_V17].get('stability')
    src = inspect.getsource(AG.v18_day_end_reasons)
    # the tolerant match lives only inside the "reviewed" (second answer) branch
    assert src.index('if reviewed:') < src.index('LSS.names_compared') < src.index('EARLY_DAY_END_REVIEW_MUST_NAME_COMPARED_OPTIONS')


def test_v19ls_day_end_rejection_asks_for_the_structured_alternative_and_v17_text_is_unchanged():
    import inspect
    from operator_choice.autonomy_v1 import autonomous_agent as AG
    src = inspect.getsource(AG.validate_selection)
    assert "spec.get('stability')" in src and 'DAY_END_REVIEW_HINT' in src
    assert 'rejected_alternative.action_id' in LSS.DAY_END_REVIEW_HINT
    assert 'DAY_END_REVIEW_HINT' not in inspect.getsource(AG.early_day_end_reasons)   # V17 path


def test_day_end_live_recheck_plan_stays_within_16_calls_and_seeds_only_before_the_cutoff(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/v18_batch'))
    import batch as B
    jobs = B.plan_v19d()
    assert B.V19D['max_calls'] == 16 and B.V19D['max_usd'] == 0.05 and sum(j['max_calls'] for j in jobs) <= 16
    assert sorted((j['pid'], j['rep']) for j in jobs) == [('A05', 1), ('A05', 2), ('A07', 1), ('A07', 2)]
    assert all(j['policy'] == 'V19LS' and j['seed']['job'] == 'B_%s_V19LS_r%d' % (j['pid'], j['rep']) for j in jobs)
    assert all('"visit_purpose": "anniversary"' in ' '.join(j['args']) for j in jobs if j['pid'] == 'A07')
    cont = B.plan_v19d_cont()
    assert all(j['seed']['job'] == j['id'] and j['args'][j['args'].index('--e2e-max-decisions') + 1] == '40' for j in cont)
    # seeding: finished calls strictly before the cutoff only; never errors, in-flight records or run state
    seed = tmp_path / 'p5'; calls = seed / 'runs' / 'B_A07_V19LS_r1' / 'calls'; calls.mkdir(parents=True)
    for key in ('A07_2026-11-05_2025_V19LS_CUSTOMER_ACT_a1', 'A07_2026-11-05_2128_V19LS_CUSTOMER_ACT_a1'):
        for kind in ('request', 'response'): (calls / ('%s.%s.json' % (key, kind))).write_text('{}')
    (calls / 'A07_2026-11-05_1933_V19LS_CUSTOMER_ACT_a1.request.json').write_text('{}')
    (calls / 'A07_2026-11-05_1933_V19LS_CUSTOMER_ACT_a1.error.json').write_text('{}')
    (seed / 'runs' / 'B_A07_V19LS_r1' / 'run_state.json').write_text('{}')
    run = tmp_path / 'd' / 'D_A07_V19LS_r1'
    copied = B.seed_checkpoint(jobs[[j['id'] for j in jobs].index('D_A07_V19LS_r1')], str(seed), str(run))
    assert copied == ['A07_2026-11-05_2025_V19LS_CUSTOMER_ACT_a1']
    assert sorted(p.name for p in (run / 'calls').iterdir()) == ['A07_2026-11-05_2025_V19LS_CUSTOMER_ACT_a1.request.json', 'A07_2026-11-05_2025_V19LS_CUSTOMER_ACT_a1.response.json']
    assert not (run / 'run_state.json').exists()


SHORTFALL = '같은 식당을 여러 번 찾았고, 이전 양 부족을 겪은 뒤 각자 스테이크를 시키는 등 주문을 바꿨다.'


def test_portion_shortfall_flag_and_party_fit_are_information_only():
    assert 'PORTION_SHORT' in LSS.stance(SHORTFALL)[1]
    assert 'PORTION_SHORT' not in LSS.stance('중식 코스의 양이 부담돼 단품을 골랐다.')[1], 'too much is not a shortfall'
    assert 'PORTION_SHORT' not in LSS.stance('많이 먹지 못해 정가에는 망설임이 있다.')[1]
    assert [LSS.party_fit(x, 3) for x in (None, 2, 3, 4)] == ['미확인', '인원보다 적음', '인원과 같음', '인원보다 많음']
    out = LSS.annotate(lean([(['F25'], SHORTFALL, 'other')]))
    opts = {o['basket_id']: o for c in out['candidates'] for g in c.get('basket_groups') or [] for o in g['options']}
    assert opts['meal:PIZZA_HILL#14']['party_fit'] == '인원보다 많음' and opts['meal:THE_PAVILION#4']['party_fit'] == '미확인'
    assert [o['basket_id'] for o in opts.values()] == ['meal:PIZZA_HILL#14', 'meal:THE_PAVILION#4'], 'no basket added, removed or reordered'
    assert '양 부족' in out['personal']['records'][0]['flags']
    assert '양을 늘리라는 지시가 아니며' in ' '.join(LSS.SYSTEM_LINES)


def test_quantity_diagnostics_use_known_equivalents_and_never_block():
    l = LSS.annotate(lean([(['F25'], SHORTFALL, 'other')]))
    for o in [o for c in l['candidates'] for g in c.get('basket_groups') or [] for o in g['options']]:
        if o['basket_id'] == 'meal:PIZZA_HILL#14': o['meal_equivalents'] = 3
    codes = [d['code'] for d in LSS.diagnose(answer(), l, 3)]
    assert codes == ['QUANTITY_AT_OR_BELOW_PARTY_DESPITE_SHORTFALL_RECORD']
    assert LSS.diagnose(answer(sel='meal:THE_PAVILION', basket='meal:THE_PAVILION#4'), l, 3) == [], 'unknown equivalents are not judged'
    l2 = LSS.annotate(lean([]))
    for o in [o for c in l2['candidates'] for g in c.get('basket_groups') or [] for o in g['options']]:
        if o['basket_id'] == 'meal:PIZZA_HILL#14': o['meal_equivalents'] = 2
    assert [d['code'] for d in LSS.diagnose(answer(), l2, 3)] == ['QUANTITY_BELOW_PARTY']


def test_mixed_record_cited_only_to_exclude_an_unnamed_candidate_is_not_a_one_sided_reading():
    """P5 A02 14:45: a mixed Pizza Hill record cited as counterevidence for a Pavilion choice whose reason never
    names Pizza Hill. That is an unused citation, reported as such, not a one-sided reading of the record."""
    m = LSS.annotate(lean([(['F18'], REFUSED, 'wh')]), venue_links={'meal:PIZZA_HILL': {'F18'}})
    got = [d['code'] for d in LSS.diagnose(answer(sel='meal:THE_PAVILION', basket='meal:THE_PAVILION#4', reason='대기 없이 바로 먹을 수 있는 샌드위치를 고릅니다.', counter=['F18']), m, 3)]
    assert got == ['COUNTEREVIDENCE_FOR_UNNAMED_ALTERNATIVE']
    named = dict(answer(sel='meal:THE_PAVILION', basket='meal:THE_PAVILION#4', reason='피자힐은 다시 가지 않겠다고 해 제외하고 샌드위치를 고릅니다.', counter=['F18']))
    assert 'COUNTEREVIDENCE_FOR_UNNAMED_ALTERNATIVE' not in [d['code'] for d in LSS.diagnose(named, m, 3)]


def test_partly_included_breakfast_is_shown_per_line_and_in_conditions_without_changing_the_order():
    """P5 re-check A05 r1: 2 of 3 diners were covered by the room contract, but the candidate said included=false
    with price 85,000 (the third diner's cost); the model read 85,000 as the breakfast price and skipped it."""
    contract = dict(components=[dict(sku_id='HC-MENU-098', role='MAIN', billing_quantity=2, unit_price_krw=0, included_benefit='ROOM_BREAKFAST_INCLUDED_CONTRACT'),
                                dict(sku_id='HC-MENU-098', role='MAIN', billing_quantity=1, unit_price_krw=85000)])
    row = dict(action_id='BREAKFAST_BUFFET', conditions=dict(price_krw=85000, included=False),
               items=[dict(sku_id='HC-MENU-098', quantity=2), dict(sku_id='HC-MENU-098', quantity=1)],
               item_contracts=[dict(sku_id='HC-MENU-098', quantity=2), dict(sku_id='HC-MENU-098', quantity=1)])
    before_items = copy.deepcopy(row['items'])
    LSS.breakfast_inclusion(row, contract)
    assert row['conditions']['included'] == dict(status='PARTIAL', included_persons=2, paid_persons=1, extra_cost_krw=85000, basis='ROOM_BREAKFAST_CONTRACT')
    assert row['conditions']['price_krw'] == 85000 and row['items'] == before_items, 'engine order and total unchanged'
    assert [x['price_basis'] for x in row['item_contracts']] == ['객실 조식 포함(추가 비용 없음)', '추가 결제']
    skip = dict(action_id='SKIP_BREAKFAST', conditions=dict(price_krw=0, included=False))
    assert LSS.breakfast_inclusion(skip, None)['conditions']['included'] is False
    full = dict(conditions=dict(price_krw=0, included=True), item_contracts=[dict(sku_id='X', quantity=2)])
    LSS.breakfast_inclusion(full, dict(components=[dict(sku_id='X', role='MAIN', billing_quantity=2, included_benefit='Y')]))
    assert full['conditions']['included']['status'] == 'ALL'
    assert 'paid_persons와 price_krw는 포함되지 않은 인원의 추가 비용' in ' '.join(LSS.SYSTEM_LINES)
    import inspect
    from operator_choice.autonomy_v1 import autonomous_agent as AG
    src = inspect.getsource(AG.breakfast_choice)
    assert "if spec_of(a).get('stability'):" in src and 'LSS.breakfast_inclusion' in src, 'V19LS only; V16/V17 breakfast requests unchanged'


def test_a05_followup_plan_is_four_calls_and_breakfast_reuses_only_offline_evening():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/v18_batch'))
    import batch as B
    jobs = B.plan_v19e()
    assert B.V19E == dict(max_calls=4, max_usd=0.02, pools=dict(E=4)) and sum(j['max_calls'] for j in jobs) == 4
    assert [j['seed']['job'] for j in jobs if j.get('seed')] == ['S_A05_V19LS', 'S_A05_V19LS']
    assert all(j['seed']['before'] == '2026-11-08_0800' for j in jobs if j.get('seed'))
    assert B.plan_v19e_seed()[0]['id'] == 'S_A05_V19LS'
