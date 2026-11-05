"""
blog44 — 한호 정답 확인
정답 확인: 한호 · 9/29 · 보류 없음 (정확한 인원·주차 층·방문 시각은 원문상 미상)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
9/28 자동 초안을 원문 r048과 대조했다. 성향(TRAIT_EVIDENCE)은 자동 초안 그대로 두었다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 14, 13, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 빛의 시어터 (그랜드워커힐 서울 B1) 전시 관람 목적 방문, 투숙 언급 없음",
    "nights": "◎ 주말에 전시 보러 나옴 — 비투숙",
    "party": "△ 본인과 아이 1명은 확인되나 다른 동행이 없었다는 문장은 없음 (최소 2명)",
    "child": "◎ 아이와 함께 관람, 키즈 케어존 전시",
    "included_meals": "해당 없음 (비투숙)",
    "booked": "○ 사전 예매했다는 문장 없음 → 비움",
    "arrival": "◎ '주차 타워에 주차 후, 엘리베이터를 이용해서 빛의 시어터 쪽으로 이동' — 발렛 언급 없음",
    "room_minimal": "해당 없음 (비투숙)",
    "start_time": "△ 방문 시각 없음 — 주말 오후 관람 가정, 이용 시작 30분 전",
    "depart_by": "△ 60분 전시 + 포토타임 + 아트샵 + 카페 + 로비 공연까지 이용 끝 무렵으로 추정"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.5, "○ 전시 후 카페에서 '한강 뷰를 바라보는 재미' 가 있다고 적음 — 좋았다 수준, 고른 이유로는 안 씀"),
    '새로움 추구': (None, "근거 없음 → 미상 (시그니처 메뉴는 '도전해보고 싶었지만' 다른 메뉴 선택)"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[확인 초안] blog44 · 비투숙 · 빛의 시어터 전시 관람 · 아이 동반',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,  # △ 확인 가능한 최소 인원; 정확한 인원 미상
    has_child_under_13=True,
    nights=0,
    property='GRAND',
    is_guest=False,
    club_access=False,
    depart_by=time(16, 30),
    included_meals=(),
    booked=(),
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 6개",
)

TRUTH_VISITED: dict[str, str] = {
    "THEATRE_OF_LIGHT": "◎ 클림트 : 골드 인 모션 전시 관람, 포토존 촬영, 누워서 관람",
    "THEATRE_ART_SHOP": "○ 전시장을 나와 아트샵 진열품을 직접 구경하고 소감을 적음",
    "LE_PASSAGE": "○ 로비에 가서 베이커리 케이크를 직접 구경함 (구매·식사 아님)",
    "GRAND_LOBBY": "◎ '마지막엔 1층 워커힐 로비에 가서' 피아노 트리오 클래식 공연 관람"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_ROOM": "○ 언급 없음 (비투숙)",
    "PIZZA_HILL": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음 (발렛 요금 안내만, 직접 주차)"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "그랜드 층 미상 빛의 라운지 카페": "◎ 전시 후 카페에 들러 음료를 주문하고 마심. 정확한 층은 원문에 없음",
    "그랜드 주차타워 층 미상": "◎ 주차타워에 직접 주차 후 엘리베이터 이동. 주차 층 미상"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('THEATRE_OF_LIGHT', 'THEATRE_ART_SHOP', '◎ 전시장을 나와 이어지는 아트샵 구경'), ('THEATRE_ART_SHOP', 'GRAND_LOBBY', '◎ 아트샵·카페 뒤 마지막에 로비에서 공연 관람')]
TRUTH_MEALS: list[tuple[str, str, str]] = []

