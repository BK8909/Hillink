"""
자동 추출 페르소나 vs 손으로 만든 페르소나 — 두 층으로 잰다

  python3 persona_compare.py 1        # persona_blog01.py (손) vs persona_blog01_auto.py (자동)

1층 · 추출이 같은가      사실 · 성향 값 · 미상 판단 · 정답(방문 · 식당 · 끼니 · 순서)
2층 · 결과가 같은가      두 페르소나로 에이전트 v2 를 돌려 **손 정답**으로 채점
                        성향 값이 좀 달라도 에이전트 동선이 같으면 실용상 같은 추출이다.
                        반대로 값이 비슷해도 사실 하나(포함 끼니 · 박 수)가 틀리면 동선이 크게 바뀐다.
"""

from __future__ import annotations

import importlib, sys
from datetime import datetime

import agent_v2
from match import evaluate
from walkerhill_timeline_validator import validate_walkerhill_timeline

FACT_FIELDS = ("property", "is_guest", "nights", "party_size", "has_child_under_13",
               "club_access", "included_meals", "booked", "room_minimal")


def _pairs(xs):
    return {(a, b) for a, b, *_ in xs}


def _prf(truth: set, got: set) -> str:
    hit = len(truth & got)
    r = hit / len(truth) if truth else 1.0
    p = hit / len(got) if got else 1.0
    return f"재현 {r:.0%} ({hit}/{len(truth)}) · 정밀 {p:.0%} ({hit}/{len(got)})"


def compare(n: int) -> dict:
    H = importlib.import_module(f"persona_blog{n:02d}")
    A = importlib.import_module(f"persona_blog{n:02d}_auto")
    hp, ap = H.PERSONA, A.PERSONA
    out: dict = {}

    print(f"=== blog{n:02d} · 손 vs 자동 ===\n")
    print("1층 · 추출")
    print("  사실")
    fact_ok = 0
    for f in FACT_FIELDS:
        hv, av = getattr(hp, f), getattr(ap, f)
        same = (set(hv) == set(av)) if isinstance(hv, tuple) else hv == av
        fact_ok += same
        print(f"    {'=' if same else '≠'} {f:20s} 손 {hv!r:40s} 자동 {av!r}")
    out["facts"] = (fact_ok, len(FACT_FIELDS))

    print("  성향 (미상 = None)")
    diffs, agree_unknown, n_tr = [], 0, 0
    for k, hv in hp.traits.items():
        av = ap.traits.get(k)
        n_tr += 1
        if hv is None and av is None:
            agree_unknown += 1; mark = "= 둘 다 미상"
        elif hv is None or av is None:
            mark = "≠ 미상 판단이 갈림"
        else:
            diffs.append(abs(hv - av)); mark = f"차이 {abs(hv - av):.1f}"
        hs = "미상" if hv is None else f"{hv:.1f}"
        as_ = "미상" if av is None else f"{av:.1f}"
        print(f"    {k:8s} 손 {hs:4s} 자동 {as_:4s}  {mark}")
    both = len(diffs)
    split = n_tr - both - agree_unknown
    mae = sum(diffs) / both if both else 0.0
    within = sum(1 for d in diffs if d <= 0.2)
    print(f"    → 둘 다 값 있음 {both}개 · 평균 차이 {mae:.2f} · 0.2 이내 {within}/{both} · "
          f"둘 다 미상 {agree_unknown} · 미상 판단 갈림 {split}")
    out["traits"] = dict(both=both, mae=mae, within=within, agree_unknown=agree_unknown, split=split)

    print("  정답")
    hv, av = set(H.TRUTH_VISITED), set(A.TRUTH_VISITED)
    print(f"    방문 집합   {_prf(hv, av)}")
    print(f"      자동만 {sorted(av - hv) or '—'}   손만 {sorted(hv - av) or '—'}")
    print(f"    식당 집합   {'일치' if set(H.TRUTH_RESTAURANTS) == set(A.TRUTH_RESTAURANTS) else '불일치'}"
          f"   손 {sorted(H.TRUTH_RESTAURANTS)}  자동 {sorted(A.TRUTH_RESTAURANTS)}")
    hm, am = _pairs(H.TRUTH_MEALS), _pairs(A.TRUTH_MEALS)
    print(f"    끼니        {_prf(hm, am)}   자동만 {sorted(am - hm) or '—'}")
    ho, ao = _pairs(H.TRUTH_ORDER_PAIRS), _pairs(A.TRUTH_ORDER_PAIRS)
    contra = sorted((a, b) for a, b in ao if (b, a) in ho)
    print(f"    순서 쌍     {_prf(ho, ao)} · 손과 반대인 쌍 {len(contra)}"
          + (f" {contra}" if contra else "  (같은 쌍이 적은 건 쌍을 고르는 단위가 달라서 — 프런트 vs 로비)"))
    hn = {k for k, v in H.TRUTH_NOT_VISITED.items() if str(v).startswith("◎")}
    an = {k for k, v in A.TRUTH_NOT_VISITED.items() if str(v).startswith("◎")}
    print(f"    금지(◎)     손 {sorted(hn)}  자동 {sorted(an)}")
    out["visited"] = (hv, av)

    print("\n2층 · 에이전트 v2 를 두 페르소나로 돌려 손 정답으로 채점")
    start = getattr(H, "START_AT", datetime(2025, 1, 31, 14, 0))
    rows = {}
    for label, P in (("손", hp), ("자동", ap)):
        segs, _ = agent_v2.run_agent(P, start, verbose=False)
        rep = validate_walkerhill_timeline(segs, enforce_stay_day=P.is_guest, nights=P.nights)
        r = evaluate(segs, H, reachable=agent_v2.reachable(P))
        o = "—" if r.order_rate is None else f"{r.order_rate:.0%}"
        seq = [s.venue or s.location for s in segs]
        places = []
        for p in seq:
            if not places or places[-1] != p:
                places.append(p)
        rows[label] = (rep.ok, r, places)
        print(f"  {label:3s} 정합성 {'PASS' if rep.ok else 'FAIL'}  집합 {r.recall:.0%}/{r.precision:.0%}  "
              f"식당 {r.restaurants_label}  순서 {o}  끼니 {r.meal_label}")
    same_places = set(rows["손"][2]) == set(rows["자동"][2])
    print(f"  → 에이전트가 간 곳 {'같음' if same_places else '다름'}")
    if not same_places:
        print(f"     손만   {sorted(set(rows['손'][2]) - set(rows['자동'][2]))}")
        print(f"     자동만 {sorted(set(rows['자동'][2]) - set(rows['손'][2]))}")
    out["agent"] = rows
    return out


if __name__ == "__main__":
    compare(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
