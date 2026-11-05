"""근거 ↔ 성향(facet) ↔ 선택지 속성 연결표 (10/22 2차 · 강경수 1차 검수 반영)

V4.1 패턴은 '새 경험'에 여행 가방 매장 비교를, '공간·분위기'에 와인 여행 · 셰프 코스를 함께 묶어 두었다. 그 묶음을 그대로 쓰면
이유 칸에 선택과 무관한 근거가 붙는다. 그래서 근거(특성 키) 하나하나에 대해
  - 어느 성향의 **대표(rep)** 근거인지, **약한(weak)** 근거인지, **제외(exclude)** 인지
  - 어떤 **선택지 속성 태그**(night_view · garden · event · limited_goods · discount …)를 뒷받침하는지
를 적는다. 엔진은 선택지의 속성과 태그가 맞는 근거만 기여 계산과 이유에 넣는다. 원본 프로파일의 관측 사실은 지우지 않는다.

이 표는 개발 표본(blog41 · 42)의 비식별 특성 키를 사람이 읽고 손으로 연결한 것이다(자동 추출 아님 · 검수 대상).
검수에서 바뀌면 이 파일만 고치면 된다.
"""

# 태그 어휘(선택지 속성)
#  novelty: event 시즌 행사 · limited_goods 한정 상품 · new_place 새 장소 · new_food 새 음식 · promo 홍보를 보고
#  space:   night_view 야경 · garden 정원 · 산책 · ambience 공간 분위기 · decor 연출 · view_seat 조망 좌석
#  food:    menu_explore 여러 메뉴 · course 코스 · buffet · dessert · signature
#  benefit: discount 할인 · voucher 바우처 · 쿠폰 · card 카드 특전 · package 패키지
#  premium: chef · course / warm_rest: footbath · warm_pool / rest_need: rest / routine: repeat
#  practical_alt: room_meal · alt_meal / alcohol_familiar: wine · bar / seasonal: event · limited_goods · seasonal_food

R, W, X = "rep", "weak", "exclude"

