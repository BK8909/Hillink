"""
후기 텍스트 → 페르소나 초안 (persona_blogNN_auto.py) — 추출 자동화 시험판

지금까지 페르소나 4편은 사람이 후기를 읽고 손으로 썼다. 과제의 "빌더" 는 이걸 자동으로 하는 것.
이 파일은 그 첫 단계다:  후기 텍스트 → (LLM) → JSON → 검사 → persona_blogNN_auto.py

손으로 만든 페르소나는 버리지 않는다. 자동 추출이 얼마나 맞는지 재는 **정답지**가 된다
(persona_compare.py).

사용
  # 1) LLM 을 바로 부른다 (ANTHROPIC_API_KEY 필요)
  python3 persona_extract.py 원문.txt --blog 1

  # 2) 키가 없으면 프롬프트만 뽑아서 아무 LLM 에 붙여 넣고, 받은 JSON 으로 파일을 만든다
  python3 persona_extract.py 원문.txt --print-prompt > prompt.txt
  python3 persona_extract.py --from-json out.json --blog 1

규칙 (persona_template.py 와 같다)
  - 원문은 저장소 밖. 이 스크립트는 원문을 저장하지 않는다. 결과 파일엔 근거 요약만
  - 동행자·아동 식별 정보 금지 — 나이 · 학년 · 이름은 검사에서 걸러 파일을 안 만든다
  - 이미지 미수집 — 텍스트만 넣는다 (사진 OCR 도 본문 글자만)
"""

from __future__ import annotations

import argparse, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# 장소 코드 — 검증기 노드에서 뽑는다. 이름은 사람이 읽으라고 붙인 것
# ---------------------------------------------------------------------------

PLACE_NAMES = {
    "HOTEL_GATE": "정문", "VALET_DESK": "발렛", "PARKING_TOWER_B1": "주차타워 B1(호텔 연결층)",
    "PARKING_TOWER_4F": "주차타워 4층",
    "GRAND_LOBBY": "그랜드 로비", "GRAND_FRONT_DESK": "그랜드 프런트", "GRAND_ROOM": "그랜드 객실",
    "GRAND_CLUB_LOUNGE": "그랜드 클럽라운지", "LE_PASSAGE": "르파사쥬(베이커리·피자 포장)",
    "GRAND_LIBRARY": "워커힐 라이브러리(그랜드 2층) — 비스타 투숙객도 여기를 쓴다. 비스타에는 따로 없다", "GRAND_POOL": "그랜드 실내수영장(B2)",
    "VISTA_LOBBY": "비스타 로비", "VISTA_ROOM": "비스타 객실", "VISTA_POOL": "비스타 수영장(3F)",
    "THE_BUFFET": "더뷔페", "MOEGI": "모에기(일식)", "SKYARD": "스카이야드(비스타 4F 족욕)",
    "ANNEX": "별관", "PIZZA_HILL": "피자힐", "MYONGWOLGWAN": "명월관(한식 고기)",
    "ONDAL": "온달(한식 코스)", "GEUMRYONG": "금룡(중식)", "THE_PAVILION": "더파빌리온(로비 라운지)",
    "LUX_BAR": "LUX 바", "FITNESS": "그랜드 피트니스 센터(지하 2층) — 그랜드 · 더글라스 투숙객. 비스타 투숙객은 VISTA_FITNESS",
    "VISTA_FITNESS": "비스타 3층 웰니스 클럽 피트니스(비스타 투숙객 전용)",
    "WELLNESS_SAUNA": "웰니스 사우나 — 투숙 건물과 상관없이 사우나는 이 코드 하나 (몇 곳인지 미확정)",
    "FOREST_PARK": "포레스트파크", "RIVERPARK": "리버파크(야외 수영장, 여름)", "GOLF_CLUB": "골프",
    "TENNEZ_PARK": "테니스", "CONVENTION": "컨벤션·웨딩홀",
    "THEATRE_OF_LIGHT": "빛의 시어터", "THEATRE_ART_SHOP": "빛의 시어터 아트샵", "CU_THEATRE": "지하 CU 편의점",
    "DOUGLAS_LOBBY": "더글라스 로비", "DOUGLAS_LOUNGE": "더글라스 라운지", "DOUGLAS_LIBRARY": "더글라스 라이브러리",
    "DOUGLAS_ROOM": "더글라스 객실",
    "GWANGNARU_STN": "광나루역", "GANGBYEON_STN": "강변역", "ICN_T1": "인천공항 T1", "ICN_T2": "인천공항 T2",
}


