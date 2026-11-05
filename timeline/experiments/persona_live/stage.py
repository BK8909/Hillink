"""무대 — 날짜 · 건물 · 동행에 맞는 실제 워커힐 선택지 (10/20 · 총괄 C · 격리)

값은 timeline/place_assumptions.csv · timeline/menu.csv 에서 읽는다(◎ 공식 · ○ 후기/보도 · △ 추정). 표에 없는 값은 '미상'으로 적고 만들지 않는다.
가상 선택지(VIRTUAL)는 실제 제공이 아니며 이름 앞에 [가상] 을 붙인다. 조건 변경(비 · 가격 배수 · 동행 변경)도 [가상 조건] 으로 적는다.
"""
from __future__ import annotations

import csv, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_PA = list(csv.DictReader(open(ROOT / "place_assumptions.csv", encoding="utf-8-sig")))
_MENU = list(csv.DictReader(open(ROOT / "menu.csv", encoding="utf-8-sig")))


def pa(code: str, item: str) -> tuple[str, str]:
    """place_assumptions 값 · 등급. 없으면 예외 — 무대는 표에 있는 값만 쓴다."""
    for r in _PA:
        if r["장소코드"] == code and r["항목"] == item:
            return r["값"], r["등급"]
    raise KeyError(f"place_assumptions 에 없음: {code} / {item}")


def menu(shop: str, item: str) -> tuple[int, str, str]:
    for r in _MENU:
        if r["업장"] == shop and r["상품"] == item:
            return int(r["단가"]), r["단위"], r["등급"]
    raise KeyError(f"menu 에 없음: {shop} / {item}")


def won(x: int | float) -> str:
    return f"{int(round(x)):,}원"


VIRTUAL = {
    "buffet_fall_window": dict(
        name="[실험용 가상 선택지 · 이번 방문엔 실제로 있다고 가정] 더뷔페 '가을 창가 조망 디너' 안내", slot="저녁 식사", venue="THE_BUFFET",
        text="늦가을 한강 · 아차산 단풍을 보는 창가 자리를 예약 때 요청할 수 있다고 안내(보장은 아님). 메뉴 · 가격은 평소 석식과 같음.",
        source="persona_market ANALYSIS_20261020 의 검토 아이디어 — 실제 제공 아님"),
    "beer_terrace": dict(
        name="[실험용 가상 선택지 · 이번 방문엔 실제로 있다고 가정] 피자힐 테라스 맥주 행사", slot="저녁 식사", venue="PIZZA_HILL",
        text="17:00~21:00 테라스에서 맥주와 피자(가정 행사 · 가격 · 대상 미상).",
        source="persona_lab conditions.BEER_EVENT 가정 행사 — 실제 운영 근거 없음"),
}

VISIT_TERMS = "객실만 예약했다. 패키지 전용 혜택(포함 조식 · 입장권 · 식사권)은 이번 숙박에 없다(지난 방문의 패키지 혜택은 이번엔 없음). 객실 유형에 딸린 기본 제공(예: 더글라스 객실의 라운지 조식 · 스낵 · 더글라스 아워)과 투숙객 무료 시설은 그대로 쓸 수 있다. 미리 예약한 식사도 없다(원하면 현장 · 전화 예약). 비용은 모두 우리가 낸다. 예산 상한은 정해 두지 않았다."
SLOTS = ["체크인 뒤 오후(15:00~18:00)", "저녁 식사", "저녁 이후(20:00~)", "다음 날 아침(퇴실 11:00 전)"]


