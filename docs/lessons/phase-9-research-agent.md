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

## 18. Phase 9 완료 기준

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

## 19. Phase 9에서 제외하는 기능

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

## 20. Phase 9 결과

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

## 21. 다음 Phase

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
