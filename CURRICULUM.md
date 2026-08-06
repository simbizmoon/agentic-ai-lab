# Agentic AI Lab — CURRICULUM

## 1. 문서 상태

- 상태: 완료된 학습 이력
- 적용 범위: 기존 Phase 0부터 Phase 13
- 현재 제품 개발 기준: 아님
- 최상위 제품 기준: `AIRA_PROJECT_CHARTER.md`
- 프로젝트 운영 기준: `MASTER.md`
- 확정 결정과 변경 이력: `DECISIONS.md`
- 현재 실행계획: `ROADMAP.md`

본 문서는 Agentic AI Lab 프로젝트에서 Phase 0부터 Phase 13까지 수행한
학습과 구현 순서를 기록한다.

현재 프로젝트의 주목적은 교육과정을 계속 진행하는 것이 아니라,
실제로 유용하고 사용 가능한 AIRA를 구축하는 것이다.

따라서 앞으로의 제품 개발 작업은 본 문서의 Phase 또는 Lesson 구조가 아니라
`AIRA_PROJECT_CHARTER.md`, `MASTER.md`, `DECISIONS.md` 및
`ROADMAP.md`에 정의된 Stage와 Integration Work Item을 따른다.

본 문서는 다음 목적으로만 사용한다.

- 기존 학습 이력 확인
- 특정 Component를 학습한 배경 확인
- 기존 Phase와 Lesson의 목적 확인
- 필요한 개념 복습
- Existing Capability Audit의 보조 자료
- 기존 코드가 만들어진 맥락 확인

본 문서의 내용이 현재 기준 문서와 충돌할 경우 현재 기준 문서를 우선한다.

---

## 2. 기존 교육 방식

각 수업은 다음 구조를 기본으로 하였다.

1. 현재 위치와 사용자 가치
2. 필요한 핵심 이론
3. 전체 구조
4. 최소 구현
5. 실제 실행
6. 테스트와 실패 분석
7. 사용성 평가
8. 학습 기록

모든 항목을 기계적으로 분리하지 않았다.

간단한 Lesson은 필요한 항목만 사용하였다.

이 교육 방식은 현재에도 특정 개념을 복습하거나 새로운 기술을 이해할 때
참고할 수 있지만, 향후 제품 개발 Work Item의 필수 형식은 아니다.

---

## 3. 완료된 기존 Phase 구조

0. 프로젝트 기반
1. Agentic AI 기초
2. OpenAI API 기초
3. Structured Outputs와 데이터 검증
4. Tool Calling
5. Workflow와 상태 관리
6. RAG
7. Memory
8. Planning Agent
9. Single Research Agent
10. 제한된 Multi-Agent Research
11. Evals, Guardrails, Reliability
12. Application, Persistence, Background Jobs
13. Practical AIRA Integration and Delivery

Phase 0부터 Phase 13까지의 학습과 기존 구현 과정은 완료되었다.

Phase 13은 기존 교육과정의 마지막 Phase이며,
AIRA 제품 개발 전체의 종료를 의미하지 않는다.

향후 제품 통합은 신규 학습 Phase가 아니라
`ROADMAP.md`에 정의된 Stage와 Integration Work Item으로 관리한다.

---

## 4. 기존 학습 및 개발 원칙

기존 교육과정은 다음 원칙으로 진행되었다.

- Single Agent를 기본으로 한다.
- Planning과 Memory는 필요한 요청에만 사용한다.
- Multi-Agent는 비교 평가에서 이점이 확인된 경우에만 사용한다.
- 새 기능보다 실제 연구 흐름 완성을 우선한다.
- 기존 코드 재사용을 우선한다.
- 세부 추상화를 위한 추상화를 만들지 않는다.
- 실제 실행 결과와 사용자 효용을 평가한다.
- 테스트 수 자체보다 사용자 흐름을 보호한다.
- 코드와 문서를 함께 관리한다.

현재에도 유효한 원칙은 `MASTER.md`와 `DECISIONS.md`에 반영되어 있다.

기존 교육과정은 Phase 13에서 종료하였다.

향후 제품 개발은 신규 교육 Phase가 아니라 Stage와 Work Item으로 관리한다.

---

## 5. 기존 Phase 13 학습 및 구현 범위

다음 항목은 Phase 13 당시의 목표였으며,
현재는 결정론적 Offline Baseline의 개발 이력으로 분류한다.

1. 최종 AIRA 사용 시나리오 확정
2. 기존 모듈의 통합 경로 정리
3. CLI 연구 실행
4. 최소 영속 저장
5. 선택적인 최소 FastAPI
6. 실제 문서 또는 연구 주제 실행
7. 결과 품질과 비용 확인
8. Docker 실행환경
9. 사용자 가이드와 운영 메모
10. 최종 평가

Phase 13 결과는 폐기하지 않는다.

