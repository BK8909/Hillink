"""Q1/Q2 후속 설명 대조 실험 (10/21 · 총괄 C) — 결정은 저장된 그대로 두고, 후속 질문 입력만 바꾼다.

  python3 qctx_experiment.py --plan                       # 호출 없음 · 10명 × 조건 A~D 입력 비교 → review/qctx_inputs_1021.json
  python3 qctx_experiment.py --run --cases blog25,blog41,blog58 --conds A,B,C,D --budget 1.6 --approved "<메모>"
                                                          # → runs/qctx_pilot_1/<blog>/<조건>.json (기존 runs 는 읽기만)

조건(모델 · 무대 · 시간표 · 바뀐 상황 글 · 질문 · 질문 순서는 모두 같게)
  A  지금 기본: 저장된 시트 + 기본 시스템            (기준선 · 같은 날 다시 물음 — 'sonnet' 별칭의 모델 차이를 피하려고)
  B  A + 그때 이유 · 버린 대안(decision_context · 평가자 의견 정리)   (설명 맥락 효과)
  C  C2 시트만(build_sheet_v2) + 기본 시스템          (근거 품질 효과)
  D  C2 시트 + 그때 이유 · 대안 + 추가 규칙(system_v2)  (결합 효과)
Q2 는 같은 조건의 Q1 답을 이어 받는다(저장 방식과 같음).
중단: 누적 비용이 --budget 을 넘거나 3회 연속 실패하면 멈춘다. 결과가 이미 있는 (사례 · 조건)은 건너뛴다.
"""
from __future__ import annotations

import argparse, datetime, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ask, branching, evidence_ctx as E                    # noqa: E402
from build_sim import visit_of                              # noqa: E402
from persona_sheet import load_cards                        # noqa: E402

Q1 = "저녁 자리가 없다고 들었을 때 왜 그걸로 바꾸셨어요? 원래 생각했던 다른 후보는 왜 안 했나요?"
Q2 = "방금 바꾼 저녁 때문에 저녁 이후나 다음 날 아침 계획도 달라지나요?"
CONDS = {"A": dict(sheet="v1", ctx=False, system="base"), "B": dict(sheet="v1", ctx=True, system="base"),
         "C": dict(sheet="c2", ctx=False, system="base"), "D": dict(sheet="c2", ctx=True, system="v2")}
OUT = HERE / "runs" / "qctx_pilot_1"


def J(p: Path): return json.loads(p.read_text(encoding="utf-8"))


def e1_of(b: str) -> Path:
    V = J(HERE / "review" / "verify10_20261021.json")
    return HERE / "runs" / "demo_1" / b / (V[b]["e1"]["key"].split(":")[1] + "_r0.json")


def inputs(b: str, cond: str, history: list | None = None, question: str = Q1) -> dict:
    """한 조건의 (system, prompt) 를 만든다. ask.call 을 바꿔 끼워 프롬프트만 받는다(호출 없음)."""
    card = load_cards()[b]; f = e1_of(b); rec = J(f); base = J(f.with_name(f"{rec['branch_of']}_r0.json")); c = CONDS[cond]
    sheet = rec["sheet"] if c["sheet"] == "v1" else E.build_sheet_v2(card)["text"]
    ctx = E.decision_context(rec, card, base) if c["ctx"] else None
    system = E.system_v2(ask.SYSTEM) if c["system"] == "v2" else None
    got = {}; real = ask.call
    ask.call = lambda system, prompt, schema, model=ask.MODEL, timeout=240: got.update(system=system, prompt=prompt) or {}
    try:
        ask.ask_followup(sheet, rec["stage_text"], rec["output"], question, history=history, visit=visit_of(f, rec), change=branching.change_text(f, rec), context=ctx, system=system)
    finally:
        ask.call = real
    return got


def plan() -> dict:
    cards = load_cards(); V = J(HERE / "review" / "verify10_20261021.json"); rows = []
    for b in sorted(V):
        row = dict(blog=b, e1=str(e1_of(b).relative_to(HERE)))
        for cond in CONDS:
            g = inputs(b, cond); full = g["system"] + "\n" + g["prompt"]; pc = E.prompt_contamination(full, cards[b])
            row[cond] = dict(chars=len(g["prompt"]), system_chars=len(g["system"]), evaluator_ids=pc["evaluator_ids"], unmarked_evaluator_content=len(pc["unmarked_evaluator_content"]),
                             unmarked_examples=[x[:90] for x in pc["unmarked_evaluator_content"][:3]], prompt_sha=hashlib.sha256(full.encode()).hexdigest()[:12])
        rows.append(row)
    return dict(note="호출 없음 · 같은 E1 결정 · 조건별 Q1 입력", conds=CONDS, rows=rows)


def run(cases: list[str], conds: list[str], budget: float, memo: str) -> dict:
    spent, fails, log = 0.0, 0, []
    for b in cases:
        for cond in conds:
            out = OUT / b / f"{cond}.json"
            if out.exists(): log.append(f"{b} {cond} 건너뜀(있음)"); continue
            hist, res = [], []
            for q in (Q1, Q2):
                if spent >= budget or fails >= 3:
                    log.append(f"중단: 비용 {spent:.3f} / 연속 실패 {fails}"); return dict(spent=spent, log=log)
                g = inputs(b, cond, history=hist, question=q)
                try:
                    r = ask.call(g["system"], g["prompt"], ask.FOLLOWUP_SCHEMA); fails = 0
                except Exception as e:   # noqa: BLE001 — 실패도 기록
                    fails += 1; log.append(f"{b} {cond} 실패: {str(e)[:120]}"); break
                spent += r.get("cost_usd") or 0
                res.append(dict(question=q, **r)); hist.append(dict(question=q, answer=r["output"]["answer"]))
            if len(res) == 2:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(dict(blog=b, cond=cond, cond_spec=CONDS[cond], e1=str(e1_of(b).relative_to(HERE)), memo=memo,
                                               at=datetime.datetime.now().isoformat(timespec="seconds"), answers=res), ensure_ascii=False, indent=1), encoding="utf-8")
                log.append(f"{b} {cond} 완료 · 누적 ${spent:.3f}")
            print(log[-1], flush=True)
    return dict(spent=spent, log=log)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--plan", action="store_true"); ap.add_argument("--run", action="store_true")
    ap.add_argument("--cases", default="blog25,blog41,blog58"); ap.add_argument("--conds", default="A,B,C,D"); ap.add_argument("--budget", type=float, default=1.6); ap.add_argument("--approved", default="")
    a = ap.parse_args()
    if a.plan:
        P = plan(); (HERE / "review" / "qctx_inputs_1021.json").write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding="utf-8")
        for r in P["rows"]:
            print(r["blog"], " | ".join(f"{c}: {r[c]['chars']}자 · 평가ID {len(r[c]['evaluator_ids'])} · 표시없는 평가내용 {r[c]['unmarked_evaluator_content']}" for c in CONDS))
    elif a.run:
        if not a.approved: sys.exit("승인 메모(--approved) 없이는 호출하지 않는다")
        R = run(a.cases.split(","), a.conds.split(","), a.budget, a.approved); print(json.dumps(R, ensure_ascii=False, indent=1))
    else:
        print(__doc__)
