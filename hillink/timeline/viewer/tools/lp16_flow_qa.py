"""CL-1025-29 — LP-16 첫 5명(QA16_ alias) 개발 격리 실행: 실제 flow_run.main()(= /api/flow 가 부르는 코드)을 이 프로세스 안에서만 확장해 돌립니다.

  python3 tools/lp16_flow_qa.py --qa /tmp/lp16_qa --out /tmp/cl29/flow [--clean] [--variant V0|V1|V2]

변형(CL-1025-30 · 모두 격리 QA 후보 — 공식 의미 계약 아님)
· V0  CL-29 그대로: 미검수 극성을 neutral 로 합성 → importer 가 성향 근거로 소비(CD-11 이 문제로 지적한 경로 · 비교 기준)
· V1  CD-11 제안 후보: 사람 의미 검수 승인 0건 → 62개 전부 점수 projection 밖(성향 · 업장 실적 · 활동 가중 기여 0). 원자 사실 · 계보는 보존
· V2  관측 행동만(미승인 추정 경계): 성향(극성 기반) 기여 0 은 V1 과 같고, 워커힐 직접 관측 행동(OBSERVED) 사실만 '이 활동을 실제로 했음'
      재현 가중 · 근거 표시에 사용. NOT_DONE · CLOSED_INCOMPLETE · OTHER_CONTEXT · 범위 밖은 제외. 상태는 LP 원본 필드에서 Claude 가 도출(LP-16C 집계와 대조) · MEANING_PENDING
표시용 요지: 모든 변형에서 근거 요지(traits.evidence_index.gist)를 최소 안전 요지로 바꿔 응답에 실음(건강 · 아동 세부 제거 · 동행 범주 유지).
  선택 근거 판정용 내부 요지(라이브러리 engine.facts)는 그대로 두고 응답에는 실리지 않음을 출력 검사로 확인.

격리 원칙
· 디스크의 정본 목록(turn_personas_*.json · persona_library*.json · persona_publish.json)과 AD.DEMO 는 바꾸지 않습니다.
  이 프로세스의 메모리에서만 AD.load_all_personas · AD.load_inputs · AD.DEMO 를 감싸 QA16_ 5명을 덧붙입니다(웹 서버 /api/flow 는 별도 프로세스라 영향 없음).
· 입력 = lp16_candidate_convert_qa.py 결과(traits_qa.json · converted_v42_facts.PRIVATE.json, 원문 anchor SHA 검증 통과분).
  라이브러리 항목은 변환된 사실만으로 최소 구성(type_group = LP 공식 대표 유형 라벨, engine.facts = 변환 사실, 범위 밖 제외 사실은 hidden).
· 출력은 --out(비공개 /tmp)에만. 결과 JSON 에는 flow_run 의 FORBIDDEN 검사가 그대로 적용됩니다. LLM 호출 0.
· 결과는 개발 격리 QA 입니다. 제품 RUNNABLE 이 아닙니다(정식 ID · 스키마 · 사용자 승인 전).
"""
import contextlib, copy, io, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import flow_run as FR  # noqa: E402

AD = FR.AD
TYPE_LABEL = {"friends": "친구 모임", "couple_anniversary": "커플 · 기념일", "family_infant": "가족 · 영유아", "family_parents": "가족 · 부모 동반",
              "solo_rest": "혼자 휴식", "business": "업무 · 출장", "gourmet": "미식", "wellness": "웰니스", "sports": "스포츠 목적", "event": "행사 체험",
              "benefit_membership": "혜택 · 멤버십"}
PRIMARY = {"QA16_00532": "friends", "QA16_00491": "couple_anniversary", "QA16_00499": "family_infant", "QA16_00274": "friends", "QA16_00333": "family_infant"}   # LP-16A 후보(type_id 변경 없음 · 00491 · 00333 은 TYPE_REVIEW)
# CL-1025-30 — TYPE_REVIEW 2명은 type_id 는 그대로 두고, 엔진이 읽는 유형 문자열만 근거 범위로(기념일 · 영유아를 엔진 입력에서 확정하지 않음)
QA_TYPE_LABEL = {"QA16_00491": "커플(기념일 미확인)", "QA16_00333": "가족 · 아이 동반(연령 미확인)"}


