# AIRA PROJECT CHARTER

## 1. 문서의 목적

본 문서는 AIRA(Agentic Intelligence Research Assistant) 프로젝트의 최상위 목적, 제품 정의, 핵심 요구사항, 개발 원칙, 운영 방식, 기술 방향 및 성공 기준을 정의한다.

본 문서는 앞으로 다음 작업의 최상위 기준으로 사용한다.

* ChatGPT `Agentic AI Lab` 프로젝트의 총괄 관리
* 로컬 `agentic-ai-lab` 저장소의 코드 감사
* Single Research Agent 설계 및 구현
* Tool, RAG, Memory, Planning 및 Eval 통합
* Codex 작업지시서 작성
* 기능 확장과 Multi-Agent 전환 판단
* 비용, 품질 및 보안 관련 의사결정

기존 문서, 기존 코드 또는 과거 Phase·Lesson의 내용이 본 문서와 충돌하는 경우에는 임의로 수정하지 않는다.

충돌 내용을 먼저 분석한 후 다음 중 하나로 분류한다.

* 기존 내용을 유지
* 본 문서에 맞게 수정
* 별도의 호환 계층으로 유지
* 보류
* 폐기 후보

중요한 결정은 `DECISIONS.md`에 기록한다.

---

# 2. 프로젝트 배경

본 프로젝트는 Agentic AI의 개념, 구조, 구현, 평가, 보안 및 운영을 학습하면서 실제로 사용할 수 있는 AI Research Agent를 구축하기 위해 시작되었다.

프로젝트 과정에서 다음과 같은 내용을 단계적으로 학습하거나 구현하였다.

* 생성형 AI와 LLM
* OpenAI API와 Responses API
* OpenAI Python SDK
* Structured Outputs
* Function Calling과 Tool Calling
* Tool Registry와 Tool Execution
* Workflow와 State
* Retry와 Timeout
* RAG
* Document Parsing
* Chunking
* Embedding
* Keyword Search
* Vector Search
* Hybrid Retrieval
* Citation Grounding
* Memory와 State
* Planning Agent
* Replanning
* Agent Loop
* Single Research Agent
* Multi-Agent Research 구조
* Evals
* Guardrails
* Tracing
* Application Service
* Persistence
* Retry, Cancellation 및 Background Job 구조
* Token Usage와 API 비용 계산

그러나 현재 기본 AIRA Runtime은 위 기능 전체를 충분히 통합하지 못하고 있다.

현재 실제 실행 경로는 로컬 TXT 또는 Markdown 문서를 대상으로 결정론적 Research Pipeline을 수행하는 최소 구조에 가깝다.

따라서 앞으로의 핵심 과제는 새로운 기능을 무조건 추가하는 것이 아니다.

우선 기존 `agentic-ai-lab` 저장소를 정확하게 감사하고, 이미 구현된 기능을 최대한 재사용하여 사용자가 원래 기대한 실제 AIRA를 단계적으로 완성하는 것이다.

---

# 3. AIRA의 최종 목표

AIRA의 최종 목표는 다음과 같다.

> AIRA는 사용자가 관심 분야, 연구 주제 또는 선행특허 조사를 요청하면 조사 목적과 범위를 이해하고 연구계획을 수립한 뒤, 인터넷의 공개 자료와 사용자가 지정한 로컬 문서를 검색·수집한다. 수집된 자료의 관련성, 중요도, 신뢰도, 최신성 및 증거 수준을 평가하고, 핵심 내용을 정리·요약·비교·분석한다. 이후 자료 간 일치점, 차이점, 충돌, 위험요소 및 시사점을 도출하고, 근거 기반의 제안사항과 추적 가능한 Citation을 포함한 최종 연구 리포트를 작성한다.

AIRA는 단순 검색기, 문서 요약기 또는 고정된 문서 처리 Pipeline을 최종 목표로 하지 않는다.

AIRA는 사용자의 연구와 의사결정을 지원하는 분석·제안형 AI Research Agent를 목표로 한다.

---

# 4. AIRA의 핵심 역할

AIRA는 다음 역할을 하나의 연속된 연구 과정으로 수행해야 한다.

1. 사용자 요청 이해
2. 조사 목적과 범위 정의
3. 하위 연구과제 생성
4. 검색 전략 및 Query 생성
5. 인터넷 자료 검색
6. 로컬 문서 검색
7. 원문 수집과 Parsing
8. 문서 Chunking과 Retrieval
9. 관련 Evidence 추출
10. 자료별 중요도와 신뢰도 평가
11. 자료 정리와 요약
12. 복수 자료 비교
13. 공통점, 차이점 및 충돌 분석
14. Evidence 충분성 평가
15. 부족한 경우 검색계획 수정과 추가 조사
16. Claim 생성
17. Claim과 Evidence 및 Citation 연결
18. 위험요소와 시사점 도출
19. 근거 기반 제안사항 작성
20. 최종 품질 및 무결성 검증
21. Markdown 및 JSON 보고서 저장
22. 조사 범위, 방법, 비용 및 한계 기록

---

# 5. 주요 사용 사례

## 5.1 관심 분야 조사

예:

```text
최근 Agentic AI 분야의 핵심 기술, 주요 프레임워크,
유망한 사업기회 및 향후 발전 방향을 조사하라.
```

AIRA는 다음을 수행한다.

* 관심 분야의 범위 정의
* 주요 하위 영역 분류
* 최신 자료 탐색
* 중요한 기술과 흐름 식별
* 자료별 중요도 평가
* 주요 기회와 위험 분석
* 향후 주목할 영역 제안
* 최종 동향 보고서 작성

---

## 5.2 특정 연구주제 조사

예:

```text
압력센서를 활용한 착석 상태 기반 행동관리 기술의
현재 기술 수준과 발전 가능성을 조사하라.
```

