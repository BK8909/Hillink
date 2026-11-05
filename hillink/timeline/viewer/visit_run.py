"""연속 방문 실행 어댑터.

하루 계산기 autonomy_v1을 날짜별로 재사용하되, 고객별 방문 프로필을 한 번
고정하고 이전 날짜의 활동·행사·끼니·피로·혜택 상태를 다음 날짜 실행에 전달한다.
모든 날짜의 행동은 계속 기존 flow_run.py → autonomy_v1에서 계산된다.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLOW = [sys.executable, str(HERE / "flow_run.py")]
sys.path.insert(0, str(HERE))
import flow_run as FR  # noqa: E402
AD = FR.AD
import package_entitlements as PE  # noqa: E402

from operator_choice.operator_world_v1_1 import isolated_registry as IR

MAX_NIGHTS = 3
FIXED_START_DATE = "2026-10-24"
WINE_FAIR_DATES = {"2026-10-24", "2026-10-25"}
from operator_choice.autonomy_v1 import m4_runtime as M4
from operator_choice.autonomy_v1 import candidate_services as C01
from operator_choice.autonomy_v1 import operational_environment as OE
LEGACY_VISIT_ENGINE_VERSION = f"{AD.VERSION}+visit-state-v2.3-date-closure"
VISIT_ENGINE_VERSION = LEGACY_VISIT_ENGINE_VERSION + "+m4-" + M4.configuration()["sha256"][:12]
SLEEP_RECOVERY_PER_HOUR = abs(AD.EFFORT["sleep"])  # 기존 하루 엔진의 EFFORT 단위 사용
NON_ACTION_CODES = {"move", "wait", "idle", "sleep", "wake", "checkin", "checkout", "arrive", "leave", "unpack", "pack"}


def decision_backend(plans, requested_policy):
    """Describe executed provenance, not merely the operator's requested mode."""
    decisions=[d for p in plans.values() for d in p.get('autonomous_decisions',[])]
    executed=[d for d in decisions if d.get('execution_state')=='EXECUTED']
    fallbacks=[d for d in decisions if d.get('execution_state')=='RULE_FALLBACK']
    holds=[d for d in decisions if d.get('execution_state')=='EXECUTION_HOLD']
    calls=sum(p.get('trace',{}).get('llm_calls',0) for p in plans.values())
    replays=sum(p.get('trace',{}).get('llm_replays',0) for p in plans.values())
    if executed:
        origin='live' if calls else 'cache replay' if replays else 'synthetic or unverified provider'
        return 'LLM decisions ('+origin+') · M4 validation'+(' · partial rule fallback' if fallbacks else '')+(' · incomplete: execution HOLD' if holds else '')
    if holds:return 'Execution HOLD · no accepted autonomous decision; no scored replacement'
    if decisions:return 'Rule fallback · no accepted autonomous LLM decision'
    reviewed=any(r.get('review_succeeded') for p in plans.values() for r in p.get('native_review_attempts',[]))
    if reviewed:return 'Selective LLM review ('+('live' if calls else 'cache replay' if replays else 'unverified provider')+') · M4 execution'
    if requested_policy:return 'Rules · requested LLM review not applied'
    return 'rules(LLM 호출 0)'


def _resolve_catalog_room_contracts(resolutions, options, catalog, breakfast_policy=None):
    """Expose the same V2 explicit-room contract used by breakfast_policy."""
    from operator_choice.autonomy_v1 import breakfast_policy as BP
    if BP.policy({'breakfast_policy': breakfast_policy}) != BP.V2:
        return
    for pid, resolution in resolutions.items():
        sku = (options.get('room_products') or {}).get(pid)
        room = catalog.BY.get(sku)
        if not room:
            continue
        resolution['selected_room_sku_id'] = sku
        if room['venue_id'] == 'DOUGLAS':
            resolution['breakfast_plan'] = 'breakfast_included'
            resolution['breakfast_plan_source'] = 'SELECTED_ROOM_DOUGLAS_FACILITY_LIGHT_BREAKFAST_RIGHT'
        elif sku in ('HC-MENU-003', 'HC-MENU-023'):
            resolution['breakfast_plan'] = 'breakfast_included'
            resolution['breakfast_plan_source'] = 'SELECTED_ROOM_SOURCE_ADULT_TWO_BUFFET'
        else:
            resolution['breakfast_plan'] = 'room_only'
            resolution['breakfast_plan_source'] = 'SELECTED_ROOM_NO_AUTOMATIC_BUFFET_CONTRACT'


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()


def phase_schedule(duration):
    if duration == "day_visit":
        return [(1, "visit")]
    nights = {"stay_1": 1, "stay_2": 2, "stay_3": 3}.get(duration)
    if nights is None or not 1 <= nights <= MAX_NIGHTS:
        raise ValueError("지원하지 않는 체류 기간입니다")
    return [(1, "checkin")] + [(i + 1, "mid") for i in range(1, nights)] + [(nights + 1, "checkout")]


