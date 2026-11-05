"""근거 층 · 후속 질문 맥락 — 격리 변형 (10/21 · 사람 검수 반영 P0-B · 총괄 C · 모델 호출 없음)

기본 경로(persona_sheet.build_sheet · ask.SYSTEM · branching.followup)는 바꾸지 않는다. 여기 있는 것은 모두 옵트인이다.
승인 전에는 이 변형으로 모델을 부르지 않는다(실험 목록 · 비용은 review/EVIDENCE_CONTEXT_P0B_1021.md).

고치려는 것 (경수 PR #81 Q41-8 'A. 추론 활용, 기억 확정 표현 금지' · 한호 PR #83 판정기준 · RAG/LLM 감사)
  1. 평가자 의견 행 ID(PR73:* · H25 · H43)가 시트에 고객 근거 ID 처럼 나와 개인 기억으로 인용된다 → 시트에서 인용 가능한 ID 로 내지 않는다.
  2. 지난 방문의 예약 · 혜택 줄이 항목 출처와 관계없이 일괄 [관측] → 항목마다 provenance · status 를 적는다.
  3. 이용 사실이 곧 '좋아했다' 로 읽힌다 → 이용 사실 · 만족/불만 · 재선택 이유를 나눈다. 카드에 만족 기록이 없으면 '기록 없음' 으로 둔다.
  4. 시트에서 빠지던 order · session · polarity · source_verification 을 적는다.
  5. Q1/Q2 가 원래 결정의 이유 네 층 · 버린 대안(why_not)을 받지 못한다 → decision_context() 로 넘길 글을 만든다.

층 이름: observed(관측) · human_inference(사람 추론) · scenario_assumption(시나리오 가정) · unknown(미상) · evaluator_comment(평가자 의견 — 고객이 쓴 기록 아님)
"""
from __future__ import annotations

import re

from persona_sheet import COMP, CONSTRAINT, ENTITLE, KIND, MEAL, PLACE, PREF, PROV, PURPOSE, SCOPE, _season

EVAL_RE = re.compile(r"^(PR\d+:|H\d+$)")
LAYER_KO = {"observed": "관측", "human_inference": "사람 추론", "scenario_assumption": "시나리오 가정", "unknown": "미상", "evaluator_comment": "평가자 의견", "ai_estimate": "자동 추정", "mixed": "관측 · 추론 혼용"}
STATUS_KO = {"uncertain": "불확실", "confirmed": "확인", "used": "사용", "unused": "미사용", "unknown": "미상"}
POLARITY_KO = {"prefer": "선호", "avoid": "기피", "neutral": "중립"}
SAME_STAY_OK = {"confirmed", "confirmed_after_splitting_second_visit"}


def is_evaluator(i: str) -> bool:
    return bool(EVAL_RE.match(i))


def id_layers(card: dict) -> dict:
    """카드의 근거 ID → 층. 평가자 의견 행이면 evaluator_comment. 같은 카드 ID 가 관측 · 추론에 함께 쓰이면 mixed."""
    out: dict[str, set] = {}

    def walk(o, default=None):
        if isinstance(o, dict):
            if "evidence_ids" in o:
                prov = o.get("provenance") or default or "unknown"
                for i in o["evidence_ids"] or []:
                    out.setdefault(i, set()).add("evaluator_comment" if is_evaluator(i) else prov)
            for k, v in o.items(): walk(v, "observed" if k in ("observed_events", "explicit_preferences") else default)
        elif isinstance(o, list):
            for v in o: walk(v, default)
    walk(card["a_card"])
    return {i: (next(iter(s)) if len(s) == 1 else "mixed") for i, s in out.items()}


def _cite(x: dict) -> tuple[str, bool]:
    """인용 가능한 카드 ID 만 붙이고, 평가자 의견 행이 섞였는지 따로 돌려준다."""
    ids = [i for i in x.get("evidence_ids", []) or [] if (":" in i or i.startswith("H")) and not is_evaluator(i)]
    ev = any(is_evaluator(i) for i in x.get("evidence_ids", []) or [])
    return (f" (근거 {', '.join(ids)})" if ids else ""), ev


