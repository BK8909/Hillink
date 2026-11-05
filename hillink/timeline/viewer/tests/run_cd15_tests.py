"""CD-1024-15 원본 시험(tests/test_cd15.py)을 이 저장소 경로로 돌린다 — 원본 파일은 고치지 않음 (CL-1024-17).
  python3 tests/run_cd15_tests.py
  · 엔진 · 로컬 프로필 경로만 opx_run 과 같은 방식으로 바꿔 끼움.
  · test_customer_winners_and_scores_match_cd14_rows 는 Mac 의 CD-14 결과 CSV 가 있어야 함 → 없으면 건너뜀(이유 출력).
"""
import importlib.util, sys, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import opx_run  # noqa: E402
S = opx_run._service()
spec = importlib.util.spec_from_file_location("test_cd15", opx_run.CD15 / "tests" / "test_cd15.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
cd14 = Path("/private/tmp/hillink-cd1024-14-private-20261024/results/verified_and_scenario_customer_results.csv")
if not cd14.exists():
    T.CD15Tests.test_customer_winners_and_scores_match_cd14_rows = unittest.skip("CD-14 결과 CSV 는 Mac 전용 — opx 결과를 CD-15 discount_*.json 과 직접 대조해 대신 확인")(T.CD15Tests.test_customer_winners_and_scores_match_cd14_rows)
r = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(T.CD15Tests))
sys.exit(0 if r.wasSuccessful() else 1)
