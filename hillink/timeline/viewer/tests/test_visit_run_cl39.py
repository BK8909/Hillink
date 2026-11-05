# CL39 selection regressions explicitly retain the legacy engine. Live M4 is
# tested separately without rewriting the frozen behavior expectations.
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import visit_run
import ledger_service
import flow_run
import copy
import package_entitlements

AD = flow_run.AD
HAS_A01 = "A01" in AD.load_inputs()[0]
DELIVERY_SUFFIX = "+external-delivery-v1" if AD.delivery_enabled() else ""   # meal-alternative policy is part of run identity


@unittest.skipUnless(HAS_A01, "A01 private approved execution input is not connected")
class VisitRunCL39(unittest.TestCase):
    def run_pair(self, duration, event_mode="none"):
        request = {"personas": ["A01"], "duration": duration, "event_mode": event_mode,
                   "seed": 17, "start_date": visit_run.FIXED_START_DATE, "behavior_engine": "legacy"}
        flow = visit_run.run_visit(request)
        self.assertNotIn("error", flow)
        self.assertEqual(flow["engine"]["version"], visit_run.LEGACY_VISIT_ENGINE_VERSION + DELIVERY_SUFFIX)
        self.assertNotEqual(flow["engine"]["version"], AD.VERSION)
        self.assertEqual(flow["visit_days"][0]["flow"]["engine"]["version"], AD.VERSION)
        self.assertEqual(flow["visit_days"][0]["flow"]["world_context"]["date"], flow["visit_days"][0]["date"])
        self.assertEqual(flow["visit_days"][0]["flow"]["world_context"]["event_available"], flow["visit_days"][0]["event"])
        ledger = ledger_service.register_visit(flow, request)
        return request, flow, ledger

    def test_phase_schedules_and_room_nights(self):
        expected = {"day_visit": ["visit"], "stay_1": ["checkin", "checkout"],
                    "stay_2": ["checkin", "mid", "checkout"],
                    "stay_3": ["checkin", "mid", "mid", "checkout"]}
        nights = {"day_visit": 0, "stay_1": 1, "stay_2": 2, "stay_3": 3}
        for duration, phases in expected.items():
            _, flow, ledger = self.run_pair(duration)
            self.assertEqual([d["phase"] for d in flow["visit_days"]], phases)
            self.assertEqual(len(flow["visit_days"]), nights[duration] + 1)
            self.assertEqual(sum(r["act"] == "room_night" for r in ledger["receipts"]["A01"]["rows"]), nights[duration])
            self.assertTrue(ledger["checks"]["receipts_equal_L4_L3_L2_L1"])
            self.assertTrue(ledger["checks"]["day_totals_equal_visit_total"])
            self.assertEqual(sum(d["paid_krw"] for d in ledger["visit"]["days"]), ledger["totals"]["paid_krw"])

    def test_prior_day_state_is_carried_into_later_day(self):
        _, flow, _ = self.run_pair("stay_2", "wine")
        first = flow["visit_days"][0]["flow"]["plans"]["A01"]
        second = flow["visit_days"][1]["flow"]["plans"]["A01"]
        state = second.get("visit_state_used") or {}
        self.assertEqual(state.get("day_index"), 1)
        self.assertTrue(state.get("prior_action_codes"))
        self.assertTrue(state.get("prior_meals"))
        self.assertIn("fatigue_after_sleep", state)
        self.assertTrue(flow["visit_days"][1]["flow"]["plans"]["A01"].get("visit_state_after"))
        P, bars, lib = AD.load_inputs()
        carried = set(state.get("prior_action_codes") or [])
        previous_action = next((s["act"] for s in first["scenes"] if s.get("act") in AD.SP.ACT and s.get("act") in carried), None)
        self.assertIsNotNone(previous_action)
        agent = AD.Agent("A01", P, bars, lib, AD.scenario("visit_state_test", event=False, observe="weekend", seed=17,
                                                          visit_state={"A01": state}))
        context = agent.ctx()
        with_history = AD.SP.act_weight(previous_action, agent.P, agent.C, context)
        without_history = copy.deepcopy(context)
        without_history["done"].discard(previous_action)
        without_history_score = AD.SP.act_weight(previous_action, agent.P, agent.C, without_history)
        self.assertAlmostEqual(without_history_score - with_history, 1.2, places=6)

    def test_prior_event_attendance_softly_adjusts_only_same_event_candidate(self):
        base = lambda o, *_: []
        history = {"event_history": [{"date": "2026-10-24", "available": True, "participated": True}]}
        adjusted = AD.score_with_visit_event_history(base, history)
        term = adjusted({"id": "WINE_FAIR"}, 0, {}, {}, {}, {})
        self.assertEqual(len(term), 1)
        self.assertEqual(term[0]["factor"], "방문 내 행사 재참여 조정(설계 가정)")
        self.assertEqual(term[0]["value"], -1.2)
        self.assertIn("재참여를 금지하지 않음", term[0]["note"])
        self.assertEqual(adjusted({"id": "PIZZA_HILL"}, 0, {}, {}, {}, {}), [])
        self.assertEqual(AD.score_with_visit_event_history(base, {"event_history": [{"participated": False}]})({"id": "WINE_FAIR"}, 0, {}, {}, {}, {}), [])

    def test_repeat_event_adjustment_is_traced_and_does_not_block_revisit(self):
        request = {"personas": ["A07"], "duration": "stay_3", "event_mode": "wine",
                   "seed": 17, "start_date": visit_run.FIXED_START_DATE}
        flow = visit_run.run_visit(request)
        self.assertNotIn("error", flow)
        first, second = flow["visit_days"][:2]
        def event_choice(day):
            for run in day["flow"].get("runs", []):
                if run.get("turn") != "event":
                    continue
                for customer in run.get("customers", []):
                    if customer.get("persona_id") == "A07":
                        return customer.get("choice") or {}
            return None
        self.assertEqual((event_choice(first) or {}).get("venue_id"), "FOREST")
        self.assertEqual((event_choice(second) or {}).get("venue_id"), "FOREST")
        state = second["flow"]["plans"]["A07"].get("visit_state_used") or {}
        self.assertEqual(state["repeat_event_adjustment"]["status"], "DESIGN_ASSUMPTION")
        self.assertEqual(state["repeat_event_adjustment"]["score_delta"], -1.2)
        event_customer = next(c for run in second["flow"].get("runs", []) if run.get("turn") == "event"
                              for c in run.get("customers", []) if c.get("persona_id") == "A07")
        encoded = __import__("json").dumps(event_customer, ensure_ascii=False)
        self.assertIn("방문 내 행사 재참여 조정(설계 가정)", encoded)
        self.assertIn("재참여를 금지하지 않음", encoded)
        third = flow["visit_days"][2]
        self.assertFalse(third["event"])
        self.assertIsNone(third["flow"]["plans"]["A07"]["visit_state_used"]["repeat_event_adjustment"])
        self.assertEqual(flow["engine"]["version"], visit_run.VISIT_ENGINE_VERSION + DELIVERY_SUFFIX)

    def test_deterministic_and_unique_visit_rows(self):
        req, flow, ledger = self.run_pair("stay_1")
        again = visit_run.run_visit(req)
        again_ledger = ledger_service.register_visit(again, req)
        self.assertEqual(flow["visit_id"], again["visit_id"])
        self.assertEqual(ledger["totals"], again_ledger["totals"])
        rows = ledger["receipts"]["A01"]["rows"]
        self.assertEqual(len({r["row_id"] for r in rows}), len(rows))
        self.assertEqual(len({r["visit_date"] for r in rows if r["act"] != "room_night"}) <= len(flow["visit_days"],), True)

    def test_event_pair_changes_only_event_availability(self):
        off_req, off, off_ledger = self.run_pair("stay_2", "none")
        on_req, on, on_ledger = self.run_pair("stay_2", "wine")
        self.assertEqual([(d["date"], d["phase"]) for d in off["visit_days"]],
                         [(d["date"], d["phase"]) for d in on["visit_days"]])
        self.assertEqual([d["event"] for d in off["visit_days"]], [False, False, False])
        self.assertEqual([d["event"] for d in on["visit_days"]], [True, True, False])
        self.assertEqual(off_ledger["context"]["profile_sha"], on_ledger["context"]["profile_sha"])
        self.assertEqual(off_ledger["context"]["seed"], on_ledger["context"]["seed"])
        compared = ledger_service.compare(off_ledger["run_id"], on_ledger["run_id"], event_only=True)
        self.assertTrue(compared["comparable"])
        self.assertEqual(compared["delta_krw"], on_ledger["totals"]["paid_krw"]-off_ledger["totals"]["paid_krw"])

    def test_unsupported_dates_and_events_are_rejected(self):
        self.assertIn("error", visit_run.run_visit({"personas":["A01"], "duration":"stay_1", "start_date":"2027-01-01"}))
        self.assertIn("error", visit_run.run_visit({"personas":["A01"], "duration":"stay_1", "event_mode":"summer_pool"}))


