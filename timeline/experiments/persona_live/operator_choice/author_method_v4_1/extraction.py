"""No-call source-aligned retrieval baseline plus long-context request contract.

Semantic analyst/model proposals and automatic windows are different layers.
This lexical baseline is not advertised as complete multi-document understanding.
"""
from __future__ import annotations
import re
from pathlib import Path

from .contract import normalize_facts

RULES = {
    "benefit_use": r"(?:할인|쿠폰|포인트|상품권|바우처|카드).{0,80}(?:받았|사용|활용|교환|주문|구매|정했다)",
    "novelty_trial": r"(?:궁금|호기심|처음|새로|한정|콜라보).{0,160}(?:주문|구매|예약|시켜|먹어|이용)",
    "food_exploration": r"(?:주문하였|주문했|먹었|먹어보|식사했|맛있게\s*먹|시켜봤)",
    "prepurchase_value": r"(?:구매|고르는|선택|예매).{0,80}(?:기준|전에는|미리)|(?:아까워서|부담스러워서|비싸서).{0,80}(?:패스|안\s*사|구매하진|아울렛)",
    "post_value_appraisal": r"가격\s*대비|값어치|할인.{0,40}해도|재구매\s*의사",
    "warm_water_rest": r"(?:온수|따뜻|족욕|자쿠지).{0,100}(?:좋|즐|최애|극락|지지)",
    "swimming_nonpreference": r"(?:물\s*무서|수영.{0,20}못|수영을\s*즐기나요.{0,15}아니오|물을\s*좋아하나요.{0,15}아니오)",
    "alcohol_experience": r"와인.{0,30}(?:짠|사왔|마셨)|와인\s*두\s*병",
    "low_alcohol_tolerance": r"알쓰|술을\s*못|줘도\s*못\s*먹는",
    "space_atmosphere": r"(?:뷰|야경|분위기|조망).{0,45}(?:좋|멋|만족|즐|감상)",
    "seasonal_promotion_response": r"(?:이벤트|증정|한정|축제|시즌).{0,120}(?:예매했|구매|주문|참여|먹었)",
    "recovery_service": r"(?:마사지|테라피|케어).{0,90}(?:이용하였|받았|받습|받아|받았|방문)",
    "practical_repeat_use": r"(?:20년\s*넘게|매년|늘\s*먹던|다시\s*재방문|다시\s*구매|자주가는)",
}
ACTION = re.compile(r"구매하였|구매했|구매한|주문하였|주문했|먹었|이용하였|다녀왔|예매했|참여했|마셨|예약했다|받았습니다")
OTHER = re.compile(r"지인들은|친구가.{0,20}(?:샀|구매)|일행분.{0,50}샀|추천한다면")


def automatic_draft(document):
    text = document["text"]
    proposals = []
    for feature, pattern in RULES.items():
        for number, match in enumerate(re.finditer(pattern, text, re.S)):
            start, end = max(0,match.start()-70), min(len(text),match.end()+100)
            snippet = text[start:end]
            kind = "preference" if feature in {"swimming_nonpreference","low_alcohol_tolerance"} else "appraisal" if feature == "post_value_appraisal" else "motive" if feature == "prepurchase_value" else "participation"
            if kind == "participation" and not ACTION.search(snippet) and feature not in {"warm_water_rest","space_atmosphere","alcohol_experience"}:
                continue
            # A window can retain cross-sentence context but still needs semantic review.
            stage = "participation_reported" if kind == "participation" else "not_applicable"
            dimension = "post_appraisal" if kind == "appraisal" else "prepurchase_criteria" if feature == "prepurchase_value" else "specific_preference" if kind == "preference" else "participation_history"
            proposals.append({"fact_id":f"{document['post_id']}_AUTO_{feature}_{number}", "experience_key":f"{document['post_id']}_AUTO_EVENT",
                              "feature_key":feature, "detail":snippet, "anchors":[{"span":[start,end],"quote":snippet}],
                              "kind":kind,"dimension":dimension,"actor":"other" if OTHER.search(snippet) else "author_inferred",
                              "time_scope":"source_experience", "action_stage":stage,
                              "polarity":"negative" if feature == "swimming_nonpreference" else "neutral", "confidence":"low",
                              "common_dimensions":[feature], "context_scope":"automatic_window_needs_semantic_review"})
    # Preserve unclassified action windows; not forced into a fixed trait vocabulary.
    for number, match in enumerate(ACTION.finditer(text)):
        if any(a["span"][0] <= match.start() < a["span"][1] for p in proposals for a in p["anchors"]):
            continue
        start,end = max(0,match.start()-60), min(len(text),match.end()+80)
        proposals.append({"fact_id":f"{document['post_id']}_OPEN_{number}","experience_key":f"{document['post_id']}_AUTO_EVENT",
                          "feature_key":f"{document['post_id']}_UNMAPPED_{number}", "detail":text[start:end],
                          "anchors":[{"span":[start,end],"quote":text[start:end]}],"kind":"participation","dimension":"participation_history",
                          "actor":"author_inferred","time_scope":"source_experience","action_stage":"participation_reported",
                          "polarity":"neutral","confidence":"low","common_dimensions":[],"context_scope":"unmapped_action_preserved_private"})
    result = normalize_facts(document, proposals)
    result["extraction_layer"] = "lexical_retrieval_not_final_semantic_facts"
    return result


def request(document):
    """Private request only: no provider and no original text written by this helper."""
    return {"prompt_version":"author_method_v4.1-prompt-0.1", "system":Path(__file__).with_name("EXTRACTION_PROMPT.md").read_text(),
            "input":{"post_id":document["post_id"],"title":document.get("title", ""),"full_text":document["text"]},
            "execution":"not_executed", "contains_private_source":True,
            "output_contract":"normalize_facts: open feature_key/detail, discourse anchors, action stages, context, common mapping in later pass"}
