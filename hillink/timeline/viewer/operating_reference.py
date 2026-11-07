"""Operating reference values and the operator's aggregate of one simulation run.

Reference values are kept apart from behaviour: they never set an individual agent's choice. They are used to
show the operator how a run's group aggregate compares with what is known, and where calibration should be reviewed.

Source classes, in order of precedence for the same metric and segment:
  HOTEL_MEASURED        the hotel's own counts (e.g. Walkerhill), supplied later via HILLINK_OPERATING_REFERENCE
  EXTERNAL_RESEARCH     published studies / operator interviews from other hotels (temporary proxy, labelled as such)
  TEMPORARY_ASSUMPTION  a stated working assumption (none shipped)
  UNKNOWN               definition only, no value
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent / 'operating_reference'
SCHEMA = 'HILLINK_OPERATING_REFERENCE_V1'
CLASSES = ('HOTEL_MEASURED', 'EXTERNAL_RESEARCH', 'TEMPORARY_ASSUMPTION', 'UNKNOWN')
CLASS_KO = {'HOTEL_MEASURED': '호텔 실측', 'EXTERNAL_RESEARCH': '외부 연구(워커힐 실측 아님)', 'TEMPORARY_ASSUMPTION': '임시 가정', 'UNKNOWN': '미확인'}
MIN_TEAMS = 20   # below this many teams a run's rate is shown, not judged against a reference


def metrics():
    return json.loads((HERE / 'metrics.json').read_text(encoding='utf-8'))['metrics']


def validate(entry, defs=None):
    """Errors for one reference entry (empty list = valid)."""
    defs = defs or metrics(); err = []
    m = entry.get('metric_id')
    if m not in defs: return ['UNKNOWN_METRIC:%s' % m]
    if entry.get('source_class') not in CLASSES: err.append('SOURCE_CLASS')
    vals = [entry.get(k) for k in ('value', 'low', 'high') if entry.get(k) is not None]
    share = not m.endswith('orders_per_room_night')   # shares lie in [0, 1]; counts per room-night are >= 0
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 or (share and v > 1) for v in vals):
        err.append('VALUE_RANGE')
    if entry.get('low') is not None and entry.get('high') is not None and entry['low'] > entry['high']: err.append('LOW_ABOVE_HIGH')
    if entry.get('source_class') != 'UNKNOWN' and not vals: err.append('NO_VALUE')
    if entry.get('source_class') in ('HOTEL_MEASURED', 'EXTERNAL_RESEARCH'):
        for k in ('period', 'segment'):
            if not entry.get(k): err.append('MISSING_' + k.upper())
        if not (entry.get('source') or {}).get('kind'): err.append('MISSING_SOURCE_KIND')
    if entry.get('source_class') == 'HOTEL_MEASURED' and not entry.get('sample_size'): err.append('MISSING_SAMPLE_SIZE')
    return err


def load(extra=None):
    """Valid entries from the shipped external file and an optional hotel file (env HILLINK_OPERATING_REFERENCE).
    Invalid or empty entries (e.g. an unfilled template) are reported, never used."""
    defs = metrics(); paths = [HERE / 'external_research_v1.json']
    hotel = extra or os.environ.get('HILLINK_OPERATING_REFERENCE')
    if hotel: paths.append(Path(hotel))
    used, rejected = [], []
    for p in paths:
        doc = json.loads(Path(p).read_text(encoding='utf-8'))
        if doc.get('schema') != SCHEMA: rejected.append(dict(file=Path(p).name, errors=['SCHEMA'])); continue
        for e in doc.get('entries') or []:
            errs = validate(e, defs)
            (rejected if errs else used).append(dict(e, file=Path(p).name, **({'errors': errs} if errs else {})))
    return used, rejected


def resolve(metric_id, segment='all', entries=None):
    entries = load()[0] if entries is None else entries
    same = [e for e in entries if e['metric_id'] == metric_id and e.get('segment', 'all') in (segment, 'all')]
    same.sort(key=lambda e: (CLASSES.index(e['source_class']), e.get('segment') != segment))
    return same[0] if same else None


def compare(simulated, entries=None, teams=0):
    """One row per metric: the run's value next to the best available reference, with a review status that
    does not change any agent."""
    entries = load()[0] if entries is None else entries
    rows = []
    for mid, d in metrics().items():
        key = d.get('simulated')
        ref = resolve(mid, entries=entries)
        sim = simulated.get(key) if key else None
        if not key:
            status = 'CONTEXT_ONLY'
        elif ref is None:
            status = 'NO_REFERENCE'
        elif ref.get('comparability', '').startswith('DIFFERENT_LEVEL'):
            status = 'NOT_COMPARABLE'
        elif sim is None:
            status = 'NOT_IN_RUN'
        elif teams < MIN_TEAMS:
            status = 'SAMPLE_TOO_SMALL'
        else:
            lo = ref['low'] if ref.get('low') is not None else ref['value']
            hi = ref['high'] if ref.get('high') is not None else ref['value']
            status = 'WITHIN_REFERENCE' if lo - 0.05 <= sim <= hi + 0.05 else 'BELOW_REFERENCE' if sim < lo else 'ABOVE_REFERENCE'
        rows.append(dict(metric_id=mid, name_ko=d['name_ko'], level=d['level'], simulated=sim, status=status,
                         reference=None if ref is None else {k: ref.get(k) for k in ('value', 'low', 'high', 'source_class', 'period', 'geography', 'sample_size', 'comparability', 'note')}
                         | dict(source_ko=CLASS_KO[ref['source_class']], title=(ref.get('source') or {}).get('title'), url=(ref.get('source') or {}).get('url'))))
    return rows


# ------------------------------------------------------------------ run aggregate (operator view)
def _rate(n, d): return None if not d else round(n / d, 4)


def aggregate(result):
    """Operator aggregate of one visit result (any number of customer teams). Breakfast in person-mornings:
    entitlement, diners, included use, paid diners, unused entitlement, reasons for not eating, paid revenue
    (registered extra payment only: included breakfasts add no revenue, so the room package is never counted twice)."""
    teams = persons = mornings = 0
    bf = dict(entitled=0, entitled_known_mornings=0, entitlement_unknown_mornings=0, diners=0, included_used=0, paid_diners=0, diners_split_unknown=0, not_entitled=0,
              paid_revenue_krw=0, skipped_team_mornings=0, skip_reasons={}, decided_by={})
    other = dict(stay_teams=0, pool_teams=0, sauna_teams=0, room_service_orders=0, room_nights=0, dinner_evenings=0, in_hotel_dinners=0, event_teams=0)
    event_on = bool((result.get('visit') or {}).get('event_mode') not in (None, 'none'))
    for pid, plan in (result.get('plans') or {}).items():
        v = (result.get('visits') or {}).get(pid) or {}
        party = int(v.get('party_size') or 1); teams += 1; persons += party
        scenes = plan.get('scenes') or []
        decs = {(d.get('date'), d.get('phase')): d for d in plan.get('autonomous_decisions') or [] if d.get('phase') == 'breakfast'}
        days = sorted({s.get('visit_date') for s in scenes if s.get('visit_date')})
        stay_mornings = days[1:] if v.get('stay') else []
        covered = None
        for s in scenes:
            c = ((s.get('basis') or {}).get('charge') or {}).get('sku_contract') or {}
            if (c.get('room_breakfast_contract') or {}).get('covered_adults') is not None: covered = c['room_breakfast_contract']['covered_adults']
        for day in stay_mornings:
            mornings += 1
            bs = [s for s in scenes if s.get('visit_date') == day and (s.get('meal') == 'breakfast' or 'BREAKFAST' in str(s.get('act')).upper()) and str(s.get('act')) != 'SKIP_BREAKFAST']
            d = decs.get((day, 'breakfast'))
            ent = covered
            if ent is None and d: ent = (((d.get('input_context') or {}).get('visit') or {}).get('breakfast') or {}).get('covered_adults')
            whole = any(((s.get('basis') or {}).get('charge') or {}).get('status') == '포함' for s in bs)
            if ent is None and whole: ent = party
            if ent is None: bf['entitlement_unknown_mornings'] += 1
            else: bf['entitled'] += min(ent, party); bf['entitled_known_mornings'] += 1; bf['not_entitled'] += party - min(ent, party)
            owner = 'LLM' if d and d.get('selection_owner', '').startswith('LLM') else 'RULE' if not d else d.get('selection_owner')
            bf['decided_by'][owner] = bf['decided_by'].get(owner, 0) + 1
            ate = False
            for s in bs:
                ch = (s.get('basis') or {}).get('charge') or {}; c = ch.get('sku_contract') or {}
                parts = c.get('components') or []
                if parts and not any(p.get('included_benefit') for p in parts) and ch.get('status') == '포함':
                    # the whole order is a package benefit (order price 0): component prices are reference rates, not revenue
                    inc = sum(p['billing_quantity'] for p in parts if p.get('role', 'MAIN') == 'MAIN' and p.get('billing_unit', 'person') == 'person') or party
                    bf['included_used'] += inc; bf['diners'] += inc; ate = True
                elif parts:
                    inc = sum(p['billing_quantity'] for p in parts if p.get('included_benefit'))
                    paid = sum(p['billing_quantity'] for p in parts if not p.get('included_benefit') and (p.get('unit_price_krw') or 0) > 0)
                    bf['included_used'] += inc; bf['paid_diners'] += paid; bf['diners'] += inc + paid
                    bf['paid_revenue_krw'] += sum((p.get('unit_price_krw') or 0) * p['billing_quantity'] for p in parts if not p.get('included_benefit'))
                    ate = ate or inc + paid > 0
                elif ch.get('status') == '포함':
                    bf['included_used'] += party; bf['diners'] += party; ate = True
                elif ch.get('status') == '유료' and isinstance(ch.get('krw'), int):
                    # a party-total set price (legacy selector) does not say how many diners were covered by the room:
                    # count the diners and the registered payment, and leave the included/paid split unknown
                    if ch.get('per') == '세트': bf['diners_split_unknown'] += party
                    else: bf['paid_diners'] += party
                    bf['diners'] += party; bf['paid_revenue_krw'] += ch['krw']; ate = True
            if not ate:
                bf['skipped_team_mornings'] += 1
                why = (d or {}).get('breakfast_outcome') or ('RULE_SELECTION' if not d else 'UNRECORDED')
                bf['skip_reasons'][why] = bf['skip_reasons'].get(why, 0) + 1
        # other services (definitions in metrics.json: per staying team / room-night / stay evening; day visits are not counted)
        stay = bool(v.get('stay')); locs = [str(s.get('loc') or '') for s in scenes]
        other['stay_teams'] += stay
        other['pool_teams'] += stay and any('POOL' in l for l in locs)
        other['sauna_teams'] += stay and any('SAUNA' in l for l in locs)
        other['room_service_orders'] += sum(1 for s in scenes if str(s.get('loc') or '').endswith('_ROOM') and s.get('meal') in ('lunch', 'dinner', 'late', 'snack') and ((s.get('basis') or {}).get('charge') or {}).get('status') == '유료')
        nights = len(stay_mornings); other['room_nights'] += nights
        evenings = days[:-1] if stay else []
        other['dinner_evenings'] += len(evenings)
        other['in_hotel_dinners'] += sum(1 for d in evenings if any(s.get('visit_date') == d and s.get('meal') == 'dinner' and 'EXTERNAL' not in str(s.get('act')) for s in scenes))
        other['event_teams'] += bool(stay and event_on and any('event' in str(s.get('act')).lower() or 'WINE' in str(s.get('act')) for s in scenes))
    simulated = {'breakfast.included_use_rate': _rate(bf['included_used'], bf['entitled']),
                 'breakfast.paid_uptake_rate': _rate(bf['paid_diners'], bf['not_entitled']),
                 'pool.team_use_rate': _rate(other['pool_teams'], other['stay_teams']), 'sauna.team_use_rate': _rate(other['sauna_teams'], other['stay_teams']),
                 'room_service.orders_per_room_night': _rate(other['room_service_orders'], other['room_nights']),
                 'dinner.in_hotel_capture_rate': _rate(other['in_hotel_dinners'], other['dinner_evenings']),
                 'event.team_participation_rate': _rate(other['event_teams'], other['stay_teams']) if event_on else None}
    entries, rejected = load()
    return dict(schema='HILLINK_OPERATING_SUMMARY_V1', teams=teams, persons=persons, team_mornings=mornings,
                breakfast=dict(bf, unused_entitlement=max(0, bf['entitled'] - bf['included_used'])), services=other, simulated=simulated,
                comparison=compare(simulated, entries, teams), rejected_reference_entries=len(rejected),
                basis='SIMULATION_AGGREGATE_NOT_OBSERVED; REFERENCES_DO_NOT_SET_AGENT_CHOICES; INCLUDED_BREAKFAST_ADDS_NO_REVENUE')
