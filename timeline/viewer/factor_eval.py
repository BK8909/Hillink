"""행동 결정 요인 분석 (10/16) — 후기 손님 59 체류에서 정보를 넣고 빼며 행동 재현이 어떻게 변하는지 잰다.

  python3 factor_eval.py run      # 실험을 돌려 cache/factor_runs.json 에 체류별 결과를 남긴다 (약 30분)
  python3 factor_eval.py run C1,C2,C3   # 조건 몇 개만 다시 돌려 장소별 확률을 채운다 (기록된 Brier 와 같은지 확인)
  python3 factor_eval.py build    # 체류별 결과 + 민감도 기록으로 static/factor_eval.json 을 만든다 (화면 · 어시스턴트가 읽음)

조건 (모두 같은 손님 · 같은 난수 줄 · 12번 확률 선택 τ 0.5 · 좌석 경쟁 없음)
  A    지금 기본 (성향 강도 0)                     A0   성향 완전 제외 (포장의 대기 회피 우회까지)
  B1   후기 성향 강도 1                             B2   강도 2
  C1   예약 정보 제외                               C2   식사 포함 혜택 정보 제외      C3  둘 다 제외
측정하지 않은 조합(예: 예약 제외 + 성향 1)은 만들지 않는다. 화면도 그 조합에는 숫자를 보이지 않는다.
"""
from __future__ import annotations

import json
import random
import statistics as st
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
sys.path.insert(0, str(TL))
import agent_v4, fit_v4  # noqa: E402
from match import BASELINE_PLACES, TRANSIT, visits_from_segments  # noqa: E402

K = 12
RUNS = HERE / "cache" / "factor_runs.json"
OUT = HERE / "static" / "factor_eval.json"
TH = 0.005          # 체류 하나의 Brier 차이가 이보다 작으면 '같음'


def run_one(m, th, p):
    start = getattr(m, "START_AT", datetime(2025, 1, 31, 14, 0))
    reach = agent_v4.reachable(p)
    seen = Counter(); R = P = 0.0
    for i in range(K):
        segs, _ = agent_v4.run_agent(p, start, verbose=False, theta=th, rng=random.Random(fit_v4.SEED + i))
        r = fit_v4.evaluate(segs, m, reachable=reach); R += r.recall; P += r.precision
        for pl in {v.place for v in visits_from_segments(segs)}:
            seen[pl] += 1
    places = [x for x in reach | set(seen) if x not in BASELINE_PLACES and x not in TRANSIT and x not in getattr(m, "TRUTH_PASSED", {})]
    truth = set(m.TRUTH_VISITED)
    brier = sum(((1.0 if x in truth else 0.0) - seen[x] / K) ** 2 for x in places) / max(1, len(places))
    return dict(recall=R / K, precision=P / K, brier=brier, prob={x: round(seen[x] / K, 3) for x in places})


def run(only=None):
    """only = 조건 몇 개만 (예: C1,C2,C3) — 기존 cache/factor_runs.json 에 장소별 확률을 채운다. 같은 난수라 기록된 Brier 와 같아야 한다"""
    prev = {d["stay"]: d for d in json.loads(RUNS.read_text(encoding="utf-8"))} if only else {}
    out = []
    base = dict(agent_v4.THETA_FIT, lam_trait=0)
    for g, lab, m in fit_v4.stays():
        p = m.PERSONA
        conds = {
            "A": (base, p),
            "A0": (base, replace(p, traits={k: None for k in p.traits})),
            "B1": (dict(base, lam_trait=1.0), p),
            "B2": (dict(base, lam_trait=2.0), p),
            "C1": (base, replace(p, booked=())),
            "C2": (base, replace(p, included_meals=())),
            "C3": (base, replace(p, booked=(), included_meals=())),
        }
        if only:
            d = prev[lab]
            for k in only:
                r = run_one(m, *conds[k])
                assert abs(r["brier"] - d["res"][k]["brier"]) < 1e-9, (lab, k, r["brier"], d["res"][k]["brier"])   # 기록과 같은 실행인지
                d["res"][k] = r
            out.append(d); print(lab, "ok", flush=True)
            continue
        res = {k: run_one(m, th, pp) for k, (th, pp) in conds.items()}
        out.append(dict(stay=lab, traits={k: v for k, v in (p.traits or {}).items() if v is not None},
                        booked=list(p.booked), incl=[list(x) for x in (p.included_meals or ())],
                        truth=sorted(set(m.TRUTH_VISITED)), res=res))
        print(lab, {k: round(v["brier"], 3) for k, v in res.items()}, flush=True)
    RUNS.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


COND = [
    ("A", "기본 모델", "기준", "예약 · 식사 포함 혜택 · 방문 목적 · 아동 동반 · 공급 제약으로 선택 (성향 강도 0)", dict(book=1, incl=1, trait="0")),
    ("A0", "성향 완전 제외", "성향", "포장 선택의 대기 회피 우회 경로까지 끔", dict(book=1, incl=1, trait="off")),
    ("B1", "후기 성향 추가 · 강도 1", "성향", "후기에서 뽑은 성향 7개를 점수에 넣음", dict(book=1, incl=1, trait="1")),
    ("B2", "후기 성향 추가 · 강도 2", "성향", "", dict(book=1, incl=1, trait="2")),
    ("C1", "예약 정보 제외", "정보 제외", "후기에 적힌 방문 전 예약 사실을 뺌", dict(book=0, incl=1, trait="0")),
    ("C2", "식사 포함 혜택 정보 제외", "정보 제외", "객실 상품에 포함된 식사 정보를 뺌", dict(book=1, incl=0, trait="0")),
    ("C3", "예약 · 식사 포함 혜택 모두 제외", "정보 제외", "", dict(book=0, incl=0, trait="0")),
]


