"""하이브리드 판단 검토자 (Claude 10/29) — 규칙 엔진이 불확실한 지점에서만 LLM 추론을 부른다.

역할 분담
  · 규칙 엔진(BE01 평가기 + 비용 계약): 계수로 재기 자연스러운 판단 — 모든 결정에서 먼저 고른다.
  · 감지기: 아래 조건에 걸린 결정만 LLM 에 넘긴다(그 외는 호출 0).
      NEAR_TIE           상위 두 후보 점수 차 < 0.35
      COST_ABSTAIN       가격 미확인 후보 때문에 금전 항 전부 제외(비용 비교 없이 결정)
      REPEAT_VENUE       이번 체류에서 이미 식사한 업장을 다시 고름
      REPEAT_MENU        이번 체류에서 이미 먹은 같은 메뉴(상품)를 다시 고름
      NO_PERSONAL_BASIS  고른 후보에 고객 개인 근거(후기 사실)가 붙은 양(+) 항이 없음
      PRICE_GAP          가격 거절 · 가치 확인 근거가 있는 고객이 같은 시각 가장 싼 식사의 2배 이상을 고름
  · LLM: 고객 근거 · 이번 체류 이력 · 후보별 업장 정보(메뉴 단품/코스 · 그날 판매 여부 · 하한가 · 건물 · 이동 · 조망 근거 상태) ·
         규칙 엔진 상위 후보와 항 요약을 받고, 감지 이유에 맞춘 질문에 답한다. 후보 목록 밖 선택은 '월드 밖 제안'으로만 기록.
  · 판정: 같은 답 → 규칙 유지. 엇갈림 → (adopt 모드) 확신도 ≥ 0.6 이고 근거에 '후기 근거 · 상황 · 업장 정보' 가 하나 이상이면 LLM 선택 채택,
          아니면 규칙 유지. 모든 엇갈림은 HYBRID_REVIEW.jsonl 에 둘 다 기록 → 따로 채점.

환경 변수
  HILLINK_HYBRID = off | dry(질문만 만들고 호출 안 함) | live | replay(캐시만)
  HILLINK_HYBRID_ARB = adopt | shadow(기록만)
  HILLINK_HYBRID_CACHE(응답 캐시 폴더) · HILLINK_HYBRID_MAX_USD(live에서는 명시적 양수 예산 필수) · HILLINK_HYBRID_MODEL(기본 gpt-6-luna) · HILLINK_HYBRID_EFFORT(기본 medium)
  키: OPENAI_API_KEY 환경 변수(값은 어디에도 기록하지 않음)
"""
from __future__ import annotations

import csv, hashlib, io, json, os, re, time, urllib.error, urllib.request
from datetime import date
from pathlib import Path
from . import review_identity as RI

VERSION = "CLAUDE_HYBRID_REVIEW_V1"
API_URL = "https://api.openai.com/v1/responses"
PRICES = {"gpt-6-luna": dict(input=0.10, cached=0.01, output=0.50)}   # USD / 1M (llm_layer.py 와 같은 확인값)
MEAL_KINDS = ("restaurant", "room_meal", "simple_meal")
MENU_VENUE = {"MOEGI": "모에기", "MYONGWOLGWAN": "명월관", "PIZZA_HILL": "피자힐", "GEUMRYONG": "금룡", "ONDAL": "온달", "THE_BUFFET": "더뷔페",
              "LE_PASSAGE": "르파사쥬", "THE_PAVILION": "파빌리온", "ROOM_MEAL": "IRD"}
BUILDING_KO = {"VISTA": "비스타 워커힐 건물", "GRAND": "그랜드 워커힐 본관", "PIZZA": "피자힐 단독 건물(언덕 위 · 로비에서 셔틀 · 팀 후기 자료)",
               "MYONG": "명월관 단독 건물", "FOREST": "포레스트 파크(야외)", "DOUGLAS": "더글라스 하우스"}
# 조망 근거(view_patch_v12 와 같은 표 + 피자힐 공식) — 근거 상태를 그대로 LLM 에 넘긴다
VIEW = {"PIZZA_HILL": "한강 · 아차산 조망 테라스(공식 보도자료) — 스카이야드 족욕과 같은 한강 방향 조망",
        "THE_BUFFET": "한강 조망 창가석 있음(팀 후기: 창가석 만석 · 대기) — 창가석 확보는 불확실",
        "MYONGWOLGWAN": "한강 조망(외부 리뷰 집계)", "MOEGI": "한강 전망(외부 리뷰 집계)",
        "GEUMRYONG": "창가석 · 창가 별실(+50,000) 한강 조망(공식 · 이용 후기) — 창가석 확보는 불확실",
        "SKYARD": "한강 조망 족욕(고객 후기)", "SKYARD_NIGHT": "한강 야경 족욕"}
# 사용자 확인 판매 규칙(10/29 21:29 bk): 금룡 단품은 주말 저녁 불가 · 점심 가능 — menu.csv 의 일요일 저녁 허용보다 우선
USER_RULES = {("금룡", "삼선 자장면 · 저녁"): "월화수목금-공휴일", ("금룡", "조리장 특선 볶음밥 (XO) · 저녁"): "월화수목금-공휴일"}
# 사용자 확인 주말 단품 규칙(10/29 21:39 bk · 외부 검색 집계 전달): 메뉴표에 가격이 없는 단품은 '가격 미수록' 으로만 알린다(가격 지어내지 않음)
ALACARTE = {
    "PIZZA_HILL": dict(weekend_lunch=True, weekend_dinner=True, note="주말 점심 · 저녁 모두 단품(피자 · 파스타 · 샐러드) 가능"),
    "MYONGWOLGWAN": dict(weekend_lunch=True, weekend_dinner=True, note="주말 점심 · 저녁 모두 식사 단품(갈비탕 · 육회비빔밥 · 냉면)과 구이 단품 가능 — 별관 오마카세는 코스 전용",
                         unpriced=["육회비빔밥", "냉면", "갈비탕(저녁 가격 미수록)"]),
    "MOEGI": dict(weekend_lunch=True, weekend_dinner=True, note="주말에도 홀 좌석은 단품(덮밥 · 튀김 · 단품 스시) 상시 가능 — 스시 카운터 · 철판 좌석은 코스 전용",
                  unpriced=["덮밥", "튀김", "단품 스시"]),
    "GEUMRYONG": dict(weekend_lunch=True, weekend_dinner=False, note="주말 점심은 단품(자장면 · 짬뽕 · 탕수육) 가능 · 주말 저녁은 코스만(단품 불가)",
                      unpriced=["짬뽕(가격 미수록)", "탕수육(가격 미수록)"]),
}
SKIP_UNIT = re.compile(r"어린이|미취학|초등|아동|추가금|이용료|20~32인|상견례|1 ?회|1건")
TRIG_KO = {"BREAKFAST_FACT": "후기에 아침 · 조식 관련 사실이 있어 기본값 대신 판단 필요", "OUTSIDE_TOP_BY_PRICE": "호텔 밖 식사(가정가)가 점수 1위 — 가격만으로 고를 수 없어 판단 필요", "NEAR_TIE": "상위 후보 점수 차가 작음", "COST_ABSTAIN": "가격 미확인 후보 때문에 비용 비교를 하지 못함",
           "REPEAT_VENUE": "이번 체류에서 이미 식사한 업장을 다시 고름", "REPEAT_MENU": "이번 체류에서 이미 먹은 메뉴를 다시 고름",
           "NO_PERSONAL_BASIS": "고객 개인 근거 없이 공통 항만으로 결정", "PRICE_GAP": "후기에 가격 판단 사례가 있는 고객 · 후보 간 1인 가격 차가 큼(어느 쪽이 맞는지는 판단 필요)"}

