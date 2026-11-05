# HILLINK 연구·기술 인계서

> **대상:** 다음 기수 담당자와 퍼실리테이터 · **작성:** 강경수 (2026-11-05)
> 이 문서의 파일 경로·상수·정책 이름은 제출 시점의 제품 코드에서 직접 확인했다.
> **보안:** 후기 원문과 비공개 검수 자료는 공개 저장소에 포함하지 않는다(10절).

이 문서는 제품을 실행하는 방법보다 **왜 이렇게 설계했고, 무엇을 검증했으며, 어떤 한계를 알고 있는지**를 넘기기 위한 것이다. 실행·복원 절차는 저장소 루트 [README](../../../README.md)와 [handover/RECOVERY.md](../../handover/RECOVERY.md)를 따른다.

---

## 0. 3분 요약

HILLINK는 실제 고객 후기에서 관측한 경험과 선택 근거를 바탕으로, **아직 일어나지 않은 워커힐 방문을 가상으로 실행하고**, 그 선택이 어떤 상품·주문·가상 매출로 이어지며 운영 조건을 바꾸면 무엇이 달라지는지 추적하는 시뮬레이터다. 실제 매출 예측기나 검증된 디지털 트윈이 아니다.

| 차원 | 하는 일 | 핵심 코드 |
|---|---|---|
| 1D 고객 이해 | 같은 작성자의 워커힐 후기·다른 호텔·식음·최근 글을 묶어 Fact(원문 구간 연결)와 성향 가설을 만든다 | `author_method_v4_1/` · `author_validation_v4_2/` · `tools/persona_pipeline.py` |
| 2D 연속 방문 | 시각·위치·끼니·허기·피로·동행·예약·행사 상태에서 가능한 행동을 만들고, 정책(규칙 / 선택적 LLM 검토 / V16 자율 LLM)이 고른 뒤 월드 계약으로 검증해 실행한다 | `autonomy_v1/agent_day.py` · `m4_runtime.py` · `autonomous_agent.py` |
| 3D 소비·운영 | 실제 실행된 SKU·수량을 같은 run의 L5 → L1 가상 원장으로 집계하고, 운영 전략 가설과 서버가 허용한 A/B만 비교한다 | `timeline/viewer/ledger_service.py` · `strategy_agent.py` · `strategy_agent_service.py` |

**2026-11-05 기준 상태(출처는 8절)**
- 라이브러리 45명 표시 · 실행 가능 28명 / 열람 전용 17명. 대표 문구 45명은 선정 원문 사례로 대조했고, blog42·blog43은 원문 연결 HOLD. **45명 전체의 의미·썸네일 사람 승인은 아님.**
- V16 실호출 검수 기록: 28명 · 완료 36방문 · 312판단(LIVE 301 / Replay 11) · 실패 시도 2건 보존. 이 문서를 쓰며 다시 실행하지 않았다.
- 과거 개발용 평가 수치(F1·Brier 등)는 **규칙 기반 v4 시절의 개발 자료 안 탐색 평가**이며, 현재 V16의 행동 예측 성능이 아니다.

---

## 1. 문제 정의가 바뀐 과정

| 시기 | 그때의 질문 | 드러난 한계 → 다음 선택 |
|---|---|---|
| 9월 | 후기에 적힌 방문 장소를 에이전트가 재현하는가 | 장소 일치만으로는 매장/포장, 예약, 결제, 선택 이유를 평가할 수 없었다. 검증기(운영 규칙)를 먼저 통과한 행동만 고르는 구조로 위반을 막았다 |
| 9월 말 ~ 10월 초 | 고객군이 어디서 얼마나 소비하는가 | 수요 규모·좌석·비투숙 배율 같은 가정이 매출을 크게 바꿨다. 확정·추정·미확인 값을 나누고, 운영 수치보다 근거 사슬에 집중하기로 했다 |
| 10월 중순 | 성향이 행동을 설명하는가 | 개발 자료에서 성향의 추가 설명력이 확인되지 않았다(5절 E0·E2). 후기 한 편으로는 지속 성향과 일시 조건을 가르기 어려워 **작성자 단위 프로파일링**으로 확대했다 |
| 10월 말 ~ 11월 | 새 행사·가격·상품 조건에서 같은 고객이 어떻게 행동하고 소비하는가 | 점수의 사후 설명으로는 부족했다. **선택 이전에** 상태·대안·기억·반례를 보고 고르게 하고, 그 선택을 소비·전략 입력까지 같은 run으로 잇는 구조(V16)로 옮겼다 |

설계 목표는 개인의 미래 행동을 맞혔다고 증명하는 것이 아니라, **근거가 있는 그럴듯한 선택을 재현하고 그 판단과 집계를 감사할 수 있게 만드는 것**이다. 실제 운영 효과 검증에는 POS·예약·수요·재고 같은 현장 자료와 별도 대조군이 필요하다.

---

## 2. 규칙 엔진 — 설계 근거와 한계

### 2-1. 왜 규칙 엔진부터 만들었나

1. **운영 규칙 위반을 구조적으로 막기 위해.** 에이전트는 매 턴 검증기를 통과한 행동만 후보로 받는다. 위반 0은 점수가 아니라 전제 조건이다(아무 데도 가지 않아도 위반은 0이다).
2. **설명이 계산과 일치하게 하기 위해.** 동결 정량 엔진은 점수를 `특성 수준 × 선택지 속성 × 역할 계수` 항의 합으로 만들고 항마다 근거 Fact ID를 붙인다. 이유 문장은 실제로 계산에 들어간 항에서만 만든다([engine.py](../../timeline/experiments/persona_live/operator_choice/operator_world_v1/engine.py) 머리말).
3. **재현성과 무과금 대조군.** 같은 시드면 같은 하루가 나오고 호출 비용이 없다. 이후 LLM 정책을 평가할 때 비교 기준이 된다.

