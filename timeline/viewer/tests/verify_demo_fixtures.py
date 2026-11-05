import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

root = Path(sys.argv[1])
base = sys.argv[2].rstrip("/")
out = Path(sys.argv[3])
fixture = json.loads((root / "timeline/viewer/static/demo_story/flow_fixture_v1.json").read_text(encoding="utf-8"))
rows = []
for key, expected in fixture["entries"].items():
    request = json.loads(key)
    request["include_ledger"] = True
    req = urllib.request.Request(base + "/api/flow", data=json.dumps(request).encode(), headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            status = response.status
            actual = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        status = exc.code
        try: actual = json.loads(exc.read())
        except Exception: actual = {}
    ledger = actual.pop("ledger", {}) if isinstance(actual, dict) else {}
    checks = ledger.get("checks") or {}
    totals = ledger.get("totals") or {}
    receipt_paid = sum(int(x.get("paid_krw") or 0) for x in (ledger.get("receipts") or {}).values())
    level_paid = {k: sum(int(x.get("paid_krw") or 0) for x in ledger.get("levels", {}).get(k, [])) for k in ("L4","L3","L2","L1")}
    run = {
        "request_persona_count": len(request.get("personas") or []),
        "personas": request.get("personas"),
        "event": request.get("event", False),
        "http_status": status,
        "same_as_saved_api": actual == expected,
        "engine": (actual.get("engine") or {}).get("name") if isinstance(actual, dict) else None,
        "run_id": ledger.get("run_id"),
        "paid_krw": totals.get("paid_krw"),
        "receipt_paid_krw": receipt_paid,
        "level_paid_krw": level_paid,
        "ledger_reconciled": bool(checks.get("receipts_equal_L4_L3_L2_L1") and checks.get("engine_scene_equal_receipt") and checks.get("duplicate_transactions") == 0 and receipt_paid == totals.get("paid_krw") and all(v == totals.get("paid_krw") for v in level_paid.values())),
    }
    rows.append(run)
failures = [r for r in rows if r["http_status"] != 200 or not r["same_as_saved_api"] or r["engine"] != "autonomy_v1" or not r["ledger_reconciled"]]
result = {"fixture_entries": len(fixture["entries"]), "actual_runs": len(rows), "http_200": sum(x["http_status"] == 200 for x in rows), "response_equal": sum(x["same_as_saved_api"] for x in rows), "ledger_reconciled": sum(x["ledger_reconciled"] for x in rows), "failures": failures, "rows": rows}
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
