"""CL-1025-28 — LP-16 첫 5명 candidate/ → 현행 엔진 입력(V4.2 사실 → V1.1 importer → 측정 계약) 격리 QA 변환기.

공식 Import 아님:
- 출력은 --out(기본 /tmp/lp16_qa) 비공개 폴더에만 씁니다. turn_personas_ext*.json · persona_library*.json · DEMO · 게시 목록에는 쓰지 않습니다.
- runtime ID · P-ID 를 만들지 않습니다. 기술 시험용 별칭은 QA16_<원 ID 숫자>(UI · 정본 미반영)입니다.

하는 일:
1) candidate/facts_events_evidence.json 사실을 V4.2 사실(author_validation_v4_2/team_profile.schema.json $defs/fact)로 옮깁니다.
   필드마다 출처를 기록합니다: COPIED · MAPPED · DERIVED · SYNTHESIZED_NEUTRAL · PRIVATE_ANCHOR.
   스키마 검사는 우회하지 않습니다. 원문 인용이 없으면 anchors 가 비어 FAIL 로 남습니다.
2) --private-anchors 를 주면 private/fact_evidence_origins_PRIVATE.json 의 인용 · 위치만 붙입니다(URL · 블로그 ID · 행 번호는 읽지 않음).
   인용 SHA256 = candidate anchor_sha256 이어야 붙입니다.
3) 제품 범위 밖 주제(포장 · 대기 · 줄 서기 · 좌석)는 소비 입력에서 빼고 excluded 로 보존합니다(CL-27 규칙과 같음).
4) daily_behavior_candidate 의 근거 관계(SAME_BEHAVIOR_OBSERVED · CONTEXT_TRANSFER_INFERENCE · HYPOTHESIS_ONLY)를 사실별로 보존합니다.
   가설 문장(plausible_*_HYPOTHESIS)은 근거로 옮기지 않습니다.
5) 현행 엔진 변환기 V11.build_traits_v42_plus → apply_measurement_contract 로 traits 를 만듭니다(수정 없이 호출).
   그 뒤 하지 않은 경험의 업장 '실제 이용' 기록을 뺍니다(CL-27 규칙).
6) 점검: 사실 스키마 · 제외 사실 미소비 · 근거 ID ⊆ 사실 ID · 출력에 URL · 이메일 없음 · 성향 · 업장 연결 수.

사용: python3 tools/lp16_candidate_convert_qa.py <LP first5 personas 폴더> [--private-anchors] [--out /tmp/lp16_qa]
"""
import argparse, copy, hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PL = HERE.parent / "experiments" / "persona_live"
sys.path.insert(0, str(PL))
from operator_choice.operator_world_v1_1 import importer as V11  # noqa: E402
from operator_choice.operator_world_v1_1.candidate_import import apply_measurement_contract  # noqa: E402
from operator_choice.autonomy_v1.agent_day import OUT_OF_SCOPE, NEG_DONE  # noqa: E402

SCHEMA = PL / "operator_choice" / "author_validation_v4_2" / "team_profile.schema.json"
KIND_DIM = {"participation": "participation_history", "purchase": "participation_history", "revisit": "revisit_expression", "appraisal": "post_appraisal",
            "comparison": "prepurchase_criteria", "preference": "specific_preference", "motive": "prepurchase_criteria", "decline": "prepurchase_criteria",
            "expectation": "new_experience_trial"}
PARTY_CTX = {"couple": "partner", "friends": "friends", "family_kids": "kids", "family_parents": "parents", "solo": "solo"}
# LP 원본 ID 접두 'WH-' 가 측정 계약의 워커힐 경험 판정(WH_KEY = WH|VISTA|WALKERHILL)을 잘못 통과시킴(외부 호텔 경험이 워커힐 업장 이용으로 연결)
#  → 경험 키에서 고객 접두를 떼고, LP 의 명시 필드 scope_original == walkerhill_property 인 경험에만 _WH 표지를 붙인다
WH_KEY = re.compile(r"WH|VISTA|WALKERHILL")
EXCLUDE_EXTRA = re.compile(r"대기열|대기 ?줄|줄이 길|대기 없[는이]|기다리고|오픈런|좌석|창가석|자리를? ?(확보|잡)")   # 범위 밖 주제(대기 · 줄 · 좌석) 보강 — 변환기 한정 · 11명 runtime 규칙은 그대로
NOT_DONE_EXTRA = re.compile(r"취소|생략")                 # 하지 않은 경험 보강(변환기 한정)
IDENT = re.compile(r"https?://|blog\.naver|instagram\.com|[\w.+-]+@[\w-]+\.[a-z]{2,}")


