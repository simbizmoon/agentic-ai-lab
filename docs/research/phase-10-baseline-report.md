# Phase 10 Baseline Report

## 1. 개요

이 문서는 AIRA Phase 10 Multi-Agent Research System의 최초 Baseline을 기록한다.

Baseline의 목적은 현재 구현 상태를 고정하고, Phase 11 이후 품질 및 신뢰성 개선 결과를 비교할 기준을 제공하는 것이다.

---

## 2. Baseline 범위

현재 Baseline은 외부 LLM, Search API 또는 Persistent Queue를 사용하지 않는 결정론적 Test 환경을 기준으로 한다.

검증 범위는 다음과 같다.

- Agent Identity와 Role
- Capability 및 위임 권한
- Assignment와 Message
- Registry
- In-Memory Message Bus
- Manager Dispatch
- Specialist Agent 실행
- Structured Result와 Failure
- Review 및 Revision Loop
- Multi-Agent Orchestration
- Single-Agent와 Multi-Agent 비교

---

## 3. Architecture Baseline

### 3.1 Agent 역할

| Agent | 주요 책임 |
|---|---|
| Research Manager | Agent 선택과 Assignment Dispatch |
| Search Specialist | Source Candidate 검색 |
| Source Reader | Source Document 읽기 및 정규화 |
| Evidence Analyst | Evidence 추출 |
| Source Critic | Source 품질 평가 |
| Citation Verifier | Claim–Citation 연결 검증 |
| Claim Analyst | Evidence 기반 Claim 생성 |
| Synthesis Specialist | Research Report 합성 |
| Quality Reviewer | Report 품질 평가 및 승인 판정 |

### 3.2 기본 Workflow

```text
Search
    → Source Reading
    → Evidence Extraction
    → Claim Construction
    → Report Synthesis
    → Quality Review
    → Optional Revision

### 3.3 기본 종료 상태

Multi-Agent Workflow는 다음 상태 중 하나로 종료된다.

- COMPLETED

- SEARCH_FAILED

- SOURCE_READING_FAILED

- EVIDENCE_FAILED

- CLAIM_FAILED

- SYNTHESIS_FAILED

- REVIEW_FAILED

- REPORT_REJECTED

- REVISION_LIMIT_REACHED


---

## 4. Reliability Baseline

### 4.1 Schema Validation

모든 핵심 Artifact는 Pydantic Schema를 사용한다.

검증 항목은 다음과 같다.

- Blank Identifier 차단

- Duplicate Identifier 차단

- Duplicate Instruction 차단

- Duplicate Capability 차단

- Role과 Capability 불일치 차단

- Assignment와 Agent 불일치 차단

- Invalid State Transition 차단

- Output과 Failure 상태 불일치 차단

- Review Decision과 Revision Request 불일치 차단


### 4.2 Deterministic Dependency Injection

다음 Dependency를 Test에서 주입할 수 있다.

- Clock

- Assignment ID Factory

- Message ID Factory

- Delivery ID Factory

- Result ID Factory

- Output Reference ID Factory

- Executor

- Review Decision Sequence


### 4.3 Structured Failure

Agent 실행 오류는 가능한 경우 Exception으로 Workflow를 종료하지 않고 `ResearchAgentTaskResult`의 Failure로 변환한다.

Failure에는 다음 정보가 포함된다.

- Category

- Code

- Message

- Retryable

- Retry Reason

- Failed Stage

- Details


### 4.4 Partial Result

다음 Agent는 일부 입력만 성공한 경우 `PARTIAL` 결과를 지원한다.

- Source Reader

- Evidence Analyst

- Source Critic

- Citation Verifier

- Claim Analyst

- Synthesis Specialist


---

## 5. Review–Revision Baseline

Quality Reviewer는 다음 판정을 반환한다.

|Decision|의미|
|---|---|
|APPROVED|Report 승인|
|REVISION_REQUIRED|필수 수정 요청 존재|
|REJECTED|Report 사용 불가|

Review–Revision Loop는 다음을 보장한다.

- 모든 Round 보존

- 이전 Report Reference 보존

- Quality Review Reference 보존

- Parent Assignment 연결

- 수정 지시 중복 방지

- 최대 수정 횟수 준수

- Synthesis Failure 종료

- Review Failure 종료


---

## 6. Single-Agent vs Multi-Agent Baseline

### 6.1 비교 관점

두 Architecture는 다음 항목으로 비교한다.

- 완료 여부

- 최종 Output 존재 여부

- 실행 단계 수

- 참여 Agent 수

- Tool Call 수

- Token 수

- Source 수

- Evidence 수

- Claim 수

- Revision Round 수

- Traceability

- Complexity


### 6.2 Traceability Score

현재 Baseline Formula는 다음 네 조건에 각각 0.25점을 부여한다.

- 최종 Output 존재

- Source 존재

- Evidence 존재

- Claim 존재


```text
Traceability Score Range: 0.00–1.00
```

이 공식은 실제 품질 평가 공식이 아니라 Phase 11 평가 체계를 만들기 전의 Baseline이다.

### 6.3 Complexity Score

현재 Baseline Formula:

```text
raw complexity =
    execution step count
    + participating agent count
    + revision round count

