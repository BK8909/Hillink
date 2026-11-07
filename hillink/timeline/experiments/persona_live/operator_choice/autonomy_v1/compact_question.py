"""V18 question-design variants: send only the evidence the current candidates need.

Variant A sends the full persona block (`personal`; A07: 90 records). Variants B/C/D send the SAME
block — same keys, same nesting, same message position — filtered to the Fact ids tied to the shown
candidates:
- review records tied to a shown candidate (experience links of restaurants and activities, the Fact
  ids the engine coefficients used, records that mention a shown restaurant/activity by name — kept
  whatever their polarity, so counter-experiences stay), plus at most FACETS_PER_TRAIT graded records
  per trait the shown candidates read;
- profile: the same nesting; evidence items keep only sent ids; persona-level inferences without Fact
  ids (hypotheses, judgment patterns) are left out (their lists stay, empty);
- evidence_scope (in A and B alike) says which it is, how many ids were sent and why each was chosen.
Every other block of the request is identical between A and B. Only sent ids are citable. When
nothing relevant exists the block says so, and the model decides from the situation without
inventing a personal preference.

Nothing here truncates text: a record is either sent whole or recorded as not sent, with the reason,
so coverage and loss can be compared per candidate.
"""
import copy
import re

from . import agent_day as AD
from . import m4_shortlist as MS

POLICY = 'CANDIDATE_CENTRED_EVIDENCE_V1'
FACETS_PER_TRAIT = 2
BREAKFAST_RX = r'조식|아침|breakfast|모닝'


def _records(personal):
    return personal.get('evidence_records') or []


def _activity_rx(code):
    return AD.SP.EV_RE.get(code) if hasattr(AD.SP, 'EV_RE') else None


SCOPE_FULL = 'FULL_PERSONA_EVIDENCE'
SCOPE_CANDIDATE = 'CANDIDATE_RELATED_EVIDENCE'
NOTE_FULL = '이 고객의 후기 근거 전체입니다. 이번 후보와 관련 없는 기록도 들어 있습니다.'
NOTE_CANDIDATE = ('이번 후보와 관련된 후기 기록만 골라 보낸 것입니다. 보내지 않은 기록을 없었던 사실로 해석하지 마세요. '
                  '관련 기록이 없으면 동행·시간·허기·피로·환경으로 일반적인 상황 판단을 하고, 개인 취향으로 설명하지 마세요.')


def evidence_scope(mode, personal, sent, reasons=None):
    """The one field that says how much of the persona block was sent. A and B carry it with the
    same keys; only its values differ."""
    full = set(personal.get('citable_fact_ids') or [])
    return dict(mode=mode, sent_fact_count=len(sent), full_fact_count=len(full), unsent_fact_count=len(full - set(sent)),
                note=NOTE_FULL if mode == SCOPE_FULL else NOTE_CANDIDATE,
                selection_reasons={f: sorted(v) for f, v in sorted((reasons or {}).items()) if f in sent})


def with_full_scope(personal):
    """Variant A: the full persona block, unchanged, plus evidence_scope."""
    return dict(personal, evidence_scope=evidence_scope(SCOPE_FULL, personal, set(personal.get('citable_fact_ids') or [])))


def _keep_sent(x, sent):
    """Same nesting as the persona block; list items that are evidence (carry fact_ids) are kept only
    when one of their ids was sent, and then with only the sent ids. Persona-level inferences without
    fact ids (hypotheses, judgment patterns) are not candidate evidence and are left out of B."""
    if isinstance(x, list):
        out = []
        for v in x:
            if isinstance(v, dict):
                ids = [f for f in (v.get('fact_ids') or []) if f in sent]
                if not ids: continue
                v = {k: (ids if k == 'fact_ids' else _keep_sent(w, sent)) for k, w in v.items()}
            out.append(v)
        return out
    if isinstance(x, dict):
        return {k: (_keep_sent(v, sent) if isinstance(v, (list, dict)) else v) for k, v in x.items()}
    return x


def filtered_personal(personal, sent, reasons):
    """Variant B's persona block: every key of variant A's block, same structure, filtered to the sent
    Fact ids. Policy/boundary/status/coverage texts are copied as they are."""
    out = {}
    for k, v in personal.items():
        if k == 'citable_fact_ids': out[k] = sorted(f for f in v if f in sent)
        elif k == 'evidence_grades': out[k] = {f: g for f, g in v.items() if f in sent}
        elif k == 'evidence_records':
            out[k] = []
            for r in v:
                ids = [f for f in r['fact_ids'] if f in sent]
                if not ids: continue
                r = dict(r, fact_ids=ids)
                if isinstance(r.get('grade_by_fact'), dict): r['grade_by_fact'] = {f: g for f, g in r['grade_by_fact'].items() if f in sent}
                out[k].append(r)
        elif k == 'profile': out[k] = _keep_sent(v, sent)
        else: out[k] = copy.deepcopy(v)
    out['evidence_scope'] = evidence_scope(SCOPE_CANDIDATE, personal, sent, reasons)
    return out


