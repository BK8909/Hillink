/* Presentation only. Consume the existing v3 card; never write AG, plans or receipts. */
(function (root) {
  'use strict';
  const VERSION = 'rpg-reason-design-v2';
  const analytic = /후기|기록|고객입니다|성향|근거|평가|비교됐|확인|해석|추론|기여/;
  const technical = /점수|확률|가중치|계수|LLM|[A-Z]{2,}_[A-Z0-9_]+|\b[a-z]+_[a-z0-9_]+\b/;
  const endings = [
    ['먹습니다.', '먹어요.'], ['마칩니다.', '마쳐요.'], ['들릅니다.', '들러요.'],
    ['나섭니다.', '나서요.'], ['갑니다.', '가요.'], ['쉽니다.', '쉬어요.'],
    ['잡니다.', '자요.'], ['풉니다.', '풀어요.'], ['보냅니다.', '보내요.'],
    ['돌립니다.', '돌려요.'], ['녹입니다.', '녹여요.'], ['합니다.', '해요.'],
    ['있습니다.', '있어요.'], ['없습니다.', '없어요.'],
    ['했습니다.', '했어요.'], ['않았습니다.', '않았어요.'],
    ['있었습니다.', '있었어요.'], ['택했습니다.', '택했어요.']
  ];
  // Convert recorded actions and the two bounded v3 positive-trait templates.
  // Quotations and open-ended evidence interpretations keep their narrator voice.
  function spoken(text, index, party) {
    const s = String(text || '').trim();
    if (/["“”「」]/.test(s)) return {text:s, voice:'record'};
    const trait=/^후기 (?:기록으로 보면|전반으로 보면) (.+) 고객입니다\.$/.exec(s)
      || /^후기 전반에서 (.+) 쪽이 드러나는 고객입니다\.$/.exec(s);
    if (trait) return {text:`제 기록을 보면 ${trait[1]} 편이에요.`,voice:'persona'};
    if (analytic.test(s)) return {text:s, voice:'record'};
    let t = s;
    if (Number(party) > 1) t = t.replace(/두 사람이\s|일행이\s/g, '함께 ');
    for (const [from,to] of endings) if (t.endsWith(from)) return {text:t.slice(0,-from.length)+to, voice:'persona'};
    return {text:s, voice:'record'};
  }
  function splitSentences(text) {
    let quote=false,start=0;const out=[];
    for(let i=0;i<text.length;i++) {
      if(text[i]==='"')quote=!quote;
      if(text[i]==='“'||text[i]==='「')quote=true;
      if(text[i]==='”'||text[i]==='」')quote=false;
      if(!quote&&/[.!?。]/.test(text[i])&&/\s/.test(text[i+1]||'')) {
        out.push(text.slice(start,i+1).trim());start=i+1;
      }
    }
    if(text.slice(start).trim())out.push(text.slice(start).trim());
    return out;
  }
  function build(sentences, {party=null, verified=false, reasonDriven=false}={}) {
    const raw = sentences.map(s=>String(s||'').trim()).filter(Boolean);
    const items = raw.flatMap((s,i)=>splitSentences(s).map(text=>({text,source:i}))).map(({text:s,source:i})=> {
      // A legacy fallback can contain technical analysis. Leave that in precision evidence.
      if (technical.test(s)) return {text:'이 선택의 자세한 판단 과정은 행동근거에서 확인할 수 있어요.',voice:'record',source:i};
      return {...(reasonDriven ? {text:s,voice:'persona'} : verified ? spoken(s,i,party) : {text:s,voice:'record'}),source:i};
    });
    if (!items.length) items.push({text:'이 장면의 개별 선택 이유는 기록에서 확인되지 않습니다.',voice:'record',source:null});
    // v3 has at most three sentences. Longer legacy paragraphs get 1–2 per page.
    const pages=[];
    for(const item of items) {
      const last=pages.at(-1);
      if(!verified&&pages.length>1&&last.count<2&&last.text.length+item.text.length<220) {
        last.text+=' '+item.text;last.count++;
      } else pages.push({...item,count:1});
    }
    return pages.map((item,i)=>({...item,title:i===0?'지금의 선택':i===1?'경험과 이유':'선택의 맥락'}));
  }
  const clip=(t,n)=>{t=String(t||'').trim();return t.length>n?t.slice(0,n-1)+'…':t;};
  function modelPages(model) {
    const d=model.decision||{},last=(d.attempts||[]).at(-1),answer=last?.answer||{},plans=answer.plans||[];
    const actions=(d.input_context||{}).actions||[],label=id=>actions.find(a=>a.action_id===id)?.label||null;
    const sents=splitSentences(String(model.summary||'').trim()).filter(s=>!technical.test(s));
    const choice=sents[0]||(d.execution_state==='EXECUTION_HOLD'?'이 장면에서는 유효한 선택을 확정하지 못했어요.':'이 선택의 요약은 행동근거에서 볼 수 있어요.');
    const reason=clip(sents.slice(1,3).join(' '),170);
    const alt=plans.map((p,i)=>i===answer.selected_index?null:p).find(p=>p&&label(p.action_id));
    const altLine=alt?`대신 둔 선택은 ${label(alt.action_id)}${clip(splitSentences(String(alt.decision_summary||''))[0]||'',80)?` — ${clip(splitSentences(String(alt.decision_summary||''))[0],80)}`:''}`:'';
    const second=[reason,altLine].filter(Boolean).join(' ')||(d.day_end_review?'남은 일정과 휴식을 검토한 뒤 정한 선택이에요.':'이 선택과 비교한 대안은 행동근거에서 볼 수 있어요.');
    return [{text:choice,voice:'record',title:'지금의 선택',count:1},{text:second,voice:'record',title:'이유와 대안',count:1}];
  }
  function keyOf({run,customer,scene,date,start,action}) {
    return JSON.stringify([run||null,customer,scene,date||null,start,action]);
  }
  // Travel is a recorded transition, not a fresh preference/LLM judgment.
  // Read only symbolic action/meal/location codes; never interpolate venue labels.
  function movementMessage(scene={}, destination={}) {
    const act=String(destination.act||'').toLowerCase(),loc=String(scene.b||destination.loc||'').toUpperCase();
    if (/^(leave|depart|return_home)$/.test(act)) return '집으로 돌아가는 중';
    if (act==='checkin') return '체크인하러 이동 중';
    if (/^(room_|unpack|pack$|sleep$)/.test(act)||/_ROOM$/.test(loc)) return '객실로 이동 중';
    const meal=destination.meal||destination.turn||act.replace(/^turn_/,'').split('_')[0];
    if (meal==='breakfast') return '아침 먹으러 이동 중';
    if (meal==='lunch') return '점심 먹으러 이동 중';
    if (meal==='dinner') return '저녁 먹으러 이동 중';
    if (/^(pool|swim)/.test(act)||/(?:^|_)POOL$/.test(loc)) return '수영하러 이동 중';
    if (/sauna/.test(act)||/SAUNA/.test(loc)) return '사우나로 이동 중';
    if (/footbath/.test(act)||/^SKYARD/.test(loc)) return '족욕하러 이동 중';
    if (/walk|riverpark/.test(act)) return '산책하러 이동 중';
    if (/^(turn_event|event(?:_|$)|wine_fair|fair)/.test(act)||/^(FOREST|WINE_FAIR|CONVENTION|EVENT)/.test(loc)) return '행사 참가하러 이동 중';
    if (/_LOBBY$|_FRONT_DESK$/.test(loc)||act==='checkout') return '로비로 이동 중';
    if (['PIZZA_HILL','MYONGWOLGWAN','ONDAL','GEUMRYONG','THE_BUFFET','MOEGI'].includes(loc)) {
      const time=Number(destination.t0);
      if (Number.isFinite(time)) return time<660?'아침 먹으러 이동 중':time<960?'점심 먹으러 이동 중':'저녁 먹으러 이동 중';
    }
    return '다음 장소로 이동 중';
  }
  const API = {version:VERSION,build,spoken,keyOf,movementMessage};
  if (typeof module !== 'undefined' && module.exports) module.exports=API;
  root.HLDialogue=API;
  if (!root.document || typeof root.agBRCard !== 'function') return;
  let active={key:null,index:0,all:false};
  API.capture=()=>({...active});
  API.restore=s=>{if(s&&s.key){active={...s};const box=root.document.querySelector('[data-dialogue-key]');if(box?.dataset.dialogueKey===s.key)paint(box,s.index,s.all);}};
  const esc = s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const original=root.agBRCard;
  const sentencesOf=why=>{
    const story=[...why.querySelectorAll('.hls-sentence')].map(e=>e.textContent.trim());
    if(story.length)return story;
    const body=why.querySelector('.ag-readable-body,.frp-state-reason,.hls-story');
    return body ? [body.textContent.trim()] : [];
  };
  function paint(section,index,all) {
    if(section.classList.contains('hls-rpg-moving'))return;
    const pages=[...section.querySelectorAll('[data-dialogue-page]')];
    index=Math.min(Math.max(index,0),pages.length-1);
    pages.forEach((p,i)=>{p.hidden=i!==index;});
    section.dataset.dialogueIndex=String(index);
    section.querySelector('[data-dialogue-count]').textContent=`${index+1} / ${pages.length}`;
    section.querySelector('[data-dialogue-title]').textContent=pages[index].dataset.pageTitle;
    section.querySelector('[data-dialogue-voice]').textContent=pages[index].dataset.voice==='persona'?'시뮬레이션 독백 · 실제 발언 아님':'기록 안내 · 실제 발언 아님';
    const next=section.querySelector('[data-dialogue-next]');
    next.hidden=pages.length<2;
    next.setAttribute('aria-label',index===pages.length-1?'첫 대사로 돌아가기':'다음 대사');
    const full=section.querySelector('[data-dialogue-all]');full.open=!!all;
  }
  root.agBRCard=function(c,sc) {
    const html=original.apply(this,arguments);
    if(!sc)return html;
    try {
      const tpl=root.document.createElement('template');tpl.innerHTML=html.trim();
      const card=tpl.content.firstElementChild,why=card?.querySelector('[data-frp-section="why"]'),current=card?.querySelector('[data-frp-section="current"]');
      if(!why||!current)return html;
      const pid=c.persona_id, data=typeof AG!=='undefined'?AG:null;
      const D=typeof agBRData==='function'?agBRData(c,sc):null;
      const raw=data?.flow?.result?.plans?.[pid]?.scenes?.[D?.index];
      const key=keyOf({run:data?.flow?.ledger?.run_id||data?.flow?.result?.visit_id,customer:pid,scene:D?.index??sc.si,date:raw?.visit_date||sc.visit_date,start:raw?.t0??sc.t0,action:raw?.act||sc.act});
      if(active.key!==key)active={key,index:0,all:false};
      if(sc.k==='move') {
        const scenes=typeof agScenes==='function'?agScenes(pid):[],at=scenes.findIndex(s=>s.si===sc.si);
        const destination=at>=0?scenes.slice(at+1).find(s=>s.k!=='move'):null;
        const message=movementMessage(sc,destination||{}),box=root.document.createElement('section');
        box.className='frp-section frp-why hls-rpg hls-rpg-moving'+(data?.playing?'':' is-paused');
        box.dataset.frpSection='why';box.dataset.dialogueKey=key;box.dataset.movementMessage=message;
        const link=why.querySelector('[data-ux-scene]')?.outerHTML||'';
        box.innerHTML=`<div class="hls-rpg-speaker"><b>이동 중</b></div>
          <div class="hls-rpg-journey"><p aria-label="${esc(message)}..."><span>${esc(message)}</span><span class="hls-rpg-dots" aria-hidden="true"><span>...</span></span></p></div>
          <div class="hls-rpg-move-tools">${link}</div>`;
        why.replaceWith(box);current.insertAdjacentElement('afterend',box);
        return card.outerHTML;
      }
      const V=typeof agVC==='function'?agVC(pid):null;
      const latest=root.__HLS_LAST;
      const input=latest?.result===data?.flow?.result&&latest?.pid===pid&&latest?.si===sc.si?latest.x:(data?.flow?.result?.plans?.[pid]&&D?.index>=0?root.HLStory?.input(data.flow.result,pid,D.index):null);
      const plan=data?.flow?.result?.plans?.[pid];
      const autonomous=plan?.trace?.planner_backend?.startsWith('LLM_AUTONOMOUS_CUSTOMER_');
      const model=autonomous&&root.HLAgentDecisionView?.view(root.HLAgentDecisionView.resolve(raw,plan));
      const reason=!autonomous&&input&&root.HLChoiceReason?.compose(input);
      // Legacy score templates have no autonomous packets. They must not erase
      // the actual pre-choice model reason or invent a missing-record message.
      const source=model?[model.summary]:autonomous?['이 장면은 공통 방문 절차이며 별도의 LLM 선택 판단과 구분합니다.']:reason?reason.sentences:sentencesOf(why);
      // A recorded LLM decision gets exactly two pages: the choice, then a short reason with
      // the one alternative it set aside. Text comes from the decision record only; nothing
      // about feelings or motives is added, and the full record stays on the evidence page.
      const pages=model?modelPages(model):build(source,{party:V?.party,verified:!autonomous&&(!!reason||why.dataset.storyOk==='1'),reasonDriven:!!reason});
      root.__HL_REASON_LAST=reason?{pid,scene:D?.index??sc.si,...reason}:null;
      // Retain the precise existing link and every non-reason card, with its handlers.
      const kind=input&&root.HLDecisionExplain?.classify(input);
      const link=(why.querySelector('[data-ux-scene]')?.outerHTML||'').replace('행동근거 보기',kind==='SCHEDULE'?'일정 안내':kind==='CONDITIONAL'?'적용 조건 보기':'행동근거 보기');
      const box=root.document.createElement('section');
      box.className='frp-section frp-why hls-rpg';box.dataset.frpSection='why';box.dataset.dialogueKey=key;
      if(why.dataset.reasonKey)box.dataset.reasonKey=why.dataset.reasonKey;
      box.innerHTML=`<div class="hls-rpg-speaker"><b>왜 이 행동인가?</b></div>
        <div class="hls-rpg-heading"><h3>왜 이 행동인가?</h3><small data-dialogue-voice></small></div>
        <div class="hls-rpg-message"><span class="hls-rpg-chapter" data-dialogue-title></span><div class="hls-rpg-lines" aria-live="polite" aria-atomic="true">${pages.map((p,i)=>`<p data-dialogue-page="${i}" data-voice="${p.voice}" data-page-title="${p.title}"${i?' hidden':''}>${esc(p.text)}</p>`).join('')}</div></div>
        <div class="hls-rpg-footer"><details data-dialogue-all><summary>대화 전체 보기</summary><ol>${pages.map(p=>`<li>${esc(p.text)}</li>`).join('')}</ol><p>실행 기록을 옮긴 가상 대화이며 실제 후기 원문 발언이 아닙니다.</p></details><span class="hls-rpg-pager"><small data-dialogue-count></small><button type="button" data-dialogue-next aria-label="다음 대사"><span aria-hidden="true">▼</span></button></span></div>`;
      paint(box,active.index,active.all);
      // The dialog already carries the recorded decision summary; the card keeps action, place, time and spend.
      if(model)current.querySelector('.frp-current-description')?.remove();
      why.replaceWith(box);current.insertAdjacentElement('afterend',box);
      // One small evidence button directly under the dialog, outside the paged text, above 다음 일정.
      // Same handler and scene/person/run context as before (data-ux-scene).
      const evidence=root.document.createElement('div');evidence.className='hls-rpg-evidence';
      evidence.innerHTML=link.replace(/>[^<]*<\/button>/,'>정밀 근거 보기 →</button>');
      if(evidence.querySelector('[data-ux-scene]'))box.insertAdjacentElement('afterend',evidence);
      return card.outerHTML;
    } catch (_) { return html; }
  };
  if(typeof root.agStripState==='function') {
    const stripState=root.agStripState;
    root.agStripState=function(...args) {
      const result=stripState.apply(this,args);
      root.document.querySelectorAll('.hls-rpg-moving').forEach(box=>box.classList.toggle('is-paused',typeof AG==='undefined'||!AG.playing));
      return result;
    };
  }
  root.document.addEventListener('click',event=>{
    const button=event.target.closest?.('[data-dialogue-next]');if(!button)return;
    const section=button.closest('[data-dialogue-key]');
    if(!section||section.dataset.dialogueKey!==active.key)return;
    const n=section.querySelectorAll('[data-dialogue-page]').length;
    active.index=(Number(section.dataset.dialogueIndex)+1)%n;
    paint(section,active.index,active.all);
  });
  root.document.addEventListener('toggle',event=>{
    const details=event.target;
    if(!details.matches?.('[data-dialogue-all]'))return;
    if(details.closest('[data-dialogue-key]')?.dataset.dialogueKey===active.key)active.all=details.open;
  },true);
})(typeof window!=='undefined'?window:globalThis);
