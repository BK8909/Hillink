"""운영 월드 V1.1 엔진 확장 — 명시적 재방문 거부(7 · 8차 · V1 엔진 파일 수정 없음 · 이 문맥 안에서만 적용)

V1 의 업장 '가격 가치 유보' 항은 고정 감점(−0.5 ~ −1.0)이라, 같은 방문의 조망 · 메뉴 기호 같은 긍정 근거가 더 크면
작성자가 '다시 오지 않겠다'고 명시한 업장을 그대로 다시 고른다(A02 64편 · 기본 조건에서 확인).
작성자는 그 긍정 경험까지 이미 따져 본 뒤 거부했으므로, 그 업장에 대한 개인적 끌림(개인 근거 항의 양수 합)을 상쇄한다.

8차 수정 — '할인이 있으면 절반' 규칙(7차 · 가정값 0.5)을 없앴다. A02 는 20% 카드 할인을 받고 실제 지불한 뒤에도 거부했다.
이제 상쇄 비율은 '새 조건이 실제로 낸 1인 금액보다 얼마나 싼가'로 정한다:
    완화 = max(0, (실지출 1인 − 새 조건 1인 지불액) ÷ 실지출 1인)   (0 ~ 1)
    상쇄 = 개인적 끌림 × (1 − 완화)
  - 새 조건이 실지출보다 비싸거나 같으면 완화 0 → 거부가 그대로
  - 실지출보다 싸진 만큼만 완화(예: 실지출 67,600원 · 새 지불 46,000원이면 32% 완화) · 무료면 완전 완화(그래도 V1 가치 유보 감점은 남음)
  - 실지출을 원문에서 찾지 못하면 그 업장의 정가(할인 전)를 기준으로 쓴다
새 상수는 없다. 메뉴 구성의 차이(같은 업장의 다른 세트 · 신메뉴)는 월드에 없어 반영하지 않는다(한계).
"""
from __future__ import annotations

from contextlib import contextmanager

from operator_choice.operator_world_v1 import engine as EN


def relief(o: dict, ref: dict) -> float:
    base = ref.get("experienced_pp_krw") or o["price_pp_krw"]
    new = EN.out_of_pocket(o)
    return max(0.0, min(1.0, (base - new) / base)) if base else 0.0


@contextmanager
def v11_engine():
    orig = EN._score

    def _score11(o, t, state, visit, traits, world):
        terms = orig(o, t, state, visit, traits, world)
        refs = [v for v in traits.get("venues", {}).get(o["venue"], []) if v.get("kind") == "refuse"]
        if refs:
            pull = sum(x["value"] for x in terms if x["facet"] and x["value"] > 0)
            r = max(relief(o, ref) for ref in refs)
            ids = [i for ref in refs for i in ref["fact_ids"]]
            base = refs[0].get("experienced_pp_krw")
            note = (f"실지출 1인 {base:,}원 대비 새 지불 {EN.out_of_pocket(o):,.0f}원 → 완화 {r:.0%}" if base else f"실지출 미확인 · 정가 기준 완화 {r:.0%}") + " · " + refs[0]["gist"][:50]
            terms.append(EN._term("명시적 재방문 거부(같은 업장)", -pull * (1 - r), "post_appraisal", ids, note))
        return terms

    EN._score = _score11
    try:
        yield
    finally:
        EN._score = orig
