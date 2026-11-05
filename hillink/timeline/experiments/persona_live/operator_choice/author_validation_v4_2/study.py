"""Prepare private fixed-input requests for source extraction, never execute them.

Same prompt/policy for new authors; no 62 developer labels, lexical candidates,
old cards, behavior choices or evaluator opinions are passed to an extractor.
"""
from pathlib import Path
from copy import deepcopy

from ..author_method_v4_1 import VERSION as BASE_VERSION
from ..author_method_v4_1.linking import link_experiences
from .common import digest, private_document, require_corpus
from .photo_notes import normalize_notes, normalize_note_claims

SOURCE_ROOT=Path(__file__).parent.parent/"author_method_v4_1"
NOTE_GUIDE="""
선택적 시각 관찰 메모에 관한 공통 추가 규칙:
선택적 사진 관찰 메모가 있으면 본문과 별도의 visual_observer_text_note 층이다.
메모의 관측과 메모 작성자의 해석을 구분하고, 메모를 원문 본문 인용으로 쓰지 않는다.
동일 experience_key의 글·사진·영수증은 독립 반복으로 가산하지 않는다.
화면 밖의 인원·관계·결제자·음주를 만들지 않는다. 사진 메모 없음은 감점하지 않는다.
행동 정답이나 성향 점수 없이 게시글의 세부 사실·평가·추론을 먼저 보존한다.
""".strip()


def frozen_method():
    prompt=(SOURCE_ROOT/"EXTRACTION_PROMPT.md").read_text()
    return {"base_version":BASE_VERSION,"base_prompt_sha256":digest(prompt),
            "effective_prompt_sha256":digest(prompt+"\n\n"+NOTE_GUIDE),
            "aggregation_policy_sha256":digest((SOURCE_ROOT/"policy.json").read_text()),
            "profile_scoring_modified":False,"capacity_competition_supported":False}


def prepare_requests(documents, *, author_role, notes_by_post=None):
    require_corpus(documents)
    if author_role not in {"method_development","transfer_check_prior_research","holdout_new_author"}:
        raise ValueError("declared_evaluation_role_required")
    notes_by_post=notes_by_post or {}
    if not set(notes_by_post) <= {d["post_id"] for d in documents}:
        raise ValueError("photo_note_post_not_in_corpus")
    prompt=(SOURCE_ROOT/"EXTRACTION_PROMPT.md").read_text()+"\n\n"+NOTE_GUIDE
    requests=[]; excluded=[]
    for document in sorted(documents,key=lambda d:d["post_id"]):
        if document.get("profile_scope_excluded",False):
            excluded.append(document["post_id"])
            continue
        model_input={"system":prompt,"document":private_document(document),
                     "selected_photo_observer_notes":normalize_notes(document,notes_by_post.get(document["post_id"],[])),
                     "output_contract":{"facts":"V4.1 body-source facts with exact text anchors",
                                        "visual_note_claims":"Separate note-rooted observation/inference or combined body+note inference; never fake body quotes"}}
        # Operational reviewer state is provenance, not a reviewer opinion.
        for note in model_input["selected_photo_observer_notes"]:
            note.pop("human_review",None)
        request_hash=digest(model_input)
        for repeat in ("A","B"):
            requests.append({"request_id":f"{document['post_id']}_EXTRACT_{repeat}","post_id":document["post_id"],
                             "repeat":repeat,"input_sha256_private":request_hash,"model_input_private":deepcopy(model_input),
                             "execution":"not_executed","session_isolation":"not_executed_not_asserted"})
    return {"persona_id":documents[0]["persona_id"],"source_class":documents[0]["source_class"],"author_role":author_role,"method":frozen_method(),
            "requests_private":requests,"excluded_source_posts":excluded,"contains_private_source":True,
            "source_post_count":len(documents),"prepared_post_count":len(requests)//2,
            "planned_repeat_count":2,"actual_model_executions":0,"actual_behavior_executions":0,
            "product_api_calls":0,"human_review":"pending","demo_approved":False,
            "independent_quality_established":False,"approval_required_before_external_execution":True}


def validate_import(packet, request_id, response):
    """Identity/hash binding only. Structural alignment is checked separately.

    A submitted extractor result is not called semantically correct or reviewed.
    No retry, model call, response correction or profile registration is done.
    """
    expected=next((r for r in packet["requests_private"] if r["request_id"]==request_id),None)
    if expected is None:
        raise ValueError("unknown_extraction_request")
    if digest(expected["model_input_private"]) != expected["input_sha256_private"]:
        raise ValueError("prepared_input_mutated")
    if response.get("input_sha256_private") != expected["input_sha256_private"]:
        raise ValueError("response_input_hash_mismatch")
    if not response.get("actual_model_id") or not response.get("actual_session_ref") or not response.get("isolation_description"):
        raise ValueError("actual_model_session_isolation_record_required")
    if response.get("post_id") != expected["post_id"]:
        raise ValueError("response_wrong_post")
    if not isinstance(response.get("facts"),list):
        raise ValueError("structured_extraction_facts_required")
    document=expected["model_input_private"]["document"]
    from ..author_method_v4_1.contract import normalize_facts
    source_class="synthetic_fixture" if packet.get("source_class")=="synthetic_fixture" else "authorized_text"
    normalized=normalize_facts({**document,"text":document["full_text"],"source_class":source_class},response["facts"])
    supplemental=normalize_note_claims({**document,"text":document["full_text"]},expected["model_input_private"]["selected_photo_observer_notes"],response.get("visual_note_claims",[]))
    return {"normalized_private":normalized,"structural_status":"source_spans_checked_only","semantic_review":"pending",
            "visual_note_claims_private":supplemental,
            "session_isolation":"caller_reported_not_os_verified","profile_approved":False,"demo_approved":False}


def recurrence_review(facts, assertions):
    # Reuse V4.1's frozen semantics; never create a new visit from post count.
    return link_experiences(facts,assertions)