def map_actor(a):
    a = str(a or "")
    if re.search(r"pending|unverified|uncertain|claimed", a):
        return "unknown", "MAPPED(지불 · 인과 미확정 → unknown)"
    if a.startswith("other"):
        return "other", "MAPPED"
    if a.startswith("author"):
        return "author", "MAPPED(작성자 포함 동행 → author)"
    return "unknown", "MAPPED(미상)"


def map_conf(c):
    m = re.match(r"(high|medium|low)", str(c or ""))
    return (m.group(1), "MAPPED(접두 등급)") if m else ("medium", "SYNTHESIZED_NEUTRAL(등급 없음 → medium)")


def convert_fact(f, anchors_priv, keyidx=None):
    prov = {}
    out = dict(post_id=f["post_id"], fact_id=f["fact_id"]); prov.update(post_id="COPIED", fact_id="COPIED")
    raw = f.get("experience_key_PROVISIONAL") or f["event_id"]
    rest = re.sub(r"^WH-(\d+)_?", "", raw); num = (re.match(r"^WH-(\d+)", raw) or re.match(r".*?(\d+)", f["fact_id"])).group(1)
    wh = f.get("scope_original") == "walkerhill_property"
    keyidx = {} if keyidx is None else keyidx
    n = keyidx.setdefault(raw, len(keyidx) + 1)
    # CL-29 — 원본 경험 키의 낱말(예: 여행 목적 · 동행 묘사)은 건강 · 가족 정보가 섞일 수 있고 표시 경로로 새어 나갈 수 있어 쓰지 않는다.
    # 같은 원본 키 = 같은 중립 번호(사건 단위 유지). 워커힐 여부는 scope_original 로만: _WH (측정 계약 WH_KEY · profile_context 의 WH 판정 둘 다 통과)
    out["experience_key"] = f"LP16_{num}_X{n:02d}" + ("_WH" if wh else "")
    prov["experience_key"] = "MAPPED_NEUTRAL(원본 키 → 사건 번호 · 낱말 미사용" + (" · scope_original=walkerhill_property → _WH)" if wh else ")")
    out["feature_key"] = "lp16_" + re.sub(r"[^A-Za-z0-9_]", "_", f["fact_id"]).lower(); prov["feature_key"] = "SYNTHESIZED_NEUTRAL(원본에 없음 · 의미 없는 키)"
    out["detail"] = f.get("detail_intermediate_not_observation_approval") or ""; prov["detail"] = "COPIED(중간 요약 · 관측 승인 아님)"
    out["kind"] = f.get("kind_original"); prov["kind"] = "COPIED"
    out["dimension"] = KIND_DIM.get(out["kind"], "participation_history"); prov["dimension"] = "DERIVED(kind → dimension)"
    out["actor"], prov["actor"] = map_actor(f.get("actor_original"))
    out["time_scope"] = "source_experience" if f.get("scope_original") == "walkerhill_property" else "historical"; prov["time_scope"] = "DERIVED(scope_original)"
    out["action_stage"] = f.get("action_stage_original"); prov["action_stage"] = "COPIED"
    out["polarity"] = "neutral"; prov["polarity"] = "SYNTHESIZED_NEUTRAL(원본 극성 미검수 · 사람 검수 필요)"
    out["confidence"], prov["confidence"] = map_conf(f.get("original_confidence"))
    out["common_dimensions"] = []; prov["common_dimensions"] = "SYNTHESIZED_NEUTRAL(빈 목록)"
    a = anchors_priv.get(f["fact_id"])
    out["anchors"] = [a] if a else []
    prov["anchors"] = "PRIVATE_ANCHOR(인용 SHA 일치)" if a else "MISSING(비공개 인용 없이 실행)"
    return out, prov


def private_anchors(pdir, cand_facts):
    p = pdir / "private" / "fact_evidence_origins_PRIVATE.json"
    if not p.exists():
        return {}, "NO_PRIVATE_FILE"
    want = {f["fact_id"]: (f.get("anchors") or [{}])[0].get("anchor_sha256") for f in cand_facts}
    out, bad = {}, 0
    for x in json.loads(p.read_text(encoding="utf-8")):
        q = x.get("quote_PRIVATE") or ""
        if q and hashlib.sha256(q.encode()).hexdigest() == x.get("anchor_sha256") == want.get(x.get("fact_id")):
            out[x["fact_id"]] = dict(span=[int(x["anchor_start"]), int(x["anchor_end"])], quote=q)
        else:
            bad += 1
    return out, f"ATTACHED {len(out)} · SHA_MISMATCH {bad}"


