"""CL-1025-36 — 신규 후보용 사람 승인 범위 sidecar + 안전 importer adapter (격리 QA 전용 · 기존 11명 · 동결 경로 불변).

왜: V4.2 fact 스키마의 polarity 는 positive/negative/mixed/neutral 만 허용하고, 현행 importer 는 neutral 도 성향 근거 ·
업장 이력으로 연결한다(CD-13 HOLD). 미평가 · 승인 범위를 neutral 로 합성하면 점수에 새어 든다.

계약(상태 4종 · 모두 정량 기여 0)
  OBSERVATION_ONLY        실제 행동 · 미수행 · 휴관 등 관측만. 업장 방문 오귀속 금지 · 점수 0. 출력에서는 엔진 결정 이유와 다른 칸(observations)
  DIRECTION_CONTEXT_ONLY  사람 승인된 정성 방향 · 상황 범위만. 강도 · 가중치 · 점수 0 · 이용 횟수/타 업장 이력 승격 금지
  HOLD_UNKNOWN            사람 검토 후 보류. 제품 점수 · 이용 근거 · 업장 이력에서 fail-closed. 식별자 · 계보는 비공개 sidecar 에만
  UNREVIEWED              사람 검토 대상 아님/미검토. HOLD_UNKNOWN 과 같은 fail-closed
구조
  sidecar(비공개 QA)  : 62개 원자 사실 전부 — fact/event/post ID · anchor_sha256 · LP 행동 발생 · 사람 처분 · 승인 범위 · 계약 상태 ·
                        원래 극성 표지(미정량) — 값 손실 없음. polarity 칸을 만들지 않는다(역변환 방지).
  소비 입력(엔진)     : 점수 projection = 사실 0건(V4.2 변환을 거치지 않음 → neutral 합성 없음). 라이브러리 사실 · 업장 이력 · 근거 색인도 0건.
  observations(출력) : OBSERVATION_ONLY · DIRECTION_CONTEXT_ONLY 만, 엔진 reasons 와 분리된 칸. HOLD · UNREVIEWED 는 없음.
CL-36b(CD-14 HOLD 대응): 소비 직전 신뢰 입력(LP 정본 · 승인표 파일)으로 상태 · 처분 · 범위 · 사실 집합 · 입력 SHA 를 재검증 —
sidecar 만 고쳐 보류/미검토를 관측으로 바꾸는 위조는 중단. observations 는 신뢰 기대값으로 생성.
fail-closed: 알 수 없는 상태 · 'neutral'/'positive' 같은 극성 값 · 승인표에 있으나 LP 정본에 없는 fact · 강도 값이 NOT_ASSIGNED 가
아닌 행 · 중복 fact 는 예외(ContractError)로 중단.
"""
import csv, hashlib, json
from pathlib import Path

STATES = ("OBSERVATION_ONLY", "DIRECTION_CONTEXT_ONLY", "HOLD_UNKNOWN", "UNREVIEWED")
NON_SCORING = set(STATES)                       # 이번 계약에서는 4종 모두 점수 기여 0
SURFACED = {"OBSERVATION_ONLY", "DIRECTION_CONTEXT_ONLY"}
DISPOSITION = {"APPROVE_OBSERVATION_ONLY": "OBSERVATION_ONLY", "APPROVE_DIRECTION_NO_STRENGTH": "DIRECTION_CONTEXT_ONLY", "HOLD_UNKNOWN": "HOLD_UNKNOWN"}
POLARITY_WORDS = {"positive", "negative", "mixed", "neutral"}
OCCURRENCE = {"OBSERVED", "OTHER_CONTEXT", "NOT_DONE", "CANCELED_CLOSED"}


class ContractError(ValueError):
    pass