### 2-2. 계수를 어떻게 다뤘나

- `W`(novelty 2.0 · food 3.0 · cost 2.0 · rest 2.0 …)는 **초기 가설**이다. 엔진 주석에 "특정 고객·조건의 결과에 맞춰 조정하지 않음"이 명시돼 있다. 점수는 효용 지표이지 확률·지불 의사·학습된 계수가 아니다.
- 비용 항은 개인의 가격 회피 성향이 아니라 공통 상황 판단(`COST_ATTENTION 0.5`, 5만 원 단위)이다.
- 정책 스위치(`fact_share` · `lookahead` · `lookahead_depth 2` 등)는 모든 고객에게 같은 규칙으로 적용하고, 비교 실행은 정책을 바꿔 같은 입력으로 다시 돌린다.
- 이 구조의 이론적 배경은 **효용 기반 이산 선택**(McFadden 1974, Train 2009 — 중간보고서·최종보고서 인용)이다. 다만 HILLINK가 로짓 계수를 추정해 확정한 것은 과거 v4 연구(5절 E0)뿐이며, 현재 엔진의 `W`는 추정치가 아니다.

### 2-3. 한 번의 결정 (규칙 실행기)

[agent_day.py](../../timeline/experiments/persona_live/operator_choice/autonomy_v1/agent_day.py) 머리말의 7단계: ① 상태 읽기 ② 욕구·의무 판단(체크인·체크아웃·끼니 창·피로) ③ 그 시각 가능한 후보 생성 ④ 월드 규칙 검증(영업시간·투숙객/성인 전용·계절·행사·운영자 변경) ⑤ 개인 평가(엔진 지원 상품은 동결 정량 엔진, 그 밖은 계획기 성향 가중치·시드 고정) ⑥ 실행·상태 갱신 ⑦ 운영 변경 뒤 결정부터 새 월드로 재판단.

현재 실행 경로는 [m4_runtime.py](../../timeline/experiments/persona_live/operator_choice/autonomy_v1/m4_runtime.py)(`m4-live-v2-shared-world`)가 공유 월드와 시간순 결정 큐로 묶는다. 설정값에 `capacity_and_queues_supported: False`가 명시돼 있다 — **좌석·대기·정원 경쟁은 모델링하지 않는다**(프로젝트 범위 결정).

[docs/walkerhill-guest-state-machine.md](../walkerhill-guest-state-machine.md)는 2026-09-20 작성된 **상태 모델 설계 초안**(transition/guard 미정의)이다. 초기 월드 설계의 참고 자료이지 현재 런타임이 아니다.

### 2-4. 알려진 한계

- 성향 항의 기여가 작아, 고른 후보에 개인 근거가 붙지 않는 결정이 생긴다(아래 선택적 검토의 `NO_PERSONAL_BASIS` 트리거가 이를 감지하려고 만든 것).
- 엔진이 지원하지 않는 활동(점심·카페·라운지 등)은 계획기의 성향 가중치로 고르며 정량 근거가 약하다.
- 과거 v4에서 예약 가점이 업장 단위로 붙어 포장 후보에도 적용되던 구조 한계가 기록돼 있다(10/18 읽기 점검). 현재 엔진에서의 재확인은 하지 않았다.

---

## 3. LLM 배치 — 세 정책을 반드시 구분

| 정책 | 최종 행동을 누가 고르나 | LLM의 역할 | 주의 |
|---|---|---|---|
| **규칙** (`judgment_mode=rules`) | 규칙 엔진 | 호출 없음 | 대조군. 점수는 선택 확률이 아님 |
| **선택적 LLM 검토** `SELECTIVE_V12Z_NATIVE_V1` / `CLAUDE_HYBRID_REVIEW_V1` | 규칙이 먼저 고르고, 감지된 결정만 LLM이 검토 | 트리거된 결정에서 같은 후보를 다시 판단. `adopt` 모드에서 확신도 ≥ 0.6이고 근거 유형(후기 근거·상황·업장 정보)이 있을 때만 LLM 선택 채택, 아니면 규칙 유지. `shadow` 모드는 기록만 | 호출되지 않은 결정을 LLM 성과로 세지 않음. 엇갈림은 둘 다 기록해 따로 채점 |
| **V16 자율 선택** `LLM_AUTONOMOUS_CUSTOMER_V16` | **LLM** | 상태·기억·반례·가능한 행동·메뉴(SKU·가격)를 보고 3~5개 계획을 비교해 하나를 선택, 메뉴 수량까지 결정 | M4/C01 계약은 **검증만** 하고 점수로 재정렬하지 않음 |

### 3-1. 선택적 검토의 트리거 ([hybrid_review.py](../../timeline/experiments/persona_live/operator_choice/autonomy_v1/hybrid_review.py))

`NEAR_TIE`(상위 두 후보 점수 차 < 0.35) · `COST_ABSTAIN`(가격 미확인으로 금전 항 제외) · `REPEAT_VENUE` · `REPEAT_MENU` · `NO_PERSONAL_BASIS`(고른 후보에 개인 근거 항 없음) · `PRICE_GAP`(가격 민감 근거가 있는 고객이 최저가의 2배 이상 선택). 그 밖의 결정은 호출 0이다. 이 설계는 "계수로 재기 자연스러운 판단은 규칙이, 근거가 부족하거나 추론이 필요한 순간만 LLM이"라는 10/29 하이브리드 원칙을 구현한 것이다.

