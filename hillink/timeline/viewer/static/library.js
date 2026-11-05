// 페르소나 라이브러리 — CL-1024-14 전면 재구성. 주 분류는 '고객 유형' 하나.
//   1단계: 유형 아이콘 선택 → 2단계: 유형별 고객 목록(유형 썸네일 카드) → 고객 상세 → 고객흐름 재현.
//   공개 대상 = 실제 프로파일이 있는 고객만(예비 후보 · 프로파일 없는 자리 채우기 · 비공개 QA 신규 고객은 화면에 올리지 않음 · 자료는 그대로 보존).
//   재현 가능 여부는 카드 상태(빨간 '재현불가')로만 보이고 별도 목록으로 나누지 않는다. 판정은 실제 실행 계약(/api/turn/meta 의 고객 목록)과 같다.
//   자료: /api/library/personas(서버가 게시 승인 + 화면용 프로파일 고객만 병합해 줌) · /api/turn/meta(엔진 성향) · static/persona_thumbs/manifest.json(유형 썸네일 · 아이콘, 파일 이름 매칭)
const LIBV = { data: null, reviews: null, type: null, q: "", open: null, hl: new Set(), scroll: 0, assets: null, publish: null, publishTest: null };
const LIB_TYPES = ["가족 · 영유아", "가족 · 부모 동반", "커플 · 기념일", "혼자 휴식", "친구 모임", "업무 · 출장", "미식", "웰니스", "스포츠 목적", "행사 체험", "혜택 · 멤버십"];
// 유형 설명(화면 문구 · 고객 개인 정보 아님)
const LIB_TYPE_DESC = {
  "가족 · 영유아": "어린 자녀와 함께 머무는 가족 방문", "가족 · 부모 동반": "부모님과 함께하는 가족 여행", "커플 · 기념일": "둘이 함께하는 휴식 · 기념 방문",
  "혼자 휴식": "혼자 쉬고 회복하는 체류", "친구 모임": "친구와 함께 즐기는 호캉스", "업무 · 출장": "출장 · 업무 중의 숙박",
  "미식": "식사와 주류 경험이 방문 이유", "웰니스": "수영 · 요가 · 산책 같은 회복 활동", "스포츠 목적": "골프 등 운동이 방문 목적",
  "행사 체험": "와인페어 같은 행사 참여", "혜택 · 멤버십": "패키지 · 멤버십 혜택을 따져 고르는 방문",
};
// 개발 그룹 고객의 대표 유형(표시 전용 · ID · 엔진 입력은 그대로) — 근거가 없는 고객은 유형을 정하지 않는다
const LIB_TYPE_FIX = {
  blog41: { type: "커플 · 기념일", label: "커플 동행 · 기념일 미확인", facets: { companion: "couple", companion_status: "confirmed", anniversary_visit: "unconfirmed" /* 추후 '커플 동행' · '기념일 방문' 분리용 */ }, basis: "커플 동행은 확인(사용자 10/24) · 기념일 방문 근거는 없음 — 유형 탐색은 '커플' 범주에 두되 기념일로 표시하지 않음" },
  blog43: { type: null, label: "휴식 · 동행 미확인", basis: "기존 요약에 휴식 경험이 있으나 동행 인원은 원문 대조 전 — 혼자 방문한 것으로 분류하지 않음" },
  blog42: { type: null, basis: "프로파일에 동행 관계 · 방문 목적이 없음(시설 정보로 관계를 추정하지 않음) — 유형 확인 중" },
};
const LIB_CLAIM = { analyst_inference: "분석 추론", observed: "관측", author_report: "작성자 보고" };
// 행동 단계 코드(일부 프로파일은 영문 코드) → 화면 이름
const LIB_STAGE = { consumption_reported: "이용 · 소비", participation_reported: "참여", purchase_reported: "구매", reservation_reported: "예약", order_reported: "주문", not_applicable: "기타" };
const libStage = st => LIB_STAGE[st] || (st && !/^[a-z_]+$/.test(st) ? st : "행동");
const LIB_LINK = { confirmed: "같은 방문 확인", inferred: "같은 방문 추정", unlinked: "연결 미확인" };

async function libLoad() {
  if (!LIBV.data) {   // CL-1024-16 — 서버가 게시 승인 + 화면용 프로파일이 있는 고객만 골라서 준다(원본 파일은 정적 경로로 열리지 않음)
    const j = await api("/api/library/personas");
    LIBV.data = { about: j.about, sources: j.sources || {}, status_legend: j.status_legend, personas: j.personas || [] };
    LIBV.publish = { mode: j.publish && j.publish.mode, basis: j.publish && j.publish.basis, approved: (j.publish && j.publish.approved) || {} }; LIBV.hiddenCounts = j.hidden || {};
  }
  if (!LIBV.reviews) { try { LIBV.reviews = (LIB && LIB.review_list) || (await api("/api/library")).review_list || []; } catch (e) { LIBV.reviews = []; } }
  if (typeof AG !== "undefined" && !AG.meta) { try { AG.meta = await api("/api/turn/meta"); } catch (e) {} }
  if (!LIBV.localTried) {   // 로컬 전용(저장소 밖) — 비공개 보관 프로파일 · 검증된 원문 링크. 없으면 그대로 진행
    LIBV.localTried = true;
    // 로컬 프로파일 병합은 서버(/api/library/personas)가 한다
    try { const r = await fetch("/static/persona_experiments.json", { cache: "no-cache" }); if (r.ok) LIBV.exp = await r.json(); } catch (e) {}
  }
  await libLinksLoad();
  if (!LIBV.displayReview) { try { LIBV.displayReview=(await api('/api/library/display-review')).customers||{}; } catch(e) { LIBV.displayReview={}; } }
  if (!LIBV.assets) { try { const r = await fetch("/static/persona_thumbs/manifest.json", { cache: "no-cache" }); LIBV.assets = r.ok ? await r.json() : {}; } catch (e) { LIBV.assets = {}; } }
  if (typeof AG !== "undefined" && !AG.avm) { try { const r = await fetch("/static/avatars/manifest.json", { cache: "no-cache" }); AG.avm = r.ok ? await r.json() : {}; } catch (e) { AG.avm = {}; } }   // P3 — 인원 기반 공용 아바타
  if (!LIBV.cat) { try { const j = await api("/api/library/catalog"); LIBV.cat = (j && j.customers) || []; } catch (e) { LIBV.cat = []; } }   // CL-37 P7 — 열람 전용 고객(시뮬레이션 준비 중)
  if (!LIBV.gal) { try { const j = await api("/api/library/gallery"); LIBV.gal = (j && j.cards) || []; } catch (e) { LIBV.gal = []; } }   // CL-1025-37 — 시각 초안 갤러리(서버가 로컬 시연 모드에서만 줌)
}
// CL-1024-15 §7 — 원문(작성자) 링크는 검수자 보기('개발 정보' 켬)에서만 불러오고 화면에 넣는다. 꺼져 있으면 링크 표를 받지도 않는다(HTML · 네트워크에 없음)
// CL-1025-37 P2 — 원문 링크 복원: CL-1024-15(3a0d101)에서 화면 쪽 '개발 정보' 토글 뒤로 숨겨졌던 것을 되돌린다. 권한 판정은 서버(reviewer_ok: 로컬 검수 환경 · 공개 배포 아님 · 루프백)만 한다 —
//   서버가 링크를 주지 않으면(403 · 공개 배포) 링크를 만들지 않고 '원문 연결 확인 중'으로 표시한다.
const libLinksAllowed = () => true;
async function libLinksLoad() {
  if (!LIBV.access) { try { LIBV.access = await api("/api/access"); } catch(e) { return; } }
  if (!LIBV.access.reviewer) { LIBV.links = null; LIBV.linksDenied = true; return; }
  if (!libLinksAllowed()) { LIBV.links = null; if (LIBV.reviews) LIBV.reviews = LIBV.reviews.map(({ link, ...r }) => r); return; }
  // CL-1024-16 — '개발 정보' 는 요청만 하고, 실제로 줄지는 서버가 정한다(로컬 검수 환경일 때만 · 아니면 403)
  if (!LIBV.links && !LIBV.linksDenied) { try { const r = await fetch("/api/library/links", { cache: "no-cache" }); if (r.ok) LIBV.links = await r.json(); else LIBV.linksDenied = true; } catch (e) { LIBV.linksDenied = true; } }
  if (LIBV.links && LIBV.reviews && !LIBV.reviews.some(r => r.link)) { try { LIBV.reviews = (await api("/api/library")).review_list || LIBV.reviews; } catch (e) {} }
}
document.addEventListener("click", ev => { if (!ev.target.closest || !ev.target.closest("#btnDev")) return; setTimeout(async () => { await libLinksLoad(); if (typeof MODE !== "undefined" && MODE === "library" && LIBV.data) (LIBV.situation ? situationRender() : LIBV.open ? libDetail(LIBV.open) : libGrid()); }, 0); });
// 원문 링크 — 검증된 수집 표의 post_id 로만 찾는다(작성자 ID 로 다른 글 · 검색 결과를 대신 열지 않음)
const libUrl = pid => (pid && LIBV.links && LIBV.links.links && LIBV.links.links[pid]) || null;
const libDevRv = p => { if (!libLinksAllowed()) return null; const r = (LIBV.reviews || []).find(x => x.blog === p.id); return r && r.link ? { url: r.link, title: r.name } : null; };
const libStartUrl = p => (LIBV.links && LIBV.links.start && LIBV.links.start[p.id]) || libUrl(p.start_post) || (p.group === "dev" ? libDevRv(p) : null);
// 아동 · 건강 정보가 있는 문장은 화면에 쓰지 않는다
const LIB_SENS = /영아|아기|아이|유아|자녀|딸|아들|유모차|카시트|육아|임신|임산|출산|산후|모유|건강|진단|의학|병원|돌잔치/;
const libTitle = u => !u || !u.title ? "" : LIB_SENS.test(u.title) ? "제목 비표시(개인 건강 · 아동 정보 포함)" : idTxt(u.title);
const libA = (u, label, cls = "") => u && u.url ? `<a class="lib-src ${cls}" href="${esc(u.url)}" target="_blank" rel="noopener" title="${esc(libTitle(u) || "원문 후기 · 새 탭")}">${label}</a>` : "";
const libP = id => window.HillinkPrivateIntake?.get(id) || LIBV.data.personas.find(p => p.id === id);
const libEng = id => (typeof AG !== "undefined" && AG.meta ? AG.meta.personas.find(p => p.id === id) : null);
const libRuntime = id => Boolean(libEng(id));
const libShort = (t, n) => (t || "").length > n ? t.slice(0, n - 1) + "…" : (t || "");
const libSafe = t => t && !LIB_SENS.test(t) && !/제한 공유|검수 자료 참조/.test(t) ? t : "";

// ---------------------------------------------------------------- 공개 · 유형 · 카드 문구
const libTypeLabel = p => (LIB_TYPE_FIX[p.id] && LIB_TYPE_FIX[p.id].label) || libTypeOf(p) || "유형 확인 중";
function libTypeOf(p) { const f = LIB_TYPE_FIX[p.id]; if (f) return f.type; return LIB_TYPES.includes(p.type_group) ? p.type_group : null; }
function libHasProfile(p) { return Boolean((p.audit && (p.traits || []).length) || (p.engine && p.engine.n > 0)); }
function libDevName(p) { if (p.group !== "dev") return ""; const r = (LIBV.reviews || []).find(x => x.blog === p.id); return r ? (r.name || "").replace(/^(\[자동\]\s*)?blog\d+\w*\s*·?\s*/, "") : ""; }
// 카드 한 줄 — 프로파일 요약(label) → 첫 성향 → 개발 그룹은 방문 요약. 아동 · 건강 문장은 건너뛴다
function libLine(p) {
  const reviewed=libSafe(LIBV.displayReview?.[p.id]?.changes.list_line);
  if(reviewed)return reviewed;
  if(typeof p.display_list_line === "string")return libSafe(p.display_list_line);
  return libSafe(p.label) || (p.traits || []).map(t => libSafe(t.trait)).find(Boolean) || libSafe(libDevName(p)) || "";
}
// CL-1024-15 — 세 상태를 따로 판정: has_profile(화면용 실제 프로파일) · publish_approved(게시 승인 목록) · is_runnable(실행 계약). 게시 = has_profile && publish_approved
// LIBV.publishTest 는 QA 시험용 메모리 설정(파일에 쓰지 않음) — { id: true|false }
function libApproved(id) { const T = LIBV.publishTest; if (T && Object.prototype.hasOwnProperty.call(T, id)) return Boolean(T[id]); return Boolean(LIBV.publish && LIBV.publish.approved && LIBV.publish.approved[id]); }   // 서버가 이미 거른 목록 위에 화면에서 한 번 더 확인

