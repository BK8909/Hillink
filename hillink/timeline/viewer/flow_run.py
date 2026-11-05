"""고객 흐름 실행기 (CL-1024-22R) — /api/flow 가 부르는 별도 프로세스.

기존 '고객 흐름'(agent.js) 화면의 실제 행동 엔진을 autonomy_v1(프로파일 기반 하루 계획 · 선택 · 상태 · 근거 · 운영 개입 반응)로 바꾼다.
화면 계약(runs · plans · visits)은 그대로 두고, 이 어댑터가 새 엔진 결과를 그 모양으로 옮긴다.

변환 기준(합성 금지)
· 하루의 모든 장면 = autonomy_v1 실행 기록(log) 그대로. 화면이 따로 행동을 만들지 않는다.
· 핵심 턴(아침 · 행사 · 저녁) = 그 기록 가운데 정량 엔진 결정(아침: turn_candidate.decide_turn · 행사/저녁: operator_world_v1.decide_at).
  선택 · 비교 후보 · 점수 · 항별 값은 그 결정이 돌려준 값이고, 공통 · 후기 · 가정 몫은 turn_view.split_reason 규칙으로 나눈 값(agent_day.turn_raw).
  점수는 저녁 · 행사에서 엔진이 실제로 비교한 '내다보기 포함 총점(total)', 아침은 턴 점수.
· 지출 = 공통 장부(ledger) 값. 상품 가격은 엔진 월드 값을 그대로 보이고, 장부가 다르면(예: 와인페어 투숙객 무료) 장부 쪽을 지불액으로.
· 업장 단위 엔진이라 메뉴 단위 운영 조건 중 대표 상품에 해당하는 것만 옮긴다(levers_applied). 나머지는 levers_not_applied 로 돌려준다.

입력: {"personas":[...], "mode":"one|many", "visit_override":{pid:{stay,building,phase,party_size,club?}}?, "event":bool,
       "intervention":"none|wine_fair_1300|pizzahill_full|pool_check", "product_levers":{...}, "observe":"day|...", "seed":int}
출력: {"engine", "mode", "visits", "runs", "plans", "stories"?, "intervention", "notices", "levers_applied", "levers_not_applied", "inputs_sha"}
"""
import copy, hashlib, json, re, sys
from datetime import date as _date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "experiments" / "persona_live"))
sys.path.insert(0, str(HERE))
from operator_choice.autonomy_v1 import agent_day as AD  # noqa: E402
from operator_choice.operator_world_v1_1 import turn_view as TV, turn_candidate as TC  # noqa: E402
import autonomy_run as AR  # noqa: E402
import build_persona_library as BPL  # noqa: E402  (문장 단위 비표시 규칙 재사용 · main 가드 있음)

ENGINE = "autonomy_v1"
TURNS = ("breakfast", "event", "dinner")
LEVER_MAP = {   # 메뉴 상품 → 업장 단위 엔진 상품(대표 상품만 · 월드 price_note 근거)
    "PH_COUPLE_SET": ("PIZZA_HILL", 2, "피자힐 저녁 = 커플 세트 ÷ 2(월드 가격 근거)"),
    "RS_CLUB_SANDWICH": ("ROOM_MEAL", 1, "객실 식사 = 클럽 샌드위치 기준(월드 가격 근거)"),
    "WINE_FAIR": ("WINE_FAIR", 1, "와인페어 입장권"),
}
FORBIDDEN = AR.FORBIDDEN
# CL-1025-32 — 일반 API 요지 최소화: 이 결정에 실제로 인용한 사실만 요지를 싣고, 아동 · 건강 세부가 있는 요지는 사실 ID + 일반 설명으로 바꾼다(원천 사실 · 엔진 · 점수 불변)
DISPLAY_SENSITIVE = re.compile(BPL.SENSITIVE.pattern.replace("아이", "아이(?!스)") + "|컨디션")
MASKED = "아동 · 건강 관련 세부가 있어 요지를 표시하지 않음(사실 ID 로만 확인)"


