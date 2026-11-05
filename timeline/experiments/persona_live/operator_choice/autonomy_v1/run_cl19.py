"""CL-1024-19 실행기 — 규칙 기반 / 실제 LLM 보조 비교 · 입력 커버리지 · 제안 검증 로그 · 사용량 · 비용.
  python3 -m operator_choice.autonomy_v1.run_cl19 --mode check     --out DIR   # 1차 연결 검사(실호출 1회)
  python3 -m operator_choice.autonomy_v1.run_cl19 --mode compare3  --out DIR   # 2차 A07 · A05 · blog42 rule_only vs llm_assisted
  python3 -m operator_choice.autonomy_v1.run_cl19 --mode all --allow-expand --out DIR   # 3차 11명 rule vs llm · 동시 · 개입(사용자 승인 뒤)
  python3 -m operator_choice.autonomy_v1.run_cl19 --mode rules     --out DIR   # 규칙 기반만(키 없이): 11명 개별 · 동시 · 재현 · 개입 3종
출력: DIR/cl19_<mode>.json · DIR/llm_usage_<mode>.json(+llm_usage.json) · DIR/cl19_<mode>_report.md · DIR/llm_ledger.json (키 · 원문 · 경로 없음)
"""
import argparse, json, platform, sys, time
from pathlib import Path
from . import agent_day as AD, llm_layer as LL, profile_context as PC

THREE = ["A07", "A05", "blog42"]
NONACT = ("move", "wait", "idle")
IV = {
    "wine_fair_1300": dict(at="13:00", event=True, changes=[dict(at="13:00", label="포레스트 파크 와인페어 개최(2부 15:30~20:00 · 55,000원)", levers={"WINE_FAIR": {"available": True}})]),
    "pool_check": dict(at="12:00", event=False, changes=[dict(at="12:00", label="실내 수영장 16:00~19:00 점검", closed={"VISTA_POOL": ["16:00", "19:00"], "GRAND_POOL": ["16:00", "19:00"]})]),
    "pizzahill_full": dict(at="15:00", event=False, changes=[dict(at="15:00", label="피자힐 저녁 17:30~20:30 예약 마감", closed={"PIZZA_HILL": ["17:30", "20:30"]})]),
}
REST = {"room_rest", "ROOM_REST", "room_bath", "room_nap", "idle", "library"}


def acts(r): return [x for x in r["log"] if x["act"] not in ("move",)]
def seq(r): return [(x["t"], x["act"], x["loc"]) for x in r["log"]]


def evs(x):
    return " · ".join(("후기에서 확인 " + ",".join(e["fact_ids"][:3])) if e["type"] == "후기에서 확인" else ("프로파일 기반 추론" + (" " + ",".join(e.get("traits") or []) if e.get("traits") else "")) for e in x["evidence"])


def md_day(title, r):
    out = [f"\n#### {title} — 행동 {r['summary']['n_actions']} · LLM 행동 {r['summary'].get('llm_actions', 0)} · 후기 근거 행동 {r['summary']['review_evidence_actions']}\n",
           "| 시각 | 행동 | 출처 | 설명 | 근거 |", "|---|---|---|---|---|"]
    out += [f"| {x['t']}–{x['e']} | {x['label']} | {x['source']} | {x['why']} | {evs(x)} |" for x in acts(r)]
    return out


