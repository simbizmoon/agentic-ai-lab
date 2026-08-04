# Agentic AI Lab — DECISIONS

## D-001 — 기본 운영체제

- 상태: 확정
- 날짜: 2026-07-23
- 결정: Ubuntu를 기본 개발환경으로 사용한다.

## D-002 — 프로젝트 경로

- 상태: 확정
- 날짜: 2026-07-23
- 경로: `/home/moon/Project/agentic-ai-lab`

## D-003 — 원격 저장소

- 상태: 확정
- 날짜: 2026-07-23
- 주소: `https://github.com/simbizmoon/agentic-ai-lab.git`
- 기본 브랜치: `main`

## D-004 — Python 환경

- 상태: 확정
- 날짜: 2026-07-23
- Python: 3.12
- 가상환경: `/home/moon/Project/agentic-ai-lab/.venv`

## D-005 — 기본 언어

- 상태: 확정
- 날짜: 2026-07-23
- 수업과 주요 문서: 한국어
- 코드 식별자와 기술 표준: 영어

## D-006 — 기본 백엔드

- 상태: 확정
- 날짜: 2026-08-03
- 언어: Python
- API Framework: FastAPI
- 데이터 검증: Pydantic
- 적용 원칙: FastAPI는 최종 사용 흐름에 필요한 최소 API에만 사용한다.

## D-007 — 에이전트 개발 순서

- 상태: 확정
- 날짜: 2026-07-23
- 결정: Single Agent를 기본 실행 경로로 사용한다.
- Multi-Agent는 품질 향상이 평가로 확인될 때만 선택적으로 사용한다.

## D-008 — 데이터 저장

- 상태: 수정 확정
- 최초 날짜: 2026-07-23
- 수정 날짜: 2026-08-05
- 소스와 문서: Git 프로젝트
- 개발용 영속 저장: SQLite 우선
- PostgreSQL: 실제 동시 사용자 또는 운영 요구가 확인될 때 전환
- Redis: 현재 범위에서 보류
- Secret: Git에서 제외된 환경변수 또는 Secret 저장소

## D-009 — 인간 승인

다음 작업은 사용자 승인 후 수행한다.

- GitHub Push
- 외부 이메일 발송
- 데이터 삭제
- 운영 서버 배포
- 운영 데이터베이스 변경
- 비용 증가 작업
- 개인정보 외부 전송
- 보안 설정 변경

## D-010 — 전체 Phase 구조

- 상태: 대체됨
- 최초 날짜: 2026-08-03
- 대체 결정: D-013
- 이유: 실제 진행 결과 Phase 9부터 Phase 12까지 역할이 세분화되었으므로
  현재 구현 상태와 최종 목표에 맞게 구조를 다시 정렬한다.

## D-011 — Phase 3 보안 심화 기능 동결

- 상태: 확정
- 날짜: 2026-08-03
- 결정: Transparency Log, Merkle Proof, Witness Quorum,
  Signed Gossip Bundle과 Trust Decision Receipt는 동결한다.
- 재개 조건: 실제 운영 요구 또는 구체적인 보안 위협 모델이 확인된 경우

## D-012 — 프로젝트 범위 재설정

- 상태: 확정
- 날짜: 2026-08-05
- 결정: 프로젝트는 Phase 13에서 종료한다.
- 결정: Phase 14 이후의 신규 Phase를 만들지 않는다.
- 이유: 학습과 구현이 원래의 실용적 AIRA 목표보다 세밀하게 확장되었다.
- 목표: 로컬에서 실제 연구에 사용할 수 있는 최소 AIRA를 완성한다.
- 보류:
  - 분산 Worker Cluster
  - Redis 또는 RabbitMQ Queue
  - Kubernetes
  - 복잡한 조직·권한 시스템
  - 대규모 Observability Stack
  - 상용 수준 Web UI
  - 완전 자율 Multi-Agent 조직

## D-013 — 최종 Phase 구조

- 상태: 확정
- 날짜: 2026-08-05

최종 Phase 구조:

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

Phase 13은 최종 Phase이며, 실제 사용 흐름과 배포 가능한 최소 환경만
완성한다.

## D-014 — 최종 AIRA MVP

- 상태: 확정
- 날짜: 2026-08-05

필수 결과:

- CLI 연구 실행
- 프로젝트 문서 또는 준비된 Source 입력
- Evidence, Claim, Citation 추적
- 근거 기반 보고서
- 기본 평가와 Guardrail
- 실행 및 결과 저장
- 핵심 실패 처리
- 실제 예제 3개
- Docker 실행환경
- 사용자 가이드

선택 결과:

- 최소 FastAPI
- SQLite 영속화
- 제한된 Multi-Agent 비교
- 간단한 승인 단계

PostgreSQL, Redis, Nginx, OCI 운영 배포는 실제 필요가 있을 때 별도
Backlog에서 결정한다.

## D-015 — Lesson과 구현 단위 제한

- 상태: 확정
- 날짜: 2026-08-05
- 결정:
  - Phase 13은 최대 10개 Lesson으로 제한한다.
  - 하나의 작은 Schema 또는 Error Class만을 위한 Lesson을 만들지 않는다.
  - 각 Lesson은 사용자가 실행할 수 있는 기능 또는 통합 결과를 만든다.
  - 테스트 수 증가 자체를 목표로 하지 않는다.
  - 기존 구현을 재사용하고 중복 추상화를 금지한다.