SYSTEM = (
    "당신은 워커힐 호텔 투숙 고객의 행동을 시뮬레이션하는 연구팀의 검토자입니다. 규칙 기반 엔진이 이 고객의 다음 행동을 이미 골랐지만, "
    "엔진이 확신하기 어려운 지점이라 당신의 추론이 필요합니다. 고객의 후기 근거(review_confirmed 는 실제 경험, profile_inference 는 분석가 가설), "
    "이번 체류에서 이미 한 일과 먹은 것, 후보별 업장 정보(메뉴 · 단품/코스 · 그날 판매 여부 · 1인 하한가 · 건물 · 이동 · 조망 근거 상태)를 읽고, "
    "이 고객이 실제로 무엇을 할지 현실적인 사람의 감각으로 판단하세요. 연속으로 같은 곳 · 같은 메뉴를 고르는 것이 이 사람에게 자연스러운지, "
    "가격이 이 사람에게 맞는지(싼 쪽으로도 비싼 쪽으로도 치우치지 말고), 음식 · 분위기 · 편의의 경험 차이, 이동 부담 · 피로 · 혼자/동행 여부, 이미 본 풍경과 겹치는지까지 생각하세요. "
    "선택은 반드시 candidates 의 id 중 하나로 하고, 그 id 가 가리키는 상품(세트 · 코스 · 단품 · 업장 단위)과 당신의 설명이 일치해야 합니다(단품을 생각하면 세트 SKU 를 고르지 마세요). 호텔 밖 식사(배달 · 편의점)가 후보에 있으면 같은 기준으로 견주세요(가격은 가정값). 후보에 없는 더 자연스러운 대안이 있으면 "
    "가장 가까운 후보를 고르되 outside_option 에 그 대안을 적으세요. 근거마다 type 을 붙이세요: '후기 근거'(fact_ids 필수 · 목록에 있는 id 만), "
    "'상황'(이번 체류 이력 · 시각 · 피로 · 동행), '업장 정보'(주어진 업장 정보), '일반 지식(미검증)'(주어지지 않은 워커힐 · 세상 지식). "
    "주어지지 않은 사실을 확인된 것처럼 쓰지 마세요. 후기 근거는 그 사실이 말하는 범위(어떤 업장 · 상품 · 상황 · 동행)에서만 쓰세요 — 특정 업장의 포장 경험을 일반적인 배달 선호로, 한 번의 가격 거절을 전체 예산 상한으로, 다른 호텔에서의 행동을 이 호텔의 습관으로 넓히지 말고, 넓혀야 한다면 assumptions 에 그 확장을 적으세요. 규칙 엔진의 선택이 충분히 자연스러우면 그대로 동의해도 됩니다. 답은 한국어로.")

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["rule_choice_natural", "verdict", "choice", "confidence", "reasons", "outside_option", "assumptions", "summary"],
          "properties": {
              "rule_choice_natural": {"type": "boolean"},
              "verdict": {"type": "string", "enum": ["agree", "disagree"]},
              "choice": {"type": "string"},
              "confidence": {"type": "number"},
              "reasons": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["type", "text", "fact_ids"],
                                                     "properties": {"type": {"type": "string", "enum": ["후기 근거", "상황", "업장 정보", "일반 지식(미검증)"]},
                                                                    "text": {"type": "string"}, "fact_ids": {"type": "array", "items": {"type": "string"}}}}},
              "outside_option": {"type": "string"},
              "assumptions": {"type": "array", "items": {"type": "string"}},
              "summary": {"type": "string"}}}


def cfg():
    if os.environ.get("HILLINK_HYBRID", "off") == "live" and os.environ.get("HILLINK_LLM_EXTERNAL_OPT_IN") != "1":
        raise ValueError("HYBRID_PAID_PROVIDER_NOT_AUTHORIZED")
    result = dict(mode=os.environ.get("HILLINK_HYBRID", "off"), arb=os.environ.get("HILLINK_HYBRID_ARB", "adopt"),
                cache=os.environ.get("HILLINK_HYBRID_CACHE") or None, max_usd=float(os.environ.get("HILLINK_HYBRID_MAX_USD", "1.0")),
                model=os.environ.get("HILLINK_HYBRID_MODEL", "gpt-6-luna"), effort=os.environ.get("HILLINK_HYBRID_EFFORT", "medium"),
                votes=int(os.environ.get("HILLINK_HYBRID_VOTES", "1")))   # 자기 일관성 투표(관제 승인 전 기본 1)
    if result['mode']=='live' and not RI.live_allowed(result):raise ValueError('HYBRID_EXPLICIT_BUDGET_NOT_AUTHORIZED')
    return result


STATE = dict(spent=0.0, calls=0, log=None)


# ---------- 업장 정보 ----------
_MENU = None
def _menu(root):
    global _MENU
    if _MENU is None:
        p = Path(root) / "timeline/menu.csv"
        _MENU = list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8-sig"))))
    return _MENU


def _day_ok(r, day):
    if (r["업장"], r["상품"]) in USER_RULES: r = dict(r, 요일제한=USER_RULES[(r["업장"], r["상품"])])
    if r["판매시작"] and day < r["판매시작"]: return False
    if r["판매종료"] and day > r["판매종료"]: return False
    rule = r["요일제한"]
    if not rule or rule.startswith("지정일"): return not rule
    head = rule.split("공휴일")[0]
    days = [i for i, ch in enumerate("월화수목금토일") if ch in head]
    return not days or date.fromisoformat(day).weekday() in days


def _period_ok(r, minute):
    w = r["시간제한"]
    if not w: return True
    for part in w.split(","):
        m = re.match(r"(\d+):(\d+)-(\d+):(\d+)", part.strip())
        if not m: continue
        s, e = int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
        if minute >= 16 * 60 and e >= 19 * 60 and e > minute: return True       # 저녁: 저녁 시간대까지 여는 회차
        if minute < 16 * 60 and s < 16 * 60 and e > minute: return True         # 점심
    return False


def _mh(t):
    return f"{t // 60:02d}:{t % 60:02d}" if isinstance(t, int) else t


def venue_menu(root, venue, day, minute, party):
    name = MENU_VENUE.get(venue)
    if not name: return None
    rows, min2 = [], []
    for r in _menu(root):
        if r["업장"] != name or SKIP_UNIT.search(r["단위"]) or "포장" in r["상품"] or "변경" in r["상품"]: continue
        if not _day_ok(r, day) or not _period_ok(r, minute): continue
        if venue == "THE_BUFFET" and not (("석식" in r["상품"]) if minute >= 16 * 60 else ("중식" in r["상품"])): continue
        if venue == "THE_BUFFET" and "성인" not in r["상품"]: continue
        n = re.search(r"(\d+)인(?! 이상)", r["단위"]); need2 = "2인 이상" in r["단위"]
        if need2 and party < 2:
            min2.append(f"{r['상품']} {int(r['단가']):,}/인"); continue
        if n and "세트" in r["단위"] and int(n[1]) > party + 1: continue
        pp = int(r["단가"]) // (int(n[1]) if n and "세트" in r["단위"] else 1)
        kind = "코스 · 세트" if ("코스" in r["상품"] or "세트" in r["단위"] or "정식" in r["상품"] or "상차림" in r["상품"] or need2 or "맡김" in r["상품"]) else "단품"
        rows.append(dict(item=r["상품"], unit=r["단위"], pp_krw=pp, kind=kind))
    wk = date.fromisoformat(day).weekday() >= 5
    ala = ALACARTE.get(venue)
    extra = {}
    if ala and wk:
        ok = ala["weekend_dinner"] if minute >= 16 * 60 else ala["weekend_lunch"]
        extra["alacarte_today"] = ("단품 주문 가능" if ok else "단품 불가 · 코스만") + " — " + ala["note"] + " (사용자 확인 10/29 · 외부 집계)"
        if ok and ala.get("unpriced"): extra["alacarte_unpriced_items"] = ala["unpriced"]
        if not ok: rows = [x for x in rows if x["kind"] != "단품"]
    if not rows:
        return dict(venue=name, **extra, sold_now="이 인원으로 주문 가능한 메뉴 자료 없음" + (f" — 코스는 2인 이상만: {', '.join(min2[:4])}" if min2 else ""))
    rows.sort(key=lambda x: x["pp_krw"])
    sold_not = []
    for r in _menu(root):   # 다른 요일에는 파는 단품(예: 금룡 자장면) — 오늘 없는 이유를 LLM 이 알 수 있게
        if venue != "THE_BUFFET" and r["업장"] == name and not SKIP_UNIT.search(r["단위"]) and _period_ok(r, minute) and not _day_ok(r, day) and r["요일제한"] and not r["요일제한"].startswith("지정일"):
            sold_not.append(f"{r['상품']}({int(r['단가']):,}원 · {r['요일제한']})")
    return dict(venue=name, cheapest_pp_krw=rows[0]["pp_krw"], single_dishes=[f"{x['item']} {x['pp_krw']:,}" for x in rows if x["kind"] == "단품"][:6],
                courses_sets=[f"{x['item']} {x['pp_krw']:,}/인" for x in rows if x["kind"] != "단품"][:5], not_sold_today=sold_not[:4],
                needs_two_or_more=min2[:3], **extra)


