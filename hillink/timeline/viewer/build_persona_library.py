"""페르소나 라이브러리 화면 자료 생성기 (10/23).

팀 자료(원본은 각 브랜치 그대로)에서 화면에 필요한 칸만 뽑아 static/persona_library.json 한 파일로 만든다.
  · 작성자 10명 선정 · 유형 · 선정 이유 요약 — 소연 PR #92 (docs/작성자10명_선정배정_소연_1022.md)
  · 예비 18명(A11~A28) 유형 · 선정 근거 · 검수 주의 · 상태 — 소연 PR #93 (docs/data/soyeon_followup_1022/후보18명_배정안.csv)
  · A02 · A04 · A05 · A07 · A10 통합 프로파일 — 한호 PR #98 (analysis/A0x/구조화프로파일.json, 열린 PR 브랜치)
  · 지도 엔진이 실제로 쓰는 성향 · 근거 — operator_world_v1_1/turn_personas_rbase.json (R-BASE-1022 · PR #98 13차 사본)
  · A01 · A03 · A06 · A08 · A09 진행 상태 — 슬기 PR #96 · #99 집계(상세 프로파일은 저장소 밖 비공개 보관이라 화면에 싣지 않음)

넣지 않는 것: 원문 · 블로그 링크 · 실명 · 아동 · 건강 관련 서술(문장 단위로 빼고 개수만 남김).
엔진 버전과 팀 최신 분석 버전은 같다고 가정하지 않는다 — 사실 ID · 요지 문장이 몇 개 일치하는지만 기록한다.

쓰는 법: python3 build_persona_library.py --repo /path/to/walkerhill [--pr98-ref <ref>] [--team-ref <ref>]
"""
import argparse, csv, io, json, re, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / "experiments/persona_live/operator_choice/operator_world_v1_1/turn_personas_rbase.json"
OUT = HERE / "static/persona_library.json"
PR98_DIR = "docs/data/author_persona_source_analysis_update_shh_20261022/analysis"
SIM = ["A02", "A04", "A05", "A07", "A10"]
# 화면에서 문장 단위로 빼는 말 — 아동 · 건강 · 신체 상태 (팀 원본은 그대로 둔다)
SENSITIVE = re.compile(r"영아|아기|아이|유아|자녀|딸|아들|유모차|카시트|육아|임신|임산|출산|산후|모유|건강|진단|의학|병원|신체|돌잔치|돌 ")
IDENT = re.compile(r"https?://|naver|tistory|instagram|@")
TYPE_GROUP = [("가족 · 영유아", "가족 · 영유아"), ("가족 · 부모", "가족 · 부모 동반"), ("커플", "커플 · 기념일"), ("혼자", "혼자 휴식"), ("친구", "친구 모임"),
              ("업무", "업무 · 출장"), ("미식", "미식"), ("웰니스", "웰니스"), ("스포츠", "스포츠 목적"), ("행사", "행사 체험"), ("혜택", "혜택 · 멤버십")]
# 카드 사진 — 선정 이유에 처음 나오는 워커힐 장소의 콘셉트 이미지(후기 사진 아님)
THUMB = [("와인페어", "WINE_FAIR"), ("피자힐", "PIZZA_HILL"), ("모에기", "MOEGI"), ("명월관", "MYONGWOLGWAN"), ("더뷔페", "THE_BUFFET"), ("라운지", "GRAND_CLUB_LOUNGE"),
         ("리버파크", "RIVERPARK"), ("포레스트", "FOREST_PARK"), ("숲", "FOREST_PARK"), ("골프", "GOLF_CLUB"), ("사우나", "WELLNESS_SAUNA"),
         ("수영", "VISTA_POOL"), ("룸서비스", "VISTA_ROOM"), ("객실", "VISTA_ROOM"), ("스위트", "VISTA_ROOM"), ("커넥팅", "GRAND_ROOM"), ("숙박", "GRAND_ROOM")]


def git_show(repo, ref, path):
    return subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"], capture_output=True, check=True).stdout.decode("utf-8-sig")


def git_sha(repo, ref):
    return subprocess.run(["git", "-C", repo, "rev-parse", "--short", ref], capture_output=True, text=True, check=True).stdout.strip()


def clean(s, drop):
    """민감 · 식별 문장이면 None (drop 개수를 센다)."""
    s = (s or "").strip()
    if not s:
        return None
    if SENSITIVE.search(s) or IDENT.search(s):
        drop[0] += 1
        return None
    return s


def group_of(t):
    for k, g in TYPE_GROUP:
        if k in t:
            return g
    return t


def thumb_of(text):
    for k, loc in THUMB:
        if k in (text or ""):
            return dict(loc=loc, why=f"'{k}' 언급 장소")
    return dict(loc=None, why="대표 장소 미지정")