def day_specs(duration, start_date, event_mode):
    OE.validate_date(start_date)
    if event_mode not in ("none", "wine"):
        raise ValueError("행사 조건은 none 또는 wine만 지원합니다")
    start = date.fromisoformat(start_date)
    days = []
    for idx, phase in phase_schedule(duration):
        d = start + timedelta(days=idx - 1)
        iso = d.isoformat()
        event = event_mode == "wine" and iso in WINE_FAIR_DATES
        days.append(dict(day_index=idx, date=iso, phase=phase, event=event))
    if event_mode == "wine" and not any(d["event"] for d in days):
        raise ValueError("선택한 가상 날짜에는 와인페어가 열리지 않습니다")
    return days


def _resolve_visit(pid, duration, seed, inputs, package=None, conditions=None, behavior_engine="m4", breakfast_policy=None):
    P, bars, lib = inputs
    observe = "day" if duration == "day_visit" else "weekend"
    resolver = AD.Agent(pid, P, bars, lib, AD.scenario("visit_profile_resolution", event=False, observe=observe, seed=seed))
    base = copy.deepcopy(resolver.vs)
    base.setdefault('kids',bool(resolver.C.get('kids')))  # Preserve existing child signal for package eligibility, not inferred ages.
    if duration == "day_visit":
        base.update(stay=False, building=None, phase="visit", nights=0)
    else:
        if not base.get("building") and not (conditions or {}).get("building"):
            raise ValueError(f"{pid}: 숙박 건물을 가상 방문 조건으로 선택해 주세요")
        base.update(stay=True, nights={"stay_1": 1, "stay_2": 2, "stay_3": 3}[duration])
    explicit = dict(conditions or {})
    allowed = ("building", "party_size", "club", "breakfast_plan") + (("party_composition", "orders", "visit_purpose") if behavior_engine=="m4_c01" else ())
    if any(k not in allowed for k in explicit):
        raise ValueError("이 엔진에서 지원하는 방문 조건을 확인해 주세요")
    if "party_size" in explicit and (isinstance(explicit["party_size"], bool) or not isinstance(explicit["party_size"], int) or not 1 <= explicit["party_size"] <= 8):
        raise ValueError("방문 인원은 1~8인 정수로 선택해 주세요")
    if "building" in explicit and explicit["building"] not in ((None,) if duration=="day_visit" else ("GRAND","VISTA","DOUGLAS")):
        raise ValueError("방문 기간에 맞는 숙박 건물을 선택해 주세요")
    if "breakfast_plan" in explicit:
        from operator_choice.autonomy_v1 import breakfast_policy as BP
        BP.validate_plan(explicit["breakfast_plan"], explicit.get("building", base.get("building")), duration, {"breakfast_policy": breakfast_policy})
    if "visit_purpose" in explicit and explicit['visit_purpose'] not in ('anniversary','dining','rest','family_time','event','business','wellness'):
        raise ValueError('방문 목적은 확인한 운영자 시나리오 항목을 선택해 주세요')
    if "club" in explicit and not isinstance(explicit["club"], bool):
        raise ValueError("클럽 자격은 명시적인 참/거짓 값이어야 합니다")
    if behavior_engine=="m4_c01":
        from operator_choice.autonomy_v1.party_orders import validate
        explicit = validate(explicit, explicit.get("party_size",base["party_size"]))
        if explicit.get("party_composition") is not None:
            base["kids"] = bool(explicit["party_composition"]["children"])
    if explicit:
        base.update(explicit, layer="operator_override", condition_source="operator_selected_scenario")
    if package:
        if explicit.get("building") and explicit["building"] != package["building"]:
            raise ValueError("선택한 패키지는 그랜드 전용입니다. 건물 조건을 확인해 주세요")
        # Package reference occupants define entitlement coverage, not the
        # number of people actually visiting. Keep the resolved/operator party.
        base.update(stay=True, building=package["building"],
                    nights=package["nights"], package_context=copy.deepcopy(package),
                    package_reference_party_size=package["party_size"])
    from operator_choice.autonomy_v1 import breakfast_policy as BP
    base['breakfast_plan'] = BP.plan(base, {'breakfast_policy': breakfast_policy})
    base['breakfast_plan_source'] = 'OPERATOR_EXPLICIT' if 'breakfast_plan' in explicit else ('DOUGLAS_OFFICIAL_LIGHT_BREAKFAST_RIGHT' if base.get('building')=='DOUGLAS' and BP.policy({'breakfast_policy':breakfast_policy})==BP.V2 else BP.policy({'breakfast_policy': breakfast_policy}))
    # The generic room fallback must not bypass the catalog's established age rule.
    if behavior_engine == "m4_c01" and base.get("stay") and base.get("building") == "DOUGLAS":
        from types import SimpleNamespace
        from operator_choice.autonomy_v1 import hotel_catalog as HC
        age_product = next((p for p in HC.BY.values() if p.get("douglas_age_rule")), None)
        if age_product:
            subject = SimpleNamespace(N=base["party_size"], vs=base, C={"kids": bool(base.get("kids"))})
            if "DOUGLAS_AGE_QUALIFICATION_UNCONFIRMED_OR_INELIGIBLE" in HC.OC.restrictions(age_product, subject, 0, "room"):
                raise ValueError("더글라스는 아동 연령·이용 자격 확인이 필요합니다. 만 13세 미만 또는 초등학생 동반은 다른 숙박 건물을 선택해 주세요")
    if base.get("club") and (not base.get("stay") or base.get("building")!="GRAND"):
        raise ValueError("클럽 자격은 그랜드 투숙 조건에서만 설정할 수 있습니다")
    base.update(duration_source="operator_selected_scenario",
                assumption_note=("선택한 패키지에 맞춘 그랜드 2박 가상 시나리오입니다. 패키지 기준 인원과 실제 방문 인원은 별도입니다. 실제 예약 사실이 아니며 고객 행동 성향은 선택한 페르소나를 유지합니다."
                                if package else "체류 기간은 사용자가 설정한 가상 조건이며, 건물·인원은 고객별 방문 프로필의 사실 또는 모델 생성 출처를 따름"))
    return base


