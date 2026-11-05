"""
붐빌 때 어디로 가나 — 좌석이 없어 돌려보낸 손님이 그 끼니를 결국 어디서 해결했나 (10/2)

왜
  대표님 모델은 좌석 × 회차 × 점유율로 공급을 자르고 끝이다. 우리 손님은 자리가 없으면 다른 데로 간다 — 피자힐인지 포장인지
  객실에서 먹는지 안 먹는지. 좌석 상한(capacity.py)이 이미 그 선택을 시키고 있는데 세지만 않았다. 이 표가 "변칙 상황(만석)에서의 예측" 의 첫 숫자다.

어떻게
  capacity.events 에 (손님, 행동 키, 시각) 으로 돌려보낸 기록이 쌓인다. 손님마다 끼니(조식 · 중식 · 석식)별로 가장 많이 돌려보내진 업장을
  "원래 가려던 곳" 으로 잡고(선호 식당이 그중에 있으면 그것), 그 손님의 지출 줄에서 같은 끼니에 실제로 돈을 쓴 업장을 "간 곳" 으로 잡는다.
  같은 끼니에 쓴 줄이 없으면 "안 먹음 · 다른 끼니". 손님 · 끼니 당 한 번만 센다.

  출력: 원래 가려던 곳 × 간 곳 행렬 (팀 수) — generate.py 가 날짜마다 찍고 reroute.csv 에 쓴다
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from datetime import datetime, timedelta

from agent_v1 import meal_kind_at, MEAL_WINDOWS_V1
from agent_v4 import MEAL_KEYS
from prices import L3

HERE = Path(__file__).resolve().parent
MEAL_SLOTS = ("조식", "중식", "석식")
SLOT_OF_KEY = {"buffet_b": "조식", "buffet_l": "중식", "buffet_d": "석식"}
# 검증기 장소 코드 → 행동 키 (Persona.prefers 와 맞추기)
PLACE_KEY = {"THE_BUFFET": "buffet", "PIZZA_HILL": "pizza", "GEUMRYONG": "geum", "MYONGWOLGWAN": "myong",
             "MOEGI": "moegi", "ONDAL": "ondal", "THE_PAVILION": "pavilion", "LE_PASSAGE": "lepassage"}


def venue_name(key: str) -> str:
    if key == "meal_other":
        return "식당 외 식사"
    if key == "pizza_to":
        return "피자힐 포장"
    return L3.get(key, ("", key))[1] or key


def matrix(cap, stays_lines):
    """→ (Counter[(원래, 간 곳)] 팀 수, 돌려보내진 손님 수)"""
    by_who = defaultdict(lambda: defaultdict(Counter))      # who → (날짜, 끼니) → Counter(key)
    for who, key, t in cap.events:
        slot = SLOT_OF_KEY.get(key) or meal_kind_at(t)
        if slot in MEAL_SLOTS:
            by_who[who][(t.date(), slot)][key] += 1
    out = Counter()
    who_seen = set()
    for (n, label, m), lines in stays_lines:
        p = m.PERSONA
        if p.name not in by_who:
            continue
        who_seen.add(p.name)
        # 손님이 그 끼니 창에 실제로 호텔에 있었나 — 15시 체크인 손님의 "중식", 저녁 손님의 다음 날 "조식" 은 에이전트가 따져 본 것일 뿐 끼니가 아니다
        start = m.START_AT
        end = (datetime.combine(start.date() + timedelta(days=max(1, p.nights)), datetime.min.time()) + timedelta(hours=11)) if p.is_guest \
            else datetime.combine(start.date(), p.depart_by)
        pref = {PLACE_KEY.get(v, v) for v in (p.prefers or ())}
        for (day, slot), cnt in by_who[p.name].items():
            w0, w1 = (datetime.combine(day, x) for x in MEAL_WINDOWS_V1[slot])
            if min(w1, end) - max(w0, start) < timedelta(minutes=60):
                continue
            # 원래 가려던 곳 — 선호 식당이 돌려보내진 곳에 있으면 그것, 아니면 가장 많이 돌려보내진 곳
            cands = [k for k in cnt if (k in pref) or (k.startswith("buffet") and "buffet" in pref)]
            intended = cands[0] if cands else cnt.most_common(1)[0][0]
            went = [ln for ln in lines if ln["key"] in MEAL_KEYS and ln["at"].date() == day and meal_kind_at(ln["at"]) == slot]
            if went:
                dest = venue_name(went[0]["key"])
                if went[0]["krw"] == 0 and went[0]["key"] != "meal_other":
                    dest += " (포함 끼니)"
            else:
                dest = "안 먹음 · 다른 끼니"
            out[(venue_name(intended), dest)] += 1
    return out, len(who_seen)


def print_matrix(mat, n_who, date=None):
    rows = sorted({a for a, _ in mat}, key=lambda a: -sum(v for (x, _), v in mat.items() if x == a))
    cols = sorted({b for _, b in mat}, key=lambda b: -sum(v for (_, y), v in mat.items() if y == b))
    print(f"\n  붐빌 때 어디로 가나 — 자리가 없어 돌려보내진 끼니 {sum(mat.values())} 건 (손님 {n_who} 팀 · 그 끼니 창에 있던 손님만) · 원래 가려던 곳 → 간 곳")
    print("  " + f"{'원래 →':12s}" + "".join(f"{c[:9]:>11s}" for c in cols) + f"{'합':>6s}")
    for a in rows:
        tot = sum(v for (x, _), v in mat.items() if x == a)
        print("  " + f"{a:12s}" + "".join(f"{mat.get((a, c), 0):>11d}" for c in cols) + f"{tot:>6d}")
    return rows, cols


def write_csv(mat, date, path=HERE / "reroute.csv", append=False):
    mode = "a" if append and path.exists() else "w"
    with path.open(mode, newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if mode == "w":
            w.writerow(["날짜", "원래 가려던 곳", "간 곳", "팀 수"])
        for (a, b), v in sorted(mat.items(), key=lambda kv: -kv[1]):
            w.writerow([date, a, b, v])
