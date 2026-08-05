# Phase 10 — Multi-Agent Research System

## 1. 목적

Phase 10의 목적은 단일 Research Agent Workflow를 역할 기반 Multi-Agent Research System으로 확장하는 것이다.

각 Agent는 독립적인 역할, Capability, Assignment, Message, Result 및 Failure 계약을 가지며, Manager와 Orchestrator가 전체 연구 흐름을 조정한다.

Phase 10은 외부 LLM이나 Search API에 종속되지 않는 결정론적 실행 구조를 우선 구현한다.

---

## 2. 핵심 설계 원칙

### 2.1 역할 분리

각 Agent는 하나의 명확한 연구 책임을 가진다.

- Research Manager
- Search Specialist
- Source Reader
- Evidence Analyst
- Source Critic
- Citation Verifier
- Claim Analyst
- Synthesis Specialist
- Quality Reviewer

Agent 간 역할을 분리하여 검색, 읽기, 분석, 주장 생성, 합성 및 검토가 동일한 실행 주체에 집중되지 않도록 한다.

### 2.2 구조화된 계약

Agent 간 협업은 자유 형식 문자열이 아니라 Pydantic Schema를 사용한다.

주요 계약은 다음과 같다.

- Agent Identity
- Agent Role
- Agent Status
- Capability Profile
- Task Assignment
- Agent Message
- Message Delivery
- Task Result
- Structured Failure
- Shared Research Workspace

### 2.3 결정론적 실행

테스트에서 시간, ID, Executor 결과를 주입할 수 있도록 설계하였다.

이를 통해 외부 API 없이 다음 항목을 검증할 수 있다.

- Agent 선택
- Assignment 생성
- Message 전달
- Agent 실행
- Result 생성
- Failure 변환
- Review 및 Revision 반복
- Orchestration 종료 조건

### 2.4 추적 가능성

모든 주요 Artifact는 이전 단계의 Artifact를 참조한다.

대표적인 추적 흐름은 다음과 같다.

```text
Research Request
    → Search Result
    → Source Document
    → Evidence
    → Claim
    → Citation
    → Report
    → Quality Review

각 단계는 `request_id`, `workspace_id`, `assignment_id`, `parent_assignment_id`, Reference ID를 통해 연결된다.

### 2.5 독립 검토

검색과 출처 평가를 분리하고, Claim 생성과 Citation 검증을 분리하며, Report 합성과 Quality Review를 분리한다.

이를 통해 생성 Agent가 자신의 결과를 직접 승인하지 않도록 한다.

---

## 3. Phase 10 Lesson 구성

### Lesson 10.1 — Research Agent Identity and Role Schema

Agent의 ID, 이름, 역할, 설명 및 상태를 정의하였다.

### Lesson 10.2 — Agent Capability and Tool Permission Schema

Agent가 수행할 수 있는 기능과 위임 가능한 역할을 Capability Profile로 정의하였다.

### Lesson 10.3 — Agent Message Schema

Agent 간 Task Request, Result, Status, Review, Revision 등의 Message 구조를 정의하였다.

### Lesson 10.4 — Agent Task Assignment Schema

Manager가 Specialist에게 전달하는 작업 계약을 정의하였다.

Assignment에는 다음 정보가 포함된다.
- 요청 및 Workspace 식별자
- Assigner와 Assignee
- Required Role
- Required Capabilities
- Objective
- Instructions
- Inputs
- Expected Output
- Acceptance Criteria
- Priority
- Attempt 정보
- Parent Assignment
- Metadata

### Lesson 10.5 — Agent Result and Failure Schema

Agent 실행 결과, Output Reference, 실행 Metric 및 구조화된 Failure를 정의하였다.

### Lesson 10.6 — Shared Research Workspace Schema

여러 Agent가 공유하는 Research Workspace 구조를 정의하였다.

### Lesson 10.7 — Agent Registry

Agent Identity와 Capability Profile을 등록하고 검색하는 Registry를 구현하였다.

Registry는 다음 기능을 제공한다.

- Agent 조회
- Profile 조회
- Role별 Agent 조회
- 사용 가능한 Agent 조회
- 위임 가능 대상 조회
- 등록 중복 검증

### Lesson 10.8 — Agent Message Bus Contract

Message 발행, 수신, 처리 시작, 확인, 실패 및 취소에 대한 추상 계약을 정의하였다.

### Lesson 10.9 — In-Memory Agent Message Bus

결정론적 In-Memory Message Bus를 구현하였다.

Delivery 상태는 다음과 같이 전이된다.

```text
PENDING
    → DELIVERED
    → PROCESSING
        → ACKNOWLEDGED
        → FAILED
        → CANCELLED
