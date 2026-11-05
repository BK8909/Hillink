"""
수집한 후기 → 추출 대기열 — hillink 수집기(collect.py)와 이 저장소의 추출 · 정답 확인 · 봉인을 잇는 다리

hillink 의 채택 기준("행동 4개 + 시간 표현")은 한 편 안에서 선택을 앞뒤로 자르려고 만든 것이다.
여기서 필요한 건 다르다 — **워커힐 안에서 어디를 어떤 순서로 갔나** 를 정답으로 만들 수 있는 후기.
그래서 같은 원문을 이 저장소의 장소 목록(persona_extract.PLACE_NAMES)으로 다시 잰다.

  # 1) 대기열 만들기 — 원문은 읽기만. 결과는 원문 옆 data/queue/ (hillink 쪽, gitignore)
  python3 review_queue.py ~/Downloads/hillink-walkerhill-sim/data/raw

  # 2) 위에서 N 편을 추출용으로 내보내기 — data/queue/export/ 에 rNNN.txt + 추출 프롬프트
  python3 review_queue.py ~/Downloads/hillink-walkerhill-sim/data/raw --export 60 --no-sponsored

  # 이미 쓴 후기와 겹치는지 — 원문 텍스트가 있는 폴더를 주면 문장 겹침으로 잡는다
  python3 review_queue.py ... --known 이미_쓴_원문_폴더

등급
  A 체류형   투숙 신호 + 워커힐 장소 3곳 이상 + 시각 또는 순서 표현 (장소 2곳이어도 시각 · 순서가 5개 이상이면)
  B 목적형   비투숙으로 보이고 식당 · 전시 등 목적지가 이름으로 나옴 (blog09 · 13 · 14 같은 것)
  C 보류     장소가 1~2곳뿐이거나 순서가 없음 — 정답을 만들기 어렵다
  X 제외     hillink 가 이미 뺀 것 (워커힐 무관 · 연회 준비글 · 너무 짧음 · 오래됨) · 같은 계정 두 번째 글 · 이미 쓴 후기

규칙 (팀 데이터 규칙 그대로)
  - 원문 · 대기열 · 내보낸 텍스트는 전부 --out (저장소 밖). 이 스크립트는 저장소에 아무것도 안 쓴다
  - URL 은 내보낼 때 지운다 (원문 끝에 블로그 주소가 남아 있는 글이 있다)
  - 계정은 hillink 가 만든 해시만 쓴다. 같은 계정은 한 편만 — 한 사람이 표본을 끌고 가지 않게
  - 협찬 글은 빼지 않고 표시만 (행동 자체는 실제일 수 있다). 봉인 시험용으로는 협찬 아닌 글을 먼저
  - 개발용 / 시험용은 내보낼 때 키 해시로 정한다 (export_map.csv 의 split). 시험용은 정답 확인 · 봉인까지만 하고
    에이전트 결과를 보지 않는다
"""

from __future__ import annotations