### 3-2. V16 계약 ([autonomous_agent.py](../../timeline/experiments/persona_live/operator_choice/autonomy_v1/autonomous_agent.py))

- `configuration()`: `selector='LLM_FINAL_INTENT'` · `validator='M4_C01_CONTRACTS'` · `fallback='EXECUTION_HOLD_NO_SCORED_SUBSTITUTION'` · `max_replans=1` · 기억 정책 `LLM_VISIT_MEMORY_V3` · 월드 `AUTONOMOUS_WORLD_CONTRACTS_V4` · 끼니 `AUTONOMOUS_MEAL_EXPERIENCE_V5`.
- 출력 스키마: `plans`(1~5개) + `selected_index`. 계획마다 `action_id` · `items[{sku_id, quantity 1~32}]` · `order_total_krw` · `supporting_fact_ids` · `counterevidence_fact_ids` · `assumptions` · `pending_intentions` · `current_need_assessment` · `meal_assessment` 등.
- 검증(`validate_plan`): 검증된 월드 밖 행동, 입력에 없거나 인용 불가한 Fact, 일정 충돌, 체크인 전 객실 이용, 활동의 고정 주문 변경, 식사 무주문, 최근 같은 업장 재식사, SKU 중복·미판매·수량 범위, 주문 총액 불일치, 포함 혜택·가격 계약 위반을 거절한다.
- 실패 흐름(`step`): 검증 거절 → 거절 사유를 붙여 **한 번만** 재계획 → 다시 실패하면 `REPLAN_VALIDATION_EXHAUSTED`. provider 실패(`ProviderUnavailable`)는 즉시 `EXECUTION_HOLD`. 후보가 없으면 `NO_VALIDATED_ACTIONS`. **어떤 경우에도 규칙 점수로 몰래 대체하지 않는다**(`selection_owner=None`, `price_score_rerank=False`).
- 로그: 후보 수와 ID, 제외 사유, `input_sha256`, `implementation_sha256`(소스 해시), `profile_evidence_sha256`, 시도별 provider 기록, 선택 계획, 실행 전후 상태.
- 시스템 지시에 "점수 엔진의 추천은 없습니다", "기록된 끼니가 없다는 것을 굶었다는 사실로 해석하지 마세요", "null 가격은 미확인이며 무료가 아닙니다" 등 과잉 해석 금지가 들어 있다.

이전 연구 문서나 `agent_day.py`의 옛 주석에 나오는 규칙 폴백 설명과 V16 동작이 다르면 **현행 코드가 우선**이다.

### 3-3. 왜 V16으로 옮겼나 (설계 기록)

규칙 엔진은 위반이 없고 재현 가능했지만, 개발 평가에서 성향이 행동을 설명하는 몫을 입증하지 못했고(5절), 연속된 하루에서 이전 식사·기억·남은 일정·메뉴 수량을 함께 판단하는 데 한계가 있었다. 선택적 검토는 규칙의 불확실 지점만 보완한다. V16은 **선택은 LLM이, 실행 가능성은 기존 월드 계약이** 맡도록 역할을 나눈 것이다. 이 전환이 행동 예측 정확도를 높였다는 독립 평가는 **없다**.

### 3-4. LIVE / Replay / 규칙의 증거 수준 ([agent_provider.py](../../timeline/experiments/persona_live/operator_choice/autonomy_v1/agent_provider.py) · [visit_execution.py](../../timeline/viewer/visit_execution.py))

| 실행 출처 | 뜻 | 성능 근거로 쓸 수 있나 |
|---|---|---|
| `LIVE_RESPONSES` | 실제 API 응답 | 그 입력에 대한 새 판단 |
| `CACHE_REPLAY` | 입력 해시가 정확히 같은 과거 실제 응답을 재생(무과금). 원본 출처가 `LIVE_RESPONSES`가 아니면 거절 | **새 판단이 아님** |
| `rules` | 규칙 계산 | LLM 판단 아님 |
| `REPLAY_MISS` · `EXECUTION_HOLD` | 결과 없음 · 실패 | 성공으로 처리 금지 |

- 예산: 모든 작업자가 잠금된 공유 원장(`RESPONSES_AGENT_BUDGET_V1`)을 쓰고, 요청마다 최악 비용을 먼저 예약한다. 상한은 코드상 최대 2,500회 · US$20이며 명시 승인 없이는 실행되지 않는다(`EXPLICIT_APPROVED_BUDGET_REQUIRED`).
- LIVE 시작 조건(`live_status`): 승인 참조값, 외부 호출 허용, **기존** 공유 원장 파일, 승인 한도. 원장을 새로 만들어 호출하지 않는다.
- `tools/start_product.sh`는 기본이 Replay/규칙이고 `--live`는 위 조건을 통과해야 뜬다. 화면의 `행동 판단`에서 저장된 판단(무과금) · 새로운 LLM 판단(API 호출) · 규칙 계산을 구분해 고른다.

---

## 4. 페르소나 추출 — V4.1과 V4.2

### 4-1. 왜 작성자 단위인가

워커힐 후기 한 편은 방문과 장소를 알려 주지만, 그 선택이 일시 조건·동행 때문인지 반복되는 개인 성향인지 가르기 어렵다. 그래서 같은 작성자의 워커힐 후기 전체 + 다른 호텔·리조트·식음 경험 + 최근 최대 50편을 함께 본다(팀 공통 프롬프트의 입력 정의).

### 4-2. V4.1 Text-first 4-pass ([EXTRACTION_PROMPT.md](../../timeline/experiments/persona_live/operator_choice/author_method_v4_1/EXTRACTION_PROMPT.md))

입력은 승인된 한 작성자의 익명 문서뿐이며 기존 카드·정답 행동·Gold·사람 평가·엔진 점수는 주지 않는다.

