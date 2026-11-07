"""V19LS: stabilised LS (decision-topic evidence + neutral presentation) for product candidacy.

What this module adds on top of the V18LS lean request, and why (see the 2026-11-06 V17-vs-LS review):

1. Evaluation stance per evidence record (A02, WH-00532). The source facts carry no polarity, and the LS
   prompt told the model to infer it, so a mixed review ("good food, too expensive, not unless special")
   reached the reason one-sided and a revisit refusal did not stop a choice. Each record now carries a
   stance read from its own summary wording (POSITIVE / NEGATIVE / MIXED / NEUTRAL) and flags
   (REVISIT_REFUSAL, CONDITIONAL, LEFTOVER). The reading is a cue match, labelled as such
   (AUTO_CUE_READ_NOT_HUMAN_REVIEWED); the summary text stays and wins over the label.
2. Candidate link per record (about): which shown candidates a record names. Only this hotel's records
   (source_scope == 'wh') are linked to a venue; another hotel's room service is not this hotel's.
3. Repeat signal: when the last two decisions were the same wait/rest with the same reason and nothing
   in the state changed, the request says so (it never forces another action).
4. Diagnostics after a validated selection (non-blocking): reason vs. selected candidate's negative /
   refusal records, mixed records reported one-sided, quantity above party size despite a leftover record,
   cited ids outside the sent set. They are recorded for review and regression, not used to reject.
5. Integrity check of the compression: every sent Fact keeps its id, scope and stance.

Nothing here selects, ranks or removes a candidate.
"""
import copy
import re

from . import m4_shortlist as MS

POLICY = 'LS_STABILITY_V1'
STANCE_BASIS = 'AUTO_CUE_READ_NOT_HUMAN_REVIEWED'

# Cue lists read the deidentified Korean summaries. Order matters only for the flags.
REFUSAL_RX = r'오지 않겠|다시(는)? (오지|가지|방문하지) 않|재방문(하지 않|은? 안 |을? 거부|의사(가)? 없|에는? 유보|은 유보)|안 갈|가지 않겠|다음에는 (오지|가지) 않'
CONDITIONAL_RX = r'(이|가)? 아니면|라면|(때|경우)(에)?만|이상은 기다리지 않|정도는|조건부|특별한 날'
PORTION_SHORT_RX = r'양(이)? ?부족|부족한 양|양이 (적|모자)|모자랐|배가 (안|덜) 차|배고팠|양이 아쉬'
LEFTOVER_RX = r'먹고 남|남은 (음식|피자|조각|메뉴|빵|고기)|음식이 남|양이 많아|남겨서? 포장|남은 .{0,8}포장|다 먹지 못'
NEG_RX = (r'아쉽|아쉬|실망|불만|별로|낮았|낮아|낮다|비싸|아깝|불편|문제|기대 이하|기대와 달|기대에 못|못 미치|못 미쳤|부정적|못 ?했|부족|유보|후회|떨어지|'
          r'먹지 않고|나왔다고|위생|무례|불친절|시끄|좁|붐벼|오래 기다|' + REFUSAL_RX)
POS_RX = (r'만족|좋았|좋게|좋다|좋아|맛있|훌륭|추천|최고|감동|편하|편해|편했|인정|즐겼|즐기|값을 한|가장 좋|호평|'
          r'재방문(하고|할|의사)|다시 (가고|오고|방문하고)|기분 좋|여유롭')
KO = {'POSITIVE': '긍정', 'NEGATIVE': '부정', 'MIXED': '혼합', 'NEUTRAL': '서술'}
FLAG_KO = {'REVISIT_REFUSAL': '재방문 거부', 'CONDITIONAL': '조건부', 'LEFTOVER': '남김', 'PORTION_SHORT': '양 부족'}


def party_fit(eq, party):
    """Compare a basket's general meal-equivalent assumption with the party size (information only)."""
    if not party: return None
    if eq is None: return '미확인'
    return '인원보다 적음' if eq < party else '인원과 같음' if eq == party else '인원보다 많음'


def stance(summary, kind=None):
    """Read one summary. Returns (stance, flags, cues). kind is the source fact kind when known."""
    text = str(summary or '')
    pos = re.findall(POS_RX, text)
    neg = re.findall(NEG_RX, text)
    flags = []
    if re.search(REFUSAL_RX, text): flags.append('REVISIT_REFUSAL')
    if re.search(CONDITIONAL_RX, text) and (pos or neg): flags.append('CONDITIONAL')
    if re.search(LEFTOVER_RX, text): flags.append('LEFTOVER')
    if re.search(PORTION_SHORT_RX, text): flags.append('PORTION_SHORT')
    # '남은 피자 두 조각을 포장' describes quantity, not dislike: a leftover cue alone is not negative
    neg_real = [x for x in re.finditer(NEG_RX, text) if not re.match(LEFTOVER_RX, x.group(0))]
    if pos and neg_real: s = 'MIXED'
    elif neg_real: s = 'NEGATIVE'
    elif pos: s = 'POSITIVE'
    elif kind == 'decline': s = 'NEGATIVE'
    else: s = 'NEUTRAL'
    return s, flags, dict(positive=len(pos), negative=len(neg_real))


