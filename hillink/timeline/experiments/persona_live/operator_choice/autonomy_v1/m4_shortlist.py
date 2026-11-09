"""V18 experiment: the M4 rule engine shortlists, the model selects.

The world (action_space) still decides what is possible. This module ranks the
validated candidates by the existing trait coefficients (stay_planner.act_weight
through agent_day.pace_w for activities, operator_world_v1.engine.score for meal
baskets and engine offers) together with the current state, then keeps a small
representative set across meal / activity / rest / day-end / leave so the model
reads 3~5 options instead of 20 venues x 140 baskets.

Rules of the shortlist:
- fit (trait coefficients + state) and execution conditions (schedule, wait,
  price, viability) are recorded separately; neither is a verified preference.
- ranking is within a type; types are not compared by score.
- end_day_in_room, leave_visit and the top meal while dinner is unresolved are
  never dropped by score. A rest option is always represented when one exists.
- every dropped candidate stays in the trace with its fit and the reason.
- a basket is an already quoted contract (HR.quote), so one basket id fixes the
  order; the model never composes SKUs under this policy.
"""
import os
import copy

from . import agent_day as AD
from . import hotel_runtime as HR

SHORTLIST_POLICY = 'M4_TRAIT_SHORTLIST_V4'   # V4: next slots prefer an unseen activity kind / meal mode; one candidate per sold contract; V3: basket groups by criteria (experience, score, price check, party set); experience links carry no polarity; rule scope narrowed
REST_KEYS = ('room_rest', 'ROOM_REST', 'public_rest', 'wait_reconsider', 'room_bath', 'room_nap', 'room_rest_long')
ALIAS = {'ROOM_REST': 'room_rest', 'FOREST_WALK': 'forest_walk', 'GARDEN_WALK': 'garden_walk', 'RIVERPARK': 'riverpark',
         'SKYARD': 'footbath', 'POOL': 'pool', 'SAUNA': 'sauna', 'FITNESS': 'fitness', 'LIBRARY': 'library', 'THEATRE': 'theatre'}
MAX_OPTIONS = 7          # measured (bench a07/n03): 5 hid 2/4 of N03's recorded choices; +2 candidates cost ~0.3KB each in the compact request. One more only when a further evidence-linked candidate would be hidden
MAX_BASKETS = 3
MAX_MEAL_VENUES = 3
MEAL_MODE = {'ROOM_MEAL': 'in_room', 'THE_PAVILION': 'casual', 'LE_PASSAGE': 'casual', 'LUX_BAR': 'casual', 'THE_BUFFET': 'buffet'}


def kind_of(key, action):
    ex = action.get('execution')
    if ex == 'MEAL': return 'MEAL'
    if ex == 'END_DAY': return 'DAY_END'
    if ex == 'LEAVE': return 'LEAVE'
    if ex == 'SKIP_MEAL': return 'SKIP_MEAL'
    if ex == 'CHECKOUT': return 'CHECKOUT'     # research CHECKOUT_PREP only
    if ex == 'DEFER_MEAL': return 'DEFER_MEAL'  # research MEAL_DEFER only
    if key in REST_KEYS or ex in ('REST', 'WAIT'): return 'REST'
    return 'ACTIVITY'


def native_code(key, action):
    if action.get('native_code'): return action['native_code']
    if action.get('execution') == 'PLAN' and key in AD.SP.ACT: return key
    if action.get('execution') == 'ENGINE':
        oid = (action.get('offer') or {}).get('id') or key
        code = ALIAS.get(oid, oid.lower())
        return code if code in AD.SP.ACT else None
    if key in AD.SP.ACT: return key
    return None


def _trait_terms(code, a):
    """Which bars/facets the existing coefficient table reads for this code (labels, not weights)."""
    src = {'pool': ['swim_aversion', 'active'], 'sauna': ['rest_need', 'warm_rest'], 'fitness': ['active'],
           'footbath': ['warm_rest', 'rest_need', 'space'], 'night_footbath': ['warm_rest', 'rest_need', 'space'],
           'forest_walk': ['space', 'active'], 'garden_walk': ['space', 'active'], 'riverpark': ['space', 'active'],
           'night_walk': ['space', 'active'], 'tennez': ['space', 'active'], 'cafe': ['food', 'food_specific', 'novelty'],
           'bakery': ['food', 'food_specific', 'value_check', 'practical_alt'], 'lounge': ['benefit', 'premium'],
           'library': ['rest_need'], 'theatre': ['novelty', 'space', 'premium'], 'room_rest': ['rest_need', 'warm_rest'],
           'room_nap': ['rest_need'], 'room_bath': ['rest_need', 'warm_rest'], 'luxbar': ['alcohol_familiar', 'alcohol_limit', 'space']}
    bars = a.P.get('bars') or {}; facets = a.P.get('facets') or {}
    out = []
    for name in src.get(code, []):
        value = bars.get(name, facets.get(name))
        if value is None: continue
        label = AD.SP.BAR_LABEL.get(name) or AD.SP.FACET_LABEL.get(name) or name
        out.append(dict(trait=name, label=label, level=round(float(value), 2)))
    return out


def venue_evidence(a, venue, citable):
    """Citable Fact ids the existing review linker (stay_planner.fact_hits) ties to any native code
    served at this venue, e.g. lunch_myongwol -> MYONGWOLGWAN. A link, not a verified preference."""
    out = []
    for code, ids in (a.P.get('fact_hits') or {}).items():
        spec = AD.SP.ACT.get(code)
        if not spec: continue
        try: loc = spec[1](a.B)
        except Exception: continue
        if loc == venue: out += [f for f in ids if f in citable]
    return sorted(dict.fromkeys(out))


def activity_fit(a, key, action, citable):
    code = native_code(key, action)
    if code is None:
        return dict(fit=None, basis='NO_TRAIT_COEFFICIENT_FOR_THIS_OFFER', trait_terms=[], evidence_fact_ids=[])
    hits = [f for f in (a.P.get('fact_hits') or {}).get(code, []) if f in citable]
    return dict(fit=round(float(AD.pace_w(a, code)), 3), basis='M4_ACT_WEIGHT_WITH_FATIGUE_PACE', native_code=code,
                trait_terms=_trait_terms(code, a), evidence_fact_ids=hits[:6], direct_evidence_fact_ids=hits[:6])


def _norm(label):
    import re
    return re.sub(r'\s+', '', re.sub(r'룸서비스|\(.*?\)', '', str(label or '')))