def hm(t):
    return AD.hm(t)


def map_levers(pl):
    applied, skipped, levers, bf = [], [], {}, None
    for pid, lv in (pl or {}).items():
        if not isinstance(lv, dict):
            continue
        if pid == "BREAKFAST_BUFFET":
            if lv.get("in_package") is not None:
                bf = bool(lv["in_package"]); applied.append(dict(product=pid, to="breakfast_in_package", value=bf))
            if lv.get("price"):
                skipped.append(dict(product=pid, key="price", why="조식 가격은 새 엔진의 아침 판단이 '객실 포함' 가정으로만 다룸"))
            continue
        m = LEVER_MAP.get(pid)
        if not m:
            skipped.extend(dict(product=pid, key=k, why="업장 단위 새 엔진 — 이 메뉴는 대표 상품이 아님(운영 실험 탭에서 메뉴 단위 계산)") for k in lv)
            continue
        oid, n, basis = m
        ch = levers.setdefault(oid, {})
        for k, v in lv.items():
            if k == "price" and v:
                ch["price_pp_krw"] = int(round(v / n)); applied.append(dict(product=pid, to=f"{oid}.price_pp_krw", value=ch["price_pp_krw"], basis=basis))
            elif k == "guest_discount" and v is not None:
                ch["guest_discount_krw"] = int(round(v / n)); applied.append(dict(product=pid, to=f"{oid}.guest_discount_krw", value=ch["guest_discount_krw"], basis=basis))
            elif k == "in_package":
                ch["in_package"] = bool(v); applied.append(dict(product=pid, to=f"{oid}.in_package", value=bool(v), basis=basis))
            elif k == "available" and v is False:
                ch["available"] = False; applied.append(dict(product=pid, to=f"{oid}.available", value=False, basis=basis))
            else:
                skipped.append(dict(product=pid, key=k, why="새 엔진에 대응 항목 없음"))
        if not ch:
            levers.pop(oid, None)
    return levers, bf, applied, skipped


def scenario(name, q, levers, bf, iv=None):
    lv = {"WINE_FAIR": {"available": bool(q.get("event"))}}
    for k, v in (levers or {}).items():
        lv[k] = dict(lv.get(k) or {}, **v)
    kw = dict(seed=q["seed"], levers=lv, observe=q.get("observe") or "day")
    if q.get("visit_date"):
        # Visit runs supply each calendar day explicitly; standalone daily runs
        # retain the native scenario default.
        kw["date"] = _date.fromisoformat(q["visit_date"]).isoformat()
        kw["day_label"] = q["visit_date"]
    if q.get("visit_override"):
        kw["visit_override"] = q["visit_override"]
    if q.get("visit_resolution"):
        kw["visit_resolution"] = q["visit_resolution"]
    if q.get("scenario_snapshot"):
        kw["scenario_snapshot"] = q["scenario_snapshot"]
    if q.get('catalog_policy'):
        kw.update(catalog_policy=q['catalog_policy'],catalog_options=q.get('catalog_options') or {})
    if q.get('hybrid_policy'): kw['hybrid_policy']=q['hybrid_policy']
    if q.get('breakfast_policy'): kw['breakfast_policy']=q['breakfast_policy']
    if q.get("visit_state"):
        kw["visit_state"] = q["visit_state"]
    if bf is not None:
        kw["breakfast_in_package"] = bf
    if iv and iv != "none":
        kw["changes"] = AR.INTERVENTIONS[iv]["changes"]
    result = AD.scenario(name, **kw)
    if q.get("environment"):
        from operator_choice.autonomy_v1 import operational_environment as OE
        result["operational_environment"] = OE.validate(q["environment"])
    return result


