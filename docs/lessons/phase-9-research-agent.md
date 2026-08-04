# Phase 9 — Single Research Agent Workflow

## 1. 목적

Phase 9의 목적은 Phase 8에서 구축한 Planning Agent 위에 실제 연구
업무를 수행하는 Single Research Agent Workflow를 구현하는 것이다.

Research Agent는 사용자의 연구 요청을 구조화하고, 연구 과제를 분해하고,
자료를 검색·읽기·평가한 뒤, Evidence와 Citation을 기반으로 최종 연구
보고서를 생성한다.

Phase 9의 Single Research Agent는 Phase 10 Multi-Agent Research System의
성능과 비용을 비교하기 위한 Baseline으로 사용한다.

## 2. 핵심 실행 흐름

```text
Research Request
        ↓
Research Request Validation
        ↓
Research Task Decomposition
        ↓
Search Query Planning
        ↓
Source Search
        ↓
Source Reading
        ↓
Evidence Extraction
        ↓
Source Quality Evaluation
        ↓
Claim and Citation Mapping
        ↓
Research Synthesis
        ↓
Research Quality Evaluation
        ↓
Final Research Report

## Phase 9 Lesson 목록

Phase 8처럼 과도하게 확장하지 않도록 20개 Lesson으로 고정합니다.
9.1   Research Request Schema
9.2   Research Task와 Task Graph Schema
9.3   Research Request Validator
9.4   Research Task Decomposer
9.5   Search Query Schema
9.6   Search Query Planner
9.7   Source Candidate Schema
9.8   Source Search Tool Contract
9.9   In-Memory Source Search Adapter
9.10  Source Document Schema
9.11  Source Reader Contract와 In-Memory Reader
9.12  Evidence Schema
9.13  Evidence Extractor Contract
9.14  Source Quality Evaluation
9.15  Claim과 Citation Schema
9.16  Research Workspace
9.17  Research Synthesizer
9.18  Research Quality Evaluator
9.19  Single Research Agent Pipeline 및 통합 E2E
9.20  Phase 9 문서화와 Baseline Report

## Phase 9 완료 기준
다음 조건을 모두 충족해야 합니다.

연구 요청이 엄격한 Schema로 검증된다.
연구 요청이 여러 Research Task로 분해된다.
Task별 Search Query가 생성된다.
Source Search와 Source Reading이 Tool Port로 분리된다.
Source에서 Evidence를 추출할 수 있다.
Source 품질과 관련성을 평가할 수 있다.
Claim이 Evidence 및 Citation과 연결된다.
Research Workspace가 모든 중간 결과를 추적한다.
최종 보고서는 근거가 있는 주장과 불확실성을 구분한다.
품질 평가 결과가 구조화되어 반환된다.
Single-Agent 전체 흐름이 E2E 테스트로 검증된다.
비용, Tool 호출 수, Source 수, Evidence 수 등 Phase 10 비교 지표가 기록된다.
Phase 10 Multi-Agent가 동일한 입력과 평가 기준을 사용할 수 있다.

## Phase 9에서 제외할 기능
복수 검색 Provider
실제 웹 크롤러
브라우저 자동화
병렬 Multi-Agent
Agent 간 메시지
영구 데이터베이스
Background Worker
Dashboard
실제 배포

Multi-Agent는 Phase 10에서 필수 구현합니다.

## 3. 설계 원칙
연구 결론보다 Evidence를 먼저 저장한다.
모든 주요 Claim은 Evidence와 Source에 연결한다.
Source 검색과 Source 읽기를 Tool Port로 분리한다.
외부 Provider에 종속되지 않는 Domain Schema를 먼저 구현한다.
결정론적 구조 검증은 Python 코드와 Pydantic으로 수행한다.
불확실한 분해·평가·종합은 LLM이 담당할 수 있다.
사실, 추론, 의견 및 불확실성을 구분한다.
Source 간 충돌을 숨기지 않는다.
검색과 연구 작업에는 명시적인 제한과 종료 조건을 적용한다.
Phase 9에서는 Single-Agent 흐름만 구현한다.
Phase 10에서 동일한 요청과 평가 기준으로 Multi-Agent와 비교한다.
운영 부가 기능은 실제 필요가 확인되기 전까지 확장하지 않는다.

## 4. Phase 8 기능의 재사용
Phase 9는 Phase 8에서 구현한 다음 기능을 재사용한다.

Structured Plan
Plan Validation
Plan Lifecycle
Plan Scheduler
Tool Registry
Step Execution
Plan Evaluation
Bounded Replanning
Agent Trace
Timeline과 Summary
Archive와 Retention

Phase 9에서는 기존 Planning Agent를 다시 구현하지 않는다.

Research Domain에 필요한 Request, Task, Source, Evidence, Citation,
Workspace 및 Report 계층만 추가한다.

## 5. Research Request
Research Request는 사용자가 원하는 연구 작업을 구조화한 입력이다.

포함할 수 있는 정보는 다음과 같다.

Request ID
연구 질문
연구 목적
포함 범위
제외 범위
시작일과 종료일
선호 Source 유형
연구 깊이
최대 Source 수
Citation 요구 여부
출력 형식
추가 Metadata

## 6. Research Task Decomposition
큰 연구 질문은 실행 가능한 하위 Research Task로 분해한다.

각 Task는 다음 정보를 가진다.

Task ID
제목
연구 질문
목표
우선순위
의존 Task
완료 조건
상태
Search 필요 여부
예상 결과

Task 간 의존성을 기반으로 실행 순서를 결정한다.

## 7. Search Query Planning
각 Research Task에 대해 하나 이상의 Search Query를 생성한다.

Search Query Planner는 다음을 고려한다.

정확한 연구 용어
동의어와 대체 표현
공식 문서 우선 탐색
원 논문 또는 1차 Source 탐색
날짜 범위
중복 Query 방지
이미 확보한 Evidence
아직 해결되지 않은 질문

## 8. Source Search
Source Search는 Tool Port로 제공한다.

SourceSearchRequest
        ↓
SourceSearchTool
        ↓
SourceCandidate

Source Candidate는 다음 정보를 포함할 수 있다.

Source ID
제목
URL
저자
발행자
발행일
Source 유형
검색 요약
Search Query
검색 순위
Metadata

Phase 9 초기 구현은 In-Memory Adapter를 사용한다.

## 9. Source Reading
Source Reader는 Source Candidate를 정규화된 Source Document로 변환한다.

Source Document는 다음 정보를 포함할 수 있다.

Source ID
제목
본문
섹션
저자
발행자
발행일
URL
문서 유형
Content Hash
읽기 상태
오류 정보

HTML, PDF, Markdown 등의 원본 형식은 공통 Domain Schema로 정규화한다.

## 10. Evidence Extraction

Evidence는 연구 질문이나 Claim을 뒷받침하거나 반박하는 구체적인 근거이다.

Evidence Item은 다음 정보를 포함할 수 있다.

Evidence ID
Source ID
관련 Research Task ID
Evidence 내용
원문 위치
Evidence 유형
지지 또는 반박 방향
관련성 점수
신뢰도
추출 이유

연구 보고서를 먼저 생성한 후 Citation을 붙이는 방식은 사용하지 않는다.

Evidence를 먼저 확보하고 Evidence를 기반으로 Claim을 생성한다.

## 11. Source Quality Evaluation

모든 Source를 동일하게 취급하지 않는다.

평가 기준은 다음과 같다.

1차 Source 여부
공식성
저자와 발행자 명확성
발행일 명확성
연구 질문과의 관련성
최신성
방법론 투명성
다른 Source와의 교차 검증
광고성 또는 홍보성
이해관계 충돌 가능성

예상 품질 등급은 다음과 같다.

PRIMARY
AUTHORITATIVE
RELIABLE_SECONDARY
SUPPORTING
LOW_CONFIDENCE
REJECTED

## 12. Claim과 Citation

Research Claim은 하나 이상의 Evidence와 연결되어야 한다.

Research Claim
        ↓
Evidence ID
        ↓
Source ID
        ↓
Citation

Citation 계층은 다음을 검증한다.

Source가 실제 Workspace에 존재하는가
Evidence가 해당 Source에 속하는가
Claim이 참조한 Evidence가 존재하는가
Citation이 중복되지 않는가
Citation이 Claim을 실제로 지지하는가
Citation이 필요한 Claim에 누락이 없는가

## 13. Research Workspace

Research Workspace는 연구 과정의 공유 상태이다.

Research Workspace
├── Research Request
├── Research Tasks
├── Search Queries
├── Source Candidates
├── Source Documents
├── Source Evaluations
├── Evidence Items
├── Research Claims
├── Citations
├── Open Questions
├── Quality Evaluations
└── Final Report

Phase 9에서는 하나의 Single Research Agent가 Workspace를 사용한다.

Phase 10에서는 여러 Agent가 동일한 Workspace를 역할별 권한에 따라
공유한다.

## 14. Research Synthesis

Research Synthesizer는 검증된 Evidence와 Claim을 기반으로 보고서를 만든다.

보고서 구조는 다음을 포함할 수 있다.

연구 질문
Executive Summary
주요 발견
상세 분석
상반된 견해
불확실성
한계
추가 조사 과제
Citation
Source 목록

## 15. Research Quality Evaluation

최종 결과를 반환하기 전에 다음을 평가한다.

연구 질문에 직접 답했는가
필수 하위 질문을 다루었는가
주요 Claim에 Evidence가 있는가
Citation이 실제 Source와 연결되는가
신뢰도가 낮은 Source에 과도하게 의존하지 않았는가
Source 간 충돌을 표시했는가
사실과 추론을 구분했는가
불확실성과 한계를 표시했는가
사용자 범위와 출력 요구를 충족했는가

평가 결과는 다음 중 하나이다.

ACCEPTED
NEEDS_MORE_RESEARCH
NEEDS_SOURCE_VERIFICATION
NEEDS_HUMAN_REVIEW
FAILED

## 16. Phase 10 비교를 위한 Baseline Metrics

Phase 9는 다음 Metrics를 기록할 수 있어야 한다.

전체 실행시간
Planning Attempt 수
Replanning 수
Tool 호출 수
Search Query 수
Source Candidate 수
읽은 Source 수
채택된 Source 수
Evidence 수
Claim 수
Citation 수
Citation 누락 수
품질 평가 점수
Token 사용량
추정 API 비용

Phase 10은 동일한 입력과 Metrics를 사용하여 Multi-Agent와 비교한다.

## 17. Phase 9 완료 기준

다음 조건을 모두 충족하면 Phase 9를 완료한다.

Research Request가 엄격한 Schema로 검증된다.
Research Request가 실행 가능한 Research Task로 분해된다.
Task별 Search Query를 생성할 수 있다.
Source Search와 Source Reading이 Tool Port로 분리된다.
Source에서 Evidence를 추출할 수 있다.
Source 품질과 관련성을 평가할 수 있다.
Claim이 Evidence와 Citation에 연결된다.
Workspace가 전체 연구 상태를 추적한다.
Research Synthesizer가 근거 기반 보고서를 생성한다.
Research Quality Evaluator가 구조화된 평가를 반환한다.
전체 Single-Agent Workflow가 E2E 테스트로 검증된다.
Phase 10 비교용 Baseline Metrics를 생성한다.
전체 pytest가 통과한다.
전체 Ruff 검사가 통과한다.

## 18. Phase 9에서 제외하는 기능

다음 기능은 Phase 9 필수 범위에서 제외한다.

Multi-Agent 실행
Agent 간 Message
Manager–Worker Delegation
병렬 Specialist Agent
Debate Agent
복수 실제 검색 Provider
범용 Web Crawler
Browser Automation
영구 데이터베이스
Background Worker
관리자 Dashboard
실제 서비스 배포

Multi-Agent Research System은 Phase 10에서 필수로 구현한다.

## 19. Phase 9 결과

Phase 9 완료 후 AIRA는 다음 능력을 갖는다.

연구 요청 구조화
연구 과제 분해
Search Query 계획
Source 검색과 읽기
Source 품질 평가
Evidence 추출
Claim과 Citation 연결
Research Workspace 관리
근거 기반 Research Report 생성
Research 품질 평가
Single-Agent Baseline Metrics 생성

## 20. Phase 9 실제 구현 결과

Phase 9에서는 계획한 20개 Lesson을 모두 구현하였다.

완성된 Single Research Agent Workflow는 다음 단계로 구성된다.

```text
ResearchRequest
    ↓
