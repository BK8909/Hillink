"""연속 행동 ② 중간 상태 연결 — 네 시간대 계획을 공백 없는 1박 시간표로 (10/20 · 총괄 C · 설계안 §3 · §4 구현)

  python3 itinerary.py runs/demo_1/blog25/D0_r0.json      # 시간표 출력 · <cond>_visit.json 저장

원칙
  · 핵심 행동(core)은 LLM 계획 그대로. 사이의 체크인 · 준비 · 이동 · 휴식 · 대기 · 밤 · 퇴실은 코드가 잇는다(decided_by=code_link).
  · 시각 출처를 모든 줄에 적는다: 운영표(◎ ○ △ · place_assumptions) · 계획 문장(회차) · 공용 이동 함수(walkerhill_travel_time_min · import 만) · 가정(기본값) · 계산(남는 시간).
  · 취침 · 기상 시각은 모른다 — '밤' 띠 하나로 둔다. 겹치면 코드가 자르지 않고 사건(time_conflict)으로 남긴다.
  · 새 소비 · 행동을 만들지 않는다. 쉬는 시간은 계산으로 나온 길이만큼이다.
"""
from __future__ import annotations

import json, re, sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1]))
import stage as ST                                            # noqa: E402
import walkerhill_timeline_validator as V                     # noqa: E402  (공용 · 수정 없음)

PREP_MIN, PREP_BASIS = 30, "가정 30분(짐 풀기 · 씻기)"
MIN_REST = 20
SEATING = {"PIZZA_HILL", "THE_BUFFET_D", "THE_BUFFET_B", "MOEGI", "buffet_fall_window"}   # 고정 좌석 회차(늦게 들어가지 않는다)
DEFAULT_DWELL = {"WALK": 45, "WALK_EVE": 45, "SKYARD": 60, "FITNESS": 60, "THE_PAVILION_TEA": 60, "THE_PAVILION_BINGSU": 45, "THE_PAVILION_EVE": 75, "THE_PAVILION_B": 50,
                 "WINE_FAIR": 90, "WINE_FAIR_2": 90, "LUX_BAR": 90, "MYONGWOLGWAN": 120, "ONDAL": 120, "GEUMRYONG": 120, "LE_PASSAGE": 20, "OUTSIDE": 120,
                 "DOUGLAS_SNACK": 45, "DOUGLAS_HOUR": 75, "DOUGLAS_B": 45, "THE_BUFFET_B": 60, "MORNING_POOL": 60, "RIVERPARK": 150}
ROOM = {"GRAND": "GRAND_ROOM", "VISTA": "VISTA_ROOM", "DOUGLAS": "DOUGLAS_ROOM"}
LOBBY = {"GRAND": "GRAND_LOBBY", "VISTA": "VISTA_LOBBY", "DOUGLAS": "DOUGLAS_LOBBY"}
POOL = {"GRAND": "GRAND_POOL", "VISTA": "VISTA_POOL", "DOUGLAS": "GRAND_POOL"}
PLACE_OF = {"THE_BUFFET_D": "THE_BUFFET", "THE_BUFFET_B": "THE_BUFFET", "THE_PAVILION_TEA": "THE_PAVILION", "THE_PAVILION_BINGSU": "THE_PAVILION", "THE_PAVILION_EVE": "THE_PAVILION",
            "THE_PAVILION_B": "THE_PAVILION", "WINE_FAIR": "FOREST_PARK", "WINE_FAIR_2": "FOREST_PARK", "DOUGLAS_SNACK": "DOUGLAS_LOUNGE", "DOUGLAS_HOUR": "DOUGLAS_LOUNGE", "DOUGLAS_B": "DOUGLAS_LOUNGE",
            "OUTSIDE": "HOTEL_GATE", "buffet_fall_window": "THE_BUFFET", "beer_terrace": "PIZZA_HILL"}