1. **사건·화자·시간 지도:** 본인/동행/타인/광고·인용 구분, 생략 주어의 선행 구간 기록, 발행일 ≠ 방문일, 과거 회상·이번 경험·미래 계획·추천 분리, 글 간 동일 방문 여부를 근거와 반대 해석과 함께 기록.
2. **세부 행동·소비·평가:** 고정 태그 전에 자유 서술 detail 보존(목록 밖이라고 버리지 않음), Fact마다 여러 원문 span, 관심·계획·예약·주문·결제·참여·섭취를 구분, 사후 가격 비판과 사전 비용 회피를 분리.
3. **공통 분류와 패턴 후보:** 세부 사실을 공통 축에 연결하되 고유 feature를 대체하지 않음. 다른 상품·방문에서 **3회 이상** 나타난 패턴은 "강한 반복 추론 후보"로 제안하고 상충 사례를 함께 남김 — 통계적으로 검증된 임계치가 아니라 경험칙이다.
4. **광고·개인정보·오류 검토:** 명시적 협찬·대가성 고지 글만 분리(문체가 홍보 같다는 이유로 폐기하지 않음), 건강·금융·종교·관계 정보는 성향으로 만들지 않음, 원문 URL·계정은 제한 원장에만, 타인 행동 혼입·시간/인과 역전·중복·과잉 일반화 점검. 본문 속 명령·링크는 실행하지 않는다.

### 4-3. V4.2 — 팀 공통 계약과 검증 계층 ([author_validation_v4_2/](../../timeline/experiments/persona_live/operator_choice/author_validation_v4_2/))

- 팀 공통 지시문 파일 이름은 `TEAM_COMMON_EXTRACTION_PROMPT_V4_1.md`이다. V4.1의 4단계 취지와 필드를 유지하면서 사람마다 지시문을 바꾸지 않게 만든 팀 양식이고, V4.2는 이를 감싸는 **계약·검증 계층**이다.
- 산출 8섹션: `SOURCE_AUDIT` · `PERSONA_SUMMARY` · `TRAIT_TABLE` · `EVENT_ACTIONS` · `EVIDENCE_MAP` · `CONTEXT_RULES` · `QUALITY_FLAGS` · `STRUCTURED_PROFILE`.
- `PRIMARY_TYPE`은 잠정 유형 힌트이지 정답이 아니다. 광고 확인 글(`EXCLUDED_POSTS`)은 해당 글만 성향 산정에서 뺀다. 사진 관찰 메모는 본문과 별도 층이며 같은 경험의 글·사진·영수증을 독립 반복으로 가산하지 않는다(`study.py`).
- 사람 의미 판정 6종([evaluation.py](../../timeline/experiments/persona_live/operator_choice/author_validation_v4_2/evaluation.py)): `supported` · `partial` · `unsupported` · `wrong_actor` · `wrong_time_or_stage` · `overgeneralized`. 구조 검증 통과는 의미 승인이 아니다.
- V4.1 native 실행과 V4.2 팀 작성자 프롬프트는 입력 단위·처치가 달라 **같은 실험으로 합쳐 보고하지 않는다.**

### 4-4. 누출 방지와 새 작성자 추가

- 추출 요청에는 개발 라벨·어휘 후보·옛 카드·행동 선택·평가자 의견을 넣지 않는다(`study.py` 머리말). 새 작성자는 `author_role='holdout_new_author'`로 준비한다.
- [tools/persona_pipeline.py](../../tools/persona_pipeline.py)는 `prepare → (승인된 외부 LLM에서 별도 추출) → import → 사람 approve → register → verify` 인터페이스이며 **스스로 LLM을 호출하지 않는다**("External inference is never run by this tool"). 등록은 내장 등록부 17명에 새 고객을 더한 **격리 등록부**를 만들 뿐 기존 28명을 덮어쓰지 않는다. 절차는 [handover/persona/README.md](../../handover/persona/README.md).
- 예제 A14는 저장된 초안의 재수입이며 모델 실행 이력이 없어 새 LLM 추출로 인증하지 않는다. 사람 검수 대기라 `approve`·`register`는 차단 상태다.

---

## 5. 평가 지표와 과거 실험의 한계

### 5-1. 지표가 재는 것

| 분류 | 지표 | 의미 | 해석 주의 |
|---|---|---|---|
| 동선 재현 | 장소 recall / precision / F1 | 후기에 적힌 방문 장소와 모델 방문 장소의 겹침 | 매장/포장, 시각, 횟수, 이유의 적합성은 보장하지 않음. '적히지 않은 곳 = 미방문'이라는 정답 정의에 의존 |
| 분포 예측 | Brier score (낮을수록 좋음) | 장소별 방문 확률과 관측의 제곱 오차 | 반드시 같은 조건의 인기도 기준선과 비교. 반복 횟수 K가 다르면 값이 달라짐(K 12와 k 5를 한 표에 두지 않음) |
| 정보 기여 | 제거·켜기 실험(ablation) | 예약·포함 끼니·성향·LLM을 빼거나 켰을 때의 짝 차이(± 표준오차) | 선택이 바뀐 것과 관측에 더 가까워진 것은 다름. 정답 정의 3종에서 방향이 바뀔 수 있음 |
| 추출 의미 품질 | supported / partial / unsupported 등 | 원문과 화자·시점·단계·일반화 일치 | 스키마 PASS ≠ 의미 PASS |
| 엔진 안전성 | 계약 거절·HOLD·위반 | 영업·자격·시간·SKU·중복 식사 | 위반 0이 고객다운 행동의 증명은 아님 |
| 실행 계보 | LIVE / Replay / 입력 SHA | 실제 호출과 저장 응답 구분 | Replay 일치는 모델 품질 평가가 아님 |
| 거래 | L5 → L1 원장 일치 | 영수증 = L4 = L3 = L2 = L1, 무료·포함·미확인 금액 구분 | 가상 거래 합계 ≠ 실제 결제·매출 |
| 운영 KPI(연구) | OCC · ADR · RevPAR · TRevPAR | 객실 가동률·평균 요금 등 | 원장 정의·객실료 미확인·모델 가정에 민감 |
| 운영 비교 | 목표 업장 Δ · 호텔 L1 Δ · 유입/이탈/잠식 | 같은 조건에서 조절 변수만 바꾼 차이 | 호텔 안 업장 간 이동은 호텔 전체 증분이 아닐 수 있음. 인과 주장 금지 |

