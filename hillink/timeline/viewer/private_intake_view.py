"""Local isolated intake presentation. Never changes publication/approval data."""
import re
import hashlib
from operator_choice.operator_world_v1_1 import isolated_registry as IR

def project(pid, strategy=False):
    profiles=IR.registrations()
    if pid not in profiles: raise ValueError('PRIVATE_CUSTOMER_NOT_REGISTERED')
    profile,lineage=profiles[pid]
    library=IR.extend_library({})[pid]
    def gist(value):
        text=str(value or '')
        if re.search(r'https?://|www\.|blog\.naver|/Users/|@[A-Za-z0-9_]+',text):
            return '비공개 출처 세부는 표시하지 않음 · Fact ID로 추적'
        return text
    facts={k:{'gist':gist(x.get('gist')),'kind':x.get('kind'),'wh':x.get('wh'),'actor':x.get('actor'),'time_scope':x.get('time_scope')} for k,x in library['engine']['facts'].items()}
    if strategy:
        # Internal evidence projection, after the caller's existing local authorization.
        # Preserve source tags; opaque grouping keys prevent exposing private post identifiers.
        for fid, f in facts.items():
            raw = library['engine']['facts'][fid]
            f.update(features=list(raw.get('features', [])), action_stage=raw.get('action_stage'),
                     polarity=raw.get('polarity'), hidden=raw.get('hidden', False))
            for source, dest in [('post_id', 'post'), ('experience_key', 'exp')]:
                if raw.get(source):
                    f[dest] = 'group-' + hashlib.sha256((pid+'|'+source+'|'+str(raw[source])).encode()).hexdigest()[:24]
    facets={k:{'level':x.get('level'),'present':x.get('present'),'evidence':[{'fact_id':e['fact_id'],'grade':e.get('grade'),'feature':e.get('feature')} for e in x.get('evidence',[])]} for k,x in profile['traits']['facets'].items()}
    customer=dict(id=pid,label='비공개 기술 검수 고객',isolated_qa=True,engine=dict(facts=facts,n=len(facts)))
    if strategy:
        customer['strategy_facets'] = facets
    return dict(customer=customer,
                facets=facets,lineage=lineage,technical_stage='RUNNABLE',human_approval=False,public_approval=False,demo_approval=False,
                holds=['골프 행동·상품 HOLD · 정상 방문은 허용'] if pid=='WH-00276' else [],
                caution='기술 실행 검수용 · 사람 의미 승인 및 공개·시연 승인과 별도 · 게시일 미확인 자료를 최근 50편으로 간주하지 않음')
