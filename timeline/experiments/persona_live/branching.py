"""사건 재판단 가지 · 맥락 질문 — 화면 서버(serve_demo.py)와 10명 검증(verify10.py)이 같은 코드를 쓴다 (10/21)

make_branch(f, slot_index, text, kind)   → runs/<plan>/<blog>/<cond>_evK_r0.json · _visit.json (원본 기록은 그대로)
followup(f, question)                    → runs/<plan>/<blog>/<cond>_followup.json 에 덧붙임 (질문은 상태를 바꾸지 않는다)
kind: operator(운영자가 바꾼 상황) · system(코드가 찾은 실행 불가 — 운영 종료 · 좌석 없음)
"""
from __future__ import annotations

import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ask, itinerary as IT   # noqa: E402
from build_sim import slim_run, visit_of   # noqa: E402


def make_branch(f: Path, slot_index: int, text: str, kind: str = "operator") -> dict:
    rec = json.loads(f.read_text(encoding="utf-8")); cond = rec["condition"]
    i = int(slot_index); d_old = rec["output"]["decisions"][i]
    base = visit_of(f, rec)
    done = [a for a in base["activities"] if a["kind"] == "checkin" or (a["kind"] == "core" and a.get("decision_index") is not None and a["decision_index"] < i)]
    at = next((a["start"] for a in base["activities"] if a.get("decision_index") == i), None)
    if at is None:   # 실행되지 못한 시간대(운영 종료 등) — 앞 활동이 끝난 시각을 지금으로
        prev = [a for a in base["activities"] if a["kind"] == "core" and (a.get("decision_index") or 0) < i]
        at = (prev[-1]["end"] + 30) if prev else IT.mins("15:00") + 30
    snap = dict(now_hm=IT.hm(at - 30), here_label="객실" if i else "로비", slot=d_old["slot"], done=done,
                remaining=[dict(slot=x["slot"], choice=x["choice"], option_code=x["option_code"]) for x in rec["output"]["decisions"][i:]])
    event = dict(kind=kind, at=snap["now_hm"], slot=d_old["slot"], text=text)
    r = ask.ask_next(rec["sheet"], rec["stage_text"], snap, event)
    nd = dict(r["output"]); nd["slot"] = d_old["slot"]; nd["decided_by"] = "llm_event"; later = nd.pop("later_plan", "keep")
    k = 1
    while f.with_name(f"{cond}_ev{k}_r0.json").exists(): k += 1
    br = json.loads(json.dumps(rec)); br["output"]["decisions"][i] = nd
    br["condition"] = f"{cond}_ev{k}"; br["condition_name"] = rec["condition_name"] + f" + 사건: {text[:30]}"; br["branch_of"] = cond; br["event"] = event
    br["event_call"] = dict(cost_usd=r["cost_usd"], model=r["model"], prompt_sha256=r["prompt_sha256"], later_plan=later)
    bf = f.with_name(f"{cond}_ev{k}_r0.json"); bf.write_text(json.dumps(br, ensure_ascii=False, indent=1), encoding="utf-8")
    v = IT.build_visit(br); bf.with_name(f"{cond}_ev{k}_visit.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    br, v = resolve_cascade(bf)
    return dict(key=f"{br['plan']}:{br['condition']}", file=bf, entry=dict(run=slim_run(br), visit=visit_of(bf, br), followups=[]), later_plan=later, cost_usd=r["cost_usd"])


def resolve_cascade(bf: Path, max_steps: int = 2):
    """사건으로 앞 계획이 바뀐 뒤 뒤쪽 시간대가 실행 불가(운영 종료 등)가 되면 그 시간대도 LLM 이 다시 정한다(결정 D1 · 최대 2단계).
    10/21 검증: blog41 저녁이 피자힐 20:30 으로 바뀐 뒤 스카이야드(22:00 종료)가 남아 충돌 — 고객은 말로만 '안 간다' 고 했고 기록은 그대로였다."""
    br = json.loads(bf.read_text(encoding="utf-8")); v = IT.build_visit(br)
    for _ in range(max_steps):
        ev = next((e for e in v["events"] if e["kind"] == "closed"), None)
        if not ev: break
        j = next(k for k, d in enumerate(br["output"]["decisions"]) if d["slot"] == ev["slot"])
        done = [a for a in v["activities"] if a["kind"] == "checkin" or (a["kind"] == "core" and a.get("decision_index") is not None and a["decision_index"] < j)]
        last = [a for a in done if a["kind"] == "core"]
        snap = dict(now_hm=ev["at"], here_label="객실", slot=ev["slot"], done=done,
                    remaining=[dict(slot=x["slot"], choice=x["choice"], option_code=x["option_code"]) for x in br["output"]["decisions"][j:]])
        e2 = dict(kind="system", at=ev["at"], slot=ev["slot"], text=f"{ev['text']} — 바뀐 앞 일정({last[-1]['place_label']} ~{last[-1]['end_hm']}) 뒤라 원래 계획을 할 수 없다" if last else ev["text"])
        r = ask.ask_next(br["sheet"], br["stage_text"], snap, e2)
        nd = dict(r["output"]); nd["slot"] = ev["slot"]; nd["decided_by"] = "llm_event"; nd.pop("later_plan", None)
        br["output"]["decisions"][j] = nd; br.setdefault("cascade", []).append(dict(event=e2, cost_usd=r["cost_usd"], model=r["model"], prompt_sha256=r["prompt_sha256"]))
        v = IT.build_visit(br)
    bf.write_text(json.dumps(br, ensure_ascii=False, indent=1), encoding="utf-8")
    bf.with_name(bf.name.replace("_r0.json", "_visit.json")).write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    return br, v


def change_text(f: Path, rec: dict) -> str | None:
    """가지(사건 뒤 다시 정한 계획)면 — 무슨 일이 있었고 원래 무엇을 골랐다가 무엇으로 바꿨는지. 10/21 검증에서 이것이 없어 원래 선택을 잘못 말한 답이 10명 중 4명."""
    if not rec.get("branch_of"): return None
    base = json.loads(f.with_name(f"{rec['branch_of']}_r0.json").read_text(encoding="utf-8"))
    ev = rec.get("event") or {}; lines = [f"- {ev.get('at', '')} · {ev.get('slot', '')}: {ev.get('text', '')}" + (" (코드가 찾은 실행 불가)" if ev.get("kind") == "system" else "")]
    names = {o["code"]: o["name"] for o in rec["stage"]["options"]}
    for d0, d1 in zip(base["output"]["decisions"], rec["output"]["decisions"]):
        if d0["option_code"] != d1["option_code"] or d1.get("decided_by") == "llm_event":
            lines.append(f"- {d1['slot']}: 원래 당신이 고른 계획 '{names.get(d0['option_code'], d0['option_code'])}' — {d0['choice']} → 이 일 때문에 '{names.get(d1['option_code'], d1['option_code'])}' 로 다시 정함")
    lines.append("- 원래 계획을 고른 것도 당신입니다. 왜 바꿨는지 말할 때 원래 계획이 막힌 사실을 그대로 말하고, 원래 고른 곳을 처음부터 싫었던 것처럼 말하지 마세요.")
    return "\n".join(lines)


def followup_context(f: Path, rec: dict) -> str:
    """evidence_ctx.decision_context 를 저장 기록에서 만든다(호출 없음)."""
    import evidence_ctx
    from persona_sheet import load_cards
    base = json.loads(f.with_name(f"{rec['branch_of']}_r0.json").read_text(encoding="utf-8")) if rec.get("branch_of") else None
    return evidence_ctx.decision_context(rec, load_cards()[rec["blog"]], base)


def followup(f: Path, question: str, with_reasons: bool = False, sheet_variant: str = "stored", out_dir: Path | None = None) -> dict:
    """기본(with_reasons=False · sheet_variant='stored')은 예전과 같다.
    옵트인(승인 전 실행 금지): with_reasons=True 는 그때 이유 네 층 · 버린 대안(평가자 의견 정리)을, sheet_variant='c2' 는 근거 층 시트를 넘긴다.
    옵트인 결과는 저장 실행 폴더가 아니라 out_dir(기본 runs/qctx_manual/<plan>/<blog>/)에 쓴다. 조건 대조 실험은 qctx_experiment.py 를 쓴다."""
    rec = json.loads(f.read_text(encoding="utf-8")); cond = rec["condition"]
    opt = with_reasons or sheet_variant != "stored"
    if opt:
        d = out_dir or HERE / "runs" / "qctx_manual" / rec["plan"] / rec["blog"]; d.mkdir(parents=True, exist_ok=True)
        fo = d / f"{cond}_followup_{'ctx' if with_reasons else 'noctx'}_{sheet_variant}.json"
    else:
        fo = f.with_name(f"{cond}_followup.json")
    prev = json.loads(fo.read_text(encoding="utf-8")) if fo.exists() else []
    hist = [dict(question=x["question"], answer=x["output"]["answer"]) for x in prev]
    ctx = followup_context(f, rec) if with_reasons else None
    sheet = rec["sheet"]
    if sheet_variant == "c2":
        import evidence_ctx
        from persona_sheet import load_cards
        sheet = evidence_ctx.build_sheet_v2(load_cards()[rec["blog"]])["text"]
    r = ask.ask_followup(sheet, rec["stage_text"], rec["output"], question, history=hist, visit=visit_of(f, rec), change=change_text(f, rec), context=ctx)
    prev.append(dict(question=question, **r)); fo.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(question=question, answer=r["output"]["answer"], drivers=r["output"]["drivers"], cost_usd=r["cost_usd"])
