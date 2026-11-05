"""Synthetic contract checks, not new-author semantic-quality measurements."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest
import tempfile

from operator_choice.author_validation_v4_2.common import digest, require_corpus
from operator_choice.author_validation_v4_2.team_bridge import import_rows, export_rows, require_ready, mapping_status
from operator_choice.author_validation_v4_2.photo_notes import normalize_notes, image_availability, normalize_note_claims
from operator_choice.author_validation_v4_2.coverage import audit_inventory
from operator_choice.author_validation_v4_2.study import prepare_requests, validate_import, frozen_method
from operator_choice.author_validation_v4_2.evaluation import review_template, semantic_summary, compare_reviewed_runs
from operator_choice.author_validation_v4_2.__main__ import private_path,save_private

ROOT=Path(__file__).resolve().parents[1]/"operator_choice"
MAPPING=json.loads((ROOT/"author_validation_v4_2"/"team_mapping_provisional.json").read_text())


def doc(post="T1",persona="NEW",scope="walkerhill"):
    return {"persona_id":persona,"post_id":post,"scope":scope,"source_class":"synthetic_fixture",
            "title":"합성 제목","text":"처음이라 궁금해서 주문했다. 좋은 풍경이었다."}


def fact(post="T1"):
    d=doc(post)
    return {"fact_id":post+"_F1","persona_id":"NEW","post_id":post,"experience_key":"E1","feature_key":"unique_food_choice",
            "detail":"합성 행동 설명","anchors":[{"span":[0,16],"quote":d["text"][:16]}],
            "kind":"purchase","dimension":"new_experience_trial","actor":"author",
            "time_scope":"source_experience","action_stage":"order_reported","polarity":"positive",
            "confidence":"high","common_dimensions":["novelty_trial"]}


def note(document=None):
    d=document or doc()
    return {"note_id":"N1","post_id":d["post_id"],"persona_id":d["persona_id"],"experience_key":"E1",
            "observer_ref":"REVIEWER","asset_ref":"PHOTO1","body_sha256_private":digest(d["text"]),
            "observations":["사진 안에 두 잔이 보인다"],"interpretations":["두 사람일 가능성은 있으나 관계는 미상"],
            "limitations":["화면 밖의 사람이나 실제 음용자는 확인 불가"]}


def inventory():
    return {"origin":"human_source_inventory","persona_id":"NEW","source_post_ids":["T1","T2"],"used_for_method_development":False,"status":"reviewed",
            "frozen_before_extraction":True,"author_role":"holdout_new_author",
            "units":[{"reference_id":"R1","coverage_eligible":True},{"reference_id":"R2","coverage_eligible":True}]}


def submitted(facts,refs=None):
    refs=refs or inventory()
    r=review_template(facts,refs); r["human_review"]="submitted"
    for row in r["rows"]:
        row.update(verdict="supported",matched_reference_ids=["R1"],semantic_unit_id="UNIT1",actor_correct=True,
                   stage_correct=True,scope_correct=True,reason="합성 검수 이유",reviewer_ref="REVIEWER")
    r["missing_reference_ids"]=["R2"]
    return r


class TeamMappingTest(unittest.TestCase):
    def test_provisional_not_team_verified(self):
        self.assertFalse(mapping_status(MAPPING)["ready_for_fixed_input_use"])

    def test_core_fields_unmapped_rejected(self):
        m=deepcopy(MAPPING); del m["fields"]["actor"]
        with self.assertRaisesRegex(ValueError,"unmapped"): mapping_status(m)

    def test_two_targets_cannot_silently_share_field(self):
        m=deepcopy(MAPPING); m["fields"]["actor"]="detail"
        with self.assertRaisesRegex(ValueError,"one_to_one"): mapping_status(m)

    def test_lossless_unknown_detail_roundtrip(self):
        f=fact(); f["distinctive_free_description"]="태그 목록 밖의 합성 행동"
        b=import_rows(doc(),[f],MAPPING)
        self.assertEqual(export_rows(b,MAPPING),[f])
        self.assertFalse(b["integration_eligible"])

    def test_preview_cannot_claim_final_contract(self):
        b=import_rows(doc(),[fact()],MAPPING)
        with self.assertRaisesRegex(ValueError,"not_final"): require_ready(b)

    def test_actual_prompt_hash_binding(self):
        m=deepcopy(MAPPING); p="합성 팀 프롬프트"
        m.update(status="source_contract_checked",source_form_ref="SYNTHETIC_FORM",source_prompt_sha256=sha256(p.encode()).hexdigest())
        self.assertTrue(mapping_status(m,p)["ready_for_fixed_input_use"])
        self.assertFalse(mapping_status(m,p+"변경")["ready_for_fixed_input_use"])

    def test_renamed_fields_are_explicit(self):
        m=deepcopy(MAPPING); m["fields"]["detail"]="행동_설명"
        f=fact(); f["행동_설명"]=f.pop("detail")
        self.assertEqual(export_rows(import_rows(doc(),[f],m),m),[f])

    def test_post_evaluation_not_advance_price_avoidance(self):
        f=fact(); f.update(kind="appraisal",dimension="post_appraisal",common_dimensions=["prepurchase_value"],action_stage="not_applicable")
        with self.assertRaisesRegex(ValueError,"advance_price"): import_rows(doc(),[f],MAPPING)


class PhotoMemoTest(unittest.TestCase):
    def claim(self):
        return {"claim_id":"C1","experience_key":"E1","source_note_ids":["N1"],"claim_type":"observer_inference",
                "claim_text":"두 사람일 가능성을 검토","scope":"해당 장면","limitations":["사진 밖 인원 미상"]}

    def test_no_collection_and_no_missing_penalty(self):
        r=image_availability(doc(),[])
        self.assertEqual(r["status"],"image_not_collected_by_policy")
        self.assertEqual(r["absence_quality_penalty"],0)

    def test_observation_separate_from_body_and_interpretation(self):
        n=normalize_notes(doc(),[note()])[0]
        self.assertEqual(n["evidence_layer"],"visual_observer_text_note")
        self.assertNotEqual(n["observations"],n["interpretations"])
        self.assertEqual(n["new_independent_experience_credit"],0)
        self.assertFalse(n["original_images_collected_by_this_pipeline"])

    def test_related_blog_photos_not_accepted(self):
        d=doc(scope="related")
        with self.assertRaisesRegex(ValueError,"only_for_walkerhill"): normalize_notes(d,[note(d)])

    def test_wrong_author_or_post(self):
        for field in ("persona_id","post_id"):
            n=note(); n[field]="WRONG"
            with self.assertRaisesRegex(ValueError,"wrong_post_or_author"): normalize_notes(doc(),[n])

    def test_note_body_version_bound(self):
        n=note(); n["body_sha256_private"]="other"
        with self.assertRaisesRegex(ValueError,"different_body_version"): normalize_notes(doc(),[n])

    def test_duplicates_not_repeat_credit(self):
        with self.assertRaisesRegex(ValueError,"duplicate_photo"): normalize_notes(doc(),[note(),note()])

    def test_visible_limits_required(self):
        n=note(); n["limitations"]=[]
        with self.assertRaisesRegex(ValueError,"limitations_required"): normalize_notes(doc(),[n])

    def test_photo_note_not_fake_text_anchor(self):
        n=note(); n["body_anchors"]=[{"span":[0,2],"quote":"사진 관측"}]
        with self.assertRaisesRegex(ValueError,"anchor_mismatch"): normalize_notes(doc(),[n])

    def test_notes_share_body_event_root(self):
        a=note(); b=note(); b["note_id"]="N2"; b["asset_ref"]="PHOTO2"
        ns=normalize_notes(doc(),[a,b])
        self.assertEqual({n["dependency_root"] for n in ns},{"E1"})
        self.assertEqual(sum(n["new_independent_experience_credit"] for n in ns),0)

    def test_visual_claim_usable_but_not_fake_memory_or_new_event(self):
        r=normalize_note_claims(doc(),normalize_notes(doc(),[note()]),[self.claim()])[0]
        self.assertEqual(r["human_review"],"pending")
        self.assertEqual(r["new_independent_experience_credit"],0)
        self.assertIn("available",r["research_use"])

    def test_missing_visual_root_rejected(self):
        with self.assertRaisesRegex(ValueError,"existing_note_roots"): normalize_note_claims(doc(),[],[self.claim()])

    def test_photo_claim_cannot_create_another_experience(self):
        c=self.claim(); c["experience_key"]="OTHER"
        with self.assertRaisesRegex(ValueError,"wrong_source_or_experience"):
            normalize_note_claims(doc(),normalize_notes(doc(),[note()]),[c])

    def test_combined_inference_needs_actual_body(self):
        c=self.claim(); c["claim_type"]="body_note_combined_inference"
        with self.assertRaisesRegex(ValueError,"body_roots"): normalize_note_claims(doc(),normalize_notes(doc(),[note()]),[c])

    def test_no_visual_probability_or_caller_approval(self):
        c=self.claim(); c["calibrated_probability"]=0.9
        with self.assertRaisesRegex(ValueError,"not_probability"): normalize_note_claims(doc(),normalize_notes(doc(),[note()]),[c])
        c=self.claim(); c.update(human_review="approved",new_independent_experience_credit=1)
        result=normalize_note_claims(doc(),normalize_notes(doc(),[note()]),[c])[0]
        self.assertEqual(result["human_review"],"pending")
        self.assertEqual(result["new_independent_experience_credit"],0)


class CoverageTest(unittest.TestCase):
    def test_reported_total_not_fake_missing_source_ids(self):
        r=audit_inventory([doc()],self.entries(),reported_totals={"NEW":{"count":5,"source_ref":"USER_REPORT"}})
        self.assertEqual(r["authors"]["NEW"]["reported_sources_not_yet_identified"],3)
        self.assertEqual(r["authors"]["NEW"]["known_text_gaps"],["S2"])
        self.assertIsNone(r["full_search_recall"])
    def entries(self):
        return [{"source_id":"S1","persona_id":"NEW","document_post_id":"T1","discovery_basis":"current_source_ledger"},
                {"source_id":"S2","persona_id":"NEW","discovery_basis":"provided_link_only"}]

    def test_known_missing_body_no_inference(self):
        r=audit_inventory([doc()],self.entries())
        self.assertEqual(r["authors"]["NEW"]["known_text_gaps"],["S2"])
        self.assertIsNone(r["full_search_recall"])
        self.assertFalse(r["full_search_inventory_supplied"])

    def test_search_complete_needs_provenance(self):
        with self.assertRaisesRegex(ValueError,"provenance_required"): audit_inventory([doc()],self.entries(),search_complete=True)

    def test_duplicate_source_not_two_posts(self):
        items=self.entries()
        with self.assertRaisesRegex(ValueError,"duplicate_discovery"): audit_inventory([doc()],[items[0],items[0]])

    def test_unknown_or_cross_author_document_rejected(self):
        items=self.entries(); items[0]["persona_id"]="OTHER"
        with self.assertRaisesRegex(ValueError,"mismatch"): audit_inventory([doc()],items)

    def test_two_source_ids_cannot_duplicate_same_current_post(self):
        items=self.entries(); items[1]["document_post_id"]="T1"
        with self.assertRaisesRegex(ValueError,"two_discoveries"): audit_inventory([doc()],items)

    def test_other_hotels_not_walkerhill_coverage(self):
        with self.assertRaisesRegex(ValueError,"masquerade"): audit_inventory([doc(scope="related")],self.entries())


class FrozenStudyTest(unittest.TestCase):
    def test_private_raw_input_cannot_be_stored_in_git(self):
        with self.assertRaisesRegex(ValueError,"outside_git"):
            private_path(Path(__file__).parent)

    def test_private_output_refuses_to_overwrite_original(self):
        with tempfile.TemporaryDirectory() as root:
            path=save_private(root,"sample.json",{"synthetic":True})
            with self.assertRaises(FileExistsError): save_private(root,"sample.json",{})
            self.assertEqual(json.loads(path.read_text()),{"synthetic":True})

    def test_private_output_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            path=save_private(root,"sample.json",{})
            self.assertEqual(path.stat().st_mode&0o777,0o600)

    def test_private_output_name_cannot_escape_directory(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"local_to_directory"): save_private(root,"../escape.json",{})

    def test_raw_source_required_not_old_card(self):
        d=doc(); d["source_class"]="approved_card"
        with self.assertRaisesRegex(ValueError,"not_cards"): prepare_requests([d],author_role="holdout_new_author")

    def test_no_profile_from_title_only(self):
        d=doc(); d["text"]=""
        with self.assertRaisesRegex(ValueError,"full_text"): require_corpus([d])

    def test_explicit_author_group_required(self):
        with self.assertRaisesRegex(ValueError,"one_explicit_author"): require_corpus([doc(),doc("T2",persona="OTHER")])

    def test_caller_added_answers_and_evaluator_notes_never_pass(self):
        d=doc(); d.update(gold="FORBIDDEN_GOLD",action_hypothesis="FORBIDDEN_CHOICE",reviewer_notes="FORBIDDEN_REVIEW")
        packet=prepare_requests([d],author_role="holdout_new_author")
        serialized=json.dumps(packet["requests_private"],ensure_ascii=False)
        for marker in ("FORBIDDEN_GOLD","FORBIDDEN_CHOICE","FORBIDDEN_REVIEW"):
            self.assertNotIn(marker,serialized)

    def test_same_input_hash_across_repeats_and_no_execution(self):
        p=prepare_requests([doc()],author_role="holdout_new_author"); a,b=p["requests_private"]
        self.assertEqual(a["input_sha256_private"],b["input_sha256_private"])
        self.assertEqual(p["actual_model_executions"],0)
        self.assertFalse(p["independent_quality_established"])

    def test_repeats_do_not_share_mutable_inputs(self):
        p=prepare_requests([doc()],author_role="holdout_new_author"); a,b=p["requests_private"]
        a["model_input_private"]["document"]["full_text"]="changed"
        self.assertNotEqual(a["model_input_private"],b["model_input_private"])

    def test_same_method_across_two_authors(self):
        a=prepare_requests([doc(persona="ONE")],author_role="transfer_check_prior_research")
        b=prepare_requests([doc(persona="TWO")],author_role="holdout_new_author")
        self.assertEqual(a["method"],b["method"])
        self.assertFalse(a["method"]["capacity_competition_supported"])

    def test_v41_prompt_and_policy_hash_unchanged(self):
        r=frozen_method()
        self.assertEqual(r["base_prompt_sha256"],sha256((ROOT/"author_method_v4_1"/"EXTRACTION_PROMPT.md").read_bytes()).hexdigest())

    def test_profile_scope_exclusion_does_not_send_private_irrelevance(self):
        d=doc(); d["profile_scope_excluded"]=True
        r=prepare_requests([d],author_role="holdout_new_author")
        self.assertFalse(r["requests_private"])
        self.assertEqual(r["excluded_source_posts"],["T1"])

    def test_import_keeps_semantic_review_pending(self):
        p=prepare_requests([doc()],author_role="holdout_new_author"); req=p["requests_private"][0]
        r={"post_id":"T1","input_sha256_private":req["input_sha256_private"],"actual_model_id":"SYNTHETIC_FAKE",
           "actual_session_ref":"SYNTHETIC_SESSION","isolation_description":"unit test only","facts":[fact()]}
        out=validate_import(p,req["request_id"],r)
        self.assertEqual(out["semantic_review"],"pending")
        self.assertEqual(out["normalized_private"]["source_class"],"synthetic_fixture")

    def test_changed_prepared_input_rejected(self):
        p=prepare_requests([doc()],author_role="holdout_new_author"); req=p["requests_private"][0]
        req["model_input_private"]["document"]["full_text"]="changed"
        with self.assertRaisesRegex(ValueError,"mutated"): validate_import(p,req["request_id"],{})


class SemanticReviewTest(unittest.TestCase):
    def test_cross_author_reference_or_output_rejected(self):
        f=fact(); f["persona_id"]="OTHER"; r=submitted([f])
        with self.assertRaisesRegex(ValueError,"author_or_source_scope"): semantic_summary([f],inventory(),r)
    def test_developer_62_not_independent_labels(self):
        refs=inventory(); refs["origin"]="developer_selected_62"
        r=semantic_summary([fact()],refs,review_template([fact()],refs))
        self.assertIsNone(r["semantic_metrics"])

    def test_pending_human_review_has_no_semantic_metric(self):
        template=review_template([fact()],inventory())
        self.assertIsNone(template["effort_log"]["collection_minutes"])
        self.assertTrue(all(p["compensation_status"] is None for p in template["post_adjudications"]))
        r=semantic_summary([fact()],inventory(),template)
        self.assertIsNone(r["semantic_metrics"])

    def test_changed_reference_inventory_rejected(self):
        refs=inventory(); review=review_template([fact()],refs); refs["units"]=[]
        with self.assertRaisesRegex(ValueError,"changed_after"): semantic_summary([fact()],refs,review)

    def test_coverage_from_semantic_judgments_not_window_hit(self):
        refs=inventory(); r=semantic_summary([fact()],refs,submitted([fact()],refs))
        self.assertEqual(r["semantic_metrics"]["reviewed_inventory_coverage"],0.5)
        self.assertEqual(r["semantic_metrics"]["candidate_supported_fraction"],1)
        self.assertFalse(r["independent_quality_established"])
        self.assertFalse(r["demo_approved"])

    def test_duplicate_candidates_do_not_increase_reference_coverage(self):
        fs=[fact(),fact("T2")]; r=semantic_summary(fs,inventory(),submitted(fs))
        self.assertEqual(r["semantic_metrics"]["covered_reference_units"],1)
        self.assertEqual(r["semantic_metrics"]["duplicate_supported_candidates"],1)

    def test_supported_cannot_have_wrong_actor(self):
        r=submitted([fact()]); r["rows"][0]["actor_correct"]=False
        with self.assertRaisesRegex(ValueError,"conflicts_with_error"): semantic_summary([fact()],inventory(),r)

    def test_missing_actions_require_explicit_judgment(self):
        r=submitted([fact()]); r["missing_reference_ids"]=[]
        with self.assertRaisesRegex(ValueError,"missing_actions"): semantic_summary([fact()],inventory(),r)

    def test_all_candidates_need_actual_judgment(self):
        r=submitted([fact()]); r["rows"]=[]
        with self.assertRaisesRegex(ValueError,"each_candidate"): semantic_summary([fact()],inventory(),r)

    def test_pending_semantic_stability_not_fabricated(self):
        review=review_template([fact()],inventory())
        r=compare_reviewed_runs([fact()],[fact()],inventory(),review,review)
        self.assertIsNone(r["reviewed_reference_coverage_jaccard"])

    def test_reviewed_stability_not_os_independence(self):
        review=submitted([fact()]); r=compare_reviewed_runs([fact()],[fact()],inventory(),review,review)
        self.assertEqual(r["reviewed_reference_coverage_jaccard"],1)
        self.assertFalse(r["session_independence_verified"])
        self.assertFalse(r["all_free_traits_semantically_compared"])


if __name__=="__main__":
    unittest.main()
