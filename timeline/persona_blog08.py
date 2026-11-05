"""
blog08 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 → (OCR) 텍스트 → LLM(손 페르소나를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2026-09-24 — 에이전트 v3 실행 전에 정답 확정. 사람이 정답만 원문과 대조 (성향은 손대지 않음)
손으로 만든 persona_blog08.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 8
시험용(held-out) 후기 — run_all.py 가 읽는다. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 10, 29, 14, 30)      # △

FACTS_EVIDENCE = {
    "property": "◎ '워커힐 비스타 서울', '비스타워커힐 서울 13층 한강뷰' 등 비스타 객실 명시",
    "nights": "○ 전날 다른 호텔에 묵었다는 언급으로 이날 최소 1박은 확인되나 정확한 박수 명시는 없음 → 1박으로 추정",
    "party": "○ 아이와 함께 여행, '저희'라는 표현으로 동행자 존재 확인. 정확한 인원 수는 명시되지 않음 → 2인(아이 포함)으로 추정",
    "included_meals": "○ 패키지·요금에 포함되었다는 끼니 언급 없음",
    "room_minimal": "◎ '침대도 넓고 객실 상태가 매우 좋았습니다' → 미니멀 객실 아님"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상'),
    '이동 최소화': (None, '근거 없음 → 미상'),
    '격식 선호': (None, '근거 없음 → 미상 (라운지 카페 이용만 있고 격식·캐주얼 식당 선택 관련 서술 없음)'),
    '조망 중시': (0.8, "◎ 라운지에서 '이런 탁 트인 뷰를 보면서 간만에 여유를 부리니 답답했던 마음이 시원하게 풀리는 것 같았다', 수영장도 '통유리창을 통해 한강 시내전망을 볼 수 있었다'고 강조, 글 제목부터 '한강 리버뷰'를 내세움 → 조망을 매우 중시"),
    '새로움 추구': (0.7, "◎ '워커힐은 처음 방문입니다', 라운지·전시·수영장 등 여러 시설을 두루 다니며 '여기저기 구석구석 보는 재미도 있었습니다' → 새로움 추구 성향 높음"),
    '함께 먹기 선호': (0.6, "○ '저희는 워커힐 빛의 라운지 카페에서 아아와 캐모마일티, 나중에는 라떼를 하나 더 시켰고 아주 잘 마시고 방으로 올라갔다' → 동행자와 함께 음료를 마심"),
    '조용함 선호': (0.8, "◎ '생각했던 것보다 공간이 무척 넓었고 북적이지도 않았습니다', '평화롭고 조용한 분위기 속에서 오래 앉아있었습니다' → 조용함을 선호"),
}

PERSONA = Persona(
    name='[자동] blog08 · 비스타 리버뷰 1박 · 아이 동반',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=2,
    has_child_under_13=True,
    nights=1,
    property='VISTA',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(),
    booked=(),
    room_minimal=False,
    note="자동 추출 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "VISTA_ROOM": "◎ '워커힐 비스타 서울 우리 방에 짐을 놓고', '침대도 넓고 객실 상태가 매우 좋았습니다' → 객실 투숙",
    "THEATRE_OF_LIGHT": "◎ '빛의 시어터에서 진행 중이었던 전시가 파라오의 이집트... 이었습니다', '여기저기 구석구석 보는 재미도 있었습니다' → 전시 관람",
    "VISTA_POOL": "◎ '워커힐 비스타 실내수영장입니다. 3층에 위치해 있어... 유아풀 및 선베드 등 부대시설도 마련되어 있어서 편하게 놀다왔습니다' → 수영장 이용"
}
TRUTH_PASSED: dict[str, str] = {}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "PIZZA_HILL": "○ 언급 없음",
    "THE_BUFFET": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "GRAND_POOL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "빛의 라운지(카페)": "1층 몰입형 미디어아트 전시를 포함한 카페 라운지, 짐을 두고 방문해 음료를 주문하고 장시간 머묾 — 장소 코드 목록에 해당 항목 없음"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset([])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VISTA_ROOM', 'THEATRE_OF_LIGHT', '◎ 객실에 짐을 두고 1층 빛의 라운지(전시 공간 포함)로 이동'), ('THEATRE_OF_LIGHT', 'VISTA_POOL', '○ 라운지·전시 관람 후 방으로 돌아왔다가 이어서 수영장으로 이동')]
TRUTH_MEALS: list[tuple[str, str, str]] = []
