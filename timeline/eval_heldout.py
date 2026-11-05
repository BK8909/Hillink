"""
시험용 후기 채점 — v4 계수를 확정한 뒤에 만든 새 후기(blog11~)로 한 번만 돈다

  python3 eval_heldout.py 11 12 13 14 15
  python3 eval_heldout.py 32 34 41 42 43 50 51 52 59 60 61     # 봉인 3 (9/29)

비교 대상 (전부 고정 — 여기서 아무것도 고르지 않는다)
  v2 · v3              결정적 에이전트
  v4 기본값            v3 와 같은 계수
  v4 맞춘 계수         agent_v4.THETA_FIT (교차검증으로 고름) · 확률 선택이라 K_RUNS 번 평균
  v4 + 인기도 섞기     p = BLEND_ALPHA·v4 + (1−BLEND_ALPHA)·인기도 (blend_v4 · 46 폴드 전부 같은 α) — Brier 만
  인기도 기준선        개발용 체류(fit_v4.DEV_BLOGS)에서 장소마다 '간 비율' 을 확률로 쓰는 것 (에이전트 없음) — Brier 만

지표  재현 · 정밀 · F1 (한 사람의 동선) · Brier (장소마다 갈 확률 — 낮을수록 좋음)
"""
from __future__ import annotations

import importlib, sys
import agent_v2, agent_v3, agent_v4, fit_v4
from match import BASELINE_PLACES, TRANSIT

HELD = [int(x) for x in sys.argv[1:]] or [11, 12, 13, 14, 15]


def popularity(dev_stays):
    info = []
    for g, lab, m in dev_stays:
        reach = agent_v4.reachable(m.PERSONA)
        info.append((reach, set(m.TRUTH_VISITED)))
    def rate(p):
        cand = [x for x in info if p in x[0]]
        return sum(1 for x in cand if p in x[1]) / len(cand) if cand else 0.0
    return rate


def brier_pop(m, rate):
    reach = agent_v4.reachable(m.PERSONA)
    places = [p for p in reach if p not in BASELINE_PLACES and p not in TRANSIT and p not in getattr(m, "TRUTH_PASSED", {})]
    tr = set(m.TRUTH_VISITED)
    return sum(((1.0 if p in tr else 0.0) - rate(p)) ** 2 for p in places) / max(1, len(places))


def main():
    S = fit_v4.stays(HELD)
    rate = popularity(fit_v4.stays())
    rows = {"v2": [], "v3": [], "v4 기본값": [], "v4 맞춘 계수": [], "v4+인기도 섞기": [], "인기도 기준선": []}
    import blend_v4
    print(f"{'체류':12s} " + " | ".join(f"{k:>14s}" for k in rows))
    for g, lab, m in S:
        r = {
            "v2": fit_v4.run_stay(m, None, agent=agent_v2, k=1),
            "v3": fit_v4.run_stay(m, None, agent=agent_v3, k=1),
            "v4 기본값": fit_v4.run_stay(m, dict(agent_v4.THETA_DEFAULT), k=1),
            "v4 맞춘 계수": fit_v4.run_stay(m, agent_v4.THETA_FIT, k=agent_v4.K_RUNS),
        }
        v = blend_v4.v4_probs(m, agent_v4.THETA_FIT)
        a = agent_v4.BLEND_ALPHA
        r["v4+인기도 섞기"] = (float("nan"),) * 3 + (0, blend_v4.brier(m, lambda p: a * v.get(p, 0.0) + (1 - a) * rate(p)))
        r["인기도 기준선"] = (float("nan"),) * 3 + (0, brier_pop(m, rate))
        for k, v in r.items():
            rows[k].append(v)
        print(f"{lab:12s} " + " | ".join(
            (f"F1 {v[2]:.2f} B {v[4]:.3f}" if v[2] == v[2] else f"      B {v[4]:.3f}") for v in r.values()))
    print("\n평균")
    for k, v in rows.items():
        n = len(v)
        B = sum(x[4] for x in v) / n
        if v[0][2] == v[0][2]:
            R = sum(x[0] for x in v) / n; P = sum(x[1] for x in v) / n; F = sum(x[2] for x in v) / n
            print(f"  {k:14s} 재현 {R:.0%} · 정밀 {P:.0%} · F1 {F:.3f} · Brier {B:.3f} · 검증기 위반 {sum(x[3] for x in v)}")
        else:
            print(f"  {k:14s} {'':34s} Brier {B:.3f}")


if __name__ == "__main__":
    main()