def candidate_links(row, trace, personal, a):
    """Fact ids the shortlist tied to one shown candidate, by reason (rule outputs, not preferences)."""
    m4 = row.get('m4') or {}
    links = {}
    def add(ids, why):
        for f in ids or []: links.setdefault(f, set()).add(why)
    add(m4.get('direct_evidence_fact_ids'), 'EXPERIENCE_HERE')
    add(m4.get('similar_elsewhere_fact_ids'), 'SIMILAR_ELSEWHERE')
    add(m4.get('scope_unconfirmed_fact_ids'), 'SCOPE_UNCONFIRMED')
    add(m4.get('evidence_fact_ids'), 'ENGINE_COEFFICIENT_EVIDENCE')
    for g in row.get('basket_groups') or []:
        add(g.get('experience_fact_ids'), 'MENU_EXPERIENCE')
        for o in g.get('options') or []: add(o.get('experience_fact_ids'), 'MENU_EXPERIENCE')
    fit = ((trace or {}).get('fit') or {}).get(row['action_id']) or {}
    # records naming the restaurant or the activity, any polarity (counter-experiences included)
    names = []
    if row.get('type') == 'MEAL':
        venue = row['action_id'].split(':', 1)[1]
        names = MS.venue_names(venue)
    code = MS.native_code(row['action_id'], dict(execution='CONTRACT_ACTIVITY' if row['action_id'].startswith('activity:') else '', native_code=(row['action_id'].split(':')[1] if row['action_id'].startswith('activity:') else None)))
    rx = _activity_rx(code or row['action_id'])
    has_set = any(g.get('label') == '코스·세트' for g in row.get('basket_groups') or [])
    for r in _records(personal):
        text = str(r.get('summary') or '')
        ids = [f for f in r['fact_ids'] if f in personal['citable_fact_ids']]
        if (names and any(n in text for n in names) and r.get('source_scope') == 'wh') or (rx and re.search(rx, text)):
            add(ids, 'NAMES_THIS_OPTION')
        elif has_set and r.get('source_scope') == 'wh' and re.search(MS.FORMAT_RX, text, re.I):
            add(ids, 'ABOUT_THIS_COURSE_FORMAT')   # e.g. how the guest judged an omakase/course at this hotel
    return links


def trait_facts(rows, personal, decision):
    """At most FACETS_PER_TRAIT graded records per trait the shown candidates read (Walkerhill first)."""
    grades = personal.get('evidence_grades') or {}
    wanted = {t['trait'] for r in rows for t in (r.get('m4') or {}).get('trait_terms', [])}
    if decision == 'BREAKFAST': wanted |= {'breakfast_priority', 'practical_alt'}
    if any(r.get('type') == 'MEAL' for r in rows): wanted |= {'food', 'value_check', 'practical_alt'}
    scope = {f: r.get('source_scope') for r in _records(personal) for f in r['fact_ids']}
    out = {}
    for trait in sorted(wanted):
        ids = sorted([f for f, es in grades.items() if any(e.get('facet') == trait and e.get('grade') == 'rep' for e in es)],
                     key=lambda f: (scope.get(f) != 'wh', f))
        for f in ids[:FACETS_PER_TRAIT]: out.setdefault(f, set()).add('TRAIT:' + trait)
    return out


TOPIC_POLICY = 'DECISION_TOPIC_EVIDENCE_V1'
DINING_RX = r'식사|음식|메뉴|코스|오마카세|레스토랑|다이닝|조식|룸서비스|피자|스테이크|한우|고기|와인|맥주|뷔페|디저트|떡볶이|포장|맛'
OCCASION_RX = r'기념|생일|허니문|결혼|프러포즈|anniversary'
BREAKFAST_ONLY_RX = MS.BREAKFAST_ONLY_RX
OTHER_MEAL_RX = MS.OTHER_MEAL_RX
PURCHASE_ONLY_RX = r'샀|구매|셀러|마트|코스트코'
EATING_RX = r'먹|식사|맛|주문|이용'


