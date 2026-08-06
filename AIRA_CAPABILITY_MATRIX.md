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
| Live Web Search Adapter | No | No | No | No | 신규 구현 |
| ResearchSourceCandidate | Yes | Yes | Yes | Partial | 재사용 |
| ResearchSourceReader Port | Yes | Yes | Yes | Partial | 재사용 |
| InMemory Reader | Yes | Yes | Yes | No | Test Adapter 유지 |
| HTTP/HTML Reader | No | No | No | No | 신규 구현 |
| ResearchSourceDocument | Yes | Yes | Yes | Partial | 재사용 |
| ResearchSourceDocumentSection | Yes | Yes | Yes | Partial | 재사용 |
| Result Guardrail | Yes | Yes | Yes | Partial | 재사용 |
| Result Writer | Yes | Yes | Yes | Partial | Source Artifact 저장 확장 |
| OpenAI Responses Planner | Yes | Yes | No | No | 확장 후 재사용 |
| Strict Structured Output | Yes | Yes | No | Partial | 재사용 |
| Initial Planning | Yes | Yes | No | Partial | 재사용 |
| Replanning | Yes | Yes | No | Partial | 후속 연결 |
| Planner Usage 수집 | No | No | No | No | 기존 Usage Utility 연결 |
| Planner Timeout·Retry 정책 | Partial | Yes | No | No | 보강 |
| OpenAI Actual API Smoke Test | 미확인 | No | No | No | 검증 필요 |
| OpenAI Embedding Provider | Yes | Yes | No | Partial | RAG 감사 후 재사용 |
| Grounded Answer Service | Yes | Yes | No | Partial | RAG 감사 후 재사용 |
| Tool Interface | Yes | Yes | No | Partial | 후속 재사용 |
| Planning Tool Registry | Yes | Yes | No | Partial | 후속 재사용 |
| Plan Scheduler·Lifecycle | Yes | Yes | No | Partial | 후속 재사용 |
| PlanStepExecutor | Yes | Yes | No | Partial | Tool Arguments 보강 필요 |
| PlanExecutionService | Yes | Yes | No | Partial | 후속 재사용 |
| OpenAI Function Tool Registry | Yes | Yes | No | Partial | 별도 용도 유지 |
| Concrete Research Tools | No | No | No | No | 신규 구현 |
| Token Usage 추출 | Yes | Yes | No | Partial | 재사용 |
| Cached·Reasoning Token | Yes | Yes | No | Partial | 재사용 |
| ExecutionBudget | Yes | Yes | No | Partial | 재사용 |
| Attempt Budget | Yes | Yes | No | Partial | 재사용 |
| Token Budget | Yes | Yes | No | Partial | 재사용 |
| Time Budget | Yes | Yes | No | Partial | 재사용 |
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
| ConcreteAiraResearchRunner | No | No | No | No | 핵심 신규 통합 |
| Idempotency | Yes | Yes | No | Partial | 후속 연결 |
| Multi-Agent Schemas·Agents | Yes | Yes | No | No | Single-Agent 이후 평가 |
| RAG 전체 Runtime 연결 | Partial | Yes | No | No | 후속 감사 |
| Memory 전체 Runtime 연결 | Partial | Yes | No | No | 후속 감사 |
| 전체 pytest 기준선 | Yes | 4088 passed | 해당 없음 | 해당 없음 | 기준선 고정 |
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
