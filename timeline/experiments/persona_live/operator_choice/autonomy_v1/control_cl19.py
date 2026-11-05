"""CL-19 후속(P1-7) — 작은 대조 실험: 정상 프로파일 / 프로파일 없음 / 교환 프로파일.
같은 고객의 방문 조건(숙박 · 동행 · 체류 단계)은 고정하고 프로파일만 바꾼다. 결정 난수 S개로 활동 분포를 비교.
교환은 A07 ← blog42 · A05 ← A07 · blog42 ← A05 처럼 다른 고객의 프로파일을 넣는다.
규칙 기반 실행(API 호출 없음). LLM 판단으로 같은 실험을 하려면 새 호출이 필요하다(사용자 승인 뒤).
  python3 -m operator_choice.autonomy_v1.control_cl19 --seeds 30 --out DIR
"""
import argparse, collections, json
from pathlib import Path
from . import agent_day as AD
from ..operator_world_v1_1 import turn_view as TV

SKIP = {"move", "wait", "idle", "arrive", "leave", "wake", "checkin", "checkout", "pack", "unpack", "sleep"}
SWAP = {"A07": "blog42", "A05": "A07", "blog42": "A05"}


def run(p, inp, seed, mode):
    P, bars, lib = inp
    sc = AD.scenario("base", seed=0)
    real = AD.Agent(p, P, bars, lib, sc)
    if mode == "normal":
        a = real
    else:
        if mode == "none":
            P2 = dict(P); P2[p] = dict(P[p], traits=TV._empty_traits()); b2 = dict(bars); b2[p] = []; l2 = dict(lib); l2[p] = dict(lib.get(p, {}), engine={}, wh_events=[], other_events=[], traits=[], rules=[])
        else:
            q = SWAP[p]
            P2 = dict(P); P2[p] = dict(P[q], id=p); b2 = dict(bars); b2[p] = bars.get(q); l2 = dict(lib); l2[p] = lib.get(q, {})
        a = AD.Agent(p, P2, b2, l2, sc)
        a.vs, a.B, a.stay, a.phase, a.N, a.C = real.vs, real.B, real.stay, real.phase, real.N, real.C
        a.room = AD.SP.room(a.B) if a.stay else None; a.loc = a.room if a.phase in ("mid", "checkout") else "HOTEL_GATE"; a.t = real.t; a.checked_in = real.checked_in; a.end = real.end
    a.rng_base = f"autonomy|{p}|{seed}"
    w = AD.World(sc); g = 0
    while AD.decide(a, w) and g < 90:
        g += 1
    return AD.finish(a)


def dist(rs):
    c = collections.Counter(x["act"].split(":")[0] for r in rs for x in r["log"] if x["act"] not in SKIP)
    return {k: round(v / len(rs), 2) for k, v in c.items()}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=30); ap.add_argument("--out", required=True)
    a_ = ap.parse_args(); out = Path(a_.out); out.mkdir(parents=True, exist_ok=True)
    inp = AD.load_inputs(); res = {}
    for p in SWAP:
        R = {m: [run(p, inp, s, m) for s in range(a_.seeds)] for m in ("normal", "none", "swap")}
        D = {m: dist(v) for m, v in R.items()}
        keys = sorted(set().union(*D.values()), key=lambda k: -max(abs(D["normal"].get(k, 0) - D["none"].get(k, 0)), abs(D["normal"].get(k, 0) - D["swap"].get(k, 0))))
        rows = []
        for k in keys[:8]:
            ev = [e for r in R["normal"] for x in r["log"] if x["act"].split(":")[0] == k for e in x["evidence"]]
            rows.append(dict(act=k, normal=D["normal"].get(k, 0), none=D["none"].get(k, 0), swap=D["swap"].get(k, 0),
                             review_facts=sorted({f for e in ev if e["type"] == "후기에서 확인" for f in e["fact_ids"]})[:4],
                             extended_from=sorted({f for e in ev for f in e.get("extended_from", [])})[:4],
                             traits=sorted({t for e in ev if e["type"] == "프로파일 기반 추론" for t in (e.get("traits") or [])})[:5]))
        spend = {m: round(sum(r["summary"]["spent_known_krw"] for r in v) / len(v)) for m, v in R.items()}
        res[p] = dict(swap_with=SWAP[p], visit=R["normal"][0]["visit"]["why"], seeds=a_.seeds, rows=rows, avg_spent_known=spend)
    (out / "control_cl19.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = []
    for p, v in res.items():
        md += [f"\n### {p} (교환 프로파일: {v['swap_with']}) — {v['visit']} · 시드 {v['seeds']}\n", "| 행동 | 정상 | 없음 | 교환 | 정상일 때 근거(후기 · 확장 · 성향) |", "|---|---:|---:|---:|---|"]
        for r in v["rows"]:
            md.append(f"| {r['act']} | {r['normal']} | {r['none']} | {r['swap']} | 후기 {','.join(r['review_facts']) or '-'} · 확장 {','.join(r['extended_from']) or '-'} · 성향 {','.join(r['traits']) or '-'} |")
        md.append(f"\n평균 지출(가격 확인분) 정상 {v['avg_spent_known']['normal']:,} · 없음 {v['avg_spent_known']['none']:,} · 교환 {v['avg_spent_known']['swap']:,}원")
    (out / "control_cl19.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
