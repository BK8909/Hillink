"""
blog10 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 → (OCR) 텍스트 → LLM(손 페르소나를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2026-09-24 — 에이전트 v3 실행 전에 정답 확정. 사람이 정답만 원문과 대조 (성향은 손대지 않음)
손으로 만든 persona_blog10.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 10
시험용(held-out) 후기 — run_all.py 가 읽는다. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 3, 15, 14, 30)      # △ [봉인 확인] '주말' 만 명시 · 날짜 미상 → 임의 토요일 14:30 (추출 규칙대로)

FACTS_EVIDENCE = {
    "property": "◎ '워커힐 더글라스 하우스 후기', 더글라스 객실 투숙",
    "nights": "◎ '1박 2일동안' 이라고 명시",
    "party": "○ 언급 없음 → 인원 미상",
    "included_meals": "◎ 더글라스 하우스 투숙 시 라운지(라이트 스낵·더글라스 아워·조식)가 숙박에 포함되는 규정에 따름",
    "room_minimal": "○ 특이한 미니멀 객실 언급 없이 일반 더글라스 객실 구성(침대·소파·테라스 등) → 근거 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.2, "◎ 셔틀 기다리는 시간이 5분 내외라서 '이용하는데 불편함은 없었어요' 라고 긍정적으로 서술"),
    '이동 최소화': (None, '근거 없음 → 미상 (셔틀·산책로 이동 안내는 시설 정보일 뿐 본인의 선택 근거가 아님)'),
    '격식 선호': (None, '근거 없음 → 미상 (정찬·캐주얼 식사 언급 없음, 라운지 스낵류만 이용)'),
    '조망 중시': (0.7, '◎ 숲 뷰 객실·도서관 창밖 뷰·한강뷰 라운지를 반복해서 강조하고, 창가 좌석 확보를 위한 도착 시간까지 안내'),
    '새로움 추구': (0.8, '◎ 같은 숙박 동안 도서관·세탁실·멀티룸 등 부대시설을 두루 둘러보고, 라운지도 스낵·해피아워·조식 세 시간대를 모두 이용'),
    '함께 먹기 선호': (None, '일행과 함께 식사했다는 서술이 없음 → 미상'),
    '조용함 선호': (0.8, "◎ '조용한 휴식', '조용한 힐링', '조용한 분위기', '프라이빗한 숲 속 라운지', 후기 요약에서도 '조용한 객실'을 첫 번째로 꼽음"),
}

PERSONA = Persona(
    name='[자동] blog10 · 더글라스 하우스 1박 · 라운지 3회 완주',
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
    room_minimal=False,
    note="자동 추출 · 미상 3개",
    arrival="car_valet",   # ◎ 그랜드 로비 무료 발렛 1회 (v4 사실 항목, 9/24 시험 뒤 추가)
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_LOBBY": "◎ 그랜드 워커힐 로비에서 투숙객이라 말하고 발렛을 부탁드림",
    "VALET_DESK": "◎ 무료 발렛 서비스를 이용, 체크아웃 시 티켓 제시 후 차량 수령",
    "DOUGLAS_LOBBY": "◎ 더글라스 하우스 로비에서 체크인 진행, 직원이 체크인 도와줌",
    "DOUGLAS_ROOM": "◎ 2층 객실에 투숙, 침대·테라스 등 상세 후기 작성",
    "DOUGLAS_LIBRARY": "◎ 1층 도서관에서 30분 정도 책을 읽으며 시간을 보냄",
    "DOUGLAS_LOUNGE": "◎ 라이트 스낵·더글라스 아워·라이트 브렉퍼스트 3회 모두 직접 이용",
    "GRAND_POOL": "◎ 더글라스 하우스 투숙 시 그랜드 워커힐 수영장을 이용해야 해서 셔틀을 자주 이용했다고 서술"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "CU_THEATRE": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_FRONT_DESK": "○ 언급 없음",
    "GRAND_LIBRARY": "○ 언급 없음",
    "GRAND_ROOM": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
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
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "VISTA_LOBBY": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_LOBBY', 'DOUGLAS_LOBBY', '○ 그랜드 로비에서 발렛을 맡긴 뒤 셔틀로 더글라스 하우스로 이동해 체크인한 것으로 추정'), ('DOUGLAS_LOBBY', 'DOUGLAS_ROOM', '◎ 로비에서 체크인 후 객실로 입실'), ('DOUGLAS_ROOM', 'DOUGLAS_LOUNGE', "○ 라이트 스낵은 '체크인 직후 가장 먼저 즐길 수 있는' 시간대라고 설명되어 객실 입실 이후 라운지 이용으로 추정")]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'DOUGLAS_LOUNGE', '◎ 라이트 스낵 시간에 커피와 디저트를 즐김'), ('석식', 'DOUGLAS_LOUNGE', '◎ 더글라스 아워(해피아워)에 와인과 핑거푸드를 즐김'), ('조식', 'DOUGLAS_LOUNGE', '◎ 라이트 브렉퍼스트 시간에 죽·소세지 등 조식을 즐김')]
