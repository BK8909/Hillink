"""B: evidence-weighted, context-scoped author integration (unlearned research policy)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import math

from . import VERSION

POLICY = json.loads(Path(__file__).with_name("policy.json").read_text())
TRAITS = {
    "new_experience_trial": {"new_trial"}, "premium_experience": {"premium"},
    "food_engagement": {"food", "pizza", "garlic", "olive_oil"},
    "space_atmosphere": {"space", "atmosphere"}, "seasonal_event_engagement": {"seasonal_event"},
    "discount_utilization": {"discount_used"}, "alcohol_familiarity": {"wine", "beer"},
    "rest_orientation": {"rest"},
    "post_value_appraisal": {"value_appraisal"}, "prepurchase_information": set(),
}
ACTUAL_KINDS = {"participation", "purchase"}
USABLE_TIMES = {"source_experience", "past_experience"}


def _eligible(post, policy):
    if post["author_link_status"] == "unconfirmed":
        return "unconfirmed_author"
    if post["advertising"]["status"] in policy["exclude_sponsorship_statuses"]:
        return "advertising_review_pending"
    return None


def _source_groups(rows):
    """Union duplicate spans/content + reviewed event identities before scoring.

    All unlinked records are capped as ONE unresolved group per trait. This is a
    lower-bound recurrence policy, not a claim they really are the same event.
    """
    parents = list(range(len(rows)))
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    indexes = {}
    fingerprint_events = {}
    for row in rows:
        if row["event_id"]:
            fingerprint_events.setdefault(row["private_content_fingerprint"], set()).add(row["event_id"])
    for i, row in enumerate(rows):
        # Identical short descriptions can occur on confirmed different visits.
        # Do not collapse them solely by text equality.
        keys = [] if len(fingerprint_events.get(row["private_content_fingerprint"], set())) > 1 else [("content", row["private_content_fingerprint"])]
        if row["event_id"]:
            keys.append(("event", row["event_id"]))
        else:
            keys.append(("unresolved", "one_conservative_group"))
        for key in keys:
            if key in indexes:
                parents[find(i)] = find(indexes[key])
            indexes[key] = i
    groups = {}
    for i, row in enumerate(rows):
        groups.setdefault(find(i), []).append(row)
    return list(groups.values())


def _matches(row, trait):
    if trait == "prepurchase_information":
        return row["kind"] == "prepurchase_information"
    if trait == "post_value_appraisal":
        return row["kind"] == "appraisal" and "value_appraisal" in row["tags"]
    return bool(set(row["tags"]) & TRAITS[trait])


def aggregate(posts, policy=None):
    policy = deepcopy(POLICY if policy is None else policy)
    coefficients = list(policy["weights"].values()) + list(policy["confidence_multipliers"].values()) + [policy["trait_score_cap"], policy["repeat_bonus_cap"], policy["cross_domain_bonus_cap"]]
    if any(type(x) not in {int, float} or not math.isfinite(x) or x < 0 for x in coefficients) or not policy["trait_score_cap"]:
        raise ValueError("nonnegative_finite_research_policy_required")
    if not posts or len({p["author_group_id"] for p in posts}) != 1:
        raise ValueError("one_confirmed_author_group_required")
    if len({p["post_id"] for p in posts}) != len(posts):
        raise ValueError("duplicate_post_id")
    if len({p["source_class"] for p in posts}) != 1:
        raise ValueError("synthetic_and_actual_corpora_must_not_mix")
    for post in posts:
        if post.get("stage") != "A_post_extraction" or post.get("version") != VERSION:
            raise ValueError("normalized_stage_A_required")
        required = {"evidence_id", "kind", "actor", "time_scope", "tags", "confidence", "context_tags", "dimension", "event_id", "visit_id", "domain", "polarity", "private_content_fingerprint"}
        if any(not required <= row.keys() for row in post["statements"]):
            raise ValueError("normalized_statement_fields_required")
    identities = [row["evidence_id"] for post in posts for row in post["statements"]]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate_evidence_id")
    eligible, excluded = [], []
    dimensions = {key: [] for key in ("participation_history", "new_experience_trial", "prepurchase_criteria", "post_appraisal", "specific_preference", "revisit_expression")}
    for post in sorted(posts, key=lambda p: p["post_id"]):
        reason = _eligible(post, policy)
        if reason:
            excluded.append({"post_id": post["post_id"], "reason": reason, "facts_retained_in_stage_A": True})
            continue
        for statement in post["statements"]:
            if statement["actor"] not in {"author", "author_inferred"} or statement["time_scope"] not in USABLE_TIMES:
                continue
            row = deepcopy(statement)
            row["post_id"], row["media_status"] = post["post_id"], post["media_status"]
            # Textually reported spending is usable without a receipt. Explicit
            # listed prices/unknown amount kinds never create premium spend.
            threshold = policy["premium_price_threshold_krw"].get(row["domain"])
            if row["kind"] == "purchase" and threshold and row.get("amount_kind") in {"reported_paid", "order_amount"} and (row.get("amount_krw") or 0) >= threshold:
                row["tags"] = sorted(set(row["tags"]) | {"premium"})
            eligible.append(row)
            dimensions[row["dimension"]].append(row["evidence_id"])
    eligible.sort(key=lambda row: row["evidence_id"])
    dimensions = {key: sorted(set(refs)) for key, refs in dimensions.items()}
    confirmed_actions = [r for r in eligible if r["kind"] in ACTUAL_KINDS and r["event_id"]]
    varied_domains = {r["domain"] for r in confirmed_actions if r["domain"] != "other"}
    varied_events = {r["event_id"] for r in confirmed_actions}
    # Broad exploration is an active inference, NOT proof every visit was new.
    broad_trial_inference = len(varied_domains) >= 2 and len(varied_events) >= 2
    traits = {}
    for trait in TRAITS:
        rows = [r for r in eligible if _matches(r, trait) or (trait == "new_experience_trial" and broad_trial_inference and r["kind"] in ACTUAL_KINDS and r["domain"] != "other")]
        counter = [r for r in rows if r["kind"] == "decline" or r["kind"] == "specific_preference" and r["polarity"] == "negative"]
        support = [r for r in rows if r not in counter]
        group_scores, action_groups = [], []
        for group in _source_groups(support):
            def strongest(kinds):
                return max((policy["confidence_multipliers"][r["confidence"]] for r in group if r["kind"] in kinds), default=0)
            actual = strongest(ACTUAL_KINDS)
            mention = strongest({"positive_mention", "specific_preference"})
            if trait == "post_value_appraisal":
                # Evaluating value rigorously is not the same as avoiding price.
                base = policy["weights"]["positive_mention"] * strongest({"appraisal"})
            elif trait == "prepurchase_information":
                base = policy["weights"]["actual_action"] * strongest({"prepurchase_information"})
            else:
                base = max(policy["weights"]["actual_action"] * actual, policy["weights"]["positive_mention"] * mention)
            purchase = policy["weights"]["purchase_bonus"] * strongest({"purchase"}) if base else 0
            motive = policy["weights"]["explicit_motive_bonus"] * strongest({"explicit_motive"})
            if not base and not motive:
                continue
            visits = sorted({r["visit_id"] for r in group if r["visit_id"]})
            # A single merged event cannot count as several visits, even if the
            # caller supplied conflicting visit mappings.
            if len(visits) > 1:
                raise ValueError("same_event_has_conflicting_visit_links")
            entry = {"base": base, "purchase_bonus": purchase, "motive_bonus": motive,
                     "total": round(base + purchase + motive, 6), "evidence_ids": sorted({r["evidence_id"] for r in group}),
                     "visit_ids": visits, "event_ids": sorted({r["event_id"] for r in group if r["event_id"]}),
                     "domains": sorted({r["domain"] for r in group}), "actual_action": bool(actual),
                     "unresolved_group": not bool(visits)}
            group_scores.append(entry)
            if actual:
                action_groups.append(entry)
        # Only actual actions in reviewed distinct visits support repeat bonuses.
        visits = {v for g in action_groups for v in g["visit_ids"]}
        domains = {d for g in action_groups for d in g["domains"] if d != "other"}
        repeat_bonus = min(max(0, len(visits) - 1), policy["repeat_bonus_cap"]) * policy["weights"]["cross_visit_bonus"]
        # Multiple descriptions/domains in ONE merged event do not earn diversity.
        diversity = min(max(0, len(domains) - 1), max(0, len(action_groups) - 1), policy["cross_domain_bonus_cap"]) * policy["weights"]["cross_domain_bonus"]
        raw = sum(g["total"] for g in group_scores) + repeat_bonus + diversity
        score = min(raw, policy["trait_score_cap"])
        traits[trait] = {"strength_score": round(score, 6), "raw_before_cap": round(raw, 6), "scale_max": policy["trait_score_cap"],
                         "status": "strong_provisional" if score >= 6 and len(visits) >= 2 else "context_supported_inference" if score else "no_support_in_current_extraction",
                         "derivation": "varied_actual_participation_inference_not_all_first_visits" if trait == "new_experience_trial" and broad_trial_inference else "scoped_evidence_aggregation",
                         "independent_confirmed_visits": len(visits), "scored_event_groups": len(group_scores),
                         "unresolved_groups": sum(g["unresolved_group"] for g in group_scores),
                         "evidence_count": len({r["evidence_id"] for r in support}),
                         "source_location_count": len({(r["post_id"], tuple(r["span"])) for r in support}),
                         "repeat_bonus": repeat_bonus, "cross_domain_bonus": diversity, "contributions": group_scores,
                         "counter_cases": [{"evidence_id": r["evidence_id"], "tags": r["tags"], "context_tags": r["context_tags"], "kind": r["kind"]} for r in counter],
                         "scope_domains": sorted({r["domain"] for r in support}),
                         "context_tags": sorted({t for r in support for t in r["context_tags"]}),
                         "meaning": "engagement/experience signal, not automatic enjoyment, purchase probability or universal future preference"}
    return {"version": VERSION, "stage": "B_author_integration", "persona_id": posts[0]["author_group_id"],
            "source_class": posts[0]["source_class"], "source_post_count": len(posts), "source_post_ids": sorted(p["post_id"] for p in posts), "excluded_sources": excluded,
            "six_dimensions": dimensions, "derived_traits": traits,
            "specific_preferences": [{"evidence_id": r["evidence_id"], "tags": r["tags"], "polarity": r["polarity"], "scope": "stated_experience_only"} for r in eligible if r["kind"] == "specific_preference"],
            "policy_version": policy["version"], "policy_weights": policy["weights"],
            "images_required": False, "image_absence_penalty": 0,
            "source_semantics_verified": False, "human_review": "pending", "demo_approved": False, "model_calls": 0}


def shareable_stage_a(post):
    """No raw quotes, private content fingerprints or original text hashes in export."""
    result = deepcopy(post)
    result.pop("private_source_sha256", None)
    for row in result["statements"]:
        row.pop("private_content_fingerprint", None)
    return result


def validate_profile(profile, source_posts, policy=None):
    """Recompute lineage/scores/status, not a source authenticity or taste oracle."""
    try:
        expected = aggregate(source_posts, policy)
    except (ValueError, KeyError, TypeError) as error:
        return ["invalid_stage_A_or_policy:" + type(error).__name__]
    return [] if expected == profile else ["profile_not_reproducible_from_supplied_evidence_and_policy"]


def compare_scopes(posts):
    scopes = [("walkerhill_only", {"walkerhill"}), ("related_added", {"walkerhill", "related"}), ("recent_added", {"walkerhill", "related", "recent"})]
    result, previous, previous_evidence = {}, {}, set()
    for name, allowed in scopes:
        selected = [p for p in posts if p["scope"] in allowed]
        if not selected:
            result[name] = {"status": "source_unavailable_not_evaluated"}
            continue
        profile = aggregate(selected)
        scores = {trait: row["strength_score"] for trait, row in profile["derived_traits"].items()}
        evidence = {e for refs in profile["six_dimensions"].values() for e in refs}
        newly_requested_scope = {"walkerhill_only": "walkerhill", "related_added": "related", "recent_added": "recent"}[name]
        new_scope_count = sum(p["scope"] == newly_requested_scope for p in selected)
        result[name] = {"status": "computed_from_available_sources" if new_scope_count else "no_new_scope_sources_not_an_expansion_test",
                        "new_scope_post_count": new_scope_count, "profile": profile, "score_delta_from_previous_scope": {k: round(v - previous.get(k, 0), 6) for k, v in scores.items()},
                        "new_evidence_ids": sorted(evidence - previous_evidence)}
        previous = scores
        previous_evidence = evidence
    return result
