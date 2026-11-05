"""
메뉴 선택 층 — 업장당 값 하나 대신, 그 날 그 시각에 팔리는 상품 중 하나를 고른다 (10/2)

왜
  대표님 모델은 업장(L3) 아래 상품(L4)이 있고, 손님마다 상품 선택률 "(가정)" 이 있다. 우리는 prices.PRICE 로 업장당 1인 값 하나라
  객단가가 안 움직였다. 소연 상품표(menu.csv · 233줄 · PR #15)가 상품 · 단가 · 요일 · 시간 · 판매 기간을 다 가져왔으니
  에이전트가 식당에 간 시각에 "그때 팔리는 것" 중에서 고른다. 판매 기간이 조건으로 들어가서 봄 주말 같은 날도 홈페이지 기준으로 돌아간다.

어떻게
  1. menu.csv 를 읽어 요일제한 · 시간제한 · 판매시작 · 판매종료를 기계가 읽는 꼴로 푼다 (소연 형식 그대로 — docs/상품표.md)
  2. 행동 키(buffet_d · geum …) → 업장 + 끼니 필터로 후보를 좁히고, 날짜 · 요일(공휴일 포함) · 시각으로 거른다
  3. 손님에게 안 맞는 줄을 뺀다 — 어린이 줄은 아이 동반일 때만 · 2인 이상 줄은 1인 손님 제외 · 아동 동반 불가 패키지는 아이 있으면 제외 ·
     투숙객 전용은 비투숙 제외 · 연회 · 돌잔치 · 추가금 줄은 안 고른다
  4. 남은 후보에서 가중 추첨 — 원장상품(대표님 L4)이 있는 줄은 W_LEDGER 배 (대표 상품), △ 는 W_TRI 배. 이게 조정값이다
  5. 수량은 단위에서 — 1인 · 1인분 · 1잔 → 인원수 · 세트 N인 → 일행에 맞는 세트 1개 · 1판 · 1그릇 → 2인당 1 · 1박 → 박수 · 나머지 → 일행당 1
     아이 동반이면 어른 n-1 + 어린이 줄 1 (아이 수를 모르니 1로 둔다)

  시각이 어떤 창에도 안 들면 그 날 팔리는 줄에서 고르고 "시간 창 밖" 이라고 적는다 — 에이전트 시각과 메뉴판 창의 어긋남을 세기 위해
  후보가 없으면 None → revenue.py 가 prices.PRICE 값으로 떨어진다 (어느 줄이 그랬는지 note 에 남는다)

조정값 (근거 없는 숫자 — 보이게 둔다)
  W_LEDGER 3.0   원장상품이 있는 줄의 가중치. 대표님 원장이 "대표 상품" 으로 둔 것을 더 자주 고르게
  W_TRI    0.5   △ 줄의 가중치
  W_RACK   0.0   표준 요금(객실만) 줄 — 소연: "실제로 그 값에 파는지 모른다. 고를 때 빼거나 비중을 낮게"
  W_LIMITED 0.1  특정 객실 한두 개에 묶인 패키지 — 첫 판에서 바비 스위트가 하루 103 박, 빌라(2604호 하나)가 27 박 팔렸다. 실 수를 모를 때만 가중치로.
                 10/2 소연이 상품표에 객실 칸(유형 · 실 수)을 붙인 뒤로는 실 수를 아는 상품은 그 날 그 유형 상한(room_cap)으로 자른다
  W_RESERVE 0.2  사전 예약 상품 — 첫 판에서 명월관 별채 맡김차림(16석)이 44 팀. 걸어 들어온 손님이 고르는 것이 아니다
  아이 동반 손님에게 '어린이' 가 적힌 패키지(키즈 · 바비)는 W_LEDGER 배
  WEEKDAY_CHECKIN  주중 = 일~목 체크인 · 주말 = 금 · 토 (홈페이지가 요일을 안 적은 상품 — 빌라 · 나홀로 쉼). 호텔 관행 가정
  HOLIDAYS_2026    공휴일 · 대체공휴일 달력 (아래). 10/2 공식 달력과 대조 — 9/28 뺌 · 노동절 5/1 · 제헌절 7/17 넣음
"""

from __future__ import annotations

import csv, math, random, re
from datetime import date, datetime, time
from pathlib import Path

HERE = Path(__file__).resolve().parent

