import sys
import copy
import unittest
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1]
TL = VIEWER.parent
sys.path.insert(0, str(VIEWER))
sys.path.insert(0, str(TL / "experiments" / "persona_live"))

from operator_choice.autonomy_v1 import agent_day as AD


class CL50ProductStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = AD.load_inputs()
        cls.pid = "A01" if "A01" in cls.inputs[0] else next(iter(cls.inputs[0]))

    def agent(self, context=None):
        profiles, bars, library = copy.deepcopy(self.inputs)
        if context is not None:
            profiles[self.pid]["verified_source_context"] = context
        sc = AD.scenario("cl50-product-test", event=False, seed=17)
        return AD.Agent(self.pid, profiles, bars, library, sc)

    def test_future_closure_does_not_filter_earlier_candidate_but_overlap_does(self):
        pid = "A02" if "A02" in self.inputs[0] else self.pid
        def world(interval):
            return AD.World(AD.scenario("cl50-closure-target", event=False, seed=17,
                                        closed={"WELLNESS_SAUNA": interval}))
        future, overlapping = world(("20:00", "21:00")), world(("16:30", "18:30"))
        a = AD.Agent(pid, *self.inputs, future.sc)
        offer = next(o for o in future.engine_world(16 * 60)["offers"] if o["id"] == "SAUNA")
        # Old gate: presence of an interval excluded SAUNA regardless of clock.
        self.assertTrue(bool(future.closed_at(16 * 60).get("WELLNESS_SAUNA")))
        self.assertFalse(AD._engine_closure_interval(a, future, 16 * 60, offer))
        self.assertIn("SAUNA", [o["id"] for o in AD.engine_world_for(a, future, 16 * 60)["offers"]])
        self.assertNotIn("SAUNA", [o["id"] for o in AD.engine_world_for(a, overlapping, 16 * 60)["offers"]])
        self.assertTrue(AD._engine_closure_interval(a, overlapping, 16 * 60, offer))

    def test_unreviewed_room_facts_do_not_grant_access_or_bonus(self):
        a = self.agent({"spa_room": {"value": True, "fact_ids": ["F1"], "mapping_review": "PENDING"},
                        "private_waterplay_context": {"value": True, "fact_ids": ["F2"], "mapping_review": "APPROVED"}})
        ctx = a.ctx()
        self.assertFalse(ctx["spa_room"])
        self.assertEqual(ctx["spa_room_bonus"], 0.3)

    def test_approved_scoped_coefficients_apply_only_to_matching_context_once(self):
        approved = {key: {"value": True, "fact_ids": [key + "-fact"], "mapping_review": "APPROVED"}
                    for key in ("spa_room", "private_waterplay_context", "hotel_fitness_habit")}
        a = self.agent(approved)
        ctx = a.ctx()
        self.assertEqual(ctx["fitness_active"], 2.75)
        self.assertEqual(ctx["spa_room_bonus"], 2.0)
        baseline = self.agent()
        native_fitness = AD.SP.act_weight("fitness", a.P, a.C, baseline.ctx())
        scoped_fitness = AD.SP.act_weight("fitness", a.P, a.C, ctx)
        self.assertAlmostEqual(scoped_fitness - native_fitness, 1.75 * a.P["facets"]["active"])
        spa_only = self.agent({"spa_room": approved["spa_room"],
                               "private_waterplay_context": approved["private_waterplay_context"]})
        spa_native_bonus = dict(spa_only.ctx(), spa_room_bonus=0.3)
        native_bath = AD.SP.act_weight("room_bath", spa_only.P, spa_only.C, spa_native_bonus)
        scoped_bath = AD.SP.act_weight("room_bath", spa_only.P, spa_only.C, spa_only.ctx())
        self.assertAlmostEqual(scoped_bath - native_bath, 1.7)
        a.done.append("room_bath")
        self.assertEqual(a.ctx()["spa_room_bonus"], 0.3)
        repeated_bath = AD.SP.act_weight("room_bath", a.P, a.C, a.ctx())
        native_repeated_ctx = dict(spa_only.ctx(), spa_room_bonus=0.3)
        native_repeated_ctx["done"].add("room_bath")
        native_repeated_bath = AD.SP.act_weight("room_bath", a.P, a.C, native_repeated_ctx)
        self.assertAlmostEqual(repeated_bath - native_repeated_bath, 0.0)
        bath_agent = self.agent({"spa_room": approved["spa_room"],
                                 "private_waterplay_context": approved["private_waterplay_context"]})
        bath_loc = AD.SP.ACT["room_bath"][1](bath_agent.B)
        AD.plan_do(bath_agent, "room_bath", bath_loc, AD.hm("16:00"), {}, [])
        first_trace = bath_agent.log[-1]["internal"]["coefficient_adjustments"]
        self.assertEqual(first_trace[0]["parameter"], "spa_room_bonus")
        self.assertEqual(first_trace[0]["fact_ids"], ["spa_room-fact", "private_waterplay_context-fact"])
        AD.plan_do(bath_agent, "room_bath", bath_loc, AD.hm("18:00"), {}, [])
        self.assertEqual(bath_agent.log[-1]["internal"]["coefficient_adjustments"], [])
        unsupported = self.agent({"hotel_fitness_habit": {"value": True, "fact_ids": [], "mapping_review": "APPROVED"}})
        self.assertEqual(unsupported.ctx()["fitness_active"], 1.0)


if __name__ == "__main__":
    unittest.main()