def place_codes() -> set[str]:
    try:
        sys.path.insert(0, str(HERE))
        import walkerhill_timeline_validator as v
        codes = set(v._INTERNAL_GRAPH)
        for a, b in v.WALKERHILL_EXTERNAL_LEGS:
            codes |= {a, b}
        return codes
    except Exception:
        return set(PLACE_NAMES)


RESTAURANTS = ["ONDAL", "GEUMRYONG", "MYONGWOLGWAN", "MOEGI", "PIZZA_HILL", "THE_BUFFET"]
MEAL_KINDS = ["조식", "중식", "석식", "간식"]

# ---------------------------------------------------------------------------
# 성향 7개 — 에이전트 점수 함수(agent_v1.score)가 실제로 어떻게 쓰는지에 맞춰 정의한다.
# 정의가 점수 함수와 어긋나면, 사람이 잘 뽑아도 에이전트는 엉뚱하게 움직인다.
# ---------------------------------------------------------------------------

TRAITS = {
    "대기 회피": ("줄·웨이팅을 얼마나 싫어하나. 에이전트는 대기 30분마다 이 값만큼 감점한다",
               "0.25 대기를 긍정적으로 적거나 대기 중 다른 걸 함 · 0.5 담담히 기다림 · 0.75 줄 보고 포기/예약으로 피함/불만 · 1.0 대기 때문에 선택을 두 번 이상 바꿈"),
    "이동 최소화": ("이동 거리를 얼마나 싫어하나. 이동 20분마다 이 값만큼 감점",
                "0.25 먼 곳도 일부러 감 · 0.5 보통 · 0.75 가까운 곳만/'동선' 을 이유로 선택을 바꿈 · 1.0 이동이 싫어 계획을 여러 번 바꿈"),
    "격식 선호": ("코스·정찬 같은 격식 있는 식당 선호. 0.5 기준 위면 정찬 가점, 아래면 캐주얼 가점",
               "0.25 포장·캐주얼을 골라서 감 · 0.5 섞임 · 0.75 코스·파인다이닝을 골라서 감 · 1.0 정찬을 목적으로 방문"),
    "조망 중시": ("뷰가 좋은 곳에 가점",
               "0.25 뷰가 선택 기준이 아님을 스스로 말함 · 0.5 좋았다 정도 · 0.75 뷰 때문에 고름 · 1.0 뷰 때문에 돈을 더 냄/객실을 바꿈"),
    "새로움 추구": ("안 가 본 곳에 가점, 간 곳 재방문 감점",
                "0.25 목적지 하나만 · 0.5 보통 · 0.75 안 가 본 곳을 일부러 찾아감 · 1.0 '다 해 보려고' 라고 스스로 밝힘"),
    "함께 먹기 선호": ("일행이 함께 먹는 식사에 가점",
                  "0.75 일행과 같이 먹으려고 선택을 바꾼 문장이 있을 때 · 같이 먹었다는 사실만으로는 null"),
    "조용함 선호": ("조용한 곳 가점, 붐비는 곳 감점",
                "0.25 북적임을 즐김 · 0.5 무관 · 0.75 한적함을 이유로 고르거나 붐빔을 피함 · 1.0 붐벼서 계획을 바꿈. 공간 묘사만 있으면 null"),
}

