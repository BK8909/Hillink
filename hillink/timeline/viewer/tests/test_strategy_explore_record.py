"""The strategy-exploration record shown on the revenue screen must keep computed results, engine-limited runs
and uncomputable hypotheses apart, and must not recommend anything the engine did not show to raise spend."""
import json, re, unittest
from pathlib import Path
VIEWER = Path(__file__).resolve().parents[1]
X = json.loads((VIEWER / 'static' / 'strategy_santa_explore.json').read_text())
PRESET = json.loads((VIEWER / 'static' / 'strategy_santa_ab.json').read_text())
CATALOG = {p['sku_id']: p for p in json.loads((VIEWER.parents[0] / 'experiments' / 'persona_live' / 'operator_choice' / 'autonomy_v1' / 'hotel_catalog.json').read_text())['products']}


class StrategyExploreRecord(unittest.TestCase):
    def test_status_and_metrics_agree(self):
        for s in X['strategies']:
            if s['status'] in ('COMPUTED', 'ENGINE_LIMIT'):
                self.assertRegex(s['metrics']['run'], r'^[0-9a-f]{64}$', s['id'])
            else:
                self.assertEqual(s['status'], 'NOT_COMPUTABLE'); self.assertNotIn('metrics', s, s['id'])

    def test_engine_limited_runs_are_excluded_from_judgement(self):
        for s in X['strategies']:
            if s['status'] == 'ENGINE_LIMIT':
                self.assertLess(len(s['metrics']['santa']), 6, s['id']); self.assertEqual(s['verdict'], 'HOLD')

    def test_no_recommendation_without_engine_evidence_of_gain(self):
        for s in X['strategies']:
            if s['verdict'] == 'RECOMMENDED':
                m = s.get('metrics') or {}
                self.assertEqual(s['status'], 'COMPUTED'); self.assertGreater(m.get('fam_fnb', 0), 0); self.assertGreater(m.get('total', 0), 0)

    def test_computed_strategies_use_existing_discountable_skus(self):
        ids = {s['id'] for s in X['strategies'] if s['status'] == 'COMPUTED'}
        promos = {p['id']: p for p in PRESET['promotions']}
        self.assertEqual(ids, set(promos))
        for p in promos.values():
            sku = CATALOG[p['sku_id']]
            self.assertEqual(sku['unit_price_krw'], p['base_price_krw']); self.assertNotEqual(sku.get('discount_policy'), 'NO_DISCOUNT_OR_POINTS')

    def test_recorded_deltas_match_preset(self):
        # The A/B preset uses the official sessions and the current meal-alternative policy.
        off = {r['id']: r['metrics'] for r in X['official']['runs']}
        dlv = {r['id']: r['metrics'] for r in X['official']['delivery_recheck']['runs']}
        self.assertEqual(PRESET['fixed']['booked_start'], X['session_basis']['official']['booked'])
        for p in PRESET['promotions']:
            self.assertEqual(off[p['id']]['total'], p['recorded']['delta_krw'])
            self.assertEqual(dlv[p['id']]['total'], p['recorded']['delta_krw'])
            cur = {r['id']: r['metrics'] for r in X['official_current']['runs']}
            self.assertTrue(cur[p['id']]['run'].startswith(p['recorded']['scenario_run_id']))
            self.assertEqual(X['official_current']['baseline']['paid_krw'], p['recorded']['baseline_paid_krw'])


class ScenarioBasisFacts(unittest.TestCase):
    def test_booked_family_facts_are_scenario_setting_only(self):
        for f in PRESET['booked_families']:
            self.assertEqual(f['basis_role'], 'SCENARIO_SETTING_ONLY')
            for fid in f['basis_fact_ids']:
                self.assertIn(fid, f['basis'])

    def test_b3_is_not_generalised_to_zero_effect(self):
        b3 = next(i for i in X['pr126']['items'] if i['id'] == 'B3')
        self.assertEqual(b3['status'], '3인 가족 조건에서 실행 가능한 대상 없음')

    def test_official_reconciliation_differs_only_by_the_promotion(self):
        R = X['official']['reconciliation']
        for k in ('S1', 'S2'):
            self.assertTrue(R[k]['same_customers'])
            self.assertEqual([d['path'] for d in R[k]['input_diff_vs_A']], ['catalog_options.discount_percent'])
            self.assertEqual(R[k]['compare']['delta'], sum(R[k]['L2_delta'].values()))


if __name__ == '__main__':
    unittest.main()


class FinalPolicyRecord(unittest.TestCase):
    """The Santa tab's primary numbers come from the final ledger policy (room valuation v3) and never mix with older-policy totals."""
    def test_v3_baseline_excludes_unpriced_room_nights(self):
        V = X['official_v3']; b = V['baseline']
        self.assertEqual(V['policy']['room_valuation'], 'native-room-l5-v3')
        self.assertEqual((b['room_nights'], b['room_nights_unpriced'], b['L2'].get('ROOM', 0)), (28, 28, 0))
        self.assertTrue(b['l5_equals_l1']); self.assertEqual(b['paid_krw'], sum(b['L2'].values()))
    def test_strategy_deltas_are_policy_independent(self):
        old = {r['id']: r['metrics'] for r in X['official']['runs']}; new = {r['id']: r['metrics'] for r in X['official_v3']['runs']}
        for k in ('S1', 'S2', 'B3'):
            self.assertEqual((new[k]['total'], new[k]['fam_fnb'], len(new[k]['fam_changed'])), (old[k]['total'], old[k]['fam_fnb'], len(old[k]['fam_changed'])), k)
            self.assertEqual(new[k]['paid_krw'] - X['official_v3']['baseline']['paid_krw'], new[k]['total'], k)
    def test_ledger_checks_pass_on_final_policy_runs(self):
        for k, c in X['official_v3']['checks'].items():
            self.assertTrue(all(v for key, v in c.items() if isinstance(v, bool)), k)


class CurrentPolicyRecord(unittest.TestCase):
    """Room valuation v4: every room night at the virtual model rate; no Santa package without explicit selection."""
    def test_current_baseline_prices_every_room_night(self):
        V = X['official_current']; b = V['baseline']
        self.assertEqual(V['policy']['room_valuation'], 'native-room-l5-v4')
        self.assertEqual((b['room_nights'], b['room_nights_unpriced'], b['L2']['ROOM']), (28, 0, 7768000))
        self.assertEqual(b['paid_krw'], sum(b['L2'].values()))
    def test_deltas_identical_across_room_policies(self):
        cur = {r['id']: r['metrics'] for r in X['official_current']['runs']}; v3 = {r['id']: r['metrics'] for r in X['official_v3']['runs']}
        for k in ('S1', 'S2', 'B3'):
            self.assertEqual((cur[k]['total'], cur[k]['fam_fnb']), (v3[k]['total'], v3[k]['fam_fnb']), k)
    def test_checks_pass(self):
        for k, c in X['official_current']['checks'].items():
            self.assertTrue(all(v for v in c.values() if isinstance(v, bool)), k)
