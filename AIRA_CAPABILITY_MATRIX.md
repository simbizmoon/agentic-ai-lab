# AIRA CAPABILITY MATRIX

## 1. 판정 기준

- **Implemented**: 실제 코드가 존재한다.
- **Tested**: 저장소 테스트 기준선에서 관련 테스트가 통과한다.
- **Runtime-connected**: 현재 기본 `aira research` 실행 경로에서 실제 사용된다.
- **Production-ready**: 실제 외부 자료·API, 운영 오류, 영속성, 비용 및 보안까지 검증되었다.

`Partial`은 일부 구현 또는 제한된 경로만 확인된 상태이다.

---

## 2. Matrix

| Capability | Implemented | Tested | Runtime-connected | Production-ready | 결정 |
|---|---:|---:|---:|---:|---|
| CLI Parser·Validation | Yes | Yes | Yes | Partial | 재사용 |
| LocalDocumentAdapter | Yes | Yes | Yes | Partial | 재사용 |
| Current Local Research Runtime | Yes | Yes | Yes | No | Offline Baseline 유지 |
| ResearchRequest | Yes | Yes | Yes | Partial | 재사용 |
| Deterministic Task Decomposer | Yes | Yes | Yes | No | Baseline·Fallback |
| Deterministic Query Planner | Yes | Yes | Yes | No | Baseline·Fallback |
| ResearchSearchQuery Schema | Yes | Yes | Yes | Partial | 재사용 |
| ResearchSourceSearchTool Port | Yes | Yes | Yes | Partial | 재사용 |
| InMemory Search | Yes | Yes | Yes | No | Test Adapter 유지 |
| Live Web Search Adapter | Yes | Yes | Yes (live CLI) | Partial | Tavily Adapter 운영·확장 |
| ResearchSourceCandidate | Yes | Yes | Yes | Partial | 재사용 |
| ResearchSourceReader Port | Yes | Yes | Yes | Partial | 재사용 |
| InMemory Reader | Yes | Yes | Yes | No | Test Adapter 유지 |
| HTTP/HTML Reader | Yes | Yes | Yes (live CLI) | Partial | 재사용·보강 |
| ResearchSourceDocument | Yes | Yes | Yes | Partial | 재사용 |
| ResearchSourceDocumentSection | Yes | Yes | Yes | Partial | 재사용 |
| Result Guardrail | Yes | Yes | Yes | Partial | 재사용 |
| Result Writer | Yes | Yes | Yes | Partial | Source Artifact 저장 확장 |
| OpenAI Responses Planner | Yes | Yes | Yes (live research) | Partial | 재사용 |
| Strict Structured Output | Yes | Yes | Yes (LLM evaluators/claim generation) | Partial | 재사용 |
| Initial Planning | Yes | Yes | No | Partial | 재사용 |
| Replanning | Yes | Yes | No | Partial | 후속 연결 |
| Planner Usage 수집 | Yes | Yes | Yes (bounded live components) | Partial | 재사용·확장 |
| Planner Timeout·Retry 정책 | Partial | Yes | No | No | 보강 |
| OpenAI Actual API Smoke Test | Yes | Yes | Yes | Partial | 반복 Live 검증 유지 |
| OpenAI Embedding Provider | Yes | Yes | Yes (semantic evidence shortlist) | Partial | 재사용 |
| Grounded Answer Service | Yes | Yes | No | Partial | RAG 감사 후 재사용 |
| Tool Interface | Yes | Yes | No | Partial | 후속 재사용 |
| Planning Tool Registry | Yes | Yes | No | Partial | 후속 재사용 |
| Plan Scheduler·Lifecycle | Yes | Yes | No | Partial | 후속 재사용 |
| PlanStepExecutor | Yes | Yes | No | Partial | Tool Arguments 보강 필요 |
| PlanExecutionService | Yes | Yes | No | Partial | 후속 재사용 |
| OpenAI Function Tool Registry | Yes | Yes | No | Partial | 별도 용도 유지 |
| Concrete Research Tools | Yes | Yes | Yes (search/read path) | Partial | 추가 Tool 확장 |
| Token Usage 추출 | Yes | Yes | No | Partial | 재사용 |
| Cached·Reasoning Token | Yes | Yes | No | Partial | 재사용 |
| ExecutionBudget | Yes | Yes | Yes (claim/relevance runtime) | Partial | 재사용 |
| Attempt Budget | Yes | Yes | Yes | Partial | 재사용 |
| Token Budget | Yes | Yes | Yes | Partial | 재사용 |
| Time Budget | Yes | Yes | Yes | Partial | 재사용 |
| Model Price Registry | 미확인 | No | No | No | 신규 또는 후속 감사 |
| Actual Cost 계산 | 미확인 | No | No | No | 신규 또는 후속 감사 |
| Agent Trace Event | Yes | Yes | No | Partial | 재사용 |
| Trace Session·Recorder | Yes | Yes | No | Partial | 재사용 |
| Trace Timeline·Summary | Yes | Yes | No | Partial | 재사용 |
| Trace Export·File Writer | Yes | Yes | No | Partial | 재사용 |
| ApplicationExecutionRecord | Yes | Yes | No | Partial | 재사용 |
| Execution Repository Port | Yes | Yes | No | Partial | 재사용 |
| InMemory Execution Repository | Yes | Yes | No | No | Test Adapter 유지 |
| Persistent Execution Repository | 미확인 | No | No | No | 초기 파일 저장, 후속 SQLite |
| ApplicationResearchExecutionService | Yes | Yes | No | Partial | 재사용 |
| ApplicationResearchFlowService | Yes | Yes | No | Partial | 후속 연결 |
| ConcreteAiraResearchRunner | Yes | Yes | Yes (live CLI) | Partial | 재사용 |
| Idempotency | Yes | Yes | No | Partial | 후속 연결 |
| Multi-Agent Schemas·Agents | Yes | Yes | No | No | Single-Agent 이후 평가 |
| RAG 전체 Runtime 연결 | Partial | Yes | No | No | 후속 감사 |
| Memory 전체 Runtime 연결 | Partial | Yes | No | No | 후속 감사 |
| Generative Claim Builder | Yes | Yes | Yes (live CLI) | Partial | 1 Evidence → 1 Claim 유지 |
| Semantic Citation Verification | Yes | Yes | Yes (live CLI) | Partial | Evaluated Capability, blocking 보류 |
| Claim Relevance Evaluation | Yes | Yes | Yes (live CLI) | Partial | Evaluated Capability, filtering 보류 |
| Evidence Relevance Evaluation | Yes | Yes | Yes (live CLI) | Partial | Evaluated Capability, blocking 보류 |
| Paragraph Evidence Candidate Exposure | Yes | Yes | Yes (live CLI) | Partial | 재사용 |
| Embedding Semantic Evidence Ranking | Yes | Yes | Yes (live CLI) | Partial | 재사용 |
| Lexical Evidence Ranking | Yes | Yes | Yes (live CLI) | Partial | 재사용 |
| RRF Hybrid Evidence Shortlist | Yes | Yes (focused 26 passed) | Yes (live CLI) | Partial | 채택, rrf_k=60 |
| Semantic Evidence Reranker | Yes | Yes | Yes (live CLI) | Partial | 재사용 |
| Precision-first Final Evidence Selection | Yes | Yes | Yes (live CLI) | Partial | 채택 |
| Research Search Provider Budget | Yes | Yes | Yes (live CLI) | Partial | Call/Credit/Latency 제한 |
| Provider-independent Source Type Classifier | Yes | Yes | Yes (live CLI) | Partial | 재사용 |
| Supplemental Research Replanning | Yes | Yes | Yes (conditional live path) | Partial | 최대 1회 유지 |
| 전체 pytest 기준선 | Yes | 4431 passed in 16.41s | 해당 없음 | 해당 없음 | Step 5.12 최종 Checkpoint |
| Ruff 기준선 | Yes | All checks passed | 해당 없음 | 해당 없음 | 기준선 고정 |

