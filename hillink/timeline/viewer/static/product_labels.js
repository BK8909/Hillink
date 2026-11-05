/* Display-only names from this immutable run's candidate/order contracts.
 * Load before UX_STORY so its opts.label resolver prefers integrated names.
 * No request, candidate, order, or ledger value is modified. */
(() => {
  const original = agU06ActionName;
  let owner = null, names = new Map();
  const valid = n => typeof n === 'string' && n && !['다른 활동','기타'].includes(n);
  function index(flow) {
    if (owner === flow) return;
    owner = flow; names = new Map();
    function contract(c, action) {
      if (!c) return;
      if (valid(c.label)) {
        if (action) names.set(action,c.label);
        if (c.sku_id) { names.set(c.sku_id,c.label); names.set('HC_'+c.sku_id,c.label); }
      }
      for (const part of c.components || []) contract(part);
    }
    for (const plan of Object.values(flow?.plans || {})) {
      for (const d of plan.m4?.decisions || []) for (const c of d.packet?.candidates || []) {
        if (valid(c.label)) names.set(c.candidate_id,c.label);
        contract(c.sku_contract,c.candidate_id);
      }
      for (const s of plan.scenes || []) contract(s.basis?.charge?.sku_contract,s.act);
    }
    for (const run of flow?.runs || []) for (const c of run.customers || []) {
      for (const candidate of c.candidates || []) {
        if (valid(candidate.product_label)) names.set(candidate.product_id,candidate.product_label);
        contract(candidate.sku_contract,candidate.product_id);
      }
      if (valid(c.choice?.product_label)) names.set(c.choice.product_id,c.choice.product_label);
      contract(c.choice?.sku_contract,c.choice?.product_id);
    }
  }
  agU06ActionName = function(id) { const flow = typeof MODE !== 'undefined' && MODE === 'evidence' && typeof BH !== 'undefined' && BH.context ? BH.snapshots.get(BH.context.run_id)?.flow?.result : (typeof AG !== 'undefined' && AG.flow?.result); index(flow); return names.get(id) || original(id); };
  window.HillinkProductLabels = {source:'CURRENT_RUN_CANDIDATE_AND_SKU_CONTRACT',resolve: id => agU06ActionName(id)};
})();
