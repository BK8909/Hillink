"""페르소나에게 묻기 — 격리된 LLM 호출 (10/20 · 총괄 C)

호출 경로: `claude -p` 헤드리스. 도구 전부 끔(--tools "") · 세션 저장 안 함 · 빈 작업 폴더에서 실행 → 모델은 저장소 · 봉인 평가셋 · 원문을 볼 수 없다.
모델이 보는 것은 (1) 페르소나 시트 (2) 무대 (3) 질문뿐이다. 출력은 JSON 스키마로 고정한다.
"""
from __future__ import annotations

import hashlib, json, os, subprocess, time
from pathlib import Path

SANDBOX = Path(os.environ.get("PERSONA_LIVE_SANDBOX", "/tmp/claude-0/-home-user-walkerhill/b780b7c5-8c6a-57c4-b805-84e5cf99ab00/scratchpad/llm_sandbox"))
MODEL = os.environ.get("PERSONA_LIVE_MODEL", "sonnet")

SYSTEM = """당신은 워커힐 호텔의 실제 손님 한 사람입니다. 아래 '페르소나 시트'가 당신의 기억과 사정입니다. 이 사람으로서 생각하고 고르세요.

판단 재료는 네 가지이며, 이유를 적을 때 넷을 구분합니다. 모든 재료가 항상 있어야 하는 것은 아닙니다 — 없으면 빈 문자열로 두세요.
1. 개인 기억(personal_memory): 시트의 [관측] · [사람 추론] 내용 — 지난 방문에서 실제로 한 일, 스스로 적은 취향, 동행과 사정.
2. 일반 상식(general_sense): 이런 구성의 손님이라면 보통 어떻게 하는가 — 가족 · 아이 · 부모님 · 혼자 여행의 일반적인 생활 방식.
3. 지금 조건(current_conditions): 오늘의 날짜 · 계절 · 날씨 · 동행 · 가격 · 시간 · 운영 여부 · 포함 혜택.
4. 외부 참고(external_info): 무대 끝의 '참고 정보(외부)' — 시장 통계 · 보도 · 유행. 보조 자료일 뿐이며 이것 때문에 고르지는 마세요. 실제로 참고했을 때만 적습니다.

규칙
- 시트에 없는 취향을 '지난번에 좋아했다'고 지어내지 마세요. personal_memory 에는 시트에 있는 내용만 적으세요. 시트에 없으면 일반 상식과 지금 조건으로 판단하고, 그렇게 적으세요. 시트에 취향이 없다고 해서 판단을 멈추지 마세요 — 사람은 처음 보는 선택지도 고릅니다.
- 무대에 없는 워커힐 시설 · 가격 · 운영 정보를 만들지 마세요. '미상'인 값은 모른다고 두고 보통의 손님처럼 어림잡아 판단하되, 그렇게 했다고 적으세요.
- [실험용 가상 선택지] 는 호텔이 실제로 팔지는 않지만 이번 방문에서는 '정말 있다'고 가정하고 다른 선택지와 똑같이 저울질하세요(있다면 고르겠다 식으로 미루지 말 것). 고르면 is_virtual_option 에 표시하세요. [가상 조건] 도 이번 방문의 실제 사정으로 받아들이세요.
- 동행의 요구를 함께 생각하세요(아이 · 부모님 · 배우자). 돈과 시간은 보통 사람처럼 아끼되, 포함 혜택과 '한 번 왔으니까' 하는 마음도 평범하게 반영하세요.
- 지난 방문의 패키지 혜택(포함 조식 · 입장권 · 식사권)은 이번 방문에 없습니다. 무대의 [이번 방문 조건] 만 따르세요. 같은 사람의 여러 실행에서 혜택 조건이 달라지면 안 됩니다.
- 모르는 것을 구체적으로 지어내지 마세요 — 아이 나이, 예산, '원래 아끼는 편'·'원래 ○○를 좋아함' 같은 성격은 시트에 없으면 쓰지 않습니다. 대신 "나이를 모르니 보통 어린이 요금으로 어림한다", "이번엔 저녁에 더 쓰기로 했다"처럼 이번 상황의 판단으로 적으세요.
- personal_memory 를 쓴 결정에는 시트의 근거 ID(예: r003:pool)를 evidence_ids 에 그대로 적으세요. 일반 상식으로 고른 결정은 evidence_ids 를 비워 두고 general_sense 에 "시트에 근거 없음 — 일반 판단"이라고 밝히세요.
- 아무것도 하지 않기(객실에서 쉬기), 호텔 밖으로 나가기도 선택지입니다.
- 각 시간대마다 하나를 고르고, 버린 대안 1~3개와 버린 이유를 적으세요. main_driver 는 네 재료 중 이 선택을 가장 크게 움직인 것입니다.
- 이것은 실제 미래 행동의 예측이 아니라 '이 사람이라면 이렇게 할 법하다'는 조건부 판단입니다. 확신도(confidence)에 솔직하세요.
- 모든 글은 한국어, 1인칭("저", "우리")으로 씁니다. option_code 는 무대의 [코드] 를 그대로 씁니다. 목록에 없는 것을 고르면 OTHER 로 적고 choice 에 설명합니다."""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["self_intro", "decisions", "would_change_if", "unknowns_that_mattered", "one_line_quote"],
    "properties": {
        "self_intro": {"type": "string", "description": "이번 방문을 앞둔 나를 두 문장으로"},
        "decisions": {"type": "array", "minItems": 4, "maxItems": 4, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["slot", "option_code", "choice", "is_virtual_option", "est_cost_krw", "reasons", "evidence_ids", "main_driver", "alternatives", "confidence"],
            "properties": {
                "slot": {"type": "string"}, "option_code": {"type": "string"}, "choice": {"type": "string"}, "is_virtual_option": {"type": "boolean"},
                "est_cost_krw": {"type": ["integer", "null"], "description": "우리 일행 기준 어림 비용(원) · 모르면 null"},
                "reasons": {"type": "object", "additionalProperties": False, "required": ["personal_memory", "general_sense", "current_conditions", "external_info"],
                            "properties": {"personal_memory": {"type": "string"}, "general_sense": {"type": "string"}, "current_conditions": {"type": "string"}, "external_info": {"type": "string"}}},
                "evidence_ids": {"type": "array", "maxItems": 6, "items": {"type": "string"}, "description": "personal_memory 에 쓴 시트의 근거 ID · 없으면 빈 배열"},
                "main_driver": {"type": "string", "enum": ["personal_memory", "general_sense", "current_conditions", "external_info"]},
                "alternatives": {"type": "array", "maxItems": 3, "items": {"type": "object", "additionalProperties": False, "required": ["option_code", "why_not"], "properties": {"option_code": {"type": "string"}, "why_not": {"type": "string"}}}},
                "confidence": {"type": "string", "enum": ["높음", "보통", "낮음"]},
            }}},
        "would_change_if": {"type": "array", "maxItems": 4, "items": {"type": "string"}, "description": "무엇이 달라지면 선택이 바뀌는가"},
        "unknowns_that_mattered": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
        "one_line_quote": {"type": "string", "description": "누가 '왜 그렇게 하셨어요?' 라고 물으면 할 한 문장 대답"},
    },
}

