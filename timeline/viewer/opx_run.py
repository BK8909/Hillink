"""운영 실험 실행기 (CL-1024-17) — Codex CD-1024-15 실행 인터페이스를 제품 서버에서 부르는 어댑터.

  stdin  : 화면 요청 JSON (op: meta | run)
  stdout : 결과 JSON

원칙
  · CD-1024-15 소스(timeline/experiments/persona_live/operator_choice/cd1024_15/)는 원본 그대로 둔다(SHA256SUMS 대조).
    원본이 Mac 경로를 상수로 갖고 있으므로, 여기서는 모듈 상수(엔진 코드 위치 · 로컬 프로필 위치)만 이 저장소로 바꿔 끼운다.
  · 실행 전에 엔진 · 프로필 파일 SHA 를 CD-15 run_manifest 와 대조한다. 다르면 계산하지 않는다(ENGINE_SHA_MISMATCH).
  · 매 실행마다 동결 엔진을 실제로 다시 호출한다(CD-15 run_request: 기준선 · 시나리오 두 번 계산). 저장된 결과를 돌려주지 않는다.
  · 화면 입력은 여기서 먼저 검증하고(허용 필드 · 범위 · 단위), CD-15 가 한 번 더 검증한다.
  · 결과에 로컬 경로 · 원문 · 작성자 링크가 섞이면 결과를 버리고 오류로 돌려준다.
  · 기존 고객흐름(턴 · 체류) 결과는 읽지도 쓰지도 않는다.
"""
from __future__ import annotations

import hashlib, json, re, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PL = REPO / "timeline" / "experiments" / "persona_live"
CD15 = PL / "operator_choice" / "cd1024_15"
OW11 = PL / "operator_choice" / "operator_world_v1_1"

DEMO_PERSONAS = ["A02", "A04", "A05", "A07", "A10", "blog41", "blog42", "blog43", "A01", "A03", "A08"]   # CD-15 기준 11명(같은 순서)
TARGET_OFFERS = ("THE_BUFFET", "GEUMRYONG")    # 이 시나리오에서 가격 · 조건이 검증된 두 상품만 조절 대상
ADAPTER_VERSION = "cl1024-18-opx-adapter-v2"
ENGINE_FILES = {   # run_manifest.source_code_sha256 의 이름 → 이 저장소 위치
    "engine.py": PL / "operator_choice/operator_world_v1/engine.py",
    "turn_candidate.py": OW11 / "turn_candidate.py",
    "turn_view.py": OW11 / "turn_view.py",
    "rbase_profiles.json": OW11 / "turn_personas_rbase.json",
    "extension_profiles.json": OW11 / "turn_personas_ext.json",
    "local_extension_profiles.json": OW11 / "turn_personas_ext.local.json",
}
FORBIDDEN = re.compile(r"/private/|/Users/|/home/|Application Support|\.local\.json|blog\.naver|review_text|source_gist")