SCHEMA = r"""{
  "name": "blogNN · 한 줄 요약 (예: 그랜드 1박 · 커플)",
  "start_date": "YYYY-MM-DD 또는 null (방문 날짜가 적혀 있을 때만)",
  "start_time": "HH:MM (도착 · 체크인 · 첫 이용 시각)",
  "start_time_source": "◎(후기에 적힘) 또는 △(추정)",
  "facts": {
    "property": "GRAND | VISTA | DOUGLAS",
    "is_guest": true,
    "nights": 1,
    "party_size": 2,
    "has_child_under_13": false,
    "club_access": false,
    "included_meals": [["조식", "THE_BUFFET"]],
    "booked": [],
    "arrival": "car_valet | car_self | null",
    "room_minimal": false,
    "depart_by": "HH:MM 또는 null (비투숙일 때만)",
    "evidence": {"property": "근거 요약", "nights": "...", "party": "...", "included_meals": "...", "room_minimal": "..."}
  },
  "traits": {
    "대기 회피": {"value": 0.5, "evidence": "근거 문장 요약 · 없으면 '근거 없음 → 미상'"},
    "...": "성향 7개 전부"
  },
  "truth": {
    "visited":     {"PLACE_CODE": "◎ 근거"},
    "passed":      {"PLACE_CODE": "구경만/지나감 근거"},
    "not_visited": {"PLACE_CODE": "◎ 안 갔다고 적힌 근거  또는  ○ 언급 없음"},
    "unreachable": {"한글 이름": "이용했는데 장소 코드 목록에 없는 곳"},
    "restaurants": ["PIZZA_HILL"],
    "order_pairs": [["먼저_CODE", "나중_CODE", "◎ 근거"]],
    "meals":       [["석식", "PIZZA_HILL", "◎ 근거"]]
  }
}"""


