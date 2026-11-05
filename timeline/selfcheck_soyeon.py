"""
내가 고친 것들의 **경계**를 찔러 본다.

    cd timeline && python selfcheck_soyeon.py

블로그 4개가 PASS 하는 것만으로는 부족하다. 그 4개는 내가 통과하도록 시각을 맞춘
것이라, 기능이 도는지가 아니라 **내가 맞춘 값이 맞는지**만 본다.
여기서는 반대로 **통과하면 안 되는 것**을 넣는다.

주의 — `DINING` 같은 상태는 `SEATED` 를 선행으로 요구한다(I5).
창만 재려는 자리에 그런 상태를 쓰면 I5 로 걸려 놓고 "창이 막았다" 고 오해한다.
그래서 `window_only()` 가 전제 조건 있는 상태를 막는다.
"""

from datetime import date, datetime, timedelta

import blog04 as BH
import blog03 as BI
import walkerhill_timeline_validator as V
from walkerhill_timeline_validator import (
    LOCATION_PRECONDITIONS,
    STATE_PRECONDITIONS,
    WALKERHILL_VENUE_WINDOWS,
    TimelineSegment,
    validate_walkerhill_timeline,
    walkerhill_travel_time_min,
)

FAILURES: list[str] = []


PENDING: list[str] = []


def pending(label, got, want, why):
    """팀 논점이 확정돼야 기대가 정해지는 검사. 지금 결과를 실패로 세지 않는다.

    실패로 세면 진짜 회귀와 구분이 안 된다 — 지금까지 '실패 10건' 안에 이게 섞여 있었다.
    """
    PENDING.append(f"{label} — {why} (현재 {'PASS' if got else 'FAIL'} · 논점 확정 시 기대 {'PASS' if want else 'FAIL'})")
    print(f"  보류   {label}  →  {'PASS' if got else 'FAIL'}   ({why})")


def chk(label, got, want):
    if got == want:
        print(f"  OK   {label}  →  {'PASS' if got else 'FAIL'}")
    else:
        FAILURES.append(label)
        print(f"  ** 틀림 ** {label}  →  {'PASS' if got else 'FAIL'} "
              f"(기대 {'PASS' if want else 'FAIL'})")


def window_only(venue, day, a, b, state="SEATED"):
    """운영 창만 재는 한 구간. 전제 조건 있는 상태는 못 쓰게 막는다.

    취합에서 경수가 **장소 전제 조건**(I5)을 넣었다 — 클럽라운지 · 더글라스 라운지는 키를
    받은 뒤에만 들어간다. 그래서 창만 재려던 이 헬퍼가 I5 로 먼저 걸려 FAIL 이 났다
    (조식 · 티타임 · 해피아워 3건). 창을 재는 게 목적이니 **키 앵커를 깔아 I5 를 비켜 간다**
    — 검증기_취합_기록 §4 의 "점검 헬퍼에 키 앵커를 넣으면 PASS" 그대로다.
    """
    assert state not in STATE_PRECONDITIONS, f"{state} 는 선행 상태를 요구한다 — I5 가 섞인다"
    segs = []
    if venue in LOCATION_PRECONDITIONS:
        # 창 시작보다 넉넉히 앞에 두어 I2(이동)도 섞이지 않게 한다.
        key_in = datetime.fromisoformat(f"{day}T{a}") - timedelta(hours=2)
        segs.append(TimelineSegment("KEY_ISSUED", "GRAND_FRONT_DESK",
                                    key_in, key_in + timedelta(minutes=5)))
    segs.append(TimelineSegment(state, venue,
                                datetime.fromisoformat(f"{day}T{a}"),
                                datetime.fromisoformat(f"{day}T{b}"),
                                machine="M7_Outlet", venue=venue))
    return validate_walkerhill_timeline(segs, enforce_stay_day=False).ok


def reachable(a, b, when="2023-08-05T12:00"):
    try:
        walkerhill_travel_time_min(a, b, datetime.fromisoformat(when))
        return True
    except KeyError:
        return False


print("[수정 1] §8.2 에 있는데 매트릭스에 없던 지점 — 판정 불가였던 게 재지는가")
# **내 블로그가 지나는 것만** 넣었다. 다른 누락 노드(모에기·명월관·테네즈·골프클럽·
# 라이브러리·체련장·사우나)는 그 시설을 지나는 후기를 맡은 사람이 찾을 몫이라 뺐다.
for a, b in [("VISTA_ROOM", "VISTA_POOL"), ("HOTEL_GATE", "VALET_DESK"),
             ("GRAND_ROOM", "PIZZA_HILL"), ("GRAND_POOL", "SKYARD"),
             ("HOTEL_GATE", "PARKING_TOWER_B1")]:
    chk(f"{a} → {b}", reachable(a, b), True)
# 취합에서 경수가 §8.2 에 있던 노드(명월관 · 모에기 · 테네즈 …)를 채웠다. 그래서 내가
# "내 범위 밖이라 판정 불가" 로 기대했던 둘은 **이제 닿는 게 맞다** (검증기_취합_기록 §4).
for a, b in [("GRAND_LOBBY", "MOEGI"), ("GRAND_LOBBY", "TENNEZ_PARK")]:
    chk(f"{a} → {b} (취합에서 경수가 노드 추가)", reachable(a, b), True)
# 아직 아무도 안 넣은 것은 여전히 판정 불가여야 한다. 슬그머니 들어오면 범위가 넓어진 것이다.
chk("GRAND_LOBBY → WALKERHILL_LIBRARY (아직 아무도 안 넣음)",
    reachable("GRAND_LOBBY", "WALKERHILL_LIBRARY"), False)

print("\n[수정 2] 수영장은 둘이다 — 그랜드 지하2층 / 비스타 3층")
chk("GRAND_POOL 과 VISTA_POOL 이 다른 노드",
    reachable("GRAND_POOL", "VISTA_POOL"), True)
g = walkerhill_travel_time_min("GRAND_ROOM", "GRAND_POOL", datetime(2023, 5, 12, 12, 0))
v = walkerhill_travel_time_min("GRAND_ROOM", "VISTA_POOL", datetime(2023, 5, 12, 12, 0))
chk(f"그랜드 객실에서 둘까지 거리가 다르다 ({g:.0f}분 vs {v:.0f}분)", g != v, True)

print("\n[수정 2-b · 9/29] 피트니스도 둘이다 — 비스타 3층 웰니스 클럽 / 그랜드 지하 2층")
# 수정 2 에서 "후기가 지나지 않아" 뒀던 체련장을, 개발용 후기(19 · 27 · 45)가 지나가서 넣었다.
_t = datetime(2023, 5, 12, 12, 0)
_vf = walkerhill_travel_time_min("VISTA_ROOM", "VISTA_FITNESS", _t)
_gf = walkerhill_travel_time_min("VISTA_ROOM", "FITNESS", _t)
chk(f"비스타 객실에서는 비스타 피트니스가 더 가깝다 ({_vf:.0f}분 vs 그랜드 {_gf:.0f}분)", _vf < _gf, True)
chk("수영장과 피트니스는 같은 클럽 안이다 (1분)",
    walkerhill_travel_time_min("VISTA_POOL", "VISTA_FITNESS", _t) == 1, True)
chk("VISTA_FITNESS 새벽 3시", window_only("VISTA_FITNESS", "2025-06-10", "03:00", "03:40", "CHECKED_IN"), False)
chk("VISTA_FITNESS 06:30~07:30", window_only("VISTA_FITNESS", "2025-06-10", "06:30", "07:30", "CHECKED_IN"), True)
chk("VISTA_FITNESS 22시 마감 뒤", window_only("VISTA_FITNESS", "2025-06-10", "22:00", "22:40", "CHECKED_IN"), False)
# 넣지 않은 것은 여전히 없어야 한다 — 슬그머니 들어오면 범위가 넓어진 것이다
chk("사우나는 가르지 않았다 (WELLNESS_SAUNA 하나 — 공식엔 그랜드 · 비스타 두 곳 · 시각은 같고 비스타 요금 안내가 숨겨져 있다 · 10/11)", "VISTA_SAUNA" in V._INTERNAL_GRAPH, False)
chk("비스타 라이브러리 노드는 없다 (워커힐 라이브러리는 그랜드 2층 하나)", "VISTA_LIBRARY" in V._INTERNAL_GRAPH, False)

print("\n[출입 표 · 9/29] 시설마다 누가 들어가나 — 비투숙을 스카이야드 · 포레스트파크로 보내던 것")
E = V.Entry
_ng = dict(is_guest=False)
def _g(building, **kw):
    return dict(is_guest=True, building=building, **kw)
# 노드가 새로 들어오면 여기서 걸린다 — 표에 칸이 없으면 '모름' 으로 조용히 지나가기 때문
_miss = sorted(set(V._INTERNAL_GRAPH) ^ set(V.FACILITY_ACCESS))
chk(f"검증기 노드 {len(V._INTERNAL_GRAPH)}곳을 표가 빠짐없이 덮는다{' — 어긋남 ' + str(_miss) if _miss else ''}",
    not _miss, True)
chk("비투숙 칸에 '무료' 는 없다 (특전은 투숙객 것)",
    all(a.non_guest is not E.FREE for a in V.FACILITY_ACCESS.values()), True)
_rules = {k: V.FACILITY_ACCESS[k].rule for k in ("SKYARD", "FOREST_PARK", "GRAND_LIBRARY", "RIVERPARK", "THEATRE_OF_LIGHT")}
chk(f"경수가 물은 세 갈래 {_rules}",
    _rules == {"SKYARD": "투숙객만", "FOREST_PARK": "투숙객만", "GRAND_LIBRARY": "투숙객만",
               "RIVERPARK": "투숙객만", "THEATRE_OF_LIGHT": "유료면 비투숙도"}, True)
# 경수가 짚은 셋 — 비투숙은 셋 다 못 들어간다
chk("비투숙 → 스카이야드 (blog41 게시 안내 '이용대상' 에 투숙 고객만)", V.may_enter("SKYARD", **_ng), False)
chk("비투숙 → 포레스트파크 (blog42 게시 안내 '이용대상 : 호텔투숙객')", V.may_enter("FOREST_PARK", **_ng), False)
chk("비투숙 → 라이브러리 (blog41 '투숙객 전용 라이브러리로 객실 키 터치 후 입장')", V.may_enter("GRAND_LIBRARY", **_ng), False)
chk("체크아웃 뒤 라이브러리 (blog25 '체크아웃후에는 입장이 불가능')",
    V.may_enter("GRAND_LIBRARY", **_g("GRAND", checked_out=True)), False)
chk("체크아웃 전 비스타 투숙객 → 라이브러리 (blog19 '2층 워커힐 라이브러리')",
    V.may_enter("GRAND_LIBRARY", **_g("VISTA")), True)
chk("체크아웃 뒤 스카이야드 (blog35 '엘레베이터에서 객실 카드를 찍어야')",
    V.may_enter("SKYARD", **_g("VISTA", checked_out=True)), False)
# "비스타 투숙객만" 은 비투숙 칸만 맞다 — 다른 투숙객은 돈을 내면 들어간다 (blog03 B 는 내 후기다)
chk("그랜드 투숙 · 클럽 아님 → 스카이야드는 유료로 들어간다 (blog41 '그 외 투숙 고객 유료' · blog03 B)",
    V.facility_entry("SKYARD", **_g("GRAND")) is E.PAID, True)
chk("그랜드 클럽 → 스카이야드 무료 (blog41 '클럽스위트 객실 이상' · blog48 · blog51)",
    V.facility_entry("SKYARD", **_g("GRAND", club_access=True)) is E.FREE, True)
chk("더글라스 → 스카이야드는 유료 (클럽 칸으로 새지 않는다 — '그 외 투숙 고객')",
    V.facility_entry("SKYARD", **_g("DOUGLAS", club_access=True)) is E.PAID, True)
chk("그랜드 투숙 → 비스타 수영장은 못 쓴다 (blog41 '비스타 투숙객 전용 메인풀')",
    V.may_enter("VISTA_POOL", **_g("GRAND")), False)
# 더글라스 페르소나의 club_access 는 더글라스 라운지 자격이다. 그랜드 클럽 칸으로 새면 안 된다
chk("더글라스 club_access → 그랜드 클럽라운지는 모름 (무료로 새지 않는다)",
    V.facility_entry("GRAND_CLUB_LOUNGE", **_g("DOUGLAS", club_access=True)) is E.UNKNOWN, True)
# 9/30 공식 확인으로 고친 셋 (walkerhill.com)
chk("비투숙 → 리버파크 불가 (공식 '객실 투숙객 한정 유료 시설')", V.may_enter("RIVERPARK", **_ng), False)
chk("투숙 → 리버파크는 유료로 들어간다 (공식 '1객실, 1박당 1회')",
    V.facility_entry("RIVERPARK", **_g("GRAND")) is E.PAID, True)
chk("비투숙 → 테네즈 불가 · 투숙 → 유료 (공식 '피트니스 회원 및 투숙객 전용 유료 시설')",
    V.may_enter("TENNEZ_PARK", **_ng) is False and V.facility_entry("TENNEZ_PARK", **_g("VISTA")) is E.PAID, True)
chk("체크아웃 뒤 비스타 수영장 (공식 '체크아웃 전까지만 이용이 가능합니다')",
    V.may_enter("VISTA_POOL", **_g("VISTA", checked_out=True)), False)
chk("체크아웃 뒤 비스타 피트니스 (같은 '피트니스 / 수영장 공통 이용 안내')",
    V.may_enter("VISTA_FITNESS", **_g("VISTA", checked_out=True)), False)
chk("비투숙 → 더뷔페 (blog40 — 식당은 누구나)", V.may_enter("THE_BUFFET", **_ng), True)
# 모름은 막지도 열지도 않는다 — False 로 새면 근거 없이 막는 것이다
chk("비투숙 → 그랜드 실내수영장은 모름 (POOL_DAY_PASS 가 어느 수영장인지 안 적힘)",
    V.may_enter("GRAND_POOL", **_ng) is None, True)
chk("표에 없는 곳(인천공항)은 모름", V.may_enter("ICN_T1", **_ng) is None, True)

# 개발용 정답 대조 — 후기가 **실제로 간 곳**을 표가 막으면 표가 틀린 것이다.
# 시험용(봉인 대기)은 읽지 않는다. 못 씀 표시한 후기도 뺀다.
# 파일은 **이 스크립트 옆에서** 찾는다 — 현재 폴더 기준이면 저장소 루트에서 돌렸을 때
# 0편을 읽고 "0건을 막지 않는다" 로 통과해 버린다.
import importlib as _il, re as _re
from pathlib import Path as _Path
from sealed import SEALED_WAIT, unusable
_nums = sorted({int(m.group(1)) for f in _Path(__file__).resolve().parent.glob("persona_blog*.py")
                if (m := _re.fullmatch(r"persona_blog(\d\d)\.py", f.name))}
               - SEALED_WAIT)
_blocked, _seen = [], 0
# 표가 막아도 되는 방문 — 규정이 그 뒤에 바뀌었거나 에이전트가 다루지 않는 손님이라 **이유를 적고** 뺀다.
# 여기 없는 막힘은 전부 실패다.
_ACCESS_EXCEPTIONS = {
    ("blog04_ALT", "RIVERPARK"): "2023 · 숙박 없이 숙박 패키지 특전 이용권으로 입장. 2026 공식은 '객실 투숙객 한정'",
}
_excepted = []
for _n in _nums:
    _P = _il.import_module(f"persona_blog{_n:02d}")
    if unusable(_P):
        continue
    for _suf in ("", "_ALT"):
        if not hasattr(_P, "PERSONA" + _suf):
            continue
        _p = getattr(_P, "PERSONA" + _suf)
        for _place in getattr(_P, "TRUTH_VISITED" + _suf):
            if _place not in V._INTERNAL_GRAPH:
                continue
            _seen += 1
            if V.may_enter(_place, is_guest=_p.is_guest, building=_p.property,
                           club_access=_p.club_access) is False:
                if (f"blog{_n:02d}{_suf}", _place) in _ACCESS_EXCEPTIONS:
                    _excepted.append((f"blog{_n:02d}{_suf}", _place))
                else:
                    _blocked.append(f"blog{_n:02d}{_suf} {_place}")
chk(f"개발용 정답이 간 곳 {_seen}건을 표가 하나도 막지 않는다{' — 막힘 ' + str(_blocked) if _blocked else ''}"
    f" (이유를 적은 예외 {len(_excepted)}건)",
    _seen > 0 and not _blocked, True)
# 예외 목록이 실제로 쓰이는지도 본다 — 안 쓰이는 예외가 남으면 나중에 진짜 막힘을 가린다
chk("예외 목록의 방문이 전부 실제로 막힌다 (남는 예외 없음)", set(_excepted) == set(_ACCESS_EXCEPTIONS), True)
for (_who, _where), _why in _ACCESS_EXCEPTIONS.items():
    print(f"       예외 {_who} {_where} — {_why}")

print("\n[가정표 · 9/30] 장소 숫자 — 가격 · 좌석 · 객실 수 · 운영 시간 (place_assumptions.csv)")
# 웹 출처 줄(walkerhill.com 173 · 관광공사 2 · 빛의 시어터 운영사 6)은 9/30 에 브라우저로 181건 전부
# 대조했다(docs/가정표_장소.md) · 10/1 에 walkerhill.com 173 · 운영사 6 을 다시 대조해 바뀐 11줄을 고쳤다.
# 공식 메뉴판 PDF 5줄 · 후기 원문은 저장소 밖이라 여기서는 못 본다.
# 여기서 보는 것 — 모양 · 등급 · 회사 문서 근거 · 계산 · 값과 근거 속 숫자.
_rows = V.load_place_assumptions()
_cols = ["구분", "장소코드", "항목", "값", "단위", "조건", "등급", "출처", "근거", "확인일", "현장확인", "비고"]
chk(f"가정표를 읽는다 ({len(_rows)}줄) · 칸 이름이 맞다",
    len(_rows) > 0 and list(_rows[0].keys()) == _cols, True)
_codes = set(V._INTERNAL_GRAPH) | {"-"}
chk("장소코드는 검증기 장소 또는 '-' 뿐이다", all(r["장소코드"] in _codes for r in _rows), True)
chk("등급은 ◎ ○ △ 모름 넷 중 하나다", all(r["등급"] in ("◎", "○", "△", "모름") for r in _rows), True)
chk("값이 있는 줄은 근거 문장이 있고 · 모름 줄은 값이 비어 있다",
    all((r["값"] != "" and r["근거"] != "") if r["등급"] != "모름" else r["값"] == "" for r in _rows), True)
_doc_path = _Path(__file__).resolve().parent.parent / "docs" / "walkerhill-guest-state-machine.md"
_doc = _re.sub(r"\s+", " ", _doc_path.read_text(encoding="utf-8"))
_miss_doc = [r["항목"] for r in _rows if r["출처"].startswith("회사 문서") and r["등급"] != "모름"
             and _re.sub(r"\s+", " ", r["근거"]) not in _doc]
chk(f"회사 문서 근거 {sum(r['출처'].startswith('회사 문서') and r['등급'] != '모름' for r in _rows)}줄이 문서에 글자 그대로 있다"
    f"{' — 없음 ' + str(_miss_doc) if _miss_doc else ''}", not _miss_doc, True)
_bad_calc = [r["항목"] for r in _rows if r["출처"] == "계산"
             and round(eval(r["근거"].replace(",", "").replace("÷", "/"), {"__builtins__": {}})) != int(r["값"])]
chk("계산 줄은 근거 식의 결과와 값이 같다", not _bad_calc, True)
def _money_ok(r):
    v = int(r["값"])
    if v == 0:
        return "무료" in r["근거"]
    return f"{v:,}" in r["근거"] or (v % 10_000 == 0 and f"{v // 10_000}만원" in r["근거"])
_bad_money = [r["항목"] for r in _rows if r["단위"].startswith("원") and r["값"] and r["출처"] != "계산" and not _money_ok(r)]
chk(f"금액 줄의 값이 근거 문장 속 숫자와 같다{' — ' + str(_bad_money) if _bad_money else ''}", not _bad_money, True)
# 회사 문서가 빠뜨린 값 — 이번에 공식으로 채운 것이 남아 있어야 한다
_din = [r for r in _rows if r["장소코드"] == "THE_BUFFET" and r["항목"] == "중식(주말) · 석식 성인"]
chk("더뷔페 석식 성인 198,000 (회사 문서는 '—' 로 비웠던 값)", bool(_din) and _din[0]["값"] == "198000", True)
_slot = [r for r in _rows if r["장소코드"] == "PIZZA_HILL" and r["항목"] == "회차 길이"]
chk("피자힐 회차 90분 (회사 문서 '타임당 2시간' 과 다름)", bool(_slot) and _slot[0]["값"] == "90", True)
_tol = [r for r in _rows if r["장소코드"] == "THEATRE_OF_LIGHT" and r["항목"] == "운영"]
chk("빛의 시어터 10:00-18:00 (운영사 공식 · 10/11 검증기 창 — 에이전트 임시값 10:00-19:00 은 뺐다)",
    bool(_tol) and _tol[0]["값"] == "10:00-18:00", True)
# 등급을 매긴 값은 출처가 적혀 있어야 한다 — 추정(△)도 무엇에서 나왔는지 (계산 · 후기 · 관광공사) 가 있다
chk("값이 있는 줄은 전부 출처 칸이 있다 ('-' 가 아니다)",
    all(r["출처"] not in ("", "-") for r in _rows if r["등급"] != "모름"), True)
_field = sum(r["현장확인"] == "Y" for r in _rows)
print(f"       현장 확인 표시 {_field}줄 · 등급 " + " · ".join(f"{g} {sum(r['등급'] == g for r in _rows)}" for g in ("◎", "○", "△", "모름")))
_yn = [r for r in _rows if r["장소코드"] == "MYONGWOLGWAN" and r["항목"] == "정식 · 한우 양념갈비 정식 (2인 이상)"]
chk("명월관 한우 양념갈비 정식 155,000 (회사 문서 179,000 은 등심 정식 값 — 메뉴판 9/3 판 20쪽 · 10/8 판 19쪽)",
    bool(_yn) and _yn[0]["값"] == "155000", True)

print("\n[상품표 · 10/1] 업장별 상품 · 단가 · 판매 기간 (menu.csv)")
# 홈페이지 문구 121개 · 메뉴판 PDF 인용 96개 · 후기 원문은 10/1 에 브라우저 · 받은 파일로 대조했다(docs/상품표.md).
# 여기서 보는 것 — 모양 · 칸 형식 · 근거 속 단가 · 회사 문서 인용 · 가정표 · 대표님 원장과 맞는지.
import csv as _csv
with open(_Path(__file__).resolve().parent / "menu.csv", encoding="utf-8-sig", newline="") as _f:
    _menu = list(_csv.DictReader(_f))
_mcols = ["업장", "상품", "단가", "단위", "요일제한", "시간제한", "판매시작", "판매종료", "근거", "등급", "포함", "원장상품", "객실"]
chk(f"상품표를 읽는다 ({len(_menu)}줄) · 앞 9칸이 부탁받은 순서다 (뒤에 등급 · 포함 · 원장상품 · 객실)",
    len(_menu) > 0 and list(_menu[0].keys()) == _mcols, True)
