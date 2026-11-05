"""blog02 후기에서 추출한 더글라스 하우스 투숙객 페르소나.

후기의 직접 진술은 ◎, 후기 맥락에서만 추론한 값은 ○로 표시한다.
성향 점수는 근거 문장이 있는 항목만 채우며, 근거가 없는 항목은 None(미상)이다.
"""

from agent_v0 import Persona


SOURCE = "blog02 후기 (노션 대응표 참조)"


# 후기에서 실제로 확인되는 숙박·이동·이용 사실이다.
FACTS: dict[str, tuple[str, str]] = {
    "숙소": ("더글라스 하우스 디럭스 트윈", "◎ 후기의 객실 소개"),
    "숙박": ("1박", "◎ 마무리에서 1박 동안 라운지를 세 번 이용했다고 정리"),
    "인원": ("4명", "○ 여러 명이어서 라운지의 4인석을 선택했다는 서술"),
    "포함 이용": (
        "더글라스 라운지 라이트 스낵(15–17시)·더글라스 아워(19–21시)·다음 날 조식",
        "◎ 1박으로 라운지를 세 번 이용했다고 한 이용 시간 서술",
    ),
    "이동": (
        "광나루역 무료 셔틀과 호텔 내부 차량 이용",
        "◎ 무료 셔틀 및 내부 차량을 이용한 이동 서술",
    ),
    "수영": (
        "워커힐 수영장 이용",
        "◎ 수영장으로 이동해 이용했고 수모가 필요하다고 한 서술",
    ),
}


# 7개 공통 성향. 점수는 0(낮음)~1(높음)이며, 미상은 None이다.
TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {
    "대기 회피": (
        0.6,
        "◎ 셔틀을 타면 바로 호텔로 갈 수 있어 시간을 아낄 수 있다는 점을 좋게 평가",
    ),
    "이동 최소화": (
        0.9,
        "◎ 호텔 내부 차량이 빨리 준비되고 걷는 거리를 줄일 수 있어 좋았다는 평가",
    ),
    "격식 선호": (None, "근거 문장 없음"),
    "조망 중시": (
        0.9,
        "◎ 테라스를 가장 마음에 든 공간으로 꼽고, 한강·숲 전망과 창가 조식을 강조",
    ),
    "새로움 추구": (None, "근거 문장 없음"),
    "함께 먹기 선호": (
        0.9,
        "◎ 일행과 4인석에 앉아 음식과 술을 즐기며 오래 대화한 이용 서술",
    ),
    "조용함 선호": (
        0.9,
        "◎ 조용하고 힐링되는 더글라스 하우스 분위기를 장점으로 평가",
    ),
}


PERSONA = Persona(
    name="blog02 더글라스 하우스 라운지형 투숙객",
    traits={trait: value for trait, (value, _) in TRAIT_EVIDENCE.items()},
    party_size=4,
    # 어린이 동반 여부를 알 수 있는 문장은 없다. Persona 모델이 bool만 지원하므로
    # 에이전트 실행용 기본값 False를 쓰되, 사실 판단에는 사용하지 않는다.
    has_child_under_13=False,
    nights=1,
    note=(
        "더글라스 하우스 1박. 일행과 전망·조용한 분위기·라운지 이용을 중시한다. "
        "어린이 동반 여부는 후기에서 확인되지 않는다."
    ),
    included_meals=(("조식", "DOUGLAS_LOUNGE"), ("석식", "DOUGLAS_LOUNGE")),
    room_minimal=False,
    # v2 사실 항목 (bk 추가 — 한호 님 확인 필요)
    property="DOUGLAS",      # ◎ 더글라스 하우스
    is_guest=True,
    club_access=True,        # ◎ 더글라스 투숙객은 라운지 이용 포함 (라이트 스낵 · 더글라스 아워 · 조식)
)

# 후기 시작 시각 — blog02.py 의 셔틀 출발 14:24 (토요일 14:40 도착 ◎, 날짜는 실행용 가정)
from datetime import datetime
START_AT = datetime(2024, 6, 15, 14, 24)


# 실제 후기 동선의 정답 데이터. 에이전트의 제안과 비교할 때 사용한다.
TRUTH_VISITED: dict[str, str] = {
    "GWANGNARU_STN": "◎ 광나루역에서 무료 셔틀 탑승",
    "GRAND_FRONT_DESK": "◎ 토요일 14:40경 도착 후 호텔에서 체크인",
    "DOUGLAS_ROOM": "◎ 더글라스 하우스 디럭스 트윈 객실 투숙",
    "DOUGLAS_LOUNGE": "◎ 라이트 스낵·더글라스 아워·다음 날 조식 이용",
    "GRAND_POOL": "◎ 워커힐 수영장 이용",
}

TRUTH_PASSED: dict[str, str] = {
    "HOTEL_GATE": "◎ 셔틀로 워커힐 호텔에 도착",
}

# 후기에 없는 시설을 '미방문'으로 단정하지 않는다.
TRUTH_NOT_VISITED: dict[str, str] = {}
TRUTH_UNREACHABLE: dict[str, str] = {}

TRUTH_RESTAURANTS: dict[str, str] = {}

TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = [
    ("GWANGNARU_STN", "GRAND_FRONT_DESK", "◎ 셔틀 탑승 뒤 호텔 도착·체크인"),
    ("GRAND_FRONT_DESK", "DOUGLAS_ROOM", "◎ 체크인 뒤 더글라스 하우스 객실 투숙"),
    ("DOUGLAS_ROOM", "DOUGLAS_LOUNGE", "◎ 객실 뒤 라이트 스낵 이용"),
    ("DOUGLAS_LOUNGE", "GRAND_POOL", "◎ 라이트 스낵 뒤 수영장 이용"),
    ("GRAND_POOL", "DOUGLAS_LOUNGE", "◎ 수영장 뒤 저녁 더글라스 아워 이용"),
]

TRUTH_MEALS: list[tuple[str, str, str]] = [
    ("간식", "DOUGLAS_LOUNGE", "◎ 15–17시 라이트 스낵"),
    ("석식", "DOUGLAS_LOUNGE", "◎ 19–21시 더글라스 아워"),
    ("조식", "DOUGLAS_LOUNGE", "◎ 다음 날 약 7:30 조식"),
]


def print_persona() -> None:
    print(f"[{PERSONA.name}]")
    for key, (value, evidence) in FACTS.items():
        print(f"- {key}: {value}  ({evidence})")
    print("- 성향:")
    for trait, (value, evidence) in TRAIT_EVIDENCE.items():
        shown = "None(미상)" if value is None else value
        print(f"  - {trait}: {shown}  ({evidence})")
    print("- 실제 방문:", ", ".join(TRUTH_VISITED))


if __name__ == "__main__":
    print_persona()
