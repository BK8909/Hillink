"""
v4 계수를 교차검증으로 맞춘다 — "역설계" 를 과적합 없이 하는 방법

  python3 fit_v4.py            # 탐색 + 교차검증 + 결과 표 (fit_v4_result.json)
  python3 fit_v4.py --n 600    # 후보 계수 개수

무엇을 하나
  1. 계수 후보 N 개를 무작위로 뽑는다 (+ v3 와 같은 기본값 · 성향 끔 · 확률 선택 몇 개)
  2. 후보마다 개발용 체류 12개(후기 10편)를 전부 돌려 체류별 점수를 저장한다
     점수 = 방문 집합 F1 (재현 · 정밀의 조화평균). 확률 선택(tau>0)이면 K 번 돌린 평균
  3. 후기 하나씩 빼는 교차검증 (10 폴드, 같은 후기의 체류 둘은 같은 폴드):
     나머지 9편에서 가장 좋은 후보를 고르고 → 뺀 후기로 채점. 모든 체류가 딱 한 번씩 '처음 보는' 쪽이 된다
     → 이 평균이 "계수를 데이터로 맞추는 방법" 자체의 성능 추정 (고른 뒤 같은 데이터로 잰 숫자가 아니다)
  4. 기준선(v2 · v3 · 성향 끔)은 고르지 않고 같은 체류로 그대로 잰다
  5. 12개 전부로 고른 계수가 최종 v4 계수 (THETA_FIT) — 새 시험용 후기에서 한 번만 잰다

정합성: 모든 실행을 검증기에 통과시켜 위반 수도 센다 (구조상 0 이어야 한다).
"""

from __future__ import annotations

import importlib, json, math, random, sys, time
from multiprocessing import Pool
from pathlib import Path

import agent_v4
from match import evaluate
from walkerhill_timeline_validator import validate_walkerhill_timeline

K_SAMPLES = 6
SEED = 20260924


def dev_blogs():
    """개발용 후기 번호 — persona_blogNN.py 가 있고, 봉인 대기(sealed.SEALED_WAIT)도 못 씀도 아닌 것 전부.
    9/24 v4 는 1~10 (체류 12) 로 맞췄다. 2차 정답 확인 뒤(9/29)는 46편 안팎."""
    import glob, re
    from sealed import SEALED_WAIT, unusable
    nums = sorted(int(m.group(1)) for f in glob.glob(str(Path(__file__).with_name("persona_blog[0-9][0-9].py")))
                  if (m := re.fullmatch(r"persona_blog(\d\d)\.py", Path(f).name)))
    out = []
    for n in nums:
        if n in SEALED_WAIT:
            continue
        if unusable(importlib.import_module(f"persona_blog{n:02d}")):
            continue
        out.append(n)
    return out


DEV_BLOGS = dev_blogs()


class _Alt:
    def __init__(self, mod):
        for f in ("PERSONA", "START_AT", "TRUTH_VISITED", "TRUTH_PASSED", "TRUTH_NOT_VISITED",
                  "TRUTH_UNREACHABLE", "TRUTH_RESTAURANTS", "TRUTH_ORDER_PAIRS", "TRUTH_MEALS"):
            if hasattr(mod, f + "_ALT"):
                setattr(self, f, getattr(mod, f + "_ALT"))


def stays(blogs=DEV_BLOGS):
    from datetime import datetime
    out = []
    for n in blogs:
        m = importlib.import_module(f"persona_blog{n:02d}")
        out.append((n, f"blog{n:02d}", m))
        if hasattr(m, "PERSONA_ALT"):
            out.append((n, f"blog{n:02d}_ALT", _Alt(m)))
    return out


