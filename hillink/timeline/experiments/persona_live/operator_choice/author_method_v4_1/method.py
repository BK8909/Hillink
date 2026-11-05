"""Shared integration policy. No author IDs, prices or desired choices hardcoded."""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path
import re

from . import VERSION
from .contract import premium_context
from .linking import link_experiences, recurrence

POLICY = json.loads(Path(__file__).with_name("policy.json").read_text())


def screen_advertising(text):
    """Exclude a post only for explicit compensation, not ads it saw or resembles."""
    clean = re.sub(r"[^.!?\n]*(?:수수료|원고료|대가|제공)[^.!?\n]*(?:받지\s*않|받은\s*적.{0,8}없)[^.!?\n]*", "", text)
    clean = re.sub(r"(?:유료\s*광고|협찬)(?:가|이|은|는)?\s*(?:아니|아님|없)|광고를\s*포함하지\s*않", "", clean)
    explicit = list(re.finditer(r"(?:이\s*포스팅|본\s*(?:포스팅|글)).{0,100}(?:수수료|원고료|대가|제공받)|판매\s*발생\s*시\s*수수료|(?:제품|식사|숙박)(?:을|를)?\s*제공\s*받(?:아|았)|유료\s*광고를\s*포함|#협찬|협찬(?:을\s*)?받", clean, re.S))
    voluntary = bool(re.search(r"광고.{0,120}(?:구매|주문)|광고에.{0,120}호기심|광고를\s*보고", text, re.S))
    suspicious = bool(re.search(r"구매\s*링크|할인\s*코드|구매방법|예약\s*문의", text))
    return {"status": "explicit_compensation" if explicit else "ordinary_post_with_review_flags" if suspicious else "ordinary_customer_post",
            "exclude_post_from_trait_scores": bool(explicit), "voluntary_ad_response_candidate": voluntary,
            "suspicion_only_not_excluded": suspicious and not bool(explicit),
            "author_wide_exclusion": False, "scope": "this_post_only", "human_review": "pending"}