chk("업장 · 상품이 겹치지 않는다", len({(r["업장"], r["상품"]) for r in _menu}) == len(_menu), True)
chk("등급은 ◎ ○ △ 셋 중 하나다", all(r["등급"] in ("◎", "○", "△") for r in _menu), True)
_DAY = _re.compile(r"(|주중|주말|[월화수목금토일]+([+-]공휴일)?|지정일 \d\d-\d\d(,\d\d-\d\d)*)")
_TIME = _re.compile(r"(|\d\d:\d\d-\d\d:\d\d(,\d\d:\d\d-\d\d:\d\d)*)")


def _period_ok(r):
    if not r["판매시작"] and not r["판매종료"]:
        return True
    try:
        return date.fromisoformat(r["판매시작"]) <= date.fromisoformat(r["판매종료"])
    except ValueError:
        return False


_bad_fmt = [r["상품"] for r in _menu if not (_DAY.fullmatch(r["요일제한"]) and _TIME.fullmatch(r["시간제한"])
                                              and _period_ok(r) and r["단가"].isdigit())]
chk(f"요일제한 · 시간제한 · 판매 기간 · 단가 칸 형식{' — ' + str(_bad_fmt) if _bad_fmt else ''}", not _bad_fmt, True)


def _menu_money_ok(r):
    v = int(r["단가"])
    if r["근거"].startswith("대표님 원장"):
        return True  # 아래 원장 결제 단가로 본다
    if v == 0:
        return "무료" in r["근거"]
    return f"{v:,}" in r["근거"] or (v % 10_000 == 0 and f"{v // 10_000}만원" in r["근거"])


_bad_ws = [r["상품"] for r in _menu if any(("⋯" in v or "\t" in v or "  " in v or v != v.strip()) for v in r.values())]
chk(f"칸에 ⋯ · 탭 · 겹친 공백이 없다 (근거 인용은 원문 글자 그대로){' — ' + str(_bad_ws) if _bad_ws else ''}", not _bad_ws, True)
_bad_mm = [r["상품"] for r in _menu if not _menu_money_ok(r)]
chk(f"단가가 근거 문장 속 숫자와 같다 (0원은 '무료'){' — ' + str(_bad_mm) if _bad_mm else ''}", not _bad_mm, True)
_quote = lambda r: (_m.group(1) if (_m := _re.search(r'"(.*?)"', r["근거"])) else None)
_miss_mdoc = [r["상품"] for r in _menu if r["근거"].startswith("회사 문서")
              and (_quote(r) is None or _re.sub(r"\s+", " ", _quote(r)) not in _doc)]
chk(f"회사 문서 인용이 문서에 글자 그대로 있다{' — ' + str(_miss_mdoc) if _miss_mdoc else ''}", not _miss_mdoc, True)
# 10/5 — 근거에 적힌 **항목 이름**까지 맞는 줄 하나와 대조한다 ("가정표 코드 · 항목 ← …", 객실 정가는 "항목 (조건)").
# 전에는 같은 장소 · 같은 인용인 줄이 아무거나 하나 있으면 통과해서, 인용이 같은 줄이 여럿인 리버파크에서
# 가리킨 줄의 인용이 틀려도 못 잡았다.
_ga_ref = lambda r: _re.match(r"가정표 (\S+) · (.+?) ← ", r["근거"])
_ga_hit = lambda code, item: [g for g in _rows if g["장소코드"] == code and item in (g["항목"], f'{g["항목"]} ({g["조건"]})')]
_bad_ga = [r["상품"] for r in _menu if r["근거"].startswith("가정표 ")
           and not ((_m2 := _ga_ref(r)) and len(_h := _ga_hit(*_m2.groups())) == 1 and _h[0]["근거"] == _quote(r))]
chk(f"가정표에서 옮긴 {sum(r['근거'].startswith('가정표 ') for r in _menu)}줄은 그 장소 가정표 줄의 근거 그대로다"
    f"{' — ' + str(_bad_ga) if _bad_ga else ''}", not _bad_ga, True)
_onto = {}
with open(_Path(__file__).resolve().parent / "ontology_journey_shh.csv", encoding="utf-8-sig", newline="") as _f:
    for _o in _csv.DictReader(_f):
        if _o["필터종류"] == "전체":
            _onto[(_o["업장"], _o["상품"])] = int(_o["순매출"]) / int(_o["수량"]) * 1.1  # 결제 단가 (부가세 포함)
_L3 = {"파빌리온": "더파빌리온", "워키": "워키 · 숲·웰니스 프로그램"}
_linked = {}
for r in _menu:
    if r["원장상품"]:
        _linked.setdefault((_L3.get(r["업장"], r["업장"]), r["원장상품"]), []).append(int(r["단가"]))
_bad_link = [k for k, v in _linked.items() if k not in _onto or round(_onto[k]) not in v]
chk(f"원장상품 {len(_linked)}개가 대표님 원장에 있고 결제 단가가 상품표 단가와 같다"
    f"{' — ' + str(_bad_link) if _bad_link else ''}", not _bad_link, True)
_mw = [r for r in _menu if r["업장"] == "명월관" and r["상품"] in ("한우 등심 정식", "한우 양념갈비 정식")]
chk("명월관 정식 — 등심 179,000 · 양념갈비 155,000", sorted(int(r["단가"]) for r in _mw) == [155000, 179000], True)
print(f"       상품표 등급 " + " · ".join(f"{g} {sum(r['등급'] == g for r in _menu)}" for g in ("◎", "○", "△"))
      + f" · 판매 기간 있는 줄 {sum(bool(r['판매시작']) for r in _menu)}"
      + f" · 원장 L4 {len(_onto)}개 중 {len(_linked)}개 이음 (못 이은 것: "
      + ", ".join(sorted({k[0] for k in _onto if k not in _linked})) + ")")

print("\n[상품표 · 10/2] 객실 칸 — 객실 상품이 묶인 객실 유형과 실 수")
# 유형은 패키지 상세의 객실 줄 · 실 수는 객실 페이지 '호텔 N층 (N실)' — 10/2 브라우저로 46개 대조 (docs/상품표.md).
_ROOMCELL = _re.compile(r"[^+]+? (\d+실|모름)( \+ [^+]+? (\d+실|모름))*")
_addon = {"엑스트라 베드", "클럽 스위트 1인 추가 · 클럽라운지", "클럽 스위트 1인 추가 · 조식"}
_is_room = lambda r: r["업장"] in ("그랜드", "더글라스", "비스타") and r["상품"] not in _addon
_bad_rc = [r["상품"] for r in _menu if (_ROOMCELL.fullmatch(r["객실"]) is None) if _is_room(r)] \
    + [r["상품"] for r in _menu if r["객실"] and not _is_room(r)]
chk(f"객실 상품 {sum(map(_is_room, _menu))}줄은 객실 칸이 '유형 N실' · '유형 모름' 꼴이고 나머지 줄은 비어 있다"
    f"{' — ' + str(_bad_rc) if _bad_rc else ''}", not _bad_rc, True)
_ga_n = {g["항목"][len("실 수 · "):]: g["값"] + "실" for g in _rows
         if g["장소코드"] == "GRAND_ROOM" and g["항목"].startswith("실 수 · ") and g["단위"] == "실" and g["등급"] == "◎"}
_parts = [(r["업장"], *p.rsplit(" ", 1)) for r in _menu if _ROOMCELL.fullmatch(r["객실"]) for p in r["객실"].split(" + ")]
_bad_n = sorted({(b, t, n) for b, t, n in _parts if n != "모름" and not (b == "그랜드" and _ga_n.get(t) == n)
                 and (b, t, n) != ("그랜드", "빌라 2604호", "1실")})
chk(f"실 수는 가정표 '실 수 · 유형' 줄 값 그대로다 (빌라 2604호는 방 번호 하나){' — ' + str(_bad_n) if _bad_n else ''}",
    not _bad_n, True)
_same = {}
for b, t, n in _parts:
    _same.setdefault((b, t), set()).add(n)
chk("같은 건물 · 같은 유형은 어느 줄에서나 실 수가 같다", all(len(v) == 1 for v in _same.values()), True)
_rack_t = [r["상품"] for r in _menu if r["포함"] == "객실만 (표준 요금)"
           and r["객실"].rsplit(" ", 1)[0] != r["상품"][len("표준 요금 · "):].split(" (")[0]]
chk(f"표준 요금 줄의 유형은 상품 이름의 객실 그대로다{' — ' + str(_rack_t) if _rack_t else ''}", not _rack_t, True)
_kq = {r["상품"]: r["객실"] for r in _menu if r["업장"] == "그랜드"}
chk("경수 첫 판의 한정 객실 — 바비 2줄은 2실을 같이 쓰고 · 빌라 3줄은 2604호 1실",
    [_kq.get("Barbie Suite · Forever Barbie"), _kq.get("Barbie Suite · New Dreams")] == ["바비 스위트 2실"] * 2
    and {_kq.get(k) for k in _kq if k.startswith("[빌라]")} == {"빌라 2604호 1실"}, True)
_n_known = sum(bool(_re.search(r"\d+실", r["객실"])) for r in _menu)
_n_notype = sum("안 적힘" in r["객실"] for r in _menu)
print(f"       객실 칸 — 실 수 아는 줄 {_n_known} · 유형만 아는 줄 {sum(map(_is_room, _menu)) - _n_known - _n_notype}"
      f" · 유형 안 적힘 {_n_notype}")

print("\n[공휴일 · 10/2 · 10/5] 상품표 '+공휴일 · -공휴일' 이 쓰는 달력 — menu.py · 검증기")
# 「관공서의 공휴일에 관한 규정」 제2조의 날짜에 제3조 대체 규칙을 다시 적용해 손 달력과 맞춘다.
# 음력 날짜 · 선거일 · 임시공휴일은 월력요항 · 국무회의 의결 그대로 넣는다.
# 10/5 — 검증기 요일 창도 같은 뜻의 달력을 쓴다 (V.PUBLIC_HOLIDAYS). 2025 도 같은 방법으로 다시 계산한다.
import menu as _mn


def _law_holidays(y, seol, buddha, chuseok, fixed_extra=(), temporary=(), national=(), weekend_sub_extra=()):
    """→ (공휴일 전체, 대체공휴일). national = 국경일 (3·1절 · 광복절 · 개천절 · 한글날 + 그 해 공휴일인 제헌절)."""
    D = lambda m, d: date(y, m, d)
    sub_weekend = list(national) + [buddha, D(5, 5), D(12, 25)] + list(weekend_sub_extra)   # 제3조①1 — 토 · 일과 겹치면 대체
    lunar3 = [seol + timedelta(i) for i in (-1, 0, 1)] + [chuseok + timedelta(i) for i in (-1, 0, 1)]   # 제3조①2 — 일요일과 겹칠 때만
    hol = set(sub_weekend) | set(lunar3) | {D(1, 1), D(6, 6)} | set(fixed_extra) | set(temporary)   # 1/1 · 현충일 · 선거일 · 임시는 대체 없음
    alld = sub_weekend + lunar3                                           # 제3조①3 — 서로 겹치면 겹친 만큼 대체
    need = sorted([d for d in sub_weekend if d.weekday() >= 5] + [d for d in lunar3 if d.weekday() == 6]
                  + [d for d in set(alld) for _ in range(alld.count(d) - 1)])
    sub = set()
    for d0 in need:
        d1 = d0 + timedelta(1)
        while d1.weekday() >= 5 or d1 in hol or d1 in sub:
            d1 += timedelta(1)
        sub.add(d1)
    return hol | sub, sub


# 2026 — 규정 (2026.5.1 시행) · 우주항공청 2026 월력요항. 노동절 (2026.5.1 부터) · 제헌절 (2026.5.11 부터) 이 공휴일
_D = lambda m, d: date(2026, m, d)
_law, _sub = _law_holidays(2026, _D(2, 17), _D(5, 24), _D(9, 25), fixed_extra=[_D(6, 3)],
                           national=[_D(3, 1), _D(7, 17), _D(8, 15), _D(10, 3), _D(10, 9)], weekend_sub_extra=[_D(5, 1)])
chk("대체공휴일 다시 계산 = 월력요항 (3/2 · 5/25 · 8/17 · 10/5)", sorted(_sub), [_D(3, 2), _D(5, 25), _D(8, 17), _D(10, 5)])
_mh = set(_mn.HOLIDAYS_2026)
chk(f"menu.py 달력 {len(_mh)}일 = 규정으로 다시 계산한 {len(_law)}일"
    f"{' — 빠짐 ' + str(sorted(_law - _mh)) if _law - _mh else ''}"
    f"{' — 더 있음 ' + str(sorted(_mh - _law)) if _mh - _law else ''}", _mh == _law, True)
chk("검증기 2026 달력 = menu.py 달력 (요일 창과 상품표가 같은 날을 공휴일로 본다)",
    set(V.PUBLIC_HOLIDAYS[2026]) == _mh, True)
# 2025 — 우주항공청 2025 월력요항 (2024.6.20) · 임시공휴일 1/27 (2025.1.14 국무회의) · 6/3 대통령선거일 (2025.4.8 국무회의)
# 어린이날과 부처님오신날이 5/5 로 겹치고, 추석 연휴 첫날 10/5 가 일요일이다. 제헌절 · 노동절은 아직 공휴일이 아니다.
_E = lambda m, d: date(2025, m, d)
_law25, _sub25 = _law_holidays(2025, _E(1, 29), _E(5, 5), _E(10, 6), temporary=[_E(1, 27), _E(6, 3)],
                               national=[_E(3, 1), _E(8, 15), _E(10, 3), _E(10, 9)])
chk("2025 대체공휴일 다시 계산 = 월력요항 (3/3 · 5/6 · 10/8)", sorted(_sub25), [_E(3, 3), _E(5, 6), _E(10, 8)])
_vh25 = set(V.PUBLIC_HOLIDAYS[2025])
chk(f"검증기 2025 달력 {len(_vh25)}일 = 규정으로 다시 계산한 {len(_law25)}일"
    f"{' — 빠짐 ' + str(sorted(_law25 - _vh25)) if _law25 - _vh25 else ''}"
    f"{' — 더 있음 ' + str(sorted(_vh25 - _law25)) if _vh25 - _law25 else ''}", _vh25 == _law25, True)
chk("검증기 달력은 2025 · 2026 두 해 (그 밖의 해는 공휴일 없음으로 본다 — 검증기 주석)",
    sorted(V.PUBLIC_HOLIDAYS), [2025, 2026])
# 달력이 없는 해의 후기 날짜 — 공휴일이면 창이 달라지는 날만 골라, 10/5 에 확인한 21일 안에 있는지 본다.
# 새 후기가 그런 날짜를 들고 오면 여기서 걸린다 → 그 해 공휴일을 확인하고 아래 목록이나 달력에 넣는다.
import glob as _glob
import importlib as _il
from pathlib import Path as _Path
_CHECKED_1005 = {date(2000, 1, 1), date(2000, 1, 2), date(2019, 2, 9), date(2019, 2, 10), date(2021, 11, 15),
                 date(2021, 11, 16), date(2022, 8, 4), date(2022, 8, 5), date(2023, 5, 12), date(2023, 5, 13),
                 date(2023, 8, 5), date(2023, 8, 26), date(2023, 8, 27), date(2023, 8, 28), date(2023, 8, 29),
                 date(2023, 9, 24), date(2023, 9, 25), date(2024, 2, 15), date(2024, 2, 16), date(2024, 6, 15),
                 date(2024, 6, 16),
                 # 10/11 — blog39 를 원문 '재작년' 대로 2024-09-04 (수) 로 옮겼다. 2024 추석 연휴는 9/16~18 이고 9월 초엔 공휴일이 없다 (월력요항)
                 date(2024, 9, 4), date(2024, 9, 5), date(2024, 9, 6)}
_stay_days = set()
# 실행 위치(cwd)가 아니라 이 파일 옆에서 찾는다 — 저장소 루트에서 돌리면 0개를 찾고도 조용히 통과했다
_persona_files = sorted(_glob.glob(str(_Path(__file__).resolve().parent / "persona_blog*.py")))
chk(f"후기 페르소나 파일을 찾았다 ({len(_persona_files)}개)", len(_persona_files) > 0, True)
for _f in _persona_files:
    _pm = _il.import_module(_Path(_f).stem)
    if getattr(_pm, "START_AT", None) is None:
        continue
    _n = max(1, getattr(getattr(_pm, "PERSONA", None), "nights", 0) or 0)
    _stay_days |= {(_pm.START_AT + timedelta(days=_i)).date() for _i in range(_n + 1)}
import blog01 as _b1, blog02 as _b2, blog05 as _b5, blog06 as _b6
for _segs in (_b1.RUN_C, _b2.BLOG02_TIMELINE, BI.STAY_A + BI.STAY_B, BH.VISIT_A + BH.VISIT_B,
              _b5.build_timeline(), _b6.build_timeline()):
    _stay_days |= {s.t_in.date() for s in _segs}


def _holiday_matters(d):
    """그 날이 공휴일이라면 열리는 창이 하나라도 달라지나 (토요일은 대개 안 달라진다)."""
    _ws = [w for ws in V.WALKERHILL_VENUE_WINDOWS.values() for w in ws]
    before = [w.opens_on(d) for w in _ws]
    saved = V.PUBLIC_HOLIDAYS.get(d.year)
    V.PUBLIC_HOLIDAYS[d.year] = (saved or frozenset()) | {d}
    try:
        return [w.opens_on(d) for w in _ws] != before
    finally:
        if saved is None:
            V.PUBLIC_HOLIDAYS.pop(d.year)
        else:
            V.PUBLIC_HOLIDAYS[d.year] = saved


_unknown = sorted(d for d in _stay_days if d.year not in V.PUBLIC_HOLIDAYS)
_new = [d for d in _unknown if d not in _CHECKED_1005 and _holiday_matters(d)]
chk(f"달력 없는 해의 후기 날짜 {len(_unknown)}일 — 확인 안 된 날 {len(_new)}"
    + (f" {[str(d) for d in _new]}" if _new else " (10/5 월력요항 대조)"), len(_new) == 0, True)

print("\n[상품표 · 10/6] △ 줄 — 10월 매출에 걸리나 (생성기 menu.py 가 고르는 길)")
# 경수 10/6 부탁 — △ 24줄을 10월 매출에 걸리는 줄 / 안 걸리는 줄로 (docs/상품표.md '△ 24줄 — 10월 매출에 걸리는 줄 / 안 걸리는 줄').
# 걸린다 = 10월에 하루라도 팔고 (판매 기간 · 요일) 생성기가 고를 수 있다 — 객실 업장이거나 행동 키 (KEY_VENUE) 의
# 업장 · 이름 필터를 지나고, 그 행동이 에이전트 행동 목록 (agent_v4.catalog) 에 있고, 가격표 L3 에 있고 값이 0원이 아니며
# (revenue.py 는 L3 에 없는 행동은 건너뛰고, 0원이면 상품표를 안 본다 — pool · forest · skyard · valet), 단위가 SKIP_WORDS ·
# 이름이 SKIP_PRODUCTS 가 아니다 (어린이 줄은 어른 줄에 붙어 나간다). 에이전트가 실제로 고르는지는 확률이라 10월 실행으로 봤다.
# 나뉨은 menu.py · prices.py · agent_v4.py 를 따른다 — 이것들이나 상품표가 바뀌어 달라지면 여기서 걸린다 → 문서 표를 같이 고친다.
import prices as _pr6
import agent_v4 as _ag6
from agent_v0 import Persona as _P6
# 생성기 (generate.py) 가 만드는 손님으로 — 행동 목록은 건물 · 투숙 · 클럽 자격 · 도착 수단에 따라 다른데, 생성기는 도착 수단을
# 안 정한다 (arrival 없음). 그래서 발렛 · 주차 행동은 생성기에서 안 나온다.
_act6 = {_a.key for _prop in ("GRAND", "VISTA", "DOUGLAS") for _g in (True, False) for _club in (True, False)
         for _a in _ag6.catalog(_P6(name="", traits={}, property=_prop, is_guest=_g, club_access=_club))}
_mm6 = _mn.Menu()
_oct6 = [date(2026, 10, 1) + timedelta(_i) for _i in range(31)]
_path6 = lambda r: not (any(w in r["단위"] for w in _mn.SKIP_WORDS) or r["상품"] in _mn.SKIP_PRODUCTS) \
    and ((r["업장"] in _mn.ROOM_VENUE.values() and "room" in _act6)
         or any(v == r["업장"] and (f is None or f(r)) and k in _act6 and k in _pr6.L3 and _pr6.price_of(k)["krw"] > 0
                for k, (v, f) in _mn.KEY_VENUE.items()))
_tri6 = [r for r in _mm6.rows if r["등급"] == "△"]
_hit6 = {(r["업장"], r["상품"]) for r in _tri6 if _path6(r) and any(_mm6.on_sale(r, d) for d in _oct6)}
_off6 = {(r["업장"], r["상품"]) for r in _tri6 if not _path6(r)}
_rest6 = [r for r in _tri6 if (r["업장"], r["상품"]) not in _hit6 | _off6]
_HIT6 = {("그랜드", "[특가] Early Bird Sale"), ("비스타", "[특가] EARLY BIRD SALE"), ("르파사쥬", "고메 상품 구매 바스켓"),
         ("럭스바", "하이볼"), ("웰니스 사우나", "비스타 쪽 사우나 이용권")}
_OFF6 = {("그랜드", "클럽 스위트 1인 추가 · 클럽라운지"), ("그랜드", "클럽 스위트 1인 추가 · 조식"), ("IRD", "클럽 샌드위치"),
         ("IRD", "브리오슈 치즈버거"), ("더뷔페", "더글라스 투숙객 조식 추가"), ("수영장", "그랜드 실내 수영장 · 초과 인원"),
         ("주차", "주차 · 빛의 시어터 티켓 소지")}
_d6 = lambda got, want: (f" — 더 있음 {sorted(got - want)}" if got - want else "") + (f" — 빠짐 {sorted(want - got)}" if want - got else "")
chk(f"△ {len(_tri6)}줄 중 10월에 걸리는 줄 {len(_hit6)}개 — Early Bird 2 · 르파사쥬 바스켓 · 럭스바 하이볼 · 비스타 쪽 사우나"
    f"{_d6(_hit6, _HIT6)}", _hit6 == _HIT6, True)
chk(f"생성기가 어느 날에도 안 고르는 줄 {len(_off6)}개 — 클럽 1인 추가 2 · IRD 2 · 더글라스 투숙객 조식 · 수영장 초과 · 주차"
    f"{_d6(_off6, _OFF6)}", _off6 == _OFF6, True)
_bad6 = [r["상품"] for r in _rest6 if not (r["업장"] == "더뷔페" and r["상품"].endswith("1~9월") and r["판매종료"] == "2026-09-30")]
chk(f"나머지 {len(_rest6)}줄은 더뷔페 1~9월 — 판매종료 9/30 이라 10월엔 안 판다{' — ' + str(_bad6) if _bad6 else ''}",
    not _bad6 and len(_rest6) == 12, True)

print("\n[I6 상태] 체크인 전 대기와 배타 상태의 경계")
# 체크인 전 구내 체류는 **상태 이름으로** 구분한다 (§9.2). M2 의 대기 상태는
# 배타 상태가 아니라 I6 이 안 걸리고, 업장 세션 상태는 걸린다.
# I6 의 시간 경계 자체는 회사 원본 그대로 두어야 한다 — 경계를 넓히면
# 체크아웃 뒤 한참 지난 식사까지 통과한다.
# M2 StayMachine 이 이미 가지고 있는 체크인 전 대기 상태 (§9.2).
# 검증기 쪽에는 두지 않는다 — 검증기가 쓰지 않는 상수이고, 이건 '회사 설계가
# 이미 이 구분을 하고 있다' 를 확인하는 **테스트의 전제**이기 때문이다.
_PRE_STAY = frozenset({"EARLY_ARRIVAL_ROOM_NOT_READY", "LUGGAGE_STORED",
                       "LOUNGE_WAITING"})
