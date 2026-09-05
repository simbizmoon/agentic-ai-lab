# Agentic AI Lab

Agentic AI를 프로젝트 기반으로 학습하고,
실제로 사용할 수 있는 연구 지원 도구 AIRA를 만드는 저장소입니다.

최종 목표는 기능 수가 많은 플랫폼이 아니라,
Source와 Evidence를 확인하고 Citation이 연결된 보고서를 생성하는
작고 신뢰할 수 있는 AIRA MVP입니다.

## Environment

- Ubuntu
- Python 3.12
- Git
- OpenAI API
- Pydantic
- pytest
- Ruff
- Codex
- Docker

선택적으로 FastAPI와 SQLite를 사용합니다.

## Project Location

```text
/home/moon/Project/agentic-ai-lab
```

## Activate Python Environment

```bash
cd ~/Project/agentic-ai-lab
source .venv/bin/activate
```

## Quality Baseline

Latest documented real-development baseline (Stage 9 Step 5, 2026-08-30):

```text
development cases: 4 completed and persisted
provider requests: 16
external requests: 19
recorded tokens: 17,894
estimated cost: USD 0.214728
human review: ACCEPT 1 / NEEDS_REVISION 3 / REJECT 0
blind holdout cases executed: 0
```

Documentation reconciliation verification (2026-09-05):

```text
full repository pytest: 6550 passed
Ruff: PASS
git diff --check: PASS
external/provider requests: 0
```

실행 완료는 품질 승인을 뜻하지 않는다. 현재 세 사례가 수정 필요 판정이며 blind holdout은
development 결과의 remediation과 closeout 결정 전까지 실행하지 않는다.

## Core Documents

- `AIRA_PROJECT_CHARTER.md`: 최종 제품 목표와 Stage 0~11 상위 제품 구조
- `MASTER.md`: 프로젝트 운영·개발·검증 원칙과 문서 권한
- `ROADMAP.md`: **현재 제품 위치와 다음 실행 순서의 authoritative source**
- `DECISIONS.md`: 확정된 기술·제품·운영 결정
- `AIRA_CURRENT_SYSTEM_GUIDE.md`: 현재 실제 사용자/runtime 기능
- `RUNTIME_ARCHITECTURE.md`: 현재 runtime architecture
- `AIRA_LLM_AND_AGENT_USER_MANUAL.md`: 실제 운영·사용 방법
- `AIRA_CAPABILITY_MATRIX.md`: 구현·평가 capability snapshot
- `CURRICULUM.md`: 교육 방식과 학습 범위
- `AGENTS.md`: Codex와 코딩 에이전트 작업 규칙
- `LEARNING_LOG.md`: 실제 학습·구현·실패 분석 기록

과거 `Phase 0~13` 및 `Stage A~I` 표현은 historical checkpoint이며 현재 제품 Stage를
대체하지 않는다.

## Current Status

```text
Stage 8 — Essential Cost Control
→ COMPLETE

Stage 9 — Mandatory Real Research Evaluation
→ IN PROGRESS

Step 5 — Bounded Single-Agent Development Baseline Execution
→ RUN AND HUMAN REVIEW COMPLETE / QUALITY REVISION REQUIRED
```

현재 development 4건은 모두 실행·저장됐지만 인간 검토에서 1건만 바로 승인됐다.
Blind holdout 6건은 아직 실행하지 않았다.

다음 공식 작업:

```text
Stage 9 — Mandatory Real Research Evaluation
Step 5 — Development baseline remediation and closeout decision
```

## AIRA MVP

기본 흐름:

```text
연구 질문 또는 문서
→ Source 검색과 읽기
→ Evidence 추출
→ Claim과 Citation 연결
→ 근거 기반 보고서
→ Eval과 Guardrail
→ 결과 저장
```

필수 결과:

- CLI 연구 실행
- Single Research Agent 기본 경로
- Source, Evidence, Claim, Citation 추적
- 보고서 생성
- 실행 및 결과 저장
- 실제 사례 3개
- Docker 실행환경
- 사용자 가이드

선택 결과:

- 최소 FastAPI
- SQLite
- 제한된 Multi-Agent 비교

## Scope Boundary

현재 완료 조건에 포함하지 않습니다.

- Redis 또는 RabbitMQ
- 분산 Worker
- Kubernetes
- 복잡한 인증과 RBAC
- 대규모 Observability
- 상용 Web UI
- 운영용 Multi-Server Architecture

이 항목들은 실제 필요가 확인된 경우에만 별도 Backlog에서 검토합니다.

## Main Lesson Documents

- `docs/lessons/phase-6-rag.md`
- `docs/lessons/phase-7-memory.md`
- `docs/lessons/phase-8-planning-agent.md`
- `docs/lessons/phase-9-research-agent.md`
- `docs/lessons/phase12-application-persistence-jobs.md`
