"""Rule-engine repeat diagnosis (no model calls): why the same dinner venue is chosen on both evenings of a 2-night stay.

    python repeat_lab.py <out.private.json> [--personas A01,...] [--only C0,D1,...]

Conditions (same customers, dates, seed, engine; one factor changed each):
  C0  baseline
  D1  night-view base off            HILLINK_DIAG_SPACE_BASE=off
  D2  in-visit memory of the venue   HILLINK_DIAG_VISIT_MEMORY=on  (discovery terms not earned twice without personal evidence)
  D3  candidate count                HILLINK_DIAG_SKU_CAP=12      (at most 12 SKUs per restaurant venue)
  D4  opening hours                  catalog_options.dinner_plan_lead_min=120 (venues opening within 2 h can be planned; default 45)
  D5  in-visit memory, base only     HILLINK_DIAG_VISIT_MEMORY=base (only the non-personal discovery parts are not earned twice)
  D6  as D5, liked space kept        HILLINK_DIAG_VISIT_MEMORY=base_unless_personal (a night-view term with personal evidence is kept whole)

Each repeated venue visit (2nd evening at the same venue) of C0 is classified from the decision packet:
  SITUATIONAL   no other hotel restaurant was a feasible candidate at that decision (hours / closures / already eaten)
  STRUCTURAL    removing the unconditional night-view base (0.45 for the chosen venue, minus the runner-up's if it has one)
                flips the choice: the base given to every customer decides
  PERSONAL      otherwise, removing the personal-evidence terms (terms carrying Fact ids, chosen minus runner-up) flips it
  INSUFFICIENT  neither removal flips it: non-personal terms (price, benefit, generic fit, lookahead) decide
Success is not fewer repeats: it is fewer repeats without a basis and the personal-evidence repeats kept.
"""
import copy
import json
import os
import sys
import time

import operating_reference as OR
import population_lab as PL
import visit_run as VR

SPACE_BASE = 0.45
CONDITIONS = dict(C0={}, D1={'HILLINK_DIAG_SPACE_BASE': 'off'}, D2={'HILLINK_DIAG_VISIT_MEMORY': 'on'}, D3={'HILLINK_DIAG_SKU_CAP': '12'},
                  D4={'catalog_options': {'dinner_plan_lead_min': 120}}, D5={'HILLINK_DIAG_VISIT_MEMORY': 'base'},
                  D6={'HILLINK_DIAG_VISIT_MEMORY': 'base_unless_personal'})
HOTEL_RESTAURANT_KINDS = ('HOTEL_RESTAURANT',)


def evenings(flow):
    by = {}
    for r in OR.dinner_rows(flow):
        by.setdefault(r['customer_id'], []).append(r)
    return {k: sorted(v, key=lambda r: r['date']) for k, v in by.items()}


def classify(flow):
    """One row per repeated evening (same venue as an earlier evening of the stay)."""
    rows = []
    for pid, ev in evenings(flow).items():
        plan = flow['plans'][pid]
        seen = {}
        for r in ev:
            v = r.get('venue')
            if not v or r['kind'] == 'NO_DINNER_RECORDED':
                continue
            seen[v] = seen.get(v, 0) + 1
            if seen[v] < 2:
                continue
            x, cands = PL._decision_at(plan, r)
            row = dict(customer_id=pid, date=r['date'], venue=v, visit_number=seen[v], kind=r['kind'])
            if not x:
                rows.append(dict(row, cls='NO_DECISION_PACKET')); continue
            chosen = cands.get(x['selected_action'])
            ok = [c for c in cands.values() if c.get('world_allowed') and PL._score(c) is not None and (c.get('meal_fraction') or 0) >= .8]
            best = {}
            for c in ok:
                vv = PL._venue_of(c)
                if vv not in best or PL._score(c) > PL._score(best[vv]): best[vv] = c
            others = sorted((c for vv, c in best.items() if vv != v), key=PL._score, reverse=True)
            other_rest = [c for c in others if PL._venue_of(c) not in ('EXTERNAL_DELIVERY', 'ROOM_REST') and not str(PL._venue_of(c)).endswith('ROOM')]
            alt = others[0] if others else None
            margin = round(PL._score(chosen) - PL._score(alt), 4) if (chosen and alt) else None
            terms = (chosen or {}).get('terms') or []
            aterms = (alt or {}).get('terms') or []
            pers = lambda ts: sum(t['value'] for t in ts if t.get('fact_ids') and t.get('value'))
            personal = round(pers(terms), 4); personal_adv = round(pers(terms) - pers(aterms), 4)
            space = [t for t in terms if t.get('facet') == 'space' and (t.get('value') or 0) > 0]
            space_personal = any(t.get('fact_ids') for t in space)
            alt_space = any(t.get('facet') == 'space' and (t.get('value') or 0) > 0 for t in aterms)
            base_adv = (SPACE_BASE if space else 0) - (SPACE_BASE if alt_space else 0)
            excluded = sorted({e.get('venue_id') for e in ((x.get('packet') or {}).get('catalog_excluded_candidates') or []) if e.get('venue_id')})
            # counterfactual test on the recorded terms (lookahead total kept as recorded): which removal flips the choice?
            if not other_rest:
                cls = 'SITUATIONAL'
            elif margin is not None and margin - base_adv <= 0:
                cls = 'STRUCTURAL'
            elif margin is not None and margin - personal_adv <= 0:
                cls = 'PERSONAL'
            else:
                cls = 'INSUFFICIENT'
            rows.append(dict(row, cls=cls, margin=margin, runner_up_venue=PL._venue_of(alt) if alt else None,
                             personal_terms=personal, personal_advantage=personal_adv, night_view_base_advantage=base_adv, personal_fact_ids=sorted({f for t in terms for f in (t.get('fact_ids') or [])}),
                             night_view_term=round(sum(t['value'] for t in space), 4), night_view_personal=space_personal, runner_up_night_view=alt_space,
                             other_restaurants_feasible=len(other_rest), excluded_venues=excluded,
                             top_terms=sorted(({'factor': t['factor'], 'value': t['value'], 'personal': bool(t.get('fact_ids'))} for t in terms if t.get('value')), key=lambda t: -abs(t['value']))[:6]))
    return rows