FOLLOWUP_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["answer", "drivers"],
    "properties": {"answer": {"type": "string"}, "drivers": {"type": "array", "items": {"type": "string", "enum": ["personal_memory", "general_sense", "current_conditions", "external_info"]}}},
}


def user_prompt(sheet_text: str, stage_text: str, slots: list[str]) -> str:
    return f"""# 페르소나 시트(당신)
{sheet_text}

# 무대(오늘 워커힐에서 고를 수 있는 것)
{stage_text}

# 할 일
이번 1박 동안 네 시간대 — {' / '.join(slots)} — 에 무엇을 할지 하나씩 고르고 이유를 네 재료로 나눠 적으세요.
포함 혜택이 있으면 그것을 어떻게 쓸지도 정하세요. 끝에, 누가 "왜 그렇게 하셨어요?" 라고 물으면 할 한 문장을 적으세요."""


def call(system: str, prompt: str, schema: dict, model: str = MODEL, timeout: int = 240) -> dict:
    SANDBOX.mkdir(parents=True, exist_ok=True)
    cmd = ["claude", "-p", prompt, "--system-prompt", system, "--tools", "", "--no-session-persistence", "--model", model,
           "--output-format", "json", "--json-schema", json.dumps(schema, ensure_ascii=False)]
    t0 = time.time()
    last = None
    for attempt in range(2):
        r = subprocess.run(cmd, cwd=SANDBOX, capture_output=True, text=True, timeout=timeout)
        try:
            d = json.loads(r.stdout)
            out = d.get("structured_output")
            if out:
                return dict(output=out, cost_usd=d.get("total_cost_usd"), duration_s=round(time.time() - t0, 1), model=model, attempt=attempt + 1,
                            prompt_sha256=hashlib.sha256((system + "\n\n" + prompt).encode("utf-8")).hexdigest()[:16])
            last = d.get("result") or r.stderr[-500:]
        except json.JSONDecodeError:
            last = (r.stdout or r.stderr)[-500:]
    raise RuntimeError(f"구조화 출력 실패: {last}")


