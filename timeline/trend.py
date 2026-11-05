"""
SNS 신호 → 선택 가중 (10/13 · 조정값 trend_w · 기본 꺼짐)

  python3 trend.py            # 신호 강도 1 로 표를 찍는다
  python3 trend.py 0.5        # 강도 0.5
  WH_TREND=1 python3 generate.py ...   # 손님 만들 때 dining_pref 를 SNS 쪽으로 기운다 (화면은 조정값 'SNS 신호 가중')

무엇을 바꾸나
  손님은 목적별로 "가고 싶은 식당" 하나를 dining_pref.csv 에서 뽑는다 (generate.pick_prefer).
  SNS 후기(trend_signals.csv · 업장마다 수동 검수한 게시물의 목적 건수)는 "이 업장에 간 사람의 목적 구성" P(목적 | 업장) 을 준다.
  이 조정값은 그 업장을 가고 싶어 하는 손님의 목적 구성을 SNS 구성 쪽으로 옮긴다.
  업장을 가고 싶어 하는 손님 수(전체 무게)는 그대로 둔다 — SNS 게시물 수는 "누가" 가는지는 말해도 "몇 명" 가는지는 말하지 않기 때문.

어떻게
  1. 모델 사전 m_p = P(목적 p | 이 업장을 가고 싶음) ∝ 목적 섞기(purpose_mix) × dining_pref[p][업장]
  2. SNS 구성 s_p = (SNS 건수 + K × m_p) / (표본 + K)   — 표본이 적어서 모델 사전 K=10 건어치를 섞는다 (0건 목적이 0 이 되지 않게)
  3. 목표 t_p ∝ m_p^(1−w) × s_p^w   — w = 조정값 강도 (0 = 그대로, 1 = SNS 구성)
  4. dining_pref[p][업장] = min(0.8, C × t_p / 목적 섞기_p),  C = 원래 이 업장 전체 무게 → 목적 행의 나머지 업장은 비율대로 줄이거나 늘린다
     0.8 상한: 한 목적 손님의 80% 넘게 한 업장만 가고 싶어 하게 만들지 않는다. 상한에 걸리면 목표에 못 미친다 (그 몫은 '목적 손님 수 자체가 적다' 는 신호)
  추정 판정 게시물은 EST_W (기본 1) 배로 센다. 0.5 로 두면 '명시' 쪽 무게가 커진다.
  출처유형 열 — 문장형(캡션 검수 · 기본) 과 집계형(플레이스 태그 건수) 을 따로 둔다. WH_TREND_SRC=집계형 이면 그 줄을 쓴다.
  집계형은 분모가 커서 게시 성향이 거의 없다고 보고, 문장형의 게시 성향(propensity)을 재는 기준으로도 쓴다.

손님 생성의 난수 흐름은 바뀌지 않는다 (pick_prefer 는 가중치와 상관없이 같은 횟수로 난수를 쓴다) — 같은 손님에게 '가고 싶은 식당' 만 달라진다.
"""
from __future__ import annotations

import csv, os, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
K = 10.0
CAP = 0.8
EST_W = float(os.environ.get("WH_TREND_EST", "1"))


SRC_TYPE = os.environ.get("WH_TREND_SRC", "문장형")   # 문장형 (인스타 · 블로그 캡션 검수) / 집계형 (네이버 플레이스 · 캐치테이블 태그 건수)


def load_signals(path=HERE / "trend_signals.csv", src_type=None):
    """업장 → {목적: 가중 건수}, 표본(가중), 출처. 출처유형 열이 있으면 src_type (기본 WH_TREND_SRC · 문장형) 줄만 쓴다"""
    src_type = SRC_TYPE if src_type is None else src_type
    out = {}
    if not Path(path).exists():
        return out
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        if r.get("출처유형", "문장형") != src_type:
            continue
        v = out.setdefault(r["업장"], {"counts": {}, "src": r["출처"], "raw": {}, "type": src_type})
        c = float(r["명시"] or 0) + EST_W * float(r["추정"] or 0)
        v["counts"][r["목적"]] = c
        v["raw"][r["목적"]] = {k: r.get(k, "") for k in ("건수", "명시", "추정", "2021~23", "2024~26", "연도 미확인", "메모")}
    for v in out.values():
        v["n"] = sum(v["counts"].values())
    return out


def _norm(d):
    s = sum(d.values()) or 1.0
    return {k: x / s for k, x in d.items()}


def prior(dining, pmix, venue):
    """P(목적 | 이 업장을 가고 싶음) — 목적 섞기 × dining_pref"""
    w = {}
    for p, rows in dining.items():
        a = dict(rows).get(venue)
        if a and pmix.get(p):
            w[p] = pmix[p] * a
    return _norm(w)