def _csv(p):
    with open(p, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


PINNED_MANIFEST = Path(__file__).resolve().parent / "approved_inputs_manifest_cl36c.json"
PINNED_MANIFEST_SHA256 = "a46c980d56034c67a80bf40fb3b78a71add73fc8e6262d137915dd192c1f0568"   # CL-1025-36d — 커밋된 매니페스트 파일 자체의 SHA(파일만 교체 · 삭제하면 중단)


def load_pinned_manifest():
    """운영 경로의 유일한 매니페스트 로더 — 경로 · 내용 모두 고정(호출 인자 없음). 파일 SHA 가 코드 상수와 다르거나 파일이 없으면 중단.
    한계: 코드와 매니페스트를 함께 고칠 수 있는 저장소 쓰기 권한자는 막지 못함(서명 · 접근 통제의 몫)."""
    try:
        raw = PINNED_MANIFEST.read_bytes()
    except OSError:
        raise ContractError("고정 매니페스트 파일 없음")
    if hashlib.sha256(raw).hexdigest() != PINNED_MANIFEST_SHA256:
        raise ContractError("고정 매니페스트 파일이 커밋된 버전과 다름(교체 · 수정)")
    return _check_manifest(json.loads(raw.decode("utf-8")))


def _check_manifest(m):
    for k in ("boundary_csv", "approval_csv", "source_facts"):
        if not m.get(k):
            raise ContractError(f"매니페스트에 {k} 없음")
    return m


class TrustedInputs:
    """CL-1025-36b/36c/36d — 소비 직전 재검증용 신뢰 입력. 원래 LP 정본 · 사용자 승인표 · LP 원본 사실 파일에서 다시 읽고,
    세 입력 SHA 를 고정 매니페스트(load_pinned_manifest)와 대조한다. **매니페스트를 인자로 받지 않는다**(CD-14C: 호출자 manifest 주입 우회 차단).
    합성 입력 시험은 tests/ 쪽 하위 클래스가 _manifest() 를 재정의해서만 가능(운영 모듈에는 주입 경로 없음)."""
    def __init__(self, boundary_csv, approval_csv, source_dir):
        if not source_dir:
            raise ContractError("LP 원본 사실(source_dir) 없이 신뢰 입력을 만들 수 없음 — post_id · anchor_sha256 재도출 불가")
        m = self._manifest()
        if _file_sha(boundary_csv) != m["boundary_csv"]:
            raise ContractError("LP 정본 CSV 가 고정 매니페스트 SHA 와 다름")
        if _file_sha(approval_csv) != m["approval_csv"]:
            raise ContractError("승인표 CSV 가 고정 매니페스트 SHA 와 다름")
        src = {p.parent.parent.name: p for p in Path(source_dir).glob("WH-*/candidate/facts_events_evidence.json")}
        if set(src) != set(m["source_facts"]):
            raise ContractError(f"LP 원본 사실 파일 집합이 매니페스트와 다름 {sorted(set(src) ^ set(m['source_facts']))}")
        for sid, p in src.items():
            if _file_sha(p) != m["source_facts"][sid]:
                raise ContractError(f"{sid}: LP 원본 사실 파일이 고정 매니페스트 SHA 와 다름")
        self.manifest_sha = sha_of(m)
        sc = build_sidecar(boundary_csv, approval_csv, source_dir, _bind=self.manifest_sha)   # 같은 결정 규칙으로 기대값 재도출(계보 필드 포함)
        self.sha = self.manifest_sha
        self.expected = {r["fact_id"]: r for rows in sc.values() for r in rows}
        self.by_profile = {sid: {r["fact_id"] for r in rows} for sid, rows in sc.items()}
        missing = [f for f, r in self.expected.items() if not r.get("post_id") or not r.get("anchor_sha256")]
        if missing:
            raise ContractError(f"LP 원본에 계보(post_id · anchor_sha256)가 없는 사실 {missing[:5]}")

    def _manifest(self):
        return load_pinned_manifest()


def _bind_sha(boundary_csv, approval_csv):
    return hashlib.sha256((_file_sha(boundary_csv) + ":" + _file_sha(approval_csv)).encode()).hexdigest()


TRUSTED_FIELDS = ("fact_id", "event_id", "source_profile_id", "behavior_occurrence", "direct_walkerhill", "human_disposition", "approval_scope", "contract_state", "strength", "score_contribution",
                  "post_id", "anchor_sha256", "applicable_activities", "original_polarity_marker", "trusted_input_sha")   # CL-36c — 계보 필드 3종 + 원 극성 표지 + 결속 SHA


def verify_against_trusted(sid, rows, trusted):
    """sidecar 행을 신뢰 입력에서 재도출한 기대값과 대조 — 상태 · 처분 · 범위 · 계보(post_id · anchor_sha256 · applicable_activities) 위조,
    행 누락 · 추가 · 중복, 다른 입력/매니페스트로 만든 sidecar 를 모두 중단."""
    if not isinstance(trusted, TrustedInputs):
        raise ContractError("신뢰 입력(TrustedInputs) 없이 소비 불가")
    got = [r.get("fact_id") for r in rows]
    if len(got) != len(set(got)):
        raise ContractError(f"{sid}: sidecar 행 중복")
    if set(got) != trusted.by_profile.get(sid, set()):
        raise ContractError(f"{sid}: sidecar 사실 집합이 신뢰 입력과 다름(누락 · 추가)")
    for r in rows:
        e = trusted.expected[r["fact_id"]]
        bad = [k for k in TRUSTED_FIELDS if r.get(k) != e.get(k)]
        if bad:
            raise ContractError(f"{r['fact_id']}: 신뢰 입력과 불일치 {bad}")
    return True


def build_sidecar(boundary_csv, approval_csv, candidates_dir=None, _bind=None):
    """LP-16C 정본(62) + 사용자 승인표(15) → 고객별 sidecar. candidates_dir 가 있으면 post_id · anchor_sha256 계보를 덧붙임.
    trusted_input_sha = 고정 매니페스트 digest. (_bind 는 결속 표지일 뿐 신뢰 근거가 아님 — 신뢰 판단은 TrustedInputs 에서만)"""
    B = _csv(boundary_csv); A = _csv(approval_csv)
    bind = _bind or sha_of(load_pinned_manifest())
    if len({r["fact_id"] for r in B}) != len(B):
        raise ContractError("LP 정본 fact 중복")
    lp = {r["fact_id"]: r for r in B}
    appr = {}
    for r in A:
        f = r["fact_id"]
        if f in appr:
            raise ContractError(f"승인표 fact 중복 {f}")
        if f not in lp:
            raise ContractError(f"승인표 fact 가 LP 정본에 없음 {f}")
        if r.get("strength_status") != "NOT_ASSIGNED":
            raise ContractError(f"강도 값이 NOT_ASSIGNED 가 아님 {f}")
        d = r["human_disposition"]
        if d.lower() in POLARITY_WORDS or d not in DISPOSITION:
            raise ContractError(f"알 수 없는 처분/극성 값 {f}={d}")
        appr[f] = r
    anc = {}
    if candidates_dir:
        for fe in Path(candidates_dir).glob("WH-*/candidate/facts_events_evidence.json"):
            for x in json.loads(fe.read_text(encoding="utf-8"))["facts"]:
                anc[x["fact_id"]] = dict(post_id=x.get("post_id"), anchor_sha256=[a.get("anchor_sha256") for a in x.get("anchors") or []],
                                         original_polarity_marker=x.get("original_polarity"))
    out = {}
    for f, r in lp.items():
        if r["behavior_occurrence"] not in OCCURRENCE:
            raise ContractError(f"알 수 없는 행동 발생 값 {f}")
        a = appr.get(f)
        st = DISPOSITION[a["human_disposition"]] if a else "UNREVIEWED"
        rec = dict(fact_id=f, event_id=r["event_id"], source_profile_id=r["source_profile_id"], behavior_occurrence=r["behavior_occurrence"],
                   direct_walkerhill=r["direct_walkerhill_experience"], applicable_activities=r["applicable_activities"].split("|") if r.get("applicable_activities") else [],
                   lp_preference_direction_candidate=r.get("preference_direction"), lp_preference_value=r.get("preference_value"),
                   human_disposition=(a or {}).get("human_disposition", "NOT_IN_REVIEW_SET"), approval_scope=(a or {}).get("approval_scope"),
                   strength="NOT_ASSIGNED", contract_state=st, score_contribution=0, trusted_input_sha=bind, **anc.get(f, {}))
        out.setdefault(r["source_profile_id"], []).append(rec)
    return out


def validate_sidecar(sc):
    for sid, rows in sc.items():
        for r in rows:
            if r.get("contract_state") not in STATES:
                raise ContractError(f"알 수 없는 계약 상태 {r.get('fact_id')}={r.get('contract_state')}")
            if "polarity" in r or str(r.get("contract_state", "")).lower() in POLARITY_WORDS:
                raise ContractError(f"극성 칸/값 금지(역변환 방지) {r['fact_id']}")
            if r.get("strength") != "NOT_ASSIGNED" or r.get("score_contribution") != 0:
                raise ContractError(f"강도 · 점수 기여는 NOT_ASSIGNED · 0 이어야 함 {r['fact_id']}")
    return True


def empty_traits(alias, visit_companion=None):
    """점수 projection 0건 — 현행 변환기에 빈 사실 집합을 넣은 것과 같은 구조(V4.2 극성 합성 없음)."""
    import sys
    HERE = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(HERE.parent / "experiments" / "persona_live"))
    from operator_choice.operator_world_v1_1 import importer as V11   # noqa: E402  (변환기와 같은 현행 importer · 수정 없이 호출)
    from operator_choice.operator_world_v1_1.candidate_import import apply_measurement_contract   # noqa: E402
    doc = {"STRUCTURED_PROFILE": {"persona_id": alias, "facts": []}}
    traits, _ = apply_measurement_contract(doc, V11.build_traits_v42_plus(doc, visit_companion=visit_companion))
    return traits


