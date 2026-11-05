"""
blog58 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 네이버 블로그(hillink 수집) → review_queue 내보내기 → LLM(손 페르소나 · 에이전트를 못 보는 별도 에이전트) → JSON. 추출기 9/28 판(시작 날짜·시각 분리 · 비투숙 기본 시각). 정답 확인 2차 — 개발용
손으로 만든 persona_blog58.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 58
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 8, 14, 30)      # 날짜 △ 글 작성일 · 시각 △ 추정

FACTS_EVIDENCE = {
    "property": "◎ 그랜드 워커힐 아차산뷰 클럽딜럭스 예약",
    "nights": "◎ 1박 2일",
    "party": "◎ 작성자와 동행자 둘",
    "included_meals": "○ 클럽딜럭스 객실로 티타임·저녁 클럽라운지·클럽라운지 조식 이용 — '포함' 이라는 단어는 없고 클럽 객실이라 라운지 이용으로 봄",
    "room_minimal": "◎ 방에서 먹고 자고, 라운지 사이에 방에서 쉬고, 조식 후 한숨 더 잠"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.5, '○ 한강뷰 자리를 위해 더뷔페에 첫 번째로 줄 서서 기다림(긍정적 대기) · 반면 모바일 체크인으로 대기 없이 방 배정받음 → 섞임'),
    '이동 최소화': (0.25, '○ 저녁에 셔틀을 타고 포레스트파크까지 가서 둘러보고, 퇴실 후 더글라스 가든 산책까지 일부러 감'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.75, '◎ 더뷔페 한강뷰가 좋다고 해서 첫 번째로 줄 서 한강뷰 자리 확보 · 객실은 클럽 혜택을 위해 한강뷰를 포기'),
    '새로움 추구': (0.75, "○ '이왕 간 김에 야무지게 즐기고 싶어서' 클럽 객실 선택, 포레스트파크·더글라스 가든·기념품샵까지 두루 찾아감"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상'),
}

PERSONA = Persona(
    name='[자동] blog58 · 그랜드 클럽 딜럭스 1박 · 성인 2인 · 셔틀 이용',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=False,
    nights=1,
    property='GRAND',
    is_guest=True,
    club_access=True,
    depart_by=time(20, 0),
    included_meals=(('간식', 'GRAND_CLUB_LOUNGE'), ('석식', 'GRAND_CLUB_LOUNGE'), ('조식', 'GRAND_CLUB_LOUNGE')),
    booked=('THE_BUFFET',),
    arrival=None,
    room_minimal=False,
    note="자동 추출 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "GANGBYEON_STN": "◎ 강변역에서 셔틀버스를 타고 호텔로 옴, 귀가도 강변역행 셔틀",
    "GRAND_ROOM": "◎ 모바일 체크인 후 방에 짐을 두고 쉼, 투숙",
    "GRAND_CLUB_LOUNGE": "◎ 티타임에 에그타르트, 저녁 클럽라운지에서 와인·맥주, 다음 날 라운지 조식",
    "FOREST_PARK": "○ 호텔 셔틀을 타고 포레스트파크에 가서 둘러봄 ('구경' 이지만 일부러 찾아이 산책)",
    "THE_BUFFET": "◎ 퇴실 후 주말 중식 2부 예약으로 입장해 2시간 식사"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "○ 언급 없음 (모바일 체크인)",
    "GRAND_POOL": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FITNESS": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "더글라스 가든": "◎ 퇴실 후 짐을 맡기고 산책",
    "지하 1층 기념품 판매점": "◎ 산책 후 기념품 구입 — 빛의 시어터 아트샵인지 불명",
    "한강변 산책로": "◎ 저녁 라운지 후 동행자가 산책을 원해 나가서 노을 구경"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GANGBYEON_STN', 'GRAND_ROOM', '◎ 강변역 셔틀로 호텔 도착 후 방 배정'), ('GRAND_ROOM', 'GRAND_CLUB_LOUNGE', '◎ 짐을 두고 티타임 즐기러 라운지로'), ('GRAND_CLUB_LOUNGE', 'FOREST_PARK', '◎ 저녁 라운지 후 산책, 셔틀 타고 포레스트파크'), ('FOREST_PARK', 'THE_BUFFET', '◎ 포레스트파크는 첫날, 더뷔페는 다음 날 퇴실 후'), ('GRAND_CLUB_LOUNGE', 'THE_BUFFET', '◎ 라운지 조식 먹고 퇴실 후 더뷔페 중식')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'GRAND_CLUB_LOUNGE', '◎ 티타임에 갓 구운 에그타르트 등 디저트'), ('석식', 'GRAND_CLUB_LOUNGE', '○ 저녁 클럽라운지에서 와인·맥주와 함께 이용'), ('조식', 'GRAND_CLUB_LOUNGE', '◎ 다음 날 클럽라운지 조식'), ('중식', 'THE_BUFFET', '◎ 퇴실 후 주말 중식 2부 더뷔페')]
