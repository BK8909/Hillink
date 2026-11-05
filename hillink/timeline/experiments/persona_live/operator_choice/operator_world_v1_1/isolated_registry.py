"""Explicit private pilot input shared by parent and daily child processes."""
import hashlib
import json
import os
from pathlib import Path

CONTRACT = "hillink-isolated-intake-v1"

def _read(reference):
    supplied = Path(reference["path"])
    if not supplied.is_absolute():
        raise ValueError("isolated_input_absolute_path_required")
    path = supplied.resolve()
    if not path.is_absolute() or any((parent / ".git").exists() for parent in (path.parent, *path.parents)):
        raise ValueError("isolated_input_must_be_outside_git")
    try:
        raw = path.read_bytes()
    except OSError:
        raise ValueError("isolated_input_unreadable") from None
    if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise ValueError("isolated_input_sha_mismatch")
    return json.loads(raw)

def registrations():
    if os.environ.get("HILLINK_ISOLATED_CUSTOMERS") != "1":
        return {}
    path = os.environ.get("HILLINK_ISOLATED_REGISTRY")
    expected = os.environ.get("HILLINK_ISOLATED_REGISTRY_SHA256")
    if not path or not expected:
        raise ValueError("isolated_registry_reference_required")
    registry = _read({"path": path, "sha256": expected})
    if registry.get("contract_version") != CONTRACT:
        raise ValueError("unsupported_isolated_contract")
    out = {}
    for row in registry["customers"]:
        pid = row["customer_id"]
        if pid in out or row.get("approval_status") != "ISOLATED_PILOT_APPROVED":
            raise ValueError("isolated_approval_required")
        profile = _read(row["profile"])
        library = _read(row["library"])
        if library.get("id") != pid:
            raise ValueError("isolated_library_identity_mismatch")
        source = _read(row["source_import"])
        check = _read(row["product_check"])
        if profile.get("id") != pid or source["team_profile_private"]["STRUCTURED_PROFILE"]["persona_id"] != pid or check.get("persona") != pid:
            raise ValueError("isolated_customer_identity_mismatch")
        if source.get("structural_status") != "received_fields_and_source_links_checked_not_semantic_accuracy" or check.get("issues") != []:
            raise ValueError("isolated_intake_not_passed")
        out[pid] = (profile, {"customer_id": pid, "profile_sha256": row["profile"]["sha256"],
            "library_sha256": row["library"]["sha256"], "registry_sha256": expected, "contract_version": CONTRACT, "approval_status": row["approval_status"]})
    return out

def extend_profiles(base):
    extra = registrations()
    if set(base) & set(extra):
        raise ValueError("isolated_profile_must_not_override_existing_customer")
    return dict(base, **{pid: value[0] for pid, value in extra.items()})

def allowed_personas(base):
    extra = registrations()
    if set(base) & set(extra):
        raise ValueError("isolated_customer_must_not_override_default_registry")
    return set(base) | set(extra)

def lineage(ids):
    return {pid: value[1] for pid, value in registrations().items() if pid in ids}


def extend_library(base, protected_ids=()):
    extra = registrations()
    if set(protected_ids) & set(extra):
        raise ValueError("isolated_library_must_not_override_existing_customer")
    if not extra:
        return base
    registry = _read({"path": os.environ["HILLINK_ISOLATED_REGISTRY"], "sha256": os.environ["HILLINK_ISOLATED_REGISTRY_SHA256"]})
    return dict(base, **{row["customer_id"]: _read(row["library"]) for row in registry["customers"]})