def topic_reasons(a, rows, personal, actions, visit):
    """L2: the person's records that bear on THIS decision's topic, by meaning already in the data
    (not by exact name/SKU): for a meal, every food signal of each shown venue (the venue, a food kind
    or course format it sells, the in-room-meal pattern; m4_shortlist.personal_meal_signal), past
    special-occasion meals when this visit has a stated purpose, and price observations made about
    dining (never car, room-rate or shopping price records). Polarity stays for the model to read."""
    reasons = {}
    add = lambda ids, why: [reasons.setdefault(f, set()).add(why) for f in ids]
    citable = set(personal.get('citable_fact_ids') or [])
    meal_rows = [r for r in rows if r.get('type') == 'MEAL']
    for r in meal_rows:
        act = (actions or {}).get(r['action_id'])
        if not act: continue
        sig = MS.personal_meal_signal(a, r['action_id'], act, _records(personal), citable)
        for kind, ids in sig['fact_ids'].items(): add(ids, 'FOOD_SIGNAL:' + kind)
    if not meal_rows: return reasons
    purpose = (visit or {}).get('purpose')
    stated = isinstance(purpose, dict) and purpose.get('value') not in (None, '', 'UNKNOWN')
    grades = personal.get('evidence_grades') or {}
    breakfast = all(str(r.get('action_id', '')).upper().startswith('BREAKFAST') for r in meal_rows)
    for r in _records(personal):
        ids = [f for f in r['fact_ids'] if f in citable]
        text = str(r.get('summary') or '')
        if not ids or not re.search(DINING_RX, text): continue
        # the person's eating experiences are this decision's topic, wherever they happened; two exclusions only:
        # breakfast-only records for a lunch/dinner choice, and buying drinks/food to take home (shopping, not eating out)
        breakfast_only = re.search(BREAKFAST_ONLY_RX, text) and not re.search(OTHER_MEAL_RX, text)
        purchase_only = re.search(PURCHASE_ONLY_RX, text) and not re.search(EATING_RX, text)
        if not purchase_only and (breakfast or not breakfast_only): add(ids, 'EATING_EXPERIENCE')
        if stated and re.search(OCCASION_RX, text): add(ids, 'OCCASION_MEAL')
        if any(e.get('facet') in ('value_check', 'benefit') and e.get('grade') == 'rep' for f in ids for e in grades.get(f, [])):
            add(ids, 'PRICE_OBSERVED_IN_DINING')
    return reasons


def build(a, t, base, rows, trace, decision='ACTION', actions=None, topic=False):
    """Return (context, citable_fact_ids, coverage) for the compact variant."""
    personal = base['personal']; citable = set(personal.get('citable_fact_ids') or [])
    reasons = {}
    per_candidate = {}
    for row in rows:
        links = candidate_links(row, trace, personal, a)
        per_candidate[row['action_id']] = sorted(f for f in links if f in citable)
        for f, why in links.items():
            if f in citable: reasons.setdefault(f, set()).update(why)
    if decision == 'BREAKFAST':
        for r in _records(personal):
            if re.search(BREAKFAST_RX, str(r.get('summary') or '')):
                for f in r['fact_ids']:
                    if f in citable: reasons.setdefault(f, set()).add('NAMES_BREAKFAST')
    for f, why in trait_facts(rows, personal, decision).items():
        if f in citable: reasons.setdefault(f, set()).update(why)
    if topic:
        for f, why in topic_reasons(a, rows, personal, actions, base.get('visit')).items():
            if f in citable: reasons.setdefault(f, set()).update(why)
    sent = {f for r in _records(personal) for f in r['fact_ids'] if f in reasons}
    context = dict(base, personal=filtered_personal(personal, sent, reasons))
    context.setdefault('candidates', rows)
    unsent = sorted(citable - sent)
    coverage = dict(policy=TOPIC_POLICY if topic else POLICY, full_citable=len(citable), full_records=len(_records(personal)), sent_facts=len(sent),
                    sent_records=len(context['personal']['evidence_records']),
                    unsent=len(unsent), per_candidate=per_candidate,
                    candidate_links_sent={k: all(f in sent for f in v) for k, v in per_candidate.items()},
                    unsent_scope=dict(wh=sum(1 for r in _records(personal) if r.get('source_scope') == 'wh' and not set(r['fact_ids']) & sent),
                                      other=sum(1 for r in _records(personal) if r.get('source_scope') != 'wh' and not set(r['fact_ids']) & sent)),
                    reasons={f: sorted(v) for f, v in reasons.items()})
    return context, sorted(sent), coverage
