# Agentic AI Lab — 첫 작업지시

본 프로젝트의 목표는 기존 교육과정을 계속 진행하는 것이 아니라, 실제로 유용하고 사용 가능한 AIRA(Agentic Intelligence Research Assistant)를 단계적으로 구축하는 것이다.

먼저 프로젝트에 등록된 다음 기준 문서를 충분히 읽고 서로의 관계를 이해하라.

1. `AIRA_PROJECT_CHARTER.md`
2. `DECISIONS.md`
3. `MASTER.md`
4. `ROADMAP.md`

`CURRICULUM.md`는 완료된 학습 이력이며 현재 제품 개발의 핵심 기준으로 사용하지 않는다.

---

## 1. 최종적으로 구축할 AIRA

사용자가 연구 주제를 입력하면 AIRA는 다음 전체 흐름을 수행해야 한다.

```text
연구 주제 입력
→ 연구 목적과 범위 이해
→ 조사계획과 검색어 생성
→ 인터넷 및 지정된 로컬 자료 검색
→ 관련 자료 수집
→ 자료별 관련성·중요도·신뢰도·최신성·증거 수준 평가
→ 자료별 요약과 Evidence 추출
→ 수집·평가 결과를 로컬 폴더에 구조적으로 저장
→ 저장된 복수 자료 정리·비교·분석
→ 공통점·차이점·충돌·위험요소·시사점 도출
→ 근거 기반 제안사항 생성
→ Claim, Evidence 및 Citation이 연결된 최종 보고서 저장
```

AIRA는 단순 검색기나 요약기가 아니라 사용자의 연구와 의사결정을 지원하는 분석·제안형 Research Agent여야 한다.

---

## 2. 핵심 개발 원칙

다음 원칙을 반드시 지킨다.

### 단계적 구현

전체 기능을 한꺼번에 구현하지 않는다.

각 기능은 다음 순서로 진행한다.

```text
기존 코드 감사
→ 재사용 여부 판단
→ 최소 통합 설계
→ 한 단계 구현
→ 테스트
→ 실제 연구 주제로 실행
→ 결과 검증
→ 문제 수정
→ 사용자 승인
→ 다음 단계
```

현재 단계를 검증하기 전에는 다음 단계로 넘어가지 않는다.

### 기존 코드 우선 재사용

로컬 저장소의 실제 경로는 다음과 같다.

```text
/home/moon/Project/agentic-ai-lab
```

새 코드를 작성하기 전에 기존 코드에서 다음 기능의 구현 여부를 확인해야 한다.

* OpenAI Responses API와 OpenAI SDK
* Structured Outputs
* Tool Calling과 Tool Loop
* Search 및 Source Reader
* Research Request와 Query Planning
* RAG, Chunking, Retrieval 및 Citation
* Evidence, Claim 및 Report
* Memory와 Agent State
* Planning 및 Replanning
* Usage, Token 및 비용 계산
* CLI와 결과 저장
* Evals, Guardrails 및 Tracing

기존 코드가 있으면 다음 네 상태를 구분한다.

* Implemented
* Tested
* Runtime-connected
* Production-ready

파일이나 클래스가 존재한다는 이유만으로 실제 사용 가능한 기능이라고 판단하지 않는다.

가능하면 기존 코드를 그대로 재사용하고, 직접 연결이 어려우면 Adapter를 우선 검토한다. 재작성은 최후의 선택이다.

### Single-Agent 우선

처음에는 LLM 기반 Single Research Agent를 구축한다.

Multi-Agent는 Single-Agent 대비 품질, 비용, 처리시간 또는 Context 관리가 실제 평가에서 개선된 경우에만 검토한다.

### 비용 관리

기존 Usage 및 비용 계산 코드를 반드시 감사한다.

비용은 실행 후 기록만 하는 것이 아니라 다음 실행 제한에 사용해야 한다.

* 최대 LLM 호출 수
* 최대 Search 호출 수
* 최대 Tool 호출 수
* 최대 Source 수
* 최대 Chunk 수
* 최대 Token
* 최대 반복 횟수
* 최대 실행시간
* 실행당 비용 상한

검색한 모든 문서 전체를 LLM에 전달하지 않는다. 중복 제거, Metadata 선별, Chunking 및 Retrieval을 통해 관련 Evidence만 전달한다.

### Provider 독립성

초기 구현에는 기존 OpenAI Responses API 또는 OpenAI SDK를 사용할 수 있다.

그러나 AIRA의 Domain Model, Tool, RAG, Evidence, Claim, Citation, Report 및 Agent State는 OpenAI 전용 객체에 직접 의존하지 않도록 한다.

향후 다른 상용 LLM API, OpenAI-compatible API, Ollama 및 로컬 LLM으로 교체할 수 있는 Provider 구조를 고려한다.

---

## 3. 단계별 구현 순서

### 구현 단계 1 — 검색·수집·로컬 저장

첫 기능 목표는 다음과 같다.

```text
연구 주제 입력
→ 최소 조사계획 생성
→ 하나의 검색 경로 사용
→ 제한된 수의 Source 검색
→ Source 원문 또는 핵심 내용 수집
→ Metadata와 함께 로컬 폴더에 저장
```

검증 항목:

