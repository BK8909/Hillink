"""Real catalogue contracts, pre-choice amounts, fullness and no forced upsell."""
from pathlib import Path
from types import SimpleNamespace as NS
import copy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hotel_ledger
from operator_choice.autonomy_v1 import hotel_catalog as H, hotel_runtime as HR, meal_basket as B


def actor(n=2, hunger=1, meals=None):
    return NS(N=n, C={}, sc={'date':'2026-09-10'}, hunger_e=hunger, meal_log=meals or [])


def order(a, sku, quantity=None):
    p=H.BY[sku]
    return H.compose([H.component(p, H.quantity(p,a) if quantity is None else quantity,a)],a,'dinner')


def test_real_pizza_pasta_and_couple_set_keep_original_prices_and_order_identity():
    a=actor();base=[order(a,k) for k in ['HC-MENU-091','HC-MENU-096','HC-MENU-084']]
    before=copy.deepcopy(base);rows=B.alternatives(base,a,'dinner',H)
    mixed=next(c for c in rows if c['meal_basket']['kind']=='MIXED_REGISTERED_MENUS' and len(c['components'])==2)
    assert mixed['unit_price_krw']==73000+49000
    assert [p['billing_quantity'] for p in mixed['components']]==[1,1]
    assert mixed['meal_basket']['meal_equivalents']==3
    assert mixed['meal_basket']['meal_fraction']==1
    assert mixed['meal_basket']['excess_capacity']==1
    for old in before:
        same=next(c for c in rows if c['sku_id']==old['sku_id'])
        assert same['components']==old['components'] and same['unit_price_krw']==old['unit_price_krw']
    couple=next(c for c in rows if c['components'][0]['sku_id']=='HC-MENU-084')
    assert couple['unit_price_krw']==184000
    assert HR.choice_attributes(couple)['menu_tags']==['pizza','pasta','salad']
    assert HR.choice_attributes(couple)['course_menu'] is False


def test_light_order_requires_prior_food_and_reduces_fraction_not_unit_price():
    a=actor(hunger=.4,meals=[{'t':800,'slot':'lunch','size':'full'}])
    rows=B.alternatives([order(a,'HC-MENU-096')],a,'dinner',H)
    light=next(c for c in rows if c['meal_basket']['kind']=='LIGHT_AFTER_PRIOR_MEAL')
    assert light['unit_price_krw']==49000
    assert light['meal_basket']['meal_fraction']==.5
    a.meal_log=[]
    assert len(B.alternatives([order(a,'HC-MENU-096')],a,'dinner',H))==1


def test_person_courses_and_child_contracts_are_not_split_or_forced():
    a=actor();a.C={'kids':True};a.N=3
    base=[order(a,'HC-MENU-091'),order(a,'HC-MENU-096')]
    assert len(B.alternatives(base,a,'dinner',H))==len(base)
    for sku in ['HC-MENU-134','HC-MENU-189','HC-MENU-147']:
        assert not B.expandable(H.BY[sku])
    assert B.expandable(H.BY['HC-MENU-150'])


def test_mixed_orders_priced_before_scoring_and_set_drinks_not_added_again():
    a=actor();a.sc['catalog_options']={'price_overrides':{'HC-MENU-091':100000},'discount_percent':{'HC-MENU-091':20}}
    rows=B.alternatives([order(a,'HC-MENU-091'),order(a,'HC-MENU-096'),order(a,'HC-MENU-084')],a,'dinner',H)
    mixed=next(c for c in rows if c['meal_basket']['kind']=='MIXED_REGISTERED_MENUS')
    assert mixed['unit_price_krw']==129000 and mixed['discount_krw']==20000
    assert H.charge(mixed)['krw']==sum(p['billing_quantity']*p['unit_price_krw'] for p in mixed['components'])
    couple=next(c for c in rows if c['components'][0]['sku_id']=='HC-MENU-084')
    assert len(couple['components'])==1
    assert couple['components'][0]['included_components']['drinks']==2


def test_unknown_portions_explicitly_labeled_not_measured_fullness():
    a=actor();c=order(a,'HC-MENU-091');c['components'][0]['billing_unit']='unknown'
    B.metadata(c,a)
    assert c['meal_basket']['meal_equivalents'] is None
    assert c['meal_basket']['limitation']=='PORTION_UNKNOWN_LEGACY_FULL_MEAL_ASSUMPTION'


def test_six_venues_quote_only_eligible_components_and_keep_buffet_admissions():
    a=actor();a.B='GRAND';a.stay=True;a.checked_in=True;a.checked_out=False
    a.club=True;a.pid='TEST';a.vs={'nights':1};a.phase='checkin';a.visit_history={}
    for venue in B.VENUES:
        rows,_=H.orders(a,venue,1080,90,'dinner')
        assert rows,venue
        for c in rows:
            assert c['unit_price_krw']==sum(p['unit_price_krw']*p['billing_quantity'] for p in c['components'])
            assert 0<c['meal_basket']['meal_fraction']<=1
            for p in c['components']:
                assert not H.eligible(H.BY[p['sku_id']],a,1080,90,'dinner',True)
                assert p['billing_quantity']>=p['minimum_quantity']
        if venue=='THE_BUFFET':
            assert all(len(c['components'])==1 and c['components'][0]['billing_quantity']==2 for c in rows)
        else:
            assert any(c['meal_basket']['kind']=='MIXED_REGISTERED_MENUS' for c in rows)


def test_light_basket_fraction_reaches_offer_and_consumption_memory():
    from operator_choice.autonomy_v1 import ledger as L
    from unittest.mock import patch
    a=actor(hunger=.4,meals=[{'t':800,'slot':'lunch','size':'full'}]);a.meals={}
    c=next(c for c in B.alternatives([order(a,'HC-MENU-096')],a,'dinner',H) if c['meal_basket']['kind']=='LIGHT_AFTER_PRIOR_MEAL')
    with patch.dict(HR.AD.ENGINE_LOC,{}),patch.dict(HR.AD.ENGINE_DOMAIN,{}),patch.dict(HR.AD.VENUE_KO,{}):
        o=HR.offer(a,c,1080,90,{'offers':[]})
    assert o['food']['meal_fraction']==.5
    assert L.record_meal(a,o['id'],'restaurant','식사',1080,o['food']['meal_fraction'])=='dinner'
    assert a.meal_log[-1]['size']=='light'
