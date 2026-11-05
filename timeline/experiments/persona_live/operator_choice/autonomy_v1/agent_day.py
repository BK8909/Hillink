"""자율 행동 시뮬레이션 V1 (CL-1024-18) — 후기 기반 고객 11명이 워커힐 월드에서 각자 하루를 진행한다.

구조(한 번의 결정):
  ① 현재 상태 읽기(시각 · 위치 · 끼니 · 피로 · 이미 한 활동 · 체류 단계 · 동행)
  ② 욕구 판단(의무: 체크인 · 체크아웃 · 귀가 · 취침 / 끼니 창 / 피로 / 여가)
  ③ 그 시각 월드에서 할 수 있는 행동 후보 생성(엔진 지원 상품 + 계획기 활동 카탈로그 + 객실 · 아무것도 안 함 · 귀가)
  ④ 월드 규칙 검증(영업시간 · 투숙객 전용 · 성인 전용 · 체류 단계 · 계절 · 행사 날 숲 제한 · 운영자 변경)
  ⑤ 개인 평가 — 엔진이 지원하는 상품(저녁 식당 · 행사 · 족욕 · 수영장 · 사우나 · 숲 산책 · 객실 식사 · 휴식)은 동결 정량 엔진(V1 decide_at · C-1/2/3)으로,
     엔진 밖 활동(아침 · 점심 · 카페 · 라운지 · 시어터 · 바 · 산책 · 객실 활동)은 계획기의 성향 가중치(stay_planner.act_weight · lunch_weight)로 시드 고정 선택
  ⑥ 실행 — 이동 · 활동 기록, 시각 · 위치 · 상태 갱신
  ⑦ 운영자 변경이 생기면 그 시각 이후의 결정부터 새 월드로 다시 판단(이미 한 행동은 그대로)

원칙: 엔진 · 계수 · 프로필 · 계획기 파일은 고치지 않고 불러 쓴다. 엔진이 지원하지 않는 활동도 불가능으로 치지 않는다.
근거 기록: 행동마다 '후기에서 확인'(그 고객 소유 사실 ID) / '프로파일 기반 추론'(성향 · 동행 · 상황) 두 유형. 운영 조건 · 점수 · 출처 등급은 내부 기록(internal)에만.
LLM: 이 실행기는 규칙 백엔드로 돈다(LLM 키 없음 · 실제 호출 0). 후보 제안 계층 자리는 propose_llm() 로 비워 둔다.
"""
from __future__ import annotations

import copy, hashlib, json, random, re
from pathlib import Path

from ..operator_world_v1 import engine as EN, world as WD
from ..operator_world_v1_1 import stay_planner as SP
from ..operator_world_v1_1.candidate import candidate_engine
from ..operator_world_v1_1.turn_view import load_all_personas, turn_meta
from . import ledger as LG

VERSION = "autonomy_v1-2026-10-24"
HERE = Path(__file__).resolve().parent
TL = HERE.parents[3]
DEMO = ["A02", "A04", "A05", "A07", "A10", "blog41", "blog42", "blog43", "A01", "A03", "A08"]

# 엔진 상품 → 지도 장소 · 행동 영역
ENGINE_LOC = {"WINE_FAIR": "FOREST_PARK", "PIZZA_HILL": "PIZZA_HILL", "THE_BUFFET": "THE_BUFFET", "MYONGWOLGWAN": "MYONGWOLGWAN", "ONDAL": "ONDAL", "GEUMRYONG": "GEUMRYONG",
              "ROOM_MEAL": "@room", "SIMPLE_MEAL_VIEW": "LE_PASSAGE", "SKYARD": "SKYARD", "SKYARD_NIGHT": "SKYARD", "POOL": "@pool", "SAUNA": "WELLNESS_SAUNA",
              "FOREST_WALK": "FOREST_PARK", "ROOM_REST": "@room", "BREAKFAST_BUFFET": "THE_BUFFET", "SKIP_BREAKFAST": "@room"}
ENGINE_DOMAIN = {"WINE_FAIR": "행사", "PIZZA_HILL": "식사", "THE_BUFFET": "식사", "MYONGWOLGWAN": "식사", "ONDAL": "식사", "GEUMRYONG": "식사", "ROOM_MEAL": "식사",
                 "SIMPLE_MEAL_VIEW": "식사", "SKYARD": "웰니스", "SKYARD_NIGHT": "웰니스", "POOL": "웰니스", "SAUNA": "웰니스", "FOREST_WALK": "산책", "ROOM_REST": "객실 휴식",
                 "BREAKFAST_BUFFET": "식사", "SKIP_BREAKFAST": "객실 휴식"}
PLAN_DOMAIN = {"rest": "객실 휴식", "wellness": "웰니스", "outdoor": "산책", "snack": "카페", "culture": "문화", "lunch": "식사", "bar": "바", "stay": "체류"}
GUEST_ENGINE = {"POOL", "SAUNA", "ROOM_MEAL", "ROOM_REST"}           # 투숙객만(계획기 GUEST_ONLY 와 같은 기준)
NIGHT_FROM = {"night_walk": "18:00", "night_footbath": "19:30", "luxbar": "18:00"}   # 이름 그대로 저녁 · 밤 활동(일몰 가정 18:00 · 야경 족욕 운영 19:30)
SEASON_CLOSED = {"riverpark": "리버파크는 여름 시즌 운영 — 10월 비운영(월드 · 계절 규칙)"}
NOT_ELIGIBLE = {"lounge": "클럽 라운지는 클럽 객실 자격이 필요 — 이번 고객의 객실 등급 미상이라 후보에서 제외"}
LEISURE = ["pool", "sauna", "fitness", "footbath", "night_footbath", "forest_walk", "garden_walk", "riverpark", "tennez", "cafe", "bakery", "lounge", "library", "theatre",
           "luxbar", "night_walk", "room_rest", "room_bath", "room_nap"]
LUNCH_ENGINE = {"lunch_pizzahill": "PIZZA_HILL", "lunch_myongwol": "MYONGWOLGWAN", "lunch_ondal": "ONDAL", "lunch_geumryong": "GEUMRYONG", "lunch_bakery": "SIMPLE_MEAL_VIEW", "lunch_room": "ROOM_MEAL"}   # 같은 업장을 하루 두 끼로 고르지 않음
FOOD_KINDS = {"snack", "lunch"}
REST_MERGE = {"room_rest", "ROOM_REST", "room_bath", "idle"}
# 시간당 피로(+) · 회복(−) — 설계값(결과에 맞춘 조정 아님): 운동 1.0 · 걷기 0.7 · 관람 0.5 · 식사 0.3 · 온수 · 족욕 0.1 · 객실 휴식 −1.5
EFFORT = {"pool": 1.0, "POOL": 1.0, "fitness": 1.0, "sauna": 0.2, "SAUNA": 0.2, "footbath": 0.1, "night_footbath": 0.1, "SKYARD": 0.1, "SKYARD_NIGHT": 0.1,
          "forest_walk": 0.7, "FOREST_WALK": 0.7, "garden_walk": 0.6, "night_walk": 0.6, "tennez": 0.6, "riverpark": 0.8, "theatre": 0.5, "WINE_FAIR": 0.6,
          "room_rest": -1.5, "ROOM_REST": -1.5, "room_bath": -1.5, "room_nap": -1.5, "library": -0.8, "unpack": -0.5, "idle": -1.0, "wait": 0.0, "sleep": -3.0, "wake": 0.0}
EFFORT_DOMAIN = {"식사": 0.3, "카페": 0.1, "바": 0.2, "체류": 0.4, "대기": 0.0, "포기": 0.0, "휴식": -1.0, "객실 휴식": -1.5}
CHECKOUT_BY = "11:00"
ENGINE_ADULT = {"SAUNA"}   # 계획기 ACT 의 성인 전용(sauna)에 대응하는 엔진 상품
EV_OVER = {"library": r"라이브러리|library", "cafe": r"카페|cafe|디저트|dessert|(?<!캡슐)커피"}
NEG_DONE = re.compile(r"포기|못 ?했|안 ?했|하지 않|않았|으로 전환|로 전환")   # '…하려다 포기 · …로 전환' — 그 활동을 실제로 하지 않은 경험
INCOMPLETE = re.compile(r"휴관|휴무|운영 ?중단|임시 ?폐쇄|(관람|이용|입장|체험)(을|에|이)? ?(못|실패)|(관람|이용|입장|체험) ?실패")   # CL-1025-30 — 운영 중단 · 미완료(CLOSED/CANCELED_INCOMPLETE): 가려 했으나 시설 쪽 사정으로 이용하지 못함. NEG_DONE(본인이 하지 않음)과 구분
INCOMPLETE_WHY = "운영 중단 · 미완료로 이용하지 못한 경험(CLOSED/CANCELED_INCOMPLETE)"
SUBSTITUTE = re.compile(r"(대체|대신)\S*\s*(방문|이용|식사|관람)|(으로|로) 대체|대신했")   # CL-1025-31 — '휴관 뒤 다른 곳을 대신 이용'은 그 대체 행동이 실제로 일어난 관측(OBSERVED) — CLOSED 로 묶지 않음(F010 ≠ F011)
INCOMPLETE_NEG = rf"^(?!.*(?:{SUBSTITUTE.pattern})).*(?:{INCOMPLETE.pattern})"   # fact_hits 부정 패턴용(대체 행동 문장은 제외)
VENUE_UNSPEC = re.compile(r"근처 ?(다른 )?(카페|가게|식당|베이커리|빵집)")   # CL-1025-31 — 장소를 특정하지 않은 워커힐 관측(예: '근처 카페') — 월드의 특정 업장 직접 경험 · 선택 가중으로 쓰지 않음
UNSPEC_WHY = "장소 미특정 관측 — 같은 종류 활동을 한 번 했다는 사실만(이 업장 직접 경험 · 선호 강도 아님)"


def incomplete(g):
    return bool(INCOMPLETE.search(g or "")) and not SUBSTITUTE.search(g or "")
# CL-1025-24 — 근거 수준 구분(동결 엔진 · 계수 불변 · 표시 · 근거 분류만)
CONTEXT_ONLY = re.compile(r"동선|위치|가까|접근")   # 시설을 '이용'한 기록이 아니라 동선 · 위치에 대한 만족(예: 객실이 스카이야드와 가까워 좋았다)
USE_DONE = re.compile(r"이용|즐기|즐겼|족욕(을|하)|수영(을|하)|먹었|먹고|마셨|참여|주문|발을 따뜻|반신욕|관람")
AVOID = re.compile(r"다음에는 오지 않|다시 (가|오|찾)지 않|재방문(하지 않| 의사 ?없)|추천하지 않|비추천")   # 그 업장에 다시 가지 않겠다는 직접 경험 — 회피(부정) 근거
AUTHOR_PENDING = "원저자 매핑 검수 대기(여러 글을 합친 개발 비교 고객 · 사람 검수 전)"
CLUB_RE = re.compile(r"클럽")
# CL-1025-25 — 행동 근거로 쓰지 않는 내용(원문 · 사실은 보존 · 근거 표시 · 설명에서만 제외): 남은 음식 포장 · 줄 서기 · 대기 감수
OUT_OF_SCOPE = re.compile(r"포장|남은 음식|웨이팅|줄을 ?서|현장 대기|대기를 (받아|감수)|기다리(기로|며)")
TRANSFER = "CONTEXT_TRANSFER_INFERENCE"
TRANSFER_WHY = "같은 업장 이용 맥락에서 넓힌 추론(다른 메뉴 · 다른 끼니를 묶은 요약 — 이 상품 직접 경험 아님)"


def clause_transfer(g, names, slot):
    """요지를 문장으로 나눠, 업장 이름이 나온 문장에 끼니 말이 없고 끼니 말은 다른 문장에만 있으면 True(묶인 요약 — 예: '룸서비스 짬뽕 … 라이트 조식은 …')."""
    from .profile_context import SLOT_WORDS
    words = SLOT_WORDS.get(slot, ())
    if not slot or not names or not any(w in g for w in words):
        return False
    cl = [c for c in re.split(r"(?<=다)\.\s*|\.\s+", g) if c.strip()]
    at = [c for c in cl if any(n in c for n in names)]
    return bool(at) and not any(w in c for c in at for w in words)
