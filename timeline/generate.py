"""
하루 손님 생성기 — 페르소나 격자 × 날짜 배율로 "10월 N일 손님 M 팀" 을 뽑아 revenue.py 에 흘려보낸다

  python3 generate.py --date 2026-10-10                 # 그 날 손님을 뽑아 L1~L3 표 + revenue_l5.csv (날짜 · 성별 · 연령 · 목적 채워짐)
  python3 generate.py --date 2026-10-10 --scale 0.2     # 공급의 20% 만 (빠르게 보기)
  python3 generate.py --date 2026-10-03 --date 2026-10-06   # 여러 날 비교 (공휴일 vs 평일)
  python3 generate.py --date 2026-10-10 --no-cap            # 좌석 상한 없이 (10/1 이전 동작)
  python3 generate.py --date 2026-10-10 --occupancy 0.55    # 팔 수 있는 좌석을 55% 로 (온톨로지 점유율 조정값)
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
    8. 연령 조정값 — age_mix.csv(온톨로지 25/50/25) 로 격자의 연령 비중을 바꿔 가중한다. 한호 격자(서울 인구 · 50세 이상 49%)는 --grid-age
  아직 안 하는 것
    - 외부팀 실제 규모 확인 — 독립 시나리오도 임시 가정이다. 업장별 외부 방문기회·구매 건수는 고유 방문팀과 다르다.
    - AI 유형 — 슬기 분류가 오면 목적 → 유형 분포로 채운다 (지금은 미설정)
    - 목적별로 행동이 달라지는 것 — 지금 격자는 "누가 왔나" 만 바꾸고 "뭘 하나" 는 v4 그대로. 그래서 목적별 매출 차이는 인원 · 아동 · 박수에서만 나온다
"""

from __future__ import annotations

import argparse, csv, json, math, random, sys, warnings
from collections import defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent_v0 import Persona, TRAITS
from prices import ROOMS, ROOM_L3, net
from capacity import Capacity
import revenue, reroute

SEED = 20261001
OCC_BASE = 0.79            # 온톨로지 기준 가동률
BREAKFAST_PKG = 0.18       # 조식 포함 패키지 비중 (온톨로지 TYPE 2 18%)
P_PREFER_GUEST = 0.7       # 투숙 손님 중 "호텔 식당 하나는 가고 싶다" 비율 (△ — 온톨로지 10/10 식당 이용 인원 ≈ 투숙 인원에서 역산한 자리표)
P_PREFER_DAY = 0.9         # 비투숙은 거의 식당 · 시설이 목적 (△)
# 비투숙 도착 시각 분포 (시, 가중) — 점심 손님 11:00 · 저녁 손님 17:00 (△ 가정 4:6). 실험용 덮어쓰기: WH_DAY_ARRIVE='{"11":0.3,"13":0.2,"15":0.2,"17":0.3}' (10/13 온톨로지 대조 · 피자힐 저녁 집중)
DAY_ARRIVE = [(11, 0.4), (17, 0.6)]
import os as _os, json as _json
# 10/13 실험 조정값 — WH_ROOMS=onto 면 객실 수를 온톨로지 값(그랜드 507 · 비스타 244 · 더글라스 50 — 공식 557실에 더글라스 50 포함 가정 · 비스타 · 더글라스는 공개 OTA)으로. prices.ROOMS 를 제자리에서 바꿔 revenue 도 같은 값을 본다. 기본은 557 · 253 · 65 (전과 같다)
if _os.environ.get("WH_ROOMS") == "onto":
    for _p, _n in (("GRAND", 507), ("VISTA", 244), ("DOUGLAS", 50)):
        ROOMS[_p]["n"] = _n
