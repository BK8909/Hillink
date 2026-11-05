"""Generic event-owned explanations and meal audits; no persona-specific prose or outcome targets."""
import json,hashlib,re,argparse
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('run_dir');args=ap.parse_args();O=Path(args.run_dir);x=json.loads((O/'run.json').read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
def has_unknown_price(node):
 if isinstance(node,dict):
  if node.get('feasible') and any('가격 미확인' in v.get('factor','') for v in node.get('terms',[])):return True
  return any(has_unknown_price(v) for v in node.values() if isinstance(v,(dict,list)))
 if isinstance(node,list):return any(has_unknown_price(v) for v in node)
 return False
records=[];audits=[];links=[];profiles=x['profiles'];row_checks=[]
for pid,p in x['flow']['plans'].items():
 facts=profiles[pid]['traits']['evidence_index'];events=p['m4']['activity_history'];decisions=p['m4']['decisions'];by={e['event_id']:e for e in events}
 for si,sc in enumerate(p['scenes']):
  eid=sc.get('basis',{}).get('m4',{}).get('event_id');event=by.get(eid)
  if not event:continue
  action=event['action_id'];matches=[(i,d) for i,d in enumerate(decisions) if d.get('actual_next_event_id')==eid];exact=[(i,d) for i,d in matches if d.get('selected_action')==action];match=(exact or matches)
  di,d=match[-1] if match else (None,None);pkt=d['packet'] if d else {};context=pkt.get('context_factors',{});candidates=pkt.get('candidates',[]);candidate=next((c for c in candidates if c['candidate_id']==action),None)
  edge=[e for e in x['execution_lineage'] if e['actual_event_id']==eid];tr=[(i,t) for i,t in enumerate(x['policy_trace']) if t.get('proposal_id') in {e['proposal_id'] for e in edge}]
  used=[];trait_sources=[];alternatives=[];method=d.get('decision_mode',pkt.get('kind','NATIVE_RULE')) if d else 'NATIVE_RULE';refs=[dict(file='run.json',jsonpath=f'$.flow.plans.{pid}.scenes[{si}]')];next_plan=None;preplan=None
  if tr:
   ti,t=tr[-1];terms=t['selected_terms'];used=list(dict.fromkeys(f for v in terms if v['value']>0 for f in v.get('fact_ids',[])));alternatives=t['candidates'];context=t['context'];method='SHARED_TRANSITION_FINAL_CONTRACT';next_plan=t['next_plan'];preplan=dict(plan=t['prior_plan'],status=t['prior_plan_status'],completion_semantics='ACTION_HISTORY_MATCH_NOT_UNIQUE_PLAN_INSTANCE; REPEATED_ACTION_COMPLETION_UNRESOLVED',comparison=t['prior_plan_comparison']);refs.append(dict(file='run.json',jsonpath=f'$.policy_trace[{ti}]'))
   names=[v['factor'] for v in sorted(terms,key=lambda v:-v['value']) if v.get('fact_ids') and v['value']>0][:2]
   summary=f"{('·'.join(names)+'에 연결된 개인 근거와 ') if names else ''}이 시점의 상태·운영 조건 및 후속 대안을 비교해 {sc['label']}을 선택했습니다."
   if preplan['plan']:summary+=' 이전 잠정 계획도 다시 비교했으며 자동 우선권은 주지 않았습니다.'
  elif candidate:
   terms=candidate.get('terms',[]);used=list(dict.fromkeys(candidate.get('candidate_fact_ids',[])+[f for v in terms if v.get('value',0)>0 for f in v.get('fact_ids',[])]));alternatives=candidates
   marg=sorted([(k,v) for k,v in candidate.get('profile_feature_marginals',{}).items() if v.get('weight_delta_at_fixed_state',0)>0],key=lambda kv:-kv[1]['weight_delta_at_fixed_state'])
   labels={'food':'음식 경험','space':'조망·공간','rest_need':'휴식','warm_rest':'온수 휴식','routine':'익숙한 경험','alcohol_familiar':'주류 경험','benefit':'혜택 활용','premium':'고급 경험','value_check':'가격 비교','novelty':'새 경험','practical_alt':'실용적 대안','food_specific':'구체적인 음식 기호','breakfast_priority':'조식 관심'}
   for key,val in marg[:2]:
    facet=key.split('.')[-1];ev=profiles[pid]['traits']['facets'].get(facet,{}).get('evidence',[]);trait_sources.append(dict(feature=key,value=val['value'],marginal=val['weight_delta_at_fixed_state'],source_evidence=ev,role='FEATURE_PROVENANCE_NOT_RETROSPECTIVE_DIRECT_FACT_INPUT'))
   names=[labels.get(v['feature'].split('.')[-1],v['feature']) for v in trait_sources]
   summary=f"{('·'.join(names)+' 성향이 후보 평가에 반영된 가운데, ') if names else ''}현재 이용 가능한 대안 중 {sc['label']}을 선택했습니다."
   if used:summary=f"이 고객의 관련 이용·선호 근거를 반영해, 현재 가능한 대안 중 {sc['label']}을 선택했습니다."
   refs.append(dict(file='run.json',jsonpath=f'$.flow.plans.{pid}.m4.decisions[{di}]'))
  else:
   summary=sc.get('why') or f"기존 방문 절차에 따라 {sc['label']}을 수행했습니다."
   if action in ('room_rest','ROOM_REST'):summary='앞선 활동 뒤 현재 상태에 적용되는 기존 휴식 규칙에 따라 객실에서 쉬었습니다.'
  incomplete_price=bool(tr and any('가격 미확인' in v.get('factor','') for v in tr[-1][1]['selected_terms']))
  comparison_incomplete=incomplete_price
  if tr:
   evaluation_path=O/'evaluations'/tr[-1][1]['evaluation']
   comparison_incomplete=has_unknown_price(json.loads(evaluation_path.read_text()))
  if incomplete_price:summary+=' 이 식사의 금액은 미확인이라 비용까지 비교한 결론은 아닙니다.'
  missing=[f for f in used if f not in facts];row_checks.append(dict(customer_id=pid,event_id=eid,missing_direct_fact_ids=missing))
  record=dict(reason_record_id=digest([x['run_id'],pid,eid]),run_id=x['run_id'],customer_id=pid,actual_event_id=eid,time=dict(date=event['date'],start=event['start'],end=event['end']),action=action,final_method=method,basic_summary=summary,basic_tags=['후기 근거·성향 추론'] if used or trait_sources else ['공통 절차·모의 상태'],user_sentences=[dict(text=summary,source_refs=refs,fact_ids=used,explanation_type='RECORD_BASED_NOT_MODEL_PROSE')],personal_evidence={f:facts[f] for f in used if f in facts},trait_lineage=trait_sources,context=context,alternatives=alternatives,sampling=d.get('sampling') if d else None,prior_plan=preplan,next_plan=next_plan,execution_contract=edge,decision_comparability='INCOMPLETE_PRICE_COMPARISON' if comparison_incomplete else 'RECORDED_MODEL_COMPARISON',limitations=['Fatigue and meal fractions are model states, not measured physiology.','Missing direct evidence is not filled with another customer facts.'])
  records.append(record);sc['reason_record_id']=record['reason_record_id']
 for di,d in enumerate(decisions):
  packet=d['packet'];cs=packet['candidates'];ctx=packet['context_factors'];sel=d.get('selected_action')
  meal=any(str(c.get('candidate_id','')).startswith('lunch_') for c in cs) or any(c.get('meal_fraction',0)>0 for c in cs) or str(sel).startswith('BREAKFAST')
  if not meal:continue
  sampling=d.get('sampling') or {};weights=sampling.get('candidate_weights',{});clamped=[c['candidate_id'] for c in cs if c.get('final_score') is not None and c['final_score']<.05 and c['candidate_id'] in weights]
  traces=[(i,t) for i,t in enumerate(x['policy_trace']) if t['customer_id']==pid and t['date']==ctx['date'] and t['time']==ctx['time']]
  audits.append(dict(run_id=x['run_id'],engine_version=x['engine_version'],customer_id=pid,date=ctx['date'],time=ctx['time'],jsonpath=f'$.flow.plans.{pid}.m4.decisions[{di}]',native_packet=packet,policy_trace_indices=[i for i,t in traces],selected=sel,actual_action=d.get('actual_next_action'),execution_status=d.get('execution_status'),sampling=sampling,clamped_to_same_floor=clamped,profile_sha=profiles[pid]['sha'],policy='LOOKAHEAD_ACTIVE' if traces else 'NATIVE_SAMPLING_OR_SCORE',score_floor_note='Existing .05 sampling floor; not a learned probability; retained rather than tuned for restaurant balance.'))
by_reason={(r['customer_id'],r['actual_event_id']):r for r in records}
for pid,receipt in x['ledger']['receipts'].items():
 events=x['flow']['plans'][pid]['m4']['activity_history']
 for row in receipt['rows']:
  es=[e for e in events if e['date']==row['visit_date'] and e['start']==row['time'] and e['action_id'] in (row['action_id'],row.get('product_id'))];e=es[0] if len(es)==1 else None
  links.append(dict(run_id=x['run_id'],customer_id=pid,row_id=row['row_id'],event_id=e['event_id'] if e else None,reason_record_id=by_reason.get((pid,e['event_id']),{}).get('reason_record_id') if e else None,action=row['action_id'],paid_krw=row['paid_krw']))
(O/'reasons.json').write_text(json.dumps(dict(version='BE01_GENERIC_EVENT_REASON_V1',run_id=x['run_id'],records=records),ensure_ascii=False))
(O/'meal_audit.json').write_text(json.dumps(audits,ensure_ascii=False));(O/'transaction_links.json').write_text(json.dumps(links,ensure_ascii=False));(O/'reason_checks.json').write_text(json.dumps(row_checks,ensure_ascii=False))
print(json.dumps(dict(run_id=x['run_id'],reasons=len(records),meal_decisions=len(audits),missing_facts=sum(bool(r['missing_direct_fact_ids']) for r in row_checks))))