def _tag(x: dict, default: str = "unknown") -> str:
    """항목 출처. 고객 원문 ID 없이 평가자 의견 ID 만 있으면 카드 표기와 관계없이 평가자 의견으로 적는다."""
    ids = x.get("evidence_ids", []) or []
    if ids and all(is_evaluator(i) for i in ids):
        return f"[평가자 의견 — 고객 원문 근거 없음 · 카드 표기 {PROV.get(x.get('provenance'), x.get('provenance') or '없음')}]"
    prov = x.get("provenance") or default
    st = STATUS_KO.get(x.get("status"))
    return f"[{PROV.get(prov, LAYER_KO.get(prov, prov))}{' · ' + st if st and st != PROV.get(prov) else ''}]"


def build_sheet_v2(card: dict, sentiment: dict | None = None) -> dict:
    """persona_sheet.build_sheet 와 같은 내용을 층이 섞이지 않게 적은 시트(C2 변형).
    sentiment: {장소코드: {"polarity": positive|neutral|negative, "layer": observed|human_inference, "ids": [...]}} — 사람 검수를 거친 것만 넘긴다. 없으면 '기록 없음'."""
    a = card["a_card"]; L = []; ev_items = []

    def ref(x, what):
        s, ev = _cite(x)
        if ev: ev_items.append(what)
        return s
    comp, size = a["party"]["composition"], a["party"]["size"]
    party = comp.get("value")
    L.append(f"동행: {COMP.get(party, party or '미상')} {_tag(comp)}{ref(comp, '동행 구성')}"
             + (f" · {size['value']}명 {_tag(size)}{ref(size, '인원')}" if size.get("value") else ""))
    pu = a["purpose"]
    L.append(f"그때의 방문 목적: {' · '.join(PURPOSE.get(v, v) for v in pu.get('value') or []) or '미상'} {_tag(pu)}{ref(pu, '방문 목적')}")
    ov = a["observed_visit"]
    prop = {"GRAND": "그랜드 워커힐", "VISTA": "비스타 워커힐", "DOUGLAS": "더글라스 하우스"}.get(ov.get("property"), ov.get("property"))
    L.append(f"그때의 방문: {prop} · {ov.get('nights')}박 · {_season(ov['check_in'].get('value'))} {_tag(ov['check_in'])}"
             + (f" · 도착 {ov['check_in_time']['value']}쯤" if isinstance(ov['check_in_time'].get('value'), str) else ""))
    sv = a.get("source_verification") or {}
    if sv.get("same_stay_status") and sv["same_stay_status"] not in SAME_STAY_OK:
        L.append(f"[주의] 이 기억은 글 {sv.get('post_count', '여러')}편을 합친 것이며 같은 방문인지 확인 중이다({sv['same_stay_status']}). 다른 방문의 기억이 섞였을 수 있으니 하나의 방문 경험으로 단정하지 말 것.")
    if a["entitlements"]:
        L.append("그때 패키지에 포함돼 있던 것(지난 방문의 조건 — 이번 방문에는 적용되지 않음): " + " · ".join(
            f"{ENTITLE.get(e['item'], e['item'])}{(' ' + str(e['quantity']) + '인분') if e.get('quantity') else ''} {_tag(e)}{ref(e, '지난 혜택')}" for e in a["entitlements"]))
    if a["reservations"]:
        L.append("그때 미리 예약한 것(지난 방문): " + " · ".join(
            f"{PLACE.get(r['venue'], r['venue'])} {MEAL.get(r.get('meal'), '')}{(' ' + str(r['session']) + '부') if r.get('session') else ''} {_tag(r)}{ref(r, '지난 예약')}" for r in a["reservations"]))
    mem = []
    for e in sorted(a["observed_events"], key=lambda e: (e.get("order") is None, e.get("order") or 0)):
        if e["kind"] in ("checkin", "transport"): continue
        meal = MEAL.get(e.get("meal"), e.get("meal") or "")
        mem.append(f"{(str(e['order']) + '. ') if e.get('order') is not None else ''}{PLACE.get(e['place'], e['place'])}{(' · ' + meal) if meal else ''}"
                   f"{(' ' + str(e['session']) + '부') if e.get('session') else ''} — {KIND.get(e['kind'], e['kind'])}{ref(e, '지난 행동')}")
    if mem:
        L.append("그때 실제로 한 일 [관측 · 순서는 카드 순서 · 이용 사실만]: " + " / ".join(mem))
    S = sentiment or {}
    places = list(dict.fromkeys(e["place"] for e in sorted(a["observed_events"], key=lambda e: (e.get("order") is None, e.get("order") or 0)) if e["kind"] not in ("checkin", "transport")))
    def judged(p):
        e = S[p]; how = " · ".join(f"{a['aspect']} {ASPECT_KO.get(a['polarity'], a['polarity'])}" for a in e["aspects"]) if e.get("aspects") else ({"positive": "만족", "neutral": "보통", "negative": "불만"})[e["polarity"]]
        return f"{PLACE.get(p, p)} {how} [{LAYER_KO.get(e['layer'], e['layer'])}{' · ' + e['scope'] if e.get('scope') else ''}]{(' (근거 ' + ', '.join(e['ids']) + ')') if e.get('ids') else ''}"
    told = [judged(p) for p in places if p in S]
    rest = [PLACE.get(p, p) for p in places if p not in S]
    parts = told + ([f"{' · '.join(rest)} — 카드에 기록 없음(이용했다는 사실만으로 좋아했다고 말하지 않는다)"] if rest else [])
    if parts:
        L.append("그때 이용한 곳의 만족 · 불만: " + " / ".join(parts))
    prefs = [f"{PREF.get(p['feature'], p['feature'])}({SCOPE.get(p.get('scope'), p.get('scope'))} · {POLARITY_KO.get(p.get('polarity'), p.get('polarity') or '방향 미상')}){ref(p, '스스로 적은 취향')}"
             for p in a["explicit_preferences"]]
    if prefs:
        L.append("그때 스스로 적은 취향 [관측]: " + " · ".join(prefs))
    cons = [f"{CONSTRAINT.get(c['feature'], c['feature'])} {_tag(c, 'observed')}{ref(c, '사정 · 제약')}" for c in a["constraints"]]
    if cons:
        L.append("사정 · 제약: " + " · ".join(cons))
    if a.get("human_inferences"):
        L.append("사람 검수자의 메모 [사람 추론 — 원문에 쓰인 사실이 아님]: " + " / ".join(f"{h['field']}: {h.get('note') or h.get('value')}" for h in a["human_inferences"]))
    if ev_items:
        L.append(f"[평가자 의견 포함] {' · '.join(dict.fromkeys(ev_items))} 줄에는 평가자가 단 의견이 섞여 있다. 그 의견은 고객이 쓴 기록이 아니므로 '내가 겪었다 · 내가 좋아했다' 로 말하지 말고, 쓴다면 '그럴 수 있다' 는 추론으로 말할 것. 평가자 의견 ID 는 근거 ID 로 적지 않는다.")
    if a["unknowns"]:
        L.append("확인되지 않은 것 [미상] (모른다고 두고 판단할 것): " + " · ".join(a["unknowns"]))
    lay = id_layers(card)
    cite = sorted(i for i, l in lay.items() if l != "evaluator_comment" and (":" in i or i.startswith("H")))
    kids = any(k in (party or "") for k in ("child", "children"))
    return dict(blog_id=card["blog_id"], party=party, size=size.get("value"), has_children=kids, property=ov.get("property"), nights=ov.get("nights"),
                text="\n".join("- " + s for s in L), evidence_ids=cite, evaluator_ids=sorted(i for i, l in lay.items() if l == "evaluator_comment"))