```

Broadcast와 Direct Message를 지원하며 Priority와 발행 순서에 따라 Message를 수신한다.

### Lesson 10.10 — Research Manager Agent

Manager가 Registry에서 적절한 Specialist를 선택하고 Assignment와 Task Request Message를 생성하도록 구현하였다.
선택 조건은 다음과 같다.

- 위임 가능한 Role
- Agent 사용 가능 상태
- Required Capability 충족
- Registry 등록 순서

### Lesson 10.11 — Search Specialist Agent

Search Assignment를 검증하고 Search Executor를 호출하여 정규화된 Source Candidate Set을 생성하도록 구현하였다.

### Lesson 10.12 — Source Reader Specialist Agent

Source Reference를 읽어 정규화된 Document Set을 생성하도록 구현하였다.

전체 성공, 부분 성공 및 전체 실패 결과를 지원한다.

### Lesson 10.13 — Evidence Analyst Agent

Document에서 추적 가능한 Evidence를 추출하도록 구현하였다.

Evidence는 다음 식별자를 유지한다.

- Evidence ID
- Document ID
- Source ID
- Location Reference

### Lesson 10.14 — Source Critic and Citation Verifier Agents

Source Critic은 출처의 권위성, 관련성, 최신성 및 투명성을 평가한다.

Citation Verifier는 Claim, Citation, Evidence 및 Source 연결을 독립적으로 검증한다.

### Lesson 10.15 — Claim and Synthesis Specialist Agents

Claim Analyst는 Evidence를 기반으로 Claim과 Citation을 생성한다.

Synthesis Specialist는 Claim을 구조화된 Research Report로 합성한다.

Report는 다음 구조를 가진다.

- Title
- Executive Summary
- Sections
- Limitations
- Follow-up Questions

### Lesson 10.16 — Quality Reviewer Agent

최종 Report를 다음 기준으로 평가한다.

- Completeness
- Evidence Coverage
- Citation Quality
- Source Quality
- Logical Consistency
- Clarity

최종 판정은 다음 중 하나이다.

- APPROVED
- REVISION_REQUIRED
- REJECTED

### Lesson 10.17 — Review and Revision Loop

Synthesis Specialist와 Quality Reviewer를 반복적으로 연결하였다.

종료 상태는 다음과 같다.

- APPROVED
- REJECTED
- REVISION_LIMIT_REACHED
- SYNTHESIS_FAILED
- REVIEW_FAILED

수정 Assignment에는 이전 Report와 Quality Review가 Input으로 추가된다.

### Lesson 10.18 — Multi-Agent Research Orchestrator

다음 파이프라인을 하나의 실행 흐름으로 연결하였다.

```text
Search
    → Source Reading
    → Evidence Extraction
    → Claim Construction
    → Report Synthesis
    → Quality Review
    → Revision
```

이전 단계가 실패하면 이후 단계는 실행하지 않는다.

### Lesson 10.19 — Single-Agent and Multi-Agent Comparison

동일한 연구 요청에 대한 Single-Agent와 Multi-Agent 실행 결과를 비교하는 Evaluator를 구현하였다.

비교 Metric은 다음과 같다.

- Completion
- Output Availability
- Execution Step Count
- Participating Agent Count
- Tool Call Count
- Token Count
- Source Count
- Evidence Count
- Claim Count
- Revision Round Count
- Traceability Score
- Complexity Score

비교 결과는 Multi-Agent가 항상 우월하다고 가정하지 않는다.

최종 판단은 다음 중 하나이다.

- SINGLE_AGENT
- MULTI_AGENT
- CONTEXT_DEPENDENT

---

## 4. Multi-Agent 실행 흐름

```text
Research Request
        ↓
Research Manager
        ↓
Search Specialist
        ↓
Source Reader
        ↓
Evidence Analyst
        ↓
Claim Analyst
        ↓
Synthesis Specialist
        ↓
Quality Reviewer
        ├── APPROVED
        ├── REJECTED
        └── REVISION_REQUIRED
                    ↓
             Synthesis Specialist
                    ↺
