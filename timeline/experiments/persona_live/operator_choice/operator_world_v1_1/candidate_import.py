"""운영 월드 V1.1 후보 — 가져오기 측정 계약(V1.1 importer 출력 위에 얹는 후처리 · importer.py 는 수정하지 않음)

M-1 할인 근거 구분
    importer 는 '할인 · 카드 · 쿠폰'이 나온 사실을 모두 혜택 성향(benefit · discount/card 태그)으로 연결한다.
    측정 계약은 셋을 구분한다.
      changed    : 할인 때문에 선택을 바꿨다고 원문에 적힘(예: 할인 상품을 골라 구매)          → 할인 반응 근거(대표)
      considered : 할인 수단을 비교 · 확인함(선택 대상이 아니라 결제 수단)                      → 약한 근거(기존 weak 등급 · 새 값 없음)
      used       : 할인을 사용했다는 기록만                                                      → 할인 반응 근거에서 뺌(사실 기록은 감사표에 보존)
    원문 근거가 불명확하면 changed 로 올리지 않는다(규칙에 맞지 않으면 used).
    포함 혜택(package · voucher 태그)은 바꾸지 않는다 — 포함 혜택 사용 이력은 고객 × 혜택 구조로 별도 검증할 과제.

M-2 업장 식별
    importer 의 업장 어휘는 시설 유형('수영장' · '사우나' · '룸서비스' · '뷔페')도 워커힐 업장으로 연결한다.
    측정 계약: 그 경험(experience_key)이 워커힐 방문으로 확인될 때만 워커힐 업장 이력으로 둔다.
      워커힐 확인 = 경험 키에 WH · VISTA · WALKERHILL 이 있거나, 같은 경험의 사실 요지에 워커힐 · 비스타 또는 워커힐 고유 업장명이 나옴
      피자힐 · 명월관 · 온달 · 금룡 · 르파사쥬 · 스카이야드 · 모에기 같은 고유 업장명이 사실 자체에 있으면 워커힐로 봄
      확인되지 않으면 월드 업장 이력에 연결하지 않고 '시설 유형 경험(비활성)'으로 보존
    같은 업장의 실제 방문은 experience_key 로 중복 제거(같은 방문의 여러 사실이 이용 횟수를 늘리지 않음 · candidate.C-2b 가 사용)

C-4 방문 상태 자동 연결
    visit_from_experience(doc, experience_key): 그 방문의 사실에서 원문에 적힌 상태만 꺼내 방문 조건으로 옮긴다.
      음주: 그 방문에서 음주하지 않았다고 적힘 → alcohol_eligible=False
      동행: 그 방문 사실의 동행 어휘 → 기존 V1.1 동행 방문 변형(COMPANION_VISITS)의 companions · party_size 만 사용(새 값 없음)
    과거 방문 상태를 미래 방문의 성향으로 쓰지 않는다 — 이 함수는 '그 방문을 재현할 때'만 쓴다. 출처는 state_observed 로 남긴다.
"""
from __future__ import annotations

import copy
import re

from operator_choice.operator_world_v1 import profile_adapter as PA
from operator_choice.operator_world_v1_1 import importer as V11

DEAL_CHANGED = r"할인\S*\s*(때문에|덕분에|을 보고|보고|이 있어|있어서|에 끌려)|할인\s?(와인|상품|메뉴|품목|가격)\S*\s?(을|를)?\s?골|할인된\s?\S+\s?(을|를)?\s?(골|선택)|싸서\s?(골|선택|예약|샀)|쿠폰(이|을)?\s?(있어|보고|때문)"
DEAL_CONSIDERED = r"할인\s?수단|비교해|따져|확인해 달라|확인해달라|어느 카드|카드를 하나씩"
WH_KEY = r"WH|VISTA|WALKERHILL"
WH_TEXT = r"워커힐|비스타|피자힐|명월관|온달|금룡|르\s?파사쥬|스카이야드|모에기|더뷔페"
WH_PROPER = {"PIZZA_HILL": r"피자힐", "MYONGWOLGWAN": r"명월관", "ONDAL": r"온달", "GEUMRYONG": r"금룡", "LE_PASSAGE": r"르\s?파사쥬",
             "SKYARD": r"스카이야드"}
