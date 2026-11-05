// Recommendation policy only: never writes behavior traits, catalog contracts, orders or ledger.
(function(root){'use strict';
const unique=a=>[...new Set(a.filter(Boolean))];
const decisionId=r=>JSON.stringify([r.customer_id,r.date,r.slot,r.packet_sha256||null,r.event_id||null,r.time]);
const NAMES={THE_BUFFET:'더뷔페',PIZZA_HILL:'피자힐',GEUMRYONG:'금룡',MOEGI:'모에기',MYONGWOLGWAN:'명월관',ONDAL:'온달',DELVINO:'델비노',THE_PAVILION:'파빌리온',IRD:'룸서비스',EXTERNAL_DELIVERY:'외부 배달'};
const RULES=[
 {id:'experience',label:'미식·새 경험',patterns:['food_exploration','premium_experience'],features:/food_exploration|chef_course|two_flavors|dessert_trial|limited_menu|menu_explor/,causes:['MENU'],needs:'테마 메뉴 제공 여부·기간·예약·경험 조건의 실험 입력'},
 {id:'food',label:'음식 취향',patterns:['food_specificity'],features:/pizza.*preference|two_flavors|shellfish|truffle|shrimp_pizza|breakfast_menu|chefs_kitchen_breakfast|pasta.*(preference|revisit)|dish_no_revisit|overordered/,causes:['MENU','MEAL_NEED'],needs:'등록 메뉴의 재료·판매 단위·동행 인원에 맞는 구성'},
 {id:'benefit',label:'혜택 활용',patterns:['benefit_use','seasonal_promotion_response'],features:/discount|coupon|voucher|included_amenities|three_sessions|with_promo/,causes:['INCLUSION','PRICE'],needs:'혜택 대상·중복 적용·포함 인원·이용 횟수 계약'},
 {id:'space',label:'공간·분위기',patterns:['space_atmosphere'],features:/ambience|night_view|footbath|window|terrace|suite_stay/,causes:['SPACE'],needs:'목표 업장의 실제 좌석·전망·배정 방식·예약 가능 여부'},
 {id:'convenience',label:'예약·편의',patterns:['travel_convenience_purchase'],features:/prebook|openrun|queue|before_checkin|checkout_praise|machine_failure/,causes:['TIME','PLAN','STATE'],needs:'예약 가능한 시간·이동 동선·다음 일정과의 충돌'},
 {id:'value',label:'가격 대비 가치',patterns:['prepurchase_value','post_value_appraisal','practical_alternative'],features:/price|value|cost_planning|with_promo|discount_but_unsatisfied|overordered/,causes:['PRICE','VALUE_CHECK'],needs:'실제 메뉴 구성·총액·추가 비용·포함 혜택의 비교 기준'}
];
// Exact existing facet meanings, used only when no semantic feature/pattern is mapped.
// Generic novelty/promo/practical_alt are deliberately not aliases for dining motivation.
const FACET_RULES={food:['food_specific'],benefit:['benefit'],space:['space'],value:['value_check','post_appraisal']};
const sourceUsable=f=>!['other','unknown'].includes(f.actor)&&!['future','recommended','mixed'].includes(f.time_scope);
// Keep the existing fallback policy until its cross-category links are semantically reviewed.
// Diagnostics expose suppressed rep links without approving them or changing recommendation ranks.
function facetAudit(bundle){
 const facts=(bundle?.facts||[]).filter(sourceUsable),byId=new Map(facts.map(f=>[f.id,f]));
 const triggers=RULES.flatMap(r=>[
  ...facts.filter(f=>(f.features||[]).some(t=>r.features.test(t))).map(f=>({kind:r.id,fact_id:f.id,path:'FEATURE',excluded:(FACET_RULES[r.id]||[]).some(name=>(bundle?.facet_evidence?.[name]?.evidence||[]).some(e=>e.fact_id===f.id&&e.grade==='exclude'))})),
  ...r.patterns.filter(k=>bundle?.patterns?.[k]?.contributions?.length).map(k=>({kind:r.id,path:'PATTERN',pattern:k}))
 ]);
 const suppressed=triggers.length?RULES.flatMap(r=>(FACET_RULES[r.id]||[]).flatMap(name=>{
  const facet=bundle?.facet_evidence?.[name];if(!facet?.present)return [];
  return (facet.evidence||[]).filter(e=>e.grade==='rep'&&byId.has(e.fact_id)&&(byId.get(e.fact_id).features||[]).includes(e.feature)).map(e=>({kind:r.id,facet:name,fact_id:e.fact_id,grade:e.grade,feature:e.feature}));
 })):[];
 return {semantic_mapped:triggers.length>0,triggers,suppressed_rep_links:suppressed,policy:'EXISTING_CUSTOMER_WIDE_FALLBACK',review_status:'SEMANTIC_HOLD'};
}
function facetLinks(bundle,rule){
 if(facetAudit(bundle).semantic_mapped)return [];
 const byId=new Map((bundle?.facts||[]).map(f=>[f.id,f]));
 return (FACET_RULES[rule.id]||[]).flatMap(name=>{
  const facet=bundle?.facet_evidence?.[name];if(!facet?.present)return [];
  return (facet.evidence||[]).filter(e=>e.grade==='rep'&&byId.has(e.fact_id)&&sourceUsable(byId.get(e.fact_id))&&(byId.get(e.fact_id).features||[]).includes(e.feature)).map(e=>({...e,facet:name,basis:'EXISTING_FACET_LINK',semantic_status:'SEMANTIC_HOLD'}));
 });
}
const qualified=f=>['negative','mixed'].includes(f.polarity)||(f.features||[]).some(t=>/qualified|exceptions|nonpreference|not_|unsatisfied|regret|no_revisit|price_cap|failure/.test(t));
function observationUnits(facts){
 // A shared post OR experience merges observations; multiple facts from one post never add votes.
 const units=[];for(const f of facts){const keys=new Set([...(f.posts||[]).map(x=>'p:'+x),...(f.experiences||[]).map(x=>'e:'+x)]);if(!keys.size)continue;const hits=units.filter(s=>[...keys].some(k=>s.has(k)));for(const h of hits){for(const k of h)keys.add(k);units.splice(units.indexOf(h),1);}units.push(keys);}return units.length;
}
function evidence(bundle,rule){
 const facts=(bundle?.facts||[]).filter(sourceUsable),byId=new Map(facts.map(f=>[f.id,f]));
 const patterns=rule.patterns.map(k=>({name:k,...bundle?.patterns?.[k]})).filter(p=>p.contributions?.length);
 const matched=f=>rule.features instanceof RegExp?(f.features||[]).some(t=>rule.features.test(t)):(f.features||[]).some(t=>(rule.features||[]).includes(t));
 const ancestry=facetLinks(bundle,rule);
 const excluded=new Set((FACET_RULES[rule.id]||[]).flatMap(name=>(bundle?.facet_evidence?.[name]?.evidence||[]).filter(e=>e.grade==='exclude').map(e=>e.fact_id)));
 const ids=unique([...ancestry.map(e=>e.fact_id),...patterns.flatMap(p=>p.contributions.flatMap(c=>c.fact_ids)),...facts.filter(matched).map(f=>f.id)]).filter(id=>!excluded.has(id));
 const support=ids.map(id=>byId.get(id)).filter(Boolean).map(f=>{const cc=patterns.flatMap(p=>p.contributions).filter(c=>c.fact_ids.includes(f.id));return {...f,posts:unique([...(f.posts||[]),...cc.flatMap(c=>c.post_ids||[])]),experiences:unique([...(f.experiences||[]),...cc.map(c=>c.experience_group)])};});
 const qualifiedIds=unique(patterns.flatMap(p=>p.qualifications||[]));
 const qualifications=facts.filter(f=>(qualifiedIds.includes(f.id)||ids.includes(f.id)&&(qualified(f)||ancestry.some(e=>e.fact_id===f.id)&&['decline','appraisal'].includes(f.kind))));
 const anchored=support.filter(f=>f.anchors?.length),positive=support.filter(f=>!qualifications.some(q=>q.id===f.id));
 return {support,positive,qualifications,facet_links:ancestry,excluded_fact_ids:[...excluded].filter(id=>byId.has(id)),posts:unique(support.flatMap(f=>f.posts)),experiences:unique(support.flatMap(f=>f.experiences)),observation_units:observationUnits(support),patterns:patterns.map(p=>p.name),
 anchored_count:anchored.length,strength:anchored.length?'원문 구간 대조 있음':support.length?'추출 요약 · 원문 의미 검수 필요':'근거 없음',status:anchored.length?'SOURCE_EXCERPT_AND_SUMMARY':'SUMMARY_ONLY'};
}
function menuReferences(catalog,target,decision){
 const eligible=(catalog?.menu_references||[]).filter(p=>p.venue_id===target&&p.role==='MAIN'&&p.sku_id&&p.automatic_choice!==false&&(!decision?.date||(!p.valid_from||p.valid_from<=decision.date)&&(!p.valid_until||p.valid_until>=decision.date))&&(!decision?.slot||!p.service_periods?.length||p.service_periods.includes(decision.slot))&&(!decision?.slot||target!=='THE_BUFFET'||!['breakfast','lunch','dinner'].includes(decision.slot)||p.label.startsWith({breakfast:'조식',lunch:'중식',dinner:'석식'}[decision.slot])));
 const compared=decision?.competitors?.find(c=>c.venue===target)?.sku,match=eligible.find(p=>p.sku_id===compared);return match?[match]:eligible.slice(0,3);
}
function intervention(rule,ev,target,intent,menus){
 const tags=ev.support.flatMap(f=>f.features||[]),has=re=>tags.some(t=>re.test(t)),name=NAMES[target]||'목표 업장',ref=menus[0]?.label;
 const content={
 experience:has(/chef_course/)?['메뉴 탐색과 조리 설명을 묶은 식사 경험',`${name}의 ${ref||'등록 메뉴'}를 바탕으로 맛·조리 방식 비교와 셰프 설명이 가능한 테마 식사를 검토합니다.`]:has(/limited_menu/)?['관심 메뉴를 미리 알리는 예약 안내',`${name}의 실제 제공 메뉴를 먼저 소개하고 관심 메뉴의 제공 시간·예약 가능 여부를 안내합니다. 한정 판매 여부는 별도 확인합니다.`]:['여러 맛을 비교할 수 있는 메뉴 안내',`${name}의 등록 메뉴에서 맛·조리법이 다른 구성을 비교해 새로운 음식 경험을 안내합니다.`],
 food:has(/overordered/)&&intent==='increase'?['양을 늘리기보다 선호 메뉴로 구성 교체',`과한 주문을 후회한 경험을 고려해 ${name}의 기존 주문량을 기준으로 선호 메뉴 교체를 검토합니다.`]:has(/garlic/)?['선호 소스와 재료를 확인하는 맞춤 메뉴 안내',`마늘·소스 관련 경험과 ${name} 메뉴의 재료를 대조해 맞는 선택지를 안내합니다. 재료가 확인되지 않은 메뉴를 추천 메뉴로 확정하지 않습니다.`]:has(/pasta/)?['선호한 파스타·음식 구성을 기준으로 비교',`${name}의 실제 음식 목록에서 선호한 조리법·식재료와 일치하는 항목을 확인하고, 현재 주문과 차이를 설명합니다.`]:['좋아한 음식과 예외를 반영한 메뉴 선택',`${name}의 음식 구성과 개인 취향 기록을 대조해 선호 메뉴와 피할 재료를 안내합니다.`],
 benefit:has(/three_sessions|included_amenities/)?['이미 가진 식음 혜택과 추가 결제 비교',`객실에 포함된 식음 혜택을 먼저 확인하고 ${name} 이용 시 추가로 얻는 구성과 결제액을 안내합니다.`]:['적용 가능한 혜택과 식사 구성을 함께 안내',`${name}의 등록 상품에서 적용 가능한 숙박객·식사 혜택 조건과 최종 결제액을 비교합니다.`],
 space:has(/window.*regret/)?['창가 좌석 가능 여부와 도착 순서 안내',`${name}의 좌석 배정 방식과 가능한 시간대를 먼저 확인합니다. 창가 확보를 보장하지 않고 고객이 원하는 조건으로 일정을 선택하게 합니다.`]:has(/terrace/)?['조용한 좌석·공간 조건을 먼저 제안',`${name}에서 제공 가능한 좌석·공간을 확인하고 프라이빗한 공간 경험과 비교해 안내합니다.`]:['식사 시간대와 공간 경험을 함께 안내',`${name}의 실제 좌석·전망 정보를 식사 시간과 함께 소개합니다. 다른 시설의 전망을 그대로 보장하지 않습니다.`],
 convenience:has(/prebook|openrun|queue/)?['식사 예약과 대기를 줄이는 일정 제안',`${name}의 예약 가능 시간과 실제 방문 일정을 대조해, 대기·이동을 줄일 수 있는 시간을 안내합니다.`]:['남은 일정에 맞춘 식사 이용 안내',`${name} 이동·식사 시간과 현재 남은 일정을 대조해 이용 가능한 시간을 제안합니다.`],
 value:ev.qualifications.length?['할인율보다 구성과 총액을 먼저 비교',`가격·구성에 대한 유보적 평가를 고려해 ${name}의 구성·양·추가 비용을 현재 주문과 비교합니다. 더 높은 소비를 강제하지 않습니다.`]:['지출 우선순위에 맞는 식사 구성 비교',`${name}의 메뉴 구성과 총액을 비교해 이번 식사에서 무엇을 더 얻는지 설명합니다.`]
 }[rule.id];
 const focus={experience:has(/chef_course/)?/chef_course/:has(/limited_menu/)?/limited_menu/:/food_exploration|two_flavors|dessert_trial/,food:has(/overordered/)&&intent==='increase'?/overordered/:has(/garlic/)?/garlic/:has(/pasta/)?/pasta/:rule.features,benefit:has(/three_sessions|included_amenities/)?/three_sessions|included_amenities/:rule.features,space:has(/window.*regret/)?/window.*regret/:has(/terrace/)?/terrace/:rule.features,convenience:has(/prebook|openrun|queue/)?/prebook|openrun|queue/:rule.features,value:rule.features}[rule.id];
 const variant={
 experience:has(/chef_course/)?['chef_comparison','맛과 조리 설명을 결합한 테마 식사']:has(/limited_menu/)?['menu_availability','관심 메뉴의 제공 시간·예약 안내']:['menu_tasting','다양한 맛을 경험하는 테마 식사'],
 food:has(/overordered/)&&intent==='increase'?['portion_swap','주문량을 유지한 선호 메뉴 교체']:has(/garlic/)?['ingredient_match','선호 재료·소스를 확인한 맞춤 메뉴 구성']:has(/pasta/)?['cooking_match','선호 조리법을 반영한 맞춤 메뉴 구성']:['taste_match','개인 음식 취향과 예외를 반영한 메뉴 구성'],
 benefit:has(/three_sessions|included_amenities/)?['included_benefit','기존 숙박 혜택과 연계한 식사 구성']:['eligible_benefit','적용 가능한 혜택을 결합한 식사 구성'],
 space:has(/window.*regret/)?['seat_booking','선호 공간을 반영한 예약·좌석 전략']:has(/terrace/)?['space_match','선호 공간과 실제 좌석 조건을 연결한 식사 안내']:['space_time','시간대와 공간 경험을 결합한 식사 안내'],
 convenience:has(/prebook|openrun|queue/)?['booking_route','방문 일정에 맞춘 예약·동선 개선']:['schedule_fit','남은 일정에 맞춘 식사 시간 조정'],
 value:ev.qualifications.length?['value_conditions','구성·양·추가 비용을 함께 비교하는 식사 제안']:['value_budget','지출 우선순위에 맞춘 식사 가치 제안']
 }[rule.id];
 return {strategy_summary:variant[1],intervention_key:variant[0],title:content[0],content:content[1],intervention_fact_ids:ev.support.filter(f=>(f.features||[]).some(t=>focus.test(t))).map(f=>f.id),specificity:has(/window.*regret|garlic|pasta|limited_menu|chef_course|three_sessions|prebook|overordered/)?2:1};
}
function rankIdea(rule,ev,decision,target,menus,ab){
 const mentioned=ev.support.filter(f=>f.summary.includes(NAMES[target]||'__unknown__'));
 const current=ev.support.filter(f=>(decision?.chosen?.facts||[]).includes(f.id));
 const targetCandidate=decision?.competitors?.find(c=>c.venue===target),causes=(targetCandidate?.causes||[]).filter(c=>c.delta>0&&rule.causes.includes(c.category));
 const interventionInfo=intervention(rule,ev,target,'switch',menus);
 const criteria={target_evidence:mentioned.length?1:0,current_decision_link:current.length?1:0,recorded_target_barrier:causes.length?1:0,specificity:interventionInfo.specificity,positive_support:ev.positive.length?1:0,observation_groups:Math.min(3,ev.observation_units),source_checked:ev.anchored_count?1:0,executable_price_component:ab.length?1:0};
 const vector=Object.values(criteria);
 const reasons=[mentioned.length?'목표 업장을 직접 언급한 경험 연결':menus.length?'목표 업장의 등록 메뉴를 참고':'목표 상품 제공 조건 확인 필요',current.length?'현재 선택의 점수 근거와 연결':'현재 선택의 직접 기여는 미확인',causes.length?'목표 업장과 비교한 불리한 항목에 대응':null,ev.observation_units>1?`같은 글·경험 중복을 합친 ${ev.observation_units}개 관측 묶음`:ev.observation_units===1?'하나의 관측 묶음에 기반':'독립 관측 횟수 미확인',ev.qualifications.length?'관련 유보적 평가를 반영한 조건부 제안':null].filter(Boolean);
 return {policy:'EVIDENCE_RELEVANCE_LEXICOGRAPHIC_V1',criteria,vector,reasons,target_fact_ids:mentioned.map(f=>f.id),decision_fact_ids:current.map(f=>f.id),counter_fact_ids:ev.qualifications.map(f=>f.id),tie_break:'strategy_kind_only_not_customer_id',not_behavior_score:true};
}
function recommend({goal,bundles,catalog,decisions=[],executable=[]}){
 const assumed=goal.basis==='OPERATOR_ASSUMPTION',target=goal.target,customers=unique(goal.customer_ids||decisions.map(r=>r.customer_id)),proposals=[];
 for(const pid of customers){
  const bundle=bundles[pid];if(!bundle)continue;
  const actual=decisions.filter(r=>r.customer_id===pid),anchor=actual[0],menus=menuReferences(catalog,target,anchor),ideas=[];
  for(const rule of RULES){
   const ev=evidence(bundle,rule);if(!ev.support.length)continue;
   ev.strength=ev.anchored_count?'원문 구간 대조 있음':'추출 요약 · 원문 의미 검수 필요';
   const ab=['benefit','value'].includes(rule.id)&&!assumed?executable.filter(c=>c.venue===target&&c.customers.includes(pid)).map(c=>c.sku):[];
   const plan=intervention(rule,ev,target,goal.intent,menus),ranking=rankIdea(rule,ev,assumed?null:anchor,target,menus,ab);
   const preferred=[...ev.support].sort((a,b)=>Number(plan.intervention_fact_ids.includes(b.id))-Number(plan.intervention_fact_ids.includes(a.id))||Number(b.summary.includes(NAMES[target]||'__'))-Number(a.summary.includes(NAMES[target]||'__'))||Number((anchor?.chosen?.facts||[]).includes(b.id))-Number((anchor?.chosen?.facts||[]).includes(a.id))||a.id.localeCompare(b.id));
   ideas.push({id:pid+':'+rule.id,customer_id:pid,kind:rule.id,...plan,ranking,evidence:ev,menus,target,status:'UNTESTED_HYPOTHESIS',basis:assumed?'OPERATOR_ASSUMPTION':actual.length?'OBSERVED_VISIT':'PROFILE_ONLY',assumed_origin:assumed?goal.assumed_origin:null,
    personal_reason:unique(preferred.map(f=>f.summary)).slice(0,2).join(' / '),mechanism:`이 경험을 ${NAMES[target]||'목표 업장'}의 운영 제안과 연결하는 해석입니다.`,
    expected_behavior:goal.intent==='increase'?'현재 업장을 유지하며 구성의 가치를 비교':'목표 업장을 새로운 선택지로 고려',requirements:rule.needs,
    price_basis:'등록 메뉴는 참고 상품입니다. 제공 날짜·끼니·인원·가격 계약 확인이 필요합니다.',ab_options:ab,ab_note:'가격 A/B는 해당 할인 조건만 검증하며 이 운영 가설 전체의 효과를 뜻하지 않습니다.'});
  }
  ideas.sort((a,b)=>{for(let i=0;i<a.ranking.vector.length;i++){const n=b.ranking.vector[i]-a.ranking.vector[i];if(n)return n;}return a.kind.localeCompare(b.kind);});
  const picked=[];for(const idea of ideas){const ids=new Set(idea.evidence.support.map(f=>f.id));if(picked.some(i=>i.evidence.support.filter(f=>ids.has(f.id)).length/Math.max(ids.size,i.evidence.support.length)>.7))continue;picked.push(idea);if(picked.length===3)break;}
  const dimensions=RULES.map(rule=>{const ev=evidence(bundle,rule);return {id:rule.id,label:rule.label,facts:ev.support.length,posts:ev.posts.length,anchored:ev.anchored_count,units:ev.observation_units,evidence:ev,strength:ev.anchored_count?'원문 구간 대조 있음':'요약 근거'};});
  const first=picked[0];
  const mapped=new Set(dimensions.flatMap(x=>x.evidence.support.map(f=>f.id)));
  const audit=facetAudit(bundle);
  const holdReason=!mapped.size&&bundle.facts?.length?(audit.triggers.some(t=>t.excluded)&&audit.suppressed_rep_links.length?'FACET_GRADE_REVIEW':'GOAL_EVIDENCE_REVIEW'):null;
  const evidence_coverage={fact_count:bundle.facts?.length||0,mapped_fact_count:mapped.size,status:mapped.size?'MAPPED':bundle.facts?.length?'UNMAPPED_EVIDENCE':'NO_EVIDENCE',hold_reason:holdReason,
   hold_message:holdReason==='FACET_GRADE_REVIEW'?'후기 근거는 있으나 기존 근거 등급과 이번 목표에 적용할 의미를 다시 확인해야 합니다. 제외·약한 근거를 자동 승인하지 않고 개인화 전략 근거 검수 보류로 남깁니다.':holdReason?'후기 근거는 있으나 이번 목표에 적용할 연결이 확인되지 않았습니다. 개인화 전략 근거 검수 보류로 남기고 관련 경험과 운영 조건을 확인합니다.':null};
  proposals.push({customer_id:pid,semantic_status:bundle.semantic_status||'SEMANTIC_HOLD',evidence_bridge:bundle.facet_evidence&&Object.keys(bundle.facet_evidence).length?'EXISTING_FEATURE_AND_FACET':'EXISTING_PATTERN',dimensions,evidence_coverage,relationship:bundle.relationship,basis:assumed?'OPERATOR_ASSUMPTION':actual.length?'OBSERVED_VISIT':'PROFILE_ONLY',decisions:actual,ideas:picked,ranking_trace:ideas.map(i=>({kind:i.kind,...i.ranking,selected:picked.includes(i)})),limitations:bundle.limitations||[],
   conclusion:first?`‘${first.title}’를 먼저 검토하세요. ${first.ranking.reasons.filter(x=>!x.includes('미확인')).slice(0,2).join(' · ')}이 이 제안을 우선한 이유입니다. ${first.evidence.qualifications.length?'관련 유보적 경험이 있어 제공 조건을 먼저 확인해야 합니다.':'실제 제공 조건과 고객 반응을 확인한 뒤 적용하세요.'}`:'이번 목표에 연결할 개인 근거가 부족합니다. 관련 후기 경험과 제공 가능한 운영 조건을 확인한 뒤 제안할 수 있습니다.'});
 }
 const observed=proposals.filter(p=>p.basis==='OBSERVED_VISIT').length,profileOnly=proposals.filter(p=>p.basis==='PROFILE_ONLY').length;
 return {version:'PERSONAL_STRATEGY_V31',goal,proposals,observed_customers:observed,profile_only_customers:profileOnly,idea_count:proposals.reduce((n,p)=>n+p.ideas.length,0),basis:assumed?'OPERATOR_ASSUMPTION':observed&&profileOnly?'MIXED':observed?'OBSERVED_VISIT':'PROFILE_ONLY',conclusion:proposals.map(p=>p.conclusion).join(' ')||'분석할 고객이 없습니다.'};
}
// Pure customer-level aggregation of existing recommendations. No new preference/effect inference.
function summarizeCohort(model){
 const requested=unique(model?.goal?.customer_ids||model?.proposals?.map(p=>p.customer_id)||[]).sort();
 const byId=new Map();for(const p of model?.proposals||[]){if(!requested.includes(p.customer_id))continue;if(byId.has(p.customer_id)&&JSON.stringify(byId.get(p.customer_id))!==JSON.stringify(p))throw Error('같은 고객의 서로 다른 추천 결과를 함께 집계할 수 없습니다.');byId.set(p.customer_id,p);}
 const categories=RULES.map(r=>({kind:r.id,label:r.label,primary_ids:[],included_ids:[],evidence_ids:[],customers:[],interventions:[]}));
 const catById=new Map(categories.map(c=>[c.kind,c])),interventions=new Map(),customers=[];
 for(const id of requested){
  const p=byId.get(id),ideas=p?.ideas||[],coverage=p?.evidence_coverage||{fact_count:0,status:'NO_EVIDENCE'};
  const basis=p?.basis||'PROFILE_ONLY';
  customers.push({id,basis,has_visit:Boolean(p?.decisions?.length),fact_count:coverage.fact_count,status:p?coverage.status:'MISSING_INPUT',idea_count:ideas.length,primary_kind:ideas[0]?.kind||null,primary_summary:ideas[0]?.strategy_summary||null,proposal:p||null});
  for(const [rank,i] of ideas.entries()){
   const c=catById.get(i.kind);if(!c)throw Error('등록되지 않은 전략 범주를 집계할 수 없습니다.');
   if(rank===0)c.primary_ids.push(id);c.included_ids.push(id);
   const support=[...new Map((i.evidence?.support||[]).map(f=>[f.id,f])).values()];if(support.length)c.evidence_ids.push(id);
   let owner=c.customers.find(x=>x.customer_id===id);if(!owner){owner={customer_id:id,primary:rank===0,evidence:[],idea_ids:[],posts:[],observation_units:0};c.customers.push(owner);}
   owner.primary ||= rank===0;owner.idea_ids=unique([...owner.idea_ids,i.id]);owner.evidence=[...new Map([...owner.evidence,...support].map(f=>[f.id,f])).values()];owner.posts=unique(owner.evidence.flatMap(f=>f.posts||[]));owner.observation_units=observationUnits(owner.evidence);
   const key=JSON.stringify([i.kind,i.target||model.goal.target,i.intervention_key||'UNSPECIFIED']);
   if(!interventions.has(key))interventions.set(key,{key,kind:i.kind,target:i.target||model.goal.target,intervention_key:i.intervention_key||'UNSPECIFIED',summary:i.strategy_summary||null,content:i.content||null,primary_ids:[],included_ids:[],executable_ids:[],requirements:[],idea_ids:[]});
   const v=interventions.get(key);if(rank===0)v.primary_ids.push(id);v.included_ids.push(id);if(i.ab_options?.length)v.executable_ids.push(id);v.requirements=unique([...v.requirements,i.requirements]);v.idea_ids=unique([...v.idea_ids,i.id]);
  }
 }
 const finish=x=>{for(const k of ['primary_ids','included_ids','evidence_ids','executable_ids'])if(x[k])x[k]=unique(x[k]).sort();x.primary_count=x.primary_ids.length;x.included_count=x.included_ids.length;if(x.evidence_ids)x.evidence_count=x.evidence_ids.length;return x;};
 const variants=[...interventions.values()].map(finish).sort((a,b)=>b.primary_count-a.primary_count||b.included_count-a.included_count||a.key.localeCompare(b.key));
 for(const c of categories){finish(c);c.customers.sort((a,b)=>a.customer_id.localeCompare(b.customer_id));c.interventions=variants.filter(v=>v.kind===c.kind);}
 const generated=customers.filter(c=>c.idea_count).length,peak=Math.max(0,...categories.map(c=>c.primary_count));
 const counts={selected:requested.length,with_facts:customers.filter(c=>c.fact_count>0).length,generated,unmapped:customers.filter(c=>c.status==='UNMAPPED_EVIDENCE').length,no_evidence:customers.filter(c=>c.status==='NO_EVIDENCE').length,missing_input:customers.filter(c=>c.status==='MISSING_INPUT').length,actual_visit_linked:customers.filter(c=>c.has_visit).length,assumed:customers.filter(c=>c.basis==='OPERATOR_ASSUMPTION').length,profile_only:customers.filter(c=>c.basis==='PROFILE_ONLY').length,observed:customers.filter(c=>c.basis==='OBSERVED_VISIT').length};
 if(categories.reduce((n,c)=>n+c.primary_count,0)!==generated)throw Error('1순위 추천 고객 수가 추천 생성 고객 수와 다릅니다.');
 const review={generated,semantic_approved:customers.filter(c=>c.proposal?.semantic_status==='SEMANTIC_APPROVED').length,semantic_pending:customers.filter(c=>c.proposal&&c.proposal.semantic_status!=='SEMANTIC_APPROVED').length,ab_status:'NOT_ATTACHED',hypothesis_count:customers.reduce((n,c)=>n+(c.proposal?.ideas||[]).filter(i=>i.status==='UNTESTED_HYPOTHESIS').length,0)};
 return {version:'COHORT_STRATEGY_SUMMARY_V1',goal:model.goal,counts,review,categories,interventions:variants,customers,leaders:peak?categories.filter(c=>c.primary_count===peak).map(c=>c.kind):[],unit:'UNIQUE_CUSTOMER',effect_status:'NOT_TESTED',source_run_id:model.source_run_id||null};
}

function actualDecisions(flow){
 const rows=[],seen=new Set(),days=flow.visit_days?.map(d=>d.flow)||[flow];
 const hm=t=>String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0');
 for(const day of days)for(const [pid,plan] of Object.entries(day.plans||{}))for(const d of plan.m4?.decisions||[]){
  if(d.execution_status!=='EXECUTED')continue;
  const ev=plan.m4.activity_history?.find(e=>e.event_id===d.actual_next_event_id),pk=d.packet;
  if(!ev||!['breakfast','lunch','dinner','snack'].includes(ev.meal_slot)||!pk)continue;
  const key=[pid,pk.packet_sha256,ev.event_id].join('|');if(seen.has(key))continue;seen.add(key);
  const scene=(plan.scenes||[]).find(s=>s.basis?.m4?.event_id===ev.event_id&&s.visit_date===ev.date);
  const paid=scene?(flow.ledger?.receipts?.[pid]?.rows||[]).filter(r=>r.visit_date===ev.date&&r.time===ev.start&&r.act===scene.act&&r.t0===scene.t0&&r.loc===scene.loc):[];
  const c=pk.candidates?.find(c=>c.candidate_id===(d.selected_action?.candidate_id||d.selected_action));
  if(!paid.length&&!['lunch','dinner'].includes(ev.meal_slot))continue;
  rows.push({customer_id:pid,date:ev.date,slot:ev.meal_slot,time:hm(pk.context_factors.time),actual_time:ev.start,packet_sha256:pk.packet_sha256,event_id:ev.event_id,
   status:pk.kind==='QUANTITATIVE'?'ANALYZED':'NO_TERM_DECOMPOSITION',decision_key:`${pid}|${ev.date}|${hm(pk.context_factors.time)}`,observed_context:{...pk.context_factors,profile_feature_marginals:c?.profile_feature_marginals},orders:paid.map(r=>({product:r.product,quantity:r.quantity,unit_price_krw:r.unit_price_krw,paid_krw:r.paid_krw,sku:r.sku_id})),
   chosen:{facts:unique((c?.terms||[]).flatMap(t=>t.fact_ids||[])),terms:c?.terms||[],choice_source:paid.length?'RECORDED_SCENE_ORDER':undefined,venue:paid[0]?.venue_id||paid[0]?.sku_contract?.venue_id||c?.service_contract?.venue_id||ev.venue_id,label:paid.length?paid.map(r=>r.product).join(' + '):c?.candidate_label||ev.action_id,total_krw:paid.length?paid.reduce((n,r)=>n+(r.paid_krw||0),0):null}});
 }
 return rows;
}
function selectCustomers(people,selection){return people.filter(p=>selection.scope==='all'||selection.scope==='type'&&p.type===selection.type||selection.scope==='selected'&&(selection.ids||[]).includes(p.id)||selection.scope==='one'&&p.id===selection.ids?.[0]);}
const api={summarizeCohort,RULES,FACET_RULES,facetAudit,facetLinks,observationUnits,actualDecisions,selectCustomers,decisionId,evidence,menuReferences,recommend};root.HLPersonalStrategy=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
