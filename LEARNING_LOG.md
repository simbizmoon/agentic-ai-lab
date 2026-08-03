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
- 기준 문서 생성 및 검증
- 첫 Commit과 GitHub Push
- Codex CLI 버전 0.145.0 확인
- Codex 읽기 전용 저장소 분석 수행
- Codex 읽기 전용 분석 중 파일 생성, 수정, 삭제를 수행하지 않음

### 개발환경

- Git: 2.43.0
- Python: 3.12.3
- Node.js: 24.12.0
- npm: 11.6.2
- Docker: 29.3.0
- Codex CLI: 0.145.0

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
8. Phase 문서는 실제 진행상태와 계속 일치해야 한다.
9. Codex 작업은 허용된 권한 경계를 지켜야 한다.

### Codex 읽기 전용 분석 결과

Codex는 다음 세 가지 문서 정합성 문제를 발견했다.

1. `ROADMAP.md` 상단의 현재 위치는 "문서 검증과 첫 Commit"을 다음 단계로 표시했지만, Phase 0 체크리스트에서는 이미 완료로 표시되어 있었다.
2. `LEARNING_LOG.md`에는 기준 문서 검증, 첫 Commit과 GitHub Push, Codex 읽기 전용 분석 기록이 아직 반영되지 않았다.
3. `AGENTS.md`의 애플리케이션 기능 구현 금지 조건은 "문서 검토와 커밋 전"으로만 표현되어, Phase 0 평가 완료 전까지 기능 구현을 보류해야 한다는 기준이 충분히 명확하지 않았다.

### Phase 0 최종 완료

Phase 0의 프로젝트 기반 구성과 평가를 완료했다.

완료한 핵심 내용은 다음과 같다.

- Git 저장소 초기화와 변경 이력 관리
- GitHub 원격 저장소 연결과 Push
- Python 가상환경 생성과 프로젝트 격리
- 기준 문서 작성, 검증 및 정합성 점검
- Codex CLI 설치 확인과 버전 0.145.0 확인
- Codex 읽기 전용 분석과 권한 경계 확인
- 허용된 파일만 대상으로 한 제한된 문서 수정 실습
- Git Diff 확인과 Commit 전 검증 흐름
- Human-in-the-loop 승인 원칙
- 최소 권한 원칙

Phase 0 이해도 평가 결과는 통과이다.

사용자는 다음 사례를 정확히 구분했다.

- 단순 설명 요청 → Chatbot
- 고정된 반복 절차 → Workflow
- 상황 판단과 반복 수행 → Agent

## Session 002 — Agentic AI 기초

### 완료한 Lesson

- Lesson 1.1 Chatbot, Workflow, Agent의 차이
- Lesson 1.2 Goal, Environment, State, Action, Observation
- Lesson 1.3 Agent Loop와 Deterministic/Probabilistic 처리
- Lesson 1.4 자율성 단계와 Agent가 필요하지 않은 문제
- Lesson 1.5 같은 문제의 Chatbot/Workflow/Agent 비교 설계
- Lesson 1.6 Agent 실패 유형과 안전장치
- Lesson 1.7 Phase 1 종합 Agent 설계

### 핵심 학습 내용

- Chatbot은 단순 설명과 질의응답에 적합하고, Workflow는 고정된 반복 절차에 적합하며, Agent는 상황 판단과 반복 수행이 필요한 문제에 적합하다.
- Agent 구성요소는 Goal, Environment, State, Action, Observation으로 나누어 볼 수 있다.
- Agent Loop는 관찰, 판단, 행동, 결과 확인을 반복하는 구조이다.
- Deterministic 처리는 규칙, 검증, 계산처럼 코드로 확정할 수 있는 영역에 사용하고, Probabilistic 처리는 해석, 요약, 분류처럼 불확실성이 있는 영역에 사용한다.
- 최소 자율성 원칙에 따라 필요한 만큼만 Agent에게 판단 권한을 준다.
- Human-in-the-loop는 삭제, 발송, 비용 증가, 보안 변경처럼 중요한 작업에 사람의 승인을 넣는 안전장치이다.
- Hallucination은 모델이 그럴듯하지만 틀린 내용을 생성하는 실패 유형이다.
- Prompt Injection은 외부 입력이나 문서가 모델의 지시 체계를 악용하려는 공격이다.
- 객관적 완료 조건은 작업이 끝났는지 주관이 아니라 검증 가능한 기준으로 판단하게 해 준다.
- 최소 권한은 Agent와 도구가 필요한 범위의 권한만 갖게 하는 보안 원칙이다.

### 잘 이해한 내용

- Chatbot, Workflow, Agent의 차이를 사례로 구분했다.
- Agent 구성요소와 Agent Loop를 연결해서 설명했다.
- Deterministic/Probabilistic 분리 기준을 설계 판단에 적용했다.
- 최소 자율성, Human-in-the-loop, 최소 권한을 안전장치로 설명했다.