LABEL = {"GRAND_ROOM": "그랜드 객실", "VISTA_ROOM": "비스타 객실", "DOUGLAS_ROOM": "더글라스 객실", "GRAND_LOBBY": "그랜드 로비", "VISTA_LOBBY": "비스타 로비", "DOUGLAS_LOBBY": "더글라스 로비",
         "GRAND_POOL": "그랜드 실내 수영장", "VISTA_POOL": "비스타 실내 수영장", "THE_BUFFET": "더뷔페", "PIZZA_HILL": "피자힐", "MYONGWOLGWAN": "명월관", "ONDAL": "온달", "GEUMRYONG": "금룡", "MOEGI": "모에기",
         "THE_PAVILION": "더파빌리온", "LE_PASSAGE": "르파사쥬", "LUX_BAR": "럭스 바", "FOREST_PARK": "포레스트 파크", "SKYARD": "스카이야드", "FITNESS": "피트니스", "THEATRE_OF_LIGHT": "빛의 시어터",
         "RIVERPARK": "리버파크", "DOUGLAS_LOUNGE": "더글라스 라운지", "HOTEL_GATE": "호텔 정문(외부)", "WALK": "경내 산책로"}


def hm(m: int) -> str:
    d, r = divmod(m, 1440); return f"{'다음 날 ' if d else ''}{r // 60:02d}:{r % 60:02d}"


def mins(s: str, day: int = 0) -> int:
    h, m = s.split(":"); return day * 1440 + int(h) * 60 + int(m)


def _sessions(code: str, date: str) -> tuple[list[tuple[int, int]], str]:
    """(회차 목록 [(시작, 끝)], 출처). 회차가 없으면 운영 창 하나."""
    wd = datetime.fromisoformat(date).weekday(); md = date[5:]
    P = lambda c, i: ST.pa(c, i)[0]
    rng = lambda s: tuple(mins(x) for x in s.replace("~", "-").split("-"))
    if code == "PIZZA_HILL":
        return [(mins("11:30") + 90 * i, mins("11:30") + 90 * (i + 1)) for i in range(7)], "피자힐 회차 90분 · 1부 11:30 … 7부 20:30 ◎"
    if code == "THE_BUFFET_D":
        if md >= "12-01": return [rng(P("THE_BUFFET", "운영 · 석식 · 12월 · 월~일 1부")), rng(P("THE_BUFFET", "운영 · 석식 · 12월 · 월~일 2부"))], "더뷔페 석식 12월 회차 ◎"
        if wd == 5: return [rng(P("THE_BUFFET", "운영 · 석식 · 토·공휴일 1부")), rng(P("THE_BUFFET", "운영 · 석식 · 토·공휴일 2부"))], "더뷔페 석식 토요일 회차 ◎"
        a, b = rng(P("THE_BUFFET", "운영 · 석식 · 월~금·일")); return [(a, b)], "더뷔페 석식 운영 창 ◎ · 체류 120분 △"
    if code == "THE_BUFFET_B":
        nd = (datetime.fromisoformat(date) + timedelta(days=1)).weekday()
        if nd in (5, 6, 0): return [rng(P("THE_BUFFET", "운영 · 조식 · 토~월·공휴일 1부")), rng(P("THE_BUFFET", "운영 · 조식 · 토~월·공휴일 2부"))], "더뷔페 조식 회차 ◎ · 체류 60분 가정"
        a, b = rng(P("THE_BUFFET", "운영 · 조식 · 화~금")); return [(a, b)], "더뷔페 조식 운영 창 ◎ · 체류 60분 가정"
    if code == "MOEGI":
        return [(mins("18:00"), mins("20:30")), (mins("18:30"), mins("21:00"))], "모에기 카운터 회차 150분 ◎"
    if code in ("WINE_FAIR", "WINE_FAIR_2"):
        return [rng(P("FOREST_PARK", "와인페어 운영 · 1부")), rng(P("FOREST_PARK", "와인페어 운영 · 2부"))], "와인페어 1부 · 2부 ◎ · 체류 90분 가정"
    if code == "RIVERPARK":
        return [(mins("10:00"), mins("18:00"))], "리버파크 1부 10:00~18:00 ◎"
    WIN = {"GRAND_POOL": ("GRAND_POOL", "운영"), "VISTA_POOL": ("VISTA_POOL", "운영"), "MORNING_POOL": ("GRAND_POOL", "운영"), "SKYARD": ("SKYARD", "운영"), "THEATRE_OF_LIGHT": ("THEATRE_OF_LIGHT", "운영"),
           "FOREST_PARK": ("FOREST_PARK", "운영"), "DOUGLAS_SNACK": ("DOUGLAS_LOUNGE", "운영 · 오후 스낵"), "DOUGLAS_HOUR": ("DOUGLAS_LOUNGE", "운영 · 더글라스 아워"), "DOUGLAS_B": ("DOUGLAS_LOUNGE", "운영 · 라이트 조식"),
           "LE_PASSAGE": ("LE_PASSAGE", "운영 · 테이크아웃 피자 주문"), "FITNESS": ("WELLNESS_SAUNA", "운영")}
    if code in WIN:
        c, i = WIN[code]; v, g = ST.pa(c, i); a, b = rng(v.split("(")[0].strip())
        if code == "THEATRE_OF_LIGHT": b = mins("17:00")      # 입장 마감 ◎
        return [(a, b)], f"{LABEL.get(c, c)} {i} {v} {g}"
    FIXED = {"THE_PAVILION_TEA": ("11:00-20:00", "◎"), "THE_PAVILION_BINGSU": ("10:00-20:00", "◎"), "THE_PAVILION_EVE": ("09:00-20:00", "◎"), "THE_PAVILION_B": ("10:00-14:00", "◎"),
             "LUX_BAR": ("20:00-25:00", "◎"), "MYONGWOLGWAN": ("17:30-21:00", "◎"), "ONDAL": ("18:00-21:00", "◎"), "GEUMRYONG": ("18:00-21:00", "◎"), "WALK": ("15:00-18:00", "시간대"),
             "WALK_EVE": ("20:00-22:00", "시간대 · 가정"), "OUTSIDE": ("17:00-22:00", "가정"), "buffet_fall_window": ("17:30-22:00", "◎"), "beer_terrace": ("17:00-21:00", "가정 행사")}
    if code in FIXED:
        s, g = FIXED[code]; return [rng(s)], f"운영 창 {s} {g}"
    return [(mins("15:00"), mins("23:00"))], "운영 창 미상 · 시간대로 둠"


