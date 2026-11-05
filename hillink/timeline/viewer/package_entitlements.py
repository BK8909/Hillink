"""Narrow, source-backed package context for continuous visit simulations.

Package selection is an operator scenario input, never evidence of a booking or
transaction. Unknown package prices and overage terms stay out of cash totals.
"""
from __future__ import annotations

from copy import deepcopy

SUPPORTED_SCOPES = {"per_visit", "per_room_per_night", "per_person", "per_room"}


PACKAGE_CATALOG = {
    "GRAND_SUNGSU_V2_2N": {
        "id": "GRAND_SUNGSU_V2_2N",
        "label": "두근두근 성수 Ver.2 · 2박",
        "building": "GRAND",
        "nights": 2,
        "party_size": 2,
        "qualification": "그랜드 워커힐 · 2박형 · 성인 2인 패키지 구성",
        "effective_from": "2026-05-18",
        "effective_to": "2026-12-31",
        "source": "timeline/menu.csv · Walkerhill Package/8797; PR #114 OP27B-05",
        "scenario_only": True,
        "transaction_status": "NOT_OBSERVED",
        "benefits": {
            "GRAND_SUNGSU_SAUNA": {
                "facility": "SAUNA",
                "scope": "per_visit",
                "limit": 1,
                "included_people": 2,
                "minimum_age": 17,
                "auto_charge": False,
                "source": "Walkerhill Package/8797; PR #114 OP27B-05: 1박·2박형 모두 사우나 1회 2인; PR #113 official facility catalog: minimum age 17",
            }
        },
    }
}


def get_package(package_id: str | None):
    package = PACKAGE_CATALOG.get(package_id) if package_id else None
    return deepcopy(package) if package else None


def initial_benefit_usage(package: dict | None) -> dict:
    if not package:
        return {}
    for rule in package["benefits"].values():
        if rule.get("scope") not in SUPPORTED_SCOPES:
            raise ValueError(f"unsupported package entitlement scope: {rule.get('scope')}")
    return {
        benefit_id: {
            "package_id": package_id,
            "facility": rule["facility"],
            "scope": rule["scope"],
            "limit": rule["limit"],
            "included_people": rule["included_people"],
            "used_count": 0,
            "remaining": rule["limit"],
            "status": "AVAILABLE",
            "used_dates": [],
            "auto_charge": False,
            "source": rule["source"],
        }
        for package_id, p in [(package["id"], package)]
        for benefit_id, rule in p["benefits"].items()
    }


def consume_benefit(usage: dict, benefit_id: str, service_date: str) -> bool:
    """Consume one included unit exactly once; return false when none remains."""
    if not usage:
        return False
    entry = usage.get(benefit_id)
    if not entry or entry.get("remaining", 0) <= 0:
        return False
    entry["used_count"] += 1
    entry["remaining"] -= 1
    entry["status"] = "USED" if entry["remaining"] == 0 else "AVAILABLE"
    if service_date not in entry["used_dates"]:
        entry["used_dates"].append(service_date)
    return True

