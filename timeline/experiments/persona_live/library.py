"""페르소나 라이브러리 — 저장소에 이미 있는 고객 자료를 태그로 구조화 (10/21 · 총괄 C)

  python3 library.py        # → demo/library.json (요약만 출력)

출처(우선순위)
  1. 고객 카드 v1(group_inputs_v1) — 사람 사실 확인. 관측/사람 추론 구분이 카드에 있다.
  2. 후기별 페르소나 파일(timeline/persona_blogNN.py) — 구조화 칸만 읽는다(인원 · 아이 · 건물 · 박 수 · 방문일 등급 · 이용 장소 코드 · 등급 기호).
     따옴표 원문 · 서술 문장은 옮기지 않는다.
  3. 후기 유형표(docs/blog_types.csv) — 목적 분류 · 한 줄 요약(자동 분류 · 요약문).
  4. 인스타그램 표본(docs/instagram_persona_*.csv) — 게시물 단위 방문 요약(인물 단위 후기가 아님 · 프로필만).

제외: 3차 봉인 평가셋(파일을 열지 않는다 · 카드 v1 에 이미 있는 41 · 43 · 59 만 카드로 포함), 직접 방문기가 아닌 글('못 씀' 표시).
가상 고객을 만들어 빈 유형을 채우지 않는다.

태그 근거 수준: observed(관측) · inferred(사람 추론 · 사람 정리) · estimated(자동 분류 · 추정).
"""
from __future__ import annotations

import csv, importlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TL = HERE.parents[1]; ROOT = TL.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(TL))
from persona_sheet import load_cards   # noqa: E402

SEALED3 = {32, 34, 41, 42, 43, 50, 51, 52, 59, 60, 61}
LV = {"◎": "observed", "○": "inferred", "△": "estimated"}
FAC = {"GRAND_POOL": "실내 수영장", "VISTA_POOL": "실내 수영장", "RIVERPARK": "리버파크", "PIZZA_HILL": "피자힐", "THE_BUFFET": "더뷔페", "MYONGWOLGWAN": "명월관", "ONDAL": "온달",
       "GEUMRYONG": "금룡", "MOEGI": "모에기", "THE_PAVILION": "더파빌리온", "LE_PASSAGE": "르파사쥬", "LUX_BAR": "럭스 바", "GRAND_CLUB_LOUNGE": "클럽 라운지", "DOUGLAS_LOUNGE": "더글라스 라운지",
       "SKYARD": "스카이야드", "FOREST_PARK": "포레스트 파크", "THEATRE_OF_LIGHT": "빛의 시어터", "FITNESS": "피트니스 · 사우나", "WELLNESS_SAUNA": "피트니스 · 사우나", "VISTA_FITNESS": "피트니스 · 사우나",
       "GRAND_LIBRARY": "라이브러리", "DOUGLAS_LIBRARY": "라이브러리", "GOLF_CLUB": "골프", "TENNEZ_PARK": "테니스"}
STAY = {"GRAND": "그랜드", "VISTA": "비스타", "DOUGLAS": "더글라스"}
PURPOSE = {"가족·친족": "가족 여행", "커플·기념일": "기념일 · 데이트", "친구·모임": "모임", "혼자 휴식": "호캉스 · 휴식", "휴식·산책 동행": "호캉스 · 휴식", "미식 방문": "미식 · 식사"}
TRAIT = {"조망 중시": "조망", "조용함 선호": "조용함", "새로움 추구": "새로운 경험", "이동 최소화": "이동 최소화", "함께 먹기 선호": "함께 먹기", "격식 선호": "격식 있는 식사", "대기 회피": "대기 회피"}
CARD_PREF = {"view_enjoyment": "조망", "view_seating": "조망", "window_seat": "조망", "window_seat_enjoyment": "조망", "river_view_seat": "조망", "river_view_room": "조망", "river_view_hotel": "조망", "view_walk": "조망",
             "low_view_priority": "객실 조망 무관", "quiet_conversation": "조용함", "quiet_rest": "조용함", "private_room": "별실", "on_property_convenience": "이동 최소화", "broad_facility_use": "새로운 경험",
             "repeat_visit": "재방문", "club_benefits_over_room_view": "클럽 혜택"}