import os as _os
EVENT_FEE_DECISION = _os.environ.get("HILLINK_EVENT_FEE_DECISION") == "1"   # CL-1024-21A 승인 지점 — 기본 0(동결 엔진 가격으로 판단 · 장부만 무료)
PLACE_NAMES = {"PIZZA_HILL": ["피자힐", "피자"], "MYONGWOLGWAN": ["명월관"], "ONDAL": ["온달"], "GEUMRYONG": ["금룡"], "THE_BUFFET": ["더뷔페", "더 뷔페", "뷔페"],
               "MOEGI": ["모에기"], "SIMPLE_MEAL_VIEW": ["르 파사쥬", "르파사쥬", "베이커리"], "PAVILION": ["파빌리온"], "SKYARD": ["스카이야드", "족욕"], "POOL": ["수영장", "풀에서", "온수풀"],
               "SAUNA": ["사우나"], "ROOM_MEAL": ["룸서비스", "인룸"], "WINE_FAIR": ["와인페어"], "LUXBAR": ["럭스바"], "FITNESS": ["헬스장", "피트니스"], "GARDEN_BBQ": ["BBQ", "바비큐"], "LOUNGE": ["라운지", "해피아워"]}
PLACE_FAMILY = {"SKYARD_NIGHT": "SKYARD", "footbath": "SKYARD", "night_footbath": "SKYARD", "VISTA_POOL": "POOL", "GRAND_POOL": "POOL", "pool": "POOL", "sauna": "SAUNA",
                "RS_BREAKFAST_KOREAN": "ROOM_MEAL", "lunch_room": "ROOM_MEAL", "lunch_pizzahill": "PIZZA_HILL", "lunch_myongwol": "MYONGWOLGWAN", "lunch_ondal": "ONDAL",
                "lunch_geumryong": "GEUMRYONG", "lunch_moegi": "MOEGI", "lunch_bakery": "SIMPLE_MEAL_VIEW", "bakery": "SIMPLE_MEAL_VIEW", "LE_PASSAGE": "SIMPLE_MEAL_VIEW",
                "cafe": "PAVILION", "lunch_cafe": "PAVILION", "luxbar": "LUXBAR", "fitness": "FITNESS", "BREAKFAST_BUFFET": "THE_BUFFET", "BREAKFAST": "THE_BUFFET"}


BLD_SHORT = {"VISTA": "비스타", "GRAND": "그랜드", "DOUGLAS": "더글라스", "NONSTAY": "비투숙 당일 방문"}


def review_stay(P, vs, W, pending=False):
    """CL-1025-24 — 후기에 남은 숙박(관측)과 이번 기본 시나리오(성향 가중 추첨 · 후기 복사 아님)를 나란히.
    추첨 · 결과는 바꾸지 않는다. 운영자가 후기 숙박 조건을 고르면 visit_override 경로(운영자가 정한 조건)로만 바뀐다."""
    form = str((P.get("vfs") or {}).get("방문 형태") or "")
    b = None
    if form:
        hb = [k for k, rx in SP.HOTEL_RE.items() if re.search(rx, form, re.I)]
        if "숙박" in form and hb and not form.startswith("비투숙"):
            b = hb[-1]
        elif re.search(SP.NONSTAY_RE, form):
            b = "NONSTAY"
    if not b:   # 방문 형태 요약이 없으면 후기 사실에서 잡힌 숙박(계획기 visit_state 와 같은 규칙 · 읽기만)
        hits = {}
        for f in P.get("facts") or []:
            if f.get("kind") in ("expectation", "decline"):
                continue
            t = f"{f.get('gist', '')} {f.get('feat', '')}"
            for k, rx in SP.HOTEL_RE.items():
                if re.search(rx, t, re.I):
                    hits[k] = hits.get(k, 0) + 1
            if re.search(SP.NONSTAY_RE, t):
                hits["NONSTAY"] = hits.get("NONSTAY", 0) + 1
        if hits:
            b = max(hits, key=lambda k: (W.get(k, 0), hits[k]))
    tot = sum(v for v in W.values() if v > 0) or 1.0
    share = lambda k: round(W.get(k, 0) / tot, 2) if W else None
    drawn = vs["building"] if vs.get("stay") else "NONSTAY"
    club = bool(b == "GRAND" and CLUB_RE.search(form))
    out = dict(building=b, label=(BLD_SHORT.get(b, b) + (" 클럽" if club else "")) if b else None, club=club, review_share=share(b) if b else None,
               drawn=drawn, drawn_share=share(drawn), same=bool(b and b == drawn), pending=pending, core=["클럽 라운지(티타임 · 해피아워)"] if club else [])
    if not b:
        out["text"] = "후기에 숙박 단서가 없어 유형 · 성향으로 방문 조건을 정했습니다."
    elif pending:
        out["text"] = f"숙박 단서({BLD_SHORT.get(b, b)})는 여러 글을 합친 자료에서 나와 원저자 대응을 검수하기 전입니다 — 후기 숙박으로 단정하지 않습니다."
    elif out["same"]:
        out["text"] = f"기본 시나리오도 후기 숙박과 같은 {out['label']}입니다."
    else:
        miss = f" 그래서 후기의 핵심 경험({', '.join(out['core'])})은 이번 하루 후보에 없습니다." if out["core"] else ""
        out["text"] = (f"후기 숙박은 {out['label']}입니다. 기본 시나리오는 후기를 그대로 복사하지 않고 성향 가중치로 추첨하는데(후기 쪽 {int(round((out['review_share'] or 0) * 100))}%), "
                       f"이번 시드에서는 {BLD_SHORT.get(drawn, drawn)}({int(round((out['drawn_share'] or 0) * 100))}%){SP.josa(BLD_SHORT.get(drawn, drawn), '이', '가')} 나왔습니다.{miss} "
                       f"후기 숙박 그대로 보려면 '후기 숙박 조건으로 실행'(운영자가 정한 조건)을 누릅니다.")
    return out


def tod(t):   # 시간대 말 — 설명 문장이 실제 시각과 맞도록
    return "아침" if t < hm("10:30") else "오전" if t < hm("11:30") else "점심" if t < hm("14:00") else "오후" if t < hm("17:30") else "저녁" if t < hm("21:00") else "밤"


SAME_FACILITY = {"pool": "POOL", "sauna": "SAUNA", "footbath": "SKYARD", "night_footbath": "SKYARD_NIGHT", "forest_walk": "FOREST_WALK", "room_rest": "ROOM_REST"}
REPEATABLE = {"room_rest", "lunch_skip"}
VENUE_KO = {"PIZZA_HILL": "피자힐", "THE_BUFFET": "더뷔페", "MYONGWOLGWAN": "명월관", "ONDAL": "온달", "GEUMRYONG": "금룡", "ROOM_MEAL": "객실 룸서비스", "SIMPLE_MEAL_VIEW": "르 파사쥬"}
ENGINE_COVERS = {"pool", "sauna", "footbath", "night_footbath", "forest_walk", "room_rest"}   # 15:30 뒤에는 엔진이 같은 활동을 점수로 판단 → 계획기 쪽 중복 후보 제외


def hm(s): return EN.hm(s)
def mh(t): return EN.mh(int(t))


def _sha(o): return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False, default=list).encode()).hexdigest()


def propose_llm(agent, t, needs):   # 하이브리드 자리 — 키 없음 · 호출 안 함
    return None


# ---------------------------------------------------------------- 입력
def clean_overlay():
    return json.loads((Path(__file__).with_name("product_clean_input_v1.json")).read_text(encoding="utf-8"))


def apply_clean_input(P, overlay=None):
    """CL-1025-27 — 제품용 정제 입력(비파괴). 동결 입력 P 는 건드리지 않고, 영향 고객의 traits 만 깊은 복사본으로 바꿔 새 dict 를 돌려준다.
    성향(facet) 근거 목록과 업장 이용 기록에서 지정 사실만 뺀다 — 수준은 동결 엔진 산식(ev)이 다시 계산(사후 점수 빼기 아님)."""
    ov = overlay or clean_overlay()
    out, log = dict(P), []
    for it in ov["items"]:
        pid, fid = it["persona"], it["fact_id"]
        if pid not in out:
            continue
        if out[pid] is P.get(pid):
            out[pid] = copy.deepcopy(P[pid])
        tr = out[pid]["traits"]
        for fk in (it["remove"].get("facets") or []):
            f = tr["facets"].get(fk)
            if not f:
                continue
            n0 = len(f.get("evidence") or [])
            f["evidence"] = [e for e in f.get("evidence") or [] if e.get("fact_id") != fid]
            f["fact_ids"] = [x for x in f.get("fact_ids") or [] if x != fid]
            lv0 = f.get("level")
            lv = EN.ev({"facets": {fk: f}}, fk)[0] if f["evidence"] else 0.0   # 저장 수준 = 동결 산식 ev() 와 같은 값(검증함) — 같은 산식으로 다시 계산
            f.update(level=lv, level_all=lv, present=bool(f["evidence"]) and lv > 0)
            log.append(dict(persona=pid, fact_id=fid, where=f"facets.{fk}.evidence", removed=n0 - len(f["evidence"]), code=it["code"], level_before=lv0, level_after=lv))
        for vk in (it["remove"].get("venue_used") or []):
            vs = (tr.get("venues") or {}).get(vk) or []
            n0 = len(vs)
            tr["venues"][vk] = [v for v in vs if not (v.get("kind") == "used" and fid in (v.get("fact_ids") or []))]
            log.append(dict(persona=pid, fact_id=fid, where=f"venues.{vk}[used]", removed=n0 - len(tr["venues"][vk]), code=it["code"]))
    return out, log


def load_inputs():
    import sys
    sys.path.insert(0, str(TL / "viewer"))
    P = load_all_personas()
    if _os.environ.get("HILLINK_CLEAN_INPUT") == "1":   # CL-1025-27 — 제품용 정제 입력(사용자 승인 전 기본 꺼짐 · 성향 막대도 같은 입력으로)
        P, _log = apply_clean_input(P)
    meta = turn_meta("dinner", P)
    bars = {p["id"]: p.get("bars") or [] for p in meta.get("personas", [])}
    lib = {}
    for fn in ("persona_library.json", "persona_library.local.json"):
        f = TL / "viewer" / "static" / fn
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            ps = d.get("personas") if isinstance(d, dict) else d
            items = ps.items() if isinstance(ps, dict) else ((p["id"], p) for p in ps or [])
            for k, p in items:   # CL-1025-23 — 로컬 전용 자료는 공개 항목 위에 겹친다(유형 · 방문 형태 같은 공개 필드가 지워지지 않게 · 값이 None 인 필드는 덮지 않음)
                lib[k] = dict(lib.get(k) or {}, **{kk: vv for kk, vv in (p or {}).items() if vv is not None})
    return P, bars, lib


# ---------------------------------------------------------------- 시나리오(운영 조건) — 내부 기록
def scenario(name="base", **kw):
    """levers: 엔진 월드 운영 변수(시작부터) · changes: [{at, label, levers, closed:{loc:[s,e]}}] 운영자 개입 · breakfast_in_package: 조식 포함 가정."""
    s = dict(name=name, date="2026-10-24", day_label="가을 토요일", levers={"WINE_FAIR": {"available": False}}, changes=[], closed={}, breakfast_in_package=True,
             observe="day", seed=0, assumptions=["조식은 객실 포함으로 가정(공식 조식 가격 미확인)", "건물 사이 이동 시간은 지도 거리감 기반 연출값", "좌석 · 대기 · 정원은 모델링하지 않음"])
    s.update(kw)
    return s


