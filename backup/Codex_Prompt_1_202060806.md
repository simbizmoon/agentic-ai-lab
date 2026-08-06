# AIRA 첫 Work Item — 검색·수집·로컬 저장 Capability Audit

당신은 `/home/moon/Project/agentic-ai-lab` 저장소의 기존 구현을 감사하는 역할을 수행한다.

이번 작업의 목적은 새 기능을 구현하는 것이 아니다.

사용자가 연구 주제를 입력했을 때 다음 최소 흐름을 구축하기 위해 기존 코드에서 재사용 가능한 기능을 정확히 확인하는 것이 목적이다.

```text
연구 주제 입력
→ 최소 조사계획 또는 검색 Query 생성
→ 인터넷 Source 검색
→ Source 원문 또는 핵심 내용 수집
→ Metadata와 함께 로컬 폴더 저장
→ Usage와 비용 기록
```

---

## 1. 절대 규칙

이번 작업은 읽기 전용 Audit이다.

다음을 수행하지 마라.

* 코드 수정
* 파일 생성 또는 삭제
* Refactoring
* 새로운 Schema, Interface, Adapter 또는 Service 작성
* Dependency 추가 또는 제거
* 테스트 수정
* Git Commit
* Git Push
* 실제 유료 API 호출
* 기존 환경변수 변경
* 저장소 전체를 무계획하게 전수 분석

코드를 변경하지 말고 Audit 보고서만 출력하라.

비밀키, Token 또는 Secret의 실제 값을 출력하지 마라.

---

## 2. 기준 경로

```text
/home/moon/Project/agentic-ai-lab
```

모든 명령은 위 경로를 기준으로 실행한다.

작업 시작 시 다음을 확인하라.

```bash
cd /home/moon/Project/agentic-ai-lab
pwd
git status --short
git branch --show-current
```

작업 전후에 `git status --short`를 실행하여 저장소 변경이 발생하지 않았는지 확인하라.

기존에 변경된 파일이 있더라도 수정하거나 되돌리지 마라.

---

## 3. 이번 Audit의 제한 범위

저장소 전체 Architecture를 모두 감사하지 않는다.

다음 흐름과 직접 관계된 코드만 우선 조사한다.

### A. CLI 및 Composition Root

* CLI Entry Point
* `aira research` 또는 이에 준하는 명령
* CLI Argument 또는 Prompt 입력
* Handler
* Composition Root
* 실제 Pipeline 조립
* 실행 결과의 반환과 저장 경로

### B. Research Request와 Planning

* Research Request 모델
* Research Task
* Query Planning
* Research Plan
* Planning Agent
* LLM 기반 계획과 결정론적 계획의 구분

### C. LLM 및 OpenAI

* OpenAI Client
* Client Factory
* Responses API
* Structured Outputs
* Tool Calling
* Usage 반환
* Retry와 Timeout
* 실제 Client와 Fake·Stub Client 구분
* 현재 CLI Runtime 연결 여부

### D. 검색

* Search Port
* Search Provider
* Search Adapter
* Search Tool
* Internet Search
* Local Search
* Fake Search
* 검색 결과 Metadata 구조

### E. Source 수집과 Reader

* Source Reader Port
* Web Fetcher
* HTML Reader
* PDF Reader
* Text Reader
* Markdown Reader
* Source 원문 수집
* URL, 제목, 발행기관, 날짜 등 Metadata
* Reader가 현재 Runtime에 연결되는지 여부

### F. 결과 및 로컬 저장

* Report Writer
* Result Writer
* Artifact Writer
* File Repository
* Markdown 저장
* JSON 저장
* 실행별 폴더 생성
* 파일명 규칙
* 저장된 결과 재조회
* 중복 실행 또는 충돌 처리

### G. Usage와 비용

* Usage Collector
* Token Counter
* Price Registry
* Cost Estimator
* 실제 비용 계산
* Budget
* Budget Guardrail
* CLI 또는 Pipeline 연결 여부

---

## 4. 조사 방법

### 4.1 파일 구조 확인

먼저 관련 디렉터리와 Entry Point를 찾는다.

필요한 범위에서 다음과 같은 명령을 사용할 수 있다.

```bash
find . -maxdepth 3 -type f | sort
find src tests -type f | sort
rg -n "aira|research|ResearchRequest|ResearchPlan|query|search|reader|source|report|result|artifact|usage|token|cost|budget|Responses|OpenAI" .
```

