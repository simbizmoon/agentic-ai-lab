# Phase 8 — Planning Agent

## 1. 목적

Phase 8의 목적은 AIRA가 사용자 요청을 구조화된 Plan으로 변환하고, Plan을 실행·평가하며, 실패 시 제한된 범위에서 자동 재계획할 수 있는 Planning Agent 기반을 구축하는 것이다.

또한 전체 실행 과정을 Trace로 기록하고, 운영 환경에서 조회·보관·정리·보고·Alert·Notification할 수 있는 기반을 제공한다.

## 2. 핵심 실행 흐름

```text
PlanningAgentRequest
        ↓
PlanningService
        ↓
Structured Plan
        ↓
Plan Validation
        ↓
Plan Lifecycle
        ↓
Plan Scheduler
        ↓
Plan Runner
        ↓
Step / Tool Execution
        ↓
Plan Evaluation
        ├─ Goal Achieved
        ├─ Human Review
        ├─ Failed
        └─ Replan Required
                ↓
        Bounded Replanning Loop
```

## 3. Planning 기능

Phase 8에서 구현된 Planning 기능은 다음과 같다.

* 구조화된 Plan Schema
* 결정론적 Plan 검증
* Plan Factory
* Plan Lifecycle Service
* Plan Scheduler
* Tool Contract
* Tool Registry
* Plan Step Executor
* Plan Execution Service
* 반복 Plan Runner
* Plan Evaluator
* Replan Context
* 안전한 Planner Prompt Composer
* Structured Planner Output 검증
* OpenAI Responses Structured Output Client
* Planning Service
* Planning Agent Pipeline
* 제한된 자동 Replanning Loop

## 4. 자동 재계획

Planning Agent는 실행 결과에 따라 다음 결정을 내린다.

* 목표 달성
* 재계획 필요
* 사람의 검토 필요
* 실행 실패
* 실행 취소

재계획이 필요한 경우에는 이전 Plan의 실행 결과와 평가 결과를 바탕으로 새로운 Plan을 생성한다.

자동 재계획은 무한 반복되지 않으며, 요청에 설정된 최대 재계획 횟수 안에서만 수행된다.

```text
Initial Plan
    ↓
Execution Failure
    ↓
Evaluation
    ↓
Replan Required
    ↓
Replan Context
    ↓
Replacement Plan
    ↓
Execution
```

## 5. Trace 기능

Planning Agent의 실행 중 다음 주요 Event가 기록된다.

```text
AGENT_STARTED
PLANNING_STARTED
PLANNING_COMPLETED
PLANNING_FAILED
PLAN_STARTED
PLAN_COMPLETED
PLAN_FAILED
PLAN_CANCELLED
PLAN_BLOCKED
STEP_STARTED
STEP_COMPLETED
STEP_FAILED
STEP_SKIPPED
TOOL_STARTED
TOOL_COMPLETED
TOOL_FAILED
EVALUATION_COMPLETED
REPLANNING_STARTED
REPLANNING_COMPLETED
REPLANNING_FAILED
REPLAN_LIMIT_REACHED
AGENT_COMPLETED
AGENT_FAILED
```

각 Trace Event는 다음 정보를 포함할 수 있다.

* trace_id
* sequence
* event_type
* occurred_at
* message
* plan_id
* step_id
* tool_name
* attempt_number
* metadata

Trace Event는 하나의 Trace 안에서 1부터 시작하는 연속된 sequence를 가진다.

## 6. Trace Session과 Recorder

`AgentTraceSession`은 하나의 Planning Agent 실행에 대한 Trace 상태를 관리한다.

주요 역할은 다음과 같다.

* trace_id 생성 또는 지정
* Event sequence 자동 증가
* Event 발생 시각 기록
* TraceRecorder에 Event 전달
* 기존 Trace에 이어서 Event 기록

현재 구현된 Recorder는 다음과 같다.

* `TraceRecorder`: 추상 Port
* `InMemoryTraceRecorder`: 메모리 기반 구현