DEAL_USED = r"사용|적용|받(았|고|아)|이용|썼|결제|청구|면제"
OTHER_PROPERTY = r"하얏트|메리어트|롯데|시그니엘|씨마크|파라스파라|파라다이스|인스파이어|조선|포시즌스|신라|레스케이프|소피텔|파르나스|풀만|나루|몬드리안|아난티|델피노|세부|발리|파리|라오스|방비엥|타이둥|보홀|교토|오사카|제주|강릉|고성"
NO_ALCOHOL = r"음주하지 않|술(을|도)?\s?(마시지|못\s?마시|안\s?마시)|비음주"


def _facts(doc: dict) -> dict:
    return {f["fact_id"]: f for f in doc["STRUCTURED_PROFILE"]["facts"]}


def deal_class(text: str) -> str:
    """changed(선택이 바뀜) · considered(고려·비교) · used(사용) · undetermined(원문만으로 판단 불가)"""
    if re.search(DEAL_CHANGED, text):
        return "changed"
    if re.search(DEAL_CONSIDERED, text):
        return "considered"
    if re.search(DEAL_USED, text):
        return "used"
    return "undetermined"


def wh_experiences(doc: dict) -> set:
    by = {}
    for f in doc["STRUCTURED_PROFILE"]["facts"]:
        by.setdefault(f.get("experience_key") or f["fact_id"], []).append(f)
    out = set()
    for k, fs in by.items():
        if re.search(WH_KEY, k) or any(re.search(WH_TEXT, f.get("detail", "")) for f in fs):
            out.add(k)
    return out


def apply_measurement_contract(doc: dict, traits: dict, deal: bool = True, venue: bool = True,
                               considered: str = "weak", venue_rule: str = "m2") -> tuple[dict, list[dict]]:
    """importer 출력(traits)에 M-1 · M-2 를 적용한 사본과 변경 감사 목록을 돌려준다.
    considered: "weak"(기준선 R-BASE) | "record"(고려 사실로만 보존 · 할인 반응 근거 아님)
    venue_rule: "m2"(기준선 R-BASE: 같은 경험 요지의 워커힐 언급도 인정) | "strict"(venue_records 의 matched_* 만)"""
    t = copy.deepcopy(traits)
    F = _facts(doc)
    audit = []
    if deal:
        keep = []
        for e in t["facets"]["benefit"]["evidence"]:
            if e["grade"] != "exclude" and set(e["tags"]) & {"discount", "card"}:
                c = deal_class((F.get(e["fact_id"]) or {}).get("detail", ""))
                if c in ("used", "undetermined") or (c == "considered" and considered == "record"):
                    audit.append(dict(rule="M-1", fact_id=e["fact_id"], before=f"benefit:{e['grade']}:{e['tags']}", after={"used": "제외(할인 사용 기록)", "undetermined": "제외(판단 불가 · 보존)", "considered": "제외(고려 사실로만 보존)"}[c], reason=c))
                    continue
                if c == "considered" and e["grade"] == "rep":
                    audit.append(dict(rule="M-1", fact_id=e["fact_id"], before="benefit:rep", after="benefit:weak", reason=c))
                    e = dict(e, grade="weak")
                elif c == "changed":
                    audit.append(dict(rule="M-1", fact_id=e["fact_id"], before=f"benefit:{e['grade']}", after=f"benefit:{e['grade']}(유지)", reason=c))
            keep.append(e)
        t["facets"]["benefit"]["evidence"] = keep
    if venue and venue_rule == "strict":
        recs = {r["fact_id"]: r for r in venue_records(doc, t)}
        venues, inactive = {}, []
        for v, xs in t.get("venues", {}).items():
            for x in xs:
                r = recs.get(x["fact_ids"][0])
                if r and r["venue_match_status"].startswith("matched"):
                    venues.setdefault(v, []).append(dict(x, venue_match_status=r["venue_match_status"], place_evidence=r["place_evidence"]))
                else:
                    st = r["venue_match_status"] if r else "pending"
                    inactive.append(dict(x, venue_type=v, venue_match_status=st))
                    audit.append(dict(rule="M-2s", fact_id=x["fact_ids"][0], before=f"venues[{v}].{x['kind']}", after=f"연결 보류({st})",
                                      reason=(r or {}).get("place_evidence", "")))
        t["venues"] = venues
        t["facility_type_history"] = inactive
    elif venue:
        wh = wh_experiences(doc)
        venues, inactive = {}, []
        for v, xs in t.get("venues", {}).items():
            for x in xs:
                f0 = F.get(x["fact_ids"][0]) or {}
                proper = WH_PROPER.get(v) and re.search(WH_PROPER[v], f0.get("detail", ""))
                ok = bool(proper) or (x.get("experience") in wh)
                if ok:
                    venues.setdefault(v, []).append(x)
                else:
                    inactive.append(dict(x, venue_type=v))
                    audit.append(dict(rule="M-2", fact_id=x["fact_ids"][0], before=f"venues[{v}].{x['kind']}", after="시설 유형 경험(비활성)",
                                      reason=f"워커힐 방문 미확인: {x.get('experience')}"))
        t["venues"] = venues
        t["facility_type_history"] = inactive
    PA._finish(t["facets"])
    return t, audit


