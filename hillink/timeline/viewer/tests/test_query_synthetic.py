"""10/16 · 캐시 없이도 도는 조건으로 묻기(query.py) 회귀 검사 — 작은 가상 하루를 임시 폴더에 만들어 검사한다 (CI · 다른 개발 환경용)

  python3 tests/test_query_synthetic.py

저장된 하루 캐시가 필요한 tests/test_query_qa.py 와 같은 규칙을 가상 데이터로 확인한다.
  1. 고객군 '전체' 합 = 회차별 인원 · 투숙 + 비투숙 = 전체 · 여러 조건 교집합 ≤ 각 조건 · 한 손님은 한 번만
  2. 공급 제한(다른 선택)은 손님 · 업장마다 한 번
  3. 이 날 회차가 없는 업장(다음 날 회차만)의 '회차 전체' 질의 → status no_window (오류 아님) · 없는 회차 이름은 오류
  4. 연박 집계 연결: 같은 조건 키(base_keys)일 때만 값 · 다른 조건 → None + 안내 · 연박 집계 밖 업장 → None + '아직 계산하지 않음' (0 아님)
  5. 럭스바 · 르파사쥬 결제 수량(잔 · 병 · 바스켓)을 착석 인원과 따로 돌려줌
"""
import json
import sys
import tempfile
import contextlib
import io
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import query as Q  # noqa: E402

ok = fail = 0