# ---------- 감지 ----------
def _price_pp(row, offer):
    """1인 실지불(투숙객 할인 · 카드 혜택 뺀 값) — 와인페어 무료 입장이 55,000 으로 보이던 결함 수정."""
    c = row.get("sku_contract") or (offer or {}).get("sku_contract")
    if c and c.get("unit_price_krw") is not None:
        # 세트 · 공유 단위(커플 세트 184,000 = 2인 합계)는 1인값으로 환산 — 후보 가격이 메뉴표 92,000/인과 어긋나던 결함(10/30 변동 시험에서 발견)
        if c.get("billing_unit") in ("set", "shared", "table") or "세트" in str(c.get("source_unit") or ""):
            n = re.search(r"(\d+)인", str(c.get("source_unit") or ""))
            per = int(n[1]) if n else max(1, int(c.get("billing_quantity") or 1))
            return int(round(int(c["unit_price_krw"]) * int(c.get("billing_quantity") or 1) / max(1, per) if not n else int(c["unit_price_krw"]) / per))
        return int(c["unit_price_krw"])
    p = (offer or {}).get("price_pp_krw")
    if p is None: return None
    return max(0, int(p) - int((offer or {}).get("guest_discount_krw") or 0) - int((offer or {}).get("card_benefit_krw") or 0))


def _stay_meals(a, offers_by_id):
    out = []
    vh = getattr(a, "visit_history", {}) or {}
    evs = (STATE.get("events") or {}).get(getattr(a, "pid", None)) or []
    for m in vh.get("prior_meals", []):
        # 이전 날 식사는 M4 사건 기록에서 실제 상품(action_id)을 찾아 메뉴명으로(10/30: 'turn_dinner' 만 전달돼 LLM 이 전날 봉골레를 몰랐던 결함)
        hit = next((e for e in evs if e.get("date") == m.get("date") and e.get("meal_slot") == m.get("slot") and e.get("venue_id") == m.get("venue_id")), None)
        code = (hit or {}).get("action_id") or m.get("action")
        what = (offers_by_id.get(code) or {}).get("label") or code
        out.append(dict(date=m.get("date"), slot=m.get("slot"), venue=m.get("venue_id"), what=what, code=code))
    for x in a.log:
        if x.get("meal_slot") and x.get("act") not in ("move", "wait"):
            out.append(dict(date=a.sc.get("date"), slot=x["meal_slot"], venue=x.get("loc"), what=x.get("label"), code=x.get("act"), t=x.get("t")))
    return out


def recorded_memory(a,t):
    """Only stored events and plans. Pending intention is not an experience."""
    now=date.fromisoformat(a.sc['date']).toordinal()*1440+t
    events=[]
    for e in (getattr(a,'visit_history',{}) or {}).get('m4_history',[]):
        try:end=date.fromisoformat(e['date']).toordinal()*1440+int(e['end'][:2])*60+int(e['end'][3:])
        except (KeyError,TypeError,ValueError):continue
        if end<=now:events.append({k:e.get(k) for k in ('event_id','date','start','end','action_id','venue_id','meal_slot')})
    rest=[{k:x.get(k) for k in ('t','e','act','label','loc')} for x in a.log if x.get('act') in ('room_rest','room_bath','sleep','footbath','night_footbath') and x.get('e') and int(x['e'][:2])*60+int(x['e'][3:])<=t]
    goals=getattr(a,'intents',None)
    if not isinstance(goals,(dict,list)):goals=None
    return dict(prior_executed_events=events,recent_recorded_rest=rest,
                recorded_goals=goals,goal_status='RECORDED_PLAN_NOT_EXECUTED_FACT' if goals else 'NOT_RECORDED',
                source='ACTUAL_VISIT_HISTORY_AND_ACTOR_LOG_ONLY_NO_INFERRED_MEMORY')


JUDGMENT_ONLY = {"OUTSIDE_MEAL"}   # 규칙 엔진이 가격 항만으로 고르지 못하는 후보 — LLM 이 맥락상 자연스럽다고 판단할 때만 채택(11명 실행에서 15,000 가정값이 비용 항으로 8/11 저녁을 가져간 결함 수정)


def detect(a, ev, offers_by_id):
    feas = sorted([r for r in ev["candidates"] if r.get("feasible")], key=lambda r: -r["total"])
    if len(feas) < 2: return [], feas
    pre = []
    if feas[0]["offer"] in JUDGMENT_ONLY:
        # 규칙 선택을 판단 전용이 아닌 1위로 내리고, 그 결정은 반드시 LLM 검토로
        demoted = feas[0]; feas = [r for r in feas if r["offer"] not in JUDGMENT_ONLY] + [r for r in feas if r["offer"] in JUDGMENT_ONLY]
        pre.append("OUTSIDE_TOP_BY_PRICE")
    top = feas[0]; o = offers_by_id.get(top["offer"], {})
    meal_involved = any(offers_by_id.get(r["offer"], {}).get("kind") in MEAL_KINDS for r in feas[:3])
    if not meal_involved and top.get("kind") != "event": return pre, feas
    trig = list(pre)
    if feas[0]["total"] - feas[1]["total"] < 0.35: trig.append("NEAR_TIE")
    if (ev.get("cost_comparison") or {}).get("applied"): trig.append("COST_ABSTAIN")
    if o.get("kind") in MEAL_KINDS:
        meals = _stay_meals(a, offers_by_id)
        if any(m["venue"] == o.get("venue") for m in meals if m.get("venue")): trig.append("REPEAT_VENUE")
        lab = (o.get("label") or "").split(" · ")[0]
        if any(lab and lab in (m.get("what") or "") or m.get("code") == top["offer"] for m in meals): trig.append("REPEAT_MENU")
        terms = top.get("raw_terms") or top["terms"]
        if not any(t.get("fact_ids") and t["value"] > 0.1 and t.get("kind") == "profile" for t in terms): trig.append("NO_PERSONAL_BASIS")
        ev_ids = " ".join((a.traits.get("evidence_index") or {}).keys())
        price_fact = any(re.search(r"가격|비싸|원이라|만원|가성비|할인", (v or {}).get("gist", "")) for v in (a.traits.get("evidence_index") or {}).values())
        my = _price_pp(top, o)
        prices = [p for r in feas if offers_by_id.get(r["offer"], {}).get("kind") in MEAL_KINDS for p in [_price_pp(r, offers_by_id.get(r["offer"]))] if p]
        if price_fact and my and prices and my >= 2 * min(prices): trig.append("PRICE_GAP")
    return trig, feas


