"""Author-first, multimodal profile assembly for exploratory research.

Only de-identified anchors and paraphrased claims are emitted. A post, visit,
and event are separate entities; evidence roots prevent repeated media from
being mistaken for independent observations.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
OUT = HERE / "profile_v3_artifacts"


def _anchor(doc: str, pages: list[int], modality: str, root: str, state: str = "supplied_page_note") -> dict:
    return {"document_id": doc, "pages": pages, "modality": modality,
            "evidence_root": root, "source_state": state}


def blog41_input() -> dict:
    """De-identified research input. No raw quotation, account key, or URL."""
    docs = [
        {"document_id":"P1", "topic":"GRAND guest room", "published_date":"2025-05-08",
         "event_date":"2024-10 (month-level, as described in post)", "date_basis":"post_body_note",
         "visit_cluster":"V1_GRAND_CANDIDATE", "cluster_status":"strong_same_trip_candidate",
         "pages":[10,11,12,13], "media":["room_view_photo","amenity_and_delivery_photos"],
         "source_state":"selected_pages_rendered_visual_spot_check; text_from_user_review_memo_not_ocr_verified"},
        {"document_id":"P2", "topic":"THE BUFFET breakfast", "published_date":"2025-05-09",
         "event_date":"2024-10 (same Grand stay candidate)", "date_basis":"linked_post_context",
         "visit_cluster":"V1_GRAND_CANDIDATE", "cluster_status":"strong_same_trip_candidate",
         "pages":[1,10,11,12,13], "media":["two_place_settings_and_plates","restaurant_view","menu_and_price_photos"],
         "source_state":"selected_pages_rendered_visual_spot_check; text_from_user_review_memo_not_ocr_verified"},
        {"document_id":"P3", "topic":"VISTA guest room", "published_date":"2026-09-05",
         "event_date":"unknown; two nights / three days stated", "date_basis":"post_body_duration_only",
         "visit_cluster":"V2_VISTA_CANDIDATE", "cluster_status":"probable_link_not_fully_verified",
         "pages":[8,17,18,20], "media":["room_and_bed_photo","room_dining_photo","linked_review_cards"],
         "source_state":"selected_pages_rendered_visual_spot_check; text_from_user_review_memo_not_ocr_verified"},
        {"document_id":"P4", "topic":"Pizza Hill meal", "published_date":"2026-09-07",
         "event_date":"2026-07-23 15:46 (receipt time)", "date_basis":"receipt_record_reported_in_review_memo",
         "visit_cluster":"V2_VISTA_CANDIDATE", "cluster_status":"probable_link_to_VISTA_trip_not_exact_sequence",
         "pages":[8,9,10,11,12], "media":["food_photos","two_drinks_photo","receipt","menu_and_sauce_photos"],
         "source_state":"selected_pages_rendered_visual_spot_check; text_from_user_review_memo_not_ocr_verified"},
        {"document_id":"P5", "topic":"THE BUFFET dinner", "published_date":"2026-09-07",
         "event_date":"unknown; linked to VISTA travel posts", "date_basis":"cross_linked_post_context",
         "visit_cluster":"V2_VISTA_CANDIDATE", "cluster_status":"probable_link_not_fully_verified",
         "pages":[1,4,12,14,15], "media":["food_and_menu_photos","price_and_benefit_photos"],
         "source_state":"selected_pages_rendered_visual_spot_check; text_from_user_review_memo_not_ocr_verified"},
        {"document_id":"P6", "topic":"VISTA facilities: fitness, pools, Skyard, foot bath", "published_date":None,
         "event_date":"unknown", "date_basis":"not_supplied", "visit_cluster":"UNASSIGNED_P6",
         "cluster_status":"same_author_linked; stay_link_unknown", "pages":[5,6,14,15,16,17,21,22,23],
         "media":["fitness_equipment_and_room_photos","indoor_pool_and_kids_pool_photos","night_view_photos","foot_bath_and_rules_photos"],
         "source_state":"selected_pages_visually_opened; page_specific_text_interpretation_from_user_instruction"},
    ]
    claims = [
        {"claim_id":"C01","aspect":"author_self_description_gender_expression","value":"woman_self_expression_reported",
         "claim_layer":"first_person_self_expression","scope":"author_level","strength":"direct_if_transcription_verified",
         "anchors":[_anchor("P6",[5],"text", "P6:self_expression")],
         "reasoning":"사용자가 지정한 1인칭 여성 표현을 작성자 수준 단서로 둔다. 페이지의 작은 문구 전사 재확인은 남아 있다.",
         "alternatives":[],"decision_usable":False,"review":"human_review_pending"},
        {"claim_id":"C02","aspect":"gym_participation","value":"used_fitness_facility",
         "claim_layer":"observed_activity","scope":"P6_visit_only","strength":"direct_activity_not_preference",
         "anchors":[_anchor("P6",[5,6],"text+image","P6:gym_visit")],
         "reasoning":"운동시설 이용은 참여 사실이다. 운동 목적 여행·지속적 운동 성향·혼잡 회피를 단독으로 뜻하지 않는다.",
         "alternatives":["체류 중 부수 이용"],"decision_usable":True,"review":"human_review_pending"},
        {"claim_id":"C03","aspect":"gym_size_and_crowding_appraisal","value":"mixed_or_qualified_facility_evaluation",
         "claim_layer":"contextual_appraisal_candidate","scope":"this_gym_experience","strength":"page_note_not_transcribed",
         "anchors":[_anchor("P6",[5,6],"text+image","P6:gym_evaluation")],
         "reasoning":"규모·혼잡 평가가 있었다는 사용자 페이지 지정은 보존하되 방향·강도는 문구 재확인 전 임의 점수화하지 않는다.",
         "alternatives":["혼잡과 시설 규모는 별도 평가축일 수 있음"],"decision_usable":False,"review":"human_review_pending"},
        {"claim_id":"C04","aspect":"indoor_pool_and_kids_pool","value":"warm_and_suitable_for_water_fearful_users",
         "claim_layer":"positive_contextual_appraisal_reported","scope":"specific_pool_feature_and_use_case","strength":"user_page_interpretation; page_anchor_present",
         "anchors":[_anchor("P6",[14,15,16,17],"text+image","P6:pool_and_kids_pool")],
         "reasoning":"유아풀 언급은 따뜻함·물에 대한 두려움이 있는 사람에게 적합하다는 긍정 맥락으로 전달됨. 성인 적합성에 대한 부정으로 자동 변환하지 않는다.",
         "alternatives":["다른 풀의 크기·성인 수영 적합성은 별도 평가"],"decision_usable":True,"review":"human_review_pending"},
        {"claim_id":"C05","aspect":"skyard_night_view","value":"positive_appraisal_reported",
         "claim_layer":"positive_contextual_appraisal_reported","scope":"specific_night_view_experience","strength":"user_page_interpretation; visual_scene_seen",
         "anchors":[_anchor("P6",[21],"text+image","P6:skyard_night_view")],
         "reasoning":"야간 조망 경험의 긍정 평가는 스카이야드 야경 범위에 한정한다. 재방문 의향·모든 전망 선호는 별도다.",
         "alternatives":[],"decision_usable":True,"review":"human_review_pending"},
        {"claim_id":"C06","aspect":"foot_bath_expectation_vs_use","value":"expectation_and_actual_use_both_present; valence_unresolved",
         "claim_layer":"observed_experience_plus_unknown_appraisal","scope":"specific_foot_bath_experience","strength":"page_note_not_transcribed",
         "anchors":[_anchor("P6",[22,23],"text+image","P6:foot_bath")],
         "reasoning":"기대와 실제 이용을 구분한다. 기대가 충족되었는지와 전반 만족은 원문 캡션 재확인 전 미상.",
         "alternatives":["이용했으나 평가 방향은 불명"],"decision_usable":False,"review":"human_review_pending"},
        {"claim_id":"C07","aspect":"pizza_food_preference","value":"likes_pizza; garlic_sauce_preferred; garlic_and_olive_oil_flavors_positive",
         "claim_layer":"explicit_preference_and_menu_appraisal_reported","scope":"pizza_and_named_flavor_features","strength":"strong_in_supplied_review_summary",
         "anchors":[_anchor("P4",[8,9,10],"text+image","P4:pizza_and_flavor")],
         "reasoning":"피자 자체 취향, 갈릭 소스 우선, 마늘·올리브오일 풍미 평가는 메뉴 단위 개인 선호다. 모든 이탈리안 식당으로 넓히지 않는다.",
         "alternatives":["피자힐 피자의 전반 평가는 별도 평가"],"decision_usable":True,"review":"human_review_pending",
         "decision_mappings":[{"scenario":"pizza_revisit","conditions":["regular_price","same_20_percent_discount"],"option_directions":{"PIZZA_HILL":1},"category":"personal_fit","evidence_root":"P4:pizza_and_flavor","reliability":0.75,"relevance":0.55,"basis":"피자/갈릭 풍미 선호는 업장 가격가치 평가와 분리된 메뉴 적합성 단서."}]},
        {"claim_id":"C08","aspect":"pizza_hill_taste_and_value","value":"pizza_not_exceptional; poor_value_even_after_20_percent_guest_discount",
         "claim_layer":"contextual_appraisal_reported","scope":"P4_meal_and_discounted_transaction","strength":"strong_in_supplied_review_summary",
         "anchors":[_anchor("P4",[8,10,11,12],"text+image","P4:pizzahill_value")],
         "reasoning":"총액과 할인 후 가격 대비 만족을 낮게 평가한 국소 경험이다. 피자 선호와 공존하며 저가 지향·전반 가격 민감성으로 승격하지 않는다.",
         "alternatives":["추가 할인·메뉴 변경·대체 업장에 대한 가격 반응은 미측정"],"decision_usable":True,"review":"human_review_pending",
         "transaction":{"amount_krw":189000,"guest_discount_percent":20,"payment_interpretation":"order_total_and_discount_reported; personal final payment not independently verified"},
         "decision_mappings":[{"scenario":"pizza_revisit","conditions":["regular_price","same_20_percent_discount"],"option_directions":{"PIZZA_HILL":-2},"category":"value_fit","evidence_root":"P4:pizzahill_value","reliability":0.85,"relevance":0.9,"basis":"20% 할인 뒤에도 가격 대비 만족이 낮았다는 해당 거래의 국소 평가."},{"scenario":"pizza_revisit","conditions":["additional_discount_unquantified"],"status":"unknown_for_condition","option_directions":{},"category":"value_fit","evidence_root":"P4:pizzahill_value","reliability":0,"relevance":0,"basis":"추가 할인 탄력성 자료 없음; 점수 변화 미추정."}]},
        {"claim_id":"C09","aspect":"two_drinks_visual","value":"two_drinks_present; author_consumption_unknown",
         "claim_layer":"visual_observation","scope":"P4_table_scene","strength":"image_scene_reported",
         "anchors":[_anchor("P4",[10],"image","P4:drinks_scene")],
         "reasoning":"음료 두 잔이 보이는 사실은 작성자의 실제 음주·음료 종류 선호를 확정하지 않는다.",
         "alternatives":["동행자 음료일 수 있음"],"decision_usable":False,"review":"human_review_pending"},
        {"claim_id":"C10","aspect":"buffet_menu_evaluations","value":"multiple_item_specific_positive_and_qualified_evaluations",
         "claim_layer":"contextual_appraisal_reported","scope":"named_menu_items_only","strength":"strong_in_supplied_review_summary",
         "anchors":[_anchor("P5",[4,12,14],"text+image","P5:menu_evaluation")],
         "reasoning":"음식 품질에 대한 구체 평가와 가격·가치 유보를 분리한다. 뷔페 전체의 무조건적 선호나 불호가 아니다.",
         "alternatives":["메뉴별 취향 차이가 있음"],"decision_usable":True,"review":"human_review_pending",
         "decision_mappings":[{"scenario":"buffet_dinner","conditions":["full_price","voucher_or_discount"],"option_directions":{"THE_BUFFET":1},"category":"personal_fit","evidence_root":"P5:menu_evaluation","reliability":0.7,"relevance":0.7,"basis":"세부 메뉴에 대한 긍정·혼합 평가; 전체 업장 재방문 선호는 아님."}]},
        {"claim_id":"C16","aspect":"buffet_price_value","value":"high_listed_dinner_price_and_value_reservation_with_benefit_consideration",
         "claim_layer":"contextual_appraisal_reported","scope":"P5_dinner_transaction_and_listed_price","strength":"moderate_in_supplied_review_summary",
         "anchors":[_anchor("P5",[1,14,15],"text+image","P5:price_and_benefit")],
         "reasoning":"음식 품질 평가와 정가 부담·식사권/투숙 할인 검토를 분리한다. 혜택 이용은 비용을 고려하는 행동이지 전반적인 절약 성향은 아니다.",
         "alternatives":["메뉴 만족이 가격 부담보다 클 수 있음","혜택 자격·실제 자기부담액은 조건별로 달라짐"],"decision_usable":True,"review":"human_review_pending",
         "decision_mappings":[{"scenario":"buffet_dinner","conditions":["full_price"],"option_directions":{"THE_BUFFET":-1},"category":"value_fit","evidence_root":"P5:price_and_benefit","reliability":0.65,"relevance":0.75,"basis":"정가 및 가치에 대한 유보 보고; 체감 가격 민감도의 개인 상수로 취급하지 않음."},{"scenario":"buffet_dinner","conditions":["voucher_or_discount"],"option_directions":{"THE_BUFFET":-1},"category":"value_fit","evidence_root":"P5:price_and_benefit","reliability":0.65,"relevance":0.75,"basis":"혜택 이용 검토가 가격 유보를 해소했다고 확인되지 않아 같은 평가를 유지; 실제 할인 후 만족·자기부담액 미상."}]},
        {"claim_id":"C11","aspect":"breakfast_entitlement_use","value":"breakfast_used_as_included_benefit",
         "claim_layer":"observed_benefit_use","scope":"P2_Grand_stay","strength":"strong_in_supplied_review_summary",
         "anchors":[_anchor("P2",[1,13],"text+image","P2:included_breakfast")],
         "reasoning":"포함 조식 이용은 확인 가능한 사용 행태지만, 유료 조식을 직접 구매할 의사와는 다르다.",
         "alternatives":["포함 여부가 이용 결정에 영향을 주었을 수 있음"],"decision_usable":True,"review":"human_review_pending",
         "decision_mappings":[{"scenario":"paid_breakfast","conditions":["included"],"option_directions":{"USE_INCLUDED":1},"category":"engagement_fit","evidence_root":"P2:included_breakfast","reliability":0.8,"relevance":0.6,"basis":"포함 혜택으로 실제 이용한 경험; 유료 구매 의향 아님."},{"scenario":"paid_breakfast","conditions":["self_paid","voucher"],"status":"unknown_for_condition","option_directions":{},"category":"value_fit","evidence_root":"P2:included_breakfast","reliability":0,"relevance":0,"basis":"유료 구매·바우처 추가 이용의 직접 근거가 아님."}]},
        {"claim_id":"C12","aspect":"scenic_space_interest","value":"selects_and_documents_multiple_view_contexts",
         "claim_layer":"cross_visit_behavioral_pattern","scope":"room_vs_dining_seat_vs_rooftop_view_separate","strength":"moderate_cross_visit_candidate",
         "anchors":[_anchor("P1",[10],"text+image","P1:mountain_view_choice"),_anchor("P2",[10,11,12],"image","P2:hangang_breakfast_seat"),_anchor("P3",[8],"image","P3:river_view_room"),_anchor("P6",[21],"image","P6:night_view")],
         "reasoning":"과거 리버뷰 경험 후 마운틴뷰 선택과 다른 시기의 한강 조망·조식 좌석·야경 기록을 통합한다. '객실 뷰 낮은 우선순위' 하나로 축약하지 않는다.",
         "alternatives":["조망은 경험별 선택 이유가 다를 수 있음"],"decision_usable":True,"review":"human_review_pending"},
        {"claim_id":"C13","aspect":"room_dining_and_external_food","value":"external_chicken_in_room_at_grand_and_vista",
         "claim_layer":"repeated_behavior_across_distinct_stays_reported","scope":"convenience_room_dining_not_hotel_food_rejection","strength":"moderate_cross_stay_candidate",
         "anchors":[_anchor("P1",[11,12],"text+image","P1:room_delivery"),_anchor("P3",[17,18],"text+image","P3:room_delivery")],
         "reasoning":"외부 음식의 객실 이용과 호텔 내 고급 식음 경험은 공존한다. 편의 수용성 단서이지 호텔 식음 회피로 보지 않는다.",
         "alternatives":["일회성 일정·동행·배달 가능성이 원인일 수 있음"],"decision_usable":True,"review":"human_review_pending"},
        {"claim_id":"C14","aspect":"review_documentation_style","value":"detailed_facility_food_price_receipt_and_photo_documentation",
         "claim_layer":"author_content_pattern","scope":"review_writing_not_consumption_or_activity_intensity","strength":"strong_across_six_posts",
         "anchors":[_anchor(doc["document_id"],doc["pages"],"text+image","author_review_detail") for doc in docs],
         "reasoning":"상세 기록 성향은 작성 방식이다. 실제 시설 횟수, 신체 활동성, 만족도와 독립 변수로 유지한다.",
         "alternatives":["블로그 장르·제휴·기록 목적이 상세성에 기여할 수 있음"],"decision_usable":False,"review":"human_review_pending"},
        {"claim_id":"C15","aspect":"party_size_and_relationship","value":"two_person_companion_trip_is_primary; specific_relationship_unknown",
         "claim_layer":"ranked_hypothesis_not_fact","scope":"more_than_one_visit_candidate","strength":"heuristic_uncalibrated",
         "anchors":[_anchor("P2",[10,11],"image","party_size_grand_scene"),_anchor("P4",[10],"image","party_size_vista_scene"),_anchor("P3",[8],"image","bed_configuration_scene")],
         "reasoning":"그랜드와 비스타 방문 후보의 2인 세팅·음료 장면은 동행 규모 가설을 지지한다. 침대 사진은 한 개의 넓은 침대를 보여주지만 공식 유형·정원과 관계를 확인하지 않는다. 커플/부부는 확인 우선 후보이며 친구·가족·기타 가능성도 유지한다.",
         "alternatives":["partner_or_spouse","friend_or_relative_companion","other_two_person_companion"],"decision_usable":False,"review":"human_review_pending"},
        {"claim_id":"C17","aspect":"bed_configuration_visual","value":"one_wide_bed_visible_official_bed_type_and_guest_occupancy_unknown",
         "claim_layer":"visual_observation","scope":"P3_room_image_only","strength":"visual_scene_not_room_specification",
         "anchors":[_anchor("P3",[8],"image","P3:bed_scene")],
         "reasoning":"객실 사진에 넓은 침대 한 개가 보인다. 킹/더블 규격, 예약 정원, 실제 투숙 인원을 사진만으로 확정하지 않는다.",
         "alternatives":["개별 수면 선호·추가 침구·촬영 프레임 밖 구성이 가능"],"decision_usable":False,"review":"human_review_pending"},
    ]
    return {
        "persona_id":"blog41", "profile_version":"author_profile_v3.0",
        "analysis_unit":"author", "source_review_count":6, "author_link_status":"same_author_link_as_reported_in_user_supplied_review_material",
        "source_access_status":"six_supplied_pdf_captures; selected_pages_rendered_and_visually_spot_checked; fine_text_not_ocr_verified; user_page_notes_used",
        "publication_dates_are_not_visit_dates":True, "documents":docs,
        "visit_clusters":[
            {"visit_cluster_id":"V1_GRAND_CANDIDATE","property":"GRAND","post_ids":["P1","P2"],"event_ids":["P1:room","P2:breakfast"],"visit_date":"2024-10 month-level context","confidence":"strong_same_trip_candidate","basis":"room post and included-breakfast post linked to Grand stay; exact day/time unresolved"},
            {"visit_cluster_id":"V2_VISTA_CANDIDATE","property":"VISTA","post_ids":["P3","P4","P5"],"event_ids":["P3:stay","P4:pizza","P5:dinner"],"visit_date":"one event 2026-07-23 15:46; other event dates unknown","confidence":"probable_link_not_fully_verified","basis":"two-night/three-day Vista post, Pizza Hill receipt, and buffet-dinner cross-links; no exact sequence assumed"},
            {"visit_cluster_id":"UNASSIGNED_P6","property":"VISTA facilities context","post_ids":["P6"],"event_ids":["P6:gym","P6:pool","P6:skyard","P6:foot_bath"],"visit_date":None,"confidence":"same_author_linked_stay_unknown","basis":"facilities review linked at author level; no stay merge without date/link evidence"}
        ],
        "known_distinct_lodging_visit_count":{"minimum":2,"maximum":None,"count_status":"at_least_two_property_stays; inventory_incomplete"},
        "legacy_card_audit":[
            {"field":"r011_single_stay_scope","existing_value":"one VISTA stay card with meal/facility events","finding":"valid as a stay-level record only; insufficient as author-wide profile after GRAND posts and additional linked posts","correction_candidate":"keep the original card immutable; add author-level profile joining posts while retaining separate visit clusters"},
            {"field":"B_snapshot_start_at","existing_value":"2026-09-05T14:30:00","finding":"2026-09-05 is P3 publication date; the supplied source summary states two nights/three days but no exact check-in date/time. P4 has a 2026-07-23 receipt event. Publication date must not become check-in.","correction_candidate":"exact VISTA check-in date/time unknown; do not overwrite original card without separate approval"},
            {"field":"single_stay_assignment_for_all_posts","existing_value":"P1-P6 not represented","finding":"GRAND P1/P2 form one strong stay candidate; VISTA P3-P5 are probable linked; P6 date/stay assignment remains open","correction_candidate":"at least two known lodging contexts; additional visit count remains incomplete"}
        ],
        "claims":claims,
        "profile_summary":"blog41은 시설을 다양하게 이용하고 식음 경험을 메뉴·풍미·가격·혜택 단위로 세밀하게 기록하는 후기 작성자다. 피자와 특정 마늘 풍미를 좋아한다고 보고하면서도 피자힐에서는 할인 후에도 가격 대비 가치를 낮게 평가해, 음식 취향과 업장 가치 판단을 구분할 수 있다. 더뷔페에서는 음식별 긍정과 가격 유보가 공존하고, 포함 조식 이용은 정가 구매 의향을 입증하지 않는다. 그랜드의 마운틴뷰 선택, 비스타의 한강 조망 객실, 조식 좌석과 야경 경험은 조망을 하나의 고정 선호로 축약하기 어렵다는 점을 보여준다. 두 숙박 경험에서 객실 내 외부 음식 이용도 보고되어 고급 호텔 식음과 편의형 식사가 상황에 따라 병존한다. 2인 동행은 반복 장면상 유력하지만 관계는 미확정이며, 운동·수영·스카이야드·족욕 경험의 세부 평가와 날짜는 페이지 문구 및 방문 연결을 사람 검수해야 한다.",
        "promotion_mode":{"exploratory_research":"allowed_with_source_lineage_and_sensitivity_only","verified_or_demo":"requires_transcription_and_human_review","independent_evaluation_eligible":False,"demo_approved":False},
        "human_review_status":"pending", "raw_quotes_stored":False, "public_urls_stored":False,
        "author_identifiers_stored":False, "model_calls":0
    }


def _cluster_roots(claim: dict) -> set[str]:
    return {a["evidence_root"] for a in claim.get("anchors", [])}


def rank_party_hypotheses(profile: dict) -> dict:
    """Transparent ordinal evidence count; never calibrated as probability."""
    claim = next((c for c in profile["claims"] if c["aspect"] == "party_size_and_relationship"), None)
    if not claim:
        return {"primary_hypothesis":"unknown","alternatives":[],"calibration_status":"not_calibrated"}
    # The two-person table/meal scenes support party size, not romantic status.
    roots = _cluster_roots(claim)
    document_clusters = {post_id: visit["visit_cluster_id"]
        for visit in profile.get("visit_clusters", []) for post_id in visit.get("post_ids", [])}
    anchors = claim.get("anchors", [])
    distinct_visit_roots = {document_clusters.get(a["document_id"], a["document_id"])
                            for a in anchors if a.get("document_id")}
    return {"primary_hypothesis":"two_person_companion_relationship_unknown",
            "party_size_support_roots":sorted(roots),
            "distinct_visit_context_count":len(distinct_visit_roots),
            "party_size_heuristic_support_score":float(len(distinct_visit_roots)),
            "relationship_candidates":[
                {"hypothesis":"partner_or_spouse","heuristic_support_score":0.0,"supporting_evidence":[],"contradicting_evidence":[],"review_priority":"first_candidate_to_check_not_ranked_as_more_likely"},
                {"hypothesis":"friend_or_relative","heuristic_support_score":0.0,"supporting_evidence":[],"contradicting_evidence":[],"review_priority":"keep_as_live_alternative"},
                {"hypothesis":"other_companion","heuristic_support_score":0.0,"supporting_evidence":[],"contradicting_evidence":[],"review_priority":"keep_as_live_alternative"}
            ],"calibration_status":"uncalibrated_ordinal_evidence_count_not_probability",
            "note":"2인 장면은 동행 규모의 후보를 지지하나 관계별 증거는 아직 없다. 관계 가설 동점은 데이터가 구별하지 못한다는 뜻이며 억지로 순위를 만들지 않는다. 침대 공식 유형·인원·관계의 직접 확인 없음. 개별 사진/세팅을 같은 방문에서 중복 가산하지 않음."}


def write() -> dict:
    OUT.mkdir(exist_ok=True)
    profile=blog41_input()
    profile["party_hypothesis_ranking"]=rank_party_hypotheses(profile)
    path=OUT/"blog41_author_profile_v3.json"
    content=json.dumps(profile,ensure_ascii=False,indent=2)+"\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"refusing_to_overwrite_changed_artifact:{path.name}")
    else:
        path.write_text(content,encoding="utf-8")
    return profile


if __name__ == "__main__":
    p=write()
    print(json.dumps({"persona_id":p["persona_id"],"posts":p["source_review_count"],"visit_min":p["known_distinct_lodging_visit_count"]["minimum"],"claims":len(p["claims"]),"model_calls":p["model_calls"]}))