POOL_DEFAULT = 90   # 결정 D3 (10/21) · 바꿀 때는 변경 전후 행동 비교를 함께 남긴다


def _dwell(code: str) -> tuple[int, str]:
    # 10/21 결정 D3 — 120분은 '1회 이용 시간 상한'(◎ 운영표)으로만 쓴다. 고객이 시각을 적지 않았으면 잠정 기본 90분(가정)
    if code in ("GRAND_POOL", "VISTA_POOL"): cap = int(ST.pa("GRAND_POOL", "1회 이용 시간 상한")[0]); return min(POOL_DEFAULT, cap), f"가정 {min(POOL_DEFAULT, cap)}분(잠정 기본 · 이용 상한 {cap}분 ◎)"
    if code == "PIZZA_HILL": return 90, "회차 90분 ◎"
    if code == "THEATRE_OF_LIGHT": return int(ST.pa("THEATRE_OF_LIGHT", "회차 길이")[0]), "회차 60분 ◎"
    if code == "THE_BUFFET_D": return 120, "석식 체류 120분 △(후기 한 편)"
    if code == "MOEGI": return 150, "카운터 회차 150분 ◎"
    if code in DEFAULT_DWELL: return DEFAULT_DWELL[code], f"가정 {DEFAULT_DWELL[code]}분"
    return 60, "가정 60분"


def travel(a: str, b: str, at_min: int, date: str) -> tuple[int, str]:
    if a == b: return 0, "같은 곳"
    try:
        t = datetime.fromisoformat(date) + timedelta(minutes=at_min)
        return max(1, round(V.walkerhill_travel_time_min(a, b, t))), "공용 이동 함수(walkerhill_timeline_validator)"
    except Exception:
        return 10, "가정 10분(이동표에 없는 곳)"


def _choice_times(text: str) -> list[int]:
    return [mins(f"{int(h):02d}:{m}") for h, m in re.findall(r"(\d{1,2}):(\d{2})", text or "")]


