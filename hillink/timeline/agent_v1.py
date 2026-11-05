"""
정합성을 유지하며 의사결정하는 에이전트 — v1

v0 을 blog01 페르소나로 돌려 일치율을 재 보니 (run_blog01.py) 이렇게 갈렸다:
  집합 86%/75% · 식당 불일치(금룡) · 순서 60% · 끼니 33% · 금지 1

갈린 지점과 고친 것 — 하나씩 근거를 붙인다.

  1. 키 받고 2시간 반을 그냥 기다렸다가 저녁 뷔페로 갔다 (14:55 → 17:30, 대기 146분)
     원인  대기 비용이 '대기 회피' 성향에만 걸려 있어서, 그 성향이 미상(None)이면 대기가 공짜다.
     고침  시간 비용을 둘로 나눈다. 기다리는 것 자체의 기본 비용(성향 무관) + 성향 가중.
           미상은 "영향 없음"이지 "시간이 안 간다"가 아니다.
           그리고 시작이 지금부터 150분 넘게 남은 후보는 아예 보지 않는다 (지금 할 일을 고른다).

  2. 취침을 안 하고 20:12 객실에서 다음 날 11:00 포레스트파크로 넘어갔다. 조식을 걸렀다.
     원인  취침 후보가 22:30 이후에만 생기는데, 20시대에는 그 시각이 아직 안 와서 후보가 없었다.
     고침  20:00 이후면 취침을 후보에 넣고 시작을 22:30 으로 잡는다. 그 사이는 객실.
           기상 07:30 이후 첫 끼니 필요가 조식으로 잡힌다.

  3. 저녁을 피자힐이 아니라 금룡으로 갔다. 후기는 '피자힐과 더뷔페만' 이라고 못 박았다.
     원인  격식 점수가 formal 에 +w 라서 격식 선호가 낮아도(0.3) formal 이 손해를 안 본다.
           그리고 13세 미만 동반이 식당 선택에 아무 영향이 없었다.
     고침  격식을 0.5 기준 양방향으로: formal 은 (w-0.5)×2, casual 은 (0.5-w)×1.
           13세 미만 동반이면 kids 태그 업장 +1, formal −1. 이건 성향이 아니라 동반 사실에서 나오는 규칙.
           (후기 한 편이 근거라 ○ 수준. 후기가 쌓이면 다시 본다)

  4. 조식 뷔페(buffet_b)를 저녁에 갔다.
     원인  '조식 전용인데 석식' 감점(−6)이 끼니 가점(+6)과 상쇄돼 0 으로 남았다.
     고침  끼니 전용 행동은 다른 끼니 때 후보에서 뺀다. 감점이 아니라 불가.
           식당은 끼니 때가 아니면 후보에서 뺀다 (카페인 파빌리온은 예외).
           같은 날 같은 끼니를 두 번 먹지 않는다 — 감점이 아니라 불가.

  5. 예약에 조식 1회 · 중식 1회(더뷔페)가 포함돼 있었는데 에이전트는 몰랐다.
     원인  페르소나에 성향만 있고 예약 사실이 없었다.
     고침  Persona.included_meals. 포함된 끼니를 그 업장에서 먹으면 +8 (필요 +6 보다 크게).
           식사의 절반은 현장이 아니라 예약 시점에 결정된다 — 이게 이번 라운드의 가장 큰 발견.

  6. 객실 체류 최소형('방에 있을 시간이 별로 없으니')이 반영되지 않았다.
     고침  Persona.room_minimal 이면 객실 후보 −1.

v0 은 그대로 둔다. 같은 페르소나로 둘을 돌려 일치율을 나란히 본다 (run_compare.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta

from walkerhill_timeline_validator import (
    TimelineSegment,
    validate_walkerhill_timeline,
    walkerhill_travel_time_min,
)
from agent_v0 import (
    Action, Persona, Trace, TRAITS,
    CHECKIN_FLOW, DINING, FACILITY, SLEEP, SLEEP_FROM, WAKE_AT,
    MEAL_ONLY, earliest_start,
)

# ---------------------------------------------------------------------------
# 카탈로그 — v0 것을 그대로 쓰고 kids 태그만 덧붙인다
# ---------------------------------------------------------------------------

KIDS_FRIENDLY = {"pizza", "buffet_b", "buffet_l", "pavilion", "pool", "forest"}

def _with_kids(a: Action) -> Action:
    if a.key in KIDS_FRIENDLY and "kids" not in a.tags:
        return replace(a, tags=a.tags + ("kids",))
    return a

ACTIONS = [_with_kids(a) for a in CHECKIN_FLOW + DINING + FACILITY + [SLEEP]]   # MEAL_OTHER 는 아래에서 붙인다

RESTAURANTS = {"ondal", "geum", "myong", "moegi", "pizza", "buffet_b", "buffet_l", "lux", "lounge"}
MEAL_ACTIONS = RESTAURANTS | {"meal_other"}

HORIZON_MIN = 150        # 지금부터 이 시간 안에 시작할 수 있는 것만 후보

# 끼니 창 — v0 은 중식을 11:30 부터로 잡았는데 더뷔페 중식 슬롯은 11:00 에 열린다.
# 창이 업장 슬롯보다 늦으면 '끼니 때 아님' 으로 예약 포함 중식이 후보에서 빠진다 (실제로 그랬다).
MEAL_WINDOWS_V1 = {
    "조식": (time(6, 30), time(10, 30)),
    "중식": (time(11, 0), time(15, 0)),
    "석식": (time(17, 30), time(21, 30)),
}

def meal_kind_at(at: datetime) -> str | None:
    for kind, (a, b) in MEAL_WINDOWS_V1.items():
        if a <= at.time() <= b:
            return kind
    return None


# 7. 후기에 없는 끼니 — 호텔 식당 밖 (편의점 · 인룸 · 외부). 매출이 안 잡히는 식사.
#    후기는 2박 동안 호텔 식사를 셋만 적었다 (조식 · 중식 · 피자힐). 나머지 끼니는 기록이 없다.
#    이 선택지가 없으면 에이전트는 여섯 끼를 전부 호텔 식당에서 먹고, 매출 대조가 부풀려진다.
#    검증기에 '호텔 밖' 상태가 없어서 객실 체류(IN_ROOM)로 둔다 → 멘토링 질문으로 올림.
MEAL_OTHER = Action("meal_other", "IN_ROOM", "GRAND_ROOM", 45, machine="M2_Stay",
                    requires=("key",), once=False, tags=("meal_other",),
                    label="식당 외 식사")
ACTIONS = ACTIONS + [MEAL_OTHER]
BY_KEY = {a.key: a for a in ACTIONS}
SLEEP_CONSIDER_FROM = time(20, 0)
BASE_WAIT_COST_PER_30 = 1.0
CHECKIN_KEYS = {a.key for a in CHECKIN_FLOW if a.key != "room"}


def next_meal_start(t: datetime) -> datetime:
    """t 가 끼니 창 안이면 t, 아니면 다음 끼니 창이 열리는 시각.
    식당은 종일 열려 있어도 사람은 끼니 때 간다. 15:58 에 피자힐이 '끼니 때 아님' 으로
    빠지고 18:00 온달만 남는 일이 실제로 있었다 — 후보를 다음 끼니 시작으로 밀어서 비교한다."""
    if meal_kind_at(t) is not None:
        return t
    for day_offset in (0, 1):
        day = (t + timedelta(days=day_offset)).date()
        for _, (a, _b) in MEAL_WINDOWS_V1.items():
            cand = datetime.combine(day, a)
            if cand >= t:
                return cand
    return t


# ---------------------------------------------------------------------------
# 점수
# ---------------------------------------------------------------------------

def score(action: Action, persona: Persona, travel_min: float, wait_min: float,
          visited: set[str], start: datetime, meals_done: set[tuple],
          included_used: set[tuple], last_key: str | None) -> tuple[float, list[str]]:
    s = 0.0
    why: list[str] = []

    def add(pts: float, reason: str):
        nonlocal s
        if abs(pts) < 1e-9:
            return
        s += pts
        why.append(f"{reason} {pts:+.2f}")

    if action.key in CHECKIN_KEYS:
        add(20.0, "체크인 절차")
        return s, why

    if action.key == "sleep":
        add(8.0, "밤이라 취침")
        return s, why

    # 1. 시간 비용 — 기본 + 성향
    add(-BASE_WAIT_COST_PER_30 * wait_min / 30, f"대기 {wait_min:.0f}분(기본)")
    add(-persona.w("대기 회피") * wait_min / 30, f"대기(성향)")
    add(-persona.w("이동 최소화") * travel_min / 20, f"이동 {travel_min:.0f}분")

    # 5. 끼니 — 필요, 그리고 예약 포함
    kind = meal_kind_at(start)
    if action.key in MEAL_ACTIONS and kind is not None:
        if (kind, action.venue) in persona.included_meals and (kind, action.venue) not in included_used:
            add(8.0, f"{kind} 예약 포함")
        elif action.key == "meal_other":
            add(6.0, f"{kind} 때 · 식당 외")
            # 함께 먹기는 업장이 아니라 식사 자체의 성질이다. 식당 외 식사도 같이 먹는다.
            if persona.party_size >= 2:
                add(persona.w("함께 먹기 선호") * 1.0, "함께 먹기")
            # 업장 성향(격식·조망·새로움)은 붙이지 않는다 — 어느 업장도 아니라서.
            # 호텔 안 식당 vs 식당 외의 경계는 이 한 편으로는 근거가 약하다. 매출 자료가 오면 다시 잰다.
            return s, why
        else:
            add(6.0, f"{kind} 때")

    # 6. 객실
    if action.key == "room":
        add(0.4, "객실에서 쉼")
        if last_key == "room":
            add(-3.0, "직전에도 객실")
        if persona.room_minimal:
            add(-1.0, "객실 체류 최소형")

    # 3. 격식 — 양방향. 동반 아동 규칙
    wf = persona.traits.get("격식 선호")
    if wf is not None:
        if "formal" in action.tags:
            add((wf - 0.5) * 2.0, "격식")
        if "casual" in action.tags:
            add((0.5 - wf) * 1.0, "캐주얼")
    if persona.has_child_under_13:
        if "kids" in action.tags:
            add(1.0, "아동 동반")
        if "formal" in action.tags:
            add(-1.0, "아동 동반인데 격식 업장")

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

def run_agent(persona: Persona, start_at: datetime, max_turns: int = 60,
              verbose: bool = True) -> tuple[list[TimelineSegment], list[Trace]]:
    timeline: list[TimelineSegment] = []
    done: set[str] = set()
    visited: set[str] = set()
    traces: list[Trace] = []
    meals_done: set[tuple] = set()          # (날짜, 끼니)
    included_used: set[tuple] = set()       # (끼니, 업장)

    here = "HOTEL_GATE"
    now = start_at
    last_key: str | None = None
    checkout = (start_at + timedelta(days=persona.nights)).replace(hour=11, minute=0)

    if verbose:
        unk = persona.unknown_traits()
        print(f"  미상 {len(unk)}개: {', '.join(unk) or '없음'} — 0 이 아니라 영향 없음으로 가정")

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

            # 2. 취침 — 20시 이후면 후보. 시작은 22:30 (그 사이는 객실로 메워진다)
            if a.key == "sleep":
                if not (arrive.time() >= SLEEP_CONSIDER_FROM or arrive.time() < WAKE_AT):
                    continue
                if arrive.time() >= SLEEP_CONSIDER_FROM:
                    start = max(arrive, datetime.combine(arrive.date(), SLEEP_FROM))
                    t_out = datetime.combine(arrive.date() + timedelta(days=1), WAKE_AT)
                else:   # 자정 넘어 도착
                    start = arrive
                    t_out = datetime.combine(arrive.date(), WAKE_AT)
                if t_out <= start:
                    continue
            else:
                not_before = next_meal_start(arrive) if a.key in MEAL_ACTIONS else arrive
                start = earliest_start(a, not_before)
                if start is None:
                    rejected.append(f"{a.label}: 오늘 남은 운영 창 없음")
                    continue
                # 1. 지금 할 일을 고른다
                if (start - now) > timedelta(minutes=HORIZON_MIN):
                    rejected.append(f"{a.label}: 시작이 {int((start-now).total_seconds()//60)}분 뒤")
                    continue
                t_out = start + timedelta(minutes=a.dwell_min)

            # 4. 끼니 규칙 — 감점이 아니라 불가
            if a.key in MEAL_ACTIONS:
                kind = meal_kind_at(start)
                if kind is None:
                    rejected.append(f"{a.label}: 끼니 때 아님")
                    continue
                fixed = MEAL_ONLY.get(a.key)
                if fixed and fixed != kind:
                    rejected.append(f"{a.label}: {fixed} 전용")
                    continue
                if (start.date(), kind) in meals_done:
                    rejected.append(f"{a.label}: {kind} 이미 먹음")
                    continue

            seg = TimelineSegment(state=a.state, location=a.location,
                                  t_in=start, t_out=t_out, machine=a.machine, venue=a.venue)
            report = validate_walkerhill_timeline(timeline + [seg], enforce_stay_day=True,
                                                  nights=persona.nights)
            if not report.ok:
                rejected.append(f"{a.label}: {report.violations[0].code}")
                continue

            wait = (start - arrive).total_seconds() / 60
            pts, why = score(a, persona, travel, wait, visited, start,
                             meals_done, included_used, last_key)
            candidates.append((pts, a, seg, travel, wait, why))

        if not candidates:
            if verbose:
                print(f"  {turn:2d}  후보 없음 — 종료. 마지막 거절 사유: {rejected[:5]}")
            break

        candidates.sort(key=lambda c: (-c[0], c[1].key))
        pts, a, seg, travel, wait, why = candidates[0]
        if seg.t_out > checkout:
            if verbose:
                print(f"  {turn:2d}  체크아웃 {checkout:%m-%d %H:%M} 도달 — 종료")
            break

        # 빈 시간이 한 시간 넘으면 객실에서 보낸다
        gap = (seg.t_in - now).total_seconds() / 60
        if gap > 60 and "key" in done:
            back = walkerhill_travel_time_min(here, "GRAND_ROOM", now)
            out = walkerhill_travel_time_min("GRAND_ROOM", a.location, seg.t_in)
            if back + out + 30 <= gap:
                idle = TimelineSegment(state="IN_ROOM", location="GRAND_ROOM",
                                       t_in=now + timedelta(minutes=round(back)),
                                       t_out=seg.t_in - timedelta(minutes=round(out)),
                                       machine="M2_Stay")
                if validate_walkerhill_timeline(timeline + [idle, seg], nights=persona.nights).ok:
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
        if a.key in MEAL_ACTIONS:
            k = meal_kind_at(seg.t_in)
            meals_done.add((seg.t_in.date(), k))
            if (k, a.venue) in persona.included_meals:
                included_used.add((k, a.venue))

        traces.append(Trace(turn, a.label, seg.t_in, len(ACTIONS), len(candidates),
                            rejected[:4], why))
        if verbose:
            print(f"  {turn:2d}  {seg.t_in:%m-%d %H:%M}–{seg.t_out:%H:%M}  "
                  f"{a.label:<16} 이동 {travel:>4.0f}분  대기 {wait:>3.0f}분  "
                  f"후보 {len(candidates)}개 중 선택 ({pts:+.2f})  {' · '.join(why[:4])}")

    return timeline, traces
