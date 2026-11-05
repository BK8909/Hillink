"""Experience linking: explicit sameness, distinction, and unresolved alternatives."""
from __future__ import annotations
from itertools import combinations


def link_experiences(facts, assertions=()):
    keys = sorted({row["experience_key"] for row in facts})
    parent = {key:key for key in keys}
    def root(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key
    allowed = {"registry", "explicit_body_reference", "explicit_visit_date", "distinct_product_context", "title_only", "publication_date_only"}
    fact_ids = {fact["fact_id"] for fact in facts}
    owners = {key:{fact.get("persona_id") for fact in facts if fact["experience_key"] == key} for key in keys}
    checked, pending = [], []
    for claim in assertions:
        if claim["left"] not in parent or claim["right"] not in parent or claim["basis"] not in allowed:
            raise ValueError("unknown_link_or_basis")
        if not claim.get("evidence_refs") or not set(claim["evidence_refs"]) <= fact_ids:
            raise ValueError("link_requires_traceable_evidence")
        if owners[claim["left"]] != owners[claim["right"]] or len(owners[claim["left"]]) != 1:
            raise ValueError("cross_author_experience_link_forbidden")
        if claim["basis"] in {"title_only", "publication_date_only"}:
            pending.append(dict(claim, status="not_sufficient_for_identity_or_independence"))
            continue
        if claim["relation"] == "same_experience":
            a,b = root(claim["left"]), root(claim["right"])
            parent[max(a,b)] = min(a,b)
        elif claim["relation"] not in {"distinct_experience", "same_visit", "distinct_visit"}:
            raise ValueError("unknown_relation")
        checked.append(claim)
    groups = {key:root(key) for key in keys}
    distinct, visit_same, visit_distinct = set(), set(), set()
    for claim in checked:
        pair = tuple(sorted((groups[claim["left"]], groups[claim["right"]])))
        if claim["relation"] in {"distinct_experience", "distinct_visit"}:
            if pair[0] == pair[1]:
                raise ValueError("same_and_distinct_experience_conflict")
            distinct.add(pair)
        if claim["relation"] == "same_visit":
            visit_same.add(pair)
        if claim["relation"] == "distinct_visit":
            visit_distinct.add(pair)
    if visit_same & visit_distinct:
        raise ValueError("same_and_distinct_visit_conflict")
    return {"groups": groups, "distinct_pairs": sorted(distinct), "same_visit_pairs": sorted(visit_same),
            "assertions": checked, "pending_assertions": pending,
            "scope_note": "different experiences need not be different stays; registry/basis truth still needs review"}


def recurrence(groups, links):
    """A clique is a conservative lower bound on distinct experiences, not all unknown=one.

    Exact for up to18 groups; a greedy valid lower bound for larger collections.
    Uncertain groups retain discounted mass and an upper-bound count.
    """
    keys = sorted(set(groups))
    distinct = {tuple(pair) for pair in links["distinct_pairs"]}
    best = []
    if len(keys) <= 18:
        for size in range(len(keys), 0, -1):
            found = next((list(subset) for subset in combinations(keys, size)
                          if all(tuple(sorted(pair)) in distinct for pair in combinations(subset,2))), None)
            if found:
                best = found
                break
    else:
        for start in keys:
            candidate = [start]
            for key in keys:
                if key != start and all(tuple(sorted((key,k))) in distinct for k in candidate):
                    candidate.append(key)
            if len(candidate) > len(best):
                best = candidate
    # Experience repetition and independent visit repetition are not synonyms.
    visit_parent = {key:key for key in keys}
    def visit_root(key):
        while visit_parent[key] != key:
            key = visit_parent[key]
        return key
    for left,right in links["same_visit_pairs"]:
        if left in visit_parent and right in visit_parent:
            a,b = visit_root(left),visit_root(right)
            visit_parent[max(a,b)] = min(a,b)
    linked_visit_groups = len({visit_root(key) for key in keys})
    return {"minimum_distinct_experiences": len(best), "maximum_possible_experiences": len(keys),
            "same_visit_linked_groups_upper_bound":linked_visit_groups,
            "independent_visit_count_not_established_by_distinct_products":True,
            "independent_core": sorted(best), "unresolved_groups": sorted(set(keys) - set(best)),
            "algorithm": "exact_clique_lower_bound" if len(keys) <= 18 else "greedy_valid_lower_bound_not_exact"}
