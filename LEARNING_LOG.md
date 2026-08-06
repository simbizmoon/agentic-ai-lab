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
