# Phase 12 — Application, Persistence, and Background Jobs

## 1. 목적

Phase 12의 목적은 Phase 11까지 구현한 Agent, Workflow, Evaluation,
Guardrail, Retry 및 Reliability 기능을 실제 Application 계층에서
안전하게 실행하고 추적할 수 있도록 만드는 것이다.

Phase 12에서는 다음 기능을 구현하였다.

- 실행 이력의 영속화
- Evaluation 결과 영속화
- Guardrail 결과 영속화
- Background Job 생명주기 관리
- Job Queue 및 Worker Lease
- Retry Scheduling
- Cancellation Persistence
- Research, Tool, Workflow Application Service
- Reliability Query
- Transaction Boundary
- Idempotency 및 중복 방지
- Application Failure Mapping
- End-to-End Application Flow
- Persistence 및 Job Reliability 검증

---

## 2. 전체 구조

```text
Application Request
        |
        v
Idempotency Service
        |
        v
Transaction Boundary
        |
        +-----------------------------+
        |                             |
        v                             v
Execution Application Service    Background Job Service
        |                             |
        v                             v
Execution Repository             Job Repository
        |
        +-----------------------------+
        |
        v
Evaluation / Guardrail Repository
        |
        v
Reliability Query Service

Application 계층은 구체적인 데이터베이스, Agent 구현 또는 Tool 구현에
직접 의존하지 않는다.

각 기능은 Protocol 또는 Abstract Repository Interface를 통해 연결된다.

---

## 3. Application Execution Record

`ApplicationExecutionRecord`는 다음 실행을 공통 형식으로 추적한다.

- Agent 실행

- Tool 실행

- Workflow 실행

- Assignment 실행

- Evaluation 실행

- Guardrail 실행


주요 필드는 다음과 같다.

- `execution_id`

- `root_execution_id`

- `parent_execution_id`

- `previous_attempt_execution_id`

- `request_id`

- `workspace_id`

- `subject_type`

- `subject_id`

- `status`

- `attempt_number`

- `maximum_attempts`

- `created_at`

- `started_at`

- `finished_at`

- `failure`

- `record_version`


실행 상태는 Transition Policy를 통해서만 변경된다.

```text
PENDING
  -> QUEUED
  -> RUNNING
  -> SUCCEEDED
  -> FAILED
  -> CANCELLATION_REQUESTED
  -> CANCELLED
  -> TIMED_OUT
```

`record_version`은 Optimistic Concurrency Control에 사용된다.

---

## 4. Repository 계층

Phase 12에서는 다음 Repository Interface와 In-Memory 구현을 추가하였다.

- Application Execution Repository

- Application Evaluation Repository

- Application Guardrail Repository

- Application Job Repository

- Application Cancellation Repository

- Application Idempotency Repository


Repository의 주요 책임은 다음과 같다.

- 생성

- 단건 조회

- 조건 검색

- 상태 갱신

- Optimistic Concurrency 검사

- 중복 ID 방지

- 논리적 고유 키 방지

- Snapshot 및 Restore


In-Memory Repository는 테스트와 Application 설계 검증을 위한 구현이다.

향후 PostgreSQL Repository를 추가하더라도 Application Service의
인터페이스는 변경하지 않는다.

---

## 5. Background Job

`ApplicationJobRecord`는 Background Job의 전체 생명주기를 나타낸다.

주요 상태는 다음과 같다.

```text
PENDING
SCHEDULED
QUEUED
LEASED
RUNNING
SUCCEEDED
FAILED
RETRY_SCHEDULED
CANCELLATION_REQUESTED
CANCELLED
DEAD_LETTERED
```

Job은 다음 정보를 포함한다.

- Job ID

- Root Job ID

- Previous Attempt Job ID

- Request 및 Workspace ID

- Job Type

- Queue Name

- Priority

- Payload

- Attempt Number

- Maximum Attempts

- Available Time

- Worker Lease

- Failure 정보

- Cancellation 정보

- Record Version


---

## 6. Job Queue와 Worker Lease

`ApplicationJobQueueService`는 다음 작업을 담당한다.

- Job Enqueue

- 실행 가능한 Job 일괄 Enqueue

- Worker의 Job Acquire

- Lease 생성

- Job Start

- Lease Renew

- Lease Release

- 만료 Lease 복구


Worker가 Job을 Acquire하면 Job 상태는 `LEASED`가 된다.

Lease에는 다음 정보가 저장된다.

- Lease ID

- Worker ID

- Acquired Time

- Expiration Time


Worker가 비정상 종료되거나 Lease 갱신에 실패하면
`recover_expired_leases()`가 Job을 다시 `QUEUED` 상태로 복구한다.

이 구조는 Worker Crash로 인한 Job 영구 손실을 방지한다.

---

## 7. Retry Scheduling

`ApplicationRetrySchedulingService`는 Phase 11의 Retry Policy와
Background Job을 연결한다.

Retry 흐름은 다음과 같다.

```text
FAILED Job
    |
    v