def _daily_flow(payload):
    proc = subprocess.run(FLOW, input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True,
                          encoding="utf-8", cwd=HERE,
                          timeout=1800 if str(payload.get('hybrid_policy','')).startswith('LLM_AUTONOMOUS_') else 300)
    if proc.returncode:
        raise RuntimeError((proc.stderr or "")[-2000:] or "하루 행동 엔진 실행 오류")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("하루 행동 엔진 응답을 읽지 못했습니다") from exc
    if out.get("error"):
        return out
    expected = IR.lineage(payload.get("personas") or [])
    if expected and out.get("isolated_input_lineage") != expected:
        raise RuntimeError("isolated_daily_profile_lineage_mismatch")
    return out


def _sleep_recovery(flow, pid, next_resolution):
    plan = (flow.get("plans") or {}).get(pid) or {}
    summary = plan.get("summary") or {}
    fatigue = float(summary.get("fatigue_end") or 0.0)
    sleeps = [s for s in plan.get("scenes") or [] if s.get("act") == "sleep"]
    sleep_end = int(sleeps[-1]["t1"]) if sleeps else 23 * 60
    p, bars, lib = AD.load_inputs()
    profile = AD.Agent(pid, p, bars, lib, AD.scenario("visit_wake_resolution", observe="weekend", seed=0))
    wake = 8 * 60 + 30 if "late" in profile.P["fact_hits"] else 7 * 60 + 30
    hours = max(0.0, (24 * 60 - sleep_end + wake) / 60)
    recovered = min(fatigue, hours * SLEEP_RECOVERY_PER_HOUR)
    return max(0.0, fatigue - recovered), dict(fatigue_before_sleep_recovery=round(fatigue, 4),
                                                sleep_hours_assumed=round(hours, 3),
                                                recovery_per_hour_existing_engine=SLEEP_RECOVERY_PER_HOUR,
                                                fatigue_after_sleep=round(max(0.0, fatigue - recovered), 4))


