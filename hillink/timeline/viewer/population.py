"""Population layer: composition weights for a group of simulated customer teams (research, no agent changes).

The run's customers are not a probability sample of a hotel's guests. When the hotel (or a test file) states its
guest composition (composition.* metrics, e.g. party size shares), each team gets a weight so the weighted group
matches that composition. Behaviour is never reweighted toward a behaviour target: delivery or F&B shares are
outcomes compared after weighting, never inputs to the weights.

Records: normalized weights (mean 1), effective sample size (Kish), the largest weight, weight capping, target
segments missing from the sample (calibration impossible -> reported, their share is not represented), teams whose
segment is unknown (excluded from the weighted estimate) and the share of the target the sample covers.
Weighted results are estimates for the stated composition; the run's ledger totals stay the actual simulated sums.
"""
import operating_reference as OR

CAP = 4.0            # largest weight allowed relative to the mean (trimmed and re-normalized); a stated setting
MIN_ESS = 10         # below this effective sample size the weighted estimate is shown with a warning
COMPANION = {'family_kids': 'family', 'family_parents': 'family', 'family': 'family', 'couple': 'couple',
             'friends': 'friends', 'friend': 'friends', 'solo': 'solo'}


def segments(result):
    """Segment values per staying team (party size bucket; companion type when the visit profile states it)."""
    out = {}
    for pid, v in (result.get('visits') or {}).items():
        if not v.get('stay'): continue
        n = int(v.get('party_size') or 0)
        out[pid] = {'party_size': None if n <= 0 else 'party_size:1' if n == 1 else 'party_size:2' if n == 2 else 'party_size:3+',
                    'companion': ('companion:' + COMPANION[v['rel']]) if v.get('rel') in COMPANION else None}
    return out


def weights(result, entries, dimension='party_size', cap=CAP):
    defs = OR.metrics(); mid = next((k for k, d in defs.items() if d.get('composition_dimension') == dimension), None)
    if mid is None: return dict(status='REFUSED', reason='UNSUPPORTED_DIMENSION:%s' % dimension)
    targets = {}
    for seg in defs[mid]['segments']:
        e = OR.resolve(mid, seg, entries)
        if e is not None and e.get('segment') == seg and e.get('value') is not None: targets[seg] = e
    if not targets: return dict(status='REFUSED', reason='NO_COMPOSITION_REFERENCE', dimension=dimension)
    classes = {e['source_class'] for e in targets.values()}; sets = {e.get('source_set') for e in targets.values()}
    if len(sets) > 1: return dict(status='REFUSED', reason='MIXED_SOURCE_SETS_FOR_ONE_COMPOSITION', sets=sorted(map(str, sets)))
    periods = {e.get('period') for e in targets.values()}
    if len(periods) > 1: return dict(status='REFUSED', reason='MIXED_PERIODS_FOR_ONE_COMPOSITION', periods=sorted(map(str, periods)))
    total = sum(e['value'] for e in targets.values())
    if abs(total - 1) > 0.02: return dict(status='REFUSED', reason='TARGET_SHARES_DO_NOT_SUM_TO_ONE', total=round(total, 4))
    seg = segments(result)
    if not seg: return dict(status='REFUSED', reason='NO_STAY_TEAMS')
    known = {pid: s[dimension] for pid, s in seg.items() if s[dimension]}
    unknown = sorted(pid for pid, s in seg.items() if not s[dimension])
    counts = {}
    for s in known.values(): counts[s] = counts.get(s, 0) + 1
    unsupported = sorted(s for s in targets if s not in counts)
    outside = sorted(s for s in counts if s not in targets)
    covered = sum(targets[s]['value'] for s in targets if s in counts)
    if not counts or covered <= 0: return dict(status='REFUSED', reason='NO_SAMPLE_IN_TARGET_SEGMENTS')
    n = sum(counts[s] for s in counts if s in targets)
    w = {pid: (targets[s]['value'] / covered) / (counts[s] / n) for pid, s in known.items() if s in targets}
    capped = False
    for _ in range(20):
        mean = sum(w.values()) / len(w); w = {k: x / mean for k, x in w.items()}
        over = {k for k, x in w.items() if x > cap}
        if not over: break
        capped = True; w = {k: (cap if k in over else x) for k, x in w.items()}
    ess = sum(w.values()) ** 2 / sum(x * x for x in w.values())
    return dict(status='OK' if ess >= MIN_ESS else 'OK_LOW_EFFECTIVE_SAMPLE', dimension=dimension, metric_id=mid,
                source_class=sorted(classes), source_ko=[OR.CLASS_KO[c] for c in sorted(classes)], source_set=next(iter(sets)),
                targets={s: e['value'] for s, e in targets.items()}, sample_counts=counts,
                weights={k: round(x, 4) for k, x in sorted(w.items())}, effective_sample_size=round(ess, 2), teams_weighted=len(w),
                max_weight=round(max(w.values()), 4), capped=capped, cap=cap,
                unsupported_segments=unsupported, target_share_not_represented=round(1 - covered, 4),
                sample_segments_outside_target=outside, excluded_unknown_segment=unknown,
                basis='COMPOSITION_ONLY; BEHAVIOUR_SHARES_ARE_OUTCOMES_NOT_WEIGHT_TARGETS')


def estimates(result, w=None):
    """Per-team behaviour and spend, raw (each team counts 1) and weighted (composition weights). The weighted
    values are estimates for the stated composition, not ledger totals."""
    rows = OR.dinner_rows(result); teams = sorted({r['customer_id'] for r in rows})
    ww = (w or {}).get('weights') or {}

    def mean(fn, weighted):
        ids = [t for t in teams if (t in ww or not weighted)]
        if not ids: return None
        num = sum((ww[t] if weighted else 1) * fn(t) for t in ids); den = sum((ww[t] if weighted else 1) for t in ids)
        return round(num / den, 4)
    per = {t: [r for r in rows if r['customer_id'] == t] for t in teams}
    share = lambda kind: (lambda t: sum(r['kind'] == kind for r in per[t]) / max(1, len(per[t])))
    metrics = {'delivery.evening_share': share('EXTERNAL_DELIVERY'), 'dinner.restaurant_share': share('HOTEL_RESTAURANT'),
               'dinner.room_service_share': share('ROOM_SERVICE'),
               'delivery.team_share': lambda t: float(any(r['kind'] == 'EXTERNAL_DELIVERY' for r in per[t])),
               'fnb.dinner_revenue_per_stay_team': lambda t: sum(r['paid_krw'] for r in per[t])}
    out = {k: dict(raw=mean(f, False), weighted=mean(f, True) if ww else None) for k, f in metrics.items()}
    return dict(teams=len(teams), evenings=len(rows), metrics=out,
                note='raw = 실행한 팀을 같은 비중으로 · weighted = 기준 고객 구성 가중 추정(원장 합계 아님)')
