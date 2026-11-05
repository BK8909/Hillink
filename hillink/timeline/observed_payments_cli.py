"""후기 원문으로 확인한 추가 결제 집계 · 독립 실행 (10/16 PR #55 에서 revenue.py 밖으로 분리).

가상 손님의 시뮬레이션 매출(revenue.py)과 섞지 않는다. revenue.py 는 모델 버전 계산 대상이라,
관측 결제 처리 코드를 여기 두면 결제 집계를 고쳐도 모델 버전 · 기존 계산 캐시가 바뀌지 않는다.

  python3 observed_payments_cli.py --month all            # 실제 결제월별 집계 (전체)
  python3 observed_payments_cli.py --month 2025-03        # 한 달
  python3 observed_payments_cli.py --blog 5               # 후기 한 편의 추가 결제
  python3 observed_payments_cli.py --month all --output out.json
"""
import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from observed_payments import build_monthly_report, build_report, load_payment_sources  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="후기 원문 확인 추가 결제 집계 · 시뮬레이션 · 전체 체류 매출과 별도")
    ap.add_argument("--blog", type=int, help="후기 한 편(persona_blogNN)의 원문 확인 추가 결제")
    ap.add_argument("--month", help="실제 결제 연월로 자동 집계: YYYY-MM 또는 all")
    ap.add_argument("--output", type=Path, help="보고서를 별도 JSON 에도 저장")
    a = ap.parse_args(argv)
    if (a.blog is None) == (a.month is None):
        ap.error("--blog 또는 --month 중 하나만 사용하세요")
    if a.month is not None:
        try:
            report = build_monthly_report(load_payment_sources(HERE), None if a.month == "all" else a.month)
        except ValueError as exc:
            ap.error(str(exc))
    else:
        report = build_report(importlib.import_module(f"persona_blog{a.blog:02d}"))
    if a.output is not None:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
