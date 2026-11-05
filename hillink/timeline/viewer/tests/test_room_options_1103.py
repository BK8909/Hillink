import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from room_options import room_options
from package_entitlements import PACKAGE_CATALOG
from santa_packages import PACKAGES

def test_options_are_catalog_projection_not_separate_products():
    options=[p for p in room_options()['packages'] if p['adapter']!='catalog_room']
    assert {p['id'] for p in options}==set(PACKAGE_CATALOG)|set(PACKAGES)
    for p in options:
        source=PACKAGE_CATALOG.get(p['id']) or PACKAGES[p['id']]
        assert p['effective_from']==source.get('effective_from',source.get('stay_from'))
        assert p['effective_to']==source.get('effective_to',source.get('stay_to'))
        assert p['minimum_nights']==source['nights']
        assert p['runnable']==source.get('runnable',True)

def test_unimplemented_future_packages_are_not_executable_options():
    rows={p['id']:p for p in room_options()['packages']}
    assert rows['SANTA_PKG_2025']['runnable']
    assert rows['SANTA_PKG_2025']['event_card_id']=='SANTA_KIDS_VILLAGE_2025'
    for p in PACKAGES.values():
        if not p['runnable']:assert not rows[p['package_id']]['runnable']

def test_runtime_room_catalog_projection_and_alias_are_complete():
    from hotel_ledger import H
    result=room_options();options={p['id']:p for p in result['packages']}
    rooms=[p for p in H.DATA['products'] if p['role']=='ROOM']
    aliases={a['sku_id']:a['option_id'] for a in result['catalog_aliases']}
    assert len(rooms)==result['catalog_room_count']==77
    assert aliases['HC-MENU-007']=='GRAND_SUNGSU_V2_2N'
    assert 'HC-MENU-007' not in options
    for p in rooms:
        if p['sku_id'] in aliases:continue
        o=options[p['sku_id']]
        assert o['adapter']=='catalog_room'
        assert o['room_price_krw']==p['unit_price_krw']
        assert o['effective_from']==p.get('valid_from')
        assert o['effective_to']==p.get('valid_until')
        assert o['source_day_rule']==p['source_day_rule']
        assert o['required_party_size']==p.get('package_people')
        assert o['runnable'] or o['not_runnable_reason']

def test_weekday_and_source_period_follow_existing_engine():
    rows={p['id']:p for p in room_options()['packages']}
    solo=rows['HC-MENU-018']
    assert solo['required_party_size']==1
    assert solo['party_qualification']['douglas_age_rule']
    assert '2026-10-26' in solo['allowed_dates']  # Monday
    assert '2026-10-24' not in solo['allowed_dates']  # Saturday
    assert '2025-10-24' not in solo['allowed_dates']
    assert not solo['runnable']  # package benefits are not claimed complete

def test_room_only_and_two_adult_breakfast_have_explicit_execution_scope():
    rows={p['id']:p for p in room_options()['packages']}
    assert rows['HC-MENU-038']['runnable']
    assert rows['HC-MENU-038']['actual_date_quote'] is False
    assert rows['HC-MENU-038']['validity_status']=='SOURCE_DATE_RANGE_UNSPECIFIED_REFERENCE_ONLY'
    assert rows['HC-MENU-003']['runnable']
    assert rows['HC-MENU-003']['required_party_size'] is None
    assert rows['HC-MENU-003']['reference_people']==2
    assert rows['HC-MENU-003']['breakfast_contract']=='SOURCE_ADULT_TWO_BUFFET'
    assert 'GIFT_DESCRIPTION_NOT_EXECUTED' in rows['HC-MENU-003']['benefit_scope']
    assert not rows['HC-MENU-004']['runnable']  # conditional club breakfast
    assert not rows['HC-MENU-035']['runnable']  # composite signature rights

def test_explicit_catalog_room_contract_overrides_generic_v2_but_not_v1():
    from types import SimpleNamespace
    from hotel_ledger import H
    from operator_choice.autonomy_v1 import breakfast_policy as BP
    import room_revenue as RR
    a=SimpleNamespace(pid='P',B='GRAND',N=2,stay=True,checked_in=True,checked_out=False,
        vs={'building':'GRAND','breakfast_plan':'breakfast_included'},
        sc={'catalog_policy':H.POLICY,'breakfast_policy':BP.V2,'catalog_options':{'room_products':{'P':'HC-MENU-038'}}})
    assert BP.covered_adults(a)==0  # no free buffet from default after buying room-only
    a.sc['catalog_options']['room_products']['P']='HC-MENU-003'
    a.vs['breakfast_plan']='room_only'
    assert BP.covered_adults(a)==2  # selected included source beats generic room-only switch
    a.sc['breakfast_policy']=BP.V1
    assert BP.covered_adults(a)==0  # historical policy keeps its plan semantics
    a.vs['breakfast_plan']='breakfast_included'
    assert BP.covered_adults(a)==2
    f={'visit_id':'explicit-room-contract','visit':{'start_date':'2026-10-24','catalog_policy':H.POLICY,'breakfast_policy':BP.V2,
        'catalog_options':{'room_products':{'P':'HC-MENU-003'}}},'visits':{'P':{'building':'GRAND','party_size':2,'party_composition':{'adult_count':2,'children':[]}}}}
    assert RR.native_price(f,'P','2026-10-24',0,1)['virtual_gross_krw']==313000
    f['visit']['catalog_options']['room_products']['P']='HC-MENU-038'
    assert RR.native_price(f,'P','2026-10-24',0,1)['virtual_gross_krw']==798600


def test_resolved_contract_metadata_matches_engine_and_preserves_v1():
    import visit_run as VR
    from hotel_ledger import H
    from operator_choice.autonomy_v1 import breakfast_policy as BP
    for sku,plan,source in [('HC-MENU-038','room_only','SELECTED_ROOM_NO_AUTOMATIC_BUFFET_CONTRACT'),
                            ('HC-MENU-003','breakfast_included','SELECTED_ROOM_SOURCE_ADULT_TWO_BUFFET'),
                            ('HC-MENU-018','breakfast_included','SELECTED_ROOM_DOUGLAS_FACILITY_LIGHT_BREAKFAST_RIGHT')]:
        rows={'P':{'breakfast_plan':'breakfast_included','breakfast_plan_source':'old'}}
        VR._resolve_catalog_room_contracts(rows,{'room_products':{'P':sku}},H,BP.V2)
        assert rows['P']['breakfast_plan']==plan
        assert rows['P']['breakfast_plan_source']==source
        assert rows['P']['selected_room_sku_id']==sku
    rows={'P':{'breakfast_plan':'breakfast_included','breakfast_plan_source':'old'}}
    VR._resolve_catalog_room_contracts(rows,{'room_products':{'P':'HC-MENU-038'}},H,BP.V1)
    assert rows=={'P':{'breakfast_plan':'breakfast_included','breakfast_plan_source':'old'}}
