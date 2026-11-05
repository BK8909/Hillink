"""Operator booking assumption for the 2025 Santa card: validation only (fast)."""
import sys, unittest
from pathlib import Path
VIEWER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VIEWER))
import visit_run  # noqa: F401  (path setup)
from operator_choice.autonomy_v1 import event_scenarios as E

SESSIONS = [["10:00", "11:30"], ["12:00", "13:30"], ["14:00", "15:30"], ["16:00", "17:30"]]
BASE = {"sessions": SESSIONS, "duration_min": 60, "historical_model_prices_acknowledged": True}


def santa(booked):
    return {"event_card_id": "SANTA_KIDS_VILLAGE_2025", "assumptions": dict(BASE, booked_sessions=booked)}


class SantaBookedSessions(unittest.TestCase):
    def test_declared_session_is_accepted_and_kept_in_snapshot(self):
        s = E.snapshot(santa({"A06": {"date": "2025-12-19", "start": "14:00"}}), "2025-12-19", "stay_1")
        self.assertEqual(s["assumptions"]["booked_sessions"]["A06"]["start"], "14:00")

    def test_booking_changes_scenario_identity(self):
        a = E.snapshot({"event_card_id": "SANTA_KIDS_VILLAGE_2025", "assumptions": BASE}, "2025-12-19", "stay_1")
        b = E.snapshot(santa({"A06": {"date": "2025-12-19", "start": "14:00"}}), "2025-12-19", "stay_1")
        self.assertNotEqual(a["scenario_id"], b["scenario_id"])

    def test_undeclared_start_rejected(self):
        with self.assertRaisesRegex(ValueError, "BOOKED_SESSION_START_NOT_DECLARED"):
            E.snapshot(santa({"A06": {"date": "2025-12-19", "start": "15:00"}}), "2025-12-19", "stay_1")

    def test_extra_fields_rejected(self):
        with self.assertRaisesRegex(ValueError, "BOOKED_SESSION_FIELDS_INVALID"):
            E.snapshot(santa({"A06": {"date": "2025-12-19", "start": "14:00", "selected": True}}), "2025-12-19", "stay_1")

    def test_other_event_cards_cannot_book(self):
        cfg = {"event_card_id": "PIZZA_HILL_GOLDEN_NIGHT_2026", "assumptions": {"sessions": [["17:00", "21:00"]], "duration_min": 60,
               "booked_sessions": {"A06": {"date": "2026-09-10", "start": "17:00"}}}}
        with self.assertRaisesRegex(ValueError, "BOOKED_SESSIONS_SANTA_ONLY"):
            E.snapshot(cfg, "2026-09-10", "stay_1")


if __name__ == "__main__":
    unittest.main()
