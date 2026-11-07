"""Current-engine checks kept apart from the frozen historical expectations.

The six CL-42 smoke cases and the CD-15 operating experiment keep their original expected values in their own tests
(classified standing failures: the engine has changed since they were frozen). These tests check what must hold for
the current engine on the same requests, without new expected amounts:
- the visit structure (days, nights, phases, event dates) is the one the request asks for;
- ledger receipts = L4 = L3 = L2 = L1, day totals = visit total, no duplicate rows, integer KRW;
- the sealed CD-15 experiment refuses to compute on a changed engine instead of producing numbers.
"""
import json, subprocess, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]; ROOT = HERE.parents[1]; sys.path.insert(0, str(HERE))
import visit_run, ledger_service

FIXTURE = json.loads((ROOT / 'research/cl39/fixtures/visit_smoke_v1.json').read_text(encoding='utf-8'))
LOCAL = ROOT / 'timeline/experiments/persona_live/operator_choice/operator_world_v1_1/turn_personas_ext.local.json'


class CurrentEngineSmokeInvariants(unittest.TestCase):
    def test_six_smoke_requests_structure_and_ledger_identities(self):
        for case in FIXTURE['cases']:
            with self.subTest(request=case['request']):
                request = dict(case['request'], behavior_engine='legacy')
                flow = visit_run.run_visit(request)
                if flow.get('code') == 'E_FLOW_INPUT_MISSING': self.skipTest('approved local run inputs are not connected')
                self.assertFalse(flow.get('error'), flow.get('error'))
                ledger = ledger_service.register_visit(flow, request)
                want = case['expected']
                self.assertEqual(len(flow['visit_days']), want['day_count'])
                self.assertEqual(flow['visit']['nights'], want['nights'])
                self.assertEqual([d['phase'] for d in flow['visit_days']], want['phases'])
                self.assertEqual(ledger['visit']['event_dates'], want['event_dates'])
                chk = ledger['checks']
                self.assertIs(chk['receipts_equal_L4_L3_L2_L1'], True); self.assertIs(chk['day_totals_equal_visit_total'], True)
                self.assertIs(chk['room_nights_equal_duration'], True); self.assertEqual(chk['duplicate_simulation_rows'], 0)
                levels = {lv: sum(g.get('paid_krw', 0) for g in ledger['levels'][lv]) for lv in ('L4', 'L3', 'L2', 'L1')}
                self.assertEqual(len(set(levels.values())), 1, levels); self.assertEqual(levels['L1'], ledger['totals']['paid_krw'])
                self.assertEqual(sum(d['paid_krw'] for d in ledger['visit']['days']), ledger['totals']['paid_krw'])
                for r in (r for c in ledger['receipts'].values() for r in c['rows']):
                    self.assertIsInstance(r['paid_krw'], int, r.get('product'))


@unittest.skipUnless(LOCAL.exists(), 'local CD-15 profile not restored')
class SealedExperimentGuard(unittest.TestCase):
    def test_cd15_refuses_on_a_changed_engine(self):
        out = subprocess.run([sys.executable, str(HERE / 'opx_run.py')], input=json.dumps({'op': 'run', 'date': '2026-10-27', 'start_time': '18:30', 'discount_amount': 20000}),
                             capture_output=True, text=True, timeout=120)
        d = json.loads(out.stdout)
        self.assertEqual(d['experiment']['run_status'], 'ENGINE_SHA_MISMATCH')
        self.assertFalse(d['integrity']['ok'])
        self.assertNotIn('venue_aggregates', d)
        self.assertEqual(sorted(x['file'] for x in d['integrity']['engine'] if not x['ok']), ['engine.py', 'turn_view.py'])