def relations(pdir):
    b = json.loads((pdir / "candidate" / "daily_behavior_candidate.json").read_text(encoding="utf-8"))
    rel = {}
    for k, v in (b["facets"].items() if isinstance(b["facets"], dict) else b["facets"]):
        for fid in v.get("same_behavior_fact_ids") or []:
            rel.setdefault(fid, set()).add("SAME_BEHAVIOR_OBSERVED")
        for fid in v.get("cross_context_fact_ids") or []:
            rel.setdefault(fid, set()).add("CONTEXT_TRANSFER_INFERENCE")
        if v.get("evidence_relation") == "HYPOTHESIS_ONLY":
            for fid in v.get("source_fact_ids_for_inference") or []:
                rel.setdefault(fid, set()).add("HYPOTHESIS_ONLY(이 facet 은 가설 · 근거로 쓰지 않음)")
    return {k: sorted(v) for k, v in rel.items()}


def lp_occurrence(csv_path):
    """CL-1025-32 — LP-16C 안전 정본(ID · 상태만)에서 행동 발생 · 워커힐 직접 여부만 읽음(극성 값 미사용)."""
    import csv
    return {r["fact_id"]: (r["behavior_occurrence"], r["direct_walkerhill_experience"]) for r in csv.DictReader(open(csv_path, encoding="utf-8-sig"))} if csv_path else {}


def split_scope(detail):
    """'·' 로 나뉜 절 가운데 범위 밖 주제가 없는 절만 → (소비 절, 비소비 절)."""
    parts = [x.strip() for x in re.split(r"\s*·\s*", detail) if x.strip()]
    bad = lambda x: OUT_OF_SCOPE.search(x) or EXCLUDE_EXTRA.search(x)
    return [x for x in parts if not bad(x)], [x for x in parts if bad(x)]


