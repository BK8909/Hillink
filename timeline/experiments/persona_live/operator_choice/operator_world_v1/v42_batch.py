"""신규 작성자 V4.2 프로파일 일괄 적용 (10/22 5차 · 다음 단계 준비)

슬기님 · 한호님이 보내는 V4.2 팀 공통 프롬프트 출력(8개 섹션 JSON)을 받아, 기존 세 작성자와 **같은 엔진 · 같은 월드 · 같은 운영 조건**으로 돌린다.
- 사실 → 성향 연결은 `auto_link`(공통 규칙)만 쓴다. 손 연결표(relevance.py)는 쓰지 않는다.
- 모델 · 외부 호출 없음. 원문 · 링크 · 닉네임은 다루지 않으며, 출력에는 사실 ID · 연결 결과 · 행동 요약만 남긴다(detail 문장 미출력).
- 출력은 '검수 전 · 시연 승인 없음'. 사람 표본 검수(사실 30~50개)와 위험 연결(제외해야 할 연결이 대표로 들어감) 집계를 함께 낸다.

사용: python3 -m operator_choice.operator_world_v1 import-v42 --in <V4.2 JSON 폴더> --out <결과 폴더>
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from . import auto_link as AL
from . import engine as EN
from . import profile_adapter as PA
from . import world as WD

SCHEMA = Path(__file__).resolve().parent.parent / "author_validation_v4_2" / "team_profile.schema.json"
REQUIRED_SECTIONS = ("SOURCE_AUDIT", "PERSONA_SUMMARY", "TRAIT_TABLE", "EVENT_ACTIONS", "EVIDENCE_MAP", "CONTEXT_RULES", "QUALITY_FLAGS", "STRUCTURED_PROFILE")
FORBIDDEN_TEXT = ("http://", "https://", "blog.naver", "m.blog")


def check_profile(doc: dict) -> list[str]:
    """V4.2 계약 확인 — 8개 섹션 · 사실 필수 필드 · 허용값(스키마 $defs.fact) · 링크 문자열 없음."""
    errs = [f"missing_section:{k}" for k in REQUIRED_SECTIONS if k not in doc]
    facts = (doc.get("STRUCTURED_PROFILE") or {}).get("facts") or []
    if not facts:
        errs.append("no_facts")
    try:
        import jsonschema
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        v = jsonschema.Draft202012Validator({"$defs": schema.get("$defs", {}), "$ref": "#/$defs/fact"})
        for f in facts:
            for e in v.iter_errors(f):
                errs.append(f"fact_schema:{f.get('fact_id')}:{e.message[:80]}")
    except ImportError:
        errs.append("jsonschema_unavailable")
    text = json.dumps(doc, ensure_ascii=False)
    if any(t in text for t in FORBIDDEN_TEXT):
        errs.append("contains_link_text")
    return errs


def link_audit(doc: dict, sample_n: int = 40, seed: int = 20261022) -> dict:
    """사실별 자동 연결 요약 + 사람 표본 검수 목록(사실 ID · 연결만)."""
    facts = doc["STRUCTURED_PROFILE"]["facts"]
    rows = []
    for f in facts:
        r = AL.link_fact(f)
        rows.append(dict(fact_id=f["fact_id"], post_id=f.get("post_id"), feature_key=f.get("feature_key"), kind=f.get("kind"), dimension=f.get("dimension"),
                         actor=f.get("actor"), time_scope=f.get("time_scope"), confidence=f.get("confidence"),
                         links={k: g for k, (g, _) in r["links"].items()}, rules=sorted({x.split(":")[-1] for x in r["rules"]})))
    rng = random.Random(seed)
    sample = rng.sample(rows, min(sample_n, len(rows)))
    return dict(n_facts=len(rows), n_linked=sum(1 for r in rows if any(g != "exclude" for g in r["links"].values())),
                n_excluded_all=sum(1 for r in rows if r["links"] and all(g == "exclude" for g in r["links"].values())),
                n_unlinked=sum(1 for r in rows if not r["links"]), rows=rows,
                review_sample=[dict(r, human_verdict=None, dangerous_link=None) for r in sample])


def run_person(doc: dict, presets: list[dict]) -> dict:
    tr = PA.build_traits_v42(doc)
    pid = tr["persona_id"]
    visit = WD.default_visit(pid)
    out = {}
    for p in presets:
        d = EN.simulate_day(tr, visit, WD.apply_levers(WD.default_world(), p["levers"]))
        top = next((s for s in d["steps"] if s["chosen"] == "WINE_FAIR"), d["steps"][0])
        out[p["id"]] = dict(stage=d["events"][0]["stage"], sequence=[(s["starts"], s["chosen"], s.get("action")) for s in d["steps"]],
                            cost=d["party_total_out_of_pocket_krw"],
                            top_reasons=[dict(text=x["text"], value=x["value"], n_evidence=x["n_evidence"]) for x in top["reasons"][:3]])
    present = {k: dict(level=v["level"], n_evidence=len(v["fact_ids"])) for k, v in tr["facets"].items() if v["present"]}
    return dict(persona_id=pid, facets=present, results=out, profile_status=tr["profile_status"], demo_approved=False, human_review="pending")


def differentiation(people: list[dict], preset_ids: list[str]) -> dict:
    """사람들 사이 행동 차이 — 같은 조건에서 단계 · 하루 순서가 얼마나 갈리는가(새 사람에게도 차이가 유지되는지 보는 지표)."""
    vec = {p["persona_id"]: tuple(p["results"][k]["stage"] for k in preset_ids) for p in people}
    seq = {p["persona_id"]: {k: tuple(x[1] for x in p["results"][k]["sequence"]) for k in preset_ids} for p in people}
    ids = list(vec)
    pairs = [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    seq_diff = [sum(seq[a][k] != seq[b][k] for k in preset_ids) / len(preset_ids) for a, b in pairs]
    per_preset = {k: dict((s, sum(1 for p in people if p["results"][k]["stage"] == s)) for s in {p["results"][k]["stage"] for p in people}) for k in preset_ids}
    return dict(n_people=len(ids), distinct_stage_vectors=len(set(vec.values())), mean_pairwise_sequence_difference=(round(sum(seq_diff) / len(seq_diff), 3) if seq_diff else None),
                stage_by_preset=per_preset,
                note="같은 조건에서 모두 같은 단계 · 같은 하루면 차이가 사라진 것 — 원인이 선택지 구성인지 근거 연결인지 사람 검수로 나눠 본다")


def run_batch(in_dir: Path, out_dir: Path, presets: list[dict]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    people, audits, rejected = [], {}, {}
    for f in sorted(Path(in_dir).glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        errs = check_profile(doc)
        if errs:
            rejected[f.name] = errs[:20]
            continue
        res = run_person(doc, presets)
        people.append(res)
        audits[res["persona_id"]] = link_audit(doc)
    core = [p["id"] for p in presets if not p["label"].startswith(("⑧", "⑨"))]
    summary = dict(engine=EN.VERSION, policy=dict(EN.POLICY), weights=dict(EN.W), model_calls=0, human_review="pending", demo_approved=False,
                   linker="auto_link(공통 규칙) · 손 연결표 미사용", accepted=[p["persona_id"] for p in people], rejected=rejected,
                   differentiation=(differentiation(people, core) if people else None))
    (out_dir / "people.json").write_text(json.dumps(people, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "link_audit.json").write_text(json.dumps(audits, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