def _candidate_names(c):
    names = set(MS.venue_names(c.get('location')) or [])
    for k in ('label', 'location'):
        v = c.get(k)
        if isinstance(v, str) and len(v) >= 2 and not re.fullmatch(r'[A-Z_]+', v): names.add(v)
    return [n for n in names if n]


FEATURE_VENUE = {'pizzahill': 'PIZZA_HILL', 'myung': 'MYONGWOLGWAN', 'moegi': 'MOEGI', 'roomservice': 'ROOM_MEAL', 'buffet': 'THE_BUFFET',
                 'pavilion': 'THE_PAVILION', 'lepassage': 'LE_PASSAGE', 'footbath': 'footbath', 'riverpark': 'riverpark', 'indoor_pool': 'indoor_pool'}


def feature_links(raw_facts, candidates):
    """action_id -> fact ids whose source feature tag names that venue (e.g. pizzahill_revisit -> PIZZA_HILL).
    Source tags written when the fact was extracted; a link, not a polarity."""
    out = {}
    for c in candidates or []:
        loc = str(c.get('location') or ''); aid = c['action_id']
        for fid, f in (raw_facts or {}).items():
            for tag in (f or {}).get('features') or []:
                v = next((v for k, v in FEATURE_VENUE.items() if str(tag).startswith(k)), None)
                if v and (v == loc or v in aid): out.setdefault(aid, set()).add(fid)
    return out


GENERIC_NAMES = {'룸서비스', '인룸', '뷔페', '라운지', '수영장', '사우나', '피트니스', '족욕', '스파'}


def annotate(lean, kinds=None, venue_links=None):
    """Add stance, flags and candidate links to a copy of a lean (L) request. kinds: fact_id -> source kind.

    about: candidates a record names (venue name or alias), or whose shown menu groups/options list it as an
    experience. Engine coefficient evidence (m4.evidence_fact_ids) is not a link: a trait fact is not about a
    venue. A record whose source is not confirmed as this hotel links only through a distinctive venue name
    and is marked about_scope=UNCONFIRMED; shared services (room service, buffet, pool) never link that way."""
    out = copy.deepcopy(lean)
    cands = out.get('candidates') or []
    names = {c['action_id']: _candidate_names(c) for c in cands}
    linked = {}
    for c in cands:
        ids = set()
        for g in c.get('basket_groups') or []:
            ids |= set(g.get('experience_fact_ids') or [])
            for o in g.get('options') or []: ids |= set(o.get('experience_fact_ids') or [])
        linked[c['action_id']] = ids | set((venue_links or {}).get(c['action_id']) or [])
    for r in (out.get('personal') or {}).get('records') or []:
        kind = next((kinds.get(f) for f in r.get('fact_ids', []) if kinds and kinds.get(f)), None)
        s, flags, _ = stance(r.get('summary'), kind)
        r['stance'] = KO[s]
        if flags: r['flags'] = [FLAG_KO[f] for f in flags]
        text = str(r.get('summary') or '')
        wh = r.get('source_scope') == 'wh'
        about, unconfirmed = [], []
        for a, ns in names.items():
            by_id = bool(set(r.get('fact_ids', [])) & linked.get(a, set()))
            hit = [n for n in ns if n in text]
            if wh and (hit or by_id): about.append(a)
            elif not wh and [n for n in hit if n not in GENERIC_NAMES]: about.append(a); unconfirmed.append(a)
        if about: r['about'] = sorted(about)
        if unconfirmed: r['about_scope'] = 'UNCONFIRMED_SOURCE_NAMES_THIS_VENUE'
    party = (out.get('visit') or {}).get('party_size')
    if party:
        for c in cands:
            for g in c.get('basket_groups') or []:
                for o in g.get('options') or []:
                    if g.get('role', 'MEAL') == 'MEAL' and 'meal_equivalents' in o: o['party_fit'] = party_fit(o['meal_equivalents'], party)
    p = out.setdefault('personal', {})
    p['stance_note'] = ('stance·flags는 요약 문구에서 자동으로 읽은 표시이며 사람 검수 전입니다. 요약 원문이 우선합니다. '
                        'about은 그 기록이 언급한 후보입니다. about_scope가 있으면 이 호텔 경험인지 확인되지 않은 기록입니다.')
    rs = repeat_signal(out)
    if rs: out['repeat_signal'] = rs
    return out


def trim(lean):
    """Input reduction that removes repetition only (measured on the 2026-11-07 offline bench, ~1.7KB/request):
    the per-fact selection reasons (the decision record keeps them) and a menu option label that only repeats
    its own item labels. No record, id, summary, candidate, item, quantity or price is removed."""
    out = copy.deepcopy(lean)
    scope = (out.get('personal') or {}).get('evidence_scope')
    if isinstance(scope, dict): scope.pop('selection_reasons', None)
    for c in out.get('candidates') or []:
        for g in c.get('basket_groups') or []:
            for o in g.get('options') or []:
                if o.get('label') and o.get('items') and o['label'] == ' + '.join(str(i.get('label')) for i in o['items']):
                    del o['label']
    return out


