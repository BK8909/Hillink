"""
blog21 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용
손으로 만든 persona_blog21.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 21
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 30)      # △ 후기에 날짜·시각 없음

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 투숙, 투숙 카드로 라이브러리 입장",
    "nights": "◎ 다음날 아침 집으로 돌아이 아이 등원",
    "party": "○ 작성자·동행자 1명·아이, '애들' 복수 표현으로 아이 2명 추정",
    "included_meals": "◎ 조식 포함 언급 없음, 조식 뷔페는 먹을 예정이었다가 취소",
    "arrival": "○ 집에서 20분 거리를 오감(자차로 보이나 발렛/직접 주차 언급 없음)",
    "room_minimal": "○ 객실 묘사는 없으나 잠만 잤다는 문장도 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (0.5, '○ 집에서 가까워 오가며 힘 안 빼서 좋다고 함, 호텔 안에서는 차를 불러 언덕 위 피자힐까지 감 → 보통'),
    '격식 선호': (None, '근거 없음 → 미상 (피자힐 선택 이유는 격식이 아니라 다음날 일정)'),
    '조망 중시': (None, '근거 없음 → 미상 (돌아오는 길 한강뷰 잠깐 봤다는 정도)'),
    '새로움 추구': (0.5, '◎ 익숙해진 시설이라 자주 찾고 좋아하는 라이브러리를 재방문, 동시에 피자힐은 처음 가 보기로 함 → 섞임'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (0.5, '◎ 라이브러리의 고요함이 정말 좋다고 하나, 사람이 많아 목욕탕 같던 유아 수영장도 즐거웠다고 함 → 섞임'),
}

PERSONA = Persona(
    name='[자동] blog21 · 그랜드 1박 · 기념일 · 아이 동반 가족',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=True,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "○ 도착해 체크인",
    "GRAND_POOL": "◎ 체크인 후 바로 수영장에서 물놀이",
    "GRAND_LOBBY": "◎ 로비에서 사진, 로비에서 차량 불러 피자힐 이동",
    "GRAND_LIBRARY": "◎ 라이브러리에서 아이와 책 읽고 과제",
    "PIZZA_HILL": "◎ 차 타고 피자힐 가서 피자·파스타·맥주 식사",
    "GRAND_ROOM": "○ 1박 투숙, 아이들이 자는 동안 새벽에 헬스하러 나감",
    "FITNESS": "◎ 새벽 6시 헬스장에서 운동, 운동화 대여",
    "WELLNESS_SAUNA": "◎ 현장 추가 결제 후 사우나 이용, 냉탕·온탕"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 조식 뷔페 예정이었으나 다음날 일정이 빡빡하다는 조언에 취소",
    "ONDAL": "○ 멤버십 할인 대상으로 언급만",
    "GEUMRYONG": "○ 멤버십 할인 대상으로 언급만",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_FRONT_DESK', 'GRAND_POOL', '◎ 체크인을 하고 바로 수영장으로'), ('GRAND_POOL', 'GRAND_LOBBY', '○ 수영 후 로비에서 한 컷'), ('GRAND_POOL', 'GRAND_LIBRARY', '◎ 수영장 다음은 라이브러리'), ('GRAND_LIBRARY', 'PIZZA_HILL', '○ 라이브러리 다음 피자힐 (번호 순서)'), ('PIZZA_HILL', 'FITNESS', '◎ 저녁 피자힐, 다음날 새벽 6시 헬스'), ('FITNESS', 'WELLNESS_SAUNA', '◎ 헬스 후 사우나 루틴')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '◎ 피자힐에서 콰트로 피자·토마토 파스타·맥주')]
