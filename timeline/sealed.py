"""봉인 대기 — 정답 확인 2차의 시험용 후기 번호.

이 후기들은 에이전트를 한 번도 돌리지 않는다 (run_all · trait_sensitivity 가 건너뜀).
정답 확인이 끝나면 해시를 docs/시험용_후기_봉인_3.txt 에 먼저 커밋하고,
에이전트를 확정한 뒤 eval_heldout.py 로 **한 번만** 채점한다. 그 뒤에는 개발용으로 풀어 준다.
"""
SEALED_WAIT: frozenset[int] = frozenset()   # 봉인 3 (32·34·41·42·43·50·51·52·59·60·61) 은 9/29 한 번 채점 뒤 개발용으로 풀림. 다음 시험용은 3차에서 새로


import re as _re

def unusable(mod) -> bool:
    """정답 확인에서 `못 씀:` 으로 표시한 후기 (기사 · 홍보 · 직접 방문 아님). 채점 · 평균에서 뺀다."""
    return bool(_re.search(r"^\s*(\*\*)?못 씀", mod.__doc__ or "", _re.M))
