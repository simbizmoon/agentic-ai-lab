# Agentic AI Lab — LEARNING LOG

## 학습자

- 사용자: moon
- GitHub: simbizmoon
- 시작일: 2026-07-23
- 시작 수준: Agentic AI 초보자
- 운영체제: Ubuntu
- 프로젝트 경로: `/home/moon/Project/agentic-ai-lab`

## Phase 0–5 요약

### Phase 0 — 프로젝트 기반

- Ubuntu, Git, GitHub와 Python 가상환경 구성
- 기준 문서와 권한 경계 확정
- Codex 읽기 전용 분석과 Diff 검토 학습

### Phase 1 — Agentic AI 기초

- Chatbot, Workflow와 Agent 구분
- Goal, Environment, State, Action, Observation
- Agent Loop
- Deterministic과 Probabilistic 처리
- 최소 자율성, Human-in-the-loop와 최소 권한

최종 평가: 93점, 통과

### Phase 2 — OpenAI API

- OpenAI Python SDK
- Responses API
- Secret 관리
- Request, Response와 Token Usage
- API 오류 처리

### Phase 3 — Structured Outputs

- JSON Schema와 Pydantic
- Structured Outputs
- 모델 응답 검증
- 오류 분류와 제한된 교정
- 문서 분석 Structured Output
- 보안·감사 심화 기능 구현

범위 교훈:

Phase 3의 Transparency Log, Merkle Proof, Witness Quorum,
Signed Gossip Bundle과 Trust Decision Receipt는 유익한 심화 실습이었으나
AIRA의 핵심 목표보다 과도하게 확장되었다.

해당 기능은 동결했다.

### Phase 4 — Tool Calling

- 문서 통계와 키워드 Tool
- Tool Registry와 Dispatcher
- 인수 검증과 오류 교정
- 허용 Tool 정책
- Observation과 Final Answer 분리

### Phase 5 — Workflow와 상태 관리

- 명시적 상태 모델
- 허용 상태 전이
- 성공, 교정과 실패 경로
- Tool Calling Workflow와 상태 머신 통합

## Phase 6–8 요약

### Phase 6 — RAG

- 문서 수집, Chunk와 Retrieval
- Source와 Evidence 연결
- 근거 기반 응답
- RAG 평가와 문서화

### Phase 7 — Memory

- Memory Schema
- 저장, 검색과 갱신
- Memory와 Workflow State 분리
- 불필요한 장기 Memory 사용 제한

### Phase 8 — Planning Agent

- 목표와 Plan
- 단계, 의존성 및 실행 상태
- Replanning과 Stop Condition
- Planning이 불필요한 요청 구분

## Phase 9 — Single Research Agent 완료

- Research Request
- Task 분해
- Search Query 계획
- Source Search와 Reader
- Evidence 추출
- Source 품질
- Claim과 Citation
- Research Workspace
- Synthesis와 품질 평가
- Single-Agent E2E와 Baseline

핵심 결과:

AIRA의 기본 연구 경로가 완성되었다.

## Phase 10 — Multi-Agent Research 완료

- Agent Role과 Capability
- Task Assignment와 Message
- Shared Workspace
- Delegation
- 전문 Agent 실행
- Sequential 및 Parallel Pipeline
- Conflict Detection과 Revision
- Single-Agent와 Multi-Agent 비교

핵심 교훈:

Multi-Agent는 항상 더 좋은 것이 아니다.
비용과 지연이 증가하므로 평가에서 이점이 확인된 요청에만 사용해야 한다.

## Phase 11 — Evals, Guardrails, Reliability 완료

- Evaluation Dataset
- Deterministic Evaluation Runner
- Citation, Evidence와 Claim Support 평가
- Report Quality
- Multi-Agent Workflow 평가
- Regression Runner
- Input, Output와 Tool Guardrail
- Retry, Timeout, Cancellation과 Failure Recovery
- Reliability Metrics
- Phase 11 E2E
- Reliability Baseline

## Phase 12 — Application, Persistence, Background Jobs 완료

완료일: 2026-08-05

구현:

- Application Execution Record
- Execution, Evaluation, Guardrail과 Job Repository
- Background Job Lifecycle
- Queue와 Worker Lease
- Retry Scheduling
- Cancellation Persistence
- Research, Tool과 Workflow Application Service
- Reliability Query
- Transaction Boundary
- Idempotency와 Duplicate Prevention
- Application Failure Mapping
- Phase 12 E2E Flow
- Persistence와 Job Reliability Test
- 기술 문서와 Baseline

최종 검증:

```text
4048 passed
Ruff: All checks passed
```

예상된 ZIP Duplicate Warning도 테스트에서 명시적으로 포착하여
경고 없는 Baseline을 만들었다.

## 범위 재평가 — 2026-08-05

### 확인한 문제

- 여러 Phase가 작은 Schema, Repository와 Error Class 단위로 지나치게
  세분화되었다.
- 전체 구조 학습보다 테스트와 하위 추상화의 수가 빠르게 증가했다.
- 원래 목표인 실용적인 AIRA보다 운영 플랫폼과 분산 시스템 방향으로
  확장될 위험이 생겼다.
- Phase 3에서 이미 유사한 범위 확장 문제를 경험했다.

### 결정

- Phase 13을 최종 Phase로 확정한다.
- Phase 14 이후 계획은 폐기하고 Backlog로 이동한다.
- 최종 목표는 로컬에서 실제 사용할 수 있는 AIRA MVP다.
- CLI와 Single Research Agent를 기본 경로로 한다.
- 최소 저장, 실제 사용 사례, Docker와 사용자 가이드에 집중한다.
- PostgreSQL, Redis, Nginx, 분산 Worker, Kubernetes와 상용 Web UI는
  완료 조건에서 제외한다.

### 다음 단계

Phase 13 — Practical AIRA Integration and Delivery

첫 작업:

1. 실제 사용 시나리오 확정
2. 기존 모듈 통합 지도 작성
3. 불필요한 기본 경로 제거
4. AIRA CLI 완성

## Evidence Chunking and Source Quality

Implemented and tested paragraph-based evidence extraction for live web research.

Observed results:

- 4,145 tests passed.
- Ruff passed.
- Live research completed successfully.
- Three readable sources produced nine evidence items.
- Every evidence excerpt was no longer than 1,200 characters.
- Each source produced no more than three evidence items.
- The generated Markdown report was 71 lines and 9,089 bytes.
- No real-looking API key was exposed.
- The official OpenAI documentation received a higher source-quality score than secondary sources.

Key lesson:

Chunking controls report size, but chunking alone does not guarantee answer quality. Source-quality evaluation must influence candidate selection or evidence ordering to prevent weaker third-party sources from receiving equal report space.

## Quality-Aware Source Selection

Implemented quality-aware document selection for live research.

Validation results:

- 4,146 tests passed.
- Ruff passed.
- Nine search candidates were collected for a three-source request.
- Nine candidates were read.
- Three documents were selected.
- All selected documents came from the official OpenAI developer domain.
- Secondary blog and compatibility-provider sources were removed.
- Live quality score increased to 0.976.

Failure analysis:

Authority-based selection solved the weak-source problem but did not solve topical relevance. Generic API overview pages, documentation indexes, and code-heavy quickstart sections displaced the more directly relevant Responses API overview. Same-domain pages also occupied all available source slots.

Lesson:

Source selection must combine authority with query relevance, document specificity, content usefulness, and redundancy control. Authority is a necessary signal, not a complete ranking strategy.
---

## 2026-08-06 — Evidence-aware Source Backfill과 정직한 품질 실패

### 학습 목표

검색 후보가 충분해도 실제 Evidence를 제공하는 Source가 부족할 수 있다는
문제를 이해하고, Evidence 중심으로 Source quota와 품질 판정을 설계한다.

### 최초 현상

OpenAI Responses API 공식문서 조사에서 세 문서를 선택했지만 Hard Filter를
적용한 뒤 실제로 남은 Evidence는 한 Source의 한 문단뿐이었다.

그럼에도 기존 Quality Evaluator는 다음 결과를 냈다.

```text
quality ≈ 0.97
quality level = excellent
passed = yes
```

Claim Coverage와 Citation Coverage는 높았지만 독립 Source 수가 부족한
구조적 문제가 품질 통과를 막지 못했다.

### 잘못된 중간 접근

처음에는 Source 선택 단계에서 최대 세 문서를 고르면 충분하다고 생각했다.

그러나 문서 선택 이후 Evidence 추출 단계에서 다음 자료들이 제거되었다.

- 코드 실행 예제
- 단순 함수 호출
- Markdown Navigation fragment
- 문서 Index
- 링크 카드 목록
- 자연어 한 줄 뒤에 붙은 다중 Markdown 링크 목록

즉, 선택 문서 수와 유효 Evidence Source 수는 서로 다른 값이었다.

### 발견한 핵심 원인

```text
Source Selection
→ maximum_sources만큼 먼저 고정
→ Evidence Extraction
→ 일부 문서가 NO_EVIDENCE
→ 교체 없음
```

`NO_EVIDENCE` 문서가 최종 Source quota를 이미 소비한 것이 근본 원인이었다.

### 해결 구조

```text
전체 적격 문서 Ranking
→ 한 문서씩 Evidence 추출
→ Evidence가 있으면 최종 Source로 채택
→ NO_EVIDENCE이면 다음 후보로 Backfill
→ maximum_sources 도달 또는 후보 소진
```

최종 Source 수는 검색결과 수나 읽은 문서 수가 아니라 Evidence를 실제로
제공한 독립 Source 수로 계산한다.

### 최소 Source 품질 Gate

```text
minimum_evidence_sources = min(2, maximum_sources)
```

- `maximum_sources >= 2`인데 Evidence Source가 1개이면 품질 실패
- `maximum_sources = 1`이면 Source 1개로 통과 가능
- Offline Baseline에는 적용하지 않아 기존 호환성 유지

### 실패 사례 분석

Backfill 도입 후 두 번째 Source가 확보된 것처럼 보였지만, Evidence 내용은
다음과 같은 문서 색인이었다.

```text
- Multi-agent
- Node reference
- SDKs and CLI
- OpenAI CLI
```

이 자료는 Responses API의 핵심 기능을 직접 설명하는 Evidence가 아니었다.

다중 Markdown 링크 목록 Hard Filter를 추가한 뒤 해당 Source들은
`NO_EVIDENCE`가 되었고 Pipeline은 다음 후보를 계속 시도했다.

최종적으로 깨끗한 두 번째 Source를 찾지 못했으므로 다음 결과가 나왔다.

```text
read_candidate_count = 9
evidence_attempted_document_count = 4
selected_document_count = 1
no_evidence_document_count = 3
quality_passed = false
LOW_SOURCE_DIVERSITY = error
```

### 검증

- Backfill 성공
- Source quota 조기 종료
- 후보 소진
- `maximum_sources=1`
- 결정론

위 다섯 시나리오를 회귀 테스트로 고정하였다.

최종 결과:

```text
4157 passed
All checks passed
Live Evidence noise = 0
```

### 배운 점

1. Source 수는 검색결과 수가 아니다.
2. 읽은 문서 수 역시 Evidence Source 수가 아니다.
3. 품질 점수가 높아도 최소 구조 요건을 충족하지 못하면 실패해야 한다.
4. Hard Filter를 약화해 Source 수를 채우면 Research Agent의 신뢰성이
   오히려 낮아진다.
5. 근거가 부족하면 `passed=false`로 보고하는 것이 올바른 Agent 행동이다.
6. Live 실패 사례는 단위 테스트만으로 발견하기 어려운 새로운 노이즈 형태를
   보여준다.
7. 실제 Live E2E와 결정론적 Regression Test를 함께 사용해야 한다.

### 다음 학습 과제

Evidence Source가 부족할 때 단순히 실패하는 데서 끝나지 않고, Agent가
Query를 수정하거나 다른 공식 Source 유형을 탐색하는 제한된 Replanning으로
연결해야 한다.

---

## 2026-08-07 — Evidence 부족을 제한형 Replanning으로 복구하기

### 학습 목표

Research Agent가 근거 부족을 단순 실패로 보고하는 데서 끝나지 않고, 비용과
횟수가 제한된 추가 조사를 수행하도록 설계한다.

### 출발 상태

Evidence-aware Backfill과 최소 Source Gate를 구현한 뒤 결과는 다음과 같았다.

```text
Evidence Source = 1
LOW_SOURCE_DIVERSITY = error
quality_passed = false
```

### 설계 결정

범용 `PlanningAgentLoop` 대신 문제 크기에 맞는
`SupplementalResearchQueryPlanner`를 만들었다.

```text
Evidence Source 부족
→ Query 한 개 보완
→ 검색 한 번 추가
```

