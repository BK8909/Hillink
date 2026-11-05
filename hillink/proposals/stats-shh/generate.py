"""
하루 손님 생성기 — 페르소나 격자 × 날짜 배율로 "10월 N일 손님 M 팀" 을 뽑아 revenue.py 에 흘려보낸다

  python3 generate.py --date 2026-10-10                 # 그 날 손님을 뽑아 L1~L3 표 + revenue_l5.csv (날짜 · 성별 · 연령 · 목적 채워짐)
  python3 generate.py --date 2026-10-10 --scale 0.2     # 공급의 20% 만 (빠르게 보기)
  python3 generate.py --date 2026-10-03 --date 2026-10-06   # 여러 날 비교 (공휴일 vs 평일)
  python3 generate.py --date 2026-10-10 --no-cap            # 좌석 상한 없이 (10/1 이전 동작)
  python3 generate.py --date 2026-10-10 --occupancy 0.55    # 팔 수 있는 좌석을 55% 로 (온톨로지 점유율 손잡이)
  python3 generate.py --date 2026-10-10 --day-parties 300    # 이 날짜 비투숙 300팀 지정 (전체 scale 적용 전)
  python3 generate.py --date 2026-10-10 --day-scenario low   # 외부팀 수 독립 시나리오 (가정)

10/1 — 대표님 매출 온톨로지가 "(가정)" 으로 손으로 넣은 고객 구성비를 에이전트가 만들어 내는 첫 단계.
  읽는 것
    persona_grid.csv   성별 × 연령 × 목적 × 비중 · 인원수 · 아동 동반 · 박수 · 근거 — 서울 인구에 소득별 연 감당 횟수를 가중한 실험 격자.
                       개인지불 투숙에만 가구소득 대리값을 적용한다. 박수 0 = 비투숙 구성용이며 전체 비투숙 규모를 결정하지 않는다.
    day_visit_scenarios.json  하루 비투숙 팀 수 독립 시나리오. 실제 외부 방문팀 통계로 보정하기 전의 가정.
    date_factors.csv   날짜 × 목적 9종 수요 배율 — 온톨로지 "일자 × 고객 유형별 실제 적용 수요 배율" 표 그대로 (10월 31일)
    prices.ROOMS       판매 가능 객실 수
  하는 것
    1. 그 날 팀 수 = (객실 수 합 × 기준 가동률) 를 목적별 비중 × 그 날 배율로 나눠 뽑는다 (온톨로지와 같은 산식 · 가동률 79%)
    2. 팀마다 Persona 를 만든다 — 성별 · 연령 · 목적은 격자에서, 인원 · 아동 · 박수는 격자의 분포에서 뽑고,
       건물은 객실 수 비례, 조식 포함 패키지는 18% (온톨로지 TYPE 2 비중), 성향은 전부 미상(None — v4 는 lam_trait 0 이라 영향 없음)
    3. revenue.spend_lines 로 돌려 L3 → L2 → L1 합산 · OCC · 시간대 · L5 집계행
    4. 식당 선택 기본값 — 목적별로 "가고 싶은 식당" 하나를 dining_pref.csv 에서 뽑아 Persona.prefers 에 넣는다 (+3 · 예약 +5 보다 약하게).
       근거는 슬기 39편 분류(목적 × 실제 간 식당)에 온톨로지 구성비 원장을 사전으로 섞은 것. 투숙 70% · 비투숙 90% 만 (△)
    5. 좌석 상한 (capacity.py) — 그 날 손님이 식당 좌석을 나눠 쓴다. 만석이면 자리 날 때까지 대기 벌점, 창 안에 안 나면 다른 데로
    6. 목적 분포 · AI 유형 · 기상 시각 — purpose_mix.csv(슬기 39편 목적 분포 + 온톨로지 배분) 로 격자의 목적 비중을 바꿔 가중하고,
       type_mix.csv(목적 → 유형) 로 ai_type 을 채운다. 기상 시각은 06:30~09:00 에 퍼뜨린다 (△) — 조식 1부가 비지 않게
    7. 2박 손님 이어묵기 — 날짜를 이어서 돌리면 전날 2박 손님이 오늘 객실을 차지한다 (오늘 공급에서 빼고 OCC 에 더한다). 매출은 체크인 날에 센다
  아직 안 하는 것
    - 외부팀 실제 규모 확인 — 독립 시나리오도 임시 가정이다. 업장별 외부 방문기회·구매 건수는 고유 방문팀과 다르다.
    - AI 유형 — 슬기 분류가 오면 목적 → 유형 분포로 채운다 (지금은 미설정)
    - 목적별로 행동이 달라지는 것 — 지금 격자는 "누가 왔나" 만 바꾸고 "뭘 하나" 는 v4 그대로. 그래서 목적별 매출 차이는 인원 · 아동 · 박수에서만 나온다
"""

