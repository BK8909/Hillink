"""팀 프로파일 수용 점검기(10/23) — 새 작성자(예: A16 · N09 · A13 · A15)의 익명 공용 프로파일(team_persona_shared_export_v1)을
같은 변환기(V1.1 importer → 측정 계약 M-1/M-2)로 엔진 입력 후보로 바꾸고, 연결 전에 검수 항목을 출력한다.

- 기본은 점검만(dry run). --write 를 주면 로컬 전용 turn_personas_ext.local.json 에 '팀 export · 13차 분리 없음' 파이프라인으로 추가한다(저장소에 올리지 않음).
- R-BASE 5명 · 기존 입력은 바꾸지 않는다. 계수 변경 없음.
- 점검: ① 사실 수 vs 독립 경험(경험 키) 수 ② 미래 · 기대 사실이 경험 이력 성향(routine 등)에 연결됐는지 ③ 미실행(decline · motive) 단계가
  음주 · 반복 이력 성향에 연결됐는지 ④ 원문 앵커 · 링크 문자열이 없는지 ⑤ 성향이 실제 턴 결정 항목(저녁 · 행사 · 아침)에 쓰이는지
사용: python3 intake_team_profile.py <profile.json> [--write]
"""
import argparse, json, re, sys
from collections import Counter
from pathlib import Path

PL = Path(__file__).resolve().parent.parent / "experiments" / "persona_live"
sys.path.insert(0, str(PL))
from operator_choice.operator_world_v1_1 import importer as V11  # noqa: E402
from operator_choice.operator_world_v1_1.candidate_import import apply_measurement_contract  # noqa: E402
from operator_choice.operator_world_v1_1.turn_view import turn_view, EXT_PATHS  # noqa: E402

HISTORY_FACETS = ("routine", "alcohol_familiar", "food", "space")
NOCONSUME = re.compile(r"(사지 않|구매하지 않|마시지 않|음주하지 않|손대지 않)")
IDENT = re.compile(r"https?://|blog\.naver|instagram|@")
CONDS = {"저녁 기본": {}, "저녁 파스타 60,000": {"product_levers": {"PH_PASTA": {"price": 60000}}},
         "행사 55,000": {"turn": "event", "event": True}, "행사 할인 30,000": {"turn": "event", "event": True, "product_levers": {"WINE_FAIR": {"guest_discount": 30000}}},
         "아침 기본": {"turn": "breakfast"}}


def check(path: str):
    t = json.loads(Path(path).read_text(encoding="utf-8"))
    assert t.get("schema_version", "").startswith("team_persona_shared_export"), "공용 내보내기 형식이 아님"
    pid = t["author_group_id"]; facts = t["facts"]
    doc = {"STRUCTURED_PROFILE": {"persona_id": pid, "facts": facts}}
    traits = apply_measurement_contract(doc, V11.build_traits_v42_plus(doc))[0]
    rep = {"persona": pid, "facts": len(facts), "experiences": len({f.get("experience_key") or f["fact_id"] for f in facts}),
           "review_status": t.get("review_status"), "issues": []}
    links = {f["fact_id"]: V11.link_fact_v11(f)["links"] for f in facts}
    for f in facts:
        L = links[f["fact_id"]]
        if (f.get("time_scope") in ("future", "mixed") or f.get("kind") == "expectation") and any(k in L and L[k][0] != "X" for k in HISTORY_FACETS):
            rep["issues"].append(dict(fact=f["fact_id"], type="미래 · 혼합 시점 사실이 경험 이력 성향에 연결 — 확인 필요", facets=[k for k in HISTORY_FACETS if k in L]))
        if f.get("kind") in ("decline", "motive") and "alcohol_familiar" in L:
            rep["issues"].append(dict(fact=f["fact_id"], type="동기 · 미구매 단계가 음주 친숙성에 연결 — 확인 필요(실제 선호 표현이면 유지 · 시도 후 미구매면 정정 후보)", facets=["alcohol_familiar"]))
    # 사건 단위(02-A 안 C 와 같은 구조): 같은 사건(event_id → experience_key)에 미구매 · 미음주 단계가 있으면,
    # 그 사건의 시도 · 관람 단계(act ∈ attempt/visit, 라벨 없으면 kind 가 purchase · consume 아닌 단계)가 소비 이력에 연결됐는지 본다.
    ev = {}
    for f in facts:
        k = f.get("event_id") or f.get("experience_key")
        if k: ev.setdefault(k, []).append(f)
    for k, fs in ev.items():
        if not any(x.get("kind") == "decline" for x in fs): continue
        for f in fs:
            act = f.get("act")
            nonconsume = act in ("attempt", "visit") if act else f.get("kind") not in ("decline", "purchase", "consume")
            if nonconsume and "alcohol_familiar" in links[f["fact_id"]]:
                rep["issues"].append(dict(fact=f["fact_id"], event=k, type="사건 단위: 미소비로 끝난 사건의 시도 · 관람 단계가 음주 친숙성에 연결 — 확인 필요" + ("" if act else "(act 라벨 없음)"), facets=["alcohol_familiar"]))
    # 분리 안 된 한 문장에 '시도 · 관람'과 '미구매 · 미음주'가 함께 있으면 사건 단위 규칙이 닿지 않는다 → 단계 분리 필요(검수 표시만 · 연결 규칙 아님)
    for f in facts:
        if f.get("kind") not in ("decline",) and "alcohol_familiar" in links[f["fact_id"]] and NOCONSUME.search(f.get("detail", "")):
            rep["issues"].append(dict(fact=f["fact_id"], type="한 문장에 시도 · 관람과 미구매 · 미음주가 섞임 — 단계 분리(act 라벨) 뒤 사건 단위 규칙 적용 필요", facets=["alcohol_familiar"]))
    if IDENT.search(json.dumps(t, ensure_ascii=False)):
        rep["issues"].append(dict(type="식별 문자열(링크 · 계정) 포함 — 연결 중단"))
    per = dict(id=pid, label=f"{pid} · 후기 작성자", companion=None, pipeline="팀 export v1 → V1.1 importer + 측정 계약 · 13차 단계 분리 없음 · 검수 전", traits=traits)
    rep["facet_levels"] = {k: round(v["level"], 2) for k, v in traits["facets"].items() if v.get("present")}
    rep["turns"] = {}
    for cn, c in CONDS.items():
        cu = turn_view([pid], c, {pid: per})["customers"][0]
        rep["turns"][cn] = dict(choice=cu["choice"]["product_id"], review_share=round(cu["reason_totals"]["review"], 2),
                                facts_used=sorted({fid for r in cu["reasons"] if r["parts"]["review"] > 0.05 for fid in r["fact_ids"]})[:6])
    rep["unused_in_turns"] = "후기 근거 몫이 모든 조건에서 0.1 미만 — 개인화 근거 부족" if all(v["review_share"] < 0.1 for v in rep["turns"].values()) else None
    return rep, per


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("profile"); ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    rep, per = check(a.profile)
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    if a.write:
        if any("식별" in i["type"] for i in rep["issues"]):
            raise SystemExit("식별 문자열 — 쓰지 않음")
        p = EXT_PATHS[1]
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"_about": "로컬 전용 확장 에이전트(저장소 밖)", "personas": {}}
        d["personas"][per["id"]] = per
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
        print("로컬 전용 입력에 추가:", p)


if __name__ == "__main__":
    main()
