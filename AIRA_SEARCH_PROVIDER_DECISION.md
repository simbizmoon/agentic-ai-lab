# AIRA SEARCH PROVIDER DECISION

## 1. 문서 목적

본 문서는 AIRA Live Research Vertical Slice의 첫 Web Search Provider와
통합 방식을 결정한다.

기준일: 2026-08-06

근거 문서:

- `AIRA_PROJECT_CHARTER.md`
- `DECISIONS.md`
- `AIRA_PROJECT_AUDIT_REPORT.md`
- `AIRA_CAPABILITY_MATRIX.md`
- `AIRA_TARGET_ARCHITECTURE.md`
- `AIRA_INTEGRATION_PLAN.md`
- Audit 14 저장소 조사 결과
- Tavily 공식 API 문서
- Brave Search API 공식 문서
- SerpApi 공식 문서

---

## 2. 결정

첫 Live Web Search Provider는 **Tavily Search API**로 한다.

초기 구현은 Tavily Python SDK를 사용하지 않고,
**직접 REST 호출 + `httpx` Client Adapter** 방식으로 구현한다.

초기 환경변수는 다음을 사용한다.

```text
TAVILY_API_KEY
TAVILY_PROJECT_ID        # 선택
TAVILY_TIMEOUT_SECONDS   # 기본값 적용
```

초기 Search 요청 정책:

```text
endpoint: https://api.tavily.com/search
search_depth: basic
auto_parameters: false
include_answer: false
include_raw_content: false
include_images: false
include_usage: true
topic: general
max_results: 명시적 상한
```

---

## 3. 선택 이유

### 3.1 Agent Research 용도 적합성

Tavily Search API는 일반 검색 결과뿐 아니라 다음 정보를 제공한다.

- 정렬된 Search Result
- 제목
- URL
- 관련 Content Snippet
- Relevance Score
- Request ID
- Response Time
- 선택적 Credit Usage

이 필드는 기존 AIRA의 다음 Domain Model로 정규화하기 적합하다.

- `ResearchSourceCandidate`
- `ResearchSourceSearchResult`
- 실행 Usage 및 Provider Metadata

### 3.2 초기 비용과 학습 접근성

Tavily는 무료 월간 Credit을 제공한다.

초기 `basic` 검색은 요청당 1 Credit이므로
Live Vertical Slice와 Smoke Test에 적합하다.

초기 구현에서는 `search_depth=basic`을 명시하여
자동으로 2 Credit의 `advanced` 검색이 선택되지 않도록 한다.

### 3.3 명시적인 Usage 기록

`include_usage=true`를 사용하면 응답에 사용 Credit을 포함할 수 있다.

이는 AIRA의 실행별 Usage 기록 목표와 일치한다.

### 3.4 날짜 및 Domain Filter

Tavily는 다음 Search 제약을 지원한다.

- `start_date`
- `end_date`
- `time_range`
- `include_domains`
- `exclude_domains`
- `country`
- `max_results`

기존 `ResearchSearchQuery`와 `ResearchRequest`의 제약을
Provider 요청으로 변환하기에 적합하다.

### 3.5 Provider-independent Adapter 가능

REST 요청과 응답을 Tavily 전용 Adapter 내부에 격리하면
AIRA Domain과 Search Port는 Tavily SDK 객체에 의존하지 않는다.

향후 Brave, SerpApi 또는 다른 Provider를 추가할 때
동일한 `ResearchSourceSearchTool` Port를 구현할 수 있다.

---

## 4. 직접 REST + httpx를 선택한 이유

Audit 14에서 확인된 사실:

- `httpx 0.28.1`이 현재 가상환경에 설치되어 있다.
- 그러나 `pyproject.toml`의 직접 의존성에는 선언되어 있지 않다.
- 설치된 `httpx`는 OpenAI SDK의 전이 의존성일 가능성이 높다.
- Tavily SDK는 현재 설치되어 있지 않다.
- 저장소에는 Lock File이 없다.
- 실제 애플리케이션 코드에서 `httpx`를 사용하는 구현은 확인되지 않았다.

