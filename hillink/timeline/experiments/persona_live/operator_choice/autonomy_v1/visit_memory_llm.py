"""Research: LLM policy V19LS_MEM1 — multi-day visit memory (never the default; V19LS is unchanged).

V19LS's lean request tells a next-day decision only how many meals were eaten on earlier days
(`today.earlier_days_meals`). MEM1 sends what this customer actually did on the earlier days of this visit:

  - meals: place, period, time, order (items x quantity), hotel order total, included-benefit quantity, the model's own
    meal intent / expected satiety at the time (labelled as the model's assumption, intake never observed)
  - a day without a dinner record: when the day ended, the fatigue level then, and the last decisions while dinner
    was still open (what the record shows, no invented cause)
  - facilities visited (executed activities, travel excluded) and benefits used (included breakfast / facilities)
  - per executed decision: choice, the model's short reason, cited Fact ids, the stated next intent, the need state
  - the intentions still open at the end of the previous day (intentions, not experiences)
  - on today's candidates: `earlier_use` when the same venue / facility was used on an earlier day

Only executed records enter (decision records with execution_state EXECUTED, executor meal and activity records).
Nothing is generated: a field with no record is absent. The log is kept in the visit memory under `mem1_log`, which
carries across days with the rest of the memory and is not shown in the `memory` block (to avoid duplication).
"""
import copy

LOG_KEY = 'mem1_log'
POLICY_TAG = 'V19LS_MEM1'
LINES = [
    'earlier_days는 이번 가상 방문의 앞선 날 실제 실행 기록(식사·주문·이용 시설·혜택 사용·결정 이유·하루 종료 상태)입니다. 후기 사실이 아니며 실제 섭취량과 만족은 관측되지 않았습니다.',
    '오늘 후보를 비교할 때 전날 같은 업장·시설을 이용했는지(candidates의 earlier_use), 전날 식사량과 마지막 식사 시각, 전날 비교만 하고 보류한 후보, 남은 계획과 이미 쓴 혜택, 아직 경험하지 않은 대안을 확인하세요.',
    '반복도 변경도 강제되지 않습니다. 같은 곳을 다시 고르면 개인 기록이나 현재 상황의 이유를, 바꾸면 그 이유를 reason에 짧게 밝히세요.',
]
NON_FACILITY_DOMAINS = ('이동', '대기')
PLACE_KO_FALLBACK = {'THE_PAVILION': '파빌리온'}   # venues missing from the shared Korean label table (MEM1 display only)
GENERIC_PLACE_SUFFIXES = ('_ROOM', '_LOBBY')       # a room or lobby is not a facility the customer chose to revisit


