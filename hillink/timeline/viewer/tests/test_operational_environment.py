import unittest,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run as V
from operator_choice.autonomy_v1 import operational_environment as E

class EnvironmentContract(unittest.TestCase):
    def test_valid_date_calendar_and_unsupported_year(self):
        days=V.day_specs('stay_2','2026-12-25','none')
        self.assertEqual([d['date'] for d in days],['2026-12-25','2026-12-26','2026-12-27'])
        for d in ('2027-01-01','2025-12-25'):
            with self.assertRaises(ValueError):V.day_specs('day_visit',d,'none')
        self.assertEqual(E.validate_date('2025-12-25',True).year,2025)
    def test_reject_unknown_or_malformed_environment(self):
        for value in ([],{'wind':'high'},{'weather':'snow'},{'arrival_time':'09:99'},{'arrival_time':'07:30'},{'arrival_time':'20:01'},{'arrival_time':930}):
            with self.subTest(value=value),self.assertRaises(ValueError):E.validate(value)
    def test_rain_blocks_walk_but_keeps_pool_and_records_reason(self):
        a=SimpleNamespace(sc={'operational_environment':{'weather':'rain'}});why={}
        with patch.object(E.AD,'plan_ok',return_value='kept'),patch.object(E.AD,'engine_world_for',return_value={'offers':[{'id':'FOREST_WALK','available':True},{'id':'POOL','available':True}]}),E.install():
            self.assertIsNone(E.AD.plan_ok(a,'forest_walk',600,None,why))
            self.assertIn('forest_walk',why)
            self.assertEqual(E.AD.plan_ok(a,'pool',600,None,why),'kept')
            offers=E.AD.engine_world_for(a,None,600)['offers']
            self.assertFalse(offers[0]['available']);self.assertTrue(offers[1]['available'])
    def test_arrival_applies_only_first_day_and_scopes_are_restored(self):
        original=E.AD.Agent.__init__
        def init(a,*args,**kw):a.t=600
        with patch.object(E.AD.Agent,'__init__',init):
            with E.install():
                for phase,expected in [('checkin',870),('visit',870),('mid',600),('checkout',600)]:
                    a=SimpleNamespace(phase=phase,sc={'operational_environment':{'arrival_time':'14:30'}})
                    E.AD.Agent.__init__(a);self.assertEqual(a.t,expected)
            self.assertIs(E.AD.Agent.__init__,init)
        self.assertIs(E.AD.Agent.__init__,original)
