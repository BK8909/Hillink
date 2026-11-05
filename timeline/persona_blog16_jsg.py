"""
정답 확인: 슬기 · 9/28 · 15분 · 보류 없음

blog16 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 정답 확인 1차(9/24~) — 개발용
손으로 만든 persona_blog16.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 16
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 20)      # ◎ 14:20쯤 비스타워커힐 로비 도착

FACTS_EVIDENCE = {
    "property": "◎ 비스타 워커힐 11층 디럭스 트윈 리버뷰 투숙",
    "nights": "◎ 금요일 체크인 · 다음날 체크아웃",
    "party": "◎ '우리' 둘이 투숙 · 동행자 1명 · 아이 언급 없음",
    "included_meals": "◎ 조식은 투숙객 할인가로 따로 결제 → 포함 아님",
    "booked": "◎ 다음날 조식 1부(06:30~08:10)를 동행자가 예약",
    "arrival": "도착 수단 언급 없음 → null",
    "room_minimal": "○ 객실 미니바·커피머신·블루투스 스피커를 즐김 → 객실 체류 있음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.5, '◎ 체크인 대기줄 44팀을 보고 웃어넘기며 담담히 기다림 · 조식은 예약으로 해결'),
    '이동 최소화': (0.4, '◎ 언덕 15분 거리 피자힐을 셔틀로 일부러 찾아감 · 그랜드 쪽 뷔페·라이브러리까지 이동 · 셔틀은 편의로 이용'),
    '격식 선호': (0.35, '◎ 식사는 피자힐 피자(small)와 뷔페 조식 · 코스·정찬 선택 없음'),
    '조망 중시': (0.65, "◎ 리버뷰 객실에 크게 기뻐함 · 피자힐은 '맛은 뷰값' · 롯데타워 보며 수영 · 창가 소파 즐김 (뷰로 고른 흔적은 없음)"),
    '새로움 추구': (0.85, "◎ '부대시설 다 즐겼다' · '즐기려면 누워서 TV 볼 시간이 없다' · 피트니스·수영장·족욕·피자힐·라이브러리 두루 이용 · 피자힐은 궁금해서 감"),
    '함께 먹기 선호': (0.6, '○ 동행자와 피자·조식을 함께 먹고 미니바 맥주도 저녁과 함께 한잔씩'),
    '조용함 선호': (None, '수영장이 여유로웠다는 공간 묘사뿐 · 한적함 때문에 고른 행동 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog16 · 비스타 1박 · 2인 · 부대시설 두루 이용',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('THE_BUFFET',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 1개",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_LOBBY": "◎ 14:20쯤 로비 도착 · 체크인 · 로비 키오스크로 셔틀 호출",
    "VISTA_ROOM": "◎ 11층 리버뷰 객실 투숙",
    "FITNESS": "◎ 탈의실 직원이 운동복·라커 안내 · 만족도 최고",
    "VISTA_POOL": "◎ 롯데타워 보면서 수영 · 레인 4줄 여유",
    "SKYARD": "◎ 스카이야드 족욕 추천 · 발 매끈해짐",
    "PIZZA_HILL": "◎ 셔틀로 가서 콤비네이션 small 먹음",
    "THE_BUFFET": "◎ 다음날 조식 1부 7시에 먹음 · 3그릇",
    "GRAND_LIBRARY": "○ 2층 도서관 라운지 소파에 앉아 1층 발렛 구경 (그랜드 2층 라이브러리로 추정)"
}
TRUTH_PASSED: dict[str, str] = {
    "WELLNESS_SAUNA": "지하1층 사우나 이용권 가격·탕 개수만 언급 ('시설 최고일듯') · 이용 서술 없음",
    "VALET_DESK": "라이브러리 창문으로 발렛 구경만"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "RIVERPARK": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL', 'THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VISTA_LOBBY', 'VISTA_ROOM', '◎ 로비 체크인 후 객실'), ('VISTA_ROOM', 'PIZZA_HILL', '○ 체크인 후 저녁에 셔틀로 피자힐'), ('PIZZA_HILL', 'THE_BUFFET', '◎ 전날 피자 먹고 다음날 조식'), ('VISTA_ROOM', 'THE_BUFFET', '◎ 객실에서 자고 다음날 조식'), ('VISTA_ROOM', 'SKYARD', '○ 첫날 부대시설 이용 중 족욕'), ('VISTA_ROOM', 'VISTA_POOL', '○ 첫날 부대시설 이용')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'PIZZA_HILL', '◎ 전날 저녁 피자 4.5조각 (포장 할인 언급 · 매장/포장 불확실)'), ('조식', 'THE_BUFFET', '◎ 다음날 조식 1부 7시')]