### 5-2. 과거 연구 스냅샷 — 규칙 기반 v4 시절, 현재 V16 성능 아님

| 실험 | 자료·조건 | 결과 | 출처 |
|---|---|---|---|
| E0 v4 재맞춤 (9/29) | 개발용 46편(48체류) · 후기 하나씩 빼기 46폴드 | F1 기준 선택: F1 **0.607**(v2 0.506 · v3 0.524) · Brier 0.154 / Brier 기준 선택: Brier **0.125** vs 인기도 기준선 **0.107**. **성향 계수 `lam_trait`는 모든 폴드에서 0** | [timeline/fit_v4_result.json](../../timeline/fit_v4_result.json) (직접 대조) |
| E0 봉인 3 (9/29, 1회) | 시험용 11편 | v4 F1 0.526 · Brier 0.157(v2 0.240) · v4+인기도 섞기 **0.1177** vs 인기도 **0.1178**(동률, 4승 7패). 채점 뒤 개발용으로 풀림 → **이후 독립 평가 자료 없음** | 팀 연구 기록 |
| E1 조건부 인기도 (9/29) | 개발용 59체류 교차검증 | 인기도에 예약·포함 끼니·투숙·건물·클럽·아이를 붙인 표 0.094 ≈ v4 섞기(차이 0.002). 평상시 분포에서 에이전트가 더하는 정보는 거의 없고, 에이전트의 몫은 **개인 동선·순서와 변칙 상황** | 팀 연구 기록 |
| E2 성향 켜기 (10/16) | 59체류 × K 12 | 성향을 켜면 행동은 바뀌지만 후기와 더 맞지 않았고, 정답 정의에 따라 방향이 바뀜 → "추가 설명력 미확정"(성향이 무의미하다는 뜻 아님) | 같은 기록 · `static/factor_eval.json` |
| E3 정보 제거 (10/16) | 59체류 × K 12 | 예약 정보 제거 시 정답 정의 3종 **모두 악화**(Brier 0.1201 → 0.1356). 포함 끼니 제거는 구분 안 됨. 예약은 후기에서 사후 복원한 사실이라 실제 예약 기록으로 같은 기여가 유지되는지는 미확인 | 같은 기록 |
| E5 LLM 선택 파일럿 (10/16) | 같은 후보에서 고르는 주체만 LLM으로, k 5 | 규칙 대비 짝 차이 +0.0078 ± 0.0071 → 구분 안 됨. k 5 하네스 안의 비교로만 인용 | 팀 연구 기록 |

**정리:** 과거 실험이 일관되게 말하는 것은 "예약 같은 **사실**이 재현을 좌우하고, 후기에서 뽑은 성향의 추가 설명력은 개발 자료에서 확인되지 않았다"이다. 모두 개발 자료 안의 탐색 평가다. 이 수치를 V16이나 45명 라이브러리의 미래 행동 정확도로 옮기지 않는다.

### 5-3. 현재 제품 QA 스냅샷 — 행동 예측 성능이 아니라 실행·계약 검수

| 항목 | 값 | 출처 |
|---|---|---|
| V16 실호출 검수 | 28명 · 완료 36방문 · 312판단(LIVE 301 / Replay 11) · 실패 시도 2건(HTTP 500 → HOLD 보존 후 복구) · LLM 독립 평가 36회(**사람 승인 아님**) | [previous-llm/coverage-and-budget.json](../../handover/profile45_review/previous-llm/coverage-and-budget.json) · `submission-QA.md.gz` |
| 할인 처리군 비교 | 3쌍 모두 할인 대상 SKU가 양쪽에서 선택되지 않음. 호텔 총액 차이 +290,000원은 다른 선택의 차이로 기록하고 **할인 효과로 귀속하지 않음** | 같은 보고 |
| 비용 원장 | 그 보고 시점 1,933 / 2,500회, 보수적 추정 US$11.37 / 20(청구서 아님). 11/5 LIVE 사전 점검 시점 1,938회 · 신규 호출 0 | 같은 파일 · `concise45` 사전 점검 기록 |
| 회귀 (11/5) | Python 뷰어 723 PASS · **기존 12 FAIL** · 1 SKIP(신규 실패 0) · Node 249 PASS | [concise45_final/검수보고서.md](../../handover/profile45_review/concise45_final/검수보고서.md) |
| 프로필 45명 | 대표 문구 45명 선정 원문 대조 · blog42·43 원문 연결 HOLD · 전체 의미·썸네일 사람 승인 미완료 | 같은 보고서 · [45-signature-final.csv](../../handover/profile45_review/concise45_final/45-signature-final.csv) |
| 전략 Replay | 정수/실수 JSON 직렬화 차이로 입력 해시·판단 ID 불일치(`REPLAY_MISS`) — 기존 결함, 새 A/B 효과 HOLD | [review-report.json](../../handover/profile45_review/review-report.json) |

