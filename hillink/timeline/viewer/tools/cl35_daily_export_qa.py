"""CL-1025-35 — CD-14D 수용 sidecar 계약(점수 0)으로 첫 5명 격리 실행 → 하루 전체 행동 내역 export. 읽기 전용 QA · LLM 호출 0.

  python3 tools/cl35_daily_export_qa.py --boundary B.csv --approval A.csv --source PERSONAS_DIR --out OUT [--head SHA]

무엇을 하나
· 운영 경로 그대로: TrustedInputs(커밋된 고정 manifest) → build_sidecar → install_into_flow(이 프로세스 메모리 한정 alias 5명).
· 각 고객 × 시나리오를 실제 /api/flow 코드(flow_run.main)로 돌리고, 같은 시나리오를 agent_day.run_one 으로 다시 돌려
  하루 기록(log)을 행 단위로 export 한다. 두 경로의 inputs_sha 가 같아야만 내보낸다(= export 한 기록이 /api/flow 기록).
· 칼럼은 '실제 계산 기여'(엔진 점수 항 · 공통/후기/가정/내다보기 몫 · 점수 인용 사실)와 '설명용 관측 사실'(sidecar 관측 · 점수 0 · 선택에 미사용)을
  따로 둔다. 관측 사실은 활동 코드 표(OBS_ACT · 문자 그대로 대응)로만 장면 옆에 표시하고, 엔진 입력에는 들어가지 않는다.
· 엔진 설명 문장(why)은 그대로 싣되, 성향 근거가 0인데 '성향' 낱말이 있으면 TEMPLATE_SENTENCE_NOT_PERSONAL 로 표시한다.

하지 않는 것
· 엔진 · 월드 · 스키마 · importer · flow_run 수정 없음. 날짜를 바꾸는 입력이 엔진에 없어(월드는 date 를 읽지 않음) 다른 날짜 행사는 NOT_RUN 으로 남긴다.
· 원문 · 사실 요지 · URL · 계정은 출력에 없음(사실 ID · 상태 · 활동 코드만). 결과는 --out(비공개)에만.
"""
import argparse, csv, hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE / "tools"), str(HERE)]
import approval_sidecar_qa as S  # noqa: E402
import lp16_flow_qa as Q  # noqa: E402

FR, AD = Q.FR, Q.AD

SCENARIOS = {   # 실행 가능한 것만. 엔진 날짜 라벨은 2026-10-24(토) 고정 · 월드는 날짜를 읽지 않음
    "BASE_NO_EVENT": dict(event=False, programming="HYPOTHETICAL_EVENT_PROGRAMMING",
                          label="엔진 기준일(고정 라벨 2026-10-24 토) · 와인페어 끔",
                          note="실제 2026-10-24 는 와인페어 행사일 — 같은 날 행사를 끈 편성은 가상 비교 기준선"),
    "WINE_FAIR_20261024": dict(event=True, programming="DATE_CONSISTENT_SIMULATED_VISIT",
                               label="2026-10-24 와인페어 행사일(엔진 창 2부 15:30~20:00)",
                               note="행사 날짜 · 운영은 공식 일정과 같음 · 방문팀과 하루는 시뮬레이션(실제 방문 기록 아님) · 1부(11:00~15:00)는 엔진에 없음"),
}
NOT_RUN = {
    "AUTUMN_CAMCNIC_20261026": "엔진 시나리오에 날짜 입력이 없음(scenario.date 라벨만 있고 World 가 읽지 않음) · 캠크닉 패키지/행사 offer 가 엔진 월드에 없음 · "
                               "10/26(월)을 10/24 고정일에 끼워 넣으면 실제 일자처럼 보이므로 실행하지 않음 — 엔진 · 월드 확장은 금지 범위",
}
OBS_ACT = {   # 관측 활동 코드 → 엔진 행동/업장(문자 그대로 대응하는 것만 · 설명 표시용)
    "FOREST_PARK_WINE_FAIR": {"WINE_FAIR"}, "ONDAL_DINNER_COURSE": {"ONDAL", "lunch_ondal"}, "ONDAL_PRICE_VALUE": {"ONDAL", "lunch_ondal"},
    "ROOM_SERVICE_PRICE": {"ROOM_MEAL", "lunch_room"}, "PAVILION_CAFE": {"cafe", "lunch_cafe"}, "THE_BUFFET_BREAKFAST": {"THE_BUFFET"},
    "RIVERPARK_POOL": {"riverpark"}, "THEATRE_OF_LIGHT": {"theatre"},
}   # DOUGLAS_LOUNGE · DOUGLAS_BREAKFAST = 엔진에 표현 없음(REPRESENTATION_GAP) · CAFE(장소 미특정)는 업장 대응 없음
TEMPLATE_RX = re.compile(r"성향|기울|중시|좋아|취향")
COLS = ["scenario_id", "programming", "alias", "source_profile_id", "seed", "code_head", "seq", "t_start", "t_end", "act", "label", "loc", "domain",
        "decision_source", "decision_engine", "candidates_feasible", "not_chosen_feasible", "not_chosen_blocked", "time_event_constraints",
        "score", "total", "contrib_common", "contrib_review", "contrib_assumption", "contrib_lookahead", "scoring_fact_ids", "reason_basis",
        "why_text_engine", "why_text_flag", "charge_status", "charge_krw", "package_eligibility", "explanatory_observation_ids_display_only"]