class World:
    """공유 월드 — 시각에 따라 운영자 변경을 반영한다. 고객끼리 자원을 다투지 않는다(현재 지원되는 대기 · 정원 제약 없음)."""
    def __init__(self, sc):
        self.sc = sc
        self.changes = sorted(sc.get("changes") or [], key=lambda c: hm(c["at"]))

    def levers_at(self, t):
        lv = copy.deepcopy(self.sc.get("levers") or {})
        for c in self.changes:
            if hm(c["at"]) <= t:
                for k, v in (c.get("levers") or {}).items():
                    lv[k] = dict(lv.get(k) or {}, **v)
        return lv

    def closed_at(self, t):
        cl = dict(self.sc.get("closed") or {})
        for c in self.changes:
            if hm(c["at"]) <= t:
                cl.update(c.get("closed") or {})
        return {k: (hm(a), hm(b)) for k, (a, b) in cl.items()}

    def engine_world(self, t):
        return WD.apply_levers(WD.default_world(), self.levers_at(t))

    def notice(self, t0, t1):
        return [c for c in self.changes if t0 < hm(c["at"]) <= t1]


# ---------------------------------------------------------------- 고객
class Agent:
    def __init__(self, pid, P, bars, lib, sc):
        self.pid = pid
        self.traits = P[pid]["traits"]
        self.lib = (lib or {}).get(pid) or {}
        self.staff = sorted({v.get("owner") for v in (lib or {}).values() if isinstance(v, dict) and v.get("owner")})   # 담당 분석가 이름 — 문맥에서 걸러내기 위해서만(출력 안 함)   # 팀 분석(방문 경험 · 판단 패턴 · 행동 가설) — LLM 문맥 어댑터가 비식별 요약만 사용
        self.P = SP.profile(pid, P.get(pid), bars.get(pid), lib)
        from . import profile_context as _PC
        _unspec = [f for f in self.P["facts"] if VENUE_UNSPEC.search(f.get("gist") or "") and _PC.fact_context(self, f["id"]) == "wh"]   # CL-1025-31
        _neg = SP.NEG_BASE + "|" + INCOMPLETE_NEG
        self.obs_unspec = SP.fact_hits(_unspec, neg_rx=_neg, over=EV_OVER) if _unspec else {}   # 표시 근거로만(선택 가중 없음)
        self.P["fact_hits"] = SP.fact_hits([f for f in self.P["facts"] if f not in _unspec], neg_rx=_neg, over=EV_OVER)   # CL-1025-30 — 휴관 · 관람 실패 사실은 그 활동의 선택 가중 · '후기에서 확인' 근거로 쓰지 않음   # CL-1025-23 — '독서'(리버파크 선베드) · '캡슐커피'(객실 미니바)가 라이브러리 · 카페 경험으로 잡히지 않게(자율 엔진만 · 기존 계획기 불변)
        seed = sc.get("seed", 0)
        _pk, _cap = SP.pick, {}
        def _pick_cap(rng, items, w):   # 방문 조건 추첨의 가중치를 기록만(추첨 · 결과는 그대로) — 후기 숙박과 기본 시나리오의 차이를 설명하려고
            if "VISTA" in items and "W" not in _cap:
                _cap["W"] = {k: w(k) for k in items}
            return _pk(rng, items, w)
        SP.pick = _pick_cap
        try:
            self.vs = SP.visit_state(self.P, {"event": False, "scenario": sc.get("observe", "day")}, None, seed)   # 투숙 · 건물 · 박수 · 단계 · 동행은 고객 프로파일이 정함(운영자 강제 아님)
        finally:
            SP.pick = _pk
        self.author_pending = (self.lib or {}).get("group") == "dev"   # CL-1025-24 — blog41~43: 여러 글 합성 · 원저자 대응 사람 검수 전 → 직접 경험으로 단정하지 않음
        self.review_stay = review_stay(self.P, self.vs, _cap.get("W") or {}, self.author_pending)
        ov = (sc.get("visit_override") or {}).get(pid)   # CL-1024-22R — 고객 흐름 '한 명'(운영자가 정한 방문 조건) · 여러 명 '같은 조건 고정'. 없으면 고객이 정함
        if ov:
            self.vs = dict(self.vs, **{k: ov[k] for k in ("stay", "building", "phase", "party_size", "nights") if ov.get(k) is not None})
            if not self.vs["stay"]:
                self.vs.update(phase="visit", building=None)
            if self.vs["stay"] and not self.vs.get("nights"):
                self.vs["nights"] = 1
            self.vs.update(layer="operator_override", why="운영자가 정한 방문 조건(고객 흐름) — 고객이 정한 조건이 아님" + (" · 클럽 객실" if ov.get("club") else ""))
        self.B, self.stay, self.phase, self.N = self.vs["building"], self.vs["stay"], self.vs["phase"], self.vs["party_size"]
        # 클럽 객실(클럽 라운지 자격): 운영자가 명시한 경우, 또는 기본 시나리오가 후기와 같은 건물을 뽑았고 후기가 클럽 숙박인 경우만
        self.club = bool(self.stay and self.B == "GRAND" and ((ov or {}).get("club") if ov else (self.review_stay.get("club") and self.review_stay.get("building") == "GRAND")))
        self.review_stay["club_today"] = self.club
        self.C = SP.comp_of(pid, self.N, {"n": self.N, "rel": self.vs["rel"], "kids": self.vs["kids"], "elder": self.vs["elder"]})
        self.rng = random.Random(f"autonomy|{pid}|{seed}|{sc.get('name')}")
        self.rng_base = f"autonomy|{pid}|{seed}"
        self.log, self.done, self.used = [], [], set()
        self.meals = {"breakfast": False, "lunch": False, "dinner": False}
        self.fatigue, self.spent, self.hunger_e = 0.0, 0, 1.0
        self.spent_est = 0   # 아이 동반 가족의 성인 요금 기준 추정분(spent 에 포함 · 확정 지출 아님)
        self.meal_log, self.charges = [], []   # 공통 장부(ledger) — 끼니 칸 · 양 / 지출(가격 미정 구분)
        self.checked_in = self.phase in ("mid", "checkout")
        self.checked_out = False
        self.left = False
        self.room = SP.room(self.B) if self.stay else None
        self.loc = self.room if self.phase in ("mid", "checkout") else "HOTEL_GATE"
        fh = self.P["fact_hits"]
        if self.phase in ("mid", "checkout"):
            self.t = hm("08:30") if "late" in fh else hm("07:30")
        elif self.phase == "checkin":
            self.t = hm("13:30") if "early" in fh else hm("14:30")
        else:
            self.t = hm("11:30") if "lunch_visit" in fh else hm("15:00")
        self.end = hm("23:00")
        self.visit_e = dict(WD.default_visit(pid), party_size=self.N, end="23:00", checkin="15:30")
        self.steps = 0
        self.checked = set()   # 안내를 이미 확인한 행사(같은 행사의 안내를 두 번 확인하지 않음 · 엔진 simulate_day 와 같은 규칙)
        self.food = []          # (끝 시각, 장소) — 식사 · 간식 직후 같은 곳 · 연속 간식 방지
        self.ended = False
        self.gave_up = set()
        self.rest_limit = round(3.4 - 1.4 * self.P["bars"].get("rest_need", 0) - 0.6 * self.P["facets"].get("warm_rest", 0) + 0.5 * self.P["facets"].get("active", 0), 2)   # 개인 페이스(휴식 성향이 클수록 일찍 쉼)
        self.trace = []         # 결정마다 욕구 · 고려 대안 · 앞선 활동 영향 · 백엔드(내부)
        self.planner = sc.get("planner", "rules")
        self.intents = []       # LLM 계획 블록에서 받은 다음 행동 의도(차례로 검증 · 실행)
        self.llm_ctx = {}

    # 근거 · 설명 -------------------------------------------------------
    def gist(self, fid):
        e = (self.traits.get("evidence_index") or {}).get(fid) or {}
        if e.get("gist"):
            return e["gist"]
        for f in self.P["facts"]:
            if f["id"] == fid:
                return f["gist"]
        return ""

    def fact_places(self, fid):
        """사실이 특정 장소에 관한 것이면 그 장소 집합(구조화 연결 + 요지의 업장 이름). 비어 있으면 일반 성향 사실."""
        if not hasattr(self, "_fp"):
            self._fp = {}
            for k, vs in (self.traits.get("venues") or {}).items():
                for v in vs:
                    for f in v.get("fact_ids") or []:
                        self._fp.setdefault(f, set()).add(v.get("venue") or k)
            for v in self.traits.get("facility_type_history") or []:
                for f in v.get("fact_ids") or []:
                    self._fp.setdefault(f, set()).add(v.get("venue_type") or v.get("venue"))
        g = self.gist(fid)
        named = {pid for pid, names in PLACE_NAMES.items() if any(n in g for n in names)}
        if "LOUNGE" in named and "피자힐" not in g:   # CL-1025-24 — '라운지 해피아워 피자'는 피자힐 경험이 아님
            named.discard("PIZZA_HILL")
        return (self._fp.get(fid) or set()) | named

    def avoid_facts(self, venue):
        """CL-1025-24 — 그 업장에 '다시 가지 않겠다'고 한 워커힐 직접 경험(회피 근거). 원저자 검수 전 · 다른 곳 경험은 제외."""
        from . import profile_context as PC
        if self.author_pending:
            return []
        names = PLACE_NAMES.get(PLACE_FAMILY.get(venue, venue)) or []
        out, seen = [], set()
        for f in self.P.get("facts") or []:
            g, fid = str(f.get("gist") or ""), f.get("id")
            base = re.sub(r"[a-z]$", "", str(fid))
            if fid and names and any(n in g for n in names) and AVOID.search(g) and base not in seen and PC.fact_context(self, fid) != "other":
                seen.add(base); out.append(fid)
        return out[:2]

    def ev_review(self, fids, what, target=None, strict=False, slot=None):
        """target(이 행동의 장소 · 상품 ID 집합)이 있으면 다른 장소에 관한 사실은 '후기에서 확인'으로 붙이지 않음(의미가 다른 활동에 끼워 맞추지 않음).
        CL-19 후속: 같은 작성자의 다른 호텔 · 장소 경험(출처 맥락 'other')이나 다른 끼니 경험(slot 불일치)은
        '후기에서 확인'이 아니라 '프로파일 기반 추론'(그 경험에서 확장)으로 표시한다 — 사실 ID 는 내부 extended_from 에만."""
        from . import profile_context as PC
        own = [f for f in dict.fromkeys(fids) if self.gist(f) and not OUT_OF_SCOPE.search(self.gist(f))]   # CL-1025-25 — 범위 밖 내용은 근거로 쓰지 않음
        fam_names = [n for x in (target or ()) for n in PLACE_NAMES.get(PLACE_FAMILY.get(x, x), [])]
        guest_now = self.stay and self.checked_in and not self.checked_out
        reasons = {}
        for f in own:
            ctx = PC.fact_context(self, f)
            g = self.gist(f)
            if self.author_pending:
                reasons[f] = AUTHOR_PENDING
            elif CONTEXT_ONLY.search(g) and not USE_DONE.search(g):
                reasons[f] = "시설 이용이 아닌 맥락(동선 · 위치 만족)"
            elif ctx == "other":
                reasons[f] = "다른 곳 경험"
            elif ctx is None:
                reasons[f] = "출처 매핑 미확정"
            elif PC.slot_mismatch(self.gist(f), slot):
                reasons[f] = "다른 끼니 경험"
            elif not guest_now and "투숙객" in self.gist(f):
                reasons[f] = "투숙 때 경험(이번 방문은 비투숙)"
            elif incomplete(g):   # CL-1025-30 — 휴관 · 관람 실패는 그 시설을 이용한 직접 경험이 아님(원자 사실 · 원문은 보존, 귀속만 바꿈)
                reasons[f] = INCOMPLETE_WHY
            elif NEG_DONE.search(self.gist(f)):
                reasons[f] = "하지 않았거나 다른 것으로 바꾼 경험"
            elif strict and slot and clause_transfer(g, fam_names, slot):   # CL-1025-25 — 같은 업장의 다른 메뉴 · 다른 끼니를 묶은 요약(A08S_E28)
                reasons[f] = TRANSFER_WHY
        ext = sorted([f for f in own if f in reasons], key=lambda f: reasons[f] in ("다른 곳 경험", "출처 매핑 미확정"))   # 같은 업장 맥락 이전 · 이용 아님 같은 구분을 앞에(4개 제한에 밀리지 않게)
        own = [f for f in own if f not in ext]
        if target:
            fam = set(target) | {PLACE_FAMILY.get(x, x) for x in target}
            own = [f for f in own if (not strict and not self.fact_places(f)) or ({PLACE_FAMILY.get(x, x) for x in self.fact_places(f)} & fam)]
            # strict(정량 엔진 성향 항의 근거): 이 장소 · 상품에 관한 사실만 '후기에서 확인' — 일반 성향 사실은 '프로파일 기반 추론'(성향 수준)으로만
        out = [dict(type="후기에서 확인", fact_ids=own[:4], about=what)] if own else []
        if ext:
            out.append(dict(type="프로파일 기반 추론", traits=[], about="후기 경험에서 확장한 추론(" + " · ".join(dict.fromkeys(reasons[f] for f in ext[:4])) + ")",
                            extended_from=ext[:4], ext_reasons={f: reasons[f] for f in ext[:4]}, **({"basis_kind": TRANSFER} if any(reasons[f] == TRANSFER_WHY for f in ext[:4]) else {})))
        return out

    # 실행 -------------------------------------------------------------
    def add(self, kind, code, label, loc, t0, dur, domain, source, why, evidence, internal=None, start_at=None, offer=None, in_package=False, fraction=None):
        last = next((x for x in reversed(self.log) if x["act"] != "move"), None)
        if code in REST_MERGE and last and last["act"] in REST_MERGE and last["loc"] == loc and last["e"] == mh(t0):
            last["e"] = mh(t0 + dur); last.setdefault("internal", {})["merged_min"] = last["internal"].get("merged_min", 0) + dur   # 같은 객실 휴식이 이어지면 한 덩어리로
            self.t = t0 + dur; self.fatigue = max(0.0, self.fatigue - dur / 40); self.steps += 1
            return last
        tr = SP.travel_min(self.loc, loc) if loc and self.loc and loc != self.loc else 0
        if tr:
            self.log.append(dict(t=mh(t0), e=mh(t0 + tr), act="move", label=f"이동 → {label}", loc_from=self.loc, loc=loc, domain="이동",
                                 source="world_rule", why="다음 행동 장소로 이동합니다.", evidence=[], internal=dict(travel_min=tr, travel_basis="지도 거리감 연출값")))
        s = t0 + tr
        if start_at is not None and start_at > s:
            self.log.append(dict(t=mh(s), e=mh(start_at), act="wait", label=f"{label} 시간 전 여유", loc=loc, domain="대기", source="world_rule",
                                 why=f"{label} 시작 시각 전까지 근처에서 쉬어 갑니다.", evidence=[], internal=dict(wait_min=start_at - s)))
            s = start_at
        rec = dict(t=mh(s), e=mh(s + dur), act=code, kind=kind, label=label, loc=loc, domain=domain, source=source, why=why, evidence=merge_evidence(evidence), internal=internal or {})
        if not any(e["type"] == "후기에서 확인" for e in rec["evidence"]):   # 후기 근거가 남지 않았으면 설명에서도 '후기에서 확인' 문구를 뺌
            rec["why"] = rec["why"].replace(" 후기에서도 같은 경험이 확인됩니다.", "").replace("후기에서도 같은 경험이 확인됩니다.", "")
        self.log.append(rec)
        if code not in ("move", "wait"):   # 출처(규칙 · LLM · 엔진)와 무관하게 같은 장부를 지남
            slot = LG.record_meal(self, code, kind, domain, s, fraction if fraction is not None else ((offer or {}).get("food") or {}).get("meal_fraction"))
            if slot:
                rec["meal_slot"] = slot
            ch = LG.charge(self, code, kind, loc, offer=offer, in_package=in_package)
            if ch.get("per") == "인" and ch.get("status") == "유료" and self.C["kids"]:   # CL-1025-24 — 아이 동반: 1인 요금 × 인원은 성인 기준 추정(아동 요금 · 구성 미확인)
                ch = dict(ch, party_estimate=True, party_note=f"성인 요금 × {self.N}인 기준 추정 — 성인 · 아동 구성과 아동 요금 미확인")
                self.spent_est += ch["krw"] or 0
            rec["charge"] = ch
            self.charges.append(dict(t=mh(s), act=code, label=label, **ch))
            if ch["krw"]:
                self.spent += ch["krw"]
        if not str(source).startswith("llm_plan") and source != "world_rule":   # 규칙 · 엔진 결정도 내부 추적(욕구 · 고려 대안 · 앞선 활동 · 사용 근거)
            iv = internal or {}
            alts = list((iv.get("weights") or {}).keys()) or [r.get("offer") for r in iv.get("alternatives", []) if isinstance(r, dict)] or []
            self.trace.append(dict(t=mh(s), backend=source, option=code, accepted=True, need=dict(hunger=round(getattr(self, "hunger_e", 0), 2), fatigue=round(self.fatigue, 2),
                                   meals={k: v for k, v in self.meals.items()}), alternatives=[x for x in alts if x and x != code][:6], prev=last["act"] if last else None,
                                   facts=[f for e in evidence if e.get("type") == "후기에서 확인" for f in e.get("fact_ids", [])],
                                   traits=[t_ for e in evidence if e.get("type") == "프로파일 기반 추론" for t_ in (e.get("traits") or [])]))
        self.loc = loc
        self.t = s + dur
        self.done.append(code)
        self.steps += 1
        self.fatigue = max(0.0, self.fatigue + EFFORT.get(code, EFFORT_DOMAIN.get(domain, 0.4)) * dur / 60 + tr / 60)   # 활동 강도별(쉬는 성격의 활동은 피로를 덜거나 줄임)
        if domain == "식사" or (code in SP.ACT and SP.ACT[code][2] in FOOD_KINDS):
            self.food.append((s + dur, loc))
        return rec

    def ctx(self):
        last = next((x for x in reversed(self.log) if x["act"] != "move"), None)
        return {"done": set(self.done), "fatigue": self.fatigue, "last_kind": SP.ACT[last["act"]][2] if last and last["act"] in SP.ACT else None, "stay": self.stay}


