"""산출물 생성: python3 -m operator_choice.operator_world_v1 build [--out DIR]
- 모델 호출 0 · 기존 파일 덮어쓰지 않음(다른 내용이면 오류 · 같은 내용이면 통과)
- presets: 운영자 시나리오(기본 · 가격 인하 · 객실 패키지 · 페어링 코스 · 셰프 콜라보 · 무알코올 · 미개최) × 작성자
- grid: 화면의 운영자 조작을 서버 없이도 돌려 보기 위한 조합표(가격 × 할인 × 음식 구성 × 셰프 × 패키지 × 무알코올)
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from . import engine as EN
from . import profile_adapter as PA
from . import world as WD
from .gists import PATTERN_KO

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "operator_world_v1_artifacts"
ENTRIES = [
    dict(id="blog41", persona_id="blog41", visit="default", label="blog41 · 새 경험 · 특별한 식음에 실제 행동", source="V4.1 개발 · 원문 대조 잠정 프로파일(54편) · 검수 전"),
    dict(id="blog42", persona_id="blog42", visit="default", label="blog42 · 혜택 활용 · 조식 · 휴식과 새 메뉴 병행", source="V4.1 개발 · 원문 대조 잠정 프로파일(58편) · 검수 전"),
    dict(id="blog43", persona_id="blog43", visit="default", label="blog43 · 와인 · 미식 · 공간 — 일반 2인 숙박", source="경수 수동 파일럿(50편) · 자동 추출 아님 · 근거 글 단위(사실 단위인 blog41 · 42와 점수 척도 다름 · 근거 단위에 결과가 민감) · 검수 전"),
    dict(id="blog43_rest", persona_id="blog43", visit="rest", label="blog43 · 같은 작성자 — 조용한 휴식이 목적인 숙박", source="같은 프로파일 · 방문 목적만 다름 · 근거 글 단위"),
]
PERSONAS = tuple(e["id"] for e in ENTRIES)
ENTRY = {e["id"]: e for e in ENTRIES}

PRESETS = [
    dict(id="base", label="① 기본(공식 운영 조건): 2부 15:30~20:00 · 입장권 55,000원 · 시음 + 푸드 교환권 1매 · 메뉴 미공개", levers={},
         operator_question="와인페어를 지금 구성 그대로 열면 이 고객은 참여할까, 기존 저녁 · 휴식을 택할까?"),
    dict(id="price_down", label="② 투숙객 할인 30,000원", levers={"WINE_FAIR": {"guest_discount_krw": 30000}},
         operator_question="투숙객 할인을 주면 참여 판단이 어떻게 달라지나?"),
    dict(id="bundle", label="③ 객실 패키지에 행사 포함", levers={"WINE_FAIR": {"in_package": True}},
         operator_question="객실과 묶어 팔면(추가 지불 없음) 참여 · 다른 일정이 어떻게 바뀌나?"),
    dict(id="pairing", label="④ 음식 페어링 코스 3종 · 90,000원 · 메뉴 공개(치즈 · 해산물)", levers={"WINE_FAIR": {"food_level": "pairing_course", "price_pp_krw": 90000, "menu_known": True, "menu_tags": ["wine", "cheese", "seafood"]}},
         operator_question="와인 중심에서 음식 페어링 중심으로 바꾸고 값을 올리면?"),
    dict(id="chef", label="⑤ 셰프 콜라보 페어링(피자 · 갈릭) · 120,000원", levers={"WINE_FAIR": {"food_level": "pairing_course", "quality": "chef_collab", "price_pp_krw": 120000, "menu_known": True, "menu_tags": ["wine", "pizza", "garlic"]}},
         operator_question="셰프 콜라보로 프리미엄화하면 누가 반응하나? 가격 인하와 무엇이 다른가?"),
    dict(id="nonalc", label="⑥ 안주 1종 · 무알코올 대안 · 55,000원", levers={"WINE_FAIR": {"food_level": "light_bites", "nonalcoholic_alt": True, "menu_known": True, "menu_tags": ["wine", "cheese"]}},
         operator_question="술이 약한 고객 · 비음주 동행을 위해 무알코올 대안을 두면?"),
    dict(id="closed", label="⑦ 와인페어 미개최(대조)", levers={"WINE_FAIR": {"available": False}},
         operator_question="행사가 없을 때의 하루 — 행사가 무엇을 대체 · 추가했는지 보는 기준"),
    dict(id="evening", label="⑧ [가상] 저녁 시간대 17:00~21:00로 변경", levers={"WINE_FAIR": {"window": {"start": "17:00", "end": "21:00"}}},
         operator_question="공식 2부(15:30~20:00) 대신 저녁 시간대로 옮기면 저녁 식사 · 야경과 어떻게 맞물리나? (가상 운영 변경안 · 3 · 4차의 기본 시간)"),
    dict(id="menu_board", label="⑨ [가상] 행사장 입구에 메뉴 게시", levers={"WINE_FAIR": {"onsite_menu_board": True}},
         operator_question="메뉴를 미리 공개하지 않더라도 입구에 게시하면, 망설이던 고객의 판단이 바뀌나? (가상 운영 변경안)"),
]

GRID = dict(price_pp_krw=[30000, 55000, 90000, 120000, 160000], guest_discount_krw=[0, 20000, 30000],
            food_level=["tasting_only", "light_bites", "pairing_course"], quality=["standard", "chef_collab"],
            in_package=[False, True], nonalcoholic_alt=[False, True])
GRID_MENU = {"tasting_only": dict(menu_known=False, menu_tags=["wine"]), "light_bites": dict(menu_known=True, menu_tags=["wine", "cheese"]),
             "pairing_course": dict(menu_known=True, menu_tags=["wine", "cheese", "seafood"])}
GRID_MENU_CHEF = {"pairing_course": dict(menu_known=True, menu_tags=["wine", "pizza", "garlic"])}


def compact_step(s: dict, n_rej: int = 6) -> dict:
    return dict(time=s["time"], starts=s["starts"], ends=s["ends"], chosen=s["chosen"], label=s["label"], kind=s["kind"], stage=s["stage"],
                score=s["score"], total=s.get("total"), next_plan=s.get("next_plan"), runner_up_next=s.get("runner_up_next"),
                action=s.get("action"), plan_change=s.get("plan_change"), browse_note=s.get("browse_note"),
                margin=s["margin"], runner_up=s["runner_up"], out_of_pocket_pp=s["out_of_pocket_pp"], hunger_after=s["hunger_after"],
                reasons=s["reasons"][:8],
                rejected=sorted([r for r in s["rejected"] if r["feasible"]], key=lambda r: -(r["total"] if r.get("total") is not None else r["score"]))[:n_rej] + [r for r in s["rejected"] if not r["feasible"]][:3],
                event_stages=s["event_stages"])


def compact_day(day: dict) -> dict:
    return dict(persona_id=day["persona_id"], steps=[compact_step(s) for s in day["steps"]], events=day["events"],
                party_total_out_of_pocket_krw=day["party_total_out_of_pocket_krw"], traits_sha=day["traits_sha"], world_sha=day["world_sha"], model_calls=0)


def grid_key(price, disc, food, qual, pkg, nonalc) -> str:
    return f"{price}|{disc}|{food}|{qual}|{int(pkg)}|{int(nonalc)}"


_TRAITS: dict = {}


def _grid_cell(job):
    p, (price, disc, food, qual, pkg, nonalc) = job
    if p not in _TRAITS:
        _TRAITS[p] = PA.traits_for(ENTRY[p]["persona_id"])
    world = WD.default_world()
    visit = WD.default_visit(ENTRY[p]["persona_id"], ENTRY[p]["visit"])
    lv = {"WINE_FAIR": dict(price_pp_krw=price, guest_discount_krw=disc, food_level=food, quality=qual, in_package=pkg, nonalcoholic_alt=nonalc,
                            **(GRID_MENU_CHEF.get(food, GRID_MENU[food]) if qual == "chef_collab" else GRID_MENU[food]))}
    r = EN.run(_TRAITS[p], visit, world, lv)
    steps = r["day"]["steps"]
    ev = next((s for s in steps if s["chosen"] == "WINE_FAIR" and s.get("action") != "browse"), None)   # 4차: 들러보기는 참여가 아님
    best_view = None
    if ev is None:
        views = [v for s in steps for v in s["event_stages"] if v["offer"] == "WINE_FAIR" and v["stage"] != "참여 불가"]
        if views:
            best_view = min(views, key=lambda v: v["gap"])
    ev_step = ev or (next((s for s in steps if any(v["offer"] == "WINE_FAIR" and v is best_view for v in s["event_stages"])), None) if best_view else None)
    ev_terms = []
    if ev_step:
        if ev:
            ev_terms = [dict(text=x["text"], value=x["value"], layer=x["layer"], n_evidence=len(x["evidence"])) for x in ev["reasons"][:5]]
        else:
            rj = next((x for x in ev_step["rejected"] if x["offer"] == "WINE_FAIR"), None)
            ev_terms = [dict(text=f"선택한 {ev_step['label']} 대비 가장 뒤진 항: {rj['major_reason']}", value=None, evidence=[], layer="비교")] if rj else []
    return dict(sequence=[dict(t=s["starts"], a=s["chosen"], st=s["stage"], x=s.get("action")) for s in steps],
                event=r["day"]["events"][0], cost=r["day"]["party_total_out_of_pocket_krw"], event_reasons=ev_terms,
                flips=r["flip_conditions"], event_time=(ev["starts"] if ev else None))


def build(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    traits = {p: PA.traits_for(ENTRY[p]["persona_id"]) for p in PERSONAS}
    world = WD.default_world()
    results = {}
    for p in PERSONAS:
        visit = WD.default_visit(ENTRY[p]["persona_id"], ENTRY[p]["visit"])
        base = EN.run(traits[p], visit, world, {})
        results[p] = {}
        for pr in PRESETS:
            r = EN.run(traits[p], visit, world, pr["levers"])
            results[p][pr["id"]] = dict(day=compact_day(r["day"]), flip_conditions=r["flip_conditions"], compare_to_base=EN.compare(base["day"], r["day"]),
                                        offer=next(o for o in r["world"]["offers"] if o["id"] == "WINE_FAIR"))
    authors = sorted({e["persona_id"] for e in ENTRIES})
    presets = dict(version=EN.VERSION, presets=PRESETS, entries=ENTRIES, authors=authors, results=results,
                   headline=f"작성자 {len(authors)}명 · 방문 조건 {len(ENTRIES)}개",
                   computation=f"이 화면은 Python 엔진이 미리 계산한 {len(PRESETS)}개 시나리오(상세)와 1,440개 조합(요약)을 조회한다 · 브라우저가 엔진을 다시 실행하지는 않음",
                   visit={p: WD.default_visit(ENTRY[p]["persona_id"], ENTRY[p]["visit"]) for p in PERSONAS}, world=world,
                   policy=dict(weights=EN.W, cost_attention=EN.COST_ATTENTION, cost_unit=EN.COST_UNIT, consider_margin=EN.CONSIDER_MARGIN,
                               interest_margin=EN.INTEREST_MARGIN, notes=EN.POLICY_NOTES,
                               common=dict(EN.POLICY, lookahead_w=EN.LOOKAHEAD_W),
                               common_ko=["같은 원문 사실이 한 선택지의 여러 성향 항에 쓰이면 그 사실은 합쳐서 한 몫(1/n)만 기여 — 사실 단위 근거에만 적용",
                                          "선택은 '지금 + 바로 다음 한 단계' 합계로 비교 — 행사 대 (식사 → 행사) · (식사 → 야경) 같은 저녁 보내는 방법 전체를 공정하게 비교",
                                          "식사 선택지는 시작 60분 전부터 후보(기다리는 시간은 비용)",
                                          "남은 끼니보다 많이 먹는 음식은 0.3만 음식 경험으로 인정(저녁 두 번 먹는 하루 방지)",
                                          "4차: 메뉴 기호 · 셰프 코스의 음식 가치도 남은 끼니만큼만(체험 가치는 그대로)",
                                          "4차 · 5차: '입장 전 안내 확인'(가상 행동 · 15분 · 무료)은 입장이 아님 → 현장에서 실제로 공개된 정보만 새로 알게 됨(메뉴는 현장 게시 근거가 없어 기본은 새 정보 없음) → 다시 판단 → 입장할 때만 입장권 지출",
                                          "5차: 와인페어 기본 시간은 공식 2부 15:30~20:00 · 17:00~21:00은 가상 운영 변경안(⑧)",
                                          "5차: 남은 배고픔을 넘는 음식은 보상하지 않음(배부르면 한 접시의 0.3만) · 저녁 전에 먹은 음식도 저녁 배고픔을 줄이고, 17:00 뒤에 끝나는 식사는 이른 저녁으로 인정",
                                          "5차: 야경은 활동이 일몰(가정 18:00) 뒤까지 이어질 때만",
                                          "5차: 포레스트 파크에서 행사가 열리는 날에는 포레스트 파크 산책 불가(공식 공지)",
                                          "4차: 식당별로 실제 제공하는 음식 경험의 근거만(뷔페 탐색 → 뷔페 · 코스 → 3단 이상 코스) · 객실 식사는 음식 성향 근거 없음",
                                          "4차: 다음 계획도 실제 판단과 같은 방식(한 단계 더)으로 골라, 계획과 다음 실제 선택이 어긋나지 않게(lookahead_depth 2)",
                                          "4차: 기본 월드에는 공식 확인값만 — 피자힐 투숙객 할인(후기값)은 운영 조건으로만"]),
                   model_calls=0, human_review="pending", demo_approved=False)
    grid = {p: {} for p in PERSONAS}
    jobs = [(p, combo) for p in PERSONAS for combo in itertools.product(*GRID.values())]
    import multiprocessing as mp, os
    n = max(1, min(os.cpu_count() or 1, 8))
    if n > 1:
        with mp.get_context("fork").Pool(n) as pool:
            cells = pool.map(_grid_cell, jobs, chunksize=8)
    else:
        cells = [_grid_cell(j) for j in jobs]
    for (p, combo), cell in zip(jobs, cells):
        grid[p][grid_key(*combo)] = cell
    grid_doc = dict(version=EN.VERSION, axes=GRID, menu_by_food=GRID_MENU, menu_chef=GRID_MENU_CHEF, grid=grid, model_calls=0)
    traits_doc = {p: dict(entry=ENTRY[p], persona_id=ENTRY[p]["persona_id"], facets={k: dict(v, label=v.get("label") or PATTERN_KO.get(k, k)) for k, v in t["facets"].items()},
                          menu=t["menu"], venues=t["venues"], evidence_index=t["evidence_index"], source_post_count=t["source_post_count"],
                          active_fact_count=t["active_fact_count"], assumptions=t["assumptions"], counterexamples=t.get("counterexamples", []),
                          profile_version=t["profile_version"], profile_status=t.get("profile_status"), relevance_audit=t.get("relevance_audit", []),
                          human_review=t["human_review"], demo_approved=False)
                  for p, t in traits.items()}
    files = {"presets.json": presets, "grid.json": grid_doc, "traits.json": traits_doc}
    written = {}
    for name, doc in files.items():
        text = json.dumps(doc, ensure_ascii=False, indent=(None if name == "grid.json" else 1), sort_keys=True, separators=((",", ":") if name == "grid.json" else None))
        path = out / name
        if path.exists() and path.read_text(encoding="utf-8") != text:
            raise SystemExit(f"refuse_overwrite_different_content:{path}")
        path.write_text(text, encoding="utf-8")
        written[name] = hashlib.sha256(text.encode()).hexdigest()[:16]
    manifest = dict(version=EN.VERSION, files=written, personas=list(PERSONAS), presets=[p["id"] for p in PRESETS],
                    grid_cells=sum(len(g) for g in grid.values()), model_calls=0, human_review="pending", demo_approved=False,
                    profile_source="author_method_v4_1_artifacts/profiles_and_quality.json (scope recent_added)",
                    note="모든 운영 조건은 연구용 가상값 · 행동은 규칙 엔진 계산 결과이지 실제 고객 행동 · 예측 확률이 아님")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "import-v42"]); ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--in", dest="in_dir", default=None, help="import-v42: V4.2 팀 프로파일 JSON 폴더")
    a = ap.parse_args()
    if a.cmd == "import-v42":
        from .v42_batch import run_batch
        if not a.in_dir or a.out == str(OUT):
            raise SystemExit("import-v42 는 --in <폴더> 와 별도 --out <폴더> 가 필요합니다(기존 산출물 보호)")
        print(json.dumps(run_batch(Path(a.in_dir), Path(a.out), PRESETS), ensure_ascii=False, indent=1))
        return
    m = build(Path(a.out))
    print(json.dumps(m, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