WAIT_KEYS = ('wait_reconsider', 'public_rest', 'room_rest')


def repeat_signal(lean):
    """Two latest decisions: same wait/rest action and same reason, with no meal or time-slot change between.
    Returned as information for the model; nothing is forced."""
    rec = lean.get('recent_decisions') or []
    if len(rec) < 2: return None
    a, b = rec[-2], rec[-1]
    if a.get('action_id') != b.get('action_id') or a.get('action_id') not in WAIT_KEYS: return None
    same_reason = _norm(a.get('reason')) and _norm(a.get('reason')) == _norm(b.get('reason'))
    same_need = a.get('need') == b.get('need')
    if not (same_reason or same_need): return None
    return dict(action_id=b['action_id'], times=[a.get('time'), b.get('time')], same_reason=bool(same_reason),
                note='직전 두 결정이 같은 대기·휴식이었고 상태 변화가 기록되지 않았습니다. 새로 생긴 정보가 있는지 확인하고 다른 행동·식사·휴식·하루 종료를 다시 비교하세요. 다시 기다리는 것도 정상 선택입니다.')


def _norm(s):
    return re.sub(r'\s+', '', str(s or ''))[:80]


def integrity(personal_full, lean):
    """Compression check: the ids, scopes and summaries sent are the ones in the full evidence, every sent
    record has a stance, and no sent id is outside citable. Returns a list of problems (empty = ok)."""
    full = {f: r for r in (personal_full or {}).get('evidence_records', []) for f in r.get('fact_ids', [])}
    p = lean.get('personal') or {}
    sent = [f for r in p.get('records', []) for f in r.get('fact_ids', [])]
    cite = set(p.get('citable_fact_ids') or [])
    out = []
    for r in p.get('records', []):
        for f in r.get('fact_ids', []):
            src = full.get(f)
            if not src: out.append(('UNKNOWN_FACT', f)); continue
            if src.get('source_scope') != r.get('source_scope'): out.append(('SCOPE_CHANGED', f))
            if _norm(src.get('summary')) != _norm(r.get('summary')): out.append(('SUMMARY_CHANGED', f))
        if 'stance' not in r: out.append(('NO_STANCE', tuple(r.get('fact_ids', []))))
    if set(sent) - cite: out.append(('SENT_NOT_CITABLE', sorted(set(sent) - cite)))
    if cite - set(sent): out.append(('CITABLE_NOT_SENT', sorted(cite - set(sent))))
    return out


OVERRIDE_RX = r'대기|기다|시간|일정|늦|이른|지금|바로|가까|이동|영업|예약|기념|특별|동행|아이|부모|인원|비|날씨|피곤|허기|배고|가볍|다른 후보|대안|없(어|으)|만 (가능|남)|유일'