* 연구 주제를 입력할 수 있는가
* 실제 검색이 수행되는가
* Source URL, 제목, 발행기관, 날짜 등 Metadata가 보존되는가
* 원문 또는 분석 가능한 내용이 저장되는가
* 실행별 독립된 로컬 폴더가 생성되는가
* 오류, Usage 및 비용이 기록되는가
* 동일 실행을 재현하거나 결과를 다시 읽을 수 있는가

### 구현 단계 2 — 자료별 평가와 요약

단계 1이 검증된 후 다음을 추가한다.

```text
저장된 Source
→ 관련성 평가
→ 중요도 평가
→ 신뢰도 평가
→ 최신성 평가
→ 핵심 요약
→ Evidence 추출
→ 평가 결과 저장
```

### 구현 단계 3 — 복수 자료 비교·분석

단계 2가 검증된 후 다음을 추가한다.

```text
평가된 복수 Source
→ 주제별 분류
→ 중복 통합
→ 공통점 비교
→ 차이점 비교
→ 충돌 탐지
→ 주요 발견과 시사점 생성
```

### 구현 단계 4 — 제안사항과 최종 보고서

단계 3이 검증된 후 다음을 추가한다.

```text
분석 결과
→ 위험요소
→ 근거 기반 제안사항
→ Confidence
→ Claim-Evidence-Citation 검증
→ 최종 Markdown 및 JSON 보고서
```

### 이후 고도화

기본 흐름이 검증된 뒤에만 다음을 검토한다.

* PDF 고도화
* HWP와 HWPX
* Hybrid RAG
* Embedding과 Reranking
* Evidence Sufficiency 기반 추가 검색
* 공식자료·학술자료·특허 전문 검색
* Cache
* 다른 상용 LLM
* Ollama 및 로컬 LLM
* Multi-Agent
* FastAPI, SQLite, MCP 또는 ChatGPT App

---

## 4. 이번 대화에서 수행할 첫 작업

이번 대화에서는 코드를 직접 구현하거나 전체 Architecture를 새로 작성하지 않는다.

가장 먼저 다음을 수행하라.

1. 등록된 기준 문서를 읽고 핵심 목표와 제약을 정리한다.
2. 문서 간 충돌이나 불명확한 사항이 있는지 확인한다.
3. 사용자가 원하는 첫 구현 단계를 다음과 같이 명확히 정의한다.

```text
연구 주제 입력
→ 검색
→ 자료 수집
→ 로컬 폴더 저장
```

4. 이 첫 구현에 필요한 기존 Capability를 목록화한다.
5. Codex가 감사해야 할 저장소 범위를 최소 단위로 정한다.
6. Codex용 첫 감사 작업지시를 작성한다.
7. 이 단계에서는 Codex가 코드를 수정하지 않고 읽기 전용 Audit만 수행하도록 한다.

---

## 5. 첫 Audit의 제한 범위

첫 Audit은 저장소 전체를 한꺼번에 분석하지 않는다.

다음 기능과 직접 관련된 코드만 우선 조사한다.

* CLI에서 연구 주제를 입력받는 경로
* Research Request 모델
* Research Planning 또는 Query Planning
* OpenAI Responses API 또는 LLM Client
* Search Port, Search Adapter 또는 Search Tool
* Source Reader 또는 Fetcher
* Research Document 또는 Source 모델
* 파일 기반 결과 저장
* Report 또는 Result Writer
* Usage, Token 및 비용 계산
* 현재 Composition Root와 실제 Runtime 연결 경로

RAG, Memory, Multi-Agent, Background Job 등은 위 기능과 직접 연결된 부분만 확인하고, 전체 감사는 이후 별도 Work Item에서 수행한다.

---

## 6. Audit 결과에 반드시 포함할 사항

Codex Audit 결과는 다음을 포함해야 한다.

```text
Component
File path
주요 클래스 또는 함수
현재 역할
Implemented 여부
Tested 여부
Runtime-connected 여부
실제 API 사용 여부
Fake 또는 Stub 여부
재사용 가능 여부
Adapter 필요 여부
부족한 기능
권장 조치
근거가 되는 테스트 또는 실행 경로
```

또한 다음 질문에 답해야 한다.

* 현재 CLI에서 실제로 어떤 Pipeline이 실행되는가
* 외부 LLM이 실제 기본 경로에서 호출되는가
* 인터넷 검색 기능이 이미 존재하는가
* Source 원문을 수집하는 Reader가 존재하는가
* 실행 결과를 로컬 폴더에 저장하는 코드가 존재하는가
* 저장된 자료를 다시 읽을 수 있는가
* Usage와 비용 계산이 실제 API 응답과 연결되는가
* 첫 구현 단계에서 재사용할 수 있는 최소 코드 집합은 무엇인가
* 새로 작성해야 할 최소 기능은 무엇인가

---

## 7. 작업 원칙

* 실제 코드 상태를 추측하지 않는다.
* 기준 문서의 주장만으로 구현 여부를 확정하지 않는다.
* 코드, 테스트, 실행 경로를 근거로 판단한다.
* 아직 확인하지 못한 사항은 `미확인`으로 표시한다.
* 신규 구현 전에 Audit 결과를 사용자에게 보고한다.
* 사용자의 승인 전에는 다음 구현 단계로 넘어가지 않는다.
* 한 번에 하나의 검증 가능한 Work Item만 진행한다.

먼저 위 기준을 바탕으로 현재 목표와 첫 Audit 범위를 간결하게 재확인하고, 이어서 Codex CLI에 전달할 읽기 전용 첫 Audit Prompt를 작성하라.
