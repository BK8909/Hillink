"""Operating reference values and the operator's aggregate of one simulation run.

Reference values are kept apart from behaviour. They are used (1) to show the operator how a run's group aggregate
compares with what is known, (2) by population.py for composition weights (composition_* metrics only) and (3) by the
research behaviour prior (metrics marked behaviour_prior_usable only). They never set an individual agent's choice.

Source classes, in order of precedence for the same metric and segment:
  HOTEL_MEASURED        the hotel's own counts (e.g. Walkerhill), supplied later via HILLINK_OPERATING_REFERENCE
  EXTERNAL_RESEARCH     published studies / operator interviews from other hotels (temporary proxy, labelled as such)
  SYNTHETIC_TEST        development values for a fictional hotel (never shown as measured or research)
  TEMPORARY_ASSUMPTION  a stated working assumption (none shipped)
  UNKNOWN               definition only, no value
Profiles choose which files are loaded: none | external | synthetic_delivery_high_v1 | synthetic_hotel_format_b_v1 | hotel.
"""
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent / 'operating_reference'
SCHEMA = 'HILLINK_OPERATING_REFERENCE_V1'
CLASSES = ('HOTEL_MEASURED', 'EXTERNAL_RESEARCH', 'SYNTHETIC_TEST', 'TEMPORARY_ASSUMPTION', 'UNKNOWN')
CLASS_KO = {'HOTEL_MEASURED': '호텔 실측', 'EXTERNAL_RESEARCH': '외부 연구(워커힐 실측 아님)', 'SYNTHETIC_TEST': '합성 테스트값(실측·연구 아님)',
            'TEMPORARY_ASSUMPTION': '임시 가정', 'UNKNOWN': '미확인'}
MIN_TEAMS = 20   # below this many teams a run's rate is shown, not judged against a reference
PROFILES = {'none': [], 'external': ['external_research_v1.json'],
            'synthetic_delivery_high_v1': ['external_research_v1.json', 'synthetic_delivery_high_v1.json'],
            'synthetic_hotel_format_b_v1': ['external_research_v1.json', 'synthetic_hotel_format_b_v1.json'],
            'hotel': ['external_research_v1.json']}   # + the file named by HILLINK_OPERATING_REFERENCE


def metrics():
    return json.loads((HERE / 'metrics.json').read_text(encoding='utf-8'))['metrics']


def validate(entry, defs=None):
    """Errors for one reference entry (empty list = valid)."""
    defs = defs or metrics(); err = []
    m = entry.get('metric_id')
    if m not in defs: return ['UNKNOWN_METRIC:%s' % m]
    d = defs[m]; cls = entry.get('source_class')
    if cls not in CLASSES: err.append('SOURCE_CLASS')
    vals = [entry.get(k) for k in ('value', 'low', 'high') if entry.get(k) is not None]
    kind = d.get('value_kind', 'share')
    bad = lambda v: not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 or (kind == 'share' and v > 1) or (kind == 'krw' and not isinstance(v, int))
    if any(bad(v) for v in vals): err.append('VALUE_RANGE')
    if entry.get('low') is not None and entry.get('high') is not None and entry['low'] > entry['high']: err.append('LOW_ABOVE_HIGH')
    if cls != 'UNKNOWN' and not vals: err.append('NO_VALUE')
    if cls == 'UNKNOWN' and vals: err.append('UNKNOWN_WITH_VALUE')
    if d.get('segments') and entry.get('segment') not in d['segments']: err.append('UNSUPPORTED_SEGMENT:%s' % entry.get('segment'))
    if not d.get('segments') and entry.get('segment', 'all') != 'all' and not str(entry.get('segment')).startswith(('party_size:', 'companion:', 'stay:')):
        err.append('UNSUPPORTED_SEGMENT:%s' % entry.get('segment'))
    if entry.get('level') and entry['level'] != d['level']: err.append('DENOMINATOR_LEVEL_MISMATCH:%s!=%s' % (entry['level'], d['level']))
    if cls in ('HOTEL_MEASURED', 'EXTERNAL_RESEARCH', 'SYNTHETIC_TEST'):
        for k in ('period', 'segment'):
            if not entry.get(k): err.append('MISSING_' + k.upper())
        if not (entry.get('source') or {}).get('kind'): err.append('MISSING_SOURCE_KIND')
    if cls == 'HOTEL_MEASURED' and not entry.get('sample_size'): err.append('MISSING_SAMPLE_SIZE')
    if cls == 'SYNTHETIC_TEST' and not entry.get('synthetic_label'): err.append('SYNTHETIC_LABEL_REQUIRED')
    if cls == 'HOTEL_MEASURED' and entry.get('synthetic_label'): err.append('SYNTHETIC_VALUE_CANNOT_BE_HOTEL_MEASURED')
    return err


