"""비투숙 규모와 처리 순서 분리 실험. 기본 파일·화면·캐시를 수정하지 않는다.

legacy: 현재 v4.1처럼 하루 명단 전체를 섞음.
fixed: 생성일 묶음은 유지하고 팀 ID별 SHA256 우선순위로 정렬. 공통 팀 상대 순서 고정.
stream: 현재 팀별 난수 줄. keyed: 행동 시점별·상품 선택별 난수 고정(실험 비교 장치).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import inspect
import json
from pathlib import Path
import random
import subprocess
import sys
import textwrap
import time
import zlib

HERE = Path(__file__).resolve().parent
TL = HERE.parents[1]
REPO = TL.parent
sys.path[:0] = [str(TL), str(TL/'viewer')]
import stay_day as S
from fast_capacity import FastCapacity

A, G, E, revenue = S.agent_v4, S.G, S.E, S.revenue
LOC_NAMES = {v:k for k,v in E.SEAT_LOC.items()}
CORE = ['THE_BUFFET','PIZZA_HILL','GEUMRYONG','MYONGWOLGWAN','ONDAL','MOEGI']


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(',', ':'))


def sha(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()


def group_of(p, start, target):
    if not p.is_guest:
        return '비투숙'
    days = (target-start.date()).days
    return {0:'그날 체크인',1:'전날 체크인',2:'그 전날 체크인'}.get(days, f'{days}일 전 체크인')


def canonical_versions():
    out = {}
    for label, names in [('model', E._version.MODEL_FILES), ('input', E._version.INPUT_FILES)]:
        h = hashlib.sha1()
        for n in names:
            rel = (TL/n).resolve().relative_to(REPO).as_posix()
            raw = (TL/n).read_bytes()
            git = subprocess.check_output(['git','show',f'HEAD:{rel}'], cwd=REPO)
            assert raw.replace(b'\r\n',b'\n') == git.replace(b'\r\n',b'\n'), rel
            h.update(n.encode()); h.update(git)
        out[label] = {'git':h.hexdigest()[:8], 'local':E._version._hash(names)}
    return out


def run(args):
    started = time.monotonic()
    target_date = datetime.fromisoformat(args.date).date()
    output = args.output.resolve()
    if output.is_relative_to(REPO):
        raise ValueError('원본 실행 결과는 저장소 밖 로컬 폴더를 지정하세요.')
    output.mkdir(parents=True, exist_ok=True)
    versions = canonical_versions()
    original_theta = dict(E.V4)
    E.V4 = dict(original_theta, wd_day=args.multiplier)
    E.CACHE = output/'unused_engine_cache'
    generated, order_log, persons, people = {}, {}, {}, {}
    draws, draws_by_person = {}, defaultdict(dict)
    per_person = {}
    eligible_blocks = []
    caps = []
    all_lines_digest = {}
    menu_units = {(x['업장'],x['상품']):x['단위'] for x in revenue.menu_mod.default().rows}
    payment_units = defaultdict(Counter)
    active_spend = []
    original_guests, original_spend, original_detail = G.guests_for, revenue.spend_lines, E.detail_json
    base_capacity = FastCapacity if args.capacity=='fast' else S.Capacity

    class StudyCapacity(base_capacity):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw); caps.append(self)

    def guests_for(day,*a,**kw):
        stays = original_guests(day,*a,**kw)
        signatures = {}
        for gid,_,m in stays:
            p=m.PERSONA
            # 합성 손님의 속성을 대조하며 개별 기록은 로컬에만 보관한다.
            signatures[p.name] = sha(vars(p))
            people[p.name] = p.party_size
            persons[p.name] = {'gid':gid,'origin':day,'guest':p.is_guest,'party':p.party_size,
                               'nights':p.nights if p.is_guest else 0,'age':p.age_band,'purpose':p.purpose,
                               'group':group_of(p,m.START_AT,target_date),'signature':signatures[p.name]}
        generated[day]={'guest_teams':sum(m.PERSONA.is_guest for _,_,m in stays),
                        'external_teams':sum(not m.PERSONA.is_guest for _,_,m in stays),
                        'signatures':signatures}
        print(f"COHORT {day} {len(stays)} teams",file=sys.__stdout__,flush=True)
        return stays

    def exp_order(stays,day,seed):
        if args.order=='legacy':
            random.Random(G.SEED+7).shuffle(stays)
        else:
            stays.sort(key=lambda x:hashlib.sha256(f'fixed-priority-v1|{G.SEED}|{x[2].PERSONA.name}'.encode()).digest())
        order_log[day]=[m.PERSONA.name for _,_,m in stays]

    def record_draw(name,event,seed):
        token=f'{name}|{event}'
        sample=random.Random(seed).random().hex()
        assert token not in draws or draws[token]==sample
        draws[token]=sample;draws_by_person[name][event]=sample
        return random.Random(seed)

    class KeyedRng:
        def __init__(self,name):
            self.name=name;self.n=Counter()

        def at(self,now):
            stamp=now.isoformat();self.n[stamp]+=1
            event=f'action|{stamp}|{self.n[stamp]}'
            seed=zlib.crc32(f'{self.name}|{stamp}|{self.n[stamp]}'.encode())+revenue.SEED
            return record_draw(self.name,event,seed)

    def block(p,key,at):
        if at.date()==target_date:
            eligible_blocks.append((p.name,key,at.isoformat()))

    # 순서 호출 및 난수 선택 자리만 런타임에 바꾼다. E1 등 식사 규칙은 바꾸지 않는다.
    stock_run_src = textwrap.dedent(inspect.getsource(S.run))
    src=stock_run_src.replace('def run(', 'def run_order_study(', 1)
    old='random.Random(G.SEED + 7).shuffle(stays)'
    assert src.count(old)==1
    src=src.replace(old,'_experiment_order(stays, day, seed)')
    S._experiment_order=exp_order
    exec(compile(src,'<한호 실험 · 순서만 별도>','exec'),S.__dict__)

    agent_src=textwrap.dedent(inspect.getsource(A.run_agent))
    old='best = rng.choices(candidates, weights=ws, k=1)[0]'
    assert agent_src.count(old)==1
    agent_src=agent_src.replace('def run_agent(','def run_agent_order_study(',1).replace(old,'best = (rng.at(now) if hasattr(rng, "at") else rng).choices(candidates, weights=ws, k=1)[0]')
    old='blocked.append((_pts, a, full_reason, start))'
    assert agent_src.count(old)==1
    agent_src=agent_src.replace(old,'_experiment_blocked(persona, a.key, start); '+old)
    A._experiment_blocked=block
    exec(compile(agent_src,'<한호 실험 · 선택별 난수와 계측>','exec'),A.__dict__)
    def agent(p,start,*a,**kw):
        if args.rng=='keyed' and active_spend:
            kw['rng']=KeyedRng(p.name)
        return A.run_agent_order_study(p,start,*a,**kw)
    A.run_agent=agent

    original_pick = revenue.menu_mod.Menu.pick
    menu_draw_count=Counter()
    def pick(menu,key,p,at,rng):
        if args.rng=='keyed' and active_spend:
            assert p.name==active_spend[-1]
            token=(p.name,key,at.isoformat());menu_draw_count[token]+=1
            event=f'menu|{key}|{at.isoformat()}|{menu_draw_count[token]}'
            seed=int.from_bytes(hashlib.sha256(f'menu-fixed-v1|{revenue.SEED}|{p.name}|{event}'.encode()).digest()[:8],'big')
            rng=record_draw(p.name,event,seed)
        return original_pick(menu,key,p,at,rng)
    revenue.menu_mod.Menu.pick=pick

    def spend(m,*a,**kw):
        p=m.PERSONA
        active_spend.append(p.name)
        try:
            lines=original_spend(m,*a,**kw)
        finally:
            assert active_spend.pop()==p.name
        gross=Counter()
        for line in lines:
            qty=line.get('qty',1) or 1
            date=line['at'].date()
            room=line['l2']=='ROOM' and line['l3'] in S.ROOM_L3
            amount=0.0
            if room and qty>1:
                if date<=target_date<date+timedelta(days=qty):amount=line['krw']/qty
            elif date==target_date:amount=line['krw']
            gross[line['l3']]+=amount
            if date==target_date and line['l3'] in S.L3LOC:
                payment_units[S.L3LOC[line['l3']]][menu_units.get((line['l3'],str(line['product'])),'단위 미확정')]+=qty
        per_person[p.name]={'net_by_l3':{k:v/1.1 for k,v in gross.items() if k!='빛의 시어터'},
                            'hotel_net':(sum(gross.values())-gross.get('빛의 시어터',0))/1.1,
                            'theatre_gross':gross.get('빛의 시어터',0),'meals':{},'breakfast':{},
                            'switch_venues':[],'route_digest':None}
        all_lines_digest[p.name]=sha(lines)
        return lines

    def detail(p,start,segs,traces,lines):
        d=original_detail(p,start,segs,traces,lines)
        out=per_person[p.name]
        meals=Counter();bf=Counter();switch=set()
        for st in d['steps']:
            if st['t_in'][:10]!=args.date:continue
            if st['kind']=='meal' and st.get('venue') and st.get('state')!='TAKEOUT_ORDER' and st['venue'] not in S.L3LOC.values():
                meals[st['venue']]+=p.party_size
                if st['venue']=='THE_BUFFET' and '조식' in st['label']:
                    bf[S.window_of('THE_BUFFET',datetime.fromisoformat(st['t_in']))]+=p.party_size
            sw=st.get('switch') or {}
            if sw.get('원래_키'):
                switch.add(sw['원래_키'])
        out.update(meals=dict(meals),breakfast=dict(bf),switch_venues=sorted(switch),route_digest=sha(d['steps']))
        return d

    G.guests_for=guests_for;revenue.spend_lines=spend;E.detail_json=detail;S.Capacity=StudyCapacity
    result=S.run_order_study(args.date,args.seed,3)
    cap=caps[0]
    raw=defaultdict(list);valid=defaultdict(list)
    for name,key,at in cap.events:
        if at.date()==target_date:raw[cap.venue_of(key)].append(name)
    for name,key,at in eligible_blocks:
        valid[cap.venue_of(key)].append(name)
    group_stats=defaultdict(lambda:defaultdict(Counter))
    for name,p in persons.items():
        z=per_person[name];g=p['group']
        for loc,count in z['meals'].items():
            venue=LOC_NAMES.get(loc,loc);group_stats[venue][g]['seated_person_visits']+=count
        for venue,net in z['net_by_l3'].items():group_stats[venue][g]['net_krw']+=net
    for s in result['seat_summary']:
        venue=s['venue'];assert s['turned']==len(raw[venue])
        s.update(raw_unique_teams=len(set(raw[venue])),eligible_candidate_checks=len(valid[venue]),
                 eligible_unique_teams=len(set(valid[venue])))
        for name in set(raw[venue]):group_stats[venue][persons[name]['group']]['raw_constraint_unique_teams']+=1
        for name in set(valid[venue]):group_stats[venue][persons[name]['group']]['eligible_constraint_unique_teams']+=1
        for name in raw[venue]:group_stats[venue][persons[name]['group']]['raw_constraint_checks']+=1
        for name in valid[venue]:group_stats[venue][persons[name]['group']]['eligible_constraint_checks']+=1
    for loc,u in payment_units.items():assert sum(u.values())==sum(result['meals'].get(loc,{}).values())
    assert result['checks']['duplicate_ids']==0 and result['checks']['warm_covers_max_nights']
    assert not cap.over_cap()
    hotel_net=sum(p['hotel_net'] for p in per_person.values())
    raw_l3=Counter()
    for p in per_person.values():raw_l3.update(p['net_by_l3'])
    for loc in CORE:
        assert sum(z['meals'].get(loc,0) for z in per_person.values())==sum(result['meals'].get(loc,{}).values())
    # 개인별 지출과 기존 운영일 집계를 별도 경로로 대조한다.
    model_gross=sum(v for by_l2 in result['rev_day'].values() for v in by_l2.values())
    independent_gross=hotel_net*1.1+sum(z['theatre_gross'] for z in per_person.values())
    assert abs(model_gross-independent_gross)<=len(result['rev_day'])*3, (model_gross,independent_gross)
    booked={v:[(a.isoformat(),b.isoformat(),n) for a,b,n in bookings] for v,bookings in cap.booked.items()}
    script_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'fast_capacity.py']}
    params={'multiplier':args.multiplier,'order':args.order,'rng':args.rng,'warmup':3,
            'same_generation_cohort_priority_across_days':True,'fixed_priority':'SHA256(fixed-priority-v1|generation_seed|team_name)',
            'action_rng_key':'team_name|decision_datetime|within_time_ordinal',
            'menu_rng_key':'team_name|action_key|purchase_datetime|within_key_time_ordinal',
            'menu_rng_stage':'revenue only; generate.room_booking keeps its original RNG',
            'basic_v4_1_meal_rules_unchanged':True,'capacity_query':args.capacity,'script_sha256':script_hashes}
    result.update(frame='자정 달력일 운영: 앞 3일 준비·이월·좌석 공유', multiplier=args.multiplier,
                  order=args.order,rng=args.rng,capacity_query=args.capacity,basis_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
                  versions=versions,experiment_params=params,experiment_id='weekday-order-'+sha(params)[:12],
                  generated=generated,execution_order=order_log,persons=persons,per_person=per_person,
                  choice_draws=draws,choice_draws_by_person=dict(draws_by_person),
                  hotel_net=hotel_net,hotel_net_by_l3=dict(raw_l3),payment_quantity_by_unit={k:dict(v) for k,v in payment_units.items()},
                  venue_group_metrics={v:{g:dict(z) for g,z in gs.items()} for v,gs in group_stats.items()},
                  bookings_digest=sha(booked),route_digests={k:v['route_digest'] for k,v in per_person.items()},
                  spend_lines_digests=all_lines_digest,seconds=round(time.monotonic()-started,2),
                  checks_extended={'per_person_meals_match_aggregate':True,'payment_quantity_match':True,
                                   'per_person_revenue_match_aggregate_rounding':True,'seat_cap_all_retained_booking_starts':True},
                  limitations=['실제 방문·전환·운영 정확도 검증 아님','같은 시각·같은 선택번호의 공통 기회 난수만 동일; 경로가 달라지면 기회 자체가 달라짐',
                               '예전 고객의 전체 체류 선점과 생성일 묶음 우선은 유지','대체선택 검토에 남은 만석 후보도 실제 이탈 인원 아님',
                               '호텔 영업일 마감 미확정; 모델 자정 기준','개별 고객·선택 기록은 합성 자료이며 로컬에만 보관'])
    filename=f'{args.date}_m{args.multiplier:.1f}_{args.order}_{args.rng}_{args.capacity}_s{args.seed}.json'
    (output/filename).write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print(dump({'done':filename,'hotel_net':round(hotel_net),'seconds':result['seconds'],'versions':versions}),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('date');ap.add_argument('seed',type=int)
    ap.add_argument('--multiplier',type=float,choices=[.3,.5,.7,1.0],required=True)
    ap.add_argument('--order',choices=['legacy','fixed'],required=True)
    ap.add_argument('--rng',choices=['stream','keyed'],required=True)
    ap.add_argument('--capacity',choices=['stock','fast'],default='fast')
    ap.add_argument('--output',type=Path,required=True)
    run(ap.parse_args())
