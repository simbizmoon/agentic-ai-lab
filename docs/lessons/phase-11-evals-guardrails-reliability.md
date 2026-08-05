# Phase 11 — Evals, Guardrails, and Reliability

## 1. 문서 목적

이 문서는 AIRA(Agentic Intelligence Research Assistant)의 Phase 11에서 구현한 평가, Guardrail, Retry, Timeout, Recovery 및 Reliability 구성요소의 구조와 책임을 정리한다.

Phase 11의 목적은 단순히 Agent가 실행되는 시스템을 만드는 것이 아니라 다음 조건을 만족하는 신뢰 가능한 Agent 시스템을 만드는 것이다.

- 실행 결과의 품질을 반복적으로 평가할 수 있다.
- 허용되지 않은 입력, 출력 및 Tool 사용을 실행 전에 차단할 수 있다.
- 일시적 실패와 영구적 실패를 구분할 수 있다.
- Timeout과 취소 요청을 일관되게 처리할 수 있다.
- 재시도 소진 후 안전한 Fallback을 선택할 수 있다.
- 실행 결과를 신뢰성 지표로 집계할 수 있다.
- 향후 변경이 품질을 저하했는지 회귀 평가할 수 있다.

---

## 2. Phase 11 구현 범위

Phase 11은 다음 Lesson으로 구성된다.

| Lesson | 주제 |
|---|---|
| 11.1 | Evaluation Dataset Schema |
| 11.2 | Evaluation Case and Expected Outcome |
| 11.3 | Evaluation Result Schema |
| 11.4 | Deterministic Evaluation Runner |
| 11.5 | Citation Correctness Eval |
| 11.6 | Evidence Grounding Eval |
| 11.7 | Claim Support Eval |
| 11.8 | Report Quality Rubric |
| 11.9 | Multi-Agent Workflow Eval |
| 11.10 | Regression Evaluation Runner |
| 11.11 | Guardrail Policy Schema |
| 11.12 | Input Guardrails |
| 11.13 | Output Guardrails |
| 11.14 | Tool Permission Guardrails |
| 11.15 | Retry and Backoff Policy |
| 11.16 | Timeout and Cancellation |
| 11.17 | Failure Recovery and Fallback |
| 11.18 | Reliability Metrics |
| 11.19 | Phase 11 E2E Evaluation |
| 11.20 | Documentation and Reliability Baseline |

---

## 3. Evaluation Architecture

Phase 11의 평가 구조는 다음과 같다.

```text
Evaluation Dataset
        ↓
Evaluation Case Definition
        ↓
Expected Outcome
        ↓
Execution Snapshot
        ↓
Deterministic Evaluators
        ├── Citation Correctness
        ├── Evidence Grounding
        ├── Claim Support
        ├── Report Quality
        └── Multi-Agent Workflow
        ↓
Evaluation Case Result
        ↓
Regression Comparison
```

### 3.1 Evaluation Dataset

Evaluation Dataset은 반복 평가에 사용하는 Case 집합이다.

각 Case는 다음 정보를 포함한다.

- Case ID

- 입력 데이터

- 난이도

- 기대 결과

- 평가 Dimension

- 필수 위반 조건

- 최소 점수 기준


Dataset과 Case는 실행 코드와 분리되어야 한다. 동일한 Dataset을 여러 모델, Prompt, Tool 구성 및 Workflow 버전에 반복 적용할 수 있어야 한다.

### 3.2 Deterministic Evaluation Runner

Deterministic Evaluation Runner는 실행 Snapshot과 Expected Outcome을 비교한다.

평가 결과는 다음을 포함한다.

- 전체 상태

- 전체 점수

- Dimension별 점수

- Blocking Violation

- 실행 Metrics

- 오류 정보

- 평가 요약


평가 로직은 가능한 범위에서 결정론적으로 구현한다. 해석이 필요한 평가만 향후 LLM Evaluator로 확장한다.

### 3.3 Specialized Evaluators

#### Citation Correctness Evaluator

다음을 검사한다.

- Citation Reference 존재 여부

- Citation 대상의 실제 Source 존재 여부