chk("체크인 전 대기 상태가 배타 상태가 아니다 (그래서 I6 이 안 걸린다)",
    not (_PRE_STAY & V.PHYSICALLY_EXCLUSIVE_STATES), True)
chk("IN_LOUNGE 는 배타 상태다 (체크인 전에 쓰면 안 된다)",
    "IN_LOUNGE" in V.PHYSICALLY_EXCLUSIVE_STATES, True)
# 변환이 실제로 대기 상태를 쓰는지 — 체크인 전 구간에 업장 세션이 있으면 안 된다.
_pre = [s for segs in (BI.STAY_A, BI.STAY_B) for s in segs
        if s.state in V.PHYSICALLY_EXCLUSIVE_STATES and s.state != "AT_FRONT_DESK"
        and s.t_in < V.stay_day_bounds(segs[0].t_in)[0]]
chk("체크인 전 구간에 배타 상태를 쓰지 않았다", not _pre, True)
if _pre:
    print(f"       {[(s.state, f'{s.t_in:%H:%M}') for s in _pre]}")

print("\n[I6 회귀] 회사 원본 경계가 그대로 도는가")
D1 = "2022-08-04"


def stay(state, loc, a, b, day=D1, day_out=None):
    return TimelineSegment(state, loc,
                           datetime.fromisoformat(f"{day}T{a}"),
                           datetime.fromisoformat(f"{day_out or day}T{b}"),
                           machine="M7_Outlet")


def i6(segs, want_i6=None):
    """I6 만 재려는 것이므로 다른 불변식이 섞이지 않게 만든다.

    · 키 발급을 깔아 I5(전제 상태)를 피한다.
    · 키 발급과 입실 사이에 피크 이동시간 8분 이상을 확보해 I2를 피한다.
    · `want_i6` 를 주면 **위반 코드가 정말 I6 인지**까지 본다.
    """
    key = stay("KEY_ISSUED", "VISTA_LOBBY", "15:10", "15:15")
    report = validate_walkerhill_timeline([key, *segs], enforce_stay_day=True)
    codes = [v.invariant for v in report.violations]
    if want_i6 is False and codes and codes != ["I6"]:
        FAILURES.append(f"I6 이 아니라 {codes} 로 걸렸다")
        print(f"       (주의: 위반 코드가 {codes} — I6 이 아니다)")
    return report.ok


anchor = stay("IN_ROOM", "VISTA_ROOM", "15:30", "22:00")
# 올바른 상태(LOUNGE_WAITING)를 쓰면 **회사 원본 경계 그대로** 통과한다.
chk("체크인 30분 전 대기 — LOUNGE_WAITING",
    i6([anchor, stay("LOUNGE_WAITING", "VISTA_LOBBY", "14:30", "15:00")]), True)
chk("체크인 5시간 전 대기 — LOUNGE_WAITING",
    i6([anchor, stay("LOUNGE_WAITING", "VISTA_LOBBY", "10:00", "11:00")]), True)
# ── 아래 둘은 **논점 1(I6 범위)이 확정돼야** 기대가 정해진다 ─────────────────
# 취합은 경수 안(I6 를 객실 점유 상태에만)으로 합쳤고, 내 안(배타 상태 전부)은 회의 안건이다.
# 경수 안에서는 둘 다 통과하고, 내 안에서는 둘 다 잡힌다. 어느 쪽이 맞는지는 팀이 정한다.
# 그때까지 결과를 실패로 세지 않는다 — 세면 진짜 회귀와 섞여 구분이 안 된다.
# 근거와 측정값은 docs/논점_I6_수영장상태.md · timeline/i6_pool_논점_실험.py 에 있다.
#
# 다만 실험 결과 내 안에는 막히는 지점이 있다: 배타 상태 전부에 경계를 걸면
# AT_FRONT_DESK(체크인 행위 자체)가 투숙 기간 밖으로 잡혀 체크인이 성립하지 않는다.
# 그래서 나는 회의에 **경수 안 확정**을 제안했고, 그러면 아래 둘의 기대는 이렇게 바뀐다:
#   · IN_LOUNGE  → 기대를 버린다. 로비 라운지는 비투숙객도 쓴다 (투숙객 전용은 장소로 I5 에서 건다)
#   · 사흘 뒤 저녁 → I6 가 아니라 "한 타임라인 = 한 체류" 범위 검사(I7 후보)로 옮긴다
pending("체크인 전에 IN_LOUNGE 를 쓰면 잡힌다",
        i6([anchor, stay("IN_LOUNGE", "VISTA_LOBBY", "14:30", "15:00")]), False,
        "논점 1 — 경수 안이면 통과가 맞다(로비 라운지는 비투숙객도 쓴다)")
pending("체크인 사흘 뒤 저녁",
        i6([anchor, stay("SEATED", "ONDAL", "18:30", "20:00", day="2022-08-07")]), False,
        "논점 1 — 경수 안이면 I6 가 아니라 별도 범위 규칙(I7 후보)의 몫")
chk("체크아웃 뒤 객실 점유",
    i6([anchor, stay("IN_ROOM", "VISTA_ROOM", "15:30", "22:00", day="2022-08-07")], want_i6=False), False)

print("\n[수정 4] 클럽라운지 세 서비스가 따로 선다")
chk("조식 07:30~09:00", window_only("GRAND_CLUB_LOUNGE", "2025-04-16", "07:30", "09:00", "IN_LOUNGE"), True)
chk("티타임 16:10~17:00", window_only("GRAND_CLUB_LOUNGE", "2025-04-15", "16:10", "17:00", "IN_LOUNGE"), True)
chk("해피아워 17:30~19:30", window_only("GRAND_CLUB_LOUNGE", "2025-04-15", "17:30", "19:30", "IN_LOUNGE"), True)
# 취합에서 슬기가 2025 해피아워 창(18:00~20:00 · years={2025} · 후기 관측)을 넣었다.
# 내 blog04(2025-04 게시 · 3편 글 속 이용시간)와 슬기 blog05(2025-03)가 따로 같은 값을 봤다 — 해마다 바뀐다 (Q17).
# 그래서 "공식 창을 넘으니 FAIL" 이던 내 기대는 **연도를 안 보던 때의 기대**다. 연도로 가른다.
chk("후기값 18:00~20:00 은 2025 엔 열린다 (슬기 REVIEW 창)",
    window_only("GRAND_CLUB_LOUNGE", "2025-04-15", "18:00", "20:00", "IN_LOUNGE"), True)
chk("같은 18:00~20:00 이 2026 엔 안 열린다 (공식 17:30~19:30)",
    window_only("GRAND_CLUB_LOUNGE", "2026-04-15", "18:00", "20:00", "IN_LOUNGE"), False)
chk("11:00~12:00 창 사이", window_only("GRAND_CLUB_LOUNGE", "2025-04-15", "11:00", "12:00", "IN_LOUNGE"), False)

print("\n[수정 5] 르파사쥬 매장 영업시간")
chk("19:20~19:55 TOGO 픽업 (회사 19:30 이면 반려됐다)",
    window_only("LE_PASSAGE", "2022-08-04", "19:20", "19:55", "TAKEOUT_ORDERED"), True)
chk("09:30 이용 (회사 11:00 이면 반려됐다)",
    window_only("LE_PASSAGE", "2022-08-04", "09:30", "10:00", "TAKEOUT_ORDERED"), True)
chk("21:30 마감 후", window_only("LE_PASSAGE", "2022-08-04", "21:30", "22:00", "TAKEOUT_ORDERED"), False)

print("\n[수정 6] 부대시설 창 — 없던 시절엔 전부 통과했다")
for v, st in [("SKYARD", "ADMITTED"), ("VISTA_POOL", "CHECKED_IN"),
              ("GRAND_POOL", "CHECKED_IN")]:
    chk(f"{v} 새벽 3시", window_only(v, "2023-08-05", "03:00", "03:40", st), False)
chk("SKYARD 21:00~21:40 (22시 마감 안)", window_only("SKYARD", "2023-08-05", "21:00", "21:40", "ADMITTED"), True)
chk("VISTA_POOL 17:00~18:30 (후기의 그 시간)", window_only("VISTA_POOL", "2022-08-04", "17:00", "18:30", "ENTERED"), True)

print("\n[수정 7-a] 기간 — 리버파크 2부제는 골드시즌에만")
chk("골드 8/05 14:30~15:00 청소시간", window_only("RIVERPARK", "2023-08-05", "14:30", "15:00", "ENTERED"), False)
chk("레이트블루 8/22 14:30~15:00", window_only("RIVERPARK", "2023-08-22", "14:30", "15:00", "ENTERED"), True)
chk("얼리블루 7/10 14:30~15:00", window_only("RIVERPARK", "2023-07-10", "14:30", "15:00", "ENTERED"), True)
chk("비시즌 10/05 정오 — 창이 하나도 안 열린다", window_only("RIVERPARK", "2023-10-05", "12:00", "13:00", "ENTERED"), False)

print("\n[수정 7-b] 퇴장 유예는 **나가는 상태에만** 붙는다")
# 유예를 상태 구분 없이 주면 이용 시간까지 늘어난다. 리버파크 1부를 14:50 까지
# 이용한 하루가 통과하는데, 그건 다음 타임 손님과 겹치는 하루다.
chk("이용 ENTERED 10:00~14:30 (마감까지)",
    window_only("RIVERPARK", "2023-08-05", "10:00", "14:30", "ENTERED"), True)
chk("이용 ENTERED 10:00~14:50 (유예를 이용에 씀)",
    window_only("RIVERPARK", "2023-08-05", "10:00", "14:50", "ENTERED"), False)
chk("퇴장 EXITED 14:30~14:50 (후기의 그 장면)",
    window_only("RIVERPARK", "2023-08-05", "14:30", "14:50", "EXITED"), True)
chk("퇴장 EXITED 14:30~15:00 (유예 초과)",
    window_only("RIVERPARK", "2023-08-05", "14:30", "15:00", "EXITED"), False)
chk("14:40 신규 입장 (입장엔 유예 없음)",
    window_only("RIVERPARK", "2023-08-05", "14:40", "14:50", "ENTERED"), False)

# **유예를 상태로만 가르면 구멍이 한 칸 옆으로 옮겨간다.**
# ENTERED 10:00~14:50 을 막아 놔도, 같은 구간을 EXITED 로 **이름만 바꾸면**
# 그대로 통과했다. 퇴장이 마감 이전까지 유예보다 길게 걸쳐 있으면 그건 이용이다.
chk("  EXITED 10:00~14:50 (구간 전체를 퇴장이라 부름)",
    window_only("RIVERPARK", "2023-08-05", "10:00", "14:50", "EXITED"), False)
chk("  EXITED 14:10~14:50 (마감 20분 전부터 나오기 — 유예와 같음)",
    window_only("RIVERPARK", "2023-08-05", "14:10", "14:50", "EXITED"), True)
chk("  EXITED 14:09~14:50 (유예보다 길게 점유)",
    window_only("RIVERPARK", "2023-08-05", "14:09", "14:50", "EXITED"), False)

# 반대쪽 — **맞는 퇴장을 틀렸다고 하면 안 된다.**
# L.O.(없으면 마감 시각)가 퇴장까지 막아서, 마감에 **정확히** 시작하는 퇴장만
# 통과했다. 14:35 에 샤워실로 나가는 후기 장면이 I3 로 떨어졌다.
# L.O. 는 주문·이용 마감이지 퇴장 마감이 아니다.
for _t in ("14:31", "14:35", "14:45"):
    chk(f"  EXITED {_t}~14:50 (마감 뒤 시작하는 퇴장)",
        window_only("RIVERPARK", "2023-08-05", _t, "14:50", "EXITED"), True)
chk("  EXITED 14:52~14:55 (유예 밖에서 시작)",
    window_only("RIVERPARK", "2023-08-05", "14:52", "14:55", "EXITED"), False)

# 퇴장이 L.O. 검사를 넘는 건 **L.O. 가 선언되지 않은 창에서만**이다.
# 상태만 보고 풀면 L.O. 가 실제로 있는 식음업장까지 뚫린다 — 거기선 `EXITED`
# 가 올 자리가 아니라(§3.2 식음 어휘), 이름을 잘못 붙여야만 닿는 통과 경로다.
chk("  리버파크 EXITED 14:35 (L.O. 미선언 — 마감 시각이 대체값일 뿐)",
    window_only("RIVERPARK", "2023-08-05", "14:35", "14:50", "EXITED"), True)
# (운영 시간 **안**이면서 L.O. 는 지난 시각을 고른다 — 창 밖이라 떨어지면 의미가 없다)
for _v, _a, _b in (("PIZZA_HILL", "21:15", "21:30"),     # 11:30~22:00 L.O. 21:00 (10/11 · 전엔 11:00~23:00 이라 22:00)
                   ("THE_PAVILION", "20:30", "20:45"),   # 09:00~21:00 L.O. 20:00
                   ("ONDAL", "14:40", "14:55")):         # 12:00~15:00 L.O. 14:30
    chk(f"  {_v} EXITED {_a} (L.O. 가 선언된 업장 — 뚫리면 안 된다)",
        window_only(_v, "2023-08-05", _a, _b, "EXITED"), False)



print("\n[수정 7-d] 시즌 시간표는 **근거가 있는 연도에만** 적용된다")
# `season` 은 월·일만 비교하므로 묶지 않으면 2023년 요금표가 다른 해에도 적용된다.
chk("2023-08-05 골드 1부 (근거가 있는 해)",
    window_only("RIVERPARK", "2023-08-05", "10:00", "14:30", "ENTERED"), True)
# 10/5 — 2026 창 (공식 리버파크 페이지) 이 생겨서 2026-08-05 는 이제 열린다. 연도 검사는 시간표가 없는 해 (2025) 로 본다.
chk("2025-08-05 같은 시각 (그 해 시간표를 모른다)",
    window_only("RIVERPARK", "2025-08-05", "10:00", "14:30", "ENTERED"), False)
chk("2026-08-05(수) 같은 시각 — 2026 은 공식 골드 월~목 10:00~20:00 (아래 [10/5])",
    window_only("RIVERPARK", "2026-08-05", "10:00", "14:30", "ENTERED"), True)
chk("2019-08-05 같은 시각",
    window_only("RIVERPARK", "2019-08-05", "10:00", "14:30", "ENTERED"), False)


def why(venue, day, a, b, state="SEATED"):
    """창 검사가 낸 이유 문장 (통과면 빈 문자열). 어느 갈래로 떨어졌는지 본다."""
    seg = TimelineSegment(state, venue, datetime.fromisoformat(f"{day}T{a}"),
                          datetime.fromisoformat(f"{day}T{b}"), machine="M7_Outlet", venue=venue)
    return V._fits_any_window(seg)[1]


print("\n[10/5 · 요일 창] 더뷔페 평일 · 공휴일 · 기간 한정 회차 (공식표 · 공지)")
_B = "THE_BUFFET"
_S = "TIME_LIMIT_ACTIVE"     # 에이전트 v4 의 더뷔페 상태
# 평일 창이 생겼다 — 10/5 전까지는 주말 슬롯뿐이라 반려됐다
chk("수 10/07 중식 12:00~13:30 (월~금 12:00~14:30)", window_only(_B, "2026-10-07", "12:00", "13:30", _S), True)
chk("화 10/06 조식 08:00~09:00 (화~금 07:00~10:00 — 2부제 아님)", window_only(_B, "2026-10-06", "08:00", "09:00", _S), True)
chk("일 10/11 석식 18:00~20:00 (월~금 · 일 18:00~21:00)", window_only(_B, "2026-10-11", "18:00", "20:00", _S), True)
# 2부제 날의 슬롯 사이는 여전히 막힌다 — 요일 없이 평일 창을 더했으면 여기가 뚫렸다
chk("토 10/10 중식 13:00~13:30 (1부 · 2부 사이)", window_only(_B, "2026-10-10", "13:00", "13:30", _S), False)
chk("월 10/12 조식 08:00~09:00 (토~월 2부제 — 1부 08:10 끝 · 2부 08:30 시작)",
    window_only(_B, "2026-10-12", "08:00", "09:00", _S), False)
chk("일 10/11 석식 17:30~19:00 (일요일은 2부제 아님 — 18:00 시작)", window_only(_B, "2026-10-11", "17:30", "19:00", _S), False)
chk("수 10/07 중식 11:00~12:30 (주말 1부 시각 — 평일엔 없다)", window_only(_B, "2026-10-07", "11:00", "12:30", _S), False)
# 공휴일 — '+' 는 요일과 상관없이 열고 '-' 는 닫는다 (상품표와 같은 뜻)
chk("금 7/17 제헌절 중식 11:00~12:30 (공휴일 1부)", window_only(_B, "2026-07-17", "11:00", "12:30", _S), True)
chk("금 7/17 제헌절 중식 12:00~14:00 (평일 창은 공휴일에 닫힌다)", window_only(_B, "2026-07-17", "12:00", "14:00", _S), False)
chk("월 10/05 대체공휴일 석식 17:30~19:00 (토 · 공휴일 1부)", window_only(_B, "2026-10-05", "17:30", "19:00", _S), True)
chk("월 10/05 대체공휴일 석식 18:00~20:00 (평일 석식 창은 공휴일에 닫힌다)",
    window_only(_B, "2026-10-05", "18:00", "20:00", _S), False)
chk("목 2025-12-25 석식 17:30~19:00 (2025 달력 — 공휴일 1부)", window_only(_B, "2025-12-25", "17:30", "19:00", _S), True)
chk("목 2025-12-25 석식 18:00~20:00", window_only(_B, "2025-12-25", "18:00", "20:00", _S), False)
chk("수 2025-10-08 추석 대체공휴일 중식 11:00~12:30", window_only(_B, "2025-10-08", "11:00", "12:30", _S), True)
chk("수 2024-10-09 한글날 중식 12:00~13:30 (달력 없는 해는 요일로만 — 주석)",
    window_only(_B, "2024-10-09", "12:00", "13:30", _S), True)
# 기간 한정 공지 — 2026 여름 조식 매일 2부제 · 2026 12월 석식 매일 2부
chk("화 2026-08-04 조식 08:00~08:40 (여름 2부제 — 평일 창이 닫힌다)", window_only(_B, "2026-08-04", "08:00", "08:40", _S), False)
chk("화 2026-08-04 조식 06:30~08:00 (여름 1부)", window_only(_B, "2026-08-04", "06:30", "08:00", _S), True)
chk("월 2026-08-31 조식 08:30~10:00 (공지 마지막 날)", window_only(_B, "2026-08-31", "08:30", "10:00", _S), True)
chk("화 2026-09-01 조식 08:00~09:00 (공지 끝 — 평일 창으로 돌아온다)", window_only(_B, "2026-09-01", "08:00", "09:00", _S), True)
chk("화 2025-08-05 조식 08:00~09:00 (여름 2부제는 2026 공지뿐)", window_only(_B, "2025-08-05", "08:00", "09:00", _S), True)
chk("수 2026-12-02 석식 18:00~20:00 (12월은 매일 2부 — 평일 창이 닫힌다)", window_only(_B, "2026-12-02", "18:00", "20:00", _S), False)
chk("수 2026-12-02 석식 17:30~19:00 (12월 1부)", window_only(_B, "2026-12-02", "17:30", "19:00", _S), True)
chk("화 2026-12-01 석식 20:00~21:30 (12월 첫날 2부)", window_only(_B, "2026-12-01", "20:00", "21:30", _S), True)
chk("화 2026-11-30 석식 18:00~20:00 (11월 — 평일 창)", window_only(_B, "2026-11-30", "18:00", "20:00", _S), True)
chk("목 2026-12-31 석식 18:00~20:00 (12월 마지막 날)", window_only(_B, "2026-12-31", "18:00", "20:00", _S), False)
chk("수 2025-12-03 석식 18:00~20:00 (12월 매일 2부는 해마다 — 공식 사본 2023 · 2024 · 2026)", window_only(_B, "2025-12-03", "18:00", "20:00", _S), False)
chk("수 2025-12-03 석식 17:30~19:00 (해마다 12월 1부)", window_only(_B, "2025-12-03", "17:30", "19:00", _S), True)
chk("월 2025-11-24 석식 18:00~20:00 (11월은 평일 창)", window_only(_B, "2025-11-24", "18:00", "20:00", _S), True)
# 그 날 열리는 회차 수만 센다
_m = why(_B, "2026-10-10", "13:00", "13:30", _S)
chk(f"토요일 실패 메시지는 그 날 회차 6개 ('{_m[-22:]}')", "운영 슬롯 6개" in _m, True)
_m = why(_B, "2026-10-06", "10:30", "11:00", _S)
chk(f"화요일은 회차 3개 ('{_m[-22:]}')", "운영 슬롯 3개" in _m, True)

print("\n[10/5 · 요일 창] 리버파크 2026 — 공식 리버파크 페이지 (블루 매일 · 골드 월~목 통운영 · 금~일 1부 · 2부)")
_R = "RIVERPARK"
chk("토 2026-07-18 1부 10:00~17:00", window_only(_R, "2026-07-18", "10:00", "17:00", "ENTERED"), True)
chk("토 2026-07-18 2부 15:00~21:30", window_only(_R, "2026-07-18", "15:00", "21:30", "ENTERED"), True)
chk("토 2026-07-18 10:00~19:00 (1부 18:00 마감을 넘김 — 1부 · 2부는 서로 다른 입장)",
    window_only(_R, "2026-07-18", "10:00", "19:00", "ENTERED"), False)
chk("금 2026-07-17 골드 첫날 10:00~13:00", window_only(_R, "2026-07-17", "10:00", "13:00", "ENTERED"), True)
chk("일 2026-08-30 골드 마지막 날 15:00~18:00", window_only(_R, "2026-08-30", "15:00", "18:00", "ENTERED"), True)
chk("월 2026-07-20 골드 월~목 10:00~20:00 (통운영)", window_only(_R, "2026-07-20", "10:00", "20:00", "ENTERED"), True)
chk("월 2026-07-20 15:00~21:00 (월~목은 20:00 마감 · 2부 없음)", window_only(_R, "2026-07-20", "15:00", "21:00", "ENTERED"), False)
chk("목 2026-07-23 10:00~19:00 (월~목은 1부 · 2부로 안 나뉜다)", window_only(_R, "2026-07-23", "10:00", "19:00", "ENTERED"), True)
chk("월 2026-08-17 광복절 대체공휴일 10:00~20:00 (공휴일 표기 없음 — 요일대로 월~목 창)",
    window_only(_R, "2026-08-17", "10:00", "20:00", "ENTERED"), True)
chk("토 2026-07-11 블루 10:00~20:00 (블루는 매일 통운영)", window_only(_R, "2026-07-11", "10:00", "20:00", "ENTERED"), True)
chk("금 2026-06-26 블루 첫날 10:00~13:00", window_only(_R, "2026-06-26", "10:00", "13:00", "ENTERED"), True)
chk("목 2026-06-25 10:00~13:00 (블루 전날)", window_only(_R, "2026-06-25", "10:00", "13:00", "ENTERED"), False)
chk("금 2026-07-17 10:00~20:00 (골드 첫날은 금요일 — 2부제라 통운영 아님)",
    window_only(_R, "2026-07-17", "10:00", "20:00", "ENTERED"), False)
