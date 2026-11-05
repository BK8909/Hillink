"""연박 집계 묶음 · 두 기준을 나란히 (10/16 · 실험 · 기본 모델과 화면 계산은 바꾸지 않음)

  python3 stay_summary.py /tmp/sd/sd_*.json      # stay_day.py 결과 파일들 → static/stay_day.json (runs + summary)

두 기준
  체크인 고객 기준 (화면 범위) : 그 날 도착한 손님만 만든 하루 계산(engine.day 캐시). 업장 이용은 당일 중 · 석식 + 다음 날 중식(전날 손님의 오늘 중식 대리).
                                럭스바 · 르파사쥬는 그 날 결제 수량. 매출은 그 손님들의 체류 전체.
  달력일 운영 기준             : stay_day.py (앞 사흘 이어 생성 · 이월 · 좌석 공유). 목표일에 시작한 행동 · 결제만 센다. 조식은 따로.
온톨로지 쪽은 같은 날짜의 풀 실이용(인 · 회, 잔, 건). 조식 · 객실 · 포장 · 에이드 · 파빌리온 · 라운지 풀은 단위가 달라 업장 비교에서 뺀다.
"""
from __future__ import annotations

import contextlib
import io
import json
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
with contextlib.redirect_stdout(io.StringIO()):
    import engine as E  # noqa: E402

OUT = HERE / "static" / "stay_day.json"
Q = 1.1e8        # 결제(VAT 포함) → 순매출 억 원 (화면 보고서와 같은 ÷ 1.1)
VEN = ["THE_BUFFET", "PIZZA_HILL", "MYONGWOLGWAN", "GEUMRYONG", "ONDAL", "MOEGI", "LUX_BAR", "LE_PASSAGE"]
SKIP_POOL = ("room-", "breakfast", "pizza-addon", "pizza-takeout", "pavilion", "ird", "lounge", "nature", "club", "partner", "forest", "healing", "yoga", "kids", "tour", "liqueur")


def ms(xs, nd=1):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return dict(mean=round(st.mean(xs), nd), lo=round(min(xs), nd), hi=round(max(xs), nd), n=len(xs))


def onto_by_venue(oo, date):
    out = defaultdict(int)
    for p in (oo["daily"].get(date) or {}).get("pools", []):
        if not (p["cap"] > 0) or p["id"].startswith(SKIP_POOL):
            continue
        loc = E.ONTO_LOC.get(p["venue"])
        if loc in VEN:
            out[loc] += p["used"]
    return dict(out)


def screen_counts(date, seed, mv, iv):
    """화면 범위 — 한호님 hanho_check_20261015.py screen 과 같은 셈"""
    f = E.CACHE / (E.day_key(date, "none", 1, dict(E.V4, seed=seed)) + ".json")
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    if d.get("model_ver") != mv or d.get("input_ver") != iv:
        return None
    vals = {}
    for loc, v in d["venue_detail"].items():
        if loc not in VEN:
            continue
        if loc in ("LUX_BAR", "LE_PASSAGE"):
            vals[loc] = sum((v.get("l4_qty_day") or {}).values())
            continue
        same = [w for w in v["windows"] if "익일" not in w["name"] and w["kind"] != "조식"]
        nxt = [w for w in v["windows"] if "익일" in w["name"] and w["kind"] == "중식"]
        vals[loc] = sum(w["persons"] for w in same + nxt)
    bf = {w["name"]: w["persons"] for w in d["venue_detail"].get("THE_BUFFET", {}).get("windows", []) if w["kind"] == "조식"}
    return dict(counts=vals, stay_rev=d.get("total"), day_rev=d.get("total_day"), teams=d.get("n"), breakfast_next=bf)


def op_counts(r):
    """달력일 운영 기준 — 조식 뺀 착석 인원 · 바는 결제 수량"""
    out = {}
    for loc in VEN:
        if loc in ("LUX_BAR", "LE_PASSAGE"):
            out[loc] = sum((r["meals"].get(loc) or {}).values())
        else:
            out[loc] = sum(n for k, n in (r.get("meal_kind", {}).get(loc) or {}).items() if k != "조식")
    return out


