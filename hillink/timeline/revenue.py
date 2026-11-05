"""
매출 합산 — 에이전트 한 명의 하루를 돈으로 바꿔 레벨 4(고객) → 3(업장) → 2(부문) → 1(전체) 로 쌓는다

  python3 revenue.py             # 개발용 체류 전부 (46편 + ALT) · revenue_result.json · 표 출력
  python3 revenue.py --k 3       # 체류마다 3번 돌려 평균 (tau 확률 선택이라 흔들림을 줄인다)
  python3 revenue.py --l5        # 대표님 온톨로지의 L5 집계행 모양으로 revenue_l5.csv 를 같이 쓴다

10/1 — 대표님 매출 온톨로지(walkerhill-ontology)에 꽂히는 모양으로
  - 순매출 = 결제액 ÷ 1.1 (VAT 10% 차감) 을 같이 낸다. 온톨로지 트리의 숫자가 전부 순매출이라 비교하려면 이게 필요
  - L5 집계행: 구매 날짜 | 성별 | 대표자 연령 | 구성·방문 목적 | AI 유형 | 업장 | 상품 | 구매 수량 | 결제액 | 순매출
    성별 · 연령 · AI 유형은 후기 페르소나에 없어서 "미설정" — 한호(인구통계) · 슬기(호캉스 유형) 축이 붙으면 채워진다
    구성은 지금 아는 사실(인원 · 아동 동반)만 적는다. 온톨로지의 9 목적(커플·기념일 …)으로의 매핑은 추측이라 안 한다

9/30 멘토링에서 대표님이 요구한 것
  - blog01 샘플을 보고: "이 손님이 단계마다 얼마를 썼고 총 매출이 얼마인지가 나와야 한다"
  - 지금 있는 50명 정도로 "하루에 왔다 갔다" 가정하고 객단가 · 회전율 · OCC · ADR · RevPAR 를 내 보라. 텅텅 비어도 거기서부터
  - 가격은 홈페이지 정가, 수용 규모는 공개 자료 · 추산, 회전율 · 점유율 벤치마크는 업계 공개 자료
  - 결과는 영업이익 개선 회의 트리(L1~L3)에 꽂히는 모양으로

어떻게
  1. 체류마다 v4 를 돌려 행동 열(Trace)을 받는다 — 행동 키(buffet_d · pizza_to …)에 prices.PRICE 를 붙인다
  2. 포함 끼니(included_meals)는 객실 요금에 이미 들어 있으니 0 으로 — 두 번 세지 않는다
  3. 한 손님의 지출 줄(시각 · 업장 · 금액 · 등급)을 모으고, 업장(L3) → 부문(L2) → 전체(L1) 로 합산
  4. 지표: 객단가(업장 매출 ÷ 이용 인원) · 좌석 회전(이용 인원 ÷ 좌석) · OCC(판매 객실 ÷ 판매 가능 객실) · ADR · RevPAR
     시간대별(조식 · 중식 · 석식 · 기타) 매출 분포
  5. 등급이 △ 인 가격이 매출의 몇 % 를 차지하는지 같이 낸다 — 이 숫자가 "얼마나 추정에 기대고 있나" 다

가정 (전부 △)
  - 체류 하나 = 객실 하나 (일행이 한 방). 비투숙은 객실 0
  - "하루" = 체류들을 같은 날에 겹쳐 놓는다. 박수는 그대로 (2박이면 객실 매출 2박)
  - 이용 인원 = party_size. 성인 전용(럭스바)은 party_size 그대로 (아동 수를 모름)
"""

from __future__ import annotations

import argparse, importlib, json, random, sys, zlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import agent_v4, fit_v4, menu as menu_mod
from prices import L3, ROOM_L3, ROOMS, SEATS, price_of, net

SEED = 20260930
# 10/14 손님마다 다른 난수 (조정값 rng_team · 기본 꺼짐) — 꺼져 있으면 모든 손님이 같은 난수 줄(Random(SEED))로 확률 선택을 해서
# 같은 차례의 선택이 손님끼리 같은 난수를 쓴다. 켜면 팀 이름으로 난수 줄을 나눠 손님끼리 독립이고, 같은 팀은 상황이 바뀌어도 같은 줄을 쓴다
RNG_TEAM = False
USE_MENU = True     # 10/2 메뉴 선택 층 (menu.py · 소연 상품표). False 면 prices.PRICE 의 업장당 값 하나 (--no-menu)


