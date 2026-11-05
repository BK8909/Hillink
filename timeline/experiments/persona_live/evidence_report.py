"""P0-B 저장 기록 전후 점검 (10/21 · 총괄 C) — 모델 호출 없음 · 저장 실행을 바꾸지 않음.

  python3 evidence_report.py   # → review/evidence_context_p0b_1021.json (표는 EVIDENCE_CONTEXT_P0B_1021.md 에 옮김)

'전' = 지금 기본 경로(persona_sheet.build_sheet · ask_followup 기본). '후' = evidence_ctx 옵트인 변형으로 **만들어질 입력**.
모델이 그 입력으로 다르게 답하는지는 호출이 필요하므로 여기서 판정하지 않는다(미검증).
"""
from __future__ import annotations

import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ask, branching, evidence_ctx as E                     # noqa: E402
from build_sim import visit_of                              # noqa: E402
from persona_sheet import build_sheet, load_cards           # noqa: E402

OUT = HERE / "review" / "evidence_context_p0b_1021.json"
Q1 = "저녁 자리가 없다고 들었을 때 왜 그걸로 바꾸셨어요? 원래 생각했던 다른 후보는 왜 안 했나요?"


def J(p: Path): return json.loads(p.read_text(encoding="utf-8"))


def followup_prompt(f: Path, rec: dict, context: str | None) -> str:
    """ask.call 을 바꿔 끼워 프롬프트만 받는다(호출 없음)."""
    got = {}
    real = ask.call
    ask.call = lambda system, prompt, schema, model=ask.MODEL, timeout=240: got.update(system=system, prompt=prompt) or {"output": {"answer": "", "drivers": []}, "cost_usd": 0}
    try:
        ask.ask_followup(rec["sheet"], rec["stage_text"], rec["output"], Q1, visit=visit_of(f, rec), change=branching.change_text(f, rec), context=context)
    finally:
        ask.call = real
    return got["prompt"]


def run() -> dict:
    cards = load_cards(); V = J(HERE / "review" / "verify10_20261021.json"); rows = []
    for b in sorted(V):
        card = cards[b]; d = HERE / "runs" / "demo_1" / b; base = J(d / "D0_r0.json"); key = V[b]["e1"]["key"].split(":")[1]
        bf = d / f"{key}_r0.json"; br = J(bf)
        s1, s2 = build_sheet(card)["text"], E.build_sheet_v2(card)
        ev_ids = s2["evaluator_ids"]
        sheet = dict(evaluator_ids_in_v1=[i for i in ev_ids if i in s1], evaluator_ids_in_v2=[i for i in ev_ids if i in s2["text"]],
                     blanket_observed_v1=sum(1 for l in s1.splitlines() if ("예약한 것" in l or "포함돼 있던 것" in l) and l.rstrip().endswith("[관측]")),
                     chars_v1=len(s1), chars_v2=len(s2["text"]), same_stay_caveat="[주의]" in s2["text"])
        aud = E.audit_decisions(base, card) + E.audit_decisions(br, card)
        decisions = dict(evaluator_cited=sorted({i for a in aud for i in a["evaluator_ids"]}), evaluator_cited_n=sum(len(a["evaluator_ids"]) for a in aud),
                         liking_without_record=sum(len(a["liking_without_record"]) for a in aud), memory_without_id=sum(a["memory_without_id"] for a in aud),
                         revisit_by_visit_only=sorted({a["option"] for a in aud if a["revisit_by_visit_only"]}))
        fu = d / f"{key}_followup.json"; q1 = next((x for x in J(fu) if x["question"] == Q1), None) if fu.exists() else None
        k = next((i for i, x in enumerate(br["output"]["decisions"]) if x.get("decided_by") == "llm_event"), None)
        why = [x["why_not"] for x in br["output"]["decisions"][k]["alternatives"]] + [x["why_not"] for x in base["output"]["decisions"][k]["alternatives"]] if k is not None else []
        p0, p1 = followup_prompt(bf, br, None), followup_prompt(bf, br, E.decision_context(br, card, base))
        q = dict(why_not_total=len(why), why_not_in_prompt_before=sum(w in p0 for w in why), why_not_in_prompt_after=sum(w in p1 for w in why),
                 reasons_in_prompt_before=all(v in p0 for v in br["output"]["decisions"][k]["reasons"].values() if v) if k is not None else None,
                 reasons_in_prompt_after=all(v in p1 for v in br["output"]["decisions"][k]["reasons"].values() if v) if k is not None else None,
                 prompt_chars_before=len(p0), prompt_chars_after=len(p1),
                 stored_q1_alignment=E.followup_alignment(br, q1["output"]["answer"], base) if q1 else None)
        feas = {k: [x["text"] for x in E.feasibility_signals(J(d / f"{k}_visit.json"))] for k in ("D0", key)}
        rows.append(dict(blog=b, e1=f"demo_1/{key}", sheet=sheet, decisions=decisions, q1=q, feasibility=feas))
    return dict(note="저장 기록 기반 · 모델 호출 없음 · '후' 는 만들어질 입력이지 새 응답이 아님", rows=rows)


if __name__ == "__main__":
    R = run(); OUT.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in R["rows"]:
        s, d, q = r["sheet"], r["decisions"], r["q1"]
        print(r["blog"], "| 시트 평가ID", len(s["evaluator_ids_in_v1"]), "→", len(s["evaluator_ids_in_v2"]), "| 일괄관측", s["blanket_observed_v1"], "| 인용", d["evaluator_cited_n"], d["evaluator_cited"],
              "| 좋아함", d["liking_without_record"], "| 가봤다→다시", d["revisit_by_visit_only"], "| why_not", q["why_not_in_prompt_before"], "→", q["why_not_in_prompt_after"], "/", q["why_not_total"],
              "| 이유", q["reasons_in_prompt_before"], "→", q["reasons_in_prompt_after"], "| 글자", q["prompt_chars_before"], "→", q["prompt_chars_after"],
              "| Q1", (q["stored_q1_alignment"] or {}).get("mentioned_unrecorded"), "| 시간", sum(len(v) for v in r["feasibility"].values()))
