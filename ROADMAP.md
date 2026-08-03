# Agentic AI Lab — ROADMAP

## 진행상태

- `[ ]` 시작 전
- `[~]` 진행 중
- `[x]` 완료
- `[!]` 보충 필요
- `[-]` 보류

## 현재 위치

- 현재 Phase: Phase 4 — Tool Calling
- 현재 Lesson: Lesson 4.1 — 단일 Tool 정의와 호출
- 현재 상태: 시작 준비 완료
- 다음 단계: 허용된 로컬 Tool 하나를 모델이 선택하고 실행하는 최소 흐름 구현
- 운영 원칙: 복잡한 Agent Loop나 여러 Tool로 확장하지 않고 단일 Tool부터 시작한다.

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

- 상태: 시작 전

- [ ] RAG 개념과 필요성
- [ ] 문서 파싱
- [ ] Chunking
- [ ] Embedding
- [ ] Vector Search
- [ ] Keyword Search
- [ ] Hybrid Search
- [ ] Metadata Filtering
- [ ] Reranking
- [ ] Citation Grounding
- [ ] Retrieval Eval
- [ ] Phase 6 평가

## Phase 7 — Memory

- 상태: 시작 전

- [ ] Conversation History
- [ ] Working Memory
- [ ] Long-term Memory
- [ ] 사용자 Memory와 프로젝트 Memory
- [ ] Memory 저장 기준
- [ ] Memory 검색과 주입
- [ ] Memory 갱신과 삭제
- [ ] Memory Policy
- [ ] PostgreSQL 기반 저장
- [ ] 개인정보와 보안
- [ ] Phase 7 평가

## Phase 8 — Planning Agent

- 상태: 시작 전

- [ ] Task Decomposition
- [ ] ReAct
- [ ] Plan-and-execute
- [ ] Reflection과 Critic
- [ ] Retry와 Replanning
- [ ] 객관적 완료 조건
- [ ] Stop Condition
- [ ] Token과 비용 Budget
- [ ] 장기 작업 State
- [ ] Human Approval
- [ ] Phase 8 평가

## Phase 9 — Evals와 Guardrails

- 상태: 시작 전

### Evals

- [ ] Unit Test
- [ ] Integration Test
- [ ] End-to-end Test
- [ ] Golden Dataset
- [ ] Deterministic Eval
- [ ] LLM-as-judge
- [ ] Human Evaluation
- [ ] Trace Evaluation
- [ ] Regression Test
- [ ] 비용과 지연 측정

### Guardrails

- [ ] Prompt Injection
- [ ] Indirect Prompt Injection
- [ ] Tool Misuse
- [ ] Data Exfiltration
- [ ] Excessive Agency
- [ ] Least Privilege
- [ ] Sandboxing
- [ ] Secret Management
- [ ] Approval Gate
- [ ] Kill Switch
- [ ] Threat Model
- [ ] Phase 9 평가

## Phase 10 — Multi-Agent

- 상태: 시작 전

- [ ] Single Agent와 Multi-Agent 선택 기준
- [ ] 역할 분리 기준
- [ ] Researcher
- [ ] Analyst
- [ ] Writer
- [ ] Reviewer
- [ ] Coordinator와 Manager Pattern
- [ ] Handoff
- [ ] Agent as Tool
- [ ] Agent 간 Structured Output
- [ ] Context Isolation
- [ ] Shared State
- [ ] 중복 작업 방지
- [ ] 비용과 지연 통제
- [ ] Single Agent와 Multi-Agent 비교 평가
- [ ] Phase 10 평가

## Phase 11 — MCP·Plugins·Skills·Codex 통합

- 상태: 시작 전

### MCP

- [ ] MCP 개념
- [ ] MCP Client
- [ ] MCP Server
- [ ] Tool과 Resource
- [ ] Tool Discovery
- [ ] Schema
- [ ] 인증과 권한
- [ ] 감사 로그
- [ ] 프로젝트 MCP Server

### ChatGPT와 Codex 통합

- [ ] ChatGPT Projects와 Work 활용
- [ ] Plugins와 Skills
- [ ] Codex CLI
- [ ] AGENTS.md
- [ ] Codex 작업지시 작성
- [ ] Diff 검토
- [ ] 테스트 기반 완료 조건
- [ ] Git Worktree
- [ ] Harness Engineering
- [ ] Phase 11 평가

## Phase 12 — 배포와 운영 및 최종 AIRA

- 상태: 시작 전

### 배포와 운영

- [ ] FastAPI
- [ ] Dockerfile
- [ ] Docker Compose
- [ ] PostgreSQL
- [ ] Redis와 Worker
- [ ] Nginx
- [ ] HTTPS
- [ ] 개발·테스트·운영 환경
- [ ] CI/CD
- [ ] Logging
- [ ] Metrics와 Tracing
- [ ] Backup과 Restore
- [ ] Rollback
- [ ] Cost Monitoring

### 최종 AIRA 통합

- [ ] 요구사항 확정
- [ ] 전체 아키텍처
- [ ] Research 기능
- [ ] 문서 분석 기능
- [ ] RAG 지식베이스
- [ ] Memory와 State
- [ ] Planning Agent
- [ ] Multi-Agent 확장
- [ ] Eval 데이터셋 실행
- [ ] Guardrail 검증
- [ ] Human Approval
- [ ] Web UI
- [ ] 스테이징 배포
- [ ] 운영 배포
- [ ] 장애 복구 실험
- [ ] 최종 발표와 평가