- 허용된 Source 범위

- 중복 Citation

- Citation 형식과 구조


#### Evidence Grounding Evaluator

다음을 검사한다.

- Report 또는 Claim이 Evidence를 참조하는지

- 참조 Evidence가 실제로 존재하는지

- 필수 Evidence가 사용되었는지

- 근거 없는 결론이 포함되었는지


#### Claim Support Evaluator

다음을 검사한다.

- Claim과 Supporting Evidence 연결

- 요구되는 최소 Evidence 수

- Claim Support 상태

- Unsupported Claim

- Evidence Reference 중복


#### Report Quality Rubric

다음을 평가한다.

- 구조적 완전성

- 명확성

- 논리적 일관성

- 근거 활용

- Citation 품질

- 결론의 적절성


#### Multi-Agent Workflow Evaluator

다음을 검사한다.

- Specialist Stage 순서

- Assignment Parent Link

- Review Round 순서

- Review Assignment 연결

- Review-Reviser Loop 종료 상태

- Workflow 최종 상태


---

## 4. Regression Evaluation

Regression Evaluation Runner는 Baseline Result와 Current Result를 비교한다.

```text
Baseline Result
        +
Current Result
        ↓
Regression Evaluation
```

검사 항목은 다음과 같다.

- PASSED에서 FAILED로 상태 전환

- Overall Score 하락

- Dimension Score 하락

- 새로운 Blocking Violation

- 기존 Blocking Violation 해결

- Token 사용량 증가

- Tool Call 수 증가


품질 Regression과 비용 증가는 구분한다.

다음 변화는 품질 Regression으로 취급한다.

- PASSED → FAILED

- 허용 범위를 초과한 Overall Score 하락

- 허용 범위를 초과한 Dimension Score 하락

- 새로운 Blocking Violation


Token 및 Tool Call 증가는 기본적으로 경고 정보로 기록하며 자동 품질 실패로 처리하지 않는다.

---

## 5. Guardrail Architecture

Guardrail 구조는 다음과 같다.

```text
Guardrail Policy
        ↓
Guardrail Evaluator
        ↓
Guardrail Violation
        ↓
Guardrail Evaluation Result
        ├── ALLOWED
        ├── WARNED
        └── BLOCKED
```

### 5.1 Guardrail Policy

Guardrail Policy는 다음 속성을 가진다.

- Scope

- Target

- Severity

- Action

- Blocking 여부

- Retry 가능 여부

- Priority

- Remediation

- Rule

- Condition


지원 Scope는 다음과 같다.

- INPUT

- OUTPUT

- TOOL

- ASSIGNMENT

- AGENT

- WORKFLOW

- EVALUATION


지원 Action은 다음과 같다.

- ALLOW

- LOG

- WARN

- BLOCK

- REQUEST_REVISION

- RETRY

- CANCEL

- QUARANTINE


### 5.2 Schema Validation과 Guardrail Validation

Schema Validation과 Guardrail Validation은 서로 다른 책임을 가진다.

```text
Schema Validation
    └── 객체 자체가 가질 수 없는 상태 차단

Guardrail Validation
    └── 실행 Context와 정책에 따라 허용 여부 결정
```

예를 들어 다음 조건은 Schema에서 차단한다.

- Assignment Assignee Role과 Required Role 불일치

- 성공 Result의 Output 누락

- Result Agent와 Assignment Assignee 불일치

- 복수 Primary Output

- 중복 Output Reference

- 실패 Result에 Output 포함


Guardrail은 정상적인 Schema 객체를 대상으로 다음을 검사한다.

- 현재 Request 및 Workspace와 일치하는가

- 실행에 필요한 Input Reference가 존재하는가

- Output Type이 Assignment 계약과 일치하는가

- Tool 사용 권한이 있는가

- 호출 제한과 위험 정책을 만족하는가


---

## 6. Input Guardrails

Input Guardrail은 Agent 실행 전에 Assignment를 검사한다.

검사 항목은 다음과 같다.

- Assignment Assignee와 Capability Profile 일치

- Required Role 일치

- Required Capability 보유

