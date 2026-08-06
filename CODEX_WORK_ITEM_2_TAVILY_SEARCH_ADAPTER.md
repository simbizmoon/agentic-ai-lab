# CODEX WORK ITEM 2 — TAVILY LIVE WEB SEARCH ADAPTER

## 1. 작업 목적

AIRA Live Research Vertical Slice의 첫 실제 외부 기능으로
Tavily Search API Adapter를 구현한다.

이번 작업은 다음 범위로 제한한다.

```text
Tavily Config
→ Environment Loader
→ HTTP Client Boundary
→ Tavily REST Client
→ ResearchSourceSearchTool Adapter
→ Error Mapping
→ Response Validation
→ Unit Tests
→ Optional Manual Smoke Test
```

이번 작업에서 HTTP/HTML Reader, Source Artifact Writer,
Concrete Runner, CLI Live Mode 및 OpenAI Planning 연결은 구현하지 않는다.

---

## 2. 최상위 기준 문서

작업 전에 반드시 다음 문서를 순서대로 읽는다.

1. `AIRA_PROJECT_CHARTER.md`
2. `DECISIONS.md`
3. `AIRA_PROJECT_AUDIT_REPORT.md`
4. `AIRA_CAPABILITY_MATRIX.md`
5. `AIRA_TARGET_ARCHITECTURE.md`
6. `AIRA_INTEGRATION_PLAN.md`
7. `AIRA_SEARCH_PROVIDER_DECISION.md`
8. `MASTER.md`
9. `ROADMAP.md`

충돌 시 상위 문서를 우선한다.

문서의 주장보다 실제 코드, 테스트 및 실행 결과를 우선하여 확인한다.

---

## 3. 작업 전 필수 감사

코드를 수정하기 전에 저장소에서 다음을 확인하고 간단히 보고한다.

### 3.1 기존 Search Domain

정확한 실제 위치와 계약을 확인한다.

- `ResearchSourceSearchTool`
- `ResearchSourceSearchResult`
- `ResearchSourceCandidate`
- `ResearchSearchQuery`
- 관련 Error 또는 Result Schema
- In-memory Search 구현
- 관련 Unit Test

### 3.2 설정 구조

확인할 것:

- `app/config.py`
- Pydantic Config Schema 패턴
- Environment Loader 패턴
- Secret이 `repr`, 로그 및 오류에 노출되지 않는 기존 방식
- Factory 패턴
- Dependency Injection 방식

### 3.3 HTTP 관련 구조

확인할 것:

- `httpx`가 실제 Runtime 코드에서 사용되는지
- Async 또는 Sync 코드 스타일
- Timeout, Retry 및 Error Mapping 기존 패턴
- `httpx.MockTransport` 또는 Fake Client 테스트 사용 가능성

### 3.4 패키지 구조

새 파일 위치를 추측하지 말고 기존 모듈 구조에 맞춰 결정한다.

감사 결과를 먼저 제시한 뒤 다음을 설명한다.

- 재사용 대상
- 신규 파일 후보
- 수정 파일 후보
- 테스트 파일 후보
- 구조적 위험
- 중복 추상화 가능성

---

## 4. 확정 Architecture 결정

첫 Provider:

```text
Tavily Search API
```

통합 방식:

```text
직접 REST 호출
+ 명시적 httpx Runtime Dependency
+ Provider-specific Adapter
+ 기존 ResearchSourceSearchTool Port 유지
```

환경변수:

```text
TAVILY_API_KEY
TAVILY_PROJECT_ID        # 선택
TAVILY_TIMEOUT_SECONDS   # 선택
```

초기 Endpoint:

```text
POST https://api.tavily.com/search
```

초기 요청 기본값:

```text
search_depth=basic
auto_parameters=false
include_answer=false
include_raw_content=false
include_images=false
include_usage=true
topic=general
```

인증:

```text
Authorization: Bearer <TAVILY_API_KEY>
Content-Type: application/json
```

선택 Header:

```text
X-Project-ID
X-Session-Id
```

API Key는 어떤 Trace, Artifact, 오류, Snapshot 또는 테스트 출력에도
노출하면 안 된다.

---

## 5. 구현 원칙

### 5.1 기존 Port 유지

Tavily 전용 객체가 Domain 또는 Application Layer로 누출되면 안 된다.

최종 Adapter는 기존 `ResearchSourceSearchTool` 계약을 구현해야 한다.

### 5.2 직접 의존성 선언

현재 `httpx`가 전이 의존성으로 설치되어 있더라도
`pyproject.toml`의 Runtime Dependency에 명시한다.

버전 상한이나 하한은 저장소의 기존 정책과 Python 3.12 호환성을 확인한 뒤
최소한으로 지정한다.

### 5.3 설정 분리

