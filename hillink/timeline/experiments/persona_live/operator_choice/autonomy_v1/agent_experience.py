"""Decision context and executed visit memory, never persona facts or utility scores.

Orders are executed simulation records. Diners, intake and satiety below remain
explicit planning assumptions; neither receipts nor serving estimates prove eating.
"""
import copy
import hashlib
import re
from datetime import date
from . import profile_context as PC, hotel_catalog as H, breakfast_policy as BP

POLICY = 'AGENT_EXPERIENCE_CONTEXT_V10'
MEMORY_POLICY = 'LLM_VISIT_MEMORY_V3'


def opaque(pid, value):
    return hashlib.sha256((pid + '|' + str(value)).encode()).hexdigest()[:24]


def clock(minute):
    """Model-facing clock, never reinterpret minute counts as HHMM digits."""
    if type(minute) is int and 0 <= minute <= 1440:
        return f'{minute//60:02d}:{minute%60:02d}'
    return minute


def meal_history_context(rows):
    """Presentation-only copy; executor minute arithmetic remains unchanged."""
    result = copy.deepcopy(rows)
    for row in result:
        legacy={k:row.pop(k) for k in ('size','meal_fraction') if k in row}
        if legacy:
            row['legacy_portion_estimate']=dict(legacy,
                basis='LEGACY_EQUAL_PARTY_SHARE_NOT_LLM_MEAL_INTENT_OR_OBSERVED_INTAKE')
            if legacy.get('size')=='skip':row['meal_execution']='SKIPPED_NOT_INTAKE'
        for source, target in (('t', 'start_time'), ('start', 'start_time'), ('end', 'end_time')):
            if source in row:
                row[target] = clock(row.pop(source))
    return result


def evidence(a, personal):
    """Keep existing grades and all eligible summaries, including negative context.

    Same-summary aliases are one observation. Same-post facts share a conservative
    provenance group; a post group is not asserted to be a distinct visit.
    """
    raw = ((a.lib or {}).get('engine') or {}).get('facts') or {}
    idx = a.traits.get('evidence_index') or {}
    hidden = set(a.P.get('hidden') or [])
    grades = {}
    for facet, item in (a.traits.get('facets') or {}).items():
        for e in item.get('evidence', []):
            grades.setdefault(e['fact_id'], []).append(dict(facet=facet, grade=e.get('grade')))
    grouped = {}
    for fid, f in idx.items():
        g = raw.get(fid) or {}
        if fid in hidden or g.get('hidden'): continue
        if grades.get(fid) and not any(x['grade'] == 'rep' for x in grades[fid]): continue
        summary = PC._clean(f.get('gist'), n=1200, staff=PC.staff_re(a))
        if not summary: continue
        posts = f.get('posts') or ([g.get('post') or g.get('post_id')] if g.get('post') or g.get('post_id') else [])
        groups = sorted(opaque(a.pid, p) for p in posts)
        actor = g.get('actor') or 'UNCONFIRMED'
        stage = g.get('action_stage') or 'UNCONFIRMED'
        time_scope = g.get('time_scope') or 'REVIEW_TIME_UNCONFIRMED_NOT_CURRENT_VISIT'
        key = (re.sub(r'\s+', '', summary), tuple(groups), str(actor), str(stage), str(time_scope))
        row = grouped.setdefault(key, dict(fact_ids=[], summary=summary,
            provenance_groups=groups, provenance_basis='SOURCE_POST_GROUP_NOT_CONFIRMED_INDEPENDENT_VISIT' if groups else 'UNRESOLVED',
            source_scope=PC.fact_context(a, fid) or 'UNRESOLVED',
            actor=actor, action_stage=stage, time_scope=time_scope,
            polarity=g.get('polarity') or 'UNANNOTATED_READ_SUMMARY',
            grade_by_fact={}, human_review='PENDING_NOT_APPROVED_BY_AGENT'))
        row['fact_ids'].append(fid); row['grade_by_fact'][fid] = grades.get(fid, [])
    rows = list(grouped.values())
    for row in rows:
        row['fact_ids'].sort()
        row['observation_key'] = opaque(a.pid, (row['summary'], row['provenance_groups'], row['actor'], row['action_stage'], row['time_scope']))
        row['independent_observation_count'] = None  # no manufactured recurrence
    personal.update(evidence_records=rows,
        citable_fact_ids=sorted({f for x in rows for f in x['fact_ids']}),
        evidence_policy=POLICY,
        evidence_boundary='SUMMARY_ALIASES_ARE_ONE_OBSERVATION; SAME_POST_NOT_MULTIPLE_VISITS; SOURCE_MEANING_REQUIRES_REVIEW')
    return personal


