"""Conservative extraction sandbox, synthetic-testable, never an approved profile.

No automatic age/personality inference, multi-visit merging, Gold generation or
production-tag rewrite. Output spans are candidate locators, not verified anchors.
"""
from __future__ import annotations

import re

SELF = re.compile(r"저희|저는|우리는|우리가|나는|내가|이번에|이번에는")
OTHER = re.compile(r"친구(?:는|가)|동료(?:는|가)|지인(?:은|이)|아이(?:는|가)|다른\s*(?:사람|가족)|옆\s*테이블")
PAST = re.compile(r"예전|지난\s*방문|지난번|과거|결혼\s*전")
CURRENT = re.compile(r"이번|오늘|지금")
PLANNED = re.compile(r"예정|계획|가려고|갈\s*거|다음에|다음엔")
RECOMMEND = re.compile(r"추천|가시면|가신다면|방문한다면|하기\s*좋|가족에게|친구에게")
FAIL = re.compile(r"못\s*(?:갔|가|했|들어)|포기|취소|생략")
ACTUAL = re.compile(r"다녀왔|방문했|갔|갔다|왔다|묵었|숙박했|투숙했|이용했|수영했|먹었")
WITH = re.compile(r"^\s*(?:와|과|랑|하고)|^\s*(?:동반|데리고)")
KIN = [
    ("partner", r"남자\s*친구|여자\s*친구|남친|여친|남편|아내|부부"),
    ("friends_family", r"친구네\s*가족"),
    ("family_group", r"가족\s*모임|가족들|식구"),
    ("child_reference", r"꼬마\s*친구|아이(?!스|템|디)(?:들)?|아기(?!자기)|자녀"),
    ("parents", r"부모님|엄마|아빠|어머니|아버지"),
    ("friends_or_colleagues", r"친구|동료|지인"),
]
SPORTS = re.compile(r"수영|골프|테니스|러닝|요가|피트니스|운동")
MOTIVE = re.compile(r"목적|위해|하러|치러|뛰러|출장으로")


def extract_candidates(text):
    units = []
    for number, match in enumerate(re.finditer(r"[^.!?\n]+[.!?]?", text)):
        sentence = match.group()
        actor = "mixed_or_unknown" if SELF.search(sentence) and OTHER.search(sentence) else "other_person" if OTHER.search(sentence) else "narrator_candidate" if SELF.search(sentence) else "unknown"
        time = "mixed_visits_requires_segmentation" if PAST.search(sentence) and CURRENT.search(sentence) else "past_visit" if PAST.search(sentence) else "source_visit" if CURRENT.search(sentence) else "unknown_visit"
        status = "recommended_or_general" if RECOMMEND.search(sentence) else "failed_not_used" if FAIL.search(sentence) else "planned_not_used" if PLANNED.search(sentence) else "actual_candidate" if ACTUAL.search(sentence) else "mention_only"
        remaining = sentence
        companions = []
        attached = False
        for label, pattern in KIN:
            rx = re.compile(pattern)
            if rx.search(remaining):
                companions.append(label)
                attached = attached or any(WITH.search(remaining[m.end():]) for m in rx.finditer(remaining))
                remaining = rx.sub(" " * 6, remaining)
        relation = "author_companion_candidate" if actor == "narrator_candidate" and attached and status == "actual_candidate" else "mentioned_people_not_confirmed_companions"
        sport = bool(SPORTS.search(sentence))
        purpose = "explicit_motive_candidate" if MOTIVE.search(sentence) and actor == "narrator_candidate" and status == "actual_candidate" else "activity_only_not_travel_purpose" if sport and status == "actual_candidate" else "unconfirmed_purpose"
        sports_motive = bool(re.search(r"(?:수영|골프|테니스|러닝|요가|운동)(?:을|를)?\s*(?:하기\s*위해|하러|치러|뛰러|목적으로)", sentence))
        target = "sports" if sports_motive else "rest" if re.search(r"휴식하러|쉬러|쉬기\s*위해", sentence) else "business" if "출장으로" in sentence else "unknown"
        if time == "mixed_visits_requires_segmentation":
            relation, purpose, target = "visit_segmentation_required", "unconfirmed_until_visit_segmentation", "unknown"
        units.append({"unit_id": f"SYN-U{number:03d}", "span": [match.start(), match.end()],
                      "actor_scope": actor, "visit_scope": time, "statement_status": status,
                      "companion_mentions": companions, "companion_assertion": relation,
                      "purpose_status": purpose, "sports_activity_mentioned": sport,
                      "purpose_target_candidate": target if purpose == "explicit_motive_candidate" else "unknown",
                      "sports_primary_purpose_candidate": target == "sports" and purpose == "explicit_motive_candidate",
                      "provenance": "automatic_draft", "human_review": "pending",
                      "usable_as_personal_fact": False, "original_anchor_verified": False,
                      "limitations": ["clause-local heuristic, not full coreference", "multi-visit claims require explicit review"]})
    return {"version": "scoped_extraction_sandbox_v1", "units": units,
            "raw_text_exported": False, "approved_card_generated": False}
