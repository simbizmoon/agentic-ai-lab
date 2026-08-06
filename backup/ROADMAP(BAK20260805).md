# Agentic AI Lab — ROADMAP

## 진행상태

- `[ ]` 시작 전
- `[~]` 진행 중
- `[x]` 완료
- `[!]` 보충 필요
- `[-]` 보류

## 현재 위치

- 현재 Phase: Phase 9 — Single Research Agent Workflow
- 현재 Lesson: Lesson 9.1 — Research Request Schema
- 현재 상태: 시작
- 완료된 Phase: Phase 0부터 Phase 8
- 다음 단계: Research Request Domain Schema와 결정론적 검증 구현
- 운영 원칙: Phase 9는 20개 Lesson으로 제한하며 Single-Agent Baseline 완성에 집중한다.
- 후속 원칙: Phase 10에는 Multi-Agent Research System을 필수로 구현한다.

## Phase 0 — 프로젝트 기반

- 상태: 완료

- [x] ChatGPT Project 생성
- [x] Work와 Plugins 확인
- [x] Ubuntu 개발환경 확인
- [x] 저장공간 확인
- [x] 프로젝트 경로 확정
- [x] Git 저장소 초기화
- [x] GitHub 원격 연결
- [x] Python 가상환경 생성
- [x] 기준 문서 작성
- [x] 문서 검증
- [x] 첫 Commit과 Push
- [x] Codex CLI 설치
- [x] Codex 읽기 전용 분석
- [x] 제한된 Codex 문서 수정 실습
- [x] Git Diff와 Commit 검증
- [x] Phase 0 평가

## Phase 1 — Agentic AI 기초

- 상태: 완료

- [x] 생성형 AI와 LLM
- [x] Chatbot, Workflow 및 Agent
- [x] Goal, Environment, State, Action, Observation
- [x] Agent Loop
- [x] Deterministic과 Probabilistic 처리
- [x] 자율성 단계
- [x] Agent가 필요하지 않은 문제
- [x] 비교 실험
- [x] 평가

## Phase 2 — OpenAI API 기초

- 상태: 완료

- [x] API와 SDK
- [x] API Key와 환경변수
- [x] HTTP Request와 Response
- [x] OpenAI Python SDK
- [x] Responses API 첫 호출
- [x] Token과 Context
- [x] 오류 처리와 종료 코드
- [x] 사용량·비용·로그 기초
- [x] Secret 비노출 검증
- [x] 평가

## Phase 3 — Structured Outputs와 데이터 검증

- 상태: 완료

- [x] JSON과 JSON Schema
- [x] Pydantic 모델과 검증
- [x] Structured Outputs
- [x] 모델 응답 검증
- [x] 오류 분류와 복구
- [x] 결정적 직렬화와 무결성 검증 실습
- [x] 서명된 감사 산출물과 오프라인 검증 심화 실습
- [x] 동일 입력 재사용과 의미적 충돌 검증
- [x] AIRA 문서 분석 Structured Output
- [x] Phase 3 최종 평가

### Phase 3 범위 조정

Phase 3에서 구현한 Transparency Log, Merkle Proof, Witness Quorum,
Signed Gossip Bundle 및 Trust Decision Receipt는 고급 심화 실습으로
완료하였다.

이 하위 시스템은 현재 상태로 동결하며, 추가적인 암호화·분산 신뢰
기능은 실제 AIRA 운영 요구가 확인되기 전까지 확장하지 않는다.

Tool Calling은 다음 Phase에서 최소 단일 Tool부터 별도로 학습한다.

## Phase 4 — Tool Calling

- 상태: 진행 중

- [~] Tool의 개념과 역할
- [ ] 단일 Tool 정의와 호출
- [ ] Tool 함수 Schema
- [ ] Tool 호출 인수 검증
- [ ] Tool 실행 결과를 Observation으로 전달
- [ ] Tool 오류 처리
- [ ] 허용 Tool과 금지 Tool
- [ ] 여러 Tool 중 선택
- [ ] Tool 호출 테스트
- [ ] Phase 4 평가

## Phase 5 — Workflow와 상태 관리

- 상태: 시작 전

- [ ] Workflow와 Agent Loop의 차이
- [ ] 단계별 Workflow 설계
- [ ] Workflow State 정의
- [ ] 단계 전환 조건
- [ ] 상태 저장과 복원
- [ ] Checkpoint와 Resume
- [ ] Retry와 Timeout
- [ ] Stop Condition
- [ ] 실패 상태와 복구 경로
- [ ] Human Approval 단계
- [ ] Phase 5 평가

## Phase 6 — RAG

- 상태: 완료
- 상세 문서: `docs/lessons/phase-6-rag.md`

## Phase 7 — Memory

- 상태: 완료
- 상세 문서: `docs/lessons/phase-7-memory.md`

## Phase 8 — Planning Agent

- 상태: 완료
- 마지막 Lesson: Lesson 8.33
- 상세 문서: `docs/lessons/phase-8-planning-agent.md`

## Phase 9 — Single Research Agent Workflow

- 상태: 진행 중
- 현재 Lesson: Lesson 9.1 — Research Request Schema
- 상세 문서: `docs/lessons/phase-9-research-agent.md`

