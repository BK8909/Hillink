"""페르소나 시뮬레이터 화면 생성 — 지도 중심 한 화면 (10/20 · 총괄 C)

  python3 build_sim.py      # runs/demo_1 · runs/live_1/blog25 → demo/persona_sim.html (외부 스크립트 없음 · 지도 그림은 viewer/static/map_base.png 참조)

화면의 숫자 · 시각 · 이유는 모두 실행 기록(runs/*_r0.json · *_visit.json)에서 온다. 확률 · 참여율 · 혼잡은 없다.
지도 좌표 · 길은 viewer/static/map.js 에서 떼어 낸 demo/map_core.js(DOM 없음)를, 드로어 · 이름표는 viewer/static/app.js 에서 떼어 낸 demo/hillink_ui.js 를 그대로 넣는다.
화면 스타일은 viewer/static/style.css 를 그대로 링크한다(새 디자인 없음 · 10/21 v3).
"""
from __future__ import annotations

import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import itinerary as IT, library as LIBM, make_case, run_demo, run_live   # noqa: E402
from persona_sheet import COMP, PURPOSE, load_cards   # noqa: E402

DEMO = HERE / "demo"
CAT = {"THE_BUFFET": "식음", "PIZZA_HILL": "식음", "MYONGWOLGWAN": "식음", "ONDAL": "식음", "GEUMRYONG": "식음", "MOEGI": "식음", "THE_PAVILION": "식음", "LE_PASSAGE": "식음", "LUX_BAR": "식음", "DOUGLAS_LOUNGE": "식음",
       "GRAND_POOL": "시설", "VISTA_POOL": "시설", "RIVERPARK": "시설", "THEATRE_OF_LIGHT": "시설", "SKYARD": "시설", "FITNESS": "시설", "FOREST_PARK": "시설"}


def slim_run(rec: dict) -> dict:
    names = {o["code"]: o["name"] for o in rec["stage"]["options"]}
    out = rec["output"]
    return dict(plan=rec["plan"], blog=rec["blog"], cond=rec["condition"], cond_name=rec["condition_name"], date=rec["date"], head=rec["stage"]["head"], notes=rec["stage"]["notes"],
                external=rec["stage"].get("external", []), sheet=rec["sheet"], self_intro=out["self_intro"], quote=out["one_line_quote"], would_change=out["would_change_if"], unknowns=out["unknowns_that_mattered"],
                flags=make_case.honesty_flags(rec), cost=rec["cost_usd"], model=rec["model"], branch_of=rec.get("branch_of"), event=rec.get("event"), later=(rec.get("event_call") or {}).get("later_plan"),
                options=[dict(code=o["code"], name=o["name"], slot=o["slot"], text=o["text"], price=o["price"], grade=o["grade"], source=o["source"], virtual=o.get("virtual", False)) for o in rec["stage"]["options"]],
                decisions=[dict(slot=d["slot"], code=d["option_code"], name=names.get(d["option_code"], d["option_code"]), choice=d["choice"], virtual=d.get("is_virtual_option", False), cost=d.get("est_cost_krw"),
                                reasons=d["reasons"], main=d["main_driver"], ids=d.get("evidence_ids", []), conf=d["confidence"], decided_by=d.get("decided_by", "llm_plan"),
                                alts=[dict(code=a["option_code"], name=names.get(a["option_code"], a["option_code"]), why=a["why_not"]) for a in d["alternatives"]]) for d in out["decisions"]])


def visit_of(f: Path, rec: dict) -> dict:
    vf = f.with_name(f.name.replace("_r0.json", "_visit.json"))
    v = json.loads(vf.read_text(encoding="utf-8")) if vf.exists() else IT.build_visit(rec)
    for a in v["activities"]:
        a["cat"] = CAT.get(a["place"], "기타") if a["kind"] == "core" and a.get("cost") else None
    return v


def followups(f: Path) -> list:
    fo = f.with_name(f.name.replace("_r0.json", "_followup.json"))
    return [dict(q=x["question"], a=x["output"]["answer"], drivers=x["output"]["drivers"]) for x in json.loads(fo.read_text(encoding="utf-8"))] if fo.exists() else []


def main():
    cards = load_cards(); people = {}
    for b, c in cards.items():
        if c.get("selection_status") != "selected": continue
        a = c["a_card"]; party = a["party"]["composition"].get("value")
        runs = {}
        for f in sorted((HERE / "runs" / run_demo.PLAN / b).glob("*_r0.json")) + (sorted((HERE / "runs" / run_live.PLAN / b).glob("*_r0.json")) if b == run_live.FOCUS else []):
            rec = json.loads(f.read_text(encoding="utf-8")); key = f"{rec['plan']}:{rec['condition']}"
            runs[key] = dict(run=slim_run(rec), visit=visit_of(f, rec), followups=followups(f))
        if not runs: continue
        ov = a["observed_visit"]
        people[b] = dict(blog=b, label=COMP.get(party, party or "구성 미상"), purpose=" · ".join(PURPOSE.get(v, v) for v in a["purpose"].get("value") or []), property=ov.get("property"),
                         nights_before=ov.get("nights"), runs=runs, default=f"{run_demo.PLAN}:D0")
    # 결정 D6 (10/21) — 기본 시연에는 기본 계획 + 10명 공통 검증(verify10)에서 쓴 가지만. 나머지 실험 · QA 가지는 '실험 기록 보기' 에서만
    vf = HERE / "review" / "verify10_20261021.json"; vlog = json.loads(vf.read_text(encoding="utf-8")) if vf.exists() else {}
    for b, p in people.items():
        shown = {p["default"]} | {x["key"] for k, x in vlog.get(b, {}).items() if isinstance(x, dict) and "key" in x}
        for k, e in p["runs"].items():
            e["show"] = k in shown; e["verify"] = next((t for t, x in vlog.get(b, {}).items() if isinstance(x, dict) and x.get("key") == k), None)
    lib = LIBM.build(); (DEMO / "library.json").write_text(json.dumps(lib, ensure_ascii=False, indent=1), encoding="utf-8")
    data = dict(d0=dict(name=run_demo.D0["name"], date=run_demo.D0["date"]), focus=run_live.FOCUS, people=people, library=lib,
                legend=dict(llm_plan="판단(LLM 계획)", code_link="연결(코드)", llm_event="사건 재판단(LLM)", operator="운영자 개입"),
                total_cost=round(sum(r["run"]["cost"] for p in people.values() for r in p["runs"].values()), 2))
    html = (DEMO / "sim_template.html").read_text(encoding="utf-8")
    core = (DEMO / "map_core.js").read_text(encoding="utf-8"); ui = (DEMO / "hillink_ui.js").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    (DEMO / "persona_sim.html").write_text(html.replace("/*__DATA__*/null", payload).replace("/*__MAP_CORE__*/", core).replace("/*__HILLINK_UI__*/", ui), encoding="utf-8")
    print(f"demo/persona_sim.html · 사람 {len(people)} · 실행 {sum(len(p['runs']) for p in people.values())} · 데이터 {len(payload):,} bytes")


if __name__ == "__main__":
    main()