def build_prompt(text: str, postdate: str | None = None) -> str:
    codes = sorted(place_codes())
    place_lines = "\n".join(f"  {c:18s} {PLACE_NAMES.get(c, '')}" for c in codes)
    trait_lines = "\n".join(f"  - {k}: {d}\n      눈금: {a}" for k, (d, a) in TRAITS.items())
    post_line = (f"## 글 작성일: {_iso(postdate)}\n"
                 "방문은 이 날이나 그 전이다. 본문 날짜가 '8/31' 처럼 연도 없이 적혔을 때 연도를 정하는 데만 쓴다.\n"
                 "본문에 방문 날짜가 없으면 start_date 는 null — 이 작성일을 start_date 에 옮겨 적지 않는다.\n\n"
                 if postdate else "")
    return f"""너는 호텔 투숙 후기에서 시뮬레이션용 페르소나를 뽑는 분석가다.
아래 워커힐 호텔 후기 하나를 읽고, 정해진 JSON 하나만 출력한다. 설명 문장 없이 JSON 만.

## 원칙 — 반드시 지킨다
1. 성향 값에는 반드시 근거를 붙인다. 근거는 후기 속 **행동이나 스스로 밝힌 선호**여야 한다.
   가족 구성·나이·직업 같은 인구 정보로 성향을 짐작하지 않는다.
   근거가 없으면 value 를 null 로 둔다. null(미상)은 0 이 아니다. 지어내느니 null 이 낫다.
   **시설을 이용했다는 사실만으로 점수를 주지 않는다.** "왜 골랐나 / 왜 포기했나" 가 문장으로 확인될 때만 값을 준다.
   (수영장에 갔다 → 새로움 추구 아님. "다 해 보려고 수영장까지 갔다" → 새로움 추구 0.75)
   값은 null · 0.25 · 0.5 · 0.75 · 1.0 다섯 가지만 쓴다. 근거는 ◎ 또는 ○ 로 시작한다.
2. 사실(facts)은 성향이 아니라 예약 시점에 정해진 것이다 — 숙박 건물, 박 수, 인원, 13세 미만 동반 여부,
   패키지에 포함된 끼니(included_meals), 클럽 객실 여부, 미리 예약한 곳(booked — 시설 입장권 · 식당 예약 모두, 장소 코드로),
   도착 수단(arrival — 자차 발렛 "car_valet" · 자차 직접 주차 "car_self" · 그 밖이나 모르면 null).
   included_meals 는 "포함" 이라고 적힌 것만. 그냥 먹은 것은 truth.meals 로.
   - 더글라스 하우스 투숙은 라운지(라이트 스낵 · 더글라스 아워 · 조식)가 숙박에 포함된다 → club_access true,
     조식 · 석식을 DOUGLAS_LOUNGE 로 included_meals 에. 그랜드 클럽 객실도 club_access true.
   - **클럽 객실 · 더글라스의 라운지 티타임 · 해피아워 · 조식은 숙박에 따라오는 것** — "포함" 낱말이 없어도
     후기가 이용했다고 적었으면 included_meals 에 넣는다 (간식 · 석식 → *_CLUB_LOUNGE / DOUGLAS_LOUNGE, 평일 조식은 THE_BUFFET).
     반대로 "조식 추가" · "할인가로 결제" · "투숙객 할인" 처럼 **따로 낸** 끼니는 포함이 아니다 (meals 에만).
   - 비투숙(식당 · 시설만 이용)이면 is_guest false, nights 0, depart_by 는 떠난 시각 (모르면 이용 끝 무렵으로 추정 △).
   - 날짜와 시각은 따로 적는다. **날짜가 없어도 시각이 적혀 있으면 그 시각을 쓴다(◎).**
     start_date: 방문 날짜가 적혀 있을 때만, 없으면 null (글 작성일로 채우는 건 코드가 한다).
     start_time: 후기가 적은 도착 · 체크인 · 첫 이용 시각 중 가장 이른 것(◎). "체크인은 15시부터" 같은 운영 안내 시각은 아니다.
     시각이 전혀 없으면 투숙은 14:30(△), 비투숙은 이용 시작 30분 전(△).
3. 개인정보 금지: 동행자·아동의 **나이, 학년, 이름, 생일**, 블로그 아이디, URL, 가격 외 식별 정보를 어디에도 쓰지 않는다.
   아동은 has_child_under_13 true/false 로만. 근거 문장에도 아들·딸·남편 같은 관계어 대신 '아이' · '동행자' 로 쓴다.
4. 정답(truth)은 후기가 **이용을 못 박은 곳만** visited 에.
   visited 의 근거는 반드시 "◎" 또는 "○" 로 시작하고, **이용한 문장**을 요약한다.
   부대시설 소개 · 운영 시간 안내 · 추천 · "다음엔 가 보고 싶다" 는 visited 가 아니다 — 가장 흔한 실수다.
   passed 는 **몸이 실제로 거쳐 간 곳만** — 로비 · 정문 · 주차장을 지나감, 가 봤는데 붐벼서 돌아섬, 외관만 봄.
   프런트(*_FRONT_DESK)는 "체크인했다" · "키를 받았다" 한 줄뿐이면 passed 다 — 누구나 하는 절차라 정보가 없다.
   줄 서서 기다림 · 얼리 체크인 요청 · 문의하고 안내받음처럼 **그 자리에서 일어난 일**이 적혔을 때만 visited.
   (정답 확인에서 사람이 지운 자동 방문지의 대부분이 이 프런트다)
   글에서 **소개 · 언급만 하고 가지 않은 곳은 passed 가 아니라 not_visited** 에 "○ 언급만 — <무엇>" 으로.
   (채점에서 passed 는 에이전트가 가도 감점하지 않는 칸이라, 언급만 한 곳을 넣으면 점수가 느슨해진다)
   not_visited 는 후기가 안 갔다 · 못 갔다 · 포기했다고 적은 곳이면 "◎ …", 언급만이면 "○ 언급만 …", 언급이 없으면 "○ 언급 없음".
   장소는 반드시 아래 코드로. 목록에 없는 곳을 이용했으면 unreachable 에 한글 이름으로.
5. restaurants 는 visited 중 다음 식당만: {", ".join(RESTAURANTS)}
6. order_pairs 는 후기에서 순서가 확정되는 두 장소 쌍만 — **각 장소에 처음 간 순서** 기준 (시각이 아니라 앞뒤).
   객실 → 수영장 → 다시 객실이면 (객실, 수영장) 이다. 짐작이면 근거를 "○" 로 시작.
   **넣지 않는 쌍** (정답 확인에서 사람이 지운 쌍의 대부분이 이것이다):
   - 체크인 절차 안쪽끼리(정문 · 주차 · 로비 · 프런트 · 객실 입실) — 프런트→객실, 로비→객실, 주차→로비는 뻔해서 정보가 없다
   - 머문 곳이 아닌 곳(지나감 · 역 · 정문)이 한쪽인 쌍
   - 사진이 그 순서로 붙어 있을 뿐인 것, "아마 그랬겠지" — 원문에 "~하고 나서" · "다음 날" · "저녁에" 처럼 앞뒤가 적힌 쌍만
   쌍은 식당 · 객실 · 수영장 · 라운지 · 전시처럼 **머문 곳끼리만**. 같은 곳을 두 번 갔으면 처음 간 순서.
7. meals 는 호텔 안에서 먹은 끼니 (끼니: {", ".join(MEAL_KINDS)}). 라운지 식사·포장도 포함. 룸서비스·외부 음식은 제외.
   장소 코드 목록에 없는 곳(예: 전시 연계 카페)에서 먹었으면 meals 에 넣지 않고 unreachable 에만 적는다.
8. 근거 표시: ◎ 후기에 명시 · ○ 후기에서 강하게 추론 · △ 추정.
9. 한 후기에 방문(체류)이 둘 이상이면 이용 장소가 가장 많은 체류 하나만 다룬다. name 에 어느 체류인지 적는다.

## 성향 7개 — 에이전트가 이 값으로 다음 행동의 점수를 매긴다 (0.0~1.0)
{trait_lines}

## 장소 코드
{place_lines}

## 출력 JSON 형식
{SCHEMA}

{post_line}## 후기 본문 (OCR 이라 오탈자가 있다. 문맥으로 읽는다)
<<<
{text}
>>>
"""