실행 상한은 Supplemental Query 1개, 추가 검색 1회, 총 검색 2회로 고정했다.

### 구현 흐름

```text
첫 번째 검색
→ Evidence-aware Backfill
→ Evidence Source 수 검사
→ 부족하면 Supplemental Query 생성
→ 두 번째 검색
→ 기존 URL·Source ID 중복 제거
→ 신규 후보만 읽기
→ 초기 문서와 신규 문서 병합
→ 전체 Ranking 재실행
→ Evidence-aware Backfill 재실행
```

### 핵심 학습

- 작은 실패 원인에는 작은 복구 Loop가 적합하다.
- Replanning 성공 여부는 검색 실행이 아니라 Evidence Source 증가로 판단한다.
- 서로 다른 Query가 반환한 동일 URL은 Pipeline 수준에서 제거해야 한다.
- 추가 문서는 기존 문서와 함께 전체 재평가해야 한다.
- 복구 후에는 오래된 품질 Issue를 현재 상태에 맞게 제거해야 한다.
- 결정론적 테스트와 실제 Live E2E는 서로 다른 오류를 발견한다.

### Live 검증

```text
search_round_count = 2
replanning_triggered = true
supplemental_query_count = 1
supplemental_candidate_count = 4
deduplicated_candidate_count = 5
read_candidate_count = 13
evidence_attempted_document_count = 5
selected_document_count = 2
evidence_source_count = 2
no_evidence_document_count = 3
source_count = 2
claim_count = 4
citation_count = 4
quality_score = 0.9163
LOW_SOURCE_DIVERSITY = 없음
```

### 테스트 결과

```text
4167 passed in 9.41s
All checks passed
git diff --check passed
```

### 다음 학습 과제

Supplemental Search의 Provider Credit과 Latency를 측정해 Budget 제약과
연결한다. 또한 `result.json`에 Quality `passed`를 명시적으로 저장할지
검토한다.

---

## 2026-08-07 — 계산 속성과 외부 JSON 계약 분리하기

### 학습 목표

Python 객체에서 계산되는 속성과 외부에 저장되는 JSON 필드가 서로 어떻게
다른지 이해하고, 영향 범위를 통제하면서 외부 계약을 확장한다.

### 발견한 현상

Markdown Report에는 `Passed: yes`가 정상적으로 표시되었지만,
`result.json`에서 `data["quality"].get("passed")`는 `None`을 반환했다.

### 원인

`ResearchQualityEvaluation.passed`는 일반 `@property`였다. 일반 속성은 Python
객체에서는 읽을 수 있지만 Pydantic의 `model_dump()`와
`model_dump_json()`에는 자동 포함되지 않는다.

Markdown Writer는 `quality.passed`를 직접 읽었고, JSON Writer는 모델
직렬화 결과만 저장했기 때문에 두 출력의 차이가 발생했다.

### 선택한 구조

```text
내부 모델
→ issues를 기준으로 passed 계산

외부 Writer
→ 계산된 passed를 JSON Payload에 복사

result.json
→ true 또는 false를 명시적으로 저장
```

### 회귀 테스트

성공 Case:

```text
Quality ERROR 없음
→ result.quality.passed is True
→ payload["quality"]["passed"] is True
```

실패 Case:

```text
LOW_SOURCE_DIVERSITY/error 존재
→ result.quality.passed is False
→ payload["quality"]["passed"] is False
```

### 검증 결과

```text
3 writer tests passed
4168 total tests passed in 15.61s
All checks passed
git diff --check passed
```

### 배운 점

1. Python에서 접근 가능한 속성이 자동으로 JSON에 저장되는 것은 아니다.
2. 계산 속성과 저장 필드는 서로 다른 설계 문제다.
3. 계산 가능한 값을 일반 필드로 중복 저장하면 상태 불일치 위험이 생긴다.
4. 작은 외부 계약 변경은 Writer 경계에서 처리하면 영향 범위를 줄일 수 있다.
5. `computed_field`는 편리하지만 모든 직렬화 경로를 바꾼다는 점을 고려해야 한다.
6. 성공 Case뿐 아니라 실패 Case도 JSON 계약 테스트로 고정해야 한다.
7. 외부 Agent나 자동 평가기는 Boolean을 직접 읽을 수 있어야 한다.

### 다음 학습 과제

다음 단계에서는 Live Research의 검색 호출 수, Provider Credit, Latency를
측정하여 Supplemental Search가 실제로 사용하는 비용을 Budget 제약과
연결한다.

---

## 2026-08-07 — 외부 Provider 사용량을 Budget으로 통제하기

### 학습 목표

검색 횟수만 제한하는 것과 실제 Provider 자원 사용량을 제한하는 것의 차이를
이해하고, Call·Credit·Latency를 하나의 실행 Budget으로 연결한다.

### 핵심 학습

- 검색 라운드 수와 Provider 호출 수는 같은 개념이 아니다.
- 비용 제한은 실행 계획이 아니라 실제 Usage와 연결되어야 한다.
- 호출 전 예상값과 호출 후 실제값을 구분해야 한다.
- 미보고 Usage를 0으로 처리하면 비용을 과소평가할 수 있다.
- 초기 검색과 보완 검색이 같은 Budget을 공유해야 전체 상한이 유지된다.
- Budget 차단도 최종 결과의 관측 가능한 상태로 남겨야 한다.
- 네트워크 Latency Budget과 절대 실행 Deadline은 다른 정책이다.

### 검증 결과

```text
4194 passed in 15.69s
All checks passed
git diff --check passed
provider calls = 1
credits used = 1.0
budget exhausted = false
```

---

## 2026-08-07 — 품질 기준을 낮추지 않고 Source 분류 오류 해결하기

### 학습 목표

근거 Source가 부족할 때 Selector 기준을 완화하기 전에 Search, Reader,
Evaluator, Selector 중 어느 계층이 실제 원인인지 증거로 구분한다.

### 단계별 진단

```text
READ 성공 = 9
FAILED = 1
```

따라서 Reader가 한 문서만 읽었다는 가설은 틀렸다.

```text
developers.openai.com = 0.88
openai.github.io = 0.6625
기타 일반 Source = 0.6625
```

Selector는 최고 점수 0.88에서 0.12 이내인 문서만 적격으로 처리했으며,
입력 점수에 따라 정상 동작했다.

### 근본 원인

Tavily Candidate 생성 코드가 모든 결과를 다음 값으로 고정했다.

```text
source_type = OTHER
```

### 선택한 해결

Provider 독립적인 `ResearchSourceTypeClassifier`를 만들고 Candidate 정규화
단계에 연결했다. Live Runtime에서는 정확한 `openai.github.io`만 Trusted Host로
등록했다.

### Live 재검증

```text
openai.github.io = official_documentation / 0.9225
developers.openai.com = official_documentation / 0.9225
selected_document_count = 2
evidence_source_count = 2
search_round_count = 1
provider_call_count = 1
credit_used = 1.0
overall_quality = 0.9345
passed = true
```

### 배운 점

1. 최종 Source 부족만 보고 Reader 실패라고 추정하면 안 된다.
2. Raw Read 결과와 Selected Document 결과를 분리해서 관찰해야 한다.
3. Selector가 한 개를 선택해도 Selector 자체가 원인이라는 뜻은 아니다.
4. Source Type 정규화 오류는 Quality Score와 최종 Evidence 수를 연쇄적으로 왜곡한다.
5. 품질 기준을 낮추기 전에 입력 Domain Model이 정확한지 확인해야 한다.
6. 광범위한 Domain Pattern보다 정확한 Trusted Host가 안전하다.
7. 검색 정확도 개선은 품질뿐 아니라 Supplemental 호출과 Credit도 줄인다.
8. 단위 테스트와 저장된 Live Artifact 재진단을 함께 사용해야 근본 원인을 확정할 수 있다.

### 다음 학습 과제

다음 단계에서는 Citation 검증을 구현하고, 동일 질문 반복 실행에서 Provider
결과와 최종 Evidence가 얼마나 달라지는지 측정한다.

---

## 2026-08-07 — LLM-as-a-Judge Semantic Citation Verification 평가하기

### 학습 목표

Claim과 Evidence가 단순히 ID로 연결되어 있는지를 넘어,
Evidence가 실제로 Claim의 의미를 지지하는지 LLM으로 평가하고,
그 Judge 자체의 신뢰성을 Golden Dataset과 Blind Holdout으로 검증한다.

### 처음 발견한 문제

기존 Live Research의 Deterministic Claim Builder는 다음과 같이 동작하였다.

```text
Claim.text = Evidence.excerpt
```

따라서 Live Semantic Citation 결과가 모두:

```text
entailment_score = 1.0
decision = verified
```

여도 Semantic Judge 능력이 검증된 것은 아니었다.

이는 사실상 다음 질문이었다.

```text
"문장 A가 문장 A를 지지하는가?"
```

### 첫 번째 실패 — 숫자 Score를 정책으로 사용

초기 구조:

```text
LLM entailment_score
→ threshold
→ decision
```

실제 평가 결과 rationale는 적절했지만 연속 점수는 안정적으로 calibration되지
않았다.

비슷한 Partial Support 사례에서도 점수가 크게 흔들렸고, 더 강한 과장이
더 높은 점수를 받기도 했다.

### 개선

Semantic Support Level을 명시적으로 도입하였다.

```text
fully_supported
partially_supported
unsupported
contradicted
```

정책 결정은 코드가 수행한다.

```text
fully_supported
→ verified

partially_supported
→ needs_revision

unsupported
→ rejected

contradicted
→ rejected
```

`entailment_score`는 진단용으로만 유지한다.

### 두 번째 학습 — Category도 Eval이 필요하다

범주형 분류가 연속 점수보다 안정적이었지만 경계 사례에서는 여전히
판정이 흔들렸다.

특히 다음 요소들이 중요했다.

```text
may vs always
조건 누락
수량 상한
scope 확대
entity mismatch
causation vs association
missing information vs contradiction
```

### Golden Dataset과 Label Adjudication

초기 16 Case Golden Dataset:

```text
13 / 16
81.25%
```

실패를 분석하면서 Judge뿐 아니라 Golden Label 자체도 잘못될 수 있음을
확인하였다.

따라서 평가 데이터에도 사람의 논리적 Adjudication이 필요하다.

### Dev Set과 Holdout 분리

Golden Dataset v2를 Prompt 개선에 사용하였다.

따라서 해당 Dataset은 더 이상 독립적인 최종 평가셋이 아니며,
Development Dataset으로 취급하였다.

Prompt v2 결과:

```text
18 / 20
90%
false_fully_supported = 0
```

그 후 Prompt를 동결하고 처음 보는 Blind Holdout 20 Case를 실행하였다.

```text
19 / 20
95%
false_fully_supported = 0
false_rejected = 1
```

### 중요한 Known Failure

다음 Evidence:

```text
The service is available during business hours.
```

를 다음 의미로 과도하게 읽는 오류가 발생했다.

```text
The service is available only during business hours.
```

즉 Positive Scoped Evidence를 Exclusive Evidence로 해석할 수 있다.

### 전체 검증

```text
4245 passed in 16.27s
Ruff: All checks passed
git diff --check: passed
```

Live Research E2E:

```text
quality = 0.9345
semantic citation verification count = 6
support_level = fully_supported 6 / 6
decision = verified 6 / 6
```

단, Live Claim이 Evidence excerpt와 동일하므로 이 결과는 Semantic Judge의
판별 성능이 아니라 Runtime Wiring 검증으로 해석한다.

### 배운 점

1. LLM의 좋은 rationale가 좋은 score calibration을 보장하지 않는다.
2. 정책 결정은 가능하면 명시적 category와 결정론적 코드로 통제해야 한다.
3. 연속 score는 진단 신호와 정책 신호를 분리해야 한다.
4. Golden Dataset의 정답도 틀릴 수 있으므로 Label Adjudication이 필요하다.
5. 평가 결과를 보고 Prompt를 수정한 Dataset은 더 이상 Blind Test가 아니다.
6. Development Dataset과 Holdout Dataset을 분리해야 일반화 성능을 측정할 수 있다.
7. 정확도만 보지 말고 오류의 방향을 측정해야 한다.
8. Citation Verification에서는 false fully supported가 특히 위험하다.
9. Missing Information과 Contradiction은 다른 의미 관계다.
10. Live E2E Wiring 검증과 Semantic Judge 품질 평가는 서로 다른 테스트다.
11. 작은 Holdout의 높은 정확도를 전체 현실 성능으로 일반화해서는 안 된다.
12. Evaluated Capability와 Production Blocking Quality Gate는 같은 상태가 아니다.

### 현재 판단

```text
Semantic Citation Verification
= Evaluated Capability

Blocking Quality Gate
= 보류
```

