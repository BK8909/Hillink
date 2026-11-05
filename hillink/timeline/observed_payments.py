"""원문 확인 추가 결제 원장. 예측 행동·TRUTH_*·월 매출과 합치지 않는다."""
from copy import deepcopy
from datetime import date
from math import isfinite
import re
from collections import defaultdict

from prices import net


def build_monthly_report(modules, month=None):
    """후기의 실제 결제 날짜로만 집계. 금액 미상/기록 없음은 0원이 아니다."""
    if month is not None:
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ValueError("월은 YYYY-MM 형식이어야 합니다")
        date.fromisoformat(month + "-01")
    rows, seen = [], set()
    for module in modules:
        report = build_report(module)
        for row in report["rows"]:
            if row["id"] in seen:
                raise ValueError("출처 간 동일 결제 ID 중복: " + row["id"])
            seen.add(row["id"])
            rows.append({**row, "source": report["source"]})
    available = sorted({r["date"][:7] for r in rows})
    selected = [r for r in rows if month is None or r["date"][:7] == month]

    def summarize(items):
        known = [r for r in items if r["krw"] is not None]
        return dict(observed_count=len(items), known_count=len(known),
                    unknown_count=len(items) - len(known),
                    known_subtotal_krw=sum(r["krw"] for r in known) if known else None,
                    known_subtotal_net=sum(r["net"] for r in known) if known else None,
                    unallocated_count=sum(r["l2"] is None for r in known),
                    all_priced=bool(items) and len(known) == len(items))

    groups = defaultdict(list)
    for row in selected:
        groups[row["date"][:7]].append(row)
    monthly = []
    for period, items in sorted(groups.items()):
        outlets = defaultdict(list)
        for row in items:
            outlets[(row["l2"], row["l3"])].append(row)
        monthly.append(dict(month=period, **summarize(items), outlets=[
            dict(l2=l2, l3=l3, **summarize(values))
            for (l2, l3), values in sorted(outlets.items(), key=lambda x: str(x[0]))]))
    return dict(scope="확보한 후기의 추가 결제만 · 실제 날짜 기준 · 호텔 전체 월 매출/예측 아님",
                selected_month=month, available_months=available, months=monthly,
                rows=selected, summary=summarize(selected), complete_stay_total=False,
                simulation_merged=False, no_records=not selected,
                vat_basis="순매출=확인 결제액/1.1은 모델 규칙. 실제 영수증 세금 구분 미확인")


def load_payment_sources(directory):
    """새 원장이 추가된 후기 파일도 발견. 새 프로세스에서 사용해 오래된 모듈 캐시를 피한다."""
    from pathlib import Path
    import importlib
    return [importlib.import_module(p.stem)
            for p in sorted(Path(directory).glob("persona_blog[0-9][0-9].py"))
            if "OBSERVED_PAYMENTS" in p.read_text(encoding="utf-8-sig")]


def build_report(module):
    rows = deepcopy(list(getattr(module, "OBSERVED_PAYMENTS", ())))
    seen = set()
    for row in rows:
        if row["id"] in seen:
            raise ValueError("동일 결제 ID 중복: " + row["id"])
        seen.add(row["id"])
        date.fromisoformat(row["date"])
        amount = row["krw"]
        if amount is not None and (
            isinstance(amount, bool) or not isinstance(amount, (int, float))
            or not isfinite(amount) or amount < 0
        ):
            raise ValueError("결제액은 유효한 비음수 또는 None이어야 합니다")
        row["payment_status"] = "금액 미확정" if amount is None else "후기 결제액 자기보고"
        row["net"] = None if amount is None else net(amount)
    known = [row for row in rows if row["krw"] is not None]
    return {
        "source": getattr(module, "SOURCE_ID", module.__name__.removeprefix("persona_")),
        "scope": "원문에서 확인한 추가 결제/주문만 · 전체 체류 매출 아님 · 예측 아님",
        "rows": rows,
        "known_payment_count": len(known),
        "unknown_payment_count": len(rows) - len(known),
        "known_subtotal_krw": sum(row["krw"] for row in known) if known else None,
        "known_subtotal_net": sum(row["net"] for row in known) if known else None,
        "known_unallocated_count": sum(row["l2"] is None for row in known),
        "listed_payments_all_priced": bool(rows) and len(known) == len(rows),
        "complete_stay_total": False,
        "vat_basis": "순매출은 기존 모델 규칙 결제액/1.1. 실제 영수증 세금 구분은 미확인",
    }
