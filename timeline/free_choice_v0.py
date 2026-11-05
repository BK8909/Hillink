"""자유 선택 Gold v0 (10/16) — 기존 후기 59 체류의 검수 요약에서 '선택 · 변경 · 비이용' 단서를 다시 뽑은 초안.

출처: persona_blogNN.py 의 FACTS · TRAIT_EVIDENCE · TRUTH_* 요약. 일부 후보는 2026-10-16 원문을 직접 대조했다 (docs/Gold_체류시간_추가원문검수_20261016.md).
직접 대조 여부는 사례별 evidence·certainty로 구분한다. 요약만 있는 후보를 원문 검수 완료로 보지 않으며, 이 초안 전체를 독립 평가 세트로 쓰지 않는다. 채우지 못한 칸은 None 으로 둔다 (임의로 채우지 않음).
동행자 · 아동 정보는 넣지 않는다. 사람 이름 · URL · 닉네임 없음.

자유 선택 정의 (리뷰 10/16):
  · 포함 혜택 · 사전 예약으로 정해진 식사는 제외
  · 예약이 없다고 자유 선택은 아니다 (방문 전에 정했을 수 있음) → '방문만 확인' 은 자유 선택 정답이 아님
  · 고민 · 비교 · 계획 변경 · 대기 후 이동 · 비이용(밖 · 배달 · 생략)이 드러나야 함
평가 수준 (level):
  venue      업장 수준 대체 선택 — 원래 업장과 최종 업장이 모두 확인
  nonuse     호텔 식당 비이용 선택 — 호텔 밖 · 배달 · 생략 (최종 업장 정답 아님)
  form       같은 업장 안 이용 형태 — 매장 ↔ 포장
  time       같은 업장 회차 · 시각 선택 — 대기를 시각으로 피함
  wait_stay  대기 감수 — 대기 후에도 같은 업장 유지
  plan       계획 변경 확인 · 최종은 포함 혜택 등으로 귀결 (업장 정답으로 쓰지 않음)
  exclude    단서는 있으나 포함 혜택 · 예약으로 정해진 선택
"""

FIELDS = ("id", "stay", "guest", "situation", "booked", "included", "prior_plan", "condition", "observed",
          "alternatives", "evidence", "certainty", "level", "scope")