ResearchRequestValidator
    ↓
ResearchTaskDecomposer
    ↓
ResearchTaskGraph
    ↓
ResearchQueryPlanner
    ↓
ResearchSearchQuerySet
    ↓
ResearchSourceSearcher
    ↓
ResearchSourceCandidateSet
    ↓
ResearchSourceReader
    ↓
ResearchSourceDocumentSet
    ├── Source Quality Evaluation
    ↓
ResearchEvidenceExtractor
    ↓
ResearchEvidenceSet
    ↓
ResearchClaimBuilder
    ↓
ResearchClaimSet
    ↓
ResearchWorkspace
    ↓
ResearchSynthesizer
    ↓
ResearchSynthesisReport
    ↓
ResearchQualityEvaluator
    ↓
SingleResearchPipelineResult
```

Phase 9의 최종 구현은 외부 검색 Provider나 실제 LLM에 직접 결합되지 않는 결정론적 Baseline이다.

각 단계는 명시적인 Schema 또는 Protocol 계약을 가지며, In-Memory 구현, Fake 구현, 실제 API Adapter 및 LLM 기반 구현으로 교체할 수 있도록 구성하였다.

---

## 21. 구현된 Domain Schema

Phase 9에서 구현한 주요 Domain Schema는 다음과 같다.

### 22.1 Research Request

`ResearchRequest`는 사용자의 연구 요청을 구조화한다.

주요 정보는 다음과 같다.

* Request ID
* 연구 질문
* 연구 목적
* 포함 주제
* 제외 주제
* 선호 Source 유형
* 출력 형식
* Metadata

Research Request Validator는 연구 질문과 목적이 실제 조사에 충분한지 결정론적으로 검증한다.

### 22.2 Research Task와 Task Graph

`ResearchTask`는 하나의 실행 가능한 연구 작업을 표현한다.

각 Task는 다음 정보를 가진다.

* Task ID
* Request ID
* 제목
* 연구 질문
* 목표
* 완료 조건
* 예상 출력
* 선행 Task
* Search 필요 여부
* Metadata

`ResearchTaskGraph`는 Task 간 의존 관계를 검증하고 Topological Order를 제공한다.

Topological Order의 결과는 실행 순서에 따른 Task ID 목록이다.

### 22.3 Research Search Query

`ResearchSearchQuery`는 특정 Research Task를 수행하기 위한 검색 질의를 표현한다.

`ResearchSearchQuerySet`은 다음을 검증한다.

* Query ID의 고유성
* Request ID 일치
* Task ID 존재 여부
* Query 중복 여부
* Query와 Task Graph의 연결

### 22.4 Research Source Candidate

`ResearchSourceCandidate`는 검색 결과에서 발견한 출처 후보를 표현한다.

주요 정보는 다음과 같다.

* Source ID
* Request ID
* Task ID
* Query ID
* 제목
* URL
* Source 유형
* 저자
* 발행기관
* 발행일
* 검색 순위
* Metadata

`ResearchSourceCandidateSet`은 Source Candidate가 실제 Query와 Task를 참조하는지 검증한다.

### 22.5 Research Source Document

`ResearchSourceDocument`는 Source Candidate를 읽고 정규화한 문서이다.

주요 정보는 다음과 같다.

* Document ID
* Source Candidate
* 읽기 상태
* Content Type
* 본문
* Section
* 언어
* Word Count
* Character Count
* Reader
* 오류 정보
* Metadata

읽기 상태를 통해 성공한 Document와 실패한 Document를 구분할 수 있다.

### 22.6 Research Evidence

`ResearchEvidence`는 Source Document에서 추출된 구체적인 근거이다.

주요 정보는 다음과 같다.

* Evidence ID
* Request ID
* Task ID
* Source ID
* Document ID
* Section ID
* Excerpt
* Character Range
* Evidence Type
* Evidence Stance
* Relevance Score
* Confidence Score
* 추출 근거
* Metadata

Evidence Stance는 다음과 같이 구분한다.

* Supports
* Contradicts
* Neutral

Evidence는 반드시 실제 Source Document에 존재하는 범위와 연결되어야 한다.

### 22.7 Research Claim과 Citation

`ResearchClaim`은 하나 이상의 Citation을 통해 Evidence와 연결되는 연구 주장이다.

Claim의 주요 정보는 다음과 같다.

* Claim ID
* Request ID
* Task ID
* Claim Text
* Claim Type
* Claim Status
* Confidence Score
* Citations
* Supporting Evidence IDs
* Contradicting Evidence IDs
* Rationale
* Metadata

Claim Status는 다음과 같이 구분한다.

* Draft
* Supported
* Contested
* Rejected

`ResearchCitation`은 다음 정보를 포함한다.

* Citation ID
* Evidence ID
* Source ID
* Document ID
* Excerpt
* Character Range
* Label
* Metadata

Citation의 Source ID, Document ID, Excerpt 및 Character Range는 연결된 Evidence와 정확히 일치해야 한다.

Supporting Evidence와 Contradicting Evidence는 서로 중복될 수 없다.

Supported Claim은 하나 이상의 Supporting Evidence를 가져야 한다.

Contested Claim은 하나 이상의 Contradicting Evidence를 가져야 한다.

---

## 22. Research Workspace 구현 결과

`ResearchWorkspace`는 하나의 연구 실행에서 생성된 모든 중간 결과를 보관하는 중앙 상태 객체이다.

주요 필드는 다음과 같다.

```text
workspace_id
request
task_graph
query_set
candidate_set
document_set
evidence_set
claim_set
source_quality_evaluations
metadata
```

Workspace는 다음 단계 의존성을 강제한다.

```text
request
    ↓
