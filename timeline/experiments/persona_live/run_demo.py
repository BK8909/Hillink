"""시연용 — 카드 v1 선정 10팀을 같은 날 같은 워커힐에 투입 (10/20 · 총괄 C)

  python3 run_demo.py            # 10명 × 조건 D0 한 번 → runs/demo_1/<blog>/D0_r0.json
  python3 run_demo.py --dry --only blog58

조건 D0: 2026-10-24(토) 1박 · 가을 축제 '폴 인 워커힐' · 와인페어 날 · 참고 정보(외부) 포함.
건물은 카드의 지난 방문 건물을 따른다. 지난번에 투숙하지 않은 팀(0박)은 '이번엔 1박 투숙' 을 가상 조건으로 적는다.
한 명 한 번. 반복 비율 · 확률은 만들지 않는다. 깊은 검수는 blog25(persona_live 초점 사례)에서 하고, 여기서는 서로 다른 열 명이 같은 무대에서 각자 다르게 고르는지를 본다.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ask, stage as ST                      # noqa: E402
from persona_sheet import build_sheet, load_cards   # noqa: E402
from run_live import EXT_FALL                # noqa: E402

PLAN = "demo_1"
D0 = dict(name="가을 주말(10/24 토) · 폴 인 워커힐 · 와인페어 날", date="2026-10-24", mods=dict(external=EXT_FALL))


def cell(blog: str, dry: bool = False) -> dict | None:
    cards = load_cards(); sheet = build_sheet(cards[blog])
    mods = dict(D0["mods"])
    if not sheet["nights"]:
        mods["extra_note"] = "지난번에는 투숙하지 않고 식사 · 방문만 했지만, 이번에는 1박 투숙한다"
    st = ST.build_stage(D0["date"], sheet["property"], sheet["has_children"], mods)
    stage_text = ST.render(st)
    if dry:
        print(ask.user_prompt(sheet["text"], stage_text, ST.SLOTS)); return None
    out = HERE / "runs" / PLAN / blog; out.mkdir(parents=True, exist_ok=True)
    f = out / "D0_r0.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    r = ask.ask_persona(sheet["text"], stage_text, ST.SLOTS)
    rec = dict(plan=PLAN, blog=blog, condition="D0", condition_name=D0["name"], rep=0, virtual=True, date=D0["date"], modifiers=mods,
               sheet=sheet["text"], sheet_evidence_ids=sheet["evidence_ids"], party=sheet["party"], property=sheet["property"], nights=sheet["nights"],
               stage=st, stage_text=stage_text, **r)
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{blog} D0] ${r['cost_usd']:.3f} {r['duration_s']}s · " + " / ".join(x["option_code"] for x in r["output"]["decisions"]))
    return rec


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); ap.add_argument("--dry", action="store_true"); a = ap.parse_args()
    blogs = [a.only] if a.only else [b for b, c in load_cards().items() if c.get("selection_status") == "selected"]
    total = 0.0
    for b in blogs:
        rec = cell(b, a.dry)
        if rec: total += rec.get("cost_usd") or 0
    if not a.dry: print(f"합계 비용 ${total:.2f}")


if __name__ == "__main__":
    main()