def consumption(sidecar_rows, alias, type_label, visit_companion=None, *, trusted, source_profile_id):
    """엔진 소비 입력(점수 0) + 출력용 observations 분리. 반환: (persona, lib, observations).
    CL-36b: 신뢰 입력으로 상태 · 처분 · 범위를 소비 직전에 재검증(없거나 불일치면 중단). observations 는 sidecar 값이 아니라 신뢰 기대값으로 만든다."""
    validate_sidecar({alias: sidecar_rows})
    verify_against_trusted(source_profile_id, sidecar_rows, trusted)
    sidecar_rows = [dict(r, **{k: trusted.expected[r["fact_id"]][k] for k in TRUSTED_FIELDS}) for r in sidecar_rows]
    tr = empty_traits(alias, visit_companion)
    persona = dict(id=alias, label=f"{alias} · QA 격리(승인 sidecar)", companion=None, source_post_count=0, active_fact_count=0, traits=tr)
    lib = dict(id=alias, group="qa_isolated", type=type_label, type_group=type_label, engine=dict(facts={}), wh_events=[], other_events=[], visit_feature_summary={})
    obs = [dict(fact_id=r["fact_id"], event_id=r["event_id"], contract_state=r["contract_state"], behavior_occurrence=r["behavior_occurrence"],
                approval_scope=r["approval_scope"], applicable_activities=r["applicable_activities"], score_contribution=0,
                note="관측/정성 방향 기록 — 엔진 결정 이유가 아님 · 점수 기여 0")
           for r in sidecar_rows if r["contract_state"] in SURFACED]
    return persona, lib, obs