CARD_PURPOSE = {"family_hotel_stay": "가족 여행", "family_stay": "가족 여행", "family_summer_vacation": "가족 여행", "lunar_new_year_family_trip": "가족 여행", "quiet_rest": "호캉스 · 휴식",
                "birthday_hotel_stay": "기념일 · 데이트", "anniversary_family_dinner": "기념일 · 데이트", "special_buffet_meal": "미식 · 식사", "dining": "미식 · 식사", "buffet": "미식 · 식사",
                "hotel_exploration": "호캉스 · 휴식", "hotel_facility_exploration": "호캉스 · 휴식", "post_event_late_checkin": "호캉스 · 휴식", "spa_room": "호캉스 · 휴식", "conversation": "모임"}
EVENT_WORDS = [("크리스마스", "크리스마스"), ("와인", "와인페어"), ("벚꽃", "벚꽃"), ("단풍", "단풍 · 가을 산책"), ("설 연휴", "설 연휴"), ("설연휴", "설 연휴"), ("기념일", "기념일"), ("생일", "기념일"), ("돌", "가족 행사")]


def season(m: int) -> str:
    return {12: "겨울", 1: "겨울", 2: "겨울", 3: "봄", 4: "봄", 5: "봄", 6: "여름", 7: "여름", 8: "여름", 9: "가을", 10: "가을", 11: "가을"}[m]


# 시설 · 행사 태그의 이용 상태 — 실제 이용 / 예약만 / 시도 후 실패 / 혜택만 보유 / 언급(방문 여부 미확인) / 방문 목적 / 방문 날짜
STATUS = {"used": "실제 이용", "reserved": "예약만", "failed": "시도 후 실패 · 포기", "entitled": "혜택만 보유(이용 미확인)", "mention": "언급 · 방문 미확인", "purpose": "방문 목적", "date": "방문 날짜로 추정"}
ITEM2FAC = {"THE_BUFFET_BREAKFAST": "THE_BUFFET", "THE_BUFFET": "THE_BUFFET", "THEATRE_OF_LIGHT_TICKET": "THEATRE_OF_LIGHT", "GRAND_POOL": "GRAND_POOL", "RIVERPARK_TICKET": "RIVERPARK", "PIZZA_HILL": "PIZZA_HILL"}


def tag(group, label, level, basis, status=None):
    t = dict(group=group, label=label, level=level, basis=basis)
    if status: t["status"] = status
    return t


def companion_tags(size, kids, purpose_raw, level, basis):
    out = []
    if kids: out.append(tag("동행", "아이 동반", level, basis))
    if purpose_raw == "가족·친족" and not kids: out.append(tag("동행", "성인 가족", "estimated", "유형표 목적 + 아이 없음"))
    if size == 1: out.append(tag("동행", "혼자", level, basis))
    elif size == 2 and not kids and purpose_raw != "가족·친족": out.append(tag("동행", "2인 · 커플", level, basis))
    elif size and size >= 3 and not kids and purpose_raw == "친구·모임": out.append(tag("동행", "친구 · 모임", level, basis))
    return out


def blog_types() -> dict:
    return {r["blog"]: r for r in csv.DictReader(open(ROOT / "docs" / "blog_types.csv", encoding="utf-8-sig"))}


