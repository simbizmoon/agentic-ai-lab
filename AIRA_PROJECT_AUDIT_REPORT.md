# AIRA PROJECT AUDIT REPORT

## 1. 문서 목적

본 문서는 2026-08-06 기준 `/home/moon/Project/agentic-ai-lab` 저장소의
AIRA 관련 구현 상태를 실제 코드, 참조 관계, 테스트 및 실행 결과에 근거해
정리한 Existing Capability Audit 결과이다.

본 감사의 목적은 기존 코드를 폐기하거나 신규 기능을 무조건 추가하는 것이
아니다. 이미 구현된 Capability를 다음 네 상태로 분리하고, 실제 AIRA Runtime에
재사용할 대상을 확정하는 것이다.

- Implemented
- Tested
- Runtime-connected
- Production-ready

감사 중 소스 파일은 수정하지 않았으며, 감사 전후 Git 작업 트리는 깨끗했다.

---

## 2. 감사 범위

이번 감사에서는 다음 축을 우선 확인했다.

1. CLI Entry Point와 실제 Runtime 호출 경로
2. Research Request, Task, Query Planning
3. OpenAI Responses API와 Structured Planning
4. Search Port와 Search Adapter
5. Source Reader Port와 Web Fetch 가능성
6. Result Writer와 실행별 저장
7. Usage, Token, Budget 및 Cost
8. Trace와 Execution Record
9. Application Research Flow
10. Tool Registry, Plan Step 실행 및 Agent Loop
11. 전체 테스트와 Ruff 기준선

RAG, Memory 및 Multi-Agent 전체 구현의 세부 품질은 이번 감사에서 완결하지
않았다. 다만 첫 Live Research Vertical Slice와 직접 연결되는 부분은 참조 관계와
계측 Schema를 확인했다.

---

## 3. 저장소 기준선

- 저장소 경로: `/home/moon/Project/agentic-ai-lab`
- Git Branch: `main`
- Python: `3.12.3`
- pytest: `9.1.1`
- Ruff: `0.16.0`
- 전체 테스트: `4088 passed in 15.93s`
- Ruff: `All checks passed!`
- 감사 전후 Git 작업 트리: clean

해석:

- 저장소의 Unit·Integration 테스트 기준선은 강하다.
- 테스트 통과는 실제 외부 API와 인터넷 자료를 사용한 운영 검증을 의미하지 않는다.
- 현재 제품 문제의 핵심은 코드 품질 부족보다 Runtime 통합 부족이다.

---

## 4. 현재 `aira research` Runtime

확인된 기본 실행 경로는 다음과 같다.

```text
aira
→ app.cli:main
→ run_research_command
→ LocalResearchHandler
→ LocalDocumentAdapter
→ build_local_research_pipeline
→ ResearchRequest
→ SingleResearchAgentPipeline
→ ResearchResultGuardrail
→ ResearchResultWriter
```

현재 Runtime은 사용자가 직접 지정한 TXT 또는 Markdown 문서를 대상으로 한다.

```text
로컬 문서 입력
→ 결정론적 Task 분해
→ 결정론적 Query 생성
→ In-memory Search
→ In-memory Reader
→ 문서 전체 Evidence 처리
→ 결정론적 Claim 생성
→ Markdown·JSON 저장
```

### 판정

현재 `aira research`는 다음으로 분류한다.

```text
결정론적 Offline Research Baseline
```

현재 Runtime은 다음이 아니다.

- 실제 인터넷 Research Agent
- LLM 기반 조사·분석 Runtime
- 동적으로 Tool을 선택하는 Agent
- 실제 Web Search와 Web Fetch를 수행하는 Agent
- 기존 RAG, Memory, Multi-Agent Capability를 통합한 Runtime

### 유지 가치

- Schema와 Pipeline 회귀 테스트
- 외부 API 없는 결정론적 테스트
- 실패 상태 Simulation
- 향후 Live Agent와의 비교 기준
- 제한된 Offline Fallback