# ---------------------------------------------------------------- 후보 검증(월드 규칙)
def plan_ok(a, code, t, world, why_out, revisit=False):
    """revisit=True: 후기 근거가 있는 재방문(같은 시설 · 같은 업장) — 시설 하루 한 번 · 같은 업장 두 끼 검사를 건너뜀(나머지 월드 규칙은 그대로)."""
    name, locf, kind, dur, adult, _ = SP.ACT[code]
    loc = locf(a.B)
    if not revisit and code not in REPEATABLE and (code in a.done or SAME_FACILITY.get(code) in a.used):
        why_out[code] = "오늘 이미 이용"; return None
    if a.phase == "checkout" and not a.checked_out and t + SP.travel_min(a.loc, loc) + dur + SP.travel_min(loc, a.room) + 20 + SP.travel_min(a.room, SP.lobby(a.B)) + 20 > hm(CHECKOUT_BY):
        why_out[code] = "체크아웃(11:00) 전에 짐 정리 · 퇴실까지 마칠 수 없음"; return None
    if not revisit and code in LUNCH_ENGINE and LUNCH_ENGINE[code] in a.used:
        why_out[code] = "오늘 이미 이 업장에서 식사함"; return None
    if kind in FOOD_KINDS and code != "lunch_skip":
        if any(t - e < 90 for e, _ in a.food):
            why_out[code] = "방금 식사 · 간식을 함(90분 이내)"; return None
        if any(l == loc and t - e < 240 for e, l in a.food):
            why_out[code] = "조금 전 같은 곳에서 먹고 마심"; return None
    if code in SEASON_CLOSED:
        why_out[code] = SEASON_CLOSED[code]; return None
    if code in NOT_ELIGIBLE and not (code == "lounge" and a.club):
        why_out[code] = ("클럽 라운지는 클럽 객실 자격이 필요 — 이번 방문 조건은 클럽 객실이 아님(후기 숙박 조건으로 실행하면 후보)"
                         if code == "lounge" and a.review_stay.get("club") and not a.author_pending else NOT_ELIGIBLE[code]); return None
    if adult and a.C["kids"]:
        why_out[code] = "성인 전용"; return None
    lastx = next((x for x in reversed(a.log) if x["act"] not in ("move", "wait")), None)
    if code in ("room_rest", "room_bath") and lastx and lastx["act"] in ("room_rest", "room_bath", "ROOM_REST") and lastx["loc"] == loc:
        why_out[code] = "방금 객실에서 쉼(같은 자리 휴식을 새 활동으로 나누지 않음)"; return None
    if PLAN_DOMAIN.get(kind) == "웰니스" and sum(1 for x in a.log if x["domain"] == "웰니스") >= 2 and not a.P["fact_hits"].get(code):
        why_out[code] = "오늘 웰니스 2회 이상 — 이 시설 후기 근거 없이 더 늘리지 않음"; return None
    if code in ("room_rest", "room_bath"):
        rr = rest_ok(a, t)
        if rr:
            why_out[code] = rr; return None
    if code == "room_nap" and not a.C["kids"]:
        why_out[code] = "아이 동반이 아님(이 활동은 아이와 쉬는 시간)"; return None
    if code in NIGHT_FROM and t < hm(NIGHT_FROM[code]):
        why_out[code] = f"{NIGHT_FROM[code]} 뒤 활동"; return None
    bl = LG.blocked(a, loc)
    if bl:
        why_out[code] = bl; return None
    if loc in SP.GUEST_ONLY and (not a.stay or a.checked_out or not a.checked_in):
        why_out[code] = "투숙객 전용(체크인 전 · 퇴실 뒤 · 비투숙 불가)"; return None
    tr = SP.travel_min(a.loc, loc)
    s, e = t + tr, t + tr + dur
    if not (SP.WIN.get(loc) or SP.DEFAULT_WIN.get(loc)):
        why_out[code] = "운영시간 자료 없음(월드 · 검증기 미확인) — 임의 시간으로 열지 않음"; return None
    if not SP.open_at(loc, s, e):
        why_out[code] = "영업시간 밖"; return None
    cl = world.closed_at(t).get(loc)
    if cl and not (e <= cl[0] or s >= cl[1]):
        why_out[code] = "운영자 변경 — 이용 중지 시간"; return None
    lv = world.levers_at(t)
    if code == "forest_walk" and (lv.get("WINE_FAIR") or {}).get("available", True) and WD.default_world()["offers"][0]["window"] and s < hm("20:00") and (lv.get("WINE_FAIR") or {}).get("available") is not False:
        why_out[code] = "행사 날 포레스트 파크 일반 이용 제한(공식)"; return None
    if e > a.end:
        why_out[code] = "하루 끝을 넘김"; return None
    return loc


REST_KINDS = {"room_rest", "ROOM_REST", "room_bath", "room_nap", "idle"}


def late_breakfast(a):
    """아침을 실제로 늦게 먹었는지(10:00 이후 끝남) — 연박 중간일이라는 이유만으로 늦은 아침으로 보지 않음."""
    bf = next((x for x in a.log if x.get("meal_slot") == "breakfast"), None)
    return bool(bf and hm(bf["e"]) >= hm("10:00"))