def agg(D, c):
    if not D:
        return None
    r = dict(recall=round(st.mean(d["res"][c]["recall"] for d in D) * 100, 1),
             precision=round(st.mean(d["res"][c]["precision"] for d in D) * 100, 1),
             brier=round(st.mean(d["res"][c]["brier"] for d in D), 4))
    if c != "A":
        diffs = [d["res"][c]["brier"] - d["res"]["A"]["brier"] for d in D]
        r["cmp"] = dict(better=sum(1 for x in diffs if x < -TH), same=sum(1 for x in diffs if abs(x) <= TH), worse=sum(1 for x in diffs if x > TH))
        if all("prob" in d["res"][c] for d in D):     # 장소별 확률이 기록된 조건만
            r["moved"] = sum(1 for d in D if any(abs(d["res"][c]["prob"].get(x, 0) - d["res"]["A"]["prob"].get(x, 0)) > 0.25
                                                 for x in set(d["res"][c]["prob"]) | set(d["res"]["A"]["prob"])))
    return r


def build():
    D = json.loads(RUNS.read_text(encoding="utf-8"))
    hi = lambda t: [d for d in D if (d["traits"].get(t) or 0) >= 0.6]
    # 10/16 분석 대상 — '관측 행동' (후기에서 실제로 관찰된 방문) 과 '고객군' (같은 방문을 손님 조건으로 나눈 묶음) 을 구분한다
    groups = [
        ("all", "후기 손님이 실제로 간 곳", "behavior", f"후기 46편 · 성향 값이 있는 {len(D)} 체류 전체", D, ""),
        ("book", "예약한 곳이 있는 손님", "segment", None, [d for d in D if d["booked"]], "후기에 방문 전 예약이 적힌 체류"),
        ("incl", "패키지 포함 식사가 있는 손님", "segment", None, [d for d in D if d["incl"]], "객실 상품에 포함된 식사가 있는 체류"),
        ("wait", "대기 회피 성향이 높은 손님", "segment", None, hi("대기 회피"), "후기에서 뽑은 대기 회피 값 0.6 이상"),
        ("view", "조망을 중시하는 손님", "segment", None, hi("조망 중시"), "후기에서 뽑은 조망 중시 값 0.6 이상"),
        ("quiet", "조용함을 선호하는 손님", "segment", None, hi("조용함 선호"), "후기에서 뽑은 조용함 선호 값 0.6 이상"),
    ]
    G = []
    for gid, name, kind, sub, rows, note in groups:
        G.append(dict(id=gid, name=name, kind=kind, n=len(rows), sub=sub or f"{len(rows)} 체류 · {note}",
                      res={c: agg(rows, c) for c, *_ in COND}))
    stays = [dict(stay=d["stay"], traits=d["traits"], booked=d["booked"], incl=[x[1] for x in d["incl"]], truth=d["truth"],
                  res={c: dict(brier=round(d["res"][c]["brier"], 4), recall=round(d["res"][c]["recall"] * 100, 1)) for c, *_ in COND},
                  prob={c: d["res"][c]["prob"] for c, *_ in COND if "prob" in d["res"][c]}) for d in D]   # 10/16 정보 제외 조건도 장소별 확률 (run C1,C2,C3 로 채움)
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    out = dict(
        built=datetime.now().strftime("%Y-%m-%d"), model_ver=__import__("version").model_ver(),
        sample=f"후기 46편 · 성향 값이 있는 {len(D)} 체류 · {K}번 확률 선택(τ 0.5) · 같은 난수 줄 · 좌석 경쟁 없음",
        metric="재현 = 후기가 간 곳 중 모델도 간 곳 · 정밀 = 모델이 간 곳 중 후기에 있는 곳 · Brier = 장소마다 갈 확률과 후기(갔다 1 · 아니면 0)의 제곱 차이 평균 (낮을수록 좋음)",
        caveat="탐색 결과입니다. 봉인 11편이 9/29에 풀려 독립 검증 자료가 없습니다. 어느 정보에 기대는지를 가른 것이지 실제 예측 성능이 좋다는 입증이 아니며, 묶음 결과로 한 손님의 행동 원인을 단정하지 않습니다. 예약 · 식사 포함 혜택은 후기에서 사후 복원한 방문 전 사실이라 호텔이 사전에 보유한 예약 기록과 같은 뜻은 아닙니다.",
        same_th=TH, cond=[dict(id=c, name=n, kind=k, note=no, sel=s) for c, n, k, no, s in COND],
        groups=G, stays=stays, sensitivity=old.get("sensitivity"), doc="근거사슬_가설실험_1014 7-15 · 7-16 · 7-18",
        planned=[dict(id="wait_inv", name="대기 회피 성향 역추정", n=13, status="탐색 완료", note="후기 대기 행동 13건 · 조건부 대기 회피 가설의 추가 설명력 탐색 (wait_inv.py · static/wait_inv.json · 근거사슬 7-20)"),
                 dict(id="photo", name="SNS 캡션 vs 캡션 + 사진", n=None, status="진행 예정", note="같은 게시물 30~50건에서 사진이 더해 주는 관찰 정보와 미확인 비율"),
                 dict(id="pref", name="목적별 선호 식당 제외", n=None, status="진행 예정", note="하루 전체 손님(고객 유형표)에서만 의미 있음 · 집단 시뮬레이션 민감도")],
    )
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("→", OUT, len(stays), "체류")


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "run" and len(sys.argv) > 2:
        run(sys.argv[2].split(","))        # python3 factor_eval.py run C1,C2,C3
    else:
        {"run": run, "build": build}[cmd]()