def summary(flow):
    ev = evenings(flow)
    venues = {}
    for pid, rs in ev.items():
        for r in rs:
            venues[r.get('venue') or r['kind']] = venues.get(r.get('venue') or r['kind'], 0) + 1
    twice = sorted(pid for pid, rs in ev.items() if len(rs) >= 2 and rs[0].get('venue') and rs[0].get('venue') == rs[1].get('venue'))
    ph_twice = sorted(pid for pid in twice if ev[pid][0].get('venue') == 'PIZZA_HILL')
    rep = classify(flow)
    counts = {}
    for r in rep: counts[r['cls']] = counts.get(r['cls'], 0) + 1
    return dict(evenings=sum(len(v) for v in ev.values()), dinners_by_venue=dict(sorted(venues.items(), key=lambda kv: -kv[1])),
                same_venue_both_evenings=twice, pizza_hill_both_evenings=ph_twice, repeats=rep, repeat_class_counts=counts,
                evening_choices={pid: [r.get('venue') or r['kind'] for r in rs] for pid, rs in ev.items()})


def run_condition(name, ids, cfg):
    env = {k: v for k, v in cfg.items() if k.startswith('HILLINK_')}
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        req = PL.base_request(ids, 'stay_2', catalog_options=cfg.get('catalog_options'))
        t = time.time(); flow = VR.run_visit(req)
        if flow.get('error'): return dict(error=flow.get('error'))
        out = summary(flow); out['seconds'] = round(time.time() - t, 1); out['diagnostic'] = cfg
        return out
    finally:
        for k, v in saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v


def main():
    out = sys.argv[1]
    args = dict(zip(sys.argv[2::2], sys.argv[3::2]))
    ids = args.get('--personas', '').split(',') if args.get('--personas') else sorted(VR.IR.allowed_personas(VR.AD.DEMO))
    only = args.get('--only', ','.join(CONDITIONS)).split(',')
    res = dict(duration='stay_2', personas=ids, conditions={})
    for name in only:
        r = run_condition(name, ids, CONDITIONS[name]); res['conditions'][name] = r
        print(name, r.get('seconds'), 'PH twice', len(r.get('pizza_hill_both_evenings') or []), 'same venue twice', len(r.get('same_venue_both_evenings') or []),
              r.get('repeat_class_counts'), r.get('dinners_by_venue'), flush=True)
        json.dump(res, open(out, 'w'), ensure_ascii=False)
    c0 = res['conditions'].get('C0')
    if c0:
        base = {(r['customer_id'], r['date']): r['cls'] for r in c0['repeats']}
        for name, r in res['conditions'].items():
            if name == 'C0' or r.get('error'): continue
            kept = {k: v for k, v in base.items() if (k[0], k[1]) in {(x['customer_id'], x['date']) for x in r['repeats']}}
            r['vs_C0'] = dict(personal_repeats_kept=sum(1 for v in kept.values() if v == 'PERSONAL'), personal_repeats_in_C0=sum(1 for v in base.values() if v == 'PERSONAL'),
                              unbased_repeats_kept=sum(1 for v in kept.values() if v in ('STRUCTURAL', 'INSUFFICIENT')),
                              unbased_repeats_in_C0=sum(1 for v in base.values() if v in ('STRUCTURAL', 'INSUFFICIENT')),
                              changed_customers=sorted(pid for pid in r['evening_choices'] if r['evening_choices'][pid] != c0['evening_choices'].get(pid)))
        json.dump(res, open(out, 'w'), ensure_ascii=False)
    print('written', out)


if __name__ == '__main__':
    main()
