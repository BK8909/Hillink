"""Source-backed opt-in product gates; separate processes preserve default mode."""
import json,os,subprocess,sys,unittest
from pathlib import Path
VIEWER=Path(__file__).resolve().parents[1]
def probe(enabled):
 code='''import sys,json
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1]);import flow_run
from operator_choice.autonomy_v1 import candidate_services as C,menu_connections as M
sc=C.AD.scenario();a=SimpleNamespace(N=2,C={'kids':False},sc={'date':'2026-10-24'},t=1184)
with C.install(sc['date']):
 w=C.AD.World(sc).engine_world(1080)
 o=next(o for o in w['offers'] if o['id']=='C01_PIZZA_VONGOLE')
 pasta=M.attach(o,a,1184)
 added=[k for k in M.SPECS if k.startswith('C01_MYONG_GRILL_') or k=='C01_MYONG_BULGOGI_L']
 result={'added':added,'pasta_available':pasta.get('available'),'pasta_end':pasta['window']['end'],'deadline':pasta.get('order_deadline')}
 if added:
  o=next(o for o in w['offers'] if o['id']=='C01_MYONG_BULGOGI_L')
  line,row=M.find('명월관','숯불 불고기 (점심 한정)')
  lunch={'sku_contract':M.contract(line,row,'MYONGWOLGWAN','lunch',2)};dinner=M.attach(o,a,1080)
  assert M.source_sessions(row,'lunch')==[(720,900)]
  result.update(bulgogi_price=lunch['sku_contract']['unit_price_krw'],bulgogi_qty=lunch['sku_contract']['billing_quantity'],bulgogi_dinner=dinner['available'])
 P={'bars':{k:0.4 for k in ('food','space','value_check','benefit','rest_need','routine')},'facets':{k:0.2 for k in ('swim_aversion','active','warm_rest','food_specific','novelty','premium','practical_alt','alcohol_familiar','alcohol_limit')},'fact_hits':{}}
 from operator_choice.operator_world_v1_1 import stay_planner as SP
 ctx={'done':[],'fatigue':0};Cflags={'kids':False,'elder':False,'solo':False,'couple':False,'friends':False}
 first=SP.act_weight('room_rest',P,Cflags,ctx);ctx['done']=['room_rest'];repeat=SP.act_weight('room_rest',P,Cflags,ctx)
 result['rest_repeat_penalty']=round(first-repeat,6)
 print(json.dumps(result))
'''
 env={**os.environ,'HILLINK_V12Z_COMMON':str(enabled),'PYTHONDONTWRITEBYTECODE':'1','HILLINK_LLM_ENABLED':'0','HILLINK_LLM_EXTERNAL_OPT_IN':'0'}
 return json.loads(subprocess.check_output([sys.executable,'-c',code,str(VIEWER)],env=env,text=True))
class CommonCandidateTests(unittest.TestCase):
 def test_default_menu_registry_unchanged(self):
  self.assertEqual(probe(0)['added'],[])
 def test_source_backed_menu_and_portion_contract(self):
  p=probe(1);self.assertEqual(len(p['added']),6);self.assertEqual((p['bulgogi_price'],p['bulgogi_qty']),(53000,2));self.assertFalse(p['bulgogi_dinner'])
 def test_rest_continuation_does_not_receive_new_experience_penalty(self):
  self.assertEqual(probe(0)["rest_repeat_penalty"],1.2);self.assertEqual(probe(1)["rest_repeat_penalty"],0.0)
 def test_order_deadline_and_service_close_are_distinct(self):
  before=probe(0);after=probe(1)
  self.assertFalse(before['pasta_available']);self.assertTrue(after['pasta_available'])
  self.assertEqual(after['deadline'],'21:00');self.assertEqual(after['pasta_end'],'22:00')
if __name__=='__main__':unittest.main()