W_LEDGER = 3.0
W_TRI = 0.5
W_RACK = 0.0
W_LIMITED = 0.1   # 특정 객실 한두 개에 묶인 패키지 (빌라 2604호 · 바비 스위트 · 비건 스위트 · 키즈 스위트 · 펫 룸 · 허니문 · 슈퍼 스파). 실 수를 모르니 가중치로 누른다 — 현장 질문 7번
W_RESERVE = 0.2   # 사전 예약 상품 (별채 맡김차림 · 도원경 경 · 철판 · 오마카세 카운터) — 그 날 걸어 들어온 손님이 고르는 것이 아니다
LIMITED_WORDS = ("빌라", "바비", "Barbie", "비건 스위트", "키즈 딜럭스", "펫 컨셉", "허니문", "슈퍼 스파", "클럽 스위트 트윈")

# 2026 공휴일 · 대체공휴일 (상품표의 '+공휴일 · -공휴일' 은 대체 공휴일도 포함 — 추미진향 문구)
# 10/2 소연 대조 — 「관공서의 공휴일에 관한 규정」(2026.5.1 시행) · 천문연구원 2026 월력요항. 근거는 docs/상품표.md '공휴일 달력'
HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),      # 설 연휴
    date(2026, 3, 1), date(2026, 3, 2),                           # 삼일절(일) · 대체
    date(2026, 5, 1),                                             # 노동절 (2026.5.1 부터 공휴일)
    date(2026, 5, 5),                                             # 어린이날
    date(2026, 5, 24), date(2026, 5, 25),                         # 부처님오신날(일) · 대체
    date(2026, 6, 3),                                             # 지방선거
    date(2026, 6, 6),                                             # 현충일 (대체 없음)
    date(2026, 7, 17),                                            # 제헌절 (2026.5.11 부터 다시 공휴일)
    date(2026, 8, 15), date(2026, 8, 17),                         # 광복절(토) · 대체
    date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26),      # 추석 연휴 (26일 토 — 설 · 추석은 일요일과 겹칠 때만 대체)
    date(2026, 10, 3), date(2026, 10, 5),                         # 개천절(토) · 대체
    date(2026, 10, 9),                                            # 한글날
    date(2026, 12, 25),
}

DAYS = "월화수목금토일"

# 행동 키 → (업장, 상품 이름 필터 함수). 필터는 같은 업장 안에서 끼니 · 포장을 가른다
KEY_VENUE = {
    "geum": ("금룡", None),
    "pizza": ("피자힐", lambda r: "포장" not in r["단위"] and "추가금" not in r["단위"]),
    "pizza_to": ("피자힐", lambda r: "포장" in r["단위"]),
    "buffet_b": ("더뷔페", lambda r: r["상품"].startswith("조식")),
    "buffet_l": ("더뷔페", lambda r: r["상품"].startswith("중식")),
    "buffet_d": ("더뷔페", lambda r: r["상품"].startswith("석식")),
    "ondal": ("온달", None),
    "myong": ("명월관", None),
    "moegi": ("모에기", None),
    "pavilion": ("파빌리온", None),
    "lepassage": ("르파사쥬", None),
    "lux": ("럭스바", None),
    # 10/5 소연 — 입장권만 (쁘띠카바나는 뺀다). 전엔 '1부 · 2부' 이름만 골라서, 공식 리버파크 페이지로 더한
    # 블루 시즌 · 골드 월~목 (통운영) 줄이 빠지고 가격표 값으로 떨어졌다.
    "river": ("리버파크", lambda r: "카바나" not in r["상품"]),
    "theatre": ("빛의 시어터", None),
    "sauna": ("웰니스 사우나", None),
    "pool": ("수영장", lambda r: "투숙객" in r["상품"]),
    "forest": ("포레스트 파크", lambda r: "투숙객" in r["상품"]),
    # 10/8 소연 — 와인페어 입장권 (성인 줄 하나 · 아동은 child_row 가 붙인다). 투숙객이면 pick 이 0원으로 (10/11)
    "winefair": ("와인페어", None),
    "skyard": ("스카이야드", None),
    "valet": ("발렛", None),
}
ROOM_VENUE = {"GRAND": "그랜드", "VISTA": "비스타", "DOUGLAS": "더글라스"}