def spend_lines(m, k=1, capacity=None, menu="default"):
    """한 체류의 지출 줄. k 번 돌리면 금액을 k 로 나눠 평균 (줄은 전부 남김). capacity 는 generate.py 의 좌석 상한 (후기 재현에는 None)
    menu: 메뉴 선택 층 (menu.Menu). "default" 면 USE_MENU 에 따라 menu.csv — 그 날 · 그 시각에 팔리는 상품 하나를 골라 값을 붙인다.
          None 이면 prices.PRICE 의 업장당 값 하나. 후기 날짜가 2026 이전(START_AT 기본값)이면 상품표의 판매 기간이 안 맞으니 날짜만 2026 으로 옮겨 본다"""
    p = m.PERSONA
    start = getattr(m, "START_AT", datetime(2025, 1, 31, 14, 0))
    if menu == "default":
        menu = menu_mod.default() if USE_MENU else None
    incl = {(meal, place) for meal, place in (p.included_meals or ())}
    lines = []
    label2key = {a.label: a.key for a in agent_v4.catalog(p)}   # Trace.chosen 은 라벨
    for i in range(k):
        arng = random.Random((zlib.crc32(("team|" + p.name).encode()) + SEED + i) if RNG_TEAM else SEED + i)
        segs, traces = agent_v4.run_agent(p, start, verbose=False, theta=agent_v4.THETA_FIT, rng=arng, capacity=capacity)
        mrng = random.Random(zlib.crc32(p.name.encode()) + SEED + i)   # 체류마다 고정 — 상품 추첨이 재현되게
        seen_room = False
        for t in traces:
            key = label2key.get(t.chosen, t.chosen)
            if key not in L3:
                continue
            l2, l3 = L3[key]
            if key in ("room", "sleep"):
                if seen_room or not p.is_guest:
                    continue
                seen_room = True
                l3 = ROOM_L3[p.property]
            pr = price_of(key, p.property)
            slot = pr.get("slot", "기타")
            # 포함 끼니 → 0 (객실 요금에 포함)
            place = agent_v4_place(key, p)
            included = any(mm == slot and pl == place for mm, pl in incl)
            if pr["per"] == "person":
                amount = pr["krw"] * p.party_size
            elif pr["per"] == "party":
                amount = pr["krw"]
            else:  # night
                amount = pr["krw"] * max(1, p.nights)
            qty = p.party_size if pr["per"] == "person" else (max(1, p.nights) if pr["per"] == "night" else 1)
            product, grade, note = key, pr["grade"], ""
            if menu is not None and pr["krw"] > 0:
                at = t.start if t.start.year >= 2026 else t.start.replace(year=2026)
                sel = menu.pick(key, p, at, mrng)
                if sel is not None:
                    amount, qty, product, grade = sel["krw"], sel["qty"], sel["product"], sel["grade"]
                    note = sel["note"]
                else:
                    note = "상품표에 없음 · 가격표 값"
            if included:
                amount = 0
                note = "포함 끼니"
            if getattr(t, "switch", None):
                note = (note + " · " if note else "") + f"원래 {t.switch['원래']} → {t.switch['사유']}"
            lines.append(dict(t=t.start.strftime("%a %H:%M"), at=t.start, day=(t.start.date() - start.date()).days, key=key, l2=l2, l3=l3, slot=slot,
                              persons=p.party_size, qty=qty, krw=amount / k, net=net(amount / k), grade=grade, product=product, note=note))
    return lines


def agent_v4_place(key, p):
    L = agent_v4.PROPERTY[p.property]
    return {"buffet_b": "THE_BUFFET", "buffet_l": "THE_BUFFET", "buffet_d": "THE_BUFFET",
            "lounge_b": L["lounge"], "lounge_h": L["lounge"], "pizza": "PIZZA_HILL", "pizza_to": "PIZZA_HILL",
            "geum": "GEUMRYONG", "myong": "MYONGWOLGWAN", "moegi": "MOEGI", "ondal": "ONDAL",
            "lepassage": "LE_PASSAGE", "pavilion": "THE_PAVILION"}.get(key, "")