# ---------------------------------------------------------------------------
# 검사 — 형식 · 코드 · 개인정보. 걸리면 파일을 만들지 않는다
# ---------------------------------------------------------------------------

TRAIT_SCALE = {0.25, 0.5, 0.75, 1.0}          # 슬기 기준 (9/28) — None 은 미상
MAX_VISITED = 15                              # 사람이 확인한 체류 17개의 최대 방문지 수가 8 (blog01)
# "안내 · 추천" 은 실제 이용 문장에도 나온다 ("직원이 안내해 줌 · 족욕 추천") — "~만" 일 때만 약한 근거로 본다
WEAK_VISIT = re.compile(r"언급\s*(만|없음)|(소개|안내|추천|사진)\s*만|가\s*보고\s*싶|다음\s*(엔|에는|기회)|예정|(못|안)\s*(갔|감|가)")

PRIVACY_PATTERNS = [
    # "13세 미만" 은 사실 칸의 이름(has_child_under_13)이라 허용. 그 밖의 숫자+세/살/개월은 전부 나이로 본다
    (re.compile(r"(?<!\d)(?!13\s*세\s*미만)\d+\s*(세|살|개월)"), "나이"),
    (re.compile(r"(초등|중학|고등|유치원|어린이집)\s*\d*\s*(학년|생|반)?"), "학년·기관"),
    (re.compile(r"https?://|blog\.naver|tistory\.com|@\w+"), "URL·계정"),
    (re.compile(r"생일"), "생일"),
]


# 가족 관계어 · 나이대 표현은 동행자 정보라 결과물에 두지 않는다 — 검사 전에 일반어로 바꾼다.
# (blog01 첫 추출에서 '아들·딸' · '미취학' 이 근거 문장에 그대로 들어왔다. 검사가 나이 숫자만 봐서 못 잡았음)
REDACT = [
    (re.compile(r"(우리\s*)?(아들|딸)이(?=\s|$|[^가-힣])"), "아이가"),
    (re.compile(r"(우리\s*)?(아들|딸)이"), "아이가"),
    (re.compile(r"우리\s*(아들|딸)|아들|딸(?!기)"), "아이"),
    (re.compile(r"미취학\s*\d*|초딩|유딩|영유아|신생아|영아|아기|아가(?!씨)"), "아이"),  # 영아 · 아가 — blog20 (9/24)
    (re.compile(r"신랑|남편|아내|와이프|엄마|아빠|시어머니|장모"), "동행자"),
]


def sanitize(data: dict) -> tuple[dict, int]:
    blob = json.dumps(data, ensure_ascii=False)
    n = 0
    for pat, rep in REDACT:
        blob, k = pat.subn(rep, blob)
        n += k
    return json.loads(blob), n


def normalize(data: dict) -> tuple[dict, list[str]]:
    """사람 판단이 필요 없는 형식 정리만. 장소 코드가 아닌 곳의 끼니 → unreachable 로 옮김 (blog20, 9/28)."""
    notes: list[str] = []
    tr = data.get("truth", {})
    codes = place_codes()
    keep = []
    for m in tr.get("meals", []) or []:
        if len(m) >= 2 and m[1] not in codes:
            tr.setdefault("unreachable", {}).setdefault(str(m[1]), f"{m[0]} 식사 — 장소 코드 목록에 없음")
            notes.append(f"끼니 {m[0]}@{m[1]} → unreachable (장소 코드 아님)")
        else:
            keep.append(m)
    if "meals" in tr:
        tr["meals"] = keep
    return data, notes


