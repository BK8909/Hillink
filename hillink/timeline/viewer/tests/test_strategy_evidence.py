import hashlib
import json
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('strategy_evidence', Path(__file__).parents[1] / 'strategy_evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_projection_checks_source_digest_and_permissions(tmp_path):
    source = tmp_path / 'private.pdf'
    source.write_bytes(b'authorized test source')
    anchors = tmp_path / 'sources.json'
    anchors.write_text(json.dumps({'C': {'facts': {'F': [{'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'page': 2, 'source_id': 'provided', 'excerpt': 'private excerpt'}]}}}))
    profiles = tmp_path / 'profiles.json'
    profiles.write_text(json.dumps({'authors': {'C': {'scope_profiles': {'recent_added': {'patterns': {'food_exploration': {'contributions': [{'fact_ids': ['F', 'HIDDEN'], 'post_ids': ['P'], 'experience_group': 'G'}]}}}}}}}))
    customer = {'id': 'C', 'engine': {'facts': {'F': {'gist': 'visible summary'}, 'HIDDEN': {'gist': 'private hidden', 'hidden': True}}}}
    public = module.project(customer, profiles_path=profiles, sources_path=anchors)
    assert [f['id'] for f in public['facts']] == ['F']
    assert public['patterns']['food_exploration']['contributions'][0]['fact_ids'] == ['F']
    assert 'excerpt' not in public['facts'][0]['anchors'][0]
    assert str(source) not in json.dumps(public)
    private = module.project(customer, reviewer=True, profiles_path=profiles, sources_path=anchors)
    assert private['facts'][0]['anchors'][0]['excerpt'] == 'private excerpt'
    source.write_bytes(b'changed source')
    changed = module.project(customer, reviewer=True, profiles_path=profiles, sources_path=anchors)
    assert changed['facts'][0]['anchors'] == []
    assert changed['facts'][0]['source_status'] == 'EXTRACTED_SUMMARY'


def test_missing_provenance_does_not_invent_repetition_or_relationship(tmp_path):
    result = module.project({'id': 'C', 'engine': {'facts': {'F': {'gist': 'one fact'}}}}, profiles_path=tmp_path / 'absent', sources_path=tmp_path / 'absent2')
    assert result['patterns'] == {}
    assert result['facts'][0]['posts'] == []
    assert result['facts'][0]['quote'] is None
    assert result['relationship']['status'] == 'UNCONFIRMED'


def test_team_profile_provenance_and_authorized_post_links(tmp_path):
    customer = {'id': 'C', 'engine': {'facts': {'F': {'gist': 'registered summary', 'post': 'P', 'exp': 'E', 'wh': True}, 'H': {'gist': 'hidden', 'hidden': True, 'post': 'SECRET'}}}}
    links = {'P': {'url': 'https://example.com/post', 'title': 'source'}, 'SECRET': {'url': 'https://example.com/private'}}
    kwargs = dict(profiles_path=tmp_path/'absent.json', sources_path=tmp_path/'absent-sources.json', links=links)
    public = module.project(customer, **kwargs)
    private = module.project(customer, reviewer=True, **kwargs)
    f = private['facts'][0]
    assert f['posts'] == ['P'] and f['experiences'] == ['E']
    assert f['source'] == 'WALKERHILL'
    assert f['source_links'] == [{'post': 'P', 'url': 'https://example.com/post'}]
    assert not public['facts'][0]['source_links']
    assert 'SECRET' not in json.dumps(private)


def test_facet_ancestry_filters_hidden_ids_without_inventing_patterns(tmp_path):
    import copy
    customer={'id':'C','engine':{'facts':{'F':{'gist':'visible','features':['opaque-event']},'H':{'gist':'hidden','hidden':True}}},'strategy_facets':{'space':{'present':True,'level':.9,'evidence':[{'fact_id':'F','feature':'opaque-event','grade':'exclude'},{'fact_id':'H','grade':'rep'}]}}}
    original=copy.deepcopy(customer)
    out=module.project(customer,profiles_path=tmp_path/'none',sources_path=tmp_path/'no-source')
    assert out['patterns']=={}
    assert out['facet_evidence']['space']['evidence']==[{'fact_id':'F','feature':'opaque-event','grade':'exclude'}]
    assert 'level' not in out['facet_evidence']['space']
    assert out['semantic_status']=='SEMANTIC_HOLD'
    assert out['facts'][0]['posts']==[] and customer==original


def test_registered_facet_lookup_requires_same_customer_identity(tmp_path):
    path=tmp_path/'profiles.json';path.write_text(json.dumps({'personas':{'C':{'id':'OTHER','traits':{'facets':{'space':{'present':True,'evidence':[{'fact_id':'F','grade':'rep'}]}}}}}}))
    out=module.project({'id':'C','engine':{'facts':{'F':{'gist':'visible'}}}},profiles_path=tmp_path/'none',engine_profiles_path=path)
    assert out['facet_evidence']=={}
