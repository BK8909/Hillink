import copy, csv, json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import experiment_service as S
from offer_eligibility import check_offer

class CD15Tests(unittest.TestCase):
    def req(self, discount=None):
        r=S.default_request()
        if discount is not None:
            r['scenario_id']=f'BUFFET_{discount}'
            if discount: r['offer_overrides']={'THE_BUFFET':{'discount_amount':discount,'discount_unit':'per_person','scenario_label':f'Buffet {discount} KRW/person'}}
        return r
    def counts(self, result):
        return {x['venue_id']:x['scenario_selected_count'] for x in result['venue_aggregates']}
    def test_cd14_four_discount_baselines(self):
        expected={0:{'GEUMRYONG':11,'THE_BUFFET':0},10000:{'GEUMRYONG':11,'THE_BUFFET':0},20000:{'GEUMRYONG':9,'THE_BUFFET':2},40000:{'GEUMRYONG':8,'THE_BUFFET':3}}
        for amount,want in expected.items():
            with self.subTest(amount=amount):
                got=S.run_request(self.req(amount))
                self.assertEqual(got['experiment']['run_status'],'COMPLETED')
                self.assertEqual(self.counts(got),want)
                self.assertEqual(len(got['customers']),11)
    def test_customer_winners_and_scores_match_cd14_rows(self):
        source_path=Path('/private/tmp/hillink-cd1024-14-private-20261024/results/verified_and_scenario_customer_results.csv')
        with source_path.open(encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f))
        variant={0:'A1_VERIFIED_SUBSET',10000:'B_SCENARIO_BUFFET_10K_DISCOUNT',20000:'B_SCENARIO_BUFFET_20K_DISCOUNT',40000:'B_SCENARIO_BUFFET_40K_DISCOUNT'}
        for amount,name in variant.items():
            with self.subTest(amount=amount):
                old={x['persona_id']:x for x in rows if x['variant']==name}
                got=S.run_request(self.req(amount))
                self.assertEqual(len(old),11)
                for customer in got['customers']:
                    expected=old[customer['persona_id']]
                    self.assertEqual(customer['scenario_choice']['offer_id'],expected['winner_offer'])
                    self.assertAlmostEqual(customer['scenario_choice']['score'],float(expected['winner_score']),places=4)
    def test_repeat_deterministic(self):
        a=S.run_request(self.req(20000)); b=S.run_request(self.req(20000))
        self.assertEqual(a,b)
    def test_discount_party_unit_is_converted(self):
        a=S.run_request(self.req(10000))
        r=self.req(20000);r['offer_overrides']['THE_BUFFET']={'discount_amount':20000,'discount_unit':'per_party'}
        b=S.run_request(r)
        self.assertEqual([x['scenario_choice'] for x in a['customers']],[x['scenario_choice'] for x in b['customers']])
        buffet=next(x for x in b['eligibility'] if x['offer_id']=='THE_BUFFET')
        self.assertEqual(buffet['override_price_calculation']['discount_effective_krw_per_person'],10000.0)
        self.assertEqual(buffet['override_price_calculation']['discount_effective_krw_for_party'],20000.0)
    def test_expired_offer_ineligible_and_zero_candidates(self):
        r=self.req();r['simulation_date']='2026-10-31';r['start_time']='18:30';r['is_public_holiday']=False
        got=S.run_request(r)
        rows={x['offer_id']:x for x in got['eligibility']}
        self.assertEqual(rows['GEUMRYONG']['eligibility_status'],'INELIGIBLE')
        self.assertEqual(rows['THE_BUFFET']['eligibility_status'],'INELIGIBLE')
        self.assertEqual(got['experiment']['run_status'],'NO_ELIGIBLE_OFFERS')
    def test_missing_reservation_assumption_blocks_verified_offers(self):
        r=self.req();r['reservation_assumption']=False
        got=S.run_request(r); rows={x['offer_id']:x for x in got['eligibility']}
        self.assertEqual(rows['GEUMRYONG']['eligibility_status'],'INELIGIBLE')
        self.assertIn('reservation_not_assumed_available',rows['GEUMRYONG']['reasons'])
    def test_seat_condition_filters_geumryong(self):
        r=self.req();r['seat_type']='private_room';got=S.run_request(r)
        rows={x['offer_id']:x for x in got['eligibility']}
        self.assertEqual(rows['GEUMRYONG']['eligibility_status'],'INELIGIBLE')
        self.assertIn('THE_BUFFET',[x['offer_id'] for x in got['scenario']['customers'][0]['candidates']])
    def test_partial_pizzahill_not_scored(self):
        got=S.run_request(self.req())
        row=next(x for x in got['eligibility'] if x['offer_id']=='PH_COUPLE_SET')
        self.assertEqual(row['eligibility_status'],'INELIGIBLE')
        self.assertNotIn('PH_COUPLE_SET',got['experiment']['selected_offer_ids'])
    def test_child_buffet_price_is_insufficient_data(self):
        r=self.req();r['party_composition']={'adults':1,'children':1}
        got=S.run_request(r); row=next(x for x in got['eligibility'] if x['offer_id']=='THE_BUFFET')
        self.assertEqual(row['eligibility_status'],'INSUFFICIENT_DATA')
        self.assertIn('child_price_or_adult_child_composition_unverified',row['reasons'])
    def test_nonstaying_excludes_room_service(self):
        catalog=S._load_catalog(); r=self.req();r['stay_status']='non_staying'
        room=next(x for x in catalog['offers'] if x['offer_id']=='RS_CLUB_SANDWICH')
        answer=check_offer(room,r,allow_scenario=False,reservation_confirmed=True)
        self.assertEqual(answer['status'],'INELIGIBLE')
        self.assertIn('stay_required',answer['reasons'])
    def test_no_private_paths_or_text_in_output(self):
        results=list((ROOT/'results').glob('*.json'))
        data='\n'.join(p.read_text(encoding='utf-8') for p in results)+'\n'+json.dumps(S.run_request(self.req(20000)),ensure_ascii=False)
        for forbidden in ('/private/tmp','/Users/','Application Support','turn_personas_ext.local.json','review_text','source_gist'):
            self.assertNotIn(forbidden,data)
    def test_narrow_margin_flag_is_diagnostic(self):
        got=S.run_request(self.req(20000))
        row=next(x for x in got['scenario']['customers'] if x['persona_id']=='blog42')
        self.assertEqual(row['margin_diagnostic'],'NARROW_MARGIN')
        self.assertAlmostEqual(row['margin'],0.007,places=3)
    def test_input_hash_and_score_only_changes_exposed(self):
        a=S.run_request(self.req(0)); b=S.run_request(self.req(10000))
        self.assertNotEqual(a['experiment']['scenario_input_sha256'],b['experiment']['scenario_input_sha256'])
        self.assertTrue(any(x['score_changed_without_choice_change'] for x in b['customers']))
    def test_price_and_discount_overrides_cannot_double_apply(self):
        r=self.req();r['offer_overrides']={'THE_BUFFET':{'discount_amount':10000,'discount_unit':'per_person','price_amount':188000,'price_unit':'per_person'}}
        with self.assertRaisesRegex(ValueError,'choose_price_or_discount_override'): S.run_request(r)
    def test_party_size_and_adult_composition_are_used(self):
        r=self.req();r['party_size']=3;r['party_composition']={'adults':3,'children':0}
        got=S.run_request(r)
        self.assertEqual(got['experiment']['run_status'],'COMPLETED')
        self.assertTrue(all(c['scenario_choice']['price_pp_krw']>0 for c in got['customers']))
    def test_per_party_price_validation(self):
        r=self.req();r['offer_overrides']={'THE_BUFFET':{'price_amount':300000,'price_unit':'per_party'}}
        result=S.run_request(r)
        self.assertEqual(result['experiment']['run_status'],'COMPLETED')

if __name__=='__main__': unittest.main()
