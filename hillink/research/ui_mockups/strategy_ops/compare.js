const { chromium } = require('playwright');
const O='/mnt/user-data/outputs/W44_최신통합_20261101/UX_1103/';
(async()=>{const b=await chromium.launch();const pg=await b.newPage({viewport:{width:2240,height:540}});
const fs=require('fs');const col=(t,f)=>`<div class="c"><h2>${t}</h2><img src="data:image/png;base64,${fs.readFileSync(O+f).toString('base64')}"></div>`;
await pg.setContent(`<html><body style="margin:0;background:#eee5db;font-family:'Noto Sans KR',sans-serif"><div style="display:flex;gap:16px;padding:16px">${col('기존 · 운영 전략(현재 실행 분석 탭)','기존_1_현재실행분석_1440.png')}${col('시안 A · 호텔 RMS 중심','시안A_1440_Q20_fold.png')}${col('시안 B · 실험 의사결정 중심','시안B_1440_Q20_fold.png')}</div><style>.c{flex:1}.c img{width:100%;border-radius:10px;box-shadow:0 6px 20px #0002}h2{margin:4px 0 10px;font-size:22px;color:#3a322d}</style></body></html>`);
await pg.waitForTimeout(500);await pg.screenshot({path:O+'전후비교_1440_첫화면.png',fullPage:true});await b.close();console.log('ok')})();