SYSTEM_RULES_V2 = """
추가 규칙(근거 층 · 10/21 사람 검수 반영)
- 지난 방문에 어떤 곳을 이용했다는 사실은 '그곳을 좋아했다' 는 뜻이 아닙니다. 시트의 '만족 · 불만' 줄에 만족이 없으면, 다시 고르는 이유를 '지난번에 좋아서' 라고 말하지 말고 이번 상황(시간 · 가격 · 동행 · 거리 · 대안이 없음 · 익숙함일 수 있음)으로 설명하세요. 불만이 적혀 있으면 그 점을 먼저 따지세요.
- 사람 추론 · 일반 판단은 써도 됩니다. 다만 '~였을 수 있다 · 보통은 ~하다' 처럼 추론으로 말하고, 확인된 개인 기억처럼 단정하지 마세요.
- [평가자 의견] 은 고객이 쓴 기록이 아닙니다. 개인 기억(personal_memory)이나 evidence_ids 에 넣지 마세요.
- 산책 · 가벼운 시설처럼 비용과 기회비용이 작은 활동, 전망 좋은 객실에서 쉬는 것도 그 자체로 가치 있는 선택입니다. 활동 수를 채우려고 고르지 마세요.
- 시간표에 넣지 않을 행동(예: '시간이 되면 산책')은 계획이 아니라 제안이라고 밝히세요. 예약 · 좌석 · 혜택 자격은 무대에 확인된 것만 확정으로 말하세요."""


