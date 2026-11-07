"""Size estimate for a leaner V18 selection question (design measurement only — not a policy).

  python3 tools/v18_bench/lean_estimate.py <private run dir> [call key ...]

Reads recorded request bodies from a private bench run and prints, per call, the size of each block
as sent and as it would be under the lean rules below. Prints sizes only (no request text), so the
output can be summarised publicly. Nothing here changes what any policy sends.

Lean rules (draft, see 설계-문맥경량화-상태분리-1106.md):
- personal: each record keeps fact_ids, summary, source_scope; review metadata (stage, actor,
  provenance, grades, coverage, policy texts) stays in the decision record; profile keeps type+summary.
- visit: the facts a choice can use (date, nights, party size/status, relationship/purpose status,
  building, breakfast, pre-arrival intake); scenario/contract/budget metadata stays in the record.
- history: today's actions once (label, start, end); state.recent_actions and state.meal_history,
  which repeat activity_experiences / meal_experiences, are dropped; constant fields
  (satisfaction NOT_OBSERVED, recovery basis) are said once in the instructions.
- reassessment: the last two decisions (time, action, reason) only.
- state: time, fatigue level/percent, meals flags, today_remaining counts; basis strings dropped.
- candidates: action_id, type, label, schedule/price fields, M4 rank, shown_because and direct
  evidence ids; meal options keep basket_id, label, total, items (label, quantity), meal_equivalents,
  marks; the basket note appears once and only when a meal is among the candidates.
- shortlist: counts only (the dropped list stays in the trace).
- system prompt: meal/basket/meal_assessment lines only when a meal candidate is shown.
"""
import json, re, sys
from pathlib import Path

L = lambda v: len(json.dumps(v, ensure_ascii=False, separators=(',', ':')))
VISIT_KEEP = ('date', 'nights', 'party_size', 'party_status', 'relationship_status', 'purpose', 'building', 'breakfast', 'pre_arrival_intake', 'checked_in', 'checked_out')
COND_KEEP = ('start_time', 'end_time', 'duration_minutes', 'travel_minutes', 'wait_minutes', 'price_krw', 'included', 'reservation')
MEAL_LINE = re.compile(r'basket|meal_assessment|식사\(type=MEAL\)')


def lean(system, personal, ctx):
    meal = any(c.get('type') in ('MEAL', 'BREAKFAST') for c in ctx.get('candidates', []))
    p = dict(profile={k: (personal.get('profile') or {}).get(k) for k in ('customer_type', 'summary')},
             records=[{k: r.get(k) for k in ('fact_ids', 'summary', 'source_scope')} for r in personal.get('evidence_records', [])],
             scope={k: (personal.get('evidence_scope') or {}).get(k) for k in ('mode', 'sent_fact_count', 'full_fact_count')})
    st = ctx.get('state') or {}
    c = dict(
        visit={k: v for k, v in (ctx.get('visit') or {}).items() if k in VISIT_KEEP},
        today=[dict(label=x.get('label'), start=x.get('start_time'), end=x.get('end_time')) for x in ctx.get('activity_experiences', []) if x.get('date') == (ctx.get('visit') or {}).get('date')],
        meals=[{k: m.get(k) for k in ('slot', 'label', 'venue', 'start_time', 'end_time', 'items', 'order_total_krw') if k in m} for m in ctx.get('meal_experiences', [])],
        recent=[{k: d.get(k) for k in ('time', 'action_id', 'reason')} for d in ((ctx.get('reassessment') or {}).get('recent_decisions') or [])[-2:]],
        state=dict(time=st.get('time'), fatigue=dict(level=(st.get('fatigue_scale') or {}).get('level'), percent=(st.get('fatigue_scale') or {}).get('ratio_percent')),
                   meals=st.get('meals'), today_remaining={k: v for k, v in (st.get('today_remaining') or {}).items() if k != 'basis'}),
        memory=ctx.get('memory'),
        candidates=[dict(action_id=x['action_id'], type=x['type'], label=x.get('label'),
                         conditions={k: v for k, v in (x.get('conditions') or {}).items() if k in COND_KEEP},
                         m4={k: (x.get('m4') or {}).get(k) for k in ('rank_in_type', 'of', 'shown_because', 'direct_evidence_fact_ids')},
                         **({'basket_groups': [dict(label=g.get('label'), role=g.get('role'), shown_because=g.get('shown_because'), experience_fact_ids=g.get('experience_fact_ids'),
                                                    options=[dict(basket_id=o['basket_id'], label=o['label'], total_krw=o['total_krw'], meal_equivalents=o.get('meal_equivalents'),
                                                                  marks=o.get('marks'), items=[(i.get('label'), i.get('quantity')) for i in o.get('items', [])]) for o in g['options']])
                                               for g in x['basket_groups']]} if x.get('basket_groups') else {}))
                    for x in ctx.get('candidates', [])],
        basket_note=(next((x.get('basket_note') for x in ctx.get('candidates', []) if x.get('basket_note') and len(x['basket_note']) > 40), None) if meal else None),
        shortlist={k: (ctx.get('shortlist') or {}).get(k) for k in ('candidate_count', 'shown')})
    sysl = system if meal else '\n'.join(l for l in system.split('\n') if not MEAL_LINE.search(l))
    return len(sysl), L(p), L(c)


def main(run_dir, keys):
    calls = Path(run_dir) / 'calls'
    files = [calls / (k + '.request.json') for k in keys] if keys else sorted(calls.glob('*_a1.request.json'))
    print('call | sent system/personal/context = total | lean system/personal/context = total | lean/sent')
    for f in files:
        b = json.load(open(f, encoding='utf-8'))['request_body']
        system = b['input'][0]['content']; users = [json.loads(m['content']) for m in b['input'][1:]]
        ctx = {k: v for u in users for k, v in u.items()}; personal = ctx.pop('personal', {})
        sent = (len(system), L(personal), L(ctx)); ln = lean(system, personal, ctx)
        print('%s | %d/%d/%d = %d | %d/%d/%d = %d | %.0f%%' % (f.name.replace('.request.json', ''), *sent, sum(sent), *ln, sum(ln), 100 * sum(ln) / sum(sent)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
