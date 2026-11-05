"""
blog44 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog44.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 44
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 14, 13, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 빛의 시어터 (그랜드워커힐 서울 B1) 전시 관람 목적 방문, 투숙 언급 없음",
    "nights": "◎ 주말에 전시 보러 나옴 — 비투숙",
    "party": "○ 본인과 아이 둘로 보임 (음료 두 잔 주문, 다른 동행 언급 없음)",
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
    name='[자동] blog44 · 비투숙 · 빛의 시어터 전시 관람 · 아이 동반',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
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
    "GRAND_LOBBY": "◎ '마지막엔 1층 워커힐 로비에 가서' 피아노 트리오 클래식 공연 관람"
}
TRUTH_PASSED: dict[str, str] = {
    "THEATRE_ART_SHOP": "전시장 나오면 이어지는 아트샵 '구경도 쏠쏠' — 구매 언급 없음",
    "LE_PASSAGE": "로비에서 '르 파사쥬 베이커리 카페 케이크도 구경' — 구경만",
    "THE_PAVILION": "○ '호텔 로비 앞 카페에서 커피 한잔 하며 … 보내도 참 좋겠더라' — 추천만, 이용 안 함"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_ROOM": "○ 언급 없음 (비투숙)",
    "PIZZA_HILL": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음 (발렛 요금 안내만, 직접 주차)"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "빛의 라운지 카페": "◎ 전시 후 '빛의 라운지 카페에 들러 커피 한잔' — 아인슈페너·딸기라떼 주문",
    "주차타워(층 미상)": "◎ '주차 타워에 주차 후 엘리베이터' — 어느 층인지 적히지 않아 코드 지정 보류"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('THEATRE_OF_LIGHT', 'GRAND_LOBBY', "◎ 전시·카페 후 '마지막엔 1층 워커힐 로비에 가서'")]
TRUTH_MEALS: list[tuple[str, str, str]] = []
