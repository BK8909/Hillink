"""계산 항(why 라벨) → 고객 입력 칸 · 근거 층 — agent_v4.score_v4 · run_agent 의 add() 라벨을 코드에서 옮긴 표 (10/20 · 격리)

층(layer) — 판단 근거 여섯 층 중 계산 항이 기대는 입력의 층
  fact      고객 파일의 사실 칸(FACTS_EVIDENCE 등급으로 다시 관측 ◎ / 사람 추론 ○ / 추정 △ 를 가른다 — card.py)
  trait     성향 7개 — 자동 추출 값(사람 검수 없음). lam_trait 를 곱하는 항과 곱하지 않는 항을 나눠 적는다
  env       공용 모델의 고정 규칙 · 계수(THETA_FIT) · 운영 창 · 이동 시간 — 고객과 상관없는 시뮬레이션 가정
  knob      실험 조정값(기본 꺼짐) — 켜졌을 때만 나오는 항
표에 없는 라벨은 'unmapped' — tests 가 10팀 실행에서 0 건인지 본다(설명이 계산과 어긋나지 않게).
"""
from __future__ import annotations

import re

# (정규식, 입력 칸, 층, lam_trait 를 곱하나) — 위에서부터 먼저 맞는 것
TERM_RULES: list[tuple[re.Pattern, str, str, bool]] = [(re.compile(p), f, layer, lam) for p, f, layer, lam in [
    (r"^체크인 절차$", "procedure", "env", False),
    (r"^밤이라 취침$", "procedure", "env", False),
    (r"^입실 절차$", "procedure", "env", False),
    (r"^포장 음식 객실에서$", "procedure", "env", False),
    (r"^대기\(성향\)$", "trait:대기 회피", "trait", True),
    (r"^대기 \d+분$", "wait", "env", False),
    (r"^이동 \d+분$", "travel", "env", False),          # w_travel + 성향 '이동 최소화'×lam — 한 항으로 합쳐져 나온다
    (r"^(조식|중식|석식|간식) 예약 포함$", "fact:included_meals", "fact", False),
    (r"^포함 저녁 두고 다른 저녁$", "fact:included_meals", "fact", False),
    (r"^(조식|중식|석식|간식) 때 · 식당 밖$", "meal_other", "env", False),
    (r"^호텔 조식 두고 방에서$", "fact:is_guest", "fact", False),
    (r"^(조식|중식|석식|간식) 때$", "meal", "env", False),
    (r"^평일 저녁 호텔 식당 계획 없음$", "knob:wd_dine", "knob", False),
    (r"^객실에서 쉼$", "room_rest", "env", False),
    (r"^직전에도 객실$", "room_rest", "env", False),
    (r"^객실 체류 최소형$", "fact:room_minimal", "fact", False),
    (r"^격식$|^캐주얼$", "trait:격식 선호", "trait", True),
    (r"^아동 동반$|^아동 동반인데 격식 업장$", "fact:has_child_under_13", "fact", False),
    (r"^조망$", "trait:조망 중시", "trait", True),
    (r"^조용함$|^붐빔$", "trait:조용함 선호", "trait", True),
    (r"^함께 먹기$", "trait:함께 먹기 선호", "trait", True),
    (r"^이미 가 봄$|^처음$", "trait:새로움 추구", "trait", True),
    (r"^예약한 곳$", "fact:booked", "fact", False),
    (r"^가고 싶던 곳$", "fact:prefers", "fact", False),
    (r"^줄 대신 포장$", "trait:대기 회피", "trait", False),   # ← lam 을 곱하지 않는다(agent_v4.py score_v4 '줄 대신 포장')
    (r"^포장 기본 감점$", "knob:takeout_base", "knob", False),
    (r"^르파사쥬 구매 계획|^저녁 뒤 한잔 계획|^르파사쥬 구매 계획 없음$|^오늘 밤 바 계획 없음$", "knob:purpose", "knob", False),
    (r"^빈 시간 채우기", "gap_fill", "env", False),
]]


def classify(label: str) -> tuple[str, str, bool]:
    for rx, field, layer, lam in TERM_RULES:
        if rx.search(label):
            return field, layer, lam
    return "unmapped", "unmapped", False