AIRA는 다음을 수행한다.

* 핵심 개념과 연구질문 구체화
* 관련 기술 용어와 동의어 생성
* 논문, 기술문서, 제품 및 공식 자료 검색
* 주요 기술방식 분류
* 방식별 장점과 한계 비교
* 미해결 문제 분석
* 연구 및 개발 방향 제안
* 최종 연구 보고서 작성

---

## 5.3 선행특허 조사

예:

```text
착석 상태를 자동 감지하여 사용자의 행동을 유도하는
시스템과 관련된 선행특허를 조사하라.
```

AIRA는 다음을 수행한다.

* 발명의 핵심 구성요소 추출
* 한국어 및 영어 검색어 생성
* 동의어와 관련 개념 확장
* 관련 특허자료 검색
* 특허별 관련도와 중요도 평가
* 핵심 청구항과 기술구성 분석
* 사용자 발명과 대응 비교
* 공통점과 차이점 분석
* 신규성·진보성 관련 위험요소 후보 정리
* 추가 조사 또는 출원 전략 제안
* 최종 선행특허 조사 보고서 작성

AIRA의 특허 분석은 전문 변리사 또는 법률전문가의 최종 판단을 대체하지 않는다.

---

## 5.4 인터넷 자료와 로컬 문서의 통합 조사

예:

```text
내가 작성한 특허 명세서와 인터넷상의 선행기술 자료를
함께 분석하여 차별점과 위험요소를 정리하라.
```

AIRA는 인터넷 자료와 로컬 문서를 동일한 Research Document 구조로 정규화한 뒤 통합 분석해야 한다.

---

## 5.5 복수 로컬 문서 비교

예:

```text
V0 명세서와 V5 명세서를 비교하여 새로 추가된 기술적 내용을 찾고,
V0에서 그 근거를 확인하라.
```

AIRA는 문서 간 변경, 누락, 추가, 충돌 및 근거 관계를 분석해야 한다.

---

# 6. 입력 범위

## 6.1 연구 요청

AIRA는 최소한 다음 입력을 지원한다.

* 연구 질문
* 조사 목적
* 조사 범위
* 중점 평가 기준
* 원하는 결과 형태
* 기간 범위
* 언어 범위
* 선호 Source 유형
* 제외할 Source 유형
* 최대 Source 수
* 최대 반복 횟수
* 최대 비용
* 로컬 문서 또는 폴더
* 인터넷 검색 사용 여부

---

## 6.2 지원할 로컬 문서

초기 목표 형식:

* TXT
* Markdown
* PDF
* HWP
* HWPX

향후 확장 후보:

* DOCX
* HTML
* CSV
* XLSX
* PPTX

지원 여부는 단순 파일 열기에 그치지 않는다.

다음 정보가 가능한 범위에서 보존되어야 한다.

* 파일명
* 파일 경로
* 문서 제목
* Heading 또는 Section
* 페이지 번호
* 문단 위치
* 줄 범위
* 표 또는 목록 위치
* 변환 방식
* 원문 인용문

---

## 6.3 인터넷 자료

조사 대상은 다음과 같다.

* 일반 웹페이지
* 정부 및 공공기관 자료
* 국제기구 자료
* 기업 공식문서
* 기술 Documentation
* 학술 논문
* 공개 Preprint
* 기술 보고서
* 공개 PDF
* 뉴스
* 공개 특허자료
* 공개 데이터셋 설명

AIRA는 다음을 목적으로 하지 않는다.

* 로그인 우회
* 유료벽 우회
* 접근권한 우회
* robots.txt 위반
* 비공개 시스템 침입
* 불법 또는 무단 데이터 수집

---

# 7. 자료 평가 기준

AIRA는 검색된 자료를 단순히 나열해서는 안 된다.

각 자료를 최소한 다음 기준으로 평가해야 한다.

## 7.1 관련성

* 사용자의 질문과 직접 관련되는가?
* 핵심 연구주제를 실제로 다루는가?
* 보고서의 특정 Claim을 지원할 수 있는가?

## 7.2 중요도

* 전체 결론에 미치는 영향이 큰가?
* 핵심 기술, 사건, 특허 또는 규정을 포함하는가?
* 다른 자료를 이해하는 데 기준이 되는가?

## 7.3 신뢰도

* 공식 원출처인가?
* 작성자와 발행기관이 확인되는가?
* 학술적 검증 또는 기관 검토를 거쳤는가?
* 독립된 다른 자료로 확인되는가?

## 7.4 최신성

* 최신 정보가 중요한 주제인가?
* 발행일 또는 공개일이 확인되는가?
* 현재 시점에도 유효한가?

## 7.5 증거 수준

* Claim을 직접 입증하는가?
* 간접적으로 지지하는가?
* 단순 의견 또는 해석인가?
* 다른 Source와 상충하는가?

## 7.6 평가 결과의 사용

평가 점수는 단순 표시용으로 사용하지 않는다.

다음 의사결정에 실제 반영한다.

* 어떤 Source를 읽을 것인가
* 어떤 Source를 제외할 것인가
* 어떤 Source를 주요 근거로 사용할 것인가
* 어떤 Claim의 Confidence를 낮출 것인가
* 추가 교차검증이 필요한가
* 보고서에서 어떤 자료를 우선 제시할 것인가

---

# 8. 정리·요약·비교·분석 원칙

AIRA는 다음 작업을 구분해야 한다.

## 8.1 정리

자료를 주제, 유형, 시기, 기술방식 또는 Source 종류별로 구조화한다.

## 8.2 요약

각 자료의 핵심 주장, 결과 또는 기술구성을 압축한다.

## 8.3 비교

복수 자료를 동일한 평가기준으로 나란히 검토한다.

비교 기준 예:

