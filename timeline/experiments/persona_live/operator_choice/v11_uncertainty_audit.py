"""Versioned sensitivity probe, not a replacement for the frozen V1.1 policy.

Only the probe table changes; source profiles/environments/V1.1 packets are read-only.
The selection calculation reuses the baseline utility/regret and feasibility rules.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path

from . import dynamic_operating_choice_v1_1 as engine
from . import dynamic_wine_study_v1_1 as study
from .dynamic_operating_choice_v1 import digest

HERE = Path(__file__).resolve().parent
OUT = HERE / "v11_audit_artifacts"
PROBE_VERSION = "v11_uncertainty_audit_0.1"


def selection_from_table(table, profile, env, policy):
    """Baseline-equivalent selector with a supplied experimental interval table."""
    baseline = engine.decide(profile, env, policy)
    rows = [r for r in table["options"] if r["feasible"]]
    variables = sorted({u["variable"] for r in rows for u in r["uncertainty"]})
    if len(variables) > 10:
        raise ValueError("audit_endpoint_limit")
    worlds = [dict(zip(variables, bits)) for bits in product((0, 1), repeat=len(variables))]
    best_scores = [max(engine._utility(row, world) for row in rows) for world in worlds]
    _, regrets = engine._best_regret(rows, worlds, best_scores, policy["numerical_tie_tolerance"])
    candidates = [{"option_id": row["option_id"], "action": row["action"], "worst_case_regret": round(regrets[row["option_id"]], 6),
                   "party_total_krw": row["party_total_krw"]} for row in rows]
    info = deepcopy(baseline["information_plan"])
    target = next(row for row in table["options"] if row["option_id"] == env["preview"]["target_option"])
    observable = sorted({u["variable"] for u in target["uncertainty"] if u["observable_in_preview"] and "menu_match" in env["preview"]["resolves"]})
    info["observable_variables"] = observable
    info["contingency"] = []
    if info["feasible"]:
        end = engine.minute(env["preview"]["end"])
        after = [r for r in rows if not engine.feasibility(next(o for o in env["options"] if o["option_id"] == r["option_id"]), env, end)]
        groups = {}
        for i, world in enumerate(worlds):
            groups.setdefault(tuple(world[v] for v in observable), []).append(i)
        remaining = 0
        for state, indices in groups.items():
            selected, group_regrets = engine._best_regret(after, [worlds[i] for i in indices], [best_scores[i] for i in indices], policy["numerical_tie_tolerance"])
            remaining = max(remaining, group_regrets[selected["option_id"]])
            info["contingency"].append({"observations": dict(zip(observable, state)), "prospective_option": selected["option_id"]})
        info["residual_opportunity_loss_index"] = remaining
        candidates.append({"option_id": "PREVIEW_PLAN", "action": "inspect_event", "worst_case_regret": round(remaining + info["inspection_cost_index"], 6),
                           "party_total_krw": env["preview"]["price_krw"] * env["visit"]["party_size"]})
    minimum = min(r["worst_case_regret"] for r in candidates)
    tied = [r for r in candidates if r["worst_case_regret"] - minimum <= policy["numerical_tie_tolerance"]]
    selected = min(tied, key=lambda r: (r["party_total_krw"], r["option_id"]))
    ordered = sorted(candidates, key=lambda r: (r["worst_case_regret"], r["party_total_krw"], r["option_id"]))
    other = next((r for r in ordered if r["option_id"] != selected["option_id"]), None)
    return {"action": selected["action"], "action_label": engine.LABELS[selected["action"]], "selected_option": selected["option_id"],
            "alternatives": ordered, "nearest_alternative": other,
            "choice_gap": round(other["worst_case_regret"] - selected["worst_case_regret"], 6) if other else None,
            "information_plan": info, "option_intervals": [{"option_id": r["option_id"],
                "low": round(r["fixed_score"] + sum(u["low"] for u in r["uncertainty"]), 6),
                "high": round(r["fixed_score"] + sum(u["high"] for u in r["uncertainty"]), 6),
                "uncertainty": r["uncertainty"]} for r in rows],
            "status": "offline_policy_probe_not_human_or_LLM_result", "model_calls": 0, "human_review": "pending", "demo_approved": False}


def probe(profile, env, menu_policy="baseline", lower_loss_fraction=.5, quantity_fraction=None, direct_dislike=None, policy=None):
    policy = deepcopy(engine.POLICY if policy is None else policy)
    table = engine.evaluate(profile, env, policy)
    target_id = env["preview"]["target_option"]
    row = next(r for r in table["options"] if r["option_id"] == target_id)
    food = next(t for t in row["terms"] if t["factor"] == "food_fit")
    menu_variables = [u for u in row["uncertainty"] if u["variable"].startswith("menu_match:")]
    if menu_policy not in {"baseline", "suppress_upside", "two_sided"}:
        raise ValueError("unknown_menu_probe_policy")
    if not 0 <= lower_loss_fraction <= 1:
        raise ValueError("loss_fraction_range")
    if menu_policy == "suppress_upside":
        row["uncertainty"] = [u for u in row["uncertainty"] if not u["variable"].startswith("menu_match:")]
    elif menu_policy == "two_sided":
        for variable in menu_variables:
            variable["low"] = -food["value"] * lower_loss_fraction
            variable["stage"] = "probe_lower_general_food_fit_to_possible_direct_match"
            variable["interpretation"] = "감소는 식음 적합성의 불확실성이다. 실제 불호를 부여한 것이 아니다. 만족도 자체를 관람으로 알아낸다는 뜻도 아니다."
    if quantity_fraction is not None:
        if not 0 <= quantity_fraction <= 1:
            raise ValueError("quantity_fraction_range")
        # Shared unknown amount affects both meal fulfillment and food fit.
        # No extra taste upside is added in this probe: no invented independent combinations.
        row["uncertainty"] = [u for u in row["uncertainty"] if not u["variable"].startswith("menu_match:")]
        food_and_meal = sum(t["value"] for t in row["terms"] if t["factor"] in {"food_fit", "current_meal_goal"})
        row["uncertainty"].append({"variable": "unconfirmed_food_amount", "low": -(1 - quantity_fraction) * food_and_meal,
                                  "high": 0, "observable_in_preview": False, "stage": "operator_unknown_portion_assumption"})
    if direct_dislike is not None:
        claim = next((c for c in profile["claims"] if c["claim_id"] == direct_dislike["claim_id"]), None)
        if claim is None or claim["aspect"] != "explicit_menu_dislike" or claim.get("scope") != "named_menu_feature":
            raise ValueError("direct_scoped_dislike_evidence_required")
        if claim.get("feature") != direct_dislike["feature"]:
            raise ValueError("dislike_feature_evidence_mismatch")
        if direct_dislike["source_status"] not in {"synthetic_fixture", "direct_source_verified"}:
            raise ValueError("explicit_dislike_provenance_required")
        if direct_dislike["source_status"] == "direct_source_verified" and (claim.get("review") != "human_review_approved" or not claim.get("anchors")):
            raise ValueError("direct_dislike_not_verified")
        option = next(o for o in env["options"] if o["option_id"] == target_id)
        if direct_dislike["feature"] in option["menu_tags"]:
            new_value = -policy["weights"]["food_experience"] * row["meal_adequacy"] * option["food_quality"]
            row["fixed_score"] += new_value - food["value"]
            food.update(value=new_value, claim_ids=[claim["claim_id"]], stage="explicit_scoped_dislike_probe")
            row["uncertainty"] = [u for u in row["uncertainty"] if not u["variable"].startswith("menu_match:")]
    result = selection_from_table(table, profile, env, policy)
    result["probe_parameters"] = {"menu_policy": menu_policy, "lower_loss_fraction": lower_loss_fraction,
                                  "quantity_fraction": quantity_fraction, "direct_dislike_source": direct_dislike}
    result["profile_sha256"], result["environment_sha256"] = digest(profile), digest(env)
    return result


def timing_metrics(env):
    option = next(o for o in env["options"] if o["option_id"] == env["preview"]["target_option"])
    booking = option["reservation"]
    return {"preview_end": env["preview"]["end"], "processing_minutes": booking["processing_minutes"],
            "deadline": booking["closes_at"], "now": env["now"],
            "current_booking_slack_minutes": engine.minute(booking["closes_at"]) - engine.minute(env["now"]) - booking["processing_minutes"],
            "slack_minutes": engine.minute(booking["closes_at"]) - engine.minute(env["preview"]["end"]) - booking["processing_minutes"]}


def _clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def run_audit():
    profile = engine.profile_input(json.loads(study.PROFILE_PATH.read_text(encoding="utf-8")))
    conditions = study.wine_conditions()
    result = {"version": PROBE_VERSION, "profile_sha256": digest(profile), "baseline_commit": "6f70aee9b72c5402edd8ab567c1c42d385ec1295",
              "menu_cases": {}, "menu_policy_grid": [], "sensitivity": [], "ABCD": {},
              "model_calls": 0, "human_review": "pending", "demo_approved": False}
    for condition, env in conditions.items():
        r = probe(profile, env)
        result["ABCD"][condition] = {"result": r, "changed_variable": {"A": "기본 음식3종·12만원", "B": "음식1종만", "C": "숙박객 혜택3만원만", "D": "가격16만원만"}[condition]}
    base = conditions["D"]
    cases = {"unknown_menu_adequate_quantity": deepcopy(base), "preferred_menu": deepcopy(base), "other_no_dislike": deepcopy(base)}
    cases["preferred_menu"]["options"][0].update(menu_tags=["pizza", "garlic", "olive_oil"], menu_details_complete=True)
    cases["other_no_dislike"]["options"][0].update(menu_tags=["seafood", "cheese"], menu_details_complete=True)
    for name, env in cases.items():
        result["menu_cases"][name] = {"environment_sha256": digest(env), "result": probe(profile, env)}
    result["menu_cases"]["unknown_quantity"] = {"result": probe(profile, base, quantity_fraction=1 / 3),
                                                      "assumption": "한 끼 충족과 식음 적합성이 함께 1/3~1배로 달라지는 가상 구간. 현재 관람으로 실제 양을 확인할 수 있다고 추가 가정하지 않음."}
    result["menu_cases"]["actual_dislike_blog41"] = {"status": "not_evaluable", "reason": "현재 승인 근거에 직접적인 음식 불호가 확인되지 않아 blog41에게 추가하지 않음"}
    synthetic = {"persona_id": "SYNTHETIC_DISLIKE_PROBE", "profile_version": "synthetic_fixture_only",
                 "claims": [{"claim_id": "SYN:dislike", "aspect": "explicit_menu_dislike", "value": "dislikes_fixture_feature",
                             "feature": "fixture_feature", "scope": "named_menu_feature", "review": "synthetic_not_human_review", "anchors": []}]}
    synthetic_env = deepcopy(base)
    synthetic_env["options"][0].update(menu_tags=["fixture_feature"], menu_details_complete=True)
    direct = {"claim_id": "SYN:dislike", "feature": "fixture_feature", "source_status": "synthetic_fixture"}
    result["synthetic_dislike_probe"] = {"status": "mechanism_fixture_not_customer_evidence", "result": probe(synthetic, synthetic_env, direct_dislike=direct)}
    for mode, loss in (("baseline", 0), ("suppress_upside", 0), ("two_sided", .5), ("two_sided", 1)):
        result["menu_policy_grid"].append({"mode": mode, "lower_food_fit_loss_fraction": loss, "result": probe(profile, base, mode, loss)})
    for name, values in (("general_cost", (.25, .5, .75)), ("novelty_upper", (0, .275, .55)), ("food_quality", (.4, .7, 1))):
        for value in values:
            env, policy = deepcopy(base), deepcopy(engine.POLICY)
            if name == "general_cost":
                policy["general_cost_attention"] = value
            elif name == "novelty_upper":
                policy["transfer_levels"]["new_experience_upper"] = value
            else:
                env["options"][0]["food_quality"] = value
            result["sensitivity"].append({"variable": name, "value": value, "price_context": 160000, "result": probe(profile, env, policy=policy)})
    for price in (160000, 200000):
        for axis, values in (("booking_delay", (0, 1, 3, 5)), ("preview_delay", (1, 3, 5)),
                             ("preview_duration", (10, 15, 16, 20)), ("time_after_planned_preview", (1, 3, 5)),
                             ("deadline", ("17:45", "17:50", "17:55")),
                             ("future_seats", ("assumed_remaining_for_planning_only", "unknown"))):
            for value in values:
                env = deepcopy(base)
                env["options"][0]["price_krw"] = price
                if axis == "booking_delay":
                    env["options"][0]["reservation"]["processing_minutes"] += value
                elif axis == "preview_delay":
                    for key in ("start", "end"):
                        env["preview"][key] = _clock(engine.minute(env["preview"][key]) + value)
                elif axis == "preview_duration":
                    env["preview"]["end"] = _clock(engine.minute(env["preview"]["start"]) + value)
                elif axis == "time_after_planned_preview":
                    env["now"] = _clock(engine.minute(env["preview"]["end"]) + value)
                elif axis == "deadline":
                    env["options"][0]["reservation"]["closes_at"] = value
                else:
                    env["preview"]["future_seats"] = value
                result["sensitivity"].append({"variable": axis, "value": value, "price_context": price,
                                               "time_scope": "hypothetical_later_time_snapshot_no_observed_menu_outcome" if axis == "time_after_planned_preview" else "ex_ante_replanning_at_17_00",
                                               "timing": timing_metrics(env), "result": probe(profile, env)})
    result["baseline_timing"] = timing_metrics(base)
    return result


def render_review(result):
    lines = ["# V1.1 불확실성·시간 경계 검수", "", "가상 조건·공통 연구 정책에 대한 규칙 계산이다. 독립 LLM 응답·실제 구매·사람 판정은 없다.", "",
             "| 조건 | 바꾼 변수 | 행동 | 가장 가까운 대안 | 차이 | 검수 질문 |", "|---|---|---|---|---:|---|"]
    questions = {"A": "새로운 경험의 가능성과 메뉴 정보 부족을 구별했는가?", "B": "C13 객실 식사 이력과 현재 가상 휴식 목표0.5를 별도 근거로 이해할 수 있는가?", "C": "혜택은 비용만 바꿨는데 왜 선택이 같거나 다른가?", "D": "예약과 확인의 작은 차이를 확고한 고가 구매 성향으로 읽고 있지 않은가?"}
    for key, cell in result["ABCD"].items():
        r = cell["result"]
        alt = r["nearest_alternative"]
        lines.append(f"| {key} | {cell['changed_variable']} | {r['action_label']} | {engine.LABELS[alt['action']]} | {r['choice_gap']:.3f} | {questions[key]} |")
    lines.extend(["", "개인 경험: C07 음식·풍미, C05/C12 공간 맥락, C02/C04/C06 같은 P6 묶음, C13 객실 식사. C08/C16은 사후 평가로만 보존한다.", "",
                  "정책·가상 조건: 메뉴 미확인의 상한, 새 경험 전이0~0.55, 최대 기회손실 방식, 일반 비용0.50, 현재 식사·휴식 목표, 대안 가격·품질·시간. 이 값들은 관측된 고객 심리나 확률이 아니다.", "",
                  "## 메뉴 처리 비교", "", "| 경우 | 행동·상태 |", "|---|---|"])
    for name, cell in result["menu_cases"].items():
        lines.append(f"| {name} | {cell['result']['action_label'] if 'result' in cell else cell['status'] + ': ' + cell['reason']} |")
    lines.extend(["", "직접 불호는 blog41에서 확인되지 않아 실행할 수 없다. 별도 합성 고객은 명시적 불호의 처리 경로만 검사하며 실제 고객 근거나 사람 정답이 아니다.", "",
                  "| 메뉴 정책 사본 | 일반 식음 적합성 손실 하한 | 행동 |", "|---|---:|---|"])
    for row in result["menu_policy_grid"]:
        lines.append(f"| {row['mode']} | {row['lower_food_fit_loss_fraction']} | {row['result']['action_label']} |")
    lines.extend(["", "## 계수와 시간 — 각 행은 한 변수 실험", "", "| 가격 | 변수 | 값 | 현재 시각 | 계획 관람후 여유 | 현재 예약 여유 | 관람 계획 | 행동 |", "|---:|---|---|---|---:|---:|---|---|"])
    for row in result["sensitivity"]:
        r = row["result"]
        timing = row.get("timing", {})
        # Baseline constraint wording uses the simulated post-preview time, not
        # necessarily env['now']; label that scope rather than implying no
        # immediate booking is possible at 17:00.
        constraints = [c.replace("현재 시각에서 예약 처리 불가", "관람 종료 후 예약 처리 불가") for c in r['information_plan']['constraints']]
        plan_status = "가능" if r['information_plan']['feasible'] else '; '.join(constraints)
        lines.append(f"| {row['price_context']:,} | {row['variable']} | {row['value']} | {timing.get('now', '—')} | {timing.get('slack_minutes', '—')} | {timing.get('current_booking_slack_minutes', '—')} | {plan_status} | {r['action_label']} |")
    lines.extend(["", "17:00에 지연을 미리 알고 다시 계획하는 경우에는 지금 예약할 수 있다. 현재 시각 자체가17:46 이후인 스냅샷에서는 그때의 예약 가능 여부를 계산한다. 후자는 실제 관람 완료·메뉴 관측이 발생했다는 기록이 아니며 가상 시간 스냅샷이다.", ""])
    lines.extend(["", "## 사람 판정", "", "각 축에 납득 / 보완 필요 / 납득 어려움과 구체적 이유를 기록한다.", "",
                  "| 조건 | 페르소나 충실도·이유 | 상황 적합성·이유 | 행동 개연성·이유 | 운영 활용성·이유 |", "|---|---|---|---|---|",
                  *[f"| {key} | 미검수 | 미검수 | 미검수 | 미검수 |" for key in result["ABCD"]], "",
                  "B에서는 휴식 목표를 없애면 일반 식당으로 바뀐다는 V1.1 대조를 함께 본다. D는 관측된 고가 상품 선호나 실제 가격 수용성으로 표시하지 않는다. 무표 LLM도 시스템 지시·후보 목록의 영향을 받으며, 보조 조건은 분석 보조를 받은 판단이다.", ""])
    return "\n".join(lines)


def _write_new(path, value):
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise FileExistsError("immutable_audit_artifact:" + path.name)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def write():
    result = run_audit()
    preserved = [HERE / name for name in ("dynamic_operating_choice_v1.py", "dynamic_operating_policy_v1.json", "dynamic_operating_choice_v1_1.py", "dynamic_operating_policy_v1_1.json")]
    for dirname in ("dynamic_wine_v1_artifacts", "dynamic_wine_v1_1_artifacts"):
        preserved.extend(sorted((HERE / dirname).rglob("*.json")))
    manifest = {"version": PROBE_VERSION, "preserved_sha256": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved},
                "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "result_sha256": digest(result),
                "contract_draft_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in ("persona_v4_contract.py", "persona_profile_v4_draft.schema.json")},
                "LLM_sessions_executed": 0, "human_reviews_completed": 0, "demo_approved": False}
    _write_new(OUT / "results.json", result)
    _write_new(OUT / "HUMAN_REVIEW_COMPARISON.md", render_review(result))
    _write_new(OUT / "preservation_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"manifest_sha256": digest(write()), "model_calls": 0}))
