import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
IDS = ["A01", "A02", "A03", "A04", "A05", "A07", "A08", "A10", "blog41", "blog42", "blog43"]
BUILDINGS = ["GRAND", "VISTA", "DOUGLAS"]
PHASES = ["checkin", "mid", "checkout"]


def post(payload):
    req = urllib.request.Request(
        BASE + "/api/flow",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read()
            return response.status, json.loads(raw), None
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw)
        except Exception:
            body = raw.decode("utf-8", "replace")
        return exc.code, body, None
    except Exception as exc:
        return 0, None, repr(exc)


def summarize(label, pid, event, visit_override, payload):
    status, body, transport_error = post(payload)
    row = {
        "case": label,
        "persona_id": pid,
        "event": event,
        "visit_override": visit_override,
        "http_status": status,
        "transport_error": transport_error,
    }
    if isinstance(body, dict):
        row.update({
            "error": body.get("error"),
            "code": body.get("code"),
            "engine": (body.get("engine") or {}).get("name"),
            "mode": body.get("mode"),
            "inputs_sha": body.get("inputs_sha"),
            "visits": body.get("visits", {}).get(pid),
            "runs": len(body.get("runs") or []),
            "plans": len(body.get("plans") or {}),
            "plan_status": (body.get("plans", {}).get(pid) or {}).get("status"),
            "summary_completed": (body.get("plans", {}).get(pid) or {}).get("summary", {}).get("completed"),
            "plan_backend": (body.get("plans", {}).get(pid) or {}).get("backend"),
            "plan_fallback_reason": (body.get("plans", {}).get(pid) or {}).get("fallback_reason"),
        })
        decisions = [c for run in (body.get("runs") or []) for c in (run.get("customers") or []) if c.get("persona_id") == pid]
        row["decision_count"] = len(decisions)
        row["decisions_with_alternative"] = sum(bool(c.get("runner_up") or c.get("not_chosen")) for c in decisions)
        row["decisions_with_reason"] = sum(bool(c.get("reasons") or c.get("why")) for c in decisions)
        row["decisions_with_evidence_field"] = sum("evidence" in c and "evidence_status" in c for c in decisions)
        row["fact_cited_decisions"] = sum(bool(c.get("direct_review_fact_ids")) for c in decisions)
        ledger = body.get("ledger") or {}
        receipt = (ledger.get("receipts") or {}).get(pid) or {}
        row["paid_krw"] = receipt.get("paid_krw")
        row["engine_scene_paid_krw"] = receipt.get("engine_scene_paid_krw")
        row["room_assumption_krw"] = receipt.get("assumption_addition_krw")
        row["ledger_checks"] = ledger.get("checks") or {}
        row["ledger_total_paid_krw"] = (ledger.get("totals") or {}).get("paid_krw")
        row["level_paid_krw"] = {
            level: sum(int(g.get("paid_krw") or 0) for g in (ledger.get("levels") or {}).get(level, []))
            for level in ("L4", "L3", "L2", "L1")
        }
        row["receipt_total_paid_krw"] = sum(int(r.get("paid_krw") or 0) for r in (ledger.get("receipts") or {}).values())
        row["ledger_status"] = "PASS" if ledger.get("checks", {}).get("receipts_equal_L4_L3_L2_L1") and ledger.get("checks", {}).get("engine_scene_equal_receipt") and ledger.get("checks", {}).get("duplicate_transactions") == 0 else "FAIL"
        row["http_body"] = body if status != 200 else None
    else:
        row["http_body"] = body
    row["request"] = payload
    return row


rows = []
party = {}
for pid in IDS:
    # The matrix's "customer-defined" row uses the runtime's own visit profile.
    for event in (False, True):
        payload = {"personas": [pid], "mode": "one", "event": event, "seed": 0, "include_ledger": True}
        rows.append(summarize("customer_defined", pid, event, None, payload))
        if event is False:
            visit = rows[-1].get("visits") or {}
            party[pid] = visit.get("party_size")
    if not party.get(pid):
        continue
    for building in BUILDINGS:
        for phase in PHASES:
            override = {"stay": True, "building": building, "phase": phase, "party_size": party[pid]}
            for event in (False, True):
                payload = {"personas": [pid], "mode": "one", "event": event, "seed": 0, "visit_override": {pid: override}, "include_ledger": True}
                rows.append(summarize(f"{building}_{phase}", pid, event, override, payload))
    override = {"stay": False, "building": None, "phase": "visit", "party_size": party[pid]}
    for event in (False, True):
        payload = {"personas": [pid], "mode": "one", "event": event, "seed": 0, "visit_override": {pid: override}, "include_ledger": True}
        rows.append(summarize("nonstay_visit", pid, event, override, payload))

fails = []
for row in rows:
    reasons = []
    if row["http_status"] != 200:
        reasons.append("HTTP_NOT_200")
    if row.get("engine") != "autonomy_v1":
        reasons.append("ENGINE_NOT_AUTONOMY_V1")
    if row.get("plans", 0) != 1 or row.get("runs", 0) < 1:
        reasons.append("MISSING_PLAN_OR_RUN")
    if row.get("plan_status") != "ok":
        reasons.append("PLAN_NOT_OK")
    if row.get("summary_completed") is not True:
        reasons.append("DAY_NOT_COMPLETED")
    if row.get("plan_backend") != "autonomy_v1" or row.get("plan_fallback_reason") is not None:
        reasons.append("ENGINE_BACKEND_OR_FALLBACK_MISMATCH")
    if row.get("decision_count", 0) < 1 or row.get("decisions_with_alternative") != row.get("decision_count"):
        reasons.append("DECISION_OR_ALTERNATIVE_MISSING")
    if row.get("decisions_with_reason") != row.get("decision_count") or row.get("decisions_with_evidence_field") != row.get("decision_count"):
        reasons.append("REASON_OR_EVIDENCE_STRUCTURE_MISSING")
    if row.get("paid_krw") != row.get("engine_scene_paid_krw"):
        reasons.append("RECEIPT_SCENE_BALANCE_MISMATCH")
    if row.get("ledger_status") != "PASS":
        reasons.append("LEDGER_NOT_OK")
    if row.get("ledger_total_paid_krw") != row.get("receipt_total_paid_krw"):
        reasons.append("RECEIPT_TOTAL_MISMATCH")
    if any(amount != row.get("ledger_total_paid_krw") for amount in (row.get("level_paid_krw") or {}).values()):
        reasons.append("HIERARCHY_TOTAL_MISMATCH")
    row["validation"] = "PASS" if not reasons else "FAIL"
    row["failure_reasons"] = reasons
    if reasons:
        fails.append(row)

result = {
    "base_url": BASE,
    "ids": IDS,
    "expected_runs": 242,
    "actual_runs": len(rows),
    "http_200": sum(r["http_status"] == 200 for r in rows),
    "autonomy_v1": sum(r.get("engine") == "autonomy_v1" for r in rows),
    "fully_valid": sum(r["validation"] == "PASS" for r in rows),
    "ledger_checks_pass": sum(r.get("ledger_status") == "PASS" for r in rows),
    "decisions_with_reason": sum(r.get("decisions_with_reason", 0) for r in rows),
    "decisions_with_alternative": sum(r.get("decisions_with_alternative", 0) for r in rows),
    "fact_cited_decisions": sum(r.get("fact_cited_decisions", 0) for r in rows),
    "failures": fails,
    "rows": rows,
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