def ask_persona(sheet_text: str, stage_text: str, slots: list[str], model: str = MODEL) -> dict:
    return call(SYSTEM, user_prompt(sheet_text, stage_text, slots), SCHEMA, model)


def _plan_text(prior_output: dict, visit: dict | None) -> str:
    if visit:
        return "\n".join(f"- {a['start_hm']}~{a['end_hm'] or ''} {a['place_label']} · {a['label']} [{ {'llm_plan':'내가 정함','code_link':'사이를 이은 것','llm_event':'사건 뒤 다시 정함','operator':'운영자'}.get(a['decided_by'], a['decided_by'])}]" for a in visit["activities"])
    return json.dumps(prior_output["decisions"], ensure_ascii=False, indent=1)


def ask_followup(sheet_text: str, stage_text: str, prior_output: dict, question: str, model: str = MODEL, history: list | None = None, visit: dict | None = None, change: str | None = None, context: str | None = None, system: str | None = None) -> dict:
    """context · system 은 옵트인(evidence_ctx.decision_context · system_v2). 둘 다 없으면 프롬프트는 예전과 같다."""
    hist = "\n".join(f"Q. {h['question']}\nA. {h['answer']}" for h in (history or [])[-6:])
    prompt = f"""# 페르소나 시트(당신의 실제 기억 — 지난 실제 방문)
{sheet_text}

# 무대(이번 가상 방문)
{stage_text}

# 이번 가상 방문에서 이미 정한 것(실제 기억이 아니라 이번 방문의 계획 · 진행)
{_plan_text(prior_output, visit)}{(chr(10) + chr(10) + context) if context else ""}
{('# 이번 방문 중에 생긴 일(바뀐 상황 — 위 계획은 이 일을 겪은 뒤 다시 정한 것)' + chr(10) + change) if change else ''}
{('# 이미 나눈 이야기(이어서 답할 것)' + chr(10) + hist) if hist else ''}

# 질문
{question}
같은 사람으로서 3~5문장으로 답하고, 답에 쓰인 재료(personal_memory · general_sense · current_conditions · external_info)를 drivers 에 적으세요. 지난 실제 방문의 기억과 이번 방문에서 정한 것을 섞지 마세요."""
    return call(system or SYSTEM, prompt, FOLLOWUP_SCHEMA, model)


NEXT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["option_code", "choice", "is_virtual_option", "est_cost_krw", "reasons", "evidence_ids", "main_driver", "alternatives", "confidence", "later_plan"],
    "properties": {**SCHEMA["properties"]["decisions"]["items"]["properties"],
                   "later_plan": {"type": "string", "enum": ["keep", "change"], "description": "남은 계획을 그대로 두는가(keep) · 바꾸는가(change)"}},
}


def ask_next(sheet_text: str, stage_text: str, snapshot: dict, event: dict, model: str = MODEL) -> dict:
    """사건 재판단(③): 지금 시각 · 위치 · 한 것 · 남은 계획 · 사건을 주고 다음 행동 하나를 고르게 한다."""
    done = "\n".join(f"- {a['start_hm']}~{a['end_hm'] or ''} {a['place_label']} · {a['label']}" for a in snapshot["done"])
    remain = "\n".join(f"- {a['slot']}: {a['choice']} ({a['option_code']})" for a in snapshot["remaining"])
    prompt = f"""# 페르소나 시트(당신의 실제 기억)
{sheet_text}

# 무대(이번 가상 방문)
{stage_text}

# 지금 상황
- 지금 시각 {snapshot['now_hm']} · 위치 {snapshot['here_label']}
- 오늘 이미 한 것:
{done or '- (아직 없음)'}
- 남은 계획:
{remain or '- (없음)'}

# 방금 생긴 일
{event['text']}

# 할 일
이 일 때문에 '{snapshot['slot']}' 에 할 일을 다시 정하세요. 무대의 선택지 중 하나(없으면 OTHER)를 고르고 이유를 네 재료로 적으세요. 남은 계획을 그대로 둘지(keep) 바꿀지(change)도 적으세요. 새 소비를 억지로 만들지 말고, 객실에서 쉬는 것도 답이 될 수 있습니다."""
    return call(SYSTEM, prompt, NEXT_SCHEMA, model)