따라서 삭제하지 않고 Offline Baseline으로 명확히 격리한다.

---

## 5. OpenAI 및 LLM Capability

### 확인된 구현

- `OpenAIPlannerClient`
- OpenAI Responses API `responses.create`
- Strict JSON Schema 출력
- Pydantic 결과 검증
- `responses.parse` 기반 Structured Analysis
- Multi-turn Tool Calling 예제와 테스트
- OpenAI Embedding Provider
- Grounded Answer Service
- 실제 OpenAI Usage 추출 코드

### Planning 호출 구조

```text
PlanCreationRequest
→ PlannerPromptComposer
→ OpenAIPlannerClient
→ Responses API
→ PlanDraftOutput
→ PlannerOutputValidator
→ PlanFactory
→ PlanningService
```

### 장점

- OpenAI SDK 객체의 최소 Protocol 추상화
- Fake Client 주입 가능
- Strict JSON Schema
- Prompt와 Request 일치 검증
- Prompt Injection 방어 지침
- Initial Planning과 Replanning 지원
- Factory 기반 실제 `OpenAI()` 생성

### 확인된 Gap

- 현재 `aira research`에 연결되지 않음
- Planner Result에 Usage가 포함되지 않음
- Timeout과 Retry가 Planner Config에 명시적으로 연결되지 않음
- 실제 OpenAI API Smoke Test는 미확인
- 범용 Plan Step에 Tool별 구조화된 인수가 없음

### 재사용 결정

- Planner Client, Prompt Composer, Validation 및 Factory는 재사용한다.
- Usage, Timeout, Retry 및 Research 전용 변환 Adapter를 보강한다.
- 첫 Live Research Vertical Slice에서는 범용 Plan Tool Loop를 필수 경로로 삼지 않는다.

---

## 6. Research Task와 Query Planning

### 현재 구현

`ResearchTaskDecomposer`와 `ResearchSearchQueryPlanner`는 모두 결정론적이다.

Task 분해:

- `include_topics`가 없으면 일반 Research Task 하나 생성
- Topic이 있으면 Topic별 Task 생성
- Topic이 여러 개면 마지막 Synthesis Task 생성

Query Planning:

- Focused Query
- Official Documentation Query
- Primary Research Query
- 날짜 범위
- 선호 Source 유형
- 최대 결과 수
- Query Priority

### Query Schema 장점

`ResearchSearchQuery`는 다음을 지원한다.

- Query ID와 Task 연결
- Query Type
- Priority
- Source Type
- Date Range
- Maximum Results
- Exact Phrase
- Metadata

### 현재 한계

- LLM 기반 의미 이해 없음
- 동의어와 Entity 확장 없음
- 한국어·영어 병렬 Query 없음
- 검색 결과 기반 Query 수정 없음
- Contradicting·Recency Query 유형은 Schema에 있으나 기본 Planner에서 미사용

### 재사용 결정

- Query Schema와 Query Set은 그대로 재사용한다.
- 결정론적 Planner는 Baseline과 Fallback으로 유지한다.
- Live Runtime에는 LLM 기반 Research Query Planning Adapter를 추가한다.

---

## 7. Search Capability

### 확인된 구현

- `ResearchSourceSearchTool` Port
- `ResearchSourceSearchResult`
- `ResearchSourceCandidate`
- `InMemoryResearchSourceSearchTool`
- Query Set 전체 실행 Adapter

### In-memory Search 동작

- 미리 적재된 Record만 검색
- 제목 일치 가중치 3
- Keyword 일치 가중치 2
- Snippet 일치 가중치 1
- Date와 Source Type 필터

### 확인된 사실

실제 인터넷 검색 구현은 발견되지 않았다.

다음 Provider 또는 네트워크 검색 사용 흔적이 없었다.

- OpenAI Web Search Tool
- Bing Search
- Google Search
- Brave Search
- Tavily
- SerpAPI
- DuckDuckGo
- 기타 HTTP Search API

### 재사용 결정

