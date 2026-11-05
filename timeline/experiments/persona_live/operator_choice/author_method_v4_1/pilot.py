"""Run caller-supplied private raw-text corpus; publish only an explicit safe projection.

No source files, account aliases, original text hashes or free-form fact details
are written to the research repository by this module.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
from itertools import combinations
import json
from pathlib import Path
from time import perf_counter

from .contract import normalize_facts
from .extraction import automatic_draft
from .method import integrate, screen_advertising
from .quality import consistency, human_review_rows, source_sample_check


def run_private(documents, annotations, assertions):
    """annotations are analyst/source-check proposals, not automatic ground truth."""
    started = perf_counter()
    if not documents or len({d["post_id"] for d in documents}) != len(documents):
        raise ValueError("nonempty_deduplicated_corpus_required")
    if any(d["scope"] not in {"walkerhill","related","recent"} for d in documents):
        raise ValueError("source_scope_assignment_required_before_pilot")
    if not set(annotations) <= {d["post_id"] for d in documents}:
        raise ValueError("annotation_post_not_in_authorized_corpus")
    batches = [normalize_facts(doc, annotations.get(doc["post_id"],[])) for doc in documents]
    automatic = [automatic_draft(doc) for doc in documents]
    result = {"version":"author_method_v4.1-private-pilot", "authors":{}, "execution":{"separate_model_calls":0,"product_api_calls":0,"human_reviews":0,"demo_approved":False}}
    for persona in sorted({doc["persona_id"] for doc in documents}):
        docs = [d for d in documents if d["persona_id"] == persona]
        source_posts = {d["post_id"] for d in docs}
        selected = [b for b in batches if b["post_id"] in source_posts]
        autos = [b for b in automatic if b["post_id"] in source_posts]
        scope_results = {}
        for scope, allowed in (("walkerhill_only",{"walkerhill"}), ("related_added",{"walkerhill","related"}), ("recent_added",{"walkerhill","related","recent"})):
            subset = [b for b in selected if b["scope"] in allowed]
            subset_docs = [d for d in docs if d["scope"] in allowed]
            if not subset:
                scope_results[scope]={"status":"source_unavailable_not_evaluated","source_post_count":0,"patterns":{},"human_review":"pending","demo_approved":False}
                continue
            keys = {f["experience_key"] for b in subset for f in b["facts"]}
            subset_links = [a for a in assertions if a["left"] in keys and a["right"] in keys]
            scope_results[scope] = integrate(subset, subset_docs, subset_links)
        full_keys = {f["experience_key"] for b in selected for f in b["facts"]}
        full_links = [a for a in assertions if a["left"] in full_keys and a["right"] in full_keys]
        final = scope_results["recent_added"]
        rerun = integrate(list(reversed(selected)), list(reversed(docs)), full_links)
        result["authors"][persona] = {"scope_profiles":scope_results, "automatic_retrieval_profile":integrate(autos,docs),
                                     "developer_sample_check":source_sample_check([f for b in selected for f in b["facts"]],[f for b in autos for f in b["facts"]]),
                                     "deterministic_rerun":consistency(final,rerun),
                                     "private_stage_A":selected,"private_automatic_candidates":autos,
                                     "post_screening":[{"post_id":d["post_id"],**screen_advertising(d["text"])} for d in docs]}
    result["human_review_sheet"] = human_review_rows(result["authors"])
    result["local_processing_seconds"] = round(perf_counter()-started,6)
    return result


def public_projection(private_result):
    """Only code IDs, derived indices and null/pending review slots are shared.

    Does not certify semantic correctness or deidentification of caller-provided
    identifiers. Original text, accounts, locations and free details never pass.
    """
    public = {"version":"author_method_v4.1-deidentified-pilot", "authors":{},"execution":private_result["execution"],
              "human_review_sheet":private_result["human_review_sheet"],
              "interpretation":"actual source pilot; analyst-assisted facts and automatic retrieval evaluated separately; not blind accuracy"}
    for persona, data in private_result["authors"].items():
        public["authors"][persona] = {key:deepcopy(data[key]) for key in ("scope_profiles","automatic_retrieval_profile","developer_sample_check","deterministic_rerun","post_screening")}
        profiles = list(public["authors"][persona]["scope_profiles"].values()) + [public["authors"][persona]["automatic_retrieval_profile"]]
        for profile in profiles:
            links=profile.get("links",{})
            # The complete source-reviewed registry remains private; duplicating
            # its all-pairs assertions in every scope obscures the actual output.
            if "assertions" in links:
                links["source_checked_assertion_count"]=len(links.pop("assertions"))
            if "pending_assertions" in links:
                links["pending_assertion_count"]=len(links.pop("pending_assertions"))
    return public


def validate_public_projection(value):
    serialized = json.dumps(value,ensure_ascii=False)
    forbidden = ("http://","https://","author_account",'"quote"','"detail"',"source_sha256_private",'"text"',"@")
    return [token for token in forbidden if token in serialized]


def write_private_only(directory, result):
    root = Path(directory).resolve()
    # Never write raw extraction data anywhere under a Git worktree.
    if any((p / ".git").exists() for p in (root,*root.parents)):
        raise ValueError("private_corpus_output_must_be_outside_git_worktree")
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    target = root / "pilot_private_result.json"
    if target.exists():
        raise FileExistsError("version_private_results_do_not_overwrite")
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    target.chmod(0o600)
    return target