def turn_of(log):
    """기록 → {turn: 기록}. 아침 = 아침 턴 판단 · 행사 = 와인페어 참여 · 저녁 = 16:30 뒤 첫 정량 식사 판단."""
    out = {}
    for x in log:
        tr = (x.get("internal") or {}).get("turn_raw")
        if not tr:
            continue
        if tr["world"] == "breakfast" and "breakfast" not in out:
            out["breakfast"] = x
        elif x["act"] == "WINE_FAIR" and "event" not in out:
            out["event"] = x
        elif x["domain"] == "식사" and hm(x["t"]) >= 16 * 60 + 30 and "dinner" not in out:
            out["dinner"] = x
    return out


def offers_at(sc, x, N):
    tr = x["internal"]["turn_raw"]
    if "runtime_offers" in tr:
        return {o["id"]: o for o in tr["runtime_offers"]}
    if tr["world"] == "breakfast":
        w, _ = TC.turn_world("breakfast", "historical", N, product_levers=x["internal"].get("breakfast_levers") or None)
    else:
        w = AD.World(sc).engine_world(hm(x["t"]))
    out = {o["id"]: o for o in w["offers"]}
    if "ROOM_MEAL" in out and AD.DELIVERY_ID not in out:   # actor-specific external delivery: display copy, amount unknown
        d = copy.deepcopy(out["ROOM_MEAL"])
        d.update(id=AD.DELIVERY_ID, label="외부 배달 · 객실에서 먹기", venue=AD.DELIVERY_ID, price_pp_krw=None, external_spend=dict(amount_krw=None, status="EXTERNAL_AMOUNT_UNKNOWN", hotel_revenue_krw=0))
        out[AD.DELIVERY_ID] = d
    return out


def option(o, val, B, stay, feasible=True, blocked=()):
    if o.get("price_pp_krw") is None:
        # Native legacy formatter requires arithmetic; no sentinel escapes here.
        op = TV._option(dict(o, price_pp_krw=0), val, B or "VISTA", feasible, blocked)
        op["price"].update(pp_krw=None, paid_krw=None, list_krw=None,
                           basis="EXTERNAL_DELIVERY_AMOUNT_UNKNOWN_NOT_HOTEL_REVENUE" if o.get("external_spend") else "VENUE_ONLY_AMOUNT_UNKNOWN",
                           source="EXTERNAL_NOT_HOTEL" if o.get("external_spend") else "NO_APPROVED_SKU", menu_as_of="UNKNOWN")
    else:
        op = TV._option(o, val, B or "VISTA", feasible, blocked)
    if o["id"] == "ROOM_REST" and not stay:   # 비투숙에게 엔진의 기준 선택(쉬기)은 객실이 아님
        op.update(product_label="따로 움직이지 않고 쉬기", venue_label="현장에서 쉬기", map_loc="AG_GARDEN")
    if o.get("sku_contract"):
        op["sku_contract"] = o["sku_contract"]
        op["price"]["price_status"] = o["sku_contract"]["price_status"]
    return op


