#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

cat > MASTER.md <<'EOF'
# Agentic AI Lab — MASTER

## 1. 프로젝트 정의

### 프로젝트명

Agentic AI Lab

### 최종 제품명

AIRA — Agentic Intelligence Research Assistant

### 목적

Agentic AI의 최신 이론, 개발 기법, 시스템 구축, 평가, 보안,
배포 및 운영 방법을 초보자 수준부터 체계적으로 학습한다.

학습은 단순한 개념 설명에 그치지 않는다. 실제 Agentic AI 시스템을
직접 설계하고 구현하고 테스트하고 평가하고 배포한다.

최종적으로 연구, 설계, 개발, 평가 및 보고서 작성을 지원하는
AIRA 시스템을 구축한다.

## 2. 최종 시스템 기능

AIRA는 다음 기능을 갖는다.

1. 사용자 목표와 요구사항 분석
2. 복합 작업의 단계별 계획 수립
3. 웹과 프로젝트 문서 검색
4. 적절한 도구 선택 및 실행
5. 구조화된 결과 생성
6. 작업 상태 저장과 중단 후 재개
7. RAG 기반 근거 있는 답변
8. 단일 에이전트와 다중 에이전트 협업
9. 코드 작성, 테스트 및 리뷰
10. 결과 평가와 회귀 테스트
11. Human-in-the-loop 승인
12. 로그, 추적, 비용 및 보안 관리
13. Docker 기반 배포와 운영

## 3. 학습 범위

### ChatGPT 활용

- Chat
- Work
- Projects
- Apps
- Plugins
- Skills
- 파일 및 프로젝트 지식 관리

### Agentic AI 핵심

- LLM과 생성형 AI
- Workflow와 Agent
- Agent Loop
- Tool Calling
- Structured Outputs
- Planning
- State
- Memory
- RAG
- Handoff
- Single Agent
- Multi-Agent
- MCP
- Guardrails
- Human-in-the-loop
- Evals
- Tracing
- Production deployment

### 개발 기술

- Python
- OpenAI API
- Responses API
- Agents SDK
- FastAPI
- PostgreSQL
- Redis
- Docker
- Nginx
- Git과 GitHub
- Codex
- AGENTS.md

## 4. ChatGPT의 역할

### 교수

- 개념을 초보자 수준으로 설명한다.
- 전문용어를 처음 사용할 때 정의한다.
- 쉬운 비유와 실제 사례를 제공한다.
- 사용자의 이해도를 평가한다.

### 시스템 설계자

- 요구사항을 시스템 구조로 변환한다.
- 기술 대안을 비교한다.
- 선택 이유와 단점을 설명한다.
- 최소 구조에서 시작하고 필요할 때 확장한다.

### Codex 감독

- Codex 작업 범위를 명확히 정의한다.
- 금지사항과 완료 조건을 지정한다.
- Diff와 테스트 결과를 검토한다.
- 사용자가 결과를 이해하도록 설명한다.

### 평가자

- 이론 이해도와 구현 결과를 평가한다.
- 자동 테스트와 수동 검증을 적용한다.
- 단계별 통과 기준을 적용한다.
- 부족한 부분을 보충한 후 다음 단계로 진행한다.

## 5. 사용자의 역할

사용자는 직접 학습하고 판단하는 개발자 역할을 수행한다.

1. 핵심 개념을 자신의 말로 설명한다.
2. 명령어를 직접 실행한다.
3. 실행 결과와 오류를 확인한다.
4. 설계 결정에 참여한다.
5. Codex의 Diff를 검토한다.
6. 테스트를 직접 실행한다.
7. 평가 문제를 수행한다.
8. 학습 결과를 기록한다.
9. 이해하지 못한 내용을 그대로 넘기지 않는다.

## 6. 학습 진행 순서

1. 현재 단계 확인
2. 이론 설명
3. 쉬운 예제
4. 시스템 설계
5. 직접 실습
6. Codex 작업
7. 테스트
8. 실패 사례 분석
9. 이해도 평가
10. 학습 기록

## 7. 핵심 설계 원칙

### 작은 시스템부터 시작한다

일반 LLM 호출
→ 구조화 출력
→ 단일 도구
→ 여러 도구
→ 상태 관리
→ RAG
→ Planning
→ 평가
→ Multi-Agent
→ MCP
→ 운영 배포

### 확정 가능한 것은 코드로 처리한다

