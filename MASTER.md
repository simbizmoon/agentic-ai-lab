# Agentic AI Lab — MASTER

## 1. 문서의 역할

본 문서는 Agentic AI Lab 전체 프로젝트의 운영·개발·학습 원칙을 정의한다.

AIRA의 제품 목표와 최상위 범위는 `AIRA_PROJECT_CHARTER.md`를 기준으로 하며,
구체적인 확정 결정과 변경 이력은 `DECISIONS.md`에 기록한다.

본 문서는 다음을 관리한다.

- Agentic AI Lab 프로젝트 운영 원칙
- ChatGPT, Codex 및 사용자의 역할
- 기존 코드 감사와 재사용 원칙
- 점진적 Single-Agent 통합 방식
- Tool, RAG, Memory, Skill 및 Multi-Agent 적용 원칙
- LLM Provider와 비용 관리 원칙
- Work Item, 테스트, 평가 및 변경 관리
- 프로젝트 문서 체계

기존 문서 또는 코드가 상위 기준 문서와 충돌하는 경우 임의로 수정하지 않는다.

다음 순서로 처리한다.

1. 충돌 내용 확인
2. 실제 코드와 테스트 상태 확인
3. 영향 분석
4. 수정·유지·보류·대체안 제시
5. 사용자 승인
6. `DECISIONS.md`에 이력 기록

---

## 2. 프로젝트 정의

### 2.1 프로젝트명

Agentic AI Lab

### 2.2 최종 제품명

AIRA — Agentic Intelligence Research Assistant

### 2.3 프로젝트 목적

본 프로젝트는 Agentic AI의 핵심 이론과 구현 방법을 실제 개발을 통해
학습하고, 최종적으로 인터넷 공개 자료와 로컬 문서를 통합 조사하는
실용적인 AI Research Agent를 완성하는 것을 목적으로 한다.

AIRA는 사용자의 관심 분야, 연구주제 또는 선행특허 조사 요청을 바탕으로
관련 자료를 검색·수집하고, 자료의 관련성·중요도·신뢰도·최신성 및
증거 수준을 평가한다.

수집된 자료를 정리·요약·비교·분석하고, 자료 간 일치점·차이점·충돌,
위험요소 및 시사점을 도출한다.

최종적으로 AIRA는 다음을 포함한 연구 리포트를 생성해야 한다.

- 핵심 결론
- 중요 자료와 평가 결과
- 근거 기반 Claim
- Supporting Evidence
- Contradicting Evidence
- 추적 가능한 Citation
- 위험요소와 불확실성
- 근거 기반 제안사항
- 추가 조사 과제
- 조사 방법, 범위, 비용 및 한계

AIRA의 상세 제품 목표는 `AIRA_PROJECT_CHARTER.md`를 최상위 기준으로 한다.

---

## 3. 목표 사용자 흐름

AIRA의 기본 사용자 흐름은 다음과 같다.

```text
Research Request
→ Request Understanding
→ LLM Research Planning
→ Tool Selection
→ Internet and Local Source Search
→ Source Reading and Parsing
→ Retrieval and Evidence Extraction
→ Source Importance and Quality Evaluation
→ Organization, Summary and Comparison
→ Evidence Sufficiency Evaluation
→ Limited Replanning and Additional Search
→ Claim and Recommendation Generation
→ Claim-Evidence-Citation Validation
→ Final Report
→ Usage, Cost, Trace and Limitation Recording
```

AIRA는 단순 검색기, 단순 요약기 또는 고정된 문서 처리 Pipeline을
최종 제품으로 정의하지 않는다.

AIRA는 사용자의 연구와 의사결정을 지원하는 분석·제안형
AI Research Agent를 목표로 한다.

---

## 4. 단계적 제품 범위

### 4.1 초기 Single-Agent Core

처음부터 모든 기능을 완성하지 않는다.

먼저 실제로 처음부터 끝까지 동작하는 최소 LLM 기반
Single Research Agent를 완성한다.

초기 Core의 필수 기능은 다음과 같다.

1. 연구 요청 구조화
2. LLM 기반 조사계획 생성
3. 제한된 Tool 선택과 실행
4. 최소 하나의 인터넷 검색 Provider
5. 웹페이지 원문 읽기
6. 로컬 TXT 및 Markdown 검색과 읽기
7. 기존 코드로 가능한 기본 PDF 처리
8. 기본 Retrieval
9. Evidence 추출
10. Source 관련성·중요도·신뢰도 기본 평가
11. Evidence 충분성 평가
12. 제한된 재검색 또는 Replanning
13. Claim과 Citation 연결
14. 자료 정리·요약·비교·기본 분석
15. 근거 기반 제안사항 생성
16. Markdown 및 JSON 보고서 저장
17. Usage, Token 및 비용 기록
18. Agent Trace와 종료 이유 기록
19. 최대 반복, Tool 호출 및 비용 제한
20. 실제 연구 예제를 이용한 E2E 검증