def rest_ok(a, t):
    """쉬는 행동(객실 휴식 · 욕조 · 제자리 휴식)을 새로 넣을 이유가 있는지 — 휴식을 막지 않고 '이유 없는 반복'만 막음.
    이유 = 지침(피로가 개인 한도의 절반 이상) · 앞선 활동이 몸을 많이 씀 · 방금 식사."""
    r = a.fatigue / max(0.8, a.rest_limit)
    lastx = next((x for x in reversed(a.log) if x["act"] not in ("move", "wait")), None)
    if not lastx or t >= hm("21:30"):   # 밤에는 객실로 돌아가 쉬는 것이 하루 마무리(반복 휴식으로 보지 않음)
        return None
    last_rest_end = max([hm(x["e"]) for x in a.log if x["act"] in REST_KINDS] or [-999])
    prev_effort = EFFORT.get(str(lastx["act"]).split(":")[0], EFFORT_DOMAIN.get(lastx["domain"], 0.4))
    if lastx["act"] in REST_KINDS and r < 0.8:
        return "방금 쉬었음(이어서 또 쉴 만큼 지치지 않음)"
    if t - last_rest_end < 90 and r < 0.8:
        return "쉰 지 90분이 안 됨 · 아직 지치지 않음"
    if r < 0.35 and prev_effort < 0.6 and lastx["domain"] != "식사":
        return "아직 쉴 만큼 지치지 않음(피로 · 앞선 활동 · 식사 이유 없음)"
    return None


def merge_evidence(ev):
    """화면 근거는 두 라벨 각 한 덩어리로 — '후기에서 확인' 사실 ID 합치기 · '프로파일 기반 추론' 성향 · 확장 근거 합치기(중복 라벨 방지)."""
    rv = [e for e in ev or [] if e.get("type") == "후기에서 확인"]
    inf = [e for e in ev or [] if e.get("type") == "프로파일 기반 추론"]
    out = []
    if rv:
        out.append(dict(type="후기에서 확인", fact_ids=list(dict.fromkeys(f for e in rv for f in e.get("fact_ids", [])))[:4], about=rv[0].get("about")))
    if inf:
        m = dict(type="프로파일 기반 추론", traits=sorted({t for e in inf for t in (e.get("traits") or [])}),
                 about=" · ".join(dict.fromkeys(e.get("about") for e in inf if e.get("about"))))
        ext = list(dict.fromkeys(f for e in inf for f in e.get("extended_from", [])))
        if ext:
            m["extended_from"] = ext[:4]; m["ext_reasons"] = {k: v for e in inf for k, v in (e.get("ext_reasons") or {}).items() if k in ext[:4]}
        if any(e.get("basis_kind") for e in inf):
            m["basis_kind"] = next(e["basis_kind"] for e in inf if e.get("basis_kind"))
        out.append(m)
    out += [e for e in ev or [] if e.get("type") in ("후기 회피 근거", "불확실")]   # CL-1025-24 — 회피(부정) 근거 · 불확실 표시는 따로 남김
    return out


def plan_choose(a, t, world, codes, wfn, domain_hint=None):
    rej = {}
    ok = [(c, plan_ok(a, c, t, world, rej)) for c in codes]
    ok = [(c, l) for c, l in ok if l]
    for c, _ in list(ok):
        if wfn(c) <= 0:
            rej[c] = "성향 · 동행 · 상황상 후보가 아님(적합도 0 이하)"
    ok = [(c, l) for c, l in ok if wfn(c) > 0]
    if not ok:
        return None, rej
    rng = random.Random(f"{a.rng_base}|{t}|{a.steps}|{','.join(sorted(a.done))}")   # 같은 상태 → 같은 선택(개별 · 동시 실행 동일)
    c = SP.pick(rng, [c for c, _ in ok], wfn)[0]
    return (c, dict(ok)[c], {x: round(wfn(x), 3) for x, _ in ok}), rej


def plan_do(a, code, loc, t, weights, rej, source="planner_rules", note=None):
    name, _, kind, dur, _, _ = SP.ACT[code]
    why, traits = SP.why(code, a.P, a.C, a.ctx())
    LUNCH_PLACE = {"lunch_ondal": "온달에서", "lunch_geumryong": "금룡에서", "lunch_myongwol": "명월관에서", "lunch_moegi": "모에기에서", "lunch_pizzahill": "피자힐에서",
                   "lunch_bakery": "르 파사쥬 빵 · 샌드위치로 가볍게", "lunch_cafe": "더 파빌리온에서 가볍게", "lunch_room": "객실에서 간단히", "lunch_outside": "호텔 밖에서"}
    if code == "lunch_skip":
        bf = next((x for x in a.log if x.get("meal_slot") == "breakfast"), None)
        snack = next((x for x in reversed(a.log) if x["domain"] == "카페" and t - hm(x["e"]) <= 120), None)
        lead = ("아침을 늦게 먹어 " if late_breakfast(a) else
                f"조금 전 {snack['label']}{SP.josa(snack['label'], '으로', '로')} 출출함을 달래 " if snack else
                f"{bf['label']}{SP.josa(bf['label'], '으로', '로')} 아침을 먹었고 " if bf else "")   # 실제로 한 일만(양 · 포만감은 단정하지 않음)
        why = f"{lead}점심은 따로 챙기지 않고 오후에 출출하면 간단히 먹기로 합니다." + (" 후기에서도 같은 경험이 확인됩니다." if code in a.P["fact_hits"] else "")
    elif code in LUNCH_PLACE:
        tl = " · ".join(SP.BAR_LABEL.get(k) or SP.FACET_LABEL.get(k) for k in traits)
        why = f"{(tl + ' 성향이라 ') if tl else ''}점심은 {LUNCH_PLACE[code]} 먹습니다." + (" 후기에서도 같은 경험이 확인됩니다." if code in a.P["fact_hits"] else "")
    ev = a.ev_review(a.P["fact_hits"].get(code, []), f"{name} 관련 이전 경험", target={code, loc}, slot=LG.meal_slot(t) if PLAN_DOMAIN.get(kind) == "식사" else None)
    un = [f for f in (getattr(a, "obs_unspec", {}) or {}).get(code, []) if f not in {i for e in ev for i in (e.get("fact_ids") or []) + (e.get("extended_from") or [])}]
    if un:   # CL-1025-31 — 장소 미특정 관측(예: '근처 카페')은 이 업장 직접 근거 · 선택 가중이 아니라 같은 종류 활동 관측으로만 표시
        ev.append(dict(type="프로파일 기반 추론", traits=[], about="같은 종류 활동의 관측 경험(장소 미특정)", extended_from=un[:4], ext_reasons={f: UNSPEC_WHY for f in un[:4]}))
    if traits:
        ev.append(dict(type="프로파일 기반 추론", traits=traits, about="누적 프로파일 성향"))
    if not ev:
        ev.append(dict(type="프로파일 기반 추론", traits=[], about="동행 · 시간 · 피로 등 현재 상황"))
    if SAME_FACILITY.get(code) and code != "room_rest":
        a.used.add(SAME_FACILITY[code])
    if code in LUNCH_ENGINE:
        a.used.add(LUNCH_ENGINE[code])
    why = why.replace("을 이어 갑니다.", "을 즐깁니다.").replace("를 이어 갑니다.", "를 즐깁니다.").replace("을 합니다.", "을 즐깁니다.").replace("를 합니다.", "를 즐깁니다.")
    why = why.replace("저녁 산책 · 야경을", f"{tod(t)} 산책을") if code == "night_walk" and t < hm("18:00") else why
    if "피로가 쌓여 객실에서" in why and not code.startswith("room"):
        why = why.replace("객실에서 쉬어 갑니다.", f"{name}{SP.josa(name, '으로', '로')} 조용히 쉬어 갑니다.")
    a.add("activity", code, name, loc, t, dur, PLAN_DOMAIN.get(kind, kind), source, why, ev,
          dict(weights=weights, rejected=rej, note=note))


# ---------------------------------------------------------------- 엔진 결정(지원 상품)
def turn_raw(a, d_terms, rejected, chosen, o, w, t, world_kind, score, total=None):
    """CL-1024-22R — 고객 흐름 화면용 정량 결정 기록: 항별 값을 공통 · 후기 근거 · 설계 가정 몫으로 나눈다(turn_view.split_reason 과 같은 규칙 · 계산 변경 없음).
    공통 몫 = 후기 근거가 없는 성향으로 같은 시각 · 같은 월드에서 계산한 같은 항의 값."""
    from ..operator_world_v1_1 import turn_view as TV
    try:
        if world_kind == "breakfast":
            base = TV.common_baseline(o, a.visit_e, w, "breakfast")
        else:
            with candidate_engine(c1=True, c2="venue_visits", c3=True):
                bt = EN.score(o, t, dict(used=set(), hunger=1.0), dict(a.visit_e, checkin=mh(t)), TV._empty_traits(), w)
            base = {}
            for x in bt:
                base[x["factor"]] = base.get(x["factor"], 0.0) + x["value"]
    except Exception:
        base = {}
    terms = []
    slot = "breakfast" if world_kind == "breakfast" else (LG.meal_slot(t) if ENGINE_DOMAIN.get(chosen) == "식사" else None)
    names = list(dict.fromkeys(PLACE_NAMES.get(PLACE_FAMILY.get(chosen, chosen), []) + PLACE_NAMES.get(PLACE_FAMILY.get(o.get("venue"), o.get("venue")), [])))
    for x in d_terms:
        r = dict(factor=x["factor"], value=round(x["value"], 4), facet=x.get("facet"), fact_ids=list(x.get("fact_ids", [])), note=x.get("note", ""))
        parts = TV.split_reason(r, o, base)
        # CL-1025-26 — 후기 근거 몫의 출처를 사실별로 나눈다(엔진 값 · 몫의 합은 그대로 · 표시가 아니라 분류):
        #   CONTEXT_TRANSFER_INFERENCE = 같은 업장의 다른 메뉴 · 다른 끼니 요약(이 상품 직접 경험 아님) → parts.transfer
        #   OUT_OF_SCOPE = 범위 밖 과거 경험(포장 · 대기 감수) — 동결 입력이라 점수에 남음 → parts.out_of_scope + SCORE_PROVENANCE_CONFLICT
        prov = {}
        if parts.get("review") and r["fact_ids"]:
            for f in r["fact_ids"]:
                g = a.gist(f) or ""
                prov[f] = "OUT_OF_SCOPE" if OUT_OF_SCOPE.search(g) else "NOT_DONE" if ("실제 이용" in r["note"] and (NEG_DONE.search(g) or incomplete(g))) else TRANSFER if (slot and clause_transfer(g, names, slot)) else "REVIEW"
        if prov and any(v != "REVIEW" for v in prov.values()):
            ev_mass = {e.get("fact_id"): float(e.get("mass") or 1.0) for e in (((a.traits.get("facets") or {}).get(r["facet"]) or {}).get("evidence") or [])}
            m = {f: ev_mass.get(f, 1.0) for f in prov}; tot = sum(m.values()) or 1.0
            rv = parts["review"]
            sh = {k: round(rv * sum(m[f] for f in prov if prov[f] in ((k,) if k != "OUT_OF_SCOPE" else ("OUT_OF_SCOPE", "NOT_DONE"))) / tot, 4) for k in ("REVIEW", TRANSFER, "OUT_OF_SCOPE")}
            parts = dict(parts, review=round(rv - sh[TRANSFER] - sh["OUT_OF_SCOPE"], 4), transfer=sh[TRANSFER], out_of_scope=sh["OUT_OF_SCOPE"])
            r["provenance"] = prov
            r["share_basis"] = "후기 근거 몫을 근거 질량 비율로 사실별 배분(엔진 값 불변)"
            if sh["OUT_OF_SCOPE"]:
                cf = [f for f in prov if prov[f] in ("OUT_OF_SCOPE", "NOT_DONE")]
                r["score_provenance_conflict"] = dict(code="SCORE_PROVENANCE_CONFLICT", amount=sh["OUT_OF_SCOPE"], fact_ids=cf, kinds={f: prov[f] for f in cf},
                                                      why="범위 밖 과거 경험 · 하지 않은 경험이 동결 입력(R-BASE 성향 수준 · 업장 이용 기록)에 들어 있어 점수에 남음 — 빼면 점수가 바뀌므로 관제 승인 대상")
            if "실제 이용" in r["note"] and any(prov[f] == "NOT_DONE" for f in prov):   # C-2 업장 이용 횟수가 하지 않은 경험에서 나온 경우
                r["engine_note"] = r["note"]
                r["note"] = f"{VENUE_KO.get(o.get('venue'), o.get('venue'))} 직접 이용 0회 — 엔진 입력의 '업장 이용 1회'는 하지 않은(포기한) 경험에서 나옴 · 출처 충돌"
                r["product_direct_visits"] = 0
            if sh[TRANSFER] and "실제 이용" in r["note"] and "engine_note" not in r:   # C-2 업장 이용 횟수 항: 업장 단위 이용이지 이 상품 이용이 아님
                n = re.search(r"실제 이용 (\d+)회", r["note"])
                r["engine_note"] = r["note"]
                r["note"] = f"{VENUE_KO.get(o.get('venue'), o.get('venue'))} 업장 이용 {n.group(1) if n else '?'}회(다른 메뉴 · 다른 끼니 — 맥락 이전 추론) · 이 상품 직접 이용 0회"
                r["product_direct_visits"] = 0
        shown = [f for f in r["fact_ids"] if not OUT_OF_SCOPE.search(a.gist(f) or "")] if parts["review"] or parts.get("transfer") else []   # 범위 밖 사실은 근거 목록에 싣지 않음(충돌 항목에 ID 만)
        terms.append(dict(r, parts=parts, cls=TV.classify(parts), fact_ids=shown, **({"hidden_fact_n": len(r["fact_ids"]) - len(shown)} if (parts["review"] or parts.get("transfer") or parts.get("out_of_scope")) and len(shown) < len(r["fact_ids"]) else {})))
    return dict(world=world_kind, chosen=chosen, score=round(score, 4) if score is not None else None, total=round(total, 4) if total is not None else None,
                terms=terms, rejected=[dict(offer=r.get("offer") or r.get("id"), feasible=bool(r.get("feasible")), score=r.get("score"), total=r.get("total"),
                                            blocked=list(r.get("blocked") or ([r["major_reason"]] if r.get("major_reason") and not r.get("feasible") else []))) for r in rejected])