WH_NAMES = r"워커힐|비스타|그랜드\s?워커힐|더\s?글라스"


def venue_records(doc: dict, traits: dict) -> list[dict]:
    """업장 구조화 필드(후보 규격): facility_type · venue_id · brand_or_property · experience_key · place_evidence · venue_match_status.
    matched_explicit      : 그 사실 요지에 워커힐 고유 업장명 또는 워커힐 · 비스타가 나옴
    matched_by_experience : 경험 키가 워커힐 숙박·방문 구간(WH · VISTA · WALKERHILL)이고 그 사실에 다른 숙소명이 없음
    external              : 그 사실이나 경험 키에 다른 숙소·지역명이 나옴
    pending               : 그 밖(같은 후기에 워커힐이 나온다는 것만으로는 연결하지 않음) — 삭제하지 않고 보류"""
    F = _facts(doc)
    out = []
    for v, xs in traits.get("venues", {}).items():
        for x in xs:
            fid = x["fact_ids"][0]
            f = F.get(fid) or {}
            d = f.get("detail", "")
            k = x.get("experience") or f.get("experience_key") or ""
            proper = WH_PROPER.get(v)
            if (proper and re.search(proper, d)) or re.search(WH_NAMES, d):
                st, ev, brand = "matched_explicit", (re.search(proper, d).group(0) if proper and re.search(proper, d) else re.search(WH_NAMES, d).group(0)), "워커힐"
            elif re.search(OTHER_PROPERTY, d) or re.search(OTHER_PROPERTY.replace("|", "|"), k, re.I) or re.search(r"HYATT|MARRIOTT|LOTTE|SEAMARQ|PARASPARA|PARADISE|INSPIRE|CEBU|PARIS|DELPINO|FAMILIA|JOSUN|FOUR_SEASONS|NARU|MONDRIAN|PULLMAN|SOFITEL|ANANTI|LESCAPE|PARNAS|BALI", k):
                st, ev, brand = "external", (re.search(OTHER_PROPERTY, d).group(0) if re.search(OTHER_PROPERTY, d) else f"experience_key:{k}"), "다른 숙소"
            elif re.search(WH_KEY, k):
                st, ev, brand = "matched_by_experience", f"experience_key:{k}", "워커힐"
            else:
                st, ev, brand = "pending", f"experience_key:{k} · 사실에 장소 근거 없음", "미확인"
            out.append(dict(fact_id=fid, facility_type=v, venue_id=(v if st.startswith("matched") else None), brand_or_property=brand,
                            experience_key=k, place_evidence=ev, venue_match_status=st, kind=x["kind"]))
    return out


