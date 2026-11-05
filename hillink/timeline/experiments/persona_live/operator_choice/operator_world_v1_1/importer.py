"""운영 월드 V1.1 — 신규 작성자 입력 경로 보완(10/22 6차 · V1 동결 파일 수정 없음 · V1과 나란히 비교용)

V1 엔진 · 월드 · 계수(W) · 정책(POLICY)은 그대로 쓴다. 바꾸는 것은 'V4.2 사실 → 성향 · 업장 경험' 변환뿐이다.
PR #94 5명을 V1로 돌려 찾은 공통 실패 유형에 대응한다.

1. 업장 경험 연결(venue linking) — V4.1 경로에는 있고 V4.2 경로에는 없던 것
   예: '피자힐 음식의 가격 대비 만족이 낮아 다시 오지 않겠다' → V1은 이 사실을 엔진에 넘기지 못해 기본 조건에서 피자힐을 고름
   → 사실의 업장 이름 · 특성 키에서 업장을 찾고, 이용 후 부정 평가 · 재방문 거부면 appraisal, 실제 이용이면 used 로 연결
2. 자동 연결 어휘 보강(관측된 누락만) — '아깝다 · 가격 대비 만족 낮음' → 구매 전 가치 비교
3. 동행 맥락(companion context) — 같은 사람이라도 부모 · 아이 · 친구 · 배우자 · 혼자 방문에 따라 근거의 무게가 다름
   - 사실의 detail 에 동행이 드러나면 그 맥락 태그를 붙인다(원문에 없는 동행은 만들지 않음 · 태그 없음 = 맥락 무관)
   - 이번 방문의 동행과 같은 맥락의 근거는 1.0, 다른 맥락의 근거는 0.6(가정 · V1.1 연구 값 · 결과에 맞춰 조정하지 않음)
   - '○○와 다시 오면 ~하고 싶다' 같은 조건부 의향은 V1에서 제외되지만, 이번 방문이 그 조건과 같으면 약한 근거로 살린다
"""
from __future__ import annotations

import re
from copy import deepcopy

from operator_choice.operator_world_v1 import auto_link as AL
from operator_choice.operator_world_v1 import profile_adapter as PA
from operator_choice.operator_world_v1 import world as WD
from operator_choice.operator_world_v1.relevance import X, W as WEAK, R

VERSION = "operator_world_v1_1_importer"
OTHER_CONTEXT_WEIGHT = 0.6      # 가정(V1.1 연구 값)

VENUE_LEX = [
    (r"피자힐|pizzahill|pizza_hill", "PIZZA_HILL"), (r"더뷔페|the_?buffet|뷔페", "THE_BUFFET"), (r"명월관|myung", "MYONGWOLGWAN"),
    (r"온달|ondal", "ONDAL"), (r"금룡|geumryong", "GEUMRYONG"), (r"르\s?파사쥬|le_?passage|베이커리", "LE_PASSAGE"),
    (r"스카이야드|skyard|족욕|footbath", "SKYARD"), (r"실내 수영장|수영장|indoor_pool|pool", "POOL"), (r"사우나|sauna", "SAUNA"),
    (r"포레스트 파크|forest", "FOREST"), (r"룸서비스|roomservice|room_service|(?<![가-힣])인룸", "ROOM_MEAL")    # 10차: '파인룸'(식당 별실) 속 '인룸' 제외,
]
COMPANION_LEX = {
    "parents": r"부모|엄마|아빠|어머니|아버지|모친|부친",
    "kids": r"아이(?!디)|자녀|키즈|유아|어린이|아기|육아|돌잔치|남매",
    "friends": r"친구",
    "partner": r"아내|남편|배우자|커플|연인|기념일|와이프",
    "solo": r"혼자",
}
EXTRA_LEX = [(r"아깝|가격 대비 만족이 낮|비싸서|비싸다고", [("value_check", [])])]
NEG_APPRAISAL = r"다시 (오지|가지) 않|재방문(하지| 의사 없| 거부)|가격 대비 만족이 낮|아쉽|실망|불만|No!|가격(만큼|에 비해|대비).{0,12}(않|낮)"
REFUSAL = r"(다시|다음에는?|또는?)\s*(오지|가지|방문하지|찾지)\s*않|재방문(하지 않| 의사 없| ?거부)|재방문거부|올거냐\? ?No|재방문은 부정|No!"
PRICE_DECLINE = r"\d+\s?만\s?원이라|원이라 (주문|구매|이용)하지|비싸(서|다고)|아깝"