향후 데이터베이스나 외부 Observability 시스템을 사용할 경우 새로운 Recorder Adapter를 추가할 수 있다.

## 7. Trace Timeline과 Summary

원시 Trace Event는 사용자와 운영 시스템이 읽기 쉬운 형태로 변환할 수 있다.

### 7.1 AgentTraceTimeline

Timeline은 Event를 sequence 순서로 정리하고 다음 정보를 제공한다.

* Trace 시작 시각
* Trace 종료 시각
* 전체 실행시간
* Event별 누적 경과시간
* Attempt 번호
* Plan ID
* Step ID
* Tool 이름
* Event 메시지

### 7.2 AgentTraceSummary

Summary는 전체 Trace를 집계하여 다음 정보를 제공한다.

* 최종 Outcome
* 전체 Event 수
* Attempt 수
* Plan 수
* Planning 횟수
* Replanning 횟수
* 시작된 Step 수
* 완료된 Step 수
* 실패한 Step 수
* 건너뛴 Step 수
* 시작된 Tool 실행 수
* 완료된 Tool 실행 수
* 실패한 Tool 실행 수
* 최종 Plan ID
* 최종 메시지
* 전체 실행시간

Trace Outcome은 다음 중 하나이다.

* COMPLETED
* FAILED
* INCOMPLETE

## 8. Trace Export

Trace Timeline과 Summary는 다음 형식으로 Export할 수 있다.

* JSON
* Plain Text
* Markdown

### 8.1 JSON

JSON은 다음 용도로 사용한다.

* API 응답
* 시스템 간 연동
* 데이터 분석
* 장기 저장
* 자동화된 Evaluation

### 8.2 Plain Text

Plain Text는 다음 용도로 사용한다.

* 터미널 출력
* 서버 로그
* 간단한 관리자 확인
* 장애 분석

### 8.3 Markdown

Markdown은 다음 용도로 사용한다.

* GitHub Issue
* 기술 문서
* 실행 보고서
* 운영 검토
* 개발 기록

## 9. Trace File Writer

Export된 Trace는 `AgentTraceFileWriter`를 통해 파일로 저장할 수 있다.

다음 안전 정책을 적용한다.

1. 지정된 출력 디렉터리 안에서만 저장한다.
2. `../` 등의 경로 이탈을 허용하지 않는다.
3. 사용자 지정 파일명에 경로 구분자를 허용하지 않는다.
4. 허용되지 않은 문자를 포함한 파일명을 거부한다.
5. Export 형식과 파일 확장자가 일치해야 한다.
6. 기본적으로 기존 파일을 덮어쓰지 않는다.
7. 명시적으로 허용한 경우에만 덮어쓴다.
8. UTF-8 형식으로 저장한다.
9. Trace ID는 안전한 파일명으로 변환한다.

기본 파일명 예시는 다음과 같다.

```text
trace-001.json
trace-001.txt
trace-001.md
```

## 10. Archive Policy

Trace Archive 기능은 저장 정책을 구조화된 Schema로 관리한다.

설정 가능한 항목은 다음과 같다.

* 저장할 Export 형식
* 완료된 Trace 저장 여부
* 실패한 Trace 저장 여부
* 미완료 Trace 저장 여부
* 기존 파일 덮어쓰기 여부

예시 정책은 다음과 같다.

```text
formats:
  - JSON
  - MARKDOWN

archive_completed: true
archive_failed: true
archive_incomplete: false
overwrite: false
```

Archive Policy에 따라 저장 대상이 아닌 Trace는 오류가 아니라 정상적인 Skip으로 처리한다.

## 11. Retention Policy

저장된 Trace 파일이 무한히 증가하지 않도록 Retention Policy를 적용한다.

지원하는 기준은 다음과 같다.

* 최대 보관 기간
* 최대 파일 수
* Dry Run

### 11.1 최대 보관 기간

