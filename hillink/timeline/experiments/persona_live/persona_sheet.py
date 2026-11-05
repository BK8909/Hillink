"""고객 카드 v1 → 페르소나 시트(자연어 · 근거 층 표시) (10/20 · 총괄 C · 격리)

카드 A(사람 사실 확인)만 쓴다. 블로그 원문 · URL · 작성자 정보는 카드에 없고 여기서도 만들지 않는다.
ai_traits 는 unreviewed 라 기본으로 넣지 않는다(include_ai_traits=True 로 넣으면 '검수 안 된 자동 추정' 표시).

시트는 세 층으로 적는다 — 페르소나가 판단할 때 무엇이 '기억'이고 무엇이 '해석'인지 알게 하기 위해서다.
  [관측]      원문에서 직접 확인된 사실 (provenance=observed)
  [사람 추론] 사람이 단서를 결합한 해석 (human_inference)
  [미상]      확인되지 않은 것 — 0 이나 비선호로 바꾸지 않는다
"""
from __future__ import annotations

import json
from pathlib import Path

CARDS = Path(__file__).resolve().parents[2] / "group_inputs_v1" / "cards" / "customer_card_pairs_v1.json"

PLACE = {
    "GRAND_FRONT_DESK": "그랜드 워커힐 프런트", "GRAND_ROOM": "그랜드 객실", "VISTA_ROOM": "비스타 객실", "DOUGLAS_ROOM": "더글라스 하우스 객실", "DOUGLAS_LOBBY": "더글라스 하우스 로비",
    "GRAND_POOL": "그랜드 실내 수영장", "VISTA_POOL": "비스타 실내 수영장", "RIVERPARK": "리버파크(야외 수영장)", "FOREST_PARK": "포레스트 파크(야외 피크닉 공간)", "SKYARD": "스카이야드(족욕 · 루프탑)",
    "FITNESS": "피트니스", "GRAND_LIBRARY": "그랜드 라이브러리", "THEATRE_OF_LIGHT": "빛의 시어터(미디어아트 전시)",
    "THE_BUFFET": "더뷔페(한강 조망 뷔페)", "PIZZA_HILL": "피자힐(한강 조망 피자 레스토랑)", "MYONGWOLGWAN": "명월관(한우 구이)", "ONDAL": "온달(한식)", "GEUMRYONG": "금룡(중식)", "MOEGI": "모에기(일식)",
    "THE_PAVILION": "더파빌리온(카페 · 브런치)", "LE_PASSAGE": "르파사쥬(베이커리 · 델리)", "LUX_BAR": "럭스 바(16층 바 · 재즈 라이브)", "GRAND_CLUB_LOUNGE": "그랜드 클럽 라운지", "DOUGLAS_LOUNGE": "더글라스 라운지",
    "PARKING_TOWER": "주차 타워", "GRAND_LOBBY": "그랜드 로비", "GANGBYEON_STN": "강변역(셔틀)",
}
MEAL = {"breakfast": "조식", "lunch": "점심", "dinner": "저녁", "brunch": "브런치", "snack": "간식", "drinks": "음료 · 술", "unknown": "끼니 미상", None: ""}
KIND = {"checkin": "체크인", "stay": "투숙", "facility": "이용", "meal": "식사", "wait": "줄 서서 기다림", "abandonment": "기다리다 포기", "purchase": "구매", "transport": "이동"}
COMP = {"writer, spouse, two children": "작성자 · 배우자 · 아이 둘(나이 미상)", "writer, parents, sibling": "작성자 · 부모님 · 형제자매(모두 성인으로 추론)", "solo": "혼자",
        "mother and adult daughter": "어머니와 성인 딸", "mother and adult child": "어머니와 성인 자녀", "two adults and three children": "성인 둘과 아이 셋",
        "anniversary couple and children": "기념일을 맞은 부부와 아이들", "writer and companion": "작성자와 동행 1명"}
