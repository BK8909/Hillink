"""Receive selected Walkerhill image-observation TEXT notes; no image collection.

Body statements and an observer's visual notes are separate evidence layers.
These notes never become exact body quotes or independent event counts.
"""
from copy import deepcopy

from .common import digest, require_opaque


def normalize_notes(document, notes):
    if notes and document.get("scope") != "walkerhill":
        raise ValueError("selected_photo_notes_only_for_walkerhill_posts")
    normalized=[]; seen=set()
    for supplied in notes:
        note=deepcopy(supplied)
        for field in ("note_id","post_id","persona_id","experience_key","observer_ref","asset_ref"):
            require_opaque(note.get(field))
        if note["note_id"] in seen:
            raise ValueError("duplicate_photo_note")
        seen.add(note["note_id"])
        if note["post_id"] != document["post_id"] or note["persona_id"] != document["persona_id"]:
            raise ValueError("photo_note_wrong_post_or_author")
        if note.get("body_sha256_private") != digest(document["text"]):
            raise ValueError("photo_note_bound_to_different_body_version")
        if not isinstance(note.get("observations"),list) or not note["observations"] or any(not isinstance(v,str) or not v.strip() for v in note["observations"]):
            raise ValueError("visible_observation_text_required")
        if not isinstance(note.get("interpretations",[]),list) or any(not isinstance(v,str) for v in note.get("interpretations",[])):
            raise ValueError("separate_interpretations_required")
        if not isinstance(note.get("limitations"),list) or not note["limitations"] or any(not isinstance(v,str) or not v.strip() for v in note["limitations"]):
            raise ValueError("visible_frame_limitations_required")
        anchors=note.get("body_anchors",[])
        for anchor in anchors:
            start,end=anchor["span"]
            if not 0 <= start < end <= len(document["text"]) or document["text"][start:end] != anchor["quote"]:
                raise ValueError("photo_note_body_anchor_mismatch")
        normalized.append({key:note[key] for key in ("note_id","post_id","persona_id","experience_key","observer_ref","asset_ref","observations","limitations")})
        normalized[-1].update(interpretations=note.get("interpretations",[]),body_anchors=anchors,
                              evidence_layer="visual_observer_text_note",source_alignment="note_not_original_body_quote",
                              dependency_root=note["experience_key"],new_independent_experience_credit=0,
                              human_review="pending",original_images_collected_by_this_pipeline=False)
    return sorted(normalized,key=lambda n:n["note_id"])


def image_availability(document,notes):
    normalized=normalize_notes(document,notes)
    return {"image_policy":"selected_walkerhill_notes_only","status":"selected_observer_text_note_available" if normalized else "image_not_collected_by_policy",
            "absence_quality_penalty":0,"observations":normalized,"contains_private_source":bool(normalized)}


def normalize_note_claims(document, normalized_notes, claims):
    """Keep research-usable visual/combined inference out of fake body quotes."""
    notes={n["note_id"]:n for n in normalized_notes}; seen=set(); result=[]
    for row in claims:
        claim=deepcopy(row)
        require_opaque(claim.get("claim_id")); require_opaque(claim.get("experience_key"))
        if claim["claim_id"] in seen:
            raise ValueError("duplicate_note_claim")
        seen.add(claim["claim_id"])
        refs=claim.get("source_note_ids",[])
        if not refs or not set(refs)<=set(notes):
            raise ValueError("visual_claim_requires_existing_note_roots")
        if any(notes[ref]["post_id"]!=document["post_id"] or notes[ref]["dependency_root"]!=claim["experience_key"] for ref in refs):
            raise ValueError("visual_claim_wrong_source_or_experience")
        if claim.get("claim_type") not in {"observer_observation","observer_inference","body_note_combined_inference"}:
            raise ValueError("visual_claim_layer_required")
        if not isinstance(claim.get("claim_text"),str) or not claim["claim_text"].strip() or not claim.get("scope") or not claim.get("limitations"):
            raise ValueError("visual_claim_scope_and_limits_required")
        anchors=claim.get("body_anchors",[])
        if claim["claim_type"]=="body_note_combined_inference" and not anchors:
            raise ValueError("combined_inference_needs_body_roots")
        for anchor in anchors:
            start,end=anchor["span"]
            if not 0 <= start < end <= len(document["text"]) or document["text"][start:end]!=anchor["quote"]:
                raise ValueError("visual_combined_body_anchor_mismatch")
        if claim.get("calibrated_probability") is not None:
            raise ValueError("uncalibrated_visual_inference_is_not_probability")
        # Explicit allowlist: no caller-supplied approval or event credit survives.
        result.append({key:claim[key] for key in ("claim_id","experience_key","source_note_ids","claim_type","claim_text","scope","limitations")})
        result[-1].update(body_anchors=anchors,alternative_readings=claim.get("alternative_readings",[]),
                          source_layer="observer_note_claim_not_verified_image",human_review="pending",
                          new_independent_experience_credit=0,research_use="scoped_supplement_available_not_approved_memory")
    return result
