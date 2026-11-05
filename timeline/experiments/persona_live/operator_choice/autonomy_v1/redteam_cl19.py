"""CL-19 후속 — 실행기 검증(validator) 적대 시험: 일부러 월드 제약을 어기는 LLM 의도를 넣어 실제로 거절 · 대체되는지.
  python3 -m operator_choice.autonomy_v1.redteam_cl19 --out DIR
API 를 부르지 않는다(의도를 직접 주입). 결과: DIR/redteam_cl19.json · .md
"""
import argparse, json
from pathlib import Path
from . import agent_day as AD, llm_layer as LL


def agent(pid, inp, t, sc=None, setup=None):
    sc = sc or AD.scenario("rt")
    a = AD.Agent(pid, *inp, sc); w = AD.World(sc)
    while a.t + 60 <= AD.hm(t) and AD.decide(a, w):   # 규칙으로 그 시각 직전까지 진행(현실적인 상태)
        pass
    a.t = max(a.t, AD.hm(t))
    if setup:
        setup(a)
    return a, w


def intent(option, fact_ids=(), why="(적대 시험 의도)"):
    return dict(option=option, why=why, fact_ids=list(fact_ids), alternatives=[], keep_or_change="새로 시도", dropped_fact_ids=[], profile_basis="")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a_ = ap.parse_args()
    out = Path(a_.out); out.mkdir(parents=True, exist_ok=True)
    inp = AD.load_inputs(); R = []

    def case(name, expect, pid, t, it, sc=None, setup=None):
        a, w = agent(pid, inp, t, sc, setup)
        n0 = len(a.log); t0 = a.t
        ok, why = LL.execute(a, w, a.t, it)
        got = "채택" if ok else "거절"
        res = a.log[-1] if ok and len(a.log) > n0 else None
        R.append(dict(case=name, customer=pid, time=AD.mh(t0), option=it["option"], expect=expect, got=got, reason=why,
                      result=(res["label"] + " · " + res["loc"]) if res else None, passed=(got == expect)))

    case("비투숙 → 실내 수영장", "거절", "blog42", "13:00", intent("pool"))
    case("비투숙 → 스카이야드 족욕(출입표 비투숙 불가)", "거절", "blog42", "14:00", intent("footbath"))
    case("비투숙 → 포레스트 파크 산책(출입표 비투숙 불가)", "거절", "blog42", "14:00", intent("forest_walk"))
    case("영업 전 럭스바(20:00~)", "거절", "A07", "10:00", intent("luxbar"))
    case("같은 업장 두 끼 · 재방문 후기 인용 없음", "거절", "A07", "12:00", intent("lunch_pizzahill"), setup=lambda a: a.used.add("PIZZA_HILL"))
    case("와인페어 미개최일 참여", "거절", "A07", "16:00", intent("wine_fair"))
    case("선택지에 없는 id", "거절", "A07", "16:00", intent("spa_massage"))
    case("방금 쉬었는데 또 객실 휴식", "거절", "A07", "15:00", intent("rest_room"),
         setup=lambda a: a.add("activity", "room_rest", "객실 휴식", a.room, a.t, 45, "객실 휴식", "planner_rules", "시험 준비", []))
    def calm(a):
        a.add("activity", "cafe", "더 파빌리온에서 커피 · 디저트", "THE_PAVILION", a.t, 40, "카페", "planner_rules", "시험 준비", []); a.fatigue = 0.0
    case("지치지 않았는데 제자리 휴식(앞선 활동 카페 · 피로 0)", "거절", "A07", "15:00", intent("stay_put"), setup=calm)
    case("체크아웃 날 10:40 수영(퇴실 마감)", "거절", "A10", "10:00", intent("pool"))
    case("웰니스 3번째 · 그 시설 후기 인용 없음", "거절", "A05", "15:00", intent("sauna"),
         setup=lambda a: [a.add("activity", c, c, AD.SP.ACT[c][1](a.B), a.t, 30, "웰니스", "planner_rules", "시험 준비", []) for c in ("fitness",)])
    case("운영시간 자료 없는 곳(테네즈 파크)", "거절", "A07", "16:00", intent("tennez"))
    # 같은 곳 4시간 안 두 번째 식사 — 엔진 후보 목록에서 직접 확인
    a, w = agent("blog42", inp, "13:00")
    a.food.append((AD.hm("16:17"), "LE_PASSAGE")); a.t = AD.hm("18:00")
    offs = {o["id"] for o in AD.engine_world_for(a, w, a.t)["offers"]}
    ok = "SIMPLE_MEAL_VIEW" not in offs and "PIZZA_HILL" in offs
    R.append(dict(case="같은 곳(르 파사쥬) 4시간 안 두 번째 식사 → 그곳 저녁 후보 제외 · 다른 식당은 남음", customer="blog42", time="18:00", option="dinner",
                  expect="제외", got="제외" if ok else "남음", reason=f"남은 식사 후보 {sorted(x for x in offs if x in ('SIMPLE_MEAL_VIEW', 'PIZZA_HILL', 'MYONGWOLGWAN', 'THE_BUFFET', 'ONDAL', 'GEUMRYONG'))}", result=None, passed=ok))
    case("[대조] 워커힐에서 겪은 쉬는 방식 인용 → 반복 휴식 규칙 예외", "채택", "A07", "15:00", intent("rest_room", ["A07-F07"]),
         setup=lambda a: a.add("activity", "garden_walk", "더글라스 가든 산책", "AG_GARDEN", a.t, 20, "산책", "planner_rules", "시험 준비", []) or a.add("activity", "room_rest", "객실 휴식", a.room, a.t, 30, "객실 휴식", "planner_rules", "시험 준비", []) or a.add("activity", "cafe", "카페", "THE_PAVILION", a.t, 20, "카페", "planner_rules", "시험 준비", []))
    case("[대조] 밤 21:30 뒤 객실로 돌아가 쉬기(하루 마무리)", "채택", "A07", "21:40", intent("rest_room"),
         setup=lambda a: a.add("activity", "luxbar", "럭스바", "LUX_BAR", a.t, 30, "바", "planner_rules", "시험 준비", []) or setattr(a, "fatigue", 0.0))
    WF = AD.scenario("rt_wf", changes=[dict(at="13:00", label="와인페어 개최", levers={"WINE_FAIR": {"available": True}})])
    case("행사일 · 비투숙 → 포레스트 파크 일반 산책", "거절", "blog42", "16:00", intent("forest_walk"), sc=WF)
    case("[대조] 행사일 · 비투숙 → 와인페어(외부 유료 입장 · 행사 출입표)", "채택", "blog42", "16:00", intent("wine_fair"), sc=WF)
    def co(a):
        a.checked_out = True; a.room = None; a.end = AD.hm("22:00")
    case("행사일 · 체크아웃 뒤 → 포레스트 파크 일반 산책", "거절", "A10", "15:40", intent("forest_walk"), sc=WF, setup=co)
    case("[대조] 행사일 · 체크아웃 뒤 → 와인페어(외부 손님 자격)", "채택", "A10", "15:40", intent("wine_fair"), sc=WF, setup=co)
    case("행사일 · 투숙 → 포레스트 파크 일반 산책(행사 날 일반 이용 제한)", "거절", "A07", "16:00", intent("forest_walk"), sc=WF)
    case("[대조] 행사일 · 투숙 → 와인페어", "채택", "A07", "16:00", intent("wine_fair"), sc=WF)
    case("행사 시간 밖(20:30 · 2부 15:30~20:00)", "거절", "A07", "20:30", intent("wine_fair"), sc=WF)
    case("미개최일 · 비투숙 → 와인페어", "거절", "blog42", "16:00", intent("wine_fair"))
    def fee_case(name, pid, t, kind, krw, setup=None):   # CL-1024-21A — 2026 와인페어 입장권 장부(방문 조건별)
        a, w = agent(pid, inp, t, WF, setup)
        ok, why = LL.execute(a, w, a.t, intent("wine_fair"))
        ch = (a.log[-1].get("charge") or {}) if ok else {}
        got = f"{ch.get('price_kind')} {ch.get('krw')}"
        R.append(dict(case=name, customer=pid, time=t, option="wine_fair", expect=f"{kind} {krw}", got=got, reason=ch.get("basis", why), result=ch.get("extras"),
                      passed=ok and ch.get("price_kind") == kind and ch.get("krw") == krw))
    fee_case("입장료 · 투숙 중(A07) → 투숙객 무료(known_free)", "A07", "16:00", "known_free", 0)
    fee_case("입장료 · 비투숙(blog42 · 2인) → 성인 55,000 × 2", "blog42", "16:00", "known_paid", 110000)
    fee_case("입장료 · 체크아웃 뒤(A10) → 투숙객 무료 적용 미확인(unknown)", "A10", "15:40", "unknown", None, setup=co)
    from . import ledger as LG
    a0, _ = agent("blog42", inp, "12:00")
    rs = LG.event_blocked(a0, "BUSKING")
    R.append(dict(case="출입표에 없는 행사(가상 '버스킹') → 열지 않음", customer="blog42", time="-", option="BUSKING", expect="거절", got="거절" if rs else "채택", reason=rs, result=None, passed=bool(rs)))
    case("[대조] 비투숙 → 빛의 시어터(누구나 유료)", "채택", "blog42", "12:20", intent("theatre"))
    case("[대조] 피곤할 때 객실 휴식", "채택", "A07", "15:00", intent("rest_room"), setup=lambda a: setattr(a, "fatigue", a.rest_limit))
    pz = AD.scenario("rt_pz", changes=[dict(at="15:00", label="피자힐 저녁 마감", closed={"PIZZA_HILL": ["17:30", "20:30"]})])
    case("운영 마감 중 저녁 → 다른 식당으로 대체(피자힐 고르던 고객)", "채택", "blog41", "17:35", intent("dinner"), sc=pz)
    # 남의 사실 ID 인용 → plan() 단계에서 제거
    a, w = agent("A07", inp, "16:00")
    LL.USAGE.reset("rt")
    real_call = LL._call
    LL._call = lambda ag, prompt: dict(need="시험", interest="시험", reaction_to_notice="", intents=[dict(option="garden_walk", why="시험", fact_ids=["P060_F01", "A07-F37"], profile_basis="", alternatives=[], keep_or_change="새로 시도")])
    try:
        LL.plan(a, w, a.t)
    finally:
        LL._call = real_call
    it = a.intents[0] if a.intents else {}
    R.append(dict(case="다른 고객(blog42) 사실 ID 인용", customer="A07", time=AD.mh(a.t), option="garden_walk", expect="제거", got="제거" if "P060_F01" in it.get("dropped_fact_ids", []) else "남음",
                  reason=f"남은 인용 {it.get('fact_ids')} · 제거 {it.get('dropped_fact_ids')}", result=None, passed="P060_F01" in it.get("dropped_fact_ids", [])))
    (out / "redteam_cl19.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["| 시험 | 고객 · 시각 | 의도 | 기대 | 결과 | 이유 · 실행된 행동 |", "|---|---|---|---|---|---|"] + \
         [f"| {r['case']} | {r['customer']} {r['time']} | {r['option']} | {r['expect']} | {'✅' if r['passed'] else '❌'} {r['got']} | {r['reason'] or ''}{(' → ' + r['result']) if r['result'] else ''} |" for r in R]
    (out / "redteam_cl19.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md)); print(f"\n통과 {sum(r['passed'] for r in R)}/{len(R)}")


if __name__ == "__main__":
    main()
