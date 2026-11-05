"""Legacy automatic extraction -> quarantine exchange format, without model calls."""
from __future__ import annotations

import re


def from_legacy(draft: dict, agent_id: str) -> dict:
    """An automatic draft's ◎ marker is a model claim, never human verification."""
    units = []
    for place, summary in draft.get("truth", {}).get("visited", {}).items():
        if re.search(r"언급\s*없|소개만|추천만|다음엔|못\s*갔", summary):
            continue
        units.append({"unit_id": f"{agent_id}.U{len(units) + 1:02d}", "observed_behavior": summary,
                      "evaluated_aspect": {"target": place, "polarity": "unknown"}, "personal_reason": None,
                      "context": {"visit_scope": "unverified", "order": None}, "evidence_ids": [],
                      "provenance": "ai_estimate", "original_anchor_verified": False})
    return {"version": "extraction_exchange_v1", "agent_id": agent_id, "source_access": "unavailable",
            "verification_status": "automatic_draft", "evidence_units": units,
            "excluded_fields": ["traits", "truth.not_visited", "automatic_entitlement_assumptions", "default_date_and_time"]}


def validate_exchange(data: dict) -> list[str]:
    import json
    from pathlib import Path
    import jsonschema
    schema = json.loads(Path(__file__).with_name("extraction.schema.json").read_text(encoding="utf-8"))
    issues = ["schema:" + e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(data)]
    blob = json.dumps(data, ensure_ascii=False)
    if re.search(r"https?://|author_hash|author_id|source_key|sk-proj-", blob):
        issues.append("private_identifier_or_url_in_extraction")
    for unit in data.get("evidence_units", []):
        if unit.get("original_anchor_verified") and (not unit.get("evidence_ids") or data.get("source_access") != "permitted_source_checked"):
            issues.append("anchor_verification_without_source_access")
        if data.get("verification_status") == "automatic_draft" and unit.get("provenance") != "ai_estimate":
            issues.append("automatic_output_promoted_to_observed")
    return issues
