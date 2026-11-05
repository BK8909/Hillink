"""작성자 통합 프로필 → 행동 엔진이 읽는 고객 특성(AgentTraits) (10/22 2차 · 총괄 C · 격리 연구)

입력
- V4.1 JSON: `author_method_v4_1_artifacts/profiles_and_quality.json` 의 `authors[<id>].scope_profiles[<scope>]`
- 경수 수동 파일럿 JSON: `manual_profiles/<id>_textfirst_profile_pilot.json`

2차 변경(1차 검수 반영): V4.1 패턴 묶음을 그대로 쓰지 않고, 근거(특성 키)마다 `relevance.EVIDENCE` 의
대표/약한/제외 등급과 선택지 속성 태그를 붙인다. 성향 수준은 '태그가 맞는 근거의 질량'에서 선택 시점에 계산한다(engine.ev).
원본 프로파일의 관측 사실은 그대로 보존하고, 여기서는 연결만 바꾼다.

수준 = min(1, 맞는 근거 질량 / MASS_FULL) × 범위 이전 0.8 — 확률이 아니며 작성자 간 절대 비교에 쓰지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from .gists import gist, PATTERN_KO
from .relevance import EVIDENCE, GRADE_WEIGHT, MANUAL_TRAITS, R, W, X
from . import auto_link as AL

HERE = Path(__file__).resolve().parent
PROFILES_PATH = HERE.parent / "author_method_v4_1_artifacts" / "profiles_and_quality.json"
MANUAL_DIR = HERE / "manual_profiles"

MASS_FULL = 6.4            # 가정 — 대표 근거 4건(V4.1 근거 질량 1.6 × 4)이면 수준 상한
SCOPE_TRANSFER = 0.8       # 가정 — '특정 상품 · 보고된 방문' 범위의 성향을 새 상황에 옮길 때 일괄 할인
MANUAL_MULT = 0.8          # 가정 — 사람 수동 5점 척도(검수 전)를 상한 1.0 에 맞추되 자동 추출 아님을 반영

FACETS = {
    "novelty": +1, "seasonal": +1, "promo": +1, "food": +1, "food_specific": +1, "premium": +1, "benefit": +1, "value_check": 0,
    "space": +1, "warm_rest": +1, "swim_aversion": -1, "active": +1, "rest_need": +1, "routine": +1, "practical_alt": +1,
    "alcohol_familiar": +1, "alcohol_limit": -1, "breakfast_priority": 0, "post_appraisal": 0,
}
FACET_KO = {"novelty": "새 경험 시도", "seasonal": "시즌 행사 · 한정 반응", "promo": "홍보를 보고 움직임", "food": "음식 경험", "food_specific": "구체적 음식 기호",
            "premium": "프리미엄 식음", "benefit": "혜택 활용", "value_check": "구매 전 가치 비교", "space": "공간 · 전망 · 분위기", "warm_rest": "온수 · 족욕 휴식",
            "swim_aversion": "수영 비선호", "active": "운동 참여", "rest_need": "휴식 · 회복", "routine": "익숙한 곳 재방문", "practical_alt": "실용적 식사 대안",
            "alcohol_familiar": "와인 · 주류 경험", "alcohol_limit": "낮은 음주 내성", "breakfast_priority": "조식 우선", "post_appraisal": "이용 후 가치 평가"}

# 특성 키 → 메뉴 태그 (손 연결 · 개발 표본)
MENU_FEATURES = {
    "pizza_garlic_preference": (["pizza", "garlic", "olive_oil"], 1.0),
    "two_flavors_and_sauces": (["pizza"], 0.4),
    "matcha_egg_tart_preference": (["matcha", "egg_tart"], 1.0),
    "signature_drink_curiosity": (["signature_drink"], 0.5),
    "shellfish_preference_exceptions": (["shellfish"], -0.5),
    "wine_and_friend_trip": (["wine"], 0.3),
    "bar_ambience_and_nonalcoholic": (["nonalcoholic"], 0.4),
}
# 특성 키 → 시설/업장 실제 이용 경험. kind: used · appraisal(이용 후 평가 −) · avoid_swim
VENUE_FEATURES = {
    "night_view_footbath": ("SKYARD", "used"), "day_night_footbath": ("SKYARD", "used"),
    "gym_shoe_rental": ("FITNESS", "used"), "lounge_food_then_gym": ("FITNESS", "used"),
    "warm_shallow_pool": ("POOL", "used"), "pool_visit_not_swimming": ("POOL", "avoid_swim"),
    "forest_shuttle_walk": ("FOREST", "used"),
    "meal_discount_applied": ("PIZZA_HILL", "used"), "two_flavors_and_sauces": ("PIZZA_HILL", "used"), "pizza_value_qualified": ("PIZZA_HILL", "appraisal"),
    "buffet_food_exploration": ("THE_BUFFET", "used"), "buffet_voucher_value": ("THE_BUFFET", "appraisal"),
    "bakery_guest_discount": ("LE_PASSAGE", "used"), "room_external_food": ("ROOM_MEAL", "used"),
    "early_breakfast_routine": ("BREAKFAST", "used"), "breakfast_coupon_used": ("BREAKFAST", "used"),
}


def _empty_facets():
    return {f: dict(direction=d, present=False, evidence=[], level_all=0.0, fact_ids=[], features=[], label=FACET_KO[f], opposing_count=0,
                    conditional_on=None, unmapped=[]) for f, d in FACETS.items()}


def _finish(facets):
    for f, x in facets.items():
        inc = [e for e in x["evidence"] if e["grade"] != X]
        x["present"] = bool(inc)
        x["fact_ids"] = [e["fact_id"] for e in inc]
        x["features"] = sorted({e["feature"] for e in inc})
        x["level_all"] = round(min(1.0, sum(e["mass"] * GRADE_WEIGHT[e["grade"]] for e in inc) / MASS_FULL) * SCOPE_TRANSFER, 4)
        x["level"] = x["level_all"]
    return facets


def load_profile(persona_id: str, scope: str = "recent_added", path: Path | None = None) -> dict:
    data = json.loads((path or PROFILES_PATH).read_text(encoding="utf-8"))
    return data["authors"][persona_id]["scope_profiles"][scope]


def build_traits(profile: dict, linker: str = "hand") -> dict:
    """V4.1 프로필 → AgentTraits. 근거는 individual_features 단위로 연결한다.
    linker="hand": relevance.py 손 연결표(3명 검수 사례) · linker="auto": auto_link 공통 규칙(새 작성자와 같은 방식)."""
    patterns = profile.get("patterns", {})
    features = profile.get("individual_features", {})
    # fact → 질량(패턴 기여에서 · 여러 패턴이면 최대) · fact → 특성 키
    mass: dict[str, float] = {}
    for p in patterns.values():
        for c in p.get("contributions", []):
            per = c["evidence_mass"] / max(1, len(c["fact_ids"]))
            for f in c["fact_ids"]:
                mass[f] = max(mass.get(f, 0.0), per)
    facets = _empty_facets()
    evidence_index = {}
    audit = []      # 연결 감사: 특성 키 · V4.1 패턴에서의 소속 · 이번 연결 · 등급
    pattern_of = {}
    for pname, p in patterns.items():
        for c in p.get("contributions", []):
            for f in c["fact_ids"]:
                pattern_of.setdefault(f, []).append(pname)
    for key, feat in features.items():
        fids = sorted({f for c in feat.get("contributions", []) for f in c["fact_ids"]})
        posts = sorted({pp for c in feat.get("contributions", []) for pp in c.get("post_ids", [])})
        for f in fids:
            evidence_index[f] = dict(fact_id=f, features=[key], gist=gist(key), posts=posts)
        links = EVIDENCE.get(key) if linker == "hand" else AL.link_fact(dict(feature_key=key, detail=gist(key)))["links"]
        if links is None:
            audit.append(dict(feature=key, fact_ids=fids, v41_patterns=sorted({q for f in fids for q in pattern_of.get(f, [])}), linked="미연결(표에 없음 · 기여 0)"))
            continue
        for facet, (grade, tags) in links.items():
            for f in fids:
                facets[facet]["evidence"].append(dict(fact_id=f, feature=key, grade=grade, tags=list(tags), mass=round(mass.get(f, 1.6), 4), gist=gist(key)))
        audit.append(dict(feature=key, fact_ids=fids, v41_patterns=sorted({q for f in fids for q in pattern_of.get(f, [])}),
                          linked={fc: (g, t) for fc, (g, t) in links.items()}))
    opposing = {}
    for pname, p in patterns.items():
        opposing[pname] = len(p.get("opposing_or_qualified_facts") or [])
    PATTERN_TO_FACET = {"novelty_trial": "novelty", "seasonal_promotion_response": "seasonal", "voluntary_ad_response": "promo", "food_exploration": "food",
                        "food_specificity": "food_specific", "premium_experience": "premium", "benefit_use": "benefit", "prepurchase_value": "value_check",
                        "space_atmosphere": "space", "warm_water_rest": "warm_rest", "swimming_nonpreference": "swim_aversion", "active_engagement": "active",
                        "recovery_service": "rest_need", "trip_rest_context": "rest_need", "practical_repeat_use": "routine", "practical_alternative": "practical_alt",
                        "alcohol_experience": "alcohol_familiar", "low_alcohol_tolerance": "alcohol_limit", "breakfast_priority": "breakfast_priority",
                        "post_value_appraisal": "post_appraisal"}
    for pname, n in opposing.items():
        if pname in PATTERN_TO_FACET:
            facets[PATTERN_TO_FACET[pname]]["opposing_count"] += n
    _finish(facets)
    menu = [dict(feature=k, tags=t, weight=w, fact_ids=sorted({f for c in features[k]["contributions"] for f in c["fact_ids"]}), gist=gist(k))
            for k, (t, w) in MENU_FEATURES.items() if k in features]
    venues = {}
    for key, (venue, kind) in VENUE_FEATURES.items():
        if key in features:
            venues.setdefault(venue, []).append(dict(feature=key, kind=kind, fact_ids=sorted({f for c in features[key]["contributions"] for f in c["fact_ids"]}), gist=gist(key)))
    return dict(
        persona_id=profile.get("persona_id"), profile_version=profile.get("version"), evidence_granularity="fact", linker=linker,
        profile_status="V4.1 개발 · 원문 대조 잠정 프로파일(독립 자동 추출 성능 미확인 · 검수 전)",
        source_post_count=profile.get("source_post_count"), active_fact_count=profile.get("active_fact_count"),
        facets=facets, menu=menu, venues=venues, evidence_index=evidence_index, relevance_audit=audit,
        assumptions=[f"성향 수준 = min(1, 선택지 속성과 맞는 근거 질량 / {MASS_FULL}) × 범위 이전 {SCOPE_TRANSFER}(가정) · 약한 근거는 ×0.5 · 제외 근거는 0",
                     "근거 등급 · 태그는 relevance.py 의 손 연결표(검수 대상) · 원본 프로파일 사실은 보존",
                     "메뉴 태그 · 시설 이용 연결은 손 연결표(자동 추출 아님)",
                     "이용 후 가격 가치 평가는 같은 업장 재선택에만 쓰고 새 행사의 구매 전 가격 계수로 쓰지 않음"],
        human_review="pending", demo_approved=False)


def convert_pilot_json(doc: dict) -> dict:
    traits = []
    for t in doc["traits"]:
        traits.append(dict(key=t["key"], label=t["label"], strength=float(t["score"]), links=MANUAL_TRAITS.get(t["key"], {}),
                           fact_ids=list(t["evidence_ids"]), gist=t.get("basis", ""), rule=t.get("rule", "")))
    venues = [dict(feature="douglas_quiet_stay", venue="ROOM", kind="used", fact_ids=["B43-P02"], gist="더글라스 숙박에서 라운지 · 객실 휴식에 집중"),
              dict(feature="buffet_wait_switch", venue="THE_BUFFET", kind="used", fact_ids=["B43-P02"], gist="더뷔페 조식 긴 대기 → 라운지 조식으로 전환")]
    return dict(version=doc.get("version"), persona_id=doc["profile_id"],
                source=f"경수 {doc.get('version')} · {doc['source_scope'].get('unique_posts')}편 · 사진 수집 {doc['source_scope'].get('image_collection')}",
                status=doc.get("study_status"), source_post_count=doc["source_scope"].get("unique_posts"), traits=traits, venues=venues,
                counterexamples=[doc.get("primary_context", ""), "평소 활동성과 특정 방문의 휴식 선택을 동일시하지 않음"],
                scenario_rules=doc.get("scenario_rules", []), core=doc.get("core"),
                menu={"food_specific_preferences": (["pasta", "korean", "variety", "seafood"], 0.6)})


def build_traits_manual(doc: dict) -> dict:
    """사람 수동 파일럿 프로필(5점 척도 · 근거 ID 표) → 같은 AgentTraits. 강도는 특성 단위이며 근거 수에 비례시키지 않는다."""
    facets = _empty_facets()
    evidence_index = {}
    menu = []
    audit = []
    for tr in doc["traits"]:
        level_target = min(1.0, tr["strength"] / 5.0) * MANUAL_MULT          # 범위 이전은 _finish 에서 곱함
        total_mass = level_target * MASS_FULL
        per = total_mass / max(1, len(tr["fact_ids"]))
        for f in tr["fact_ids"]:
            e = evidence_index.setdefault(f, dict(fact_id=f, features=[], gist="", posts=[f]))
            if tr["key"] not in e["features"]:
                e["features"].append(tr["key"])
        for facet, (grade, tags) in tr["links"].items():
            for f in tr["fact_ids"]:
                facets[facet]["evidence"].append(dict(fact_id=f, feature=tr["key"], grade=grade, tags=list(tags), mass=round(per, 4), gist=tr["gist"]))
            if tr["key"] == "quiet_rest_context":
                facets[facet]["conditional_on"] = "visit.purpose == rest"
        audit.append(dict(feature=tr["key"], fact_ids=tr["fact_ids"], manual_strength=tr["strength"], linked={fc: (g, t) for fc, (g, t) in tr["links"].items()}, rule=tr.get("rule")))
        if tr["key"] in doc.get("menu", {}):
            tags, w = doc["menu"][tr["key"]]
            menu.append(dict(feature=tr["key"], tags=tags, weight=w, fact_ids=tr["fact_ids"], gist=tr["gist"]))
    gist_by_key = {tr["key"]: tr["gist"] for tr in doc["traits"]}
    for e in evidence_index.values():
        e["gist"] = " / ".join(gist_by_key.get(k, k) for k in e["features"])
    _finish(facets)
    venues = {}
    for v in doc.get("venues", []):
        venues.setdefault(v["venue"], []).append(dict(feature=v["feature"], kind=v["kind"], fact_ids=v["fact_ids"], gist=v["gist"]))
        for f in v["fact_ids"]:
            evidence_index.setdefault(f, dict(fact_id=f, features=[v["feature"]], gist=v["gist"], posts=[f]))
    return dict(persona_id=doc["persona_id"], profile_version=doc["version"], evidence_granularity="post",
                profile_status="경수 수동 파일럿(텍스트 중심 · GPT 보조) · 자동 추출 아님 · 검수 전",
                source_post_count=doc.get("source_post_count"), active_fact_count=len(evidence_index),
                facets=facets, menu=menu, venues=venues, evidence_index=evidence_index, relevance_audit=audit,
                assumptions=[f"수동 5점 척도 → 수준 = 강도/5 × {MANUAL_MULT} × 범위 이전 {SCOPE_TRANSFER}(가정) · 근거 수에 비례시키지 않음",
                             "V4.2 독립 자동 추출 결과가 아님 · 사람 공식 검수 전", doc.get("status", "")],
                counterexamples=doc.get("counterexamples", []), scenario_rules=doc.get("scenario_rules", []), source=doc.get("source"),
                human_review="pending", demo_approved=False)


CONF_MASS = {"high": 1.6, "medium": 1.28, "low": 0.8}     # 가정 — V4.1 근거 질량 1.6 을 기준으로 확신 등급별


def build_traits_v42(team: dict) -> dict:
    """V4.2 팀 공통 프롬프트 출력(8개 섹션) → AgentTraits. 사실 단위(STRUCTURED_PROFILE.facts)를 auto_link 로 자동 연결한다.
    같은 experience_key 의 사실은 한 경험으로 묶어 질량을 나눈다(같은 숙박 · 같은 구매를 여러 번 세지 않음)."""
    sp = team["STRUCTURED_PROFILE"]
    facts = sp["facts"]
    by_exp: dict[str, int] = {}
    for f in facts:
        by_exp[f.get("experience_key") or f["fact_id"]] = by_exp.get(f.get("experience_key") or f["fact_id"], 0) + 1
    facets = _empty_facets()
    evidence_index, audit, menu = {}, [], []
    for f in facts:
        text = f"{f.get('feature_key', '')} {f.get('detail', '')}"
        res = AL.link_fact(f)
        mass = CONF_MASS.get(f.get("confidence"), 1.28) / by_exp[f.get("experience_key") or f["fact_id"]]
        gist_txt = f.get("detail") or f.get("feature_key")
        evidence_index[f["fact_id"]] = dict(fact_id=f["fact_id"], features=[f.get("feature_key")], gist=gist_txt, posts=[f.get("post_id")])
        for facet, (grade, tags) in res["links"].items():
            facets[facet]["evidence"].append(dict(fact_id=f["fact_id"], feature=f.get("feature_key"), grade=grade, tags=list(tags), mass=round(mass, 4), gist=gist_txt))
        audit.append(dict(feature=f.get("feature_key"), fact_ids=[f["fact_id"]], linked={k: v for k, v in res["links"].items()}, rules=res["rules"]))
        if "food_specific" in res["links"] and res["links"]["food_specific"][0] != X:
            tags = AL.menu_tags(text)
            if tags:
                w = -0.5 if f.get("polarity") == "negative" else 1.0
                menu.append(dict(feature=f.get("feature_key"), tags=tags, weight=w, fact_ids=[f["fact_id"]], gist=gist_txt))
    _finish(facets)
    return dict(persona_id=sp.get("persona_id") or team.get("SOURCE_AUDIT", {}).get("author_id"), profile_version="team_v4.2_import",
                evidence_granularity="fact", linker="auto", profile_status="V4.2 팀 공통 프롬프트 출력 · 자동 연결 · 검수 전",
                source_post_count=len({f.get("post_id") for f in facts}), active_fact_count=len(facts),
                facets=facets, menu=menu, venues={}, evidence_index=evidence_index, relevance_audit=audit,
                assumptions=["사실 → 성향 연결은 auto_link 공통 규칙(손 연결표 아님)", "같은 experience_key 의 사실은 질량을 나눔", "확신 등급별 질량 high 1.6 · medium 1.28 · low 0.8(가정)"],
                human_review="pending", demo_approved=False)


def traits_for(persona_id: str, scope: str = "recent_added", path: Path | None = None, linker: str = "hand") -> dict:
    data = json.loads((path or PROFILES_PATH).read_text(encoding="utf-8"))
    if persona_id in data["authors"]:
        return build_traits(data["authors"][persona_id]["scope_profiles"][scope], linker=linker)
    pilot = MANUAL_DIR / f"{persona_id}_textfirst_profile_pilot.json"
    if pilot.exists():
        return build_traits_manual(convert_pilot_json(json.loads(pilot.read_text(encoding="utf-8"))))
    raise KeyError(f"no profile for {persona_id}")