task_graph
    ↓
query_set
    ↓
candidate_set
    ↓
document_set
    ↓
evidence_set
    ↓
claim_set
```

따라서 다음과 같은 불완전한 상태는 허용하지 않는다.

* Task Graph가 없는 Query Set
* Query Set이 없는 Candidate Set
* Candidate Set이 없는 Document Set
* Document Set이 없는 Evidence Set
* Evidence Set이 없는 Claim Set

Workspace에 포함된 모든 계층은 동일한 Request ID를 사용해야 한다.

Workspace는 현재 진행 단계를 다음과 같이 계산한다.

```text
REQUESTED
DECOMPOSED
QUERIES_PLANNED
SOURCES_DISCOVERED
DOCUMENTS_READ
EVIDENCE_EXTRACTED
CLAIMS_BUILT
```

또한 다음 통계를 제공한다.

* 전체 Task 수
* Search가 필요한 Task 수
* Query 수
* Source Candidate 수
* Document 수
* 읽기 성공 Document 수
* 읽기 실패 Document 수
* Evidence 수
* Claim 수
* Source Quality Evaluation 수

Workspace는 Task별 Query, Candidate, Document, Evidence 및 Claim 조회 기능도 제공한다.

---

## 23. Source Quality Evaluation 구현 결과

`ResearchSourceQualityEvaluator`는 Source Document의 품질을 결정론적으로 평가한다.

평가 항목과 가중치는 다음과 같다.

| 항목             | 가중치 |
| -------------- | --: |
| Authority      | 30% |
| Primary Source | 20% |
| Recency        | 15% |
| Completeness   | 20% |
| Traceability   | 15% |

### Authority

Source 유형에 따라 기본 권위성 점수를 계산한다.

공식 문서와 정부 문서는 높은 점수를 받고, 일반 출처는 상대적으로 낮은 점수를 받는다.

### Primary Source

원 연구, 공식 문서 및 정부 문서처럼 원 자료에 가까운 출처에 높은 점수를 부여한다.

### Recency

기준일과 발행일 사이의 기간에 따라 최신성을 계산한다.

발행일이 없는 Source는 낮은 기본 점수를 받는다.

### Completeness

다음 정보를 기반으로 계산한다.

* 본문 길이
* Section 존재 여부
* 언어 정보 존재 여부

### Traceability

다음 정보의 존재 여부를 평가한다.

* URL
* 저자
* 발행기관
* 발행일

최종 Source Quality Level은 다음 기준으로 결정한다.

```text
EXCELLENT  overall_score >= 0.85
HIGH       overall_score >= 0.70
MEDIUM     overall_score >= 0.45
LOW        overall_score < 0.45
```

평가 결과에는 점수 외에도 Strength와 Limitation을 포함할 수 있다.

---

## 24. Research Synthesis 구현 결과

`DeterministicResearchSynthesizer`는 Research Workspace의 Claim과 Citation을 구조화된 Research Report로 변환한다.

Synthesizer는 다음 원칙을 적용한다.

1. Task Graph의 Topological Order를 따른다.
2. Claim이 있는 Task만 Report Section으로 생성한다.
3. Claim 순서를 결정론적으로 유지한다.
4. Citation Label을 `[1]`, `[2]` 형식으로 생성한다.
5. 같은 Evidence는 Report Citation Registry에 한 번만 등록한다.
6. Citation을 실제 Evidence와 Source Document에 연결한다.
7. 동일한 Workspace에 대해 동일한 Report를 생성한다.

최종 `ResearchSynthesisReport`는 다음 정보를 포함한다.

* Report ID
* Workspace ID
* Request ID
* 제목
* Executive Summary
* Task별 Section
* Report-level Citation
* Claim Count
* Citation Count
* Source Count
* Synthesizer 이름
* Metadata

각 Report Section은 다음 정보를 포함한다.

* Section ID
* Task ID
* 제목
* 내용
* 순서
* Claim IDs
* Citation IDs
* Metadata

Report Citation은 다음 정보를 포함한다.

* Citation ID
* Evidence ID
* Source ID
* Document ID
* Citation Label
* Source 제목
* Source URL
* Evidence Excerpt

---

## 25. Final Research Quality Evaluation 구현 결과

`ResearchQualityEvaluator`는 완성된 Research Report를 원래 Workspace와 비교하여 품질을 평가한다.

평가 항목과 가중치는 다음과 같다.

| 평가 항목                  | 가중치 |
| ---------------------- | --: |
| Claim Coverage         | 30% |
| Citation Coverage      | 25% |
| Source Diversity       | 15% |
| Source Quality         | 20% |
| Contradiction Handling | 10% |

### Claim Coverage

Workspace의 Claim이 Report Section에 포함된 비율을 계산한다.

### Citation Coverage

Workspace Claim이 Report Citation에 연결된 비율을 계산한다.

### Source Diversity

Claim 수에 비해 서로 다른 Source가 충분히 사용되었는지 평가한다.

현재 Baseline에서는 최대 세 개의 독립 Source를 목표값으로 사용한다.

### Source Quality

Workspace에 포함된 Source Quality Evaluation의 평균 점수를 사용한다.

Source Quality Evaluation이 없을 경우 중립 기본값인 `0.5`를 사용한다.

### Contradiction Handling

Contradicting Evidence가 존재하는 Claim이 `CONTESTED` 상태로 처리되었는지 평가한다.

최종 품질 등급은 다음과 같다.

```text
EXCELLENT  overall_score >= 0.90
HIGH       overall_score >= 0.75
MEDIUM     overall_score >= 0.50
LOW        overall_score < 0.50
```

구조화된 Quality Issue는 다음과 같다.

```text
MISSING_CLAIMS
UNCITED_CLAIMS
LOW_SOURCE_DIVERSITY
LOW_SOURCE_QUALITY
UNHANDLED_CONTRADICTIONS
```

Issue Severity는 Warning과 Error로 구분한다.

Error Issue가 하나도 없으면 `ResearchQualityEvaluation.passed`는 `True`이다.

---

## 26. Single Research Agent Pipeline 구현 결과

`SingleResearchAgentPipeline`은 Phase 9의 전체 연구 Workflow를 하나의 실행 흐름으로 연결한다.

Pipeline 구성요소는 Protocol을 통해 주입된다.

```text
ResearchRequestValidatorProtocol
ResearchTaskDecomposerProtocol
ResearchQueryPlannerProtocol
ResearchSourceSearcherProtocol
ResearchSourceReaderProtocol
ResearchEvidenceExtractorProtocol
ResearchClaimBuilderProtocol
ResearchSourceQualityEvaluatorProtocol
```

Report Synthesizer와 Research Quality Evaluator도 생성자에서 교체할 수 있다.

Pipeline의 전체 실행 순서는 다음과 같다.

```text
Request Validation
    ↓
