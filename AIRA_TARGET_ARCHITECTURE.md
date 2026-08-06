# AIRA TARGET ARCHITECTURE

## 1. 문서 목적

본 문서는 AIRA Live Research Vertical Slice의 목표 Runtime Architecture,
Component 책임, 의존 방향, 데이터 흐름, 실행 산출물 및 확장 경계를 정의한다.

본 문서는 다음 기준 문서에 근거한다.

1. `AIRA_PROJECT_CHARTER.md`
2. `DECISIONS.md`
3. `AIRA_PROJECT_AUDIT_REPORT.md`
4. `AIRA_CAPABILITY_MATRIX.md`
5. `MASTER.md`
6. `ROADMAP.md`

본 문서의 초기 범위는 실제 인터넷 검색과 HTTP/HTML 원문 수집을 포함하는
최소 Single-Agent Live Research Runtime이다.

---

## 2. Architecture 목표

첫 Live Runtime은 다음을 실제로 수행해야 한다.

```text
Research Question
→ Validated Research Request
→ Limited Query Planning
→ Live Web Search
→ Limited Source Selection
→ HTTP/HTML Source Reading
→ Source and Metadata Storage
→ Basic Result Construction
→ Usage, Error and Trace Storage
→ Re-readable Run Result
```

초기 목표는 고도화된 보고서 품질이 아니라 다음 세 가지이다.

1. 실제 외부 자료를 사용한다.
2. 실행 결과를 재검토할 수 있게 저장한다.
3. 기존 Offline Baseline과 전체 테스트 기준선을 깨뜨리지 않는다.

---

## 3. Architecture 원칙

### 3.1 Integration-first

기존 Capability를 우선 재사용한다.

전면 재작성은 하지 않는다.

### 3.2 Single-Agent first

첫 Runtime은 하나의 `ConcreteAiraResearchRunner`가 전체 흐름을 조정한다.

Multi-Agent는 Single-Agent 대비 개선이 평가로 확인된 뒤 도입한다.

### 3.3 Domain independence

Research Domain은 특정 Search Provider, 특정 HTTP Client 또는 OpenAI 객체에
직접 의존하지 않는다.

외부 Provider는 Adapter로 연결한다.

### 3.4 Explicit limits

모든 외부 실행은 다음 상한을 명시한다.

- 최대 Search Query 수
- 최대 Search 호출 수
- Query당 최대 Result 수
- 최대 Source 수
- Source당 최대 본문 크기
- HTTP Timeout
- 전체 실행시간
- 최대 LLM 호출 수
- 최대 Token

### 3.5 Reproducibility

실행 결과 폴더만으로 다음을 확인할 수 있어야 한다.

- 무엇을 요청했는가
- 어떤 Query를 사용했는가
- 어떤 결과를 받았는가
- 어떤 Source를 읽었는가
- 무엇이 실패했는가
- 얼마의 시간과 Usage가 사용되었는가
- 어떤 결과를 생성했는가

### 3.6 Safe external access

초기 Reader는 다음만 허용한다.

- `http`
- `https`

다음은 명시적으로 차단한다.

- 로컬 파일 URI
- 사설망 및 Loopback 접근
- 비HTTP Scheme
- 무제한 Redirect
- 무제한 응답 크기

세부 SSRF 방어 정책은 구현 Work Item에서 테스트로 고정한다.

---

## 4. 전체 Runtime 구조

```text
CLI
└── LiveResearchCommandHandler
    └── ApplicationResearchExecutionService
        └── ConcreteAiraResearchRunner
            ├── ApplicationResearchRequestAdapter
            ├── ResearchTaskDecomposer
            ├── ResearchSearchQueryPlanner
            ├── ResearchSourceSearchTool
            │   └── LiveWebSearchAdapter
            ├── ResearchSourceReader
            │   └── HttpHtmlResearchSourceReader
            ├── SourceArtifactWriter
            ├── ResearchResultGuardrail
            ├── ResearchResultWriter
            ├── AgentTraceSession
            └── ExecutionBudget
```

OpenAI Planning은 첫 Runtime에서 선택적으로 연결한다.

```text
최소 경로:
Deterministic Query Planning + Live Search + Live Reader

확장 경로:
OpenAI Planning + Live Search + Live Reader
```

첫 외부 Vertical Slice 성공을 위해 Search와 Reader 연결을 Planning LLM 연결보다
우선할 수 있다.

---

## 5. Layer별 책임

## 5.1 Interface Layer

### `LiveResearchCommandHandler`

책임:

- CLI 인수 수신
- Offline과 Live Mode 구분
- 외부 네트워크 사용 여부 확인
- 입력값을 Application Request로 변환
- 성공 결과 경로 출력
- 오류별 종료코드 반환

담당하지 않는 것:

