"""QA 전용 신규 프로파일 통합 계층(CL-1024-12 긴급 보충 · Codex CD-1024-06 P0-1).

- 본제품 11명 입력(turn_view.load_all_personas · persona_library)은 건드리지 않는다. 여기서 읽는 고객은 '정량 등록부 밖의 QA 후보'뿐이다.
- 입력 위치는 저장소 밖 비공개 경로만: 환경변수 HILLINK_QA_PROFILE_ROOT(여러 개는 os.pathsep 로 구분). 없으면 아무것도 읽지 않는다.
- 패키지의 checksums.sha256 와 실제 파일 SHA-256 이 맞을 때만 '로드'로 본다. 존재 · 파싱 가능만으로 통과시키지 않는다.
- 원문 인용(anchors · EVIDENCE_MAP) · 계정 · URL 은 읽어도 계획기 입력 · 응답 · 로그로 내보내지 않는다(사실 ID · 분석 요지 detail · 특징 키만).
- 성향 수준은 '사실 · 일상 슬롯 → 계획기 성향 키' 고정 키워드 대응으로 만든 QA 매핑이다. 검증된 행동계수가 아니며 결과에 맞춰 조정하지 않는다.
"""
import hashlib
import json
import os
import re
from pathlib import Path

ENV = "HILLINK_QA_PROFILE_ROOT"
DAILY_SLOTS = ["breakfast", "lunch_dinner", "snacks_cafes", "activity_rest", "wellness", "room_time", "time_route",
               "companion_decisions", "event_adjustment", "facility_trial", "repeat_alternative", "surprise_response"]
MAPPING_VERSION = "QA-MAP-1024-12b"
# 자료 승인 상태(Codex CD-1024-06 기준) — QA 입력으로만 쓰며 제품 승인 자료가 아니다. 보류 · 수정 후보는 별도 표시.
APPROVAL = "QA_INPUT_NOT_PRODUCT_APPROVED"
HOLD = {"N20": "Codex 공식 수용 보류(N20-F009 단계 미확정)", "N03": "Codex 공식 수용 보류(N03-F001 단계 미확정)", "N08": "V2 수정 후보 — 현재 판본은 수정 전"}

# 사실(분석 요지 detail · feature_key) · 일상 슬롯 요약 → 계획기 성향 키. 'bar' 는 '바레(barre)'와 겹치므로 쓰지 않는다.
def _k(ko, en):
    """한글 요지는 부분 일치, 영문 특징 키는 단어 단위(밑줄 → 공백) — 'rest'⊂'restaurant' · 'walk'⊂'walkerhill' · 'run'⊂'brunch' 오일치 방지."""
    return ko + "|" + "|".join(rf"\b{w}\b" for w in en.split())

# 사실(분석 요지 detail · feature_key) · 일상 슬롯 요약 → 계획기 성향 키(QA-MAP-1024-12b)
TRAIT_RX = {
    "food":        _k(r"식사|저녁|점심|명월관|금룡|모에기|온달|오마카세|뷔페|브런치|코스", "dinner lunch buffet omakase brunch course dining myeongwol myeongwolgalbi gumryong moegi ondal"),
    "value_check": _k(r"가격|할인|쿠폰|예산|총액|비용|추가 ?결제", "discount coupon budget price pay paid total payment"),
    "benefit":     _k(r"혜택|멤버십|회원권|쿠폰|콜키지|이용권|투숙객 할인", "benefit membership corkage redeem coupon gift"),
    "rest_need":   _k(r"휴식|피곤|피로|숙면|쉬었|쉬며|쉬는", "tired fatigue rest sleep humidity"),
    "space":       _k(r"산책|자연|숲|단풍|정원|포레스트|뷰|전망", "forest garden view nature walk"),
    "routine":     _k(r"재방문|반복|여러 차례|연속|익숙", "repeat revisit annual return"),
}
FACET_RX = {
    "active":            _k(r"수영|러닝|운동|피트니스|요가|바레", "swim run running gym fitness yoga barre activity"),
    "warm_rest":         _k(r"스파|사우나|온천|자쿠지|족욕", "spa sauna jacuzzi onsen wellness"),
    "alcohol_familiar":  _k(r"와인|주류|럭스바|콜키지", "wine winefair corkage"),
    "novelty":           _k(r"처음|새로운|호기심|체험", "first trial novelty new"),
    "premium":           _k(r"오마카세|파인 ?다이닝|스위트|프리미엄", "fine omakase suite premium"),
    "food_specific":     _k(r"메뉴|사전선택|주문", "menu preorder order"),
    "practical_alt":     _k(r"대안|대신|포장|픽업|전환", "alternative alt takeout pickup vs"),
    "breakfast_priority": _k(r"조식|아침 식사", "breakfast"),
}
NEG_RX = r"안 ?했|못 ?했|하지 않|않았|않음|취소|생략|포기|실패|\bcancel\b|\bskip\b|\bfail\b|\bdecline\b"
# 동행(방문별 맥락) — 후보로만 쓰고 확정하지 않는다(사실 ID 를 함께 남김)
PARTY_RX = [("family_kids", _k(r"자녀|아이|아기|키즈|돌잔치|두 돌", "kids kid child baby dol")),
            ("family_parents", _k(r"부모|어머니|아버지|할머니|모친|부친|효도|3대|칠순|환갑", "mother father threegen 70th mom")),
            ("couple", _k(r"남편|아내|부부|커플|연인", "husband wife couple date")),
            ("friends", _k(r"친구", "friend friends")),
            ("solo", _k(r"혼자", "solo"))]