INC = re.compile(r"휴관|휴무|운영 ?중단|임시 ?폐쇄|(관람|이용|입장|체험)(을|에|이)? ?(못|실패)|(관람|이용|입장|체험) ?실패")
NEG = re.compile(r"포기|못 ?했|안 ?했|하지 않|않았|으로 전환|로 전환|생략|취소")
SENSITIVE = [(r"컨디션상\s*", ""), (r"컨디션", ""), (r"아기 동반\s*|아기와\s*|아이 동행으로\s*|아이 동행\s*|아기\s*", "가족 동행 "), (r"유모차", "가족용품"),
             (r"육아용품", "가족용품"), (r"육아 중\s*", "가족 일정상 "), (r"육아", "가족"), (r"친구 엄마", "친구"), (r"엄마", ""), (r"유아 ?가구", "가구")]
SENSITIVE_RX = re.compile(r"컨디션|건강|임신|아기|아이 동행|유아|육아|유모차|엄마")


def safe_gist(g):
    """표시용 최소 안전 요지(QA 격리) — 건강 · 아동 세부 낱말 제거, 동행 일반 범주는 유지. 정식 경로는 LP 표시용 요지가 필요."""
    for a, b in SENSITIVE:
        g = re.sub(a, b, g)
    return re.sub(r"\s{2,}", " ", g).strip()


def fact_status(f, excluded):
    """LP 원본 필드에서 도출한 의미 상태(Claude 도출 · 사람 승인 아님)."""
    if f["fact_id"] in excluded:
        return "OUT_OF_SCOPE"
    if f["time_scope"] != "source_experience":
        return "OTHER_CONTEXT"
    if INC.search(f["detail"]) and not re.search(r"대체|대신", f["detail"]):
        return "CLOSED_INCOMPLETE"
    if NEG.search(f["detail"]):
        return "NOT_DONE"
    return "OBSERVED"


def project(tr, variant):
    """V1 · V2 — 극성 기반 성향 · 업장 실적 projection 을 비움(원본 traits 는 파일에 그대로)."""
    if variant == "V0":
        return tr
    t = copy.deepcopy(tr)
    for k, f in (t.get("facets") or {}).items():
        f.update(evidence=[], fact_ids=[], level=0.0, level_all=0.0, present=False)
    t["venues"] = {}
    return t


LP_MAP = {"OBSERVED": "OBSERVED", "OTHER_CONTEXT": "OTHER_CONTEXT", "NOT_DONE": "NOT_DONE", "CANCELED_CLOSED": "CLOSED_INCOMPLETE"}


def lp_status(csv_path):
    """CL-1025-31 — LP-16C 정본 행동 상태(SAFE_CLAUDE_FACT_BOUNDARY_IDS_ONLY.csv · ID · 상태만). 극성 값은 읽지 않음(UNKNOWN_NOT_ASSIGNED 62/62 · 승인 0)."""
    import csv
    return {r["fact_id"]: LP_MAP[r["behavior_occurrence"]] for r in csv.DictReader(open(csv_path, encoding="utf-8-sig"))}


