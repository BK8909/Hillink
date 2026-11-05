/* Validate fresh API responses only. Saved visits and source records stay untouched. */
(() => {
  'use strict';
  function fail(code) {
    const error=new Error('새 실행의 고객·행동·거래 연결을 확인하지 못했습니다.');
    error.code=code;
    throw error;
  }
  function sameIds(a,b) {return JSON.stringify([...a].sort())===JSON.stringify([...b].sort());}
  function validate(request,flow) {
    const ids=request && request.personas,ledger=flow && flow.ledger;
    if(!Array.isArray(ids)||!ids.length||new Set(ids).size!==ids.length)fail('REQUEST_CUSTOMERS');
    if(!ledger||ledger.source!=='live_engine'||!ledger.run_id||!flow.visit_id)fail('LIVE_RUN_ID');
    if(!sameIds(ids,Object.keys(flow.plans||{}))||!sameIds(ids,Object.keys(flow.visits||{}))||!sameIds(ids,Object.keys(ledger.receipts||{})))fail('RESPONSE_CUSTOMERS');
    const be01=request.behavior_engine==='be01';
    if(!flow.engine || (be01
      ? flow.engine.behavior_engine!=='m4_c01'||flow.engine.requested_behavior_engine!=='be01'||flow.engine.policy_version!=='BE01_SHARED_TIME_INTAKE_25fc2a899514_active'
      : flow.engine.behavior_engine!==(request.behavior_engine||'m4')))fail('ENGINE_ID');
    if(flow.engine.execution_mode!=='LIVE_COMPUTATION_NOT_REPLAY')fail('NOT_FRESH_COMPUTATION');
    if(request.scenario && flow.visit?.scenario_snapshot?.event_card_id!==request.scenario.event_card_id)fail('SCENARIO_NOT_EXECUTED');
    const snapshot=flow.visit?.scenario_snapshot;
    if(snapshot && (ledger.context?.scenario_id!==snapshot.scenario_id||ledger.context?.scenario_snapshot_sha256!==snapshot.snapshot_sha256))fail('SCENARIO_LEDGER');
    for(const id of ids) {
      const plan=flow.plans[id],visit=flow.visits[id],receipt=ledger.receipts[id];
      if(receipt.customer_id!==id||receipt.visit_id!==flow.visit_id||receipt.party_size!==visit.party_size||receipt.building!==visit.building)fail('CUSTOMER_VISIT');
      for(const row of receipt.rows||[])if(row.customer_id!==id||row.run_id!==ledger.run_id||row.visit_id!==flow.visit_id)fail('TRANSACTION_OWNER');
      for(const decision of plan.m4?.decisions||[])if(decision.packet?.context_factors?.customer_id!==id)fail('REASON_OWNER');
    }
    if(be01) {
      const b=flow.be01;
      if(!b||b.execution_run_id!==flow.visit_id||b.reason_bundle?.run_id!==flow.visit_id||b.provider_calls!==0||flow.engine.llm_calls!==0||(b.product_ledger_run_id||b.native_ledger?.run_id)!==ledger.run_id)fail('BE01_RUN_OWNER');
      if(b.native_ledger.totals.paid_krw!==ledger.totals.paid_krw||b.native_ledger.totals.unknown_count!==ledger.totals.unknown_count)fail('BE01_LEDGER_ARITHMETIC');
      for(const id of ids)if(b.native_ledger.customer_totals[id]?.paid_krw!==ledger.receipts[id].paid_krw||b.native_ledger.customer_totals[id]?.unknown_count!==ledger.receipts[id].unknown_count)fail('BE01_CUSTOMER_LEDGER');
    }
    return Object.freeze({run_id:ledger.run_id,visit_id:flow.visit_id,customer_ids:[...ids],engine:{...flow.engine},scenario_id:snapshot?.scenario_id||null});
  }
  const original=typeof api==='function'?api:null;
  const state={version:'product-new-visit-contract-v1',last:null,validate};
  if(original)api=async function(url,request,...rest) {
    const result=await original.call(this,url,request,...rest);
    if(url==='/api/visit'&&result&&!result.error)state.last=validate(request,result);
    return result;
  };
  window.NewVisitContract=state;
})();