PARTY_N = {"family_kids": 3, "family_parents": 3, "couple": 2, "friends": 3, "solo": 1}


def roots():
    v = os.environ.get(ENV) or ""
    return [Path(p) for p in v.split(os.pathsep) if p.strip()]


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _find(pid):
    for r in roots():
        if not r.is_dir():
            continue
        for cand in list(r.glob(f"profiles/{pid}/structured_profile.json")) + list(r.glob(f"*/profiles/{pid}/structured_profile.json")) + list(r.glob(f"*/*/profiles/{pid}/structured_profile.json")):
            return cand.parent.parent.parent, cand.parent
    return None, None


def _checksums(pkg):
    out = {}
    f = pkg / "checksums.sha256"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                out[parts[1].strip().lstrip("*")] = parts[0]
    return out


def load(pid):
    """→ (raw | None, status). status 는 응답에 그대로 실어도 되는 정보만 담는다(경로는 패키지 이름까지만)."""
    st = {"profile_id": pid, "qa_profile_root_set": bool(roots()), "profile_loaded": False, "daily_behavior_loaded": False,
          "profile_version": None, "package": None, "structured_sha256": None, "daily_sha256": None, "sha_verified": False,
          "daily_missing_reason": None, "load_error": None, "mapping_version": MAPPING_VERSION,
          "data_approval": APPROVAL, "data_hold": HOLD.get(pid)}
    if not roots():
        st["load_error"] = f"{ENV} 미설정 — QA 프로파일을 읽지 않음"
        return None, st
    pkg, d = _find(pid)
    if not d:
        st["load_error"] = "QA 프로파일 패키지에 이 ID 없음"
        return None, st
    st["package"] = pkg.name
    sums = _checksums(pkg)
    sp_f = d / "structured_profile.json"
    rel = f"profiles/{pid}/structured_profile.json"
    st["structured_sha256"] = _sha(sp_f)
    if sums.get(rel) != st["structured_sha256"]:
        st["load_error"] = "structured_profile SHA 불일치 또는 checksums 누락 — 로드 거부"
        return None, st
    try:
        sp = json.loads(sp_f.read_text(encoding="utf-8"))
    except Exception as e:
        st["load_error"] = f"structured_profile 파싱 실패 {type(e).__name__}"
        return None, st
    if (sp.get("STRUCTURED_PROFILE") or {}).get("persona_id") != pid:
        st["load_error"] = "structured_profile 의 persona_id 가 요청 ID 와 다름 — 로드 거부"
        return None, st
    st["profile_loaded"] = True
    st["sha_verified"] = True
    daily = None
    df = d / "daily_behavior_profile.json"
    drel = f"profiles/{pid}/daily_behavior_profile.json"
    if not df.exists():
        st["daily_missing_reason"] = "패키지에 daily_behavior_profile.json 없음(이 판본은 일상 행동 자료 미포함) — 축소 모드: 사실 · 성향 · 규칙만 사용"
    else:
        st["daily_sha256"] = _sha(df)
        if sums.get(drel) != st["daily_sha256"]:
            st["daily_missing_reason"] = "daily_behavior_profile SHA 불일치 — 사용하지 않음(축소 모드)"
            st["sha_verified"] = False
        else:
            try:
                daily = json.loads(df.read_text(encoding="utf-8"))
                if daily.get("persona_id") != pid:
                    st["daily_missing_reason"] = "daily persona_id 불일치 — 사용하지 않음"; daily = None
                else:
                    st["daily_behavior_loaded"] = True
                    st["profile_version"] = daily.get("version")
            except Exception as e:
                st["daily_missing_reason"] = f"daily 파싱 실패 {type(e).__name__}"
    return {"sp": sp, "daily": daily}, st


def _level(n_main, n_other):
    """근거 개수 → 0~1 수준(QA 매핑 · 고정식). 워커힐 사실 1개 0.35, 이후 0.15씩, 다른 곳 경험은 절반."""
    x = n_main + 0.5 * n_other
    return 0.0 if x <= 0 else min(1.0, 0.35 + 0.15 * (x - 1))


