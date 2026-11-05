"""
와인페어 시나리오 — "몇 명이 가나" 가정을 얹어 행사 있는 주말 / 없는 주말을 비교한다 (10/8 경수 · 2판 → 10/11 4판)

  python3 scenario_winefair.py --date 2026-10-09 --date 2026-10-10 --date 2026-10-11              # 기본 가정
  python3 scenario_winefair.py --date 2026-10-10 --wf-guest 0.10 --wf-day 300                    # 조정값 바꿔 보기
  python3 scenario_winefair.py --date 2026-10-10 --wf-guest-only                                  # 외부 손님 입장 막기
  (행사 없음 기준선은 generate.py 에 --close WINE_FAIR=2026-10-10~2026-10-11 — 포레스트 파크 입장 제한은 그대로)

행사 자체는 합본에 들어 있다 (10/8 소연 · PR #28) — 검증기 창 WINE_FAIR · 에이전트 와인페어 행동 (120분) ·
상품표 입장권 (성인 55,000 · 아동 10,000) · 패키지 포함이면 성인 2인 0원 · 외부 입장 스위치 agent_v4.WINE_FAIR_PUBLIC.
이 스크립트는 그 위에 "누가 가나" 만 얹는다. 합본만으로는 투숙객이 저녁 식사 점수에 밀려 거의 안 간다 (주말 투숙 1.1% · 소연 10/8).

가정 (△ — 근거 없는 조정값. 결과는 이 값에 따라 달라진다)
  WF_GUEST  그 날 투숙 팀 중 와인페어에 가기로 한 비율 (기본 0.15)
  WF_DAY    와인페어만 보러 오는 외부 팀 수 · 행사 하루 (기본 150 · 적게 75 · 많이 300). 기존 비투숙 손님과 따로 더한다
  WF_BOOST  가기로 한 손님이 행사 쪽으로 더 받는 점수 (기본 +5 · '예약한 곳' +5 위에). 산 표는 거의 쓴다고 본다
  외부 팀은 기존 비투숙 손님 중 한 팀을 본떠 만든다 (인원 · 나이 · 목적), 도착은 11시 · 15시 반반
  3판 (10/8) — 외부 팀 목적을 슬기님 와인페어 보완 표본 18개 비율로 (--no-mix 로 끔)
  --wf-food 1 · --wf-food-hotel 1|0 · --wf-food-krw N : 행사장 푸드트럭 (끼니 하나를 행사장에서 · 값과 호텔 매출 여부는 가정)
  4판 (10/11 · 소연 PR #31 반영) — 투숙객은 패키지와 상관없이 무료 입장 (보도자료 9/14 · menu.py 가 0 으로 셈).
    입장권에 '푸드 교환권 1매' 가 들어 있다 (네이버 예약 화면 · 가정표) → 표를 산 외부 손님의 행사장 식사는 0 원 (표값에 이미 들어 있다 ·
    표값 중 음식 몫은 모른다). 무료로 들어간 투숙객은 교환권이 없다고 보고 WF_FOOD_KRW 를 낸다 (△). 사전 구매 10% 할인은 안 뺐다 (소연 상품표 그대로)
"""
from __future__ import annotations

import random, sys
from datetime import date, datetime, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import agent_v4
import generate as G

FAIR_DAYS = [date(2026, 10, d) for d in (10, 11, 17, 18, 24, 25)]
SPOT = "FOREST_PARK"          # 합본 와인페어 행동의 자리 (venue 는 WINE_FAIR)
WF_GUEST = 0.15
WF_DAY = 150
WF_BOOST = 5.0
GUEST_ONLY = False
# 10/8 3판 — 슬기님 #워커힐와인페어 보완 표본 18개 (docs/instagram_persona_winefair_additional.csv) 의 방문 목적
#   휴식·산책 동행 6 · 미식 방문 6 · 친구·모임 3 · 가족·친족 2 · 커플·기념일 1. 해시태그 목적 표본이라 전체 고객 구성비가 아니다 (△)
WF_MIX = {"휴식·산책 동행": 6, "미식 방문": 6, "친구·모임": 3, "가족·친족": 2, "커플·기념일": 1}
USE_MIX = True
# 행사장 푸드트럭 — 보완 표본 18개 중 다수가 푸드트럭 · 피크닉을 기록. 값 · 호텔 매출 여부 모름 (△). 행사에 들어간 뒤에만 고른다
WF_FOOD = 1            # 1 이면 행사 손님에게 행사장 식사(푸드트럭) 를 연다 (3판 기본 · 0 이면 2판처럼)
WF_FOOD_KRW = 20_000   # 1인 (△ 근거 없음)
WF_FOOD_HOTEL = 1      # 1 = 호텔 매출로 셈 · 0 = 입점 업체 매출이라 0 원 (끼니는 먹은 것으로)
WF_FOOD_BOOST = 3.0    # 행사장에 온 손님이 끼니 때 푸드트럭 쪽으로 더 받는 점수 (△)


