"""데이터 기여도 · 추가 데이터 가치 분석 (10/16 · 리뷰 제안 · 근거사슬 7-23 · docs/데이터_가치_분석_1016.md)

  python3 data_value.py stage1     # 이미 돌린 정보 제거 · 성향 · LLM 실험을 같은 잣대로 다시 매김 (API 호출 · 새 시뮬레이션 없음)
  python3 data_value.py stage2     # 피자힐 대기 시간 정보의 가치 — 같은 후기 손님에 대기 0 · 20 · 40 · 60분을 주고 선택 변화를 잰다 (몇 분)
  python3 data_value.py all

결과는 static/data_value.json. 숫자는 모두 모델 안의 결과이며 실제 고객 반응의 측정값이 아니다.

1단계 — 이미 검증한 데이터 기여도
  factor_eval.json(정보 제거 · 성향 강도 · 같은 난수 12번)과 llm_pilot.json(LLM · 5번)의 체류별 장소 확률을 같은 방식으로 다시 매긴다.
  · 체류별 짝 차이의 평균 ± 표준오차 (59 체류 기준 · 반복 횟수는 표본 수가 아님)
  · 정답 정의 세 가지: 후기에 적히지 않은 곳도 미방문 / 언급 없음 제외 / 명시 미방문만
  · 순위 판별(AUC): 같은 체류에서 간 곳에 명시 미방문보다 높은 확률을 줬는가 — 전체 확률 수준과 무관
  결론이 정답 정의에 따라 바뀌는 요인과 안 바뀌는 요인을 가른다.

2단계 — 추가 데이터의 잠재적 활용 가치 (피자힐 대기)
  후기 손님 59 체류를 혼자 돌리되(다른 손님 없음) 피자힐 석식에만 정해진 길이의 줄을 세운다(wait_inv.py 의 LineAt · 식당 앞 줄을 대기로 세는 실험 조건).
  조건: 지금 모델(성향 강도 0) · 성향 반영(강도 1, 대기 회피 0 · 0.5 · 1). 석식 결과를 피자힐 매장 · 포장 · 다른 호텔 식당 · 식당 외로 나눈다.
  보는 것: ① 대기 시간이 바뀔 때 선택이 얼마나 움직이나 ② 같은 대기에서 성향이 바뀔 때 얼마나 움직이나
           ③ '이탈 여부' 만 보면 구분할 수 없는 조합(성향 높음 · 대기 짧음 ↔ 성향 낮음 · 대기 김)이 있는가 — 대기 기록이 있어야 둘을 가른다
           ④ 지금 v4.1 규칙(줄 30분 상한 · 예약 대기 · 객실 출발 시 대기 벌점 없음) 그대로면 대기 정보가 선택을 바꾸는가 — 데이터 가치는 모델 구조에도 달려 있다
  이 실험으로 '예측력이 좋아졌다' 고 말할 수 없다. 실제 대기 · 선택 기록이 있어야 검증된다.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
sys.path.insert(0, str(TL)); sys.path.insert(0, str(HERE))
import agent_v4, fit_v4  # noqa: E402

OUT = HERE / "static" / "data_value.json"
COND_NAME = {"A": "기본 모델", "A0": "성향 완전 제외", "B1": "성향 강도 1", "B2": "성향 강도 2", "C1": "예약 정보 제외", "C2": "식사 포함 혜택 제외", "C3": "예약 · 혜택 모두 제외"}


def _tier(v):
    v = str(v)
    return 1 if v.startswith("◎") else 3 if "언급 없음" in v else 2


def _score(probs_by_stay, S, maxtier):
    """체류별 Brier — maxtier None: 후보 장소 전부(적히지 않은 곳도 미방문) · 2: 언급 없음 제외 · 1: 명시 미방문만"""
    out = {}
    for lab, P in probs_by_stay.items():
        m = S[lab]; T = set(m.TRUTH_VISITED); NV = {k: _tier(v) for k, v in (getattr(m, "TRUTH_NOT_VISITED", {}) or {}).items()}
        e = [((1 - p) ** 2 if pl in T else p ** 2) for pl, p in P.items() if pl in T or maxtier is None or (pl in NV and NV[pl] <= maxtier)]
        out[lab] = sum(e) / len(e) if e else None
    return out


def _auc(probs_by_stay, S, tier=1):
    win = n = 0.0
    for lab, P in probs_by_stay.items():
        m = S[lab]; T = set(m.TRUTH_VISITED); NV = {k: _tier(v) for k, v in (getattr(m, "TRUTH_NOT_VISITED", {}) or {}).items()}
        pos = [P[p] for p in P if p in T]; neg = [P[p] for p in P if p not in T and NV.get(p) == tier]
        for u in pos:
            for w in neg:
                n += 1; win += 1.0 if u > w else 0.5 if u == w else 0.0
    return round(win / n, 3) if n else None


def _paired(a, b):
    dd = [b[k] - a[k] for k in a if a[k] is not None and b.get(k) is not None]
    mu = sum(dd) / len(dd); se = (sum((x - mu) ** 2 for x in dd) / (len(dd) - 1) / len(dd)) ** 0.5
    return dict(d=round(mu, 4), se=round(se, 4), z=round(mu / se, 1) if se else None, better=sum(1 for x in dd if x < -0.005), worse=sum(1 for x in dd if x > 0.005), n=len(dd))


def _read(d):
    """d=+면 악화 (Brier 는 낮을수록 좋음). 2 표준오차를 넘으면 방향을 말하고, 아니면 '구분 안 됨'"""
    if d["z"] is None or abs(d["z"]) < 2:
        return "구분 안 됨"
    return "악화" if d["d"] > 0 else "개선"


def stage1():
    S = {lab: m for g, lab, m in fit_v4.stays()}
    F = json.loads((HERE / "static" / "factor_eval.json").read_text(encoding="utf-8"))
    TIERS = [("all", None, "적히지 않은 곳도 미방문 (지금 방식)"), ("no_unm", 2, "언급 없음 제외"), ("explicit", 1, "명시 미방문만")]
    rows = []
    # 정보 제거 · 성향 — 같은 난수 12번
    fp = {c: {s["stay"]: s["prob"][c] for s in F["stays"]} for c in F["stays"][0]["prob"]}
    base = {t: _score(fp["A"], S, mt) for t, mt, _ in TIERS}
    for c in ("C1", "C2", "C3", "A0", "B1", "B2"):
        r = dict(id=c, name=COND_NAME[c], family="정보 제거" if c.startswith("C") else "성향", source="factor_eval.json · 12번",
                 auc={"base": _auc(fp["A"], S), "cond": _auc(fp[c], S)})
        for t, mt, _ in TIERS:
            r[t] = _paired(base[t], _score(fp[c], S, mt)); r[t]["read"] = _read(r[t])
        rows.append(r)
    # LLM — 5번 (A · A2 잡음 · B · C)
    L = json.loads((HERE / "static" / "llm_pilot.json").read_text(encoding="utf-8"))
    lp = {arm: {x["stay"]: x["res"][arm]["prob"] for x in L["stays"]} for arm in ("A", "A2", "B", "C")}
    lbase = {t: _score(lp["A"], S, mt) for t, mt, _ in TIERS}
    for arm, nm, fam in (("A2", "규칙 엔진 · 난수만 바꿈 (잡음 기준)", "잡음"), ("B", "모든 결정을 LLM", "LLM"), ("C", "자유 식사 결정만 LLM", "LLM")):
        r = dict(id="LLM_" + arm, name=nm, family=fam, source="llm_pilot.json · 5번", auc={"base": _auc(lp["A"], S), "cond": _auc(lp[arm], S)})
        for t, mt, _ in TIERS:
            r[t] = _paired(lbase[t], _score(lp[arm], S, mt)); r[t]["read"] = _read(r[t])
        rows.append(r)
    for r in rows:
        reads = {r[t]["read"] for t, _, _ in TIERS}
        r["robust"] = "정답 정의와 무관하게 " + reads.pop() if len(reads) == 1 else "정답 정의에 따라 달라짐"
    cnt = Counter(_tier(v) for m in S.values() for v in (getattr(m, "TRUTH_NOT_VISITED", {}) or {}).values())
    WI = json.loads((HERE / "static" / "wait_inv.json").read_text(encoding="utf-8")) if (HERE / "static" / "wait_inv.json").exists() else {}
    # 하루 손님 단위 · 목적별 선호 식당 (pref_eval.py · 10/10 · 시드 3 짝) — 후기 체류 표와 다른 잣대(온톨로지 구성비)라 따로 둔다
    PF = json.loads((HERE / "static" / "pref_eval.json").read_text(encoding="utf-8")) if (HERE / "static" / "pref_eval.json").exists() else None
    pref = None
    if PF:
        pref = dict(rows=[dict(id=r["id"], name=r["name"], comp_gap_pp=r["fit"]["comp_gap_pp"], within=r["fit"]["within"], ratio=r["ratio"],
                                d=r.get("d_comp_gap_pp"), total_eok=r["total_eok"]) for r in PF["rows"]],
                    seeds=PF["seeds"], date=PF["date"], note=PF["note"],
                    read="민감도와 독립 예측력을 나눠 읽는다. ① 10/10 · 시드 3개 · 식당 6곳 집계에서 목적별로 다른 식당 비중(목적 정보)의 추가 효과는 구분되지 않았다(−0.1%p · −0.5 ~ +0.5). 이것은 이 집계 잣대에서의 결과이며, 방문 목적이 개별 고객의 식당 선택에 영향이 없다는 뜻은 아니다. ② '가고 싶은 식당' 입력 자체를 지우면 모델의 식당 수요 분포가 크게 달라진다(+4.1%p · 3개 시드 모두 · 더뷔페 89% → 67%). 이것은 민감도다. 선호를 가질 확률 투숙 0.7 은 같은 온톨로지 10/10 식당 이용 인원에서 역산한 값(△), 비투숙 0.9 는 가정(△)이라, 온톨로지와 잘 맞는 것은 어느 정도 예상된 결과이고 실제 고객 행동을 더 잘 예측한다는 근거는 아니다. ③ 예약은 이미 이루어진 구체적 행동에 대한 정보이고, 선호는 행동을 유도하려고 모델에 넣은 확률 입력이라 같은 수준의 근거가 아니다. 지금 모델에서 선호 입력의 영향력은 크지만 그 확률은 독립적으로 검증되지 않았다. 실제 예약 · 이용 자료가 있으면 이 입력의 타당성을 평가할 수 있다.")
    return dict(tiers=[dict(id=t, name=n) for t, _, n in TIERS], rows=rows, pref=pref,
                gold={"명시 미방문 (◎)": cnt[1], "간접 (○)": cnt[2], "언급 없음": cnt[3], "간 곳": sum(len(m.TRUTH_VISITED) for m in S.values()),
                      # 10/16 QA · 원문 방문 확인(전체)과 Brier · AUC 의 분모(평가 후보 안)를 나눈다 — 후보 밖 방문(로비 · 발렛 등 행동 후보가 아닌 곳)은 평가에 안 들어감
                      "간 곳 · 평가 후보 안": sum(len(set(S[x["stay"]].TRUTH_VISITED) & set(x["prob"]["A"])) for x in F["stays"] if x["stay"] in S)},
                wait_inv=dict(verdict=WI.get("verdict"), n_info=WI.get("n_info"), n_model=WI.get("n_model")),
                rule="체류별 짝 차이 평균이 표준오차의 2배를 넘을 때만 방향(악화 · 개선)을 말한다. 59 체류 기준이며 반복 횟수는 표본 수가 아니다.")


# ---------------------------------------------------------------------------
# 2단계 — 피자힐 대기
# ---------------------------------------------------------------------------
WAITS = (0, 5, 10, 15, 20, 40, 60)       # 10/16 · 처음 0 · 20 · 40 · 60 으로 돌렸더니 20분에서 이미 매장 0 → 0~20 을 촘촘히
VS = (0.0, 0.5, 1.0)
K2 = 20


def _dinner(traces):
    for t in traces:
        k = (t.meta or {}).get("key")
        if k is None or agent_v4.meal_kind_at(t.start) != "석식":
            continue
        if k == "pizza":
            return "매장"
        if k == "pizza_to":
            return "포장"
        if k in ("meal_other", "meal_out"):
            return "식당 외"
        if k in agent_v4.MEAL_KEYS:
            return "다른 식당"
    return "석식 기록 없음"


def stage2():
    from dataclasses import replace
    with contextlib.redirect_stdout(io.StringIO()):
        import wait_inv as WI      # 식당 앞 줄을 대기로 세는 실험 조건(점수 감싸기)과 LineAt 을 그대로 쓴다
    base = dict(agent_v4.THETA_FIT)
    noq = {k: v for k, v in base.items() if k not in ("queue_max", "reserve_wait", "next_window")}
    v41q = dict(base, queue_max=30, reserve_wait=1, next_window=1)
    c = dict(venue="PIZZA_HILL", meal="석식")
    stays = []
    only_stays = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    for g, lab, m in fit_v4.stays():
        if lab.endswith("_ALT") or (only_stays and lab not in only_stays):
            continue
        p = m.PERSONA
        start = getattr(m, "START_AT", datetime(2025, 1, 31, 14, 0))
        fixed = any(k == "석식" for (k, _pl) in (p.included_meals or ())) or "PIZZA_HILL" in (p.booked or ())
        only = lambda v, p=p: replace(p, traits={k: (v if k == "대기 회피" else None) for k in p.traits})

        def dist(th, persona, w, line_as_wait=True):
            WI.LINE.update(on=line_as_wait, venue="PIZZA_HILL", meal="석식", w=w)
            cnt = Counter()
            for i in range(K2):
                cap = WI.LineAt("PIZZA_HILL", "석식", w)
                with contextlib.redirect_stdout(io.StringIO()):
                    segs, tr = agent_v4.run_agent(persona, start, verbose=False, theta=th, rng=random.Random(fit_v4.SEED + i), capacity=cap)
                cnt[_dinner(tr)] += 1
            return {k: v / K2 for k, v in cnt.items()}
        row = dict(stay=lab, fixed=fixed, cur={}, trait={}, v41={})
        for w in WAITS:
            row["cur"][str(w)] = dist(dict(noq), p, w)
            row["trait"][str(w)] = {str(v): dist(dict(noq, lam_trait=1.0), only(v), w) for v in VS}
            row["v41"][str(w)] = dist(dict(v41q), p, w, line_as_wait=False)
        stays.append(row)
        print(lab, "고정" if fixed else "자유", {w: round(row["cur"][str(w)].get("매장", 0), 2) for w in WAITS}, flush=True)

    # 피자힐을 저녁 후보로 실제로 고르는 손님만 — 대기 0분 지금 모델에서 피자힐(매장 · 포장) 비율이 10% 이상인 자유 석식 체류
    pick = [r for r in stays if not r["fixed"] and (r["cur"]["0"].get("매장", 0) + r["cur"]["0"].get("포장", 0)) >= 0.10]
    CATS = ("매장", "포장", "다른 식당", "식당 외", "석식 기록 없음")
    avg = lambda key, w, v=None: {k: round(sum((r[key][str(w)] if v is None else r[key][str(w)][str(v)]).get(k, 0) for r in pick) / max(1, len(pick)), 3) for k in CATS}
    curve = {"cur": {str(w): avg("cur", w) for w in WAITS}, "v41": {str(w): avg("v41", w) for w in WAITS},
             "trait": {str(v): {str(w): avg("trait", w, v) for w in WAITS} for v in VS}}
    # ③ 관측 동치 — '피자힐 매장을 포기한 비율' 만 보면 같은 값이 나오는 (대기 회피, 대기) 조합
    leave = {(v, w): 1 - curve["trait"][str(v)][str(w)]["매장"] / max(1e-9, curve["trait"][str(v)]["0"]["매장"]) for v in VS for w in WAITS}
    pairs = []
    for (v1, w1), a in leave.items():
        for (v2, w2), b in leave.items():
            if v1 < v2 and w1 > w2 and abs(a - b) <= 0.03 and w2 > 0 and 0.05 < a < 0.95:      # 모두 떠나거나 모두 남는 칸(포화)은 빼고
                pairs.append(dict(low_trait=dict(v=v1, wait=w1, leave=round(a, 3)), high_trait=dict(v=v2, wait=w2, leave=round(b, 3))))
    # ①② 움직임의 크기 — 대기만 바꿀 때(성향 고정) vs 성향만 바꿀 때(대기 고정), 매장 비율의 폭
    span_wait = {str(v): round(max(curve["trait"][str(v)][str(w)]["매장"] for w in WAITS) - min(curve["trait"][str(v)][str(w)]["매장"] for w in WAITS), 3) for v in VS}
    span_trait = {str(w): round(max(curve["trait"][str(v)][str(w)]["매장"] for v in VS) - min(curve["trait"][str(v)][str(w)]["매장"] for v in VS), 3) for w in WAITS}
    span_v41 = round(max(curve["v41"][str(w)]["매장"] for w in WAITS) - min(curve["v41"][str(w)]["매장"] for w in WAITS), 3)
    return dict(k=K2, waits=list(WAITS), vs=list(VS), n_stays=len(stays), n_pick=len(pick), picked=[r["stay"] for r in pick],
                curve=curve, leave={f"{v}|{w}": round(x, 3) for (v, w), x in leave.items()}, equiv=pairs,
                span_wait=span_wait, span_trait=span_trait, span_v41=span_v41,
                sample=f"후기 손님 {len(stays)} 체류 중 석식이 포함 혜택 · 피자힐 예약으로 정해지지 않았고, 대기가 없을 때 지금 모델에서 피자힐을 10% 이상 고르는 {len(pick)} 체류 · 체류마다 조건당 {K2}번 · 같은 난수 줄 · 다른 손님 없음",
                caveat="모델 안의 민감도입니다. 대기 벌점 계수(w_wait)는 후기 59 체류에 맞춘 값이고, 성향 강도 1 은 가정입니다. 실제 대기 · 선택 기록 없이 '예측이 좋아졌다' 고 말할 수 없습니다.")


# ---------------------------------------------------------------------------
# 3단계 — 행동별 관측 가능 정보 · 추가 데이터 가치 매트릭스와 확보 로드맵 (문서 · 화면이 같은 표를 읽는다)
#   숫자는 지금 자료에서 센 것. '추가 데이터' 는 있으면 무엇을 검증할 수 있는지까지만 말하고, 예측력이 좋아진다고 약속하지 않는다
# ---------------------------------------------------------------------------
MATRIX = [
    dict(behavior="식당 방문 (어디에 갔나)", now="후기에서 간 곳 266곳 확인(그중 평가 후보 안 196곳) · 안 갔다고 적힌 곳은 46곳뿐 · 간접 단서 24곳 (나머지 884곳은 관측되지 않음)",
         gap="'언급 없음' 을 미방문으로 볼지에 따라 모델 비교의 방향이 뒤집힘 (LLM · 성향 실험)",
         data="익명화된 업장 이용 · 결제 기록 (업장 · 시각 · 일행 규모)", hypo="모델 방문 확률이 실제 이용 여부와 맞는가 (미방문까지 확인된 정답)",
         metric="Brier · 순위 판별(AUC) · 업장별 이용률", level="부분 관측"),
    dict(behavior="식당 자유 선택", now="원래 · 최종 업장이 모두 확인되는 대체 선택 1건 · 예약 · 포함 혜택 없는 '방문만 확인' 은 다수",
         gap="무엇과 비교해 골랐는지 · 선택 순간에 가능했던 대안을 모름",
         data="선택 시점의 업장별 예약 가능 여부 · 대기 · 가용 좌석 (시각별 스냅샷)", hypo="성향보다 실제 이용 가능성이 선택을 더 잘 설명하는가",
         metric="선택 상황별 조건부 로그 점수 · 1순위 적중", level="거의 관측 안 됨"),
    dict(behavior="대기 후 이탈", now="후기 대기 사례 13건 · 모델로 표현되는 4건 · 값을 가를 수 있는 2건",
         gap="성격상 기다리기 싫어했는지, 실제로 너무 오래 기다려야 했는지 분리 불가 (대기 시간 미관측)",
         data="익명 대기 등록 · 안내 대기 시간 · 호출 · 취소 시각", hypo="대기 시간이 길어질수록 유지 · 포장 · 이동 · 포기 비율이 어떻게 바뀌나",
         metric="대기 구간별 이탈률 곡선 적합 · 보류 기간 검증", level="거의 관측 안 됨"),
    dict(behavior="대체 식당 선택 (이탈 수요의 행방)", now="모델은 막힌 식사의 행방을 계산 (예: 10/10 더뷔페에서 이용이 제한된 식사의 82% 가 호텔 밖 · 객실) · 후기에서 확인되는 경로는 1건",
         gap="모델의 행방 분포를 검증할 관측이 없음",
         data="예약 취소 · 변경 후 다른 업장 예약 · 이용 기록 (익명 키로 연결)", hypo="혼잡한 업장에서 빠진 수요가 어디로 가나",
         metric="행방 분포 비교 (호텔 안 다른 업장 · 호텔 밖 · 포기)", level="관측 안 됨"),
    dict(behavior="조식 이용 · 비이용", now="후기 조식 언급 34건 · 비이용 명시 소수 · 모델의 '식당 외 식사' 비중이 높다는 신호 (LLM 1차)",
         gap="후기에 안 적은 것과 실제로 안 먹은 것을 구분 못 함 · 2부 쏠림은 기상 시각 가정(△)에 민감 (초과 수요 198~546명)",
         data="조식 포함 객실 수 · 회차별 실제 입장 인원 · 입장 시각", hypo="포함 혜택과 이용 가능 시간대가 조식 이용 · 회차를 얼마나 설명하나",
         metric="포함 객실 대비 이용률 · 회차별 입장 분포", level="부분 관측"),
    dict(behavior="호텔 내 추가 이용 (순서)", now="후기 순서 쌍 144개",
         gap="미방문 판정이 불확실해 '다음에 무엇을 안 했는지' 를 모름",
         data="익명화된 시설 이용 · 결제 시계열", hypo="한 시설 이용 뒤 어떤 추가 이용이 나타나나",
         metric="순서 재현율 · 전환 확률", level="부분 관측"),
    dict(behavior="방문 유도 (콘텐츠 · SNS)", now="피자힐 SNS 게시 28건 집계 (개인과 연결 안 됨)",
         gap="선택 전에 어떤 정보를 봤는지 모름",
         data="콘텐츠 노출 · 예약 전환 기록 (집계)", hypo="선택 전에 제공된 정보가 실제 예약과 연결되나",
         metric="노출 대비 예약 전환", level="집계만"),
]
ROADMAP = [
    dict(rank=1, item="조식 회차별 입장 인원 · 조식 포함 객실 수", unit="회차 × 날짜 (개인 연결 불필요)", period="평일 · 주말이 섞인 2주 이상",
         link="날짜 · 회차 집계만", verify="조식 이용률 · 2부 쏠림 (기상 시각 가정 △)", why="운영 요약 숫자를 가장 크게 움직이는 약한 고리 · 매일 생기는 집계 · 개인정보 부담 낮음",
         use="조식 준비량 · 회차 안내"),
    dict(rank=2, item="피자힐 대기 등록 · 안내 대기 시간 · 호출 · 취소 시각", unit="대기 1건 (익명 번호)", period="주말 포함 4주 이상",
         link="대기 건 단위 · 같은 날 다른 업장 이용과는 익명 키로만", verify="대기 구간별 유지 · 포장 · 이탈 곡선 · 성향과 대기 조건 분리", why="지금 모델의 대기 반응은 자료가 없어 계단 모양 (2단계)",
         use="대기 관리 · 포장 안내 · 대체 업장 추천"),
    dict(rank=3, item="업장별 예약 가능 여부 · 가용 좌석 (시각별 스냅샷)", unit="업장 × 30분", period="2주 이상",
         link="시각 · 업장 집계", verify="자유 선택에서 이용 가능성 vs 성향", why="자유 선택 정답의 '선택 순간 대안' 을 채움",
         use="예약 안내 · 수요 분산"),
    dict(rank=4, item="예약 변경 · 취소 후 다른 업장 예약 · 이용", unit="예약 1건 (익명 키)", period="4주 이상",
         link="같은 고객의 기록을 익명 키로 연결", verify="이탈 수요의 행방", why="모델의 행방 표를 처음 검증",
         use="휴업 · 만석 시 대체 업장 준비"),
    dict(rank=5, item="익명화된 시설 이용 · 결제 시계열", unit="이용 1건 (익명 키 · 시각)", period="4주 이상",
         link="익명 키 · 시각 순서", verify="방문 확률 · 추가 이용 순서 (미방문까지 확인된 정답)", why="정답의 '관측되지 않음' 을 줄이는 근본 자료 · 개인 연결이 필요해 가장 나중",
         use="동선 · 교차 판매"),
]
RULES = ["실제 선택 뒤에 생긴 기록을 그 선택의 예측 입력으로 쓰지 않는다 (시간 순서)",
         "개인을 식별하지 않는 익명 키 · 집계 단위를 먼저 요청하고, 연결이 꼭 필요한 항목만 익명 키로 연결한다",
         "받은 기간의 일부는 미리 보지 않은 검증 기간으로 남긴다",
         "자료가 있으면 무조건 예측이 좋아진다고 약속하지 않는다 · 각 자료가 검증하게 해 주는 가설과 평가 지표만 약속한다"]


def stage3():
    return dict(matrix=MATRIX, roadmap=ROADMAP, rules=RULES)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    res.update(built=datetime.now().strftime("%Y-%m-%d %H:%M"), model_ver=__import__("version").model_ver())
    if cmd in ("stage1", "all"):
        res["stage1"] = stage1()
        for r in res["stage1"]["rows"]:
            print(f"{r['name']:<22} " + " | ".join(f"{t['id']} {r[t['id']]['d']:+.4f}±{r[t['id']]['se']:.4f} {r[t['id']]['read']}" for t in res["stage1"]["tiers"]) + f" | AUC {r['auc']['base']}→{r['auc']['cond']} | {r['robust']}")
    if cmd in ("stage3", "stage1", "all"):
        res["stage3"] = stage3()
    if cmd in ("stage2", "all"):
        res["stage2"] = stage2()
        s2 = res["stage2"]
        print(s2["sample"]); print("지금 모델", s2["curve"]["cur"]); print("v4.1 규칙 그대로", s2["curve"]["v41"])
        for v in s2["vs"]:
            print("대기 회피", v, {w: s2["curve"]["trait"][str(v)][str(w)]["매장"] for w in s2["waits"]})
        print("대기만 바꿀 때 폭", s2["span_wait"], "성향만 바꿀 때 폭", s2["span_trait"], "v4.1 규칙 폭", s2["span_v41"]); print("관측 동치", s2["equiv"])
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