def clock(m):
    return None if m is None else '%02d:%02d' % (m // 60, m % 60)


def sync(a, actions_label=None):
    """Append every executed decision of today not yet in the visit memory log (idempotent by date+minute+action)."""
    memory = a.__dict__.setdefault('_autonomous_memory', {})
    log = memory.setdefault(LOG_KEY, [])
    seen = {(x['date'], x['minute'], x['action_id']) for x in log}
    for d in getattr(a, '_autonomous_decisions', []):
        plan = d.get('selected_plan') or {}
        if d.get('execution_state') != 'EXECUTED' or not plan.get('action_id'):
            continue
        key = (d.get('date'), d.get('minute'), plan['action_id'])
        if key in seen:
            continue
        need = (plan.get('current_need_assessment') or {}).get('state')
        ma = plan.get('meal_assessment') or {}
        after = d.get('state_after') or {}
        log.append(dict(date=d.get('date'), minute=d.get('minute'), time=clock(d.get('minute')), action_id=plan['action_id'],
                        label=(actions_label or {}).get(plan['action_id']), owner=d.get('selection_owner'),
                        reason=plan.get('decision_summary') if str(d.get('selection_owner', '')).startswith('LLM') else None,
                        fact_ids=sorted(set(plan.get('supporting_fact_ids') or [])),
                        counter_fact_ids=sorted(set(plan.get('counterevidence_fact_ids') or [])),
                        next_intent=(plan.get('pending_intentions') or [None])[0], need=need,
                        compared_not_chosen=(plan.get('why_not_other_plans') or None) if str(d.get('selection_owner', '')).startswith('LLM') else None,
                        meal_intent=ma.get('kind'), expected_satiety=ma.get('expected_satiety'),
                        meals_done_after={k: v for k, v in (after.get('meals') or {}).items()} or None,
                        status='EXECUTED_DECISION_RECORD'))
        seen.add(key)
    return log


def note_execution(a, t, actions, fatigue_before, fatigue_after):
    """Called right after an executed step (shared execution path): log it with the fatigue level before and after
    execution (a day end resets fatigue, so the state at the decision is the one before) and the included flag."""
    log = sync(a, {k: x.get('label') for k, x in (actions or {}).items()})
    for x in reversed(log):
        if x['date'] == a.sc.get('date') and x['minute'] == t:
            x['fatigue_before'] = {k: (fatigue_before or {}).get(k) for k in ('level', 'ratio_percent')}
            x['fatigue_after'] = {k: (fatigue_after or {}).get(k) for k in ('level', 'ratio_percent')}
            inc = (actions or {}).get(x['action_id'], {}).get('included')
            if inc is not None:
                x['included'] = bool(inc)
            break


def place_ko(venue, venue_ko):
    if venue == 'EXTERNAL_DELIVERY':
        return '외부 배달'
    if str(venue or '').endswith('_ROOM'):
        return '객실(룸서비스)'
    return venue_ko.get(venue) or PLACE_KO_FALLBACK.get(venue, venue)


def _meal_row(m, venue_ko, covered):
    order = [dict(label=i.get('label'), quantity=i.get('quantity')) for i in (m.get('order') or [])][:6]
    out = dict(period=m.get('period'), place=place_ko(m.get('venue'), venue_ko),
               start=clock(m.get('start')) if isinstance(m.get('start'), int) else m.get('start_time'),
               end=clock(m.get('end')) if isinstance(m.get('end'), int) else m.get('end_time'),
               order=order, hotel_order_total_krw=m.get('order_total_krw'), party_size=m.get('party_size'))
    st = m.get('start') if isinstance(m.get('start'), int) else None
    if st is not None:
        by_clock = 'breakfast' if st < 11 * 60 else 'lunch' if st < 17 * 60 else 'dinner'
        if by_clock != m.get('period'):
            out['period_by_start_time'] = by_clock   # the engine's period label is the service class at decision time
    pm = m.get('portion_model') or {}
    if pm.get('meal_equivalents') is not None:
        out['meal_equivalents'] = pm.get('meal_equivalents')
    ass = m.get('assessment') or {}
    if ass:
        out['model_assumption_at_the_time'] = dict(kind=ass.get('kind'), modeled_diners=ass.get('modeled_diners'), expected_satiety=ass.get('expected_satiety'))
    if m.get('period') == 'breakfast' and covered:
        out['included_benefit'] = dict(covered_adults=covered, note='객실 패키지 조식 포함 인원')
    return out


def earlier_days(c, a, venue_ko):
    """The MEM1 block for today's request, from the full (pre-lean) context and the visit memory."""
    today = (c.get('visit') or {}).get('date')
    memory = getattr(a, '_autonomous_memory', {}) or {}
    log = [x for x in memory.get(LOG_KEY, []) if x.get('date') and x['date'] < today]
    meals = [m for m in c.get('meal_experiences') or [] if m.get('date') and m['date'] < today]
    acts = [x for x in c.get('activity_experiences') or [] if x.get('date') and x['date'] < today]
    covered = ((c.get('visit') or {}).get('breakfast') or {}).get('covered_adults')
    days = []
    for date in sorted({x['date'] for x in log} | {m['date'] for m in meals} | {x['date'] for x in acts}):
        dl = [x for x in log if x['date'] == date]
        inc = {x['action_id']: x['included'] for x in dl if 'included' in x}
        dm = [m for m in meals if m['date'] == date]
        da = [x for x in acts if x['date'] == date and x.get('domain') not in NON_FACILITY_DOMAINS + ('식사',) and x.get('selected_action_id')
              and x.get('selected_action_id') not in ('end_day_in_room', 'leave_visit')]
        day = dict(date=date, meals=[_meal_row(m, venue_ko, covered) for m in dm],
                   visited=[dict(time=x.get('start_time'), label=x.get('label'), action_id=x.get('selected_action_id'),
                                 **({'included': inc[x['selected_action_id']]} if x['selected_action_id'] in inc else {})) for x in da][:12],
                   decisions=[{k: x.get(k) for k in ('time', 'action_id', 'label', 'reason', 'fact_ids', 'counter_fact_ids', 'compared_not_chosen', 'next_intent', 'need')
                               if x.get(k) not in (None, [], '')} for x in dl if x.get('owner') and str(x['owner']).startswith('LLM')][-12:])
        end = next((x for x in reversed(dl) if x.get('action_id') in ('end_day_in_room', 'leave_visit')), None)
        if end:
            day['day_end'] = dict(time=end.get('time'), fatigue_when_ending=end.get('fatigue_before'), meals_done=end.get('meals_done_after'))
        if not any(m.get('period') == 'dinner' for m in dm):
            open_after = [x for x in dl if (x.get('meals_done_after') or {}).get('dinner') is False]
            day['no_dinner_record'] = dict(note='이 날 저녁 식사 실행 기록이 없음(원인은 아래 기록으로만 판단)',
                                           day_end_time=end.get('time') if end else None, fatigue_when_ending=end.get('fatigue_before') if end else None,
                                           last_choices_while_dinner_open=[dict(time=x.get('time'), action_id=x.get('action_id')) for x in open_after][-3:])
        days.append(day)
    out = dict(status='EXECUTED_SIMULATION_RECORDS_OF_THIS_VISIT_NOT_REVIEW_FACTS; INTAKE_AND_SATISFACTION_NOT_OBSERVED', days=days)
    if memory.get('pending_intentions'):
        out['open_intentions_from_last_decision'] = dict(items=list(memory['pending_intentions']), status='INTENTION_NOT_EXPERIENCE')
    return out


def mark_candidates(cands, c, a):
    """`earlier_use` on today's candidates used on an earlier day of this visit (same venue for meals, same action or
    place for activities). Record only, no preference."""
    today = (c.get('visit') or {}).get('date')
    meals = [m for m in c.get('meal_experiences') or [] if m.get('date') and m['date'] < today]
    acts = [x for x in c.get('activity_experiences') or [] if x.get('date') and x['date'] < today]
    marked = 0
    for x in cands or []:
        uses = []
        if x.get('type') == 'MEAL':
            for m in meals:
                if m.get('venue') and m.get('venue') == x.get('location'):
                    uses.append(dict(date=m['date'], period=m.get('period'), order=[i.get('label') for i in (m.get('order') or [])][:4]))
        elif x.get('type') == 'ACTIVITY':
            place = x.get('location')
            same_place_ok = bool(place) and not str(place).endswith(GENERIC_PLACE_SUFFIXES)
            for y in acts:
                if y.get('domain') in NON_FACILITY_DOMAINS or not y.get('selected_action_id'):
                    continue
                if y.get('selected_action_id') == x.get('action_id'):
                    uses.append(dict(date=y['date'], time=y.get('start_time'), label=y.get('label')))
                elif same_place_ok and y.get('location') == place:
                    # e.g. the day-time and the night footbath are two options at the same facility (Sky Yard)
                    uses.append(dict(date=y['date'], time=y.get('start_time'), label=y.get('label'), same_place_other_option=True))
        if uses:
            x['earlier_use'] = dict(times=len(uses), last=uses[-3:])
            marked += 1
    return marked


EARLIER_WORDS = ('어제', '전날', '지난', '다시', '또 ', '한 번 더', '재방문', '이미', '앞서')


def repeat_check(full):
    """Before the call: every shown candidate already used on an earlier day, with what the request carried about it
    (times used, personal evidence linked to it, how the rule engine shortlisted it). Record only."""
    out = []
    for c in full.get('candidates') or []:
        eu = c.get('earlier_use')
        if not eu:
            continue
        m4 = c.get('m4') or {}
        direct = sorted(set(m4.get('direct_evidence_fact_ids') or []))
        # evidence_fact_ids also carry Fact ids of general trait terms (e.g. a price-comparison tendency attached to
        # every priced venue); only a direct link is evidence about THIS venue or activity (v20b: Pizza Hill showed
        # travel-booking Facts of the value-check trait)
        out.append(dict(action_id=c['action_id'], type=c.get('type'), times_before=eu.get('times'),
                        personal_evidence_fact_ids=direct,
                        general_trait_fact_ids=sorted(set(m4.get('evidence_fact_ids') or []) - set(direct)),
                        same_place_other_option=any(u.get('same_place_other_option') for u in eu.get('last') or []),
                        shown_because=m4.get('shown_because'), rank_in_type=m4.get('rank_in_type'), of=m4.get('of')))
    return dict(candidates=out, shown=len(full.get('candidates') or []),
                not_used_before=[c['action_id'] for c in full.get('candidates') or [] if not c.get('earlier_use') and c.get('type') in ('MEAL', 'ACTIVITY')])


def repeat_choice(check, plan):
    """After validation: was the chosen action a repeat, which visit number, and what the model's own text cites."""
    if not check:
        return None
    sel = (plan or {}).get('action_id')
    hit = next((c for c in check.get('candidates') or [] if c['action_id'] == sel), None)
    if not hit:
        return dict(repeat=False, chosen=sel)
    text = ' '.join(str((plan or {}).get(k) or '') for k in ('decision_summary', 'why_not_other_plans', 'tradeoff_note'))
    cited = sorted(set((plan or {}).get('supporting_fact_ids') or []) | set((plan or {}).get('counterevidence_fact_ids') or []))
    personal = sorted(set(cited) & set(hit.get('personal_evidence_fact_ids') or []))
    general = sorted(set(cited) & set(hit.get('general_trait_fact_ids') or []))
    return dict(repeat=True, chosen=sel, visit_number=(hit.get('times_before') or 0) + 1,
                personal_evidence_shown=hit.get('personal_evidence_fact_ids'), personal_evidence_cited=personal,
                general_trait_evidence_shown=hit.get('general_trait_fact_ids'), general_trait_evidence_cited=general,
                same_place_other_option=hit.get('same_place_other_option'),
                reason_mentions_earlier=any(w in text for w in EARLIER_WORDS),
                basis=('PERSONAL_EVIDENCE_CITED' if personal else 'REASON_CITES_EARLIER_VISIT_OR_SITUATION' if any(w in text for w in EARLIER_WORDS)
                       else 'NO_STATED_BASIS_CHECK_STRUCTURE'),
                alternatives_not_used_before=check.get('not_used_before'),
                note='basis is read from what the model wrote before execution (reason, compared alternative, cited Fact ids)')


def has_earlier_days(a):
    """True when this visit has executed records on a date before today (memory carried across days)."""
    today = a.sc.get('date')
    memory = getattr(a, '_autonomous_memory', {}) or {}
    return any(x.get('date') and x['date'] < today for k in (LOG_KEY, 'meal_experiences', 'activity_experiences') for x in memory.get(k) or [])


# ---------------------------------------------------------------- research: selective memory (MEM1S, not wired by default)
SELECTIVE_NOTE = ('판단 유형에 맞춰 줄인 기억입니다. 식사·이용 시설·하루 종료 기록은 모두 남기고, 지금 후보와 관련 없는 결정은 '
                  '이유 문장을 생략했습니다(시각·선택·필요·인용 Fact는 유지). 생략은 그 결정이 없었다는 뜻이 아닙니다.')


def selective_earlier_days(block, candidates, purpose=None):
    """The MEM1 block reduced by decision type without dropping facts: every executed meal (place, order, totals,
    times, benefit), every visited facility, the day end and the no-dinner record stay; decision reasons stay for
    decisions about a shown candidate (same action, same label, or same venue) and the last decision of each day;
    for breakfast, meal decisions keep their reasons. Other decisions keep time, action, need and cited Fact ids.
    Same place / different product, executed / planned and observed / simulated stay as in the full block."""
    if not block or not block.get('days'):
        return block
    ids = {c.get('action_id') for c in candidates or []}
    labels = {c.get('label') for c in candidates or [] if c.get('label')}
    venues = {c.get('location') for c in candidates or [] if c.get('type') == 'MEAL'}
    meal_purpose = str(purpose or '').startswith('BREAKFAST')
    out = copy.deepcopy(block); dropped = 0
    for day in out['days']:
        decs = day.get('decisions') or []
        for i, d in enumerate(decs):
            aid = str(d.get('action_id') or '')
            related = (aid in ids or (d.get('label') and d['label'] in labels) or (aid.startswith('meal:') and aid[5:] in venues)
                       or i == len(decs) - 1 or (meal_purpose and aid.startswith(('meal:', 'BREAKFAST', 'SKIP_BREAKFAST'))))
            if related:
                continue
            for k in ('reason', 'compared_not_chosen', 'next_intent'):
                if d.pop(k, None) is not None and k == 'reason':
                    dropped += 1
    out['selection'] = dict(mode='SELECTIVE_BY_SHOWN_CANDIDATES_AND_PURPOSE', reasons_omitted=dropped, note=SELECTIVE_NOTE)
    return out
