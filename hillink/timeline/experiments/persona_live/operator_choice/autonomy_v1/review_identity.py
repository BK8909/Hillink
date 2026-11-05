"""Review provenance and strict cache identity. No approximate response reuse."""
import hashlib,json,math,os

def sha(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=list).encode()).hexdigest()

def identity(packet,config,version,system):
    return dict(version='native-review-cache-v1',review_version=version,
        policy=config.get('native_policy','SOURCE_V12Z_REVIEW_V1'),model=config['model'],effort=config['effort'],
        system_sha256=hashlib.sha256(system.encode()).hexdigest(),input_sha256=sha(packet),
        customer_sha256=sha(packet.get('customer')),state_sha256=sha(packet.get('stay')),
        candidates_sha256=sha(packet.get('candidates')),vote=packet.get('_vote'))

def live_allowed(config):
    # A generic live flag or inherited key is not a budget authorization.
    explicit=os.environ.get('HILLINK_HYBRID_MAX_USD')
    try:budget=float(explicit) if explicit is not None else 0;limit=float(config.get('max_usd',0))
    except (ValueError,TypeError):return False
    return (os.environ.get('HILLINK_LLM_EXTERNAL_OPT_IN')=='1' and math.isfinite(budget)
            and math.isfinite(limit) and budget>0 and 0<limit<=budget)

def execution(entry):
    if not entry:return dict(review_execution='NOT_REVIEWED',decision_source='RULE_ENGINE',review_succeeded=False)
    call=entry.get('call') or {};answer=entry.get('llm')
    if call.get('fixture'):mode='SYNTHETIC_TEST'
    elif call.get('cache_hit') and answer:mode='CACHE_REPLAY'
    elif call.get('provider_response_received') and answer:mode='LIVE_REVIEW'
    elif call.get('skipped') in ('replay_miss','cache_policy_mismatch','cache_content_mismatch'):mode='CACHE_MISS'
    elif call.get('skipped') in ('budget','authorization','dry'):mode='REVIEW_NOT_RUN'
    elif call.get('error') or call.get('skipped')=='INVALID_REVIEW_RULE_KEPT':mode='REVIEW_ERROR'
    else:mode='UNVERIFIED_REVIEW_RECORD' if answer else 'NOT_REVIEWED'
    adopted='ADOPTED' in str(entry.get('outcome'))
    successful=bool(answer) and mode in ('CACHE_REPLAY','LIVE_REVIEW') and not entry.get('validation_error')
    source=('SYNTHETIC_REVIEW_ADOPTED' if mode=='SYNTHETIC_TEST' and adopted else
            'REVIEW_ADOPTED' if successful and adopted else 'RULE_ENGINE')
    return dict(review_execution=mode,decision_source=source,review_succeeded=successful,
                provider_call_performed=bool(call.get('network_attempted')),cache_hit=bool(call.get('cache_hit')))
