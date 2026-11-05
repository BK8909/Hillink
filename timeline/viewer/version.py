"""계산 결과의 버전 (10/14) — 같은 날 · 같은 조정값이라도 코드나 입력 표가 바뀌면 다른 결과다.
캐시 키(날짜 · 행사 · 규모 · 조정값)에는 버전이 없으므로, 결과 파일에 model_ver · input_ver 를 적고
화면 · 서버가 지금 버전과 다르면 '이전 버전 결과' 로 표시하거나 다시 계산한다."""
from __future__ import annotations

import hashlib
from pathlib import Path

TL = Path(__file__).resolve().parent.parent
# 손님 생성 · 에이전트 선택 · 좌석 · 매출을 정하는 코드
MODEL_FILES = ["agent_v0.py", "agent_v1.py", "agent_v4.py", "generate.py", "revenue.py", "capacity.py", "menu.py", "prices.py",
               "walkerhill_timeline_validator.py", "trend.py", "signal_inputs.py", "viewer/engine.py"]
# 모델 입력 표 (가설표 · 출처표처럼 기록용 장부는 넣지 않는다)
INPUT_FILES = ["persona_grid.csv", "purpose_mix.csv", "type_mix.csv", "age_mix.csv", "date_factors.csv", "dining_pref.csv", "menu.csv",
               "day_visit_scenarios.json", "anomaly_scenarios.csv", "hypotheses.csv", "trend_signals.csv",
               "../docs/data/ontology_inverse_followup_shh_20261013/객실_온톨로지참고계수_31일.csv"]


def _hash(names):
    h = hashlib.sha1()
    for n in names:
        p = TL / n
        h.update(n.encode("utf-8"))
        h.update(p.read_bytes() if p.exists() else b"-")
    return h.hexdigest()[:8]


def model_ver() -> str:
    return _hash(MODEL_FILES)


def input_ver() -> str:
    return _hash(INPUT_FILES)