# ---------------------------------------------------------------- meal baskets (BASKET_SELECTION_V3)
# Composition groups are chosen by criteria (experience, score, price check, party set), not by a
# bare score cut: within one restaurant the native product score is nearly flat (A07 피자힐: 38
# baskets within 4.38~5.32, the gap is the per-person price term), so a top-N cut by score is a
# price cut in disguise. Inside a group every distinct, engine-quoted size/topping variant is
# listed up to MAX_VARIANTS; every cut is recorded.
import re as _re
MAX_GROUPS = 3
MAX_VARIANTS = 12
FOOD_KINDS = {'pizza': '피자', 'pasta': '파스타', 'salad': '샐러드', 'burger': '버거', 'sandwich': '샌드위치', 'noodles': '우동|소바|국수',
              'steak': '스테이크', 'chicken': '치킨|닭', 'beef': '한우|소고기|고기|갈비|차돌|등심', 'japanese': '스시|초밥|오마카세|우동|소바|회',
              'korean': '한식|정식|된장|갈비탕|불고기', 'seafood': '해산물|새우|크랩|해물', 'pork': '돼지|학센', 'rice': '덮밥|밥', 'soup': '탕|국|찌개',
              'chinese': '중식|짜장|짬뽕|딤섬', 'buffet': '뷔페', 'brunch': '브런치'}
KIND_KO = {'pizza': '피자', 'pasta': '파스타', 'salad': '샐러드', 'burger': '버거', 'sandwich': '샌드위치', 'noodles': '면', 'steak': '스테이크',
           'chicken': '치킨', 'beef': '소고기', 'japanese': '일식', 'korean': '한식', 'seafood': '해산물', 'pork': '돼지고기', 'rice': '밥',
           'soup': '탕', 'chinese': '중식', 'buffet': '뷔페', 'brunch': '브런치'}
GENERIC_TOKENS = {'세트', '추가', '피자', '파스타', '단품', '코스', '런치', '디너', '점심', '저녁', '메뉴', '스페셜', '시그니처', '정식', '플래터', '브런치', '음료',
                  '커플', '패밀리', '가족', '키즈', '어린이', '아이', '성인', '2인', '3인', '4인', '1인', '인룸', '모둠', '특선', '한정', '프로모션'}   # people/target and promo words never identify a dish
DRINK_RX = r'맥주|생맥주|와인|WINE|BEER|칵테일|하이볼|샴페인|사케|위스키'
DESSERT_RX = r'디저트|DESSERT|케이크|빙수'
SET_RX = r'세트|코스|정식|오마카세|course|omakase|set'
FORMAT_RX = r'코스|오마카세|정식|세트|course|omakase'
SIZE_RX = r'\b(S|M|L|XL|HALL|TAKEOUT)\b|단품|\(.*?\)'
VENUE_ALIAS = {'ROOM_MEAL': ['룸서비스', '인룸'], 'THE_PAVILION': ['파빌리온'], 'THE_BUFFET': ['더뷔페', '더 뷔페'], 'MOEGI': ['모에기'],
               'MYONGWOLGWAN': ['명월관'], 'PIZZA_HILL': ['피자힐'], 'ONDAL': ['온달'], 'GEUMRYONG': ['금룡'], 'LE_PASSAGE': ['파사쥬'], 'LUX_BAR': ['럭스바']}


def venue_names(venue):
    names = list(VENUE_ALIAS.get(venue, []))
    ko = AD.VENUE_KO.get(venue)
    if ko and ko not in names: names.append(ko)
    return [n for n in names if n]


def venue_records(a, venue, records, citable):
    """Review records about this restaurant: linked by the existing review linker (fact_hits) or naming it.
    Polarity is not annotated in the source (UNANNOTATED_READ_SUMMARY), so nothing here is read as liked or disliked."""
    linked = set(venue_evidence(a, venue, citable)); names = venue_names(venue); out = []
    for r in records or []:
        ids = [f for f in r.get('fact_ids', []) if f in citable]
        if not ids: continue
        # only this hotel's records describe THIS restaurant; another hotel's room service is a habit, not this venue
        if r.get('source_scope') != 'wh': continue
        text = str(r.get('summary') or '')
        if set(ids) & linked or any(n in text for n in names):
            out.append(dict(fact_ids=ids, summary=text))
    return out


def _food(c):
    return [p for p in c['components'] if p.get('role') not in ('DRINK', 'ADDON')]


def basket_role(c):
    """MEAL / DRINK_SNACK / DESSERT from catalog labels, units, tags and included components (no new facts)."""
    food = _food(c) or c['components']
    text = ' '.join('%s %s' % (p.get('label', ''), p.get('source_unit', '')) for p in food)
    tags = {t for p in food for t in p.get('tags', [])}
    included = {k for p in food for k, v in ((p.get('included_components') or {}) if isinstance(p.get('included_components'), dict) else {}).items() if v and k != 'drinks'}
    food_tags = (tags | included) & set(FOOD_KINDS)
    if _re.search(DESSERT_RX, text, _re.I) and not food_tags: return 'DESSERT'
    if _re.search(DRINK_RX, text, _re.I) and not food_tags: return 'DRINK_SNACK'
    return 'MEAL'


def composition(c):
    """Group key and Korean label: all courses/sets of a restaurant form one group; other baskets group by
    food kind (one dish or two different dishes of the same kinds are options inside the group)."""
    food = _food(c) or c['components']
    if any(p.get('billing_unit') == 'set' or _re.search(SET_RX, str(p.get('label', '')), _re.I) for p in food):
        return 'set', '코스·세트'
    kinds = sorted({t for p in food for t in p.get('tags', [])} & set(FOOD_KINDS))
    if not kinds:
        name = ' + '.join(sorted({_re.sub(SIZE_RX, '', p.get('label', '')).strip() for p in food}))
        return 'item|' + _norm(name), name
    return '+'.join(kinds), ' + '.join(KIND_KO[k] for k in kinds)


def _item_tokens(c, venue):
    names = venue_names(venue); out = set()
    for p in _food(c) or c['components']:
        label = _re.sub(SIZE_RX, ' ', str(p.get('label', '')))
        for n in names: label = label.replace(n, ' ')
        for tok in _re.split(r'[\s+&·,/]+', label):
            tok = tok.strip()
            if len(tok) >= 2 and tok not in KIND_KO.values() and tok not in GENERIC_TOKENS: out.add(tok)
    return out


def _stated_people(c):
    for p in _food(c) or c['components']:
        m = _re.search(r'(\d+)\s*인', '%s %s' % (p.get('source_unit', ''), p.get('label', '')))
        if m: return int(m.group(1))
    return None


def engine_score(a, t, action, c, w, citable):
    """The native product score of one quoted contract (as HR.choose computes it, without the random draw)."""
    o = HR.offer(a, c, action['start'], action['duration'], w)
    unknown = o.get('price_pp_krw') is None
    so = dict(o, price_pp_krw=0, guest_discount_krw=0, card_benefit_krw=0, in_package=False) if unknown else o
    terms = AD.EN.score(so, t, dict(used=set(a.used), hunger=a.hunger_e), dict(a.visit_e, checkin=AD.mh(t)), a.traits, w)
    facts = sorted({f for x in terms for f in x.get('fact_ids', []) if f in citable})
    return round(sum(x['value'] for x in terms), 3), [x['factor'] for x in terms if x.get('value')][:6], facts, unknown


