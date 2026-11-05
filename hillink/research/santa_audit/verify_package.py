"""Verify a delivered audit package without HILLINK or private customer inputs.
Usage: python3 verify_package.py [PACKAGE_DIRECTORY]
Checks integrity and arithmetic, not the truth of source reviews or actual POS.
"""
import hashlib,json,sys
from collections import Counter
from pathlib import Path

def verify(folder):
 manifest=json.loads((folder/'MANIFEST_SHA256.json').read_text())
 errors=[];checks={}
 for name,expected in manifest['files'].items():
  path=folder/name
  if path.parent!=folder or not path.is_file():errors.append('MISSING_OR_INVALID_PATH:'+name);continue
  if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:errors.append('CHECKSUM_MISMATCH:'+name)
 ledger=json.loads((folder/'ledger_L5.json').read_text());aggregates=json.loads((folder/'aggregates.json').read_text());recon=json.loads((folder/'reconciliation.json').read_text());config=json.loads((folder/'scenario_config.json').read_text())
 for name in ('A','S1','S2'):
  rows=ledger[name];total=sum(r.get('paid_krw') or 0 for r in rows)
  ids=[r.get('row_id') for r in rows];customers={r.get('customer_id') for r in rows}
  duplicate=len(ids)!=len(set(ids));level_sums={k:sum(r.get('paid_krw') or 0 for r in aggregates[name][k]) for k in ('L4','L3','L2','L1')}
  if duplicate:errors.append(name+':DUPLICATE_ROW_ID')
  components=[(r.get('customer_id'),r.get('visit_date'),r.get('parent_order_id'),r.get('component_index')) for r in rows if r.get('parent_order_id') and r.get('component_index') is not None]
  if len(components)!=len(set(components)):errors.append(name+':DUPLICATE_ORDER_COMPONENT')
  if len(config[name]['request']['scenario']['assumptions']['booked_sessions'])!=6:errors.append(name+':BOOKED_FAMILY_COUNT')
  if len(customers)!=28:errors.append(name+':CUSTOMER_COUNT')
  if any(v!=total for v in level_sums.values()) or recon[name]['paid_L5_krw']!=total:errors.append(name+':LEDGER_SUM_MISMATCH')
  if config[name]['request']['scenario']['assumptions']['booked_sessions'] and any(v['start']!='14:10' for v in config[name]['request']['scenario']['assumptions']['booked_sessions'].values()):errors.append(name+':BOOKING_TIME_MISMATCH')
  checks[name]={'run_id':config[name]['run_id'],'customers':len(customers),'rows':len(rows),'paid_krw':total,'levels':level_sums,'export_validation_status':recon[name]['overall']}
 for name in ('S1','S2'):
  cmp=recon['comparisons'][name]
  if checks[name]['paid_krw']-checks['A']['paid_krw']!=cmp['hotel_paid_delta_krw']:errors.append(name+':DELTA_MISMATCH')
  if sum(x['delta_krw'] for x in cmp['amount_changes'])!=cmp['hotel_paid_delta_krw']:errors.append(name+':CUSTOMER_DELTA_MISMATCH')
  if cmp['same_conditions_except_target_discount']['status']!='PASS':errors.append(name+':CONDITION_MISMATCH')
 if any(r['export_validation_status']=='FAIL' for r in checks.values()):errors.append('EXPORT_VALIDATION_FAIL')
 return {'integrity_and_arithmetic':'PASS' if not errors else 'FAIL','overall':'FAIL' if errors else 'VALID_WITH_HOLD' if any(r['export_validation_status']=='HOLD' for r in checks.values()) else 'PASS','errors':errors,'runs':checks,'files_checked':len(manifest['files']),'limitations':'Source meaning, unknown prices, and actual hotel POS are not verified by checksum or sums.'}
if __name__=='__main__':
 folder=(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent).resolve()
 result=verify(folder);print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(bool(result['errors']))