---

## 3. 즉시 재사용 집합

```text
ResearchRequest
ResearchSearchQuery / QuerySet
ResearchSourceSearchTool
ResearchSourceCandidate
ResearchSourceReader
ResearchSourceDocument / Section
OpenAI Planner Prompt·Validation
Token Usage Utility
ExecutionBudget
Agent Trace
ApplicationExecutionRecord
ApplicationResearchExecutionService
ResearchResultGuardrail
ResearchResultWriter
```

---

## 4. 첫 Vertical Slice 신규 집합

```text
Live Web Search Adapter
HTTP/HTML Source Reader
Source Artifact Writer
Application Request → ResearchRequest Adapter
ConcreteAiraResearchRunner
Live Composition Root
CLI Live Mode
Actual API Smoke Tests
```

---

## 5. 첫 Vertical Slice에서 제외

```text
Multi-Agent 기본 실행
전체 RAG 통합
Long-term Memory
PDF/HWP 고도화
범용 Plan Tool Loop 통합
FastAPI
Background Job
SQLite/PostgreSQL
복수 Search Provider
상용 Web UI
```

---

## 6. 2026-08-08 Capability 상태 갱신

### Live Research 핵심 경로

현재 실제 Live CLI 경로는 다음 Capability를 사용한다.

```text
Research Request
→ Task / Query Planning
→ Tavily Live Web Search
→ HTTP/HTML Reading
→ Source Type Classification
→ Source Quality Evaluation
→ Evidence-aware Selection / Supplemental Search
→ Paragraph Candidate Generation
→ Embedding + Lexical RRF Shortlist
→ LLM Semantic Evidence Relevance
→ Precision-first Final Evidence Selection
→ Generative Claim Construction
→ Semantic Citation Verification
→ Claim Relevance Evaluation
→ Report / Quality / JSON Artifact
```

