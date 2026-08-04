# Agentic AI Lab — CURRICULUM

## 교육 방식

각 수업은 다음 구조를 기본으로 한다.

1. 현재 위치와 사용자 가치
2. 필요한 핵심 이론
3. 전체 구조
4. 최소 구현
5. 실제 실행
6. 테스트와 실패 분석
7. 사용성 평가
8. 학습 기록

모든 항목을 기계적으로 분리하지 않는다.
간단한 Lesson은 필요한 항목만 사용한다.

## 전체 Phase 구조

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

Phase 0부터 Phase 12까지 완료하였다.

Phase 13은 최종 Phase다.

## 학습 및 개발 원칙

- Single Agent를 기본으로 한다.
- Planning과 Memory는 필요한 요청에만 사용한다.
- Multi-Agent는 비교 평가에서 이점이 확인된 경우에만 사용한다.
- 새 기능보다 실제 연구 흐름 완성을 우선한다.
- 기존 코드 재사용을 우선한다.
- 세부 추상화를 위한 추상화를 만들지 않는다.
- 실제 실행 결과와 사용자 효용을 평가한다.
- Phase 13 이후 신규 Phase는 만들지 않는다.

## Phase 13 학습 범위

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

## 평가 방식

각 Phase는 다음 영역으로 평가한다.

- 개념 이해
- 설계 판단
- 구현 능력
- 결과 검증
- 실제 사용 가능성
- 불필요한 복잡성 통제

## 최종 결과

필수:

- AIRA CLI
- Single Research Agent 기본 경로
- Source, Evidence, Claim, Citation 추적
- 근거 기반 보고서
- Eval과 Guardrail
- 실행 상태와 결과 저장
- Docker 실행환경
- 실제 사용 예제
- 사용자 가이드

선택:

- 최소 FastAPI
- SQLite
- 제한된 Multi-Agent 비교
- 간단한 Human Approval

현재 완료 조건에 포함하지 않음:

- Redis
- Nginx
- Kubernetes
- 분산 Worker
- 상용 Web UI
- 대규모 운영 플랫폼