def to_planner(pid, raw, st):
    """QA 원자료 → stay_planner 가 쓰는 P(같은 키) + qa(추적 정보). 원문 인용은 넣지 않는다."""
    sp, daily = raw["sp"], raw.get("daily")
    facts_all = (sp.get("STRUCTURED_PROFILE") or {}).get("facts") or []
    blocked, facts = [], []
    for f in facts_all:
        if f.get("kind") == "participation" and f.get("action_stage") in (None, "", "not_applicable"):
            blocked.append(f.get("fact_id"))   # Codex 계약 participation_stage_required — 원 데이터 생산자 확인 전 사용 안 함
            continue
        facts.append(f)
    def ftxt(f): return f"{f.get('detail', '')} {str(f.get('feature_key', '')).replace('_', ' ')}"
    def fneg(f): return f.get("kind") == "decline" or f.get("polarity") == "negative" or re.search(NEG_RX, ftxt(f))
    trait_ev = {}
    for key, rx in list(TRAIT_RX.items()) + list(FACET_RX.items()):
        main, other = [], []
        for f in facts:
            if fneg(f) and key not in ("practical_alt", "rest_need"):
                continue
            if re.search(rx, ftxt(f), re.I):
                (main if f.get("scope") == "walkerhill_property" else other).append(f["fact_id"])
        trait_ev[key] = {"level": round(_level(len(main), len(other)), 2), "walkerhill": main, "other": other}
    bars = {k: trait_ev[k]["level"] for k in TRAIT_RX}
    facets = {k: trait_ev[k]["level"] for k in FACET_RX}
    for k in ("swim_aversion", "alcohol_limit", "promo"):
        facets[k] = 0.0
    # 일상 슬롯 — 관찰 요약(observed)과 LLM 가설(hypothesis)을 분리해서 계획기에 준다
    slots = {}
    for k in DAILY_SLOTS:
        v = ((daily or {}).get("daily_behavior") or {}).get(k)
        if not v:
            continue
        obs = v.get("observed_summary") or ""
        observed = bool(v.get("observed_fact_ids")) and "직접 확인된 관측 없음" not in obs
        slots[k] = {"label": v.get("label"), "observed": observed, "observed_fact_ids": [i for i in (v.get("observed_fact_ids") or []) if i not in blocked],
                    "observed_summary": obs if observed else "", "hypothesis": v.get("plausible_llm_continuation") or "",
                    "hypothesis_status": v.get("hypothesis_status"), "possible_action": v.get("possible_action")}
    # 동행 후보(방문별 맥락) — 사실 ID 를 근거로 남기고, 하나로 확정하지 않는다
    party = {}
    for f in facts:
        for rel, rx in PARTY_RX:
            if re.search(rx, ftxt(f), re.I):
                party.setdefault(rel, []).append(f["fact_id"])
    P = {
        "id": pid, "type": "", "party_src": None, "bars": bars, "facets": facets,
        "facts": [{"id": f["fact_id"], "gist": f.get("detail", ""), "feat": f.get("feature_key", ""), "kind": f.get("kind"),
                   "scope": f.get("scope")} for f in facts if f.get("scope") == "walkerhill_property"],
        "facts_other": [{"id": f["fact_id"], "gist": f.get("detail", ""), "feat": f.get("feature_key", ""), "kind": f.get("kind")} for f in facts if f.get("scope") != "walkerhill_property"],
        "vfs": {}, "traits_src": [{"trait_id": t.get("trait_id"), "trait": t.get("trait"), "evidence_ids": t.get("evidence_ids") or []} for t in sp.get("TRAIT_TABLE") or []],
        "rules_src": [{"rule_id": r.get("rule_id"), "evidence_ids": r.get("evidence_ids") or [], "status": r.get("validation_status")} for r in sp.get("CONTEXT_RULES") or []],
        "daily": slots, "party_candidates": party, "qa": True,
    }
    P["n_wh"] = len(P["facts"])
    qa = {"trait_evidence": trait_ev, "blocked_facts": blocked, "daily_slots_observed": [k for k, v in slots.items() if v["observed"]],
          "daily_slots_hypothesis_only": [k for k, v in slots.items() if not v["observed"]], "party_candidates": party,
          "facts_walkerhill": P["n_wh"], "facts_other": len(P["facts_other"]), "traits": len(P["traits_src"]), "rules": len(P["rules_src"])}
    return P, qa


def party_for_visit(P, seed):
    """방문별 동행 — 후보 중 근거 수에 비례해 시드로 고른다(후기의 과거 동행을 그대로 복사하지 않음 · 근거 ID 표시)."""
    import random
    c = P.get("party_candidates") or {}
    if not c:
        return None
    rng = random.Random(f"qa-party|{P['id']}|{seed}")
    items = sorted(c)
    tot = sum(len(c[k]) for k in items)
    r = rng.random() * tot
    acc = 0
    for k in items:
        acc += len(c[k])
        if acc >= r:
            return {"n": PARTY_N[k], "rel": k, "kids": k == "family_kids", "elder": k == "family_parents", "basis": c[k][:4], "layer": "review"}
    return None
