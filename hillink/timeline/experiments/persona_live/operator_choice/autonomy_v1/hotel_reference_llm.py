"""Research: LLM policy V19LS_HP1 — external delivery as a real dinner alternative + the hotel's delivery
statistic as low-priority general reference (never the default; V19LS is unchanged).

What changes against V19LS (and only for this policy):
  1. EXTERNAL_DELIVERY becomes a selectable dinner alternative for checked-in staying guests. The hotel does not
     sell it: price unknown, hotel revenue 0 (the ledger records it as external spend). V19LS excludes it
     (NONCATALOG_PURCHASE_QUOTE_NOT_CONNECTED), so V19LS customers can never choose delivery.
  2. When the research prior is ON with an applicable reference (same denominator: stay-team evenings), the
     request carries `hotel_reference`: what the number measures, its source class (hotel measured / external
     research / synthetic test), period and scope, and how it may be used. No score, coefficient or target is
     sent. The rule engine's 0.8 x share is not used in this policy.
  3. Personal evidence first: a customer with personal records about eating in the room, room service or
     delivery receives the block without the value (withheld, with the reason). The model also states in
     `hotel_reference_use` whether it used the reference and why.
Every decision records whether the reference was provided, withheld or not applicable, and why.
"""
import copy
import re

from . import hotel_prior as HP

DELIVERY = 'EXTERNAL_DELIVERY'
DELIVERY_LABEL = '외부 배달 · 객실에서 먹기 (호텔 밖 업체 · 결제 금액 미상 · 호텔 매출 아님)'
PERSONAL_TERMS = re.compile(r'배달|딜리버리|룸서비스|룸 서비스|객실에서 (먹|식사)|방에서 (먹|식사)|포장해|테이크아웃|시켜 먹|배민|요기요|쿠팡이츠')
CLASS_KO = {'HOTEL_MEASURED': '호텔 실측', 'EXTERNAL_RESEARCH': '외부 연구(이 호텔 실측 아님)', 'SYNTHETIC_TEST': '합성 테스트값(실측·연구 아님)'}

LINES = [
    'hotel_reference가 있으면 이 호텔 투숙객 집단의 저녁 외부 배달 경향을 요약한 일반 참고정보입니다. 개인 기록·반례·명시적 기피, 이번 방문의 동행·허기·피로·일정이 항상 우선합니다.',
    '그 비율을 이 고객의 확률이나 목표로 쓰지 말고, 집단 비율에 맞추려고 선택을 바꾸지 마세요. 개인 근거가 부족해 판단이 비슷할 때만 참고하세요. 출처 등급(호텔 실측·외부 연구·합성 테스트값)을 사실의 강도로 구분하세요.',
    '외부 배달 후보는 호텔이 파는 상품이 아니며 가격은 미확인입니다(무료가 아님). hotel_reference_use에 참고 여부와 이유를 한 문장으로 적고, hotel_reference가 없거나 값이 없으면 used=false로 적으세요.',
]


def schema(base):
    s = copy.deepcopy(base)
    s['properties']['hotel_reference_use'] = {'type': 'object', 'additionalProperties': False, 'required': ['used', 'reason'],
                                              'properties': {'used': {'type': 'boolean'}, 'reason': {'type': 'string'}}}
    s['required'] = sorted(s['properties'])
    return s


def personal_evidence(records):
    """Fact ids of records about eating in the room, room service or delivery (personal evidence first)."""
    return sorted({f for r in records or [] for f in r.get('fact_ids') or []
                   if PERSONAL_TERMS.search(' '.join([str(r.get('summary') or '')] + [str(x) for x in r.get('about') or []] + [str(x) for x in r.get('flags') or []]))})