def companions_of(text: str) -> list[str]:
    return sorted(k for k, p in COMPANION_LEX.items() if re.search(p, text))


FOOD_WORDS = r"메뉴|음식|요리|맛|소스|코스|디저트|뷔페|파스타|피자를|리조또|세트|플래터|안주|식사"
FOOD_SPECIFIC_WORDS = r"파스타|리조또|피자를|말차|타르트|갈릭|마늘|해산물|치즈|한우|면요리|카야|갈치|야키니쿠|안주"
# 9차: 닫힌 메뉴 목록만으로는 새 작성자의 음식 기호(예: 감자칩 · 초콜릿)를 놓침 → 실제로 먹은 표현이 있으면 음식 기호로 인정
EAT_WORDS = r"먹|섭취|곁들|가져다|주문해|맛[이을은]"
VIEW_WORDS = r"조망|뷰|전망|사진|경치"
PRICE_WORDS = r"가격|원|할인|저렴|비싸|비용|예산|요금|혜택|추가금|추가인원|리조트머니|포함 조건"
EXERCISE_DONE = r"헬스|피트니스|운동(을|하러|했)|러닝|웨이트"
LIGHT_DRINK = r"조금|소량|한두 잔|한 잔|살짝"


def _corrections(fact: dict, links: dict, rules: list) -> None:
    """7차 공통 보정(V1 auto_link 은 동결 · V1.1 에서만): 6차 검수에서 확인한 오연결 유형을 의미 조건으로 막는다."""
    d = fact.get("detail", "")
    if "food" in links and links["food"][0] != X and not re.search(FOOD_WORDS, d):
        links.pop("food"); rules.append("food:removed:no_food_words(예: '요가 두 가지')")
    if "food_specific" in links and links["food_specific"][0] != X:
        if not (re.search(FOOD_SPECIFIC_WORDS, d) or re.search(EAT_WORDS, d) or re.search(FOOD_WORDS, d)) or (re.search(VIEW_WORDS, d) and not re.search(r"맛|메뉴|파스타|리조또", d)):
            links.pop("food_specific"); rules.append("food_specific:removed:not_about_food(예: 식당 조망 · 사진)")
    if "active" in links and not re.search(EXERCISE_DONE, d):
        links.pop("active"); rules.append("active:removed:no_exercise_done(예: '운동 수영에는 덥다' 평가)")
    if "swim_aversion" in links and not re.search(r"수영[^.,·()]{0,10}(안 함|않|무서|비선호)", d):
        links.pop("swim_aversion"); rules.append("swim_aversion:removed:no_swim_negation_nearby(예: '수영 후 … 원인이 아님')")
    # 10차: '밤 추위 · 밤 카페인' 의 '밤' 은 야경이 아님 — 조망 · 야경 단어 없이 '밤' 만으로 잡힌 공간 연결은 뺀다
    if "space" in links and links["space"][0] != X and set(links["space"][1]) <= {"night_view"} and re.search(r"밤", d) \
            and not re.search(r"야경|night|뷰|전망|조망|풍경|경치|일몰|노을|밤하늘|별빛|불빛", d):
        links.pop("space"); rules.append("space:removed:night_word_not_view(예: '밤 추위' · '밤 카페인')")
    # 10차: 대체 선택(당기지 않아 · 품절이라 다른 메뉴) · '여러 메뉴 중 하나를 더 선호' 는 새 메뉴 탐색이 아님
    if re.search(r"다른 메뉴|시그니처", d) and re.search(r"당기지 않|대신|품절|안 돼|어렵|못 ", d):
        for fct, tg in (("novelty", "new_food"), ("food", "menu_explore")):
            if fct in links and links[fct][0] != X and set(links[fct][1]) <= {tg}:
                links.pop(fct); rules.append(f"{fct}:removed:substitution_not_exploration(예: 당기지 않아 다른 메뉴)")
    if re.search(r"메뉴 중[^.]{0,20}(선호|더 좋|골랐)", d):
        if "food" in links and links["food"][0] != X and set(links["food"][1]) <= {"menu_explore"}:
            links.pop("food"); rules.append("food:removed:picked_one_among_many(예: 여러 메뉴 중 돼지고기 선호)")
    # 10차: '다시 연락 · 다시 물놀이 · 취소한 뒤 다시 방문' 의 '다시' 는 재방문 습관(같은 곳을 또 찾음)이 아님
    if "routine" in links and links["routine"][0] != X and re.search(r"다시", d) \
            and not re.search(r"재방문|재예약|두 번|두 차례|세 번|단골|매번|습관|자주|또 (가|왔|찾)|다시 (가고|찾고|오고|방문하고) 싶", d) \
            and re.search(r"다시 (연락|전화|문의|시도|먹|물놀이|들어|돌아)|취소한 뒤 다시|취소 후 다시", d):
        links.pop("routine"); rules.append("routine:removed:retry_or_resume_not_revisit(예: 다시 연락 · 다시 물놀이)")
    # 10차(A01 · A08): 자기 가족 · 본인 행사(돌잔치 · 결혼 · 예식 · 파티)의 '행사' 는 시즌 행사 · 새 경험 근거가 아님
    if re.search(r"행사", d) and re.search(r"돌잔치|돌상|백일|결혼|예식|웨딩|브라이덜|첫째 행사|둘째 행사|행사 인원", d) and not re.search(r"팝업|축제|페어|박람|시즌", d):
        for fct in ("novelty", "seasonal"):
            if fct in links and links[fct][0] != X:
                links.pop(fct); rules.append(f"{fct}:removed:own_family_event(예: 돌잔치 · 결혼 '행사')")
    # 9차(A03): 업장 이름 · 동선 표현과의 어휘 충돌
    if "premium" in links and re.search(r"셰프", d) and not re.search(r"셰프(?!스\s?키친)", d):
        links.pop("premium"); rules.append("premium:removed:chef_in_venue_name(예: '셰프스키친 조식')")
    if re.search(r"코스", d) and not re.search(r"(코스 ?요리|코스 ?메뉴|디너 ?코스|런치 ?코스|귀빈 ?코스|기본 ?코스|오마카세|페어링 ?코스|\d+ ?코스|코스 [0-9,]+원)", d) \
            and re.search(r"(식당|카페|데이트|여행|산책|관람|전시)[^.,]{0,8}코스|코스로 (이동|돌|다녀|짜)|코스를 (짜|돌|구성)", d):
        drop = ["premium"] + ([] if re.search(r"맛|메뉴|먹|식사", d) else ["food"])
        for fct in drop:
            if fct in links and links[fct][0] != X:
                links.pop(fct); rules.append(f"{fct}:removed:itinerary_course(예: '식당 · 카페 코스' = 동선)")
    if "routine" in links and re.search(r"(오전|오후|당일|같은 ?날|그날)[^.,]{0,12}재방문|재방문[^.,]{0,6}(오후|저녁)에", d) and not re.search(r"다시 (가|찾|방문)고 싶|또 (가|오)|단골|매번|자주", d):
        links.pop("routine"); rules.append("routine:removed:same_day_return(예: 도슨트를 위해 오후 재방문 ≠ 재방문 습관)")
    if "value_check" in links and links["value_check"][0] != X:
        if re.search(r"비교", d) and not re.search(PRICE_WORDS, d):
            links.pop("value_check"); rules.append("value_check:removed:compare_without_price(예: 가게끼리 맛 비교)")
        elif re.search(r"가격만 (보지|아니|보고)|가격보다|가격만이 아니라", d):
            links.pop("value_check"); rules.append("value_check:removed:price_not_decisive(예: 가격보다 편한 항공사)")
    if "breakfast_priority" in links and re.search(r"조식.{0,12}(포기|건너|거르|안 먹)|(포기|건너).{0,6}조식", d):
        links.pop("breakfast_priority"); rules.append("breakfast_priority:removed:skipped_breakfast")
    # 10차: 먹다 남은 음식을 싸 온 것(잔여 포장)은 포장 · 객실 식사를 '고른' 근거가 아님 — 선택 표현(미리 주문 · 숙소에서 간단히 등)이 있을 때만
    leftover_only = re.search(r"(남은|남겨|잔여)[^.]{0,12}포장|포장[^.]{0,6}(남은|잔여)", d) and not re.search(r"룸서비스|포장을? 미리|포장 주문|미리 주문|객실에서 (식사|먹)|방에서 (식사|먹)|숙소에서 간단히|숙소에서 먹(었|기로)", d)
    if re.search(r"포장|룸서비스|객실에서 (식사|먹)|방에서 (식사|먹)|숙소에서 간단히", d) and links.get("practical_alt", (None,))[0] != X and fact.get("dimension") != "post_appraisal":
        if leftover_only:
            rules.append("practical_alt:skipped:leftover_packing(예: 남은 피자 포장)")
        else:
            links["practical_alt"] = (R, ["room_meal"]); rules.append("practical_alt:rep:takeout_or_room_meal")
    if re.search(r"(뷔페|조식|식사|코스)[^,.;]{0,12}(포기|건너|취소)", d):
        for fct in ("food", "breakfast_priority"):
            if fct in links and links[fct][0] != X:
                links.pop(fct); rules.append(f"{fct}:removed:gave_up_that_option(예: 조식 뷔페 포기)")
    if "post_appraisal" in links and fact.get("polarity") == "positive":
        links.pop("post_appraisal"); rules.append("post_appraisal:removed:positive_program_appraisal(다른 업장의 가치 유보로 번지지 않게)")
    if "alcohol_familiar" in links and links["alcohol_familiar"][0] == R and re.search(LIGHT_DRINK, d):
        links["alcohol_familiar"] = (WEAK, links["alcohol_familiar"][1]); rules.append("alcohol_familiar:weak:light_drink")


