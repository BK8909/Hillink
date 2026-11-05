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
        self.assertTrue(any('같은 날' in note for row in r['rows'] for note in row['notes']))

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
    def setUpClass(cls):cls.s=Server({'HILLINK_REVIEWER_LOCAL':'','HILLINK_DEPLOY':'local'})
    @classmethod
    def tearDownClass(cls):cls.s.stop()

    def test_opt_in_does_not_change_existing_flow_contract(self):
        q={'personas':['A01'],'mode':'one','seed':0,'event':False}
        st,b=self.s.call('/api/flow',q);self.assertEqual(st,200);old=json.loads(b)
        st,b=self.s.call('/api/flow',{**q,'include_ledger':True});self.assertEqual(st,200);new=json.loads(b)
        ledger=new.pop('ledger');self.assertEqual(new,old)
        self.assertEqual(ledger['receipts']['A01']['paid_krw'],626000)
        self.assertEqual(ledger['source'],'live_engine')

    def test_no_client_transactions_and_demo_source_label(self):
        st,b=self.s.call('/api/ledger/filter',{'run_id':'0'*64});self.assertEqual(st,409)
        key=next(k for k in json.loads((HERE/'static/demo_story/flow_fixture_v1.json').read_text())['entries'] if json.loads(k)['personas']==['A03'])
        st,b=self.s.call('/api/ledger/demo',{'key':key});self.assertEqual(st,200);self.assertEqual(json.loads(b)['source'],'stored_demo')
        st,b=self.s.call('/api/ledger/demo',{'key':'not a stored run'});self.assertEqual(st,404)
        st,b=self.s.call('/api/flow',{'personas':['N08'],'include_ledger':True});self.assertEqual(st,403)


if __name__=='__main__':unittest.main()


class ReceiptComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx=json.loads((HERE/'static/demo_story/flow_fixture_v1.json').read_text())
        cls.pair=[]
        for event in (False,True):
            key,flow=next((k,v) for k,v in cls.fx['entries'].items() if len(json.loads(k)['personas'])==11 and bool(json.loads(k)['event'])==event)
            cls.pair.append(LS.register(flow,json.loads(key)))

    def test_event_difference_reconciles_by_customer_venue_department(self):
        a,b=self.pair;c=LS.compare(a['run_id'],b['run_id'])
        self.assertTrue(c['comparable']);self.assertEqual(c['team_count'],11)
        self.assertEqual(sum(v['delta_krw'] for v in c['venues']),c['delta_krw'])
        self.assertEqual(sum(v['delta_krw'] for v in c['customers'].values()),c['delta_krw'])
        for x in c['customers'].values():
            self.assertEqual(sum(x['decomposition'].values()),x['delta_krw'])
            self.assertEqual(sum(y['delta_krw'] for y in x['departments']),x['delta_krw'])
        z=LS.compare(a['run_id'],a['run_id']);self.assertEqual(z['delta_krw'],0)

    def test_price_and_unexplained_change_are_not_fabricated(self):
        a=copy.deepcopy(next(iter(self.pair[0]['receipts'].values())))
        b=copy.deepcopy(a);r=next(r for r in b['rows'] if r['paid_krw']>0)
        r['paid_krw']+=100;r['unit_price_krw']=(r['unit_price_krw'] or 0)+100;b['paid_krw']+=100
        parts,_=LS._decompose(a,b);self.assertEqual(parts['price_condition'],100)
        c=copy.deepcopy(a);r=next(r for r in c['rows'] if r['paid_krw']>0);r['paid_krw']+=101;c['paid_krw']+=101
        parts,_=LS._decompose(a,c);self.assertEqual(parts['interaction'],101)

    def test_changed_cohort_and_replay_are_not_live_comparisons(self):
        a,b=self.pair
        key,flow=next((k,v) for k,v in self.fx['entries'].items() if json.loads(k)['personas']==['A01'])
        one=LS.register(flow,json.loads(key));self.assertFalse(LS.compare(a['run_id'],one['run_id'])['comparable'])
        replay=LS.register(flow,json.loads(key),'stored_demo')
        with self.assertRaises(LS.ReceiptError):LS.compare(one['run_id'],replay['run_id'])


class ReceiptComparisonHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.s=Server({'HILLINK_DEPLOY':'local','HILLINK_REVIEWER_LOCAL':''})
    @classmethod
    def tearDownClass(cls):cls.s.stop()

    def test_live_phase_change_has_independent_receipts(self):
        results=[]
        for phase in ('mid','checkout'):
            st,body=self.s.call('/api/flow',{'personas':['A01'],'include_ledger':True,'seed':0,'visit_override':{'A01':{'stay':True,'building':'GRAND','phase':phase,'party_size':4}}})
            self.assertEqual(st,200);d=json.loads(body);l=d['ledger'];self.assertEqual(l['receipts']['A01']['paid_krw'],l['receipts']['A01']['engine_scene_paid_krw']);results.append(l)
        st,body=self.s.call('/api/ledger/compare',{'baseline_id':results[0]['run_id'],'scenario_id':results[1]['run_id']})
        self.assertEqual(st,200);c=json.loads(body);self.assertTrue(c['comparable']);self.assertEqual(c['delta_krw'],results[1]['totals']['paid_krw']-results[0]['totals']['paid_krw'])
        self.assertEqual(results[1]['receipts']['A01']['assumption_addition_krw'],0)


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
