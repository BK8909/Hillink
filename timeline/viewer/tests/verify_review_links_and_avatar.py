import json,sys,hashlib,traceback,time
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip('/');OUT=Path(sys.argv[2]);OUT.mkdir(parents=True,exist_ok=True);results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 for width in (1440,1024):
  r={'width':width,'checks':[],'errors':[],'console_errors':[],'http_errors':[],'flow_requests':[],'external_links':[]}
  def check(name,ok,detail=None):r['checks'].append({'name':name,'pass':bool(ok),'detail':detail});print(width,name,'PASS' if ok else 'FAIL',flush=True)
  page=browser.new_page(viewport={'width':width,'height':1000})
  page.on('pageerror',lambda e:r['errors'].append(str(e)));page.on('console',lambda m:r['console_errors'].append(m.text) if m.type=='error' else None)
  page.on('response',lambda x:r['http_errors'].append({'status':x.status,'path':x.url.split(BASE)[-1]}) if x.status>=400 and x.url.startswith(BASE) else None)
  page.on('request',lambda x:r['flow_requests'].append(x.post_data_json) if x.url.endswith('/api/flow') and x.method=='POST' else None)
  def select(pid):
   page.locator('#agOne').select_option(pid);page.wait_for_function('(pid)=>!!document.querySelector("#agent .ag-prepared[data-p="+pid+"]")',arg=pid)
  try:
   page.goto(BASE+'/',wait_until='domcontentloaded');page.locator('.lb-tile[data-t="전체"]').wait_for(timeout=60000);page.locator('.lb-tile[data-t="전체"]').click()
   check('library_37',page.locator('.lb-card').count()==37)
   for pid in ('A01','A02','A08'):
    page.locator('[data-pf="'+pid+'"]').click();page.locator('a.lb-srcbtn').wait_for()
    page.locator('.lb-rel > summary').click();page.locator('#libEf > summary').click()
    expected=page.evaluate('(pid)=>{const p=LIBV.data.personas.find(p=>p.id===pid);return {start:libStartUrl(p).url,related:[...(p.wh_events||[]),...(p.other_events||[])].flatMap(e=>e.posts||[]).map(id=>libUrl(id)).filter(Boolean).map(v=>v.url),facts:Object.values((p.engine||{}).facts||{}).map(f=>libUrl(f.post)).filter(Boolean).map(v=>v.url)}}',pid)
    primary=page.locator('a.lb-srcbtn');related=page.locator('.lb-rels a.lib-src').first;fact=page.locator('#libEf a.lib-src').first
    check(pid+'_source_mapping',primary.get_attribute('href')==expected['start'] and related.get_attribute('href') in expected['related'] and fact.get_attribute('href') in expected['facts'])
    # Open original links through real user clicks. Record no author, URL or source text.
    if width==1440:
     for label,a in [('representative',primary),('related',related),('fact',fact)]:
      href=a.get_attribute('href');a.scroll_into_view_if_needed()
      with page.expect_popup(timeout=15000) as popup_info:a.click()
      popup=popup_info.value;status=None;opened=False;error=None
      try:
       popup.wait_for_load_state('domcontentloaded',timeout=20000);opened=popup.url.startswith('http')
       status=popup.evaluate('document.readyState')
      except Exception as e:
       opened=popup.url.startswith('http') and not popup.url.startswith('chrome-error:');error=type(e).__name__
      r['external_links'].append({'customer':pid,'kind':label,'href_sha256':hashlib.sha256(href.encode()).hexdigest(),'navigation_opened':opened,'ready_state':status,'error':error})
      check(pid+'_'+label+'_popup',opened,{'ready_state':status,'error':error});popup.close()
    page.screenshot(path=str(OUT/f'profile_{pid}_{width}.png'),full_page=True);page.locator('#libBack').click()
   page.locator('nav .tab[data-mode="day"]').click();page.locator('#agOne').wait_for(timeout=60000)
   check('before_customer_empty',page.locator('#agent .ag-avatar').count()==0 and not r['flow_requests'])
   select('A01');check('selected_avatar_no_simulation',page.locator('#agent .ag-avatar').count()==1 and page.evaluate('AG.res===null && AG.runs.length===0 && !AG.playing') and not r['flow_requests'] and page.locator('#rcReceipt').count()==0)
   for bld in ('GRAND','VISTA','DOUGLAS'):
    page.locator('#agBld').select_option(bld);page.wait_for_function('(b)=>document.querySelector("#agent .ag-prepared").dataset.start===b+"_ROOM"',arg=bld)
    check('ready_'+bld,page.evaluate('(b)=>{const a=document.querySelector("#agent .ag-avatar");return !!a&&!!LOC[b+"_ROOM"]&&document.querySelector("#agent .ag-tag text").textContent.includes("No.0001")}',bld) and not r['flow_requests'])
   page.locator('#agStay [data-v="0"]').click();page.wait_for_function('document.querySelector("#agent .ag-prepared").dataset.start==="HOTEL_GATE"');check('nonstay_ready_gate',not r['flow_requests'])
   page.locator('#agStay [data-v="1"]').click();select('A02');check('customer_ready_updates',page.locator('#agent .ag-tag').text_content().startswith('No.0002') and not r['flow_requests'])
   page.screenshot(path=str(OUT/f'avatar_ready_{width}.png'),full_page=True)
   # Follow the actual requested library -> situation -> live flow path.
   page.locator('nav .tab[data-mode="library"]').click();page.locator('[data-pf="A01"]').click();page.locator('#libSimWine').click();page.locator('#sitRun').wait_for()
   page.locator('[data-sit-event="none"]').click();page.locator('#sitRun').click();page.wait_for_function('!AG.busy && AG.flow && AG.flow.ledger && AG.runs.length>0',timeout=90000)
   if page.evaluate('!!AG.playing'):page.locator('#strip .ag-play').click()
   paid=page.evaluate('AG.flow.ledger.totals.paid_krw');run=page.evaluate('AG.flow.ledger.run_id')
   check('live_receipt_626000',paid==626000 and page.evaluate('AG.flow.ledger.source==="live_engine"') and len(r['flow_requests'])==1)
   page.locator('#rcReceipt [data-rc-revenue]').scroll_into_view_if_needed();page.screenshot(path=str(OUT/f'live_receipt_{width}.png'),full_page=True)
   n=len(r['flow_requests']);page.locator('#rcReceipt [data-rc-revenue]').click();page.locator('.rev-readonly').wait_for();check('same_run_revenue_no_calculation',page.evaluate('REV.ledger.run_id')==run and page.evaluate('REV.ledger.totals.paid_krw')==paid and len(r['flow_requests'])==n)
   page.screenshot(path=str(OUT/f'recent_revenue_{width}.png'),full_page=True)
   check('no_product_errors',not r['errors'] and not r['console_errors'] and not r['http_errors'],{'page':r['errors'],'console':r['console_errors'],'http':r['http_errors']})
  except Exception as e:
   r['exception']=str(e);r['traceback']=traceback.format_exc();print(r['traceback'],flush=True);page.screenshot(path=str(OUT/f'ERROR_{width}.png'),full_page=True)
  finally:
   results.append(r);(OUT/'RESULTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));page.close()
 browser.close()
print(json.dumps({'checks':sum(len(r['checks']) for r in results),'pass':sum(c['pass'] for r in results for c in r['checks']),'fail':sum(not c['pass'] for r in results for c in r['checks']),'exceptions':sum('exception' in r for r in results)}))
