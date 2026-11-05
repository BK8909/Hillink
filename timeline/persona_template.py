"""
persona_blog0N.py 양식 — 이 파일을 복사해서 채운다. 다 채우면 `python3 run_all.py` 가 알아서 돈다.

원칙
  - 성향 값 하나마다 근거 문장 요약을 붙인다. 근거가 없으면 None (미상). 미상은 0 이 아니다.
  - 동행자·아동 식별 정보는 넣지 않는다 (13세 미만 동반 여부 · 인원 수 · 박 수만).
  - 후기 원문·URL 은 저장소 밖. 여기엔 근거 요약만.
  - 정답은 "후기가 이용을 못 박은 곳" 만. 구경만 한 곳은 TRUTH_PASSED 로.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

# ── 후기 시작 시각 — 후기에 있으면 그 값, 없으면 체크인 15:00 근처로 (△ 표시) ──────────
START_AT = datetime(2025, 1, 1, 14, 30)      # △

# ── 사실 — 성향이 아니라 예약 시점에 정해진 것 ───────────────────────────────────
FACTS = {
    "숙박":      ("1박 · 그랜드 / 비스타 / 더글라스 중 하나", "◎"),
    "인원":      ("성인 2", "◎"),
    "아동":      ("13세 미만 동반 여부", "◎"),
    "교통":      ("자차 발렛 / 셔틀 / 택시", "◎"),
    "포함 식사": ("패키지에 포함된 끼니가 있으면 (끼니, 업장)", "◎"),
    "클럽":      ("클럽 객실이면 클럽라운지 자격", "◎"),
}

# ── 성향 7개 — (값 또는 None, 근거 요약) ─────────────────────────────────────────
TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    "대기 회피":     (None, "근거 없음 → 미상"),
    "이동 최소화":   (None, ""),
    "격식 선호":     (None, ""),
    "조망 중시":     (None, ""),
    "새로움 추구":   (None, ""),
    "함께 먹기 선호": (None, ""),
    "조용함 선호":   (None, ""),
}

PERSONA = Persona(
    name="blog0N · 한 줄 요약",
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    # 사실 항목
    property="GRAND",            # "GRAND" · "VISTA" · "DOUGLAS"
    is_guest=True,               # 비투숙 방문이면 False
    club_access=False,           # 클럽 객실이면 True
    depart_by=time(20, 0),       # 비투숙일 때 떠난 시각
    included_meals=(),           # 예: (("조식", "THE_BUFFET"),)
    booked=(),                   # 미리 끊은 시설 입장권. 예: ("RIVERPARK",) — 비투숙 리버파크 방문
    room_minimal=False,          # 후기가 "방에 있을 시간 없다" 같은 말을 했으면 True
    note="근거 붙여 뽑음. 미상 N개",
)

# ── 정답 1 · 이용이 확정된 곳 (검증기 장소 코드로) ──────────────────────────────
TRUTH_VISITED: dict[str, str] = {
    "GRAND_LOBBY": "◎ 체크인",
    "GRAND_ROOM":  "◎",
    # "PIZZA_HILL": "◎ 저녁",
}
# 지나갔거나 구경만 한 곳 — 채점에서 뺀다
TRUTH_PASSED: dict[str, str] = {}
# 후기가 안 갔다고 못 박은 곳 — 에이전트가 가면 표시
TRUTH_NOT_VISITED: dict[str, str] = {}
# 이용은 확정인데 검증기·에이전트에 없는 곳
TRUTH_UNREACHABLE: dict[str, str] = {}

# 식당 집합 (헤드라인 지표) — 후기가 이용한 식당만
TRUTH_RESTAURANTS: frozenset[str] = frozenset({})

# ── 정답 2 · 순서가 확정되는 쌍만 (먼저, 나중, 근거) ─────────────────────────────
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [
    # ("GRAND_LOBBY", "GRAND_ROOM", "◎ 체크인 뒤 객실"),
]

# ── 끼니 — 후기에 적힌 호텔 내 식사 (끼니, 업장, 근거) ────────────────────────────
TRUTH_MEALS: list[tuple[str, str, str]] = [
    # ("조식", "THE_BUFFET", "◎ 패키지"),
]


def print_persona() -> None:
    print(f"페르소나  {PERSONA.name}")
    for k, (v, why) in TRAIT_EVIDENCE.items():
        print(f"  {k:8s} {'미상' if v is None else f'{v:.1f}':4s}  {why}")


if __name__ == "__main__":
    print_persona()
