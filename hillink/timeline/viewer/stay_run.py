"""체류·행동 계획 실행기(10/24) — 지도 화면이 /api/stay 로 부르는 별도 프로세스.
입력(stdin JSON): {"op":"visit", "personas":[...], "cond":{event}, "comp":{pid:{n,rel,kids}}, "seed":0} → {"visits":{pid:{stay,building,nights,phase,party_size,rel,layer,why}}}
                 {"op":"plan", "personas":[...], "cond":{...}, "decisions":{pid:[{turn,time,loc,label,product_label,venue_id,changed}]},
                  "base_decisions":{pid:[...]}(선택 · 기준 조건), "comp":{pid:{n,rel,kids,elder}}, "seed":0, "backend":"rules|llm|auto"}
출력: {"plans":{pid:{"scenes":[...],"backend":..,"warnings":[..]}}, "llm_available":bool}
동결 엔진(turn_view)은 부르지 않는다 — 결정은 화면이 이미 받은 엔진 결과를 그대로 넘긴다."""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PL = HERE.parent / "experiments" / "persona_live"
sys.path.insert(0, str(PL))
from operator_choice.operator_world_v1_1.turn_view import turn_meta, load_all_personas  # noqa: E402
from operator_choice.operator_world_v1_1 import stay_planner as SP  # noqa: E402
from operator_choice.operator_world_v1_1 import stay_qa_profiles as QA  # noqa: E402


def load_lib():
    out = {}
    for fn in ("persona_library.json", "persona_library.local.json"):
        f = HERE / "static" / fn
        if not f.exists():
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        ps = d.get("personas") if isinstance(d, dict) else d
        if isinstance(ps, dict):
            out.update(ps)
        else:
            for p in ps or []:
                out[p["id"]] = p
    return out


def resolve(pid, P, bars, lib, strict=False):
    """고객 ID → (계획기 프로파일, 추적 정보). 순서: ①정량 등록부(본제품 11명) ②QA 후보 패키지(SHA 검증 · 비공개 경로) ③generic_demo_fallback(명시).
    strict=True 면 ③ 대신 실패(None)를 돌려준다. 추적 정보에는 원문 · 계정 · URL 을 넣지 않는다."""
    tr = {"profile_id": pid, "profile_source": None, "profile_loaded": False, "daily_behavior_loaded": False, "daily_missing_reason": None,
          "profile_fallback_used": False, "profile_version": None, "structured_sha256": None, "daily_sha256": None, "sha_verified": False, "qa": None}
    if pid in P:
        tr.update(profile_source="registry", profile_loaded=True, profile_version="V1-registry", data_approval="PRODUCT_REGISTRY_V1",
                  daily_missing_reason="본제품 정량 등록부 고객 — 이번 범위에서 daily_behavior_profile 미연결(축소 모드: 성향 막대 · 후기 사실만)")
        return SP.profile(pid, P.get(pid), bars.get(pid), lib), tr
    raw, st = QA.load(pid)
    if raw:
        st["type_hint"] = qa_type(raw, pid)
        prof, qa = SP.qa_profile(pid, raw, st)
        tr.update(profile_source="qa_profile", profile_loaded=True, daily_behavior_loaded=st["daily_behavior_loaded"], daily_missing_reason=st["daily_missing_reason"],
                  profile_version=st["profile_version"], structured_sha256=st["structured_sha256"], daily_sha256=st["daily_sha256"], sha_verified=st["sha_verified"],
                  package=st["package"], mapping_version=st["mapping_version"], data_approval=st["data_approval"], data_hold=st["data_hold"], qa=qa)
        return prof, tr
    tr.update(profile_source="generic_demo_fallback", profile_fallback_used="generic_demo_fallback", load_error=st.get("load_error"),
              daily_missing_reason="프로파일 미로드 — 일상 행동 자료 없음")
    if strict:
        return None, tr
    return SP.profile(pid, None, [], lib), tr


def qa_type(raw, pid):
    """유형 힌트 — 같은 패키지 manifest 의 임시 출처 유형(분석 라벨). 없으면 빈 값."""
    import csv
    for r in QA.roots():
        for m in list(r.glob("manifest.csv")) + list(r.glob("*/manifest.csv")) + list(r.glob("*/*/manifest.csv")):
            try:
                for row in csv.DictReader(m.read_text(encoding="utf-8-sig").splitlines()):
                    if row.get("author_id") == pid:
                        return row.get("tentative_source_type") or ""
            except Exception:
                pass
    return ""