남은 HOLD(V16 보고 기준): 후기 원문 의미·귀속과 약한 선호 전이, 구조화 Fact 연결 누락·연속 활동 병합에 따른 판단 경계 추적, 실제 동행 연령·접근 자격, 섭취량·휴식 적절성, 할인 인과효과, 슬기 789행 전수 의미 대조.

수치를 인용할 때는 **기준 SHA · 정책 버전 · 대상 고객/방문 · 입력 SHA · 평가 정의 · PASS/FAIL/HOLD · 출처 파일**을 함께 적는다.

---

## 6. 참고 문헌 — 무엇을 참고했고 어디에 닿았나

**라벨:** `CITED_IN_FINAL_REPORT`(11/6 최종보고서 참고문헌) · `CITED_IN_INTERIM_REPORT`(10/16 중간보고서) · `MENTORING_1026_LIST`(10/26 멘토링 자료에 정리한 참고문헌) · `ENGINEERING_DESIGN`(코드 속 일반 공학 원칙). 어느 경우에도 **논문 저자의 코드나 실험을 재현·이식했다는 뜻이 아니다.**

> 논문 5편의 실재와 서지는 2026-11-05에 다시 확인했다. 최종보고서는 R1·R2와 Train(2009), Ng & Russell(2000)을 인용한다.

| | 문헌 | 참고한 관점 | HILLINK에서 닿은 곳 | 하지 않은 것 |
|---|---|---|---|---|
| R1 | Park et al. (2023), *Generative Agents: Interactive Simulacra of Human Behavior*, UIST 2023 — `CITED_IN_FINAL_REPORT` | 기억·계획·회고를 이어 하루의 연속 행동을 만드는 틀 | V16의 방문 기억(`LLM_VISIT_MEMORY_V3`, `agent_experience.py`) · 미실행 의도(`pending_intentions`) · 재평가 문맥. 중간보고서 단계에서는 "하루를 사는 에이전트의 틀"만 참고하고 행동은 검증기+점수로 계산 | 25명 사회 상호작용·회고 트리 재현 안 함 |
| R2 | Park et al., *LLM Agents Grounded in Self-Reports Enable General-Purpose Simulation of Individuals* (arXiv:2411.10109, 초판 제목 *Generative Agent Simulations of 1,000 People*) — `CITED_IN_FINAL_REPORT` | 개인의 자기 보고(인터뷰·설문)로 개인 에이전트를 만들고 held-out 응답으로 평가, 본인의 재검사 일관성으로 정규화 | 한 편이 아닌 **작성자 전체 글**로 프로필을 만드는 결정, 새 작성자 holdout 역할(`study.py`) | 2시간 인터뷰·GSS·Big Five 평가나 정규화 정확도를 HILLINK에 이전하지 않음. 블로그는 자기 보고 인터뷰와 다른 자료 |
| R3 | Li et al. (2025), *How Far are LLMs from Being Our Digital Twins? A Benchmark for Persona-Based Behavior Chain Simulation* (BehaviorChain), Findings of ACL 2025 — `MENTORING_1026_LIST` | 단발 응답이 아니라 이어지는 행동 사슬을 평가 | 하루 안의 연속 결정과 상태 전이(이전 식사·피로·남은 일정)를 결정 단위로 기록·검수하는 구조 | 벤치마크·점수 재현 안 함. HILLINK 자체 평가셋과 별개 |
| R4 | Huang et al. (2026), *AgentPersonaBench: Benchmarking Persona-Driven User Simulation* (arXiv:2610.04379, 2026-10-03 제출) — `MENTORING_1026_LIST` | 페르소나 성향이 말투가 아니라 **관측 가능한 행동**을 바꾸는지 검사 | 사후 대조 관점: "Fact ID가 출력에 있다 ≠ 그 Fact가 선택을 바꿨다", 성향 켜기·제거 실험(E2)의 해석. 10월 초 공개라 그 전 설계의 근거가 아님 | APB 실험 재현 안 함 |
| R5 | Wanyan et al. (2026), *Task-Aware Automated User Profile Generation for Recommendation Simulation Using Large Language Models* (APG4RecSim, arXiv:2605.13497) — `MENTORING_1026_LIST` | 시뮬레이터 성능과 별개로 **프로필 생성 품질**을 따로 평가(특성 후보 추출 → 병합 → 결정 단계 연결) | V4.2의 추출 품질 검증(의미 판정 6종)을 행동 평가와 분리한 구조, 향후 추출 방법 비교 과제 | 알고리즘·추천 지표(nDCG·RMSE) 구현 안 함 |
| — | Train (2009), *Discrete Choice Methods with Simulation* · McFadden (1974) — `CITED_IN_FINAL_REPORT` / `CITED_IN_INTERIM_REPORT` | 효용 점수에 비례한 확률 선택(로짓)과 계수 추정 | 과거 v4의 확률 선택(τ)과 계수 적합(5절 E0), 현재 엔진의 효용 항 구조 | 현재 `W`는 추정 계수가 아님 |
| — | Ng & Russell (2000), *Algorithms for Inverse Reinforcement Learning*, ICML — `CITED_IN_FINAL_REPORT` | 관측된 행동에서 보상(선호)을 거꾸로 추정하는 관점 | "관측 행동 → 선택 이유 역추적"이라는 연구 질문의 비유적 틀 | IRL 알고리즘 구현 안 함 |
| — | Brier (1950) · Grimm et al. (2020) ODD 프로토콜 — `CITED_IN_INTERIM_REPORT` | 확률 예측 점수 · 에이전트 모델 기술 표준 | Brier 평가, 고객·환경·규칙·가정·실험 조건을 나눠 기록하는 방식 | — |