import argparse, csv, json, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 원문에서 장소를 알아보는 이름들 → 장소 코드. 코드는 persona_extract.PLACE_NAMES 와 같다.
# 넓게 잡되, 한 글자 약칭처럼 오탐이 큰 건 넣지 않는다.
ALIASES: dict[str, str] = {
    r"발렛": "VALET_DESK",
    r"주차\s*타워|주차장": "PARKING_TOWER_B1",
    r"그랜드\s*(?:워커힐\s*)?(?:로비|프런트|프론트)": "GRAND_LOBBY",
    r"클럽\s*라운지|이그제큐티브\s*라운지": "GRAND_CLUB_LOUNGE",
    r"르\s*파사쥬|르파사주": "LE_PASSAGE",
    r"라이브러리": "GRAND_LIBRARY",
    r"실내\s*수영장|그랜드\s*수영장|인도어\s*풀": "GRAND_POOL",
    r"비스타\s*(?:워커힐\s*)?(?:로비|프런트|프론트)": "VISTA_LOBBY",
    r"비스타\s*(?:워커힐\s*)?(?:수영장|풀)|스카이\s*야드?\s*풀": "VISTA_POOL",
    r"더\s*뷔페|더뷔페": "THE_BUFFET",
    r"모에기": "MOEGI",
    r"스카이\s*야드|족욕": "SKYARD",
    r"피자\s*힐": "PIZZA_HILL",
    r"명월관": "MYONGWOLGWAN",
    r"온달": "ONDAL",
    r"금룡": "GEUMRYONG",
    r"파빌리온": "THE_PAVILION",
    r"럭스\s*바|LUX\s*바|룩스\s*바": "LUX_BAR",
    r"피트니스|헬스장": "FITNESS",
    r"사우나": "WELLNESS_SAUNA",
    r"포레스트\s*파크|산책로": "FOREST_PARK",
    r"리버\s*파크": "RIVERPARK",
    r"빛의\s*시어터": "THEATRE_OF_LIGHT",
    r"아트\s*샵": "THEATRE_ART_SHOP",
    r"편의점|CU": "CU_THEATRE",
    r"더글라스\s*(?:하우스\s*)?(?:로비)": "DOUGLAS_LOBBY",
    r"더글라스\s*(?:하우스\s*)?라운지|더글라스\s*아워": "DOUGLAS_LOUNGE",
    r"셔틀": "SHUTTLE",
    r"광나루역": "GWANGNARU_STN",
    r"강변역": "GANGBYEON_STN",
}
ALIAS_RE = [(re.compile(p), c) for p, c in ALIASES.items()]
DESTINATIONS = {"THE_BUFFET", "MOEGI", "PIZZA_HILL", "MYONGWOLGWAN", "ONDAL", "GEUMRYONG",
                "THE_PAVILION", "LUX_BAR", "THEATRE_OF_LIGHT", "RIVERPARK"}

STAY_RE = re.compile(r"체크\s*인|체크\s*아웃|[1-3]\s*박|호캉스|투숙|객실|룸\s*컨디션|숙박")
TIME_RE = re.compile(r"(?:오전|오후|새벽|아침|저녁|밤)?\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분|\s*반)?(?![간절대작])|\d{1,2}:\d{2}")
ORDER_RE = re.compile(r"그\s*다음|이후에?|먼저|마지막으로|이튿날|다음\s*날|둘째\s*날|체크인\s*(?:하고|후)|저녁\s*먹고|조식\s*먹고")
SPONSOR_RE = re.compile(r"협찬|제공\s*(?:을|를)?\s*받|지원\s*(?:을|를)?\s*받|원고료|소정의|체험단|서포터즈|대가를 받|무상 제공|제휴 링크|파트너스 활동|수수료를\s*(?:제공\s*)?받|초대(?:를)?\s*받")
# 표본 감사(20편, 2026-09-24)에서 나온 것: 판매 · 특가 글, 정보 · 기사글, 인천 '경원재 바이 워커힐'
EXP_RE = re.compile(r"다녀왔|다녀온|갔다|갔어|먹었|묵었|머물|체크인\s*했|이용했|했어요|했다")
AD_RE = re.compile(r"특가|최저가|판매|구매|쿠폰|할인\s*코드|링크|제휴|수수료|문의")
OTHER_RE = re.compile(r"경원재|앰배서더")
URL_RE = re.compile(r"https?://\S+|www\.\S+|blog\.naver\.com\S*")
ZW_RE = re.compile(r"[​‌‍﻿]")
PROPERTY_RE = {"DOUGLAS": re.compile(r"더글라스"), "VISTA": re.compile(r"비스타"),
               "GRAND": re.compile(r"그랜드\s*워커힐|그랜드워커힐")}

HILLINK_OUT = ("워커힐 무관", "워커힐 언급 없음", "연회", "너무 짧음", "오래됨")


# 본문 뒤 페이지 껍데기. hillink 의 clean_body 가 못 자른 변형이 300편 전부에 붙어 있었다 —
# 공감 · 댓글 버튼, 그리고 **다른 글 목록 JSON (블로그 아이디 · 닉네임 포함)**. 여기서 가장 먼저 나온 곳부터 자른다.
CHROME_MARKERS = ("저작자 명시 필수", "태그 취소 확인", "이 글에 공감한 블로거", "span.u_likeit_button",
                  "이 블로그 전체 카테고리", '[{"title"', "domainIdOrBlogId", "nicknameOrBlogId")
