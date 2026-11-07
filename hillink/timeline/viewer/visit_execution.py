"""Product execution modes. Provider cache keys still cover the complete input.

Never change process-wide environment while concurrent requests are running.
The engine and its original provider/decision contracts are left intact.
"""
import copy, hashlib, json, os
from pathlib import Path
import saved_visits

POLICY = 'LLM_AUTONOMOUS_CUSTOMER_V16'
LIVE_POLICY = 'LLM_AUTONOMOUS_CUSTOMER_V19LS'          # product LIVE default since 2026-11-07 (P5 + day-end LIVE re-check)
PREVIOUS_LIVE_POLICY = 'LLM_AUTONOMOUS_CUSTOMER_V17'   # kept: selectable only when a request names it (?policy=V17)
EXPERIMENT_POLICIES = ('LLM_AUTONOMOUS_CUSTOMER_V18', 'LLM_AUTONOMOUS_CUSTOMER_V18B', 'LLM_AUTONOMOUS_CUSTOMER_V18BM', 'LLM_AUTONOMOUS_CUSTOMER_V18BD')   # M4 shortlist experiments; never the default
SELECTABLE_LIVE_POLICIES = (PREVIOUS_LIVE_POLICY,) + EXPERIMENT_POLICIES
POLICIES = (POLICY, LIVE_POLICY, PREVIOUS_LIVE_POLICY) + EXPERIMENT_POLICIES   # stored V16 runs replay under V16; a request names the policy it wants and gets exactly that
POLICY_NOTES = {POLICY: '과거 판단 기준(V16) · 조기 종료 검증 이전의 저장 응답',
                LIVE_POLICY: '현재 실시간 AI 판단 기준(V19-LS) · 근거 성격 표시 · 하루 종료 재검토 · 선택 진단 기록',
                PREVIOUS_LIVE_POLICY: '이전 실시간 판단 기준(V17) · 명시적으로 선택한 경우에만',
                'LLM_AUTONOMOUS_CUSTOMER_V18': '실험 기준(V18) · 규칙 선별 후 LLM 선택 · 조기 종료 검증 적용',
                'LLM_AUTONOMOUS_CUSTOMER_V18B': '실험 기준(V18-B) · 규칙 선별 후 LLM 선택 · 후보 관련 근거만 전달',
                'LLM_AUTONOMOUS_CUSTOMER_V18BM': '실험 기준(V18-C) · V18-B와 같은 입력 · reasoning medium',
                'LLM_AUTONOMOUS_CUSTOMER_V18BD': '실험 기준(V18-D) · V18-B 입력 · 최소 출력'}
MODES = ('rules', 'replay', 'live')