- Search Port와 결과 Schema는 그대로 재사용한다.
- In-memory Search는 Offline Test Adapter로 유지한다.
- 실제 Web Search Adapter 한 개를 첫 신규 외부 Capability로 구현한다.

---

## 8. Source Reader와 Web Fetch

### 확인된 구현

- `ResearchSourceReader` Port
- `ResearchSourceDocument`
- `ResearchSourceDocumentSection`
- 구조화된 Read Failure
- `InMemoryResearchSourceReader`

### Document Schema 장점

- Source Candidate 포함
- Read/Failed 상태
- Content Type
- Language
- Section과 Character Range
- Word/Character Count 무결성 검증
- Reader 이름
- 구조화된 Error

### 확인된 사실

실제 URL에 HTTP 요청을 보내는 Web Reader는 발견되지 않았다.

다음 사용 흔적이 없었다.

- `requests.get`
- `httpx.Client` 또는 `httpx.get`
- `urllib.request`
- `aiohttp`
- BeautifulSoup
- Trafilatura
- Readability
- HTML 본문 Parser

### 재사용 결정

- Reader Port와 Document Schema는 그대로 재사용한다.
- In-memory Reader는 Offline Test Adapter로 유지한다.
- 첫 Live Runtime에 HTTP/HTML Reader를 신규 구현한다.
- PDF Reader는 첫 HTML 경로 안정화 후 별도 Work Item으로 확장한다.

---

## 9. Usage, Token, Budget 및 Cost

### 확인된 구현

실제 OpenAI 응답에서 다음 Usage를 추출하는 코드가 존재한다.

- Input Tokens
- Cached Input Tokens
- Output Tokens
- Reasoning Tokens
- Total Tokens

다음 무결성 검증도 존재한다.

- Cached Input Tokens는 Input Tokens를 초과하지 않음
- Reasoning Tokens는 Output Tokens를 초과하지 않음
- Total Tokens는 Input과 Output의 합과 일치

`ExecutionBudget`은 다음을 제한한다.

- 최대 Attempt
- 최대 기록 Token
- 최대 경과 시간

Budget 초과 전용 예외와 실제 중단 로직이 구현되어 있다.

### 확인된 Gap

- Planner Client가 Usage 추출 코드를 사용하지 않음
- 현재 `aira research`에 Usage와 Budget이 연결되지 않음
- Model Price Registry 미확인
- 실제 비용 금액 계산 미확인
- 실행 전 예상비용과 실행 후 실제비용 미확인
- Search API Cost 모델 없음

### 재사용 결정

- Token Usage 추출과 검증을 공통 Utility로 재사용한다.
- ExecutionBudget을 Live Runner에 연결한다.
- 금액 Cost 계산은 공식 가격 Source와 기준일 관리 방식을 별도 결정한 후 추가한다.

---

## 10. Trace와 Execution Record

### Trace

다음 Event가 구현되어 있다.

- Agent 시작·완료·실패
- Planning 시작·완료·실패
- Plan 시작·완료·실패·취소·차단
- Step 시작·완료·실패·건너뜀
- Tool 시작·완료·실패
- Evaluation 완료
- Replanning 시작·완료·실패
- Replan 한도 도달

다음 Trace 기능도 존재한다.

- Trace Session
- In-memory Recorder
- Timeline Builder
- Summary Builder
- Read Service
- JSON·Text·Markdown Export
- File Writer
- Archive와 Retention

### Execution Record

`ApplicationExecutionRecord`는 다음을 지원한다.

- Execution, Root, Parent 및 Previous Attempt 관계
- PENDING, RUNNING, SUCCEEDED, FAILED 등 Lifecycle
- Input·Output Artifact Reference
- Guardrail·Retry·Recovery Reference
- Failure Category
- Timestamp와 Optimistic Concurrency

### 확인된 Gap

- 현재 `aira research`에 Trace가 연결되지 않음
- Execution Repository의 확인된 Concrete 구현은 In-memory 방식
- CLI 재실행 후 Execution Record 영속성 없음
- Usage와 Artifact Reference가 현재 Research Runtime에 연결되지 않음

