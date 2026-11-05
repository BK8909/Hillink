"""Private-only workbook normalization and exact-account/post deduplication.

No fuzzy author matching. URLs, accounts, titles, raw text and original hashes
in this return value belong in a restricted source ledger, never public exports.
"""
from hashlib import sha256
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

from .contract import opaque
from .intake import read_workbook


def source_identity(url):
    parsed = urlparse(url.strip())
    if parsed.hostname not in {"blog.naver.com", "m.blog.naver.com"}:
        raise ValueError("unsupported_source_identity_use_explicit_private_registry")
    parts = parsed.path.strip("/").split("/")
    query = parse_qs(parsed.query)
    if query.get("blogId") and query.get("logNo"):
        account,post = query["blogId"][0],query["logNo"][0]
    elif len(parts) == 2 and parts[1].isdigit():
        account,post = parts
    else:
        raise ValueError("source_author_post_identity_unresolved")
    if not re.fullmatch(r"[A-Za-z0-9_-]+",account) or not post.isdigit():
        raise ValueError("invalid_source_identity")
    return account.lower(),post


def normalize_workbooks(paths, author_aliases=None):
    """Resolve aliases from a PRIVATE registry; scope assignment remains explicit.

    Exact duplicate source rows are retained as locations but do not create extra
    posts, purchases or visits. Same source with differing text requires review.
    """
    author_aliases = author_aliases or {}
    if any(not opaque(value) for value in author_aliases.values()):
        raise ValueError("opaque_persona_aliases_required")
    if len(set(author_aliases.values())) != len(author_aliases):
        raise ValueError("different_accounts_require_separate_author_groups")
    documents, by_source, accounts, duplicate_rows = [],{}, {},0
    inventory=[]
    for supplied in paths:
        path = Path(supplied)
        workbook_count=0
        for sheet in read_workbook(path):
            for row in sheet["rows"]:
                cells=row["cells"]; number=row["excel_row"]
                def value(column):
                    return cells.get(f"{column}{number}",{}).get("value","")
                if sheet["sheet_name"] == "본문" and number >= 6:
                    url,text,title,published=value("F"),value("J"),value("E"),value("G")
                elif sheet["sheet_name"] == "링크와 본문" and number >= 5:
                    url,text,title,published=value("A"),value("B"),"",""
                else:
                    continue
                if not text.strip() or not url.strip():
                    continue
                account,source_post = source_identity(url)
                key=(account,source_post)
                workbook_count+=1
                location={"workbook":path.name,"sheet":sheet["sheet_name"],"excel_row":number}
                comparable=re.sub(r"\s+"," ",text).strip()
                if key in by_source:
                    previous=by_source[key]
                    if previous["normalized_text_private"] != comparable:
                        raise ValueError("same_source_different_body_requires_version_review")
                    previous["source_locations_private"].append(location)
                    duplicate_rows+=1
                    continue
                if account not in accounts:
                    accounts[account]=author_aliases.get(account,f"AUTHOR_{len(accounts)+1}")
                    if len(set(accounts.values())) != len(accounts):
                        raise ValueError("author_alias_collision_requires_explicit_registry")
                document={"post_id":f"P{len(documents)+1:03}","persona_id":accounts[account],
                          "source_class":"authorized_text","scope":"scope_review_pending",
                          "text":text,"title":title or next((line.strip() for line in text.splitlines() if line.strip()),""),
                          "source_locations_private":[location],"url_private":url,"account_private":account,
                          "normalized_text_private":comparable,"source_sha256_private":sha256(text.encode()).hexdigest(),
                          "publication_date_unverified":published,"publication_is_not_visit_date":True,
                          "image_status":"image_not_collected_by_policy"}
                documents.append(document); by_source[key]=document
        inventory.append({"workbook":path.name,"body_rows":workbook_count})
    return {"documents_private":documents,"source_inventory":inventory,"body_row_count":sum(v["body_rows"] for v in inventory),
            "unique_post_count":len(documents),"duplicate_source_rows":duplicate_rows,"author_group_count":len(accounts),
            "visit_count":None,"visit_count_not_equal_post_count":True,"contains_private_source":True}
