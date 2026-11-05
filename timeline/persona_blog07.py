"""
blog07 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 → (OCR) 텍스트 → LLM(손 페르소나를 못 보는 별도 에이전트) → JSON. 시험용 봉인 2026-09-24 — 에이전트 v3 실행 전에 정답 확정. 사람이 정답만 원문과 대조 (성향은 손대지 않음)
손으로 만든 persona_blog07.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 7
시험용(held-out) 후기 — run_all.py 가 읽는다. 에이전트를 이 후기에 맞춰 고치면 더 이상 시험용이 아니다.
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 12, 25, 14, 30)      # △

FACTS_EVIDENCE = {
    "property": "◎ '워커힐 더글라스 하우스', '더글라스 디럭스 트윈' 투숙",
    "nights": "◎ '12월 25일부터 1박 2일'",
    "party": "○ 더글라스 디럭스 트윈(트윈룸) 및 '1인당 스낵 박스 하나씩' 표현으로 2인 추정, 정확한 인원 명시 없음",
    "included_meals": "◎ 더글라스 하우스 투숙 시 라운지(라이트 스낵·더글라스 아워·라이트 조식)가 숙박에 포함된다고 명시, 규칙상 조식·석식을 DOUGLAS_LOUNGE로 처리",
    "room_minimal": "△ 더글라스 하우스 내 객실 등급 비교 정보가 없어 최소 객실 여부 판단 불가, false로 둠"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (None, '근거 없음 → 미상 (셔틀 대기 5분 내외라는 언급은 있으나 대기에 대한 태도를 보여주는 행동·선호 서술은 아님)'),
    '이동 최소화': (0.6, "◎ '체크인 동선. 그랜드 워커힐을 거쳐야 해서 처음에는 다소 복잡하게 느껴질 수 있습니다'를 아쉬운 점으로 꼽음 · 반면 수영장까지 셔틀 5분 거리는 '부담 없이 다녀왔다'고 함"),
    '격식 선호': (0.2, '◎ 피자힐에서 피자 포장, 더글라스 아워 테이크아웃을 객실에서 즐기는 등 식사가 전반적으로 캐주얼/테이크아웃 위주였고 정찬·코스 이용 서술 없음'),
    '조망 중시': (0.7, "◎ '테라스로 나가면 한강과 서울 시내가 한눈에 들어옵니다', '서울 안에서 이 정도 뷰를 가진 숙소가 많지 않다는 점에서 만족스러웠습니다', 총평에서도 '한강 뷰'를 장점으로 재차 강조"),
    '새로움 추구': (0.6, '○ 체크인(그랜드 로비)·라운지 3타임(스낵·아워·조식)·수영장·로비 벽난로 등 숙박 중 여러 시설을 두루 이용함'),
    '함께 먹기 선호': (None, "근거 없음 → 미상 (식사 장면이 모두 '저는' 1인칭 단수 서술로, 함께 먹는 것을 중요히 여기는 서술이나 행동이 드러나지 않음)"),
    '조용함 선호': (0.85, "◎ '노키즈존에 숲으로 둘러싸인 이곳이 딱이었습니다'로 조용함을 선택 이유로 명시, 총평에서도 '노키즈존의 조용함', '아늑하고 조용한 매력'을 장점으로 강조"),
}

PERSONA = Persona(
    name='[자동] blog07 · 더글라스 하우스 크리스마스 1박 2일',
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
    note="자동 추출 · 미상 2개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "◎ '그랜드 워커힐 서울 본관에서 사전 체크인 절차를 거친 후' 셔틀로 이동",
    "GRAND_LOBBY": "◎ '그랜드 워커힐 로비에 들어서자마자 거대한 크리스마스 트리가 눈에 들어왔습니다', 재즈 밴드 라이브 공연 관람",
    "DOUGLAS_ROOM": "◎ '더글라스 디럭스 트윈' 객실 투숙",
    "DOUGLAS_LOUNGE": "◎ 라이트 스낵·더글라스 아워·라이트 조식 모두 이용",
    "GRAND_POOL": "◎ '가볍게 몇 바퀴 돌기에는 충분했습니다... 셔틀로 5분이면 이동할 수 있어서 부담 없이 다녀왔습니다'",
    "PIZZA_HILL": "◎ '피자힐에서 피자를 포장해 와서... 콤비네이션+해산물 하프앤하프를 포장했습니다'"
}
TRUTH_PASSED: dict[str, str] = {
    "FITNESS": "그랜드 워커힐 피트니스를 무료로 이용할 수 있다고 언급만 하고 실제 이용 서술 없음",
    "THE_BUFFET": "추가 금액을 내면 그랜드 워커힐 더뷔페 조식을 별도 이용할 수 있다고 언급만 함, 본인 이용 서술 없음",
    "DOUGLAS_LOBBY": "○ '더글라스 하우스 로비에는... 벽난로가 있습니다. 크리스마스 트리 옆 소파에 앉아 불멍을 하며 쉬기 좋습니다' — [봉인 확인] 쉬기 좋다는 묘사라 이용 확정 아님 → 구경/통과로"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ONDAL": "○ 언급 없음",
    "GEUMRYONG": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "VISTA_POOL": "○ 언급 없음",
    "RIVERPARK": "○ 언급 없음",
    "WELLNESS_SAUNA": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "THEATRE_OF_LIGHT": "○ 언급 없음",
    "FOREST_PARK": "○ 언급 없음",
    "LE_PASSAGE": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "THE_PAVILION": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "멀티룸(당구대·보드게임)": "지하 멀티룸(당구대, 보드게임)이 언급되나 목록 코드 없음, 본인 이용 여부도 불명확해 일반 시설 설명으로만 처리"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('GRAND_FRONT_DESK', 'DOUGLAS_ROOM', '◎ 그랜드 워커힐에서 사전 체크인 후 셔틀로 더글라스 하우스 객실로 이동'), ('DOUGLAS_ROOM', 'DOUGLAS_LOUNGE', '◎ 체크인 후 이용할 수 있는 라이트 스낵(오후 티타임)을 이용'), ('DOUGLAS_LOUNGE', 'PIZZA_HILL', '◎ 15시 라이트 스낵 이후 저녁에 피자힐에서 피자를 포장해 옴'), ('DOUGLAS_ROOM', 'GRAND_POOL', '○ 체크인 이후 숙박 중 셔틀로 그랜드 워커힐 수영장을 다녀옴')]
TRUTH_MEALS: list[tuple[str, str, str]] = [('간식', 'DOUGLAS_LOUNGE', '◎ 라이트 스낵(15:00~17:00) 커피·디저트 이용'), ('석식', 'DOUGLAS_LOUNGE', '◎ 더글라스 아워 테이크아웃(스낵 박스, 와인)을 객실에서 즐김'), ('석식', 'PIZZA_HILL', '◎ 피자힐에서 포장한 피자를 더글라스 아워 테이크아웃과 함께 저녁으로 먹음'), ('조식', 'DOUGLAS_LOUNGE', '◎ 라이트 조식(07:00~10:00) 빵·샐러드 등 이용')]
