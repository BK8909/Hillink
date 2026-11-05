"""10명 공통 검증 절차 (10/21 · 총괄 C) — 기술 실행과 행동 검증을 구분하기 위한 같은 조건의 시험

  python3 verify10.py --run     # 실시간 LLM 호출(가지 · 질문)을 만들고 review/verify10_20261021.json 에 기록
  python3 verify10.py           # 저장된 기록으로 자동 점검표만 다시 만든다(호출 없음)

공통 절차(모든 고객 같게)
  P0 전체 일정 — runs/demo_1/<blog>/D0 (10/24 토 · 와인페어 날 · 객실만 1박)
  S  코드가 찾은 실행 불가(운영 종료 등)가 있으면 그 시간대만 LLM 재판단(kind=system) — 결정 D1
  E1 공통 사건 — 저녁 식사로 고른 곳이 '단체 예약으로 자리가 모두 찼고 대기 불가'(운영자) → 저녁 시간대 재판단
  Q1 그 가지에서 '왜 그걸로 바꿨고 다른 후보는 왜 아닌가' · Q2 '방금 바꾼 저녁 때문에 남은 일정이 달라지나' (Q2 는 Q1 을 기억해야 한다)
blog25 는 같은 종류의 사건(피자힐 19:00 회차 마감 · D0_ev1)이 이미 있어 E1 로 쓴다.
"""
from __future__ import annotations

import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import branching as BR, make_case   # noqa: E402
from build_sim import visit_of   # noqa: E402
from persona_sheet import load_cards   # noqa: E402

OUT = HERE / "review" / "verify10_20261021.json"
Q1 = "저녁 자리가 없다고 들었을 때 왜 그걸로 바꾸셨어요? 원래 생각했던 다른 후보는 왜 안 했나요?"
Q2 = "방금 바꾼 저녁 때문에 저녁 이후나 다음 날 아침 계획도 달라지나요?"
REUSE_E1 = {"blog25": "D0_ev1"}


def people():
    return sorted(b for b, c in load_cards().items() if c.get("selection_status") == "selected" and (HERE / "runs" / "demo_1" / b / "D0_r0.json").exists())


def run():
    log = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for b in people():
        L = log.setdefault(b, {}); f = HERE / "runs" / "demo_1" / b / "D0_r0.json"; rec = json.loads(f.read_text(encoding="utf-8"))
        v = visit_of(f, rec)
        if v["events"] and "system" not in L:
            e = v["events"][0]; i = next(k for k, d in enumerate(rec["output"]["decisions"]) if d["slot"] == e["slot"])
            done = [a for a in v["activities"] if a["kind"] == "core"]
            txt = f"{e['text']} — 앞 일정({done[-1]['place_label']} {done[-1]['start_hm']}~{done[-1]['end_hm']}) 뒤에는 시간이 남지 않는다"
            r = BR.make_branch(f, i, txt, "system"); L["system"] = dict(key=r["key"], text=txt, later=r["later_plan"]); print(b, "system", r["key"], flush=True)
        if "e1" not in L:
            if b in REUSE_E1:
                L["e1"] = dict(key=f"demo_1:{REUSE_E1[b]}", text=json.loads((f.with_name(REUSE_E1[b] + "_r0.json")).read_text(encoding="utf-8"))["event"]["text"], reused=True)
            else:
                dinner = next((a for a in v["activities"] if a["kind"] == "core" and a.get("decision_index") == 1), None)
                name = dinner["place_label"] if dinner else rec["output"]["decisions"][1]["choice"][:20]
                txt = f"{name}의 오늘 저녁 자리가 단체 예약으로 모두 찼고, 대기도 받지 않는다고 안내받았다"
                r = BR.make_branch(f, 1, txt, "operator"); L["e1"] = dict(key=r["key"], text=txt, later=r["later_plan"]); print(b, "e1", r["key"], flush=True)
            OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        bf = f.with_name(L["e1"]["key"].split(":")[1] + "_r0.json")
        for k, q in (("q1", Q1), ("q2", Q2)):
            if k not in L:
                L[k] = BR.followup(bf, q); print(b, k, "ok", flush=True)
                OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return log