def system_v2(base_system: str) -> str:
    return base_system + "\n" + SYSTEM_RULES_V2


# 평가자 의견만으로 카드에 들어간 항목의 내용 낱말(ID 를 지워도 내용이 개인 기억처럼 다시 쓰이는지 잡기 위함). 새 카드에 평가자 전용 항목이 생기면 evaluator_terms() 가 'unmapped' 로 알린다.
EVAL_TERMS = {"childcare_load": ("돌보", "돌봄"), "sun_exposure": ("햇볕", "햇빛", "햇살", "선베드")}
ID_TOKEN = re.compile(r"\s*\(?\b(PR\d+:[\w\-]+|H\d+)\b\)?")
EVAL_MARK = "[평가자 의견 내용 — 고객 기록 아님]"


def evaluator_terms(card: dict) -> dict:
    """평가자 의견 ID 만으로 뒷받침되는 항목 → 내용 낱말. {"terms": [...], "unmapped": [항목]}"""
    terms, unmapped = [], []
    for sec in ("constraints",):
        for x in card["a_card"].get(sec, []):
            ids = x.get("evidence_ids") or []
            if ids and all(is_evaluator(i) for i in ids):
                (terms.extend(EVAL_TERMS[x["feature"]]) if x["feature"] in EVAL_TERMS else unmapped.append(x["feature"]))
    return dict(terms=sorted(set(terms)), unmapped=unmapped)


def _sentences(t: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.다요])\s+", t or "") if x]


def sanitize_text(text: str, card: dict) -> tuple[str, dict]:
    """평가자 의견 ID 를 지우고, 평가자 전용 내용 낱말이 든 문장 끝에 표시를 단다(내용은 지우지 않음 — 추론으로는 쓸 수 있으니)."""
    terms = evaluator_terms(card)["terms"]; ids = ID_TOKEN.findall(text or ""); out = []; marked = 0
    for sent in _sentences(ID_TOKEN.sub("", text or "")):
        if any(w in sent for w in terms) and EVAL_MARK not in sent:
            sent = f"{sent} {EVAL_MARK}"; marked += 1
        out.append(sent)
    return " ".join(out), dict(ids_removed=len(ids), marked=marked)


def _reason_lines(d: dict, layer: dict, names: dict, card: dict | None = None) -> list[str]:
    clean = (lambda t: sanitize_text(t, card)[0]) if card is not None else (lambda t: t)
    R = d.get("reasons") or {}
    ids = [f"{i}({LAYER_KO.get(layer.get(i), '카드 밖')})" for i in d.get("evidence_ids", []) if card is None or layer.get(i) != "evaluator_comment" and not is_evaluator(i)]
    out = [f"  선택: {names.get(d['option_code'], d['option_code'])} — {clean(d.get('choice', ''))}",
           f"  가장 크게 움직인 것: {d.get('main_driver', '')} · 확신 {d.get('confidence', '')}"]
    for k, ko in (("personal_memory", "개인 경험"), ("general_sense", "일반 판단"), ("current_conditions", "지금 조건"), ("external_info", "외부 정보")):
        if R.get(k): out.append(f"  {ko}: {clean(R[k])}")
    if ids: out.append(f"  근거 ID: {', '.join(ids)}")
    for x in d.get("alternatives", []) or []:
        out.append(f"  버린 대안 {names.get(x['option_code'], x['option_code'])}: {clean(x['why_not'])}")
    return out


