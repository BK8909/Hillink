"""CL-19 보충 — 비식별 근거 문맥 어댑터.
고객별로 보유한 프로파일 자료(후기 사실 요지 · 업장 경험 · 메뉴 취향 · 다른 숙박의 시설 이용 · 팀 분석의 판단 패턴 · 행동 가설 · 동행 · 반례)를
LLM 판단 입력용 요약으로 묶는다. 원문 · 링크 · 작성자 · 검수자 이름 · 글 번호는 넣지 않는다.
- '후기에서 확인' 묶음: fact_id 가 붙은 요지(실제 경험) → LLM 이 인용 가능(fact_ids).
- '프로파일 기반 추론' 묶음: 팀 분석가의 성향 · 행동 가설(검증 전) → 인용 ID 없음, 추론으로만 사용.
"""
from __future__ import annotations
import re

URL = re.compile(r"https?://\S+|www\.\S+|blog\.naver\S*")
STAFF_FIXED = r"검수본|엑셀|PR\s?#\d+"   # 담당 분석가 이름은 저장소에 적지 않고 실행 시 라이브러리 owner 값으로 만든다
CAP = dict(wh=10, venue=10, menu=5, other=8, judgment=6, rule=5, counter=3, facts=12)


def staff_re(a):
    return re.compile("|".join([STAFF_FIXED] + [re.escape(x) for x in getattr(a, "staff", [])]))


_ST = None


def _clean(s, n=110, staff=None):
    staff = staff or _ST
    s = URL.sub("", str(s or "")).strip()
    return "" if (not s or (staff and staff.search(s))) else s[:n]


def _fids(x):
    return [f for f in (x.get("fact_ids") or x.get("facts") or []) if isinstance(f, str)] if isinstance(x, dict) else []


def context(a):
    """→ (block, citable_fact_ids, coverage)"""
    t, L = a.traits, a.lib or {}
    global _ST
    _ST = staff_re(a)
    hidden = set(a.P.get("hidden") or [])
    held, sent, omitted = {}, {}, {}

    def take(name, items, cap, mk):
        items = list(items or [])
        held[name] = len(items)
        out, drop = [], dict(cap=0, hidden_or_staff=0, empty_or_duplicate=0)
        for x in items:
            if len(out) >= cap:
                drop["cap"] += 1; continue
            if any(f in hidden for f in _fids(x)):
                drop["hidden_or_staff"] += 1; continue
            y = mk(x)
            if not y:
                drop["empty_or_duplicate"] += 1; continue
            out.append(y)
        sent[name] = len(out); omitted[name] = {k: v for k, v in drop.items() if v}
        return out

    seen = {}

    def ev(x, extra=None):
        g = _clean(x.get("gist") or x.get("detail"))
        if not g:
            return None
        if g in seen:   # 같은 요지는 한 번만(사실 ID 는 앞 항목에 합침)
            seen[g]["fact_ids"] = sorted(set(seen[g]["fact_ids"]) | set(_fids(x)[:3])); return None
        y = dict(what=g, fact_ids=_fids(x)[:3], **(extra or {}))
        ctx = next((fact_context(a, f) for f in y["fact_ids"] if fact_context(a, f)), None)
        y["where"] = {"wh": "워커힐", "other": "다른 곳"}.get(ctx, "출처 미확정")   # 다른 곳 · 미확정 경험을 인용하면 확장 추론으로 표시
        seen[g] = y
        return y

    # 1) 워커힐 업장 · 시설 경험(후기 사실)
    venues = [dict(v, _venue=k) for k, vs in (t.get("venues") or {}).items() for v in vs]
    wh_v = take("venue_experiences", venues, CAP["venue"], lambda x: ev(x, dict(place=x["_venue"], kind=x.get("basis") or x.get("kind"))))
    wh_e = take("walkerhill_visit_events", sorted(L.get("wh_events") or [], key=lambda e: e.get("link") != "confirmed"), CAP["wh"],
                lambda x: ev(x, dict(stage=_clean(x.get("stage"), 30), link="워커힐 방문 확인" if x.get("link") == "confirmed" else "워커힐 방문으로 추정")))
    # 2) 메뉴 취향 · 다른 숙박의 시설 유형 이용(행동 패턴)
    menu = take("menu_preferences", t.get("menu"), CAP["menu"], lambda x: ev(x, dict(tags=x.get("tags", [])[:4])))
    fth = take("other_stay_patterns", t.get("facility_type_history"), CAP["other"], lambda x: ev(x, dict(type=x.get("venue_type") or x.get("venue"))))
    # 3) 팀 분석 — 소비 판단 · 만족 · 불만 패턴(추론) · 행동 가설(검증 전)
    judg = take("judgment_patterns", L.get("traits"), CAP["judgment"],
                lambda x: (dict(pattern=_clean(x.get("trait"), 90), when=[_clean(c, 80) for c in (x.get("conditions") or [])[:1] if _clean(c, 80)],
                                but=[_clean(c, 80) for c in (x.get("counter") or [])[:1] if _clean(c, 80)]) if _clean(x.get("trait")) else None))
    rules = take("behavior_hypotheses", L.get("rules"), CAP["rule"],
                 lambda x: (dict(if_=_clean(x.get("condition"), 90), then=_clean(x.get("hypothesis"), 100), status="검증 전 가설") if _clean(x.get("hypothesis")) else None))
    counter = take("counterexamples", t.get("counterexamples"), CAP["counter"], lambda x: ev(x) if isinstance(x, dict) else ({"what": _clean(x)} if _clean(x) else None))
    # 4) 기타 후기 사실(위에서 빠진 것 보충)
    used = {f for grp in (wh_v, wh_e, menu, fth, counter) for y in grp for f in y.get("fact_ids", [])}
    rest = [v for k, v in (t.get("evidence_index") or {}).items() if k not in used]
    extra = take("other_review_facts", rest, CAP["facts"], lambda x: ev(dict(gist=x.get("gist"), fact_ids=[x.get("fact_id")])))
    comp = t.get("visit_companion")
    held["companion"] = int(bool(comp)); sent["companion"] = int(bool(comp))
    other_ev = L.get("other_events") or []
    held["other_hotel_events(팀 분석 원자료)"] = len(other_ev); sent["other_hotel_events(팀 분석 원자료)"] = 0
    if other_ev:
        omitted["other_hotel_events(팀 분석 원자료)"] = {"요약 패턴(other_stay_patterns · judgment_patterns)으로 대신 전달": len(other_ev)}
    label = (t.get("entry") or {}).get("label") or L.get("label") or ""
    block = dict(customer_type=_clean(L.get("type") or a.P.get("type"), 30), summary=_clean(label, 90), companion=comp if isinstance(comp, (str, dict)) else None,
                 review_confirmed=dict(walkerhill_places=wh_v, walkerhill_visits=wh_e, menu=menu, patterns_elsewhere=fth, counterexamples=counter, more=extra),
                 profile_inference=dict(judgment_patterns=judg, behavior_hypotheses=rules))
    cite = sorted({f for grp in (wh_v, wh_e, menu, fth, counter, extra) for y in grp for f in y.get("fact_ids", []) if a.gist(f)})
    cov = dict(held=held, sent=sent, omitted=omitted, citable_fact_ids=len(cite), total_facts=len(t.get("evidence_index") or {}))
    return block, cite, cov


