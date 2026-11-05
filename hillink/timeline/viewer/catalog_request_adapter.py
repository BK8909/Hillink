"""Bridge validated per-visit menu-row orders to the received catalog contract."""
import copy
from types import SimpleNamespace

VERSION='visit-menu-row-to-catalog-order-v1'

def connect(options,resolutions,catalog,dates):
    result=copy.deepcopy(options)
    for pid,visit in resolutions.items():
        room=catalog.BY.get(result.get('room_products',{}).get(pid,''))
        if room:
            a=SimpleNamespace(pid=pid,sc={'date':min(dates),'catalog_options':result},N=visit['party_size'],B=visit['building'],stay=visit['stay'],checked_in=True,checked_out=False,C={'kids':visit.get('kids',False)},vs=visit)
            # Checkout is not another room night; validate every charged night.
            nights=sorted(dates)[:visit.get('nights',1)]
            for service_date in nights or [min(dates)]:
                a.sc['date']=service_date
                reasons=catalog.eligible(room,a,0,0,'booking')
                if reasons:raise ValueError('HC_ROOM_NOT_ELIGIBLE:'+service_date+':'+','.join(reasons))
        for order in visit.get('orders') or []:
            if order['date'] not in dates:
                raise ValueError('C01_ORDER_DATE_NOT_IN_VISIT')
            mapped=dict(date=order['date'],venue_id=order['venue_id'],service_period=order['service_period'],items=[])
            for item in order['items']:
                matches=[p for p in catalog.DATA['products'] if p.get('sku_id')==f"HC-MENU-{item['source_line']:03}" and p.get('source_line')==item['source_line'] and p['venue_id']==order['venue_id']]
                if len(matches)!=1:
                    raise ValueError('C01_ORDER_CATALOG_MAPPING_UNCONFIRMED')
                mapped['items'].append(dict(sku_id=matches[0]['sku_id'],quantity=item['quantity']))
            orders=result.setdefault('purchase_orders',{}).setdefault(pid,[])
            same=[x for x in orders if all(x[k]==mapped[k] for k in ('date','venue_id','service_period'))]
            if same and same!=[mapped]:
                raise ValueError('C01_ORDER_INPUT_CONFLICT')
            if not same:orders.append(mapped)
    return catalog.validate(result,list(resolutions))
