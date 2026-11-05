"""시연 화면 생성 — 10명 같은 무대 + blog25 깊은 사례 + 고객에게 질문 (10/20 · 총괄 C)

  python3 build_demo.py      # runs/demo_1 · runs/live_1/blog25 → demo/persona_demo.html (외부 스크립트 없는 단일 파일)

화면 숫자는 모두 실행 기록(runs/)에서 온다. 확률 · 참여율 · 반복 비율은 없다. 실시간 질문은 serve_demo.py 가 떠 있을 때만, 아니면 저장된 질의응답만 보여 준다.
"""
from __future__ import annotations

import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_case, run_demo, run_live   # noqa: E402
from persona_sheet import COMP, PURPOSE, load_cards   # noqa: E402

DEMO = HERE / "demo"


def slim(rec: dict) -> dict:
    names = {o["code"]: o["name"] for o in rec["stage"]["options"]}
    names.update({v["name"].split("] ")[-1]: v["name"] for v in []})
    out = rec["output"]
    return dict(plan=rec["plan"], blog=rec["blog"], cond=rec["condition"], cond_name=rec["condition_name"], date=rec["date"], head=rec["stage"]["head"],
                notes=rec["stage"]["notes"], external=rec["stage"].get("external", []), sheet=rec["sheet"], self_intro=out["self_intro"], quote=out["one_line_quote"],
                would_change=out["would_change_if"], unknowns=out["unknowns_that_mattered"], flags=make_case.honesty_flags(rec), cost=rec["cost_usd"], model=rec["model"],
                decisions=[dict(slot=d["slot"], code=d["option_code"], name=names.get(d["option_code"], d["option_code"]), choice=d["choice"], virtual=d["is_virtual_option"],
                                cost=d.get("est_cost_krw"), reasons=d["reasons"], main=d["main_driver"], ids=d.get("evidence_ids", []), conf=d["confidence"],
                                alts=[dict(code=a["option_code"], name=names.get(a["option_code"], a["option_code"]), why=a["why_not"]) for a in d["alternatives"]]) for d in out["decisions"]])


def followups(plan: str, blog: str, cond: str) -> list:
    f = HERE / "runs" / plan / blog / f"{cond}_followup.json"
    return [dict(q=x["question"], a=x["output"]["answer"], drivers=x["output"]["drivers"]) for x in json.loads(f.read_text(encoding="utf-8"))] if f.exists() else []


def main():
    cards = load_cards()
    people = []
    for b, c in cards.items():
        f = HERE / "runs" / run_demo.PLAN / b / "D0_r0.json"
        if c.get("selection_status") != "selected" or not f.exists(): continue
        rec = json.loads(f.read_text(encoding="utf-8")); a = c["a_card"]
        party = a["party"]["composition"].get("value")
        people.append(dict(blog=b, label=COMP.get(party, party or "구성 미상"), purpose=" · ".join(PURPOSE.get(v, v) for v in a["purpose"].get("value") or []),
                           property=rec["property"], nights_before=rec["nights"], run=slim(rec), followups=followups(run_demo.PLAN, b, "D0")))
    focus = run_live.FOCUS
    deep = []
    for cond in run_live.CONDITIONS:
        f = HERE / "runs" / run_live.PLAN / focus / f"{cond}_r0.json"
        if f.exists():
            deep.append(dict(run=slim(json.loads(f.read_text(encoding="utf-8"))), followups=followups(run_live.PLAN, focus, cond)))
    data = dict(d0=dict(name=run_demo.D0["name"], date=run_demo.D0["date"]), people=people, focus=focus, deep=deep,
                total_cost=round(sum(p["run"]["cost"] for p in people) + sum(d["run"]["cost"] for d in deep), 2))
    html = (DEMO / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    (DEMO / "persona_demo.html").write_text(html.replace("/*__DATA__*/null", payload), encoding="utf-8")
    print(f"demo/persona_demo.html · 사람 {len(people)} · 깊은 사례 {len(deep)}조건 · 데이터 {len(payload):,} bytes")


if __name__ == "__main__":
    main()