현재 전역 `app/config.py`가 `OPENAI_API_KEY`를 필수로 요구하므로
Tavily Search 설정을 그 구조에 무리하게 결합하지 않는다.

초기에는 Tavily 전용 Config Schema와 Loader 또는 Factory를 둔다.

설정 객체는 최소 다음을 검증해야 한다.

- API Key가 비어 있지 않음
- Base URL이 비어 있지 않음
- Timeout이 양수
- `max_results`가 허용 범위
- `search_depth`가 허용된 값
- Project ID는 선택

Secret 값 자체는 Validation Error에 포함하지 않는다.

### 5.4 Client Boundary

Unit Test에서 실제 네트워크를 사용하지 않도록 한다.

다음 중 저장소 스타일에 맞는 방법을 선택한다.

- 작은 Provider Client Protocol
- `httpx.Client` 주입
- `httpx.MockTransport`
- 기존 Fake Client 패턴

불필요한 추상화를 새로 만들지 않는다.

### 5.5 Sync/Async 결정

기존 Search Port와 Runtime 호출 방식에 맞춘다.

기존 Port가 Sync라면 첫 Adapter를 Async로 바꾸기 위해
광범위한 구조 변경을 하지 않는다.

---

## 6. 요청 Mapping

기존 `ResearchSearchQuery`의 실제 필드를 확인하여
지원 가능한 항목만 Tavily 요청으로 변환한다.

최소 Mapping:

```text
query text
→ query

maximum result limit
→ max_results

start date
→ start_date

end date
→ end_date

included domains
→ include_domains

excluded domains
→ exclude_domains
```

초기에는 지원되지 않는 필드를 조용히 버리지 않는다.

다음 중 하나를 적용한다.

- 명시적으로 미지원 처리
- 안전한 기본값
- Metadata에 변환되지 않았음을 기록

최대 결과 수는 다음 두 제한 중 더 작은 값을 사용한다.

```text
Query 요청값
Config 상한
```

---

## 7. 응답 Mapping

Tavily 응답에서 최소 다음을 검증한다.

Top-level:

- `query`
- `results`
- `response_time`
- `request_id`
- `usage.credits` 또는 공식 응답 형태

Result item:

- `title`
- `url`
- `content`
- `score`

AIRA Mapping:

```text
title
→ ResearchSourceCandidate.title

url
→ ResearchSourceCandidate URL 필드

content
→ snippet 또는 summary 필드

원래 배열 순서
→ rank

score
→ provider metadata

request_id
→ search result metadata

response_time
→ search result metadata

usage credits
→ usage/provider metadata
```

정확한 Domain 필드명은 기존 Schema를 확인하여 사용한다.

Domain Schema를 Tavily 응답에 맞추기 위해 임의로 크게 변경하지 않는다.

필수 정보가 기존 Schema에 없으면 최소한의 Metadata 확장 또는
Adapter 내부 결과 구조를 제안하고 근거를 설명한다.

---

## 8. URL 처리

최소 검증:

- `http`
- `https`

다음은 제외 또는 오류 처리한다.

- 빈 URL
- 잘못된 URL
- `file://`
- 지원하지 않는 Scheme

실제 HTTP Reader의 SSRF 검사는 다음 Work Item에서 수행한다.

Search Adapter에서는 최소 Scheme과 형식 검증까지만 담당한다.

---

## 9. 오류 Mapping

최소 다음을 구분한다.

- 설정 오류
- 요청 Validation 오류
- 400 Bad Request
- 401/403 Authentication 또는 Permission
- 429 Rate Limit
- Timeout
- Network Error
- 5xx Provider Error
- 잘못된 JSON
- 응답 Schema 오류
- 정상적인 빈 Result

429에서는 가능하면 `Retry-After`를 보존한다.

오류 객체 또는 예외에는 다음 정보를 안전하게 담는다.

- 오류 단계
- HTTP Status
- Provider
- retryable 여부
- Retry-After
- 안전한 메시지

다음은 절대 포함하지 않는다.

- API Key
- Authorization Header
- 전체 Request Header
- Secret이 포함될 수 있는 객체 repr

첫 작업에서는 자동 Retry Loop를 구현하지 않는다.

---

## 10. 권장 신규 Component

정확한 이름과 위치는 감사 후 확정한다.

예상 책임 단위:

```text
TavilySearchConfig
load_tavily_search_config
TavilySearchClient 또는 최소 HTTP Wrapper
TavilyResearchSourceSearchTool
Tavily Error Mapper
Tavily Response Schema
Factory
```

구조가 과도해지면 더 적은 Component로 통합해도 된다.

단, 다음 경계는 유지해야 한다.

```text
환경 설정
HTTP Provider 통신
Provider 응답 검증
AIRA Domain Mapping
```