def _files(profile, extra):
    if profile not in PROFILES: raise ValueError('UNKNOWN_REFERENCE_PROFILE:%s' % profile)
    paths = [HERE / f for f in PROFILES[profile]]
    hotel = extra or (os.environ.get('HILLINK_OPERATING_REFERENCE') if profile in ('hotel', 'external') else None)
    if profile == 'hotel' and not hotel: raise ValueError('HOTEL_REFERENCE_FILE_REQUIRED')
    if hotel: paths.append(Path(hotel))
    return paths


def load(extra=None, profile='external'):
    """Valid entries of the chosen profile (external file, a synthetic test file, or the hotel file named by
    HILLINK_OPERATING_REFERENCE). Invalid or empty entries (e.g. an unfilled template) are reported, never used."""
    defs = metrics(); used, rejected = [], []
    for p in _files(profile, extra):
        doc = json.loads(Path(p).read_text(encoding='utf-8'))
        if doc.get('schema') != SCHEMA: rejected.append(dict(file=Path(p).name, errors=['SCHEMA'])); continue
        for e in doc.get('entries') or []:
            errs = validate(e, defs)
            (rejected if errs else used).append(dict(e, file=Path(p).name, source_set=doc.get('source_set'), **({'errors': errs} if errs else {})))
    return used, rejected


def provenance(profile='external', extra=None):
    """Which files (and their SHA-256) a run used: the reference version recorded with every result."""
    return dict(profile=profile, files=[dict(name=Path(p).name, sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest(),
                                             source_set=json.loads(Path(p).read_text(encoding='utf-8')).get('source_set')) for p in _files(profile, extra)])


def resolve(metric_id, segment='all', entries=None):
    entries = load()[0] if entries is None else entries
    same = [e for e in entries if e['metric_id'] == metric_id and e.get('segment', 'all') in (segment, 'all') and e['source_class'] != 'UNKNOWN']
    same.sort(key=lambda e: (CLASSES.index(e['source_class']), e.get('segment') != segment))
    if same: return same[0]
    unknown = [e for e in entries if e['metric_id'] == metric_id and e['source_class'] == 'UNKNOWN']
    return unknown[0] if unknown else None


def compare(simulated, entries=None, teams=0):
    """One row per metric: the run's value next to the best available reference, with a review status that
    does not change any agent."""
    entries = load()[0] if entries is None else entries
    rows = []
    for mid, d in metrics().items():
        if d.get('composition_dimension'): continue   # composition is used by population.py, not compared here
        key = d.get('simulated')
        ref = resolve(mid, entries=entries)
        if ref is None and d.get('segments') and not d.get('composition_dimension'):   # context-only segmented sources (e.g. sales mode)
            ref = next((e for e in entries if e['metric_id'] == mid), None)
        sim = simulated.get(key) if key else None
        if not key:
            status = 'CONTEXT_ONLY'
        elif ref is None or ref['source_class'] == 'UNKNOWN':
            status = 'NO_REFERENCE'
        elif ref.get('comparability', '').startswith(('DIFFERENT_LEVEL', 'DENOMINATOR_UNCONFIRMED')):
            status = 'NOT_COMPARABLE'
        elif sim is None:
            status = 'NOT_IN_RUN'
        elif teams < MIN_TEAMS:
            status = 'SAMPLE_TOO_SMALL'
        else:
            lo = ref['low'] if ref.get('low') is not None else ref['value']
            hi = ref['high'] if ref.get('high') is not None else ref['value']
            tol = 0.05 if d.get('value_kind', 'share') == 'share' else 0.1 * max(abs(lo), 1)
            status = 'WITHIN_REFERENCE' if lo - tol <= sim <= hi + tol else 'BELOW_REFERENCE' if sim < lo else 'ABOVE_REFERENCE'
        rows.append(dict(metric_id=mid, name_ko=d['name_ko'], level=d['level'], value_kind=d.get('value_kind', 'share'), simulated=sim, status=status,
                         reference=None if ref is None else {k: ref.get(k) for k in ('value', 'low', 'high', 'source_class', 'period', 'geography', 'sample_size', 'comparability', 'note', 'synthetic_label', 'source_set')}
                         | dict(source_ko=CLASS_KO[ref['source_class']], title=(ref.get('source') or {}).get('title'), url=(ref.get('source') or {}).get('url'))))
    return rows