CONTEXT_HEAD = ("# 그때 당신이 적은 이유(기록 · 참고용)\n"
                "이 기록과 지금 상황에 맞게 답하되, 기록 가운데 근거가 약하거나 사실과 다른 부분이 있으면 그렇다고 말해도 됩니다. "
                "기록에 없는 이유를 새로 들 때는 그때 생각한 것이 아니라 지금 덧붙이는 것이라고 밝히세요.")


def decision_context(rec: dict, card: dict, base_rec: dict | None = None, slots: list[int] | None = None, sanitize: bool = True) -> str:
    """후속 질문에 넘길 '그때 적은 이유' 블록. 가지면 바뀐 시간대의 원래 결정(base_rec)과 새 결정을 함께 준다.
    sanitize=True(기본): 평가자 의견 ID 를 빼고, 평가자 전용 내용은 문장마다 [평가자 의견 내용] 표시.
    기록을 '그대로 반복하라' 고 하지 않는다 — 일관성과 타당성을 따로 재기 위해(잘못된 첫 이유를 굳히지 않게)."""
    layer = id_layers(card); names = {o["code"]: o["name"] for o in rec["stage"]["options"]}; cc = card if sanitize else None
    D = rec["output"]["decisions"]; B = (base_rec or {}).get("output", {}).get("decisions") or []
    if slots is None:
        slots = [k for k, d in enumerate(D) if base_rec and (d.get("decided_by") == "llm_event" or (k < len(B) and B[k]["option_code"] != d["option_code"]))] or list(range(len(D)))
    L = [CONTEXT_HEAD]
    for k in slots:
        d = D[k]
        if base_rec and k < len(B) and (B[k]["option_code"] != d["option_code"] or d.get("decided_by") == "llm_event"):
            L.append(f"- {d['slot']} · 원래 결정"); L += _reason_lines(B[k], layer, names, cc)
            L.append(f"- {d['slot']} · 바뀐 뒤 결정"); L += _reason_lines(d, layer, names, cc)
        else:
            L.append(f"- {d['slot']}"); L += _reason_lines(d, layer, names, cc)
    if sanitize and evaluator_terms(card)["terms"]:
        L.append(f"- {EVAL_MARK} 표시는 평가자가 단 의견에서 온 내용이다. 고객이 겪은 일 · 고객의 사정으로 단정하지 말고, 쓴다면 '그럴 수 있다' 는 추론으로 말할 것.")
    return "\n".join(L)


def prompt_contamination(text: str, card: dict) -> dict:
    """입력(시스템 + 프롬프트)에 평가자 의견이 고객 근거처럼 남았는지: 평가자 ID 수 · 표시 없이 평가자 전용 내용이 든 줄."""
    terms = evaluator_terms(card)["terms"]; lay = id_layers(card)
    ev_ids = [i for i in lay if lay[i] == "evaluator_comment" and i in text]
    lines = [l.strip() for l in text.splitlines() if any(w in l for w in terms) and "평가자 의견" not in l]
    return dict(evaluator_ids=ev_ids, unmarked_evaluator_content=lines)


MEMORY_CLAIM = re.compile(r"(지난번|지난 방문|그때|예전에|원래|사정|꺼리는 편|꺼려|적혀|적었|기록에)")
INFER_MARK = re.compile(r"(수도 있|일 수|것 같|추측|추론|아마|가능성)")


def answer_contamination(answer: str, card: dict) -> dict:
    """답에서: 평가자 ID 인용 · 평가자 전용 내용을 기억 · 사정으로 단정한 문장(추론 표지가 있으면 제외)."""
    terms = evaluator_terms(card)["terms"]; lay = id_layers(card)
    ids = [i for i in lay if lay[i] == "evaluator_comment" and i in answer]
    claims = [s for s in _sentences(answer) if any(w in s for w in terms) and MEMORY_CLAIM.search(s) and not INFER_MARK.search(s)]
    return dict(evaluator_ids=ids, memory_claims=claims)


# ---------- 저장 기록 점검(모델 호출 없음) ----------
LIKE_RE = re.compile(r"(좋았|만족|맛있었|마음에 들었|좋아서|좋았던|즐거웠|또 가고 싶)")
PAST_RE = re.compile(r"(지난번|지난 방문|그때|예전에|전에 (왔|묵|갔))")
NEG_RE = re.compile(r"(없|않|아니|못|모르)")