def basket_scores(a, t, action, w, citable, records=None):
    """Score each quoted contract exactly as the native product pick does (HR.choose), without the random draw,
    and attach the catalog-derived role, composition, portion and the review records that name its items."""
    venue = action.get('venue'); vrec = venue_records(a, venue, records, citable); rows = []
    for c in action.get('_quotes') or []:
        fit, factors, facts, unknown = engine_score(a, t, action, c, w, citable)
        mains = sorted({_norm(p.get('label')) for p in _food(c)} or {_norm(c['label'])})
        key, label = composition(c)
        role = basket_role(c)
        if role != 'MEAL':   # a drink platter sold as a 'set' never shares a group with meal sets
            key, label = role + '|' + key, {'DRINK_SNACK': '음료·안주', 'DESSERT': '디저트'}.get(role, role) + ': ' + label
        tokens = _item_tokens(c, venue)
        kinds = {t for p in (_food(c) or c['components']) for t in p.get('tags', [])} & set(FOOD_KINDS)
        item_facts = sorted({f for r in vrec for f in r['fact_ids'] if any(tok in r['summary'] for tok in tokens)})
        kind_facts = sorted({f for r in vrec for f in r['fact_ids'] if any(_re.search(FOOD_KINDS[k], r['summary']) for k in kinds)})
        format_facts = sorted({f for r in vrec for f in r['fact_ids'] if _re.search(FORMAT_RX, r['summary'], _re.I)}) if key == 'set' else []
        mb = c.get('meal_basket') or {}
        rows.append(dict(sku_id=c['sku_id'], label=c['label'], total_krw=c['unit_price_krw'], price_status=c.get('price_status'), main_key='|'.join(mains),
                         items=[dict(sku_id=p['sku_id'], quantity=p['billing_quantity'], label=p.get('label'), unit_price_krw=p.get('unit_price_krw'), role=p.get('role')) for p in c['components']],
                         fit=fit, factors=factors, evidence_fact_ids=facts[:6], price_known=not unknown, role=role, group=key, group_label=label,
                         meal_equivalents=mb.get('meal_equivalents'), party_size=mb.get('party_size', a.N), stated_people=_stated_people(c),
                         experience_item_fact_ids=item_facts, experience_kind_fact_ids=kind_facts, experience_format_fact_ids=format_facts))
    rows.sort(key=lambda r: (-r['fit'], r['total_krw'] or 0))
    return rows


PERSONAL_FIRST = 'PERSONAL_SIGNAL_FIRST_V1'
SIGNAL_EXCLUDED_KINDS = {'rice', 'soup'}   # '밥'·'국/탕' match too many unrelated words (조식 밥, 한국) to signal a food preference
# one-syllable alternatives ('회' in 기회·회사, '닭') are dropped for the signal; the lexicon itself is unchanged
SIGNAL_KIND_RX = {k: '|'.join(x for x in v.split('|') if len(x) >= 2) for k, v in FOOD_KINDS.items()}
SIGNAL_FORMAT_RX = r'코스(?!트코)|오마카세|정식|course|omakase'   # a sold course/정식, not any '세트' (and not 코스트코)
BREAKFAST_ONLY_RX = r'조식|아침|브런치'   # a record about breakfast only says nothing about a lunch/dinner choice
OTHER_MEAL_RX = r'저녁|디너|만찬|점심|런치|코스|오마카세|피자|스테이크|한우|고기|뷔페|레스토랑|다이닝'


def personal_meal_signal(a, key, action, records, citable):
    """V18-only (PERSONAL_FIRST): which of this person's review records relate to this venue, by meaning
    already in the data: the venue named (VENUE_ALIAS), a food kind this venue sells (FOOD_KINDS, the
    existing lexicon), a course/set format the venue sells (FORMAT_RX), or the existing in-room-meal
    facet for room service. Polarity is not decided here: a disappointment is as relevant as praise and
    the model reads the summary. Counted per record (aliases of one record are one observation)."""
    venue = action.get('venue') or key.split(':', 1)[-1]
    quotes = action.get('_quotes') or []
    tags = {tg for c in quotes for p in c.get('components', []) for tg in p.get('tags', [])} - SIGNAL_EXCLUDED_KINDS
    has_set = any(_re.search(SIGNAL_FORMAT_RX, str(c.get('label') or ''), _re.I) for c in quotes)
    names = venue_names(venue)
    room = {e['fact_id'] for e in (((a.traits or {}).get('facets') or {}).get('practical_alt') or {}).get('evidence', []) if e.get('grade') == 'rep'} if venue == 'ROOM_MEAL' else set()
    out = dict(venue=[], kind=[], format=[], in_room=[])
    for r in records or []:
        ids = [f for f in r.get('fact_ids', []) if f in citable]
        if not ids: continue
        text = str(r.get('summary') or '')
        if names and any(n in text for n in names): out['venue'].append(ids)
        elif any(SIGNAL_KIND_RX.get(k) and _re.search(SIGNAL_KIND_RX[k], text) for k in tags): out['kind'].append(ids)
        elif has_set and _re.search(SIGNAL_FORMAT_RX, text, _re.I): out['format'].append(ids)
        elif room & set(ids): out['in_room'].append(ids)
    related = {f for v in out.values() for ids in v for f in ids}
    # a repeat visit is a settled positive only for what it was about: the record must name this venue or a
    # food kind it sells, and a breakfast-only record does not speak for a lunch/dinner choice
    breakfast = str(action.get('period') or '').lower() == 'breakfast' or key.upper().startswith('MEAL:BREAKFAST')
    def breakfast_only(text):
        for n in names: text = text.replace(n, ' ')   # '더뷔페' names a venue, it is not a buffet dinner
        return _re.search(BREAKFAST_ONLY_RX, text) and not _re.search(OTHER_MEAL_RX, text)
    about = {f for r in records or [] for f in r.get('fact_ids', []) if f in citable
             and (any(f in ids for ids in out['venue']) or any(f in ids for ids in out['kind']))
             and (breakfast or not breakfast_only(str(r.get('summary') or '')))}
    pos, neg = confirmed_food_evaluations(a, tags, about)
    return dict(records={k: len(v) for k, v in out.items()}, fact_ids={k: sorted({f for ids in v for f in ids}) for k, v in out.items()},
                total=sum(len(v) for v in out.values()), tags=sorted(tags), tier=None,
                confirmed_positive=sorted(pos), confirmed_negative=sorted(related & neg),
                unclassified=sorted(related - pos - neg))


