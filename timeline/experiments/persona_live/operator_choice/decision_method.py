"""Pre-choice ordinal evidence comparison. No customer IDs, learned weights or LLMs.

Directional cues are compared by (relevance, grounding, importance), never summed.
Shared evidence is counted once, common advantages cancel, unresolved tradeoffs
remain a frontier. A stable tie policy permits execution without inventing taste.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from .rules import digest

VERSION = "ordinal_evidence_method_v1"
RELEVANCE = {"weak": 0, "domain": 1, "exact": 2}
GROUNDING = {"scenario_policy": 0, "population_matched": 1, "bounded_inference": 1,
             "card_stated": 2, "source_checked": 3, "stipulated_current_goal": 3}
IMPORTANCE = {"incidental": 0, "preference": 1, "goal": 2}
LAYERS = ("personal_observation", "personal_inference", "population_prior", "current_context")

# Current option affordances are declared experiment assumptions, NOT persona traits.
ATTRIBUTES = {
    "REST": {"rest": True, "private": True, "water": False, "exploration": False},
    "WALK": {"rest": False, "view": True, "water": False, "exploration": True},
    "GRAND_POOL": {"indoor_water": True, "outdoor_water": False, "water": True, "rest": False},
    "VISTA_POOL": {"indoor_water": True, "outdoor_water": False, "water": True, "rest": False},
    "RIVERPARK": {"indoor_water": False, "outdoor_water": True, "water": True, "rest": False},
    "SKYARD": {"view": True, "water": False, "rest": False, "exploration": True},
    "THEATRE_OF_LIGHT": {"culture": True, "water": False, "rest": False, "exploration": True},
    "DOUGLAS_SNACK": {"dining": True, "water": False, "rest": False},
    "FOREST_PARK": {"water": False, "rest": False, "exploration": True},
    "BEER_FESTIVAL": {"water": False, "rest": False, "exploration": True, "beer_optional": True},
    "WINE_FAIR": {"water": False, "rest": False, "exploration": True, "wine_optional": True},
}


def options_from_stage(stage: dict) -> list[dict]:
    result = []
    for o in stage["options"]:
        attrs = {"venue": o["code"], "onsite": True, "quiet": None, "conversation": None, **ATTRIBUTES.get(o["code"], {})}
        attrs["outdoor"] = o["code"] in {"WALK", "RIVERPARK", "SKYARD", "FOREST_PARK", "WINE_FAIR", "BEER_FESTIVAL"}
        attrs["payment_required"] = True if o["code"] in {"RIVERPARK", "THEATRE_OF_LIGHT", "BEER_FESTIVAL", "WINE_FAIR"} else False if o["code"] in {"REST", "WALK", "DOUGLAS_SNACK"} else None
        result.append({"option_code": o["code"], "attributes": attrs,
                       "attribute_provenance": "scenario_assumption:option_affordance_v1",
                       "domain": "activity", "available": True, "known_total_cost_krw": 0 if o["code"] in {"REST", "WALK"} else None})
    return result


def rank(cue: dict) -> tuple[int, int, int]:
    return (RELEVANCE[cue["relevance"]], GROUNDING[cue["grounding"]], IMPORTANCE[cue["importance"]])


def _cue(rule, option, *, layer, relevance, grounding, importance, direction, aspect, rationale):
    return {"cue_id": rule["rule_id"] + ":" + option["option_code"], "rule_id": rule["rule_id"],
            "evidence_ids": list(rule["evidence_ids"]), "layer": layer, "direction": direction,
            "relevance": relevance, "grounding": grounding, "importance": importance,
            "aspect": aspect, "rationale": rationale,
            "source_status": rule["verification_status"], "root_group": None}


def _apply(rule: dict, option: dict, context: dict) -> tuple[list[dict], list[dict]]:
    if not rule["decision_usable"]:
        return [], [{"rule_id": rule["rule_id"], "reason": "context_only_or_unusable_no_preference_score"}]
    predicate = rule["predicate"]
    attrs = option["attributes"]
    if "goals" in predicate:
        if not context.get("goal_continuity", False):
            return [], [{"rule_id": rule["rule_id"], "reason": "past_goal_not_assumed_current"}]
        hits = [g for g in predicate["goals"] if attrs.get(g) is True]
        if not hits:
            return [], [{"rule_id": rule["rule_id"], "reason": "goal_not_matched_not_dislike"}]
        specific = any(g not in {"exploration", "conversation"} for g in hits)
        return [_cue(rule, option, layer="personal_inference", relevance="exact" if specific else "domain",
                     grounding="bounded_inference", importance="goal", direction="support", aspect="goal_fit",
                     rationale="과거 목적을 이번에도 참고한다는 명시적 가정 하의 일치: " + ", ".join(hits))], []
    if option["domain"] not in predicate["domains"]:
        return [], [{"rule_id": rule["rule_id"], "reason": "outside_recorded_context"}]
    attribute = predicate["attribute"]
    if attribute not in attrs or attrs[attribute] is None:
        return [], [{"rule_id": rule["rule_id"], "reason": "unknown_option_attribute", "attribute": attribute}]
    if attrs[attribute] != predicate["expected"]:
        return [], [{"rule_id": rule["rule_id"], "reason": "unmatched_preference_not_automatic_avoidance"}]
    return [_cue(rule, option, layer="personal_observation", relevance="exact",
                 grounding="source_checked" if rule["verification_status"] == "source_verified" else "card_stated",
                 importance="preference", direction=predicate["direction"], aspect=attribute,
                 rationale="기록된 선호/평가와 명시적 선택지 속성이 같은 범위에서 연결됨")], []


def match_prior(p: dict, facts: dict, scenario: str, domain: str) -> list[str]:
    """A measured participation rate is not a relative-choice preference."""
    errors = []
    required = ("prior_id", "source_url", "survey_period", "country", "sample", "measured_question", "result", "population", "reviewed_by")
    if any(not p.get(k) for k in required):
        errors.append("incomplete_prior_metadata")
    if p.get("review_status") != "verified":
        errors.append("unreviewed_prior")
    measurement = p.get("measurement", {})
    if measurement.get("construct") not in {"pairwise_choice", "stated_activity_preference"} or measurement.get("domain") != domain:
        errors.append("measurement_does_not_support_this_choice")
    if scenario not in p.get("scenarios", []):
        errors.append("scenario_mismatch")
    if not p.get("applicability"):
        errors.append("no_population_link")
    for field, expected in p.get("applicability", {}).items():
        fact = facts.get(field, {})
        if fact.get("provenance") != "observed" or fact.get("status") != "known" or fact.get("value") is None or fact.get("value") != expected:
            errors.append("unobserved_population_attribute:" + field)
    return errors


def _groups(cues: list[dict]) -> None:
    """Connected citation sets: observation/inference reuse cannot accumulate votes."""
    groups: list[set[str]] = []
    for cue in cues:
        ids = set(cue["evidence_ids"]) or {cue["rule_id"]}
        if cue["layer"] == "population_prior":
            ids = {"population:" + x for x in ids}
        overlap = [g for g in groups if g & ids]
        for g in overlap:
            ids |= g
            groups.remove(g)
        groups.append(ids)
    for cue in cues:
        ids = set(cue["evidence_ids"]) or {cue["rule_id"]}
        if cue["layer"] == "population_prior":
            ids = {"population:" + x for x in ids}
        cue["root_group"] = "|".join(sorted(next(g for g in groups if g & ids)))


def _reduce(row: dict) -> None:
    grouped = defaultdict(list)
    for c in row["evaluated_cues"]:
        grouped[c["root_group"]].append(c)
    active = []
    for group, cues in grouped.items():
        best_rank = max(rank(c) for c in cues)
        best = [c for c in cues if rank(c) == best_rank]
        if len({c["direction"] for c in best}) > 1:
            row["actual_conflicts"].append({"kind": "same_root_opposing_claims", "root_group": group, "cue_ids": [c["cue_id"] for c in best]})
            continue
        chosen = sorted(best, key=lambda c: c["cue_id"])[0]
        active.append(chosen)
        row["suppressed_duplicates"].extend(c["cue_id"] for c in cues if c is not chosen)
    # Actual conflicting personal directions on the same aspect are distinct
    # from generic warnings and unverified reviewer reports.
    by_aspect = defaultdict(list)
    for c in active:
        if c["layer"].startswith("personal"):
            by_aspect[c["aspect"]].append(c)
    unresolved = set()
    for aspect, cues in by_aspect.items():
        if len({c["direction"] for c in cues}) > 1:
            row["actual_conflicts"].append({"kind": "personal_aspect_conflict", "aspect": aspect, "cue_ids": [c["cue_id"] for c in cues]})
            best_rank = max(rank(c) for c in cues)
            if len({c["direction"] for c in cues if rank(c) == best_rank}) > 1:
                unresolved.update(c["cue_id"] for c in cues)
    filtered = []
    for c in active:
        if c["cue_id"] in unresolved:
            continue
        blockers = [x for x in active if x["layer"] == "personal_observation" and x["direction"] == "oppose"
                    and x["aspect"] == c["aspect"] and rank(x) >= rank(c)]
        if c["layer"] == "population_prior" and c["direction"] == "support" and blockers:
            row["suppressed_prior_conflicts"].append({"cue_id": c["cue_id"], "blocked_by": [x["cue_id"] for x in blockers]})
        else:
            filtered.append(c)
    row["active_cues"] = filtered
    row["support"] = [c for c in filtered if c["direction"] == "support"]
    row["opposition"] = [c for c in filtered if c["direction"] == "oppose"]


def _compare(a: dict, b: dict) -> dict:
    ca = {c["root_group"]: c for c in a["active_cues"]}
    cb = {c["root_group"]: c for c in b["active_cues"]}
    differences, common = [], []
    for root in sorted(ca.keys() | cb.keys()):
        x, y = ca.get(root), cb.get(root)
        if x and y and x["direction"] == y["direction"] and rank(x) == rank(y):
            common.append(root)
            continue
        directional = []
        if x:
            directional.append((rank(x), 1 if x["direction"] == "support" else -1))
        if y:
            directional.append((rank(y), -1 if y["direction"] == "support" else 1))
        top = max(v[0] for v in directional)
        signs = {sign for r, sign in directional if r == top}
        differences.append({"root_group": root, "rank": list(top), "sign": signs.pop() if len(signs) == 1 else 0})
    if differences:
        top = max(tuple(d["rank"]) for d in differences)
        signs = {d["sign"] for d in differences if tuple(d["rank"]) == top}
        winner = a["option_code"] if signs == {1} else b["option_code"] if signs == {-1} else None
    else:
        winner = None
    return {"a": a["option_code"], "b": b["option_code"], "winner": winner,
            "decisive_differences": differences, "common_non_discriminating_roots": common}


def decide(rules: list[dict], options: list[dict], context: dict, priors: list[dict] | None = None) -> dict:
    """One decision from input only. Runs/Gold/reviewer answers are never inputs."""
    codes = [o["option_code"] for o in options]
    if len(codes) != len(set(codes)) or not options:
        raise ValueError("unique_nonempty_options_required")
    rows, prior_exclusions = [], []
    for option in options:
        row = {"option_code": option["option_code"], "feasible": option["available"], "evaluated_cues": [],
               "unknowns": [], "context_only": [], "actual_conflicts": [], "suppressed_duplicates": [],
               "suppressed_prior_conflicts": [], "reported_conflicts_used": False,
               "general_cautions": ["이용≠선호", "미선택≠비선호", "카드 요약≠직접 앵커 검증"]}
        for rule in rules:
            cues, notes = _apply(rule, option, context)
            row["evaluated_cues"].extend(cues)
            row["unknowns"].extend(n for n in notes if n["reason"] == "unknown_option_attribute")
            row["context_only"].extend(n for n in notes if n["reason"] != "unknown_option_attribute")
        if context.get("current_goal") and context.get("current_goal_status") == "explicit_scenario_condition" and option["attributes"].get(context["current_goal"]) is True:
            row["evaluated_cues"].append({"cue_id": "CTX-current-goal:" + option["option_code"], "rule_id": "CTX-current-goal",
                "evidence_ids": ["CTX-current-goal"], "layer": "current_context", "direction": "support",
                "relevance": "exact", "grounding": "stipulated_current_goal", "importance": "goal",
                "aspect": "current_goal", "rationale": "별도로 명시한 이번 방문의 우선 목적. 과거 개인 성향이나 관측 기억을 새로 만든 것이 아님.",
                "source_status": "explicit_scenario_condition", "root_group": None})
        for aspect, applies, why in (
            ("payment", context.get("cost_policy") == "opportunity_cost" and option["attributes"].get("payment_required") is True,
             "유료 활동에는 지출 기회비용이 있다는 공개된 일반 판단 정책. 고객의 가격 회피 성향이 아님."),
            ("weather", context.get("weather") == "rain" and option["attributes"].get("outdoor") is True,
             "비를 맞는 야외 활동의 부담이라는 현재 상황 판단. 개인의 야외 기피 기억이 아님.")
        ):
            if applies:
                row["evaluated_cues"].append({"cue_id": "CTX-" + aspect + ":" + option["option_code"],
                    "rule_id": "CTX-" + aspect, "evidence_ids": ["CTX-" + aspect], "layer": "current_context",
                    "direction": "oppose", "relevance": "exact", "grounding": "scenario_policy", "importance": "incidental",
                    "aspect": aspect, "rationale": why, "source_status": "declared_experiment_policy", "root_group": None})
        for p in priors or []:
            reasons = match_prior(p, context.get("population_facts", {}), context["scenario"], option["domain"])
            if reasons:
                prior_exclusions.append({"prior_id": p.get("prior_id"), "reasons": reasons})
                continue
            predicate = p["predicate"]
            if option["attributes"].get(predicate["attribute"]) == predicate["expected"]:
                row["evaluated_cues"].append({"cue_id": p["prior_id"] + ":" + option["option_code"], "rule_id": p["prior_id"],
                    "evidence_ids": [p["prior_id"]], "layer": "population_prior", "direction": predicate["direction"],
                    "relevance": "exact", "grounding": "population_matched", "importance": "incidental",
                    "aspect": predicate["attribute"], "rationale": "검수된 문항과 관측 집단 연결의 제한된 보조 근거", "source_status": "verified", "root_group": None})
        rows.append(row)
    _groups([c for row in rows for c in row["evaluated_cues"]])
    for row in rows:
        _reduce(row)
    feasible = [r for r in rows if r["feasible"]]
    if not feasible:
        raise ValueError("no_feasible_option")
    pairs = [_compare(a, b) for i, a in enumerate(feasible) for b in feasible[i + 1:]]
    defeated = {p["b"] if p["winner"] == p["a"] else p["a"] for p in pairs if p["winner"]}
    frontier = sorted(r["option_code"] for r in feasible if r["option_code"] not in defeated)
    cycle = not frontier
    if cycle:
        frontier = sorted(r["option_code"] for r in feasible)
    chosen = frontier[0]  # disclosed execution tie policy, not a customer preference
    chosen_row = next(r for r in rows if r["option_code"] == chosen)
    cue_index = {c["cue_id"]: c for r in rows for c in r["active_cues"]}
    decisive_roots = {d["root_group"] for p in pairs if p["winner"] == chosen for d in p["decisive_differences"]
                      if p["decisive_differences"] and tuple(d["rank"]) == max(tuple(x["rank"]) for x in p["decisive_differences"])}
    result = {"method_version": VERSION, "options": rows, "pairwise": pairs, "frontier": frontier,
              "selected": chosen, "selection_basis": "unique_evidence_frontier" if len(frontier) == 1 else "stable_code_tie_policy",
              "uncertainty": {"unresolved_frontier": len(frontier) > 1, "cycle": cycle,
                              "source_anchors_pending": any(r["verification_status"] != "source_verified" for r in rules if r["decision_usable"]),
                              "choice_changes_under_reverse_tie_policy": len(frontier) > 1},
              "factor_contributions": {layer: {
                  "available_in_selected": [c["cue_id"] for c in chosen_row["active_cues"] if c["layer"] == layer],
                  "decisive_comparisons": sorted(c["cue_id"] for c in cue_index.values() if c["layer"] == layer and c["root_group"] in decisive_roots)
              } for layer in LAYERS},
              "prior_exclusions": prior_exclusions,
              "contribution_kind": "computed_prechoice_cues_not_model_self_report",
              "behavior_probability": None}
    result["input_sha256"] = digest({"rules": rules, "options": options, "context": context, "priors": priors or []})
    return result


def audit_choice(choice: str, frozen: dict) -> dict:
    """Audit against an already-frozen table; never recompute ranks after output."""
    feasible = {r["option_code"] for r in frozen["options"] if r["feasible"]}
    row = next((r for r in frozen["options"] if r["option_code"] == choice), None)
    return {"available": choice in feasible, "in_prechoice_frontier": choice in frozen["frontier"],
            "same_as_execution_tie_choice": choice == frozen["selected"], "prechoice_sha256": digest(frozen),
            "chosen_option_prechoice_factors": {layer: {
                "support": [c["cue_id"] for c in row["support"] if c["layer"] == layer] if row else [],
                "opposition": [c["cue_id"] for c in row["opposition"] if c["layer"] == layer] if row else []}
                for layer in LAYERS},
            "requires_human_review": True, "semantic_truth_verified": False}
