# Phase 11 Reliability Baseline

## 1. Baseline 목적

이 문서는 Phase 11 완료 시점의 평가, Guardrail 및 Reliability 기능을 기준선으로 고정한다.

Phase 12 이후 Application, Persistence, Background Job 또는 Deployment 기능을 추가할 때 현재 기준선과 비교하여 기능 및 품질 회귀 여부를 판단한다.

---

## 2. Baseline 식별 정보

| 항목 | 값 |
|---|---|
| 프로젝트 | AIRA — Agentic Intelligence Research Assistant |
| Phase | Phase 11 |
| 주제 | Evals, Guardrails, Reliability |
| 기준일 | 2026-08-04 |
| Python | 3.12 |
| Validation | Pydantic strict and frozen schemas |
| Test Runner | `python -m pytest -q` |
| Linter | `ruff check .` |
| Baseline 상태 | PASS |

Git Commit Hash는 Phase 11 문서 Commit 후 아래 명령으로 확인한다.

```bash
git rev-parse HEAD
```

## 3. Baseline 검증 명령

Phase 11 기준선을 검증하는 공식 명령은 다음과 같다.

```bash
python -m pytest -q
ruff check .
git status --short
```

통과 조건은 다음과 같다.

- 모든 Pytest Test가 통과한다.

- Ruff 오류가 없다.

- 의도하지 않은 Working Tree 변경이 없다.


---

## 4. Evaluation Baseline

현재 시스템은 다음 평가 기능을 제공한다.

| 평가 영역                           | 상태   |
| ------------------------------- | ---- |
| Evaluation Dataset Schema       | PASS |
| Evaluation Case Definition      | PASS |
| Expected Outcome Schema         | PASS |
| Evaluation Result Schema        | PASS |
| Deterministic Evaluation Runner | PASS |
| Citation Correctness Evaluator  | PASS |
| Evidence Grounding Evaluator    | PASS |
| Claim Support Evaluator         | PASS |
| Report Quality Rubric           | PASS |
| Multi-Agent Workflow Evaluator  | PASS |
| Regression Evaluation Runner    | PASS |

---

## 5. Guardrail Baseline

현재 시스템은 다음 Guardrail 기능을 제공한다.

|Guardrail 영역|상태|
|---|---|
|Guardrail Policy Schema|PASS|
|Guardrail Violation Schema|PASS|
|Guardrail Evaluation Result|PASS|
|Input Guardrail|PASS|
|Output Guardrail|PASS|
|Tool Permission Guardrail|PASS|
|Blocking Decision|PASS|
|Warning Decision|PASS|
|Remediation Information|PASS|

---

## 6. Reliability Baseline

현재 시스템은 다음 신뢰성 기능을 제공한다.

|Reliability 영역|상태|
|---|---|
|Retry Failure Classification|PASS|
|Maximum Attempt Control|PASS|
|Fixed Backoff|PASS|
|Linear Backoff|PASS|
|Exponential Backoff|PASS|
|Retry-After|PASS|
|Full Jitter|PASS|
|Equal Jitter|PASS|
|Soft Timeout|PASS|
|Hard Timeout|PASS|
|Absolute Deadline|PASS|
|Graceful Cancellation|PASS|
|Force Cancellation|PASS|
|Cancellation Grace Period|PASS|
|Alternate Tool Recovery|PASS|
|Alternate Agent Recovery|PASS|
|Cached Result Recovery|PASS|
|Partial Result Recovery|PASS|
|Manual Review|PASS|
|Safe Abort|PASS|
|Reliability Metrics|PASS|

---

## 7. Reliability Metric Definitions

### Success Rate

```text
successful_executions / total_executions
```

### Failure Rate

```text
failed_executions / total_executions
```

### Timeout Rate

```text
timed_out_executions / total_executions
```

### Retry Rate

```text
retried_executions / total_executions
```

### Retry Success Rate

```text
successful_retried_executions / retried_executions
```

### Recovery Attempt Rate

```text
recovery_attempts / total_executions
```

### Recovery Success Rate

```text
recovery_successes / recovery_attempts
```

### Guardrail Block Rate

```text
guardrail_blocks / guardrail_evaluations
```

분모가 0인 경우 결과는 `0.0`이다.

---

## 8. Phase 11 E2E Baseline Scenario

현재 E2E Baseline은 다음 시나리오를 통과한다.

