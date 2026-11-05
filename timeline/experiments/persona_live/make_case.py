"""교차검수용 사례 문서 — runs/ 의 결과를 사람이 읽는 '행동 이야기 + 근거 사슬 + 검수 칸' 으로 (10/20 · 총괄 C)

  python3 make_case.py            # → review/CASE_blog25.md (초점 1명 · 조건별) · review/CONTRAST.md (대조 2명) · review/review_sheet.csv (검수 칸)

정확도 · 반복 비율 · 확률은 만들지 않는다. 자동으로 하는 점검은 하나뿐이다 —
'개인 기억' 이유에 시트에 없는 장소 · 근거 ID 가 들어갔는지, 아이 나이 · 절약 성향처럼 시트에 없는 구체적 사실을 만들었는지(근거의 정직성 · 사람 검수자가 볼 자리 표시).
"""
from __future__ import annotations

import csv, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_live as RL      # noqa: E402
from persona_sheet import PLACE   # noqa: E402

LAYER = {"personal_memory": "개인의 실제 경험", "general_sense": "일반적인 행동 지식", "current_conditions": "현재 환경", "external_info": "외부 참고 정보"}
PLACE_WORDS = {"리버파크": "RIVERPARK", "실내 수영장": "GRAND_POOL", "포레스트 파크": "FOREST_PARK", "빛의 시어터": "THEATRE_OF_LIGHT", "스카이야드": "SKYARD", "더뷔페": "THE_BUFFET", "피자힐": "PIZZA_HILL",
               "명월관": "MYONGWOLGWAN", "온달": "ONDAL", "금룡": "GEUMRYONG", "모에기": "MOEGI", "파빌리온": "THE_PAVILION", "르파사쥬": "LE_PASSAGE", "럭스 바": "LUX_BAR", "럭스바": "LUX_BAR", "더글라스 라운지": "DOUGLAS_LOUNGE", "클럽 라운지": "GRAND_CLUB_LOUNGE", "와인페어": "WINE_FAIR"}


def load(blog: str, cond: str) -> dict | None:
    f = HERE / "runs" / RL.PLAN / blog / f"{cond}_r0.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def honesty_flags(rec: dict) -> list[str]:
    """'개인 기억' 이유에 시트에 없는 장소 이름이 '지난번' 맥락으로 나오면 표시 — 판정은 사람이"""
    sheet = rec["sheet"]; flags = []
    for d in rec["output"]["decisions"]:
        pm = d["reasons"]["personal_memory"]
        for sent in re.split(r"(?<=[.다요])\s+", pm):
            for w in PLACE_WORDS:
                if w in sent and w not in sheet and re.search(r"지난|전에|그때|이용했|즐겼|좋아했", sent) and not re.search(r"없|않|아니|못", sent):
                    flags.append(f"{d['slot']}: 개인 기억 이유에 시트에 없는 '{w}' 를 경험처럼 언급 — 검수자 확인")
        for i in d.get("evidence_ids", []):
            if i not in sheet:
                flags.append(f"{d['slot']}: 근거 ID '{i}' 가 시트에 없음")
        text = pm + " " + rec["output"].get("self_intro", "")
        if re.search(r"\d+\s*살|\d+\s*세(?!금)|여덟 살|일곱 살|여섯 살|다섯 살", text):
            flags.append(f"{d['slot']}: 시트에 없는 구체적 나이를 적음")
        if re.search(r"아끼는 편|절약|알뜰한 사람|원래 .{0,6}좋아", pm):
            flags.append(f"{d['slot']}: 시트에 없는 성격 · 취향을 개인 기억처럼 적음")
    return flags