출력량이 너무 많으면 검색 범위를 좁혀라.

### 4.2 Runtime 경로 추적

현재 사용자가 실행하는 CLI 명령에서 시작하여 실제 호출 흐름을 추적한다.

예시 형식:

```text
CLI Entry Point
→ Command
→ Handler
→ Adapter
→ Pipeline
→ Planner
→ Search
→ Reader
→ Writer
→ Output path
```

실제 코드에서 확인된 클래스와 함수 이름을 사용하라.

### 4.3 테스트 확인

각 주요 Component에 대해 관련 테스트를 확인한다.

다음을 구분하라.

* Unit Test
* Integration Test
* E2E Test
* Fake 또는 Stub 기반 Test
* 실제 외부 API Test
* 테스트 없음

전체 테스트 Suite를 무조건 실행하지 마라.

Audit에 필요한 좁은 테스트가 명확하고 외부 비용 없이 실행 가능할 때만
관련 테스트 명령을 제안하거나 실행하라.

실행한 경우 정확한 명령과 결과를 기록하라.

### 4.4 외부 API 호출 확인

코드를 읽어 다음을 구분한다.

* 실제 외부 API Client
* Fake Client
* Stub
* Deterministic 구현
* 테스트 전용 Adapter
* Runtime 기본 Adapter

실제 API 호출은 수행하지 않는다.

### 4.5 구현 상태 분류

각 Component를 다음 네 상태로 구분한다.

* `Implemented`
* `Tested`
* `Runtime-connected`
* `Production-ready`

판정 기준:

#### Implemented

실제 기능 코드가 존재한다.

#### Tested

기능을 직접 검증하는 관련 테스트가 존재하고 통과가 확인되었거나,
최근 신뢰할 수 있는 테스트 결과가 존재한다.

#### Runtime-connected

현재 기본 CLI 실행 경로에서 실제로 호출된다.

#### Production-ready

실제 Provider·실제 데이터·오류 처리·비용·보안 및 운영 제약까지
검증되었다.

파일이 존재한다는 이유만으로 `Runtime-connected` 또는
`Production-ready`로 판정하지 마라.

---

## 5. 핵심 확인 질문

Audit 결과에서 다음 질문에 명확히 답하라.

1. 현재 기본 CLI 명령은 무엇인가?
2. CLI에서 연구 주제나 파일을 어떻게 입력받는가?
3. CLI가 실제로 호출하는 최종 Pipeline은 무엇인가?
4. 현재 Pipeline은 LLM 기반인가, 결정론적인가?
5. OpenAI Responses API 코드는 어디에 있는가?
6. 해당 코드가 현재 CLI Runtime에 연결되어 있는가?
7. Structured Output과 Tool Calling 코드는 재사용 가능한가?
8. 인터넷 검색 Provider 또는 Tool이 이미 존재하는가?
9. 존재한다면 실제 Provider인가, Fake 또는 Port만 존재하는가?
10. 웹페이지 원문을 읽는 Reader가 존재하는가?
11. TXT·Markdown·PDF Reader는 각각 어디에 있는가?
12. Source Metadata 모델에는 어떤 필드가 있는가?
13. 실행 결과를 로컬 폴더에 저장하는 코드는 어디에 있는가?
14. 현재 생성되는 파일과 폴더 구조는 무엇인가?
15. 저장된 Source 원문과 Metadata를 다시 읽을 수 있는가?
16. Usage와 Token 계산 코드는 어디에 있는가?
17. 실제 OpenAI API 응답의 Usage와 연결되는가?
18. 모델별 가격과 비용 계산 코드가 있는가?
19. Budget 또는 비용 상한이 Agent 실행을 실제로 중단시키는가?
20. 첫 구현 단계에 그대로 재사용할 수 있는 최소 Component 집합은 무엇인가?
21. Adapter만 추가하면 사용할 수 있는 Component는 무엇인가?
22. 반드시 새로 구현해야 할 최소 기능은 무엇인가?
23. 첫 구현 단계에서 건드리지 말아야 할 불필요한 고급 기능은 무엇인가?

---

## 6. 결과 보고 형식

다음 구조로 최종 Audit 결과를 출력하라.

# 1. Executive Summary

* 현재 CLI Runtime의 실제 상태
* 인터넷 검색 가능 여부
* 외부 LLM 연결 여부
* Source 수집 및 저장 가능 여부
* Usage와 비용 연결 여부
* 첫 구현 단계에서 가장 중요한 결론

