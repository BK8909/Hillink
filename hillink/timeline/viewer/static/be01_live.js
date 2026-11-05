/* Explicit per-tab pilot. No stored visit is supplied to the execution engine. */
(() => {
  'use strict';
  const VERSION='BE01_SHARED_TIME_INTAKE_25fc2a899514_active';
  const indices=new WeakMap();
  const state={enabled:new URLSearchParams(location.search).get('be01')==='1',version:VERSION,service:'http://127.0.0.1:8898',runs:new Set(),pending:null};
  async function service(path,body) {
    const response=await fetch(state.service+path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{cache:'no-store'});
    const result=await response.json();if(!response.ok||result.error)throw new Error(result.error||'새 방문 실행 서비스에 연결하지 못했습니다.');return result;
  }
  const originalApi=api;
  api=async function(url,request,...rest) {
    if(url==='/api/visit'&&(state.enabled||request.behavior_engine==='be01')) {
      if(state.enabled||request.behavior_engine==='be01') {
        if(request.duration!=='stay_2'||request.event_mode!=='wine'||request.package_id||(request.scenario&&request.scenario.event_card_id!=='WINE_FAIR_2026_AUTUMN'))throw new Error('BE01 시범은 2박·와인페어 방문에서 실행할 수 있습니다.');
        request.behavior_engine='be01';
      }
      let job=await service('/api/visit',request);state.pending=job.job_id;
      while(job.status==='pending') {await new Promise(resolve=>setTimeout(resolve,2000));job=await service('/api/jobs/'+job.job_id);}
      state.pending=null;if(job.status!=='complete'||!job.result)throw new Error(job.error||'새 방문 계산을 완료하지 못했습니다.');
      const result=job.result;NewVisitContract.last=NewVisitContract.validate(request,result);state.runs.add(result.ledger.run_id);return result;
    }
    const serviceRun=id=>id&&(state.runs.has(id)||(NewVisitContract.last?.run_id===id&&NewVisitContract.last.engine.execution_service==='LOCAL_ASYNC_PRODUCT_ADAPTER_V1')||(typeof AG!=='undefined'&&AG.flow?.ledger?.run_id===id&&AG.flow.result?.engine?.execution_service==='LOCAL_ASYNC_PRODUCT_ADAPTER_V1'));
    if(url.startsWith('/api/ledger/')&&url!=='/api/ledger/demo'&&request&&[request.run_id,request.baseline_id,request.scenario_id].some(serviceRun))return service(url,request);
    return originalApi.call(this,url,request,...rest);
  };
  const savedView=typeof hlReasonView==='function'?hlReasonView:null;
  hlReasonView=function(flow,pid,index) {
    const data=flow&&(flow.result||flow),b=data&&data.be01,L=flow&&(flow.ledger||data.ledger);
    if(!b)return savedView?savedView(flow,pid,index):null;
    const scene=data.plans?.[pid]?.scenes[index],eid=scene?.basis?.m4?.event_id;
    if(!scene||!eid||!L||b.version!==VERSION||data.engine?.policy_version!==VERSION||b.execution_run_id!==data.visit_id||L.run_id!==(b.product_ledger_run_id||b.native_ledger.run_id))return null;
    if(!indices.has(data)) {
      const map=new Map();for(const r of b.reason_bundle?.records||[]) {const key=JSON.stringify([r.run_id,r.customer_id,r.actual_event_id]);map.set(key,map.has(key)?null:r);}indices.set(data,map);
    }
    const r=indices.get(data).get(JSON.stringify([b.execution_run_id,pid,eid]));if(!r||r.run_id!==b.execution_run_id||r.customer_id!==pid||r.actual_event_id!==eid)return null;
    if(r.time.date!==scene.visit_date||r.time.start!==agHM(scene.t0))return null;
    return {...r,live_execution:true,record_id:r.reason_record_id,source_engine:'BE01_LIVE',registered_version:VERSION,bundle_version:b.reason_bundle.version,sentences:[r.basic_summary],tags:r.basic_tags||[],method_label:r.final_method==='SHARED_TRANSITION_FINAL_CONTRACT'?'계획·후속 상태 비교 · 규칙 기반':'기록된 공통 절차·후보 선택',actual_final_method:r.final_method,fact_ids:[...new Set((r.user_sentences||[]).flatMap(x=>x.fact_ids||[]))],identity:{run_id:L.run_id,execution_run_id:b.execution_run_id,customer_id:pid,event_id:eid,scene_index:index},raw_record:r,invocation_id:b.invocation_id,computed_at:b.computed_at,provider_calls:b.provider_calls};
  };
  const savedHTML=typeof hlReasonEvidenceHTML==='function'?hlReasonEvidenceHTML:null;
  hlReasonEvidenceHTML=function(record) {
    if(!record?.live_execution)return savedHTML?savedHTML(record):'';
    return `<section class="ux-evidence-raw" data-live-be01-reason="${esc(record.record_id)}"><h3>최종 선택 이유</h3><p class="frp-note">${esc(record.method_label)}</p><p data-basic-summary>${esc(record.basic_summary)}</p><div class="frp-chips">${record.tags.map(t=>`<span>${esc(t)}</span>`).join('')}</div><details data-reason-details><summary>판단 근거·후속 계획·실행 정보</summary><p>${esc(record.registered_version)} · LLM 호출 ${record.provider_calls}회</p><p>미확정 가격은 비용 비교의 한계로 유지합니다. 잠정 계획은 활동 이력으로 완료를 확인하며 반복 의도의 고유 완료까지 보장하지 않습니다.</p><p>기본 M4 제안은 최종 선택의 이유와 구분합니다.</p><pre>${esc(JSON.stringify({identity:record.identity,invocation_id:record.invocation_id,computed_at:record.computed_at,record:record.raw_record},null,2))}</pre></details></section>`;
  };
  const originalScenes=typeof agScenes==='function'?agScenes:null;
  if(originalScenes)agScenes=function(pid,...args) {
    const scenes=originalScenes.call(this,pid,...args),flow=AG.flow,plan=flow?.result?.plans?.[pid];
    if(!flow?.result?.be01||!plan)return scenes;
    return scenes.map(scene=>{
      const event=scene.basis?.m4?.event_id;if(!event||scene.k==='move')return scene;
      const index=plan.scenes.findIndex(raw=>raw.basis?.m4?.event_id===event&&raw.t0===scene.t0&&raw.visit_date===scene.visit_date);
      const reason=index<0?null:hlReasonView(flow,pid,index);
      return reason?{...scene,why:reason.basic_summary,why_source:'MATCHED_LIVE_BE01_EVENT',reason_record_id:reason.record_id}:scene;
    });
  };
  const originalModel=typeof bhModel==='function'?bhModel:null;
  if(originalModel)bhModel=function(snapshot,context) {
    const model=originalModel.call(this,snapshot,context);
    if(!model?.flow?.result?.be01)return model;
    const reason=hlReasonView(model.flow,context.customer_id,context.scene_index),event=model.raw.basis?.m4?.event_id;
    if(!reason||!event)return model;
    // BE01 reissues packet hashes. The handed-off actual event is authoritative;
    // the original packet, native proposal and source scenes remain immutable.
    const matches=(model.plan.m4?.decisions||[]).filter(d=>d.actual_next_event_id===event&&d.packet?.context_factors?.customer_id===context.customer_id);
    const exact=matches.filter(d=>d.selected_action===model.raw.act),native=(exact.length?exact:matches).at(-1);
    if(!native)return model;
    const decision=reason.actual_final_method==='SHARED_TRANSITION_FINAL_CONTRACT'?{...native,sampling:null,native_sampling_before_policy:native.sampling}:native;
    return {...model,decision,row:decision.packet.candidates.find(c=>c.candidate_id===decision.selected_action)||null};
  };
  window.BE01Live=state;
})();