### 다음 학습 과제

더 큰 Holdout과 반복 평가를 통해 Judge 변동성과 Class별 Precision/Recall을
측정한 뒤, 생성형 Claim Builder를 도입했을 때 실제 Claim-to-Evidence
Semantic Verification이 어떻게 동작하는지 평가한다.

---
## 2026-08-07 — Generative Claim Construction 및 Bounded Execution

### 학습한 핵심 개념

1. **Claim Generation과 Provenance는 분리해야 한다.**
   - LLM은 의미를 자연스럽게 표현하는 데 강하다.
   - ID, Source, Document, Evidence, Citation 및 문자 범위는 결정론적 코드가 관리해야 추적성과 재현성이 유지된다.
   - 이번 구현의 핵심 원칙은 `Meaning by LLM; provenance by code.`이다.

2. **Citation correctness와 Answer relevance는 다른 문제다.**
   - 생성 Claim이 Evidence에 의해 `fully_supported`여도 사용자의 질문에 직접 답하지 않을 수 있다.
   - `Claim ↔ Evidence` 평가는 Semantic Citation Verification의 책임이고, `Question/Objective ↔ Claim` 평가는 별도의 Relevance Evaluation 문제다.

3. **Bounded execution은 Agentic System의 필수 안전장치다.**
   - Evidence 수가 증가한다고 LLM 호출 수가 무제한 증가해서는 안 된다.
   - 호출 횟수, Token 및 시간에 상한을 두어 비용과 latency를 제어해야 한다.

4. **Budget 초과와 실행 실패는 동일하지 않다.**
   - 호출 전 attempt budget이 소진되면 다음 호출을 시작하지 않는다.
   - 성공한 호출이 token/time ceiling을 넘긴 경우 그 결과는 보존하고 이후 호출만 중단할 수 있다.
   - 이것은 전체 작업을 버리지 않는 graceful degradation이다.

5. **실제 Runtime 검증은 Unit Test와 별개다.**
   - Unit Test에서 budget 로직을 검증한 뒤 실제 Live Runtime에서도 attempt와 token ceiling을 강제로 발생시켜 동작을 확인했다.
   - Fake/Stub 성공만으로 Production Runtime 동작을 주장하면 안 된다.

### 직접 확인한 결과

- 실제 OpenAI Claim generation이 Evidence 복사가 아닌 paraphrase를 생성했다.
- Live Research의 생성 Claim 3개가 모두 Evidence 원문과 달랐다.
- 세 Claim 모두 Semantic Citation Verification에서 `fully_supported`였다.
- Attempt limit 실험: Evidence 6개, budget 3회 → Claim 3개.
- Token limit 실험: Evidence 6개, token budget 1 → 첫 Claim 1개 보존 후 중단.
- 관련 테스트, 전체 pytest, Ruff 및 `git diff --check` 통과.

### 다음 학습 질문

- Evidence에 충실한 Claim이 실제 Research Question에도 충분히 관련 있는지를 어떻게 평가할 것인가?
- Claim Relevance를 categorical policy로 둘 것인가, score 기반 Eval로 둘 것인가?
- Relevance 평가를 blocking quality gate로 사용할 시점은 언제인가?

---

## 2026-08-08 — Grounded Claim과 Relevant Claim은 다르다

### 학습 목표

Semantic Citation이 완전히 지지되는 Claim도 사용자의 Research Question에
답하지 않을 수 있다는 문제를 분리해서 이해한다.

### 최초 Live Failure

연구 질문:

```text
How does the OpenAI Agents SDK support tool calling?
```

생성된 Claim 3개는 모두 Semantic Citation Verification에서
`fully_supported`였지만 Claim Relevance에서는 모두 `irrelevant`였다.

### 배운 점

1. `Claim ↔ Evidence`와 `Question/Objective ↔ Claim`은 서로 다른 평가 문제다.
2. Citation 정확도만 높다고 Research Answer가 좋은 것은 아니다.
3. Groundedness와 Answer Relevance를 분리하면 실패 위치를 더 정확히 찾을 수 있다.
4. LLM Judge의 연속 score를 곧바로 정책 threshold로 쓰기보다 categorical
   judgment를 중심에 두는 편이 안정적이다.
5. Eval에 사용한 Development Dataset과 Blind Holdout을 구분해야 한다.
6. Holdout 결과를 본 뒤 같은 Holdout에 맞춰 Prompt를 다시 조정하면
   Blind Test의 의미가 사라진다.

### Claim Relevance 평가

```text
Prompt v2.1 Development:
17 / 18 = 94.44%

Blind Holdout v2:
17 / 18 = 94.44%
false_direct = 1
false_irrelevant = 0
```

현재 판단:

```text
Claim Relevance
= Evaluated Capability

Blocking Quality Gate
= 보류
```

---

## 2026-08-08 — Semantic Evidence Relevance: 답이 문서 안에 있어도 Retrieval이 실패할 수 있다

### 학습 목표

Search가 맞고 Source Document 안에 답이 존재하는데도 최종 Claim이 질문에
답하지 못하는 경우, Evidence Retrieval 계층에서 실패를 찾는 방법을 학습한다.

### Failure Localization

초기 Live Failure를 단계별로 확인하였다.

```text
Search Query
→ 적절함

Selected Source
→ 관련 문서임

Full Document
→ answer-bearing Passage 존재

Selected Evidence
→ 일반적인 소개 Paragraph 위주
```

따라서 문제는 Search 실패가 아니라:

```text
Semantic Evidence Relevance Gap
```

이었다.

### 배운 점

1. Search relevance와 Evidence relevance는 다른 단계다.
2. 문서 전체가 관련 있어도 모든 Paragraph가 질문에 관련 있는 것은 아니다.
3. Objective가 Retrieval 과정에 들어가지 않으면 Question 단어 overlap만 높은
   Paragraph가 선택될 수 있다.
4. Candidate Generation, Shortlisting, Semantic Evaluation, Final Selection을
   분리하면 어느 단계가 실패했는지 추적할 수 있다.

### Evidence Relevance 평가

```text
Golden Development initial:
16 / 18 = 88.89%

Prompt v1.1 Development:
18 / 18 = 100%

Blind Holdout v1:
16 / 18 = 88.89%
false_direct = 2
false_irrelevant = 0
```

Development Dataset의 100%를 일반적인 현실 성능으로 해석하지 않는다.

---

## 2026-08-08 — Embedding similarity는 Answer Relevance와 같지 않다

### 실제 관찰

68개 Paragraph Candidate에서 질문에 직접 답하는 Passage의 Embedding 순위는:

```text
agent loop / invokes tools
→ rank 9

function tools / schema / Pydantic
→ rank 10

MCP + native function tools
→ rank 11
```

기존 Top-8 Embedding Shortlist에서는 이 Passage들이 LLM Semantic Evaluator에
도달하지 못했다.

특히 다음 Passage는:

```text
function tools with automatic schema generation
and Pydantic-powered validation
```

다음 신호를 보였다.

```text
embedding score ≈ 0.552
lexical score   ≈ 0.726
```

### 핵심 학습

Embedding은 의미적 유사성을 잘 측정하지만 다음을 보장하지 않는다.

```text
"이 Passage가 사용자의 질문에 가장 직접적으로 답하는가?"
```

Lexical ranking도 반대로 단독으로 완전하지 않다.

따라서 서로 다른 signal을 결합해야 한다.

---

## 2026-08-08 — Recall과 Precision을 분리하고 RRF로 결합하기

### 구조

```text
Paragraph Candidates
       ↓
Embedding Rank ──┐
                 ├─ RRF Hybrid Shortlist
Lexical Rank ────┘
       ↓
LLM Evidence Relevance
       ↓
Precision-first Final Selection
```

### 개념

- **Recall**: 필요한 정답 후보를 놓치지 않는 능력
- **Precision**: 가져온 후보 중 정말 필요한 것만 고르는 능력

이번 구조에서:

```text
Embedding + Lexical + RRF
= Recall 담당

LLM Semantic Evidence Relevance
= Precision 담당
```

### RRF Simulation

```text
Core Passage                              Embedding  Lexical  RRF

SDK general overview                           1        3      1
function tools / schema / Pydantic            10        1      5
built-in agent loop / invokes tools            9        8      6
```

Top-8 budget을 늘리지 않고도 핵심 Passage가 평가 범위에 들어왔다.

### 배운 점

1. Budget 문제를 후보 수 증가로만 해결하지 않아도 된다.
2. 서로 다른 Ranking signal을 결합하면 Recall을 개선할 수 있다.
3. 특정 질문의 keyword를 Production 코드에 하드코딩해서는 안 된다.
4. Retrieval algorithm 개선은 일반화 가능한 signal 조합으로 해결해야 한다.

---

## 2026-08-08 — UNEVALUATED와 IRRELEVANT는 같은 상태가 아니다

### 문제

Semantic Relevance Budget이 먼저 소진되면 일부 Candidate는 평가되지 않은
`UNEVALUATED` 상태로 남는다.

초기 구현에서는:

```text
DIRECT
→ PARTIAL
→ UNEVALUATED
→ IRRELEVANT
```

순서 때문에 이미 Relevant Evidence가 있어도 남은 Top-N을 UNEVALUATED
Candidate가 채웠고 CTA 같은 노이즈가 최종 Evidence에 들어갈 수 있었다.

### 최종 정책

```text
Relevant Evidence 존재
→ DIRECT/PARTIAL만 최종 Evidence

Relevant 없음 + Budget exhaustion
→ best UNEVALUATED 1개 fallback

모두 평가 완료 + 모두 IRRELEVANT
→ NO_EVIDENCE
```

### 배운 점

1. `평가하지 못함`은 `관련 없음`과 다르다.
2. Budget exhaustion은 의미 판정이 아니라 실행 상태다.
3. graceful degradation은 불확실성을 숨기지 않아야 한다.
4. Final promotion policy와 Reranker trace policy는 서로 다른 책임이다.

---

## 2026-08-08 — RRF 이후 Live Regression에서 확인한 것

최종 Live Source:

```text
Tools - OpenAI Agents SDK
official OpenAI Agents SDK documentation
```

Final Evidence:

```text
PARTIAL 0.55
DIRECT  0.88
PARTIAL 0.60

UNEVALUATED = 0
CTA noise = 0
```

Citation:

```text
3 / 3 verified
3 / 3 fully_supported
```

Claim Relevance:

```text
PARTIAL 0.50
PARTIAL 0.60
DIRECT  0.78
```

Deterministic Quality:

```text
0.8845
high
passed = true
```

### 중요한 해석

이번 결과는 시스템이 완벽하게 Tool Calling 전체 흐름을 설명했다는 뜻은 아니다.

Evaluator는 여전히 일부 Claim에 대해 다음 부족함을 지적했다.

- Tool 등록/노출 방식의 전체 설명 부족
- 실행 시 Agent가 Tool을 선택하는 과정 부족
- Argument 전달 부족
- Tool invocation 부족
- Tool result가 모델로 돌아오는 흐름 부족

즉 다음 품질 문제는:

```text
Relevant Evidence를 찾는가?
```

에서 한 단계 나아가:

```text
여러 Relevant Evidence를 어떻게 조합해
Question 전체를 충분히 Coverage하는가?
```

로 이동하였다.

### 최종 학습

1. Grounded != Relevant.
2. Embedding similarity != Answer relevance.
3. Recall과 Precision은 분리해야 한다.
4. RRF는 서로 다른 retrieval signal을 결합하는 단순하고 강력한 방법이다.
5. LLM Judge는 candidate filtering보다는 의미적 precision 판단에 적합하다.
6. UNEVALUATED와 IRRELEVANT를 구분해야 한다.
7. Live E2E 실패는 단위 테스트가 찾지 못하는 retrieval pathology를 보여준다.
8. 실제 코드, schema, runtime artifact를 문서나 추측보다 우선해야 한다.
9. Evaluation 결과가 존재하는 위치도 schema와 writer를 실제로 확인해야 한다.
10. 높은 deterministic quality score와 semantic answer quality는 별개일 수 있다.

### 최종 Regression Checkpoint

Step 5.12의 Claim Relevance, Semantic Evidence Relevance,
RRF Hybrid Retrieval, Precision-first Selection 및 문서 업데이트를 포함해
전체 Repository를 다시 검증하였다.

```text
4431 passed in 16.41s
Ruff: All checks passed
git diff --cached --check: passed
```

이 결과는 focused test 성공만이 아니라 기존 Repository 전체 Regression과의
호환성도 유지되었음을 의미한다.

### 다음 학습 과제

