import json,sys,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip('/');OUT=Path(sys.argv[2]);OUT.mkdir(parents=True,exist_ok=True);results=[]
def shot(page,name):page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
def wait_flow(page):
 page.wait_for_function('!AG.busy && AG.runs.length>0 && AG.flow && AG.flow.ledger',timeout=90000)
 if page.evaluate('!!AG.playing'):page.locator('#strip .ag-play').click()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 for width in (1440,1024):
  r={'width':width,'checks':[],'page_errors':[],'console_errors':[],'http_errors':[],'flow_requests':[]}
  def check(name,ok,detail=None):r['checks'].append({'name':name,'pass':bool(ok),'detail':detail});print(width,name,'PASS' if ok else 'FAIL',flush=True)
  page=browser.new_page(viewport={'width':width,'height':1000})
  page.on('pageerror',lambda e:r['page_errors'].append(str(e)));page.on('console',lambda m:r['console_errors'].append(m.text) if m.type=='error' else None)
  page.on('response',lambda x:r['http_errors'].append({'status':x.status,'url':x.url}) if x.status>=400 else None)
  page.on('request',lambda x:r['flow_requests'].append(x.post_data_json) if x.method=='POST' and x.url.endswith('/api/flow') else None)
  try:
   page.goto(BASE+'/',wait_until='domcontentloaded');page.locator('.lb-tile[data-t="전체"]').wait_for(timeout=60000);page.locator('.lb-tile[data-t="전체"]').click();page.locator('[data-pf="A01"]').click();page.locator('#libSimWine').wait_for()
   check('detail_action_label',page.locator('#libSimWine').inner_text()=='이 고객의 상황별 하루 보기 →')
   page.locator('#libSimWine').click();page.locator('#sitRun').wait_for();page.wait_for_function('SIT.options && SIT.pid==="A01"')
   check('profile_to_setup_without_calculation',not r['flow_requests'] and page.locator('.st-hero h1').inner_text().startswith('No.0001'))
   traits=page.locator('.st-hero .lb-htr').inner_text();check('existing_traits_and_thumbnail',2<=page.locator('.st-hero .lb-htr span').count()<=3 and page.locator('.st-hero .lb-th').count()==1)
   check('future_options_disabled',page.locator('[data-sit-event="pool_party"]').is_disabled() and page.locator('.st-future button:not(:disabled)').count()==0)
   check('setup_PC_no_overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'));shot(page,f'situation_none_{width}');page.locator('#sitRun').scroll_into_view_if_needed();shot(page,f'situation_actions_{width}')
   page.locator('[data-sit-event="none"]').click();page.locator('#sitRun').click();wait_flow(page)
   off=page.evaluate('({request:AG.flow.request,run:AG.flow.ledger.run_id,paid:AG.flow.ledger.receipts.A01.paid_krw,visit:AG.flow.result.visits.A01,bars:AG.meta.personas.find(p=>p.id==="A01").bars,source:AG.flow.ledger.source})')
   check('none_actual_engine',off['source']=='live_engine' and off['request']['event'] is False and off['request']['visit_override'] is None and off['paid']==626000,{'paid':off['paid'],'run':off['run']})
   check('engine_note_two_lines',page.locator('.fr-static span').filter(has_text='LLM 호출 0').locator('br').count()==1)
   page.locator('#rcReceipt').scroll_into_view_if_needed();shot(page,f'flow_none_{width}');n=len(r['flow_requests']);page.locator('#rcReceipt [data-rc-revenue]').click();page.wait_for_function('REV.ledger && REV.scope==="recent"')
   page.locator('.rev-readonly').wait_for();check('none_revenue_same_run_readonly',page.evaluate('REV.ledger.run_id===REV.latest.flow.ledger.run_id && REV.ledger.totals.paid_krw===626000') and len(r['flow_requests'])==n and page.locator('#revRun').count()==0);shot(page,f'recent_none_{width}')
   page.locator('nav .tab[data-mode="day"]').click();page.locator('#agSituation').wait_for();page.locator('#agSituation').click();page.locator('#sitRun').wait_for()
   check('return_to_setup_same_persona',page.evaluate('SIT.pid==="A01" && situationForm("A01").event==="none"') and page.locator('.st-hero .lb-htr').inner_text()==traits)
   page.locator('[data-sit-event="wine"]').click();shot(page,f'situation_wine_{width}');page.locator('#sitRun').click();wait_flow(page)
   wine=page.evaluate('({request:AG.flow.request,run:AG.flow.ledger.run_id,paid:AG.flow.ledger.receipts.A01.paid_krw,visit:AG.flow.result.visits.A01,bars:AG.meta.personas.find(p=>p.id==="A01").bars,source:AG.flow.ledger.source})')
   left=dict(off['request']);right=dict(wine['request']);left.pop('event');right.pop('event')
   check('wine_actual_engine_event_only',wine['source']=='live_engine' and wine['request']['event'] is True and left==right and off['visit']==wine['visit'] and off['bars']==wine['bars'],{'off':off['paid'],'on':wine['paid']})
   page.locator('#rcReceipt').scroll_into_view_if_needed();shot(page,f'flow_wine_{width}');n=len(r['flow_requests']);page.locator('#rcReceipt [data-rc-revenue]').click();page.wait_for_function('(id)=>REV.ledger && REV.ledger.run_id===id',arg=wine['run'])
   page.locator('.rev-readonly').wait_for();check('wine_revenue_same_run',page.evaluate('REV.ledger.totals.paid_krw')==wine['paid'] and len(r['flow_requests'])==n);shot(page,f'recent_wine_{width}')
   page.locator('nav .tab[data-mode="day"]').click();page.locator('#agSituation').click();page.locator('#sitCustom').check();check('incomplete_visit_cannot_run',page.locator('#sitRun').is_disabled())
   page.locator('#sitStay').select_option('1');page.locator('#sitBuilding').select_option('VISTA');page.locator('#sitPhase').select_option('checkout');page.locator('#sitParty').select_option('2');page.locator('#sitRun').click();wait_flow(page)
   check('supported_visit_override_actual',page.evaluate('AG.flow.result.visits.A01.building==="VISTA" && AG.flow.result.visits.A01.phase==="checkout" && AG.flow.result.visits.A01.party_size===2 && AG.flow.ledger.receipts.A01.assumption_addition_krw===0'))
   check('future_axes_not_sent',all(not any(k in q for k in ('weather','weekday','pool_party','purpose')) for q in r['flow_requests']) and len(r['flow_requests'])==3)
   page.locator('#agSituation').click();page.locator('#sitBack').click();page.locator('#libSimWine').wait_for();page.locator('#libBack').click();page.locator('.lb-card').first.wait_for();check('library_37_preserved',page.locator('.lb-card').count()==37)
   page.goto(BASE+'/#demo/F1',wait_until='domcontentloaded');page.reload(wait_until='domcontentloaded');page.locator('#agRun').wait_for(timeout=60000);n=len(r['flow_requests']);page.locator('#agRun').click();wait_flow(page)
   check('stored_demo_preserved',page.evaluate('AG.flow.ledger.source==="stored_demo"') and len(r['flow_requests'])==n)
  except Exception as e:
   r['error']=str(e);r['traceback']=traceback.format_exc();print(width,'ERROR',str(e),flush=True)
   try:shot(page,f'ERROR_{width}')
   except Exception:pass
  finally:
   check('no_console_or_network_errors',not r['page_errors'] and not r['console_errors'] and not r['http_errors'],{'page':r['page_errors'],'console':r['console_errors'],'http':r['http_errors']});page.close();results.append(r);(OUT/'RESULTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 browser.close()
print(json.dumps({'viewports':len(results),'checks':sum(len(r['checks']) for r in results),'passed':sum(c['pass'] for r in results for c in r['checks']),'failed':sum(not c['pass'] for r in results for c in r['checks']),'errors':sum('error' in r for r in results)}),flush=True)