다음 목적으로 유지한다.

- Offline Baseline
- Schema 검증
- Pipeline Regression Test
- 외부 API 없는 실행 경로
- 향후 LLM 기반 AIRA와의 비교 기준

현재 AIRA 제품 목표는 Phase 13의 범위보다 확장되었다.

주요 확장 목표:

- 실제 인터넷 검색
- 인터넷과 로컬 문서 통합 조사
- OpenAI Responses API 또는 교체 가능한 LLM Provider
- Tool을 사용하는 Single Research Agent
- Evidence Sufficiency 기반 제한된 Replanning
- Source 중요도·신뢰도·최신성 평가
- 자료 정리·요약·비교·분석
- 근거 기반 제안사항
- Citation 검증
- 비용과 Budget 관리
- PDF, HWP 및 HWPX
- Hybrid RAG
- 다른 상용 LLM과 로컬 LLM 비교

상세한 현재 목표는 `AIRA_PROJECT_CHARTER.md`와 `ROADMAP.md`를 따른다.

---

## 6. 기존 평가 방식

각 Phase는 다음 영역으로 평가하였다.

- 개념 이해
- 설계 판단
- 구현 능력
- 결과 검증
- 실제 사용 가능성
- 불필요한 복잡성 통제

현재 제품 개발에서도 위 기준의 일부는 유지한다.

그러나 현재의 주요 평가는 다음으로 확장된다.

- 실제 사용자 흐름
- Search Relevance
- Retrieval Relevance
- Evidence Coverage
- Source Quality
- Citation Accuracy
- Claim Support
- Contradiction Detection
- Recommendation Grounding
- Hallucination Rate
- 비용
- 처리시간
- 재현성
- 유지관리 가능성

현재 평가 기준과 Stage Gate는 `MASTER.md`와 `ROADMAP.md`를 따른다.

---

## 7. 기존 교육과정의 완료 결과

기존 교육과정은 다음 결과를 목표로 하였다.

### 필수 결과

- AIRA CLI
- Single Research Agent 기본 경로
- Source, Evidence, Claim 및 Citation 추적
- 근거 기반 보고서
- Eval과 Guardrail
- 실행 상태와 결과 저장
- Docker 실행환경
- 실제 사용 예제
- 사용자 가이드

### 선택 결과

- 최소 FastAPI
- SQLite
- 제한된 Multi-Agent 비교
- 간단한 Human Approval

### 기존 완료 조건에 포함하지 않았던 항목

- Redis
- Nginx
- Kubernetes
- 분산 Worker
- 상용 Web UI
- 대규모 운영 Platform

위 결과는 기존 Phase 13 Baseline의 범위다.

현재 AIRA의 최종 완료 조건은 `AIRA_PROJECT_CHARTER.md`,
`MASTER.md` 및 `ROADMAP.md`를 따른다.

---

## 8. 현재 프로젝트에서의 활용 방법

본 문서는 ChatGPT `Agentic AI Lab` 프로젝트의 핵심 Source로
등록하지 않는 것을 원칙으로 한다.

이유:

- 현재 제품 개발보다 과거 교육과정에 초점이 맞춰져 있음
- 기존 Phase와 Lesson 구조가 현재 Stage 운영과 혼동될 수 있음
- Phase 13 당시의 축소된 Baseline 목표가 현재 목표로 오해될 수 있음
- 핵심 Source의 문맥을 불필요하게 증가시킬 수 있음

다음 경우에만 참고한다.

- 특정 Phase에서 무엇을 학습했는지 확인할 때
- 기존 코드의 학습 목적과 배경을 확인할 때
- Existing Capability Audit 중 관련 Phase를 추적할 때
- 특정 개념을 복습할 때

Git 저장소에서는 프로젝트의 완료된 학습 이력으로 보존한다.

---

## 9. 현재 기준 문서

현재 AIRA 제품 개발에는 다음 문서를 사용한다.

### 필수 제품·운영 기준

1. `AIRA_PROJECT_CHARTER.md`
2. `MASTER.md`
3. `DECISIONS.md`
4. `ROADMAP.md`

### 작성 후 추가할 핵심 문서

5. `AIRA_PROJECT_AUDIT_REPORT.md`
6. `AIRA_CAPABILITY_MATRIX.md`
7. `AIRA_TARGET_PRODUCT_SPEC.md`
8. `AIRA_TARGET_ARCHITECTURE.md`
9. `AIRA_TOOL_SKILL_REGISTRY.md`
10. `AIRA_INTEGRATION_PLAN.md`

### 보조 이력 문서

- `CURRICULUM.md`
- `LEARNING_LOG.md`
- 기존 Phase 및 Lesson 문서

현재 구현 상태는 문서의 주장보다 실제 코드, 테스트 및 실행 결과를
우선하여 판단한다.