def sha_of(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


QA_TYPE = {"WH-00532": ("친구 모임", "friends"), "WH-00491": ("커플(기념일 미확인)", "partner"), "WH-00499": ("가족 · 영유아", "kids"),
           "WH-00274": ("친구 모임", "friends"), "WH-00333": ("가족 · 아이 동반(연령 미확인)", "kids")}   # CL-30 격리 유형 문자열 · 동행 범주(근거 범위)


def install_into_flow(sc, trusted):
    """lp16_flow_qa 와 같은 방식(이 프로세스 메모리 한정)으로 sidecar 소비 입력을 실행기에 덧붙임. 반환: (ids, observations)."""
    import lp16_flow_qa as Q
    AD = Q.AD
    QP, QL, OBS = {}, {}, {}
    for sid, rows in sorted(sc.items()):
        alias = "QA16_" + sid.split("-")[1]
        lab, comp = QA_TYPE.get(sid, ("", None))
        p, l, o = consumption(rows, alias, lab, comp, trusted=trusted, source_profile_id=sid)
        QP[alias], QL[alias], OBS[alias] = p, l, o
    base_lap, base_li = AD.load_all_personas, AD.load_inputs
    AD.load_all_personas = lambda: dict(base_lap(), **QP)
    def li():
        P, bars, lib = base_li()
        return P, bars, dict(lib, **QL)
    AD.load_inputs = li
    AD.DEMO = list(AD.DEMO) + [k for k in QP if k not in AD.DEMO]
    return sorted(QP), OBS