- 여러 Relevant Evidence의 coverage를 측정하는 방법
- Direct Evidence가 부족할 때 추가 Retrieval/Replanning 여부
- Claim set 전체가 Question/Objective를 충분히 커버하는지 평가하는 방법
- Semantic Relevance를 언제 Blocking Quality Gate로 승격할지

---

## 2026-08-09 — Observability 이후 최적화는 측정된 병목부터 한다

### 학습 목표

Agent 시스템 최적화를 감으로 수행하지 않고 실제 Stage별 Call, Token,
Latency를 측정하여 가장 비싼 부분부터 개선하는 방법을 학습한다.

### 출발점

Step 6.5 Observability에서 다음 heavy path가 측정되었다.

```text
tracked LLM calls = 30
tracked tokens = 45,498
total elapsed = 591.871s
```

후속 re-baseline에서는 동일 benchmark 계열의 대표 heavy path가:

```text
tracked calls median ≈ 24
recorded tokens median ≈ 40.9K
total elapsed median ≈ 293s
quality = 0.8845
```

로 확인되었다.

핵심 병목은 Web Search가 아니라 검색 이후 Semantic Evaluation과
Coverage Round의 반복 평가였다.

### 배운 점

1. 최적화 전에 반드시 관측 가능성이 있어야 한다.
2. 가장 눈에 띄는 외부 Tool이 가장 비싼 단계라는 보장은 없다.
3. Stage별 wall-clock과 API Usage를 분리해야 병목을 찾을 수 있다.
4. 모든 AI API 호출이 동일한 계측 경로에 들어오는 것은 아니므로
   `tracked calls`의 의미를 명시해야 한다.

---

## 2026-08-09 — 재사용은 새 호출보다 먼저 검토한다

Coverage Replanning에서는 기존 Round의 결과를 그대로 버리고 전체를 다시
평가하면 비용이 급격히 증가한다.

따라서 다음 순서를 적용하였다.

```text
기존 Evidence/Claim/Evaluation 재사용 가능성 확인
→ 새 문서만 Semantic Evaluation
→ 필요할 때만 새 Claim 생성
→ 최종 Coverage는 전체 Claim Set으로 평가
```

### 학습

- Agentic loop에서 Replanning은 모든 단계를 처음부터 다시 실행하는 것을
  의미하지 않는다.
- 불변 부분과 신규 부분을 분리하면 호출 수와 latency를 크게 줄일 수 있다.
- Incremental path는 기존 상태가 정확히 보존되는 경우에만 사용해야 한다.
- 기존 Evidence가 바뀌면 Full Rebuild fallback이 더 안전하다.

---

## 2026-08-09 — Batch는 의미를 합치는 것이 아니라 Transport를 합치는 것

Evidence, Claim, Citation 및 Relevance 단계에서 API fan-out이 컸다.

잘못된 최적화는 여러 Evidence를 하나의 의미적 synthesis 요청으로 바꾸는 것이다.
그렇게 하면 기존 provenance 계약이 바뀐다.

선택한 방식:

```text
독립된 N개 작업의 의미는 유지
→ 하나의 Structured Batch 요청으로 전송
→ item_id로 결과를 다시 매핑
→ 최종 ID와 provenance는 코드가 재구성
```

### 적용 결과

- Evidence Semantic Relevance: 문서별 batch
- Claim Relevance: claim batch
- Semantic Citation Verification: claim/citation pair batch
- Claim Generation: evidence→claim batch

### 핵심 학습

1. Batch Optimization과 Semantic Architecture 변경은 다른 문제다.
2. 모델에게 내부 provenance ID를 맡기지 않는다.
3. Batch output은 temporary item ID만 사용해 순서 변화에 안전해야 한다.
4. 구조화 응답 오류와 Provider/runtime 오류를 구분해야 한다.
5. Structured batch 오류에는 bounded single fallback을 사용할 수 있지만,
   Provider/runtime failure를 무조건 N개의 single call로 확대하면 안 된다.

---

## 2026-08-09 — Logical Usage와 Physical API Usage는 다르다

Batch를 도입하면 다음 두 값이 달라진다.

```text
Evidence 3개 평가

logical attempts = 3
physical API calls = 1
```

따라서 Usage 의미를 분리하였다.

```text
last_usage
= 논리적 item/budget usage

last_api_usage
= 실제 Provider/API 호출 usage
```

### 배운 점

- Budget은 업무량 제한과 외부 비용 제한이라는 두 목적을 가질 수 있다.
- Batch 이후에도 논리적 item cap을 유지해야 기존 안전장치가 사라지지 않는다.
- Observability에서는 physical API usage를 사용해야 실제 fan-out 감소가 보인다.
- Token/time을 item별로 정확히 분배할 수 없는 batch 응답은 그 한계를
  명시적으로 기록해야 한다.

---

## 2026-08-09 — Step 6.6 최종 성능 결과와 한계효용 체감

최종 C1 Live Regression:

```text
Round 1
Evidence Semantic       1
Claim Generation        1
Citation Verification   1
Claim Relevance         1
Answer Coverage         1

Coverage Round
Evidence Semantic       1
Claim Generation        1
Citation Verification   1
Claim Relevance         1
Answer Coverage         1
```

최종 결과:

```text
tracked LLM calls = 10
recorded tokens = 27,248
total elapsed = 163.709s
quality = 0.8845
passed = true
```

대표 heavy-path baseline과 비교:

```text
tracked calls:
24 → 10
약 58.3% 감소
```

### 중요한 실패 사례

최종 Coverage는:

```text
partially_covered
→ partially_covered
```

였다.

새 Evidence 3개가 생겼지만 내용은:

```text
Agents + tools + built-in loop
Agents as tools / handoffs
MCP tools alongside function tools
```

에 집중되었다.

정작 필요한:

```text
function tool 정의/등록
argument 전달
tool invocation
tool result 반환
runner loop lifecycle
```

이 부족했다.

### 해석

Claim batch가 좋은 Evidence를 망친 것이 아니라 최종 Evidence 자체가 필요한
세부 메커니즘을 충분히 포함하지 않았다.

즉 Failure Localization은:

```text
Batch Claim Generation
→ 핵심 원인 아님

Upstream Retrieval / Coverage Replanning
→ Known Limitation
```

으로 판단하였다.

---

## 2026-08-09 — 언제 최적화를 멈출 것인가

### 새 학습

소프트웨어와 Agent 시스템은 항상 더 개선할 수 있다.

하지만 다음 질문이 더 중요하다.

```text
이 개선이 가능한가?
```

보다:

```text
이 개선이 지금 할 가치가 있는가?
```

### 현재 판단

Single-Agent Live Research는 주요 기능과 실패 감지, Budget, Observability,
Replanning 및 Batch 최적화까지 확보하였다.

추가 미세조정은 가능하지만 현재 단계에서는 다음 비용이 커지기 시작했다.

- 분석 시간
- 코드 복잡성
- Regression 범위
- 특정 benchmark 과최적화
- 새로운 Agent Architecture 학습 지연

따라서 현재 Baseline을 고정하고 Multi-Agent 학습으로 이동한다.

### Stop Rule

앞으로 각 주요 단계는 가능하면 다음을 기록한다.

```text
Goal
Acceptance Criteria
Measured Result
Known Limitation
Stop Rule
Reopen Condition
```

### 최종 교훈

1. 완벽함은 Stage 완료 조건이 아니다.
2. 실패를 탐지하고 한계를 기록할 수 있으면 다음 단계로 이동할 수 있다.
3. 큰 구조적 낭비를 먼저 제거하고 작은 최적화는 실제 필요가 생길 때 한다.
4. Cost-effectiveness에는 API 비용뿐 아니라 개발자의 시간과 복잡성도 포함된다.
5. Multi-Agent도 같은 원칙으로 평가해야 한다.

---

## 2026-08-15 — Federated Retrieval != Integrated Evidence

### 1. Federated Retrieval이란 무엇인가

Federated Retrieval은 서로 다른 source universe를 각각 검색한 뒤 결과를 하나의
normalized candidate stream으로 합치는 방법이다. 이번 slice에서는 Web와 Local을
검색하고 `research_origin`, source/document identity 및 provenance를 잃지 않은 채
interleave, deduplicate, rerank했다.

```text
Web candidates + Local candidates
→ normalized federated candidate set
```

그러나 candidate set에 들어왔다는 사실만으로 final evidence가 된 것은 아니다.

### 2. Federation과 Integrated Evidence는 다르다

첫 real smoke에서 Local candidate는 path, filename, raw SHA-256/size와 함께 정상적으로
federation되었지만 global quality selection 뒤 semantic evidence extraction에 도달하지
못했다. 즉 다음 두 상태는 다르다.

```text
Federated Retrieval
!=
Integrated Evidence
```

이 실패는 search/routing 문제가 아니라 extraction 전 selection 문제였다.

### 3. Source-universe-aware selection

Web와 Local score는 같은 척도가 아니다. 따라서 Integrated-only selector는 두 origin이
모두 readable이고 quota가 2 이상이면 best Web와 best Local에 각각 evidence extraction
기회를 준 뒤 기존 combined quality order로 나머지를 채운다.

이것은 citation 강제가 아니다. weak Local fixture는 실제 기회를 받은 뒤
`NO_EVIDENCE`로 거부되었고 pipeline은 다음 Web document로 backfill했다. 반대로 질문에
직접 답한 strong Local fixture는 final 3 source 중 Local 1개로 남아 여러 claim/citation을
지원했다. 공정한 기회와 품질 기준을 동시에 유지한 사례다.

### 4. Capability composition보다 먼저 오는 security boundary

Local content를 external provider가 처리할 수 있는 component보다 먼저 구성하면 승인
실패가 너무 늦다. 올바른 순서는 다음과 같다.

```text
path + raw digest + size approval validation
→ local parsing
→ same-policy fresh fingerprint
→ approval revalidation
→ Tavily/OpenAI/worker construction
→ pipeline execution
```

Semantic Local approval과 Integrated approval은 purpose가 달라 서로 대신 사용할 수 없다.

### 5. Provenance가 중요한 이유

`research_origin`, canonical path, filename, raw digest/size, source/document/evidence ID,
exact character range가 연결되어야 citation이 어느 원문에서 왔는지 추적할 수 있다.
Federation은 provenance를 지우는 merge가 아니라 provenance를 보존하는 normalization이다.

### 6. Offline test와 real smoke의 역할

Offline tests는 federation, routing, approval ordering, selector 및 backfill contract를
재현 가능하게 검증했다. 실제 runtime smoke는 추가로 다음을 드러냈다.

- `OPENAI_TIMEOUT_SECONDS=30`, `OPENAI_MAX_RETRIES=2`에서 semantic evidence relevance
  중 `APITimeoutError` 발생
- `120`/`0` 설정의 smoke는 성공했지만 permanent default 결정은 아님
- semantic evidence processing이 dominant latency 구간
- weak fixture의 실제 `NO_EVIDENCE`와 backfill
- strong fixture의 final Local claim/citation 기여

### 핵심 교훈

> Federated Retrieval != Integrated Evidence

검색 결과에 포함되었는지뿐 아니라 selection, extraction, evidence, claim, citation까지
끝까지 provenance가 이어지는지 실제 실행으로 확인해야 한다.

---

## 2026-08-16 — Persistent Embedding Cache: Cache는 권한이 아니라 최적화다

### 1. Cache, Index, Vector Database의 차이

- **Cache**는 이미 계산한 결과를 같은 identity로 다시 요청할 때 재사용하는 최적화다.
- **Index**는 문서를 검색 가능한 구조로 조직하여 어떤 항목을 찾을지 결정한다.
- **Vector database**는 vector 저장, 검색, lifecycle 및 운영 기능을 제공하는 persistence다.

이번 구현은 exact text embedding 결과를 재사용하는 cache이며 persistent retrieval index나
vector database가 아니다. 서로 다른 책임을 한 component에 합치지 않는 것이 중요하다.

### 2. Content-addressed identity와 decorator pattern

동일 embedding을 재사용할 수 있는 identity는 다음 세 값으로 구성했다.

```text
exact UTF-8 text SHA-256
+ embedding model name
+ embedding dimensions
```

source path는 같은 내용이 다른 파일로 복사될 때 재사용을 막으므로 identity에 넣지 않는다.
`CachingEmbeddingProvider`는 기존 provider를 변경하지 않고 감싸는 decorator/composition
pattern을 사용한다. miss만 underlying provider에 batch로 보내고 input order는 복원한다.

### 3. Authoritative validation과 non-authoritative cache

Local source validation과 external-send approval은 authoritative safety boundary다. Cache는
결과를 빠르게 만드는 non-authoritative optimization일 뿐이다.

```text
LocalDocumentAccessGate
→ external-send approval
→ fresh source/approval revalidation
→ cache/provider composition
```