* 목적
* 기술구성
* 적용범위
* 센서 또는 입력방식
* 판단방법
* 자동화 수준
* 출력방법
* 장점
* 한계
* 공개일
* 증거 수준

## 8.4 분석

자료의 의미와 시사점을 도출한다.

예:

* 왜 중요한가
* 어떤 기술 흐름을 나타내는가
* 공통된 한계는 무엇인가
* 서로 모순되는 이유는 무엇인가
* 사용자 아이디어와 겹치는 부분은 무엇인가
* 차별화 가능성은 어디에 있는가
* 향후 기회와 위험은 무엇인가

AIRA의 핵심 가치는 검색과 요약 자체보다 비교, 분석, 검증 및 제안 단계에서 나타나야 한다.

---

# 9. 제안사항 작성 원칙

AIRA의 최종 제안은 일반적인 조언이어서는 안 된다.

모든 주요 제안은 가능한 범위에서 다음 구조를 가져야 한다.

```text
제안사항
→ 제안 이유
→ Supporting Evidence
→ 관련 Source
→ 예상 효과
→ 위험요소
→ Confidence
→ 다음 행동
```

기술 조사 제안 예:

* 우선 개발할 기능
* 차별화 가능한 기술요소
* 추가 실험이 필요한 가설
* 시제품 설계 방향
* 후속 연구 주제
* 시장 진입 우선순위

특허 조사 제안 예:

* 추가 검색이 필요한 특허분류
* 주의해야 할 선행특허
* 청구항 차별화 후보
* 명세서에서 강화해야 할 구성
* 근거가 부족한 표현
* 전문가 검토가 필요한 쟁점

---

# 10. 초기 Single-Agent 목표

AIRA는 처음부터 모든 기능을 완성하려 하지 않는다.

먼저 실제로 처음부터 끝까지 동작하는 최소 Single Research Agent를 완성한다.

초기 목표 구조는 다음과 같다.

```text
Research Request
→ LLM-based Research Planning
→ Tool Selection
→ Internet or Local Search
→ Source Reading
→ Basic Retrieval
→ Evidence Extraction
→ Basic Source and Evidence Evaluation
→ Limited Replanning
→ Claim Generation
→ Citation-grounded Report
→ Final Validation
```

초기 Single Agent는 최소한 다음 능력을 가져야 한다.

* 연구 요청을 구조화
* 조사계획 생성
* 사용할 Tool 선택
* 인터넷 또는 로컬 자료 검색
* 관련 Source 선택
* 원문 읽기
* Evidence 추출
* 기본 중요도와 신뢰도 평가
* 자료가 부족하면 제한된 추가 검색
* Claim 생성
* Citation 연결
* 제안사항 도출
* Markdown 및 JSON 보고서 작성

초기 버전은 완벽한 기능보다 전체 흐름의 실제 작동을 우선한다.

단, 최종 목표를 단순 로컬 문서 검색기나 고정형 Workflow로 축소하지 않는다.

---

# 11. 점진적 확장 원칙

추가 기능은 실제 필요성과 평가 결과에 따라 단계적으로 도입한다.

후보 확장 기능:

* PDF 처리 고도화
* HWP 및 HWPX 처리 고도화
* Hybrid RAG
* Embedding Search
* Reranking
* Source 중요도 평가 고도화
* Evidence 교차검증
* 상충자료 분석
* Working Memory
* Long-term Memory
* Research Cache
* 전문 Research Skill
* 선행특허 전문 Workflow
* Application Persistence
* Background Job
* Multi-Agent

각 확장 기능은 다음 절차를 따른다.

```text
Need Identification
→ Existing Code Audit
→ Reuse Decision
→ Integration Design
→ Implementation
→ Unit Test
→ Integration Test
→ Real Research Evaluation
→ Cost and Quality Comparison
→ Adoption Decision
```

기능 수가 증가했다는 이유만으로 프로젝트가 발전했다고 판단하지 않는다.

실제 조사 품질, 신뢰도, 비용, 처리시간 또는 사용성이 개선되어야 한다.

---

# 12. Multi-Agent 발전 방향

Multi-Agent는 초기 기본 구조로 도입하지 않는다.

Single-Agent Runtime을 완성하고 실제 연구 과제로 평가한 후 역할 분리가 다음 중 하나를 개선하는 경우에만 도입한다.

* Retrieval 품질
* Evidence Coverage
* Citation 정확도
* 상충자료 탐지
* 복잡한 분석 품질
* Context 관리
* 병렬 처리시간
* 실패 격리
* 비용 효율

후보 Agent 역할:

* Research Coordinator
* Web Search Specialist
* Local Document Specialist
* Patent Search Specialist
* Evidence Analyst
* Claim Critic
* Verification Agent
* Report Writer

Multi-Agent 구조를 도입할 때에는 Agent 수 증가 자체를 목표로 하지 않는다.

동일한 Evaluation Dataset으로 Single-Agent 대비 개선을 입증해야 한다.

---

# 13. 기존 저장소 우선 재사용 원칙

새 기능을 구현하기 전에 다음 저장소를 반드시 감사한다.

```text
/home/moon/Project/agentic-ai-lab
```

특히 다음 기능을 우선 감사한다.

* OpenAI Responses API
* OpenAI Python SDK
* Structured Outputs
* Tool Calling
* Tool Registry
* Tool Execution Loop
* Workflow와 State
* Retry와 Timeout
* RAG
* Document Parsing
* Chunking
* Embedding
* Retrieval
* Reranking
* Citation Grounding
* Memory
* Planning Agent
* Replanning
* Single Research Agent
* Multi-Agent
* Evals
* Guardrails
* Tracing
* Usage 수집
* Token 계산
* API 비용 계산
* Budget 제한
* Retry
* Cancellation
* Background Job
* Application Service

