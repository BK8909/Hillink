import copy,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import wire_json as W

def test_lossless_repeated_decisions_receipts_and_types():
    contract={'sku':'SKU','quantity':2,'paid':170000,'boolean':True,'float':1.0,'quote':'한글 <script>','nested':[None,False,0]}
    data={'plans':{'A':{'decision':copy.deepcopy(contract)}},'days':[copy.deepcopy(contract) for _ in range(100)],'__proto__':{'safe':True}}
    before=copy.deepcopy(data);wire=W.serialize(data,100)
    assert len(wire)<len(json.dumps(data,ensure_ascii=False).encode())
    assert W.unpack(json.loads(wire))==data and data==before
    assert W.serialize({'ok':True},192*1024*1024)==b'{"ok": true}'

@pytest.mark.parametrize('nodes,root',[
    ([['a',[{'r':0}]]],{'r':0}),
    ([['d',[['x',1],['x',2]]]],{'r':0}),
    ([['d',[[1,'bad']]]],{'r':0}),
    ([['a',[]]],{'r':-1})])
def test_invalid_cycle_forward_reference_or_key_fails_closed(nodes,root):
    with pytest.raises(ValueError):W.unpack(dict(hillink_transport=W.POLICY,nodes=nodes,root=root))