function libState(p) { return { has_profile: libHasProfile(p), publish_approved: libApproved(p.id), is_runnable: libRuntime(p.id) }; }
function libPublished(p) { const s = libState(p); return s.has_profile && s.publish_approved; }
function libPub() { return LIBV.data.personas.filter(libPublished); }
// 공개하지 않는 항목과 이유(보고 · QA 용 — 화면에는 숫자만)
function libHidden() {   // 숨긴 고객은 서버가 내용을 보내지 않는다 — 사유별 수만
  return Object.entries(LIBV.hiddenCounts || {}).map(([why, n]) => ({ why, n }));
}
function libTopBars(id, n) { const e = libEng(id); return e ? e.bars.filter(b => b.status === "observed").sort((a, b) => b.level - a.level).slice(0, n) : []; }
function libKw(p, n) {
  const bars = libTopBars(p.id, n).map(b => b.label.replace(/ · 분위기$/, ""));
  return bars.length ? bars : (p.traits || []).slice(0, n).map(t => libShort(t.trait.split(/[·,+]/)[0].trim(), 12)).filter(x => x && !LIB_SENS.test(x));
}
// 유형 썸네일(2단계 · 카드 · 상세) / 유형 아이콘(1단계) — 파일 이름 매칭 목록에서만. 없으면 같은 모양의 임시 표지(호텔 시설 사진으로 대체하지 않음)
const libAssetUrl = (kind, t) => { const it = LIBV.assets && LIBV.assets[kind] && LIBV.assets[kind].items && LIBV.assets[kind].items[t]; return it ? `/static/${kind === "thumbs" ? "persona_thumbs" : "type_icons"}/${encodeURIComponent(it)}` : null; };
const LIB_ICON = {   // 임시 아이콘(24 격자 선 그림) — type_icons/ 에 '유형명_아이콘' 파일이 들어오면 그 파일을 쓴다
  "가족 · 영유아": '<circle cx="9" cy="19" r="1.6"/><circle cx="17" cy="19" r="1.6"/><path d="M4 5h2l2.2 9h9.3l1.5-6H7.3"/><path d="M12 8V4.5a4 4 0 0 1 4 4"/>',
  "가족 · 부모 동반": '<circle cx="6" cy="7" r="2.2"/><circle cx="18" cy="7" r="2.2"/><circle cx="12" cy="9" r="1.8"/><path d="M2.5 20v-3.5A3.5 3.5 0 0 1 6 13a3.5 3.5 0 0 1 3.2 2M21.5 20v-3.5A3.5 3.5 0 0 0 18 13a3.5 3.5 0 0 0-3.2 2M9 20v-2.5a3 3 0 0 1 6 0V20"/>',
  "커플 · 기념일": '<path d="M12 20s-7-4.3-7-9.5A3.8 3.8 0 0 1 12 8.3a3.8 3.8 0 0 1 7 2.2C19 15.7 12 20 12 20z"/><path d="M17.5 3.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z"/>',
  "혼자 휴식": '<path d="M17 14.5A7 7 0 0 1 9.5 7a7 7 0 0 0 .5-3 8 8 0 1 0 9.8 9.8 7 7 0 0 1-2.8.7z"/>',
  "친구 모임": '<path d="M7 3h5l-.6 6.2a2 2 0 0 1-3.8 0zM9.5 11v7M7 20h5"/><path d="M14.5 6h5l-.6 6.2a2 2 0 0 1-3.8 0zM17 14v4.5M14.8 20.5h4.4"/>',
  "업무 · 출장": '<rect x="3" y="7" width="18" height="12" rx="2"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3 12.5h18M11 12.5v2h2v-2"/>',
  "미식": '<path d="M3 17h18M5 17a7 7 0 0 1 14 0M12 8.5V7M10 20h4"/>',
  "웰니스": '<path d="M12 20c-4.5-1.5-7-5-7-9 3 0 5.5 1.5 7 4 1.5-2.5 4-4 7-4 0 4-2.5 7.5-7 9z"/><path d="M12 15c-1.6-2.2-1.6-6.3 0-10 1.6 3.7 1.6 7.8 0 10z"/>',
  "스포츠 목적": '<path d="M8 21V3l9 3.5L8 10"/><path d="M4 21h11"/><circle cx="17.5" cy="18.5" r="1.5"/>',
  "행사 체험": '<path d="M8 3h8l-.8 6a3.2 3.2 0 0 1-6.4 0zM12 12.2V19M9 21h6"/><path d="M19.5 3.5v3M18 5h3M4.5 12v2.5M3.25 13.25h2.5"/>',
  "혜택 · 멤버십": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10h18M6.5 14.5h4"/><path d="M16 13.2l.7 1.3 1.4.2-1 1 .2 1.4-1.3-.7-1.3.7.2-1.4-1-1 1.4-.2z"/>',
  "전체": '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
};
function libIcon(t, size = 40) {
  const u = t !== "전체" && libAssetUrl("icons", t);
  return u ? `<img class="lb-icimg" src="${u}" alt="" width="${size}" height="${size}">`
    : `<svg class="lb-icsvg" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${LIB_ICON[t] || LIB_ICON["전체"]}</svg>`;
}
function libThumb(t, cls = "") {
  const u = t && libAssetUrl("thumbs", t);
  return u ? `<div class="lb-th ${cls}"><img src="${u}" alt="${esc(t)} 유형 대표 이미지" loading="lazy"></div>`
    : `<div class="lb-th lb-th0 ${cls}" title="유형 썸네일 준비 중">${libIcon(t || "전체", 34)}<span>${esc(t || "유형 확인 중")}</span></div>`;
}
// P5 — 같은 유형 대표 사진을 두 고객이 함께 쓰면 고유 이미지가 아니다: 유형별 첫 고객(표시 번호 순)만 대표 사진, 나머지는 중립 표지(유형 아이콘 + 인원 아바타)
// CL-1025-37 P5 긴급 — 커플 · 기념일 No.0003 카드 표시 이미지(시연용 임시 표시 자산 · 동일인 미검증 · 사람 승인 대기). 프로필 · 유형 · 아바타 · 엔진 · ID 는 그대로.
const LIB_THUMB_OVERRIDE = { A03: { src: "/static/demo_thumbs/no0003_couple_room_temp.webp", sha256: "67b5bef5d7d26c5ed87767598688ef8c4ee0d21afe4c268856e0888fd5cbce71", status: "DISPLAY_ONLY_TEMP_CROSS_CUSTOMER_ASSET_REVIEW", alt: "커플 객실 휴식 대표 이미지(생성 이미지)" } };
function libThumbOwner(t) { const P = (LIBV.data ? libPub() : []).filter(p => libTypeOf(p) === t && !LIB_THUMB_OVERRIDE[p.id]).sort((a, b) => (dno(a.id) < dno(b.id) ? -1 : 1)); return P[0] ? P[0].id : null; }
function libThumbP(p, cls = "") {
  const t = libTypeOf(p), ov = LIB_THUMB_OVERRIDE[p.id];
  if (ov) return `<div class="lb-th ${cls}" data-thumb="override"><img src="${ov.src}" alt="${esc(ov.alt)}" loading="lazy"></div>`;
  if (t && libThumbOwner(t) === p.id) return libThumb(t, cls);
  return `<div class="lb-th lb-th0 lb-thn ${cls}" title="고유 대표 이미지 준비 전 — 같은 유형의 다른 고객과 같은 사진을 쓰지 않음">${typeof agAvatarIcon === "function" && dnoParty(p.id).n ? agAvatarIcon(p.id, dnoParty(p.id).n, 72) : libIcon(t || "전체", 40)}<span>${esc(t || "유형 확인 중")}</span></div>`;
}
const libNoRun = `<span class="lb-norun" title="이 환경에는 이 고객의 엔진 실행 입력이 없어 고객흐름에서 재현할 수 없습니다. 프로파일은 볼 수 있습니다.">재현불가</span>`;

async function libEnter() {
  const v = $("#libraryView");
  if (!LIBV.data) v.innerHTML = `<div class="lb"><div class="hint">불러오는 중…</div></div>`;
  try { await libLoad(); } catch (e) { v.innerHTML = `<div class="lb"><div class="callout">라이브러리를 불러오지 못했습니다 — ${esc(e.message)}</div></div>`; return; }
  if (location.hash.startsWith("#lib")) { libApplyRoute(location.hash); return; }
  LIBV.situation ? situationRender() : LIBV.draft ? libDraft(LIBV.draft) : LIBV.cOpen ? libCDetail(LIBV.cOpen) : LIBV.open ? libDetail(LIBV.open) : libGrid();
}
// ---------------------------------------------------------------- CL-1025-37 시각 초안 갤러리 — 고객별 고유 썸네일 초안(사람 승인 전) · 게시 승인 · 프로파일 · 실행과 별개
const LIB_GBASIS = { APP_LIBRARY: "", APP_LIBRARY_NON11: "", LP_CANDIDATE: "유형 후보", LP_REVIEW: "유형 검토 중", UNKNOWN: "" };
// CL-1025-37 P5 — 이미지 파일만 있고 화면용 프로필 · 원문 연결이 확인되지 않은 시각 초안은 일반 라이브러리에 내지 않는다(파일 · 목록은 그대로 보존 · '개발 정보'를 켠 내부 검수에서만)
const libInternal = () => typeof document !== "undefined" && document.body.classList.contains("devmode");
const libG = () => libInternal() ? (LIBV.gal || []) : [];
const libObs = cid => (typeof DS !== "undefined" && DS.story && DS.story.observations && DS.story.observations[cid]) || null;   // 시연 스토리의 후기 관측 요약(LP 검수 · 원문 아님)
const libGName = c => dno(c.card_id);   // P3 — 표시 카드 번호(LP 표시 ID · 카드 키는 기술 상세에만)
// CL-1025-37 P1 — 발표 모드(시연 스토리 단계 재생 중): 사진형 초안이 준비된 유형 · 고객만, 내부 상태 문자열 · 원장 수치는 '자료 상태 · 검증 상세' 로 접는다
const libPresent = () => typeof DS !== "undefined" && DS.on && !!DS.step;
const libPhoto = c => !!(c.image && /사진/.test(c.image.style || ""));
function libAudit(P, G) {
  return G.length ? `<details class="lb-audit"><summary>자료 상태 · 검증 상세 <span class="lb-chip">시각 자료 검수 중</span></summary><div class="lb-ledger"><b>카드 ${P.length + G.length}장 ≠ 검증 고객 ${P.length + G.length}명</b><span>행동 실행 검증 ${P.length}명 · 고객별 이미지 초안 ${G.length}장(사람 승인 0 · 사진형 ${G.filter(libPhoto).length} · 벡터 ${G.filter(c => c.image && !libPhoto(c)).length} · 비표시 ${G.filter(c => !c.image).length}) · 앱 고객 원장 63명 중 이미지와 ID 일치 26명(유형 충돌 10) · 이미지에만 있는 39명은 앱 ID 없음 · 원장에만 있는 37명</span></div></details>` : "";
}
// P3 — 인원 기반 공용 아바타 칩: 확인된 인원(후기 · 사용자 확인)만 그 인원수로, 미상은 중립 마커 + '동행 인원 확인 전'(1인으로 단정하지 않음)
function libAvChip(id) {
  const P = dnoParty(id);
  if (P.n && typeof agAvatarIcon === "function") return `<span class="lb-avc" title="동행 인원 출처: ${esc(P.origin === "REVIEW_OBSERVED" ? "후기 관측" : P.origin === "USER_CONFIRMED" ? "사용자 확인" : P.origin)}">${agAvatarIcon(id, P.n, 26)}<em>${P.n}인</em></span>`;
  return `<span class="lb-avc unk" title="동행 인원 확인 전 — 1인 방문으로 단정하지 않음"><svg viewBox="0 0 26 26" width="26" height="26" aria-hidden="true"><circle cx="13" cy="9" r="4.5" fill="#cbbda8"/><rect x="7.5" y="14" width="11" height="9" rx="4.5" fill="#cbbda8"/></svg><em>인원 확인 전</em></span>`;
}
function libPCard(c) {   // 발표용 사진 카드 — 이름 · 유형 · 검수 중 표시만
  return `<article class="lb-card lb-gcard lb-pcard" data-g="${esc(c.card_id)}" tabindex="0"><div class="lb-thw">${libGImg(c)}<span class="lb-gdraft">생성 이미지 · 검수 중</span>${libPD(c)}${libAvChip(c.card_id)}</div>
    <div class="lb-cb"><div class="lb-cid"><b>${esc(libGName(c))}</b><span class="lb-cty">${esc(c.type || "유형 확인 중")}</span></div>${libObs(c.card_id) ? `<p class="lb-line">${esc(libObs(c.card_id).title.split("·").slice(1).join("·").trim())}</p>` : ""}</div></article>`;
}
const libGIn = (c, t, UNK) => t === "전체" || (t === UNK ? !c.type : c.type === t);
const libGHit = (c, q) => !q || q.toLowerCase().split(/\s+/).filter(Boolean).every(w => [libGName(c), c.card_id, c.type || "유형 확인 중", c.display_id || ""].join(" ").toLowerCase().includes(w));
// 사진형 증분 36(2026-10-26) — 카드마다 이번 반영 상태: 새 사진 반영 / 사진 보류(사유) / 기존 사진 유지 · 사람 승인 전
const libPD = c => c.photo_delta ? `<span class="lb-pd ${esc(c.photo_delta.status.toLowerCase())}" title="${esc(c.photo_delta.reason || "")}">${esc(c.photo_delta.label)}</span>` : "";
// ---------------------------------------------------------------- CL-37 P7 — 열람 전용 고객(제품 원장 앱 ID ↔ 표시 번호 ↔ 고객별 썸네일 1:1 확인) · 시뮬레이션 준비 중
// 실행 승인 11명과 따로 센다(catalogue_visible ≠ engine_runnable). 실행 API 는 서버 허용 목록이 그대로 막는다. 프로필 독립 검수 전 · 이미지 사람 승인 전.
let libC = () => (LIBV.cat || []).map(c=>window.HLProfileDisplayReview.catalog(c,LIBV.displayReview?.[c.id]));
const libCName = c => dno(c.id);
const libCIn = (c, t, UNK) => t === "전체" || (t === UNK ? !c.type : c.type === t);
const libCHit = (c, q) => !q || q.toLowerCase().split(/\s+/).filter(Boolean).every(w => [libCName(c), dnoS(c.id), c.type || "유형 확인 중", c.summary || "", c.visit || ""].join(" ").toLowerCase().includes(w));
const libCScenes = () => new Set(libC().map(c => c.scene));
function libCImg(c, cls = "") {
  return c.image ? `<div class="lb-th lb-gth ${cls}"><img src="${esc(c.image.src)}" alt="${esc(libCName(c))} 고객 썸네일(생성 이미지)" loading="lazy"></div>`
    : `<div class="lb-th lb-th0 lb-thn ${cls}" title="${esc(c.image_withheld || "이미지 준비 중")}">${libIcon(c.type || "전체", 40)}<span>${esc(c.type || "유형 확인 중")}</span></div>`;
}
const libCSoon = c => libEng(c.id)?.isolated_qa ? `<button type="button" class="cf-btn cf-sm" data-private-run="${esc(c.id)}">검수용 시뮬레이션</button>` : `<button type="button" class="cf-btn cf-sm lb-soon" disabled title="현재 환경에 검증된 실행 입력이 등록되지 않았습니다">시뮬레이션 준비 중</button>`;
function libCCard(c) {
  return `<article class="lb-card lb-ccard" data-c="${esc(c.id)}" tabindex="0"><div class="lb-thw">${libCImg(c)}<span class="lb-thid">${esc(libCName(c))}</span>${c.image ? `<span class="lb-gdraft">생성 이미지 · 검수 중</span>` : ""}${libAvChip(c.scene)}</div>
    <div class="lb-cb"><div class="lb-cid"><b>${esc(libCName(c))}</b><span class="lb-cty">${esc(c.type || "유형 확인 중")}</span><span class="lb-ro">${libEng(c.id)?.isolated_qa?"비공개 실행 가능":"열람 전용"}</span></div>
      <p class="lb-line">${c.summary ? escP(c.summary) : `<span class="lb-prep">프로필 정리 중</span>`}</p>${c.visit ? `<div class="lb-cvis" title="${esc(c.visit)}">후기 속 방문 · ${esc(c.visit)}</div>` : ""}
      <div class="lb-cact"><button type="button" class="cf-btn cf-sm" data-cp="${esc(c.id)}">프로필 보기</button>${libCSoon(c)}</div></div></article>`;
}
function libCDetail(id) {
 const c=libC().find(x=>x.id===id);if(!c){LIBV.cOpen=null;return libGrid();}
 const notes=[...(c.visit?[c.visit]:[]),...(c.notes||[])].filter(Boolean);
 const section=(eyebrow,title,body)=>`<section class="lb-sec pvx-sec"><div class="lb-sh"><span class="pv2-eyebrow pvx-eyebrow">${eyebrow}</span><h3>${title}</h3></div>${body}</section>`;
 const no=(msg,choice=false)=>`<p class="pvx-readonly-note${choice?' pvx-choice-sentence':''}">${msg}</p>`;
 const experiences=notes.length?`<div class="pvx-magazine" data-profile-layout="text" data-image-count="0"><div class="pv3-compact-list pvx-mag-text">${notes.map(n=>`<article class="pv3-compact-event"><small class="pv3-event-meta">기존 방문 메모 · 독립 검수 전</small><h4>${esc(libShort(n,42))}</h4>${n.length>42?`<details><summary>기록 내용</summary><p>${esc(n)}</p></details>`:''}</article>`).join('')}</div></div>`:no('현재 표시 가능한 방문 메모가 없습니다. 고객의 행동이나 선호를 추정해 채우지 않습니다.');
 $("#libraryView").innerHTML=`<div class="lb lb-det pv3-profile pvx-profile pvx-readonly"><div class="lb-crumb"><button type="button" class="cf-btn cf-sm" id="libBack">← ${esc(LIBV.type&&LIBV.type!=='전체'?LIBV.type:'목록')}</button><span class="lb-path">페르소나 라이브러리 › <b>${esc(libCName(c))}</b></span></div>
 <section class="lb-hero pvx-hero">${libCImg(c,'lb-hth')}<div class="lb-hb"><div class="lb-hk">${libAvChip(c.scene)}<span class="lb-cty">${esc(c.type||'유형 확인 중')}</span><span class="lb-ro">${libEng(c.id)?.isolated_qa?'비공개 실행 가능':'열람 전용'}</span></div><h2>${esc(libCName(c))}</h2><p class="lb-hline">${esc(c.summary||'후기 방문 메모를 확인하는 고객 프로필')}</p><p class="pvx-readonly-note">현재 공개된 방문 메모 범위에서 살펴봅니다. 프로필 독립 검수와 성향 연결은 아직 완료되지 않았습니다.</p><div class="lb-cact">${libCSoon(c)}</div><div class="pvx-hfoot"><span>${esc(c.visit||'방문 형태 확인 전')}</span><span>대표 이미지는 생성 이미지 · 검수 중</span></div></div></section>
 ${section('CHOICE SIGNATURE','대표적인 선택 방식',no(c.display_signature&&c.display_signature!==c.summary?esc(c.display_signature):'대표적인 선택 방식을 판단할 연결 근거는 검수 중입니다. 목록용 방문 요약을 반복 성향으로 대신 표시하지 않습니다.',true))}
 <section class="lb-sec pvx-sec" id="libExperiences"><div class="lb-sh"><span class="pv2-eyebrow pvx-eyebrow">MOMENTS &amp; CHOICES</span><h3>이 고객의 실제 행동</h3><span>현재 공개된 방문 메모 · 행동 근거 연결 전</span></div>${experiences}</section>
 ${section('TRAITS &amp; PATTERNS','반복 성향과 패턴',no('반복 성향을 뒷받침하는 Fact 연결과 관측 횟수가 이 화면에 제공되지 않았습니다. 유형이나 방문 메모를 성향 점수로 바꾸지 않습니다.'))}
 ${section('IF THE SITUATION CHANGES','어떤 상황에서 선택이 달라지나',no('조건별 선택을 설명할 검증된 연결 자료가 아직 없습니다.'))}
 ${section('REVIEW EVIDENCE','후기 근거 찾아보기',`<details><summary>자료와 확인 범위</summary>${no('기존 방문 메모를 보존했습니다. 이 프로필에 승인된 원문 주소와 Fact 대응표는 아직 연결되지 않았습니다.')}<p class="pvx-readonly-note">${esc(c.type_note||'동행 관계와 세부 방문 목적을 추정하지 않습니다.')}</p></details><details id="libFlowD"><summary>실제 경험이 선택으로 이어지는 과정 <span>연결 근거 확인 범위</span></summary><div class="lib-flow" id="libFlowBody"><div class="lib-fs"><span class="lib-fn">1</span><div class="lib-fh">후기에서 관측한 경험</div><p>${esc(notes[0]||'공개된 방문 메모 없음')}</p><small>기존 메모 · 원문 대조 전</small></div><div class="lib-farr" aria-hidden="true">→</div><div class="lib-fs"><span class="lib-fn">2</span><div class="lib-fh">추출한 성향과 판단 기준</div><p>연결 Fact·반복 관측을 확인하기 전입니다.</p></div><div class="lib-farr" aria-hidden="true">→</div><div class="lib-fs win"><span class="lib-fn">3</span><div class="lib-fh">가상 선택 또는 조건부 판단</div><p>현재 프로필에서 가상 선택을 계산하지 않았습니다. 관측 사실로 표시하지 않습니다.</p></div></div></details>`)}
 </div>`;
 $("#libBack").onclick=()=>{LIBV.cOpen=null;libGrid();};$("#libraryView").scrollTop=0;
}