따라서 cache hit가 있어도 access gate나 approval을 건너뛸 수 없다. 빠른 결과가 권한을
대체하면 안 된다.

### 4. Corruption은 miss, 안전한 I/O 실패는 error

Malformed JSON, unsupported/schema-invalid payload 및 identity mismatch는 stale embedding을
반환하지 않고 miss로 낮출 수 있다. 하지만 unsafe symlink/path 또는 genuine filesystem,
read/write/locking failure를 miss로 숨기면 안전 문제를 정상 cache 상태로 오해하게 된다.

구현 중 decoding boundary의 누락을 발견했다. 처음에는 `read_text()` 주변에서 `OSError`만
처리했지만 invalid UTF-8은 JSON parsing 전에 `UnicodeDecodeError`를 발생시켰다.

```python
except UnicodeDecodeError:
    return None
```

회귀 테스트를 추가하여 invalid UTF-8 entry가 miss가 되는 것을 검증했다. 핵심 교훈은
corruption handling이 JSON/schema parser뿐 아니라 byte-to-text decoding layer까지
포함해야 한다는 점이다.

### 5. Persistent hit를 증명하는 방법

같은 in-memory provider object를 재사용하는 것만으로 persistence를 증명할 수 없다.
동일 directory를 가리키는 새 `FileEmbeddingCache`와 새 provider instance를 만들고 같은
query/candidate text를 요청했다.

```text
first provider calls  = one batch
second provider calls = []
```

Real Local Semantic CLI smoke에서도 첫 실행 뒤 JSON entry 3개가 생성되었고 두 번째 실행
뒤에도 같은 3개만 남았다. 두 실행 모두 report/result artifact를 만들었다.

```text
run 1: real 1m14.286s, entries 3
run 2: real 1m26.481s, entries 3
```

두 번째 wall-clock time이 더 길어도 cache 실패를 의미하지 않는다. Evidence relevance,
claim generation, citation/relevance/coverage 등 embedding 이외 semantic LLM call이 계속
실행되며 전체 latency를 지배할 수 있기 때문이다.

### 검증과 다음 학습 목표

- Step 1 focused tests: `57 passed`
- Step 2 focused integration tests: `74 passed`
- real Local Semantic repeated-run smoke: 두 실행 성공, entry `3 → 3`

다음 목표는 같은 cache abstraction을 Integrated Web + Local semantic research에 연결하되,
Local source access/approval ordering을 약화하지 않는 것이다.


---

## 2026-08-16 — Persistent Semantic Embedding Cache: 캐시 경계는 데이터 출처가 아니라 계산 identity에 둘 수 있다

### 1. Retrieval origin과 semantic computation은 다른 concern이다

Local/Web origin은 source routing, approval 및 provenance의 concern이다. 반면 embedding
reuse는 같은 입력으로 같은 semantic computation을 다시 수행하는지의 concern이다.
Integrated Research는 Web와 Local document에 하나의 shared semantic shortlister를 사용한다.
이 경계에서 Local-only cache를 유지하려면 origin-aware router나 extractor duplication이
필요했고, 이는 retrieval concern을 embedding provider layer에 끌어들이는 구조였다.

따라서 cache를 provider-level semantic identity 경계에 두었다.

```text
exact UTF-8 text SHA-256
+ embedding model
+ embedding dimensions
```

path, URL, origin 및 execution mode가 달라도 위 계산이 같으면 entry를 재사용할 수 있다.
같은 computation을 source universe별로 중복 저장할 이유가 없다는 뜻이다.

### 2. Authoritative safety와 non-authoritative cache

Source approval/access validation은 authoritative하고 cache는 non-authoritative optimization이다.
Integrated Local source는 다음 순서를 모두 통과한 뒤에만 cache lookup에 도달한다.

```text
approval validation
→ validated document loading
→ fresh raw source fingerprint
→ approval revalidation
→ cache/provider composition
```

따라서 cache hit는 빠른 계산 결과일 뿐 권한이 아니다. pre-existing entry가 있어도 Local
access gate, raw SHA-256 revalidation 또는 external-send approval을 생략할 수 없다.

### 3. Mandatory cache와 error taxonomy

Mandatory cache는 persistent filesystem을 runtime availability dependency로 만든다. 하지만
best-effort fallback이 항상 더 안전한 것은 아니다. malformed JSON이나 invalid UTF-8 같은
payload corruption은 miss로 낮출 수 있지만 unsafe symlink, lock failure 및 permission failure를
숨기면 security-significant condition을 정상 miss로 오해할 수 있다.

현재 taxonomy가 recoverable I/O와 security failure를 충분히 구분하지 않으므로 cache는
fail-closed로 유지한다. 안전한 fallback을 원한다면 먼저 error taxonomy를 세분화해야 한다.

### 4. Raw text를 저장하지 않아도 privacy concern은 남는다

Cache payload는 raw source/query text, URL, local path 및 origin을 저장하지 않는다. 그러나
embedding vector는 semantic information을 담고 SHA-256은 공격자가 예상 text를 알고 있을 때
확인 수단이 될 수 있다. shared cache는 Local뿐 아니라 Web/query hash와 vector도 저장한다.

따라서 final directory를 `0700`, JSON/lock/temp file을 `0600`으로 normalize했다. 기존
broader-mode directory도 `0700`으로 줄이고 `chmod` 실패는 명시적 error로 처리한다.

### 5. Real smoke가 보여 준 partial success

Isolated Integrated smoke의 첫 실행은 embedding entry 87개를 성공적으로 저장한 뒤
`OpenAIEvidenceRelevanceEvaluator`에서 `APITimeoutError`가 발생했다. 즉 전체 실행 실패가
모든 앞 단계 실패를 의미하지 않는다. embedding persistence는 완료됐고 downstream semantic
relevance call이 timeout 난 것이다.

환경변수는 unset이어서 repository default 30 seconds/2 retries가 적용되었다. retry에서는
smoke isolation 목적으로 shell에서만 temporary `120`/`0`을 사용했고 report/result 생성에
성공했다. 이는 permanent configuration decision이 아니다. cache entry는 `87 → 121`로
증가했는데, live Web result와 paragraph text가 실행마다 달라질 수 있으므로 정상이다.

### 6. 새 permission 관측

같은 smoke에서 `report.md`와 `result.json` mode가 `0664`로 관측되었다. 이것만으로 policy
violation이나 취약점이라고 결론 내릴 수는 없다. 다만 Local-derived research artifact의
confidentiality 관점에서 `ResearchResultWriter`와 기존 persistence convention을 별도로
감사할 이유가 생겼다. embedding cache의 `0700`/`0600` hardening과는 다른 boundary다.

### 검증과 다음 학습 목표

- focused cache/handler suite: `82 passed`
- broader Integrated regression: `151 passed`
- offline persistent reuse: new instance, Local → Integrated, Web → Local 통과
- real Integrated smoke: entry `87 → 121`, temporary `120`/`0` retry 성공

다음 구현 목표는 `Parsed Document Cache`이다. 다만 그 전에 Research Result Artifact
Permission Audit을 좁은 security audit으로 수행할지 우선순위를 판단한다.


---

## 2026-08-16 — Research Result Artifact Hardening: 출력 파일도 데이터 경계다

### 1. Unix umask는 보안 정책 자체가 아니다

일반적으로 text file creation은 requested mode `0666`, directory creation은 `0777`에서
시작하고 process umask가 bit를 제거한다. 기존 writer가 `Path.write_text()`와 기본
`mkdir()`에 의존했을 때 umask `0002`는 file `0664`, directory `0775`를 만들었다.
이는 실행 환경에서 파생된 결과이지 AIRA가 의도적으로 선택한 private policy가 아니었다.

### 2. Directory permission도 함께 봐야 한다

File이 `0664`여도 모든 ancestor가 `0700`이면 다른 사용자가 접근할 수 없다. 하지만
관측된 output root와 execution directory가 모두 `0775`였으므로 그런 parent protection이
없었다. Permission audit은 file mode 하나가 아니라 전체 path boundary를 확인해야 한다.

### 3. Result artifact는 최종 report보다 더 많은 데이터를 담을 수 있다

`report.md`는 Local evidence excerpt, filename/title, citation 및 derived claim을 포함할
수 있다. `result.json`은 normalized source text와 section, canonical Local path, raw
SHA-256/size, evidence range, PDF/HWPX provenance 및 전체 workspace metadata까지 담을 수
있다. 따라서 사람이 읽는 final answer뿐 아니라 machine-readable artifact도 중요한
confidentiality boundary다.

### 4. Shared root 안에 private execution boundary를 둔다

User-selected output root는 협업이나 후속 처리를 위해 의도적으로 shared일 수 있으므로
writer가 mode를 바꾸지 않는다. 대신 각 새 research execution directory를 `0700`으로,
`report.md`와 `result.json` 및 temporary artifact를 `0600`으로 만든다.

```text
shared-or-user-managed output root
└── private execution directory (0700)
    ├── report.md (0600)
    └── result.json (0600)
```

이 구조는 사용자 root ownership을 존중하면서 Local-derived output을 private-by-default로
만든다.

### 5. Atomic write는 content completeness와 durability를 높인다

Same-directory temporary file에 전체 UTF-8 content를 쓴 뒤 flush와 file `fsync`를 하고
`os.replace`로 final name을 설치한다. 마지막에 directory를 `fsync`하면 directory entry
변경의 durability도 요청할 수 있다. Temporary file은 content write 전에 `0600`으로
설정해 post-write `chmod`의 노출 window를 피한다.

### 6. 두 파일은 하나의 완전한 transaction이 아니다

Report와 JSON temporary file을 모두 준비한 후 replace하고, 실패 시 설치된 artifact를
rollback하면 partial state window를 크게 줄일 수 있다. 그러나 ordinary filesystem에서
두 개의 서로 다른 file을 하나의 atomic operation으로 commit할 수는 없다. 두 replace
사이의 process/machine crash에는 하나만 보일 가능성이 남는다.

### 7. Path check와 descriptor-level TOCTOU는 다르다

Execution ID single-component validation과 symlink/final-target rejection은 명백한 unsafe
path를 막는다. 새 `0700` directory도 cross-user race surface를 크게 줄인다. 하지만
path check와 use 사이 race를 descriptor 수준에서 제거하려면 `openat()`/`O_NOFOLLOW`
같은 별도 hardening이 필요하다. 이번 변경이 모든 TOCTOU를 해결했다고 주장해서는 안 된다.

### 8. Real deterministic Local smoke

`/tmp/aira-result-permission-smoke`의 실제 smoke에서 user-managed root `0775`는 그대로
유지되고 새 execution directory는 `0700`, report/result는 각각 `0600`이었다.
`source.md`의 `0664`는 사용자가 만든 input mode이며 writer artifact policy와 별개다.
Deterministic Local Research는 성공했고 report 1099 bytes와 parse 가능한 JSON 33474 bytes를
생성했다.

### 검증과 다음 학습 목표

- ResearchResultWriter focused tests: `18 passed`
- authoritative independent affected-suite re-audit: `90 passed`
- implementation task의 다른 test-file 조합: `98 passed`
- broader research regression: `104 passed`
- Ruff, format check 및 `git diff --check`: 통과

다음 학습 및 구현 목표는 `Parsed Document Cache`이다.


---

## 2026-08-16 — Parsed Document Cache: content identity, filesystem identity, authorization은 서로 다른 경계다

### 1. Content identity와 filesystem identity를 분리한다

같은 bytes가 `/data/a.pdf`와 `/archive/copy.pdf`에 있으면 parsing 계산 결과는 같을 수 있지만
현재 filesystem provenance는 다르다. 그래서 reusable `ParsedLocalDocument`에는 normalized
content, content type, section range 및 PDF/HWPX structural provenance만 넣고 path, filename,
source ID와 pseudo-URL은 넣지 않았다.

```text
raw SHA-256 + raw size + parser identity
→ reusable parsed content

current validated path + input position
→ current source/document identity
```

Cache hit 뒤 `LocalDocumentAdapter`가 현재 path에서 runtime identity를 다시 만들기 때문에
동일 bytes를 다른 path에서 재사용해도 이전 path가 새 result에 섞이지 않는다.

### 2. Cache hit는 권한을 만들지 않는다

Cache는 과거 계산 결과를 갖고 있을 뿐 현재 file을 읽을 권한이나 외부 provider로 보낼
권한을 증명하지 않는다. 따라서 deterministic, semantic 및 Integrated Local 모두 cache보다
먼저 fresh `LocalDocumentAccessGate`를 통과한다. Semantic/Integrated는 fresh identity에
approval을 다시 확인한 뒤에만 cache를 사용한다.

