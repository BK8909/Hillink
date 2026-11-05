"""
조건부 인기도 기준선 — "간 비율" 을 사실(투숙 · 건물 · 예약 · 포함 끼니 · 아이)로 나눠서 낸다

  python3 cond_pop.py            # 개발용 전체 · 후기 하나씩 빼는 교차검증 · cond_pop_result.json

왜
  인기도(갈 수 있는 사람 중 간 비율)가 v4 와 동률이다. 그런데 인기도는 손님 사정을 모른다 —
  비투숙은 객실에 못 가고, 더뷔페를 예약한 사람은 더뷔페에 간다. 그 사실 몇 개만 붙인 인기도가
  v4 를 이기면 "시뮬레이션 에이전트는 평상시 분포 예측에 보태는 게 없다" 는 뜻이고, 못 이기면
  에이전트가 사실을 쓰는 방식이 맞다는 뜻이다.

어떻게
  장소 p 의 확률 = 조건이 같은 사람들 중 간 비율. 표본이 적으니 넓은 조건으로 물러난다(backoff):
    1. 예약(booked)에 p 가 있으면 → 예약한 사람들 중 간 비율 (거의 1)
    2. 포함 끼니(included_meals)에 p 가 있으면 → 포함된 사람들 중 간 비율
    3. (투숙 여부, 건물) 이 같은 사람들 중 간 비율 — 표본 k 가 적으면 전체 비율과 섞는다: (간 수 + m·전체) / (k + m)
  후보 조건 묶음 몇 개를 같은 폴드로 재서 비교한다. 지표는 Brier (전체 칸 · 갈릴 만한 칸).
"""

from __future__ import annotations

import json, time
from collections import defaultdict
from pathlib import Path

import agent_v4, fit_v4, blend_v4
from match import BASELINE_PLACES, TRANSIT


def key_of(m, cond):
    p = m.PERSONA
    parts = []
    if "guest" in cond: parts.append(("guest", bool(p.is_guest)))
    if "property" in cond: parts.append(("property", p.property if p.is_guest else "NONGUEST"))
    if "club" in cond: parts.append(("club", bool(p.club_access)))
    if "child" in cond: parts.append(("child", bool(p.has_child_under_13)))
    return tuple(parts)


def table(stays, cond):
    """장소마다: 전체 (간 수, 갈 수 있는 수) · 조건 키별 (간 수, 갈 수 있는 수) · 예약자 · 포함자"""
    glob = defaultdict(lambda: [0, 0]); by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    booked = defaultdict(lambda: [0, 0]); incl = defaultdict(lambda: [0, 0])
    for _, _, m in stays:
        reach = agent_v4.reachable(m.PERSONA); truth = set(m.TRUTH_VISITED); k = key_of(m, cond)
        bk = set(m.PERSONA.booked or ()); im = {pl for _, pl in (m.PERSONA.included_meals or ())}
        for p in reach:
            y = 1 if p in truth else 0
            glob[p][0] += y; glob[p][1] += 1
            by[k][p][0] += y; by[k][p][1] += 1
            if p in bk: booked[p][0] += y; booked[p][1] += 1
            if p in im: incl[p][0] += y; incl[p][1] += 1
    return glob, by, booked, incl


def rate_fn(tbl, m, cond, shrink=4.0, use_booked=True, use_incl=True):
    glob, by, booked, incl = tbl
    k = key_of(m, cond); bk = set(m.PERSONA.booked or ()); im = {pl for _, pl in (m.PERSONA.included_meals or ())}
    def rate(p):
        g = glob[p][0] / glob[p][1] if glob[p][1] else 0.0
        if use_booked and p in bk and booked[p][1] >= 2:
            return (booked[p][0] + 1) / (booked[p][1] + 1)          # 예약자 중 간 비율 (라플라스)
        if use_incl and p in im and incl[p][1] >= 2:
            return (incl[p][0] + 1) / (incl[p][1] + 1)
        c = by[k][p]
        return (c[0] + shrink * g) / (c[1] + shrink) if c[1] else g
    return rate