from __future__ import annotations

import argparse, csv, json, math, random, sys
from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent_v0 import Persona, TRAITS
from prices import ROOMS, net
from capacity import Capacity
import revenue

SEED = 20261001
OCC_BASE = 0.79            # 온톨로지 기준 가동률
BREAKFAST_PKG = 0.18       # 조식 포함 패키지 비중 (온톨로지 TYPE 2 18%)
P_PREFER_GUEST = 0.7       # 투숙 손님 중 "호텔 식당 하나는 가고 싶다" 비율 (△ — 온톨로지 10/10 식당 이용 인원 ≈ 투숙 인원에서 역산한 자리표)
P_PREFER_DAY = 0.9         # 비투숙은 거의 식당 · 시설이 목적 (△)
DAY_SCALE = 0.5            # 이전 결과 재현용. --day-scale을 명시할 때만 사용하며, 기본은 독립 팀 수 시나리오다.
PURPOSES = ["커플·기념일", "가족·친족", "비즈니스·접대", "친구·모임", "혼자 휴식", "휴식·산책 동행", "골프·스포츠 모임", "미식 방문", "공항 이동·여행"]


def load_grid(path=HERE / "persona_grid.csv"):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    for r in rows:
        r["비중"] = float(r["비중"]); r["아동동반"] = float(r["아동동반"])
    return rows


def load_dining(path=HERE / "dining_pref.csv"):
    """목적 → [(장소 코드, 비중)] — 슬기 39편 분류의 '식당=' 건수에 온톨로지 구성비 원장을 사전으로 섞은 것"""
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        out.setdefault(r["목적"], []).append((r["업장"], float(r["비중"])))
    return out


def load_mix(path, key="목적"):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        out[r[key]] = float(r["비중"])
    return out


def load_type_mix(path=HERE / "type_mix.csv"):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        out.setdefault(r["목적"], []).append((r["AI유형"], float(r["비중"])))
    return out


def pick_type(purpose, tmix, rng):
    if purpose not in tmix:
        return None
    t, w = zip(*tmix[purpose])
    return rng.choices(t, weights=w)[0]


WAKE_SPREAD = [(time(6, 30), 1), (time(7, 0), 2), (time(7, 30), 3), (time(8, 0), 3), (time(8, 30), 2), (time(9, 0), 1)]   # △ 기상 시각 분포


def pick_prefer(purpose, dining, rng, p):
    if purpose not in dining or rng.random() >= p:
        return ()
    venues, w = zip(*dining[purpose])
    return (rng.choices(venues, weights=w)[0],)


def load_factors(path=HERE / "date_factors.csv"):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        out[r["날짜"]] = {k: float(v) for k, v in r.items() if k != "날짜"}
    return out


def pick_dist(spec: str, rng: random.Random) -> int:
    """'3:0.4/4:0.5/5:0.1' 같은 분포 문자열에서 하나"""
    items = [(int(a), float(b)) for a, b in (x.split(":") for x in spec.split("/"))]
    r = rng.random() * sum(w for _, w in items)
    for v, w in items:
        r -= w
        if r <= 0:
            return v
    return items[-1][0]


def is_day_row(r) -> bool:
    """박수 0 = 비투숙 (한호 격자: 미식 방문 · 친구 모임 · 공항 이동은 0박이 많다)"""
    return r["박수"].split("/")[0].startswith("0:") and len(r["박수"].split("/")) == 1