def diagnose(answer, lean, party_size=None):
    """Non-blocking review codes for one validated selection. Returns list of dicts(code, detail)."""
    out = []
    if not answer: return out
    sel = answer.get('selected_action_id'); reason = str(answer.get('reason') or '') + ' ' + str(answer.get('tradeoff_note') or '')
    p = lean.get('personal') or {}
    recs = p.get('records') or []
    cite = set(p.get('citable_fact_ids') or [])
    cited = set(answer.get('supporting_fact_ids') or []) | set(answer.get('counterevidence_fact_ids') or [])
    if cited - cite: out.append(dict(code='CITED_NOT_SENT', detail=sorted(cited - cite)))
    about_sel = [r for r in recs if sel in (r.get('about') or [])]
    hard = [r for r in about_sel if r.get('stance') == KO['NEGATIVE'] or '재방문 거부' in (r.get('flags') or [])]
    if hard:
        note = str(answer.get('tradeoff_note') or '')
        hard_ids = [f for r in hard for f in r['fact_ids']]
        explained = bool(note.strip()) and any(f in cited for f in hard_ids)
        clean = clean_alternatives(sel, lean)
        code = 'NEGATIVE_RECORD_ON_SELECTED_' + ('EXPLAINED' if explained else 'UNEXPLAINED')
        out.append(dict(code=code, detail=dict(facts=hard_ids, clean_same_type_alternatives=clean)))
    support = set(answer.get('supporting_fact_ids') or [])
    cand_names = {c['action_id']: _candidate_names(c) for c in lean.get('candidates') or []}
    named = lambda a: a in reason or any(n in reason for n in cand_names.get(a, []))
    for r in recs:
        # the reason uses a mixed record when it supports the choice, is about the selected candidate, or names
        # the candidate the record is about; a cited record the reason never uses is reported separately
        # (COUNTEREVIDENCE_FOR_UNNAMED_ALTERNATIVE), not as a one-sided reading
        if r.get('stance') != KO['MIXED'] or not set(r['fact_ids']) & cited: continue
        about = r.get('about') or []
        if not (set(r['fact_ids']) & support or sel in about or any(named(a) for a in about) or not about): continue
        has_pos = bool(re.search(POS_RX, reason)); has_neg = bool(re.search(NEG_RX, reason))
        if not (has_pos and has_neg): out.append(dict(code='MIXED_RECORD_ONE_SIDED', detail=r['fact_ids']))
    left = [r for r in about_sel if '남김' in (r.get('flags') or [])]
    if left and party_size:
        eq = selected_equivalents(answer, lean)
        if eq is not None and eq > party_size:
            why = str((answer.get('meal_assessment') or {}).get('quantity_reason') or '') + ' ' + reason
            out.append(dict(code='QUANTITY_ABOVE_PARTY_DESPITE_LEFTOVER',
                            detail=dict(equivalents=eq, party=party_size, facts=[f for r in left for f in r['fact_ids']],
                                        leftover_mentioned=bool(re.search(r'남(았|은|기|겨)', why)),
                                        intent_stated=bool(re.search(r'추가로|더 (먹|시키)|포장해 (가|갈)|다음 (식사|끼니)|야식|기념|특별', why)))))
    short = [r for r in recs if '양 부족' in (r.get('flags') or [])]
    party = party_size or (lean.get('visit') or {}).get('party_size')
    if party and answer.get('selected_basket_id'):
        eq = selected_equivalents(answer, lean, known_only=True)
        why = str((answer.get('meal_assessment') or {}).get('quantity_reason') or '') + ' ' + reason
        if eq is not None and eq <= party and short:
            out.append(dict(code='QUANTITY_AT_OR_BELOW_PARTY_DESPITE_SHORTFALL_RECORD',
                            detail=dict(equivalents=eq, party=party, facts=[f for r in short for f in r['fact_ids']],
                                        shortfall_mentioned=bool(re.search(r'부족|모자|양이|넉넉|배고', why)))))
        elif eq is not None and eq < party:
            out.append(dict(code='QUANTITY_BELOW_PARTY', detail=dict(equivalents=eq, party=party)))
    names = {c['action_id']: _candidate_names(c) for c in lean.get('candidates') or []}
    alt = answer.get('rejected_alternative') or {}
    said = reason + ' ' + str(alt.get('action_id') or '') + ' ' + str(alt.get('reason') or '')
    counter = set(answer.get('counterevidence_fact_ids') or [])
    for r in recs:
        if not set(r['fact_ids']) & counter: continue
        others = [a for a in (r.get('about') or []) if a != sel]
        if others and sel not in (r.get('about') or []) and not any(a in said or any(n in said for n in names.get(a, [])) for a in others):
            out.append(dict(code='COUNTEREVIDENCE_FOR_UNNAMED_ALTERNATIVE', detail=dict(facts=r['fact_ids'], about=others)))
    if lean.get('repeat_signal') and sel == lean['repeat_signal']['action_id']:
        out.append(dict(code='REPEATED_WAIT_AFTER_SIGNAL', detail=lean['repeat_signal'].get('times')))
    return out


def clean_alternatives(sel, lean):
    """Other shown candidates of the selected type with no negative/refusal record about them and no longer wait."""
    cands = {c['action_id']: c for c in lean.get('candidates') or []}
    me = cands.get(sel) or {}
    recs = (lean.get('personal') or {}).get('records') or []
    bad = {a for r in recs if r.get('stance') == KO['NEGATIVE'] or '재방문 거부' in (r.get('flags') or []) for a in r.get('about') or []}
    wait = lambda c: (c.get('conditions') or {}).get('wait_minutes') or 0
    return sorted(a for a, c in cands.items() if a != sel and c.get('type') == me.get('type') and a not in bad and wait(c) <= wait(me))


def selected_equivalents(answer, lean, known_only=False):
    """meal_equivalents of the selected basket; without it, the item count (known_only=False) or None."""
    b = answer.get('selected_basket_id')
    if not b: return None
    for c in lean.get('candidates') or []:
        for g in c.get('basket_groups') or []:
            for o in g.get('options') or []:
                if o.get('basket_id') == b:
                    if o.get('meal_equivalents') is not None: return o['meal_equivalents']
                    if known_only: return None
                    return sum(int(i.get('quantity') or 0) for i in o.get('items') or []) or None
    return None


