const test=require('node:test'),assert=require('node:assert/strict');
const D=require('../static/reason_dialogue.js');
test('conversational action preserves the actual choice and adds no motivation',()=>{
  const raw=['객실에서 쉬다가 두 사람이 명월관에서 저녁을 먹습니다.','후기 기록으로 보면 음식 경험을 중시하는 고객입니다.'];
  const copy=structuredClone(raw),p=D.build(raw,{party:2,verified:true});
  assert.equal(p[0].text,'객실에서 쉬다가 함께 명월관에서 저녁을 먹어요.');
  assert.equal(p[1].text,'제 기록을 보면 음식 경험을 중시하는 편이에요.');assert.equal(p[1].voice,'persona');assert.deepEqual(raw,copy);
});
test('unverified reasons and quoted records are not turned into personal testimony',()=>{
  const quote='"공간이 좋았다"라는 기록이 있는 고객입니다.';
  assert.equal(D.build([quote],{verified:true})[0].text,quote);
  assert.equal(D.build(['객실에서 쉽니다.'])[0].voice,'record');
  assert.equal(D.build(['객실에서 쉽니다.'],{verified:true})[0].text,'객실에서 쉬어요.');
});
test('missing evidence stays a neutral record and technical terms stay in precision',()=>{
  assert.equal(D.build([])[0].voice,'record');
  assert.doesNotMatch(D.build(['LLM 판단 확률 0.7, C01_MENU 선택.'])[0].text,/LLM|0.7|C01_MENU/);
});
test('separate pages preserve the full adopted explanation without new model claims',()=>{
  const src=['객실에서 쉬다가 명월관에 자리를 잡고 양념갈비로 저녁을 합니다.','전날에 이미 피자힐에서 봉골레 파스타를 먹었던 터라, 오늘은 다른 곳으로 정했습니다.','워커힐의 가든 BBQ에서는 음식뿐 아니라 공연·조망을 포함한 경험을 긍정적으로 평가했다고 했습니다.'];
  const p=D.build(src,{verified:true});assert.equal(p.length,3);
  assert.match(p[0].text,/명월관.*양념갈비/);assert.equal(p[1].text,src[1].replace('정했습니다.','정했어요.'));assert.equal(p[2].text,src[2]);
  assert.doesNotMatch(p.map(x=>x.text).join(' '),/LLM|맛있을|기대|행복/);
});
test('scene identity separates customers, runs, dates and repeated activities',()=>{
  const k={run:'r',customer:'A03',scene:2,date:'2026-10-24',start:1020,action:'room_rest'};
  for(const [key,value] of Object.entries({run:'r2',customer:'A05',scene:3,date:'2026-10-25',start:1030,action:'pool'}))assert.notEqual(D.keyOf(k),D.keyOf({...k,[key]:value}));
});
test('long legacy paragraphs paginate without splitting a quoted observation',()=>{
  const raw=['지금은 객실에서 쉽니다. 다음 일정까지 시간이 남았습니다. 창밖을 봅니다. 이동은 아직 시작하지 않았습니다. 기록된 일정은 유지됩니다.'];
  const pages=D.build(raw);assert.equal(pages.length,3);assert.equal(pages.map(p=>p.text).join(' '),raw[0]);
  const quote='후기에 "공간이 좋았다. 다시 가고 싶다."라는 기록이 있습니다.';
  assert.equal(D.build([quote],{verified:true}).length,1);assert.equal(D.build([quote],{verified:true})[0].text,quote);
});

test('movement uses destination purpose codes without venue names or invented judgment',()=>{
  const fixtures=[
    [{b:'VISTA_ROOM'},{act:'unpack'},'객실로 이동 중'],
    [{b:'GRAND_LOBBY'},{act:'wait'},'로비로 이동 중'],
    [{b:'VISTA_LOBBY'},{act:'checkin'},'체크인하러 이동 중'],
    [{b:'THE_BUFFET'},{act:'breakfast'},'아침 먹으러 이동 중'],
    [{b:'LE_PASSAGE'},{act:'lunch_cafe'},'점심 먹으러 이동 중'],
    [{b:'MYONGWOLGWAN'},{act:'turn_dinner'},'저녁 먹으러 이동 중'],
    [{b:'FOREST'},{act:'turn_event',label:'Savoring Summer Night'},'행사 참가하러 이동 중'],
    [{b:'VISTA_POOL'},{act:'pool'},'수영하러 이동 중'],
    [{b:'WELLNESS_SAUNA'},{act:'sauna'},'사우나로 이동 중'],
    [{b:'SKYARD'},{act:'footbath'},'족욕하러 이동 중'],
    [{b:'FOREST'},{act:'forest_walk'},'산책하러 이동 중'],
    [{b:'HOTEL_GATE'},{act:'leave'},'집으로 돌아가는 중'],
    [{b:'LE_PASSAGE'},{label:'르파사쥬도 할 수 있었다'},'다음 장소로 이동 중'],
    [{b:'VISTA_ROOM'},{act:'turn_event'},'객실로 이동 중']
  ];
  const original=structuredClone(fixtures);
  for(const [scene,dest,text] of fixtures)assert.equal(D.movementMessage(scene,dest),text);
  assert.deepEqual(fixtures,original);assert.equal(D.movementMessage(), '다음 장소로 이동 중');
});