def customer(pid, x, r, sc, P):
    v = r["visit"]; B = v.get("building") if v.get("stay") else None; N = v.get("party_size") or 2
    tr = x["internal"]["turn_raw"]
    by = offers_at(sc, x, N)
    o = by[tr["chosen"]]
    val = tr["total"] if tr["total"] is not None else tr["score"]
    ch = option(o, val, B, v.get("stay"))
    ch["map_loc"] = x["loc"]
    pr = dict(ch["price"])
    c = x.get("charge") or {}
    if c.get("status") in ("무료", "포함"):
        pr.update(paid_krw=0, in_package=c["status"] == "포함" or pr.get("in_package"))
    elif c.get("status") == "유료" and c.get("krw") is not None:
        pr["paid_krw"] = int(round(c["krw"] / max(1, N)))
    elif c.get("status") == "가격 미정":
        pr["paid_krw"] = None
    pr.update(ledger_status=c.get("status"), ledger_basis=c.get("basis"), price_kind=c.get("price_kind"), extras=c.get("extras"), party_note=c.get("party_note"))
    ch["price"] = pr
    others = []
    for q in tr["rejected"]:
        o2 = by.get(q["offer"])
        if not o2 or q["offer"] == tr["chosen"]:
            continue
        qv = q["total"] if q.get("total") is not None else q.get("score")
        others.append(option(o2, qv, B, v.get("stay"), q["feasible"] and qv is not None, q.get("blocked") or []))
    others.sort(key=lambda z: (z["score"] is None, -(z["score"] or 0)))
    feas = [z for z in others if z["feasible"] and z["score"] is not None]
    runner = feas[0] if feas else None
    other_v = next((z for z in feas if z["venue_id"] != ch["venue_id"]), None)
    reasons = list(tr["terms"])
    if tr["total"] is not None and tr["score"] is not None and abs(tr["total"] - tr["score"]) > 1e-6:   # 엔진이 실제로 비교한 총점 = 지금 점수 + 다음 일정 내다보기(decide_at) — 합계가 선택 점수와 맞도록 그 몫을 한 항으로
        nx = dict(x["internal"].get("next_plan") or {})
        if nx.get("offer") == "ROOM_REST" and not v.get("stay"):
            nx["label"] = "따로 움직이지 않고 쉬기"
        lv = round(tr["total"] - tr["score"], 4)
        reasons.append(dict(factor=f"이어지는 다음 일정(내다보기){' — ' + nx['label'] if nx.get('label') else ''}", value=lv, facet=None, fact_ids=[],
                            note="정량 엔진 decide_at 의 내다보기 몫(다음 계획의 점수)", parts=dict(common=lv, review=0.0, assumption=0.0), cls="common"))
    totals = {k: round(sum(t["parts"].get(k, 0.0) for t in reasons), 4) for k in ("common", "review", "assumption", "transfer", "out_of_scope")}
    totals = {k: v for k, v in totals.items() if k in ("common", "review", "assumption") or abs(v) > 1e-9}   # CL-1025-26 — 맥락 이전 · 범위 밖 몫은 있을 때만
    traits = P[pid]["traits"]
    cited = [f for t in reasons for f in t["fact_ids"]]
    evidence, ev_status = TV.display_evidence(traits, cited)
    used = set(cited) | {f for e in x["evidence"] for f in (e.get("fact_ids") or [])}   # CL-1025-32 — 결정에 쓰지 않은 성향 근거 요지는 응답에서 뺌
    evidence = {k: v for k, v in evidence.items() if k in used}; ev_status = {k: v for k, v in ev_status.items() if k in used}
    for k, v in list(evidence.items()):
        if DISPLAY_SENSITIVE.search(v or ""):
            evidence[k], ev_status[k] = MASKED, "masked_sensitive"
    oos = {f for t in reasons for f, k in (t.get("provenance") or {}).items() if k == "OUT_OF_SCOPE"} | {f for f in evidence if AD.OUT_OF_SCOPE.search(evidence.get(f) or "")}
    evidence = {k: v for k, v in evidence.items() if k not in oos}; ev_status = {k: v for k, v in ev_status.items() if k not in oos}   # 범위 밖 사실은 근거 요지로 내보내지 않음(충돌 항목에 ID 만)
    pdv = [t["product_direct_visits"] for t in reasons if "product_direct_visits" in t]
    return dict(persona_id=pid, persona=dict(label=P[pid]["label"], companion=P[pid].get("companion"), bars=TV.persona_bars(traits)),
                choice=ch, runner_up=None if not runner else dict(runner, margin=round(val - runner["score"], 4)),
                best_other_venue=None if not other_v else dict(other_v, margin=round(val - other_v["score"], 4)),
                not_chosen=others, reasons=reasons, reason_totals=totals, evidence=evidence, evidence_status=ev_status,
                state_after=dict(chained=False), decided_at=x["t"], why=x["why"], engine_evidence=x["evidence"],
                avoid=[e for e in x["evidence"] if e.get("type") == "후기 회피 근거"], uncertain=[e for e in x["evidence"] if e.get("type") == "불확실"],
                direct_review_fact_ids=[f for e in x["evidence"] if e.get("type") == "후기에서 확인" for f in e.get("fact_ids") or []],
                product_direct_visits=(min(pdv) if pdv else None),
                score_provenance_conflicts=[t["score_provenance_conflict"] for t in reasons if t.get("score_provenance_conflict")],
                score_basis="내다보기 포함 총점(total)" if tr["total"] is not None else "턴 점수",
                decision_engine=x["internal"].get("engine"))