def qa_inputs(qa_dir: Path, variant="V0", safe=True, lp=None):
    P, lib = {}, {}
    for d in sorted(qa_dir.glob("QA16_*")):
        alias = d.name
        rep = json.loads((d / "report.json").read_text(encoding="utf-8"))
        if rep.get("convert_status") != "CONVERT_READY":
            continue
        tr = json.loads((d / "traits_qa.json").read_text(encoding="utf-8"))
        conv = json.loads((d / "converted_v42_facts.PRIVATE.json").read_text(encoding="utf-8"))
        excl = {x["fact_id"] for x in rep["excluded"]}
        tr = project(tr, variant)
        for fid, e in (tr.get("evidence_index") or {}).items() if safe else ():
            if e.get("gist"):
                e["gist"] = safe_gist(e["gist"])
        for fk, fc in (tr.get("facets") or {}).items() if safe else ():
            for e in fc.get("evidence") or []:
                if e.get("gist"):
                    e["gist"] = safe_gist(e["gist"])
        P[alias] = dict(id=alias, label=f"{alias} · QA 격리", companion=None, source_post_count=tr.get("source_post_count"), active_fact_count=tr.get("active_fact_count"), traits=tr)
        facts = {}
        for f in conv["v42_facts"]:
            st = "OUT_OF_SCOPE" if f["fact_id"] in excl else (lp or {}).get(f["fact_id"]) or fact_status(f, excl)   # LP 정본 상태가 있으면 그것(범위 밖 제외는 제품 범위 축으로 따로)
            hid = f["fact_id"] in excl if variant == "V0" else True if variant == "V1" else st != "OBSERVED"
            facts[f["fact_id"]] = dict(gist=f["detail"], features=[f["feature_key"]], wh=f["time_scope"] == "source_experience",   # 변환기: scope_original == walkerhill_property → source_experience
                                       exp=f["experience_key"], kind=f["kind"], hidden=hid, post=f["post_id"], status=st)
        ev = {}
        for fid, x in facts.items():   # 사건(경험 키) 단위 출처 — 워커힐 직접(source_experience) / 다른 곳 · 과거. 라이브러리 wh_events · other_events 와 같은 모양
            if not x["hidden"]:
                ev.setdefault(("wh" if x["wh"] else "other", x["exp"]), []).append(fid)
        wh_events = [dict(event_id=k, facts=v) for (w, k), v in sorted(ev.items()) if w == "wh"]
        other_events = [dict(event_id=k, facts=v) for (w, k), v in sorted(ev.items()) if w == "other"]
        lib[alias] = dict(id=alias, group="qa_isolated", type=QA_TYPE_LABEL.get(alias, TYPE_LABEL[PRIMARY[alias]]), type_group=QA_TYPE_LABEL.get(alias, TYPE_LABEL[PRIMARY[alias]]), type_id=PRIMARY[alias], engine=dict(facts=facts),
                          wh_events=wh_events, other_events=other_events, visit_feature_summary={})
    return P, lib


def install(qa_dir: Path, variant="V0", safe=True, lp=None):
    QP, QL = qa_inputs(qa_dir, variant, safe, lp)
    base_lap, base_li = AD.load_all_personas, AD.load_inputs

    def lap():
        P = base_lap()
        P.update(QP)
        return P

    def li():
        P, bars, lib = base_li()
        lib = dict(lib, **QL)
        return P, bars, lib

    AD.load_all_personas = lap
    AD.load_inputs = li
    AD.DEMO = list(AD.DEMO) + [k for k in QP if k not in AD.DEMO]   # 메모리 한정(파일 · 서버 불변)
    return sorted(QP)


def flow(q: dict) -> dict:
    buf = io.StringIO()
    old = sys.stdin
    sys.stdin = io.StringIO(json.dumps(q, ensure_ascii=False))
    try:
        with contextlib.redirect_stdout(buf):
            FR.main()
    finally:
        sys.stdin = old
    return json.loads(buf.getvalue())


if __name__ == "__main__":
    a = sys.argv[1:]
    get = lambda k, d: a[a.index(k) + 1] if k in a else d
    qa, out = Path(get("--qa", "/tmp/lp16_qa")), Path(get("--out", "/tmp/cl29/flow"))
    if "--clean" in a:
        os.environ["HILLINK_CLEAN_INPUT"] = "1"
    out.mkdir(parents=True, exist_ok=True)
    ids = install(qa, get("--variant", "V0"), "--no-safe-gist" not in a, lp_status(get("--lp-status", None)) if "--lp-status" in a else None)
    REVIEW = {"QA16_00274": ("DOUGLAS", 2), "QA16_00491": ("DOUGLAS", 2), "QA16_00532": ("DOUGLAS", 3), "QA16_00499": ("VISTA", 3), "QA16_00333": ("GRAND", 3)}   # 후기 숙박 건물 · 확인된 최소 인원
    runs = {}
    for pid in ids:
        runs[f"{pid}_default"] = flow({"personas": [pid], "mode": "one", "seed": 0})
        b, n = REVIEW[pid]
        runs[f"{pid}_review_stay"] = flow({"personas": [pid], "mode": "one", "seed": 0, "visit_override": {pid: {"stay": True, "building": b, "phase": "mid", "party_size": n}}})
    runs["concurrent5"] = flow({"personas": ids, "mode": "many", "seed": 0})
    runs["concurrent16"] = flow({"personas": list(FR.AD.DEMO), "mode": "many", "seed": 0})
    for iv in ("wine_fair_1300", "pizzahill_full", "pool_check"):
        runs[f"concurrent5_{iv}"] = flow({"personas": ids, "mode": "many", "seed": 0, "intervention": iv})
    for k, v in runs.items():
        (out / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: ("ERROR " + v.get("code", "")) if "error" in v else "OK" for k, v in runs.items()}, ensure_ascii=False, indent=1))
