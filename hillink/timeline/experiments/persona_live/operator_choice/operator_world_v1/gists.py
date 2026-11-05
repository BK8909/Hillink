"""근거 요지 사전 — V4.1 특성 키(individual_features) → 비식별 한국어 요지.

출처: `author_method_v4_1_artifacts/blog41_profile.md` · `blog42_profile.md` 의 비식별 요약(Codex 개발 대조 · 경수 검수 전).
원문 인용·계정·URL·정확한 위치는 제한 원장에만 있다. 여기 요지는 화면과 이유 문장에 쓰는 공유용 설명이며 원문 그 자체가 아니다.
키가 없으면 특성 키를 그대로 보여 준다(요지를 지어내지 않는다).
"""

GISTS = {
    # blog41
    "ad_spread_trial": "광고를 보고 스프레드 제품을 시도해 봄(재구매는 안 함)",
    "advert_seen_dessert_trial": "다른 호텔의 디저트를 광고에서 보고 식후에도 주문해 봄",
    "bar_ambience_and_nonalcoholic": "바의 분위기를 즐기며 무알코올 음료를 주문함",
    "buffet_food_exploration": "뷔페에서 여러 메뉴를 두루 맛봄",
    "buffet_voucher_value": "뷔페 식사권의 가격 대비 가치는 유보적으로 평가함(이용 후)",
    "card_discount_and_coupon": "카드 할인·쿠폰을 실제로 활용함",
    "chef_course_consumed": "셰프 코스 식사를 실제로 이용함",
    "chef_course_reservation": "셰프를 만나는 코스 식사를 직접 예약함",
    "gym_shoe_rental": "호텔 피트니스를 신발 대여까지 해서 실제 이용함",
    "limited_goods_wait_purchase": "한정 상품을 기다려서 구매함",
    "limited_swimcap_after_ad": "광고를 본 뒤 한정판 수영모를 구매함(디자인·한정 매력)",
    "lodging_voucher_choice": "숙박 바우처를 비교해 선택함",
    "low_alcohol_self_description": "스스로 술이 약하다고 적음(낮은 음주 내성)",
    "meal_discount_applied": "피자힐에서 투숙객 할인을 적용받음",
    "new_hotel_stay": "새로 생긴 호텔에 투숙해 봄",
    "night_view_footbath": "스카이야드에서 야경을 보며 족욕을 이용함",
    "pizza_garlic_preference": "피자·마늘·갈릭 소스 풍미를 구체적으로 좋아함",
    "pizza_value_qualified": "피자힐은 할인 뒤에도 가격 대비 만족이 유보적(이용 후 평가)",
    "pool_decor_planning": "수영장의 장식·분위기를 미리 계획해 즐김",
    "pool_visit_not_swimming": "수영장에 갔지만 수영 자체는 하지 않음(물을 무서워함)",
    "poster_changed_booking": "증정품 일정에 맞춰 예매를 바꿈",
    "pre_perfume_bundle_choice": "처음 사는 향 제품은 대용량 대신 작은 구성을 고름(구매 전 비교)",
    "pre_sportswear_value": "운동복은 자기 가격 기준으로 고름(구매 전 비교)",
    "pre_transport_price_increase": "요금 인상 전에 교통편을 미리 예매함",
    "room_external_food": "호텔 객실에서 외부 음식(치킨)을 시켜 먹음",
    "sauna_goods_purchase": "사우나 관련 상품을 구매함",
    "sauna_market_same_purchase": "같은 사우나 상품을 다른 곳에서도 구매함",
    "shellfish_preference_exceptions": "조개류는 대체로 피하지만 좋아한 예외 메뉴가 있음",
    "spread_no_repurchase": "시도한 스프레드는 다시 사지 않음",
    "swimcap_not_swim_preference": "수영모 구매가 수영 선호를 뜻하지는 않음(스스로 밝힘)",
    "travel_bag_same_purchase": "같은 여행 가방을 다시 구매함",
    "travel_bag_store_choice": "여행 가방을 매장을 비교해 구매함",
    "two_flavors_and_sauces": "피자힐에서 두 가지 맛과 소스를 함께 주문함",
    "warm_shallow_pool": "따뜻하고 얕은 풀을 좋게 평가함(물이 무서운 사람에게 적합)",
    "wine_and_friend_trip": "친구와의 여행에서 와인을 준비해 마심",
    # blog42
    "annual_ice_plan_not_purchase": "올해 빙수는 계획만 적음(실제 구매 아님)",
    "annual_ice_review_references": "매년 빙수 안내 글에 과거 경험을 반복 인용함",
    "bakery_guest_discount": "호텔 베이커리에서 투숙객 할인을 받음",
    "breakfast_coupon_used": "별도 아침 식사 쿠폰을 사용함",
    "brunch_rest_purpose": "쉬려고 시간을 따로 내어 브런치를 감",
    "day_night_footbath": "낮과 밤 두 번 족욕을 이용함",
    "earlier_menu_different": "전에 먹은 것과 다른 메뉴를 고름",
    "early_breakfast_routine": "조식에 맞춰 일찍 움직임",
    "forest_shuttle_walk": "포레스트 파크를 셔틀·산책으로 이용함",
    "functional_shaver_replacement": "오래 쓴 생활 가전을 비교 후 교체함(기능적 구매)",
    "garden_break_habit": "백화점 정원에서 쉬는 습관",
    "garden_tea_break": "정원과 차를 결합해 쉼",
    "hotel_ice_card_topup": "호텔 빙수를 카드 혜택과 추가 결제로 이용함",
    "hotel_ice_different": "다른 호텔 빙수도 비교해 이용함",
    "icecream_card_benefit": "아이스크림을 카드 혜택으로 이용함",
    "lounge_food_then_gym": "라운지 음식을 먹고 헬스장을 이용함",
    "matcha_egg_tart_preference": "말차·에그타르트를 구체적으로 좋아함",
    "new_menu_after_previous": "익숙한 식당에서 새 메뉴를 시도함",
    "popup_food_trial": "팝업 음식을 시도해 봄",
    "prior_hotel_ices": "과거 여러 호텔 빙수 경험",
    "recovery_service_a": "회복(마사지) 서비스 이용 ①",
    "recovery_service_b": "회복(마사지) 서비스 이용 ②",
    "recovery_service_c": "회복(마사지) 서비스 이용 ③",
    "sale_food_disappointment": "할인 구매한 음식의 상태에 실망함(이용 후 평가)",
    "sale_food_purchase": "할인 식재료를 가격 확인 후 구매함",
    "signature_drink_curiosity": "시그니처 음료가 궁금해 주문함",
    "voucher_choice_not_brunch": "연간 바우처의 대안을 비교해 교환함",
}

