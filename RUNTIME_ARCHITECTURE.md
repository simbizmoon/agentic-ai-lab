# AIRA Runtime Architecture

## 1. 목적

이 문서는 Phase 13에서 실제 개인용 AIRA를 실행하기 위해 기존 모듈 중 무엇을 사용하고 무엇을 기본 경로에서 제외할지 정의한다.

Phase 13에서는 새로운 Agent Framework를 만들지 않는다.

기존 Single Research Agent와 Application Service를 최소한으로 연결하여 질문과 로컬 문서로부터 근거 기반 보고서를 생성하는 것이 목표다.

## 2. 기본 사용자 흐름

```
연구 질문 + 로컬 Markdown/Text 문서
→ 문서 로딩
→ Single Research Agent
→ Evidence와 Claim 생성
→ Citation 연결
→ 보고서 합성
→ 기본 평가와 Guardrail
→ report.md와 result.json 저장
```

## 3. 기본 실행 경로

```
AIRA CLI
  ↓
Input Validation
  ↓
LocalDocumentAdapter
  ↓
SingleResearchAgentPipeline
  ↓
ApplicationResearchFlowService
  ↓
Minimal Evaluation and Guardrail
  ↓
ResearchResultWriter
```

## 4. 재사용할 기존 모듈

### 4.1 Research Core

* `ResearchRequest`
* `ResearchRequestValidator`
* `ResearchTaskDecomposer`
* `ResearchSearchQueryPlanner`
* `SingleResearchAgentPipeline`
* `ResearchEvidenceExtractor`
* `ResearchSourceQualityEvaluator`
* `ResearchSynthesizer`
* `ResearchQualityEvaluator`

### 4.2 Application Core

* `ApplicationResearchExecutionService`
* `ApplicationResearchFlowService`
* `InMemoryExecutionRepository`
* `InMemoryIdempotencyRepository`
* `InMemoryTransactionManager`
* `ApplicationFailureMapper`

### 4.3 초기 Source Adapter

* `InMemoryResearchSourceSearchTool`
* `InMemoryResearchSourceReader`

기존 In-Memory Adapter는 `LocalDocumentAdapter`가 만든 문서 레코드를 Research Pipeline에 전달하는 데 재사용한다.

## 5. Phase 13에서 추가할 최소 구성

### 5.1 LocalDocumentAdapter

책임은 다음과 같다.

* Markdown과 Text 파일 경로 검증
* UTF-8 문서 읽기
* 기존 In-Memory Research Source와 Document Schema로 변환
* 파일명과 경로를 Citation 식별 정보로 유지

### 5.2 ResearchResultWriter

책임은 다음과 같다.

* 실행별 출력 디렉터리 생성
* `report.md` 저장
* `result.json` 저장
* 기존 Research 결과 모델 직렬화
* 실패 시 불완전한 출력 파일을 남기지 않음

### 5.3 CLI Composition Root

책임은 다음과 같다.

* CLI 인수 처리
* 기존 Service와 Adapter 생성
* 의존성 조립
* Application Flow 한 번 실행
* 결과 경로와 품질 요약 출력

## 6. 기본 경로에서 사용하지 않는 기능

다음 기능은 구현되어 있어도 MVP 기본 경로에서 호출하지 않는다.

* Multi-Agent Research Orchestrator
* Research Agent Registry
* Research Agent Message Bus
* Background Job Queue
* Worker Lease
* Retry Scheduler Process
* Cancellation Workflow
* Reliability Dashboard
* Signed Report Archive
* Authentication Bundle
* Transparency Log
* Merkle Proof
* Witness Quorum
* MCP
* Redis
* PostgreSQL

## 7. 조건부 기능

다음 기능은 실제 필요성이 확인된 경우에만 연결한다.

* OpenAI 기반 의미 합성
* Input Guardrail
* Output Guardrail
* Report Quality Evaluation
* SQLite Persistence
* 최소 FastAPI
* 제한된 Multi-Agent 비교

## 8. 데이터 저장

초기 출력 구조는 다음과 같다.

```
reports/
└── <execution-id>/
    ├── report.md
    └── result.json
```

초기에는 파일 저장으로 충분하다.

SQLite는 다음 요구가 발생할 때만 추가한다.

* 실행 목록 검색
* 상태별 조회
* 많은 결과의 관리
* CLI 재조회 기능이 파일만으로 불편한 경우

## 9. 설계 원칙

* Single Agent가 기본이다.
* 기존 코드를 우선 재사용한다.
* 의미가 없는 추상화를 추가하지 않는다.
* 사용자에게 보이는 결과를 먼저 완성한다.
* 결정 가능한 검증은 코드가 수행한다.
* 의미 해석과 합성에만 LLM을 사용한다.
* 고급 기능은 기본 경로에서 비활성화한다.
* 테스트 수보다 실제 사용 가능성을 우선한다.

## 10. Phase 13.2 완료 판정

다음 사항을 확정하였다.

* 기존 CLI가 없음을 확인했다.
* 기존 Single Research Agent Pipeline을 재사용한다.
* `LocalDocumentAdapter`가 필요하다.
* 최소 Markdown/JSON Writer가 필요하다.
* CLI Composition Root가 필요하다.
* Multi-Agent와 Background Job은 기본 경로에서 제외한다.
* 고급 Report Archive와 Transparency 기능은 사용하지 않는다.
* Phase 13의 신규 Production 구성은 최소 세 개로 제한한다.