def compose_summary(tags: list, stay: str | None, nights, size) -> str:
    """카드 · 파일의 구조화된 사실(태그)로만 한 줄 소개를 만든다 — 검수 메모 문장은 소개에 쓰지 않는다."""
    g = lambda k: [t["label"] for t in tags if t["group"] == k]
    head = "비투숙 방문" if stay == "비투숙" else (f"{stay} {nights}박" if stay and stay != "미상" and nights else (stay if stay and stay != "미상" else "숙박 미상"))
    comp = (g("동행") or [""])[0].replace("2인 · 커플", "커플").replace(" · ", "/")
    who = " ".join(x for x in [f"{size}인" if size else "", comp] if x)
    fac = "·".join(dict.fromkeys(t["label"].replace(" · ", "/") for t in tags if t["group"] == "시설" and t.get("status", "used") == "used"))   # 실제 이용만 (예약 · 혜택 · 포기는 소개에 넣지 않음)
    return " · ".join(x for x in [head, who, fac] if x)


def from_card(c: dict, bt: dict | None) -> dict:
    a = c["a_card"]; b = c["blog_id"]; T = []
    comp = a["party"]["composition"]; cv = comp.get("value") or ""; lv = "observed" if comp.get("provenance") == "observed" else "inferred"
    if "child" in cv: T.append(tag("동행", "아이 동반", lv, "카드 v1 동행"))
    if "parents" in cv or "mother" in cv: T.append(tag("동행", "부모님 동반", lv, "카드 v1 동행"))
    if cv in ("solo",): T.append(tag("동행", "혼자", lv, "카드 v1 동행"))
    if cv in ("writer and companion",) or (a["party"]["size"].get("value") == 2 and "child" not in cv and "mother" not in cv): T.append(tag("동행", "2인 · 커플", lv, "카드 v1 동행"))
    pu = a["purpose"]; plv = "observed" if pu.get("provenance") == "observed" else "inferred"
    for v in pu.get("value") or []:
        if v in CARD_PURPOSE: T.append(tag("목적", CARD_PURPOSE[v], plv, "카드 v1 목적"))
    ov = a["observed_visit"]; ci = ov["check_in"]; v = ci.get("value")
    if isinstance(v, dict): v = v.get("earliest")
    when = dict(text="방문 시기 미상", season=None, year=None, level=None)
    if isinstance(v, str) and re.match(r"\d{4}-\d{2}", v):
        y, m = int(v[:4]), int(v[5:7]); slv = "observed" if ci.get("provenance") == "observed" else "inferred"
        when = dict(text=f"{y}년 {m}월", season=season(m), year=y, level=slv); T.append(tag("시기", season(m), slv, "카드 v1 방문일"))
    if ov.get("nights"): T.append(tag("숙박", STAY.get(ov.get("property"), "미상"), "observed", "카드 v1"))
    else: T.append(tag("숙박", "비투숙", "observed", "카드 v1"))
    eid = lambda e: (e.get("evidence_ids") or [""])[0]
    used = set()
    for e in a["observed_events"]:
        if e.get("place") in FAC and e["kind"] in ("meal", "facility", "stay", "purchase", "cultural"):
            T.append(tag("시설", FAC[e["place"]], "observed", f"카드 v1 관측 {eid(e)}".strip(), "used")); used.add(e["place"])
        elif e.get("place") in FAC and e["kind"] == "abandonment":
            T.append(tag("시설", FAC[e["place"]], "observed", f"카드 v1 관측(포기) {eid(e)}".strip(), "failed"))
    for r in a.get("reservations") or []:
        if r.get("venue") in FAC and r["venue"] not in used:
            T.append(tag("시설", FAC[r["venue"]], "observed" if r.get("provenance") == "observed" else "inferred", f"카드 v1 예약 {eid(r)}".strip(), "reserved"))
    for en in a.get("entitlements") or []:
        f = ITEM2FAC.get(en.get("item"))
        if f in FAC and f not in used and en.get("use_status") == "not_observed":
            T.append(tag("시설", FAC[f], "observed" if en.get("provenance") == "observed" else "inferred", f"카드 v1 혜택(이용 기록 없음) {eid(en)}".strip(), "entitled"))
    for p in a["explicit_preferences"]:
        if p["feature"] in CARD_PREF: T.append(tag("관심", CARD_PREF[p["feature"]], "observed", f"카드 v1 명시 선호 {p['evidence_ids'][0] if p.get('evidence_ids') else ''}".strip()))
    if any(x in (pu.get("value") or []) for x in ("birthday_hotel_stay", "anniversary_family_dinner")): T.append(tag("이벤트", "기념일", plv, "카드 v1 목적", "purpose"))
    if "lunar_new_year_family_trip" in (pu.get("value") or []): T.append(tag("이벤트", "설 연휴", plv, "카드 v1 목적", "purpose"))
    memo = (bt or {}).get("근거", "").split("; ", 1)[-1] if bt else ""
    stay = STAY.get(ov.get("property")) if ov.get("nights") else "비투숙"; size = a["party"]["size"].get("value")
    return dict(id=b, source="블로그 후기 · 고객 카드 v1(사람 사실 확인)", source_kind="card", summary=compose_summary(T, stay, ov.get("nights"), size), memo=memo, when=when,
                stay=stay, nights=ov.get("nights"), size=size, tags=T, customer_key=c.get("team_id"), visit_key=c.get("stay_id"))