def reference_block(rows, records):
    """(block for the request or None, trace). The block is only built when delivery is among the candidates."""
    cfg = HP.config()
    trace = dict(policy='V19LS_HP1', provided=False, value_sent=False)
    if not any(r['action_id'] == DELIVERY for r in rows):
        trace['reason'] = 'DELIVERY_NOT_A_CANDIDATE_AT_THIS_DECISION'; return None, trace
    if cfg is None:
        trace['reason'] = 'REFERENCE_OFF'; return None, trace
    trace.update(status=cfg.get('status'), reference_profile=cfg.get('reference_profile'),
                 files=[(f.get('source_set'), f.get('sha256')) for f in (cfg.get('provenance') or {}).get('files') or []])
    if cfg.get('status') != 'APPLICABLE':
        trace['reason'] = cfg.get('status') or 'NO_APPLICABLE_REFERENCE'; return None, trace
    ref = cfg['reference']
    block = dict(kind='HOTEL_GROUP_TENDENCY_GENERAL_REFERENCE', metric='숙박 팀·저녁 중 외부 배달로 저녁을 먹은 비율',
                 denominator='숙박 팀·저녁(체크아웃 날 제외)', source_class=CLASS_KO.get(ref['source_class'], ref['source_class']),
                 source_label=ref.get('synthetic_label') or ref.get('source_set'), period=ref.get('period'), segment=ref.get('segment'),
                 how_to_use='개인 근거가 부족할 때만 참고 · 개인 확률·목표 아님 · 이 고객의 기록과 현재 상태가 우선')
    own = personal_evidence(records)
    if own:
        block.update(value=None, withheld_reason='이 고객에게 객실 식사·룸서비스·배달 관련 개인 기록이 있어 집단 비율을 제공하지 않음', personal_fact_ids=own)
        trace.update(provided=True, value_sent=False, reason='PERSONAL_EVIDENCE_TAKES_PRECEDENCE', personal_fact_ids=own)
        return block, trace
    block['value'] = ref['value']
    trace.update(provided=True, value_sent=True, value=ref['value'], source_class=ref['source_class'], reason='NO_PERSONAL_EVIDENCE_REFERENCE_SENT')
    return block, trace


def delivery_row(a, t, actions, citable, MS):
    """The model row of the delivery alternative, added after the shortlist (outside the hotel venue cap) at dinner."""
    action = actions[DELIVERY]
    fit = MS.activity_fit(a, DELIVERY, action, citable)
    cond = dict(MS.execution_conditions(a, t, action), price_krw=None, price_status='EXTERNAL_PRICE_UNKNOWN_NOT_HOTEL_REVENUE')
    return dict(action_id=DELIVERY, type='ACTIVITY', label=DELIVERY_LABEL, location=action.get('location'), conditions=cond,
                m4=dict(rank_in_type=None, of=None, basis=fit.get('basis'), shown_because='HP1_EXTERNAL_DELIVERY_DINNER_ALTERNATIVE',
                        trait_terms=fit.get('trait_terms', []), evidence_fact_ids=fit.get('evidence_fact_ids', []),
                        direct_evidence_fact_ids=fit.get('direct_evidence_fact_ids', []), similar_elsewhere_fact_ids=fit.get('similar_elsewhere_fact_ids', []),
                        scope_unconfirmed_fact_ids=fit.get('scope_unconfirmed_fact_ids', []), meaning='RULE_FIT_FROM_TRAIT_COEFFICIENTS_NOT_VERIFIED_PREFERENCE'))


# ------------------------------------------------------------------ HP1b (2026-11-08): controlled comparison
# v20a found two control defects in HP1: (1) the reference lines and the hotel_reference_use field were sent even with
# the reference OFF, so A -> B0 mixed "delivery became a candidate" with "the prompt/schema changed"; (2) the delivery
# label showed operator information ("not hotel revenue") to the customer. HP1b keeps V19LS's system prompt and
# output schema unchanged in B0 and B alike; the only per-condition difference is the reference block itself, which
# carries its own meaning and scope. A synthetic value is framed as an explicit operating condition of the simulated
# hotel (never as a measurement or an observed outside fact).
DELIVERY_LABEL_B = '외부 배달 · 객실에서 받아 먹기 (호텔 밖 업체 · 가격 미확인)'
PRICE_STATUS_B = 'EXTERNAL_PRICE_UNKNOWN'
SCENARIO_KO = '가상 호텔 운영 시나리오 조건(이 시뮬레이션에서 설정한 값 · 실측이나 외부에서 관측된 사실 아님)'