def prepare_replay_cache(destination):
    """Publish SHA-verified original receipts, never saved visit outputs.

    Deterministic first original response wins when an identical full input was
    sampled more than once. No response is used for a different input hash.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    spec = saved_visits.manifest(); selected = {}; collisions = 0
    rows = sorted(spec['v16_runs']+spec.get('product_replay_runs',[]), key=lambda r: (not r['tag'].endswith('-baseline'), r['tag']))
    for row in rows:
        for entry in row.get('replay_entries', []):
            value = saved_visits._read(entry['path'], spec)
            key = entry['input_sha256']
            if value.get('input_sha256') != key or value.get('origin') != 'LIVE_RESPONSES':
                raise ValueError('INVALID_APPROVED_RECEIPT')
            if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
                raise ValueError('INVALID_RECEIPT_KEY')
            if key in selected:
                collisions += selected[key]['answer'] != value['answer']
                continue
            selected[key] = value
            path = destination / (key + '.json')
            path.write_text(json.dumps(value, ensure_ascii=False))
            path.chmod(0o600)
    (destination/'manifest.json').write_text(json.dumps(dict(policy='EXACT_PROVIDER_INPUT_ONLY',
        bundle_sha256=hashlib.sha256((saved_visits.DATA/'bundle.json').read_bytes()).hexdigest(),
        receipts=len(selected),multiple_answers_same_input=collisions,human_approval=False)))
    return dict(path=str(destination.resolve()),receipts=len(selected),ambiguous_inputs=collisions)


def live_status():
    """Read-only preflight; never create, reset or settle the spend journal."""
    if os.environ.get('HILLINK_LIVE_APPROVAL_REFERENCE','').strip() == '':
        return False, 'LIVE_APPROVAL_REQUIRED'
    if os.environ.get('HILLINK_LLM_EXTERNAL_OPT_IN') != '1':
        return False, 'EXTERNAL_CALL_NOT_AUTHORIZED'
    path = os.environ.get('HILLINK_AGENT_BUDGET_FILE')
    if not path or not Path(path).is_file():return False, 'EXISTING_SHARED_BUDGET_REQUIRED'
    try:
        state=json.loads(Path(path).read_text())
        calls=int(os.environ.get('HILLINK_AGENT_MAX_CALLS','0'))
        usd=float(os.environ.get('HILLINK_AGENT_MAX_USD','0'))
        if not 0<calls<=2500 or not 0<usd<=20:return False,'APPROVED_LIMIT_REQUIRED'
        if calls>400 and not any(x.get('approved_max_calls',0)>=calls and x.get('unchanged_max_usd')==20 and x.get('approval_reference') for x in state.get('limit_amendments',[])):
            return False,'EXISTING_JOURNAL_CALL_EXTENSION_APPROVAL_REQUIRED'
        used=sum(r.get('charged_upper_usd',r['reserved_usd']) for r in state['requests'])
        if len(state['requests'])>=min(calls,state.get('approved_global_max_calls',state['max_calls'])):return False,'CALL_LIMIT'
        if used>=min(usd,state['max_usd']):return False,'USD_LIMIT'
    except (ValueError,TypeError,KeyError,OSError):return False,'INVALID_EXISTING_BUDGET'
    return True,None


def configure(payload):
    """Return a child-only environment and enforce the explicitly chosen mode."""
    mode=payload.get('judgment_mode')
    if mode is None:return payload,dict(os.environ),None  # compatible internal/test callers
    if mode not in MODES:raise ValueError('INVALID_JUDGMENT_MODE')
    request=copy.deepcopy(payload);request.pop('judgment_mode',None)
    env=dict(os.environ)
    if mode=='rules':
        request.pop('hybrid_policy',None)
        env.update(HILLINK_AUTONOMOUS_AGENT='0',HILLINK_AGENT_MODE='off',HILLINK_LLM_ENABLED='0',HILLINK_LLM_EXTERNAL_OPT_IN='0')
    else:
        if request.get('behavior_engine')!='m4_c01' or request.get('catalog_policy')!='C01_HOTEL_CATALOG_V1' or request.get('hybrid_policy') not in POLICIES:
            raise ValueError('V16_PRODUCT_CONTRACT_REQUIRED')
        if os.environ.get('HILLINK_AUTONOMOUS_AGENT')!='1':raise ValueError('AUTONOMOUS_ENGINE_DISABLED')
        env.update(HILLINK_AUTONOMOUS_AGENT='1',HILLINK_AGENT_MODE=mode)
        if mode=='replay':env.update(HILLINK_LLM_EXTERNAL_OPT_IN='0',HILLINK_LLM_ENABLED='0')
        else:
            ok,reason=live_status()
            if not ok:raise ValueError(reason)
    return request,env,mode


def describe(flow,mode,policy=None):
    if mode is None:return flow
    plans=flow.get('plans') or {}; customers={}; blocked=[]
    policy=policy if policy in POLICIES else POLICY
    for pid,plan in plans.items():
        records=plan.get('autonomous_decisions') or []
        origins=[a['provider'].get('execution') for d in records for a in d.get('attempts',[]) if a.get('provider')]
        holds=[d.get('fallback_reason') or d.get('hold_reason') or d.get('execution_state') for d in records if d.get('execution_state') not in ('VALIDATED','EXECUTED')]
        rule_only=[d for d in records if d.get('selection_owner')=='M4_RULE' and not d.get('attempts')]
        customers[pid]=dict(decisions=len(records),origins=origins,holds=holds,rule_decisions=len(rule_only))
        required='CACHE_REPLAY' if mode=='replay' else 'LIVE_RESPONSES'
        if mode!='rules' and (not records or holds or (not origins and not rule_only) or any(o!=required for o in origins)):
            blocked.append(pid)
    flow['judgment']=dict(requested=mode,actual='rules' if mode=='rules' else ('BLOCKED' if blocked or not plans else mode),
        policy=policy if mode!='rules' else 'RULE_ONLY',customers=customers,
        policy_note=None if mode=='rules' else POLICY_NOTES[policy],
        current_paid_calls=0 if mode in ('rules','replay') else None,human_approval=False)
    if mode!='rules' and (blocked or not plans):
        flow.update(error=('저장된 판단을 재현하지 못했습니다. 현재 조건과 일치하는 저장 응답이 없습니다.' if mode=='replay' else 'AI 판단을 완료하지 못했습니다. 호출 권한·예산·응답 상태를 확인해 주세요.')+' 규칙 계산으로 대체하지 않았습니다.',
                    code='V16_EXECUTION_HOLD')
    return flow


if __name__=='__main__':
    import sys
    print(json.dumps(prepare_replay_cache(sys.argv[1])))