각 기능은 다음 네 상태를 구분한다.

* Implemented
* Tested
* Runtime-connected
* Production-ready

파일이나 클래스가 존재한다는 이유만으로 실제 사용 가능한 기능이라고 판단하지 않는다.

기존 구현이 요구사항을 충족하면 그대로 재사용한다.

직접 연결하기 어렵다면 Adapter를 추가한다.

일부 기능만 부족하면 해당 부분만 수정한다.

동일 기능을 새로 작성하는 것은 다음 조건에서만 허용한다.

* 기존 구현이 Target Architecture와 구조적으로 호환되지 않음
* 기존 구현에 심각한 품질 또는 보안 문제가 있음
* 재사용 비용이 재작성 비용보다 명확히 큼
* 테스트를 통해 재사용 불가능함이 확인됨

재작성 결정은 근거와 영향을 기록한다.

---

# 14. 기존 Capability Audit

초기 최우선 작업은 새로운 기능 개발이 아니라 Existing Capability Audit이다.

Audit은 다음을 확인한다.

* 현재 전체 파일 Inventory
* 모듈별 책임
* 주요 클래스와 함수
* 단위 테스트 존재 여부
* 통합 테스트 존재 여부
* 실제 API 호출 여부
* Fake 또는 Stub 사용 여부
* 실제 Runtime 연결 여부
* 외부 LLM 의존 여부
* 외부 검색 API 의존 여부
* 중복 구현
* 미사용 코드
* 재사용 가능한 코드
* Adapter가 필요한 코드
* 수정이 필요한 코드
* 보류 또는 폐기 후보

Audit 결과에는 최소한 다음 표가 포함되어야 한다.

```text
Component
Location
Implemented
Tested
Runtime-connected
Production-ready
External dependency
Reusable
Integration effort
Decision
```

---

# 15. OpenAI Responses API와 SDK

초기 AIRA는 기존 프로젝트에서 학습하거나 구현한 OpenAI Responses API 또는 OpenAI SDK를 활용할 수 있다.

기존 구현 감사 대상:

* API Client
* Client Factory
* 환경변수 처리
* Responses API 호출
* Structured Output
* Tool Definition
* Tool Call 처리
* Tool Result 반환
* Multi-turn Response 처리
* Retry와 Timeout
* Usage 수집
* Token 계산
* 비용 계산
* 오류 정규화
* 실제 API 테스트
* Fake Client 테스트
* 현재 Runtime 연결 여부

기존 코드가 사용 가능하면 새로 작성하지 않고 재사용한다.

초기 구현에서 OpenAI를 사용하는 이유는 다음과 같다.

* 기존 학습 및 구현 자산 활용
* Structured Outputs 지원
* Tool Calling 지원
* 상대적으로 빠른 초기 통합
* 안정적인 Single-Agent 기준선 확보

단, AIRA 전체를 OpenAI 전용 구조로 설계하지 않는다.

---

# 16. LLM Provider 독립성

AIRA의 Domain Model, Tool System, RAG, Evidence, Claim, Citation, Report 및 Agent State는 특정 LLM Provider에 직접 종속되지 않아야 한다.

공통 `LLMProvider` 또는 이에 준하는 계약을 정의한다.

후보 구현:

* OpenAI Responses Provider
* 다른 상용 LLM API Provider
* OpenAI-compatible Provider
* Ollama Provider
* 로컬 LLM Provider
* Deterministic Test Provider

공통 Provider가 제공할 기능 후보:

* Structured Output 생성
* Tool Call 요청
* Research Planning
* Query 생성
* Source 관련성 평가
* Evidence 분석
* Claim 생성
* 제안사항 생성
* Report 합성
* Usage 반환
* 비용 추정
* 오류 정규화

AIRA 내부는 Provider 고유 Response 객체를 직접 사용하지 않고 정규화된 공통 응답 구조를 사용한다.

예:

```text
LLMResponse
├── content
├── structured_output
├── tool_calls
├── input_tokens
├── output_tokens
├── cached_tokens
├── provider
├── model
├── latency
├── estimated_cost
└── raw_reference
```

---

# 17. 로컬 LLM 발전 방향

AIRA는 장기적으로 로컬 LLM을 활용할 수 있도록 설계한다.

로컬 LLM 사용 목적:

* 외부 API 비용 절감
* 민감한 로컬 문서의 외부 전송 최소화
* Offline 또는 제한된 네트워크 환경 지원
* 반복적인 저난도 작업의 로컬 처리
* 특정 분야 모델 실험

초기 로컬 LLM 적용 후보:

* 검색 Query 확장
* Source 분류
* 검색결과 1차 평가
* Chunk 관련성 판단
* 간단한 요약
* 중복 내용 판정
* 개인정보 및 민감정보 탐지

고난도 작업은 로컬 모델의 품질이 실제 평가를 통과하기 전까지 검증된 외부 LLM을 사용할 수 있다.

고난도 작업 예:

* 복수 Source 종합
* 복잡한 기술 비교
* 상충 Evidence 분석
* 선행특허 구성 대응 분석
* 최종 전문 보고서 작성

외부 LLM과 로컬 LLM은 동일한 Provider 계약과 Evaluation Dataset을 사용해 비교한다.

---

# 18. 모델 라우팅 방향

초기 버전은 복잡성을 줄이기 위해 하나의 검증된 모델로 시작할 수 있다.

이후에는 작업 난도와 비용에 따라 모델을 선택할 수 있도록 확장한다.

예상 역할:

* Query 생성: 저비용 모델
* Search Result 분류: 저비용 또는 로컬 모델
* Chunk Retrieval: Embedding 또는 Reranker
* Evidence 분석: 중간급 모델
* 복수 자료 비교: 고성능 모델
* 상충자료 분석: 고성능 모델
* 최종 보고서: 고성능 모델
* Citation ID 검증: 결정론적 코드