External provider 직전에는 source를 다시 hash하고 approval을 다시 검증한다. Parsing 이후
provider composition 사이에 file이 바뀌는 practical TOCTOU window를 줄이기 위해서다. Cache
entry가 이미 있어도 stale approval이나 changed bytes는 이 경계를 통과하지 못한다.

### 3. Same-key compute lock은 cache stampede를 막는다

두 process가 같은 miss를 동시에 보면 둘 다 PDF/HWPX를 parse하는 cache stampede가 생길 수
있다. Global lock은 서로 다른 document까지 막으므로 key별 `fcntl` lock을 사용했다.

```text
Process A: exclusive key lock → recheck → parse → persist → unlock
Process B: wait → recheck → persistent hit
```

Locked handle이 lock 없는 내부 `get`/`put`을 제공해 같은 process가 public lock API를 다시
호출하는 nested-lock 문제를 피했다. 실제 two-process test에서 underlying parse는 한 번만
기록되었다.

### 4. Parsed cache, embedding cache, vector index는 다르다

- Parsed Document Cache는 decoding, PDF page extraction 및 HWPX ZIP/XML parsing을 피한다.
- Persistent Semantic Embedding Cache는 exact text의 vector 계산을 피한다.
- Vector index/database는 어떤 document를 찾을지 결정하는 retrieval structure다.

```text
raw document
→ access validation
→ Parsed Document Cache
→ evidence text
→ Persistent Semantic Embedding Cache
→ semantic ranking
```

이번 Stage 4 구현은 앞의 두 cache이며 Stage 6 persistent VectorStore/vector database 완료를
의미하지 않는다.

### 5. Real persistent hit와 permission smoke

Isolated `XDG_CACHE_HOME=/tmp/aira-parsed-cache-smoke`에서 같은 deterministic Local request를
두 번 실행했다. 첫 실행 뒤 parsed JSON은 1개였고 두 번째 실행 뒤에도 같은 1개였다. 두
실행 모두 report/result를 생성했다. Cache directory는 `0700`, JSON과 lock은 `0600`이었다.

자동화된 second-instance test는 새 handler, 새 cache 및 새 parser를 사용해 두 번째 parser
call이 없음을 직접 확인했다. PDF/HWPX runtime test도 두 번째 extraction이 실행되지 않으면서
page/body-section provenance가 그대로 유지됨을 검증했다.

### 6. Test도 cache location을 격리해야 한다

Runtime default를 테스트하면 의도하지 않게 실제 user cache에 fixture entry가 남을 수 있다.
Handler/CLI test는 `XDG_CACHE_HOME`을 `tmp_path`로 설정하고 subprocess에도 isolated environment를
전달해야 한다. Test isolation도 persistent-state 설계의 일부다.

### 검증과 다음 학습 목표

- Step 3 focused: `64 passed`
- Step 1–3 regression: `168 passed`
- Step 4 focused: `75 passed`
- full repository pytest: `4955 passed`
- full Ruff 및 `git diff --check`: 통과
- changed Python format: `14 files already formatted`

다음 학습 목표는 cache lifecycle/eviction/maintenance architecture audit이다. 이후 remaining
Local format/safety work와 Patent Research Vertical Slice를 진행한다.

## 2026-08-16 — Persistent Cache Lifecycle: 관찰, 계획, 삭제 권한은 서로 다르다

### 1. Observation, plan, mutation은 다른 계약이다

```text
filesystem
→ CacheStatus observation
→ CachePrunePlan pure computation
→ CachePruneResult actual mutation
```

Status는 concurrent writer가 있을 수 있는 observational view이고 transactional snapshot이
아니다. Plan은 target까지 지울 valid entry를 계산하지만 deletion authorization이 아니다.
이 lifecycle은 다음 authoritative boundary와도 분리된다.

```text
Local source validation / external-send approval
≠ cache authorization
```

Cache hit가 source access나 send permission을 만들지 않듯 prune plan도 pathname을 삭제할
권한을 만들지 않는다.

### 2. Mutation에는 lock과 revalidation이 필요하다

Execution은 candidate가 같은 regular non-symlink final JSON이고 size/mtime/identity가 여전히
일치하는지 다시 확인한다. Embedding cache는 global exclusive lock, Parsed cache는 per-entry
exclusive lock을 쓴다. Parsed lock pathname을 unlink하면 새 inode가 생겨 서로 다른 process의
`flock` coordination이 갈라질 수 있으므로 lock file은 보존한다.

### 3. Target과 mtime은 quota/LRU가 아니다

Manual target은 operational target이지 concurrent hard quota가 아니다. `mtime_ns`는
successful-write recency이며 access recency가 아니므로 true LRU가 아니다. Hit마다 access
metadata를 쓰지 않아 read path와 lock contention도 늘리지 않았다.

### 4. Regenerable cache의 non-transactional 삭제

Cache content는 재생성 가능하므로 여러 entry 삭제를 transaction처럼 rollback하지 않는다.
중간 실패 전 mutation은 유지하고 partial state를 명시적으로 보고한다. Unlink 뒤 directory
`fsync`가 durable success에 필요하며, 실행 후 fresh inventory가 최종 source of truth다.
Corrupt/temp/unknown/lock file은 보고하지만 자동 삭제하지 않는다.

Cache lifecycle은 계산 결과의 disk growth를 관리한다. 어떤 document를 검색할지 관리하는
retrieval/index lifecycle은 별도 Stage 6 문제다.

### 검증과 다음 학습 목표

- maintenance focused: `62 passed`
- cache CLI: `11 passed`
- existing CLI regression: `51 passed`
- broader cache/CLI regression: `229 passed`
- isolated smoke, dry-run no-mutation 및 actual prune: 통과
- lock/corrupt/temp/unknown 보존과 repopulation: 통과
- full repository pytest: `5028 passed in 23.31s`
- Ruff: 통과
- changed Python format: `7 files already formatted`
- `git diff --check`: 통과

다음 학습 목표는 remaining Local format/safety expansion이며, 그 뒤 Patent Research Vertical
Slice를 진행한다.

## 2026-08-16 — Stage completion은 모든 checklist 소진이 아니라 product capability 계약으로 판단한다

### 1. Stage goal은 계약이다

Stage는 가능한 기능을 모두 구현하는 무한 backlog가 아니다. Stage 4의 계약은 Local 문서를
안전하게 읽고 provenance를 보존해 Web evidence와 함께 분석하는 것이었다. TXT/Markdown,
text-PDF, text-bearing HWPX baseline이 이 계약을 충족했고, 감사 결과 production-code
`MUST NOW` 항목은 남지 않았다.

### 2. Unsupported-but-safe failure도 baseline이다

Image-only PDF가 명확한 no-text error로 끝나고 HWP/DOCX가 지원되지 않는다고 일관되게
거절되는 것은 silent corruption보다 안전하다. 모든 format을 추가하는 것이 자동으로 더 좋은
architecture는 아니다. 실제 입력 evidence 없이 parser와 dependency를 늘리면 attack surface,
provenance contract 및 maintenance burden도 함께 늘어난다.

### 3. Security hardening은 threat model에 맞춘다

현재 raw SHA/size, allowed root, symlink rejection, per-execution approval 및 provider-near
revalidation은 single-user/local baseline을 구성한다. Descriptor-level race resistance가 완성된
것은 아니지만 hostile/shared deployment evidence가 없을 때 Stage closure를 막지는 않는다.
Threat model이 바뀌면 TOCTOU hardening을 다시 연다.

### 4. SHOULD와 DEFER는 evidence로 재개한다

HWP binary, structured tables 및 descriptor-bound reading은 가치가 있어 SHOULD NOW로
남긴다. OCR, Markdown heading provenance, classifier/redaction 및 persistent approval은 DEFER다.
이들은 scanned patent fixture, conversion loss, table-dependent conclusion, privacy review 같은
실제 evidence가 생길 때 재개한다.

### 5. Abstraction boundary를 Stage boundary와 맞춘다

Parsed/Embedding Cache는 계산 재사용이고 persistent vector retrieval/index와 Hybrid Retrieval은
다른 abstraction이다. 후자는 Stage 6에 남긴다. General Patent/academic/Web expansion은 Stage 5다.
Stage 4 안에서 이를 미리 완성하려 하면 실제 Patent Research Vertical Slice보다 Local optimization을
끝없이 앞세우게 된다.

Stage 4 baseline completion은 future Local capability 전체 완료가 아니다. Scope를 닫음으로써
이제 real product use인 Patent Research Vertical Slice에서 다음 필요를 관찰할 수 있다.

검증 기준선은 full pytest `5028 passed`, Ruff `All checks passed`, `git diff --check` 통과,
cache lifecycle isolated/repopulation smoke 통과 및 기존 Local/Integrated real smoke 통과이다.

## 2026-08-17 — Patent Provider Foundation: Mock PASS와 External Contract PASS는 다르다

### 1. Mock test는 provider의 실제 contract를 증명하지 않는다

Step 2B synthetic tests가 통과한 뒤 공식 OPS contract와 다시 대조하면서 `/search → /search/biblio`, `Range query → X-OPS-Range`, space `+ → %20` 차이를 발견했다.

```text
mock PASS ≠ external API contract PASS
```

외부 Provider integration은 `official documentation + mock/unit tests + bounded real smoke`의 세 층으로 검증해야 한다.

### 2. Discovery와 verification은 다르다

Tavily나 official-domain URL은 candidate discovery에 유용하지만 verified record를 뜻하지 않는다. EPO에서는 bibliographic DOCDB identity와 publication-specific abstract identity가 정확히 일치해야 VERIFIED로 승격한다.

### 3. Provider-specific representation을 generic identity에 섞지 않는다

EPO DOCDB request representation은 EPO adapter가 보존하고 generic publication normalizer는 conservative identity 역할만 유지한다.

### 4. XML safety는 transport와 parser를 함께 설계한다

```text
HTTPS exact host → OAuth → timeout/byte limit → MIME → defusedxml → namespace-aware parse
```

### 5. Live smoke가 architecture hypothesis를 실제 capability로 바꾼다

```text
query = ab=energy
maximum_results = 1
publication_number = US20260238012A1
publication_docdb = US.20260238012.A1
abstract_chars = 878
verification_state = verified
RESULT = PASS
```

Secret과 abstract 원문은 출력하지 않았다.

### 6. Technical relevance와 legal conclusion은 별도 capability다

Structured metadata/abstract verification은 novelty, invalidity, obviousness, infringement 또는 FTO 판단과 동일하지 않다.

### 검증과 다음 학습 목표

```text
Step 1 / 2A / 2B / 2C / 2D = FINAL PASS
Step 2B affected regression = 138 passed
Step 2C focused = 73 passed
Patent affected regression = 150 passed
Ruff / format / diff-check = PASS
EPO live smoke = PASS
```

마지막 full-repository accepted baseline은 `5028 passed`이며, 새 full regression은 checkpoint commit 전에 실행한다.

다음 목표는 `PatentResearchHandler` orchestration이다.

## 2026-08-17 — PatentResearchHandler: orchestration과 planning을 분리한다

### 1. Handler는 manager이지 provider/parser가 아니다
이미 검증된 searcher → abstract retriever → verified adapter를 얇게 연결했다. OAuth, XML parsing, DOCDB verification을 Handler에서 다시 구현하지 않았다.

### 2. 자연어 → CQL은 orchestration이 아니다
`PatentResearchRequest`에는 question/objective가 있지만 EPO searcher는 explicit CQL을 요구한다. 이 간극을 Handler 안에서 임의 변환하지 않고 다음 planning contract로 남겼다.

### 3. bounded는 input과 output 모두의 invariant다
exact request binding, provider record-count bound, selected candidate와 verified result의 identity/order 일치를 모두 검증한다.

### 4. VERIFIED 이름은 schema invariant로 보호한다
`EpoOpsVerifiedPatentRecord`가 EPO OPS source family와 VERIFIED state를 직접 강제한다.

### 5. partial recovery는 error taxonomy 뒤에 온다
현재 abstract error가 여러 failure type을 묶고 있으므로 broad `except: continue`를 도입하지 않았다.

### 검증
- focused final: `63 passed`
- Patent/EPO affected: `159 passed`
- full repository: `5170 passed`
- Ruff / format / diff-check: PASS

다음 학습 목표는 자연어 patent request를 structured patent query와 연결하는 planning/integration boundary다.

## 2026-08-17 — Patent Query Planning: provider query language를 일반 검색어와 분리한다

### 1. 같은 문자열 타입이어도 같은 abstraction은 아니다
일반 Web query의 `query_text`와 EPO CQL은 둘 다 문자열이지만 의미와 validation contract가 다르다.

### 2. 생성 전에 안전한 출력 계약을 먼저 만든다
자연어→CQL generation보다 먼저 `PatentSearchQueryPlan`을 만들었다.

