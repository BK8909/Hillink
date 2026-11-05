"""
시드 묶음 — 같은 날 · 같은 조정값을 시드만 바꿔 여러 번 돌려 결과의 범위를 낸다 (10/14 경수)

  cd timeline/viewer
  python3 band.py --date 2026-10-10 --theta '{"next_window":1,...}' --seeds 10
  python3 band.py --date 2026-10-10 --theta '{...v4...}' --compare '{...v4..., "trend_w":1}' --seeds 10 --jobs 4

왜
  하루 결과는 시드 하나(손님 생성 · 에이전트 확률 선택 · 상품 추첨)의 한 번이다. 조정값을 켜서 생긴 차이가
  시드만 바꿔도 생기는 흔들림보다 큰지 봐야 그 차이를 '효과' 라고 말할 수 있다.

무엇을 하나
  1. 시드 0..n-1 마다 engine.day 를 새 프로세스로 돌린다 (조정값 seed — generate.SEED · revenue.SEED 를 같이 옮김. 0 은 기본 결과 그대로)
  2. 하루마다 지표를 뽑는다 — 순매출 · L2 비중 · 업장별 이용 인원(다음날 중식 대리 포함) · 초과 수요 · 포장 · 럭스바 · 르파사쥬 · 피자힐 목적 구성
  3. 지표마다 평균 · 표준편차 · 최소 · 최대. --compare 가 있으면 같은 시드끼리 짝지어 차이(효과)의 평균 · 표준편차와
     '효과 ÷ 시드 흔들림' 을 낸다 (같은 시드면 손님이 같아서 짝 비교가 공정하다)
  4. cache/band_<기준 키>.json 에 쓴다 — 화면 하루 패널이 이 파일이 있으면 '시드 범위' 카드를 띄운다
  시드 1 이상의 손님 상세(.guests.jsonl · .cap.pkl)는 용량 때문에 지운다 (--keep 이면 남김). 시드 0 은 그대로
"""
from __future__ import annotations

import argparse, json, math, statistics as st, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine  # noqa: E402  (day_key · KNOBS 만 쓴다)

CACHE = engine.CACHE
# 양측 95% t 분포 (자유도 → 값). 짝 비교라 자유도 = 시드 수 − 1
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
        13: 2.160, 14: 2.145, 15: 2.131, 19: 2.093, 24: 2.064, 29: 2.045}
VENUES = {"THE_BUFFET": "더뷔페", "PIZZA_HILL": "피자힐 홀", "GEUMRYONG": "금룡", "MYONGWOLGWAN": "명월관", "ONDAL": "온달", "MOEGI": "모에기"}


def run_day(date, scen, scale, theta, keep):
    key = engine.day_key(date, scen, scale, theta)
    f = CACHE / f"{key}.json"
    import version
    stale = False
    if f.exists():      # 10/14 — 코드 · 입력 버전이 다르면 다시 계산
        try:
            m = json.loads(f.read_text(encoding="utf-8")); stale = (m.get("model_ver"), m.get("input_ver")) != (version.model_ver(), version.input_ver())
        except Exception:
            stale = True
    if not f.exists() or stale:
        r = subprocess.run([sys.executable, str(HERE / "engine.py"), "day", "--date", date, "--scenario", scen, "--scale", str(scale),
                            "--theta", json.dumps(theta)], cwd=HERE, capture_output=True, text=True)
        if r.returncode != 0 or not f.exists():
            raise RuntimeError(f"{key}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else '실패'}")
    if theta.get("seed") and not keep:
        for ext in (".guests.jsonl", ".cap.pkl"):
            (CACHE / f"{key}{ext}").unlink(missing_ok=True)
    return key


def metrics(key):
    D = json.loads((CACHE / f"{key}.json").read_text(encoding="utf-8"))
    vd = D["venue_detail"]
    out = {"순매출 (억)": D["total_net"] / 1e8}
    l2 = D["by_l2"]; tot = sum(l2.values()) or 1
    for k in ("ROOM", "F&B"):
        out[f"L2 {k} 비중 (%)"] = l2.get(k, 0) / tot * 100

    def pv(loc):
        v = vd[loc]
        return sum(w["persons"] for w in v["windows"] if "익일" not in w["name"] or w["kind"] == "중식")
    for loc, nm in VENUES.items():
        if loc in vd:
            out[f"{nm} 이용 (명)"] = pv(loc)
            out[f"{nm} 초과 수요 (명)"] = vd[loc].get("over_persons", 0)
    # 10/15 시연 점검 — 위 '이용' 은 온톨로지 날짜 대조용(그 날 + 다음날 중식)이라 이 날 체크인 손님의 다음날 조식이 빠진다.
    # 초과 수요 · 공급 제한은 조식을 세므로, 조식 쪽 변화를 같은 표에서 보려고 따로 둔다
    if "THE_BUFFET" in vd:
        out["더뷔페 다음날 조식 이용 (명)"] = sum(w["persons"] for w in vd["THE_BUFFET"]["windows"] if "익일" in w["name"] and w["kind"] == "조식")
    for loc, nm in (("PIZZA_HILL", "피자힐"), ("THE_BUFFET", "더뷔페")):
        bg = (vd.get(loc) or {}).get("by_guest") or {}
        out[f"{nm} 비투숙 팀 (팀)"] = bg.get("비투숙", 0)
    pz = vd.get("PIZZA_HILL", {})
    out["피자힐 포장 (판)"] = sum(q for n, q in (pz.get("l4_qty_day") or {}).items() if "포장" in n)
    if "LUX_BAR" in vd:
        out["럭스바 (잔)"] = sum((vd["LUX_BAR"].get("l4_qty_day") or {}).values())
    if "LE_PASSAGE" in vd:
        out["르파사쥬 (건)"] = sum((vd["LE_PASSAGE"].get("l4_qty_day") or {}).values())
    bp = pz.get("by_purpose") or {}; tp = sum(bp.values()) or 1
    for p in ("가족·친족", "커플·기념일", "미식 방문", "혼자 휴식", "비즈니스·접대"):
        out[f"피자힐 {p} (%)"] = bp.get(p, 0) / tp * 100
    out["행동 전환 (회)"] = D.get("n_switch", 0)
    if "n_switch_teams" in D:
        out["공급 제한 겪은 팀 (팀)"] = D["n_switch_teams"]          # 고유 팀 (같은 팀 여러 번은 1)
    if "total_day" in D:
        out["그날 지출 (억)"] = D["total_day"] / 1.1 / 1e8            # 순매출 기준 · 그날 날짜로 잡힌 결제만
    return out


