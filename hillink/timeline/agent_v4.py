"""
정합성을 유지하며 의사결정하는 에이전트 — v4 (계수를 데이터로 맞추는 버전)

v3 는 개발용 체류 8개에서 71 → 82% 로 올랐지만 봉인한 새 후기 4편에서는 44 → 44% 로 그대로였다 (과적합).
그리고 성향을 전부 지우면 새 후기에서 52% 로 오히려 올랐다 — 지금 성향 가중치가 방해가 된다.
v4 는 규칙을 더 쓰는 대신 세 가지를 바꾼다.

  1. 점수의 숫자들을 계수 θ 로 뺐다 (THETA_DEFAULT). 대기 · 이동 · 성향 반영 강도(lam_trait) · 끼니 · 포함 끼니 ·
     예약 · 포장 · 아동 · 객실 휴식 · 포함 저녁 대체 벌점 · 빈 시간 채우기 켜기 · 선택 온도.
     계수는 사람이 정하지 않고 fit_v4.py 가 교차검증(후기 하나씩 빼고 나머지로 맞춰 뺀 후기로 채점)으로 고른다.
  2. 항상 1등만 고르지 않고 점수에 비례해 확률로 고른다 (tau). 같은 사람을 여러 번 돌리면
     "포함 저녁이 있어도 피자도 포장해 온다" (blog07) 같은 경우가 자연스럽게 나온다. v2 규칙 5 의 금지는 벌점(incl_block)으로 바꿨다.
  3. 구조 · 사실 보강 (v2 처럼 후기에 상관없이 통하는 쪽):
     Persona.arrival (자차 발렛 · 자차 주차) → 발렛 · 주차타워를 거쳐 도착 (blog01 · 03 B · 04 A · 09 · 10)
     더글라스 라이브러리 행동 (blog10) · Persona.booked 에 식당 예약도 (blog09 네이버 예약)

아래는 v3 머리말 그대로.

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
import math, random, zlib
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
    # FOREST_PARK — 10/7 소연: 검증기 창으로 옮겼다 (공식 11:00~20:00 · 7/1~9/27 21:00 · 입장 제한일). 아래 forest 행동이 venue 로 본다
    # WELLNESS_SAUNA · THEATRE_OF_LIGHT — 10/11 소연: 검증기 창으로 옮겼다 (사우나 06:00~22:00 · 그랜드 휴관일 / 빛의 시어터 10:00~18:00 ·
    #   입장 마감 17:00 — 공식). 아래 sauna · theatre 행동이 venue 로 본다. 전 임시값은 06:00~21:00 (blog01 안내표) · 10:00~19:00 (△ blog06)
    "GRAND_LIBRARY":    ((time(7, 0), time(22, 0)),),                                    # △
    # 더글라스 라운지 — 검증기에 창이 없다. blog02 후기(◎ 라이트 스낵 15–17 · 더글라스 아워 19–21 · 조식 07:30경)
    "DOUGLAS_LOUNGE":   ((time(7, 0), time(10, 0)), (time(15, 0), time(17, 0)), (time(19, 0), time(21, 0))),
}


# 10/8 소연 · 와인페어 입장 대상 (경수 부탁의 '고를 수 있는 것') — 1 이면 비투숙도 (기본), 0 이면 투숙객만.
#   10/11 기본을 1 로 — 워커힐 보도자료 (9/14) "네이버와 카카오톡을 통해 사전 구매할 경우 10% 할인 혜택을 받을 수 있다" — 외부 판매가 있다
#   (가정표 FOREST_PARK '와인페어 입장 대상'). 10/8 엔 공식 홈페이지에 외부 판매가 안 적혀 0 (투숙객만) 이었다.
#   generate.py --set agent_v4.WINE_FAIR_PUBLIC=0 으로 바꾼다 (정수로 둔다 — bool 이면 '0' 도 True 가 된다)
WINE_FAIR_PUBLIC = 1
# 10/12 경수 · 행동 전환 기록 — run_agent 가 "자리가 없어 원래 선택 대신 다른 행동" 을 고를 때마다 한 줄 (generate.py 가 reroute_log.csv 로 쓴다)
SWITCH_LOG: list[dict] = []

FIRST_ROOM_MIN = 20      # v3-A 짐 풀기
# v3-E 늦게 들어가도 창 마감까지는 머무는 곳 — 라운지 3창 · 뷔페 회차. 값은 최소 체류(분)
#   blog02 라이트 스낵 '16시대' · blog04 B 티타임 16:10–17:00 · blog05 조식 회차 — 정해진 체류가 창에 안 들어가 통째로 빠지던 것
MIN_DWELL = {"lounge_b": 30, "lounge_t": 30, "lounge_h": 40, "buffet_b": 40, "buffet_l": 50, "buffet_d": 50}
def busy_short(th: dict, key: str) -> bool:
    """붐빌 때 최소 체류로 줄이는가. 10/16 조정값 no_busy_dwell — 1 = 더뷔페 모든 식사에서 끔 · 2 = 중식 · 석식만 끔 (조식은 그대로) · 근거사슬 7-17 · 7-19"""
    nb = th.get("no_busy_dwell") or 0
    return not (nb == 1 or (nb == 2 and key in ("buffet_l", "buffet_d")))


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


def turn_window(a: Action, start: datetime) -> bool:
    """10/16 — 회차제 창인가. 모에기는 식사별 1회라 늘 회차로 본다. 더뷔페는 같은 날 바로 앞뒤(60분 안)에
    다른 창이 붙어 있을 때만 회차(1부 · 2부)로 본다. 화~금 조식 07:00~10:00 처럼 한 창으로 여는 날에
    좌석을 창 끝까지 잡으면 끼니당 한 번만 앉게 돼 온톨로지의 회전 상한 2와도 맞지 않는다."""
    v = a.venue or a.location
    if v == "MOEGI":
        return True
    ws = [w for w in WALKERHILL_VENUE_WINDOWS.get(v, ()) if w.opens_on(start.date())]
    d = start.date()
    for w in ws:
        o, c = datetime.combine(d, w.open_at), datetime.combine(d, w.close_at)
        if o <= start < c:
            for x in ws:
                if x is w:
                    continue
                xo, xc = datetime.combine(d, x.open_at), datetime.combine(d, x.close_at)
                if timedelta(0) <= xo - c <= timedelta(minutes=60) or timedelta(0) <= o - xc <= timedelta(minutes=60):
                    return True
            return False
    return False


def catalog(p: Persona) -> list[Action]:
    L = PROPERTY[p.property]
    lobby, desk, room, pool, lounge = L["lobby"], L["desk"], L["room"], L["pool"], L["lounge"]
    lounge_venue = lounge if lounge in WALKERHILL_VENUE_WINDOWS else None

    # v4 도착 수단 — 자차면 발렛 · 주차타워를 거친다 (사실 항목)
    pre_arrive: list[Action] = []
    if p.arrival == "car_valet":
        pre_arrive = [Action("valet", "VALET_RECEIVED", "VALET_DESK", 4, machine="M5_Transport", label="발렛")]
    elif p.arrival == "car_self":
        pre_arrive = [Action("park", "PARKED", "PARKING_TOWER_B1", 10, machine="M5_Transport", label="주차")]
    checkin = pre_arrive + [
        Action("arrive",  "ARRIVED_ON_PROPERTY", lobby, 5, machine="M2_Stay",
               requires=tuple(a.key for a in pre_arrive), label="도착"),
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
        # 10/11 경수 · 피자힐 착석 90분 — 1부 11:30 부터 90분씩 7부 (10/7 현장 안내판 · 비스타 공식 페이지 · 소연 PR #31).
        #   120분이면 마지막 시작이 20:00 이라 실제 7부 (20:30) 를 못 쓴다. 상품표 · 검증기 창은 이미 90분 7부제
        Action("pizza",    "DINING",             "PIZZA_HILL",    90, venue="PIZZA_HILL",   requires=key_req, tags=("shared", "view", "casual", "kids"), label="피자힐"),
        # v3-C 피자힐 포장 — 주문·수령 20분. 먹는 건 객실에서 (아래 run_agent)
        Action("pizza_to", "TAKEOUT_ORDER",      "PIZZA_HILL",    20, venue="PIZZA_HILL",   requires=key_req, tags=("casual", "kids", "takeout"), label="피자힐 포장"),
        Action("buffet_b", "TIME_LIMIT_ACTIVE",  "THE_BUFFET",    90, venue="THE_BUFFET",   requires=key_req, tags=("shared", "busy", "kids"), label="더뷔페 조식"),
        Action("buffet_l", "TIME_LIMIT_ACTIVE",  "THE_BUFFET",   120, venue="THE_BUFFET",   requires=key_req, tags=("shared", "busy", "kids"), label="더뷔페 중식"),
        # 9/29 · 더뷔페 석식 — 검증기 창(17:30–19:30 · 20:00–22:00)은 있는데 행동이 없어서 예약(booked)한 저녁 손님이
        #   피자힐로 갔다 (blog31 · 40 · 41 · 52 — 더뷔페 디너 후기 4편)
        Action("buffet_d", "TIME_LIMIT_ACTIVE",  "THE_BUFFET",   120, venue="THE_BUFFET",   requires=key_req, tags=("shared", "busy", "kids"), label="더뷔페 석식"),
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
        Action("forest",  "ADMITTED", "FOREST_PARK",      90, venue="FOREST_PARK", requires=("arrive",), tags=("view", "quiet", "kids"), label="포레스트 파크"),
        Action("sauna",   "IN_TREATMENT", "WELLNESS_SAUNA", 60, venue="WELLNESS_SAUNA", requires=("key",), tags=("quiet",), label="사우나"),
        Action("skyard",  "ADMITTED", "SKYARD",           40, venue="SKYARD", requires=("arrive",), tags=("view", "quiet"), label="스카이야드"),
        Action("river",   "ENTERED",  "RIVERPARK",       180, venue="RIVERPARK", requires=("arrive",), tags=("busy", "kids", "view"), label="리버파크"),
        Action("theatre", "ADMITTED", "THEATRE_OF_LIGHT", 90, venue="THEATRE_OF_LIGHT", requires=("arrive",), tags=("quiet", "kids"), label="빛의 시어터"),
        Action("library", "IN_LOUNGE", "GRAND_LIBRARY",   40, requires=("key",), tags=("quiet",), label="라이브러리", open_close=TEMP_WINDOWS["GRAND_LIBRARY"][0]),   # 투숙객 전용 2층
    ]
    if p.property == "DOUGLAS":   # v4 더글라스 1층 라이브러리 — 투숙 기간 24시간 (blog10 ◎)
        facility.append(Action("dlibrary", "IN_LOUNGE", "DOUGLAS_LIBRARY", 40, requires=("key",), tags=("quiet", "view"), label="더글라스 라이브러리"))
    acts = checkin + dining + facility
    # 10/8 소연 · 와인페어 (경수 부탁) — 자리는 포레스트 파크, 창은 검증기 WINE_FAIR (2026 10/10~25 의 토 · 일 · 1부 11–15 · 2부 15:30–20).
    #   그 날은 포레스트 파크 일반 이용이 막혀 forest 행동은 안 열리고 이것만 연다. 체류 120분은 가정 (△ — 근거 없음).
    #   포레스트 파크 출입 표 (비투숙 불가) 는 일반 이용 규칙이라 여기엔 안 쓴다 — 누가 들어가나는 WINE_FAIR_PUBLIC 이 정한다
    fair = [Action("winefair", "ADMITTED", "FOREST_PARK", 120, venue="WINE_FAIR", requires=("arrive",), tags=("view",), label="와인페어")] \
        if (p.is_guest or WINE_FAIR_PUBLIC) else []
    # 9/29 소연 · 시설 출입 표 (검증기 FACILITY_ACCESS) — 이 손님이 못 들어가는 곳(불가)은 행동에서 뺀다.
    #   모름(근거 없음)은 막지 않는다. 비투숙이 스카이야드 · 포레스트파크 · 라이브러리 · 수영장으로 가던 것이 여기서 막힌다
    try:
        from walkerhill_timeline_validator import may_enter
    except ImportError:
        return acts + fair
    guest = dict(is_guest=p.is_guest, building=p.property if p.is_guest else None, club_access=bool(p.club_access))
    return [a for a in acts if may_enter(a.location, **guest) is not False] + fair


BAR_MIX = {"커플·기념일": 40.0, "친구·모임": 25.0, "비즈니스·접대": 20.0, "미식 방문": 15.0}   # 온톨로지 럭스바 풀 고객 믹스 (10월 기준 · mix_ledger)
BAR_MIX_MAX = max(BAR_MIX.values())


def planned(persona, key: str, th: dict) -> bool | None:
    """럭스바 · 르파사쥬를 '계획한 팀만 가는' 조정값이 켜져 있으면 이 팀이 계획했는지 (None = 조정값 꺼짐)"""
    if key == "lux" and th.get("bar_nightcap"):
        mix, rate, tag = BAR_MIX, th["bar_nightcap"], "bar"
    elif key == "lepassage" and th.get("passage_rate"):
        mix, rate, tag = PASSAGE_MIX, th["passage_rate"], "passage"
    else:
        return None
    wt = mix.get(persona.purpose or "", 0.0)
    u = (zlib.crc32(f"{persona.name}|{tag}".encode()) % 10000) / 10000
    return wt > 0 and u < rate * wt / max(mix.values())
PASSAGE_MIX = {"커플·기념일": 30.0, "가족·친족": 30.0, "친구·모임": 20.0, "미식 방문": 20.0}   # 온톨로지 르파사쥬 독립 구매 풀 고객 믹스
MEAL_KEYS = {"ondal", "geum", "myong", "moegi", "pizza", "pizza_to", "buffet_b", "buffet_l", "buffet_d", "lepassage",
             "lux", "lounge_b", "lounge_h", "meal_other", "meal_out"}   # meal_out = 비투숙 호텔 밖 식사 (실험 조정값 meal_split 일 때만 생김)
CHECKIN_KEYS = {"valet", "park", "arrive", "luggage", "queue", "desk", "key"}
# 10/14 가설 H4 — 평일 저녁 호텔 식당 계획. 독립 검증에서 평일(10/7 · 10/14) 식당 이용이 온톨로지의 1.25~1.5배였다.
# 모델은 저녁마다 거의 모든 투숙 팀이 호텔 식당을 찾아 좌석이 늘 차고, 온톨로지는 평일 저녁 점유율 50% 안팎이다.
# 조정값 wd_dine = 평일에 투숙 팀이 그날 저녁을 호텔 식당에서 먹기로 한 비율. 계획이 없는 팀은 식당 밖 식사 쪽으로 간다 (포함 끼니 · 예약 · 비투숙은 그대로)
# 조정값 wd_named = 1 이면 유명 업장(WD_NAMED — SNS 게시물 최다 · 10/7 현장 평일 저녁 거의 만석)은 평일에도 계획과 상관없이 찾는다
DINE_KEYS = {"ondal", "geum", "myong", "moegi", "pizza", "buffet_d"}
WD_NAMED = {"PIZZA_HILL"}
HOLIDAYS = {"2026-09-24", "2026-09-25", "2026-09-26", "2026-10-03", "2026-10-05", "2026-10-09"}


def is_weekday(d) -> bool:
    # Use the same public-holiday calendar as venue windows, including other seasons.
    from walkerhill_timeline_validator import is_public_holiday
    return d.weekday() < 5 and not is_public_holiday(d)


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

# ---------------------------------------------------------------------------
# v4 계수 — 기본값은 v3 와 같은 동작. fit_v4.py 가 교차검증으로 고친다
# ---------------------------------------------------------------------------

THETA_DEFAULT = dict(
    w_wait=1.0,          # 대기 30분당 기본 비용
    w_travel=0.0,        # 이동 20분당 기본 비용 (성향과 별개)
    lam_trait=1.0,       # 성향 7개가 점수에 들어가는 강도 (0 이면 성향 무시)
    meal=6.0,            # 끼니 때 식사 가점
    included=8.0,        # 예약에 포함된 끼니
    meal_other=0.0,      # 식당 밖 식사 — 식당 대비 가감 (0 이면 식당과 같은 6)
    bfast_room=1.0,      # 투숙객이 조식을 방에서 때우면 벌점
    kids=1.0,            # 13세 미만 동반 — 아이 시설 가점 · 격식 업장 벌점
    takeout=1.0,         # 포장 가점 × 대기 회피
    room_rest=0.4,       # 객실에서 쉼
    booked=8.0,          # 미리 예약한 시설 · 식당에 처음 갈 때
    prefer=3.0,          # 10/1 가고 싶던 식당 (Persona.prefers) — 예약보다 약하게. 식당 외 식사(+0.33)를 넘기되 이동 · 대기는 여전히 센다
    incl_block=99.0,     # 포함 저녁이 남았는데 다른 저녁 — 벌점 (50 이상이면 v2 처럼 금지)
    gap_fill=1.0,        # 빈 시간 채우기 켜기 (0 · 1)
    tau=0.0,             # 선택 온도 (0 이면 항상 1등)
)


# fit_v4.py 가 교차검증으로 고른 계수 (2026-09-24 확정). 10 폴드 모두 같은 값을 골랐다 — 흔들리지 않음.
#   선택 기준 = 확률 점수(Brier): 여러 번 돌렸을 때 장소마다 '갈 확률' 이 후기와 얼마나 맞나 (매출 대조와 같은 방향)
#   성향 강도 lam_trait = 0 · 이동 비용 1.47 · 확률 선택 tau 2 · 빈 시간 채우기 켬
THETA_FIT_0924 = {"w_wait": 0.5923173259845662, "w_travel": 1.4696647598132695, "lam_trait": 0, "meal": 6.0, "included": 5.749474668549004, "meal_other": 0.7993340537517142, "bfast_room": 1.6137127253520316, "kids": 1.5040936495502613, "takeout": 1.8120750303821465, "room_rest": 1.1757516514065607, "booked": 3.8455539306643494, "incl_block": 99.0, "gap_fill": 1.0, "tau": 2.0}
# ↑ 9/24 · 후기 10편(체류 12)으로 고른 계수 — 봉인 시험 2 에서 v2 · 인기도에 짐 (docs/v4_교차검증_시험.md)
THETA_FIT = {"w_wait": 0.8983561398079523, "w_travel": 1.1404126838031146, "lam_trait": 0, "meal": 6.0, "included": 7.884896313357884, "meal_other": 0.3299565338710213, "bfast_room": 1.0523809827825645, "kids": 0.6892480577003421, "takeout": 1.5610287476491085, "room_rest": 1.3329332359000041, "booked": 5.003308859256185, "incl_block": 99.0, "gap_fill": 0.0, "tau": 0.5}
# 실험용 덮어쓰기 — 환경변수 WH_THETA_OVERRIDE='{"takeout_base": -3}' 처럼 주면 그 키만 바꾼다 (10/13 · 온톨로지 대조 실험). 기본은 비어 있어 행동이 같다
import os as _os, json as _json
THETA_FIT.update(_json.loads(_os.environ.get("WH_THETA_OVERRIDE", "{}")))
# ↑ 9/29 · 후기 46편(체류 48)으로 고른 계수 (Brier 기준 · 39/46 폴드 같음) — fit_v4_result.json theta_fit_brier
#   성향 계수 lam_trait 0 (모든 폴드) · booked 5.0 · included 7.88 · tau 0.5
K_RUNS = 12  # 확률 선택이라 한 사람을 여러 번 돌린다 (9/29 · 6 → 12, blend_v4 와 같게)
BLEND_ALPHA = 0.4   # 9/29 · 분포 예측은 p = α·v4 + (1−α)·인기도 — 46 폴드 전부 (tau 0.5, α 0.4) 를 고름 (blend_v4_result.json)



def score_v4(action: Action, persona: Persona, travel_min: float, wait_min: float, visited: set[str],
             start: datetime, meals_done: set[tuple], included_used: set[tuple], last_key: str | None,
             th: dict) -> tuple[float, list[str]]:
    s = 0.0
    why: list[str] = []
    lam = th["lam_trait"]

    def add(pts, reason):
        nonlocal s
        if abs(pts) < 1e-9:
            return
        s += pts; why.append(f"{reason} {pts:+.2f}")

    def w(k):
        v = persona.traits.get(k)
        return 0.0 if v is None else v * lam

    if action.key in CHECKIN_KEYS:
        add(20.0, "체크인 절차"); return s, why
    if action.key == "sleep":
        add(8.0, "밤이라 취침"); return s, why

    add(-th["w_wait"] * wait_min / 30, f"대기 {wait_min:.0f}분")
    add(-w("대기 회피") * wait_min / 30, "대기(성향)")
    add(-(th["w_travel"] + w("이동 최소화")) * travel_min / 20, f"이동 {travel_min:.0f}분")

    kind = meal_kind_at(start)
    # 10/13 실험 조정값 bar_nightcap — 럭스바를 끼니가 아니라 저녁 뒤 한잔(나이트캡)으로 본다. 온톨로지 럭스바 풀 고객 믹스(커플 40 · 친구 25 · 비즈니스 20 · 미식 15)를 목적별 가중으로. 기본 없음 (전과 같다)
    # 10/13 실험 조정값 passage_rate — 르파사쥬를 저녁 대용 포장이 아니라 온톨로지처럼 '독립 구매'(고메 바스켓)로 본다. 값 = 가장 많이 사는 목적의 구매 계획 비율, 온톨로지 르파사쥬 풀 믹스(커플 30 · 가족 30 · 친구 20 · 미식 20). 기본 없음
    if action.key == "lepassage" and th.get("passage_rate"):
        wt = PASSAGE_MIX.get(persona.purpose or "", 0.0)
        p_go = th["passage_rate"] * wt / max(PASSAGE_MIX.values())
        u = (zlib.crc32(f"{persona.name}|passage".encode()) % 10000) / 10000
        if wt > 0 and u < p_go:
            add(6.0, f"르파사쥬 구매 계획 ({persona.purpose})")
        else:
            add(-99.0, "르파사쥬 구매 계획 없음")
        return s, why
    if action.key == "lux" and th.get("bar_nightcap"):
        # 값 = 가장 많이 가는 목적(커플)의 '오늘 밤 한잔 하기로 한' 비율. 다른 목적은 온톨로지 믹스 비만큼 낮다. 정한 팀만 가고(+6), 안 정한 팀은 후보에서 사실상 빠진다
        wt = BAR_MIX.get(persona.purpose or "", 0.0)
        p_go = th["bar_nightcap"] * wt / BAR_MIX_MAX
        u = (zlib.crc32(f"{persona.name}|bar".encode()) % 10000) / 10000
        if wt > 0 and u < p_go:
            add(6.0, f"저녁 뒤 한잔 계획 ({persona.purpose})")
        else:
            add(-99.0, "오늘 밤 바 계획 없음")
        return s, why
    if action.key in MEAL_KEYS and kind is not None:
        venue = action.venue or action.location
        if (kind, venue) in persona.included_meals and (kind, venue) not in included_used:
            add(th["included"], f"{kind} 예약 포함")
        elif action.key == "meal_other":
            add(th["meal"] + th["meal_other"], f"{kind} 때 · 식당 밖")
            if persona.party_size and persona.party_size >= 2:
                add(w("함께 먹기 선호"), "함께 먹기")
            if persona.is_guest and kind == "조식":
                add(-th["bfast_room"], "호텔 조식 두고 방에서")
            return s, why
        else:
            add(th["meal"], f"{kind} 때")
            if th.get("wd_dine") is not None and kind == "석식" and action.key in DINE_KEYS and persona.is_guest \
                    and venue not in persona.booked and is_weekday(start.date()) \
                    and not (th.get("wd_named") and venue in WD_NAMED):
                u = (zlib.crc32(f"{persona.name}|{start.date()}|dine".encode()) % 10000) / 10000
                if u >= th["wd_dine"]:
                    add(-8.0, "평일 저녁 호텔 식당 계획 없음")

    if action.key == "room":
        add(th["room_rest"], "객실에서 쉼")
        if last_key == "room":
            add(-3.0, "직전에도 객실")
        if persona.room_minimal:
            add(-1.0, "객실 체류 최소형")

    wf = persona.traits.get("격식 선호")
    if wf is not None:
        if "formal" in action.tags:
            add(lam * (wf - 0.5) * 2.0, "격식")
        if "casual" in action.tags:
            add(lam * (0.5 - wf), "캐주얼")
    if persona.has_child_under_13:
        if "kids" in action.tags:
            add(th["kids"], "아동 동반")
        if "formal" in action.tags:
            add(-th["kids"], "아동 동반인데 격식 업장")
    if "view" in action.tags:
        add(w("조망 중시"), "조망")
    if "quiet" in action.tags:
        add(w("조용함 선호"), "조용함")
    if "busy" in action.tags:
        add(-w("조용함 선호") * 0.8, "붐빔")
    if "shared" in action.tags and (persona.party_size or 2) >= 2:
        add(w("함께 먹기 선호"), "함께 먹기")
    if action.location in visited:
        add(-w("새로움 추구") * 1.2, "이미 가 봄")
    else:
        add(w("새로움 추구") * 0.6, "처음")
    if action.location in persona.booked and action.location not in visited:
        add(th["booked"], "예약한 곳")
    if action.location in persona.prefers and action.location not in visited:
        add(th.get("prefer", 3.0), "가고 싶던 곳")     # 10/1 격자 손님의 식당 선택 기본값 (dining_pref.csv)
    if "takeout" in action.tags:
        add(th["takeout"] * (persona.traits.get("대기 회피") or 0.0), "줄 대신 포장")
        base = th.get("takeout_base" if action.key == "pizza_to" else "passage_base")
        if base:
            add(base, "포장 기본 감점")      # 10/13 실험용 계수 (피자힐 포장 · 르파사쥬 따로) — 기본 0 (온톨로지 포장 비중 대조)
    return s, why


def run_agent(persona: Persona, start_at: datetime, max_turns: int = 60,
              verbose: bool = True, theta: dict | None = None,
              rng: random.Random | None = None, capacity=None) -> tuple[list[TimelineSegment], list[Trace]]:
    """capacity: capacity.Capacity — 같은 날 손님들이 나눠 쓰는 식당 좌석 (10/1). None 이면 전과 같다 (후기 재현 · 적합)"""
    th = dict(THETA_DEFAULT, **(theta or {}))
    rng = rng or random.Random(0)
    actions = catalog(persona)
    # 10/13 실험 조정값 fine_dwell — 온톨로지 '파인다이닝 식사시간'(기본 120분)을 금룡 · 온달 · 명월관 체류에 그대로 (모델 기본 110 · 120 · 90). 기본 없음
    if th.get("fine_dwell"):
        actions = [replace(a, dwell_min=int(th["fine_dwell"])) if a.key in ("geum", "ondal", "myong") else a for a in actions]
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
        blocked = []        # 10/12 · 자리가 없어 빠진 행동과 그때 받았을 점수 — 전환 기록용
        for a in actions:
            incl_pen = 0.0
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
                wake = persona.wake_at or WAKE_AT          # 10/1 격자 손님은 기상 시각이 퍼져 있다
                if not (arrive.time() >= SLEEP_CONSIDER_FROM or arrive.time() < wake):
                    continue
                if arrive.time() >= SLEEP_CONSIDER_FROM:
                    start = max(arrive, datetime.combine(arrive.date(), SLEEP_FROM))
                    t_out = datetime.combine(arrive.date() + timedelta(days=1), wake)
                else:
                    start = arrive
                    t_out = datetime.combine(arrive.date(), wake)
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
                # 10/13 실험 조정값 takeout_cap — 피자힐 독립 포장은 하루 처리 한도가 있다 (온톨로지: 한도 60판 · 기준 수요 30판/일). 기본 없음
                if a.key == "pizza_to" and capacity is not None and th.get("takeout_cap") is not None:
                    if getattr(capacity, "takeout", {}).get(("PIZZA_HILL", start.date()), 0) >= th["takeout_cap"]:
                        rejected.append(f"{a.label}: 포장 한도"); continue
                # 10/1 좌석 상한 — 자리가 없으면 자리 나는 시각까지 밀린다 (대기 벌점). 창 안에 자리가 안 나면 빠진다
                reserve_at = None          # 회차 배정으로 다음 회차에 앉게 된 경우 그 회차 시작 (예약 대기 — 벌점 없음)
                if capacity is not None and capacity.venue_of(a.key):
                    # 10/16 — 좌석 검사도 실제로 잡을 구간으로 (아래 확정과 같은 식). 붐비면 최소 체류 · 창 마감에서 자르기 · 회차제는 회차 끝까지
                    def _hold_end(t, a=a, a_fit=a_fit):
                        _d = a_fit.dwell_min if (a.key in MIN_DWELL and busy_short(th, a.key) and capacity.busy(a.key, t, persona.party_size)) else a.dwell_min
                        _e = t + timedelta(minutes=_d)
                        if a.key in MIN_DWELL:
                            _wc = window_close(a, t)
                            _e = min(_e, _wc) if _wc else _e
                        _tt = t + timedelta(minutes=3 if a.state in ("DINING", "COURSE_IN_PROGRESS") else 0)
                        if th.get("turn_hold") and (a.venue or a.location) in ("THE_BUFFET", "MOEGI") and turn_window(a, _tt):
                            _e = max(_e, window_close(a, _tt) or _e)
                        return _e
                    seated_at = capacity.delay(a.key, start, a_fit.dwell_min, persona.party_size, window_close(a, start), hold_end=_hold_end)
                    # 10/13 실험 조정값 queue_max — 도착 → 착석 줄이 이 분수를 넘으면 이 회차는 포기 (소연 가정표: 50분 넘는 줄은 포기 → 30분 제안). 기본 없음
                    _qm = th.get("queue_max")
                    if _qm is not None and seated_at is not None and (seated_at - start) > timedelta(minutes=_qm):
                        # 줄이 상한을 넘는다 — 예약 대기를 켰고 다음 회차(자리 나는 시각)가 예약 범위 안이면 그 회차를 예약한 것으로 (피자힐 7부처럼 창이 하나인 식당), 아니면 이 회차는 포기
                        if th.get("reserve_wait") and (seated_at - now) <= timedelta(minutes=th.get("reserve_horizon", 300)):
                            reserve_at = seated_at
                        else:
                            seated_at = None
                    # 10/13 실험 조정값 next_window — 이 회차 창에 자리가 없으면 같은 날 다음 회차 창(더뷔페 석식 2부 20:00 등)을 본다 (회차 배정). 기본 꺼짐 (전과 같다)
                    if seated_at is None and th.get("next_window"):
                        _close = window_close(a, start)
                        while _close is not None and seated_at is None:
                            _nxt = earliest_start(a_fit, _close + timedelta(minutes=1))
                            if _nxt is None or _nxt.date() != start.date() or (a.key in MEAL_KEYS and meal_kind_at(_nxt) != meal_kind_at(start)):
                                break
                            seated_at = capacity.delay(a.key, _nxt, a_fit.dwell_min, persona.party_size, window_close(a, _nxt), hold_end=_hold_end)
                            if _qm is not None and seated_at is not None and (seated_at - _nxt) > timedelta(minutes=_qm):
                                seated_at = None
                            if seated_at is not None:
                                reserve_at = _nxt
                            _close = window_close(a, _nxt) if seated_at is None else _close
                    full_reason = None
                    if seated_at is None:
                        full_reason = "만석"
                    elif reserve_at is not None and th.get("reserve_wait"):
                        pass                                       # 예약 대기 — 상한도 벌점도 안 본다 (회차 배정)
                    elif seated_at != start and (seated_at - now) > timedelta(minutes=th.get("wait_horizon", HORIZON_MIN)):   # 대기 상한 (분) — 실험 조정값, 기본 HORIZON_MIN
                        full_reason = f"만석 (자리 {int((seated_at-start).total_seconds()//60)}분 뒤)"
                    if full_reason:
                        capacity.note_turned_away(a.key, persona.name, start)
                        rejected.append(f"{a.label}: {full_reason}")
                        # 자리가 있었다면 받았을 점수 — 이 행동이 1등이었는지 뒤에서 본다 (전환 기록)
                        # 10/13 · 자리가 있었어도 뒤 규칙(끼니 전용 · 이미 먹은 끼니 · 종료 시각)에 걸렸을 행동은 넣지 않는다.
                        #   전엔 저녁 시각의 '더뷔페 조식' (조식 전용이라 어차피 빠질 행동) 이 원래 선택으로 잡혔다
                        _kind = meal_kind_at(start) if a.key in MEAL_KEYS else None
                        _fixed = MEAL_ONLY.get(a.key) or {"lounge_b": "조식", "lounge_h": "석식"}.get(a.key)
                        if a.key in MEAL_KEYS and (_kind is None or (_fixed and _fixed != _kind) or (start.date(), _kind) in meals_done):
                            continue
                        if start + timedelta(minutes=a_fit.dwell_min) > end_at:
                            continue
                        try:
                            _k = {"lepassage": "pizza", "pizza_to": "pizza", "lounge_b": "lounge", "lounge_h": "lounge", "lounge_t": "lounge"}.get(a.key, a.key)
                            _a = replace(a, key=_k, venue=a.venue or a.location) if (a.key in MEAL_KEYS and a.key != "meal_other") else a
                            _w = 0.0 if (here == room and "key" in done) else (start - arrive).total_seconds() / 60
                            _pts, _ = score_v4(_a, persona, travel, _w, visited, start, meals_done, included_used, last_key, th)
                            blocked.append((_pts, a, full_reason, start))
                        except Exception:
                            pass
                        continue
                    if seated_at != start:
                        start = seated_at
                    # 10/16 조정값 no_busy_dwell (busy_short) — 붐벼도 체류를 줄이지 않는다. '붐비면 최소 체류만' 은 v3-E 창 맞춤용 임시값이고 근거가 없다 (근거사슬 7-13 · 7-17 · 7-19)
                    if a.key in MIN_DWELL and busy_short(th, a.key) and capacity.busy(a.key, start, persona.party_size):
                        a = a_fit                                   # 붐비면 최소 체류만 하고 일어난다
                t_out = start + timedelta(minutes=a.dwell_min)
                if a.key in MIN_DWELL:
                    # v3-E 창 마감까지 남은 만큼만 머문다 (최소 MIN_DWELL)
                    t_out = min(t_out, window_close(a, start) or t_out)

            if planned(persona, a.key, th) is False:
                rejected.append(f"{a.label}: 계획 없음"); continue      # 계획 안 한 팀은 후보에서 뺀다 (점수 −99 로 두면 다른 후보가 없을 때 골라졌다)
            if a.key in MEAL_KEYS and not ((a.key == "lux" and th.get("bar_nightcap")) or (a.key == "lepassage" and th.get("passage_rate"))):
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
                        if th["incl_block"] >= 50:
                            rejected.append(f"{a.label}: 포함 {kind}({inc_place}) 남음"); continue
                        incl_pen = th["incl_block"]
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
            if reserve_at is not None and th.get("reserve_wait"):
                wait = max(0.0, (start - reserve_at).total_seconds() / 60)      # 예약 대기: 다음 회차 시작까지는 안 센다 (회차 안 줄만)
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
            pts, why = score_v4(a, persona, travel, wait_for_score, visited, start,
                                meals_done, included_used, last_key, th)
            if incl_pen:
                pts -= incl_pen; why.append(f"포함 저녁 두고 다른 저녁 -{incl_pen:.2f}")
            candidates.append((pts, a, seg, travel, wait, why, pre))

        # 10/16 실험 조정값 meal_split — '식당 외 식사' 를 두 갈래로. 투숙 손님의 '객실 · 호텔 밖 식사' 는 그대로 두고,
        #   비투숙 손님에게 '호텔 밖 식사 (방문 종료)' 를 연다. 점수는 투숙 손님의 식당 외 식사와 같은 식(끼니 6 + 식당 밖 0.33)이라
        #   선택지 하나를 나눈 것이지 새 가점을 주는 것이 아니다. 1 = 끼니 때마다 후보, 2 = 그 끼니의 식당이 막혔을 때만 후보. 기본 꺼짐 (전과 같다)
        if th.get("meal_split") and not persona.is_guest and "arrive" in done:
            try:
                _tr = walkerhill_travel_time_min(here, "HOTEL_GATE", now)
            except Exception:
                _tr = None
            if _tr is not None:
                _arr = now + timedelta(minutes=round(_tr))
                _st = next_meal_start(_arr)
                _kind = meal_kind_at(_st)
                _blk = any(b[1].key in MEAL_KEYS and meal_kind_at(b[3]) == _kind for b in blocked)
                if _kind is not None and (_st.date(), _kind) not in meals_done and _st <= end_at \
                        and (_st - now) <= timedelta(minutes=HORIZON_MIN) and (th["meal_split"] != 2 or _blk):
                    _a = Action("meal_out", "EXITED", "HOTEL_GATE", 0, machine="M2_Stay", tags=("meal_other",), label="호텔 밖 식사 (방문 종료)")
                    _w = (_st - _arr).total_seconds() / 60
                    _pts, _why = score_v4(replace(_a, key="meal_other"), persona, _tr, _w, visited, _st, meals_done, included_used, last_key, th)
                    _seg = TimelineSegment(state="EXITED", location="HOTEL_GATE", t_in=_st, t_out=_st, machine="M2_Stay")
                    candidates.append((_pts, _a, _seg, _tr, _w, _why, []))

        if not candidates:
            if verbose:
                print(f"  {turn:2d}  후보 없음 — 종료. 마지막 거절: {rejected[:5]}")
            break

        candidates.sort(key=lambda c: (-c[0], c[1].key))
        if verbose == 2:
            print("        후보:", " | ".join(f"{c[1].label} {c[2].t_in:%H:%M} {c[0]:+.2f} w{c[4]:.0f}" for c in candidates[:8]))
        best = candidates[0]
        if th["tau"] > 0 and len(candidates) > 1 and best[1].key not in CHECKIN_KEYS:
            # v4 확률 선택 — 점수 차이가 tau 보다 크면 거의 1등, 비슷하면 골고루
            top = candidates[0][0]
            ws = [math.exp((c[0] - top) / th["tau"]) for c in candidates]
            best = rng.choices(candidates, weights=ws, k=1)[0]
        # v3-B 빈 시간 채우기 — 최선 후보가 오래 기다려야 하면, 그 전에 끝내고 제때 갈 수 있는 활동을 먼저
        if th["gap_fill"] >= 0.5 and best[4] >= FILL_WAIT_MIN and best[1].key not in CHECKIN_KEYS and best[1].key != "sleep" and not takeout_pending:
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
        if a.key == "meal_out":
            # 비투숙 손님이 호텔 밖에서 먹기로 함 — 방문이 여기서 끝난다. 동선에는 넣지 않고 기록(트레이스)만 남긴다
            switch = {}
            if blocked:
                b_pts, b_act, b_reason, b_start = max(blocked, key=lambda b: b[0])
                if b_pts > pts:
                    switch = {"원래": b_act.label, "원래_키": b_act.key, "사유": b_reason, "원래_점수": round(b_pts, 2),
                              "대체": a.label, "대체_키": a.key, "대체_점수": round(pts, 2), "시각": b_start}
                    SWITCH_LOG.append(dict(switch, 손님=persona.name, 투숙=persona.is_guest, 날짜=seg.t_in.date()))
            top_pts = candidates[0][0]
            meta = dict(key=a.key, location=a.location, venue=None, state=a.state, t_out=seg.t_out, pts=round(pts, 2),
                        travel=round(travel, 1), wait=round(max(0.0, wait), 1),
                        rank=next((i + 1 for i, c in enumerate(candidates) if c[1].key == a.key), None),
                        top_gap=round(top_pts - pts, 2), tau=th["tau"],
                        alts=[dict(label=c[1].label, key=c[1].key, location=c[1].location, t=c[2].t_in, pts=round(c[0], 2),
                                   travel=round(c[3], 1), wait=round(max(0.0, c[4]), 1), why=list(c[5])) for c in candidates[:6]],
                        rejected=list(rejected))
            traces.append(Trace(turn, a.label, seg.t_in, len(actions), len(candidates), rejected[:4], why, switch, meta))
            if verbose:
                print(f"  {turn:2d}  {seg.t_in:%m-%d %H:%M}  {a.label}  ({pts:+.2f})")
            break
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
        if capacity is not None and a.key == "pizza_to":
            if not hasattr(capacity, "takeout"):
                capacity.takeout = {}
            # 판 단위로 센다 (온톨로지 포장 풀 단위 · menu.qty_of 와 같은 식: 성인 2명당 1판)
            _pans = max(1, math.ceil((persona.party_size - (1 if persona.has_child_under_13 else 0)) / 2))
            capacity.takeout[("PIZZA_HILL", seg.t_in.date())] = capacity.takeout.get(("PIZZA_HILL", seg.t_in.date()), 0) + _pans
        if capacity is not None and capacity.venue_of(a.key):
            # 좌석은 착석 절차(pre · 3분)부터 잡는다 — 후보 검사가 그 시각(start)을 보기 때문. seg.t_in 으로 잡으면 같은 시각에 온 손님들이 서로를 못 본다
            _hold = seg.t_out
            # 10/13 실험 조정값 turn_hold — 회차제 식당(더뷔페 1부 · 2부, 모에기 식사별 1회)은 좌석을 회차 창 끝까지 잡는다 (온톨로지: 더뷔페 끼니당 회전 상한 2 · 모에기 1회). 기본 없음 (체류 끝에 자리가 난다)
            # 10/16 — 한 창으로 여는 날(화~금 조식 · 평일 중식 · 일~금 석식)은 회차가 아니라 체류 끝에 자리가 난다 (turn_window)
            if th.get("turn_hold") and (a.venue or a.location) in ("THE_BUFFET", "MOEGI") and turn_window(a, seg.t_in):
                _hold = max(seg.t_out, window_close(a, seg.t_in) or seg.t_out)
            capacity.book(a.key, (pre[0].t_in if pre else seg.t_in), _hold, persona.party_size)
            capacity.note_delay(a.key, max(0.0, wait), seg.t_in)
        done.add(a.key); visited.add(a.location)
        here = a.location; now = seg.t_out; last_key = a.key
        if "takeout" in a.tags and persona.is_guest and "key" in done and not (a.key == "lepassage" and th.get("passage_rate")):
            takeout_pending = True
        elif a.key == "room" and takeout_pending:
            takeout_pending = False
        if a.key in MEAL_KEYS and not ((a.key == "lux" and th.get("bar_nightcap")) or (a.key == "lepassage" and th.get("passage_rate"))):
            k = meal_kind_at(seg.t_in)
            meals_done.add((seg.t_in.date(), k))
            if (k, a.venue or a.location) in persona.included_meals:
                included_used.add((k, a.venue or a.location))
        switch = {}
        if blocked:
            b_pts, b_act, b_reason, b_start = max(blocked, key=lambda b: b[0])
            if b_pts > pts and b_act.key != a.key:
                # 자리만 있었으면 그걸 골랐을 것 — 원래 선택 · 실패 사유 · 대체 선택
                switch = {"원래": b_act.label, "원래_키": b_act.key, "사유": b_reason, "원래_점수": round(b_pts, 2),
                          "대체": a.label, "대체_키": a.key, "대체_점수": round(pts, 2), "시각": b_start}
                SWITCH_LOG.append(dict(switch, 손님=persona.name, 투숙=persona.is_guest, 날짜=seg.t_in.date()))
        # 10/12 · 화면용 근거 — 같은 턴 후보 상위 여섯 (점수 순) · 빠진 후보 전부. 선택에는 안 쓴다
        top_pts = candidates[0][0]
        meta = dict(key=a.key, location=a.location, venue=a.venue, state=a.state, t_out=seg.t_out, pts=round(pts, 2),
                    travel=round(travel, 1), wait=round(max(0.0, wait), 1),
                    rank=next((i + 1 for i, c in enumerate(candidates) if c[1].key == a.key), None),
                    top_gap=round(top_pts - pts, 2), tau=th["tau"],
                    alts=[dict(label=c[1].label, key=c[1].key, location=c[1].location, t=c[2].t_in, pts=round(c[0], 2),
                               travel=round(c[3], 1), wait=round(max(0.0, c[4]), 1), why=list(c[5]))
                          for c in candidates[:6]],
                    rejected=list(rejected))
        traces.append(Trace(turn, a.label, seg.t_in, len(actions), len(candidates), rejected[:4], why, switch, meta))
        if verbose:
            print(f"  {turn:2d}  {seg.t_in:%m-%d %H:%M}–{seg.t_out:%H:%M}  {a.label:<14} "
                  f"이동 {travel:>3.0f}분 대기 {wait:>3.0f}분  ({pts:+.2f})  {' · '.join(why[:3])}")

    return timeline, traces


def reachable(persona: Persona) -> set[str]:
    """이 페르소나의 에이전트가 갈 수 있는 장소 — match.py 가 '빈 칸' 을 가르는 데 쓴다."""
    return {a.location for a in catalog(persona)}