def visit_from_experience(doc: dict, experience_key: str, base_visit: dict) -> dict:
    """C-4(과거 재현 전용): 그 방문의 사실에서 원문에 적힌 상태만 방문 조건으로(재현용 · observed). 없는 상태는 기본값(assumed)."""
    fs = [f for f in doc["STRUCTURED_PROFILE"]["facts"] if (f.get("experience_key") or f["fact_id"]) == experience_key]
    v = dict(base_visit)
    observed = []
    # 그 방문 전체가 음주하지 않는 상태였다고 적힌 경우만(한 번 술을 안 마신 일 · 배불러 미니바에 손대지 않은 일은 방문 상태가 아님)
    na = [f["fact_id"] for f in fs if re.search(NO_ALCOHOL, f.get("detail", ""))]
    if na:
        v["alcohol_eligible"] = False
        observed.append(dict(field="alcohol_eligible", value=False, facts=na))
    comps = sorted({c for f in fs for c in V11.companions_of(f.get("detail", ""))})
    if len(comps) == 1 and comps[0] in V11.COMPANION_VISITS:
        c = V11.COMPANION_VISITS[comps[0]]
        v["companions"] = c["companions"].replace("(가정)", "(원문)")
        v["party_size"] = c["party_size"]
        observed.append(dict(field="companions", value=comps[0], facts=[f["fact_id"] for f in fs if comps[0] in V11.companions_of(f.get("detail", ""))]))
    v["visit_label"] = f"재현 방문 · {experience_key}"
    v["assumptions"] = list(base_visit.get("assumptions", [])) + [
        "재현 방문: 원문에서 관측된 상태만 옮김(" + (", ".join(o["field"] for o in observed) or "관측 상태 없음") + ") · 나머지는 기본 가정"]
    return v, observed


def visit_for_future(base_visit: dict, assumptions: dict | None = None) -> tuple[dict, list]:
    """C-4(미래 방문 가정 전용): 프로필의 과거 방문 상태를 읽지 않는다. 운영자가 준 가정만 적용하고 출처를 assumed 로 남긴다."""
    v = dict(base_visit)
    assumed = []
    for k2, val in (assumptions or {}).items():
        if k2 not in ("alcohol_eligible", "companions", "party_size", "rest_goal", "breakfast_included"):
            raise ValueError(f"unsupported_assumption:{k2}")
        v[k2] = val
        assumed.append(dict(field=k2, value=val, source="assumed"))
    v["assumptions"] = list(base_visit.get("assumptions", [])) + ["미래 방문 가정: " + (", ".join(a["field"] for a in assumed) or "기본 가정만") + " · 과거 방문 상태는 옮기지 않음"]
    return v, assumed


# ---------- M-3 포함 혜택 측정(옵션 · R-BASE 에는 없음) ----------
INCLUDED = r"라운지|해피아워|티타임|애프터눈\s?티|조식\s?포함|포함(된|한)|포함 (혜택|조건|촬영|서비스)|무료\s?(미니바|조식|입장|간식)|리조트머니|숙박권|특전|추가 서비스"
BEN_NOT_USED = r"않|못\s?(했|하|함|이용|경험)|포기|대신|늘리지"
BEN_USED = r"이용|먹|마셨|사용|받|즐기|즐겼|썼"
BEN_REASON = [("rest", r"쉬|휴식|피곤|늦잠|체력"), ("schedule", r"일정|시간이 없|맞지 않|격주"), ("price", r"가격|비싸|추가금|원\\b")]
BEN_TYPE = [("lounge", r"라운지|해피아워|티타임|애프터눈\s?티"), ("breakfast", r"조식"), ("minibar_amenity", r"미니바|캡슐|정수기|다림질"),
            ("voucher_credit", r"리조트머니|숙박권|쿠폰|크레딧"), ("service", r"촬영|서비스|특전")]