def check(data: dict) -> list[str]:
    issues: list[str] = []
    codes = place_codes()
    for key in ("name", "facts", "traits", "truth"):
        if key not in data:
            issues.append(f"형식: '{key}' 없음")
    if issues:
        return issues
    f = data["facts"]
    if f.get("property") not in ("GRAND", "VISTA", "DOUGLAS"):
        issues.append(f"사실: property={f.get('property')!r}")
    ev = f.get("evidence", {}) or {}
    for k in ("property", "nights", "party"):
        if not str(ev.get(k, "")).strip():
            issues.append(f"사실: {k} 근거 없음 — 원문 문장을 요약해 붙인다")
    for k in TRAITS:
        t = data["traits"].get(k)
        if t is None:
            issues.append(f"성향: '{k}' 빠짐"); continue
        v = t.get("value")
        if v is not None and float(v) not in TRAIT_SCALE:
            issues.append(f"성향: {k}={v} — 눈금은 null · 0.25 · 0.5 · 0.75 · 1.0")
        if v is not None and not str(t.get("evidence", "")).lstrip().startswith(("◎", "○")):
            issues.append(f"성향: {k}={v} 인데 근거가 ◎/○ 가 아님 — 이유 문장이 없으면 null")
        if not str(t.get("evidence", "")).strip():
            issues.append(f"성향: {k} 근거 없음")
    tr = data["truth"]
    # 방문지 — 근거 없는 방문지는 막는다 (blog02 자동 추출이 언급만 한 곳까지 넣어 30곳이 됨, 9/28)
    visited = tr.get("visited", {}) or {}
    for c, why in visited.items():
        w = str(why).strip()
        if not w.startswith(("◎", "○")):
            issues.append(f"방문: {c} 근거가 ◎/○ 로 시작하지 않음 ({w[:30]!r})")
        elif WEAK_VISIT.search(w):
            issues.append(f"방문: {c} 근거가 이용이 아니라 언급 · 소개로 보임 ({w[:40]!r}) → passed 나 삭제")
    if len(visited) > MAX_VISITED:
        issues.append(f"방문: {len(visited)}곳 — {MAX_VISITED}곳이 넘으면 언급만 한 곳이 섞였는지 사람이 먼저 본다")
    both = set(visited) & {c for c, w in (tr.get("not_visited", {}) or {}).items()}
    if both:
        issues.append(f"방문: {sorted(both)} 가 visited 와 not_visited 에 동시에 있음")
    for section in ("visited", "passed", "not_visited"):
        for c in tr.get(section, {}):
            if c not in codes:
                issues.append(f"정답: {section} 의 '{c}' 는 장소 코드가 아님 (unreachable 로?)")
    for a, b, *_ in tr.get("order_pairs", []):
        for c in (a, b):
            if c not in codes:
                issues.append(f"순서: '{c}' 는 장소 코드가 아님")
    for k, p, *_ in tr.get("meals", []) + [list(x) + [""] for x in f.get("included_meals", [])]:
        if k not in MEAL_KINDS:
            issues.append(f"끼니: '{k}'")
        if p not in codes:
            issues.append(f"끼니: 장소 '{p}' 는 코드가 아님")
    blob = json.dumps(data, ensure_ascii=False)
    for pat, what in PRIVACY_PATTERNS:
        m = pat.search(blob)
        if m:
            issues.append(f"개인정보({what}): '…{blob[max(0, m.start()-15):m.end()+10]}…'")
    return issues


TIME_RE = re.compile(r"(?<![\d:])([01]?\d|2[0-3])\s*(?::\s*([0-5]\d)|시(?:\s*([0-5]?\d)\s*분|\s*반)?)")
ARRIVE_RE = re.compile(r"도착|체크\s*인|입실|들어갔|왔|출발")
NOTICE_RE = re.compile(r"부터|이후|가능|까지|운영|오픈|마감")


def stated_times(text: str, window: int = 25) -> list[str]:
    """도착 · 체크인 근처에 적힌 시각 (운영 안내 '15시부터' 류는 뺀다). 추출이 △ 로 둔 걸 사람에게 알리는 용도"""
    out = []
    for m in TIME_RE.finditer(text):
        around = text[max(0, m.start() - window): m.end() + window]
        after = text[m.end(): m.end() + 6]
        if ARRIVE_RE.search(around) and not NOTICE_RE.search(after):
            out.append(around.replace("\n", " "))
    return out


# ---------------------------------------------------------------------------
# 파일 만들기
# ---------------------------------------------------------------------------