def expname(n): return re.sub(r"\s+", " ", re.sub(r"'[^']*'", "", str(n).split("(")[0])).strip()


def check(log):
    rows = []
    for b in people():
        L = log.get(b, {}); f = HERE / "runs" / "demo_1" / b / "D0_r0.json"; rec = json.loads(f.read_text(encoding="utf-8")); v = visit_of(f, rec)
        D = rec["output"]["decisions"]; sheet = rec["sheet"]
        ids_sheet = set(re.findall(r"[A-Za-z0-9]+:[A-Za-z0-9_\-]+", sheet))
        used = sorted({i for d in D for i in d.get("evidence_ids", [])})
        gen_personal = [d["slot"] for d in D if re.search(r"(편이라|좋아해|싫어해|성향|취향이라)", d["reasons"].get("general_sense", "")) and not d.get("evidence_ids")]
        row = dict(blog=b, choices=[expname(next((o["name"] for o in rec["stage"]["options"] if o["code"] == d["option_code"]), d["option_code"])) for d in D],
                   mains=[d["main_driver"] for d in D], ids_used=used, ids_unknown=[i for i in used if i not in ids_sheet], flags=make_case.honesty_flags(rec),
                   no_personal=[d["slot"] for d in D if not d.get("evidence_ids")], gen_personal=gen_personal, spend=v["est_spend_krw"], events=v["events"])
        if "e1" in L:
            bf = f.with_name(L["e1"]["key"].split(":")[1] + "_r0.json"); br = json.loads(bf.read_text(encoding="utf-8")); bv = visit_of(bf, br)
            nd = br["output"]["decisions"][1]; nn = expname(next((o["name"] for o in br["stage"]["options"] if o["code"] == nd["option_code"]), nd["option_code"]))
            gaps = [(a["end"], c["start"]) for a, c in zip(bv["activities"], bv["activities"][1:]) if a["end"] != c["start"]]
            row["e1"] = dict(event=L["e1"]["text"], new=nn, code=nd["option_code"], same_as_before=nd["option_code"] == D[1]["option_code"], main=nd["main_driver"], ids=nd.get("evidence_ids", []),
                             later=(br.get("event_call") or {}).get("later_plan"), spend=bv["est_spend_krw"], gaps=len(gaps), conflicts=bv["events"], flags=make_case.honesty_flags(br))
            if "q1" in L and "q2" in L:
                a1, a2 = L["q1"]["answer"], L["q2"]["answer"]
                key = [w for w in re.split(r"[\s·()]+", nn) if len(w) >= 2][:2]
                row["q"] = dict(q1_names_new=any(w in a1 for w in key), q2_names_new=any(w in a2 for w in key), q2_refers_back=bool(re.search(r"(방금|앞서|말씀드린|아까|바꾼|그래서)", a2)),
                                q1=a1, q2=a2, drivers=[L["q1"]["drivers"], L["q2"]["drivers"]])
        if "system" in L:
            sf = f.with_name(L["system"]["key"].split(":")[1] + "_r0.json"); sr = json.loads(sf.read_text(encoding="utf-8"))
            i = next(k for k, d in enumerate(sr["output"]["decisions"]) if d.get("decided_by") == "llm_event")
            row["system"] = dict(event=L["system"]["text"], new=expname(next((o["name"] for o in sr["stage"]["options"] if o["code"] == sr["output"]["decisions"][i]["option_code"]), "")), later=L["system"].get("later"))
        rows.append(row)
    return rows


if __name__ == "__main__":
    log = run() if "--run" in sys.argv else (json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {})
    rows = check(log)
    (HERE / "review" / "verify10_checks_20261021.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(r["blog"], "|", " / ".join(r["choices"]), "| flags", len(r["flags"]), "| ids?", r["ids_unknown"], "| e1:", r.get("e1", {}).get("new"), r.get("e1", {}).get("later"), "| q:", {k: v for k, v in r.get("q", {}).items() if k.startswith("q") and isinstance(v, bool)})
