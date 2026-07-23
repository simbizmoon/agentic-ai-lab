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