def load_day_scenarios(path=HERE / "day_visit_scenarios.json"):
    with open(path, encoding="utf-8-sig") as f:
        config = json.load(f)
    if config.get("unit") != "unique_parties_per_day" or config.get("scope") != "hotel_grounds_excluding_airport":
        raise ValueError("비투숙 설정의 단위·범위를 확인해 주세요")
    if not config.get("reference_date") or not config.get("scenarios"):
        raise ValueError("비투숙 기준일·시나리오가 필요합니다")
    for name, count in config["scenarios"].items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"비투숙 {name}: 팀 수는 0 이상의 정수여야 합니다")
    return config


def day_party_count(date, rows, factors, scale, *, explicit=None, scenario="base", config=None):
    """전체 외부팀 수. 격자의 0박 질량·객실 공급·투숙팀 수를 사용하지 않는다."""
    if not math.isfinite(scale) or scale < 0:
        raise ValueError("scale은 0 이상의 유한한 수여야 합니다")
    if explicit is not None:
        if isinstance(explicit, bool) or not isinstance(explicit, int) or explicit < 0:
            raise ValueError("비투숙 팀 수는 0 이상의 정수여야 합니다")
        count = int(round(explicit * scale))  # 날짜 배율을 다시 곱하지 않는다.
    else:
        config = load_day_scenarios() if config is None else config
        if scenario not in config["scenarios"]:
            raise ValueError(f"없는 비투숙 시나리오: {scenario}")
        baseline = config["scenarios"][scenario]
        if isinstance(baseline, bool) or not isinstance(baseline, int) or baseline < 0:
            raise ValueError("비투숙 시나리오 팀 수는 0 이상의 정수여야 합니다")
        if baseline == 0 or scale == 0:
            return 0
        ref = config["reference_date"]
        if ref not in factors:
            raise ValueError(f"비투숙 기준일 배율이 없습니다: {ref}")
        mass = sum(r["비중"] for r in rows)
        if mass <= 0:
            raise ValueError("비투숙 구성의 비중 합계가 0입니다")
        current = sum(r["비중"] * factors[date].get(r["목적"], 1.0) for r in rows) / mass
        reference = sum(r["비중"] * factors[ref].get(r["목적"], 1.0) for r in rows) / mass
        if not math.isfinite(current) or not math.isfinite(reference) or current < 0 or reference <= 0:
            raise ValueError("비투숙 날짜 배율은 유한하며 기준일은 0보다 커야 합니다")
        count = int(round(baseline * scale * current / reference))
    if count > 0 and (not rows or sum(r["비중"] for r in rows) <= 0):
        raise ValueError("비투숙 팀 수는 있지만 구성용 0박 행이 없습니다")
    return count


