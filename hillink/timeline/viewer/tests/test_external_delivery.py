"""External delivery as a general dinner alternative (11/02 operator assumption).

- Offered only to staying, checked-in guests; separate from paid in-room dining.
- Not a hotel sale: hotel revenue 0, guest outside spend amount unknown (never 0 KRW, never an invented amount).
- Scored with existing room-meal terms; its unknown price is compared at parity with the cheapest hotel dinner
  available in the same decision, so an unknown price cannot win a price comparison. No reference -> not offered.
- On an exact score tie a hotel option ranks first.
"""
import os, sys, unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import flow_run  # noqa: F401  (path setup)
from operator_choice.autonomy_v1 import agent_day as AD, ledger as LG
from operator_choice.operator_world_v1 import world as WD, engine as EN

ROOM = next(o for o in WD.default_world()["offers"] if o["id"] == "ROOM_MEAL")
def guest(**kw):
    return SimpleNamespace(**dict(dict(stay=True, checked_in=True, checked_out=False, room="GRAND_ROOM", food=[]), **kw))
def priced(i, pp, kind="restaurant", meal=1.0):
    return dict(id=i, label=i, kind=kind, price_pp_krw=pp, available=True, food=dict(meal_fraction=meal))


class ExternalDelivery(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.pop("HILLINK_EXTERNAL_DELIVERY", None)
    def tearDown(self):
        if self._env is None: os.environ.pop("HILLINK_EXTERNAL_DELIVERY", None)
        else: os.environ["HILLINK_EXTERNAL_DELIVERY"] = self._env

    def test_offered_only_to_checked_in_staying_guests(self):
        self.assertIsNotNone(AD.delivery_offer(guest(), ROOM, 1100))
        for g in (guest(stay=False), guest(checked_in=False), guest(checked_out=True)):
            self.assertIsNone(AD.delivery_offer(g, ROOM, 1100))

    def test_separate_from_room_service_and_amount_unknown(self):
        d = AD.delivery_offer(guest(), ROOM, 1100)
        self.assertEqual(d["id"], "EXTERNAL_DELIVERY"); self.assertNotEqual(d["venue"], "ROOM_MEAL")
        self.assertIsNone(d["price_pp_krw"]); self.assertIsNone(d["external_spend"]["amount_krw"])
        self.assertEqual(d["external_spend"]["hotel_revenue_krw"], 0); self.assertEqual(d["food"]["menu_tags"], [])

    def test_parity_with_cheapest_available_hotel_dinner_only(self):
        d = AD.delivery_offer(guest(), ROOM, 1100)
        offers = [priced("PIZZA", 40000), priced("IRD", 43000, "room_meal"), priced("BAKERY", 12000, "simple_meal", .5),
                  dict(priced("CLOSED", 10000), available=False)]
        p = AD.delivery_parity(d, offers)
        self.assertEqual(p["price_pp_krw"], 40000); self.assertEqual(p["price_reference"]["reference_offer"], "PIZZA")
        self.assertEqual(p["price_reference"]["method"], "PARITY_WITH_CHEAPEST_AVAILABLE_HOTEL_DINNER")
        self.assertIsNone(AD.delivery_parity(d, [priced("BAKERY", 12000, "simple_meal", .5)]))   # no reference -> not offered

    def test_policy_off_removes_the_candidate(self):
        os.environ["HILLINK_EXTERNAL_DELIVERY"] = "0"
        self.assertIsNone(AD.delivery_offer(guest(), ROOM, 1100))

    def test_ledger_is_no_hotel_purchase_with_unknown_outside_spend(self):
        c = LG.charge(guest(), "EXTERNAL_DELIVERY", "식사", "GRAND_ROOM", offer=dict(id="EXTERNAL_DELIVERY"))
        self.assertEqual(c["status"], "구매 없음"); self.assertEqual(c["krw"], 0)
        self.assertIsNone(c["external_spend"]["amount_krw"]); self.assertEqual(c["external_spend"]["hotel_revenue_krw"], 0)

    def test_exact_tie_never_favours_delivery(self):
        src = Path(EN.__file__).read_text()
        self.assertIn('c["offer"] == "EXTERNAL_DELIVERY", c["offer"]', src)
        rows = [dict(total=5.0, kind="room_meal", offer="ROOM_MEAL"), dict(total=5.0, kind="room_meal", offer="EXTERNAL_DELIVERY")]
        rows.sort(key=lambda c: (-c["total"], c["kind"] != "rest", c["offer"] == "EXTERNAL_DELIVERY", c["offer"]))
        self.assertEqual(rows[0]["offer"], "ROOM_MEAL")


if __name__ == "__main__":
    unittest.main()
