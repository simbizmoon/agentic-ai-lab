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

```text
pytest: 4048 passed
ruff: All checks passed
```

## Core Documents

- `MASTER.md`: 최상위 목표, MVP 범위와 범위 통제
- `DECISIONS.md`: 확정된 기술 및 운영 결정
- `ROADMAP.md`: 현재 위치와 최종 Phase 13 계획
- `CURRICULUM.md`: 교육 방식과 학습 범위
- `AGENTS.md`: Codex와 코딩 에이전트 작업 규칙
- `LEARNING_LOG.md`: 실제 학습 및 구현 기록

## Current Status

- Phase 0–12: COMPLETE
- Current Phase: Phase 13 — Practical AIRA Integration and Delivery
- Phase 13: 최종 Phase
- 다음 작업: AIRA MVP 사용 시나리오와 통합 경로 확정

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
