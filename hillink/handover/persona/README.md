# 페르소나 추가

하나의 인터페이스 `python tools/persona_pipeline.py <단계> --workspace /절대경로/private-workspace`를 사용합니다. 작업공간과 원문은 Git 밖에 둡니다. 기존 고객 ID는 덮어쓰지 않습니다.

1. `prepare --corpus /승인된/본문.json`: 작성자 하나의 원문 배열을 검증하고 공통 프롬프트·스키마에 묶인 `request.json`을 만듭니다. 원문 예시는 `corpus.example.json`의 필드 구성을 따릅니다.
2. 승인된 외부 LLM 환경에서 request의 `model_input_private`로 추출합니다. 이 도구는 API를 호출하지 않습니다. 결과 봉투에는 `actual_model_id`, `actual_session_ref`, `isolation_description`, `input_sha256_private`, `profile`을 기록합니다. profile은 요청 안의 공통 8개 섹션 스키마를 따릅니다.
3. `import --response /승인된/결과.json`: 원문 span·화자·시점·사건 연결·중복 횟수 상한을 검증하고 `review.json`을 생성합니다. 구조 통과는 의미 승인이 아닙니다.
4. 사람이 원문과 각 Fact, 부정·타인·시간·사건 중복을 읽고 검수 양식의 모든 HOLD를 처분합니다. 수정이 필요하면 새 작업공간에서 재수입합니다. `approve --review /검수완료/양식.json`으로 검수자·시점·원본 SHA에 승인을 묶습니다.
5. `register`: 현행 제품 importer·측정 계약·화자/과거 이력 검사를 통과한 격리 등록부를 생성합니다. 내장 등록부17명에 새 고객을 추가한 새 등록부를 생성합니다. 기존28명을 덮어쓰거나 공개 승인하지 않습니다.
6. 새 registry와 출력된 SHA를 환경 설정에 연결해 서버를 시작하고 `verify --server http://127.0.0.1:8994`를 실행합니다. 1·2박×행사 유무의 원장을 확인합니다. Replay 누락은 실제 LLM 검증으로 세지 않습니다.

새 유료 호출에는 운영 책임자가 승인한 키·기존 비용 원장·잔여 한도가 필요합니다. 실제 새 고객의 전체 파이프라인 승인 검증은 아직 HOLD입니다. 자동화된 승인은 검수자의 실제 의미 검토를 대신하지 않습니다. 원문·응답·등록부 파일을 HTTP static 폴더로 옮기지 않습니다.


## 실제 새 작성자 예제

```bash
.venv/bin/python tools/persona_pipeline.py example --workspace /tmp/hillink-new-author
```

브랜치 내장 자료에서 A14의 실제 수집 원문119개와 제공된 추출 초안을 읽어 Fact19개를 검사하고 사람 검수 양식을 생성합니다. 이 작성자는 기존28명 실행 등록부에 없습니다. 원본 초안의19개 행동 행을 Fact에 이미 선언된8개 경험 키에 연결하는 구조 어댑터를 적용하며 원본 Fact·인용·성향은 수정하지 않습니다. 사건 독립성은 사람이 승인해야 합니다.

이 예제는 **저장 초안 재수입**입니다. 제공 자료에 모델명·세션 기록이 없어 새 LLM 추출 실행으로 인증하지 않습니다. 실제 모델 결과는 `import --response`로 수입하고, 모델 이력이 없는 제공 초안은 `--supplied-draft`로 명시합니다. 원문 검증 PASS와 LLM 실행 증명, 사람 의미 승인은 서로 다릅니다.

현재 A14는 사람 검수 대기이며 `approve`와 `register`가 차단됩니다. 검수 완료 후 review.json의19개 Fact와 사건·화자·시점 검토를 승인하고 검수자·시점을 남깁니다. 모델 이력 미확인 초안을 승인하려면 `model_origin_review`에 `ACKNOWLEDGE_MODEL_UNRECORDED`를 명시해야 합니다. 이후 같은 CLI의 `approve`, `register`, `verify` 순서를 사용합니다. 최종 제품·공개·시연 승인은 별개입니다.

A14-F016은 피자힐 미선택과 외부 치킨·맥주 섭취를 한 Fact에 담아 제품 단계 검사1건이 남습니다. `product_preflight.json`에 표시합니다. 원본 Fact를 삭제하거나 실제 음주를 임의로 부정하지 않습니다. 사람이 원문에 맞게 사건·단계 범위를 검토하고 필요한 경우 새 초안으로 분리해야 합니다. 현재 실제 A14 등록·방문은 이 문제와 사람 승인 때문에 미실행입니다. 합성 승인 fixture의 전체 HTTP 방문4조건 검증과 구분합니다.
