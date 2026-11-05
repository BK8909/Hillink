"""Approved included default: versioned contract, historical replay, and package extension."""
import unittest
from types import SimpleNamespace
import test_official_contracts  # establishes the viewer's engine import path
from operator_choice.autonomy_v1 import breakfast_policy as BP
import room_revenue as RR
import santa_packages as SP

class IncludedDefault(unittest.TestCase):
    def test_default_and_historical_plans(self):
        for building, rate in [('GRAND',313000),('VISTA',373000)]:
            v={'building':building}
            self.assertEqual(BP.plan(v),'breakfast_included')
            self.assertEqual(BP.plan(v,{'breakfast_policy':BP.V1}),'room_only')
            self.assertEqual(BP.plan(dict(v,breakfast_plan='room_only')),'room_only')
            flow={'visit':{'breakfast_policy':BP.V2,'start_date':'2026-10-24'},'visits':{'P':v}}
            self.assertEqual(RR.breakfast_room_fields(flow,'P',building)['virtual_gross_krw'],rate)
            flow['visit']['breakfast_policy']=BP.V1
            self.assertIsNone(RR.breakfast_room_fields(flow,'P',building))
    def test_unknown_douglas_rate_not_invented(self):
        self.assertEqual(BP.plan({'building':'DOUGLAS'}),'breakfast_included')
        self.assertEqual(BP.plan({'building':'DOUGLAS'},{'breakfast_policy':BP.V1}),'room_only')
        self.assertNotIn('DOUGLAS',BP.INCLUDED_ROOM_RATE)
    def test_right_is_not_forced_usage_and_only_two_adults_covered(self):
        a=SimpleNamespace(vs={'building':'GRAND','party_composition':{'adult_count':3,'children':[{'age_months':72}]}},sc={},stay=True,N=4)
        self.assertEqual(BP.covered_adults(a),2)
        self.assertFalse(BP.whole_party_covered(a))
        self.assertNotIn('used',a.vs)
        a.vs['breakfast_plan']='room_only'
        self.assertEqual(BP.covered_adults(a),0)
    def test_santa_first_night_and_extra_included_room(self):
        flow={'visit':{'breakfast_policy':BP.V2,'start_date':'2025-12-19','scenario_snapshot':{'event_card_id':SP.SANTA_CARD,'entitlements':{'P':{'selected_package':True}}}},'visits':{'P':{'building':'GRAND','party_size':3}}}
        self.assertEqual(SP.room_night(flow,'P','2025-12-19',0)['virtual_gross_krw'],559000)
        self.assertIsNone(SP.room_night(flow,'P','2025-12-20',1))
        self.assertEqual(RR.breakfast_room_fields(flow,'P','GRAND')['virtual_gross_krw'],313000)
        flow['visits']['P']['breakfast_plan']='room_only'
        self.assertIsNone(RR.breakfast_room_fields(flow,'P','GRAND'))