EXIT_WORDS = r"(?:나와|나오|나서|나가|이동|마치|마무리|끝내|끝나|정리|돌아|까지)"
def _exit_times(text: str) -> list[int]:
    """계획 문장에서 '그 활동을 마치는 시각' — 시각 바로 뒤(10자 안)에 나와 · 이동 · 마치 · 까지 같은 말이 있을 때만 (예: '17:15쯤 나와 저녁으로')."""
    return [mins(f"{int(h):02d}:{m}") for h, m in re.findall(r"(\d{1,2}):(\d{2})[^\d:]{0,10}?" + EXIT_WORDS, text or "")]


def build_visit(rec: dict, resolver=None, event_log: list | None = None) -> dict:
    """resolver(snapshot, event) -> decision dict(계획 결정과 같은 모양 · decided_by=llm_event) 또는 None. 없으면 사건만 기록한다."""
    date = rec["date"]; prop = rec.get("property") or rec["stage"]["property"]
    room, lobby = ROOM[prop], LOBBY[prop]
    decs = rec["output"]["decisions"]
    acts: list[dict] = []; events: list[dict] = []
    n = [0]

    def add(kind, place, label, start, end, start_rule, end_rule, basis, decided_by="code_link", di=None, d=None, note=""):
        n[0] += 1
        a = dict(id=f"{rec['blog']}-{rec['condition']}-{n[0]:02d}", kind=kind, place=place, place_label=LABEL.get(place, place), label=label,
                 start=start, end=end, start_hm=hm(start), end_hm=hm(end) if end is not None else None, start_rule=start_rule, end_rule=end_rule, time_basis=basis,
                 decided_by=decided_by, decision_index=di, virtual=True, note=note)
        if d is not None:
            if d["option_code"] in ("WALK", "WALK_EVE"): a["place_label"] = "경내 산책로(호텔 주변)"
            a.update(option_code=d["option_code"], choice=d["choice"], cost=d.get("est_cost_krw"), main_driver=d["main_driver"], evidence_ids=d.get("evidence_ids", []), confidence=d["confidence"], is_virtual_option=d.get("is_virtual_option", False))
        acts.append(a); return a

    def place_of(code: str) -> str:
        if code in ("REST", "REST_EVE", "SLEEP_IN"): return room
        if code == "MORNING_POOL": return POOL[prop]
        if code == "WALK" or code == "WALK_EVE": return lobby
        if code == "FITNESS": return "FITNESS"
        return PLACE_OF.get(code, code)

    def _resolve(resolver, event, d, di):
        """사건 → ③ 재판단. resolver 가 없으면 None(사건만 기록)."""
        if event_log is not None: event_log.append(event)
        if resolver is None: return None
        snap = dict(now_hm=hm(now), here_label=LABEL.get(here, here), slot=d["slot"], done=[a for a in acts if a["kind"] in ("core", "checkin")],
                    remaining=[dict(slot=x["slot"], choice=x["choice"], option_code=x["option_code"]) for x in decs[di:]])
        nd = resolver(snap, event)
        if nd:
            nd = dict(nd); nd["slot"] = d["slot"]; nd["decided_by"] = "llm_event"; event["resolved_by"] = nd["option_code"]
            events[-1] = event
        return nd

    t_in = mins(ST.pa("-", "체크인 시각")[0]); t_out = mins(ST.pa("-", "체크아웃 시각")[0]) + 1440
    add("checkin", lobby, "체크인", t_in, t_in, "체크인 시각 ◎", "—", "◎ 운영표")
    here, now = lobby, t_in
    tv0, tr0 = travel(lobby, room, now, date)
    if tv0: add("move", room, "이동 → 객실", now, now + tv0, "체크인 뒤", tr0, "모델값(이동 함수)"); now += tv0
    here = room
    add("prep", room, "객실 · 짐 풀기 · 준비", now, now + PREP_MIN, "객실 도착", PREP_BASIS, "가정"); now += PREP_MIN

    def go(code, d, di, earliest, window_rule_after=None):
        """핵심 행동 하나를 놓는다 — 이동 · 대기 · 휴식을 앞에 채운 뒤 core 를 더한다. 반환: 끝난 시각 · 장소."""
        nonlocal here, now
        place = place_of(code)
        if place == room:
            return None
        sess, srule = _sessions(code, date); dw, drule = _dwell(code)
        if code in ("THE_BUFFET_B", "DOUGLAS_B", "THE_PAVILION_B", "MORNING_POOL"): sess = [(a + 1440, b + 1440) for a, b in sess]
        tv, trule = travel(here, place, now, date)
        ready = max(now + tv, earliest)
        chosen = None; srule_used = ""; adj = None   # adj = 코드가 계획 시각을 옮긴 기록(time_adjustment) · 화면에 '일정 연결 · 조정' 으로 보인다
        cand = [(a, b) for ct in _choice_times(d["choice"]) for a, b in sess if abs(a - ct) <= 5]   # 계획 문장의 시각과 맞는 회차
        feas = [(a, b) for a, b in cand if a >= ready]
        if feas:
            chosen = feas[0]; srule_used = f"계획 문장 '{hm(chosen[0])} 회차' · {srule}"
        elif cand and code not in SEATING and cand[0][1] - ready >= min(dw, 60):
            chosen = (ready, cand[0][1]); srule_used = f"계획 문장 '{hm(cand[0][0])} 회차' 안에 {hm(ready)} 입장(창형 회차 · 늦은 입장) · {srule}"
            adj = dict(by="code_link", kind="late_entry", field="start", planned=cand[0][0], planned_hm=hm(cand[0][0]), actual=ready, actual_hm=hm(ready),
                       reason=f"계획 문장은 {hm(cand[0][0])} 회차 · 앞 일정({hm(now)}) + 이동 {tv}분 뒤 도착 · 들어갈 수 있는 창형 회차라 도착 시각에 입장")
        elif cand and code in SEATING and acts and acts[-1]["kind"] == "core" and ("가정" in acts[-1]["end_rule"] or "상한" in acts[-1]["end_rule"]):
            prev = acts[-1]; tv2, _ = travel(prev["place"], place, cand[0][0], date); new_end = cand[0][0] - tv2
            if new_end - prev["start"] >= 30:
                pt = [t for t in _choice_times(prev["label"]) if prev["start"] < t < prev["end"]]   # 앞 활동 계획 문장에 적힌 나오는 시각(예: '17:15쯤 나와')
                prev["time_adjustment"] = dict(by="code_link", kind="shortened", field="end", planned=prev["end"], planned_hm=hm(prev["end"]), planned_rule=prev["end_rule"], actual=new_end, actual_hm=hm(new_end),
                                               plan_text_times=[hm(t) for t in pt],
                                               reason=f"다음 예약 회차 {hm(cand[0][0])} − 이동 {tv2}분" + (f" · 계획 문장의 '{hm(pt[0])}' 와 {abs(new_end - pt[0])}분 차이" if pt else " · 계획 문장에 나오는 시각 없음(원래 끝 시각은 코드 가정)"))
                prev["end_rule"] = f"다음 예약 회차 {hm(cand[0][0])} 에 맞춰 일찍 마침(계산 · 원래 {prev['end_rule']})"; prev["end"] = new_end; prev["end_hm"] = hm(new_end)
                now = new_end; tv, trule = tv2, "공용 이동 함수(walkerhill_timeline_validator)"
                chosen = cand[0]; srule_used = f"계획 문장 '{hm(chosen[0])} 회차' · {srule}"
            else:
                chosen = cand[0]; srule_used = f"계획 문장 '{hm(chosen[0])} 회차' · {srule}"
                events.append(dict(kind="time_conflict", at=hm(now), slot=d["slot"], text=f"{LABEL.get(place, place)} {hm(chosen[0])} 회차가 앞 활동 종료({hm(now)}) + 이동 {tv}분보다 이르다"))
        elif cand:
            chosen = cand[0]; srule_used = f"계획 문장 '{hm(chosen[0])} 회차' · {srule}"
            events.append(dict(kind="time_conflict", at=hm(now), slot=d["slot"], text=f"{LABEL.get(place, place)} {hm(chosen[0])} 회차가 앞 활동 종료({hm(now)}) + 이동 {tv}분보다 이르다"))
        else:
            for a, b in sess:
                if code in SEATING and a < ready: continue    # 좌석 회차는 진행 중인 회차에 늦게 끼어들지 않는다(다음 회차부터) — 10/21 D3 비교에서 발견
                if b - max(a, ready) >= min(dw, 60):          # 들어갈 수 있고 최소 체류가 남는 회차
                    chosen = (max(a, ready), b); srule_used = f"{srule} · 가장 이른 가능 시각"; break
        if chosen is None:
            events.append(dict(kind="closed", at=hm(ready), slot=d["slot"], text=f"{LABEL.get(place, place)} 는 {hm(ready)} 에 운영이 끝났거나 남은 시간이 없다(운영 {', '.join(hm(a) + '~' + hm(b) for a, b in sess)})"))
            return "closed"
        start = chosen[0]
        if start < now + tv:
            start = now + tv
        gap = start - tv - now
        if gap >= MIN_REST and here != room:
            tb, tbr = travel(here, room, now, date); tf, tfr = travel(room, place, now + tb, date)
            if gap - tb >= MIN_REST and start - (now + tb + tf) >= 0:
                add("move", room, "이동 → 객실", now, now + tb, "앞 활동 종료", tbr, "모델값(이동 함수)"); now += tb; here = room
                tv, trule = tf, tfr; gap = start - tv - now
        if gap >= MIN_REST:
            cue = "객실 · 씻고 쉬기 · 다음 준비" if here == room else f"{LABEL.get(here, here)} 근처에서 쉬기"
            add("rest", here, cue, now, now + gap, "앞 활동 종료", f"다음 활동 시작 − 이동 {tv}분까지(계산)", "계산"); now += gap
        if tv:
            add("move", place, f"이동 → {LABEL.get(place, place)}" + (" (순환 셔틀 ○)" if place == "PIZZA_HILL" else ""), now, now + tv, "앞 활동 종료", trule, "모델값(이동 함수)"); now += tv
        if start > now:
            add("wait", place, f"{LABEL.get(place, place)} 현장 대기", now, start, "도착", "활동 시작까지(계산)", "계산"); now = start
        end = min(start + dw, chosen[1]) if chosen[1] > start else start + dw
        # 체류 시간이 코드 가정(가정 · 상한)일 때, 계획 문장에 고객이 '언제 나온다' 고 적었으면 그 시각을 쓴다(고객의 결정 · 코드가 뒤에서 줄이지 않게)
        ex = [t for t in _exit_times(d["choice"]) if start + 15 <= t <= (chosen[1] if chosen[1] > start else start + 600)] if ("가정" in drule or "상한" in drule) else []
        if ex:
            drule = f"계획 문장 '{hm(ex[0])}' 에 마침(고객 계획 · 코드 가정 {drule} 대신)"; end = ex[0]
        c = add("core", place, d["choice"], start, end, srule_used, drule, "◎ 운영표 + 계획" if "◎" in srule + drule else "가정", d.get("decided_by", "llm_plan"), di, d)
        if adj: c["time_adjustment"] = adj
        here, now = place, end
        return end

    # 오후
    d0 = decs[0]
    if place_of(d0["option_code"]) == room:
        add("core", room, d0["choice"], now, now, "체크인 뒤", "저녁 전까지(계산)", "계산", d0.get("decided_by", "llm_plan"), 0, d0)
        rest_from = len(acts) - 1
    else:
        r = go(d0["option_code"], d0, 0, mins("15:00"))
        if r == "closed":
            nd = _resolve(resolver, events[-1], d0, 0)
            if nd and place_of(nd["option_code"]) != room: go(nd["option_code"], nd, 0, now)
            elif nd: add("core", room, nd["choice"], now, now, "사건 뒤 다시 정함", "저녁 전까지(계산)", "계산", "llm_event", 0, nd)
    # 저녁 식사
    d1 = decs[1]
    if d1["option_code"] == "LE_PASSAGE" or place_of(d1["option_code"]) == room:
        place = "LE_PASSAGE" if d1["option_code"] == "LE_PASSAGE" else room
        if place != room:
            tv, trule = travel(here, place, now, date)
            if tv: add("move", place, "이동 → 르파사쥬", now, now + tv, "앞 활동 종료", trule, "모델값(이동 함수)"); now += tv
            add("core", place, "르파사쥬 포장 주문", now, now + 20, "도착", "가정 20분", "가정", d1.get("decided_by", "llm_plan"), 1, d1); now += 20
            tv, trule = travel(place, room, now, date); add("move", room, "이동 → 객실", now, now + tv, "포장 뒤", trule, "모델값(이동 함수)"); now += tv
        c = add("core", room, d1["choice"], now, now + 60, "객실 도착", "가정 60분(객실 식사)", "가정", d1.get("decided_by", "llm_plan"), 1, d1); now += 60; here = room
        if place != room: c["cost"] = 0; c["note"] = "결제는 르파사쥬 포장 주문 때 한 번 · 객실 식사에서 다시 세지 않음"
    else:
        r = go(d1["option_code"], d1, 1, mins("17:00"))
        if r == "closed":
            nd = _resolve(resolver, events[-1], d1, 1)
            if nd and nd["option_code"] != "LE_PASSAGE" and place_of(nd["option_code"]) != room: go(nd["option_code"], nd, 1, now)
            elif nd: add("core", room if nd["option_code"] != "LE_PASSAGE" else "LE_PASSAGE", nd["choice"], now, now + 60, "사건 뒤 다시 정함", "가정 60분", "가정", "llm_event", 1, nd); now += 60
    # 저녁 이후
    d2 = decs[2]
    if place_of(d2["option_code"]) == room:
        if here != room:
            tv, trule = travel(here, room, now, date); add("move", room, "이동 → 객실", now, now + tv, "앞 활동 종료", trule, "모델값(이동 함수)"); now += tv; here = room
        add("core", room, d2["choice"], now, None, "객실 도착", "취침 시각 미상 — '밤' 띠로 둠", "계산", d2.get("decided_by", "llm_plan"), 2, d2)
    else:
        r = go(d2["option_code"], d2, 2, mins("20:00"))
        if r == "closed":
            nd = _resolve(resolver, events[-1], d2, 2)
            if nd and place_of(nd["option_code"]) != room:
                go(nd["option_code"], nd, 2, now)
            elif nd:
                if here != room:
                    tv, trule = travel(here, room, now, date); add("move", room, "이동 → 객실", now, now + tv, "앞 활동 종료", trule, "모델값(이동 함수)"); now += tv; here = room
                add("core", room, nd["choice"], now, None, "사건 뒤 다시 정함", "취침 시각 미상", "계산", "llm_event", 2, nd)
        if here != room:
            tv, trule = travel(here, room, now, date); add("move", room, "이동 → 객실", now, now + tv, "앞 활동 종료", trule, "모델값(이동 함수)"); now += tv; here = room
        if acts[-1]["end"] is not None:
            add("night", room, "객실 · 밤(취침 시각 미상)", now, None, "앞 활동 종료", "—", "계산")
    # 다음 날 아침
    d3 = decs[3]
    if place_of(d3["option_code"]) == room:
        for a in acts:
            if a["end"] is None: a["end"] = mins("07:00") + 1440; a["end_hm"] = hm(a["end"]); a["end_rule"] = "기상 시각 미상 · 07:00 은 표시용 경계"
        add("core", room, d3["choice"], mins("07:00") + 1440, t_out, "아침(기상 시각 미상 · 07:00 은 표시용)", "퇴실 11:00 ◎", "가정", d3.get("decided_by", "llm_plan"), 3, d3)
        now = t_out
    else:
        night_end_idx = len(acts)
        sess, srule = _sessions(d3["option_code"], date); place = place_of(d3["option_code"])
        tv, trule = travel(room, place, mins("08:00") + 1440, date)
        chosen = None
        for ct in _choice_times(d3["choice"]):
            for a, b in sess:
                if abs(a - ct) <= 5: chosen = (a + 1440, b + 1440); break
            if chosen: break
        if chosen is None:
            a, b = sess[-1] if len(sess) > 1 else sess[0]
            chosen = (max(a, mins("08:00")) + 1440, b + 1440); srule_used = f"{srule} · 08:00 이후 가장 이른 시각(가정)"
        else:
            srule_used = f"계획 문장 '{hm(chosen[0])}' · {srule}"
        dw, drule = _dwell(d3["option_code"])
        for a in acts:
            if a["end"] is None: a["end"] = chosen[0] - tv; a["end_hm"] = hm(a["end"]); a["end_rule"] = "다음 활동 출발까지(계산) · 취침 · 기상 시각은 미상"
        now = chosen[0] - tv
        add("move", place, f"이동 → {LABEL.get(place, place)}", now, now + tv, "아침 활동 출발", trule, "모델값(이동 함수)"); now += tv
        end = min(chosen[0] + dw, chosen[1])
        add("core", place, d3["choice"], chosen[0], end, srule_used, drule, "◎ 운영표 + 계획" if "◎" in srule else "가정", d3.get("decided_by", "llm_plan"), 3, d3); now = end; here = place
        if now < t_out:
            tv, trule = travel(here, room, now, date)
            if tv: add("move", room, "이동 → 객실", now, now + tv, "앞 활동 종료", trule, "모델값(이동 함수)"); now += tv
            if t_out - now >= MIN_REST: add("rest", room, "객실 · 짐 정리 · 자유시간", now, t_out, "아침 활동 뒤", "퇴실 11:00 까지(계산)", "계산")
    for a in acts:
        if a["end"] is None: a["end"] = t_out; a["end_hm"] = hm(t_out); a["end_rule"] = "퇴실까지(계산) · 취침 · 기상 시각은 미상"
    last = acts[-1]
    if last["place"] != lobby:
        tvo, tro = travel(last["place"], lobby, t_out, date)
        if tvo and last["end"] - tvo > last["start"]:
            last["end"] = t_out - tvo; last["end_hm"] = hm(last["end"])
            add("move", lobby, "이동 → 로비(퇴실)", t_out - tvo, t_out, "퇴실 준비", tro, "모델값(이동 함수)")
    add("checkout", lobby, "퇴실", t_out, t_out, "체크아웃 시각 ◎", "—", "◎ 운영표")
    seen_d = set(); est = 0   # 한 결정(시간대)의 비용은 한 번만 — 포장 주문 → 객실 식사처럼 한 결정이 두 활동으로 나뉘어도
    for a in acts:
        if a["kind"] == "core" and a.get("cost") and (a.get("decided_by"), a.get("decision_index")) not in seen_d:
            seen_d.add((a.get("decided_by"), a.get("decision_index"))); est += a["cost"]
    return dict(blog=rec["blog"], condition=rec["condition"], date=date, property=prop, activities=acts, events=events,
                est_spend_krw=est, spend_note="핵심 행동의 어림 비용 합(페르소나가 적은 값 · 객실 요금 미포함 · 아이 나이 미상이라 어린이 요금 추정 포함 가능)",
                legend=dict(llm_plan="판단(LLM 계획)", code_link="연결(코드)", llm_event="사건 재판단(LLM)", operator="운영자 개입"))


def main():
    for f in sys.argv[1:]:
        rec = json.loads(Path(f).read_text(encoding="utf-8")); v = build_visit(rec)
        out = Path(f).with_name(Path(f).name.replace("_r0.json", "_visit.json")); out.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"== {v['blog']} {v['condition']} · 예상 지출 {v['est_spend_krw']:,}원 · 사건 {len(v['events'])}")
        for a in v["activities"]:
            print(f"  {a['start_hm']:>12}~{a['end_hm'] or '':<12} {a['kind']:<8} {a['place_label']:<12} {a['label'][:40]:<42} [{a['decided_by']}] {a['time_basis']} | {a['start_rule'][:40]} / {a['end_rule'][:40]}")
        for e in v["events"]: print("  ⚠", e)


if __name__ == "__main__":
    main()