def repeats(r):
    """같은 시설 재이용 · 쉬는 활동 연속을 '타당(이유 있음)'과 '기계적 반복'으로 구분."""
    xs = [x for x in r["log"] if x["act"] not in ("move", "wait")]
    out = []
    seen = {}
    for i, x in enumerate(xs):
        base = str(x["act"]).split(":")[0]
        key = AD.LUNCH_ENGINE.get(base) or AD.SAME_FACILITY.get(base) or base
        if x["domain"] in ("식사", "카페", "바", "웰니스", "산책", "문화", "행사") and key in seen and base not in ("BREAKFAST_BUFFET",):
            note = (x.get("internal") or {}).get("note") or ""
            ok = "후기 근거 재방문" in note
            out.append(dict(kind="같은 시설 재이용", t=x["t"], what=x["label"], first=seen[key], verdict="타당(후기 근거 재방문)" if ok else "기계적 반복(이유 없음)", basis=note or x["why"]))
        seen.setdefault(key, x["t"])
        if i and base in REST and str(xs[i - 1]["act"]).split(":")[0] in REST:
            prev = xs[i - 1]
            before = xs[i - 2] if i >= 2 else None
            hard = before is not None and AD.EFFORT.get(str(before["act"]).split(":")[0], AD.EFFORT_DOMAIN.get(before["domain"], 0.4)) >= 0.6
            rev = any(e["type"] == "후기에서 확인" for e in x["evidence"])
            reasons = [r for r, ok in (("앞서 몸을 많이 씀(" + (before["label"] if before else "") + ")", hard), ("이 쉬는 방식이 후기에서 확인됨", rev),
                                       ("장소 · 방식이 다름(" + prev["label"] + " → " + x["label"] + ")", prev["loc"] != x["loc"]),
                                       ("LLM 근거: " + str((x.get("internal") or {}).get("profile_basis")), bool((x.get("internal") or {}).get("profile_basis")))) if ok]
            mech = prev["loc"] == x["loc"] and not rev and not hard
            out.append(dict(kind="쉬는 활동 연속", t=x["t"], what=f"{prev['label']} → {x['label']}", verdict="기계적 반복(같은 자리 · 새 이유 없음)" if mech else "타당(" + "; ".join(reasons) + ")", basis=x["why"]))
    return out


def coverage(inp):
    rows = {}
    for p in AD.DEMO:
        a = AD.Agent(p, *inp, AD.scenario("cov"))
        _, cite, cov = PC.context(a)
        rows[p] = cov
    return rows


def md_cov(cov):
    keys = ["venue_experiences", "walkerhill_visit_events", "menu_preferences", "other_stay_patterns", "judgment_patterns", "behavior_hypotheses", "counterexamples", "other_review_facts"]
    ko = dict(venue_experiences="업장 · 시설 경험", walkerhill_visit_events="워커힐 방문 사건", menu_preferences="메뉴 취향", other_stay_patterns="다른 숙박 시설 이용", judgment_patterns="판단 패턴(분석)",
              behavior_hypotheses="행동 가설(검증 전)", counterexamples="반례", other_review_facts="기타 후기 사실")
    out = ["| 고객 | " + " | ".join(ko[k] + " 전달/보유" for k in keys) + " | 인용 가능 사실 / 전체 사실 | 다른 숙박 원자료 |", "|---|" + "---|" * (len(keys) + 2)]
    for p, c in cov.items():
        out.append(f"| {p} | " + " | ".join(f"{c['sent'].get(k, 0)}/{c['held'].get(k, 0)}" for k in keys) + f" | {c['citable_fact_ids']}/{c['total_facts']} | 0/{c['held'].get('other_hotel_events(팀 분석 원자료)', 0)} (요약 패턴으로 대체) |")
    return out


def llm_log(r, n=40):
    tr = [x for x in r["trace"] if x.get("backend") == "llm"]
    out = ["| 시각 | LLM 욕구 해석 | 제안 | 고려 대안 | 이유 · 프로파일 근거 | 인용 사실 | 검증 | 실제 행동 |", "|---|---|---|---|---|---|---|---|"]
    for x in tr[:n]:
        out.append(f"| {x['t']} | {x.get('need') or ''} | {x['option']} ({x.get('keep_or_change')}) | {', '.join(x.get('alternatives') or [])} | {x.get('why') or ''} · {x.get('profile_basis') or ''} | "
                   f"{','.join(x.get('fact_ids') or [])}{(' (제거: ' + ','.join(x['dropped_fact_ids']) + ')') if x.get('dropped_fact_ids') else ''} | {'채택' if x['accepted'] else '거절 — ' + str(x['reject_reason'])} | {x.get('result') or '-'} ({x.get('result_source') or '-'}) |")
    return out


def diff_rule_llm(rule, llm):
    ra = [x for x in acts(rule) if x["act"] not in NONACT]; la = [x for x in acts(llm) if x["act"] not in NONACT]
    rs, ls = {x["act"] for x in ra}, {x["act"] for x in la}
    return dict(only_rule=sorted(rs - ls), only_llm=sorted(ls - rs), same=sorted(rs & ls), rule_review_ev=rule["summary"]["review_evidence_actions"], llm_review_ev=llm["summary"]["review_evidence_actions"],
                llm_actions=llm["summary"].get("llm_actions", 0), n_rule=len(ra), n_llm=len(la),
                llm_distinct_facts=len({f for x in la for e in x["evidence"] if e["type"] == "후기에서 확인" for f in e["fact_ids"]}),
                rule_distinct_facts=len({f for x in ra for e in x["evidence"] if e["type"] == "후기에서 확인" for f in e["fact_ids"]}))