형식 검증, 숫자 계산, 상태 전이, 권한 확인, 중복 검사처럼
결정적인 작업은 코드로 처리한다.

의미 해석, 요약, 계획 및 분류처럼 불확실한 작업에 LLM을 사용한다.

### 중요한 작업은 인간이 승인한다

다음 작업은 기본적으로 사용자 승인 후 수행한다.

- 외부 이메일 발송
- 데이터 삭제
- GitHub Push
- 운영 서버 배포
- 운영 데이터베이스 변경
- 비용 증가 작업
- 개인정보 외부 전송
- 보안 설정 변경

### 결과보다 과정을 이해한다

Codex나 ChatGPT가 코드를 작성하더라도 사용자는 구조, 입력, 출력,
실패 지점, 테스트 및 대안을 이해해야 한다.

## 8. 기준 문서 우선순위

1. MASTER.md
2. DECISIONS.md
3. ROADMAP.md
4. CURRICULUM.md
5. AGENTS.md
6. README.md
7. LEARNING_LOG.md

## 9. 변경관리

- 핵심 목표를 임의로 변경하지 않는다.
- 로드맵 변경 시 이유와 영향을 기록한다.
- 최신 기술은 공식 자료를 확인한 뒤 반영한다.
- 확정된 결정 변경 시 DECISIONS.md에 이력을 남긴다.
- 핵심 개념을 이해하지 못한 채 다음 단계로 넘어가지 않는다.

## 10. 완료 조건

사용자가 다음을 직접 설명하고 구현할 수 있어야 한다.

- Workflow와 Agent의 차이
- Tool Calling
- RAG, Memory 및 State의 차이
- Single Agent와 Multi-Agent 선택
- 평가 데이터셋과 회귀 테스트
- Guardrail과 승인 절차
- Codex 감독과 Diff 검토
- Docker 배포
- 로그와 장애 대응
- 백업과 롤백
- 비용과 보안 위험
EOF

cat > ROADMAP.md <<'EOF'
# Agentic AI Lab — ROADMAP

## 진행상태

- `[ ]` 시작 전
- `[~]` 진행 중
- `[x]` 완료
- `[!]` 보충 필요
- `[-]` 보류

## 현재 위치

- 현재 Phase: Phase 0
- 현재 Lesson: 기준 문서 작성
- 현재 상태: 진행 중
- 다음 단계: 문서 검증과 첫 Commit

## Phase 0 — 프로젝트 기반

- [x] ChatGPT Project 생성
- [x] Work와 Plugins 확인
- [x] Ubuntu 개발환경 확인
- [x] 저장공간 확인
- [x] 프로젝트 경로 확정
- [x] Git 저장소 초기화
- [x] GitHub 원격 연결
- [x] Python 가상환경 생성
- [~] 기준 문서 작성
- [ ] 문서 검증
- [ ] 첫 Commit과 Push
- [ ] Codex CLI 설치
- [ ] Codex 읽기 전용 분석
- [ ] Phase 0 평가

## Phase 1 — Agentic AI 기초

- [ ] 생성형 AI와 LLM
- [ ] Chatbot, Workflow 및 Agent
- [ ] Goal, Environment, State, Action, Observation
- [ ] Agent Loop
- [ ] Deterministic과 Probabilistic 처리
- [ ] 자율성 단계
- [ ] Agent가 필요하지 않은 문제
- [ ] 비교 실험
- [ ] 평가

## Phase 2 — OpenAI API 기초

- [ ] API와 SDK
- [ ] API Key와 환경변수
- [ ] HTTP Request와 Response
- [ ] OpenAI Python SDK
- [ ] Responses API 첫 호출
- [ ] Token과 Context
- [ ] 오류 처리
- [ ] 사용량과 비용
- [ ] 평가

## Phase 3 — Structured Outputs와 Tool Calling

- [ ] JSON과 JSON Schema
- [ ] Pydantic
- [ ] Structured Outputs
- [ ] Function Calling
- [ ] Tool Definition
- [ ] Tool Execution Loop
- [ ] Validation
- [ ] Timeout과 Retry
- [ ] 최소 Tool-using Agent
- [ ] 평가

## Phase 4 — RAG와 검색

- [ ] RAG
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

## Phase 5 — Memory와 State

- [ ] Conversation History
- [ ] Working Memory
- [ ] Long-term Memory
- [ ] Project State
- [ ] Checkpoint와 Resume
- [ ] State Machine
- [ ] Memory Policy
- [ ] PostgreSQL
- [ ] 평가