def confirmed_food_evaluations(a, venue_tags, about=()):
    """Fact ids whose evaluation the existing profile already settled (no new sentiment classifier):
    - positive: a structured menu evaluation (traits.menu, weight > 0) whose tags meet this venue's food tags;
      and representative repeat behaviour (routine facet, tag 'repeat') when the record is about this venue
      or a food kind it sells (`about`);
    - negative: a structured menu evaluation with weight < 0 whose tags meet the venue's tags, and the
      profile's counterexamples.
    Facet evidence such as 'food'/'premium' marks what a trait rests on, not whether the guest liked it,
    so it is not used. Everything else stays 'related, unclassified': a mention or a non-use (e.g. a
    breakfast not taken) is neither a preference nor a dislike."""
    pos, neg = set(), set()
    for m in (a.traits or {}).get('menu') or []:
        if set(m.get('tags') or []) & set(venue_tags):
            w = m.get('weight') or 0
            if w > 0: pos.update(m.get('fact_ids') or [])
            elif w < 0: neg.update(m.get('fact_ids') or [])
    for e in (((a.traits or {}).get('facets') or {}).get('routine') or {}).get('evidence', []):
        if e.get('grade') == 'rep' and 'repeat' in (e.get('tags') or []) and e.get('fact_id') in about: pos.add(e['fact_id'])
    for c in (((getattr(a, 'P', None) or {}).get('profile') or {}).get('counterexamples') or []):
        neg.update(c.get('fact_ids') or [])
    return pos - neg, neg


def _adequate(r, n):
    me = r.get('meal_equivalents')
    return me is None or me >= n


def meal_fit(a, t, key, action, w, citable, records=None, meal_decision=True):
    rows = basket_scores(a, t, action, w, citable, records)
    if not rows:
        return dict(fit=None, basis='NO_SCORED_BASKET', baskets=[], groups=[], dropped_baskets=[])
    n = a.N
    for i, r in enumerate(rows): r['m4_rank'] = i + 1
    # distinct main dishes only (same dish under another SKU, or with only another drink, is one choice)
    distinct, seen, dropped = [], {}, []
    for r in rows:
        if r['main_key'] in seen:
            dropped.append(dict(sku_id=r['sku_id'], label=r['label'], fit=r['fit'], total_krw=r['total_krw'], m4_rank=r['m4_rank'], reason='SAME_MAIN_AS:' + seen[r['main_key']])); continue
        seen[r['main_key']] = r['sku_id']; distinct.append(r)
    groups = {}
    for r in distinct: groups.setdefault(r['group'], []).append(r)
    info = {}
    for g, items in groups.items():
        role = 'MEAL' if any(x['role'] == 'MEAL' for x in items) else items[0]['role']
        info[g] = dict(group=g, label=items[0]['group_label'], role=role, fit=max(x['fit'] for x in items),
                       item_facts=sorted({f for x in items for f in x['experience_item_fact_ids']}),
                       kind_facts=sorted({f for x in items for f in x['experience_kind_fact_ids']}),
                       format_facts=sorted({f for x in items for f in x.get('experience_format_fact_ids', [])}),
                       party_set=any(x['stated_people'] == n for x in items) and g == 'set', items=items)
    meal_groups = [g for g in info.values() if g['role'] == 'MEAL'] if meal_decision else list(info.values())
    other_groups = [g for g in info.values() if g not in meal_groups]
    by_fit = sorted(meal_groups, key=lambda g: -g['fit'])
    value_check = float((a.P.get('bars') or {}).get('value_check', 0) or 0)
    adequate = [r for r in distinct if r['role'] == 'MEAL' and _adequate(r, n) and r['total_krw'] is not None] if meal_decision else [r for r in distinct if r['total_krw'] is not None]
    cheapest = min(adequate, key=lambda r: (r['total_krw'], -r['fit'])) if adequate else None
    chosen, why = [], {}
    def pick(g, reason):
        if g and g not in chosen and len(chosen) < MAX_GROUPS: chosen.append(g); why[g['group']] = reason
    exp = sorted([g for g in meal_groups if g['item_facts']], key=lambda g: (-len(g['item_facts']), -g['fit'])) \
        or sorted([g for g in meal_groups if g['format_facts']], key=lambda g: -g['fit']) \
        or sorted([g for g in meal_groups if g['kind_facts']], key=lambda g: (-len(g['kind_facts']), -g['fit']))
    if exp: pick(exp[0], 'EXPERIENCE_ITEM' if exp[0]['item_facts'] else 'EXPERIENCE_FORMAT' if exp[0]['format_facts'] else 'EXPERIENCE_KIND')
    # a course/set format the guest wrote about at this restaurant is kept even when an item match took the first slot
    for g in [g for g in meal_groups if g['format_facts']]: pick(g, 'EXPERIENCE_FORMAT')
    if by_fit: pick(by_fit[0], 'TOP_PRODUCT_SCORE')
    if cheapest and value_check >= 0.5: pick(info[cheapest['group']], 'PRICE_CHECK_CHEAPEST_ADEQUATE')
    party = sorted([g for g in meal_groups if g['party_set']], key=lambda g: -g['fit'])
    if party: pick(party[0], 'SET_FOR_THIS_PARTY_SIZE')
    for g in sorted([g for g in meal_groups if g['item_facts'] or g['kind_facts']], key=lambda g: -g['fit']): pick(g, 'EXPERIENCE_KIND')
    for g in by_fit: pick(g, 'NEXT_PRODUCT_SCORE')
    if not meal_decision:   # a meal decision never shows drink/snack/dessert baskets as a meal (they stay in the trace)
        for g in sorted(other_groups, key=lambda g: -g['fit']): pick(g, 'NEXT_PRODUCT_SCORE')
    for g in info.values():
        if g in chosen: continue
        reason = 'NOT_A_MEAL_BASKET_FOR_MEAL_DECISION:' + g['role'] if (meal_decision and g['role'] != 'MEAL') else 'GROUP_BUDGET_FULL'
        for r in g['items']:
            dropped.append(dict(sku_id=r['sku_id'], label=r['label'], fit=r['fit'], total_krw=r['total_krw'], m4_rank=r['m4_rank'], group=g['group'],
                                experience_fact_ids=r['experience_item_fact_ids'] or r['experience_kind_fact_ids'], reason=reason))
    out_groups, baskets, bid = [], [], 0
    for g in chosen:
        items = sorted(g['items'], key=lambda r: (not r['experience_item_fact_ids'], not _adequate(r, n),
                                                  (r['meal_equivalents'] - n) if r['meal_equivalents'] is not None else 99, r['total_krw'] or 0, -r['fit']))
        shown, cut = items[:MAX_VARIANTS], items[MAX_VARIANTS:]
        for r in cut:
            dropped.append(dict(sku_id=r['sku_id'], label=r['label'], fit=r['fit'], total_krw=r['total_krw'], m4_rank=r['m4_rank'], group=g['group'],
                                experience_fact_ids=r['experience_item_fact_ids'], reason='VARIANT_CAP_IN_GROUP'))
        opts = []
        for r in shown:
            bid += 1; r['basket_id'] = '%s#%d' % (key, bid)
            r['marks'] = [m for m, ok in (('직접 경험 메뉴', bool(r['experience_item_fact_ids'])), ('최저가(인원 충족)', r is cheapest),
                                          ('상품 점수 1위', r is rows[0]), ('인원에 맞춘 세트', r['stated_people'] == n and g['group'] == 'set')) if ok]
            opts.append(r); baskets.append(r)
        out_groups.append(dict(group=g['group'], label=g['label'], role=g['role'], shown_because=why[g['group']],
                               experience_fact_ids=g['item_facts'] or g['format_facts'] or g['kind_facts'], options=opts, hidden_variants=len(cut)))
    evidence = sorted({f for r in baskets for f in r['evidence_fact_ids']})
    direct = venue_evidence(a, action.get('venue'), citable)
    named = sorted({f for r in venue_records(a, action.get('venue'), records, citable) for f in r['fact_ids']})
    return dict(fit=max(g['fit'] for g in chosen) if chosen else rows[0]['fit'], basis='M4_PRODUCT_SCORE_MAX_BASKET; BASKET_SELECTION_V3_GROUPS_BY_CRITERIA',
                baskets=baskets, groups=out_groups, dropped_baskets=dropped, evidence_fact_ids=evidence[:8],
                direct_evidence_fact_ids=sorted(set(direct) | set(named))[:8], basket_count=len(rows),
                cheapest_adequate=cheapest['sku_id'] if cheapest else None, top_score=rows[0]['sku_id'])