def guests_for(date: str, grid, factors, scale=1.0, rng=None, dining=None, purpose_mix=None, type_mix=None, carry=None,
               day_parties=None, day_scenario="base", day_config=None, legacy_day_scale=None):
    """그 날의 손님 팀 목록 → [(label, module-like)]. 투숙 팀은 객실 공급, 비투숙 팀은 독립 설정으로
    purpose_mix: 목적 → 비중. 격자의 목적 분포(한호 격자는 균등 1/9)를 이 분포로 바꿔 가중한다. None 이면 격자 그대로
    type_mix:    목적 → [(AI 유형, 비중)] — Persona.ai_type 을 채운다
    carry:       전날 체크인한 2박 손님이 오늘 차지한 객실 수 {건물: n} — 오늘 공급에서 뺀다"""
    if not math.isfinite(scale) or scale < 0:
        raise ValueError("scale은 0 이상의 유한한 수여야 합니다")
    if day_parties is not None and legacy_day_scale is not None:
        raise ValueError("비투숙 팀 수와 이전 배율을 함께 지정할 수 없습니다")
    rng = rng or random.Random(SEED + int(date.replace("-", "")))
    dining = load_dining() if dining is None else dining
    if purpose_mix:
        gp = defaultdict(float)
        for r in grid:
            gp[r["목적"]] += r["비중"]
        grid = [dict(r, 비중=r["비중"] * purpose_mix.get(r["목적"], 0) / gp[r["목적"]]) for r in grid if gp[r["목적"]] > 0]
    fac = factors[date]
    rooms = sum(v["n"] for v in ROOMS.values())
    base_parties = rooms * OCC_BASE * scale
    # 공항 이동·여행은 공항 라운지(대외사업) 손님 — 호텔 시뮬 밖
    grid = [r for r in grid if r["목적"] != "공항 이동·여행"]
    g_rows = [r for r in grid if not is_day_row(r)]
    d_rows = [r for r in grid if is_day_row(r)]
    # 격자 비중 × 그 날 목적 배율 → 팀 수 (온톨로지: 수요 = 기준 × 배율, 공급 상한)
    g_w = [r["비중"] * fac.get(r["목적"], 1.0) for r in g_rows]
    d_w = [r["비중"] * fac.get(r["목적"], 1.0) for r in d_rows]
    g_share = sum(g_w) / (sum(r["비중"] for r in g_rows) or 1)          # 투숙 수요 배율 (격자 기준 1.0)
    n_guest = min(int(round(base_parties * g_share)), int(rooms * scale))   # 공급 상한
    if legacy_day_scale is not None:
        if not math.isfinite(legacy_day_scale) or legacy_day_scale < 0:
            raise ValueError("이전 비투숙 배율은 0 이상의 유한한 수여야 합니다")
        n_day = int(round(n_guest * sum(d_w) / sum(g_w) * legacy_day_scale)) if sum(g_w) > 0 and d_w else 0
    else:
        n_day = day_party_count(date, d_rows, factors, scale, explicit=day_parties,
                                scenario=day_scenario, config=day_config)
    left = {p: int(ROOMS[p]["n"] * scale) - (carry or {}).get(p, 0) for p in ("GRAND", "VISTA", "DOUGLAS")}   # 건물별 공급 상한 − 전날 2박 손님 (온톨로지 "용량 초과 제한")
    n_guest = min(n_guest, max(0, sum(left.values())))
    checkin = datetime.strptime(date, "%Y-%m-%d").replace(hour=15, minute=0)
    out = []
    for i in range(n_guest):
        r = rng.choices(g_rows, weights=g_w)[0]
        party = pick_dist(r["인원수"], rng)
        kid = rng.random() < r["아동동반"] and party >= 2
        nights = max(1, pick_dist(r["박수"], rng))
        avail = [p for p, n in left.items() if n > 0]
        if not avail:
            break
        prop = rng.choices(avail, weights=[ROOMS[p]["n"] for p in avail])[0]
        left[prop] -= 1
        incl = (("조식", "THE_BUFFET"),) if rng.random() < BREAKFAST_PKG else ()
        p = Persona(name=f"{date} #{i+1} {r['목적']}", traits={k: None for k in TRAITS},
                    party_size=party, has_child_under_13=kid, nights=nights, property=prop, is_guest=True,
                    included_meals=incl, sex=r["성별"], age_band=r["연령"], purpose=r["목적"],
                    ai_type=pick_type(r["목적"], type_mix or {}, rng),
                    prefers=pick_prefer(r["목적"], dining, rng, P_PREFER_GUEST),
                    wake_at=rng.choices([t for t, _ in WAKE_SPREAD], weights=[w for _, w in WAKE_SPREAD])[0],
                    note="격자 생성 · 구매력은 실험 가정 · 성향 미상")
        out.append((f"{date}#{i+1}", f"{date}#{i+1}", SimpleNamespace(PERSONA=p, START_AT=checkin)))
    for j in range(n_day):
        r = rng.choices(d_rows, weights=d_w)[0]
        party = pick_dist(r["인원수"], rng)
        kid = rng.random() < r["아동동반"] and party >= 2
        # 비투숙 도착: 점심 손님 11:00 · 저녁 손님 17:00 (△ 가정 4:6) · 떠나는 시각 22:00
        hour = 11 if rng.random() < 0.4 else 17
        arrive = datetime.strptime(date, "%Y-%m-%d").replace(hour=hour, minute=0)
        p = Persona(name=f"{date} 비투숙 #{j+1} {r['목적']}", traits={k: None for k in TRAITS},
                    party_size=party, has_child_under_13=kid, nights=0, property="GRAND", is_guest=False,
                    depart_by=time(22, 0), sex=r["성별"], age_band=r["연령"], purpose=r["목적"],
                    ai_type=pick_type(r["목적"], type_mix or {}, rng),
                    prefers=pick_prefer(r["목적"], dining, rng, P_PREFER_DAY),
                    note="격자 생성 · 비투숙 규모 가정 · 성향 미상")
        out.append((f"{date}D#{j+1}", f"{date}D#{j+1}", SimpleNamespace(PERSONA=p, START_AT=arrive)))
    return out