def link_fact_v11(fact: dict, visit_companion: str | None = None) -> dict:
    # 7차: 한국어 요지가 있으면 어휘 판정은 요지로만 — 영문 특성 키 조각 충돌 방지(pizzahill → 'pizza' · walkerhill_membership → 'walk')
    use_detail_only = bool(re.search(r"[가-힣]", fact.get("detail", "")))
    base = dict(fact, feature_key="") if use_detail_only else dict(fact)
    # 10차: V1 원칙(안내 · 소개 = 실제 경험 아님)이 '마감 안내를 받았으나 예약', '테라스만 가능하다고 안내받고 머묾', '지인 소개로 방문' 같은
    # 실제 경험 문장까지 지움 → '안내를 받다 · 소개로/소개받아'는 통보 · 추천 경로로 바꿔 읽는다(내용 삭제 아님 · 연결 판정용 문구만)
    if re.search(r"안내(를|를 )?\s?받|소개(로|를 받|받)", base.get("detail", "")):
        base["detail"] = re.sub(r"안내(를|를 )?\s?받", "통보받", re.sub(r"소개(로|를 받|받)", "추천으로", base["detail"]))
    # 9차: 긍정 이용 후 평가(예: '부대시설 중 만족도가 가장 높았던 야경 족욕')는 V1 원칙 5가 내용 연결을 모두 지우고,
    # 7차 보정이 남은 post_appraisal 까지 지워 근거가 0이 됐다 → 긍정 평가는 내용 차원(야경 · 족욕 등)으로 연결하고 가치 유보로는 쓰지 않는다
    positive_appraisal = fact.get("dimension") == "post_appraisal" and fact.get("polarity") == "positive"
    if positive_appraisal:
        base["dimension"] = "participation_history"
    res = AL.link_fact(base)
    links = dict(res["links"]); rules = list(res["rules"])
    if positive_appraisal:
        rules.append("v1.1:positive_appraisal_content_links(긍정 평가 → 내용 차원 · 가치 유보 제외)")
    if base.get("detail") != fact.get("detail"):
        rules.append("v1.1:notice_or_referral_not_info_text(안내받음 · 소개로 → 실제 경험)")
    _corrections(fact, links, rules)
    text = f"{fact.get('feature_key', '')} {fact.get('detail', '')}"
    blocked = fact.get("time_scope") in ("future", "recommended") or fact.get("kind") == "expectation" or fact.get("actor") in ("other", "unknown")
    if not blocked and (fact.get("dimension") != "post_appraisal" or positive_appraisal):
        for pat, add in EXTRA_LEX:
            if re.search(pat, text):
                for facet, tags in add:
                    if links.get(facet, (None,))[0] != X:
                        links[facet] = (R, tags); rules.append(f"{facet}:rep:v1.1_lex")
    # 조건부 의향: '○○와 다시 오면' — 이번 방문 동행이 그 조건과 같을 때만 약한 근거로
    if fact.get("kind") == "expectation" and visit_companion and visit_companion in companions_of(text):
        relinked = AL.link_fact(dict(fact, kind="participation", time_scope="source_experience"))["links"]
        for facet, (g, tags) in relinked.items():
            if g != X:
                links[facet] = (WEAK, tags); rules.append(f"{facet}:weak:v1.1_conditional_intent({visit_companion})")
    return dict(links=links, rules=rules)