chk("월 2026-08-31 10:00~13:00 (8/30 뒤 운영은 페이지에 없다)", window_only(_R, "2026-08-31", "10:00", "13:00", "ENTERED"), False)
# 실패 이유가 갈래마다 다르게 나오는가 — 기간 · 연도 (요일 갈래는 아래 시험용 창으로 본다)
_m = why(_R, "2026-09-04", "10:00", "13:00", "ENTERED")
chk(f"9/4 → '기간' 갈래 ({_m[:30]}…)", _m.startswith("해당 기간에 운영하지 않음"), True)
_m = why(_R, "2025-08-02", "10:00", "13:00", "ENTERED")
chk(f"2025 → '연도' 갈래 ({_m[:30]}…)", _m.startswith("이 연도의 운영 시간을 모름") and "2026" in _m, True)
chk("2023 시간표는 그대로 (골드 8/05 1부 10:00~14:30)", window_only(_R, "2023-08-05", "10:00", "14:30", "ENTERED"), True)
chk("2023 창이 2026 에 새지 않는다 (토 2026-08-22 10:00~19:00 — 2023 레이트 블루 통운영이면 통과했을 구간)",
    window_only(_R, "2026-08-22", "10:00", "19:00", "ENTERED"), False)
# 요일 갈래 — 기간 · 연도는 맞는데 그 요일에 여는 창이 없을 때. 실제 업장엔 지금 그런 곳이 없어 시험용 창으로 본다.
_probe = "ZZ_WEEKEND_ONLY"
V.WALKERHILL_VENUE_WINDOWS[_probe] = (V.VenueWindow(V.time(10, 0), V.time(18, 0), weekdays=frozenset({4, 5, 6})),)
try:
    _m = why(_probe, "2026-07-20", "10:00", "13:00", "ENTERED")
    chk(f"  금~일만 여는 창 · 월요일 → '요일' 갈래 + 금토일 표기 ({_m[:40]}…)",
        "이 요일에 열리는 창 없음" in _m and "금토일" in _m, True)
finally:
    V.WALKERHILL_VENUE_WINDOWS.pop(_probe)

print("\n[10/5 · 요일 창] 칸 오타는 조용히 지나가지 않는다")
for _bad, _kw in (("holidays='x'", dict(holidays="x")), ("weekdays={7}", dict(weekdays=frozenset({7}))),
                  ("weekdays=빈 집합", dict(weekdays=frozenset())),
                  ("closed 거꾸로", dict(closed=((date(2026, 8, 31), date(2026, 7, 17)),)))):
    try:
        V.VenueWindow(V.time(9, 0), V.time(10, 0), **_kw)
        chk(f"  {_bad} → 막힘", False, True)
    except ValueError:
        chk(f"  {_bad} → 막힘", True, True)

print("\n[10/5 · 요일 창] 검증기 창 = 상품표 더뷔페 줄 (2026 하루하루 · 끼니마다 회차 대조)")
# 두 표는 따로 손으로 적었다. 요일 · 공휴일 문법을 옮기다 틀리면 에이전트는 가는데 상품표는
# 그 회차를 안 팔거나, 그 반대가 된다. 2026 년 365일 × 조식 · 중식 · 석식의 회차 집합을 맞춘다.
# 알려진 차이 하나 — 상품표에는 2026 여름 조식 2부제 공지 (7/17~8/31) 가 없다 (docs/상품표.md ·
# 현장 질문 14번). 그 기간 화~금 조식만 다르고, 값은 같은 85,000 이라 매출은 안 바뀐다.
_menu_obj = _mn.Menu()
_meal_of = lambda t: "조식" if t < V.time(11, 0) else ("중식" if t < V.time(16, 0) else "석식")
_diff, _known = [], []
for _i in range(365):
    _day = date(2026, 1, 1) + timedelta(_i)
    for _meal in ("조식", "중식", "석식"):
        _rows = [r for r in _menu_obj.by_venue.get("더뷔페", []) if r["상품"].startswith(_meal + " · 성인")
                 and _menu_obj.on_sale(r, _day)]
        _ms = {(f"{a // 60:02d}:{a % 60:02d}", f"{b // 60:02d}:{b % 60:02d}") for r in _rows for a, b in r["_times"]}
        _vs = {(f"{w.open_at:%H:%M}", f"{w.close_at:%H:%M}") for w in V.WALKERHILL_VENUE_WINDOWS["THE_BUFFET"]
               if w.opens_on(_day) and _meal_of(w.open_at) == _meal}
        if _ms != _vs:
            _summer = _meal == "조식" and date(2026, 7, 17) <= _day <= date(2026, 8, 31) and _day.weekday() in (1, 2, 3, 4)
            (_known if _summer else _diff).append((_day, _meal, sorted(_ms), sorted(_vs)))
chk(f"  회차가 다른 날 {len(_diff)} (여름 2부제 화~금 조식 {len(_known)}일은 알려진 차이)"
    + (f" — 처음 {_diff[0]}" if _diff else ""), len(_diff) == 0, True)
# 리버파크도 같은 방법으로 — 상품표 리버파크 줄 (시각이 있는 블루 · 골드 월~목 · 1부 · 2부) 과 2026 년 하루하루 회차가 같아야 한다.
# 창만 열고 상품표가 안 팔면 에이전트는 가는데 매출이 '가격표 값' 으로 새고, 반대면 0 이 된다.
_rp_diff = []
for _i in range(365):
    _day = date(2026, 1, 1) + timedelta(_i)
    _ms = {(f"{a // 60:02d}:{a % 60:02d}", f"{b // 60:02d}:{b % 60:02d}")
           for r in _menu_obj.by_venue.get("리버파크", []) if r["_times"] and _menu_obj.on_sale(r, _day)
           for a, b in r["_times"]}
    _vs = {(f"{w.open_at:%H:%M}", f"{w.close_at:%H:%M}") for w in V.WALKERHILL_VENUE_WINDOWS["RIVERPARK"] if w.opens_on(_day)}
    if _ms != _vs:
        _rp_diff.append((_day, sorted(_ms), sorted(_vs)))
_rp_days = sum(1 for _i in range(365) if any(w.opens_on(date(2026, 1, 1) + timedelta(_i)) for w in V.WALKERHILL_VENUE_WINDOWS["RIVERPARK"]))
chk(f"  리버파크 2026 — 회차가 다른 날 {len(_rp_diff)} (창이 여는 날 {_rp_days}일)"
    + (f" — 처음 {_rp_diff[0]}" if _rp_diff else ""), len(_rp_diff) == 0 and _rp_days > 0, True)
# 생성기가 실제로 고르는 길로도 본다 — menu.Menu.candidates (행동 키의 상품 필터까지 거친다).
# 10/5 에 리버파크 블루 · 월~목 줄을 넣었는데 'river' 키 필터가 '1부 · 2부' 이름만 골라 가격표 값으로 떨어졌다.
# 회차 집합 대조만으로는 못 잡는 구멍이라, 검증기 창이 여는 날 · 회차마다 그 시각에 팔 줄이 있는지 본다.
from types import SimpleNamespace as _NS
_guest = _NS(party_size=2, has_child_under_13=False, is_guest=True, nights=1, name="selfcheck", package=None)
_buffet_key = lambda t: "buffet_b" if t < V.time(11, 0) else ("buffet_l" if t < V.time(16, 0) else "buffet_d")
_no_row = []
for _i in range(365):
    _day = date(2026, 1, 1) + timedelta(_i)
    for _venue, _keyf in (("THE_BUFFET", _buffet_key), ("RIVERPARK", lambda t: "river")):
        for w in V.WALKERHILL_VENUE_WINDOWS[_venue]:
            if not w.opens_on(_day):
                continue
            _at = datetime.combine(_day, w.open_at)
            _rows_c, _exact = _menu_obj.candidates(_keyf(w.open_at), _guest, _at)
            _summer = (_venue == "THE_BUFFET" and w.open_at == V.time(6, 30)
                       and date(2026, 7, 17) <= _day <= date(2026, 8, 31) and _day.weekday() in (1, 2, 3, 4))
            if not _rows_c or not (_exact or _summer):
                _no_row.append((str(_day), _venue, f"{w.open_at:%H:%M}", len(_rows_c), _exact))
chk(f"  검증기 창이 여는 날 · 회차마다 상품표에 그 시각 팔 줄이 있다 (생성기 고르는 길 · 더뷔페 · 리버파크)"
    + (f" — 없음 {len(_no_row)} · 처음 {_no_row[0]}" if _no_row else ""), len(_no_row) == 0, True)
_tf = sum(1 for _i in range(46) if (date(2026, 7, 17) + timedelta(_i)).weekday() in (1, 2, 3, 4))
chk(f"  알려진 차이는 7/17~8/31 의 화~금 {_tf}일에서 공휴일 7/17(금) 을 뺀 {_tf - 1}일뿐", len(_known) == _tf - 1, True)

print("\n[10/7 · 포레스트 파크 창] 검증기 창 = 가정표 FOREST_PARK '운영' · '입장 제한일 · 2026' (경수 부탁 — 와인페어 시나리오)")
# 전엔 검증기에 창이 없어 에이전트가 임시값 (11:00~20:00) 으로 다녔고, generate.py --close FOREST_PARK=… 도 못 썼다.
# 공식 체험/활동 페이지 "11:00 ~ 20:00 7/1~9/27 기간에는 21:00까지" · 공지 3757 [이용 제한일] — 둘 다 가정표에 있다.
_fpg = {g["항목"]: g for g in V.load_place_assumptions("FOREST_PARK")}
_fpw = V.WALKERHILL_VENUE_WINDOWS["FOREST_PARK"]
_fph = sorted((f"{w.open_at:%H:%M}-{w.close_at:%H:%M}", w.season) for w in _fpw)
chk("운영 = 가정표 '운영' 11:00-20:00 · 조건 '7/1~9/27 은 21:00 까지'",
    _fpg["운영"]["값"] == "11:00-20:00" and _fpg["운영"]["조건"] == "7/1~9/27 은 21:00 까지"
    and _fph == [("11:00-20:00", (9, 28, 6, 30)), ("11:00-21:00", (7, 1, 9, 27))], True)
_fp_ga = {date(2026, int(_m), int(_d)) for _m, _d in (_x.split("-") for _x in _fpg["입장 제한일 · 2026"]["값"].split(","))}
_fp_v = {_a + timedelta(_i) for w in _fpw for _a, _b in w.closed for _i in range((_b - _a).days + 1)}
chk(f"닫는 날 {len(_fp_v)}일 = 가정표 '입장 제한일 · 2026' {len(_fp_ga)}일 (10/10~11 · 17~18 · 24~25 · 31)", _fp_v == _fp_ga, True)
# 2026 하루하루 — 제한일만 창이 0개, 나머지 날은 정확히 1개 (연장 기간 경계 6/30 · 7/1 · 9/27 · 9/28 에 빈 날 · 겹친 날이 없다)
_fp_bad = [str(_d) for _d in (date(2026, 1, 1) + timedelta(_i) for _i in range(365))
           if sum(w.opens_on(_d) for w in _fpw) != (0 if _d in _fp_ga else 1)]
chk(f"2026 하루하루 — 제한일만 닫히고 나머지 날은 창이 하나{' — ' + str(_fp_bad[:5]) if _fp_bad else ''}", not _fp_bad, True)
# 에이전트 v4 의 포레스트 파크 행동이 이 창을 본다 (임시값이 아니라) — 그 날 그 시각에 시작할 수 있나
_fpa = [_a for _a in _ag6.catalog(_P6(name="", traits={}, property="GRAND", is_guest=True)) if _a.key == "forest"][0]
_fp_same_day = lambda _dt: (_s := _ag6.earliest_start(_fpa, _dt)) is not None and _s.date() == _dt.date()
chk("에이전트 v4 포레스트 파크 — 10/10 · 10/31 은 못 가고, 10/9 · 11/1 11:00 은 가고, 7/18 19:30 은 가고 (21:00 까지) 10/9 19:00 은 못 간다 (20:00 마감)",
    [_fp_same_day(datetime(2026, _m, _d, _h, _mi)) for _m, _d, _h, _mi in
     ((10, 10, 11, 0), (10, 31, 11, 0), (10, 9, 11, 0), (11, 1, 11, 0), (7, 18, 19, 30), (10, 9, 19, 0))]
    == [False, False, True, True, True, False] and _fpa.venue == "FOREST_PARK" and "FOREST_PARK" not in _ag6.TEMP_WINDOWS, True)

print("\n[10/8 · 와인페어] 검증기 창 · 상품표 · 에이전트 · 값 — 가정표 FOREST_PARK '와인페어 …' 줄과 같은가 (경수 부탁 — 와인페어를 모델 안에)")
# 공식 Wine Forest 상세 (8837 · 8838) "① 운영 날짜" · "② 운영 시간" · "⑥ … (추가 요금: 성인 55,000원 | 아동 10,000원 …)" — 다 가정표에 있다.
# 자리는 포레스트 파크 (그 날 일반 이용은 막힘). 입장 대상은 agent_v4.WINE_FAIR_PUBLIC (기본 1 = 외부도 · 10/11).
# 10/11 — 워커힐 보도자료 (9/14) "행사 기간 중 워커힐 투숙객은 무료로 입장이 가능하다" · "네이버와 카카오톡을 통해 사전 구매할 경우
#   10% 할인" 으로 투숙객 0원 · 외부 판매 기본을 켰다 (10/8 엔 공식 홈페이지만 보고 패키지 성인 2인 0원 · 투숙객만).
import random as _rnd8
_wfg = {g["항목"]: g for g in V.load_place_assumptions("FOREST_PARK") if g["항목"].startswith("와인페어")}
_wfw = V.WALKERHILL_VENUE_WINDOWS["WINE_FAIR"]
_wf_days = {date(2026, int(_m), int(_d)) for _m, _d in (_x.split("-") for _x in _wfg["와인페어 운영 날짜 · 2026"]["값"].split(","))}
chk("창 = 가정표 '와인페어 운영 · 1부' 11:00-15:00 · '2부' 15:30-20:00 (공식 출처)",
    sorted(f"{w.open_at:%H:%M}-{w.close_at:%H:%M}" for w in _wfw) == [_wfg["와인페어 운영 · 1부"]["값"], _wfg["와인페어 운영 · 2부"]["값"]]
    == ["11:00-15:00", "15:30-20:00"] and {w.source.name for w in _wfw} == {"OFFICIAL"}, True)
# 2025 · 2026 · 2027 하루하루 — 가정표 여섯 날에만 1부 · 2부 둘 다 열고, 나머지 날 (다른 해 같은 날짜 포함) 은 하나도 안 연다
_wf_bad = [str(_d) for _y in (2025, 2026, 2027) for _d in (date(_y, 1, 1) + timedelta(_i) for _i in range(365))
           if sum(w.opens_on(_d) for w in _wfw) != (2 if _d in _wf_days else 0)]
chk(f"여는 날 = 가정표 '와인페어 운영 날짜 · 2026' {len(_wf_days)}일 (10/10~11 · 17~18 · 24~25) · 다른 해는 안 연다"
    f"{' — ' + str(_wf_bad[:5]) if _wf_bad else ''}", not _wf_bad and len(_wf_days) == 6, True)
chk("와인페어 날은 전부 포레스트 파크 일반 이용이 막힌 날이다 (10/31 은 막혔지만 와인페어 날이 아니다)",
    _wf_days < _fp_ga and _fp_ga - _wf_days == {date(2026, 10, 31)}, True)
_wfm = {r["상품"]: r for r in _menu if r["업장"] == "와인페어"}
_wf_md = lambda r: {date(2026, int(_m), int(_d)) for _m, _d in (_x.strip().split("-") for _x in r["요일제한"][3:].split(","))}
chk("상품표 와인페어 성인 · 아동 — 지정일 · 시간 · 판매 기간 · 단가가 가정표와 같다",
    sorted(_wfm) == ["입장권 · 성인", "입장권 · 아동"]
    and all(_wf_md(r) == _wf_days and r["시간제한"] == "11:00-15:00,15:30-20:00"
            and (r["판매시작"], r["판매종료"]) == ("2026-10-10", "2026-10-25") for r in _wfm.values())
    and (_wfm["입장권 · 성인"]["단가"], _wfm["입장권 · 아동"]["단가"]) == (_wfg["와인페어 입장료 · 성인"]["값"], _wfg["와인페어 입장료 · 아동"]["값"])
    == ("55000", "10000"), True)
# 상품표 근거에 '투숙객 전용 · 한정' 이 들어가면 menu.fits 가 비투숙을 막아 스위치를 켜도 안 팔린다 — 입장 대상은 스위치 하나가 정한다
chk("상품표 와인페어 줄은 '투숙객 전용 · 한정' 으로 안 막는다 (스위치가 정한다)",
    not any(r["_guest_only"] for r in _mm6.by_venue["와인페어"]), True)
_wf_pk = sorted(f"{r['업장']} {r['상품']}" for r in _mm6.rows if r["업장"] in _mn.ROOM_VENUE.values() and "와인페어" in r["포함"])
chk(f"포함 칸에 와인페어가 있는 객실 상품 {len(_wf_pk)}개 — Wine Forest 2 · 캠크닉 5 · 불멍 1",
    _wf_pk == sorted(["그랜드 Wine Forest", "비스타 WINE FOREST", "그랜드 캠크닉 인더 포레스트 TYPE 1", "그랜드 캠크닉 인더 포레스트 TYPE 2",
                      "그랜드 캠크닉 인더 포레스트 TYPE 3", "비스타 [가을] 어텀 캠크닉 TYPE 1", "비스타 [가을] 어텀 캠크닉 TYPE 2",
                      "더글라스 [가을] 체크인 불멍"]), True)
# 에이전트 — 기본 (스위치 1) 은 비투숙도, 스위치 0 이면 투숙객만. 포레스트 파크 출입 표 (비투숙 불가) 를 와인페어엔 안 쓴다
_wf_has = lambda **kw: any(_a.key == "winefair" for _a in _ag6.catalog(_P6(name="", traits={}, **kw)))
_wf_sw = _ag6.WINE_FAIR_PUBLIC
_wf_cat1 = [_wf_has(property=_b, is_guest=True) for _b in ("GRAND", "VISTA", "DOUGLAS")] + [_wf_has(is_guest=False)]
_ag6.WINE_FAIR_PUBLIC = 0
_wf_cat0 = [_wf_has(is_guest=False), _wf_has(is_guest=True)]
_ag6.WINE_FAIR_PUBLIC = _wf_sw
_wf_forest_ng = any(_a.key == "forest" for _a in _ag6.catalog(_P6(name="", traits={}, is_guest=False)))
chk("에이전트 v4 — 기본 (스위치 1) 은 투숙객 세 건물 · 비투숙 다 · 스위치 0 이면 투숙객만 (포레스트 파크 일반 이용은 여전히 비투숙 불가) · 스위치는 정수",
    _wf_sw == 1 and type(_wf_sw) is int and _wf_cat1 == [True, True, True, True] and _wf_cat0 == [False, True] and not _wf_forest_ng, True)
# 가정표 '와인페어 입장 대상' · '입장료 · 투숙객' (보도자료) 가 이 기본값 · 아래 값과 같은 뜻인가
chk("가정표 — 입장 대상 '투숙객 무료 · 외부 유료' · 입장료 투숙객 0 · 사전 구매 할인 10% (워커힐 보도자료 9/14 · ◎)",
    (_wfg["와인페어 입장 대상"]["값"], _wfg["와인페어 입장료 · 투숙객"]["값"], _wfg["와인페어 사전 구매 할인"]["값"]) == ("투숙객 무료 · 외부 유료", "0", "10")
    and all(_wfg[_k]["등급"] == "◎" and _wfg[_k]["출처"].startswith("워커힐 보도자료") for _k in ("와인페어 입장 대상", "와인페어 입장료 · 투숙객", "와인페어 사전 구매 할인")), True)
_wfa = [_a for _a in _ag6.catalog(_P6(name="", traits={}, property="GRAND", is_guest=True)) if _a.key == "winefair"][0]
_wf_start = lambda _dt: (_s := _ag6.earliest_start(_wfa, _dt)) and (_s.strftime("%m-%d %H:%M") if _s.date() == _dt.date() else None)
chk("와인페어 시작 — 10/10 11:00 → 11:00 · 13:30 → 15:30 (1부에 120분이 안 들어가 2부) · 18:30 → 없음 · 10/31 · 10/9 → 없음",
    [_wf_start(datetime(2026, _m, _d, _h, _mi)) for _m, _d, _h, _mi in ((10, 10, 11, 0), (10, 10, 13, 30), (10, 10, 18, 30), (10, 31, 11, 0), (10, 9, 11, 0))]
    == ["10-10 11:00", "10-10 15:30", None, None, None] and _wfa.venue == "WINE_FAIR" and _wfa.location == "FOREST_PARK", True)
# 값 — 투숙객은 패키지와 상관없이 0원 (보도자료), 외부 손님만 성인 55,000 · 아동 10,000. 가격표 L3 · 0원 아님 (revenue.py 가 상품표를 보는 길)
_wf_at = datetime(2026, 10, 10, 11, 0)
_wf_pick = lambda **kw: (lambda _s: (_s["krw"], _s["qty"], _s["note"]))(_mm6.pick("winefair", _P6(name="", traits={}, **kw), _wf_at, _rnd8.Random(0)))
_wf_cases = [_wf_pick(party_size=2, is_guest=False), _wf_pick(party_size=3, has_child_under_13=True, is_guest=False),
             _wf_pick(party_size=2), _wf_pick(party_size=3, has_child_under_13=True), _wf_pick(party_size=3, package="Wine Forest")]
# 10/11 — 1부 동반 어린이 무료 (네이버 예약 판매 페이지 "1부 이용 시 동반 어린이 입장 무료") · 2부는 아동 10,000
_wf_2bu = (lambda _s: (_s["krw"], _s["qty"], _s["note"]))(_mm6.pick("winefair", _P6(name="", traits={}, party_size=3, has_child_under_13=True, is_guest=False),
                                                                     datetime(2026, 10, 10, 15, 30), _rnd8.Random(0)))
chk("값 — 외부 성인 2 = 110,000 · 외부 성인 2 + 아동 1부 = 110,000 (동반 어린이 무료) · 2부 = 120,000 · 투숙 (패키지 없음) 2인 = 0 · 투숙 성인 2 + 아동 = 0 · Wine Forest 성인 3 = 0",
    _wf_cases == [(110000, 2, ""), (110000, 3, "1부 동반 어린이 무료"), (0, 2, "투숙객 무료 입장"), (0, 3, "투숙객 무료 입장"), (0, 3, "투숙객 무료 입장")]
    and _wf_2bu == (120000, 3, "")
    and _pr6.L3.get("winefair") == ("레저", "와인페어") and _pr6.price_of("winefair")["krw"] == 55000, True)