`maximum_age_days`보다 오래된 Trace 파일을 정리한다.

### 11.2 최대 파일 수

가장 최근 파일만 `maximum_file_count`만큼 보관하고 오래된 파일을 정리한다.

### 11.3 Dry Run

Dry Run에서는 실제 파일을 삭제하지 않고 삭제 대상만 반환한다.

Retention은 다음 안전 정책을 적용한다.

1. 지정된 출력 디렉터리의 직접 하위 파일만 처리한다.
2. JSON, Text, Markdown 파일만 처리한다.
3. 하위 디렉터리는 탐색하지 않는다.
4. 심볼릭 링크는 처리하지 않는다.
5. 디렉터리 밖의 파일은 삭제하지 않는다.
6. 삭제 직전에 경로와 확장자를 다시 검증한다.
7. 오래된 파일부터 처리한다.

## 12. Maintenance Service

`AgentTraceMaintenanceService`는 Archive와 Retention을 하나의 운영 흐름으로 묶는다.

```text
Trace
    ↓
Archive Policy 적용
    ↓
Trace 파일 저장
    ↓
Retention Policy 적용
    ↓
Maintenance Result
```

Archive와 Retention은 독립적인 단계로 실행된다.

한 단계가 실패하더라도 다른 단계는 가능한 경우 계속 수행한다.

## 13. Maintenance 상태

Maintenance 전체 상태는 다음과 같다.

### SUCCESS

Archive와 Retention이 모두 정상적으로 완료된 상태이다.

Archive Policy에 의해 파일 저장이 생략된 경우에도 Archive 단계는 정상 성공으로 본다.

### PARTIAL_SUCCESS

Archive와 Retention 중 하나만 성공한 상태이다.

예시는 다음과 같다.

* Archive 성공, Retention 실패
* Archive 실패, Retention 성공

### FAILED

Archive와 Retention이 모두 실패한 상태이다.

각 단계의 실패는 구조화된 오류로 기록한다.

오류 정보는 다음을 포함한다.

* 실패 단계
* 예외 타입
* 오류 메시지

## 14. Maintenance Report

`AgentTraceMaintenanceReporter`는 Maintenance Result를 사람이 읽을 수 있는 운영 보고서로 변환한다.

보고서에는 다음 정보가 포함된다.

* Trace ID
* Maintenance 상태
* Headline
* 상세 설명
* 저장된 파일 수
* 검색한 파일 수
* 삭제한 파일 수
* 오류 수

보고서 예시는 다음과 같다.

```text
Trace maintenance completed successfully.

Archive stage completed and wrote 2 file(s).
Retention stage scanned 10 file(s) and deleted 1 file(s).
```

## 15. Alert Evaluation

`AgentTraceMaintenanceAlertEvaluator`는 Maintenance 결과에 따라 Alert 필요 여부를 결정한다.

### SUCCESS

```text
required: false
severity: NONE
```

### PARTIAL_SUCCESS

```text
required: true
severity: WARNING
```

### FAILED

```text
required: true
severity: CRITICAL
```

지원되는 Alert Code는 다음과 같다.

* ARCHIVE_STAGE_FAILED
* RETENTION_STAGE_FAILED
* MULTIPLE_STAGES_FAILED

## 16. Maintenance Operations Service

`AgentTraceMaintenanceOperationsService`는 다음 세 기능을 하나의 Facade로 제공한다.

```text
Maintenance 실행
        ↓
Maintenance Report 생성
        ↓
Alert Evaluation
        ↓
Operations Result
```

Operations Result는 다음 정보를 포함한다.

* Maintenance Result
* Maintenance Report
* Maintenance Alert

각 결과의 Trace ID와 상태는 서로 일치해야 한다.

## 17. Notification Port

Alert 판정과 실제 알림 전송은 분리되어 있다.

```text
AgentTraceMaintenanceAlert
        ↓
AgentTraceAlertNotificationRequest
        ↓
AgentTraceAlertNotifier
        ↓
Notification Adapter
```