초기 버전은 기능의 완벽성보다 전체 흐름이 실제로 작동하는지를 우선한다.

그러나 구현 편의를 이유로 최종 목표를 로컬 문서 검색기나 결정론적
Pipeline으로 축소하지 않는다.

### 4.2 점진적 확장 기능

초기 Core가 안정된 이후 실제 필요성과 평가 결과에 따라 다음 기능을
단계적으로 추가한다.

- PDF 처리 고도화
- HWP 및 HWPX
- DOCX, HTML, CSV, XLSX 및 PPTX
- Hybrid RAG
- Embedding Search
- Reranking
- 학술자료 전문 검색
- 특허 전문 검색
- 공식자료 우선 검색
- Source 품질 평가 고도화
- Evidence 교차검증
- 상충 자료 분석
- Working Memory
- Long-term Memory
- Query, Source, Parsing 및 Embedding Cache
- 전문 Research Skill
- 선행특허 전문 Workflow
- 다른 상용 LLM Provider
- OpenAI-compatible API
- Ollama 및 로컬 LLM
- Application Persistence
- Background Job
- FastAPI 및 Web UI
- MCP 또는 ChatGPT App 연결
- Multi-Agent 비교 실행

### 4.3 현재 비목표

초기 Single-Agent Core가 안정되기 전에는 다음을 우선 구현하지 않는다.

- Agent 수 증가 목적의 Multi-Agent
- 완전 자율 연구 조직
- 대규모 SaaS 플랫폼
- 다중 사용자 협업 제품
- 복잡한 조직 및 RBAC
- Redis 또는 RabbitMQ 기반 분산 Queue
- Kubernetes
- 복수 서버 Worker Cluster
- 고가용성 Database
- 대규모 Observability Platform
- 상용 수준 Web UI
- 로그인 또는 유료벽 우회
- 완전한 범용 웹 크롤러
- 모든 검색 Provider 동시 지원
- 외부 배포용 Plugin 패키지
- 추가적인 암호화·분산 신뢰 하위 시스템

필요성이 확인되면 별도 Work Item과 결정으로 검토한다.

---

## 5. 기존 학습 및 구현 자산

프로젝트 과정에서 다음 내용을 학습하거나 구현하였다.

- 생성형 AI와 LLM
- OpenAI API
- OpenAI Responses API
- OpenAI Python SDK
- Structured Outputs
- Function Calling과 Tool Calling
- Tool Definition
- Tool Registry
- Tool Execution
- Workflow와 State
- Retry와 Timeout
- RAG
- Document Parsing
- Chunking
- Keyword Search
- Embedding
- Vector Retrieval
- Hybrid Retrieval
- Citation Grounding
- Memory와 State
- Planning Agent
- Replanning
- Agent Loop
- Single Research Agent
- 제한된 Multi-Agent Research
- Evals
- Guardrails
- Tracing
- Application Service
- Persistence
- Retry, Cancellation 및 Background Job
- Token Usage와 API 비용 계산
- Docker와 재현 가능한 실행환경

위 항목은 모두 신규 구현 대상이 아니라 Existing Capability Audit의 대상이다.

기존 코드의 존재 여부, 테스트 여부, 실제 Runtime 연결 여부 및
실제 API 또는 자료를 사용한 검증 여부를 구분해야 한다.

---

## 6. 핵심 개발 기술

### 6.1 기본 기술

- Ubuntu
- Python 3.12
- Pydantic
- Git과 GitHub
- pytest
- Ruff
- Codex
- Docker

### 6.2 초기 기준 LLM 기술

- OpenAI Responses API 또는 OpenAI Python SDK
- Structured Outputs
- Tool Calling
- Usage 수집

초기에는 기존 OpenAI 관련 구현을 최대한 재사용하여
Single-Agent 기준선을 빠르게 완성할 수 있다.

### 6.3 필요 시 사용하는 기술

- FastAPI
- SQLite
- PostgreSQL
- OpenAI Agents SDK
- 다른 상용 LLM API
- OpenAI-compatible API
- Ollama
- 로컬 LLM Runtime
- MCP
- ChatGPT App 또는 Plugin 형태의 통합

기술 자체를 학습했다는 이유만으로 제품 Runtime에 모두 적용하지 않는다.

---

## 7. 핵심 설계 원칙

### 7.1 실용성 우선

새 기능은 다음 질문에 명확히 답할 수 있을 때만 추가한다.