def runs_of(res, sc, P, mode, q):
    T = {pid: turn_of(r["log"]) for pid, r in res.items()}
    runs = []
    for t in TURNS:
        cs = [customer(pid, T[pid][t], res[pid], sc, P) for pid in res if t in T[pid]]
        if not cs:
            continue
        v0 = res[cs[0]["persona_id"]]["visit"]
        B = v0.get("building") or "VISTA"
        conditions = dict(turn=t, stay=bool(v0.get("stay")), building=B, party_size=v0.get("party_size"), phase=v0.get("phase"),
                          event=bool(q.get("event")), pricing="operator_world_v1", product_levers=q.get("product_levers") or {}, mixed=mode == "many")
        if v0.get("package_context"):
            conditions["package_id"] = v0["package_context"].get("id")
        runs.append(dict(turn=t, time=min((c["decided_at"] for c in cs), key=hm), engine=ENGINE,
                         conditions=conditions,
                         building=dict(id=B, label=TV.BUILDING_LABEL.get(B, B)), excluded=[], customers=cs))
    return runs


def compare_runs(before, after):
    B = {r["turn"]: r for r in before}
    for R in after:
        b = B.get(R["turn"]) or dict(R, customers=[])
        cmp = TV.turn_compare(b, R)
        have = {c["persona_id"] for c in cmp["customers"]}
        for c in R["customers"]:   # 개입 전에는 이 결정이 없던 고객(예: 행사 없던 날 → 와인페어 참여)
            if c["persona_id"] not in have:
                cmp["customers"].append(dict(persona_id=c["persona_id"], status="changed",
                                             before=dict(product_id="NONE", product_label="개입 전에는 이 결정 없음", venue_id="NONE", map_loc=None, score=None),
                                             after={k: c["choice"][k] for k in ("product_id", "product_label", "venue_id", "map_loc", "score")},
                                             venue_changed=True, score_delta=0.0, top_drivers=[], kept_reason=None))
                cmp["summary"]["changed"] += 1
        R["compare"] = cmp
        R["_before"] = b
    return after


ACT_TURN = {"breakfast": "turn_breakfast", "event": "turn_event", "dinner": "turn_dinner"}