PURPOSE = {"family_hotel_stay": "가족 호텔 숙박", "indoor_pool": "실내 수영장", "breakfast": "조식", "quiet_rest": "조용한 휴식", "family_stay": "가족 숙박", "dining": "식사", "conversation": "대화",
           "lunar_new_year_family_trip": "설 연휴 가족 여행", "hotel_exploration": "호텔 구석구석 둘러보기", "birthday_hotel_stay": "생일 기념 숙박", "club_lounge": "클럽 라운지", "buffet": "뷔페",
           "family_summer_vacation": "여름 가족 휴가", "riverpark": "리버파크", "anniversary_family_dinner": "기념일 가족 저녁", "special_buffet_meal": "특별한 뷔페 식사",
           "post_event_late_checkin": "행사 뒤 늦은 체크인", "spa_room": "스파 객실", "morning_facilities": "아침 시설 이용", "hotel_facility_exploration": "호텔 시설 두루 이용"}
PREF = {"view_enjoyment": "조망을 즐김", "low_view_priority": "객실 조망은 크게 신경 쓰지 않음", "broad_facility_use": "시설을 두루 이용함", "on_property_convenience": "호텔 밖으로 나가지 않고 안에서 해결하는 편의를 중시",
        "quiet_conversation": "조용히 대화할 수 있는 자리를 선호", "quiet_rest": "조용한 휴식을 선호", "private_room": "별실을 선호", "view_walk": "조망을 보며 걷는 것을 좋아함", "view_seating": "조망 좌석을 원함",
        "club_benefits_over_room_view": "객실 조망보다 클럽 혜택을 택함", "window_seat": "창가 자리를 원함", "river_view_room": "한강 조망 객실을 선호", "river_view_seat": "한강 조망 좌석을 원함", "repeat_visit": "다시 찾음",
        "window_seat_enjoyment": "창가 자리를 즐김", "river_view_hotel": "한강 조망 호텔을 택함"}
SCOPE = {"breakfast_seating": "조식 자리", "room_view": "객실 조망", "stay": "체류 전반", "itinerary": "일정", "dining": "식사", "evening": "저녁 시간", "buffet": "뷔페", "room_choice": "객실 선택",
         "breakfast": "조식", "room": "객실", "restaurant_seating": "식당 좌석", "hotel_choice": "호텔 선택", "PIZZA_HILL": "피자힐"}
CONSTRAINT = {"childcare_load": "아이를 돌보는 부담이 있음", "buffet_closing_deadline": "뷔페 마감 시각에 걸림", "child_companion": "아이 동반", "arrival_after_event": "행사 뒤 늦게 도착", "sun_exposure": "햇볕 노출을 꺼림", "children_water_safety": "아이 물놀이 안전"}
ENTITLE = {"THE_BUFFET_BREAKFAST": "더뷔페 조식", "THEATRE_OF_LIGHT_TICKET": "빛의 시어터 입장권", "DOUGLAS_LOUNGE_BREAKFAST_AND_HAPPY_HOUR": "더글라스 라운지 조식 · 더글라스 아워(저녁 와인 · 치즈)"}
PROV = {"observed": "관측", "human_inference": "사람 추론", "unknown": "미상", "ai_estimate": "자동 추정", "scenario_assumption": "시나리오 가정"}


def load_cards() -> dict:
    return {c["blog_id"]: c for c in json.loads(CARDS.read_text(encoding="utf-8"))["cards"]}


def _ids(x: dict) -> str:
    ids = [i for i in x.get("evidence_ids", []) if ":" in i or i.startswith("H")]
    return f" (근거 {', '.join(ids)})" if ids else ""


def _p(x: dict) -> str:
    return f"[{PROV.get(x.get('provenance'), x.get('provenance', '미상'))}]"


def _season(v) -> str:
    if not v: return "시기 미상"
    if isinstance(v, dict): v = v.get("earliest") or str(v)
    v = str(v)
    m = {"01": "1월", "02": "2월", "03": "3월", "04": "4월", "05": "5월", "06": "6월", "07": "7월", "08": "8월", "09": "9월", "10": "10월", "11": "11월", "12": "12월"}
    return (v[:4] + "년 " + m.get(v[5:7], "")).strip() + (" 하순" if "late" in v else "")