- 실제 사용자 흐름에 필요한가?
- 현재 구현보다 사용성이 분명히 좋아지는가?
- 품질, 비용 또는 처리시간이 개선되는가?
- 기존 저장소에 동일하거나 유사한 기능이 이미 구현되어 있는가?
- 테스트와 운영 복잡도 증가를 감당할 가치가 있는가?
- 실제 Eval에서 개선을 측정할 수 있는가?

필요성과 개선 효과가 불명확하면 보류한다.

### 7.2 작게 시작하지만 최종 목표는 축소하지 않는다

통합 순서는 다음을 기본으로 한다.

```text
Existing Capability Audit
→ Provider-independent LLM Foundation
→ Minimal Tool-using Research Agent
→ Internet and Local Source Integration
→ Basic Retrieval and Evidence
→ Limited Agent Loop
→ Citation-grounded Report
→ Hybrid RAG
→ Advanced Verification
→ Memory and Cache
→ Multi-Agent Experiment
→ Productization
```

한 번에 모든 기능을 연결하지 않는다.

각 단계는 독립적으로 실행·테스트·평가할 수 있어야 한다.

### 7.3 기본 실행 경로는 Single Research Agent

AIRA의 기본 실행 경로는 Single Research Agent로 유지한다.

기본 Agent는 최소한 다음을 수행해야 한다.

- LLM 기반 조사계획
- Tool 선택
- 실제 인터넷 또는 로컬 자료 검색
- Tool 결과 Observation
- Agent State 갱신
- Evidence 충분성 평가
- 제한된 Replanning
- 완료 또는 보류 판단
- Claim 및 보고서 생성

Multi-Agent는 다음 조건을 만족할 때만 사용한다.

- 역할 분리가 명확히 유리함
- 동일한 Evaluation Dataset에서 품질 향상이 확인됨
- 비용과 지연 증가가 허용 범위임
- Context 관리 또는 병렬 처리에 실질적 이점이 있음

Agent 수의 증가 자체를 발전으로 간주하지 않는다.

### 7.4 LLM은 판단하고 코드는 실행·기록·검증한다

LLM은 다음에 사용한다.

- 질문 이해
- 연구계획
- Query 생성
- Source 관련성 판단
- Evidence 의미 해석
- 자료 비교
- 충돌 분석
- Claim 생성
- 제안사항 생성
- 보고서 합성

결정론적 코드는 다음을 담당한다.

- Tool 실행
- URL Fetch
- 파일 읽기
- Parsing
- Chunking
- Metadata 보존
- 중복 제거
- 페이지 및 줄 위치 계산
- Citation ID 연결
- 상태 전이
- 권한 검사
- 호출 횟수 제한
- 비용 계산
- 결과 무결성 검증
- JSON 저장
- Trace 기록

핵심 원칙:

> LLM은 판단하고, 코드는 실행·기록·검증한다.

### 7.5 기존 기능을 우선 감사하고 재사용한다

새 Schema, Repository, Service, Provider 또는 추상화를 만들기 전에
기존 기능으로 해결 가능한지 확인한다.

각 기능은 다음 상태를 구분한다.

- Implemented
- Tested
- Runtime-connected
- Production-ready

신규 구현 전 순서는 다음과 같다.

```text
기존 코드 탐색
→ 관련 테스트 확인
→ 실제 Runtime 연결 확인
→ 실제 API 또는 자료 검증 확인
→ 재사용 가능성 평가
→ Adapter 검토
→ 부족한 부분만 수정
→ 재작성은 최후 선택
```

재작성은 다음 조건에서만 허용한다.

- 기존 구조가 Target Architecture와 호환되지 않음
- 심각한 품질 또는 보안 문제가 있음
- 재사용 비용이 재작성보다 명확히 큼
- 테스트로 재사용 불가능함이 확인됨

재작성·보류·폐기 결정은 `DECISIONS.md` 또는 Audit Report에 기록한다.

### 7.6 특정 LLM Provider에 종속되지 않는다

초기에는 OpenAI Responses API 또는 OpenAI SDK를 사용할 수 있다.

그러나 다음은 OpenAI 전용 객체에 직접 의존하지 않는다.

- Domain Model
- Research Pipeline
- Tool System
- RAG
- Evidence
- Claim
- Citation
- Recommendation
- Report
- Agent State

공통 LLM Provider 계약과 Provider별 Adapter를 사용한다.

후보 Provider:

- OpenAI Responses API
- 다른 상용 LLM API
- OpenAI-compatible API
- Ollama
- 로컬 LLM Runtime
- Deterministic Test Provider

모델 또는 Provider 교체는 동일한 Evaluation Dataset에서 품질, 비용 및
처리시간을 비교한 후 결정한다.

### 7.7 비용은 Agent 실행 제약으로 관리한다

비용은 실행 후 표시만 하는 정보가 아니다.