# 포레스트 파크 · 테네즈 '투숙객 전용' (경수 부탁) — 출입 표 (비투숙 불가) 와 상품표 줄 (menu.fits 가 비투숙에게 안 판다) 둘 다.
#   상품표는 공식 문구 "워커힐 호텔앤리조트 투숙객 전용 시설" · "피트니스 회원 및 투숙객 전용 유료 시설입니다" 를 근거에 둔다 (10/8 다시 확인)
_go8 = {_v: [r["_guest_only"] for r in _mm6.by_venue[_v]] for _v in ("포레스트 파크", "테네즈 파크")}
chk(f"포레스트 파크 {len(_go8['포레스트 파크'])}줄 · 테네즈 {len(_go8['테네즈 파크'])}줄 — 상품표 전부 비투숙에게 안 팔고 · 출입 표도 비투숙 불가",
    all(_x and all(_x) for _x in _go8.values())
    and V.may_enter("FOREST_PARK", is_guest=False) is False and V.may_enter("TENNEZ_PARK", is_guest=False) is False, True)
# 가을 메뉴 · 워키 (경수 부탁 '팜플렛 내용을 상품표 · 가정표에') — 가정표 줄의 값 · 근거 문구가 상품표 줄과 같은가
_F8 = {("GEUMRYONG", "가을 한정 · 추미진향"): ("금룡", "추미진향 (가을 한정)"),
       ("ONDAL", "가을 한정 · 가을바다 꽃게 정찬"): ("온달", "가을바다 꽃게 정찬 (가을 한정)"),
       ("MYONGWOLGWAN", "가을 한정 · 능이버섯 등심 불고기 한상"): ("명월관", "능이버섯 등심 불고기 한상 (가을 한정)"),
       ("MYONGWOLGWAN", "가을 한정 · 자연송이 모둠구이 한상"): ("명월관", "자연송이 모둠구이 한상 (가을 한정)"),
       ("MYONGWOLGWAN", "가든 BBQ · 성인"): ("명월관", "명월관 가든 BBQ · 성인"),
       ("MYONGWOLGWAN", "가든 BBQ · 초등학생"): ("명월관", "명월관 가든 BBQ · 초등학생"),
       ("MYONGWOLGWAN", "가든 BBQ · 미취학"): ("명월관", "명월관 가든 BBQ · 미취학"),
       ("MOEGI", "가을 한정 · 아이소우"): ("모에기", "아이소우 (가을 한정)")}
_F8.update({("-", "워키 · " + r["상품"]): ("워키", r["상품"]) for r in _menu if r["업장"] == "워키"})
_mrow8 = {(r["업장"], r["상품"]): r for r in _menu}
_grow8 = {(g["장소코드"], g["항목"]): g for g in V.load_place_assumptions()}
_bad8 = [k[1] for k, m in _F8.items() if k not in _grow8 or m not in _mrow8
         or _grow8[k]["값"] != _mrow8[m]["단가"] or _grow8[k]["근거"] not in _mrow8[m]["근거"]]
chk(f"가을 메뉴 8 · 워키 6 — 가정표 {len(_F8)}줄의 값 · 근거 문구가 상품표 줄과 같다{' — ' + str(_bad8) if _bad8 else ''}",
    not _bad8 and len(_F8) == 14, True)

print("\n[10/11 · 피자힐 창] 검증기 = 가정표 · 상품표 · 현장 안내판 (경수 부탁 — 현장 질문 26)")
# 10/7 현장 안내판 (경수 사진): 1부 11:30 · 90분씩 7부 (20:30~22:00) · 라스트오더 21:00. 비스타 워커힐 서울 피자힐 공식 페이지 (한 · 영) 와 같다.
# 그랜드 사이트에 남은 피자힐 페이지는 아직 8부 11:00~23:00 — 검증기가 9/22 에 그 페이지를 따라 11:00~23:00 이었다.
_pzw = V.WALKERHILL_VENUE_WINDOWS["PIZZA_HILL"]
_pzg = {g["항목"]: g for g in V.load_place_assumptions("PIZZA_HILL")}
_pz_open, _pz_close = _pzg["운영 (1부 시작 ~ 7부 끝)"]["값"].split("-")
chk("창 하나 11:30~22:00 · L.O. 21:00 = 가정표 '운영 (1부 시작 ~ 7부 끝)' · 'Last Order · 포장 주문 마감' (공식 출처)",
    [(f"{w.open_at:%H:%M}", f"{w.close_at:%H:%M}", f"{w.effective_last_order():%H:%M}", w.source.name) for w in _pzw]
    == [(_pz_open, _pz_close, _pzg["Last Order · 포장 주문 마감"]["값"], "OFFICIAL")] == [("11:30", "22:00", "21:00", "OFFICIAL")], True)
_pz_h, _pz_m = map(int, _pz_open.split(":"))
chk("가정표 회차 90분 × 7부 = 11:30 부터 22:00 까지 (빈틈 · 남는 시간 없음)",
    (_pz_h * 60 + _pz_m + int(_pzg["회차 길이"]["값"]) * int(_pzg["좌석 회전 상한 · 하루"]["값"])) == 22 * 60, True)
_pz_menu = {r["시간제한"] for r in _menu if r["업장"] == "피자힐"}
chk(f"상품표 피자힐 {sum(r['업장'] == '피자힐' for r in _menu)}줄 시간제한 = 창 여는 시각 ~ L.O. (11:30-21:00)",
    _pz_menu == {f"{_pz_open}-{_pzg['Last Order · 포장 주문 마감']['값']}"}, True)
chk("착석 11:30 · 20:30~22:00 (7부) 는 되고 11:15 · L.O. 뒤 21:15 · 마감 뒤 22:00 은 안 된다",
    [window_only("PIZZA_HILL", "2026-10-14", _a, _b, "SEATED") for _a, _b in
     (("11:30", "12:30"), ("20:30", "22:00"), ("11:15", "12:30"), ("21:15", "21:45"), ("22:00", "22:30"))]
    == [True, True, False, False, False], True)
chk("포장 주문 20:55 는 되고 21:10 은 안 된다 (\"Last Order 및 포장 주문은 21:00까지\")",
    [window_only("PIZZA_HILL", "2026-10-14", _a, _b, "TAKEOUT_ORDER") for _a, _b in (("20:55", "21:00"), ("21:10", "21:15"))]
    == [True, False], True)
# 에이전트 v4 — 같은 창을 본다. 착석 피자는 체류 90분 (10/11 경수 · 7부제 그대로) 이라 마지막 시작이 20:30 (22:00 마감), 포장 (20분) 은 21:00 (L.O.)
_pz_act = {_a.key: _a for _a in _ag6.catalog(_P6(name="", traits={}, property="GRAND", is_guest=True)) if _a.key in ("pizza", "pizza_to")}
_pz_st = lambda _k, _h, _mi: (_s := _ag6.earliest_start(_pz_act[_k], datetime(2026, 10, 14, _h, _mi))) and (_s.strftime("%H:%M") if _s.date() == date(2026, 10, 14) else None)
chk("에이전트 v4 — 11:00 에 오면 11:30 부터 · 착석 피자 20:30 은 되고 20:40 은 안 된다 · 포장 21:00 은 되고 21:05 는 안 된다",
    [_pz_st("pizza", 11, 0), _pz_st("pizza", 20, 30), _pz_st("pizza", 20, 40), _pz_st("pizza_to", 21, 0), _pz_st("pizza_to", 21, 5)]
    == ["11:30", "20:30", None, "21:00", None] and _pz_act["pizza"].dwell_min == 90, True)

print("\n[10/11 · 사우나 · 빛의 시어터 창 · 휴관일] 검증기 = 가정표 (공식) — '경수님과 정하기' 로 남겼던 둘을 공식으로")
# 전엔 검증기에 창이 없어 에이전트가 임시값 (사우나 06:00~21:00 · blog01 안내표 / 빛의 시어터 10:00~19:00 · △ blog06) 으로 다녔다.
# 빛의 시어터 — 운영사 관람 안내 "관람시간 매일 10:00 - 18:00 (입장마감 17:00)". 사우나 — 그랜드 피트니스 센터 "운영시간 : 06:00 ~ 22:00
# (체련, 수영장 21:30까지)" 의 21:30 예외가 체련 · 수영장뿐이라 22:00 (○). 휴관일 — 공지 3768 (그랜드) · 2066 (비스타) 의 2026 날짜.
_tlg = {g["항목"]: g for g in V.load_place_assumptions("THEATRE_OF_LIGHT")}
_tl_open, _tl_close = _tlg["운영"]["값"].split("-")
_tw = V.WALKERHILL_VENUE_WINDOWS["THEATRE_OF_LIGHT"]
chk("빛의 시어터 기본 창 10:00~18:00 · 입장 마감 17:00 = 가정표 '운영' (운영사 관람 안내) · 나머지 창은 전부 2026 한정 (운영사 달별 공지)",
    (f"{_tw[0].open_at:%H:%M}", f"{_tw[0].close_at:%H:%M}", f"{_tw[0].effective_last_order():%H:%M}", _tw[0].source.name, _tw[0].season, _tw[0].years)
    == (_tl_open, _tl_close, _tlg["운영"]["조건"].split("입장 마감 ")[1], "OFFICIAL", None, None) == ("10:00", "18:00", "17:00", "OFFICIAL", None, None)
    and len(_tw) > 1 and all(w.years == frozenset({2026}) and w.source.name == "OFFICIAL" for w in _tw[1:]), True)
# 10/11 — 2026 달별 공지 (1432 · 1442 · 1452 · 1462 · 1470 · 1476). 하루하루 가정표와 맞춘다 — '휴관일 · 2026' 날은 창 0개,
# '입장 제한 · 2026' 날은 제한 앞 (입장 마감 = 제한 시작 1분 전) · 제한 끝부터로 쪼갠 창 (시각 순), 나머지 날은 그 달 시각 창 하나.
_tl_off = {date(2026, int(_x[:2]), int(_x[3:5])) for _x in _tlg["휴관일 · 2026"]["값"].split(",")}
_tl_sold = {}
for _x in _tlg["입장 제한 · 2026"]["값"].split(","):
    _tl_sold.setdefault(date(2026, int(_x[:2]), int(_x[3:5])), []).append(tuple(_x[6:].split("-")))
_tl_month = {}
for _k, _g in _tlg.items():
    if _k.startswith("운영 · 2026 "):
        _ms = _k.split()[-1].rstrip("월").split("~")
        for _mo in range(int(_ms[0]), int(_ms[-1]) + 1):
            _tl_month[_mo] = (_g["값"].split("-")[1], _g["조건"].split("입장 마감 ")[1].split(" ")[0])
def _tl_expect(_d):
    _cl, _lo = _tl_month.get(_d.month, (_tl_close, "17:00"))
    if _d in _tl_off:
        return []
    if _d not in _tl_sold:
        return [("10:00", _cl, _lo)]
    _out, _st = [], "10:00"
    for _s, _e in sorted(_tl_sold[_d]):
        if _s > _st:
            _out.append((_st, _cl, (datetime.combine(_d, datetime.strptime(_s, "%H:%M").time()) - timedelta(minutes=1)).strftime("%H:%M")))
        _st = _e
    return _out + ([(_st, _cl, _lo)] if _st <= _lo else [])
_tl_bad = [str(_d) for _d in (date(2026, 1, 1) + timedelta(_i) for _i in range(365))
           if [(f"{w.open_at:%H:%M}", f"{w.close_at:%H:%M}", f"{w.effective_last_order():%H:%M}") for w in _tw if w.opens_on(_d)] != _tl_expect(_d)]
chk(f"빛의 시어터 2026 하루하루 = 가정표 — 휴관 {len(_tl_off)}일 · 입장 제한 {len(_tl_sold)}일 · 5~8월 시각 ({sorted(_tl_month)}월) · "
    f"다른 날 10:00~18:00 · 17:00{' — ' + str(_tl_bad[:3]) if _tl_bad else ''}",
    not _tl_bad and len(_tl_off) == 49 and len(_tl_sold) == 15 and _tl_month == {5: ("18:40", "18:00"), 6: ("18:15", "18:00"),
                                                                                  7: ("18:40", "18:00"), 8: ("18:40", "18:00")}
    and [(f"{w.open_at:%H:%M}", f"{w.effective_last_order():%H:%M}") for w in _tw if w.opens_on(date(2025, 10, 14))] == [("10:00", "17:00")], True)
_sag = {g["항목"]: g for g in V.load_place_assumptions("WELLNESS_SAUNA")}
_fig = {g["항목"]: g for g in V.load_place_assumptions("FITNESS")}
chk("사우나 창 하나 06:00~22:00 (○ 계산) = 가정표 WELLNESS_SAUNA '운영' — 그랜드 피트니스 센터 '운영' 과 같은 페이지 · 같은 문구",
    [(f"{w.open_at:%H:%M}-{w.close_at:%H:%M}", w.source.name) for w in V.WALKERHILL_VENUE_WINDOWS["WELLNESS_SAUNA"]]
    == [(_sag["운영"]["값"], "DERIVED")] == [("06:00-22:00", "DERIVED")]
    and _sag["운영"]["등급"] == "○" and (_sag["운영"]["출처"], _fig["운영"]["값"]) == (_fig["운영"]["출처"], "06:00-22:00")
    and _fig["운영"]["근거"] in _sag["운영"]["근거"], True)
_off = lambda _code: {date(2026, int(_m), int(_d)) for _m, _d in (_x.split("-") for _x in
                      {g["항목"]: g for g in V.load_place_assumptions(_code)}["정기 휴관일 · 2026"]["값"].split(","))}
_shut = lambda _v: {_a + timedelta(_i) for w in V.WALKERHILL_VENUE_WINDOWS[_v] for _a, _b in w.closed for _i in range((_b - _a).days + 1)}
_g_off, _v_off = _off("FITNESS"), _off("VISTA_FITNESS")
chk(f"닫는 날 — 그랜드 수영장 · 사우나 = 가정표 FITNESS '정기 휴관일 · 2026' {len(_g_off)}일 · 비스타 수영장 · 피트니스 = VISTA_FITNESS {len(_v_off)}일",
    _shut("GRAND_POOL") == _shut("WELLNESS_SAUNA") == _g_off and _shut("VISTA_POOL") == _shut("VISTA_FITNESS") == _v_off
    and len(_g_off) == len(_v_off) == 11, True)
# 비스타 웰니스 사우나 (VISTA SIGNATURE STAY 상세 "운영 시간: 06:00 ~ 22:00 (휴관일: 10/14, 11/11, 12/9)") — 시각은 노드 창과 같고,
# 휴관일은 비스타 공지 2066 의 10~12월과 같다 (노드는 그랜드 휴관일로 닫는다 — 하나라서)
_sav = _sag["운영 · 비스타 웰니스 사우나"]
chk("비스타 웰니스 사우나 06:00-22:00 ◎ = 노드 창 · 휴관일 10/14 · 11/11 · 12/9 = 가정표 VISTA_FITNESS 휴관일의 10~12월",
    (_sav["값"], _sav["등급"]) == ("06:00-22:00", "◎")
    and {date(2026, int(_m), int(_d)) for _m, _d in _re.findall(r"(\d+)/(\d+)", _sav["근거"])} == {_d for _d in _v_off if _d.month >= 10}, True)
# 2026 하루하루 — 휴관일만 창이 0개, 나머지 날은 정확히 1개 (빛의 시어터는 위에서 따로 본다)
_daily_bad = [(_v, str(_d)) for _v, _o in (("GRAND_POOL", _g_off), ("WELLNESS_SAUNA", _g_off), ("VISTA_POOL", _v_off),
                                           ("VISTA_FITNESS", _v_off))
              for _d in (date(2026, 1, 1) + timedelta(_i) for _i in range(365))
              if sum(w.opens_on(_d) for w in V.WALKERHILL_VENUE_WINDOWS[_v]) != (0 if _d in _o else 1)]
chk(f"2026 하루하루 — 휴관일만 닫히고 나머지 날은 창이 하나{' — ' + str(_daily_bad[:3]) if _daily_bad else ''}", not _daily_bad, True)
chk("빛의 시어터 10/22 16:30~18:00 은 되고 17:10 입장 (마감 뒤) · 17:00~18:10 (18:00 넘김) 은 안 된다 · 10/14 (휴관) 는 안 된다 · "
    "10/20 (15:00~18:00 입장 제한) 14:00~15:30 은 되고 15:10 입장은 안 된다 · 5/14 (13:20~15:20 제한) 13:30 입장은 안 되고 15:30 은 된다 · "
    "8/31 18:00~18:40 은 된다 (8월은 18:40 마감 · 입장 18:00)",
    [window_only("THEATRE_OF_LIGHT", _d, _a, _b, "ADMITTED") for _d, _a, _b in (
        ("2026-10-22", "16:30", "18:00"), ("2026-10-22", "17:10", "17:50"), ("2026-10-22", "17:00", "18:10"), ("2026-10-14", "11:00", "12:00"),
        ("2026-10-20", "14:00", "15:30"), ("2026-10-20", "15:10", "16:00"), ("2026-05-14", "13:30", "14:30"), ("2026-05-14", "15:30", "17:00"),
        ("2026-08-31", "18:00", "18:40"))]
    == [True, False, False, False, True, False, False, True, True], True)
chk("사우나 21:00~22:00 은 되고 21:30~22:30 은 안 된다 · 10/20 (그랜드 휴관) 은 안 된다",
    [window_only("WELLNESS_SAUNA", _d, _a, _b, "IN_TREATMENT") for _d, _a, _b in
     (("2026-10-21", "21:00", "22:00"), ("2026-10-21", "21:30", "22:30"), ("2026-10-20", "10:00", "11:00"))] == [True, False, False], True)
# 에이전트 v4 — 사우나 · 빛의 시어터 행동이 이 창을 본다 (임시값이 아니라). 수영장은 휴관일에 못 간다
_ag_of = lambda _prop, _k: [_a for _a in _ag6.catalog(_P6(name="", traits={}, property=_prop, is_guest=True)) if _a.key == _k][0]
_st = lambda _a, _dt: (_s := _ag6.earliest_start(_a, _dt)) is not None and _s.date() == _dt.date() and _s.strftime("%H:%M")
_tla, _saa = _ag_of("GRAND", "theatre"), _ag_of("GRAND", "sauna")
chk("에이전트 v4 빛의 시어터 (90분) — 10/22 9:00 에 오면 10:00 · 16:30 은 되고 16:31 은 안 된다 · 10/14 (휴관) 는 안 된다 · "
    "10/20 14:00 은 되고 15:00 은 안 된다 · 5/14 14:00 에 오면 제한 끝 15:20 / 사우나 (60분) — 21:00 은 되고 21:01 · 10/20 은 안 된다",
    [_st(_tla, datetime(2026, 10, 22, 9, 0)), _st(_tla, datetime(2026, 10, 22, 16, 30)), _st(_tla, datetime(2026, 10, 22, 16, 31)),
     _st(_tla, datetime(2026, 10, 14, 9, 0)), _st(_tla, datetime(2026, 10, 20, 14, 0)), _st(_tla, datetime(2026, 10, 20, 15, 0)),
     _st(_tla, datetime(2026, 5, 14, 14, 0)),
     _st(_saa, datetime(2026, 10, 21, 21, 0)), _st(_saa, datetime(2026, 10, 21, 21, 1)), _st(_saa, datetime(2026, 10, 20, 6, 0))]
    == ["10:00", "16:30", False, False, "14:00", False, "15:20", "21:00", False, False]
    and (_tla.venue, _saa.venue, _tla.dwell_min, _saa.dwell_min) == ("THEATRE_OF_LIGHT", "WELLNESS_SAUNA", 90, 60)
    and not {"THEATRE_OF_LIGHT", "WELLNESS_SAUNA"} & set(_ag6.TEMP_WINDOWS), True)
chk("에이전트 v4 수영장 — 비스타 10/14 · 그랜드 · 더글라스 10/20 (휴관일) 은 못 가고, 비스타 10/15 · 그랜드 10/14 는 간다",
    [_st(_ag_of(_p, "pool"), datetime(2026, _m, _d, 10, 0)) for _p, _m, _d in
     (("VISTA", 10, 14), ("GRAND", 10, 20), ("DOUGLAS", 10, 20), ("VISTA", 10, 15), ("GRAND", 10, 14))]
    == [False, False, False, "10:00", "10:00"], True)

print("\n[수정 5-b] 르파사쥬 — 매장 영업시간과 주문 접수시간이 다르다")
# 매장 09:00~21:00, 피자 주문 접수 11:00~19:30.
# 한 창으로 뭉치면 "마감 전 주문하고 마감 후 수령" 이라는 후기 장면을 못 잰다.
chk("주문 11:30 (접수 시간 안)",
    window_only("LE_PASSAGE", "2022-08-04", "11:30", "12:00", "TAKEOUT_ORDER"), True)
chk("주문 19:20 (마감 직전 — 후기의 그 장면)",
    window_only("LE_PASSAGE", "2022-08-04", "19:20", "19:25", "TAKEOUT_ORDER"), True)
chk("주문 09:30 (매장은 열었지만 접수 전)",
    window_only("LE_PASSAGE", "2022-08-04", "09:30", "10:00", "TAKEOUT_ORDER"), False)
chk("주문 20:00 (접수 마감 후)",
    window_only("LE_PASSAGE", "2022-08-04", "20:00", "20:30", "TAKEOUT_ORDER"), False)
chk("수령 PICKED_UP 19:50 (주문 아님 — 매장 시간만 본다)",
    window_only("LE_PASSAGE", "2022-08-04", "19:50", "19:55", "PICKED_UP"), True)

# 상태 한정 창만 있는 업장에서, 그 목록에 없는 상태가 오면 **검사할 창이 없다.**
# 통과시키면 그 업장이 통째로 검사에서 빠진다 — venue 를 안 붙였을 때와 같다.
_probe = "ZZ_SCOPED_ONLY"
V.WALKERHILL_VENUE_WINDOWS[_probe] = (
    V.VenueWindow(V.time(11, 0), V.time(12, 0), states=frozenset({"TAKEOUT_ORDER"})),
)
chk("  상태 한정 창만 있는 업장 · 목록에 있는 상태 11:30",
    window_only(_probe, "2022-08-04", "11:30", "11:45", "TAKEOUT_ORDER"), True)
chk("  상태 한정 창만 있는 업장 · **목록에 없는 상태**",
    window_only(_probe, "2022-08-04", "20:00", "20:15", "BROWSING"), False)
V.WALKERHILL_VENUE_WINDOWS.pop(_probe)

print("\n[수정 7-c] 해를 넘기는 기간을 다룰 수 있는가")
# 내 블로그에는 해를 넘기는 기간을 쓰는 시설이 없다(리버파크는 여름 안에서 끝난다).
# 그래도 `opens_on` 이 그 경우를 제대로 다루는지는 확인해 둔다 — 겨울 시즌을 쓰는
# 후기를 맡은 사람이 이 기능에 기댈 것이기 때문이다.
_winter = V.VenueWindow(V.time(9, 0), V.time(18, 0), season=(12, 1, 2, 28))
chk("12/9 는 겨울 기간 안", _winter.opens_on(date(2026, 12, 9)), True)
chk("1/14 도 겨울 기간 안 (해를 넘김)", _winter.opens_on(date(2026, 1, 14)), True)
chk("6/10 은 겨울 기간 밖", _winter.opens_on(date(2026, 6, 10)), False)

print("\n[남겨 둔 구멍] TOGO 주문 마감은 검사되지 않는다")
# blog03 1편 ◎ "TOGO 주문 마감은 오후 7시 30분" 은 매장 영업시간(21:00)과 다른 값이다.
# 창은 업장 단위라 상태별 마감을 표현할 수 없다. 닫히면 알려 주도록 걸어 둔다.
late = window_only("LE_PASSAGE", "2022-08-04", "20:00", "20:30", "TAKEOUT_ORDERED")
print(f"  {'구멍 확인' if late else '** 닫혔다 — NOTES 를 고쳐라 **'} "
      f"20:00 TOGO 주문 → {'PASS' if late else 'FAIL'}  (후기 마감 19:30 은 안 재진다)")
