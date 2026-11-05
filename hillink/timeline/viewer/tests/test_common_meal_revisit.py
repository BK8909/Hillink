"""Meal spacing is a physical consumption rule, not SKU identity or price."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import copy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hotel_ledger  # runtime import path
from operator_choice.autonomy_v1 import agent_day as AD, hotel_runtime as HR


def actor(food=None):
    return NS(food=[(1129, 'PIZZA_HILL')] if food is None else food,
              meals={'dinner': True}, meal_log=[dict(t=1039, slot='dinner', size='full')],
              hunger_e=0, loc='PIZZA_HILL', room='GRAND_ROOM', sc={'date':'2026-09-10'})


def test_meal_clock_uses_end_not_start_and_same_place_not_same_sku():
    a=actor();before=copy.deepcopy(vars(a))
    assert AD.meal_revisit_reasons(a,1129,'PIZZA_HILL')==['RECENT_MEAL','SAME_VENUE_RECENT_MEAL']
    assert AD.meal_revisit_reasons(a,1218,'GEUMRYONG')==['RECENT_MEAL']
    assert AD.meal_revisit_reasons(a,1219,'GEUMRYONG')==[]
    assert AD.meal_revisit_reasons(a,1368,'PIZZA_HILL')==['SAME_VENUE_RECENT_MEAL']
    assert AD.meal_revisit_reasons(a,1369,'PIZZA_HILL')==[]
    assert vars(a)==before


def test_new_day_has_no_same_day_food_but_can_retain_prior_visit_memory():
    a=actor([]);a.visit_history={'prior_meals':[{'date':'2026-09-10','venue_id':'PIZZA_HILL'}]}
    assert AD.meal_revisit_reasons(a,720,'PIZZA_HILL')==[]


def catalog_world(a,t):
    # Real adapter adds these two different SKUs after native candidate filtering.
    # Mock only quote/offer construction; the actual adapter must apply the gate.
    def quote(a,v,*args):return ([{'sku_id':v+'-NEW','venue_id':v}],[])
    def offer(a,c,*args):return dict(id='HC_'+c['sku_id'],venue=c['venue_id'],kind='restaurant',hc_contract=True,food={'meal_fraction':1})
    native={'offers':[dict(id='WINE_FAIR',venue='WINE_FAIR',kind='event'),dict(id='CARD_GOLDEN',venue='PIZZA_HILL',kind='event',food={'meal_fraction':.4})],
            'hotel_catalog_exclusions':[dict(venue_id='NATIVE',reasons=['NATIVE_REASON'])]}
    with patch.object(AD,'engine_world_for',return_value=copy.deepcopy(native)),patch.object(HR.H,'enabled',return_value=True),patch.object(HR.H,'options',return_value={}),patch.object(HR,'dinner_venues',return_value={'PIZZA_HILL','GEUMRYONG'}),patch.object(HR,'quote',side_effect=quote),patch.object(HR,'offer',side_effect=offer),patch.object(HR.SP,'travel_min',return_value=0),patch.object(AD,'_engine_closure_interval',return_value=False),HR.install(NS()):
        return AD.engine_world_for(a,NS(),t)


def test_catalog_cannot_reintroduce_other_sku_or_other_restaurant_after_meal():
    w=catalog_world(actor(),1129)
    assert [o['id'] for o in w['offers']]==['WINE_FAIR','CARD_GOLDEN']  # event tasting untouched
    by={r['venue_id']:r for r in w['hotel_catalog_exclusions']}
    assert by['NATIVE']['reasons']==['NATIVE_REASON']
    assert by['PIZZA_HILL']['sku_id']=='PIZZA_HILL-NEW'
    assert by['PIZZA_HILL']['reasons']==['RECENT_MEAL','SAME_VENUE_RECENT_MEAL']
    assert by['GEUMRYONG']['reasons']==['RECENT_MEAL']
    assert by['PIZZA_HILL']['meal_state']['hunger_e']==0
    assert by['PIZZA_HILL']['meal_state']['meals']['dinner'] is True


def test_elapsed_meal_and_new_day_catalogs_are_still_available():
    assert {o['venue'] for o in catalog_world(actor(),1369)['offers']} >= {'PIZZA_HILL','GEUMRYONG'}
    assert {o['venue'] for o in catalog_world(actor([]),1039)['offers']} >= {'PIZZA_HILL','GEUMRYONG'}


def test_food_sku_never_inherits_event_template_from_same_venue():
    a=actor([]);a.N=2
    contract=dict(venue_id='PIZZA_HILL',sku_id='PIZZA',label='fixture pizza',service_period='dinner',unit_price_krw=69000,price_status='MODEL',components=[dict(role='MAIN',source_sha256='source')])
    event=AD.WD.offer('CARD_EVENT','fixture event','event','PIZZA_HILL',price=0,meal_fraction=.4)
    with patch.object(HR.H,'sessions',return_value=[(960,1320)]),patch.dict(AD.ENGINE_LOC,{}),patch.dict(AD.ENGINE_DOMAIN,{}),patch.dict(AD.VENUE_KO,{}):
        offer=HR.offer(a,contract,1039,90,{'offers':[event]})
    assert offer['kind']=='restaurant'
    assert offer['food']['meal_fraction']==1
    assert event['kind']=='event' and event['food']['meal_fraction']==.4