def build_stage(date: str, property: str, has_children: bool, modifiers: dict | None = None) -> dict:
    m = modifiers or {}
    d = datetime.date.fromisoformat(date)
    nxt = d + datetime.timedelta(days=1)
    wd = d.weekday()            # 0=월
    wk = ["월", "화", "수", "목", "금", "토", "일"]
    weekend = wd >= 5
    md = date[5:]
    closed = set(m.get("close", []))
    weather = m.get("weather")
    opts: list[dict] = []
    notes: list[str] = []

    def add(code, name, slot, text, price, grade, source, virtual=False):
        opts.append(dict(code=code, name=name, slot=slot, text=text, price=price, grade=grade, source=source, virtual=virtual))

    # ---- 오후 활동
    gold = "07-17" <= md <= "08-30"; blue = "06-26" <= md <= "07-16"
    if (gold or blue) and "RIVERPARK" not in closed:
        if gold and wd >= 4:
            ad, ch = int(pa("RIVERPARK", "1부 성인 (2026)")[0]), int(pa("RIVERPARK", "1부 어린이 (2026)")[0]); hrs = "1부 10:00~18:00"
        elif gold:
            ad, ch = int(pa("RIVERPARK", "골드 월~목 성인 (2026)")[0]), int(pa("RIVERPARK", "골드 월~목 어린이 (2026)")[0]); hrs = "10:00~20:00"
        else:
            ad, ch = int(pa("RIVERPARK", "블루 성인 (2026)")[0]), int(pa("RIVERPARK", "블루 어린이 (2026)")[0]); hrs = "10:00~20:00"
        mult = float(m.get("riverpark_price_mult", 1))
        tag = (f" [가상 조건: {m['riverpark_price_note']}]" if m.get("riverpark_price_note") else f" [가상 조건: 요금 {mult:g}배]") if mult != 1 else ""
        add("RIVERPARK", "리버파크(야외 수영장 · 투숙객 전용 유료)", SLOTS[0],
            f"{hrs} · 메인풀 50m×19m · 객실당 1박 1회 · 선베드 객실당 2개{tag}",
            f"성인 {won(ad*mult)} · 어린이 {won(ch*mult)} (1인)", "◎", "place_assumptions RIVERPARK")
    elif "RIVERPARK" in closed:
        notes.append("리버파크(야외 수영장)는 이 날 운영하지 않는다 [가상 조건]")
    else:
        notes.append("리버파크(야외 수영장)는 여름 시즌(6/26~8/30)에만 운영 — 이 날은 운영하지 않음")
    if property in ("GRAND", "DOUGLAS"):
        add("GRAND_POOL", "그랜드 실내 수영장", SLOTS[0], f"{pa('GRAND_POOL','운영')[0]} · 투숙객 무료(객실당 성인 2 + 영유아 2) · 1회 {pa('GRAND_POOL','1회 이용 시간 상한')[0]}분 상한" + (" · 더글라스 투숙객의 이용 조건은 미확인" if property == "DOUGLAS" else ""),
            "무료(초과 인원 1인 20,000원 △)", "◎", "place_assumptions GRAND_POOL")
    else:
        add("VISTA_POOL", "비스타 실내 수영장", SLOTS[0], f"{pa('VISTA_POOL','운영')[0]} · 투숙객 무료(객실당 4명)", "무료", "◎", "place_assumptions VISTA_POOL")
    winefair_days = pa("FOREST_PARK", "와인페어 운영 날짜 · 2026")[0].split(",")
    if md in winefair_days:
        add("WINE_FAIR", "와인페어 '구름 위의 산책'(포레스트 파크)", SLOTS[0],
            f"1부 {pa('FOREST_PARK','와인페어 운영 · 1부')[0]} · 2부 {pa('FOREST_PARK','와인페어 운영 · 2부')[0]} · 와인 수입사 20곳 · 700여 종 시음 · 입장권에 리델 글라스 · 칠링백 · 푸드 교환권 1매 포함 · 1부는 성인 동반 어린이 무료 · 야외",
            f"투숙객 무료 · 외부 성인 {won(int(pa('FOREST_PARK','와인페어 입장료 · 성인')[0]))} · 아동 {won(int(pa('FOREST_PARK','와인페어 입장료 · 아동')[0]))} · VIP 테이블(4인) {won(int(pa('FOREST_PARK','와인페어 VIP TABLE (4인)')[0]))}", "◎", "place_assumptions FOREST_PARK 와인페어")
        notes.append("이 날 포레스트 파크는 와인페어 행사장이라 일반 피크닉 입장이 제한된다")
    elif md not in pa("FOREST_PARK", "입장 제한일 · 2026")[0].split(","):
        add("FOREST_PARK", "포레스트 파크(야외 피크닉 · 산책 공간 · 투숙객 전용)", SLOTS[0], f"{pa('FOREST_PARK','운영')[0]}(7/1~9/27 은 21:00 까지) · 객실당 4명 무료 · 텐트 대여 시간당 {won(int(pa('FOREST_PARK','텐트 이용료')[0]))}", "무료(텐트 별도)", "◎", "place_assumptions FOREST_PARK")
    if md not in pa("THEATRE_OF_LIGHT", "휴관일 · 2026")[0].split(","):
        add("THEATRE_OF_LIGHT", "빛의 시어터(실내 미디어아트 전시)", SLOTS[0], f"{pa('THEATRE_OF_LIGHT','운영')[0]} · 입장 마감 17:00 · 회차 60분",
            f"성인 {won(int(pa('THEATRE_OF_LIGHT','입장권 · 성인')[0]))} · 어린이 {won(int(pa('THEATRE_OF_LIGHT','입장권 · 어린이')[0]))} · 영유아 무료", "◎", "place_assumptions THEATRE_OF_LIGHT")
    else:
        notes.append("빛의 시어터는 이 날 휴관")
    add("SKYARD", "스카이야드(비스타 4층 야외 족욕 · 루프탑 바)", SLOTS[0], f"{pa('SKYARD','운영')[0]} · 바 {pa('SKYARD','바 운영 · 금~일')[0] if weekend else pa('SKYARD','바 운영 · 월~목')[0]}" + ("" if property == "VISTA" else " · 비스타 투숙객이 아니면 객실당 19,000원(○ · 공식 표기 없음)"), "비스타 투숙객 무료 · 그 외 19,000원/객실 ○", "◎/○", "place_assumptions SKYARD")
    add("WALK", "호텔 경내 산책(아차산 자락 · 한강 조망 산책로)", SLOTS[0], "비용 없음 · 가을엔 단풍, 봄엔 벚꽃 시기" + (" · 비 오는 날엔 불편" if weather == "비" else ""), "무료", "○", "SNS 표본 IG06 · 보도")
    add("REST", "객실에서 쉬기", SLOTS[0], "체크인 15:00 · 퇴실 11:00", "무료", "◎", "place_assumptions 체크인 · 체크아웃")
    add("FITNESS", "피트니스 · 사우나", SLOTS[0], f"사우나 {pa('WELLNESS_SAUNA','운영')[0]} · 17세 이상", f"사우나 {won(int(pa('WELLNESS_SAUNA','요금 (그랜드 피트니스 안)')[0]))}/인", "◎", "place_assumptions WELLNESS_SAUNA")
    pav_hi = "09-01" <= md <= "11-30"
    if pav_hi:
        p, u, g = menu("파빌리온", "가을 디저트 FALL IN PAVILION")
        add("THE_PAVILION_TEA", "더파빌리온 가을 디저트 세트(카페)", SLOTS[0], "11:00~20:00 · 2인 세트 · 1인 추가 49,000원", f"{won(p)} ({u})", g, "menu 파빌리온")
    if md <= "10-11":
        p, u, g = menu("파빌리온", "시그니처 빙수"); add("THE_PAVILION_BINGSU", "더파빌리온 빙수(카페)", SLOTS[0], "10:00~20:00", f"{won(p)} (1그릇)", g, "menu 파빌리온")

    # ---- 저녁 식사
    dec = md >= "12-01"
    if dec:
        ad, ch = int(pa("THE_BUFFET", "중식 · 석식 성인 · 12월")[0]), int(pa("THE_BUFFET", "중식 · 석식 어린이 · 12월")[0]); ses = f"1부 {pa('THE_BUFFET','운영 · 석식 · 12월 · 월~일 1부')[0]} · 2부 {pa('THE_BUFFET','운영 · 석식 · 12월 · 월~일 2부')[0]}"
    else:
        ad, ch = int(pa("THE_BUFFET", "중식(주말) · 석식 성인")[0]), int(pa("THE_BUFFET", "중식(주말) · 석식 어린이")[0])
        ses = (f"1부 {pa('THE_BUFFET','운영 · 석식 · 토·공휴일 1부')[0]} · 2부 {pa('THE_BUFFET','운영 · 석식 · 토·공휴일 2부')[0]}" if wd == 5 else pa("THE_BUFFET", "운영 · 석식 · 월~금·일")[0])
    add("THE_BUFFET_D", "더뷔페 저녁(한강 조망 뷔페 · 비스타 1층)", SLOTS[1], f"{ses} · 홀 288석 · 테라스 50석 · 주말엔 회차제 · 투숙객 할인 주말 10% △", f"성인 {won(ad)} · 어린이 {won(ch)} (1인 · 표의 10~11월 값{' · 8월 값은 미확인' if md < '10-01' else ''})" if not dec else f"성인 {won(ad)} · 어린이 {won(ch)} (12월)", "◎", "place_assumptions THE_BUFFET")
    p2, _, _ = menu("피자힐", "커플 세트"); p4, _, _ = menu("피자힐", "콰트로 세트"); pl, _, _ = menu("피자힐", "콤비네이션 피자 L"); pp, _, _ = menu("피자힐", "봉골레 파스타")
    fall = " · 가을 한정 '참송이 모둠 버섯 피자'(보도 ○)" if "09-21" <= md <= "10-31" else ""
    add("PIZZA_HILL", "피자힐(한강 · 아차산 조망 피자 레스토랑 · 언덕 위)", SLOTS[1], f"회차 90분 · 1부 11:30 … 7부 20:30 · 실내 96석 · 저녁 인기 회차 17:30 · 19:00{fall} · 호텔 안 언덕 위 별도 건물(순환 셔틀 ○)", f"2인 세트 {won(p2)} · 4인 세트 {won(p4)} · 피자 L {won(pl)} · 파스타 {won(pp)}", "◎", "menu 피자힐")
    mg, _, _ = menu("명월관", "양념갈비"); mj, _, _ = menu("명월관", "한우 양념갈비 정식")
    extra = ""
    if md in menu_days("명월관", "명월관 가든 BBQ · 성인"):
        extra = f" · 이 날 저녁 '명월관 가든 BBQ' 야외(성인 {won(menu('명월관','명월관 가든 BBQ · 성인')[0])} · 초등 {won(menu('명월관','명월관 가든 BBQ · 초등학생')[0])} · 미취학 {won(menu('명월관','명월관 가든 BBQ · 미취학')[0])} · 사전 유선 예약)"
    add("MYONGWOLGWAN", "명월관(한우 숯불구이 · 별채 · 룸)", SLOTS[1], f"17:30~21:00 · 룸 9개(최소 결제 300,000원 △) · 가을 한정 '능이버섯 등심 불고기 한상'은 평일 점심만{extra}", f"양념갈비 {won(mg)}/1인분 · 정식 {won(mj)}/1인", "◎", "menu 명월관")
    og, _, _ = menu("온달", "궁중상차림"); ok, _, _ = menu("온달", "어린이반상")
    add("ONDAL", "온달(한식 · 별실 5실)", SLOTS[1], "18:00~21:00 · " + ("주말 · 공휴일은 코스만(2인 이상) · 별실은 코스 주문 시" if weekend else f"가을 한정 '가을바다 꽃게 정찬' {won(menu('온달','가을바다 꽃게 정찬 (가을 한정)')[0])}/1인(2인 이상 · 10월) · 반상 50,000~95,000원" if "10-01" <= md <= "10-30" else "반상 50,000~95,000원 · 코스 165,000원~"), f"코스 {won(og)}/1인 · 어린이반상 {won(ok)}", "◎", "menu 온달")
    add("GEUMRYONG", "금룡(중식 · 창가 PDR)", SLOTS[1], "18:00~21:00 · " + ("주말 · 공휴일 저녁은 코스만" if weekend else f"가을 한정 코스 '추미진향' {won(menu('금룡','추미진향 (가을 한정)')[0])}/1인") + f" · 창가 PDR 이용료 {won(int(pa('GEUMRYONG','창가 PDR 이용료')[0]))}", f"어린이 메뉴 {won(int(pa('GEUMRYONG','어린이 메뉴 (미취학)')[0]))}", "◎", "place_assumptions GEUMRYONG")
    mo, _, _ = menu("모에기", "아이소우 (가을 한정)") if "09-01" <= md <= "10-30" else (0, "", "")
    add("MOEGI", "모에기(일식 · 철판 · 스시 · 코스)", SLOTS[1], "저녁 코스 · 오마카세 2인 이상 · 카운터 회차 18:00 · 18:30", f"런치 코스 {won(int(pa('MOEGI','코스 · 런치 모에기')[0]))} · 디너 철판 {won(int(pa('MOEGI','철판 · 디너 TOKIMEKI')[0]))} · 어린이 {won(int(pa('MOEGI','어린이 메뉴 (초등생까지)')[0]))}", "◎", "place_assumptions MOEGI")
    lp, _, _ = menu("피자힐", "콤비네이션 피자 L · 포장")
    add("LE_PASSAGE", "르파사쥬 베이커리 · 델리 · 피자 포장(객실에서 먹기)", SLOTS[1], f"매장 {pa('LE_PASSAGE','운영 · 매장')[0]} · 피자 포장 주문 {pa('LE_PASSAGE','운영 · 테이크아웃 피자 주문')[0]} · 포장 20% 할인 · 룸서비스도 있음(가격표 미확인)", f"피자 L 포장 {won(lp)} · 베이커리 가격 미상", "◎/모름", "place_assumptions LE_PASSAGE · menu")
    bp, _, _ = menu("파빌리온", "BEER Platter (SHALL WE CHEERS)"); wp, _, _ = menu("파빌리온", "WINE Platter (SHALL WE CHEERS)")
    add("THE_PAVILION_EVE", "더파빌리온 맥주 · 와인 플래터(카페 · 가벼운 저녁)", SLOTS[1], "09:00~20:00", f"맥주 플래터 {won(bp)} · 와인 1병+플래터 {won(wp)}", "◎", "menu 파빌리온")
    if property == "DOUGLAS":
        add("DOUGLAS_HOUR", "더글라스 라운지 '더글라스 아워'(와인 · 치즈 · 핑거푸드 · 투숙 포함)", SLOTS[1], f"{pa('DOUGLAS_LOUNGE','운영 · 더글라스 아워')[0]} · 객실당 2명 무료 · 가벼운 저녁 대용 가능", "포함", "◎", "place_assumptions DOUGLAS_LOUNGE")
        add("DOUGLAS_SNACK", "더글라스 라운지 오후 스낵(투숙 포함)", SLOTS[0], f"{pa('DOUGLAS_LOUNGE','운영 · 오후 스낵')[0]}", "포함", "◎", "place_assumptions DOUGLAS_LOUNGE")
    add("OUTSIDE", "호텔 밖 식당 · 배달(광장동 · 외부)", SLOTS[1], "호텔은 아차산 자락 언덕 위(도심에서 떨어져 있음)", "미상", "○", "후기 일반")

    # ---- 저녁 이후
    ck, _, _ = menu("럭스바", "칵테일 · 클래식 (알코올)"); kb, _, _ = menu("럭스바", "맥주 · 병 kloud")
    add("LUX_BAR", "럭스 바(그랜드 16층 · 재즈 라이브 ○)", SLOTS[2], "20:00~01:00 · 120석", f"칵테일 {won(ck)} · 맥주 {won(kb)}~", "◎", "menu 럭스바")
    if md in winefair_days:
        add("WINE_FAIR_2", "와인페어 2부(15:30~20:00 · 저녁 겸)", SLOTS[2], "20:00 종료 — 저녁 이후 시간대엔 끝남", "투숙객 무료", "◎", "place_assumptions FOREST_PARK")
    add("REST_EVE", "객실에서 쉬기 · 야경 · 룸서비스", SLOTS[2], "", "무료(룸서비스 별도)", "◎", "—")
    add("WALK_EVE", "저녁 산책(경내 · 조명)", SLOTS[2], "" + (" · 비" if weather == "비" else ""), "무료", "○", "SNS · 후기")

    # ---- 다음 날 아침
    ba, bc = int(pa("THE_BUFFET", "조식 성인")[0]), int(pa("THE_BUFFET", "조식 어린이")[0])
    bses = f"1부 {pa('THE_BUFFET','운영 · 조식 · 토~월·공휴일 1부')[0]} · 2부 {pa('THE_BUFFET','운영 · 조식 · 토~월·공휴일 2부')[0]}" if nxt.weekday() in (5, 6, 0) else pa("THE_BUFFET", "운영 · 조식 · 화~금")[0]
    add("THE_BUFFET_B", "더뷔페 조식(한강 · 해돋이 조망)", SLOTS[3], f"{bses} · 혼잡하면 2부제 · 전날 회차 예약", f"성인 {won(ba)} · 어린이 {won(bc)} (포함 조식이 있으면 그 인원은 무료)", "◎", "place_assumptions THE_BUFFET")
    if property == "DOUGLAS":
        add("DOUGLAS_B", "더글라스 라운지 라이트 조식(투숙 포함)", SLOTS[3], f"{pa('DOUGLAS_LOUNGE','운영 · 라이트 조식')[0]}", "포함", "◎", "place_assumptions DOUGLAS_LOUNGE")
    pb, _, _ = menu("파빌리온", "더파빌리온 브런치")
    add("THE_PAVILION_B", "더파빌리온 브런치", SLOTS[3], "10:00~14:00 (퇴실 11:00 전이면 짧게)", f"{won(pb)}/1인", "◎", "menu 파빌리온")
    add("MORNING_POOL", "아침 수영장 · 산책", SLOTS[3], "실내 수영장 06:00~ · 경내 산책", "무료", "◎", "place_assumptions GRAND_POOL")
    add("SLEEP_IN", "늦잠 · 객실에서 여유", SLOTS[3], "퇴실 11:00", "무료", "◎", "—")

    for k in m.get("virtual", []):
        v = VIRTUAL[k]; add(k, v["name"], v["slot"], v["text"], "평소 석식과 같음" if k == "buffet_fall_window" else "미상", "가상(실험)", v["source"], virtual=True)

    if weather == "비":
        notes.append("[가상 조건] 이 날은 비 예보 — 야외(리버파크 · 포레스트 파크 · 와인페어 · 산책 · 테라스)는 비를 맞거나 운영이 바뀔 수 있다")
    if "09-21" <= md <= "10-31":
        notes.append("가을 축제 '폴 인 워커힐'(9/21~10/31): 단풍 포토 투어 맵 · 음악 벤치 · 시즌 메뉴 · 스탬프 챌린지 · SNS 인증샷 이벤트(경품에 더뷔페 식사권) — 보도 ○")
    head = f"날짜: {date}({wk[wd]}) 체크인 15:00 → {nxt.isoformat()}({wk[nxt.weekday()]}) 퇴실 11:00 · 건물: {dict(GRAND='그랜드 워커힐 서울', VISTA='비스타 워커힐 서울', DOUGLAS='더글라스 하우스(그랜드 안 부티크 · 초등학생 이하 동반 불가)').get(property, property)}"
    head += "\n[이번 방문 조건] " + m.get("visit_terms", VISIT_TERMS)
    if m.get("companions_override"):
        head += f"\n[가상 조건] 이번 방문의 동행: {m['companions_override']}"
    if m.get("extra_note"):
        notes.append(f"[가상 조건] {m['extra_note']}")
    external = list(m.get("external", []))
    return dict(date=date, weekday=wk[wd], property=property, head=head, options=opts, notes=notes, external=external, modifiers=m)


def menu_days(shop: str, item: str) -> list[str]:
    for r in _MENU:
        if r["업장"] == shop and r["상품"] == item:
            return [x.strip() for x in r["요일제한"].replace("지정일", "").split(",") if x.strip()]
    return []


def render(stage: dict) -> str:
    L = [stage["head"], ""]
    for s in SLOTS:
        L.append(f"## {s}")
        for o in stage["options"]:
            if o["slot"] == s:
                L.append(f"- [{o['code']}] {o['name']} — {o['text']} · 가격 {o['price']} · 근거 {o['grade']}")
        L.append("")
    if stage["notes"]:
        L.append("## 이 날의 사정"); L += [f"- {n}" for n in stage["notes"]]
    if stage.get("external"):
        L += ["", "## 참고 정보(외부 · 보조 — 참고만 하고 이것 때문에 고르지는 말 것)"] + [f"- {e}" for e in stage["external"]]
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-10-10"
    prop = sys.argv[2] if len(sys.argv) > 2 else "GRAND"
    print(render(build_stage(date, prop, True, dict(virtual=["buffet_fall_window"]))))