def run_stay(m, theta, agent=agent_v4, k=None):
    from datetime import datetime
    start = getattr(m, "START_AT", datetime(2025, 1, 31, 14, 0))
    reach = agent.reachable(m.PERSONA)
    reps = (K_SAMPLES if (theta or {}).get("tau", 0) > 0 else 1) if k is None else k
    R = P = F = 0.0; bad = 0
    from collections import Counter
    from match import BASELINE_PLACES, TRANSIT, visits_from_segments
    seen = Counter()
    for i in range(reps):
        if agent is agent_v4:
            segs, _ = agent.run_agent(m.PERSONA, start, verbose=False, theta=theta, rng=random.Random(SEED + i))
        else:
            segs, _ = agent.run_agent(m.PERSONA, start, verbose=False)
        bad += 0 if validate_walkerhill_timeline(segs, enforce_stay_day=m.PERSONA.is_guest,
                                                 nights=m.PERSONA.nights).ok else 1
        r = evaluate(segs, m, reachable=reach)
        for pl in {v.place for v in visits_from_segments(segs)}:
            seen[pl] += 1
        f = 2 * r.recall * r.precision / (r.recall + r.precision) if (r.recall + r.precision) else 0.0
        R += r.recall; P += r.precision; F += f
    # 확률 점수(Brier) — 갈 수 있는 곳마다 '갈 확률' 과 후기(갔다 1 · 아니면 0)의 제곱 차이 평균. 낮을수록 좋다
    #   한 명의 정확한 동선이 아니라 "여러 번 돌렸을 때 어디에 얼마나 가나" 를 잰다 — 매출 대조와 같은 방향
    places = [p for p in reach | set(seen) if p not in BASELINE_PLACES and p not in TRANSIT
              and p not in getattr(m, "TRUTH_PASSED", {})]
    truth = set(m.TRUTH_VISITED)
    brier = sum(((1.0 if p in truth else 0.0) - seen[p] / reps) ** 2 for p in places) / max(1, len(places))
    return R / reps, P / reps, F / reps, bad, brier


def popularity(dev_stays):
    """장소마다 '갈 수 있는 사람 중 간 비율' — 에이전트 없는 기준선 (eval_heldout 과 같은 정의)"""
    info = [(agent_v4.reachable(m.PERSONA), set(m.TRUTH_VISITED)) for _, _, m in dev_stays]
    def rate(p):
        cand = [x for x in info if p in x[0]]
        return sum(1 for x in cand if p in x[1]) / len(cand) if cand else 0.0
    return rate


def brier_pop(m, rate):
    from match import BASELINE_PLACES, TRANSIT
    reach = agent_v4.reachable(m.PERSONA)
    places = [p for p in reach if p not in BASELINE_PLACES and p not in TRANSIT and p not in getattr(m, "TRUTH_PASSED", {})]
    truth = set(m.TRUTH_VISITED)
    return sum(((1.0 if p in truth else 0.0) - rate(p)) ** 2 for p in places) / max(1, len(places))


def sample_theta(rng):
    return dict(
        w_wait=rng.uniform(0, 2), w_travel=rng.uniform(0, 1.5), lam_trait=rng.choice([0, 0.25, 0.5, 0.75, 1.0, 1.5]),
        meal=6.0, included=rng.uniform(2, 10), meal_other=rng.uniform(-3, 1), bfast_room=rng.uniform(0, 3),
        kids=rng.uniform(0, 2), takeout=rng.uniform(0, 2), room_rest=rng.uniform(-1, 1.5),
        booked=rng.uniform(0, 10), incl_block=rng.choice([99.0, rng.uniform(0, 8)]),
        gap_fill=rng.choice([0.0, 1.0]), tau=rng.choice([0.0, 0.0, 0.5, 1.0, 2.0]),
    )


def _eval(args):
    idx, theta = args
    S = stays(DEV_BLOGS)
    return idx, [run_stay(m, theta) for _, _, m in S]