def breakfast_context(a):
    from . import santa_2026 as S26
    snap=a.sc.get('scenario_snapshot') or {};package=S26.package(snap,a.pid)
    if package:
        party=H.PO.party(a) or {};day=S26.breakfast_day(snap)
        matches=party.get('adult_count')==package['base_adults'] and len(party.get('children',[]))==package['base_children']
        venue=package['breakfast_venue']
        if venue=='CLUB_WEEKDAY_BUFFET':venue='GRAND_CLUB_LOUNGE' if date.fromisoformat(day).weekday()>=5 else 'THE_BUFFET'
        return dict(policy='SANTA_2026_BREAKFAST_ENTITLEMENT_CONTEXT',plan=package['package_id'],
            covered_adults=package['base_adults'],covered_children=package['base_children'],
            benefit_date=day,applicable_today=a.sc['date']==day,venue=venue,
            whole_party_covered=matches,coverage_subject_to_actual_offer_validation=True,
            source='EXISTING_SANTA_2026_PACKAGE_CONTRACT_NOT_GENERIC_ROOM_RIGHT',source_sha256=S26.SHA,
            entitlement_usage=copy.deepcopy(a.visit_history.get('hotel_entitlement_usage',{})),
            consumption='NOT_OBSERVED; OFFER_AND_EXECUTION_RECORD_DETERMINE_VIRTUAL_USE')
    return dict(policy=BP.policy(a.sc),plan=BP.plan(a.vs,a.sc),
        covered_adults=BP.covered_adults(a),whole_party_covered=BP.whole_party_covered(a),
        event_override=a.sc.get('breakfast_entitlement_override'),
        source='CURRENT_SIMULATED_ROOM_PACKAGE_CONTRACT_NOT_HISTORICAL_ENTITLEMENT')


def visit(a):
    explicit = H.PO.party(a)
    modeled = H.modeled_party(a)
    if modeled is None:
        modeled=dict(adult_count=a.N,children=[],source='LEGACY_ALL_ADULT_PRICE_REFERENCE',
            operational_eligibility='REVIEW_REQUIRED_COMPOSITION_AND_AGES_UNCONFIRMED')
    return dict(date=a.sc['date'], party_size=a.N, party=copy.deepcopy(explicit),
        party_status='OPERATOR_SCENARIO_NOT_REVIEW_FACT' if explicit else 'COMPOSITION_AND_AGES_UNCONFIRMED',
        contract_party_assumption=copy.deepcopy(modeled),
        purpose=(dict(status='OPERATOR_SCENARIO_NOT_REVIEW_FACT', value=a.vs['visit_purpose']) if a.vs.get('visit_purpose') else dict(status='UNCONFIRMED', basis='HISTORICAL_VISIT_PURPOSE_IS_NOT_CURRENT_PURPOSE')),
        relationship=a.vs.get('rel'), relationship_status='RUNTIME_ASSUMPTION_NOT_CONFIRMED_RELATIONSHIP',
        building=a.B, nights=a.vs.get('nights'), checked_in=a.checked_in, checked_out=a.checked_out,
        scenario=copy.deepcopy(a.sc.get('scenario_snapshot')), environment=copy.deepcopy(a.sc.get('operational_environment')),
        pre_arrival_intake='UNKNOWN_NOT_ZERO_MEALS', intake_boundary='ORDERED_FOOD_NOT_OBSERVED_INTAKE',
        budget='UNKNOWN',breakfast=breakfast_context(a))


def history(a, minute):
    rows = copy.deepcopy(getattr(a, '_autonomous_memory', {}).get('meal_experiences', []))
    for row in rows:
        try:
            days = (date.fromisoformat(a.sc['date']) - date.fromisoformat(row['date'])).days
            row['minutes_since_end'] = days * 1440 + minute - row['end']
        except (ValueError, TypeError):
            row['minutes_since_end'] = None
    return meal_history_context(rows)


