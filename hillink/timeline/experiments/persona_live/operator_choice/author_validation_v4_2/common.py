"""Shared identities and immutable content fingerprints, private unless projected."""
from hashlib import sha256
import json

from ..author_method_v4_1.contract import opaque


def digest(value):
    encoded=value.encode() if isinstance(value,str) else json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()
    return sha256(encoded).hexdigest()


def require_opaque(value):
    if not opaque(value):
        raise ValueError("opaque_alias_required")
    return value


def require_corpus(documents):
    if not documents or len({d["post_id"] for d in documents}) != len(documents):
        raise ValueError("nonempty_unique_post_corpus_required")
    if len({d["persona_id"] for d in documents}) != 1:
        raise ValueError("one_explicit_author_group_required")
    for document in documents:
        require_opaque(document["post_id"]); require_opaque(document["persona_id"])
        if document.get("source_class") not in {"authorized_text","synthetic_fixture"}:
            raise ValueError("raw_authorized_source_required_not_cards_or_answers")
        if not isinstance(document.get("text"),str) or not document["text"].strip():
            raise ValueError("full_text_required_no_title_only_profile")
        if document.get("scope") not in {"walkerhill","related","recent"}:
            raise ValueError("explicit_scope_assignment_required")
    if len({d["source_class"] for d in documents}) != 1:
        raise ValueError("real_and_synthetic_corpus_must_not_mix")


def private_document(document):
    """Allowlist prevents caller-added Gold, answers and evaluator fields passing."""
    return {"persona_id":document["persona_id"],"post_id":document["post_id"],
            "scope":document["scope"],"title":document.get("title",""),"full_text":document["text"]}
