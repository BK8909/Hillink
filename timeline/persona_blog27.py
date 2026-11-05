"""
정답 확인: 경수 · 보류: facts.party_size — '저희' 뿐, 인원 없음 · 석식 — '저녁을 먹은 뒤' 장소 없음

blog27 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog27.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 27
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 8, 31, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 서울 한강뷰 객실 투숙",
    "nights": "◎ 1박 2일",
    "party": "○ '저희'로 서술, 인원·아이 동반 명시 없음 → 2인 추정",
    "included_meals": "○ 포함 끼니 언급 없음",
    "room_minimal": "◎ 객실에서 조금 쉬다가 수영장, 객실·한강뷰 만족 서술",
    "arrival": "○ 자차로 와서 체크아웃 후 차를 호텔에 둠 — 발렛/직접 주차 여부 미기재 → null",
    "booked": "◎ 로비 베이커리에 샤인머스켓 요거트 케이크를 미리 주문"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상 (체크아웃 후 계획 변경은 주차 걱정 때문)'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.75, "○ '무엇보다 한강이 훤히 내려다보이는 뷰맛집' · 객실에서 제일 좋았던 건 한강뷰, 밤 야경 보러 족욕"),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='blog27 · 비스타 1박 · 2인 추정 (체크아웃 후 서울 나들이)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('LE_PASSAGE',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 6개",
)

TRUTH_VISITED: dict[str, str] = {
    "LE_PASSAGE": "○ 로비 베이커리에서 미리 주문한 케이크를 받아 먹음 ('맛났어요')",
    "VISTA_ROOM": "◎ 체크인 후 객실, 전동커튼 한강뷰",
    "VISTA_POOL": "◎ 객실에서 쉬다가 투숙객 무료 실내수영장 이용, 야외 공간에서 사진",
    "SKYARD": "◎ 수영·저녁 후 야경 보며 족욕",
    "VISTA_FITNESS": "◎ 다음 날 헬스장 운동 (운동복 대여) + 밖 야외 트랙 걷기 — 9/29 소연: 비스타 노드 신설로 목록 밖에서 옮김",
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_LOBBY": "○ 로비로 가는 길에 카지노 구경",
    "VISTA_LOBBY": "○ '체크인을 하고' 한 줄 — 비스타 프런트는 코드가 없어 로비로 (규칙 ①)",
    "GANGBYEON_STN": "◎ 체크아웃 후 호텔 셔틀로 강변역 → 성수동 (blog02 광나루역과 같이 지나감)"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "RIVERPARK": "○ 언급만 — 실외수영장은 별도 유료라고만 적고 이용 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('LE_PASSAGE', 'VISTA_ROOM', "○ 로비 베이커리 케이크 서술 뒤 '체크인을 하고 객실로 올라갔어요'"), ('VISTA_ROOM', 'VISTA_POOL', '◎ 객실에서 조금 쉬다가 실내수영장'), ('VISTA_POOL', 'SKYARD', '◎ 수영을 하고 저녁을 먹은 뒤 족욕'), ('SKYARD', 'VISTA_FITNESS', '◎ 족욕은 첫날 밤, 헬스장은 다음 날 — 9/29 소연: 초안의 쌍. 피트니스가 목록 밖이라 빠졌던 것을 되살림')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'LE_PASSAGE', '○ 미리 주문한 케이크를 먹음')]