- 실행 가능한 Assignment Status

- 필수 Input 존재

- Input Reference 가용성

- Request ID 일치

- Workspace ID 일치


Input Guardrail이 `BLOCKED`를 반환하면 Agent Executor를 호출해서는 안 된다.

---

## 7. Output Guardrails

Output Guardrail은 Agent Result를 다음 단계로 전달하기 전에 검사한다.

검사 항목은 다음과 같다.

- 예상 Assignment 일치

- Result Agent 일치

- Request Context 일치

- Workspace Context 일치

- Primary Output 존재

- Expected Output Type 일치

- Output Reference 정합성


Result Schema가 원천적으로 차단하는 조건을 Output Guardrail에서 중복 테스트하지 않는다. 다만 외부 직렬화, 저장 데이터 복구 또는 향후 Schema 변경에 대비한 방어 검사는 코드에 유지할 수 있다.

---

## 8. Tool Permission Guardrails

Tool Permission Guardrail은 Tool 실행 전에 다음을 검사한다.

- Tool Allowlist

- 허용 Operation

- Read-only 또는 Read-write Access

- 외부 Network 사용 권한

- Sensitive Operation 승인

- Agent Role

- 최대 호출 횟수

- Request Context

- Workspace Context

- Risk Level


기본 정책은 `default_deny=True`이다.

Allowlist에 명시되지 않은 Tool은 원칙적으로 차단한다.

High 또는 Critical Risk Tool 호출이 허용되는 경우에도 Warning을 생성할 수 있다.

---

## 9. Retry and Backoff

Retry Policy는 일시적 실패만 재시도하도록 설계한다.

기본적으로 재시도 가능한 Failure Category는 다음과 같다.

- TIMEOUT

- RATE_LIMIT

- NETWORK

- TOOL_TEMPORARY

- SERVICE_UNAVAILABLE


기본적으로 재시도하지 않는 Failure Category는 다음과 같다.

- VALIDATION

- PERMISSION

- POLICY

- AUTHENTICATION

- NOT_FOUND

- CANCELLED


Backoff Strategy는 다음을 지원한다.

- FIXED

- LINEAR

- EXPONENTIAL


지수 Backoff 계산식은 다음과 같다.

```text
delay = base_delay × multiplier^(attempt_number - 1)
```

최종 Delay는 Maximum Delay로 제한한다.

Retry-After가 제공되고 정책에서 이를 존중하도록 설정한 경우 Retry-After를 우선 적용한다.

Jitter Strategy는 다음을 지원한다.

- NONE

- FULL

- EQUAL


테스트 재현성을 위해 Random Fraction Factory를 주입한다.

---

## 10. Timeout and Cancellation

Execution Control Evaluator는 다음 순서로 실행 상태를 판단한다.

1. Terminal 상태 여부

2. Cancellation Request

3. Absolute Deadline

4. Hard Timeout

5. Soft Timeout

6. 정상 계속 실행


지원 Decision은 다음과 같다.

- CONTINUE

- WARN

- REQUEST_CANCELLATION

- FORCE_CANCEL

- TIMEOUT

- TERMINAL


Soft Timeout은 경고를 생성하지만 실행을 계속할 수 있다.

Hard Timeout과 Deadline 초과는 실행 중단을 요구한다.

Graceful Cancellation은 Grace Period 동안 정상 종료 기회를 제공한다. Grace Period가 지나면 Force Cancellation으로 전환한다.

모든 `datetime`은 timezone-aware여야 한다.

---

## 11. Failure Recovery and Fallback

Retry가 소진된 후 Failure Recovery Evaluator를 실행한다.

지원 전략은 다음과 같다.

1. ALTERNATE_TOOL

2. ALTERNATE_AGENT

3. CACHED_RESULT

4. PARTIAL_RESULT

5. MANUAL_REVIEW

6. ABORT


Recovery Strategy는 Priority 순서로 평가한다.

### Alternate Tool

현재 실패한 Tool과 동일한 Tool은 Fallback 대상으로 선택하지 않는다.

### Alternate Agent

현재 Agent와 동일한 Agent는 Fallback 대상으로 선택하지 않는다.

