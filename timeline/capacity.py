"""
좌석 상한 — 같은 날 손님들이 식당 좌석을 나눠 쓴다 (10/1)

왜
  하루 손님 생성기로 10/10 을 돌리니 더파빌리온에 1,000명 넘게 갔다. 81석 × 3회전이면 243명이 한도다.
  대표님 온톨로지는 좌석 × 회차 × 점유율로 공급을 자르는데, 에이전트는 가고 싶은 대로 다 갔다.
  이 모듈이 "지금 그 식당에 자리가 있나" 를 답한다. 자리가 없으면 자리가 날 때까지의 시간이 대기로 붙고(w_wait 벌점),
  그 날 운영 창 안에 자리가 안 나면 그 행동은 빠진다 → 에이전트가 다른 데로 간다. 이게 "붐빌 때 어디로 가나" 다.

어떻게
  Capacity 하나를 그 날 손님 전부가 공유한다 (generate.py). 에이전트가 식당 행동을 고를 때마다 book() 으로 좌석을 잡아 두고,
  다음 손님은 delay() 로 "이 시각에 n 명 앉을 수 있나 · 없으면 언제 되나" 를 묻는다.
  좌석 수는 prices.SEATS (소연 가정표 · 홈페이지). 회차는 안 쓴다 — 체류 시간(dwell)이 시간축에서 회전을 자연히 만든다.
  붐비면(앉고 나서 좌석 절반 이상이 차면) 뷔페 · 라운지는 최소 체류(MIN_DWELL)만 하고 일어난다 — 그래야 2부 조식 90분 창에 회전이 생긴다.
  포장(pizza_to) · 르파사쥬(좌석 없음) · 라운지(클럽 전용) 는 안 센다.

  후기 재현(revenue.py · fit_v4)에는 안 붙는다 — 후기 한 편은 그 날 혼자이고 좌석 경쟁이 없다.

  10/2 — 이어지는 날짜를 돌릴 때 Capacity 하나를 날짜들이 공유한다 (generate.py). 2박 손님의 둘째 날 끼니는 체크인 날 에이전트가 둘째 날
  시각으로 미리 잡아 두므로, 둘째 날 손님들이 같은 좌석을 두고 경쟁한다 (한호 지적: 전엔 이어묵는 손님이 객실만 차지하고 식당엔 안 갔다).
  먼저 온 손님이 먼저 앉는 셈이라 2박 손님이 둘째 날 좌석에서 유리하다 — 가정. 집계(summary · turned_away · delayed)는 날짜별로 센다.
"""

from __future__ import annotations

from bisect import insort
from datetime import datetime, timedelta

from prices import L3, SEATS

# 행동 키 → 좌석을 세는 업장 (L3 이름). 좌석 개념 없는 곳은 뺀다
SEATED = {k: l3 for k, (l2, l3) in L3.items() if l3 in SEATS and k not in ("pizza_to", "lepassage")}


