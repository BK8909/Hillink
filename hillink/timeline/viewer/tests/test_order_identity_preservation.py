"""An unrelated additive SKU must not reshuffle legacy scored alternatives."""
import copy
from unittest.mock import patch
from test_agent_world_choices import actor,C,A
H=A.H

def test_legacy_order_id_unchanged_without_falsifying_active_catalog_lineage():
 a,_=actor(1080,False)
 with C.install(a.sc['date']):
  parts=[H.component(H.BY['HC-MENU-091'],1,a)]
 original=copy.deepcopy(parts);original[0]['catalog_sha256']=H.PRE_REVIEWED_SHA
 quote=H.compose(parts,a,'dinner')
 assert quote['sku_id']=='HC-ORDER-'+H.digest(original)[:20]
 assert quote['catalog_sha256']==H.SHA and quote['components'][0]['catalog_sha256']==H.SHA
 other=copy.deepcopy(parts);other[0]['catalog_sha256']='unrelated-full-catalog-change'
 assert H.order_identity(other)==quote['sku_id']
 other[0]['billing_quantity']+=1;assert H.order_identity(other)!=quote['sku_id']
 other=copy.deepcopy(parts);other[0]['unit_price_krw']+=1000;assert H.order_identity(other)!=quote['sku_id']

def test_new_shared_product_identity_is_stable_but_quantity_price_are_not_erased():
 a,_=actor(1080,False);a.sc['date']='2026-11-05'
 parts=[H.component(H.BY['HC-PDF-20261102-GEUMRYONG-46-PORK'],1,a)];original=copy.deepcopy(parts)
 changed=copy.deepcopy(parts);changed[0]['catalog_sha256']='additional-menu-tomorrow'
 assert H.order_identity(parts)==H.order_identity(changed)
 changed[0]['unit_price_krw']=84000;assert H.order_identity(parts)!=H.order_identity(changed)
 assert parts==original

def test_existing_derived_pool_tariff_keeps_parent_order_identity():
 a,_=actor(1080,False)
 # The runtime derives a scenario tariff from a registered parent. It is not
 # an additive reviewed menu item, even though its ID is absent from BY.
 p=copy.deepcopy(H.BY['HC-MENU-235'])
 p.update(sku_id=p['sku_id']+'-VISTA-MODEL',pricing_parent_sku_id=p['sku_id'],unit_price_krw=20000)
 parts=[H.component(p,2,a)];before=copy.deepcopy(parts)
 before[0]['catalog_sha256']=H.PRE_REVIEWED_SHA
 assert H.order_identity(parts)=='HC-ORDER-'+H.digest(before)[:20]
 assert parts[0]['catalog_sha256']==H.SHA