RetryFailureContext
    |
    v
RetryPolicyEvaluator
    |
    +-- STOP
    |
    +-- RETRY
          |
          v
New Attempt Job
```

새 Retry Job은 다음 규칙을 따른다.

- 새로운 `job_id`

- 동일한 `root_job_id`

- 이전 Job을 `previous_attempt_job_id`로 참조

- `attempt_number + 1`

- Policy가 계산한 Delay만큼 `available_at` 설정

- Delay가 0이면 `PENDING`

- Delay가 있으면 `SCHEDULED`


동일한 실패 Job에 대한 중복 Retry Scheduling은 차단된다.

---

## 8. Cancellation Persistence

취소 요청은 Job 상태와 별도의
`ApplicationJobCancellationRequestRecord`로 저장된다.

취소 요청에는 다음 정보가 포함된다.

- Cancellation Request ID

- Job ID

- Request 및 Workspace ID

- Requested By

- Reason

- Force 여부

- Requested Time

- Acknowledged Time 및 Worker

- Completed Time 및 Worker

- Record Version


취소 상태는 다음과 같다.

```text
REQUESTED
ACKNOWLEDGED
COMPLETED
```

취소 요청 시 Job은 `CANCELLATION_REQUESTED`로 변경된다.

실제 취소가 완료되면 Job은 `CANCELLED`로 변경된다.

Transaction Boundary와 함께 사용하면 취소 요청 레코드와 Job 상태를
원자적으로 저장할 수 있다.

---

## 9. Research Execution Application Service

`ApplicationResearchExecutionService`는 Research Runner를 실행하고
그 생명주기를 Execution Repository에 기록한다.

```text
Request
  -> PENDING
  -> RUNNING
  -> Runner Execute
  -> SUCCEEDED 또는 FAILED