- Search Provider 호출
- HTML Parsing
- Report 생성 규칙
- Execution 상태 전이

---

## 5.2 Application Layer

### `ApplicationResearchExecutionService`

기존 구현을 재사용한다.

책임:

- `execution_id` 생성
- PENDING → RUNNING → SUCCEEDED/FAILED 상태 관리
- 실행 시작·종료 시각 기록
- 실행 실패 저장
- Runner 호출

초기 Repository:

- Process 내 실행관리는 기존 In-memory Repository를 사용할 수 있다.
- 실행 결과의 영속성은 실행별 Artifact 폴더가 담당한다.
- SQLite Repository는 첫 Vertical Slice에서 제외한다.

### `ApplicationResearchRequestAdapter`

책임:

```text
ApplicationResearchExecutionRequest
→ ResearchRequest
```

변환 예:

- `query` → `question`
- `context.objective` → `objective`
- `context.maximum_sources` → `maximum_sources`
- `context.preferred_source_types` → `preferred_source_types`
- `context.start_date` → `start_date`
- `context.end_date` → `end_date`

변환되지 않는 값은 명시적 기본값을 사용하며, 숨은 추론을 하지 않는다.

---

## 5.3 Orchestration Layer

### `ConcreteAiraResearchRunner`

첫 Live Runtime의 Composition 중심이다.

책임:

1. Application Request를 ResearchRequest로 변환
2. Trace 시작
3. Budget 초기화
4. Task 분해
5. Query 생성
6. Search 실행
7. Source 선택
8. Reader 실행
9. Source Artifact 저장
10. Basic Result 생성
11. Guardrail 검증
12. Result와 Trace 저장
13. Application Output 반환

담당하지 않는 것:

- Provider 전용 응답 Parsing 세부사항
- HTTP Body Parsing 세부사항
- 파일명 안전화 세부사항
- 가격표 관리

---

## 5.4 Domain Layer

기존 구조를 우선 재사용한다.

핵심 모델:

- `ResearchRequest`
- `ResearchSearchQuery`
- `ResearchSearchQuerySet`
- `ResearchSourceCandidate`
- `ResearchSourceDocument`
- `ResearchSourceDocumentSection`
- Research 결과 및 Report Schema

Domain Model은 다음을 알지 않는다.

- Search Provider SDK
- HTTP Client Library
- OpenAI SDK
- CLI
- 파일시스템 경로

---

## 5.5 Port와 Adapter

### Search Port

기존 `ResearchSourceSearchTool`을 사용한다.

Live Adapter 책임:

- Query 실행
- Provider Timeout 적용
- Provider 응답 정규화
- `ResearchSourceCandidate` 생성
- Result Rank 보존
- Provider Metadata 보존
- No Result와 Error 구분

초기에는 Search Provider 하나만 연결한다.

복수 Provider, Provider Routing 및 Provider Fallback은 제외한다.

### Reader Port

기존 `ResearchSourceReader`를 사용한다.

`HttpHtmlResearchSourceReader` 책임:

- URL 검증
- HTTP 요청
- Redirect 제한
- Timeout 적용
- Status Code 처리
- Content-Type 확인
- 응답 크기 제한
- Charset 처리
- HTML 본문 추출
- Section 생성
- Content Hash 계산
- Fetch Metadata 저장

초기 지원 Content-Type:

- `text/html`
- `text/plain`
- `text/markdown` 또는 동등한 Text 응답

PDF는 첫 Reader에서 제외하고 명시적인 Unsupported 결과로 처리한다.

---

## 5.6 Persistence와 Artifact Layer

### `SourceArtifactWriter`

외부 Source별 원문과 Metadata를 저장한다.

### `ResearchResultWriter`

기존 Writer를 확장 또는 조합하여 최종 `result.json`과 `report.md`를 저장한다.

초기 실행 폴더:

```text
reports/<execution_id>/
├── request.json
├── execution.json
├── queries.json
├── search_results.json
├── sources/
│   ├── source-001.json
│   ├── source-001.md
│   └── ...
├── usage.json
├── trace.json
├── errors.json
├── result.json
└── report.md
```

`plan.json`은 실제 Planning 객체를 사용하는 경우에만 생성한다.

빈 파일을 형식상 만들지 않는다.

---

## 6. 실행 데이터 흐름

### 6.1 Request

```text
CLI Arguments
→ ApplicationResearchExecutionRequest
→ ResearchRequest
→ request.json
```

### 6.2 Query

```text
ResearchRequest
→ Task Decomposition
→ Query Planning
→ ResearchSearchQuerySet
→ queries.json
```

### 6.3 Search

```text
ResearchSearchQuery
→ LiveWebSearchAdapter
→ Provider Response
→ ResearchSourceCandidate
→ search_results.json
```

