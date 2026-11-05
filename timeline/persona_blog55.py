"""
정답 확인: 슬기 · 2차 · 보류 있음
보류: TRUTH_VISITED 의 도서관 — 원문은 '도서관'이라고만 적혀 있어 어느 건물인지 확정 불가
  → 9/29 소연: 풀림. 비스타 라이브러리가 따로 있다는 근거가 없어 라이브러리는 GRAND_LIBRARY 하나로 두기로 했다
    (비스타 투숙 blog19 도 "2층 워커힐 라이브러리" 라고 부른다). 건물을 몰라도 되므로 GRAND_LIBRARY 로 옮김
blog55 — r032 정답 확인.

성향(TRAIT_EVIDENCE)은 자동 초안 값을 유지한다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2026, 9, 7, 14, 10)      # 날짜 △ 글 작성일 · 시각 ◎ 후기

FACTS_EVIDENCE = {
    "property": "◎ 워커힐 비스타 디럭스룸(코너룸 배정)",
    "nights": "◎ 1박 2일",
    "party": "◎ 총 3명 이용, 조식은 성인 2인 + 1인 추가",
    "included_meals": "○ 조식은 추가/할인 이용으로 보이며 포함 문장은 없음 → 비움",
    "room_minimal": "◎ 객실에서 쉬고 풍선 세팅 등 객실 체류 시간이 있음"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.75, "◎ 체크인 웨이팅을 걸고 50분 가까이 기다린 뒤 '차라리 좀 더 늦게 올걸' 하고 불만을 적음"),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상'),
    '조망 중시': (0.75, '◎ 더뷔페 예약 때 창가석을 원한다고 코멘트를 남김 · 객실은 한강뷰/마운틴뷰를 고민하다 마운틴뷰 선택'),
    '새로움 추구': (0.75, "○ 비가 오는데도 우산을 쓰고 스카이야드 족욕까지 함, '비만 안 왔으면 더 다양한 시설을 알차게 즐겼을 텐데' 라고 아쉬워함"),
    '함께 먹기 선호': (None, '근거 없음 → 미상'),
    '조용함 선호': (None, '근거 없음 → 미상 (로비 붐빔·도서관 분위기는 묘사뿐)'),
}

PERSONA = Persona(
    name='blog55 · 비스타 디럭스 1박 · 성인 3인',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=3,
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
    note="정답 확인 2차 · 성향 자동 초안 유지",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_LOBBY": "◎ 로비에서 체크인 웨이팅을 걸고 기다리다 3시에 체크인",
    "VISTA_ROOM": "◎ 12층 디럭스 코너룸 배정, 방에서 쉬고 투숙",
    "THE_BUFFET": "◎ 저녁 더뷔페 창가석에서 식사, 다음 날 조식도 창가 자리에서 식사",
    "VISTA_POOL": "◎ 저녁 식사 후 소화시킬 겸 한강뷰 실내수영장에서 수영",
    "SKYARD": "◎ 비가 오지만 우산을 쓰고 스카이야드에서 족욕",
    "GRAND_LIBRARY": "○ '방에서 쉬다가 저녁 먹기 전에 도서관 구경을 해줬어요. 조용하니 분위기도 좋아서' — 9/29 소연: 라이브러리는 GRAND_LIBRARY 하나로 두기로 해 건물 불명 보류를 풀어 옮김"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "RIVERPARK": "○ 언급 없음 (비 때문에 다양한 시설을 못 즐겼다고 적음)",
    "GRAND_POOL": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "FITNESS": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [
    ('VISTA_ROOM', 'THE_BUFFET', '◎ 방에서 쉬다가 저녁 식사하러 감'),
    ('THE_BUFFET', 'VISTA_POOL', '◎ 저녁 뷔페 후 소화시킬 겸 수영'),
    ('VISTA_POOL', 'SKYARD', '○ 수영은 첫날 저녁, 스카이야드 족욕은 조식 뒤에 적힘'),
]
TRUTH_MEALS: list[tuple[str, str, str]] = [('석식', 'THE_BUFFET', '◎ 저녁 더뷔페에서 스시·대게·갈비 등 식사'), ('조식', 'THE_BUFFET', '◎ 다음 날 조식을 창가 자리에서 샐러드·과일·우동으로')]