# 고르지 않는 줄 — 손님이 "한 번에 사는 단위" 가 아닌 것
SKIP_WORDS = ("추가금", "1인 추가", "연회", "1인 추가 시", "객실에 추가")
SKIP_PRODUCTS = ("[돌잔치] MY LITTLE STAR", "엑스트라 베드", "창가 PDR 이용료", "자연송이 모둠구이 한상 (가을 한정)", "3층 Bottle Zone SET (최저)",
                 "테니스 추가 인원", "테니스 볼 1캔 (2개)", "쁘띠카바나", "텐트 이용료")


def _parse_days(s: str):
    """요일제한 → (요일 집합 또는 None=매일, 공휴일 처리, 지정일 집합). 공휴일 처리: '+' 공휴일도 팜 · '-' 공휴일은 뺌 · None 무관"""
    s = s.strip()
    if not s:
        return None, None, None
    if s.startswith("지정일"):
        return None, None, {d.strip() for d in s[3:].split(",")}
    if s == "주중":
        return "weekday", None, None
    if s == "주말":
        return "weekend", None, None
    hol = None
    if s.endswith("+공휴일"):
        hol = "+"; s = s[:-4]
    elif s.endswith("-공휴일"):
        hol = "-"; s = s[:-4]
    return {DAYS.index(c) for c in s}, hol, None


_ROOM_PART = re.compile(r"^(.*?) (\d+)실$")


def _parse_rooms(cell: str):
    """→ [(유형, 실 수 또는 None)] · 빈 칸이면 []"""
    out = []
    for part in [p.strip() for p in cell.split(" + ") if p.strip()]:
        m = _ROOM_PART.match(part)
        if m:
            out.append((m.group(1), int(m.group(2))))
        else:
            out.append((part.rsplit(" ", 1)[0] if part.endswith(" 모름") else part, None))
    return out


def _parse_times(s: str):
    out = []
    for w in s.split(","):
        w = w.strip()
        if not w:
            continue
        a, b = w.split("-")
        h1, m1 = map(int, a.split(":")); h2, m2 = map(int, b.split(":"))
        out.append((h1 * 60 + m1, h2 * 60 + m2))
    return out