현재 구현된 Notification 구성은 다음과 같다.

* `AgentTraceAlertNotifier`: 추상 Port
* `NotificationIdGenerator`: 알림 ID 생성 Port
* `UUIDNotificationIdGenerator`: UUID 기반 구현
* `InMemoryAgentTraceAlertNotifier`: 메모리 기반 구현

## 18. Notification 처리

Alert가 필요한 경우 다음 결과를 반환한다.

```text
status: SENT
notification_id: notification-...
```

Alert가 필요하지 않은 경우 실제 알림을 전송하지 않고 다음 결과를 반환한다.

```text
status: SKIPPED
notification_id: null
```

현재 In-Memory Notifier는 다음 기능을 제공한다.

* Notification Request 기록
* Notification Result 기록
* 전송 ID 생성
* 방어적 복사 반환
* 기록 초기화

## 19. Maintenance Notification Service

`AgentTraceMaintenanceNotificationService`는 Phase 8 운영 흐름의 최종 Facade이다.

```text
Trace ID
    ↓
Maintenance Operations
    ├─ Archive
    ├─ Retention
    ├─ Report
    └─ Alert Evaluation
            ↓
Notification Request
            ↓
Notifier
            ↓
Maintenance Notification Result
```

최종 결과에는 다음 정보가 포함된다.

* Maintenance Operations Result
* Notification Result
* Trace ID

## 20. Phase 8 통합 실행 흐름

Phase 8 전체 흐름은 다음과 같다.

```text
사용자 요청
    ↓
구조화된 초기 Plan 생성
    ↓
Plan 검증
    ↓
Plan 실행
    ↓
Tool 실행 실패
    ↓
Plan Evaluation
    ↓
Replan Required
    ↓
Replan Context 생성
    ↓
Replacement Plan 생성
    ↓
Replacement Plan 실행 성공
    ↓
Goal Achieved
    ↓
Trace Timeline과 Summary 생성
    ↓
JSON·Markdown Export
    ↓
Archive Policy 적용
    ↓
파일 저장
    ↓
Retention Policy 적용
    ↓
Maintenance Report 생성
    ↓
Alert 판정
    ↓
Notification 처리
```

## 21. Phase 8 안전성 원칙

Phase 8에서는 다음 원칙을 적용한다.

1. 자동 재계획 횟수는 제한한다.
2. 구조화된 Planner Output은 결정론적으로 검증한다.
3. Plan 상태와 Tool 실행 결과를 분리한다.
4. 실패한 실행을 무한 반복하지 않는다.
5. 모든 주요 실행 단계는 Trace Event로 기록한다.
6. Trace Event sequence는 연속성을 보장한다.
7. Trace 파일은 지정된 디렉터리 안에서만 관리한다.
8. 파일 덮어쓰기는 명시적으로 허용한 경우에만 수행한다.
9. Retention 삭제 대상은 반복해서 안전성을 검증한다.
10. Archive와 Retention 실패를 독립적으로 기록한다.
11. 운영 오류는 구조화된 Report와 Alert로 변환한다.
12. 실제 Notification 전송은 Port를 통해 분리한다.
13. Alert가 필요하지 않은 경우 Notification을 Skip한다.
14. 외부 시스템 종속 기능은 Adapter로 분리한다.

## 22. Phase 8 완료 기준

다음 흐름이 통합 테스트로 검증되면 Phase 8을 완료한 것으로 본다.

```text
요청
→ 초기 계획
→ 실행 실패
→ 평가
→ 자동 재계획
→ 실행 성공
→ Trace 생성
→ Timeline과 Summary
→ JSON·Markdown Archive
→ Retention
→ Maintenance Report
→ Alert 판정
→ Notification 처리
```

통합 테스트에서 확인하는 핵심 항목은 다음과 같다.