def _advance_state(state, flow, pid, day, next_resolution=None):
    plan = (flow.get("plans") or {}).get(pid) or {}
    if plan.get('autonomous_memory'):
        state['autonomous_memory'] = copy.deepcopy(plan['autonomous_memory'])
    actions = state.setdefault("prior_action_codes", [])
    facilities = state.setdefault("visited_facilities", [])
    meals = state.setdefault("prior_meals", [])
    checked = state.setdefault("checked_events", [])
    benefits = state.setdefault("benefit_usage", {"breakfast_in_package": {"scope": "per_morning_assumption", "dates": []},
                                                  "package_entitlements": {}})
    package_usage = benefits.get("package_entitlements")
    for scene in plan.get("scenes") or []:
        code, loc = scene.get("act"), scene.get("loc")
        if code and code not in NON_ACTION_CODES and code not in actions:
            actions.append(code)
        if loc and loc not in facilities and loc not in ("HOTEL_GATE", "move"):
            facilities.append(loc)
        if (code in ("WINE_FAIR", "WINE_FAIR:check", "turn_event") or scene.get("turn") == "event") and "WINE_FAIR" not in checked:
            checked.append("WINE_FAIR")
        meal = scene.get("meal")
        charge = ((scene.get("basis") or {}).get("charge") or {})
        if charge.get('hotel_entitlement_key'):
            state.setdefault('hotel_entitlement_usage',{})[charge['hotel_entitlement_key']]=1
        benefit_id = charge.get("entitlement_id")
        if benefit_id and (charge.get("status") == "포함" or charge.get("entitlement_consumed") is True):
            if not PE.consume_benefit(package_usage, benefit_id, day["date"]):
                charge.update(status="가격 미정", krw=None,
                              basis="포함 혜택 잔여 횟수 없음 · 추가 과금 조건 미확인")
                scene["basis"]["charge"] = charge
        if meal:
            meals.append(dict(date=day["date"], slot=meal, action=code, venue_id=loc, charge_status=charge.get("status")))
        if meal == "breakfast" and charge.get("status") == "포함" and day["date"] not in benefits["breakfast_in_package"]["dates"]:
            benefits["breakfast_in_package"]["dates"].append(day["date"])
    event_runs = [r for r in flow.get("runs") or [] if r.get("turn") == "event"]
    for run in event_runs:
        for customer in run.get("customers") or []:
            if customer.get("persona_id") != pid:
                continue
            choice = customer.get("choice") or {}
            history = state.setdefault("event_history", [])
            history.append(dict(date=day["date"], available=bool(day.get("event")), decision_id=customer.get("decision_id"),
                                selected_venue=choice.get("venue_id"), selected_product=choice.get("product_id"),
                                participated=choice.get("venue_id") == "FOREST"))
    if day["phase"] != "checkout" and next_resolution:
        fatigue, sleep = _sleep_recovery(flow, pid, next_resolution)
        state["fatigue_after_sleep"] = fatigue
        state["sleep_recovery"] = sleep
    last_action = next((s.get("act") for s in reversed(plan.get("scenes") or [])
                        if s.get("act") and s.get("act") not in NON_ACTION_CODES), None)
    if last_action and AD.SP.ACT.get(last_action):
        state["prior_last_kind"] = AD.SP.ACT[last_action][2]
    if plan.get("m4") is not None:
        state["m4_history"] = copy.deepcopy(plan["m4"]["activity_history"])
    state["day_index"] = day["day_index"]
    state["last_date"] = day["date"]
    state["reservation_state"] = "UNKNOWN_NO_RESERVATION_INPUT"
    state["last_phase"] = day["phase"]
    return state


