#!/usr/bin/env python3
"""페르소나 라이브러리 유형 자산 목록 생성 (CL-1024-14 · CL-1024-15 보강).

  static/persona_thumbs/  → 2단계 고객 목록 · 카드 · 상세 상단의 '유형별 썸네일'
  static/type_icons/      → 1단계 유형 선택 화면의 '유형 아이콘' (1:1 정사각형 권장 · svg/png/webp)

연결 순서
  1) 정식 자산 목록 static/persona_thumbs/asset_registry.json — 파일 · 유형 · SHA · 근거 · 사용자 승인 여부를 적은 수동 대응.
     목록의 파일 SHA 가 실제 파일과 다르면 그 항목은 쓰지 않고 SHA_MISMATCH 로 보고한다(파일을 몰래 바꾸지 않게).
  2) 목록에 없는 파일은 파일 이름의 유형명으로 자동 매칭.
     - 파일 이름과 유형명에서 공백 · 가운뎃점(·) · 밑줄 · 하이픈 · 괄호를 지우고 비교, Mac(NFD) 이름은 NFC 로 바꿔 비교.
     - 정확히 한 유형만 맞을 때만 연결. 서로 다른 유형이 둘 이상 맞으면(포함 관계가 아니면) UNMATCHED 로 보류.
     - 같은 유형에 파일이 둘 이상이면 이름순 첫 파일, 나머지는 DUPLICATE 로 보고.
  3) 맞는 유형이 없는 파일은 UNMATCHED(화면에 쓰지 않음).
실행: python3 timeline/viewer/tools/build_type_assets.py   (파일을 넣거나 바꾼 뒤 한 번)
"""
import hashlib
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1] / "static"
TYPES = ["가족 · 영유아", "가족 · 부모 동반", "커플 · 기념일", "혼자 휴식", "친구 모임", "업무 · 출장",
         "미식", "웰니스", "스포츠 목적", "행사 체험", "혜택 · 멤버십"]
EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


def norm(s: str) -> str:
    return re.sub(r"[\s·・_\-()\[\]]+", "", unicodedata.normalize("NFC", s))


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def auto_type(stem: str):
    key = norm(stem)
    hits = [t for t in TYPES if norm(t) in key]
    # 포함 관계(긴 이름이 짧은 이름을 품음)만 남기면 하나여야 함
    tops = [t for t in hits if not any(t != u and norm(t) in norm(u) for u in hits)]
    # 다른 유형의 첫 낱말(커플 · 가족 · 혼자 …)이 함께 들어 있으면 의미가 섞인 이름 → 보류
    firsts = {norm(t.split(" ")[0]) for t in TYPES}
    present = {w for w in firsts if w in key}
    if len(tops) == 1 and present <= {norm(tops[0].split(" ")[0])} | {norm(tops[0])}:
        return tops[0], "AUTO_FILENAME"
    return None, ("UNMATCHED_AMBIGUOUS" if len(tops) > 1 or (tops and len(present) > 1) else "UNMATCHED")


def scan(folder: str, registry: list) -> dict:
    d = ROOT / folder
    items, report = {}, []
    if not d.is_dir():
        return {"items": {}, "report": [], "unmatched": []}
    files = {unicodedata.normalize("NFC", f.name): f for f in d.iterdir() if f.suffix.lower() in EXT and not f.name.startswith(".")}
    reg_by_file = {unicodedata.normalize("NFC", r["file"]): r for r in registry}
    for name in sorted(files):
        f = files[name]
        r = reg_by_file.get(name)
        if r:
            ok = sha(f) == r.get("file_sha256")
            status = r.get("match", "MANUAL") if ok else "SHA_MISMATCH"
            t = r["type"] if ok else None
        else:
            t, status = auto_type(f.stem)
        if t and t in items:
            status, t = "DUPLICATE", None
        if t:
            items[t] = f.name   # 실제 파일 이름 그대로(NFD 여도 서버가 그 이름으로 연다)
        report.append({"file": name, "type": t, "status": status, "user_approved": bool(r and r.get("user_approved"))})
    return {"items": items, "report": report, "unmatched": [x["file"] for x in report if not x["type"]]}


def main():
    regp = ROOT / "persona_thumbs" / "asset_registry.json"
    reg = json.loads(regp.read_text(encoding="utf-8")) if regp.exists() else {}
    man = {"_about": "build_type_assets.py 가 정식 자산 목록(asset_registry.json) → 파일 이름 유형명 순으로 만든 목록 · 손으로 고치지 않음",
           "types": TYPES, "type_ids": reg.get("type_ids", {}),
           "thumbs": scan("persona_thumbs", reg.get("thumbs", [])), "icons": scan("type_icons", reg.get("icons", []))}
    p = ROOT / "persona_thumbs" / "manifest.json"
    p.write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k in ("thumbs", "icons"):
        st = {}
        for x in man[k]["report"]:
            st[x["status"]] = st.get(x["status"], 0) + 1
        print(k, f"{len(man[k]['items'])}/{len(TYPES)}", "· 상태:", st or "-", "· 없음:", [t for t in TYPES if t not in man[k]["items"]] or "-",
              "· 보류:", man[k]["unmatched"] or "-")


if __name__ == "__main__":
    main()
