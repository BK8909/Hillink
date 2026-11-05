"""Official with-meal price cannot receive a second discount via either input."""
import json
from pathlib import Path
import pytest
from test_agent_world_choices import A


@pytest.mark.parametrize('sku,amount',[
    ('HC-SRC-PIZZA-AMERICANO-WITH-MEAL',10000),
    ('HC-SRC-PIZZA-ICED-AMERICANO-WITH-MEAL',12000),
])
def test_meal_discount_is_already_included_and_not_stackable(sku,amount):
    p=A.H.BY[sku]
    assert A.H.price(p)['unit_price_krw']==amount
    assert p['reviewed_sale_condition_source']['page']==16
    assert not A.H.discount_allowed(p)
    for options in ({'discount_percent':{sku:20}},{'price_overrides':{sku:amount-1}}):
        with pytest.raises(ValueError,match='HC_SOURCE_DISCOUNT_NOT_ALLOWED'):
            A.H.validate(options,['A01'])
        # Direct quotes cannot bypass request validation.
        with pytest.raises(ValueError,match='HC_SOURCE_DISCOUNT_NOT_ALLOWED'):
            A.H.price(p,options)
    assert A.H.validate({'discount_percent':{sku:0}},['A01'])


def test_regular_pizza_discount_remains_supported_and_source_inputs_preserved():
    p=A.H.BY['HC-MENU-091']
    assert A.H.discount_allowed(p)
    assert A.H.price(p,{'discount_percent':{p['sku_id']:20}})['unit_price_krw']==round(p['unit_price_krw']*.8)
    source=json.loads(A.H.OC.PATH.read_text())
    original=next(p for p in source['products'] if p['sku_id']=='HC-SRC-PIZZA-AMERICANO-WITH-MEAL')
    assert original.get('discount_policy') is None


def test_editor_and_runtime_share_reviewed_discount_restrictions():
    editor=json.loads((Path(__file__).parents[1]/'static/sku_scenario_options.json').read_text())
    by={p['sku_id']:p for p in editor['products']}
    for sku in ('HC-SRC-PIZZA-AMERICANO-WITH-MEAL','HC-SRC-PIZZA-ICED-AMERICANO-WITH-MEAL'):
        assert by[sku]['discount_policy']==A.H.BY[sku]['discount_policy']
    assert editor['catalog_sha256']==A.H.SHA