### 3. 모르는 semantics를 과도하게 normalize하지 않는다
outer whitespace exact duplicate만 차단하고 case/semantic normalization은 하지 않았다.

### 4. type hint만으로 runtime contract가 보장되지는 않는다
`Sequence[str]`에 Python `str`도 포함되므로 bare string을 별도로 거부했다.

### 5. 테스트 fixture도 검증 대상이다
초기 control-character 테스트는 escaping 실수로 실제 제어문자가 아니라 literal backslash sequence를 만들었다. 실패 원인을 validator와 fixture로 분리하여 수정했다.

### 검증
- focused final: `45 passed`
- Patent affected regression: `154 passed`
- full repository: `5195 passed`
- Ruff / format / diff-check: PASS

다음 학습 목표는 natural-language patent request에서 bounded technical search concepts를 생성하되, 최종 실행 전에 Step 3B1 plan contract를 통과시키는 것이다.

## 2026-08-17 — Patent Technical Concept Planning: 생성보다 grounding을 먼저 강제한다

### 1. natural-language planning이 반드시 자유 생성일 필요는 없다
첫 slice에서는 LLM에게 동의어, 번역어, classification, CQL을 만들게 하지 않고 사용자의 request 안에 이미 있는 technical terminology만 구조화해 선택하도록 제한했다.

### 2. structured output 뒤에도 deterministic validation이 필요하다
`PatentTechnicalConceptSelection`이 schema-valid해도 최종 `PatentTechnicalConceptPlan`은 모든 term이 원래 `question`/`objective`에 실제 존재하는지 로컬에서 다시 확인한다.

### 3. domain contract와 provider adapter를 분리한다
OpenAI Responses Structured Outputs는 `OpenAIPatentTechnicalConceptGenerator` 안에 머문다. Domain plan은 OpenAI response object를 포함하지 않는다.

### 4. fake API fixture는 실제 helper contract를 먼저 읽어야 한다
초기 refusal test는 `type="refusal"`을 가정해 두 번 실패했다. 실제 `has_refusal()` 구현은 `content_item.refusal` truthiness를 검사했고, 기존 passing test의 fixture shape를 확인한 뒤 수정했다.

### 5. atomic patch는 실패 전에 모든 anchor를 검증해야 한다
첫 test-hardening script는 anchor mismatch로 쓰기 전에 중단했고 repo state를 보존했다. 이후 더 단순한 anchor로 다시 실행했다.

### 6. strict schema는 실제 JSON path로도 검증해야 한다
Python enum 객체를 직접 넣은 fake test만 믿지 않고 `model_validate_json()`으로 `"role": "primary"` / `"alternate"` structured-output JSON parsing을 추가 검증했다.

### 7. live validation은 correctness와 efficiency를 분리해서 본다
실제 `gpt-5` 1-call smoke는 PASS했지만 작은 concept-selection 작업에 1599 tokens, 20.426초가 사용되었다. 이것은 Step 3B2 correctness blocker는 아니며 후속 optimization 관찰값이다.

### 검증
- focused final: `66 passed`
- Patent/OpenAI affected regression: `212 passed`
- full repository: `5224 passed`
- Ruff / changed-file format / diff-check: PASS
- bounded OpenAI Structured Outputs live smoke: PASS

다음 학습 목표는 grounded technical concepts를 bounded EPO CQL candidate로 변환하되, CQL syntax generation과 D-064 `PatentSearchQueryPlan` validation/execution semantics를 분리하는 것이다.

## 2026-08-18 — Deterministic EPO CQL Planning: 문법 생성과 검색 품질을 분리한다

### 1. provider query syntax를 LLM에게 맡길 필요가 없다
Step 3B2에서 term이 이미 request-grounded되어 있으므로 Step 3B3는 deterministic renderer만으로 EPO CQL을 만들 수 있다.

### 2. 같은 입력은 같은 query를 만들어야 한다
`EpoOpsPatentCqlPlanner`는 concept order와 term order를 그대로 보존하고 hidden rewrite나 semantic normalization을 하지 않는다.

### 3. provider-specific syntax 뒤에도 domain contract를 다시 통과시킨다
생성된 CQL은 바로 실행하지 않고 D-064 `PatentSearchQueryPlanner`를 통해 `PatentSearchQueryPlan`으로 검증한다.

### 4. 날짜 filter와 법률 판단을 섞지 않는다
`prior_art_cutoff_date`는 `pd < YYYYMMDD`라는 exclusive publication-date retrieval bound로만 사용한다. 이것만으로 법률상 prior art 여부를 확정하지 않는다.

### 5. fail-fast policy는 의미를 명확히 해야 한다
`"`, `*`, `?`, `#`는 CQL metacharacter ambiguity 때문에 first-slice에서 차단한다. non-ASCII 차단은 EPO의 protocol restriction이 아니라 automatic translation을 아직 허용하지 않는 AIRA local policy다.

### 6. 문법적으로 유효한 query가 좋은 검색 결과를 보장하지 않는다
Live smoke의 `ta all "pressure sensor" and pd < 20260818`은 EPO에서 정상 실행됐지만 seat occupancy와 무관한 intraocular pressure sensor 문헌을 반환했다. Syntax correctness와 retrieval precision은 서로 다른 evaluation 대상이다.

### 7. retrieval precision은 upstream와 downstream이 함께 책임진다
Upstream Step 3B2가 더 구체적인 grounded concept를 선택하고, downstream technical-relevance evaluator가 실제 evidence relevance를 판정해야 한다.

### 검증
- focused contract: `53 passed`
- Patent/EPO affected regression: `158 passed`
- full repository: `5234 passed`
- Ruff / changed-file format / diff-check: PASS
- bounded EPO OPS live smoke: PASS
- request round-trip: PASS
- maximum results: 1

다음 학습 목표는 planning 결과를 `PatentResearchHandler` 실행 경로에 안전하게 연결하면서 PRIMARY/ALTERNATE budget/fallback과 transport bounds를 명시하는 것이다.

## 2026-08-18 — Patent Planning-to-Execution: fallback은 실패 은폐가 아니라 bounded retrieval policy다

### 1. query plan과 query execution은 별도 책임이다
`PatentSearchQueryPlan`이 PRIMARY/ALTERNATE 역할을 정의해도 그것만으로 실행 순서가 정해지는 것은 아니다. Step 3C에서 별도 `PatentResearchPlanExecutor`를 두어 runtime semantics를 명시했다.

### 2. ALTERNATE는 provider failure recovery가 아니다
PRIMARY가 정상적으로 실행되어 VERIFIED result가 0건일 때만 ALTERNATE를 실행한다. 인증, network, rate limit, MIME/XML, identity, abstract retrieval 실패는 fallback으로 감추지 않고 그대로 fail-fast한다.

### 3. request-level bound는 transport creation 시점에 binding해야 한다
`PatentResearchRequest.maximum_bytes`를 Handler 안에서 소비하지 않고 `EpoOpsPatentRuntime`이 `EpoOpsConfig.maximum_response_bytes`로 binding한다. 이로써 request policy와 HTTP response bound가 같은 runtime execution에 묶인다.

### 4. 서로 다른 provider 설정을 억지로 하나의 Settings에 넣지 않는다
현재 `Settings`는 OpenAI 필수값과 결합되어 있다. EPO config를 여기에 강제로 포함하면 EPO-only execution에도 OpenAI 설정이 필요해지는 잘못된 coupling이 생긴다. OpenAI settings와 EPO credential/config는 분리 유지했다.

### 5. end-to-end runtime도 단계별 request binding을 재검증한다
concept generation plan, CQL query plan, execution collection이 모두 원래 `PatentResearchRequest`와 동일한지 확인한다. 단계별 component가 독립적으로 맞아도 composition에서 request drift가 생길 수 있기 때문이다.

### 6. smoke script도 production schema를 추측하면 안 된다
첫 end-to-end smoke는 실제 VERIFIED record 생성까지 성공했지만 출력 코드가 존재하지 않는 `first.abstract.abstract_text`를 읽어 마지막 줄에서 실패했다. 실제 schema를 확인해 `first.abstract_text`로 수정한 뒤 전체 PASS를 확인했다. Test/smoke utility도 production schema audit 대상이다.

### 7. end-to-end PASS와 retrieval relevance는 여전히 다르다
전체 chain이 성공해도 반환 문헌이 질문에 기술적으로 적합한지는 별도 평가 문제다. Source identity verification과 technical-relevance evaluation을 분리해야 한다.

### 검증
- focused integration: `166 passed`
- Patent/EPO broader regression: `178 passed`
- full repository: `5254 passed`
- Ruff / changed-file format / diff-check: PASS
- bounded end-to-end live smoke: PASS
- request binding: PASS
- VERIFIED record: PASS

최종 live smoke는 `gpt-5` concept planning, deterministic CQL, PRIMARY execution, EPO search/abstract retrieval, VERIFIED mapping을 한 번에 통과했다.

다음 학습 목표는 patent source의 technical-relevance evidence/evaluation/synthesis contract를 설계하는 것이다.


## 2026-08-18 — Patent Technical Relevance: VERIFIED와 Relevant는 다른 판정이다

### 1. VERIFIED source와 relevant evidence는 다른 상태다

EPO OPS의 `VERIFIED` record는 publication identity, metadata, abstract source binding이 source-specific contract를 통과했다는 뜻이다.

그 문헌이 사용자의 기술 질문에 실제로 유용한지는 별도 문제다.

```text
verified source identity
≠ technical relevance
≠ legal conclusion
```

Budget exhaustion 등으로 semantic judgment가 완료되지 않은 passage는
`UNEVALUATED`로 구분하며, 이를 technical relevance 판정으로 간주하지 않는다.

### 2. 새 vertical slice를 만들 때 기존 generic capability 재사용 가능성을 먼저 확인한다

Patent 전용 evidence extractor와 relevance evaluator를 새로 만드는 대신 기존 generic semantic evidence stack을 audit했다.

확인한 결과:

- `ResearchSourceDocument`는 generic metadata와 readable content를 수용한다.
- `ResearchEvidence`는 exact excerpt/character provenance를 강제한다.
- `SemanticResearchEvidenceExtractor`는 paragraph candidate → embedding shortlist → semantic rerank 구조를 이미 제공한다.
- `OpenAIEvidenceRelevanceEvaluator`는 question/objective/passage만 사용하며 truth/source authority를 평가하지 않는다.

따라서 필요한 것은 새 parallel pipeline이 아니라 다음 thin adapter였다.

```text
EpoOpsVerifiedPatentRecord
→ ResearchSourceDocument
```

### 3. Domain-specific provenance와 generic semantic analysis를 분리할 수 있다

Patent adapter는 publication number, source family, verification state, publication date, source URL, executed CQL provenance를 보존한다.

그 위의 generic evidence layer는 patent provider semantics를 알 필요 없이 passage가 question/objective에 기여하는지만 판단한다.

### 4. Exact character provenance는 report 이전에 확보해야 한다

abstract 원문을 그대로 `ResearchSourceDocument.content`에 넣었기 때문에 final evidence는 다음을 만족한다.

```text
document.content[start_character:end_character] == evidence.excerpt
```

Live smoke에서도:

- `CN122100948A`: `0:1066`
- `WO2026157301A1`: `0:1140`

으로 exact provenance가 유지되었다.

### 5. 테스트 fixture도 실제 production schema를 따라야 한다

첫 Step 3D1 테스트는 adapter가 실행되기 전에 `EpoOpsBibliographicRecord` fixture가 실패했다.

실제 schema가 요구하는 `source_endpoint`, `document_id_type`을 fixture가 빠뜨린 것이 원인이었다.

교훈:

> Test double과 fixture도 production schema의 consumer다.

### 6. Patch utility 자체도 검증 대상이다

Step 3D3 patch script에 Python 문법 오류가 있어 repo 변경 전에 실행이 중단되었다.

수정본은 전달 전에 `py_compile`로 syntax validation했다.

Source code뿐 아니라 migration, patch, smoke, audit utility도 실행 가능한 artifact이므로 최소 syntax/preflight 검증이 필요하다.

### 7. Offline integration과 live smoke의 역할이 다르다

Offline controlled test에서는 seat-occupancy abstract를 `DIRECTLY_RELEVANT`, intraocular-pressure abstract를 `IRRELEVANT`로 만들어 filtering semantics를 deterministic하게 검증했다.

Live smoke에서는 실제 EPO + OpenAI 경로가 다음 결과를 냈다.

```text
concept_count     = 2
query_count       = 2
attempted_queries = PRIMARY
verified_records  = 2
document_count    = 2
evidence_count    = 2
request_binding   = true
RESULT            = PASS
```

실제 evidence:

- `CN122100948A`
  - `directly_relevant`
  - score `0.86`