CASES = [
    dict(id="F01", stay="blog43", guest="투숙", situation="조식 장소", booked="없음", included="더글라스 라운지 조식",
         prior_plan="더뷔페 조식 (추가 요금)", condition="9시 넘어 대기가 길다고 적음", observed="더뷔페 포기 후 더글라스 라운지 조식",
         alternatives=["더뷔페 조식", "더글라스 라운지 조식"], evidence="TRUTH_NOT_VISITED · TRUTH_MEALS ◎", certainty="명시 (요약)",
         level="venue", scope="원래 업장 · 최종 업장 · 영향 조건 모두 확인"),
    dict(id="F02", stay="blog06", guest="투숙", situation="석식 장소 · 형태", booked="없음", included="없음",
         prior_plan="피자힐", condition="앞에 11팀 · 예상 60~90분 안내", observed="피자힐 포장 후 객실 식사",
         alternatives=["피자힐 매장 (대기)", "피자힐 포장"], evidence="TRAIT_EVIDENCE 대기 회피 (검수 요약)", certainty="명시 (요약)",
         level="form", scope="같은 업장 안 매장 ↔ 포장 선택 · 다른 업장 비교 근거 없음"),
    dict(id="F03", stay="blog19", guest="투숙", situation="석식 형태", booked="없음", included="없음",
         prior_plan=None, condition=None, observed="피자힐 매장 대신 포장해 숙소로",
         alternatives=["피자힐 매장", "피자힐 포장"], evidence="TRAIT_EVIDENCE 격식 선호 ◎", certainty="명시 (요약) · 이유 불명",
         level="form", scope="형태 선택만 확인 · 이유 미기재"),
    dict(id="F04", stay="blog61", guest="투숙", situation="석식 장소", booked="없음", included="없음",
         prior_plan=None, condition=None, observed="피자힐을 고민했지만 초밥 · 회 배달, 부족해 편의점 컵라면",
         alternatives=["피자힐", "배달"], evidence="TRUTH_NOT_VISITED ◎ ('피자힐을 먹을까도 고민했지만')", certainty="명시 (요약)",
         level="nonuse", scope="고민한 대안과 비이용 선택 확인 · 이유는 미기재"),
    dict(id="F05", stay="blog21", guest="투숙", situation="조식", booked="없음", included="없음",
         prior_plan="조식 뷔페", condition="다음날 일정이 빡빡하다는 조언", observed="조식 뷔페 취소",
         alternatives=["조식 뷔페"], evidence="TRUTH_NOT_VISITED ◎", certainty="명시 (요약)",
         level="nonuse", scope="계획 포기 확인 · 대신 무엇을 했는지 불명"),
    dict(id="F06", stay="blog35", guest="투숙", situation="식사 (끼니 미상)", booked="없음", included="없음",
         prior_plan=None, condition="룸서비스가 비싸다는 언급", observed="룸서비스 대신 호텔 밖 캐주얼 식당까지 걸어감",
         alternatives=["룸서비스", "호텔 밖 식당"], evidence="TRAIT_EVIDENCE 격식 선호 · 이동 ○", certainty="간접 (요약)",
         level="nonuse", scope="비이용 선택과 비교 대안 확인 · 끼니 미상"),
    dict(id="F07", stay="blog39", guest="투숙", situation="석식", booked="없음", included="없음",
         prior_plan=None, condition=None, observed="호텔 식당 대신 근처에서 산 와인과 배달 음식",
         alternatives=None, evidence="TRAIT_EVIDENCE 격식 선호 ○", certainty="간접 (요약)",
         level="nonuse", scope="비이용 선택만 · 비교한 호텔 식당 불명"),
    dict(id="F08", stay="blog23", guest="투숙", situation="석식", booked="없음", included="클럽라운지 석식",
         prior_plan="호텔 밖 식사", condition="라운지 만족", observed="밖 식사 계획을 접고 클럽라운지 해피아워",
         alternatives=["호텔 밖 식사", "클럽라운지"], evidence="TRAIT_EVIDENCE 이동 최소화 ○", certainty="간접 (요약)",
         level="plan", scope="계획 변경 확인 · 최종은 포함 혜택이라 업장 정답으로 쓰지 않음"),
    dict(id="F09", stay="blog28", guest="투숙", situation="조식 장소", booked="없음", included="클럽라운지 조식",
         prior_plan=None, condition="성수기", observed="1층 조식당 대신 클럽라운지 조식",
         alternatives=["더뷔페 조식", "클럽라운지 조식"], evidence="TRUTH_NOT_VISITED ○", certainty="간접 (요약)",
         level="plan", scope="혼잡 회피 언급 · 최종은 포함 혜택"),
    dict(id="F10", stay="blog30", guest="투숙", situation="조식 회차", booked="없음", included="없음",
         prior_plan=None, condition="2부 웨이팅이 길다고 들음", observed="1부 오픈런",
         alternatives=["조식 1부", "조식 2부"], evidence="TRAIT_EVIDENCE 대기 회피 ◎", certainty="명시 (요약)",
         level="time", scope="같은 업장 회차 선택"),
    dict(id="F11", stay="blog05", guest="투숙", situation="조식 회차 · 도착 시각", booked="없음", included="더뷔페 조식 패키지 기준 2명 포함 · 추가 성인 1명 별도 결제",
         prior_plan=None, condition="다른 후기의 긴 대기를 읽음", observed="2부 개시 약 10분 전에 줄을 섬",
         alternatives=None, evidence="2026-10-16 blog05 원문 조식 절 직접 대조", certainty="명시 (원문 대조) · 실제 대기분 미상",
         level="time", scope="포함 조식의 도착 시각 선택 · 대안 회차 불명 · 업장 자유 선택 아님"),
    dict(id="F12", stay="blog49", guest="투숙", situation="조식 도착 시각", booked="없음", included="없음",
         prior_plan=None, condition=None, observed="2부 오픈런으로 10분쯤 먼저 가서 기다림",
         alternatives=None, evidence="TRAIT_EVIDENCE 대기 회피 ◎", certainty="명시 (요약)",
         level="time", scope="도착 시각 선택"),
    dict(id="F13", stay="blog60", guest="투숙", situation="석식", booked="없음", included="없음",
         prior_plan="피자힐", condition="잠깐 웨이팅", observed="기다린 뒤 창가석에서 식사",
         alternatives=None, evidence="TRAIT_EVIDENCE 대기 회피 ◎", certainty="명시 (요약)",
         level="wait_stay", scope="대기 후에도 같은 업장 유지"),
    dict(id="F14", stay="blog03", guest="투숙", situation="석식", booked="없음", included="없음",
         prior_plan="피자힐", condition="저녁 대기 ('기다리기 나쁘지 않았습니다')", observed="기다려서 피자힐 이용",
         alternatives=None, evidence="TRAIT_EVIDENCE 대기 회피 · TRUTH_ORDER_PAIRS ◎", certainty="명시 (요약)",
         level="wait_stay", scope="대기 감수 · 'TOGO 놓치고' 의 뜻은 원문 확인 필요"),
    dict(id="F15", stay="blog11", guest="투숙", situation="석식 형태", booked="없음", included="더글라스 라운지 석식",
         prior_plan=None, condition=None, observed="라운지 뷔페를 포장해 객실에서 먹고 룸서비스 스테이크 추가 주문",
         alternatives=None, evidence="2026-10-16 blog11 원문 라운지·객실 식사 단락 직접 대조", certainty="행동 명시 (원문 대조) · 포장 이유 미상",
         level="exclude", scope="라운지 혜택의 형태 선택으로 분리 · 계약 포함 여부는 정책 가정 · 룸서비스 추가 주문은 다른 식당 전환이 아님"),
    dict(id="F16", stay="blog50", guest="투숙", situation="석식", booked="없음", included="클럽라운지 석식",
         prior_plan=None, condition="따로 밥 사 먹을 시간이 없음", observed="해피아워를 저녁 대신 이용",
         alternatives=None, evidence="TRUTH_MEALS ◎", certainty="명시 (요약)",
         level="exclude", scope="포함 혜택으로 정해진 식사"),
]

# 10/16 LLM 파일럿에서 '식당이 둘 이상인 자유 선택' 으로 쓴 4건 — 이 정의로 다시 보면 '방문만 확인' (예약 · 포함이 없을 뿐 고민 · 변경 단서 없음)
PILOT_FREE4 = {"blog18": "방문만 확인", "blog24": "방문만 확인", "blog31": "방문만 확인", "blog42": "방문만 확인"}

if __name__ == "__main__":
    from collections import Counter
    c = Counter(x["level"] for x in CASES)
    print(len(CASES), "건 ·", dict(c))
    for x in CASES:
        print(f"{x['id']} {x['stay']:<7} {x['level']:<9} {x['certainty']:<14} {x['situation']} · {x['observed']}")