def env_block():
    c = LL.cfg()
    return dict(run_on="mac" if platform.system() == "Darwin" else ("cloud(linux)" if platform.system() == "Linux" else platform.system().lower()), python=platform.python_version(),
                llm_enabled=c["enabled"], key_present=c["has_key"], mock=c["mock"], replay=c["replay"], model=c["model"], max_calls=c["max_calls"], max_cost_usd=c["max_cost"], cache=bool(c["cache"]),
                at=time.strftime("%Y-%m-%d %H:%M:%S"), engine_version=AD.VERSION)


def interventions(ids, base_sc_fn, inp, planner):
    res = {}
    base = AD.run_many(ids, base_sc_fn("base"), inp)["personas"]
    for k, v in IV.items():
        chg = AD.run_many(ids, base_sc_fn(k, changes=v["changes"]), inp)["personas"]
        res[k] = dict(compare=AD.compare(base, chg, v["at"], event=v["event"]), logs={p: chg[p]["log"] for p in ids})
    return base, res


def md_iv(res):
    out = []
    for k, v in res.items():
        out.append(f"\n### {k}\n\n| 고객 | 분류 | 이유(고객 기준) | 대안 |\n|---|---|---|---|")
        for p, c in v["compare"].items():
            alt = c.get("alternative")
            out.append(f"| {p} | {c['cls']} | {c.get('reason') or ''} | {(alt['t'] + ' ' + alt['label'] + ' — ' + alt['why']) if alt else ''} |")
    return out


