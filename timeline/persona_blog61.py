"""
정답 확인: 슬기 · 2차 · 보류 없음
blog61 — r030 정답 확인. 시험용이므로 에이전트 실행 금지.

성향(TRAIT_EVIDENCE)은 자동 초안 값을 유지한다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 9, 14, 0)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 서울 디럭스 더블룸 14층",
    "nights": "◎ '1박 2일 잘 놀다 온 워커힐 호캉스'",
    "party": "◎ 동행자와 둘, 아이 동반 언급 없음",
    "included_meals": "○ 동행자 회사 복지 당첨 숙박, 조식 포함 여부 명시 없음",
    "arrival": "○ 주차타워 지하 3층 주차 팁을 적어 자차 직접 주차로 추론",
    "room_minimal": "○ '방에 잠깐 누워있다가 바로 수영하러 감' 외 객실 최소화 문장 없음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.5, '◎ 체크인 대기 인원이 많아 순번까지 20분 정도 기다림, 포기·불만 없이 담담히 기록'),
    '이동 최소화': (0.75, "○ '주차타워 지하 3층과 호텔 지하 1층이 연결되어 있어 지하 3층에 주차하는 것이 이동하는 게 편함' — 이동 편의를 기준으로 주차 위치를 고름"),
    '격식 선호': (0.25, "◎ 더 파빌리온 빙수 가격 보고 '못 사 먹겠다', 피자 대신 초밥·회 배달, 부족해서 편의점 컵라면 — 캐주얼·포장을 골라 먹음"),
    '조망 중시': (0.5, "◎ '비 와서 아숩지만 그래도 한강뷰라 좋았음' — 좋았다 정도"),
    '새로움 추구': (None, '근거 없음 → 미상'),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (조식을 같이 먹었다는 사실만 있음)'),
    '조용함 선호': (None, '근거 없음 → 미상 (조식 때 사람 많았다는 묘사만)'),
}

PERSONA = Persona(
    name='blog61 · 그랜드 디럭스 더블 한강뷰 1박 · 2인 · 수영·빵·배달',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    arrival='car_self',
    room_minimal=False,
    note="정답 확인 2차 · 시험용 · 성향 자동 초안 유지",
)

TRUTH_VISITED: dict[str, str] = {
    "PARKING_TOWER_B1": "○ 주차타워 지하 3층과 호텔 지하 1층 연결 동선을 안내",
    "GRAND_FRONT_DESK": "◎ 프런트 근처 태블릿에 예약 정보 입력 후 20분 대기해 체크인",
    "GRAND_ROOM": "◎ 14층 디럭스 더블룸 배정, 무료 미니바 이용",
    "GRAND_POOL": "◎ 방에 잠깐 누웠다가 바로 수영, 탈의실·탈수기 이용",
    "LE_PASSAGE": "◎ 수영 후 레몬크림 시나몬롤 구매(투숙객 할인), 다음날 아이스 아메리카노 구매",
    "CU_THEATRE": "◎ 배달이 양이 적어 CU 가서 컵라면 사다 먹음(저녁 7시 반쯤)",
    "GRAND_LOBBY": "◎ 배달 장소를 정문 로비로 해서 배달기사를 만남",
    "THE_BUFFET": "○ 다음날 조식 뷔페(지정 자리 안내, 양식·한식) — 장소명은 해시태그 '그랜드워커힐조식'뿐이라 더뷔페로 추론"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "THE_PAVILION": "◎ 르 파사쥬 바로 옆 더 파빌리온 빙수 가격만 보고 못 사 먹겠다고 적음",
    "PIZZA_HILL": "◎ '워커힐 피자를 먹을까도 고민했지만' 초밥·회 배달을 시킴",
    "VISTA_POOL": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "외부 배달 음식": "◎ 피자 대신 초밥·회 배달을 시킴 — 체크리스트상 끼니로 세지 않음"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [
    ('GRAND_ROOM', 'GRAND_POOL', '◎ 방에 잠깐 누워있다가 바로 수영하러 감'),
    ('GRAND_POOL', 'LE_PASSAGE', '◎ 수영 후 빵 사러 감'),
    ('LE_PASSAGE', 'CU_THEATRE', '◎ 빵 구매 후 배달 음식이 부족해 저녁 7시 반쯤 CU 컵라면'),
    ('CU_THEATRE', 'THE_BUFFET', '◎ 첫날 밤 CU, 다음날 조식')
]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'LE_PASSAGE', '◎ 수영 후 허기져서 시나몬롤 구매'), ('조식', 'THE_BUFFET', '○ 다음날 일어나서 바로 조식 뷔페'), ('간식', 'LE_PASSAGE', '◎ 조식 후 르 파사쥬에서 아이스 아메리카노 구매')]