if not late:
    FAILURES.append("TOGO 구멍이 닫혔는데 NOTES 가 그대로다")

print("\n[안전장치 0] 내가 쓴 상태 이름이 회사 카탈로그에 실제로 있는가")
# 사용 상태가 회사 카탈로그에 존재하는지 확인한다.
import re
from pathlib import Path

import blog04 as BH
import blog03 as BI

_DOC = (Path(__file__).resolve().parents[1] / "docs" /
        "walkerhill-guest-state-machine.md").read_text(encoding="utf-8")
_used = {s.state for segs in (BI.STAY_A, BI.STAY_B, BH.VISIT_A, BH.VISIT_B) for s in segs}
_unknown = [st for st in sorted(_used)
            if not re.search(rf"`{re.escape(st)}`|\b{re.escape(st)}\b", _DOC)]
chk(f"상태 {len(_used)}개 전부 문서에 있음", not _unknown, True)
if _unknown:
    print(f"       지어낸 상태: {', '.join(_unknown)}")

# machine 라벨도 마찬가지다. 판정에는 안 쓰이지만 틀리면 잘못된 정보가 남는다.
_MACHINES = {f"M{m.group(1)}_": m.group(2) for m in
             re.finditer(r"\|\s*M(\d+)\s*\|\s*`([A-Za-z]+)`", _DOC)}
_used_m = {s.machine for segs in (BI.STAY_A, BI.STAY_B, BH.VISIT_A, BH.VISIT_B) for s in segs}
_bad_m = [m for m in sorted(_used_m)
          if not any(m.startswith(f"M{n}_") for n in range(1, 12))
          or f"M{m.split('_')[0][1:]}_" not in _MACHINES]
chk(f"machine 라벨 {len(_used_m)}개가 M1~M11 안에 있음", not _bad_m, True)
# 번호만 맞는 게 아니라 **뜻이 맞는지**도 본다. 시설 세션은 §3.3 이고 §3 은 M7 이다.
_facility_m = {s.machine for segs in (BI.STAY_B,) for s in segs
               if s.venue in ("SKYARD", "GRAND_POOL", "VISTA_POOL")}
chk(f"시설 세션이 M7(OutletSessionMachine) 소속 {_facility_m}",
    _facility_m <= {"M7_Outlet"}, True)

print("\n[안전장치 0-b] 업장과 상태가 **같은 표 행**에 있는가")
# §3의 업장별 표 행과 실제 사용 상태를 대조한다.
_ROWS = [ln for ln in _DOC.splitlines() if ln.startswith("|") and "`" in ln]


def _states_of(keyword: str) -> set[str]:
    """그 업장이 적힌 표 행에서 백틱으로 묶인 상태 이름을 긁는다."""
    out: set[str] = set()
    for ln in _ROWS:
        if keyword in ln:
            out |= set(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", ln))
    return out


_VENUE_ROW = {
    "THE_BUFFET": "더뷔페",
    "GRAND_CLUB_LOUNGE": "클럽라운지",
    "LE_PASSAGE": "르 파사쥬",
    "PIZZA_HILL": "테이크아웃",
    "RIVERPARK": "리버파크",
    "GRAND_POOL": "그랜드피트니스", "VISTA_POOL": "그랜드피트니스",
    "LUX_BAR": "LUX BAR",
}
_pairs = [(s.venue, s.state) for segs in (BI.STAY_A, BI.STAY_B, BH.VISIT_A, BH.VISIT_B)
          for s in segs if s.venue in _VENUE_ROW]
_wrong = [(v, st) for v, st in _pairs if st not in _states_of(_VENUE_ROW[v])]
chk(f"(업장, 상태) 쌍 {len(_pairs)}개가 제 표 행 안에 있음", not _wrong, True)
for _v, _st in _wrong:
    print(f"       {_v} 에 {_st} — 그 업장 행에 없는 이름이다")
# SKYARD 는 §3.3 에 행이 아예 없어서 검사 대상에서 뺐다 (회신 항목).
chk("SKYARD 는 §3.3 에 행이 없다 (그래서 위 검사에서 제외)",
    not _states_of("SKYARD"), True)

print("\n[추정 검증] 방문일 추정이 결론을 흔드는가")
# blog03 는 방문일이 원문에 적혀 있다 — "2022년 8월 4일 (1박)" / "2023년 5월 12~13일 (1박)".
# **blog04 만 추정**이다. 게시일과 "토요일 1부 방문" 에서 역산했다.
# 기간(season) 을 넣은 뒤로는 날짜가 판정을 바꾸므로, 하나만 찍어 두면
# 그 날짜가 맞다는 보장이 없다. 그래서 **가능한 날짜를 전부** 돌린다.
import blog04 as BH


def shift(segments, days):
    return [
        TimelineSegment(s.state, s.location,
                        s.t_in + timedelta(days=days), s.t_out + timedelta(days=days),
                        machine=s.machine, venue=s.venue)
        for s in segments
    ]


print("   리버파크 — '토요일 1부 방문' · 골드시즌(7/22~8/20) 안 · 게시일(8/7) 이전 토요일")
for _d, _label in [(-14, "2023-07-22"), (-7, "2023-07-29"), (0, "2023-08-05")]:
    _r = validate_walkerhill_timeline(shift(BH.VISIT_A, _d), enforce_stay_day=False)
    chk(f"  {_label}({date.fromisoformat(_label).strftime('%a')}) 전체 동선",
        _r.ok, True)

print("   클럽스위트 — 게시일 2025-04-16 12:19 · 그 전 사흘 중 하루 체크인 · 3편 '공휴일이 껴있어서' 라 공휴일 낀 날 (삼일절 3/1 · 대체 3/3) 도")
for _d, _label in [(-45, "2025-03-01"), (-43, "2025-03-03"), (-2, "2025-04-13"), (-1, "2025-04-14"), (0, "2025-04-15")]:
    _r = validate_walkerhill_timeline(shift(BH.VISIT_B, _d), enforce_stay_day=True)
    chk(f"  {_label}({date.fromisoformat(_label).strftime('%a')}) 체크인 전체 동선",
        _r.ok, True)

print("   blog03 — 원문에 명시된 날짜라 추정이 아니다 (대조만)")
import blog03 as BI

for _segs, _label in [(BI.STAY_A, "2022-08-04 비스타"), (BI.STAY_B, "2023-05-12 그랜드")]:
    chk(f"  {_label}", validate_walkerhill_timeline(_segs, enforce_stay_day=True).ok, True)

print("\n[안전장치 1] 노드를 추가해도 **기존 지점 사이 거리가 안 바뀌어야** 한다")
# 노드를 넣으면 없던 지름길이 생길 수 있다. 그러면 I2 가 전역적으로 느슨해진다.
# 회사 시나리오 5개가 통과하는 건 타임라인 5개일 뿐이라 증거가 못 된다.
import importlib.util
import sys
from pathlib import Path

import walkerhill_timeline_validator as V

_ORIG = Path(__file__).resolve().parents[2] / "walkerhill-world" / "vendor" / \
    "walkerhill-main" / "timeline" / "walkerhill_timeline_validator.py"
if _ORIG.exists():
    _spec = importlib.util.spec_from_file_location("orig_validator", _ORIG)
    _orig = importlib.util.module_from_spec(_spec)
    sys.modules["orig_validator"] = _orig
    _spec.loader.exec_module(_orig)

    _when = datetime(2023, 5, 12, 12, 0)          # 피크 아닌 시각으로 고정
    _nodes = sorted(_orig._INTERNAL_GRAPH)
    _diff, _same = [], 0
    for _a in _nodes:
        for _b in _nodes:
            if _a == _b:
                continue
            _o = _orig.walkerhill_travel_time_min(_a, _b, _when)
            _m = V.walkerhill_travel_time_min(_a, _b, _when)
            if abs(_o - _m) > 1e-9:
                _diff.append(f"{_a}->{_b}: {_o}→{_m}")
            else:
                _same += 1
    # 취합에서 한호가 찾은 Q16 수정 — 더글라스 셔틀 호출 대기 5분이 **같은 건물 안 이동에도**
    # 붙던 버그를 건물 사이 이동에만 붙게 고쳤다. 그래서 더글라스 내부 쌍은 정확히 5분 줄어든다.
    # 이건 의도된 변경이라 통과시키고, **그 밖의 거리 변화는 여전히 실패**로 잡는다.
    # (검증기_취합_기록 §4 에 이 항목이 빠져 있어 진짜 회귀와 구분이 안 됐다.)
    def _is_q16(line: str) -> bool:
        pair, _, delta = line.partition(": ")
        a, _, b = pair.partition("->")
        if not (a.startswith("DOUGLAS_") and b.startswith("DOUGLAS_")):
            return False
        before, _, after = delta.partition("→")
        try:
            return abs(float(before) - float(after) - 5.0) < 1e-9
        except ValueError:
            return False

    _q16 = [d for d in _diff if _is_q16(d)]
    _unexpected = [d for d in _diff if d not in _q16]
    chk(f"기존 노드 {len(_nodes)}개 · {_same}쌍 거리 불변 "
        f"(더글라스 내부 {len(_q16)}쌍 -5분은 Q16 의도)", not _unexpected, True)
    _diff = _unexpected
    if _diff:
        for _x in _diff[:5]:
            print(f"       {_x}")
else:
    print("   (원본 검증기를 못 찾아 건너뜀)")

print("\n[안전장치 2] 같은 구간을 양방향으로 다르게 적지 않았는가")
# `_internal_adjacency` 는 무향으로 정규화하면서 **더 짧은 쪽**을 택한다.
# 실수로 두 값을 적으면 조용히 짧은 쪽이 쓰이고, 그건 느슨해지는 방향이다.
_M = V.WALKERHILL_INTERNAL_MATRIX
_conflict = [
    f"{a}->{b}={m} vs {b}->{a}={_M[b][a]}"
    for a, nb in _M.items() for b, m in nb.items()
    if b in _M and a in _M[b] and _M[b][a] != m
]
chk("양방향 값이 어긋난 구간 없음", not _conflict, True)
for _x in _conflict[:5]:
    print(f"       {_x}")

print("\n[출처 감사] 내가 넣거나 바꾼 운영 창의 근거가 무엇인가")
# "홈페이지 기준" 이라고 말하려면 **어디까지가 홈페이지인지** 분명해야 한다.
# 전부가 홈페이지는 아니다 — 리버파크 2023 창은 후기 현장 요금표로 채웠다 (2026 창은 10/5 공식 리버파크 페이지).
# 창 하나에 출처 하나가 아니다 — 취합으로 GRAND_CLUB_LOUNGE 에 슬기의 2025 후기 관측 창이
# 하나 들어왔다. "전부 공식" 기대는 그때부터 틀렸다 (검증기_취합_기록 §4). 기대를 집합으로 적는다.
_MINE = {
    "GRAND_CLUB_LOUNGE": "공식 홈페이지 3 + 후기 관측 1",
    "LE_PASSAGE": "공식 홈페이지",
    "PIZZA_HILL": "공식 홈페이지",
    "GRAND_POOL": "공식 홈페이지",
    "VISTA_POOL": "공식 홈페이지",
    "SKYARD": "공식 홈페이지",
    "RIVERPARK": "2023 후기 현장 요금표 4 + 2026 공식 리버파크 페이지 4",   # 10/5 2026 창
    "VISTA_FITNESS": "공식 홈페이지",   # 9/29 blog19 원문 "피트니스 클럽은 06:00 - 22:00" → 10/11 공식 웰니스 클럽 페이지 (값 같음) + 공지 2066 휴관일
    "WELLNESS_SAUNA": "공식 홈페이지 (계산)",   # 10/11 — 그랜드 피트니스 센터 운영시간의 21:30 예외가 체련 · 수영장뿐 + 공지 3768 휴관일
    "THEATRE_OF_LIGHT": "운영사 공식 홈페이지",  # 10/11 — deslumieres.co.kr 관람 안내 "매일 10:00 - 18:00 (입장마감 17:00)"
    "THE_BUFFET": "공식 홈페이지",     # 10/5 — 공식표 + 공식 공지 이미지
    "FOREST_PARK": "공식 홈페이지",    # 10/7 — 체험/활동 페이지 운영시간 + 공지 3757 입장 제한일
    "WINE_FAIR": "공식 홈페이지",      # 10/8 — Wine Forest 패키지 상세 (8837 · 8838) 운영 날짜 · 시간
}
for _v, _src in sorted(_MINE.items()):
    _ws = V.WALKERHILL_VENUE_WINDOWS[_v]
    _kinds = {w.source.name for w in _ws}
    if _src in ("공식 홈페이지", "운영사 공식 홈페이지"):
        _want = {"OFFICIAL"}
    elif _src == "공식 홈페이지 (계산)":
        _want = {"DERIVED"}
    elif _src == "공식 홈페이지 3 + 후기 관측 1":
        _want = {"OFFICIAL", "REVIEW"}
    elif _src.startswith("2023 후기 현장 요금표 4 + 2026"):
        _want = {"ESTIMATED", "OFFICIAL"}
    else:
        _want = {"ESTIMATED"}
    _mark = "OK  " if _kinds == _want else "** 표기 불일치 **"
    if _kinds != _want:
        FAILURES.append(f"{_v} 출처 표기")
    print(f"  {_mark} {_v:<20} 창 {len(_ws)}개 · {_src}")

print()
print("     내가 넣거나 고친 업장의 창이 공식 값과 맞는가 (틀린 값은 남기면 안 된다):")
# 아래에 명시한 아홉 시설의 등록 시간값을 대조한다.
#
# **이 표가 '공식 기준' 의 실체다.** 출처 표기(◎)는 내가 붙이는 것이라
# 틀려도 아무도 모른다 — 실제로 피자힐에서 한 번 틀렸다(근거 없이 22:00 으로
# 좁히고 ◎ 를 붙였다). 값을 바꿀 때는 공식 페이지를 열어 확인하고
# 확인 날짜를 같이 남긴다.
_OFFICIAL_HOURS = {
    # 2026-10-11 확인 · 비스타 워커힐 서울 피자힐 공식 페이지 (한 · 영) 7부, 1부 11:30 시작 ~ 7부 22:00 종료 · Last Order 21:00 = 10/7 현장 안내판
    #   (그랜드 사이트에 남은 피자힐 페이지는 아직 8부 11:00~23:00 — 9/22 에 그 페이지를 보고 11:00~23:00 으로 두었다)
    "PIZZA_HILL": [("11:30", "22:00")],
    # 2026-09-22 확인 · '영업시간 연중 09:00 ~ 21:00' / '테이크아웃 피자 주문시간 11:00 ~ 19:30'
    "LE_PASSAGE": [("09:00", "21:00"), ("11:00", "19:30")],
    # 2026-09-22 확인 · Breakfast / Tea Time / Happy Hour
    "GRAND_CLUB_LOUNGE": [("07:00", "10:00"), ("13:00", "17:00"), ("17:30", "19:30")],
    # 2026-10-11 확인 (9/22 엔 페이지를 다시 못 찾았다 → 9/30 부터 가정표에 공식 문구) ·
    #   그랜드 체험/활동 "(체련, 수영장 21:30까지)" · 비스타 웰니스 클럽 INDOOR POOL "06:00 ~ 21:30" · 스카이야드 "이용 시간 09:00 ~ 22:00"
    "GRAND_POOL": [("06:00", "21:30")], "VISTA_POOL": [("06:00", "21:30")],
    "SKYARD": [("09:00", "22:00")],
    # 2026-10-11 확인 · 비스타 웰니스 클럽 FITNESS "서비스 시간 06:00 ~ 22:00" · 그랜드 피트니스 센터 "운영시간 : 06:00 ~ 22:00" (사우나 · ○) ·
    #   빛의 시어터 운영사 "관람시간 매일 10:00 - 18:00 (입장마감 17:00)"
    "VISTA_FITNESS": [("06:00", "22:00")], "WELLNESS_SAUNA": [("06:00", "22:00")], "THEATRE_OF_LIGHT": [("10:00", "18:00")],
}
for _v, _want in _OFFICIAL_HOURS.items():
    # 연도 한정 창(`years`)은 특정 해의 관측이라 **공식 현재값 대조에서 뺀다.**
    # 취합으로 들어온 슬기의 2025 해피아워 창이 여기 섞여 FAIL 이 났었다 (Q17 — 창이 해마다 바뀐다).
    _got = [(f"{w.open_at:%H:%M}", f"{w.close_at:%H:%M}")
            for w in V.WALKERHILL_VENUE_WINDOWS[_v] if not w.years]
    chk(f"  {_v}", _got == _want, True)
    if _got != _want:
        print(f"         지금 {_got} / 공식 {_want}")
# 더뷔페 — 10/5 전까지는 주말 슬롯 6개만 두고 이 자리에서 '6개 그대로' 를 지켰다 (요일 기능이 없어서).
# 10/5 요일 칸이 생겨 공식표를 **요일 · 공휴일까지** 대조한다. 연도 한정 창(공지 둘)은 [10/5] 검사가 본다.
# 2026-10-05 확인 · DINING > 더뷔페 '운영시간 및 가격' 10~11월 표 (12월 표는 석식만 다르다)
# 10/5 — 12월 석식 매일 2부는 해마다 (공식 페이지 웹 보관본 2023 · 2024 · 2026) 라 season 으로 매년 12월에 둔다.
_BUFFET_OFFICIAL = [
    ("06:30", "08:10", "월토일+공휴일", ""),        # 표기는 월요일부터 (공식 "토요일 ~ 월요일, 공휴일")
    ("07:00", "10:00", "화수목금-공휴일 · 2026-07-17~2026-08-31 닫음", ""),    # 닫는 기간은 공식 공지 이미지 (2026 여름 조식 2부제)
    ("08:30", "10:00", "월토일+공휴일", ""),
    ("11:00", "13:00", "토일+공휴일", ""), ("12:00", "14:30", "월화수목금-공휴일", ""), ("13:30", "15:30", "토일+공휴일", ""),
    ("17:30", "19:30", "토+공휴일", ""),
    ("17:30", "19:30", "매일", "12-01~12-31"),                        # 공식 12월 표 "월요일 ~ 일요일 1부 17:30 ~ 19:30"
    ("18:00", "21:00", "월화수목금일-공휴일", "01-01~11-30"),          # 12월엔 닫힌다 (12월은 매일 2부)
    ("20:00", "22:00", "토+공휴일", ""),
    ("20:00", "22:00", "매일", "12-01~12-31"),                        # 공식 12월 표 "2부 20:00 ~ 22:00"
]
_season_txt = lambda w: f"{w.season[0]:02d}-{w.season[1]:02d}~{w.season[2]:02d}-{w.season[3]:02d}" if w.season else ""
_got = [(f"{w.open_at:%H:%M}", f"{w.close_at:%H:%M}", w.day_rule_text(), _season_txt(w))
        for w in V.WALKERHILL_VENUE_WINDOWS["THE_BUFFET"] if not w.years]
chk(f"  THE_BUFFET 연도 무관 창 {len(_BUFFET_OFFICIAL)}개 = 공식 (시각 · 요일 · 공휴일 · 기간)", _got == _BUFFET_OFFICIAL, True)
if _got != _BUFFET_OFFICIAL:
    print(f"         지금 {_got}")

print()
print("     ※ 이동 매트릭스의 **분(分) 값**은 층 정보만 공식이고 시간은 내 추정 △ 다.")
print("       예외: PARKING_TOWER_B1→GRAND_LOBBY 4분 은 회사 §8.4 값.")
print("     ※ I6 배타 상태의 StayDay 경계는 15:00~다음날 11:00이다.")

print("\n[회귀] 회사 시나리오 5개 — 10/5 요일 창으로 둘이 바뀐다 (이유를 적은 기대)")
import walkerhill_timeline_scenarios as sc

# 10/5 까지는 5개 모두 "원래 결과 그대로" 였다. 더뷔페 평일 창이 들어오며 둘이 바뀐다.
# 예제 날짜가 2026-09-21(월) · 22(화) 이고, 공식표로는 그 요일이 2부제가 아니다.
#   buffet         화 9/22 조식 08:00~09:40 — 화~금 조식은 07:00~10:00 한 번 → 통과가 맞다 (I3 → 없음)
#   double_booked  월 9/21 더뷔페 13:30~15:30 — 월~금 중식은 12:00~14:30 → I3 가 하나 더 (I1 · I4 → I1 · I3 · I4)
# 예제가 보이려던 것은 아래에서 날짜만 옮겨 그대로 확인한다.
expected = {
    "draft": (False, ["I3"]), "corrected": (True, []),
    "buffet": (True, []), "douglas": (False, ["I2"]),
    "double_booked": (False, ["I1", "I3", "I4"]),
}
builders = {
    "draft": (sc.draft_timeline, True), "corrected": (sc.corrected_timeline, True),
    "buffet": (sc.buffet_slot_mismatch, True), "douglas": (sc.douglas_shuttle_omitted, True),
    "double_booked": (sc.double_booked, False),
}
for name, (build, enforce) in builders.items():
    r = validate_walkerhill_timeline(build(), enforce_stay_day=enforce)
    want_ok, want_codes = expected[name]
    got = [v.invariant for v in r.violations]
    if r.ok is want_ok and got == want_codes:
        print(f"  OK   {name:<14} {'PASS' if r.ok else 'FAIL ' + str(got)}")
    else:
        FAILURES.append(f"회사 시나리오 {name}")
        print(f"  ** 틀림 ** {name:<14} {'PASS' if r.ok else 'FAIL ' + str(got)} "
              f"(기대 {'PASS' if want_ok else 'FAIL ' + str(want_codes)})")

# 예제의 뜻 — 날짜만 2부제 날로 옮기면 원래 결과가 그대로 나와야 한다.
#   buffet         하루 당겨 일 9/20 체크인 → 월 9/21 조식 (토~월 2부제) 08:00 → I3
#   double_booked  이틀 당겨 토 9/19 (토 · 일 중식 2부 13:30~15:30) → I1 · I4 만
_day0, _next0 = sc.DAY, sc.NEXT
for _name, _build, _enforce, _shift, _want in (
        ("buffet · 월요일 조식으로", sc.buffet_slot_mismatch, True, 1, ["I3"]),
        ("double_booked · 토요일로", sc.double_booked, False, 2, ["I1", "I4"])):
    sc.DAY, sc.NEXT = _day0 - timedelta(days=_shift), _next0 - timedelta(days=_shift)
    try:
        _got = [v.invariant for v in validate_walkerhill_timeline(_build(), enforce_stay_day=_enforce).violations]
    finally:
        sc.DAY, sc.NEXT = _day0, _next0
    chk(f"  {_name} ({(_day0 - timedelta(days=_shift)):%m-%d} 시작) → {_got} (기대 {_want})", _got == _want, True)

print("\n[10/13 · 정원표] program_capacity.csv — 실내수영장 · 사우나 · 빛의 시어터 · 워키 · 행사 (경수 부탁 — 화면의 수용 범위 대비 이용률)")
# 인용은 만들 때 그 쪽 화면 글자와 그대로 대조했다 (walkerhill.com 10/13 · 빛의 시어터 운영사 · 보도자료 9/14 · 대관 플랫폼 · 멘토링 기록).
# 여기서 보는 것 — 모양 · 등급 · 정원과 등급의 짝 · 검증기 창 · 가정표 · 상품표와 같은지 (docs/운영_조건표.md).
with open(_Path(__file__).resolve().parent / "program_capacity.csv", encoding="utf-8-sig", newline="") as _f:
    _cap = list(_csv.DictReader(_f))
_ccols = ["구분", "장소코드", "이름", "회차", "요일", "시작", "끝", "운영 기간", "정원", "정원 단위", "정원 등급", "정원 근거",
          "최소 인원", "화면 가정 정원", "화면 가정 근거", "시간 등급", "출처", "근거", "확인일", "비고", "온톨로지 가능량", "온톨로지 근거"]
chk(f"정원표를 읽는다 ({len(_cap)}줄) · 칸 이름이 맞다", len(_cap) > 0 and list(_cap[0].keys()) == _ccols, True)
chk("장소코드는 검증기 장소 또는 '-' 뿐이다", all(r["장소코드"] in _codes for r in _cap), True)
chk("등급은 ◎ ○ △ 모름 — 정원이 비면 '모름', 정원이 있으면 '모름' 이 아니다",
    all(r["정원 등급"] in ("◎", "○", "△", "모름") and r["시간 등급"] in ("◎", "○", "△")
        and (r["정원"] == "") == (r["정원 등급"] == "모름") for r in _cap), True)
_cday, _chm = _re.compile(r"매일|[월화수목금토일]+"), _re.compile(r"\d\d:\d\d")
_cbad = [r["이름"] for r in _cap if not (_cday.fullmatch(r["요일"]) and _chm.fullmatch(r["시작"]) and _chm.fullmatch(r["끝"])
                                        and r["시작"] < r["끝"] and r["출처"] and r["근거"] and r["정원 근거"])]
chk(f"요일 · 시작 · 끝 형식 (시작 < 끝) · 출처 · 근거 · 정원 근거가 다 있다{' — ' + str(_cbad) if _cbad else ''}", not _cbad, True)
chk("화면 가정 정원은 △ 근거와 함께만 · 공식 정원이 있는 줄에는 안 쓴다",
    all((r["화면 가정 정원"] == "") == (r["화면 가정 근거"] == "")
        and (not r["화면 가정 정원"] or (r["정원"] == "" and r["화면 가정 근거"].startswith("△"))) for r in _cap), True)
# 10/14 — 정원 모름인 곳은 온톨로지 가능량을 참고값으로 나란히 (진행 정리 10/13 · 소연 몫). 값은 timeline/ontology_oct_daily.json pool_def 와 같아야 한다
import json as _json
_onto_pool = _json.loads((_Path(__file__).resolve().parent / "ontology_oct_daily.json").read_text(encoding="utf-8"))["pool_def"]
_onto_rows = [r for r in _cap if r["온톨로지 가능량"]]
_onto_id = lambda r: re.search(r"pool_def '(\w+)'", r["온톨로지 근거"]).group(1)
_onto_cap = lambda pid: int(re.search(r"(?:일 정원|일 최대) (\d+)명", _onto_pool[pid]["how"]).group(1))
chk(f"온톨로지 가능량 {len(_onto_rows)}줄 — 정원 모름 줄에만 · 근거는 △ · 값 = ontology_oct_daily.json pool_def (워키 6종 20 · 리버파크 400)",
    len(_onto_rows) == 9 and all(r["정원"] == "" and r["온톨로지 근거"].startswith("△")
                                and int(r["온톨로지 가능량"]) == _onto_cap(_onto_id(r)) for r in _onto_rows)
    and all((r["온톨로지 가능량"] == "") == (r["온톨로지 근거"] == "") for r in _cap), True)
# 검증기 창과 같은가 — 날마다 열리는 창 중 하나와 시작 · 끝이 같다 (요일 · 휴관일을 피한 날로 본다)
_cwin = lambda _code, _d: {(f"{w.open_at:%H:%M}", f"{w.close_at:%H:%M}") for w in V.WALKERHILL_VENUE_WINDOWS[_code] if w.opens_on(_d)}
_cref = {"GRAND_POOL": date(2026, 10, 21), "VISTA_POOL": date(2026, 10, 21), "WELLNESS_SAUNA": date(2026, 10, 21),
         "FOREST_PARK": date(2026, 10, 21), "SKYARD": date(2026, 10, 21)}
_cwbad = [r["이름"] for r in _cap if r["장소코드"] in _cref and r["구분"] != "행사"
          and (r["시작"], r["끝"]) not in _cwin(r["장소코드"], _cref[r["장소코드"]])]
# 어텀 버스킹 (행사 · 포레스트 파크) — 그 날 포레스트 파크 창 안에 든다
_cwbad += [r["이름"] for r in _cap if r["이름"].startswith("어텀 버스킹")
           and not any(a <= r["시작"] and r["끝"] <= b for a, b in _cwin("FOREST_PARK", date.fromisoformat(r["운영 기간"][:10])))]
_rp_day = {"매일": date(2026, 7, 1), "월화수목": date(2026, 7, 20), "금토일": date(2026, 7, 18)}
_cwbad += [r["이름"] for r in _cap if r["장소코드"] == "RIVERPARK" and (r["시작"], r["끝"]) not in _cwin("RIVERPARK", _rp_day[r["요일"]])]
_cwbad += [r["이름"] for r in _cap if r["이름"].startswith("와인페어") and (r["시작"], r["끝"]) not in _cwin("WINE_FAIR", date(2026, 10, 10))]
chk(f"수영장 · 사우나 · 포레스트 파크 · 스카이야드 · 리버파크 · 와인페어 시간 = 검증기 창{' — ' + str(_cwbad) + ' · 와인페어 창 ' + str(sorted(_cwin('WINE_FAIR', date(2026, 10, 10)))) if _cwbad else ''}", not _cwbad, True)
# 행사 날짜 — '요일 × 운영 기간' 으로 센 날이 실제 행사 날과 같다 (요일만 맞추면 기간 사이 빈 날까지 들어간다)
_cdays = lambda r: {_a + timedelta(_i) for _a, _b in [tuple(date.fromisoformat(_x) for _x in r["운영 기간"][:21].split("~"))]
                    for _i in range((_b - _a).days + 1) if r["요일"] == "매일" or "월화수목금토일"[(_a + timedelta(_i)).weekday()] in r["요일"]}
_cev = lambda _p: set().union(*[_cdays(r) for r in _cap if r["이름"].startswith(_p)])
_bk_days = {date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26), date(2026, 10, 3), date(2026, 10, 4)}   # 기획전 그림 '9. 24-9. 26 | 10. 03-10. 04 (총 5일)'
_wf_days = {date(2026, 10, 1) + timedelta(_i) for _i in range(31) if _cwin("WINE_FAIR", date(2026, 10, 1) + timedelta(_i))}
chk(f"행사 날짜 — 어텀 버스킹 두 공연이 각각 5일 (기획전 그림) · 와인페어 1부 · 2부가 검증기 WINE_FAIR 가 여는 {len(_wf_days)}일과 같다",
    all(_cev(f"어텀 버스킹 · {_n}") == _bk_days for _n in ("서커스 공연", "밴드 공연"))
    and all(_cev(f"와인페어 '구름 위의 산책' · {_n}") == _wf_days for _n in ("1부", "2부")), True)