def adjust(dining, pmix, w, signals=None):
    """dining (목적 → [(업장, 비중)]) 을 SNS 신호 쪽으로 기운 새 dict 와 보고표를 돌려준다"""
    signals = load_signals() if signals is None else signals
    if not w or not signals:
        return dining, {}
    new = {p: dict(rows) for p, rows in dining.items()}
    report = {}
    for venue, sig in signals.items():
        m = prior(dining, pmix, venue)
        if not m:
            continue
        n = sig["n"]
        s = {p: (sig["counts"].get(p, 0.0) + K * m[p]) / (n + K) for p in m}
        t = _norm({p: (m[p] ** (1 - w)) * (s[p] ** w) for p in m})
        C = sum(pmix[p] * new[p][venue] for p in m)
        # 상한에 걸린 목적은 0.8 로 묶고, 남는 무게는 나머지 목적에 목표 비율대로 나눈다 (업장 전체 무게 C 유지)
        capped, A = set(), {}
        for _ in range(len(m)):
            free = [p for p in m if p not in capped]
            Cf = C - sum(pmix[p] * CAP for p in capped)
            tf = sum(t[p] for p in free) or 1.0
            A = {p: (CAP if p in capped else Cf * t[p] / tf / pmix[p]) for p in m}
            over = {p for p in free if A[p] > CAP}
            if not over:
                break
            capped |= over
        for p in m:
            old = new[p][venue]
            a = min(CAP, A[p])
            rest_old = 1.0 - old
            rest_new = 1.0 - a
            for v2 in new[p]:
                if v2 != venue:
                    new[p][v2] = new[p][v2] * (rest_new / rest_old) if rest_old > 0 else 0.0
            new[p][venue] = a
        got = _norm({p: pmix[p] * new[p][venue] for p in m})
        raw = {p: sig["counts"].get(p, 0.0) / n for p in m} if n else {}
        report[venue] = {"n": n, "src": sig["src"], "w": w, "K": K, "cap": CAP, "est_w": EST_W,
                         "rows": [{"purpose": p, "sns_raw": round(raw.get(p, 0), 4), "model_prior": round(m[p], 4), "sns_shrunk": round(s[p], 4),
                                   "target": round(t[p], 4), "achieved": round(got[p], 4), "pref_old": round(dict(dining[p])[venue], 4),
                                   "pref_new": round(new[p][venue], 4), "capped": new[p][venue] >= CAP - 1e-9, **sig["raw"].get(p, {})}
                                  for p in sorted(m, key=lambda q: -t[q])]}
    return {p: [(v, round(x, 6)) for v, x in rows.items()] for p, rows in new.items()}, report


ONTO_NAME = {"PIZZA_HILL": "피자힐", "THE_BUFFET": "더뷔페", "GEUMRYONG": "금룡", "MYONGWOLGWAN": "명월관", "ONDAL": "온달",
             "MOEGI": "모에기", "LUX_BAR": "럭스바", "THE_PAVILION": "파빌리온", "LE_PASSAGE": "르파사쥬"}


def propensity(signals=None, draws=4000, seed=1):
    """게시 성향 = SNS 목적 비중 ÷ 온톨로지 고객 구성비 (같은 업장). 1보다 크면 그 목적 손님이 더 많이 올린다.
    0건 칸은 0.5 건 사전(Jeffreys) · 90% 구간은 디리클레 표본. 업장을 늘리면 업장마다 따로 나오고, 여러 업장에서 비슷하면
    다른 업장 · 다른 시기의 SNS 를 손님 구성으로 바꾸는 보정 계수로 쓴다 (가설)."""
    import json, random
    signals = load_signals() if signals is None else signals
    mix = json.load(open(HERE / "ontology_oct_daily.json", encoding="utf-8")).get("pool_mix", {})
    out = {}
    for venue, sig in signals.items():
        o = (mix.get(ONTO_NAME.get(venue, venue)) or {}).get("mix")
        if not o:
            continue
        ks = list(o); a = {k: sig["counts"].get(k, 0.0) + 0.5 for k in ks}; A = sum(a.values())
        rng = random.Random(seed); S = {k: [] for k in ks}
        for _ in range(draws):
            g = {k: rng.gammavariate(a[k], 1) for k in ks}; t = sum(g.values())
            for k in ks:
                S[k].append(g[k] / t / o[k])
        out[venue] = {k: {"onto": o[k], "sns": sig["counts"].get(k, 0.0) / sig["n"], "r": a[k] / A / o[k],
                          "lo": sorted(S[k])[int(.05 * draws)], "hi": sorted(S[k])[int(.95 * draws)]} for k in ks}
    return out


def env_w():
    try:
        return float(os.environ.get("WH_TREND", "0") or 0)
    except ValueError:
        return 0.0


if __name__ == "__main__":
    import generate as G
    w = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    os.environ.pop("WH_TREND", None)
    dining = G.load_dining()
    pmix = G.load_mix(HERE / "purpose_mix.csv")
    _, rep = adjust(dining, pmix, w)
    for venue, r in rep.items():
        print(f"{venue} · SNS {r['n']:g}건 · 강도 {w:g} · K={K:g} · 상한 {CAP}")
        print(f"{'목적':<10} {'SNS':>6} {'모델':>6} {'섞은SNS':>7} {'목표':>6} {'달성':>6}  가고싶음 전→후")
        for x in r["rows"]:
            print(f"{x['purpose']:<10} {x['sns_raw']*100:6.1f} {x['model_prior']*100:6.1f} {x['sns_shrunk']*100:7.1f} {x['target']*100:6.1f} {x['achieved']*100:6.1f}  {x['pref_old']:.3f}→{x['pref_new']:.3f}{' (상한)' if x['capped'] else ''}")
    for venue, r in propensity().items():
        print(f"\n{venue} 게시 성향 (SNS 비중 ÷ 온톨로지 구성비 · 90% 구간)")
        for k, x in sorted(r.items(), key=lambda kv: -kv[1]["r"]):
            tag = "더 올림" if x["lo"] > 1 else ("덜 올림" if x["hi"] < 1 else "판단 보류")
            print(f"{k:<10} SNS {x['sns']*100:5.1f}  온톨로지 {x['onto']*100:5.1f}  성향 {x['r']:.2f} ({x['lo']:.2f}~{x['hi']:.2f}) {tag}")
