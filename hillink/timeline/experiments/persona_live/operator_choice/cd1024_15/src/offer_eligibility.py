"""CD-1024-15 isolated offer eligibility. No product integration."""
from datetime import date, datetime

VALID_STATUSES={"VERIFIED","PARTIAL","SCENARIO"}


def _date(value):
    try: return date.fromisoformat(value) if value else None
    except (TypeError,ValueError): return None

def _time(value):
    try: return datetime.strptime(value,"%H:%M").time() if value else None
    except (TypeError,ValueError): return None

def check_offer(offer, request, *, allow_scenario=False, reservation_confirmed=None):
    status=offer.get('verification_status')
    if status not in VALID_STATUSES: return {'status':'INSUFFICIENT_DATA','reasons':['unknown_verification_status']}
    if status=='SCENARIO' and not allow_scenario: return {'status':'INSUFFICIENT_DATA','reasons':['scenario_not_enabled']}
    date_v=_date(request.get('simulation_date')); time_v=_time(request.get('start_time'))
    missing=[]
    if not date_v: missing.append('simulation_date_missing_or_invalid')
    if not time_v: missing.append('start_time_missing_or_invalid')
    if request.get('meal_period') not in (offer.get('meal_period') or []):
        if request.get('meal_period'): return {'status':'INELIGIBLE','reasons':['meal_period_mismatch']}
        missing.append('meal_period_missing')
    if not isinstance(request.get('party_size'),int) or request.get('party_size',0)<1: missing.append('party_size_missing_or_invalid')
    if not isinstance(request.get('duration_minutes'),int) or request.get('duration_minutes',-1)<0: missing.append('duration_missing_or_invalid')
    if not isinstance(request.get('is_public_holiday'),bool): missing.append('holiday_status_missing_or_invalid')
    if offer.get('reservation_required') and reservation_confirmed is None: missing.append('reservation_assumption_missing')
    if missing: return {'status':'INSUFFICIENT_DATA','reasons':missing}
    if date_v:
        valid_from,valid_to=_date(offer.get('valid_from')),_date(offer.get('valid_to'))
        if valid_from and date_v<valid_from or valid_to and date_v>valid_to:
            return {'status':'INELIGIBLE','reasons':['outside_validity_window']}
        days=offer.get('day_of_week')
        if days is not None and date_v.strftime('%a') not in days:
            return {'status':'INELIGIBLE','reasons':['day_of_week_mismatch']}
    if offer.get('holiday_policy')=='exclude' and request['is_public_holiday']:
        return {'status':'INELIGIBLE','reasons':['public_holiday_excluded']}
    party=request['party_size']; pmin,pmax=offer.get('party_size_min'),offer.get('party_size_max')
    if offer.get('price_basis')=='per_adult' and request.get('party_composition',{}).get('children',0)>0:
        return {'status':'INSUFFICIENT_DATA','reasons':['child_price_or_adult_child_composition_unverified']}
    if pmin is not None and party<pmin: return {'status':'INELIGIBLE','reasons':['party_below_minimum']}
    if pmax is not None and party>pmax: return {'status':'INELIGIBLE','reasons':['party_above_maximum']}
    condition=offer.get('eligibility_conditions') or {}
    if condition.get('stay_required') is True and request.get('stay_status')=='non_staying':
        return {'status':'INELIGIBLE','reasons':['stay_required']}
    if condition.get('stay_required') is True and request.get('stay_status') not in ('staying','non_staying'):
        missing.append('stay_status_missing')
    seating=condition.get('seating_type')
    if seating and request.get('seat_type')!=seating:
        if request.get('seat_type') is None: missing.append('seat_type_missing')
        else: return {'status':'INELIGIBLE','reasons':['seat_type_mismatch']}
    if offer.get('reservation_required') and reservation_confirmed is False:
        return {'status':'INELIGIBLE','reasons':['reservation_not_assumed_available']}
    rules=offer.get('session_rules')
    if rules:
        weekday=date_v.strftime('%a'); applicable=[]
        for rule in rules:
            if weekday not in rule.get('days',[]): continue
            h=rule.get('holiday','any')
            if h=='non_holiday' and request['is_public_holiday']: continue
            if h=='public_holiday' and not request['is_public_holiday']: continue
            if h=='any' or h in ('non_holiday','public_holiday'): applicable.append(rule)
        if not applicable: return {'status':'INSUFFICIENT_DATA','reasons':['no_matching_session_rule']}
        start_min=time_v.hour*60+time_v.minute; dur=request['duration_minutes']
        fits=[]
        for r in applicable:
            st,en=_time(r.get('start')),_time(r.get('end'))
            if not st or not en: continue
            sm=st.hour*60+st.minute; em=en.hour*60+en.minute
            if sm<=start_min<em and start_min+dur<=em: fits.append(r)
        if not fits: return {'status':'INELIGIBLE','reasons':['outside_or_exceeds_session']}
    elif offer.get('session_start') or offer.get('session_end'):
        st,en=_time(offer.get('session_start')),_time(offer.get('session_end'))
        if not st or not en: missing.append('session_boundary_incomplete')
        else:
            sm,em=st.hour*60+st.minute,en.hour*60+en.minute
            tmin=time_v.hour*60+time_v.minute
            if not (sm<=tmin and tmin+request['duration_minutes']<=em):
                return {'status':'INELIGIBLE','reasons':['outside_or_exceeds_session']}
    if status=='PARTIAL': missing.append('offer_data_partial')
    if offer.get('price_amount') is None or not offer.get('price_basis'): missing.append('price_or_basis_missing')
    if not offer.get('source_url') or not offer.get('source_checked_at'): missing.append('source_provenance_missing')
    if missing: return {'status':'INSUFFICIENT_DATA','reasons':list(dict.fromkeys(missing))}
    return {'status':'ELIGIBLE','reasons':[]}