def from_file(n: int, bt: dict | None) -> dict | None:
    name = f"persona_blog{n:02d}"
    try:
        m = importlib.import_module(name)
    except Exception:
        try: m = importlib.import_module(name + "_auto")
        except Exception: return None
    head = "\n".join((m.__doc__ or "").strip().split("\n")[:4])
    if re.search(r"^못 씀|\*\*못 씀\*\*", head, re.M): return dict(id=f"blog{n:02d}", excluded="직접 방문기가 아님(파일 표시)")
    P = m.PERSONA; F = getattr(m, "FACTS_EVIDENCE", {}); T = []
    lvf = lambda k: LV.get((F.get(k) or " ")[0], "estimated")
    purpose_raw = (bt or {}).get("목적", "")
    T += companion_tags(P.party_size, P.has_child_under_13, purpose_raw, lvf("party"), "후기 파일 동행 칸")
    if purpose_raw in PURPOSE: T.append(tag("목적", PURPOSE[purpose_raw], "estimated", "후기 유형표(자동 분류)"))
    T.append(tag("숙박", STAY.get(P.property, "미상") if P.is_guest else "비투숙", lvf("property") if P.is_guest else "inferred", "후기 파일 건물 칸"))
    src = (Path(m.__file__).read_text(encoding="utf-8").split("START_AT", 1) + [""])[1].split("\n", 1)[0]
    st = getattr(m, "START_AT", None); when = dict(text="방문 시기 미상", season=None, year=None, level=None)
    if st and st.year > 2000:
        if "작성일" in src or "게시" in src:
            when = dict(text=f"방문 시기 미상 · 게시 {st.year}년 {st.month}월", season=None, year=None, level=None)
        else:
            g = next((LV[c] for c in src if c in LV), "estimated")
            when = dict(text=f"{st.year}년 {st.month}월", season=season(st.month), year=st.year, level=g)
            T.append(tag("시기", season(st.month), g, "후기 파일 방문일 등급"))
            if st.month == 12 and 20 <= st.day <= 31: T.append(tag("이벤트", "크리스마스", g, "방문일", "date"))
    for code, txt in getattr(m, "TRUTH_VISITED", {}).items():
        if code in FAC: T.append(tag("시설", FAC[code], LV.get((txt or " ")[0], "estimated"), "후기 파일 이용 장소", "used"))
    for k, (v, _) in getattr(m, "TRAIT_EVIDENCE", {}).items():
        if v is not None and v >= 0.6 and k in TRAIT: T.append(tag("관심", TRAIT[k], "estimated", "성향 초안(검수 안 됨)"))
    summ = (bt or {}).get("근거", "").split("; ", 1)[-1]
    for w, lab in EVENT_WORDS:
        if w in summ: T.append(tag("이벤트", lab, "estimated", "유형표 요약에 낱말이 나옴", "mention"))
    dup = "같은 작성자의 다른 체류 기록이 함께 있음(유형표)" if "같은 사람" in summ else None
    stay = STAY.get(P.property) if P.is_guest else "비투숙"; nights = P.nights if P.is_guest else 0
    return dict(id=f"blog{n:02d}", source="블로그 후기 · 후기 파일(사람 정리 · 자동 초안 포함)", source_kind="file", summary=compose_summary(T, stay, nights, P.party_size), memo=summ, when=when,
                stay=stay, nights=nights, size=P.party_size, tags=T, dup_note=dup)


