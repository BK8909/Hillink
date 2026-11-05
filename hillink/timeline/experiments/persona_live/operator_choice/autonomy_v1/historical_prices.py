"""2025 historical reference prices (operator-approved 11/03). Separate overlay; never a confirmed date-specific sale.

The same product rows feed the catalog path (hotel_catalog DATA) and the native path (menu_connections.buffet), so the
candidate, the score input, the order contract and the L5 row carry one price. Only general breakfast/dinner exist:
no lunch, no seasonal 2026-only product is back-dated.
"""
import copy,hashlib,json
from pathlib import Path
PATH=Path(__file__).with_name('historical_buffet_2025.json')
DATA=json.loads(PATH.read_text(encoding='utf-8'));SHA=hashlib.sha256(PATH.read_bytes()).hexdigest()

def load(base,base_sha):
    by={p['sku_id']:copy.deepcopy(p) for p in base['products']}
    for p in DATA['products']:
        q=copy.deepcopy(p);q['source_sha256']=SHA;by[q['sku_id']]=q
    out=copy.deepcopy(base);out['products']=list(by.values());out['historical_overlay_version']=DATA['version']
    return out,hashlib.sha256((base_sha+SHA).encode()).hexdigest()

def menu_rows(venue_ko='더뷔페'):
    """Rows shaped like timeline/menu.csv rows for the native path (line numbers 9001+ mark the overlay)."""
    out=[]
    for i,p in enumerate(DATA['products'],9001):
        out.append((i,{'업장':venue_ko,'상품':p['label'],'단가':str(p['unit_price_krw']),'단위':p['source_unit'],'요일제한':p['source_day_rule'],
                       '시간제한':p['source_service_windows'],'판매시작':p['valid_from'],'판매종료':p['valid_until'],'근거':p['source_document'],'등급':p['source_grade'],
                       '_hist':p}))
    return out

def patch_contract(c,row):
    """Re-point a native contract built from an overlay row at the overlay source (not menu.csv)."""
    p=row.get('_hist')
    if not p:return c
    c.update(sku_id=p['sku_id'],source_path=p['source_path'],source_sha256=SHA,price_status=p['price_status'],
             price_class_ko=p['price_class_ko'],source_document=p['source_document'],source_grade=p['source_grade'],
             label='더뷔페 '+p['label']+' · 2025 과거 참고가 기준 가상 계산',service_window_basis=p['service_window_basis'])
    return c
