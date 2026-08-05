# Phase 12 Application Baseline

## 1. Baseline 정보

- Project: AIRA — Agentic Intelligence Research Assistant
- Phase: 12
- Phase Name: Application, Persistence, and Background Jobs
- Baseline Date: 2026-08-05
- Python: 3.12.3
- Test Runner: pytest
- Static Analysis: Ruff
- Persistence Implementation: In-Memory Repository
- Transaction Implementation: Snapshot and Restore
- Background Job Model: Queue, Lease, Retry, Cancellation
- Idempotency Fingerprint: SHA-256

---

## 2. 전체 검증 결과

```text
pytest: 4048 passed
execution time: 15.45s
ruff: All checks passed
```

이 Baseline은 Phase 1부터 Phase 12까지의 전체 회귀 테스트가 통과한
상태를 의미한다.

---

## 3. Phase 12 완료 범위

### 12.1 Application Execution Record Schema

- 공통 실행 레코드

- 실행 상태

- 실패 정보

- Attempt 연결

- 상태 불변조건

- Optimistic Concurrency Version


### 12.2 Execution Repository Interface

- Create

- Get

- Require

- Update

- Query

- Count

- Exists


### 12.3 In-Memory Execution Repository

- Thread-safe 저장

- Case-insensitive ID

- Version Conflict 검사

- Query 및 Pagination


### 12.4 Evaluation Result Repository

- Evaluation 결과 저장

- 상태 및 점수 검색

- Blocking 결과 검색


### 12.5 Guardrail Result Repository

- Guardrail Decision 저장

- Violation 집계

- Request 및 Workspace 검색


### 12.6 Job Schema and Lifecycle

- Background Job Record

- Worker Lease

- Failure

- Cancellation

- Retry Attempt

- Job Transition Policy


### 12.7 Background Job Repository

- Job 생성 및 갱신

- 상태별 검색

- Queue 및 Availability 검색

- Lease 검색

- Version Conflict 처리


### 12.8 Job Queue Service

- Enqueue

- Enqueue Due Jobs

- Acquire

- Start

- Release

- Renew Lease

- Recover Expired Lease


### 12.9 Retry Scheduling Service

- Retry Policy 연결

- Exponential Backoff

- Retry-After 지원

- 새 Attempt 생성

- Duplicate Retry 차단

- Maximum Attempt 중단


### 12.10 Cancellation Persistence

- Cancellation Request 저장

- Acknowledge

- Complete

- Job Cancellation 상태 연결

- 중복 활성 취소 차단


### 12.11 Research Execution Application Service

- Research Request 정규화

- Runner Protocol

- Execution 상태 저장

- 성공 및 실패 이력 저장


### 12.12 Tool Execution Application Service

- Tool Runner Protocol

- Permission Checker Protocol

- Permission, Validation, Tool, Internal 실패 구분


### 12.13 Workflow Execution Application Service

- Workflow Runner Protocol

- Step Result

- Workflow 상태 저장

- Step 및 Artifact 중복 검사


### 12.14 Reliability Query Service

- Execution Metrics

- Evaluation Metrics

- Guardrail Metrics

- Job Metrics

- Request 및 Workspace Filter


### 12.15 Application Transaction Boundary

- Transaction Manager Protocol

- Snapshot

- Commit

- Rollback

- 다중 Repository 원자성

- 중첩 Transaction 차단


### 12.16 Idempotency and Duplicate Prevention

- 논리적 Idempotency Identity

- Payload SHA-256 Fingerprint

- 성공 Result 재사용

- 진행 중 중복 차단

- Payload Conflict 차단

- 실패 요청 재시작


### 12.17 Application Failure Mapping

- 표준 Failure Category

- Stable Error Code

- Public 및 Internal Message 분리

- HTTP Status Hint

- Retryable Flag

- Validation Detail


### 12.18 Phase 12 E2E Application Flow

- Transaction

- Idempotency

- Research Execution

- 성공 결과 재사용

- 실패 상태 저장

- Failure Mapping


### 12.19 Persistence and Job Reliability Tests

- Transaction Rollback

- Snapshot Restore

- Lease Expiration Recovery

- Retry Scheduling

- Due Job Enqueue

- Cancellation Commit 및 Rollback

- Idempotency Result Reuse


### 12.20 Docs and Application Baseline

- Phase 12 기술 문서

- 신뢰성 기준선

- 전체 회귀 검증


---

## 4. Reliability Guarantees

현재 In-Memory Application 구현은 다음을 보장한다.

### 4.1 실행 이력 보존

