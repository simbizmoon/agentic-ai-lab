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

- 상태: 확정
- 날짜: 2026-07-23
- 확정일: 2026-08-03
- 언어: Python
- API Framework: FastAPI
- 데이터 검증: Pydantic
- 결정: Phase 2와 Phase 3 실습 결과 현재 구성을 유지한다.

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

## D-010 — 전체 학습 Phase 구조

- 상태: 확정
- 날짜: 2026-08-03
- 결정:
  - Phase 3: Structured Outputs와 데이터 검증
  - Phase 4: Tool Calling
  - Phase 5: Workflow와 상태 관리
  - Phase 6: RAG
  - Phase 7: Memory
  - Phase 8: Planning Agent
  - Phase 9: Evals와 Guardrails
  - Phase 10: Multi-Agent
  - Phase 11: MCP·Plugins·Skills·Codex 통합
  - Phase 12: 배포와 운영 및 최종 AIRA
- 이유: 단일 모델 호출에서 시작하여 Tool, Workflow, 검색,
  Memory, Planning 및 Multi-Agent 순으로 복잡도를 단계적으로 높인다.

## D-011 — Phase 3 보안 심화 기능 동결

- 상태: 확정
- 날짜: 2026-08-03
- 결정: Phase 3에서 구현한 Transparency Log, Merkle Proof,
  Witness Quorum, Signed Gossip Bundle 및 Trust Decision Receipt는
  심화 실습 완료 상태로 동결한다.
- 이유: 해당 하위 시스템을 더 확장하지 않고 AIRA의 핵심 기능인
  Tool Calling, Workflow, RAG, Memory 및 Planning 학습으로 이동한다.
- 재개 조건: 실제 AIRA 운영 요구 또는 구체적인 보안 위협 모델이
  확인된 경우에만 별도 결정 후 확장한다.