def story(rec: dict) -> str:
    o = rec["output"]; c = RL.CONDITIONS[rec["condition"]]
    L = [f"### {rec['condition']} · {c['name']}", "", f"**상황** {rec['stage']['head'].replace(chr(10), ' / ')}"]
    for n in rec["stage"]["notes"]:
        if "[가상 조건]" in n: L.append(f"**추가 조건** {n}")
    L += ["", f"**자기소개** {o['self_intro']}", "", "**행동 이야기**", ""]
    for d in o["decisions"]:
        v = " [가상 선택지]" if d["is_virtual_option"] else ""
        cost = f" · 어림 비용 {d['est_cost_krw']:,}원" if d.get("est_cost_krw") else ""
        ev = f" · 근거 ID {', '.join(d['evidence_ids'])}" if d.get("evidence_ids") else " · 개인 기억 근거 없음(일반 판단)"
        L.append(f"- **{d['slot']}** → {d['choice']}{v} (`{d['option_code']}`{cost} · 확신 {d['confidence']}{ev})")
    L += ["", "**근거 사슬** (주재료 ★)", "", "| 시간대 | 개인의 실제 경험 | 일반적인 행동 지식 | 현재 환경 | 외부 참고 |", "|---|---|---|---|---|"]
    for d in o["decisions"]:
        r = d["reasons"]
        cells = [(k, r.get(k, "") or "—") for k in ("personal_memory", "general_sense", "current_conditions", "external_info")]
        L.append(f"| {d['slot']} | " + " | ".join(("★ " if k == d["main_driver"] else "") + v.replace("|", "／") for k, v in cells) + " |")
    L += ["", "**버린 대안**", ""]
    for d in o["decisions"]:
        if d["alternatives"]:
            L.append(f"- {d['slot']}: " + " / ".join(f"`{a['option_code']}` — {a['why_not']}" for a in d["alternatives"]))
    L += ["", "**무엇이 달라지면 바뀌는가** " + " · ".join(o["would_change_if"]), "", "**모른 채 판단한 것** " + " · ".join(o["unknowns_that_mattered"]), "",
          f"**한마디** “{o['one_line_quote']}”", ""]
    fl = honesty_flags(rec)
    L.append("**자동 점검(근거의 정직성)** " + ("; ".join(fl) if fl else "개인 기억 이유에 시트 밖 장소 언급 없음"))
    L += ["", f"실행: 모델 {rec['model']} · 프롬프트 지문 `{rec['prompt_sha256']}` · 비용 ${rec['cost_usd']:.3f} · 파일 `runs/{RL.PLAN}/{rec['blog']}/{rec['condition']}_r0.json`", ""]
    return "\n".join(L)


def review_block() -> str:
    return "\n".join(["**검수** (강경수 · 한호님 독립 기입 — review/review_sheet.csv)", "",
                      "| 항목 | 질문 | 강경수 | 한호님 | 갈린 지점 |", "|---|---|---|---|---|",
                      "| 개연성 | 실제 그 블로그의 사람이라면 충분히 할 법한가 | | | |",
                      "| 일관성 | 과거 경험 · 방문 목적 · 동행 구성과 모순되지 않는가 | | | |",
                      "| 상황 대응 | 가격 · 계절 · 동행 · 선택지가 바뀌면 적절히 반응하는가 | | | |",
                      "| 근거의 정직성 | 없던 취향을 만들거나 결론에 이유를 끼워 맞추지 않았는가 | | | |", ""])


def matrix(blog: str, conds: list[str]) -> str:
    recs = [(c, load(blog, c)) for c in conds]; recs = [(c, r) for c, r in recs if r]
    slots = recs[0][1]["output"]["decisions"]
    L = ["| 시간대 | " + " | ".join(f"{c} {RL.CONDITIONS[c]['name']}" for c, _ in recs) + " |", "|---|" + "---|" * len(recs)]
    for i, d in enumerate(slots):
        L.append(f"| {d['slot']} | " + " | ".join(f"`{r['output']['decisions'][i]['option_code']}`" + (" ★" if r["output"]["decisions"][i]["main_driver"] == "personal_memory" else "") for _, r in recs) + " |")
    return "\n".join(L)


