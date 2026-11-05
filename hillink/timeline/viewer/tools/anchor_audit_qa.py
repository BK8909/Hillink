"""CL-1025-36d — LP 원문 앵커 62건 사실별 대조(읽기 전용 · 비공개 출력). 원문 · 인용 · 계정 · URL 은 출력하지 않음(SHA · offset · 상태만).

  python3 tools/anchor_audit_qa.py <LP 첫5 번들>/personas --out <비공개 폴더>/CL36D_ANCHOR_62_FACT_AUDIT_PRIVATE.csv

원문 JSONL 은 고객마다 본문 칸 이름이 다르다(full_original_text_PRIVATE 또는 body) — 둘 다 읽는다.
CL-36C 는 앞의 칸만, CD-14C 는(수로 보아) 뒤의 칸만 읽어 23/39 · 39/23 으로 서로 반대가 나왔다.
상태: matching(구간 SHA = anchor_sha256) · true_mismatch(본문은 있으나 구간 SHA 다름) · missing_body(본문 없음)
"""
import collections, csv, hashlib, json, sys
from pathlib import Path

BODY_FIELDS = ("full_original_text_PRIVATE", "body")
h = lambda s: hashlib.sha256(s.encode()).hexdigest()


def audit(personas_dir):
    out = []
    for p in sorted(Path(personas_dir).glob("WH-*")):
        ft = [json.loads(l) for l in open(p / "private/private_original_fulltext.jsonl", encoding="utf-8")]
        bypost = collections.defaultdict(list)
        for x in ft:
            bypost[x["post_id"]].append(x)
        for f in json.loads((p / "private/fact_evidence_origins_PRIVATE.json").read_text(encoding="utf-8")):
            rows = bypost.get(f["post_id"], [])
            cand = [(k, x[k]) for x in rows for k in BODY_FIELDS if x.get(k)]
            st, field, body_ok = ("missing_body", "", None) if not cand else ("true_mismatch", cand[0][0], None)
            for k, t in cand:
                body_ok = h(t) == f["source_sha256"]
                if h(t[f["anchor_start"]:f["anchor_end"]]) == f["anchor_sha256"]:
                    st, field = "matching", k
                    break
            out.append(dict(fact_id=f["fact_id"], post_id=f["post_id"], body_field=field, source_body_sha256=f["source_sha256"], body_sha_match=body_ok,
                            anchor_start=f["anchor_start"], anchor_end=f["anchor_end"], anchor_sha256=f["anchor_sha256"],
                            quote_sha_eq_anchor=h(f["quote_PRIVATE"]) == f["anchor_sha256"], status=st, rows_for_post=len(rows)))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    res = audit(a[0])
    if "--out" in a:
        o = Path(a[a.index("--out") + 1])
        with open(o, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(res[0])); w.writeheader(); w.writerows(res)
    print(json.dumps(dict(n=len(res), status=collections.Counter(r["status"] for r in res), body_field=collections.Counter(r["body_field"] for r in res)), ensure_ascii=False))