## Phase 6 — Planning과 장기 작업

- [ ] Task Decomposition
- [ ] ReAct
- [ ] Plan-and-execute
- [ ] Reflection과 Critic
- [ ] Retry와 Replanning
- [ ] Stop Condition
- [ ] Budget Limit
- [ ] Task State Machine
- [ ] 평가

## Phase 7 — Codex와 Harness Engineering

- [ ] Codex CLI
- [ ] Codex 앱 또는 IDE
- [ ] AGENTS.md
- [ ] 작업지시 작성
- [ ] Diff 검토
- [ ] 테스트 기반 완료조건
- [ ] Git Worktree
- [ ] 병렬 작업
- [ ] Harness Engineering
- [ ] 평가

## Phase 8 — Agents SDK와 Multi-Agent

- [ ] Agents SDK
- [ ] Agent와 Runner
- [ ] Tool
- [ ] Handoff
- [ ] Agent as Tool
- [ ] Manager Pattern
- [ ] Reviewer Pattern
- [ ] Context Isolation
- [ ] Shared State
- [ ] Single과 Multi-Agent 비교
- [ ] 평가

## Phase 9 — MCP

- [ ] MCP 개념
- [ ] MCP Client
- [ ] MCP Server
- [ ] Tool과 Resource
- [ ] Tool Discovery
- [ ] Schema
- [ ] 인증과 권한
- [ ] 감사 로그
- [ ] 프로젝트 MCP Server
- [ ] Codex 연결
- [ ] 평가

## Phase 10 — Agent Evals

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

## Phase 11 — Guardrails와 보안

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

## Phase 12 — 배포와 운영

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

## Phase 13 — 최종 AIRA

- [ ] 요구사항 확정
- [ ] 전체 아키텍처
- [ ] Research Agent
- [ ] Architecture Agent
- [ ] Coding Agent
- [ ] Evaluation Agent
- [ ] Reviewer Agent
- [ ] Human Approval
- [ ] Web UI
- [ ] 평가 데이터 실행
- [ ] 보안 검토
- [ ] 스테이징 배포
- [ ] 운영 배포
- [ ] 장애 복구 실험
- [ ] 최종 발표와 평가
EOF

cat > CURRICULUM.md <<'EOF'
# Agentic AI Lab — CURRICULUM

## 교육 방식

각 수업은 다음 구조로 진행한다.

1. 현재 위치와 학습 목표
2. 초보자용 이론 설명
3. 쉬운 비유
4. 실제 개발 사례
5. 시스템 설계
6. 직접 실습
7. Codex 작업
8. 테스트
9. 실패 사례 분석
10. 평가와 학습 기록

## 평가 방식

각 Phase는 다음 네 영역으로 평가한다.

- 개념 이해
- 설계 판단
- 구현 능력
- 결과 검증

핵심 개념을 설명하지 못하거나 테스트 결과를 해석하지 못하면
보충 학습 후 다시 평가한다.

## 최종 결과

- AIRA Agentic Research Assistant
- 프로젝트 문서
- Agent 코드
- Tool 모듈
- RAG 지식베이스
- Memory와 State 저장
- Multi-Agent 구조
- MCP Server
- Eval 데이터셋
- Guardrail
- Docker 배포환경
- 운영 Runbook
EOF

cat > DECISIONS.md <<'EOF'
# Agentic AI Lab — DECISIONS

## D-001 — 기본 운영체제

- 상태: 확정
- 날짜: 2026-07-23
- 결정: Ubuntu를 기본 개발환경으로 사용한다.

## D-002 — 프로젝트 경로

- 상태: 확정
- 날짜: 2026-07-23
- 경로: `/home/moon/Project/agentic-ai-lab`
- 이유: Linux 권한, Python 가상환경 및 Docker 호환성을 확보한다.

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

- 상태: 잠정 확정
- 날짜: 2026-07-23
- 언어: Python
- API Framework: FastAPI
- 데이터 검증: Pydantic
- 재검토: Phase 2 시작 전

## D-007 — 에이전트 개발 순서

- 상태: 확정
- 날짜: 2026-07-23
- 결정: Single Agent로 시작하고 실제 필요가 확인된 후 Multi-Agent로 확장한다.

## D-008 — 데이터 저장