### 재사용 결정

- Trace Schema와 Session을 Live Runner에 연결한다.
- Application Execution Service를 실행 Lifecycle 관리에 재사용한다.
- 초기 영속성은 실행 폴더의 JSON Artifact로 구현한다.
- SQLite는 조회와 누적 관리 요구가 확인된 후 도입한다.

---

## 11. Application Research Flow

### 확인된 구조

```text
ApplicationResearchFlowService
→ Idempotency
→ Transaction
→ ApplicationResearchExecutionService
→ ResearchExecutionRunner
→ Execution Repository
```

`ResearchExecutionRunner`는 실제 Agent 구현을 주입하기 위한 Port이다.

### 확인된 사실

- Application Service는 구현되고 테스트됨
- Execution Lifecycle 저장 가능
- Idempotent Result 재사용 가능
- 실제 AIRA Runner는 존재하지 않음
- 현재 CLI와 Application Flow가 연결되지 않음

### 재사용 결정

첫 Live Runtime에서는 다음을 구현한다.

```text
ConcreteAiraResearchRunner
```

Runner의 책임:

1. Application Request를 ResearchRequest로 변환
2. Planning과 Query 생성
3. Search 실행
4. Source 읽기
5. Artifact 저장
6. Usage와 Trace 기록
7. 정규화된 Application Output 반환

첫 Vertical Slice에서는 Idempotency 전체를 필수로 연결하지 않는다.
ApplicationResearchExecutionService부터 우선 연결한다.

---

## 12. Tool Registry와 Agent Loop

### 확인된 구현

- Planning Agent용 `Tool` Interface
- Planning Tool Registry
- Plan Scheduler
- Plan Lifecycle
- Plan Step Executor
- Plan Execution Service
- Tool 성공·실패에 따른 Step 상태 반영
- Trace Event 연결
- OpenAI Function Tool Definition Registry
- Application Tool Execution Service

### 구조적 중복

현재 세 종류의 Tool 계약이 존재한다.

1. Planning `Tool`
2. OpenAI Function `ToolDefinition`
3. Application `ToolExecutionRunner`

서로 목적은 다르지만 직접 연결되지 않는다.

### 핵심 Gap

Plan Step에는 Tool 이름은 있으나 Tool별 구조화된 인수가 없다.

현재 Step Executor는 Tool에 다음만 전달한다.

- Title
- Expected Output
- Metadata

Web Search에 필요한 Query, Maximum Results, Date Range 등은 보장되지 않는다.

### 재사용 결정

- Tool Interface, Registry, Scheduler, Lifecycle 및 Trace는 후속 Agent Loop에 재사용한다.
- 첫 Live Research Vertical Slice는 Research Domain Port를 직접 조립한다.
- 실제 Search·Reader 경로가 안정된 후 범용 Plan Tool Loop와 통합한다.

---

## 13. Capability 분류 요약

### 그대로 재사용

- ResearchRequest
- Research Task·Query Schema
- Source Candidate·Document Schema
- Search Port
- Source Reader Port
- Result Guardrail과 Writer 일부
- OpenAI Planner의 Prompt·Validation 구조
- Token Usage 추출과 검증
- ExecutionBudget
- Agent Trace
- ApplicationExecutionRecord
- ApplicationResearchExecutionService

### 확장 또는 Adapter 후 재사용

- OpenAI Planner Result와 Config
- ResearchRequest ↔ Application Request 변환
- LLM Research Query Planning
- Search Set Adapter의 오류·Duration·Provider 보존
- Reader Set Adapter의 개별 실패 보존
- Result Writer의 Source 원문·Metadata 저장
- Execution Record의 Artifact·Usage Reference
- CLI Handler와 Composition Root

### Offline Baseline으로 유지

- Deterministic Task Decomposer
- Deterministic Query Planner
- In-memory Search
- In-memory Reader
- Whole-document Evidence Extraction
- Deterministic Claim Builder
- 현재 Local Research Runtime