def state_fit(a, t, key, action):
    """Rest / day-end / leave / wait are state-driven, not trait-ranked; the fit only orders rests among themselves."""
    ratio = a.fatigue / max(a.rest_limit, 0.01)
    kind = kind_of(key, action)
    if kind == 'REST':
        code = native_code(key, action)
        if code in AD.SP.ACT:
            return dict(fit=round(float(AD.pace_w(a, code)), 3), basis='M4_ACT_WEIGHT_WITH_FATIGUE_PACE', native_code=code, trait_terms=_trait_terms(code, a))
        return dict(fit=round(0.1 + 0.5 * ratio - (0.3 if key == 'wait_reconsider' else 0), 3), basis='STATE_ONLY_NOT_TRAIT')
    if kind == 'DAY_END':
        return dict(fit=round(ratio + max(0, 1 - max(0, a.end - t) / 240), 3), basis='STATE_ONLY_FATIGUE_RATIO_AND_TIME_LEFT; MANDATORY_CANDIDATE')
    if kind == 'LEAVE':
        return dict(fit=None, basis='MANDATORY_CANDIDATE_AFTER_CHECKOUT')
    return dict(fit=None, basis='UNRANKED')


def execution_conditions(a, t, action):
    wait = action.get('wait')
    return dict(start_time=AD.mh(action['start']), end_time=AD.mh(action['start'] + action['duration']), duration_minutes=action['duration'],
                travel_minutes=AD.SP.travel_min(a.loc, wait['location']) + AD.SP.travel_min(wait['location'], action['location']) if wait else AD.SP.travel_min(a.loc, action['location']),
                wait_minutes=max(0, action['start'] - t - (AD.SP.travel_min(a.loc, action['location']))) if not wait else wait['end'] - wait['start'],
                price_krw=action.get('order_total_krw'), price_status=action.get('price_status'), included=action.get('included'),
                planning_viability=action.get('planning_viability', 'AVAILABLE_NOW'), reservation='UNKNOWN_NOT_BOOKED',
                basis='WORLD_VALIDATED_SCHEDULE_NOT_CONFIRMED_RESERVATION')


FAIR_BAND = 0.5   # one unverified rule term (the night-view base alone is 0.45): fit gaps below this do not decide exposure