complexity score =
    min(raw complexity / 12, 1.0)
```

### 6.4 Architecture Preference

현재 비교기는 다음 중 하나를 반환한다.

- SINGLE_AGENT

- MULTI_AGENT

- CONTEXT_DEPENDENT


현재 Rule은 다음 관점을 반영한다.

- 한 Architecture만 성공하면 성공한 Architecture를 선호한다.

- Multi-Agent의 Traceability 개선이 충분하면 높은 복잡성을 감수할 수 있다.

- Traceability가 동일하고 Single-Agent가 더 저렴하면 Single-Agent를 선호한다.

- 그 외에는 Context Dependent로 판정한다.


---

## 7. Test Baseline 기록 방법

다음 명령으로 현재 Test 수를 기록한다.

```bash
python -m pytest -q
```

현재 실행 환경에서 출력된 최종 Test 수를 아래에 기록한다.

```text
Total Tests:
Passed:
Failed:
Skipped:
Duration:
```

Ruff 결과도 기록한다.

```bash
ruff check .
```

```text
Ruff Result:
```

---

## 8. Git Baseline 기록 방법

다음 명령을 실행한다.

```bash
git log -1 --oneline --decorate
git status -sb
```

아래에 결과를 기록한다.

```text
Baseline Commit:
Branch Status:
```

---

## 9. Known Limitations

현재 Baseline에는 다음 한계가 있다.

- 실제 LLM 기반 Agent 실행 미포함

- 실제 Web Search Provider 미포함

- 실제 Document Download 및 Parsing 미포함

- Persistent Database 미포함

- Persistent Message Queue 미포함

- Parallel Agent Execution 미포함

- Distributed Worker 미포함

- Timeout 및 Circuit Breaker 미포함

- Dataset 기반 정량 Eval 미포함

- Human Evaluation 미포함

- Source Critic과 Citation Verifier의 기본 Orchestrator 통합 미완료


---

## 10. Phase 11 비교 기준

Phase 11 완료 후 다음 항목을 이 Baseline과 비교한다.

- Evaluation Case 수

- Evaluation Pass Rate

- Citation Correctness

- Evidence Grounding

- Claim Support Rate

- Report Quality Score

- Guardrail Violation Detection

- False Positive Rate

- Retry Success Rate

- Failure Recovery Rate

- Regression Detection Rate

- Average Tool Calls

- Average Token Usage

- Average Revision Rounds

- End-to-End Success Rate


---

## 11. Baseline 결론

Phase 10은 역할 기반 Multi-Agent Research Architecture의 구조적 기반을 완성하였다.

현재 시스템은 외부 Tool 없이도 Agent 계약, 작업 위임, 단계별 실행, Failure 처리, 독립 검토, 수정 반복 및 Architecture 비교를 검증할 수 있다.

다음 Phase에서는 이 구조 위에 Eval Dataset, Quality Rubric, Guardrail 및 Reliability Policy를 추가하여 실제 Agent 결과의 품질을 측정하고 회귀를 방지한다.