결정:

- `httpx`를 `pyproject.toml`의 직접 Runtime Dependency로 명시한다.
- Tavily SDK 의존성은 추가하지 않는다.
- Tavily API 호출 세부사항은 Adapter 내부에 둔다.
- Unit Test에서는 실제 `httpx.Client` 대신 Provider Client Port 또는
  `httpx.MockTransport`를 사용한다.

장점:

- 불필요한 SDK 의존성 방지
- Provider 전용 객체 누출 방지
- Timeout과 Header를 직접 제어
- 응답 Fixture Test가 쉬움
- 향후 Provider 교체가 쉬움

---

## 5. 기존 설정 구조에 대한 결정

현재 `app/config.py`는 `OPENAI_API_KEY`가 없으면 오류를 발생시키는 구조다.

이는 다음 실행에는 적합하지 않다.

```text
Deterministic Planner
+ Tavily Search
+ HTTP Reader
+ OpenAI 호출 없음
```

따라서 첫 Search Adapter는 전역 `app/config.py`에 직접 결합하지 않는다.

초기에는 Tavily 전용 설정 Schema와 Factory를 둔다.

예상 책임:

```text
TavilySearchConfig
- api_key
- base_url
- timeout_seconds
- search_depth
- max_results
- project_id

load_tavily_search_config()
- TAVILY_API_KEY 읽기
- 선택적 환경변수 읽기
- 값 검증
- Secret 값 자체는 repr 또는 로그에 노출하지 않음
```

장기적으로 전역 설정 구조를 재설계할 수 있으나,
첫 Vertical Slice에서 OpenAI 설정과 Search 설정을 강제로 합치지 않는다.

---

## 6. 인증과 Header 정책

Tavily REST 인증은 다음 Header를 사용한다.

```text
Authorization: Bearer <TAVILY_API_KEY>
Content-Type: application/json
```

선택적으로 다음을 사용할 수 있다.

```text
X-Project-ID: <TAVILY_PROJECT_ID>
X-Session-Id: <execution_id>
```

초기 정책:

- `X-Project-ID`는 설정된 경우에만 전송한다.
- `X-Session-Id`에는 AIRA `execution_id`를 사용하도록 검토한다.
- `X-Human-Id`는 첫 Vertical Slice에서 전송하지 않는다.
- Authorization Header는 Trace, Error, Fixture 및 Artifact에 저장하지 않는다.

---

## 7. 요청 Mapping

AIRA Search Query를 Tavily 요청으로 다음과 같이 변환한다.

| AIRA | Tavily |
|---|---|
| query text | `query` |
| maximum results | `max_results` |
| start date | `start_date` |
| end date | `end_date` |
| included domains | `include_domains` |
| excluded domains | `exclude_domains` |
| general/news intent | `topic` |
| execution usage tracking | `include_usage=true` |

초기에는 다음을 고정한다.

```text
search_depth=basic
auto_parameters=false
include_answer=false
include_raw_content=false
include_images=false
```

검색 Provider가 원문 Reader 역할까지 대신하지 않도록
`include_raw_content=false`로 둔다.

---

## 8. 응답 Mapping

Tavily 응답의 다음 필드를 보존한다.

Top level:

- `query`
- `response_time`
- `request_id`
- `usage.credits`

Result:

- `title`
- `url`
- `content`
- `score`
- 원래 Result 순서

AIRA Mapping:

```text
title       → ResearchSourceCandidate.title
url         → ResearchSourceCandidate.url
content     → ResearchSourceCandidate.snippet
result order→ ResearchSourceCandidate.rank
score       → candidate metadata
request_id  → search result metadata
credits     → normalized usage metadata
```

Provider의 전체 원본 응답은 기본적으로 저장하지 않는다.

필요한 필드만 검증·정규화하여 저장한다.

---

## 9. 오류 Mapping

최소 분류:

