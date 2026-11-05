"""
blog17 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(성향 눈금 · 방문 근거 검사). 정답 확인 1차 — 개발용
손으로 만든 persona_blog17.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 17
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 30)      # △ 후기에 날짜·시각 없음

FACTS_EVIDENCE = {
    "property": "◎ 그랜드워커힐 더글라스 호캉스, 더글라스 하우스 객실 투숙",
    "nights": "◎ 다음날 라이트 조식 후 체크아웃",
    "party": "○ '둘 다 술을 마시진 않지만' — 본인 + 동행자 1",
    "included_meals": "◎ 더글라스(조식) 포함으로 예약 · 더글라스 투숙은 라운지 포함 규칙 적용",
    "room_minimal": "○ 객실에서 라면 끓여 먹고 9시부터 푹 잠 — 객실 최소 아님",
    "arrival": "◎ 자차 이동, 발렛 1회 무료지만 직접 주차타워에 주차"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상 (창가 자리 못 잡았지만 대기·포기 문장 없음)'),
    '이동 최소화': (0.25, "◎ 발렛 무료인데 '시간도 많은데' 직접 주차, 도보 5분 거리도 괜히 차 타 보고 싶어 차량 이용, 체크아웃 후 차량 대신 일부러 숲쪽으로 걸어 내려감"),
    '격식 선호': (None, '근거 없음 → 미상 (본관 조식 추가를 안 한 이유는 부지런하지 못해서)'),
    '조망 중시': (0.5, "◎ 라운지 창가 자리는 못 잡았지만 '전체적인 뷰가 좋아서 매우 행복' — 좋았다 수준"),
    '새로움 추구': (0.5, '○ 괜히 차 한번 타 보고, 와인 한번 마셔 보고, 조식도 먹어 보고 싶어 일어남 — 포함 혜택을 맛보는 정도, 본관 뷔페 추가는 패스'),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (숲 속 같은 객실 묘사뿐)'),
}

PERSONA = Persona(
    name='[자동] blog17 · 더글라스 1박 · 2인 (기념일)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='DOUGLAS',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('조식', 'DOUGLAS_LOUNGE'), ('석식', 'DOUGLAS_LOUNGE')),
    booked=(),
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 4개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "○ 3시쯤 본관에서 체크인 완료 후 더글라스로 이동",
    "DOUGLAS_ROOM": "◎ 더글라스 하우스 객실 투숙, 9시부터 잠",
    "DOUGLAS_LOUNGE": "◎ 라이트 스낵 · 더글라스 아워(핫윙·핫도그·맥주) · 라이트 조식 이용",
    "DOUGLAS_LOBBY": "◎ 체크아웃 전 아쉬워서 로비를 들락날락"
}
TRUTH_PASSED: dict[str, str] = {
    "GRAND_LOBBY": "○ 본관 체크인 후 더글라스행 차량 타러 지나감",
    "FOREST_PARK": "더글라스-본관 사이에 있다고 소개·추천만, 이용 문장 없음",
    "CU_THEATRE": "편의점 운영시간 안내만",
    "GWANGNARU_STN": "지하철 이용 시 도보 거리 안내만"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "THE_BUFFET": "◎ 더글라스 조식 포함이라 본관 뷔페는 패스, 아침에 추가도 안 함",
    "VALET_DESK": "◎ 발렛 무료 1회지만 직접 주차",
    "GRAND_ROOM": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "주차타워 지하2층": "◎ 자리가 없어 돌다가 지하2층에 주차"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_FRONT_DESK', 'DOUGLAS_ROOM', '◎ 본관 체크인 완료 후 차량으로 더글라스 하우스 도착'), ('DOUGLAS_ROOM', 'DOUGLAS_LOUNGE', '○ 체크인 후 라이트 스낵, 이후 객실에서 라면')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'DOUGLAS_LOUNGE', '◎ 체크인 후 라이트 스낵(쿠키·음료)'), ('석식', 'DOUGLAS_LOUNGE', '◎ 더글라스 아워에 핫윙·핫도그·핑거푸드와 맥주'), ('조식', 'DOUGLAS_LOUNGE', '◎ 다음날 라이트 조식')]