def contested(rate_plain, p):
    return 0.15 <= rate_plain(p) <= 0.85


def main():
    t0 = time.time()
    S = fit_v4.stays(fit_v4.DEV_BLOGS); groups = [g for g, _, _ in S]
    P = [blend_v4.v4_probs(m, agent_v4.THETA_FIT) for _, _, m in S]
    CONDS = {
        "인기도 (조건 없음)": dict(cond=(), use_booked=False, use_incl=False),
        "+ 예약 · 포함 끼니": dict(cond=(), use_booked=True, use_incl=True),
        "+ 투숙 여부": dict(cond=("guest",), use_booked=True, use_incl=True),
        "+ 투숙 · 건물": dict(cond=("guest", "property"), use_booked=True, use_incl=True),
        "+ 투숙 · 건물 · 클럽": dict(cond=("guest", "property", "club"), use_booked=True, use_incl=True),
        "+ 투숙 · 건물 · 클럽 · 아이": dict(cond=("guest", "property", "club", "child"), use_booked=True, use_incl=True),
    }
    res = {nm: {"all": [], "hard": []} for nm in CONDS}
    res["v4만"] = {"all": [], "hard": []}
    res["v4 + 인기도 (α 0.4)"] = {"all": [], "hard": []}
    res["v4 + 조건부(투숙·건물) (α 0.4)"] = {"all": [], "hard": []}
    nhard = 0; nall = 0
    for g in sorted(set(groups)):
        tr = [S[i] for i, x in enumerate(groups) if x != g]; te = [i for i, x in enumerate(groups) if x == g]
        tbls = {nm: table(tr, c["cond"]) for nm, c in CONDS.items()}
        plain = None
        for i in te:
            m = S[i][2]; truth = set(m.TRUTH_VISITED); places = blend_v4.places_of(m)
            rates = {nm: rate_fn(tbls[nm], m, c["cond"], use_booked=c["use_booked"], use_incl=c["use_incl"]) for nm, c in CONDS.items()}
            plain = rates["인기도 (조건 없음)"]; cond_r = rates["+ 투숙 · 건물"]
            v = P[i]
            fns = dict(rates)
            fns["v4만"] = lambda p, v=v: v.get(p, 0.0)
            fns["v4 + 인기도 (α 0.4)"] = lambda p, v=v, r=plain: 0.4 * v.get(p, 0.0) + 0.6 * r(p)
            fns["v4 + 조건부(투숙·건물) (α 0.4)"] = lambda p, v=v, r=cond_r: 0.4 * v.get(p, 0.0) + 0.6 * r(p)
            hard = [p for p in places if contested(plain, p)]
            nall += len(places); nhard += len(hard)
            for nm, fn in fns.items():
                res[nm]["all"].append(sum(((1.0 if p in truth else 0.0) - fn(p)) ** 2 for p in places) / max(1, len(places)))
                if hard:
                    res[nm]["hard"].append(sum(((1.0 if p in truth else 0.0) - fn(p)) ** 2 for p in hard) / len(hard))
    avg = lambda xs: sum(xs) / len(xs)
    out = {nm: dict(brier=avg(v["all"]), brier_hard=avg(v["hard"])) for nm, v in res.items()}
    out["_meta"] = dict(stays=len(S), cells=nall, hard_cells=nhard, seconds=round(time.time() - t0))
    Path(__file__).with_name("cond_pop_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"체류 {len(S)} · 칸 {nall} (갈릴 만한 칸 {nhard}) · {out['_meta']['seconds']}초 · 후기 하나씩 빼는 교차검증\n")
    print(f"  {'':34s} {'Brier 전체':>10s} {'갈릴 만한 칸':>12s}")
    for nm, v in out.items():
        if nm.startswith("_"): continue
        print(f"  {nm:34s} {v['brier']:10.3f} {v['brier_hard']:12.3f}")
    return out


if __name__ == "__main__":
    main()
