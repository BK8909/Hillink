/* Explicit laboratory visit inputs. Profile context never manufactures behavior. */
(function(root){'use strict';
const SANTA='SANTA_KIDS_VILLAGE_2026';
function events(registry){return registry.events.filter(e=>e.event_card_id!=='SANTA_KIDS_VILLAGE_2025');}
function request(lab,ids,registry,rooms,cap){
 const event=events(registry).find(e=>e.id===lab.event);if(!event?.enabled)throw Error('선택 행사는 실행 준비 중입니다.');
 if(!ids.length)throw Error('방문할 고객을 선택하세요.');
 if(event.source_date_range&&(lab.date<event.source_date_range[0]||lab.date>event.source_date_range[1]))throw Error('방문 시작일을 행사 운영 기간 안에서 선택하세요.');
 if(event.weekdays&&!event.weekdays.includes((new Date(lab.date+'T12:00:00Z').getUTCDay()+6)%7))throw Error('해당 요일에는 등록된 행사가 운영되지 않습니다.');
 const r={personas:[...ids],start_date:lab.date,duration:lab.duration,seed:Number(lab.seed),include_ledger:true,behavior_engine:'m4_c01',catalog_policy:cap.catalog_policy||'C01_HOTEL_CATALOG_V1',event_mode:event.event?'wine':'none',environment:{weather:lab.weather,arrival_time:lab.arrival},scenario:{event_card_id:event.event_card_id||'NONE',...structuredClone(event.scenario_defaults||{})}};
 if(!Number.isInteger(r.seed)||r.seed<0)throw Error('시드를 0 이상의 정수로 입력하세요.');
 const p=rooms.packages.find(p=>p.id===lab.package&&p.event_card_id===SANTA);
 if(event.event_card_id===SANTA&&lab.package&&!p)throw Error('2026 산타 패키지를 다시 선택하세요.');
 if(event.event_card_id===SANTA&&p){
  if(lab.duration==='day_visit')throw Error('객실 패키지는 1박 이상의 방문에만 적용합니다.');
  if(!lab.partyAssumption)throw Error('성인 2인·어린이 1인 동행을 이번 방문 조건으로 명시적으로 선택하세요.');
  r.visit_conditions={};r.scenario.entitlements={};r.scenario.assumptions=r.scenario.assumptions||{};
  for(const pid of ids){r.visit_conditions[pid]={building:p.buildings[0],party_size:3,party_composition:{adult_count:2,children:[{}]}};r.scenario.entitlements[pid]={selected_package:true,included_people:3,package_id:p.id};
   if(lab.bookingDate)r.scenario.entitlements[pid].booking_date=lab.bookingDate;
   if(lab.earlybird)r.scenario.entitlements[pid].earlybird=true;
   if(lab.session){r.scenario.assumptions.booked_sessions=r.scenario.assumptions.booked_sessions||{};r.scenario.assumptions.booked_sessions[pid]={date:lab.date,start:lab.session};}
  }
  r.scenario.assumptions.santa_before_checkin='not_allowed';
 }
 if(event.virtual_package_included_people){
  if(!lab.partyAssumption||lab.duration==='day_visit')throw Error('리버파크 패키지는 숙박·패키지 인원 가정에 동의한 후 실행하세요.');
  r.visit_conditions={};r.scenario.entitlements={};
  for(const pid of ids){r.visit_conditions[pid]={building:event.default_building,party_size:event.virtual_package_included_people};r.scenario.entitlements[pid]={selected_package:true,included_people:event.virtual_package_included_people};}
 }
 return r;
}
function summary(lab,source,registry){
 if(lab.mode==='EXISTING')return source?`보존된 가상 방문 · ${source.request.start_date} · ${source.flow.visit?.scenario_snapshot?.sources?.[0]?.record?.['행사 · 상품명']||'행사 없음'} · 원래 요청 조건 유지`:'연결할 기존 방문이 없습니다.';
 const event=events(registry).find(e=>e.id===lab.event);
 return `${event?.label||'행사 없음'} · ${lab.date} · ${lab.duration.replace('stay_','')==='day_visit'?'당일':lab.duration.replace('stay_','')+'박'} · ${lab.mode==='SIMULATE'?'새 M4 가상 방문':'프로필 기반 가설 · 방문 미실행'}${lab.basis==='OPERATOR_ASSUMPTION'?' · 출발 행동은 운영자 가정':''}${lab.package?' · 패키지 선택 가정':''}${lab.session?' · '+lab.session+' 예약 가정':''}`;
}
const api={events,request,summary,SANTA};if(typeof module!=='undefined')module.exports=api;root.HLStrategyEventLab=api;
})(typeof window!=='undefined'?window:globalThis);