EVIDENCE = {
    # ---------------- blog41
    "ad_spread_trial":              {"promo": (R, ["promo"]), "novelty": (W, ["promo", "new_food"])},
    "advert_seen_dessert_trial":    {"promo": (R, ["promo"]), "novelty": (R, ["new_food", "promo"]), "food": (R, ["dessert", "menu_explore"])},
    "bar_ambience_and_nonalcoholic": {"space": (R, ["ambience", "night_view"]), "novelty": (W, ["new_place"]), "alcohol_familiar": (X, [])},   # 3차: 무알코올 주문은 음주 친숙성 근거 아님
    "buffet_food_exploration":      {"food": (R, ["buffet", "menu_explore"])},
    "buffet_voucher_value":         {"post_appraisal": (R, []), "benefit": (W, ["voucher"])},
    "card_discount_and_coupon":     {"benefit": (R, ["card", "discount"])},
    "chef_course_consumed":         {"premium": (R, ["chef", "course"]), "food": (R, ["course"]), "space": (X, [])},
    "chef_course_reservation":      {"premium": (R, ["chef", "course"]), "food": (R, ["course"]), "novelty": (R, ["new_food"])},
    "gym_shoe_rental":              {"active": (R, [])},
    "limited_goods_wait_purchase":  {"novelty": (R, ["limited_goods"]), "seasonal": (R, ["limited_goods"])},
    "limited_swimcap_after_ad":     {"novelty": (R, ["limited_goods", "promo"]), "seasonal": (R, ["limited_goods"]), "promo": (R, ["promo"])},
    "lodging_voucher_choice":       {"benefit": (R, ["voucher", "package"])},
    "low_alcohol_self_description": {"alcohol_limit": (R, [])},
    "meal_discount_applied":        {"benefit": (R, ["discount"])},
    "new_hotel_stay":               {"novelty": (R, ["new_place"]), "space": (W, ["ambience"])},
    "night_view_footbath":          {"space": (R, ["night_view"]), "warm_rest": (R, ["footbath"])},
    "pizza_garlic_preference":      {"food_specific": (R, [])},
    "pizza_value_qualified":        {"post_appraisal": (R, [])},
    "pool_decor_planning":          {"space": (R, ["decor", "ambience"]), "novelty": (W, ["new_place"])},
    "pool_visit_not_swimming":      {"swim_aversion": (R, [])},
    "poster_changed_booking":       {"seasonal": (R, ["event"]), "novelty": (R, ["event"])},
    "pre_perfume_bundle_choice":    {"value_check": (R, []), "novelty": (X, []), "benefit": (X, [])},
    "pre_sportswear_value":         {"value_check": (R, []), "benefit": (X, [])},
    "pre_transport_price_increase": {"value_check": (R, [])},
    "room_external_food":           {"practical_alt": (R, ["room_meal"])},
    "sauna_goods_purchase":         {"benefit": (X, [])},
    "sauna_market_same_purchase":   {"benefit": (X, [])},
    "shellfish_preference_exceptions": {"food_specific": (W, [])},
    "spread_no_repurchase":         {"post_appraisal": (R, [])},
    "swimcap_not_swim_preference":  {"swim_aversion": (R, [])},
    "travel_bag_same_purchase":     {"novelty": (X, []), "value_check": (W, [])},
    "travel_bag_store_choice":      {"novelty": (X, []), "value_check": (W, [])},
    "two_flavors_and_sauces":       {"food": (R, ["menu_explore"]), "novelty": (W, ["new_food"])},
    "warm_shallow_pool":            {"warm_rest": (R, ["warm_pool"])},
    "wine_and_friend_trip":         {"alcohol_familiar": (R, ["wine"]), "space": (X, [])},
    # ---------------- blog42
    "annual_ice_plan_not_purchase": {"value_check": (W, []), "novelty": (X, []), "seasonal": (X, [])},
    "annual_ice_review_references": {"benefit": (X, []), "seasonal": (X, [])},
    "bakery_guest_discount":        {"benefit": (R, ["discount"]), "food": (W, ["dessert"])},
    "breakfast_coupon_used":        {"benefit": (R, ["voucher"]), "breakfast_priority": (R, [])},
    "brunch_rest_purpose":          {"rest_need": (R, ["rest"]), "space": (W, ["ambience"])},
    "day_night_footbath":           {"space": (R, ["night_view"]), "warm_rest": (R, ["footbath"])},
    "earlier_menu_different":       {"food": (R, ["menu_explore"]), "novelty": (R, ["new_food"])},
    "early_breakfast_routine":      {"breakfast_priority": (R, [])},
    "forest_shuttle_walk":          {"space": (R, ["garden"]), "practical_alt": (W, ["alt_meal"])},
    "functional_shaver_replacement": {"value_check": (R, []), "benefit": (X, [])},
    "garden_break_habit":           {"space": (R, ["garden"]), "routine": (R, ["repeat"]), "rest_need": (W, ["rest"])},
    "garden_tea_break":             {"space": (R, ["garden"]), "routine": (R, ["repeat"]), "rest_need": (W, ["rest"])},
    "hotel_ice_card_topup":         {"benefit": (R, ["card"]), "seasonal": (R, ["seasonal_food"]), "food": (W, ["dessert"])},
    "hotel_ice_different":          {"seasonal": (W, ["seasonal_food"]), "novelty": (W, ["new_food"]), "benefit": (X, [])},
    "icecream_card_benefit":        {"benefit": (R, ["card"])},
    "lounge_food_then_gym":         {"active": (R, []), "food": (W, ["menu_explore"]), "space": (W, ["ambience"])},
    "matcha_egg_tart_preference":   {"food_specific": (R, [])},
    "new_menu_after_previous":      {"food": (R, ["menu_explore"]), "novelty": (R, ["new_food"])},
    "popup_food_trial":             {"novelty": (R, ["event", "new_food"]), "seasonal": (R, ["event"])},
    "prior_hotel_ices":             {"seasonal": (W, ["seasonal_food"]), "benefit": (X, [])},
    "recovery_service_a":           {"rest_need": (R, ["rest"])},
    "recovery_service_b":           {"rest_need": (R, ["rest"])},
    "recovery_service_c":           {"rest_need": (R, ["rest"]), "benefit": (X, [])},   # 3차: 바우처 실사용 근거 미확인 → 혜택에서 제외
    "sale_food_disappointment":     {"post_appraisal": (R, [])},
    "sale_food_purchase":           {"value_check": (R, []), "benefit": (W, ["discount"])},
    "signature_drink_curiosity":    {"food": (R, ["signature"]), "novelty": (R, ["new_food"])},
    "voucher_choice_not_brunch":    {"benefit": (R, ["voucher"]), "routine": (W, ["repeat"])},
}

# blog43 수동 파일럿의 특성 키 → facet · 태그 (원문 근거 ID 는 특성 단위로 같이 묶임)
MANUAL_TRAITS = {
    "wine_and_alcohol_experience":  {"alcohol_familiar": (R, ["wine", "bar"])},
    "premium_dining":               {"premium": (R, ["chef", "course"]), "food": (R, ["course", "menu_explore"])},
    "space_view_atmosphere":        {"space": (R, ["view_seat", "garden", "night_view", "ambience"])},
    "hotel_travel_experience":      {},
    "new_food_exploration":         {"novelty": (R, ["new_food", "new_place"]), "food": (R, ["menu_explore"]), "seasonal": (X, [])},   # 3차: 근거가 새 식당 · 메뉴 · 장소이며 시즌 행사 참여 기록이 아님
    "quiet_rest_context":           {"rest_need": (R, ["rest"])},
    "food_specific_preferences":    {"food_specific": (R, [])},
    "flexible_alternative_choice":  {"practical_alt": (R, ["alt_meal", "room_meal"])},
    "revisit_and_repeat":           {"routine": (R, ["repeat"])},
    "selective_benefits":           {"benefit": (R, ["discount", "voucher"])},
}

GRADE_WEIGHT = {R: 1.0, W: 0.5, X: 0.0}
