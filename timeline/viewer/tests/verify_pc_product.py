import json,sys,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE=sys.argv[1].rstrip('/'); OUT=Path(sys.argv[2]); OUT.mkdir(parents=True,exist_ok=True)
results=[]
def pause(page):
    if page.evaluate('typeof AG!=="undefined" && !!AG.playing') and page.locator('#strip .ag-play').count(): page.locator('#strip .ag-play').click()
def wait_flow(page):
    page.wait_for_function('!AG.busy && AG.runs.length>0 && AG.flow && AG.flow.ledger',timeout=90000); pause(page)
def wait_revenue(page):
    page.wait_for_function('!REV.busy && REV.ledger && REV.completedKey===revDraftKey()',timeout=90000)
def shot(page,name): page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
def amounts(page):
    return page.evaluate('({ids:Object.keys(REV.ledger.receipts).sort(),total:REV.ledger.totals.paid_krw,receipts:Object.fromEntries(Object.entries(REV.ledger.receipts).map(([id,r])=>[id,r.paid_krw])),levels:Object.fromEntries(Object.entries(REV.ledger.levels).map(([k,rows])=>[k,rows.reduce((s,r)=>s+r.paid_krw,0)])),run:REV.ledger.run_id})')
def balanced(x): return sum(x['receipts'].values())==x['total'] and all(v==x['total'] for v in x['levels'].values())
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    for width in (1440,1024):
        r={'width':width,'checks':[],'console_errors':[],'page_errors':[],'http_errors':[],'flow_requests':[]}
        def check(name,ok,detail=None):
            r['checks'].append({'name':name,'pass':bool(ok),'detail':detail}); print(width,name,'PASS' if ok else 'FAIL',flush=True)
        page=browser.new_page(viewport={'width':width,'height':1000})
        page.on('pageerror',lambda e:r['page_errors'].append(str(e)))
        page.on('console',lambda m:r['console_errors'].append(m.text) if m.type=='error' else None)
        page.on('response',lambda x:r['http_errors'].append({'status':x.status,'url':x.url}) if x.status>=400 else None)
        page.on('request',lambda x:r['flow_requests'].append(x.post_data_json) if x.url.endswith('/api/flow') and x.method=='POST' else None)
        try:
            page.goto(BASE+'/',wait_until='domcontentloaded'); page.locator('.lb-tile[data-t="전체"]').wait_for(timeout=60000); page.locator('.lb-tile[data-t="전체"]').click(); page.locator('.lb-card').first.wait_for()
            check('37_library_cards',page.locator('.lb-card').count()==37,page.locator('.lb-card').count())
            if width==1440:
                cards=page.locator('.lb-card').evaluate_all('(es)=>es.map(e=>({id:e.dataset.id||e.dataset.c,catalog:!!e.dataset.c}))'); detail=[]
                for c in cards:
                    page.locator(f'[data-cp="{c["id"]}"]' if c['catalog'] else f'[data-pf="{c["id"]}"]').click(); page.locator('.lb-det').wait_for(); detail.append({'id':c['id'],'content':len(page.locator('.lb-det').inner_text())>180}); page.locator('#libBack').click()
                check('37_details_open',len(detail)==37 and all(x['content'] for x in detail))
            shot(page,f'library_{width}')
            page.locator('[data-run="A01"]').click(); page.locator('#sitRun').wait_for(); page.locator('#sitRun').click(); wait_flow(page)
            first=page.evaluate('({run:AG.flow.ledger.run_id,amount:AG.flow.ledger.receipts.A01.paid_krw,source:AG.flow.ledger.source})')
            check('1_A01_live_receipt',first['source']=='live_engine' and first['amount']==626000,first)
            page.locator('#rcReceipt').scroll_into_view_if_needed(); shot(page,f'A01_receipt_{width}')
            check('consumption_title',page.locator('#rcReceipt h3').inner_text()=='하루 소비 내역')
            page.locator('#rcReceipt [data-rc-revenue]').scroll_into_view_if_needed();shot(page,f'consumption_to_revenue_button_{width}')
            n=len(r['flow_requests']); page.locator('#rcReceipt [data-rc-revenue]').click(); page.locator('[data-rev-scope="recent"]').wait_for(); wait_revenue(page)
            check('4_recent_keeps_exact_result',page.evaluate('REV.scope==="recent" && REV.ledger.run_id===REV.latest.flow.ledger.run_id && Object.keys(REV.ledger.receipts).join()==="A01"') and len(r['flow_requests'])==n,amounts(page))
            check('1_receipt_revenue_equal',amounts(page)['total']==first['amount'] and balanced(amounts(page)))
            shot(page,f'recent_A01_{width}')
            check('recent_is_readonly',page.locator('#revScenario, #revType, #revStay, #revRun').count()==0)
            page.locator('[data-rev-scope="selected"]').click()
            page.locator('[data-rev-select="A01"]').uncheck(); page.locator('[data-rev-select="A02"]').check(); page.locator('#revScenario').select_option('none'); page.locator('#revRun').click(); wait_revenue(page)
            second=amounts(page); check('direct_A02_only',second['ids']==['A02'] and balanced(second),second)
            page.locator('[data-rev-select="A01"]').check(); check('draft_hides_old_revenue',page.locator('.rev-summary').count()==0 and page.evaluate('REV.ledger===null')); page.locator('#revRun').click(); wait_revenue(page)
            group=amounts(page)
            check('2_A01_A02_receipts_equal_group',group['ids']==['A01','A02'] and group['receipts']['A01']==first['amount'] and group['receipts']['A02']==second['total'] and balanced(group),group)
            shot(page,f'selected_two_{width}')
            page.locator('#revScenario').select_option('wine'); page.locator('#revRun').click(); wait_revenue(page)
            check('5_same_selected_group_event_delta',page.evaluate('REV.comparison.comparable && Object.keys(REV.comparison.customers).sort().join()==="A01,A02" && REV.comparison.venues.reduce((s,v)=>s+v.delta_krw,0)===REV.comparison.delta_krw') and balanced(amounts(page)))
            shot(page,f'selected_two_comparison_{width}')
            n=len(r['flow_requests']);page.locator('[data-rev-scope="recent"]').click();wait_revenue(page)
            check('return_recent_original_626000',amounts(page)['run']==first['run'] and amounts(page)['total']==626000 and len(r['flow_requests'])==n)
            page.locator('[data-rev-scope="all"]').click();check('scope_change_hides_old_revenue',page.locator('.rev-summary').count()==0);page.locator('#revScenario').select_option('none'); page.locator('#revRun').click(); wait_revenue(page)
            full=amounts(page); check('3_all_11_L5_to_L1',len(full['ids'])==11 and balanced(full),full)
            page.locator('#revScenario').select_option('wine'); page.locator('#revRun').click(); wait_revenue(page)
            check('all_11_same_cohort_comparison',page.evaluate('REV.comparison.comparable && REV.comparison.team_count===11') and balanced(amounts(page)))
            page.locator('[data-rev-venue]').first.click(); page.locator('[data-rev-product]').first.click(); page.locator('[data-rev-customer]').first.click()
            selected=page.evaluate('({pid:REV.customer,run:REV.flow.ledger.run_id,product:REV.product})')
            check('6_venue_product_customer_receipt',page.locator('.rev-customer-line small').count()>0 and page.locator('.rev-drill .rc-receipt').count()==1 and page.locator('.rev-customer-line.on').count()==1)
            shot(page,f'venue_customer_drill_{width}')
            page.locator('.rev-drill .rc-detail > summary').click(); page.locator('.rev-drill .rc-detail li details > summary').first.click(); n=len(r['flow_requests']); page.locator('.rev-drill [data-rc-turn]').first.click(); page.locator('#drawer:not(.hidden)').wait_for()
            check('6_exact_run_evidence_link',page.evaluate('AG.flow.ledger.run_id===REV.flow.ledger.run_id && AG.sel===REV.customer') and page.locator('#drBody').inner_text().strip()!='' and len(r['flow_requests'])==n,selected)
            shot(page,f'evidence_{width}'); page.locator('#drClose').click()
            page.locator('nav .tab[data-mode="opx"]').click(); page.locator('#revCustomerFlow').wait_for(); page.locator('#revCustomerFlow').click(); page.locator('#rcReceipt').wait_for()
            check('6_customer_flow_same_run',page.evaluate('AG.flow.ledger.run_id===REV.flow.ledger.run_id && AG.sel===REV.customer'))
            page.locator('nav .tab[data-mode="opx"]').click(); page.locator('#revProduct > summary').click(); page.wait_for_function('OPX.last && !OPX.busy',timeout=90000)
            check('existing_product_experiment',page.evaluate('OPX.last.experiment.run_status==="COMPLETED"'))
            check('PC_no_horizontal_overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            check('visible_images_loaded',page.locator('img:visible').evaluate_all('(es)=>es.every(e=>e.complete && e.naturalWidth>0)'))
            page.locator('nav .tab[data-mode="day"]').click();page.locator('#flowSeg [data-m="agents"]').click();page.locator('#agRun').click();wait_flow(page)
            multi=page.evaluate('({run:AG.flow.ledger.run_id,count:AG.flow.ledger.team_count,total:AG.flow.ledger.totals.paid_krw})');n=len(r['flow_requests'])
            page.locator('#rcReceipt [data-rc-revenue]').click();wait_revenue(page)
            check('recent_multiple_exact_result',multi['count']==11 and amounts(page)['run']==multi['run'] and amounts(page)['total']==multi['total'] and len(r['flow_requests'])==n and page.locator('#revRun').count()==0)
            page.goto(BASE+'/#demo/F1',wait_until='domcontentloaded'); page.reload(wait_until='domcontentloaded'); page.locator('#agRun').wait_for(timeout=60000); n=len(r['flow_requests']); page.locator('#agRun').click(); wait_flow(page)
            check('stored_demo_stays_separate',page.evaluate('AG.flow.ledger.source==="stored_demo" && REV.latest.flow.ledger.source==="stored_demo"') and len(r['flow_requests'])==n)
            page.locator('#rcReceipt [data-rc-revenue]').click();page.locator('[data-rev-scope="recent"]').wait_for();wait_revenue(page)
            check('recent_replay_labeled_and_unchanged',page.evaluate('REV.ledger.source==="stored_demo" && REV.ledger.run_id===REV.latest.flow.ledger.run_id') and page.locator('#revRun').count()==0 and len(r['flow_requests'])==n)
        except Exception as e:
            r['error']=str(e);r['traceback']=traceback.format_exc();print(width,'ERROR',str(e),flush=True)
            try: shot(page,f'ERROR_{width}')
            except Exception: pass
        finally:
            check('no_console_or_network_errors',not r['page_errors'] and not r['console_errors'] and not r['http_errors'],{'console':r['console_errors'],'page':r['page_errors'],'http':r['http_errors']})
            page.close(); results.append(r); (OUT/'RESULTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    browser.close()
print(json.dumps({'viewports':len(results),'checks':sum(len(r['checks']) for r in results),'passed':sum(c['pass'] for r in results for c in r['checks']),'failed':sum(not c['pass'] for r in results for c in r['checks']),'errors':sum('error' in r for r in results)}),flush=True)
