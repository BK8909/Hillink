#!/usr/bin/env python3
"""CL-37 P7 — 라이브러리 열람 카탈로그(열람 전용 고객) 생성기.

입력(읽기 전용):
  - static/persona_library.json        제품 고객 원장(63 · 앱 ID · 유형 · 방문 요약)
  - static/persona_gallery/gallery.json 고객별 썸네일 카드 65(scene 슬롯 · 이미지 · QA · 사진형 증분 상태)
  - static/persona_publish.json         게시(실행) 승인 11 — 이미 라이브러리에 나오는 고객은 카탈로그에서 뺀다
  - static/display_registry.js          표시 번호(No.####) — scene 슬롯의 lp_display = 앱 ID 인 행만 조인(새 번호를 만들지 않음)
출력: static/persona_catalog.json (비공개 소스 ID · 작성자 · 원문 · URL 없음)

조인 규칙: 표시 레지스트리 scene 행의 lp_display 가 원장 앱 ID 와 정확히 같고, gallery 카드 display_id 도 같은 앱 ID 일 때만 '확인된 고객'.
표시 번호가 없는 원장 고객(썸네일 원장에 없음)은 번호를 새로 만들지 않고 제외(사유 기록).
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ST = HERE / "static"
SENS = re.compile(r"영아|아기|아이|유아|자녀|딸|아들|유모차|카시트|육아|임신|임산|출산|산후|모유|건강|진단|의학|병원|돌잔치|첫째|둘째|셋째|낮잠|학생|몸이|몸보신|아파|아픈|수술|시술")
PRIV = re.compile(r"블로그|해외 생활|작성자|싱가포르|제한 공유|검수 자료 참조")


# 10/26 — 앱 원장 유형과 이미지 원장(65) 유형 후보가 다른 10명(교차표 MATCHED+TYPE_CONFLICT · ID 만). 어느 쪽도 확정하지 않고 '유형 확인 중'으로 둔다
TYPE_REVIEW = {"A06", "A13", "A20", "A23", "N04", "N05", "N15", "N20", "N24", "N25"}


def registry():
    t = (ST / "display_registry.js").read_text(encoding="utf-8")
    j = json.loads(t[t.index("{"): t.rindex("}") + 1])
    return j["entries"]


def items(pick):
    if not pick:
        return []
    parts = re.split(r"\s*[①②③④⑤]\s*|\s*;\s*", pick)
    if len([p for p in parts if p.strip()]) <= 1:
        parts = re.split(r"\s+·\s+", pick)
    out = []
    for p in parts:
        p = p.strip(" ·;")
        if not p or SENS.search(p) or PRIV.search(p):
            continue
        out.append(p)
    return out[:3]


def visit_form(v):
    if not v or SENS.search(v):
        return None
    v = re.sub(r"\s*\((?:[^()]*)\)\s*", " ", v).strip()
    return v or None


def main():
    led = {p["id"]: p for p in json.loads((ST / "persona_library.json").read_text(encoding="utf-8"))["personas"]}
    gal = {c["card_id"]: c for c in json.loads((ST / "persona_gallery" / "gallery.json").read_text(encoding="utf-8"))["cards"]}
    pub = json.loads((ST / "persona_publish.json").read_text(encoding="utf-8"))
    runnable = set(pub.get("demo_display") or {})
    reg = registry()
    types11 = ["가족 · 영유아", "가족 · 부모 동반", "커플 · 기념일", "혼자 휴식", "친구 모임", "업무 · 출장", "미식", "웰니스", "스포츠 목적", "행사 체험", "혜택 · 멤버십"]
    scene_of = {}
    for k, e in reg.items():
        if e.get("kind") == "visual_draft" and e.get("lp_display"):
            scene_of.setdefault(e["lp_display"], []).append(k)
    cat, excluded = [], []
    for pid, p in led.items():
        if pid in runnable:
            continue
        sc = scene_of.get(pid) or []
        if len(sc) != 1:
            excluded.append({"id": pid, "type": p.get("type_group"), "reason": "표시 번호 없음 — 썸네일 원장(65)에 이 고객 행이 없어 No. 미배정(새 번호 생성 금지)" if not sc else "썸네일 행이 2개 이상 — 1:1 조인 불가"})
            continue
        s = sc[0]; g = gal.get(s)
        if not g or g.get("display_id") != pid:
            excluded.append({"id": pid, "type": p.get("type_group"), "reason": "썸네일 카드의 고객 ID 불일치"}); continue
        im = g.get("image") or {}
        qa = im.get("qa") or ""
        show = bool(im.get("src")) and not g.get("image_withheld") and qa != "FIX"
        conflict = pid in TYPE_REVIEW
        ty = p.get("type_group") if (p.get("type_group") in types11 and not conflict) else None
        it = items(p.get("pick"))
        cat.append({
            "id": pid, "scene": s, "no": reg[s]["no"], "type": ty,
            "type_note": None if ty else ("고객 원장 유형과 이미지 원장 유형 후보가 달라 확인 중 — 11개 유형에 넣지 않음" if conflict else "동행 · 방문 목적 확인 전 — 11개 유형에 넣지 않음"), "type_review": conflict,
            "summary": it[0] if it else None, "notes": it, "visit": visit_form((p.get("visit_feature_summary") or {}).get("방문 형태")),
            "image": {"src": im["src"], "sha256": im.get("sha256"), "qa": qa, "label": "생성 이미지 · 검수 중 · 실제 고객 사진 아님"} if show else None,
            "image_withheld": None if show else ("이미지 수정 필요(FIX) — 중립 표지로 대체" if qa == "FIX" else "이미지 비표시"),
            "photo_delta": (g.get("photo_delta") or {}).get("status"),
            "profile": "정리 중", "reviewed": bool((p.get("status") or {}).get("reviewed")),
            "catalogue_visible": True, "engine_runnable": False,
        })
    cat.sort(key=lambda c: c["no"])
    used = {c["scene"] for c in cat}
    unmatched = [k for k, e in reg.items() if e.get("kind") == "visual_draft" and k not in used]
    out = {"about": "CL-37 P7 라이브러리 열람 카탈로그 — 제품 고객 원장(앱 ID)과 표시 레지스트리 · 썸네일 카드가 1:1 로 맞는 고객만. 열람 전용(시뮬레이션 준비 중) · 엔진 허용 목록 · 게시 승인과 별개. 프로필 독립 검수 전 · 이미지 사람 승인 전.",
           "version": "catalog_p7_v1", "generated_by": "tools/build_catalog_p7.py",
           "counts": {"ledger": len(led), "runnable": len(runnable), "catalogue": len(cat), "with_image": sum(1 for c in cat if c["image"]),
                      "excluded_ledger": len(excluded), "thumbnail_cards": len(gal), "thumbnail_cards_unjoined": len(unmatched)},
           "customers": cat, "excluded": excluded}
    (ST / "persona_catalog.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["counts"], ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