```

Source Critic과 Citation Verifier는 독립 검토 계층으로 존재하며, 향후 Orchestrator 확장 시 병렬 또는 순차 검토 단계로 삽입할 수 있다.

---

## 5. 주요 파일

### Schema

- `app/schemas/research_agent.py`
- `app/schemas/research_agent_capability.py`
- `app/schemas/research_agent_message.py`
- `app/schemas/research_agent_assignment.py`
- `app/schemas/research_agent_result.py`
- `app/schemas/shared_research_workspace.py`

### Infrastructure

- `app/research/research_agent_registry.py`
- `app/research/research_agent_message_bus.py`
- `app/research/in_memory_research_agent_message_bus.py`

### Manager and Specialists

- `app/research/research_manager_agent.py`
- `app/research/search_specialist_agent.py`
- `app/research/source_reader_specialist_agent.py`
- `app/research/evidence_analyst_agent.py`
- `app/research/source_critic_agent.py`
- `app/research/citation_verifier_agent.py`
- `app/research/claim_analyst_agent.py`
- `app/research/synthesis_specialist_agent.py`
- `app/research/quality_reviewer_agent.py`

### Workflow

- `app/research/review_revision_loop.py`
- `app/research/multi_agent_research_orchestrator.py`
- `app/research/single_agent_research_execution.py`
- `app/research/research_execution_comparison.py`

---

## 6. 현재 구현 범위

Phase 10에서 완료된 기능은 다음과 같다.

- 역할 기반 Agent Identity
- Capability 기반 작업 권한
- Agent Registry
- Agent Message 계약
- In-Memory Message Bus
- Manager 기반 Specialist 선택
- Search, Read, Evidence, Claim, Synthesis Agent
- Source 및 Citation 검토 Agent
- 독립 Quality Reviewer
- Review–Revision Loop
- Multi-Agent Orchestrator
- Single-Agent 및 Multi-Agent 비교
- 구조화된 Success, Partial 및 Failure 결과
- 결정론적 Unit Test 및 회귀 Test

---

## 7. 현재 한계

### 7.1 실제 병렬 실행 미지원

현재 Orchestrator는 순차적으로 Agent를 실행한다.

실제 동시 실행, Queue Worker 및 Distributed Agent 처리는 이후 Phase에서 구현한다.

### 7.2 In-Memory Infrastructure

Registry, Message Bus 및 실행 이력은 현재 Process Memory에 존재한다.

Process가 종료되면 상태가 유지되지 않는다.

### 7.3 실제 외부 Tool 미연결

각 Specialist는 Executor 계약을 사용하지만 실제 Web Search, Document Reader, LLM Provider와의 연결은 아직 기본 구현 범위에 포함되지 않는다.

### 7.4 Source Critic과 Citation Verifier의 Orchestrator 통합

두 Agent는 독립적으로 구현되어 있지만 현재 기본 Orchestrator Pipeline에는 직접 삽입되지 않았다.

향후 다음과 같은 확장이 가능하다.

```text
Source Reader
    → Source Critic
    → Evidence Analyst
    → Claim Analyst
    → Citation Verifier
    → Synthesis
```

### 7.5 단순 비교 공식

Traceability와 Complexity Score는 현재 Baseline 평가를 위한 단순 결정론적 공식이다.

실제 품질 평가는 Phase 11 Evals에서 Dataset 및 Rubric 기반으로 확장해야 한다.

---

## 8. Phase 10 완료 기준

Phase 10은 다음 조건을 충족할 때 완료된 것으로 본다.

- 모든 Lesson Test 통과
- 전체 Test Suite 통과
- Ruff 전체 검사 통과
- Multi-Agent Orchestrator 성공 및 실패 흐름 검증
- Review–Revision 종료 조건 검증
- Single-Agent와 Multi-Agent 비교 결과 검증
- Phase 10 기술 문서와 Baseline Report 작성
- Git Working Tree Clean 상태 확인

---

## 9. 다음 단계

Phase 11에서는 다음 내용을 구현한다.

# Phase 11 — Evals, Guardrails, and Reliability

주요 작업 후보는 다음과 같다.

- Evaluation Dataset Schema
- Evaluation Case와 Expected Outcome
- Agent Result Scoring
- Citation Correctness Eval
- Evidence Grounding Eval
- Claim Support Eval
- Report Quality Rubric
- Regression Evaluation Runner
- Guardrail Policy
- Input Validation Guardrail
- Output Validation Guardrail
- Tool Permission Guardrail
- Retry Policy
- Timeout Policy
- Failure Recovery
- Reliability Baseline Report