1. 정상 Assignment가 Input Guardrail을 통과한다.

2. Allowlist에 없는 Tool이 차단된다.

3. 허용된 Tool은 실행 허가를 받는다.

4. 첫 번째 Tool 실행이 Timeout으로 실패한다.

5. Retry Policy가 두 번째 Attempt를 허용한다.

6. 두 번째 Attempt에서 최대 재시도 횟수에 도달한다.

7. Failure Recovery가 Alternate Tool을 선택한다.

8. Alternate Tool 실행이 성공한다.

9. Reliability Metrics가 전체 실행을 집계한다.


E2E Baseline의 기대 결과는 다음과 같다.

|항목|기대 결과|
|---|---|
|Input Guardrail|ALLOWED|
|Unknown Tool|BLOCKED|
|Allowed Tool|ALLOWED|
|First Retry Decision|RETRY|
|Final Retry Decision|STOP|
|Stop Reason|MAXIMUM_ATTEMPTS_REACHED|
|Recovery Strategy|ALTERNATE_TOOL|
|Final Fallback Execution|SUCCEEDED|
|Reliability Metrics 생성|PASS|

---

## 9. Regression Blocking 조건

다음 변화가 발생하면 Phase 11 Baseline Regression으로 처리한다.

- 기존 통과 Test가 실패한다.

- Ruff 오류가 발생한다.

- Evaluation Result가 PASSED에서 FAILED로 변경된다.

- 새로운 Blocking Violation이 발생한다.

- Overall Score가 허용 범위를 초과해 하락한다.

- 필수 Dimension Score가 허용 범위를 초과해 하락한다.

- Input Guardrail이 유효한 Assignment를 차단한다.

- Tool Guardrail이 금지된 Tool을 허용한다.

- Retry Policy가 Validation 또는 Permission 오류를 재시도한다.

- Hard Timeout 이후 실행이 계속된다.

- Retry 소진 전 Recovery가 실행된다.

- 사용할 수 없는 Fallback Resource가 선택된다.

- Reliability Count와 Rate의 정합성이 깨진다.


---

## 10. Non-Blocking 관찰 항목

다음 변화는 자동 Blocking 대상은 아니지만 검토한다.

- Token 사용량 증가

- Tool Call 수 증가

- 평균 실행시간 증가

- P95 실행시간 증가

- Retry Rate 증가

- Manual Review 비율 증가

- Guardrail Warning 증가

- Cache Fallback 사용 증가


이 항목은 품질 오류가 아닐 수 있으므로 원인과 비용을 별도로 분석한다.

---

## 11. Phase 12 변경 관리 원칙

Phase 12에서 다음 구성요소를 추가할 때 Phase 11 Baseline을 유지해야 한다.

- Database Repository

- Job Queue

- Scheduler

- Retry Worker

- Cancellation Persistence

- API Layer

- Application Service

- Background Execution

- Reliability Query Service


Phase 12의 모든 기능은 기존 Evaluator와 Guardrail을 우회해서는 안 된다.

---

## 12. Baseline 재검증 절차

중요 변경 후 다음 절차를 수행한다.

```bash
python -m pytest -q
ruff check .
git diff --check
git status --short
```

필요한 경우 특정 Phase 11 테스트를 별도로 실행한다.

```bash
python -m pytest \
  tests/test_phase11_e2e_evaluator.py \
  tests/test_regression_evaluation_runner.py \
  tests/test_input_guardrail_evaluator.py \
  tests/test_output_guardrail_evaluator.py \
  tests/test_tool_permission_guardrail_evaluator.py \
  tests/test_retry_policy_evaluator.py \
  tests/test_execution_control_evaluator.py \
  tests/test_failure_recovery_evaluator.py \
  tests/test_reliability_metrics_calculator.py \
  -q
```

---

## 13. Baseline 결론

Phase 11 완료 시점에서 AIRA는 다음 능력을 갖는다.

- Research 결과의 구조화된 품질 평가

- Baseline 대비 Regression 탐지

- Input, Output 및 Tool 실행 통제

- 실패 유형에 따른 Retry 판단

- Backoff 및 Jitter 계산

- Timeout 및 Cancellation 제어

- Retry 소진 후 안전한 Recovery

- 실행 Reliability 지표 계산

- Phase 11 전체 E2E 검증


이 기준선은 Phase 12 Application Integration의 출발점이다.
