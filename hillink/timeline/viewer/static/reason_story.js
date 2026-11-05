// HILLINK 고객 흐름 — '왜 이 행동인가' 서사형 설명 v2 (Claude 10/30 오후 · 관제 재검수 반영)
// 역할 분리: 고객 흐름 카드 = 2~3문장 이야기(점수 · 확률 · 규칙/LLM · 금액 · ID 없음) / 정밀 근거 페이지 = 기존 행동근거 화면을 '결정 요약 → 후기 근거 → 상태 → 후보 → 규칙·LLM → 최종·원장' 순으로 재배치.
// 입력은 실제 실행 기록(plan.scenes · plan.m4.decisions · 장면 basis · 원장 행)뿐. 기록에 없는 심리 · 선호 · 대안 · 수치는 쓰지 않는다. 계산 · 행동 · 원장은 바꾸지 않는다.
// 브라우저(제품 agent.js · behavior.js 뒤에 로드)와 Node(검수 스크립트) 공용.
(function (root) {
  'use strict';
  const hm = m => (m == null || isNaN(m)) ? '' : String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(Math.round(m % 60)).padStart(2, '0');
  const jong = w => { const c = String(w || '').replace(/\s*\([^)]*\)\s*$/, '').trim().slice(-1).charCodeAt(0); return c >= 0xAC00 && c <= 0xD7A3 ? (c - 0xAC00) % 28 : -1; };
  const josa = (w, a, b) => { const j = jong(w); if (j < 0) return b; if (a === '으로') return (j === 0 || j === 8) ? b : a; return j ? a : b; };
  const clean0 = s => String(s || '').replace(/\s*·\s*포함 혜택(?=\s|$)/g, '').replace(/\s*·\s*(기존 메뉴 기준 가상 계산|기존 공식 메뉴 기준 가상[^·]*|상품 조건 확인|상품\/금액 미확인|2026 가상 모델 단가)\s*/g, '').replace(/\s*·?\s*(객실포함|객실 포함|패키지 포함)(?=\s|$)/g, '').replace(/\s+(HOT|ICE)(?=\s|$)/, '').replace(/\s+/g, ' ').trim();
  const clean = s => clean0(s).replace(/^(\S+) \1(?=\s|$)/, '$1').replace(/^(\S+) 더\1(?=\s|$)/, '더 $1').replace(/\s*\+\s*/g, ' + ');
  const noParen = s => clean(s).replace(/\s*\([^)]*\)\s*/g, ' ').replace(/\s+/g, ' ').trim();
  const firstSentence = (s, max = 140) => { const t = String(s || '').trim(); const m = t.match(/^.+?(다\.|요\.|니다\.|[.!?])(\s|$)/); let x = m ? m[0].trim() : t; if (x.length > max) { const cut = x.slice(0, max); x = cut.slice(0, Math.max(cut.lastIndexOf(','), cut.lastIndexOf(' '))) + '…'; } return x; };
  const hash = s => { let h = 7; for (const ch of String(s)) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return h; };
  const SKIP = new Set(['move', 'wait']);
  const OBLIGATION = new Set(['arrive', 'checkin', 'unpack', 'wake', 'pack', 'checkout', 'leave', 'sleep']);
  const TRAIT = { space: '공간과 풍경을 즐기는 편', rest_need: '조용히 쉬는 시간을 중시하는 편', warm_rest: '따뜻하게 쉬는 것을 좋아하는 편', food: '음식 경험을 중시하는 편', food_specific: '좋아하는 메뉴가 분명한 편', value_check: '가격을 따져 보는 편', benefit: '혜택을 챙기는 편', routine: '익숙한 곳을 다시 찾는 편', novelty: '새로운 경험을 시도하는 편', premium: '특별한 경험에 비용을 쓰는 편', active: '몸을 움직이는 활동을 즐기는 편', alcohol_familiar: '술자리에 익숙한 편', breakfast_priority: '아침 식사를 챙기는 편', practical_alt: '실용적인 대안을 고르는 편', promo: '행사 · 프로모션에 관심이 있는 편' };
  // 점수 항(factor) → 카드 문장용 성향 표현. 선택된 후보의 점수 항에 실제로 기여한 경우에만 쓴다(기여 없는 요지 인용 금지)
  const FACTOR = [[/정원\s*·\s*산책/, '정원 산책을 즐기는'], [/온수\s*·\s*족욕/, '따뜻하게 쉬는 것을 좋아하는'], [/야경.*공간|공간 경험/, '야경과 공간을 즐기는'], [/실용적 식사 대안/, '식사를 간단히 해결하는'], [/새 경험 시도/, '새로운 경험을 시도하는'], [/시즌 행사|한정 반응/, '시즌 행사에 반응하는'], [/할인 반응/, '할인에 반응하는'], [/구체적 메뉴 기호/, '좋아하는 메뉴가 분명한'], [/음식 경험/, '음식 경험을 중시하는'], [/휴식\s*·\s*회복/, '쉬는 시간을 챙기는'], [/익숙한 곳|실제 이용 경험/, '가 본 곳을 다시 찾는'], [/홍보를 보고/, '홍보를 보고 움직이는'], [/아침|조식/, '아침 식사를 챙기는']];
  const FACTOR_WORDS = [[/정원|산책/, ['산책', '정원', '가든', '걷', '파크', '트레킹', '조망', '공원']], [/온수|족욕/, ['족욕', '온천', '스파', '사우나', '온수', '탕']], [/야경|공간/, ['야경', '뷰', '전망', '조망', '공간', '풍경', '루프탑', '한강']], [/음식|메뉴/, ['맛', '메뉴', '식사', '음식', '뷔페', '레스토랑', '파스타', '피자', '고기', '조식', '디너', '런치', '먹']], [/새 경험/, ['처음', '새로', '도전', '체험']], [/시즌|한정/, ['행사', '페어', '축제', '시즌', '이벤트', '한정']], [/할인/, ['할인', '쿠폰', '프로모션', '혜택', '특가']], [/휴식|회복/, ['휴식', '쉬', '마사지', '스파', '힐링', '여유', '누워']], [/익숙|실제 이용/, ['다시', '재방문', '또', '단골', '이용']], [/아침|조식/, ['조식', '아침', '뷔페']], [/홍보/, ['광고', '홍보', '인스타', 'SNS', '보고']]];
  const factorWords = f => { const out = []; for (const [re, ws] of FACTOR_WORDS) if (re.test(String(f || ''))) out.push(...ws); return out; };
  const factorPhrase = f => { for (const [re, t] of FACTOR) if (re.test(String(f || ''))) return t; return null; };
  const KNUM = ['', '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉', '열'];
  const hoursWord = min => { const h = Math.round(min / 60); if (h < 1 || h > 10) return null; const rem = min - h * 60; return `${KNUM[h]} 시간${rem > 20 ? ' 넘게' : rem < -20 ? ' 가까이' : ''}`; };
  const BLOCK = [[/SERVICE_NOT_OPEN_YET|아직 시작 전|NOT_OPEN/, '아직 문을 열기 전이었습니다'], [/운영 종료.*끝낼 수 없음|ORDER_DEADLINE|LAST_ORDER/, '마감이 가까워 들르기 어려운 시간이었습니다'], [/NO_APPLICABLE_DATED_SERVICE_WINDOW|NO_FITTING|운영 시간|영업시간 밖|운영하지 않음/, '이날 이 시간에는 이용할 수 없었습니다'], [/투숙객 전용|비투숙|퇴실 뒤/, '투숙객 전용이라 이용할 수 없었습니다'], [/방금 식사|조금 전 같은 곳/, '조금 전에 먹은 터라 건너뛰었습니다'], [/오늘 이미 이용/, '오늘 이미 다녀온 곳입니다'], [/성인 전용/, '아이와 함께라 이용할 수 없었습니다']];
  const TRIGGER = { NEAR_TIE: '근소한 점수 차', PRICE_GAP: '후보 간 가격 차 큼', BREAKFAST_FACT: '아침 식사 후기 사실 있음', NO_PERSONAL_BASIS: '개인 근거 없음', OUTSIDE_TOP_BY_PRICE: '가격 항으로 1위가 됨', REPEAT_VENUE: '같은 업장 반복', REPEAT_MENU: '같은 메뉴 반복', COST_ABSTAIN: '비용 때문에 건너뜀' };
  const rawId = l => { const t = String(l || '').trim(); return /^(?:HC[_-]|C01[_-])/.test(t) || /^[A-Z0-9_]{3,}$/.test(t) || /^[a-z0-9]+(_[a-z0-9]+)+$/.test(t); };
  const blockText = r => { for (const [re, t] of BLOCK) if (re.test(String(r || ''))) return t; return null; };
  const isFood = id => /^C01_|MEAL|BUFFET|MYONG|ONDAL|GEUM|MOEGI|PIZZA|^lunch_|BAKERY|DINING|RESTAUR/i.test(String(id || '')) && !/OUTSIDE_MEAL/.test(String(id || ''));
  const isEvent = id => /WINE_FAIR|SANTA|GOLDEN|SAVORING|EVENT/.test(String(id || ''));
  const MEAL = { breakfast: '아침', lunch: '점심', dinner: '저녁' };
  const VENUES = '피자힐|명월관|금룡|온달|모에기|더뷔페|파빌리온|더 파빌리온|르 ?파사쥬|르파사쥬|더글라스';
  // 상품 단위(C01) 후보 이름 — 엔진 menu_connections.py SPECS(v12z)에서 자동 추출(c01_labels_from_engine.json). 제품 이름표가 '다른 활동'으로만 아는 id에 쓴다. 제품 통합 시 C01 공용 상품명 테이블(정본)로 교체
  const C01_LABELS = {"C01_GEUM_SET1": "금룡 주중 특선 SET ①", "C01_GEUM_SET2": "금룡 주중 특선 SET ②", "C01_GEUM_HWARYONG": "금룡 화룡 코스", "C01_GEUM_LONGEVITY": "금룡 만수무강 코스", "C01_GEUM_CHEF": "금룡 진계도 셰프 스페셜", "C01_GEUM_DO": "금룡 도원경 · 도", "C01_GEUM_WON": "금룡 도원경 · 원", "C01_GEUM_KYUNG": "금룡 도원경 · 경", "C01_ONDAL_SURA": "온달 수라상차림", "C01_ONDAL_COURT": "온달 궁중상차림", "C01_MYONG_SPECIAL2": "명월관 스페셜 모둠 · 2인 식사 포함", "C01_MYONG_SPECIAL4": "명월관 모둠 한상", "C01_MYONG_SIRLOIN": "명월관 한우 등심 정식", "C01_MYONG_RIB_SET": "명월관 한우 양념갈비 정식", "C01_GEUM_JAJANG_L": "금룡 삼선 자장면 · 점심", "C01_GEUM_JAJANG_D": "금룡 삼선 자장면 · 저녁", "C01_GEUM_XO_L": "금룡 조리장 특선 볶음밥 (XO) · 점심", "C01_GEUM_XO_D": "금룡 조리장 특선 볶음밥 (XO) · 저녁", "C01_MYONG_TANG_KR": "명월관 한우 갈비탕", "C01_MYONG_TANG_US": "명월관 갈비탕 (미국산)", "C01_PIZZA_VONGOLE": "피자힐 봉골레 파스타", "C01_MYONG_GRILL_RIB": "명월관 양념갈비", "C01_MYONG_GRILL_RIB_SP": "명월관 특 양념갈비", "C01_MYONG_GRILL_MIX": "명월관 한우 모둠 주물럭", "C01_MYONG_GRILL_SIRLOIN": "명월관 생등심", "C01_MYONG_GRILL_SHORTRIB": "명월관 생갈비", "C01_ONDAL_ABALONE": "온달 반상 · 전복 돌솥비빔밥", "C01_ONDAL_SPICY_SOUP": "온달 반상 · 온달 육개장", "C01_ONDAL_BEEF_SOUP": "온달 반상 · 한우 도가니 곰탕", "C01_ONDAL_BULGOGI": "온달 반상 · 한우 불고기", "C01_ONDAL_HAIRTAIL_STEW": "온달 반상 · 제주 갈치조림", "C01_ONDAL_HAIRTAIL_GRILL": "온달 반상 · 제주 갈치구이"};
  const LABELS = Object.assign({}, C01_LABELS);
  Object.assign(LABELS, {"unpack":"객실 짐 정리 · 휴식","room_rest":"객실 휴식","room_nap":"객실에서 아이와 휴식","room_bath":"객실 욕조에서 휴식","room_snack":"객실에서 간단히 먹기","pool":"수영장 이용","sauna":"사우나 · 피트니스","fitness":"피트니스","footbath":"스카이야드 족욕","night_footbath":"스카이야드 야경 족욕","forest_walk":"포레스트 파크 산책","garden_walk":"더글라스 가든 산책","riverpark":"리버파크 산책","tennez":"테네즈 파크 둘러보기","cafe":"더 파빌리온에서 커피 · 디저트","bakery":"르 파사쥬에서 빵 · 음료","lounge":"클럽 라운지 이용","library":"라이브러리에서 책 · 음악","theatre":"빛의 시어터 관람","lunch_ondal":"온달에서 점심","lunch_geumryong":"금룡에서 점심","lunch_myongwol":"명월관에서 점심","lunch_moegi":"모에기에서 점심","lunch_pizzahill":"피자힐에서 점심","lunch_bakery":"르 파사쥬 빵 · 샌드위치로 점심","lunch_cafe":"카페에서 가볍게 점심","lunch_room":"객실에서 간단히 점심","lunch_skip":"점심 건너뛰기 · 늦은 간식","lunch_outside":"호텔 밖에서 점심","luxbar":"럭스바에서 한잔","night_walk":"저녁 산책 · 야경","room_night":"객실 복귀 · 휴식","checkin":"체크인","checkout":"체크아웃","wake":"기상 · 준비","pack":"짐 정리","arrive":"호텔 도착","leave":"귀가","sleep":"취침","ROOM_REST":"객실에서 쉬기","ROOM_MEAL":"룸서비스","OUTSIDE_MEAL":"배달 · 편의점 식사","WINE_FAIR":"와인페어","SKYARD":"스카이야드 족욕","SKYARD_NIGHT":"스카이야드 야경 족욕","PIZZA_HILL":"피자힐","THE_BUFFET":"더뷔페","MOEGI":"모에기","POOL":"실내 수영장","SAUNA":"사우나","FOREST_WALK":"포레스트 파크 산책","SIMPLE_MEAL_VIEW":"르파사쥬 빵 · 간단히","MYONGWOLGWAN":"명월관","ONDAL":"온달","GEUMRYONG":"금룡","MOEGI_MIYABI":"모에기 미야비 코스","MOEGI_MOMIJI":"모에기 모미지 코스"}, { GRAND_ROOM: '그랜드 워커힐 객실', VISTA_ROOM: '비스타 워커힐 객실', DOUGLAS_ROOM: '더글라스 하우스 객실', HOTEL_GATE: '호텔 입구', GRAND_LOBBY: '그랜드 워커힐 로비' });
  const GENERIC = new Set(['다른 활동', '기타', '']);
  function nameOf(id, opts, extra) {
    const a = opts && opts.label ? opts.label(id) : null;
    if (a && !GENERIC.has(a) && a !== id) return a;
    return LABELS[id] || (extra && extra[id]) || a || id;
  }
  const FOOD_PLACE = {PIZZA_HILL:'피자힐',THE_BUFFET:'더뷔페',MOEGI:'모에기',GEUMRYONG:'금룡',MYONGWOLGWAN:'명월관',ONDAL:'온달',LE_PASSAGE:'르 파사쥬',THE_PAVILION:'더 파빌리온',LUX_BAR:'럭스바'};
  function narrativeScene(source) {
    let label=clean(source.label).replace(/\s*·\s*(규격 미정|이용료 가정|무료 대상 투숙객|그 외 투숙객)/g,'');
    if(source.meal==='breakfast'&&source.loc==='THE_BUFFET'&&/조식.*뷔페/.test(label))label='더뷔페 조식 뷔페';
    else if(source.act==='theatre')label='빛의 시어터 관람';
    else if(source.loc==='SKYARD'&&source.consume)label='스카이야드 족욕';
    else if(source.act==='hc_golf')label='실내 골프 연습';
    else if(source.consume&&FOOD_PLACE[source.loc]&&!venueOf(label))label=FOOD_PLACE[source.loc]+' '+label;
    return {...source,label}; // Display view only; raw scenes and ledger remain immutable.
  }
  function sceneList(plan) { return (plan && plan.scenes || []).map((s, i) => ({ s:narrativeScene(s), i })); }
  function decisionOf(plan, s) {
    const decisions=plan?.m4?.decisions||[],ids=s.basis?.m4?.decision_packet_ids||[];
    const linked=decisions.filter(d=>d.packet&&ids.includes(d.packet.packet_sha256));
    const actual=linked.filter(d=>d.execution_status==='EXECUTED'&&(!s.visit_date||d.packet.context_factors?.date===s.visit_date)&&(!s.basis?.m4?.event_id||d.actual_next_event_id===s.basis.m4.event_id));
    if(actual.length===1)return actual[0];
    if(actual.length>1)return null;
    const info=linked.filter(d=>d.execution_status==='INFO_CHECK_NOT_ATTENDANCE');
    if(info.length===1&&linked.length===1)return info[0];
    // A discarded proposal is not the actual decision, even when its packet is linked.
    // Legacy single packets without execution metadata remain auditable, not verified.
    if(linked.length===1&&!linked[0].execution_status)return linked[0];
    // Legacy scenes sometimes omit the packet join. Resolve only an exact,
    // unique executed event in this customer's plan; never nearest-time matching.
    const final=s.basis?.charge?.sku_contract?.final_candidate_id||s.basis?.review?.actual_candidate_id||s.act;
    const events=(plan?.m4?.activity_history||[]).filter(e=>e.date===s.visit_date&&e.start===hm(s.t0)&&e.location_id===s.loc&&e.action_id===final);
    if(events.length!==1)return null;
    const matches=decisions.filter(d=>d.execution_status==='EXECUTED'&&d.actual_next_event_id===events[0].event_id&&d.selected_action===events[0].action_id&&d.packet?.context_factors?.date===s.visit_date);
    return matches.length===1?matches[0]:null;
  }
  function sameDay(a, b) { return (a.visit_date || a.visit_day) === (b.visit_date || b.visit_day); }
  const foodScene = s => !!(s && (s.meal || /^(lunch_|turn_(breakfast|dinner|lunch)|ROOM_MEAL|OUTSIDE_MEAL)$/.test(s.act)));
  const venueOf = l => { const m = noParen(l).match(new RegExp('^(' + VENUES + ')')); return m ? m[1].replace(/\s+/g, '') : null; };
  const shortName = l => { let t = noParen(l).split(/\s*·\s*/)[0]; if (/에서/.test(t)) t = t.split('에서')[0]; return t.replace(/\s*(관람|이용)$/, '').trim(); };
  const longest = t => String(t || '').split(/\s+/).filter(w => w.length >= 2).sort((a, b) => b.length - a.length)[0] || String(t || '');
  const polite = t => String(t || '').trim().replace(/(있|없|했|됐|갔|왔|겼|냈|렸|였|았|었|같|싶)다\.$/, '$1습니다.').replace(/이다\.$/, '입니다.').replace(/한다\.$/, '합니다.').replace(/된다\.$/, '됩니다.').replace(/본다\.$/, '봅니다.').replace(/낮다\.$/, '낮습니다.').replace(/높다\.$/, '높습니다.').replace(/많다\.$/, '많습니다.').replace(/크다\.$/, '큽니다.').replace(/작다\.$/, '작습니다.').replace(/[가-힣]다\.$/, m => m);
  const hasPrice = t => /\d[\d,]*\s*(만\s*)?원|\d+\s*%|천\s*원/.test(String(t || ''));
  // 활동별 연관어 — 후기 요지가 이 활동과 이어질 때만 카드에 인용한다(정밀 근거에는 모두 남는다)
  const RELATED = [[/족욕|스카이야드/, ['족욕', '스카이야드', '야경', '한강']], [/수영/, ['수영', '풀', '물놀이']], [/사우나|피트니스|운동/, ['사우나', '피트니스', '운동', '헬스']], [/시어터|관람|전시/, ['시어터', '전시', '관람', '공연', '미디어']], [/산책|가든|파크|둘러보기/, ['산책', '정원', '가든', '걷', '파크', '공원']], [/라이브러리/, ['라이브러리', '책', '음악']], [/조식|아침|뷔페|라이트/, ['조식', '아침', '뷔페', '라운지']], [/피자힐|피자|파스타/, ['피자', '파스타', '피자힐']], [/명월관|갈비|등심|주물럭|한우/, ['갈비', '고기', '한우', '구이', '명월관', 'BBQ', '바비큐']], [/금룡|자장|볶음밥|코스/, ['중식', '자장', '면', '금룡', '중국']], [/온달|육개장|반상|정찬/, ['한식', '국', '온달', '정찬', '국밥']], [/모에기|우동/, ['일식', '우동', '모에기']], [/룸서비스|객실에서/, ['룸서비스', '객실에서', '앱으로', '배달', '포장']], [/배달|편의점|호텔 밖/, ['배달', '편의점', '밖']], [/럭스바|한잔|바$/, ['바', '칵테일', '와인', '술', '맥주', '위스키']], [/커피|디저트|아메리카노|빵|음료|카페|베이커리|파사쥬|파빌리온/, ['커피', '빵', '디저트', '카페', '아메리카노', '베이커리', '케이크']], [/와인페어|행사|페어/, ['와인', '행사', '페어', '축제']], [/휴식|쉬기|욕조|낮잠/, ['휴식', '쉬', '객실', '반신욕', '누워', '낮잠', '잠']]];
  const relatedWords = label => { const l = noParen(label); const out = []; for (const [re, ws] of RELATED) if (re.test(l)) out.push(...ws); return out.length ? out : shortName(l).split(/\s+/).filter(w => w.length >= 2); };
  const mealOf = s => s.meal || (/breakfast|조식|아침/.test(s.act + (s.label || '')) ? 'breakfast' : /lunch|점심/.test(s.act + (s.label || '')) ? 'lunch' : /dinner|저녁/.test(s.act + (s.label || '')) ? 'dinner' : null);

  // 정규화 입력 — 이 객체에 있는 값만 문장 · 정밀 근거에 쓴다
  function input(flowResult, pid, index, opts = {}) {
    const plan = flowResult.plans[pid], s = narrativeScene(plan.scenes[index]), list = sceneList(plan);
    const prev = list.slice(0, index).reverse().find(x => !SKIP.has(x.s.act) && sameDay(x.s, s));
    const nexts = list.slice(index + 1).filter(x => !SKIP.has(x.s.act) && sameDay(x.s, s) && x.s.t0 >= s.t1).slice(0, 2);
    const d = decisionOf(plan, s), b = s.basis || {};
    const extra = {}; for (const x of list) { const sb = x.s.basis || {}; if (sb.charge && sb.charge.sku_contract) extra[sb.charge.sku_contract.sku_id] = sb.charge.sku_contract.label; const rv0 = sb.review; if (rv0) { if (rv0.rule_label) extra[rv0.rule_choice] = rv0.rule_label; if (rv0.final_label) extra[rv0.final] = rv0.final_label; } }
    if (d) for (const c of (d.packet.candidates || [])) { if (c.candidate_label) extra[c.candidate_id] = c.candidate_label; }
    const cands = d ? (d.packet.candidates || []).map(c => ({ id: c.candidate_id, label: nameOf(c.candidate_id, opts, extra), allowed: c.world_allowed !== false, block: c.block_reason || null, score: c.final_with_lookahead != null ? c.final_with_lookahead : c.final_score, prob: d.sampling && d.sampling.probabilities ? d.sampling.probabilities[c.candidate_id] : null, price_pp: c.price_pp_krw != null ? c.price_pp_krw : null })) : [];
    const excluded = d ? (d.packet.world_excluded_candidates || []).map(x => ({ id: x.candidate_id, label: nameOf(x.candidate_id, opts, extra), reason: x.reason })) : [];
    const review = b.review || null;
    // 후기 사실의 '역할' — 실제로 이 선택에 작용한 것만 카드에 쓴다. direct: 장면 근거에 '후기에서 확인'으로 기록 / score_term: 선택된 후보의 점수 항에 연결(기여값 있음) / llm_cited: LLM 검토가 인용 / basis: 장면에 연결만 된 사실(점수 기여 아님)
    const facts = [], factOf = id => { let f = facts.find(y => y.id === id); if (!f) { f = { id, gist: opts.gist ? opts.gist(id) : null, roles: [], factor: null, value: 0, ext: null }; facts.push(f); } return f; };
    const ext = {}; for (const e of (b.evidence || [])) { for (const k in (e.ext_reasons || {})) ext[k] = e.ext_reasons[k]; if (e.type === '후기에서 확인') for (const id of (e.fact_ids || [])) factOf(id).roles.push('direct'); }
    for (const id of (b.facts || [])) { const f = factOf(id); if (!f.roles.length) f.roles.push('basis'); }
    const selRow = d ? (d.packet.candidates || []).find(c => c.candidate_id === d.selected_action) : null;
    // 성향 기여: 같은 상태에서 그 성향을 중립값으로 바꿨을 때 이 후보 가중치가 낮아지는(=성향이 끌어올린) 경우만 '개인적 이유' 로 쓴다
    const marg = selRow && selRow.profile_feature_marginals ? Object.entries(selRow.profile_feature_marginals).map(([k, v]) => ({ key: k.split('.').pop(), delta: v && v.weight_delta_at_fixed_state, value: v && v.value, neutral: v && v.neutral_reference })) : null;
    const posTraits = marg ? marg.filter(m => typeof m.delta === 'number' && m.delta > 1e-6).sort((a, b) => b.delta - a.delta).map(m => m.key) : null;
    const allTerms = selRow ? (selRow.terms || []).slice() : [];
    const terms = allTerms.filter(t => (t.value || 0) > 0.1 && (t.fact_ids || []).length).sort((a, b) => b.value - a.value);
    for (const t of terms) for (const id of t.fact_ids) { const f = factOf(id); f.roles.push('score_term'); if ((t.value || 0) > f.value) { f.value = t.value; f.factor = t.factor; } }
    if (review) for (const r of (review.reasons || [])) for (const id of (r.fact_ids || [])) factOf(id).roles.push('llm_cited');
    for (const f of facts) { f.ext = ext[f.id] || null; f.roles = [...new Set(f.roles)]; f.contrib = f.roles.includes('direct') || f.roles.includes('llm_cited') || (f.roles.includes('score_term') && f.value > 0.1); }
    facts.sort((a, b) => (b.roles.includes('llm_cited') - a.roles.includes('llm_cited')) || (b.roles.includes('direct') - a.roles.includes('direct')) || (b.value - a.value));
    // A mixed profile/offer term can be entirely a common food/space baseline.
    // Without a source Fact or measured marginal it cannot establish a personal preference.
    const traitTerms = [];
    const lookahead = allTerms.map(t => ({ t, m: /^이어지는 다음 일정\(내다보기\)\s*[—-]\s*(.+)$/.exec(t.factor || '') })).filter(z => z.m && (z.t.value || 0) > 0.8).map(z => ({ label: clean(z.m[1]), value: z.t.value }))[0] || null;
    const cf = d ? (d.packet.context_factors || {}) : {};
    const ctx = d ? { time: cf.time, msme: cf.minutes_since_meal_end, fatigue: cf.fatigue_proxy, lastMeal: cf.last_meal || null, companions: cf.companions || null, activities: cf.activities || [] } : null;
    // 식사 이력(이전 날 포함) — LLM이 '반복'을 이유로 바꾼 장면에서 실제 전 식사를 가리키는 데 쓴다
    const mealHistory = list.slice(0, index).filter(x => foodScene(x.s) && !/건너/.test(x.s.label || '')).map(x => ({ scene: x.s, venue: venueOf(x.s.label), label: clean(x.s.label), meal: mealOf(x.s), sameDay: sameDay(x.s, s) }));
    // 같은 곳을 이번 체류에서 이미 이용한 기록(연속성) — 같은 act 또는 같은 업장
    const selV = venueOf(s.label), priorSame = list.slice(0, index).filter(x => !SKIP.has(x.s.act) && x.s !== s && ((x.s.act === s.act && !OBLIGATION.has(s.act) && !/^(room_rest|ROOM_REST|room_night|idle)$/.test(s.act)) || (selV && venueOf(x.s.label) === selV))).map(x => ({ scene: x.s, sameDay: sameDay(x.s, s) }));
    const considered = ((b.choice && b.choice.considered) || []).map(c => ({ label: clean(c.label), note: c.note || '' }));
    // Breakfast uses a separate native turn scorer. Read its actual per-customer
    // result rather than claiming a missing M4 packet is a missing decision.
    const executed=(plan.m4?.activity_history||[]).filter(e=>e.event_id===b.m4?.event_id&&e.date===s.visit_date&&e.start===hm(s.t0)&&e.location_id===s.loc);
    const turnProduct=b.charge?.sku_contract?.final_candidate_id||b.review?.actual_candidate_id||(executed.length===1?executed[0].action_id:s.act);
    const turnMatches=(flowResult.runs||[]).filter(r=>r.visit_date===s.visit_date&&(r.visit_day||1)===(s.visit_day||1)&&r.turn===(s.turn||s.meal)).flatMap(r=>(r.customers||[]).filter(c=>c.persona_id===pid&&c.decided_at===hm(s.t0)&&c.choice?.product_id===turnProduct&&c.choice?.map_loc===s.loc));
    const turnDecision=turnMatches.length===1?turnMatches[0]:null;
    return { pid, index, turnDecision, executionEvent:executed.length===1?executed[0]:null, linkedDecisions:(plan.m4?.decisions||[]).filter(d=>(b.m4?.decision_packet_ids||[]).includes(d.packet?.packet_sha256)), scene: s, prev: prev && prev.s, nexts: nexts.map(x => x.s), decision: d, cands, rawCands: d ? (d.packet.candidates || []) : [], excluded, choice: b.choice || null, considered, traits: b.traits || [], posTraits, marginals: marg, facts, traitTerms, lookahead, ctx, priorSame, charge: b.charge || null, review, visit: opts.visit || null, ledgerRows: opts.rows || [], sampling: d && d.sampling ? d.sampling.mode : null, selectedId: d ? d.selected_action : null, mealHistory, name: id => nameOf(id, opts, extra), place: id => (opts.place && opts.place(id)) || nameOf(id, opts, extra), gistOf: id => (opts.gist && opts.gist(id)) || null };
  }

  // ---------- 고객 흐름 카드: 2~3문장 이야기 ----------
  const partyWords = v => { const n = (v && v.party_size) || 1, rel = (v && v.rel) || ''; if (n <= 1) return ['혼자', '혼자서']; if (/kid|child/.test(rel)) return ['아이와 함께', '가족이']; if (/parent|family/.test(rel)) return ['가족이', '가족과 함께']; if (/couple/.test(rel) && n === 2) return ['둘이서', '두 사람이']; const cnt = { 3: '셋이서', 4: '넷이서', 5: '다섯이서' }[n] || `${n}명이`; if (/friend/.test(rel)) return ['친구들과', n === 2 ? '둘이서' : cnt]; return n === 2 ? ['둘이서', '두 사람이'] : [cnt, '일행이']; };
  const timeWord = t => { const h = t / 60; if (h < 10.5) return '아침'; if (h < 13.5) return '점심 무렵'; if (h < 17) return '오후'; if (h < 20) return '저녁 무렵'; return '밤'; };
  const nextShort = n => { if (!n) return null; if (n.meal && MEAL[n.meal]) return MEAL[n.meal]; if (/turn_event|WINE_FAIR/.test(n.act)) return noParen(n.label).split(/\s*·\s*/)[0]; return null; };
  function foodPhrase(label, meal, pick) {
    const l = noParen(label), v = venueOf(l), menu = v ? l.replace(new RegExp('^(' + VENUES + ')\\s*'), '').replace(/\s*·\s*(점심|저녁|아침)\s*$/, '').replace(/\s*·\s*/g, ' · ').trim() : '';
    const M = MEAL[meal] || '식사';
    if (/건너|거르/.test(l)) return meal === 'breakfast' ? '아침은 거르고 객실에서 쉽니다' : `${M}은 거릅니다`;
    if (/룸서비스|객실에서 식사|객실에서 간단히/.test(l)) return pick([`${M}은 객실로 룸서비스를 불러 해결합니다`, `${M}은 밖에 나가지 않고 객실에서 먹습니다`]);
    if (/배달|편의점|호텔 밖/.test(l)) return `${M}은 호텔 밖 음식으로 간단히 때웁니다`;
    if (/조식 뷔페|더뷔페/.test(l) && meal === 'breakfast') return pick(['아침은 더뷔페 조식 뷔페에서 먹습니다', '아침 식사는 더뷔페 조식 뷔페입니다']);
    if (/라이트 조식|더글라스/.test(l) && meal === 'breakfast') return '아침은 더글라스 라이트 조식으로 시작합니다';
    if (v && menu && /빵|샌드위치|커피|브런치/.test(menu)) { const mn = menu.replace(/\s*(으)?로\s*(가볍게\s*)?(점심|아침|저녁)$/, '').replace(/\s*\+\s*/g, ' + '); return pick([`${M}은 ${v}에서 ${mn}${josa(mn, '으로', '로')} 가볍게 합니다`, `${v}에 들러 ${mn}${josa(mn, '으로', '로')} ${M}을 대신합니다`]); }
    if (v && menu && !/점심|저녁|아침/.test(menu)) return pick([`${M}은 ${v}에서 ${menu}${josa(menu, '을', '를')} 먹습니다`, `${M} 때가 되어 ${v}${josa(v, '으로', '로')} 가 ${menu}${josa(menu, '을', '를')} 주문합니다`, `${v}에 자리를 잡고 ${menu}${josa(menu, '으로', '로')} ${M}을 합니다`]);
    if (v) return pick([`${M}은 ${v}에서 먹습니다`, `${M} 때가 되어 ${v}${josa(v, '으로', '로')} 갑니다`]);
    return `${M}은 ${l}${josa(l, '으로', '로')} 합니다`;
  }
  function actPhrase(x, pick) {
    const s = x.scene, label = clean(s.label), l = noParen(label), act = s.act;
    if (OBLIGATION.has(act)) {
      const beforeCheckin = x.nexts.some(n => n.act === 'checkin');
      return ({ arrive: beforeCheckin ? '호텔에 도착했지만 체크인까지는 시간이 조금 남아 있습니다' : '호텔에 도착합니다', checkin: '체크인을 마칩니다', unpack: pick(['객실에 들어가 짐을 풀고 잠시 숨을 돌립니다', '객실에 짐을 두고 한숨 돌립니다']), wake: '일어나 하루를 준비합니다', pack: '짐을 챙깁니다', checkout: x.nexts.length ? '체크아웃을 하고도 바로 떠나지는 않습니다' : '체크아웃합니다', leave: '호텔을 나섭니다', sleep: '객실로 돌아가 하루를 마칩니다' })[act] || `${label}${josa(label, '을', '를')} 합니다`;
    }
    if (act === 'wait') return '다음 일정이 시작되기를 기다립니다';
    if (act === 'hc_golf') return '실내 골프 연습장을 이용합니다';
    if (act === 'theatre') return '빛의 시어터를 관람합니다';
    if (/^(footbath|night_footbath)$/.test(act)) return act === 'night_footbath' ? '스카이야드에서 야경을 보며 족욕을 합니다' : '스카이야드에서 족욕을 합니다';
    if (act === 'pool') return '실내 수영장에서 수영합니다';
    if (foodScene(s)) return foodPhrase(label, mealOf(s), pick);
    if (s.consume && FOOD_PLACE[s.loc]) { const venue=FOOD_PLACE[s.loc],menu=label.startsWith(venue)?label.slice(venue.length).trim():label; return `${venue}에서 ${menu}${josa(menu,'을','를')} 주문합니다`; }
    if(s.consume && /^룸서비스/.test(label))return `${label}${josa(label,'을','를')} 주문합니다`;
    if (act === 'lunch_skip' || /건너뛰기/.test(label)) return '점심은 따로 먹지 않고 지나갑니다';
    if (act === 'room_bath') return pick(['객실 욕조에 몸을 담그고 쉽니다', '객실로 돌아와 욕조에 몸을 녹입니다']);
    if (act === 'room_nap') return x.ctx?.companions?.kids ? '객실에서 아이와 함께 낮잠을 잡니다' : '객실에서 낮잠을 잡니다';
    const ns = nextShort(x.nexts[0]), soon = x.nexts[0] && (x.nexts[0].t0 - s.t1) <= 150;
    if (/^(room_rest|ROOM_REST|idle|room_night)$/.test(act)) return ns && soon ? pick([`${ns} 전까지 객실에서 쉬어 갑니다`, `객실로 돌아와 ${ns}까지 한숨 돌립니다`]) : pick(['객실로 돌아와 쉽니다', '객실에서 한숨 돌립니다', '객실에서 쉬어 갑니다']);
    if (/turn_event|WINE_FAIR/.test(act) || /와인페어|행사/.test(l)) { const ev = l.split(/\s*·\s*/)[0]; return pick([`마침 열리고 있는 ${ev}에 들릅니다`, `${ev}${josa(ev, '을', '를')} 보러 갑니다`]); }
    if (/족욕/.test(l)) return /야경|밤/.test(l) ? pick(['스카이야드로 올라가 야경을 보며 족욕을 합니다', '밤 스카이야드에서 족욕으로 하루를 식힙니다']) : pick(['스카이야드로 올라가 족욕을 합니다', '스카이야드 족욕으로 잠시 쉬어 갑니다']);
    if (/시어터|관람/.test(l)) { const t = l.replace(/\s*관람$/, ''); return pick([`${t}${josa(t, '을', '를')} 보러 갑니다`, `${t} 관람에 나섭니다`]); }
    if (/한잔/.test(l)) return `${l.replace(/에서 한잔$/, '')}에서 한잔합니다`;
    if (/수영장/.test(l)) return pick(['수영장에 갑니다', '수영장에서 몸을 풉니다']);
    if (/사우나|피트니스/.test(l)) return pick([`${l}${josa(l, '으로', '로')} 향합니다`, `${l}에서 몸을 풉니다`]);
    if (/라이브러리/.test(l)) return pick(['라이브러리에서 책과 음악으로 시간을 보냅니다', '라이브러리에 들러 조용히 시간을 보냅니다']);
    if (/산책|둘러보기/.test(l)) { const p = l.replace(/\s*(산책|둘러보기)$/, ''); return pick([`${p}${josa(p, '을', '를')} 걷습니다`, `${p} 산책에 나섭니다`]); }
    if (/라운지/.test(l)) return '라운지에서 시간을 보냅니다';
    if (/커피|디저트|아메리카노|라떼|빵|음료/.test(l)) { const v = venueOf(l) || l.split(/에서|\s/)[0]; const rest = l.replace(new RegExp('^(' + VENUES + ')(에서)?\\s*'), '').replace(/^더\s*/, ''); return rest ? pick([`${v}에 들러 ${rest}${josa(rest, '으로', '로')} 쉬어 갑니다`, `${v}에서 ${rest}${josa(rest, '을', '를')} 곁들여 잠시 쉽니다`]) : `${v}에 들릅니다`; }
    return pick([`${l}${josa(l, '을', '를')} 합니다`, `${l}${josa(l, '으로', '로')} 시간을 보냅니다`]);
  }
  function leadPhrase(x, pick) {
    const s = x.scene, p = x.prev; if (!p || OBLIGATION.has(s.act)) return '';
    const pl = noParen(p.label), beforeCheckin = x.nexts.some(n => n.act === 'checkin');
    if (beforeCheckin && p.act === 'arrive') return pick(['체크인까지 시간이 남아', '체크인 전에 비는 시간이 있어']);
    if (p.act === 'unpack') return pick(['짐을 풀고 나서', '객실에 짐을 두고 나와']);
    if (p.act === 'checkin') return '체크인을 마치고';
    if (p.act === 'checkout') return '체크아웃을 마친 뒤';
    if (p.act === 'wake') return mealOf(s) === 'breakfast' ? pick(['일어나자마자', '']) : pick(['일어나자마자', '아침에 일어나']);
    if (OBLIGATION.has(p.act)) return '';
    if (foodScene(p) && /건너|거르/.test(pl)) { const m = MEAL[mealOf(p)] || '식사'; return pick([`${m}은 거른 채`, '']); }
    if (foodScene(p)) { const m = MEAL[mealOf(p)] || '식사'; const v = venueOf(pl); return pick([`${v ? v + '에서 ' : ''}${m}을 마치고`, `${m}을 먹고 나서`, `${m} 뒤에`]); }
    if (/라이브러리/.test(pl)) return pick(['라이브러리에서 나와', '책을 덮고 나와']);
    if (/커피|디저트|빵|음료|카페|아메리카노/.test(pl)) { const v = venueOf(pl); return v ? `${v}에서 나와` : '카페에서 나와'; }
    if (/라운지/.test(pl)) return '라운지에서 나와';
    if (/족욕/.test(pl)) return pick(['족욕을 마치고', '스카이야드에서 내려와']);
    if (/시어터|관람/.test(pl)) return pick(['관람을 마친 뒤', '전시를 보고 나와']);
    if (/와인페어|행사/.test(pl)) return pick([`${pl.split(/\s*·\s*/)[0]}에서 나와`, '행사장을 둘러본 뒤']);
    if (/휴식|쉬기/.test(pl)) { const tw = timeWord(s.t0); return pick(['객실에서 쉬다가', '한숨 돌린 뒤', `${tw}${josa(tw, '이', '가')} 되자`]); }
    if (/수영장|사우나|피트니스/.test(pl)) return pick([`${pl.replace(/\s*이용$/, '')}에서 나와`, '몸을 풀고 나서']);
    if (/산책/.test(pl)) return '산책을 마치고';
    { const sn = shortName(pl); return pick([`${sn}${josa(sn, '을', '를')} 마치고`, `${sn} 뒤에는`]); }
  }
  function compose(x) {
    const s = x.scene, out = [], used = { facts: [], traits: [], alternatives: [], review: false, next: null };
    const h = hash(x.pid + '|' + (s.visit_date || s.visit_day) + '|' + s.act + '|' + s.t0);
    const pick = arr => arr[h % arr.length], pick2 = arr => arr[(h >>> 3) % arr.length], pick3 = arr => arr[(h >>> 6) % arr.length];
    const party = partyWords(x.visit), lead = leadPhrase(x, pick2), act = actPhrase(x, pick);
    const duty = OBLIGATION.has(s.act);
    const adopted0 = !!(x.review && /ADOPTED/.test(x.review.decided_by || x.review.outcome || ''));
    const sel = x.cands.find(c => c.id === x.selectedId), sampled = !!(x.sampling && sel && sel.prob != null), weak = sampled && sel.prob < 0.5 && !adopted0;
    const subj = duty || /^(아침|점심|저녁)/.test(act) ? '' : (h % 3 === 0 ? party[0] + ' ' : (h % 3 === 1 && !/^혼자/.test(party[1]) ? party[1] + ' ' : ''));
    out.push(`${lead ? lead + ' ' : ''}${subj}${act}.`.replace(/\s+/g, ' ').trim());
    if (x.nexts[0] && /전까지|까지 한숨/.test(out[0])) used.next = clean(x.nexts[0].label);
    // 개인적 이유 — 기록에 있는 것만. 추첨으로 정해진 약한 선택(사후 확률 50% 미만)은 선호 때문이라고 쓰지 않는다
    const adopted = x.review && /ADOPTED/.test(x.review.decided_by || x.review.outcome || '');
    if (adopted) {
      const rv = x.review, rs = (rv.reasons || []).filter(r => r.text), rule = clean(rv.rule_label || rv.rule_choice), rvV = venueOf(rule), finV = venueOf(s.label);
      const repeat = (rv.triggers || []).some(t => /REPEAT/.test(t)) || rs.some(r => /전날|어제|같은 업장|같은 메뉴|반복/.test(r.text)), hist = repeat && rvV ? x.mealHistory.slice().reverse().find(m => m.venue === rvV) : null;
      const review = rs.find(r => r.type === '후기 근거'), situ = rs.find(r => r.type !== '후기 근거');
      const say = t => polite(firstSentence(t, 130));
      const analytic = t => /근거|확인[되됩]|뒷받침|시사|판단|패턴|자연스럽|해석|가능하더라도|보기는 어렵|확대하지|일반적인|선호는|무리 없|배제되|증거|전환한 경험|보긴 어렵|보기 어렵|상황입니다/.test(firstSentence(t, 130));
      const priceTrig = (rv.triggers || []).some(t => /PRICE|COST/.test(t));
      const finLabel = /배달|편의점|호텔 밖/.test(s.label) ? '호텔 밖 음식' : /룸서비스|객실에서/.test(s.label) ? '룸서비스' : shortName(s.label);
      const other = /룸서비스|호텔 밖 음식/.test(finLabel) ? `${finLabel}${josa(finLabel, '으로', '로')} 했습니다` : finV && finV !== rvV ? '다른 곳으로 정했습니다' : '다른 메뉴로 정했습니다';
      if (hist) {
        const when = hist.sameDay ? `${MEAL[hist.meal] || '아까'}에` : `전날 ${MEAL[hist.meal] || '식사'}에`, menu = noParen(hist.label).replace(new RegExp('^(' + VENUES + ')\\s*'), '');
        out.push(`${when} 이미 ${hist.venue}에서 ${menu ? menu + josa(menu, '을', '를') : ''} 먹었던 터라, 오늘은 ${other}.`.replace(/\s+/g, ' '));
        if (review && !hasPrice(review.text) && !analytic(review.text)) out.push(say(review.text));
      } else if (repeat && rvV) {
        const st = situ ? situ.text : '', when = /전날|어제/.test(st) ? '전날에 이미' : /오늘|아까|조금 전/.test(st) ? '오늘 이미' : '이번 체류에서 이미', menu = (rv.triggers || []).includes('REPEAT_MENU') ? noParen(rule).replace(new RegExp('^(' + VENUES + ')\\s*'), '') : '';
        out.push(menu ? `${when} ${rvV}에서 ${menu}${josa(menu, '을', '를')} 먹었던 터라, 오늘은 ${other}.` : `${when} ${rvV}에 다녀온 터라, 오늘은 ${other}.`);
        if (review && !hasPrice(review.text) && !analytic(review.text)) out.push(say(review.text));
      } else {
        const okR = review && !hasPrice(firstSentence(review.text, 130)) && !analytic(review.text) ? review : null, okS = situ && !hasPrice(firstSentence(situ.text, 130)) && !analytic(situ.text) ? situ : null;
        if (okR) out.push(say(okR.text));
        if (okS && out.length < 3) out.push(polite(firstSentence(okS.text, 110)));
      }
      used.review = true; used.facts = rs.flatMap(r => r.fact_ids || []);
    } else if (!duty) {
      // (a) 실제로 기여한 개인 후기 — 역할이 direct(후기에서 확인) · score_term(점수 기여) 인 사실만. 요지에 상품 단어가 있다는 이유로는 인용하지 않는다
      const isRest = /^(room_rest|ROOM_REST|room_night|idle|room_bath|room_nap)$/.test(s.act);
      const kw = relatedWords(s.label);
      const sentences = g => String(g || '').replace(/\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일\s*/g, '').split(/(?<=다|요|음|함)\.\s*|(?<=[^.])\.\s+/).map(t => t.trim()).filter(t => t && !hasPrice(t) && (t.match(/,/g) || []).length < 3 && t.length <= 90 && t.length >= 8);
      // 인용문은 이 활동(kw) 또는 그 점수 항(fw)과 이어지는 문장일 때만. 이어지지 않으면 인용 없이 성향 표현만 쓴다
      const quoteOf = f => { const ss = sentences(f.gist); if (!ss.length) return null; const fw = factorWords(f.factor); return ss.find(t => kw.some(w => t.includes(w))) || ss.find(t => fw.some(w => t.includes(w))) || null; };
      const contrib = x.facts.filter(f => f.contrib && !f.roles.includes('llm_cited') && !/화면에서 제외|요지 미확인|비공개/.test(f.gist || ''));
      const score = f => (f.roles.includes('direct') ? 4 : 0) + (sentences(f.gist).some(t => kw.some(w => t.includes(w))) ? 2 : 0) + (quoteOf(f) ? 1 : 0) + Math.min(f.value || 0, 0.9) / 10;
      contrib.sort((a, b) => score(b) - score(a));
      const f = contrib[0], fp = f ? factorPhrase(f.factor) : null, gq = f ? quoteOf(f) : null;
      const revisit = !foodScene(s) && x.priorSame.length > 0;   // 이번 체류에서 이미 같은 활동을 한 경우 — 같은 후기를 다시 인용하지 않고 연속성 문장으로 잇는다
      if (f && !isRest && !revisit) {
        const g = gq ? gq.replace(/[.。]$/, '').replace(/(이?라)?고\s*(적었|썼|말했|남겼|했)다$/, '') : null;
        const direct = f.roles.includes('direct') || (g && kw.some(w => g.includes(w)));
        if (g && direct && !weak) out.push(`후기에서 추출한 경험 요약: ${g}.`);
        else if (fp && !weak) out.push(pick3([`후기 기록으로 보면 ${fp} 고객입니다.`, `후기 전반에서 ${fp} 쪽이 드러나는 고객입니다.`]));
        if (out.length > 1) used.facts = [f.id];
      } else if (!isRest && !weak && !revisit && x.traitTerms.length) {
        const fp2 = factorPhrase(x.traitTerms[0].factor); if (fp2) { out.push(`후기 전반으로 보면 ${fp2} 고객입니다.`); used.traits = [x.traitTerms[0].factor]; }
      }
    }
    // 대안 · 상태 · 연속성 — 기록에 있고 뜻이 있는 경우에만. 점수 · 확률은 쓰지 않는다. 최대 3문장
    if (!duty && !adopted) {
      const isRest = /^(room_rest|ROOM_REST|room_night|idle|room_bath|room_nap)$/.test(s.act);
      const venue = l => venueOf(l) || noParen(l).split(' ')[0], selV = venue(s.label);
      const here = foodScene(s) && venueOf(s.label) ? venueOf(s.label) : /룸서비스|객실에서/.test(s.label) ? '객실' : shortName(s.label);
      const altName = c => /객실에서 쉬기|^ROOM_REST$|^ROOM$/.test(c.label + '|' + c.id) ? '객실 휴식' : venueOf(c.label) || (LABELS[c.id] && venueOf(LABELS[c.id])) || (shortName(c.label).length >= 3 ? shortName(c.label) : noParen(c.label).replace(/\s*·\s*/g, '·'));
      const ev = x.cands.find(c => c.allowed && c.id !== x.selectedId && isEvent(c.id) && Number.isFinite(c.score) && Number.isFinite(sel?.score) && Math.abs(c.score-sel.score)<0.35);
      const alts = x.cands.filter(c => c.allowed && c.id !== x.selectedId && c.id !== 'OUTSIDE_MEAL' && !rawId(c.label) && !isEvent(c.id) && !(foodScene(s) && venue(c.label) === selV)).sort((a, b) => (b.prob ?? b.score ?? 0) - (a.prob ?? a.score ?? 0)).slice(0, 2);
      const blk = foodScene(s) && s.act !== 'lunch_skip' && !/건너/.test(s.label) ? [...x.cands.filter(c => !c.allowed && c.block && !rawId(c.label) && !isEvent(c.id) && isFood(c.id)).map(c => ({ v: venue(c.label), why: blockText(c.block) })), ...x.excluded.filter(e => isFood(e.id)).map(e => ({ v: venue(e.label), why: blockText(e.reason) }))].filter(e => e.why && /마감|문을 열지/.test(e.why) && e.v && !/[A-Z_]{3,}/.test(e.v) && e.v !== selV) : [];
      const nearTie = !!(x.review && (x.review.triggers || []).includes('NEAR_TIE'));
      // The trigger describes the top pair, not every surviving named alternative.
      const nearAlt = nearTie && alts.find(a=>Number.isFinite(a.score)&&Number.isFinite(sel?.score)&&Math.abs(a.score-sel.score)<0.35);
      const extras = [];
      // (d) 그 시점의 상태 — 허기(마지막 식사 뒤 경과) · 피로 지표(기록값)
      if (x.ctx) {
        const lm = x.ctx.lastMeal, slot = lm && (MEAL[lm.meal_slot] || null), hw = x.ctx.msme != null ? hoursWord(x.ctx.msme) : null;
        if (foodScene(s) && !/건너/.test(s.label) && slot && hw && x.ctx.msme >= 150 && mealOf(s) !== lm.meal_slot) extras.push([pick3([`${slot}을 먹은 지 ${hw} 지난 때였습니다.`, `${slot} 뒤로 ${hw} 지나 있었습니다.`]), () => { used.state = 'meal_gap'; }]);
        else if (isRest && typeof x.ctx.fatigue === 'number' && x.ctx.fatigue >= 0.75) extras.push([pick3(['이 시점에는 휴식이 필요한 상태로 계산되었습니다.']), () => { used.state = 'fatigue'; }]);
      }
      // (b) 행사가 열려 있었는데 가지 않음
      if (isRest && !ev) { /* 휴식 장면에는 대안을 늘어놓지 않는다 */ }
      else if (ev && !isEvent(x.selectedId || '')) { const el = noParen(ev.label).split(/\s*·\s*/)[0]; extras.push([pick3([`같은 시간 ${el}도 열려 있었지만 이번에는 들르지 않았습니다.`, `${el}가 한창인 시간이었지만 이쪽을 택했습니다.`]), () => used.alternatives.push(clean(ev.label))]); }
      // (c) 실제로 견준 대안 — 근소한 차(규칙 엔진 기록) · 추첨에서 비중이 컸던 다른 후보
      else if (nearAlt && !isRest) { const a = nearAlt; extras.push([pick3([`${altName(a)}${josa(altName(a), '과', '와')} 마지막까지 견준 선택입니다.`, `${altName(a)}도 거의 같은 수준으로 비교됐습니다.`]), () => used.alternatives.push(clean(a.label))]); }
      else if (blk.length >= 2) { const g = {}; for (const e of blk) { (g[e.why] = g[e.why] || []); if (!g[e.why].includes(e.v)) g[e.why].push(e.v); } const [why, vs] = Object.entries(g).sort((a, b) => b[1].length - a[1].length)[0]; if (vs.length >= 2) extras.push([`${vs.slice(0, 3).join(' · ')}${josa(vs[Math.min(vs.length, 3) - 1], '은', '는')} ${why}.`, null]); }
      // (e) 연속성 — 이번 체류에서 이미 들른 곳 · 뒤이어 생각해 둔 일정(내다보기 기록)
      if (!isRest && x.priorSame.length && !foodScene(s)) { const p0 = x.priorSame[x.priorSame.length - 1]; extras.push([p0.sameDay ? '오늘 두 번째 걸음입니다.' : '전날에도 들렀던 곳입니다.', () => { used.state = used.state || 'prior_same'; }]); }
      else if (x.lookahead && !isRest) { const nl = shortName(x.lookahead.label); extras.push([`뒤이어 ${nl}까지 생각해 둔 시간이었습니다.`, () => { used.lookahead = clean(x.lookahead.label); }]); }
      for (const [t, mark] of extras) { if (out.length >= 3) break; out.push(t); if (mark) mark(); }
    }
    return { sentences: out.filter(Boolean).slice(0, 3), used, weak: !!weak };
  }

  // QA: 카드 문장이 실제 선택 · 기록과 어긋나거나, 카드에 두지 않기로 한 정보가 들어가면 실패 → 기존 카드로 대체
  function qa(x, story) {
    const errs = [], txt = story.sentences.join(' '), lab = /^(theatre|footbath|night_footbath|pool)$/.test(x.scene.act) ? LABELS[x.scene.act] : clean(x.scene.label);
    const norm = t => String(t).replace(/\s|에서|을|를|으로|로|은|는|이|가/g, '');
    const v0 = venueOf(lab), menu0 = v0 ? noParen(lab).replace(new RegExp('^(' + VENUES + ')\\s*'), '').replace(/\s*·\s*(점심|저녁|아침)\s*$/, '').split(/\s*·\s*/)[0] : '';
    const core = foodScene(x.scene) && v0 ? [v0, menu0 && !/^(점심|저녁|아침|식사)$/.test(menu0) ? longest(menu0) : null].filter(Boolean) : null;
    const anyTok = shortName(lab).split(/\s+/).filter(t => t.length >= 2 && !/^(호텔|객실|간단히|가볍게|투숙|건물|기존|메뉴|기준|가상|계산)$/.test(t));
    const missing = core ? core.some(t => !norm(txt).includes(norm(t))) : (anyTok.length > 0 && !anyTok.some(t => norm(txt).includes(norm(t))));
    if (!OBLIGATION.has(x.scene.act) && x.scene.act !== 'wait' && !/rest|REST|bath|nap|idle|SKIP_BREAKFAST|lunch_skip|room_night/.test(x.scene.act) && !/건너/.test(lab) && missing) errs.push('최종 선택 이름 없음');
    if (story.sentences.length < 1 || story.sentences.length > 3) errs.push('문장 수 ' + story.sentences.length);
    if (/(^|\s)([가-힣]{2,}) \2(\s|$)/.test(txt)) errs.push('이름 중복');
    if (/[A-Z]{2,}_[A-Z0-9_]+|\b[a-z]+_[a-z0-9_]+\b/.test(txt)) errs.push('내부 ID 노출');
    if (hasPrice(txt) || /점수|확률|가중치|규칙 엔진|LLM|확신|계산상|중립값/.test(txt)) errs.push('카드에 둘 수 없는 정보');
    if (story.used.next && x.nexts[0] && clean(x.nexts[0].label) !== story.used.next) errs.push('다음 일정 불일치');
    if (x.review && /ADOPTED/.test(x.review.decided_by || x.review.outcome || '') && !story.used.review) errs.push('LLM 변경인데 규칙 이유 사용');
    if (story.used.facts.some(f => x.review ? false : !x.facts.find(y => y.id === f))) errs.push('기록에 없는 사실 인용');
    for (const a of story.used.alternatives) if (!x.cands.some(c => clean(c.label) === a)) errs.push('기록에 없는 대안: ' + a);
    if (story.weak && /좋아|선호|취향|즐기는|중시/.test(txt.replace(/"[^"]*"/g, ''))) errs.push('약한 추첨 선택에 선호 서술');
    if (!x.review) for (const id of story.used.facts) { const f = x.facts.find(y => y.id === id); if (!f || !f.contrib) errs.push('기여 없는 후기 인용: ' + id); }
    if (story.used.lookahead && (!x.lookahead || clean(x.lookahead.label) !== story.used.lookahead)) errs.push('기록에 없는 내다보기');
    if (story.used.state && !x.ctx) errs.push('기록에 없는 상태 서술');
    if (/피로가 쌓인|쉴 때가 된/.test(txt) && !(x.ctx && typeof x.ctx.fatigue === 'number' && x.ctx.fatigue >= 0.75)) errs.push('피로 지표 없이 피로 서술');
    if (/먹은 지 .* 지난 때|뒤로 .* 지나 있었/.test(txt) && !(x.ctx && x.ctx.msme >= 150)) errs.push('식사 경과 기록 없이 허기 서술');
    return errs;
  }

  // ---------- 정밀 근거 페이지용 구조화 값(기록에 있는 것만) ----------
  function traceRows(x) {
    const s = x.scene, d = x.decision, rv = x.review, cf = d ? d.packet.context_factors || {} : {};
    return {
      personal: { facts: x.facts, traits: x.traits.map(k => ({ key: k, label: TRAIT[k] || k })), marginals: x.marginals || [] },
      state: d ? { time: hm(cf.time), location: x.place(cf.location_id), prior: (cf.activities || []).slice(-4).map(a => `${a.start} ${clean(x.name(a.action_id))}`), last_meal: cf.last_meal, minutes_since_meal_end: cf.minutes_since_meal_end, fatigue_proxy: cf.fatigue_proxy, companions: cf.companions } : { time: hm(s.t0), location: x.place(s.loc), prior: x.prev ? [hm(x.prev.t0) + ' ' + clean(x.prev.label || x.name(x.prev.act))] : [] },
      method: d ? { selection: x.sampling || d.decision_mode || d.selection_phase || null, selected: d.selected_action, llm_choice: d.llm_choice || null, native_before_review: d.provisional_native_choice || null } : { selection: s.source },
      review: rv ? { decided_by: rv.decided_by, rule_choice: rv.rule_choice, final: rv.final, rule_label: rv.rule_label || null, final_label: rv.final_label || null, triggers: rv.triggers || [], confidence: rv.confidence, reasons: rv.reasons || rv.reasons_shown || [], cited_not_in_profile: rv.cited_fact_ids_not_in_profile || [] } : null,
      final: { time: `${hm(s.t0)}–${hm(s.t1)}`, label: s.label, place: x.place(s.loc), charge: x.charge, ledger_rows: x.ledgerRows.map(r => ({ product: r.product, quantity: r.quantity, unit_price_krw: r.unit_price_krw, paid_krw: r.paid_krw, status: r.amount_status, row_id: r.row_id })) }
    };
  }
  const methodLabel = (tr, x) => tr.review && /ADOPTED/.test(tr.review.decided_by || '') ? 'LLM 검토로 변경' : x.sampling ? '가중치 추첨' : /MAX/.test(String(tr.method.selection || '')) ? '최고 점수 선택' : tr.review ? 'LLM 검토 뒤 규칙 선택 유지' : x.decision ? '규칙 점수 선택' : '정해진 일정';
  const esc = t => String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const num = v => v == null ? '–' : (typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(2) : v.toLocaleString('ko-KR')) : esc(String(v)));
  const STATUS = { SIMULATED_CHARGE: '가상 계산 결제', NO_CHARGE: '결제 없음', OBSERVED_CHARGE: '관측 결제', PACKAGE_INCLUDED: '포함 혜택', FREE_USE: '무료 이용' };
  // ④ 규칙·LLM 판단 / ⑤ 최종 행동과 원장 — 기존 행동근거 화면에 없는 두 묶음만 새로 만든다(나머지는 기존 패널 재배치)
  function reviewHTML(tr, x) {
    const rv = tr.review, m = tr.method;
    const head = `<div class="ux-evidence-section-title"><h3>④ 규칙 · LLM 판단</h3><span>${esc(methodLabel(tr, x))}</span></div>`;
    if (!rv) return `<section class="ux-evidence-candidates hls-ev">${head}<p class="ux-evidence-muted">${x.decision ? (x.sampling ? '허용된 후보 가운데 가중치 추첨으로 정했습니다. 최고 가중치 후보와 다를 수 있으며, 이 장면에는 LLM 검토 기록이 없습니다.' : '규칙 점수로 정한 장면입니다. LLM 검토 기록은 없습니다.') : '정해진 일정(도착 · 체크인 · 취침 등)으로 후보 비교가 없는 장면입니다.'}${m.llm_choice ? ` · LLM 선택 기록: ${esc(clean(x.name(m.llm_choice)))}` : ''}</p></section>`;
    const changed = /ADOPTED/.test(rv.decided_by || '');
    const rows = `<table><thead><tr><th>구분</th><th>선택</th></tr></thead><tbody><tr><th>규칙 엔진 1위</th><td>${esc(clean(rv.rule_label || x.name(rv.rule_choice)))}<code>${esc(rv.rule_choice || '')}</code></td></tr><tr class="${changed ? 'selected' : ''}"><th>최종 선택${changed ? ' (LLM 검토로 변경)' : ' (규칙 선택 유지)'}</th><td>${esc(clean(rv.final_label || x.name(rv.final)))}<code>${esc(rv.final || '')}</code></td></tr><tr><th>검토 계기</th><td>${(rv.triggers || []).map(t => esc(TRIGGER[t] || t)).join(' · ') || '기록 없음'}</td></tr><tr><th>LLM 확신</th><td>${rv.confidence != null ? num(rv.confidence) : '기록 없음'}</td></tr></tbody></table>`;
    const reasons = (rv.reasons || []).length ? `<h4>LLM이 적은 이유(원문)</h4>${rv.reasons.map(r => `<article class="hls-ev-reason"><small>${esc(r.type || '이유')}</small><p>${esc(r.text || '')}</p>${(r.fact_ids || []).length ? `<div>${r.fact_ids.map(id => `<button class="cf-link" data-bh-fact="${esc(id)}">${esc(id)} · 프로필의 해당 사실 →</button>`).join('')}</div>` : '<small class="ux-evidence-muted">인용한 후기 사실 없음 · 상황 판단</small>'}</article>`).join('')}` : '<p class="ux-evidence-muted">LLM 이유 원문이 기록에 없습니다.</p>';
    const warn = (rv.cited_not_in_profile || []).length ? `<p class="ux-evidence-muted">프로필에 없는 사실 ID를 인용했습니다: ${rv.cited_not_in_profile.map(esc).join(', ')}</p>` : '';
    return `<section class="ux-evidence-candidates hls-ev">${head}<div class="ux-evidence-table-scroll">${rows}</div>${reasons}${warn}</section>`;
  }
  function finalHTML(tr, x, paymentText) {
    const f = tr.final, ch = f.charge || {};
    const rows = f.ledger_rows.length ? `<table><thead><tr><th>원장 품목</th><th>수량</th><th>단가</th><th>금액</th><th>구분</th></tr></thead><tbody>${f.ledger_rows.map(r => `<tr><th>${esc(clean(r.product))}${r.row_id ? `<code>${esc(r.row_id)}</code>` : ''}</th><td>${r.quantity != null ? esc(r.quantity) : '–'}</td><td>${r.unit_price_krw != null ? num(r.unit_price_krw) + '원' : '–'}</td><td>${r.paid_krw != null ? num(r.paid_krw) + '원' : '–'}</td><td>${esc(STATUS[r.status] || r.status || '')}</td></tr>`).join('')}</tbody></table>` : `<p class="ux-evidence-muted">이 장면에 연결된 원장 행이 없습니다${paymentText ? ' · ' + esc(paymentText) : ''}.</p>`;
    const assumption = ch.grade && ch.grade !== '◎' ? `<p class="ux-evidence-muted">가격 근거 등급 ${esc(ch.grade)}: ${esc(ch.basis || '운영 가정')} — 관측 결제가 아닌 가상 계산입니다.</p>` : '';
    return `<section class="ux-evidence-candidates hls-ev"><div class="ux-evidence-section-title"><h3>⑤ 최종 행동과 원장</h3><span>${esc(f.time)} · ${esc(clean(f.label))}${f.place && !rawId(f.place) ? ' · ' + esc(f.place) : ''}</span></div><div class="ux-evidence-table-scroll">${rows}</div>${assumption}</section>`;
  }

  function foodObservation(x) {
    const o=x.decision?.packet?.context_factors?.food_observation;
    if (!o) return '';
    const labels={UNOBSERVED_IN_ACCEPTED_INPUT:'음식 종류 취향 미관측 · 현재 수용 입력 기준',FOOD_EVIDENCE_UNMAPPED:'음식 관련 근거 있음 · 구체 메뉴 취향 연결은 미확정',LINKED_PREFERENCE:'기존 프로필의 음식 선호·비선호 연결 있음'};
    const selected=(x.rawCands||[]).find(c=>c.candidate_id===x.selectedId);
    const terms=selected?.terms||[];
    const direct=new Set((o.menu_links||[]).flatMap(m=>m.fact_ids||[]));
    const active=terms.filter(t=>Math.abs(t.value||0)>0 && (t.fact_ids||[]).length);
    const food=active.some(t=>t.facet==='food_specific' && t.fact_ids.some(id=>direct.has(id)));
    const plannerIndirect=Object.entries(selected?.profile_feature_marginals||{}).some(([k,v])=>(o.indirect_fact_ids?.[k.split('.').pop()]||[]).length && Math.abs(v.weight_delta_at_fixed_state||0)>0);
    const desc=plannerIndirect?'개인 근거가 있는 일반 성향이 점심 선택 가중치에 반영됐습니다. 이 가중치는 저녁 후보 점수와 다른 단위이며 구체 음식 취향을 뜻하지 않습니다.':food?'구체 메뉴 근거가 실제 점수에 연결됐습니다. 원문 직접성·조건부 표현은 별도 확인 대상입니다.':active.length?'개인의 일반적인 선택 성향·경험이 간접 기여했습니다. 이를 해당 음식의 확고한 취향으로 해석하지 않습니다.':'선택 후보의 규칙 점수는 직접 개인 Fact 기여 없이 공통 규칙·현재 상황 중심입니다. 별도 검토 근거는 최종 판단에서 확인합니다.';
    const delta=selected?.score_contribution;
    return `<div class="hls-food-observation"><p><strong>${esc(labels[o.status]||'음식 취향 관측 상태 확인 필요')}</strong></p><p>${esc(desc)}</p><small>미관측은 비선호가 아닙니다. 근거 수만으로 신뢰도를 확정하지 않으며 반례가 없다고 가정하지 않습니다.</small>${delta?`<p>동일 상태 자체 점수: 공통 ${delta.common.toFixed(3)} + 개인 근거 차이 ${delta.evidence_delta.toFixed(3)} = ${delta.actual.toFixed(3)}<br><small>이후 일정 가치와 상태 보정은 별도입니다. 이 차이는 확률이나 전체 방문의 인과 효과가 아닙니다.</small></p>`:''}</div>`;
  }

  function diningComparison(x) {
    const labels = {PIZZA_HILL:'피자힐',MOEGI:'모에기',MYONGWOLGWAN:'명월관',GEUMRYONG:'금룡',ONDAL:'온달',THE_BUFFET:'더뷔페',THE_PAVILION:'파빌리온',LE_PASSAGE:'르 파사쥬',ROOM_MEAL:'룸서비스',LUX_BAR:'LUX BAR'};
    const by = new Map(), score = r => r.final_with_lookahead ?? r.final_score;
    for (const r of x.rawCands || []) {
      const v=r.service_contract?.venue_id;
      if (!labels[v] || r.world_allowed === false || !Number.isFinite(score(r))) continue;
      if (!by.has(v) || score(r)>score(by.get(v))) by.set(v,r);
    }
    if (!by.size) return foodObservation(x);
    const rows=[...by].sort((a,b)=>score(b[1])-score(a[1]));
    const termHTML=r=>(r.terms||[]).map(t=>`<li>${esc(t.factor)}: ${Number(t.value||0).toFixed(3)} · ${esc((t.fact_ids||[]).length ? '개인 근거 연결: '+t.fact_ids.join(', ') : /profile/.test(t.kind||'') ? '상품·공통 기저 포함 항 · 직접 Fact 없음' : '상황·공통 규칙')}</li>`).join('');
    const excluded=x.decision?.packet?.catalog_excluded_candidates||[];
    const reasons=new Map();for(const e of excluded)for(const why of e.reasons||[]){const key=(e.venue_id||'상품')+' · '+why;reasons.set(key,(reasons.get(key)||0)+1);}
    return `${foodObservation(x)}<details class="hls-dining-comparison"><summary>식당별 최고 후보와 실제 점수 항 비교</summary><p class="ux-evidence-muted">같은 결정 시점의 업장별 최고 후보입니다. 자체 점수와 이후 일정 가치를 구분합니다. Fact가 연결된 혼합항도 전부 개인 기여액이라는 뜻은 아닙니다. 점수는 선택 확률이 아닙니다.</p><div class="ux-evidence-table-scroll"><table><thead><tr><th>업장·후보</th><th>자체</th><th>이후 일정</th><th>비교 총점</th></tr></thead><tbody>${rows.map(([v,r])=>`<tr><th>${esc(labels[v])}${r.candidate_id===x.selectedId?' · 최종 선택':''}<br><small>${esc(r.candidate_label||x.name(r.candidate_id))}</small><details><summary>점수 항·근거</summary><ul>${termHTML(r)}${r.context_adjustment?`<li>이전 상태·문맥 보정: ${Number(r.context_adjustment).toFixed(3)}</li>`:''}</ul></details></th><td>${Number(r.final_score).toFixed(3)}</td><td>${(score(r)-r.final_score).toFixed(3)}</td><td>${score(r).toFixed(3)}</td></tr>`).join('')}</tbody></table></div>${reasons.size?`<details><summary>점수 계산 전 판매 조건에서 제외된 항목</summary><ul>${[...reasons].map(([k,n])=>`<li>${esc(k)} · ${n}개</li>`).join('')}</ul><small>한 상품에 여러 제외 조건이 있을 수 있습니다. 세부 원문 코드는 감사 기록입니다.</small></details>`:''}</details>`;
  }

  const API = { input, decisionOf, compose, qa, traceRows, reviewHTML, finalHTML, diningComparison, foodObservation, methodLabel, clean, hm, _lead: leadPhrase, _act: actPhrase };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.HLStory = API;
  if (typeof root.document === 'undefined') return;

  // ---------- 제품 연결 0: C01 상품 이름 — 제품 이름표가 '다른 활동'으로만 아는 id 에 엔진 SPECS 이름을 붙인다(정본 테이블로 교체 예정) ----------
  if (typeof root.agU06ActionName === 'function' && !root.agU06ActionNameOriginal) {
    const origName = root.agU06ActionName; root.agU06ActionNameOriginal = origName;
    root.agU06ActionName = function (id) { const n = origName(id); return (GENERIC.has(n) || n === id) && (C01_LABELS[id] || LABELS[id]) ? (C01_LABELS[id] || LABELS[id]) : n; };
  }
  // ---------- 제품 연결 1: 고객 흐름 카드(agBRWhy) — 이야기 + '행동근거 보기 →' 버튼만 ----------
  const readX = (flow, pid, index, D, c, sc) => {
    const lab = id => (typeof root.agU06ActionName === 'function' ? root.agU06ActionName(id) : id);
    const place = id => { try { const n = typeof root.agPlaceName === 'function' ? root.agPlaceName(id) : null; return n && n !== id ? n : null; } catch (e) { return null; } };
    const gist = id => { try { if (typeof root.agBRFacts === 'function' && c && sc) { const f = root.agBRFacts(pid, c, sc).find(f => f.id === id || f.fact_id === id); if (f && (f.gist || f.text)) return f.gist || f.text; } const LP = (typeof libP === 'function') ? libP : root.libP, LS = (typeof LIB_SENS !== 'undefined') ? LIB_SENS : root.LIB_SENS; const P = typeof LP === 'function' ? LP(pid) : null, Fx = P && P.engine && P.engine.facts || {}; const g = Fx[id] && !Fx[id].hidden ? Fx[id].gist : null; return g && !(LS && LS.test(g)) ? g : null; } catch (e) { return null; } };
    return input(flow.result, pid, index, { label: lab, place, gist, visit: (flow.result.visits || {})[pid], rows: (D && D.rows) || [] });
  };
  if (typeof root.agBRWhy === 'function') {
    const original = root.agBRWhy; root.agBRWhyOriginal = original;
    root.agBRWhy = function (c, sc, D) {
      try {
        const AGx = (typeof AG !== 'undefined') ? AG : root.AG, flow = AGx && AGx.flow, pid = c.persona_id;   // agent.js 의 AG 는 최상위 let/const
        if (!flow || !flow.result || !flow.result.plans[pid] || !D || D.index < 0) return original(c, sc, D);
        if (flow.result.plans[pid].trace?.planner_backend?.startsWith('LLM_AUTONOMOUS_CUSTOMER_')) return original(c, sc, D);
        if (typeof root.hlReasonView === 'function' && root.hlReasonView(flow, pid, D.index)) return original(c, sc, D);   // 연구 저장 실행은 기존 설명 유지
        const x = readX(flow, pid, D.index, D, c, sc), story = compose(x), errs = qa(x, story);
        root.__HLS_LAST = { result: flow.result, pid, si: sc.si, x, story, ok: !errs.length };
        if (errs.length) return original(c, sc, D) + `<!-- HLStory QA 실패: ${esc(errs.join(', '))} -->`;
        return `<section class="frp-section frp-why hls-why" data-frp-section="why" data-story-ok="1"><div class="frp-section-heading"><h3>왜 이 행동인가</h3><button class="rp-link" data-ux-scene="${sc.si}" data-ux-person="${esc(pid)}">행동근거 보기 →</button></div><p class="hls-story">${story.sentences.map((sentence,i)=>{let text=esc(sentence);if(i===0){const names=[clean(x.scene.label),...clean(x.scene.label).split(/\s*·\s*/),x.charge?.sku_contract?.label,x.selectedId&&x.name(x.selectedId)].filter(Boolean).sort((a,b)=>b.length-a.length);const name=names.find(n=>sentence.includes(n));if(name)text=text.replace(esc(name),'<strong>'+esc(name)+'</strong>');}return `<span class="hls-sentence hls-sentence-${i}">${text}</span>`;}).join(' ')}</p></section>`;
      } catch (e) { return original(c, sc, D); }
    };
  }

  // ---------- 제품 연결 1b: 카드 전체(agBRCard) 후처리 — 중복 설명 제거 · 제목 정리 · 후기 근거 간결화. 이야기(agBRWhy)가 적용된 카드에만 ----------
  const ROLE_TEXT = f => f.roles.includes('llm_cited') ? 'LLM 검토가 인용' : f.roles.includes('direct') ? '후기에서 확인' : f.roles.includes('score_term') ? `점수 기여 · ${f.factor || '성향 항'}${f.value ? ' +' + f.value.toFixed(2) : ''}` : '장면 연결 사실 · 점수 기여 아님';
  if (typeof root.agBRCard === 'function') {
    const origCard = root.agBRCard; root.agBRCardOriginal = origCard;
    root.agBRCard = function (c, sc) {
      const html = origCard(c, sc);
      try {
        const L = root.__HLS_LAST; if (!sc || !L || !L.ok || L.pid !== c.persona_id || L.si !== sc.si) return html;
        const tpl = root.document.createElement('template'); tpl.innerHTML = html.trim(); const card = tpl.content.firstElementChild; if (!card || !card.querySelector('.hls-why')) return html;
        const x = L.x, s = x.scene;
        // (1) 제목: 내부 분석 꼬리표 제거('기존 메뉴 기준 가상 계산' · 'LLM 변경'), 식사 장면은 실제 메뉴를 함께
        const h2 = card.querySelector('.frp-current h2');
        const menuOf = () => { const lab = clean0((x.charge && x.charge.sku_contract && x.charge.sku_contract.label) || (x.ledgerRows[0] && x.ledgerRows[0].product) || s.label || ''); const v = venueOf(lab); const m = v ? lab.replace(new RegExp('^(' + VENUES + ')\\s*'), '').replace(/\s*·\s*(점심|저녁|아침)\s*$/, '').trim() : ''; return m && !/^(점심|저녁|아침|식사)$/.test(m) ? m : null; };
        if (h2) { let t = clean0(h2.textContent).replace(/\s*[·(]?\s*LLM 변경[^)·]*\)?/g, '').trim(); const menu = foodScene(s) ? menuOf() : null; if (menu && !t.includes(menu)) t = `${t} · ${menu}`; h2.textContent = t; }
        // (2) 상단 설명줄: 기존 scene.why(성향 문장)가 새 문단과 겹치면 제거하고, 식사면 메뉴만 남긴다
        const desc = card.querySelector('.frp-current-description');
        if (desc) { const txt = (desc.querySelector('.ag-readable-body') || desc).textContent.trim(); if (txt === clean(s.why || '') || /성향|맞춰|중시하는|선호|뒷받침|고정한 비교/.test(txt)) desc.remove(); }
        // (3) 후기 근거: 이 선택에 실제로 작용한 사실만 남기고(원문 · 프로필 링크 유지), 전체는 정밀 근거로
        const ev = card.querySelector('.frp-evidence');
        if (ev) {
          const contrib = x.facts.filter(f => f.contrib); const keep = new Set(contrib.map(f => f.id)); const byId = Object.fromEntries(contrib.map(f => [f.id, f]));
          const cards = [...ev.querySelectorAll('.frp-fact-card')]; const kept = [];
          for (const li of cards) { const id = String(li.getAttribute('data-frp-fact-search') || '').split(' ')[0]; if (!keep.has(id)) { li.remove(); continue; } kept.push(li); const fact = byId[id], direct = fact.roles.includes('direct') || fact.roles.includes('llm_cited'); li.dataset.factDirect = String(direct); const tag = li.querySelector('.frp-fact-tags span'); if (tag) tag.textContent = (typeof root.agBRFactTag === 'function' ? root.agBRFactTag(fact.gist || '', fact) + ' · ' : '') + (direct ? '현재 장면에 직접 연결된 근거' : '성향 점수에 사용된 간접 근거'); const d = li.querySelector('details'); if (d) { const links = d.querySelector('.frp-fact-links'); const row = root.document.createElement('div'); row.className = 'frp-fact-links hls-fact-links'; const role = root.document.createElement('small'); role.className = 'hls-fact-role'; role.textContent = ROLE_TEXT(byId[id]); row.appendChild(role); if (links) while (links.firstChild) row.appendChild(links.firstChild); d.replaceWith(row); } }
          const ctxBox = ev.querySelector('details.frp-context-facts'); if (ctxBox) { const ul = ctxBox.querySelector('ul.frp-fact-cards'); if (ul && kept.length) ctxBox.replaceWith(ul); else ctxBox.remove(); }
          for (const pnote of ev.querySelectorAll('p.frp-note')) pnote.remove();
          const h3 = ev.querySelector('h3'); const head = root.document.createElement('div'); head.className = 'frp-section-heading'; head.innerHTML = `<h3>후기 근거</h3><button class="rp-link" data-review-all="${esc(c.persona_id)}" data-review-scene="${esc(sc.si)}">전체 근거 →</button>`; if (h3) h3.replaceWith(head); else ev.insertBefore(head, ev.firstChild);
          if (!kept.length) { const pn = root.document.createElement('p'); pn.className = 'frp-note'; pn.textContent = x.decision ? '이 선택에 직접 작용한 후기 사실은 기록에 없습니다. 당시 상태와 공통 규칙으로 정해진 장면입니다.' : OBLIGATION.has(s.act) ? '정해진 일정이라 후기 근거를 쓰지 않는 장면입니다.' : '이 장면에는 후보 비교 기록이 없어 후기 근거를 쓰지 않습니다.'; ev.appendChild(pn); }
          else { const pn = root.document.createElement('p'); pn.className = 'frp-note hls-fact-note'; pn.textContent = `이 선택에 작용한 후기 ${kept.length}건 · 전체 후기는 고객 상세의 후기 근거 탭에서`; ev.appendChild(pn); }
        }
        return card.outerHTML;
      } catch (e) { return html; }
    };
  }

  // ---------- 제품 연결 2: 정밀 근거 페이지(bhEvidenceHTML) — 기존 패널을 ①~⑤ 순서로 재배치하고, 없는 ④ ⑤ 만 추가 ----------
  if (typeof root.bhEvidenceHTML === 'function') {
    const originalEv = root.bhEvidenceHTML; root.bhEvidenceHTMLOriginal = originalEv;
    root.bhEvidenceHTML = function (m, c) {
      if (root.HLAgentDecisionView?.record(m.raw) || m.plan?.trace?.planner_backend?.startsWith('LLM_AUTONOMOUS_CUSTOMER_')) return originalEv(m,c);
      const html = originalEv(m, c);
      try {
        const tpl = root.document.createElement('template'); tpl.innerHTML = html.trim();
        const rootEl = tpl.content.firstElementChild; if (!rootEl) return html;
        const q = s => rootEl.querySelector(s);
        const nav = q('.ux-evidence-nav'), hero = q('.ux-evidence-hero'), major = q('.ux-evidence-major'), grid = q('.ux-evidence-grid'), cands = q('.ux-evidence-candidates'), raw = q('.ux-evidence-raw');
        if (!nav || !hero || !grid || !cands) return html;
        const gs = [...grid.children]; const facts = gs.find(e => /후기/.test(e.querySelector('h3') ? e.querySelector('h3').textContent : '')), profile = gs.find(e => /프로파일|프로필/.test(e.querySelector('h3') ? e.querySelector('h3').textContent : '')), common = gs.find(e => /공통/.test(e.querySelector('h3') ? e.querySelector('h3').textContent : '')), state = gs.find(e => /환경|이전 행동/.test(e.querySelector('h3') ? e.querySelector('h3').textContent : ''));
        const known = new Set([nav, hero, major, grid, cands, raw].filter(Boolean));
        const others = [...rootEl.children].filter(el => !known.has(el)); const footer = others.filter(el => el.tagName === 'P' && /연결된 제품 실행 기록만/.test(el.textContent)); const research = others.filter(el => !footer.includes(el));
        const pid = c.customer_id, x = readX(m.flow, pid, c.scene_index, { rows: m.rows }, null, null), story = compose(x), errs = qa(x, story), tr = traceRows(x);
        const paymentText = (hero.querySelector('.ux-evidence-money b') || {}).textContent || '';
        // 제목의 내부 분석 꼬리표('기존 메뉴 기준 가상 계산' 등)는 작은 글씨로 내린다(값은 ⑤ 가격 근거에 그대로)
        { const h3 = hero.querySelector('h3'); if (h3) { const full = h3.textContent.trim(), short = clean0(full).replace(/\s*[·(]?\s*LLM 변경[^)·]*\)?/g, '').trim(); if (short && short !== full) { h3.textContent = short; const tail = full.replace(short, '').replace(/^\s*·\s*/, '').trim(); if (tail) { const sm = root.document.createElement('small'); sm.className = 'hls-hero-tail'; sm.textContent = tail; h3.insertAdjacentElement('afterend', sm); } } } }
        // ① 결정 요약(이야기 + 선택 방식 · 근거 수 · 변경 여부)
        const chips = [`선택 방식: ${methodLabel(tr, x)}`, `후기 근거 ${x.facts.length}건`, tr.review ? (/ADOPTED/.test(tr.review.decided_by || '') ? `LLM 검토로 변경: ${clean(tr.review.rule_label || x.name(tr.review.rule_choice))} → ${clean(tr.review.final_label || x.name(tr.review.final))}` : 'LLM 검토 뒤 규칙 선택 유지') : (x.decision ? 'LLM 검토 없음' : '후보 비교 없음(정해진 일정)'), x.sampling && x.cands.find(k => k.id === x.selectedId) && x.cands.find(k => k.id === x.selectedId).prob != null ? `추첨 사후 확률 ${(100 * x.cands.find(k => k.id === x.selectedId).prob).toFixed(0)}%` : null].filter(Boolean);
        const summary = root.document.createElement('section'); summary.className = 'hls-ev-summary';
        // 첫 화면 핵심: 최종 선택 / 작용한 개인 근거 · 상황 / 규칙과 LLM 차이 / 주문 · 매출 — 모두 기록값만
        const adoptedEv = !!(tr.review && /ADOPTED/.test(tr.review.decided_by || '')), selC = x.cands.find(k => k.id === x.selectedId), allowedN = x.cands.filter(k => k.allowed).length;
        const finalName = clean(tr.review && tr.review.final_label || (x.charge && x.charge.sku_contract && x.charge.sku_contract.label) || x.scene.label);
        const ruleName = tr.review ? clean(tr.review.rule_label || x.name(tr.review.rule_choice)) : null;
        const howText = adoptedEv ? `규칙 엔진 1위는 ${ruleName} — LLM 검토로 ${finalName}${josa(finalName, '으로', '로')} 변경` : x.sampling ? `허용 후보 ${allowedN}개 중 가중치 추첨${selC && selC.prob != null ? ` · 사후 확률 ${(100 * selC.prob).toFixed(0)}%` : ''}${tr.review ? ' · LLM 검토 뒤 규칙 선택 유지' : ''}` : x.decision ? `허용 후보 ${allowedN}개 중 규칙 점수 1위${tr.review ? ' · LLM 검토 뒤 유지' : ''}` : '정해진 일정(후보 비교 없음)';
        const contribF = x.facts.filter(f => f.contrib), basisOnly = x.facts.filter(f => !f.contrib);
        const factText = contribF.length ? contribF.slice(0, 4).map(f => `${f.id} ${ROLE_TEXT(f)}${f.ext && !f.roles.includes('llm_cited') ? ` (${f.ext}에서 확장)` : ''}`).join(' · ') + (contribF.length > 4 ? ` 외 ${contribF.length - 4}건` : '') : (x.traitTerms.length ? `개인 후기 사실 연결 없음 · 성향 항 ${x.traitTerms.map(t => `${t.factor} +${(t.value || 0).toFixed(2)}`).join(', ')}` : '개인 후기 기여 없음 — 공통 규칙과 당시 상태로 정해진 선택');
        const lmSlot = x.ctx && x.ctx.lastMeal && MEAL[x.ctx.lastMeal.meal_slot], stateText = x.ctx ? [hm(x.ctx.time), tr.state.location && !rawId(tr.state.location) ? tr.state.location : null, tr.state.prior.length ? `직전 ${tr.state.prior[tr.state.prior.length - 1]}` : null, x.ctx.msme != null ? `${lmSlot ? lmSlot + ' ' : '마지막 식사 '}뒤 ${x.ctx.msme}분` : null, x.ctx.companions && x.ctx.companions.n ? `일행 ${x.ctx.companions.n}명` : null, typeof x.ctx.fatigue === 'number' ? `피로 지표 ${x.ctx.fatigue.toFixed(2)}` : null].filter(Boolean).join(' · ') : `${hm(x.scene.t0)}${tr.state.prior.length ? ' · 직전 ' + tr.state.prior[0] : ''}`;
        const llmText = adoptedEv ? `규칙 ${ruleName} → LLM ${finalName} · 계기: ${(tr.review.triggers || []).map(t => TRIGGER[t] || t).join(', ') || '기록 없음'}${(tr.review.reasons || []).some(r => (r.fact_ids || []).length) ? ` · 인용 사실 ${[...new Set(tr.review.reasons.flatMap(r => r.fact_ids || []))].join(', ')}` : ' · 후기 인용 없음(상황 판단)'}` : tr.review ? `LLM 검토 있음 · 규칙 선택 유지(계기: ${(tr.review.triggers || []).map(t => TRIGGER[t] || t).join(', ') || '기록 없음'})` : x.decision ? 'LLM 검토 없음' : '해당 없음';
        const ledgerText = tr.final.ledger_rows.length ? tr.final.ledger_rows.map(r => `${clean(r.product)}${r.quantity != null ? ' ×' + r.quantity : ''}${r.paid_krw != null ? ' ' + num(r.paid_krw) + '원' : ''}${STATUS[r.status] ? ' (' + STATUS[r.status] + ')' : ''}`).join(' · ') : (paymentText || '연결된 원장 행 없음');
        const keyRows = [['① 당시 상황', stateText], ['② 개인 성향·후기', factText + (basisOnly.length ? ` · 장면 연결만(점수 기여 아님) ${basisOnly.map(f => f.id).join(', ')}` : '')], ['③ 후보 비교', `적격 후보 ${allowedN}개 · 점수 기여와 제외 사유는 아래 후보표에서 확인`], ['④ 최종 판단', `${finalName} — ${howText} · ${llmText}`], ['⑤ 행동·소비', ledgerText]];
        summary.innerHTML = `<div class="hls-ev-steps"><span>① 당시 상황</span><span>② 성향·후기</span><span>③ 후보 비교</span><span>④ 최종 판단</span><span>⑤ 행동·소비</span></div><p class="hls-ev-story">${errs.length ? '<span class="ux-evidence-muted">이야기 요약을 만들 수 없는 장면입니다(' + esc(errs.join(', ')) + ').</span>' : story.sentences.map(esc).join(' ')}</p><dl class="hls-ev-key">${keyRows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl><ul class="hls-ev-chips">${chips.map(t => `<li>${esc(t)}</li>`).join('')}</ul>`;
        const step = (n, title, note) => { const h = root.document.createElement('div'); h.className = 'hls-ev-step'; h.innerHTML = `<h3>${n} ${esc(title)}</h3>${note ? `<span>${esc(note)}</span>` : ''}`; return h; };
        const wrap = (cls, ...els) => { const w = root.document.createElement('div'); w.className = cls; els.filter(Boolean).forEach(e => w.appendChild(e)); return w; };
        // ② 선택 당시 상태 — 기존 패널에 읽을 수 있는 직전 활동 · 장소 · 식사 뒤 경과만 보탠다
        if (state) { const dl = state.querySelector('dl.ux-state'); if (dl) { const add = (k, v) => { if (v == null || v === '') return; const d = root.document.createElement('div'); d.innerHTML = `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`; dl.insertBefore(d, dl.firstChild); }; add('식사 뒤 경과', tr.state.minutes_since_meal_end != null ? tr.state.minutes_since_meal_end + '분' : null); add('피로 지표', tr.state.fatigue_proxy != null ? num(tr.state.fatigue_proxy) : null); add('직전 활동', tr.state.prior.length ? tr.state.prior.join(' → ') : null); add('판단 장소', tr.state.location && !rawId(tr.state.location) ? tr.state.location : null); } }
        // ① 후기 사실의 역할 표시 — LLM 인용 / 점수 기여(+값 · 확장 출처) / 후기에서 확인 / 장면 연결만. LLM이 인용했는데 기존 목록에 없는 사실은 맨 앞에 보탠다
        if (facts) {
          const box = facts.querySelector('.ux-evidence-facts') || facts; const seen = new Set();
          for (const art of box.querySelectorAll('article')) { const sm = art.querySelector('small'); const id = sm ? sm.textContent.trim() : ''; const f = x.facts.find(y => y.id === id); seen.add(id); const b = root.document.createElement('span'); b.className = 'hls-role' + (f && f.roles.includes('llm_cited') ? ' hls-role-llm' : f && f.contrib ? ' hls-role-score' : ' hls-role-link'); b.textContent = f ? ROLE_TEXT(f) + (f.ext && !f.roles.includes('llm_cited') ? ` · ${f.ext}에서 확장` : '') : '점수 항 연결'; if (sm) sm.insertAdjacentElement('afterend', b); else art.appendChild(b); }
          for (const f of x.facts.filter(y => y.roles.includes('llm_cited') && !seen.has(y.id))) { const art = root.document.createElement('article'); const g = f.gist || x.gistOf(f.id); art.innerHTML = `<p>${esc(g || '공개 가능한 Fact 요지 연결 미확인')}</p><small>${esc(f.id)}</small><span class="hls-role hls-role-llm">${esc(ROLE_TEXT(f))} · 최종 변경 근거</span><button class="cf-link" data-bh-fact="${esc(f.id)}">프로필의 해당 사실 →</button>`; box.insertBefore(art, box.firstChild); }
          const none = box.querySelector('p.ux-evidence-muted'); if (none && box.querySelector('article')) none.remove();
        }
        // ③ 후보표 — 기본은 최종 선택 · 규칙 1위 · 상위 대안 3개만, 나머지는 펼쳐 보기(행은 지우지 않는다). 업장 묶음 행 · 상품 조건은 기록된 service_contract 로 설명
        const rawById = Object.fromEntries(x.rawCands.map(r => [r.candidate_id, r])); const scoreOf = r => r.final_with_lookahead != null ? r.final_with_lookahead : r.final_score;
        const tops = x.rawCands.filter(r => r.world_allowed !== false && r.candidate_id !== x.selectedId && scoreOf(r) != null).sort((a, b) => scoreOf(b) - scoreOf(a)).slice(0, 3).map(r => r.candidate_id);
        if (x.sampling && x.decision && x.decision.sampling && x.decision.sampling.probabilities) { const pr = x.decision.sampling.probabilities; Object.keys(pr).filter(id => id !== x.selectedId).sort((a, b) => pr[b] - pr[a]).slice(0, 3).forEach(id => { if (!tops.includes(id)) tops.push(id); }); }
        const keepIds = new Set([x.selectedId, tr.review && tr.review.rule_choice, ...tops].filter(Boolean));
        const COND = { CHOOSE_AVAILABLE_PRODUCT_FOR_MEAL_EXECUTION: '상품 단위로 선택하는 업장 묶음 행', SET_SERVING_SIZE_NOT_MATCHED: '세트 인원 조건 불일치', SKU_SERVICE_PERIOD_NOT_AVAILABLE: '이 시간대 판매 메뉴 아님' };
        const tbody = cands.querySelector('tbody'); let hiddenN = 0;
        if (tbody) {
          for (const tr0 of [...tbody.querySelectorAll('tr')]) {
            const code = tr0.querySelector('th code'); const id = code ? code.textContent.trim() : null; const r = id && rawById[id]; const sc = r && r.service_contract;
            if (id) { const tn = code.parentElement.firstChild; const nm = C01_LABELS[id] || LABELS[id]; if (tn && tn.nodeType === 3 && GENERIC.has(tn.textContent.trim()) && nm) tn.textContent = nm; }
            if (id && tr.review && /ADOPTED/.test(tr.review.decided_by || '') && id === tr.review.rule_choice) { const sm = root.document.createElement('small'); sm.textContent = ' 규칙 엔진 1위'; code.parentElement.appendChild(sm); tr0.classList.add('hls-rule-top'); }
            if (sc && r.world_allowed === false) { const td = tr0.lastElementChild; const orig = td.textContent.trim(); const w = sc.service_window; let t = null;
              const extra = orig.split(/\s*;\s*/).filter(pz => pz && !/운영하지 않음|상세 이용 조건/.test(pz));
              if (sc.selection_role === 'VENUE_CONTAINER_NOT_SEPARATE_UNPRICED_MEAL' && sc.venue_operating) t = [`업장 운영 중${w ? `(${w.start}–${w.end})` : ''} · ${COND.CHOOSE_AVAILABLE_PRODUCT_FOR_MEAL_EXECUTION}${(sc.eligible_product_ids || []).length ? ` · 선택 가능 상품 ${sc.eligible_product_ids.length}개` : ''}`, ...extra].join(' · ');
              else if (COND[sc.blocked_reason]) t = [COND[sc.blocked_reason] + (w ? ` · 업장 ${w.start}–${w.end}` : ''), ...extra].join(' · ');
              if (t) { td.innerHTML = `${esc(t)}<small class="hls-cond-raw">기록 문구: ${esc(orig)}</small>`; td.title = orig; } }
            if (id && !keepIds.has(id)) { tr0.classList.add('hls-more'); tr0.hidden = true; hiddenN++; }
          }
          if (hiddenN) { const cols = (cands.querySelector('thead tr') || { children: { length: 7 } }).children.length; const row = root.document.createElement('tr'); row.className = 'hls-more-toggle'; row.innerHTML = `<td colspan="${cols}"><button type="button" class="rp-link" data-hls-more="${hiddenN}">나머지 후보 ${hiddenN}개 펼치기 ↓</button></td>`; tbody.appendChild(row); const title = cands.querySelector('.ux-evidence-section-title span'); if (title) title.textContent = `${x.rawCands.length}개 · 기본 표시: 최종 선택 · 규칙 상위 · 주요 대안 · 점수와 확률은 별도 단위`; }
        }
        cands.insertAdjacentHTML('afterbegin',diningComparison(x));
        const rvEl = root.document.createElement('div'); rvEl.innerHTML = reviewHTML(tr, x); const fnEl = root.document.createElement('div'); fnEl.innerHTML = finalHTML(tr, x, paymentText);
        const out = root.document.createElement('div'); out.className = rootEl.className;
        [nav, summary, hero, major,
          step('①', '당시 상황', '시각 · 장소 · 직전 활동 · 식사 뒤 경과'), wrap('ux-evidence-grid hls-one', state),
          step('②', '개인 성향과 후기 근거', '직접 점수 기여와 참고 Fact를 구분합니다'), ...research, wrap('ux-evidence-grid', facts, profile),
          step('③', '후보 비교와 점수', '열거한 후보 전체 · 가능/불가 사유 · 점수와 추첨 확률'), wrap('ux-evidence-grid hls-one', common), cands,
          rvEl.firstElementChild, fnEl.firstElementChild,
          raw, ...footer].filter(Boolean).forEach(el => out.appendChild(el));
        return out.outerHTML;
      } catch (e) { return html; }
    };
  }
  root.document.addEventListener('click', e => { const b = e.target.closest && e.target.closest('[data-hls-more]'); if (!b) return; const tb = b.closest('tbody'); if (!tb) return; const open = b.getAttribute('aria-expanded') === 'true'; tb.querySelectorAll('tr.hls-more').forEach(r => { r.hidden = open; }); b.setAttribute('aria-expanded', String(!open)); b.textContent = open ? `나머지 후보 ${b.dataset.hlsMore}개 펼치기 ↓` : '주요 후보만 보기 ↑'; });
  const css = `.hls-story{margin:6px 0 2px;line-height:1.65;font-size:13px;color:inherit;word-break:keep-all;overflow-wrap:break-word}
.hls-ev-summary{margin:0 0 16px;padding:18px 22px;border:1px solid #e4dacb;border-radius:12px;background:#fbf8f2}.hls-ev-steps{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}.hls-ev-steps span{font-size:10px;color:#9a8c78;padding:3px 8px;border:1px solid #e6dccb;border-radius:12px;background:#fff}.hls-ev-steps span::before{content:counter(hls) ' ';counter-increment:hls}.hls-ev-steps{counter-reset:hls}
.hls-ev-story{font-size:15px;line-height:1.75;color:#3d474f;margin:0 0 10px;word-break:keep-all}.hls-ev-chips{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px}.hls-ev-chips li{font-size:11px;color:#6e665b;padding:4px 10px;background:#fff;border:1px solid #e6dccb;border-radius:6px}
.hls-ev-step{display:flex;align-items:baseline;gap:12px;margin:22px 0 10px}.hls-ev-step h3{font-size:15px;color:#4f4c46;margin:0}.hls-ev-step span{font-size:11px;color:#a09587}
.ux-evidence-grid.hls-one{grid-template-columns:1fr}.ux-evidence-candidates.hls-ev{margin-top:0}.ux-evidence-candidates.hls-ev h4{font-size:12px;margin:14px 0 6px;color:#6a6258}.hls-ev-reason{padding:10px 0;border-top:1px solid #eee8df}.hls-ev-reason small{font-size:10px;color:#a18a6d}.hls-ev-reason p{font-size:13px;line-height:1.7;color:#5f5950;margin:4px 0 6px}.hls-ev-reason .cf-link{font-size:11px;margin-right:10px}
.ux-evidence-candidates tr.hls-rule-top th{color:#8a5a2b}.ux-evidence-candidates tr.hls-rule-top small{color:#8a5a2b}
.hls-ev-key{margin:0 0 12px;padding:0;display:grid;grid-template-columns:1fr;gap:6px}.hls-ev-key div{display:grid;grid-template-columns:88px 1fr;gap:10px;font-size:12.5px;line-height:1.6}.hls-ev-key dt{color:#9a8c78;margin:0}.hls-ev-key dd{margin:0;color:#4a443d;word-break:keep-all}
.hls-role{display:inline-block;margin-left:8px;font-size:10.5px;padding:2px 7px;border-radius:10px;background:#f1ece3;color:#6e665b;vertical-align:1px}.hls-role-llm{background:#fdf0ec;color:#a3342f}.hls-role-score{background:#eef4ee;color:#3f6b4a}.hls-role-link{background:#f3f1ee;color:#8b8178}
.ux-evidence-candidates tr.hls-more-toggle td{text-align:center;padding:10px}.hls-cond-raw{display:block;font-size:10px;color:#a09587;margin-top:2px}
.hls-fact-links{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin-top:6px;font-size:11px}.hls-fact-role{color:#6e665b;background:#f1ece3;padding:2px 7px;border-radius:10px;font-size:10.5px}.hls-fact-note{margin-top:8px}.hls-hero-tail{display:block;font-size:11px;color:#a09587;margin:-2px 0 6px}`;
  const st = root.document.createElement('style'); st.textContent = css; root.document.head.appendChild(st);
})(typeof window !== 'undefined' ? window : globalThis);