def fair_meal_order(a, t, group, signals):
    """Research switch HILLINK_RESEARCH_FAIR_MEAL_EXPOSURE=1 (default OFF). Offline 28-customer audit (2026-11-08): when a
    meal was open Pizza Hill was shown 107/112 times it was feasible and was the rule-fit top 69/119, while Ondal was shown
    7/92 (only with a personal link); the margin over the next venue was mostly one unverified term (night-view base 0.45,
    trait 'food experience' coefficient). The model can only choose among what it is shown.
    Order for the meal slots (the slot rules themselves are unchanged):
      1. personal signal (settled positive tier, then a direct record link) - unchanged priority
      2. fit band: venues within FAIR_BAND of the best remaining fit are treated as equal; a clearly lower fit stays lower
      3. inside a band, a venue already eaten at during this visit without a personal link or a stated intention comes after
         one not yet tried (it is still shown when there is room, with its visit memory)
      4. then a reproducible per customer/day/period order (no score), so equal venues share exposure across customers
    Nothing is removed and nothing is chosen here."""
    import hashlib
    eaten = {str(m.get('venue')) for m in (getattr(a, '_autonomous_memory', {}) or {}).get('meal_experiences', []) or []}
    intents = ' '.join(str(x) for x in ((getattr(a, '_autonomous_memory', {}) or {}).get('pending_intentions') or []))
    best = max((r['fit'].get('fit') for r in group if r['fit'].get('fit') is not None), default=0)
    def key(r):
        venue = str(r['action_id']).split(':', 1)[-1]
        sig = signals.get(r['action_id'], {}) if signals else {}
        linked = bool(r['fit'].get('direct_evidence_fact_ids'))
        fit = r['fit'].get('fit')
        band = int(max(0.0, best - fit) // FAIR_BAND) if fit is not None else 99
        repeat = venue in eaten and not linked and venue not in intents and AD.VENUE_KO.get(venue, '~') not in intents
        rot = hashlib.sha256(('%s|%s|%s|%s' % (a.pid, a.sc.get('date'), 'lunch' if t < 900 else 'dinner', venue)).encode()).hexdigest()
        return (-(sig.get('tier') or 0), not linked, band, repeat, rot)
    group.sort(key=key)
    for i, r in enumerate(group): r['fair_order'] = i + 1


def build(a, world, t, actions, menus, w, citable, max_options=MAX_OPTIONS, records=None, selection='M4_FIT'):
    """Return (shortlist rows in model order, trace). Rows carry fit, conditions and baskets."""
    ratio = a.fatigue / max(a.rest_limit, 0.01)
    # research CHECKOUT_PREP / MEAL_DEFER candidates never take a slot from the existing shortlist (no displacement)
    max_options += sum(1 for k, v in actions.items() if kind_of(k, v) in ('CHECKOUT', 'DEFER_MEAL') or k == 'room_rest_long')
    from .autonomous_agent import meal_state
    ms = meal_state(a)
    dinner_resolved = bool(ms['meals']['dinner'] or ms['meal_decision_resolved']['dinner'])
    meal_period = next((x.get('period') for x in actions.values() if x.get('execution') == 'MEAL'), None)
    meal_open = meal_period is not None and not (ms['meals'].get(meal_period) or ms['meal_decision_resolved'].get(meal_period))
    scope = {f: r.get('source_scope') for r in records or [] for f in r.get('fact_ids', [])}
    rows = {}; no_meal = []
    for key, action in actions.items():
        kind = kind_of(key, action)
        if kind == 'MEAL': fit = meal_fit(a, t, key, action, w, citable, records, meal_decision=meal_open)
        elif kind == 'ACTIVITY': fit = activity_fit(a, key, action, citable)
        else: fit = state_fit(a, t, key, action)
        if records is not None and fit.get('direct_evidence_fact_ids'):
            linked = fit['direct_evidence_fact_ids']
            fit['direct_evidence_fact_ids'] = [f for f in linked if scope.get(f) == 'wh']
            fit['similar_elsewhere_fact_ids'] = [f for f in linked if scope.get(f) == 'other']
            fit['scope_unconfirmed_fact_ids'] = [f for f in linked if scope.get(f) not in ('wh', 'other')]   # never shown as 'elsewhere' or as protection
        if kind == 'MEAL' and not fit.get('groups'):
            no_meal.append(dict(action_id=key, type='MEAL', fit=None, reason='NO_MEAL_OPTION_FOR_THIS_DECISION'))   # e.g. a drinks-only venue while dinner is open
            continue
        rows[key] = dict(action_id=key, type=kind, label=action.get('label'), location=action.get('location'), execution=action['execution'],
                         fit=fit, conditions=execution_conditions(a, t, action))
    # duplicates: the same native code offered twice (PLAN vs ENGINE, contract vs engine) keeps the cheaper/contract one
    seen = {}
    dropped = list(no_meal)
    for key, row in list(rows.items()):
        code = row['fit'].get('native_code') if row['type'] in ('ACTIVITY', 'REST') else None
        if not code: continue
        if code in seen:
            keep, drop = (seen[code], key) if actions[seen[code]]['execution'] != 'ENGINE' or actions[key]['execution'] == 'ENGINE' else (key, seen[code])
            dropped.append(dict(action_id=drop, type=rows[drop]['type'], fit=rows[drop]['fit'].get('fit'), reason='DUPLICATE_OF:' + keep))
            rows.pop(drop); seen[code] = keep
        else:
            seen[code] = key
    # the same sold contract under two native codes (e.g. 족욕 / 야간 족욕 = one SKYARD contract) is one
    # choice; after 18:00 the night variant is the time-appropriate name, before it the day variant
    by_contract = {}
    for key, row in list(rows.items()):
        sku = (actions[key].get('contract') or {}).get('sku_id') if row['type'] == 'ACTIVITY' else None
        if not sku: continue
        if sku in by_contract:
            other = by_contract[sku]
            night = lambda k: str(rows[k]['fit'].get('native_code') or k).startswith('night_')
            keep = (key if night(key) else other) if t >= 1080 else (other if night(key) else key)
            if night(key) == night(other): keep = other if (rows[other]['fit'].get('fit') or -9) >= (rows[key]['fit'].get('fit') or -9) else key
            drop = key if keep == other else other
            # the merged candidate keeps every evidence link of both names (the day variant's link is the same facility)
            for field in ('direct_evidence_fact_ids', 'similar_elsewhere_fact_ids', 'scope_unconfirmed_fact_ids', 'evidence_fact_ids'):
                merged = list(dict.fromkeys((rows[keep]['fit'].get(field) or []) + (rows[drop]['fit'].get(field) or [])))
                if merged: rows[keep]['fit'][field] = merged
            dropped.append(dict(action_id=drop, type='ACTIVITY', fit=rows[drop]['fit'].get('fit'), reason='SAME_CONTRACT_AS:' + keep))
            rows.pop(drop); by_contract[sku] = keep
        else:
            by_contract[sku] = key
    by_type = {}
    for row in rows.values(): by_type.setdefault(row['type'], []).append(row)
    for kind, group in by_type.items():
        group.sort(key=lambda r: -(r['fit'].get('fit') if r['fit'].get('fit') is not None else -1e9))
        for i, r in enumerate(group): r['m4_rank_in_type'] = i + 1; r['type_size'] = len(group)
    signals = {}
    if selection == PERSONAL_FIRST and by_type.get('MEAL'):
        # V18-only: venues this person's records relate to survive first; the M4 fit (price-heavy) orders only
        # within the same level of personal signal and fills the remaining meal slots (fallback)
        for r in by_type['MEAL']: signals[r['action_id']] = personal_meal_signal(a, r['action_id'], actions[r['action_id']], records, citable)
        # Priority only from evaluations the profile already settled (confirmed positive, no settled negative).
        # A related record (a mention, a non-use, an unannotated summary) gives no priority: it is kept for the
        # evidence links the model reads. Within a level, and for every remaining slot, C's rules apply unchanged
        # (a way of eating not yet shown first, one evidence-linked venue, the extension slot), so P only moves
        # settled-positive venues ahead of the M4 (price-heavy) order and never narrows the kinds shown.
        # Two levels, not counts: a settled positive about this venue itself (the record names it) > a settled
        # positive about a food kind it sells (experience generalised from elsewhere) > none.
        for v in signals.values():
            v['tier'] = 2 if set(v['confirmed_positive']) & set(v['fact_ids']['venue']) else 1 if v['confirmed_positive'] else 0
        by_type['MEAL'].sort(key=lambda r: (-signals[r['action_id']]['tier'], -(r['fit'].get('fit') if r['fit'].get('fit') is not None else -1e9)))
    if os.environ.get('HILLINK_RESEARCH_FAIR_MEAL_EXPOSURE') == '1' and by_type.get('MEAL'):
        fair_meal_order(a, t, by_type['MEAL'], signals)
    chosen = []; reasons = {}
    def facet(r):
        """Activity kind (wellness/outdoor/culture/rest/snack/bar) or meal mode (in-room/casual/buffet/restaurant)."""
        if r['type'] == 'MEAL': return MEAL_MODE.get(r['action_id'].split(':', 1)[1], 'restaurant')
        code = r['fit'].get('native_code')
        return AD.SP.ACT[code][2] if code in AD.SP.ACT else 'other'
    def take(kind, n=1, why='M4_TOP_OF_TYPE'):
        for _ in range(n):
            group = [r for r in by_type.get(kind, []) if r not in chosen]
            if not group: return
            # representative over repetition: the next slot prefers a kind/mode not yet shown
            # (with sparse personal evidence the trait ranking alone narrows to the engine's guess)
            shown = {facet(r) for r in chosen if r['type'] == kind}
            fresh = [r for r in group if facet(r) not in shown] if kind in ('ACTIVITY', 'MEAL') and shown else []
            r = fresh[0] if fresh else group[0]
            label = 'CONFIRMED_POSITIVE_FIRST' if signals.get(r['action_id'], {}).get('tier') else why
            chosen.append(r); reasons[r['action_id']] = (label + '_NEW_KIND') if fresh else label
    def take_evidence(kind):
        """The next slot of this type goes to the candidate with the most direct personal Fact links
        that is not yet shown: a meaningful exception is never left out only because its score is low."""
        linked = [r for r in by_type.get(kind, []) if r not in chosen and r['fit'].get('direct_evidence_fact_ids')]
        if not linked: return False
        best = max(linked, key=lambda r: (len(r['fit']['direct_evidence_fact_ids']), r['fit'].get('fit') or -1e9))
        chosen.append(best); reasons[best['action_id']] = 'DIRECT_PERSONAL_EVIDENCE_LINK'; return True
    # mandatory and exception candidates first
    take('DAY_END'); take('LEAVE'); take('SKIP_MEAL'); take('CHECKOUT'); take('DEFER_MEAL')   # the last two exist only under research switches
    # an event the operator applied to this visit (wine fair, an event card) is always shown while it can be joined:
    # the model decides whether to go; a score-ranked budget must not hide the scenario under test (2026-11-09)
    for key, row in rows.items():
        if row not in chosen and (key == 'WINE_FAIR' or key.startswith('CARD_')):
            chosen.append(row); reasons[key] = 'OPERATOR_SCENARIO_EVENT'
    if by_type.get('MEAL') and (meal_open or not dinner_resolved): take('MEAL')
    take('ACTIVITY'); take('REST')
    # research REST_BLOCKS: the long block is shown next to the room rest it extends (its own slot, see max_options)
    if 'room_rest_long' in rows and rows['room_rest_long'] not in chosen:
        chosen.append(rows['room_rest_long']); reasons['room_rest_long'] = 'RESEARCH_LONG_REST_BLOCK'
    if by_type.get('MEAL') and 'MEAL' not in {r['type'] for r in chosen} and len(chosen) < max_options: take('MEAL')
    # fill the remaining budget: a second meal venue when the meal is open or the guest reads hungry,
    # otherwise a second activity, then a second rest when tired
    hungry = a.hunger_e >= 0.6
    order = (['MEAL', 'MEAL', 'ACTIVITY'] if (meal_open or hungry) else ['ACTIVITY', 'MEAL', 'ACTIVITY']) + (['REST'] if ratio >= 0.4 else []) + ['ACTIVITY', 'MEAL']
    for kind in order:
        if len(chosen) >= max_options: break
        if kind == 'MEAL' and sum(r['type'] == 'MEAL' for r in chosen) >= MAX_MEAL_VENUES: continue
        # further slots of a type go first to directly evidence-linked candidates, then to an unseen kind/mode, then to score.
        # Meals: one evidence-linked venue in the regular budget (polarity is unannotated, so evidence must not crowd out
        # every other way of eating); a further linked venue gets the extension slot below.
        linked_meals = sum(1 for r in chosen if r['type'] == 'MEAL' and reasons.get(r['action_id']) == 'DIRECT_PERSONAL_EVIDENCE_LINK')
        if kind in ('MEAL', 'ACTIVITY') and any(r['type'] == kind for r in chosen) and not (kind == 'MEAL' and linked_meals >= 1) and take_evidence(kind): continue
        take(kind, why='M4_NEXT_OF_TYPE')
    # top up with whatever is left (type order) so a small world is shown whole and no slot stays empty
    for kind in ('MEAL', 'ACTIVITY', 'REST', 'SKIP_MEAL', 'DAY_END', 'LEAVE', 'CHECKOUT', 'DEFER_MEAL'):
        while len(chosen) < max_options and any(r not in chosen for r in by_type.get(kind, [])):
            if kind == 'MEAL' and sum(r['type'] == 'MEAL' for r in chosen) >= MAX_MEAL_VENUES: break
            take(kind, why='FILL_REMAINING_SLOT')
    # one extension slot: a further directly evidence-linked meal/activity that would otherwise be
    # left out only for lack of room (ties broken by score are not a reason to hide personal evidence)
    extended = None
    for kind in ('MEAL', 'ACTIVITY'):
        if extended: break
        if kind == 'MEAL' and sum(r['type'] == 'MEAL' for r in chosen) >= MAX_MEAL_VENUES + 1: continue
        if len(chosen) >= max_options and any(r not in chosen and r['fit'].get('direct_evidence_fact_ids') for r in by_type.get(kind, [])):
            if take_evidence(kind): extended = chosen[-1]['action_id']
    for row in rows.values():
        if row not in chosen:
            linked = row['fit'].get('direct_evidence_fact_ids')
            dropped.append(dict(action_id=row['action_id'], type=row['type'], fit=row['fit'].get('fit'), m4_rank_in_type=row.get('m4_rank_in_type'),
                                direct_evidence_fact_ids=linked or [],
                                reason=('EVIDENCE_LINKED_BUT_OPTION_BUDGET_FULL' if linked else 'TYPE_BUDGET_FULL' if row['type'] in {r['type'] for r in chosen} else 'OPTION_BUDGET_FULL')))
    # the model reads the list in a neutral type order (meal, activity, rest, day end, leave), not in
    # shortlist-priority order, so the mandatory day-end candidate does not lead the list
    display = {'MEAL': 0, 'SKIP_MEAL': 1, 'DEFER_MEAL': 1, 'ACTIVITY': 2, 'REST': 3, 'DAY_END': 4, 'LEAVE': 5, 'CHECKOUT': 5}
    chosen.sort(key=lambda r: (display.get(r['type'], 9), r.get('m4_rank_in_type') or 0))
    model_rows = []
    for r in chosen:
        fit = r['fit']
        out = dict(action_id=r['action_id'], type=r['type'], label=r['label'], location=r['location'], conditions=r['conditions'],
                   m4=dict(rank_in_type=r['m4_rank_in_type'], of=r['type_size'], basis=fit.get('basis'), shown_because=reasons.get(r['action_id']),
                           trait_terms=fit.get('trait_terms', []), evidence_fact_ids=fit.get('evidence_fact_ids', []),
                           direct_evidence_fact_ids=fit.get('direct_evidence_fact_ids', []), similar_elsewhere_fact_ids=fit.get('similar_elsewhere_fact_ids', []),
                           scope_unconfirmed_fact_ids=fit.get('scope_unconfirmed_fact_ids', []),
                           meaning='RULE_FIT_FROM_TRAIT_COEFFICIENTS_NOT_VERIFIED_PREFERENCE'))
        if r['type'] == 'MEAL':
            out['basket_groups'] = [dict(label=g['label'], role=g['role'], shown_because=g['shown_because'], experience_fact_ids=g['experience_fact_ids'],
                                         hidden_variants=g['hidden_variants'],
                                         options=[dict(basket_id=b['basket_id'], label=b['label'], total_krw=b['total_krw'], price_status=b['price_status'],
                                                       meal_equivalents=b['meal_equivalents'], marks=b['marks'], experience_fact_ids=b['experience_item_fact_ids'],
                                                       items=[dict(label=i['label'], quantity=i['quantity'], unit_price_krw=i['unit_price_krw']) for i in b['items']]) for b in g['options']])
                                    for g in fit['groups']]
            out['basket_note'] = ('selected_basket_id로 옵션 하나를 고르세요. 주문은 그 옵션의 상품·수량·총액으로 확정되며 옵션 밖 구성은 없습니다. '
                                  '수량은 엔진이 인원 %d명 기준으로 정한 값이고 meal_equivalents는 일반 1인분 환산 가정입니다(섭취 관측 아님). '
                                  '이 식당의 전체 %d개 구성 중 구성 묶음 %d개를 보였습니다(선별 이유는 shown_because). experience_fact_ids는 그 메뉴·종류를 언급한 후기 Fact이며 긍정·부정은 표시되지 않았으니 요약을 직접 읽으세요.'
                                  % (a.N, fit.get('basket_count', 0), len(fit['groups'])))
        if r['type'] == 'DAY_END': out['scope'] = 'CLOSES_TODAY'
        if r['type'] == 'REST': out['scope'] = 'KEEPS_TODAY_OPEN'
        if r['type'] == 'CHECKOUT': out['scope'] = 'ENDS_ROOM_USE; HOTEL_ACTIVITIES_OR_LEAVE_AFTER'
        if r['type'] == 'DEFER_MEAL': out['scope'] = 'LUNCH_STAYS_OPEN_REVIEWED_AGAIN'
        if r['type'] == 'SKIP_MEAL' and r['execution'] == 'SKIP_MEAL' and 'lunch_defer' in rows: out['scope'] = 'LUNCH_CLOSED_FOR_TODAY'
        model_rows.append(out)
    trace = dict(policy=SHORTLIST_POLICY, selection=selection, option_budget=max_options, candidate_count=len(actions), shortlisted=[r['action_id'] for r in chosen],
                 personal_signal=signals or None,
                 m4_fit_meal_order=[r['action_id'] for r in sorted([x for x in rows.values() if x['type'] == 'MEAL'], key=lambda r: r.get('m4_rank_in_type') or 99)],
                 shown_because={k: v for k, v in reasons.items() if k in {r['action_id'] for r in chosen}},
                 budget_extended_for_evidence=extended,
                 types={k: [r['action_id'] for r in v] for k, v in by_type.items()},
                 fit={r['action_id']: dict(type=r['type'], fit=r['fit'].get('fit'), basis=r['fit'].get('basis'), rank_in_type=r.get('m4_rank_in_type'),
                                           dropped_baskets=r['fit'].get('dropped_baskets'), basket_count=r['fit'].get('basket_count'),
                                           top_score=r['fit'].get('top_score'), cheapest_adequate=r['fit'].get('cheapest_adequate'),
                                           groups=[dict(group=g['group'], label=g['label'], role=g['role'], shown_because=g['shown_because'], options=[o['sku_id'] for o in g['options']], hidden_variants=g['hidden_variants']) for g in r['fit'].get('groups') or []],
                                           basket_index={b['basket_id']: dict(sku_id=b['sku_id'], label=b['label'], total_krw=b['total_krw'], m4_rank=b['m4_rank'],
                                                                              items=[dict(sku_id=i['sku_id'], quantity=i['quantity']) for i in b['items']]) for b in r['fit'].get('baskets') or []}) for r in rows.values()},
                 dropped=dropped, state=dict(fatigue_ratio=round(ratio, 3), hunger=round(a.hunger_e, 3), dinner_resolved=dinner_resolved, meal_period=meal_period, meal_open=meal_open),
                 meaning='FIT_IS_RULE_COEFFICIENT_OUTPUT_NOT_VERIFIED_PREFERENCE; MANDATORY_CANDIDATES_NEVER_DROPPED_BY_SCORE')
    if os.environ.get('HL_DEBUG_SHORTLIST_FILE'):   # offline diagnosis only (harness exposure audit)
        import json as _json
        with open(os.environ['HL_DEBUG_SHORTLIST_FILE'], 'a', encoding='utf-8') as fh:
            fh.write(_json.dumps(dict(customer=a.pid, date=a.sc.get('date'), minute=t, state=trace['state'], shortlisted=trace['shortlisted'],
                                      shown_because=trace['shown_because'], meal_order=trace['m4_fit_meal_order'],
                                      meal_fit={k: v['fit'] for k, v in trace['fit'].items() if v['type'] == 'MEAL'},
                                      evidence={r['action_id']: r['fit'].get('direct_evidence_fact_ids') for r in rows.values() if r['type'] == 'MEAL'},
                                      top_factors={r['action_id']: ((r['fit'].get('baskets') or [{}])[0].get('factors')) for r in rows.values() if r['type'] == 'MEAL'}), ensure_ascii=False, default=str) + '\n')
    return model_rows, trace


# Rule-only scope (V3). The rule engine may conclude only where the WORLD leaves no personal choice:
#   1. SINGLE_VALID_ACTION      - the validated world offers exactly one action;
#   2. CHECKED_OUT_NOTHING_LEFT - after checkout the world offers only leaving and the 10-minute wait-and-reconsider;
#   3. DAY_END_OR_SHORT_WAIT    - the world offers only end_day_in_room and the 10-minute wait-and-reconsider.
# wait_reconsider is a 10-minute pause to decide again, not a rest: no rest option (room or lobby) is
# ever decided away by rule.
# Everything else goes to the model: rest vs. day end, which rest, which meal or activity. Fatigue
# ratios, the clock and score gaps are never a rule reason (a world with nothing left is not the
# same fact as a guest wanting to end the day), and no rule extends the day or adds spending.
RULE_SCOPE = ('SINGLE_VALID_ACTION', 'CHECKED_OUT_NOTHING_LEFT', 'DAY_END_OR_SHORT_WAIT')


def rule_sufficient(rows, a, t, actions=None):
    actions = actions if isinstance(actions, dict) else {r['action_id']: dict(execution=r.get('execution', '')) for r in rows}
    kinds = {k: kind_of(k, v) for k, v in actions.items()}
    if len(actions) == 1:
        return next(iter(actions)), 'SINGLE_VALID_ACTION'
    if a.checked_out and 'leave_visit' in actions and set(actions) <= {'leave_visit', 'wait_reconsider'}:
        return 'leave_visit', 'CHECKED_OUT_NOTHING_LEFT'   # a lobby rest is still a personal choice and goes to the model
    if set(actions) == {'end_day_in_room', 'wait_reconsider'}:
        return 'end_day_in_room', 'DAY_END_OR_SHORT_WAIT'
    return None, None