if _os.environ.get("WH_DAY_ARRIVE"):
    DAY_ARRIVE = [(int(h), float(w)) for h, w in _json.loads(_os.environ["WH_DAY_ARRIVE"]).items()]
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
    # 10/13 조정값 trend_w — WH_TREND=강도(0~1) 면 SNS 신호(trend_signals.csv) 쪽으로 '가고 싶은 식당' 을 기운다 (trend.py). 기본 꺼짐 · 전과 같다
    if _os.environ.get("WH_TREND") and float(_os.environ["WH_TREND"] or 0) > 0:
        import trend as _trend
        out, _ = _trend.adjust(out, load_mix(HERE / "purpose_mix.csv"), float(_os.environ["WH_TREND"]))
    # 10/14 변칙 시나리오 — WH_BOOST='{"PIZZA_HILL":1.5}' 면 그 업장의 '가고 싶은 식당' 무게를 곱하고 목적마다 다시 나눈다 (anomaly_scenarios.csv). 기본 꺼짐
    if _os.environ.get("WH_BOOST"):
        bst = _json.loads(_os.environ["WH_BOOST"])
        nb = {}
        for p_, rows in out.items():
            w = [(v, x * float(bst.get(f"{p_}|{v}", bst.get(v, 1.0)))) for v, x in rows]   # '목적|업장' 이 있으면 그 목적만
            t = sum(x for _, x in w) or 1.0
            nb[p_] = [(v, x / t) for v, x in w]
        out = nb
    return out


def load_mix(path, key="목적"):
    # 10/13 실험 조정값 — WH_PURPOSE_MIX=onto 면 purpose_mix.csv 의 '온톨로지 배분' 열을 쓴다 (기본은 '비중' · 후기 기반, 전과 같다)
    col = "온톨로지 배분" if (key == "목적" and _os.environ.get("WH_PURPOSE_MIX") == "onto") else "비중"
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        out[r[key]] = float(r.get(col) or r["비중"])
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
    path = Path(_os.environ.get("WH_DATE_FACTORS_FILE", str(path)))
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


def pick_property(left, has_child_under_13, rng, by_left=False):
    """남은 객실 중 아동 동반이면 더글라스를 제외한다 (더글라스 패키지 전부 '초등학생 이하 동반 불가' · 10/2 한호). 적격 객실이 없으면 None
    by_left: 객실 산식 옵션에서 건물별 체크인 몫이 정해져 있을 때 — 남은 몫에 비례해 뽑아 몫을 채운다"""
    available = [p for p, n in left.items() if n > 0 and not (has_child_under_13 and p == "DOUGLAS")]
    if not available:
        return None
    return rng.choices(available, weights=[(left[p] if by_left else ROOMS[p]["n"]) for p in available])[0]


# 10/14 객실 산식 옵션 (한호님 10/13 제안) — WH_ROOM_FORMULA=1 이면
#   건물별 목표 객실박 = min(건물 재고, 반올림(재고 × OCC_BASE × 건물별 날짜 계수)) · 신규 체크인 = max(0, 목표 − 이월)
# 계수는 한호님 참고계수 93행 (온톨로지 건물별 요청 객실박 ÷ (재고 × 0.79) · 날짜 · 목적 · 행사 효과가 섞인 값). 없는 날짜는 기존 방식
ROOM_COEF_PATH = HERE.parent / "docs" / "data" / "ontology_inverse_followup_shh_20261013" / "객실_온톨로지참고계수_31일.csv"
_BLDG = {"그랜드": "GRAND", "비스타": "VISTA", "더글라스": "DOUGLAS"}


def load_room_coef(path=ROOM_COEF_PATH):
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[(r["날짜"], _BLDG[r["건물"]])] = float(r["참고수요계수"])
    extra = _os.environ.get("WH_ROOM_COEF_EXTRA")
    if extra:
        for r in csv.DictReader(open(extra, encoding="utf-8-sig")):
            out[(r["날짜"], _BLDG[r["건물"]])] = float(r["참고수요계수"])
    return out