모델 분리는 실제 평가에서 품질 또는 비용 개선이 확인된 경우에만 적용한다.

---

# 19. Tool 시스템

## 19.1 Tool의 정의

Tool은 Agent가 외부 환경을 검색, 읽기, 분석 또는 저장하기 위해 호출하는 개별 기능이다.

각 Tool은 최소한 다음 정보를 가져야 한다.

* 이름
* 설명
* 입력 Schema
* 출력 Schema
* 권한
* 비용 유형
* Timeout
* Retry 정책
* 오류 형식
* 최대 실행 횟수
* Trace 정책
* 민감정보 처리 정책

---

## 19.2 초기 핵심 Tool 후보

### 인터넷 검색 및 읽기

* `web_search`
* `fetch_web_page`
* `fetch_web_pdf`
* `search_official_sources`
* `search_academic_sources`
* `search_patent_sources`

### 로컬 문서

* `search_local_documents`
* `read_text_document`
* `read_markdown_document`
* `read_pdf_document`
* `read_hwp_document`
* `read_hwpx_document`

### RAG

* `chunk_document`
* `index_document`
* `retrieve_chunks`
* `rerank_chunks`

### 분석

* `extract_evidence`
* `evaluate_source_quality`
* `compare_evidence`
* `detect_conflicts`
* `validate_citation`
* `run_python_analysis`

### 결과

* `save_research_report`
* `save_research_result`
* `export_trace`

초기 버전에서 모든 Tool을 한꺼번에 구현하지 않는다.

실제 최소 Agent Loop에 필요한 Tool부터 연결한다.

---

# 20. Skill 시스템

## 20.1 Skill의 정의

Skill은 특정 연구업무를 반복 가능하고 일관되게 수행하기 위한 재사용 가능한 절차이다.

Tool은 개별 행동이고, Skill은 여러 Tool과 판단규칙을 목적별로 결합한 작업방법이다.

## 20.2 초기 Skill 후보

* `general-web-research`
* `official-source-research`
* `academic-literature-review`
* `local-document-analysis`
* `cross-source-verification`
* `claim-evidence-audit`
* `conflicting-evidence-analysis`
* `technical-trend-report`
* `patent-prior-art-analysis`
* `project-document-consistency-audit`

## 20.3 Skill 구성

각 Skill은 최소한 다음을 정의한다.

* 목적
* 적용 조건
* 입력
* 사용 가능한 Tool
* Source 우선순위
* 조사 단계
* 평가 기준
* 완료 조건
* 추가 조사 조건
* 실패 또는 보류 조건
* 보고서 형식
* Guardrail

Skill은 처음부터 ChatGPT Plugin 형태로 만들 필요는 없다.

우선 저장소 내 재사용 가능한 Agent 업무 절차로 정의하고 검증한다.

---

# 21. RAG 목표

AIRA의 RAG는 인터넷 자료와 로컬 문서를 동일한 Research Document 구조로 처리해야 한다.

기본 흐름:

```text
Source Discovery
→ Document Fetching
→ Parsing
→ Metadata Normalization
→ Chunking
→ Keyword Index
→ Embedding Index
→ Hybrid Retrieval
→ Reranking
→ Evidence Selection
```

## 21.1 Hybrid Retrieval

AIRA는 다음 방식을 결합하는 방향을 검토한다.

* Keyword Search
* Semantic Embedding Search
* Metadata Filtering
* Reranking

Keyword Search가 중요한 경우:

* 특허번호
* 법률 조문
* 제품명
* 정확한 기술용어
* 고유명사
* 코드 식별자
* 도면부호

Semantic Search가 중요한 경우:

* 동의어
* 유사 표현
* 다른 언어의 유사 개념
* 문맥상 관련 내용
* 질문과 의미적으로 유사한 설명

## 21.2 Citation 위치

모든 Evidence는 가능한 범위에서 원문 위치를 보존한다.

인터넷:

* URL
* 제목
* 작성자 또는 발행기관
* 게시일
* 검색일
* Heading
* 인용문

TXT와 Markdown:

* 파일 경로
* Heading
* 줄 범위
* 인용문

PDF:

* 파일 또는 URL
* 페이지 번호
* 인용문

HWP와 HWPX:

* 파일 경로
* Section 또는 문단
* 변환 방식
* 확인 가능한 원문 위치
* 인용문

---

# 22. Memory와 State

초기에는 하나의 연구 실행 내부에서 필요한 Working State를 우선 구현한다.

상태 후보:

* Research Request
* Research Plan
* Tasks
* Search Queries
* Tool Calls
* Search Results
* Visited Sources
* Documents
* Chunks
* Evidence
* Claims
* Citations
* Conflicts
* Recommendations
* Quality Evaluation
* Usage
* Cost
* Iteration Count
* Termination Reason

장기 Memory는 이후 다음 목적에 따라 도입한다.

* 동일 Source 재다운로드 방지
* 동일 문서 Parsing 재사용
* 동일 문서 Embedding 재사용
* 이전 조사 결과 재사용
* 프로젝트 지식 축적
* 중복 조사 방지
* 이전 Claim과 신규 Claim 비교

민감한 정보는 자동으로 장기 Memory에 저장하지 않는다.

---

# 23. Agent Loop

실제 Single Research Agent는 최소한 다음 Loop를 가져야 한다.

```text
Plan
→ Select Action
→ Execute Tool
→ Observe Result
→ Update State
→ Evaluate Evidence
→ Replan if Needed
→ Generate Claims
→ Verify
→ Complete or Abstain
```

Agent는 다음을 판단할 수 있어야 한다.

