"""Source/SKU/quantity contracts, not live behavior or full-menu approval."""
import copy
from test_agent_world_choices import A,C,actor,plan


def test_page27_variants_are_additive_and_do_not_manufacture_serving_counts():
    rows=[p for p in A.H.DATA['products'] if p['sku_id'].startswith('HC-PDF-20261102-GEUMRYONG-')]
    assert len(rows)==8
    assert {p['sku_id'] for p in rows}.isdisjoint({p['sku_id'] for p in A.H.BASE_DATA['products']})
    assert all(p['official_source']['page']==27 and p['source_servings'] is None for p in rows)
    assert A.H.BY['HC-PDF-20261102-GEUMRYONG-46-PORK']['unit_price_krw']==105000
    assert A.H.BY['HC-PDF-20261102-GEUMRYONG-46-BEEF']['unit_price_krw']==145000
    assert A.H.BY['HC-PDF-20261102-GEUMRYONG-45-S']['unit_price_krw']==85000
    assert A.H.BY['HC-PDF-20261102-GEUMRYONG-45-L']['unit_price_krw']==115000


def test_shared_dish_reaches_agent_and_exact_order_but_not_backdated_research():
    a,w=actor(1080,False);a.food=[];sku='HC-PDF-20261102-GEUMRYONG-46-PORK'
    assert any('BEFORE_REVIEWED_MENU' in r for r in A.H.eligible(A.H.BY[sku],a,1080,90,'dinner',True))
    a.sc['date']='2026-11-04'
    with C.install(a.sc['date']):
        choices,menus,_,world=A.action_space(a,w,a.t)
        row=next(p for p in menus['meal:GEUMRYONG'] if p['sku_id']==sku)
        assert row['serving_estimate']['meal_equivalents_per_sale_unit'] is None
        p=plan(choices['meal:GEUMRYONG'])
        before=copy.deepcopy(p['items']);p['items'].append(dict(sku_id=sku,quantity=1));p['order_total_krw']+=105000
        result=A.validate_plan(a,p,choices,menus,[])['contract']
        assert A.H.charge(result)['krw']==p['order_total_krw']
        assert next(x for x in result['components'] if x['sku_id']==sku)['billing_quantity']==1
        assert p['items'][:-1]==before
