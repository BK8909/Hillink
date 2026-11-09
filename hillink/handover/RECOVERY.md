# HILLINK | 설치·실행·복원 안내

HILLINK를 처음 실행하거나 다른 환경에서 이어서 개발할 때 필요한 설치 방법, 데이터 복원, AI 판단 모드와 검증 절차를 정리했습니다. 시스템의 목적과 주요 기능은 [README](../../README.md)를 참고하세요.

## 1. 설치와 기본 실행

**필요 환경:** Python 3.11, macOS 또는 Linux, 웹 브라우저. JavaScript 테스트에는 Node.js가 필요합니다.

```bash
git clone https://github.com/BK8909/Hillink.git
cd Hillink/hillink
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
bash tools/start_product.sh
```

기본 주소: **http://127.0.0.1:8994/**

다른 포트를 사용하려면 서버를 시작하기 전에 환경변수를 지정합니다.

```bash
HILLINK_PORT=8997 bash tools/start_product.sh
```

기본 서버는 외부 AI API 호출을 하지 않으며, 규칙 계산과 정확한 저장 판단 재현을 사용할 수 있습니다. `tools/start_product.sh`는 자료 무결성 확인, 데이터 캐시 복원, 저장 응답 준비, 실행 코드 확인을 수행합니다. `bash tools/start_product.sh --check`로 서버를 열지 않고 사전 점검할 수도 있습니다.

**주의:** 제품은 `hillink/` 디렉터리를 기준으로 실행합니다. 저장소 루트의 과거 팀 파일과 제품 폴더를 임의로 조합하지 않습니다.

## 2. 데이터 복원

제공된 자료는 `handover/data/`의 패키지와 매니페스트를 기준으로 확인합니다.

```bash
.venv/bin/python -B tools/bootstrap_data.py --json
.venv/bin/python -B tools/verify_package.py
```

복원기는 포함 파일의 체크섬과 고객·출처 연결을 검사하고, 파생 데이터를 로컬 캐시에 복원합니다. 캐시가 손상됐거나 서로 다른 실험의 데이터가 섞인 것으로 의심되면 **원본 패키지를 수정하지 말고 새 캐시 디렉터리**를 지정해 복원합니다.

```bash
HILLINK_DATA_HOME=/absolute/path/to/new-cache bash tools/start_product.sh --check
```

원본 후기·프로필·상품·저장 AI 응답은 일반적인 화면용 JSON으로 직접 편집하지 않습니다. 수정·검증한 입력을 새 패키지로 구성할 때에는 원본 출처·연결 관계·해시를 함께 갱신해야 합니다.

## 3. 방문 실행 방식

| 화면에서 선택하는 방식 | 실제 동작 | 필요한 조건 |
|---|---|---|
| **규칙 계산** | 호텔 운영 계약과 규칙으로 방문을 계산 | API 키 없이 실행 가능 |
| **저장된 AI 판단 재현** | 기존 LIVE에서 기록한 모델의 **원본 응답**을 같은 입력으로 재생 | 정책·모델·설정·입력 해시와 저장 응답의 정확한 일치 |
| **실시간 AI 판단** | 개인 근거와 현재 방문 상태로 새 모델 판단 수행 | 승인된 키·비용 원장·호출 권한 |
| **실시간 AI 판단 · 개선형** | 이전 방문 기억과 객실 저녁·취침 구분을 포함해 신규 판단 | 동일한 LIVE 승인 및 개선형 실행 정책 |

실시간 판단의 정확한 실행 정책 식별자는 `timeline/viewer/visit_execution.py`의 `LIVE_POLICY`와 `IMPROVED_POLICY`에서 확인합니다. 정책 식별자는 재현 계약과 내부 기록용이며 제품 사용자가 외울 필요는 없습니다.

Replay가 일치하지 않을 경우 `REPLAY_MISS` 또는 해당 차단 사유가 표시되며, AI 응답을 임의로 변형하거나 **규칙 계산을 AI 재생으로 위장하지 않습니다.** 개선형 원본 LIVE 응답을 저장본으로 제공할 때에도 정확한 영수증과 입력을 연결합니다. 다른 고객·기간·가격 조건의 응답을 사용하지 않습니다.

비공개 원응답 묶음을 추가해야 할 때에는 권한을 확인한 다음 `HILLINK_PRIVATE_REPLAY_DIR`로 해당 디렉터리를 지정합니다. 파일은 원본 입력 해시 이름을 가진 영수증이어야 하며 실제 호출 출처가 검증된 응답만 사용됩니다. **API 키·원응답 전문·사용량 원장 등 비공개 자료는 Git에 올리지 않습니다.**

## 4. 승인된 실시간 AI 실행

새 AI 요청은 기본 실행에서 차단됩니다. 실시간 실행은 실제 승인 범위와 기존 누적 사용량 원장을 가진 환경에서만 활성화합니다. 설정 예시는 [environment.example](environment.example)를 참고하세요.

```bash
export HILLINK_AGENT_BUDGET_FILE=/absolute/private/existing/usage.private.json
export HILLINK_AGENT_MAX_CALLS="$APPROVED_CALL_LIMIT"
export HILLINK_AGENT_MAX_USD="$APPROVED_USD_LIMIT"
export HILLINK_LIVE_APPROVAL_REFERENCE="$APPROVAL_REFERENCE"
bash tools/start_product.sh --live
```