def soyeon_ten(md):
    sec = md.split("## 2. 10명", 1)[1].split("\n## ", 1)[0]
    rows = []
    for ln in sec.splitlines():
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) >= 8 and re.fullmatch(r"A\d\d", c[0]):
            rows.append(dict(id=c[0], owner=c[1], type=c[2], start=c[3], archive_posts=int(c[5]) if c[5].isdigit() else None, pick=c[6], caution="" if c[7] in ("—", "-") else c[7]))
    return rows


def wh_post_ids(d):
    return set(d["SOURCE_AUDIT"].get("walkerhill_post_ids") or [])


def pr98_profile(raw, eng):
    d = json.loads(raw)
    drop = [0]
    A = d["SOURCE_AUDIT"]
    wh = wh_post_ids(d)
    facts = {f["fact_id"]: f for f in d["STRUCTURED_PROFILE"]["facts"]}

    def ev(e):
        det = clean(e.get("detail"), drop)
        if not det:
            return None
        return dict(id=e["event_id"], visit=e["visit_id"].split("-", 1)[-1], stage=" · ".join(e.get("stages") or []), link=e.get("link_status"),
                    detail=det, facts=e.get("fact_ids") or [], posts=e.get("post_ids") or [], wh=bool(set(e.get("post_ids") or []) & wh), feature=e.get("feature_key"))

    evs = [x for x in (ev(e) for e in d["EVENT_ACTIONS"]) if x]
    traits = []
    for t in d["TRAIT_TABLE"]:
        name = clean(t.get("trait"), drop)
        if not name:
            continue
        traits.append(dict(id=t["trait_id"], trait=name, strength=clean(t.get("strength"), drop) or "", n=t.get("independent_evidence_count"),
                           conditions=[x for x in (clean(c, drop) for c in t.get("conditions") or []) if x],
                           counter=[x for x in (clean(c, drop) for c in t.get("counterexamples") or []) if x],
                           claim=t.get("claim_type"), evidence=len(t.get("evidence_ids") or []), support=t.get("support_event_ids") or []))
    rules = []
    for r in d["CONTEXT_RULES"]:
        cnd, hyp = clean(r.get("condition"), drop), clean(r.get("behavior_hypothesis"), drop)
        if cnd and hyp:
            rules.append(dict(id=r["rule_id"], condition=cnd, hypothesis=hyp, status=r.get("status"), evidence=len(r.get("evidence_ids") or []), support=r.get("support_event_ids") or []))
    # 엔진이 쓰는 사실 ↔ 팀 최신 사실
    ei = eng["traits"].get("evidence_index") or {}
    base = lambda fid: facts.get(fid) or facts.get(re.sub(r"(\d)[a-z]$", r"\1", fid))
    efacts, n_found, n_same = {}, 0, 0
    for fid, x in ei.items():
        f = base(fid)
        gist = clean(x.get("gist"), drop)
        if f:
            n_found += 1
            n_same += int((f.get("detail") or "").strip() == (x.get("gist") or "").strip())
        efacts[fid] = dict(gist=gist, features=x.get("features") or [], in_team=bool(f),
                           wh=bool(f and set([f.get("post_id")]) & wh), exp=(f or {}).get("experience_key", "").split("-", 1)[-1] or None,
                           kind=(f or {}).get("kind"), hidden=gist is None, post=(f or {}).get("post_id"))
    vg = clean(A.get("visit_grouping"), drop)
    return dict(
        label=clean(d["STRUCTURED_PROFILE"].get("label"), drop),
        audit=dict(unique_posts=A.get("unique_post_count"), walkerhill=A["scope_counts"].get("walkerhill"), related=A["scope_counts"].get("related"),
                   recent=A["scope_counts"].get("recent"), events_confirmed=A.get("independent_event_count"), missing_sources=len(A.get("missing_sources") or []),
                   review_requests=len(A.get("review_requests") or []), recent50_complete=A.get("recent50_complete"),
                   full_read_claimed=A.get("all_posts_full_semantic_read_claimed"), assignment_complete=A.get("entire_assignment_complete"),
                   prompt=A.get("common_prompt_version")),
        visit_grouping=vg, start_post=sorted(wh)[0] if wh else None, wh_post_ids=sorted(wh), wh_events=[e for e in evs if e["wh"]], other_events=[e for e in evs if not e["wh"]],
        traits=traits, rules=rules, n_facts=len(facts),
        engine=dict(fact_ids=list(ei), n=len(ei), found_in_team=n_found, gist_same=n_same, facts=efacts),
        hidden_sentences=drop[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--team-ref", default="origin/merge/validator-0923")
    ap.add_argument("--pr98-ref", default="origin/author-persona-source-analysis-update-shh-20261022")
    a = ap.parse_args()
    eng = json.loads(ENGINE.read_text(encoding="utf-8"))
    ten = soyeon_ten(git_show(a.repo, a.team_ref, "docs/작성자10명_선정배정_소연_1022.md"))
    cand = list(csv.DictReader(io.StringIO(git_show(a.repo, a.team_ref, "docs/data/soyeon_followup_1022/후보18명_배정안.csv"))))
    out = dict(
        about="페르소나 라이브러리 화면 자료 — 팀 자료에서 화면 칸만 뽑음. 원문 · 링크 · 실명 · 아동 · 건강 서술 없음. 생성: timeline/viewer/build_persona_library.py",
        sources=dict(team=f"{a.team_ref} · {git_sha(a.repo, a.team_ref)} (PR #92 · #93)", pr98=f"PR #98 열린 브랜치 · {git_sha(a.repo, a.pr98_ref)}",
                     engine="R-BASE-1022 · PR #98 13차 사본(turn_personas_rbase.json)", slgi="PR #96 병합 · PR #99 열림 — 담당 5명 집계만(상세 비공개 보관)"),
        status_legend=dict(explore="후기 탐색 가능", profile="프로파일 추출", reviewed="팀 검수 완료", sim="행동 시뮬레이션 가능"),
        personas=[])
    for r in ten:
        p = dict(id=r["id"], group="first10", owner=r["owner"], type=r["type"], type_group=group_of(r["type"]), start=r["start"], archive_posts=r["archive_posts"],
                 pick=r["pick"], caution=r["caution"], thumb=thumb_of(r["pick"]))
        if r["id"] in SIM:
            prof = pr98_profile(git_show(a.repo, a.pr98_ref, f"{PR98_DIR}/{r['id']}/구조화프로파일.json"), eng["personas"][r["id"]])
            p.update(prof)
            p["status"] = dict(explore=True, profile="done", reviewed=False, sim=True,
                               note="PR #98 통합 프로파일(보강 진행 · 팀 검수 전) · 지도 엔진은 R-BASE-1022 사본 사용")
        else:
            p["status"] = dict(explore=True, profile="progress", reviewed=False, sim=False,
                               note="슬기 님 프로파일 추출 진행 — 상세 결과는 비공개 보관 · 화면 연결 전")
        out["personas"].append(p)
    for c in cand:
        held = "보류" in c["상태"]
        out["personas"].append(dict(id=c["작성자ID"], group="reserve", owner=c["담당안"], type=c["잠정 주유형"], type_group=group_of(c["잠정 주유형"]),
                                    start=c["시작글"], archive_posts=int(c["아카이브 글수"]) if c["아카이브 글수"].isdigit() else None,
                                    pick=c["선정 근거"], caution=c["검수 주의"], thumb=thumb_of(c["선정 근거"]),
                                    status=dict(explore=True, profile="none", reviewed=False, sim=False, note=("조건부 보류 · " if held else "") + c["상태"])))
    # 개발 그룹 blog41~43 — 저장소 traits.json(V1 형식) 그대로 엔진에 들어감 · 측정 계약 미적용 · 평가 표본 아님
    extp = ENGINE.with_name("turn_personas_ext.json")
    if extp.exists():
        for k, v in json.loads(extp.read_text(encoding="utf-8"))["personas"].items():
            ei = v["traits"].get("evidence_index") or {}
            out["personas"].append(dict(id=k, group="dev", owner="경수", type="개발 그룹", type_group="개발 그룹", start=k, archive_posts=None, pick="", caution="",
                                        thumb=dict(loc=None, why="후기 손님 목록 사진 사용"), label=None, n_facts=len(ei),
                                        engine=dict(fact_ids=list(ei), n=len(ei), found_in_team=None, gist_same=None,
                                                    facts={fid: dict(gist=x.get("gist"), features=x.get("features") or [], in_team=None, wh=True, exp=None, kind=None,
                                                                     hidden=x.get("gist", "").startswith("아동 · 건강"), post=None) for fid, x in ei.items()}),
                                        status=dict(explore=True, profile="done", reviewed=False, sim=True, note=v.get("pipeline", "") + " · 개발 그룹(평가 표본 아님)")))
    s = json.dumps(out, ensure_ascii=False, indent=1)
    bad = IDENT.findall(s)
    assert not bad, f"식별 문자열 {bad[:5]}"
    OUT.write_text(s, encoding="utf-8")
    sim = [p for p in out["personas"] if p.get("engine")]
    print(OUT, len(out["personas"]), "명 ·", " ".join(f"{p['id']}:{p['engine']['found_in_team']}/{p['engine']['n']}·요지{p['engine']['gist_same']}·숨김{p.get('hidden_sentences', 0)}" for p in sim))


if __name__ == "__main__":
    main()
