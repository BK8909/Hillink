"""
정답 확인: 경수 · 보류: LUX_BAR — '럭스바 가기 전에 산책' 한 줄뿐, 이용 서술 없음 · 중식@THE_PAVILION — 원문은 '브런치'

blog26 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog26.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 26
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 2, 16, 14, 30)      # 날짜 ○ '2026년 설 연휴 첫째날' (2/16) · 시각 △ 추정 — 작성일(9월)로 두면 겨울 체류가 여름이 된다

FACTS_EVIDENCE = {
    "property": "◎ '우리는 그랜드 워커힐에서 묵었다', 그랜드 트윈 객실",
    "nights": "◎ 그랜드 워커힐 2박 3일 호캉스",
    "party": "◎ 동행자와 둘 (트윈 객실, 수라상 2인분, '우리 둘만') · 아이 동반 언급 없음",
    "included_meals": "○ 조식은 '신청' 해야 하는 방식으로 적힘 — '포함' 표기 없음",
    "booked": "◎ 더 파빌리온 애프터눈 티세트 네이버 예약 · ◎ 온달 수라상 차림 미리 예약",
    "arrival": "◎ 자가용으로 운전해 와서 주차타워에 직접 주차",
    "room_minimal": "◎ 객실에서 피자 파티하며 쉼 — 객실을 적극 사용"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.25, "○ 체크인 줄을 서서 기다리는 동안 동행자는 로비 공연을 보며 '기분 좋더라' — 대기 중 다른 걸 하며 긍정적으로 적음"),
    '이동 최소화': (0.25, "○ 둘째 날 낮 '본격적으로 산책에 나섰다' — 걸어서 더글라스 하우스·포레스트파크까지 감, 체크아웃 후 먼 경복궁까지 차로 이동"),
    '격식 선호': (0.75, "◎ 여러 식당 중 '고르고 골라서' 한정식 코스 온달을 택하고 프라이빗 룸으로 예약"),
    '조망 중시': (0.75, "◎ '한강 야경 구경하러 잠깐 나갔다 왔다' — 야경을 목적으로 산책 · 조식 때 좋은 자리 잡아 일출 봄"),
    '새로움 추구': (0.75, "◎ 라이브러리 '도서관 탐방', 지하 '편의점 탐방' 등 안 가 본 곳을 일부러 찾아다님 · '모든 식당을 다 갈 순 없었다'"),
    '함께 먹기 선호': (None, '근거 없음 → 미상 (동행자 입맛에 맞춰 브런치를 추가 주문했을 뿐, 같이 먹으려 선택을 바꾼 문장 없음)'),
    '조용함 선호': (0.75, "◎ 온달에서 '프라이빗하게 즐기는 룸이 좋아' 룸을 택함 · 경복궁에서도 '사람 많은 곳을 피해' 다니고 '최대한 사람이 적은' 대여점을 고름"),
}

PERSONA = Persona(
    name='blog26 · 그랜드 2박 · 성인 2인 · 자차 · 설 연휴 체류',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=2,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=('THE_PAVILION', 'ONDAL'),
    arrival='car_self',
    room_minimal=False,
    note="자동 추출 · 미상 1개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "◎ 줄서서 기다려 체크인 (대기 — 규칙 ①)",
    "GRAND_LOBBY": "◎ 체크인 대기 중 로비 공연을 봄",
    "GRAND_ROOM": "◎ 그랜드 트윈 객실에 묵으며 피자 파티",
    "LE_PASSAGE": "◎ 르 파사쥬 키오스크에서 베이컨 포테이토 피자를 사서 객실로 가져감",
    "LUX_BAR": "○ '럭스바 가기 전에 잠깐 산책한 것' — 첫날 밤 럭스바에 감",
    "GRAND_LIBRARY": "◎ 로비 한 층 위 라이브러리를 카드키로 들어가 탐방",
    "CU_THEATRE": "◎ 지하 1층 CU 편의점 탐방, 탄산 음료 구매",
    "THE_PAVILION": "◎ 둘째 날 조식 대신 더 파빌리온에서 애프터눈 티세트와 브런치",
    "FOREST_PARK": "◎ 포레스트파크에 올라가 투숙객 확인 후 텐트에서 음료 두 잔 마심",
    "ONDAL": "◎ 둘째 날 저녁 온달 룸에서 수라상 차림 코스",
    "THE_BUFFET": "◎ 셋째 날 6시 30분 비스타 더 뷔페 조식",
    "PARKING_TOWER_B1": "○ 주차타워에 주차 — '만석은 아니어서', 헤매며 건물로 (주차 서술 — 규칙 ①, 층 미상)"
}
TRUTH_PASSED: dict[str, str] = {
    "PIZZA_HILL": "◎ 가 봤지만 사람이 많아 냄새만 맡고 이용 안 함",
    "VISTA_LOBBY": "○ 야경 산책 중 '비스타 워커힐도 멋있었고' — 구경만",
    "DOUGLAS_LOBBY": "◎ 산책하다 더글라스 하우스를 만남 — 외관만 봄"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "THEATRE_OF_LIGHT": "◎ 가고 싶었으나 전시가 없어 휴관",
    "GEUMRYONG": "◎ 금룡도 있지만 '모든 식당을 다 갈 순 없었다' — 온달을 택함",
    "WELLNESS_SAUNA": "○ 언급 없음 (포레스트파크 핀란드 사우나는 이용 안 함)",
    "ANNEX": "○ 언급 없음",
    "CONVENTION": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
    "HOTEL_GATE": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "PARKING_TOWER_4F": "○ 언급 없음 (주차 층 미상)",
    "RIVERPARK": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "VALET_DESK": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "VISTA_ROOM": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "그랜드 지하 1층 빛의 라운지 카페": "◎ 파빌리온 후 후식으로 들어가 에이드를 마심 (음료만 — 끼니 아님)"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['ONDAL', 'THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('LE_PASSAGE', 'LUX_BAR', '◎ 첫날 르 파사쥬 피자로 방에서 파티 → 산책 → 럭스바'), ('LE_PASSAGE', 'GRAND_LIBRARY', "◎ 피자 파티·야경 산책을 마치고 '이번에는 도서관 탐방'"), ('GRAND_LIBRARY', 'CU_THEATRE', "○ 도서관 다음 '그리고 지하 1층. 편의점 탐방'"), ('THE_PAVILION', 'FOREST_PARK', '○ 둘째 날 아침 파빌리온 → 둘째 날 낮 산책 중 포레스트파크'), ('THE_PAVILION', 'ONDAL', '◎ 둘째 날 아침 파빌리온 → 둘째 날 저녁 온달'), ('ONDAL', 'THE_BUFFET', '◎ 둘째 날 저녁 온달 → 셋째 날 조식 뷔페')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'LE_PASSAGE', '◎ 첫날 간식 겸 식사로 르 파사쥬 피자 포장해 객실에서 먹음'), ('중식', 'THE_PAVILION', '◎ 둘째 날 조식을 건너뛰고 애프터눈 티세트와 브런치 (브런치라 끼니 구분은 ○)'), ('석식', 'ONDAL', '◎ 둘째 날 저녁 온달 수라상 차림'), ('조식', 'THE_BUFFET', '◎ 셋째 날 6시 30분 더 뷔페 조식')]
