"""
blog50 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 시험용
손으로 만든 persona_blog50.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 50
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 2, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 이번에 이용한 객실은 그랜드 호텔, 그랜드 클럽 스위트룸",
    "nights": "○ 회원권 혜택 중 클럽스위트 1박 숙박권 이용",
    "party": "△ 이 체류에서 동행 언급 없음 → 호캉스 2인 추정",
    "included_meals": "◎ 클럽스위트 이용 시 라운지 티타임 · 해피아워 · 조식이 다 포함 (해피아워는 저녁 대신, 조식은 비스타에서 이용)",
    "room_minimal": "◎ 거실·침실 미닫이 문, 욕조, 냉장고 간식 등 객실을 충분히 즐김",
    "arrival": "○ 주차 자리 많고 지하로 건물과 연결되어 비 맞을 일 없다고 적음 → 자차 직접 주차 추정"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.25, "○ 그랜드 투숙인데 '비스타 쪽 조식이 더 다양해서' 일부러 비스타로 가서 조식 이용"),
    '격식 선호': (None, '근거 없음 → 미상 (해피아워로 저녁을 대신한 건 시간 때문이라고 적음)'),
    '조망 중시': (0.75, '◎ 객실을 한강뷰로 선택했다고 적고, 가을엔 단풍 보러 아차산뷰로 다시 오고 싶다고 함'),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (쉼이 목적이라 헬스장 안 감 — 조용함 이유는 아님)'),
}

PERSONA = Persona(
    name='[자동] blog50 · 그랜드 클럽 스위트 1박 (회원권 숙박권) — 본문 첫 체류 기준 (피자힐 편 별도 체류·더파빌리온 편 과거 방문은 제외)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('조식', 'THE_BUFFET'), ('석식', 'GRAND_CLUB_LOUNGE'), ('간식', 'GRAND_CLUB_LOUNGE')),
    booked=(),
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 5개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_ROOM": "◎ 그랜드 클럽 스위트룸에 숙박, 거실·침실을 열고 닫으며 이용",
    "GRAND_CLUB_LOUNGE": "◎ 16층 라운지에서 티타임 후 해피아워(17:30-19:30)를 저녁 대신 이용",
    "THE_BUFFET": "○ '조식은 비스타에서 이용했어요' · 해시태그 더뷔페 → 비스타 조식 식당"
}
TRUTH_PASSED: dict[str, str] = {
    "SKYARD": "스위트 투숙객은 이용 가능하다는 소개·족욕 안내뿐, 이번 이용은 불명확",
    "FOREST_PARK": "좋아하는 장소로 소개·셔틀 안내만, 이번 체류 이용은 적지 않음",
    "GRAND_LIBRARY": "객실 키로 2층 도서관 이용 가능하다는 안내만",
    "PARKING_TOWER_B1": "○ 지하로 건물과 연결된 주차장 언급 — 주차 후 통과 추정"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_POOL": "◎ 물놀이를 좋아하지 않아 수영장은 이용하지 않음",
    "VISTA_POOL": "◎ 수영장은 이용하지 않음",
    "RIVERPARK": "◎ 실내·실외 수영장 모두 이용하지 않음",
    "FITNESS": "◎ 쉼이 목적이라 헬스장도 이용하지 않음",
    "PIZZA_HILL": "○ 언급 없음 (이 체류 기준)",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음 (이 체류 기준)",
    "LUX_BAR": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "산책로(아차산)": "○ 조식 먹고 항상 산책한다고 적음 — 장소 코드 목록에 없음"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_ROOM', 'GRAND_CLUB_LOUNGE', '○ 체크인 후 라운지 티타임 → 해피아워'), ('GRAND_CLUB_LOUNGE', 'THE_BUFFET', '○ 첫날 라운지, 다음 날 아침 비스타 조식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'GRAND_CLUB_LOUNGE', '◎ 라운지 티타임에서 커피·차·디저트'), ('석식', 'GRAND_CLUB_LOUNGE', '◎ 해피아워를 저녁 대신 이용, 따로 밥 사 먹을 시간이 없었음'), ('조식', 'THE_BUFFET', '○ 비스타에서 조식 이용')]