MENU_POS = r"선호|취향|좋아|높은 평가|호평|맛있|맛이 좋|재방문|재선택|즐겼|즐기|만족|높이 평가|높게 평가|긍정 평가|최고|1순위|\d+\s*~?\s*\d*\s*(조각|번|그릇|접시)|여러 번|리필|더 가져"
MENU_NEU = r"무난|평범|그럭저럭|보통|나쁘지 않|무난한"
MENU_NEG = r"아쉽|별로|실망|짜고|짰|질기|비싸|불만|남겼|맛이 없|입에 안"
MENU_WORD = dict(AL.MENU_LEX, pizza=r"피자(?!힐)|pizza")      # 업장 이름 '피자힐' 은 피자 기호가 아님


def menu_prefs(text: str, polarity: str | None = None):
    """10차: 메뉴 단어가 들어 있는 '절' 의 평가로 메뉴 기호를 나눈다. 같은 사실 안의 '파스타 선호' 와 '피자는 무난' 을 같은 +1 로 묶지 않음.
    반환 [(태그들, 가중치, 근거 절)] — 가중치 +1(명시 호평 · 반복 섭취) · 0(무난 · 평가 없는 주문 → 기호 아님) · -0.5(부정 평가)"""
    clauses = [c for c in re.split(r"[,.;]\s*|(?<=[고며])\s+(?=\S)|지만\s*|으나\s*|(?<=했)으며\s*", text) if c and c.strip()]
    out = []
    for c in clauses:
        tags = [k for k, p in MENU_WORD.items() if re.search(p, c)]
        if re.search(r"메뉴 중", c):
            tags = [t for t in tags if t != "variety"]
        if not tags:
            continue
        if re.search(MENU_NEU, c) and not re.search(r"선호|좋아|맛있|호평", c):
            out.append((tags, 0.0, c.strip()))
        elif re.search(MENU_POS, c):
            out.append((tags, 1.0, c.strip()))
        elif re.search(MENU_NEG, c):
            out.append((tags, -0.5, c.strip()))
        else:
            out.append((tags, 0.0, c.strip()))
    # 절에 평가 단어가 없고 사실 전체가 부정이면 부정으로(이전 규칙과 같은 방향)
    if polarity == "negative":
        out = [(t, (-0.5 if w == 0.0 and not re.search(MENU_NEU, c) else w), c) for t, w, c in out]
    return out