def _dedupe_persona(b):
    """같은 요지의 하위 사실(F10 · F10a · F10b …)을 한 줄로 접는다 — 한 사건이 여러 근거처럼 보이던 결함 수정."""
    import copy
    b = copy.deepcopy(b)
    prof = b.get("profile") or {}
    for sec in ("review_confirmed", "profile_inference"):
        d = prof.get(sec)
        if not isinstance(d, dict): continue
        for key, items in d.items():
            if not isinstance(items, list) or not items or not isinstance(items[0], dict): continue
            seen = {}; out = []
            for it in items:
                g = (it.get("what") or it.get("pattern") or json.dumps(it, ensure_ascii=False))[:60]
                if g in seen:
                    seen[g].setdefault("fact_ids", [])
                    for f in it.get("fact_ids", []):
                        if f not in seen[g]["fact_ids"]: seen[g]["fact_ids"].append(f)
                    continue
                seen[g] = it; out.append(it)
            d[key] = out
    return b


# ---------- 질문 ----------
def _question(trig, a, top_label, meals):
    q = []
    if "REPEAT_VENUE" in trig or "REPEAT_MENU" in trig:
        prev = "; ".join(f"{m.get('date')} {m.get('slot')} {m.get('what') or m.get('venue')}" for m in meals)
        q.append(f"이 고객은 이번 체류에서 이미 이렇게 먹었습니다: {prev}. 규칙 엔진은 이번에 다시 '{top_label}' 를 골랐습니다. "
                 "같은 곳 · 같은 메뉴를 또 고르는 것이 이 사람에게 자연스러운가요? 반복은 그 자체로 틀린 것이 아닙니다 — 그 메뉴 · 업장을 실제로 좋아한 후기, 재방문 근거, "
                 "피곤함 · 이동 편의 · 익숙함 같은 상황이 있으면 다시 고르는 것이 자연스럽고, 그런 근거 없이 메뉴 폭이 좁아지거나 이동(셔틀 · 언덕) · 이미 본 풍경이 겹치면 덜 자연스럽습니다. "
                 "양쪽을 같은 무게로 보고 판단하세요.")
    if "COST_ABSTAIN" in trig or "PRICE_GAP" in trig:
        q.append("일부 후보의 정확한 가격을 몰라 규칙 엔진은 가격을 빼고 비교했습니다. 후보별 '1인 하한가 · 단품/코스' 정보와 이 고객의 경험을 함께 보고, "
                 "이 사람이 실제로 어디서 무엇을 먹을지 판단하세요. 싼 쪽도 비싼 쪽도 그 사람에게 이유가 있으면 자연스럽습니다 — 한 번의 가격 거절 경험을 고정 예산 상한으로 확대하지 말고, "
                 "그날의 기분 · 특별한 저녁을 원할 이유 · 메뉴 선호 · 동행 · 이동 부담을 함께 저울질하세요.")
    if "OUTSIDE_TOP_BY_PRICE" in trig:
        q.append("점수상으로는 호텔 밖 식사(배달 · 편의점 · 가격은 가정값)가 가장 싸서 1위지만, 호캉스 중인 사람이 실제로 그렇게 할지는 가격만으로 정할 수 없습니다. "
                 "이 고객의 경험 · 동행 · 오늘의 흐름 · 호텔 안에서 먹을 이유(분위기 · 편의 · 경험)를 함께 보고, 호텔 밖 식사가 정말 자연스러운 경우에만 그것을 고르세요.")
    if "NEAR_TIE" in trig and not q:
        q.append("규칙 엔진의 상위 후보 점수가 거의 같습니다. 이 고객이라면 어느 쪽을 고를지 판단하세요.")
    if "NO_PERSONAL_BASIS" in trig:
        q.append("규칙 엔진의 선택에는 이 고객 개인의 후기 근거가 직접 붙어 있지 않습니다(공통 항으로 결정). 이 고객에게 맞는 선택인지 확인하세요.")
    return " ".join(q)


def build_packet(a, ev, w, t, trig, feas, root, LL):
    offers_by_id = {o["id"]: o for o in w["offers"]}
    day = a.sc.get("date"); party = getattr(a, "N", 1)
    meals = _stay_meals(a, offers_by_id)
    cands = []
    # 식사 · 행사 후보는 순위와 무관하게 전부(상위 9개 절단으로 OUTSIDE_MEAL · 르파사쥬가 빠지던 결함 수정) + 그 외는 상위 5개
    picked = [r for r in feas if offers_by_id.get(r["offer"], {}).get("kind") in MEAL_KINDS + ("event",)]
    for r in feas:
        if r not in picked and len([x for x in picked if offers_by_id.get(x["offer"], {}).get("kind") not in MEAL_KINDS + ("event",)]) < 5:
            picked.append(r)
    picked.sort(key=lambda r: feas.index(r))
    for r in picked[:22]:   # 10/30: 명월관 구이 단품 5종 추가로 후보가 늘어 16개 절단에 다른 업장이 빠지지 않게
        o = offers_by_id.get(r["offer"], {})
        terms = r.get("raw_terms") or r["terms"]
        info = dict(id=r["offer"], label=o.get("label", r["offer"]), kind=o.get("kind"), start=r.get("start"), end=r.get("end"),
                    travel_min=r.get("travel_min"), rule_rank=feas.index(r) + 1, rule_total=round(r["total"], 3),
                    rule_terms=[f"{x['factor']} {x['value']:+.2f}" for x in sorted(terms, key=lambda x: -abs(x["value"]))[:5]],
                    rule_terms_note="가격 항은 비용 계약 때문에 실제 순위 계산에서는 빠짐(참고로 표시)" if r.get("raw_terms") else "")
        p = _price_pp(r, o)
        info["price_pp_krw"] = p if p is not None else "미확인"
        if o.get("kind") == "event" and o.get("guest_discount_krw"):
            info["price_note"] = f"정가 {int(o['price_pp_krw']):,} · 투숙객 무료 입장(실지불 0) · 시음은 유료 티켓(55,000/성인) 별도 · 식사 대체 아님"
        if o.get("kind") in MEAL_KINDS or o.get("kind") == "event":
            v = o.get("venue")
            SP = LL.SP
            info["building"] = BUILDING_KO.get(SP.BLDG_OF.get(v, ""), SP.BLDG_OF.get(v, "")) if v else None
            info["view"] = VIEW.get(r["offer"]) or VIEW.get(v) or "조망 정보 없음(없다는 뜻 아님)"
            vm = venue_menu(root, v, day, (LL.SP._hm(r["start"]) if isinstance(r.get("start"), str) else (r.get("start") or t)), party) if v else None
            if vm: info["venue_menu"] = vm
            if o.get("price_note"): info["price_note"] = o["price_note"][:120]
            if o.get("external_spend"): info["venue_menu"] = dict(venue="호텔 밖(배달 · 편의점)", note="가격은 가정값 15,000/인(미확인) · 메뉴표 없음 · 호텔 매출 0")
        cands.append(info)
    persona = _dedupe_persona(LL._persona_block(a, []))
    paid = {}
    for c in getattr(a, "charges", []) or []:
        if c.get("krw"): paid[(c.get("t"), c.get("act"))] = c["krw"]
    today = []
    for x in a.log:
        if x["act"] in ("move", "wait"): continue
        item = dict(t=x["t"], what=x["label"])
        k = paid.get((x["t"], x["act"]))
        if k: item["paid_krw"] = k
        if x.get("meal_slot"): item["meal"] = f"{x['meal_slot']} {int(round((x.get('food') or x.get('fraction') or 0) * 100)) if isinstance(x.get('food') or x.get('fraction'), (int, float)) else ''}".strip()
        if x["act"] == "WINE_FAIR": item["note"] = "투숙객 무료 입장 · 시음권 · 음식은 포함 안 됨 · 행사장에서 먹었는지는 미확인 → 저녁은 따로 필요"
        today.append(item)
    today = today[-12:]
    r = a.fatigue / max(0.8, a.rest_limit)
    top_label = cands[0]["label"]
    purpose = f"{persona.get('type') or ''} · {party}인" + (f" · {a.vs.get('rel')}" if getattr(a, 'vs', None) else "") + (" · 아이 동반" if (a.C or {}).get("kids") else "")
    packet = dict(customer=persona, visit_purpose=purpose + " — 방문 목적 · 동행은 후보 비교에서 가격과 같은 무게로 보세요",
                  stay=dict(date=day, weekday="월화수목금토일"[date.fromisoformat(day).weekday()], now=_mh(t),
                            meals_this_stay=meals, today_so_far=today, fatigue="여유" if r < 0.4 else "조금 피곤" if r < 0.8 else "피곤",
                            spent_so_far_krw=int(a.spent), party_size=party),
                  rule_engine=dict(choice=cands[0]["id"], why_review=[TRIG_KO[x] for x in trig],
                                   cost_comparison=(ev.get("cost_comparison") or {}).get("mode", "RECORDED_PRICE_COMPARISON")),
                  candidates=cands,
                  question=_question(trig, a, top_label, meals))
    packet['stay']['recorded_memory']=recorded_memory(a,t)
    return packet