function libGImg(c, cls = "") {
  return c.image ? `<div class="lb-th lb-gth ${cls}"><img src="${esc(c.image.src)}" alt="${esc(libGName(c))} 고객 고유 썸네일 초안" loading="lazy"></div>`
    : `<div class="lb-th lb-th0 lb-gph ${cls}" title="${esc(c.image_withheld || "이미지 준비 중")}">${libIcon(c.type || "전체", 30)}<span>이미지 비표시 · 참고용</span></div>`;
}
function libGCard(c) {
  const b = LIB_GBASIS[c.type_basis];
  return `<article class="lb-card lb-gcard" data-g="${esc(c.card_id)}" tabindex="0"><div class="lb-thw">${libGImg(c)}<span class="lb-thid">${esc(libGName(c))}</span><span class="lb-gdraft">시각 초안</span>${libPD(c)}${libAvChip(c.card_id)}</div>
    <div class="lb-cb"><div class="lb-cid"><b>${esc(libGName(c))}</b><span class="lb-cty">${esc(c.type || "유형 확인 중")}</span>${b ? `<span class="lb-gb">${b}</span>` : ""}</div>
      <div class="lb-gst"><span class="${c.fact_review === "EVIDENCE_READY" ? "" : "warn"}">${c.fact_review === "EVIDENCE_READY" ? "검수 중" : "참고용 · 사실 재확인"}</span>${c.image ? `<span>${esc(c.image.qa_label)}</span><span>${esc(c.image.style)}</span>` : ""}</div>
      ${c.fact_note ? `<p class="lb-gnote">${esc(c.fact_note)}</p>` : ""}
      <div class="lb-gav">아바타: 동행 확인 전 · 중립 표시 유지</div>
      <div class="lb-cact"><button type="button" class="cf-btn cf-sm" data-gd="${esc(c.card_id)}">초안 정보</button><button type="button" class="cf-btn cf-sm" disabled title="실행 허용 목록 밖 — 행동 시뮬레이션 검증 중">행동 시뮬레이션 검증 중</button></div></div></article>`;
}
function libDraft(cid) {
  const c = libG().find(x => x.card_id === cid); if (!c) { LIBV.draft = null; return libGrid(); }
  const b = LIB_GBASIS[c.type_basis], ob = libObs(c.card_id);
  const rows = [["카드", c.card_id], ["유형", `${c.type || "유형 확인 중"}${b ? ` (${b} · 공식 분류 아님)` : ""}`],
    ["이미지", c.image ? `${c.image.qa_label} · ${c.image.style} · 사람 승인 전 · 실제 고객 사진 아님` : (c.image_withheld || "이미지 비표시")],
    ["사실 검토", c.fact_review === "EVIDENCE_READY" ? "근거 확인 · 화면 프로파일 연결 전" : (c.fact_note || "사실 재확인 중")],
    ["아바타", "동행 · 인원 런타임 확인 전(AVATAR_REVIEW_PENDING) — 기존 중립 표시 유지"],
    ["게시 · 프로파일", "게시 승인 없음 · 화면용 프로파일 미연결"],
    ["행동 엔진", ob ? ob.engine : "실행 허용 목록 밖 — 실행 전"]];
  const conf = ob ? ob.lines.filter(l => /LP/.test(l.src)) : [], ctx = ob ? ob.lines.filter(l => !/LP/.test(l.src)) : [];
  const unk = ob ? [...(ob.unknown || []), ...(ob.cautions || []).filter(x => !(ob.unknown || []).includes(x))] : ["후기 요약이 아직 화면에 연결되지 않았습니다"];
  const facts = ob ? ob.lines.flatMap(l => l.facts || []) : [];
  const col = (k, h, items, note) => `<section class="lb-dc ${k}"><h3>${h}</h3>${items.length ? `<ul>${items.join("")}</ul>` : `<p class="lb-dnone">${note}</p>`}</section>`;
  $("#libraryView").innerHTML = `<div class="lb lb-det lb-gdet"><div class="lb-crumb"><button type="button" class="cf-btn cf-sm" id="libBack">← ${esc(LIBV.type && LIBV.type !== "전체" ? LIBV.type : "목록")}</button><span class="lb-path">페르소나 라이브러리 › <b>${esc(libGName(c))}</b></span></div>
    <section class="lb-hero lb-ghero">${libGImg(c, "lb-hth")}<div class="lb-hb"><div class="lb-hk">${libAvChip(c.card_id)}<span class="lb-cty">${esc(c.type || "유형 확인 중")}</span><span class="ds-k img">생성 이미지 · 검수 중</span>${ob ? `<span class="ds-k obs">후기 관측</span>` : ""}</div>
      <h2>${esc(libGName(c))}${ob ? ` · ${esc(ob.title.split("·").slice(1).join("·").trim())}` : ""}</h2>
      <p class="lb-gsum">${ob ? "후기에서 확인한 경험과, 아직 확인하지 못한 것을 나눠서 봅니다." : "고객별 이미지 초안입니다. 후기 요약은 아직 화면에 연결되지 않았습니다."}</p>
      <div class="lb-gstat"><span>행동 엔진 실행 전</span><span>실제 고객 사진 아님</span></div></div></section>
    <div class="lb-d3">${col("ok", "확인된 경험", conf.map(l => `<li>${esc(l.text)}</li>`), "화면용 요약 준비 중")}
      ${col("ctx", "관찰된 맥락", ctx.map(l => `<li>${esc(l.text)}<em>${esc(l.src.replace(/\(.*?\)/, "").trim())}</em></li>`), "추가 맥락 없음")}
      ${col("unk", "아직 모르는 것", unk.map(x => `<li>${esc(x)}</li>`), "")}</div>
    <details class="lb-tech"><summary>기술 상세 <span>카드 · 검수 상태 · 사실 ID · 엔진</span></summary><dl class="lb-hfacts">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("")}${facts.length ? `<div><dt>사실 ID</dt><dd>${facts.map(f => `<code>${esc(f)}</code>`).join(" ")}</dd></div>` : ""}</dl></details></div>`;
  $("#libBack").onclick = () => { LIBV.draft = null; libGrid(); };
  $("#libraryView").scrollTop = 0;
}
// 행사 환경 카드 — 소연 시즌 행사 정리표(PR #92 · 169행) 근거 행 그대로. 실행은 엔진이 지원하는 와인페어만
const LIB_EVENTS = [
  { id: "WINE_FAIR_2026_AUTUMN", name: "2026 가을 와인페어 '구름 위의 산책'", period: "2026-10-10~11 · 17~18 · 24~25 (1부 11:00~15:00 · 2부 15:30~20:00)", who: "외부 입장권 · 패키지 투숙객 입장 포함(상품별)", grade: "공식", src: "정리표 행 81 · PR #71 1-1", mode: "고객흐름 실행 가능(엔진 2부 창만) · 행사일 포레스트 파크 일반 이용 제한", run: true, show: "10/24 행사일 하루를 저장된 엔진 실행으로 재생", note: "행사는 10/25에 끝났습니다 — 지금 진행 중인 행사가 아닙니다" },
  { id: "SANTA_KIDS_VILLAGE_2025", name: "2025 산타 키즈 빌리지", period: "2025-12-19~25 · 하루 4부", who: "가족 · 아동 동반(입장권 · 연계 패키지)", grade: "보도 기사", src: "정리표 행 64", mode: "설명 카드(PREVIEW_ONLY) — 엔진에 행사 없음", note: "가족 · 아동 동반 행사 — 와인페어와 대상이 다른 과거 시즌 예시(2026 일정 미확인)" },
  { id: "PIZZA_HILL_GOLDEN_NIGHT_2026", name: "2026 피자힐 골든 나이트", period: "보도자료 기준 9/18까지 목 · 금 · 시작일 · 시각 미확인", who: "요금 · 대상 미확인", grade: "공식 보도자료 · 요금 미확인", src: "정리표 행 99 · PR #71 1-3", mode: "설명 카드(PREVIEW_ONLY) — 엔진에 행사 없음", note: "과거 행사 · 메뉴값 · 포장 비교 아님" },
  { id: "SAVORING_SUMMER_NIGHT_2026", name: "2026 리버파크 Savoring Summer Night", period: "투숙 2026-07-17~08-30 금 · 토 · 일 · 리버파크 2부", who: "해당 패키지 고객만(일반 투숙객 자유 참여 아님)", grade: "공식", src: "정리표 행 132 · 125 · PR #71 1-2", mode: "설명 카드(PREVIEW_ONLY) — 엔진은 10월 리버파크 비운영", note: "계절 · 이용 자격이 다른 과거 시즌" },
];
function libEvents() {
  const evc = (e, main) => `<div class="lb-evc${main ? " main" : ""}"><div class="lb-evk">${e.run ? `<span class="ds-k rep">저장된 실행으로 보기</span>` : `<span class="ds-k pre">행사 미리보기 · 엔진 결과 아님</span>`}</div><b>${esc(e.name)}</b><dl><div><dt>기간</dt><dd>${esc(e.period)}</dd></div><div><dt>대상</dt><dd>${esc(e.who)}</dd></div>${main ? `<div><dt>시연</dt><dd>${esc(e.show)}</dd></div>` : ""}</dl><p>${esc(e.note)}</p>
      <details class="lb-evsrc"><summary>근거</summary>${esc(e.grade)} · ${esc(e.src)} · ${esc(e.mode)}</details>
      ${e.run ? `<button type="button" class="cf-btn cf-sm cf-primary" data-evrun="${e.id}">고객흐름에서 와인페어일 보기</button>` : ""}</div>`;
  const [m, cmp, ...rest] = LIB_EVENTS;
  const body = `<div class="lb-evg2">${evc(m, true)}${evc(cmp)}</div><details class="lb-evmore"><summary>다른 시즌 행사 ${rest.length}개 더 보기</summary><div class="lb-evg">${rest.map(e => evc(e)).join("")}</div></details>`;
  if (LIBV.evOnly && libPresent()) return `<section class="lb-ev lb-evonly"><div class="lb-s1h"><h3>행사 환경</h3><span>행사가 열렸다는 사실은 고객이 참여했다는 근거가 아닙니다</span></div>${body}</section>`;
  return `<details class="lb-sit lb-ev"${LIBV.evOpen ? " open" : ""}><summary>행사 환경 카드 <span>시즌 행사 정리표 근거 · 행사 개최는 고객 참여 근거가 아님</span></summary>${body}</details>`;
}
// 검색 — ID · 유형 · 한 줄 특징 · 성향 키워드(보조 성향은 여기서 쓴다)
function libSearchHit(p, q) {
  if (!q) return true;
  const hay = [p.id, dno(p.id), libTypeOf(p) || "", libLine(p), ...libKw(p, 5), ...(p.traits || []).map(t => t.trait)].join(" ").toLowerCase();
  return q.toLowerCase().split(/\s+/).filter(Boolean).every(w => hay.includes(w));
}

