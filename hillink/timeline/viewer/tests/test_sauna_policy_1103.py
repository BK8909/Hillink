"""Model contracts from the user-supplied official 11/03 guidance, no private inputs."""
import sys,copy
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visit_run
from operator_choice.autonomy_v1 import hotel_catalog as H,sauna_policy as S,facility_rules as F

def actor(b='VISTA',age=None,room=None,n=2,date='2025-12-19'):
    party={'adult_count':2,'children':[{'age_months':age}]} if age!='NONE' else {'adult_count':n,'children':[]}
    return SimpleNamespace(B=b,N=3 if age!='NONE' else n,pid='P',C={'kids':age!='NONE'},stay=True,checked_in=True,checked_out=False,vs={'party_composition':party,'nights':2},sc={'date':date,'catalog_options':{'room_products':{'P':room}} if room else {}},visit_history={})

def quote(a,sku='HC-MENU-232'):
    p=H.BY[sku]
    assert not H.eligible(p,a,720,60,'activity')
    return H.compose([H.component(p,H.quantity(p,a),a)],a,'activity')

@pytest.mark.parametrize('building,sku,rate',[('GRAND','HC-MENU-231',20000),('DOUGLAS','HC-MENU-231',20000),('VISTA','HC-MENU-232',55000),('GRAND','HC-MENU-232',66000),('DOUGLAS','HC-MENU-232',66000)])
def test_facility_and_guest_rate(building,sku,rate):
    c=quote(actor(building,age='NONE'),sku)
    assert c['unit_price_krw']==2*rate
    p=c['components'][0];assert p['historical_tariff_confirmed'] is False
    assert p['price_status']=='2026_REFERENCE_APPLIED_TO_OTHER_YEAR_SCENARIO'
    assert p['party_total_people']==p['sauna_eligible_people']==2

@pytest.mark.parametrize('age',[None,24,60,96])
def test_children_never_billed_as_adult_sauna_users(age):
    c=quote(actor(age=age));assert c['unit_price_krw']==110000
    assert c['components'][0]['billing_quantity']==2
    assert c['components'][0]['party_composition']['children'][0]['age_months']==age

def test_vista_guest_grand_prohibited_and_gender_not_inferred():
    a=actor(age='NONE');assert 'SAUNA_CROSS_BUILDING_NOT_AUTHORIZED' in H.eligible(H.BY['HC-MENU-231'],a,720,60,'activity')
    assert S.DATA['gender_access']=='UNCONFIRMED_NO_GENDER_EXCLUSION'

@pytest.mark.parametrize('b,day',[('VISTA','2025-12-10'),('GRAND','2025-12-16')])
def test_recurring_closures_apply_actual_visit_year(b,day):
    a=actor(b,date=day,age='NONE');assert F.block(a,'sauna')

@pytest.mark.parametrize('room,b,people',[('HC-MENU-007','GRAND',2),('HC-MENU-019','DOUGLAS',1),('HC-MENU-028','VISTA',2),('HC-MENU-035','VISTA',3)])
def test_included_contract_uses_wellness_facility_once(room,b,people):
    a=actor(b,age='NONE',n=people,room=room,date='2026-10-26');assert S.facility(a)=='VISTA_SAUNA'
    c=H.entitlement(a,quote(a));assert c['hc_included'];assert H.charge(c,included=True)['krw']==0
    a.visit_history={'hotel_entitlement_usage':{c['hotel_entitlement_key']:1}}
    after=H.entitlement(a,quote(a));assert not after.get('hc_included');assert after['unit_price_krw']>0

def test_package_overage_and_solo_two_uses():
    a=actor(age='NONE',n=3,room='HC-MENU-028',date='2026-10-26');c=H.entitlement(a,quote(a));assert c['unit_price_krw']==55000
    a=actor(age='NONE',n=1,room='HC-MENU-028',date='2026-10-26')
    for _ in range(2):
        c=H.entitlement(a,quote(a));assert c['hc_included'];a.visit_history.setdefault('hotel_entitlement_usage',{})[c['hotel_entitlement_key']]=1
    assert not H.entitlement(a,quote(a)).get('hc_included')

def test_no_current_package_benefit_on_2025_visit():
    a=actor(age='NONE',room='HC-MENU-028');assert not H.entitlement(a,quote(a)).get('hc_included')

def test_explicit_adult_participation_cannot_exceed_eligible_people():
    a=actor(age=60);a.sc['catalog_options']['purchase_orders']={'P':[{'date':a.sc['date'],'venue_id':'SAUNA','service_period':'activity','items':[{'sku_id':'HC-MENU-232','quantity':3}]}]}
    with pytest.raises(ValueError,match='SAUNA_PARTICIPANTS'):H.explicit_order(a,'SAUNA','activity',720,60)