# ---------- 호출 ----------
def _cost(model, inp, cached, out):
    p = PRICES.get(model)
    return round(((inp - cached) * p["input"] + cached * p["cached"] + out * p["output"]) / 1e6, 8) if p else None


def call(packet, c):
    """votes>1 이면 같은 질문을 n회(캐시 키에 회차 포함) 받아 다수결 선택 · 평균 확신 · 각 답을 기록."""
    if c.get("votes", 1) > 1:
        answers, recs = [], []
        for i in range(c["votes"]):
            a, r = _call_once(dict(packet, _vote=i), c); recs.append(r)
            if a: answers.append(a)
        if not answers:return None,dict(votes=recs,skipped=next((r.get('skipped') for r in recs if r.get('skipped')),'no_answer'),network_attempted=any(r.get('network_attempted') for r in recs))
        from collections import Counter
        top = Counter(a["choice"] for a in answers).most_common(1)[0][0]
        picked = [a for a in answers if a["choice"] == top]
        merged = dict(picked[0], confidence=round(sum(a["confidence"] for a in picked) / len(picked), 3),
                      vote=dict(n=len(answers), for_choice=len(picked), choices=[a["choice"] for a in answers], confidences=[a["confidence"] for a in answers]))
        rec = dict(votes=recs,cost_usd=round(sum(r.get('cost_usd') or 0 for r in recs),6),cache_hit=all(r.get('cache_hit') for r in recs),network_attempted=any(r.get('network_attempted') for r in recs),provider_response_received=any(r.get('provider_response_received') for r in recs))
        return merged, rec
    return _call_once(packet, c)


def _call_once(packet, c):
    prompt = json.dumps(packet, ensure_ascii=False)
    key = hashlib.sha256((VERSION + c["model"] + c["effort"] + SYSTEM + prompt).encode()).hexdigest()
    legacy_key=key;ident=RI.identity(packet,c,VERSION,SYSTEM)
    if c.get('native_policy'):key=RI.sha(ident)
    rec = dict(prompt_sha=key[:16], cache_key=key,legacy_cache_key=legacy_key,identity=ident,
               input_sha256=ident['input_sha256'],citable_fact_ids=packet.get('customer',{}).get('citable_fact_ids'),model=c["model"],effort=c["effort"],cache_hit=False,network_attempted=False)
    cache = Path(c["cache"]) / f"{key}.json" if c["cache"] else None
    legacy_cache=Path(c['cache'])/f'{legacy_key}.json' if c.get('cache') else None
    if cache and not cache.exists() and c.get('native_policy') and legacy_cache.exists():
        rec.update(cache_rejection_reason='cache_policy_mismatch',legacy_exact_packet_file_exists=True)
        if c['mode']!='live':rec['skipped']='cache_policy_mismatch';return None,rec
    if cache and cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        rejection=('cache_content_mismatch' if RI.sha(d.get('prompt'))!=ident['input_sha256'] else
                   'cache_policy_mismatch' if c.get('native_policy') and d.get('identity')!=ident else None)
        if rejection:
            rec['cache_rejection_reason']=rejection
            if c['mode']!='live':rec['skipped']=rejection;return None,rec
        else:
            rec.update(d.get('usage') or {},cache_hit=True,cost_usd=0.0,
                       cache_origin='VERSIONED_NATIVE_CACHE' if d.get('identity') else 'LEGACY_EXACT_SOURCE_PACKET',network_attempted=False,provider_response_received=False)
            return d["answer"], rec
    if c["mode"] != "live":
        rec.update(skipped="dry" if c["mode"] == "dry" else "replay_miss"); return None, rec
    if not RI.live_allowed(c):
        rec.update(skipped='authorization');return None,rec
    if os.environ.get('HILLINK_AGENT_BUDGET_FILE'):
        # Comparative experiments share the same durable allowance as the new
        # agent. Preserve this reviewer's candidate set, prompt and arbitration.
        from . import agent_provider as AP
        try:
            answer,trace=AP.request(policy=VERSION+'+SHARED_BUDGET_TRANSPORT_V1',system=SYSTEM,
                context=packet,schema=SCHEMA,purpose='LEGACY_SELECTIVE_REVIEW_CONTROL',
                model=c['model'],effort=c['effort'],max_output=16000)
        except AP.ProviderUnavailable as error:
            trace=getattr(error,'trace',{})
            rec.update(error=str(error),network_attempted=bool(trace),shared_provider=trace)
            return None,rec
        replay=trace['execution']=='CACHE_REPLAY';usage=trace.get('usage') or {}
        cost=0 if replay else trace.get('charged_upper_usd',0)
        STATE['spent']+=cost;STATE['calls']+=int(not replay)
        rec.update(input_tokens=usage.get('input_tokens',0),output_tokens=usage.get('output_tokens',0),
            reasoning_tokens=usage.get('output_tokens_details',{}).get('reasoning_tokens',0),
            cost_usd=cost,cost_basis='TOKEN_BASED_UPPER_ESTIMATE_NOT_INVOICE',cache_hit=replay,
            cache_origin='SHARED_EXACT_RESPONSES_CACHE' if replay else None,
            network_attempted=not replay,provider_response_received=not replay,
            model_returned=trace.get('model_returned'),shared_provider=trace)
        return answer,rec
    if STATE["spent"] + 0.01 > c["max_usd"]:
        rec.update(skipped="budget"); return None, rec
    body = {"model": c["model"], "input": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "max_output_tokens": 4000, "reasoning": {"effort": c["effort"]},
            "text": {"format": {"type": "json_schema", "name": "hybrid_review", "strict": True, "schema": SCHEMA}}}
    t0 = time.time(); last = None
    for attempt in range(2):
        try:
            rec['network_attempted']=True
            req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("OPENAI_API_KEY", "")})
            with urllib.request.urlopen(req, timeout=120) as resp:
                d = json.loads(resp.read().decode())
            u = d.get("usage") or {}
            inp, cached, out = u.get("input_tokens", 0), (u.get("input_tokens_details") or {}).get("cached_tokens", 0), u.get("output_tokens", 0)
            usage = dict(input_tokens=inp, cached_tokens=cached, output_tokens=out,
                         reasoning_tokens=(u.get("output_tokens_details") or {}).get("reasoning_tokens", 0))
            cost = _cost(c["model"], inp, cached, out) or 0
            STATE["spent"] += cost; STATE["calls"] += 1
            rec.update(usage, cost_usd=cost, ms=int((time.time() - t0) * 1000), model_returned=d.get("model"), status=d.get("status"),provider_response_received=True)
            txt = "".join(cc.get("text", "") for it in d.get("output", []) if it.get("type") == "message" for cc in it.get("content", []) if cc.get("type") == "output_text")
            ans = json.loads(txt)
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(dict(answer=ans,usage=usage,prompt=packet,identity=ident),ensure_ascii=False),encoding='utf-8')
            return ans, rec
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (429, 500, 502, 503, 504) and attempt == 0: time.sleep(3); continue
            break
        except Exception as e:   # 네트워크 · 해석 실패
            last = type(e).__name__
            if attempt == 0: time.sleep(3); continue
    rec.update(error=last); return None, rec


