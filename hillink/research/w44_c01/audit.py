"""Reproducible source/runtime full outer inventory, without activating proposals."""
import csv,hashlib,json,re,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT/'timeline/experiments/persona_live'))
from operator_choice.autonomy_v1 import candidate_services as C
A=C.AD;S=A.SP
FIELDS='venue_id display_name source_path source_id source_checked_at source_sha operational_status service_period date_rule official_hours last_order eligibility reservation_state venue_candidate_id active_runtime_candidate activity_id product_sku_id sku_meal_period price_status price_source source_approval_status runtime_loader_path run_id_sample blocked_reason gap_type proposed_fix QA_status'.split()
ALIAS={'BUFFET':'THE_BUFFET','PIZZAHILL':'PIZZA_HILL','GRAND-SAUNA':'WELLNESS_SAUNA','GRAND_SAUNA':'WELLNESS_SAUNA','SAUNA':'WELLNESS_SAUNA','FOREST':'FOREST_PARK','LEPASSAGE':'LE_PASSAGE','TENNIS':'TENNEZ_PARK','IRD':'ROOM_MEAL'}
def normalize(v):return ALIAS.get(v,v)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def periods(w):
 if not w:return 'UNKNOWN'
 return 'breakfast' if w[0]<600 else 'lunch' if w[0]<960 else 'dinner'
