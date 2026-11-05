"""Portable environment seam from product1-operational-input-v1.
Source: product1_visit.validate/daily/run, product1 522c943 dirty handoff.
Prices remain exclusively C01. Explicit virtual conditions, not a forecast.
"""
import copy
from contextlib import contextmanager, ExitStack
from unittest.mock import patch
from datetime import date
from . import agent_day as AD
VERSION = 'product1-operational-input-v1+release-environment-v1'
OUTDOOR_WALKS = ('forest_walk', 'garden_walk', 'night_walk', 'tennez')

def validate(value):
    if value is None: return {}
    if not isinstance(value, dict) or set(value)-{'weather', 'arrival_time'}:
        raise ValueError('지원하지 않는 환경 입력입니다')
    e = copy.deepcopy(value)
    if e.get('weather', 'clear') not in ('clear', 'rain'):
        raise ValueError('날씨는 clear/rain만 지원합니다')
    if 'arrival_time' in e:
        t = e['arrival_time']
        if not isinstance(t, str) or len(t) != 5 or t[2] != ':' or not t[:2].isdigit() or not t[3:].isdigit() or int(t[3:]) >= 60 or not 480 <= AD.hm(t) <= 1200:
            raise ValueError('방문 시작은 08:00~20:00 HH:MM으로 선택해 주세요')
    return e

def validate_date(start, has_scenario=False):
    d = date.fromisoformat(start)
    if d.year not in (2025, 2026) or d.year == 2025 and not has_scenario:
        raise ValueError('2025년은 근거가 있는 행사 시나리오에서만, 일반 방문은 2026년만 지원합니다')
    return d

def snapshot(e, start):
    return dict(version=VERSION, weather=e.get('weather','clear'), arrival_time=e.get('arrival_time'), date=start,
                calendar='ACTUAL_DATE_WEEKDAY_AND_EXISTING_PUBLIC_HOLIDAY_TABLE',
                source='OPERATOR_VIRTUAL_CONDITION_NOT_FORECAST',
                rain_rule='Outdoor walks held; pool is not automatically closed')

@contextmanager
def install():
    # Installed after catalog/native boundary so an accepted choice cannot bypass
    # the same environment eligibility check used by the planner.
    init0=AD.Agent.__init__; plan0=AD.plan_ok; world0=AD.engine_world_for
    def init(a,*args,**kw):
        init0(a,*args,**kw)
        e=a.sc.get('operational_environment') or {}
        if e.get('arrival_time') and a.phase in ('visit','checkin'):
            a.t=AD.hm(e['arrival_time'])
    def plan(a,code,t,w,*args,**kw):
        if (a.sc.get('operational_environment') or {}).get('weather')=='rain' and code in OUTDOOR_WALKS:
            why=args[0] if args and isinstance(args[0],dict) else kw.get('why_out')
            if why is not None: why[code]='가상 운영 조건: 비 오는 날 실외 산책 미운영'
            return None
        return plan0(a,code,t,w,*args,**kw)
    def world(a,w,t):
        result=world0(a,w,t)
        if (a.sc.get('operational_environment') or {}).get('weather')=='rain':
            for o in result['offers']:
                if o['id']=='FOREST_WALK':
                    o.update(available=False,status='OPERATOR_RAIN_OUTDOOR_WALK_HOLD')
        return result
    with ExitStack() as stack:
        for obj,key,value in ((AD.Agent,'__init__',init),(AD,'plan_ok',plan),(AD,'engine_world_for',world)):
            stack.enter_context(patch.object(obj,key,value))
        yield
