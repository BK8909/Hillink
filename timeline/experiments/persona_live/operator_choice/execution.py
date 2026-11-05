"""Approval-bound execution interface; no default provider or credentials are selected.

A future provider adapter must make ONE isolated request per call, with no hidden
retry and an exact model ID. Existing ask.call retries and aliases do not satisfy
that contract. Preparation and evaluation do not import ask or execute subprocesses.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import math
import random
from typing import Protocol

from .evaluate import DECISION_SCHEMA, evaluate
from .experiment import write_new
from .rules import digest


class Provider(Protocol):
    name: str
    model_id: str
    max_attempts: int
    parameters: dict

    def __call__(self, *, system: str, prompt: str, schema: dict) -> dict:
        """Return output, cost_usd, resolved_model, provider. Never retry silently."""


def execute(plan: dict, approval: dict, provider: Provider, destination: Path) -> list[dict]:
    """Callable from an approved backend adapter. Not exposed as an executable CLI."""
    if approval.get("status") != "approved" or not approval.get("approved_by"):
        raise PermissionError("explicit_model_execution_approval_required")
    if approval.get("plan_sha256") != digest(plan):
        raise PermissionError("approval_does_not_match_plan")
    if not approval.get("model_id") or approval["model_id"] in {"sonnet", "default", "latest"}:
        raise PermissionError("exact_model_id_required")
    if (provider.name, provider.model_id, provider.max_attempts) != (approval.get("provider"), approval["model_id"], 1):
        raise PermissionError("provider_or_model_contract_mismatch")
    parameters = deepcopy(getattr(provider, "parameters", None))
    if not parameters or parameters != approval.get("parameters"):
        raise PermissionError("provider_parameters_must_be_registered")
    max_calls = approval.get("max_calls", 0)
    budget, reserve = approval.get("budget_usd", 0), approval.get("reserve_per_call_usd", 0)
    if not (0 < max_calls <= plan["unique_calls"] and 0 < reserve <= budget <= plan["approval"]["budget_usd"]):
        raise PermissionError("invalid_call_or_budget_limit")
    if destination.exists():
        raise FileExistsError("use_a_new_run_directory; results_are_immutable")
    cells = {}
    for cell in plan["cells"]:
        if digest({"system": cell["system"], "prompt": cell["prompt"]}) != cell["prompt_sha256"]:
            raise ValueError("prompt_hash_mismatch")
        cells.setdefault(cell["execution_id"], cell)
    order = list(cells)
    random.Random(approval.get("schedule_seed", 20261021)).shuffle(order)
    write_new(destination / "preregistration.json", {"plan_sha256": digest(plan), "approval": approval, "execution_order": order,
                                                   "schedule_seed_is_not_model_seed": True})
    records, spent = [], 0.0
    for execution_id in order[:max_calls]:
        if spent + reserve > budget:
            break
        if provider.parameters != parameters:
            raise ValueError("provider_parameters_changed_during_experiment")
        cell = cells[execution_id]
        try:
            result = provider(system=cell["system"], prompt=cell["prompt"], schema=deepcopy(DECISION_SCHEMA))
            record = {"execution_id": execution_id, "agent_id": cell["agent_id"], "prompt_sha256": cell["prompt_sha256"],
                      "provider": result.get("provider"), "resolved_model": result.get("resolved_model"),
                      "parameters": parameters,
                      "output": result.get("output"), "cost_usd": result.get("cost_usd"), "human_review_status": "pending"}
            cost = record["cost_usd"]
            error = None
            if record["resolved_model"] != provider.model_id or record["provider"] != provider.name:
                error = "resolved_model_or_provider_mismatch"
            elif not isinstance(cost, (int, float)) or isinstance(cost, bool) or not math.isfinite(cost) or cost < 0:
                error = "billing_unknown_stop"
            elif cost > reserve:
                error = "per_call_reserve_exceeded_stop"
            record["evaluation"] = evaluate(record["output"], cell)
            if record["evaluation"]["errors"]:
                error = error or "invalid_response_stop"
            record["stop_reason"] = error
            write_new(destination / f"{execution_id}.json", record)
            records.append(record)
            if error:
                break
            spent += cost
        except Exception as exc:
            # Billing on a failed call is unknown: stop at the first error.
            # Do not persist error text, which may contain credentials/provider payloads.
            write_new(destination / f"{execution_id}_failure.json", {"error_type": type(exc).__name__, "stop_reason": "failure_billing_unknown"})
            break
    return records