def install():
    agent_v4.WINE_FAIR_PUBLIC = 0 if GUEST_ONLY else 1

    base_score = agent_v4.score_v4

    def score(action, persona, *a, **kw):
        s, why = base_score(action, persona, *a, **kw)
        if action.key == "winefair" and SPOT in persona.booked:
            s += WF_BOOST
            why = why + [f"와인페어 가기로 함 +{WF_BOOST:.2f}"]
        return s, why
    agent_v4.score_v4 = score

    if WF_FOOD:
        import prices
        prices.L3["fair_food"] = ("F&B" if WF_FOOD_HOTEL else "레저", "와인페어 푸드트럭")
        prices.PRICE["fair_food"] = dict(per="person", krw=WF_FOOD_KRW if WF_FOOD_HOTEL else 0, grade="△",
                                         src="와인페어 행사장 푸드트럭 1인 — 값 · 호텔 매출 여부 모름 (슬기 인스타 보완 표본의 행동)", slot="기타")
        agent_v4.MEAL_KEYS.add("fair_food")
        # 10/11 4판 — 표를 산 외부 손님은 교환권으로 먹는다 (0 원 · 표값에 포함). 투숙객 (무료 입장 · 교환권 없음) 만 값을 낸다 (△)
        import menu as menu_mod
        base_pick = menu_mod.Menu.pick

        def pick(self, key, p, at, rng):
            if key == "fair_food":
                krw = 0 if (not p.is_guest or not WF_FOOD_HOTEL) else WF_FOOD_KRW * p.party_size
                return dict(product="와인페어 푸드트럭", qty=p.party_size, krw=krw, grade="△", ledger="",
                            note="입장권 푸드 교환권 1매 (표값에 포함)" if not p.is_guest else "투숙객 무료 입장 · 교환권 없음 · 1인 값 가정", unit="인")
            return base_pick(self, key, p, at, rng)
        menu_mod.Menu.pick = pick
        base_catalog = agent_v4.catalog

        def catalog(p):
            acts = base_catalog(p)
            if SPOT in p.booked:
                acts.append(agent_v4.Action("fair_food", "ADMITTED", SPOT, 40, venue="WINE_FAIR", requires=("arrive", "winefair"),
                                            tags=("casual", "shared"), label="와인페어 푸드트럭"))
            return acts
        agent_v4.catalog = catalog
        prev_score = agent_v4.score_v4

        def score2(action, persona, *a, **kw):
            s_, why = prev_score(action, persona, *a, **kw)
            if action.key == "fair_food":
                s_ += WF_FOOD_BOOST
                why = why + [f"행사장 식사 +{WF_FOOD_BOOST:.2f}"]
            return s_, why
        agent_v4.score_v4 = score2

    base_guests = G.guests_for

    def guests_for(d, *a, **kw):
        out = base_guests(d, *a, **kw)
        day = datetime.strptime(d, "%Y-%m-%d").date()
        if day not in FAIR_DAYS:
            return out
        rng = random.Random(G.SEED + 7 + int(d.replace("-", "")))
        for _, _, m in out:
            p = m.PERSONA
            if p.is_guest and rng.random() < WF_GUEST:
                p.booked = tuple(p.booked) + (SPOT,)
        if not GUEST_ONLY and WF_DAY > 0:
            scale = kw.get("scale", a[2] if len(a) > 2 else 1.0)
            src = [m for _, _, m in out if not m.PERSONA.is_guest] or [m for _, _, m in out]
            by_purpose = {}
            for m in src:
                by_purpose.setdefault(m.PERSONA.purpose, []).append(m)
            mix = {k: v for k, v in WF_MIX.items() if by_purpose.get(k)} if USE_MIX else {}
            for j in range(int(round(WF_DAY * scale))):
                if mix:
                    want = rng.choices(list(mix), weights=list(mix.values()))[0]
                    t = rng.choice(by_purpose[want]).PERSONA
                else:
                    t = rng.choice(src).PERSONA
                arrive = datetime.combine(day, time(11 if rng.random() < 0.5 else 15, 0))
                p = G.Persona(name=f"{d} 와인페어 #{j+1} {t.purpose}", traits={k: None for k in G.TRAITS},
                              party_size=t.party_size, has_child_under_13=t.has_child_under_13, nights=0,
                              property="GRAND", is_guest=False, depart_by=time(22, 0), sex=t.sex, age_band=t.age_band,
                              purpose=t.purpose, ai_type=t.ai_type, prefers=t.prefers, booked=(SPOT,),
                              note="와인페어 외부 손님 · 규모 가정 (△)")
                out.append((f"{d}W#{j+1}", f"{d}W#{j+1}", G.SimpleNamespace(PERSONA=p, START_AT=arrive)))
        return out
    G.guests_for = guests_for


if __name__ == "__main__":
    argv = sys.argv[1:]

    def take(flag, cast, default):
        if flag in argv:
            i = argv.index(flag); v = cast(argv[i + 1]); del argv[i:i + 2]; return v
        return default
    WF_GUEST = take("--wf-guest", float, WF_GUEST)
    WF_DAY = take("--wf-day", int, WF_DAY)
    WF_BOOST = take("--wf-boost", float, WF_BOOST)
    WF_FOOD = take("--wf-food", int, WF_FOOD)
    WF_FOOD_HOTEL = take("--wf-food-hotel", int, WF_FOOD_HOTEL)
    WF_FOOD_KRW = take("--wf-food-krw", int, WF_FOOD_KRW)
    if "--no-mix" in argv:
        argv.remove("--no-mix"); USE_MIX = False
    if "--wf-guest-only" in argv:
        argv.remove("--wf-guest-only"); GUEST_ONLY = True
    print(f"[와인페어 가정] 투숙 {WF_GUEST:.0%} 가기로 함 · 외부 {WF_DAY}팀/일 · 가점 +{WF_BOOST} · 외부 입장 {'막음' if GUEST_ONLY else '허용'}"
          f" · 외부 목적 {'슬기 표본 18' if USE_MIX else '기존 비투숙'}"
          f" · 푸드트럭 {'없음' if not WF_FOOD else ('외부 교환권 0원 · 투숙객 ' + f'{WF_FOOD_KRW:,}원/인 · ' + ('호텔 매출' if WF_FOOD_HOTEL else '호텔 밖'))}")
    install()
    sys.argv = [sys.argv[0]] + argv
    G.main()
