"""V19LS one-time meal quantity review (no key, no cost).

A customer with a past 'not enough food' record who picks a meal whose usual-portion equivalents are at or below
the party size, without citing that record or explaining the quantity, is asked once to reconsider. The second
answer stands whatever quantity it keeps: nothing forces a larger order. The stored A05 LIVE dinner (pizza L for
three, record F25 not cited) is the pattern this reproduces; whether the model then changes its order needs LIVE.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'experiments/persona_live'))
from operator_choice.autonomy_v1 import ls_stability as L  # noqa: E402

LEAN = dict(visit=dict(party_size=3), personal=dict(
    citable_fact_ids=['X-F25', 'X-F02'],
    records=[dict(fact_ids=['X-F25'], stance='서술', flags=['양 부족'], about=['meal:PIZZA_HILL'], summary='세 명이 피자 한 판으로는 양이 부족했다고 적음'),
             dict(fact_ids=['X-F02'], stance='긍정', about=['meal:PIZZA_HILL'], summary='피자 맛을 좋게 평가')]),
    candidates=[dict(action_id='meal:PIZZA_HILL', label='피자힐', basket_groups=[dict(label='피자', options=[
        dict(basket_id='meal:PIZZA_HILL#1', items=[dict(label='마르게리타 피자 L', quantity=1)], meal_equivalents=3, total_krw=79000),
        dict(basket_id='meal:PIZZA_HILL#14', items=[dict(label='마르게리타 피자 L', quantity=1), dict(label='파스타', quantity=1)], meal_equivalents=4, total_krw=127000)])])])


def answer(basket, cited=(), reason='저녁으로 피자를 고릅니다.', quantity='세 명이 나눠 먹습니다.'):
    return dict(selected_action_id='meal:PIZZA_HILL', selected_basket_id=basket, reason=reason, supporting_fact_ids=list(cited), counterevidence_fact_ids=[],
                meal_assessment=dict(kind='FULL_MEAL', modeled_diners=3, sharing_plan='나눠 먹음', quantity_reason=quantity, expected_satiety='COMFORTABLE'))


def test_asks_once_when_the_shortfall_record_is_ignored():
    with pytest.raises(ValueError, match=L.MEAL_QUANTITY_REVIEW):
        L.meal_quantity_review(answer('meal:PIZZA_HILL#1'), LEAN, 3, None)


def test_second_answer_stands_even_with_the_same_quantity():
    L.meal_quantity_review(answer('meal:PIZZA_HILL#1'), LEAN, 3, dict(reason=L.MEAL_QUANTITY_REVIEW + ': ...'))


@pytest.mark.parametrize('ans', [
    answer('meal:PIZZA_HILL#1', cited=['X-F25']),                                    # record weighed and cited
    answer('meal:PIZZA_HILL#1', quantity='지난번엔 양이 부족했지만 늦은 점심을 먹어 한 판이면 됩니다.'),   # explained
    answer('meal:PIZZA_HILL#14'),                                                    # above the party size
    dict(answer('meal:PIZZA_HILL#1'), selected_basket_id=None),                      # no basket
])
def test_no_request_when_weighed_explained_or_larger(ans):
    L.meal_quantity_review(ans, LEAN, 3, None)


def test_no_shortfall_record_no_request():
    lean = dict(LEAN, personal=dict(LEAN['personal'], records=[LEAN['personal']['records'][1]]))
    L.meal_quantity_review(answer('meal:PIZZA_HILL#1'), lean, 3, None)


def test_quantity_summary_records_the_final_choice():
    s = L.quantity_summary(answer('meal:PIZZA_HILL#14', cited=['X-F25']), LEAN, 3)
    assert s == dict(equivalents=4, party=3, cited=['X-F25'], quantity_reason='세 명이 나눠 먹습니다.')