def build_sheet(card: dict, include_ai_traits: bool = False) -> dict:
    a = card["a_card"]
    party = a["party"]["composition"].get("value")
    size = a["party"]["size"].get("value")
    L = []
    L.append(f"동행: {COMP.get(party, party or '미상')}{f' · {size}명' if size else ''} {_p(a['party']['composition'])}{_ids(a['party']['composition'])}")
    pu = a["purpose"]
    L.append(f"그때의 방문 목적: {' · '.join(PURPOSE.get(v, v) for v in pu.get('value') or []) or '미상'} {_p(pu)}{_ids(pu)}")
    ov = a["observed_visit"]
    prop = {"GRAND": "그랜드 워커힐", "VISTA": "비스타 워커힐", "DOUGLAS": "더글라스 하우스"}.get(ov.get("property"), ov.get("property"))
    L.append(f"그때의 방문: {prop} · {ov.get('nights')}박 · {_season(ov['check_in'].get('value'))} {_p(ov['check_in'])}" + (f" · 도착 {ov['check_in_time']['value']}쯤" if isinstance(ov['check_in_time'].get('value'), str) else ""))
    if a["entitlements"]:
        L.append("그때 패키지에 포함돼 있던 것(지난 방문의 조건 — 이번 방문에는 적용되지 않음): " + " · ".join(f"{ENTITLE.get(e['item'], e['item'])} {e.get('quantity', '')}{'인분' if e.get('quantity') else ''}{_ids(e)}" for e in a["entitlements"]) + " [관측]")
    if a["reservations"]:
        L.append("그때 미리 예약한 것(지난 방문): " + " · ".join(f"{PLACE.get(r['venue'], r['venue'])} {MEAL.get(r.get('meal'), '')}{(' ' + r['session'] + '부') if r.get('session') else ''}{_ids(r)}" for r in a["reservations"]) + " [관측]")
    mem = []
    for e in a["observed_events"]:
        if e["kind"] in ("checkin", "transport"): continue
        what = KIND.get(e["kind"], e["kind"])
        meal = MEAL.get(e.get("meal"), e.get("meal") or "")
        mem.append(f"{PLACE.get(e['place'], e['place'])}{(' · ' + meal) if meal else ''} — {what}{_ids(e)}")
    if mem:
        L.append("그때 실제로 한 일 [관측]: " + " / ".join(mem))
    prefs = [f"{PREF.get(p['feature'], p['feature'])}({SCOPE.get(p.get('scope'), p.get('scope'))}){_ids(p)}" for p in a["explicit_preferences"]]
    if prefs:
        L.append("그때 스스로 적은 취향 [관측]: " + " · ".join(prefs))
    cons = [f"{CONSTRAINT.get(c['feature'], c['feature'])} {_p(c)}{_ids(c)}" for c in a["constraints"]]
    if cons:
        L.append("사정 · 제약: " + " · ".join(cons))
    if a.get("human_inferences"):
        L.append("사람 검수자의 메모 [사람 추론]: " + " / ".join(f"{h['field']}: {h.get('note') or h.get('value')}" for h in a["human_inferences"]))
    if a["unknowns"]:
        L.append("확인되지 않은 것 [미상] (모른다고 두고 판단할 것): " + " · ".join(a["unknowns"]))
    if include_ai_traits and a.get("ai_traits"):
        vals = {k: v for k, v in a["ai_traits"].get("values", {}).items() if v is not None}
        L.append(f"검수 안 된 자동 추정 성향(참고만): {vals}")
    kids = any(k in (party or "") for k in ("child", "children"))
    return dict(blog_id=card["blog_id"], party=party, size=size, has_children=kids, property=ov.get("property"), nights=ov.get("nights"),
                text="\n".join("- " + s for s in L), evidence_ids=sorted({i for p in a["explicit_preferences"] for i in p.get("evidence_ids", [])} | {i for e in a["observed_events"] for i in e.get("evidence_ids", [])}))


if __name__ == "__main__":
    import sys
    cards = load_cards()
    for b in sys.argv[1:] or [k for k, c in cards.items() if c.get("selection_status") == "selected"][:3]:
        s = build_sheet(cards[b]); print(f"=== {b}\n{s['text']}\n")
