"""Bind the RECEIVED team prompt's actual inputs/eight outputs to V4.1 facts.

The source MD defines ordered sections but no full JSON Schema. This schema is
an explicit versioned implementation, not a separately approved team artifact.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from ..author_method_v4_1.contract import normalize_facts, STAGES
from ..author_method_v4_1.linking import link_experiences
from ..author_method_v4_1.method import integrate
from .common import digest, private_document, require_corpus, require_opaque
from .photo_notes import normalize_notes, normalize_note_claims
from .study import frozen_method

ROOT=Path(__file__).parent
SECTIONS=("SOURCE_AUDIT","PERSONA_SUMMARY","TRAIT_TABLE","EVENT_ACTIONS","EVIDENCE_MAP","CONTEXT_RULES","QUALITY_FLAGS","STRUCTURED_PROFILE")
SCHEMA=json.loads((ROOT/"team_profile.schema.json").read_text())


def received_contract():
    source=(ROOT/"TEAM_COMMON_EXTRACTION_PROMPT_V4_1.md").read_text()
    block=re.search(r"```text\n(.*?)\n```",source,re.S)
    if not block:
        raise ValueError("received_instruction_block_missing")
    # Verify these are sourced section labels rather than renamed inventions.
    positions=[block[1].find(f"{i}. {name}:") for i,name in enumerate(SECTIONS,1)]
    if any(p<0 for p in positions) or positions!=sorted(positions):
        raise ValueError("received_team_sections_changed")
    return {"source_filename":"HILLINK_TEAM_COMMON_EXTRACTION_PROMPT_V4_1.md","source_sha256":digest(source),
            "instruction_block":block[1],"instruction_sha256":digest(block[1]),"json_schema_sha256":digest(SCHEMA),
            "team_prompt_received":True,"eight_sections_checked_against_source":True,
            "subfield_json_schema_origin":"versioned_implementation_of_received_prose_not_separate_team_approved_schema"}


def adapt_team_photo_notes(documents,notes):
    """Map actual minimum team fields; retain free linked_text as private context.

    The source prompt gives a prose relation example. Free relation text requires
    an explicit confirm/augment/contradict code instead of silent interpretation.
    """
    if notes in (None,"none"):
        notes=[]
    if not isinstance(notes,list):
        raise ValueError("team_photo_notes_must_be_array_or_none")
    docs={d["post_id"]:d for d in documents}; grouped={}; ids=set()
    for position,supplied in enumerate(notes,1):
        row=deepcopy(supplied)
        required={"post_id","image_position","visual_observation","supported_claim_scope","inference_limit"}
        if not required<=set(row) or not all(row[k] for k in required):
            raise ValueError("received_team_photo_minimum_fields_required")
        if row["post_id"] not in docs:
            raise ValueError("team_photo_unknown_post")
        row.setdefault("note_id",f"{row['post_id']}_PHOTO_{position}")
        row.setdefault("experience_key",f"{row['post_id']}_VISUAL_UNLINKED")
        row.setdefault("observer_ref","OBSERVER_UNRECORDED")
        if row["note_id"] in ids:
            raise ValueError("duplicate_team_photo_note_id")
        ids.add(row["note_id"])
        relation=row.get("relation_code",row.get("relation_to_text"))
        if relation not in {"confirm","augment","contradict"}:
            raise ValueError("explicit_photo_relation_code_required")
        anchors=row.get("linked_text_anchor",[])
        if isinstance(anchors,dict): anchors=[anchors]
        if not isinstance(anchors,list):
            raise ValueError("linked_text_anchor_must_be_exact_anchors")
        d=docs[row["post_id"]]
        native={"note_id":row["note_id"],"post_id":row["post_id"],"persona_id":d["persona_id"],
                "experience_key":row["experience_key"],"observer_ref":row["observer_ref"],"asset_ref":row["note_id"],
                "body_sha256_private":digest(d["text"]),"observations":[row["visual_observation"]],
                "interpretations":row.get("interpretations",[]),"limitations":[row["inference_limit"]],"body_anchors":anchors}
        normalized=normalize_notes(d,[native])[0]
        normalized.update(image_position=row["image_position"],relation_to_text=relation,
                          relation_to_text_original_private=row.get("relation_to_text"),
                          linked_text_private=row.get("linked_text",""),supported_claim_scope=row["supported_claim_scope"],
                          observation_confidence=row.get("observation_confidence","not_supplied"),
                          text_anchor_status="exact_anchor_checked" if anchors else "prose_link_pending_resolution",
                          experience_link_status="declared_candidate" if "experience_key" in supplied else "unlinked_no_new_experience_credit")
        grouped.setdefault(d["post_id"],[]).append(normalized)
    return grouped


def prepare_team_requests(documents, *, author_role, primary_type=None, photo_notes=None, excluded_posts=(), coverage=None):
    require_corpus(documents)
    scope_excluded=[d["post_id"] for d in documents if d.get("profile_scope_excluded",False)]
    documents=[d for d in documents if not d.get("profile_scope_excluded",False)]
    if not documents: raise ValueError("no_profile_scope_sources_available")
    if author_role not in {"method_development","transfer_check_prior_research","holdout_new_author"}:
        raise ValueError("declared_author_role_required")
    source=received_contract(); docs={d["post_id"]:d for d in documents}
    notes=adapt_team_photo_notes(documents,photo_notes)
    exclusions=[]
    for row in excluded_posts:
        if row.get("post_id") not in docs or row.get("status") not in {"confirmed_compensation","pending"} or not row.get("basis_ref"):
            raise ValueError("exclusion_requires_post_status_and_source_basis")
        exclusions.append({k:row[k] for k in ("post_id","status","basis_ref")})
    if len({r["post_id"] for r in exclusions})!=len(exclusions):
        raise ValueError("duplicate_post_exclusion")
    if primary_type is not None and (not isinstance(primary_type,dict) or not {"label","basis"}<=set(primary_type)):
        raise ValueError("primary_type_must_be_tentative_with_basis_or_null")
    posts=[]
    for d in sorted(documents,key=lambda d:d["post_id"]):
        posts.append({**private_document(d),"publication_date":d.get("publication_date_unverified",d.get("publication_date")),
                      "publication_is_not_visit_date":True})
    inputs={"AUTHOR_ID":documents[0]["persona_id"],"PRIMARY_TYPE":deepcopy(primary_type),"POSTS":posts,
            "WALKERHILL_PHOTO_NOTES":[n for values in notes.values() for n in values],"EXCLUDED_POSTS":exclusions}
    # Same schema supplement for every author. Never append old profiles/labels.
    intake_metadata={"duplicate_source_rows":sum(max(0,len(d["source_locations_private"])-1) for d in documents) if all("source_locations_private" in d for d in documents) else None,
                     "excluded_input_scope_post_ids":scope_excluded,
                     "full_search_inventory_supplied":bool(coverage and coverage.get("full_search_inventory_supplied")),
                     "known_missing_source_ids":coverage.get("authors",{}).get(documents[0]["persona_id"],{}).get("known_text_gaps",[]) if coverage else []}
    model_input={"system":source["instruction_block"],"inputs":inputs,"intake_audit_metadata":intake_metadata,"machine_output_contract":SCHEMA}
    return {"persona_id":documents[0]["persona_id"],"source_class":documents[0]["source_class"],"author_role":author_role,
            "contract":{k:v for k,v in source.items() if k!="instruction_block"},"native_baseline":frozen_method(),
            "input_sha256_private":digest(model_input),"model_input_private":model_input,
            "source_coverage_private":coverage,"actual_executions":0,"approval_required":True,
            "excluded_input_scope_post_ids":scope_excluded,
            "planned_independent_repeats":["A","B"],"prepared_author_request_count":2,
            "human_review":"pending","demo_approved":False,
            "comparison_note":"Full-author team prompt condition differs from original single-post native V4.1; do not pool as same extraction treatment"}


def ordered_team_output(profile):
    return {section:deepcopy(profile[section]) for section in SECTIONS}


def import_team_profile(documents,packet,profile):
    require_corpus(documents)
    documents=[d for d in documents if not d.get("profile_scope_excluded",False)]
    if not documents: raise ValueError("no_profile_scope_sources_available")
    if digest(packet["model_input_private"])!=packet["input_sha256_private"]:
        raise ValueError("prepared_team_input_mutated")
    try:
        json.dumps(profile,allow_nan=False)
    except (ValueError,TypeError) as error:
        raise ValueError("team_output_must_be_strict_json") from error
    for error in Draft202012Validator(SCHEMA).iter_errors(profile):
        raise ValueError("team_eight_section_schema_invalid:"+"/".join(map(str,error.absolute_path)))
    docs={d["post_id"]:d for d in documents}; structured=profile["STRUCTURED_PROFILE"]
    if structured["persona_id"]!=documents[0]["persona_id"] or packet["persona_id"]!=documents[0]["persona_id"]:
        raise ValueError("team_output_wrong_author")
    original_posts={p["post_id"]:p for p in packet["model_input_private"]["inputs"]["POSTS"]}
    if set(original_posts)!=set(docs) or any(original_posts[k]["full_text"]!=docs[k]["text"] for k in docs):
        raise ValueError("team_import_corpus_changed")
    audit=profile["SOURCE_AUDIT"]
    if audit["unique_post_count"]!=len(docs) or audit["scope_counts"]!={scope:sum(d["scope"]==scope for d in documents) for scope in ("walkerhill","related","recent")}:
        raise ValueError("team_source_counts_inconsistent")
    notes=packet["model_input_private"]["inputs"]["WALKERHILL_PHOTO_NOTES"]
    note_ids={n["note_id"] for n in notes}
    if audit["photo_note_count"]!=len(notes): raise ValueError("team_photo_count_inconsistent")
    excluded={r["post_id"] for r in packet["model_input_private"]["inputs"]["EXCLUDED_POSTS"] if r["status"]=="confirmed_compensation"}
    if set(audit["excluded_post_ids"])!=excluded: raise ValueError("unconfirmed_or_author_wide_exclusion_not_allowed")
    if audit["excluded_post_count"]!=len(excluded): raise ValueError("team_excluded_post_count_inconsistent")
    expected_duplicates=sum(max(0,len(d["source_locations_private"])-1) for d in documents) if all("source_locations_private" in d for d in documents) else None
    if audit["duplicate_source_rows"]!=expected_duplicates: raise ValueError("source_duplicate_count_needs_intake_provenance_or_null")
    grouped={k:[] for k in docs}
    for fact in structured["facts"]:
        if fact["post_id"] not in docs: raise ValueError("team_fact_unknown_post")
        grouped[fact["post_id"]].append(fact)
    batches=[normalize_facts(d,grouped[d["post_id"]]) for d in documents]
    facts=[f for b in batches for f in b["facts"]]; facts_by_id={f["fact_id"]:f for f in facts}
    if len(facts_by_id)!=len(facts): raise ValueError("duplicate_team_fact_id")
    visual=[]
    for claim in structured.get("visual_note_claims",[]):
        if claim.get("post_id") not in docs: raise ValueError("visual_claim_unknown_post")
        d=docs[claim["post_id"]]
        visual.extend(normalize_note_claims(d,[n for n in notes if n["post_id"]==d["post_id"]],[claim]))
    visual_by_id={c["claim_id"]:c for c in visual}
    if len(visual_by_id)!=len(visual) or set(visual_by_id)&set(facts_by_id): raise ValueError("duplicate_team_claim_id")
    evidence={e["claim_id"]:e for e in profile["EVIDENCE_MAP"]}
    if len(evidence)!=len(profile["EVIDENCE_MAP"]) or set(evidence)!=set(facts_by_id)|set(visual_by_id):
        raise ValueError("team_evidence_map_must_cover_each_claim_once")
    for claim_id,entry in evidence.items():
        if entry["post_id"] not in docs or not set(entry["photo_note_ids"])<=note_ids:
            raise ValueError("team_evidence_unknown_source")
        if any(n["post_id"]!=entry["post_id"] for n in notes if n["note_id"] in entry["photo_note_ids"]):
            raise ValueError("team_evidence_photo_wrong_post")
        if claim_id in facts_by_id:
            f=facts_by_id[claim_id]
            if entry["post_id"]!=f["post_id"] or entry["text_anchors"]!=f["anchors"] or entry["source_layer"]!="body":
                raise ValueError("body_fact_evidence_map_mismatch")
        else:
            v=visual_by_id[claim_id]
            expected_layer="body_and_note" if v["claim_type"]=="body_note_combined_inference" else "visual_observer_note"
            if set(entry["photo_note_ids"])!=set(v["source_note_ids"]) or entry["source_layer"]!=expected_layer or entry["text_anchors"]!=v["body_anchors"]:
                raise ValueError("visual_claim_evidence_map_mismatch")
    all_claims=set(evidence)
    for row in profile["TRAIT_TABLE"]+profile["CONTEXT_RULES"]:
        if not row["evidence_ids"] or not set(row["evidence_ids"])<=all_claims:
            raise ValueError("trait_or_rule_requires_existing_claims")
    for row in profile["TRAIT_TABLE"]:
        if not set(row["representative_post_ids"])<=set(docs): raise ValueError("trait_unknown_representative_post")
        roots={facts_by_id[k]["experience_key"] if k in facts_by_id else visual_by_id[k]["experience_key"] for k in row["evidence_ids"]}
        if row["independent_evidence_count"]>len(roots): raise ValueError("reported_repeat_count_exceeds_possible_experiences")
    covered_facts=set()
    if len({e["event_id"] for e in profile["EVENT_ACTIONS"]})!=len(profile["EVENT_ACTIONS"]):
        raise ValueError("same_event_must_not_be_duplicated_in_actions")
    for event in profile["EVENT_ACTIONS"]:
        require_opaque(event["event_id"])
        if event["visit_id"] is not None: require_opaque(event["visit_id"])
        if not set(event["stages"])<=STAGES or not set(event["fact_ids"])<=set(facts_by_id) or not set(event["post_ids"])<=set(docs):
            raise ValueError("event_action_unknown_stage_or_source")
        if any(facts_by_id[k]["experience_key"]!=event["event_id"] or facts_by_id[k]["post_id"] not in event["post_ids"] or facts_by_id[k]["action_stage"] not in event["stages"] for k in event["fact_ids"]):
            raise ValueError("event_identity_or_lifecycle_stage_mismatch")
        covered_facts.update(event["fact_ids"])
    if covered_facts!=set(facts_by_id): raise ValueError("each_fact_needs_event_action_link")
    links=link_experiences(facts,structured["experience_links"])
    if audit["independent_event_count"]>len(set(links["groups"].values())):
        raise ValueError("audit_event_count_exceeds_possible_experiences")
    return {"team_profile_private":deepcopy(profile),"canonical_batches_private":batches,"visual_supplements_private":visual,
            "experience_links_checked":links,"excluded_post_ids":sorted(excluded),
            "structural_status":"received_fields_and_source_links_checked_not_semantic_accuracy",
            "reported_traits_are_not_recomputed_or_approved_scores":True,"reported_independence_counts_verified":False,
            "human_review":"pending","demo_approved":False}


def integrate_imported_team(documents, imported):
    """Recompute only frozen V4.1 indices, not the LLM's reported trait scores.

    Declared confirmed compensated posts stay in private extraction provenance,
    but are omitted from scoring; pending suspicions are not silently omitted.
    Visual supplements remain available qualitatively without extra event credit.
    """
    excluded=set(imported["excluded_post_ids"])
    batches=[b for b in imported["canonical_batches_private"] if b["post_id"] not in excluded]
    docs=[d for d in documents if d["post_id"] not in excluded]
    if not batches:
        return {"status":"no_unexcluded_source_batches","scored_post_count":0,"human_review":"pending","demo_approved":False}
    facts=[f for b in batches for f in b["facts"]]
    keys={f["experience_key"] for f in facts}; ids={f["fact_id"] for f in facts}
    supplied=imported["team_profile_private"]["STRUCTURED_PROFILE"]["experience_links"]
    assertions=[a for a in supplied if a["left"] in keys and a["right"] in keys and set(a["evidence_refs"])<=ids]
    result=integrate(batches,docs,assertions)
    result.update(declared_compensation_excluded_post_ids=sorted(excluded),
                  source_links_held_back_after_exclusion=len(supplied)-len(assertions),
                  visual_supplements_private=deepcopy(imported["visual_supplements_private"]),
                  profile_interpretation="source_aligned_unreviewed_research_candidate_not_independent_quality_result")
    return result
