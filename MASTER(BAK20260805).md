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