NON_WORLD_VENUE = r"riverpark|리버파크|yoga|요가|kart|카트|tea|티코스|dive|다이빙|hotel_other|타 ?호텔"


def _experienced_pp(facts: list) -> int | None:
    """같은 경험의 사실에서 '최종 결제액 ÷ 인원'(1인 실지출)을 찾는다. 결제 · 지불 문구의 마지막 금액과 'N인 · 성인 N명'을 쓴다. 못 찾으면 None."""
    amt, n = None, None
    for f in facts:
        d = f.get("detail", "")
        if re.search(r"결제|지불", d):
            vals = [int(x.replace(",", "")) for x in re.findall(r"(\d{1,3}(?:,\d{3})+|\d{4,})\s?원", d)]
            if vals:
                amt = vals[-1]
        m = re.search(r"(\d)\s?인|성인\s?(\d)\s?명|(\d)\s?명", d)
        if m:
            n = int(next(g for g in m.groups() if g))
    return round(amt / n) if amt and n else None


def venue_of(fact: dict):
    """7차: 업장은 '그 사실이 다루는 대상'으로 정한다 — 특성 키 우선. 특성 키가 월드 밖 대상(리버파크 · 요가 등)이면 연결하지 않고,
    특성 키로 알 수 없을 때만 요지에서 업장이 '하나만' 언급된 경우에 쓴다(대안으로 언급된 업장에 평가가 번지지 않게)."""
    fk = fact.get("feature_key", "") or ""
    if re.search(NON_WORLD_VENUE, fk, re.I):
        return None
    for pat, v in VENUE_LEX:
        if re.search(pat, fk, re.I):
            return v
    found = {v for pat, v in VENUE_LEX if re.search(pat, fact.get("detail", ""), re.I)}
    return found.pop() if len(found) == 1 else None


