# 설치·복원 및 핵심 기술 계약

저장소 루트의 README가 제품 시작 안내입니다. 현재 제품은 `hillink/` 하나에 있습니다. 루트에 보존된 기존 팀 파일을 복사하거나 조합하지 않습니다. 아래 명령은 `hillink/`에서 실행합니다.

## 실행과 데이터

Python 3.11 가상환경에 `requirements-dev.txt`를 설치한 뒤 `bash tools/start_product.sh`로 시작합니다. 기본 주소는 `http://127.0.0.1:8994/`이며 `HILLINK_PORT`로 변경합니다. 외부 API 호출은 기본 차단됩니다.

`tools/bootstrap_data.py --json`이 `handover/data/bundle.json`의 SHA를 확인하고 내장 자료를 사용자 캐시에 복원합니다. 빈 캐시 재검증은 Git 밖의 새 경로를 `HILLINK_DATA_HOME`에 지정합니다. 특정 개발자의 폴더를 전달받을 필요가 없습니다. 복원된 `.local.json`은 파생 파일이며 직접 수정하거나 커밋하지 않습니다. 캐시를 재구성하려면 새 캐시 경로를 사용합니다.

기본 시작 명령은 내장 표시 검수 자료의 고객 ID·원문 SHA·방문 ID를 확인하고 승인된 범위의 목록 문구를 적용합니다. `handover/data/profile-display-review.json`의 수정은 표시 전용이며 엔진 Fact·성향·사람 의미 승인·썸네일 승인을 바꾸지 않습니다. 원문이 변조되거나 고객 연결이 맞지 않으면 복원을 중단합니다.

자료는 **비공개 저장소의 승인된 인수자 내부 사용** 범위입니다. 후기 원문·사진·공식 메뉴는 공개 재배포 권한이 확인된 자료가 아닙니다. 저장소를 공개로 전환하거나 외부에 재배포하기 전에 자료별 권한을 별도로 확인해야 합니다. 새 인수자는 저장소 소유자로부터 비공개 저장소 열람 권한을 받아 동일한 코드·자료를 clone합니다.

## 디렉터리와 연결 구조

| 위치 | 역할 |
|---|---|
| `tools/start_product.sh` | 유일한 표준 서버 시작 명령, 자료 복원·Replay 준비·실호출 사전 확인 |
| `timeline/viewer/app.py` | 로컬 HTTP 서버와 방문·원장·전략 API |
| `timeline/viewer/static/` | 기존 고객 라이브러리·조건·지도·행동근거·매출·운영 전략 화면 |
| `timeline/viewer/visit_execution.py`, `visit_run.py` | 규칙/Replay/LIVE 구분과 연속 방문 실행 |
| `timeline/experiments/persona_live/operator_choice/autonomy_v1/` | 현재 행동 엔진, V16 판단·운영 규칙·상품 계약 |
| `timeline/viewer/ledger_service.py`, `ledger_l5.py` | 동일 run의 SKU·수량·결제 및 L5~L1 집계 |
| `timeline/viewer/strategy_agent_service.py` | 해당 run의 실제 선택을 사용하는 개인·집단 전략과 A/B 계약 |
| `handover/data/` | 고객 입력·원문·공식 자료·원 응답 Replay와 단일 데이터 manifest |
| `tools/persona_pipeline.py` | 신규 페르소나 준비·수입·사람 승인·격리 등록·검증 |
| `timeline/viewer/tests/` | 유지한 회귀 코드와 fixture |

방문 요청은 `m4_c01`·`C01_HOTEL_CATALOG_V1`·`LLM_AUTONOMOUS_CUSTOMER_V16` 계약으로 판단을 실행합니다. 모델 선택 이후 영업시간·이동·예약·자격·상품 조건을 검증하고 실제 채택된 행동만 주문·원장으로 연결합니다. 행동근거 ④와 매출·운영 전략은 같은 run을 사용합니다. 내부 모듈의 과거 버전 이름은 import 호환성을 위한 것이며 사용자가 여러 엔진이나 추출기를 조립하지 않습니다.

Replay는 모델·설정·전체 입력이 일치하는 원 응답만 이용합니다. `REPLAY_MISS`는 차단이며 규칙이나 실호출로 자동 전환하지 않습니다. `CACHE_REPLAY`와 `LIVE_RESPONSES`, 모델 판단과 사람 의미 승인을 구분합니다.

## API 키와 승인된 실호출

