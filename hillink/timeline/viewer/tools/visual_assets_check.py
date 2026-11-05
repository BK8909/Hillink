"""CL-1025-29 — 고객별 시각 자산 원장(공용 아바타 · 고객 고유 썸네일 · 유형 아이콘 분리) 검사기. 읽기 전용 · 이미지 생성 없음.

  python3 tools/visual_assets_check.py LEDGER.json [--root REPO]

원장 한 줄(고객 1명)
  {"persona": "QA16_00491",                      # 승인 전에는 격리 alias · 승인 뒤 정식 ID
   "type_id": "couple_anniversary",              # 공식 11개 중 하나(변경 금지) — 1차 화면 아이콘 · 유형 썸네일은 '범주 참고'
   "avatar":   {"key": "couple_smart", "pool": "duo", "basis_fact_ids": [...], "status": "MAPPED|REVIEW|NO_ASSET"},
   "thumbnail":{"asset_id": null, "path": null, "sha256": null, "prompt": "...", "evidence_ids": [...],
                "status": "AWAITING_LP|PROMPT_READY|IMAGE_READY|USER_APPROVED"}}
검사(하나라도 걸리면 FAIL)
  · avatar.key 는 공용 풀(solo / duo / group_3plus)의 기존 키여야 함 — 고객 1:1 전용 아바타 금지
  · 관계가 다른 풀 사용 금지(친구 · 일행에 가족 그림, 친구 2인에 커플 그림)
  · thumbnail 은 고객 고유: 같은 path · sha256 · asset_id 를 두 고객이 쓰면 중복 매핑 오류
  · 유형 공용 썸네일(persona_thumbs/*_썸네일.jpg)을 고객 썸네일로 넣으면 오류(범주 참고일 뿐)
  · avatar 파일 경로를 thumbnail 로 넣는 등 두 필드 혼용 오류
  · IMAGE_READY 이상이면 파일 실재 + sha256 일치, 아니면 path/sha256 은 비어 있어야 함(완료 사칭 방지)
"""
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
POOLS = {   # 기존 30파일(10키)만 — 인원 · 큰 관계. 성별 · 나이 · 기념일 · 영유아는 확정하지 않음
    "solo": {"solo_casual", "solo_office", "solo_hiker"},
    "duo": {"couple_smart", "couple_vacation", "couple_wine", "friends_2f"},
    "group_3plus": {"family_kid1", "family_kid2", "family_3gen"},   # 현재 전부 가족 그림 — 친구 · 일행 3+ 공용 그림 없음(제작 후보 1건)
}
REL_OK = {   # 큰 관계 → 쓸 수 있는 키
    "couple": {"couple_smart", "couple_vacation"},          # couple_wine(정장 · 와인잔)은 기념 · 행사 연출 — 근거 있을 때만
    "friends": {"friends_2f"},
    "family": {"family_kid1", "family_kid2", "family_3gen"},
    "solo": POOLS["solo"],
    "group": set(),                                          # 일행 3+ 공용 그림 없음
}
TYPES = {"family_infant", "family_parents", "couple_anniversary", "solo_rest", "friends", "business", "gourmet", "wellness", "sports", "event", "benefit_membership"}


def check(ledger, root=ROOT):
    errs, seen = [], {}
    for r in ledger:
        p, av, th = r.get("persona"), r.get("avatar") or {}, r.get("thumbnail") or {}
        if r.get("type_id") not in TYPES:
            errs.append(f"{p}: type_id 가 공식 11개가 아님")
        k = av.get("key")
        if k:
            pool = next((n for n, ks in POOLS.items() if k in ks), None)
            if not pool:
                errs.append(f"{p}: 아바타 {k} 는 공용 풀에 없음(1:1 전용 금지)")
            elif av.get("pool") and av["pool"] != pool:
                errs.append(f"{p}: 아바타 풀 표기 {av['pool']} ≠ 실제 {pool}")
            rel = av.get("rel")
            if rel and k not in REL_OK.get(rel, set()) and not (k == "couple_wine" and av.get("event_basis_fact_ids")):
                errs.append(f"{p}: 관계 {rel} 에 맞지 않는 그림 {k}")
            for side in ("front", "side", "portrait"):
                if not (root / f"timeline/viewer/static/avatars/{k}_{side}.png").exists():
                    errs.append(f"{p}: 아바타 파일 없음 {k}_{side}")
        elif av.get("status") not in ("REVIEW", "NO_ASSET"):
            errs.append(f"{p}: 아바타 키 없음인데 상태가 REVIEW/NO_ASSET 아님")
        path, sha, aid, st = th.get("path"), th.get("sha256"), th.get("asset_id"), th.get("status")
        if path and "/persona_thumbs/" in path and path.endswith("_썸네일.jpg"):
            errs.append(f"{p}: 유형 공용 썸네일을 고객 썸네일로 사용(범주 참고일 뿐)")
        if path and "/avatars/" in path:
            errs.append(f"{p}: 아바타 파일을 썸네일 필드에 넣음(필드 혼용)")
        for key, val in (("path", path), ("sha256", sha), ("asset_id", aid)):
            if val:
                if val in seen.get(key, {}):
                    errs.append(f"{p}: 썸네일 {key} 중복 — {seen[key][val]} 와 같음(1페르소나 1이미지)")
                seen.setdefault(key, {})[val] = p
        if st in ("IMAGE_READY", "USER_APPROVED"):
            f = root / path if path else None
            if not f or not f.exists():
                errs.append(f"{p}: {st} 인데 파일 없음")
            elif hashlib.sha256(f.read_bytes()).hexdigest() != sha:
                errs.append(f"{p}: 썸네일 sha256 불일치")
        elif path or sha:
            errs.append(f"{p}: 이미지 준비 전({st})인데 path/sha256 이 채워짐")
        if not th.get("evidence_ids"):
            errs.append(f"{p}: 썸네일 근거 사실 ID 없음")
    return errs


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    root = Path(a[a.index("--root") + 1]) if "--root" in a else ROOT
    led = json.loads(Path(a[0]).read_text(encoding="utf-8"))
    e = check(led.get("personas", led) if isinstance(led, dict) else led, root)
    print(json.dumps({"pass": not e, "errors": e}, ensure_ascii=False, indent=1))
    sys.exit(1 if e else 0)