// ---------------------------------------------------------------- 1 · 2단계 — 유형 선택 / 유형별 고객 목록
function libGrid() {
  LIBV.open = null;
  const P = libPub(), nRun = P.filter(p => libRuntime(p.id)).length, nPriv = P.filter(p => libRuntime(p.id) && libEng(p.id)?.isolated_qa).length;   // counts come from the engine meta / private registry, never fixed numbers
  const UNK = "유형 확인 중", inType = (p, t) => t === UNK ? !libTypeOf(p) : libTypeOf(p) === t;
  const CS = libCScenes(), G = libG().filter(c => !CS.has(c.card_id)), C = LIBV.runOnly ? [] : libC();   // P7 — 열람 전용 고객과 같은 썸네일 카드는 내부 초안 목록에서 뺀다(중복 카드 금지)
  const ccnt = t => C.filter(c => libCIn(c, t, UNK)).length, cnt = t => P.filter(p => inType(p, t)).length + ccnt(t), gcnt = t => G.filter(c => libGIn(c, t, UNK)).length, nUnk = cnt(UNK) + gcnt(UNK), nAll = P.length + C.length;
  const head = `<div class="lb-head"><div class="lb-ht"><h2>페르소나 라이브러리</h2><p>실제 워커힐 후기와 같은 작성자의 다른 경험으로 만든 고객 유형별 페르소나</p></div>
      <div class="lb-hs"><input class="cf-input lb-q" id="libQ" type="search" placeholder="고객 번호 · 특징 검색" value="${esc(LIBV.q)}" aria-label="고객 검색"><div class="lb-cnt" data-lib-counts="${nAll}|${nRun}|${nPriv}|${libC().length}"><b>${LIBV.runOnly ? nRun : nAll}</b>명 <span>${LIBV.runOnly ? "실행 가능 고객" : "라이브러리 고객"}</span><span> · 실행 가능 ${nRun}${nPriv ? ` (기본 시연 ${nRun - nPriv} · 비공개 기술 검수 ${nPriv})` : ""}</span>${libC().length ? `<span> · 열람 전용 ${libC().length}</span>` : ""}${G.length ? ` <span>· 내부 검수 시각 초안 ${G.length}장</span>` : ""}${!nPriv && libC().length ? `<small class="lb-cnt-note">비공개 기술 검수 등록부가 이 서버에 연결되지 않아 추가 고객은 열람 전용입니다</small>` : ""}</div></div></div>
    ${libC().length ? `<div class="lb-flt" role="group" aria-label="고객 보기"><button type="button" class="lb-fb${LIBV.runOnly ? "" : " on"}" data-ro="0">전체 ${P.length + libC().length}</button><button type="button" class="lb-fb${LIBV.runOnly ? " on" : ""}" data-ro="1">실행 가능 ${nRun}</button></div>` : ""}`;
  const stage1 = LIBV.type == null && !LIBV.q;
  if (!P.length) { $("#libraryView").innerHTML = `<div class="lb">${head}<div class="lb-empty">${LIBV.publish && LIBV.publish.mode === "public" ? "공개 배포 모드입니다 — 외부 공개 승인을 받은 고객이 아직 없습니다." : "게시 승인을 받은 고객이 없습니다."}</div></div>`; return; }
  let body;
  if (stage1) {
    const tile = (t, n, dis, g = 0) => `<button type="button" class="lb-tile allow-wrap" data-t="${esc(t)}"${dis ? " disabled" : ""}><span class="lb-ic">${libIcon(t, 44)}</span><b>${esc(t)}</b><span class="lb-tn">${dis ? "등록 고객 없음" : `${n}명${g ? ` · 초안 ${g}` : ""}`}</span></button>`;
    body = `<section class="lb-s1"><div class="lb-s1h"><h3>어떤 고객 유형을 볼까요?</h3><span>유형을 고르면 그 유형의 고객 목록이 열립니다</span></div>
      <div class="lb-tiles">${LIB_TYPES.map(t => tile(t, cnt(t), !cnt(t) && !gcnt(t), gcnt(t))).join("")}${tile("전체", nAll, false, G.length)}</div>
      ${nUnk ? `<div class="lb-unk"><button type="button" class="lb-unkb" data-t="${UNK}">${UNK} <b>${nUnk}명</b></button><span>원장 간 유형 불일치 또는 방문 목적 미확정 · 실행 가능 여부와 별개</span></div>` : ""}</section>
      ${libAudit(P, G)}
      ${libEvents()}
      ${LIBV.exp && LIBV.exp.situations && LIBV.exp.situations.length ? `<details class="lb-sit"${LIBV.sitOpen ? " open" : ""}><summary>운영 상황으로 고객 찾기 <span>상황을 고르면 관련 경험이 있는 고객을 근거 종류별로 나눕니다</span></summary>${libSituations()}</details>` : ""}`;
  } else {
    const cur = LIBV.type || "전체";
    const list = P.filter(p => (cur === "전체" || inType(p, cur)) && libSearchHit(p, LIBV.q));
    const clist = C.filter(c => libCIn(c, cur, UNK) && libCHit(c, LIBV.q)).sort((a, b) => (LIB_TYPES.indexOf(a.type) + 100) % 100 - (LIB_TYPES.indexOf(b.type) + 100) % 100 || (a.no < b.no ? -1 : 1));
    const glist = G.filter(c => libGIn(c, cur, UNK) && libGHit(c, LIBV.q)).sort((a, b) => (LIB_TYPES.indexOf(a.type) + 100) % 100 - (LIB_TYPES.indexOf(b.type) + 100) % 100 || (a.card_id < b.card_id ? -1 : 1));
    const order = p => [LIB_TYPES.indexOf(libTypeOf(p)) < 0 ? 99 : LIB_TYPES.indexOf(libTypeOf(p)), libRuntime(p.id) ? 0 : 1, p.id];
    list.sort((a, b) => { const x = order(a), y = order(b); for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1; return 0; });
    const nav = `<nav class="lb-nav" aria-label="고객 유형"><button type="button" class="lb-up" id="libUp">← 유형 선택</button>
      <button type="button" class="lb-ni${cur === "전체" ? " on" : ""}" data-t="전체"><span class="lb-nic">${libIcon("전체", 18)}</span><span class="lb-nl">전체</span><em>${nAll + G.length}</em></button>
      ${LIB_TYPES.map(t => { const n = cnt(t) + gcnt(t); return `<button type="button" class="lb-ni${cur === t ? " on" : ""}" data-t="${esc(t)}"${n ? "" : " disabled"}><span class="lb-nic">${libIcon(t, 18)}</span><span class="lb-nl">${esc(t)}</span><em>${n}</em></button>`; }).join("")}
      ${nUnk ? `<div class="lb-nsep"></div><button type="button" class="lb-ni lb-niu${cur === UNK ? " on" : ""}" data-t="${UNK}"><span class="lb-nic">?</span><span class="lb-nl">${UNK}</span><em>${nUnk}</em></button>` : ""}</nav>`;
    const card = p => { const t = libTypeOf(p), run = libRuntime(p.id), kw = libKw(p, 2);
      const vis = p.visit_feature_summary && libSafe(p.visit_feature_summary["방문 형태"]);   // CL-1024-16 — 같은 유형 이미지를 쓰는 고객끼리 구분: 이미지 위 ID · 확인된 방문 한 줄
      return `<article class="lb-card" data-id="${esc(p.id)}" tabindex="0"><div class="lb-thw">${libThumbP(p)}<span class="lb-thid">${esc(dno(p.id))}</span>${libAvChip(p.id)}</div>
        <div class="lb-cb"><div class="lb-cid"><b>${esc(dno(p.id))}</b><span class="lb-cty">${esc(libTypeLabel(p))}</span>${p.isolated_qa?'<small class="review-state">검토 중</small>':run ? "" : libNoRun}</div>
          <p class="lb-line">${escP(libLine(p))}</p>${vis ? `<div class="lb-cvis" title="${esc(vis)}">확인된 방문 · ${esc(vis.replace(/\s*\(.*?\)\s*/g, " ").trim())}</div>` : ""}
          <div class="lb-kw">${kw.map(k => `<span>${esc(k)}</span>`).join("")}</div>
          <div class="lb-cact"><button type="button" class="cf-btn cf-sm" data-pf="${esc(p.id)}">프로파일 보기</button>${run ? `<button type="button" class="cf-btn cf-sm cf-primary" data-run="${esc(p.id)}">상황별 하루 설정</button>` : ""}</div></div></article>`; };
    body = `<div class="lb-body">${nav}<section class="lb-main">
      <div class="lb-mh"><span class="lb-mic">${libIcon(cur, 22)}</span><div><h3>${esc(cur)}</h3><span>${cur === "전체" ? "등록된 모든 고객" : cur === UNK ? "동행 관계 · 방문 목적이 확인되지 않은 고객(11개 유형 수에 넣지 않음)" : esc(LIB_TYPE_DESC[cur] || "")}${LIBV.q ? ` · '${esc(LIBV.q)}' 검색` : ""}</span></div><b class="lb-mn">${list.length + clist.length}명</b></div>
      ${list.length || clist.length ? `<div class="lb-grid">${list.map(card).join("")}${clist.map(libCCard).join("")}</div>` : glist.length ? "" : `<div class="lb-empty">${LIBV.q ? "검색 조건에 맞는 고객이 없습니다." : "이 유형에 등록된 고객이 없습니다."}</div>`}
      ${glist.length ? `<div class="lb-gsec"><div class="lb-gh"><b>내부 검수 자료 · 생성 이미지 초안 ${glist.length}</b><span>${libPresent() ? "같은 유형의 후기 사례 · 프로필 미연결 · 행동 실행 전" : "고객별 고유 썸네일 초안(사람 승인 전) · 게시 승인 · 화면 프로파일 · 행동 시뮬레이션과 별개 · 내부 시연용"}</span></div><div class="lb-grid">${(libPresent() ? [...glist].sort((a, b) => libPhoto(b) - libPhoto(a)) : glist).map(libPresent() ? libPCard : libGCard).join("")}</div></div>` : ""}
    </section></div>`;
  }
  $("#libraryView").innerHTML = `<div class="lb">${head}${body}<div class="lb-foot">대표 이미지는 생성 이미지이며 실제 고객 사진이 아닙니다.${libInternal() ? " 원문 링크는 로컬 검수 환경(서버 설정)에서만 열립니다." : ""}</div></div>`;
  libWireGrid();
  $("#libraryView").scrollTop = LIBV.scroll || 0; LIBV.scroll = 0;
}
function libRouteWrite(hash, replace = false) {
  const url = location.pathname + location.search + hash;
  try { const {hillinkNav,...state}=history.state||{}; history[replace ? "replaceState" : "pushState"]({ ...state, hillinkLibrary: hash }, "", url); } catch (e) {}
}
function libTypeHash(type, query = "") {
  return `#lib/type/${encodeURIComponent(type)}${query ? `?q=${encodeURIComponent(query)}` : ""}`;
}
function libApplyRoute(hash) {
  if (!hash.startsWith("#lib")) return false;
  const route = hash.slice(1), [path, query = ""] = route.split("?"), params = new URLSearchParams(query);
  const resetDetails = () => { LIBV.situation = null; LIBV.draft = null; LIBV.cOpen = null; LIBV.open = null; LIBV.hl.clear(); LIBV.scroll = 0; };
  if (path === "lib" || path === "lib/") {
    resetDetails(); LIBV.type = null; LIBV.q = ""; LIBV.runOnly = false; libGrid(); return true;
  }
  const typeMatch = path.match(/^lib\/type\/(.+)$/);
  if (typeMatch) {
    resetDetails(); try { LIBV.type = decodeURIComponent(typeMatch[1]); } catch (e) { LIBV.type = null; }
    LIBV.q = params.get("q") || ""; libGrid(); return true;
  }
  const profileMatch = path.match(/^lib\/profile\/(.+)$/);
  if (profileMatch) {
    let id; try { id = decodeURIComponent(profileMatch[1]); } catch (e) { id = ""; }
    const p = (libPub() || []).find(x => x.id === id);
    if (p) { resetDetails(); LIBV.type = params.get("type") || libTypeOf(p) || "전체"; LIBV.q = params.get("q") || ""; LIBV.open = id; libDetail(id); return true; }
  }
  const cardMatch = path.match(/^lib\/card\/(.+)$/);
  if (cardMatch) {
    let id; try { id = decodeURIComponent(cardMatch[1]); } catch (e) { id = ""; }
    if ((LIBV.cat || []).some(x => x.id === id)) { resetDetails(); LIBV.type = params.get("type") || "전체"; LIBV.cOpen = id; libCDetail(id); return true; }
  }
  const draftMatch = path.match(/^lib\/draft\/(.+)$/);
  if (draftMatch) {
    let id; try { id = decodeURIComponent(draftMatch[1]); } catch (e) { id = ""; }
    if ((LIBV.gal || []).some(x => x.card_id === id)) { resetDetails(); LIBV.type = params.get("type") || "전체"; LIBV.draft = id; libDraft(id); return true; }
  }
  libRouteWrite("#lib", true);
  resetDetails(); LIBV.type = null; LIBV.q = ""; LIBV.runOnly = false; libGrid(); return true;
}
function libHome() {
  LIBV.situation = null; LIBV.draft = null; LIBV.cOpen = null; LIBV.open = null;
  LIBV.type = null; LIBV.q = ""; LIBV.runOnly = false; LIBV.hl.clear(); LIBV.scroll = 0; LIBV.sit = null;
  if (location.hash !== "#lib") libRouteWrite("#lib"); else libRouteWrite("#lib", true);
  setMode("library"); if (LIBV.data) libGrid();
}
window.addEventListener("popstate", () => {
  if (!location.hash.startsWith("#lib")) return;
  if (typeof MODE !== "undefined" && MODE !== "library") setMode("library");
  if (LIBV.data) libApplyRoute(location.hash);
});
function libWireGrid() {
  const V = $("#libraryView");
  const q = $("#libQ"); if (q) { q.oninput = () => { const pos = q.selectionStart; LIBV.q = q.value.trim(); if (LIBV.q && LIBV.type == null) LIBV.type = "전체"; libRouteWrite(LIBV.type == null ? "#lib" : libTypeHash(LIBV.type, LIBV.q), true); libGrid(); const n = $("#libQ"); if (n) { n.focus(); try { n.setSelectionRange(pos, pos); } catch (e) {} } }; }
  V.querySelectorAll(".lb-tile, .lb-ni, .lb-unkb").forEach(b => b.onclick = () => { LIBV.type = b.dataset.t; LIBV.q = ""; LIBV.situation = null; LIBV.open = null; libRouteWrite(libTypeHash(LIBV.type)); libGrid(); });
  const up = $("#libUp"); if (up) up.onclick = () => libHome();
  V.querySelectorAll(".lb-card[data-id]").forEach(c => { c.onclick = ev => { if (ev.target.closest("button, a")) return; libOpen(c.dataset.id); }; c.onkeydown = ev => { if (ev.key === "Enter" && ev.target === c) libOpen(c.dataset.id); }; });
  V.querySelectorAll("[data-pf]").forEach(b => b.onclick = () => libOpen(b.dataset.pf));
  const cOpen = id => { LIBV.scroll = V.scrollTop; LIBV.cOpen = id; libRouteWrite(`#lib/card/${encodeURIComponent(id)}?type=${encodeURIComponent(LIBV.type || "전체")}`, false); libCDetail(id); };
  V.querySelectorAll(".lb-ccard").forEach(c => { c.onclick = ev => { if (ev.target.closest("button, a")) return; cOpen(c.dataset.c); }; c.onkeydown = ev => { if (ev.key === "Enter" && ev.target === c) cOpen(c.dataset.c); }; });
  V.querySelectorAll("[data-cp]").forEach(b => b.onclick = () => cOpen(b.dataset.cp));
  V.querySelectorAll("[data-ro]").forEach(b => b.onclick = () => { LIBV.runOnly = b.dataset.ro === "1"; libGrid(); });
  V.querySelectorAll(".lb-gcard").forEach(c => { c.onclick = ev => { if (ev.target.closest("button, a")) return; LIBV.scroll = V.scrollTop; LIBV.draft = c.dataset.g; libRouteWrite(`#lib/draft/${encodeURIComponent(c.dataset.g)}?type=${encodeURIComponent(LIBV.type || "전체")}`, false); libDraft(c.dataset.g); }; c.onkeydown = ev => { if (ev.key === "Enter" && ev.target === c) { LIBV.draft = c.dataset.g; libRouteWrite(`#lib/draft/${encodeURIComponent(c.dataset.g)}?type=${encodeURIComponent(LIBV.type || "전체")}`, false); libDraft(c.dataset.g); } }; });
  V.querySelectorAll("[data-gd]").forEach(b => b.onclick = () => { LIBV.scroll = V.scrollTop; LIBV.draft = b.dataset.gd; libDraft(b.dataset.gd); });
  const ev = V.querySelector(".lb-ev"); if (ev) ev.ontoggle = () => { LIBV.evOpen = ev.open; };
  V.querySelectorAll("[data-evrun]").forEach(b => b.onclick = () => { if (typeof AG === "undefined") return; AG.cond.event = true; AG.res = null; LIBV.hl.clear(); setMode("agent"); });
  V.querySelectorAll("[data-run]").forEach(b => b.onclick = () => situationOpen(b.dataset.run));
  V.querySelectorAll("[data-auto]").forEach(b => b.onclick = () => auOpenFor(b.dataset.auto));
  const sd = V.querySelector(".lb-sit"); if (sd) sd.ontoggle = () => { LIBV.sitOpen = sd.open; };
  V.querySelectorAll(".lib-sit-tab").forEach(b => b.onclick = () => { LIBV.sit = b.dataset.sit; LIBV.sitOpen = true; LIBV.scroll = V.scrollTop; libGrid(); });
  V.querySelectorAll(".lib-sit-run").forEach(b => b.onclick = () => { const S = (LIBV.exp.situations || []).find(x => x.id === b.dataset.sit); if (S && S.cond) libSimMany(S); });
  V.querySelectorAll(".lib-sit-f").forEach(b => b.onclick = () => libOpen(b.dataset.a, [b.dataset.f]));
}