def integrate(batches, documents, assertions=(), policy=None):
    policy = deepcopy(POLICY if policy is None else policy)
    values=list(policy["weights"].values())+[policy["strength_scale"]]
    if any(type(value) not in {int,float} or not math.isfinite(value) or value < 0 for value in values) or not policy["strength_scale"]:
        raise ValueError("nonnegative_finite_scoring_policy_required")
    if any(not 0 <= policy[key] <= 1 for key in ("source_explicit_distinct_discount","uncertain_experience_discount")):
        raise ValueError("independence_discounts_must_be_between_zero_and_one")
    if type(policy["strong_repeat_minimum"]) is not int or policy["strong_repeat_minimum"] < 3:
        raise ValueError("strong_repeat_requires_at_least_three_distinct_experiences")
    if not batches or len({b["persona_id"] for b in batches}) != 1:
        raise ValueError("single_author_corpus_required")
    if len({b["source_class"] for b in batches}) != 1:
        raise ValueError("real_synthetic_sources_must_not_mix")
    if len({b["post_id"] for b in batches}) != len(batches):
        raise ValueError("deduplicate_source_posts_before_integration")
    fact_ids=[f["fact_id"] for b in batches for f in b["facts"]]
    if len(fact_ids) != len(set(fact_ids)):
        raise ValueError("fact_ids_must_be_unique_across_posts")
    indexes = {d["post_id"]:d for d in documents}
    active, excluded = [], []
    for batch in batches:
        document = indexes[batch["post_id"]]
        if document["persona_id"] != batch["persona_id"]:
            raise ValueError("author_identity_mismatch")
        screen = screen_advertising(document["text"])
        if document.get("profile_scope_excluded", False):
            excluded.append({"post_id":batch["post_id"], "reason":"outside_authorized_behavior_profile_scope", "other_posts_retained":True})
            continue
        if screen["exclude_post_from_trait_scores"]:
            excluded.append({"post_id":batch["post_id"], "reason":"explicit_post_compensation", "other_posts_retained":True})
            continue
        for fact in batch["facts"]:
            if fact["actor"] in {"author", "author_inferred"} and fact["time_scope"] in {"source_experience", "historical"}:
                active.append(fact)
    if not active:
        return {"version":VERSION, "persona_id":batches[0]["persona_id"],"source_class":batches[0]["source_class"],
                "source_post_count":len(batches),"active_fact_count":0,"patterns":{},"individual_features":{},
                "excluded_posts":excluded,"policy_version":policy["version"],"images_required":False,
                "model_behavior_calls":0,"human_review":"pending", "demo_approved":False}
    # Link all input facts, including excluded-post references, but count only active ones.
    all_facts = [f for b in batches for f in b["facts"]]
    links = link_experiences(all_facts, assertions)
    dimensions = defaultdict(list)
    individual = defaultdict(list)
    for fact in active:
        individual[fact["feature_key"]].append(fact)
        for dimension in set(fact["common_dimensions"]):
            dimensions[dimension].append(fact)
        if premium_context(fact)["premium_experience_supported"]:
            dimensions["premium_experience"].append(fact)
    def summarize(rows):
        grouped = defaultdict(list)
        for fact in rows:
            grouped[links["groups"][fact["experience_key"]]].append(fact)
        repeat = recurrence(grouped, links)
        contributions = []
        for key, group in sorted(grouped.items()):
            def level(kinds):
                return max(({"high":1.0,"medium":0.75,"low":0.5}[f["confidence"]] for f in group if f["kind"] in kinds), default=0)
            action = level({"participation", "purchase"}) * policy["weights"]["participation"]
            # Multiple descriptions or actions of the same experience count once.
            base = max(action, level({"preference"}) * policy["weights"]["preference"], level({"appraisal","comparison"}) * policy["weights"]["appraisal"])
            bonus = level({"purchase"}) * policy["weights"]["purchase_bonus"] + level({"motive"}) * policy["weights"]["explicit_motive_bonus"]
            mass = base + bonus
            contributions.append({"experience_group":key, "base":base, "role_bonus":bonus,
                                  "unadjusted_mass":mass, "fact_ids":sorted({f["fact_id"] for f in group}),
                                  "post_ids":sorted({f["post_id"] for f in group})})
        # Independence bounds do not privilege a lexically first clique member.
        # One strongest observed experience retains its base; uncertain extra
        # groups add discounted evidence rather than being discarded.
        representative = min(contributions,key=lambda c:(-c["unadjusted_mass"],c["experience_group"]))["experience_group"]
        explicit_endpoints = {key for pair in links["distinct_pairs"] for key in pair if key in grouped}
        for contribution in contributions:
            quality = policy["source_explicit_distinct_discount"] if contribution["experience_group"] == representative or contribution["experience_group"] in explicit_endpoints else policy["uncertain_experience_discount"]
            contribution["independence_discount"] = quality
            contribution["evidence_mass"] = round(contribution["unadjusted_mass"]*quality,6)
        mass = sum(row["evidence_mass"] for row in contributions)
        return {"strength_index":round(policy["strength_scale"] * math.log1p(mass),6), "evidence_mass":round(mass,6),
                "score_has_no_hard_cap":True, "score_is_not_probability":True,
                "recurrence":repeat, "status":"no_behavioral_mass_from_this_kind" if not mass else "strong_repeated_inference_candidate" if repeat["minimum_distinct_experiences"] >= policy["strong_repeat_minimum"] else "plausible_repeated_candidate" if repeat["maximum_possible_experiences"] >= 3 else "context_supported_candidate",
                "fact_count":len({f["fact_id"] for f in rows}), "source_post_count":len({f["post_id"] for f in rows}),
                "contributions":contributions, "opposing_or_qualified_facts":sorted({f["fact_id"] for f in rows if f["polarity"] in {"negative","mixed"} or f["kind"] == "decline"}),
                "direction_counts":{direction:len({f["fact_id"] for f in rows if f["polarity"] == direction}) for direction in ("positive","negative","mixed","neutral")},
                "strength_is_evidence_accumulation_not_positive_preference":True,
                "local_evaluations_not_global_dislike":True,
                "scopes":sorted({f.get("context_scope","stated_experience") for f in rows})}
    return {"version":VERSION, "persona_id":batches[0]["persona_id"], "source_class":batches[0]["source_class"],
            "source_post_count":len(batches), "active_fact_count":len(active), "excluded_posts":excluded,
            "patterns":{key:summarize(rows) for key,rows in sorted(dimensions.items())},
            "individual_features":{key:summarize(rows) for key,rows in sorted(individual.items())},
            "links":links, "policy_version":policy["version"], "images_required":False,
            "human_review":"pending", "demo_approved":False, "model_behavior_calls":0,
            "interpretation":"research traits and scoped rules, not completed actions or future behavior probabilities"}