def main():
    q = json.loads(sys.stdin.read() or "{}")
    op = q.get("op", "plan")
    if op not in ("plan", "visit"):
        raise SystemExit("op 없음")
    P = load_all_personas()
    meta = turn_meta("dinner", P)
    bars = {p["id"]: p.get("bars") or [] for p in meta.get("personas", [])}
    lib = load_lib()
    cond = q.get("cond") or {}
    seed = int(q.get("seed") or 0)
    backend = q.get("backend") or "rules"
    strict = bool(q.get("strict_profiles"))   # True: 미등록 · 미로드 ID 는 일반 계획 대신 명시적 실패
    if op == "visit":   # 보충2 — 고객별 방문 상태(투숙 · 건물 · 박수 · 체류 단계 · 동행)를 프로파일 + 월드 조건으로 정한다(엔진 호출 없음)
        visits = {}
        for pid in q.get("personas") or []:
            prof, tr = resolve(pid, P, bars, lib, strict)
            if prof is None:
                visits[pid] = {"status": "error", "error": "프로파일 미로드(strict)", "trace": tr, "registered": False}; continue
            comp = (q.get("comp") or {}).get(pid) or (QA.party_for_visit(prof, seed) if tr["profile_source"] == "qa_profile" else None)
            visits[pid] = SP.visit_state(prof, cond, comp, seed)
            visits[pid]["registered"] = pid in P   # 정량 등록부에 없는 ID = 개인화 정량 결정 없음
            visits[pid]["trace"] = trace_public(tr)
            if comp and comp.get("basis"): visits[pid]["basis"]["party_facts"] = comp["basis"]
        sys.stdout.write(json.dumps({"visits": visits}, ensure_ascii=False, default=list))
        return
    plans = {}
    cond_by = q.get("cond_by") or {}   # 고객별 방문 조건(여러 명 자율 모드) — 없으면 공통 조건
    for pid in q.get("personas") or []:
        prof, tr = resolve(pid, P, bars, lib, strict)
        if prof is None:
            plans[pid] = {"status": "error", "scenes": [], "error": "프로파일 미로드(strict) — 계획 생성 안 함", "trace": trace_public(tr), "registered": False}; continue
        dec = (q.get("decisions") or {}).get(pid) or []
        comp = (q.get("comp") or {}).get(pid) or {}
        cp = dict(cond, **(cond_by.get(pid) or {}))
        base = None
        bdec = (q.get("base_decisions") or {}).get(pid)
        if bdec:
            base = SP.plan_rules(prof, bdec, cp, comp, seed)
        if not comp and tr["profile_source"] == "qa_profile":
            comp = QA.party_for_visit(prof, seed) or {}
        out = SP.plan(prof, dec, cp, comp, seed, backend, base_plan=base)
        out["registered"] = pid in P
        iu = out["inputs_used"]
        out["trace"] = dict(trace_public(tr), backend_requested=out["requested"], backend_used=out["backend"],
                            planner_backend_fallback_used=out["requested"] != out["backend"], fallback_reason=out["fallback_reason"],
                            decision_context_preserved=out["decision_context_preserved"],
                            # 계획기 입력 검증 = 이 고객 소유 사실 ID 또는 일상 슬롯이 실제 장면 근거로 쓰였는가(파일 존재만으로 참이 되지 않음)
                            planner_inputs_verified=bool(tr["profile_loaded"] and (iu["fact_ids"] or iu["daily_slots"] or iu.get("trait_fact_ids") or (tr["profile_source"] == "registry" and iu["trait_keys"]))),
                            # 개인화 상태 — 미로드(generic_demo_fallback)는 개인화 성공이 아니다 · QA 입력은 제품 승인 자료와 구별
                            personalization=("not_personalized_generic_demo" if tr["profile_fallback_used"] else
                                             "qa_profile_unapproved" if tr["profile_source"] == "qa_profile" else "product_registry"),
                            scene_sources={k: sum(1 for x in out["scenes"] if x.get("source") == k) for k in ("observed_reference", "quantitative_decision", "generated_plan")})
        plans[pid] = out
    sys.stdout.write(json.dumps({"plans": plans, "llm_available": SP.llm_available()}, ensure_ascii=False, default=list))


def trace_public(tr):
    """응답에 싣는 추적 — QA 상세(성향 근거 · 차단 사실)는 ID · 수준만. 원문 · 경로 · 계정 없음."""
    t = {k: v for k, v in tr.items() if k != "qa"}
    q = tr.get("qa")
    if q:
        t["qa_inputs"] = {"facts_walkerhill": q["facts_walkerhill"], "facts_other": q["facts_other"], "traits": q["traits"], "rules": q["rules"],
                          "daily_slots_observed": q["daily_slots_observed"], "daily_slots_hypothesis_only": q["daily_slots_hypothesis_only"],
                          "blocked_facts": q["blocked_facts"], "trait_levels": {k: v["level"] for k, v in q["trait_evidence"].items() if v["level"]},
                          "trait_evidence_ids": {k: (v["walkerhill"] + v["other"])[:4] for k, v in q["trait_evidence"].items() if v["level"]},
                          "party_candidates": q["party_candidates"], "activity_links": q.get("activity_links")}
    return t


if __name__ == "__main__":
    main()