- 상태: 확정
- 날짜: 2026-07-23
- 소스와 문서: Git 프로젝트
- PostgreSQL과 Redis: Docker named volume
- Secret: Git에서 제외된 환경변수 또는 Secret 저장소
- 대형 데이터셋과 로컬 모델: 필요하면 대용량 디스크로 분리

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
EOF

cat > LEARNING_LOG.md <<'EOF'
# Agentic AI Lab — LEARNING LOG

## 학습자

- 사용자: moon
- GitHub: simbizmoon
- 시작일: 2026-07-23
- 시작 수준: Agentic AI 초보자
- 운영체제: Ubuntu

## Session 001 — 프로젝트 기반

### 완료한 작업

- ChatGPT Project 생성
- Work 메뉴 확인
- Plugins 메뉴 확인
- Ubuntu 개발환경 확인
- SSD 저장공간 확인
- 프로젝트 경로 확정
- Git 저장소 초기화
- GitHub 원격 연결
- Python 가상환경 생성
- 초기 폴더 구조 생성

### 개발환경

- Git: 2.43.0
- Python: 3.12.3
- Node.js: 24.12.0
- npm: 11.6.2
- Docker: 29.3.0

### 프로젝트 위치

`/home/moon/Project/agentic-ai-lab`

### 이번 세션의 핵심 개념

1. ChatGPT Project는 대화, 파일 및 지침의 작업 공간이다.
2. Git 저장소는 코드와 문서의 변경 이력을 관리한다.
3. GitHub는 원격 저장소와 협업 공간이다.
4. Python 가상환경은 프로젝트 의존성을 격리한다.
5. `.gitignore`는 Secret과 생성 파일을 Git에서 제외한다.
6. 프로젝트 코드와 데이터베이스 데이터는 저장 방식을 분리할 수 있다.
7. Docker 이미지와 캐시는 많은 저장공간을 차지할 수 있다.

### 자기평가

작성 예정

### 질문

작성 예정
EOF

cat > AGENTS.md <<'EOF'
# AGENTS.md

## Mission

Build AIRA, a reliable Agentic AI research and development assistant,
while teaching the learner every major concept and implementation decision.

## Project Root

`/home/moon/Project/agentic-ai-lab`

## Current Stage

Phase 0. Do not implement application features until the project foundation
and learning documents have been reviewed and committed.

## Required Behavior

- Read MASTER.md before proposing changes.
- Read DECISIONS.md before choosing technologies.
- Check ROADMAP.md to determine the current phase.
- Explain changes in beginner-friendly language.
- Prefer minimal and reversible changes.
- Do not add unrelated features.
- Do not perform broad refactoring without an explicit request.
- Do not expose or commit secrets.
- Add tests for behavioral changes.
- Report modified files and executed tests.

## Approval Required

Do not perform the following without explicit user approval:

- Git push
- Production deployment
- Data deletion
- Database migration on production
- External email sending
- Security configuration changes
- Actions that materially increase cost

## Coding Standards

- Python 3.12
- Type hints for public functions
- Pydantic for structured validation where appropriate
- Clear error handling
- Small functions with explicit responsibilities
- Tests for important behavior
- English identifiers
- Korean explanatory documentation when it improves learning

## Completion Report

Every coding task must report:

1. Goal
2. Files changed
3. Design decisions
4. Commands executed
5. Tests executed
6. Results
7. Known limitations
8. Recommended next step
EOF

cat > README.md <<'EOF'
# Agentic AI Lab

Agentic AI의 최신 이론, 개발, 평가, 보안, 배포 및 운영을
프로젝트 기반으로 학습하는 저장소입니다.

최종 목표는 연구·설계·개발·평가를 지원하는
AIRA Agentic Intelligence Research Assistant를 구축하는 것입니다.

## Environment

- Ubuntu
- Python 3.12
- Git
- Docker
- OpenAI API
- Codex

## Project Location

```text
/home/moon/Project/agentic-ai-lab
```

## Activate Python Environment

```bash
cd ~/Project/agentic-ai-lab
source .venv/bin/activate
```

## Core Documents

- `MASTER.md`: 최상위 목표와 원칙
- `ROADMAP.md`: 전체 과정과 현재 진행상태
- `CURRICULUM.md`: 교육 방식과 학습 범위
- `DECISIONS.md`: 확정된 기술 및 운영 결정
- `LEARNING_LOG.md`: 실제 학습 기록
- `AGENTS.md`: Codex와 코딩 에이전트의 작업 규칙

## Current Status

Phase 0 — 프로젝트 기반 구성

EOF

echo "Project documents created successfully."