def summ(vals):
    m = st.mean(vals)
    sd = st.stdev(vals) if len(vals) > 1 else 0.0
    return {"mean": round(m, 3), "sd": round(sd, 3), "min": round(min(vals), 3), "max": round(max(vals), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-10"); ap.add_argument("--scenario", default="none"); ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--theta", default="{}"); ap.add_argument("--compare"); ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--jobs", type=int, default=3); ap.add_argument("--keep", action="store_true")
    ap.add_argument("--no-base-write", action="store_true", help="기준 날 범위 파일을 덮어쓰지 않음 (시드 수가 더 많은 기준 범위가 이미 있을 때)")
    a = ap.parse_args()
    base = {k: v for k, v in json.loads(a.theta).items() if k in engine.KNOBS and k != "seed"}
    comp = {k: v for k, v in json.loads(a.compare).items() if k in engine.KNOBS and k != "seed"} if a.compare else None
    jobs = [("base", s, dict(base, **({"seed": s} if s else {}))) for s in range(a.seeds)]
    if comp is not None:
        jobs += [("comp", s, dict(comp, **({"seed": s} if s else {}))) for s in range(a.seeds)]
    keys = {}
    with ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(run_day, a.date, a.scenario, a.scale, th, a.keep): (side, s) for side, s, th in jobs}
        for f, (side, s) in futs.items():
            keys[(side, s)] = f.result()
            print(f"  {side} 시드 {s} · {keys[(side, s)]}", flush=True)
    M = {(side, s): metrics(k) for (side, s), k in keys.items()}
    names = list(M[("base", 0)].keys())
    import version
    res = {"date": a.date, "scenario": a.scenario, "scale": a.scale, "seeds": a.seeds, "theta": base, "compare": comp,
           "model_ver": version.model_ver(), "input_ver": version.input_ver(),
           "base_key": keys[("base", 0)], "compare_key": keys.get(("comp", 0)),
           "base": {n: summ([M[("base", s)][n] for s in range(a.seeds)]) for n in names},
           "per_seed": {str(s): M[("base", s)] for s in range(a.seeds)}}
    if comp is not None:
        res["comp"] = {n: summ([M[("comp", s)][n] for s in range(a.seeds)]) for n in names}
        eff = {}
        for n in names:
            d = [M[("comp", s)][n] - M[("base", s)][n] for s in range(a.seeds)]
            noise = res["base"][n]["sd"]
            md = st.mean(d); sdd = st.stdev(d) if len(d) > 1 else 0.0
            se = sdd / math.sqrt(len(d)) if len(d) > 1 else 0.0
            tq = T975.get(len(d) - 1, 1.96)       # 10/14 — 시드 수에 맞는 t 값 (전에는 10개일 때만 t, 나머지는 2 × 표준오차)
            eff[n] = {"diff": round(md, 3), "diff_sd": round(sdd, 3), "lo95": round(md - tq * se, 3), "hi95": round(md + tq * se, 3), "t": tq,
                      "ratio": round(abs(md) / noise, 2) if noise else None,
                      "same_sign": sum(1 for x in d if (x > 0) == (md > 0) and x != 0)}
        res["effect"] = eff
    # 기준 날 파일엔 기준 범위만 (비교가 여럿이어도 덮어쓰지 않게) · 비교 날 파일엔 범위 + 효과
    out = CACHE / f"band_{res['base_key']}.json"
    base_only = {k: v for k, v in res.items() if k not in ("comp", "effect", "compare", "compare_key")}
    if not a.no_base_write:
        out.write_text(json.dumps(base_only, ensure_ascii=False, indent=1), encoding="utf-8")
    if comp is not None:
        out = CACHE / f"band_{res['compare_key']}.json"
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {out}")
    w = max(len(n) for n in names)
    for n in names:
        b = res["base"][n]
        line = f"{n:<{w}}  평균 {b['mean']:>9.2f}  ±{b['sd']:<7.2f} [{b['min']:.2f} ~ {b['max']:.2f}]"
        if comp is not None:
            e = res["effect"][n]
            line += f"  | 효과 {e['diff']:+.2f} (95% {e['lo95']:+.2f} ~ {e['hi95']:+.2f}) · 흔들림 대비 {e['ratio']} · 같은 방향 {e['same_sign']}/{a.seeds}"
        print(line)


if __name__ == "__main__":
    main()