def delivery_row_b(a, t, actions, citable, MS):
    """HP1b: the same row as HP1 without operator-only wording (label and price status)."""
    row = delivery_row(a, t, actions, citable, MS)
    row['label'] = DELIVERY_LABEL_B
    row['conditions']['price_status'] = PRICE_STATUS_B
    row['m4']['shown_because'] = 'HP1B_EXTERNAL_DELIVERY_DINNER_ALTERNATIVE'
    return row


def reference_block_b(rows, records):
    """(block or None, trace) for HP1b. Same gating and personal-evidence rule as HP1; the block explains itself."""
    cfg = HP.config()
    trace = dict(policy='V19LS_HP1B', provided=False, value_sent=False)
    if not any(r['action_id'] == DELIVERY for r in rows):
        trace['reason'] = 'DELIVERY_NOT_A_CANDIDATE_AT_THIS_DECISION'; return None, trace
    if cfg is None:
        trace['reason'] = 'REFERENCE_OFF'; return None, trace
    trace.update(status=cfg.get('status'), reference_profile=cfg.get('reference_profile'),
                 files=[(f.get('source_set'), f.get('sha256')) for f in (cfg.get('provenance') or {}).get('files') or []])
    if cfg.get('status') != 'APPLICABLE':
        trace['reason'] = cfg.get('status') or 'NO_APPLICABLE_REFERENCE'; return None, trace
    ref = cfg['reference']
    synthetic = ref['source_class'] == 'SYNTHETIC_TEST'
    block = dict(kind='SIMULATED_HOTEL_OPERATING_CONDITION' if synthetic else 'HOTEL_GROUP_TENDENCY_REFERENCE',
                 source=SCENARIO_KO if synthetic else CLASS_KO.get(ref['source_class'], ref['source_class']),
                 metric='이 호텔 숙박 팀의 저녁 중 외부 배달로 해결한 비율', denominator='숙박 팀·저녁(체크아웃 날 제외)',
                 period=None if synthetic else ref.get('period'), segment=ref.get('segment'),
                 how_to_use=('호텔 전체 투숙객의 경향이며 이 고객의 확률·목표가 아닙니다. 개인 기록·반례·명시적 기피, 이번 방문의 동행·허기·피로·일정보다 '
                             '낮은 우선순위입니다. 반드시 쓸 필요가 없고, 이 비율에 맞춰 선택할 필요도 없습니다. 외부 배달 가격은 확인되지 않았습니다.'))
    if synthetic:
        block['scenario_note'] = '이 시뮬레이션의 가상 호텔은 이 비율을 운영 조건으로 둡니다. 다른 호텔·실제 워커힐의 수치가 아닙니다.'
    own = personal_evidence(records)
    if own:
        block.update(value=None, withheld_reason='이 고객에게 객실 식사·룸서비스·배달 관련 개인 기록이 있어 비율을 제공하지 않음', personal_fact_ids=own)
        trace.update(provided=True, value_sent=False, reason='PERSONAL_EVIDENCE_TAKES_PRECEDENCE', personal_fact_ids=own)
        return block, trace
    block['value'] = ref['value']
    trace.update(provided=True, value_sent=True, value=ref['value'], source_class=ref['source_class'],
                 framing='SIMULATED_HOTEL_OPERATING_CONDITION' if synthetic else 'REFERENCE', reason='NO_PERSONAL_EVIDENCE_REFERENCE_SENT')
    return block, trace


def earlier_days(c, venue_ko):
    """HP1: what this customer did on the earlier days of this visit (executed simulation actions, not reports).
    V19LS's lean request sends only a count of earlier meals; a next-day choice could not see yesterday's dinner."""
    today = (c.get('visit') or {}).get('date')
    meals = [dict(date=m.get('date'), period=m.get('period'),
                  place='외부 배달' if m.get('venue') == DELIVERY else venue_ko.get(m.get('venue'), m.get('venue')),
                  order=[i.get('label') for i in (m.get('order') or [])][:4], hotel_revenue=m.get('venue') != DELIVERY)
             for m in c.get('meal_experiences') or [] if m.get('date') and m.get('date') != today]
    acts = [dict(date=x.get('date'), label=x.get('label')) for x in c.get('activity_experiences') or [] if x.get('date') and x.get('date') != today][-10:]
    return dict(meals=meals, activities=acts, status='EXECUTED_SIMULATION_ACTIONS_NOT_CUSTOMER_REPORTS')
