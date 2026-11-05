"""Facility rule set (operator 2026-11-02 00:56): building-specific closure, unpriced Vista sauna, ALL THAT WELLNESS solo x2."""
import sys, unittest, copy
from types import SimpleNamespace
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(HERE))
import visit_run  # noqa: F401  (sets up operator_choice import path)
from operator_choice.autonomy_v1 import facility_rules as FR, hotel_catalog as H

def actor(b='VISTA', day='2026-10-24', n=2, room=None, used=None, pkg=None):
    opts = {'room_products': {'P1': room}} if room else {}
    return SimpleNamespace(B=b, N=n, pid='P1', sc={'date': day, 'catalog_options': opts},
                           visit_history={'hotel_entitlement_usage': dict(used or {})}, vs={'package_context': pkg} if pkg else {})

class FacilityRules(unittest.TestCase):
    def test_vista_closure_second_wednesday(self):
        self.assertEqual(FR.block(actor('VISTA', '2026-10-14', room='HC-MENU-028'), 'sauna'), 'VISTA_WELLNESS_REGULAR_CLOSURE_2ND_WEDNESDAY')
        # Grand closure date does not close the Vista wellness club
        self.assertIsNone(FR.block(actor('VISTA', '2026-10-20', room='HC-MENU-028'), 'sauna'))
    def test_grand_closure_third_tuesday(self):
        for code in ('sauna', 'SAUNA', 'fitness'):
            self.assertEqual(FR.block(actor('GRAND', '2026-10-20'), code), 'GRAND_FITNESS_REGULAR_CLOSURE_3RD_TUESDAY')
        self.assertIsNone(FR.block(actor('GRAND', '2026-10-14'), 'sauna'))
        self.assertIsNone(FR.block(actor('DOUGLAS', '2026-10-24'), 'fitness'))
    def test_vista_sauna_without_included_benefit_is_price_unknown_not_blocked(self):
        a = actor('VISTA', '2026-10-24')
        self.assertIsNone(FR.block(a, 'SAUNA'))            # use stays possible (no ban)
        self.assertFalse(FR.vista_sauna_unpriced(a, 'sauna'))
        self.assertFalse(FR.vista_sauna_unpriced(actor('VISTA', room='HC-MENU-028'), 'SAUNA'))
        self.assertFalse(FR.vista_sauna_unpriced(actor('VISTA', room='HC-MENU-028', used={'HC_ROOM_SAUNA_ONCE': 1}), 'SAUNA'))
        self.assertFalse(FR.vista_sauna_unpriced(actor('GRAND'), 'sauna'))
    def test_unpriced_order_uses_existing_unknown_price_contract(self):
        c = {'components': [{'source_line': 232, 'unit_price_krw': 44000, 'price_status': 'X', 'discount_krw': 0}],
             'unit_price_krw': 44000, 'price_status': 'COMPOSED_EXISTING_REFERENCE', 'hc_included': False, 'service_period': 'activity'}
        [m] = FR.mark_unpriced([c])
        out = H.charge(m)
        self.assertEqual(out['status'], '가격 미정'); self.assertIsNone(out['krw'])
        self.assertIsNone(out['sku_contract']['unit_price_krw']); self.assertIsNone(out['sku_contract']['components'][0]['unit_price_krw'])
        inc = dict(c, hc_included=True)
        self.assertNotIn('price_unknown', FR.mark_unpriced([inc])[0])
        self.assertEqual(H.charge(FR.mark_unpriced([inc])[0], included=True)['krw'], 0)
    def test_all_that_wellness_two_persons_once_or_one_person_twice(self):
        self.assertEqual(FR.room_sauna_cover(actor(n=2, room='HC-MENU-028')), 1)
        self.assertEqual(FR.room_sauna_cover(actor(n=1, room='HC-MENU-028')), 2)
        self.assertEqual(FR.room_sauna_cover(actor(n=1, room='HC-MENU-028', used={'HC_ROOM_SAUNA_ONCE': 1})), 1)
        self.assertEqual(FR.room_sauna_cover(actor(n=1, room='HC-MENU-028', used={'HC_ROOM_SAUNA_ONCE': 1, FR.SOLO_SECOND_KEY: 1})), 0)
    def test_hidden_html_vista_price_is_marked_unconfirmed(self):
        p = H.BY['HC-MENU-232']
        self.assertTrue(p['price_confirmed']); self.assertFalse(p['historical_tariff_confirmed']); self.assertEqual(p['unit_price_krw'],55000)
        self.assertEqual(H.BY['HC-MENU-231']['unit_price_krw'], 20000)
    def test_no_unfounded_sauna_probability_or_bonus_constants(self):
        src = (HERE.parent / 'experiments/persona_live/operator_choice/autonomy_v1/facility_rules.py').read_text()
        for bad in ('random', '0.7', '0.1', '+50'):
            self.assertNotIn(bad, src)

if __name__ == '__main__': unittest.main()