def run(pdir: Path, use_private: bool, lp=None):
    sid = pdir.name
    alias = "QA16_" + re.sub(r"\D", "", sid)
    fe = json.loads((pdir / "candidate" / "facts_events_evidence.json").read_text(encoding="utf-8"))
    dm = json.loads((pdir / "candidate" / "display_manifest.json").read_text(encoding="utf-8"))
    anc, anc_note = private_anchors(pdir, fe["facts"]) if use_private else ({}, "NOT_REQUESTED")
    facts, prov, excluded, keyidx, partial, originals = [], {}, [], {}, [], {}
    for f in fe["facts"]:
        g, p = convert_fact(f, anc, keyidx)
        if OUT_OF_SCOPE.search(g["detail"]) or EXCLUDE_EXTRA.search(g["detail"]):
            keep, drop = split_scope(g["detail"])
            occ = (lp or {}).get(g["fact_id"])
            if occ == ("OBSERVED", "YES") and keep and drop:   # CL-1025-32 — 같은 사실 안의 관측 행동(소비)과 범위 밖 맥락(비소비)을 독립 태그로. 원문 · 앵커 불변
                p["detail"] = "PARTIAL_OBSERVED(LP OBSERVED · 범위 밖 절 비소비 · 원 요약은 detail_original)"
                g = dict(g, detail=" · ".join(keep)); p["scope_context_excluded"] = len(drop)
                partial.append(dict(fact_id=g["fact_id"], consumed_clauses=len(keep), excluded_clauses=len(drop), tag="scope_context_excluded"))
                originals[g["fact_id"]] = f["detail_intermediate_not_observation_approval"]
            else:
                excluded.append(dict(fact_id=g["fact_id"], why="제품 범위 밖 주제(포장 · 대기 · 줄 서기 · 좌석) — 소비 입력 제외 · 원본 보존"))
                continue
        facts.append(g); prov[g["fact_id"]] = p
    import jsonschema
    S = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fv = jsonschema.Draft202012Validator({"$schema": S.get("$schema"), "$defs": S["$defs"], "$ref": "#/$defs/fact"})
    schema_err = {g["fact_id"]: sorted({(".".join(str(x) for x in e.absolute_path) or "(fact)") + ":" + e.validator for e in fv.iter_errors(g)}) for g in facts}
    schema_err = {k: v for k, v in schema_err.items() if v}
    ctx = PARTY_CTX.get(dm.get("party_type"))
    pids = {x["fact_id"] for x in partial}
    doc = {"STRUCTURED_PROFILE": {"persona_id": alias, "facts": [g for g in facts if g["fact_id"] not in pids]}}   # CL-1025-32 — 부분 관측은 성향 · 업장 점수 projection 에 넣지 않음(관측 계층만)
    traits, mc_audit = apply_measurement_contract(doc, V11.build_traits_v42_plus(doc, visit_companion=ctx))
    for g in facts:
        if g["fact_id"] in pids:   # 관측 계층: 근거 색인에만(점수 · 성향 · 업장 실적 기여 0)
            traits.setdefault("evidence_index", {})[g["fact_id"]] = dict(fact_id=g["fact_id"], gist=g["detail"], experience=g["experience_key"], kind=g["kind"], layer="OBSERVATION_ONLY_PARTIAL")
    not_done = []
    for v, xs in list((traits.get("venues") or {}).items()):
        keep = []
        for x in xs:
            det = lambda fid: next((g["detail"] for g in facts if g["fact_id"] == fid), "")
            if x["kind"] == "used" and all(NEG_DONE.search(det(fid)) or NOT_DONE_EXTRA.search(det(fid)) for fid in x["fact_ids"]):
                not_done.append(dict(venue=v, fact_ids=x["fact_ids"], why="하지 않은 경험 — 업장 실제 이용 기록에서 제외"))
            else:
                keep.append(x)
        traits["venues"][v] = keep
    rel = relations(pdir)
    for fid, e in (traits.get("evidence_index") or {}).items():
        e["lp_relation"] = rel.get(fid, ["UNLINKED(일상 행동 facet 에 연결 없음)"])
    fids = {g["fact_id"] for g in facts}
    used_ev = {e["fact_id"] for f in traits["facets"].values() for e in f.get("evidence") or []}
    checks = {
        "fact_schema_pass": f"{len(facts) - len(schema_err)}/{len(facts)}",
        "excluded_not_consumed": not ({x["fact_id"] for x in excluded} & (used_ev | {i for xs in traits['venues'].values() for x in xs for i in x['fact_ids']})),
        "evidence_subset_of_facts": used_ev <= fids,
        "no_url_email_in_traits": not IDENT.search(json.dumps(traits, ensure_ascii=False)),
        "facets_present": sorted(k for k, f in traits["facets"].items() if f.get("present")),
        "venues": {v: [x["kind"] for x in xs] for v, xs in traits["venues"].items() if xs},
    }
    status = "CONVERT_READY" if not schema_err and all(checks[k] for k in ("excluded_not_consumed", "evidence_subset_of_facts", "no_url_email_in_traits")) else "BLOCKED"
    report = dict(source_profile_id=sid, qa_alias=alias, alias_scope="QA 전용 · UI · 정본 · runtime 미반영", visit_companion_ctx=ctx,
                  facts_in=len(fe["facts"]), facts_converted=len(facts), excluded=excluded, partial_observed=partial, not_done_venue_removed=not_done,
                  private_anchors=anc_note, schema_errors=schema_err, field_provenance_summary=_summ(prov), checks=checks,
                  measurement_contract_changes=len(mc_audit), convert_status=status,
                  lp_relation_counts={k: sum(1 for v in rel.values() if k in " ".join(v)) for k in ("SAME_BEHAVIOR_OBSERVED", "CONTEXT_TRANSFER_INFERENCE", "HYPOTHESIS_ONLY")})
    return report, dict(v42_facts=facts, field_provenance=prov, detail_original_PRIVATE=originals), traits


def _summ(prov):
    out = {}
    for p in prov.values():
        for k, v in p.items():
            out.setdefault(k, set()).add(v)
    return {k: sorted(v) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("personas_dir"); ap.add_argument("--private-anchors", action="store_true"); ap.add_argument("--out", default="/tmp/lp16_qa"); ap.add_argument("--lp-status", default=None)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    allrep = []
    for pdir in sorted(Path(a.personas_dir).iterdir()):
        if not (pdir / "candidate" / "facts_events_evidence.json").exists():
            continue
        rep, conv, traits = run(pdir, a.private_anchors, lp_occurrence(a.lp_status))
        d = out / rep["qa_alias"]; d.mkdir(exist_ok=True)
        (d / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "converted_v42_facts.PRIVATE.json").write_text(json.dumps(conv, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "traits_qa.json").write_text(json.dumps(traits, ensure_ascii=False, indent=1), encoding="utf-8")
        allrep.append({k: rep[k] for k in ("source_profile_id", "qa_alias", "facts_in", "facts_converted", "private_anchors", "convert_status")} | {"schema_fail": len(rep["schema_errors"]), "excluded": len(rep["excluded"]), "partial_observed": len(rep["partial_observed"]), "not_done_venue_removed": len(rep["not_done_venue_removed"]), "facets_present": len(rep["checks"]["facets_present"]), "venues": rep["checks"]["venues"]})
    (out / "SUMMARY.json").write_text(json.dumps(allrep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(allrep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
