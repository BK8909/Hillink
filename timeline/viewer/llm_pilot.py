"""LLM 선택 파일럿 (10/16 · 실험) — 같은 손님 · 같은 후보 · 같은 운영 규칙에서 '누가 고르나' 만 바꿔 비교한다.

  python3 llm_pilot.py ping                      # 모델 목록에서 gpt-6-luna 가 있는지 확인
  python3 llm_pilot.py cases --n 16              # 첫 실험 · 후기가 그 식사에 실제로 간 곳을 아는 결정 16개를 뽑는다 (API 없음)
  python3 llm_pilot.py cases-run                 # 그 결정마다 Decisions API(후보별 확률) + Responses API(선택 이유 · reasoning low) → static/llm_cases.json
  python3 llm_pilot.py dry  --stays 5            # 체류 단위 실행에 필요한 호출 수 · 예시 프롬프트 (API 없음)
  python3 llm_pilot.py run  --stays 5 --k 1      # 체류 단위 소규모 실행 (B 는 Decisions 확률로 고름)
  python3 llm_pilot.py run  --k 3                # 후기 59 체류 · 세 방식 비교 → static/llm_pilot.json

API 쓰임새 (10/16 정함)
  · 행동 선택 · 확률 평가 = Decisions API (POST /v1/decisions · choice 질문 · 후보마다 확률). 엔진의 확률 선택 자리에 이 확률을 넣는다
  · 자연어 판단 · 선택 이유 = Responses API (reasoning effort low 부터). 결정 사례에만 쓰고 시뮬레이션 선택에는 쓰지 않는다
  · LLM 은 행동 선택만. 좌석 · 회차 · 예약 처리는 기존 엔진(v4.1 규칙)이 한다

세 방식 (같은 손님 · 같은 시작 시각 · 같은 난수 줄 · 같은 좌석 · 회차 · 운영 규칙)
  A 규칙   지금 v4 맞춘 계수의 점수 · 확률 선택 그대로
  B LLM    결정마다 엔진이 만든 '갈 수 있는 후보' 목록에서 LLM 이 하나를 고른다(체크인 절차는 규칙 그대로)
  C 혼합   평소에는 규칙, 자리가 없어 빠진 후보가 있거나 대기가 10분 이상인 후보가 있는 결정만 LLM

공정하게 하려고 지키는 것
  · LLM 은 후보 밖 행동을 만들 수 없다. 좌석 · 회차 · 운영 시간 · 포함 식사 규칙은 엔진이 먼저 걸러 낸다
  · LLM 에게는 구조화된 손님 정보(인원 · 아이 · 목적 · 박수 · 객실 상품의 포함 식사 · 예약)와 후보의 사실(장소 · 시각 · 이동 · 대기 · 규칙상 성격)만 준다.
    후기 원문 · 정답(후기가 간 곳) · 모델 점수는 주지 않는다(정답이 섞이면 비교가 무의미해진다). 성향 값도 주지 않는다(성향 실험과 섞지 않음)
  · 평가는 후기 59 체류에서 행동 역추적과 같은 재현 · 정밀 · Brier. 실행 수가 같아야 Brier 를 비교할 수 있어 세 방식 모두 같은 k 로 센다
  · 응답은 프롬프트 해시로 저장해(cache/llm_pilot_calls.jsonl) 다시 돌리면 같은 답을 쓴다. 토큰 사용량을 함께 남긴다

키는 저장소에 두지 않는다. 환경변수 OPENAI_API_KEY 또는 ~/.secrets/openai_key 에서 읽는다. 모델은 OPENAI_MODEL (기본 gpt-6-luna)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parent
sys.path.insert(0, str(TL)); sys.path.insert(0, str(HERE))
import agent_v4, fit_v4  # noqa: E402
from match import BASELINE_PLACES, TRANSIT, visits_from_segments  # noqa: E402

MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
CALLS = HERE / "cache" / "llm_pilot_calls.jsonl"
OUT = HERE / "static" / "llm_pilot.json"
LOC, PROP = {}, {}
try:
    import engine  # noqa: E402
    LOC, PROP = engine.LOC_NAMES, engine.PROP_NAMES
except Exception:
    pass


def api_key():
    k = os.environ.get("OPENAI_API_KEY")
    if not k:
        f = Path.home() / ".secrets" / "openai_key"
        k = f.read_text().strip() if f.exists() else None
    if not k:
        raise SystemExit("OPENAI_API_KEY 가 없습니다")
    return k


# ---------------------------------------------------------------------------
# 프롬프트 — 손님 · 지금 상황 · 후보의 사실만
# ---------------------------------------------------------------------------
_NUM = re.compile(r"\s*[+−-]\d+(\.\d+)?$")
_SKIP = ("대기 ", "이동 ", "대기(성향)", "격식", "캐주얼", "조망", "조용함", "붐빔", "함께 먹기", "이미 가 봄", "처음")


def facts(why):
    out = []
    for w in why:
        w = _NUM.sub("", str(w)).strip()
        if not w or w.startswith(_SKIP):
            continue
        out.append(w)
    return out


def persona_text(p):
    kids = "있음" if getattr(p, "has_child_under_13", False) else "없음"
    inc = ", ".join(f"{k} {LOC.get(v, v)}" for k, v in (p.included_meals or ())) or "없음"
    bk = ", ".join(LOC.get(b, b) for b in (p.booked or ())) or "없음"
    pf = ", ".join(LOC.get(b, b) for b in (p.prefers or ())) or "없음"
    stay = f"투숙 {p.nights}박 ({PROP.get(p.property, p.property)})" if p.is_guest else "비투숙 당일 방문"
    return (f"- 일행 {p.party_size}명 · 13세 미만 아이 {kids}\n- {stay}\n- 방문 목적: {p.purpose or '알 수 없음'}\n"
            f"- 객실 상품에 포함된 식사: {inc}\n- 방문 전에 예약한 곳: {bk}\n- 가고 싶던 식당: {pf}")


def now_of(cands):
    """결정 시각 — 후보마다 (시작 − 대기 − 이동) 중 가장 이른 것"""
    from datetime import timedelta
    return min((c[6][0].t_in if c[6] else c[2].t_in) - timedelta(minutes=max(0, c[4]) + c[3]) for c in cands)


def prompt(p, now, here, history, cands):
    lines = [f"{i}. {cand_desc(c, now)}" for i, c in enumerate(cands)]
    hist = " → ".join(history[-8:]) or "아직 없음"
    return ("워커힐 호텔을 찾은 손님 일행입니다.\n" + persona_text(p) +
            f"\n\n지금: {now:%m/%d %H:%M} · 위치 {LOC.get(here, here)}\n지금까지 한 일: {hist}\n\n"
            "지금 할 수 있는 행동 후보입니다(운영 시간 · 좌석 · 예약 규칙을 이미 통과한 것만):\n" + "\n".join(lines))


ASK_PICK = '\n\n이 일행이라면 지금 무엇을 하겠습니까? 후보 번호 하나와 한 문장 이유를 고르세요.'


SYSTEM = "당신은 호텔 손님의 다음 행동을 고르는 역할입니다. 주어진 후보 밖의 행동은 고를 수 없습니다. 손님 정보에 없는 사실을 지어내지 마세요."


# ---------------------------------------------------------------------------
# LLM 호출 (응답 저장 · 재사용)
# ---------------------------------------------------------------------------
_CACHE = None
USAGE = Counter()


def _cache():
    global _CACHE
    if _CACHE is None:
        _CACHE = {}
        if CALLS.exists():
            for line in CALLS.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line); _CACHE[r["h"]] = r
                except Exception:
                    pass
    return _CACHE


def _post(path, body, timeout=90):
    import requests
    last = None
    for attempt in range(4):
        try:
            r = requests.post("https://api.openai.com/v1/" + path, json=body, timeout=timeout,
                              headers={"Authorization": f"Bearer {api_key()}"})
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 + 3 * attempt); last = f"{r.status_code} {r.text[:150]}"; continue
            if not r.ok:
                raise RuntimeError(f"{r.status_code} {r.text[:300]}")
            return r.json()
        except Exception as e:
            last = str(e)[:300]; USAGE["errors"] += 1
            if "401" in last or "400" in last or "404" in last:
                break
    raise RuntimeError(last)


_LOCK = threading.Lock()


def _remember(h, rec):
    rec["h"] = h; rec["t"] = datetime.now().isoformat(timespec="seconds")
    CALLS.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with CALLS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _cache()[h] = rec


def free_meal(p, now, population):
    """자유 식사 결정 — 식사가 30분 안에 시작할 수 있고, 그 끼니가 포함 식사 · 예약으로 정해지지 않은 결정 (결정 사례와 같은 기준)"""
    meals = [c for c in population if c[1].key in agent_v4.MEAL_KEYS or c[1].key == "pizza_to"]
    if not meals or min((c[2].t_in - now).total_seconds() / 60 for c in meals) > 30:
        return False
    kind = agent_v4.meal_kind_at(min(c[2].t_in for c in meals))
    if kind is None:
        return False
    fixed = {pl for (k2, pl) in (p.included_meals or ()) if k2 == kind} | set(p.booked or ())
    return not any(c[1].location in fixed or (c[1].venue or "") in fixed for c in meals)


def cand_desc(c, now=None):
    """후보의 사실 — 장소 · 시작 ~ 끝 · 이동 · 시작까지 남은 시간 · 규칙상 성격(점수 숫자는 뺌).
    '대기' 라고 쓰지 않는다: 혼자 돌릴 때 기다림은 대부분 운영 시작 전 객실 등에서 보내는 시간이다"""
    pts, a, seg, travel, wait, why, pre = c
    t0 = pre[0].t_in if pre else seg.t_in
    f = facts(why)
    lead = "" if now is None else f" · 지금부터 {max(0, int((t0 - now).total_seconds() // 60))}분 뒤 시작"
    return f"{a.label} · {LOC.get(a.location, a.location)} · {t0:%H:%M}~{seg.t_out:%H:%M} · 이동 {travel:.0f}분{lead}" + (f" · {' / '.join(f)}" if f else "")


def decide(text, cands):
    """Decisions API · choice 질문 하나 — 후보마다 확률을 돌려준다(후보 순서). 같은 입력은 저장된 답을 쓴다. 실패하면 None"""
    descs = [cand_desc(c, now_of(cands)) for c in cands]
    h = hashlib.sha1(("decide|" + MODEL + "|" + text).encode("utf-8")).hexdigest()
    c = _cache()
    if h in c:
        USAGE["cached"] += 1; return c[h]["probs"]
    body = {"model": MODEL, "input": text,
            "questions": [{"name": "next_action", "type": "choice",
                           "instructions": "이 손님 일행이 지금 고를 다음 행동은 어느 후보인가요? 후보 밖 행동은 없습니다.",
                           "choices": [{"value": str(i), "description": d[:300]} for i, d in enumerate(descs)]}]}
    try:
        d = _post("decisions", body)
    except Exception as e:
        USAGE["fallback"] += 1; print("  Decisions 실패 → 규칙:", str(e)[:200], flush=True); return None
    ans = (d.get("answers") or [{}])[0]
    if ans.get("type") != "choice":
        USAGE["refusal"] += 1; return None
    pm = {str(x.get("value")): float(x.get("probability", 0)) for x in ans.get("probabilities", [])}
    probs = [pm.get(str(i), 0.0) for i in range(len(cands))]
    tot = sum(probs) or 1.0
    probs = [x / tot for x in probs]
    u = d.get("usage") or {}
    USAGE["decisions"] += 1; USAGE["in"] += u.get("input_tokens", 0); USAGE["out"] += u.get("output_tokens", 0)
    _remember(h, dict(api="decisions", probs=probs, choice=ans.get("choice"), confidence=ans.get("confidence"), model=d.get("model", MODEL), usage=u))
    return probs


def respond(text, effort="low"):
    """Responses API — 고른 번호와 한 문장 이유 (reasoning effort low). 결정 사례에만 쓴다"""
    h = hashlib.sha1((f"respond|{effort}|" + MODEL + "|" + text).encode("utf-8")).hexdigest()
    c = _cache()
    if h in c:
        USAGE["cached"] += 1; return c[h]
    body = {"model": MODEL, "reasoning": {"effort": effort}, "instructions": SYSTEM, "input": text,
            "text": {"format": {"type": "json_schema", "name": "pick", "strict": True,
                                "schema": {"type": "object", "additionalProperties": False, "required": ["choice", "reason"],
                                           "properties": {"choice": {"type": "integer"}, "reason": {"type": "string"}}}}}}
    try:
        d = _post("responses", body)
    except Exception as e:
        USAGE["fallback"] += 1; print("  Responses 실패:", str(e)[:200], flush=True); return None
    txt = d.get("output_text") or "".join(p.get("text", "") for o in d.get("output", []) if o.get("type") == "message" for p in o.get("content", []))
    try:
        j = json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt or "", re.S); j = json.loads(m.group(0)) if m else {}
    u = d.get("usage") or {}
    USAGE["responses"] += 1; USAGE["in"] += u.get("input_tokens", 0); USAGE["out"] += u.get("output_tokens", 0)
    rec = dict(api="responses", effort=effort, choice=j.get("choice"), reason=str(j.get("reason", ""))[:300], model=d.get("model", MODEL), usage=u)
    _remember(h, rec)
    return rec


# ---------------------------------------------------------------------------
# 고르는 자리 — run_agent 의 확률 선택(rng.choices)을 가로챈다. 모델 코드는 그대로
# ---------------------------------------------------------------------------
class Chooser(random.Random):
    """run_agent 의 rng 자리에 넣는다. 엔진이 후보를 다 만든 뒤 확률 선택(rng.choices)을 부르는 순간만 가로챈다.
    arm: A 규칙(그대로) · B LLM(모든 결정을 Decisions 확률로 고름) · C 혼합(자유 식사 결정만 LLM, 나머지 규칙) ·
         W 혼합(대기 10분 이상 후보가 있는 결정만 LLM · 처음 설계) ·
         dry / dryC (규칙으로 고르되 B · C 였다면 몇 번 불렀을지 센다) · collect (결정 사례를 모은다)"""
    def __init__(self, seed, arm, persona, rep=0, tau=0.5):
        super().__init__(seed)
        self.arm, self.p, self.rep, self.tau = arm, persona, rep, tau
        self.history, self.n_dec, self.n_llm, self.example, self.here = [], 0, 0, None, "HOTEL_GATE"
        self.log = []          # collect: (지금, 위치, 지금까지, 후보, 규칙 확률)

    def rule_probs(self, population):
        top = max(c[0] for c in population)
        w = [pow(2.718281828, (c[0] - top) / self.tau) for c in population]
        t = sum(w); return [x / t for x in w]

    def choices(self, population, weights=None, *, cum_weights=None, k=1):
        is_cand = bool(population) and isinstance(population[0], tuple) and len(population[0]) == 7 and hasattr(population[0][1], "key")
        if not is_cand:
            return super().choices(population, weights=weights, cum_weights=cum_weights, k=k)
        self.n_dec += 1
        now = now_of(population)
        if self.arm == "collect":
            self.log.append(dict(now=now, here=self.here, history=list(self.history), cands=list(population), rule=self.rule_probs(population)))
        use = (self.arm in ("B", "dry") or (self.arm in ("C", "dryC") and free_meal(self.p, now, population))
               or (self.arm == "W" and any(c[4] >= 10 for c in population)))
        pick = None
        if use:
            self.n_llm += 1
            text = prompt(self.p, now, self.here, self.history, population)
            if self.example is None: self.example = text
            if self.arm in ("B", "C", "W"):
                pr = decide(text, population)
                if pr is not None:
                    pick = super().choices(population, weights=pr, k=1)      # 같은 난수 줄로 LLM 확률에 따라 고른다
        if pick is None:
            pick = super().choices(population, weights=weights, cum_weights=cum_weights, k=k)
        self._note(pick[0]); return pick

    def _note(self, c):
        self.history.append(f"{c[2].t_in:%H:%M} {c[1].label}")
        self.here = c[1].location


def run_stay(m, arm, k, seed_base=fit_v4.SEED):
    p = m.PERSONA
    start = getattr(m, "START_AT", datetime(2025, 1, 31, 14, 0))
    reach = agent_v4.reachable(p)
    seen = Counter(); R = P = 0.0; dec = llm = 0; ex = None
    for i in range(k):
        rng = Chooser(seed_base + i, arm, p, rep=i)
        segs, _ = agent_v4.run_agent(p, start, verbose=False, theta=dict(agent_v4.THETA_FIT), rng=rng)
        r = fit_v4.evaluate(segs, m, reachable=reach); R += r.recall; P += r.precision
        for pl in {v.place for v in visits_from_segments(segs)}:
            seen[pl] += 1
        dec += rng.n_dec; llm += rng.n_llm; ex = ex or rng.example
    places = [x for x in reach | set(seen) if x not in BASELINE_PLACES and x not in TRANSIT and x not in getattr(m, "TRUTH_PASSED", {})]
    truth = set(m.TRUTH_VISITED)
    brier = sum(((1.0 if x in truth else 0.0) - seen[x] / k) ** 2 for x in places) / max(1, len(places))
    return dict(recall=R / k, precision=P / k, brier=brier, prob={x: round(seen[x] / k, 3) for x in places}, decisions=dec, llm_calls=llm), ex


# ---------------------------------------------------------------------------
# 첫 실험 · 결정 사례 12~20개 — 후기가 그 식사 시간대에 실제로 간 곳(TRUTH_MEALS)을 아는 식사 결정만
# ---------------------------------------------------------------------------
CASES = HERE / "cache" / "llm_cases_input.json"
CASES_OUT = HERE / "static" / "llm_cases.json"
# 10/16 2차 · '어느 식당' 만 비교 — 1차는 '식당에 간 결정' 만 골라서 '식당에 가느냐' 까지 섞였다 (식당 후보 균등만으로도 둘 다 이김)
CASES_P = HERE / "cache" / "llm_cases_place_input.json"
CASES_P_OUT = HERE / "static" / "llm_cases_place.json"
NOT_REST = ("meal_other", "meal_out")


def rest_idx(keys):
    """후보 중 '식당 식사' (식당 외 식사 · 객실 · 시설 제외)"""
    return [i for i, k in enumerate(keys) if k in agent_v4.MEAL_KEYS and k not in NOT_REST]


def _clean(t):
    """결과 파일에는 동행 · 아동 언급을 남기지 않는다 (LLM 입력에는 범주 '아이 동반 있음' 만 들어감)"""
    if t is None:
        return None
    import re
    t = re.sub(r"\s*/\s*아동 동반", "", t).replace(" · 아동 동반", "")
    return None if re.search(r"아동|아이|동반|자녀|가족", t) else t


def build_cases(n=16, mode="meal"):
    """규칙 엔진으로 후기 체류를 한 번씩 돌려, 식사 시간대 결정 중 (1) 후보가 3개 이상이고 (2) 후기가 그 식사에 간 곳이 후보에 있고
    (3) 후보 중 그곳이 아닌 것도 있고 (4) 식사 후보가 30분 안에 시작할 수 있는(식사를 고르는 순간) 결정을 체류마다 하나씩 모은다. 규칙 확률은 엔진과 같은 식(점수 차 ÷ τ 0.5 의 지수 비례)"""
    rows = []
    for g, lab, m in fit_v4.stays():
        tm = getattr(m, "TRUTH_MEALS", None) or []
        if not tm:
            continue
        p = m.PERSONA
        start = getattr(m, "START_AT", datetime(2025, 1, 31, 14, 0))
        rng = Chooser(fit_v4.SEED, "collect", p)
        agent_v4.run_agent(p, start, verbose=False, theta=dict(agent_v4.THETA_FIT), rng=rng)
        for d in rng.log:
            meals = [c for c in d["cands"] if c[1].key in agent_v4.MEAL_KEYS or c[1].key == "pizza_to"]
            kind = agent_v4.meal_kind_at(min(c[2].t_in for c in meals)) if meals else None
            if kind is None or len(d["cands"]) < 3:
                continue
            if min((c[2].t_in - d["now"]).total_seconds() / 60 for c in meals) > 30:      # 식사가 30분 안에 시작할 수 있는 '식사 결정' 순간만
                continue
            seen_places = {pl for (k2, pl, *_rest) in tm if k2 == kind}
            hit = [i for i, c in enumerate(d["cands"]) if c[1].location in seen_places or (c[1].venue or "") in seen_places]
            if not hit or len(hit) == len(d["cands"]):
                continue
            if mode == "place":                              # 식당이 둘 이상(장소 기준)이고 관찰한 곳이 그 식당 중 하나
                ri = rest_idx([c[1].key for c in d["cands"]])
                venues = {(d["cands"][i][1].venue or d["cands"][i][1].location) for i in ri}
                if len(venues) < 2 or not set(hit) & set(ri) or any((r0["stay"], r0["kind"]) == (lab, kind) for r0 in rows):
                    continue
            text = prompt(p, d["now"], d["here"], d["history"], d["cands"])
            d["cands_desc"] = [cand_desc(c, d["now"]) for c in d["cands"]]
            fixed = {pl for (k2, pl) in (p.included_meals or ()) if k2 == kind} | set(p.booked or ())
            rows.append(dict(stay=lab, purpose=p.purpose, kind=kind, free=not (seen_places & fixed), now=d["now"].isoformat(timespec="minutes"), text=text,
                             cands=d["cands_desc"], keys=[c[1].key for c in d["cands"]], observed=hit,
                             observed_places=sorted(seen_places), rule=d["rule"], n_cands=len(d["cands"]), rest=rest_idx([c[1].key for c in d["cands"]])))
            if mode != "place":
                break                                    # 체류마다 하나 (한 손님이 결과를 좌우하지 않게)
    # 고르는 기준은 결정의 종류뿐(규칙 확률 · 결과를 보고 고르지 않는다): 포함 식사 · 예약으로 정해지지 않은 '자유 선택' 결정을 먼저,
    # 식사 시간대가 고르게 섞이게 차례로 돌며 n 개. 같은 입력으로 다시 뽑으면 같은 사례
    import itertools
    pick = []
    if mode == "place":                                  # 체류 · 끼니마다 하나, 체류마다 최대 2 · 중식 · 석식 먼저
        per = Counter()
        for r in sorted(rows, key=lambda r: (not r["free"], r["kind"] == "조식", r["stay"])):
            if per[r["stay"]] < 2 and len(pick) < n:
                pick.append(r); per[r["stay"]] += 1
        rows_out = CASES_P
    else:
        rows_out = CASES
    for free in ((True, False) if mode != "place" else ()):
        by = {}
        for r in sorted((r for r in rows if r["free"] == free), key=lambda r: r["stay"]):
            by.setdefault(r["kind"], []).append(r)
        for grp in itertools.zip_longest(*[by[k] for k in sorted(by)]):
            for r in grp:
                if r is not None and len(pick) < n:
                    pick.append(r)
    rows_out.parent.mkdir(parents=True, exist_ok=True)
    rows_out.write_text(json.dumps(dict(built=datetime.now().isoformat(timespec="seconds"), model_ver=__import__("version").model_ver(),
                                     n_found=len(rows), cases=pick), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"후보 결정 {len(rows)}개 중 {len(pick)}개 → {rows_out}")
    for r in pick:
        print(f"  {r['stay']:<12} {r['kind']} {'자유' if r['free'] else '정해짐'} 후보 {r['n_cands']} · 관찰 {r['observed_places']} · 규칙 확률(관찰) {sum(r['rule'][i] for i in r['observed']):.2f}")
    print("\n--- 예시 입력 ---\n" + pick[0]["text"] if pick else "")


def run_cases(effort="low", mode="meal"):
    import math
    C = json.loads((CASES_P if mode == "place" else CASES).read_text(encoding="utf-8"))["cases"]
    out = []
    for r in C:
        fake = [None] * r["n_cands"]
        # decide() 는 후보 설명이 필요하다 — 저장한 설명으로 질문을 만든다
        probs = _decide_desc(r["text"], r["cands"])
        resp = respond(r["text"] + ASK_PICK, effort=effort)
        po_rule = sum(r["rule"][i] for i in r["observed"])
        po_llm = None if probs is None else sum(probs[i] for i in r["observed"])
        ri = r.get("rest") or rest_idx(r["keys"])
        oi = [i for i in r["observed"] if i in ri]
        cond = lambda pr: (sum(pr[i] for i in oi) / max(1e-9, sum(pr[i] for i in ri))) if (pr and len(ri) >= 2 and oi) else None
        row = dict(stay=r["stay"], kind=r["kind"], purpose=r["purpose"], n_cands=r["n_cands"], cands=[_clean(c) or c.split(" · ")[0] for c in r["cands"]], observed=r["observed"],
                   rest=ri, p_rest_rule=round(sum(r["rule"][i] for i in ri), 4), p_rest_llm=None if probs is None else round(sum(probs[i] for i in ri), 4),
                   pc_rule=None if cond(r["rule"]) is None else round(cond(r["rule"]), 4), pc_llm=None if cond(probs) is None else round(cond(probs), 4),
                   pc_unif=round(len(oi) / len(ri), 4) if (len(ri) >= 2 and oi) else None,
                   rule=[round(x, 4) for x in r["rule"]], llm=None if probs is None else [round(x, 4) for x in probs],
                   p_obs_rule=round(po_rule, 4), p_obs_llm=None if po_llm is None else round(po_llm, 4),
                   top_rule=max(range(r["n_cands"]), key=lambda i: r["rule"][i]),
                   top_llm=None if probs is None else max(range(r["n_cands"]), key=lambda i: probs[i]),
                   resp_choice=(resp or {}).get("choice"), resp_reason=_clean((resp or {}).get("reason")))
        out.append(row)
        print(r["stay"], r["kind"], "관찰 확률 규칙", round(po_rule, 2), "LLM", None if po_llm is None else round(po_llm, 2), "| 이유:", (row["resp_reason"] or "")[:60], flush=True)
    ok = [x for x in out if x["p_obs_llm"] is not None]
    lg = lambda v: math.log(max(v, 1e-3))
    agg = dict(n=len(out), n_ok=len(ok),
               mean_p_obs_rule=round(sum(x["p_obs_rule"] for x in ok) / max(1, len(ok)), 3),
               mean_p_obs_llm=round(sum(x["p_obs_llm"] for x in ok) / max(1, len(ok)), 3),
               logscore_rule=round(sum(lg(x["p_obs_rule"]) for x in ok) / max(1, len(ok)), 3),
               logscore_llm=round(sum(lg(x["p_obs_llm"]) for x in ok) / max(1, len(ok)), 3),
               top1_rule=sum(1 for x in ok if x["top_rule"] in x["observed"]), top1_llm=sum(1 for x in ok if x["top_llm"] in x["observed"]),
               llm_better=sum(1 for x in ok if x["p_obs_llm"] > x["p_obs_rule"] + 0.05), llm_worse=sum(1 for x in ok if x["p_obs_llm"] < x["p_obs_rule"] - 0.05),
               resp_agrees_top_llm=sum(1 for x in ok if x["resp_choice"] == x["top_llm"]),
               resp_top1=sum(1 for x in ok if x["resp_choice"] in x["observed"]),
               # 기준선 · 후보 전부 균등 / 식당 후보만 균등 (관찰이 식당인 사례만 골랐으므로 '식당에 간다' 는 사례 고르기에서 이미 정해짐)
               logscore_uniform=round(sum(math.log(len(x["observed"]) / x["n_cands"]) for x in ok) / max(1, len(ok)), 3),
               logscore_rest_uniform=round(sum(lg(len([i for i in x["observed"] if i in x["rest"]]) / max(1, len(x["rest"]))) for x in ok) / max(1, len(ok)), 3),
               mean_p_rest_rule=round(sum(x["p_rest_rule"] for x in ok) / max(1, len(ok)), 3),
               mean_p_rest_llm=round(sum(x["p_rest_llm"] for x in ok) / max(1, len(ok)), 3))
    cc = [x for x in ok if x["pc_rule"] is not None and x["pc_llm"] is not None]
    agg.update(n_place=len(cc),
               place_logscore_rule=round(sum(lg(x["pc_rule"]) for x in cc) / max(1, len(cc)), 3),
               place_logscore_llm=round(sum(lg(x["pc_llm"]) for x in cc) / max(1, len(cc)), 3),
               place_logscore_uniform=round(sum(lg(x["pc_unif"]) for x in cc) / max(1, len(cc)), 3),
               place_mean_rule=round(sum(x["pc_rule"] for x in cc) / max(1, len(cc)), 3),
               place_mean_llm=round(sum(x["pc_llm"] for x in cc) / max(1, len(cc)), 3),
               place_mean_uniform=round(sum(x["pc_unif"] for x in cc) / max(1, len(cc)), 3),
               place_llm_better=sum(1 for x in cc if x["pc_llm"] > x["pc_rule"] + 0.05), place_llm_worse=sum(1 for x in cc if x["pc_llm"] < x["pc_rule"] - 0.05))
    res = dict(built=datetime.now().strftime("%Y-%m-%d %H:%M"), model=MODEL, effort=effort, model_ver=__import__("version").model_ver(),
               usage=dict(USAGE), agg=agg, cases=out,
               method="후기 체류에서 규칙 엔진이 만든 식사 시간대 결정 중, 후기가 그 식사에 실제로 간 곳이 후보에 있는 결정을 체류마다 하나씩 골랐다. 같은 후보 목록을 규칙 확률(엔진의 점수 · τ 0.5)과 Decisions API 확률(gpt-6-luna)로 매기고, 후기에 실제로 간 곳에 준 확률을 비교한다. Responses API(reasoning low)로 고른 번호와 이유를 따로 받는다.",
               caveat="첫 파일럿 · 결정 사례 수가 적다. LLM 에게 후기 원문 · 정답 · 모델 점수를 주지 않았다. 이유 문장은 모델이 생성한 설명이며 실제 판단 근거와 같다는 보장이 없다. 그럴듯한 설명이 실제 행동을 더 잘 예측한다는 뜻이 아니다.")
    res["mode"] = mode
    (CASES_P_OUT if mode == "place" else CASES_OUT).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(agg, ensure_ascii=False), dict(USAGE))


def _decide_desc(text, descs):
    """decide() 와 같은 Decisions 호출 · 후보 설명을 직접 받는다 (결정 사례용)"""
    class _C(tuple):
        pass
    h = hashlib.sha1(("decide|" + MODEL + "|" + text).encode("utf-8")).hexdigest()
    c = _cache()
    if h in c:
        USAGE["cached"] += 1; return c[h]["probs"]
    body = {"model": MODEL, "input": text,
            "questions": [{"name": "next_action", "type": "choice",
                           "instructions": "이 손님 일행이 지금 고를 다음 행동은 어느 후보인가요? 후보 밖 행동은 없습니다.",
                           "choices": [{"value": str(i), "description": d[:300]} for i, d in enumerate(descs)]}]}
    try:
        d = _post("decisions", body)
    except Exception as e:
        USAGE["fallback"] += 1; print("  Decisions 실패:", str(e)[:200], flush=True); return None
    ans = (d.get("answers") or [{}])[0]
    if ans.get("type") != "choice":
        USAGE["refusal"] += 1; return None
    pm = {str(x.get("value")): float(x.get("probability", 0)) for x in ans.get("probabilities", [])}
    probs = [pm.get(str(i), 0.0) for i in range(len(descs))]
    tot = sum(probs) or 1.0; probs = [x / tot for x in probs]
    u = d.get("usage") or {}
    USAGE["decisions"] += 1; USAGE["in"] += u.get("input_tokens", 0); USAGE["out"] += u.get("output_tokens", 0)
    _remember(h, dict(api="decisions", probs=probs, choice=ans.get("choice"), confidence=ans.get("confidence"), model=d.get("model", MODEL), usage=u))
    return probs


# ---------------------------------------------------------------------------
# 10/16 리뷰 ③ · '가지 않은 곳' 과 '후기에 적히지 않은 곳' 을 나눠 다시 매긴다 (API 호출 없음 · llm_pilot.json 의 확률만 씀)
#   TRUTH_NOT_VISITED 의 등급: ◎ 명시 미방문 · ○ 간접 · '언급 없음' (대부분). 지금 Brier 는 장소 후보 전부를 쓰고, 목록에 없는 곳도 0 으로 센다
# ---------------------------------------------------------------------------
def _tier(v):
    v = str(v)
    return 1 if v.startswith("◎") else 3 if "언급 없음" in v else 2


def gold_tiers():
    import math
    d = json.loads(OUT.read_text(encoding="utf-8"))
    S = {lab: m for g, lab, m in fit_v4.stays()}
    arms = [a for a in ("A", "A2", "B", "C") if a in d["agg"]]
    cnt = Counter(_tier(v) for m in S.values() for v in (getattr(m, "TRUTH_NOT_VISITED", {}) or {}).values())

    def brier(maxtier):
        out = {a: [] for a in arms}
        for x in d["stays"]:
            m = S[x["stay"]]; T = set(m.TRUTH_VISITED); NV = {k: _tier(v) for k, v in (getattr(m, "TRUTH_NOT_VISITED", {}) or {}).items()}
            for a in arms:
                e = [((1 - p) ** 2 if pl in T else p ** 2) for pl, p in x["res"][a]["prob"].items()
                     if pl in T or maxtier is None or (pl in NV and NV[pl] <= maxtier)]
                out[a].append(sum(e) / len(e) if e else None)
        row = {}
        for a in arms:
            v = [z for z in out[a] if z is not None]; r = dict(brier=round(sum(v) / len(v), 4))
            if a != "A":
                dd = [out[a][i] - out["A"][i] for i in range(len(out["A"])) if out[a][i] is not None and out["A"][i] is not None]
                mu = sum(dd) / len(dd); se = (sum((z - mu) ** 2 for z in dd) / (len(dd) - 1) / len(dd)) ** 0.5
                r.update(d=round(mu, 4), se=round(se, 4), better=sum(1 for z in dd if z < -0.005), worse=sum(1 for z in dd if z > 0.005))
            row[a] = r
        return row

    def auc(a, t):
        win = n = 0.0
        for x in d["stays"]:
            m = S[x["stay"]]; T = set(m.TRUTH_VISITED); NV = {k: _tier(v) for k, v in (getattr(m, "TRUTH_NOT_VISITED", {}) or {}).items()}
            P = x["res"][a]["prob"]; pos = [P[p] for p in P if p in T]; neg = [P[p] for p in P if p not in T and NV.get(p) == t]
            for u in pos:
                for w in neg:
                    n += 1; win += 1.0 if u > w else 0.5 if u == w else 0.0
        return (round(win / n, 3), int(n)) if n else (None, 0)

    d["gold_tiers"] = dict(
        counts={"명시 미방문 (◎)": cnt[1], "간접 (○)": cnt[2], "언급 없음": cnt[3]},
        brier={"전체 (적히지 않은 곳도 미방문)": brier(None), "언급 없음 제외 (간 곳 + ◎ · ○)": brier(2), "명시 미방문만 (간 곳 + ◎)": brier(1)},
        auc={lab: {a: auc(a, t) for a in arms} for lab, t in (("명시 미방문 (◎)", 1), ("간접 (○)", 2), ("언급 없음", 3))},
        note="Brier 를 '간 곳 + 명시 미방문' 으로만 매기면 미방문 칸이 적어(◎ 46개) 확률을 넓게 퍼뜨린 쪽이 유리하고, 적히지 않은 곳까지 미방문으로 매기면 퍼뜨린 쪽이 불리하다. 순위 판별(AUC)은 전체 확률 수준과 무관하게 '간 곳에 안 간 곳보다 높은 확률을 줬는가' 만 본다.")
    # 1 · 2 단계 결정 사례 요약 (사례별 정답 위치는 저장소 밖 파일에만)
    for f, key in ((CASES_OUT, "stage1"), (CASES_P_OUT, "stage2")):
        if f.exists():
            a = json.loads(f.read_text(encoding="utf-8"))["agg"]
            d[key] = {k: a[k] for k in a if k in ("n", "mean_p_obs_rule", "mean_p_obs_llm", "logscore_rule", "logscore_llm", "logscore_rest_uniform", "top1_rule", "top1_llm",
                                                  "n_place", "place_logscore_rule", "place_logscore_llm", "place_logscore_uniform")}
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(d["gold_tiers"], ensure_ascii=False, indent=1)); print(d.get("stage1"), d.get("stage2"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["dry", "ping", "run", "cases", "cases-run", "tiers"])
    ap.add_argument("--n", type=int, default=16, help="cases: 결정 사례 수 (12~20)")
    ap.add_argument("--effort", default="low", help="cases-run: Responses API reasoning effort")
    ap.add_argument("--stays", type=int, default=0, help="앞에서 몇 체류만 (0 = 59 전체)")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--arms", default="A,A2,B,C")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--mode", default="meal", choices=["meal", "place"], help="cases: meal = 1차(식사 결정) · place = 2차(식당이 둘 이상인 결정, 어느 식당만 비교)")
    a = ap.parse_args()
    if a.cmd == "ping":
        import requests
        r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {api_key()}"}, timeout=30)
        print(r.status_code)
        ids = sorted(x["id"] for x in r.json().get("data", [])) if r.ok else []
        print("모델 수", len(ids), "·", MODEL, "있음" if MODEL in ids else "없음")
        print([i for i in ids if i.startswith("gpt-6") or "luna" in i][:30])
        return
    if a.cmd == "tiers":
        return gold_tiers()
    if a.cmd == "cases":
        return build_cases(a.n, a.mode)
    if a.cmd == "cases-run":
        return run_cases(a.effort, a.mode)
    S = fit_v4.stays()
    if a.stays:
        S = S[: a.stays]
    if a.cmd == "dry":
        tot = Counter(); ex = None
        for g, lab, m in S:
            for arm in ("dry", "dryC"):
                r, e = run_stay(m, arm, 1)
                tot[arm + "_dec"] += r["decisions"]; tot[arm + "_llm"] += r["llm_calls"]; ex = ex or e
        print(f"{len(S)} 체류 · 실행 1번당 결정 {tot['dry_dec']} · B 호출 {tot['dry_llm']} · C 호출 {tot['dryC_llm']}")
        print("\n--- 예시 프롬프트 ---\n" + (ex or ""))
        return
    arms = a.arms.split(",")
    from concurrent.futures import ThreadPoolExecutor

    def one(gm):
        g, lab, m = gm
        row = dict(stay=lab, res={})
        for arm in arms:          # A2 = 규칙 엔진을 다른 난수 줄로 한 번 더 · 난수만 바뀔 때의 차이(잡음 기준)
            r, _ = run_stay(m, "A", a.k, seed_base=fit_v4.SEED + 1000) if arm == "A2" else run_stay(m, arm, a.k)
            row["res"][arm] = r
        print(lab, {arm: (round(row["res"][arm]["brier"], 3), round(row["res"][arm]["recall"], 2), row["res"][arm]["llm_calls"]) for arm in arms}, flush=True)
        return row
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        out = list(ex.map(one, S))
    agg = {arm: dict(recall=round(sum(x["res"][arm]["recall"] for x in out) / len(out) * 100, 1),
                     precision=round(sum(x["res"][arm]["precision"] for x in out) / len(out) * 100, 1),
                     brier=round(sum(x["res"][arm]["brier"] for x in out) / len(out), 4),
                     llm_calls=sum(x["res"][arm]["llm_calls"] for x in out), decisions=sum(x["res"][arm]["decisions"] for x in out)) for arm in arms}
    import math
    for arm in arms:              # 체류별 짝 비교 (A 기준) · 평균 차 ± 표준오차 · 좋아진 / 나빠진 체류 수
        if arm == "A" or "A" not in arms:
            continue
        dd = [x["res"][arm]["brier"] - x["res"]["A"]["brier"] for x in out]
        dr = [x["res"][arm]["recall"] - x["res"]["A"]["recall"] for x in out]
        mu = sum(dd) / len(dd); se = (sum((v - mu) ** 2 for v in dd) / max(1, len(dd) - 1) / len(dd)) ** 0.5
        agg[arm].update(d_brier=round(mu, 4), se_brier=round(se, 4), d_recall=round(sum(dr) / len(dr) * 100, 1),
                        better=sum(1 for v in dd if v < -0.005), worse=sum(1 for v in dd if v > 0.005))
    res = dict(built=datetime.now().strftime("%Y-%m-%d %H:%M"), model=MODEL, model_ver=__import__("version").model_ver(), k=a.k, n=len(out),
               usage=dict(USAGE), agg=agg, stays=out,
               caveat="파일럿입니다. 같은 후보 · 같은 규칙에서 고르는 주체만 바꿨고, 후기 원문 · 정답 · 모델 점수는 LLM 에게 주지 않았습니다. 그럴듯한 설명이 실제 행동을 더 잘 예측한다는 뜻은 아니며, 평가는 후기가 실제로 간 곳과의 재현 · 정밀 · Brier 로만 합니다.")
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(agg, ensure_ascii=False), dict(USAGE))


if __name__ == "__main__":
    main()
