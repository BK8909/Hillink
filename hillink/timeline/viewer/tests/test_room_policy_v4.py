"""Room-night valuation v4: virtual model rate on every date (labelled as a model rate), explicit Santa package night,
explicit operator room-rate input. Both pricing paths (native and C01 catalog) follow the same rules."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import room_revenue as R, visit_run as VR

def flow(catalog=False, rates=None, building='GRAND', party=2, santa=False):
    v = dict(package_context=None, start_date='2025-12-19')
    if catalog: v.update(catalog_policy='C01_HOTEL_CATALOG_V1', catalog_options={})
    if rates: v['virtual_room_rates'] = dict(rates=rates)
    v['scenario_snapshot'] = dict(event_card_id='SANTA_KIDS_VILLAGE_2025', entitlements={'p': dict(selected_package=True, included_people=3)} if santa else {})
    return dict(visit_id='t', visit=v, visits={'p': dict(building=building, party_size=party, breakfast_plan='room_only')})

class RoomPolicyV4(unittest.TestCase):
    def test_version(self):
        self.assertEqual(R.NATIVE_VERSION, 'native-room-l5-v4')
    def test_model_rate_on_2025_nights_both_paths_labelled(self):
        for catalog in (False, True):
            for b, amount in (('GRAND', 247000), ('VISTA', 307000), ('DOUGLAS', 259000)):
                p = R.native_price(flow(catalog, building=b), 'p', '2025-12-19', 0, 2)
                self.assertEqual(p['virtual_gross_krw'], amount, (catalog, b))
                self.assertTrue(p['model_rate_outside_model_year']); self.assertIn('가상 객실 모델 단가', p['product'])
    def test_2026_unchanged(self):
        self.assertEqual(R.native_price(flow(False), 'p', '2026-10-24', 0, 2)['product'], '객실 1박 · 2026 가상 모델 단가')
    def test_santa_package_first_night_only_and_explicit(self):
        for catalog in (False, True):
            n0 = R.native_price(flow(catalog, santa=True, party=3), 'p', '2025-12-19', 0, 2)
            n1 = R.native_price(flow(catalog, santa=True, party=3), 'p', '2025-12-20', 1, 2)
            self.assertEqual((n0['virtual_gross_krw'], n0['package_id']), (559000, 'SANTA_PKG_2025'), catalog)
            self.assertEqual(n1['virtual_gross_krw'], 247000, catalog); self.assertNotEqual(n1.get('package_id'), 'SANTA_PKG_2025')
            self.assertEqual(R.native_price(flow(catalog, party=3), 'p', '2025-12-19', 0, 2)['virtual_gross_krw'], 247000)   # no selection, no package
            self.assertEqual(R.native_price(flow(catalog, santa=True, building='DOUGLAS', party=3), 'p', '2025-12-19', 0, 1)['virtual_gross_krw'], 259000)
    def test_explicit_operator_rate(self):
        for catalog in (False, True):
            p = R.native_price(flow(catalog, {'GRAND': 300000}), 'p', '2025-12-19', 0, 2)
            self.assertEqual((p['virtual_gross_krw'], p['price_status']), (300000, 'OPERATOR_VIRTUAL_ROOM_RATE_INPUT'))
    def test_request_validation(self):
        base = dict(personas=['A08'], duration='stay_2', seed=0, start_date='2025-12-19')
        for bad in ({'GRAND': 0}, {'GRAND': '300000'}, {'SUITE': 300000}, {}):
            self.assertEqual(VR.run_visit(dict(base, virtual_room_rates=bad)).get('code'), 'E_VISIT_ROOM_RATE')

if __name__ == '__main__': unittest.main()
