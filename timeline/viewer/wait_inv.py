"""대기 회피 역추정 (10/16 · 작업배정 항목 18 · 근거사슬 7-20) — 후기에서 실제로 관찰된 '대기 뒤 선택' 을 가장 잘 설명하는 대기 회피 값을 찾는다.

  python3 wait_inv.py run      # 사례 × 대기 회피 값 격자 × 줄 길이를 돌려 static/wait_inv.json 을 만든다 (1~2분)

무엇을 하나
  1. 후기에서 대기 · 혼잡을 겪거나 피한 체류 13건(슬기님 10/7 표 11건 + 근거사슬 7-10 의 blog05 · blog06)을 모은다.
     지금 모델이 '줄을 설까 다른 걸 할까' 를 고르는 선택으로 표현할 수 있는 사례만 실험에 쓰고, 나머지는 왜 안 되는지 적는다
     (업장 안의 음식 줄 · 도착 시각이나 예약으로 미리 피함 · 포함 식사 규칙으로 정해짐).
  2. 쓸 수 있는 사례마다 같은 후기 손님을 혼자 돌리되, 관찰된 업장에만 후기에 적힌 길이의 줄을 세운다(다른 손님 없음).
     줄 길이가 후기에 숫자로 없으면 범위(낮음 · 기준 · 높음)로 두고 그렇다고 적는다.
  3. 대기 회피 값 v 를 0 ~ 1 격자로 바꿔(성향 강도 1 · 다른 성향은 비움 · 그 밖의 계수는 v4 맞춘 값 그대로) 60번씩 돌리고,
     관찰된 선택(줄을 서서 이용 · 포장)을 고른 비율을 잰다.
  4. 하나씩 빼기 — 한 사례를 빼고 나머지로 가장 잘 맞는 v 를 고른 뒤, 뺀 사례에서 그 v 가 관찰을 얼마나 맞히는지 본다.
     비교: 지금 기본 모델(성향 강도 0 · 포장 가점에만 후기 값) · 후기에서 뽑은 값(성향 강도 1).
     지금 규칙은 객실에서 출발하면 줄도 대기 벌점 없이 객실 시간으로 본다(v3-F). 이 실험에서만 식당 앞 줄을 대기로 센다(스크립트 안에서 점수를 감쌈 · 모델 코드는 그대로).
  5. 같은 줄을 지금 v4.1 규칙(줄 30분 상한 · 예약 대기 · 다음 회차)으로 돌렸을 때 대기 회피 값이 선택을 바꾸는지도 잰다.

한계 (화면 · 문서에 그대로): 사례가 적어 방향까지만 말한다. 고객군 수준의 값이며 한 사람의 성향을 단정하지 않는다.
후기에서 뽑은 성향 값은 같은 후기 문장에서 나왔을 수 있어(대기 언급) 독립 비교가 아니다. 기본 모델에 넣지 않는다.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import math
import random
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
sys.path.insert(0, str(TL))
import agent_v4, fit_v4, capacity as CAP  # noqa: E402

OUT = HERE / "static" / "wait_inv.json"
K = 60
GRID = [round(i / 10, 1) for i in range(11)]

# 후기에서 대기 · 혼잡을 겪거나 피한 체류 (슬기 `후기_대기후행동_저녁후행동_20261007.md` · 근거사슬 7-10). 문장은 요약이고 원문이 아니다
CASES = [
    # 모델의 선택으로 표현할 수 있는 사례 — 관찰된 업장에 줄을 세우고 '줄 · 다른 선택' 을 고르게 한다
    dict(blog="blog06", kind="model", venue="PIZZA_HILL", meal="석식", keys=("pizza_to",), obs="포장",
         seen="피자힐 앞 대기 11팀 · 60~90분 안내", did="같은 업장 포장으로 바꿈", wait=(60, 75, 90), wait_src="후기 숫자 (60~90분 안내)"),
    dict(blog="blog49", kind="model", venue="THE_BUFFET", meal="조식", keys=("buffet_b",), obs="줄 서서 이용",
         seen="더뷔페 조식 2부 시작 전 약 10분 대기", did="같은 더뷔페에서 식사", wait=(5, 10, 15), wait_src="후기 숫자 (약 10분)"),
    dict(blog="blog58", kind="model", venue="THE_BUFFET", meal="중식", keys=("buffet_l",), obs="줄 서서 이용",
         seen="더뷔페 중식 2부 · 회차 시작 전 줄 (예약 입장)", did="같은 더뷔페에서 식사", wait=(10, 20, 30), wait_src="가정 (후기에 분 없음 · 10~30분)", note="퇴실 뒤 중식이라 모델의 체류 범위(퇴실 11:00까지) 밖입니다"),
    dict(blog="blog60", kind="model", venue="PIZZA_HILL", meal="석식", keys=("pizza",), obs="줄 서서 이용",
         seen="예약 없이 피자힐 방문 · 잠깐 대기", did="같은 피자힐에서 식사", wait=(5, 10, 15), wait_src="가정 (후기에 '잠깐' · 5~15분)", note="모델에서 이 손님의 저녁은 거의 다른 곳으로 갑니다"),
    # 모델 밖 — 이유를 적고 실험에는 쓰지 않는다
    dict(blog="blog43", kind="rule", seen="더뷔페 조식 대기가 길어 포기", did="포함된 더글라스 라운지 조식",
         why="객실 상품에 라운지 조식이 포함돼 있으면 모델은 같은 식사 시간대의 다른 식당을 처음부터 후보에서 뺀다. 더뷔페에 줄을 섰다가 포기하는 선택이 생기지 않는다"),
    dict(blog="blog32", kind="inside", seen="클럽라운지 해피아워 음식 줄", did="일행과 나눠 가져와 같은 라운지에서 식사",
         why="업장 안의 음식 줄은 모델에 없다(라운지는 좌석 · 줄을 세지 않음)"),
    dict(blog="blog51", kind="inside", seen="해피아워 한강뷰 좌석 만석 · 초반 음식 줄", did="안쪽 좌석에서 같은 라운지 이용",
         why="업장 안의 좌석 고르기 · 음식 줄은 모델에 없다"),
    dict(blog="blog59", kind="inside", seen="리버파크 세미뷔페 음식 줄에 늦게 합류", did="같은 세미뷔페에서 식사",
         why="업장 안의 음식 줄은 모델에 없다"),
    dict(blog="blog19", kind="plan", seen="혼잡한 조식 2부 대신 1부", did="1부 이용", why="도착 · 기상 시각을 미리 고르는 행동이라 그 순간의 후보 선택이 아니다(모델은 기상 시각 분포로만 둔다)"),
    dict(blog="blog30", kind="plan", seen="2부 혼잡 정보를 보고 1부 오픈", did="1부 이용", why="같은 이유(미리 시각 선택)"),
    dict(blog="blog45", kind="plan", seen="사전 예약과 1부 이용", did="줄 없이 입장", why="예약 · 시각을 미리 고른 행동"),
    dict(blog="blog25", kind="plan", seen="현장 줄은 길었으나 사전 예약", did="바로 안내", why="예약으로 줄을 피한 행동(모델의 '예약한 곳' 가점으로만 들어감)"),
    dict(blog="blog05", kind="plan", seen="조식 2부 개시 전 줄", did="시각을 당겨 피함", why="미리 시각을 고른 행동"),
]
KIND_NAME = {"model": "모델의 선택으로 표현됨", "rule": "규칙으로 정해짐 (포함 식사)", "inside": "업장 안의 줄 (모델에 없음)", "plan": "미리 피함 (시각 · 예약)"}


class LineAt(CAP.Capacity):
    """관찰된 업장 · 식사 시간대에만 정해진 길이의 줄을 세운다. 다른 손님은 없다(좌석 경쟁 없음)"""
    def __init__(self, venue, meal, wait_min):
        super().__init__()
        self.v = {"THE_BUFFET": "더뷔페", "PIZZA_HILL": "피자힐"}[venue]      # 좌석 장부는 업장 이름(L3)으로 센다
        self.meal, self.w = meal, wait_min

    def delay(self, key, start, dwell_min, party, close, hold_end=None):
        venue = self.venue_of(key)
        if venue != self.v or agent_v4.meal_kind_at(start) != self.meal or not self.w:
            return start
        t = start + timedelta(minutes=self.w)
        if close is not None and t + timedelta(minutes=dwell_min) > close:
            return None
        return t

    def busy(self, key, t, party, ratio=0.5):
        return False


# 실험 조건 '줄을 대기로' — 지금 규칙(v3-F)은 객실에서 출발하면 기다림을 대기 벌점 없이 객실에서 보낸 것으로 본다.
#   식당 앞 줄은 객실 시간이 아니므로, 이 실험에서만 관찰된 업장의 줄 길이를 점수에 대기로 더한다(이미 대기로 센 만큼은 빼고).
#   모델 코드는 바꾸지 않고 이 스크립트 안에서만 감싼다
_ORIG_SCORE = agent_v4.score_v4
LINE = {"on": False, "venue": None, "meal": None, "w": 0}


def _score_line(action, persona, travel_min, wait_min, visited, start, meals_done, included_used, last_key, th):
    s, why = _ORIG_SCORE(action, persona, travel_min, wait_min, visited, start, meals_done, included_used, last_key, th)
    if LINE["on"] and LINE["w"] and (action.venue or action.location) == LINE["venue"] and "takeout" not in action.tags \
            and agent_v4.meal_kind_at(start) == LINE["meal"]:
        extra = max(0.0, LINE["w"] - wait_min)
        if extra > 0:
            v = (persona.traits.get("대기 회피") or 0.0) * th["lam_trait"]
            pts = -(th["w_wait"] + v) * extra / 30
            s += pts; why = why + [f"식당 앞 줄 {extra:.0f}분 (실험) {pts:+.2f}"]
    return s, why


agent_v4.score_v4 = _score_line


def load(blog):
    with contextlib.redirect_stdout(io.StringIO()):
        m = importlib.import_module("persona_" + blog)
    return m, m.PERSONA, getattr(m, "START_AT", datetime(2025, 1, 31, 14, 0))


def outcome(segs, traces, c):
    """그 식사 시간대에 무엇을 했나 — 관찰된 선택을 했으면 True. 그 시간대에 관찰된 업장을 아예 안 봤으면 None(정보 없음)"""
    for t in traces:
        k = (t.meta or {}).get("key")
        if k is None or agent_v4.meal_kind_at(t.start) != c["meal"]:
            continue
        if k in c["keys"]:
            return True
        if k in agent_v4.MEAL_KEYS or k == "pizza_to":
            return False
    return False


def rate(c, th, persona, start, wait_min, K=K, line_as_wait=True):
    LINE.update(on=line_as_wait, venue=c["venue"], meal=c["meal"], w=wait_min)
    hit = 0
    for i in range(K):
        cap = LineAt(c["venue"], c["meal"], wait_min)
        segs, tr = agent_v4.run_agent(persona, start, verbose=False, theta=th, rng=random.Random(fit_v4.SEED + i), capacity=cap)
        hit += 1 if outcome(segs, tr, c) else 0
    return hit / K


def run():
    base = dict(agent_v4.THETA_FIT)
    noq = {k: v for k, v in base.items() if k not in ("queue_max", "reserve_wait", "next_window")}
    v41q = dict(base, queue_max=30, reserve_wait=1, next_window=1)
    out_cases = []
    for c in CASES:
        row = {k: c[k] for k in ("blog", "kind", "seen", "did", "note") if k in c}
        row["kind_name"] = KIND_NAME[c["kind"]]
        if c["kind"] != "model":
            row["why"] = c["why"]
            out_cases.append(row); continue
        m, p, start = load(c["blog"])
        pv = p.traits.get("대기 회피")
        only = lambda v: replace(p, traits={k: (v if k == "대기 회피" else None) for k in p.traits})
        row.update(venue=c["venue"], meal=c["meal"], obs=c["obs"], wait=list(c["wait"]), wait_src=c["wait_src"], trait_review=pv)
        row["no_line"] = rate(c, dict(noq), p, start, 0)                         # 줄이 없을 때 지금 기본 모델이 관찰된 선택을 하는 비율
        row["grid"] = {str(w): [rate(c, dict(noq, lam_trait=1.0), only(v), start, w) for v in GRID] for w in c["wait"]}
        row["current"] = {str(w): rate(c, dict(noq), p, start, w) for w in c["wait"]}      # 지금 기본 (성향 강도 0 · 포장 가점에만 후기 값)
        row["v41_rules"] = {str(w): [rate(c, dict(v41q, lam_trait=1.0), only(v), start, w, line_as_wait=False) for v in (0.0, 0.5, 1.0)] for w in c["wait"]}
        out_cases.append(row)
        print(c["blog"], "줄 없음", row["no_line"], {w: row["grid"][w][::5] for w in row["grid"]}, flush=True)

    # 정보가 있는 사례 — 줄이 없어도 모델이 그 식사를 그 업장에서 거의 하지 않으면(5% 미만) 대기 회피 값을 가릴 수 없다
    for r in out_cases:
        if r["kind"] != "model":
            continue
        g = r["grid"][str(r["wait"][1])]
        r["informative"] = max([r["no_line"]] + g) >= 0.05
        p0, p1 = g[0], g[-1]
        se = math.sqrt(p0 * (1 - p0) / K + p1 * (1 - p1) / K) or (1 / K)
        r["effect"] = round(p1 - p0, 3); r["effect_se"] = round(se, 3)
        r["effect_clear"] = abs(p1 - p0) > 2 * se
        r["v41_effect"] = {w: round(x[-1] - x[0], 3) for w, x in r["v41_rules"].items()}
    # 하나씩 빼기 — 정보가 있는 사례만 · 줄 길이는 기준값(가운데)으로. 확률 0 을 피하려고 0.5 / K 를 더한다
    M = [r for r in out_cases if r["kind"] == "model" and r["informative"]]
    eps = 0.5 / K
    ll = lambda r, i, w=None: math.log(r["grid"][str(w or r["wait"][1])][i] + eps)
    def best(rows, w_pick=1):
        sc = [sum(math.log(r["grid"][str(r["wait"][w_pick])][i] + eps) for r in rows) for i in range(len(GRID))]
        top = max(sc)
        return GRID[sc.index(top)], sc
    allv, allsc = best(M)
    loo = []
    for h in M:
        v, _ = best([r for r in M if r is not h])
        mid = str(h["wait"][1])
        i = GRID.index(v)
        pv = h["trait_review"]
        loo.append(dict(blog=h["blog"], v_others=v, p_others=h["grid"][mid][i], p_current=h["current"][mid],
                        p_review=(h["grid"][mid][GRID.index(round(pv, 1))] if pv is not None and round(pv, 1) in GRID else None)))
    # 줄 길이 범위를 바꿔도 같은 결론인지 — 낮음 · 높음 줄로 다시 고른 값
    v_lo, _ = best(M, 0); v_hi, _ = best(M, 2)
    res = dict(
        built=datetime.now().strftime("%Y-%m-%d"), model_ver=__import__("version").model_ver(), k=K, grid=GRID,
        sample=f"후기 대기 관련 체류 {len(CASES)}건 · 모델의 선택으로 표현되는 {sum(1 for r in out_cases if r['kind'] == 'model')}건 · 그중 정보가 있는 {len(M)}건 · 사례마다 {K}번 · 같은 난수 줄 · 다른 손님 없음",
        n_model=sum(1 for r in out_cases if r["kind"] == "model"), n_info=len(M), n_clear=sum(1 for r in M if r["effect_clear"]),
        verdict=None,
        cases=out_cases, v_all=allv, v_all_wait_lo=v_lo, v_all_wait_hi=v_hi, score_all=[round(x, 3) for x in allsc], loo=loo,
        caveat="제한된 사례에서 '줄 앞에서 대기 회피가 선택을 바꾼다' 는 조건부 가설이 지금 모델보다 추가 설명력을 갖는지 탐색한 결과입니다. 개인의 실제 성향을 알아낸 것이 아니며, 사례가 적어 방향까지만 봅니다. 후기에서 뽑은 대기 회피 값은 같은 후기의 대기 언급에서 나왔을 수 있어 독립 비교가 아닙니다. 기본 모델에 넣지 않습니다.",
        doc="근거사슬 7-20",
    )
    # 판정 — 다른 사례로 고른 값이 뺀 사례를 지금 기본 모델보다 잘 맞혀야(모든 사례에서) '옮겨 쓸 수 있는 고객군 값' 으로 본다
    res["loo_better"] = sum(1 for x in loo if x["p_others"] > x["p_current"])
    res["verdict"] = "조건부 대기 회피 가설의 추가 설명력 · 탐색에서 보임" if loo and res["loo_better"] == len(loo) else "조건부 대기 회피 가설의 추가 설명력 · 확인되지 않음"
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v_all", allv, "lo/hi", v_lo, v_hi, "loo", loo)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    run()