def remember_activities(a, minute):
    """Carry completed executor records across days, independently of LLM intent.

    Read the actual timeline, including obligations/booking hooks and movement.
    A validated proposal alone is not an experience. Rebuild today's portion so
    a merged rest segment is updated rather than counted as a second activity.
    No historical review, inferred satisfaction or recovery claim enters memory.
    """
    memory = a.__dict__.setdefault('_autonomous_memory', copy.deepcopy(
        a.visit_history.get('autonomous_memory') or {}))
    if memory.get('customer_id', a.pid) != a.pid:
        raise ValueError('VISIT_MEMORY_CUSTOMER_MISMATCH')
    memory.update(policy=MEMORY_POLICY, customer_id=a.pid)
    memory.setdefault('pending_intentions', [])
    today = a.sc['date']
    rows = [copy.deepcopy(x) for x in memory.get('activity_experiences', []) if x['date'] < today]
    for rec in a.log:
        start, end = rec.get('t'), rec.get('e')
        if not isinstance(start, str) or not isinstance(end, str): continue
        try:
            start_min = int(start[:2]) * 60 + int(start[3:])
            end_min = int(end[:2]) * 60 + int(end[3:])
        except ValueError:
            continue
        if start_min < 0 or end_min < start_min or end_min > minute: continue
        decision = (rec.get('internal') or {}).get('autonomous_decision') or {}
        if decision and decision.get('execution_state') != 'EXECUTED':
            # Scene internals can contain a deep-copied VALIDATED snapshot.
            # Join the authoritative completion, not a different or merely
            # proposed action. This mirrors the behavior-evidence run join.
            keys=('input_sha256','customer_id','date','minute','policy','contract_sha256')
            matches=[d for d in getattr(a,'_autonomous_decisions',[])
                     if decision.get('input_sha256') and
                     all(d.get(k)==decision.get(k) for k in keys) and
                     d.get('selected_plan')==decision.get('selected_plan')]
            if len(matches)!=1 or matches[0].get('execution_state')!='EXECUTED': continue
            decision=matches[0]
        row = dict(date=today, start=start_min, end=end_min, action=rec.get('act'),
            start_time=start, end_time=end, time_unit='START_END_NUMBERS_ARE_MINUTES_SINCE_MIDNIGHT',
            label=rec.get('label'), location=rec.get('loc'), domain=rec.get('domain'),
            execution_source=rec.get('source'),
            status='EXECUTED_SIMULATED_ACTIVITY_NOT_REVIEW_FACT',
            satisfaction='NOT_OBSERVED', recovery='MODEL_STATE_CHANGE_NOT_MEASURED_EFFECT')
        if decision:
            row['selected_action_id'] = decision.get('selected_plan', {}).get('action_id')
        rows.append(row)
    memory['activity_experiences'] = rows
    return memory


def activity_history(a, minute):
    rows = copy.deepcopy(remember_activities(a, minute)['activity_experiences'])
    for row in rows:
        row['minutes_since_end'] = (date.fromisoformat(a.sc['date']) - date.fromisoformat(row['date'])).days * 1440 + minute - row['end']
        # Human/model-facing times are clock strings, avoiding 1288 -> 12:48.
        for key in ('start','end'):
            value=row[key]
            row[key+'_time']=f'{value//60:02d}:{value%60:02d}'
            row.pop(key)
        row.pop('time_unit',None)
    return rows


def intention_context(memory):
    # Experiences are supplied once in the dated top-level history fields.
    return {k:copy.deepcopy(v) for k,v in memory.items()
            if k not in ('activity_experiences', 'meal_experiences', 'mem1_log')}   # mem1_log: MEM1 research only, sent as earlier_days


def reassessment_context(a, minute):
    """Expose what actually changed; time passing creates no customer report."""
    prior = [d for d in getattr(a, '_autonomous_decisions', [])
             if d.get('date') == a.sc['date'] and d.get('minute', minute) < minute
             and d.get('execution_state') == 'EXECUTED']
    recent = []
    for d in prior[-3:]:
        plan = d.get('selected_plan') or {}
        recent.append(dict(time=clock(d['minute']), action_id=plan.get('action_id'),
                           need_assessment=copy.deepcopy(plan.get('current_need_assessment')),
                           reason=plan.get('decision_summary'),
                           status='PRIOR_MODEL_JUDGMENT_NOT_CUSTOMER_REPORT'))
    return dict(recent_decisions=recent,
                minutes_since_previous_decision=minute-prior[-1]['minute'] if prior else None,
                customer_report_channel='NOT_PRESENT_IN_THIS_SIMULATION',
                newly_observed_intake_hunger_or_child_condition=False,
                available_changes='EXECUTED_SIMULATION_ACTIONS_ORDERS_ELAPSED_TIME_AND_CONTRACT_WINDOWS',
                portion_reference='LEGACY_EQUAL_PARTY_SHARE_IS_NOT_MEASURED_INTAKE_OR_ADULT_INFANT_REQUIREMENT',
                choice_owner='LLM; uncertainty is not a requirement to keep waiting')


