"""Explicit field mapping. A provisional contract is not a received team form."""
from copy import deepcopy
from hashlib import sha256

from ..author_method_v4_1.contract import normalize_facts
from .common import digest

REQUIRED = {"fact_id","experience_key","feature_key","detail","anchors","kind","dimension",
            "actor","time_scope","action_stage","polarity","confidence","common_dimensions"}


def mapping_status(mapping, team_prompt=None):
    fields=mapping.get("fields",{})
    if not REQUIRED <= set(fields):
        raise ValueError("required_v41_fields_unmapped")
    if len(set(fields.values())) != len(fields) or any(not isinstance(path,str) or not path for path in fields.values()):
        raise ValueError("mapping_must_be_explicit_one_to_one")
    actual_hash=sha256(team_prompt.encode()).hexdigest() if team_prompt is not None else None
    ready=(mapping.get("status") == "source_contract_checked" and actual_hash is not None
           and actual_hash == mapping.get("source_prompt_sha256") and bool(mapping.get("source_form_ref")))
    return {"ready_for_fixed_input_use":ready,"status":"source_contract_hash_checked" if ready else "provisional_mapping_not_team_verified",
            "mapping_sha256":digest(mapping),"team_prompt_sha256_private":actual_hash,
            "does_not_certify_team_approval":True}


def import_rows(document, rows, mapping, team_prompt=None):
    status=mapping_status(mapping,team_prompt)
    proposals=[]
    for row in rows:
        proposal={}
        used=set()
        for target,source in mapping["fields"].items():
            if source not in row:
                if target in REQUIRED:
                    raise ValueError("required_team_field_missing")
                continue
            proposal[target]=deepcopy(row[source]); used.add(source)
        # Unknown details are not discarded or coerced into a fixed tag list.
        proposal["team_unmapped_private"]={key:deepcopy(value) for key,value in row.items() if key not in used}
        proposals.append(proposal)
    result=normalize_facts(document,proposals)
    result["team_mapping"]=status
    result["integration_eligible"]=status["ready_for_fixed_input_use"]
    result["human_review"]="pending"
    return result


def export_rows(batch,mapping):
    mapping_status(mapping)
    rows=[]
    for fact in batch["facts"]:
        row=deepcopy(fact.get("team_unmapped_private",{}))
        for target,source in mapping["fields"].items():
            if target in fact:
                if source in row:
                    raise ValueError("unmapped_field_export_collision")
                row[source]=deepcopy(fact[target])
        rows.append(row)
    return rows


def require_ready(batch):
    if not batch.get("integration_eligible"):
        raise ValueError("team_mapping_preview_is_not_final_extraction")