위 명령을 사용하기 전에 `APPROVED_CALL_LIMIT`, `APPROVED_USD_LIMIT`, `APPROVAL_REFERENCE`를 실제 승인 내용으로 설정해야 합니다. API 인증정보는 서버 환경변수 또는 권한이 제한된 로컬 키 파일에서만 읽고, 브라우저나 Git 파일에 포함하지 않습니다.

시작 스크립트와 API 서버는 승인 참조, 인증정보, 공유 원장, 잔여 호출·비용 한도를 확인합니다. **기존 비용 원장을 비우거나 새 원장으로 바꿔 누적 제한을 초기화하지 않습니다.** 서버를 시작했다고 자동으로 유료 호출하는 것은 아니며, 실시간 판단을 선택한 방문에서만 호출합니다.

## 5. 제품 기능 확인

다음 순서로 하나의 고객·하나의 실행 기록이 끝까지 이어지는지 점검합니다.

1. **고객 라이브러리:** 프로필 선택 → 원문·Fact·반례 및 실행 가능 여부 확인.
2. **방문 생성:** 방문일·기간·동행·날씨·행사·객실 조건 설정 → 규칙 계산 또는 저장 판단 재현.
3. **고객 흐름:** 지도·시간표를 수동 재생해 식사·활동·휴식·취침·퇴실 연결 확인.
4. **행동근거:** 관측된 개인 Fact → 당시 상황 → 비교한 대안 → 실제 선택을 확인. 원시 코드·JSON·해시는 제품 본문에 표시하지 않음.
5. **전체분석:** 28명 후기에서 반복되는 경험·불편, 우선 운영 제안과 검증 지표를 확인.
6. **가상 소비:** 장면별 주문·금액과 고객(L5)부터 호텔(L1)까지의 집계가 같은 실행에 연결되는지 확인.
7. **운영 전략:** 목표 업장 선택 → 원인 진단 → 전략 카드 → A/B 실행 조건 → 고객 이동·업장/호텔 순변화 → 운영 결론.
8. **재접속:** 새로고침·고객 변경·화면 왕복 뒤에도 현재 실행 ID·방문 조건·판단 방식·거래가 달라지지 않는지 확인.

A/B는 실행 출처에 따라 규칙 기반 비교, 새 LLM 판단을 포함한 비교, 기존 주문 수량을 고정한 가격 산술 계산을 구분합니다. 실제 실행할 수 없는 상품·예약·운영 조건에는 결과를 만들어 넣지 않습니다. 한 조건의 오류·보류·미유입 결과를 다른 실행의 성공처럼 표시하지 않습니다.

### 자동화 검증

```bash
PYTHONPATH=tools/offline_test_guard .venv/bin/python -m pytest -q timeline/viewer/tests
node --test timeline/viewer/tests/*.test.cjs
```

전체 테스트의 합격 여부는 실행한 코드와 데이터의 실제 결과를 기준으로 판단합니다. 과거의 예상값·고정 해시를 성공 수치에 맞추기 위해 수정해서는 안 됩니다. 회귀의 알려진 제약은 `tools/ci/`와 해당 테스트의 근거를 참고합니다. 실제 브라우저 E2E에서는 렌더링·콘솔·네트워크·원장·정책 표시를 함께 확인해야 합니다.

## 6. 주요 코드와 후속 개발

| 위치 | 기능 |
|---|---|
| `tools/start_product.sh` · `tools/bootstrap_data.py` | 서버 시작·데이터 복원 |
| `timeline/viewer/app.py` · `visit_execution.py` | 제품 API·실행 모드와 가용성 |
| `timeline/experiments/persona_live/operator_choice/autonomy_v1/` | 행동 후보·LLM 판단·상태/기억·SKU/운영 검증 |
| `timeline/viewer/static/` | 라이브러리·지도·행동근거·가상 매출·전략 UI |
| `timeline/viewer/ledger_service.py` · `ledger_l5.py` | 주문·영수증·다층 가상 원장 |
| `timeline/viewer/strategy_agent_service.py` | 개인·집단 전략 및 A/B 실행 계약 |
| `tools/persona_pipeline.py` | 신규 작성자 프로필 준비·검증·등록 |
| `timeline/viewer/tests/` | 회귀·계약 테스트 |

신규 고객은 **원문 준비 → 추출 결과 생성 → 출처·사건·Fact 검증 → 사람 의미 검수 → 격리 등록 → 가상 방문 실행** 순서로 추가합니다. 세부 절차는 [페르소나 등록 안내](persona/README.md)를 따릅니다.

문제가 발생하면 먼저 **실행한 Git 커밋, 선택한 모드, 입력 조건, 서버가 반환한 차단 사유, 원장 검증 결과**를 확인합니다. 디버그용 세부 기록은 로컬 검수 환경에서 보되 일반 제품 화면에 노출하지 않습니다.

---

이 문서는 제품을 실행·복원하기 위한 공개 기술 안내입니다. 실제 고객의 행동 정확도나 호텔 매출 효과를 인증하는 문서가 아닙니다.