def from_ig() -> list:
    out = []
    for f, wf in (("instagram_persona_sample.csv", False), ("instagram_persona_winefair_additional.csv", True)):
        for r in csv.DictReader(open(ROOT / "docs" / f, encoding="utf-8-sig")):
            lv = "inferred" if r["판단상태"] == "확실" else "estimated"; T = []
            c = r["동행"]
            if "아이" in c: T.append(tag("동행", "아이 동반", lv, "SNS 표본 수동 분류"))
            if "부모" in c: T.append(tag("동행", "부모님 동반", lv, "SNS 표본 수동 분류"))
            if c in ("부부", "커플"): T.append(tag("동행", "2인 · 커플", lv, "SNS 표본 수동 분류"))
            if "친구" in c or "지인" in c or "모임" in c: T.append(tag("동행", "친구 · 모임", lv, "SNS 표본 수동 분류"))
            if r["방문목적"] in PURPOSE: T.append(tag("목적", PURPOSE[r["방문목적"]], lv, "SNS 표본 수동 분류"))
            fac = r["이용시설"]
            for k, lab in (("수영장", "실내 수영장"), ("피자힐 포장", "피자힐"), ("더뷔페", "더뷔페"), ("포레스트", "포레스트 파크"), ("스카이야드", "스카이야드"), ("클럽", "클럽 라운지"), ("라이브러리", "라이브러리"), ("사우나", "피트니스 · 사우나"), ("라운지", "더글라스 라운지" if "더글라스" in fac else "클럽 라운지")):
                if k in fac and not any(t["label"] == lab for t in T): T.append(tag("시설", lab, lv, "SNS 표본 이용시설(게시물에 보인 이용)", "used"))
            if r["와인페어표시"] == "예" or "와인페어" in fac: T.append(tag("이벤트", "와인페어", lv, "SNS 표본 · 와인페어 현장 게시물", "used"))
            if "벚꽃" in fac: T.append(tag("이벤트", "벚꽃", lv, "SNS 표본 이용시설", "used"))
            elif "벚꽃" in r["근거요약"]: T.append(tag("이벤트", "벚꽃", lv, "SNS 표본 요약에 낱말이 나옴", "mention"))
            if "크리스마스" in r["근거요약"]: T.append(tag("이벤트", "크리스마스", lv, "SNS 표본 요약에 낱말이 나옴", "mention"))
            if "단풍" in r["근거요약"]: T.append(tag("이벤트", "단풍 · 가을 산책", lv, "SNS 표본 요약에 낱말이 나옴", "mention"))
            if "기념일" in r["근거요약"]: T.append(tag("이벤트", "기념일", lv, "SNS 표본 요약에 낱말이 나옴", "mention"))
            mm = re.match(r"(\d{4})-(\d{2})", r["게시일"])
            when = dict(text=f"게시 {mm.group(1)}년 {int(mm.group(2))}월" if mm else "방문 시기 미상", season=season(int(mm.group(2))) if mm else None, year=int(mm.group(1)) if mm else None, level="estimated" if mm else None)
            if mm: T.append(tag("시기", season(int(mm.group(2))), "estimated", "게시월(방문월과 다를 수 있음)"))
            stay = "그랜드" if "그랜드" in fac else "비스타" if "비스타" in fac else "더글라스" if "더글라스" in fac else "미상"
            if stay != "미상": T.append(tag("숙박", stay, lv, "SNS 표본 이용시설"))
            out.append(dict(id=r["표본ID"], source="인스타그램 공개 게시물 표본(게시물 단위 요약 · 인물 후기 아님)", source_kind="sns", summary=r["근거요약"], when=when,
                            stay=stay, nights=None, size=None, tags=T, sponsored=r.get("협찬여부") or None,
                            # 계정 해시는 중복 경고 계산에만 쓰고 공유 산출물에는 내보내지 않는다.
                            _customer_key=("acct:" + r["계정해시"][:10]) if r.get("계정해시") else None, visit_key=None))
    return out


