"""Private customer admission helpers. No facts, sources or identity data in Git."""
import copy,hashlib,json,re
from pathlib import Path

STAGES=('SOURCE_QA','SEMANTIC_QA','SCHEMA_READY','TECH_ACCEPTED','RUNNABLE','DEMO_APPROVED')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def save(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with p.open('x') as f:
        p.chmod(0o600);json.dump(value,f,ensure_ascii=False,indent=2,default=list)
def ref(p):
    p=Path(p).resolve();return dict(path=str(p),sha256=sha(p.read_bytes()))
def history_holds(facts):
    return [f['fact_id'] for f in facts if f.get('time_scope') in ('mixed','future','recommended')]
def library(pid,facts):
    return dict(id=pid,group='isolated_pilot',engine=dict(facts={f['fact_id']:dict(gist=f['detail'],features=[f['feature_key']],kind=f['kind'],wh=f['scope']=='walkerhill' and f['actor']=='author' and f['time_scope'] in ('source_experience','historical') and f['kind'] not in ('expectation','decline'),source_scope=f['scope'],post_id=f['post_id'],experience_key=f['experience_key'],actor=f['actor'],time_scope=f['time_scope'],action_stage=f['action_stage']) for f in facts}))
def export(pid,facts):
    omit={'anchors','source_sha256_private','source_location','source_location_private','original_text_private'}
    return dict(schema_version='team_persona_shared_export_v1',author_group_id=pid,review_status='ISOLATED_TECHNICAL_CANDIDATE_HUMAN_PENDING',facts=[{k:v for k,v in f.items() if k not in omit} for f in facts])
def semantic_audit(profile,facts):
    """Audit actual calculated facet evidence, without treating intent as history."""
    by={f['fact_id']:f for f in facts};errors=[];context=[];excluded=[]
    for facet,value in profile['traits']['facets'].items():
        for e in value['evidence']:
            f=by[e['fact_id']]
            if e['grade']=='exclude':
                excluded.append(dict(fact_id=e['fact_id'],facet=facet,reason='ZERO_RELEVANCE_WEIGHT_AUDIT_ONLY'));continue
            if f['actor'] in ('other','unknown'):errors.append(dict(fact_id=e['fact_id'],facet=facet,reason='OTHER_ACTOR_IN_PERSONAL_TRAIT'))
            if facet in ('routine','food','space','alcohol_familiar') and (f['time_scope'] in ('mixed','future','recommended') or f.get('kind')=='expectation'):errors.append(dict(fact_id=e['fact_id'],facet=facet,reason='NONOBSERVED_IN_HISTORY'))
            if (f['time_scope'] in ('mixed','future','recommended') or f.get('kind')=='expectation'):context.append(dict(fact_id=e['fact_id'],facet=facet,classification='NONOBSERVED_PREFERENCE_OR_CONTEXT_NOT_CONSUMPTION_HISTORY'))
    return dict(errors=errors,excluded_link_annotations=excluded,nonobserved_preference_context=context,human_review='PENDING',scope='TARGETED_ACTOR_TIME_AND_ACTUAL_FACET_LINKS_NOT_FULL_HUMAN_SEMANTIC_APPROVAL')
def temporal_record(row,text,as_of='2026-10-30'):
    """Separate collection classification from verified publication dates.

    Post-number interpolation and dates merely mentioned in a story are not
    evidence of publication recency. No latent-trait coefficients are changed.
    """
    estimated=row.get('publication_date_est');basis=row.get('date_basis')
    dates=sorted(set(re.findall(r'(?<!\d)((?:19|20)\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})',text)))
    verified=row.get('verified_publication_date') if basis in ('explicit_publication_header','source_metadata_verified') else None
    return dict(post_id=row['post_id'],declared_collection_scope=row['scope'],publication_date_estimate=estimated,date_estimate_basis=basis,
                verified_publication_date=verified,publication_date_evidence='NOT_SUPPLIED' if not verified else basis,
                temporal_class='UNVERIFIED_RECENCY' if not verified else 'VERIFIED_PUBLICATION_DATE',
                recent_label_is_verified=False if not verified else None,mentioned_dates=['-'.join(x) for x in dates],mentioned_dates_are_publication_dates=False,
                recency_bonus_allowed=False,correction='RECENT_COLLECTION_SCOPE_IS_NOT_A_VERIFIED_RECENT_POST' if row['scope']=='recent' and not verified else None,as_of=as_of)
