"""Transparent exploratory profile-fit scorer; no learned preferences or probabilities."""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_WEIGHTS = json.loads((HERE / "decision_weights_v2.json").read_text(encoding="utf-8"))
CATEGORY_ORDER = ("personal_fit", "trip_fit", "engagement_fit", "value_fit", "statistical_support", "context_adjustment")

def evaluate_option(option: dict, signals: list[dict], weights: dict | None = None) -> dict:
    weights = weights or DEFAULT_WEIGHTS["weights"]
    code = option["option_code"]
    if option.get("available", True) is False:
        return {"option_code": code, "feasible": False, "score": None, "categories": {}, "signals": [], "confidence": "not_applicable"}
    used, seen = [], set()
    totals = {k: 0.0 for k in CATEGORY_ORDER}
    for s in signals:
        if code not in s.get("options", []): continue
        cat = s["category"]
        if cat not in totals: raise ValueError("unknown_category:" + cat)
        root = s.get("evidence_root") or s["signal_id"]
        # One source root is one vote per option even when represented in
        # multiple derived profile categories (e.g. purpose + facility breadth).
        if root in seen: continue
        seen.add(root)
        direction = s["direction"]
        if direction not in {-2, -1, 0, 1, 2}: raise ValueError("direction_out_of_range")
        conf, rel = float(s["reliability"]), float(s["relevance"])
        if not 0 <= conf <= 1 or not 0 <= rel <= 1: raise ValueError("factor_out_of_range")
        contribution = direction * conf * rel * float(weights[cat])
        totals[cat] += contribution
        used.append({**s, "contribution": round(contribution, 4), "weight": weights[cat]})
    score = round(sum(totals.values()), 4)
    abs_sum = sum(abs(s["contribution"]) for s in used)
    confidence = "low" if not used or abs_sum == 0 else "moderate" if abs_sum >= 3 else "low"
    return {"option_code": code, "feasible": True, "score": score, "categories": {k: round(v, 4) for k, v in totals.items()},
            "signals": used, "confidence": confidence, "is_probability": False}

def decide(options: list[dict], signals: list[dict], weights: dict | None = None, tie_tolerance=0.25) -> dict:
    if not options or len({o["option_code"] for o in options}) != len(options): raise ValueError("unique_nonempty_options_required")
    rows = [evaluate_option(o, signals, weights) for o in options]
    feasible = sorted((r for r in rows if r["feasible"]), key=lambda x: (-x["score"], x["option_code"]))
    if not feasible: return {"method": "profile_fit_v2", "selected": None, "status": "no_feasible_options", "options": rows}
    margin = feasible[0]["score"] - feasible[1]["score"] if len(feasible) > 1 else None
    tie = margin is not None and margin <= tie_tolerance
    return {"method": "profile_fit_v2", "weights_version": DEFAULT_WEIGHTS["version"],
        "selected": None if tie else feasible[0]["option_code"],
        "tie_break_candidate": feasible[0]["option_code"] if tie else None,
        "status": "unresolved_tie" if tie else "ranked_candidate",
        "tie_candidates": [r["option_code"] for r in feasible if feasible[0]["score"] - r["score"] <= tie_tolerance],
        "margin": margin, "confidence": "low" if tie or (feasible[0]["score"] < 1) else feasible[0]["confidence"],
        "is_probability": False, "options": rows}

def sensitivity(options, signals, weights=None):
    base = weights or DEFAULT_WEIGHTS["weights"]
    result = {"base": decide(options, signals, base)}
    for category in CATEGORY_ORDER:
        for multiplier in (.75, 1.25):
            varied = dict(base); varied[category] = round(base[category] * multiplier, 4)
            result[f"{category}x{multiplier}"] = decide(options, signals, varied)
    result["reversed_option_order"] = decide(list(reversed(options)), signals, base)
    return result
