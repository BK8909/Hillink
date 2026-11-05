import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hotel_ledger as L
from test_sauna_policy_1103 import actor,H

def test_override_discount_reference_and_settlement_are_distinct():
    a=actor(age='NONE');a.sc['catalog_options']={'price_overrides':{'HC-MENU-142':30000},'discount_percent':{'HC-MENU-142':20}}
    p=H.component(H.BY['HC-MENU-142'],2,a);c=H.compose([p],a,'dinner');charged=H.charge(c)['sku_contract']
    row={'선택 SKU 계약':charged,'상태':'유료','_row_key':'parent','확인 메모':'','확정 결제액':48000}
    out=L.expand([row],{'parent':{}})[0];p=out['선택 SKU 계약']
    assert p['original_list_unit_price_krw']==30000
    assert p['price_trace']['catalog_unit_price_krw']==H.BY['HC-MENU-142']['unit_price_krw']
    assert p['unit_price_krw']==24000 and out['결제액']==48000 and p['discount_krw']==6000

def test_included_reference_not_overwritten_by_zero_split():
    a=actor(age='NONE',n=2,room='HC-MENU-028',date='2026-10-26')
    from test_sauna_policy_1103 import quote
    c=H.entitlement(a,quote(a));charged=H.charge(c,included=True)['sku_contract']
    row={'선택 SKU 계약':charged,'상태':'포함','_row_key':'parent','확인 메모':'','확정 결제액':0}
    out=L.expand([row],{'parent':{}})[0]
    assert out['결제액']==0 and out['선택 SKU 계약']['original_list_unit_price_krw']==55000