### Evaluated Capability

다음 Semantic Capability는 구현, 테스트, Live Runtime 연결 및 별도 Eval을
수행하였다.

```text
Semantic Citation Verification
Claim Relevance Evaluation
Semantic Evidence Relevance
```

현재 공통 정책:

```text
Evaluation 결과
→ 관측·artifact·failure analysis에 사용

Blocking Quality Gate
→ 아직 보류
```

### 최근 Live 검증

OpenAI Agents SDK Tool Calling 질문의 RRF Hybrid Live Regression:

```text
Official source:
Tools - OpenAI Agents SDK

Evidence:
1 directly_relevant
2 partially_relevant
0 unevaluated

Citation verification:
3 / 3 fully_supported
3 / 3 verified

Claim relevance:
1 directly_relevant
2 partially_relevant

Deterministic quality:
0.8845
high
passed = true
```

### 주의

`Production-ready=Partial`은 기능이 Live에서 동작하지 않는다는 뜻이 아니다.

현재 남아 있는 주요 이유는 다음과 같다.

- 더 큰 Eval Dataset 필요
- 반복 Live 변동성 측정 필요
- Blocking Semantic Quality Gate 미적용
- 비용·보안·Provider 실패를 포함한 장기 운영 검증 부족
- 인터넷 + 로컬 문서 통합 전체 경로 미완료
- PDF/HWP/HWPX 및 Integrated RAG 전체 통합 미완료

### 최종 검증 Checkpoint

```text
전체 pytest = 4431 passed in 16.41s
Ruff = All checks passed
git diff --cached --check = passed
```

### 다음 Matrix 갱신 조건

다음 Checkpoint에서 다시 갱신한다.

- Semantic Relevance Blocking 정책 결정
- Local Document + Internet 통합 Runtime 연결
- Integrated RAG 통합
- 실제 사용자 Research Dataset 반복 평가

## 7. 2026-08-13 Capability Matrix 갱신

### 현재 Production / Evaluated Capability

| Capability | 상태 | 현재 역할 / 제한 |
|---|---|---|
| Live Web Search | Production path | Tavily, budgeted, serial |
| HTTP/HTML Source Reading | Production path | bounded parallel 가능, live default concurrency 2 |
| Source Quality / Selection | Production path | deterministic/quality-aware |
| Hybrid Retrieval | Production path | lexical + embedding/RRF 계열 |
| Semantic Evidence Relevance | Production/evaluated | high-judgment path, Local 4B로 무리하게 이전하지 않음 |
| Generative Claim Construction | Production path | high-judgment generation |
| Semantic Citation Verification | Production/evaluated | Qwen3.5-4B bounded first-pass 가능 |
| Claim Relevance | Production/evaluated | Qwen3.5-4B bounded classifier 가능 |
| Answer Coverage | Production/evaluated | Qwen3.5-4B reviewer/critic 가능, authoritative final gate 아님 |
| Bounded Coverage Replanning | Production path | 제한된 replanning |
| Local Worker Backend | Production path | qwen3.5:4b bounded roles |
| Multi-Agent Orchestrator | Available / conditional | default 아님, workload-dependent escalation |
| Hybrid Role Routing | Production architecture | deterministic + OpenAI/stronger + Local bounded worker |
| Source Read Parallelism | Production path | bounded, env-configurable 1..8, default 2 |
| Search Parallelism | Deferred | shared usage/budget safety 문제 |
| Local Worker Parallelism | Deferred | 현재 concurrency 1 유지 |

### Architecture Capability 판정

```text
Single-Agent default
→ ACCEPTED

Multi-Agent escalation
→ ACCEPTED WITH WORKLOAD CONDITION

Hybrid heterogeneous routing
→ ACCEPTED

Qwen3.5-4B universal Main Agent
→ NOT ACCEPTED

Bounded local worker
→ ACCEPTED

Bounded parallel source reading
→ ACCEPTED
```

### Phase 11 검증 Checkpoint

```text
Real HTTP source-reading semantics
→ identical across concurrency 1 / 2 / 4

Live runtime default
→ AIRA_SOURCE_READ_CONCURRENCY=2

Live smoke
→ quality 0.9345
→ 2/2 selected documents read
→ ollama-local provenance confirmed

Full regression
→ 4635 passed in 16.70s
→ Ruff clean
```

### 다음 Matrix 갱신 조건

다음 갱신은 Phase 12에서 hardware/model capacity 판단이 확정되거나 다음 중 하나가
실제 구현될 때 수행한다.

- larger local model production role 채택
- local worker parallelism 정책 변경
- search concurrency 안전 구조 도입
- integrated local-document + web RAG production path 확대
