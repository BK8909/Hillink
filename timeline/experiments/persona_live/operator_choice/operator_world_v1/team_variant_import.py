"""PR #94(한호 · 10/22) 팀 변형 JSON → V4.2 사실(fact) 변환 (6차 · V1 동결 파일은 수정하지 않는 별도 모듈)

팀 변형 구조: EVENT_ACTIONS[event_id · feature_key · visit_group · stage(한국어) · detail · evidence_ids]
             + EVIDENCE_MAP[claim_id · event_id · post_id · line_start · line_end · evidence_kind[] · claim]
             + STRUCTURED_PROFILE(메타 정보 · facts[] 없음)
V4.2 계약: STRUCTURED_PROFILE.facts[] (post_id · fact_id · experience_key · feature_key · detail · anchors[{span, quote}] · kind · dimension · actor ·
          time_scope · action_stage · polarity · confidence · common_dimensions) · experience_links[]

변환 원칙
- 그대로 옮김(무손실): post_id · fact_id(=event_id) · experience_key(=visit_group) · feature_key · detail · 줄 범위(span)
- 규칙으로 도출(손실 · 표시함): kind · dimension · time_scope · action_stage · polarity · confidence — 근거는 stage 문구와 evidence_kind 뿐
- 만들 수 없음: anchors.quote(원문 인용) — 원문이 없으므로 비워 두고 '원문 재대조 필요'로 표시. 따라서 변환본은 V4.2 계약 검사를 통과하지 못함(정상)
- actor: 팀 문서가 모두 '작성자 보고'로 기록 → author. 동행의 행동을 작성자가 보고한 것도 author(작성자 관찰)로 둠
"""
from __future__ import annotations

import re

DERIVED_FIELDS = ("kind", "dimension", "time_scope", "action_stage", "polarity", "confidence")


def _kind_dim(stage: str, ek: set[str]) -> tuple[str, str]:
    s = stage
    # 이용 뒤 평가 · 재방문 거부는 의향 문구가 섞여 있어도 '이용 후 평가'(실제 경험의 결론) — 미래 의향으로 빼면 '다시 안 간다'가 사라짐
    if re.search(r"재방문거부|거부의향|부정평가", s):
        return "appraisal", "post_appraisal"
    if "의향·추천" in " ".join(ek) or re.search(r"추천|미래|의향|계획", s) and not re.search(r"실제|이용|참여|식사|섭취|구매", s):
        return "expectation", "new_experience_trial"
    if re.search(r"예약불가.*(워크인|입장)|워크인", s):
        return "participation", "participation_history"          # 예약은 실패했지만 현장 대기로 실제 입장 — 포기가 아님(6차 검수)
    if re.search(r"구매하지않음|이용하지않음|숙박하지않음|미실행|접근실패|예약불가", s):
        return "decline", "participation_history"
    if re.search(r"재방문|재이용", s):
        return "revisit", "revisit_expression"
    if re.search(r"혜택|결제|선결제|구매", s):
        return "purchase", "participation_history"
    if re.search(r"선호명시|선호", s):
        return "preference", "specific_preference"
    if re.search(r"비교", s):
        return "comparison", "participation_history"
    if re.search(r"동기", s):
        return "motive", "participation_history"
    if re.fullmatch(r"(가격평가|서비스평가|메뉴별사후평가|평가|종합평가/재방문거부의향|사후평가/의향)", s):
        return "appraisal", "post_appraisal"
    return "participation", "participation_history"


def _time_scope(stage: str, ek: set[str]) -> str:
    if "작성자 과거 회상" in ek or re.search(r"과거", stage):
        return "historical"
    if "작성자 의향·추천" in ek and not ({"작성자 행동·동기 보고", "작성자 평가"} & ek):
        return "recommended" if "추천" in stage else "future"
    if "작성자 의향·추천" in ek:
        return "mixed"
    return "source_experience"


def _action_stage(stage: str) -> str:
    if re.search(r"예약", stage):
        return "reservation_reported"
    if re.search(r"주문|포장|배달", stage):
        return "order_reported"
    if re.search(r"구매|결제", stage):
        return "purchase_reported"
    if re.search(r"식사|섭취|음료", stage):
        return "consumption_reported"
    if re.search(r"참여|이용|입장|숙박|방문|산책|관람|이동", stage):
        return "participation_reported"
    return "not_applicable"


NEG = r"아쉽|불편|낮|않겠|않았|실망|덥다|비싸|아깝|부족|별로|거부"
POS = r"좋|만족|선호|인정|높게|즐|추천"


def _polarity(detail: str) -> str:
    n, p = bool(re.search(NEG, detail)), bool(re.search(POS, detail))
    return "mixed" if n and p else ("negative" if n else ("positive" if p else "neutral"))