# 2. Repository Status

```text
Repository path:
Current branch:
Initial git status:
Final git status:
Files modified by this audit: none
```

# 3. Current Runtime Call Path

실제 코드의 파일, 클래스 및 함수 이름을 사용해 다음처럼 작성한다.

```text
CLI
→ Command
→ Handler
→ Adapter
→ Pipeline
→ Writer
→ Output
```

각 단계의 파일 경로를 함께 표시한다.

# 4. Capability Matrix

| Component | File/Location | Implemented | Tested | Runtime-connected | Production-ready | Real/Fake | Reusable | Adapter needed | Notes |
| --------- | ------------- | ----------: | -----: | ----------------: | ---------------: | --------- | -------: | -------------: | ----- |

최소 포함 Component:

* CLI Input
* Research Request
* Research Planning
* Query Planning
* OpenAI Client
* Responses API
* Structured Output
* Tool Calling
* Search Port
* Internet Search Provider
* Source Reader
* Web Reader
* TXT Reader
* Markdown Reader
* PDF Reader
* Research Document
* Source Metadata
* Evidence
* Report Writer
* JSON Writer
* Local Folder Storage
* Usage Collector
* Token Counter
* Price Registry
* Cost Calculator
* Budget Guardrail
* Trace

# 5. Reusable Components

각 항목에 대해 다음을 기록한다.

* Component
* 파일 경로
* 그대로 재사용 가능한 이유
* 필요한 설정
* 관련 테스트
* 현재 제한

# 6. Adapter or Partial Modification Candidates

* Component
* 현재 구조
* 필요한 Adapter 또는 최소 수정
* 예상 연결 지점
* 위험

# 7. Missing Minimum Capabilities

다음 첫 구현 흐름에 필요한 누락 기능만 정리한다.

```text
연구 주제
→ 검색
→ Source 수집
→ 로컬 저장
```

기능을 과도하게 확장하지 마라.

# 8. Cost Audit Findings

* 실제 Usage 수집 여부
* Token 유형 구분
* 가격 Registry
* 예상비용
* 실제비용
* Budget 실행 연결
* 첫 구현에서 재사용할 수 있는 코드
* 미확인 사항

# 9. Recommended Minimal Integration Path

신규 코드를 최소화하는 연결 순서를 제안한다.

예시:

```text
기존 CLI
→ 기존 Research Request
→ 기존 LLM Provider Adapter
→ 기존 또는 신규 최소 Search Adapter
→ 기존 Source Reader
→ 기존 File Writer
→ 기존 Usage/Cost Collector
```

실제 확인된 코드에 맞춰 작성하라.

# 10. Proposed Next Work Item

Audit 이후 수행할 단 하나의 다음 Work Item을 제안한다.

다음 조건을 지켜라.

* 검색·수집·로컬 저장의 최소 수직 흐름
* 기존 코드 최대 재사용
* 한 번에 검증 가능
* Multi-Agent 제외
* Hybrid RAG 제외
* HWP/HWPX 제외
* FastAPI 제외
* Database 제외
* 유료 API 호출은 사용자 승인 전 제외

포함할 내용:

* 목표
* 수정 예상 파일
* 재사용 Component
* 새로 필요한 최소 코드
* Acceptance Criteria
* 테스트 계획
* 실제 연구 검증 방법
* 비용 및 보안 영향

# 11. Unverified Items

확인하지 못한 사항을 추측하지 말고 별도로 기록하라.

---

## 7. 완료 조건

이번 Audit은 다음을 충족하면 완료다.

* 저장소 파일을 수정하지 않았다.
* 현재 CLI Runtime 경로를 코드로 추적했다.
* 검색·수집·저장 관련 기존 Component를 식별했다.
* 실제 구현과 Fake·Stub을 구분했다.
* `Implemented`, `Tested`, `Runtime-connected`,
  `Production-ready`를 구분했다.
* Usage와 비용 코드의 실제 연결 상태를 확인했다.
* 재사용 가능한 최소 Component를 제시했다.
* 누락된 최소 기능만 제시했다.
* 다음 구현 Work Item을 하나만 제안했다.
* 모든 판단에 파일 경로, 클래스, 함수 또는 테스트 근거가 있다.

Audit 완료 후 코드를 수정하지 말고 결과만 보고하라.
