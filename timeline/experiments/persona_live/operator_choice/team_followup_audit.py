"""Read public Git metadata and optional local CSV registries, never sealed text.

python3 -m operator_choice.team_followup_audit --write operator_choice/team_followup_artifacts
Local registries are optional; only counts/booleans/file fingerprints are exported.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

from .experiment import write_new
from .rules import digest
from .team_followup_guard import release_preview, inspect_model_input
from .session_phase_gate import phase_request, check_authority

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
COMMON = "45219f94c3b7f94aeacb4ac65940348aa0a7bbc9"
PR_HEADS = {90: "57f7e0939c802fccfaa3918b7ed30ee62381afb3", 91: "01aa021c514a782cd53024fac6be9bb2a42223e3"}
LIBRARY = "f798373"
TARGET = "REV-bea98b3d8f343905fd1f"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def document_audit():
    prs = []
    research_paths = set(git("-c", "core.quotePath=false", "diff", "--name-only", COMMON + "...68db05b").decode().splitlines())
    for number, head in PR_HEADS.items():
        paths = git("-c", "core.quotePath=false", "diff", "--name-only", COMMON + "..." + head).decode().splitlines()
        docs = [git("show", head + ":" + p).decode() for p in paths]
        base = git("merge-base", COMMON, head).decode().strip()
        trial = git("merge-tree", base, COMMON, head).decode()
        prs.append({"number": number, "head": head, "base": "merge/validator-0923", "checked_common_sha": COMMON,
                    "files": [{"path": p, "blob": git("rev-parse", head + ":" + p).decode().strip()} for p in paths],
                    "all_markdown": all(p.endswith(".md") for p in paths),
                    "read_only_merge_tree_conflict_markers": bool(re.search(r"^<{7}|^>{7}", trial, re.M)),
                    "overlap_with_research_paths": sorted(set(paths) & research_paths),
                    "raw_blog_url_pattern": any(re.search(r"https?://(?:m\.)?blog\.naver\.com|https?://[^\s/]*tistory\.com", t) for t in docs),
                    "merge_authority": "awaiting_user_approval", "merged_this_stage": False})
    source = git("show", PR_HEADS[91] + ":docs/아카이브대조_시연후보_소연_1021저녁.md").decode()
    candidates = re.findall(r"^\| (H\d{2}) \|", source, re.M)
    pairs = re.findall(r"^\| (P\d) \|", source, re.M)
    checks = {"candidate_rows": len(candidates) == len(set(candidates)) == 23,
              "pair_rows": len(pairs) == len(set(pairs)) == 5,
              "archive_composition": 543 + 680 + 980 == 2203,
              "body_status": 2126 + 58 + 19 == 2203,
              "shortage_rows": 61 + 19 + 9 + 2 == 91 and 20 + 17 + 54 == 91,
              "read_fragments": 119 + 112 + 86 == 317,
              "outside_archive": 105 + 162 == 267 and 49 + 162 == 211,
              "exclusion_precedence": sum([77, 7, 39, 14, 7, 133, 144, 46, 344, 1392]) == 2203,
              "candidate_partitions": 8 + 13 + 2 == 23 and 12 + 11 == 23}
    preserved = []
    prefix = "docs/data/persona_afternoon_review_shh_20261021/"
    for name in ("human_review_1021_v1.1_한호_판정기준보완본.xlsx", "한호_1021_오후검수_결과및판정기준_보완본.md"):
        path = prefix + name
        preserved.append({"path": path, "common_blob": git("rev-parse", COMMON + ":" + path).decode().strip(),
                          "pr89_blob_same": git("rev-parse", "6fb2934:" + path) == git("rev-parse", COMMON + ":" + path)})
    return {"prs": prs, "pr91_document_arithmetic": checks, "arithmetic_is_not_independent_archive_verification": True,
            "pr89_original_files": preserved}


def library_audit():
    meta = json.loads(git("show", LIBRARY + ":timeline/experiments/persona_live/library_ext/data/public/reviews_meta.json"))
    lib = json.loads(git("show", LIBRARY + ":timeline/experiments/persona_live/demo/library.json"))
    detail = json.loads(git("show", LIBRARY + ":timeline/experiments/persona_live/demo/library_detail.json"))
    t = next(r for r in meta["records"] if r["review_id"] == TARGET)
    current = []
    for ref in ("68db05b", COMMON):
        data = json.loads(git("show", ref + ":timeline/experiments/persona_live/demo/library.json"))
        current.append({"ref": ref, "items": len(data["items"]), "target_present": any(i["id"] == TARGET for i in data["items"])})
    paths = [HERE.parent / "runs/demo_1", HERE / "artifacts", HERE / "method_v1_artifacts/session_responses",
             HERE / "method_v1_1_artifacts/fresh_session_packets", HERE / "causal_p0_artifacts/packets"]
    scanned, hits = 0, []
    for directory in paths:
        for path in directory.rglob("*.json"):
            scanned += 1
            if not inspect_model_input(json.loads(path.read_text(encoding="utf-8")))["pass_exact_id_check"]:
                hits.append(str(path.relative_to(ROOT)))
    preview = release_preview(lib["items"], meta["records"])
    return {"inspected_library_ref": LIBRARY, "metadata_records": len(meta["records"]), "library_items": len(lib["items"]),
            "target": {"review_id": TARGET, "wh_id": t["wh_id"], "stage": t["stage"], "split": t["split"],
                       "library_ready": next(i["ready"] for i in lib["items"] if i["id"] == TARGET),
                       "detail_exists": TARGET in detail,
                       "same_author_records_within_543": sum(bool(t.get("author_key")) and r.get("author_key") == t.get("author_key") for r in meta["records"]),
                       "same_stay_candidates_within_543": len(t["same_stay_candidates"])},
            "public_author_key_field_count": sum(bool(r.get("author_key")) for r in meta["records"]),
            "author_key_values_exported": False, "runtime_views": current,
            "exact_id_usage_scan": {"files": scanned, "matches": hits, "scope": [str(p.relative_to(ROOT)) for p in paths],
                                    "derived_text_or_training_absence_proven": False},
            "release_guard_preview": {"mode": preview["mode"], "held": preview["held"], "allowed_count": len(preview["allowed_ids"])},
            "actual_runtime_guard_installed": False, "sealed_text_opened": False}


def local_mapping(links, exports):
    if not links or not exports:
        return {"checked": False, "reason": "optional_local_registry_paths_not_supplied"}
    module_path = ROOT / "docs/review_link_registry/registry_tool.py"
    spec = importlib.util.spec_from_file_location("registry_tool_metadata_only", module_path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with links.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with exports.open(encoding="utf-8-sig", newline="") as handle:
        split_rows = list(csv.DictReader(handle))
    chosen = [r for r in rows if r["rNNN"] == "r060"]
    matches = [module.suggested_id(r["url"]) == TARGET for r in chosen]
    return {"checked": True, "links_rows": len(rows), "export_rows": len(split_rows), "r060_links_rows": len(chosen),
            "reported_rev_matches_r060": bool(matches) and all(matches),
            "r060_test_split_marked": any(r.get("export") == "r060" and r.get("split") == "시험용" for r in split_rows),
            "links_file_sha256": hashlib.sha256(links.read_bytes()).hexdigest(),
            "export_file_sha256": hashlib.sha256(exports.read_bytes()).hexdigest(),
            "private_url_key_author_values_exported": False, "original_text_read": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", type=Path, required=True)
    ap.add_argument("--links", type=Path)
    ap.add_argument("--exports", type=Path)
    args = ap.parse_args()
    plan = json.loads((HERE / "causal_p0_artifacts/preparation_manifest.json").read_text())
    result = {"version": "team_followup_metadata_audit_v1", "research_start_head": "68db05b8e6b063d884809b738ee6a9dc9c0a3285",
              "documents": document_audit(), "library": library_audit(), "local_registry": local_mapping(args.links, args.exports),
              "restricted_read_log_317": "not_found_in_scoped_local_roots_not_independently_verified",
              "model_generation_sessions": 0, "human_behavior_reviews_completed": 0,
              "phase1": phase_request(plan, 1), "phase2": phase_request(plan, 2),
              "without_new_approval_phase1_errors": check_authority(plan, 1, {}),
              "without_new_approval_phase2_errors": check_authority(plan, 2, {})}
    write_new(args.write / "metadata_audit.json", result)
    print(json.dumps({"document_counts": [len(p["files"]) for p in result["documents"]["prs"]],
                      "arithmetic_checks": result["documents"]["pr91_document_arithmetic"],
                      "r060_mapping_confirmed": result["local_registry"].get("reported_rev_matches_r060"),
                      "new_sessions": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