def _iso(d: str | None) -> str | None:
    """20260830 · 2026-08-30 → 2026-08-30"""
    if not d:
        return None
    d = re.sub(r"\D", "", str(d))
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None


NONGUEST_START = {"조식": "07:30", "중식": "11:30", "석식": "17:30"}   # 끼니 시작 30분 전 무렵 (△)


def default_start_time(data: dict) -> str:
    """시각이 후기에 없을 때. 투숙은 14:30 체크인 무렵.
    비투숙은 첫 끼니 30분 전 — 예전엔 비투숙도 14:30 이 돼서 런치 후기(blog22)가
    런치가 끝난 뒤에 도착하는 꼴이 됐다 (한호 지적). 끼니가 없으면 11:00."""
    if data.get("facts", {}).get("is_guest", True):
        return "14:30"
    meals = [m[0] for m in data.get("truth", {}).get("meals", []) if m and m[0] in NONGUEST_START]
    order = list(NONGUEST_START)
    return NONGUEST_START[min(meals, key=order.index)] if meals else "11:00"


def start_at_line(data: dict, postdate: str | None = None) -> str:
    """START_AT 한 줄. 날짜와 시각을 따로 정한다 (9/28 정답 확인에서 나온 것).

    - 시각: 후기에 적힌 시각(◎)이 있으면 날짜가 없어도 그것. 없으면 투숙 14:30 · 비투숙은 첫 끼니 30분 전(△)
      (예전 스키마 start_at 은 날짜가 없으면 null 이 돼서 적힌 시각까지 버려졌다 — blog16 14:20)
    - 날짜: 후기에 적힌 날짜 → 글 작성일(--postdate) → 2025-01-01 순.
      2025-01-01 로 두면 계절 운영 시설(리버파크 · 야외 수영장)이 닫힌 날로 돌아간다 (소연 지적)
    """
    date = data.get("start_date")
    tm, t_src = data.get("start_time"), data.get("start_time_source", "△")
    old = data.get("start_at")                       # 예전 스키마 JSON 도 읽는다
    if old and not date:
        date = old[:10]
    if old and not tm and len(old) >= 16:
        tm, t_src = old[11:16], data.get("start_at_source", "△")
    if date:
        d_note = "날짜 ◎ 후기"
    elif _iso(postdate):
        date, d_note = _iso(postdate), "날짜 △ 글 작성일"
    else:
        date, d_note = "2025-01-01", "날짜 △ 후기·작성일 없음"
    if not tm:
        tm, t_src = default_start_time(data), "△"
    t_note = "시각 ◎ 후기" if str(t_src).startswith("◎") else "시각 △ 추정"
    y, mo, d = map(int, date[:10].split("-"))
    hh, mm = map(int, tm[:5].split(":"))
    return f"START_AT = datetime({y}, {mo}, {d}, {hh}, {mm})      # {d_note} · {t_note}"


