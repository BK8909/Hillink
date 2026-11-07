"""Current-engine ledger invariants (independent of frozen historical amounts).

Every KRW amount is an integer, and a charged row's unit price x billing quantity equals its paid amount.
Regression: a buffet breakfast whose room contract covered 2 of 3 guests was priced 28,333.33 won per person;
the ledger showed 85000.0 and parsed a unit price of 333,333,333,332 won from the basis text (legacy selector).
"""
import sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(HERE))
import visit_run as VR
import ledger_service as LS

HAS_INPUT = 'A05' in VR.AD.load_inputs()[0]


def rows(request):
    flow = VR.run_visit(request)
    if flow.get('error'): raise AssertionError(flow)
    ledger = LS.register_visit(flow, request)
    return ledger, [r for c in ledger['receipts'].values() for r in c['rows']]


@unittest.skipUnless(HAS_INPUT, 'approved A05 execution inputs unavailable')
class LedgerAmountInvariants(unittest.TestCase):
    def check(self, request):
        ledger, rs = rows(request)
        self.assertTrue(rs)
        for r in rs:
            for k in ('paid_krw', 'unit_price_krw', 'discount_krw'):
                if r.get(k) is not None: self.assertIsInstance(r[k], int, (k, r.get('product'), r[k]))
            if r.get('amount_status') == 'SIMULATED_CHARGE' and r.get('unit_price_krw') is not None and isinstance(r.get('billing_quantity'), int) and not r.get('discount_krw'):
                self.assertEqual(r['unit_price_krw'] * r['billing_quantity'], r['paid_krw'], r.get('product'))
        self.assertIsInstance(ledger['totals']['paid_krw'], int)
        self.assertTrue(ledger['checks']['receipts_equal_L4_L3_L2_L1'])

    def test_legacy_selector_partly_included_breakfast(self):
        self.check(dict(personas=['A05'], duration='stay_2', event_mode='none', seed=0, start_date='2026-10-24'))

    def test_product_catalog_engine(self):
        self.check(dict(personas=['A05'], duration='stay_2', event_mode='none', seed=0, start_date='2026-10-24',
                        behavior_engine='m4_c01', catalog_policy='C01_HOTEL_CATALOG_V1'))
