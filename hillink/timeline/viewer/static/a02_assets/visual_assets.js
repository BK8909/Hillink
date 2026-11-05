/* W44-A02 display-only adapter. No profile, request, engine, or ledger writes. */
(() => {
  'use strict';
  if (window.A02Assets) return;
  const VERSION = 'w44-a02-20261028-v3';
  const assetRelations = {
    solo_casual: ['solo'], solo_hiker: ['solo'], solo_office: ['solo'],
    couple_vacation: ['couple', 'spouse'], couple_smart: ['couple', 'spouse'],
    couple_wine: ['couple', 'spouse'], friends_2f: ['friends'],
    family_kid1: ['family_kids'], family_kid2: ['family_kids'],
    family_3gen: ['family_multigeneration'],
  };
  const normalize = rel => ({friend:'friends',friends:'friends',couple:'couple',spouse:'spouse',solo:'solo',family_kids:'family_kids',family_parents:'family_parents',family_multigeneration:'family_multigeneration'}[rel] || 'group');
  const compatible = (a,b) => normalize(a) === normalize(b) || ['couple','spouse'].includes(normalize(a)) && ['couple','spouse'].includes(normalize(b));
  const neutral = n => Array.from({length:n}, (_, i) => ['adult','adultB','adultC','adultD','adultE','adultF'][i % 6]);
  const slotFor = (rel, n) => rel === 'family_parents' && n === 3 ? 'family_parents_3' : rel === 'friends' && n === 3 ? 'friends_neutral_3' : `neutral_group_${n}`;
  const contract = {thumbnailBindings:{}, pendingSharedSlots:['neutral_group_2','neutral_group_3']};

  // An illustration's identity and member count are independent from type icons.
  // A future shared slot is used only after its manifest explicitly verifies it.
  function resolve({pid, size, visit=null, observed=null, direct=null, pool={}, partyMembers={}, partyLabels={}}) {
    const n = Number.isInteger(Number(size)) && Number(size) >= 1 && Number(size) <= 8 ? Number(size) : null;
    const source = observed && observed.label || null;
    if (n === null) return {n:null, rel:'group', members:[], av:null, src:source, match:false, label:'인원 확인 전', scen:'인원 확인 전', asset_status:'UNCERTAIN_PARTY', asset_slot:null};
    const v = visit && Number(visit.party_size) === n ? visit : null;
    const sourceFits = observed && observed.n === n;
    const overridden = !!(v && (v.layer === 'operator_override' || v.condition_source === 'operator_selected_scenario'));
    let rel = n === 1 ? 'solo' : v ? normalize(v.rel) : sourceFits ? normalize(observed.rel) : direct && direct.rel && direct.supported === n ? normalize(direct.rel) : 'group';
    if (n > 1 && rel === 'solo') rel = 'group';
    if (v && rel === 'group' && !overridden && sourceFits && observed.rel) rel = normalize(observed.rel);
    const sourceRelMatches = sourceFits && observed.rel && compatible(observed.rel, rel);
    const sourceMatches = sourceFits && (!observed.rel || compatible(observed.rel,rel));
    const savedMembers = sourceRelMatches && partyMembers[observed.rel];
    const members = savedMembers && savedMembers.length === n ? [...savedMembers] : neutral(n);
    const fits = key => !!(key && pool[key] && pool[key].n_members === n && (assetRelations[key] || []).includes(rel));
    let key = null;
    // Preserve an existing ID-specific sprite only when its visit relation fits.
    if (direct && direct.supported === n && fits(direct.av)) {
      if (!/^family_/.test(direct.av) || sourceRelMatches) key = direct.av;
    }
    if (!key && sourceRelMatches && observed.av && fits(observed.av)) key = observed.av;
    if (!key && rel === 'solo') key = ['solo_casual','solo_office','solo_hiker'].find(fits) || null;
    if (!key && (rel === 'couple' || rel === 'spouse')) key = ['couple_vacation','couple_smart','couple_wine'].find(fits) || null;
    if (!key && rel === 'friends' && n === 2 && fits('friends_2f')) key = 'friends_2f';
    const genericSlot = `neutral_group_${n}`;
    for (const slot of [slotFor(rel,n),genericSlot]) {
      const future=pool[slot];
      if (!key && future && future.a02_verified === true && future.n_members === n && (future.visit_relations || []).includes(rel)) key=slot;
    }
    const label = sourceMatches ? observed.label : `${partyLabels[rel] || (rel === 'group' ? '동행 미확인' : rel)} · ${n}인`;
    return {n, rel, members, av:key, src:source, match:!!sourceMatches, label, scen:`${n}인`, asset_status:key?'VALID':'PENDING_ASSET', asset_slot:key?null:genericSlot};
  }

  function visitOf(pid, n) {
    const data = typeof AG === 'undefined' ? null : AG;
    if (!data) return null;
    // Never borrow another customer's visit, or substitute a package occupancy.
    const v = data.visits && data.visits[pid];
    if (v && Number(v.party_size) === Number(n)) return v;
    const one = data.oneVisit;
    return one && one.pid === pid && one.v && Number(one.v.party_size) === Number(n) ? one.v : null;
  }
  function composition(pid, n, relOverride) {
    const direct = typeof AG_AVMAP !== 'undefined' ? AG_AVMAP[pid] : null;
    let observed = typeof AG_COMP !== 'undefined' ? AG_COMP[pid] : null;
    if (!observed && typeof dnoParty === 'function') {
      const record = dnoParty(pid);
      if (record.n && ['REVIEW_OBSERVED','USER_CONFIRMED'].includes(record.origin)) {
        observed = {n:record.n,label:record.label,rel:record.origin === 'USER_CONFIRMED' && direct && direct.supported === record.n ? direct.rel : null};
      }
    }
    let visit = visitOf(pid, n);
    if (relOverride != null) visit = {...(visit || {}),party_size:n,rel:relOverride};
    return resolve({pid,size:n,visit,observed,direct,pool:typeof AG !== 'undefined' && AG.avm || {},partyMembers:typeof AG_PARTY !== 'undefined' ? AG_PARTY : {},partyLabels:typeof AG_PARTY_LABEL !== 'undefined' ? AG_PARTY_LABEL : {}});
  }

  const originalVisitConditions = typeof agVC === 'function' ? agVC : null;
  function visitConditions(pid, run) {
    const data = typeof AG !== 'undefined' ? AG : null;
    const current = run || data && data.res;
    const exact = current && (current.customers || []).find(c => c.persona_id === pid);
    if (exact && exact.vc) return exact.vc;
    const v = pid && data && data.visits && data.visits[pid];
    if (v) return {
      stay:!!v.stay,B:v.stay?v.building:null,
      bl:v.stay && ((data.meta && data.meta.buildings || {})[v.building] || v.building) || '',
      party:v.party_size,phase:v.stay?v.phase:'visit',nights:v.nights,v,
    };
    // An absent customer cannot inherit another customer's first run conditions.
    if (pid && current && !exact) return {stay:false,B:null,bl:'',party:null,phase:'visit',v:null,unresolved:true};
    return originalVisitConditions ? originalVisitConditions(pid,run) : {stay:false,B:null,bl:'',party:null,phase:'visit',v:null,unresolved:true};
  }

  const originalThumb = typeof libThumbP === 'function' ? libThumbP : null;
  function thumbnail(p, cls='') {
    const binding = contract.thumbnailBindings[p.id];
    if (binding && binding.target_customer_id === p.id && binding.status === 'STAGING_CANDIDATE' && binding.policy_hold === false && binding.src && binding.sha256) {
      return `<div class="lb-th ${cls}" data-a02-thumb="${esc(p.id)}"><img src="${esc(binding.src)}" alt="콘셉트 이미지 · 실제 사진 아님 · 시각 승인 전" loading="lazy"></div>`;
    }
    const override = typeof LIB_THUMB_OVERRIDE !== 'undefined' && LIB_THUMB_OVERRIDE[p.id];
    if (p.id === 'A03' && override && override.status === 'DISPLAY_ONLY_TEMP_CROSS_CUSTOMER_ASSET_REVIEW' && override.src === '/static/demo_thumbs/no0003_couple_room_temp.webp') {
      // This file belongs to a different source customer; no canonical join exists.
      const type = typeof libTypeOf === 'function' && libTypeOf(p);
      return `<div class="lb-th lb-th0 lb-thn ${cls}" data-a02-thumb="PENDING_ID_MATCH" title="고객 고유 이미지 연결 확인 중">${libIcon(type || '전체',40)}<span>고객 이미지 준비 중</span></div>`;
    }
    return originalThumb ? originalThumb(p,cls) : '';
  }

  window.A02Assets = Object.freeze({version:VERSION,resolve,composition,visitConditions,contract,slotFor});
  if (originalVisitConditions) agVC = visitConditions;
  if (typeof agComp === 'function') agComp = (pid,n) => composition(pid,n);
  if (typeof agAvKey === 'function') agAvKey = (pid,rel,n) => composition(pid,n,rel).av;
  if (typeof agAvFallback === 'function') agAvFallback = (pid,rel,n) => composition(pid,n,rel).av;
  if (originalThumb) libThumbP = thumbnail;
})();