SYSTEM_LINES = [
    'personal.records의 stance(긍정·부정·혼합·서술)와 flags(재방문 거부·조건부·남김·양 부족)는 요약 문구에서 자동으로 읽은 표시이며 검수 전입니다. 요약 원문이 표시보다 우선합니다.',
    'about에 후보 action_id가 있는 기록은 이 호텔에서 그 후보를 언급한 경험입니다. 부정이거나 재방문 거부인 기록이 있는 후보를 고를 때는, 이번에 그 단점보다 강한 현재 조건(대기·시간·일정·동행·방문 목적·다른 후보의 제약)을 tradeoff_note에 구체적으로 적고 그 기록 id를 counterevidence_fact_ids에 넣으세요. 그런 조건이 없다면 다른 후보와 다시 비교해 고르세요.',
    '혼합 기록을 이유로 쓸 때는 좋았던 점과 아쉬웠던 점을 함께 적으세요. 조건부 기록(예: 특별한 날이 아니면)은 그 조건이 이번 방문에 해당하는지 visit.purpose로 판단하세요. visit.purpose가 미확인이면 해당하지 않는 것으로 봅니다.',
    '남김 표시가 있는 기록이 있으면 과거에 양이 많았다는 참고입니다. options의 meal_equivalents나 수량이 인원보다 많은 구성을 고를 때는 나눠 먹기·추가 메뉴 등 이유를 meal_assessment.quantity_reason에 적으세요. 과거 주문량이 이번 식사량의 절대 제한은 아닙니다.',
    '조식 후보의 conditions.included가 객체이면 객실 계약으로 일부 인원의 조식이 포함된 경우입니다: included_persons는 추가 비용 없이 이용할 수 있는 인원, paid_persons와 price_krw는 포함되지 않은 인원의 추가 비용입니다. 조식을 건너뛰면 포함된 인원의 조식도 이용하지 않게 됩니다.',
    '식사 options의 party_fit은 meal_equivalents(일반 1인분 환산 가정, 섭취 관측 아님)를 visit.party_size와 비교한 표시입니다. 인원과 같음은 여유가 없다는 뜻이고 인원보다 적음이면 부족할 수 있습니다. 양 부족 표시가 있는 기록이 있으면 그 경험과 동행 인원을 함께 고려하세요. 양을 늘리라는 지시가 아니며, 고른 양의 이유를 meal_assessment.quantity_reason에 적으세요.',
    'repeat_signal이 있으면 직전 두 번 같은 대기·휴식을 같은 이유로 골랐다는 뜻입니다. 그 사이 바뀐 정보가 있는지 확인하고 식사·활동·휴식·하루 종료를 다시 비교하세요. 다시 기다리는 것도 정상이며 강제되지 않습니다.',
    '기록이 없거나 근거가 약하면 일반적인 상황 판단으로 고르고, 그 사실을 reason에 짧게 밝히세요.',
]
OUTPUT_LINE = 'tradeoff_note는 부정·재방문 거부·혼합 기록이 있는 후보를 고르거나 과거와 다른 양을 고를 때 그 선택을 정당화하는 현재 조건 한 문장이며, 해당 없으면 null입니다.'


# V19LS-P2 research (party-subset breakfast, one-time meal quantity review): extra lines, V19LS unchanged.
P2_LINES = [
    '조식 포함 고객은 특별한 사정이 없으면 포함된 조식을 이용하는 것이 기본입니다. 늦잠·운영시간 충돌, 이른 체크아웃·외부 일정, 컨디션 저하·식욕 부족, 전날 식사·음주로 인한 포만, 구체적인 조식 기피 경험, 동행과 다른 아침 계획처럼 이번 방문에 해당하는 사정이 있을 때만 다르게 고르세요. 과거에 조식을 건너뛴 기록은 그 이유가 이번에도 해당하는지 확인하고, 확률이나 비율을 정하지 마세요.',
    '조식 후보의 conditions.included.diners가 일행 인원보다 적으면 일부 인원만 먹는 후보입니다(not_eating 명은 먹지 않음, waived_included 명은 객실 포함 조식을 쓰지 않음). 일부 인원만 먹는 후보를 고르면 meal_assessment.modeled_diners는 diners와 같아야 합니다.',
]


def system(base, extra=()):
    """Insert the stability lines (and research extras) before the output block of an LS system prompt."""
    head, sep, tail = base.partition('\n응답 작성:')
    assert sep, 'LS system prompt layout changed'
    head = head.replace('기록의 긍정·부정은 표시돼 있지 않으니 요약을 읽고 판단하세요. ', '')
    head = head.replace('experience_fact_ids는 그 식당·메뉴를 언급한 후기이며 긍정·부정이 표시돼 있지 않으니 요약을 읽고 판단하세요. ', 'experience_fact_ids는 그 식당·메뉴를 언급한 후기입니다. ')
    return head + '\n' + '\n'.join(SYSTEM_LINES + list(extra)) + sep + tail + '\n' + OUTPUT_LINE


def schema(base):
    s = copy.deepcopy(base)
    s['properties']['tradeoff_note'] = {'type': ['string', 'null']}
    s['required'] = sorted(s['properties'])
    return s


# Day-end review re-plan (P5 finding). The shared review accepts a reviewed day end only when the
# reason names a remaining candidate by its full label or action id. In P5, 4/24 visits (2 per
# policy) stopped at 21:28-21:32 because the second answer wrote "룸서비스 식사는…" for the label
# "객실 룸서비스". V19LS also accepts a distinctive word of the label (3+ characters, not a generic
# place word) but only inside a clause that states a comparison or a decision about that candidate
# (보다·대신·않·없·필요·생략…). A bare mention ("룸서비스 룸서비스", "룸서비스가 좋았다") is not a
# comparison. The first early day end is still rejected and must be re-planned; V17/V18 unchanged.
LABEL_STOPWORDS = {'객실', '레스토랑', '라운지', '카페', '산책', '휴식', '이용', '식사', '코스', '세트', '메뉴', '서비스', '호텔', '워커힐'}
COMPARE_CUE = re.compile(r'보다|대신|말고|않|없|필요|생략|건너|미루|다음에|내일|굳이|비교|제외|원하지|이미|충분|부담|추가로?|더 먹|배부|포만')
CLAUSE_SPLIT = re.compile(r'[.!?;\n]|(?<=[다요])[,\s]')


