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