기존 Usage 및 비용 계산 코드를 우선 감사하고 다음 제한을
Agent Runtime에 적용할 수 있어야 한다.

- 최대 LLM 호출
- 최대 Search 호출
- 최대 Tool 호출
- 최대 Source
- 최대 Chunk
- 최대 입력 Token
- 최대 출력 Token
- 최대 반복 횟수
- 최대 실행시간
- 실행당 비용 상한
- Stage별 Usage 및 Latency 관측

Budget 초과 시 다음 중 하나를 수행한다.

- 실행 중단
- 범위 축소
- 저가 모델로 전환
- 사용자 승인 요청

검색한 모든 문서 전체를 LLM에 전달하지 않는다.

기본 비용 최적화 흐름:

```text
검색결과
→ 중복 제거
→ Metadata 및 Keyword 1차 선별
→ 중요 Source 원문 수집
→ Parsing
→ Chunking
→ Retrieval
→ Reranking
→ 관련 Evidence만 LLM 전달
```

다음 Cache를 검토한다.

- Query Cache
- Source Cache
- Parsing Cache
- Embedding Cache
- 동일 실행 결과 Cache

### 7.8 중요한 작업은 인간이 승인한다

다음 작업은 사용자 승인 후 수행한다.

- GitHub Push
- 외부 이메일 발송
- 데이터 삭제
- 운영 서버 배포
- 운영 데이터베이스 변경
- 유료 LLM 또는 검색 API 최초 활성화
- 실행당 비용 상한 증가
- 비공개 로컬 문서의 외부 LLM 전송
- 개인정보 또는 민감정보의 외부 전송
- 새로운 외부 데이터 Provider 연결
- 허용된 로컬 파일 접근 범위 확대
- 보안 설정 또는 보안정책 변경

### 7.9 테스트 수보다 실제 사용자 흐름을 우선한다

테스트는 중요하지만 테스트 수 자체가 목표가 아니다.

모든 신규 테스트는 다음 중 하나를 보호해야 한다.

- 실제 사용자 흐름
- 중요한 데이터 무결성
- Agent 종료 조건
- 비용 및 호출 한도
- Claim과 Citation 관계
- 재현 가능한 실패 복구
- 핵심 품질 기준
- Provider 교체 가능성
- Regression 방지


### 7.10 Observability는 최적화보다 먼저 측정한다

성능, 비용 또는 Agent Loop를 최적화하기 전에 실제 Runtime의 병목을 측정한다.

최소 관측 항목은 다음과 같다.

- 전체 실행시간
- Search Provider 호출 수·Credit·Latency
- Source Reading 시간
- Evidence Semantic Evaluation 호출 수·Token·시간
- Claim Generation 호출 수·Token·시간
- Citation Verification 호출 수·Token·시간
- Claim Relevance 호출 수·Token·시간
- Answer Coverage 호출 수·Token·시간
- Replanning 여부와 추가 라운드 비용

관측값은 품질 정책 자체를 변경하지 않는 진단 정보로 사용한다.
결정론적 Baseline의 재현성을 깨뜨리는 Wall-clock 값은 기본 결과에 강제로
포함하지 않고, Live Runtime과 같이 필요한 실행 경로에서 명시적으로 수집한다.

최적화는 측정 결과에서 가장 큰 비용과 지연을 만드는 단계부터 수행한다.

---

## 8. Tool, RAG, Memory, Skill 및 Multi-Agent 원칙

### 8.1 Tool

Tool은 Agent가 외부 환경을 검색, 읽기, 분석 또는 저장하기 위해
호출하는 개별 실행 기능이다.

각 Tool은 다음을 정의해야 한다.

- 이름
- 설명
- 입력 Schema
- 출력 Schema
- 권한
- 비용 유형
- Timeout
- Retry 정책
- 오류 형식
- 최대 실행 횟수
- Trace 정책
- 민감정보 처리 정책

초기 Tool 후보:

- `web_search`
- `fetch_web_page`
- `fetch_web_pdf`
- `search_local_documents`
- `read_text_document`
- `read_markdown_document`
- `read_pdf_document`
- `retrieve_chunks`
- `extract_evidence`
- `evaluate_source_quality`
- `validate_citation`
- `save_research_report`
- `save_research_result`

모든 Tool을 한꺼번에 구현하지 않는다.

초기 Agent Loop에 필요한 최소 Tool부터 연결한다.

### 8.2 RAG

AIRA의 RAG는 인터넷 자료와 로컬 문서를 동일한 Research Document 구조로
처리하는 방향을 따른다.

기본 흐름:

```text
Source Discovery
→ Document Fetching
→ Parsing
→ Metadata Normalization
→ Chunking
→ Keyword Search
→ Embedding Search
→ Hybrid Retrieval
→ Reranking
→ Evidence Selection
```

