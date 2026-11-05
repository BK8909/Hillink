"""Lossless JSON DAG transport for oversized repeated visit traces.

Only responses which previously exceeded the plain JSON bound use this format.
Original decisions, receipts and server retention accounting remain unchanged.
"""
import hashlib,json

POLICY='HILLINK_JSON_DAG_V1'

def pack(value):
    nodes=[];seen={}
    def item(value):
        if not isinstance(value,(dict,list)):return value
        if isinstance(value,dict):
            payload=['d',[[k if isinstance(k,str) else next(iter(json.loads(json.dumps({k:None})))),item(v)] for k,v in value.items()]]
        else:payload=['a',[item(v) for v in value]]
        signature=json.dumps(payload,ensure_ascii=False,default=str,separators=(',',':'))
        key=hashlib.sha256(signature.encode()).hexdigest()
        if key not in seen:
            seen[key]=len(nodes);nodes.append(payload)
        elif nodes[seen[key]]!=payload:raise ValueError('WIRE_HASH_COLLISION')
        return {'r':seen[key]}
    root=item(value)
    return dict(hillink_transport=POLICY,nodes=nodes,root=root)

def unpack(value):
    if not isinstance(value,dict) or value.get('hillink_transport')!=POLICY:return value
    nodes=value.get('nodes');built=[]
    if not isinstance(nodes,list) or len(nodes)>2_000_000:raise ValueError('INVALID_WIRE_NODES')
    def item(value):
        if not isinstance(value,dict):
            if isinstance(value,list):raise ValueError('INVALID_WIRE_VALUE')
            return value
        index=value.get('r')
        if set(value)!={'r'} or type(index) is not int or not 0<=index<len(built):raise ValueError('INVALID_WIRE_REFERENCE')
        return built[index]
    for node in nodes:
        if not isinstance(node,list) or len(node)!=2 or node[0] not in ('d','a') or not isinstance(node[1],list):raise ValueError('INVALID_WIRE_NODE')
        if node[0]=='a':out=[item(v) for v in node[1]]
        else:
            out={}
            for pair in node[1]:
                if not isinstance(pair,list) or len(pair)!=2 or not isinstance(pair[0],str) or pair[0] in out:raise ValueError('INVALID_WIRE_KEY')
                out[pair[0]]=item(pair[1])
        built.append(out)
    return item(value['root'])

def serialize(value,limit):
    raw=json.dumps(value,ensure_ascii=False,default=str).encode()
    if len(raw)<=limit:return raw
    packed=json.dumps(pack(value),ensure_ascii=False,default=str,separators=(',',':')).encode()
    return packed if len(packed)<len(raw) else raw
