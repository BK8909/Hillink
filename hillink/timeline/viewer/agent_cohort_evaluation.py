"""Paired autonomous simulation comparisons, never causal-effect approval.

Accept only matching policies, implementations, model settings and visit
conditions, with a single declared catalog discount changed per pair.
Fixed-choice repricing and scored-rule controls do not qualify.
"""
import copy
import agent_evaluation as E


def compare(pairs, *, sku_id, discount_percent, venue_id):
    rows=[];holds=[];customers=set()
    for baseline,treatment in pairs:
        a=copy.deepcopy(baseline['request']);b=copy.deepcopy(treatment['request'])
        ids=a.get('personas',[])
        reason=[]
        if len(ids)!=1 or b.get('personas')!=ids:
            holds.append(dict(code='PAIR_CUSTOMER_MISMATCH'));continue
        pid=ids[0]
        if pid in customers:reason.append('DUPLICATE_CUSTOMER_NOT_INDEPENDENT_COHORT_MEMBER')
        customers.add(pid)
        options=copy.deepcopy(a.get('catalog_options') or {})
        if sku_id in options.get('discount_percent',{}):reason.append('BASELINE_ALREADY_DISCOUNTED')
        options.setdefault('discount_percent',{})[sku_id]=discount_percent
        expected=copy.deepcopy(a);expected['catalog_options']=options
        if b!=expected:reason.append('MORE_THAN_DECLARED_DISCOUNT_CHANGED')
        ca=baseline.get('configuration') or {};cb=treatment.get('configuration') or {}
        for key in ('policy','model','effort','source_sha256','world_policy','needs_policy','memory'):
            if ca.get(key) is None or ca.get(key)!=cb.get(key):reason.append('CONFIGURATION_MISMATCH:'+key)
        if not str(ca.get('policy','')).startswith('LLM_AUTONOMOUS_CUSTOMER_'):
            reason.append('AUTONOMOUS_POLICY_REQUIRED')
        measures=[];profiles=[];models=[];implementations=[]
        for side in (baseline,treatment):
            flow=side['result']
            if 'error' in flow:
                reason.append('EXECUTION_ERROR');continue
            audit=E.audit(flow,pid)
            if audit['contract_status']!='CHECKED_NO_CONTRACT_ISSUE':reason.append('EXECUTION_CONTRACT_HOLD')
            decisions=flow['plans'][pid].get('autonomous_decisions',[])
            profiles.append({d.get('profile_evidence_sha256') for d in decisions})
            implementations.append({d.get('implementation_sha256') for d in decisions})
            models.append({d.get('attempts',[{}])[-1].get('provider',{}).get('model_returned')
                           for d in decisions if d.get('attempts')})
            if not decisions:reason.append('NO_AUTONOMOUS_DECISIONS')
            for d in decisions:
                if d.get('execution_state')!='EXECUTED':reason.append('INCOMPLETE_DECISION')
                if not d.get('attempts') or d['attempts'][-1].get('provider',{}).get('execution') not in ('LIVE_RESPONSES','CACHE_REPLAY'):
                    reason.append('LIVE_OR_PROVEN_LIVE_REPLAY_REQUIRED')
            rr=flow['ledger']['receipts'][pid]['rows']
            target=[r for r in rr if r.get('venue_id')==venue_id]
            # Included breakfast access is not paid dinner conversion.
            target_sku=[r for r in target if (r.get('sku_id') or r.get('product_id'))==sku_id]
            measures.append(dict(hotel_paid_krw=flow['ledger']['totals']['paid_krw'],
                target_venue_paid_krw=sum(r['paid_krw'] for r in target),
                target_sku_paid_krw=sum(r['paid_krw'] for r in target_sku),
                target_sku_quantity=sum(r['quantity'] for r in target_sku),
                target_sku_selected=bool(target_sku),target_venue_used=bool(target)))
        if len(profiles)!=2 or not profiles[0] or None in profiles[0] or profiles[0]!=profiles[1]:
            reason.append('PROFILE_EVIDENCE_MISMATCH_OR_MISSING')
        if len(models)!=2 or not models[0] or None in models[0] or models[0]!=models[1]:
            reason.append('RETURNED_MODEL_MISMATCH_OR_MISSING')
        if (len(implementations)!=2 or not implementations[0] or None in implementations[0]
                or implementations[0]!=implementations[1]):reason.append('EXECUTED_IMPLEMENTATION_MISMATCH_OR_MISSING')
        if reason:
            holds.append(dict(customer_id=pid,codes=sorted(set(reason))));continue
        x,y=measures
        rows.append(dict(customer_id=pid,baseline=x,treatment=y,
            delta={k:y[k]-x[k] for k in x},
            status='PAIRED_SIMULATED_REDECISIONS_NOT_CAUSAL_EFFECT'))
    totals={}
    if rows:
        totals={k:sum(r['delta'][k] for r in rows) for k in rows[0]['delta']}
    return dict(policy='AUTONOMOUS_COHORT_COMPARISON_V1',
        intervention=dict(sku_id=sku_id,discount_percent=discount_percent,venue_id=venue_id),
        paired_customers=len(rows),pairs=rows,holds=holds,aggregate_delta=totals,
        status='HOLD_INCOMPARABLE_PAIRS' if holds else 'EXPLORATORY_PAIRED_SIMULATION',
        causal_effect='NOT_ESTABLISHED',human_semantic_approval=False,
        limitations=['One response per condition does not estimate response variability or a causal discount effect.',
            'Customer conditions are matched within each pair, not asserted homogeneous across the cohort.',
            'Revenue is simulated; SKU purchase, venue use and included access are separate.',
            'Only already registered catalog discount is tested; other operational levers remain unsupported.'])
