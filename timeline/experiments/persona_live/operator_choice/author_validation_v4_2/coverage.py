"""Compare a declared discovery inventory to source-ready current text posts.

No crawling, title-only profiling, claims of exhaustive search, or missing-body
inferences. Source/author identity matching must already exist in a private ledger.
"""
from .common import require_opaque


def audit_inventory(documents, inventory, *, search_complete=False, inventory_ref=None, reported_totals=None):
    docs={d["post_id"]:d for d in documents}
    if len(docs) != len(documents):
        raise ValueError("duplicate_current_post")
    rows=[]; seen=set(); linked_posts=set()
    for item in inventory:
        for field in ("source_id","persona_id"):
            require_opaque(item[field])
        if item["source_id"] in seen:
            raise ValueError("duplicate_discovery_source")
        seen.add(item["source_id"])
        post_id=item.get("document_post_id")
        if post_id is not None:
            require_opaque(post_id)
            if post_id not in docs or docs[post_id]["persona_id"] != item["persona_id"]:
                raise ValueError("inventory_document_or_author_mismatch")
            if post_id in linked_posts:
                raise ValueError("same_post_must_not_count_as_two_discoveries")
            linked_posts.add(post_id)
            if docs[post_id].get("scope") != "walkerhill":
                raise ValueError("related_post_cannot_masquerade_as_walkerhill_coverage")
            body_available=bool(docs[post_id].get("text","").strip())
        else:
            body_available=False
        rows.append({"source_id":item["source_id"],"persona_id":item["persona_id"],"post_id":post_id,
                     "status":"current_text_available" if body_available else "not_in_current_text_corpus",
                     "discovery_basis":item["discovery_basis"],"body_inference_performed":False})
    personas=sorted({d["persona_id"] for d in documents}|{i["persona_id"] for i in inventory})
    if search_complete and not inventory_ref:
        raise ValueError("full_search_inventory_provenance_required")
    reported_totals=reported_totals or {}
    for entry in reported_totals.values():
        if type(entry.get("count")) is not int or entry["count"]<0 or not entry.get("source_ref"):
            raise ValueError("reported_count_requires_provenance_not_source_identity")
    result={"inventory_ref":inventory_ref,"full_search_inventory_supplied":bool(search_complete),
            "full_search_recall":None,"recall_not_inferred_from_partial_inventory":True,
            "authors":{p:{"known_inventory_posts":sum(r["persona_id"]==p for r in rows),
                          "linked_text_posts":sum(r["persona_id"]==p and r["status"]=="current_text_available" for r in rows),
                          "known_text_gaps":[r["source_id"] for r in rows if r["persona_id"]==p and r["status"]!="current_text_available"],
                          "current_text_not_in_inventory":[d["post_id"] for d in documents if d["persona_id"]==p and d["scope"]=="walkerhill" and d["post_id"] not in linked_posts]} for p in personas},
            "rows":rows,"human_review":"pending","missing_body_semantics":"not_inferred"}
    for persona,entry in reported_totals.items():
        if persona not in result["authors"]: raise ValueError("reported_total_unknown_author")
        author=result["authors"][persona]
        author["reported_discovery_total"]=entry["count"]
        author["reported_total_source_ref"]=entry["source_ref"]
        author["reported_sources_not_yet_identified"]=max(0,entry["count"]-author["known_inventory_posts"])
        author["reported_count_is_not_verified_source_inventory"]=True
    return result