def plan_of(pid, r, T, new_keys):
    scenes, prev_move = [], 0
    turn_ids = {id(x): t for t, x in T.items()}
    for x in r["log"]:
        if x["act"] == "move":
            prev_move = hm(x["e"]) - hm(x["t"]); continue
        if x["act"] == "wait" and hm(x["e"]) - hm(x["t"]) < 10:
            continue
        t = turn_ids.get(id(x))
        evs = x.get("evidence") or []
        facts = [f for e in evs if e.get("type") == "후기에서 확인" for f in (e.get("fact_ids") or [])]
        traits = sorted({k for e in evs if e.get("type") == "프로파일 기반 추론" for k in (e.get("traits") or [])})
        ch = x.get("charge") or {}
        scenes.append(dict(t0=hm(x["t"]), t1=hm(x["e"]), loc=x["loc"], act=ACT_TURN[t] if t else x["act"], label=x["label"], why=x["why"],
                           layer="engine" if t else ("review" if facts else "generated"), turn=t, travel=prev_move,
                           kind="rest" if x["domain"] in ("객실 휴식", "휴식", "대기") else "activity",
                           consume=ch.get("status") in ("유료", "포함", "가격 미정") or x["domain"] == "식사",
                           meal_intent=x.get('meal_intent'),
                           meal=x.get('meal_slot') if (x.get('internal') or {}).get('autonomous_decision') else ("lunch" if str(x["act"]).startswith("lunch_") else ("dinner" if t == "dinner" else "breakfast" if t == "breakfast" else None)),
                           cond_dep=(x["act"], x["loc"]) in new_keys, source=x["source"], domain=x["domain"],
                           basis=dict(facts=facts, traits=traits, evidence=evs, charge=ch or None, choice=x.get("choice"),
                                      menu_decision=(x.get("internal") or {}).get("hotel_product_decision"),
                                      autonomous_decision=(x.get('internal') or {}).get('autonomous_decision'),
                                      continued_autonomous_decisions=(x.get('internal') or {}).get('continued_autonomous_decisions',[]),
                                      review=(x.get("internal") or {}).get("decision_trace"), selection_id=(x.get("internal") or {}).get("selection_id"), engine=(x.get("internal") or {}).get("engine"), decision=bool((x.get("internal") or {}).get("turn_raw")))))
        prev_move = 0
    result = dict(status="ok", scenes=scenes, backend=ENGINE, requested=ENGINE, fallback_reason=None, summary=r.get("summary"),
                  trace=dict(engine=ENGINE, version=AD.VERSION, planner="autonomy_v1.agent_day", llm_calls=0, profile_loaded=True,
                             personalization="product_registry", backend_requested=ENGINE, backend_used=ENGINE, planner_backend_fallback_used=False))
    if r.get('native_review_attempts'):
        result['native_review_attempts']=r['native_review_attempts']
        calls=[x.get('call') or {} for x in r['native_review_attempts']]
        result['trace'].update(llm_calls=sum(bool(c.get('network_attempted')) for c in calls),
            llm_replays=sum(bool(c.get('cache_hit')) for c in calls),
            llm_errors=sum(bool(c.get('error')) for c in calls),planner_backend='SELECTIVE_V12Z_NATIVE_V1')
    if 'autonomous_decisions' in r:
        result['autonomous_decisions'] = r['autonomous_decisions']
        result['autonomous_memory'] = r.get('autonomous_memory')
        calls=[attempt['provider'] for rec in r['autonomous_decisions'] for attempt in rec['attempts'] if 'provider' in attempt]
        result['trace'].update(llm_calls=sum(c['execution'] in ('LIVE_RESPONSES','LIVE_ERROR') for c in calls),
            llm_errors=sum(c['execution']=='LIVE_ERROR' for c in calls),
            llm_replays=sum(c['execution']=='CACHE_REPLAY' for c in calls),
            execution_holds=sum(d['execution_state']=='EXECUTION_HOLD' for d in r['autonomous_decisions']),
            planner_backend=next((d['policy'] for d in r['autonomous_decisions'] if d.get('policy')), 'AUTONOMOUS_POLICY_UNCONFIRMED'),
            planner_backend_fallback_used=any(d['execution_state']=='RULE_FALLBACK' for d in r['autonomous_decisions']))
    if r.get("visit_state_used") is not None:
        result["visit_state_used"] = r["visit_state_used"]
    if r.get("m4") is not None:
        result["m4"] = r["m4"]
        result["trace"]["behavior_engine"] = "m4"
        result["trace"]["m4_configuration_sha256"] = r["m4"]["configuration"]["sha256"]
        for scene in scenes:
            event=next((e for e in r["m4"]["activity_history"] if e["date"]==r["m4"]["date"] and
                        hm(e["start"])==scene["t0"] and hm(e["end"])==scene["t1"] and e["venue_id"]==scene["loc"]),None)
            if event:
                decisions=[d for d in r["m4"]["decisions"] if d.get("actual_next_event_id")==event["event_id"]]
                scene["basis"]["m4"]={"event_id":event["event_id"],
                    "decision_packet_ids":[d["packet"]["packet_sha256"] for d in decisions],
                    "lookup":"plans[customer_id].m4.decisions", "execution_mode":"LIVE_COMPUTATION"}
    return result


