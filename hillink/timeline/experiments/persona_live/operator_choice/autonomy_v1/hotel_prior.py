"""Research: hotel-level general behaviour prior (default OFF; never part of V19LS or the stored replays).

One rule, for one action: a staying guest's dinner choice of EXTERNAL_DELIVERY. When the selected operating reference
gives the hotel's share of stay-team evenings eaten from external delivery (metric delivery.evening_share_per_stay,
the only denominator accepted), and the customer has NO personal evidence about eating in the room, that share is
used in place of the missing personal level of the existing 'practical alternative (eat in the room)' term:

    delta = W['practical'] (0.8, the engine's existing coefficient) x share

The mapping (population share -> missing personal level) is a stated model assumption, fixed before any run and
never tuned to make the group reach the reference share. Personal evidence always wins:
  - personal practical_alt evidence present  -> not applied (the personal term already speaks)
  - a source-linked negative term on this candidate, or the venue directly avoided -> not applied
  - not a dinner decision, or the reference is missing / UNKNOWN / another denominator -> not applied
Every applied or skipped decision is traced with the reference class, file SHA and the reason.
"""
import json
import os

VERSION = 'HOTEL_PRIOR_V1'
TARGET_ACTION = 'EXTERNAL_DELIVERY'
METRIC = 'delivery.evening_share_per_stay'
DINNER_WINDOW = (16 * 60, 23 * 60)


def config():
    raw = os.environ.get('HILLINK_BEHAVIOUR_PRIOR_JSON')
    if not raw:
        return None
    cfg = json.loads(raw)
    if cfg.get('policy') != VERSION:
        raise ValueError('E_BEHAVIOUR_PRIOR_POLICY')
    return cfg


def adjustment(offer, terms, context, traits, practical_level):
    """(delta, trace) for one candidate at the actual decision (no lookahead). trace is None when the prior is off
    or the candidate is not the prior's action, so runs with the prior OFF are byte-identical to before."""
    cfg = config()
    if cfg is None or offer.get('id') != TARGET_ACTION:
        return 0.0, None
    trace = dict(version=VERSION, action=TARGET_ACTION, metric_id=METRIC, applied=False, delta=0.0,
                 reference=cfg.get('reference'), status=cfg.get('status'),
                 formula="W['practical'] x hotel share, only when personal practical_alt evidence is absent",
                 coefficient_origin='EXISTING_ENGINE_COEFFICIENT_PRACTICAL_0.8; SHARE_AS_MISSING_PERSONAL_LEVEL_IS_A_MODEL_ASSUMPTION',
                 scope='ACTUAL_CURRENT_DECISION_ONLY_NO_LOOKAHEAD')

    def stop(reason):
        trace['reason'] = reason
        return 0.0, trace
    if cfg.get('status') != 'APPLICABLE':
        return stop(cfg.get('status') or 'NO_APPLICABLE_REFERENCE')
    t = context.get('time')
    if t is None or not DINNER_WINDOW[0] <= t <= DINNER_WINDOW[1]:
        return stop('NOT_A_DINNER_DECISION')
    if practical_level > 0:
        return stop('PERSONAL_PRACTICAL_ALT_EVIDENCE_PROTECTED')
    if (context.get('direct_avoid_venues') or {}).get(offer.get('venue')) or any(x.get('fact_ids') and x.get('value', 0) < 0 for x in terms):
        return stop('SOURCE_LINKED_NEGATIVE_EVIDENCE_PROTECTED')
    share = float(cfg['reference']['value'])
    delta = round(cfg['coefficient'] * share, 6)
    trace.update(applied=True, delta=delta, share=share, coefficient=cfg['coefficient'], reason='NO_PERSONAL_EVIDENCE_HOTEL_PRIOR_USED')
    return delta, trace