_ct = [r for r in _cap if r["장소코드"] == "THEATRE_OF_LIGHT"]
_tlen = int({g["항목"]: g for g in V.load_place_assumptions("THEATRE_OF_LIGHT")}["회차 길이"]["값"])
_hm = lambda _s: int(_s[:2]) * 60 + int(_s[3:])
chk(f"빛의 시어터 {len(_ct)}회차가 검증기 창 10:00~18:00 을 {_tlen}분씩 빈틈없이 채운다 (가정표 '회차 길이')",
    _cwin("THEATRE_OF_LIGHT", date(2026, 10, 21)) == {(_ct[0]["시작"], _ct[-1]["끝"])}
    and all(_hm(r["끝"]) - _hm(r["시작"]) == _tlen for r in _ct) and all(a["끝"] == b["시작"] for a, b in zip(_ct, _ct[1:])), True)
# 워키 — 상품표 '워키' 줄 (요일제한 · 시간제한 · 판매 기간) 과 같다
_wkm = {r["상품"]: r for r in _menu if r["업장"] == "워키"}
_wkc = {r["이름"][len("워키 · "):]: r for r in _cap if r["이름"].startswith("워키 · ")}
chk(f"워키 {len(_wkc)}종 — 요일 · 시간 · 운영 기간이 상품표 워키 줄과 같다 · 최소 인원 2 · 정원은 6종 모두 '모름' (공식 숫자 없음)",
    sorted(_wkc) == sorted(_wkm) and all(
        (r["요일"], f"{r['시작']}-{r['끝']}", r["운영 기간"]) == (_wkm[n]["요일제한"], _wkm[n]["시간제한"], f"{_wkm[n]['판매시작']}~{_wkm[n]['판매종료']}")
        and r["최소 인원"] == "2" and r["정원"] == "" and r["정원 등급"] == "모름" for n, r in _wkc.items()), True)
_tz = {g["항목"]: g for g in V.load_place_assumptions("TENNEZ_PARK")}
_tzc = [r for r in _cap if r["장소코드"] == "TENNEZ_PARK"]
chk("테네즈 동시 정원 12 = 가정표 '코트' 2면 × '코트 1면 최대 인원' 6 (계산 ○)",
    len(_tzc) == 1 and int(_tzc[0]["정원"]) == int(_tz["코트"]["값"]) * int(_tz["코트 1면 최대 인원"]["값"]) == 12 and _tzc[0]["정원 등급"] == "○", True)
_mtg = (_Path(__file__).resolve().parent.parent / "docs" / "멘토링_1013_결과.md").read_text(encoding="utf-8")
_forest = [r for r in _cap if r["이름"] == "워키 · 해설이 있는 숲 체험"]
# 10/13 다시 읽기 — 'up to 10 guests' 는 영문 대상 칸에만 있다 (한 · 중 대상 칸은 나이만 · 일문은 '투숙객' 만) → 정원이 아니라 화면 가정 (△)
chk("숲 체험 — 정원 '모름' · 화면 가정 10 (△ · 영문 대상 칸 'up to 10 guests' · 한 · 일 · 중엔 없음) · 대표님 예시 40 은 비고에만 (멘토링 기록에 그 문장이 있다)",
    len(_forest) == 1 and (_forest[0]["정원"], _forest[0]["정원 등급"]) == ("", "모름") and "up to 10 guests" in _forest[0]["정원 근거"]
    and all(_l in _forest[0]["정원 근거"] for _l in ("한글", "일문", "중문"))
    and _forest[0]["화면 가정 정원"] == "10" and _forest[0]["화면 가정 근거"].startswith("△") and "40명" in _forest[0]["비고"]
    and "해설이 있는 숲 체험은 40명 받을 수 있는데 4명이면 10%" in _mtg, True)
# 다른 각도 — 검증기 창이 아니라 가정표 '운영' 줄 값과 바로 맞춘다 (같은 공식 값을 두 표에 적었으니 글자가 같아야 한다)
_pa = {(g["장소코드"], g["항목"]): g for g in V.load_place_assumptions()}
_pa_run = {"GRAND_POOL": "운영", "VISTA_POOL": "운영", "FOREST_PARK": "운영", "SKYARD": "운영", "TENNEZ_PARK": "운영 · 3~11월"}
_pbad = [r["이름"] for r in _cap if r["장소코드"] in _pa_run and r["구분"] == "시설"
         and _pa[(r["장소코드"], _pa_run[r["장소코드"]])]["값"] != f"{r['시작']}-{r['끝']}"]
_pbad += [r["이름"] for r in _cap if r["이름"] == "그랜드 사우나 (피트니스 센터 안)" and _pa[("WELLNESS_SAUNA", "운영")]["값"] != f"{r['시작']}-{r['끝']}"]
_pbad += [r["이름"] for r in _cap if r["이름"] == "비스타 웰니스 사우나" and _pa[("WELLNESS_SAUNA", "운영 · 비스타 웰니스 사우나")]["값"] != f"{r['시작']}-{r['끝']}"]
_pbad += [r["이름"] for r in _cap if r["이름"].startswith("와인페어") and _pa[("FOREST_PARK", f"와인페어 운영 · {r['회차']}")]["값"] != f"{r['시작']}-{r['끝']}"]
_pbad += [r["이름"] for r in _cap if r["장소코드"] == "THEATRE_OF_LIGHT" and not (_pa[("THEATRE_OF_LIGHT", "운영")]["값"].split("-")[0] <= r["시작"]
                                                                               and r["끝"] <= _pa[("THEATRE_OF_LIGHT", "운영")]["값"].split("-")[1])]
_pbad += [r["이름"] for r in _cap if r["이름"].startswith("워키 · ") and f"{r['시작']}–{r['끝']}" not in _pa[("-", r["이름"])]["조건"]]
chk(f"정원표 시간 = 가정표 '운영' · 워키 줄 조건 · 와인페어 1부 · 2부 값 (검증기를 거치지 않고 바로){' — ' + str(_pbad) if _pbad else ''}", not _pbad, True)
# 모델이 지금 이 장소로 손님을 보내는가 (보고만 한다 — 워키 · 테네즈 행동이 생기면 여기 숫자가 바뀐다)
_cact = {a.location for _pp in ("GRAND", "VISTA", "DOUGLAS") for a in _ag6.catalog(_P6(name="", traits={}, property=_pp, is_guest=True))}
_cact |= {a.venue for _pp in ("GRAND", "VISTA", "DOUGLAS") for a in _ag6.catalog(_P6(name="", traits={}, property=_pp, is_guest=True)) if a.venue}
_ccodes = sorted({r["장소코드"] for r in _cap if r["장소코드"] != "-"})
print(f"       모델 손님 행동이 있는 곳: {[c for c in _ccodes if c in _cact]} · 없는 곳: {[c for c in _ccodes if c not in _cact]} · "
      f"장소코드 '-' (모델 밖) {sum(r['장소코드'] == '-' for r in _cap)}줄")
print(f"       정원 공개 {sum(r['정원'] != '' for r in _cap)}줄 · 모름 {sum(r['정원'] == '' for r in _cap)}줄 · 화면 가정값 {sum(r['화면 가정 정원'] != '' for r in _cap)}줄")
import agent_v1 as _ag1
_bfw = {g["항목"]: g for g in V.load_place_assumptions("THE_BUFFET")}
print(f"       더뷔페 조식 좌석 대기 — 가정표 제안 {_bfw['조식 · 좌석 대기 상한 (제안)']['값']}분 (△) · 지금 모델 agent_v1.HORIZON_MIN {_ag1.HORIZON_MIN}분")

print("\n[10/13 · 객실 수] 가정표 객실 수 = 정부 호텔업 등급결정 등록 (그랜드 539 · 비스타 244) · 더글라스 연혁 65 는 1993 년 수 (경수 부탁 — 507 · 244 · 50 채택 여부)")
# 등록 쪽 (hotelrating.or.kr) 은 호텔이 등급 신청 때 적은 객실 수 — 더글라스 하우스는 따로 없어 그랜드 539 에 든 것으로 본다
_rk = {(g["장소코드"], g["항목"]): g for g in V.load_place_assumptions()}
_rkg = _rk[("-", "총 객실 수 · 그랜드 워커힐 (호텔업 등급결정 등록)")]
_rkv = _rk[("VISTA_ROOM", "실 수 · 비스타 전체")]
_rkd = _rk[("DOUGLAS_ROOM", "실 수 · 더글라스 하우스 전체")]
_rkb = _rk[("GRAND_ROOM", "실 수 · 그랜드 본관 (등록 539 − 더글라스 50)")]
chk("등록 그랜드 539 · 비스타 244 (◎ · 근거에 등록 글자 'NNNRooms') · 더글라스 50 (△ · 연혁 65 는 1993 년 수라고 비고에) · 본관 489 = 539 − 50",
    (_rkg["값"], _rkg["등급"], _rkv["값"], _rkv["등급"]) == ("539", "◎", "244", "◎")
    and "539Rooms" in _rkg["근거"] and "244Rooms" in _rkv["근거"]
    and (_rkd["값"], _rkd["등급"]) == ("50", "△") and "1993" in _rkd["비고"]
    and int(_rkb["값"]) == int(_rkg["값"]) - int(_rkd["값"]), True)
_rk_ours = int(_rkb["값"]) + int(_rkv["값"]) + int(_rkd["값"])
_rk_model = " · ".join(k + " " + str(v["n"]) for k, v in _pr6.ROOMS.items())
print(f"       모델 prices.ROOMS {_rk_model} = {sum(v['n'] for v in _pr6.ROOMS.values())}실 · 온톨로지 507 · 244 · 50 = 801실 · 가정표 (등록 기준) 489 · 244 · 50 = {_rk_ours}실")

print("\n[10/13 · 피자힐 좌석] 실내 96 × 7부 = 672 (온톨로지 홀 가능량과 같은 셈) · 테라스는 공식에 있으나 좌석 수 모름 · 예약 식당")
_pz = {g["항목"]: g for g in V.load_place_assumptions("PIZZA_HILL")}
chk("실내 96 ◎ · 하루 최대 672 = 실내 96 × 7부 (실내만) · 테라스 운영 ◎ · 테라스 좌석 '모름' · 예약 접수 2개월 전 1일 ◎ (더뷔페와 같다)",
    (_pz["좌석 · 실내"]["값"], _pz["좌석 · 실내"]["등급"]) == ("96", "◎")
    and int(_pz["하루 최대 좌석 이용 (실내 96석 × 7부)"]["값"]) == int(_pz["좌석 · 실내"]["값"]) * int(_pz["좌석 회전 상한 · 하루"]["값"]) == 672
    and _pz["테라스 운영 (공식)"]["등급"] == "◎" and (_pz["좌석 · 테라스"]["값"], _pz["좌석 · 테라스"]["등급"]) == ("", "모름")
    and _pz["예약 접수 시작 (공식)"]["값"] == _bfw["예약 접수 시작 (공식)"]["값"] == "2개월 전 1일 10:00", True)

print("\n[10/13 · 더뷔페 석식] 석식도 예약 · 날짜 지정 (상품권 사전 예약 · 석식 패키지 월~금 입실) · 체류 120분 = 모델 buffet_d")
_ag_bd = {a.key: a for a in _ag6.catalog(_P6(name="", traits={}, property="VISTA", is_guest=True))}["buffet_d"]
_bd_m = [r for r in _menu if r["상품"] == "VISTA X THE BUFFET @ DINNER"]
chk("상품권 사전 예약 ◎ · 석식 패키지 월~금 ◎ = 상품표 요일제한 월화수목금 · 석식 체류 120 △ = agent_v4 buffet_d 보통 체류 · 토 · 공휴일 1부 창 2시간",
    _bfw["상품권 이용 · 사전 예약 (공식)"]["등급"] == "◎"
    and _bfw["석식 패키지 · 판매 요일 (공식)"]["등급"] == "◎" and len(_bd_m) == 1 and _bd_m[0]["요일제한"] == "월화수목금"
    and (_bfw["석식 · 체류"]["값"], _bfw["석식 · 체류"]["등급"]) == ("120", "△") and int(_bfw["석식 · 체류"]["값"]) == _ag_bd.dwell_min
    and _bfw["운영 · 석식 · 토·공휴일 1부"]["값"] == "17:30-19:30", True)

print("\n[10/13 · 어린이 값] 아이 동반이면 어른 n−1 + 어린이 줄 1 — 멘토링 '더뷔페 중식 3인 49만 원' 은 이미 어린이 값 · 금룡 · 온달 어린이 메뉴 (미취학)")
_kid3 = _P6(name="", traits={}, party_size=3, has_child_under_13=True, property="VISTA")
_kid_l = _mm6.pick("buffet_l", _kid3, datetime(2026, 10, 10, 11, 0), _rnd8.Random(1))
_kid_pa = {g["장소코드"] + " " + g["항목"]: g for g in V.load_place_assumptions() if "어린이" in g["항목"]}
_kid_mn = {r["업장"]: r for r in _menu if r["업장"] in ("금룡", "온달", "모에기") and ("어린이" in r["상품"])}
chk("3인 (아이 1) 더뷔페 주말 중식 494,000 = 성인 198,000 × 2 + 어린이 98,000 · 상품표 금룡 68,000 · 온달 40,000 · 모에기 70,000 = 가정표 어린이 메뉴 (◎) 값",
    _kid_l["krw"] == 198000 * 2 + 98000 == 494000 and _kid_l.get("child", "").startswith("중식 · 어린이")
    and [int(_kid_mn[v]["단가"]) for v in ("금룡", "온달", "모에기")]
        == [int(_kid_pa[k]["값"]) for k in ("GEUMRYONG 어린이 메뉴 (미취학)", "ONDAL 어린이반상 (미취학)", "MOEGI 어린이 메뉴 (초등생까지)")] == [68000, 40000, 70000]
    and all(_kid_pa[k]["등급"] == "◎" for k in ("GEUMRYONG 어린이 메뉴 (미취학)", "ONDAL 어린이반상 (미취학)", "MOEGI 어린이 메뉴 (초등생까지)")), True)

print("\n[10/14 · 어린이 값 짝] 고른 상품과 짝이 맞는 어린이 줄만 붙는다 — 명월관 BBQ 날 보통 메뉴 · 워키 · 포레스트 파크 (menu.child_row · 6985102 경수님 고침 확인)")
# 10/13 소연 제보 → 10/14 경수님 고침. 전엔 업장의 첫 어린이 줄을 붙여 명월관 가든 BBQ 지정일 보통 저녁에 'BBQ · 초등학생' 95,000,
# 워키 프로그램에 'Kids Play' 70,000, 포레스트 파크 투숙객 무료 입장 · 텐트에 '초과 인원 입장료 · 어린이' 20,000 이 붙었다.
# 같은 씨앗 통째 비교 (10/3 · 10/10 · 10/14) 에서 바뀐 결제 줄은 명월관 6줄뿐 · 행동 같음 (input_provenance '어린이 가격' 비고)
_kd = datetime(2026, 10, 10, 12, 0)              # 토요일 · 명월관 가든 BBQ 지정일 (09-12 · 09-19 · 10-03 · 10-10)
_kid_of = lambda r: (_mm6.child_row("x", r, _kd) or {}).get("상품", "")
_kv = lambda v: [r for r in _mm6.by_venue.get(v, []) if not r["_child"] and _mm6.on_sale(r, _kd.date())]
_my_bbq = [r for r in _kv("명월관") if r["상품"].startswith("명월관 가든 BBQ")]
_my_etc = [r for r in _kv("명월관") if not r["상품"].startswith("명월관 가든 BBQ")]
chk(f"10/10 명월관 — 가든 BBQ 성인 {len(_my_bbq)}줄엔 'BBQ · 초등학생' · 보통 메뉴 {len(_my_etc)}줄엔 어린이 줄 없음 (명월관은 어린이 메뉴가 없다 · 가정표)",
    len(_my_bbq) == 1 and _kid_of(_my_bbq[0]) == "명월관 가든 BBQ · 초등학생" and len(_my_etc) >= 10 and all(_kid_of(r) == "" for r in _my_etc), True)
