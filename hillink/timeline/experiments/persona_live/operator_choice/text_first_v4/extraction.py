"""A: full-text draft proposals + exact-span normalization. Never exports raw text.

The keyword bootstrap is a reproducible baseline, NOT a full semantic extractor.
The same normalizer accepts separately approved model/human extraction proposals.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import jsonschema

from . import VERSION

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / "statement.schema.json").read_text())
DIMENSIONS = {"positive_mention": "specific_preference", "participation": "participation_history",
              "purchase": "participation_history", "explicit_motive": "new_experience_trial",
              "appraisal": "post_appraisal", "specific_preference": "specific_preference",
              "revisit": "revisit_expression", "decline": "participation_history",
              "prepurchase_information": "prepurchase_criteria"}
MEDIA = {"image_not_collected_by_policy", "image_unavailable", "selected_image_available"}
ACTUAL = re.compile(r"이용했|참여했|다녀왔|방문했|먹었|마셨|숙박했|투숙했|식사했|사용했|쉬었다|갔다|샀다|구매했|결제했|주문했|예약했")
PARTICIPATION = re.compile(r"이용했|참여했|다녀왔|방문했|먹었|마셨|숙박했|투숙했|식사했|사용했|쉬었다|갔다")
BUY = re.compile(r"샀다|구매했|결제했|주문했|예약했|지불했|지출했")
FAIL = re.compile(r"포기했|취소했|이용하지 않았|참여하지 않았|먹지 않았|마시지 않았|구매하지 않았|구매 안|못 갔|하지 못했")
FUTURE = re.compile(r"예정|할 계획|가려고|다음에.{0,12}(?:갈|가볼)|방문할 것")
RECOMMEND = re.compile(r"추천합니다|추천해요|방문하세요|가보세요|이용해보세요")
OTHER = re.compile(r"친구는|지인은|동료가|다른 사람|옆 테이블|방문객들은|이용객들은")
SELF = re.compile(r"저는|나는|내가|우리는|저희|직접|내 돈")
SENTENCES = re.compile(r"(?:[^.!?\n]|\.(?=\d))+[.!?]?")
MONEY = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(만\s*원|원)")


def money_values(text):
    return [int(float(m.group(1).replace(",", "")) * (10000 if "만" in m.group(2) else 1)) for m in MONEY.finditer(text)]


def advertising_status(text):
    # Remove local denial phrases, not the whole document: another disclosure
    # elsewhere must still be detected. Denial itself does not prove independence.
    disclosure_text = re.sub(r"(?:유료\s*광고|협찬)(?:가|이|은|는)?\s*(?:아니|아님|없)|광고를\s*포함하지\s*않", "", text)
    disclosed = re.search(r"#협찬|협찬(?:을\s*)?받|유료\s*광고|광고를\s*포함|원고료|소정의\s*(?:대가|수수료)|제공받[아았]|제공\s*받[아았]|지원받[아았]|경제적\s*대가|paid partnership|sponsored", disclosure_text, re.I)
    commercial = [bool(re.search(p, text)) for p in (r"예약\s*문의", r"구매\s*링크|제휴\s*링크", r"최저가|특가\s*판매", r"할인\s*코드")]
    return {"status": "disclosed_sponsored" if disclosed else "promotional_signals" if sum(commercial) >= 2 else "no_signal_detected",
            "self_funded_claim": bool(re.search(r"내돈내산|내\s*돈으로", text)),
            "signal_count": int(bool(disclosed)) + sum(commercial),
            "verification": "heuristic_not_proof_of_sponsorship_or_independence",
            "human_review": "pending"}


def _document_errors(doc):
    errors = []
    for name in ("post_id", "author_group_id", "text", "source_class", "scope", "media_status", "author_link_status"):
        if name not in doc:
            errors.append("missing:" + name)
    if errors:
        return errors
    for name in ("post_id", "author_group_id"):
        if not isinstance(doc[name], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", doc[name]):
            errors.append("anonymous_id_required:" + name)
    if not isinstance(doc["text"], str) or not doc["text"].strip():
        errors.append("full_text_required")
    if doc["source_class"] not in {"synthetic_fixture", "authorized_text"}:
        errors.append("authorized_raw_text_required_not_card_or_sealed")
    if doc["scope"] not in {"walkerhill", "related", "recent"}:
        errors.append("invalid_scope")
    if doc["media_status"] not in MEDIA:
        errors.append("explicit_media_collection_status_required")
    if doc["author_link_status"] not in {"verified", "user_confirmed", "unconfirmed"}:
        errors.append("invalid_author_link_status")
    return errors


def normalize_post(doc, proposals, links=(), method="offline_regex_draft"):
    """No model execution. Exact spans checked against caller-supplied private text.

    Event/visit links are a separate reviewed registry, not a model's assumption.
    `confirmed` means caller-supplied linkage, not authenticated by this code.
    """
    errors = _document_errors(doc)
    if errors:
        raise ValueError(",".join(errors))
    link_index = {}
    for link in links:
        if link["post_id"] != doc["post_id"]:
            continue
        if not link.get("linkage_ref") or link.get("status") != "confirmed":
            raise ValueError("event_link_requires_confirmed_registry_reference")
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", link.get(k, "")) for k in ("event_id", "visit_id")):
            raise ValueError("anonymous_event_visit_id_required")
        key = tuple(link["span"])
        if key in link_index and link_index[key] != link:
            raise ValueError("conflicting_event_link")
        link_index[key] = link
    statements = []
    for proposal in proposals:
        if list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(proposal)):
            raise ValueError("statement_schema_invalid")
        start, end = proposal["span"]
        if not 0 <= start < end <= len(doc["text"]) or doc["text"][start:end] != proposal["quote"]:
            raise ValueError("source_span_quote_mismatch")
        for tag, pattern in (("wine", r"와인"), ("beer", r"맥주"), ("pizza", r"피자"), ("garlic", r"갈릭|마늘"), ("olive_oil", r"올리브오일")):
            if tag in proposal["tags"] and not re.search(pattern, proposal["quote"]):
                raise ValueError("specific_feature_requires_source_word:" + tag)
        if "nonalcoholic" in proposal["tags"] and set(proposal["tags"]) & {"wine", "beer"}:
            raise ValueError("split_alcoholic_and_nonalcoholic_claims_before_scoring")
        if proposal.get("amount_krw") is not None and proposal["amount_krw"] not in money_values(proposal["quote"]):
            raise ValueError("amount_not_in_source_span")
        stages = {"purchase": {"reservation_reported", "order_reported", "purchase_reported"},
                  "participation": {"participation_reported", "consumption_reported"}}
        if proposal["action_stage"] not in stages.get(proposal["kind"], {"not_applicable"}):
            raise ValueError("action_kind_and_stage_mismatch")
        link = link_index.get((start, end), {})
        row = {k: v for k, v in proposal.items() if k != "quote"}
        if proposal.get("amount_krw") is not None and "amount_kind" not in proposal:
            raise ValueError("amount_kind_required")
        dimension = DIMENSIONS[proposal["kind"]]
        if proposal["kind"] == "explicit_motive" and "new_trial" not in proposal["tags"]:
            dimension = "participation_history"
        row.update(evidence_id=f"{doc['post_id']}-S{start}-{end}-{proposal['kind']}",
                   dimension=dimension, event_id=link.get("event_id"), visit_id=link.get("visit_id"),
                   link_status="confirmed_registry" if link else "unresolved", review_status="pending",
                   source_alignment="exact_span_checked_not_semantic_verification")
        # Exact repeated excerpts can be deduplicated privately; never publish this key.
        row["private_content_fingerprint"] = hashlib.sha256(" ".join(proposal["quote"].split()).encode()).hexdigest()
        statements.append(row)
    if len({row["evidence_id"] for row in statements}) != len(statements):
        raise ValueError("duplicate_statement_reconcile_before_normalization")
    statements.sort(key=lambda row: (row["span"], row["kind"]))
    return {"version": VERSION, "stage": "A_post_extraction", "post_id": doc["post_id"], "author_group_id": doc["author_group_id"],
            "source_class": doc["source_class"], "scope": doc["scope"], "media_status": doc["media_status"],
            "author_link_status": doc["author_link_status"], "extraction_method": method,
            "private_source_sha256": hashlib.sha256(doc["text"].encode()).hexdigest(), "source_chars": len(doc["text"]),
            "advertising": advertising_status(doc["text"]), "statements": statements,
            "human_review": "pending", "model_calls": 0, "raw_text_exported": False}


def _tags(text):
    pairs = {"food": r"식사|맛|피자|페어링|뷔페|파인다이닝|레스토랑", "pizza": r"피자", "garlic": r"갈릭|마늘",
             "olive_oil": r"올리브오일", "space": r"조망|야경|한강뷰|리버뷰|공간", "atmosphere": r"분위기|야경",
             "seasonal_event": r"시즌|크리스마스|축제|팝업|페스티벌", "premium": r"파인다이닝|고급\s*식사",
             "pool": r"수영|물놀이", "rest": r"휴식|객실에서\s*쉬"}
    tags = [tag for tag, pattern in pairs.items() if re.search(pattern, text)]
    # Non-alcoholic alternatives neither establish alcohol familiarity nor dislike.
    if re.search(r"무알코올|논알코올|알코올\s*프리", text):
        tags.append("nonalcoholic")
    elif re.search(r"와인|맥주", text):
        tags.extend(tag for tag, pattern in (("wine", "와인"), ("beer", "맥주")) if re.search(pattern, text))
    if re.search(r"할인.{0,8}(?:받|사용|적용했)|바우처.{0,8}(?:썼|사용했)|쿠폰.{0,8}사용했", text):
        tags.append("discount_used")
    if re.search(r"처음|새로운|새로\s*(?:출시|나온)|처음\s*보는", text):
        tags.append("new_trial")
    if re.search(r"가격.{0,12}(?:비해|대비)|값어치|가성비|비쌌지만", text):
        tags.append("value_appraisal")
    return sorted(set(tags))


def _domain(text):
    for domain, pattern in (("dining", r"식사|피자|페어링|뷔페|파인다이닝|레스토랑"), ("shopping", r"상품|제품|샀다|쇼핑"),
                            ("event", r"행사|축제|시즌|크리스마스|팝업"), ("hotel", r"호텔|숙박|투숙|객실"),
                            ("leisure", r"수영|골프|족욕|운동"), ("travel", r"여행|관광")):
        if re.search(pattern, text):
            return domain
    return "other"


def draft_extract(doc, links=()):
    """Full text coverage, sentence-local rules; unresolved pronouns/irony need review."""
    errors = _document_errors(doc)
    if errors:
        raise ValueError(",".join(errors))
    proposals = []
    for match in SENTENCES.finditer(doc["text"]):
        text = match.group()
        actor = "other" if OTHER.search(text) else "author" if SELF.search(text) else "author_inferred"
        time = "recommendation" if RECOMMEND.search(text) else "future_plan" if FUTURE.search(text) else "past_experience" if re.search(r"지난번|예전에|작년", text) else "source_experience"
        if re.search(r"지난번|예전에|작년", text) and re.search(r"이번|오늘", text):
            time = "mixed_unresolved"
        tags, domain = _tags(text), _domain(text)
        positive = bool(re.search(r"좋아|좋았|만족|훌륭|마음에\s*들|값어치.{0,6}했", text))
        negative = bool(re.search(r"싫|불만|실망|맛없|부족|아쉬|평범|비쌌", text))
        kinds = []
        failed = bool(FAIL.search(text))
        if failed:
            kinds.append(("decline", "negative"))
        if PARTICIPATION.search(text) and not failed:
            kinds.append(("participation", "neutral"))
        if BUY.search(text) and not failed:
            kinds.append(("purchase", "neutral"))
        if re.search(r"궁금해서|경험해\s*보고\s*싶|먹어\s*보고\s*싶|위해서|하러", text):
            kinds.append(("explicit_motive", "neutral"))
        if re.search(r"좋아한다|좋아해서|제일\s*좋|선호|싫어한다|싫어해서", text):
            kinds.append(("specific_preference", "negative" if "싫" in text else "positive"))
        if positive or negative:
            kinds.append(("appraisal", "mixed" if positive and negative else "positive" if positive else "negative"))
        if positive and not ACTUAL.search(text):
            kinds.append(("positive_mention", "positive"))
        if re.search(r"재방문|다시\s*예약했|다시\s*구매했", text):
            kinds.append(("revisit", "negative" if re.search(r"안|않|없", text) else "positive"))
        if re.search(r"예약\s*전|구매\s*전", text) and re.search(r"비교했|확인했|살펴봤", text):
            kinds.append(("prepurchase_information", "neutral"))
        amounts = money_values(text)
        # More than one amount needs semantic role resolution, not first-number selection.
        amount_value = amounts[0] if len(amounts) == 1 else None
        contexts = [tag for tag, pattern in (("family", r"가족|자녀|아이와"), ("partner", r"남편|아내|남자친구|여자친구"),
                                             ("friends", r"친구와|친구랑"), ("solo", r"혼자"), ("business", r"출장")) if re.search(pattern, text)]
        for kind, polarity in kinds:
            proposal = {"span": [match.start(), match.end()], "quote": text, "kind": kind, "actor": actor,
                        "time_scope": time, "domain": domain, "tags": tags, "polarity": polarity,
                        "confidence": "high" if actor == "author" else "medium", "reasoning": "literal_action" if kind in {"participation", "purchase"} else "explicit_expression",
                        "context_tags": contexts or ["unknown"]}
            if kind == "purchase":
                proposal["action_stage"] = "reservation_reported" if "예약했" in text else "order_reported" if "주문했" in text else "purchase_reported"
            elif kind == "participation":
                proposal["action_stage"] = "consumption_reported" if re.search(r"먹었|마셨|식사했", text) else "participation_reported"
            else:
                proposal["action_stage"] = "not_applicable"
            if kind == "purchase" and amount_value is not None:
                # Reported paid text is valid evidence without a photo; not independent payment verification.
                proposal.update(amount_krw=amount_value, amount_kind="reported_paid" if re.search(r"결제했|지불했|지출했", text) else "order_amount" if re.search(r"주문했", text) else "unknown")
            proposals.append(proposal)
    return normalize_post(doc, proposals, links)


def build_extraction_request(doc):
    """Returns a PRIVATE execution input, never invokes a provider or writes it."""
    errors = _document_errors(doc)
    if errors:
        raise ValueError(",".join(errors))
    return {"system": (HERE / "EXTRACTION_PROMPT.md").read_text(), "output_schema": {"type": "array", "items": SCHEMA},
            "input": {"post_id": doc["post_id"], "text": doc["text"]}, "execution_status": "not_executed",
            "sharing": "restricted_contains_original_text", "model_calls": 0}


def chunk_requests(doc, max_chars=12000, overlap_chars=500):
    """Bounded input planning, not a tokenizer/cost estimate or provider adapter.

    Retains every character; overlap helps context but is not semantic guarantee.
    Per-chunk spans are rebased before final validation against the full source.
    """
    if type(max_chars) is not int or type(overlap_chars) is not int or not 0 <= overlap_chars < max_chars:
        raise ValueError("invalid_chunk_limits")
    if _document_errors(doc):
        raise ValueError("valid_source_document_required")
    result, start = [], 0
    while start < len(doc["text"]):
        end = min(start + max_chars, len(doc["text"]))
        fragment = dict(doc, text=doc["text"][start:end])
        request = build_extraction_request(fragment)
        request.update(chunk_id=f"{doc['post_id']}-C{len(result)}", source_span=[start, end], span_coordinate_system="chunk_local_then_rebase")
        result.append(request)
        if end == len(doc["text"]):
            break
        start = end - overlap_chars
    return result


def reconcile_chunk_proposals(doc, requests, outputs, links=()):
    if len(requests) != len(outputs):
        raise ValueError("every_chunk_output_required")
    proposals = {}
    covered = 0
    for request, rows in zip(requests, outputs):
        start, end = request["source_span"]
        if start > covered or not 0 <= start < end <= len(doc["text"]) or request["input"]["text"] != doc["text"][start:end]:
            raise ValueError("chunk_source_mismatch_or_missing_coverage")
        covered = max(covered, end)
        for row in rows:
            absolute = dict(row, span=[row["span"][0] + start, row["span"][1] + start])
            if not start <= absolute["span"][0] < absolute["span"][1] <= end:
                raise ValueError("chunk_local_span_outside_fragment")
            key = (tuple(absolute["span"]), absolute["kind"])
            if key in proposals and absolute != proposals[key]:
                raise ValueError("chunk_extraction_conflict_review_required")
            proposals[key] = absolute
    if covered != len(doc["text"]):
        raise ValueError("every_source_character_must_be_covered")
    return normalize_post(doc, list(proposals.values()), links, method="imported_chunk_proposals_not_executed_here")