def room_booking(prop, party, kid, nights, checkin, rng):
    """건물이 정해진 뒤 객실 상품 · 포함 끼니 · 라운지 자격을 한 번에 — 체크인 전에 (10/2 메뉴 선택 층)
    상품표가 없거나(--no-menu) 그 손님에게 맞는 상품이 없으면 조식 포함 18% 가정으로 떨어진다"""
    incl, club, package = (("조식", "THE_BUFFET"),) if rng.random() < BREAKFAST_PKG else (), False, None
    mm = revenue.menu_mod.default() if revenue.USE_MENU else None
    if mm is not None:
        tmp = Persona(name="", traits={}, party_size=party, has_child_under_13=kid, nights=nights, property=prop, is_guest=True)
        sel = mm.pick("room", tmp, checkin, rng)
        if sel is not None:
            package = sel["product"]
            incl, club = mm.package_terms(mm.row_of(ROOM_L3[prop], package))
    return incl, club, package


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
               day_parties=None, day_scenario="base", day_config=None, legacy_day_scale=None, age_mix=None):
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
    if age_mix:
        # 연령 조정값 — 한호 격자는 서울 인구 분포(50세 이상 49%)이고 소득 가중으로도 안 내려간다(10/1 한호 검토).
        # 호텔 손님 연령 자료가 생길 때까지 온톨로지 25/50/25 로 가중한다. --grid-age 로 격자 그대로
        ga = defaultdict(float)
        for r in grid:
            ga[r["연령"]] += r["비중"]
        grid = [dict(r, 비중=r["비중"] * age_mix.get(r["연령"], 0) / ga[r["연령"]]) for r in grid if ga[r["연령"]] > 0]
    fac = factors[date]
    # Search changes restaurant preference only. It does not multiply total visitors.
    if float(_os.environ.get("WH_SEARCH_WEIGHT", "0")):
        from signal_inputs import search_dining
        dining = search_dining(dining, fac, float(_os.environ["WH_SEARCH_WEIGHT"]))
    rooms = sum(v["n"] for v in ROOMS.values())
    base_parties = rooms * OCC_BASE * scale
    # 공항 이동·여행은 공항 라운지(대외사업) 손님 — 호텔 시뮬 밖
    grid = [r for r in grid if r["목적"] != "공항 이동·여행"]
    g_rows = [r for r in grid if not is_day_row(r)]
    d_rows = [r for r in grid if is_day_row(r)]
    # 격자 비중 × 그 날 목적 배율 → 팀 수 (온톨로지: 수요 = 기준 × 배율, 공급 상한)
    g_w = [r["비중"] * fac.get(r["목적"], 1.0) for r in g_rows]
    d_w = [r["비중"] * fac.get(r["목적"], 1.0) for r in d_rows]
    day_dining = dining
    if _os.environ.get("WH_POSTING_K"):
        from signal_inputs import nonstay_pizza
        day_dining = nonstay_pizza(dining, d_rows, d_w, float(_os.environ["WH_POSTING_K"]))
    g_share = sum(g_w) / (sum(r["비중"] for r in g_rows) or 1)          # 투숙 수요 배율 (격자 기준 1.0)
    # 가동률은 "객실박 ÷ 객실" 이라 오늘 차 있을 객실 수다 — 전날 2박 손님(carry)이 이미 차지한 방을 빼야 오늘 체크인 수가 된다 (10/2 · 일주일 돌려 보니 매일 100% 가 나왔다)
    n_guest = min(int(round(base_parties * g_share)) - sum((carry or {}).values()), int(rooms * scale))   # 공급 상한
    n_guest = max(0, n_guest)
    if legacy_day_scale is not None:
        if not math.isfinite(legacy_day_scale) or legacy_day_scale < 0:
            raise ValueError("이전 비투숙 배율은 0 이상의 유한한 수여야 합니다")
        n_day = int(round(n_guest * sum(d_w) / sum(g_w) * legacy_day_scale)) if sum(g_w) > 0 and d_w else 0
    else:
        n_day = day_party_count(date, d_rows, factors, scale, explicit=day_parties,
                                scenario=day_scenario, config=day_config)
    # 10/14 가설 H5 — 평일 비투숙 구성. WH_WD = {"thin": 평일 배율, "exempt": [줄이지 않는 목적], "party": {목적: 일행 분포}}
    # 엔진이 평일에만 넣는다. 없으면 전과 같다 (기본 꺼짐)
    wd = _json.loads(_os.environ["WH_WD"]) if _os.environ.get("WH_WD") else None
    if wd and d_w and sum(d_w) > 0:
        ex, thin = set(wd.get("exempt") or []), float(wd.get("thin", 1.0))
        s_ex = sum(w for r, w in zip(d_rows, d_w) if r["목적"] in ex) / sum(d_w)
        n_day = int(round(n_day * (thin * (1 - s_ex) + s_ex)))          # 줄이는 목적만 thin 배
        if thin > 0:
            d_w = [w / thin if r["목적"] in ex else w for r, w in zip(d_rows, d_w)]   # 줄이지 않는 목적의 팀 수가 그대로 남도록
    left = {p: int(ROOMS[p]["n"] * scale) - (carry or {}).get(p, 0) for p in ("GRAND", "VISTA", "DOUGLAS")}   # 건물별 공급 상한 − 전날 2박 손님 (온톨로지 "용량 초과 제한")
    n_guest = min(n_guest, max(0, sum(left.values())))
    by_left = False
    if _os.environ.get("WH_ROOM_FORMULA"):
        coef = load_room_coef()
        if all((date, p) in coef for p in left):
            left = {p: max(0, min(int(ROOMS[p]["n"] * scale), int(round(ROOMS[p]["n"] * scale * OCC_BASE * coef[(date, p)])))
                           - (carry or {}).get(p, 0)) for p in left}
            n_guest, by_left = sum(left.values()), True   # 객실 수요(건물별 몫)를 고객 구성(목적 섞기)과 따로 정한다
        else:
            warnings.warn(f"{date}: 객실 참고계수가 없어 기존 객실 산식을 씁니다", RuntimeWarning)
    checkin = datetime.strptime(date, "%Y-%m-%d").replace(hour=15, minute=0)
    out = []
    unassigned_child = 0
    for i in range(n_guest):
        r = rng.choices(g_rows, weights=g_w)[0]
        party = pick_dist(r["인원수"], rng)
        kid = rng.random() < r["아동동반"] and party >= 2
        nights = max(1, pick_dist(r["박수"], rng))
        if not any(n > 0 for n in left.values()):
            break
        prop = pick_property(left, kid, rng, by_left)
        if prop is None and kid and left.get("DOUGLAS", 0) > 0:
            # 그랜드 · 비스타가 먼저 찼으면 아직 체크인 전인 성인팀 하나를 더글라스로 옮겨 자리를 낸다 (이어묵는 손님은 안 옮긴다 · 10/2 한호)
            adults = [m.PERSONA for _, _, m in out if not m.PERSONA.has_child_under_13 and m.PERSONA.property in ("GRAND", "VISTA")]
            if adults:
                moved = rng.choice(adults)
                prop = moved.property
                moved.property = "DOUGLAS"
                # 건물이 바뀌면 이전 상품 · 조식 혜택을 들고 가지 않고 새 건물에서 다시 예약한다
                moved.included_meals, moved.club_access, moved.package = room_booking(
                    moved.property, moved.party_size, moved.has_child_under_13, moved.nights, checkin, rng)
                left["DOUGLAS"] -= 1
                left[prop] += 1
        if prop is None:
            unassigned_child += 1
            continue
        left[prop] -= 1
        incl, club, package = room_booking(prop, party, kid, nights, checkin, rng)
        p = Persona(name=f"{date} #{i+1} {r['목적']}", traits={k: None for k in TRAITS},
                    party_size=party, has_child_under_13=kid, nights=nights, property=prop, is_guest=True,
                    included_meals=incl, club_access=club, package=package, sex=r["성별"], age_band=r["연령"], purpose=r["목적"],
                    ai_type=pick_type(r["목적"], type_mix or {}, rng),
                    prefers=pick_prefer(r["목적"], dining, rng, P_PREFER_GUEST),
                    wake_at=rng.choices([t for t, _ in WAKE_SPREAD], weights=[w for _, w in WAKE_SPREAD])[0],
                    note="격자 생성 · 구매력은 실험 가정 · 성향 미상")
        out.append((f"{date}#{i+1}", f"{date}#{i+1}", SimpleNamespace(PERSONA=p, START_AT=checkin)))
    if unassigned_child:
        warnings.warn(f"{date}: 아동 동반 {unassigned_child}팀 배정 보류 — 그랜드 · 비스타 잔여 객실 없음. 실제 생성 투숙팀 수는 요청 수보다 적다", RuntimeWarning)
    for j in range(n_day):
        r = rng.choices(d_rows, weights=d_w)[0]
        party = pick_dist(((wd or {}).get("party") or {}).get(r["목적"]) or r["인원수"], rng)
        kid = rng.random() < r["아동동반"] and party >= 2
        # 비투숙 도착: 점심 손님 11:00 · 저녁 손님 17:00 (△ 가정 4:6) · 떠나는 시각 22:00
        hour = rng.choices([h for h, _ in DAY_ARRIVE], weights=[w for _, w in DAY_ARRIVE])[0]   # 기본 (11:0.4 · 17:0.6) 은 전과 같은 난수 소비 · 같은 결과
        arrive = datetime.strptime(date, "%Y-%m-%d").replace(hour=hour, minute=0)
        p = Persona(name=f"{date} 비투숙 #{j+1} {r['목적']}", traits={k: None for k in TRAITS},
                    party_size=party, has_child_under_13=kid, nights=0, property="GRAND", is_guest=False,
                    depart_by=time(22, 0), sex=r["성별"], age_band=r["연령"], purpose=r["목적"],
                    ai_type=pick_type(r["목적"], type_mix or {}, rng),
                    prefers=pick_prefer(r["목적"], day_dining, rng, P_PREFER_DAY),
                    note="격자 생성 · 비투숙 규모 가정 · 성향 미상")
        out.append((f"{date}D#{j+1}", f"{date}D#{j+1}", SimpleNamespace(PERSONA=p, START_AT=arrive)))
    return out