모든 Research, Tool 및 Workflow 실행은 성공 또는 실패 상태로 저장된다.

### 4.2 Optimistic Concurrency

Repository Update는 예상 Version과 실제 Version이 다르면 거부된다.

### 4.3 Transaction Rollback

Transaction 중 예외가 발생하면 참여한 모든 In-Memory Repository가
Transaction 시작 전 Snapshot으로 복원된다.

### 4.4 Duplicate Prevention

동일한 Workspace, Operation 및 Idempotency Key의 조합은 한 개의
논리적 요청으로 취급된다.

### 4.5 Payload Integrity

동일한 Idempotency Key에 다른 Payload가 사용되면 Conflict로 거부된다.

### 4.6 Result Reuse

성공한 동일 요청은 Runner를 다시 실행하지 않고 저장된 Result를 반환한다.

### 4.7 Worker Crash Recovery

Worker Lease가 만료되면 Job을 다시 Queue 상태로 복구할 수 있다.

### 4.8 Controlled Retry

Retry Policy가 허용한 실패만 새로운 Attempt로 예약된다.

### 4.9 Cancellation Traceability

취소 요청자, 이유, 시각, Worker 확인 및 완료 정보가 별도로 저장된다.

### 4.10 Failure Isolation

공개 Failure Response는 기본적으로 내부 오류 메시지를 노출하지 않는다.

---

## 5. 현재 제한 사항

현재 Baseline에는 다음 제한이 있다.

### 5.1 In-Memory Persistence

프로세스가 종료되면 데이터가 사라진다.

### 5.2 단일 프로세스 Lock

현재 `RLock`은 하나의 Python Process 안에서만 유효하다.

### 5.3 실제 Database Transaction 부재

Snapshot Transaction은 Application 설계 검증용이며,
실제 운영 환경에서는 PostgreSQL Transaction으로 교체해야 한다.

### 5.4 실제 Distributed Queue 부재

현재 Queue는 Repository 상태 기반이다.

운영 환경에서는 PostgreSQL, Redis, RabbitMQ 또는 다른 Queue Backend가
필요하다.

### 5.5 Worker Process 부재

현재 Worker Lease 및 Job Lifecycle은 구현되어 있지만,
지속 실행 Worker Process는 아직 없다.

### 5.6 Dead Letter 처리기 부재

Dead Letter 상태는 존재하지만 별도 운영 처리기는 아직 없다.

### 5.7 자동 Scheduler 부재

Retry 및 Scheduled Job을 주기적으로 Enqueue하는 Scheduler Process는
아직 없다.

### 5.8 외부 API Adapter 부재

FastAPI 또는 다른 HTTP Adapter는 아직 연결되지 않았다.

### 5.9 실제 Tool 및 Provider 장애 테스트 부재

현재 실패 테스트는 결정론적 Fake Runner를 사용한다.

### 5.10 Multi-Process Idempotency 부재

실제 분산 환경에서는 Database Unique Constraint 또는 Redis Atomic
Operation이 필요하다.

---

## 6. 운영 전 필수 후속 작업

운영 배포 전 최소한 다음 작업이 필요하다.

1. PostgreSQL Schema 및 Migration

2. PostgreSQL Repository 구현

3. Database Transaction Manager

4. Durable Job Queue

5. Worker Process

6. Scheduled Job Scanner

7. Retry Worker

8. Dead Letter Handler

9. FastAPI Application Adapter

10. Authentication 및 Authorization 연결

11. Structured Logging

12. OpenTelemetry Trace

13. Metrics Exporter

14. Health Check

15. Graceful Shutdown

16. Integration Test Database

17. Multi-Worker Concurrency Test

18. Load Test

19. Crash Recovery Test

20. Backup 및 Restore 검증


---

## 7. Phase 12 종료 판정

Phase 12는 다음 조건을 충족하였다.

- 계획한 20개 Lesson 완료

- 전체 테스트 통과

- Ruff 정적 검사 통과

- Repository Interface 및 In-Memory 구현 완료

- Background Job Lifecycle 완료

- Queue 및 Lease 복구 완료

- Retry Scheduling 완료

- Cancellation Persistence 완료

- Application Execution Service 완료

- Reliability Query 완료

- Transaction Boundary 완료

- Idempotency 완료

- Failure Mapping 완료

- E2E Application Flow 완료

- Persistence 및 Job Reliability Test 완료

- 기술 문서와 Baseline 작성 완료


따라서 Phase 12의 Application 계층 설계 및 In-Memory Reference
Implementation은 완료된 것으로 판정한다.