def main(n_cfg=400):
    t0 = time.time()
    rng = random.Random(SEED)
    D = dict(agent_v4.THETA_DEFAULT)
    named = {"v3 과 같은 기본값": D, "성향 끔 (lam 0)": dict(D, lam_trait=0.0),
             "기본값 + 확률 선택": dict(D, tau=1.0, incl_block=4.0)}
    cfgs = list(named.values()) + [sample_theta(rng) for _ in range(n_cfg)]
    S = stays()
    labels = [lab for _, lab, _ in S]
    groups = [n for n, _, _ in S]
    with Pool(2) as pool:
        res = dict(pool.map(_eval, list(enumerate(cfgs)), chunksize=4))
    scores = [res[i] for i in range(len(cfgs))]      # [cfg][stay] = (R, P, F, bad)
    bad_total = sum(s[3] for sc in scores for s in sc)

    # 기준선 v2 · v3 (결정적)
    import agent_v2, agent_v3
    base = {}
    for nm, ag in (("v2", agent_v2), ("v3", agent_v3)):  # 결정적 · 고르지 않음
        base[nm] = [run_stay(m, None, agent=ag, k=1) for _, _, m in S]
    # 인기도 기준선 — 후기 하나씩 빼고 나머지의 '간 비율' 로 그 후기를 잰다 (Brier 만)
    pop = []
    for i, (g, _, m) in enumerate(S):
        others = [x for j, x in enumerate(S) if groups[j] != g]
        pop.append((float("nan"), float("nan"), float("nan"), 0, brier_pop(m, popularity(others))))
    base["인기도 (하나씩 빼기)"] = pop

    # 교차검증 — 후기 하나씩 빼기
    test = [None] * len(S); chosen = []
    test_b = [None] * len(S); chosen_b = []
    for g in sorted(set(groups)):
        tr = [i for i, x in enumerate(groups) if x != g]; te = [i for i, x in enumerate(groups) if x == g]
        best = max(range(len(cfgs)), key=lambda c: sum(scores[c][i][2] for i in tr) / len(tr))
        chosen.append((g, best))
        for i in te:
            test[i] = scores[best][i]
        best_b = min(range(len(cfgs)), key=lambda c: sum(scores[c][i][4] for i in tr) / len(tr))
        chosen_b.append((g, best_b))
        for i in te:
            test_b[i] = scores[best_b][i]

    def avg(rows):
        return tuple(sum(r[j] for r in rows) / len(rows) for j in (0, 1, 2, 4))

    n_blogs = len(set(groups))
    KEYS = ("recall", "precision", "f1", "brier")

    full_best = max(range(len(cfgs)), key=lambda c: avg(scores[c])[2])
    out = dict(
        n_cfg=len(cfgs), dev_blogs=DEV_BLOGS, stays=labels, seconds=round(time.time() - t0),
        violations=bad_total,
        cv=dict(zip(KEYS, avg(test))),
        cv_per_stay={labels[i]: dict(zip(KEYS, (test[i][0], test[i][1], test[i][2], test[i][4]))) for i in range(len(S))},
        cv_brier_select=dict(zip(KEYS, avg(test_b))),
        fold_theta_brier=[dict(blog=g, **cfgs[c]) for g, c in chosen_b],
        theta_fit_brier=cfgs[min(range(len(cfgs)), key=lambda c: avg(scores[c])[3])],
        baselines={nm: dict(zip(KEYS, avg(v))) for nm, v in base.items()},
        named={nm: dict(zip(KEYS, avg(scores[i]))) for i, nm in enumerate(named)},
        fit_in_sample=dict(zip(KEYS, avg(scores[full_best]))),
        theta_fit=cfgs[full_best],
        fold_theta=[dict(blog=g, **cfgs[c]) for g, c in chosen],
    )
    Path(__file__).with_name("fit_v4_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    pr = lambda d: (f"재현 {d['recall']:.0%} · 정밀 {d['precision']:.0%} · F1 {d['f1']:.3f} · Brier {d['brier']:.3f}"
                    if d['f1'] == d['f1'] else f"{'':34s}Brier {d['brier']:.3f}")
    print(f"후보 계수 {len(cfgs)}개 · 후기 {n_blogs}편 · 체류 {len(S)}개 · {out['seconds']}초 · 검증기 위반 {bad_total}")
    print(f"\n개발용 {len(S)} 체류 — 같은 데이터로 잰 것 (고르지 않은 기준선)")
    for nm, d in out["baselines"].items():
        print(f"  {nm:22s} {pr(d)}")
    for nm, d in out["named"].items():
        print(f"  v4 {nm:19s} {pr(d)}")
    print(f"\n교차검증 (후기 하나씩 빼고 고른 계수로 뺀 후기를 잼) — v4 방법의 성능 추정")
    print(f"  {'v4 교차검증 (F1 로 고름)':22s} {pr(out['cv'])}")
    print(f"  {'v4 교차검증 (Brier 로 고름)':22s} {pr(out['cv_brier_select'])}")
    print(f"  (참고) 전부로 고르고 같은 체류로 잰 값: {pr(out['fit_in_sample'])} ← 낙관적, 보고용 아님")
    print(f"\n최종 계수 ({len(S)} 체류 전부로 고름):")
    print("  " + " · ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in out["theta_fit"].items()))
    print("\n폴드별로 고른 계수 — 흔들림을 본다")
    keys = ["lam_trait", "w_wait", "w_travel", "included", "meal_other", "booked", "incl_block", "gap_fill", "tau"]
    print("  " + "blog  " + "  ".join(f"{k:>10s}" for k in keys))
    for ft in out["fold_theta"]:
        print(f"  {ft['blog']:02d}    " + "  ".join(f"{ft[k]:10.2f}" for k in keys))
    print("\nBrier 로 고른 폴드별 계수")
    for ft in out["fold_theta_brier"]:
        print(f"  {ft['blog']:02d}    " + "  ".join(f"{ft[k]:10.2f}" for k in keys))
    return out


if __name__ == "__main__":
    if "--dev" in sys.argv:                       # 예: --dev 1-10  (9/24 와 같은 12 체류)
        a, b = sys.argv[sys.argv.index("--dev") + 1].split("-")
        DEV_BLOGS = [n for n in DEV_BLOGS if int(a) <= n <= int(b)]
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 400
    main(n)
