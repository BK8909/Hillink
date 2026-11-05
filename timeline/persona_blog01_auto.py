"""
blog01 — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

추출 경로: 후기 PDF → OCR 텍스트 → LLM → JSON
손으로 만든 persona_blog01.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py 1
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

START_AT = datetime(2025, 1, 1, 14, 30)      # △ 후기에 날짜·시각 없음

FACTS_EVIDENCE = {
    "property": "◎ '그랜드로 픽', '그랜드 워커힐 서울' 체크인 - 디럭스 트윈",
    "nights": "◎ '워커힐 호캉스 2박 3일', '2박 3일 놀고 체크아웃'",
    "party": "◎ 패키지 설명 '성인 2+아이2', 아이·아이 언급으로 성인2+아동2 구성",
    "included_meals": "◎ '하루는 조식포함(성인2+아이2), 하루는 중식포함(성인2+아이)', 이용처는 비스타 건물 소재 더뷔페로 서술(조식후기·주말점심 후기)",
    "room_minimal": "◎ '기본룸 기준으로 비스타가 조금 더 비쌍' - 기본(디럭스) 등급 객실 예약"
}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    '대기 회피': (0.2, "◎ 체크인 대기 중 '패드에 핸드폰번호 등록해두면 톡 알림' 신청, '동행자은 로비에서, 난 애들 데리고 구경다님' - 대기를 다른 활동으로 채움"),
    '이동 최소화': (None, "근거 없음 → 미상 (라이브러리 '동선이 좋진 않음' 언급은 시설 특징 서술일 뿐, 이 때문에 선택을 바꿨다는 서술은 없음)"),
    '격식 선호': (0.2, "◎ '우리는 피자힐이랑 더뷔페만 이용해봄' - 코스요리 식당(온달·금룡 등)은 이용하지 않고 캐주얼 식당만 이용"),
    '조망 중시': (0.2, "◎ '방에 있을 시간이 별로 없으니 리버뷰 굳이?' - 마운틴뷰(더 저렴한 등급)로 예약, 뷰를 위해 추가비용 지불 안했음을 스스로 밝힘"),
    '새로움 추구': (0.8, '◎ 체크인 전 로비·꽃집·포토존을 구경하고 비스타 건물까지 걸어가서 둘러봄 - 시설을 두루 훑음'),
    '함께 먹기 선호': (None, "근거 없음 → 미상 (가족 동반 식사이나 '함께 먹는 것'의 중요성에 대한 명시적 서술이나 행동 근거 없음)"),
    '조용함 선호': (None, '근거 없음 → 미상 (라이브러리가 한산하다는 서술은 공간 묘사일 뿐, 조용함을 선택 이유로 든 서술은 없음)'),
}

PERSONA = Persona(
    name='[자동] blog01 · 그랜드 2박 · 가족(아이2)',
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    has_child_under_13=True,
    nights=2,
    property='GRAND',
    is_guest=True,
    club_access=False,
    depart_by=time(20, 0),
    included_meals=(('조식', 'THE_BUFFET'), ('중식', 'THE_BUFFET')),
    booked=(),
    room_minimal=True,
    note="자동 추출 · 미상 3개",
)

TRUTH_VISITED: dict[str, str] = {
    "GRAND_FRONT_DESK": "◎ 체크인 카운터에서 체크인 진행 ('그리고 체크인!')",
    "GRAND_LOBBY": "◎ 주말 클래식 공연 관람 ('로비에서 주말에 클래식공연이 있어서 우리도 토요일에 봤는데 넘 좋았음')",
    "GRAND_POOL": "◎ '수영장에서 이틀 내내 썼고' - 그랜드 실내수영장 이용",
    "GRAND_ROOM": "◎ 디럭스 트윈 객실 숙박, 저층 트윈으로 변경 배정받음",
    "PIZZA_HILL": "◎ '우리는 피자힐이랑 더뷔페만 이용해봄'",
    "THE_BUFFET": "◎ 조식·중식 포함 패키지로 이용, '조식후기', '주말점심 후기' 서술",
    "VALET_DESK": "◎ '비자 플래티늄이 있어서 맡김' - 무료 발렛 이용"
}
TRUTH_PASSED: dict[str, str] = {
    "CONVENTION": "결혼식장 존재 언급, '토요일 일요일 결혼식 손님 많았음' - 지나가며 목격",
    "CU_THEATRE": "'지하 1층에 편의점이 있음' - 언급만, 구매 서술 없음",
    "FOREST_PARK": "'캠프같은거 보낼수 있음, 좋은 선택지 일 수도' - 시설 소개로만 언급, 이번 체류에 이용 서술 없음",
    "GRAND_LIBRARY": "'2층에는 투숙객전용 라이브러리가 있는데 돌아가야만해서 동선이 좋진 않음' - 언급만, 개인 이용 확인 안됨",
    "HOTEL_GATE": "'정면 원형지붕아래에서 발렛 맡길 수 있음' - 정문 인근 통과 서술",
    "LE_PASSAGE": "포스팅 내 관련글 링크로만 언급 ('르파사쥬, 라이브러리, 에노테카, 와인샵'), 본문 이용 서술 없음",
    "THEATRE_OF_LIGHT": "포스팅 내 관련글 링크로만 언급, 본문 이용 서술 없음",
    "THE_PAVILION": "'로비라운지 더파빌리온', 아이가 사달라고 했으나 '너무 비싸' 구매 안함 - 구경만",
    "VISTA_LOBBY": "'비스타까지 구경하고 애들이 밖으로 나가서 가고싶대서 다시 돌아나옴' - 구경만 하고 이용 안함"
}
TRUTH_NOT_VISITED: dict[str, str] = {
    "ANNEX": "○ 언급 없음",
    "DOUGLAS_LIBRARY": "○ 언급 없음",
    "DOUGLAS_LOBBY": "○ 언급 없음",
    "DOUGLAS_LOUNGE": "○ 언급 없음",
    "DOUGLAS_ROOM": "○ 언급 없음",
    "FITNESS": "○ 언급 없음",
    "GANGBYEON_STN": "○ 언급 없음",
    "GEUMRYONG": "◎ '우리는 피자힐이랑 더뷔페만 이용해봄' - 금룡 언급 직후 이용처를 한정하여 명시적 제외",
    "GOLF_CLUB": "○ 언급 없음",
    "GRAND_CLUB_LOUNGE": "○ 언급 없음",
    "GWANGNARU_STN": "○ 언급 없음",
    "ICN_T1": "○ 언급 없음",
    "ICN_T2": "○ 언급 없음",
    "LUX_BAR": "○ 언급 없음",
    "MOEGI": "○ 언급 없음",
    "MYONGWOLGWAN": "○ 언급 없음",
    "ONDAL": "○ 언급 없음",
    "PARKING_TOWER_4F": "◎ '무료카드 있으니 무조건 발렛이쥬' - 주차타워 직접 이용 대신 발렛만 이용",
    "PARKING_TOWER_B1": "◎ '무료카드 있으니 무조건 발렛이쥬' - 주차타워 직접 이용 대신 발렛만 이용",
    "RIVERPARK": "○ 언급 없음",
    "SKYARD": "○ 언급 없음",
    "TENNEZ_PARK": "○ 언급 없음",
    "THEATRE_ART_SHOP": "○ 언급 없음",
    "VISTA_POOL": "◎ '수영장은 각각 이용' + '그랜드로 픽' - 그랜드 투숙객으로 그랜드 수영장만 이용",
    "VISTA_ROOM": "◎ '그랜드로 픽' - 비스타가 아닌 그랜드 객실에 숙박",
    "WELLNESS_SAUNA": "○ 언급 없음"
}
TRUTH_UNREACHABLE: dict[str, str] = {
    "포토존(거울샷 촬영)": "◎ '비스타쪽 가는 길에 찍는곳도 있는데... 우리는 거울샷이나 찍자' - 목록에 없는 포토스팟에서 촬영(네컷사진은 구경만)"
}
TRUTH_RESTAURANTS: frozenset[str] = frozenset(['PIZZA_HILL', 'THE_BUFFET'])
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [('VALET_DESK', 'GRAND_FRONT_DESK', '○ 발렛 이후 체크인 대기로 이어지는 서술 순서'), ('GRAND_LOBBY', 'GRAND_FRONT_DESK', "◎ '체크인 가능 전까지 로비에서... 구경다님' 다음 '그리고 체크인!'"), ('VISTA_LOBBY', 'GRAND_FRONT_DESK', "◎ '비스타까지 구경하고... 다시 돌아나옴' 다음 '그리고 체크인!'"), ('GRAND_FRONT_DESK', 'GRAND_ROOM', "◎ 체크인 후 '올라가자~~' 객실로 이동"), ('GRAND_POOL', 'GRAND_ROOM', "◎ '수영장에서 이틀 내내 썼고 올라와서' 객실로 복귀")]
TRUTH_MEALS: list[tuple[str, str, str]] = [('조식', 'THE_BUFFET', "◎ 조식포함 패키지 이용, '한번은 조식' 서술"), ('중식', 'THE_BUFFET', "◎ 중식포함 패키지 이용, '주말점심 후기' 서술"), ('석식', 'PIZZA_HILL', '△ 석식포함 패키지가 매진되어 없었다는 서술과 피자힐 가격 언급으로 별도 결제 저녁 식사로 추정'), ('간식', 'GRAND_ROOM', '◎ 무료 미니바(하이볼, 물, 음료, 과자) 2박간 객실 내 이용')]
