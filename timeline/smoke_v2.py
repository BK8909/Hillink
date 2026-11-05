"""
v2 가 새 출발 조건 셋에서 도는지 — 정합성만 본다. 일치율은 팀원 페르소나가 오면 run_all.py.
페르소나 값은 임시(성향 전부 미상)라 여기 숫자에 의미를 두지 않는다.
"""
from datetime import datetime, time
from agent_v0 import Persona, TRAITS
import agent_v2
from walkerhill_timeline_validator import validate_walkerhill_timeline
from match import visits_from_segments

unknown = {t: None for t in TRAITS}
cases = [
    Persona("임시 · 비스타 1박 · 성인 3", unknown, party_size=3, nights=1, property="VISTA"),
    Persona("임시 · 더글라스 1박 · 친구 4", unknown, party_size=4, nights=1, property="DOUGLAS"),
    Persona("임시 · 클럽스위트 1박 · 2인", unknown, party_size=2, nights=1, property="GRAND", club_access=True),
    Persona("임시 · 리버파크 비투숙 · 2023-08-05", unknown, party_size=2, is_guest=False, depart_by=time(16, 0)),
]
starts = [datetime(2025,3,9,14,0), datetime(2024,6,15,14,40), datetime(2025,4,15,15,0), datetime(2023,8,5,9,30)]
for p, s in zip(cases, starts):
    segs, _ = agent_v2.run_agent(p, s, verbose=False)
    r = validate_walkerhill_timeline(segs, enforce_stay_day=p.is_guest, nights=p.nights)
    path = [v.place for v in visits_from_segments(segs)]
    print(f"{p.name:28s} {'PASS' if r.ok else [v.code for v in r.violations]}  {' → '.join(path)}")
