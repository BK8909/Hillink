"""
blog14 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 텍스트 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2 — v4 계수 확정(fit_v4_result.json) 뒤에 만든 후기. 사람은 정답만 원문과 대조
손으로 만든 persona_blog14.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 14
시험용(held-out) 후기 2 — v4 계수 확정 뒤 봉인. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 8, 2, 13, 30)      # △ [봉인 확인] 게시 직전 토요일 · 시각 미상 → 추출 규칙대로 추정

FACTS_EVIDENCE = {
    "property": "△ [봉인 확인] 비투숙 — 빛의 시어터가 그랜드 쪽, 로비 왼쪽 체크인 · 오른쪽 시어터 서술",
    "nights": "◎ 숙박 관련 서술 없이 당일 전시·라운지 이용만 서술됨 → 0박",
    "party": "○ '서울에서 특별한 커플 실내 데이트 장소 고민하다가 찾게 된 곳'이라는 서술로 커플(2인) 방문으로 추정",
    "included_meals": "◎ 요금·할인 정보만 있고 숙박 패키지에 포함된 식사 언급 없음",
    "room_minimal": "◎ 비투숙으로 객실 이용 서술 자체가 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.8, "○ 미리 구매한 표를 QR로 찍고 '바로 입장 완료'라고 서술 — 사전 예약으로 대기를 피한 것으로 추론"),
    '이동 최소화': (0.8, "◎ '주차나 접근성도 좋아서 망설임 없이 선택했습니다' — 접근성(동선)이 선택 이유"),
    '격식 선호': (None, '근거 없음 → 미상 (식사 관련 서술이 커피 한 잔 외에 없음)'),
    '조망 중시': (0.5, "◎ '라운지 창밖으로 보이는 서울 전경도 멋지고' — 좋았다는 언급은 있으나 선택 기준이었다는 서술은 없음"),
    '새로움 추구': (0.2, "◎ '또 가보고 싶어요', '두번 봐도 좋아요' 등 재방문 의사를 밝히고 전시 한 곳(빛의 시어터)만 집중 이용"),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (커피를 누구와 함께 마셨는지 서술 없음)'),
    '조용함 선호': (None, '근거 없음 → 미상 (셔틀 혼잡 서술은 있으나 전시·라운지 자체의 혼잡/한적함에 대한 호불호 서술 없음)'),
}

PERSONA = Persona(
    name='[자동] blog14 · 빛의 시어터 데이트 · 비투숙',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=0,
    property='GRAND',
    is_guest=False,
    club_access=False,
    depart_by=time(16, 30),
    included_meals=(),
    booked=('THEATRE_OF_LIGHT',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "THEATRE_OF_LIGHT": "◎ 미리 구매한 표를 지류로 교환·QR 입장 후 36분 몰입형 전시 및 체험존 관람",
    "GANGBYEON_STN": "◎ 강변역 1번 출구에서 구체적 경로(횡단보도 두 번)로 워커힐 셔틀 탑승"
}
TRUTH_PASSED: dict[str, str] = {
    "THEATRE_ART_SHOP": "○ '아트샵 이용고객은 10% 할인'이라는 정보만 있고 실제 방문 서술은 없음",
    "GWANGNARU_STN": "○ 광나루역에서도 셔틀 탑승 가능하다는 안내만 있고 실제 탑승은 강변역으로 서술됨",
    "VALET_DESK": "○ '발렛파킹은 호텔 발렛서비스 카드가 있으면 무료'라는 요금 안내만 있고 본인이 이용했다는 서술은 없음",
    "GRAND_LOBBY": "◎ 로비로 들어가 오른쪽으로 — 통과"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음",
    "HOTEL_GATE": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음",
    "PARKING_TOWER_B1": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "빛의 시어터 라운지": "◎ 전시 관람 후 바로 옆 라운지에서 커피 한 잔, 창밖 서울 전경을 봄 — 장소 코드 목록에 없음"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GANGBYEON_STN', 'THEATRE_OF_LIGHT', '◎ 강변역에서 셔틀 탑승 후 빛의 시어터 입장')]
TRUTH_MEALS: list[tuple[str, str, str]] = []