def engine_world_for(a, world, t):
    w = world.engine_world(t)
    offers = []
    for o in w["offers"]:
        if o["id"] in GUEST_ENGINE and (not a.stay or a.checked_out) and o["id"] != "ROOM_REST":
            continue
        if o["id"] in ENGINE_ADULT and a.C["kids"]:
            continue   # CL-1025-23 — 계획기의 '성인 전용'(사우나 · 피트니스 · 럭스바)과 같은 기준을 정량 엔진 후보에도(아이 동반이면 사우나 상품 제외)
        if o.get("kind") == "event" and o.get("available") and LG.event_blocked(a, o["id"]):
            continue   # 행사 출입표(EVENT_ACCESS)에 근거가 없거나 이 고객 칸이 불가
        place = SP.pool(a.B) if o["id"] == "POOL" and a.B else LG.ENGINE_PLACE.get(o["id"])
        if place and LG.blocked(a, place):
            continue   # 검증기 출입표 '불가'(예: 비투숙 → 스카이야드 · 포레스트 파크)
        cl = world.closed_at(t).get(SP.pool(a.B) if o["id"] == "POOL" else ENGINE_LOC.get(o["id"], ""))
        if cl and o["window"]:
            continue   # 운영자 이용 중지(간단히: 해당 시간대가 걸리면 후보 제외)
        is_meal = o.get("kind") in ("restaurant", "room_meal", "simple_meal")   # 행사의 곁들임 음식(와인페어 0.15)은 식사 규칙 대상이 아님
        if is_meal and any(t - e < 90 for e, _ in a.food):
            continue
        floc = a.room if ENGINE_LOC.get(o["id"]) == "@room" else ENGINE_LOC.get(o["id"], o["venue"])
        if is_meal and any(l == floc and t - e < 240 for e, l in a.food):
            continue   # 같은 곳에서 4시간 안에 먹었으면 그곳 식사 상품은 후보가 아님(계획기 규칙과 같은 기준)   # 방금(90분 이내) 먹었으면 다른 식사 상품은 아직 후보가 아님(계획기 음식 규칙과 같은 기준)
        if o["id"] in a.checked:
            o = dict(o, _checked=True)
        if EVENT_FEE_DECISION and o["id"] in LG.EVENT_FEE and LG.guest_class(a) != "non_guest":
            o = dict(o, price_pp_krw=0)   # 승인 전 기본 꺼짐 — 투숙객 무료 입장을 판단 점수에도 반영하는 격리 오버라이드(자율 하루 경로 한정)
        offers.append(o)
    return dict(w, offers=offers)


def engine_step(a, world, t):
    w = engine_world_for(a, world, t)
    st = dict(used=set(a.used), hunger=a.hunger_e)
    closed = [o["id"] for o in world.engine_world(t)["offers"] if o["window"] and world.closed_at(t).get(SP.pool(a.B) if o["id"] == "POOL" else ENGINE_LOC.get(o["id"], ""))]
    if closed:   # 운영자 마감이 걸린 상품 — 마감이 없었다면 그것을 골랐을지 먼저 본다(이용 포기 · 대안 기록)
        full = world.engine_world(t)
        full = dict(full, offers=[(dict(o, _checked=True) if o["id"] in a.checked else o) for o in full["offers"] if not (o["id"] in GUEST_ENGINE and (not a.stay or a.checked_out) and o["id"] != "ROOM_REST")])
        try:
            with candidate_engine(c1=True, c2="venue_visits", c3=True):
                d0 = EN.decide_at(t, dict(st), dict(a.visit_e, checkin=mh(t)), a.traits, full)
            if d0["chosen"] in closed and d0["chosen"] not in a.gave_up:
                a.gave_up.add(d0["chosen"])
                o0 = next(x for x in full["offers"] if x["id"] == d0["chosen"])
                a.add("abandon", d0["chosen"] + ":full", f"{o0['label']} 문의 · 마감으로 포기", a.loc, t, 5, "포기", "world_rule",
                      f"{VENUE_KO.get(o0['id'], o0['label'])}에 가려 했지만 이 시간대가 마감이라 다른 곳을 찾습니다.",
                      a.ev_review([e["fact_id"] for r in d0["reasons"] if r["value"] > 0 for e in r.get("evidence", []) if e.get("fact_id")], "원래 끌렸던 이유", target={d0["chosen"]}),
                      dict(blocked_offer=d0["chosen"], reason="운영자 마감(예약 · 수용 불가 가정)"))
                t = a.t
        except IndexError:
            pass
    try:
        with candidate_engine(c1=True, c2="venue_visits", c3=True):
            d = EN.decide_at(t, st, dict(a.visit_e, checkin=mh(t)), a.traits, w)
    except IndexError:   # 이 시각 엔진 지원 상품이 모두 불가(종료 · 이미 이용 · 내다보기 끝) → 엔진 밖 활동 · 휴식으로 넘김
        return None, w
    return d, w


def engine_do(a, d, w, t):
    o = next(x for x in w["offers"] if x["id"] == d["chosen"])
    loc = ENGINE_LOC.get(o["id"], o["venue"])
    loc = a.room if loc == "@room" else SP.pool(a.B) if loc == "@pool" else loc
    starts, ends = hm(d["starts"]), hm(d["ends"])
    pos = [r for r in d["reasons"] if r["value"] > 0 and r["layer"] != "불확실"]
    fids = [e["fact_id"] for r in pos for e in r.get("evidence", []) if e.get("fact_id")]
    traits_used = sorted({r.get("facet") for r in pos if r.get("facet") and r.get("evidence")})
    prof = [r for r in pos if "프로필" in r["layer"]]   # 고객 성향 항만 설명의 앞에(끼니 해결 같은 공통 조건은 내부 기록)
    top = [r["text"].split(" — ")[0] for r in (prof or pos)[:2]]
    browse = d.get("stage") == EN.CHECK_STAGE
    if browse:
        why = f"{o['label']} 안내를 먼저 확인해 봅니다 — {', '.join(top) or '관심'} 쪽으로 마음이 기울지만 직접 보고 정하려 합니다."
        dur = EN.BROWSE_MIN
    else:
        lead = " · ".join(top)
        pre = f"{lead}{SP.josa(lead, '을', '를')} 중시하는 성향이라 " if lead and prof else ""
        dom = ENGINE_DOMAIN.get(o["id"])
        after_dinner = dom == "식사" and a.meals.get("dinner") and starts >= hm("16:30")
        heavy_lunch = any(m["slot"] == "lunch" and m["size"] == "full" for m in a.meal_log)
        if after_dinner:   # CL-1025-23 — 이미 저녁을 먹은 뒤의 식사 상품은 '저녁'이 아니라 늦은 간식 · 야식으로
            why = f"{pre}저녁 뒤 출출해 {'객실에서 룸서비스로' if o['id'] == 'ROOM_MEAL' else VENUE_KO.get(o['id'], o['label']) + '에서'} 가볍게 더 먹습니다."
        elif dom == "식사" and o["food"]["meal_fraction"] < 0.8:
            why = (f"점심을 든든히 먹어 저녁은 {VENUE_KO.get(o['id'], o['label'])}에서 간단히 요기합니다." + (f" {lead}{SP.josa(lead, '을', '를')} 중시하는 성향에도 맞는 곳입니다." if lead and prof else "") if heavy_lunch and starts >= hm("16:30")
                   else f"{pre}{VENUE_KO.get(o['id'], o['label'])}에서 간단히 요기합니다.")
        elif dom == "식사":
            why = f"{pre}저녁은 객실에서 룸서비스로 해결합니다." if o["id"] == "ROOM_MEAL" else f"{pre}저녁은 {VENUE_KO.get(o['id'], o['label'])}에서 먹습니다."
        elif dom == "객실 휴식":
            why = f"{pre}객실로 돌아와 쉬어 갑니다." if pre else "다른 일정보다 객실에서 쉬는 쪽을 택합니다."
        elif dom == "행사":
            why = f"{pre}{o['label']}에 참여합니다."
        else:
            why = f"{pre}{o['label']}{SP.josa(o['label'], '을', '를')} 즐깁니다."
        dur = ends - starts
    ev = a.ev_review(fids, "이 선택을 뒷받침한 후기 사실", target={o["id"], loc}, strict=True, slot=LG.meal_slot(starts) if ENGINE_DOMAIN.get(o["id"]) == "식사" else None)
    if traits_used or not ev:
        ev.append(dict(type="프로파일 기반 추론", traits=traits_used, about="정량 엔진의 성향 항(후기 근거로 측정한 수준)"))
    # CL-1025-24 — 식사 결정: 근소한 대안 · 회피(부정) 근거를 문장과 근거에 따로(점수 · 선택은 엔진 그대로)
    if not browse and ENGINE_DOMAIN.get(o["id"]) == "식사" and not after_dinner:
        alts = sorted([r for r in d.get("rejected", []) if r.get("feasible") and r.get("total") is not None and r["offer"] != o["id"]], key=lambda r: -r["total"])
        avoid = {r["offer"]: a.avoid_facts(r["offer"]) for r in alts if r["offer"] in VENUE_KO}
        avoid = {k: v for k, v in avoid.items() if v}
        my = d.get("total") if d.get("total") is not None else d["score"]
        near = next((r for r in alts if r["offer"] in VENUE_KO and r["offer"] not in avoid), None)
        if near and my - near["total"] < 0.3:
            wn = str(near.get("major_reason") or "")
            tail = "1인 가격 부담이 조금 더 커 이쪽을 택합니다" if "지불액" in wn else "야경 · 분위기 면에서 이쪽이 조금 낫다고 봅니다" if ("야경" in wn or "공간" in wn) else "이쪽을 택합니다"
            why += f" {VENUE_KO[near['offer']]}도 거의 비슷하게 끌렸지만 {tail}."
        for v, fs in avoid.items():
            why += f" {VENUE_KO[v]}{SP.josa(VENUE_KO[v], '은', '는')} 지난 방문 뒤 다시 오지 않겠다고 한 곳이라 고르지 않습니다."
            ev.append(dict(type="후기 회피 근거", fact_ids=fs, venue=v, about=f"{VENUE_KO[v]} — 후기에서 다시 오지 않겠다고 한 곳(직접 경험 · 고르지 않은 이유)"))
    if not browse and o["id"] == "WINE_FAIR" and a.C["kids"]:
        why += " 아이 동반 입장 규칙은 확인되지 않아, 가족 중 누가 함께 들어가는지는 정하지 않았습니다."
        ev.append(dict(type="불확실", about="영유아 동반 가족 — 행사의 아동 입장 · 동반 규칙 자료 없음. 가족 전체 입장으로 확정하지 않음 · 동반 인원 · 아동 요금 미확인(재판정 대상)"))
    internal = dict(engine="operator_world_v1.decide_at + C-1/2/3", score=d["score"], total=d.get("total"), margin=d.get("margin"), runner_up=d.get("runner_up"),
                    stage=d.get("stage"), price_pp_krw=o["price_pp_krw"], price_grade=o["price_source"].get("grade"), next_plan=d.get("next_plan"),
                    event_view=[x for x in d.get("event_stages", []) if x.get("offer") == "WINE_FAIR"],
                    alternatives=sorted([dict(offer=r["offer"], total=r.get("total"), why_not=r.get("major_reason")) for r in d.get("rejected", []) if r.get("feasible")], key=lambda r: -(r["total"] or -9))[:5],
                    terms=[dict(text=r["text"], value=round(r["value"], 3), layer=r["layer"], fact_ids=[e.get("fact_id") for e in r.get("evidence", [])]) for r in d["reasons"][:6]])
    internal["turn_raw"] = turn_raw(a, d.get("terms") or [], d.get("rejected") or [], o["id"], o, w, t, "operator", d["score"], d.get("total"))
    rec = a.add("engine", o["id"] + (":check" if browse else ""), o["label"] + (" · 안내 확인" if browse else ""), loc, t, dur, ENGINE_DOMAIN.get(o["id"], "기타"), "quantitative_engine", why, ev, internal,
                start_at=None if browse else starts, offer=None if browse else o)
    if browse:
        a.checked.add(o["id"])
        return rec
    a.used.add(o["id"])
    for pc, eid in SAME_FACILITY.items():
        if eid == o["id"] and pc != "room_rest":
            a.done.append(pc)
    if o["food"]["meal_fraction"] > 0 and starts < hm(w["dinner_window"]["end"]):
        a.hunger_e = max(0.0, round(a.hunger_e - o["food"]["meal_fraction"], 4))

    return rec