- [~] Research Request Schema
- [ ] Research Task와 Task Graph Schema
- [ ] Research Request Validator
- [ ] Research Task Decomposer
- [ ] Search Query Schema
- [ ] Search Query Planner
- [ ] Source Candidate Schema
- [ ] Source Search Tool Contract
- [ ] In-Memory Source Search Adapter
- [ ] Source Document Schema
- [ ] Source Reader Contract와 In-Memory Reader
- [ ] Evidence Schema
- [ ] Evidence Extractor Contract
- [ ] Source Quality Evaluation
- [ ] Claim과 Citation Schema
- [ ] Research Workspace
- [ ] Research Synthesizer
- [ ] Research Quality Evaluator
- [ ] Single Research Agent Pipeline 및 통합 E2E
- [ ] Phase 9 문서화와 Baseline Report

### Phase 9 완료 기준

- [ ] Research Request가 엄격하게 검증된다.
- [ ] 연구 요청이 실행 가능한 Research Task로 분해된다.
- [ ] Search Query를 계획할 수 있다.
- [ ] Source Search와 Source Reading이 Port로 분리된다.
- [ ] Evidence를 추출하고 Source에 연결할 수 있다.
- [ ] Source 품질을 평가할 수 있다.
- [ ] Claim과 Citation을 검증할 수 있다.
- [ ] Research Workspace가 전체 상태를 추적한다.
- [ ] 근거 기반 최종 보고서를 생성할 수 있다.
- [ ] Research 품질 평가를 수행할 수 있다.
- [ ] Single-Agent 통합 E2E 테스트가 통과한다.
- [ ] Phase 10 비교용 Baseline Metrics가 생성된다.
- [ ] 전체 pytest와 Ruff가 통과한다.

## Phase 10 — Multi-Agent Research System

- 상태: 시작 전
- 필수 Phase: 예

- [ ] Single-Agent와 Multi-Agent 선택 기준
- [ ] Agent Identity와 Role Schema
- [ ] Agent Capability와 Tool Permission
- [ ] Agent Registry
- [ ] Agent Task Assignment
- [ ] Agent Message Schema
- [ ] Agent Mailbox
- [ ] Shared Research Workspace
- [ ] Delegation Service
- [ ] Worker Agent Contract
- [ ] Research Manager Agent
- [ ] Search Agent
- [ ] Source Reader Agent
- [ ] Evidence Analyst Agent
- [ ] Citation Verifier Agent
- [ ] Critic Agent
- [ ] Report Writer Agent
- [ ] Sequential Multi-Agent Pipeline
- [ ] Parallel Specialist 실행
- [ ] Conflict Detection과 Revision
- [ ] Multi-Agent Stop Condition
- [ ] 비용과 지연 통제
- [ ] Multi-Agent Trace
- [ ] Single-Agent와 Multi-Agent 비교 Evaluation
- [ ] Multi-Agent 통합 E2E
- [ ] Phase 10 문서화

## Phase 11 — Evals, Guardrails, Reliability

- 상태: 시작 전

### Evals

- [ ] Golden Research Dataset
- [ ] Deterministic Eval
- [ ] LLM-as-judge
- [ ] Human Evaluation
- [ ] Citation Accuracy
- [ ] Evidence Coverage
- [ ] Source Quality
- [ ] Hallucination Evaluation
- [ ] Trace Evaluation
- [ ] Single-Agent와 Multi-Agent 비교
- [ ] 비용과 지연 측정
- [ ] Regression Test

### Guardrails

- [ ] Prompt Injection
- [ ] Indirect Prompt Injection
- [ ] 악성 Source 처리
- [ ] Tool Misuse
- [ ] Data Exfiltration
- [ ] Excessive Agency
- [ ] Least Privilege
- [ ] Agent별 Tool Permission
- [ ] 무한 Delegation 방지
- [ ] 무한 Debate 방지
- [ ] Approval Gate
- [ ] Kill Switch
- [ ] Threat Model
- [ ] Phase 11 평가

## Phase 12 — Application, Persistence, Background Jobs

- 상태: 시작 전

- [ ] CLI Interface
- [ ] FastAPI
- [ ] Research Job API
- [ ] Research 진행 상태 API
- [ ] Result와 Citation API
- [ ] SQLite 또는 PostgreSQL
- [ ] Research Repository
- [ ] Source Repository
- [ ] Evidence Repository
- [ ] Citation Repository
- [ ] Agent State Repository
- [ ] Background Worker
- [ ] Retry와 Timeout
- [ ] Cancellation
- [ ] Checkpoint와 Resume
- [ ] 인증과 권한 기초
- [ ] Phase 12 평가

## Phase 13 — Deployment, Operations, Final AIRA

- 상태: 시작 전

### 배포와 운영

- [ ] Dockerfile
- [ ] Docker Compose
- [ ] PostgreSQL
- [ ] Redis와 Worker
- [ ] Nginx
- [ ] HTTPS
- [ ] 개발·테스트·운영 환경
- [ ] CI/CD
- [ ] Structured Logging
- [ ] Metrics와 Tracing
- [ ] Backup과 Restore
- [ ] Rollback
- [ ] Cost Monitoring
- [ ] OCI 배포
- [ ] 운영 Runbook

### 최종 AIRA 통합

- [ ] 전체 요구사항 확정
- [ ] 전체 아키텍처 문서
- [ ] Single Research Agent
- [ ] Multi-Agent Research Team
- [ ] RAG 지식베이스
- [ ] Memory와 State
- [ ] Planning Agent
- [ ] Eval Dataset 실행
- [ ] Guardrail 검증
- [ ] Human Approval
- [ ] CLI 또는 Web UI
- [ ] 스테이징 배포
- [ ] 운영 배포
- [ ] 장애 복구 실험
- [ ] Single-Agent와 Multi-Agent 최종 비교
- [ ] 사용자 가이드
- [ ] 개발자 가이드
- [ ] 최종 발표와 평가