def write_l5(stays_lines):
    """온톨로지 L5 집계행 모양. 성별 · 연령 · AI 유형은 아직 '미설정' — 그 칸이 한호 · 슬기 축이 꽂히는 자리다"""
    import csv
    cols = ["체류", "구매 날짜", "성별", "대표자 연령", "구성·방문 목적", "AI 유형", "부문", "업장", "상품", "구매 수량", "결제액", "순매출", "등급", "비고"]
    with Path(__file__).with_name("revenue_l5.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(cols)
        for (n, label, m), lines in stays_lines:
            p = m.PERSONA
            comp = f"{p.party_size}인" + (" · 아동 동반" if p.has_child_under_13 else "") + ("" if p.is_guest else " · 비투숙")
            if p.purpose:
                comp = f"{p.purpose} · " + comp
            start = getattr(m, "START_AT", None)
            for ln in lines:
                day = (start + timedelta(days=ln["day"])).strftime("%Y-%m-%d") if start and start.year >= 2026 else f"D{ln['day']}"
                w.writerow([n, day, p.sex or "미설정", p.age_band or "미설정", comp, p.ai_type or "미설정", ln["l2"], ln["l3"], ln.get("product", ln["key"]),
                            ln["qty"], round(ln["krw"]), round(ln["net"]), ln["grade"], ln["note"]])


def aggregate(stays_lines):
    by_l3 = defaultdict(lambda: dict(krw=0.0, persons=0, visits=0, tri=0.0))
    by_slot = defaultdict(float)
    rooms_sold = defaultdict(int); room_krw = defaultdict(float)
    total = 0.0; tri = 0.0
    for (n, label, m), lines in stays_lines:
        p = m.PERSONA
        if p.is_guest:
            rooms_sold[p.property] += 1
        for ln in lines:
            a = by_l3[(ln["l2"], ln["l3"])]
            a["krw"] += ln["krw"]; a["visits"] += 1; a["persons"] += ln["persons"]
            if ln["grade"] == "△":
                a["tri"] += ln["krw"]; tri += ln["krw"]
            by_slot[ln["slot"]] += ln["krw"]
            total += ln["krw"]
            if ln["key"] in ("room", "sleep"):
                room_krw[p.property] += ln["krw"]
    return by_l3, by_slot, rooms_sold, room_krw, total, tri


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--blog", type=int, help="한 편만 — 손님 한 명의 지출 줄을 그대로 보여 준다")
    ap.add_argument("--l5", action="store_true", help="온톨로지 L5 집계행 모양의 revenue_l5.csv 도 쓴다")
    ap.add_argument("--no-menu", action="store_true", help="메뉴 선택 층을 끄고 prices.PRICE 의 업장당 값 하나로 (10/1 까지의 방식)")
    a = ap.parse_args()
    global USE_MENU
    if a.no_menu:
        USE_MENU = False

    if a.blog:
        m = importlib.import_module(f"persona_blog{a.blog:02d}")
        lines = spend_lines(m, k=1)
        p = m.PERSONA
        print(f"blog{a.blog:02d} · {'투숙' if p.is_guest else '비투숙'} · {p.property} · {p.party_size}인 · {p.nights}박\n")
        print(f"  {'시각':10s} {'행동':10s} {'부문':5s} {'업장':10s} {'금액':>10s} 등급  상품 · 비고")
        for ln in lines:
            print(f"  {ln['t']:10s} {ln['key']:10s} {ln['l2']:5s} {str(ln['l3']):10s} {ln['krw']:>10,.0f} {ln['grade']}   {ln.get('product','')} ×{ln['qty']}  {ln['note']}")
        tot = sum(l['krw'] for l in lines)
        print(f"\n  총 결제액 {tot:,.0f}원 · 순매출(VAT 차감) {net(tot):,.0f}원 · 그중 추정 단가(△) {sum(l['krw'] for l in lines if l['grade']=='△'):,.0f}원")
        return

    S = fit_v4.stays(fit_v4.DEV_BLOGS)
    stays_lines = [((n, label, m), spend_lines(m, k=a.k)) for n, label, m in S]
    by_l3, by_slot, rooms_sold, room_krw, total, tri = aggregate(stays_lines)
    n_guest = sum(1 for _, _, m in S if m.PERSONA.is_guest)
    persons = sum(m.PERSONA.party_size for _, _, m in S)

    print(f"체류 {len(S)} (투숙 {n_guest} · 비투숙 {len(S)-n_guest}) · 인원 {persons} · 같은 날에 겹쳐 놓음 · 체류당 {a.k}회 평균\n")
    # L1 · L2
    l2 = defaultdict(float)
    for (a2, _), v in by_l3.items():
        l2[a2] += v["krw"]
    print(f"L1 전체  결제액 {total:,.0f}원 · 순매출 {net(total):,.0f}원   (추정 단가 △ 비중 {tri/total*100 if total else 0:.0f}%)")
    for k2 in ("ROOM", "F&B", "레저"):
        print(f"  L2 {k2:5s} {l2[k2]:>14,.0f}원  (순매출 {net(l2[k2]):>14,.0f})")
    # L3
    print(f"\n  {'L3 업장':12s} {'매출':>12s} {'이용 인원':>8s} {'객단가':>9s} {'좌석 회전':>8s}  △비중")
    for (k2, k3), v in sorted(by_l3.items(), key=lambda kv: -kv[1]["krw"]):
        if v["krw"] == 0 and v["visits"] == 0:
            continue
        seat = SEATS.get(k3, {}).get("n")
        turn = f"{v['persons']/seat:.2f}" if seat else "—"      # 이용 인원 ÷ 좌석 (하루 회차는 SEATS[..]['turns'] 참고)
        apc = v["krw"] / v["persons"] if v["persons"] else 0
        print(f"  {k3:12s} {v['krw']:>12,.0f} {v['persons']:>8d} {apc:>9,.0f} {turn:>8s}  {v['tri']/v['krw']*100 if v['krw'] else 0:3.0f}%")
    # 객실 지표
    print(f"\n  {'객실':8s} {'판매':>4s} {'가능':>5s} {'OCC':>6s} {'ADR':>10s} {'RevPAR':>10s}")
    for prop in ("GRAND", "VISTA", "DOUGLAS"):
        sold = rooms_sold[prop]; avail = ROOMS[prop]["n"]; rev = room_krw[prop]
        nights = sum(max(1, m.PERSONA.nights) for _, _, m in S if m.PERSONA.is_guest and m.PERSONA.property == prop)
        adr = rev / nights if nights else 0
        print(f"  {ROOM_L3[prop]:8s} {sold:>4d} {avail:>5d} {sold/avail*100:>5.1f}% {adr:>10,.0f} {rev/avail/ max(1, 1):>10,.0f}  (객실 수 {ROOMS[prop]['grade']})")
    # 시간대
    print("\n  시간대별 매출 분포")
    for slot in ("객실", "조식", "중식", "석식", "기타"):
        print(f"    {slot:4s} {by_slot[slot]:>14,.0f}원  {by_slot[slot]/total*100 if total else 0:4.0f}%")

    if a.l5:
        write_l5(stays_lines)
        print(f"\n  L5 집계행 → revenue_l5.csv")
    mm = menu_mod.default() if USE_MENU else None
    if mm is not None:
        print(f"\n  메뉴 선택 층: 상품표 {len(mm.rows)}줄 · 상품표에 없어 가격표 값으로 {mm.fallbacks}줄 · 시간 창 밖 {mm.off_window}줄")

    out = dict(stays=len(S), guests=n_guest, persons=persons, k=a.k, total=total, net=net(total), tri_share=tri / total if total else 0,
               l2={k: v for k, v in l2.items()},
               l3={f"{k2}/{k3}": v for (k2, k3), v in by_l3.items()},
               rooms={p: dict(sold=rooms_sold[p], avail=ROOMS[p]["n"], krw=room_krw[p]) for p in ROOMS},
               slots=dict(by_slot))
    Path(__file__).with_name("revenue_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