def report(date, stays, fac, cap=None, carry=None):
    stays_lines = [((n, label, m), revenue.spend_lines(m, k=1, capacity=cap)) for n, label, m in stays]
    by_l3, by_slot, rooms_sold, room_krw, total, tri = revenue.aggregate(stays_lines)
    persons = sum(m.PERSONA.party_size for _, _, m in stays)
    n_g = sum(1 for _, _, m in stays if m.PERSONA.is_guest)
    print(f"\n=== {date} · 손님 {len(stays)} 팀 (투숙 {n_g} · 비투숙 {len(stays)-n_g}) · {persons} 명 · 배율 " + " ".join(f"{k[:2]}{v:.2f}" for k, v in fac.items() if k != "공항 이동·여행"))
    print(f"L1 전체  결제액 {total:,.0f}원 · 순매출 {net(total):,.0f}원   (추정 단가 △ 비중 {tri/total*100 if total else 0:.0f}%)")
    l2 = defaultdict(float)
    for (a2, _), v in by_l3.items():
        l2[a2] += v["krw"]
    for k2 in ("ROOM", "F&B", "레저"):
        print(f"  L2 {k2:5s} {l2[k2]:>14,.0f}원  (순매출 {net(l2[k2]):>14,.0f})")
    print(f"\n  {'L3 업장':12s} {'매출':>12s} {'이용 인원':>8s} {'객단가':>9s}")
    for (k2, k3), v in sorted(by_l3.items(), key=lambda kv: -kv[1]["krw"])[:12]:
        if v["krw"] == 0:
            continue
        print(f"  {k3:12s} {v['krw']:>12,.0f} {v['persons']:>8d} {v['krw']/v['persons'] if v['persons'] else 0:>9,.0f}")
    print(f"\n  {'객실':8s} {'체크인':>4s} {'이어묵음':>5s} {'가능':>5s} {'OCC':>6s} {'ADR':>10s} {'RevPAR':>10s}")
    for prop in ("GRAND", "VISTA", "DOUGLAS"):
        sold = rooms_sold[prop]; avail = ROOMS[prop]["n"]; rev = room_krw[prop]; co = (carry or {}).get(prop, 0)
        nights = sum(m.PERSONA.nights for _, _, m in stays if m.PERSONA.is_guest and m.PERSONA.property == prop)
        print(f"  {revenue.ROOM_L3[prop]:8s} {sold:>4d} {co:>5d} {avail:>5d} {(sold+co)/avail*100:>5.1f}% {rev/nights if nights else 0:>10,.0f} {rev/avail:>10,.0f}")
    if cap is not None:
        print(f"\n  {'좌석':8s} {'좌석':>5s} {'앉은 인원':>8s} {'돌려보냄':>7s} {'대기 분':>8s}")
        for venue, n, seated, away, dmin in cap.summary():
            if seated or away:
                print(f"  {venue:8s} {n:>5d} {seated:>8d} {away:>7d} {dmin:>8,.0f}")
    # 목적별 — 온톨로지 "고객 관점에서 역으로 보기" 와 같은 표
    by_p = defaultdict(lambda: [0, 0.0])
    for (n, label, m), lines in stays_lines:
        by_p[m.PERSONA.purpose][0] += 1
        by_p[m.PERSONA.purpose][1] += sum(l["krw"] for l in lines)
    print(f"\n  {'목적':12s} {'팀':>4s} {'결제액':>14s} {'팀당':>10s}")
    for p, (c, krw) in sorted(by_p.items(), key=lambda kv: -kv[1][1]):
        print(f"  {p:12s} {c:>4d} {krw:>14,.0f} {krw/c:>10,.0f}")
    return stays_lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append", default=None)
    ap.add_argument("--scale", type=float, default=1.0, help="전체 실험 규모 비율 (1.0 = 객실 전부 × 가동률 79%%, 독립 비투숙 규모도 함께 적용)")
    ap.add_argument("--no-cap", action="store_true", help="좌석 상한 끄기")
    ap.add_argument("--occupancy", type=float, default=1.0, help="팔 수 있는 좌석 비율 (온톨로지 좌석 점유율 손잡이)")
    day_args = ap.add_mutually_exclusive_group()
    day_args.add_argument("--day-parties", type=int, default=None, help="각 날짜의 비투숙 팀 수 (전체 scale 적용 전, 날짜 배율 추가 없음)")
    day_args.add_argument("--day-scenario", choices=("low", "base", "high"), default=None, help="독립 외부팀 규모 가정 (기본 base)")
    day_args.add_argument("--day-scale", type=float, default=None, help="이전 격자 비율 방식 재현용; 실제 외부 규모 근거 아님")
    ap.add_argument("--day-config", type=Path, default=HERE / "day_visit_scenarios.json", help="비투숙 독립 규모 설정 파일")
    ap.add_argument("--prefer", type=float, default=None, help="투숙 손님의 식당 선호 비율 (기본 P_PREFER_GUEST)")
    ap.add_argument("--grid-purpose", action="store_true", help="목적 분포를 격자 그대로 (기본은 purpose_mix.csv — 슬기 39편 + 온톨로지)")
    a = ap.parse_args()
    global P_PREFER_GUEST
    if not math.isfinite(a.scale) or a.scale < 0: ap.error("scale은 0 이상의 유한한 수여야 합니다")
    if a.day_parties is not None and a.day_parties < 0: ap.error("비투숙 팀 수는 0 이상이어야 합니다")
    if a.day_scale is not None and (not math.isfinite(a.day_scale) or a.day_scale < 0): ap.error("비투숙 배율은 0 이상의 유한한 수여야 합니다")
    if a.prefer is not None: P_PREFER_GUEST = a.prefer
    grid, factors = load_grid(), load_factors()
    day_config = load_day_scenarios(a.day_config) if a.day_parties is None and a.day_scale is None else None
    if a.day_scale is not None:
        print(f"[가정·이전 방식] 비투숙 격자 비율 × {a.day_scale}. 독립 규모 보정 전 결과입니다.")
    elif a.day_parties is not None:
        print(f"[실험 입력] 비투숙 각 날짜 {a.day_parties}팀 × scale. 실제 관측값이라는 뜻은 아닙니다.")
    else:
        print(f"[가정·독립 규모] {a.day_scenario or 'base'}: {day_config['reference_date']} 기준 {day_config['scenarios'][a.day_scenario or 'base']}팀 × 날짜 배율 × scale")
        print("  " + day_config.get("basis", "외부팀 규모의 근거를 별도로 확인해 주세요"))
    pmix = None if a.grid_purpose else load_mix(HERE / "purpose_mix.csv")
    tmix = load_type_mix()
    dates = sorted(a.date or ["2026-10-10"])
    all_lines = []
    carry = {}; prev = None
    for d in dates:
        if prev is None or (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(prev, "%Y-%m-%d")).days != 1:
            carry = {}                       # 이어지는 날짜가 아니면 이어묵는 손님 없음
        stays = guests_for(d, grid, factors, scale=a.scale, purpose_mix=pmix, type_mix=tmix, carry=carry,
                           day_parties=a.day_parties, day_scenario=a.day_scenario or "base",
                           day_config=day_config, legacy_day_scale=a.day_scale)
        cap = None if a.no_cap else Capacity(occupancy=a.occupancy)
        all_lines += report(d, stays, factors[d], cap, carry)
        # 내일로 이어지는 객실: 오늘 체크인한 2박 이상 + 전날 3박 이상 … (여기선 nights-1 일만큼)
        nxt = defaultdict(int)
        for _, _, m in stays:
            p = m.PERSONA
            if p.is_guest and p.nights >= 2:
                nxt[p.property] += 1
        carry = dict(nxt); prev = d
    revenue.write_l5(all_lines)
    print(f"\n  L5 집계행 → revenue_l5.csv ({sum(len(l) for _, l in all_lines)} 줄)")


if __name__ == "__main__":
    main()