def check(name, cond, info=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print("실패:", name, info)


def W(name, kind, t0, t1, persons, peak=50):
    return dict(name=name, kind=kind, t0=t0, t1=t1, persons=persons, peak_pct=peak)


def guest(i, is_guest, party, steps, kids=False, nights=1, purpose="커플·기념일", age="30~49세"):
    return dict(id=i, persona=dict(is_guest=is_guest, party=party, kids=kids, nights=nights if is_guest else 0, purpose=purpose, age=age), steps=steps)


def step(venue, t, state="DINING", spend=None, switch=None, l3=None):
    return dict(kind="meal", venue=venue, location=venue, state=state, t_in=f"2026-10-10T{t}", spend=spend or [], switch=switch or {})


G = [
    guest(1, True, 2, [step("THE_BUFFET", "18:00", spend=[dict(l3="더뷔페", krw=220000, qty=2, l2="F&B")])], nights=2, kids=True, purpose="가족·친족"),
    guest(2, True, 3, [step("THE_BUFFET", "18:30"), step("LUX_BAR", "20:10", state="TAB_OPEN", spend=[dict(l3="럭스바", krw=60000, qty=4, l2="F&B")])]),
    # 손님 3 은 더뷔페 단계가 둘 — 착석은 단계마다(인 · 회) 세고, 공급 제한(다른 선택)은 손님 · 업장마다 한 번 (engine.day 와 같은 규칙)
    guest(3, False, 4, [step("THE_BUFFET", "17:40", switch=dict(원래="피자힐", 시각="2026-10-10T17:35")),
                        step("THE_BUFFET", "17:45", switch=dict(원래="피자힐", 시각="2026-10-10T17:44"))], purpose="친구·모임"),
    guest(4, False, 1, [step("LE_PASSAGE", "12:00", state="TAKEOUT_ORDER", spend=[dict(l3="르파사쥬", krw=50000, qty=1, l2="F&B")])]),
    guest(5, True, 2, [step("PIZZA_HILL", "18:00")], nights=2, kids=True, purpose="커플·기념일"),
]
VD = {
    "THE_BUFFET": dict(name="더뷔페", cap=288, windows=[W("석식 1부", "석식", "10/10 17:30", "19:30", 13), W("석식 2부", "석식", "10/10 20:00", "22:00", 0)]),
    "PIZZA_HILL": dict(name="피자힐", cap=96, windows=[W("석식 1부", "석식", "10/10 17:30", "19:00", 2)]),
    "LUX_BAR": dict(name="럭스바", cap=120, windows=[W("석식", "석식", "10/10 20:00", "21:59", 3)], l4_qty_day={"맥주 · 병": 4}),
    "LE_PASSAGE": dict(name="르파사쥬", cap=30, windows=[W("중식", "중식", "10/10 11:00", "19:30", 0)]),
    "THE_PAVILION": dict(name="파빌리온", cap=81, windows=[W("중식", "중식", "10/10 13:00", "17:00", 0)]),
    "MOEGI": dict(name="모에기", cap=40, windows=[W("중식 (익일)", "중식", "10/11 12:00", "14:30", 0)]),     # 이 날 회차 없음 (다음 날만)
}
def main():
    global ok, fail
    ok = fail = 0
    with tempfile.TemporaryDirectory() as td:
        C = Path(td)
        base, other = "2026-10-10_none_s100_test-base", "2026-10-10_none_s100_test-bs338"
        for k in (base, other):
            (C / f"{k}.json").write_text(json.dumps(dict(key=k, date="2026-10-10", scenario="none", knobs="", model_ver="m1", input_ver="i1", venue_detail=VD,
                                                         guests=[dict(purpose=g["persona"]["purpose"], age=g["persona"]["age"]) for g in G]), ensure_ascii=False), encoding="utf-8")
            (C / f"{k}.guests.jsonl").write_text("\n".join(json.dumps(g, ensure_ascii=False) for g in G) + "\n", encoding="utf-8")
        stay = C / "stay_day.json"
        stay.write_text(json.dumps(dict(model_ver="m1", input_ver="i1", condition="가상 기본 조건", base_keys=[base],
                                        runs=[dict(date="2026-10-10", seed=0, warm=3, meals={"THE_BUFFET": {"그날 체크인": 5, "전날 체크인": 2, "비투숙": 4}})]), ensure_ascii=False), encoding="utf-8")
        Q.STAY_FILE = stay

        a, g, d = (Q.query(C, base, "THE_BUFFET", "*", x) for x in ("all", "guest", "day"))
        check("전체 합 = 회차별 인원", a["check_ok"] and [r["persons"] for r in a["rows"]] == [13, 0], a["rows"])
        check("투숙 + 비투숙 = 전체", all(x["persons"] + y["persons"] == z["persons"] and x["teams"] + y["teams"] == z["teams"] for x, y, z in zip(g["rows"], d["rows"], a["rows"])))
        check("공급 제한은 손님 · 업장마다 한 번", Q.query(C, base, "PIZZA_HILL", "*", "all")["rows"][0]["over_persons"] == 4)
        k1, k2, kk = (Q.query(C, base, "THE_BUFFET", "*", x) for x in ("kids", "n2", "kids,n2"))
        check("교집합 ≤ 각 조건", all(z["persons"] <= min(x["persons"], y["persons"]) for x, y, z in zip(k1["rows"], k2["rows"], kk["rows"])))
        check("여러 조건을 모두 만족하는 손님 한 번만", kk["rows"][0]["persons"] == 2 and kk["rows"][0]["teams"] == 1, kk["rows"][0])
        check("목적 + 2박 교집합", Q.query(C, base, "THE_BUFFET", "*", "p:가족·친족,n2")["rows"][0]["teams"] == 1)
        r = Q.query(C, base, "MOEGI", "*", "all")
        check("회차 없는 업장 → no_window", r.get("status") == "no_window" and r["rows"] == [], r)
        try:
            Q.query(C, base, "MOEGI", "없는 회차", "all"); check("없는 회차 이름은 오류", False)
        except ValueError:
            check("없는 회차 이름은 오류", True)
        check("같은 조건 → 연박 값", a["operating"] is not None and a["operating"]["mean"] == 11, a["operating"])
        check("비투숙만 → 연박 값", d["operating"] is not None and d["operating"]["mean"] == 4, d["operating"])
        r = Q.query(C, other, "THE_BUFFET", "*", "all")
        check("다른 조건 → None + 안내", r["operating"] is None and bool(r["operating_note"]), r["operating_note"])
        r = Q.query(C, base, "THE_PAVILION", "*", "all")
        check("연박 집계 밖 업장 → None (0 아님)", r["operating"] is None and "아직 계산하지" in (r["operating_note"] or ""), r)
        r = Q.query(C, base, "THE_BUFFET", "*", "a:30~49세")
        check("연령 고객군 → 연박 값 붙이지 않음", r["operating"] is None and r["operating_note"])
        r = Q.query(C, base, "LUX_BAR", "*", "all")
        check("럭스바 착석 3 · 결제 수량 4 따로", r["rows"][0]["persons"] == 3 and r["rows"][0]["qty"] == 4 and r["kind"] == "bar", r["rows"])
        r = Q.query(C, base, "LE_PASSAGE", "*", "all")
        check("르파사쥬 구매 1건 · 착석 0", r["rows"][0]["qty"] == 1 and r["rows"][0]["persons"] == 0 and r["kind"] == "purchase", r["rows"])
    print(f"통과 {ok} · 실패 {fail}")
    return 1 if fail else 0


class QuerySyntheticRegression(unittest.TestCase):
    def test_synthetic_query_invariants(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main()
        self.assertEqual(result, 0, output.getvalue())


if __name__ == "__main__":
    raise SystemExit(main())
