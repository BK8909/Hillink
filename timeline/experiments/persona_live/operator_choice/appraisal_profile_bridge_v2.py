"""Bridge appraisal outputs into profiles without promoting reviewer leads or local events to traits."""
from copy import deepcopy
from .contextual_appraisal_v2 import aggregate_stable_traits

def attach(profile: dict, appraisals: list[dict]) -> dict:
    result=deepcopy(profile)
    result["contextual_appraisals"] = [deepcopy(x) for x in appraisals]
    result["derived_appraisal_traits"] = aggregate_stable_traits(appraisals)
    result["appraisal_bridge_status"] = "local_appraisals_attached_stable_traits_require_verified_distinct_stays"
    return result

def blog41_review_leads(profile: dict) -> list[dict]:
    """Unscored #90 reviewer claims; not raw quotes, source-verified memories, or model context."""
    return [{"source_id":x["review_id"],"target":x["aspect"],"polarity":"unknown","valence_score":None,
      "evidence_strength":None,"interpretation_confidence":"not_assessed","inference_level":"D3",
      "source_status":"reviewer_report_anchor_pending","decision_usable":False,
      "note":"원문 문장 미확인; 경수/슬기 교차 확인 전 모델 입력과 프로필 성향에 사용 금지."}
      for x in profile.get("evaluated_experiences", [])]

def blog41_appraisal_candidates(profile: dict) -> list[dict]:
    """Paraphrased leads from reviewed derivatives; not outputs of raw-text inference."""
    rows=[{"source_id":"r011:skyard", "target":"SKYARD_visit_experience", "polarity":"positive",
      "valence_score":1,"evidence_strength":3,"interpretation_confidence":"moderate",
      "inference_level":"D1", "scope":"this_facility_visit_only",
      "source_status":"human_checked_persona_truth_summary_raw_anchor_not_reopened",
      "contextual_reasoning":"검수된 방문 요약에 해당 시설 이용에 대한 강한 긍정 표현이 기록됨. 이 시설의 해당 체험에 국한.",
      "alternative_readings":["해당 체험의 일부 요소만 긍정일 수 있음"],
      "behavioral_implication":"SKYARD 유사 활동 비교에서 약한 참고; 재방문 의향·모든 시설 선호는 아님.",
      "decision_usable":False,"raw_text_stored":False}]
    rows.extend(blog41_review_leads(profile))
    return rows