def _place_of(code: str, visited: set) -> str | None:
    """선택지 코드(예: THE_BUFFET_D) → 지난 방문 장소 코드(THE_BUFFET). 없으면 None."""
    return next((p for p in visited if code == p or code.startswith(p + "_")), None)


def audit_decisions(rec: dict, card: dict, sentiment: dict | None = None) -> list[dict]:
    """결정마다(판정 아님 · 사람 확인용 신호)
    evaluator_ids: 평가자 의견 ID 를 근거로 인용
    revisit_by_visit_only: 지난번 이용한 곳을 다시 고르면서 개인 경험이 가장 큰 이유인데, 그곳의 만족 기록이 없음('가 봤다 → 다시 간다')
    liking_without_record: 개인 경험 칸에서 지난 이용을 '좋았다 · 만족' 으로 말함(만족 기록 없음)
    memory_without_id: 개인 경험 칸이 있는데 근거 ID 가 없음"""
    layer = id_layers(card); S = sentiment or {}; out = []
    visited = {e["place"] for e in card["a_card"]["observed_events"] if e["kind"] not in ("checkin", "transport", "abandonment", "wait")}
    for k, d in enumerate(rec["output"]["decisions"]):
        pm = (d.get("reasons") or {}).get("personal_memory", "")
        ev = [i for i in d.get("evidence_ids", []) if layer.get(i) == "evaluator_comment" or is_evaluator(i)]
        liking = [s for s in re.split(r"(?<=[.다요])\s+", pm) if LIKE_RE.search(s) and PAST_RE.search(s) and not NEG_RE.search(s)]
        place = _place_of(d["option_code"], visited)
        revisit = bool(place) and d.get("main_driver") == "personal_memory" and S.get(place, {}).get("polarity") != "positive"
        out.append(dict(slot=k, option=d["option_code"], evaluator_ids=ev, revisit_by_visit_only=revisit, liking_without_record=liking, memory_without_id=bool(pm.strip()) and not d.get("evidence_ids")))
    return out


def followup_alignment(rec: dict, answer: str, base_rec: dict | None = None) -> dict:
    """Q1 답이 기록된 대안(why_not)과 맞는지 — 바뀐 시간대의 선택지만 본다(낱말 일치 · 판정 아님).
    mentioned_recorded: 기록된 대안 중 답에 나온 것 · mentioned_unrecorded: 기록에 없는 같은 시간대 선택지를 답에서 꺼낸 것."""
    D = rec["output"]["decisions"]
    k = next((i for i, d in enumerate(D) if d.get("decided_by") == "llm_event"), None)
    if k is None: return {}
    slot = D[k]["slot"]; chosen = D[k]["option_code"]
    opts = {o["code"]: o["name"] for o in rec["stage"]["options"] if o.get("slot") == slot}
    key = lambda c: re.split(r"[\s(·'’]", opts[c].strip())[0]
    recorded = {x["option_code"] for x in D[k].get("alternatives", []) or []}
    if base_rec: recorded |= {base_rec["output"]["decisions"][k]["option_code"]} | {x["option_code"] for x in base_rec["output"]["decisions"][k].get("alternatives", []) or []}
    mentioned = {c for c in opts if c != chosen and len(key(c)) >= 2 and key(c) in answer}
    return dict(slot=k, recorded=sorted(recorded - {chosen}), mentioned_recorded=sorted(mentioned & recorded), mentioned_unrecorded=sorted(mentioned - recorded))