ID_RE = re.compile(r'"(?:domainIdOrBlogId|nicknameOrBlogId|blogId|logNo)"\s*:\s*"[^"]*"')


def clean(text: str) -> str:
    t = text or ""
    cut = min([i for i in (t.find(m) for m in CHROME_MARKERS) if i >= 0], default=len(t))
    t = ID_RE.sub(" ", t[:cut])
    t = ZW_RE.sub(" ", t)
    t = URL_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def _days(a: str | None, b: str | None) -> int:
    from datetime import datetime
    try:
        return abs((datetime.strptime(b, "%Y%m%d") - datetime.strptime(a, "%Y%m%d")).days)
    except (TypeError, ValueError):
        return 999


def shingles(t: str, n: int = 12) -> set[str]:
    t = re.sub(r"\s+", "", t)
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


def split_of(key: str) -> str:
    """개발용 / 시험용을 **내보낼 때** 정한다 — 에이전트를 돌려 보기 전에, 사람 손을 안 타게.
    키 해시로 정하니 누가 언제 돌려도 같다. 10편 중 3편꼴로 시험용."""
    import hashlib
    return "시험용" if int(hashlib.sha256(key.encode()).hexdigest(), 16) % 10 < 3 else "개발용"


def assess(key: str, d: dict) -> dict:
    text = clean(d.get("text", ""))
    places = sorted({c for r, c in ALIAS_RE if r.search(text)})
    wh_places = [p for p in places if p not in ("SHUTTLE", "GWANGNARU_STN", "GANGBYEON_STN", "PARKING_TOWER_B1")]
    stay = len(STAY_RE.findall(text))
    times = len(TIME_RE.findall(text))
    order = len(ORDER_RE.findall(text))
    props = [k for k, r in PROPERTY_RE.items() if r.search(text)]
    sponsored = bool(SPONSOR_RE.search(text))
    dest = [p for p in wh_places if p in DESTINATIONS]
    hv = d.get("verdict", "")

    if any(s in hv for s in HILLINK_OUT):
        tier, why = "X", "hillink · " + hv.replace("탈락 · ", "")
    elif OTHER_RE.search(text):
        tier, why = "X", "다른 지역 워커힐 브랜드"
    elif not EXP_RE.search(text):
        tier, why = "C", "직접 방문 서술 없음 (정보 · 기사 · 홍보)"
    elif len(AD_RE.findall(text)) / max(1, len(text)) * 1000 > 3:
        tier, why = "C", "판매 · 광고성"
    elif stay >= 2 and (len(wh_places) >= 3 and (times or order)
                        or len(wh_places) >= 2 and times + order >= 5):   # 클럽라운지 회차처럼 장소는 적어도 시각이 촘촘한 체류
        tier, why = "A", "체류형"
    elif stay < 2 and dest and (times or order or len(wh_places) >= 2):
        tier, why = "B", "목적형"
    else:
        tier, why = "C", f"장소 {len(wh_places)} · 시각 {times} · 순서 {order}"

    # 순위 — 정답을 만들 재료가 많은 순. 협찬은 뒤로
    score = 2 * len(wh_places) + min(times, 6) + min(order, 4) + (2 if stay >= 2 else 0) - (3 if sponsored else 0)
    return dict(key=key, tier=tier, why=why, score=score, account=d.get("blog_id_hash", ""),
                postdate=d.get("postdate", ""), property="/".join(props) or "?",
                guest="투숙" if stay >= 2 else "비투숙?", places=" ".join(wh_places), n_places=len(wh_places),
                times=times, order=order, sponsored="협찬" if sponsored else "", chars=len(text),
                dup="", _text=text)