---

## 11. 필수 Unit Test

실제 네트워크 없이 다음을 검증한다.

### Config

- 정상 Config
- API Key 없음
- 빈 API Key
- 잘못된 Timeout
- 잘못된 max_results
- Secret repr 비노출

### Request

- 기본 요청 Payload
- `search_depth=basic`
- `auto_parameters=false`
- `include_answer=false`
- `include_raw_content=false`
- `include_images=false`
- `include_usage=true`
- 최대 Result 상한
- 날짜 Mapping
- Domain Filter Mapping
- Authorization Header 생성
- 선택적 Project Header
- Secret 비노출

### Response

- 정상 Result 1개
- 정상 Result 여러 개
- Rank 보존
- Score Metadata 보존
- Request ID 보존
- Response Time 보존
- Usage Credit 보존
- 빈 Result
- 중복 URL 처리
- 잘못된 URL
- 필수 필드 누락
- 잘못된 JSON

### Error

- 400
- 401
- 403
- 429와 Retry-After
- Timeout
- Network Error
- 500
- 503
- Error Body에 Secret이 있어도 노출되지 않는지

### Compatibility

- 기존 In-memory Search 테스트 유지
- 기존 Search Port 계약 유지
- 기존 Offline Runtime 테스트 유지

---

## 12. 선택적 Smoke Test

실제 Smoke Test는 기본 pytest에 포함하지 않는다.

명시적 환경변수나 별도 Script로만 실행한다.

예:

```text
RUN_TAVILY_SMOKE_TEST=1
TAVILY_API_KEY=...
```

Smoke Test가 확인할 항목:

- 실제 검색 결과 1개 이상
- Provider `request_id`
- `response_time`
- 사용 Credit
- Result title과 URL
- API Key 출력 없음

실제 API Key를 입력하라고 사용자에게 요청하지 않는다.

`.env` 내용을 출력하지 않는다.

Smoke Test를 구현하더라도 자동 실행하지 않는다.

---

## 13. 이번 작업에서 금지

- HTTP/HTML Reader 구현
- Source Artifact Writer 구현
- Concrete Live Research Runner 구현
- CLI Live Mode 구현
- OpenAI Planning 연결
- Tavily Extract API
- Tavily Crawl API
- Tavily Research API
- Tavily SDK 추가
- 복수 Search Provider
- 자동 Provider Fallback
- 자동 Retry Loop
- 기존 Offline Runtime 제거
- 기존 Search Domain 대규모 재설계
- 테스트 통과를 위한 기존 테스트 삭제 또는 완화

---

## 14. 검증 명령

정확한 테스트 경로는 구현 후 실제 파일명으로 제시한다.

최소 실행:

```bash
pytest <신규 관련 테스트> -q
ruff check <신규 및 수정 경로>
git diff --check
```

그 후 전체 검증:

```bash
pytest -q
ruff check app tests scripts examples
git diff --check
```

기준선:

```text
4088 passed
All checks passed
```

새 테스트 추가로 총 테스트 수는 증가할 수 있다.

---

## 15. Codex 결과 보고 형식

작업 후 다음 순서로 보고한다.

### A. 감사 결과

- 확인한 기존 파일
- 재사용한 계약
- 새 파일 위치를 선택한 이유

### B. 구현 요약

- 신규 파일
- 수정 파일
- 각 Component 책임

### C. Request/Response Mapping

- AIRA → Tavily
- Tavily → AIRA

### D. 오류와 Secret 보호

- 오류 분류
- Retry 가능 여부
- API Key 비노출 방법

### E. 테스트 결과

- 관련 테스트
- 전체 pytest
- Ruff
- `git diff --check`
- 실제 Smoke Test 실행 여부

### F. Git Diff 요약

- 변경 파일 목록
- 주요 변경
- 의도하지 않은 변경 여부

### G. 미완료와 다음 작업

이번 작업 범위 밖의 항목을 명확히 기록한다.

---

## 16. 작업 중단 조건

다음 중 하나가 확인되면 임의 구현하지 말고 보고한다.

- 기존 Search Port가 Tavily 결과를 표현할 수 없음
- Domain 변경이 광범위하게 필요함
- `httpx` 추가가 기존 의존성 정책과 충돌함
- 현재 Sync/Async 구조 때문에 대규모 변경이 필요함
- Secret 보호를 기존 구조에서 보장하기 어려움
- 문서와 실제 코드가 중대한 충돌을 보임
- 예상 외로 이미 Tavily 또는 다른 실제 Search Adapter가 존재함

작은 명명 차이, 파일 위치 선택 또는 테스트 Fixture 구성은
기존 스타일을 따라 합리적으로 결정하고 작업을 계속한다.
