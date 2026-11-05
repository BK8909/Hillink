"""Reproducible SYNTHETIC pipeline exercise; real blog41 source files pending."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from time import perf_counter

from .aggregation import aggregate, compare_scopes, shareable_stage_a
from .comparison import compare_media_profiles
from .extraction import draft_extract
from .fixtures import four_author_corpora
from .plans import build_plan_candidates, fictional_wine_environment

HERE = Path(__file__).parent
OUT = HERE.parent / "text_first_v4_artifacts"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run():
    result = {"version": "text_first_v4_synthetic_study_0.1", "data_class": "synthetic_fixture_only",
              "real_authors_processed": 0, "real_posts_read": 0, "LLM_extraction_calls": 0, "LLM_behavior_calls": 0,
              "human_reviews": 0, "demo_approved": False, "authors": {}}
    for author, corpus in four_author_corpora().items():
        stage_a = [draft_extract(doc, links) for doc, links in corpus]
        profile = aggregate(stage_a)
        # Availability-only placebo: no image was read or extra evidence added.
        placebo = deepcopy(stage_a)
        for post in placebo:
            post["media_status"] = "selected_image_available"
        result["authors"][author] = {"stage_A": [shareable_stage_a(post) for post in stage_a],
                                      "stage_B": profile, "three_scope_comparison": compare_scopes(stage_a),
                                      "media_availability_placebo": compare_media_profiles(profile, aggregate(placebo)),
                                      "fictional_plan_candidates": build_plan_candidates(profile, fictional_wine_environment())}
    result["source_availability"] = {
        "existing_blog41_V3": "preserved_legacy_summary_not_raw_text_input_for_this_study",
        "walkerhill_reviews_from_links.xlsx": {"reported_posts": 7, "local_file_status": "not_supplied_in_accessible_environment", "read_posts": 0},
        "walkerhill_reviews_from_links(1).xlsx": {"reported_posts": 50, "local_file_status": "not_supplied_in_accessible_environment", "read_posts": 0},
        "blog41_three_scope_real_comparison": "pending_authorized_text_files_not_generated",
        "real_3_to_5_author_pilot": "pending_sources_and_extraction_review"}
    return result


def render(result):
    labels = {"new_experience_trial": "새 경험 시도", "premium_experience": "프리미엄 경험", "food_engagement": "식음 참여", "space_atmosphere": "공간·분위기",
              "seasonal_event_engagement": "시즌 행사", "discount_utilization": "할인 활용", "alcohol_familiarity": "음주 경험", "post_value_appraisal": "사후 가치 평가"}
    lines = ["# Text-First V4 — 합성 4작성자 검수 패킷", "", "**아래 고객은 모두 만들어진 테스트 사례다. 실제 고객 추출 정확도·실제 blog41 V4·사람 검수 결과가 아니다.**", "",
             "| 합성 작성자 | 입력 범위 | " + " | ".join(labels.values()) + " |", "|---|---|" + "---:|" * len(labels)]
    for author, output in result["authors"].items():
        for name, cell in output["three_scope_comparison"].items():
            traits = cell["profile"]["derived_traits"]
            lines.append(f"| {author} | {name} | " + " | ".join(str(traits[t]["strength_score"]) for t in labels) + " |")
    lines.extend(["", "각 점수는 0~12의 초기 공통 정책 지표다. 독립 근거 수·가점·상한·반대 사례는 results.json에서 추적한다. 확률·실제 인격 점수·고객 간 정확도 순위가 아니다.", "",
                  "## 단계별 확인", "", "- A: 원문 전체 → 실제 참여/구매/동기/평가/대안 후보, 정확한 span, 광고 신호. 원문·원문 해시·중복 확인용 내용 해시는 공유 출력에서 제외한다.",
                  "- B: 동일 사건 통합 → 방문 반복·종류 다양성 → 성향 강도와 근거량 분리. 모르는 방문 연결은 반복 보너스를 받지 않지만 단일 맥락 단서는 사용한다.",
                  "- 계획: 행사 후 식사 / 간단 시음 후 식사 / 불참 후 객실 식사를 후보로 구성. 선택 완료·실제 이용·독립 LLM 행동은 생성하지 않았다.",
                  "- 이미지 가용성 플래그만 바꾼 대조에서는 성향 점수가 동일하다. 이것은 무감점 검사이지 이미지의 실제 기여도 측정이 아니다.", "",
                  "## 사람 검수 — 실제 자료 확보 후", "", "| 작성자·근거 | 행동 추출 누락/오류 | 중복·방문 연결 | 추론 범위·반대 사례 | 광고 처리 | 수정 이유·검수자 |", "|---|---|---|---|---|---|",
                  "| 실제 표본 1~5 | 미실행 | 미실행 | 미실행 | 미실행 | 미검수 |", "",
                  "실제 표본은 3~5명의 서로 다른 작성자여야 한다. 동일 작성자 3개 입력 범위는 3명으로 세지 않는다. 원문 span 검수는 제한 저장소에서 수행한다.", "",
                  "## 이미지 기여도 — 별도 짝 비교", "", "같은 작성자·같은 글·같은 통합 정책 아래 텍스트만/선별 사진 추가를 비교한다. 유효 추가 근거, 오추론 증감, 선택·설명 검수, 수집·검수 시간, 저장 바이트를 기록한다. 이번에는 사진을 보지 않아 모두 미측정이다. 사진 부재를 프로필 결함으로 처리하지 않는다.", ""])
    return "\n".join(lines)


def _new(path, value):
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text() != content:
        raise FileExistsError("versioned_artifact_must_not_be_overwritten:" + path.name)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def write():
    started = perf_counter()
    result = run()
    elapsed = perf_counter() - started
    old = HERE.parent
    preserve = [old / "profile_v3_artifacts/blog41_author_profile_v3.json", old / "persona_profile_v4_draft.schema.json", old / "persona_v4_contract.py"]
    for name in ("dynamic_wine_v1_artifacts", "dynamic_wine_v1_1_artifacts", "causal_p0_artifacts", "v11_audit_artifacts"):
        preserve.extend(sorted((old / name).rglob("*.json")))
    preserve.extend(old / n for n in ("dynamic_operating_choice_v1.py", "dynamic_operating_choice_v1_1.py", "dynamic_operating_policy_v1.json", "dynamic_operating_policy_v1_1.json"))
    manifest = {"version": result["version"], "baseline_commit": "b89ff4dcd0d50f43084c82a7fb46f1bbc06aab7c",
                "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.iterdir()) if p.suffix in {".py", ".json", ".md"}},
                "preserved_sha256": {str(p.relative_to(old)): hashlib.sha256(p.read_bytes()).hexdigest() for p in preserve},
                "result_sha256": digest(result), "source_class": "synthetic_fixture_only", "real_posts_processed": 0,
                "model_calls": 0, "human_review": "pending", "demo_approved": False}
    _new(OUT / "results.json", result)
    _new(OUT / "REVIEW_PACKET.md", render(result))
    _new(OUT / "manifest.json", manifest)
    return {"result_sha256": manifest["result_sha256"], "manifest_sha256": digest(manifest),
            "synthetic_authors": len(result["authors"]), "synthetic_posts": sum(len(a["stage_A"]) for a in result["authors"].values()),
            "offline_synthetic_elapsed_seconds": round(elapsed, 6), "real_posts_processed": 0, "model_calls": 0}


if __name__ == "__main__":
    print(json.dumps(write(), ensure_ascii=False))