키는 `OPENAI_API_KEY` 환경변수 또는 권한600의 `~/.config/hillink/openai.env`로 공급합니다. 키·인증정보·개인 비용 원장은 Git에 포함하지 않습니다. 모델과 추론 설정은 `HILLINK_AGENT_MODEL`, `HILLINK_AGENT_EFFORT`이며 가격 등록은 `agent_provider.py`를 따릅니다.

승인된 사용자는 운영 책임자로부터 **기존 누적 비용 원장과 유효한 승인 범위**를 접근 통제된 경로로 받아 아래처럼 실행합니다. 새 빈 원장으로 누적 한도를 초기화하지 않습니다.

```bash
HILLINK_AGENT_BUDGET_FILE=/absolute/private/existing/usage.private.json \
HILLINK_AGENT_MAX_CALLS=2500 HILLINK_AGENT_MAX_USD=20 \
HILLINK_LIVE_APPROVAL_REFERENCE='실제로 승인된 실행 범위' \
bash tools/start_product.sh --live
```

실행기는 기존 원장의 승인 확장·잔여 호출·잔여 비용을 검사합니다. 서버 시작만으로 API를 호출하지 않습니다. 방문에서 ‘새로운 LLM 판단 (API 호출)’을 선택해야 호출하며, 비활성 서버는 사용 불가를 표시합니다. 규칙과 Replay에는 개인 키·원장이 필요 없습니다.

## 최소 확인

1. 라이브러리에서 A03 / No.0003을 선택합니다. 당일 방문, 2026-11-09, 오후14:30, 날씨·행사 없음, 동일 입력 재현 시드62, ‘저장된 LLM 판단 (무과금)’으로 실행합니다.
2. 지도·수동 재생·RPG 설명에서 행동근거 ④로 이동해 선택 전 판단·대안·Fact·운영 검증을 확인합니다. 원장의 SKU·수량·금액 및 run ID가 같아야 합니다.
3. 운영 전략에서 같은 고객의 실제 선택이 입력으로 표시되는지 확인합니다. 전략 Replay 응답이 없으면 HOLD가 정상이며 효과를 생성하지 않습니다.
4. 검증 명령은 다음과 같습니다. 전체 회귀에는 아래 알려진 실패가 남아 있습니다.

```bash
PYTHONPATH=tools/offline_test_guard .venv/bin/python -m pytest -q timeline/viewer/tests/test_visit_execution.py timeline/viewer/tests/test_http_audit_boundary.py timeline/viewer/tests/test_strategy_agent_service.py
node --test timeline/viewer/tests/visit_execution.test.cjs timeline/viewer/tests/situation_ui.test.cjs
```

전체 회귀 명령: `PYTHONPATH=tools/offline_test_guard .venv/bin/python -m pytest -q timeline/viewer/tests`, `node --test timeline/viewer/tests/*.test.cjs`. 입력 누락 SKIP은 PASS가 아닙니다. 원장 금액과 봉인 SHA를 단순히 현재 값으로 바꾸어 실패를 지우지 않습니다.

## 지원 범위와 남은 결함

- 개인·집단 전략은 방문의 실제 선택과 소비를 입력으로 받고, 유효한 상품·가격·시간 개입을 A/B 재실행할 수 있습니다. 제안, 가상 실행 차이, 실제 호텔의 인과효과는 별개입니다.
- 저장된 A03 전략은 `RECOMMENDATION_HOLD`입니다. 일반 전략 API와 별도 평가용 입력 범위가 달라 저장 전략 Replay는 `REPLAY_MISS`가 남습니다. 같은 run의 전략 입력 연결은 지원하지만 이 사례의 새 A/B 성과는 검증되지 않았습니다.
- 기존 Python 실패11개: Fact ID 투영1, 과거 방문 fixture6, 과거 원장 합계1, M4 연구 거래 fixture1, 봉인 OPX 계약2입니다. 현재 원장 불변식과 과거 기대값/봉인 계약을 구분해야 합니다. 과거 입력 누락 SKIP도 남습니다.
- 고객 Fact의 인과적 기여, 통계 prior의 효과, 사람 의미 승인, 실제 운영 효과, 메뉴의 최신 판매 조건은 미확정입니다. 28명 대규모 실행은 오래 걸릴 수 있으므로 고객을 나누어 실행합니다.
- 신규 A14 예제는 사람 검수와 일부 Fact 단계 정리가 끝나지 않았으며 현재 실행 고객에 등록하지 않았습니다. [페르소나 절차](persona/README.md)를 따릅니다.
