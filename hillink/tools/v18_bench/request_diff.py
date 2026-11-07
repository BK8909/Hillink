"""Field-level comparison of two actual V18 request bodies, with the differences each pair is meant to have.

  A <-> B : only the contents of the persona block (user message 1, `personal`); same keys and nesting
  B <-> C : only reasoning.effort
  B <-> D : only the output contract — the system prompt's "응답 작성:" section and the output schema

Everything else (system prompt, message count and order, every other context block, candidates, schema,
model, output limit) must be byte-identical. Pure functions over the recorded request bodies; the result
holds field paths, sizes and verdicts only (no request text), so it can be summarised publicly.
"""
import json

OUTPUT_MARKER = '\n응답 작성:'
ID_KEYED = ('evidence_grades', 'selection_reasons', 'grade_by_fact')   # dicts keyed by Fact id: keys are content, not structure
EXPECTED = {
    ('A', 'B'): dict(paths=('input[1].personal',), meaning='개인 근거 블록 내용만(필드 구조 동일)'),
    ('B', 'C'): dict(paths=('reasoning.effort',), meaning='reasoning effort만'),
    ('B', 'D'): dict(paths=('input[0].output_contract', 'text.format.schema'), meaning='출력 계약만(시스템 프롬프트의 응답 작성 절 · 출력 스키마)'),
    ('C', 'M'): dict(paths=('input[0].output_contract', 'text.format.schema'), meaning='식사 출력 칸만(수량 이유 제거 · 응답 작성 한 줄)'),
    ('L', 'L2'): dict(paths=('input[1].personal',), meaning='개인 근거 블록 내용만(결정 주제별 근거 추가 · 필드 구조 동일)'),
    ('C', 'N'): dict(paths=('input[0].instructions', 'input[0].output_contract', 'input[2].need_model', 'text.format.schema'),
                     meaning='상태 판단만(섭취 지시 한 줄 · need_estimate 출력 · need_model 입력 블록)'),
}


