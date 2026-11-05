const test=require('node:test'),assert=require('node:assert/strict');
const S=require('../static/reason_story.js');
function input(act='theatre',label='입장권 · 성인'){
 const f={plans:{P:{scenes:[{act,label,t0:900,t1:960,visit_day:1,basis:{m4:{decision_packet_ids:['p']}}}],m4:{decisions:[{packet:{packet_sha256:'p',context_factors:{time:900},candidates:[{candidate_id:act,world_allowed:true,final_score:1},{candidate_id:'HC_HC-ORDER-abc123',world_allowed:true,final_score:.99}]},selected_action:act,sampling:{mode:'weighted',probabilities:{[act]:.4,'HC_HC-ORDER-abc123':.6}}}]}}}};
 return S.input(f,'P',0,{visit:{party_size:2}});
}
test('admission price label is not narrated as the activity',()=>{const x=input(),s=S.compose(x);assert.match(s.sentences[0],/빛의 시어터/);assert.doesNotMatch(s.sentences.join(' '),/입장권|HC_|할 수 있는/);assert.deepEqual(S.qa(x,s),[]);});
test('included payment status stays outside the activity sentence',()=>{const x=input('footbath','족욕 객실포함'),s=S.compose(x);assert.match(s.sentences[0],/족욕/);assert.doesNotMatch(s.sentences.join(' '),/객실포함/);assert.deepEqual(S.qa(x,s),[]);});
test('a summary is never presented as a verbatim customer quotation',()=>{const x=input('theatre','빛의 시어터 관람');x.sampling=null;x.facts=[{id:'P-F1',gist:'빛의 시어터를 관람했다.',roles:['direct'],contrib:true,value:1,factor:'공간 경험'}];const s=S.compose(x);assert.doesNotMatch(s.sentences.join(' '),/"|이렇게 적었|낯설지/);assert.match(s.sentences.join(' '),/요약/);});
test('unrecorded baggage storage is not inferred from checkout',()=>{const x=input();x.prev={act:'checkout',label:'체크아웃',t0:890};assert.doesNotMatch(S.compose(x).sentences.join(' '),/짐을 맡/);});

test('a near-tie trigger cannot turn an unrelated low-ranked activity into a close alternative',()=>{const x=input();x.review={triggers:['NEAR_TIE']};x.cands[0].score=4;x.cands.push({id:'ROOM_REST',label:'객실 휴식',score:.4,allowed:true});const s=S.compose(x);assert.doesNotMatch(s.sentences.join(' '),/휴식.*견준|휴식.*비교됐/);});

test('a common food baseline is not narrated as a personal review preference',()=>{const f={plans:{P:{scenes:[{act:'turn_dinner',label:'피자힐 마르게리타',t0:1080,t1:1170,visit_day:1,basis:{m4:{decision_packet_ids:['p']}}}],m4:{decisions:[{packet:{packet_sha256:'p',context_factors:{time:1080},candidates:[{candidate_id:'meal',candidate_label:'피자힐 마르게리타',world_allowed:true,final_score:3,terms:[{factor:'음식 경험',kind:'profile_and_offer',value:1.2,fact_ids:[]}]}]},selected_action:'meal'}]}}}};const x=S.input(f,'P',0),s=S.compose(x);assert.deepEqual(x.traitTerms,[]);assert.doesNotMatch(s.sentences.join(' '),/후기 전반|후기 기록으로|좋아하는 고객/);});