# 패턴 축 → 사람이 읽는 이름
PATTERN_KO = {
    "novelty_trial": "새 경험 시도", "benefit_use": "혜택 활용", "food_exploration": "음식 탐색",
    "space_atmosphere": "공간·분위기 경험", "seasonal_promotion_response": "시즌·프로모션 반응",
    "voluntary_ad_response": "광고를 보고 자발 구매", "prepurchase_value": "구매 전 가치 비교",
    "premium_experience": "프리미엄 식음 경험", "warm_water_rest": "온수·족욕 휴식",
    "active_engagement": "운동 참여", "alcohol_experience": "와인·음주 경험", "food_specificity": "구체적 음식 기호",
    "practical_alternative": "실용적 식사 대안", "swimming_nonpreference": "수영 비선호",
    "low_alcohol_tolerance": "낮은 음주 내성", "post_value_appraisal": "이용 후 가격 가치 평가",
    "practical_repeat_use": "실용적 반복 이용", "recovery_service": "회복 서비스 이용",
    "breakfast_priority": "조식 우선", "functional_purchase": "기능적 구매", "trip_rest_context": "휴식 목적 방문",
    "sauna_related_goods": "사우나 관련 상품", "travel_convenience_purchase": "여행 편의 구매",
}


def gist(feature_key: str) -> str:
    return GISTS.get(feature_key, feature_key)