class Menu:
    def __init__(self, path: Path | None = None):
        path = path or HERE / "menu.csv"
        self.rows = []
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                r["단가"] = int(r["단가"])
                r["_days"] = _parse_days(r["요일제한"])
                r["_times"] = _parse_times(r["시간제한"])
                r["_from"] = date.fromisoformat(r["판매시작"]) if r["판매시작"] else None
                r["_to"] = date.fromisoformat(r["판매종료"]) if r["판매종료"] else None
                r["_child"] = (r["단위"].startswith("1인 · 어린이") or any(w in r["상품"] for w in ("어린이", "초등학생", "미취학", "청소년", "영유아"))) \
                    and r["업장"] not in ROOM_VENUE.values()      # 어린이 값 줄 (객실 패키지의 '어린이 동반' 은 아니다)
                r["_rack"] = r["포함"] == "객실만 (표준 요금)"
                r["_guest_only"] = "투숙객 전용" in r["근거"] or "투숙객 한정" in r["근거"]
                r["_limited"] = r["업장"] in ROOM_VENUE.values() and any(w in r["포함"] + r["상품"] for w in LIMITED_WORDS)
                # 객실 칸 (10/2 소연) — "유형 N실" · "유형 모름" · "A N실 + B M실". 실 수를 다 알면 그 날 그 유형 상한으로 쓴다
                r["_rooms"] = _parse_rooms(r.get("객실", ""))
                self.rows.append(r)
        self.by_venue = {}
        for r in self.rows:
            self.by_venue.setdefault(r["업장"], []).append(r)
        self.room_sold: dict[tuple, int] = {}   # (날짜, 건물, 객실 유형) → 그 날 그 유형으로 판 객실 수 — 실 수 상한 (10/2)
        self.room_capped = 0                     # 실 수가 차서 후보에서 뺀 횟수
        self.fallbacks = 0      # 후보가 없어 prices 값으로 떨어진 횟수
        self.off_window = 0     # 시각이 창 밖이라 그 날 줄에서 고른 횟수
        self.off_log: list[tuple[str, str]] = []   # (행동 키, HH:MM) — 어느 시각이 창 밖이었나

    # ── 날짜 · 요일 · 시각 ──────────────────────────────────────────────
    @staticmethod
    def is_holiday(d: date) -> bool:
        return d in HOLIDAYS_2026

    def on_sale(self, r, d: date) -> bool:
        if r["_from"] and d < r["_from"]:
            return False
        if r["_to"] and d > r["_to"]:
            return False
        days, hol, fixed = r["_days"]
        if fixed is not None:
            return d.strftime("%m-%d") in fixed
        if days is None:
            return True
        if days == "weekday":            # 호텔 관행 가정: 일~목 체크인
            return d.weekday() in (6, 0, 1, 2, 3)
        if days == "weekend":
            return d.weekday() in (4, 5)
        h = self.is_holiday(d)
        if hol == "+" and h:
            return True
        if hol == "-" and h:
            return False
        return d.weekday() in days

    @staticmethod
    def in_window(r, t: time) -> bool:
        if not r["_times"]:
            return True
        m = t.hour * 60 + t.minute
        for a, b in r["_times"]:
            if a <= b:
                if a <= m <= b:
                    return True
            else:                        # 자정을 넘김 (럭스바 20:00-01:00)
                if m >= a or m <= b:
                    return True
        return False

    # ── 손님에게 맞는 줄인가 ─────────────────────────────────────────────
    @staticmethod
    def fits(r, p) -> bool:
        if any(w in r["단위"] for w in SKIP_WORDS) or r["상품"] in SKIP_PRODUCTS:
            return False
        if r["_child"]:
            return False                 # 어린이 줄은 add_child 가 따로 붙인다
        u = r["단위"]
        if "(2인 이상)" in u and p.party_size < 2:
            return False
        if "성인 1인" in u and p.party_size != 1:
            return False
        if "성인 3인" in u and p.party_size != 3:
            return False
        if ("동반 불가" in u) and p.has_child_under_13:
            return False
        if r["_guest_only"] and not p.is_guest:
            return False
        if u.startswith("2박") and p.nights != 2:
            return False
        if u.startswith("1박") and p.nights == 2 and r["상품"].endswith("· 1박"):
            return False                 # 2박 묶음이 있는 상품은 2박 손님에게 2박 줄을 준다
        return True

    # ── 수량 ───────────────────────────────────────────────────────────
    @staticmethod
    def qty_of(r, p, adults: int) -> int:
        u = r["단위"]
        if u.startswith("세트"):
            return 1
        if u.startswith("1판") or u.startswith("1그릇"):
            return max(1, math.ceil(adults / 2))
        if u.startswith("1박"):
            return max(1, p.nights)
        if u.startswith("2박"):
            return 1
        if u.startswith("1인") or u.startswith("1잔") or u.startswith("1병"):
            return adults
        return 1

    @staticmethod
    def set_size(r) -> int | None:
        u = r["단위"]
        if u.startswith("세트"):
            for tok in u.split("·"):
                tok = tok.strip()
                if tok.endswith("인") and tok[:-1].isdigit():
                    return int(tok[:-1])
        return None

    # ── 고르기 ─────────────────────────────────────────────────────────
    def candidates(self, key: str, p, at: datetime):
        if key in ("room", "sleep"):
            venue, flt = ROOM_VENUE[p.property], None
        elif key in KEY_VENUE:
            venue, flt = KEY_VENUE[key]
        else:
            return [], False
        d = at.date()
        rows = [r for r in self.by_venue.get(venue, []) if (flt is None or flt(r)) and self.on_sale(r, d) and self.fits(r, p)]
        exact = [r for r in rows if self.in_window(r, at.time())]
        if exact:
            return exact, True
        return rows, False

    def room_cap(self, r) -> int | None:
        """객실 상품의 실 수 상한 — 모든 유형의 실 수를 알 때만 (하나라도 '모름' 이면 None = 상한 없음)"""
        parts = r.get("_rooms") or []
        if not parts or any(n is None for _, n in parts):
            return None
        return sum(n for _, n in parts)

    def room_sold_of(self, r, d) -> int:
        return sum(self.room_sold.get((d, r["업장"], t), 0) for t, _ in (r.get("_rooms") or []))

    def note_room_sold(self, r, d):
        for t, _ in (r.get("_rooms") or []):
            self.room_sold[(d, r["업장"], t)] = self.room_sold.get((d, r["업장"], t), 0) + 1

    def row_of(self, venue: str, product: str):
        for r in self.by_venue.get(venue, []):
            if r["상품"] == product:
                return r
        return None

    def package_terms(self, r) -> tuple[tuple[tuple[str, str], ...], bool]:
        """객실 상품의 포함 칸 → (included_meals, club_access). 생성기가 체크인 전에 persona 에 넣는다
        더뷔페 조식 · 중식 · 석식(디너) 은 포함 끼니로, 클럽 라운지 · 더글라스 라운지는 club_access 로 (라운지 조식 · 티타임 · 해피아워 자격)
        2박 줄의 포함 칸이 "1박 구성 + …" 로 줄여 적혀 있으면 같은 상품의 1박 줄 포함 칸을 이어 붙여 본다 (나홀로 쉼 2박 · 두근두근 2박 — 10/2 한호)"""
        inc = r["포함"]
        if inc.startswith("1박 구성") and r["상품"].endswith("· 2박"):
            one = self.row_of(r["업장"], r["상품"][:-len("· 2박")] + "· 1박")
            if one is not None:
                inc = one["포함"] + " · " + inc
        meals = []
        if "더뷔페 조식" in inc:
            meals.append(("조식", "THE_BUFFET"))
        if "더뷔페 중식" in inc:
            meals.append(("중식", "THE_BUFFET"))
        if "더뷔페 석식" in inc or "더뷔페 디너" in inc:
            meals.append(("석식", "THE_BUFFET"))
        club = any(w in inc for w in ("클럽 라운지", "클럽라운지", "더글라스 라운지", "라운지 Light Breakfast", "라운지 ·"))
        return tuple(meals), club

    def pick(self, key: str, p, at: datetime, rng: random.Random):
        """→ dict(product, qty, krw, grade, ledger, note) 또는 None"""
        if key in ("room", "sleep") and getattr(p, "package", None):
            r = self.row_of(ROOM_VENUE[p.property], p.package)      # 생성기가 미리 고른 객실 상품 — 다시 추첨하지 않는다
            if r is not None:
                qty = self.qty_of(r, p, max(1, p.party_size))
                return dict(product=r["상품"], qty=qty, krw=r["단가"] * qty, grade=r["등급"], ledger=r["원장상품"], note="", unit=r["단위"])
        rows, exact = self.candidates(key, p, at)
        if key in ("room", "sleep"):
            # 실 수 상한 — 그 날 그 유형이 다 팔렸으면 후보에서 뺀다 (바비 스위트 2실 · 빌라 1실 · 클럽 스위트 56실 …)
            before = len(rows)
            rows = [r for r in rows if self.room_cap(r) is None or self.room_sold_of(r, at.date()) < self.room_cap(r)]
            self.room_capped += before - len(rows)
        if not rows:
            self.fallbacks += 1
            return None
        adults = max(1, p.party_size - (1 if p.has_child_under_13 else 0))
        # 세트는 일행에 맞는 것 하나만 — 가장 작은 N ≥ 인원 (없으면 가장 큰 세트)
        sets = [(self.set_size(r), r) for r in rows if self.set_size(r)]
        if sets:
            fit = [r for n, r in sorted(sets) if n >= adults]
            best = fit[0] if fit else max(sets)[1]
            rows = [r for r in rows if not self.set_size(r)] + [best]
        weights = []
        for r in rows:
            w = W_LEDGER if r["원장상품"] else 1.0
            if p.has_child_under_13 and "어린이" in r["단위"]:
                w *= W_LEDGER                # 아이 동반 손님은 아이 동반을 적은 패키지(키즈 스위트 · 바비) 쪽으로
            if r["등급"] == "△":
                w *= W_TRI
            if r["_rack"]:
                w *= W_RACK
            if r["_limited"] and self.room_cap(r) is None:
                w *= W_LIMITED                   # 실 수를 알면 가중치 대신 상한으로 자른다
            if "사전 예약" in r["근거"] or "사전 유선 예약" in r["근거"]:
                w *= W_RESERVE
            weights.append(w)
        if sum(weights) <= 0:
            self.fallbacks += 1
            return None
        r = rng.choices(rows, weights)[0]
        if key in ("room", "sleep"):
            self.note_room_sold(r, at.date())
        qty = self.qty_of(r, p, adults)
        krw = r["단가"] * qty
        note = "" if exact else "시간 창 밖"
        if not exact:
            self.off_window += 1
            self.off_log.append((key, at.strftime("%H:%M")))
        out = dict(product=r["상품"], qty=qty, krw=krw, grade=r["등급"], ledger=r["원장상품"], note=note, unit=r["단위"])
        # 아이 동반 — 같은 업장 · 같은 끼니의 어린이 줄 하나를 1인 붙인다
        if p.has_child_under_13 and p.party_size >= 2:
            kid = self.child_row(key, r, at)
            if kid is not None:
                out["krw"] += kid["단가"]
                out["qty"] += 1
                out["child"] = kid["상품"]
        # 10/11 소연 · 와인페어 — 투숙객은 무료 입장 (워커힐 보도자료 9/14 "행사 기간 중 워커힐 투숙객은 무료로 입장이 가능하다").
        #   값을 내는 건 외부 손님뿐 (성인 55,000 · 아동 10,000). 10/8 엔 공식 홈페이지만 보고 패키지 (Wine Forest · 캠크닉 · 불멍)
        #   손님 성인 2인만 0원으로 두었다. 수량은 들어간 인원 그대로
        # 10/11 소연 · 와인페어 1부 (11:00~15:00) 는 성인 입장권에 어린이가 무료로 같이 들어간다 — 워커힐 네이버 예약 판매 페이지
        #   (사용자 화면 확인) "1부 이용 시 동반 어린이 입장 무료-솜사탕 제공 없음". 2부는 어린이 값 (10,000) 을 받는다
        if key == "winefair" and "child" in out and at.time() < time(15, 0):
            out["krw"] -= kid["단가"]
            out["note"] = "1부 동반 어린이 무료" + (f" · {note}" if note else "")
        if key == "winefair" and p.is_guest:
            out["krw"] = 0
            out["note"] = "투숙객 무료 입장" + (f" · {note}" if note else "")
        return out

    def child_row(self, key: str, chosen, at: datetime):
        venue = chosen["업장"]
        meal = chosen["상품"].split(" · ")[0]
        d = at.date()
        for r in self.by_venue.get(venue, []):
            if not r["_child"] or not self.on_sale(r, d):
                continue
            if venue == "더뷔페" and not r["상품"].startswith(meal):
                continue
            if venue == "더뷔페" and r["요일제한"] != chosen["요일제한"]:
                continue
            if venue == "리버파크" and ("1부" in chosen["상품"]) != ("1부" in r["상품"]):
                continue
            if venue == "빛의 시어터" and "어린이" not in r["상품"]:
                continue
            if venue not in ("더뷔페", "리버파크", "빛의 시어터"):
                continue      # 아래 두 번째 고르기로
            return r
        # 10/13 소연님 제안 — 그 밖의 업장은 고른 상품과 이름 앞 토막(' · ' 앞)이 같은 어린이 줄, 없으면 '어린이' 로 시작하는 일반 어린이 메뉴만.
        # (전엔 업장의 첫 어린이 줄을 붙여 명월관 가든 BBQ 지정일에 보통 저녁에도 'BBQ · 초등학생' 95,000 이 붙었다 · 워키 'Kids Play' 도 같은 문제)
        if venue in ("더뷔페", "리버파크", "빛의 시어터"):
            return None
        rows = [r for r in self.by_venue.get(venue, []) if r["_child"] and self.on_sale(r, d)]
        for r in rows:
            if r["상품"].split(" · ")[0] == meal:
                return r
        for r in rows:
            if r["상품"].startswith("어린이"):
                return r
        return None


_MENU = None


def default() -> Menu | None:
    global _MENU
    if _MENU is None and (HERE / "menu.csv").exists():
        _MENU = Menu()
    return _MENU


if __name__ == "__main__":
    import sys
    m = Menu()
    print(f"상품표 {len(m.rows)}줄 · 업장 {len(m.by_venue)}")
    for d in (date(2026, 10, 10), date(2026, 4, 4), date(2026, 10, 7)):
        n = sum(m.on_sale(r, d) for r in m.rows)
        rooms = [r["상품"] for r in m.rows if r["업장"] in ("그랜드", "비스타", "더글라스") and not r["_rack"] and m.on_sale(r, d)]
        print(f"  {d} ({DAYS[d.weekday()]}{' · 공휴일' if m.is_holiday(d) else ''}) 팔리는 줄 {n} · 객실 패키지 {len(rooms)}")
