"""연박 집계 · 그 날 머무는 손님 기준 (10/16 · 실험 · 기본 모델과 화면 계산은 바꾸지 않음)

  python3 stay_day.py 2026-10-11 0            # 목표일 · 시드 → cache/stay_day_runs.json 에 한 줄 더함
  python3 stay_summary.py cache/stay_day_runs.json   # 두 기준 묶음 → static/stay_day.json (화면)
  python3 stay_day.py 2026-10-10 0 --warm 0   # 이어 돌리기 없이 (엔진 하루 계산과 같은지 확인용)

왜: 하루 계산(engine.day)은 그 날 체크인한 손님만 만들고, 그 손님의 다음 날 조식까지 센다. 그래서 '그 날 아침 더뷔페에 오는 손님'
(전날 · 그 전날 체크인한 연박 손님)을 세지 못하고, 조식 준비량 예시의 분모가 실제 그 날 아침 손님이 아니다.

어떻게: 목표일 앞 이틀부터 같은 v4.1 조정값으로 이어 생성한다. 2박 손님은 다음 날 객실 이월(carry)로 넘겨 객실 산식이 신규 체크인에서 빼고,
좌석표(Capacity)는 사흘이 같이 쓴다. 집계는 목표일에 시작한 행동만 센다. 한호님 '이월 포함 달력일 범위'(hanho_check_20261015.py operating)와 같은 정의다.
매출: 객실 요금은 체크인 결제 한 줄에 박수가 수량으로 들어 있어, 달력일 매출에서는 밤마다 1/박수씩 그 밤 날짜에 나눈다. 체크인 고객 기준(rev_stay_checkin)은 체류 전체 그대로.
확인: --warm 0 이면 engine.day 와 손님 · 지출이 한 명 단위로 같고(10/10 시드 0: 체류 매출 · 그날 지출 · 업장 8곳 같은 날 인원 모두 일치), 이월 효과만 따로 볼 수 있다.
한계: 워밍업 첫날의 이월은 0 으로 시작한다(실제 호텔 장부를 복원한 것이 아님). 손님마다 하루 경로를 먼저 다 정하는 순서 가정은 그대로다.
모델 코드 · 입력 표는 읽기만 한다 (version.MODEL_FILES · INPUT_FILES 에 이 파일은 없다).
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
sys.path[:0] = [str(TL), str(HERE)]
with contextlib.redirect_stdout(io.StringIO()):
    import engine as E  # noqa: E402
    import agent_v4, generate as G, prices, revenue  # noqa: E402
from capacity import Capacity  # noqa: E402

OUT = HERE / "cache" / "stay_day_runs.json"     # 실행 결과 모음 (저장소 밖 캐시) — 화면용 묶음은 stay_summary.py 가 static/stay_day.json 으로
LOCS = ["THE_BUFFET", "PIZZA_HILL", "MYONGWOLGWAN", "GEUMRYONG", "ONDAL", "MOEGI", "LUX_BAR", "LE_PASSAGE"]
L3LOC = {"럭스바": "LUX_BAR", "르파사쥬": "LE_PASSAGE"}
ROOM_L3 = ("그랜드", "비스타", "더글라스")


def setup_day(day: str, seed: int):
    """engine.day 의 앞부분과 같은 순서로 그 날 조건을 맞춘다 (v4.1 기본 · 행사 없음 · 규모 100%)"""
    th = E.norm_theta(day, dict(E.V4, seed=seed))
    agent_v4.THETA_FIT.update(th)
    for k in ("wd_day", "wd_biz", "biz_party", "wd_dine", "wd_named"):        # 주말이면 평일 전용 값을 지운다 (THETA_FIT 은 update 만 하므로)
        if k not in th:
            agent_v4.THETA_FIT.pop(k, None)
    if th.get("purpose_onto"):
        os.environ["WH_PURPOSE_MIX"] = "onto"
    if th.get("rooms_formula"):
        os.environ["WH_ROOM_FORMULA"] = "1"
    if th.get("rooms_onto"):
        for p, n in (("GRAND", 507), ("VISTA", 244), ("DOUGLAS", 50)):
            prices.ROOMS[p]["n"] = n
    if th.get("rng_team"):
        revenue.RNG_TEAM = True
    G.SEED = 20261001 + seed
    revenue.SEED = 20260930 + seed
    os.environ["WH_SEARCH_WEIGHT"] = "0"
    for k in ("WH_POSTING_K", "WH_TREND", "WH_WD"):
        os.environ.pop(k, None)
    E.apply_scenario("none", day)
    cfg = copy.deepcopy(G.load_day_scenarios())
    if agent_v4.is_weekday(datetime.strptime(day, "%Y-%m-%d").date()) and th.get("wd_day") is not None:
        cfg["scenarios"]["base"] = int(round(cfg["scenarios"]["base"] * float(th["wd_day"])))
    return th, cfg


def window_of(loc: str, t: datetime, key: str = "name"):
    for w in E.venue_windows(loc, t.date()):
        if w["t0"] <= t < w["t1"]:
            return w[key] or "기타"
    return "창 밖"


def run(target: str, seed: int, warm: int = 3):
    cap = Capacity()
    if "모에기" in cap.cap:
        cap.cap["모에기"] = int(E.V4.get("moegi_seats") or cap.cap["모에기"])
    catch = E.Catch()
    carry: dict = {}
    t_day = datetime.strptime(target, "%Y-%m-%d").date()
    meals = defaultdict(Counter)            # 업장 → 손님 무리(그날 체크인 · 전날 체크인 · 그 전날 체크인 · 비투숙) → 인원
    bf_win = defaultdict(Counter)           # 더뷔페 조식 회차 → 무리 → 인원
    meal_kind = defaultdict(Counter)        # 업장 → 식사 구분(조식 · 중식 · 석식 · 기타) → 인원 (온톨로지 풀과 같은 범위로 맞출 때 · 투숙/비투숙 무리 합)
    bar_steps = Counter()                   # 럭스바 · 르파사쥬 '식사 단계' 인원 — 결제 수량과 함께 더하면 이중 집계 (확인용으로만 기록)
    inhouse = Counter()                     # 목표일 밤 객실에 있는 투숙 팀 · 인원 (무리별)
    rev_day = defaultdict(lambda: defaultdict(float))   # 달력일 운영 매출: 목표일에 일어난 지출 · 무리 → L2 → 원
    rev_stay_T = defaultdict(float)         # 체크인 고객 기준: 목표일 체크인 무리의 체류 전체 지출 · L2 → 원
    seen_ids, dup_ids, max_nights = set(), [], 0
    warmup = []
    for ix in range(-warm, 1):
        dt = datetime.strptime(target, "%Y-%m-%d") + timedelta(days=ix)
        day = dt.date().isoformat()
        th, cfg = setup_day(day, seed)
        # 입력 표는 setup_day 가 환경(WH_PURPOSE_MIX 등)을 맞춘 뒤에 읽는다 — engine.day 와 같은 순서 (10/16 정정: 앞에서 읽으면 목적 배분이 '온톨로지 배분' 이 아닌 '비중' 열로 읽힘)
        grid, factors = G.load_grid(), G.load_factors()
        pmix = G.load_mix(TL / "purpose_mix.csv")
        amix = G.load_mix(TL / "age_mix.csv", key="연령")
        tmix = G.load_type_mix()
        cap.prune(dt)
        with contextlib.redirect_stdout(io.StringIO()):
            stays = G.guests_for(day, grid, factors, scale=1.0, purpose_mix=pmix, type_mix=tmix, carry=carry,
                                 day_parties=None, day_scenario="base", day_config=cfg, age_mix=amix)
        if th.get("order_mix"):
            stays = list(stays)
            random.Random(G.SEED + 7).shuffle(stays)
        grp_of = {0: "그날 체크인", -1: "전날 체크인", -2: "그 전날 체크인"}
        grp_of.update({k: f"{-k}일 전 체크인" for k in range(-warm, -2)})
        nxt = Counter()
        n_guest = 0
        for gid, _, m in stays:
            p = m.PERSONA
            lines = revenue.spend_lines(m, k=1, capacity=cap)
            segs, traces = catch.last
            det = E.detail_json(p, m.START_AT, segs, traces, lines)
            g = grp_of[ix] if p.is_guest else "비투숙"
            if gid in seen_ids:
                dup_ids.append(gid)
            seen_ids.add(gid)
            if p.is_guest:
                max_nights = max(max_nights, p.nights)
            if ix == 0:
                for l2, krw in det["spend_by_l2"].items():
                    rev_stay_T[l2] += krw
            if p.is_guest:
                n_guest += 1
                if p.nights >= 2:
                    nxt[p.property] += 1
                if p.nights + ix >= 1:       # 목표일 밤에도 객실에 있음 (체크인일 + 박수 > 목표일)
                    inhouse[g + " 팀"] += 1
                    inhouse[g + " 인원"] += p.party_size
            for s in det["steps"]:
                # 객실 요금은 체크인 결제 한 줄에 박수가 수량으로 들어 있다 — 달력일 매출은 밤마다 1/박수씩 그 밤 날짜에 나눈다 (engine.day 의 '그날 지출' 도 첫 밤만 셈)
                d_in = datetime.fromisoformat(s["t_in"]).date()
                for sp in s["spend"]:
                    q = sp.get("qty", 1) or 1
                    if sp["l2"] == "ROOM" and sp["l3"] in ROOM_L3 and q > 1 and d_in <= t_day < d_in + timedelta(days=q):
                        rev_day[g]["ROOM"] += sp["krw"] / q
                if s["t_in"][:10] != target:
                    continue
                t = datetime.fromisoformat(s["t_in"])
                if s["kind"] == "meal" and s.get("venue") and s.get("state") != "TAKEOUT_ORDER" and s["venue"] in L3LOC.values():
                    bar_steps[s["venue"]] += p.party_size
                if s["kind"] == "meal" and s.get("venue") and s.get("state") != "TAKEOUT_ORDER" and s["venue"] not in L3LOC.values():   # 럭스바 · 르파사쥬는 아래 결제 수량으로만 센다
                    meals[s["venue"]][g] += p.party_size
                    meal_kind[s["venue"]][window_of(s["venue"], t, "kind")] += p.party_size
                    if s["venue"] == "THE_BUFFET" and "조식" in s["label"]:
                        bf_win[window_of("THE_BUFFET", t)][g] += p.party_size
                for sp in s["spend"]:
                    if not (sp["l2"] == "ROOM" and sp["l3"] in ROOM_L3 and (sp.get("qty", 1) or 1) > 1):
                        rev_day[g][sp["l2"]] += sp["krw"]
                    loc = L3LOC.get(sp["l3"])
                    if loc:
                        meals[loc][g] += sp["qty"]
        warmup.append(dict(date=day, new_teams=len(stays), new_guest_teams=n_guest, carry_in=sum(carry.values()), carry_out=sum(nxt.values())))
        carry = dict(nxt)
    # 좌석 공유 확인 — 목표일 06:00~24:00 10분 칸마다 업장별 동시 점유 최고치 ≤ 좌석 수 (사흘 손님이 같은 좌석표를 씀)
    seat_check = {}
    for venue, bk in cap.booked.items():
        t = datetime.combine(t_day, datetime.min.time()).replace(hour=6)
        pk = 0
        while t.date() == t_day:
            pk = max(pk, sum(n for a, b, n in bk if a <= t < b))
            t += timedelta(minutes=10)
        if pk:
            seat_check[venue] = dict(peak=pk, cap=cap.cap.get(venue), ok=pk <= cap.cap.get(venue, 10 ** 9))
    peak = 0
    t = datetime.combine(t_day, datetime.min.time()).replace(hour=6)
    while t.hour < 11:
        peak = max(peak, sum(n for a, b, n in cap.booked.get("더뷔페", []) if a <= t < b))
        t += timedelta(minutes=10)
    rooms_total = sum(int(prices.ROOMS[p]["n"]) for p in ("GRAND", "VISTA", "DOUGLAS"))
    return dict(date=target, seed=seed, warm=warm, frame="그 날 머무는 손님 (앞 이틀 이어 생성 · 이월 포함)" if warm else "그 날 체크인 손님만 (엔진 하루 계산과 같은 범위)",
                meals={k: dict(v) for k, v in meals.items()}, meal_kind={k: dict(v) for k, v in meal_kind.items()}, bar_meal_steps=dict(bar_steps), buffet_breakfast={k: dict(v) for k, v in bf_win.items()},
                buffet_cap=cap.cap.get("더뷔페"), buffet_breakfast_peak=peak, inhouse=dict(inhouse), warmup=warmup,
                rev_day={g: {k: round(v) for k, v in d.items()} for g, d in rev_day.items()}, rev_stay_checkin={k: round(v) for k, v in rev_stay_T.items()},
                checks=dict(duplicate_ids=len(dup_ids), max_nights=max_nights, warm_covers_max_nights=warm >= max_nights,
                            inhouse_rooms=sum(v for k, v in inhouse.items() if k.endswith(" 팀")), rooms_total=rooms_total, seats=seat_check),
                seat_summary=[dict(venue=v, seats=c, seated=n, turned=t, wait_min=round(w)) for v, c, n, t, w in cap.summary(t_day)],
                model_ver=E._version.model_ver(), input_ver=E._version.input_ver(),
                note="실험 · 워밍업 첫날 이월 0 · 실제 호텔 장부 복원 아님 · 기본 모델과 화면 계산은 그대로")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date"); ap.add_argument("seed", type=int); ap.add_argument("--warm", type=int, default=3)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    r = run(a.date, a.seed, a.warm)
    out = Path(a.out)
    try:
        allr = json.loads(out.read_text(encoding="utf-8"))
    except Exception:
        allr = {"runs": []}
    allr["runs"] = [x for x in allr["runs"] if not (x["date"] == r["date"] and x["seed"] == r["seed"] and x["warm"] == r["warm"])] + [r]
    allr["built"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    out.write_text(json.dumps(allr, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: r[k] for k in ("date", "seed", "warm", "buffet_breakfast", "buffet_breakfast_peak", "inhouse")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
