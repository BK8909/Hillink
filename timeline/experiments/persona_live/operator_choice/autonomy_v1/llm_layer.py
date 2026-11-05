"""LLM 계획 계층 (CL-1024-19) — 자율 하루 실행기(agent_day)에 붙는 판단 지원.

역할 분담(서로 다른 점수를 더하지 않는다)
  · LLM     : 고객 프로파일 · 후기 사실 요지 · 방문 목적 · 동행 · 지금 상태(끼니 · 피로 · 앞선 활동) · 운영자 공지를 읽고
              '지금 무엇이 필요한가'와 다음 행동 의도 1~3개(그 시각 실제로 가능한 선택지 중에서)를 고른다. 유지 · 포기 · 쉬기 · 귀가도 선택지.
  · 실행기  : 의도마다 월드 규칙(영업시간 · 자격 · 체크아웃 · 이동 · 하루 끝 · 같은 시설 · 식사 직후)을 다시 검증. 통과하면 실행, 아니면 거절 기록.
  · 정량 엔진 : LLM 이 '저녁 식사'를 고르면 어느 식당인지는 동결 엔진이 고른다(정량 결정 계약 유지). 행사 · 엔진 시설은 엔진의 항(근거)을 그대로 기록.
  · 폴백    : 키 없음 · 한도 초과 · 오류 · 의도 전부 거절 → 기존 규칙 실행. 폴백은 LLM 성공으로 세지 않는다.

비용 · 안전
  · 환경 변수만 읽음: OPENAI_API_KEY(값은 어디에도 쓰지 않음) · HILLINK_LLM_ENABLED=1 · HILLINK_LLM_MODEL(기본 gpt-6-luna)
    HILLINK_MAX_LLM_CALLS(기본 30) · HILLINK_MAX_LLM_COST_USD(기본 2) · HILLINK_LLM_CACHE(응답 캐시 폴더 · 재현용)
  · 호출 전 예상 비용(입력 추정 + 최대 출력)이 남은 예산을 넘으면 호출하지 않음 · 재시도 1회(429 · 5xx · 네트워크)만.
  · 요청에는 고객 ID · 유형 · 성향 수준 · 후기 사실 '요지'(요약 · 원문 아님) · 상태 · 선택지만. 작성자 · URL · 원문 · 경로 없음.
  · HILLINK_LLM_MOCK=1 은 시험용 가짜 응답(실제 LLM 아님 · 보고에서 mock 으로 표시).
"""
from __future__ import annotations

import hashlib, json, os, re, time, urllib.error, urllib.request
from pathlib import Path

from ..operator_world_v1 import engine as EN
from ..operator_world_v1_1 import stay_planner as SP
from ..operator_world_v1_1.candidate import candidate_engine

API_URL = "https://api.openai.com/v1/responses"
# 단가(USD / 1M 토큰) — OpenAI 공식 문서(developers.openai.com/api/docs/pricing · models/gpt-6-luna) 2026-10-24 확인값. 추론 토큰은 출력 토큰에 포함된 값으로 계산(중복 계산 안 함).
PRICES = {"gpt-6-luna": dict(input=0.10, cached=0.01, output=0.50, cache_write_30m=0.125, checked="2026-10-24", source="developers.openai.com/api/docs/pricing")}
MAX_OUT = 900
NOW_LABEL = {"pool": "수영장", "sauna": "사우나", "footbath": "족욕", "night_footbath": "야경 족욕", "forest_walk": "포레스트 파크 산책"}
CODE_ENGINE = {"pool": "POOL", "sauna": "SAUNA", "footbath": "SKYARD", "night_footbath": "SKYARD_NIGHT", "forest_walk": "FOREST_WALK"}
SPECIAL = {"dinner": "저녁 식사(어느 식당인지는 정량 엔진이 고름)", "wine_fair": "포레스트 파크 와인페어 참여", "rest_room": "객실로 돌아가 쉬기",
           "stay_put": "지금 자리에서 잠시 쉬며 있기(아무것도 하지 않음)", "leave": "일정을 마치고 귀가", "lunch_skip": "점심은 건너뛰기"}


def cfg():
    return dict(enabled=os.environ.get("HILLINK_LLM_ENABLED") == "1", mock=os.environ.get("HILLINK_LLM_MOCK") == "1",
                has_key=bool(os.environ.get("OPENAI_API_KEY")), model=os.environ.get("HILLINK_LLM_MODEL", "gpt-6-luna"),
                max_calls=int(os.environ.get("HILLINK_MAX_LLM_CALLS", "30")), max_cost=float(os.environ.get("HILLINK_MAX_LLM_COST_USD", "2")),
                cache=os.environ.get("HILLINK_LLM_CACHE") or None, effort=os.environ.get("HILLINK_LLM_EFFORT", "low"),
                replay=os.environ.get("HILLINK_LLM_REPLAY") == "1")   # 캐시 재생 전용 — 네트워크 호출 없음 · 캐시에 없으면 규칙 폴백