* 다음에 어떤 Tool을 사용할 것인가
* 어떤 Query를 생성할 것인가
* 어떤 Source를 읽을 것인가
* 어떤 자료를 제외할 것인가
* Evidence가 충분한가
* 추가 검색이 필요한가
* 상충하는 자료를 추가 확인해야 하는가
* 조사 완료 조건을 충족했는가
* 근거 부족으로 결론을 보류해야 하는가

Agent Loop에는 반드시 제한이 있어야 한다.

* 최대 반복 횟수
* 최대 Tool 호출
* 최대 Search 호출
* 최대 Source 수
* 최대 Token
* 최대 비용
* 최대 실행시간
* 종료 이유 기록

---

# 24. 검증 원칙

## 24.1 Source 검증

* 공식 원출처인가
* 작성자와 기관이 확인되는가
* 게시일이 확인되는가
* 2차 인용이 아닌가
* 접근한 원문이 실제 검색결과와 일치하는가

## 24.2 Claim 검증

* 모든 핵심 Claim에 Evidence가 있는가
* Citation이 실제 Source를 가리키는가
* Evidence가 Claim을 실제로 지지하는가
* Claim이 Evidence보다 과도하게 확장되지 않았는가
* 상충 Evidence가 누락되지 않았는가

## 24.3 교차검증

중요 Claim은 가능한 경우 독립된 복수 Source로 확인한다.

교차검증이 불가능한 경우 다음 상태 중 하나로 표시한다.

* 단일 Source 확인
* 공식 확인 불가
* 출처 간 상충
* 제한적 근거
* 추가 조사 필요
* 사실 확인 불가

## 24.4 불확실성

AIRA는 불확실성을 숨기지 않는다.

결론 또는 Claim의 상태 예:

* Confirmed
* Strongly Supported
* Moderately Supported
* Limited Evidence
* Conflicting
* Unverified

---

# 25. 보고서 구조

최종 보고서는 최소한 다음 구성을 지원한다.

```markdown
# 연구·조사 보고서

## 1. Executive Summary
- 핵심 결론
- 가장 중요한 발견
- 우선 제안사항

## 2. 조사 요청
- 질문
- 목적
- 범위
- 기준일

## 3. 조사 방법
- 사용한 검색 경로
- 검색 Query
- 로컬 문서 범위
- 포함·제외 기준

## 4. 주요 자료 평가
- 관련성
- 중요도
- 신뢰도
- 최신성
- Evidence Strength

## 5. 핵심 내용 정리 및 요약

## 6. 비교 분석

## 7. 주요 발견
- Claim
- Supporting Evidence
- Contradicting Evidence
- Confidence
- Citations

## 8. 위험요소와 시사점

## 9. 제안사항
- 우선순위
- 근거
- 기대효과
- 위험
- 다음 행동

## 10. 한계와 불확실성

## 11. 추가 조사 과제

## 12. Sources
```

선행특허 보고서에는 다음을 추가한다.

* 특허번호
* 발명의 명칭
* 출원인
* 우선일
* 출원일
* 공개일
* 법적 상태
* 핵심 청구항
* 주요 기술구성
* 사용자 발명과의 관련도
* 공통점
* 차이점
* 잠재적 위험
* 추가 확인사항

---

# 26. API Usage 및 비용 관리

LLM과 검색 API 비용은 AIRA의 핵심 설계 제약이다.

기존 저장소에 구현된 다음 코드를 우선 감사한다.

* Usage Collector
* Token Counter
* Model Price Registry
* Cost Estimator
* Actual Cost Calculator
* Budget
* Budget Guardrail
* Execution Cost Report

Audit에서는 다음을 구분한다.

* 토큰 계산만 가능한가
* 실제 API Usage를 수집하는가
* 입력·출력·캐시 Token을 구분하는가
* 모델별 가격을 적용하는가
* 가격 기준일을 기록하는가
* 실행 전 예상비용을 계산하는가
* 실행 후 실제비용을 계산하는가
* 실행별 비용을 저장하는가
* 누적비용을 관리하는가
* 비용한도 초과 시 중단하는가
* 검색 API 비용을 추가할 수 있는가

AIRA는 최소한 다음 제한을 지원하는 방향으로 설계한다.

* 최대 LLM 호출 횟수
* 최대 Search 호출 횟수
* 최대 Source 수
* 최대 Chunk 수
* 최대 입력 Token
* 최대 출력 Token
* 최대 반복 횟수
* 실행당 최대 비용
* 동일 Query Cache
* 동일 Source Cache
* Parsing Cache
* Embedding Cache

---

# 27. 비용 최적화 원칙

AIRA는 검색한 모든 문서 전체를 LLM에 전달하지 않는다.

기본 비용 절감 흐름:

```text
검색결과
→ 중복 제거
→ Metadata 및 Keyword 1차 선별
→ 중요 Source 원문 수집
→ Parsing
→ Chunking
→ Keyword 또는 Embedding Retrieval
→ Reranking
→ 관련 Evidence만 LLM 전달
```

비용 최적화 후보:

* 검색결과 중복 제거
* 동일 URL Cache
* 동일 문서 Hash Cache
* 문서 전체 대신 관련 Chunk 전달
* 단순 분류에 저가 모델 사용
* 최종 분석에만 고성능 모델 사용
* 실패한 Tool 무한 재호출 방지
* 비용한도 도달 전 조기 종료
* 저가 모델 또는 로컬 모델로 1차 필터링
* 최종 보고서 생성 횟수 제한

---

# 28. Evals

AIRA의 완성 여부는 구현된 기능 수가 아니라 측정 가능한 품질로 판단한다.

핵심 평가 항목:

* Search Relevance
* Retrieval Relevance
* Evidence Coverage
* Source Quality
* Citation Accuracy
* Claim Support
* Contradiction Detection
* Hallucination Rate
* Recommendation Grounding
* Report Completeness
* Trace Completeness
* Latency
* Token Usage
* API Cost
* Reproducibility

