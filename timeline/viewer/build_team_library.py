"""Pinned team-data -> display-only library adapter. Never imports facts into R-BASE.

python3 timeline/viewer/build_team_library.py --team-repo /path/to/team/worktree
Generated display JSON is separate from *.local.json and all engine inputs.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

import build_persona_library as display

TEAM_BASE = 'b6c4e77f874d8aeba23d2358608c04e89d667298'
REVIEW_BASE = '43f4e296451af5d374241d2ef8679c9547fa758f'
SUPPLEMENTAL_BASE = '23ef33bffc36aa71633071bed5889409350c4d2b'
TEAM_DIR = 'docs/data/team_personas_current/'
CARD_PATH = 'docs/data/library_soyeon_1023/라이브러리카드_1023.csv'
EXCLUSION_PATH = 'docs/data/library_soyeon_1023/열람기록_1023_평가제외.csv'
HANDOFF_PATH = 'docs/team_data_sync_20261023/library_handoff.json'
CARD_ADDITIONS_PATH = 'docs/data/library_soyeon_1023/라이브러리카드_추가_1023오후.csv'
VISIT_FEATURES_PATH = 'docs/data/library_soyeon_1023/방문특징_1023오후.csv'
EXPOSURE_ADDITIONS_PATH = 'docs/data/library_soyeon_1023/열람기록_1023오후_추가.csv'
PRIORITY_ADDITIONS_PATH = 'docs/data/library_soyeon_1023/우선순위_1023오후.csv'
REVIEW_OUT = display.HERE / 'static/team_review_index.json'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class TeamSource:
    def __init__(self, repo, ref=TEAM_BASE):
        if not re.fullmatch(r'[0-9a-f]{40}', ref):
            raise ValueError('team ref must be a pinned full commit SHA')
        self.repo, self.ref, self.receipts = Path(repo), ref, {}
        subprocess.run(['git', '-C', str(self.repo), 'cat-file', '-e', ref + '^{commit}'], check=True, capture_output=True)

    def raw(self, path):
        if path.startswith('/') or '..' in Path(path).parts:
            raise ValueError('unsafe team path')
        raw = subprocess.check_output(['git', '-C', str(self.repo), 'show', f'{self.ref}:{path}'])
        self.receipts[path] = digest(raw)
        return raw

    def json(self, path):
        return json.loads(self.raw(path).decode('utf-8-sig'))


def view_text(value):
    return display.clean(value, [0])


def legacy_view_contract(shared):
    """An in-memory display contract only; no anchor hydration or engine conversion."""
    if shared['schema_version'] != 'team_persona_shared_export_v1':
        raise ValueError('unsupported shared profile')
    return {'SOURCE_AUDIT': shared['source_audit'],
            'STRUCTURED_PROFILE': {'label': shared['label'], 'facts': shared['facts']},
            'EVENT_ACTIONS': shared['event_actions'], 'TRAIT_TABLE': shared['traits'],
            'CONTEXT_RULES': shared['context_rules']}


def review_payload(source, followup=None, supplemental=None):
    cross = source.json(TEAM_DIR + 'review/A01_A08_cross_review.json')
    items = []
    for original in cross['items']:
        r = copy.deepcopy(original)
        r['event_refs'] = [r['author'] + '-' + e for e in r['claims'].split(';') if e]
        for k in ['opinion', 'actor_time', 'independence', 'scope', 'point']:
            r[k] = view_text(r.get(k))
        r['comparison_status'] = 'awaiting_latest_detail_and_joint_review'
        items.append(r)
    # Full detail is deliberately not inferred from the aggregate Markdown.
    result = {'schema_version': 'team_review_display_v1', 'team_commit': source.ref,
            'cross_review': {'source_commit': cross['source_commit'], 'source_version': cross['received_source_version'],
                             'layer': 'reviewer_opinion_not_original_observation', 'team_consensus': False, 'items': items},
            'slgi': {'source_pr': 102, 'source_commit': '713a3fc0c818a60dcb416b431b514e0976b5f5b1',
                     'aggregate_path': 'docs/customer_type_library/common_workbook_review_20261023/README.md',
                     'aggregate_sha256': digest(source.raw('docs/customer_type_library/common_workbook_review_20261023/README.md')),
                     'detail_workbook_status': 'not_received',
                     'reported_workbook_sha256': 'e3fd4d6fe6a84a3eb1be30773439300a45dae7fac9272f0d8a510cc9267abf2b',
                     'authors': ['A01', 'A03', 'A06', 'A08', 'A09'],
                     'comparison_keys': ['author_group_id', 'event_id', 'claim_ids', 'source_version'],
                     'required_detail_fields': ['author_group_id', 'event_id', 'claim_ids', 'source_version',
                                                'reviewer_judgment', 'reviewer_reason', 'restricted_anchor_refs'],
                     'latest_detail_comparison_complete': False},
            'machine_field_proposals': source.json(TEAM_DIR + 'review/machine_field_proposals.json'),
            'runtime_fact_mapping': source.json(TEAM_DIR + 'review/runtime_fact_mapping.json'),
            'rbase_comparison': source.json(TEAM_DIR + 'review/rbase_comparison.json'),
            'human_behavior_approved': False, 'demo_approved': False}
    if followup is not None:
        path = 'docs/customer_type_library/future_action_signal_review_20261023/README.md'
        text = followup.raw(path).decode('utf-8-sig')
        cases = []
        for line in text.splitlines():
            cells = [s.strip() for s in line.strip().strip('|').split('|')]
            if len(cells) == 3 and re.match(r'A\d\d-F\d+', cells[0]):
                cases.append({'runtime_fact_id': re.match(r'A\d\d-F\d+[a-z]?', cells[0]).group(),
                              'reported_connection': view_text(cells[1]), 'review_question': view_text(cells[2]),
                              'behavior_impact_verified': False})
        result['future_signal_review'] = {'source_pr': 105, 'common_commit': followup.ref,
            'source_path': path, 'sha256': digest(text.encode()), 'cases': cases,
            'applied_to_engine': False, 'joint_approved': False}
    if supplemental is not None:
        d = 'docs/data/persona_evidence_signal_followup_shh_20261023/'
        hypotheses = supplemental.json(d + '행동가설_20건_후속검수.json')
        proposals = supplemental.json(d + '기계필드_정정제안_7건.json')
        splits = supplemental.json(d + '혼합행동단계_분리의견_5건.json')
        cross_cases = supplemental.json(d + 'PR105_네사례_교차의견.json')
        comparisons = supplemental.json(d + '미래계획_신호제외_아침저녁_대조결과.json')
        source_index = supplemental.json(d + '선택이유_사용근거와전체색인_구분.json')
        result['pr106_review'] = {
            'source_pr': 106, 'source_commit': supplemental.ref,
            'review_only': True, 'applied_to_profiles_or_engine': False,
            'hypothesis_reviews': len(hypotheses['items']),
            'machine_field_proposals': len(proposals['changes']),
            'machine_field_status': proposals['status'],
            'mixed_action_stage_opinions': len(splits['items']),
            'pr105_followups': len(cross_cases['items']),
            'comparison_scope': comparisons['runtime_scope'],
            'comparison_runtime_commit': comparisons['runtime_commit'],
            'comparison_customer_decisions': comparisons['customer_decisions'],
            'comparison_scenario_calls': comparisons['scenario_calls'],
            'comparison_model_calls': comparisons['model_calls'],
            'source_index_checks': len(source_index['checks']),
            'a05_reference_review': {
                'source_fact_id': 'A05-F08', 'runtime_fact_id': 'A05-F08a',
                'relationship': 'distinct_ids_under_review_not_aliases',
                'profile_or_runtime_change_applied': False
            },
            'shared_paths': [d + name for name in [
                '행동가설_20건_후속검수.json', '기계필드_정정제안_7건.json',
                '혼합행동단계_분리의견_5건.json', 'PR105_네사례_교차의견.json',
                '미래계획_신호제외_아침저녁_대조결과.json',
                '선택이유_사용근거와전체색인_구분.json']],
            'human_review_complete': False, 'joint_approved': False
        }
        result['pr107_library_followup'] = {
            'source_pr': 107, 'source_commit': supplemental.ref,
            'candidate_additions': 5, 'candidate_ids': ['N28', 'N29', 'N30', 'N31', 'N32'],
            'total_candidate_inventory': 60, 'validated_profiles': 0,
            'runtime_agents_added': 0,
            'morning_exposure_rows': 155, 'afternoon_additional_exposure_rows': 36,
            'afternoon_overlap_with_morning': 0,
            'next_in_depth_profile_proposals': ['A16', 'N04', 'N09', 'N24', 'A20', 'A13', 'A15', 'A25', 'N14', 'N16'],
            'photo_and_source_link_indexes_included': False,
            'applied_to_runtime': False
        }
    return result


def build(source, existing, runtime, followup=None, supplemental=None):
    before_runtime = json.dumps(runtime, sort_keys=True, ensure_ascii=False)
    manifest = source.json(TEAM_DIR + 'manifest.json')
    for name, expected in manifest['files'].items():
        if digest(source.raw(TEAM_DIR + name)) != expected:
            raise ValueError('shared export hash mismatch: ' + name)
    handoff = source.json(HANDOFF_PATH)
    raw_cards, raw_exclusions = source.raw(CARD_PATH), source.raw(EXCLUSION_PATH)
    for raw, expected in [(raw_cards, handoff['source_card_sha256']), (raw_exclusions, handoff['source_exclusion_sha256'])]:
        if digest(raw) != expected:
            raise ValueError('candidate/exclusion hash mismatch')
    cards = list(csv.DictReader(io.StringIO(raw_cards.decode('utf-8-sig'))))
    base_candidate_count = len(cards)
    supplemental_receipts = {}
    visit_features, priority_rows, additional_exposures = {}, {}, []
    if supplemental is not None:
        additions_raw = supplemental.raw(CARD_ADDITIONS_PATH)
        additions = list(csv.DictReader(io.StringIO(additions_raw.decode('utf-8-sig'))))
        features_raw = supplemental.raw(VISIT_FEATURES_PATH)
        feature_rows = list(csv.DictReader(io.StringIO(features_raw.decode('utf-8-sig'))))
        priority_raw = supplemental.raw(PRIORITY_ADDITIONS_PATH)
        priorities = list(csv.DictReader(io.StringIO(priority_raw.decode('utf-8-sig'))))
        exposure_raw = supplemental.raw(EXPOSURE_ADDITIONS_PATH)
        additional_exposures = list(csv.DictReader(io.StringIO(exposure_raw.decode('utf-8-sig'))))
        expected_new = ['N28', 'N29', 'N30', 'N31', 'N32']
        if [r['ID'] for r in additions] != expected_new:
            raise ValueError('unexpected #107 candidate additions')
        if len(feature_rows) != 60 or len({r['ID'] for r in feature_rows}) != 60:
            raise ValueError('invalid #107 visit-feature inventory')
        if len(additional_exposures) != 36:
            raise ValueError('invalid #107 additional exposure count')
        visit_features = {r['ID']: r for r in feature_rows}
        priority_rows = {r['ID']: r for r in priorities}
        if set(visit_features) != set(ids := [c['ID'] for c in cards] + expected_new):
            raise ValueError('candidate IDs do not match #107 visit-feature inventory')
        cards.extend(additions)
    ids = [c['ID'] for c in cards]
    if len(ids) != len(set(ids)) or ids[:base_candidate_count] != handoff['candidate_ids']:
        raise ValueError('duplicate, missing or reordered candidate IDs')
    profiles = {a: source.json(TEAM_DIR + f'profiles/{a}.json') for a in manifest['active_author_ids']}
    previous = {p['id']: p for p in existing['personas']}
    out = copy.deepcopy(existing)
    out['personas'] = []
    out['sources'].update(team=source.ref, pr98='익명 선별본 #104 · 원본 #98 · 2e1575e',
                          slgi='#99 병합 · #102 집계 공유 · 상세 검수표 미수령',
                          review='선별 #103 · 의견층/정정 제안 · 공동 승인 아님',
                          followup_106_107=supplemental.ref if supplemental else None)
    reviews = review_payload(source, followup, supplemental)
    for c in cards:
        pid = c['ID']
        p = copy.deepcopy(previous.get(pid, {}))
        p.update(id=pid, group='first10' if c['그룹'] == '1차 정밀' else 'reserve', candidate_cohort=c['그룹'],
                 owner=c['담당'], type=c['탐색용 주유형'], type_group=display.group_of(c['탐색용 주유형']),
                 start=c['시작 글'], analysis_priority=c['우선순위'],
                 pick=view_text(c['한눈에 보일 행동']) or '상세 내용은 제한 공유 검수 자료 참조',
                 caution=view_text(c['주의']) or '',
                 reported_status={'profile': c['프로필 상태'], 'engine': c['엔진 상태']})
        if pid in visit_features:
            vf = visit_features[pid]
            pr = priority_rows.get(pid)
            p['visit_feature_summary'] = {k: view_text(vf.get(k, '')) for k in [
                '방문 형태', '방문 시기 (본문)', '결제 · 혜택 언급 (본문 낱말 · 이용 확정 아님)', '원문 상태']}
            p['priority_proposal'] = ({'category': pr.get('구분'), 'reason': view_text(pr.get('이유')),
                                      'owner_proposal': pr.get('담당안 (제안)')}
                                     if pr else None)
        p.setdefault('archive_posts', None)
        p.setdefault('start_post', c['시작 글'])
        p.setdefault('label', None)
        p.setdefault('thumb', display.thumb_of(c['한눈에 보일 행동']))
        if pid in profiles:
            if pid not in runtime:
                raise ValueError('missing existing runtime snapshot for ' + pid)
            profile = profiles[pid]
            projected = display.pr98_profile(json.dumps(legacy_view_contract(profile), ensure_ascii=False), runtime[pid])
            # These audit fields are not in the shared export; do not invent zeros.
            projected['audit'].update(missing_sources='별도 검수', review_requests='별도 검수')
            p.update(projected)
            p['team_profile'] = {'source_commit': source.ref, 'contract': profile['schema_version'],
                                 'review_status': profile['review_status'], 'engine_input_replaced': False}
            p['status'] = dict(explore=True, profile='done', reviewed=False, sim=True,
                               note='익명 최신 분석 · 현재 R-BASE 입력과 별도 버전 · 검수/승인 전')
        else:
            p['status'] = dict(explore=True, profile='progress' if pid in {'A01','A03','A06','A08','A09'} else 'none',
                               reviewed=False, sim=False, note='상세 추출/검수 대기 · 후보를 실행 입력으로 변환하지 않음')
        own = [r for r in reviews['cross_review']['items'] if r['author'] == pid]
        p['team_review'] = {'review_ids': [r['review_id'] for r in own], 'index': 'team_review_index.json',
                            'joint_approved': False, 'detail_status': 'not_received' if pid in reviews['slgi']['authors'] else 'shared_analysis_only'}
        out['personas'].append(p)
    # Retain development personas verbatim; they are not part of the 55 team candidates.
    for p in existing['personas']:
        if p['id'] not in ids:
            out['personas'].append(copy.deepcopy(p))
    exclusion_rows = len(list(csv.DictReader(io.StringIO(raw_exclusions.decode('utf-8-sig')))))
    if supplemental is not None:
        morning_keys = {(r.get('아카이브 번호'), r.get('REV_ID')) for r in csv.DictReader(io.StringIO(raw_exclusions.decode('utf-8-sig')))}
        afternoon_keys = {(r.get('아카이브 번호'), r.get('REV_ID')) for r in additional_exposures}
        if morning_keys & afternoon_keys:
            raise ValueError('afternoon exposure records overlap morning exclusion records')
    out['team_data'] = {'commit': source.ref, 'supplemental_commit': supplemental.ref if supplemental else None,
                        'candidate_count': len(ids), 'base_candidate_count': base_candidate_count,
                        'shared_profile_count': len(profiles),
                        'new_candidate_ids': [c['ID'] for c in cards if c['그룹'] == '신규 후보'],
                        'additional_exposure_rows': len(additional_exposures),
                        'additional_exposure_ids': [r.get('REV_ID') for r in additional_exposures],
                        'evaluation_exclusion_rows': len(list(csv.DictReader(io.StringIO(raw_exclusions.decode('utf-8-sig'))))),
                        'evaluation_exclusion_sha256': digest(raw_exclusions), 'runtime_input_updated': False,
                        'private_links_included': False,
                        'source_hashes': {'team_base': dict(source.receipts),
                                          'followup_106_107': dict(supplemental.receipts) if supplemental else {}}}
    if json.dumps(runtime, sort_keys=True, ensure_ascii=False) != before_runtime:
        raise AssertionError('runtime input mutated')
    for data in [out, reviews]:
        if display.IDENT.search(json.dumps(data, ensure_ascii=False)):
            raise ValueError('identifier/URL detected in shared display output')
    return out, reviews


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--team-repo', required=True)
    ap.add_argument('--team-ref', default=TEAM_BASE)
    ap.add_argument('--review-ref', default=REVIEW_BASE)
    ap.add_argument('--supplemental-ref', default=SUPPLEMENTAL_BASE)
    ap.add_argument('--output', type=Path, default=display.OUT)
    ap.add_argument('--review-output', type=Path, default=REVIEW_OUT)
    a = ap.parse_args()
    source = TeamSource(a.team_repo, a.team_ref)
    existing = json.loads(display.OUT.read_text(encoding='utf-8'))
    runtime = json.loads(display.ENGINE.read_text(encoding='utf-8'))['personas']
    library, review = build(source, existing, runtime, TeamSource(a.team_repo, a.review_ref),
                            TeamSource(a.team_repo, a.supplemental_ref))
    a.output.write_text(json.dumps(library, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    a.review_output.write_text(json.dumps(review, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'team_commit': source.ref, 'team_candidates': library['team_data']['candidate_count'], 'library_entries': len(library['personas']),
                      'shared_profiles': 5, 'cross_review_items': len(review['cross_review']['items']),
                      'runtime_input_updated': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
