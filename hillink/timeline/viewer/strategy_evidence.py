"""Read-only recommendation evidence. Caller must enforce existing customer permissions.

Uses existing analyst provenance; neither scores nor author identity are inferred.
No private corpus is copied, no source URL is reconstructed from a Fact identifier.
"""
import json
import hashlib
from functools import lru_cache
from pathlib import Path

ENGINE_PROFILES = Path(__file__).resolve().parents[1] / 'experiments/persona_live/operator_choice/operator_world_v1_1/turn_personas_ext.local.json'

PROFILE = Path(__file__).resolve().parents[1] / 'experiments/persona_live/operator_choice/author_method_v4_1_artifacts/profiles_and_quality.json'


@lru_cache(maxsize=32)
def source_digest(path, size, modified):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def anchors_for(pid, path):
    try:
        local = json.loads(path.read_text()).get(pid, {})
    except (OSError, ValueError):
        return {}, None
    valid = {}
    for fid, anchors in local.get('facts', {}).items():
        for anchor in anchors:
            try:
                source = Path(anchor['path']); stat = source.stat()
                if source_digest(str(source), stat.st_size, stat.st_mtime_ns) != anchor['sha256']:
                    continue
            except (OSError, KeyError):
                continue
            valid.setdefault(fid, []).append({k: anchor[k] for k in ('source_id', 'page', 'sha256', 'excerpt', 'check_scope') if k in anchor})
    return valid, local.get('relationship') if valid else None


def project(customer, reviewer=False, profiles_path=PROFILE, sources_path=None, links=None, engine_profiles_path=ENGINE_PROFILES):
    pid = customer['id']
    try:
        author = json.loads(profiles_path.read_text()).get('authors', {}).get(pid, {})
    except (OSError, ValueError):
        author = {}
    scopes = author.get('scope_profiles', {})
    full = scopes.get('recent_added', {})
    facts = {k:v for k,v in customer.get('engine', {}).get('facts', {}).items() if not v.get('hidden') and v.get('gist')}
    # Existing facet ancestry is distinct from analyst pattern contributions. Never
    # infer a pattern, score, recurrence or semantic approval from a facet level.
    facets = customer.get('strategy_facets')
    if facets is None:
        try:
            registered = json.loads(engine_profiles_path.read_text()).get('personas', {}).get(pid, {})
            facets = registered.get('traits', {}).get('facets', {}) if registered.get('id') == pid else {}
        except (OSError, ValueError):
            facets = {}
    facet_evidence = {}
    for name, facet in facets.items():
        rows = [{'fact_id': e['fact_id'], 'grade': e.get('grade'), 'feature': e.get('feature')}
                for e in facet.get('evidence', []) if e.get('fact_id') in facts]
        if rows:
            facet_evidence[name] = {'present': facet.get('present') is True,
                                    'evidence': rows, 'human_review': 'pending'}
    anchors, relationship = anchors_for(pid, sources_path or Path(__file__).with_name('strategy_sources.local.json'))
    locations = {}
    patterns = {}
    for scope, data in scopes.items():
        for name, pattern in data.get('patterns', {}).items():
            for contribution in pattern.get('contributions', []):
                for fid in contribution.get('fact_ids', []):
                    if fid in facts:
                        at = locations.setdefault(fid, {'posts': set(), 'scopes': set(), 'experiences': set()})
                        at['posts'].update(contribution.get('post_ids', []))
                        at['scopes'].add(scope)
                        if contribution.get('experience_group'):
                            at['experiences'].add(contribution['experience_group'])
    for name, pattern in full.get('patterns', {}).items():
        contributions = [{'fact_ids': [f for f in c.get('fact_ids', []) if f in facts],
                          'post_ids': c.get('post_ids', []), 'experience_group': c.get('experience_group')}
                         for c in pattern.get('contributions', [])]
        contributions = [c for c in contributions if c['fact_ids']]
        if contributions:
            patterns[name] = {'contributions': contributions, 'status': pattern.get('status'),
                              'qualifications': [f for f in pattern.get('opposing_or_qualified_facts', []) if isinstance(f,str) and f in facts and not facts[f].get('hidden')],
                              'recurrence': pattern.get('recurrence', {}),
                              'human_review': full.get('human_review', 'pending')}
    safe_links = {}
    if reviewer:
        for post, item in (links or {}).items():
            url = item.get('url') if isinstance(item, dict) else item
            if isinstance(url, str) and url.startswith(('https://', 'http://')):
                safe_links[post] = url
    out = []
    for fid, f in facts.items():
        if f.get('hidden') or not f.get('gist'):
            continue
        at = locations.get(fid, {})
        posts = set(at.get('posts', set())) | ({f['post']} if f.get('post') else set())
        experiences = set(at.get('experiences', set())) | ({f['exp']} if f.get('exp') else set())
        source = ('WALKERHILL' if f.get('wh') is True or 'walkerhill_only' in at.get('scopes', set()) else
                  'SAME_AUTHOR_OTHER' if f.get('wh') is False or at else 'UNRESOLVED')
        out.append({'id': fid, 'summary': f['gist'], 'features': f.get('features', []),
                    'kind': f.get('kind'), 'polarity': f.get('polarity'),
                    **({k:f.get(k) for k in ('actor','time_scope','action_stage')} if customer.get('isolated_qa') else {}),
                    'source': source, 'posts': sorted(posts), 'experiences': sorted(experiences),
                    'source_links': [{'post': post, 'url': safe_links[post]} for post in sorted(posts) if post in safe_links],
                    'quote': None,
                    'anchors': [{k:v for k,v in at.items() if reviewer or k!='excerpt'} for at in anchors.get(fid,[])],
                    'source_status': 'SOURCE_SEGMENT_CHECKED' if anchors.get(fid) else 'EXTRACTED_SUMMARY', 'review_required': True})
    return {'customer_id': pid, 'facts': out, 'patterns': patterns,
            'facet_evidence': facet_evidence, 'semantic_status': 'SEMANTIC_HOLD',
            'version': 'CUSTOMER_EVIDENCE_V3', 'human_review': full.get('human_review', 'pending'),
            'relationship': relationship or {'status':'UNCONFIRMED','note':'동행 인원이나 유형 분류만으로 커플·부부 관계를 확정하지 않습니다.'},
            'limitations': ['후기 추출 요약과 연구상 반복 후보입니다. 원문 미연결 항목은 원문 검증 완료가 아닙니다.',
                           '경험 묶음 수는 독립 방문 횟수나 전환 확률이 아닙니다. 외부 경험의 현재 방문 전이는 가설입니다.']}