// ---------------------------------------------------------------- 고객 상세 — 누구인가 → 주요 성향 → 실제 행동 → 선택이 달라지는 상황 → 상세 근거(접기)
// CL-1025-37 P2 — 고객 상세의 '후기 원문 보기'(대표 후기 1편 직접 링크) + '관련 후기 n개'(글별 행동 요지 · 원문). 링크는 서버가 준 검증 URL 만.
function libSrcBlock(p, startU, compact = false) {
  const seen = new Set(), rel = [];
  [...(p.wh_events || []), ...(p.other_events || [])].forEach(e => (e.posts || []).forEach(pp => { if (seen.has(pp)) return; seen.add(pp); if (LIB_SENS.test(e.detail || "")) return; rel.push({ post: pp, wh: (p.wh_events || []).includes(e), stage: libStage(e.stage), gist: e.detail, u: libUrl(pp) }); }));
  const nLink = rel.filter(r => r.u).length, denied = !LIBV.links;
  const btn = startU ? libA(startU, "후기 원문 보기 ↗", "lb-srcbtn") : `<span class="lb-srcbtn off" title="${denied ? "이 서버는 원문 링크 권한이 없습니다(로컬 검수 환경 아님 · 공개 배포)" : "검증된 원문 주소가 없습니다"}">원문 연결 확인 중</span>`;
  const row = r => `<li><span class="lb-rt ${r.wh ? "wh" : ""}">${r.wh ? "워커힐 후기" : "같은 작성자 · 다른 경험"}</span><span class="lb-rs">${esc(r.stage)}</span><span class="lb-rg">${esc(libShort(r.gist || "", 80))}</span>${r.u ? libA(r.u, "원문 보기 ↗", "sm") : `<em class="lb-rn">원문 연결 확인 중</em>`}</li>`;
  if (compact) return `<div class="lb-srcb pvx-srcb"><span class="pvx-src-k">실제 후기</span><span class="pvx-src-v">${startU ? "대표 후기 1편 · 새 탭에서 열림" : denied ? "원문 링크는 로컬 검수 환경에서만 열립니다" : "대표 후기 원문 주소 확인 중"}</span>${rel.length ? `<details class="lb-rel pvx-rel"${LIBV.relOpen ? " open" : ""}><summary>관련 후기 ${rel.length}편 <span>${nLink ? `원문 연결 ${nLink}편` : "원문 연결 확인 중"}</span></summary><ul class="lb-rels">${rel.slice(0, 5).map(row).join("")}</ul>${rel.length > 5 ? `<details class="lb-rmore"><summary>나머지 ${rel.length - 5}편 보기</summary><ul class="lb-rels">${rel.slice(5).map(row).join("")}</ul></details>` : ""}</details>` : ""}</div>`;
  return `<div class="lb-srcb"><div class="lb-srch"><b>실제 후기</b><span>${startU ? "대표 후기 1편 · 새 탭에서 원문이 열립니다" : denied ? "원문 링크는 로컬 검수 환경에서만 열립니다" : "대표 후기 원문 주소 확인 중"}</span>${btn}</div>
    ${rel.length ? `<details class="lb-rel"${LIBV.relOpen ? " open" : ""}><summary>관련 후기 ${rel.length}편 보기 <span>${nLink ? `원문 연결 ${nLink}편` : "원문 연결 확인 중"} · 글마다 확인된 행동 요지</span></summary><ul class="lb-rels">${rel.slice(0, 5).map(row).join("")}</ul>${rel.length > 5 ? `<details class="lb-rmore"><summary>나머지 ${rel.length - 5}편 보기</summary><ul class="lb-rels">${rel.slice(5).map(row).join("")}</ul></details>` : ""}</details>` : `<div class="lb-note">연결된 후기 1편(대표 후기) — 같은 작성자의 다른 글은 아직 연결되지 않았습니다</div>`}</div>`;
}
function libOpen(id, factIds) {
  LIBV.situation = null;
  if (!LIBV.open && MODE === "library") LIBV.scroll = $("#libraryView").scrollTop;   // 목록 위치 기억 → 돌아오면 복원
  LIBV.open = id; LIBV.cOpen = null; LIBV.hl = new Set(factIds || []);
  const query = new URLSearchParams(); query.set("type", LIBV.type || "전체"); if (LIBV.q) query.set("q", LIBV.q);
  libRouteWrite(`#lib/profile/${encodeURIComponent(id)}?${query.toString()}`);
  if (MODE !== "library") setMode("library"); else libDetail(id);
}
function libBack() { LIBV.situation = null; LIBV.open = null; LIBV.hl.clear(); libRouteWrite(LIBV.type == null ? "#lib" : libTypeHash(LIBV.type, LIBV.q)); libGrid(); }
// 행동 문장에 나오는 워커힐 장소 → 시설 사진(실제 방문 장소 · 상세의 행동 사례에서만)
const LIB_PLACE = [["와인페어", "WINE_FAIR"], ["피자", "PIZZA_HILL"], ["모에기", "MOEGI"], ["명월관", "MYONGWOLGWAN"], ["온달", "ONDAL"], ["금룡", "GEUMRYONG"], ["뷔페", "THE_BUFFET"], ["파빌리온", "THE_PAVILION"], ["르 파사쥬", "LE_PASSAGE"], ["르파사쥬", "LE_PASSAGE"], ["라운지", "GRAND_CLUB_LOUNGE"], ["럭스바", "LUX_BAR"], ["리버파크", "RIVERPARK"], ["포레스트", "FOREST_PARK"], ["족욕", "SKYARD"], ["스카이야드", "SKYARD"], ["사우나", "WELLNESS_SAUNA"], ["수영", "VISTA_POOL"], ["피트니스", "VISTA_FITNESS"], ["골프", "GOLF_CLUB"], ["빛의 시어터", "THEATRE_OF_LIGHT"], ["미디어아트", "THEATRE_OF_LIGHT"]];
// 건물마다 다른 시설(수영장)은 이 고객의 실제 투숙 건물을 알 때만 그 건물 사진 — 모르면 사진 없이(다른 건물 사진을 대신 쓰지 않음)
function libBld(p) { if (!p) return null; const v = (p.visit_feature_summary && p.visit_feature_summary["방문 형태"]) || ""; if (/비스타/.test(v)) return "VISTA"; if (/그랜드/.test(v)) return "GRAND"; if (/더글라스/.test(v)) return "DOUGLAS";
  if (p.group === "dev") { const r = (LIBV.reviews || []).find(x => x.blog === p.id && !x.alt); return r && r.is_guest ? r.property : null; } return null; }
