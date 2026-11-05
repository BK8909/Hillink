"""
정합성을 유지하며 의사결정하는 에이전트 — v0

매 턴 후보 행동을 만들고, 검증기에 물어 정합하지 않은 후보를 버린 뒤,
남은 것 중에서 페르소나의 성향으로 고른다.
위반 0건이 구조적으로 보장된다.

실행:  cd timeline && python3 agent_v0.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from walkerhill_timeline_validator import (
    TimelineSegment,
    WALKERHILL_VENUE_WINDOWS,
    validate_walkerhill_timeline,
    walkerhill_travel_time_min,
)

# ---------------------------------------------------------------------------
# 페르소나
# ---------------------------------------------------------------------------

TRAITS = [
    "대기 회피",
    "이동 최소화",
    "격식 선호",
    "조망 중시",
    "새로움 추구",
    "함께 먹기 선호",
    "조용함 선호",
]


@dataclass
class Persona:
    name: str
    # 0.0 ~ 1.0. None 은 미상 — 0 이 아니라 "영향 없음으로 가정하고 계산에서 제외"
    traits: dict[str, float | None]
    party_size: int = 2
    has_child_under_13: bool = False
    nights: int = 1
    note: str = ""
    # v1 부터 쓰는 사실 항목. v0 은 읽지 않는다.
    #   included_meals: 예약에 포함된 식사 (끼니, 업장). 성향이 아니라 예약 시점의 결정.
    #   room_minimal:   후기가 객실 체류를 최소로 한다고 스스로 밝힌 경우
    included_meals: tuple[tuple[str, str], ...] = ()
    room_minimal: bool = False
    # v2 부터 쓰는 사실 항목 (예약 시점에 정해지는 것)
    #   property:    "GRAND" · "VISTA" · "DOUGLAS" — 어느 건물에 묵었나
    #   is_guest:    False 면 비투숙 방문 (체크인 · 객실 · 취침 없음)
    #   club_access: 클럽 객실 예약 — 클럽라운지 조식 · 티타임 · 해피아워 자격
    #   depart_by:   비투숙일 때 떠나는 시각
    #   booked:      미리 끊어 둔 시설 입장권 (blog04 A — 비투숙 리버파크). 끼니의 included_meals 와 같은 성격.
    property: str = "GRAND"
    is_guest: bool = True
    club_access: bool = False
    depart_by: time = time(20, 0)
    booked: tuple[str, ...] = ()
    #   arrival:     도착 수단 — "car_valet" · "car_self" · None(미상 · 셔틀 · 택시). v4 부터 읽는다
    arrival: str | None = None
    #   10/1 · 대표님 매출 온톨로지의 고객 축 네 개 — L5 집계행(성별 · 대표자 연령 · 구성·방문 목적 · AI 유형)에 그대로 적는다.
    #   후기 페르소나는 None(미설정). 격자에서 생성한 손님(generate.py)은 채워진다. 행동 선택에는 아직 안 쓴다.
    sex: str | None = None            # "여성" · "남성" · "미설정"
    age_band: str | None = None       # "20~29세" · "30~49세" · "50세 이상"
    purpose: str | None = None        # 온톨로지 방문 목적 9종 — "커플·기념일" …
    ai_type: str | None = None        # AI 가이드 호캉스 유형 코드 — "FOHE" …
    #   prefers: 이 손님이 끌리는 식당 (검증기 장소 코드). 예약(booked)보다 약한 "가고 싶은 곳" — 격자 손님에게 목적별 식당 선택
    #            기본값을 주는 자리 (10/1 · dining_pref.csv). 후기 페르소나는 비어 있다
    prefers: tuple[str, ...] = ()
    #   wake_at: 기상 시각 (None 이면 WAKE_AT 07:30). 격자 손님은 생성기가 퍼뜨린다 — 전부 같은 시각에 깨면 조식 1부(06:30~08:10)가 빈다
    wake_at: time | None = None
    #   package: 예약한 객실 상품 이름 (소연 상품표 menu.csv 의 "상품" 칸 · 10/2). 생성기가 체크인 전에 고르고, 그 상품의 포함 끼니 ·
    #            클럽 라운지가 included_meals · club_access 로 넘어온다. 매출은 이 상품의 값으로. 후기 페르소나는 None
    package: str | None = None

    def w(self, key: str) -> float:
        v = self.traits.get(key)
        return 0.0 if v is None else v

    def unknown_traits(self) -> list[str]:
        return [k for k in TRAITS if self.traits.get(k) is None]


# ---------------------------------------------------------------------------
# 행동 카탈로그 — 무대는 체크인 + 레스토랑
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Action:
    key: str
    state: str
    location: str
    dwell_min: int
    venue: str | None = None
    machine: str = "M7_Outlet"
    requires: tuple[str, ...] = ()       # 이 행동 전에 끝나 있어야 하는 행동 key
    once: bool = True
    adults_only: bool = False
    tags: tuple[str, ...] = ()
    label: str = ""
    # 검증기 VENUE 목록에 없는 시설의 운영 창. 여기서 임시로 들고 있는다.
    # 검증기에 넣는 것은 별도 커밋 건으로 기록해 두었다.
    open_close: tuple[time, time] | None = None


CHECKIN_FLOW = [
    Action("arrive",  "ARRIVED_ON_PROPERTY", "GRAND_LOBBY",      5, machine="M2_Stay",
           label="도착"),
    Action("luggage", "LUGGAGE_STORED",      "GRAND_LOBBY",      5, machine="M2_Stay",
           requires=("arrive",), label="짐 맡김"),
    Action("queue",   "IN_CHECKIN_QUEUE",    "GRAND_LOBBY",     30, machine="M2_Stay",
           requires=("arrive",), label="체크인 대기"),
    Action("desk",    "AT_FRONT_DESK",       "GRAND_FRONT_DESK", 8, machine="M2_Stay",
           requires=("queue",), label="프런트 응대"),
    Action("key",     "KEY_ISSUED",          "GRAND_FRONT_DESK", 3, machine="M2_Stay",
           requires=("desk",), label="키 수령"),
    Action("room",    "IN_ROOM",             "GRAND_ROOM",      60, machine="M2_Stay",
           requires=("key",), once=False, label="객실"),
]

DINING = [
    Action("ondal",    "COURSE_IN_PROGRESS", "ONDAL",        120, venue="ONDAL",
           requires=("key",), tags=("formal", "shared", "quiet"), label="온달"),
    Action("geum",     "DINING",             "GEUMRYONG",    110, venue="GEUMRYONG",
           requires=("key",), tags=("formal", "shared"), label="금룡"),
    Action("myong",    "DINING",             "MYONGWOLGWAN",  90, venue="MYONGWOLGWAN",
           requires=("key",), tags=("formal", "shared"), label="명월관"),
    Action("moegi",    "DINING",             "MOEGI",         90, venue="MOEGI",
           requires=("key",), tags=("formal", "quiet"), label="모에기"),
    Action("pizza",    "DINING",             "PIZZA_HILL",   120, venue="PIZZA_HILL",
           requires=("key",), tags=("shared", "view", "casual"), label="피자힐"),
    Action("buffet_b", "TIME_LIMIT_ACTIVE",  "THE_BUFFET",    90, venue="THE_BUFFET",
           requires=("key",), tags=("shared", "busy"), label="더뷔페 조식"),
    Action("buffet_l", "TIME_LIMIT_ACTIVE",  "THE_BUFFET",   120, venue="THE_BUFFET",
           requires=("key",), tags=("shared", "busy"), label="더뷔페 중식"),
    Action("pavilion", "SEATED",             "THE_PAVILION",  90, venue="THE_PAVILION",
           requires=("arrive",), tags=("quiet", "casual"), label="더 파빌리온"),
    Action("lux",      "TAB_OPEN",           "LUX_BAR",      100, venue="LUX_BAR",
           requires=("key",), adults_only=True, tags=("view", "quiet", "formal"),
           label="LUX BAR"),
    Action("lounge",   "HAPPY_HOUR_ACTIVE",  "GRAND_CLUB_LOUNGE", 90,
           venue="GRAND_CLUB_LOUNGE", requires=("key",), adults_only=True,
           tags=("view", "quiet"), label="클럽라운지 해피아워"),
]

FACILITY = [
    # 실내수영장 — 취합 후 검증기가 GRAND_POOL / VISTA_POOL 둘로 나뉘고 운영 창도 검증기에 있다.
    # 그래서 venue 를 넣고 임시 open_close 는 뺀다 (검증기가 창을 본다).
    Action("pool",   "ENTERED", "GRAND_POOL",  80, venue="GRAND_POOL", requires=("key",),
           tags=("busy",), label="실내수영장"),
    Action("forest", "ADMITTED", "FOREST_PARK", 90, requires=("arrive",),
           tags=("view", "quiet"), label="포레스트 파크",
           open_close=(time(11, 0), time(20, 0))),     # docs §8.6 ◎
    Action("sauna",  "IN_TREATMENT", "WELLNESS_SAUNA", 60, requires=("key",),
           tags=("quiet",), label="사우나",
           open_close=(time(6, 0), time(21, 0))),      # 후기 안내표 ◎
]

# 취침 — 객실에 머무는 것을 1시간씩 쪼개지 않는다.
SLEEP = Action("sleep", "IN_ROOM", "GRAND_ROOM", 0, machine="M2_Stay",
               requires=("key",), once=False, label="취침")
SLEEP_FROM = time(22, 30)
WAKE_AT = time(7, 30)

ACTIONS = CHECKIN_FLOW + DINING + FACILITY + [SLEEP]
BY_KEY = {a.key: a for a in ACTIONS}


# ---------------------------------------------------------------------------
# 끼니
#
# 성향은 "어디서 먹을까" 를 가르지 "먹을까 말까" 를 가르지 않는다.
# 끼니때가 되면 사람은 먹는다. 그래서 끼니는 성향이 아니라 필요로 둔다.
# ---------------------------------------------------------------------------

MEAL_WINDOWS = {
    "조식": (time(7, 0), time(10, 30)),
    "중식": (time(11, 30), time(15, 0)),
    "석식": (time(17, 30), time(21, 30)),
}

MEAL_ONLY = {"buffet_b": "조식", "buffet_l": "중식", "buffet_d": "석식"}   # buffet_d 는 v4 만 쓴다 (9/29)


def meal_kind_at(at: datetime) -> str | None:
    for kind, (a, b) in MEAL_WINDOWS.items():
        if a <= at.time() <= b:
            return kind
    return None


# ---------------------------------------------------------------------------
# 운영 창 안에서 가장 이른 시작 시각
# ---------------------------------------------------------------------------

def earliest_start(action: Action, not_before: datetime) -> datetime | None:
    """운영 창을 지키면서 not_before 이후 가장 이른 시작 시각. 없으면 None."""
    if action.venue is None:
        if action.open_close is None:
            return not_before
        o, c = action.open_close
        dwell = timedelta(minutes=action.dwell_min)
        for day_offset in (0, 1):
            day = (not_before + timedelta(days=day_offset)).date()
            open_at = datetime.combine(day, o)
            close_at = datetime.combine(day, c)
            start = max(open_at, not_before) if day_offset == 0 else open_at
            if start + dwell <= close_at:
                return start
        return None

    windows = WALKERHILL_VENUE_WINDOWS.get(action.venue)
    if not windows:
        return not_before

    dwell = timedelta(minutes=action.dwell_min)
    for day_offset in (0, 1):
        day = (not_before + timedelta(days=day_offset)).date()
        for w in windows:
            # 10/5 소연 — 그 날 안 여는 창(요일 · 공휴일 · 기간 · 연도)은 건너뛴다. v2~v4 와 같은 규칙.
            # 안 보면 토요일 07:30 에 '화~금 07:00~10:00' 조식 창을 골라, v1 이 검증기 반려로 조식을 놓친다.
            if not w.opens_on(day):
                continue
            open_at = datetime.combine(day, w.open_at)
            close_at = datetime.combine(day, w.close_at)
            last_order = datetime.combine(day, w.effective_last_order())
            start = max(open_at, not_before if day_offset == 0 else datetime.combine(day, time(0, 0)))
            if start > last_order:
                continue
            if start + dwell > close_at:
                continue
            return start
    return None


# ---------------------------------------------------------------------------
# 성향 점수
# ---------------------------------------------------------------------------

def score(action: Action, persona: Persona, travel_min: float,
          wait_min: float, visited: set[str], start: datetime,
          meals_done: set[tuple], last_key: str | None) -> tuple[float, list[str]]:
    s = 0.0
    why: list[str] = []

    def add(pts: float, reason: str):
        nonlocal s
        if abs(pts) < 1e-9:
            return
        s += pts
        why.append(f"{reason} {pts:+.2f}")

    # 체크인 절차는 성향과 무관하게 먼저 끝낸다. 객실 체류는 여기 해당하지 않는다.
    if action.machine == "M2_Stay" and action.key != "room":
        add(20.0, "체크인 절차")
        return s, why

    # 끼니 — 필요이지 성향이 아니다
    is_dining = action.venue is not None and "shared" in action.tags or action.key in MEAL_ONLY
    kind = meal_kind_at(start)
    if action.venue is not None and action.key not in ("pavilion",):
        day = start.date()
        if kind is None:
            add(-4.0, "끼니때 아님")
        elif (day, kind) in meals_done:
            add(-5.0, f"{kind} 이미 먹음")
        else:
            add(6.0, f"{kind} 때")
            fixed = MEAL_ONLY.get(action.key)
            if fixed and fixed != kind:
                add(-6.0, f"{fixed} 전용인데 {kind}")

    if action.key == "sleep":
        add(8.0, "밤이라 취침")
        return s, why

    # 객실 체류 — 갈 데가 없을 때의 기본값
    if action.key == "room":
        add(0.4, "객실에서 쉼")
        if last_key == "room":
            add(-3.0, "직전에도 객실")

    add(-persona.w("대기 회피") * wait_min / 30, f"대기 {wait_min:.0f}분")
    add(-persona.w("이동 최소화") * travel_min / 20, f"이동 {travel_min:.0f}분")

    if "formal" in action.tags:
        add(persona.w("격식 선호") * 1.0, "격식")
    if "casual" in action.tags:
        add(-persona.w("격식 선호") * 0.5, "격식 아님")
    if "view" in action.tags:
        add(persona.w("조망 중시") * 1.0, "조망")
    if "quiet" in action.tags:
        add(persona.w("조용함 선호") * 1.0, "조용함")
    if "busy" in action.tags:
        add(-persona.w("조용함 선호") * 0.8, "붐빔")
    if "shared" in action.tags and persona.party_size >= 2:
        add(persona.w("함께 먹기 선호") * 1.0, "함께 먹기")

    if action.location in visited:
        add(-persona.w("새로움 추구") * 1.2, "이미 가 봄")
    else:
        add(persona.w("새로움 추구") * 0.6, "처음")

    return s, why


# ---------------------------------------------------------------------------
# 에이전트
# ---------------------------------------------------------------------------

@dataclass
class Trace:
    turn: int
    chosen: str
    start: datetime
    considered: int
    feasible: int
    rejected: list[str] = field(default_factory=list)
    why: list[str] = field(default_factory=list)
    # 10/12 경수 · 행동 전환 기록 — 자리가 없어 원래 고르려던 행동 대신 이걸 골랐을 때 {"원래": 라벨, "사유": "만석", "원래_점수": ..}
    switch: dict = field(default_factory=dict)
    # 10/12 경수 · 화면(viewer)용 — 고른 행동의 키 · 장소 · 점수 · 이동 · 대기, 같은 턴의 다른 후보 (점수 · 이유) 와 빠진 후보 전부.
    #   기록만 한다. 행동 선택은 이 칸을 읽지 않는다
    meta: dict = field(default_factory=dict)


def run_agent(persona: Persona, start_at: datetime, max_turns: int = 30,
              verbose: bool = True) -> tuple[list[TimelineSegment], list[Trace]]:
    timeline: list[TimelineSegment] = []
    done: set[str] = set()
    visited: set[str] = set()
    traces: list[Trace] = []

    here = "HOTEL_GATE"
    now = start_at
    meals_done: set[tuple] = set()
    last_key: str | None = None
    checkout = (start_at + timedelta(days=persona.nights)).replace(hour=11, minute=0)

    for turn in range(1, max_turns + 1):
        candidates = []
        rejected = []

        for a in ACTIONS:
            if a.once and a.key in done:
                continue
            if a.requires and not all(r in done for r in a.requires):
                continue
            if a.adults_only and persona.has_child_under_13:
                rejected.append(f"{a.label}: 동반 아동 제한")
                continue

            try:
                travel = walkerhill_travel_time_min(here, a.location, now)
            except Exception as e:
                rejected.append(f"{a.label}: {e}")
                continue

            arrive = now + timedelta(minutes=round(travel))
            start = earliest_start(a, arrive)
            if start is None:
                rejected.append(f"{a.label}: 오늘 남은 운영 창 없음")
                continue

            if a.key == "sleep":
                if start.time() < SLEEP_FROM and start.time() > WAKE_AT:
                    rejected.append("취침: 아직 이름")
                    continue
                wake_day = start.date() + (timedelta(days=1) if start.time() >= SLEEP_FROM else timedelta())
                t_out = datetime.combine(wake_day, WAKE_AT)
                if t_out <= start:
                    rejected.append("취침: 기상 시각이 지남")
                    continue
            else:
                t_out = start + timedelta(minutes=a.dwell_min)

            seg = TimelineSegment(
                state=a.state, location=a.location,
                t_in=start, t_out=t_out,
                machine=a.machine, venue=a.venue,
            )
            report = validate_walkerhill_timeline(
                timeline + [seg], enforce_stay_day=True, nights=persona.nights
            )
            if not report.ok:
                rejected.append(f"{a.label}: {report.violations[0].code}")
                continue

            wait = (start - arrive).total_seconds() / 60
            pts, why = score(a, persona, travel, wait, visited, start, meals_done, last_key)
            candidates.append((pts, a, seg, travel, wait, why))

        if not candidates:
            break

        candidates.sort(key=lambda c: (-c[0], c[1].key))
        pts, a, seg, travel, wait, why = candidates[0]

        if seg.t_out > checkout:
            break

        # 다음 목적지가 열릴 때까지 한 시간 넘게 비면 그 사이는 객실에서 보낸다.
        # 타임라인에 설명되지 않는 구멍을 남기지 않기 위한 것.
        gap = (seg.t_in - now).total_seconds() / 60
        if gap > 60 and "key" in done:
            back = walkerhill_travel_time_min(here, "GRAND_ROOM", now)
            out = walkerhill_travel_time_min("GRAND_ROOM", a.location, seg.t_in)
            if back + out + 30 <= gap:
                idle = TimelineSegment(
                    state="IN_ROOM", location="GRAND_ROOM",
                    t_in=now + timedelta(minutes=round(back)),
                    t_out=seg.t_in - timedelta(minutes=round(out)),
                    machine="M2_Stay",
                )
                if validate_walkerhill_timeline(
                    timeline + [idle, seg], nights=persona.nights
                ).ok:
                    timeline.append(idle)
                    if verbose:
                        print(f"       {idle.t_in:%m-%d %H:%M}–{idle.t_out:%H:%M}  "
                              f"{'객실에서 대기':<16} (빈 시간 {gap:.0f}분을 메움)")

        timeline.append(seg)
        done.add(a.key)
        visited.add(a.location)
        here = a.location
        now = seg.t_out
        last_key = a.key
        k = meal_kind_at(seg.t_in)
        if a.venue is not None and k and a.key != "pavilion":
            meals_done.add((seg.t_in.date(), k))

        traces.append(Trace(turn, a.label, seg.t_in, len(ACTIONS),
                            len(candidates), rejected[:4], why))

        if verbose:
            print(f"  {turn:2d}  {seg.t_in:%m-%d %H:%M}–{seg.t_out:%H:%M}  "
                  f"{a.label:<16} 이동 {travel:>4.0f}분  대기 {wait:>3.0f}분  "
                  f"후보 {len(candidates)}개 중 선택 ({pts:+.2f})")

    return timeline, traces


# ---------------------------------------------------------------------------

PERSONAS = [
    Persona(
        name="가족 동반형",
        traits={"대기 회피": 0.8, "이동 최소화": 0.7, "격식 선호": 0.2,
                "조망 중시": 0.5, "새로움 추구": 0.6, "함께 먹기 선호": 0.9,
                "조용함 선호": 0.3},
        party_size=4, has_child_under_13=True, nights=2,
        note="후기 원문(yisohee)에서 뽑은 조합에 가깝게 잡은 것",
    ),
    Persona(
        name="조용함 우선형",
        traits={"대기 회피": 0.9, "이동 최소화": 0.4, "격식 선호": 0.8,
                "조망 중시": 0.7, "새로움 추구": 0.2, "함께 먹기 선호": 0.3,
                "조용함 선호": 0.9},
        party_size=2, has_child_under_13=False, nights=1,
    ),
    Persona(
        name="성향 대부분 미상",
        traits={"대기 회피": None, "이동 최소화": 0.5, "격식 선호": None,
                "조망 중시": None, "새로움 추구": None, "함께 먹기 선호": None,
                "조용함 선호": None},
        party_size=2, has_child_under_13=False, nights=1,
        note="후기에서 근거를 못 찾은 항목이 많을 때",
    ),
]


if __name__ == "__main__":
    start = datetime.fromisoformat("2025-01-31T14:00")

    for p in PERSONAS:
        print("=" * 78)
        print(f"{p.name}   일행 {p.party_size}명 · {p.nights}박"
              + (" · 13세 미만 동반" if p.has_child_under_13 else ""))
        if p.note:
            print(f"  {p.note}")
        unknown = p.unknown_traits()
        if unknown:
            print(f"  미상 {len(unknown)}개 — {', '.join(unknown)}")
            print("  미상은 0이 아니라 '영향 없음으로 가정'하고 계산에서 제외합니다")
        print("-" * 78)

        timeline, traces = run_agent(p, start)

        report = validate_walkerhill_timeline(timeline, nights=p.nights)
        print("-" * 78)
        print(" ", report.render().replace("\n", "\n  "))
        print()
