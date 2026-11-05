"""Invented test inputs only. Never substitutes for blog41 or other actual authors."""
from .extraction import SENTENCES


def document(author, post, text, scope="walkerhill", media="image_not_collected_by_policy"):
    return {"author_group_id": author, "post_id": post, "text": text, "source_class": "synthetic_fixture",
            "scope": scope, "media_status": media, "author_link_status": "verified"}


def link_post(doc, event, visit):
    return [{"post_id": doc["post_id"], "span": [m.start(), m.end()], "event_id": event, "visit_id": visit,
             "status": "confirmed", "linkage_ref": "SYNTHETIC_LINK_REGISTRY"} for m in SENTENCES.finditer(doc["text"])]


def four_author_corpora():
    definitions = {
        "SYN_FOOD": [("나는 처음 파인다이닝에서 29만원을 결제했다.", "walkerhill"),
                     ("나는 새로운 메뉴가 궁금해서 다른 호텔 레스토랑에서 식사했다. 나는 와인을 마셨다.", "related"),
                     ("나는 새로운 시즌 축제에 참여했다. 나는 투숙객 할인을 사용했다.", "recent")],
        "SYN_ROOM": [("나는 객실에서 쉬려고 호텔에 숙박했다.", "walkerhill"),
                     ("나는 다른 호텔 객실에서 쉬었다. 조용한 분위기가 좋았다.", "related"),
                     ("나는 무알코올 칵테일을 주문했다.", "recent")],
        "SYN_SHOP": [("나는 호텔에 숙박했다.", "walkerhill"),
                     ("나는 처음 보는 팝업 상품이 궁금해서 35만원을 결제했다.", "related"),
                     ("나는 새로운 제품을 직접 구매했다. 나는 쿠폰을 사용했다.", "recent")],
        "SYN_REVIEW": [("나는 피자를 주문했다. 가격에 비해 맛은 평범했다.", "walkerhill"),
                       ("나는 다른 레스토랑에서 식사했다. 비쌌지만 그만한 값어치를 했다.", "related"),
                       ("나는 예약 전에 메뉴를 비교했다. 나는 와인 행사에 참여했다.", "recent")],
    }
    result = {}
    for author, items in definitions.items():
        result[author] = []
        for i, (text, scope) in enumerate(items):
            doc = document(author, f"{author}_P{i}", text, scope)
            result[author].append((doc, link_post(doc, f"{author}_E{i}", f"{author}_V{i}")))
    return result