초기에는 실제 사용 분야를 반영한 Golden Dataset을 구축한다.

후보 평가 주제:

* Agentic AI 기술 동향
* 특정 기술 연구주제
* 공식 규정 조사
* 로컬 문서 비교
* 선행특허 조사

Single-Agent와 Multi-Agent는 동일한 Dataset으로 비교한다.

---

# 29. Guardrails

초기 Guardrail 후보:

* 빈 연구 요청 차단
* 과도하게 넓은 연구범위 경고
* 허용되지 않은 로컬 경로 접근 차단
* URL Scheme 검증
* 내부 네트워크 주소 접근 제한
* 악성 웹페이지 Prompt Injection 방어
* Tool Permission 검사
* 최대 반복 횟수
* 최대 Source 수
* 최대 Token
* 최대 비용
* Citation 없는 핵심 Claim 차단
* 존재하지 않는 Evidence 참조 차단
* Claim과 Citation ID 무결성 검사
* 외부 전송 전 민감정보 확인
* 비용 증가 작업 승인 정책
* 데이터 삭제 승인 정책

---

# 30. ChatGPT `Agentic AI Lab` 프로젝트의 역할

ChatGPT의 `Agentic AI Lab` 프로젝트는 전체 프로젝트의 총괄 지휘 공간으로 사용한다.

주요 역할:

* 최상위 목표 보존
* 프로젝트 기준 문서 관리
* Capability Audit 총괄
* Target Architecture 설계
* 기술적 의사결정
* 개발 순서 관리
* Codex 작업지시서 작성
* 코드 변경 결과 검토
* 테스트 결과 해석
* 위험과 우선순위 관리
* Tool 및 Skill 설계
* 장기 프로젝트 문맥 유지

ChatGPT는 실제 코드 상태를 추측하지 않는다.

판단에 필요한 경우 저장소의 코드, 파일목록, 테스트 결과, Git Diff 또는 실행결과를 근거로 사용한다.

---

# 31. Codex의 역할

Codex는 실제 코드 구현과 저장소 작업의 주 실행 도구로 사용한다.

Codex의 주요 역할:

* 저장소 탐색
* 기존 기능 감사
* 코드 작성
* Adapter 작성
* Runtime Integration
* 테스트 작성
* Refactoring
* Ruff 수정
* Git Diff 검토 지원
* 문서와 코드의 정합성 확인

Codex 작업지시에는 최소한 다음이 포함되어야 한다.

* 작업 목적
* 관련 기준 문서
* 현재 확인된 코드 상태
* 재사용해야 할 기존 모듈
* 수정 허용 범위
* 수정 금지 범위
* Acceptance Criteria
* 실행할 테스트
* 완료 후 보고 형식

Codex의 결과를 자동으로 정답으로 간주하지 않는다.

ChatGPT와 사용자는 다음을 검토한다.

* 요구사항 충족
* 중복 구현 여부
* 기존 코드 재사용 여부
* 테스트 결과
* 보안 영향
* 비용 영향
* Git Diff

Codex Usage Limit이 소진된 기간에는 다음을 진행할 수 있다.

* 프로젝트 문서 정리
* Capability Audit 설계
* Target Architecture 작성
* Tool 및 Skill Registry 설계
* Codex용 작업지시서 작성
* 기존 실행결과 분석

---

# 32. Plugin, App 및 MCP 방향

Plugin, ChatGPT App 또는 MCP 연결은 초기 Single-Agent Runtime의 선행조건이 아니다.

우선 독립 실행 가능한 AIRA Runtime을 완성한다.

향후 다음 구조를 고려한다.

```text
ChatGPT
→ AIRA App 또는 MCP Client
→ AIRA Runtime
→ Internet 및 Local Tools
→ Research Result
```

장기 목표 후보:

* ChatGPT에서 AIRA 조사 실행
* ChatGPT 프로젝트와 로컬 AIRA 연결
* 로컬 파일을 안전하게 검색
* 조사결과를 ChatGPT 프로젝트로 반환
* 검증된 Research Skill 배포
* 외부 데이터베이스 또는 사내 시스템 연결

Tool과 Agent Runtime이 안정되기 전에 Plugin 또는 MCP 연결부터 개발하지 않는다.

---

# 33. 개발 단계

## Stage 0 — Project Charter 확정

* 목표 확정
* 범위 확정
* 개발 원칙 확정
* ChatGPT와 Codex 역할 확정

## Stage 1 — Existing Capability Audit

* 전체 Inventory
* Responses API
* Tool
* RAG
* Memory
* Planning
* Research
* Multi-Agent
* Evals
* Guardrails
* Cost
* Application 계층 감사

## Stage 2 — Target Product and Architecture

* Single-Agent 목표 구조
* Domain Model
* Agent State
* Tool 계약
* LLM Provider
* Search Provider
* Document Adapter
* RAG 구조
* Report 구조 확정

## Stage 3 — Minimal Intelligent Agent

* OpenAI Responses API 또는 기존 LLM 코드 연결
* 최소 Tool Calling
* 인터넷 또는 로컬 검색
* Source 읽기
* Evidence 추출
* 기본 분석
* Citation 기반 보고서

## Stage 4 — Local Document Expansion

* TXT
* Markdown
* PDF
* HWP
* HWPX

## Stage 5 — Internet Research Expansion

* 일반 웹검색
* 웹페이지 읽기
* 공개 PDF
* 공식자료 우선 검색
* 특허 및 학술자료 검색

## Stage 6 — Integrated RAG

* Parsing
* Chunking
* Keyword Search
* Embedding
* Hybrid Retrieval
* Reranking
* Citation Grounding

## Stage 7 — Agent Loop

