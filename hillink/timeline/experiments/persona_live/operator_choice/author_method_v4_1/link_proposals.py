"""Transparent candidate identity links from source-backed document metadata.

The output is a proposal registry, not verified author/visit identity. Titles and
publication dates alone never establish independent visits or same experience.
"""
from itertools import combinations
from .contract import explicit_date


def propose(documents):
    proposals = []
    for left,right in combinations(sorted(documents,key=lambda d:d["post_id"]),2):
        if left["persona_id"] != right["persona_id"]:
            continue
        a,b = left.get("experience_hint",{}),right.get("experience_hint",{})
        evidence = []
        for doc,hint in ((left,a),(right,b)):
            if hint.get("visit_date"):
                anchor = hint.get("date_anchor",{})
                if hint.get("date_role") != "explicit_visit" or not anchor:
                    continue
                start,end = anchor["span"]
                if doc["text"][start:end] != anchor["quote"]:
                    raise ValueError("link_date_anchor_mismatch")
                explicit_date(hint["visit_date"],anchor["quote"])
                evidence.append(doc["post_id"])
        if len(evidence) == 2:
            if a["visit_date"] != b["visit_date"]:
                relation,basis = "distinct_visit","explicit_visit_date"
            elif a.get("venue_key") and a.get("venue_key") == b.get("venue_key") and a.get("activity_key") and a.get("activity_key") == b.get("activity_key"):
                relation,basis = "same_experience","explicit_visit_date"
            else:
                relation,basis = "same_visit_candidate","explicit_visit_date"
        elif right["post_id"] in a.get("same_experience_post_refs",[]):
            relation,basis = "same_experience_candidate","explicit_body_reference"
        elif left.get("title") and left["title"] == right.get("title"):
            relation,basis = "unresolved","title_only"
        else:
            continue
        proposals.append({"left":left["post_id"],"right":right["post_id"],"relation":relation,"basis":basis,
                          "evidence_post_ids":evidence,"status":"source_link_candidate_not_human_verified"})
    return proposals