def breakfast_step(a, world, t):
    """아침 — 기존 아침 턴과 같은 정량 판단(조식 뷔페 · 룸서비스 조식 · 건너뜀)."""
    from ..operator_world_v1_1 import turn_candidate as TC
    lv = {"BREAKFAST_BUFFET": {"in_package": True}} if world.sc.get("breakfast_in_package") else {}
    w, _ = TC.turn_world("breakfast", "historical", a.N, product_levers=lv)
    d = TC.decide_turn(a.traits, dict(a.visit_e, checkin="07:00"), w, "breakfast", dict(used=set(a.used), hunger=1.0))
    ch = d["chosen"]
    o = next(x for x in w["offers"] if x["id"] == ch["id"])
    loc = a.room if o["kind"] in ("room_meal", "rest") else ENGINE_LOC.get(o["id"], o["venue"])
    pos = sorted([r for r in d.get("reasons", []) if r.get("value", 0) > 0], key=lambda r: -r["value"])
    fids = [f for r in pos for f in r.get("fact_ids", [])]
    prof = [r for r in pos if r.get("fact_ids")]
    lead = " · ".join(r["factor"] for r in prof[:2])
    skip = ch["id"] == "SKIP_BREAKFAST"
    why = ("아침은 건너뛰고 객실에서 여유롭게 쉽니다." if skip else f"{(lead + SP.josa(lead, '을', '를') + ' 중시하는 성향이라 ') if lead else ''}아침은 {o['label']}{SP.josa(o['label'], '으로', '로')} 먹습니다.")
    ev = a.ev_review(fids, "아침 선택을 뒷받침한 후기 사실", target={ch["id"], loc}, strict=True, slot="breakfast") or [dict(type="프로파일 기반 추론", traits=sorted({r.get('facet') for r in pos if r.get('facet')}), about="아침 식사 성향")]
    a.add("engine", ch["id"], o["label"], loc, t, o["duration_min"], "식사" if not skip else "객실 휴식", "quantitative_engine", why, ev,
          dict(engine="turn_candidate.decide_turn(breakfast)", score=ch.get("score"), price_grade=o["price_source"].get("grade") if o.get("price_source") else None, assumption="조식 객실 포함" if lv else None,
               turn_raw=turn_raw(a, d.get("reasons") or [], [dict(offer=x["id"], feasible=x["feasible"], score=x.get("score"), blocked=x.get("blocked")) for x in d.get("not_chosen", [])], ch["id"], o, w, t, "breakfast", ch.get("score")),
               breakfast_levers=lv), offer=o, in_package=bool(lv) and ch["id"] == "BREAKFAST_BUFFET")


# ---------------------------------------------------------------- 하루 진행(한 번의 결정)
def checkout_now(a, t):
    a.add("activity", "pack", "짐 정리", a.room, t, 20, "객실 휴식", "obligation", "퇴실 준비를 합니다.", [])
    a.add("activity", "checkout", "체크아웃", SP.lobby(a.B), a.t, 20, "체류", "obligation", "체크아웃합니다.", [])
    a.checked_out = True; a.room = None
    a.end = hm("15:30") if "linger" in a.P["fact_hits"] else hm("14:00")


def need_checkout(a, t):
    need = SP.travel_min(a.loc, a.room) + 20 + SP.travel_min(a.room, SP.lobby(a.B)) + 20
    return t + need >= hm(CHECKOUT_BY) - 15


def end_day(a, why=None):
    """하루 끝 상태를 분명히 — 비투숙 · 퇴실 고객은 귀가, 투숙 고객은 취침."""
    if a.phase == "visit" or a.checked_out:
        if not a.left:
            a.add("activity", "leave", "귀가", "HOTEL_GATE", a.t, 15, "체류", "obligation", "일정을 마치고 호텔을 나섭니다.", []); a.left = True
    elif not any(x["act"] == "sleep" for x in a.log):
        a.add("activity", "sleep", "객실 복귀 · 취침", a.room, a.t, 15, "객실 휴식", "obligation", why or "하루를 마무리하고 쉽니다.", [])
    a.ended = True


def rest_break(a, t, world):
    """피로가 이 고객의 페이스를 넘으면 쉬어 간다 — 투숙 고객은 객실, 그 밖에는 카페 · 라이브러리 · 벤치."""
    ev = [dict(type="프로파일 기반 추론", traits=[k for k in ("rest_need", "warm_rest") if (a.P["bars"].get(k) or a.P["facets"].get(k) or 0) >= 0.3], about="연이은 활동 뒤 피로 · 휴식 페이스")]
    if a.stay and a.checked_in and not a.checked_out:
        dur = 60 if a.fatigue >= a.rest_limit + 1 else 45
        prev = next((x for x in reversed(a.log) if x["act"] not in ("move", "wait")), None)
        pl = (prev or {}).get("label", "").split("(")[0].strip()
        why = f"{pl}{SP.josa(pl, '을', '를')} 마치고 나니 피곤해 객실에서 잠시 쉬어 갑니다." if pl else "객실에서 잠시 쉬어 갑니다."
        if prev and str(prev.get("act", "")).endswith(":check"):
            why = f"{pl} 안내를 확인하고 나니 피곤해 객실에서 잠시 쉬어 갑니다."
        if prev and prev.get("domain") == "식사":
            why = f"{pl}{SP.josa(pl, '으로', '로')} 배를 채우고 객실에서 잠시 쉬어 갑니다."
        a.add("activity", "room_rest", "객실 휴식", a.room, t, dur, "객실 휴식", "planner_rules", why, ev, dict(fatigue=round(a.fatigue, 2), rest_limit=a.rest_limit, note="피로 한도 초과 휴식", after=(prev or {}).get("act")))
        return True
    rej = {}
    for code in ("library", "cafe"):
        loc = plan_ok(a, code, t, world, rej)
        if loc:
            plan_do(a, code, loc, t, {}, rej, note="피로 한도 초과 — 앉아서 쉬는 곳"); return True
    a.add("wait", "idle", "벤치에서 쉬어 감", "AG_GARDEN", t, 30, "휴식", "planner_rules", "많이 걸어 다리를 쉬어 갑니다.", ev, dict(fatigue=round(a.fatigue, 2))); return True


