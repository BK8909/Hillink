"""A04 regression: visit-level engine_scene_paid_krw must equal the sum of the daily values.

The multi-day roll-up used to deepcopy day 1 (amount included) and then add day 1 again,
so a 1-night A04 visit reported 274,000 while the non-room receipt rows summed to 182,000.
"""
import sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
import visit_run as VR
import ledger_service as LS

INPUTS=VR.AD.load_inputs()[0]

def _run(personas,duration):
    q=dict(personas=personas,duration=duration,event_mode='none',seed=0,start_date='2026-10-24')
    f=VR.run_visit(q)
    if f.get('error'): raise AssertionError(f)
    daily={}
    original=LS.register
    def spy(flow,request,source='live_engine'):
        out=original(flow,request,source=source)
        with LS._LOCK: cached=LS._CACHE.get(out['run_id'])
        for pid,meta in cached['info'].items(): daily[pid]=daily.get(pid,0)+int(meta.get('engine_scene_paid_krw') or 0)
        return out
    LS.register=spy
    try: ledger=LS.register_visit(f,q)
    finally: LS.register=original
    with LS._LOCK: info=LS._CACHE[ledger['run_id']]['info']
    return ledger,info,daily

class VisitEngineSceneTotalTests(unittest.TestCase):
    def check(self,personas,duration):
        LS._CACHE.clear()
        ledger,info,daily=_run(personas,duration)
        for pid in personas:
            self.assertEqual(info[pid]['engine_scene_paid_krw'],daily[pid],(pid,duration))
            nonroom=sum(int(r['paid_krw'] or 0) for r in ledger['receipts'][pid]['rows'] if r['action_id']!='room_night')
            # engine scene amounts never exceed what the receipt rows actually charged outside the room
            self.assertLessEqual(info[pid]['engine_scene_paid_krw'],nonroom,(pid,duration))
    @unittest.skipUnless('A04' in INPUTS,'A04 private inputs unavailable')
    def test_a04_day_visit(self): self.check(['A04'],'day_visit')
    @unittest.skipUnless('A04' in INPUTS,'A04 private inputs unavailable')
    def test_a04_one_night(self): self.check(['A04'],'stay_1')
    @unittest.skipUnless('A04' in INPUTS,'A04 private inputs unavailable')
    def test_a04_two_nights(self): self.check(['A04'],'stay_2')
    @unittest.skipUnless({'A04','A08'}<=set(INPUTS),'A04/A08 private inputs unavailable')
    def test_a04_a08_shared_one_night(self): self.check(['A04','A08'],'stay_1')

if __name__=='__main__': unittest.main()
