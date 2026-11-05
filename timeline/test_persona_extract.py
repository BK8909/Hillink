"""persona_extract 검사 — LLM 없이 돌아가는 부분만.

  python3 -m pytest -q test_persona_extract.py      (pytest 없으면 python3 test_persona_extract.py)
"""

from __future__ import annotations

import copy

import persona_extract as pe

BASE = {
    "name": "blog99 · 시험",
    "facts": {
        "property": "VISTA", "is_guest": True, "nights": 1, "party_size": 2,
        "has_child_under_13": False, "club_access": False, "included_meals": [], "booked": [],
        "evidence": {"property": "◎ 비스타 1박", "nights": "◎ 1박", "party": "◎ 둘이 · 13세 미만 아이 언급 없음"},
    },
    "traits": {k: {"value": None, "evidence": "근거 없음 → 미상"} for k in pe.TRAITS},
    "truth": {"visited": {"VISTA_ROOM": "◎ 체크인 후 객실", "PIZZA_HILL": "◎ 저녁을 먹음"},
              "not_visited": {}, "meals": [["석식", "PIZZA_HILL", "◎"]], "order_pairs": []},
}


def issues(mut=None):
    d = copy.deepcopy(BASE)
    if mut:
        mut(d)
    return pe.check(d)


def test_base_passes():
    assert issues() == []


def test_trait_scale_is_sulgi_standard():
    def m(d):
        d["traits"]["조망 중시"] = {"value": 0.65, "evidence": "◎ 리버뷰"}
    assert any("눈금" in i for i in issues(m))


def test_trait_without_reason_is_blocked():
    def m(d):
        d["traits"]["새로움 추구"] = {"value": 0.75, "evidence": "수영장에 갔다"}
    assert any("◎/○" in i for i in issues(m))


def test_mentioned_only_place_is_blocked():
    """blog02 자동 추출: 언급만 한 곳이 방문지에 들어가 30곳이 됨"""
    def m(d):
        d["truth"]["visited"]["SKYARD"] = "○ 언급 없음"
    assert any(i.startswith("방문: SKYARD") for i in issues(m))


def test_real_visit_with_word_recommend_passes():
    """'추천' · '안내' 는 실제 이용 문장에도 나온다 (blog16 족욕)"""
    def m(d):
        d["truth"]["visited"]["SKYARD"] = "◎ 족욕 추천 · 발이 매끈해짐"
    assert issues(m) == []


def test_too_many_visited():
    def m(d):
        d["truth"]["visited"] = {c: "◎ 이용" for c in sorted(pe.place_codes())[:20]}
    assert any("곳 —" in i for i in issues(m))


def test_fact_evidence_required():
    def m(d):
        d["facts"]["evidence"].pop("property")
    assert any("property 근거" in i for i in issues(m))


def test_under13_label_is_not_age():
    assert not any("나이" in i for i in issues())


def test_stated_time_kept_without_date():
    """blog16: 날짜 없이 '14시 20분쯤 도착' — 예전 스키마(start_at)는 null 이 돼 14:30 으로 떨어졌다"""
    line = pe.start_at_line({"start_date": None, "start_time": "14:20", "start_time_source": "◎"}, "20260830")
    assert "datetime(2026, 8, 30, 14, 20)" in line and "시각 ◎" in line and "날짜 △ 글 작성일" in line


def test_postdate_fills_date_not_2025():
    """날짜가 없으면 글 작성일 — 2025-01-01 은 계절 시설이 닫힌 날 (소연)"""
    assert "datetime(2026, 9, 8, 14, 30)" in pe.start_at_line({}, "20260908")
    assert "datetime(2025, 1, 1, 14, 30)" in pe.start_at_line({})


def test_stated_date_beats_postdate():
    line = pe.start_at_line({"start_date": "2026-08-31", "start_time": "13:30", "start_time_source": "△"}, "20260907")
    assert "datetime(2026, 8, 31, 13, 30)" in line and "날짜 ◎" in line and "시각 △" in line


def test_old_schema_json_still_reads():
    assert "datetime(2026, 8, 31, 13, 30)" in pe.start_at_line({"start_at": "2026-08-31T13:30", "start_at_source": "△"})


def test_prompt_carries_postdate_but_not_as_visit_date():
    s = pe.build_prompt("본문", "20260830")
    assert "글 작성일: 2026-08-30" in s and "start_date 에 옮겨 적지 않는다" in s
    assert "## 글 작성일" not in pe.build_prompt("본문")


def test_stated_times_warns_on_arrival_not_notice():
    assert pe.stated_times("회사 조퇴하고 14시 20분쯤 로비에 도착했는데")
    assert not pe.stated_times("체크인은 15시부터 가능합니다")


def test_nonguest_default_is_before_the_meal():
    """blog22: 비투숙 런치 후기가 14:30 도착으로 떨어져 런치가 끝난 뒤였다 (한호)"""
    d = {"facts": {"is_guest": False}, "truth": {"meals": [["중식", "THE_BUFFET", "◎"]]}}
    assert "datetime(2026, 9, 9, 11, 30)" in pe.start_at_line(d, "20260909")
    d["truth"]["meals"] = [["석식", "PIZZA_HILL", "◎"]]
    assert ", 17, 30)" in pe.start_at_line(d)
    assert ", 14, 30)" in pe.start_at_line({"facts": {"is_guest": True}})


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); n += 1
    print(f"{n} passed")