# ------------------------------------------------------------------ run aggregate (operator view)
def _rate(n, d): return None if not d else round(n / d, 4)


DINNER_KINDS = ('EXTERNAL_DELIVERY', 'ROOM_SERVICE', 'HOTEL_RESTAURANT', 'OUTSIDE_OR_OTHER')


def dinner_kind(scene):
    """Where one dinner scene was eaten: external delivery (outside spend, not hotel revenue), hotel room service,
    a hotel restaurant, or something else."""
    b = scene.get('basis') or {}; ch = b.get('charge') or {}; c = ch.get('sku_contract') or {}
    if ch.get('external_spend') or 'DELIVERY' in str(scene.get('act')).upper() or str(scene.get('loc')) == 'EXTERNAL_DELIVERY':
        return 'EXTERNAL_DELIVERY'
    venue = c.get('venue_id') or ''
    if venue in ('IRD', 'ROOM_MEAL') or str(scene.get('loc') or '').endswith('_ROOM'):
        return 'ROOM_SERVICE'
    if 'EXTERNAL' in str(scene.get('act')).upper() or str(scene.get('loc') or '').startswith('OUT'):
        return 'OUTSIDE_OR_OTHER'
    return 'HOTEL_RESTAURANT'


def dinner_rows(result):
    """One row per staying team per stay evening (check-out day excluded): kind, venue, paid KRW (hotel only)."""
    rows = []
    for pid, plan in (result.get('plans') or {}).items():
        v = (result.get('visits') or {}).get(pid) or {}
        if not v.get('stay'): continue
        scenes = plan.get('scenes') or []
        days = sorted({s.get('visit_date') for s in scenes if s.get('visit_date')})
        for day in days[:-1]:
            ds = [s for s in scenes if s.get('visit_date') == day and s.get('meal') == 'dinner']
            if not ds:
                rows.append(dict(customer_id=pid, date=day, kind='NO_DINNER_RECORDED', venue=None, paid_krw=0, label=None)); continue
            s = ds[0]; ch = (s.get('basis') or {}).get('charge') or {}; kind = dinner_kind(s)
            paid = ch.get('krw') if kind in ('ROOM_SERVICE', 'HOTEL_RESTAURANT') and ch.get('status') == '유료' and isinstance(ch.get('krw'), int) else 0
            venue = (ch.get('sku_contract') or {}).get('venue_id') or ('EXTERNAL_DELIVERY' if kind == 'EXTERNAL_DELIVERY' else s.get('loc'))
            rows.append(dict(customer_id=pid, date=day, time=s.get('t0'), kind=kind, venue=venue, paid_krw=paid, label=s.get('label'), event_id=((s.get('basis') or {}).get('m4') or {}).get('event_id')))
    return rows