const libPlaceOf = (t, p) => { for (const [k, l] of LIB_PLACE) if ((t || "").includes(k)) { if (l === "VISTA_POOL") { const b = libBld(p); return b === "VISTA" ? "VISTA_POOL" : b === "GRAND" ? "GRAND_POOL" : null; } return l; } return null; };
// 대표 행동 2~4개 — 장소가 드러나고 엔진이 쓰는 사실에 연결된 워커힐 행동을 장소가 겹치지 않게(아동 · 건강 문장 제외)
function libReps(p, n) {
  const used = new Set((p.engine || {}).fact_ids || []), seen = new Set();
  const sc = e => (libPlaceOf(e.detail, p) ? 2 : 0) + (e.facts.some(f => used.has(f)) ? 1 : 0) + (e.link === "confirmed" ? 1 : 0) + (e.facts.some(f => LIBV.hl.has(f)) ? 3 : 0);
  return [...(p.wh_events || [])].filter(e => !LIB_SENS.test(e.detail)).map((e, i) => ({ e, i, s: sc(e) })).sort((a, b) => b.s - a.s || a.i - b.i)
    .filter(({ e }) => { const k = libPlaceOf(e.detail, p) || e.feature || e.id; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, n).map(x => x.e);
}
// Profile signature (restored UXIA01 V3 editorial lead card): presentation only; never a computed decision.
function libProfileView(p) {
  const all = [...(p.wh_events || []), ...(p.other_events || [])];
  const titles = {
    A01: ['가치를 비교한 선택적 지출', '사진과 공간을 위한 대안', '원하는 경험에는 다시 시도'],
    A02: ['여행 목적에 맞춘 숙소', '체험이 이어지는 소비', '동행과 다음 일정 우선', '이용 뒤 다시 따지는 가치', '경험 뒤 소비를 조정'],
  };
  const contextIds = { A01: ['A01S_E11', 'A01S_E18', 'A01S_E02'] };
  const traits = (p.traits || []).filter(t => !LIB_SENS.test(t.trait));
  const signatures = traits.map((trait, i) => {
    const support = (trait.support || []).map(id => all.find(e => e.id === id || (e.facts || []).includes(id))).filter(Boolean);
    const example = support.find(e => !LIB_SENS.test(e.detail)) || all.find(e => e.id === ((contextIds[p.id] || [])[i]) && !LIB_SENS.test(e.detail));
    return { trait, title: (titles[p.id] || [])[i] || libShort(trait.trait, 26), example, explicit: support.includes(example) };
  });
  return { signatures, headline: p.id === 'A01' ? '혜택과 편의를 비교해, 필요한 곳에 선택적으로 쓰는 고객' : libLine(p) || libTypeLabel(p), all };
}
function libProfileEventTitle(e) {
  const titles = {
    A01S_E02:'마감 뒤 다시 연락해 모에기를 예약', A01S_E03:'숙박·식음 혜택을 비교해 멤버십 가입', A01S_E04:'최소보증에 맞춰 음료를 추가 주문', A01S_E07:'촬영·예약 혜택을 따로 확인', A01S_E08:'전망 변경을 문의하고 실제 객실을 평가', A01S_E11:'뷔페를 포기하고 룸서비스 조식 선택', A01S_E12:'족욕을 반복 이용하고 퇴실 뒤 동선 변경', A01S_E18:'촬영 예약 대신 셀프 사진 부스 이용', A01S_E19:'매장에서 먹고 남은 베이글 포장', A01S_E22:'닫힌 부스 대신 별도 무료체험 신청', A01S_E26:'가격을 고민한 뒤 포인트로 장식 구매',
    'A02-E01':'실내 수영장 이용 뒤 장단점을 구분', 'A02-E03':'탈의 불편을 타월 요청으로 해결', 'A02-E04':'리버파크를 본 뒤 가격·시간 탐색', 'A02-E05':'유료 풀 대신 실내 수영장 이용', 'A02-E07':'부모와 함께할 요가 두 가지에 참여', 'A02-E09':'다음 날 야외 요가를 더 좋게 평가', 'A02-E14':'피자힐 세트를 먹고 남은 음식 포장', 'A02-E16':'할인 수단을 비교해 실제 결제', 'A02-E18':'분위기와 음식 값을 나눠 재방문 판단', 'A02-E19':'추가 요금·층수에 따른 조망 비교', 'A02-E23':'설명을 들으며 첫 와인 페어링 경험', 'A02-E24':'서비스 음료 뒤 치즈 플래터 추가 주문', 'A02-E36':'장비 구매를 돌아보고 대여를 권고', 'A02-E25':'부모와 티코스를 예약해 체험', 'A02-E26':'차 체험 뒤 할인 혜택으로 구매', 'A02-E27':'다음 일정을 고려해 카트 3회권 선택', 'A02-E29':'쿠폰이 있어도 추가 활동은 생략',
  };
  return titles[e.id] || libShort(e.detail.split(/[.!?。]/)[0], 42);
}
// Profile-only image preparation: approved mapping + actual browser decode, never a new asset.
const LIB_PROFILE_IMAGE_CACHE = new Map();
function libProfileRows(p) {
 const E=p.engine||{facts:{}};
 const reps=(p.wh_events||[]).length?libReps(p,4):[];
 const row=(place,stage,text,src,hl,title,eid,factIds=[])=>({place,stage,text,src,hl,title,eid,factIds,image:null,imageStatus:'NO_MAPPING'});
 return reps.length?reps.map(e=>row(libPlaceOf(e.detail,p),libStage(e.stage),e.detail,`${esc(LIB_LINK[e.link]||'출처 연결 미확인')} ${libA(libUrl((e.posts||[])[0]),'원문 ↗','sm')}`,e.facts.some(f=>LIBV.hl.has(f)),libProfileEventTitle(e),e.id,e.facts)):
 Object.entries(E.facts||{}).filter(([,f])=>!f.hidden&&f.gist&&!LIB_SENS.test(f.gist)).sort((a,b)=>(b[1].wh?1:0)-(a[1].wh?1:0)).slice(0,4).map(([k,f])=>row(f.wh?libPlaceOf(f.gist,p):null,f.wh?'워커힐 후기':'다른 경험',f.gist,`${f.wh?'워커힐 후기':'다른 경험'}<span class="dev"> · 후기 사실 ${esc(k)}</span> ${libA(libUrl(f.post),'원문 ↗','sm')}`,LIBV.hl.has(k),libShort(f.gist.split(/[.!?。]/)[0],42),null,[k]));
}
function libProfileImageAllowed(loc,image) {
 if(!loc||!image?.src)return false;
 const it=window.PLACE_THUMBS?.pick(loc);
 if(it)return ['concept','team_photo','official_permitted'].includes(it.kind)&&it.approved!==false&&!it.withheld;
 return image.src.startsWith('/local-photo/')&&((LIB.photos||{})[loc]||[]).length>0;
}
async function libProfilePrepareImages(rows) {
 await Promise.all(rows.map(async row=>{
  const im=row.place&&typeof placeImg==='function'?placeImg(row.place):null;
  if(!im)return;
  if(!libProfileImageAllowed(row.place,im)){row.imageStatus='APPROVAL_HOLD';return;}
  if(!LIB_PROFILE_IMAGE_CACHE.has(im.src))LIB_PROFILE_IMAGE_CACHE.set(im.src,new Promise(resolve=>{
   const probe=new Image();let done=false;const finish=ok=>{if(done)return;done=true;clearTimeout(timer);resolve(ok?{...im,width:probe.naturalWidth,height:probe.naturalHeight}:null);};
   const timer=setTimeout(()=>finish(false),4000);probe.onload=()=>finish(probe.naturalWidth>0&&probe.naturalHeight>0);probe.onerror=()=>finish(false);probe.src=im.src;
  }));
  row.image=await LIB_PROFILE_IMAGE_CACHE.get(im.src);row.imageStatus=row.image?'LOADED':'LOAD_FAILED';
 }));return rows;
}
function libProfileMoments(rows) {
 const images=rows.filter(r=>r.image),attrs=r=>`${r.eid?` id="profile-event-${esc(r.eid)}"`:''} data-profile-moment="${rows.indexOf(r)}"`;
 const fig=(r,cls='')=>`<figure class="${cls}" style="aspect-ratio:${r.image.width}/${r.image.height}"><img src="${esc(r.image.src)}" alt="${esc(r.image.name)}" loading="eager" width="${r.image.width}" height="${r.image.height}"><figcaption>${esc(r.image.name)} · ${esc(r.image.credit||'장소 참고 이미지')}</figcaption></figure>`;
 // Keep the accepted four-image layout, including its original markup and order.
 if(images.length===4&&rows.length===4)return `<div class="lb-acts pvx-acts" data-profile-layout="four">${rows.map(r=>`<div class="lb-act pvx-act${r.hl?' hl':''}"${attrs(r)}><div class="lb-aph"><img src="${esc(r.image.src)}" alt="${esc(r.image.name)}" loading="lazy"><span>${esc(r.image.name)}</span></div><div class="lb-ab"><span class="lb-ast">${esc(r.stage)}</span>${r.title?`<h4 class="pvx-act-title">${esc(r.title)}</h4>`:''}<p>${esc(libShort(r.text,120))}</p><span class="lb-asrc">${r.src}</span></div></div>`).join('')}</div>`;
 // Two featured images use the compact layout; a third asset stays in details. Other image counts
 // keep their existing markup; a shortened heading is expanded from its original text.
 if(images.length===2||images.length===3){
  const featured=images.slice(0,2);
  const copy=r=>{
   const title=r.title&&!/(?:…|\.\.\.)$/.test(r.title)?r.title:(r.text||'').split(/[.!?。]/)[0].trim();
   const body=(r.text||'').startsWith(title)?(r.text||'').slice(title.length).replace(/^[\s.!?。]+/,''):(r.text||'');
   return {title,body};
  };
  const text=rows.filter(r=>!featured.includes(r));
  return `<div class="pvx-magazine pvx-magazine-two" data-profile-layout="magazine" data-image-count="${images.length}"><div class="pvx-mag-featured">${featured.map(r=>{const c=copy(r);return `<article class="pvx-mag-hero${r.hl?' hl':''}"${attrs(r)}>${fig(r)}<div class="pvx-mag-copy"><small>${esc(r.stage)}</small><h4>${esc(c.title)}</h4>${c.body?`<p>${esc(c.body)}</p>`:''}<div class="pv3-source-row">${r.src}</div></div></article>`;}).join('')}</div>${text.length?`<div class="pv3-compact-list pvx-mag-text" data-text-count="${text.length}">${text.map(r=>{const c=copy(r);return `<article class="pv3-compact-event${r.hl?' hl':''}"${attrs(r)}><small class="pv3-event-meta">${esc(r.stage)}</small><h4>${esc(c.title)}</h4>${c.body?`<p>${esc(c.body)}</p>`:''}<div class="pv3-source-row">${r.src}</div>${r.image?`<details class="pvx-secondary-image"><summary>관련 장소 이미지</summary>${fig(r)}</details>`:''}</article>`;}).join('')}</div>`:''}</div>`;
 }
 const featured=images.slice(0,2),text=rows.filter(r=>!featured.includes(r));
 return `<div class="pvx-magazine" data-profile-layout="${images.length?'magazine':'text'}" data-image-count="${images.length}">${featured.length?`<div class="pvx-mag-featured">${featured.map(r=>`<article class="pvx-mag-hero${r.hl?' hl':''}"${attrs(r)}>${fig(r)}<div class="pvx-mag-copy"><small>${esc(r.stage)}</small><h4>${esc(r.title||libShort(r.text,42))}</h4><p>${esc(r.text)}</p><div class="pv3-source-row">${r.src}</div></div></article>`).join('')}</div>`:''}${text.length?`<div class="pv3-compact-list pvx-mag-text">${text.map(r=>`<article class="pv3-compact-event${r.hl?' hl':''}"${attrs(r)}><small class="pv3-event-meta">${esc(r.stage)}</small><h4>${esc(r.title||libShort(r.text,42))}</h4><details><summary>상황과 출처</summary><p>${esc(r.text)}</p><div class="pv3-source-row">${r.src}</div>${r.image?`<details class="pvx-secondary-image"><summary>관련 장소 이미지</summary>${fig(r)}</details>`:''}</details></article>`).join('')}</div>`:''}</div>`;
}
function libProfileMountImages(rows) {
 const root=document.querySelector('#libExperiences [data-profile-layout]');if(!root)return;
 root.querySelectorAll('img').forEach(img=>img.onerror=()=>{
  const row=rows[Number(img.closest('[data-profile-moment]').dataset.profileMoment)];if(!row?.image)return;
  row.image=null;row.imageStatus='LOAD_FAILED';
  const opened=[...root.querySelectorAll('details[open]')].map(d=>d.closest('[data-profile-moment]')?.dataset.profileMoment);
  const holder=document.createElement('div');holder.innerHTML=libProfileMoments(rows);root.replaceWith(holder.firstElementChild);libProfileMountImages(rows);
  opened.forEach(i=>document.querySelector(`#libExperiences [data-profile-moment="${i}"] details`)?.setAttribute('open',''));
 });
}
function libProfileFlowUnavailable(p,choice,reason) {
 const facts=Object.values(p.engine?.facts||{}).filter(f=>!f.hidden&&f.gist&&!LIB_SENS.test(f.gist));
 return `<div class="lib-fs"><span class="lib-fn">1</span><div class="lib-fh">후기에서 관측한 경험</div><p>${facts.length?`연결 가능한 후기 사실 ${facts.length}개가 있습니다. 이 선택에 직접 기여한 경험은 확인되지 않았습니다.`:'연결할 후기 경험이 확인되지 않았습니다.'}</p></div><div class="lib-farr" aria-hidden="true">→</div><div class="lib-fs"><span class="lib-fn">2</span><div class="lib-fh">추출한 성향과 판단 기준</div><p>${esc(reason||'이 실행에서 후기 성향의 직접 기여를 확인하지 못했습니다.')}</p></div><div class="lib-farr" aria-hidden="true">→</div><div class="lib-fs win"><span class="lib-fn">3</span><div class="lib-fh">가상 선택 또는 조건부 판단</div><p>${choice?esc(choice):'이 프로필에 연결된 가상 선택을 계산하지 않았습니다.'}</p><small>후기 경험과 가상 선택을 동일한 관측 사실로 보지 않습니다.</small></div>`;
}
async function libDetail(id) {
  const original=libP(id);if(!original||!libPublished(original))return libBack();
  const p=window.HLProfileDisplayReview.profile(original,LIBV.displayReview?.[id]);
  const momentRows=libProfileRows(p);
  await libProfilePrepareImages(momentRows);
  if(LIBV.open!==id || MODE!=='library')return;
  const t = libTypeOf(p), eng = libEng(id), run = libRuntime(id), E = p.engine || { facts: {}, n: 0 }, A = p.audit;
  const vf = p.visit_feature_summary && libSafe(p.visit_feature_summary["방문 형태"]);
  const pick = libSafe(p.pick);
  const fix = LIB_TYPE_FIX[id];
  const facts = [
    vf && ["확인된 방문", vf],
    pick && ["대표 방문", libShort(pick, 90)],
    fix && ["유형 근거", fix.basis],
    A ? ["근거 규모", `워커힐 글 ${A.walkerhill ?? "-"} · 분석한 글 ${A.unique_posts ?? "-"}${A.events_confirmed != null ? ` · 확인된 경험 묶음 ${A.events_confirmed}` : ""}`] : E.n ? ["근거 규모", `엔진이 쓰는 후기 사실 ${E.n}개`] : null,
  ].filter(Boolean);
  const startU = libStartUrl(p);
  const top3 = eng ? eng.bars.filter(b => b.status === "observed").sort((a, b) => b.level - a.level).slice(0, 3) : [];
  const hero = `<section class="lb-hero pvx-hero">${libThumbP(p, "lb-hth")}
    <div class="lb-hb"><div class="lb-hk">${libAvChip(p.id)}<span class="lb-cty">${esc(libTypeLabel(p))}</span>${p.isolated_qa?'<small class="review-state">검토 중</small>':run ? "" : libNoRun}</div>
      <h2>${esc(dno(p.id))}</h2><p class="lb-hline">${escP(libLine(p))}</p>
      ${top3.length ? `<div class="lb-htr">${top3.map(b => `<span>${esc(b.label)}</span>`).join("")}</div>` : ""}
      <div class="lb-hact pvx-hact">${run ? `<button type="button" class="cf-btn cf-primary" id="libSimWine">이 고객의 상황별 하루 보기 →</button>` : `<span class="lb-hnr">심층 프로필 보기 가능 · 행동 실행 미검증</span>`}${startU ? libA(startU, "대표 원문 후기 ↗", "cf-btn pvx-srcbtn") : `<button type="button" class="cf-btn pvx-srcbtn off" disabled aria-disabled="true" title="${LIBV.links ? "검증된 원문 주소가 없습니다" : "원문 링크는 로컬 검수 환경에서만 열립니다"}">대표 원문 후기 ↗</button>`}</div>
      <div class="pvx-hfoot">${[libBld(p) ? `숙박 · ${({ GRAND: "그랜드", VISTA: "비스타", DOUGLAS: "더글라스" })[libBld(p)] || libBld(p)}` : "", dnoParty(p.id).label, A && A.walkerhill != null ? `워커힐 글 ${A.walkerhill}편` : "", `사용 가능한 사실 ${Object.values(E.facts || {}).filter(f => !f.hidden).length}개`].filter(Boolean).map(x => `<span>${esc(x)}</span>`).join("")}<span class="lb-hcap">대표 이미지는 생성 이미지입니다</span></div></div></section>`;
  // Signature — restored V3 lead card (CHOICE SIGNATURE). Uses only this profile's traits and experiences.
  const PV = libProfileView(p), sigs = PV.signatures.filter(x => x.trait.claim || (x.trait.support || []).length || (x.trait.fact_ids || []).some(fid=>p.engine?.facts?.[fid]?.gist) || x.example || libShort(x.trait.trait, 26) !== x.trait.trait), originalLead = sigs.find(x => p.id === "A02" && x.trait.id === "A02-T4") || sigs[0], sigLead = p.display_signature ? {title:p.display_signature,trait:{id:"display-review",trait:p.display_signature,fact_ids:p.display_review.fact_ids},displayReview:true} : originalLead, sigSupport = sigs.filter(x => x !== originalLead && !(p.display_review?.redundant_support_texts || []).includes(x.trait.trait) && x.title !== sigLead?.title && x.trait.trait !== sigLead?.title && x.title !== libLine(p)).slice(0, 4);
  const sigJump = x => { if(x?.displayReview)return `<button class="cf-link" data-pvx-open="rel">관련 후기와 원문 ↓</button>`; const e = x && x.example; return e ? `<button class="cf-link" data-profile-story="${esc(e.id)}" data-profile-story-facts="${esc((e.facts || []).join(","))}">관련 경험 보기 ↓</button>` : (x?.trait.fact_ids||[]).length ? `<button class="cf-link" data-profile-story="facet-${esc(x.trait.id)}" data-profile-story-facts="${esc(x.trait.fact_ids.join(","))}">연결된 후기 사실 보기 ↓</button>` : ""; };
  const signature = sigLead ? `<section class="pv2-section pv2-signatures pv3-patterns pvx-signature"><div class="pv2-section-head"><div><span class="pv2-eyebrow">CHOICE SIGNATURE</span><h3>대표적인 선택 방식</h3></div><small>대표 사례를 중심으로 편집 · 성향의 점수 순위가 아닙니다</small></div><div class="pv3-pattern-layout${sigSupport.length > 2 ? " pv3-rich-pattern" : ""}"><article class="pv3-pattern-lead"><span class="pv3-small-label">이 고객을 기억할 한 가지</span><h4>${esc(/…$/.test(sigLead.title) ? sigLead.trait.trait : sigLead.title)}</h4><div class="pv3-lead-bottom"><span>${esc(sigLead.displayReview ? (p.display_review.status === "EVIDENCE_LIMITED_DISPLAY_ONLY" ? "기존 요약 · 원문 대조 HOLD" : "해당 원문 사례 대조 · 전체 의미 승인 전") : LIB_CLAIM[sigLead.trait.claim] || (sigLead.trait.semantic_status==='SEMANTIC_HOLD'?"기존 성향 근거 · 의미 검수 대기":"프로필 해석"))}</span>${sigJump(sigLead)}</div></article>${sigSupport.length ? `<div class="pv3-pattern-support">${sigSupport.map(x => `<article><h4>${esc(x.title)}</h4>${x.trait.trait !== x.title ? `<p>${esc(x.trait.trait)}</p>` : ""}${sigJump(x)}</article>`).join("")}</div>` : ""}</div></section>` : "";
  const sigBlock = signature ? `<div class="pv3-story-top pvx-story-top"><div class="pv3-story-intro">${signature}</div><aside class="pv3-record-rail" aria-label="출처와 확인 상태"><span class="pv3-small-label">출처와 확인 상태</span><button type="button" class="cf-link" data-pvx-open="rel">관련 후기와 원문 ↓</button><button type="button" class="cf-link" data-pvx-open="val">자료·검증 상세 ↓</button><p>${esc(p.display_review ? p.display_review.review_scope : "대표 선택 방식은 후기 근거로 편집한 해석이며 성향 점수의 순위가 아닙니다.")}</p></aside></div>` : "";
  // 1 · 주요 성향 — 근거가 있는 엔진 성향(관측)만 막대로, 근거 없는 성향은 숫자만
  const obs = eng ? eng.bars.filter(b => b.status === "observed").sort((a, b) => b.level - a.level).slice(0, 5) : [], nNone = eng ? eng.bars.filter(b => b.status !== "observed").length : 0;
  const traits = (p.traits || []).filter(x => !LIB_SENS.test(x.trait) && x.trait !== libLine(p)).slice(0, 5);
  const s1 = `<section class="lb-sec pvx-sec"><div class="lb-sh"><span class="pv2-eyebrow pvx-eyebrow">TRAITS &amp; PATTERNS</span><h3>반복 성향과 패턴</h3><span>${signature ? "대표 선택 방식을 뒷받침하는 후기 근거 성향" : "무엇을 중요하게 생각하나"} · 후기 근거와 분석 추론을 구분</span></div>
    <div class="lb-two">${obs.length ? `<div class="lb-col"><div class="lb-ck">후기 근거로 측정한 성향 <em>엔진 입력</em></div>${typeof agBars === "function" ? agBars(obs) : ""}${nNone ? `<div class="lb-note">근거가 확인되지 않은 성향 ${nNone}개는 표시하지 않음</div>` : ""}</div>` : `<div class="lb-col"><div class="lb-ck">후기 근거로 측정한 성향</div><div class="lb-note">이 환경에는 엔진 성향 자료가 없습니다.</div></div>`}
      ${traits.length ? `<div class="lb-col"><div class="lb-ck">여러 경험에서 반복된 패턴 <em>분석 추론</em></div><ul class="lb-traits">${traits.map(x => `<li><b>${esc(x.trait)}</b>${x.n != null ? `<span>독립 경험 ${x.n}</span>` : ""}</li>`).join("")}</ul></div>` : ""}</div></section>`;
  // 2 · 실제 행동 — 워커힐 시설 사진은 여기서만
  const s2body=libProfileMoments(momentRows);
  const s2 = `<section class="lb-sec pvx-sec" id="libExperiences"><div class="lb-sh"><span class="pv2-eyebrow pvx-eyebrow">MOMENTS &amp; CHOICES</span><h3>이 고객의 실제 행동</h3><span>후기에서 확인한 주요 방문 · 선택${momentRows.length?` · 대표 ${momentRows.length}개`:''}</span></div>${momentRows.length?s2body:'<p class="lb-note">화면에 연결할 행동 사례가 아직 없습니다.</p>'}</section>`;
  // 3 · 선택이 달라지는 상황 — 관측(후기)과 가설을 구분
  const rules = (p.rules || []).filter(r => !LIB_SENS.test(r.condition + r.hypothesis)).slice(0, 4);
  const s3 = `<section class="lb-sec pvx-sec"><div class="lb-sh"><span class="pv2-eyebrow pvx-eyebrow">IF THE SITUATION CHANGES</span><h3>어떤 상황에서 선택이 달라지나</h3><span>같은 고객의 조건별 행동 — 가설 · 검증 전</span></div>
    ${rules.length ? `<div class="lb-rules">${rules.map(r => `<div class="lb-rule"><div><span>이런 조건이면</span>${esc(libShort(r.condition, 70))}</div><div><span>예상 선택</span>${esc(libShort(r.hypothesis, 90))}</div><em>근거 경험 ${(r.support || []).length || r.evidence || "-"} · 가설</em></div>`).join("")}</div>` : `<div class="lb-note">조건별 행동 규칙은 아직 추출되지 않았습니다.</div>`}
    </section>`;
  // 4 · 상세 근거 — 접기
  const efs = Object.entries(E.facts || {}).filter(([, f]) => !f.hidden);
  const efRow = ([k, f]) => `<li class="${LIBV.hl.has(k) ? "hl" : ""}"><span class="badge">${esc(fidD(k))}</span><span class="lib-ef">${esc(f.gist)}${p.display_review?.changes.fact_summaries?.[k] ? `<small> · 원문 대조 표시 보정 · 엔진 입력은 변경하지 않음</small><details><summary>보존된 엔진 입력</summary>${esc(original.engine?.facts?.[k]?.gist||"")}</details>` : ""}</span><span class="lib-ex ${f.wh ? "wh" : ""}">${f.wh ? "워커힐 후기" : "다른 경험"} ${libA(libUrl(f.post), "원문 ↗", "sm")}</span></li>`;
  const efSorted = [...efs].sort((a, b) => LIBV.hl.has(b[0]) - LIBV.hl.has(a[0]));
  const s4 = `<section class="lb-sec lb-deep pvx-sec"><div class="lb-sh"><span class="pv2-eyebrow pvx-eyebrow">REVIEW EVIDENCE</span><h3>후기 근거 찾아보기</h3><span>필요할 때 펼쳐 보기 · 원문·Fact·검증 정보</span></div>
    <details id="libRelated" class="pvx-related"><summary>관련 후기와 원문 <span>대표 후기 · 같은 작성자의 관련 후기</span></summary>${libSrcBlock(p, startU)}</details>
    ${run ? `<details id="libFlowD"><summary>실제 경험이 선택으로 이어지는 과정 <span>기본 조건 저녁 턴 · 같은 엔진</span></summary><div class="lib-flow" id="libFlowBody"><div class="hint">계산 중…</div></div></details>` : ""}
    ${efs.length ? `<details${LIBV.hl.size ? " open" : ""} id="libEf"><summary>후기 근거 전체 <span>엔진이 쓰는 후기 사실 ${efs.length}${LIBV.hl.size ? ` · 지도에서 고른 근거 ${[...LIBV.hl].filter(k => E.facts[k]).length}개 강조` : ""}</span></summary><ul class="lib-efs">${efSorted.slice(0, 8).map(efRow).join("")}</ul>${efSorted.length > 8 ? `<details class="lb-rmore"><summary>나머지 ${efSorted.length - 8}개 보기</summary><ul class="lib-efs">${efSorted.slice(8).map(efRow).join("")}</ul></details>` : ""}</details>` : ""}
    ${p.wh_events ? `<details><summary>워커힐 행동 전체 <span>${p.wh_events.length}</span></summary><ul class="lib-ev">${p.wh_events.map(libEvent).join("")}</ul></details>` : ""}
    ${p.other_events ? `<details><summary>다른 여행 · 식사 경험 전체 <span>${p.other_events.length}</span></summary><ul class="lib-ev">${p.other_events.map(libEvent).join("")}</ul></details>` : ""}
    ${(p.traits || []).length ? `<details><summary>반복 패턴 상세 <span>${p.traits.length}개 · 근거 사례 · 예외</span></summary>${libPatterns(p)}</details>` : ""}
    <details><summary>데이터 · 검증 정보</summary><table class="kv ag-kv lib-kv">
      ${facts.map(([k, v]) => `<tr><td>${k}</td><td>${esc(v)}</td></tr>`).join("")}
      <tr><td>표시 번호</td><td>${esc(dno(p.id))} <span class="hint">임시 카드 번호 · 정식 고객 번호 아님</span><span class="dev"> · 내부 실행 ID ${esc(p.id)} (P-#### 정식 번호는 ID 계약 승인 전)</span></td></tr>
      <tr><td>동행 인원</td><td>${esc(dnoParty(p.id).label)} · 출처 ${esc(dnoParty(p.id).origin)}</td></tr>
      <tr><td>엔진 입력</td><td>${esc(eng ? eng.pipeline || "-" : "이 환경에 없음")}</td></tr>
      ${A ? `<tr><td>수집 범위</td><td>워커힐 ${A.walkerhill ?? "-"} · 다른 숙박 제목 후보 ${A.related ?? "-"} · 최근 ${A.recent ?? "-"}편 · 공통 프롬프트 ${esc(A.prompt || "")}</td></tr>
      <tr><td>미확인</td><td>팀 검수 · 승인 전 · 배정 전체 ${A.assignment_complete ? "완료" : "미완료"} · 열지 못한 출처 ${A.missing_sources ?? "-"}</td></tr>` : ""}
      <tr><td>사실 대조</td><td>엔진이 쓰는 사실 ${E.n || 0}개${E.found_in_team != null ? ` · 팀 분석에 있음 ${E.found_in_team}` : ""}${p.n_facts ? ` · 팀 분석 사실 ${p.n_facts}개` : ""}</td></tr>
      <tr><td>화면 제외</td><td>아동 · 건강 관련 문장${p.hidden_sentences != null ? ` ${p.hidden_sentences}개` : ""} · 원문 링크는 로컬 전용 자료에서만 연결</td></tr>
      ${p.caution ? `<tr><td>검수 주의</td><td>${esc(p.caution)}</td></tr>` : ""}</table></details></section>`;
  $("#libraryView").innerHTML = `<div class="lb lb-det pv3-profile pvx-profile"><div class="lb-crumb"><button type="button" class="cf-btn cf-sm" id="libBack">← ${esc(LIBV.type && LIBV.type !== "전체" ? LIBV.type : LIBV.type === "전체" ? "전체 목록" : "라이브러리")}</button>${LIBV.hl.size ? `<button type="button" class="cf-btn cf-sm" id="libToMap">← 고객흐름으로 돌아가기</button>` : ""}<span class="lb-path">페르소나 라이브러리 › ${esc(t || "유형 확인 중")} › <b>${esc(dno(p.id))}</b></span></div>
    ${hero}${sigBlock}${s2}${s1}${s3}${s4}</div>`;
  libProfileMountImages(momentRows);
  $("#libBack").onclick = libBack;
  $$("#libraryView [data-pvx-open]").forEach(b => b.onclick = () => { const k = b.dataset.pvxOpen; let d = k === "rel" ? $("#libRelated") : [...$$("#libraryView .lb-deep details")].find(x => /데이터 · 검증/.test(x.querySelector("summary")?.textContent || "")); if (d) { d.open = true; d.scrollIntoView({ block: "center", behavior: "smooth" }); } });
  $$("#libraryView [data-profile-story]").forEach(b => b.onclick = () => { const el = document.getElementById("profile-event-" + b.dataset.profileStory); if (el) { el.scrollIntoView({ block: "center", behavior: "smooth" }); el.classList.add("pvx-focus"); setTimeout(() => el.classList.remove("pvx-focus"), 1600); } else { const facts = (b.dataset.profileStoryFacts || "").split(",").filter(Boolean); if (facts.length) libOpen(id, facts); else { const d = $("#libEf"); if (d) { d.open = true; d.scrollIntoView({ block: "start" }); } } } });
  const sw = $("#libSimWine"); if (sw) sw.onclick = () => situationOpen(id);
  const tm = $("#libToMap"); if (tm) tm.onclick = () => { LIBV.hl.clear(); setMode("agent"); };
  const sb = $("#libSim"); if (sb) sb.onclick = () => { if (typeof AG !== "undefined") { AG.cond.event = false; AG.cond.product_levers = {}; AG.mode = "agent"; } libSim(id); };
  const ab = $("#libAuto"); if (ab) ab.onclick = () => auOpenFor(id);
  $$("#libraryView .lib-xrun").forEach(b => b.onclick = () => { const x = (LIBV.exp.experiments[id] || []).find(y => y.id === b.dataset.x); if (x) libSim(id, x); });
  $$("#libraryView .lib-xf").forEach(b => b.onclick = () => libOpen(id, [b.dataset.xf]));
  const fd = $("#libFlowD"); if (fd) fd.ontoggle = () => { if (fd.open) libFlow(p); };
  if (LIBV.hl.size) setTimeout(() => { const el = $("#libEf"); if (el) el.scrollIntoView({ block: "start", behavior: "instant" }); }, 0); else $("#libraryView").scrollTop = 0;
}
// 반복 패턴 상세(성향별 근거 사례 · 예외)
function libPatterns(p) {
  const evById = {}; [...(p.wh_events || []), ...(p.other_events || [])].forEach(e => evById[e.id] = e);
  return `<div class="lb-pats">${p.traits.map(t => { const sup = (t.support || []).map(x => evById[x]).filter(Boolean);
    return `<div class="lb-pat"><div class="lb-pth"><b>${esc(t.trait)}</b><em>${esc(LIB_CLAIM[t.claim] || "분석")}${t.n != null ? ` · 독립 경험 ${t.n}` : ""}</em></div>${sup.length ? `<ul class="lib-ev">${sup.map(libEvent).join("")}</ul>` : ""}${t.counter && t.counter.length ? `<div class="lib-ce"><span>예외</span>${esc(t.counter.join(" / "))}</div>` : ""}</div>`; }).join("")}</div>`;
}
function libEvent(e) {
  const hl = e.facts.some(f => LIBV.hl.has(f)), u = libUrl((e.posts || [])[0]);
  return `<li class="${hl ? "hl" : ""}"><span class="lib-et">${esc(libStage(e.stage))}</span><span class="lib-ed">${esc(LIB_SENS.test(e.detail) ? "아동 · 건강 정보가 있어 화면에서 제외" : e.detail)}</span><span class="lib-el">${libA(u, "원문 ↗", "sm") || esc(LIB_LINK[e.link] || e.link || "")}</span></li>`;
}

// 10/23 운영 상황 → 관련 에이전트 역검색(성향 입력의 근거 사실로 분류 · 신뢰도 · 적중률 아님). 실행 버튼은 계산 가능한 상황에만.
function libSituations() {
  const SS = LIBV.exp && LIBV.exp.situations; if (!SS || !SS.length) return "";
  const cur = SS.find(x => x.id === LIBV.sit) || SS[0];
  const CL = { direct: ["직접 관련 경험", "ok"], transfer: ["유사 경험 · 전이 가설", ""], common: ["공통 계산 중심", ""], nopersonal: ["개인화 근거 부족 · 계산 가능", ""], na: ["현재 계산 불가", "na"] };
  const groups = ["direct", "transfer", "common", "nopersonal", "na"].map(k => [k, cur.agents.filter(a => a.class === k)]).filter(([, xs]) => xs.length);
  return `<section class="lib-sec" id="libSit"><div class="lib-sh">운영 상황에서 고객 찾기 <span class="hint">상황을 고르면 근거 종류별로 에이전트를 나눕니다 · 신뢰도 점수 아님</span>${noteI("근거의 종류로 나눈 것이며 예측 적중률 · 신뢰도 순위가 아닙니다.")}</div>
    <div class="lib-chips lib-sits">${SS.map(x => `<button class="lib-sit-tab ${x.id === cur.id ? "on" : ""}" data-sit="${x.id}">${esc(x.title)}</button>`).join("")}</div>
    <div class="lib-sitb"><div class="hint lib-sitn">${esc(cur.note)}${cur.share_note ? noteI(cur.share_note + " 숫자는 그 조건에서 선택 점수에 더해진 후기 근거 몫이며 신뢰도 · 적중률이 아닙니다. 사실 ID를 누르면 프로파일의 해당 경험이 열립니다.") : ""}</div>
      <div class="lib-sitg">${groups.map(([k, xs]) => `<div class="lib-sitc"><div class="lib-sith"><span class="ag-st ${CL[k][1]}">${CL[k][0]}</span><b>${xs.length}</b></div><ul>${xs.map(a => `<li><b>${esc(dno(a.agent))}</b>${a.review_share != null ? `<span class="lib-sitv" title="후기 근거 몫">${a.review_share.toFixed(2)}</span>` : ""}${(a.facts || []).slice(0, 2).map(f => `<button type="button" class="lib-sit-f" data-a="${esc(a.agent)}" data-f="${esc(f)}">${esc(fidD(f))}</button>`).join("")}${a.pipeline && !/R-BASE/.test(a.pipeline) ? `<em class="hint" title="${esc(a.pipeline)}">입력 다름</em>` : ""}${a.flag ? `<em class="lib-sitflag" title="${esc(a.flag)}">검수 중</em>` : ""}</li>`).join("")}</ul></div>`).join("")}</div>
      ${cur.cond ? `<div class="dact"><button class="rv-btn lib-sit-run" data-sit="${cur.id}">11명에게 실행 ▶ <span class="hint">${esc(cur.levers)}</span></button></div>` : `<div class="hint">이 상황은 지금 실행 버튼이 없습니다 — ${esc(cur.note)}</div>`}
    </div></section>`;
}
function libSimMany(S) {
  AG.keep.agents = null; AG.res = null; AG.autorun = true; AG.from = null;
  AG.exp = { id: S.id, agent: "전원", question: S.title, class: "situation", levers: S.levers, basis: [], unverified: ["운영 상황 기준 역검색 · 대표 조건 하나로 실행 · 입력 버전 3종 혼재"], version: "engine_input" };
  AG.cond = Object.assign({ pricing: "historical", product_levers: {} }, JSON.parse(JSON.stringify(S.cond))); AG.open = new Set(Object.keys(AG.cond.product_levers));
  if (AG.meta) AG.many = new Set(AG.meta.personas.map(p => p.id));
  LIBV.hl.clear(); setMode("agents");
}

// E — 대표 사례 하나: 후기 경험 → 엔진 성향 → 이번 저녁 선택에 더한 몫 (같은 엔진 · 기본 조건)
LIBV.turn = {};
async function libFlow(p) {
  const el = $("#libFlowBody"); if (!el) return;
  try {
    if (!LIBV.turn[p.id]) LIBV.turn[p.id] = await api("/api/turn", { op: "view", personas: [p.id], cond: { turn: "dinner", event: false, stay: true, building: "VISTA", party_size: 2, pricing: "historical", product_levers: {} } });
  } catch (e) { if(LIBV.open===p.id)el.innerHTML=libProfileFlowUnavailable(p,null,'가상 선택을 계산하지 못했습니다. 기존 후기 근거는 아래에서 확인할 수 있습니다.'); return; }
  if (LIBV.open !== p.id || !$("#libFlowBody")) return;
  const c = LIBV.turn[p.id].customers[0], r = c.reasons.filter(x => x.parts.review > 0.01).sort((a, b) => b.parts.review - a.parts.review)[0];
  const V = c.choice.venue_id === "ROOM_MEAL" ? "객실 식사" : c.choice.venue_label, prod = c.choice.product_label.replace(/^(룸서비스|피자힐) /, "");
  if (!r) { el.innerHTML=libProfileFlowUnavailable(p,`${V} · ${prod}`, '기본 조건의 저녁 턴에서 후기 기여 항이 없어 공통 계산으로 선택됐습니다. 개인 성향의 인과관계를 만들지 않습니다.'); return; }
  const fid = (r.fact_ids || []).find(f => p.engine.facts[f] && !p.engine.facts[f].hidden), f = fid && p.engine.facts[fid];
  const key = typeof AG_FACET !== "undefined" ? Object.keys(AG_FACET).find(k => AG_FACET[k].test(r.factor)) : null, bar = key && libEng(p.id) ? libEng(p.id).bars.find(b => b.key === key) : null;
  el.innerHTML = `<div class="lib-fs"><span class="lib-fn">1</span><div class="lib-fh">후기에서 관측한 경험</div>${f ? `<p>${esc(libShort(f.gist, 90))}</p><span class="lib-ex ${f.wh ? "wh" : ""}">${f.wh ? "워커힐 후기" : "다른 경험"} · ${esc(fid)}</span>` : `<p class="hint">근거 문장 비공개</p>`}</div>
    <div class="lib-farr" aria-hidden="true">→</div>
    <div class="lib-fs"><span class="lib-fn">2</span><div class="lib-fh">추출한 성향</div>${bar && bar.status === "observed" ? `<div class="ag-bars"><div class="ag-bar f-${bar.key}"><span class="ag-bl">${esc(bar.label)}</span><span class="ag-bt"><i style="width:${Math.round(bar.level * 100)}%"></i></span><span class="ag-bv">근거 ${bar.evidence_count}건</span></div></div>` : `<p>${esc(r.factor)}</p>`}<span class="lib-ex">연결 근거 ${r.fact_ids.length}건</span></div>
    <div class="lib-farr" aria-hidden="true">→</div>
    <div class="lib-fs win"><span class="lib-fn">3</span><div class="lib-fh">이번 저녁 선택에 기여</div><p><b>${esc(r.factor)} +${r.parts.review.toFixed(2)}</b></p><p>${esc(V)} · ${esc(prod)} <span class="hint">(선택 점수 ${c.choice.score.toFixed(2)} · 확률 아님)</span></p></div>`;
}

// ---------------------------------------------------------------- 3. 지도로 — 같은 ID 를 엔진에 넘긴다
function libSim(id, exp) {
  AG.one = id; AG.keep.agent = null; AG.res = null; AG.autorun = true; AG.from = id;
  AG.exp = exp ? Object.assign({ agent: id }, exp) : null;
  if (exp && exp.cond) { AG.cond = Object.assign({ pricing: "historical", product_levers: {} }, JSON.parse(JSON.stringify(exp.cond))); AG.open = new Set(Object.keys(AG.cond.product_levers)); }
  else if (!exp) { /* 실험 없이 들어오면 조건은 그대로 */ }
  LIBV.hl.clear();
  setMode("agent");
}
// 10/23 프로파일 → 운영 실험(역설계) — 얇은 계층: persona_experiments.json 의 카드를 보여주고, 누르면 그 조건을 운영 조건 패널에 넣어 실행
const LIB_XCLS = { direct: ["직접 관련 경험", "ok"], transfer: ["유사 경험 기반 · 전이 가설", ""], common: ["공통 계산 중심", ""], na: ["현재 평가 불가", "na"] };
function libExps(p) {
  const xs = LIBV.exp && LIBV.exp.experiments && LIBV.exp.experiments[p.id];
  if (!xs || !xs.length) return "";
  const card = x => { const [cl, k] = LIB_XCLS[x.class] || [x.class, ""];
    const why = x.basis[0] ? x.basis[0].why.replace(/^\(팀 최신본\)\s*/, "") : "", not = x.engine_note && x.engine_note.includes("—") ? x.engine_note.split("—").slice(1).join("—").trim() : "";
    const info = [why && `착안: ${why}`, `바꾸는 조건: ${x.change || x.levers}`, not && `계산하지 않은 것: ${not}`].filter(Boolean).join(" · ");
    return `<div class="lib-xp ${x.cond ? "" : "na"}"><div class="lib-xt"><b>${esc(x.title || x.question)}</b>${noteI(info)}</div><div class="lib-xtp">${esc(x.topic || "")}</div>
      <div class="lib-xc">${esc(x.change || x.levers)}</div>${x.demo === false && x.demo_note ? `<div class="hint" title="${esc(x.demo_note)}">공통 설계 가정 중심 · 시연 대표 아님</div>` : ""}
      ${x.cond ? `<button type="button" class="rv-btn lib-xrun" data-x="${esc(x.id)}">이 조건으로 실험</button>` : `<span class="ag-st na">현재 계산 불가</span>`}
      <details class="lib-xd"><summary>질문 배경 · 후기 근거</summary><p>${esc(x.question)}</p>
        <div class="lib-xk">질문을 떠올린 경험 <span class="hint">후기에서 착안한 가설</span></div><div class="lib-xb">${x.basis.slice(0, 3).map(b => `<button type="button" class="lib-xf${/팀 최신본/.test(b.why) ? " new" : ""}" data-xf="${esc(b.fact)}" title="${esc(idTxt(b.why))}">${esc(fidD(b.fact))}</button>`).join("")}</div>
        ${x.basis.some(b => /팀 최신본/.test(b.why)) ? `<div class="hint">점선 = 최신 연구 자료(현재 엔진 입력에 없음 · 계산에 쓰이지 않음)</div>` : ""}
        <div class="lib-xk">변경 조건에서 엔진이 선택에 쓴 후기 근거</div><div class="lib-xb">${(x.calc_facts || []).length ? x.calc_facts.map(f => `<button type="button" class="lib-xf" data-xf="${esc(f)}">${esc(fidD(f))}</button>`).join("") : `<span class="hint">없음 — 공통 계산만</span>`}</div>
        <div class="hint">${esc(x.engine_note || "")}</div>
        <div class="hint">${esc(LIB_XCLS[x.class] ? LIB_XCLS[x.class][0] : x.class)}<span class="dev"> · ${esc(x.id)}</span>${x.unverified && x.unverified.length ? " · 미검증: " + esc(idTxt(x.unverified.join(" / "))) : ""}</div></details></div>`; };
  return `<div class="card lib-xps"><div class="g-sec">이 고객으로 실험해볼 운영 상황 <span>후기에서 착안한 가설 · ${xs.length}개</span>${noteI("고객의 실제 후기 사실과 다른 경험의 행동규칙에서 '운영자가 바꿀 수 있는 조건' 으로 이어지는 질문만 골랐습니다. 누르면 그 조건을 지도 시뮬레이터의 운영 조건에 넣고 기준 조건과 나란히 계산합니다. 직접 관련 경험이 있어도 예측 정확도가 보장되는 것은 아니며, 유사 경험 기반은 전이 가설입니다.")}</div><div class="lib-xgrid">${xs.map(card).join("")}</div></div>`;
}