def label_words(label):
    return [w for w in re.split(r'[\s·()/,]+', str(label or '')) if len(w) >= 3 and w not in LABEL_STOPWORDS]


def compared_by(text, actions, keys):
    """How text names a compared candidate: 'ID', 'LABEL', 'DISTINCTIVE_WORD_IN_COMPARISON' or None."""
    text = str(text or '')
    for k in keys:   # structured: rejected_alternative.action_id is a remaining candidate (why_not_other_plans = "id: reason")
        if text.startswith(k + ':') and len(text) > len(k) + 3: return 'STRUCTURED_ALTERNATIVE'
    for k in keys:
        label = (actions.get(k) or {}).get('label') or ''
        if k in text: return 'ID'
        if label and label in text: return 'LABEL'
    clauses = [c for c in CLAUSE_SPLIT.split(text) if c and c.strip()]
    for k in keys:
        words = label_words((actions.get(k) or {}).get('label'))
        for c in clauses:
            for w in words:
                if w in c and COMPARE_CUE.search(c.replace(w, ' ')):
                    return 'DISTINCTIVE_WORD_IN_COMPARISON'
    return None


def names_compared(text, actions, keys):
    return compared_by(text, actions, keys) is not None


DAY_END_REVIEW_HINT = (' 비교한 남은 후보 하나를 rejected_alternative.action_id에 그 후보의 action_id로 적고, '
                       'reason에 그 후보를 고르지 않는 현재 이유를 쓰세요(휴식 후보가 아니라 남은 식사·활동 후보).')


INCLUDED_KEY = 'ROOM_BREAKFAST_INCLUDED_CONTRACT'


def party_breakfast_variants(offer, party_size, compose):
    """V19LS-P2: from a party breakfast of N adults with the same entitlement terms, in which the room contract
    covers k of them, add the choices in which only m of them eat (1 <= m < N): min(m, k) included at no cost,
    max(0, m - k) paid, N - m not eating; when m < k, k - m included breakfasts are left unused. Built from the
    same registered sale units and prices (compose), so quantities, unit prices and totals stay integer and match
    the ledger. Not generated with child menus, for a whole-party inclusion, without a partial room contract,
    or for a one-person party (nothing to leave out). No eligibility or child price is assumed."""
    c = (offer or {}).get('sku_contract') or {}
    parts = c.get('components') or []
    if not offer.get('hc_contract') or offer.get('hc_included') or not parts: return []
    inc = [p for p in parts if p.get('included_benefit') == INCLUDED_KEY]
    paid = [p for p in parts if not p.get('included_benefit')]
    if len(inc) != 1 or len(paid) != 1 or any(p.get('role') != 'MAIN' for p in parts) or inc[0].get('sku_id') != paid[0].get('sku_id'): return []
    k, extra = inc[0]['billing_quantity'], paid[0]['billing_quantity']
    if k + extra != party_size or party_size < 2: return []
    out = []
    for m in range(1, party_size):
        use, buy = min(m, k), max(0, m - k)
        lines = [dict(inc[0], billing_quantity=use)] + ([dict(paid[0], billing_quantity=buy)] if buy else [])
        v = compose(lines, m)
        v.update(participant_count=m, candidate_available_at=c.get('candidate_available_at'), room_breakfast_contract=dict(covered_adults=k),
                 party_breakfast=dict(diners=m, party=party_size, included=use, paid=buy, not_eating=party_size - m, waived_included=k - use,
                                      basis='PARTY_SUBSET_BREAKFAST_V19LS_P2'))
        note = f"객실 포함 {use}명" + (f" · 추가 결제 {buy}명" if buy else '') + f" · {party_size - m}명 미이용" + (f" · 포함 조식 {k - use}명분 미사용" if k > use else '')
        o = dict(offer, id=f"{offer['id']}#D{m}", sku_contract=v, venue=offer.get('venue'), label=f"{offer['label']} · {m}명 이용({note})",
                 party_breakfast=v['party_breakfast'], price_pp_krw=None)
        o['food'] = dict(offer.get('food') or {}, meal_fraction=round((offer.get('food') or {}).get('meal_fraction', 1) * m / party_size, 4))
        out.append(o)
    return out