def usage_md(u, led, env):
    t = u["total"]
    return [f"\n## LLM 사용량 · 비용\n\n| 항목 | 값 |\n|---|---|\n| 실행 환경 | {env['run_on']} |\n| 실행 방식 | {u['mode']} |\n| 모델 | {u['model']} ({u['api']}) · 단가 {u['prices']} |\n"
            f"| 실제 API 호출 · 성공 | {t['real_api_calls']} · {t['real_api_ok']} |\n| 기록 전체(시도 · 성공 · 실패 · 재시도 · 캐시 재생 · mock) | {t['calls']} · {t['ok']} · {t['failed']} · {t['retries']} · {t['cache_hits']} · {t['mock_calls']} |\n"
            f"| 입력 · 캐시 입력 · 출력(추론 포함) · 추론 · 전체 토큰 | {t['input_tokens']} · {t['cached_tokens']} · {t['output_tokens']} · {t['reasoning_tokens']} · {t['total_tokens']} |\n| 추정 비용 | ${t['cost_usd']:.6f} |\n"
            f"| 소요 | {u['wall_sec']}초(API 대기 합 {t['ms']}ms) |\n| 제안 반영 | 계획 {u['decisions']['llm_plans']} · 의도 {u['decisions']['intents']} · 채택 {u['decisions']['accepted']} · 거절 {u['decisions']['rejected']} · 규칙 폴백 {u['decisions']['fallback_steps']} |\n"
            f"| 한도 중단 | {u['stopped'] or '-'} |\n| 호출 0회 이유 | {u['zero_call_reason'] or '-'} |\n| 오류 | {u['errors'] or '-'} |\n| 같은 출력 폴더 누적 실호출 | {led['calls']}회 · ${led['cost_usd']:.6f} (한도 {env['max_calls']}회 · ${env['max_cost_usd']}) |\n",
            "고객별:\n\n| 고객 | 기록 호출 | 입력 | 캐시 입력 | 출력 | 전체 | 비용 USD | ms |\n|---|---:|---:|---:|---:|---:|---:|---:|"] + \
           [f"| {p} | {v['calls']} | {v['input_tokens']} | {v['cached_tokens']} | {v['output_tokens']} | {v['total_tokens']} | {v['cost_usd']:.6f} | {v['ms']} |" for p, v in u["per_persona"].items()] + \
           ["\n호출별(앞 30):\n\n| # | 고객 | 성공 | 캐시 | 입력 | 출력 | 비용 USD | ms | 오류 |\n|---:|---|---|---|---:|---:|---:|---:|---|"] + \
           [f"| {i + 1} | {c['persona']} | {c['ok']} | {c.get('cache_hit')} | {c.get('input_tokens', 0)} | {c.get('output_tokens', 0)} | {(c.get('cost_usd') or 0):.6f} | {c.get('ms', 0)} | {c.get('error') or ''} |" for i, c in enumerate(u["calls"][:30])]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--mode", required=True, choices=["check", "compare3", "all", "rules"]); ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--allow-expand", action="store_true", help="3차(all) — 사용자가 호출 한도 확대를 승인한 뒤에만")
    ap.add_argument("--ledger", default=None, help="실호출 누적 원장 경로(기본 OUT/llm_ledger.json) — 결과 폴더를 나눠도 한도는 합산")
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.mode == "all" and not a.allow_expand:
        sys.exit("3차(all)는 2차 결과 검토와 사용자 승인 뒤 --allow-expand 로만 실행합니다(호출 · 비용 확대 방지).")
    ledger = Path(a.ledger) if a.ledger else out / "llm_ledger.json"   # 실제 API 호출 누적(키 · 원문 없음) — 같은 폴더에서 1차 · 2차 · 3차를 돌리면 한도를 합산
    led = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else dict(runs=[], calls=0, cost_usd=0.0)
    LL.USAGE.prior = dict(calls=led["calls"], cost_usd=led["cost_usd"])
    env = env_block(); inp = AD.load_inputs(); S = a.seed
    res = dict(env=env, mode=a.mode, version=AD.VERSION, seed=S)
    md = [f"# CL-1024-19 실행 결과 — {a.mode}\n", f"- 실행 환경 {env['run_on']} · 엔진 {env['engine_version']} · 모델 {env['model']} · LLM 켬 {env['llm_enabled']} · 키 {'있음(값 미출력)' if env['key_present'] else '없음'} · mock {env['mock']} · 한도 {env['max_calls']}회 / ${env['max_cost_usd']} · 시드 {S} · {env['at']}\n"]
    sc = lambda name, planner, **kw: AD.scenario(name, seed=S, planner=planner, **kw)
    LL.USAGE.reset(a.mode)
    if a.mode == "check":
        ag = AD.Agent("A07", *inp, sc("check", "llm")); w = AD.World(sc("check", "llm"))
        ag.t = AD.hm("15:30"); ag.loc = ag.room
        ok = LL.plan(ag, w, ag.t) if (env["llm_enabled"] and (env["key_present"] or env["mock"])) else False
        res["check"] = dict(ok=ok, intents=ag.intents, need=ag.llm_ctx.get("need"), interest=ag.llm_ctx.get("interest"), coverage=getattr(ag, "llm_cov", None))
        md.append(f"## 1차 연결 검사\n\n- 결과: {'성공' if ok else '실패'}\n- LLM 욕구 해석: {ag.llm_ctx.get('need')}\n- 관심: {ag.llm_ctx.get('interest')}\n- 의도: " + "; ".join(f"{i['option']}({i['keep_or_change']}) — {i['why']} [근거: {i.get('profile_basis')} · {','.join(i['fact_ids'])}]" for i in ag.intents))
    if a.mode in ("compare3", "all", "rules"):
        cov = coverage(inp); res["coverage"] = cov
        md += ["\n## 11명 프로파일 입력 커버리지(LLM 호출 직전 실제 전달 / 보유)\n"] + md_cov(cov)
    if a.mode == "rules":
        ind = {p: AD.run_one(p, sc("base", "rules"), inp) for p in AD.DEMO}
        ind2 = {p: AD.run_one(p, sc("base", "rules"), inp) for p in AD.DEMO}
        con = AD.run_many(AD.DEMO, sc("base", "rules"), inp)
        base, ivr = interventions(AD.DEMO, lambda n, **kw: sc(n, "rules", **kw), inp, "rules")
        res.update(individual=ind, concurrent=dict(personas=con["personas"], interaction=con.get("interaction")), interventions=ivr,
                   same_ind_con={p: seq(ind[p]) == seq(con["personas"][p]) for p in AD.DEMO}, same_repeat={p: seq(ind[p]) == seq(ind2[p]) for p in AD.DEMO},
                   repeats={p: repeats(ind[p]) for p in AD.DEMO})
        md.append(f"\n- 개별 = 동시 {sum(res['same_ind_con'].values())}/11 · 같은 입력 재실행 동일 {sum(res['same_repeat'].values())}/11")
        for p in AD.DEMO:
            md += md_day(p, ind[p])
        md += ["\n## 운영자 개입(규칙 기반)"] + md_iv(ivr)
        md += ["\n## 재방문 · 연속 휴식 구분\n", "| 고객 | 종류 | 시각 | 내용 | 판정 | 근거 |", "|---|---|---|---|---|---|"] + \
              [f"| {p} | {x['kind']} | {x['t']} | {x['what']} | {x['verdict']} | {x['basis']} |" for p, xs in res["repeats"].items() for x in xs]
    if a.mode in ("compare3", "all"):
        ids = THREE if a.mode == "compare3" else AD.DEMO
        rule = {p: AD.run_one(p, sc("base", "rules"), inp) for p in ids}
        llm = {p: AD.run_one(p, sc("base", "llm"), inp) for p in ids}
        res.update(rule_only=rule, llm_assisted=llm, diff={p: diff_rule_llm(rule[p], llm[p]) for p in ids}, repeats_llm={p: repeats(llm[p]) for p in ids}, repeats_rule={p: repeats(rule[p]) for p in ids})
        md += ["\n## 규칙 기반 vs LLM 보조(같은 방문 조건 · 시드)\n", "| 고객 | 행동 수 규칙/LLM | LLM 결정 행동 | 후기 근거 행동 규칙/LLM | 서로 다른 인용 사실 규칙/LLM | LLM에만 | 규칙에만 |", "|---|---|---|---|---|---|---|"] + \
              [f"| {p} | {d['n_rule']}/{d['n_llm']} | {d['llm_actions']} | {d['rule_review_ev']}/{d['llm_review_ev']} | {d['rule_distinct_facts']}/{d['llm_distinct_facts']} | {', '.join(d['only_llm'])} | {', '.join(d['only_rule'])} |" for p, d in res["diff"].items()]
        for p in ids:
            md.append(f"\n### {p} — 방문 조건: {rule[p]['visit']['why']}")
            md += md_day("rule_only", rule[p]) + md_day("llm_assisted", llm[p])
            md += ["\n#### LLM 제안 → 검증 → 채택 · 거절\n"] + llm_log(llm[p])
            rp = res["repeats_llm"][p]
            if rp:
                md += ["\n재방문 · 연속 휴식(LLM): " + "; ".join(f"{x['t']} {x['what']} — {x['verdict']}" for x in rp)]
        if a.mode == "all":
            con = AD.run_many(AD.DEMO, sc("base", "llm"), inp)   # 같은 입력 → 캐시 재사용
            res["same_ind_con"] = {p: seq(llm[p]) == seq(con["personas"][p]) for p in AD.DEMO}
            base, ivr = interventions(AD.DEMO, lambda n, **kw: sc(n, "llm", **kw), inp, "llm")
            res["interventions"] = ivr
            md.append(f"\n- LLM 개별 = 동시 {sum(res['same_ind_con'].values())}/11(캐시 재생으로 같은 판단)")
            md += ["\n## 운영자 개입(LLM 보조)"] + md_iv(ivr)
    u = LL.USAGE.summary(); res["llm_usage"] = u; t = u["total"]
    led["runs"].append(dict(mode=a.mode, at=env["at"], run_on=env["run_on"], model=env["model"], real_api_calls=t["real_api_calls"], real_api_ok=t["real_api_ok"], cost_usd=t["cost_usd"]))
    led["calls"] += t["real_api_calls"]; led["cost_usd"] = round(led["cost_usd"] + t["cost_usd"], 6)
    ledger.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
    md += usage_md(u, led, env)
    (out / f"cl19_{a.mode}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    for fn in (f"llm_usage_{a.mode}.json", "llm_usage.json"):
        (out / fn).write_text(json.dumps(dict(env=env, usage=u, ledger=led), ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"cl19_{a.mode}_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(dict(mode=a.mode, run_on=env["run_on"], llm=u["mode"], real_api_calls=t["real_api_calls"], real_api_ok=t["real_api_ok"], mock_calls=t["mock_calls"], cost_usd=t["cost_usd"],
                          ledger_calls=led["calls"], stopped=u["stopped"], zero_call_reason=u["zero_call_reason"], out=str(out)), ensure_ascii=False))


if __name__ == "__main__":
    main()
