"""Explain the standing ledger failure (test_ledger_l5::test_all_sums) without changing its expected values.

The check "저장본 하루 = 같은 조건 실시간 하루" compares the stored 11-customer demo days (flow_fixture_v1) with the
current engine on the same conditions. For every case with a gap this lists, per paid scene, whether the difference
is BEHAVIOUR (different paid scenes) or PRICE (same scene, different amount). Informational: exit 0 unless it crashes.

  python tools/ci/explain_ledger_gaps.py [out.json]     (product directory)
"""
import json, os, sys, collections
from pathlib import Path
VIEWER = Path(__file__).resolve().parents[2] / 'timeline/viewer'
os.chdir(VIEWER); sys.path.insert(0, str(VIEWER))
import ledger_l5 as L
def basis_kind(text):
    if '호텔 상품 시뮬레이션 주문' in text or '정량 엔진 상품 가격' in text and '세트' in text: return 'REGISTERED_SKU_ORDER'
    if '원 × ' in text and '인' in text: return 'PER_PERSON_LEGACY_PRICE'
    return 'OTHER'


def contract_change(ba, bb):
    ka = {basis_kind(t) for t in ba}; kb = {basis_kind(t) for t in bb}
    if ka == {'PER_PERSON_LEGACY_PRICE'} and kb == {'REGISTERED_SKU_ORDER'}: return 'PER_PERSON_PRICE_TO_REGISTERED_SKU_ORDER'
    if ka == kb: return 'SAME_CONTRACT_KIND_DIFFERENT_PRICE_OR_QUANTITY'
    return 'CONTRACT_KIND_CHANGED ' + '/'.join(sorted(ka)) + ' -> ' + '/'.join(sorted(kb))


meta = {"types": L.load_types(), "no": L.display_no()}
out = []
for pid, ev, e in L.fixture_entries():
    v = e["visits"][pid]
    if not v.get("stay"): continue
    ph = v.get("phase")
    vo = {pid: {"stay": True, "building": v["building"], "phase": ph, "party_size": v["party_size"], **({"club": True} if v.get("club") else {})}}
    live = L.run_flow(pid, ev, vo)
    def paid(plan):
        rows = []
        for sc in plan["scenes"]:
            ch = (sc.get("basis") or {}).get("charge") or {}
            if ch.get("status") == "유료": rows.append((sc.get("act"), sc.get("loc"), ch.get("krw") or 0, ch.get("basis") or ""))
        return rows
    a, b = paid(e["plans"][pid]), paid(live["plans"][pid])
    sa, sb = sum(x[2] for x in a), sum(x[2] for x in b)
    if sa == sb: continue
    acts_a = collections.Counter((x[0], x[1]) for x in a); acts_b = collections.Counter((x[0], x[1]) for x in b)
    same = acts_a & acts_b
    price = []
    for key in same:
        pa = sorted(x[2] for x in a if (x[0], x[1]) == key); pb = sorted(x[2] for x in b if (x[0], x[1]) == key)
        if pa != pb:
            ba = sorted({x[3] for x in a if (x[0], x[1]) == key}); bb = sorted({x[3] for x in b if (x[0], x[1]) == key})
            price.append((key, pa, pb, contract_change(ba, bb), ba[:1], bb[:1]))
    only_a = list((acts_a - acts_b).elements()); only_b = list((acts_b - acts_a).elements())
    cause = []
    if only_a or only_b: cause.append('BEHAVIOUR (different paid scenes)')
    if price: cause.append('PRICE (same scene, different amount)')
    out.append(dict(case=f"{meta['no'].get(pid)} 행사{ev} {ph}", stored=sa, live=sb, cause=cause,
                    stored_only=[f"{x[0]}@{x[1]}" for x in only_a], live_only=[f"{x[0]}@{x[1]}" for x in only_b],
                    price=[dict(scene=f"{k[0]}@{k[1]}", stored=pa, live=pb, change=ch, stored_basis=ba, live_basis=bb) for k, pa, pb, ch, ba, bb in price]))
if len(sys.argv) > 1: json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
for o in out: print(o['case'], o['stored'], '->', o['live'], o['cause'], 'stored_only', o['stored_only'][:4], 'live_only', o['live_only'][:4], 'price', [(x['scene'], x['stored'], x['live'], x['change']) for x in o['price'][:2]])
print(len(out), 'cases with a gap'); print(collections.Counter(tuple(o['cause']) for o in out))
print('price differences by contract change:', dict(collections.Counter(x['change'] for o in out for x in o['price'])))
print('scenes only in the live engine:', dict(collections.Counter(x.split('@')[0] for o in out for x in o['live_only'])))
print('scenes only in the stored day:', dict(collections.Counter(x.split('@')[0] for o in out for x in o['stored_only'])))