# ---------------------------------------------------------------- 출처 맥락(워커힐 경험 / 다른 곳 경험)
_AM = None


def _author_method_wh_posts():
    """V4.1 작성자 프로필(blog41 · blog42)의 '워커힐 글만' 범위 글 번호 — 같은 작성자의 다른 글과 구분."""
    global _AM
    if _AM is None:
        _AM = {}
        try:
            import json
            from pathlib import Path
            d = json.loads((Path(__file__).resolve().parents[1] / "author_method_v4_1_artifacts" / "profiles_and_quality.json").read_text(encoding="utf-8"))
            for pid, v in d.get("authors", {}).items():
                s = json.dumps(v.get("scope_profiles", {}).get("walkerhill_only", {}))
                _AM[pid] = set(re.findall(r'"(P\d{3})_F\d+', s))
        except Exception:
            pass
    return _AM


def fact_context(a, fid):
    """'wh'(워커힐에서 직접 겪은 일) · 'other'(같은 작성자의 다른 호텔 · 장소 경험) · None(원천 매핑 없음)."""
    if not hasattr(a, "_fctx"):
        m = {}
        base = lambda f: re.sub(r"[a-z]$", "", f)
        for e in (a.lib or {}).get("wh_events") or []:
            for f in e.get("facts") or []:
                m[base(f)] = "wh"
        for e in (a.lib or {}).get("other_events") or []:
            for f in e.get("facts") or []:
                m.setdefault(base(f), "other")
        for k, vs in (a.traits.get("venues") or {}).items():
            for v in vs:
                for f in v.get("fact_ids") or []:
                    m.setdefault(base(f), "wh")
        for v in a.traits.get("facility_type_history") or []:
            for f in v.get("fact_ids") or []:
                m.setdefault(base(f), "wh" if "WH" in str(v.get("experience", "")) else "other")
        posts = _author_method_wh_posts().get(a.pid)
        if posts:
            for f in (a.traits.get("evidence_index") or {}):
                m.setdefault(base(f), "wh" if f.split("_")[0] in posts else "other")
        a._fctx = m
    f = ((a.lib or {}).get("engine") or {}).get("facts", {}).get(fid) or {}
    exp, g = str(f.get("exp") or ""), str(f.get("gist") or "")
    if exp and not re.search(r"WH|CURRENT|WALKERHILL", exp, re.I):
        return "other"   # CL-1025-23 — 같은 글 안의 과거 · 다른 곳 경험(예: HAWAII_PREVIOUS)은 워커힐 직접 경험이 아님
    if re.search(r"서로 다른 맥락|각각 다른 숙박", g):
        return "other"   # 여러 호텔 경험을 묶은 요약 사실 — 워커힐 한 장면의 직접 근거로 쓰지 않음
    return a._fctx.get(re.sub(r"[a-z]$", "", fid))


SLOT_WORDS = {"breakfast": ("아침", "조식", "브런치"), "lunch": ("점심", "런치", "중식"), "dinner": ("저녁", "석식", "디너", "야식")}


def slot_mismatch(gist, slot):
    """식사 행동의 끼니(slot)와 사실 요지의 끼니가 다르면 True(예: 아침 경험을 점심 선택 근거로)."""
    if not slot:
        return False
    own = any(w in gist for w in SLOT_WORDS.get(slot, ()))
    other = any(w in gist for k, ws in SLOT_WORDS.items() if k != slot for w in ws)
    return other and not own