def benefit_history(doc: dict) -> list[dict]:
    """M-3: 포함 혜택에 관한 사실을 '포함 사실 · 사용 · 미사용 · 이유 · 만족'으로 나눈 기록(원문 요지 기준 · 사실 단위)."""
    out = []
    for f in doc["STRUCTURED_PROFILE"]["facts"]:
        d = f.get("detail", "")
        if not re.search(INCLUDED, d):
            continue
        used = bool(re.search(BEN_USED, d)) and not re.search(r"(이용|경험)(하지|을 하지) (못|않)", d)
        not_used = bool(re.search(BEN_NOT_USED, d))
        status = "mixed" if (used and not_used) else ("not_used" if not_used else ("used" if used else "included_only"))
        reason = next((k for k, p in BEN_REASON if re.search(p, d)), None) if status in ("not_used", "mixed") else None
        sat = "+" if re.search(r"만족|호평|좋|편하", d) else ("-" if re.search(r"아쉽|불만|불편", d) else None)
        btype = next((k for k, p in BEN_TYPE if re.search(p, d)), "other")
        out.append(dict(fact_id=f["fact_id"], experience_key=f.get("experience_key"), benefit_type=btype, status=status, reason=reason, satisfaction=sat))
    return out


def apply_benefit_history(doc: dict, traits: dict) -> tuple[dict, list[dict]]:
    """M-3 를 성향 입력에 연결(기존 질량 · 등급 · 산식만 사용 · 새 값 없음).
    사용(used · mixed) → 혜택 성향의 포함 근거(package 태그 · rep) · 미사용 + 휴식 이유 → 휴식 성향 근거(rest 태그 · rep)
    미사용 + 일정 이유 → 방문 상태 기록(성향 아님) · 포함 사실만 있는 기록 → 연결하지 않음"""
    t = copy.deepcopy(traits)
    F = _facts(doc)
    hist = benefit_history(doc)
    audit = []
    have = {(fc, e["fact_id"]) for fc, x in t["facets"].items() for e in x["evidence"]}
    for h in hist:
        f = F[h["fact_id"]]
        mass = PA.CONF_MASS.get(f.get("confidence"), PA.CONF_MASS["medium"])
        if h["status"] in ("used", "mixed") and ("benefit", h["fact_id"]) not in have:
            t["facets"]["benefit"]["evidence"].append(dict(fact_id=h["fact_id"], feature=f.get("feature_key", ""), grade="rep", tags=["package"], mass=mass,
                                                         gist=f.get("detail", ""), experience=f.get("experience_key")))
            audit.append(dict(rule="M-3", fact_id=h["fact_id"], after=f"benefit:package:rep({h['benefit_type']})", reason=h["status"]))
        if h["status"] in ("not_used", "mixed") and h["reason"] == "rest" and ("rest_need", h["fact_id"]) not in have:
            t["facets"]["rest_need"]["evidence"].append(dict(fact_id=h["fact_id"], feature=f.get("feature_key", ""), grade="rep", tags=["rest"], mass=mass,
                                                           gist=f.get("detail", ""), experience=f.get("experience_key")))
            audit.append(dict(rule="M-3", fact_id=h["fact_id"], after="rest_need:rest:rep", reason=f"{h['status']}·{h['reason']}"))
    # 같은 숙박·같은 사건의 여러 사실은 독립 사건 1건 — 같은 묶음 안에서 질량을 나눔(기존 importer 의 경험 단위 규칙과 같음)
    group = {}
    for l in doc["STRUCTURED_PROFILE"].get("experience_links", []) or []:
        if l.get("relation", "same_trip_or_event") == "same_trip_or_event":
            for i in l.get("fact_ids", []):
                group[i] = l.get("link_id") or l.get("visit_id")
    for fc in ("benefit", "rest_need"):
        added = [e for e in t["facets"][fc]["evidence"] if any(a["fact_id"] == e["fact_id"] and a["after"].startswith(fc) for a in audit)]
        cnt = {}
        for e in added:
            g = group.get(e["fact_id"]) or e.get("experience") or e["fact_id"]
            cnt[g] = cnt.get(g, 0) + 1
        for e in added:
            g = group.get(e["fact_id"]) or e.get("experience") or e["fact_id"]
            e["mass"] = round(e["mass"] / cnt[g], 4)
            e["event_group"] = g
    t["benefit_history"] = hist
    PA._finish(t["facets"])
    return t, audit