### 신규 구현

- Concrete AIRA Research Runner
- 실제 Web Search Adapter
- 실제 HTTP/HTML Source Reader
- Source Artifact Writer
- Live Composition Root
- 실제 외부 API Smoke Test
- 금액 Cost 계산과 Price Registry

### 후속 감사 또는 통합

- RAG 전체 재사용성
- Memory 전체 재사용성
- Multi-Agent 실제 Runtime 연결성
- PDF/HWP Reader
- Persistent Repository
- 범용 Plan Tool Loop와 Research Domain 연결

---

## 14. 목표 Minimal Live Runtime

```text
CLI
→ Live Research Handler
→ ApplicationResearchExecutionService
→ ConcreteAiraResearchRunner
   → ResearchRequest Adapter
   → LLM Research Planning 또는 최소 Query Planning
   → ResearchSearchQuerySet
   → Web Search Adapter
   → HTTP/HTML Reader
   → Source Artifact Writer
   → Usage Collector
   → Trace Session
   → Result Writer
```

초기 성공 기준:

1. 연구 질문 하나를 입력할 수 있음
2. 제한된 검색 Query를 생성함
3. 실제 인터넷 검색을 최소 1회 수행함
4. 최대 3~5개 Source를 선택함
5. 실제 원문을 Fetch함
6. Source별 Metadata와 본문을 저장함
7. Query, Provider, 오류, Duration 및 Usage를 저장함
8. 결과 폴더만으로 실행을 다시 검토할 수 있음
9. Offline Baseline과 Live Runtime을 명확히 구분함
10. 관련 Unit Test, Integration Test, Smoke Test, Ruff가 통과함

---

## 15. 권장 구현 순서

### Work Item 1 — Live Web Search Adapter

- Search Provider 결정
- `ResearchSourceSearchTool` 구현
- Provider 응답을 `ResearchSourceCandidate`로 정규화
- Timeout, 오류, No Result, Retryable 상태 처리
- Fake Unit Test
- 실제 Smoke Test

### Work Item 2 — HTTP/HTML Source Reader

- `ResearchSourceReader` 구현
- Redirect, Status, Content-Type, Timeout 처리
- HTML 본문 추출
- SourceDocument와 Section 생성
- Fetch Metadata와 Content Hash 저장
- Fake Server 또는 Fixture Test
- 실제 공개 페이지 Smoke Test

### Work Item 3 — Source Artifact Writer

실행 폴더 예시:

```text
reports/<execution_id>/
├── request.json
├── execution.json
├── plan.json
├── queries.json
├── search_results.json
├── sources/
│   ├── source-001.json
│   ├── source-001.md
│   └── ...
├── usage.json
├── trace.json
├── result.json
└── report.md
```

### Work Item 4 — Concrete Live Research Runner

- Application Request Adapter
- Search와 Reader 조립
- Trace와 Budget 연결
- Artifact Reference 연결
- Result 반환

### Work Item 5 — CLI Live Mode

- Offline과 Live 명령 분리
- 비용과 외부 연결 승인 Gate
- 실패 메시지와 종료 코드
- 실제 E2E 실행

---

## 16. 최종 감사 결론

저장소는 기능이 없거나 품질이 낮은 상태가 아니다.

실제 상태는 다음과 같다.

```text
개별 Capability와 Schema: 풍부하고 테스트됨
Offline Baseline: 구현됨
OpenAI Planning: 구현되었으나 기본 Runtime에 미연결
Usage·Budget·Trace·Application: 구현되었으나 미연결
실제 Web Search: 없음
실제 Web Reader: 없음
Concrete Product Runtime: 없음
```

따라서 권장 전략은 전면 재작성이 아니다.

```text
Integration-first
→ 실제 외부 Search·Reader 최소 추가
→ 기존 Capability를 좁은 Live Runtime으로 연결
→ E2E 성공 후 RAG, Memory, Tool Loop, Multi-Agent를 단계적으로 통합
```