def decide(a, world):
    t = a.t
    if a.ended or a.left:
        return False
    if t >= a.end:
        end_day(a); return True
    # 의무 행동
    if a.phase == "checkin" and not a.checked_in:
        if a.loc == "HOTEL_GATE" and not a.done:
            a.add("activity", "arrive", "호텔 도착", "HOTEL_GATE", t, 15, "체류", "obligation", "호텔에 도착했습니다.", []); return True
        ci = max(t, hm("15:00"))
        if ci > t:   # 체크인 전 — 로비 · 카페 등 투숙객 전용이 아닌 곳에서 시간을 보냄
            r, rej = plan_choose(a, t, world, ["cafe", "bakery", "garden_walk", "theatre", "tennez"], lambda c: SP.act_weight(c, a.P, a.C, a.ctx()))
            if r and t + SP.travel_min(a.loc, r[1]) + SP.ACT[r[0]][3] <= ci + 30:
                plan_do(a, r[0], r[1], t, r[2], rej, note="체크인 전 시간"); return True
            a.add("wait", "wait", "체크인 시각까지 로비에서 대기", SP.lobby(a.B), t, ci - t, "대기", "world_rule", "체크인(15:00)까지 로비에서 기다립니다.", []); return True
        a.add("activity", "checkin", "체크인", SP.lobby(a.B), t, 20, "체류", "obligation", f"{SP.BLD_KO.get(a.B, a.B)}에 체크인합니다.", [])
        a.checked_in = True
        a.add("activity", "unpack", "객실 짐 정리 · 휴식", a.room, a.t, 35, "객실 휴식", "obligation", "객실에 들어가 짐을 풉니다.", []); return True
    if a.phase == "visit" and not a.done:
        a.add("activity", "arrive", "호텔 도착", "HOTEL_GATE", t, 15, "체류", "obligation", "호텔에 도착했습니다.", []); return True
    if a.phase in ("mid", "checkout") and not a.done:
        a.add("activity", "wake", "기상 · 준비", a.room, t, 40, "객실 휴식", "obligation", "일어나 하루를 준비합니다.", []); return True
    if a.phase in ("mid", "checkout") and not a.meals["breakfast"] and a.t < hm("10:00"):
        breakfast_step(a, world, a.t); return True
    if a.phase == "checkout" and not a.checked_out and need_checkout(a, t):
        checkout_now(a, t); return True
    # 귀가 판단(비투숙 · 퇴실 뒤)
    if (a.phase == "visit" or a.checked_out):
        late = t >= (a.end - 20) or (a.phase == "visit" and a.meals["dinner"] and t >= hm("19:30")) or (a.phase == "visit" and t >= hm("21:30"))
        if late or (a.fatigue >= a.rest_limit + 1.2 and a.steps >= 4):
            a.add("activity", "leave", "귀가", "HOTEL_GATE", t, 15, "체류", "obligation" if late else "planner_rules",
                  "일정을 마치고 호텔을 나섭니다." if late else "많이 움직여 지쳐 예정보다 일찍 귀가합니다.", [] if late else [dict(type="프로파일 기반 추론", traits=["rest_need"], about="피로 상태")])
            a.left = True; a.ended = True; return True
    # 취침
    if a.stay and not a.checked_out and t >= hm("22:30"):
        a.add("activity", "sleep", "객실 복귀 · 취침", a.room, t, max(15, a.end - t), "객실 휴식", "obligation", "하루를 마무리하고 쉽니다.", []); a.t = a.end; a.ended = True; return True
    # 피로 한도
    if a.fatigue >= a.rest_limit and t < hm("22:00"):
        return rest_break(a, t, world)
    # LLM 계획 계층(켜져 있을 때) — 의도를 검증해 실행 · 실패하면 아래 규칙으로
    meal_due = (not a.meals["lunch"] and hm("13:15") <= t < hm("14:00") and (a.meals["breakfast"] or a.phase in ("visit", "checkin"))) or \
               (not a.meals["dinner"] and a.hunger_e >= 0.3 and hm("19:45") <= t < hm("21:00") and not a.checked_out)   # 끼니를 놓치기 직전이면 규칙(끼니 욕구)으로
    if a.planner == "llm" and not meal_due:
        from . import llm_layer as LL
        if LL.step(a, world, t):
            return True
    # 점심 욕구
    if not a.meals["lunch"] and hm("11:30") <= t < hm("14:00") and (a.meals["breakfast"] or a.phase in ("visit", "checkin")):
        r, rej = plan_choose(a, t, world, [c for c in SP.LUNCH if not (c == "lunch_room" and (not a.stay or a.checked_out or not a.checked_in))],
                             lambda c: SP.lunch_weight(c, a.P, a.C, dict(a.ctx(), late_breakfast=late_breakfast(a))))
        if r:
            plan_do(a, r[0], r[1], t, r[2], rej, note="점심 욕구(끼니 창)"); return True
    # 15:30 뒤 · 현장에 있음 → 정량 엔진의 연속 판단(지원 상품)
    if hm("15:30") <= t < a.end and not a.checked_out:
        d, w = engine_step(a, world, t)
        t = a.t   # 마감 문의 기록(5분)이 있었으면 그 뒤부터 이동 · 이용(CL-1024-21A 시간 겹침 수정)
        if d and d["chosen"] != "ROOM_REST":
            engine_do(a, d, w, t); return True
        codes = [c for c in LEISURE if c not in ENGINE_COVERS] + (["room_rest"] if a.stay else [])
        r, rej = plan_choose(a, t, world, codes, lambda c: pace_w(a, c))
        if r and r[0] != "room_rest":
            plan_do(a, r[0], r[1], t, r[2], rej, note="엔진 지원 상품 중 휴식보다 나은 것이 없을 때 엔진 밖 활동 검토"); return True
        if a.stay and d:
            engine_do(a, d, w, t); return True
        if a.stay and t >= hm("21:00"):
            end_day(a, why="밤이 깊어 더 갈 만한 곳이 없어 객실로 돌아가 하루를 마무리합니다."); return True
        if a.stay:
            plan_do(a, "room_rest", a.room, t, {}, rej, note="엔진 후보 없음 · 객실 휴식"); return True
        waiting = not a.meals["dinner"] and t < hm("17:30")
        a.add("wait", "idle", "벤치에서 쉬어 감", "AG_GARDEN", t, min(30, hm("17:30") - t) if waiting else 30, "휴식", "planner_rules",
              "저녁 식사 시간(17:30)까지 갈 만한 곳이 없어 벤치에서 쉬며 기다립니다." if waiting else "잠시 벤치에서 쉬어 갑니다.",
              [dict(type="프로파일 기반 추론", traits=["rest_need"], about="휴식 욕구 · 남은 시간")], dict(waiting_for="dinner" if waiting else None)); return True
    # 15:30 전 여가 · 퇴실 뒤 여가
    codes = [c for c in LEISURE if not (c.startswith("room") and (not a.stay or a.checked_out or not a.checked_in))]
    r, rej = plan_choose(a, t, world, codes, lambda c: pace_w(a, c))
    if r:
        plan_do(a, r[0], r[1], t, r[2], rej, note="여가 욕구"); return True
    if a.phase == "checkout" and not a.checked_out:
        checkout_now(a, t); return True   # 체크아웃 전 더 할 수 있는 것이 없으면 바로 퇴실
    a.add("wait", "idle", "잠시 쉬어 감", a.loc or "HOTEL_GATE", t, 30, "휴식", "world_rule", "지금 갈 만한 곳(오늘 이미 이용했거나 이용할 수 없는 곳 제외)이 없어 잠시 쉬어 갑니다.", [], dict(rejected=rej)); return True


def pace_w(a, c):
    """계획기 적합도 + 현재 피로(개인 페이스 대비) — 지칠수록 활동은 덜, 휴식은 더."""
    w = SP.act_weight(c, a.P, a.C, a.ctx())
    k = SP.ACT[c][2]; r = a.fatigue / max(0.8, a.rest_limit)
    if k in ("wellness", "outdoor", "culture"):
        w -= 0.6 * r
    elif k == "rest":
        w += 0.5 * r
    return w


def finish(a):
    acts = [x for x in a.log if x["act"] not in ("move", "wait", "idle")]
    return dict(persona_id=a.pid, version=VERSION, visit=dict(stay=a.stay, building=a.B if a.stay else None, phase=a.phase, nights=a.vs["nights"], party_size=a.N, rel=a.vs["rel"],
                                                               why=a.vs["why"], layer=a.vs["layer"], club=a.club, review_stay=a.review_stay),
                log=a.log, summary=dict(n_actions=len(acts), domains=sorted({x["domain"] for x in acts}), meals=a.meals, spent_krw=int(a.spent), fatigue_end=round(a.fatigue, 2),
                                        engine_actions=sum(1 for x in acts if x["source"] == "quantitative_engine"), planner_actions=sum(1 for x in acts if x["source"] == "planner_rules"),
                                        review_evidence_actions=sum(1 for x in acts if any(e["type"] == "후기에서 확인" for e in x["evidence"])),
                                        llm_actions=sum(1 for x in acts if str(x["source"]).startswith("llm_plan")),
                                        # CL-19 후속 — 집계 정의 분리: 타임라인 행동(이동 · 대기 · 제자리 휴식 제외) / 제자리 휴식 / LLM 의도 · 채택 · 거절 · 병합
                                        timeline_actions=len(acts), idle_blocks=sum(1 for x in a.log if x["act"] == "idle"),
                                        idle_min=sum(hm(x["e"]) - hm(x["t"]) for x in a.log if x["act"] == "idle"),
                                        llm_idle_blocks=sum(1 for x in a.log if x["act"] == "idle" and str(x["source"]).startswith("llm_plan")),
                                        llm_intents=sum(1 for x in a.trace if x.get("backend") == "llm"),
                                        llm_accepted=sum(1 for x in a.trace if x.get("backend") == "llm" and x["accepted"]),
                                        llm_rejected=sum(1 for x in a.trace if x.get("backend") == "llm" and not x["accepted"]),
                                        llm_merged=sum(1 for x in a.trace if x.get("backend") == "llm" and x.get("merged")),
                                        spent_known_krw=int(a.spent), unpriced=[dict(t=c["t"], act=c["act"], basis=c["basis"]) for c in a.charges if c["status"] == "가격 미정"],
                                        charges_by_status={k: sum(1 for c in a.charges if c["status"] == k) for k in ("구매 없음", "무료", "포함", "유료", "가격 미정")},
                                        meal_log=a.meal_log, spent_party_estimate_krw=int(a.spent_est),
                                        completed=a.left or a.t >= a.end or a.ended), planner=a.planner, trace=a.trace)


# ---------------------------------------------------------------- 실행 모드
def run_one(pid, sc, inputs=None):
    P, bars, lib = inputs or load_inputs()
    world = World(sc)
    a = Agent(pid, P, bars, lib, sc)
    guard = 0
    while decide(a, world) and guard < 90:
        guard += 1
    out = finish(a)
    out["notices"] = [dict(at=c["at"], label=c.get("label")) for c in world.changes]
    return out


def run_many(pids, sc, inputs=None):
    """동시 실행 — 한 월드 · 한 시계. 가장 이른 다음 결정 시각의 고객부터 한 걸음씩 진행. 고객끼리 자원 경쟁은 없음(지원 제약 없음) → 같은 장소 동시 체류는 관찰로만 기록."""
    P, bars, lib = inputs or load_inputs()
    world = World(sc)
    agents = {p: Agent(p, P, bars, lib, sc) for p in pids}
    live = dict(agents); order = []; guard = 0
    while live and guard < 2000:
        guard += 1
        pid = min(live, key=lambda k: (live[k].t, pids.index(k)))
        a = live[pid]
        if not decide(a, world) or a.steps > 90:
            live.pop(pid); continue
        order.append((a.log[-1]["t"], pid, a.log[-1]["act"]))
    outs = {p: finish(a) for p, a in agents.items()}
    copresence = {}
    for tt in range(hm("07:00"), hm("23:00"), 30):
        here = {}
        for p, a in agents.items():
            for x in a.log:
                if hm(x["t"]) <= tt < hm(x["e"]) and x["act"] != "move":
                    here.setdefault(x["loc"], []).append(p); break
        copresence[mh(tt)] = {k: v for k, v in here.items() if len(v) >= 2}
    return dict(mode="concurrent", personas=outs, interleave=order[:400], copresence=copresence, interaction="없음 — 현재 월드에 지원되는 좌석 · 대기 · 정원 제약이 없어 고객 사이 자원 경쟁을 계산하지 않음(동시 체류는 관찰만)",
                notices=[dict(at=c["at"], label=c.get("label")) for c in world.changes])


def compare(base, chg, at, event=True):
    """운영자 개입 전후 — 개입 시각 이후 행동 비교(고객별)."""
    T = hm(at)
    def after(r): return [(x["act"], x["loc"]) for x in r["log"] if hm(x["t"]) >= T and x["act"] not in ("move", "wait", "idle")]
    out = {}
    for pid in base:
        b, c = after(base[pid]), after(chg[pid])
        new = [x for x in c if x not in b]; gone = [x for x in b if x not in c]
        wf = [x for x in chg[pid]["log"] if x["act"] == "WINE_FAIR"]
        views = [v for x in chg[pid]["log"] for v in (x.get("internal") or {}).get("event_view", []) if v.get("stage") != "참여 불가"] if event else []
        full = [x for x in chg[pid]["log"] if str(x["act"]).endswith(":full")]
        firstnew = next((x for x in chg[pid]["log"] if hm(x["t"]) >= T and (x["act"], x["loc"]) in new and x["act"] not in ("move", "wait", "idle")), None)
        if full:
            alt = next((x for x in chg[pid]["log"] if hm(x["t"]) >= hm(full[0]["t"]) and x is not full[0] and x["act"] not in ("move", "wait", "idle")), None)
            out[pid] = dict(cls="이용 포기 · 대안 선택", new=new, cancelled=gone, event_views=[], reason=full[0]["why"],
                            alternative=dict(t=alt["t"], label=alt["label"], why=alt["why"], evidence=alt["evidence"]) if alt else None)
            continue
        if not new and not gone:
            cls = "원래 일정 유지" + (" · 새 조건에 관심 낮음" if views and all("관심 낮음" in v.get("stage", "") for v in views) else " · 관심은 있었으나 다른 선택" if views else "")
        elif wf and any(x[0] == "WINE_FAIR" for x in new):
            cls = "새 행동 선택(행사 참여)" + (" · 기존 활동 대체" if gone else "")
        elif any(x[0] == "WINE_FAIR:check" for x in new):
            cls = "행사 안내만 확인 · 다른 일정 선택"
        else:
            cls = "기존 활동 취소 · 대체" if gone else "새 행동 추가"
        if wf and any(x[0] == "WINE_FAIR" for x in new):
            firstnew = wf[0]   # 행사 참여면 참여 기록의 이유를 대표 이유로
        reason = (firstnew["why"] if firstnew else None) or ("; ".join(f"{v.get('stage')}" + (f"(다른 선택과 차 {v['gap']})" if v.get("gap") is not None else "") for v in views[:2]) if views else "개입과 관련된 시설을 오늘 계획에서 쓰지 않음")
        out[pid] = dict(cls=cls, new=new, cancelled=gone, event_views=views[:3], reason=reason,
                        new_evidence=(firstnew["evidence"] if firstnew else []), new_source=(firstnew["source"] if firstnew else None))
    return out