def _fsha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def integrity() -> dict:
    man = json.loads((CD15 / "run_manifest.json").read_text(encoding="utf-8"))
    out = {"cd15_source": [], "engine": [], "ok": True}
    for line in (CD15 / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        h, name = line.split(None, 1)
        p = CD15 / name.strip()
        if not p.exists():
            continue   # results/* 는 반입하지 않음(실행 결과 묶음 · 화면이 쓰지 않음)
        ok = _fsha(p) == h
        out["cd15_source"].append({"file": name.strip(), "ok": ok})
        out["ok"] &= ok
    for name, want in man["source_code_sha256"].items():
        p = ENGINE_FILES[name]
        ok = p.exists() and _fsha(p) == want
        out["engine"].append({"file": name, "present": p.exists(), "ok": ok})
        out["ok"] &= ok
    out["engine_head"] = man["engine_head"]
    out["catalog_version"] = man["catalog_version"]
    return out


def _service():
    sys.path.insert(0, str(PL))
    sys.path.insert(0, str(CD15 / "src"))
    import experiment_service as S   # noqa: E402  (원본 그대로)
    S.ENGINE_CODE = PL               # 원본 상수(Mac 경로) → 이 저장소의 같은 엔진(SHA 대조 통과분)
    S.PRODUCT_WORKTREE = REPO        # 로컬 전용 프로필(turn_personas_ext.local.json) 위치
    return S


class Bad(ValueError):
    pass


def build_request(ui: dict, S) -> dict:
    """화면 입력 → CD-15 요청. 허용 필드만 받는다."""
    allowed = {"op", "date", "start_time", "duration_minutes", "adults", "children", "stay_status", "reservation",
               "seat_type", "holiday", "target_offer", "discount_amount", "discount_unit"}
    extra = set(ui) - allowed
    if extra:
        raise Bad("허용되지 않은 입력: " + ", ".join(sorted(extra)))
    try:
        d = date.fromisoformat(str(ui.get("date", "")))
    except ValueError:
        raise Bad("날짜는 YYYY-MM-DD 형식이어야 합니다")
    if not (date(2026, 1, 1) <= d <= date(2027, 12, 31)):
        raise Bad("날짜는 2026-01-01 ~ 2027-12-31 사이여야 합니다")
    st = str(ui.get("start_time", ""))
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", st):
        raise Bad("시작 시각은 HH:MM 형식이어야 합니다")
    dur = ui.get("duration_minutes", 90)
    if not isinstance(dur, int) or isinstance(dur, bool) or not (30 <= dur <= 240):
        raise Bad("이용 시간은 30~240분 정수여야 합니다")
    ad, ch = ui.get("adults", 2), ui.get("children", 0)
    for v, n in ((ad, "성인"), (ch, "아동")):
        if not isinstance(v, int) or isinstance(v, bool) or v < 0 or v > 8:
            raise Bad(f"{n} 수는 0~8 정수여야 합니다")
    if ad + ch < 1:
        raise Bad("인원은 1명 이상이어야 합니다")
    stay = ui.get("stay_status", "staying")
    if stay not in ("staying", "non_staying", "unknown"):
        raise Bad("투숙 조건 값이 올바르지 않습니다")
    for k in ("reservation", "holiday"):
        if not isinstance(ui.get(k, k == "reservation"), bool):
            raise Bad(f"{k} 는 참/거짓이어야 합니다")
    seat = ui.get("seat_type", "hall")
    if seat not in ("hall", "private_room"):
        raise Bad("좌석 값이 올바르지 않습니다")
    tgt = ui.get("target_offer", "THE_BUFFET")
    if tgt not in TARGET_OFFERS:
        raise Bad("조절 대상 상품은 금룡 · 더뷔페 중 하나입니다")
    amt = ui.get("discount_amount", 0)
    if not isinstance(amt, int) or isinstance(amt, bool) or amt < 0:
        raise Bad("할인 금액은 0 이상 정수(원)여야 합니다")
    unit = ui.get("discount_unit", "per_person")
    if unit not in ("per_person", "per_party"):
        raise Bad("할인 단위는 1인 / 팀 전체 중 하나입니다")
    cat = S._load_catalog()
    offer = next(o for o in cat["offers"] if o["offer_id"] == tgt)
    party = ad + ch
    per_person = amt / (party if unit == "per_party" else 1)
    if offer.get("price_amount") is not None and per_person > float(offer["price_amount"]):
        raise Bad(f"할인이 기준 가격({offer['price_amount']:,}원/인)을 넘습니다")
    overrides = {}
    if amt > 0:
        overrides[tgt] = {"discount_amount": amt, "discount_unit": unit, "scenario_label": f"운영자 가상 할인 {amt:,}원/{'인' if unit == 'per_person' else '팀'}"}
    return {
        "scenario_id": f"CL17_{tgt}_{amt}_{unit}", "simulation_date": d.isoformat(), "meal_period": "dinner", "start_time": st,
        "duration_minutes": dur, "party_size": party, "party_composition": {"adults": ad, "children": ch}, "stay_status": stay,
        "reservation_assumption": bool(ui.get("reservation", True)), "is_public_holiday": bool(ui.get("holiday", False)),
        "seat_type": seat, "selected_persona_ids": list(DEMO_PERSONAS), "offer_overrides": overrides,
        "catalog_version": cat["catalog_version"], "engine_version": S.EXPECTED_ENGINE_VERSION, "allow_scenario_offers": False,
    }


def _scrub_check(obj) -> list:
    s = json.dumps(obj, ensure_ascii=False)
    return sorted(set(FORBIDDEN.findall(s)))


def main():
    ui = json.loads(sys.stdin.read() or "{}")
    op = ui.get("op", "run")
    integ = integrity()
    if op == "meta":
        S = _service()
        cat = S._load_catalog()
        vm = json.loads((HERE / "opx_venue_map.json").read_text(encoding="utf-8"))
        vm_ok = vm.get("map_js_sha256") == _fsha(HERE / "static" / "map.js") and vm.get("catalog_version") == cat["catalog_version"]
        venue_map = {"ok": vm_ok, "coord_space": vm.get("coord_space"),
                     "rows": [{k: r.get(k) for k in ("offer_id", "venue_id", "engine_venue_id", "map_loc_id", "map_building", "coord_display", "status", "use_on_map", "evidence", "coord_note")} for r in vm["rows"]]}
        if not vm_ok:   # 지도 그림 좌표나 카탈로그가 바뀌면 매핑을 다시 확인하기 전까지 지도에 그리지 않는다
            for r in venue_map["rows"]:
                r["use_on_map"] = False
        print(json.dumps({"adapter_version": ADAPTER_VERSION, "integrity": integ, "personas": DEMO_PERSONAS, "venue_map": venue_map,
                          "target_offers": [{"offer_id": o["offer_id"], "venue_id": o["venue_id"], "offer_name": o["offer_name"],
                                             "price_amount": o.get("price_amount"), "price_basis": o.get("price_basis")}
                                            for o in cat["offers"] if o["offer_id"] in TARGET_OFFERS],
                          "default": {"date": "2026-10-27", "start_time": "18:30", "duration_minutes": 90, "adults": 2, "children": 0,
                                      "stay_status": "staying", "reservation": True, "seat_type": "hall", "holiday": False,
                                      "target_offer": "THE_BUFFET", "discount_amount": 0, "discount_unit": "per_person"}},
                         ensure_ascii=False))
        return 0
    if not integ["ok"]:
        print(json.dumps({"experiment": {"run_status": "ENGINE_SHA_MISMATCH"}, "integrity": integ}, ensure_ascii=False))
        return 0
    S = _service()
    try:
        req = build_request(ui, S)
    except Bad as e:
        print(json.dumps({"experiment": {"run_status": "INVALID_REQUEST"}, "error": str(e)}, ensure_ascii=False))
        return 0
    try:
        res = S.run_request(req)
    except ValueError as e:
        print(json.dumps({"experiment": {"run_status": "INVALID_REQUEST"}, "error": str(e).splitlines()[0][:200]}, ensure_ascii=False))
        return 0
    except FileNotFoundError:
        print(json.dumps({"experiment": {"run_status": "LOCAL_INPUT_UNAVAILABLE"}, "error": "로컬 전용 프로필 입력이 없습니다(저장소 밖 자료)"}, ensure_ascii=False))
        return 0
    bad = _scrub_check(res)
    if bad:
        print(json.dumps({"experiment": {"run_status": "OUTPUT_PRIVACY_BLOCKED"}, "error": "결과에 비공개 문자열이 섞여 표시하지 않음", "patterns": bad}, ensure_ascii=False))
        return 0
    res["adapter"] = {"version": ADAPTER_VERSION, "engine_called": True, "arms_computed": ["baseline", "scenario"],
                      "integrity_ok": True, "engine_head": integ["engine_head"], "normalized_request": req,
                      "interpretation": "동결 규칙 엔진의 조건부 시나리오 · 가상 고객 11명 · 실제 수요 · 매출 예측 아님"}
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
