// Profile → supported visit conditions → one continuous visit execution.
const SIT = { pid: null, options: null, forms: new Map(), busy: false, error: null, notice: null, entered: false, token: 0 };
// Native change/blur must finish before replacing the focused input subtree.
let situationRenderFrame = null;
function situationQueueRender() {
  SIT.draftPid=SIT.pid;
  if(situationRenderFrame!==null)return;
  situationRenderFrame=requestAnimationFrame(()=>{
    situationRenderFrame=null;
    if(LIBV.situation===SIT.pid)situationRender();
  });
}
function situationForm(pid) {
  if (!SIT.forms.has(pid)) SIT.forms.set(pid, { event: "none", duration: "day_visit", seed: 0, package_id: "", catalogEnabled: true, judgment_mode: 'replay' });
  return SIT.forms.get(pid);
}
// Optional, per-visit draft only. No persona facts, default ages or persistent profile writes.
function situationDetailDraft(form,pid) {
  if(form.detailDraft)return form.detailDraft;
  const input=form.visit_conditions&&form.visit_conditions[pid]||{},party=input.party_composition,orders=structuredClone(input.orders||[]),coffee=orders.find(o=>o.venue_id==='THE_PAVILION'&&o.service_period==='snack'&&o.items.length===1&&o.items[0].source_line===204);
  return form.detailDraft={partyText:input.party_size==null?'':String(input.party_size),composition:!!party,adultText:party?String(party.adult_count):'',children:party?structuredClone(party.children):[],originalOrders:orders,cafeDate:coffee?coffee.date:'',cafeText:coffee?String(coffee.items[0].quantity):''};
}
function situationDates(form) {
  const nights=({day_visit:0,stay_1:1,stay_2:2,stay_3:3})[form.duration];return Array.from({length:nights+1},(_,i)=>{const date=new Date((form.start_date||(SIT.options&&SIT.options.events.find(x=>x.id===form.event)||{}).start_date||'2026-10-24')+'T00:00:00Z');date.setUTCDate(date.getUTCDate()+i);return date.toISOString().slice(0,10);});
}
function situationVisitDetails(pid,form) {
  const selected=structuredClone(form.visit_conditions&&form.visit_conditions[pid]||{}),draft=situationDetailDraft(form,pid),integer=(s,min,max)=>s!==''&&Number.isInteger(Number(s))&&Number(s)>=min&&Number(s)<=max;
  delete selected.party_composition;delete selected.orders;delete selected.party_size;
  if(draft.partyText!==''){if(!integer(draft.partyText,1,8))throw new Error('방문 인원은 1~8명으로 입력해 주세요.');selected.party_size=Number(draft.partyText);}
  if(form.c01Enabled){
    if(draft.composition){if(!integer(draft.adultText,0,8)||selected.party_size==null)throw new Error('구성을 명시하려면 방문 인원과 성인 수를 입력해 주세요.');if(Number(draft.adultText)+draft.children.length!==selected.party_size)throw new Error('성인 수와 아동 수의 합계가 방문 인원과 같아야 합니다.');for(const child of draft.children)if(child.age_months!=null&&(!Number.isInteger(child.age_months)||child.age_months<0||child.age_months>215))throw new Error('아동 연령은 0~215개월 또는 UNKNOWN으로 입력해 주세요.');selected.party_composition={adult_count:Number(draft.adultText),children:structuredClone(draft.children)};}
    const isCoffee=o=>o.venue_id==='THE_PAVILION'&&o.service_period==='snack'&&o.items.length===1&&o.items[0].source_line===204;
    let coffee=null;if(draft.cafeText!==''||draft.cafeDate!==''){if(!integer(draft.cafeText,1,32)||!situationDates(form).includes(draft.cafeDate))throw new Error('카페 주문은 방문 날짜와 1~32잔 수량을 함께 입력해 주세요.');coffee={date:draft.cafeDate,venue_id:'THE_PAVILION',service_period:'snack',items:[{source_line:204,quantity:Number(draft.cafeText)}]};}
    const had=draft.originalOrders.some(isCoffee),orders=draft.originalOrders.flatMap(o=>isCoffee(o)?coffee?[coffee]:[]:[structuredClone(o)]);if(coffee&&!had)orders.push(coffee);if(orders.some(o=>o.venue_id==='THE_BUFFET')&&!selected.party_composition)throw new Error('기존 뷔페 주문에는 성인·아동 구성 입력이 필요합니다. 구성을 유지하거나 상세 입력을 초기화해 주세요.');if(orders.length)selected.orders=orders;
  }
  return selected;
}
function situationDetailsHTML(pid,form) {
  const d=situationDetailDraft(form,pid),other=d.originalOrders.filter(o=>!(o.venue_id==='THE_PAVILION'&&o.service_period==='snack'&&o.items.length===1&&o.items[0].source_line===204)).length;
  return `<details class="st-visit-details"${form.detailsOpen?' open':''}><summary>인원·주문 상세 설정 <small>선택 사항 · 이번 방문의 가상 설정</small></summary><label class="st-detail-check"><input type="checkbox" id="sitC01"${form.c01Enabled?' checked':''}>이번 방문의 상세 인원·주문 입력 사용</label><p class="st-detail-note">기본 방문에는 상세 입력을 강제하지 않습니다. 미지정 구성·연령·주문량은 UNKNOWN입니다.</p>${form.c01Enabled?`<div class="st-detail-grid"><label>방문 인원 (직접 설정)<input class="cf-input" id="sitPartySize" type="number" min="1" max="8" step="1" placeholder="기존 방문 조건 사용" value="${esc(d.partyText)}"></label><label class="st-detail-check"><input type="checkbox" id="sitComposition"${d.composition?' checked':''}>성인·아동 구성을 명시</label></div>${d.composition?`<div class="st-detail-grid"><label>성인 수<input class="cf-input" id="sitAdultCount" type="number" min="0" max="8" placeholder="UNKNOWN" value="${esc(d.adultText)}"></label><button type="button" class="cf-btn cf-sm" id="sitAddChild">아동 추가</button></div><div class="st-child-list">${d.children.map((ch,i)=>`<div class="st-child-row"><b>아동 ${i+1}</b><label>연령 (개월)<input class="cf-input" data-sit-age="${i}" type="number" min="0" max="215" placeholder="UNKNOWN" value="${ch.age_months==null?'':ch.age_months}"></label><label>취학 상태<select class="cf-input" data-sit-school="${i}">${[['','UNKNOWN'],['preschool','미취학'],['elementary','초등'],['secondary','중·고등']].map(([v,t])=>`<option value="${v}"${(ch.school_stage||'')===v?' selected':''}>${t}</option>`).join('')}</select></label><button type="button" class="cf-link" data-sit-remove-child="${i}">삭제</button></div>`).join('')}</div>`:''}<h3>카페 주문 수량 <small>선택 사항</small></h3><p class="st-detail-note">파빌리온 아메리카노 HOT · 기존 메뉴 자료를 사용한 가상 주문</p><div class="st-detail-grid"><label>이용 날짜<select class="cf-input" id="sitCafeDate"><option value="">UNKNOWN</option>${situationDates(form).map(date=>`<option value="${date}"${d.cafeDate===date?' selected':''}>${date}</option>`).join('')}</select></label><label>아메리카노 HOT (잔)<input class="cf-input" id="sitCafeQuantity" type="number" min="1" max="32" step="1" placeholder="UNKNOWN" value="${esc(d.cafeText)}"></label></div>${other?`<p class="st-detail-note">기존 다른 업장 주문 ${other}건은 그대로 보존합니다.</p>`:''}`:''}<button type="button" class="cf-link" id="sitClearDetails">상세 입력 초기화</button>${form.resolvedSnapshot?`<details class="st-resolved"><summary>직전 실행의 실제 적용값</summary><p class="st-detail-note">아래는 직전 run의 값이며, 수정한 설정은 다음 실행에 적용됩니다.</p><pre>${esc(JSON.stringify(form.resolvedSnapshot,null,2))}</pre></details>`:''}</details>`;
}
function situationDetailsWire(root,pid,form) {
  const d=situationDetailDraft(form,pid),render=()=>{form.detailsOpen=true;situationQueueRender();},find=id=>root.querySelector('#'+id);
  const box=root.querySelector('.st-visit-details');box.ontoggle=()=>{if(box.isConnected)form.detailsOpen=box.open;};
  find('sitC01').onchange=e=>{form.c01Enabled=e.target.checked;render();};
  if(find('sitPartySize'))find('sitPartySize').onchange=e=>{d.partyText=e.target.value;render();};
  if(find('sitComposition'))find('sitComposition').onchange=e=>{d.composition=e.target.checked;render();};
  if(find('sitAdultCount'))find('sitAdultCount').onchange=e=>{d.adultText=e.target.value;render();};
  if(find('sitAddChild'))find('sitAddChild').onclick=()=>{if(d.children.length<8){d.children.push({age_months:null,school_stage:null});render();}};
  root.querySelectorAll('[data-sit-age]').forEach(e=>e.onchange=()=>{d.children[+e.dataset.sitAge].age_months=e.value===''?null:Number(e.value);render();});
  root.querySelectorAll('[data-sit-school]').forEach(e=>e.onchange=()=>{d.children[+e.dataset.sitSchool].school_stage=e.value||null;render();});
  root.querySelectorAll('[data-sit-remove-child]').forEach(e=>e.onclick=()=>{d.children.splice(+e.dataset.sitRemoveChild,1);render();});
  if(find('sitCafeDate'))find('sitCafeDate').onchange=e=>{d.cafeDate=e.target.value;render();};
  if(find('sitCafeQuantity'))find('sitCafeQuantity').onchange=e=>{d.cafeText=e.target.value;render();};
  find('sitClearDetails').onclick=()=>{form.c01Enabled=false;form.detailDraft={partyText:'',composition:false,adultText:'',children:[],originalOrders:[],cafeDate:'',cafeText:''};if(form.visit_conditions&&form.visit_conditions[pid])for(const k of ['party_size','party_composition','orders'])delete form.visit_conditions[pid][k];render();};
}
function situationRequest(pid, form, options) {
  const selected = options.events.find(x => x.id === form.event && x.enabled === true);
  if (!selected) throw new Error("현재 실행 가능한 행사를 선택해 주세요.");
  if (!["day_visit", "stay_1", "stay_2", "stay_3"].includes(form.duration)) throw new Error("방문 기간을 선택해 주세요.");
  const request = { personas: [pid], duration: form.duration, event_mode: selected.event === true ? "wine" : "none",
    seed: Number.isInteger(form.seed) ? form.seed : 0, start_date: form.start_date || selected.start_date || "2026-10-24", include_ledger: true };
  if(form.weather||form.arrival_time)request.environment={...(form.weather?{weather:form.weather}:{}),...(form.arrival_time?{arrival_time:form.arrival_time}:{})};
  const details=situationVisitDetails(pid,form);
  if (Object.keys(details).length) {
    if (form.duration === "day_visit") { details.building=null;details.club=false;delete details.breakfast_plan; }
    if (details.building==null)delete details.building;
    request.visit_conditions={[pid]:details};
  }
  if(form.c01Enabled)request.behavior_engine='m4_c01';
  if(form.catalogEnabled){request.behavior_engine='m4_c01';request.catalog_policy='C01_HOTEL_CATALOG_V1';}
  if(form.simulation_mode)request.simulation_mode=form.simulation_mode;
  if(form.package_id&&SIT.roomOptions&&!situationRoomPackages(form,pid,SIT.roomOptions,selected).some(x=>x.id===form.package_id))throw new Error('현재 날짜·건물·숙박 조건에 적용할 수 없는 객실 패키지입니다.');
  const chosenRoom=SIT.roomOptions?.packages.find(x=>x.id===form.package_id);
  const catalogRoom=chosenRoom?.adapter==='catalog_room';
  const santa2026 = selected.event_card_id === "SANTA_KIDS_VILLAGE_2026";
  const santaPackage = form.package_id === "SANTA_PKG_2025" || (santa2026 && chosenRoom?.adapter === "event_entitlement");
  if(catalogRoom){request.behavior_engine='m4_c01';request.catalog_policy=chosenRoom.catalog_policy;request.catalog_options={room_products:{[pid]:chosenRoom.sku_id}};}
  if (form.package_id && !santaPackage && !catalogRoom) request.package_id = form.package_id;
  if (santaPackage && (!["SANTA_KIDS_VILLAGE_2025","SANTA_KIDS_VILLAGE_2026"].includes(selected.event_card_id) || form.duration === "day_visit")) throw new Error("산타 객실 패키지는 해당 연도 산타 행사 숙박 일정에서만 선택할 수 있습니다.");
  if(selected.event_card_id){
    if(form.package_id && !santaPackage && !catalogRoom)throw new Error('행사 카드 조건과 다른 객실 패키지는 동시에 선택할 수 없습니다.');
    request.behavior_engine='m4_c01';request.scenario={event_card_id:selected.event_card_id,...structuredClone(form.scenarioOverrides||selected.scenario_defaults||{})};
    if(selected.default_building){request.visit_conditions=request.visit_conditions||{};request.visit_conditions[pid]={...(request.visit_conditions[pid]||{}),building:form.duration==='day_visit'?null:((request.visit_conditions[pid]||{}).building||selected.default_building)};}
    if(selected.virtual_package_included_people)request.scenario.entitlements={[pid]:{selected_package:true,included_people:selected.virtual_package_included_people}};
    if(santaPackage){
      // Explicit package choice only: base composition adult 2 · child 1 unless the operator set the party; Grand/Vista only.
      request.scenario.entitlements={[pid]:{selected_package:true,included_people:3,...(santa2026?{package_id:form.package_id}:{})}};
      const vc=(request.visit_conditions=request.visit_conditions||{})[pid]||{};
      if(!vc.party_composition)request.visit_conditions[pid]={...vc,party_size:3,party_composition:{adult_count:2,children:[{}]}};
      if(santa2026)request.visit_conditions[pid].building=chosenRoom.buildings[0];
      if(!['GRAND','VISTA'].includes(request.visit_conditions[pid].building))request.visit_conditions[pid].building='GRAND';
      // Package guests enter at 3부 15:20 / 4부 16:30 (2025 press release). The booked session is an operator assumption
      // (default 15:20, changeable); admission is the entitlement, attendance is still executed or missed by the engine.
      const bookStart=form.santa_booking===undefined?(santa2026?'': 'auto'):form.santa_booking;
      const as=request.scenario.assumptions=request.scenario.assumptions||{};
      as.sessions=santa2026?[["15:20","16:30"],["16:40","17:50"]]:[["11:00","12:00"],["14:10","15:10"],["15:20","16:20"],["16:30","17:30"]];as.duration_min=santa2026?70:60;
      if(bookStart)as.booked_sessions={[pid]:{date:request.start_date,start:bookStart}};else delete as.booked_sessions;
      as.santa_before_checkin=form.santa_before_checkin===false?'not_allowed':'operator_virtual_allowed';
    }
  }
  return typeof HLVisitExecution==='undefined'?request:HLVisitExecution.request(request,form.judgment_mode||'replay',form.saved_policy||null);
}
async function situationOpen(pid, fromFlow = false, updateHash = true) {
  if (SIT.busy) return;
  const token = ++SIT.token; SIT.error = null; SIT.notice = null; SIT.entered = false;
  await libLoad();
  if(libEng(pid)?.isolated_qa)await window.HillinkPrivateIntake.load(pid);
  const persona = libP(pid);
  if (!persona || !(libEng(pid)?.isolated_qa || libPublished(persona)) || !libRuntime(pid)) return;
  if (!SIT.options) { const response = await fetch("/static/event_scenario_options.json"); if (!response.ok) throw new Error("상황 선택 자료를 불러오지 못했습니다."); SIT.options = await response.json(); }
  if (!SIT.savedRuns) { try { const r = await fetch('/api/saved-visits',{cache:'no-cache'}); SIT.savedRuns = r.ok ? ((await r.json()).runs||[]) : []; } catch (e) { SIT.savedRuns = []; } }
  if (!SIT.roomOptions) { const r = await fetch('/api/room/options'); if (!r.ok) throw new Error('객실 상품을 불러오지 못했습니다.'); SIT.roomOptions = await r.json(); }
  if (token !== SIT.token) return;
  SIT.pid = pid; SIT.draftPid=pid;
  const form = situationForm(pid), last = typeof REV !== "undefined" && REV.latest && REV.latest.flow.plans[pid] ? REV.latest : null;
  if (fromFlow && last) {
    form.scenarioOverrides=last.request.scenario?structuredClone(last.request.scenario):null;
    form.event = last.request.scenario? (last.request.scenario.event_card_id==="WINE_FAIR_2026_AUTUMN"?"wine":last.request.scenario.event_card_id) : (last.request.event_mode === "wine" || last.request.event) ? "wine" : "none";
    form.duration = last.request.duration || "day_visit"; form.seed = last.request.seed || 0;
    form.package_id = last.request.package_id || last.request.catalog_options?.room_products?.[pid] || (last.request.scenario?.entitlements?.[pid]?.selected_package ? SIT.roomOptions.packages.find(x=>x.runnable&&x.adapter==='event_entitlement'&&x.event_card_id===last.request.scenario.event_card_id)?.id : '') || '';
    form.start_date=last.request.start_date;form.weather=last.request.environment?.weather;form.arrival_time=last.request.environment?.arrival_time;
    form.visit_conditions = last.request.visit_conditions ? structuredClone(last.request.visit_conditions) : null;
    form.catalogEnabled=!!last.request.catalog_policy;
    form.judgment_mode=last.request.judgment_mode||(last.request.hybrid_policy==='LLM_AUTONOMOUS_CUSTOMER_V16'?'replay':'rules');
    form.detailDraft=null;form.c01Enabled=last.request.behavior_engine==='m4_c01';form.simulation_mode=last.request.simulation_mode;form.resolvedSnapshot={run_id:last.flow.ledger.run_id,requested:last.request.visit_conditions&&last.request.visit_conditions[pid]||null,resolved_conditions:last.flow.visit&&last.flow.visit.resolved_conditions&&last.flow.visit.resolved_conditions[pid]||null};
  }
  LIBV.situation = pid; LIBV.open = pid;
  if (typeof DS !== "undefined") { DS.step = null; if (typeof dsPresent === "function") dsPresent(); }
  if (updateHash) history.pushState(null, "", `#situation/${encodeURIComponent(pid)}`);
  setMode("library"); situationRender(); const root = document.querySelector("#libraryView"); if (root) root.scrollTop = 0;
}
// Catalog eligibility is shared by rendering and request validation; unavailable products never persist.
function situationRoomPackages(form,pid,catalog,event) {
  const nights=({day_visit:0,stay_1:1,stay_2:2,stay_3:3})[form.duration]||0;
  const vc=((form.visit_conditions||{})[pid]||{}),building=vc.building;
  const date=form.start_date||(event||{}).start_date||'2026-10-24';
  const dates=Array.from({length:nights},(_,i)=>{const d=new Date(date+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+i);return d.toISOString().slice(0,10);});
  const party=Number(form.detailDraft?.partyText||vc.party_size||0);
  const children=form.detailDraft?.composition?form.detailDraft.children:vc.party_composition?.children;
  return ((catalog||{}).packages||[]).filter(p=>p.runnable&&nights>=p.minimum_nights&&(!p.nights||nights===p.nights)
    &&(!building||p.buildings.includes(building))&&(!p.required_party_size||!party||p.required_party_size===party)
    &&(!p.party_qualification?.douglas_age_rule||!children?.some(c=>c.age_months==null||c.age_months<156||c.school_stage!=='secondary'))
    &&(p.allowed_dates?dates.every(d=>p.allowed_dates.includes(d)):(!p.effective_from||p.effective_from<=date)&&(!p.effective_to||date<=p.effective_to))
    &&(p.adapter==='catalog_room'||(p.event_card_id?p.event_card_id===(event||{}).event_card_id:!(event||{}).event_card_id)));
}
function situationRender() {
  const root = document.querySelector("#libraryView"), p = SIT.pid && libP(SIT.pid);
  if (!root || !p || !SIT.options) return;
  const scroll = root.scrollTop, form = situationForm(p.id), opts = SIT.options;
  const entering = !SIT.entered; SIT.entered = true;
  const topTraits = libTopBars(p.id, 3).map(x => x.label.replace(/ · 분위기$/, ""));
  const DURATION = { day_visit: "당일 방문 · 0박", stay_1: "1박 2일", stay_2: "2박 3일", stay_3: "3박 4일" };
  const event = opts.events.find(x => x.id === form.event) || opts.events.find(x => x.id === "none");
  const type = libTypeLabel(p), viewDate = form.start_date || event && event.start_date || "2026-10-24";
  const santaCard = event && ["SANTA_KIDS_VILLAGE_2025","SANTA_KIDS_VILLAGE_2026"].includes(event.event_card_id);
  const santa2026 = event?.event_card_id === "SANTA_KIDS_VILLAGE_2026";
  const roomPackages = situationRoomPackages(form, p.id, SIT.roomOptions, event);
  if (form.package_id && !roomPackages.some(x=>x.id===form.package_id)) {
    form.package_id=''; SIT.notice='방문 조건에 적용할 수 없어 패키지 선택을 해제했습니다.';
  }
  const selectedRoomPackage=roomPackages.find(x=>x.id===form.package_id);
  if(selectedRoomPackage?.adapter==='catalog_room')form.catalogEnabled=true;
  const roomBuilding=((form.visit_conditions||{})[p.id]||{}).building;
  const roomValue=form.package_id || (((form.visit_conditions||{})[p.id]||{}).breakfast_plan==='room_only'?'room_only':'breakfast_included');
  const roomHelp=selectedRoomPackage?selectedRoomPackage.summary:form.duration==='day_visit'?'당일 방문 · 객실 미사용':roomValue==='room_only'?(roomBuilding==='DOUGLAS'?'라이트 조식 포함 · 더뷔페 별도 이용':'조식 별도 · 유료 이용 가능'):roomBuilding==='DOUGLAS'?'더글라스 라운지 · 라이트 조식 포함':'조식 포함 · 기본 2인';
  const roomDetails=selectedRoomPackage?selectedRoomPackage.details+(selectedRoomPackage.room_price_krw?' · 등록 참고가 '+Number(selectedRoomPackage.room_price_krw).toLocaleString('ko-KR')+'원 · 적용 기간 '+(selectedRoomPackage.effective_from||'미기재')+' ~ '+(selectedRoomPackage.effective_to||'미기재'):''):'가상 객실 모델 단가 · 그랜드 313,000원 / 비스타 373,000원 · 더글라스 259,000원(라운지 혜택 포함). 포함 권리와 실제 이용은 별개이며 추가 인원·상품 조건을 확인합니다. 더뷔페 변경 차액은 미확인입니다.';
  let ready=true,detailError=null;try{situationRequest(p.id,form,opts);}catch(e){ready=false;detailError=e.message;}
  // Display only: mirrors the engine's event date gate (event_scenarios.active); the engine remains the authority.
  const eventActiveOn = (item, day) => !item.source_date_range || (item.source_date_range[0] <= day && day <= item.source_date_range[1] && (item.weekdays || [0,1,2,3,4,5,6]).includes((new Date(day + "T00:00:00Z").getUTCDay() + 6) % 7));
  const eventLabel = item => item.id==='SAVORING_SUMMER_NIGHT_2026' ? '<span class="st-event-title"><span>2026 리버파크</span><span class="st-event-english">Savoring Summer Night</span></span>' : `<span>${esc(item.label)}</span>`;
  const choiceTile = (item, enabled, category = "") => enabled
    ? `<button type="button" class="st-choice${form.event === item.id && category === "event" ? " on" : ""}" data-sit-event="${esc(item.id)}" aria-pressed="${form.event === item.id && category === "event"}"${SIT.busy ? " disabled" : ""}>${eventLabel(item)}<small>${eventActiveOn(item, viewDate) ? "실행 가능" : "선택 날짜 운영 기간 아님 · 참여 없음"}</small></button>`
    : `<button type="button" class="st-choice is-pending" disabled aria-disabled="true"><span>${esc(item.label)}</span><small>${item.source === "product_roadmap" ? "준비 중" : "계산 미연결"}</small></button>`;
  const eventChoices = opts.events.map(x => choiceTile(x, x.enabled === true, "event")).join("");
  const weatherChoices = opts.weather.map(x => `<button type="button" class="st-choice${(form.weather||'clear')===x.id?' on':''}" data-sit-weather="${esc(x.id)}" aria-pressed="${(form.weather||'clear')===x.id}"><span>${esc(x.label)}</span><small>가상 운영 조건</small></button>`).join('');
  const timingSelected = x => ['weekday','weekend'].includes(x.id) ? ([0,6].includes(new Date(viewDate+'T00:00:00Z').getUTCDay()) === (x.id==='weekend')) : form.arrival_time===({morning:'09:00',afternoon:'14:30',night:'19:30'})[x.id];
  const timingTile = x => `<button type="button" class="st-choice${timingSelected(x)?' on':''}" data-sit-time="${esc(x.id)}" aria-pressed="${timingSelected(x)}"><span>${esc(x.label)}</span><small>${['weekday','weekend'].includes(x.id)?'방문일 변경':'방문 시작 시각'}</small></button>`;
  const dayChoices = opts.timing.filter(x => ["weekday", "weekend"].includes(x.id)).map(timingTile).join("");
  const arrivalChoices = opts.timing.filter(x => ["morning", "afternoon", "night"].includes(x.id)).map(timingTile).join("");
  const purposeChoices = opts.purposes.map(x => choiceTile(x, false)).join("");
  const chosenDuration = DURATION[form.duration] || form.duration;
  const chosenEvent = event ? event.label : "행사 없음";
  const chosenPackage = form.package_id === "SANTA_PKG_2025" ? `2025 산타 객실 패키지 · 1박 적용 · ${(form.santa_booking===undefined?"auto":form.santa_booking)==="auto"?"입장 회차 자동 권장":(form.santa_booking?"입장 "+form.santa_booking+" 예약(가정)":"입장 예약 없음")}` : selectedRoomPackage ? selectedRoomPackage.label : roomHelp;
  root.innerHTML = `<div class="lb st-root">
    <div class="st-topline"><button type="button" class="cf-btn cf-sm" id="sitHome">← 고객 유형</button><span>페르소나 라이브러리 · 방문 상황</span></div>
    <section class="st-persona" aria-label="선택 고객 요약">
      ${libThumbP(p, "st-thumb")}
      <div class="st-persona-main"><div class="st-persona-id"><b>${esc(dno(p.id))}</b><span>${esc(type)}</span></div>
        <div class="st-traits" aria-label="프로필 확인 특성">${topTraits.length ? topTraits.map(x => `<span>${esc(libShort(x, 28))}</span>`).join("") : `<span class="st-traits-empty">확인된 특성 없음</span>`}</div>
        <button type="button" class="st-profile-link" id="sitProfile">상세 프로필 보기 ↗</button>
      </div>
    </section>
    ${p.isolated_qa?'<p class="st-private-note">검토 중 · 소유자 전용</p>':''}<section class="st-transition"><h1>이 고객이 새로운 상황에서 워커힐을 방문한다면?</h1></section>
    <div class="st-unfold-line" aria-hidden="true"><i></i></div>
    <section class="st-conditions" aria-label="가상 방문 상황 캔버스">
      <section class="st-zone st-basic" aria-labelledby="stBasicTitle">
        <div class="st-zone-head"><span>01</span><h2 id="stBasicTitle">방문 기본 조건</h2><small>체류와 객실</small></div>
        <div class="st-fields">
          <div class="st-field"><label for="sitDuration">방문 기간</label><select class="cf-input" id="sitDuration"><option value="day_visit"${form.duration === "day_visit" ? " selected" : ""}>당일 방문 · 0박</option><option value="stay_1"${form.duration === "stay_1" ? " selected" : ""}>1박 2일</option><option value="stay_2"${form.duration === "stay_2" ? " selected" : ""}>2박 3일</option><option value="stay_3"${form.duration === "stay_3" ? " selected" : ""}>3박 4일</option></select><small>날짜별 체크인·연박·체크아웃 자동 구성</small></div>
          <div class="st-field st-judgment"><label for="sitJudgment">행동 판단</label><select class="cf-input" id="sitJudgment">${HLVisitExecution.options(form.judgment_mode||'replay')}</select><small id="sitLiveStatus" role="status" hidden></small><small>${({live:'새로운 LLM 호출 · 유료 · 판단마다 30~70초',rules:'LLM 없이 규칙 점수로만 계산 · 무료',replay:'저장된 조건과 똑같을 때만 무료로 재생 · 새 조건은 새로운 LLM 판단을 고르세요'})[form.judgment_mode||'replay']}</small>${(form.judgment_mode||'replay')==='replay'&&(SIT.savedRuns||[]).some(r=>r.customer===p.id)?`<details class="st-saved"${form.savedTag?' open':''}><summary>저장된 실행 조건 불러오기</summary><select class="cf-input" id="sitSavedRun" aria-label="저장된 실행 조건"><option value="">조건 선택</option>${SIT.savedRuns.filter(r=>r.customer===p.id).map(r=>`<option value="${esc(r.tag)}"${form.savedTag===r.tag?" selected":""}>${esc({day_visit:"당일",stay_1:"1박",stay_2:"2박",stay_3:"3박"}[r.duration]||r.duration)} · ${esc(r.tag.replace(p.id+"-","").replace(/^v16-/,""))}</option>`).join("")}</select><small>불러오면 방문 기간 · 방문일 · 시드 · 도착 시각 · 행사 · 객실 조건이 저장 당시 값으로 바뀌고 행동 판단은 ‘저장된 LLM 판단’이 됩니다.</small></details>`:""}</div>
          <div class="st-field"><label for="sitBuilding">이번 방문 숙박 건물</label><select class="cf-input" id="sitBuilding"${form.duration==='day_visit'?' disabled':''}>${[['','고객별 기존 조건'],['GRAND','그랜드'],['VISTA','비스타'],['DOUGLAS','더글라스']].map(([value,label])=>`<option value="${value}"${((form.visit_conditions||{})[p.id]||{}).building===value?' selected':''}>${label}</option>`).join('')}</select><small>선택한 건물은 이번 가상 방문에만 적용</small></div>
          <div class="st-field st-room-condition"><label for="sitRoomCondition">객실 조건</label><select class="cf-input" id="sitRoomCondition" aria-describedby="sitRoomHelp"${form.duration==='day_visit'?' disabled':''}>${[['breakfast_included','조식 포함 객실 — 기본'],['room_only','조식 별도 객실'],...roomPackages.map(x=>[x.id,x.label])].map(([value,label])=>`<option value="${esc(value)}"${roomValue===value?' selected':''}>${esc(label)}</option>`).join('')}</select><small id="sitRoomHelp" title="${esc(roomHelp)}">${esc(roomHelp)}</small><details><summary>객실 상품 상세</summary><small>${esc(roomDetails)}</small>${(SIT.roomOptions?.packages||[]).some(x=>!x.runnable)?`<p>상품 혜택의 계산 연결을 확인한 항목만 선택할 수 있습니다.</p><details><summary>아직 선택할 수 없는 등록 상품</summary>${SIT.roomOptions.packages.filter(x=>!x.runnable).map(x=>`<p>${esc(x.label)} · ${esc(x.not_runnable_reason||x.details)}</p>`).join('')}</details>`:''}</details></div>${santaCard && selectedRoomPackage?.adapter === "event_entitlement" ? `
          <div class="st-field"><label for="sitSantaBooking">산타 입장 회차(가상 예약)</label><select class="cf-input" id="sitSantaBooking" aria-describedby="sitSantaBookingHelp">${(santa2026?[["","예약 없음 · 입장 혜택만 보유"],["15:20","3부 15:20–16:30 · 예약 가정"],["16:40","4부 16:40–17:50 · 예약 가정"]]:[["auto","자동 권장 · 도착·체크인·이동 기준(기본)"],["15:20","3부 15:20 · 운영자 지정"],["16:30","4부 16:30 · 운영자 지정"],["","예약 없음 · 입장 혜택만 보유"]]).map(([v,l])=>`<option value="${v}"${(form.santa_booking===undefined?(santa2026?'':'auto'):form.santa_booking)===v?' selected':''}>${l}</option>`).join('')}</select><small id="sitSantaBookingHelp">${santa2026?'2026 공식 패키지 회차 · 예약은 운영자 가정입니다. 실제 참가는 도착·이동·자격 조건에서 결정됩니다.':'패키지 고객 입장 3·4부(2025 보도자료) · 자동 권장: 도착 후 3부가 가능하면 3부, 아니면 체크인(15:00·20분)·짐 정리(35분) 뒤 4부, 둘 다 어려우면 미이용 사유 기록 · 운영자가 회차를 지정하면 그 예약을 우선 · 참석 여부는 엔진이 시간·이동 제약 안에서 실행'}</small><label class="st-check"><input type="checkbox" id="sitSantaBeforeCheckin"${form.santa_before_checkin===false?'':' checked'}> 체크인 전 행사장 입장 허용(운영자 가상 조건 · 실제 호텔 규칙 미확인)</label></div>` : ""}
        </div>
        <label class="st-detail-check"><input type="checkbox" id="sitCatalog"${selectedRoomPackage?.adapter==='catalog_room'?' disabled':''}${form.catalogEnabled?' checked':''}>상품별 선택·가격을 함께 계산해 운영 전략 비교</label><small class="st-detail-note">이 옵션을 바꾸면 새로운 기준 방문을 생성합니다. 같은 기준 안에서 할인 전후를 비교합니다.</small>
        ${situationDetailsHTML(p.id,form)}
      </section>
      <section class="st-zone st-environment" aria-labelledby="stEnvTitle">
        <div class="st-zone-head"><span>02</span><h2 id="stEnvTitle">방문 환경</h2><small>선택 가능한 조건과 확장 항목</small></div>
        <div class="st-environment-grid">
          <section class="st-choice-group st-event-group"><h3>행사</h3><div class="st-choice-grid">${eventChoices}</div></section>
          <section class="st-choice-group st-weather-group"><h3>날씨</h3><div class="st-choice-grid">${weatherChoices}</div></section>
          <section class="st-choice-group st-timing-group"><h3>방문 시점</h3><label>가상 방문일<input id="sitDate" class="cf-input" type="date" value="${esc(viewDate)}" min="2025-01-01" max="2026-12-31"></label><details><summary>동일 입력 재현</summary><label>실행 시드<input id="sitSeed" class="cf-input" type="number" min="0" max="9999" step="1" value="${form.seed||0}"></label></details><div class="st-timing-section"><h4>요일</h4><div class="st-choice-grid st-day-grid">${dayChoices}</div></div><div class="st-timing-section"><h4>도착 시간</h4><div class="st-choice-grid st-arrival-grid">${arrivalChoices}</div></div></section>
        </div>
      </section>
      <section class="st-zone st-operations" aria-labelledby="stOpsTitle">
        <div class="st-zone-head"><span>03</span><h2 id="stOpsTitle">운영 개입</h2><small>조건별 계산 연결 상태</small></div>
        <div class="st-ops-grid">${purposeChoices}<button type="button" class="st-choice is-pending" disabled aria-disabled="true"><span>대기·혼잡</span><small>계산 미연결</small></button></div>
      </section>
      <div class="st-action"><p class="st-summary" id="sitSummary">${esc(dno(p.id))}<i>·</i>${esc(chosenDuration)}<i>·</i>${esc(chosenEvent)}<i>·</i>${esc(chosenPackage)}</p><button type="button" class="cf-btn cf-primary" id="sitRun"${!ready || SIT.busy ? " disabled" : ""}>${SIT.busy ? "가상 방문 생성 중…" : SIT.lastGeneratedForm?.pid===p.id&&SIT.lastGeneratedForm.form===JSON.stringify(form)?"가상 방문 다시 생성":"가상 방문 생성"}</button></div>
      ${detailError?`<p class="rc-note" role="alert">${esc(detailError)}</p>`:''}${SIT.notice ? `<p class="st-notice" role="status">${esc(SIT.notice)}</p>` : ""}${SIT.error ? `<p class="rc-note" role="alert">${esc(SIT.error)}</p>` : ""}
    </section>
  </div>`;
  root.querySelector("#sitHome").onclick = () => libHome();
  root.querySelector("#sitProfile").onclick = () => p.isolated_qa ? window.HillinkPrivateIntake.show(p.id) : libOpen(p.id);
  root.querySelector('#sitRoomCondition').onchange=e=>{
    form.visit_conditions=form.visit_conditions||{};
    const vc=form.visit_conditions[p.id]=form.visit_conditions[p.id]||{};
    const selected=roomPackages.find(x=>x.id===e.target.value);
    form.package_id=selected?selected.id:'';
    if(selected){delete vc.breakfast_plan;if(selected.adapter==='catalog_room')form.catalogEnabled=true;if(!vc.building&&selected.buildings.length===1)vc.building=selected.buildings[0];}
    else if(e.target.value==='room_only')vc.breakfast_plan='room_only';else delete vc.breakfast_plan;
    SIT.notice=null;situationQueueRender();
  };
  root.querySelector('#sitBuilding').onchange=e=>{form.visit_conditions=form.visit_conditions||{};form.visit_conditions[p.id]=form.visit_conditions[p.id]||{};if(e.target.value)form.visit_conditions[p.id].building=e.target.value;else delete form.visit_conditions[p.id].building;situationQueueRender();};
  root.querySelector('#sitDuration').onchange=e=>{form.duration=e.target.value;situationQueueRender();};
  HLVisitExecution.bindAvailability(root.querySelector('#sitJudgment'),root.querySelector('#sitLiveStatus'));
  // Stored-run state belongs to Replay only. Leaving Replay drops the tag and the stored policy
  // (so a LIVE request is V17 and a rules request carries no LLM policy) but keeps every
  // visible condition value the reviewer may have loaded.
  root.querySelector('#sitJudgment').onchange=e=>{form.judgment_mode=e.target.value;if(form.judgment_mode!=='replay'){form.savedTag=null;form.saved_policy=null;}situationQueueRender();};
  const savedSel=root.querySelector('#sitSavedRun'); if(savedSel) savedSel.onchange=async e=>{const tag=e.target.value; form.savedTag=tag||null; if(!tag){situationQueueRender();return;}
    try{const r=await fetch('/api/saved-visits/run?tag='+encodeURIComponent(tag),{cache:'no-cache'}); if(!r.ok) throw new Error('saved'); const q=(await r.json()).request||{};
      const before={duration:form.duration,seed:form.seed||0,start_date:form.start_date||null,event:form.event,weather:form.weather||null,arrival_time:form.arrival_time||null,building:((form.visit_conditions||{})[p.id]||{}).building||null,package_id:form.package_id||'',judgment_mode:form.judgment_mode||'replay'};
      form.duration=q.duration||form.duration; form.seed=Number.isInteger(q.seed)?q.seed:0; form.start_date=q.start_date||null;
      form.event=q.scenario?(q.scenario.event_card_id==='WINE_FAIR_2026_AUTUMN'?'wine':q.scenario.event_card_id):(q.event_mode==='wine'?'wine':'none'); form.scenarioOverrides=q.scenario?structuredClone(q.scenario):null;
      form.weather=q.environment?.weather; form.arrival_time=q.environment?.arrival_time;
      form.visit_conditions=q.visit_conditions?structuredClone(q.visit_conditions):null; form.detailDraft=null;
      form.catalogEnabled=!!q.catalog_policy; form.c01Enabled=q.behavior_engine==='m4_c01'; form.package_id=q.package_id||'';
      form.judgment_mode='replay'; form.saved_policy=q.hybrid_policy||null;
      const after={duration:form.duration,seed:form.seed||0,start_date:form.start_date||null,event:form.event,weather:form.weather||null,arrival_time:form.arrival_time||null,building:((form.visit_conditions||{})[p.id]||{}).building||null,package_id:form.package_id||'',judgment_mode:'replay'};
      const label={duration:'방문 기간',seed:'시드',start_date:'방문일',event:'행사',weather:'날씨',arrival_time:'도착 시각',building:'숙박 건물',package_id:'객실 상품',judgment_mode:'행동 판단'};
      const changed=Object.keys(after).filter(k=>String(before[k]??'')!==String(after[k]??'')).map(k=>`${label[k]} ${before[k]||'기본'} → ${after[k]||'기본'}`);
      SIT.notice=changed.length?`저장된 조건을 불러와 바뀐 항목: ${changed.join(' · ')}. 이 조건 그대로 실행하면 무료 재생입니다.`:'이미 저장된 조건과 같습니다. 이 조건 그대로 실행하면 무료 재생입니다.';
    }catch(err){SIT.notice='저장된 조건을 불러오지 못했습니다.';}
    situationQueueRender();};
  const sb=root.querySelector("#sitSantaBooking"); if(sb) sb.onchange=e=>{ form.santa_booking=e.target.value; situationQueueRender(); };
  const sbc=root.querySelector("#sitSantaBeforeCheckin"); if(sbc) sbc.onchange=e=>{ form.santa_before_checkin=e.target.checked; situationQueueRender(); };
  root.querySelectorAll("[data-sit-event]").forEach(b => b.onclick = () => { if (!opts.events.some(x => x.id === b.dataset.sitEvent && x.enabled)) return; form.event = b.dataset.sitEvent;form.start_date=null;form.scenarioOverrides=null; SIT.notice=(opts.events.find(x=>x.id===form.event)||{}).description||null; situationQueueRender(); });
  root.querySelector("#sitRun").onclick = situationRun;
  root.querySelector('#sitCatalog').onchange=e=>{form.catalogEnabled=e.target.checked;situationQueueRender();};
  situationDetailsWire(root,p.id,form);
  if (entering) {
    const enteringPid = p.id;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (SIT.pid === enteringPid && LIBV.situation === enteringPid) root.querySelector(".st-root")?.classList.add("st-animating");
    }));
  }
  root.querySelectorAll('[data-sit-weather]').forEach(b=>b.onclick=()=>{form.weather=b.dataset.sitWeather;situationQueueRender();});
  root.querySelector('#sitDate').onchange=e=>{form.start_date=e.target.value;situationQueueRender();};
  root.querySelector('#sitSeed').onchange=e=>{form.seed=Number(e.target.value);situationQueueRender();};
  root.querySelectorAll('[data-sit-time]').forEach(b=>b.onclick=()=>{const id=b.dataset.sitTime;if(['weekday','weekend'].includes(id)){const d=new Date((form.start_date||(opts.events.find(x=>x.id===form.event)||{}).start_date||'2026-10-24')+'T00:00:00Z');for(let i=0;i<7;i++){const weekend=[0,6].includes(d.getUTCDay());if(weekend===(id==='weekend'))break;d.setUTCDate(d.getUTCDate()+1);}form.start_date=d.toISOString().slice(0,10);}else {form.arrival_time={morning:'09:00',afternoon:'14:30',night:'19:30'}[id];SIT.draftPid=SIT.pid;root.querySelectorAll('.st-arrival-grid [data-sit-time]').forEach(x=>{const selected=x===b;x.classList.toggle('on',selected);x.setAttribute('aria-pressed',String(selected));});return;}situationQueueRender();});
  root.scrollTop = scroll;
}
async function situationRun() {
  if (SIT.busy || !SIT.pid) return;
  const pid = SIT.pid, request = situationRequest(pid, situationForm(pid), SIT.options);
  const previous = Object.fromEntries(['flow','plans','visits','runs','res','visitData','visitDay','duration','one','sel','cond','keep','si','f','nowMin','ti','mode'].map(k=>[k,AG[k]]));
  previous.keep={...AG.keep};
  SIT.busy = true; situationRender();
  try {
    if (typeof DS !== "undefined") DS.step = null;
    LIBV.situation = null; AG.engine = "autonomy"; AG.one = pid; AG.mode = "agent"; AG.oneOverride = !!request.visit_override; AG.oneAuto = null; AG.flow = null; AG.plans = null; AG.visits = null; AG.runs = [];
    AG.visitRequest = request; AG.visitData = null; AG.visitDay = 1; AG.duration = request.duration;
    AG.judgmentMode=request.judgment_mode;
    AG.seed = request.seed; AG.iv = "none"; AG.scen = "day"; AG.exp = null; AG.keep.agent = null; AG.res = null; AG.autorun = true;
    AG.cond = { ...AG.cond, turn: "day", event: request.event_mode === "wine", pricing: "historical", product_levers: {} };
    history.pushState(null,"",`#flow/${encodeURIComponent(pid)}/${request.event_mode === "wine" ? 1 : 0}/live`);
    await setMode("agent");
    const ready = await dsWait(() => AG.one === pid && !AG.autorun && document.querySelector("#agRun"));
    if (!ready) throw new Error("고객 흐름을 준비하지 못했습니다. 다시 실행해 주세요.");
    await agRun();
    if(AG.lastGenerationError){
      const failure=AG.lastGenerationError;
      if(previous.flow){Object.assign(AG,previous);AG.visitRequest=null;agLeft();agShow(false);agSetScene(previous.si,previous.f);agPause();document.querySelector('#panel').insertAdjacentHTML('afterbegin',`<div class="callout" role="alert">계산 실패 — ${esc(failure)} · 이전 방문을 유지합니다.</div>`);}
      throw new Error(failure);
    }
    if(AG.flow){SIT.lastGeneratedForm={pid,form:JSON.stringify(situationForm(pid))};SIT.lastRequest=structuredClone(request);SIT.draftPid=null;}
  } catch(e) { SIT.error = e.message; LIBV.situation = pid; setMode("library"); }
  finally { SIT.busy = false; if (LIBV.situation) situationRender(); }
}
window.addEventListener("hashchange", () => { const match = location.hash.match(/^#situation\/([^/]+)$/); if (match) situationOpen(decodeURIComponent(match[1]),false,false).catch(console.error); });
window.addEventListener("popstate", () => { const match = location.hash.match(/^#situation\/([^/]+)$/); if (match) situationOpen(decodeURIComponent(match[1]),false,false).catch(console.error); });
window.addEventListener("load", () => { const match = location.hash.match(/^#situation\/([^/]+)$/); if (match) situationOpen(decodeURIComponent(match[1]),false,false).catch(console.error); });