def feasibility_signals(visit: dict, min_slack: int = 10, min_pack: int = 15) -> list[dict]:
    """시간표 실행 가능성 신호(행동 개연성과 따로 · 판정 아님).
    tight_transfer: 객실 밖 두 핵심 행동 사이, 정해진 시작 시각(회차 · 운영 창)까지 이동 뒤 여유가 min_slack 분 미만(예: 와인페어 17:15 → 더뷔페 17:30)
    no_packing: 마지막 핵심 행동이 끝나고 퇴실까지 객실에 머무는 시간이 min_pack 분 미만(짐 정리 · 퇴실 준비)"""
    A = visit["activities"]; out = []
    cores = [i for i, a in enumerate(A) if a["kind"] == "core"]
    for i, j in zip(cores, cores[1:]):
        if A[i]["place"] == A[j]["place"] or A[i]["place"].endswith("_ROOM") or A[j]["place"].endswith("_ROOM"): continue   # 객실 출발 · 도착은 코드가 맞춰 잡는다
        rule = str(A[j].get("start_rule", ""))
        if not ("회차" in rule and "계획 문장" in rule) or "가장 이른" in rule: continue                                          # 정해진 회차가 아니면(도착하는 대로 시작) 여유와 무관
        moved = sum(a["end"] - a["start"] for a in A[i + 1:j] if a["kind"] == "move")
        slack = A[j]["start"] - A[i]["end"] - moved
        if slack < min_slack:
            out.append(dict(kind="tight_transfer", at=A[j]["start_hm"], text=f"{A[i]['place_label']} {A[i]['end_hm']} → {A[j]['place_label']} {A[j]['start_hm']} · 이동 {moved}분 · 여유 {slack}분"))
    co = next((k for k, a in enumerate(A) if a["kind"] == "checkout"), None)
    if co is not None and cores and cores[-1] < co:
        last = A[cores[-1]]
        in_room = sum(a["end"] - a["start"] for a in A[cores[-1] + 1:co] if a["kind"] in ("rest", "prep", "night") and a["place"].endswith("_ROOM"))
        if not last["place"].endswith("_ROOM") and in_room < min_pack:
            out.append(dict(kind="no_packing", at=A[co]["start_hm"], text=f"{last['place_label']} {last['end_hm']} 종료 → 퇴실 {A[co]['start_hm']} · 객실 체류 {in_room}분(짐 정리 · 퇴실 준비)"))
    return out


NOW_CLAIM = re.compile(r"(?:지금은?|지금이|벌써|이미)\s*(?:저녁\s*|오후\s*|밤\s*)?(\d{1,2})(?::(\d{2})|\s*시(?:\s*(반|\d{1,2}\s*분))?)(?:가|를|이)?\s*(넘은|넘었|지난|지났|넘어)?")


def time_claims(answer: str, event_hm: str, tol: int = 20) -> list[str]:
    """답이 '지금(이미 · 벌써) 몇 시' 를 사건 시각과 다르게 말했는지(예: 19:30 사건인데 '지금은 저녁 8시가 넘은 시각').
    오후 시각은 12시간을 더해 읽는다. '넘은 · 지난' 이면 그 시각 이후로 보고, 사건보다 tol 분 넘게 늦을 때만 잡는다."""
    h, m = map(int, event_hm.split(":")); ev = h * 60 + m; out = []
    for s in _sentences(answer):
        for mt in NOW_CLAIM.finditer(s):
            hh = int(mt.group(1)); hh = hh + 12 if hh < 12 and ev >= 12 * 60 else hh
            t = hh * 60 + (int(mt.group(2)) if mt.group(2) else 30 if mt.group(3) == "반" else int(re.sub(r"\D", "", mt.group(3))) if mt.group(3) else 0)
            if (t - ev > tol) if mt.group(4) else abs(t - ev) > tol:
                out.append(f"'{mt.group(0).strip()}' ↔ 사건 {event_hm}: {s[:80]}"); break
    return out



ASPECT_KO = {"positive": "좋음", "neutral": "보류 · 보통", "negative": "아쉬움", "unknown": "기록 없음"}


def load_visit_evaluations(path, blog: str, require_anchor: bool = True) -> dict:
    """review/visit_evaluations_1021.json → build_sheet_v2(sentiment=) 형식. 기본은 원문 앵커가 있는 항목만(status anchored · agreed).
    '보고됨' 상태(근거 위치 미확인)는 시트에 넣지 않는다 — 재방문 이유를 프롬프트 규칙만으로 메우지 않고, 장소별 평가를 원문 근거와 먼저 잇기 위해."""
    import json
    from pathlib import Path
    D = json.loads(Path(path).read_text(encoding="utf-8")).get(blog, {}); out = {}
    for place, e in D.items():
        if require_anchor and (e.get("status") not in ("anchored", "agreed") or not e.get("anchors")): continue
        out[place] = dict(aspects=e["aspects"], layer="observed" if e.get("status") == "agreed" else "human_inference", ids=e.get("anchors", []), scope=e.get("visit_scope"))
    return out
