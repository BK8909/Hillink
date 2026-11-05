import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import persona_blog05 as p5
import persona_blog11 as p11
from observed_payments import build_report, build_monthly_report


class ObservedPaymentsTests(unittest.TestCase):
    def test_extra_adult_is_charged_once_not_three_times(self):
        report = build_report(p5)
        self.assertEqual(report["known_subtotal_krw"], 189600)
        self.assertEqual([row["krw"] for row in report["rows"]], [124000, 65600])
        self.assertTrue(all(row["included_persons"] == 2 and row["charged_persons"] == 1
                            for row in report["rows"]))
        self.assertTrue(report["listed_payments_all_priced"])
        self.assertFalse(report["complete_stay_total"])
        self.assertEqual(report["known_unallocated_count"], 1)

    def test_unpriced_room_service_is_not_free_or_a_different_menu(self):
        report = build_report(p11)
        self.assertIsNone(report["known_subtotal_krw"])
        self.assertIsNone(report["known_subtotal_net"])
        self.assertIsNone(report["rows"][0]["qty"])
        self.assertEqual(report["unknown_payment_count"], 1)
        self.assertFalse(report["listed_payments_all_priced"])
        self.assertIn("스테이크", report["rows"][0]["product"])
        self.assertEqual(len(p11.TRUTH_MEALS), 1)

    def test_duplicate_id_rejected_and_inputs_not_mutated(self):
        before = copy.deepcopy(p5.OBSERVED_PAYMENTS)
        build_report(p5)
        self.assertEqual(p5.OBSERVED_PAYMENTS, before)
        with self.assertRaises(ValueError):
            build_report(SimpleNamespace(SOURCE_ID="test", __name__="test",
                                         OBSERVED_PAYMENTS=[before[0], before[0]]))

    def test_observed_outcome_is_not_prediction_input(self):
        from revenue import spend_lines
        before = spend_lines(p5, menu=None)
        with patch.object(p5, "OBSERVED_PAYMENTS", ()):
            after = spend_lines(p5, menu=None)
        self.assertEqual(before, after)

    def test_no_observations_is_unknown_not_zero(self):
        report = build_report(SimpleNamespace(__name__="no_data"))
        self.assertIsNone(report["known_subtotal_krw"])
        self.assertFalse(report["listed_payments_all_priced"])

    def test_months_are_actual_dates_not_simulation_dates(self):
        report = build_monthly_report([p5, p11])
        self.assertEqual(report["available_months"], ["2021-11", "2025-03"])
        self.assertEqual(report["summary"]["known_subtotal_krw"], 189600)
        self.assertEqual(report["summary"]["unknown_count"], 1)
        self.assertEqual(sum(m["known_subtotal_krw"] or 0 for m in report["months"]), 189600)
        self.assertFalse(report["simulation_merged"])
        october = build_monthly_report([p5, p11], "2026-10")
        self.assertTrue(october["no_records"])
        self.assertIsNone(october["summary"]["known_subtotal_krw"])

    def test_unknown_month_keeps_unpriced_ird_in_outlet_totals(self):
        report = build_monthly_report([p5, p11], "2021-11")
        self.assertFalse(report["no_records"])
        self.assertEqual(report["summary"]["unknown_count"], 1)
        self.assertIsNone(report["summary"]["known_subtotal_krw"])
        outlet = report["months"][0]["outlets"][0]
        self.assertEqual(outlet["l3"], "IRD")
        self.assertIsNone(outlet["known_subtotal_krw"])
        self.assertFalse(outlet["all_priced"])

    def test_partial_known_month_and_unallocated_amount_are_not_lost(self):
        report = build_monthly_report([p5, p11], "2025-03")
        month = report["months"][0]
        self.assertEqual(month["known_subtotal_krw"], 189600)
        self.assertEqual(month["unallocated_count"], 1)
        self.assertEqual(sum(o["known_subtotal_krw"] for o in month["outlets"]), 189600)

    def test_bad_month_and_cross_source_duplicate_are_rejected(self):
        for month in ["2026-13", "2026-1", "2026-10-01"]:
            with self.assertRaises(ValueError):
                build_monthly_report([p5], month)
        with self.assertRaises(ValueError):
            build_monthly_report([p5, p5])


if __name__ == "__main__":
    unittest.main()
