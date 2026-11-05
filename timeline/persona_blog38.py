"""
blog38 — 정답 확인본 (소연). 자동 추출 초안 persona_blog38_auto.py 를 원문 r057 과 대조했다.

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는
별도 에이전트) → JSON. 추출기 9/28 판. 정답 확인 2차 — 개발용

정답 확인: 소연 · 12분 · 보류 3건

정답(TRUTH)은 고칠 게 없었다. 더뷔페 한 곳이고 전날 디너와 다음 날 조식 모두 같은 뷔페다
("어제 디너에 대게가 있었던 곳에 딤섬이 있구요"). 대신 **사실 쪽이 전부 추정**이라 보류로 바꿨다.

보류: facts.property — 숙박 건물이 원문에 없다. 초안은 "더뷔페가 비스타 워커힐 1층이라 비스타로 추정" 이라
      했는데, 더뷔페는 그랜드 투숙객도 조식으로 쓴다. 이번 차수의 blog25 가 바로
      그랜드 투숙인데 비스타 1층 더뷔페에서 조식을 먹었다. 건물 추정 근거가 안 된다.
      Persona.property 는 비울 수 없어 초안 값(VISTA)을 두었지만 근거가 없다
보류: facts.is_guest · nights — "투숙 · 객실 · 체크인 · 숙박" 이라는 말이 원문에 한 번도 없다.
      전날 디너와 다음 날 조식을 같은 뷔페에서 먹었으니 투숙이 자연스럽긴 하나 적혀 있지는 않다
보류: facts.party_size — 인원이 없다. "부모님과 함께 오기에도 정말 좋은 조식" 은 추천 문장이라
      동행 근거가 아니다. 초안의 2 를 두었다

이 글은 식당 한 곳짜리 후기라 정답은 튼튼한데 사실이 약하다. 반대 모양의 후기라서,
"사실을 못 정하면 어디까지 추정할지" 기준이 있으면 좋겠다.

성향은 손대지 않았다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 1, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "△ 숙박 건물이 원문에 없다. 초안은 '더뷔페가 비스타 워커힐 1층이라 비스타로 추정' 이었지만 더뷔페는 그랜드 투숙객도 조식으로 쓴다(blog25 가 그 경우다) — 근거가 안 된다. 보류",
    "nights": "△ '전날 디너 뷔페를 거하게 먹었어도 설레이면서 잠들었던' 뿐 — 투숙 여부 · 박 수가 원문에 없다. 보류",
    "party": "△ 인원 명시 없음 → 2인 추정, 아이 동반 언급 없음",
    "included_meals": "○ 조식·디너 포함 여부 명시 없음",
    "room_minimal": "△ 객실 언급 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (뷔페만 이용, 코스·캐주얼을 고른 문장 없음)'),
    '조망 중시': (0.5, "◎ '한강뷰와 숲뷰를 보며 여유롭게 아침' — 좋았다 정도"),
    '새로움 추구': (0.25, "○ '호텔 조식 뷔페 중 좋아하는 곳이 워커힐 더뷔페', '다시 방문하고 싶은 조식, 단연 더뷔페' — 익숙한 한 곳을 반복 선호, 디너·조식 모두 더뷔페"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='blog38 · 더뷔페 디너+조식 · 투숙 추정 · 조식 재방문 선호',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="정답 확인본(소연) · 성향은 자동 추출 그대로 · 사실 3개 보류",
)

TRUTH_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 전날 디너 뷔페를 먹고 다음날 더뷔페 조식을 여러 접시 먹음"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "VISTA_POOL": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = []
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'THE_BUFFET', "◎ '전날 디너 뷔페를 거하게 먹었어도', '어제 디너에 대게가 있었던 곳' — 같은 더뷔페 디너"), ('조식', 'THE_BUFFET', '◎ 더뷔페 조식을 샐러드·스프·볶음밥 등으로 먹음')]