class Capacity:
    def __init__(self, seats: dict | None = None, occupancy: float = 1.0):
        """occupancy: 좌석 중 실제로 팔 수 있는 비율 (온톨로지 좌석 점유율 55% 같은 손잡이. 1.0 = 좌석 전부)"""
        seats = seats or SEATS
        self.cap = {name: max(1, int(v["n"] * occupancy)) for name, v in seats.items()}
        self.booked: dict[str, list[tuple[datetime, datetime, int]]] = {name: [] for name in self.cap}
        self.turned_away: dict[tuple, int] = {}      # (업장, 날짜) → 돌려보낸 횟수
        self.events: list[tuple[str, str, datetime]] = []   # (손님 이름, 행동 키, 시각) — 돌려보낸 기록. "붐빌 때 어디로 가나" 표의 재료 (10/2)
        self.delayed_min: dict[tuple, float] = {}    # (업장, 날짜) → 대기 분 합

    def venue_of(self, key: str) -> str | None:
        return SEATED.get(key)

    def load_at(self, venue: str, t: datetime) -> int:
        return sum(n for a, b, n in self.booked[venue] if a <= t < b)

    def load_max(self, venue: str, t0: datetime, t1: datetime) -> int:
        """[t0, t1) 동안의 최대 동시 착석 인원 — 시작 시각만 보면 뒤에 들어오는 예약과 겹치는 걸 놓친다"""
        pts = [t0] + [a for a, b, n in self.booked[venue] if t0 < a < t1]
        return max(self.load_at(venue, t) for t in pts)

    def delay(self, key: str, start: datetime, dwell_min: int, party: int,
              close: datetime | None, hold_end=None) -> datetime | None:
        """start 부터 dwell 동안 party 명이 앉을 수 있으면 start, 아니면 가능한 첫 시각. 창 마감 전에 안 되면 None

        hold_end(t): t 에 앉으면 좌석을 실제로 언제까지 잡는지 (book() 에 넘길 종료 시각). 10/16 고침 —
        전에는 최소 체류(dwell)만큼만 비었는지 보고, 확정은 회차 끝(turn_hold) · 전체 체류로 해서 동시 착석이 좌석 수를 넘었다
        (10/10 더뷔페 조식 2부 304명 / 288석). 이제 검사와 확정이 같은 구간 [t, hold_end(t)) 을 본다. 없으면 t + dwell (예전과 같음)"""
        venue = self.venue_of(key)
        if venue is None:
            return start
        cap = self.cap[venue]
        dwell = timedelta(minutes=dwell_min)
        # 자리가 나는 시각은 누군가의 t_out 뿐이다 → start 와 그 시각들만 순서대로 본다
        cands = [start] + sorted(b for a, b, n in self.booked[venue] if b > start)
        for t in cands:
            if close is not None and t + dwell > close:
                return None
            end = hold_end(t) if hold_end is not None else t + dwell
            if self.load_max(venue, t, max(end, t + dwell)) + party <= cap:
                return t
        return None

    def over_cap(self) -> list[tuple[str, int, int, datetime]]:
        """좌석 수를 넘은 동시 착석이 있으면 (업장, 좌석, 최대 동시, 시각) — 모든 예약 시작 시각에서 센다 (정산 검증용 · 10/16)"""
        out = []
        for venue, bk in self.booked.items():
            for t in sorted(set(a for a, b, n in bk)):
                load = sum(n for a, b, n in bk if a <= t < b)
                if load > self.cap[venue]:
                    out.append((venue, self.cap[venue], load, t))
        return out

    def busy(self, key: str, t: datetime, party: int, ratio: float = 0.5) -> bool:
        """앉고 나면 좌석의 ratio 이상이 차나 — 붐비면 최소 체류(MIN_DWELL)만 하고 일어난다 (agent_v4 가 묻는다)"""
        venue = self.venue_of(key)
        if venue is None:
            return False
        return self.load_at(venue, t) + party >= ratio * self.cap[venue]

    def book(self, key: str, t_in: datetime, t_out: datetime, party: int):
        venue = self.venue_of(key)
        if venue is not None:
            insort(self.booked[venue], (t_in, t_out, party))

    def note_turned_away(self, key: str, who: str | None = None, t: datetime | None = None):
        venue = self.venue_of(key)
        if venue is not None:
            d = t.date() if t is not None else None
            self.turned_away[(venue, d)] = self.turned_away.get((venue, d), 0) + 1
            if who is not None and t is not None:
                self.events.append((who, key, t))

    def note_delay(self, key: str, minutes: float, t: datetime | None = None):
        venue = self.venue_of(key)
        if venue is not None and minutes > 0:
            d = t.date() if t is not None else None
            self.delayed_min[(venue, d)] = self.delayed_min.get((venue, d), 0.0) + minutes

    def prune(self, before: datetime):
        """before 이전에 끝난 예약 · 그 전의 돌려보낸 기록을 버린다 — 날짜를 이어 돌릴 때 좌석표가 자라지 않게 (10/2)"""
        for venue in self.booked:
            self.booked[venue] = [b for b in self.booked[venue] if b[1] >= before]
        self.events = [e for e in self.events if e[2] >= before]

    def summary(self, day=None) -> list[tuple[str, int, int, int, float]]:
        """업장 · 좌석 · 앉은 인원 · 돌려보낸 횟수 · 대기 분 합. day 를 주면 그 날(착석 시각 기준)만"""
        out = []
        for venue in self.cap:
            seated = sum(n for a, _, n in self.booked[venue] if day is None or a.date() == day)
            away = sum(v for (vn, d), v in self.turned_away.items() if vn == venue and (day is None or d == day))
            dmin = sum(v for (vn, d), v in self.delayed_min.items() if vn == venue and (day is None or d == day))
            out.append((venue, self.cap[venue], seated, away, dmin))
        return out
