"""Check the ACTUAL received field names; fixtures are synthetic, not new users."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import unittest

from test_author_validation_v4_2 import doc,fact
from operator_choice.author_validation_v4_2.team_contract import received_contract,prepare_team_requests,import_team_profile,adapt_team_photo_notes,ordered_team_output,integrate_imported_team,SECTIONS


def profile():
    f=fact()
    return {"SOURCE_AUDIT":{"unique_post_count":1,"scope_counts":{"walkerhill":1,"related":0,"recent":0},"other_hotel_post_count":None,"duplicate_source_rows":None,"independent_event_count":1,"excluded_post_ids":[],"excluded_post_count":0,"photo_note_count":0,"missing_sources":[],"review_requests":[]},
            "PERSONA_SUMMARY":"새 식음 경험을 시도한 합성 사례다. 구체적인 동기가 있다. 실제 고객 평가는 아니다.",
            "TRAIT_TABLE":[{"trait":"새 식음 시도","strength":"provisional","independent_evidence_count":1,"representative_post_ids":["T1"],"conditions":[],"counterexamples":[],"evidence_ids":[f["fact_id"]]}],
            "EVENT_ACTIONS":[{"event_id":"E1","visit_id":None,"link_status":"unlinked","stages":["order_reported"],"fact_ids":[f["fact_id"]],"post_ids":["T1"],"motives":[],"price_information":[]}],
            "EVIDENCE_MAP":[{"claim_id":f["fact_id"],"post_id":"T1","text_anchors":f["anchors"],"photo_note_ids":[],"evidence_kind":"fact","source_layer":"body"}],
            "CONTEXT_RULES":[{"rule_id":f"RULE{i}","condition":"같은 합성 환경","behavior_hypothesis":"새 메뉴를 고려할 수 있음","evidence_ids":[f["fact_id"]],"limits":["해당 합성 맥락"]} for i in (1,2)],
            "QUALITY_FLAGS":[],"STRUCTURED_PROFILE":{"persona_id":"NEW","facts":[f],"experience_links":[],"distinctive_free_property":"고정 태그로 바꾸지 않는 세부 정보"}}


def team_note():
    return {"post_id":"T1","image_position":"음료 사진 1","visual_observation":"두 잔이 보임",
            "linked_text_anchor":[],"relation_to_text":"augment","supported_claim_scope":"장면의 물품",
            "inference_limit":"작성자의 섭취나 동행 관계는 미상"}


class ReceivedTeamContractTest(unittest.TestCase):
    def test_nonfinite_not_valid_json_profile(self):
        p=profile(); p["TRAIT_TABLE"][0]["strength"]=float("nan")
        with self.assertRaisesRegex(ValueError,"strict_json"):
            import_team_profile([doc()],prepare_team_requests([doc()],author_role="holdout_new_author"),p)
    def test_actual_received_prompt_bytes_hash(self):
        r=received_contract()
        self.assertEqual(r["source_sha256"],"4e77237e7579bebd9f23cbb52244665f8b98ef4e902547fbc316486290f605fd")
        self.assertTrue(r["eight_sections_checked_against_source"])

    def test_received_five_inputs_and_all_posts(self):
        packet=prepare_team_requests([doc(),doc("T2",scope="recent")],author_role="holdout_new_author")
        self.assertEqual(set(packet["model_input_private"]["inputs"]),{"AUTHOR_ID","PRIMARY_TYPE","POSTS","WALKERHILL_PHOTO_NOTES","EXCLUDED_POSTS"})
        self.assertEqual(len(packet["model_input_private"]["inputs"]["POSTS"]),2)
        self.assertEqual(packet["actual_executions"],0)

    def test_native_and_team_different_conditions_not_pooled(self):
        r=prepare_team_requests([doc()],author_role="holdout_new_author")
        self.assertIn("differs",r["comparison_note"])
        self.assertIn("not_separate_team_approved",r["contract"]["subfield_json_schema_origin"])

    def test_all_eight_outputs_imported_and_free_fields_preserved(self):
        packet=prepare_team_requests([doc()],author_role="holdout_new_author")
        p=profile(); r=import_team_profile([doc()],packet,p)
        self.assertEqual(r["team_profile_private"],p)
        self.assertEqual(r["canonical_batches_private"][0]["facts"][0]["feature_key"],"unique_food_choice")
        self.assertEqual(list(ordered_team_output(dict(reversed(list(p.items()))))),list(SECTIONS))
        self.assertFalse(r["demo_approved"])

    def test_missing_actual_section_rejected(self):
        p=profile(); del p["EVENT_ACTIONS"]
        with self.assertRaisesRegex(ValueError,"eight_section_schema"):
            import_team_profile([doc()],prepare_team_requests([doc()],author_role="holdout_new_author"),p)

    def test_unlinked_body_quote_rejected(self):
        p=profile(); p["EVIDENCE_MAP"][0]["text_anchors"]=[]
        with self.assertRaisesRegex(ValueError,"evidence_map_mismatch"):
            import_team_profile([doc()],prepare_team_requests([doc()],author_role="holdout_new_author"),p)

    def test_source_count_and_post_identity_guard(self):
        packet=prepare_team_requests([doc()],author_role="holdout_new_author")
        p=profile(); p["SOURCE_AUDIT"]["unique_post_count"]=6
        with self.assertRaisesRegex(ValueError,"source_counts"): import_team_profile([doc()],packet,p)
        p=profile(); p["STRUCTURED_PROFILE"]["persona_id"]="OTHER"
        with self.assertRaisesRegex(ValueError,"wrong_author"): import_team_profile([doc()],packet,p)

    def test_fake_repeat_count_rejected(self):
        p=profile(); p["TRAIT_TABLE"][0]["independent_evidence_count"]=3
        with self.assertRaisesRegex(ValueError,"repeat_count_exceeds"):
            import_team_profile([doc()],prepare_team_requests([doc()],author_role="holdout_new_author"),p)

    def test_order_not_marked_as_participation(self):
        p=profile(); p["EVENT_ACTIONS"][0]["stages"]=["participation_reported"]
        with self.assertRaisesRegex(ValueError,"lifecycle_stage"):
            import_team_profile([doc()],prepare_team_requests([doc()],author_role="holdout_new_author"),p)

    def test_primary_type_is_tentative_and_basis_required(self):
        r=prepare_team_requests([doc()],author_role="holdout_new_author",primary_type={"label":"잠정","basis":"합성 관측"})
        self.assertEqual(r["model_input_private"]["inputs"]["PRIMARY_TYPE"]["label"],"잠정")
        with self.assertRaisesRegex(ValueError,"tentative_with_basis"):
            prepare_team_requests([doc()],author_role="holdout_new_author",primary_type="정답 유형")

    def test_pending_ads_not_excluded_and_not_author_wide(self):
        packet=prepare_team_requests([doc()],author_role="holdout_new_author",excluded_posts=[{"post_id":"T1","status":"pending","basis_ref":"CHECK1"}])
        p=profile(); p["SOURCE_AUDIT"]["excluded_post_ids"]=["T1"]; p["SOURCE_AUDIT"]["excluded_post_count"]=1
        with self.assertRaisesRegex(ValueError,"unconfirmed_or_author_wide"): import_team_profile([doc()],packet,p)

    def test_confirmed_post_only_exclusion(self):
        packet=prepare_team_requests([doc()],author_role="holdout_new_author",excluded_posts=[{"post_id":"T1","status":"confirmed_compensation","basis_ref":"DISCLOSURE1"}])
        p=profile(); p["SOURCE_AUDIT"]["excluded_post_ids"]=["T1"]; p["SOURCE_AUDIT"]["excluded_post_count"]=1
        r=import_team_profile([doc()],packet,p)
        self.assertEqual(r["excluded_post_ids"],["T1"])
        self.assertEqual(len(r["canonical_batches_private"][0]["facts"]),1)
        self.assertEqual(integrate_imported_team([doc()],r)["scored_post_count"],0)

    def test_actual_output_connected_to_unchanged_v41_policy(self):
        packet=prepare_team_requests([doc()],author_role="holdout_new_author")
        imported=import_team_profile([doc()],packet,profile())
        out=integrate_imported_team([doc()],imported)
        self.assertEqual(out["policy_version"],"author_method_v4.1-policy-0.1")
        self.assertEqual(out["active_fact_count"],1)
        self.assertFalse(out["demo_approved"])

    def test_duplicate_event_actions_rejected(self):
        p=profile(); p["EVENT_ACTIONS"].append(deepcopy(p["EVENT_ACTIONS"][0]))
        with self.assertRaisesRegex(ValueError,"same_event"):
            import_team_profile([doc()],prepare_team_requests([doc()],author_role="holdout_new_author"),p)

    def test_minimum_actual_photo_fields_and_none(self):
        self.assertFalse(adapt_team_photo_notes([doc()],"none"))
        n=adapt_team_photo_notes([doc()],[team_note()])["T1"][0]
        self.assertEqual(n["relation_to_text"],"augment")
        self.assertEqual(n["text_anchor_status"],"prose_link_pending_resolution")
        self.assertEqual(n["new_independent_experience_credit"],0)

    def test_confirm_augment_contradict_are_preserved(self):
        for code in ("confirm","augment","contradict"):
            n=team_note(); n["relation_to_text"]=code
            self.assertEqual(adapt_team_photo_notes([doc()],[n])["T1"][0]["relation_to_text"],code)

    def test_prose_relation_not_silently_interpreted(self):
        n=team_note(); n["relation_to_text"]="본문의 공간을 보강"
        with self.assertRaisesRegex(ValueError,"explicit_photo_relation"): adapt_team_photo_notes([doc()],[n])
        n["relation_code"]="augment"
        self.assertEqual(adapt_team_photo_notes([doc()],[n])["T1"][0]["relation_to_text_original_private"],"본문의 공간을 보강")

    def test_invalid_photo_post_scope(self):
        with self.assertRaisesRegex(ValueError,"only_for_walkerhill"):
            adapt_team_photo_notes([doc(scope="recent")],[team_note()])

    def test_profile_scope_excluded_body_not_sent(self):
        a=doc(); b=doc("T2",scope="recent"); b["profile_scope_excluded"]=True; b["text"]="SHOULD_NOT_SEND"
        packet=prepare_team_requests([a,b],author_role="holdout_new_author")
        self.assertEqual(packet["excluded_input_scope_post_ids"],["T2"])
        self.assertEqual(len(packet["model_input_private"]["inputs"]["POSTS"]),1)
        self.assertNotIn("SHOULD_NOT_SEND",str(packet["model_input_private"]))

    def test_actual_photo_claim_connects_without_fake_body_quote(self):
        n=team_note(); n.update(note_id="N1",experience_key="E1",observer_ref="REVIEWER")
        packet=prepare_team_requests([doc()],author_role="holdout_new_author",photo_notes=[n])
        p=profile(); p["SOURCE_AUDIT"]["photo_note_count"]=1
        c={"claim_id":"C1","post_id":"T1","experience_key":"E1","source_note_ids":["N1"],
           "claim_type":"observer_inference","claim_text":"합성 장면의 보조 해석","scope":"scene_only","limitations":["not consumption proof"]}
        p["STRUCTURED_PROFILE"]["visual_note_claims"]=[c]
        p["EVIDENCE_MAP"].append({"claim_id":"C1","post_id":"T1","text_anchors":[],"photo_note_ids":["N1"],"evidence_kind":"inference","source_layer":"visual_observer_note"})
        imported=import_team_profile([doc()],packet,p)
        self.assertEqual(imported["visual_supplements_private"][0]["new_independent_experience_credit"],0)
        self.assertEqual(integrate_imported_team([doc()],imported)["active_fact_count"],1)


if __name__=="__main__": unittest.main()
