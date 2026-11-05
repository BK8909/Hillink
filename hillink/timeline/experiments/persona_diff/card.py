"""고객 카드 v0 — 고객 파일(손 정답본 · 자동 추출본) → 칸마다 값 · 근거 등급 · 근거 층 · 판단 엔진이 읽는지 (10/20 · 격리)

근거 문장은 옮기지 않는다(원문 인용이 섞여 있다). 칸마다 근거 위치(evidence_ref)만 적는다.

근거 층(class)
  observed         ◎ — 후기에 명시(손 정답본에서 사람이 원문과 대조)
  human_inferred   ○ — 사람이 원문 단서에서 추론(손 정답본)
  assumed          △ — 추정 · 시기 규칙 · 기본값(손 정답본)
  ai_claim_*       자동 추출본의 같은 등급(◎ ○ △) — 사람이 대조하지 않은 AI 판단
  ai_inferred      성향 7개 — 자동 추출 값. 손 정답본도 자동본과 값이 같거나 '성향은 손대지 않았다'면 AI 값
  human_modified_unverified  손 정답본 성향이 자동본과 다름 — 사람이 바꿨을 수 있으나 평가자 검수 기록은 아님
  default          근거 칸이 없거나 등급 표시가 없음 — Persona 기본값일 수 있다
"""
from __future__ import annotations

import inspect, re

import core

# Persona 칸 → FACTS_EVIDENCE 키(후보 순서) — 파일마다 키 이름이 조금씩 다르다
FE_KEYS = {
    "property": ["property"], "nights": ["nights"], "is_guest": ["nights", "property"],
    "party_size": ["party"], "has_child_under_13": ["child", "party"],
    "club_access": ["club_access", "included_meals"], "included_meals": ["included_meals"],
    "booked": ["booked"], "arrival": ["arrival"], "room_minimal": ["room_minimal"], "depart_by": ["depart_by"],
}
# 판단 엔진(agent_v4 · THETA_FIT)이 읽는 Persona 칸 — 코드 추적 결과(README 매트릭스와 같음)
ENGINE_READS = {
    "property": "catalog 장소 · 이동 시간", "is_guest": "체크인 · 객실 · 종료 시각 · 출입 표", "nights": "종료 시각(end_at)",
    "depart_by": "비투숙 종료 시각", "has_child_under_13": "아동 가점 · 격식 감점 · 성인 전용 제외",
    "club_access": "클럽 라운지 행동 생성", "included_meals": "포함 끼니 가점 · 다른 식사 막음",
    "booked": "예약한 곳 첫 방문 가점(장소 단위)", "arrival": "발렛 · 주차 단계(이동 경로)", "room_minimal": "객실 쉼 감점",
    "prefers": "가고 싶던 곳 가점(후기 고객은 비어 있음)", "wake_at": "기상 시각(후기 고객은 기본 07:30)",
    "party_size": "좌석 상한(capacity 있을 때만) · 포장 판 수 · 함께 먹기(lam 0 이라 0)",
    "start_at": "시작 시각 · 날짜(운영 창 · 요일)",
}
CARD_ONLY = ["purpose", "ai_type", "age_band", "sex", "package", "note"]   # 기본 계수에서는 행동 선택에 안 쓰임(purpose 는 실험 조정값에서만)
GRADE_RE = re.compile(r"[◎○△]")
TRAIT_UNTOUCHED = re.compile(r"성향(은|\(TRAIT_EVIDENCE\)은)? ?(손대지 않|자동 (추출|초안)( 값을)? (그대로|유지))|성향 근거는 초안 그대로|성향은 자동 추출 그대로")


def grade_of(text) -> str | None:
    m = GRADE_RE.search(str(text or ""))
    return m.group(0) if m else None


def _class(grade: str | None, auto: bool) -> str:
    if grade is None:
        return "default"
    if auto:
        return {"◎": "ai_claim_observed", "○": "ai_claim_inferred", "△": "ai_claim_assumed"}[grade]
    return {"◎": "observed", "○": "human_inferred", "△": "assumed"}[grade]


def start_grades(mod) -> dict:
    """START_AT 줄 주석의 '날짜 ◎/○/△ · 시각 ◎/△' — 없으면 None."""
    src = inspect.getsource(mod)
    line = next((l for l in src.splitlines() if l.startswith("START_AT")), "")
    out = {}
    for part in ("날짜", "시각"):
        m = re.search(part + r"\s*\(?\s*([◎○△])", line) or re.search(r"([◎○△])\s*" + part, line)
        out[part] = m.group(1) if m else None
    return out


def build(blog: str, auto: bool = False) -> dict:
    mod = core.load_module(blog, auto)
    p, fe = mod.PERSONA, getattr(mod, "FACTS_EVIDENCE", {}) or {}
    fields = {}
    for f, keys in FE_KEYS.items():
        key = next((k for k in keys if k in fe), None)
        g = grade_of(fe.get(key)) if key else None
        v = getattr(p, f)
        fields[f] = dict(value=list(v) if isinstance(v, tuple) else (str(v) if f == "depart_by" else v), grade=g, cls=_class(g, auto),
                         evidence_ref=f"{blog}{'_auto' if auto else ''}:fact:{key}" if key else None, engine=ENGINE_READS.get(f))
    sg = start_grades(mod)
    fields["start_at"] = dict(value=mod.START_AT.isoformat(), grade=sg["날짜"], time_grade=sg["시각"], cls=_class(sg["날짜"], auto),
                              time_cls=_class(sg["시각"], auto), evidence_ref=f"{blog}{'_auto' if auto else ''}:START_AT", engine=ENGINE_READS["start_at"])
    # 성향 층 — 자동 추출본과 값이 같으면 AI 값(머리말 문구와 상관없이). 다르면 사람이 고친 값일 수 있음(검수 기록은 따로 확인)
    doc = mod.__doc__ or ""
    auto_traits = None
    if not auto and (core.TL / f"persona_{blog}_auto.py").exists():
        auto_traits = core.load_module(blog, auto=True).PERSONA.traits
    tev = getattr(mod, "TRAIT_EVIDENCE", {}) or {}
    traits = {}
    for k, v in p.traits.items():
        same = auto or (auto_traits is not None and auto_traits.get(k) == v) or bool(TRAIT_UNTOUCHED.search(doc))
        traits[k] = dict(value=v, grade=grade_of(tev.get(k, (None, ""))[1]), cls="ai_inferred" if same else "human_modified_unverified",
                         human_reviewed=False, same_as_auto=None if auto else (auto_traits is not None and auto_traits.get(k) == v),
                         evidence_ref=f"{blog}{'_auto' if auto else ''}:trait:{k}")
    return dict(blog=blog, track="B_auto" if auto else "A_checked", fields=fields, traits=traits,
                card_only={k: getattr(p, k, None) for k in CARD_ONLY},
                truth_meals=[(m[0], m[1], grade_of(m[2])) for m in getattr(mod, "TRUTH_MEALS", [])])
