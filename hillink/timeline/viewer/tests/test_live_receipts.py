import pytest
import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE/'tests'))
import ledger_service as LS
from test_security_cl20 import Server


class ReceiptRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads((HERE/'static/demo_story/flow_fixture_v1.json').read_text())

    def test_every_customer_event_receipt_and_hierarchy(self):
        count = 0
        for key, flow in self.fx['entries'].items():
            q = json.loads(key)
            if q['mode'] != 'one': continue
            ledger = LS.register(flow, q)
            self.assertTrue(ledger['checks']['engine_scene_equal_receipt'])
            for pid, r in ledger['receipts'].items():
                self.assertEqual(r['paid_krw'], r['engine_scene_paid_krw'])
                self.assertEqual(r['paid_krw']+r['assumption_addition_krw'], r['with_assumptions_krw'])
                self.assertEqual(len({x['row_id'] for x in r['rows']}), len(r['rows']))
                for row in r['rows']:
                    if row['status'] in ('무료','포함','금액 미확인'): self.assertEqual(row['paid_krw'], 0)
                    self.assertIsNone(row['actual_transaction_id'])
                    self.assertIsNone(row['net_revenue_krw'])
                    self.assertEqual(row['tax_status'], 'UNKNOWN')
            for level in ledger['levels'].values():
                self.assertEqual(sum(x['paid_krw'] for x in level), ledger['totals']['paid_krw'])
                self.assertEqual(sum(x['with_assumptions_krw'] for x in level), ledger['totals']['with_assumptions_krw'])
            count += 1
        self.assertEqual(count, 22)

    def test_known_receipt_and_unknown_room_are_separate(self):
        q, flow = next((json.loads(k),v) for k,v in self.fx['entries'].items() if json.loads(k)['personas']==['A01'] and not json.loads(k)['event'])
        r = LS.register(flow, q)['receipts']['A01']
        self.assertEqual((r['paid_krw'],r['assumption_addition_krw'],r['with_assumptions_krw']), (626000,313000,939000))
        room = next(x for x in r['rows'] if x['act']=='room_night')
        self.assertEqual(room['status'],'금액 미확인')
        self.assertEqual(room['paid_krw'],0)
        self.assertIsNone(room['net_revenue_krw'])
        self.assertTrue(any('같은 날' in note for row in r['rows'] for note in row['notes']))
        self.assertTrue(any(a['purchase_status']=='NO_PURCHASE' for a in r['actions']))
        self.assertTrue(any(a['considered'] or a['blocked'] for a in r['actions']))
        self.assertTrue(all(a['amount_is_in_receipt'] is False for a in r['actions'] if a['purchase_status']=='NO_PURCHASE'))
        self.assertTrue(all(x['price_source_status']=='ENGINE_CHARGE_BASIS_PRESENT; VERIFIED_CATALOG_NOT_APPLIED' for x in r['rows'] if x['price_basis']))
        self.assertTrue(all(x['product_id'] is None or x['product_id'] != x['action_id'] for x in r['rows']))

    def test_identical_result_is_idempotent_and_source_is_unchanged(self):
        key, flow = next(iter(self.fx['entries'].items())); q=json.loads(key); before=copy.deepcopy(flow)
        self.assertEqual(LS.register(flow,q),LS.register(flow,q))
        self.assertEqual(flow,before)

    def test_filter_uses_exact_same_rows_and_zero_cohort(self):
        q, flow = next((json.loads(k),v) for k,v in self.fx['entries'].items() if len(json.loads(k)['personas'])==11)
        full=LS.register(flow,q)
        a=LS.lookup(full['run_id'],stay_status='staying');b=LS.lookup(full['run_id'],stay_status='non_staying')
        self.assertEqual(a['team_count']+b['team_count'],11)
        self.assertEqual(a['totals']['paid_krw']+b['totals']['paid_krw'],full['totals']['paid_krw'])
        ty=next(iter(full['receipts'].values()))['customer_type']
        filtered=LS.lookup(full['run_id'],customer_type=ty)
        self.assertTrue(all(r['customer_type']==ty for r in filtered['receipts'].values()))
        with self.assertRaises(LS.ReceiptError):LS.lookup('0'*64)
        with self.assertRaises(LS.ReceiptError):LS.lookup(full['run_id'],customer_type='invalid')


class ReceiptHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.s=Server({'HILLINK_REVIEWER_LOCAL':'','HILLINK_DEPLOY':'local','HILLINK_V12Z_COMMON':'1','HILLINK_NATIVE_HYBRID':'1','HILLINK_LLM_ENABLED':'0','HILLINK_LLM_EXTERNAL_OPT_IN':'0'})
    @classmethod
    def tearDownClass(cls):cls.s.stop()

    @pytest.mark.requires_private_personas('A01','A03','A08')
    def test_opt_in_does_not_change_existing_flow_contract(self):
        q={'personas':['A01'],'mode':'one','seed':0,'event':False}
        st,b=self.s.call('/api/flow',q);self.assertEqual(st,200);old=json.loads(b)
        st,b=self.s.call('/api/flow',{**q,'include_ledger':True});self.assertEqual(st,200);new=json.loads(b)
        ledger=new.pop('ledger');self.assertEqual(new,old);self.assertNotIn('profile_sha',new)
        self.assertTrue(ledger['context']['profile_sha'])
        # New executions resolve concrete C01 menus; the historical fixture above stays 626000.
        # Previous catalogue expected 429000. With the reviewed menu candidates,
        # four truffle pastas (49000 each) replace the old pizza choice.
        self.assertEqual(ledger['receipts']['A01']['paid_krw'],403000)
        pasta=[r for r in ledger['receipts']['A01']['rows'] if r.get('product_sku_id')=='HC-PDF-PIZZA_HILL-TRUFFLE']
        self.assertEqual([(r['billing_quantity'],r['unit_price_krw'],r['paid_krw']) for r in pasta],[(4,49000,196000)])
        self.assertTrue(any(row.get('sku_contract') for row in ledger['receipts']['A01']['rows']))
        self.assertEqual(ledger['source'],'live_engine')

    def test_no_client_transactions_and_demo_source_label(self):
        st,b=self.s.call('/api/ledger/filter',{'run_id':'0'*64});self.assertEqual(st,409)
        key=next(k for k in json.loads((HERE/'static/demo_story/flow_fixture_v1.json').read_text())['entries'] if json.loads(k)['personas']==['A03'])
        st,b=self.s.call('/api/ledger/demo',{'key':key});self.assertEqual(st,200);self.assertEqual(json.loads(b)['source'],'stored_demo')
        st,b=self.s.call('/api/ledger/demo',{'key':'not a stored run'});self.assertEqual(st,404)
        st,b=self.s.call('/api/flow',{'personas':['N08'],'include_ledger':True});self.assertEqual(st,403)


# 11/03: frozen receipt amounts predate the breakfast contract policy — reproduce the previous policy in this module only.
import os as _bf_os
def setUpModule():
    _bf_os.environ["HILLINK_BREAKFAST_POLICY"] = "LEGACY_STAY_INCLUDED"
def tearDownModule():
    _bf_os.environ.pop("HILLINK_BREAKFAST_POLICY", None)


if __name__=='__main__':unittest.main()


class ReceiptComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx=json.loads((HERE/'static/demo_story/flow_fixture_v1.json').read_text())
        cls.pair=[]
        for event in (False,True):
            key,flow=next((k,v) for k,v in cls.fx['entries'].items() if len(json.loads(k)['personas'])==11 and bool(json.loads(k)['event'])==event)
            flow['profile_sha']='test-profile-sha';flow.setdefault('engine',{})['version']='test-engine-version'
            cls.pair.append(LS.register(flow,json.loads(key)))

    def test_event_difference_reconciles_by_customer_venue_department(self):
        a,b=self.pair;c=LS.compare(a['run_id'],b['run_id'])
        self.assertTrue(c['comparable']);self.assertEqual(c['team_count'],11)
        self.assertEqual(sum(v['delta_krw'] for v in c['venues']),c['delta_krw'])
        self.assertEqual(sum(v['delta_krw'] for v in c['customers'].values()),c['delta_krw'])
        for x in c['customers'].values():
            self.assertEqual(sum(x['decomposition'].values()),x['delta_krw'])
            self.assertEqual(sum(y['delta_krw'] for y in x['departments']),x['delta_krw'])
            self.assertEqual(sum(y['delta_krw'] for y in x['venues']),x['delta_krw'])
        z=LS.compare(a['run_id'],a['run_id']);self.assertEqual(z['delta_krw'],0)

    def test_price_and_unexplained_change_are_not_fabricated(self):
        a=copy.deepcopy(next(iter(self.pair[0]['receipts'].values())))
        b=copy.deepcopy(a);r=next(r for r in b['rows'] if r['paid_krw']>0)
        r['paid_krw']+=100;r['unit_price_krw']=(r['unit_price_krw'] or 0)+100;b['paid_krw']+=100
        parts,_,changes=LS._decompose(a,b);self.assertEqual(parts['price_condition'],100);self.assertEqual(len(changes),1)
        c=copy.deepcopy(a);r=next(r for r in c['rows'] if r['paid_krw']>0);r['paid_krw']+=101;c['paid_krw']+=101
        parts,_,_=LS._decompose(a,c);self.assertEqual(parts['interaction'],101)

    def test_changed_cohort_and_replay_are_not_live_comparisons(self):
        a,b=self.pair
        key,flow=next((k,v) for k,v in self.fx['entries'].items() if json.loads(k)['personas']==['A01'])
        one=LS.register(flow,json.loads(key));self.assertFalse(LS.compare(a['run_id'],one['run_id'])['comparable'])
        replay=LS.register(flow,json.loads(key),'stored_demo')
        with self.assertRaises(LS.ReceiptError):LS.compare(one['run_id'],replay['run_id'])

    def test_ab_requires_same_non_event_context_and_profile(self):
        a,b=self.pair
        self.assertNotEqual(a['context']['event'],b['context']['event'])
        self.assertEqual(a['context']['profile_sha'],b['context']['profile_sha'])
        cache=LS._CACHE[b['run_id']]['ledger']; original=copy.deepcopy(cache['context'])
        try:
            cache['context']['visit_override']={'A01': {'stay': False, 'party_size': 2}}
            with self.assertRaisesRegex(LS.ReceiptError, '행사 조건 외 입력'):
                LS.compare(a['run_id'],b['run_id'],event_only=True)
            cache['context']=copy.deepcopy(original)
            cache['context']['event']=a['context']['event']
            with self.assertRaisesRegex(LS.ReceiptError, '행사 조건이 다른'):
                LS.compare(a['run_id'],b['run_id'],event_only=True)
            cache['context']=copy.deepcopy(original)
            cache['context']['profile_sha']='different-profile-sha'
            with self.assertRaisesRegex(LS.ReceiptError, '행사 조건 외 입력'):
                LS.compare(a['run_id'],b['run_id'],event_only=True)
        finally:
            cache['context']=original

    def test_duplicate_simulation_rows_are_idempotent_and_collisions_rejected(self):
        row={'_row_key':'same','내부 ID':'A01','L2 부문':'F&B','L3 업장':'P','L4 상품':'S','상태':'실결제','확정 결제액':100,'가정 결제액':100}
        rows,n=LS._dedupe_rows([row,copy.deepcopy(row)])
        self.assertEqual((len(rows),n),(1,1))
        conflict=copy.deepcopy(row);conflict['확정 결제액']=200
        with self.assertRaises(LS.ReceiptError):LS._dedupe_rows([row,conflict])


class ReceiptComparisonHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The isolated HTTP regression opts into the existing test-only publish override
        # so it can exercise all 11 approved demo identities without changing the
        # checked-in publication allowlist.
        ids=['A01','A02','A03','A04','A05','A07','A08','A10','blog41','blog42','blog43']
        cls.s=Server({'HILLINK_DEPLOY':'local','HILLINK_REVIEWER_LOCAL':'','HILLINK_PUBLISH_OVERRIDE':json.dumps({pid:True for pid in ids})})
    @classmethod
    def tearDownClass(cls):cls.s.stop()

    @pytest.mark.requires_private_personas('A01','A03','A08')
    def test_live_event_ab_has_independent_receipts(self):
        results=[]
        for event in (False, True):
            st,body=self.s.call('/api/flow',{'personas':['A01'],'include_ledger':True,'seed':0,'event':event,'mode':'one','intervention':'none','visit_override':{'A01':{'stay':True,'building':'GRAND','phase':'mid','party_size':4}}})
            self.assertEqual(st,200);d=json.loads(body);l=d['ledger'];self.assertEqual(l['receipts']['A01']['paid_krw'],l['receipts']['A01']['engine_scene_paid_krw']);results.append(l)
        st,body=self.s.call('/api/ledger/compare',{'baseline_id':results[0]['run_id'],'scenario_id':results[1]['run_id'],'event_only':True})
        self.assertEqual(st,200);c=json.loads(body);self.assertTrue(c['comparable']);self.assertEqual(c['comparison_kind'],'event_ab');self.assertEqual(c['delta_krw'],results[1]['totals']['paid_krw']-results[0]['totals']['paid_krw'])
        self.assertEqual(c['customers']['A01']['before_context']['visit_override'],c['customers']['A01']['after_context']['visit_override'])
        self.assertIn('activity_changes',c['customers']['A01'])
        self.assertIn('row_changes',c['customers']['A01'])

    @pytest.mark.requires_private_personas('A01','A03','A08')
    def test_live_11_customer_event_ab_uses_same_profile_and_reconciles(self):
        runs=[]
        ids=['A01','A02','A03','A04','A05','A07','A08','A10','blog41','blog42','blog43']
        for event in (False,True):
            st,body=self.s.call('/api/flow',{'personas':ids,'mode':'many','include_ledger':True,'seed':0,'event':event,'intervention':'none','product_levers':{},'observe':'day'})
            self.assertEqual(st,200,body);data=json.loads(body);ledger=data['ledger']
            self.assertEqual(ledger['team_count'],11)
            self.assertTrue(ledger['checks']['engine_scene_equal_receipt'])
            self.assertEqual(ledger['checks']['duplicate_simulation_rows'],0)
            runs.append(ledger)
        a,b=runs
        self.assertEqual(a['context']['profile_sha'],b['context']['profile_sha'])
        self.assertEqual(a['context']['engine_version'],b['context']['engine_version'])
        c=json.loads(self.s.call('/api/ledger/compare',{'baseline_id':a['run_id'],'scenario_id':b['run_id'],'event_only':True})[1])
        self.assertTrue(c['comparable']);self.assertEqual(c['team_count'],11)
        self.assertEqual(c['delta_krw'],b['totals']['paid_krw']-a['totals']['paid_krw'])
        self.assertEqual(sum(x['delta_krw'] for x in c['venues']),c['delta_krw'])
        self.assertEqual(sum(x['delta_krw'] for x in c['customers'].values()),c['delta_krw'])
        self.assertEqual(sum(x['delta_krw'] for x in c['customers']['A01']['venues']),c['customers']['A01']['delta_krw'])


class RevenueCohort(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx=json.loads((HERE/'static/demo_story/flow_fixture_v1.json').read_text())
        cls.records=[]
        for event in (False,True):
            key,flow=next((k,v) for k,v in fx['entries'].items() if len(json.loads(k)['personas'])==11 and bool(json.loads(k)['event'])==event)
            cls.records.append(LS.register(flow,json.loads(key)))

    def test_every_type_and_stay_filter_reconciles_all_levels(self):
        for full in self.records:
            for ty in [None]+full['customer_types']:
                for stay in ('all','staying','non_staying'):
                    d=LS.lookup(full['run_id'],ty,stay)
                    want={p:r for p,r in full['receipts'].items() if (not ty or r['customer_type']==ty) and (stay=='all' or r['stay']==(stay=='staying'))}
                    self.assertEqual(set(d['receipts']),set(want))
                    self.assertEqual(d['team_count'],len(want))
                    self.assertEqual(d['totals']['paid_krw'],sum(r['paid_krw'] for r in want.values()))
                    for level in d['levels'].values():
                        self.assertEqual(sum(g['paid_krw'] for g in level),d['totals']['paid_krw'])
                        self.assertEqual(sum(g['with_assumptions_krw'] for g in level),d['totals']['with_assumptions_krw'])
                    for v in d['venues']:
                        self.assertEqual(v['team_count'],len(v['customer_ids']))
                        self.assertEqual(sum(t['team_count'] for t in v['types']),v['team_count'])
                        self.assertEqual(sum(t['paid_krw'] for t in v['types']),v['paid_krw'])

    def test_repeated_visits_do_not_inflate_teams_and_room_is_not_zero_price(self):
        full=self.records[0]
        venue=next(v for v in full['venues'] if v['name']=='스카이야드')
        self.assertEqual(venue['team_count'],len(set(venue['customer_ids'])))
        room=[g for g in full['levels']['L4'] if g['key'][0]=='ROOM' and '객실 1박' in g['key'][2]]
        self.assertTrue(room)
        self.assertTrue(all(g['paid_krw']==0 and g['unknown_count']>0 for g in room))

    def test_filtered_comparison_has_same_cohort_and_reconciled_delta(self):
        a,b=self.records
        for ty in [None]+a['customer_types']:
            for stay in ('all','staying','non_staying'):
                c=LS.compare(a['run_id'],b['run_id'],ty,stay)
                if c['comparable']:
                    self.assertEqual(sum(v['delta_krw'] for v in c['venues']),c['delta_krw'])
                    self.assertEqual(sum(v['delta_krw'] for v in c['customers'].values()),c['delta_krw'])