@unittest.skipUnless("A03" in AD.load_inputs()[0], "A03 private approved execution input is not connected")
class PackageEntitlementTests(unittest.TestCase):
    PACKAGE_ID = "GRAND_SUNGSU_V2_2N"

    def run_package(self):
        request = {"personas": ["A03"], "duration": "stay_2", "event_mode": "none",
                   "seed": 0, "start_date": visit_run.FIXED_START_DATE, "package_id": self.PACKAGE_ID, "behavior_engine": "legacy"}
        flow = visit_run.run_visit(request)
        self.assertNotIn("error", flow)
        return request, flow, ledger_service.register_visit(flow, request)

    def test_entitlement_is_consumed_once_in_multi_day_engine_and_ledger(self):
        request, flow, ledger = self.run_package()
        self.assertEqual(flow["visit"]["package_context"]["id"], self.PACKAGE_ID)
        self.assertTrue(flow["visit"]["package_context"]["scenario_only"])
        scenes = [(day["day_index"], scene) for day in flow["visit_days"]
                  for scene in day["flow"]["plans"]["A03"]["scenes"] if (scene.get("act") or "").lower() == "sauna"]
        included = [(day_idx, scene) for day_idx, scene in scenes
                    if scene["basis"]["charge"].get("status") == "포함" and scene["basis"]["charge"].get("entitlement_id")]
        self.assertEqual(len(included), 1, [(n, s["basis"]["charge"]) for n, s in scenes])
        self.assertEqual(len(scenes), 2, [(n, s["basis"]["charge"]) for n, s in scenes])
        self.assertEqual(scenes[1][1]["basis"]["charge"]["status"], "유료")
        self.assertEqual(scenes[1][1]["basis"]["charge"]["krw"],132000)
        self.assertEqual(included[0][1]["basis"]["charge"]["status"], "포함")
        self.assertEqual(included[0][1]["basis"]["charge"]["krw"], 0)
        usage = flow["visits"]["A03"]["benefit_usage"]["package_entitlements"]["GRAND_SUNGSU_SAUNA"]
        self.assertEqual((usage["scope"], usage["limit"], usage["used_count"], usage["remaining"]), ("per_visit", 1, 1, 0))
        sauna_rows = [r for r in ledger["receipts"]["A03"]["rows"] if r["action_id"].lower() == "sauna"]
        self.assertEqual(sum(r["status"] == "포함" for r in sauna_rows), 1)
        self.assertEqual(sum(r["paid_krw"] for r in sauna_rows),132000)
        self.assertTrue(ledger["checks"]["receipts_equal_L4_L3_L2_L1"])
        self.assertTrue(ledger["checks"]["day_totals_equal_visit_total"])
        package_rows = [r for r in ledger["receipts"]["A03"]["rows"] if r["action_id"] == "room_night"]
        self.assertEqual(len(package_rows), 2)
        self.assertTrue(all(r["paid_krw"] == 0 and r["assumption_addition_krw"] == 0 for r in package_rows))

    def test_invalid_package_duration_and_id_are_rejected(self):
        base = {"personas": ["A03"], "event_mode": "none", "seed": 17, "start_date": visit_run.FIXED_START_DATE,
                "package_id": self.PACKAGE_ID}
        self.assertIn("error", visit_run.run_visit(dict(base, duration="stay_1")))
        self.assertIn("error", visit_run.run_visit(dict(base, duration="stay_2", package_id="UNKNOWN")))

    def test_unused_entitlement_remains_available(self):
        package = package_entitlements.get_package(self.PACKAGE_ID)
        usage = package_entitlements.initial_benefit_usage(package)
        state = {"prior_action_codes": [], "visited_facilities": [], "prior_meals": [], "checked_events": [],
                 "event_history": [], "benefit_usage": {"package_entitlements": usage}}
        visit_run._advance_state(state, {"plans": {"A03": {"scenes": []}}, "runs": []}, "A03",
                                 {"day_index": 1, "date": "2026-10-24", "phase": "checkout"})
        sauna = state["benefit_usage"]["package_entitlements"]["GRAND_SUNGSU_SAUNA"]
        self.assertEqual((sauna["remaining"], sauna["used_count"], sauna["status"]), (1, 0, "AVAILABLE"))


if __name__ == "__main__":
    unittest.main()
