"""Read-only evidence availability and same-state score attribution.

A missing link is not dislike. Existing menu polarity is not a new source
judgment. No source prose, URLs, new preferences or confidence coefficients.
"""
from copy import deepcopy

INDIRECT = ('food','space','value_check','benefit','novelty','premium',
            'practical_alt','rest_need','routine','post_appraisal','breakfast_priority')

def observation(traits):
    facets=traits.get('facets',{});index=traits.get('evidence_index',{})
    menus=[]
    for m in traits.get('menu',[]):
        ids=list(dict.fromkeys(m.get('fact_ids',[])))
        if not ids or not m.get('tags') or not m.get('weight'):continue
        menus.append(dict(tags=list(m['tags']),fact_ids=ids,
            polarity='POSITIVE_LINK' if m['weight']>0 else 'NEGATIVE_LINK',
            directness=m.get('directness','NOT_VERIFIED_IN_RUNTIME_INPUT'),
            status='EXISTING_PROFILE_LINK_NOT_NEW_SOURCE_APPROVAL'))
    indirect={k:list(dict.fromkeys(e['fact_id'] for e in facets.get(k,{}).get('evidence',[])
        if e.get('grade')!='exclude' and e.get('fact_id'))) for k in INDIRECT}
    food_ids=list(dict.fromkeys(e['fact_id'] for e in facets.get('food_specific',{}).get('evidence',[])
        if e.get('grade')!='exclude' and e.get('fact_id')))
    linked={i for m in menus for i in m['fact_ids']}
    unmapped=[i for i in food_ids if i not in linked]
    status='LINKED_PREFERENCE' if menus else 'FOOD_EVIDENCE_UNMAPPED' if food_ids else 'UNOBSERVED_IN_ACCEPTED_INPUT'
    relevant={i for ids in indirect.values() for i in ids}|set(food_ids)|linked
    missing=sorted(i for i in relevant if i not in index)
    opposing={k:f.get('opposing_count') for k,f in facets.items() if k in INDIRECT or k=='food_specific'}
    return dict(version='FOOD_OBSERVATION_V1',status=status,menu_links=menus,
        indirect_fact_ids={k:v for k,v in indirect.items() if v},unmapped_food_fact_ids=unmapped,
        source_quality=dict(directness='REUSE_EXPLICIT_METADATA_ONLY_OTHERWISE_UNVERIFIED',
            repetition='NOT_INFERRED_FROM_FACT_COUNT',counterevidence='NOT_PROVEN_ABSENT',
            recorded_opposing_counts=opposing,missing_index_fact_ids=missing,
            confidence='NOT_A_NUMERIC_CONFIDENCE_SCORE'),
        interpretation='No observed preference is neither a negative preference nor zero utility; existing choice rules remain unchanged.')

def neutral_evidence(traits):
    out=deepcopy(traits)
    for f in out.get('facets',{}).values():f['evidence']=[]
    out['menu']=[];out['venues']={}
    return out

def contribution(terms,common):
    # Same candidate, time, state and price. Not a contribution to probability
    # or a full-visit causal estimate. Original global coefficients are retained.
    a=round(sum(t['value'] for t in terms),6);b=round(sum(t['value'] for t in common),6)
    factors={}
    for t in common:factors[t['factor']]=factors.get(t['factor'],0)+t['value']
    rows=[]
    for t in terms:
        base=factors.pop(t['factor'],0)
        rows.append(dict(factor=t['factor'],actual=t['value'],common=round(base,6),
            evidence_delta=round(t['value']-base,6),fact_ids=t.get('fact_ids',[])))
    rows.extend(dict(factor=k,actual=0,common=round(v,6),evidence_delta=round(-v,6),fact_ids=[]) for k,v in factors.items())
    return dict(method='SAME_STATE_QUANTITATIVE_EVIDENCE_ABLATION',actual=a,
        common=b,evidence_delta=round(a-b,6),terms=rows,
        excludes='M4 context adjustment and continuation value; planner bars not ablated')