Task Decomposition
    ↓
Query Planning
    ↓
Source Search
    ↓
Source Reading
    ↓
Evidence Extraction
    ↓
Claim Building
    ↓
Source Quality Evaluation
    ↓
Workspace Construction
    ↓
Report Synthesis
    ↓
Final Quality Evaluation
    ↓
SingleResearchPipelineResult
```

Pipeline은 다음 조건에서 명시적으로 실행을 중단한다.

* Workspace ID가 비어 있음
* Task Decomposition 결과가 비어 있음
* Query Planning 결과가 비어 있음
* Source Search 결과가 비어 있음
* 읽을 수 있는 Document가 없음
* Evidence Extraction 결과가 비어 있음
* Claim Building 결과가 비어 있음

최종 `SingleResearchPipelineResult`는 다음 세 객체를 포함한다.

```text
workspace
report
quality
```

Pipeline Result는 다음 일관성을 검증한다.

* Report의 Workspace ID와 Workspace의 ID가 일치해야 한다.
* Report의 Request ID와 Workspace Request ID가 일치해야 한다.
* Quality Evaluation이 참조하는 Report와 Pipeline Report가 일치해야 한다.

---

## 27. 테스트 및 검증 결과

Phase 9에서는 다음 계층의 테스트를 구현하였다.

### Schema Test

각 Domain Schema에 대해 다음을 검증하였다.

* 필수 문자열의 공백 값 거부
* 점수 범위 검증
* 중복 ID 거부
* Request ID 일치
* 존재하지 않는 객체 참조 거부
* Evidence와 Citation의 Source 및 범위 일치
* 상태와 필수 데이터 관계 검증
* Metadata 검증
* 불변 객체 검증

### Component Test

다음 Component를 독립적으로 테스트하였다.

* Research Request Validator
* Research Task Decomposer
* Research Query Planner
* In-Memory Source Search Adapter
* In-Memory Source Reader
* Research Evidence Extractor
* Research Source Quality Evaluator
* Deterministic Research Synthesizer
* Research Quality Evaluator

### Workspace Integration Test

다음 항목을 검증하였다.

* 단계별 의존성
* 각 계층의 Request ID 일치
* Embedded Set 연결
* Source Quality Evaluation과 Document 연결
* Workspace Stage 계산
* Progress Count
* Task별 객체 조회
* Document별 품질 평가 조회
* 동일 입력의 결정론적 결과

### Pipeline End-to-End Test

Fake Component를 주입하여 다음 전체 흐름을 검증하였다.

```text
Research Request
→ Task
→ Query
→ Source Candidate
→ Source Document
→ Evidence
→ Claim
→ Workspace
→ Research Report
→ Research Quality Evaluation
```

E2E Test에서는 다음 항목을 확인하였다.

* 기본 Workspace ID 생성
* 사용자 지정 Workspace ID 적용
* 각 단계별 객체 수
* Report의 Claim, Citation 및 Source 수
* Claim Coverage
* Citation Coverage
* 최종 Pass 여부
* 빈 Source Search 결과 처리
* 동일 입력에 대한 동일 Pipeline Result

Phase 9 완료 시 다음 명령이 모두 성공해야 한다.

```bash
python -m pytest -q
```

```bash
ruff check .
```

또한 다음 명령에서 오류가 없어야 한다.

```bash
git diff --check
```

---

## 28. Phase 9의 주요 설계 결정

### 결정 1: Evidence를 Claim보다 먼저 생성한다

최종 보고서를 먼저 작성한 후 Citation을 붙이는 방식을 사용하지 않는다.

Source Document에서 Evidence를 먼저 추출하고, Evidence를 기반으로 Claim을 생성한다.

### 결정 2: 결정론적 검증과 불확실한 판단을 분리한다

ID, 참조 관계, 단계 순서, 점수 범위 및 Citation 범위는 코드로 검증한다.

Task 분해, Evidence 해석, Claim 생성 및 자연어 합성처럼 불확실한 작업은 향후 LLM 구현으로 교체할 수 있다.

### 결정 3: 외부 시스템은 Protocol과 Adapter로 분리한다

검색 Provider, Source Reader, Evidence Extractor 및 Claim Builder를 Pipeline에 직접 결합하지 않는다.

Protocol 계약을 구현하는 Adapter를 주입한다.

### 결정 4: Workspace는 불완전한 단계 구성을 허용하지 않는다

이전 단계가 없는 상태에서 이후 단계 결과만 추가할 수 없도록 한다.

이를 통해 Research State의 구조적 일관성을 보장한다.

### 결정 5: 최종 Claim은 Source URL까지 추적할 수 있어야 한다

다음 연결을 유지한다.

```text
Claim
→ Citation
→ Evidence
→ Document
→ Source Candidate
→ URL
```

### 결정 6: Source Quality와 Report Quality를 분리한다

Source Quality는 개별 Document의 품질을 평가한다.

Report Quality는 전체 Claim, Citation, Source Diversity 및 Contradiction Handling을 평가한다.

### 결정 7: Phase 9는 Single-Agent Baseline으로 제한한다

Agent 간 Message, 역할별 Delegation, 병렬 실행 및 Debate는 Phase 10에서 구현한다.

Phase 9에서는 Multi-Agent와 비교할 수 있는 안정적인 Single-Agent 기준선을 우선 완성한다.

---

## 29. 현재 Baseline의 한계

### 30.1 실제 외부 검색 Provider 미연결

현재 테스트와 Baseline 실행은 In-Memory 또는 Fake Source Searcher를 사용한다.

실제 Search API, Rate Limit, 네트워크 오류 및 검색 결과 변동성은 아직 포함하지 않는다.

### 30.2 실제 웹 문서 Reader 미구현

HTML, PDF, JavaScript 기반 페이지, 인증이 필요한 문서 및 대형 파일 처리는 현재 Baseline 범위에 포함하지 않는다.

### 30.3 LLM 기반 Research Reasoning 미적용

현재 Pipeline은 LLM 구현을 주입할 수 있는 구조를 가지지만, E2E Baseline은 결정론적 또는 Fake Component를 사용한다.

고급 Task Decomposition, 의미 기반 Evidence Extraction, Claim 통합 및 자연스러운 보고서 작성은 향후 LLM Adapter에서 구현해야 한다.

### 30.4 영구 저장과 Resume 미지원

Research Workspace는 메모리 내 객체로 관리된다.

Database 저장, Checkpoint, Resume, Background Job 및 장기 실행 상태 복구는 Phase 12 이후 범위이다.

### 30.5 단일 Pipeline 실패 정책

현재는 핵심 단계가 빈 결과를 반환하면 Pipeline을 중단한다.

Retry, Fallback Provider, Partial Success 및 Human Review Queue는 아직 없다.

### 30.6 제한적인 Source Diversity 평가

현재 Source Diversity는 Claim 수와 고유 Source 수를 중심으로 계산한다.

출처 기관, 저자, 도메인, 국가, 연구 방법 및 관점의 독립성은 아직 평가하지 않는다.

### 30.7 제한적인 Contradiction Handling

현재는 Contradicting Evidence가 존재하는 Claim이 `CONTESTED` 상태인지 검사한다.

서로 다른 Claim 사이의 논리적 충돌, Evidence 강도 비교 및 최종 판단 근거 생성은 향후 확장 대상이다.

---

## 30. Phase 9 완료 판정

Phase 9는 다음 조건을 충족하므로 완료 상태로 판정한다.

* Research Request Schema 구현 완료
* Research Task 및 Task Graph 구현 완료
* Research Request Validator 구현 완료
* Research Task Decomposer 구현 완료
* Search Query Schema와 Planner 구현 완료
* Source Candidate Schema 구현 완료
* Source Search Tool Contract 구현 완료
* In-Memory Source Search Adapter 구현 완료
* Source Document Schema 구현 완료
* Source Reader Contract와 In-Memory Reader 구현 완료
* Evidence Schema 구현 완료
* Evidence Extractor Contract 구현 완료
* Source Quality Evaluation 구현 완료
* Claim과 Citation Schema 구현 완료
* Research Workspace 구현 완료
* Research Synthesizer 구현 완료
* Research Quality Evaluator 구현 완료
* Single Research Agent Pipeline 구현 완료
* Pipeline E2E Test 구현 완료
* 전체 pytest 통과
* 전체 Ruff 검사 통과
* Phase 9 문서화 완료
* Phase 9 Baseline Report 작성

Phase 9의 최종 완료 정의는 다음과 같다.

```text
하나의 구조화된 Research Request를 입력받아
Research Task, Search Query, Source Candidate,
Source Document, Evidence, Claim, Citation,
Research Workspace, Research Report 및
Research Quality Evaluation까지 생성하고
각 단계의 구조와 참조 관계를 검증할 수 있다.
```

Phase 9의 구현 결과는 Phase 10 Multi-Agent Research System과 성능, 품질, 비용 및 복잡도를 비교하기 위한 Single-Agent Baseline으로 사용한다.

---

## 31. Phase 10 진입 기준

Phase 10에서는 Phase 9의 Domain Schema와 Component를 새로 다시 구현하지 않는다.

다음 기존 자산을 재사용한다.

* Research Request
* Research Task Graph
* Search Query
* Source Candidate
* Source Document
* Source Quality Evaluation
* Evidence
* Claim과 Citation
* Research Workspace
* Research Synthesis Report
* Research Quality Evaluation

Phase 10에서는 이 Component들을 전문 Agent 역할로 분리한다.

후보 역할은 다음과 같다.

```text
Research Manager Agent
├── Search Agent
├── Source Reader Agent
├── Evidence Analyst Agent
├── Source Critic Agent
├── Claim Agent
├── Citation Verifier Agent
├── Synthesis Agent
└── Quality Reviewer Agent
```

Phase 10에서 추가할 핵심 기능은 다음과 같다.

* Agent Identity
* Agent Role
* Agent Message
* Agent Task Assignment
* Manager–Worker Delegation
* Shared Research Workspace
* Agent별 Tool 권한
* 병렬 Specialist 실행
* Agent Result Review
* Critic Feedback
* Revision Loop
* Stop Condition
* Single-Agent와 Multi-Agent 비교 Evaluation

Phase 10은 Phase 9와 동일한 Research Request 및 Quality Evaluation 기준을 사용해야 한다.

이를 통해 Multi-Agent 구조가 Single-Agent Baseline보다 실제로 품질을 개선하는지, 또는 비용과 복잡성만 증가시키는지를 검증한다.

## 32. 다음 Phase

Phase 10에서는 Phase 9의 Single Research Agent를 Baseline으로 사용하여
Multi-Agent Research System을 구축한다.

필수 구성은 다음과 같다.

Research Manager Agent
Search Agent
Source Reader Agent
Evidence Analyst Agent
Citation Verifier Agent
Critic Agent
Report Writer Agent
Shared Research Workspace
Agent Task Delegation
Agent Message
Agent별 Tool 권한
Stop Condition
Single-Agent와 Multi-Agent 비교 Evaluation