def r4(v):
    return None if v is None else round(float(v), 4)


def flow_q(pid, scn, seed):
    return {"personas": [pid], "mode": "one", "seed": seed, "event": SCENARIOS[scn]["event"]}


def raw_run(pid, scn, seed, inp):
    q = dict(flow_q(pid, scn, seed), visit_override=None)
    sc = FR.scenario("none", q, None, None, None)   # flow_run.main 과 같은 생성(개입 · 레버 없음)
    return AD.run_one(pid, sc, inp)


def log_sha(pid, r):
    return hashlib.sha256(json.dumps({pid: [(x["t"], x["e"], x["act"], x["loc"]) for x in r["log"]]}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def obs_for(act, obs):
    return sorted(o["fact_id"] for o in obs if any(act in OBS_ACT.get(a, ()) for a in o["applicable_activities"]))


def row_of(x, base, obs):
    i = x.get("internal") or {}
    tr = i.get("turn_raw")
    src = x["source"]
    out = dict(base, t_start=x["t"], t_end=x["e"], act=x["act"], label=x["label"], loc=x["loc"], domain=x["domain"], decision_source=src,
               decision_engine=i.get("engine") or ("turn_candidate.decide_turn(breakfast)" if tr and tr.get("world") == "breakfast" else ""),
               why_text_engine=x.get("why", ""), charge_status=(x.get("charge") or {}).get("status"), charge_krw=(x.get("charge") or {}).get("krw"),
               package_eligibility="unknown(패키지 · 예약 입력 없음)" if src in ("quantitative_engine", "planner_rules") else "",
               explanatory_observation_ids_display_only="|".join(obs_for(x["act"], obs)))
    cited, review = [], 0.0
    if tr:
        terms = tr.get("terms") or []
        cited = sorted({f for t in terms for f in t.get("fact_ids") or []})
        parts = {k: round(sum((t.get("parts") or {}).get(k, 0.0) for t in terms), 4) for k in ("common", "review", "assumption")}
        review = parts["review"]
        rej = tr.get("rejected") or []
        feas = [q for q in rej if q.get("feasible") and q["offer"] != tr["chosen"]]
        blocked = [q for q in rej if not q.get("feasible")]
        cand = [(tr["chosen"], tr["total"] if tr.get("total") is not None else tr.get("score"))] + [(q["offer"], q.get("total") if q.get("total") is not None else q.get("score")) for q in feas]
        lk = (tr["total"] - tr["score"]) if tr.get("total") is not None and tr.get("score") is not None else None
        ev = [f"{e['offer']}:{e['stage']}({' · '.join(e.get('why') or [])})" for e in i.get("event_view") or []]
        out.update(candidates_feasible="|".join(f"{k}={r4(v)}" for k, v in cand), not_chosen_feasible="|".join(f"{q['offer']}={r4(q.get('total') if q.get('total') is not None else q.get('score'))}" for q in feas),
                   not_chosen_blocked="|".join(f"{q['offer']}:{' · '.join(q.get('blocked') or [])}" for q in blocked),
                   time_event_constraints="|".join(ev), score=r4(tr.get("score")), total=r4(tr.get("total")), contrib_common=parts["common"],
                   contrib_review=parts["review"], contrib_assumption=parts["assumption"], contrib_lookahead=r4(lk), scoring_fact_ids="|".join(cited))
        out["reason_basis"] = "REVIEW_EVIDENCE" if (cited or abs(review) > 1e-9) else "MODEL_SCORE_GENERIC_DEFAULT(공통 · 시간 · 동행 항만 · 후기 몫 0)"
    elif src == "planner_rules":
        w, rj = i.get("weights") or {}, i.get("rejected") or {}
        out.update(candidates_feasible="|".join(f"{k}={r4(v)}" for k, v in sorted(w.items(), key=lambda z: -z[1])),
                   not_chosen_feasible="|".join(f"{k}={r4(v)}" for k, v in w.items() if k != x["act"]),
                   not_chosen_blocked="|".join(f"{k}:{v}" for k, v in rj.items()), reason_basis="UNKNOWN/GENERIC_DEFAULT(규칙 계획기 가중 · 정량 모델 점수와 연결 안 됨)")
    elif src == "obligation":
        out["reason_basis"] = "OBLIGATION(도착 · 체크인 · 취침 등 고정 일정)"
    else:
        out["reason_basis"] = "WORLD_RULE(이동 · 대기 · 운영 규칙)"
    for e in x.get("evidence") or []:
        if e.get("type") == "후기에서 확인":
            cited = sorted(set(cited) | set(e.get("fact_ids") or []))
            out["scoring_fact_ids"] = "|".join(cited)
            out["reason_basis"] = "REVIEW_EVIDENCE"
    trait_ev = [t for e in x.get("evidence") or [] for t in e.get("traits") or []]
    if TEMPLATE_RX.search(out["why_text_engine"]) and not cited and not trait_ev:
        out["why_text_flag"] = "TEMPLATE_SENTENCE_NOT_PERSONAL(성향 · 후기 근거 0 — 문장 속 성향 · 취향 표현은 엔진 공통 항 이름)"
    else:
        out["why_text_flag"] = ""
    return out


def control_no_sidecar(ids, alias2sid, seed):
    """대조: sidecar · 신뢰 입력 · 관측 없이, 같은 alias 를 빈 성향(empty_traits)과 같은 유형 문자열로만 등록해 같은 시나리오를 돌린 기록 SHA."""
    QP, QL = {}, {}
    for pid in ids:
        lab, comp = S.QA_TYPE.get(alias2sid[pid], ("", None))
        QP[pid] = dict(id=pid, label=f"{pid} · 대조(sidecar 없음)", companion=None, source_post_count=0, active_fact_count=0, traits=S.empty_traits(pid, comp))
        QL[pid] = dict(id=pid, group="qa_isolated", type=lab, type_group=lab, engine=dict(facts={}), wh_events=[], other_events=[], visit_feature_summary={})
    base_lap, base_li = AD.load_all_personas, AD.load_inputs
    AD.load_all_personas = lambda: dict(base_lap(), **QP)
    AD.load_inputs = lambda: (lambda P, b, l: (P, b, dict(l, **QL)))(*base_li())
    try:
        inp = AD.load_inputs()
        return {(scn, pid): log_sha(pid, raw_run(pid, scn, seed, inp)) for scn in SCENARIOS for pid in ids}
    finally:
        AD.load_all_personas, AD.load_inputs = base_lap, base_li


def main(a):
    T = S.TrustedInputs(a.boundary, a.approval, a.source)
    sc = S.build_sidecar(a.boundary, a.approval, a.source)
    ids, OBS = S.install_into_flow(sc, T)
    alias2sid = {"QA16_" + s.split("-")[1]: s for s in sc}
    all62 = {r["fact_id"] for rows in sc.values() for r in rows}
    hidden = {r["fact_id"] for rows in sc.values() for r in rows if r["contract_state"] not in S.SURFACED}
    inp = AD.load_inputs()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows, matrix, visits, seqs, qa = [], [], {}, {}, dict(flow_vs_raw=[], determinism=[], forbidden=[], review_nonzero=0, cited_62=0, obs_hidden_leak=0)
    for scn, spec in SCENARIOS.items():
        for pid in ids:
            fl = Q.flow(flow_q(pid, scn, a.seed))
            if "error" in fl:
                matrix.append(dict(scenario_id=scn, alias=pid, status="ERROR", code=fl.get("code"))); continue
            r = raw_run(pid, scn, a.seed, inp)
            r2 = raw_run(pid, scn, a.seed, inp)
            sha = log_sha(pid, r)
            qa["flow_vs_raw"].append((scn, pid, sha == fl["inputs_sha"]))
            qa["determinism"].append((scn, pid, sha == log_sha(pid, r2)))
            if FR.FORBIDDEN.search(json.dumps(fl, ensure_ascii=False, default=list)):
                qa["forbidden"].append((scn, pid))
            base = dict(scenario_id=scn, programming=spec["programming"], alias=pid, source_profile_id=alias2sid[pid], seed=a.seed, code_head=a.head)
            for n, x in enumerate(r["log"]):
                rw = row_of(x, dict(base, seq=n), OBS[pid])
                rows.append(rw)
                qa["review_nonzero"] += bool(rw.get("contrib_review"))
                qa["cited_62"] += bool(set(filter(None, (rw.get("scoring_fact_ids") or "").split("|"))) & all62)
                qa["obs_hidden_leak"] += bool(set(filter(None, rw["explanatory_observation_ids_display_only"].split("|"))) & hidden)
            v = r["visit"]
            visits[(scn, pid)] = {k: v.get(k) for k in ("stay", "building", "phase", "nights", "party_size", "rel", "layer", "why")}
            seqs[(scn, pid)] = [(x["t"], x["act"]) for x in r["log"] if x["act"] not in ("move",)]
            matrix.append(dict(scenario_id=scn, programming=spec["programming"], alias=pid, source_profile_id=alias2sid[pid], seed=a.seed, code_head=a.head,
                               runs=1, path="flow_run.main(/api/flow 코드) + agent_day.run_one(같은 시나리오 재실행)", status="RUN",
                               inputs_sha=fl["inputs_sha"], flow_equals_raw=sha == fl["inputs_sha"], deterministic=sha == log_sha(pid, r2),
                               scenes=len(r["log"]), engine_decisions=sum(1 for x in r["log"] if (x.get("internal") or {}).get("turn_raw")),
                               planner_decisions=sum(1 for x in r["log"] if x["source"] == "planner_rules"),
                               wine_fair_chosen=any(x["act"] == "WINE_FAIR" for x in r["log"]), observations=len(OBS[pid]),
                               visit_layer=v.get("layer"), note=spec["note"]))
    ctl = control_no_sidecar(ids, alias2sid, a.seed)
    shas = {(m["scenario_id"], m["alias"]): m.get("inputs_sha") for m in matrix if m["status"] == "RUN"}
    qa["control_no_sidecar_equal"] = [(k[0], k[1], ctl[k] == shas[k]) for k in shas]
    for m in matrix:
        if m["status"] == "RUN":
            m["equals_no_sidecar_control"] = ctl[(m["scenario_id"], m["alias"])] == m["inputs_sha"]
    for scn, why in NOT_RUN.items():
        for pid in ids:
            matrix.append(dict(scenario_id=scn, programming="NOT_RUN", alias=pid, source_profile_id=alias2sid[pid], seed="", code_head=a.head, runs=0, status="NOT_RUN", note=why))
    with open(out / "trace.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows)
    mcols = sorted({k for m in matrix for k in m}, key=lambda k: (["scenario_id", "programming", "alias", "source_profile_id", "status", "runs", "seed", "code_head"] + [k]).index(k) if k in ["scenario_id", "programming", "alias", "source_profile_id", "status", "runs", "seed", "code_head"] else 99)
    with open(out / "matrix.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=mcols); w.writeheader(); w.writerows(matrix)
    obs_out = {pid: [dict(fact_id=o["fact_id"], contract_state=o["contract_state"], behavior_occurrence=o["behavior_occurrence"],
                          applicable_activities=o["applicable_activities"], score_contribution=o["score_contribution"]) for o in OBS[pid]] for pid in ids}
    json.dump(dict(visits={f"{k[0]}|{k[1]}": v for k, v in visits.items()}, seqs={f"{k[0]}|{k[1]}": v for k, v in seqs.items()}, observations=obs_out,
                   qa=qa, n_obs=sum(len(v) for v in OBS.values()), contract_counts={s: sum(r["contract_state"] == s for rows in sc.values() for r in rows) for s in S.STATES},
                   manifest_sha=T.manifest_sha, scenarios=SCENARIOS, not_run=NOT_RUN),
              open(out / "meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(dict(rows=len(rows), runs=sum(m["status"] == "RUN" for m in matrix), not_run=sum(m["status"] == "NOT_RUN" for m in matrix),
                          flow_eq=all(z[2] for z in qa["flow_vs_raw"]), determ=all(z[2] for z in qa["determinism"]), forbidden=len(qa["forbidden"]),
                          control_eq=all(z[2] for z in qa["control_no_sidecar_equal"]), review_nonzero=qa["review_nonzero"], cited_62=qa["cited_62"], obs_hidden_leak=qa["obs_hidden_leak"]), ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for k in ("--boundary", "--approval", "--source", "--out"):
        ap.add_argument(k, required=True)
    ap.add_argument("--head", default="")
    ap.add_argument("--seed", type=int, default=0)
    main(ap.parse_args())