링크: [R1](https://arxiv.org/abs/2304.03442) · [R1 DOI](https://doi.org/10.1145/3586183.3606763) · [R2](https://arxiv.org/abs/2411.10109) · [R3](https://aclanthology.org/2025.findings-acl.813/) · [R3 DOI](https://doi.org/10.18653/v1/2025.findings-acl.813) · [R4](https://arxiv.org/abs/2610.04379) · [R5](https://arxiv.org/abs/2605.13497) · [Grimm ODD DOI](https://doi.org/10.18564/jasss.4259)

### 6-2. 설계에 참고한 소비자 행동·프로파일링 문헌

10/22 점수 체계·계수 재설계 검토에서 성향 항목의 개념 경계와 프로파일링 방식을 잡을 때 참고한 문헌이다. **설계 참고용이며, 엔진의 계수 값은 이 문헌으로 정하지 않았다.**

| 주제 | 문헌 | 참고한 내용 |
|---|---|---|
| 선택 모형 | McFadden (1974), Conditional logit analysis of qualitative choice behavior | 선택지 효용 = 속성 × 계수의 합이라는 엔진 형태 |
| 가격 판단 | Kalyanaram & Winer (1995), Empirical generalizations from reference price research, *Marketing Science* | 과거 지출을 기준으로 새 가격을 판단하는 준거가격·손실회피 |
| 가격 판단 | Lichtenstein, Ridgway & Netemeyer (1993), Price perceptions and consumer shopping behavior, *Journal of Marketing Research* | 가치 의식·가격 의식·할인 반응의 구분 |
| 이용 후 평가 | Oliver (1980), A cognitive model of the antecedents and consequences of satisfaction decisions, *Journal of Marketing Research* | 기대 대비 실제 경험에 따른 만족과 재선택 |
| 소비 → 행동 의도 | Zeithaml, Berry & Parasuraman (1996), The behavioral consequences of service quality, *Journal of Marketing* | 서비스 품질이 재방문·이탈·추가 지불 의도로 이어지는 관계 |
| 반복 vs 새 경험 | McAlister & Pessemier (1982), Variety seeking behavior, *Journal of Consumer Research* | 익숙한 곳과 새 경험을 한 축으로 보는 관점 |
| 의도와 실제 행동 | Tanford (2016), Antecedents and outcomes of hospitality loyalty: A meta-analysis, *Cornell Hospitality Quarterly* | 태도 → 의도 → 실제 행동으로 갈수록 효과가 줄어듦 — 후기의 재방문 의향을 실제 행동처럼 쓰지 않는 근거 |
| 소비 동기 | Vigneron & Johnson (2004), Measuring perceptions of brand luxury, *Journal of Brand Management* | 비싼 선택의 동기를 분류하는 어휘 |
| 텍스트 기반 성격 추정 | Fast & Funder (2008); Azucar, Marengo & Settanni (2018); Koutsoumpis 외 (2022), *Psychological Bulletin* | 글에서 성격을 추정하는 방법의 효과 크기 — 검토 후 엔진 입력으로 쓰지 않기로 함 |
| 프로파일 정리 틀 | AIO(활동·관심·의견) | 같은 작성자의 여러 글을 정리하는 목차 |

동행·방문 목적·그날의 상태는 성향이 아니라 방문 조건으로 분리해 다룬다.

BDI·POMDP·강화학습 같은 이론을 구현 근거로 사후에 덧붙이지 않는다. 논문의 지표 이름이 같아도 문제와 자료가 다르면 같은 점수로 취급하지 않는다.

---

## 7. 소비 원장과 운영 전략 — 제안과 실행의 경계

- **원장:** [ledger_service.py](../../timeline/viewer/ledger_service.py)(`live-l5-v2`)가 실행된 영수증을 L4 → L1로 조립하고 `receipts_equal_L4_L3_L2_L1`을 확인한다. 외부 배달 같은 호텔 밖 지출은 L1에 넣지 않고 금액 미상으로 따로 표시한다.
- **전략 입력:** [strategy_agent_service.py](../../timeline/viewer/strategy_agent_service.py)는 서버가 발급한 run만 받는다("never accept client Fact/flow data"). run이 만료되면 `SERVER_RUN_EXPIRED_REEXECUTE_REQUIRED`, 원본 run이 다르면 `SOURCE_RUN_MISMATCH`.
- **전략 가설:** [strategy_agent.py](../../timeline/viewer/strategy_agent.py)(`LLM_OPERATOR_STRATEGY_V3`)는 6종(experience·food·benefit·space·convenience·value)으로 운영 가설을 낸다. Fact를 고치거나 구매를 만들거나 매출 증가를 추정하지 않으며, 미선택 이유는 `RECORDED_COMPARISON` / `HYPOTHESIS` / `NO_EVIDENCE`로 구분한다. 모델은 스스로 실행 가능한 개입을 승인할 수 없고, 서버가 검증한 실험 계약이 있을 때만 `AVAILABLE_NOT_RUN`, 없으면 `UNTESTED_HYPOTHESIS_ENGINE_CONNECTION_REQUIRED`다.
- **A/B 결과 해석:** 목표 업장 신규 유입, 기존 고객 주문 구성 변화, 다른 업장 감소, 할인 비용, 호텔 L1 차이를 나눠 본다. 변화 0, 실험 불가, Replay 실패, 근거 부족을 구분한다. 현장 POS·대조군 없는 값은 **가상 소비 변화**다.

---

## 8. 핵심 파일 길잡이 (경로는 `hillink/` 기준)

| 질문 | 파일 |
|---|---|
| 실행·복원 | 저장소 루트 `README.md` · `handover/RECOVERY.md` · `tools/start_product.sh` · `tools/bootstrap_data.py` |
| 동결 정량 엔진(효용 항) | `timeline/experiments/persona_live/operator_choice/operator_world_v1/engine.py` · `world.py` |
| 규칙 실행기·공유 월드 | `.../autonomy_v1/agent_day.py` · `m4_runtime.py` · `m4_context.py` |
| V16 자율 선택·기억 | `.../autonomy_v1/autonomous_agent.py` · `agent_experience.py` · `profile_context.py` |
| 월드·상품 계약 | `.../autonomy_v1/hotel_catalog.py` · `official_contracts.py` · `candidate_services.py` · `candidate_products.py` |
| 선택적 LLM 검토 | `.../autonomy_v1/hybrid_review.py` · `native_hybrid.py` |
| LLM 전송·예산·Replay | `.../autonomy_v1/agent_provider.py` · `timeline/viewer/visit_execution.py` |
| 페르소나 V4.1 | `.../author_method_v4_1/EXTRACTION_PROMPT.md` · `method.py` · `linking.py` · `quality.py` |
| 페르소나 V4.2 | `.../author_validation_v4_2/TEAM_COMMON_EXTRACTION_PROMPT_V4_1.md` · `team_contract.py` · `study.py` · `evaluation.py` |
| 새 작성자 추가 | `tools/persona_pipeline.py` · `handover/persona/README.md` |
| 원장 | `timeline/viewer/ledger_service.py` · `ledger_l5.py` |
| 운영 전략·A/B | `timeline/viewer/strategy_agent.py` · `strategy_agent_service.py` · `strategy_evidence.py` |
| 프로필 표시 | `timeline/viewer/static/library.js` · `static/profile_display_review.js` · `timeline/viewer/profile_display_review.py` · `handover/data/profile-display-review.json` |
| 과거 v4 연구 | `timeline/agent_v4.py` · `fit_v4.py` · `fit_v4_result.json` |
| 초기 상태 모델 초안 | `docs/walkerhill-guest-state-machine.md` |

---

## 9. 다음 기수 첫 주 제안

1. **재현부터:** 같은 코드·고객·날짜·시드·정책으로 A03 한 방문을 Replay로 실행하고, 후보 → Fact → 결정 → SKU·수량 → L5~L1 → 전략 입력이 같은 run으로 이어지는지 확인한다(11/5 재실행: run `413ea938…`, 판단 3개 `CACHE_REPLAY`, 합계 79,000원).
2. **의미 감사:** blog42·43 원문 연결, 45명 전체 의미 검수, 789행 독립 대조를 엔진 영향과 분리해 진행한다.
3. **독립 평가셋 복원:** 9/29 이후 독립 평가 자료가 없다. 작성자 단위로 새 시험용 후보를 먼저 봉인하고, 동일 사건 중복과 원문·정답 누출을 막은 뒤 한 번만 채점한다.
4. **정책 대조:** 규칙 vs 선택적 검토 vs V16을 같은 조건에서 비교하되 행동 타당성·계약 거절·HOLD·호출 비용·원장 일치를 따로 본다. 유료 호출은 운영 책임자 승인과 기존 원장 안에서만.
5. **현장 자료:** POS·예약·좌석·가격 자료가 확보되면 외적 타당성과 운영 효과를 검증할 수 있다(중간보고서 7절의 자료 요청 목록 참고).

---

## 10. 이 저장소에 포함된 자료와 포함하지 않은 자료

| 분류 | 위치 | 비고 |
|---|---|---|
| 후기 원문(공개 블로그 글)과 출처 링크 | `hillink/handover/data/profile-review-sources/` · `product-inputs.tar.gz` 안 고객별 `corpus.json` | 제품의 Fact 근거 대조용. 사진은 가져오지 않았다 |
| 실행 등록부·저장 응답 | `hillink/handover/data/`(`bundle.json` · `v16/` · `product_acceptance/` 등) | `tools/bootstrap_data.py`가 해시를 검사해 복원 |
| 워커힐 공식 메뉴·패키지 자료 | `hillink/handover/data/official/` · `product-inputs.tar.gz` 안 `official-sources/` | 가격·영업 계약의 출처 |
| 검수 기록 | `hillink/handover/profile45_review/` | 45명 문구 대조·화면 측정·V16 실호출 집계 |
| 이미지 | 생성 썸네일·아바타, `timeline/viewer/static/place_img/` | 후기 사진은 쓰지 않았다 |
| **포함하지 않음** | API 키(저장소 밖 `~/.config/hillink/openai.env`) · LLM 비용 원장 원본 | 테스트 코드의 키는 가짜 값. 원장은 집계 요약(`previous-llm/coverage-and-budget.json`)만 포함 |

---

## 11. 인수 체크리스트

- [ ] 45명 표시 / 28 실행 / 17 열람과 사람 의미 승인을 구분해 설명할 수 있다
- [ ] 상태 기계 초안과 현재 런타임, 선택적 검토와 V16 최종 선택을 구분할 수 있다
- [ ] Fact·사건·주문 단계와 같은 방문 중복 처리를 설명할 수 있다
- [ ] 화면에서 LIVE / Replay / 규칙을 구분하고 비용 원장·HOLD 경계를 안다
- [ ] L5 → L1의 무료·포함·실결제·미확인 금액과 가정·관측을 구분한다
- [ ] 과거 F1·Brier가 개발 자료 탐색 평가라는 것과 9/29 이후 독립 평가가 없다는 것을 안다
- [ ] 참고 문헌을 개념 참고로만 인용하고 성과 이전을 주장하지 않는다
- [ ] 키와 비용 원장은 저장소 밖에서 따로 인수한다
