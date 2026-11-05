"""Post-merge audit and blank off/on review assets. Never generates behavior.

python3 -m operator_choice.demo_readiness --write NEW_DIRECTORY
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unicodedata

from .causal_p0 import make_plan, packet_hash
from .rules import digest
from .session_exchange import load_frozen, comparison_worksheet, replay_manifest
from .session_phase_gate import phase_request, check_authority
from .team_followup_audit import PR_HEADS
from .team_followup_guard import inspect_model_input, vista_party_sensitivity

ROOT = Path(__file__).resolve().parents[4]
START = "67de104f6ce5cfc9ef19b0d5e62ae29458429655"
COMMON = "1dee647d32a24c64eaa715221f7f0ae059381c1a"
RESTRICTED_NAMES = ("열람기록_전체.csv", "아카이브대조_후보23_제한공유_1021.xlsx",
                    "아카이브_대조표.csv", "블로그_수집_항목별_아카이브.xlsx")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()


def merged_documents():
    docs = []
    for pr, head in PR_HEADS.items():
        paths = git("-c", "core.quotePath=false", "diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines()
        # Submitted commits are document-only, checked against merged public blobs.
        for path in paths:
            submitted = git("rev-parse", head + ":" + path)
            merged = git("rev-parse", COMMON + ":" + path)
            docs.append({"pr": pr, "path": path, "submitted_blob": submitted,
                         "common_blob": merged, "identical": submitted == merged})
    ancestor = git("merge-base", START, COMMON)
    common_paths = set(git("-c", "core.quotePath=false", "diff", "--name-only", ancestor, COMMON).splitlines())
    research_paths = set(git("-c", "core.quotePath=false", "diff", "--name-only", ancestor, START).splitlines())
    return {"common_sha": COMMON, "research_start_sha": START, "common_ancestor": ancestor,
            "research_common_exclusive_commit_counts": git("rev-list", "--left-right", "--count", START + "..." + COMMON).split(),
            "documents": docs, "file_overlap_since_ancestor": sorted(common_paths & research_paths),
            "common_merged_into_research": False, "documents_copied_into_research": False}


def restricted_file_availability():
    """Filename-only discovery; never opens CSV, spreadsheets, URLs or bodies."""
    roots = [Path("/Users/tk/Downloads/워커힐"), Path("/Users/tk/Downloads/hillink-walkerhill-sim")]
    wanted = {unicodedata.normalize("NFC", name) for name in RESTRICTED_NAMES}
    found = set()
    scanned = 0
    errors = []
    for root in roots:
        if not root.exists():
            continue
        for _, dirs, files in os.walk(root, onerror=lambda e: errors.append(type(e).__name__)):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", ".venv", "venv", "__pycache__"}]
            scanned += 1
            found.update(wanted & {unicodedata.normalize("NFC", f) for f in files})
    return {"search_root_count": len(roots), "directories_scanned": scanned,
            "found_basenames": sorted(found), "missing_basenames": sorted(wanted - found),
            "read_errors": sorted(set(errors)), "file_contents_opened": False,
            "author_stay_mapping": "approved_location_and_filename_still_required"}


def protected_snapshot():
    prefixes = ["timeline/group_inputs_v1", "timeline/experiments/persona_live/runs",
                "timeline/experiments/persona_live/demo", "timeline/viewer",
                "timeline/experiments/persona_live/operator_choice/artifacts",
                "timeline/experiments/persona_live/operator_choice/method_v1_artifacts",
                "timeline/experiments/persona_live/operator_choice/method_v1_1_artifacts",
                "timeline/experiments/persona_live/operator_choice/causal_p0_artifacts"]
    changed = git("-c", "core.quotePath=false", "diff", "--name-only", START, "--", *prefixes).splitlines()
    trees = {p: git("rev-parse", START + ":" + p) for p in prefixes}
    return {"baseline": START, "tree_objects": trees, "working_tree_changes": changed,
            "sealed_gold_policy": "not_opened_or_modified; full changed-file allowlist checked separately"}


def audit():
    plan = load_frozen()
    rebuilt = make_plan()
    scans = {name: inspect_model_input(packet) for name, packet in plan["packets"].items()}
    errors = []
    for name, packet in plan["packets"].items():
        if packet_hash(packet) != packet["expected_input_sha256"] or packet != rebuilt["packets"][name]:
            errors.append(name)
    return {"version": "postmerge_demo_readiness_v1", "branches": merged_documents(),
            "protected": protected_snapshot(), "restricted_files": restricted_file_availability(),
            "frozen_packet_count": len(plan["packets"]), "whole_plan_reproduces": plan == rebuilt,
            "packet_mismatches": errors, "exact_id_scan": scans,
            "request_set_sha256": plan["approval"]["request_set_sha256"], "phase1": phase_request(plan, 1),
            "phase1_authority_errors_without_approval": check_authority(plan, 1, {}),
            "schema_characters_phase1": sum(len(json.dumps(plan["packets"][r["name"]]["output_schema"], ensure_ascii=False, sort_keys=True))
                                             for r in phase_request(plan, 1)["requests"]),
            "blog59_admission_sensitivity": {p: vista_party_sensitivity(2, [None, None, None], policy=p)
                for p in ("experimental_all_admitted", "official_conditions_only")},
            "new_independent_sessions": 0, "original_text_direct_checks": 0,
            "human_reviews_completed": 0, "demo_approved": 0, "product_API_calls": 0,
            "session_cost": None, "exact_token_usage": None}


def worksheet_markdown(sheet):
    text = ["# 대표 3명 OFF/ON 검수 준비표", "",
            "신규 실행 0건. 선택·이유·사람 판정은 아직 없다. 아래 자료는 생성 세션에 제공하지 않는 평가자 전용이다.", "",
            "기존 3응답 원형과 상세 검수는 `../causal_p0_artifacts/review/HUMAN_REVIEW_PACKET.md`를 참조한다.", "",
            "카드의 관측 표기는 원문 직접 검증 완료를 의미하지 않는다. 현재 목적은 미상, 지속은 미가정이다.", ""]
    for customer in ("blog59", "blog25", "blog43"):
        rows = [r for r in sheet["rows"] if r["customer_id"] == customer]
        text += ["## " + customer, "", "| 검수 항목 | OFF | ON |", "|---|---|---|"]
        for label, key in (("실제 생성", "generation_status"), ("선택", "choice"), ("포기한 대안", "alternatives"),
                           ("새 추론", "new_inference")):
            text += ["| " + label + " | " + " | ".join(str(r[key]) if r[key] is not None else "미생성" for r in rows) + " |"]
        text += ["", "과거 경험·평가 요약(두 환경 동일, 원문 앵커 미확인):", ""]
        for e in rows[0]["historical_experience"]:
            text += [f"- {e['kind']} / {e['source_layer']}: {e['statement']} (`{', '.join(e['evidence_ids'])}`)"]
        text += ["", "과거 목적 요약(현재 의사 아님):", ""]
        for e in rows[0]["past_purpose_not_current_intent"]:
            text += [f"- {e['source_layer']}: {e['statement']} (`{', '.join(e['evidence_ids'])}`)"]
        text += ["", "현재 조건: 여름·15:30~17:00 동일 블록, ON에만 RIVERPARK 선택지 추가. 일행·날씨·가격 조건 동일.",
                 "입장 가능은 CTX-ADMISSION 실험 가정이며 실제 호텔 자격 확인이 아니다. 아동 나이·현재 피로·현재 목적·일행 총비용은 미상.",
                 "", "사람 검수: 구조/ID · 개인 사실 · 행동 개연성 · 목적 적용 · 새 추론 범위 · 대안 비교 모두 미판정.",
                 "", "검수 질문: 이용 사실을 만족으로 바꿨는가? 목적 지속을 확정했는가? 수영·산책·휴식에 같은 불확실성 기준을 적용했는가?", ""]
    return "\n".join(text).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", type=Path, required=True)
    args = ap.parse_args()
    args.write.mkdir(parents=True, exist_ok=False)
    result = audit()
    sheet = comparison_worksheet(load_frozen())
    for name, obj in (("readiness.json", result), ("phase1_review_worksheet.json", sheet),
                      ("reviewed_replay_manifest.json", replay_manifest(load_frozen()))):
        (args.write / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.write / "PHASE1_REVIEW.md").write_text(worksheet_markdown(sheet), encoding="utf-8")
    print(json.dumps({"frozen_packets": result["frozen_packet_count"], "whole_plan_reproduces": result["whole_plan_reproduces"],
                      "common_documents": len(result["branches"]["documents"]), "new_sessions": 0,
                      "phase1_sha256": result["phase1"]["phase_sha256"]}))


if __name__ == "__main__":
    main()
