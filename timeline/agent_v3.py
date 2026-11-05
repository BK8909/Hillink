"""
정합성을 유지하며 의사결정하는 에이전트 — v3

v3 는 v2 에 여섯 가지만 더했다. 전부 여러 후기에서 같은 원인으로 놓친 것이고, 가중치(성향 계수)는 그대로다.
v2 는 비교용으로 그대로 둔다 (python3 run_all.py v2 / v3).

  A. 입실 절차를 60분 → 20분 (짐 풀기).  blog02 · blog04 B · blog06 — 키를 받고 객실에서 1시간을 보내느라
     오후 라운지 티타임 · 16시 전시를 놓쳤다. 그 뒤 객실 체류는 v2 대로.
  B. 빈 시간 채우기.  가장 좋은 후보가 40분 넘게 기다려야 하면(대개 저녁 창), 그 전에 끝내고 제때 갈 수 있는
     다른 활동을 먼저 한다. 끼니라면 활동 뒤에도 같은 끼니 창 안에서 먹을 수 있으면 된다. 사람은 저녁 시간까지 방에서 기다리지 않는다 — blog03 B 족욕 뒤 저녁 · blog06 전시 뒤 피자.
  C. 피자힐 포장.  blog03 B · blog06 이 피자힐에서 포장해 객실에서 먹었다 (blog03 A 는 르파사쥬 포장).
     포장은 '대기 회피' 만큼 가점 (줄 대신 포장 — blog06 '앞에 11팀' 에서 포장 선택). 포장 뒤엔 객실에서 먹는다.
  E. 라운지 · 뷔페는 늦게 들어가도 창 마감까지 머문다 (최소 30~50분). 정해진 체류가 창에 안 들어가면 통째로 빠지던 것.
     blog02 라이트 스낵 '16시대' · blog04 B 티타임 16:10–17:00 · blog05 조식.
  F. 객실에서 다음 운영 창을 기다리는 건 줄 서기가 아니다 — 방에 있을 때는 대기 벌점을 매기지 않는다.
     v2 는 07:30 에 일어나 08:30 조식 회차까지 60분을 '대기' 로 쳐서 방에서 때우는 쪽을 골랐다 (blog03 B · blog05).
  D. 조식을 방에서 때우기 -1.  조식 예약이 없어도 blog03 B · blog05 는 더뷔페에 갔다 (blog06 은 객실 시리얼 — 반대 사례 하나).
     2 대 1 이라 약하게만.

아래는 v2 머리말 그대로.

정합성을 유지하며 의사결정하는 에이전트 — v2

v1 은 후기 1편(그랜드 2박 · 가족)에서 일치율 100%/78% 였다. 같은 후기로 고치고 잰 숫자라
일반화가 아니다. 팀이 옮긴 후기 5편(blog02~06)이 검증셋인데, v1 을 거기 돌리려면
코드를 열어보기 전에 이미 막히는 게 셋 있었다.

  1. 에이전트가 갈 수 있는 곳이 후기보다 좁다.
     더글라스 라운지(blog02) · 르파사쥬 · 스카이야드(blog03) · 리버파크 · 클럽라운지 티타임(blog04) ·
     빛의 시어터 · 라이브러리(blog06). 검증기는 취합으로 노드를 얻었는데 에이전트 카탈로그는 blog01 기준.
     고침  카탈로그를 검증기 노드에 맞춰 넓힌다. 운영 창이 검증기에 있는 곳은 venue 를 붙여 검증기가 보게 한다.

  2. 에이전트가 무조건 그랜드 객실에서 출발한다.
     blog02 는 더글라스, blog03·05 는 비스타. 어느 건물에 묵었나는 성향이 아니라 예약 사실이다.
     고침  Persona.property ("GRAND" · "VISTA" · "DOUGLAS"). 로비 · 프런트 · 객실 · 수영장 · 라운지가 거기서 정해진다.

  3. 비투숙 방문(blog04 A · 리버파크)을 아예 못 다룬다. 체크인 절차부터 시작하니까.
     고침  Persona.is_guest=False 면 체크인 절차 · 객실 · 취침이 없다. 정문에서 시작해 depart_by 까지 움직인다.

  그리고 클럽라운지는 "13세 미만 동반 아님" 이 아니라 "클럽 객실 예약" 이 조건이다 (Persona.club_access).
  v1 은 adults_only 로 뭉뚱그렸다. blog04 B 가 클럽스위트라 드러났다.

점수 함수는 v1 것을 그대로 쓴다 (agent_v1.score). 이번 라운드는 카탈로그와 출발 조건만 바꾼다 —
가중치까지 같이 바꾸면 일치율이 달라졌을 때 무엇 때문인지 모른다.

blog02(한호 페르소나)를 처음 돌려서 드러난 것 — 가중치가 아니라 절차·사실 규칙 둘:
  4. 키를 받고 객실에 안 간다. 더글라스는 객실까지 38분(피크 ×2 + 셔틀)이라 점수가 -1.3 이고
     포레스트파크(+0.8)가 이긴다. 그런데 사람은 키 받으면 짐 풀러 객실부터 간다 — 성향이 아니라 절차.
     고침  키 수령 뒤 첫 객실 입실은 체크인 절차의 일부 (+20). 그 뒤 객실은 v1 대로 성향으로.
  5. 예약에 포함된 저녁(더글라스 아워 19–21)이 있는데 17:30 에 피자힐을 먼저 먹고 나서 "석식 이미 먹음" 으로 라운지를 버린다.
     고침  오늘 아직 안 쓴 포함 끼니가 있고 그 창이 남아 있으면, 같은 끼니의 다른 식사는 후보에서 뺀다.
           돈 낸 저녁을 두고 다른 저녁을 사 먹지 않는다 — 예약 사실에서 나오는 규칙.

소연 페르소나(blog03 · blog04, 각 체류 둘)를 돌려서 드러난 것:
  6. 비투숙 리버파크 방문(blog04 A)에서 리버파크에 안 간다. 끼니 점수(+6)가 시설 점수를 다 이긴다.
     입장권을 끊고 온 사람은 그 시설이 목적이다 — 성향이 아니라 예약 사실 (included_meals 와 같은 종류).
     고침  Persona.booked=("RIVERPARK",) 면 처음 갈 때 +8.
  아직 안 고친 것 (한 편으로는 근거가 약함 — v3 후보):
     · 끼니를 창이 열리자마자 먹는다 (next_meal_start). blog03 B 는 족욕 뒤 저녁이었다.
     · 조식이 예약에 없으면 '식당 외 식사' 가 더뷔페를 이긴다 (blog03 B 더뷔페 놓침).
     · 포장(르파사쥬)과 착석(피자힐)을 성향으로 못 가른다 (blog03 A 는 르파사쥬 TOGO, 피자힐 안 감).
     · 체크인 절차 고정 길이(대기 30 + 입실 60)가 오후 라운지 티타임을 먹는다 (blog02 · blog04 B 둘 다 놓침).

실행:  python3 run_all.py        # persona_blog0N.py 가 있는 후기 전부에 v2 를 돌려 일치율 표
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, time, timedelta

from walkerhill_timeline_validator import (
    TimelineSegment, WALKERHILL_VENUE_WINDOWS,
    validate_walkerhill_timeline, walkerhill_travel_time_min,
)
from agent_v0 import Action, Persona, Trace, SLEEP_FROM, WAKE_AT, MEAL_ONLY
from agent_v1 import (
    score, meal_kind_at, next_meal_start, MEAL_WINDOWS_V1,
    HORIZON_MIN, SLEEP_CONSIDER_FROM,
)

# ---------------------------------------------------------------------------
# 건물별 장소 — 성향이 아니라 예약 사실
# ---------------------------------------------------------------------------

PROPERTY = {
    "GRAND":   dict(lobby="GRAND_LOBBY", desk="GRAND_FRONT_DESK", room="GRAND_ROOM",
                    pool="GRAND_POOL", lounge="GRAND_CLUB_LOUNGE"),
    "VISTA":   dict(lobby="VISTA_LOBBY", desk="VISTA_LOBBY", room="VISTA_ROOM",
                    pool="VISTA_POOL", lounge="GRAND_CLUB_LOUNGE"),   # 비스타 라운지 노드 없음 — blog05 확인 중
    # 더글라스는 체크인을 그랜드 프런트에서 하고 셔틀로 넘어간다 (blog02 ◎)
    "DOUGLAS": dict(lobby="GRAND_LOBBY", desk="GRAND_FRONT_DESK", room="DOUGLAS_ROOM",
                    pool="GRAND_POOL", lounge="DOUGLAS_LOUNGE"),
}

# 검증기에 운영 창이 없는 곳 — 에이전트가 임시로 들고 있는 값 (△). 검증기로 옮기는 건 별도 커밋.
TEMP_WINDOWS = {
    "FOREST_PARK":      ((time(11, 0), time(20, 0)),),                                   # docs §8.6 ◎
    "WELLNESS_SAUNA":   ((time(6, 0), time(21, 0)),),                                    # blog01 안내표 ◎
    "THEATRE_OF_LIGHT": ((time(10, 0), time(19, 0)),),                                   # △ blog06 16:00 도슨트 · 17:30 종료
    "GRAND_LIBRARY":    ((time(7, 0), time(22, 0)),),                                    # △
    # 더글라스 라운지 — 검증기에 창이 없다. blog02 후기(◎ 라이트 스낵 15–17 · 더글라스 아워 19–21 · 조식 07:30경)
    "DOUGLAS_LOUNGE":   ((time(7, 0), time(10, 0)), (time(15, 0), time(17, 0)), (time(19, 0), time(21, 0))),
}


FIRST_ROOM_MIN = 20      # v3-A 짐 풀기
# v3-E 늦게 들어가도 창 마감까지는 머무는 곳 — 라운지 3창 · 뷔페 회차. 값은 최소 체류(분)
#   blog02 라이트 스낵 '16시대' · blog04 B 티타임 16:10–17:00 · blog05 조식 회차 — 정해진 체류가 창에 안 들어가 통째로 빠지던 것
MIN_DWELL = {"lounge_b": 30, "lounge_t": 30, "lounge_h": 40, "buffet_b": 40, "buffet_l": 50}
FILL_WAIT_MIN = 40       # v3-B 이만큼 넘게 기다리면 빈 시간 채우기를 본다
FILL_MIN_SCORE = -0.5    # v3-B 채우기 후보의 최저 점수 (이동 벌점만 조금 있는 정도까지)


def window_close(a: Action, start: datetime) -> datetime | None:
    """start 가 들어 있는 운영 창의 마감 시각."""
    if a.venue is None:
        if a.open_close is None:
            return None
        return datetime.combine(start.date(), a.open_close[1])
    for w in WALKERHILL_VENUE_WINDOWS.get(a.venue, ()):
        if not w.opens_on(start.date()) or (w.states is not None and a.state not in w.states):
            continue
        o, c = datetime.combine(start.date(), w.open_at), datetime.combine(start.date(), w.close_at)
        if o <= start < c:
            return c
    return None


def catalog(p: Persona) -> list[Action]:
    L = PROPERTY[p.property]
    lobby, desk, room, pool, lounge = L["lobby"], L["desk"], L["room"], L["pool"], L["lounge"]
    lounge_venue = lounge if lounge in WALKERHILL_VENUE_WINDOWS else None

    checkin = [
        Action("arrive",  "ARRIVED_ON_PROPERTY", lobby, 5, machine="M2_Stay", label="도착"),
    ]
    if p.is_guest:
        checkin += [
            Action("luggage", "LUGGAGE_STORED",   lobby, 5, machine="M2_Stay", requires=("arrive",), label="짐 맡김"),
            Action("queue",   "IN_CHECKIN_QUEUE", lobby, 30, machine="M2_Stay", requires=("arrive",), label="체크인 대기"),
            Action("desk",    "AT_FRONT_DESK",    desk, 8, machine="M2_Stay", requires=("queue",), label="프런트 응대"),
            Action("key",     "KEY_ISSUED",       desk, 3, machine="M2_Stay", requires=("desk",), label="키 수령"),
            Action("room",    "IN_ROOM",          room, 60, machine="M2_Stay", requires=("key",), once=False, label="객실"),
            Action("sleep",   "IN_ROOM",          room, 0, machine="M2_Stay", requires=("key",), once=False, label="취침"),
            Action("meal_other", "IN_ROOM",       room, 45, machine="M2_Stay", requires=("key",), once=False,
                   tags=("meal_other",), label="식당 외 식사"),
        ]
    key_req = ("key",) if p.is_guest else ("arrive",)

    dining = [
        Action("ondal",    "COURSE_IN_PROGRESS", "ONDAL",        120, venue="ONDAL",        requires=key_req, tags=("formal", "shared", "quiet"), label="온달"),
        Action("geum",     "DINING",             "GEUMRYONG",    110, venue="GEUMRYONG",    requires=key_req, tags=("formal", "shared"), label="금룡"),
        Action("myong",    "DINING",             "MYONGWOLGWAN",  90, venue="MYONGWOLGWAN", requires=key_req, tags=("formal", "shared"), label="명월관"),
        Action("moegi",    "DINING",             "MOEGI",         90, venue="MOEGI",        requires=key_req, tags=("formal", "quiet"), label="모에기"),
        Action("pizza",    "DINING",             "PIZZA_HILL",   120, venue="PIZZA_HILL",   requires=key_req, tags=("shared", "view", "casual", "kids"), label="피자힐"),
        # v3-C 피자힐 포장 — 주문·수령 20분. 먹는 건 객실에서 (아래 run_agent)
        Action("pizza_to", "TAKEOUT_ORDER",      "PIZZA_HILL",    20, venue="PIZZA_HILL",   requires=key_req, tags=("casual", "kids", "takeout"), label="피자힐 포장"),
        Action("buffet_b", "TIME_LIMIT_ACTIVE",  "THE_BUFFET",    90, venue="THE_BUFFET",   requires=key_req, tags=("shared", "busy", "kids"), label="더뷔페 조식"),
        Action("buffet_l", "TIME_LIMIT_ACTIVE",  "THE_BUFFET",   120, venue="THE_BUFFET",   requires=key_req, tags=("shared", "busy", "kids"), label="더뷔페 중식"),
        Action("pavilion", "SEATED",             "THE_PAVILION",  90, venue="THE_PAVILION", requires=("arrive",), tags=("quiet", "casual", "kids"), label="더 파빌리온"),
        # 르파사쥬 — 피자 포장 (blog03 ◎). 검증기가 TAKEOUT_ORDER 상태에 주문 창(11–19:30)을 따로 본다
        Action("lepassage", "TAKEOUT_ORDER",     "LE_PASSAGE",    20, venue="LE_PASSAGE",   requires=key_req, tags=("casual", "kids", "takeout"), label="르파사쥬 포장"),
        Action("lux",      "TAB_OPEN",           "LUX_BAR",      100, venue="LUX_BAR",      requires=key_req, adults_only=True, tags=("view", "quiet", "formal"), label="LUX BAR"),
    ]
    # 클럽라운지 — 클럽 객실 예약자만 (blog04 B ◎). 창 셋은 검증기가 본다
    if p.is_guest and p.club_access:
        dining += [
            Action("lounge_b", "IN_LOUNGE",         lounge, 60, venue=lounge_venue, requires=("key",), tags=("quiet", "view", "shared"), label="클럽라운지 조식",
                   open_close=None if lounge_venue else TEMP_WINDOWS[lounge][0]),
            Action("lounge_t", "IN_LOUNGE",         lounge, 50, venue=lounge_venue, requires=("key",), tags=("quiet", "view"), label="클럽라운지 티타임",
                   open_close=None if lounge_venue else TEMP_WINDOWS[lounge][1]),
            Action("lounge_h", "HAPPY_HOUR_ACTIVE", lounge, 90, venue=lounge_venue, requires=("key",), adults_only=True, tags=("quiet", "view", "shared"), label="클럽라운지 해피아워",
                   open_close=None if lounge_venue else TEMP_WINDOWS[lounge][2]),
        ]

    facility = [
        # 투숙객 전용 시설은 비투숙이면 후보에 아예 없다 (requires key — 비투숙은 key 가 안 생긴다)
        Action("pool",    "ENTERED",  pool,               80, venue=pool, requires=("key",), tags=("busy", "kids"), label="실내수영장"),
        Action("forest",  "ADMITTED", "FOREST_PARK",      90, requires=("arrive",), tags=("view", "quiet", "kids"), label="포레스트 파크", open_close=TEMP_WINDOWS["FOREST_PARK"][0]),
        Action("sauna",   "IN_TREATMENT", "WELLNESS_SAUNA", 60, requires=("key",), tags=("quiet",), label="사우나", open_close=TEMP_WINDOWS["WELLNESS_SAUNA"][0]),
        Action("skyard",  "ADMITTED", "SKYARD",           40, venue="SKYARD", requires=("arrive",), tags=("view", "quiet"), label="스카이야드"),
        Action("river",   "ENTERED",  "RIVERPARK",       180, venue="RIVERPARK", requires=("arrive",), tags=("busy", "kids", "view"), label="리버파크"),
        Action("theatre", "ADMITTED", "THEATRE_OF_LIGHT", 90, requires=("arrive",), tags=("quiet", "kids"), label="빛의 시어터", open_close=TEMP_WINDOWS["THEATRE_OF_LIGHT"][0]),
        Action("library", "IN_LOUNGE", "GRAND_LIBRARY",   40, requires=("key",), tags=("quiet",), label="라이브러리", open_close=TEMP_WINDOWS["GRAND_LIBRARY"][0]),   # 투숙객 전용 2층
    ]
    return checkin + dining + facility


MEAL_KEYS = {"ondal", "geum", "myong", "moegi", "pizza", "pizza_to", "buffet_b", "buffet_l", "lepassage",
             "lux", "lounge_b", "lounge_h", "meal_other"}
CHECKIN_KEYS = {"arrive", "luggage", "queue", "desk", "key"}


# ---------------------------------------------------------------------------
# 운영 창 안에서 가장 이른 시작 — 검증기 창의 season · years · states 를 존중한다
# ---------------------------------------------------------------------------

def earliest_start(a: Action, not_before: datetime) -> datetime | None:
    dwell = timedelta(minutes=a.dwell_min)
    if a.venue is None:
        if a.open_close is None:
            return not_before
        wins = [(a.open_close, None)]
        use_validator = False
    else:
        wins = [((w.open_at, w.close_at), w) for w in WALKERHILL_VENUE_WINDOWS.get(a.venue, ())]
        if not wins:
            return not_before
        use_validator = True

    for day_offset in (0, 1):
        day = (not_before + timedelta(days=day_offset)).date()
        for (o, c), w in wins:
            if w is not None:
                if not w.opens_on(day):
                    continue
                if w.states is not None and a.state not in w.states:
                    continue
                last = datetime.combine(day, w.effective_last_order())
            else:
                last = datetime.combine(day, c)
            open_at = datetime.combine(day, o)
            close_at = datetime.combine(day, c)
            start = max(open_at, not_before) if day_offset == 0 else open_at
            if start > last or start + dwell > close_at:
                continue
            return start
    return None


# ---------------------------------------------------------------------------
# 에이전트
# ---------------------------------------------------------------------------

def run_agent(persona: Persona, start_at: datetime, max_turns: int = 60,
              verbose: bool = True) -> tuple[list[TimelineSegment], list[Trace]]:
    actions = catalog(persona)
    L = PROPERTY[persona.property]
    room = L["room"]

    timeline: list[TimelineSegment] = []
    done: set[str] = set()
    visited: set[str] = set()
    traces: list[Trace] = []
    meals_done: set[tuple] = set()
    included_used: set[tuple] = set()

    here = "HOTEL_GATE"
    now = start_at
    last_key: str | None = None
    takeout_pending = False          # v3-C 포장해 온 음식이 있으면 다음은 객실에서 먹기
    if persona.is_guest:
        end_at = (start_at + timedelta(days=persona.nights)).replace(hour=11, minute=0)
    else:
        end_at = datetime.combine(start_at.date(), persona.depart_by)
    enforce = persona.is_guest

    if verbose:
        unk = persona.unknown_traits()
        print(f"  {persona.property} · {'투숙' if persona.is_guest else '비투숙'} · "
              f"미상 {len(unk)}개: {', '.join(unk) or '없음'}")

    for turn in range(1, max_turns + 1):
        candidates, rejected = [], []
        for a in actions:
            if a.once and a.key in done:
                continue
            if a.requires and not all(r in done for r in a.requires):
                continue
            if a.adults_only and persona.has_child_under_13:
                rejected.append(f"{a.label}: 동반 아동 제한"); continue
            try:
                travel = walkerhill_travel_time_min(here, a.location, now)
            except Exception as e:
                rejected.append(f"{a.label}: {e}"); continue
            arrive = now + timedelta(minutes=round(travel))

            if a.key == "sleep":
                if not (arrive.time() >= SLEEP_CONSIDER_FROM or arrive.time() < WAKE_AT):
                    continue
                if arrive.time() >= SLEEP_CONSIDER_FROM:
                    start = max(arrive, datetime.combine(arrive.date(), SLEEP_FROM))
                    t_out = datetime.combine(arrive.date() + timedelta(days=1), WAKE_AT)
                else:
                    start = arrive
                    t_out = datetime.combine(arrive.date(), WAKE_AT)
                if t_out <= start:
                    continue
            else:
                not_before = next_meal_start(arrive) if a.key in MEAL_KEYS else arrive
                a_fit = replace(a, dwell_min=MIN_DWELL[a.key]) if a.key in MIN_DWELL else a
                start = earliest_start(a_fit, not_before)
                if start is None:
                    rejected.append(f"{a.label}: 남은 운영 창 없음"); continue
                if (start - now) > timedelta(minutes=HORIZON_MIN):
                    rejected.append(f"{a.label}: 시작이 {int((start-now).total_seconds()//60)}분 뒤"); continue
                t_out = start + timedelta(minutes=a.dwell_min)
                if a.key in MIN_DWELL:
                    # v3-E 창 마감까지 남은 만큼만 머문다 (최소 MIN_DWELL)
                    t_out = min(t_out, window_close(a, start) or t_out)

            if a.key in MEAL_KEYS:
                kind = meal_kind_at(start)
                if kind is None:
                    rejected.append(f"{a.label}: 끼니 때 아님"); continue
                # 5. 오늘 아직 안 쓴 포함 끼니가 있으면 같은 끼니의 다른 식사는 안 한다
                inc_place = next((pl for (k2, pl) in persona.included_meals
                                  if k2 == kind and (k2, pl) not in included_used), None)
                if inc_place and (a.venue or a.location) != inc_place:
                    # 같은 업장에 끼니가 다른 행동이 둘 있을 수 있다 (더글라스 라운지 조식 · 더글라스 아워).
                    # 첫 행동만 보면 조식 창(내일)이 잡혀서 규칙이 안 걸렸다 → 같은 끼니의 행동을 고른다.
                    inc_today = None
                    for x in actions:
                        if (x.venue or x.location) != inc_place or x.key not in MEAL_KEYS or x.key == "meal_other":
                            continue
                        x_fixed = MEAL_ONLY.get(x.key) or {"lounge_b": "조식", "lounge_h": "석식"}.get(x.key)
                        if x_fixed and x_fixed != kind:
                            continue
                        es = earliest_start(x, start)
                        if es is not None and es.date() == start.date() and meal_kind_at(es) == kind:
                            inc_today = x; break
                    if inc_today is not None:
                        rejected.append(f"{a.label}: 포함 {kind}({inc_place}) 남음"); continue
                fixed = MEAL_ONLY.get(a.key) or {"lounge_b": "조식", "lounge_h": "석식"}.get(a.key)
                if fixed and fixed != kind:
                    rejected.append(f"{a.label}: {fixed} 전용"); continue
                if (start.date(), kind) in meals_done:
                    rejected.append(f"{a.label}: {kind} 이미 먹음"); continue

            if t_out > end_at and a.key != "sleep":
                rejected.append(f"{a.label}: 종료 시각 넘김"); continue

            # 식당은 착석(SEATED) 뒤에 식사(DINING · COURSE)다 — 검증기 I5. v1 은 파빌리온 SEATED 가
            # 우연히 앞에 있어서 통과했다 (blog02 에서 드러남: 식당 후보가 전부 I5 로 빠졌다).
            pre: list[TimelineSegment] = []
            if a.state in ("DINING", "COURSE_IN_PROGRESS"):
                pre = [TimelineSegment(state="SEATED", location=a.location, t_in=start,
                                       t_out=start + timedelta(minutes=3), machine=a.machine, venue=a.venue)]
                seg_start = start + timedelta(minutes=3)
            else:
                seg_start = start
            seg = TimelineSegment(state=a.state, location=a.location, t_in=seg_start, t_out=t_out,
                                  machine=a.machine, venue=a.venue)
            report = validate_walkerhill_timeline(timeline + pre + [seg], enforce_stay_day=enforce,
                                                  nights=persona.nights)
            if not report.ok:
                rejected.append(f"{a.label}: {report.violations[0].code}"); continue

            wait = (start - arrive).total_seconds() / 60
            # 4. 키 받고 처음 객실에 가는 건 절차 (짐 풀기). 성향 점수를 매기지 않는다.
            if a.key == "room" and "room" not in done and "key" in done:
                # v3-A 짐 풀기는 20분
                seg = replace(seg, t_out=seg.t_in + timedelta(minutes=FIRST_ROOM_MIN))
                candidates.append((20.0, a, seg, travel, wait, ["입실 절차 +20.00"], pre))
                continue
            # v3-C 포장해 온 음식은 객실에서 먹는다 — 끼니는 포장할 때 이미 셌다
            if takeout_pending and a.key == "room":
                seg = replace(seg, t_out=seg.t_in + timedelta(minutes=40))
                candidates.append((15.0, a, seg, travel, wait, ["포장 음식 객실에서 +15.00"], pre))
                continue
            # v1 점수는 key 이름으로 끼니를 알아보고 venue 로 예약 포함을 맞춘다.
            # venue 가 없는 곳(더글라스 라운지 — 검증기에 창이 없어 venue 를 못 붙임)은 location 을 venue 자리에 넣어 넘긴다.
            a_for_score = a
            if a.key in MEAL_KEYS and a.key != "meal_other":
                # v1 은 라운지를 "lounge" 한 키로 안다. lounge_b · lounge_h 그대로 넘기면 끼니 점수(예약 포함 +8)가
                # 안 붙어서 122분 대기 페널티만 남아 포레스트파크에 진다 (blog02 에서 드러남).
                v1_key = {"lepassage": "pizza", "pizza_to": "pizza", "lounge_b": "lounge", "lounge_h": "lounge", "lounge_t": "lounge"}.get(a.key, a.key)
                a_for_score = replace(a, key=v1_key, venue=a.venue or a.location)
            # v3-F 객실에서 기다리는 건 줄이 아니다 — 방에 있으면 다음 창까지의 시간은 대기 벌점 없이 방에서 보낸다
            wait_for_score = 0.0 if (here == room and "key" in done) else wait
            pts, why = score(a_for_score, persona, travel, wait_for_score, visited, start,
                             meals_done, included_used, last_key)
            # 6. 미리 끊어 둔 입장권(리버파크)은 포함 끼니와 같은 예약 사실 — 처음 갈 때 +8
            if a.location in persona.booked and a.location not in visited:
                pts += 8.0; why.append("예약한 시설 +8.00")
            # v3-C 포장은 줄 대신 — 대기 회피만큼
            if "takeout" in a.tags:
                w = persona.w("대기 회피")
                if w:
                    pts += w; why.append(f"줄 대신 포장 +{w:.2f}")
            # v3-D 조식을 방에서 때우기 -1 (투숙객)
            if a.key == "meal_other" and persona.is_guest and meal_kind_at(start) == "조식":
                pts -= 1.0; why.append("호텔 조식 두고 방에서 -1.00")
            candidates.append((pts, a, seg, travel, wait, why, pre))

        if not candidates:
            if verbose:
                print(f"  {turn:2d}  후보 없음 — 종료. 마지막 거절: {rejected[:5]}")
            break

        candidates.sort(key=lambda c: (-c[0], c[1].key))
        if verbose == 2:
            print("        후보:", " | ".join(f"{c[1].label} {c[2].t_in:%H:%M} {c[0]:+.2f} w{c[4]:.0f}" for c in candidates[:8]))
        best = candidates[0]
        # v3-B 빈 시간 채우기 — 최선 후보가 오래 기다려야 하면, 그 전에 끝내고 제때 갈 수 있는 활동을 먼저
        if best[4] >= FILL_WAIT_MIN and best[1].key not in CHECKIN_KEYS and best[1].key != "sleep" and not takeout_pending:
            target_at = best[6][0].t_in if best[6] else best[2].t_in
            fillers = []
            for c in candidates[1:]:
                x = c[1]
                if x.key in MEAL_KEYS or x.key in ("room", "sleep") or x.key in CHECKIN_KEYS:
                    continue
                if c[0] < FILL_MIN_SCORE:
                    continue
                try:
                    back = walkerhill_travel_time_min(x.location, best[1].location, c[2].t_out)
                except Exception:
                    continue
                ready = c[2].t_out + timedelta(minutes=round(back))
                if ready <= target_at:
                    fillers.append(c)
                elif best[1].key in MEAL_KEYS:
                    # 끼니는 창이 길다 — 활동을 먼저 하고 같은 끼니 창 안에서 먹을 수 있으면 채운다 (저녁 전에 전시 · 족욕)
                    b_act = best[1]
                    b_fit = replace(b_act, dwell_min=MIN_DWELL[b_act.key]) if b_act.key in MIN_DWELL else b_act
                    nb = next_meal_start(ready) if b_act.key in MEAL_KEYS else ready
                    s2 = earliest_start(b_fit, max(nb, ready))
                    if s2 is not None and s2.date() == target_at.date() and meal_kind_at(s2) == meal_kind_at(target_at):
                        fillers.append(c)
            if fillers:
                f = fillers[0]
                best = (f[0], f[1], f[2], f[3], f[4], list(f[5]) + [f"빈 시간 채우기 ({best[1].label} 전)"], f[6])
        pts, a, seg, travel, wait, why, pre = best
        if seg.t_out > end_at:
            if verbose:
                print(f"  {turn:2d}  종료 시각 {end_at:%m-%d %H:%M} 도달")
            break

        gap = (seg.t_in - now).total_seconds() / 60
        if gap > 60 and "key" in done:
            back = walkerhill_travel_time_min(here, room, now)
            out = walkerhill_travel_time_min(room, a.location, seg.t_in)
            if back + out + 30 <= gap:
                idle = TimelineSegment(state="IN_ROOM", location=room,
                                       t_in=now + timedelta(minutes=round(back)),
                                       t_out=seg.t_in - timedelta(minutes=round(out)), machine="M2_Stay")
                if validate_walkerhill_timeline(timeline + [idle] + pre + [seg], nights=persona.nights).ok:
                    timeline.append(idle)
                    if verbose:
                        print(f"       {idle.t_in:%m-%d %H:%M}–{idle.t_out:%H:%M}  객실에서 대기 (빈 시간 {gap:.0f}분)")

        timeline.extend(pre)
        timeline.append(seg)
        done.add(a.key); visited.add(a.location)
        here = a.location; now = seg.t_out; last_key = a.key
        if "takeout" in a.tags and persona.is_guest and "key" in done:
            takeout_pending = True
        elif a.key == "room" and takeout_pending:
            takeout_pending = False
        if a.key in MEAL_KEYS:
            k = meal_kind_at(seg.t_in)
            meals_done.add((seg.t_in.date(), k))
            if (k, a.venue or a.location) in persona.included_meals:
                included_used.add((k, a.venue or a.location))
        traces.append(Trace(turn, a.label, seg.t_in, len(actions), len(candidates), rejected[:4], why))
        if verbose:
            print(f"  {turn:2d}  {seg.t_in:%m-%d %H:%M}–{seg.t_out:%H:%M}  {a.label:<14} "
                  f"이동 {travel:>3.0f}분 대기 {wait:>3.0f}분  ({pts:+.2f})  {' · '.join(why[:3])}")

    return timeline, traces


def reachable(persona: Persona) -> set[str]:
    """이 페르소나의 에이전트가 갈 수 있는 장소 — match.py 가 '빈 칸' 을 가르는 데 쓴다."""
    return {a.location for a in catalog(persona)}
