# Agentic AI Lab — ROADMAP

## 진행상태

- `[ ]` 시작 전
- `[~]` 진행 중
- `[x]` 완료
- `[!]` 보충 필요
- `[-]` 보류

## 현재 위치

- 현재 Phase: Phase 13 — Practical AIRA Integration and Delivery
- 현재 상태: 시작 전
- 완료된 Phase: Phase 0부터 Phase 12
- 전체 테스트 기준선: 4048 passed
- Ruff: All checks passed
- 다음 단계: 최종 AIRA 사용 시나리오와 통합 경로 확정
- 종료 원칙: Phase 13 완료 후 프로젝트를 종료하고 Backlog는 별도 관리
- 범위 원칙: 실제 사용 가능한 최소 AIRA에 직접 필요한 작업만 수행

## 완료된 Phase

- [x] Phase 0 — 프로젝트 기반
- [x] Phase 1 — Agentic AI 기초
- [x] Phase 2 — OpenAI API 기초
- [x] Phase 3 — Structured Outputs와 데이터 검증
- [x] Phase 4 — Tool Calling
- [x] Phase 5 — Workflow와 상태 관리
- [x] Phase 6 — RAG
- [x] Phase 7 — Memory
- [x] Phase 8 — Planning Agent
- [x] Phase 9 — Single Research Agent
- [x] Phase 10 — Multi-Agent Research System
- [x] Phase 11 — Evals, Guardrails, Reliability
- [x] Phase 12 — Application, Persistence, Background Jobs

## 이미 확보된 핵심 자산

### 연구 기능

- Research Request와 Task 분해
- Search Query 계획
- Source Search와 Reader Port
- Evidence 추출
- Source 품질 평가
- Claim과 Citation 연결
- Research Workspace
- Report Synthesis
- Single-Agent 및 Multi-Agent 연구 흐름

### 품질과 안전

- Evaluation Dataset과 Runner
- Citation, Evidence, Claim Support 평가
- Guardrail
- Retry, Timeout, Cancellation
- Reliability Metrics
- E2E Evaluation

### Application 기반

- Execution, Evaluation, Guardrail, Job Repository
- Background Job Lifecycle
- Queue와 Lease
- Retry Scheduling
- Cancellation Persistence
- Research, Tool, Workflow Application Service
- Reliability Query
- Transaction Boundary
- Idempotency
- Failure Mapping
- Phase 12 E2E Flow

## Phase 13 — Practical AIRA Integration and Delivery

- 상태: 시작 전
- 최대 Lesson: 10개
- 최종 Phase: 예

### Lesson 13.1 — 제품 사용 시나리오와 범위 확정

- [ ] 핵심 사용자 1명과 주요 사용 시나리오 확정
- [ ] 입력, 처리, 출력의 단일 기본 흐름 확정
- [ ] 사용하지 않을 고급 기능 명시
- 완료 결과: `AIRA_MVP_SPEC.md`

### Lesson 13.2 — 기존 모듈 통합 지도

- [ ] 실제 기본 경로에 필요한 기존 모듈 선택
- [ ] 중복 또는 미사용 모듈 분류
- [ ] Composition Root 설계
- 완료 결과: 한 장의 Runtime Architecture와 의존성 구성

### Lesson 13.3 — AIRA CLI

- [ ] 연구 질문 또는 파일 입력
- [ ] Single Research Agent 실행
- [ ] 진행 상태 표시
- [ ] 보고서와 Citation 출력
- 완료 결과: 실제 사용할 수 있는 CLI 명령

### Lesson 13.4 — 최소 영속 저장

- [ ] 실행 요청과 결과 저장
- [ ] 보고서 재조회
- [ ] 중복 요청 처리
- [ ] SQLite 또는 기존 In-Memory 중 실제 필요에 맞게 선택
- 완료 결과: 프로그램 재실행 후 결과를 다시 확인할 수 있음

### Lesson 13.5 — 실제 연구 사례 1

- [ ] 프로젝트 문서 분석 또는 기술 조사 실행
- [ ] Source와 Citation 검토
- [ ] 불필요한 단계와 기능 제거
- 완료 결과: 첫 실제 AIRA 보고서

### Lesson 13.6 — 실제 연구 사례 2와 품질 보완

- [ ] 다른 유형의 연구 요청 실행
- [ ] 평가와 Guardrail 확인
- [ ] 품질이 낮은 지점만 최소 수정
- 완료 결과: 재현 가능한 두 번째 사례

### Lesson 13.7 — 실제 연구 사례 3과 사용성 평가

- [ ] 실용적인 세 번째 사례 실행
- [ ] 시간, 비용, 결과 품질 기록
- [ ] Single-Agent 기본 경로 확정
- [ ] Multi-Agent는 필요할 때만 비교
- 완료 결과: AIRA 효용 평가표

### Lesson 13.8 — 선택적 최소 API

- [ ] CLI만으로 충분한지 먼저 판단
- [ ] 필요할 경우에만 FastAPI 실행·조회 Endpoint 추가
- [ ] 복잡한 인증, 다중 사용자와 Web UI는 제외
- 완료 결과: 선택적 로컬 API

### Lesson 13.9 — Docker와 운영 최소화

- [ ] Dockerfile
- [ ] 필요한 경우에만 Docker Compose
- [ ] 환경변수와 Secret
- [ ] 로그와 기본 백업 방법
- 완료 결과: 재현 가능한 로컬 실행환경

### Lesson 13.10 — 최종 문서화와 종료 평가

- [ ] 전체 아키텍처
- [ ] 사용자 가이드
- [ ] 개발자 메모
- [ ] 알려진 제한
- [ ] Backlog 분리
- [ ] 최종 E2E와 실제 사용 검증
- 완료 결과: Final AIRA Baseline

## Phase 13 완료 기준

- [ ] CLI에서 연구 요청을 실행할 수 있다.
- [ ] Source, Evidence, Claim과 Citation을 추적할 수 있다.
- [ ] 근거 기반 보고서를 생성한다.
- [ ] 실행과 결과를 저장하고 재조회할 수 있다.
- [ ] 기본 Eval과 Guardrail을 실행한다.
- [ ] 실제 사용 사례 3개가 존재한다.
- [ ] Docker에서 재현 가능하다.
- [ ] 사용자 가이드가 존재한다.
- [ ] 전체 pytest와 Ruff가 통과한다.
- [ ] 불필요한 고급 기능이 기본 경로에서 제거되거나 비활성화된다.

## 보류 Backlog

아래 항목은 Phase 13 범위가 아니다.

- [-] PostgreSQL 전환
- [-] Redis Queue
- [-] 분산 Worker
- [-] Nginx와 HTTPS
- [-] OCI 운영 배포
- [-] CI/CD 고도화
- [-] Prometheus, Grafana와 OpenTelemetry 전체 구성
- [-] 복잡한 인증과 RBAC
- [-] 협업 Workspace
- [-] 상용 Web UI
- [-] Kubernetes
- [-] 추가 보안·암호화 하위 시스템

Backlog 항목은 실제 사용 중 필요가 확인되고 사용자가 별도 승인한 경우에만
새 프로젝트 또는 후속 버전으로 진행한다.
