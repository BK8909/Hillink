const test=require('node:test'),assert=require('node:assert/strict');
const S=require('../static/strategy_story.js');
const ui={e:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),VN:s=>s||'목표 업장',money:n=>n+'원',name:s=>s};
function p(id='customer',kind='experience') {return {customer_id:id,basis:'OBSERVED_VISIT',decisions:[{chosen:{venue:'PIZZA_HILL',label:'Pizza + pasta',total_krw:117000}}],ideas:[{id:id+':'+kind,kind,title:'Menu comparison',intervention_fact_ids:['F'],evidence:{support:[{id:'F',features:[kind==='experience'?'chef_course_consumed':'included_amenities']}],qualifications:[],posts:['post1']},menus:[{sku_id:'SKU'}]}]};}
const goal={target:'THE_BUFFET',intent:'switch'};
test('conclusion joins supported observation, actual order and goal without copying ranking prose',()=>{
 const person=p();person.ideas[0].personal_reason='DO NOT COPY';person.ideas[0].ranking={reasons:['DO NOT COPY']};
 const c=S.synthesize(person,goal,ui);assert.deepEqual(c.claim_fact_ids,['F']);assert.match(c.sentences.join(' '),/셰프 코스.*Pizza \+ pasta.*THE_BUFFET/);assert.doesNotMatch(c.sentences.join(' '),/DO NOT COPY|확률/);
 const html=S.conclusion({goal,proposals:[person]},ui);assert.match(html,/가장 추천하는 운영 전략/);assert.doesNotMatch(html,/button|data-idea-focus|data-current-experiments/);
});
test('counterexample-only evidence never becomes an affirmative preference',()=>{
 const person=p();person.ideas[0].evidence.qualifications=[{id:'F'}];const c=S.synthesize(person,goal,ui);assert.deepEqual(c.claim_fact_ids,[]);assert.match(c.observed,/조건부/);assert.doesNotMatch(c.observed,/셰프 코스/);
});
test('empty evidence cannot manufacture a priority strategy',()=>{
 const person=p();person.ideas[0].evidence.support=[];const c=S.synthesize(person,goal,ui);assert.equal(c.idea_id,null);assert.match(c.sentences.join(' '),/근거가 부족/);
});
test('assumed and profile-only scenarios never assert an executed assumed visit',()=>{
 const assumed=p();assumed.basis='OPERATOR_ASSUMPTION';const c=S.synthesize(assumed,{...goal,assumed_origin:'EXTERNAL_DELIVERY'},ui);assert.match(c.sentences[1],/가정.*실제 선택.*구분/);
 const profile=p();profile.basis='PROFILE_ONLY';profile.decisions=[];assert.match(S.synthesize(profile,goal,ui).sentences[1],/방문 전 제안/);
});
test('mixed customer conclusions retain ownership and different supported mechanisms',()=>{
 const a=p('one'),b=p('two','benefit');b.decisions=[];b.basis='PROFILE_ONLY';const html=S.conclusion({goal,proposals:[a,b]},ui);assert.match(html,/data-conclusion-customer="one"/);assert.match(html,/data-conclusion-customer="two"/);assert.match(html,/셰프 코스/);assert.match(html,/객실에 포함/);
});
test('zero inflow, other changes and successful inflow remain separate from untested hypotheses',()=>{
 for(const [count,changed,pattern] of [[0,0,/선택 전환이 발생하지/],[0,2,/신규 유입은 없으며/],[1,1,/이동한 고객이 관찰/]]){
  const html=S.conclusion({goal,proposals:[p()]},ui,{pct:20,candidate:{kind:'discount'},metrics:{goal_customers:Array(count).fill('customer'),changed_customers:changed,cohort_target_delta:0,paid_delta:84000}});assert.match(html,pattern);assert.match(html,/운영 가설의 효과는 아직 검증하지/);assert.match(html,/84000원/);
 }
});
test('existing but unclassified facts are a mapping gap, not missing customer evidence',()=>{
 const P=require('../static/strategy_personal.js');const model=P.recommend({goal:{...goal,customer_ids:['u']},bundles:{u:{facts:[{id:'owned',summary:'Recorded customer observation',features:[]}],patterns:{}}},catalog:{}});
 assert.equal(model.idea_count,0);assert.equal(model.proposals[0].evidence_coverage.status,'UNMAPPED_EVIDENCE');
 const html=S.conclusion(model,ui);assert.match(html,/개인 후기 근거 1개/);assert.match(html,/개인화 전략 근거 검수 보류/);assert.doesNotMatch(html,/후기 근거가 부족/);
});
