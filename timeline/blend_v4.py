"""
v4 확률 + 인기도 섞기 — 분포 예측(Brier)에서 인기도 기준선을 넘나

  python3 blend_v4.py            # 개발용 전체 · 후기 하나씩 빼는 교차검증 · 결과 blend_v4_result.json

왜
  46편 재맞춤(fit_v4)에서 동선 재현(F1)은 v4 가 낫지만 분포(Brier)는 인기도(0.107)가 v4(0.125)보다 낫다.
  v4 는 한 사람을 여러 번 돌려도 거의 같은 곳에 가서 "갈 확률" 이 0 아니면 1 에 가깝다 — 틀리면 크게 깎인다.
  인기도는 "갈 수 있는 사람 중 간 비율" 이라 중간값을 내서 안 깎이지만 개인 사정(예약 · 포함 끼니)을 모른다.
  둘을 p = α·v4 + (1−α)·인기도 로 섞으면 개인 사정은 v4 가, 바닥은 인기도가 댄다.

어떻게
  1. 체류마다 v4 를 K 번 돌려 장소별 '간 비율' 을 만든다 (tau 후보마다 — tau 가 클수록 퍼진다)
  2. 후기 하나씩 빼고: 나머지로 인기도를 만들고, 나머지에서 Brier 가 가장 낮은 (tau, α) 를 고른 뒤, 뺀 후기를 잰다
     → 이 평균이 "섞는 방법" 의 성능 추정. 고른 뒤 같은 데이터로 잰 숫자가 아니다
  3. 인기도만 · v4만 도 같은 폴드로 잰다

지표는 Brier 만 (동선 F1 은 v4 그대로 — 섞기는 확률에만 손댄다).
"""

from __future__ import annotations

import importlib, json, random, sys, time
from collections import Counter
from pathlib import Path

import agent_v4
import fit_v4
from match import BASELINE_PLACES, TRANSIT, visits_from_segments

TAUS = (0.5, 1.0, 2.0, 4.0)
ALPHAS = tuple(i / 10 for i in range(0, 11))
K = 12


def v4_probs(m, theta):
    from datetime import datetime
    start = getattr(m, "START_AT", datetime(2025, 1, 31, 14, 0))
    seen = Counter()
    for i in range(K):
        segs, _ = agent_v4.run_agent(m.PERSONA, start, verbose=False, theta=theta, rng=random.Random(fit_v4.SEED + i))
        for pl in {v.place for v in visits_from_segments(segs)}:
            seen[pl] += 1
    return {p: seen[p] / K for p in seen}


def places_of(m):
    reach = agent_v4.reachable(m.PERSONA)
    return [p for p in reach if p not in BASELINE_PLACES and p not in TRANSIT and p not in getattr(m, "TRUTH_PASSED", {})]


def brier(m, prob):
    truth = set(m.TRUTH_VISITED)
    pl = places_of(m)
    return sum(((1.0 if p in truth else 0.0) - prob(p)) ** 2 for p in pl) / max(1, len(pl))


def main():
    t0 = time.time()
    S = fit_v4.stays(fit_v4.DEV_BLOGS)
    groups = [g for g, _, _ in S]
    base = dict(json.load(open(Path(__file__).with_name("fit_v4_result.json"), encoding="utf-8"))["theta_fit_brier"])
    thetas = {tau: dict(base, tau=tau) for tau in TAUS}
    # 1. v4 확률 (tau 마다)
    P = {tau: [v4_probs(m, th) for _, _, m in S] for tau, th in thetas.items()}
    print(f"v4 확률 {len(S)} 체류 × tau {len(TAUS)} × {K}회 — {round(time.time() - t0)}초")

    def blend_brier(i, tau, alpha, pop):
        m = S[i][2]
        v = P[tau][i]
        return brier(m, lambda p: alpha * v.get(p, 0.0) + (1 - alpha) * pop(p))

    # 2. 교차검증
    test = []; chosen = []; test_pop = []; test_v4 = {tau: [] for tau in TAUS}
    for g in sorted(set(groups)):
        tr = [i for i, x in enumerate(groups) if x != g]; te = [i for i, x in enumerate(groups) if x == g]
        pop_tr = fit_v4.popularity([S[i] for i in tr])
        # 안쪽: 학습 체류 각각을 다시 하나씩 빼서 인기도를 만들면 너무 느리다 → 학습 체류의 인기도는 tr 전체로 (약간 낙관)
        best = min(((tau, a) for tau in TAUS for a in ALPHAS),
                   key=lambda ta: sum(blend_brier(i, ta[0], ta[1], pop_tr) for i in tr) / len(tr))
        chosen.append((g, best))
        for i in te:
            test.append(blend_brier(i, best[0], best[1], pop_tr))
            test_pop.append(brier(S[i][2], pop_tr))
            for tau in TAUS:
                test_v4[tau].append(brier(S[i][2], lambda p, v=P[tau][i]: v.get(p, 0.0)))
    avg = lambda xs: sum(xs) / len(xs)
    # 3. 전부로 고른 (tau, α)
    pop_all = fit_v4.popularity(S)
    full = min(((tau, a) for tau in TAUS for a in ALPHAS),
               key=lambda ta: sum(blend_brier(i, ta[0], ta[1], pop_all) for i in range(len(S))) / len(S))
    out = dict(
        stays=[lab for _, lab, _ in S], K=K, taus=TAUS, alphas=ALPHAS, seconds=round(time.time() - t0),
        cv_blend=avg(test), cv_pop=avg(test_pop), cv_v4={str(t): avg(v) for t, v in test_v4.items()},
        fold_choice=[dict(blog=g, tau=t, alpha=a) for g, (t, a) in chosen],
        choice_all=dict(tau=full[0], alpha=full[1]),
        per_stay={S[i][1]: dict(blend=test[i], pop=test_pop[i], v4=test_v4[full[0]][i]) for i in range(len(S))},
    )
    Path(__file__).with_name("blend_v4_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n교차검증 Brier (후기 하나씩 빼기 · {len(set(groups))} 폴드 · 체류 {len(S)})")
    print(f"  인기도만            {out['cv_pop']:.3f}")
    for tau in TAUS:
        print(f"  v4만 (tau {tau})      {out['cv_v4'][str(tau)]:.3f}")
    print(f"  v4 + 인기도 섞기    {out['cv_blend']:.3f}   ← 폴드마다 (tau, α) 를 고름")
    cc = Counter((t, a) for _, (t, a) in chosen)
    print(f"\n폴드별로 고른 (tau, α): {dict(cc)}")
    print(f"전부로 고른 (tau, α): {full}")
    return out


if __name__ == "__main__":
    main()
