"""Isolated public-release policy. No private input, model calls or source deletion.

Also copied verbatim by library_release_patch into the historical 619 runtime.
Release allowance is NOT independent-evaluation eligibility or same-stay proof.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from urllib.parse import unquote, urlsplit, parse_qs

VERSION = "sealed_overlap_public_release_v1"
BLOCKED = frozenset({"REV-bea98b3d8f343905fd1f", "REV-43526bdbea049cbe0963"})
PRIVATE_KEYS = frozenset({"author_key", "author_hash", "author_id", "author_name",
                          "url", "canonical_url", "source_url", "body", "raw_body"})
_DROP = object()


def identity(row):
    return row.get("review_id") or row.get("source_id") or row.get("id")


def held_ids(metadata=None):
    """Conservative relationship quarantine, NOT a verdict that visits are equal."""
    rows = (metadata or {}).get("records", [])
    held = set(BLOCKED)
    # Keep author relationships private. Related records await split review.
    changed = True
    while changed:
        authors = {r.get("author_key") for r in rows if identity(r) in held and r.get("author_key")}
        extra = {identity(r) for r in rows if identity(r) and (
            (r.get("author_key") and r["author_key"] in authors) or
            any((identity(x) if isinstance(x, dict) else x) in held
                for x in r.get("author_series", []) + r.get("same_stay_candidates", [])))}
        changed = not extra <= held
        held.update(extra)
    return held


def _clean(value, held):
    if isinstance(value, str):
        if value.startswith("acct:") or any(i in value for i in held):
            return _DROP
        return value
    if isinstance(value, list):
        return [out for item in value if (out := _clean(item, held)) is not _DROP]
    if isinstance(value, dict):
        if identity(value) in held:
            return _DROP
        out = {}
        for key, item in value.items():
            if key in PRIVATE_KEYS or any(i in str(key) for i in held):
                continue
            clean = _clean(item, held)
            if clean is not _DROP:
                out[key] = clean
        # Preserve the shape of legacy customer links without their account hash.
        if "customer_key" in value and "customer_key" not in out:
            out["customer_key"] = None
        return out
    return deepcopy(value)


def public_metadata(meta):
    held = held_ids(meta)
    out = _clean(meta, held)
    if "counts" in out:
        out["source_counts"] = out.pop("counts")
    out["release"] = {"policy": VERSION, "records": len(out.get("records", [])),
                      "held_records": len(meta.get("records", [])) - len(out.get("records", [])),
                      "source_counts_are_not_release_denominators": True}
    return out


def public_detail(detail, metadata=None):
    return _clean(detail, held_ids(metadata))


def public_library(library, metadata=None):
    out = _clean(library, held_ids(metadata))
    items = out.get("items", [])
    for item in items:
        item.setdefault("customer_key", None)
    counts = out.setdefault("counts", {})
    counts.update(total=len(items), ready=sum(bool(i.get("ready")) for i in items),
                  blog=sum(i.get("source_kind") != "sns" for i in items),
                  sns=sum(i.get("source_kind") == "sns" for i in items),
                  review=sum(i.get("source_kind") == "review" for i in items),
                  legacy=sum(i.get("source_kind") != "review" for i in items),
                  customer_keys=len({i["customer_key"] for i in items if i.get("customer_key")}),
                  no_customer_key=sum(not i.get("customer_key") for i in items))
    counts["by_stage"] = {str(k): sum(str(i.get("stage")) == str(k) for i in items)
                          for k in out.get("stages", {})}
    counts["authors_multi"] = sum(i.get("source_kind") == "review" and i.get("author_post_count", 0) > 1 for i in items)
    out["facets"] = {g: sorted({t["label"] for i in items for t in i.get("tags", []) if t["group"] == g})
                     for g in out.get("groups", [])}
    out["release_policy"] = VERSION
    return out


def public_html(html, metadata=None):
    """Sanitize the existing embedded DATA, without altering UI structure/design.

    Fail closed if a library page no longer has the expected JSON-only marker.
    This is defense in depth for stale HTML; static publication must regenerate it.
    """
    match = re.search(r"\bconst DATA\s*=\s*", html)
    if not match:
        raise ValueError("embedded_DATA_marker_missing")
    data, length = json.JSONDecoder().raw_decode(html[match.end():])
    if "library" not in data:
        raise ValueError("embedded_library_missing")
    data["library"] = public_library(data["library"], metadata)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return html[:match.end()] + payload + html[match.end() + length:]


def json_route(path, library, detail, metadata):
    """Return (status, JSON) for controlled endpoints, else None for normal routes.

    The old UI downloads /library_detail.json in full; sanitize that file too.
    Direct IDs are resolved exclusively against the sanitized detail allowlist.
    """
    url = urlsplit(path)
    route = unquote(url.path)
    if route == "/library.json":
        return 200, public_library(library, metadata)
    if route == "/reviews_meta.json":
        return 200, public_metadata(metadata)
    if route == "/library_detail.json" or route.startswith("/library_detail/"):
        safe = public_detail(detail, metadata)
        query = parse_qs(url.query)
        ids = query.get("id", [])
        if route.startswith("/library_detail/"):
            ids = [route[len("/library_detail/"):]]
        if not ids:
            return (400, {"error": "invalid_query"}) if url.query else (200, safe)
        if len(ids) != 1 or ids[0] not in safe:
            return 404, {"error": "not_found"}
        return 200, safe[ids[0]]
    return None