### 보완한 내용

- Hallucination과 Prompt Injection을 단순 오류가 아니라 Agent 설계에서 통제해야 할 실패 유형으로 정리했다.
- 완료 조건을 "잘 작동한다"가 아니라 테스트 가능하고 관찰 가능한 기준으로 써야 함을 보완했다.
- Agent가 필요하지 않은 문제는 Workflow나 일반 코드로 해결하는 것이 더 안전할 수 있음을 정리했다.

### Phase 1 최종 평가

- 점수: 93점
- 결과: 통과
- 다음 단계: Phase 2에서 OpenAI API, SDK, HTTP Request와 Response를 학습한다.

### 자기평가

작성 예정

### 질문

작성 예정

## Session 003 — OpenAI API와 Structured Outputs

### Phase 2 완료

- OpenAI Python SDK와 Responses API 실제 호출
- API Key와 Secret의 환경변수 관리
- 설정 로더와 OpenAI Client 분리
- Response ID, Request ID 및 Token Usage 확인
- API 오류 분류와 종료 코드 처리

### Phase 3 완료 내용

- JSON Schema와 엄격한 Pydantic 모델
- Responses API Structured Outputs
- 모델 응답의 타입·필수 값·추가 필드 검증
- 불완전 응답, 거부, 파싱 및 Validation 오류 처리
- 제한된 교정 재시도와 실행 Budget
- 감사 로그, 무결성, 서명 및 공개키 검증 심화 실습
- Transparency Log, Merkle Proof, Witness Quorum
- Signed Gossip Bundle과 Offline Verification
- Trust Decision Receipt와 안전한 재사용 검증

보안·감사 하위 시스템은 고급 심화 실습으로 완료했으며,
AIRA 핵심 기능에 집중하기 위해 현재 상태로 동결한다.

### Lesson 3.35 — AIRA 문서 분석 Structured Output

추가한 구성:

- DocumentFinding과 DocumentAnalysis 스키마
- low, medium, high FindingSeverity
- OpenAI Structured Output 기반 analyze_document 서비스
- 로컬 UTF-8 문서 분석 CLI
- 스키마 테스트 7개와 서비스 테스트 9개

데이터 흐름:

로컬 문서 → Responses API → DocumentAnalysis → Pydantic 검증 → CLI 출력

실제 gpt-5 호출에서 문서 요약, 핵심 발견, 근거, 심각도,
권고 조치 및 인간 검토 필요 여부가 구조화되어 반환되었다.

### 검증 결과

- 전체 테스트: 1685개 통과
- Ruff: 통과
- Compileall: 통과
- Git diff 검사: 통과
- 실제 Responses API 호출: 성공
- 종료 코드: 0

### 핵심 학습 내용

1. Structured Output은 모델 출력에 명시적인 데이터 계약을 적용한다.
2. Pydantic은 형식과 의미 규칙을 결정적으로 검증한다.
3. LLM은 요약·발견·권고처럼 의미 해석이 필요한 작업을 담당한다.
4. 코드는 허용 값, 오류 처리와 완료 조건을 검증한다.
5. 문서에서 확인한 사실과 모델이 제안한 조치를 분리해야 한다.
6. 기존 기능을 재사용하고 불필요한 추상화를 피해야 한다.
7. Phase 3의 보안 기능은 유용했지만 원래 목표보다 과도하게 확장되었다.

### Phase 3 최종 평가

- 결과: 통과
- Structured Output와 일반 JSON 출력의 차이를 설명했다.
- LLM과 Pydantic의 역할을 구분했다.
- 오류 유형에 따라 재시도, 요청 수정 및 인간 검토를 구분했다.
- 고위험 권고에 Human-in-the-loop가 필요한 이유를 설명했다.

### 다음 단계

Phase 4 — Tool Calling으로 이동한다.

Lesson 4.1에서는 복잡한 Agent Loop를 만들지 않고,
허용된 로컬 Tool 하나를 정의하고 호출하는 최소 흐름부터 학습한다.

## Phase 4 — Tool Calling 완료

- 상태: 완료
- 구현:
  - Responses API 기반 Tool Calling
  - 문서 통계 Tool
  - 문서 키워드 추출 Tool
  - Tool Registry 및 Dispatcher
  - 허용 Tool 및 승인 정책
  - Pydantic 입력 검증
  - Tool 인수 오류 1회 교정
  - Observation과 Final Answer 분리
  - 단일 Tool 요청 정책
  - 구조화 Workflow 이벤트
  - 누적 경과시간 관측
- 실제 API 검증:
  - 통계 요청 → get_document_statistics
  - 키워드 요청 → extract_document_keywords
  - 복합 요청 → 요청 분리 안내
- 품질 확인:
  - 전체 pytest 통과
  - ruff check 통과
