import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "timeline/viewer"))
import ledger_service
import visit_run

FIXTURE = ROOT / "research/cl39/fixtures/visit_smoke_v1.json"


@unittest.skipUnless(FIXTURE.exists(), "new post-CL40 smoke baseline has not been generated")
class VisitSmokeBaselineV1(unittest.TestCase):
    def test_six_frozen_current_engine_cases(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["fixture_status"], "NEW_POST_CL40_CURRENT_ENGINE_BASELINE_NOT_HISTORICAL_GOLD")
        for case in fixture["cases"]:
            with self.subTest(request=case["request"]):
                request = dict(case["request"], behavior_engine="legacy")
                flow = visit_run.run_visit(request)
                if flow.get("error"):
                    if flow.get("code") == "E_FLOW_INPUT_MISSING":
                        self.skipTest("approved local run inputs are not connected")
                    self.fail(f"visit run error {flow.get('code')}: {flow.get('error')}")
                ledger = ledger_service.register_visit(flow, request)
                expected = case["expected"]
                # This frozen CL40 fixture belongs to the legacy selector.
                # Pin the engine, not new expected amounts; M4 has separate
                # accepted-research fixtures and live invariants.
                self.assertEqual(flow["engine"]["version"], visit_run.LEGACY_VISIT_ENGINE_VERSION)
                self.assertEqual(len(flow["visit_days"]), expected["day_count"])
                self.assertEqual(flow["visit"]["nights"], expected["nights"])
                self.assertEqual([d["phase"] for d in flow["visit_days"]], expected["phases"])
                self.assertEqual(ledger["visit"]["event_dates"], expected["event_dates"])
                self.assertEqual(ledger["totals"]["paid_krw"], expected["paid_krw"])
                self.assertEqual(ledger["visit"]["room_assumption_krw"], expected["room_assumption_krw"])
                self.assertEqual(ledger["totals"]["unknown_count"], expected["unknown_count"])
                self.assertEqual(ledger["checks"]["receipts_equal_L4_L3_L2_L1"], True)
                self.assertEqual(ledger["checks"]["duplicate_simulation_rows"], 0)
                self.assertEqual(
                    {level: sum(g.get("paid_krw", 0) for g in ledger["levels"][level])
                     for level in ("L4", "L3", "L2", "L1")},
                    expected["L4_L3_L2_L1_paid_totals"],
                )
                self.assertEqual(len(ledger["visit"]["days"]), expected["day_count"])
                self.assertEqual(
                    [dict(day_index=d["day_index"], phase=d["phase"], event_available=d["event_available"],
                          paid_krw=d["paid_krw"], room_assumption_krw=d["assumption_addition_krw"],
                          unknown_count=d["unknown_count"]) for d in ledger["visit"]["days"]],
                    expected["day_rows"],
                )


if __name__ == "__main__":
    unittest.main()
