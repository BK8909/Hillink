"""
blog09 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 → (OCR) 텍스트 → LLM(손 페르소나를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2026-09-24 — 에이전트 v3 실행 전에 정답 확정. 사람이 정답만 원문과 대조 (성향은 손대지 않음)
손으로 만든 persona_blog09.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 9
시험용(held-out) 후기 — run_all.py 가 읽는다. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2023, 8, 26, 10, 30)      # △ [봉인 확인] 게시 직전 주말 · 끼니 미상 → 중식 회차 30분 전 (추출 규칙대로)

FACTS_EVIDENCE = {
    "property": "△ 건물명이 직접 언급되지 않음. '1층 로비로 들어와 2층으로 올라간다'는 위치 설명을 근거로 더뷔페가 있는 비스타 건물로 추정",
    "nights": "◎ 숙박 없이 '워커힐 더뷔페에 다녀왔습니다'라고만 밝혀 식당만 이용한 비투숙 방문",
    "party": "△ '가족 중 기념일가 있어 겸사겸사' 방문했다고만 밝혀 정확한 인원 수는 나오지 않음, 가족 단위 최소 인원으로 추정",
    "included_meals": "◎ 패키지에 포함된 식사 언급 없음, 네이버예약 10% 할인을 받아 유료로 이용한 식당 방문",
    "room_minimal": "◎ 비투숙 방문이라 객실 해당 사항 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.7, "◎ '초반에 그릴류에 사람이 많이 몰리는데요... 저는 시간이 지나고 먹는 게 더 좋았어요'라며 초반 줄을 피해 시간이 지난 뒤 이용하는 것을 스스로 선호한다고 밝힘"),
    '이동 최소화': (None, '근거 없음 → 미상 (자차 이용 추천 등은 독자에게 주는 일반 안내일 뿐 본인의 이동 회피 선호를 드러내지 않음)'),
    '격식 선호': (None, '근거 없음 → 미상 (분위기가 깔끔하다는 서술은 있으나 정찬·캐주얼 중 무엇을 선호하는지는 드러나지 않음)'),
    '조망 중시': (None, '근거 없음 → 미상 (뷰 관련 언급 자체가 없음)'),
    '새로움 추구': (0.7, "◎ '호텔뷔페 도장 깨기를 해볼까 생각'하고 있으며 '다음번에는 조선웨스턴호텔 아리아를 한번 가보고 싶습니다'라고 밝혀 새로운 곳을 시도하려는 선호가 드러남"),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (동행자와 함께 먹는 것에 대한 별도의 서술이 없음)'),
    '조용함 선호': (0.8, "◎ 이전에 방문한 곳은 '사람도 너무 많고... 와글와글' 했다고 비교하며 워커힐은 '비교적 여유롭게 즐길 수 있는 분위기', '비좁게 인원을 꽉 채워 받는 편이 아니라서 여유 있게 즐기고 올 수 있어서 더욱 좋았다'고 밝혀 한적함을 이유로 만족감을 표현함"),
}

PERSONA = Persona(
    name='[자동] blog09 · 워커힐 더뷔페 비투숙 · 가족 기념일 방문',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=0,
    property='VISTA',
    is_guest=False,
    club_access=False,
    depart_by=time(13, 30),
    included_meals=(),
    room_minimal=False,
    note="자동 추출 · 미상 4개",
    arrival="car_self",   # ○ 주차타워 · 셀프 정산 서술 (v4 사실 항목, 9/24 시험 뒤 추가)
    booked=("THE_BUFFET",),   # ◎ 네이버 예약으로 할인받아 방문 — 방문 목적 (v4 사실 항목, 9/24 시험 뒤 추가)
)

TRUTH_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 워커힐 더뷔페를 방문해 스테이크, 양갈비, 대게, 초밥·회, 냉면, 과일·케이크 등 디저트를 직접 먹었다고 서술"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('중식', 'THE_BUFFET', '△ 방문 시각이 명시되지 않아 주말 가족 방문 정황상 점심 식사로 추정')]