def main():
    out = HERE / "review"; out.mkdir(exist_ok=True)
    focus = RL.FOCUS
    conds = [c for c in RL.CONDITIONS if focus in RL.CONDITIONS[c]["who"]]
    recs = {c: load(focus, c) for c in conds}
    base = recs.get("A0")
    L = [f"# 사례 — {focus} 페르소나가 새 상황에서 고르는가 (교차검수용 · 10/20)", "",
         "이 문서는 한 명의 페르소나(고객 카드 v1 · 블로그 원문 없음)를 가상 날짜의 워커힐에 넣고, 무엇을 고르고 왜 골랐는지를 사람이 읽고 검수하기 위한 것이다.",
         "모든 조건은 가상이며 실제 방문일이 아니다. 결과는 미래 행동의 예측이 아니라 '이 사람이라면 이렇게 할 법하다'는 조건부 판단이다. 정확도 · 반복 비율 · 확률은 만들지 않았다.", "",
         "## 페르소나 시트(모델이 본 것 전부)", "", base["sheet"] if base else "", "",
         "## 조건별 선택 한눈에 (★ = 개인 기억이 주재료)", "", matrix(focus, conds), "",
         "읽는 법: 열이 바뀔 때 행이 바뀌면 '상황 대응', 바뀌지 않으면 그 선택이 상황과 무관하게 이 사람다운 것인지 검수자가 본다.", "",
         "이번 방문 조건은 모든 열에서 같다: " + (base["stage"]["head"].split("[이번 방문 조건] ")[1].split("\n")[0] if base else ""), ""]
    for c in conds:
        if recs[c]:
            L += ["---", "", story(recs[c]), review_block()]
    fo = HERE / "runs" / RL.PLAN / focus / "A0_followup.json"
    if fo.exists():
        L += ["---", "", "## 후속 질문 — 행동을 물어보면 설명하는가", ""]
        for q in json.loads(fo.read_text(encoding="utf-8")):
            L += [f"**질문** {q['question']}", "", f"**답** {q['output']['answer']}", "", f"재료: {', '.join(LAYER[d] for d in q['output']['drivers'])}", ""]
    (out / f"CASE_{focus}.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    C = ["# 대조 — 서로 다른 페르소나가 같은 날 다른 선택을 하는가 (10/20)", "", "주의: 대조 두 명은 1차 실행(근거 ID 칸 · 이번 방문 조건 문구가 생기기 전) 결과다. 두 명 모두 지난 패키지 혜택이 없어 혜택 승계 문제는 없지만, 근거 ID 는 적혀 있지 않다.", "",
         "초점 사례(blog25 · 아이 둘 가족)와 비교하기 위한 두 명. 같은 무대(A0 여름 주말 · B0 가을 와인페어 주말)에서 선택과 이유가 어떻게 갈리는지 본다.", ""]
    for cond in ("A0", "B0", "B1"):
        rows = [(b, load(b, cond)) for b in [focus] + RL.CONTRAST]; rows = [(b, r) for b, r in rows if r]
        if not rows: continue
        C += [f"## {cond} · {RL.CONDITIONS[cond]['name']}", "", "| 시간대 | " + " | ".join(f"{b} ({r['output']['self_intro'][:28]}…)" for b, r in rows) + " |", "|---|" + "---|" * len(rows)]
        for i in range(4):
            C.append(f"| {rows[0][1]['output']['decisions'][i]['slot']} | " + " | ".join(f"`{r['output']['decisions'][i]['option_code']}` {LAYER[r['output']['decisions'][i]['main_driver']][:6]}" for _, r in rows) + " |")
        C += [""] + [f"- **{b}** “{r['output']['one_line_quote']}”" for b, r in rows] + [""]
    for b in RL.CONTRAST:
        for cond in ("A0", "B0", "B1"):
            r = load(b, cond)
            if r: C += ["---", "", f"## {b}", "", "**시트**", "", r["sheet"], "", story(r), review_block()]
    (out / "CONTRAST.md").write_text("\n".join(C) + "\n", encoding="utf-8")

    with open(out / "review_sheet.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["blog", "조건", "시간대", "선택", "주재료", "개연성(강경수)", "개연성(한호)", "일관성(강)", "일관성(한)", "상황대응(강)", "상황대응(한)", "정직성(강)", "정직성(한)", "갈린 지점 · 메모"])
        for b in [focus] + RL.CONTRAST:
            for c in RL.CONDITIONS:
                r = load(b, c)
                if r:
                    for d in r["output"]["decisions"]:
                        w.writerow([b, c, d["slot"], d["option_code"], d["main_driver"]] + [""] * 9)
    print("review/CASE_%s.md · review/CONTRAST.md · review/review_sheet.csv" % focus)


if __name__ == "__main__":
    main()
