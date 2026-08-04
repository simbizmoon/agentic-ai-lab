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