def breakfast_inclusion(row, contract):
    """V19LS breakfast candidate: mark room-contract coverage per line and in the conditions (information only).
    The engine's items, quantities and total are not changed."""
    parts = (contract or {}).get('components') or []
    inc = sum(p.get('billing_quantity') or 0 for p in parts if p.get('included_benefit'))
    if not inc: return row
    paid = sum(p.get('billing_quantity') or 0 for p in parts if not p.get('included_benefit') and p.get('role') == 'MAIN')
    cond = row.setdefault('conditions', {})
    cond['included'] = dict(status='PARTIAL' if paid else 'ALL', included_persons=inc, paid_persons=paid,
                            extra_cost_krw=cond.get('price_krw'), basis='ROOM_BREAKFAST_CONTRACT')
    pb = (contract or {}).get('party_breakfast')
    if pb: cond['included'].update(diners=pb['diners'], not_eating=pb['not_eating'], waived_included=pb.get('waived_included', 0))
    lines = row.get('item_contracts') or []
    for line, part in zip(lines, parts):
        if line.get('sku_id') == part.get('sku_id') and line.get('quantity') == part.get('billing_quantity'):
            line['price_basis'] = '객실 조식 포함(추가 비용 없음)' if part.get('included_benefit') else '추가 결제'
    return row


MEAL_QUANTITY_REVIEW = 'MEAL_QUANTITY_REVIEW_SHORTFALL_RECORD'


def quantity_summary(answer, lean, party):
    eq = selected_equivalents(answer, lean, known_only=True)
    ma = answer.get('meal_assessment') or {}
    return dict(equivalents=eq, party=party, cited=sorted(set(answer.get('supporting_fact_ids') or []) | set(answer.get('counterevidence_fact_ids') or [])),
                quantity_reason=ma.get('quantity_reason'))


def relevant_shortfall(answer, lean):
    """Shortfall records that bear on this meal: about the selected candidate or naming it, or a general record
    (no hotel candidate attached or named). A record about another candidate, or naming only another
    candidate, is that place's experience and does not count here."""
    sel = answer.get('selected_action_id')
    names = {c['action_id']: _candidate_names(c) for c in lean.get('candidates') or []}
    out = []
    for r in (lean.get('personal') or {}).get('records') or []:
        if '양 부족' not in (r.get('flags') or []): continue
        about = r.get('about') or []; text = r.get('summary') or ''
        mentions = {a for a, ns in names.items() if any(n and n in text for n in ns)}
        if sel in about or sel in mentions: out.append(r)
        elif not about and not mentions: out.append(r)
    return out


def meal_quantity_review(answer, lean, party, prior):
    """V19LS-P2, at most once per decision: a past 'not enough food' record that bears on this meal (same place or a
    general record), and a choice whose usual-portion equivalents are at or below the party size with no account of
    quantity in the reason. Citing the record alone does not settle it; an account of the quantity does. The
    second answer stands whatever quantity it keeps (no forced upsizing)."""
    if str((prior or {}).get('reason', '')).startswith(MEAL_QUANTITY_REVIEW) or not party or not answer.get('selected_basket_id'): return
    eq = selected_equivalents(answer, lean, known_only=True)
    if eq is None or eq > party: return
    short = relevant_shortfall(answer, lean)
    if not short: return
    why = str((answer.get('meal_assessment') or {}).get('quantity_reason') or '') + ' ' + str(answer.get('reason') or '') + ' ' + str(answer.get('tradeoff_note') or '')
    if re.search(r'부족|모자라|모자랐|넉넉|배고프|양이 (적|많|충분)|더 (시키|주문)|추가로', why): return
    facts = [f for r in short for f in r['fact_ids']]
    raise ValueError(f"{MEAL_QUANTITY_REVIEW}: 이 식사와 관련된 과거 양 부족 기록({', '.join(facts)})이 있는데 일반 환산 {eq}인분을 {party}명이 먹는 구성을 골랐고 양에 대한 설명이 없습니다. "
                     "그 기록과 지금의 인원·직전 식사·포만을 비교해 양을 다시 정하세요. 그대로 두려면 quantity_reason에 이유를 적으세요(기록 인용만으로는 설명이 되지 않습니다). 더 많이 주문하라는 지시가 아닙니다.")


# ------------------------------------------------------------------ V19LS-P2: included breakfast default with exceptions
BREAKFAST_DEFAULT = 'RULE_DEFAULT_INCLUDED_BREAKFAST'
BREAKFAST_FORFEIT_REVIEW = 'INCLUDED_BREAKFAST_FORFEIT_REVIEW'
# Words that tie a record, intention or recent action to this morning: breakfast itself, waking, leaving early, condition,
# fullness or drinking, aversion. A match sends the decision to the model; nothing is removed from what it sees.
MORNING_TERMS = re.compile(r'조식|아침|브런치|뷔페|늦잠|기상|일찍|이른|체크아웃|퇴실|외출|숙취|과음|음주|술|포만|배불|배부르|입맛|식욕|컨디션|몸살|아프')
LATE_ACTS = re.compile(r'BAR|WINE|LATE|PUB|LOUNGE|와인|맥주|칵테일|술|야식', re.I)


def _whole_party_included(row, party):
    inc = (row.get('conditions') or {}).get('included')
    if (row.get('conditions') or {}).get('price_krw'): return False
    if inc is True: return True
    return isinstance(inc, dict) and inc.get('status') == 'ALL' and inc.get('diners', party) == party