# ---------- 판정 ----------
def _intent_mismatch(ans, cands):
    """LLM 이 '단품' 을 말하면서 세트 · 코스 · 한상 SKU 를 고른 경우(A01 명월관 모둠 한상 770,000 사례) → 같은 업장의 업장 단위 후보로 바꾸거나 규칙 유지."""
    if not ans or not cands: return None
    text = (ans.get("summary") or "") + " ".join(r.get("text", "") for r in ans.get("reasons", []))
    by = {x["id"]: x for x in cands}; ch = by.get(ans.get("choice"))
    if not ch: return None
    lab = ch.get("label") or ""
    is_set = any(k in lab for k in ("세트", "코스", "한상", "정식", "오마카세")) or (isinstance(ch.get("price_pp_krw"), int) and ch["price_pp_krw"] >= 300000)
    core = re.sub(r"·.*$", "", lab).strip()
    named = [w for w in re.findall(r"[가-힣A-Za-z]{2,}", core) if w not in ("세트", "코스", "한상", "정식", "피자힐", "명월관", "금룡", "온달", "모에기", "더뷔페", "저녁", "점심")]
    if any(w in text for w in named): return None   # 그 세트 · 코스를 이름으로 언급했으면 의도와 일치(A01 '콰트로' 사례 — 보정 오작동 수정)
    if "단품" in text and is_set:
        venue_id = ch["id"].replace("C01_", "").split("_")[0]
        alt = [x for x in cands if x.get("kind") == "restaurant" and not any(k in (x.get("label") or "") for k in ("세트", "코스", "한상", "정식", "오마카세"))
               and (x["id"].startswith(venue_id) or venue_id in x["id"] or (x.get("venue_menu") or {}).get("venue") == (ch.get("venue_menu") or {}).get("venue"))]
        return alt[0]["id"] if alt else "KEEP_RULE"
    return None


def arbitrate(ans, feas, c, cands=None):
    ids = [r["offer"] for r in feas]
    if not ans: return None, "NO_ANSWER_RULE_KEPT"
    if ans.get("choice") not in ids:   # 'SKYARD — 스카이야드 족욕(낮)' 처럼 id 뒤에 이름을 붙여 답한 경우 id 만 취함(A01 사례)
        head = re.split(r"\s*[—\-–(]\s*", str(ans.get("choice") or ""), 1)[0].strip()
        if head in ids: ans = dict(ans, choice=head)
    if ans["verdict"] == "agree" or ans["choice"] == ids[0]: return None, "AGREE"
    if ans["choice"] not in ids: return None, "DISAGREE_CHOICE_NOT_IN_CANDIDATES_RULE_KEPT"
    mm = _intent_mismatch(ans, cands)
    if mm == "KEEP_RULE": return None, "DISAGREE_INTENT_MISMATCH_SET_VS_SINGLE_RULE_KEPT"
    if mm and mm in ids and mm != ids[0]:
        ans = dict(ans, choice=mm, confidence=min(ans.get("confidence", 0), 0.6)); ans.setdefault("assumptions", []).append("단품 의도 ↔ 세트 SKU 불일치로 같은 업장의 업장 단위 후보로 치환(검토자 보정)")
    grounded = any(r["type"] in ("후기 근거", "상황", "업장 정보") for r in ans["reasons"])
    if c["arb"] != "adopt": return None, "DISAGREE_SHADOW_RULE_KEPT"
    if ans["confidence"] >= 0.6 and grounded: return ans["choice"], "DISAGREE_LLM_ADOPTED"
    # 규칙 선택 자체를 '부자연스럽다' 고 근거 있게 판정했으면, 대안 확신이 중간(≥0.5)이어도 부자연스러운 선택을 그대로 실행하지 않는다
    if grounded and ans.get("rule_choice_natural") is False and ans["confidence"] >= 0.5: return ans["choice"], "DISAGREE_RULE_UNNATURAL_LLM_ADOPTED"
    return None, "DISAGREE_LOW_CONFIDENCE_OR_UNGROUNDED_RULE_KEPT"