- `WO2026157301A1`
  - `directly_relevant`
  - score `0.8`

Offline test는 policy semantics를 증명하고, live smoke는 external provider/runtime integration을 증명한다.

### 8. Full regression이 vertical slice 완료를 닫는다

```text
focused affected regression = 100 passed
full repository             = 5272 passed
Ruff                        = PASS
changed-file format         = PASS
git diff --check            = PASS
bounded live smoke          = PASS
```

이 결과로 Step 3D는 `FINAL PASS`다.

### 다음 학습 목표

다음은 Step 3E — Patent Synthesis / Report다.

목표는 traceable technical-relevance evidence를 citation/provenance를 잃지 않고 사람이 읽을 수 있는 bounded research report로 합성하는 것이다.

첫 report에서는 “technically relevant”, “potentially relevant prior art”, “cited excerpt appears to disclose …” 같은 제한적 표현만 사용하고 novelty/invalidity/obviousness/infringement/FTO/legal-status conclusion은 별도 후속 capability로 남긴다.

## 2026-08-18 — Patent Synthesis / Report: Relevant, Supported, Legal은 서로 다른 층이다

### 1. Generic evidence를 재사용해도 generic claim model을 억지로 재사용할 필요는 없다

Step 3E audit 결과 `ResearchClaim`은 일반 research assertion이고, `ResearchSynthesisReport`와 `DeterministicResearchSynthesizer`는 `ResearchClaimSet`을 필수 전제로 했다.

Patent domain에서는 “claim”이 특허 청구항이라는 별도 의미를 가지므로 다음 변환을 만들지 않았다.

```text
Patent evidence
→ generic ResearchClaim
→ generic synthesis report
```

대신:

```text
ResearchEvidenceSet
→ PatentTechnicalFinding
→ PatentTechnicalResearchReport
```

이라는 thin domain layer를 두었다.

교훈:

> 재사용은 schema까지 무조건 공유하는 것이 아니라, 책임이 실제로 같은 층까지만 공유해야 한다.

### 2. VERIFIED, Relevant, Supported는 모두 별도 판정이다

이번 단계까지 의미 층은 다음처럼 확장되었다.

```text
VERIFIED
= source identity / metadata / abstract binding

TECHNICALLY RELEVANT
= passage가 supplied question/objective에 기술적으로 기여함

FULLY SUPPORTED SYNTHESIS
= 생성된 요약문이 supplied evidence보다 강하지 않음

LEGAL CONCLUSION
= novelty, obviousness, invalidity, infringement, FTO 등
```

앞 단계 성공이 뒤 단계 성공을 자동으로 의미하지 않는다.

Live smoke에서 실제로:

- `CN118906928A`는 `partially_relevant`
- 하지만 그 문헌에 대한 synthesized summary는 `fully_supported`

였다.

이는 relevance와 support가 서로 다른 평가 축임을 실제 runtime에서 보여준다.

### 3. LLM output identity는 code가 소유해야 한다

각 `PatentTechnicalFinding`의 `finding_id`는 모델이 생성하지 않는다.

Synthesis model은 supplied ID를 그대로 copy해야 하며 누락/추가/중복/변경 중 하나라도 발생하면 fail-fast한다.

이 패턴은 기존 batch evaluator의 `item_id` ownership과 같다.

### 4. Synthesis 뒤에 별도 entailment verification이 필요하다

Prompt에 “evidence만 사용하라”고 적는 것만으로는 충분하지 않다.

Step 3E3에서는 기존 `OpenAISemanticCitationEvaluator`를 재사용하여:

```text
technical_summary
↔ exact evidence excerpt
```

를 다시 평가했다.

Overall summary는 모든 selected evidence를 결합한 text와 비교했고, `FULLY_SUPPORTED`만 최종 accept 대상으로 두었다.

### 5. zero-finding path는 deterministic해야 한다

초기 구현에서는 finding이 0개여도 OpenAI synthesizer를 호출했다.

Verifier는 zero-finding 상태를 exact deterministic sentence로 확인했으므로, 모델이 같은 의미를 다른 표현으로 쓰면 불필요하게 실패할 수 있었다.

수정 후:

```text
finding_count == 0
→ no LLM call
→ deterministic zero-finding synthesis
```

로 바꾸었다.

교훈:

> 모델이 필요 없는 상태 설명까지 모델에게 맡기면 비결정성과 비용만 늘어난다.

### 6. style validation도 patch workflow의 일부다

Step 3E1~3E4 patch는 기능 테스트가 통과한 뒤에도 여러 차례 Ruff import-order / formatter failure가 발생했다.

또 Step 3E3에서는 patch artifact 생성 환경에서 `ruff` 실행 권한 문제로 사전 formatter 검증을 완료하지 못했다.

Step 3E4 zero-finding fix에서는 리스트 내부 implicit string concatenation이 `ISC004`에 걸렸다.

교훈:

- `py_compile`은 syntax만 검증한다.
- repository patch는 Ruff import rules와 formatter까지 별도 확인해야 한다.
- patch utility와 smoke utility도 production artifact와 같은 수준으로 검증해야 한다.
- 사전 Ruff 실행이 불가능한 환경이면 사용자 repo에서 `ruff check --fix` / `ruff format`을 명시적인 첫 검증 단계로 둔다.

### 7. bounded live smoke는 최종 의미 경계까지 검증해야 한다

Step 3E5는 실제 EPO + OpenAI를 다음 전체 경로로 실행했다.

```text
natural-language PatentResearchRequest
→ grounded technical concepts
→ deterministic EPO CQL
→ EPO OPS
→ VERIFIED records
→ semantic evidence
→ deterministic report
→ bounded synthesis
→ semantic support verification
```

Live result:

```text
VERIFIED records = 2
evidence         = 2
findings         = 2
unevaluated      = 0
accepted         = True
```

문헌:

- `CN118906928A`
  - `partially_relevant`
  - relevance score `0.620`
  - synthesis support `fully_supported`
- `WO2023156109A1`
  - `directly_relevant`
  - relevance score `0.860`
  - synthesis support `fully_supported`

Overall synthesis도 `fully_supported`, score `0.980`이었다.

모든 request/report/finding binding contract가 PASS했다.

### 8. accepted=True는 법률 결론이 아니다

이번 Step의 가장 중요한 안전 경계:

```text
accepted=True
= generated synthesis is fully supported by supplied evidence
```

다음을 의미하지 않는다.

```text
novel
patentable
non-obvious
valid
non-infringing
free to operate
```

따라서 Patent Vertical Slice는 technical research assistant로 남으며, authoritative legal-analysis layer가 없는 상태에서 법률 결론을 과장하지 않는다.

### 9. Full regression이 Step 3E를 닫는다

최종 검증:

```text
Step 3E affected regression = 42 passed
full repository             = 5296 passed
Ruff                        = PASS
changed Python format       = PASS
git diff --check            = PASS
bounded live EPO + OpenAI   = PASS
```

이 결과로 Step 3E — Patent Synthesis / Report는 `FINAL PASS`다.

### 다음 학습 목표

다음은 Step 3F — Patent CLI Integration이다.

목표는 이미 검증된 top-level runtime을 CLI에 얇게 연결하고, 사용자가 verified metadata / technical relevance / provenance / synthesis / verification / scope notice를 명확히 구분해 볼 수 있도록 하는 것이다.

그 다음 Step 3G에서 실제 사용자 관점 UAT를 수행한다.

## 2026-08-18 — Patent CLI Integration: CLI는 runtime의 창이지 새로운 reasoning layer가 아니다

### 1. CLI integration은 새 business logic을 만들 이유가 없다

Step 3E에서 이미 top-level Patent runtime이 완성되었으므로 Step 3F의 역할은 다음뿐이다.

```text
CLI input
→ validated PatentResearchRequest
→ existing runtime
→ user-visible output
```

Query planning, provider search, source verification, relevance evaluation, synthesis, verification을 CLI에서 다시 구현하지 않았다.

교훈:

> 잘 설계된 runtime이 있으면 CLI는 얇아야 한다.

### 2. Domain validation을 CLI에서 복제하지 않는다

CLI는 positive integer와 ISO date 같은 presentation-level validation만 수행한다.

다음 bounded policy는 `PatentResearchRequest`가 계속 소유한다.

```text
maximum_search_results <= 8
maximum_sources <= 4
maximum_sources <= maximum_search_results
```

실제 test에서도 `maximum_search_results=1`, `maximum_sources=2`를 주면 handler 호출 전에 domain validation error가 발생했다.

### 3. 아직 존재하지 않는 persistence 기능을 CLI가 발명하면 안 된다

기존 Local/Live research command에는 `--output-dir`이 있지만 Patent Step 3E에는 별도 report writer/file persistence가 구현되어 있지 않다.

따라서 일관성을 가장한 가짜 기능을 추가하지 않고 first CLI slice는 stdout 전용으로 유지했다.

교훈:

> UI/CLI symmetry보다 실제 capability contract가 우선이다.

### 4. 의미 경계는 내부 schema뿐 아니라 사용자 화면에서도 보여야 한다

CLI는 다음 섹션을 분리했다.

```text
VERIFIED METADATA / TECHNICAL RELEVANCE
EVIDENCE / PROVENANCE
SYNTHESIS
SUPPORT VERIFICATION
SCOPE NOTICE
```

내부적으로 의미가 분리되어 있어도 사용자 출력에서 다시 섞이면 제품 수준에서는 경계가 무너진다.

### 5. credential fail-fast도 정상 동작의 일부다

첫 live CLI 실행은 다음으로 종료되었다.

```text
aira: error: EPO_OPS_CONSUMER_KEY is required
```

이는 CLI failure가 아니라 provider credential이 없는 shell 상태를 runtime이 정확히 드러낸 것이다.

Credential을 로컬에서 설정한 뒤 같은 command가 성공했다.

교훈:

- secret이 없으면 fail-fast한다.
- secret 값을 오류 메시지에 노출하지 않는다.
- provider failure를 fallback이나 빈 결과로 위장하지 않는다.
- operational configuration failure도 live validation scenario에 포함한다.

### 6. Live CLI smoke는 runtime 성공뿐 아니라 presentation contract도 확인해야 한다

실제 command:

```text
aira research-patent
```

결과:

```text
VERIFIED findings = 2
accepted          = true
```

문헌:

- `CN118906928A`
  - metadata: `verified`
  - relevance: `partially_relevant`
  - score: `0.720`
  - synthesis support: `fully_supported`
- `WO2023156109A1`
  - metadata: `verified`
  - relevance: `directly_relevant`
  - score: `0.840`
  - synthesis support: `fully_supported`

Overall synthesis support는 `fully_supported`, entailment score `0.950`이었다.

Evidence ID, source ID, document ID, exact character range, excerpt도 stdout에서 확인 가능했다.

### 7. 같은 문헌도 relevance score는 run마다 달라질 수 있다

Step 3E5와 Step 3F live run은 같은 두 publication을 찾았지만 semantic relevance score가 달랐다.

예:

```text
CN118906928A
Step 3E5 = 0.620
Step 3F  = 0.720
```

이는 LLM semantic evaluation score가 deterministic identity가 아니라 model judgment라는 점을 보여준다.

따라서 publication identity/provenance처럼 exact deterministic contract와 semantic score를 같은 안정성 수준으로 취급하면 안 된다.

### 8. accepted=true를 명시적으로 설명해야 한다

CLI 마지막에는 다음 문구를 출력한다.

```text
accepted=true means only that the generated technical synthesis
is fully supported by the supplied evidence.
```

그리고 scope notice에서 novelty, anticipation, obviousness, invalidity, infringement, FTO, current legal status를 명시적으로 제외한다.

이중 안내는 사용자가 acceptance를 patent-law approval로 오해하지 않도록 하기 위한 제품-level safety boundary다.

### 9. Full regression으로 Step 3F를 닫는다

최종 검증:

```text
focused CLI tests          = 55 passed
affected regression        = 73 passed
full repository regression = 5301 passed
Ruff                       = PASS
changed Python format      = PASS
git diff --check           = PASS
CLI help                   = PASS
bounded live CLI smoke     = PASS
```

이 결과로 Step 3F — Patent CLI Integration은 `FINAL PASS`다.

### 다음 학습 목표

다음은 Step 3G — Patent User Acceptance Test다.

이 단계에서는 새 기능을 먼저 만들지 않고 실제 사용자 입장에서:

- 입력이 이해 가능한지
- 오류가 actionable한지
- 결과가 읽기 쉬운지
- provenance를 추적할 수 있는지
- relevance/support/legal boundary가 명확한지

를 평가한다.

UAT 결과를 바탕으로 필요한 경우에만 CLI presentation 또는 contract를 수정한다.
