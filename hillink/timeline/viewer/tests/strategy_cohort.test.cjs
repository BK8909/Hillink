const test=require('node:test'),assert=require('node:assert/strict');
const P=require('../static/strategy_personal.js'),S=require('../static/strategy_story.js');
const ui={e:String,VN:String,name:String,money:String};
function idea(kind,post='p'){return {id:kind,kind,target:'THE_BUFFET',strategy_summary:kind+' summary',intervention_key:kind+'_operation',content:kind+' existing operation',requirements:'contract',ranking:{reasons:[],criteria:{}},menus:[],ab_options:[],evidence:{support:[{id:'F',summary:'Owned observation',posts:[post],features:['included_amenities']}],posts:[post],qualifications:[]}};}
function person(id,kinds=[],basis='PROFILE_ONLY'){return {customer_id:id,basis,ideas:kinds.map(k=>idea(k)),decisions:basis==='OBSERVED_VISIT'?[{chosen:{venue:'IRD'}}]:[],evidence_coverage:{fact_count:3,status:kinds.length?'MAPPED':'UNMAPPED_EVIDENCE'},dimensions:[]};}
const model=ps=>({goal:{target:'THE_BUFFET',intent:'switch',customer_ids:ps.map(p=>p.customer_id)},proposals:ps});
test('unique customers are votes; category top counts equal supported population',()=>{
 const a=person('a',['benefit','benefit','space']),b=person('b',['space','benefit']),c=person('c');const m=model([a,b,c]);m.proposals.push(a);m.goal.customer_ids.push('a');const s=P.summarizeCohort(m);
 assert.equal(s.counts.selected,3);assert.equal(s.counts.generated,2);assert.equal(s.counts.unmapped,1);assert.equal(s.categories.reduce((n,c)=>n+c.primary_count,0),2);
 const benefit=s.categories.find(c=>c.kind==='benefit');assert.equal(benefit.included_count,2);assert.equal(benefit.evidence_count,2);assert.equal(benefit.primary_count,1);assert.deepEqual(s.leaders,['benefit','space']);
 assert.equal(benefit.customers[0].evidence.length,1);assert.equal(benefit.customers[0].observation_units,1);
});
test('many facts from one article do not multiply customer or observation votes',()=>{
 const p=person('a',['food']);p.ideas[0].evidence.support=Array.from({length:10},(_,i)=>({id:'F'+i,summary:'Fact '+i,posts:['same-post']}));const s=P.summarizeCohort(model([p]));const c=s.categories.find(c=>c.kind==='food');assert.equal(c.included_count,1);assert.equal(c.customers[0].observation_units,1);assert.equal(c.customers[0].evidence.length,10);
});
test('same category preserves distinct actual interventions and target',()=>{
 const a=person('a',['benefit']),b=person('b',['benefit']);b.ideas[0].intervention_key='other_contract';const s=P.summarizeCohort(model([a,b]));assert.equal(s.interventions.length,2);assert(s.interventions.every(v=>v.primary_count===1));assert.equal(s.categories.find(c=>c.kind==='benefit').primary_count,2);
});
test('aggregation is deterministic under customer input order and does not mutate recommendations',()=>{
 const a=person('a',['experience','food']),b=person('b',['benefit']);const m=model([a,b]),saved=JSON.stringify(m),s=P.summarizeCohort(m),r=P.summarizeCohort({...m,proposals:[b,a]});assert.deepEqual(r,s);assert.equal(JSON.stringify(m),saved);
 assert.throws(()=>P.summarizeCohort(model([a,{...a,ideas:[]} ])),/서로 다른 추천/);
});
test('support gaps, missing input, actual visits and assumptions have separate denominators',()=>{
 const ps=[person('a',['food'],'OBSERVED_VISIT'),person('b',[],'OPERATOR_ASSUMPTION'),person('c')];const m=model(ps);m.goal.customer_ids.push('missing');const s=P.summarizeCohort(m);assert.equal(s.counts.selected,4);assert.equal(s.counts.with_facts,3);assert.equal(s.counts.actual_visit_linked,1);assert.equal(s.counts.assumed,1);assert.equal(s.counts.profile_only,2);assert.equal(s.counts.missing_input,1);assert.equal(s.counts.unmapped,2);assert.equal(s.effect_status,'NOT_TESTED');
});
test('zero, one, ties and unsupported majority never become effect claims',()=>{
 const zero=S.groupConclusion(P.summarizeCohort(model([person('a'),person('b')])),ui);assert.match(zero.headline,/선정할 수 없습니다/);
 const one=S.groupConclusion(P.summarizeCohort(model([person('a',['food']),person('b')])),ui);assert.match(one.sentences.join(' '),/1명이므로 집단적 경향으로 일반화하지/);
 const tie=S.groupConclusion(P.summarizeCohort(model([person('a',['food']),person('b',['space'])])),ui);assert.match(tie.headline,/공동/);assert.equal(tie.leaders.length,2);assert.match(tie.effect,/미검증/);
 const ps=Array.from({length:28},(_,i)=>person('p'+i,i<9?['benefit']:[]));const s=P.summarizeCohort(model(ps)),c=S.groupConclusion(s,ui);assert.match(c.sentences.join(' '),/추천 생성 9명 중 9명.*전체 분석 대상 28명/);assert.match(c.sentences.join(' '),/19명의 근거 연결이 미지원/);
});
test('group UI starts with count summary and folds all customer details',()=>{
 const m=model([person('a',['food']),person('b',['benefit'])]),s=P.summarizeCohort(m),html=S.renderCohort(m,s,ui);assert.match(html,/data-cohort-summary/);assert.equal((html.match(/data-cohort-customer=/g)||[]).length,2);assert.doesNotMatch(html,/data-conclusion-customer=|<details[^>]* open/);assert.match(html,/전체 고객 분석에서 가장 많이 추천된 운영 전략/);assert.match(html,/집단 A\/B 미실행/);
});
test('summary is separate from recommendation title and linked to the chosen intervention',()=>{
 const m=P.recommend({goal:{target:'THE_BUFFET',intent:'switch',customer_ids:['a']},bundles:{a:{facts:[{id:'f',summary:'Observed cuisine exploration',features:['food_exploration'],posts:['p']}]}},catalog:{}});const p=m.proposals[0],s=S.synthesize(p,m.goal,ui);assert(p.ideas[0].strategy_summary);assert.notEqual(s.emphasis,p.ideas[0].title);assert.equal(s.emphasis,p.ideas[0].strategy_summary);assert.equal(p.ideas[0].intervention_key,'menu_tasting');
});
test('group evidence retains each owner and never promotes qualified evidence to shared preference',()=>{
 const a=person('a',['benefit']),b=person('b',['benefit']);a.ideas[0].evidence.qualifications=[...a.ideas[0].evidence.support];
 const summary=P.summarizeCohort(model([a,b])),c=S.groupConclusion(summary,ui),patterns=c.leaders[0].observed_patterns;
 assert.equal(patterns.length,1);assert.deepEqual(patterns[0].customer_ids,['b']);assert.deepEqual(patterns[0].fact_references,[{customer_id:'b',fact_ids:['F']}]);assert.equal(c.leaders[0].count,2);
});