def review(a, ev, w, t, root, out_dir, LL):
    c = cfg()
    if c["mode"] == "off" or not ev.get("selected"): return ev
    offers_by_id = {o["id"]: o for o in w["offers"]}
    trig, feas = detect(a, ev, offers_by_id)
    if not trig: return ev
    if ev["selected"] != feas[0]["offer"]:   # 판단 전용 후보가 1위였던 경우: 규칙 선택을 내려 둔다(LLM 이 다시 올릴 수 있음)
        ev["rule_selected_raw"] = ev["selected"]; ev["selected"] = feas[0]["offer"]
    packet = build_packet(a, ev, w, t, trig, feas, root, LL)
    if 'recorded_memory' not in packet['stay']:packet['stay']['recorded_memory']=recorded_memory(a,t)
    ans, rec = call(packet, c)
    adopted, outcome = arbitrate(ans, feas, c, packet["candidates"])
    entry = dict(version=VERSION, customer_id=a.pid, date=a.sc.get("date"), time=_mh(t),
                 triggers=trig, rule_choice=feas[0]["offer"], llm=ans, outcome=outcome, final=adopted or feas[0]["offer"], call=rec,
                 rule_label=(offers_by_id.get(feas[0]["offer"]) or {}).get("label"), final_label=(offers_by_id.get(adopted or feas[0]["offer"]) or {}).get("label"),
                 packet=packet)
    with open(Path(out_dir) / "HYBRID_REVIEW.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    ev = dict(ev, hybrid_review={k: v for k, v in entry.items() if k != "packet"})
    if adopted:
        ev["rule_selected"] = ev["selected"]; ev["selected"] = adopted
    return ev


# ---------- 아침(계획기 턴) 검토 — 조식이 계획기 기본값(룸서비스 한식 47,000 × 인원)으로 검토 없이 확정되던 결함 ----------
BREAKFAST_FACT = re.compile(r"조식|아침|늦잠|브런치|일어나|기상")


def breakfast_candidates(a, w, t):
    """아침 후보 보강: 르파사쥬 빵 · 커피(공식 매장 09:00~ · 가격은 기존 월드 12,000 후기 전언 참조값) — 투숙객이 흔히 하는 '가볍게 빵으로' 가 후보에 없었다."""
    if any(o["id"] == "LE_PASSAGE_BREAKFAST" for o in w["offers"]): return w
    import copy
    try:
        from operator_choice.operator_world_v1 import world as WD
    except Exception:
        return w
    o = WD.offer("LE_PASSAGE_BREAKFAST", "르파사쥬 빵 · 커피로 가볍게 아침", "simple_meal", "LE_PASSAGE", window=dict(start="09:00", end="10:30"), duration=35,
                 price=12000, grade="△", price_note="기존 월드 르파사쥬 참조값(베이커리 가격표 미공개 · 후기 전언) · 매장 09:00 공식", meal_fraction=0.5, courses=1,
                 quality="standard", menu_tags=["bakery", "coffee"], note="V1.2(Claude 10/29) 아침 후보 보강")
    o["catalog"] = dict(id="LE_PASSAGE_BREAKFAST", kind="single", source="WORLD_REFERENCE", pricing="per_person", list_price_krw=12000, party_basis=1, share_n=None)
    w = copy.deepcopy(w); w["offers"].append(o); return w


def review_turn(a, d, w, t, turn, LLmod=None):
    """계획기 턴 결정(d = decide_turn 결과)을 같은 기준으로 검토. 채택되면 d['chosen'] 을 바꾼다."""
    c = cfg()
    if c["mode"] == "off" or turn != "breakfast": return d
    by = {o["id"]: o for o in w["offers"]}
    rows = [dict(offer=d["chosen"]["id"], total=d["chosen"].get("score") or 0, feasible=True, terms=d["reasons"])]
    for x in d.get("not_chosen", []):
        if x.get("feasible") and x.get("score") is not None: rows.append(dict(offer=x["id"], total=x["score"], feasible=True, terms=[]))
    if len(rows) < 2: return d
    feas = sorted(rows, key=lambda r: -r["total"])
    trig = []
    pos = [x for x in d["reasons"] if x["value"] > 0.1 and x.get("fact_ids")]
    if not pos: trig.append("NO_PERSONAL_BASIS")
    ei = a.traits.get("evidence_index") or {}
    bf = [k for k, v in ei.items() if BREAKFAST_FACT.search((v or {}).get("gist", ""))]
    if bf: trig.append("BREAKFAST_FACT")
    if feas[0]["total"] - feas[1]["total"] < 0.35: trig.append("NEAR_TIE")
    price_fact = any(re.search(r"가격|비싸|원이라|만원|가성비|할인", (v or {}).get("gist", "")) for v in ei.values())
    chosen_p = by[feas[0]["offer"]].get("price_pp_krw") or 0
    cheaper = [by[r["offer"]].get("price_pp_krw") for r in feas[1:] if (by[r["offer"]].get("price_pp_krw") or 0) > 0]
    if price_fact and cheaper and chosen_p >= 2 * min(cheaper): trig.append("PRICE_GAP")
    if not trig: return d
    if LLmod is None:
        from operator_choice.autonomy_v1 import llm_layer as LLmod
    root, out = STATE.get("root"), STATE.get("out")
    cands = []
    for r in feas[:10]:
        o = by[r["offer"]]; p = o.get("price_pp_krw")
        info = dict(id=o["id"], label=o["label"], kind=o["kind"], rule_rank=feas.index(r) + 1, rule_total=round(r["total"], 3),
                    price_pp_krw=(max(0, int(p) - int(o.get("guest_discount_krw") or 0)) if p is not None else "미확인"),
                    meal_fraction=o["food"]["meal_fraction"], window=o.get("window"))
        if r is feas[0]: info["rule_terms"] = [f"{x['factor']} {x['value']:+.2f}" for x in sorted(d["reasons"], key=lambda x: -abs(x["value"]))[:6]]
        if o.get("in_package"): info["price_note"] = "객실 요금에 포함"
        cands.append(info)
    blocked = []
    for x in d.get("not_chosen", []):
        if not x.get("feasible"):
            o = by.get(x["id"], {})
            blocked.append(dict(id=x["id"], label=x.get("label"), why=(x.get("blocked") or [o.get("status") or ((o.get("service_contract") or {}).get("blocked_reason")) or "실행 불가(사유 미기록)"])))
    persona = _dedupe_persona(LLmod._persona_block(a, []))
    paid = {(x.get("t"), x.get("act")): x["krw"] for x in (getattr(a, "charges", []) or []) if x.get("krw")}
    stay_meals = _stay_meals(a, by)
    prev_days = [dict(t=x["t"], what=x["label"], paid_krw=paid.get((x["t"], x["act"]))) for x in a.log if x.get("meal_slot") or x["act"] in ("WINE_FAIR",)][-8:]
    packet = dict(customer=persona, visit_purpose=f"{persona.get('type') or ''} · {getattr(a, 'N', 1)}인" + (" · 아이 동반" if (a.C or {}).get("kids") else ""),
                  stay=dict(date=a.sc.get("date"), weekday="월화수목금토일"[date.fromisoformat(a.sc["date"]).weekday()], now=_mh(t), meals_this_stay=stay_meals,
                            recent_meals_and_events=prev_days, spent_so_far_krw=int(a.spent), party_size=getattr(a, "N", 1), building=getattr(a, "B", None)),
                  rule_engine=dict(choice=feas[0]["offer"], why_review=[TRIG_KO.get(x, x) for x in trig] + (["후기에 아침 · 조식 관련 사실 있음: " + ", ".join(bf[:4])] if bf else [])),
                  candidates=cands, not_available=blocked,
                  question=("아침입니다. 규칙 엔진은 아침 끼니 해결을 고정 가치로 두어 거의 항상 룸서비스 조식을 고릅니다. 이 사람의 후기(조식을 건너뛰었는지 · 조식 가치를 어떻게 봤는지 · 늦잠 · 브런치) "
                            "와 동행 · 어제 저녁 · 오늘 체크아웃 여부를 보고, 실제로 아침을 어떻게 해결할지 판단하세요. 건너뛰기 · 가볍게 빵 · 룸서비스 · 뷔페 어느 쪽도 그 사람에게 이유가 있으면 자연스럽습니다. "
                            "선택지에 더뷔페 조식이 없으면 그 이유(가격 미확인 · 시간)는 주어진 정보로만 판단하세요."))
    if 'recorded_memory' not in packet['stay']:packet['stay']['recorded_memory']=recorded_memory(a,t)
    ans, rec = call(packet, c)
    adopted, outcome = arbitrate(ans, feas, c)
    entry = dict(version=VERSION, customer_id=a.pid, date=a.sc.get("date"), time=_mh(t), turn=turn, triggers=trig, rule_choice=feas[0]["offer"],
                 llm=ans, outcome=outcome, final=adopted or feas[0]["offer"], call=rec,
                 rule_label=(by.get(feas[0]["offer"]) or {}).get("label"), final_label=(by.get(adopted or feas[0]["offer"]) or {}).get("label"), packet=packet)
    if out:
        with open(Path(out) / "HYBRID_REVIEW.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    d = dict(d, hybrid_review={k: v for k, v in entry.items() if k != "packet"})
    if adopted:
        o = by[adopted]
        d["rule_chosen"] = d["chosen"]
        sc = next((r["total"] for r in feas if r["offer"] == adopted), 0.0)
        d["chosen"] = dict(id=o["id"], label=o["label"], price_pp_krw=o["price_pp_krw"], score=sc, catalog=o.get("catalog"), price_note=o["price_source"]["note"])
        d["not_chosen"] = [x for x in d.get("not_chosen", []) if x["id"] != adopted] + [dict(id=d["rule_chosen"]["id"], label=d["rule_chosen"]["label"], price_pp_krw=d["rule_chosen"]["price_pp_krw"], feasible=True, score=d["rule_chosen"].get("score"), blocked=[], catalog=d["rule_chosen"].get("catalog"))]
        d["reasons"] = [dict(factor="하이브리드 검토: " + (ans.get("summary") or "")[:80], value=0.0, facet=None, fact_ids=sorted({f for r in ans.get("reasons", []) for f in r.get("fact_ids", [])}), note="LLM 판단 채택")]
    return d


# ---------- 점심(계획기) 검토 — 10/30: 점심은 계획기 추첨 + 업장 안 상품 추첨으로만 정해져 LLM 이 한 번도 보지 않았다.
#   blog42 v12t: 봉골레 1일 저녁 → 2일 점심 → 3일 점심(3연속). 같은 메뉴 · 같은 곳 반복일 때만 판단을 묻는다(새 계수 없음).
def review_lunch(a, t, code, chosen, alts, offers_by_id=None, LLmod=None):
    """chosen = dict(id, label, venue, price_pp) · alts = [dict(id, code, label, venue, price_pp, weight, kind)] (chosen 포함).
    반환: (채택 id 또는 None, 기록)."""
    c = cfg()
    if c["mode"] == "off": return None, None
    meals = _stay_meals(a, offers_by_id or {})
    core = (chosen.get("label") or "").split(" · ")[0].strip()
    trig = []
    if core and any(core in (m.get("what") or "") for m in meals): trig.append("REPEAT_MENU")
    if chosen.get("venue") and any(m.get("venue") == chosen["venue"] for m in meals): trig.append("REPEAT_VENUE")
    # 저녁 검토와 같은 PRICE_GAP 기준: 후기에 가격 판단 사례가 있는 고객이 가장 싼 확인 가격의 2배 이상을 고른 경우
    price_fact = any(re.search(r"가격|비싸|원이라|만원|가성비|할인", (v or {}).get("gist", "")) for v in (a.traits.get("evidence_index") or {}).values())
    priced = [x.get("price_pp") for x in alts if isinstance(x.get("price_pp"), (int, float)) and x.get("price_pp") > 0]
    if price_fact and isinstance(chosen.get("price_pp"), (int, float)) and priced and chosen["price_pp"] >= 2 * min(priced): trig.append("PRICE_GAP")
    if not trig or len(alts) < 2: return None, None
    if LLmod is None:
        from operator_choice.autonomy_v1 import llm_layer as LLmod
    alts = [chosen_row for chosen_row in alts if chosen_row["id"] == chosen["id"]] + [x for x in alts if x["id"] != chosen["id"]]
    cands = []
    for i, x in enumerate(alts[:16]):
        info = dict(id=x["id"], label=x["label"], kind=x.get("kind"), rule_rank=i + 1, planner_weight=round(x.get("weight") or 0, 3),
                    price_pp_krw=x.get("price_pp") if x.get("price_pp") is not None else "미확인")
        if x.get("venue"): info["building"] = BUILDING_KO.get(LLmod.SP.BLDG_OF.get(x["venue"], ""), LLmod.SP.BLDG_OF.get(x["venue"], ""))
        if x.get("venue") and VIEW.get(x["venue"]): info["view"] = VIEW[x["venue"]]
        if x.get("note"): info["note"] = x["note"]
        cands.append(info)
    persona = _dedupe_persona(LLmod._persona_block(a, []))
    today = [dict(t=x["t"], what=x["label"]) for x in a.log if x["act"] not in ("move", "wait")][-10:]
    checked_out = bool(getattr(a, "checked_out", False))
    packet = dict(customer=persona, visit_purpose=f"{persona.get('type') or ''} · {getattr(a, 'N', 1)}인" + (" · 아이 동반" if (a.C or {}).get("kids") else ""),
                  stay=dict(date=a.sc.get("date"), weekday="월화수목금토일"[date.fromisoformat(a.sc["date"]).weekday()], now=_mh(t), meals_this_stay=meals,
                            today_so_far=today, checked_out=checked_out, party_size=getattr(a, "N", 1), spent_so_far_krw=int(a.spent)),
                  rule_engine=dict(choice=alts[0]["id"], why_review=[TRIG_KO.get(x, x) for x in trig],
                                   note="점심은 계획기 가중 추첨 → 업장 안 상품 추첨으로 정해졌습니다(planner_weight 는 추첨 무게 · 점수 순위 아님)."),
                  candidates=cands,
                  question=_question(trig, a, alts[0]["label"], meals) + (" 오늘은 체크아웃한 날입니다 — 떠나기 전 마지막 식사라는 점도 생각하세요." if checked_out else "")
                  + " 같은 업장의 다른 메뉴, 다른 업장, 가볍게(빵 · 카페 · 객실), 건너뛰기 어느 쪽도 이유가 있으면 자연스럽습니다.")
    if 'recorded_memory' not in packet['stay']:packet['stay']['recorded_memory']=recorded_memory(a,t)
    ans, rec = call(packet, c)
    feas = [dict(offer=x["id"], total=x.get("weight") or 0) for x in alts]
    adopted, outcome = arbitrate(ans, feas, c, cands)
    _lab = {x["id"]: x["label"] for x in alts}
    entry = dict(version=VERSION, customer_id=a.pid, date=a.sc.get("date"), time=_mh(t), turn="lunch", triggers=trig, rule_choice=alts[0]["id"],
                 llm=ans, outcome=outcome, final=adopted or alts[0]["id"], call=rec,
                 rule_label=_lab.get(alts[0]["id"]), final_label=_lab.get(adopted or alts[0]["id"]), packet=packet)
    out = STATE.get("out")
    if out:
        with open(Path(out) / "HYBRID_REVIEW.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return adopted, {k: v for k, v in entry.items() if k != "packet"}



# ---------- 장면 설명 — 10/30 관제 1번: LLM 이 선택을 바꾼 장면이 규칙 엔진(계획기) 선택의 설명 문장을 달고 있던 결함 ----------
#   새 문장을 꾸미지 않는다: 규칙 선택 → 최종 선택 사실 + LLM 이 실제로 댄 이유(후기 근거 · 상황 · 업장 정보) 원문만 옮긴다.
REASON_ORDER = {"후기 근거": 0, "상황": 1, "업장 정보": 2}


def _josa(word, a, b):
    w = (word or "").strip()
    if not w: return a
    c = w[-1]
    if "가" <= c <= "힣":
        jong = (ord(c) - 0xAC00) % 28
        if a == "으로" and jong == 8: return b   # ㄹ 받침 + 로
        return a if jong else b
    return b


def _short(label):
    return re.sub(r" · (기존 메뉴 기준 가상 계산|기존 공식 메뉴 기준 가상.*|상품 조건 확인|상품/금액 미확인)$", "", (label or "").strip())


def adopted(entry):
    return bool(entry) and "ADOPTED" in str(entry.get("outcome"))


def scene_explain(entry, valid_fact_ids=None):
    """반환 (why, 인용 fact_ids, 기록). 규칙 선택과 최종 선택, LLM 이유(최대 2개 · 후기 근거 우선)만."""
    ans = entry.get("llm") or {}
    keep = sorted([r for r in ans.get("reasons", []) if r.get("type") in REASON_ORDER], key=lambda r: REASON_ORDER[r["type"]])[:2]
    rule, fin = _short(entry.get("rule_label") or entry.get("rule_choice")), _short(entry.get("final_label") or entry.get("final"))
    why = f"규칙 엔진은 {rule}{_josa(rule, '을', '를')} 골랐지만, 검토 결과 {fin}{_josa(fin, '으로', '로')} 정했습니다. " + " ".join(r["text"].strip() for r in keep)
    fids = [f for r in keep for f in r.get("fact_ids", [])]
    unknown = [f for f in fids if valid_fact_ids is not None and f not in valid_fact_ids]
    fids = [f for f in fids if f not in unknown]
    rec = dict(decided_by="LLM_REVIEW_ADOPTED", rule_choice=entry.get("rule_choice"), final=entry.get("final"), outcome=entry.get("outcome"),
               triggers=entry.get("triggers"), reasons_shown=[dict(type=r["type"], fact_ids=r.get("fact_ids", [])) for r in keep],
               cited_fact_ids_not_in_profile=unknown, confidence=ans.get("confidence"))
    return why.strip(), fids, rec


def scene_record(entry):
    """바꾸지 않은 검토(동의 · 유지)는 설명을 그대로 두고 기록만."""
    if not entry: return None
    status=RI.execution(entry)
    return dict(**status,decided_by=("RULE_ENGINE_LLM_AGREED" if entry.get('outcome')=='AGREE' and status['review_succeeded'] else 'RULE_ENGINE'),rule_choice=entry.get("rule_choice"),
                final=entry.get("final"), outcome=entry.get("outcome"), triggers=entry.get("triggers"), confidence=(entry.get("llm") or {}).get("confidence"))