def main():
 catalog=json.loads((HERE/'sources/verified_price_catalog.json').read_text())
 sources=json.loads((HERE/'sources/official_source_register.json').read_text())
 cross=json.loads((HERE/'sources/outlet_action_crosswalk.json').read_text())
 runtime=[]
 for code,a in S.ACT.items():
  for building in ('GRAND','VISTA','DOUGLAS'):
   venue=a[1](building)
   if any(r['activity_id']==code and r['venue_id']==venue for r in runtime):continue
   runtime.append(dict(venue_id=venue,activity_id=code,display_name=a[0],service_period='lunch' if code.startswith('lunch_') else a[2],runtime_loader_path='operator_world_v1_1/stay_planner.py:ACT',price_status='EXISTING_MODEL_OR_UNKNOWN',blocked_reason=A.SEASON_CLOSED.get(code,A.NOT_ELIGIBLE.get(code,'CONDITIONAL_WORLD_ELIGIBILITY'))))
 for o in A.WD.default_world()['offers']:
  v=A.ENGINE_LOC.get(o['id'],o['venue'])
  for venue in (['GRAND_POOL','VISTA_POOL'] if v=='@pool' else ['GRAND_ROOM','VISTA_ROOM','DOUGLAS_ROOM'] if v=='@room' else [normalize(v)]):
   runtime.append(dict(venue_id=venue,activity_id=o['id'],display_name=o['label'],service_period='dinner' if o['kind']=='restaurant' else o['kind'],runtime_loader_path='operator_world_v1/world.py:default_world',price_status='EXISTING_MODEL_NOT_CURRENT_PRICE',blocked_reason='CONDITIONAL_WORLD_ELIGIBILITY'))
 for code,venue,period in [('lounge','DOUGLAS_LOUNGE','snack'),('library','DOUGLAS_LIBRARY','rest')]:
  runtime.append(dict(venue_id=venue,activity_id=code,display_name=venue,service_period=period,runtime_loader_path='autonomy_v1/candidate_services.py',price_status='ENTITLEMENT_NOT_NEW_PAYMENT',blocked_reason='CURRENT_DOUGLAS_GUEST; EXTRA_PEOPLE_UNCONFIRMED'))
 for code,venue,label,period in [('BREAKFAST_BUFFET','THE_BUFFET','더뷔페 조식','breakfast'),('lunch_buffet','THE_BUFFET','더뷔페 중식','lunch')]:
  runtime.append(dict(venue_id=venue,activity_id=code,display_name=label,service_period=period,runtime_loader_path='autonomy_v1/candidate_services.py',price_status='AMOUNT_UNKNOWN_OR_EXPLICIT_ENTITLEMENT',blocked_reason='EXPLICIT_M4_C01_ONLY'))
 for code in ('RS_BREAKFAST_KOREAN','RS_BREAKFAST_AMERICAN','RS_MORNING_BREAD_SET','RS_EGG_DISH','SKIP_BREAKFAST'):
  runtime.append(dict(venue_id='ROOM_MEAL',activity_id=code,display_name=code,service_period='breakfast',runtime_loader_path='operator_world_v1_1/turn_candidate.py',price_status='HISTORICAL_MODEL_REFERENCE',blocked_reason='GUEST_BREAKFAST_WINDOW'))
 runtime.append(dict(venue_id='MOEGI',activity_id='MOEGI',display_name='모에기 저녁',service_period='dinner',runtime_loader_path='autonomy_v1/candidate_services.py',price_status='AMOUNT_UNKNOWN',blocked_reason='EXPLICIT_M4_C01_ONLY'))
 for building in ('GRAND','VISTA','DOUGLAS'):
  runtime.append(dict(venue_id=building+'_ROOM',activity_id='room_night',display_name=building+' 객실박',service_period='night',runtime_loader_path='viewer/room_revenue.py',price_status='VIRTUAL_STARTING_PRICE',blocked_reason='NIGHTS_MUST_BE_POSITIVE'))
 rows=[];used=set()
 for sku in catalog:
  venue=normalize(sku['outlet_id']);cond=sku.get('conditions') or {};meal=cond.get('meal','UNKNOWN')
  matches=[r for r in runtime if r['venue_id']==venue and (meal=='UNKNOWN' or meal in str(r['service_period']))]
  source=sources.get(sku.get('price_source_id'),{})
  proposal=next((x['status'] for x in cross if x['catalog_outlet_id']==sku['outlet_id']),'NOT_ENGINE_APPROVED')
  for r in matches or [{}]:
   if r:used.add((r['venue_id'],r['activity_id']))
   row=dict.fromkeys(FIELDS,'UNKNOWN');row.update(r)
   row.update(venue_id=venue,display_name=sku['label'],source_path='sources/verified_price_catalog.json',source_id=sku['price_source_id'],source_checked_at=source.get('checked_at_kst','UNKNOWN'),source_sha=source.get('sha256',source.get('html_sha256',sha(HERE/'sources/official_source_register.json'))),
    operational_status='POSTED_SOURCE_NOT_BOOKING',service_period=meal if meal!='UNKNOWN' else r.get('service_period','UNKNOWN'),date_rule=cond,official_hours='SOURCE_REGISTER_SCOPE',eligibility=sku.get('limits',[]),reservation_state='UNKNOWN_NOT_BOOKED',venue_candidate_id=r.get('activity_id','NOT_CONNECTED'),active_runtime_candidate=bool(r),product_sku_id=sku['sku_id'],sku_meal_period=meal,price_status=sku['price_status'],price_source=source.get('url','UNKNOWN'),source_approval_status=proposal,gap_type='SKU_PROPOSAL_NOT_APPROVED' if r else 'SOURCE_ONLY_NOT_CONNECTED',proposed_fix='Preserve venue independently; review product conditions before billing',QA_status='HOLD_SKU_APPROVAL')
   rows.append(row)
 for r in runtime:
  if (r['venue_id'],r['activity_id']) in used:continue
  row=dict.fromkeys(FIELDS,'UNKNOWN');row.update(r)
  row.update(source_path='timeline/walkerhill_timeline_validator.py',source_sha=sha(ROOT/'timeline/walkerhill_timeline_validator.py'),source_approval_status='EXISTING_RUNTIME_MODEL',venue_candidate_id=r['activity_id'],active_runtime_candidate=True,gap_type='RUNTIME_ONLY_NO_NEW_CATALOG_SKU',QA_status='AUDITED_PRICE_SCOPE_UNRESOLVED',proposed_fix='Retain explicit model/unknown price; do not invent SKU')
  rows.append(row)
 # Every collected operating venue, including map-only/source-only facilities.
 for venue,ws in C.V.WALKERHILL_VENUE_WINDOWS.items():
  for w in ws:
   matched=[r for r in runtime if r['venue_id']==venue or (venue=='WINE_FAIR' and r['activity_id']=='WINE_FAIR')]
   row=dict.fromkeys(FIELDS,'UNKNOWN')
   row.update(venue_id=venue,display_name=venue,source_path='timeline/walkerhill_timeline_validator.py',source_sha=sha(ROOT/'timeline/walkerhill_timeline_validator.py'),source_id='VenueWindow',source_approval_status=str(w.source),service_period=periods((w.open_at.hour*60+w.open_at.minute,0)),date_rule={'years':sorted(w.years) if w.years else None,'season':w.season,'weekdays':sorted(w.weekdays) if w.weekdays else None,'states':sorted(w.states) if w.states else None},official_hours=w.open_at.strftime('%H:%M')+'-'+w.close_at.strftime('%H:%M'),last_order=w.last_order.strftime('%H:%M') if w.last_order else 'UNKNOWN',active_runtime_candidate=bool(matched),activity_id=[r['activity_id'] for r in matched],gap_type='DATED_WINDOW_ADAPTER' if matched else 'SOURCE_WINDOW_WITHOUT_ACTIVITY',proposed_fix='C01 retains date predicates; no invented program or eligibility',QA_status='CONNECTED_CONDITIONAL' if matched else 'HOLD_ACTIVITY_CONTRACT',reservation_state='UNKNOWN_NOT_BOOKED')
   rows.append(row)
 # Historical price entries are a distinct inventory, never approved current SKU.
 import prices
 legacy_alias={'pizza':'PIZZA_HILL','pizza_to':'PIZZA_HILL','buffet_b':'THE_BUFFET','buffet_l':'THE_BUFFET','buffet_d':'THE_BUFFET','geum':'GEUMRYONG','myong':'MYONGWOLGWAN','moegi':'MOEGI','ondal':'ONDAL','pavilion':'THE_PAVILION','lepassage':'LE_PASSAGE','lux':'LUX_BAR','meal_other':'ROOM_MEAL','river':'RIVERPARK','theatre':'THEATRE_OF_LIGHT','sauna':'WELLNESS_SAUNA','pool':'GRAND_POOL','forest':'FOREST_PARK','skyard':'SKYARD','winefair':'FOREST_PARK','lounge_b':'GRAND_CLUB_LOUNGE','lounge_t':'GRAND_CLUB_LOUNGE','lounge_h':'GRAND_CLUB_LOUNGE','library':'GRAND_LIBRARY','dlibrary':'DOUGLAS_LIBRARY','valet':'VALET_DESK','park':'PARKING_TOWER_B1'}
 for key,p in prices.PRICE.items():
  venue=key.split(':')[1]+'_ROOM' if key.startswith('room:') else legacy_alias.get(key,key)
  matched=[r for r in runtime if r['venue_id']==venue]
  row=dict.fromkeys(FIELDS,'UNKNOWN');row.update(venue_id=venue,display_name=key,active_runtime_candidate=bool(matched),activity_id=[r['activity_id'] for r in matched],source_path='timeline/prices.py',source_id=key,source_sha=sha(ROOT/'timeline/prices.py'),price_status='HISTORICAL_MODEL_REFERENCE',price_source=p.get('src','UNKNOWN'),source_approval_status='REFERENCE_NOT_CURRENT_SALE',gap_type='HISTORICAL_VENUE_JOIN_NOT_SKU_APPROVAL' if matched else 'HISTORICAL_PRICE_WITHOUT_ACTIVITY',QA_status='HOLD_CURRENT_SKU_APPROVAL',product_sku_id=key)
  rows.append(row)
 # Map/UI POIs are discoverable metadata, not automatically runnable services.
 mapfile=ROOT/'timeline/viewer/static/map.js'
 section=mapfile.read_text().split('const LOC = mapObj({',1)[1].split('});',1)[0]
 pois=set(re.findall(r'([A-Z][A-Z_0-9]+):\s*\[',section))
 for venue in sorted(pois):
  matched=[r for r in runtime if r['venue_id']==venue]
  row=dict.fromkeys(FIELDS,'UNKNOWN');row.update(venue_id=venue,display_name=venue,source_path='timeline/viewer/static/map.js',source_sha=sha(mapfile),source_id='LOC',active_runtime_candidate=bool(matched),activity_id=[r['activity_id'] for r in matched],source_approval_status='MAP_DISPLAY_ONLY',gap_type='MAP_RUNTIME_JOIN' if matched else 'MAP_ONLY_NOT_ACTIVITY',QA_status='AUDITED_DISPLAY_NOT_ELIGIBILITY',proposed_fix='Transport/POI is not a chargeable action; unsupported facility stays explicit HOLD')
  rows.append(row)
 # Menu inventory is separate from a paid order. Preserve unmatched rows too.
 menu=ROOT/'timeline/menu.csv'
 name_map={'더뷔페':'THE_BUFFET','모에기':'MOEGI','명월관':'MYONGWOLGWAN','온달':'ONDAL','금룡':'GEUMRYONG','피자힐':'PIZZA_HILL','르파사쥬':'LE_PASSAGE','파빌리온':'THE_PAVILION','그랜드':'GRAND_ROOM','비스타':'VISTA_ROOM','더글라스':'DOUGLAS_ROOM'}
 for i,m in enumerate(csv.DictReader(menu.open(encoding='utf-8-sig')),2):
  venue=name_map.get(m['업장'],m['업장']);matched=[r for r in runtime if r['venue_id']==venue]
  row=dict.fromkeys(FIELDS,'UNKNOWN');row.update(venue_id=venue,display_name=m['상품'],source_path='timeline/menu.csv',source_id='row:'+str(i),source_sha=sha(menu),service_period=m['시간제한'] or 'UNKNOWN',date_rule={'from':m['판매시작'],'until':m['판매종료'],'weekdays':m['요일제한']},eligibility=m['포함'],active_runtime_candidate=bool(matched),activity_id=[r['activity_id'] for r in matched],product_sku_id=m['원장상품'],price_source=m['근거'],source_approval_status='EXISTING_MENU_NOT_CURRENT_ORDER',price_status='EXISTING_CATALOG_REFERENCE',gap_type='MENU_VENUE_JOIN' if matched else 'MENU_ONLY_UNMAPPED',QA_status='HOLD_SKU_APPLICATION',proposed_fix='No automatic paid order from menu row')
  rows.append(row)
 out=HERE/'SOURCE_RUNTIME_COVERAGE.csv'
 with out.open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
  writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list,bool)) else v for k,v in row.items()} for row in rows)
 (HERE/'SOURCE_RUNTIME_COVERAGE.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 summary={'rows':len(rows),'runtime_action_venue_pairs':len(runtime),'catalog_skus':len(catalog),'source_register_entries':len(sources),'gap_counts':dict(collections.Counter(r['gap_type'] for r in rows)),'status':'AUDIT_WITH_EXPLICIT_UNRESOLVED_NOT_FULL_ACCEPTANCE','paid_provider_calls':0}
 (HERE/'AUDIT_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