class Usage:
    """실행 단위 사용량 — 호출별 · 고객별 · 전체. 키 · 원문은 담지 않는다."""
    def __init__(self):
        self.reset()

    def reset(self, label="run"):
        c = cfg()
        self.label, self.cfg = label, {k: v for k, v in c.items() if k != "has_key"} | {"key_present": c["has_key"]}
        self.calls, self.stopped, self.t0, self.fail_streak = [], None, time.time(), 0
        self.prior = getattr(self, "prior", dict(calls=0, cost_usd=0.0))   # 같은 출력 폴더의 앞선 실행(1차 · 2차 …)까지 합산해 한도 적용
        self.decisions = dict(llm_plans=0, intents=0, accepted=0, rejected=0, fallback_steps=0, merged=0, cooldown_steps=0)

    def spent(self):
        return sum(x.get("cost_usd") or 0 for x in self.calls)

    def can_call(self, est_cost):
        c = self.cfg
        n = sum(1 for x in self.calls if not x.get("cache_hit") and not x.get("mock")) + self.prior["calls"]
        if n >= c["max_calls"]:
            self.stopped = f"호출 수 한도 {c['max_calls']}회 도달(앞선 실행 {self.prior['calls']}회 포함)"; return False
        if self.spent() + self.prior["cost_usd"] + est_cost > c["max_cost"]:
            self.stopped = f"예산 한도 ${c['max_cost']} — 다음 호출 예상 ${est_cost:.4f}"; return False
        return True

    def summary(self):
        real = [x for x in self.calls if not x.get("cache_hit") and not x.get("mock") and not x.get("cache_miss")]
        per = {}
        for x in self.calls:
            p = per.setdefault(x["persona"], dict(calls=0, ok=0, failed=0, retries=0, cache_hits=0, input_tokens=0, cached_tokens=0, output_tokens=0, reasoning_tokens=0, total_tokens=0, cost_usd=0.0, ms=0))
            p["calls"] += 1; p["ok"] += int(x["ok"]); p["failed"] += int(not x["ok"]); p["retries"] += x.get("retries", 0); p["cache_hits"] += int(bool(x.get("cache_hit")))
            for k in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "ms"):
                p[k] += x.get(k) or 0
            p["cost_usd"] = round(p["cost_usd"] + (x.get("cost_usd") or 0), 6)
        tot = {k: sum(p[k] for p in per.values()) for k in ("calls", "ok", "failed", "retries", "cache_hits", "input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "ms")}
        tot["cost_usd"] = round(sum(p["cost_usd"] for p in per.values()), 6)
        tot["real_api_calls"] = len(real); tot["real_api_ok"] = sum(1 for x in real if x["ok"]); tot["mock_calls"] = sum(1 for x in self.calls if x.get("mock"))
        replay = [x for x in self.calls if x.get("cache_hit") and not x.get("mock")]
        misses = sum(1 for x in self.calls if x.get("cache_miss"))
        mode = "mock(실제 LLM 아님)" if self.cfg["mock"] else f"replay(캐시 재생 전용 · 재생 {sum(1 for x in self.calls if x.get('cache_hit'))} · 캐시 없음 {misses} → 규칙 폴백)" if self.cfg.get("replay") else ("llm_assisted" if any(x["ok"] for x in real) else "LLM 호출 시도 실패 → 규칙 폴백" if real
                                                              else "llm_assisted(캐시 재생 · 이번 실행 실호출 0)" if replay else "rule_only")
        why0 = None
        if not real:
            why0 = ("HILLINK_LLM_MOCK=1 — 시험용 가짜 응답" if self.cfg["mock"] else "HILLINK_LLM_REPLAY=1 — 저장된 응답만 재생(새 호출 안 함)" if self.cfg.get("replay") else "HILLINK_LLM_ENABLED 가 1 이 아님" if not self.cfg["enabled"]
                    else "OPENAI_API_KEY 없음" if not self.cfg["key_present"] else (self.stopped or "실호출 없음(캐시 재생 또는 오류)"))
        return dict(label=self.label, mode=mode, model=self.cfg["model"], api="OpenAI Responses API (POST /v1/responses)", prices=PRICES.get(self.cfg["model"]),
                    limits=dict(max_calls=self.cfg["max_calls"], max_cost_usd=self.cfg["max_cost"]), stopped=self.stopped, total=tot, per_persona=per,
                    decisions=self.decisions, zero_call_reason=why0, wall_sec=round(time.time() - self.t0, 1),
                    errors=[dict(persona=x["persona"], error=x.get("error")) for x in self.calls if not x["ok"]],
                    calls=[{k: v for k, v in x.items() if k not in ("raw",)} for x in self.calls])


USAGE = Usage()
_MEM = {}


def cost_of(model, inp, cached, out):
    p = PRICES.get(model)
    if not p:
        return None
    return round(((inp - cached) * p["input"] + cached * p["cached"] + out * p["output"]) / 1e6, 8)


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["need", "interest", "reaction_to_notice", "intents"],
          "properties": {"need": {"type": "string"}, "interest": {"type": "string"}, "reaction_to_notice": {"type": "string"},
                         "intents": {"type": "array", "maxItems": 3, "items": {"type": "object", "additionalProperties": False,
                                                                                "required": ["option", "why", "fact_ids", "profile_basis", "alternatives", "keep_or_change"],
                                                                                "properties": {"option": {"type": "string"}, "why": {"type": "string"},
                                                                                               "fact_ids": {"type": "array", "items": {"type": "string"}}, "profile_basis": {"type": "string"},
                                                                                               "alternatives": {"type": "array", "items": {"type": "string"}},
                                                                                               "keep_or_change": {"type": "string"}}}}}}
SYSTEM = ("당신은 워커힐 호텔에 머무는 한 고객의 다음 행동을 정하는 판단자입니다. 주어진 고객의 성향 수준과 후기 사실 요지, 방문 목적 · 동행, 지금 상태(시각 · 끼니 · 피로 · 앞선 활동)를 읽고 "
          "이 고객이 지금 무엇을 원할지 판단한 뒤, options 에 있는 id 중에서만 다음 행동 의도를 1~3개 차례로 고르세요. "
          "아무것도 하지 않기(stay_put) · 객실 휴식 · 귀가 · 기존 계획 유지도 좋은 선택입니다. 운영자 공지가 있으면 이 고객이 그것을 중요하게 여길 이유가 있는지 판단하고, 이유가 없으면 반응하지 마세요. "
          "같은 장소에서 식사 직후 또 먹거나, 지친 상태에서 연달아 움직이는 선택은 피하세요. why 는 고객을 설명하는 자연스러운 한국어 한 문장(60자 안팎)으로, "
          "실제로 판단에 쓴 후기 사실이 있으면 그 id 를 fact_ids 에 넣으세요(목록에 없는 id 금지 · 의미가 다른 사실을 끼워 맞추지 말 것). 근거가 성향뿐이면 fact_ids 는 비우세요. "
          "alternatives 에는 실제로 견주어 본 다른 option id 를, keep_or_change 에는 '유지' · '변경' · '포기' · '새로 시도' 중 하나를 쓰세요. "
          "고객 프로파일의 review_confirmed 는 후기에서 확인된 실제 경험(인용 가능한 fact_ids)이고, profile_inference 는 분석가가 세운 판단 패턴 · 행동 가설(검증 전)입니다. "
          "가설은 판단에 참고하되 실제 경험처럼 쓰지 마세요. profile_basis 에는 이 선택을 이끈 구체적인 경험 · 판단 패턴을 짧게(40자 안팎) 쓰세요(예: '수영 뒤 지치면 룸서비스를 고른 경험'). "
          "같은 곳을 다시 찾거나 쉬는 시간을 이어 가는 선택도 그 고객에게 분명한 이유가 있으면 괜찮습니다. "
          "where 가 '다른 곳'인 경험은 워커힐에서 겪은 일이 아니므로, 인용하면 화면에 '다른 곳 경험에서 확장한 추론'으로 표시됩니다. "
          "아침 경험을 점심 · 저녁 선택의 근거로 쓰는 것처럼 끼니가 다른 경험도 확장 추론입니다. 지치지 않았는데 쉬기만 반복하지 마세요.")


def _facts_for(a, codes, k=14):
    """요청에 넣을 그 고객의 후기 사실 요지 — 선택지와 연결된 사실 우선 · 숨김 제외 · 요약만."""
    picked = []
    for c in codes:
        for f in a.P["fact_hits"].get(c, [])[:3]:
            if f not in picked:
                picked.append(f)
    for f in (a.traits.get("evidence_index") or {}):
        if len(picked) >= k:
            break
        if f not in picked:
            picked.append(f)
    out = []
    for f in picked[:k]:
        g = a.gist(f)
        if g:
            out.append(dict(id=f, gist=re.sub(r"https?://\S+", "", g)[:90]))
    return out


def options_now(a, world, t):
    """그 시각 실제로 할 수 있는 선택지(실행기 규칙으로 미리 거른 것) — LLM 은 이 중에서만 고른다."""
    from . import agent_day as AD
    opts, rej = [], {}
    eng = AD.engine_world_for(a, world, t) if a.checked_in or not a.stay else None
    st = dict(used=set(a.used), hunger=a.hunger_e)
    for c in list(AD.LEISURE) + (list(SP.LUNCH) if (not a.meals["lunch"] and SP._hm("11:00") <= t < SP._hm("14:00")) else []):
        if c in ("room_nap",) or c.startswith("room") and not (a.stay and a.checked_in and not a.checked_out):
            continue
        loc = AD.plan_ok(a, c, t, world, rej)
        if loc:
            opts.append(dict(id=c, label=SP.ACT[c][0], kind=AD.PLAN_DOMAIN.get(SP.ACT[c][2], SP.ACT[c][2]), minutes=SP.ACT[c][3], travel_min=SP.travel_min(a.loc, loc)))
    if eng and SP._hm("17:00") <= t < SP._hm("21:00") and a.hunger_e >= 0.3:
        meals = [o for o in eng["offers"] if o["kind"] in ("restaurant", "room_meal", "simple_meal") and not EN.feasible(o, t, st, dict(a.visit_e, checkin=AD.mh(t)))]
        if meals:
            opts.append(dict(id="dinner", label=SPECIAL["dinner"], kind="식사", choices=[AD.VENUE_KO.get(o["id"], o["label"]) for o in meals]))
    if eng:
        wf = next((o for o in eng["offers"] if o["id"] == "WINE_FAIR" and o["available"]), None)
        if wf and "WINE_FAIR" not in a.used and not EN.feasible(wf, t, st, dict(a.visit_e, checkin=AD.mh(t))):
            opts.append(dict(id="wine_fair", label=SPECIAL["wine_fair"], kind="행사", minutes=wf["duration_min"], price_pp_krw=wf["price_pp_krw"], window=wf["window"]))
    if a.stay and a.checked_in and not a.checked_out:
        opts.append(dict(id="rest_room", label=SPECIAL["rest_room"], kind="객실 휴식"))
    opts.append(dict(id="stay_put", label=SPECIAL["stay_put"], kind="휴식"))
    if a.phase == "visit" or a.checked_out:
        opts.append(dict(id="leave", label=SPECIAL["leave"], kind="체류"))
    if not a.meals["lunch"] and SP._hm("11:30") <= t < SP._hm("14:00"):
        opts.append(dict(id="lunch_skip", label=SPECIAL["lunch_skip"], kind="식사"))
    return opts


def _persona_block(a, codes):
    from . import profile_context as PC
    ctx, cite, cov = PC.context(a)
    a.llm_cov = cov
    b, f = a.P["bars"], a.P["facets"]
    lv = {**{SP.BAR_LABEL.get(k, k): round(v, 2) for k, v in b.items() if v >= 0.2}, **{SP.FACET_LABEL.get(k, k): round(v, 2) for k, v in f.items() if v >= 0.2 and k in SP.FACET_LABEL}}
    v = a.vs
    return dict(id=a.pid, type=a.P.get("type") or "", visit=dict(stay=v["stay"], building=v["building"] if v["stay"] else None, nights=v["nights"], phase=v["phase"]),
                companions=dict(n=a.N, rel=v["rel"], kids=v["kids"], elder=v["elder"]), trait_levels=lv, profile=ctx, citable_fact_ids=cite,
                pace="휴식을 자주 찾는 편" if a.rest_limit < 2.4 else "활동량이 많은 편" if a.rest_limit > 3.2 else "보통")


def _state_block(a, world, t):
    from . import agent_day as AD
    recent = [dict(t=x["t"], what=x["label"], kind=x["domain"]) for x in a.log if x["act"] not in ("move", "wait")][-6:]
    r = a.fatigue / max(0.8, a.rest_limit)
    notices = [c.get("label") for c in world.changes if SP._hm(c["at"]) <= t]
    return dict(time=AD.mh(t), place=a.loc, meals=a.meals, fatigue=("여유" if r < 0.4 else "조금 피곤" if r < 0.8 else "피곤"), recent=recent, spent_krw=int(a.spent),
                checkout_by="11:00" if a.phase == "checkout" and not a.checked_out else None, day_end=AD.mh(a.end), operator_notices=notices)


def _call(a, prompt):
    c = USAGE.cfg
    key = hashlib.sha256((c["model"] + "|" + prompt).encode()).hexdigest()
    mkey = ("mock|" if c["mock"] else "") + key   # 메모리 캐시: mock 응답이 실제 · 재생 실행에 섞이지 않게
    rec = dict(persona=a.pid, t=None, prompt_sha=key[:16], model=c["model"], ok=False, retries=0, cache_hit=False, mock=c["mock"])
    if mkey in _MEM:
        rec.update(_MEM[mkey]["usage"], ok=True, cache_hit=True, cost_usd=0.0, ms=0); USAGE.calls.append(rec); return _MEM[mkey]["plan"]
    cache = Path(c["cache"]) / f"{key}.json" if c["cache"] else None
    if cache and cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8")); _MEM[mkey] = d
        rec.update(d["usage"], ok=True, cache_hit=True, cost_usd=0.0, ms=0); USAGE.calls.append(rec); return d["plan"]
    if c.get("replay"):
        rec.update(ok=False, cache_miss=True, error="캐시에 없음(재생 전용 — 새 호출 안 함)", cost_usd=0.0, ms=0)
        USAGE.calls.append(rec); return None
    if c["mock"]:
        plan = _mock_plan(prompt)
        rec.update(ok=True, input_tokens=0, cached_tokens=0, output_tokens=0, reasoning_tokens=0, total_tokens=0, cost_usd=0.0, ms=0)
        USAGE.calls.append(rec); _MEM[mkey] = dict(plan=plan, usage={k: rec[k] for k in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens", "total_tokens")}); return plan
    est = cost_of(c["model"], len(prompt) // 2 + 600, 0, MAX_OUT) or 0.01
    if not USAGE.can_call(est):
        return None
    body = {"model": c["model"], "input": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}], "max_output_tokens": MAX_OUT,
            "reasoning": {"effort": c["effort"]}, "text": {"format": {"type": "json_schema", "name": "next_intents", "strict": True, "schema": SCHEMA}}}
    t0 = time.time(); last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("OPENAI_API_KEY", "")})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode())
            u = d.get("usage") or {}
            inp, cached, out = u.get("input_tokens", 0), (u.get("input_tokens_details") or {}).get("cached_tokens", 0), u.get("output_tokens", 0)
            rec.update(model_returned=d.get("model"), input_tokens=inp, cached_tokens=cached, output_tokens=out,   # 응답 해석 전에 사용량 · 비용부터 기록(해석 실패도 과금됨)
                       reasoning_tokens=(u.get("output_tokens_details") or {}).get("reasoning_tokens", 0), total_tokens=u.get("total_tokens", inp + out),
                       cost_usd=cost_of(c["model"], inp, cached, out), ms=int((time.time() - t0) * 1000), response_id=d.get("id"), status=d.get("status"))
            txt = "".join(cc.get("text", "") for it in d.get("output", []) if it.get("type") == "message" for cc in it.get("content", []) if cc.get("type") == "output_text")
            try:
                plan = json.loads(txt)
            except ValueError:
                rec.update(error=f"응답 해석 실패(status={d.get('status')})"); USAGE.calls.append(rec); USAGE.fail_streak += 1
                if USAGE.fail_streak >= 3:
                    USAGE.stopped = "연속 3회 실패 — 중단"; USAGE.cfg["max_calls"] = 0
                return None
            rec["ok"] = True; USAGE.fail_streak = 0
            USAGE.calls.append(rec)
            store = dict(plan=plan, usage={k: rec[k] for k in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens", "total_tokens")})
            _MEM[mkey] = store
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True); cache.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
            return plan
        except urllib.error.HTTPError as e:
            code = e.code; last = {400: "요청 형식 오류(400)", 401: "인증 실패(401)", 403: "권한 없음(403)", 404: "모델 또는 경로 없음(404)", 429: "요청 · 사용량 한도(429)"}.get(code, f"HTTP {code}")
            try:
                msg = json.loads(e.read().decode()).get("error", {}).get("message", "")[:160]
                if code not in (401, 403):   # 인증 오류 설명에는 가려진 키 일부가 들어 있어 기록하지 않음
                    last += " — " + re.sub(r"sk-\S+|provided:\s*\S+", "[가림]", msg)
            except Exception:
                pass
            if code in (429, 500, 502, 503, 504) and attempt == 0:
                rec["retries"] += 1; time.sleep(2); continue
            break
        except (urllib.error.URLError, TimeoutError) as e:
            last = f"네트워크 · 시간 초과({type(e).__name__})"
            if attempt == 0:
                rec["retries"] += 1; time.sleep(2); continue
            break
        except (ValueError, KeyError) as e:
            last = f"응답 해석 실패({type(e).__name__})"; break
    rec.update(error=last, ms=int((time.time() - t0) * 1000), cost_usd=0.0)
    USAGE.calls.append(rec); USAGE.fail_streak += 1
    if last and ("(400)" in last or "(401)" in last or "(403)" in last or "(404)" in last or USAGE.fail_streak >= 3):
        USAGE.stopped = last   # 같은 오류로 반복 호출하지 않음
        USAGE.cfg["max_calls"] = 0
    return None


def _mock_plan(prompt):
    """시험용 — 선택지 목록에서 규칙적으로 고른 가짜 의도(실제 LLM 아님)."""
    d = json.loads(prompt.split("[지금]\n", 1)[1])
    ids = [o["id"] for o in d["options"]]
    pref = [x for x in ("dinner", "wine_fair", "theatre", "cafe", "garden_walk", "rest_room", "stay_put") if x in ids]
    pick = (pref or ids)[:2]
    return dict(need="(mock)", interest="(mock)", reaction_to_notice="(mock)", intents=[dict(option=x, why="(mock) 시험용 의도", fact_ids=[], profile_basis="(mock)", alternatives=[], keep_or_change="유지") for x in pick])


def plan(a, world, t):
    opts = options_now(a, world, t)
    if not opts:
        return False
    codes = [o["id"] for o in opts]
    cust = _persona_block(a, codes)
    now = dict(state=_state_block(a, world, t), options=opts, ask="지금부터 2~3시간 안에 이 고객이 할 다음 행동 의도를 1~3개 차례로 고르세요.")
    # 고객 프로파일(같은 고객이면 매번 같음)을 앞에 두어 입력 캐시가 걸리게 하고, 바뀌는 상태 · 선택지는 뒤에
    prompt = "[고객 프로파일]\n" + json.dumps(cust, ensure_ascii=False, sort_keys=True) + "\n\n[지금]\n" + json.dumps(now, ensure_ascii=False, sort_keys=True)
    req = dict(customer=cust)
    p = _call(a, prompt)
    USAGE.decisions["llm_plans"] += int(bool(p))
    if not p:
        return False
    allowed_f = set(req["customer"]["citable_fact_ids"])
    a.intents = []
    for it in (p.get("intents") or [])[:3]:
        fids = [f for f in it.get("fact_ids", []) if f in allowed_f]   # 목록 밖 · 남의 사실 ID 제거
        why = re.sub(r"https?://\S+", "", str(it.get("why", "")))[:120]
        a.intents.append(dict(option=str(it.get("option", "")), why=why, fact_ids=fids, alternatives=[x for x in it.get("alternatives", []) if x in codes][:4],
                              keep_or_change=str(it.get("keep_or_change", ""))[:8], profile_basis=re.sub(r"https?://\S+", "", str(it.get("profile_basis", "")))[:80], dropped_fact_ids=[f for f in it.get("fact_ids", []) if f not in allowed_f]))
    a.llm_ctx = dict(t=t, need=str(p.get("need", ""))[:160], interest=str(p.get("interest", ""))[:160], reaction=str(p.get("reaction_to_notice", ""))[:160],
                     options=codes, notices=len([c for c in world.changes if SP._hm(c["at"]) <= t]))
    USAGE.decisions["intents"] += len(a.intents)
    return True


def _ev(a, it, traits, rec=None):
    tgt = {str(rec["act"]).split(":")[0], rec["loc"]} if rec else None
    ev = a.ev_review(it["fact_ids"], "LLM 판단에 쓰인 후기 사실", target=tgt, slot=(rec or {}).get("meal_slot")) if it["fact_ids"] else []
    if not ev or traits:
        ev.append(dict(type="프로파일 기반 추론", traits=traits, about="누적 성향 · 지금 상황(LLM 판단)"))
    return ev


def _internal(a, it, extra=None):
    return dict(backend="llm", need=a.llm_ctx.get("need"), interest=a.llm_ctx.get("interest"), reaction=a.llm_ctx.get("reaction"),
                alternatives=it["alternatives"], keep_or_change=it["keep_or_change"], profile_basis=it.get("profile_basis"), dropped_fact_ids=it["dropped_fact_ids"], **(extra or {}))


def _rest_backed(a, it):
    """반복 휴식 규칙의 예외 — LLM 이 워커힐에서 직접 겪은 쉬는 방식(객실 · 욕조 · 잠깐 나갔다 돌아오기 등)을 인용했을 때."""
    from . import profile_context as PC
    # CL-1024-20 — '객실'이나 '돌아'라는 낱말만으로는 부족: 객실(욕조 · 침대)에서 쉰 경험 자체를 적은 사실만(예: 반신욕 뒤 누워 쉼 · 욕조 객실을 골라 머묾)
    def rests_in_room(g):
        return ("객실" in g or "욕조" in g or "반신욕" in g) and any(k in g for k in ("쉬", "쉼", "누워", "휴식", "반신욕", "욕조", "머물"))
    return any(PC.fact_context(a, f) == "wh" and rests_in_room(a.gist(f)) for f in it["fact_ids"])


def execute(a, world, t, it):
    """의도 하나를 검증 · 실행. 실행하면 True, 거절이면 (False, 이유)."""
    from . import agent_day as AD
    o = it["option"]
    dom = AD.PLAN_DOMAIN.get(SP.ACT[o][2]) if o in SP.ACT else ("웰니스" if o in ("pool", "sauna", "footbath", "night_footbath") else None)
    if dom == "웰니스":   # 같은 영역을 이유 없이 늘리지 않음 — 오늘 웰니스 2회 이상이면 그 시설에 관한 후기 사실 인용이 있어야
        n_well = sum(1 for x in a.log if x["domain"] == "웰니스")
        fam = {AD.PLACE_FAMILY.get(o, o), AD.PLACE_FAMILY.get(CODE_ENGINE.get(o, ""), CODE_ENGINE.get(o, ""))}
        cited = [f for f in it["fact_ids"] if {AD.PLACE_FAMILY.get(x, x) for x in a.fact_places(f)} & fam]
        if n_well >= 2 and not cited:
            return False, f"오늘 웰니스 {n_well}회 — 이 시설에 관한 후기 사실 인용 없이 더 늘리지 않음"
    if o == "dinner":
        eng = AD.engine_world_for(a, world, t)
        eng = dict(eng, offers=[x for x in eng["offers"] if x["kind"] in ("restaurant", "room_meal", "simple_meal", "rest")])
        try:
            with candidate_engine(c1=True, c2="venue_visits", c3=True):
                d = EN.decide_at(t, dict(used=set(a.used), hunger=a.hunger_e, _depth=99), dict(a.visit_e, checkin=AD.mh(t)), a.traits, eng)
        except IndexError:
            return False, "저녁 후보 없음"
        if d["chosen"] == "ROOM_REST":
            ok = sorted([r for r in d["rejected"] if r["feasible"] and r["offer"] != "ROOM_REST"], key=lambda r: -(r["total"] or r["score"] or 0))
            if not ok:
                return False, "지금 먹을 수 있는 저녁 없음"
            d = _force(a, eng, t, ok[0]["offer"])
        rec = AD.engine_do(a, d, eng, t)
        rec["source"] = "llm_plan+quantitative_engine"
        rec["why"] = (it["why"] + " " if it["why"] else "") + f"(식당은 정량 엔진이 {AD.VENUE_KO.get(d['chosen'], d['chosen'])}로 골랐습니다.)"
        rec["evidence"] = _ev(a, it, [], rec) + [e for e in rec["evidence"] if e["type"] == "후기에서 확인"]
        rec["internal"] = dict(rec.get("internal") or {}, **_internal(a, it, dict(arbitration="LLM: 지금 저녁을 먹을지 · 정량 엔진: 어느 식당인지")))
        return True, None
    if o == "wine_fair" or (o in CODE_ENGINE and t >= SP._hm("15:30") and a.checked_in and not a.checked_out):
        eid = "WINE_FAIR" if o == "wine_fair" else CODE_ENGINE[o]
        eng = AD.engine_world_for(a, world, t)
        off = next((x for x in eng["offers"] if x["id"] == eid), None)
        if not off:
            return False, "엔진 월드에 없음 · 운영 안 함"
        bl = EN.feasible(off, t, dict(used=set(a.used), hunger=a.hunger_e), dict(a.visit_e, checkin=AD.mh(t)))
        if eid == "FOREST_WALK" and any(x["kind"] == "event" and x["venue"] == "FOREST" and x["available"] for x in eng["offers"]):
            bl = bl + ["행사 날 포레스트 파크 일반 이용 제한(공식)"]
        if bl:
            return False, " · ".join(bl)
        d = _force(a, eng, t, eid)
        rec = AD.engine_do(a, d, eng, t)
        rec["source"] = "llm_plan+quantitative_engine"
        rec["why"] = it["why"] or rec["why"]
        rec["evidence"] = _ev(a, it, sorted({x.get("facet") for x in d["reasons"] if x.get("facet") and x.get("evidence") and x["value"] > 0}), rec) + [e for e in rec["evidence"] if e["type"] == "후기에서 확인" and not it["fact_ids"]]
        rec["internal"] = dict(rec.get("internal") or {}, **_internal(a, it, dict(arbitration="LLM: 참여 · 이용 의도 · 정량 엔진: 항 · 근거 기록(점수 합산 없음)")))
        return True, None
    if o == "rest_room":
        if not (a.stay and a.checked_in and not a.checked_out):
            return False, "객실 이용 불가(비투숙 · 체크인 전 · 퇴실 뒤)"
        rr = AD.rest_ok(a, t)
        if rr and not _rest_backed(a, it):
            return False, rr
        n0 = len(a.log)
        rec = a.add("activity", "room_rest", "객실 휴식", a.room, t, 45, "객실 휴식", "llm_plan", it["why"] or "객실에서 쉬어 갑니다.", [], _internal(a, it, dict(rest_rule_override="후기 근거 휴식" if rr else None)))
        rec["evidence"] = AD.merge_evidence(_ev(a, it, ["rest_need"], rec) + ([] if len(a.log) > n0 else rec["evidence"]))
        return True, None
    if o == "stay_put":
        rr = AD.rest_ok(a, t)
        if rr and not _rest_backed(a, it):
            return False, rr
        a.add("wait", "idle", "잠시 쉬며 머묾", a.loc or "HOTEL_GATE", t, 30, "휴식", "llm_plan", it["why"] or "잠시 쉬어 갑니다.", _ev(a, it, [], dict(act="idle", loc=a.loc or "HOTEL_GATE")), _internal(a, it)); return True, None
    if o == "leave":
        if not (a.phase == "visit" or a.checked_out):
            return False, "투숙 중 귀가는 선택지 아님"
        a.add("activity", "leave", "귀가", "HOTEL_GATE", t, 15, "체류", "llm_plan", it["why"] or "일정을 마치고 나섭니다.", _ev(a, it, [], dict(act="leave", loc="HOTEL_GATE")), _internal(a, it))
        a.left = True; a.ended = True; return True, None
    if o in SP.ACT:
        rej = {}
        loc = AD.plan_ok(a, o, t, world, rej)
        note = "LLM 의도"
        if not loc and rej.get(o) in ("오늘 이미 이용", "오늘 이미 이 업장에서 식사함"):
            # 재방문은 무조건 막지 않음 — 그 시설 · 업장에 대한 후기 경험(fact)을 LLM 이 인용하고, 앞선 이용에서 4시간 넘게 지났을 때만 허용
            related = set(a.P["fact_hits"].get(o, [])) | {f for vs in (a.traits.get("venues") or {}).values() for v in vs for f in (v.get("fact_ids") or [])
                                                         if AD.LUNCH_ENGINE.get(o) == v.get("venue") or (SP.ACT[o][1](a.B) == v.get("venue"))}
            last_use = max([AD.hm(x["e"]) for x in a.log if x["act"] == o or (AD.LUNCH_ENGINE.get(o) and x["act"] == AD.LUNCH_ENGINE.get(o))] or [0])
            cited = [f for f in it["fact_ids"] if f in related]
            if cited and t - last_use >= 240:
                rej2 = {}
                loc = AD.plan_ok(a, o, t, world, rej2, revisit=True)
                if loc:
                    note = f"후기 근거 재방문({','.join(cited[:3])})"
                else:
                    return False, rej2.get(o, "규칙 불통과")
            else:
                return False, rej.get(o) + (" — 재방문 근거(이 시설 후기 사실) 인용 없음" if not cited else " — 앞선 이용 뒤 4시간 미만")
        if not loc:
            return False, rej.get(o, "규칙 불통과")
        AD.plan_do(a, o, loc, t, {}, rej, source="llm_plan", note=note)
        rec = a.log[-1]
        _, traits = SP.why(o, a.P, a.C, a.ctx())
        rec["why"] = it["why"] or rec["why"]
        rec["evidence"] = _ev(a, it, traits, rec)
        rec["internal"] = dict(rec.get("internal") or {}, **_internal(a, it))
        return True, None
    return False, "선택지 목록에 없는 id"


def _force(a, eng, t, eid):
    """특정 엔진 상품의 항 · 근거를 그대로 계산해 결정 기록 형태로(정량 엔진 계수 · 항 그대로 · 순위만 LLM 의도)."""
    from . import agent_day as AD
    o = next(x for x in eng["offers"] if x["id"] == eid)
    st = dict(used=set(a.used), hunger=a.hunger_e)
    with candidate_engine(c1=True, c2="venue_visits", c3=True):
        terms = EN.score(o, t, st, dict(a.visit_e, checkin=AD.mh(t)), a.traits, eng)
    s0 = max(t, SP._hm(o["window"]["start"])) if o["window"] else t
    return dict(chosen=eid, label=o["label"], kind=o["kind"], stage="선택", score=round(sum(x["value"] for x in terms), 4), total=None, margin=None, runner_up=None,
                starts=AD.mh(s0), ends=AD.mh(s0 + o["duration_min"]), reasons=EN.reasons_from_terms(terms, a.traits), terms=terms, rejected=[], next_plan=None, event_stages=[])


def step(a, world, t):
    from . import agent_day as AD
    c = USAGE.cfg
    if not c["enabled"] or (not c["key_present"] and not c["mock"] and not c.get("replay")) or (c["max_calls"] <= 0 and not c["mock"] and not c.get("replay")):
        USAGE.decisions["fallback_steps"] += 1
        return False
    if getattr(a, "llm_cool_until", -1) > t:   # 직전 계획의 의도가 모두 거절됐으면 잠시 규칙으로(같은 상태로 다시 부르지 않음)
        USAGE.decisions["fallback_steps"] += 1; USAGE.decisions["cooldown_steps"] = USAGE.decisions.get("cooldown_steps", 0) + 1
        return False
    n_notice = len([x for x in world.changes if SP._hm(x["at"]) <= t])
    if not a.intents or (a.llm_ctx and a.llm_ctx.get("notices", 0) < n_notice):
        if not plan(a, world, t):
            USAGE.decisions["fallback_steps"] += 1
            return False
    any_ok = False
    while a.intents:
        it = a.intents.pop(0)
        n0, last0 = len(a.log), (a.log[-1] if a.log else None)
        ok, why = execute(a, world, t, it)
        merged = bool(ok and len(a.log) == n0 and a.log and a.log[-1] is last0)
        a.trace.append(dict(t=AD.mh(t), backend="llm", option=it["option"], accepted=ok, reject_reason=why, keep_or_change=it["keep_or_change"],
                            need=a.llm_ctx.get("need"), interest=a.llm_ctx.get("interest"), reaction=a.llm_ctx.get("reaction"), alternatives=it["alternatives"],
                            why=it["why"], profile_basis=it.get("profile_basis"), fact_ids=it["fact_ids"], dropped_fact_ids=it["dropped_fact_ids"],
                            result=(a.log[-1]["label"] if ok else None), result_source=(a.log[-1]["source"] if ok else None), merged=merged))
        if ok:
            USAGE.decisions["accepted"] += 1
            USAGE.decisions["merged"] = USAGE.decisions.get("merged", 0) + int(merged)
            return True
        USAGE.decisions["rejected"] += 1
    a.llm_cool_until = t + 60   # 이번 계획이 하나도 실행되지 못함 → 60분 동안 규칙 결정(불필요한 재호출 방지)
    USAGE.decisions["fallback_steps"] += 1
    return False