초기에는 기존 RAG 구현을 감사하고, 가장 작은 연결로 시작한다.

Hybrid RAG는 실제 Retrieval 품질과 비용 개선이 확인될 때 기본 경로로
채택한다.

### 8.3 Memory

초기에는 하나의 연구 실행 내부 Working State를 우선 사용한다.

상태 후보:

- Research Request
- Research Plan
- Tasks
- Search Queries
- Tool Calls
- Search Results
- Visited Sources
- Documents
- Chunks
- Evidence
- Claims
- Citations
- Conflicts
- Recommendations
- Usage
- Cost
- Iteration Count
- Termination Reason

장기 Memory는 다음 필요가 확인된 이후 도입한다.

- 이전 조사 결과 재사용
- 동일 Source 재다운로드 방지
- Parsing 및 Embedding 재사용
- 프로젝트 지식 축적
- 중복 조사 방지
- 이전 Claim과 신규 Claim 비교

민감정보는 자동으로 장기 Memory에 저장하지 않는다.

### 8.4 Skill

Skill은 검증된 여러 Tool과 판단 절차를 결합한 재사용 가능한 연구 방법이다.

초기 Skill 후보:

- General Web Research
- Official Source Research
- Academic Literature Review
- Local Document Analysis
- Cross-source Verification
- Claim-Evidence Audit
- Conflicting Evidence Analysis
- Technical Trend Report
- Patent Prior-art Analysis
- Project Document Consistency Audit

Tool과 Single-Agent Runtime이 안정된 이후 Skill을 정형화한다.

Skill 구현 자체를 핵심 Runtime보다 우선하지 않는다.

### 8.5 Plugin, App 및 MCP

Plugin, ChatGPT App 및 MCP 연결은 초기 Single-Agent Runtime의
선행조건이 아니다.

먼저 독립 실행 가능한 AIRA Runtime을 완성한다.

향후 다음 구조를 검토할 수 있다.

```text
ChatGPT
→ AIRA App 또는 MCP Client
→ Local AIRA Runtime
→ Internet and Local Tools
→ Research Result
```

### 8.6 Multi-Agent

Multi-Agent는 Single-Agent 평가 후 실험한다.

후보 역할:

- Research Coordinator
- Web Search Specialist
- Local Document Specialist
- Patent Search Specialist
- Evidence Analyst
- Claim Critic
- Verification Agent
- Report Writer

다음 중 하나 이상의 개선이 입증될 때만 채택한다.

- Evidence Coverage
- Citation Accuracy
- Contradiction Detection
- 복잡한 분석 품질
- Context 관리
- 병렬 처리시간
- 비용 대비 성능
- 실패 격리

---

## 9. Existing Capability Audit

초기 최우선 작업은 신규 기능 개발이 아니라 Existing Capability Audit이다.

Audit 대상:

- OpenAI Responses API
- OpenAI Python SDK
- Structured Outputs
- Tool Calling
- Tool Registry
- Tool Execution Loop
- Workflow와 State
- Retry와 Timeout
- RAG
- Document Parsing
- Chunking
- Embedding
- Retrieval
- Reranking
- Citation Grounding
- Memory
- Planning Agent
- Replanning
- Single Research Agent
- Multi-Agent
- Evals
- Guardrails
- Tracing
- Usage 수집
- Token 계산
- 모델 가격
- API 비용 계산
- Budget 제한
- Application Service
- Persistence
- Retry
- Cancellation
- Background Job

Audit은 최소한 다음 표를 작성해야 한다.

```text
Component
Location
Purpose
Implemented
Tested
Runtime-connected
Production-ready
Uses real API
External dependency
Reusable
Integration effort
Decision
```

Audit 결과는 다음 중 하나로 분류한다.

- 그대로 재사용
- Adapter 추가
- 부분 수정
- 재작성
- 보류
- 폐기 후보

코드 파일이 존재한다는 사실만으로 기능이 실제 구현되었다고 판단하지 않는다.

---

## 10. Work Item 운영

기존 Phase 0~13은 완료된 학습 및 구현 이력으로 유지한다.

향후 제품 통합 작업은 신규 Phase 번호보다
`AIRA_PROJECT_CHARTER.md`의 Stage와 Integration Work Item으로 관리한다.

Work Item 수를 임의로 제한하지 않는다.

하나의 작은 Schema 또는 Error Class만을 위한 독립 Work Item은
원칙적으로 만들지 않는다.

각 Work Item은 다음 중 하나를 만들어야 한다.

- 사용자가 실행할 수 있는 기능
- 기존 코드 감사 결과
- 통합 결과
- 검증 가능한 기술 결정
- 품질 또는 비용 비교 결과
- 문서와 코드의 정합성 개선

기본 절차:

