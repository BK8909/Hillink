"""실험 전용 동시 착석 조회. 예약·대기·수용 규칙은 Capacity에서 상속한다.

예약의 시작/종료 변화량을 한 번 모아 조회만 빠르게 한다. 기본 모델 파일은 수정하지 않는다.
"""
from bisect import bisect_left, bisect_right
from collections import Counter
from pathlib import Path
import sys

TL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TL))
from capacity import Capacity


class FastCapacity(Capacity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._occupancy_levels = {}

    def _levels(self, venue):
        if venue not in self._occupancy_levels:
            delta = Counter()
            for start, end, n in self.booked[venue]:
                delta[start] += n
                delta[end] -= n
            times, levels, current = [], [], 0
            for t, diff in sorted(delta.items()):
                current += diff
                times.append(t); levels.append(current)
            self._occupancy_levels[venue] = times, levels
        return self._occupancy_levels[venue]

    def load_at(self, venue, t):
        times, levels = self._levels(venue)
        i = bisect_right(times, t)-1
        return levels[i] if i >= 0 else 0

    def load_max(self, venue, t0, t1):
        times, levels = self._levels(venue)
        return max(self.load_at(venue, t0), max(levels[bisect_right(times, t0):bisect_left(times, t1)], default=0))

    def book(self, key, t_in, t_out, party):
        super().book(key, t_in, t_out, party)
        self._occupancy_levels.pop(self.venue_of(key), None)

    def prune(self, before):
        super().prune(before)
        self._occupancy_levels.clear()


def verify_queries():
    """실제 예약 경계와 임의 구간에서 원 구현과 독립 대조한다."""
    from datetime import datetime, timedelta
    import random
    r = random.Random(20261016)
    cap = FastCapacity(seats={'더뷔페': {'n': 288}})
    t = datetime(2026, 10, 21)
    checks = 0
    for i in range(90):
        a = t+timedelta(minutes=r.randrange(0, 2800))
        b = a+timedelta(minutes=r.randrange(1, 181))
        cap.book('buffet_l', a, b, r.randrange(1, 7))
        queries = [a, b, a-timedelta(microseconds=1), b-timedelta(microseconds=1)]
        queries += [t+timedelta(minutes=r.randrange(0, 3000)) for _ in range(8)]
        for q in queries:
            assert cap.load_at('더뷔페', q) == Capacity.load_at(cap, '더뷔페', q)
            end = q+timedelta(minutes=r.randrange(0, 240))
            # 원 load_max의 load_at도 원 구현으로 계산해 같은 함수를 되읽지 않는다.
            points = [q]+[x for x, _, _ in cap.booked['더뷔페'] if q < x < end]
            expected = max(Capacity.load_at(cap, '더뷔페', x) for x in points)
            assert cap.load_max('더뷔페', q, end) == expected
            checks += 2
        if i in (30, 60):
            cap.prune(t+timedelta(minutes=i*10))
    return {'independent_boundary_and_interval_queries': checks, 'all_equal': True}


if __name__ == '__main__':
    import json
    print(json.dumps(verify_queries()))
