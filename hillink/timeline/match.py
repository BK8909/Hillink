"""
일치율 — 후기 실제 경로(정답) vs 에이전트 경로.

정합성 위반 0건은 점수가 아니다. 아무 데도 안 가도 0건이다.
그래서 후기가 실제로 간 곳과 얼마나 겹치는지를 잰다.

정답이 부분적이면 채점도 부분적으로 한다.
  - 방문 집합: 후기가 이용을 못 박은 곳만 (◎). 구경만 한 곳은 안 센다.
  - 순서:     후기에서 순서가 확정되는 쌍만. 시각은 후기에 거의 없으니 채점에 안 쓴다.
  - 도달 불가: 에이전트 행동 목록에 없는 곳은 일치율에서 빼고 따로 "빈 칸"으로 보고한다.
              에이전트 탓이 아니라 카탈로그 탓이라서.

사용
  from match import evaluate, print_report
  r = evaluate(segments, persona_blog01)   # 모듈을 그대로 넘긴다
  print_report(r)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Any

from walkerhill_timeline_validator import TimelineSegment

# 에이전트가 갈 수 있는 곳 — agent_v0.ACTIONS 에서 뽑는다. import 순환을 피하려고 늦게 읽는다.
def _reachable() -> set[str]:
    from agent_v0 import ACTIONS
    return {a.location for a in ACTIONS}


RESTAURANT_KEYS = frozenset({
    "ONDAL", "GEUMRYONG", "MYONGWOLGWAN", "MOEGI", "PIZZA_HILL", "THE_BUFFET",
})
# 채점에서 빼는 장소 — 이동 통과 지점
TRANSIT = frozenset({"HOTEL_GATE"})
# 기본 동선이라 맞아도 의미가 약한 곳. 일치율에는 넣되 따로 표시한다.
BASELINE_PLACES = frozenset({"GRAND_LOBBY", "GRAND_ROOM", "GRAND_FRONT_DESK"})

MEAL_WINDOWS = {
    "조식": (time(6, 30), time(10, 30)),
    "중식": (time(11, 0), time(15, 0)),
    "석식": (time(17, 30), time(21, 30)),
    "간식": (time(15, 0), time(17, 30)),    # 라운지 라이트 스낵 (blog02) — 위 셋 다음에 본다
}
# 끼니로 세는 곳 — 식당 + 먹는 라운지·베이커리. 식당 집합(헤드라인)은 RESTAURANT_KEYS 그대로.
MEAL_PLACES = RESTAURANT_KEYS | frozenset({"GRAND_CLUB_LOUNGE", "DOUGLAS_LOUNGE", "LE_PASSAGE", "LUX_BAR"})


def meal_kind(t) -> str | None:
    tt = t.time()
    for k, (a, b) in MEAL_WINDOWS.items():
        if a <= tt <= b:
            return k
    return None


# ---------------------------------------------------------------------------
# 세그먼트 → 방문 열
# ---------------------------------------------------------------------------

@dataclass
class Visit:
    place: str
    state: str
    t_in: Any
    t_out: Any
    venue: str | None


def visits_from_segments(segments: list[TimelineSegment]) -> list[Visit]:
    """이동 통과 지점을 빼고, 같은 장소에 연속으로 머문 건 하나로 합친다."""
    out: list[Visit] = []
    for s in sorted(segments, key=lambda s: s.t_in):
        place = s.venue or s.location
        if place in TRANSIT:
            continue
        # 같은 장소라도 사이가 10분 넘게 비면 다른 방문이다 (조식 뒤 중식을 같은 뷔페에서 먹는 경우)
        if out and out[-1].place == place and (s.t_in - out[-1].t_out).total_seconds() <= 600:
            out[-1].t_out = max(out[-1].t_out, s.t_out)
            continue
        out.append(Visit(place, s.state, s.t_in, s.t_out, s.venue))
    return out


# ---------------------------------------------------------------------------
# 채점
# ---------------------------------------------------------------------------

@dataclass
class Report:
    title: str
    # 방문 집합
    truth_scorable: set[str]
    agent_places: set[str]
    hit: set[str]
    missed: set[str]
    extra: set[str]
    forbidden_hit: set[str]           # 후기가 안 갔다고 못 박은 곳(◎)에 간 것
    unmentioned_hit: set[str]         # "○ 언급 없음" 인 곳에 간 것 — 금지로 세지 않고 보여만 준다
    unreachable: dict[str, str]       # 정답인데 에이전트 카탈로그에 없는 곳
    # 식당
    truth_restaurants: set[str]
    agent_restaurants: set[str]
    # 순서
    order_checked: int
    order_ok: int
    order_fail: list[tuple[str, str]]
    # 끼니
    meals_truth: list[tuple[str, str]]
    meals_hit: list[tuple[str, str]]
    agent_meal_events: list[tuple[str, str]]   # (끼니, 장소)
    n_visits: int
    restaurants_complete: bool = True   # 페르소나 파일의 TRUTH_RESTAURANTS_COMPLETE (없으면 완전 목록으로 본다)

    @property
    def recall(self) -> float:
        return len(self.hit) / len(self.truth_scorable) if self.truth_scorable else 0.0

    @property
    def precision(self) -> float:
        return len(self.hit) / len(self.agent_places) if self.agent_places else 0.0

    @property
    def jaccard(self) -> float:
        u = self.truth_scorable | self.agent_places
        return len(self.hit) / len(u) if u else 0.0

    @property
    def restaurants_exact(self) -> bool | None:
        """정답 식당 목록이 완전할 때만 완전 일치를 본다. 부분 목록이면 None (슬기 blog05·06 지적)."""
        if not self.restaurants_complete:
            return None
        return self.agent_restaurants == self.truth_restaurants

    @property
    def restaurants_label(self) -> str:
        if self.restaurants_complete:
            return "일치" if self.agent_restaurants == self.truth_restaurants else "불일치"
        # 부분 목록: 확인된 식당을 에이전트가 다 갔나만 본다
        return "부분·포함" if self.truth_restaurants <= self.agent_restaurants else "부분·빠짐"

    @property
    def order_rate(self) -> float | None:
        return self.order_ok / self.order_checked if self.order_checked else None

    @property
    def meal_rate(self) -> float | None:
        # 정답 끼니가 없으면 0% 가 아니라 판단 유보 (슬기 지적 — 전에는 0% 로 찍혔다)
        return len(self.meals_hit) / len(self.meals_truth) if self.meals_truth else None

    @property
    def meal_label(self) -> str:
        return "—" if self.meal_rate is None else f"{self.meal_rate:.0%}"

    def one_line(self) -> str:
        o = "—" if self.order_rate is None else f"{self.order_rate:.0%}"
        return (f"{self.title:24s} 집합 {self.recall:.0%}/{self.precision:.0%}"
                f"  식당 {self.restaurants_label}"
                f"  순서 {o}  끼니 {self.meal_label}"
                f"  금지 {len(self.forbidden_hit)}  방문 {self.n_visits}")


def evaluate(segments: list[TimelineSegment], truth_mod, title: str = "",
             reachable: set[str] | None = None) -> Report:
    reachable = reachable if reachable is not None else _reachable()
    visits = visits_from_segments(segments)
    seq = [v.place for v in visits]
    agent_places = set(seq)

    truth_all = set(truth_mod.TRUTH_VISITED)
    unreachable = {k: v for k, v in truth_mod.TRUTH_UNREACHABLE.items()}
    # 갈 수 없는 곳은 빼되, 실제로 갔으면(손으로 옮긴 정답 등) 채점에 넣는다
    for k in truth_all - reachable - agent_places:
        unreachable[k] = truth_mod.TRUTH_VISITED[k] + " — 에이전트 행동 목록에 없음"
    truth_scorable = truth_all & (reachable | agent_places)

    hit = truth_scorable & agent_places
    missed = truth_scorable - agent_places
    extra = agent_places - truth_all - set(truth_mod.TRUTH_PASSED) - BASELINE_PLACES
    # 금지는 후기가 ◎ 로 못 박은 곳만. "○ 언급 없음" 은 안 갔다는 증거가 아니라 따로 보여 주기만 한다
    not_visited = truth_mod.TRUTH_NOT_VISITED
    forbidden_hit = {p for p in agent_places & set(not_visited) if str(not_visited[p]).startswith("◎")}
    unmentioned_hit = (agent_places & set(not_visited)) - forbidden_hit

    # 순서 — 두 곳 다 갔을 때만 첫 방문 순서로 본다
    first = {}
    for i, p in enumerate(seq):
        first.setdefault(p, i)
    checked = ok = 0
    fail: list[tuple[str, str]] = []
    for a, b, _ in truth_mod.TRUTH_ORDER_PAIRS:
        if a in first and b in first:
            checked += 1
            if first[a] < first[b]:
                ok += 1
            else:
                fail.append((a, b))

    # 끼니 — 식당 방문을 시간대로 끼니에 붙인다
    meal_events: list[tuple[str, str]] = []
    for v in visits:
        if v.place in MEAL_PLACES:
            k = meal_kind(v.t_in)
            meal_events.append((k or "끼니 외", v.place))
    meals_truth = [(k, p) for k, p, _ in truth_mod.TRUTH_MEALS]
    remaining = list(meal_events)
    meals_hit = []
    for k, p in meals_truth:
        if (k, p) in remaining:
            remaining.remove((k, p))
            meals_hit.append((k, p))

    return Report(
        title=title or getattr(truth_mod, "PERSONA").name,
        truth_scorable=truth_scorable, agent_places=agent_places,
        hit=hit, missed=missed, extra=extra, forbidden_hit=forbidden_hit, unmentioned_hit=unmentioned_hit,
        unreachable=unreachable,
        truth_restaurants=set(truth_mod.TRUTH_RESTAURANTS),
        agent_restaurants=agent_places & RESTAURANT_KEYS,
        order_checked=checked, order_ok=ok, order_fail=fail,
        meals_truth=meals_truth, meals_hit=meals_hit, agent_meal_events=meal_events,
        n_visits=len(visits),
        restaurants_complete=getattr(truth_mod, "TRUTH_RESTAURANTS_COMPLETE", True),
    )


def print_report(r: Report) -> None:
    print(f"=== 일치율 · {r.title} ===")
    print(f"  방문 집합   재현 {r.recall:.0%} ({len(r.hit)}/{len(r.truth_scorable)})"
          f"   정밀 {r.precision:.0%} ({len(r.hit)}/{len(r.agent_places)})"
          f"   자카드 {r.jaccard:.2f}")
    base = sorted(r.hit & BASELINE_PLACES)
    real = sorted(r.hit - BASELINE_PLACES)
    print(f"    맞춘 곳     {', '.join(real) or '—'}"
          + (f"   (기본 동선: {', '.join(base)})" if base else ""))
    print(f"    놓친 곳     {', '.join(sorted(r.missed)) or '—'}")
    print(f"    더 간 곳    {', '.join(sorted(r.extra)) or '—'}")
    if r.forbidden_hit:
        print(f"    ✗ 후기가 안 갔다고 못 박은 곳(◎)에 감: {', '.join(sorted(r.forbidden_hit))}")
    if r.unmentioned_hit:
        print(f"    △ 후기에 언급 없는 곳(○)에 감: {', '.join(sorted(r.unmentioned_hit))}  (금지로 안 셈)")
    print(f"  식당 집합   {r.restaurants_label}"
          f"   정답 {sorted(r.truth_restaurants)}  에이전트 {sorted(r.agent_restaurants)}")
    if r.order_checked:
        print(f"  순서        {r.order_ok}/{r.order_checked} 쌍 일치"
              + (f"   어긋난 쌍: {r.order_fail}" if r.order_fail else ""))
    else:
        print("  순서        비교 가능한 쌍 없음")
    print(f"  끼니        {len(r.meals_hit)}/{len(r.meals_truth)} 일치"
          f"   정답 {r.meals_truth}")
    print(f"              에이전트 식사 {len(r.agent_meal_events)}회: {r.agent_meal_events}")
    if r.unreachable:
        print("  빈 칸 (정답인데 에이전트가 갈 수 없는 곳 — 카탈로그 탓)")
        for k, why in r.unreachable.items():
            print(f"    {k:14s} {why}")
    print()


if __name__ == "__main__":
    # 자기 점검: 후기 그대로 옮긴 RUN_C 를 정답에 대보면 거의 만점이 나와야 한다.
    import persona_blog01 as P
    from blog01 import RUN_C
    r = evaluate(RUN_C, P, title="자기 점검 · RUN_C(후기 그대로)")
    print_report(r)
    print(r.one_line())