def run_visit(request):
    personas = request.get("personas") or []
    if not personas or len(personas) != len(set(personas)) or any(p not in IR.allowed_personas(AD.DEMO) for p in personas):
        return {"error": "실행 가능한 고유 고객 ID를 선택해 주세요", "code": "E_VISIT_PERSONA"}
    behavior_engine = request.get("behavior_engine", "m4")
    if behavior_engine not in ("m4", "m4_c01", "legacy"):
        return {"error": "지원하지 않는 행동 엔진입니다", "code": "E_VISIT_ENGINE"}
    engine_version = VISIT_ENGINE_VERSION if behavior_engine in ("m4", "m4_c01") else LEGACY_VISIT_ENGINE_VERSION
    if behavior_engine == "m4_c01":
        engine_version = LEGACY_VISIT_ENGINE_VERSION + "+" + C01.VERSION + "-" + C01.configuration()["sha256"][:12]
    if AD.delivery_enabled():
        engine_version += "+external-delivery-v1"   # meal-alternative policy is part of run identity (previous policy runs keep their ids)
    simulation_mode = request.get("simulation_mode", "shared_world" if behavior_engine in ("m4", "m4_c01") and len(personas)>1 else "independent")
    if simulation_mode not in ("independent", "shared_world") or (simulation_mode == "shared_world" and behavior_engine not in ("m4", "m4_c01")):
        return {"error":"공동 월드 실행은 M4에서만 지원합니다", "code":"E_VISIT_SIMULATION_MODE"}
    duration = request.get("duration")
    event_mode = request.get("event_mode", "wine" if request.get("event") else "none")
    seed = request.get("seed", 0)
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= 9999:
        return {"error": "seed는 0~9999 정수여야 합니다", "code": "E_VISIT_SEED"}
    start_date = request.get("start_date") or FIXED_START_DATE
    breakfast_policy = request.get("breakfast_policy")
    if breakfast_policy is not None:
        from operator_choice.autonomy_v1 import breakfast_policy as BP
        if breakfast_policy not in BP.POLICIES:
            return {"error": "지원하는 조식 계약 정책을 선택해 주세요", "code": "E_VISIT_BREAKFAST_POLICY"}
    hybrid_policy = request.get('hybrid_policy')
    if hybrid_policy is not None:
        from operator_choice.autonomy_v1 import native_hybrid as NH
        from operator_choice.autonomy_v1 import autonomous_agent as AA
        if os.environ.get('HILLINK_NATIVE_HYBRID')!='1' or os.environ.get('HILLINK_V12Z_COMMON')!='1':
            return dict(error='통합 후보 엔진이 이 환경에서 활성화되지 않았습니다',code='E_VISIT_HYBRID_DISABLED')
        if hybrid_policy == AA.POLICY:
            if os.environ.get('HILLINK_AUTONOMOUS_AGENT') != '1' or request.get('catalog_policy') != 'C01_HOTEL_CATALOG_V1':
                return dict(error='자율 에이전트 정책과 상품 계약 활성화가 필요합니다',code='E_AGENT_POLICY_DISABLED')
            NH = AA
        if behavior_engine != 'm4_c01' or hybrid_policy != NH.POLICY:
            return {'error':'UNSUPPORTED_NATIVE_HYBRID_POLICY','code':'E_HYBRID_POLICY'}
    virtual_room_rates = request.get('virtual_room_rates')
    if virtual_room_rates is not None:
        if (not isinstance(virtual_room_rates, dict) or not virtual_room_rates
                or any(k not in ('GRAND','VISTA','DOUGLAS') or type(v) is not int or not 10_000 <= v <= 5_000_000 for k, v in virtual_room_rates.items())):
            return {'error':'가상 객실료는 GRAND·VISTA·DOUGLAS별 1박 금액(10,000~5,000,000원 정수)으로 입력해 주세요','code':'E_VISIT_ROOM_RATE'}
        if duration == 'day_visit':
            return {'error':'당일 방문에는 객실료를 입력할 수 없습니다','code':'E_VISIT_ROOM_RATE'}
    catalog_policy = request.get('catalog_policy')
    catalog_options = request.get('catalog_options') or {}
    if catalog_policy is not None:
        from operator_choice.autonomy_v1 import hotel_catalog as HC
        if behavior_engine != 'm4_c01' or catalog_policy != HC.POLICY:
            return {'error':'UNSUPPORTED_HOTEL_CATALOG_POLICY','code':'E_HOTEL_CATALOG_POLICY'}
        try: catalog_options = HC.validate(catalog_options, personas)
        except ValueError as exc: return {'error':str(exc),'code':'E_HOTEL_CATALOG_INPUT'}
    elif catalog_options:
        return {'error':'CATALOG_OPTIONS_REQUIRE_EXPLICIT_POLICY','code':'E_HOTEL_CATALOG_INPUT'}
    try:
        environment = OE.validate(request.get("environment"))
        OE.validate_date(start_date, request.get("scenario") is not None)
        scenario_snapshot = None
        if request.get("scenario") is not None or catalog_policy:
            if behavior_engine != "m4_c01":raise ValueError("행사 카드 실행은 명시적 m4_c01에서만 지원합니다")
            from operator_choice.autonomy_v1 import event_scenarios as ES
            scenario_request=copy.deepcopy(request.get("scenario") or dict(event_card_id="WINE_FAIR_2026_AUTUMN" if event_mode=="wine" else "NONE",enabled=True))
            if environment.get("weather"):scenario_request.setdefault("weather",{})["condition"]=environment["weather"]
            if environment.get("arrival_time"):scenario_request["arrival_time"]=environment["arrival_time"]
            scenario_snapshot=ES.snapshot(scenario_request,start_date,duration)
            if set(scenario_snapshot['entitlements'])-set(personas):raise ValueError('행사 자격은 선택한 고객에게만 설정할 수 있습니다')
            if scenario_snapshot['event_card_id']=='SAVORING_SUMMER_NIGHT_2026' and request.get('package_id'):raise ValueError('리버파크 행사 패키지와 다른 객실 패키지를 동시에 가정할 수 없습니다')
            days=ES.schedule(scenario_snapshot)
            engine_version += "+"+ES.VERSION+"-"+hashlib.sha256(Path(ES.__file__).read_bytes()).hexdigest()[:12]
        else:
            days = day_specs(duration, start_date, event_mode)
        package_id = request.get("package_id")
        package = PE.get_package(package_id)
        if package_id and package is None:
            raise ValueError("선택한 객실 패키지를 지원하지 않습니다")
        if package:
            if duration != "stay_2":
                raise ValueError("두근두근 성수 Ver.2 2박형은 2박 3일 방문 시나리오에서만 선택할 수 있습니다")
            if not package["effective_from"] <= start_date <= package["effective_to"]:
                raise ValueError("선택한 가상 방문일은 패키지 게시 기간 밖입니다")
        inputs = AD.load_inputs()
        profiles = inputs[0]
        missing = [pid for pid in personas if pid not in profiles]
        if missing:
            return {"error": "행동 프로파일 입력이 연결되지 않은 고객이 있습니다", "code": "E_FLOW_INPUT_MISSING", "ids": missing}
        conditions = request.get("visit_conditions") or {}
        if not isinstance(conditions, dict) or any(pid not in personas or not isinstance(v, dict) for pid,v in conditions.items()):
            raise ValueError("선택한 고객별 방문 조건을 확인해 주세요")
        base_resolutions = {pid: _resolve_visit(pid, duration, seed, inputs, package, conditions.get(pid), behavior_engine, breakfast_policy) for pid in personas}
        from operator_choice.autonomy_v1 import santa_2026 as S26
        S26.validate_visits(scenario_snapshot,base_resolutions,request)
        if catalog_policy:
            import catalog_request_adapter
            catalog_options=catalog_request_adapter.connect(catalog_options,base_resolutions,HC,{d['date'] for d in days})
            _resolve_catalog_room_contracts(base_resolutions,catalog_options,HC,breakfast_policy)
    except (ValueError, KeyError) as exc:
        return {"error": str(exc), "code": "E_VISIT_INPUT"}

    states = {}
    for pid in personas:
        usage = {"breakfast_in_package": {"scope": "per_morning_assumption", "dates": []}}
        if package:
            usage["package_entitlements"] = PE.initial_benefit_usage(package)
        states[pid] = {"prior_action_codes": [], "visited_facilities": [], "prior_meals": [], "checked_events": [], "event_history": [],
                       "benefit_usage": usage, "fatigue_after_sleep": 0.0,
                       "reservation_state": "UNKNOWN_NO_RESERVATION_INPUT"}
    day_flows = []
    for day in days:
        resolution = {}
        for pid in personas:
            current = copy.deepcopy(base_resolutions[pid])
            current["phase"] = day["phase"]
            resolution[pid] = current
        body = dict(personas=personas, mode="one" if len(personas) == 1 else "many", seed=seed,
                    event=day["event"], intervention="none", product_levers={}, observe="weekend" if duration != "day_visit" else "day",
                    visit_date=day["date"], behavior_engine=behavior_engine, simulation_mode=simulation_mode,
                    visit_resolution=resolution, visit_state=copy.deepcopy(states))
        if scenario_snapshot:body["scenario_snapshot"]=copy.deepcopy(scenario_snapshot)
        if catalog_policy: body.update(catalog_policy=catalog_policy,catalog_options=copy.deepcopy(catalog_options))
        if environment: body["environment"]=copy.deepcopy(environment)
        if hybrid_policy: body['hybrid_policy']=hybrid_policy
        if breakfast_policy: body['breakfast_policy']=breakfast_policy
        flow = _daily_flow(body)
        if flow.get("error"):
            return flow
        if set(flow.get("plans") or {}) != set(personas):
            return {"error": "방문 중 일부 날짜의 실행 고객이 달라졌습니다", "code": "E_VISIT_COHORT_DRIFT"}
        next_resolution = base_resolutions if day["phase"] != "checkout" else None
        for pid in personas:
            state = _advance_state(states[pid], flow, pid, day, next_resolution)
            if scenario_snapshot:
                for scene in flow['plans'][pid]['scenes']:
                    usage=((scene.get('basis') or {}).get('charge') or {}).get('scenario_event_usage')
                    if usage and usage not in state.setdefault('scenario_event_usage',[]):state['scenario_event_usage'].append(usage)
            states[pid] = state
            for scene in flow["plans"][pid].get("scenes") or []:
                scene["visit_day"] = day["day_index"]
                scene["visit_date"] = day["date"]
                scene["day_phase"] = day["phase"]
        for run in flow.get("runs") or []:
            run["visit_day"] = day["day_index"]
            run["visit_date"] = day["date"]
            run["day_phase"] = day["phase"]
        for pid in personas:
            flow["plans"][pid]["visit_state_after"] = copy.deepcopy(states[pid])
        day_flows.append(dict(day_index=day["day_index"], date=day["date"], phase=day["phase"],
                              event=day["event"], flow=flow, state_after=copy.deepcopy(states)))

    combined_plans = {}
    for pid in personas:
        source = day_flows[0]["flow"]["plans"][pid]
        scenes = [scene for day in day_flows for scene in (day["flow"]["plans"][pid].get("scenes") or [])]
        summaries = [day["flow"]["plans"][pid].get("summary") or {} for day in day_flows]
        summary = copy.deepcopy(summaries[0])
        for key in ("n_actions", "timeline_actions", "idle_blocks", "idle_min", "engine_actions", "planner_actions", "review_evidence_actions", "llm_actions", "spent_krw", "spent_known_krw", "spent_party_estimate_krw"):
            if all(isinstance(s.get(key), (int, float)) for s in summaries):
                summary[key] = sum(s.get(key, 0) for s in summaries)
        summary["completed"] = all(s.get("completed") for s in summaries)
        summary["visit_days"] = [{"date": d["date"], "phase": d["phase"], "scene_count": len(d["flow"]["plans"][pid].get("scenes") or [])} for d in day_flows]
        summary["visit_state_transitions"] = [{"day_index": d["day_index"], "date": d["date"], "phase": d["phase"],
                                                "input_state": copy.deepcopy(d["flow"]["plans"][pid].get("visit_state_used") or {}),
                                                "state_after": copy.deepcopy(d["flow"]["plans"][pid].get("visit_state_after") or {})} for d in day_flows]
        combined_plans[pid] = dict(source, scenes=scenes, summary=summary,
                                   trace=dict(source.get("trace") or {}, visit_stateful=True, visit_day_count=len(days), llm_calls=0))
        if any('autonomous_decisions' in d['flow']['plans'][pid] or 'native_review_attempts' in d['flow']['plans'][pid] for d in day_flows):
            if any('autonomous_decisions' in d['flow']['plans'][pid] for d in day_flows):
                combined_plans[pid]['autonomous_decisions'] = [r for d in day_flows for r in d['flow']['plans'][pid].get('autonomous_decisions',[])]
                combined_plans[pid]['autonomous_memory'] = copy.deepcopy(day_flows[-1]['flow']['plans'][pid].get('autonomous_memory'))
            if any('native_review_attempts' in d['flow']['plans'][pid] for d in day_flows):
                combined_plans[pid]['native_review_attempts'] = [r for d in day_flows for r in d['flow']['plans'][pid].get('native_review_attempts',[])]
            traces = [d['flow']['plans'][pid]['trace'] for d in day_flows]
            combined_plans[pid]['trace'].update({k:sum(t.get(k,0) for t in traces) for k in ('llm_calls','llm_errors','llm_replays')})
            combined_plans[pid]['trace']['planner_backend_fallback_used'] = any(t.get('planner_backend_fallback_used') for t in traces)

    if behavior_engine in ("m4", "m4_c01"):
        for pid in personas:
            parts=[d["flow"]["plans"][pid].get("m4") or {} for d in day_flows]
            combined_plans[pid]["m4"] = dict(parts[-1], decisions=[r for p in parts for r in p.get("decisions",[])],
                movement_history=[r for p in parts for r in p.get("movement_history",[])])
            combined_plans[pid]['m4']['hotel_product_decisions']=[r for p in parts for r in p.get('hotel_product_decisions',[])]
    run_request = {"personas": personas, "duration": duration, "event_mode": event_mode, "start_date": start_date, "seed": seed}
    run_request["behavior_engine"] = behavior_engine
    if environment or start_date != FIXED_START_DATE:
        run_request["environment_snapshot"]=OE.snapshot(environment,start_date)
        run_request["environment_implementation_sha256"]=hashlib.sha256(Path(OE.__file__).read_bytes()).hexdigest()
    if hybrid_policy:
        run_request['hybrid_configuration']=NH.configuration()
        run_request['hybrid_execution_sha256']=_sha([dict(inputs=d['flow'].get('inputs_sha'),
            reviews=[scene.get('basis',{}).get('review') for plan in d['flow']['plans'].values() for scene in plan['scenes'] if scene.get('basis',{}).get('review')],
            autonomous=[plan.get('autonomous_decisions') for plan in d['flow']['plans'].values() if plan.get('autonomous_decisions')]) for d in day_flows])
        run_request["hybrid_policy"]=hybrid_policy
    if catalog_policy: run_request.update(catalog_policy=catalog_policy,catalog_options=copy.deepcopy(catalog_options),hotel_catalog_sha256=HC.SHA)
    if scenario_snapshot:run_request["scenario_snapshot"]=scenario_snapshot
    if virtual_room_rates: run_request["virtual_room_rates"] = dict(sorted(virtual_room_rates.items()))
    from operator_choice.autonomy_v1 import breakfast_policy as _BP
    run_request["breakfast_policy"] = _BP.policy({"breakfast_policy": breakfast_policy})   # part of run identity (11/03 policy change)
    if simulation_mode == "shared_world":
        run_request["simulation_mode"] = simulation_mode
    if conditions:
        run_request["visit_conditions"] = copy.deepcopy(conditions)
    if package_id:
        run_request["package_id"] = package_id
    run_id = _sha({"engine_version": engine_version,
                   "request": run_request,
                   "profile_sha": [d["flow"].get("profile_sha") for d in day_flows],
                   "day_inputs": [{k: d[k] for k in ("date", "phase", "event")} for d in day_flows]})
    visits = {}
    for pid in personas:
        v = copy.deepcopy(day_flows[0]["flow"]["visits"][pid])
        v.update(phase="visit" if duration == "day_visit" else "stay", nights=0 if duration == "day_visit" else {"stay_1": 1, "stay_2": 2, "stay_3": 3}[duration],
                 duration=duration, duration_source="operator_selected_scenario", visit_id=run_id,
                 assumption_note=base_resolutions[pid].get("assumption_note"))
        if duration != "day_visit":
            v["breakfast_plan"] = base_resolutions[pid].get("breakfast_plan") or "room_only"   # 11/03 조식 계약(객실 원장 · 식음 원장 공통 기준)
        for contract_key in ("breakfast_plan_source", "selected_room_sku_id"):
            if contract_key in base_resolutions[pid]:
                v[contract_key] = base_resolutions[pid][contract_key]
        if package:
            v["package_context"] = copy.deepcopy(package)
            v["benefit_usage"] = copy.deepcopy(states[pid].get("benefit_usage") or {})
        visits[pid] = v
    visit_meta = dict(visit_id=run_id, start_date=start_date, duration=duration,
                      nights=0 if duration == "day_visit" else {"stay_1": 1, "stay_2": 2, "stay_3": 3}[duration],
                      date_basis="FIXED_VIRTUAL_SCENARIO_DATE", event_mode=event_mode, behavior_engine=behavior_engine, simulation_mode=simulation_mode,
                      profile_condition_source=("persona behavior profile; building, party size and package are operator-selected scenario conditions" if package
                                                else "per-persona resolved review/model profile; duration operator-selected"),
                      room_price_policy=("selected package scenario; payment not observed or auto-posted" if package else "nightly package assumption repeated per simulated night; actual multi-night package price unverified"))
    if "environment_snapshot" in run_request:
        visit_meta["environment_snapshot"]=copy.deepcopy(run_request["environment_snapshot"])
        visit_meta["environment_implementation_sha256"]=run_request["environment_implementation_sha256"]
        visit_meta["date_basis"]="OPERATOR_VIRTUAL_CALENDAR_DATE"
    visit_meta["breakfast_policy"] = run_request["breakfast_policy"]
    if hybrid_policy:
        visit_meta.update(hybrid_policy=hybrid_policy,hybrid_mode=run_request['hybrid_configuration'].get('mode',os.environ.get("HILLINK_HYBRID","off")),hybrid_configuration=run_request["hybrid_configuration"],hybrid_execution_sha256=run_request["hybrid_execution_sha256"])
    if scenario_snapshot:visit_meta["scenario_snapshot"]=copy.deepcopy(scenario_snapshot)
    visit_meta["requested_conditions"] = copy.deepcopy(conditions)
    if virtual_room_rates:
        visit_meta["virtual_room_rates"] = dict(rates=dict(sorted(virtual_room_rates.items())), unit='ONE_ROOM_ONE_NIGHT_KRW',
                                                basis='OPERATOR_EXPLICIT_VIRTUAL_INPUT_NOT_OBSERVED_NOT_A_SALE_PRICE')
    if catalog_policy:
        import room_revenue as _hc_rooms
        visit_meta['hotel_base_room_rates']={k:copy.deepcopy(v) for k,v in _hc_rooms.prices.PRICE.items() if k.startswith('room:')}
        visit_meta.update(catalog_policy=catalog_policy,catalog_options=copy.deepcopy(catalog_options),hotel_catalog_sha256=HC.SHA,hotel_price_snapshot=copy.deepcopy(HC.DATA))
    visit_meta["resolved_conditions"] = {pid:{k:visits[pid].get(k,base_resolutions[pid].get(k)) for k in ("building","party_size","stay","nights","club","layer","condition_source","package_reference_party_size","breakfast_plan","breakfast_plan_source","selected_room_sku_id") + (("party_composition","orders","pricing_input_provenance") if behavior_engine=="m4_c01" else ())} for pid in personas}
    if behavior_engine in ("m4", "m4_c01"):
        visit_meta["m4_configuration"] = (C01 if behavior_engine == "m4_c01" else M4).configuration()
    if package:
        visit_meta.update(package_id=package_id, package_context=copy.deepcopy(package))
    shared = None
    if simulation_mode == "shared_world":
        shared = dict(mode="SHARED_WORLD_CHRONOLOGICAL", customer_ids=sorted(personas),
                      visit_id=run_id, days=[copy.deepcopy(d["flow"]["shared_world"]) for d in day_flows],
                      capacity_and_queues_supported=False, customer_interactions_supported=False,
                      source="LIVE_EXECUTION_NOT_STORED_INDEPENDENT_RESULTS")
    return dict(**({"isolated_input_lineage": IR.lineage(personas)} if IR.lineage(personas) else {}), shared_world=shared,visit_id=run_id, visit=visit_meta,
                visit_days=day_flows, plans=combined_plans, visits=visits,
                runs=[r for d in day_flows for r in d["flow"].get("runs", [])],
                mode="one" if len(personas) == 1 else "many", engine=dict(name=FR.ENGINE, version=engine_version + ("+package-entitlement-v1" if package else ""), backend=decision_backend(combined_plans,hybrid_policy), behavior_engine=behavior_engine, simulation_mode=simulation_mode, execution_mode="LIVE_COMPUTATION_NOT_REPLAY", seed=seed,
                                                                           visit_stateful=True, visit_day_count=len(days)),
                input_missing=sorted({p for d in day_flows for p in d["flow"].get("input_missing", [])}),
                notices=sorted({n for d in day_flows for n in d["flow"].get("notices", [])}),
                visit_inputs_sha=_sha({"engine_version": engine_version + ("+package-entitlement-v1" if package else ""),
                                       "request": run_request, "resolutions": base_resolutions}),
                source="live_engine")


def main():
    request = json.loads(sys.stdin.read() or "{}")
    if request.get("behavior_engine")=="be01":
        from be01_bridge import run_visit as be01_run_visit
        result=be01_run_visit(request)
    else:
        result=run_visit(request)
    print(json.dumps(result, ensure_ascii=False, default=list))


if __name__ == "__main__":
    main()
