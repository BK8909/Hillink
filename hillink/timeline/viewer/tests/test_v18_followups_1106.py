"""V18 1106 follow-ups: shortlist-phrased day-end review, FULL needs a basis, need split (N), lean input (L).

Synthetic agents and rows; nothing here is model-quality evidence.
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/v18_bench'))
from test_v18_shortlist_selection_1105 import agent, actions, A  # noqa: E402
import request_diff as RD  # noqa: E402


def plan(action_id='end_day_in_room', state='COMFORTABLE', reason='', why='', summary='마친다.'):
    return dict(action_id=action_id, items=[], order_total_krw=0, decision_summary=summary, why_not_other_plans=why,
                current_need_assessment=dict(state=state, reason=reason), supporting_fact_ids=[], counterevidence_fact_ids=[])


SPEC = A.POLICIES[A.POLICY_V18BM]
SHOWN = ['meal:PIZZA_HILL', 'library', 'room_rest', 'end_day_in_room']


def test_rejection_names_only_shortlisted_candidates_and_counts_the_rest():
    a = agent(fatigue=0.3); acts = actions()
    why = A.v18_day_end_reasons(a, plan(), acts, None, SHOWN, 1071)[0]
    assert why.startswith('EARLY_DAY_END_WITHOUT_EVENING_MEAL_REVIEW') and 'meal:PIZZA_HILL' in why
    assert 'meal:ONDAL' not in why and '이번 후보 밖에도 실행 가능한 1개' in why, 'a hidden valid meal is counted, never named'
    # the shared V16/V17 review is untouched and still lists the whole world
    assert 'meal:ONDAL' in A.early_day_end_reasons(a, plan(), acts, None)[0]
    # dinner resolved: the remaining-options review lists shown activities only
    a2 = agent(fatigue=0.3, meals={'breakfast': False, 'lunch': True, 'dinner': True})
    why2 = A.v18_day_end_reasons(a2, plan(), actions(meal=False), None, ['library', 'room_rest', 'end_day_in_room'], 1180)[0]
    assert why2.startswith('EARLY_DAY_END_WITH_REMAINING_OPTIONS_REVIEW') and 'library' in why2 and 'garden_walk' not in why2 and 'fitness' not in why2
    prior = dict(reason=why2)
    assert A.v18_day_end_reasons(a2, plan(why='library: 오늘은 충분'), actions(meal=False), prior, ['library', 'room_rest', 'end_day_in_room'], 1180) == []
    # the full world still validates: a hidden candidate is not made invalid by the shortlist
    assert 'garden_walk' in actions(meal=False)


def test_full_alone_does_not_close_the_day_with_dinner_unresolved():
    a = agent(fatigue=0.3); acts = actions(); prior = dict(reason='EARLY_DAY_END_WITHOUT_EVENING_MEAL_REVIEW: ...')
    bare = A.v18_day_end_reasons(a, plan(state='FULL', reason='배가 고프지 않음'), acts, prior, SHOWN, 1071)
    assert bare and '근거가 없었습니다' in bare[0], 'a bare FULL state is not a basis'
    told = plan(state='FULL', reason='늦은 점심을 먹어 저녁은 거르고 쉬기로 함')
    assert A.v18_day_end_reasons(a, told, acts, prior, SHOWN, 1071) == [], 'an explicit cause for skipping dinner is a normal choice'
    fed = agent(fatigue=0.3, meal_log=[dict(t=900, end=990, slot='lunch', size='full')])
    assert A.v18_day_end_reasons(fed, plan(state='FULL', reason='배부름'), acts, prior, SHOWN, 1071) == [], 'a simulated meal 81 minutes ago is a basis'
    old = agent(fatigue=0.3, meal_log=[dict(t=600, end=680, slot='lunch', size='full')])
    assert A.v18_day_end_reasons(old, plan(state='FULL', reason='배부름'), acts, prior, SHOWN, 1071), 'a meal 6.5 hours ago is not'
    # first attempts are always reviewed; tired customers close the day at once
    assert A.v18_day_end_reasons(a, told, acts, None, SHOWN, 1071)
    assert A.v18_day_end_reasons(agent(fatigue=2.9), plan(), acts, None, SHOWN, 1071) == []


def test_need_split_engine_estimate_and_mapping():
    meal = lambda since, eq, n=2: dict(date='2026-11-05', status='EXECUTED_SIMULATED_ORDER', period='dinner', venue='PIZZA_HILL', minutes_since_end=since,
                                       order=[dict(label='콤비네이션 피자 L', quantity=1)], party_size=n, portion_model=dict(meal_equivalents=eq, party_size=n))
    est = lambda since, eq: A.engine_need_estimate([meal(since, eq)], '2026-11-05', 1200)
    assert est(0, 3)['modeled_satiety'] == 'FULL_LIKELY' and est(0, 3)['per_diner_meal_equivalents'] == 1.5
    assert est(200, 3)['modeled_satiety'] == 'SATISFIED_LIKELY' and est(400, 3)['modeled_satiety'] == 'HUNGRY_LIKELY'
    assert est(30, 1)['modeled_satiety'] == 'SATISFIED_LIKELY', 'a small order is not full'
    assert est(30, None)['confidence'] == 'LOW'
    none = A.engine_need_estimate([], '2026-11-05', 1071)
    assert none['modeled_satiety'] == 'HUNGRY_LIKELY' and none['confidence'] == 'LOW' and 'PRE_ARRIVAL_INTAKE_UNKNOWN' in none['basis']
    nm = A.need_model(dict(meal_experiences=[meal(0, 3)], visit=dict(date='2026-11-05')), 1175)
    assert nm['observed']['actual_intake'] == 'NOT_OBSERVED' and 'NOT_INTAKE' in nm['engine_estimate']['basis']
    sch = A.SELECTION_V18N['properties']
    assert 'current_need_assessment' not in sch and 'UNCERTAIN' not in sch['need_estimate']['properties']['modeled_state']['enum']
    assert sch['need_estimate']['properties']['confidence']['enum'] == ['LOW', 'MEDIUM', 'HIGH']
    assert A.need_to_assessment(dict(modeled_state='FULL', confidence='LOW', reason='r'))['state'] == 'FULL'
    assert '신뢰도 LOW' in A.need_to_assessment(dict(modeled_state='FULL', confidence='LOW', reason='r'))['reason']
    # N's prompt differs from C's only in the intake line and one output line
    c, n = A.SYSTEM_V18.split('\n'), A.SYSTEM_V18N.split('\n')
    assert len(n) == len(c) + 1 and [x for x in c if x not in n] == [A.INTAKE_LINE] and A.NEED_LINE in n
    # a LOW-confidence FULL does not bypass the review (the basis rule applies to N as well)
    a = agent(fatigue=0.3); prior = dict(reason='EARLY_DAY_END_WITHOUT_EVENING_MEAL_REVIEW: ...')
    p = plan(state='FULL', reason='포만 추정'); p['need_estimate'] = dict(modeled_state='FULL', confidence='LOW', reason='포만 추정', differs_from_engine_because='엔진과 다름')
    assert A.v18_day_end_reasons(a, p, actions(), prior, SHOWN, 1071)


def test_expand_selection_keeps_need_estimate():
    rows = [dict(action_id='library', type='ACTIVITY', m4={})]
    acts = actions(meal=False)
    sel = dict(selected_action_id='library', selected_basket_id=None, reason='책', supporting_fact_ids=[], counterevidence_fact_ids=[],
               rejected_alternative=dict(action_id='', reason=''), next_intent=None, meal_assessment=None,
               need_estimate=dict(modeled_state='SATISFIED', confidence='MEDIUM', basis=['ENGINE_ESTIMATE'], differs_from_engine_because=None, reason='식후'))
    p, _ = A.expand_selection(sel, rows, acts, {})
    assert p['need_estimate']['confidence'] == 'MEDIUM' and p['current_need_assessment']['state'] == 'COMFORTABLE'


def lean_input():
    personal = dict(citable_fact_ids=['F1', 'F2'], coverage={'x': 1}, evidence_policy='P', evidence_boundary='B', evidence_status='S',
                    evidence_grades={'F1': [dict(facet='food', grade='rep')]},
                    evidence_records=[dict(fact_ids=['F1'], summary='피자를 먹었다.', source_scope='wh', actor='UNCONFIRMED', provenance_groups=['g']),
                                      dict(fact_ids=['F2'], summary='룸서비스가 비쌌다.', source_scope='other', actor='UNCONFIRMED')],
                    profile=dict(customer_type='미식', summary='요약', review_confirmed=dict(counterexamples=[dict(fact_ids=['F2'], what='비싼 룸서비스')]),
                                 profile_inference=dict(behavior_hypotheses=[])),
                    evidence_scope=dict(mode='CANDIDATE_RELATED_EVIDENCE', sent_fact_count=2, full_fact_count=9, unsent_fact_count=7, note='n', selection_reasons={'F1': ['X']}))
    opts = [dict(basket_id='meal:P#%d' % i, label='피자 %d' % i, total_krw=60000 + i, meal_equivalents=2, price_status='MODEL', marks=[], experience_fact_ids=[],
                 items=[dict(label='피자 %d' % i, quantity=1, unit_price_krw=60000 + i)]) for i in range(12)]
    return dict(personal=personal, visit=dict(date='2026-11-05', party_size=2, scenario={'big': 'x' * 500}),
                activity_experiences=[dict(date='2026-11-05', label='도착', start_time='16:30', end_time='16:45', satisfaction='NOT_OBSERVED')],
                meal_experiences=[], reassessment=dict(recent_decisions=[]), memory=dict(pending_intentions=[]),
                state=dict(time='17:51', recent_actions=[1, 2], meal_history=[], fatigue_scale=dict(level='여유', ratio_percent=4, basis='b'), meals={}, today_remaining=dict(basis='b', minutes_left=309)),
                candidates=[dict(action_id='meal:P', type='MEAL', label='피자', basket_note='n' * 300, conditions=dict(start_time='18:05', price_krw=None, price_status='UNKNOWN', basis='b'),
                                 m4=dict(rank_in_type=1, of=4, shown_because='TOP', direct_evidence_fact_ids=['F1'], similar_elsewhere_fact_ids=['F2'], trait_terms=[1], meaning='m'),
                                 basket_groups=[dict(label='피자', role='MEAL', shown_because='EXPERIENCE_ITEM', experience_fact_ids=['F1'], options=opts)]),
                            dict(action_id='end_day_in_room', type='DAY_END', label='마무리', scope='CLOSES_TODAY', conditions=dict(start_time='17:51'), m4=dict(rank_in_type=1, of=1))],
                shortlist=dict(candidate_count=20, shown=2, dropped=[{'a': 1}] * 12, meaning='m', policy='p'))


def test_lean_context_keeps_every_choice_input():
    full = lean_input(); lean = A.lean_context(copy.deepcopy(full))
    opts = lean['candidates'][0]['basket_groups'][0]['options']
    assert len(opts) == 12 and opts[3] == dict(basket_id='meal:P#3', label='피자 3', total_krw=60003, meal_equivalents=2, items=[dict(label='피자 3', quantity=1)])
    assert lean['personal']['records'] == [dict(fact_ids=['F1'], summary='피자를 먹었다.', source_scope='wh'), dict(fact_ids=['F2'], summary='룸서비스가 비쌌다.', source_scope='other')]
    assert lean['personal']['profile']['counterexamples'] == [dict(fact_ids=['F2'], what='비싼 룸서비스')] and lean['personal']['citable_fact_ids'] == ['F1', 'F2']
    assert lean['candidates'][0]['m4']['similar_elsewhere_fact_ids'] == ['F2'] and 'trait_terms' not in lean['candidates'][0]['m4']
    assert lean['candidates'][0]['conditions'] == dict(start_time='18:05', price_krw=None, price_status='UNKNOWN'), 'an unknown price keeps its status'
    assert lean['candidates'][1]['scope'] == 'CLOSES_TODAY' and 'dropped' not in lean['shortlist'] and 'scenario' not in lean['visit']
    assert 'recent_actions' not in lean['state'] and lean['today']['actions'] == [dict(label='도착', start='16:30', end='16:45')]
    assert len(json.dumps(lean, ensure_ascii=False)) < 0.7 * len(json.dumps(full, ensure_ascii=False))


def test_lean_instructions_follow_the_decision_types():
    meal = A.lean_system([dict(type='MEAL'), dict(type='DAY_END')]); act = A.lean_system([dict(type='ACTIVITY'), dict(type='REST')])
    assert 'basket_groups' in meal and 'basket_groups' not in act and 'selected_basket_id는 null' in act
    assert 'meal_assessment는 null입니다.' in act and 'meal_assessment는 식사' in meal
    assert 'CLOSES_TODAY' in act and 'CLOSES_TODAY' not in A.lean_system([dict(type='ACTIVITY')])
    assert A.resolved_spec(A.POLICIES[A.POLICY_V18L], [dict(type='MEAL'), dict(type='DAY_END')])['system'] == meal


def test_followup_policies_leave_a_to_d_unchanged():
    assert A.V18_VARIANTS == (A.POLICY_V18, A.POLICY_V18B, A.POLICY_V18BM, A.POLICY_V18BD)
    assert A.POLICIES[A.POLICY_V18BM]['system'] == A.SYSTEM_V18 and A.POLICIES[A.POLICY_V18BM]['schema'] is A.SELECTION_V18
    n, l, c = (A.POLICIES[p] for p in (A.POLICY_V18N, A.POLICY_V18L, A.POLICY_V18BM))
    assert n['effort'] == l['effort'] == c['effort'] == 'medium' and n['prefix_message'] == l['prefix_message'] == 'personal'
    assert 'current_need_assessment' in A.SELECTION_V18['properties'], 'C keeps its schema'
    assert A.resolved_spec(c, []) is c


def test_compare_lean_detects_a_dropped_menu_option():
    def body(ctx):
        return dict(model='m', reasoning={'effort': 'medium'}, max_output_tokens=1, text={'x': 1},
                    input=[dict(role='system', content='s'), dict(role='user', content=json.dumps(dict(personal=ctx['personal']), ensure_ascii=False)),
                           dict(role='user', content=json.dumps({k: v for k, v in ctx.items() if k != 'personal'}, ensure_ascii=False))])
    full = lean_input(); lean = A.lean_context(copy.deepcopy(full))
    assert RD.compare_lean(body(full), body(lean))['verdict'] == 'LEAN_PRESERVES_CHOICE_INPUTS'
    lean['candidates'][0]['basket_groups'][0]['options'].pop()
    res = RD.compare_lean(body(full), body(lean))
    assert res['verdict'] == 'LEAN_DROPPED_CHOICE_INPUTS' and res['checks']['menu_options_same'] is False


def test_neutral_presentation_removes_score_cues_only():
    full = lean_input()
    full['candidates'][0]['basket_groups'][0]['options'][5]['marks'] = ['최저가(인원 충족)', '인원에 맞춘 세트']
    full['candidates'][0]['basket_groups'][0]['options'][7]['marks'] = ['직접 경험 메뉴']
    s = A.neutral_presentation(copy.deepcopy(full))
    meal = next(x for x in s['candidates'] if x['type'] == 'MEAL')
    assert 'rank_in_type' not in meal['m4'] and 'of' not in meal['m4'] and meal['m4']['direct_evidence_fact_ids'] == ['F1']
    opts = meal['basket_groups'][0]['options']
    assert [o['total_krw'] for o in opts] == sorted(o['total_krw'] for o in opts), 'options by price, a transparent order'
    marks = [m for o in opts for m in o.get('marks', [])]
    assert marks == ['인원에 맞춘 세트'], 'only composition facts stay as marks'
    assert meal['basket_groups'][0]['experience_fact_ids'] == ['F1'], 'the group experience link stays'
    assert {o['basket_id'] for o in opts} == {o['basket_id'] for o in full['candidates'][0]['basket_groups'][0]['options']}
    assert [x['type'] for x in s['candidates']] == ['MEAL', 'DAY_END'] and s['personal'] == full['personal']
    c, n = A.SYSTEM_V18.split('\n'), A.SYSTEM_V18S.split('\n')
    assert len(c) == len(n) and sum(a != b for a, b in zip(c, n)) == 1 and 'rank_in_type' not in A.SYSTEM_V18S
    assert A.POLICIES[A.POLICY_V18S]['effort'] == 'medium' and A.POLICIES[A.POLICY_V18S]['schema'] is A.SELECTION_V18


def _body(system, ctx):
    return dict(model='m', reasoning={'effort': 'medium'}, max_output_tokens=1, text={'x': 1},
                input=[dict(role='system', content=system), dict(role='user', content=json.dumps(dict(personal=ctx['personal']), ensure_ascii=False)),
                       dict(role='user', content=json.dumps({k: v for k, v in ctx.items() if k != 'personal'}, ensure_ascii=False))])


def test_s2_orders_by_kind_and_name_not_price_or_score():
    full = lean_input()
    meal = full['candidates'][0]
    meal['m4']['shown_because'] = 'M4_TOP_OF_TYPE'
    g = meal['basket_groups'][0]; g['shown_because'] = 'PRICE_CHECK_CHEAPEST_ADEQUATE'
    g['options'].reverse(); g['options'][0]['marks'] = ['최저가(인원 충족)', '인원에 맞춘 세트']
    meal['basket_groups'].insert(0, dict(label='코스·세트', role='MEAL', shown_because='EXPERIENCE_FORMAT', experience_fact_ids=['F1'],
                                         options=[dict(basket_id='meal:P#99', label='코스', total_krw=300000, items=[])]))
    s2 = A.neutral_presentation(copy.deepcopy(full), 'NAME')
    m = next(x for x in s2['candidates'] if x['type'] == 'MEAL')
    assert m['m4']['shown_because'] == A.NEUTRAL_CANDIDATE_REASON and 'rank_in_type' not in m['m4']
    labels = [x['label'] for x in m['basket_groups']]
    assert labels == sorted(labels), 'groups by composition label'
    pizza = next(x for x in m['basket_groups'] if x['label'] != '코스·세트')
    assert pizza['shown_because'] == A.NEUTRAL_GROUP_REASON
    assert next(x for x in m['basket_groups'] if x['label'] == '코스·세트')['shown_because'] == 'EXPERIENCE_FORMAT', 'evidence reasons stay'
    names = [o['label'] for o in pizza['options']]
    assert names == sorted(names) and [o['total_krw'] for o in pizza['options']] != sorted(o['total_krw'] for o in pizza['options'])
    assert sorted(o['basket_id'] for o in pizza['options']) == sorted(o['basket_id'] for o in full['candidates'][0]['basket_groups'][1]['options'])
    assert all(o['total_krw'] for o in pizza['options']), 'prices are kept'
    assert [mk for o in pizza['options'] for mk in o.get('marks', [])] == ['인원에 맞춘 세트']
    # S (price order) is unchanged by the S2 option
    assert A.neutral_presentation(copy.deepcopy(full)) == A.neutral_presentation(copy.deepcopy(full), 'PRICE')
    assert A.POLICIES[A.POLICY_V18S2]['neutral'] == 'NAME' and A.POLICY_V18S2 in A.V18_FOLLOWUPS
    c, n = A.SYSTEM_V18.split('\n'), A.SYSTEM_V18S2.split('\n')
    assert len(c) == len(n) and sum(a != b for a, b in zip(c, n)) == 1
    # the exact request check: S2 = transform(C) + one system line; anything else is unintended
    ok = RD.compare_transformed(_body(A.SYSTEM_V18, full), _body(A.SYSTEM_V18S2, s2), lambda x: A.neutral_presentation(x, 'NAME'), 'C<->S2', 'm')
    assert ok['verdict'] == 'ONLY_INTENDED_DIFFERENCES' and ok['system_lines_changed'] == 1
    bad = copy.deepcopy(s2); bad['visit'] = dict(bad['visit'], party_size=3)
    assert RD.compare_transformed(_body(A.SYSTEM_V18, full), _body(A.SYSTEM_V18S2, bad), lambda x: A.neutral_presentation(x, 'NAME'), 'C<->S2', 'm')['verdict'] == 'UNINTENDED_DIFFERENCES'


def test_l_l2_pair_allows_only_the_personal_block():
    full = lean_input(); l2 = copy.deepcopy(full)
    l2['personal']['evidence_records'].append(dict(fact_ids=['F3'], summary='기념일 코스를 먹었다.', source_scope='other', actor='UNCONFIRMED'))
    assert RD.compare(_body('s', full), _body('s', l2), ('L', 'L2'))['verdict'] == 'ONLY_INTENDED_DIFFERENCES'
    l2['visit'] = dict(l2['visit'], party_size=3)
    assert RD.compare(_body('s', full), _body('s', l2), ('L', 'L2'))['verdict'] == 'UNINTENDED_DIFFERENCES'


from operator_choice.autonomy_v1 import m4_shortlist as MS  # noqa: E402
from operator_choice.autonomy_v1 import compact_question as CQ  # noqa: E402


def _venue(venue, labels_tags):
    return dict(venue=venue, _quotes=[dict(label=l, components=[dict(tags=t)]) for l, t in labels_tags])


SIG_RECORDS = [dict(fact_ids=['G1'], summary='명월관 한우 정식을 호평했다.', source_scope='wh'),
               dict(fact_ids=['G2'], summary='다른 호텔에서 와규 스테이크와 고기를 만족스럽게 먹었다.', source_scope='other'),
               dict(fact_ids=['G3'], summary='여수 숙소 예약 기회를 놓쳤다.', source_scope='other'),
               dict(fact_ids=['G4'], summary='코스트코에서 와인을 샀다.', source_scope='other'),
               dict(fact_ids=['G5'], summary='결혼기념일에 13코스 디너를 먹었다.', source_scope='other'),
               dict(fact_ids=['G6'], summary='GLC 시승 뒤 가격 문제로 차를 바꿨다.', source_scope='other')]


def test_personal_meal_signal_reads_meaning_not_exact_names():
    a = agent(); cite = [f'G{i}' for i in range(1, 7)]
    myeong = MS.personal_meal_signal(a, 'meal:MYONGWOLGWAN', _venue('MYONGWOLGWAN', [('한우 양념갈비 정식', ['beef', 'korean'])]), SIG_RECORDS, cite)
    assert myeong['fact_ids']['venue'] == ['G1'] and 'G2' in myeong['fact_ids']['kind'], 'a meat meal elsewhere relates to a beef venue'
    assert 'G5' in myeong['fact_ids']['format'] and 'G4' not in sum(myeong['fact_ids'].values(), []), '코스 (course) yes, 코스트코 no'
    moegi = MS.personal_meal_signal(a, 'meal:MOEGI', _venue('MOEGI', [('가케우동', ['japanese', 'noodles'])]), SIG_RECORDS, cite)
    assert 'G3' not in sum(moegi['fact_ids'].values(), []), "one-syllable '회' in 기회 is not sashimi"


def test_topic_reasons_add_occasion_and_dining_price_but_not_unrelated_price():
    a = agent(); personal = dict(citable_fact_ids=[f'G{i}' for i in range(1, 7)], evidence_records=SIG_RECORDS,
                                 evidence_grades={'G2': [dict(facet='value_check', grade='rep')], 'G6': [dict(facet='value_check', grade='rep')]})
    rows = [dict(action_id='meal:MYONGWOLGWAN', type='MEAL')]
    acts = {'meal:MYONGWOLGWAN': _venue('MYONGWOLGWAN', [('한우 양념갈비 정식', ['beef', 'korean'])])}
    why = CQ.topic_reasons(a, rows, personal, acts, dict(purpose=dict(value='anniversary')))
    assert 'OCCASION_MEAL' in why['G5'] and 'PRICE_OBSERVED_IN_DINING' in why['G2'] and 'G6' not in why, 'a car price record never enters a dinner question'
    assert 'OCCASION_MEAL' not in CQ.topic_reasons(a, rows, personal, acts, dict(purpose=dict(value='UNKNOWN'))).get('G5', set())
    assert CQ.topic_reasons(a, [dict(action_id='library', type='ACTIVITY')], personal, acts, {}) == {}


EVAL_RECORDS = [dict(fact_ids=['E1'], summary='명월관 한우 정식을 먹고 고기를 호평했다.', source_scope='wh'),
                dict(fact_ids=['E2'], summary='더뷔페 조식은 이용하지 않고 외부에서 먹었다.', source_scope='wh'),
                dict(fact_ids=['E3'], summary='5년 만에 같은 고깃집을 다시 찾아 고기에 만족했다.', source_scope='other'),
                dict(fact_ids=['E4'], summary='포함된 조식에서 한식을 먹고 객실에서 조망을 즐겼다.', source_scope='other')]


def _eval_agent(**over):
    a = agent(**over)
    a.traits = dict(menu=[dict(tags=['beef', 'korean'], weight=1.0, fact_ids=['E1'])],
                    facets=dict(routine=dict(evidence=[dict(fact_id=f, grade='rep', tags=['repeat']) for f in ('E2', 'E3', 'E4')])))
    return a


def test_relevance_is_not_preference_only_settled_evaluations_rank():
    a = _eval_agent(); cite = ['E1', 'E2', 'E3', 'E4']
    beef = _venue('MYONGWOLGWAN', [('한우 양념갈비 정식', ['beef', 'korean'])])
    m = MS.personal_meal_signal(a, 'meal:MYONGWOLGWAN', beef, EVAL_RECORDS, cite)
    assert m['confirmed_positive'] == ['E1', 'E3'], 'structured praise + a repeat visit about the same food kind'
    assert 'E4' not in m['confirmed_positive'], 'a breakfast-only repeat does not speak for dinner'
    buffet = MS.personal_meal_signal(a, 'meal:THE_BUFFET', _venue('THE_BUFFET', [('디너 뷔페', ['buffet'])]), EVAL_RECORDS, cite)
    assert 'E2' in buffet['fact_ids']['venue'] and buffet['confirmed_positive'] == [] and buffet['confirmed_negative'] == []
    assert buffet['unclassified'] == ['E2'], 'a non-use mention stays related/unclassified: neither preference nor dislike'
    neg = _eval_agent(); neg.traits['menu'] = [dict(tags=['beef'], weight=-1.0, fact_ids=['E1'])]
    n = MS.personal_meal_signal(neg, 'meal:MYONGWOLGWAN', beef, EVAL_RECORDS, cite)
    assert 'E1' in n['confirmed_negative'] and 'E1' not in n['confirmed_positive']


def test_personal_first_keeps_c_diversity_and_only_moves_settled_positives(monkeypatch):
    from test_v18_shortlist_selection_1105 import fake_engine_score
    monkeypatch.setattr(MS, 'engine_score', fake_engine_score)
    acts = actions(); recs = [dict(fact_ids=['T-F03'], summary='피자힐 콰트로 피자를 포장해 객실에서 나눠 먹었다.', source_scope='wh')]
    cite = ['T-F03', 'T-F07', 'T-F93']
    plain = _eval_agent(); plain.traits = {'facets': {}}
    c_rows, _ = MS.build(plain, {}, 1071, acts, {}, {}, citable=cite, records=recs)
    p_rows, p_tr = MS.build(plain, {}, 1071, acts, {}, {}, citable=cite, records=recs, selection=MS.PERSONAL_FIRST)
    assert [r['action_id'] for r in c_rows] == [r['action_id'] for r in p_rows], 'mentions alone give no priority: P == C'
    assert all(v['tier'] == 0 for v in p_tr['personal_signal'].values())
    liked = _eval_agent(); liked.traits = dict(menu=[dict(tags=['korean'], weight=1.0, fact_ids=['T-F93'])], facets={})
    l_rows, l_tr = MS.build(liked, {}, 1071, acts, {}, {}, citable=cite, records=recs + [dict(fact_ids=['T-F93'], summary='온달 한식 코스를 호평했다.', source_scope='wh')], selection=MS.PERSONAL_FIRST)
    meals = [r['action_id'] for r in l_rows if r['type'] == 'MEAL']
    assert l_tr['personal_signal']['meal:ONDAL']['tier'] == 2 and l_tr['shown_because']['meal:ONDAL'].startswith('CONFIRMED_POSITIVE_FIRST')
    assert 'meal:PIZZA_HILL' in meals, 'the other venue is still shown'


def test_topic_eating_experience_keeps_external_meals_but_not_breakfast_only_or_shopping():
    a = agent(); recs = [dict(fact_ids=['X1'], summary='다른 호텔 레스토랑에서 저녁 코스를 먹었다.', source_scope='other'),
                         dict(fact_ids=['X2'], summary='조식은 객실에서 간단히 먹었다.', source_scope='other'),
                         dict(fact_ids=['X3'], summary='셀러에서 와인을 구매했다.', source_scope='other')]
    personal = dict(citable_fact_ids=['X1', 'X2', 'X3'], evidence_records=recs, evidence_grades={})
    acts = {'meal:PIZZA_HILL': _venue('PIZZA_HILL', [('피자', ['pizza'])])}
    why = CQ.topic_reasons(a, [dict(action_id='meal:PIZZA_HILL', type='MEAL')], personal, acts, {})
    assert 'EATING_EXPERIENCE' in why.get('X1', set()) and 'X2' not in why and 'X3' not in why


def test_m_policy_leaves_quantity_to_the_engine():
    props = A.SELECTION_V18M['properties']['meal_assessment']['anyOf'][0]['properties']
    assert 'quantity_reason' not in props and {'kind', 'modeled_diners', 'sharing_plan', 'expected_satiety'} <= set(props)
    assert A.SYSTEM_V18M.split('응답 작성:')[0] == A.SYSTEM_V18.split('응답 작성:')[0]
    trace = dict(fit={'meal:PIZZA_HILL': dict(basket_index={'meal:PIZZA_HILL#1': dict(sku_id='P1', label='피자', total_krw=69000, items=[dict(sku_id='P1', quantity=1)])})})
    rows = [dict(action_id='meal:PIZZA_HILL', type='MEAL', basket_groups=[dict(label='피자', role='MEAL', options=[dict(basket_id='meal:PIZZA_HILL#1')])])]
    sel = dict(selected_action_id='meal:PIZZA_HILL', selected_basket_id='meal:PIZZA_HILL#1', reason='피자', supporting_fact_ids=[], counterevidence_fact_ids=[],
               rejected_alternative=dict(action_id='', reason=''), next_intent=None, current_need_assessment=dict(state='HUNGRY', reason='r'),
               meal_assessment=dict(kind='FULL_MEAL', modeled_diners=2, sharing_plan='나눔', expected_satiety='COMFORTABLE'))
    plan, _ = A.expand_selection(sel, rows, {'meal:PIZZA_HILL': dict(execution='MEAL')}, {}, trace)
    assert plan['meal_assessment']['quantity_reason'] == A.ENGINE_QUANTITY_NOTE
    A.X.validate_assessment(plan, 2, True)


def test_followup_policies_registered_one_change_each():
    for p in (A.POLICY_V18P, A.POLICY_V18L2, A.POLICY_V18M):
        assert p in A.POLICIES and p not in A.V18_VARIANTS and A.POLICIES[p]['effort'] == 'medium'
    assert A.POLICIES[A.POLICY_V18P]['shortlist'] == MS.PERSONAL_FIRST and A.POLICIES[A.POLICY_V18P]['system'] == A.SYSTEM_V18
    assert A.POLICIES[A.POLICY_V18L2]['topic'] and A.POLICIES[A.POLICY_V18L2]['context'] == A.POLICIES[A.POLICY_V18L]['context']


def test_ls_is_l2_evidence_with_s2_presentation_and_leaves_others_unchanged():
    ls, l2, s2 = A.POLICIES[A.POLICY_V18LS], A.POLICIES[A.POLICY_V18L2], A.POLICIES[A.POLICY_V18S2]
    assert ls['topic'] and ls['neutral'] == 'NAME' and ls['context'] == l2['context'] and ls['effort'] == l2['effort'] == s2['effort']
    assert ls['schema'] is l2['schema'] and A.POLICY_V18LS in A.V18_FOLLOWUPS
    assert 'neutral' not in l2 and 'topic' not in s2, 'L2 and S2 are not changed by LS'
    rows = [dict(type='MEAL'), dict(type='REST')]
    a, b = A.lean_system(rows).split('\n'), A.lean_neutral_system(rows).split('\n')
    assert len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1 and A.RANK_SENTENCE not in '\n'.join(b)


def test_evidence_check_lists_unsent_records_naming_a_shown_restaurant():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools' / 'v18_bench'))
    import evidence_check as EC
    personal = dict(citable_fact_ids=['X1', 'X2', 'X3', 'X4'], evidence_records=[
        dict(fact_ids=['X1'], summary='피자힐에서 좌석이 마음에 들지 않아 먹지 않고 나왔다', source_scope='UNRESOLVED'),
        dict(fact_ids=['X2'], summary='다른 호텔 룸서비스를 먹었다', source_scope='other'),
        dict(fact_ids=['X3'], summary='명월관 한우를 호평했다', source_scope='wh'),
        dict(fact_ids=['X4'], summary='다른 호텔의 피자힐 같은 가게', source_scope='other')])
    rows = [dict(action_id='meal:PIZZA_HILL', type='MEAL'), dict(action_id='meal:MYONGWOLGWAN', type='MEAL'), dict(action_id='meal:ROOM_MEAL', type='MEAL')]
    miss = EC.unsent(personal, rows, ['X3'], MS.venue_names)
    assert miss == {'meal:PIZZA_HILL': [dict(fact_ids=['X1'], source_scope='UNRESOLVED')]}, 'unresolved-scope record naming the venue is flagged; other hotels and generic room service are not'
    assert EC.unsent(personal, rows, ['X1', 'X3'], MS.venue_names) == {}
