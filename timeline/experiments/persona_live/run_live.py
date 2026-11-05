"""페르소나 한 명이 새 상황에서 고르는가 — 최소 실행 사례 (10/20 · 총괄 C · 격리)

  python3 run_live.py                       # 초점 1명 × 조건 7 + 대조 2명 × 조건 2~3 → runs/live_1/<blog>/<cond>_r0.json (한 칸 한 번)
  python3 run_live.py --only blog25:A0      # 한 칸만
  python3 run_live.py --dry --only blog25:A0  # 프롬프트만 출력(호출 없음)
  python3 run_live.py --followup blog25:A0 "질문"   # 저장된 계획을 두고 후속 질문

조건(모두 가상 날짜 — 후기의 실제 방문일이 아니다)
  A0 여름 주말 8/22(토) · 리버파크 골드 시즌 · 빛의 시어터 휴관
  A1 A0 + 비 [가상 조건]
  A2 A0 + 리버파크 요금 2배 [가상 조건]
  A3 A0 + 동행 변경(아이 없이 부부만) [가상 조건]
  A4 A0 + 아이들이 물놀이를 무서워함 [가상 조건]
  A5 A0 + 리버파크 가족 합계 약 20만 원 [가상 조건] — A0 후속 질문에서 페르소나가 스스로 말한 조건
  B0 가을 와인페어 주말 10/10(토) · 폴 인 워커힐 · 참고 정보(외부) 포함
  B1 B0 + [가상] 더뷔페 '가을 창가 조망 디너' 안내(persona_market 아이디어를 선택지로)
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ask, stage as ST                      # noqa: E402
from persona_sheet import build_sheet, load_cards   # noqa: E402

PLAN = "live_1"
FOCUS = "blog25"                                   # 깊게 보는 한 명(아이 둘 동반 가족)
CONTRAST = ["blog43", "blog36"]                    # 대조: 혼자 조용한 휴식 · 성인 가족(바 · 와인 이용 관측)
EXT_FALL = ["네이버 검색량(저장소 집계): 워커힐 뷔페 검색은 2023~2025년 모두 10월 말~11월 중순에 10월 초중순보다 높았다(과거 계절성 · 방문 수치 아님)",
            "보도(9/14): 2026 가을 축제 '폴 인 워커힐' 9/21~10/31 · 와인페어 '구름 위의 산책' 주말 6회 · SNS 인증샷 이벤트 경품에 더뷔페 식사권"]
CONDITIONS = {
    "A0": dict(name="여름 주말(8/22 토) · 리버파크 운영", date="2026-08-22", mods={}, who=[FOCUS] + CONTRAST),
    "A1": dict(name="여름 주말 + 비", date="2026-08-22", mods=dict(weather="비"), who=[FOCUS]),
    "A2": dict(name="여름 주말 + 리버파크 요금 2배", date="2026-08-22", mods=dict(riverpark_price_mult=2), who=[FOCUS]),
    "A3": dict(name="여름 주말 + 아이 없이 부부만", date="2026-08-22", mods=dict(companions_override="이번엔 아이들 없이 부부 둘만(아이들은 조부모 댁) — 시트의 가족 구성은 그대로지만 이번 방문 동행만 다르다"), who=[FOCUS]),
    "A4": dict(name="여름 주말 + 아이들이 물놀이를 무서워함", date="2026-08-22", mods=dict(extra_note="이번 방문에서 아이들이 물에 들어가는 것을 무서워한다(최근 물놀이에서 겁을 먹음)"), who=[FOCUS]),
    "A5": dict(name="여름 주말 + 리버파크 가족 4인 합계 약 20만 원(페르소나가 스스로 말한 조건)", date="2026-08-22", mods=dict(riverpark_price_mult=0.625, riverpark_price_note="가족 4인(성인 2 · 어린이 2) 합계 약 200,000원이 되는 요금 — 성인 59,375원 · 어린이 40,625원"), who=[FOCUS]),
    "B0": dict(name="가을 와인페어 주말(10/10 토)", date="2026-10-10", mods=dict(external=EXT_FALL), who=[FOCUS] + CONTRAST),
    "B1": dict(name="가을 와인페어 주말 + [가상] 더뷔페 가을 창가 디너 안내", date="2026-10-10", mods=dict(external=EXT_FALL, virtual=["buffet_fall_window"]), who=[FOCUS, "blog36"]),
}
REPS = 1                                           # 반복 비율을 만들지 않는다 — 한 칸 한 번, 사람이 읽고 검수한다


def cell(blog: str, cond: str, rep: int, dry: bool = False) -> dict | None:
    cards = load_cards(); c = CONDITIONS[cond]
    sheet = build_sheet(cards[blog])
    kids = sheet["has_children"] and not c["mods"].get("companions_override")
    st = ST.build_stage(c["date"], sheet["property"], kids, c["mods"])
    stage_text = ST.render(st)
    if dry:
        print(ask.SYSTEM, "\n\n-----\n", ask.user_prompt(sheet["text"], stage_text, ST.SLOTS)); return None
    out = HERE / "runs" / PLAN / blog; out.mkdir(parents=True, exist_ok=True)
    f = out / f"{cond}_r{rep}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    r = ask.ask_persona(sheet["text"], stage_text, ST.SLOTS)
    rec = dict(plan=PLAN, blog=blog, condition=cond, condition_name=c["name"], rep=rep, virtual=True, date=c["date"], modifiers=c["mods"],
               sheet=sheet["text"], sheet_evidence_ids=sheet["evidence_ids"], stage=st, stage_text=stage_text, **r)
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    d = r["output"]
    print(f"[{blog} {cond} r{rep}] ${r['cost_usd']:.3f} {r['duration_s']}s · " + " / ".join(f"{x['slot'][:6]}→{x['option_code']}" for x in d["decisions"]))
    return rec


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--only"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--followup", nargs=2, metavar=("BLOG:COND", "QUESTION"))
    a = ap.parse_args()
    if a.followup:
        key, q = a.followup; blog, cond = key.split(":")
        rec = json.loads((HERE / "runs" / PLAN / blog / f"{cond}_r0.json").read_text(encoding="utf-8"))
        r = ask.ask_followup(rec["sheet"], rec["stage_text"], rec["output"], q)
        fo = HERE / "runs" / PLAN / blog / f"{cond}_followup.json"
        prev = json.loads(fo.read_text(encoding="utf-8")) if fo.exists() else []
        prev.append(dict(question=q, **r)); fo.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(r["output"], ensure_ascii=False, indent=1)); return
    cells = [(b, c) for c in CONDITIONS for b in CONDITIONS[c]["who"]]
    if a.only:
        b, c = a.only.split(":"); cells = [(b, c)]
    total = 0.0
    for b, c in cells:
        for k in range(1 if a.dry else a.reps):
            rec = cell(b, c, k, a.dry)
            if rec: total += rec.get("cost_usd") or 0
    if not a.dry: print(f"합계 비용 ${total:.2f}")


if __name__ == "__main__":
    main()