ACTIVITY_ALIAS = {"indoor": "pool", "pool": "pool", "swim": "pool", "yoga": "yoga", "mindcare": "yoga", "phytoncide": "yoga", "program": "yoga",
                  "pizzahill": "pizzahill", "riverpark": "riverpark", "breakfast": "breakfast", "roomservice": "roomservice"}


def activity_unit(feature_key: str) -> str:
    """7차: 같은 숙박 안에서 '같은 활동 · 같은 선택'을 한 경험으로 — 특성 키의 첫 토막(+ 같은 활동의 다른 이름 묶음).
    예: pizzahill_access · meal · taste · payment · view · revisit → 피자힐 방문 1회 / mindcare_yoga · phytoncide_yoga · yoga_choice · program_* → 요가 1회.
    (규칙 기반 근사 — 검수표에 단위별로 보여 주고 사람이 고친다)"""
    head = re.split(r"[_\-\s]", feature_key or "x")[0].lower()
    if feature_key and "yoga" in feature_key.lower():
        return "yoga"
    return ACTIVITY_ALIAS.get(head, head)


def _line(x):
    """'L0013' → 13 (무손실 형식 변환) · 해석 불가면 None"""
    m = re.fullmatch(r"L?0*(\d+)", str(x or ""))
    return int(m.group(1)) if m else None


def convert(doc: dict) -> tuple[dict, dict]:
    """팀 변형 → (V4.2 모양 문서, 변환 보고). 원 문서는 수정하지 않는다."""
    ev_by = {}
    for c in doc.get("EVIDENCE_MAP", []):
        ev_by.setdefault(c["event_id"], []).append(c)
    facts, report = [], dict(n_events=0, lossless=["post_id", "fact_id", "feature_key", "detail", "anchors.span(줄 범위 · 'L0013' → 13)"],
                             derived=list(DERIVED_FIELDS) + ["experience_key(숙박 + 특성 키)"], missing=["anchors.quote(원문 인용)"], per_fact=[])
    for e in doc.get("EVENT_ACTIONS", []):
        report["n_events"] += 1
        evs = ev_by.get(e["event_id"], [])
        ek = {k for c in evs for k in c.get("evidence_kind", [])}
        kind, dim = _kind_dim(e.get("stage", ""), ek)
        posts = sorted({c["post_id"] for c in evs}) or ["UNKNOWN"]
        # 팀 변형의 visit_group 은 '같은 숙박' 묶음이고 V4.2 experience_key 는 '같은 경험(같은 구매 · 같은 활동)' 묶음이라 의미가 다름.
        # visit_group 을 그대로 쓰면 한 숙박의 사실 18개가 서로 질량을 1/18 로 나눠 성향이 사라짐 → 숙박 + 특성 키를 한 경험으로 봄(도출 · 표시)
        exp = f"{e.get('visit_group') or 'V'}__{activity_unit(e.get('feature_key') or e['event_id'])}".replace(" ", "_")
        f = dict(post_id=posts[0], fact_id=e["event_id"].replace(" ", "_"), experience_key=exp,
                 feature_key=e.get("feature_key") or "unknown", detail=e.get("detail", ""),
                 anchors=[dict(span=[_line(c.get("line_start")), _line(c.get("line_end"))], quote=None, post_id=c["post_id"]) for c in evs],
                 kind=kind, dimension=dim, actor="author", time_scope=_time_scope(e.get("stage", ""), ek), action_stage=_action_stage(e.get("stage", "")),
                 polarity=_polarity(e.get("detail", "")), confidence=("medium" if kind == "expectation" else "high"), common_dimensions=[],
                 _team_stage=e.get("stage"), _evidence_kind=sorted(ek), _all_posts=posts)
        facts.append(f)
        report["per_fact"].append(dict(fact_id=f["fact_id"], stage=e.get("stage"), evidence_kind=sorted(ek), kind=kind, dimension=dim,
                                       time_scope=f["time_scope"], action_stage=f["action_stage"], polarity=f["polarity"]))
    meta = doc.get("STRUCTURED_PROFILE", {})
    pid = meta.get("AUTHOR_ID") or doc.get("SOURCE_AUDIT", {}).get("AUTHOR_ID")
    out = {k: v for k, v in doc.items() if k != "STRUCTURED_PROFILE"}
    out["STRUCTURED_PROFILE"] = dict(persona_id=pid, facts=facts, experience_links=[], _team_meta=meta,
                                     _conversion="PR #94 팀 변형 → V4.2 모양 · 계약 미완(anchors.quote 없음) · 원문 재대조 필요")
    return out, report
