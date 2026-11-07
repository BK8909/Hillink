"""Private, local HTML report of a V18 bench run (A/B/C/D side by side). Never written inside the repo.

For each bench point and variant it shows what was actually sent (system prompt, user messages,
schema, settings), the raw provider response, the parsed choice with the engine-filled defaults kept
apart from what the model wrote, validation and replans, tokens/cache/time/cost, and the request
hash <-> body <-> response correspondence (recomputed here). It also diffs A<->B, B<->C, B<->D.
"""
import difflib, hashlib, html, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard as G  # noqa: E402
import request_diff as RD  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NAMES = {'LLM_AUTONOMOUS_CUSTOMER_V18': ('A', '기준: 전체 개인 근거 · 현재 출력 · high'),
         'LLM_AUTONOMOUS_CUSTOMER_V18B': ('B', '개인 근거 블록만 후보 관련 근거로 교체 · high'),
         'LLM_AUTONOMOUS_CUSTOMER_V18BM': ('C', 'B와 같은 입력 · reasoning medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V18BD': ('D', 'B와 같은 입력 · 최소 출력 계약 · high'),
         'LLM_AUTONOMOUS_CUSTOMER_V18N': ('N', 'C + 상태 판단 분리(관측·엔진 추정·모델 추정+신뢰도) · medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V18L': ('L', 'C + 경량 입력·판단 유형별 지시 · medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V18S': ('S', 'C + 중립 제시(M4 순위·가격 표시 제거 · 옵션 가격순) · medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V18P': ('P', 'C + 개인 신호 우선 식당 선별(제시는 C와 같음) · medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V18M': ('M', 'C + 식사 출력 간소화(수량 이유는 엔진 책임) · medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V18LS': ('LS', 'L2 결정 주제별 근거 + S2 중립 제시(순위·가격 표시 제거 · 종류/이름순) · medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V19LS': ('V19LS', 'LS + 근거 성격·재방문 거부·남김 표시 · 후보 연결 · 반복 신호 · tradeoff_note · 선택 진단 · medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V18S2': ('S2', 'C + 중립 제시 2(M4 순위·가격 표시 제거 · 후보·구성·옵션 종류/이름순 · 점수/가격 사유 중립) · medium'),
         'LLM_AUTONOMOUS_CUSTOMER_V18L2': ('L2', 'L + 결정 주제별 근거(음식 신호·기념 식사·식사 가격 관측) · medium')}
PAIRS = [('LLM_AUTONOMOUS_CUSTOMER_V18', 'LLM_AUTONOMOUS_CUSTOMER_V18B'), ('LLM_AUTONOMOUS_CUSTOMER_V18B', 'LLM_AUTONOMOUS_CUSTOMER_V18BM'),
         ('LLM_AUTONOMOUS_CUSTOMER_V18B', 'LLM_AUTONOMOUS_CUSTOMER_V18BD'), ('LLM_AUTONOMOUS_CUSTOMER_V18BM', 'LLM_AUTONOMOUS_CUSTOMER_V18N'), ('LLM_AUTONOMOUS_CUSTOMER_V18BM', 'LLM_AUTONOMOUS_CUSTOMER_V18M'), ('LLM_AUTONOMOUS_CUSTOMER_V18L', 'LLM_AUTONOMOUS_CUSTOMER_V18L2')]
E = lambda x: html.escape(str(x if x is not None else '—'))
CSS = '''
:root{--bg:#faf8f4;--fg:#211d18;--mut:#6d655b;--line:#ddd5c9;--card:#fff;--a:#7a4b22;--ok:#2f6b3a;--bad:#9b2c2c;--warn:#8a5a00;--code:#f3efe8}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17150f;--fg:#ece6dc;--mut:#a59c90;--line:#3a352d;--card:#211e17;--a:#d9a46d;--ok:#7cc48a;--bad:#ef8b8b;--warn:#e6b45c;--code:#2a261e}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 -apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
main{max-width:1500px;margin:0 auto;padding:20px 16px 60px}h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
h3{font-size:15px;margin:0 0 6px}.mut{color:var(--mut)}.banner{border:1px solid var(--warn);color:var(--warn);padding:8px 12px;border-radius:6px;margin:10px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;min-width:0}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}th{color:var(--mut);font-weight:600}
pre{background:var(--code);padding:8px;border-radius:6px;overflow:auto;max-height:520px;font-size:12px;white-space:pre-wrap;word-break:break-word}
details{margin:6px 0}summary{cursor:pointer;color:var(--a)}.ok{color:var(--ok)}.bad{color:var(--bad)}.chip{display:inline-block;border:1px solid var(--line);border-radius:10px;padding:0 7px;margin:0 4px 2px 0;font-size:12px}
.model{border-left:3px solid var(--ok);padding-left:8px}.engine{border-left:3px solid var(--warn);padding-left:8px}.diffadd{color:var(--ok)}.diffdel{color:var(--bad)}
'''


def load(path):
    try: return json.load(open(path, encoding='utf-8'))
    except FileNotFoundError: return None


def canon(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def identity(req):
    payload = {'request_policy': req['request_policy'], 'policy': req['policy'], 'purpose': req['purpose'], 'request': req['request_body']}
    return hashlib.sha256(canon(payload).encode()).hexdigest()


def user_blocks(body):
    out = {}
    for m in body['input'][1:]:
        try: out.update(json.loads(m['content']))
        except Exception: out['<text>'] = m['content']
    return out


def facts_map(ctx):
    m = {}
    for r in (ctx.get('personal') or {}).get('evidence_records', []):
        for f in r.get('fact_ids', []): m[f] = r.get('summary')
    return m


def labels(ctx):
    return {r['action_id']: r.get('label') or r['action_id'] for r in ctx.get('candidates', [])}


def diff_text(a, b, name_a, name_b):
    lines = list(difflib.unified_diff(a.splitlines(), b.splitlines(), name_a, name_b, lineterm='', n=1))
    if not lines: return '<p class="mut">차이 없음</p>'
    body = '\n'.join('<span class="%s">%s</span>' % ('diffadd' if l.startswith('+') and not l.startswith('+++') else 'diffdel' if l.startswith('-') and not l.startswith('---') else '', E(l)) for l in lines)
    return '<pre>%s</pre>' % body


def diff_requests(ra, rb, na, nb):
    """Field-level diff of the two actual request bodies and whether only the intended fields differ."""
    ba, bb = ra['request_body'], rb['request_body']
    res = RD.compare(ba, bb, (na, nb))
    ok = res['verdict'] == 'ONLY_INTENDED_DIFFERENCES'
    out = ['<h3>%s ↔ %s · 의도한 차이: %s</h3>' % (na, nb, E(res['expected'])),
           '<p>판정: %s</p>' % ('<span class="ok">의도한 필드만 다름</span>' if ok else '<span class="bad">의도하지 않은 차이 있음</span>')]
    row = lambda d: '<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        E(d['path']), E(d['change']), E(d.get('size_a')), E(d.get('size_b')),
        '<span class="ok">의도함</span>' if d not in res['unexpected'] else '<span class="bad">의도하지 않음</span>')
    out.append('<table><tr><th>필드 경로(실제 전송 본문)</th><th>변화</th><th>%s 크기</th><th>%s 크기</th><th>판정</th></tr>%s</table>'
               % (na, nb, ''.join(row(d) for d in res['differences']) or '<tr><td colspan=5 class="mut">차이 없음</td></tr>'))
    if res['structure_differences']:
        out.append('<p class="bad">개인 근거 블록 구조 차이: %s</p>' % E(res['structure_differences']))
    elif (na, nb) == ('A', 'B'):
        out.append('<p class="ok">개인 근거 블록: 키·중첩 구조 동일(Fact id로 키를 둔 표는 내용으로 취급)</p>')
    if res['expected_but_identical']:
        out.append('<p class="mut">의도한 차이 필드 중 실제로 같은 것: %s</p>' % E(res['expected_but_identical']))
    out.append('<details><summary>시스템 프롬프트 차이</summary>%s</details>' % diff_text(ba['input'][0]['content'], bb['input'][0]['content'], na, nb))
    return ''.join(out)


def korean_summary(att, lab, fmap, policy):
    if att.get('blocked'): return '실행하지 않음 — %s' % att['blocked']
    if att.get('error'): return '호출 오류 — %s' % att['error']
    p = att.get('plan') or {}; ans = att.get('answer') or {}
    sel = p.get('action_id') or ans.get('selected_action_id')
    parts = ['선택: %s' % lab.get(sel, sel)]
    if p.get('selected_basket_id'): parts.append('주문 %s원' % format(p.get('order_total_krw') or 0, ','))
    facts = p.get('supporting_fact_ids') or ans.get('fact_ids') or ans.get('supporting_fact_ids') or []
    parts.append('근거 ' + (', '.join(facts) if facts else '없음(상황 판단)'))
    alt = ans.get('rejected_action_id') or (ans.get('rejected_alternative') or {}).get('action_id')
    if alt: parts.append('비교: %s' % lab.get(alt, alt))
    parts.append('이유: %s' % (ans.get('reason') or p.get('decision_summary') or '—'))
    parts.append('검증 %s' % ('통과' if att.get('validation') == 'PASS' else '거절(%s)' % str(att.get('validation'))[:80]))
    return ' · '.join(parts)


PREF_RX = __import__('re').compile(r'좋아하|선호|취향|즐기는|즐겨|성향|평소에|늘 |항상|좋아할')


def checklist(att, ctx, sent):
    """Mechanical checks a reviewer can trust, and the judgement items left to a person."""
    ans = att.get('answer') or {}; plan = att.get('plan') or {}
    cited = set(plan.get('supporting_fact_ids', []) + plan.get('counterevidence_fact_ids', []))
    text = ' '.join(str(x) for x in (ans.get('reason'), (ans.get('rejected_alternative') or {}).get('reason'), ans.get('next_intent')) if x)
    scale = ((ctx.get('state') or {}).get('fatigue_scale') or {})
    rows = [
        ('인용 Fact가 보낸 근거 안에 있음', ('예' if cited <= set(sent) else '아니오: %s' % sorted(cited - set(sent))) if cited else '인용 없음'),
        ('성향·취향 표현(근거 없이 쓰였는지 사람 확인)', ('표현 있음 · 인용 %d개 → 확인 필요' % len(cited)) if PREF_RX.search(text) else '표현 없음'),
        ('반례 인용', ', '.join(plan.get('counterevidence_fact_ids') or []) or ('요청 안 함(D)' if 'fact_ids' in ans else '없음')),
        ('하루 마무리 선택과 피로 척도', ('선택함 · 피로 %s(%s%%)' % (scale.get('level'), scale.get('ratio_percent'))) if plan.get('action_id') == 'end_day_in_room' else '해당 없음'),
        ('검증·재계획', '%s%s' % ('통과' if att.get('validation') == 'PASS' else '거절', '')),
        ('근거 적합성 (사람)', ''), ('선택 이유의 자연스러움 (사람)', ''), ('불필요한 개인 성향 추정 (사람)', ''),
    ]
    return '<table><tr><th colspan=2>검수 체크</th></tr>%s</table>' % ''.join('<tr><td>%s</td><td>%s</td></tr>' % (E(a), E(b) if b else '<span class="mut">□ 적합 □ 부분 □ 부적합 · 메모:</span>') for a, b in rows)


def variant_card(point, rec, calls):
    policy = rec['policy']; letter, what = NAMES.get(policy, (policy, ''))
    atts = rec['attempts']
    reqs = [load(calls / ('%s.request.json' % a['call_key'])) if a.get('call_key') else None for a in atts]
    resps = [load(calls / ('%s.response.json' % a['call_key'])) if a.get('call_key') else None for a in atts]
    first = reqs[0] or {}
    ctx = user_blocks(first['request_body']) if first else {}
    lab, fmap = labels(ctx), facts_map(ctx)
    tok = lambda k: sum((a.get(k) or 0) for a in atts) if any(a.get(k) is not None for a in atts) else None
    cost = sum(float(a.get('cost_upper_usd') or 0) for a in atts)
    h = ['<div class="card"><h3>%s · %s</h3><p class="mut">%s</p>' % (letter, E(policy.replace('LLM_AUTONOMOUS_CUSTOMER_', '')), E(what))]
    h.append('<table><tr><th>시도</th><td>%d%s</td></tr><tr><th>입력 / 캐시</th><td>%s / %s</td></tr><tr><th>출력 / reasoning</th><td>%s / %s</td></tr><tr><th>시간</th><td>%s초</td></tr><tr><th>비용(토큰 기준 상한)</th><td>$%.4f</td></tr><tr><th>요청 크기</th><td>%s자 · 인용 가능 Fact %s개</td></tr></table>'
             % (len(atts), ' (재계획 포함)' if len(atts) > 1 else '', E(tok('input_tokens')), E(tok('cached_tokens')), E(tok('output_tokens')), E(tok('reasoning_tokens')),
                E(round(sum(float(a.get('seconds') or 0) for a in atts), 1)), cost, E(rec.get('request_chars')), E(rec.get('citable'))))
    for i, (a, rq, rs) in enumerate(zip(atts, reqs, resps), 1):
        tag = '재계획' if i > 1 else '첫 시도'
        h.append('<h3 style="margin-top:10px">%s</h3><p>%s</p>' % (tag, E(korean_summary(a, lab, fmap, policy))))
        if a.get('reused_from_checkpoint'): h.append('<p class="mut">체크포인트에서 재사용(새 호출 아님)</p>')
        ans = a.get('answer'); plan = a.get('plan') or {}
        if ans is not None:
            h.append('<div class="model"><b>모델이 직접 쓴 값</b><pre>%s</pre></div>' % E(json.dumps(ans, ensure_ascii=False, indent=1)))
            facts = sorted(set(plan.get('supporting_fact_ids', []) + plan.get('counterevidence_fact_ids', [])))
            if facts: h.append('<p><b>인용 Fact</b></p><ul>%s</ul>' % ''.join('<li>%s — %s</li>' % (E(f), E(fmap.get(f, '(요약 없음)'))) for f in facts))
        if ans is not None:
            sent = list((ctx.get('personal') or {}).get('citable_fact_ids', []))
            h.append(checklist(a, ctx, sent))
        if plan.get('engine_default_fields'):
            h.append('<div class="engine"><b>엔진이 채운 기본값 · 모델 진술 아님</b><pre>%s</pre></div>' % E(json.dumps({k: plan.get(k.split('.')[0]) for k in plan['engine_default_fields']}, ensure_ascii=False, indent=1)))
        if rq:
            ok = identity(rq) == rq['input_sha256']
            match = (rs or {}).get('provider_identity_matches')
            resp_ok = ((rs or {}).get('identity') or {}).get('input_sha256') == rq['input_sha256'] if rs else None
            body_sha = hashlib.sha256(canon(rq['request_body']).encode()).hexdigest()
            h.append('<p class="mut">요청 식별 해시 %s… · 본문에서 재계산 %s · 응답 파일이 가리키는 요청 %s · provider 수신 본문 일치 %s · 본문 SHA-256 %s… · 응답 id %s</p>'
                     % (E(rq['input_sha256'][:16]), '<span class="ok">일치</span>' if ok else '<span class="bad">불일치</span>',
                        {True: '<span class="ok">같은 요청</span>', False: '<span class="bad">다른 요청</span>', None: '응답 없음'}[resp_ok],
                        {True: '<span class="ok">예</span>', False: '<span class="bad">아니오</span>', None: '오프라인(해당 없음)'}[match],
                        E(body_sha[:16]), E(((rs or {}).get('trace') or {}).get('response_id'))))
            body = rq['request_body']
            h.append('<details><summary>실제 전송한 시스템 프롬프트 (%d자)</summary><pre>%s</pre></details>' % (len(body['input'][0]['content']), E(body['input'][0]['content'])))
            for j, m in enumerate(body['input'][1:], 1):
                try: pretty = json.dumps(json.loads(m['content']), ensure_ascii=False, indent=1)
                except Exception: pretty = m['content']
                h.append('<details><summary>실제 전송한 사용자 메시지 %d (%d자)</summary><pre>%s</pre></details>' % (j, len(m['content']), E(pretty)))
            h.append('<details><summary>출력 스키마 · 설정</summary><pre>%s</pre></details>' % E(json.dumps(dict(model=body['model'], reasoning=body['reasoning'], max_output_tokens=body['max_output_tokens'], schema=body['text']['format']['schema']), ensure_ascii=False, indent=1)))
        if rs is not None:
            raw = rs.get('raw_response')
            h.append('<details><summary>원본 응답 JSON%s</summary><pre>%s</pre></details>' % ('' if raw else ' (오프라인 합성 — 모델 응답 아님)', E(json.dumps(raw if raw else rs.get('answer'), ensure_ascii=False, indent=1))))
        err = load(calls / ('%s.error.json' % a['call_key'])) if a.get('call_key') else None
        if err: h.append('<details open><summary class="bad">provider 오류 기록</summary><pre>%s</pre></details>' % E(json.dumps(err, ensure_ascii=False, indent=1)))
    h.append('</div>')
    return ''.join(h), reqs[0]


def write(run_dir, bench_path):
    run_dir = Path(run_dir).resolve(); top = ROOT.parent.resolve()
    out = run_dir / 'report.html'
    if top in out.parents: raise SystemExit('refusing to write the private report inside the repository')
    calls = run_dir / 'calls'
    points = [json.loads(l) for l in open(bench_path, encoding='utf-8')] if Path(bench_path).exists() else []
    summary = load(run_dir / 'run_summary.json') or {}
    manifests = sorted(run_dir.glob('manifest.*.json'))
    man = load(manifests[-1]) if manifests else {}
    offline = summary.get('shadow') == 'offline' or man.get('shadow') == 'offline'
    parts = ['<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V18 질문 설계 비교</title><style>%s</style></head><body><main>' % CSS]
    parts.append('<h1>V18 질문 설계 A/B/C/D 비교</h1><p class="mut">코드 %s · 모델 %s · reasoning 기본 %s · 실행 %s</p>' % (E(man.get('code_commit', '')[:10]), E(man.get('model')), E(man.get('effort_default')), E(man.get('started_at'))))
    parts.append('<div class="banner">비공개 로컬 보고서입니다. 실제 요청·응답과 후기 요약이 들어 있으니 저장소·공개 위치에 올리지 마세요.%s</div>' % (' <b>오프라인 합성 실행: 응답은 모델 판단이 아니라 계약 확인용 합성 값입니다.</b>' if offline else ''))
    st = summary.get('run_state') or load(run_dir / 'run_state.json') or {}
    parts.append('<p>이번 실행 상한: 새 호출 %s회 · 최악 비용 $%s · 사용: 호출 시작 %s회 · 최악 예약 $%s · 정산 상한 $%s · 재사용 %s · 차단 %s</p>' % (
        E(man.get('max_calls')), E(man.get('max_usd')), E(st.get('calls_started')), E(st.get('ceiling_usd')), E(st.get('settled_upper_usd')), E(st.get('reused')), E(len(st.get('blocked') or []))))
    if summary.get('ledger_after') or man.get('ledger_before'):
        parts.append('<p class="mut">공유 원장: 실행 전 %s · 실행 후 %s</p>' % (E(man.get('ledger_before')), E(summary.get('ledger_after'))))
    parts.append('<p class="mut">한계: 궤적은 기록된 선택을 재생한 벤치용 상태입니다. 이전 판단 문장(reassessment)은 V17 원문이 아니라 "기록된 선택 재현" 문장이며 네 변형에 똑같이 들어갑니다. '
                 'N03의 룸서비스 혼합 주문처럼 엔진 견적으로 표현할 수 없는 선택은 후보 누락 문제이지 프롬프트 문제가 아닙니다.</p>')
    for p in points:
        step = p.get('recorded_step') or {}
        same = len({v.get('candidates_sha256') for v in p['variants']}) == 1
        parts.append('<h2>%s %s %s</h2>' % (E(p['pid']), E(p['date']), E(p['time'])))
        parts.append('<p>기록된 선택(벤치 궤적): <b>%s</b> · 기록된 대안 %s · 후보 %d/%d개 · 네 변형 후보 %s</p>' % (
            E(step.get('note') or step.get('action') or step.get('action_contains')), E([x.get('action') or x.get('action_contains') for x in step.get('alternatives', [])]),
            len(p['shortlist']), p['candidate_count'], '<span class="ok">동일(해시 일치)</span>' if same else '<span class="bad">다름</span>'))
        parts.append('<details><summary>후보 목록과 선별 이유</summary><table><tr><th>후보</th><th>유형</th><th>선별 이유</th><th>바구니 묶음</th></tr>%s</table></details>' % ''.join(
            '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (E(r['action_id']), E(r['type']), E(r.get('shown_because')), E('; '.join('%s(%d)' % (g['label'], len(g['options'])) for g in r.get('groups', [])))) for r in p['shortlist']))
        cards, first = [], {}
        for rec in p['variants']:
            html_card, req = variant_card(p, rec, calls); cards.append(html_card); first[rec['policy']] = req
        parts.append('<div class="grid">%s</div>' % ''.join(cards))
        parts.append('<h2>변형 사이의 실제 변경 (첫 시도 요청 기준)</h2>')
        for a, b in PAIRS:
            if first.get(a) and first.get(b):
                parts.append('<div class="card" style="margin-bottom:10px">%s</div>' % diff_requests(first[a], first[b], NAMES[a][0], NAMES[b][0]))
        c, l = first.get('LLM_AUTONOMOUS_CUSTOMER_V18BM'), first.get('LLM_AUTONOMOUS_CUSTOMER_V18L')
        if c and l:
            res = RD.compare_lean(c['request_body'], l['request_body'])
            parts.append('<div class="card" style="margin-bottom:10px"><h3>C ↔ L · 경량 입력이 선택에 필요한 것을 보존했는가</h3><p>판정: %s</p><table>%s</table><p class="mut">크기(메시지별 글자 수) C %s · L %s · L에서 빠진 블록 %s · 새 블록 %s</p></div>' % (
                '<span class="ok">보존</span>' if res['verdict'] == 'LEAN_PRESERVES_CHOICE_INPUTS' else '<span class="bad">누락 있음</span>',
                ''.join('<tr><td>%s</td><td>%s</td></tr>' % (E(k), E(v)) for k, v in res['checks'].items()), E(res['sizes']['c']), E(res['sizes']['l']), E(res['removed_top_level']), E(res['added_top_level'])))
    parts.append('</main></body></html>')
    G.write_private_text(str(out), ''.join(parts))
    return out


if __name__ == '__main__':
    print(write(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else Path(sys.argv[1]) / 'bench.jsonl'))
