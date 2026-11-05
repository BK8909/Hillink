"""근거 기반 페르소나와 명시적 실험 가정을 분리한 제출본.
OBSERVED_PERSONA / STAY_FACTS는 미상을 보존한다.
PERSONA는 기존 run_all.py와 호환되는 가정 포함 실행본이다.
0.75는 공통 척도가 아닌 임시 해석값. 실제 성격 측정값이 아니다.
TRUTH_*는 실행 후 평가용으로만 사용한다. 원문은 팀 후기 대응표 참조.
원문 재열람은 보안 정책으로 차단되어 기존 검수 요약만 사용했다.
"""
from dataclasses import replace
from datetime import datetime
from agent_v0 import Persona

SOURCE_ID = "blog06"
SOURCE_CHECKED = "2026-09-23"
EVIDENCE_FORMAT = "기존 본문 검수 기록의 요약이며 원문 직접 인용이 아님"
STAY_FACTS = {
    "property": None, "nights": 1,
    "adults": None, "children": None, "infants": None, "party_size": None,
    "included_meals": None, "visit_dates": None,
}
FACTS = {
    "숙박": ("당일~다음 날 퇴실의 1박 흐름; 건물은 추가 확인 필요", "객실 및 다음 날 퇴실 서술. 타임라인의 GRAND 배치를 원문 사실로 승격하지 않음"),
    "인원": (None, "작성자와 동행자 1명 언급. 전체 인원·아동 수 미상"),
    "방문일": (None, "게시일 2023-12-12와 실행 좌표 2000-01-01은 방문일이 아님"),
    "포함 식사": (None, "포장 피자와 다음 날 시리얼 식사는 확인. 예약 포함 식사 정보 없음"),
    "교통": ("피자힐 왕복 셔틀", "추위와 이동 부담 때문에 선택"),
    "클럽 자격": (None, "예약 자격 근거 없음"),
}
TRAIT_EVIDENCE = {
    "대기 회피": (0.75, "피자힐 절: 앞에 11팀, 예상 60~90분 안내 후 포장 선택. 이 상황에서의 회피 행동이며 일반적인 대기 한도는 미상"),
    "이동 최소화": (0.75, "셔틀 구간: 추위와 이동 부담 때문에 셔틀 선택. 당시 조건에 한정된 해석"),
    "격식 선호": (None, "포장 주문만으로 격식 선호를 추정하지 않음"),
    "조망 중시": (None, "검수 근거에 명시적 선호 없음"),
    "새로움 추구": (None, "전시 관람·아트샵 구경만으로 지속적인 성향을 단정하지 않음"),
    "함께 먹기 선호": (None, "동행자 1명은 사실이나 함께 먹기 선호는 미상"),
    "조용함 선호": (None, "라이브러리 방문만으로 성향을 추정하지 않음"),
}
OBSERVED_PERSONA = Persona(
    name="blog06 · 전시·피자 포장 · 1박 흐름",
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=None, has_child_under_13=None, nights=1,
    included_meals=None, room_minimal=None, property=None, is_guest=True,
    club_access=None,
    note="성향 2개 임시 코딩 / 5개 미상. 건물·총 인원·포함 식사 추가 확인 필요.",
)
TRUTH_VISITED = {
    "CU_THEATRE": "전시장 옆 CU에서 간식",
    "THEATRE_OF_LIGHT": "16시 도슨트 예약 후 관람; 예약 시각과 실제 입장 시각 구분",
    "PIZZA_HILL": "포장 주문·수령. 매장 식사 아님",
    "GRAND_LIBRARY": "다음 날 식사 후 그랜드 2층 라이브러리 방문",
}
TRUTH_PASSED = {"THEATRE_ART_SHOP": "관람 뒤 아트샵 구경; 구매 여부 미상"}
TRUTH_LOCATION_PENDING = {"ROOM": "숙박 및 포장 식사 장소인 객실. 건물 추가 확인", "POOL": "19시 이후 수영, 21:30 나옴; 풀장 건물 추가 확인"}
TRUTH_NOT_VISITED = {}  # 산책 아쉬움은 특정 시설의 확정 미방문으로 만들지 않는다.
TRUTH_UNREACHABLE = {}
TRUTH_RESTAURANTS = frozenset({"PIZZA_HILL"})
TRUTH_RESTAURANTS_COMPLETE = False
TRUTH_ORDER_PAIRS = [("THEATRE_OF_LIGHT", "PIZZA_HILL", "추가 관람·아트샵 구경 뒤 셔틀로 피자힐")]
TRUTH_EVENT_ORDER = [("피자 포장 수령", "객실 식사"), ("객실 식사", "수영"), ("다음 날 시리얼 식사", "라이브러리"), ("라이브러리", "퇴실")]
TRUTH_MEALS = []  # 포장 식사의 실제 소비 장소는 객실, 호텔 조식 업장은 확인되지 않음
TRUTH_TAKEOUT = {"PIZZA_HILL": ["불고기피자 라지", "연어샐러드"]}

EXPERIMENT_ASSUMPTIONS = {
    "party_size": (2, "작성자와 동행자 1명만 모델링. 실제 총 인원은 미상"),
    "has_child_under_13": (False, "아동 미상. 성인만의 조건으로 실행"),
    "included_meals": ((), "예약 포함 여부 미상: 포함 식사에 의한 강제 선택/가점 미적용"),
    "room_minimal": (False, "객실 최소 체류 선호 미상: 추가 감점 미적용"),
    "property": ("GRAND", "숙박 건물 미확인. 기존 타임라인의 실행 가정 재사용; VISTA/DOUGLAS도 별도 비교"),
    "club_access": (False, "예약 자격 미상: 클럽 후보를 제외한 시험 조건"),
}
START_AT = datetime(2000, 1, 1, 15, 0)
START_AT_BASIS = "방문일 미상. 기존 blog06과 같은 2000-01-01 실행 좌표; 15시 도착은 본문 기록. 과거 실제 영업시간 복원 아님"

PERSONA = replace(
    OBSERVED_PERSONA,
    **{key: value for key, (value, _) in EXPERIMENT_ASSUMPTIONS.items()},
    note=OBSERVED_PERSONA.note + " [가정 포함 실행본; EXPERIMENT_ASSUMPTIONS 참조]",
)


def print_persona():
    print(PERSONA.name)
    for key, (value, why) in TRAIT_EVIDENCE.items():
        print(f"{key}: {'미상' if value is None else value} / {why}")
    print("사실:", STAY_FACTS)
    print("실험 가정:")
    for key, (value, why) in EXPERIMENT_ASSUMPTIONS.items():
        print(f"  {key}={value!r}: {why}")
    print("시작:", START_AT.isoformat(), START_AT_BASIS)


if __name__ == "__main__":
    print_persona()