def remember_meal(a, rec, plan, period):
    charge = rec.get('charge') or {}; contract = charge.get('sku_contract') or {}
    parts = contract.get('components') or []
    assessment = copy.deepcopy(plan.get('meal_assessment'))
    row = dict(date=a.sc['date'], start=rec['t'], end=int(rec['e'][:2])*60+int(rec['e'][3:]),
        venue=rec.get('loc'), period=period, session_id=rec.get('meal_session_id'),
        period_basis='CLOCK_SERVICE_CLASSIFICATION_NOT_CUSTOMER_MEAL_INTENT',
        order=[dict(sku_id=p['sku_id'], label=p['label'], quantity=p['billing_quantity'],
                    role=p.get('role'), unit=p.get('billing_unit'), included_components=p.get('included_components'),
                    tags=p.get('tags', [])) for p in parts],
        order_total_krw=charge.get('krw'), party_size=a.N,
        sharing_assumption=plan.get('sharing_plan'), assessment=assessment,
        portion_model=copy.deepcopy(contract.get('meal_basket')),
        actual_intake='NOT_OBSERVED', actual_diners='NOT_OBSERVED', leftovers='NOT_OBSERVED',
        status='EXECUTED_SIMULATED_ORDER_WITH_LLM_INTAKE_ASSUMPTION_NOT_CUSTOMER_FACT')
    # Do not recursively embed all previous meals in each memory entry.
    if row['portion_model']: row['portion_model'].pop('prior_meals', None)
    memory=a.__dict__.setdefault('_autonomous_memory', {})
    memory.setdefault('meal_experiences', []).append(row)
    return row


def validate_assessment(plan, party_size, is_food):
    assessment=plan.get('meal_assessment')
    if not is_food:
        if assessment is not None: raise ValueError('NON_MEAL_CANNOT_CLAIM_INTAKE')
        return
    if not assessment: raise ValueError('MEAL_INTAKE_AND_SHARING_ASSUMPTION_REQUIRED')
    n=assessment['modeled_diners']
    if type(n) is not int or not 1 <= n <= party_size:
        raise ValueError('MODELED_DINERS_EXCEED_CURRENT_PARTY')
    if not assessment['quantity_reason'].strip() or not plan.get('sharing_plan','').strip():
        raise ValueError('PORTION_AND_SHARING_REVIEW_REQUIRED')


def breakfast_outcome(selected, edible_count, excluded):
    if selected != 'SKIP_BREAKFAST': return 'SIMULATED_BREAKFAST_SELECTED'
    if edible_count == 0:
        return 'CONTRACT_UNAVAILABLE_DEFERRED_NOT_CUSTOMER_PREFERENCE'
    return 'VOLUNTARY_NONUSE_AMONG_VALID_OPTIONS_NOT_STABLE_PREFERENCE'


def decision_context(context, plans):
    """Immutable allowlist of what the model received, not reconstructed reasons.

    Only already deidentified, actually cited Fact summaries enter the run.
    Raw review text, URLs, authors, API credentials and uncited profile are absent.
    """
    cited={f for p in plans for k in ('supporting_fact_ids','counterevidence_fact_ids') for f in p.get(k,[])}
    fields=('fact_ids','summary','provenance_groups','observation_key','source_scope',
            'actor','action_stage','time_scope','grade_by_fact','human_review','independent_observation_count')
    facts=[{k:copy.deepcopy(row[k]) for k in fields if k in row}
           for row in context['personal'].get('evidence_records',[]) if cited.intersection(row['fact_ids'])]
    wanted={i['sku_id'] for p in plans for i in p.get('items',[])}
    products=[{k:copy.deepcopy(p.get(k)) for k in ('sku_id','label','unit_price_krw','billing_unit','role','included_components','price_status')}
              for rows in context.get('menus',{}).values() for p in rows if p['sku_id'] in wanted]
    return dict(policy='RECORDED_DECISION_CONTEXT_V6', facts=facts, products=products,
        visit=copy.deepcopy(context.get('visit')),state=copy.deepcopy(context.get('state')),
        pending_schedule=copy.deepcopy(context.get('pending_schedule')),
        reassessment=copy.deepcopy(context.get('reassessment')),
        meal_experiences=copy.deepcopy(context.get('meal_experiences',[])),
        activity_experiences=copy.deepcopy(context.get('activity_experiences',[])),
        pending_intentions=copy.deepcopy(context.get('memory',{}).get('pending_intentions',[])),
        actions=[{k:copy.deepcopy(x.get(k)) for k in ('action_id','label','kind','location','start','duration','window','included','schedule','wait','items','item_contracts','order_total_krw','consequences')}
                 for x in context.get('actions',[])],
        status='ACTUAL_MODEL_INPUT_PROJECTION_NOT_NEW_FACT_APPROVAL')