def build_traits_v42_plus(team: dict, visit_companion: str | None = None) -> dict:
    """V4.2 사실 → AgentTraits(V1.1). V1 의 build_traits_v42 와 같은 질량 · 수준 계산에 업장 연결 · 어휘 보강 · 동행 맥락을 더한다."""
    sp = team["STRUCTURED_PROFILE"]; facts = sp["facts"]
    # 7차: '한 경험은 성향마다 한 몫' — 같은 경험 안에서 같은 성향에 연결된 사실끼리만 질량을 나눈다
    # (V1 은 경험 안 모든 사실 수로 나눠, 한 방문의 조망 근거가 같은 방문의 식사 · 결제 사실 수만큼 작아졌음)
    linked = {f["fact_id"]: link_fact_v11(f, visit_companion) for f in facts}
    per_facet: dict[tuple, int] = {}
    for f in facts:
        for facet, (g, _) in linked[f["fact_id"]]["links"].items():
            if g != X:
                k = (f.get("experience_key") or f["fact_id"], facet)
                per_facet[k] = per_facet.get(k, 0) + 1
    facets = PA._empty_facets(); evidence_index, audit, menu = {}, [], []
    venues: dict[str, list] = {}
    seen_venue: dict = {}
    for f in facts:
        text = f"{f.get('feature_key', '')} {f.get('detail', '')}"
        res = linked[f["fact_id"]]
        ctx = companions_of(text)
        ctx_w = 1.0 if (not ctx or not visit_companion or visit_companion in ctx) else OTHER_CONTEXT_WEIGHT
        base_mass = PA.CONF_MASS.get(f.get("confidence"), 1.28) * ctx_w
        gist_txt = f.get("detail") or f.get("feature_key")
        evidence_index[f["fact_id"]] = dict(fact_id=f["fact_id"], features=[f.get("feature_key")], gist=gist_txt, posts=[f.get("post_id")], context=ctx)
        for facet, (grade, tags) in res["links"].items():
            n = per_facet.get((f.get("experience_key") or f["fact_id"], facet), 1)
            facets[facet]["evidence"].append(dict(fact_id=f["fact_id"], feature=f.get("feature_key"), grade=grade, tags=list(tags), mass=round(base_mass / n, 4), gist=gist_txt,
                                                  experience=f.get("experience_key")))
        audit.append(dict(feature=f.get("feature_key"), fact_ids=[f["fact_id"]], linked=dict(res["links"]), rules=res["rules"], context=ctx, context_weight=ctx_w))
        if "food_specific" in res["links"] and res["links"]["food_specific"][0] != X:
            for tags, w, why in menu_prefs(f.get("detail", "") if re.search(r"[가-힣]", f.get("detail", "")) else text, f.get("polarity")):
                if w:
                    menu.append(dict(feature=f.get("feature_key"), tags=tags, weight=w, fact_ids=[f["fact_id"]], gist=gist_txt, basis=why))
                audit[-1].setdefault("menu", []).append(dict(tags=tags, weight=w, basis=why))
        # 업장 연결(실제 경험만)
        v = venue_of(f)
        if v and f.get("actor") == "author" and f.get("time_scope") in ("source_experience", "historical", "mixed"):
            neg = f.get("dimension") == "post_appraisal" or f.get("kind") == "appraisal" or (f.get("polarity") in ("negative", "mixed") and re.search(NEG_APPRAISAL, text))
            price_decline = f.get("kind") == "decline" and re.search(PRICE_DECLINE, text)
            kind = None
            quotes = " ".join((a.get("quote") or "") for a in f.get("anchors", []))      # 원문 인용(있으면)도 함께 봄 — 요약이 거부 표현을 줄였을 수 있음
            if re.search(REFUSAL, quotes + " " + text + " " + str(f.get("_team_stage") or "")) and f.get("kind") in ("appraisal", "revisit", "decline"):
                kind = "refuse"             # 명시적 재방문 거부 — V1.1 엔진 확장에서 같은 조건이면 그 업장의 개인적 끌림을 상쇄(영구 금지 아님)
            elif (neg and re.search(NEG_APPRAISAL, text) and re.search(PRICE_WORDS + r"|가성비|값|재방문|다시", text)) or price_decline:
                # 7차: 가격 · 가치 · 재방문에 대한 부정 평가만 '가격 가치 유보' — 시설 불편(탈의실 협소 등)은 그 업장 이용 경험으로 둠
                kind = "appraisal"          # 그 업장 · 상품에 대한 가격 가치 유보(영구 금지 아님 — 엔진에서는 감점 한 항)
            elif f.get("kind") in ("participation", "purchase", "revisit", "comparison") and f.get("time_scope") != "mixed":
                # 10차: 그 식당 음식을 '포장해 객실에서' 먹은 경험은 매장 식사 친숙성이 아님(실용 대안 근거로만)
                kind = None if (v in ("PIZZA_HILL", "THE_BUFFET", "MYONGWOLGWAN", "ONDAL", "GEUMRYONG") and "practical_alt" in res["links"]) else "used"
            for kd in (["appraisal", "refuse"] if kind == "refuse" else ([kind] if kind else [])):   # 거부 = 가치 유보(V1 항) + 거부(V1.1 확장)
                key = (v, kd, f.get("experience_key") or f["fact_id"])     # 7차: 같은 방문 · 같은 경험의 여러 사실은 한 번만
                if key in seen_venue:
                    seen_venue[key]["fact_ids"].append(f["fact_id"])
                else:
                    seen_venue[key] = dict(feature=f.get("feature_key"), venue=v, kind=kd, fact_ids=[f["fact_id"]], gist=gist_txt, experience=f.get("experience_key") or f["fact_id"],
                                           basis=("명시적 재방문 거부" if kind == "refuse" else ("구매 전 가격 거절" if price_decline else ("이용 후 부정 평가" if kd == "appraisal" else "실제 이용"))))
                    venues.setdefault(v, []).append(seen_venue[key])
    # 8차: 재방문 거부 업장의 '실제 지출(1인)'을 같은 경험의 결제 사실에서 찾는다 — 엔진 확장이 새 조건과 비교하는 기준
    for v, xs in venues.items():
        for x in xs:
            if x["kind"] == "refuse":
                x["experienced_pp_krw"] = _experienced_pp([f for f in facts if (f.get("experience_key") or f["fact_id"]) == x.get("experience")])
    PA._finish(facets)
    return dict(persona_id=sp.get("persona_id"), profile_version="team_v4.2_import_v1.1", evidence_granularity="fact", linker="auto+v1.1",
                profile_status="V4.2 입력 · V1.1 연결(업장 · 어휘 보강 · 동행 맥락) · 검수 전", visit_companion=visit_companion,
                source_post_count=len({f.get("post_id") for f in facts}), active_fact_count=len(facts),
                facets=facets, menu=menu, venues=venues, evidence_index=evidence_index, relevance_audit=audit,
                assumptions=["V1.1: 업장 연결 · 어휘 보강 · 동행 맥락(다른 맥락 근거 ×0.6 가정)", "V1 엔진 · 월드 · 계수 동일"],
                human_review="pending", demo_approved=False)


COMPANION_VISITS = {
    "parents": dict(party_size=3, companions="부모 동반(가정)", rest_goal=0.6),
    "kids": dict(party_size=3, companions="아이 동반(가정)", rest_goal=0.6),
    "friends": dict(party_size=2, companions="친구 동반(가정)", rest_goal=0.4),
    "partner": dict(party_size=2, companions="배우자 · 연인 동반(가정)", rest_goal=0.5),
    "solo": dict(party_size=1, companions="혼자(가정)", rest_goal=0.8),
}


def visit_for(pid: str, companion: str | None, companion_only: bool = True) -> dict:
    """7차: 기본은 동행만 바꾼다(방문 목적 · 휴식 목표 · 인원은 기본 방문과 같게) — 동행 차이가 개인 근거에서 오는지 보려고."""
    v = WD.default_visit(pid)
    if companion:
        c = COMPANION_VISITS[companion]
        extra = dict(companions=c["companions"]) if companion_only else dict(c)
        v = dict(v, **extra, visit_variant=f"companion_{companion}", visit_label=c["companions"])
    return v
