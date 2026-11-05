"""Q1/Q2 파일럿 자동 점수 (10/21 · 총괄 C) — 호출 없음. runs/qctx_pilot_1 → review/qctx_pilot_scores_1021.json

자동 점수는 낱말 · 규칙 신호다. 이유의 타당성은 QCTX_PILOT_1021.md 의 총괄 C 판정표(사람 검수 전)로 따로 본다.
"""
from __future__ import annotations

import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence_ctx as E                                   # noqa: E402
from persona_sheet import load_cards                       # noqa: E402
from qctx_experiment import OUT, e1_of                     # noqa: E402

# 사례별 '기록에 있던 약한 이유' — 되풀이하는지 본다(사람 검수 #81 · #83 에서 지적된 것)
WEAK = {"blog41": [("지난 예약 단정", r"(지난번|그때|지난 방문)[^.]{0,25}(미리 )?예약"), ("햇볕 · 야외 이유", r"햇볕|햇빛|야외라")],
        "blog25": [("돌봄 부담", r"돌보|돌봄"), ("전날 충분히", r"전날[^.]{0,12}충분")],
        "blog58": [("행사 무료 단정", r"무료"), ("좌석 확보 단정", r"(자리|좌석)[^.]{0,12}(잡았|확보했|예약했|예약해 뒀)")]}
EVENT_WORDS = re.compile(r"(만석|마감|단체 예약|대기|막혔|자리가 없|찼)")
BACKREF = re.compile(r"(방금|앞서|아까|말씀드린|바꾼|그래서|그 때문에)")
ADDED = re.compile(r"(지금 (덧붙|생각해 보니|돌아보면)|그때는 .{0,10}(생각하지|적지) 않|덧붙이)")
INFER = re.compile(r"(수도 있|일 수|것 같|아마|가능성|보통은|일반적으로)")


def J(p: Path): return json.loads(p.read_text(encoding="utf-8"))


def score_one(b: str, cond: str) -> dict | None:
    f = OUT / b / f"{cond}.json"
    if not f.exists(): return None
    R = J(f); card = load_cards()[b]; ef = e1_of(b); br = J(ef); base = J(ef.with_name(f"{br['branch_of']}_r0.json"))
    k = next(i for i, x in enumerate(br["output"]["decisions"]) if x.get("decided_by") == "llm_event")
    names = {o["code"]: o["name"] for o in br["stage"]["options"]}
    word = lambda c: re.split(r"[\s(·'’]", names[c].strip())[0] if c != "OUTSIDE" else "호텔 밖"
    rec_text = json.dumps([br["output"]["decisions"][k], base["output"]["decisions"][k]], ensure_ascii=False)
    new, old = br["output"]["decisions"][k]["option_code"], base["output"]["decisions"][k]["option_code"]
    out = dict(blog=b, cond=cond, cost=round(sum(a.get("cost_usd") or 0 for a in R["answers"]), 4))
    for qi, a in enumerate(R["answers"], 1):
        t = a["output"]["answer"]; ac = E.answer_contamination(t, card)
        al = E.followup_alignment(br, t, base) if qi == 1 else {}
        unrec = al.get("mentioned_unrecorded", [])
        q = dict(chars=len(t), evaluator_ids=ac["evaluator_ids"], evaluator_memory_claims=ac["memory_claims"], time_errors=E.time_claims(t, br["event"]["at"]),
                 weak_repeated=[n for n, p in WEAK.get(b, []) if re.search(p, t)], added_marker=bool(ADDED.search(t)), inference_markers=len(INFER.findall(t)),
                 names_new=word(new) in t, names_old=word(old) in t)
        if qi == 1:
            q.update(event_named=bool(EVENT_WORDS.search(t)), alts_recorded=al.get("mentioned_recorded", []),
                     alts_unrecorded_in_reasons=[c for c in unrec if word(c) in rec_text], alts_unrecorded_new=[c for c in unrec if word(c) not in rec_text])
        else:
            q.update(backref=bool(BACKREF.search(t)))
        out[f"Q{qi}"] = q
    return out


def main():
    rows = [r for b in ("blog25", "blog41", "blog58") for c in "ABCD" if (r := score_one(b, c))]
    (HERE / "review" / "qctx_pilot_scores_1021.json").write_text(json.dumps(dict(note="자동 신호 · 사람 검수 전", rows=rows), ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        q1, q2 = r["Q1"], r["Q2"]
        print(r["blog"], r["cond"], f"${r['cost']}", "| Q1 평가ID", len(q1["evaluator_ids"]), "기억단정", len(q1["evaluator_memory_claims"]), "시간오류", len(q1["time_errors"]),
              "약한이유", q1["weak_repeated"], "기록대안", len(q1["alts_recorded"]), "이유속", len(q1["alts_unrecorded_in_reasons"]), "새대안", q1["alts_unrecorded_new"],
              "원래/새", q1["names_old"], q1["names_new"], "덧붙임", q1["added_marker"], "| Q2 시간", len(q2["time_errors"]), "약한", q2["weak_repeated"], "기억단정", len(q2["evaluator_memory_claims"]), "앞답", q2["backref"], "새저녁", q2["names_new"])


if __name__ == "__main__":
    main()