### 6.4 Read

```text
ResearchSourceCandidate
→ HttpHtmlResearchSourceReader
→ ResearchSourceDocument
→ source-XXX.json
→ source-XXX.md
```

### 6.5 Result

```text
Documents
→ Basic Evidence/Claim Pipeline
→ Guardrail
→ result.json
→ report.md
```

### 6.6 Observability

```text
Stage Events
→ AgentTraceSession
→ trace.json

Provider/Reader Usage
→ Normalized Usage Record
→ usage.json

Failures
→ Structured Error Record
→ errors.json
```

---

## 7. Source 선택 정책

첫 Runtime은 단순하고 결정론적인 정책을 사용한다.

1. Query별 Rank를 보존한다.
2. URL 정규화 후 중복을 제거한다.
3. 동일 Domain 과다 집중을 제한할 수 있다.
4. 지원하지 않는 URL Scheme을 제외한다.
5. 최대 Source 수를 초과하지 않는다.
6. 읽기 실패 Source는 결과에서 삭제하지 않고 실패 상태로 보존한다.

초기에는 LLM 기반 Source Critic을 필수로 사용하지 않는다.

---

## 8. 오류 모델

오류는 최소 다음 단계로 분류한다.

- Request Validation
- Query Planning
- Search Authentication
- Search Rate Limit
- Search Timeout
- Search Provider Error
- Search No Result
- URL Validation
- HTTP Network
- HTTP Timeout
- HTTP Status
- Unsupported Content Type
- Response Too Large
- HTML Parse
- Artifact Write
- Guardrail
- Internal

각 오류는 가능하면 다음 정보를 포함한다.

- 단계
- 코드
- 메시지
- retryable
- provider
- query_id
- source_id
- URL
- 발생 시각

비밀키와 민감한 Header는 저장하지 않는다.

---

## 9. Usage와 Budget

첫 Runtime에서 반드시 기록할 항목:

- Search 호출 수
- Search 결과 수
- Reader 호출 수
- Reader 성공·실패 수
- 다운로드 Byte 수
- 전체 Duration
- 단계별 Duration
- LLM Input Token
- LLM Output Token
- Cached Input Token
- Reasoning Token
- Tool 호출 수

금액 Cost는 가격 Registry가 확정되기 전까지 필수 완료 조건으로 두지 않는다.

단, Provider가 금액 Usage를 직접 제공하면 원본 Metadata로 보존할 수 있다.

---

## 10. Trace 정책

기존 Agent Trace 구조를 재사용한다.

첫 Runtime에 필요한 최소 Event:

- AGENT_STARTED
- PLANNING_STARTED
- PLANNING_COMPLETED
- TOOL_STARTED
- TOOL_COMPLETED
- TOOL_FAILED
- AGENT_COMPLETED
- AGENT_FAILED

Search Query별 세부 정보와 URL은 민감정보 여부를 검토해 Metadata에 기록한다.

---

## 11. Security 경계

초기 구현에서 반드시 다룰 항목:

- API Key를 결과 파일에 저장하지 않음
- Authorization Header를 Trace에 저장하지 않음
- `file://` 차단
- Loopback 및 사설 IP 접근 차단
- Redirect 횟수 제한
- 응답 크기 제한
- Timeout 필수
- HTML Script 실행 금지
- 다운로드 파일 자동 실행 금지
- 파일명 Path Traversal 방지
- 기존 실행 폴더 덮어쓰기 방지

---

## 12. 첫 Vertical Slice에서 제외

- Multi-Agent 기본 실행
- 전체 RAG 통합
- Vector DB
- Long-term Memory
- PDF/HWP/HWPX 고도화
- 범용 Plan Tool Loop
- FastAPI
- Background Job
- SQLite/PostgreSQL
- 복수 Search Provider
- Provider 자동 Fallback
- Web UI
- 금액 기반 자동 Routing

---

## 13. 확장 경로

### Step A

Live Search + HTML Reader + Artifact Storage

### Step B

OpenAI Planning과 Usage 연결

### Step C

Basic Evidence와 Citation 품질 개선

### Step D

RAG와 Local Document 통합

### Step E

Evidence Sufficiency와 Replanning

### Step F

Provider 비교와 Cost 최적화

### Step G

Multi-Agent 실험

---

## 14. Architecture 완료 기준

- Component 책임과 의존 방향이 명확하다.
- Search와 Reader가 Port 뒤에 격리된다.
- Domain이 외부 Provider SDK에 의존하지 않는다.
- 실행 결과 폴더 구조가 확정된다.
- 오류·Usage·Trace 저장 위치가 확정된다.
- 첫 구현에서 제외할 범위가 명확하다.
- `AIRA_INTEGRATION_PLAN.md`의 Work Item으로 구현 순서가 연결된다.
