"""
시설 한 곳 시뮬레이션 — 첫 시험 (맛보기)

지금 에이전트는 혼자 움직인다. 같은 날 여러 손님을 한꺼번에 돌리면 어느 시설에 언제 몰리는지가 나온다.
이게 과제의 "시설 한 곳 시뮬레이션" 과 마지막 "매출 대조" 로 가는 첫 단계다.

손님 만들기
  후기 페르소나 8개(체류 8) 를 같은 날짜로 옮기고, 도착 시각을 -60 ~ +60 분으로 20분씩 흔들어 7명씩 → 56팀.
  건물 · 인원 · 포함 식사 · 성향은 각 페르소나 그대로. 날짜만 SIM_DAY 로 바꾼다.
  (분포를 흉내 낸 게 아니라 "후기 8개가 같은 날 7번씩 온다" 는 장난감 인구다. 실제 인구 비율은 회사 자료가 있어야 한다.)

돌발 상황
  "피자힐 휴장" — 검증기 운영 창을 그날 안 열리게 바꾸고 같은 56팀을 다시 돌린다.
  에이전트는 검증기에 물어보고 움직이니, 창만 바꾸면 알아서 다른 데로 간다. 코드는 안 바꾼다.

한계 (정직하게)
  - 손님끼리 서로를 모른다. 대기 시간은 운영 창에서만 나오고, 줄이 길어져서 생기는 대기는 없다.
    → 그래서 끼니 창이 열리는 순간(17:30)에 전부 몰린다. 수용 인원(좌석 수)이 있어야 대기가 생긴다 — 회사 자료 필요
  - 인구 비율(가족 · 커플 · 비투숙) 이 실제와 다르다

실행:  python3 sim_facility.py            # 표 출력 + sim_result.json
       python3 sim_facility.py --plot     # 그래프 PNG 둘 (docs/)
"""

from __future__ import annotations

import importlib, json, sys
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import agent_v3 as agent
import walkerhill_timeline_validator as V
from walkerhill_timeline_validator import VenueWindow, SourceKind

SIM_DAY = datetime(2026, 10, 10)          # 토요일 · 2026 운영 창
JITTER_MIN = (-60, -40, -20, 0, 20, 40, 60)
FOCUS = "PIZZA_HILL"
DINING_PLACES = ("PIZZA_HILL", "THE_BUFFET", "MYONGWOLGWAN", "ONDAL", "GEUMRYONG", "MOEGI",
                 "LE_PASSAGE", "GRAND_CLUB_LOUNGE", "DOUGLAS_LOUNGE", "GRAND_ROOM", "VISTA_ROOM", "DOUGLAS_ROOM")
EAT_STATES = {"DINING", "COURSE_IN_PROGRESS", "TIME_LIMIT_ACTIVE", "TAKEOUT_ORDER", "HAPPY_HOUR_ACTIVE", "SEATED"}


class _Alt:
    def __init__(self, mod):
        for f in ("PERSONA", "START_AT"):
            setattr(self, f, getattr(mod, f + "_ALT"))


def population():
    out = []
    for n in range(1, 7):
        mod = importlib.import_module(f"persona_blog{n:02d}")
        srcs = [(f"blog{n:02d}", mod)]
        if hasattr(mod, "PERSONA_ALT"):
            srcs.append((f"blog{n:02d}_ALT", _Alt(mod)))
        for label, m in srcs:
            st = getattr(m, "START_AT", datetime(2025, 1, 1, 15, 0))
            base = SIM_DAY.replace(hour=st.hour, minute=st.minute)
            for j in JITTER_MIN:
                out.append((f"{label}{j:+d}", m.PERSONA, base + timedelta(minutes=j)))
    return out


def run(closed: set[str] = frozenset()):
    saved = {}
    for v in closed:
        saved[v] = V.WALKERHILL_VENUE_WINDOWS.get(v)
        # 그날 안 여는 창 — 연도를 어긋나게 둔다 (창이 아예 없으면 '늘 열림' 으로 읽히므로)
        V.WALKERHILL_VENUE_WINDOWS[v] = (VenueWindow(SIM_DAY.time(), SIM_DAY.time().replace(hour=23),
                                                      source=SourceKind.ESTIMATED, years=frozenset({1999})),)
    try:
        rows = []
        for name, p, start in population():
            segs, _ = agent.run_agent(p, start, verbose=False)
            rep = V.validate_walkerhill_timeline(segs, enforce_stay_day=p.is_guest, nights=p.nights)
            rows.append(dict(name=name, party=p.party_size or 2, ok=rep.ok, segs=segs))
        return rows
    finally:
        for v, w in saved.items():
            V.WALKERHILL_VENUE_WINDOWS[v] = w


def occupancy(rows, place, day, step=30):
    """place 에 있는 인원(명) — step 분 간격, day 하루."""
    t0 = day.replace(hour=6, minute=0)
    slots = [t0 + timedelta(minutes=step * i) for i in range(int(18 * 60 / step))]
    occ = []
    for t in slots:
        n = 0
        for r in rows:
            for s in r["segs"]:
                if (s.venue or s.location) == place and s.t_in <= t < s.t_out:
                    n += r["party"]; break
        occ.append(n)
    return slots, occ


def meal_of(seg_list, day, lo=17, hi=22):
    for s in seg_list:
        if s.t_in.date() == day.date() and lo <= s.t_in.hour < hi and s.state in (EAT_STATES - {"SEATED"}):
            return s.venue or s.location
    return "식당 밖 (객실 등)"


def main():
    base = run()
    closed = run({FOCUS})
    day = SIM_DAY
    teams = len(base)
    ok_b = sum(r["ok"] for r in base); ok_c = sum(r["ok"] for r in closed)
    print(f"손님 {teams}팀 ({sum(r['party'] for r in base)}명) · {day:%Y-%m-%d} · 정합성 기본 {ok_b}/{teams} · 휴장 {ok_c}/{teams}")

    slots, occ_b = occupancy(base, FOCUS, day)
    _, occ_c = occupancy(closed, FOCUS, day)
    peak = max(range(len(occ_b)), key=lambda i: occ_b[i])
    print(f"\n{FOCUS} 시간대별 인원 (30분 간격, 명) — 최대 {occ_b[peak]}명 @ {slots[peak]:%H:%M}")
    for t, a in zip(slots, occ_b):
        if a:
            print(f"  {t:%H:%M}  {a:3d}  {'█' * (a // 4)}")

    db = Counter(meal_of(r["segs"], day) for r in base)
    dc = Counter(meal_of(r["segs"], day) for r in closed)
    print("\n그날 저녁을 어디서 (팀 수)   기본 → 피자힐 휴장")
    for k in sorted(set(db) | set(dc), key=lambda k: -(db[k] + dc[k])):
        print(f"  {k:22s} {db[k]:3d} → {dc[k]:3d}")

    moved = Counter()
    for rb, rc in zip(base, closed):
        a, b = meal_of(rb["segs"], day), meal_of(rc["segs"], day)
        if a == FOCUS:
            moved[b] += 1
    print(f"\n피자힐 손님({db[FOCUS]}팀) 이 휴장일에 간 곳: {dict(moved)}")

    out = dict(day=f"{day:%Y-%m-%d}", teams=teams, people=sum(r["party"] for r in base),
               valid_base=ok_b, valid_closed=ok_c,
               slots=[f"{t:%H:%M}" for t in slots], pizza_base=occ_b, pizza_closed=occ_c,
               dinner_base=dict(db), dinner_closed=dict(dc), pizza_moved=dict(moved))
    Path(__file__).with_name("sim_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    main()