def report(date, stays, fac, cap=None, carry=None):
    report.reroute_written = getattr(report, "reroute_written", False)
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
        for venue, n, seated, away, dmin in cap.summary(datetime.strptime(date, "%Y-%m-%d").date()):
            if seated or away:
                print(f"  {venue:8s} {n:>5d} {seated:>8d} {away:>7d} {dmin:>8,.0f}")
    if cap is not None and cap.events:
        # 붐빌 때 어디로 가나 (10/2 · reroute.py) — 돌려보내진 손님이 그 끼니를 어디서 해결했나
        mat, n_who = reroute.matrix(cap, stays_lines)
        reroute.print_matrix(mat, n_who, date)
        reroute.write_csv(mat, date, append=report.reroute_written)
        report.reroute_written = True
    # 목적별 — 온톨로지 "고객 관점에서 역으로 보기" 와 같은 표
    by_p = defaultdict(lambda: [0, 0.0])
    for (n, label, m), lines in stays_lines:
        by_p[m.PERSONA.purpose][0] += 1
        by_p[m.PERSONA.purpose][1] += sum(l["krw"] for l in lines)
    print(f"\n  {'목적':12s} {'팀':>4s} {'결제액':>14s} {'팀당':>10s}")
    for p, (c, krw) in sorted(by_p.items(), key=lambda kv: -kv[1][1]):
        print(f"  {p:12s} {c:>4d} {krw:>14,.0f} {krw/c:>10,.0f}")
    # 상품별 — 메뉴 선택 층이 켜져 있으면 업장 안에서 무엇이 팔렸나 (대표님 원장 L4 · 상품 선택률 "(가정)" 자리)
    if revenue.USE_MENU:
        by_prod = defaultdict(lambda: [0, 0.0])
        for _, lines in stays_lines:
            for l in lines:
                if l["krw"] > 0:
                    by_prod[(l["l3"], l.get("product", l["key"]))][0] += l["qty"]; by_prod[(l["l3"], l.get("product", l["key"]))][1] += l["krw"]
        print(f"\n  {'업장':8s} {'상품':40s} {'수량':>5s} {'결제액':>13s}")
        last = None
        for (l3, prod), (q, krw) in sorted(by_prod.items(), key=lambda kv: (kv[0][0], -kv[1][1])):
            print(f"  {l3 if l3 != last else '':8s} {prod[:40]:40s} {q:>5d} {krw:>13,.0f}")
            last = l3
        mm = revenue.menu_mod.default()
        if mm is not None:
            print(f"\n  메뉴 선택 층: 상품표에 없어 가격표 값으로 {mm.fallbacks}줄 · 시간 창 밖 {mm.off_window}줄")
            mm.fallbacks = mm.off_window = 0
    return stays_lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append", default=None)
    ap.add_argument("--scale", type=float, default=1.0, help="전체 실험 규모 비율 (1.0 = 객실 전부 × 가동률 79%%, 독립 비투숙 규모도 함께 적용)")
    ap.add_argument("--no-cap", action="store_true", help="좌석 상한 끄기")
    ap.add_argument("--occupancy", type=float, default=1.0, help="팔 수 있는 좌석 비율 (온톨로지 좌석 점유율 조정값)")
    day_args = ap.add_mutually_exclusive_group()
    day_args.add_argument("--day-parties", type=int, default=None, help="각 날짜의 비투숙 팀 수 (전체 scale 적용 전, 날짜 배율 추가 없음)")
    day_args.add_argument("--day-scenario", choices=("low", "base", "high"), default=None, help="독립 외부팀 규모 가정 (기본 base)")
    day_args.add_argument("--day-scale", type=float, default=None, help="이전 격자 비율 방식 재현용; 실제 외부 규모 근거 아님")
    ap.add_argument("--day-config", type=Path, default=HERE / "day_visit_scenarios.json", help="비투숙 독립 규모 설정 파일")
    ap.add_argument("--prefer", type=float, default=None, help="투숙 손님의 식당 선호 비율 (기본 P_PREFER_GUEST)")
    ap.add_argument("--grid-purpose", action="store_true", help="목적 분포를 격자 그대로 (기본은 purpose_mix.csv — 슬기 39편 + 온톨로지)")
    ap.add_argument("--grid-age", action="store_true", help="연령 분포를 격자 그대로 (기본은 age_mix.csv — 온톨로지 25/50/25)")
    ap.add_argument("--no-menu", action="store_true", help="메뉴 선택 층(menu.py · 소연 상품표) 끄기 — 업장당 값 하나 (10/1 방식)")
    ap.add_argument("--state", type=Path, default=None,
                    help="이어 돌리기 — 이 파일이 있으면 전날까지의 이어묵음 · 좌석표 · 집계행을 읽고 이어서, 끝나면 다시 저장한다 (31일을 몇 번에 나눠 돌릴 때)")
    ap.add_argument("--close", action="append", default=[], metavar="업장코드=YYYY-MM-DD[~YYYY-MM-DD]",
                    help="변칙 시나리오 — 그 업장을 그 날짜에 닫는다. 예: THE_BUFFET=2026-10-07")
    ap.add_argument("--set", action="append", default=[], metavar="모듈.이름=값",
                    help="조정값 덮어쓰기 (민감도 실험용 · sensitivity.py). 예: generate.OCC_BASE=0.6 menu.W_LEDGER=1")
    a = ap.parse_args()
    if a.no_menu:
        revenue.USE_MENU = False
    for item in a.set:
        target, val = item.split("=", 1)
        mod_name, attr = target.split(".", 1)
        mod = {"generate": sys.modules[__name__], "menu": revenue.menu_mod, "capacity": sys.modules["capacity"],
               "prices": sys.modules["prices"], "revenue": revenue,
               "agent_v4": revenue.agent_v4}[mod_name]   # 10/8 소연 — agent_v4.WINE_FAIR_PUBLIC=1 (와인페어 비투숙도)
        if "." in attr:
            # 10/6 — 사전 안의 칸 하나 (예: prices.SEATS.더뷔페.n=338 · 테라스 50석을 홀에 더하는 시나리오)
            head, *keys = attr.split(".")
            if not hasattr(mod, head):
                ap.error(f"--set: {target} 가 없다")
            box = getattr(mod, head)
            for k in keys[:-1]:
                if k not in box:
                    ap.error(f"--set: {target} 의 {k} 가 없다")
                box = box[k]
            if keys[-1] not in box:
                ap.error(f"--set: {target} 가 없다")
            box[keys[-1]] = type(box[keys[-1]])(val)
            print(f"[조정값] {target} = {box[keys[-1]]}")
            continue
        if not hasattr(mod, attr):
            ap.error(f"--set: {target} 가 없다")
        setattr(mod, attr, type(getattr(mod, attr))(val))
        print(f"[조정값] {target} = {getattr(mod, attr)}")
    for item in a.close:
        # 10/6 — 변칙 시나리오: 업장 하나를 그 날짜에 닫는다 (소연 검증기 VenueWindow.closed 칸을 그대로 쓴다)
        code, span = item.split("=", 1)
        d0, _, d1 = span.partition("~")
        import datetime as _dt
        d0 = _dt.date.fromisoformat(d0); d1 = _dt.date.fromisoformat(d1) if d1 else d0
        import dataclasses, walkerhill_timeline_validator as _V
        if code not in _V.WALKERHILL_VENUE_WINDOWS:
            ap.error(f"--close: {code} 는 검증기 창에 없다 ({', '.join(_V.WALKERHILL_VENUE_WINDOWS)})")
        _V.WALKERHILL_VENUE_WINDOWS[code] = tuple(dataclasses.replace(w, closed=tuple(w.closed) + ((d0, d1),))
                                                 for w in _V.WALKERHILL_VENUE_WINDOWS[code])
        print(f"[시나리오] {code} 닫음 {d0} ~ {d1}")
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
    amix = None if a.grid_age else load_mix(HERE / "age_mix.csv", key="연령")
    tmix = load_type_mix()
    dates = sorted(a.date or ["2026-10-10"])
    all_lines = []
    carry = {}; prev = None; cap = None
    if a.state is not None and a.state.exists():
        import pickle
        st = pickle.load(a.state.open("rb"))
        all_lines, carry, prev, cap = st["all_lines"], st["carry"], st["prev"], st["cap"]
        print(f"[이어 돌리기] {a.state.name}: {prev} 까지 {len(all_lines)} 체류 · 이어묵음 {dict(carry)}")
    for d in dates:
        if prev is None or (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(prev, "%Y-%m-%d")).days != 1:
            carry = {}                       # 이어지는 날짜가 아니면 이어묵는 손님 없음
            # 좌석도 새로. 이어지는 날짜면 Capacity 를 그대로 — 전날 2박 손님의 오늘 끼니가 이미 잡혀 있어 오늘 손님과 좌석을 나눠 쓴다 (10/2 · 한호 지적)
            cap = None if a.no_cap else Capacity(occupancy=a.occupancy)
        if cap is not None:
            cap.prune(datetime.strptime(d, "%Y-%m-%d"))   # 어제까지 끝난 예약은 버린다 — 오늘 끼니 잡는 건 오늘 이후 예약뿐
        stays = guests_for(d, grid, factors, scale=a.scale, purpose_mix=pmix, type_mix=tmix, carry=carry,
                           day_parties=a.day_parties, day_scenario=a.day_scenario or "base",
                           day_config=day_config, legacy_day_scale=a.day_scale, age_mix=amix)
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
    # 10/12 · 행동 전환 기록 — 자리가 없어 원래 선택 대신 다른 행동을 고른 손님 (근거 사슬 '만석 → 포장' 검증용)
    import agent_v4 as _A
    if _A.SWITCH_LOG:
        with (HERE / "reroute_log.csv").open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["날짜", "손님", "투숙", "시각", "원래", "사유", "원래 점수", "대체", "대체 점수"])
            for r in _A.SWITCH_LOG:
                w.writerow([r["날짜"], r["손님"], "투숙" if r["투숙"] else "비투숙", r["시각"].strftime("%H:%M"), r["원래"], r["사유"], r["원래_점수"], r["대체"], r["대체_점수"]])
        from collections import Counter as _C
        pairs = _C((r["원래"], r["대체"]) for r in _A.SWITCH_LOG)
        print(f"  행동 전환 → reroute_log.csv ({len(_A.SWITCH_LOG)} 줄) · 많은 순: " + " · ".join(f"{o}→{d} {n}" for (o, d), n in pairs.most_common(5)))
    if a.state is not None:
        import pickle
        pickle.dump(dict(all_lines=all_lines, carry=carry, prev=prev, cap=cap), a.state.open("wb"))
        print(f"  상태 저장 → {a.state.name} ({prev} 까지)")


if __name__ == "__main__":
    main()