* Planning
* Tool Selection
* Observation
* Evidence Sufficiency
* Limited Replanning
* Termination
* Trace

## Stage 8 — Advanced Analysis

* Source 중요도
* 교차검증
* 상충자료
* 위험요소
* 제안사항
* 전문 보고서

## Stage 9 — Evaluation and Optimization

* Golden Dataset
* Retrieval Eval
* Citation Eval
* Recommendation Eval
* 비용과 지연 측정
* 모델 비교
* Regression Test

## Stage 10 — Multi-Agent Experiment

* 역할 분리
* Single-Agent 비교
* 실질적 개선 검증
* 채택 또는 보류

## Stage 11 — Productization

후보:

* CLI 개선
* FastAPI
* Persistence
* Queue/Worker
* Web UI
* MCP/App
* 배포

---

# 34. 현재 기본 Runtime의 위치

현재 Phase 13에서 구현된 Local Research Runtime은 폐기하지 않는다.

현재 Runtime의 역할:

* 결정론적 Offline Baseline
* Schema 검증
* Pipeline Regression Test
* 외부 API 없는 테스트
* 제한된 Fallback
* 향후 LLM Agent와의 비교 기준

현재 Runtime을 최종 AIRA라고 정의하지 않는다.

---

# 35. 초기 범위에서 제외할 사항

초기 Single-Agent가 안정되기 전에는 다음을 우선 구현하지 않는다.

* Agent 수 증가 목적의 Multi-Agent
* 불필요하게 복잡한 분산시스템
* 대규모 Redis Worker
* 대규모 PostgreSQL 구조
* 완전한 웹 크롤러
* 로그인 및 유료벽 우회
* 모든 파일형식 지원
* 모든 검색엔진 동시 지원
* 복잡한 Web UI
* 모바일 앱
* 외부 배포용 Plugin 패키지
* 운영용 대규모 사용자 관리

필요성이 확인되면 별도 결정한다.

---

# 36. 보안 및 사용자 승인

다음 작업은 사용자 승인 후 수행한다.

* 외부 LLM에 로컬 문서 전송
* 개인정보 또는 비공개 자료 외부 전송
* 유료 API 활성화
* 실행당 비용 상한 증가
* GitHub Push
* 운영 배포
* 데이터 삭제
* 운영 데이터베이스 변경
* 외부 이메일 발송
* 보안정책 변경

---

# 37. 성공 기준

## 37.1 초기 Single-Agent 성공 기준

* LLM 기반 연구계획 생성
* 최소 Tool 선택 및 실행
* 인터넷 또는 로컬 Source 검색
* Source 원문 읽기
* Evidence 추출
* 기본 중요도와 신뢰도 평가
* 제한된 재검색
* Claim 생성
* Citation 연결
* 제안사항 생성
* Markdown 및 JSON 보고서
* Usage와 비용 기록
* Trace 저장

## 37.2 통합 AIRA 성공 기준

* 인터넷 검색
* 로컬 TXT/MD/PDF/HWP/HWPX 검색
* 인터넷과 로컬 자료 통합 분석
* Hybrid RAG
* Source 품질 및 중요도 평가
* Evidence 교차검증
* 자료 간 충돌 표시
* 근거 기반 제안사항
* Citation 검증
* 조사 한계 공개
* 비용한도 작동
* Guardrail 작동
* 실제 연구과제 E2E 통과

## 37.3 Multi-Agent 성공 기준

Multi-Agent는 다음 중 하나 이상의 의미 있는 개선이 입증되어야 한다.

* 품질 향상
* Citation 정확도 향상
* Evidence Coverage 향상
* 상충자료 탐지 향상
* 처리시간 단축
* Context 안정성 향상
* 비용 대비 성능 개선

---

# 38. 프로젝트 운영 철학

AIRA 프로젝트는 다음 원칙을 따른다.

> 작게 시작하지만 최종 목표는 축소하지 않는다.

> 새로 만들기 전에 이미 만든 것을 감사하고 재사용한다.

> LLM은 판단하고, 코드는 실행·기록·검증한다.

> 비용은 사후 계산만 하지 않고 Agent 실행의 제약으로 관리한다.

> 초기에는 OpenAI를 활용할 수 있지만 특정 Provider에 종속되지 않는다.

> 기능 추가는 실제 품질 개선이 검증된 경우에만 채택한다.

> Multi-Agent는 필요성과 효과가 입증된 후 도입한다.

> 근거가 부족하면 결론을 강요하지 않고 불확실성을 공개한다.

---

# 39. 문서 우선순위

프로젝트 목표와 제품 방향에 관한 잠정 문서 우선순위는 다음과 같다.

1. `AIRA_PROJECT_CHARTER.md`
2. 향후 작성할 `AIRA_TARGET_PRODUCT_SPEC.md`
3. 향후 작성할 `AIRA_TARGET_ARCHITECTURE.md`
4. `DECISIONS.md`
5. 향후 작성할 `AIRA_PROJECT_AUDIT_REPORT.md`
6. 향후 작성할 `AIRA_INTEGRATION_PLAN.md`
7. 기존 `MASTER.md`
8. 기존 `ROADMAP.md`
9. 기존 Lesson 문서

최종 우선순위는 기존 문서 감사 후 확정한다.

---

# 40. 변경 관리

본 문서의 핵심 목표를 변경할 때에는 다음을 기록한다.

* 변경 이유
* 변경 전 내용
* 변경 후 내용
* 기존 코드에 미치는 영향
* 일정에 미치는 영향
* 비용 영향
* 보안 영향
* 승인 일자

단순 구현 편의를 이유로 AIRA의 최종 목표를 축소하지 않는다.

기술적, 비용적 또는 보안상 한계가 확인되면 사실을 명확히 보고하고 단계적 구현 범위를 조정할 수 있다.