def summarize(runs):
    mv, iv = E._version.model_ver(), E._version.input_ver()
    oo = E.ontology_oct()
    by = defaultdict(list)
    for r in runs:
        if r.get("warm", 0) >= 2 and r.get("model_ver") == mv and r.get("input_ver") == iv:
            by[r["date"]].append(r)
    S = {}
    for date, rs in sorted(by.items()):
        rs.sort(key=lambda r: r["seed"])
        onto = onto_by_venue(oo, date)
        scr = [screen_counts(date, r["seed"], mv, iv) for r in rs]
        venues = {}
        for loc in VEN:
            o = onto.get(loc)
            opv = [op_counts(r)[loc] for r in rs if "meal_kind" in r or loc in ("LUX_BAR", "LE_PASSAGE")]
            scv = [s["counts"].get(loc) for s in scr if s]
            dbl = [op_counts(r)[loc] + (r.get("bar_meal_steps") or {}).get(loc, 0) for r in rs if "bar_meal_steps" in r] if loc in ("LUX_BAR", "LE_PASSAGE") else []
            venues[loc] = dict(onto=o, screen=ms(scv), operating=ms(opv),
                               screen_pct=round(100 * st.mean(scv) / o, 1) if scv and o else None,
                               operating_pct=round(100 * st.mean(opv) / o, 1) if opv and o else None,
                               steps_plus_qty_pct=round(100 * st.mean(dbl) / o, 1) if dbl and o else None)
        # 조식 (더뷔페) — 회차 · 무리
        win = sorted({w for r in rs for w in r["buffet_breakfast"]})
        bf = {}
        for w in win:
            grp = sorted({g for r in rs for g in r["buffet_breakfast"].get(w, {})})
            bf[w] = dict(total=ms([sum(r["buffet_breakfast"].get(w, {}).values()) for r in rs]),
                         groups={g: ms([r["buffet_breakfast"].get(w, {}).get(g, 0) for r in rs]) for g in grp})
        prev = (datetime.strptime(date, "%Y-%m-%d").toordinal() - 1)
        prev_d = datetime.fromordinal(prev).date().isoformat()
        scr_prev = [screen_counts(prev_d, r["seed"], mv, iv) for r in rs]
        # 객실
        inh = [r["checks"]["inhouse_rooms"] for r in rs]
        new_t = [r["inhouse"].get("그날 체크인 팀", 0) for r in rs]
        # 매출 (원) — 달력일 운영 vs 체크인 고객 체류 전체
        rd = [sum(sum(d.values()) for d in r["rev_day"].values()) for r in rs]
        rd_g = defaultdict(list)
        for r in rs:
            for g in ("그날 체크인", "전날 체크인", "그 전날 체크인", "비투숙"):
                rd_g[g].append(sum((r["rev_day"].get(g) or {}).values()))
        rs_T = [sum(r["rev_stay_checkin"].values()) for r in rs]
        scr_rev = [s["stay_rev"] for s in scr if s and s.get("stay_rev")]
        scr_day = [s["day_rev"] for s in scr if s and s.get("day_rev")]
        S[date] = dict(
            seeds=[r["seed"] for r in rs], warm=sorted({r["warm"] for r in rs}),
            checks=dict(duplicate_ids=sum(r["checks"]["duplicate_ids"] for r in rs), max_nights=max(r["checks"]["max_nights"] for r in rs),
                        warm_covers=all(r["checks"]["warm_covers_max_nights"] for r in rs),
                        rooms_ok=all(r["checks"]["inhouse_rooms"] <= r["checks"]["rooms_total"] for r in rs),
                        seats_ok=all(all(v["ok"] for v in r["checks"]["seats"].values()) for r in rs)),
            rooms=dict(inhouse=ms(inh), new_checkin=ms(new_t), carried=ms([a - b for a, b in zip(inh, new_t)]), total=rs[0]["checks"]["rooms_total"]),
            breakfast=dict(windows=bf, cap=rs[0]["buffet_cap"], peak=ms([r["buffet_breakfast_peak"] for r in rs]),
                           screen_prev_day=ms([sum(s["breakfast_next"].get(w, 0) for w in s["breakfast_next"] if "익일" in w) for s in scr_prev if s]),
                           screen_prev_day_src=f"{prev_d} 체크인 손님의 다음 날 조식 (화면 범위)"),
            venues=venues,
            revenue=dict(operating_day=ms([x / Q for x in rd], 3), operating_by_group={g: ms([x / Q for x in v], 3) for g, v in rd_g.items()},
                         stay_checkin_T=ms([x / Q for x in rs_T], 3), screen_stay=ms([x / Q for x in scr_rev], 3),
                         screen_day=ms([x / Q for x in scr_day], 3), unit="억 원 · 순매출(VAT 제외 = 결제 ÷ 1.1) · 모델 계산"),
            warmup=[r["warmup"] for r in rs])
    return S, mv, iv


def main():
    runs = []
    for p in sys.argv[1:]:
        try:
            runs += json.loads(Path(p).read_text(encoding="utf-8"))["runs"]
        except Exception as e:  # noqa: BLE001
            print("건너뜀", p, e)
    uniq = {}
    for r in runs:
        uniq[(r["date"], r["seed"], r["warm"])] = r
    runs = sorted(uniq.values(), key=lambda r: (r["date"], r["warm"], r["seed"]))
    S, mv, iv = summarize(runs)
    # 10/16 QA · 이 묶음은 v4.1 기본 조건(행사 없음 · 규모 100% · 기본 조정값) 전용이다. 화면이 다른 조건(좌석 338 · 변칙 · 다른 조정값)에
    # 붙이지 않도록, 이 조건과 같은 하루 계산 키(날짜 · 그 전날 · 시드 0~9)를 함께 적는다. 화면 · 어시스턴트는 키가 이 목록에 있을 때만 연결한다
    base_keys = sorted({E.day_key(dd, "none", 1, dict(E.V4, seed=sd)) for d in S for dd in (d, (datetime.strptime(d, "%Y-%m-%d") - timedelta(days=1)).date().isoformat()) for sd in range(10)})
    out = dict(built=datetime.now().strftime("%Y-%m-%d %H:%M"), model_ver=mv, input_ver=iv, condition="v4.1 기본 · 행사 없음 · 규모 100% · 기본 조정값 (온톨로지 정합 v4.1)", base_keys=base_keys,
               note="실험 · 워밍업 첫날 이월 0 · 실제 호텔 장부 복원 아님 · 기본 모델과 화면 계산은 그대로", summary=S, runs=runs)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for d, s in S.items():
        print(d, "seeds", s["seeds"], "checks", s["checks"])
        for loc, v in s["venues"].items():
            print(f"  {loc:13s} onto {v['onto']}  screen {v['screen_pct']}  operating {v['operating_pct']}  steps+qty {v['steps_plus_qty_pct']}")


if __name__ == "__main__":
    main()
