"""입력 버전 호환 처리 (10/16 · 한 번의 기록된 예외) — viewer 폴더에서 실행한다.

입력 파일이 바뀌면 다시 계산하는 것이 원칙이다(restamp.py 는 입력이 다르면 거부). 이 스크립트는 그 원칙을 없애지 않는다.
10/16 `menu.csv` 포함 칸 문구 정정(PR #50)이 계산에 영향을 주지 않음을 검증한 경우에 한해
`2e1f2ef2 → 65d4dc31` 한 쌍만 허용한다. 근거: docs/진행정리_및_작업배정_1016.md 0절 검증 기록
(상품 254줄 계산 판정 동일 · 일 계산 6개와 손님 상세 동일 · 연박 집계 10/10 · 10/21 동일 · 클라우드 사본 시험).

  1) 시험:  python3 restamp_input.py --dry-run
           → 대상 목록 restamp_input_plan.json 을 만들고 개수 · 종류를 출력 (아무 파일도 바꾸지 않음)
  2) 적용:  python3 restamp_input.py --apply --plan restamp_input_plan.json --expect N
           → 시험 때와 대상 목록 · 원본 SHA 가 하나라도 다르거나 개수가 N 이 아니면 아무것도 바꾸지 않고 멈춘다

바꾸는 것: 모델 d2a34bfd · 입력 2e1f2ef2 인 결과의 입력 칸 한 곳(파일 머리 또는 runs 안의 실행). 원래 값은 input_ver_orig 로 남긴다.
바꾸지 않는 것: 다른 버전 파일 · 다른 버전 실행 · 계산 내용 · .guests.jsonl · .cap.pkl · 진행 파일.
기록: cache/restamp_input_log_<시각>.json (적용 사유 · 원래 · 새 버전 · 파일별 바꾸기 전/뒤 SHA · 바꾼 실행 수).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import version  # noqa: E402

OLD, NEW, MODEL = "2e1f2ef2", "65d4dc31", "d2a34bfd"
REASON = ("PR #50 menu.csv 'Rest Together · 3인' 포함 칸 문구 정정 — 계산 판정(표준 요금 · 한정 상품 · 포함 끼니/라운지) 254줄 동일, "
          "일 계산 6개(10/10 · 10/21 · 10/11 · 10/14 · 변칙 an2 · 좌석 338) 결과와 손님 상세 동일, 연박 집계 10/10 · 10/21 동일. "
          "입력 변경 시 재계산 원칙의 한 번의 기록된 예외 (10/16 강경수 승인)")
CACHE = HERE / "cache"
EXTRA = [HERE / "static" / "stay_day.json"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def match(r) -> bool:
    return isinstance(r, dict) and r.get("model_ver") == MODEL and r.get("input_ver") == OLD


def scan():
    files = sorted(f for f in CACHE.glob("*.json") if not f.name.endswith("progress.json") and not f.name.startswith("restamp_input")) + EXTRA
    plan, other = [], {}
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            other["읽기 실패"] = other.get("읽기 실패", 0) + 1
            continue
        if not isinstance(d, dict):
            other["사전 아님"] = other.get("사전 아님", 0) + 1
            continue
        runs = d.get("runs") if isinstance(d.get("runs"), list) else []
        top = match(d)
        n_runs = sum(1 for r in runs if match(r))
        other_runs = [f"{r.get('model_ver')}/{r.get('input_ver')}" for r in runs if isinstance(r, dict) and not match(r)]
        if top or n_runs:
            plan.append(dict(file=str(f.relative_to(HERE)), sha=sha(f), top=top, runs=n_runs, runs_other_versions=sorted(set(other_runs)),
                             kind=f.name.split("_")[0] if not f.name.startswith("2026") else "day"))
        else:
            v = f"{d.get('model_ver')}/{d.get('input_ver')}"
            other[v] = other.get(v, 0) + 1
    return plan, other


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true"); g.add_argument("--apply", action="store_true")
    ap.add_argument("--plan"); ap.add_argument("--expect", type=int)
    a = ap.parse_args()
    if version.model_ver() != MODEL or version.input_ver() != NEW:
        sys.exit(f"지금 코드 · 입력 버전이 {version.model_ver()}/{version.input_ver()} 입니다. {MODEL}/{NEW} 에서만 씁니다 — 멈춤")
    plan, other = scan()
    if a.dry_run:
        out = HERE / "restamp_input_plan.json"
        out.write_text(json.dumps(dict(at=datetime.now().isoformat(timespec="seconds"), old=OLD, new=NEW, model=MODEL, targets=plan, untouched=other),
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        kinds = {}
        for p in plan:
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
        mixed = [p["file"] for p in plan if p["runs_other_versions"]]
        print(f"(시험 · 아무것도 바꾸지 않음) 대상 {len(plan)}개 {kinds}")
        print(f"건드리지 않을 파일 {sum(other.values())}개 (버전별) {other}")
        if mixed:
            print(f"주의: 다른 버전 실행이 섞인 파일 {mixed} — 그 실행은 바꾸지 않는다")
        print(f"목록: {out.name}")
        return
    if not a.plan or a.expect is None:
        sys.exit("--apply 에는 --plan (시험 때 만든 목록) 과 --expect (시험 때 대상 개수) 가 필요합니다")
    want = json.loads(Path(a.plan).read_text(encoding="utf-8"))["targets"]
    if len(plan) != a.expect or len(want) != a.expect:
        sys.exit(f"대상 개수가 다릅니다 (지금 {len(plan)} · 목록 {len(want)} · 기대 {a.expect}) — 아무것도 바꾸지 않음")
    if [(p["file"], p["sha"]) for p in plan] != [(w["file"], w["sha"]) for w in want]:
        sys.exit("시험 뒤 대상 파일이나 내용이 바뀌었습니다 — 아무것도 바꾸지 않음. 다시 시험부터")
    log = dict(at=datetime.now().isoformat(timespec="seconds"), reason=REASON, old=OLD, new=NEW, model=MODEL, files=[])
    for p in plan:
        f = HERE / p["file"]
        d = json.loads(f.read_text(encoding="utf-8"))
        n = 0
        for r in [d] + [r for r in (d.get("runs") if isinstance(d.get("runs"), list) else [])]:
            if match(r):
                r["input_ver_orig"] = OLD
                r["input_ver"] = NEW
                n += 1
        before = p["sha"]
        f.write_text(json.dumps(d, ensure_ascii=False, default=str), encoding="utf-8")
        log["files"].append(dict(file=p["file"], sha_before=before, sha_after=sha(f), changed_records=n))
    out = CACHE / f"restamp_input_log_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"적용 {len(log['files'])}개 · 기록 {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