def render(data: dict, blog: int, source_note: str, postdate: str | None = None) -> str:
    f, t, tr = data["facts"], data["traits"], data["truth"]
    ev = f.get("evidence", {})
    start_line = start_at_line(data, postdate)
    depart = f.get("depart_by")
    depart_expr = f"time({int(depart[:2])}, {int(depart[3:5])})" if depart else "time(20, 0)"

    def d(x):
        return json.dumps(x, ensure_ascii=False, indent=4).replace("\n", "\n")

    trait_lines = "\n".join(
        f"    {k!r}: ({t[k].get('value')!r}, {str(t[k].get('evidence', '')).strip()!r})," for k in TRAITS)
    return f'''"""
blog{blog:02d} — 자동 추출 페르소나 초안 (persona_extract.py 가 만듦 · 사람이 아직 안 고침)

{source_note}
손으로 만든 persona_blog{blog:02d}.py 가 있으면 그게 정답지다 — 비교는 persona_compare.py {blog}
run_all.py 는 이 파일을 읽지 않는다 (이름 끝 _auto).
"""

from __future__ import annotations

from datetime import datetime, time
from agent_v0 import Persona

{start_line}

FACTS_EVIDENCE = {d(ev)}

TRAIT_EVIDENCE: dict[str, tuple[float | None, str]] = {{
{trait_lines}
}}

PERSONA = Persona(
    name={("[자동] " + data["name"])!r},
    traits={{k: v for k, (v, _) in TRAIT_EVIDENCE.items()}},
    party_size={int(f.get("party_size") or 2)!r},
    has_child_under_13={bool(f.get("has_child_under_13"))!r},
    nights={int(f.get("nights") or 0)!r},
    property={f["property"]!r},
    is_guest={bool(f.get("is_guest", True))!r},
    club_access={bool(f.get("club_access"))!r},
    depart_by={depart_expr},
    included_meals={tuple(tuple(x) for x in f.get("included_meals", []))!r},
    booked={tuple(f.get("booked", []))!r},
    arrival={f.get("arrival") if f.get("arrival") in ("car_valet", "car_self") else None!r},
    room_minimal={bool(f.get("room_minimal"))!r},
    note="자동 추출 · 미상 {sum(1 for k in TRAITS if t[k].get('value') is None)}개",
)

TRUTH_VISITED: dict[str, str] = {d(tr.get("visited", {}))}
TRUTH_PASSED: dict[str, str] = {d(tr.get("passed", {}))}
TRUTH_NOT_VISITED: dict[str, str] = {d(tr.get("not_visited", {}))}
TRUTH_UNREACHABLE: dict[str, str] = {d(tr.get("unreachable", {}))}
TRUTH_RESTAURANTS: frozenset[str] = frozenset({sorted(tr.get("restaurants", []))!r})
TRUTH_ORDER_PAIRS: list[tuple[str, str, str]] = {[tuple(x) for x in tr.get("order_pairs", [])]!r}
TRUTH_MEALS: list[tuple[str, str, str]] = {[tuple(x) for x in tr.get("meals", [])]!r}
'''


def call_llm(prompt: str) -> str:
    """ANTHROPIC_API_KEY 가 있으면 Claude 를 부른다. 없으면 --print-prompt 경로를 안내."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY 없음 → --print-prompt 로 프롬프트를 뽑아 LLM 에 붙이고, 받은 JSON 을 --from-json 으로")
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(model=os.environ.get("EXTRACT_MODEL", "claude-sonnet-4-5"),
                                 max_tokens=8000, messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def parse_json(s: str) -> dict:
    s = s.strip()
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        raise ValueError("JSON 을 못 찾음")
    return json.loads(m.group(0))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="?", help="후기 텍스트 파일 (저장소 밖에 둘 것)")
    ap.add_argument("--blog", type=int)
    ap.add_argument("--print-prompt", action="store_true")
    ap.add_argument("--from-json")
    ap.add_argument("--note", default="추출 경로: 후기 PDF → OCR 텍스트 → LLM → JSON")
    ap.add_argument("--postdate", help="글 작성일 YYYYMMDD — 후기에 날짜가 없을 때 START_AT 날짜 (queue.csv · export_map.csv 의 postdate)")
    a = ap.parse_args()

    if a.print_prompt:
        print(build_prompt(Path(a.text).read_text(encoding="utf-8"), a.postdate)); return
    if a.from_json:
        data = json.loads(Path(a.from_json).read_text(encoding="utf-8"))
    else:
        data = parse_json(call_llm(build_prompt(Path(a.text).read_text(encoding="utf-8"), a.postdate)))

    data, n_red = sanitize(data)
    data, moved = normalize(data)
    for m in moved:
        print("정리:", m)
    if n_red:
        print(f"동행자 표현 {n_red}곳을 일반어(아이 · 동행자)로 바꿈")
    issues = check(data)
    if issues:
        print("검사에서 걸림 — 파일을 만들지 않는다:")
        for i in issues:
            print("  ·", i)
        sys.exit(1)
    if not a.blog:
        sys.exit("--blog 번호 필요")
    out = HERE / f"persona_blog{a.blog:02d}_auto.py"
    out.write_text(render(data, a.blog, a.note, a.postdate), encoding="utf-8")
    print(f"검사 통과 → {out.name}")
    print("  ", start_at_line(data, a.postdate))
    if a.text and not str(data.get("start_time_source", data.get("start_at_source", ""))).startswith("◎"):
        hits = stated_times(Path(a.text).read_text(encoding="utf-8"))
        if hits:
            print("  확인: 시각을 추정(△)했는데 본문에 시각이 있다 — START_AT 을 원문과 대조")
            for h in hits[:3]:
                print("     …" + h + "…")


if __name__ == "__main__":
    main()
