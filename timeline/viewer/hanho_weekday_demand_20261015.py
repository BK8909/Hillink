"""평일 비투숙 배율의 운영일 민감도. 파일 입력·기본 v4.1·화면 캐시는 바꾸지 않는다.

앞 3일 이어 생성, 목표일 식사/결제만 집계. 객실은 객실박으로 배분하고 호텔 매출에서
빛의 시어터를 뺀다. 배율은 실제 방문 추정치가 아닌 실험 가정이다.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess

import stay_day as S


def run(target: str, seed: int, multiplier: float, output: Path):
    repo = Path(__file__).resolve().parents[2]
    output = output.resolve()
    if output.is_relative_to(repo):
        raise ValueError('계산 결과는 저장소 밖 로컬 폴더를 지정하세요.')
    output.mkdir(parents=True, exist_ok=True)
    day_target = datetime.fromisoformat(target).date()
    base_theta = dict(S.E.V4)
    versions = {'model': S.E._version.model_ver(), 'input': S.E._version.input_ver()}
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    custom = {'wd_day': multiplier, 'warmup': 3, 'scenario': 'none', 'scale': 1, 'base_theta': base_theta, 'collector_sha256': script_sha}
    experiment_hash = hashlib.sha256(json.dumps(custom, sort_keys=True).encode()).hexdigest()[:12]
    S.E.CACHE = output / 'unused_engine_cache'
    S.E.V4 = dict(base_theta, wd_day=multiplier)
    generated = {}
    order = defaultdict(list)
    persons = {}
    gross_l3 = Counter()
    gross_l2_group = defaultdict(Counter)
    units = defaultdict(Counter)
    preference = Counter()
    caps = []
    original_guests = S.G.guests_for
    original_spend = S.revenue.spend_lines
    original_capacity = S.Capacity
    menu_rows = S.revenue.menu_mod.default().rows
    unit_of = {(r['업장'], r['상품']): r['단위'] for r in menu_rows}

    class StudyCapacity(original_capacity):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            caps.append(self)

    def guests_for(day, *args, **kwargs):
        stays = original_guests(day, *args, **kwargs)
        records = {}
        for gid, _, m in stays:
            p = m.PERSONA
            persons[p.name] = p.party_size
            records[gid] = [p.is_guest, p.property, p.nights, p.party_size, p.has_child_under_13,
                            p.purpose, p.age_band, p.package, p.prefers, m.START_AT.isoformat()]
            if day == target and not p.is_guest:
                for pref in p.prefers:
                    preference[str(pref)] += 1
        g = [m.PERSONA for _, _, m in stays if m.PERSONA.is_guest]
        non = [m.PERSONA for _, _, m in stays if not m.PERSONA.is_guest]
        generated[day] = {'guest_teams': len(g), 'guest_people': sum(p.party_size for p in g),
                          'external_teams': len(non), 'external_people': sum(p.party_size for p in non),
                          'base_external_before_date_adjustment': kwargs['day_config']['scenarios']['base'],
                          'synthetic_persona_signatures': {gid: hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode()).hexdigest() for gid, v in records.items()}}
        return stays

    def spend_lines(m, *args, **kwargs):
        p = m.PERSONA
        origin = m.START_AT.date().isoformat()
        order[origin].append(p.name)
        lines = original_spend(m, *args, **kwargs)
        group = '비투숙' if not p.is_guest else '그날 체크인' if origin == target else ('전날 체크인' if origin == (day_target-timedelta(days=1)).isoformat() else '그 전날 체크인')
        for ln in lines:
            date = ln['at'].date()
            quantity = ln.get('qty', 1) or 1
            room = ln['l2'] == 'ROOM' and ln['l3'] in S.ROOM_L3
            amount = 0.0
            if room and quantity > 1:
                if date <= day_target < date + timedelta(days=quantity):
                    amount = ln['krw'] / quantity
            elif date == day_target:
                amount = ln['krw']
            gross_l3[ln['l3']] += amount
            gross_l2_group[group][ln['l2']] += amount
            if date == day_target and ln['l3'] in S.L3LOC:
                unit = unit_of.get((ln['l3'], str(ln['product'])), '단위 미확정')
                units[S.L3LOC[ln['l3']]][unit] += quantity
        return lines

    S.Capacity = StudyCapacity
    S.G.guests_for = guests_for
    S.revenue.spend_lines = spend_lines
    result = S.run(target, seed, 3)
    cap = caps[0]
    # 집계 정의가 다른 경로를 별도 대조: 원지출 줄 합과 stay_day의 단계 합.
    for group in set(result['rev_day']) | set(gross_l2_group):
        for l2 in set(result['rev_day'].get(group, {})) | set(gross_l2_group[group]):
            assert round(gross_l2_group[group][l2]) == result['rev_day'].get(group, {}).get(l2, 0), (group, l2)
    events = defaultdict(list)
    for who, key, at in cap.events:
        if at.date() == day_target:
            events[cap.venue_of(key)].append(who)
    for s in result['seat_summary']:
        assert len(events[s['venue']]) == s['turned']
        affected = set(events[s['venue']])
        s.update(constraint_unique_teams=len(affected), constraint_unique_people=sum(persons[n] for n in affected))
    for loc, by_unit in units.items():
        assert sum(by_unit.values()) == sum(result['meals'].get(loc, {}).values())
    assert result['checks']['duplicate_ids'] == 0
    assert not cap.over_cap()
    theatre = gross_l3.get('빛의 시어터', 0)
    l2_gross = Counter()
    for vals in gross_l2_group.values():
        l2_gross.update(vals)
    payload = dict(result, frame='운영일: 앞 3일 준비·이월·좌석 공유', multiplier=multiplier,
                   basis_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
                   base_versions=versions, experiment_input_id='weekday-'+experiment_hash,
                   experiment_assumptions=custom, gross_by_l3=dict(gross_l3), gross_by_l2=dict(l2_gross),
                   hotel_net=(sum(gross_l3.values())-theatre)/1.1,
                   all_model_net=sum(gross_l3.values())/1.1, theatre_gross_excluded=theatre,
                   hotel_net_by_l3={k: v/1.1 for k, v in gross_l3.items() if k != '빛의 시어터'},
                   payment_quantity_by_unit={k: dict(v) for k, v in units.items()},
                   new_external_preferred_actions=dict(preference), generated=generated,
                   execution_order=dict(order), collection_checks={'raw_lines_equal_step_revenue': True,
                   'payment_units_equal_payment_quantity': True, 'exact_all_booking_starts_seat_cap': True},
                   limits=['가정 민감도이며 실제 방문 증가·전환·수익성 예측 아님',
                           '기존 v4.1 식음 행동 체류당 한 번·처리 순서 정책을 유지',
                           '규모가 바뀌면 셔플된 공통 손님의 상대 처리 순서도 바뀔 수 있음',
                           '좌석제약 판정 건수는 실제 취소·고유 이탈 손님 수가 아님'])
    path = output / f'weekday_{target}_m{multiplier:.1f}_s{seed}.json'
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'date': target, 'multiplier': multiplier, 'seed': seed,
                      'hotel_net': round(payload['hotel_net']), 'external_teams': generated[target]['external_teams'],
                      'model': versions['model'], 'input': versions['input']}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('date'); ap.add_argument('seed', type=int)
    ap.add_argument('--multiplier', type=float, required=True, choices=[0.3, 0.5, 0.7, 1.0])
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    run(args.date, args.seed, args.multiplier, args.output)