* 초기 Plan과 Replacement Plan이 순서대로 실행되는가
* 최대 재계획 횟수가 적용되는가
* 첫 번째 Attempt 실패가 기록되는가
* 두 번째 Attempt 성공이 기록되는가
* 최종 상태가 GOAL_ACHIEVED인가
* Trace ID가 전체 계층에서 유지되는가
* Attempt 번호가 1과 2로 구분되는가
* Step과 Tool 성공·실패 횟수가 정확한가
* Replanning 횟수가 정확한가
* JSON과 Markdown 파일이 생성되는가
* Retention이 저장된 파일을 인식하는가
* 성공 결과에서 Alert가 발생하지 않는가
* Notification이 SKIPPED로 처리되는가

## 23. 의도적으로 제외한 기능

다음 기능은 Phase 8 필수 범위에서 제외한다.

* 실제 Email 전송
* 실제 Slack 전송
* 실제 Webhook 전송
* SMS 또는 모바일 Push 전송
* 영구 데이터베이스 Trace 저장소
* 분산 Trace 시스템
* OpenTelemetry 연동
* 관리자 Dashboard UI
* 반복 Scheduler
* 메시지 Queue 기반 비동기 Maintenance
* 장기 Archive Storage
* 실시간 Alert Escalation

현재 단계에서는 Interface와 In-Memory 구현을 유지한다.

실제 배포 요구가 발생할 때 필요한 Adapter를 추가한다.

## 24. 주요 설계 결정

### 결정 1: 자동 재계획은 제한한다

무한 실행과 비용 증가를 방지하기 위해 최대 재계획 횟수를 요청에 명시한다.

### 결정 2: Planner Output은 구조화한다

LLM의 자유 형식 응답을 직접 실행하지 않고, Schema 검증을 통과한 Plan만 사용한다.

### 결정 3: 결정론적 검증과 LLM 판단을 분리한다

구조와 제약 조건은 코드로 검증하고, 불확실한 해석과 계획 생성은 LLM에 맡긴다.

### 결정 4: Trace 기록과 실행 로직을 분리한다

Trace Session은 선택적으로 전달되며, Trace가 없어도 기존 실행 기능은 동작한다.

### 결정 5: 외부 저장과 알림은 Port로 분리한다

향후 저장소나 알림 채널을 변경해도 Planning Agent 핵심 로직을 수정하지 않도록 한다.

### 결정 6: 운영 단계는 부분 성공을 허용한다

Archive 실패가 Retention 실행을 막거나, Retention 실패가 Archive 결과를 제거하지 않도록 독립적으로 처리한다.

## 25. Phase 8 결과

Phase 8 완료 후 AIRA는 다음 능력을 갖는다.

* 사용자 요청을 구조화된 Plan으로 변환
* Plan을 결정론적으로 검증
* 실행 가능한 Step을 선택
* 등록된 Tool을 사용하여 Step 실행
* Plan 상태 자동 갱신
* Plan 완료 여부 평가
* 실패 원인을 반영한 자동 재계획
* 전체 실행 Trace 기록
* Trace Timeline과 Summary 생성
* JSON·Text·Markdown Export
* Trace 파일 안전 저장
* Archive Policy 적용
* Retention Policy 적용
* Maintenance 부분 성공·실패 판정
* 운영 Report 생성
* Alert 필요 여부 판정
* Notification Port를 통한 알림 처리

## 26. 다음 Phase

Phase 9에서는 Phase 8의 Planning Agent 위에서 실제 Research Agent Workflow를 구축한다.

예상 범위는 다음과 같다.

* Research Request Schema
* Research Task 분해
* Search Query 계획
* Source Search Tool
* Source Reading Tool
* Evidence Extraction
* Evidence 저장과 추적
* Citation 관리
* Source 신뢰도 평가
* Research Synthesis
* Research Quality Evaluation
* Research 결과 보고서 생성

Phase 9에서는 실제 Research Workflow에 필요한 최소 기능부터 구현하며, Phase 8처럼 운영 부가 기능을 지나치게 확장하지 않는다.