_kid_fixed = {v: {_kid_of(r) for r in _kv(v)} for v in ("금룡", "온달", "모에기", "워키", "포레스트 파크")}
chk("10/10 금룡 · 온달 · 모에기는 어느 메뉴든 그 업장 어린이 메뉴 · 워키 프로그램엔 Kids Play 가 안 붙는다 · 포레스트 파크는 '초과 인원 입장료' 끼리만",
    _kid_fixed["금룡"] == {"어린이 메뉴"} and _kid_fixed["온달"] == {"어린이반상"} and _kid_fixed["모에기"] == {"어린이 메뉴"}
    and _kid_fixed["워키"] == {""} and len(_kv("워키")) >= 3
    and {r["상품"]: _kid_of(r) for r in _kv("포레스트 파크")} == {"포레스트 파크 · 투숙객": "", "초과 인원 입장료 · 성인": "초과 인원 입장료 · 어린이", "텐트 이용료": ""}, True)
_kid_my = _mm6.pick("myong", _P6(name="", traits={}, party_size=3, has_child_under_13=True, property="GRAND"), datetime(2026, 10, 10, 18, 0), _rnd8.Random(3))
chk(f"10/10 명월관 3인 (아이 1) 이 고른 '{_kid_my['product']}' — BBQ 면 BBQ 초등학생, 아니면 어린이 줄 없음 (수량 2 · 아이 몫 0원)",
    _kid_my.get("child", "") == ("명월관 가든 BBQ · 초등학생" if _kid_my["product"].startswith("명월관 가든 BBQ") else "")
    and (_kid_my["product"].startswith("명월관 가든 BBQ") or _kid_my["qty"] == 2), True)

print("\n[10/14 · 주말 v4] 평일 전용 조정값은 주말 · 공휴일 계산에서 빠진다 — 주말 '온톨로지 정합' = 평일 비투숙 반영 전 v4 (경수님 7e3eab8 · 작업배정 10/14 오후 검수)")
# 10/14 소연 확인: 10/10 (토) 을 화면 '온톨로지 정합' (wd_day 0.5 포함) 과 반영 전 v4 로 캐시를 따로 두고 끝까지 돌려 캐시 키 · 결과 JSON · 손님 원장이 같았다
# (손님 1,087팀 · 총매출 667,162,000). 평일 10/14 는 950 → 813팀으로 달랐다. 여기서는 매번 돌리지 않고 키 · 조정값 거르기를 10월 하루하루 본다
import sys as _sys
_sys.path.insert(0, str(_Path(__file__).resolve().parent / "viewer"))
import engine as _eng
_pre = re.search(r"full:\s*(\{[^}]*\})", (_Path(__file__).resolve().parent / "viewer" / "static" / "app.js").read_text(encoding="utf-8"))
_v4 = _json.loads(re.sub(r"(\w+):", r'"\1":', _pre.group(1)))
_v4_old = {k: v for k, v in _v4.items() if k not in _eng.WEEKDAY_ONLY}
_oct = [f"2026-10-{d:02d}" for d in range(1, 32)]
_we = [s for s in _oct if not _eng.agent_v4.is_weekday(datetime.strptime(s, "%Y-%m-%d").date())]
_key = lambda s, th: _eng.day_key(s, "none", 1.0, th)
chk(f"10월 주말 · 공휴일 {len(_we)}일 ({', '.join(s[5:] for s in _we)}) — 화면 '온톨로지 정합' 에서 평일 전용 조정값 "
    f"({' · '.join(k for k in _v4 if k in _eng.WEEKDAY_ONLY)}) 이 빠져 반영 전 v4 와 조정값 · 캐시 키가 같고, 평일 {len(_oct) - len(_we)}일은 남아 키가 다르다",
    any(k in _v4 for k in _eng.WEEKDAY_ONLY) and "2026-10-09" in _we and "2026-10-03" in _we
    and all((_eng.norm_theta(s, _v4) == _v4_old and _key(s, _v4) == _key(s, _v4_old)) if s in _we
            else (_eng.norm_theta(s, _v4) == _v4 and _key(s, _v4) != _key(s, _v4_old)) for s in _oct), True)
chk("평일 전용 목록 (engine.WEEKDAY_ONLY) 에 'wd_' 조정값 · biz_party 가 다 들어 있다 — 새 평일 조정값이 빠지면 주말 결과가 바뀐다",
    {k for k in _eng.KNOBS if k.startswith("wd_")} | {"biz_party"} <= set(_eng.WEEKDAY_ONLY), True)

print("\n[10/14 · 별실] 별실 운영 조건 · 공식 예약 시각 — 줄끼리 맞는가 (작업배정 10/14 오후 · docs/별실_운영조건_1014.md)")
_pa = {(r["장소코드"], r["항목"]): r for r in V.load_place_assumptions()}
_geum = _pa[("GEUMRYONG", "PDR · 방 수와 방별 인원")]
# 'I · II 12' 처럼 한 줄에 두 방 — 로마 숫자 두 개면 두 방으로 센다
_seats = []
for part in re.split(r" · (?=[가-힣])", _geum["조건"].replace(" (인)", "")):
    m = re.match(r"(.+?) (\d+)$", part.strip())
    _seats += [int(m.group(2))] * (2 if re.search(r"I · II$", m.group(1)) else 1)
chk(f"금룡 PDR 방 {len(_seats)}개 · 방별 합 {sum(_seats)} — 값 12실 · 좌석 줄 'PDR 99' 와 1 차이 (공식 한글 쪽 그대로 · 비고)",
    len(_seats) == int(_geum["값"]) == 12 and sum(_seats) == 98 and "PDR 99" in _pa[("GEUMRYONG", "좌석")]["조건"], True)
_dol = [r for (c, it), r in _pa.items() if c == "GEUMRYONG" and it.startswith("가족연회 (돌잔치) · ")]
chk(f"금룡 돌잔치 방 {len(_dol)}개 — 개런티 금액 = 기준 인원 × 250,000 ('수' 코스 줄 값) · 최대 인원 ≥ 기준 인원",
    len(_dol) == 6 and all(int(re.search(r"개런티 (\d+)만원", r["조건"]).group(1)) * 10_000 == int(r["값"]) * int(_pa[("GEUMRYONG", "가족연회 (돌잔치) 코스 · 수 (개런티 단가)")]["값"])
                           and int(re.search(r"최대 (\d+)명", r["조건"]).group(1)) >= int(r["값"]) for r in _dol), True)
_ond = _pa[("ONDAL", "별실 · 방 수와 방별 인원")]
_rng = [tuple(map(int, x)) for x in re.findall(r"(\d+)~(\d+)인", _ond["조건"])]
chk("온달 별실 5실 — 범위 2~4 · 5~10 · 8~12 가 '좌석' 줄 조건 '별실 2~4 · 5~10 · 8~12인' 과 같다 · 최소 2 · 최대 12",
    int(_ond["값"]) == 5 and _rng == [(2, 4), (5, 10), (8, 12)] and "별실 2~4 · 5~10 · 8~12인" in _pa[("ONDAL", "좌석")]["조건"], True)
_hm = lambda s: int(s[:2]) * 60 + int(s[3:5])
_rsv_ok = []
for _c in ("GEUMRYONG", "ONDAL", "MOEGI"):
    _r = _pa[(_c, "예약 시작 시각 (공식 예약 화면)")]
    _l, _d = re.findall(r"(\d\d:\d\d)-(\d\d:\d\d)", _r["값"])
    _close = [_pa[(_c, "운영 · 점심")]["값"][-5:], _pa[(_c, "운영 · 저녁")]["값"][-5:]]
    _rsv_ok.append(_hm(_l[1]) + 90 == _hm(_close[0]) and _hm(_d[1]) + 90 == _hm(_close[1]) and "90분 전" in _r["조건"])
chk("금룡 · 온달 · 모에기 마지막 예약 시작 + 90분 = 가정표 '운영 · 점심 · 저녁' 마감 (15:00 · 21:00) — 식사시간 간접 근거의 계산",
    all(_rsv_ok), True)

print("\n[10/14 저녁 · 네이버 · 명월관 예약 화면] 금룡 · 명월관 판매 페이지 (사용자 화면 · 크롤링 안 함) · 명월관 공식 예약 화면 — 줄끼리 · 상품표와 맞는가")
_pa = {(r["장소코드"], r["항목"]): r for r in V.load_place_assumptions()}
_mrow = {(r["업장"], r["상품"]): r for r in _menu}
# 네이버 할인가 → 상품표 줄 (이름이 메뉴판 · 상품표와 조금 다르다)
_nv = dict(re.findall(r"(진계도 셰프 스페셜|도|만수무강|원|경) ([\d,]+)", _pa[("GEUMRYONG", "네이버 예약 할인")]["조건"]))
_nvm = {"진계도 셰프 스페셜": "진계도 셰프 스페셜", "도": "도원경 · 도", "만수무강": "만수무강 코스", "원": "도원경 · 원", "경": "도원경 · 경"}
chk("금룡 네이버 할인가 5개 = 상품표 코스 단가 × 0.9 그대로 (진계도 셰프 스페셜 · 도 · 만수무강 · 원 · 경) · 할인율 줄 10%",
    len(_nv) == 5 and _pa[("GEUMRYONG", "네이버 예약 할인")]["값"] == "10"
    and all(int(v.replace(",", "")) * 10 == int(_mrow[("금룡", _nvm[k])]["단가"]) * 9 for k, v in _nv.items()), True)
_jg = _mrow.get(("금룡", "진계도 셰프 스페셜"))
chk("상품표 금룡 '진계도 셰프 스페셜' 280,000 · 1인 (2인 이상) · 만수무강과 같은 시간 (메뉴판 9쪽 · 10/14 더함)",
    bool(_jg) and _jg["단가"] == "280000" and _jg["단위"] == "1인 (2인 이상)"
    and _jg["시간제한"] == _mrow[("금룡", "만수무강 코스")]["시간제한"], True)
_glo = _pa[("GEUMRYONG", "라스트 오더")]["값"]
_grs = re.findall(r"(\d\d:\d\d)-(\d\d:\d\d)", _pa[("GEUMRYONG", "예약 시작 시각 (공식 예약 화면)")]["값"])[1][1]
chk("금룡 라스트 오더 19:30 (네이버) = 공식 예약 화면 마지막 예약 시작 = 운영 · 저녁 마감 − 90분",
    _glo == _grs == "19:30" and _hm(_glo) + 90 == _hm(_pa[("GEUMRYONG", "운영 · 저녁")]["값"][-5:]), True)
_mw = lambda it: _pa[("MYONGWOLGWAN", it)]
_mo = [_mw("운영 · 점심")["값"], _mw("운영 · 저녁")["값"]]
_ms = re.findall(r"\d\d:\d\d", _mw("예약 시작 시각 (공식 예약 화면)")["값"])
chk("명월관 공식 예약 시각 4개 = 끼니마다 운영 시작 · 30분 뒤 (12:00 · 12:30 · 17:30 · 18:00) · 온라인 1회 최대 6명 (10/14 오후 보류를 풂)",
    len(_ms) == 4 and [_hm(x) for x in _ms] == [_hm(_mo[0][:5]), _hm(_mo[0][:5]) + 30, _hm(_mo[1][:5]), _hm(_mo[1][:5]) + 30]
    and "최대 6명" in _mw("예약 시작 시각 (공식 예약 화면)")["조건"], True)
_ann = _mw("별채 맡김차림 · 식사 시간")
_last = [int(h) * 60 for _, h in re.findall(r"(점심|저녁) (\d+)시", _ann["조건"])]
chk("명월관 별채 맡김차림 120분 + 마지막 예약 (점심 13시 · 저녁 19시) = 운영 마감 (15:00 · 21:00) · 상품표 별채 맡김차림 줄도 같은 두 창",
    _ann["값"] == "120" and _last == [13 * 60, 19 * 60] and [x + 120 for x in _last] == [_hm(_mo[0][-5:]), _hm(_mo[1][-5:])]
    and {r["시간제한"] for (u, n), r in _mrow.items() if u == "명월관" and n.startswith("별채 한우 맡김차림")} == set(_mo), True)
chk("명월관 라스트 오더 (본당) 20:00 = 운영 · 저녁 마감 − 60분 (네이버 — 공식 명월관 쪽엔 없다)",
    _hm(_mw("라스트 오더 (본당)")["값"]) + 60 == _hm(_mo[1][-5:]), True)
_vg = _pa[("VALET_DESK", "발렛 요금")]
_vm = _mrow[("발렛", "발렛 파킹")]
chk("발렛 28,000 — 상품표 줄 값 · 등급 = 가정표 VALET_DESK (금룡 · 명월관 판매 페이지 둘 다 '발렛비 28,000원' · 10/14 ○ → ◎)",
    _vm["단가"] == _vg["값"] == "28000" and _vm["등급"] == _vg["등급"] == "◎", True)
_mx = {c: re.search(r"최대 (\d+)명", _pa[(c, "예약 시작 시각 (공식 예약 화면)")]["조건"]).group(1)
       for c in ("GEUMRYONG", "ONDAL", "MOEGI", "MYONGWOLGWAN")}
chk(f"공식 예약 화면 온라인 1회 최대 인원 {_mx} — 비고에 '최대 + 1명으로 조회하면 세션 0개' 확인이 적혀 있다",
    _mx == {"GEUMRYONG": "4", "ONDAL": "8", "MOEGI": "4", "MYONGWOLGWAN": "6"}
    and all(f"성인 {int(n) + 1}명으로 조회하면 세션이 0개" in _pa[(c, "예약 시작 시각 (공식 예약 화면)")]["비고"] for c, n in _mx.items()), True)
# 10/14 밤 — 식사시간을 회차로 적은 공식 값 (금룡 예약 세션 설정 · 모에기 메뉴판 카운터 회차)
_gwk = _pa[("GEUMRYONG", "주말 · 공휴일 점심 회차 (공식 예약 화면)")]
_gl = re.findall(r"(\d\d:\d\d)-(\d\d:\d\d)", _pa[("GEUMRYONG", "예약 시작 시각 (공식 예약 화면)")]["값"])[0]
chk("금룡 주말 · 공휴일 점심 회차 90분 = 두 회차 (12:00 · 13:30) 사이 · 마지막 회차 + 90분 = 운영 · 점심 마감 15:00",
    int(_gwk["값"]) == _hm(_gl[1]) - _hm(_gl[0]) == 90 and "12:00 · 13:30 두 회차" in _gwk["조건"]
    and _hm(_gl[1]) + int(_gwk["값"]) == _hm(_pa[("GEUMRYONG", "운영 · 점심")]["값"][-5:]), True)
_mc = {k: _pa[("MOEGI", f"철판 · 오마카세 카운터 회차 · {k}")] for k in ("점심", "저녁")}
_mcs = {k: [(_hm(a), _hm(b)) for a, b in re.findall(r"(\d\d:\d\d)-(\d\d:\d\d)", r["조건"])] for k, r in _mc.items()}
chk("모에기 카운터 회차 — 점심 두 회차 다 90분 · 저녁 두 회차 다 150분 (값 칸과 같다) · 저녁 2부 끝 = 운영 · 저녁 마감 21:00",
    (_mc["점심"]["값"], _mc["저녁"]["값"]) == ("90", "150")
    and all(len(v) == 2 and all(b - a == int(_mc[k]["값"]) for a, b in v) for k, v in _mcs.items())
    and _mcs["저녁"][1][1] == _hm(_pa[("MOEGI", "운영 · 저녁")]["값"][-5:]), True)
# 10/14 밤 — 모에기 · 온달 네이버 판매 페이지 (소연 화면) · 명월관 모둠 한상 상품표
_mo = lambda it: _pa[("MOEGI", it)]
_mnv = dict(re.findall(r"(생선회 정식|장어 정식|모에기 코스|마코토|미야비|모미지) ([\d,]+)", _mo("네이버 예약 할인")["조건"]))
_mnm = {"생선회 정식": "생선회 정식 (SASHIMI SET)", "장어 정식": "요비모도시 장어 정식", "모에기 코스": "런치 모에기 코스",
        "마코토": "마코토 코스", "미야비": "미야비 코스", "모미지": "모미지 코스"}
_mai = int(re.search(r"아이소우 ([\d,]+)", _mo("네이버 예약 할인")["조건"]).group(1).replace(",", ""))
chk("모에기 네이버 할인가 6개 = 상품표 단가 × 0.9 · 아이소우 83,300 = 상품표 98,000 × 0.85",
    len(_mnv) == 6 and all(int(v.replace(",", "")) * 10 == int(_mrow[("모에기", _mnm[k])]["단가"]) * 9 for k, v in _mnv.items())
    and _mai * 100 == int(_mrow[("모에기", "아이소우 (가을 한정)")]["단가"]) * 85, True)
_mlo = re.findall(r"\d\d:\d\d", _mo("라스트 오더")["값"])            # 코스 점심 · 정식 · 코스 저녁
_mrs = re.findall(r"(\d\d:\d\d)-(\d\d:\d\d)", _mo("예약 시작 시각 (공식 예약 화면)")["값"])
chk("모에기 라스트 오더 (메뉴판 · 네이버) 코스 13:30 · 19:30 = 공식 예약 마지막 시작 = 마감 − 90분 = 상품표 코스 줄 끝 · 정식 14:00 = 상품표 정식 줄 끝",
    _mlo == ["13:30", "14:00", "19:30"] and [_mrs[0][1], _mrs[1][1]] == [_mlo[0], _mlo[2]]
    and _hm(_mlo[0]) + 90 == _hm(_mo("운영 · 점심")["값"][-5:]) and _hm(_mlo[2]) + 90 == _hm(_mo("운영 · 저녁")["값"][-5:])
    and _mrow[("모에기", "런치 모에기 코스")]["시간제한"].endswith(_mlo[0])
    and all(_mrow[("모에기", n)]["시간제한"].endswith(_mlo[2]) for n in ("마코토 코스", "미야비 코스", "모미지 코스"))
    and all(_mrow[("모에기", n)]["시간제한"].endswith(_mlo[1]) for n in ("생선회 정식 (SASHIMI SET)", "요비모도시 장어 정식")), True)
_onv = _pa[("ONDAL", "네이버 예약 할인")]["조건"]
_onc = {n: int(_mrow[("온달", n)]["단가"]) for n in ("낮것상 (주중 점심)", "궁중상차림", "수라상차림", "가을바다 꽃게 정찬 (가을 한정)")}
_ong = lambda v, r: f"{(v - 5000) * r // 100:,}" in _onv              # 네이버는 5,000원 낮은 지난 정가 기준
chk("온달 네이버 — 꽃게정찬 68,000 = 상품표 80,000 × 0.85 · 코스 셋은 상품표 (메뉴판) 보다 5,000원 낮은 정가의 15% · 10% (엇갈림이 비고에 있다)",
    f"{_onc['가을바다 꽃게 정찬 (가을 한정)'] * 85 // 100:,}" in _onv and _ong(_onc["낮것상 (주중 점심)"], 85)
    and all(_ong(_onc[n], 85) and _ong(_onc[n], 90) for n in ("궁중상차림", "수라상차림"))
    and "5,000원 낮은 지난 정가" in _pa[("ONDAL", "네이버 예약 할인")]["비고"], True)
_sets = [r for r in _menu if r["단위"].startswith("세트") and re.search(r"\d+인", r["단위"])]
chk(f"인원이 적힌 세트 줄 {len(_sets)}개는 생성기가 세트 인원을 읽는다 (menu.Menu.set_size · '세트 · 2인 (510g)' 처럼 쓰면 못 읽어 1인 손님에게도 세트가 갔다)",
    len(_sets) >= 7 and all(_mn.Menu.set_size(r) == int(re.search(r"(\d+)인", r["단위"]).group(1)) for r in _sets), True)
_mdh = _mrow.get(("명월관", "명월관 모둠 한상"))
chk("상품표 명월관 모둠 한상 = 가정표 값 770,000 · 기준 인원 4 (세트 4인) · 명월관 세트는 2인 · 4인 둘",
    bool(_mdh) and int(_mdh["단가"]) == int(_mw("명월관 모둠 한상")["값"]) and _mn.Menu.set_size(_mdh) == int(_mw("명월관 모둠 한상 · 기준 인원")["값"])
    and sorted(_mn.Menu.set_size(r) for r in _menu if r["업장"] == "명월관" and _mn.Menu.set_size(r)) == [2, 4], True)
# 금룡 일요일 저녁 단품 — 공식 예약 화면 (단품 세션 요일 월~금 · 일 · 2026-07-18 부터 · 소연 화면 10/17 토 · 10/18 일) 을 따른다
_sun = _pa[("GEUMRYONG", "일요일 저녁 · 단품 (공식 예약 화면)")]
_gmo = {r["상품"]: r for r in _mn.Menu().by_venue["금룡"]}
_gdn = [_gmo[n] for n in ("삼선 자장면 · 저녁", "조리장 특선 볶음밥 (XO) · 저녁")]
_sell = lambda d: all(_mn.Menu().on_sale(r, d) for r in _gdn)
chk("금룡 단품 저녁 2줄 — 일 10/11 · 수 10/14 엔 팔고 토 10/10 · 한글날 (금) 10/9 엔 안 판다 = 가정표 '일요일 저녁 · 단품' (예약 화면 단품 세션 월~금 · 일)",
    _sun["값"] == "가능" and '"WEEK": "0,1,2,3,4,6"' in _sun["근거"]
    and _sell(date(2026, 10, 11)) and _sell(date(2026, 10, 14)) and not any(_mn.Menu().on_sale(r, d) for r in _gdn for d in (date(2026, 10, 10), date(2026, 10, 9))), True)

print("\n[10/15 · 운영 조건 확인 · 가정] 조식 '85분' 정정 · 원장 수량 단위 (진행 정리 10/16 소연 몫 · docs/운영조건_확인가정_1015.md)")
_pa = {(r["장소코드"], r["항목"]): r for r in V.load_place_assumptions()}
_bb = _pa[("THE_BUFFET", "조식 · 체류 (1부)")]
chk("더뷔페 조식 체류 (1부) = 모름 · 값 없음 · '착석 시각 없음' — blog42 의 06:30 은 방에서 나선 시각이라 85분으로 쓰지 않는다 (슬기님 원문 검수)",
    _bb["등급"] == "모름" and _bb["값"] == "" and "착석 시각 없음" in _bb["조건"] and "방에서 1층으로" in _bb["근거"], True)
# 원장 L4 결제 단가 = 상품표 단가 (위 [상품표 · 10/1]) 이므로 원장 수량은 상품표 단위로 센 것 — 럭스바는 L4 가 1잔 줄뿐
_lux_l4 = {o: v for (u, o), v in _onto.items() if u == "럭스바"}
_lux_rows = [r for r in _menu if r["업장"] == "럭스바" and r["원장상품"]]
chk(f"원장 럭스바 L4 {len(_lux_l4)}줄은 모두 상품표 '1잔' 줄에 이어지고 결제 단가 = 1잔 값 (원장 럭스바 수량 = 잔 수)",
    len(_lux_l4) >= 2 and set(_lux_l4) == {r["원장상품"] for r in _lux_rows}
    and all(r["단위"] == "1잔" and round(_lux_l4[r["원장상품"]]) == int(r["단가"]) for r in _lux_rows), True)

print()
if PENDING:
    print(f"보류 {len(PENDING)}건 — 팀 논점이 확정되면 기대를 확정한다")
    for p in PENDING:
        print(f"   · {p}")
    print()
if FAILURES:
    print(f"** 실패 {len(FAILURES)}건 **")
    for f in FAILURES:
        print(f"   - {f}")
    raise SystemExit(1)
print(f"전부 통과 · 등록된 운영 창 {len(WALKERHILL_VENUE_WINDOWS)}곳")
