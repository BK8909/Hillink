"""근거 기반 페르소나와 명시적 실험 가정을 분리한 제출본.
OBSERVED_PERSONA / STAY_FACTS는 미상을 보존한다.
PERSONA는 기존 run_all.py와 호환되는 가정 포함 실행본이다.
0.75는 공통 척도가 아닌 임시 해석값. 실제 성격 측정값이 아니다.
TRUTH_*는 실행 후 평가용으로만 사용한다. 원문은 팀 후기 대응표 참조.
2026-10-16 원문 직접 재대조로 패키지 포함 범위를 보완했다. 원문 전문·주소는 저장하지 않는다.
"""
from dataclasses import replace
from datetime import datetime
from agent_v0 import Persona

SOURCE_ID = "blog05"
SOURCE_CHECKED = "2026-10-16"
EVIDENCE_FORMAT = "기존 검수 기록 + 2026-10-16 원문 직접 재대조 요약; 전문·직접 인용 아님"
# 예약 사실은 행동 예측 입력, TRUTH_*는 사후 비교 자료다.
STAY_FACTS = {
    "property": "VISTA", "nights": 1,
    "adults": 3, "children": None, "infants": None, "party_size": None,
    "included_meals": (("조식", "THE_BUFFET"), ("석식", "GRAND_CLUB_LOUNGE")),
    "included_adults": 2, "extra_paid_adults": 1,
    "visit_dates": ("2025-03-09", "2025-03-10"),
}
FACTS = {
    "숙박": ("비스타, 2025-03-09~10, 1박", "본문 도입부"),
    "인원": ("성인 3명 확인; 아동·영유아 수 및 전체 인원 미상", "라운지 절"),
    "포함 식사": ("해피아워·더뷔페 조식 기준 2명 포함, 추가 성인 1명 별도 결제", "2026-10-16 원문 라운지·조식·마무리 절 직접 확인. 성인 3명 전원 무료 포함으로 처리하지 않음"),
    "교통": ("귀가 시 동행 1명 차량 출근, 작성자 등 셔틀", "셔틀버스 절; 도착 수단·하차역 미상"),
    "클럽 자격": (None, "라운지 실제 이용은 확인. 클럽 객실 예약 여부와 사전 포함 자격은 별개"),
    "객실 최소 체류": (None, "최소 체류를 원한다는 진술 없음"),
}
TRAIT_EVIDENCE = {
    "대기 회피": (0.75, "조식 절: 다른 후기의 긴 대기를 읽고 2부 개시 약 10분 전에 줄을 섬. 대기를 피하려는 사전 행동으로 코딩; 최대 대기시간은 미상"),
    "이동 최소화": (None, "이동의 부담이나 이동을 줄이려는 선호 근거 없음"),
    "격식 선호": (None, "라운지 이용만으로 격식 선호를 추정하지 않음"),
    "조망 중시": (0.75, "라운지 절: 창가에 앉으려고 일찍 방문해 마지막 창가 자리를 확보"),
    "새로움 추구": (None, "여러 시설 방문이 새로운 경험 선호를 뜻하는지는 미상"),
    "함께 먹기 선호": (None, "성인 3명 이용은 인원 사실이며 혼자 먹기보다 함께 먹기를 선호한다는 근거 없음"),
    "조용함 선호": (None, "직접적인 선호 근거 없음"),
}
OBSERVED_PERSONA = Persona(
    name="blog05 · 비스타 1박 · 성인 3명 확인",
    traits={k: v for k, (v, _) in TRAIT_EVIDENCE.items()},
    party_size=None, has_child_under_13=None, nights=1,
    # 2명 포함 + 1명 별도 결제를 팀 전체 포함 튜플 하나로 표현할 수 없어 미표현. 사실은 STAY_FACTS 참조.
    included_meals=None, room_minimal=None, property="VISTA", is_guest=True,
    club_access=None,
    note="성향 2개 임시 코딩 / 5개 미상. 성인 수 3과 전체 인원을 구분. 실행 가정은 사실과 별도 기록 필요.",
)
OBSERVED_ADULTS = 3
# 실제 추가 결제의 자기보고. 팀 전체 가격이나 현재 공식 단가가 아니며 예측 입력에 쓰지 않는다.
OBSERVED_PAYMENTS = (
    dict(id="blog05-extra-happy-hour", date="2025-03-09", slot="석식",
         venue="GRAND_CLUB_LOUNGE", l2=None, l3="그랜드 클럽 라운지",
         product="패키지 기준 초과 성인 해피아워 추가", qty=1, unit="성인",
         included_persons=2, charged_persons=1, krw=124000,
         basis="blog05 라운지 절 · 추가 성인 1명 현장 결제 자기보고 · 2026-10-16 직접 대조",
         note="기준 2명의 패키지 값은 이 추가 결제 원장에 재계상하지 않음. 라운지 추가요금의 L2 회계 배부는 미확인"),
    dict(id="blog05-extra-breakfast", date="2025-03-10", slot="조식",
         venue="THE_BUFFET", l2="F&B", l3="더뷔페",
         product="패키지 기준 초과 성인 조식 추가", qty=1, unit="성인",
         included_persons=2, charged_persons=1, krw=65600,
         basis="blog05 조식 절 · 투숙객 할인 후 추가 성인 1명 결제 자기보고 · 2026-10-16 직접 대조",
         note="기준 2명 포함·추가 1명 결제. 현재 조식 정가나 성인 3명 전체 식사값으로 바꾸지 않음"),
)
TRUTH_VISITED = {
    "VISTA_ROOM": "비스타 숙박",
    "VISTA_POOL": "비스타 3층 실내수영장에서 약 1시간 수영",
    "SKYARD": "저녁 약 20:30 및 다음 날 조식 후 약 30분 족욕",
    "THE_BUFFET": "다음 날 2부 조식 이용",
}
# 라운지 이용 자체는 확정. 취합 기록 §4-b의 건물/노드 확인 요청은 미해결이다.
TRUTH_LOCATION_PENDING = {"CLUB_LOUNGE": "해피아워 약 2시간 이용; GRAND_CLUB_LOUNGE 대응은 재확인 필요"}
TRUTH_PASSED = {}
TRUTH_NOT_VISITED = {}  # 언급 없음은 미방문이 아니다.
TRUTH_UNREACHABLE = {}
TRUTH_RESTAURANTS = frozenset({"THE_BUFFET"})  # 확인된 부분집합; 전체 식당 집합의 완전 일치 채점 금지
TRUTH_RESTAURANTS_COMPLETE = False
TRUTH_ORDER_PAIRS = []  # SKYARD가 두 번 등장: 장소 첫 방문만 비교하는 순서 채점으로 축약하지 않는다.
TRUTH_EVENT_ORDER = [("저녁 라운지", "저녁 SKYARD"), ("다음 날 조식", "아침 SKYARD"), ("아침 SKYARD", "퇴실")]
TRUTH_MEALS = [("조식", "THE_BUFFET", "실제 이용 확인; 패키지 기준 2명 포함·추가 성인 1명 별도 결제 (2026-10-16 원문 대조)")]

# 以下 값은 사실 확정이 아닌 실행 정책이다. OBSERVED_PERSONA는 미상을 유지한다.
EXPERIMENT_ASSUMPTIONS = {
    "party_size": (3, "확인된 성인 3명만 모델링; 전체 실제 인원이라고 단정하지 않음"),
    "has_child_under_13": (False, "아동 미상. 이번 시험은 성인만의 조건; 아동 동반 변형은 별도 비교"),
    "included_meals": ((), "사실은 기준 2명 포함·추가 1명 결제. 현재 팀 단위 입력으로 부분 포함/추가 결제를 표현할 수 없어 기존 실행 조건 유지; 3명 전원 포함으로 오인하지 않음. 정확한 과금 반영은 미완료"),
    "room_minimal": (False, "최소 객실 체류 선호 미상: 해당 추가 감점 미적용"),
    "club_access": (False, "사전 예약 자격 미상: 기본 시험에서는 클럽 후보 제외. 자격 있음 변형도 별도 실행"),
}
START_AT = datetime(2025, 3, 9, 15, 0)
START_AT_BASIS = "방문일은 본문, 15:00 도착은 미상 시각을 대신하는 실행 가정"

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
