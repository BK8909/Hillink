# HILLINK 설치·복원 및 핵심 기술 계약

[저장소 루트 README](../../README.md)가 제품 시작 안내이며, [연구·기술 인계서](../docs/research/RESEARCH_AND_ARCHITECTURE_HANDOFF.md)가 정책·실험·평가의 상세 근거입니다. **현재 제품은 V19LS 실시간 AI 판단(기본 LIVE) + V17 이전 LIVE(이름으로만 선택) + V16 저장 판단 재현 + 규칙 계산**을 지원합니다(2026-11-07 기준). 일부 V18 기초 연구 정책은 명시적으로 선택할 수 있으나, C/L2/S2/LS 교차 실험 결과는 별도 연구 기록으로 관리합니다.

공개 저장소 **[BK8909/Hillink](https://github.com/BK8909/Hillink)**에서 제품을 내려받아 사용합니다. 현재 제품은 `hillink/` 하나에 있습니다. 루트에 보존된 기존 팀 파일을 복사하거나 조합하지 않습니다. 아래 명령은 별도 안내가 없으면 `hillink/`에서 실행합니다.


## 실행과 데이터

Python 3.11 가상환경에 `requirements-dev.txt`를 설치한 뒤 `bash tools/start_product.sh`로 시작합니다.

```bash
git clone https://github.com/BK8909/Hillink.git
cd Hillink/hillink
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
bash tools/start_product.sh
```

기본 주소는 `http://127.0.0.1:8994/`이며 `HILLINK_PORT`로 변경합니다. **기본 실행은 규칙·동일 입력 Replay이며 외부 API 호출이 차단**됩니다. 새로운 LIVE 선택은 아래에서 별도 승인·설정을 거쳐 활성화합니다.

`tools/bootstrap_data.py --json`이 `handover/data/bundle.json`의 SHA를 확인하고 내장 자료를 사용자 캐시에 복원합니다. 빈 캐시 재검증은 Git 밖의 새 경로를 `HILLINK_DATA_HOME`에 지정합니다. 특정 개발자의 폴더를 전달받을 필요가 없습니다. 복원된 `.local.json`은 파생 파일이며 직접 수정하거나 커밋하지 않습니다. 캐시를 재구성하려면 새 캐시 경로를 사용합니다.

기본 시작 명령은 내장 표시 검수 자료의 고객 ID·원문 SHA·방문 ID를 확인하고 승인된 범위의 목록 문구를 적용합니다. `handover/data/profile-display-review.json`의 수정은 표시 전용이며 엔진 Fact·성향·사람 의미 승인·썸네일 승인을 바꾸지 않습니다. 원문이 변조되거나 고객 연결이 맞지 않으면 복원을 중단합니다.

현재 제품과 복원 패키지는 **공개 저장소에 함께 게시**되어 있습니다. 입력은 공개된 후기·호텔 정보에서 구축한 연구용 자료와 저장 실행 기록으로 구성했고, `handover/data/bundle.json` 및 `product-inputs.tar.gz`의 무결성을 확인해 복원합니다. **공개 기술 설명과 개별 원출처 자료의 이용 조건은 구분**하며, 데이터 출처·재현 범위·연구상 한계는 [연구·기술 인계서](../docs/research/RESEARCH_AND_ARCHITECTURE_HANDOFF.md)에 기록합니다. 개인 API 키·비공개 비용 원장은 포함하지 않습니다.

## 디렉터리와 연결 구조

| 위치 | 역할 |
|---|---|
| `tools/start_product.sh` | 유일한 표준 서버 시작 명령, 자료 복원·Replay 준비·실호출 사전 확인 |
| `timeline/viewer/app.py` | 로컬 HTTP 서버와 방문·원장·전략 API |
| `timeline/viewer/static/` | 기존 고객 라이브러리·조건·지도·행동근거·매출·운영 전략 화면 |
| `timeline/viewer/visit_execution.py`, `visit_run.py` | 규칙/Replay/LIVE 구분과 연속 방문 실행 |
| `timeline/experiments/persona_live/operator_choice/autonomy_v1/` | 현재 행동 엔진, V16 저장 판단 재현, V19LS 실시간 판단(V17 보존)·운영 규칙·상품 계약 |
| `timeline/viewer/ledger_service.py`, `ledger_l5.py` | 동일 run의 SKU·수량·결제 및 L5~L1 집계 |
| `timeline/viewer/strategy_agent_service.py` | 해당 run의 실제 선택을 사용하는 개인·집단 전략과 A/B 계약 |
| `handover/data/` | 고객 입력·원문·공식 자료·원 응답 Replay와 단일 데이터 manifest |
| `tools/persona_pipeline.py` | 신규 페르소나 준비·수입·사람 승인·격리 등록·검증 |
| `timeline/viewer/tests/` | 유지한 회귀 코드와 fixture |

## 실행 정책과 판단 출처

방문은 `m4_c01` 엔진과 `C01_HOTEL_CATALOG_V1` 상품·운영 계약을 사용하며, 실행 모드에 따라 판단 출처를 구분합니다.

| 실행 모드 | 판단 정책 | 외부 호출 및 제약 |
|---|---|---|
| 규칙 | 기존 M4 규칙 실행 | 신규 API 호출 없이 실행, 모델의 새 판단으로 표시하지 않음 |
| **저장 판단 Replay** | `LLM_AUTONOMOUS_CUSTOMER_V16` | 저장된 실제 모델 응답을 **동일 입력·모델·설정·입력 SHA**가 일치할 때만 재현, 신규 호출 0회 |
| **새 LLM 판단 LIVE** | `LLM_AUTONOMOUS_CUSTOMER_V19LS` (이전: `…_V17`, 명시적 정책 지정 시에만 선택) | `visit_execution.py`의 `LIVE_POLICY`(V17은 `PREVIOUS_LIVE_POLICY`); 명시적 키·공유 원장·승인·사용자 선택 필요 |
| **연구 정책** | V18 일부 기초 후보 선별 정책 및 C/L2/S2/LS 비교 연구 | 일부 초기 V18 정책만 명시적 식별자로 선택 가능하며, C/L2/S2/LS 교차 실험은 연구 기록으로 구분. 현재 기본 판단 정책이 아님 |

모델이 선택한 뒤 영업시간·이동·예약·자격·SKU·가격·수량을 검증하고 실제 채택된 행동만 주문·원장에 연결합니다. 행동근거 ④와 매출·운영 전략은 같은 run을 사용합니다. **검증 실패 시 재계획은 최대 1회, 실패를 규칙 점수 선택으로 몰래 대체하지 않습니다.**

Replay는 모델·설정·전체 입력이 일치하는 원 응답만 이용합니다. `REPLAY_MISS`는 차단이며 규칙이나 실호출로 자동 전환하지 않습니다. `CACHE_REPLAY`와 `LIVE_RESPONSES`, 모델 판단과 사람 의미 승인을 구분합니다. V18 실험 결과가 필요하면 [연구 인계서 5-6~5-7절](../docs/research/RESEARCH_AND_ARCHITECTURE_HANDOFF.md)을 참고하세요.

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

## 최신 제품 검증 현황 (2026-11-07)

- **V16 Replay:** 저장 응답 **38/38** 입력·선택 일치(무과금).
- **제품 회귀:** Python **830 PASS / 기존 10 FAIL(신규 회귀 0, 11/06 기준 기존 12건 중 2건 해결) / SKIP 1** · Node **255/255 PASS** · V16 Replay **38/38** · 오프라인 GitHub Actions CI.
- **오프라인 CI(`.github/workflows/offline-ci.yml`):** 패키지·데이터 SHA와 비밀정보 검사, 문서 링크·현재 LIVE 정책 일치, 새 AI 공동 작성자 표기 유입 검사, 새 캐시 복원·시작 명령, Node·Python 전체 회귀(분류된 기존 실패만 허용, 수집 오류·중단·신규 실패는 실패), 규칙 모드 결정성(같은 요청을 해시 시드 2종으로 실행해 전체 결과 비교), V16 Replay 38/38, CD-15 과거 계약 재현(Git 이력의 봉인 엔진 파일로 원래 테스트 실행 · 현행 엔진 결과로 세지 않음), 기존 원장 차이 설명(정보용), HTTP E2E(같은 실행의 인용 Fact→판단→장면→원장 행 연결, 다른 입력에 저장 판단 재사용 거부, LIVE 거절), Chromium 브라우저 E2E(흐름·행동근거·매출·운영 전략의 실행 ID 일치, 거절된 실행 뒤 이전 실행 유지, 조건 변경 시 전 화면 교체, 없는 실행 ID 거부, 1440·1024·390px). API 키 없이 실행되며 LIVE 호출은 하지 않습니다.
- **커밋 메타데이터:** 자동 AI 공동 작성자·세션 표기를 막으려면 복제본마다 `git config core.hooksPath hillink/tools/git-hooks`를 한 번 실행합니다(사람 작성자·커미터 정보는 바꾸지 않음). CI도 새 커밋에 해당 표기가 있으면 실패합니다.
- **패키지 무결성:** 현재 `package_manifest.json`의 포함 파일 **1,604개** SHA 검증 기준, 원본 데이터 번들 **125개 파일**. 비밀값 탐지 **0건**.
- **라이브러리:** 45명 화면 표시 · 28명 기술 실행 가능 · 17명 열람 전용(전체 의미·썸네일 사람 승인과 구분).
- **HTTP·브라우저:** 새 clone·가상환경·캐시에서 복원 및 서버 기동, Replay·규칙/행사 조건·매출 원장 L4~L1, 고객 흐름·행동근거·매출 화면 확인. 라이브 API 호출은 키 없는 공개 검수 환경에서 실행하지 않음.
- **연구 분리:** V18 실호출 224회·전체 방문 9건 중 7건 완주, LS/V17 실호출 16회 비교에서 LS는 미승격(11/06) → 안정화한 V19LS를 실호출 130회 비교·재확인 후 기본 LIVE로 승격(11/07). **제품 설치 성공이나 Replay 일치를 행동 예측 정확도·LS 품질 증명으로 해석하지 않습니다.**

실제 공개 배포 기록은 저장소 [release.json](../../release.json)과 [연구·기술 인계서](../docs/research/RESEARCH_AND_ARCHITECTURE_HANDOFF.md)를 함께 봅니다.

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
- 전체 Python 회귀에는 **기존 실패 10건**(5개 테스트 ID)이 남아 있고 신규 회귀 실패는 0건입니다(11/06 제출판의 12건 중 숨김 Fact ID 노출 방지·검증 도구 복원으로 2건 해결). 분류와 확인된 원인: ① 과거 기대값과 현행 계약 불일치 7건 — `test_visit_smoke_v1` 6건은 CL-42 엔진(visit-state-v2.2)에서 기록된 값이고 현행 엔진은 v2.3·외부 배달 기본 정책이 추가됨(배달 정책을 꺼도 금액이 다름), `test_m4_live_visit` 1건은 연구 기준(ae37786) 이후 상품 카탈로그 세분화·뷔페 조식 기본값·행동 변경. 두 기준 시점의 엔진은 이 저장소 이력에 없어 과거 재현은 불가하며, 같은 요청의 현행 엔진 불변식(일수·박수·단계·행사일, 영수증=L4~L1, 일별 합계, 정수 원화)은 `test_current_engine_invariants_1107.py`로 별도 검증. ② CD-15 봉인 SHA 불일치 2건(`test_opx_adapter`) — 이후 엔진 변경 3건(메뉴 다양성 근거·코스 수 미확인·외부 배달 동점 처리)과 프로필 확장. 현행 엔진은 계산을 거부(검증)하고, Git 이력의 봉인 파일로는 원래 테스트 5/5가 재현됨(CI 단계). ③ 과거 저장본 원장 차이 1건(`test_ledger_l5`) — 18개 하루의 차이를 장면 단위로 분해: 가격만 6, 행동만 2, 둘 다 10(`tools/ci/explain_ledger_gaps.py`). 가격 차이 39건은 모두 1인 기준 가격에서 등록 상품 주문 계약으로 바뀐 데서 생겼고, 행동 차이 중 현재 엔진에만 있는 유료 조식 6건은 조식 계약 정책(객실 계약이 포함하는 인원만 무료)에서, 저장본에만 있는 유료 야간 족욕 3건은 현재 엔진에서 포함 혜택(0원, PACKAGE_INCLUDED) 계약으로 처리되는 데서 생깁니다. 목록은 `tools/ci/known_failures.tsv`(테스트 ID·건수·원인), 근거는 `handover/profile45_review/ls_stabilization_1107/결과보고-최종-V19LS-제품승격-1107.md` 5절. 실패 원인은 **개별 테스트 결과를 재검토**하되, 과거 기대값·봉인 SHA·현재 원장 불변식을 임의 변경해 PASS로 처리하지 않습니다. 과거 입력 누락 SKIP은 PASS로 세지 않습니다.
- 고객 Fact의 인과적 기여, 통계 prior의 효과, 사람 의미 승인, 실제 운영 효과, 메뉴의 최신 판매 조건은 미확정입니다. 28명 대규모 실행은 오래 걸릴 수 있으므로 고객을 나누어 실행합니다.
- 신규 A14 예제는 사람 검수와 일부 Fact 단계 정리가 끝나지 않았으며 현재 실행 고객에 등록하지 않았습니다. [페르소나 절차](persona/README.md)를 따릅니다.
