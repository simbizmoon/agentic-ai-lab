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