```

Application Service는 구체적인 Research Agent를 직접 알지 않는다.

다음 Protocol만 의존한다.

```python
class ResearchExecutionRunner(Protocol):
    def execute(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ApplicationResearchExecutionOutput:
        ...
```

실패가 발생해도 FAILED Execution Record가 Repository에 남는다.

---

## 10. Tool Execution Application Service

`ApplicationToolExecutionService`는 Tool 실행 전에 권한을 검사한다.

```text
Tool Request
   |
   v
Permission Checker
   |
   +-- Denied -> FAILED
   |
   +-- Allowed
          |
          v
       Tool Runner
```

Tool 오류는 다음 범주로 구분된다.

- Permission

- Validation

- Tool

- Internal


Tool Runner와 Permission Checker는 Protocol로 주입된다.

---

## 11. Workflow Execution Application Service

`ApplicationWorkflowExecutionService`는 Workflow Runner를 실행하고
전체 Workflow 실행 상태를 저장한다.

Workflow Output에는 단계별 결과가 포함된다.

- Step ID

- Step Type

- Status

- Summary

- Child Execution ID

- Output

- Error 정보


성공한 Workflow Output에는 실패 Step이 포함될 수 없다.

Step ID와 Artifact ID는 중복될 수 없다.

---

## 12. Reliability Query Service

`ApplicationReliabilityQueryService`는 다음 Repository를 읽어
통합 Reliability Snapshot을 생성한다.

- Execution Repository

- Evaluation Repository

- Guardrail Repository

- Job Repository


주요 지표는 다음과 같다.

### Execution

- Total

- Success Rate

- Failure Rate

- Cancellation Rate

- Timeout Rate

- Retry Rate


### Evaluation

- Pass Rate

- Error Rate

- Blocking Rate

- Average Score


### Guardrail

- Allow Rate

- Warning Rate

- Blocking Rate

- Violation Count


### Job

- Completion Rate

- Success Rate

- Failure Rate

- Dead Letter Rate

- Retry Rate


분모가 0인 경우 비율은 `0.0`으로 반환한다.

---

## 13. Transaction Boundary

`ApplicationTransactionManager`는 여러 Repository 변경을 하나의
논리적 Transaction으로 묶는다.

In-Memory 구현은 다음 방식으로 동작한다.

1. 모든 Resource의 Snapshot 생성

2. Application 작업 실행

3. 정상 종료 시 변경 유지

4. 예외 발생 시 모든 Resource를 역순으로 Restore


```text
BEGIN
  -> Snapshot
  -> Repository A 변경
  -> Repository B 변경
  -> 오류 발생
  -> Repository B Restore
  -> Repository A Restore
ROLLBACK
```

현재 구현은 중첩 Transaction을 허용하지 않는다.

향후 PostgreSQL 구현에서는 동일한 Interface를 실제 DB Transaction으로
교체할 수 있다.

---

## 14. Idempotency와 중복 방지

Idempotency의 논리적 고유 키는 다음 조합이다.

```text
workspace_id
+ operation
+ idempotency_key
```

Payload는 안정적인 JSON 직렬화 후 SHA-256 Fingerprint로 비교한다.

처리 규칙은 다음과 같다.

### 최초 요청

- `IN_PROGRESS` Record 생성

- 실제 작업 실행


### 동일한 성공 요청

- 기존 Result 반환

- 실제 작업을 다시 실행하지 않음


### 동일 키, 다른 Payload

- Conflict 오류


### 기존 요청 진행 중

- In Progress 오류


### 실패한 요청

- 정책에 따라 재시작 가능

- 동일 Record의 Version 증가


---

## 15. Application Failure Mapping

Application Failure Mapper는 내부 예외를 표준 실패 모델로 변환한다.

표준 실패 정보는 다음과 같다.

- Category

- Stable Error Code

- Public Message

- Retryable

- HTTP Status Hint

- Validation Details

- Internal Message

- Exception Type

- Execution ID

- Metadata


주요 Mapping은 다음과 같다.

|오류|상태 코드|Retry|
|---|--:|--:|
|Validation|422|No|
|Not Found|404|No|
|Permission|403|No|
|Application Conflict|409|No|
|Version Conflict|409|Yes|
|Operation In Progress|409|Yes|
|Timeout|504|Yes|
|Execution Failure|500|정책에 따름|
|Unknown Internal Error|500|No|

공개 응답에는 내부 메시지를 기본적으로 포함하지 않는다.

---

## 16. Phase 12 End-to-End Flow

Phase 12 E2E Flow는 다음 기능을 하나의 흐름으로 연결한다.

```text
ApplicationResearchFlowRequest
        |
        v
Transaction
        |
        v
Idempotency Begin
        |
        +-- Reused Result
        |
        +-- Execute
              |
              v
Research Execution Service
              |
              +-- Success
              |     |
              |     v
              |  Idempotency Succeed
              |
              +-- Failure
                    |
                    v
                 Idempotency Fail
```

Research 실행 실패는 Transaction 전체를 Rollback하지 않는다.

FAILED Execution과 FAILED Idempotency Record를 저장한 후
Application Error를 호출자에게 다시 전달한다.

반면 Application 상태 저장 자체가 실패하면 Transaction Rollback을 통해
모든 Repository 상태를 이전 상태로 복원할 수 있다.

---

## 17. 주요 설계 결정

### 17.1 Application과 Infrastructure 분리

Application Service는 데이터베이스나 외부 Provider 구현에 직접
의존하지 않는다.

### 17.2 상태 변경 기록

모든 중요한 실행과 Job 상태는 Repository Record로 보존한다.

### 17.3 Optimistic Concurrency

`record_version`으로 오래된 갱신을 차단한다.

### 17.4 At-Least-Once 실행 대비

Background Job은 중복 실행 가능성을 전제로 설계하며,
Idempotency가 부작용의 중복을 방지한다.

### 17.5 Lease 기반 Worker 복구

Worker 소유권은 영구 Lock이 아닌 만료 가능한 Lease로 표현한다.

### 17.6 실패 이력 보존

실패는 단순 예외가 아니라 Repository에 저장되는 실행 결과이다.

### 17.7 Transport Neutral Failure

Application Failure는 FastAPI, CLI, Worker 등 특정 Transport에
종속되지 않는다.

---

## 18. 향후 확장

Phase 12 이후에는 다음 구현을 추가할 수 있다.

- PostgreSQL Repository

- 실제 DB Transaction Manager

- Redis 또는 Database Job Queue

- Worker Process

- Dead Letter Queue 처리기

- Retry Scheduler

- FastAPI Adapter

- REST API

- Webhook 및 Event Publisher

- OpenTelemetry Trace 연결

- Execution 및 Job Dashboard

- Long-running Research Worker