def _size(v):
    return len(json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def view(body):
    """The request as one tree: user messages parsed, system prompt split into instructions / output contract."""
    out = {k: v for k, v in body.items() if k != 'input'}
    for i, m in enumerate(body['input']):
        if m['role'] == 'system':
            head, sep, tail = m['content'].partition(OUTPUT_MARKER)
            out['input[%d]' % i] = dict(role='system', instructions=head, output_contract=(sep + tail) if sep else None)
        else:
            try: content = json.loads(m['content'])
            except ValueError: content = {'<text>': m['content']}
            out['input[%d]' % i] = dict(content, role=m['role']) if isinstance(content, dict) else {'<value>': content, 'role': m['role']}
    out['message_count'] = len(body['input'])
    out['message_roles'] = [m['role'] for m in body['input']]
    return out


def leaf_diffs(a, b, path=''):
    """Paths whose values differ. Lists and id-keyed maps are compared whole (reported with their sizes)."""
    if isinstance(a, dict) and isinstance(b, dict) and path.rsplit('.', 1)[-1] not in ID_KEYED:
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            p = '%s.%s' % (path, k) if path else k
            if k not in a: out.append(dict(path=p, change='ADDED', size_b=_size(b[k])))
            elif k not in b: out.append(dict(path=p, change='REMOVED', size_a=_size(a[k])))
            else: out.extend(leaf_diffs(a[k], b[k], p))
        return out
    if a == b: return []
    return [dict(path=path, change='VALUE', size_a=_size(a), size_b=_size(b))]


def shape(x, key=''):
    if isinstance(x, dict):
        return 'ID_MAP' if key in ID_KEYED else {k: shape(v, k) for k, v in x.items()}
    if isinstance(x, list):
        kinds = {json.dumps(shape(v), sort_keys=True) for v in x}
        return ['LIST', sorted(kinds)]
    return type(x).__name__


def structure_diffs(a, b, path=''):
    """Where the key/nesting structure differs (list item shapes are unioned, so a shorter list is not a difference)."""
    if isinstance(a, dict) and isinstance(b, dict) and path.rsplit('.', 1)[-1] not in ID_KEYED:
        out = [dict(path='%s.%s' % (path, k), change='KEY_ONLY_IN_' + ('A' if k in a else 'B')) for k in sorted(set(a) ^ set(b))]
        for k in sorted(set(a) & set(b)): out.extend(structure_diffs(a[k], b[k], '%s.%s' % (path, k)))
        return out
    if isinstance(a, list) and isinstance(b, list):
        sa = {json.dumps(shape(v), sort_keys=True) for v in a}; sb = {json.dumps(shape(v), sort_keys=True) for v in b}
        # every item shape of the shorter list must exist in the longer one (filtered lists keep item shape)
        small, big = (sa, sb) if len(a) <= len(b) else (sb, sa)
        return [] if small <= big else [dict(path=path, change='LIST_ITEM_SHAPE')]
    if type(a) != type(b) and None not in (a, b):
        return [dict(path=path, change='TYPE %s->%s' % (type(a).__name__, type(b).__name__))]
    return []


def compare(body_a, body_b, pair):
    va, vb = view(body_a), view(body_b)
    diffs = leaf_diffs(va, vb)
    allowed = EXPECTED[pair]['paths']
    inside = lambda p: any(p == x or p.startswith(x + '.') for x in allowed)
    unexpected = [d for d in diffs if not inside(d['path'])]
    struct = []
    if pair in (('A', 'B'), ('L', 'L2')):
        pa, pb = va.get('input[1]', {}).get('personal'), vb.get('input[1]', {}).get('personal')
        struct = structure_diffs(pa, pb, 'input[1].personal') if pa is not None and pb is not None else [dict(path='input[1].personal', change='MISSING')]
    missing = [x for x in allowed if not any(d['path'] == x or d['path'].startswith(x + '.') for d in diffs)]
    return dict(pair='%s<->%s' % pair, expected=EXPECTED[pair]['meaning'], expected_paths=list(allowed), differences=diffs,
                unexpected=unexpected, structure_differences=struct, expected_but_identical=missing,
                verdict='ONLY_INTENDED_DIFFERENCES' if not unexpected and not struct else 'UNINTENDED_DIFFERENCES')


def compare_all(bodies):
    """bodies: {'A': body, 'B': body, 'C': body, 'D': body} (first attempts)."""
    return [compare(bodies[x], bodies[y], (x, y)) for x, y in EXPECTED if x in bodies and y in bodies]


def _cands(body):
    ctx = {}
    for m in body['input'][1:]:
        try: ctx.update(json.loads(m['content']))
        except ValueError: pass
    return ctx


def compare_lean(body_c, body_l, pair='C<->L', ordered=True):
    """C vs L (lean): not a field diff (L is smaller by design) but what must survive the reduction:
    every candidate, every menu option with its items/quantity/total, every sent Fact id and summary,
    counterexamples, evidence links, schema and settings. Returns sizes and the checks."""
    c, l = _cands(body_c), _cands(body_l)
    opt = lambda ctx: {(x['action_id'], o['basket_id'], o['label'], o['total_krw'], json.dumps([(i.get('label'), i.get('quantity')) for i in o.get('items', [])], ensure_ascii=False))
                       for x in ctx.get('candidates', []) for g in x.get('basket_groups', []) for o in g['options']}
    links = lambda ctx: {(x['action_id'], k, f) for x in ctx.get('candidates', []) for k in ('direct_evidence_fact_ids', 'similar_elsewhere_fact_ids', 'scope_unconfirmed_fact_ids', 'evidence_fact_ids')
                         for f in ((x.get('m4') or {}).get(k) or [])}
    pc, pl = c.get('personal') or {}, l.get('personal') or {}
    recs = lambda p: {(tuple(r['fact_ids']), r.get('summary')) for r in (p.get('evidence_records') or p.get('records') or [])}
    counter = lambda p: json.dumps(((p.get('profile') or {}).get('review_confirmed') or {}).get('counterexamples', (p.get('profile') or {}).get('counterexamples', [])), ensure_ascii=False, sort_keys=True)
    checks = dict(
        candidates_same=(lambda u, v: u == v if ordered else sorted(u) == sorted(v))([x['action_id'] for x in c.get('candidates', [])], [x['action_id'] for x in l.get('candidates', [])]),
        menu_options_same=opt(c) == opt(l), menu_options=len(opt(c)),
        citable_same=pc.get('citable_fact_ids') == pl.get('citable_fact_ids'), citable=len(pc.get('citable_fact_ids') or []),
        records_same=recs(pc) == recs(pl), counterexamples_same=counter(pc) == counter(pl),
        evidence_links_same=links(c) == links(l),
        schema_same=body_c['text'] == body_l['text'], settings_same={k: body_c[k] for k in ('model', 'reasoning', 'max_output_tokens')} == {k: body_l[k] for k in ('model', 'reasoning', 'max_output_tokens')},
        message_count_same=len(body_c['input']) == len(body_l['input']))
    sizes = dict(c=[len(m['content']) for m in body_c['input']], l=[len(m['content']) for m in body_l['input']])
    ok = all(v for k, v in checks.items() if k.endswith('_same'))
    return dict(pair=pair, verdict='LEAN_PRESERVES_CHOICE_INPUTS' if ok else 'LEAN_DROPPED_CHOICE_INPUTS', checks=checks, sizes=sizes,
                removed_top_level=sorted(set(c) - set(l)), added_top_level=sorted(set(l) - set(c)))


def compare_transformed(body_a, body_b, transform, pair, meaning):
    """B must equal A with `transform` applied to its candidate block, plus exactly one changed system-prompt
    line (the sentence that describes the order). Used for C <-> S2: the neutral presentation is a pure
    function of C's request, so anything else that differs is unintended. Result: verdict, the changed
    system line count, and the (path-only) leaf differences left after the transform."""
    ta = json.loads(json.dumps(body_a))
    for m in ta['input'][1:]:
        try: c = json.loads(m['content'])
        except ValueError: continue
        if isinstance(c, dict) and 'candidates' in c:
            m['content'] = json.dumps(transform(c), ensure_ascii=False)
    sa = ta['input'][0]['content'].split('\n'); sb = body_b['input'][0]['content'].split('\n')
    changed_lines = sum(x != y for x, y in zip(sa, sb)) + abs(len(sa) - len(sb))
    va, vb = view(ta), view(body_b)
    for v in (va, vb): v['input[0]'] = dict(v['input[0]'], instructions=None)   # the one sentence is checked line by line above
    rest = leaf_diffs(va, vb)
    ok = not rest and changed_lines == 1
    return dict(pair=pair, expected=meaning, system_lines_changed=changed_lines, differences_after_transform=[d['path'] for d in rest],
                verdict='ONLY_INTENDED_DIFFERENCES' if ok else 'UNINTENDED_DIFFERENCES')


def compare_evidence_superset(body_s, body_ls, pair='S2<->LS'):
    """S2 vs LS: the same neutral candidates (same order, options, quantities, totals, evidence links),
    schema and settings; LS's personal evidence must contain all of S2's (it adds decision-topic records)."""
    base = compare_lean(body_s, body_ls, pair, ordered=True)
    s, l = _cands(body_s).get('personal') or {}, _cands(body_ls).get('personal') or {}
    recs = lambda p: [set(r['fact_ids']) for r in (p.get('evidence_records') or p.get('records') or [])]
    # a record LS sends with more of its Fact ids (the same observation) still covers S2's copy of it
    sup = dict(citable_superset=set(s.get('citable_fact_ids') or []) <= set(l.get('citable_fact_ids') or []),
               records_superset=all(any(r <= x for x in recs(l)) for r in recs(s)), added_fact_ids=len(set(l.get('citable_fact_ids') or []) - set(s.get('citable_fact_ids') or [])))
    ok = all(v for k, v in base['checks'].items() if k.endswith('_same') and k not in ('citable_same', 'records_same')) and sup['citable_superset'] and sup['records_superset']
    return dict(base, superset=sup, verdict='SAME_CHOICE_INPUTS_EVIDENCE_SUPERSET' if ok else 'UNINTENDED_DIFFERENCES')