```text
1. 실제 사용 문제 정의
2. Existing Capability Audit
3. 재사용 또는 Adapter 가능성 판단
4. 최소 통합안 설계
5. 사용자 승인
6. 구현
7. Unit Test
8. Integration Test
9. 실제 연구 E2E
10. 품질·비용·처리시간 평가
11. 채택·수정·보류·제거 결정
12. 문서화와 Commit
```

각 Work Item에는 다음을 명확히 한다.

- 목적
- 관련 기준 문서
- 현재 확인된 코드 상태
- 재사용 대상
- 수정 허용 범위
- 수정 금지 범위
- Acceptance Criteria
- 실행할 테스트
- 비용 및 보안 영향
- 완료 보고 형식

---

## 11. ChatGPT의 역할

### 11.1 프로젝트 총괄

ChatGPT의 `Agentic AI Lab` 프로젝트는 전체 프로젝트의 지휘 공간으로
사용한다.

ChatGPT는 다음을 담당한다.

- 최상위 목표 보존
- 기준 문서 관리
- Capability Audit 총괄
- Target Architecture 설계
- 기술적 의사결정
- 작업 순서 관리
- Tool 및 Skill 설계
- Codex 작업지시서 작성
- 코드 변경 결과 검토
- 테스트 및 Git Diff 해석
- 위험과 우선순위 관리
- 장기 프로젝트 문맥 유지

ChatGPT는 실제 코드 상태를 추측하지 않는다.

판단에 필요한 경우 실제 파일, 테스트 결과, 실행결과 및 Git Diff를
근거로 사용한다.

### 11.2 교수

- 핵심 개념을 초보자 수준으로 설명한다.
- 세부 구현보다 전체 구조와 사용 목적을 먼저 설명한다.
- 사용자가 결과를 직접 이해하고 판단하도록 돕는다.
- 기존 학습 내용이 실제 Runtime과 어떻게 연결되는지 설명한다.

### 11.3 시스템 설계자

- 최소 구조를 우선 제안한다.
- 최종 목표를 축소하지 않으면서 단계적 구현을 설계한다.
- 기능 증가가 사용자 가치로 연결되는지 평가한다.
- 과도한 추상화와 범위 확장을 차단한다.
- Provider 독립성, 비용 및 보안을 함께 고려한다.

### 11.4 Codex 감독

- Codex 작업 목적과 금지사항을 명확히 한다.
- 신규 구현 전에 기존 코드 감사 여부를 확인한다.
- Responses API, Tool, RAG, Memory, Planning 및 Cost 관련 기존 코드의
  재사용 여부를 확인한다.
- Diff, 테스트 및 실제 실행 결과를 검토한다.
- Codex 출력이 요구사항과 기준 문서를 충족하는지 독립적으로 검증한다.

### 11.5 평가자

다음을 함께 평가한다.

- 개념 이해
- 설계 판단
- 실제 사용 가능성
- 검색 및 Retrieval 품질
- Evidence Coverage
- Citation Accuracy
- Claim Support
- 제안사항의 근거성
- 비용과 지연
- 유지관리 가능성

---

## 12. Codex의 역할

Codex는 실제 코드 구현과 로컬 저장소 작업의 주 실행 도구다.

주요 역할:

- 저장소 탐색
- 기존 기능 감사
- 코드 작성
- Adapter 작성
- Runtime Integration
- 테스트 작성
- Refactoring
- Ruff 수정
- Git Diff 작성
- 문서와 코드의 정합성 확인

Codex의 결과는 자동으로 정답으로 간주하지 않는다.

ChatGPT와 사용자가 다음을 검토한다.

- 요구사항 충족
- 기존 코드 재사용
- 중복 구현 여부
- 테스트 결과
- 실제 실행 결과
- 보안 영향
- 비용 영향
- Git Diff

Codex Usage Limit이 소진된 기간에는 ChatGPT에서 다음을 준비한다.

- 프로젝트 문서 정리
- Capability Audit 설계
- Target Architecture
- Tool 및 Skill Registry
- Eval 기준
- Codex용 Work Item Prompt

---

## 13. 사용자의 역할

사용자는 직접 학습하고 판단하는 개발자이며 최종 제품 사용자다.

사용자는 다음을 수행한다.

1. 핵심 개념을 자신의 말로 설명한다.
2. 명령어와 실제 사용 흐름을 직접 실행한다.
3. 오류와 결과를 확인한다.
4. 기능이 실제로 유용한지 판단한다.
5. 불필요한 기능은 보류하거나 제거한다.
6. Codex Diff와 테스트를 검토한다.
7. 배포와 비용 증가 작업을 승인한다.
8. 외부 LLM에 전송할 로컬 문서 범위를 승인한다.
9. 실행당 비용 상한과 검색 범위를 결정한다.
10. 실제 연구 결과의 유용성과 제안사항의 타당성을 평가한다.
11. 핵심 목표 또는 Architecture 변경을 승인한다.