def breakfast_route(rows, records, memory, fatigue, recent, minutes_left, party):
    """Which of the three breakfast situations this is (b3582ba3 section 3):
      RULE_DEFAULT_INCLUDED_BREAKFAST  the whole party is included, one included option, no sign of an exception -> no model call
      LLM_EXCEPTION_CHECK              included, but a record / intention / state / schedule may make this morning different
      LLM_EXTRA_PAYMENT_OR_PARTY       extra payment or a partly covered party (who eats) -> the model chooses
    The rule never assigns a probability and never removes a Fact; it only decides whether a model call is needed."""
    meals = [r for r in rows if r['action_id'] != 'SKIP_BREAKFAST']
    whole = [r for r in meals if _whole_party_included(r, party)]
    if not whole or len(meals) != len(whole):
        return dict(route='LLM_EXTRA_PAYMENT_OR_PARTY', reasons=['PAID_OR_PARTLY_COVERED_OPTION'])
    reasons = []
    if len(whole) > 1: reasons.append('SEVERAL_INCLUDED_OPTIONS')
    hits = sorted({f for r in records or [] for f in r.get('fact_ids') or []
                   if MORNING_TERMS.search(' '.join([r.get('summary') or ''] + list(r.get('flags') or []) + list(r.get('about') or [])))
                   or any('BREAKFAST' in str(x).upper() for x in r.get('about') or [])})
    if hits: reasons.append('PERSONAL_RECORD:' + ','.join(hits))
    prior = [d for d in (memory or {}).get('breakfast_decisions') or [] if str(d.get('outcome', '')).startswith('VOLUNTARY_NONUSE')]
    if prior: reasons.append('SKIPPED_EARLIER_THIS_VISIT')
    if any(MORNING_TERMS.search(str(x)) for x in (memory or {}).get('pending_intentions') or []): reasons.append('PENDING_INTENTION')
    if (fatigue or {}).get('level') == '피곤': reasons.append('TIRED')
    if any(LATE_ACTS.search(' '.join(str(x.get(k) or '') for k in ('act', 'label', 'loc'))) for x in recent or []): reasons.append('LATE_DRINK_OR_FOOD_BEFORE')
    if minutes_left is not None and minutes_left < max(r.get('duration') or 60 for r in whole) + 60: reasons.append('TIGHT_SCHEDULE')
    if reasons: return dict(route='LLM_EXCEPTION_CHECK', reasons=reasons)
    return dict(route=BREAKFAST_DEFAULT, action_id=whole[0]['action_id'], reasons=[],
                basis='WHOLE_PARTY_INCLUDED; ONE_INCLUDED_OPTION; NO_MORNING_EXCEPTION_SIGN_IN_RECORDS_INTENTIONS_STATE_SCHEDULE')


def default_breakfast_answer(row, party):
    """The default as a selection in the model's answer shape, labelled as a rule decision (not a model statement)."""
    return dict(selected_action_id=row['action_id'], selected_basket_id=None,
                reason='규칙 기본 판단: 일행 전원 조식 포함 · 추가 비용 없음 · 이번 아침에 해당하는 예외 근거 없음(모델 호출 없음)',
                supporting_fact_ids=[], counterevidence_fact_ids=[], rejected_alternative=dict(action_id='SKIP_BREAKFAST', reason='예외 근거가 없어 기본 선택을 유지'),
                next_intent=None, current_need_assessment=dict(state='UNCERTAIN', reason='규칙 판단 시점에는 모델의 필요 평가가 없습니다'),
                meal_assessment=dict(kind='FULL_MEAL', modeled_diners=party, sharing_plan='각자 뷔페 이용(규칙 기본 가정)',
                                     quantity_reason='포함 인원 기준 계약 수량(규칙 기본 가정)', expected_satiety='UNCERTAIN'),
                tradeoff_note=None)


def forfeit_review(answer, rows, records, memory, party, prior):
    """One-time check (never forced): skipping an included breakfast again this visit with no concrete reason.
    A concrete reason is a cited Fact or an exception named in the reason. The second answer stands."""
    if prior or answer.get('selected_action_id') != 'SKIP_BREAKFAST': return
    if not any(_whole_party_included(r, party) or isinstance((r.get('conditions') or {}).get('included'), dict) for r in rows if r['action_id'] != 'SKIP_BREAKFAST'): return
    if not [d for d in (memory or {}).get('breakfast_decisions') or [] if str(d.get('outcome', '')).startswith('VOLUNTARY_NONUSE')]: return
    if answer.get('supporting_fact_ids') or answer.get('counterevidence_fact_ids') or MORNING_TERMS.search(answer.get('reason') or ''): return
    raise ValueError(BREAKFAST_FORFEIT_REVIEW + ': 이번 방문에서 포함 조식을 다시 건너뜁니다. 이번 아침에 해당하는 사정(일정·컨디션·포만·기피·동행 계획)이 있으면 근거와 함께 적고, 없다면 다시 고려하세요. 다시 고른 답은 그대로 따릅니다.')