### Cached Result

Cache Age가 정책의 Maximum Cache Age 이하여야 한다.

### Partial Result

Partial Output Quality Score가 최소 품질 기준 이상이어야 한다.

### Manual Review

자동 복구가 불가능할 때 사람이 검토할 수 있도록 Workflow를 중단한다.

### Abort

더 이상 안전한 복구 전략이 없을 때 명시적으로 실행을 종료한다.

---

## 12. Reliability Metrics

Reliability Metrics Calculator는 구조화된 Execution Record를 집계한다.

계산 지표는 다음과 같다.

- Total Executions

- Successful Executions

- Failed Executions

- Cancelled Executions

- Timed-out Executions

- Success Rate

- Failure Rate

- Cancellation Rate

- Timeout Rate

- Retried Executions

- Retry Success Rate

- Recovery Attempts

- Recovery Success Rate

- Manual Review Recovery Count

- Guardrail Evaluations

- Guardrail Block Rate

- Mean Duration

- P50 Duration

- P95 Duration

- Maximum Duration

- Failure Category Distribution


분모가 0인 비율은 `0.0`으로 처리한다.

Percentile은 결정론적 nearest-rank 방식으로 계산한다.

---

## 13. Phase 11 E2E Scenario

Phase 11 E2E 테스트는 다음 흐름을 검증한다.

```text
Valid Assignment
    ↓
Input Guardrail ALLOWED
    ↓
Unknown Tool BLOCKED
    ↓
Allowed Tool ALLOWED
    ↓
First Timeout
    ↓
Retry Allowed
    ↓
Second Timeout
    ↓
Maximum Attempts Reached
    ↓
Alternate Tool Recovery
    ↓
Fallback Execution Succeeded
    ↓
Reliability Metrics Calculated
```

이 테스트는 각 단위 구성요소가 개별적으로 통과하는 것뿐 아니라 서로 연결되었을 때도 계약이 유지되는지 검증한다.

---

## 14. 운영 적용 원칙

Phase 12 이후 실제 Application과 연결할 때 다음 원칙을 지킨다.

1. 모든 Agent 실행 전에 Input Guardrail을 호출한다.

2. 모든 Tool 실행 전에 Tool Permission Guardrail을 호출한다.

3. 모든 Agent 결과 전달 전에 Output Guardrail을 호출한다.

4. 일시적 실패에만 Retry Policy를 적용한다.

5. 실행 중에는 Timeout과 Cancellation 상태를 반복 확인한다.

6. Retry 소진 후에만 Failure Recovery를 적용한다.

7. 모든 실행 결과를 Reliability Execution Record로 저장한다.

8. 배포 전 Baseline과 Current Evaluation Result를 비교한다.

9. Blocking Regression이 있으면 배포를 중단한다.

10. 정책 변경은 Version을 증가시키고 테스트를 추가한다.


---

## 15. Phase 11 완료 기준

Phase 11은 다음 조건을 만족할 때 완료된 것으로 본다.

- Evaluation Dataset과 Case Schema가 존재한다.

- Deterministic Evaluation Runner가 동작한다.

- Citation, Evidence, Claim, Report 및 Workflow Evaluator가 존재한다.

- Regression Evaluation이 가능하다.

- Input, Output 및 Tool Guardrail이 존재한다.

- Retry와 Backoff 정책이 존재한다.

- Timeout과 Cancellation 제어가 존재한다.

- Failure Recovery와 Fallback 정책이 존재한다.

- Reliability Metrics를 계산할 수 있다.

- Phase 11 E2E 테스트가 통과한다.

- 전체 Pytest와 Ruff 검사가 통과한다.


---

## 16. 다음 단계

Phase 12에서는 Phase 11의 정책과 Evaluator를 실제 Application Runtime에 통합한다.

주요 과제는 다음과 같다.

- Application Service Layer

- Persistent Storage

- Execution Repository

- Evaluation Result Repository

- Background Job

- Retry Scheduling

- Cancellation Persistence

- Reliability Dashboard Data

- API Endpoints

- Application E2E Flow
