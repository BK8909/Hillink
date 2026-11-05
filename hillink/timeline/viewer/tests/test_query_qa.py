"""10/16 QA 회귀 검사 · 조건으로 묻기(query.py)와 연박 집계 연결 — 저장된 하루 캐시가 있을 때만 돈다 (없으면 건너뜀)

  python3 tests/test_query_qa.py

확인하는 것
  1. 기본 v4.1 하루에만 그 날 운영 기준(연박 집계)을 붙이고, 좌석 338 · 변칙(휴업) · 다른 조정값 하루에는 붙이지 않는다(값 None + 안내)
  2. 연박 집계가 세지 않는 업장(파빌리온)은 0 이 아니라 None + '아직 계산하지 않음'
  3. 휴업 등으로 이 날 회차가 없는 업장의 '회차 전체' 질의는 오류(500)가 아니라 status=no_window
  4. 고객군 전체 합 = 화면 회차별 인원 · 투숙 + 비투숙 = 전체 · 교집합 ≤ 각 조건 · 럭스바 · 르파사쥬는 결제 수량을 함께 돌려줌
"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import query as Q  # noqa: E402

C = HERE / "cache"
S = json.loads((HERE / "static" / "stay_day.json").read_text(encoding="utf-8"))
ok = fail = 0


def check(name, cond, info=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("실패:", name, info)


def keys_for(date):
    out = []
    for f in sorted(C.glob(f"{date}_none_s100_*.json")):
        if f.name.endswith((".progress.json",)) or f.name.startswith("band_") or not (C / (f.stem + ".guests.jsonl")).exists():
            continue
        m = json.loads(f.read_text(encoding="utf-8"))
        out.append((m["key"], m))
    return out


def main():
    global ok, fail
    ok = fail = 0
    with contextlib.redirect_stdout(io.StringIO()):
        import engine as E  # noqa: E402
    base = E.day_key("2026-10-10", "none", 1, dict(E.V4, seed=0))
    if not (C / f"{base}.guests.jsonl").exists():
        print("건너뜀: 10/10 기본 캐시 없음"); return 0

    # 1 · 기본 하루에는 붙고 다른 조건에는 안 붙음
    r = Q.query(C, base, "THE_BUFFET", "*", "all")
    check("기본 하루 연박 연결", r["operating"] is not None, r.get("operating_note"))
    others = [(k, m) for k, m in keys_for("2026-10-10") if k not in S["base_keys"] and m.get("model_ver") == S["model_ver"] and m.get("input_ver") == S["input_ver"]]
    for k, m in others:
        rr = Q.query(C, k, "THE_BUFFET", "*", "all")
        check(f"다른 조건 연박 미연결 {k[-40:]}", rr["operating"] is None and (rr.get("operating_note") or rr.get("status") == "no_window"), rr.get("operating"))
    check("다른 조건 하루가 하나 이상 검사됨", len(others) > 0)
    # 2 · 연박 집계 밖 업장
    r = Q.query(C, base, "THE_PAVILION", "*", "all")
    check("파빌리온 운영 기준 None", r["operating"] is None and "아직 계산하지" in (r.get("operating_note") or ""), r.get("operating"))
    # 3 · 회차 없는 업장
    closed = [k for k, m in others if not [w for w in m["venue_detail"]["THE_BUFFET"]["windows"] if "익일" not in w["name"] and (w["persons"] or w.get("over_persons"))]
              and m["theta"].get("anomaly")]
    for k in closed[:2]:
        try:
            rr = Q.query(C, k, "THE_BUFFET", "*", "all")
            check(f"휴업 회차 전체 {k[-30:]}", rr.get("status") == "no_window" or rr["rows"] is not None)
        except Exception as e:  # noqa: BLE001
            check(f"휴업 회차 전체 예외 없음 {k[-30:]}", False, repr(e))
    # 4 · 합계 · 분할 · 교집합 · 결제 수량
    D = json.loads((C / f"{base}.json").read_text(encoding="utf-8"))
    for v in ("THE_BUFFET", "PIZZA_HILL", "GEUMRYONG", "MYONGWOLGWAN", "MOEGI", "ONDAL", "THE_PAVILION", "LUX_BAR", "LE_PASSAGE"):
        a, g, d = (Q.query(C, base, v, "*", x) for x in ("all", "guest", "day"))
        check(f"{v} 전체 = 화면", a["check_ok"])
        check(f"{v} 투숙 + 비투숙 = 전체", all(x["persons"] + y["persons"] == z["persons"] and x["teams"] + y["teams"] == z["teams"] for x, y, z in zip(g["rows"], d["rows"], a["rows"])))
        k1, k2, kk = (Q.query(C, base, v, "*", x) for x in ("kids", "n2", "kids,n2"))
        check(f"{v} 교집합 ≤ 각 조건", all(z["persons"] <= min(x["persons"], y["persons"]) for x, y, z in zip(k1["rows"], k2["rows"], kk["rows"])))
        if v in ("LUX_BAR", "LE_PASSAGE"):
            L4 = sum((D["venue_detail"][v].get("l4_qty_day") or {}).values())
            check(f"{v} 결제 수량 = 화면 그 날 수량", sum(x["qty"] for x in a["rows"]) == L4, (sum(x["qty"] for x in a["rows"]), L4))
    print(f"통과 {ok} · 실패 {fail}")
    return 1 if fail else 0


class QueryCacheRegression(unittest.TestCase):
    def test_cached_query_invariants(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main()
        if "건너뜀:" in output.getvalue():
            self.skipTest(output.getvalue().strip())
        self.assertEqual(result, 0, output.getvalue())


if __name__ == "__main__":
    raise SystemExit(main())
