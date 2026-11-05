"""행동 차이의 출처 분해 · 미검수 성향 민감도 (10/20 · 총괄 C · 격리)

  python3 sensitivity.py              # 10팀 · 공통 가상 날짜 → out/sensitivity.json

출처 묶음(고객 입력) — 하나씩 '근거 없음 값'으로 돌려 차이를 잰다
  commitments  예약 · 포함 끼니 · 클럽(booked · included_meals · club_access)
  time         도착 시각 · 박 수 · 비투숙 퇴장 시각(start · nights · depart_by)
  party        인원 · 13세 미만 동반
  place        건물 · 도착 수단 · 객실 최소형
  traits       성향 7개 — 전부 자동 추출 초안(사람 검수 없음 · 10팀 손 정답본도 자동값과 같음)
모델 기본 규칙 몫 = '중립 손님'(모든 입력을 근거 없음 값으로, 투숙 여부만 유지)이 이미 하는 행동 — 고객 입력과 상관없이 나오는 부분.

성향 민감도(실제 고객 값을 바꾸지 않는다 — 계산 민감도로만 보고)
  S0 성향 전부 없음 · S1 하나씩 ±0.25(0.25~1.0 눈금 안) · S2 계수 lam_trait 0.5 · 1.0(공용 기본 THETA_DEFAULT 값) — 계수 쪽 가정
거리 L1 = 행동별 '체류 중 한 번이라도 고른 확률' 차의 합(체크인 절차 제외) — 기대 '다르게 고른 행동 수'.
"""
from __future__ import annotations

import argparse, itertools, json
from datetime import time
from pathlib import Path

import core
from ablate import COMMON_DAY, TRAITS

GROUPS = {
    "commitments": dict(booked=(), included_meals=(), club_access=False),
    "time": None,          # 아래 neutral_group 에서 따로
    "party": dict(party_size=2, has_child_under_13=False),
    "place": dict(property="GRAND", arrival=None, room_minimal=False),
    "traits": None,
}


def l1(p: dict, q: dict) -> float:
    return round(sum(abs(p.get(k, 0) - q.get(k, 0)) for k in set(p) | set(q)), 4)


def neutral_group(p, start, g):
    if g == "traits":
        return core.with_fields(p, traits={k: None for k in p.traits}), start
    if g == "time":
        kw = dict(nights=1) if p.is_guest else dict(depart_by=time(20, 0))
        return core.with_fields(p, **kw), (start.replace(hour=14, minute=30) if p.is_guest else start)
    return core.with_fields(p, **GROUPS[g]), start


def neutral_customer(p, start):
    q = p
    s = start
    for g in GROUPS:
        q, s = neutral_group(q, s, g)
    return q, s


def decompose(blog, k):
    p, s = core.load_persona(blog)
    s = core.at_common_date(s, COMMON_DAY)
    base = core.place_p(core.run(p, s, k))
    nq, ns = neutral_customer(p, s)
    neutral = core.place_p(core.run(nq, ns, k))
    groups = {}
    for g in GROUPS:
        q, qs = neutral_group(p, s, g)
        groups[g] = l1(base, core.place_p(core.run(q, qs, k)))
    return dict(start=s.isoformat(), place_p=base, neutral_place_p=neutral, from_neutral_l1=l1(base, neutral), group_removal_l1=groups)


def trait_sensitivity(blog, k):
    p, s = core.load_persona(blog)
    s = core.at_common_date(s, COMMON_DAY)
    base_runs = core.run(p, s, k)
    base = core.place_p(base_runs)
    out = dict(S0_none=l1(base, core.place_p(core.run(core.with_fields(p, traits={t: None for t in p.traits}), s, k))))
    s1 = {}
    for t in TRAITS:
        v = p.traits.get(t)
        if v is None:
            continue
        for dv in (-0.25, 0.25):
            nv = round(v + dv, 2)
            if not 0.25 <= nv <= 1.0:
                continue
            s1[f"{t} {v:g}→{nv:g}"] = l1(base, core.place_p(core.run(core.with_fields(p, traits={**p.traits, t: nv}), s, k)))
    out["S1_pm025"] = s1
    out["S2_lam"] = {str(lam): l1(base, core.place_p(core.run(p, s, k, theta=dict(lam_trait=lam)))) for lam in (0.5, 1.0)}
    return out


def pairwise(k):
    """10팀 서로 간 거리 — 지금 입력 그대로 vs 성향만 지운 입력. 성향이 팀 차이에 얼마나 보태는지."""
    full, notrait = {}, {}
    for b in core.TEAMS:
        p, s = core.load_persona(b)
        s = core.at_common_date(s, COMMON_DAY)
        full[b] = core.place_p(core.run(p, s, k))
        notrait[b] = core.place_p(core.run(core.with_fields(p, traits={t: None for t in p.traits}), s, k))
    pairs = list(itertools.combinations(core.TEAMS, 2))
    mf = sum(l1(full[a], full[b]) for a, b in pairs) / len(pairs)
    mn = sum(l1(notrait[a], notrait[b]) for a, b in pairs) / len(pairs)
    changed = [f"{a}~{b}" for a, b in pairs if abs(l1(full[a], full[b]) - l1(notrait[a], notrait[b])) > 1e-9]
    return dict(mean_pair_l1_full=round(mf, 4), mean_pair_l1_no_traits=round(mn, 4), pairs_changed_by_traits=changed, n_pairs=len(pairs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=core.K)
    ap.add_argument("--out", default=str(core.HERE / "out"))
    a = ap.parse_args()
    res = dict(meta=dict(common_day=COMMON_DAY.date().isoformat(), k=a.k, seed_base=core.SEED_BASE,
                         note="S1 · S2 는 계산 민감도 — 고객 성향을 바꿔 쓴 결과가 아님. 성향 값은 모두 자동 추출 초안"),
               decompose={b: decompose(b, a.k) for b in core.TEAMS},
               traits={b: trait_sensitivity(b, a.k) for b in core.TEAMS},
               pairwise=pairwise(a.k))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "sensitivity.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({b: (r["from_neutral_l1"], r["group_removal_l1"]) for b, r in res["decompose"].items()}, ensure_ascii=False))
    print(json.dumps(res["traits"], ensure_ascii=False))
    print(json.dumps(res["pairwise"], ensure_ascii=False))


if __name__ == "__main__":
    main()