def main() -> int:
    ap = argparse.ArgumentParser(description="수집한 후기 → 추출 대기열")
    ap.add_argument("raw", help="hillink data/raw 폴더 (원문 JSON)")
    ap.add_argument("--out", help="대기열 · 내보낸 텍스트를 둘 곳 — 반드시 저장소 밖. 기본: 원문 폴더 옆 queue/ "
                                  "(hillink 의 data/queue — 거기 .gitignore 에 들어 있음)")
    ap.add_argument("--known", help="이미 쓴 후기 원문 텍스트 폴더 (*.txt) — 겹치면 제외")
    ap.add_argument("--export", type=int, default=0, help="A · B 위에서 N 편을 rNNN.txt + 프롬프트로")
    ap.add_argument("--tiers", default="AB", help="내보낼 등급 (기본 AB)")
    ap.add_argument("--no-sponsored", action="store_true", help="협찬 글은 내보내지 않음 (봉인 시험용)")
    ap.add_argument("--rebuild-prompts", action="store_true",
                    help="이미 내보낸 rNNN_prompt.txt 를 지금 추출기 프롬프트로 다시 씀 (원문 · 번호 · 나눔은 그대로)")
    args = ap.parse_args()

    raw = Path(args.raw).expanduser()
    out = Path(args.out).expanduser() if args.out else raw.parent / "queue"
    repo = HERE.parent.resolve()
    if repo in out.resolve().parents or out.resolve() == repo:
        sys.exit(f"❌ --out 이 저장소 안입니다 ({out}). 원문이 섞일 수 있어 저장소 밖으로 지정하세요.")
    files = sorted(raw.glob("*.json"))
    if not files:
        sys.exit(f"❌ {raw} 에 원문 JSON 이 없습니다. hillink 에서 make collect 를 먼저.")

    # 연재 합치기 — 한 번의 투숙을 여러 글로 나눠 쓰는 블로거가 많다 (2박 3일을 여섯 편으로).
    # 같은 계정 · 게시일 간격 10일 이내 글은 한 체류로 보고 날짜순으로 이어 붙인다.
    # 빼면 가장 자세한 후기부터 잘려 나간다.
    posts = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("text"):
            posts.append((f.stem, d))
    by_acc: dict[str, list] = {}
    rows = []
    for key, d in posts:
        if any(s in d.get("verdict", "") for s in HILLINK_OUT) or not d.get("blog_id_hash"):
            rows.append(assess(key, d))
        else:
            by_acc.setdefault(d["blog_id_hash"], []).append((key, d))
    for acc, items in by_acc.items():
        items.sort(key=lambda kd: kd[1].get("postdate", ""))
        cluster = [items[0]]
        for kd in items[1:] + [None]:
            if kd and _days(cluster[-1][1].get("postdate"), kd[1].get("postdate")) <= 10:
                cluster.append(kd)
                continue
            if len(cluster) == 1:
                rows.append(assess(*cluster[0]))
            else:
                merged = dict(cluster[0][1])
                merged["text"] = "\n\n[다음 글]\n\n".join(clean(c[1]["text"]) for c in cluster)  # 글마다 껍데기를 먼저 자른다
                r = assess("+".join(c[0] for c in cluster), merged)
                r["why"] += f" · 연재 {len(cluster)}편 합침"
                rows.append(r)
            cluster = [kd] if kd else []

    # 이미 쓴 후기와 겹침
    if args.known:
        known = {p.stem: shingles(clean(p.read_text(encoding="utf-8", errors="ignore")))
                 for p in Path(args.known).expanduser().glob("*.txt")}
        for r in rows:
            s = shingles(r["_text"])
            for name, ks in known.items():
                if s and ks and len(s & ks) / min(len(s), len(ks)) > 0.3:
                    r["dup"] = name
                    r["tier"], r["why"] = "X", f"이미 씀 ({name})"
                    break

    # 같은 계정은 한 편만 — 점수 높은 글을 남긴다
    best: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: (r["tier"] == "X", -r["score"])):
        if r["tier"] == "X" or not r["account"]:
            continue
        if r["account"] in best:
            r["tier"], r["why"] = "X", "같은 계정 다른 체류 (한 사람 한 편)"
        else:
            best[r["account"]] = r

    rows.sort(key=lambda r: ("ABCX".index(r["tier"]), -r["score"]))
    out.mkdir(parents=True, exist_ok=True)
    cols = ["tier", "why", "score", "key", "postdate", "property", "guest", "n_places", "places",
            "times", "order", "sponsored", "chars"]
    with open(out / "queue.csv", "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    n = Counter(r["tier"] for r in rows)
    print(f"원문 {len(rows)}편 → A 체류형 {n['A']} · B 목적형 {n['B']} · C 보류 {n['C']} · X 제외 {n['X']}")
    xs = Counter(r["why"] for r in rows if r["tier"] == "X")
    for why, k in xs.most_common():
        print(f"    X {why:28s} {k}")
    ab = [r for r in rows if r["tier"] in "AB"]
    if ab:
        print(f"  A · B 협찬 {sum(1 for r in ab if r['sponsored'])}편 · "
              f"건물 {dict(Counter(r['property'] for r in ab))}")
    print(f"  → {out / 'queue.csv'}  (원문 없음 · 키 · 등급 · 장소 코드만)")

    if args.export:
        sys.path.insert(0, str(HERE))
        from persona_extract import build_prompt
        pick = [r for r in rows if r["tier"] in args.tiers and not (args.no_sponsored and r["sponsored"])][: args.export]
        ex = out / "export"
        ex.mkdir(exist_ok=True)
        done = {p.stem for p in ex.glob("r*.txt") if re.fullmatch(r"r\d{3}", p.stem)}   # _prompt.txt 는 세지 않음
        idx = len(done)
        mapping = out / "export_map.csv"
        new = not mapping.exists()
        header = ["export", "key", "tier", "split", "property", "guest", "places", "postdate"]
        old_rows = [] if new else list(csv.reader(open(mapping, encoding="utf-8-sig")))
        if old_rows and "postdate" not in old_rows[0]:
            # 예전 대응표(postdate 칸 없음) → 칸을 붙여 다시 쓴다. 번호 · 개발/시험 나눔은 그대로
            pd = {r["key"]: r["postdate"] for r in rows}
            with open(mapping, "w", newline="", encoding="utf-8-sig") as fp:
                w = csv.writer(fp)
                w.writerow(header)
                for row in old_rows[1:]:
                    w.writerow(row + [pd.get(row[1], "")])
        with open(mapping, "a", newline="", encoding="utf-8-sig") as fp:
            w = csv.writer(fp)
            if new:
                w.writerow(header)
            seen = {row[1] for row in old_rows[1:] if len(row) > 1}
            for r in pick:
                if r["key"] in seen:
                    continue
                idx += 1
                name = f"r{idx:03d}"
                (ex / f"{name}.txt").write_text(r["_text"], encoding="utf-8")
                (ex / f"{name}_prompt.txt").write_text(build_prompt(r["_text"], r["postdate"]), encoding="utf-8")
                sp = split_of(r["key"])
                w.writerow([name, r["key"], r["tier"], sp, r["property"], r["guest"], r["places"], r["postdate"]])
                print(f"  내보냄 {name}  {r['tier']} {sp} {r['property']:8s} {r['guest']:5s} {r['places']}")
        if args.rebuild_prompts:
            n = 0
            for row in csv.DictReader(open(mapping, encoding="utf-8-sig")):
                t = ex / f"{row['export']}.txt"
                if t.exists():
                    (ex / f"{row['export']}_prompt.txt").write_text(
                        build_prompt(t.read_text(encoding="utf-8"), row.get("postdate")), encoding="utf-8")
                    n += 1
            print(f"  프롬프트 {n}개 다시 씀 (작성일 줄 포함)")
        print(f"  → {ex}/  (rNNN.txt 원문 · rNNN_prompt.txt 추출 프롬프트) · 대응표 {mapping}")
        print("  다음: 프롬프트 → 추출 JSON → persona_extract.py --from-json … --blog NN --postdate <대응표 postdate> → 정답 확인(docs/정답_확인_체크리스트.md) → 봉인")
    return 0


if __name__ == "__main__":
    sys.exit(main())