---

## 14. 테스트, Evals 및 Guardrails

### 14.1 테스트

다음 계층을 구분한다.

- Unit Test
- Integration Test
- E2E Test
- Regression Test
- 실제 외부 API Smoke Test

Fake 또는 Stub 테스트 통과만으로 Production-ready라고 판단하지 않는다.

### 14.2 Evals

핵심 평가 항목:

- Search Relevance
- Retrieval Relevance
- Evidence Coverage
- Source Quality
- Citation Accuracy
- Claim Support
- Contradiction Detection
- Hallucination Rate
- Recommendation Grounding
- Report Completeness
- Trace Completeness
- Latency
- Stage별 실행시간
- LLM 및 Semantic Evaluator 호출 수
- Token Usage
- API Cost
- Reproducibility

초기 Golden Dataset 후보:

- Agentic AI 기술 동향
- 특정 기술 연구주제
- 공식 규정 조사
- 로컬 문서 비교
- 선행특허 조사

Single-Agent와 Multi-Agent, 외부 LLM과 로컬 LLM은 가능한 경우
동일한 Dataset으로 비교한다.

### 14.3 Guardrails

초기 Guardrail 후보:

- 빈 연구 요청 차단
- 과도하게 넓은 범위 경고
- 허용되지 않은 로컬 경로 접근 차단
- URL Scheme 검증
- 내부 네트워크 주소 접근 제한
- 웹페이지 Prompt Injection 방어
- Tool Permission 검사
- 최대 반복 횟수
- 최대 Tool 및 Search 호출
- 최대 Source 및 Chunk
- 최대 Token
- 최대 비용
- Citation 없는 핵심 Claim 차단
- 존재하지 않는 Evidence 참조 차단
- Claim과 Citation ID 무결성 검사
- 외부 전송 전 민감정보 확인
- 비용 증가 작업 승인 정책
- 데이터 삭제 승인 정책

---

## 15. 문서 체계

### 15.1 제품 목표 및 Architecture

1. `AIRA_PROJECT_CHARTER.md`
2. 향후 작성할 `AIRA_TARGET_PRODUCT_SPEC.md`
3. 향후 작성할 `AIRA_TARGET_ARCHITECTURE.md`
4. `DECISIONS.md`
5. 향후 작성할 `AIRA_PROJECT_AUDIT_REPORT.md`
6. 향후 작성할 `AIRA_INTEGRATION_PLAN.md`

### 15.2 프로젝트 운영 및 학습

1. `MASTER.md`
2. `ROADMAP.md`
3. `CURRICULUM.md`
4. `AGENTS.md`
5. `README.md`
6. `LEARNING_LOG.md`
7. 기존 Phase 및 Lesson 문서

### 15.3 사실 확인 우선순위

현재 구현 상태를 판단할 때에는 다음을 우선한다.

1. 실제 코드
2. 테스트
3. 실제 실행 결과
4. Git Diff와 Commit
5. Audit Report
6. 설명 문서

문서에 구현되었다고 적혀 있다는 이유만으로 실제 구현 상태를 단정하지 않는다.

### 15.4 Stage 번호와 현재 상태의 단일 기준

AIRA의 공식 제품 Stage 번호는 `AIRA_PROJECT_CHARTER.md`와 `ROADMAP.md`의
숫자형 `Stage 0`부터 `Stage 11`까지를 사용한다.

과거 문서에 존재하는 `Phase 0~13`, `Stage A~I`, Local/Multi-Agent Phase 번호는
학습·실험·재설계의 역사적 checkpoint다. 현재 제품 Stage를 대체하지 않는다.

현재 위치와 다음 실행 순서의 단일 기준은 `ROADMAP.md`다.

`AIRA_PROJECT_STATUS_AND_ROADMAP.md`는 장기 상태 기록과 historical snapshot으로
사용하며, 해당 문서의 과거 `Stage A~I` 또는 과거 "다음 단계" 표현이
`ROADMAP.md`의 최신 authoritative section과 충돌하면 `ROADMAP.md`를 우선한다.

---

## 16. 변경 관리

- AIRA의 핵심 제품 목표는 `AIRA_PROJECT_CHARTER.md` 승인 없이 변경하지 않는다.
- 기존 Phase 0~13은 완료 이력으로 보존한다.
- 새로운 제품 통합 작업은 Stage와 Work Item으로 관리한다.
- 주요 설계 결정 변경은 `DECISIONS.md`에 이력을 남긴다.
- 로드맵 변경 시 이유와 영향을 기록한다.
- 실제 필요가 없는 기능은 보류한다.
- 기존 기능을 확장하기 전에 실제 사용 검증을 수행한다.
- 구현 편의를 이유로 최종 제품 목표를 축소하지 않는다.
- 최신 기술은 실제 필요가 있는 경우 공식 자료와 평가 결과를 근거로 반영한다.
- Provider, 검색 서비스 또는 가격 변경 시 기준일과 영향을 기록한다.