def main():
    q = json.loads(sys.stdin.read() or "{}")
    from operator_choice.operator_world_v1_1 import isolated_registry as IR
    allowed = IR.allowed_personas(AD.DEMO)
    ids = [p for p in (q.get("personas") or []) if p in allowed]
    bad = [p for p in (q.get("personas") or []) if p not in allowed]
    if bad or not ids:
        print(json.dumps({"error": "시연 고객 11명 안의 ID 만 실행합니다", "code": "E_FLOW_PERSONA", "n_bad": len(bad)}, ensure_ascii=False)); return
    iv = q.get("intervention") or "none"
    if iv not in AR.INTERVENTIONS:
        print(json.dumps({"error": "정해진 운영 변경만 선택할 수 있습니다", "code": "E_FLOW_IV"}, ensure_ascii=False)); return
    seed = q.get("seed", 0)
    if not isinstance(seed, int) or isinstance(seed, bool) or not (0 <= seed <= 9999):
        print(json.dumps({"error": "seed 는 0~9999 정수", "code": "E_FLOW_SEED"}, ensure_ascii=False)); return
    if q.get("visit_date"):
        try:
            q["visit_date"] = _date.fromisoformat(q["visit_date"]).isoformat()
        except (TypeError, ValueError):
            print(json.dumps({"error": "방문 일자는 YYYY-MM-DD 형식이어야 합니다", "code": "E_FLOW_DATE"}, ensure_ascii=False)); return
    vo = q.get("visit_override") or None
    if vo is not None:
        if not isinstance(vo, dict) or any(k not in ids for k in vo):
            print(json.dumps({"error": "방문 조건은 실행 고객에게만", "code": "E_FLOW_VISIT"}, ensure_ascii=False)); return
        for k, v in vo.items():
            if not isinstance(v, dict) or v.get("building") not in (None, "GRAND", "VISTA", "DOUGLAS") or v.get("phase") not in (None, "mid", "checkin", "checkout", "visit") \
                    or v.get("club") not in (None, True, False) or (v.get("club") and v.get("building") != "GRAND") \
                    or not (v.get("party_size") is None or (isinstance(v.get("party_size"), int) and 1 <= v["party_size"] <= 8)):
                print(json.dumps({"error": "방문 조건 형식 오류", "code": "E_FLOW_VISIT"}, ensure_ascii=False)); return
    q = dict(q, seed=seed, visit_override=vo)
    mode = "many" if (q.get("mode") == "many" or len(ids) > 1) else "one"
    inp = AD.load_inputs(); P = inp[0]
    # 10/26 — 실행 입력(행동 프로파일)이 이 환경에 없는 고객은 서버 오류(500) 대신 이유를 돌려준다. 여러 명이면 입력이 있는 고객만 계산하고 빠진 고객을 알린다.
    miss = [p for p in ids if p not in P]
    if miss and (mode == "one" or len(miss) == len(ids)):
        print(json.dumps({"error": "이 고객의 행동 프로파일(로컬 보관 실행 입력)이 이 환경에 연결되어 있지 않아 계산할 수 없습니다", "code": "E_FLOW_INPUT_MISSING", "ids": miss}, ensure_ascii=False)); return
    ids = [p for p in ids if p in P]
    levers, bf, applied, skipped = map_levers(q.get("product_levers"))
    changed = iv != "none" or bool(levers) or bf is not None
    sc = scenario(iv, q, levers, bf, iv)
    shared_world = None
    if q.get("behavior_engine") in ("m4", "m4_c01") and q.get("visit_state") is not None:
        from operator_choice.autonomy_v1 import m4_runtime
        if q.get("behavior_engine") == "m4_c01":
            from operator_choice.autonomy_v1 import candidate_services as m4_runtime
        if q.get("scenario_snapshot"):
            from operator_choice.autonomy_v1 import event_scenarios as m4_runtime
        def run(s):
            nonlocal shared_world
            if q.get("simulation_mode") == "shared_world":
                batch = m4_runtime.run_many(ids, s, inp)
                shared_world = batch["shared_world"]
                return batch["personas"]
            return {pid: m4_runtime.run_one(pid, s, inp) for pid in ids}
    else:
        run = (lambda s: {ids[0]: AD.run_one(ids[0], s, inp)}) if mode == "one" else (lambda s: AD.run_many(ids, s, inp)["personas"])
    if q.get("environment") and q.get("behavior_engine") != "m4_c01":
        from operator_choice.autonomy_v1 import operational_environment as OE
        base_run = run
        def run(s):
            with OE.install():
                return base_run(s)
    after = run(sc)
    lab = AR._labels(after)
    out = dict(mode=mode, intervention=dict(id=iv, label=AR.INTERVENTIONS[iv]["label"]), levers_applied=applied, levers_not_applied=skipped)
    if shared_world is not None:
        out["shared_world"] = shared_world
    out["world_context"] = dict(date=sc["date"], day_label=sc["day_label"], event_available=bool((sc.get("levers", {}).get("WINE_FAIR") or {}).get("available")))
    new_keys = {}
    if changed:
        base_sc = scenario("base", q, None, None, None)
        before = run(base_sc)
        lab = AR._labels(before, after)
        AR.annotate(before, lab); AR.annotate(after, lab)
        at = AR.INTERVENTIONS[iv].get("at", "00:00") if iv != "none" else "00:00"
        cmp = AD.compare(before, after, at, event=iv == "wine_fair_1300")
        out["stories"] = AR.stories(before, after, cmp, at, lab, AR.INTERVENTIONS[iv]["label"] if iv != "none" else "운영 조건 변경", iv)
        new_keys = {pid: {tuple(k) for k in cmp[pid]["new"]} for pid in cmp}
        out["runs"] = compare_runs(runs_of(before, base_sc, P, mode, dict(q, product_levers={})), runs_of(after, sc, P, mode, q))
    else:
        AR.annotate(after, lab)
        out["runs"] = runs_of(after, sc, P, mode, q)
    T = {pid: turn_of(r["log"]) for pid, r in after.items()}
    out["plans"] = {pid: plan_of(pid, r, T[pid], new_keys.get(pid, set())) for pid, r in after.items()}
    out["visits"] = {pid: dict(r["visit"], registered=True) for pid, r in after.items()}
    if miss: out["input_missing"] = miss   # 빠진 고객이 있을 때만(없으면 출력 형식 · 저장본 SHA 그대로)
    out["notices"] = sorted({n["label"] if isinstance(n, dict) else str(n) for r in after.values() for n in (r.get("notices") or [])}) + ([f"실행 입력이 이 환경에 연결되지 않은 고객 {len(miss)}명은 이번 계산에서 빠졌습니다"] if miss else [])
    out["engine"] = dict(name=ENGINE, version=AD.VERSION, backend="rules(LLM 호출 0)", seed=seed, decided_by="autonomy_v1.agent_day(계획 · 상태) + operator_world_v1.decide_at · turn_candidate.decide_turn(정량 결정)")
    # Hash the resolved profile inputs (including local overlays) without returning their contents.
    out["profile_sha"] = hashlib.sha256(json.dumps({
        pid: {"profile": P[pid], "bars": inp[1].get(pid), "library": inp[2].get(pid)}
        for pid in sorted(after) if pid in P
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
    out["inputs_sha"] = hashlib.sha256(json.dumps({p: [(x["t"], x["e"], x["act"], x["loc"]) for x in r["log"]] for p, r in after.items()}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    lineage = IR.lineage(ids)
    if lineage:
        out["isolated_input_lineage"] = lineage
    s = json.dumps(out, ensure_ascii=False, default=list)
    if FORBIDDEN.search(s):
        print(json.dumps({"error": "결과에 비공개 문자열이 있어 내보내지 않음", "code": "E_FLOW_PRIVATE"}, ensure_ascii=False)); return
    print(s)


if __name__ == "__main__":
    main()