| HTTP/상황 | AIRA 오류 |
|---|---|
| 400 | Search request validation |
| 401/403 | Search authentication/permission |
| 429 | Search rate limit |
| Timeout | Search timeout |
| 5xx | Search provider failure |
| 잘못된 JSON | Search response validation |
| 빈 results | 정상 No Result |
| 잘못된 Result URL | 개별 Result 제외 또는 구조화 실패 |

429 응답에서는 `Retry-After`를 읽어 Metadata에 보존한다.

첫 Work Item에서는 자동 Retry를 필수로 하지 않는다.
오류 정규화와 retryable 판정을 먼저 구현한다.

---

## 10. 대안 Provider 검토

### Brave Search API

장점:

- 독립 Search Index
- 일반 Web Search 기능
- 날짜·언어·국가 관련 기능
- 비교적 단순한 가격 구조

보류 이유:

- 첫 Agent Research Vertical Slice에서 Tavily의 Search Result와 Usage 구조가
  기존 AIRA Domain에 더 직접적으로 맞는다.
- Search Result 저장·사용 관련 약관을 별도 Legal Review 없이 단정하지 않는다.
- 향후 Provider 비교 대상에서 유지한다.

### SerpApi

장점:

- 다양한 Search Engine과 SERP 유형
- 특수 검색 확장 가능성

보류 이유:

- 초기 일반 Web Research에 비해 기능 범위가 과도하다.
- 초기 유료 진입비용이 Tavily 무료 Credit보다 높다.
- 향후 특허·학술·쇼핑 등 특수 Search가 필요할 때 재검토한다.

### OpenAI Built-in Web Search

장점:

- 기존 OpenAI Responses API와 연결 가능
- LLM과 Search를 한 호출 흐름에서 사용할 수 있음

보류 이유:

- Search 결과 수집과 LLM 추론이 결합된다.
- 독립 Search Port의 재현성·비교·Provider 교체 목표와 덜 맞는다.
- 첫 Search Adapter는 LLM Provider와 분리하는 편이 Architecture 원칙에 맞다.
- 향후 OpenAI Provider 통합 또는 비교 실험에서 검토한다.

---

## 11. 구현 경계

첫 Tavily Work Item에서 구현:

- Tavily Config Schema
- 환경변수 Loader
- 최소 Provider Client Port 또는 HTTP Wrapper
- REST Client
- Search Adapter
- 오류 Mapping
- Response Validation
- Unit Test
- 선택적 Smoke Test Script

구현하지 않음:

- Tavily Extract
- Tavily Crawl
- Tavily Research
- Tavily MCP
- Tavily Python SDK
- 복수 Provider
- 자동 Provider Fallback
- Advanced Search 기본값
- Answer 생성
- Raw Content 수집
- 자동 Retry Loop

---

## 12. Acceptance Criteria

- `TAVILY_API_KEY`가 없을 때 명확한 설정 오류가 발생한다.
- API Key가 로그와 오류 메시지에 노출되지 않는다.
- Search 요청은 `search_depth=basic`을 명시한다.
- `max_results`가 AIRA 상한을 초과하지 않는다.
- 응답이 기존 AIRA Domain Model로 검증된다.
- Credit Usage와 Request ID가 Metadata에 보존된다.
- 401, 429, Timeout, 5xx 및 잘못된 응답이 구분된다.
- Unit Test는 실제 네트워크 없이 통과한다.
- 실제 Smoke Test는 명시적으로 실행할 때만 네트워크를 사용한다.
- 기존 In-memory Search 구현과 테스트를 유지한다.
- 전체 pytest와 Ruff가 통과한다.

---

## 13. 최종 결정 요약

```text
First Search Provider:
Tavily Search API

Integration:
Direct REST with explicit httpx dependency

Authentication:
TAVILY_API_KEY

Initial Mode:
basic search
no answer
no raw content
usage enabled

Architecture:
Provider-specific Adapter behind ResearchSourceSearchTool

Fallback:
None in first Vertical Slice