핵심 목표 또는 Architecture를 변경할 때에는 다음을 기록한다.

- 변경 이유
- 변경 전 내용
- 변경 후 내용
- 기존 코드 영향
- 문서 영향
- 작업량 영향
- 비용 영향
- 보안 및 개인정보 영향
- 사용자 승인 일자

---

## 17. 단계별 성공 기준

### 17.1 초기 Single-Agent Core 완료 조건

초기 Core는 다음을 만족해야 한다.

1. LLM 기반 연구계획을 생성한다.
2. 최소 하나의 인터넷 검색 Tool을 실행한다.
3. 웹페이지 원문을 읽는다.
4. 로컬 TXT 및 Markdown 자료를 검색하고 읽는다.
5. 기존 코드로 가능한 기본 PDF를 처리한다.
6. Source를 선택하고 Evidence를 추출한다.
7. Source의 관련성·중요도·신뢰도를 기본 평가한다.
8. Evidence 부족 시 제한된 재검색 또는 Replanning을 수행한다.
9. Claim과 Citation을 연결한다.
10. 자료를 정리·요약·비교·기본 분석한다.
11. 근거 기반 제안사항을 생성한다.
12. Markdown 및 JSON 보고서를 저장한다.
13. Usage, Token, 비용 및 Trace를 기록한다.
14. 최대 반복, Tool 호출 및 비용 한도가 실제로 작동한다.
15. 실제 연구 예제로 E2E를 검증한다.
16. 관련 pytest, Ruff 및 Git Diff 검사를 통과한다.

### 17.2 통합 AIRA 완료 조건

통합 AIRA는 다음을 만족해야 한다.

1. 인터넷과 로컬 자료를 함께 조사한다.
2. TXT, Markdown, PDF, HWP 및 HWPX를 처리한다.
3. 인터넷 자료와 로컬 문서를 공통 Research Document 구조로 관리한다.
4. Hybrid RAG를 사용한다.
5. 관련성·중요도·신뢰도·최신성 및 증거 수준을 평가한다.
6. 자료를 정리·요약·비교·분석한다.
7. Evidence를 교차검증한다.
8. 상충 Evidence와 불확실성을 표시한다.
9. 근거 기반 제안사항을 작성한다.
10. Claim과 Citation 정확성을 평가한다.
11. Provider를 교체 가능한 구조로 유지한다.
12. 비용 상한과 Cache가 작동한다.
13. 동일 Evaluation Dataset에서 Regression을 방지한다.
14. 실제 관심 분야, 연구주제 및 선행특허 조사에서 유용성을 확인한다.
15. 사용자 가이드와 운영 메모가 존재한다.

### 17.3 Multi-Agent 채택 조건

Multi-Agent는 다음 중 하나 이상의 의미 있는 개선이 입증되어야 한다.

- Evidence Coverage 향상
- Citation Accuracy 향상
- Contradiction Detection 향상
- 복잡한 분석 품질 향상
- Context 안정성 향상
- 처리시간 단축
- 비용 대비 성능 개선
- 실패 격리 개선

개선이 입증되지 않으면 Single-Agent를 기본 경로로 유지한다.

### 17.4 배포 및 제품화 조건

Docker는 재현 가능한 환경과 배포를 위한 중요 수단이지만,
초기 연구 품질 자체를 대체하지 않는다.

FastAPI, SQLite, PostgreSQL, Queue, Web UI 및 MCP/App는
실제 사용 요구가 확인된 순서에 따라 도입한다.

---

## 18. 프로젝트 운영 철학

> 작게 시작하지만 최종 목표는 축소하지 않는다.

> 새로 만들기 전에 이미 만든 것을 감사하고 재사용한다.

> LLM은 판단하고, 코드는 실행·기록·검증한다.

> 비용은 사후 계산만 하지 않고 Agent 실행의 제약으로 관리한다.

> 초기에는 OpenAI를 활용할 수 있지만 특정 Provider에 종속되지 않는다.

> 기능 추가는 실제 품질·비용·처리시간 개선이 검증된 경우에만 채택한다.

> Multi-Agent는 필요성과 효과가 입증된 후 도입한다.

> 근거가 부족하면 결론을 강요하지 않고 불확실성을 공개한다.

> ChatGPT는 프로젝트를 총괄하고 Codex는 실제 저장소 구현을 담당한다.

> 문서의 주장보다 실제 코드, 테스트 및 실행 결과를 우선하여 확인한다.