def aggregate(result, profile='external', extra=None):
    """Operator aggregate of one visit result (any number of customer teams). Breakfast in person-mornings:
    entitlement, diners, included use, paid diners, unused entitlement, reasons for not eating, paid revenue
    (registered extra payment only: included breakfasts add no revenue, so the room package is never counted twice)."""
    teams = persons = mornings = 0
    bf = dict(entitled=0, entitled_known_mornings=0, entitlement_unknown_mornings=0, diners=0, included_used=0, paid_diners=0, paid_diners_known_entitlement=0, diners_split_unknown=0, not_entitled=0,
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
            ate = False; paid_before = bf['paid_diners']
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
            if ent is not None: bf['paid_diners_known_entitlement'] += bf['paid_diners'] - paid_before
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
        other['event_teams'] += bool(stay and event_on and any('event' in str(s.get('act')).lower() or 'WINE' in str(s.get('act')) for s in scenes))
    dn = dinner_rows(result)
    fnb = dict(evenings=len(dn), by_kind={k: sum(r['kind'] == k for r in dn) for k in DINNER_KINDS + ('NO_DINNER_RECORDED',)},
               delivery_teams=len({r['customer_id'] for r in dn if r['kind'] == 'EXTERNAL_DELIVERY'}),
               in_hotel_dinner_revenue_krw=sum(r['paid_krw'] for r in dn), by_venue={},
               external_delivery_spend_krw=None, external_spend_note='외부 배달 금액은 미상이며 호텔 매출에 넣지 않음')
    for r in dn:
        if r['kind'] in ('ROOM_SERVICE', 'HOTEL_RESTAURANT'):
            x = fnb['by_venue'].setdefault(r['venue'], dict(evenings=0, paid_krw=0)); x['evenings'] += 1; x['paid_krw'] += r['paid_krw']
    other['in_hotel_dinners'] = fnb['by_kind']['ROOM_SERVICE'] + fnb['by_kind']['HOTEL_RESTAURANT']
    simulated = {'delivery.team_share': _rate(fnb['delivery_teams'], other['stay_teams']),
                 'delivery.evening_share': _rate(fnb['by_kind']['EXTERNAL_DELIVERY'], len(dn)),
                 'delivery.orders_per_room_night': _rate(fnb['by_kind']['EXTERNAL_DELIVERY'], other['room_nights']),
                 'dinner.restaurant_share': _rate(fnb['by_kind']['HOTEL_RESTAURANT'], len(dn)),
                 'dinner.room_service_share': _rate(fnb['by_kind']['ROOM_SERVICE'], len(dn)),
                 'fnb.dinner_revenue_per_stay_team': round(fnb['in_hotel_dinner_revenue_krw'] / other['stay_teams']) if other['stay_teams'] else None,
                 'breakfast.included_use_rate': _rate(bf['included_used'], bf['entitled']),
                 'breakfast.paid_uptake_rate': _rate(bf['paid_diners_known_entitlement'], bf['not_entitled']),
                 'pool.team_use_rate': _rate(other['pool_teams'], other['stay_teams']), 'sauna.team_use_rate': _rate(other['sauna_teams'], other['stay_teams']),
                 'room_service.orders_per_room_night': _rate(other['room_service_orders'], other['room_nights']),
                 'dinner.in_hotel_capture_rate': _rate(other['in_hotel_dinners'], other['dinner_evenings']),
                 'event.team_participation_rate': _rate(other['event_teams'], other['stay_teams']) if event_on else None}
    entries, rejected = load(extra, profile)
    sample_notes = []
    if teams < MIN_TEAMS: sample_notes.append('TEAMS_BELOW_%d: 비율은 표시하지만 기준값과 판정하지 않음' % MIN_TEAMS)
    if not other['stay_teams']: sample_notes.append('NO_STAY_TEAM: 숙박 팀이 없어 숙박 기준 비율을 계산하지 않음(0%가 아님)')
    if not mornings: sample_notes.append('NO_STAY_MORNING: 숙박 아침이 없어 조식 비율을 계산하지 않음(0명 미이용이 아님)')
    return dict(schema='HILLINK_OPERATING_SUMMARY_V1', teams=teams, persons=persons, team_mornings=mornings,
                breakfast=dict(bf, unused_entitlement=max(0, bf['entitled'] - bf['included_used'])), services=other, dinner=fnb, simulated=simulated,
                comparison=compare(simulated, entries, teams), rejected_reference_entries=len(rejected), sample_notes=sample_notes,
                reference=provenance(profile, extra),
                basis='SIMULATION_AGGREGATE_NOT_OBSERVED; REFERENCES_DO_NOT_SET_AGENT_CHOICES; INCLUDED_BREAKFAST_ADDS_NO_REVENUE')