def build() -> dict:
    cards = load_cards(); bt = blog_types(); items = []; excluded = []
    card_ids = {b for b, c in cards.items() if c.get("selection_status") in ("selected", "reserve")}
    for b in sorted(card_ids):
        items.append(from_card(cards[b], bt.get(b)))
    for n in range(1, 62):
        b = f"blog{n:02d}"
        if b in card_ids: continue
        if n in SEALED3: excluded.append(dict(id=b, reason="3차 봉인 평가셋 — 열지 않음")); continue
        e = from_file(n, bt.get(b))
        if e is None: continue
        if e.get("excluded"): excluded.append(dict(id=b, reason=e["excluded"])); continue
        items.append(e)
    items += from_ig()
    runs = HERE / "runs" / "demo_1"
    acct = {}
    internal_customer_keys = {it.get("_customer_key") or it.get("customer_key") for it in items
                              if it.get("_customer_key") or it.get("customer_key")}
    for it in items:
        key = it.get("_customer_key") or it.get("customer_key")
        if key: acct.setdefault(key, []).append(it["id"])
    for it in items:
        it["ready"] = (runs / it["id"] / "D0_r0.json").exists()
        # 단위 분리 — 원천(글 · 게시물) / 고객 키(같은 사람으로 확인된 묶음 · 모르면 없음) / 방문 키 / 종류 / 행동 준비 상태. 자동으로 합치지 않는다
        it["source_id"] = it["id"]; it["type"] = it["source_kind"]; it["ready_status"] = "agent_ready" if it["ready"] else "profile_only"
        key = it.get("_customer_key") or it.get("customer_key")
        same = [x for x in acct.get(key, []) if x != it["id"]] if key else []
        if same: it["dup_note"] = f"같은 계정의 다른 게시물 {len(same)}건({', '.join(same)}) — 같은 사람일 수 있으나 자동으로 합치지 않음"
        it.pop("_customer_key", None)
        it.setdefault("customer_key", None); it.setdefault("visit_key", None)
        seen = set(); it["tags"] = [t for t in it["tags"] if not ((t["group"], t["label"]) in seen or seen.add((t["group"], t["label"])))]
    groups = ["동행", "목적", "시기", "숙박", "시설", "이벤트", "관심"]
    facets = {g: sorted({t["label"] for it in items for t in it["tags"] if t["group"] == g}) for g in groups}
    return dict(items=items, excluded=excluded, facets=facets, groups=groups,
                status=STATUS,
                counts=dict(total=len(items), ready=sum(i["ready"] for i in items), blog=sum(i["source_kind"] != "sns" for i in items), sns=sum(i["source_kind"] == "sns" for i in items), excluded=len(excluded),
                            customer_keys=len(internal_customer_keys), no_customer_key=sum(1 for i in items if not i["customer_key"])))


def main():
    lib = build(); out = HERE / "demo" / "library.json"
    out.write_text(json.dumps(lib, ensure_ascii=False, indent=1), encoding="utf-8")
    c = lib["counts"]; print(f"라이브러리 {c['total']}명(블로그 {c['blog']} · SNS {c['sns']}) · 시뮬레이션 가능 {c['ready']} · 제외 {c['excluded']}")
    for g, v in lib["facets"].items(): print(f"  {g}: {', '.join(v)}")
    from collections import Counter
    for g in ("동행", "목적", "시기", "숙박"):
        print(f"  [{g}] " + " · ".join(f"{k} {n}" for k, n in Counter(t['label'] for it in lib['items'] for t in it['tags'] if t['group'] == g).most_common()))


if __name__ == "__main__":
    main()
