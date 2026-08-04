# Phase 9 Baseline Report

## 1. Report Overview

| 항목              | 내용                                             |
| --------------- | ---------------------------------------------- |
| Phase           | Phase 9                                        |
| System          | AIRA — Agentic Intelligence Research Assistant |
| Baseline        | Single Research Agent Workflow                 |
| Execution Model | Sequential deterministic pipeline              |
| Validation      | Pydantic schemas and model validators          |
| Test Framework  | pytest                                         |
| Static Analysis | Ruff                                           |
| External Search | Not connected in baseline E2E                  |
| LLM Synthesis   | Not used in deterministic baseline             |
| Next Phase      | Phase 10 Multi-Agent Research System           |

---

## 2. Baseline Objective

Phase 9의 목표는 하나의 Research Agent가 연구 요청을 받아 최종 보고서와 품질 평가까지 생성하는 전체 Workflow를 구축하는 것이었다.

핵심 목표는 자연어 결과를 빠르게 생성하는 것이 아니라 다음을 보장하는 것이었다.

* 각 단계의 입력과 출력이 명확할 것
* 잘못된 참조가 조기에 거부될 것
* Claim이 Evidence와 Source까지 추적될 것
* 동일 입력에서 동일 결과가 생성될 것
* 각 구성요소를 교체할 수 있을 것
* 전체 Workflow를 End-to-End로 테스트할 수 있을 것

---

## 3. Completed Capabilities

Phase 9에서 다음 기능을 구현하였다.

### Research Request

* 연구 질문
* 연구 목적
* 포함 및 제외 주제
* 선호 출처 유형
* 출력 형식
* 요청 식별자

### Research Planning

* Research Task 생성
* Task Graph 생성
* Task 의존성 검증
* Topological Order 생성
* Task별 Search Query 생성

### Source Discovery

* Source Candidate 구조화
* Source Search Tool Contract
* In-Memory Search Adapter
* Query와 Candidate 연결 검증

### Source Reading

* 읽기 성공 및 실패 상태
* Source Content
* Section
* Word Count
* Character Count
* Reader 정보
* In-Memory Reader Adapter

### Evidence

* Evidence ID
* Request ID
* Task ID
* Source ID
* Document ID
* Excerpt
* Character Range
* Evidence Type
* Evidence Stance
* Relevance Score
* Confidence Score

### Source Quality

* Authority Score
* Primary Source Score
* Recency Score
* Completeness Score
* Traceability Score
* Overall Score
* Quality Level
* Strengths
* Limitations

### Claims and Citations

* Claim Type
* Claim Status
* Confidence Score
* Citation
* Supporting Evidence
* Contradicting Evidence
* Citation과 Evidence 일치 검증

### Research Workspace

* 전체 연구 상태 통합
* 단계 의존성 검증
* Request ID 일관성 검증
* 단계별 진행 상태
* Task별 객체 조회
* Source Quality 연결

### Research Synthesis

* Task별 Section 생성
* Claim 배열
* Inline Citation Label
* Report-level Citation Registry
* Executive Summary
* Source Reference

### Research Quality

* Claim Coverage
* Citation Coverage
* Source Diversity
* Source Quality
* Contradiction Handling
* Overall Quality Score
* Quality Issue
* Pass/Fail

### Pipeline

* Protocol 기반 의존성 주입
* 전체 단계 순차 실행
* 각 단계의 빈 결과 감지
* Workspace 생성
* Report 생성
* Quality Evaluation 생성
* Pipeline Result 검증
* End-to-End 테스트

---

## 4. Baseline Architecture

```text
SingleResearchAgentPipeline
│
├── RequestValidator
├── TaskDecomposer
├── QueryPlanner
├── SourceSearcher
├── SourceReader
├── EvidenceExtractor
├── ClaimBuilder
├── SourceQualityEvaluator
├── ResearchSynthesizer
└── ResearchQualityEvaluator
```

각 구성요소는 독립적인 책임을 가진다.

Pipeline은 구성요소의 내부 구현을 알 필요가 없으며 지정된 계약만 사용한다.

---

## 5. Determinism Baseline

Phase 9는 다음 항목에서 결정론을 검증한다.

| 대상              | 결정론적 기준                                |
| --------------- | -------------------------------------- |
| Task Graph      | 동일 Request에서 동일 Task 구조                |
| Query Set       | 동일 Task에서 동일 Query                     |
| Candidate Set   | 동일 Source Registry에서 동일 순서             |
| Document Set    | 동일 Candidate에서 동일 Document             |
| Evidence Set    | 동일 Document에서 동일 Evidence              |
| Claim Set       | 동일 Evidence에서 동일 Claim                 |
| Report          | 동일 Workspace에서 동일 Section과 Citation    |
| Quality         | 동일 Workspace와 Report에서 동일 Score와 Issue |
| Pipeline Result | 동일 Request에서 동일 전체 JSON 결과             |

결정론 검증은 `model_dump(mode="json")` 결과 비교를 통해 수행한다.

---

## 6. Traceability Baseline

최종 보고서의 각 Claim은 다음 경로로 추적된다.

```text
Report Section
  → Claim ID
    → ResearchClaim
      → ResearchCitation
        → ResearchEvidence
          → ResearchSourceDocument
            → ResearchSourceCandidate
              → Source URL
```

Citation의 Source ID, Document ID, Excerpt 및 Character Range는 Evidence와 일치해야 한다.

이 구조는 근거 없는 Citation 생성이나 잘못된 문서 연결을 방지한다.

---

## 7. Quality Scoring Baseline

### 7.1 Source Quality

```text
Authority       30%
Primary Source  20%
Recency         15%
Completeness    20%
Traceability    15%
```

### 7.2 Final Report Quality

```text
Claim Coverage          30%
Citation Coverage       25%
Source Diversity        15%
Source Quality          20%
Contradiction Handling  10%
```

### 7.3 Final Quality Level

```text
EXCELLENT  >= 0.90
HIGH       >= 0.75
MEDIUM     >= 0.50
LOW        < 0.50
```

---

## 8. Failure Detection Baseline

Phase 9 Pipeline은 다음 실패를 명시적으로 감지한다.

| 단계             | 실패 조건                      |
| -------------- | -------------------------- |
| Workspace      | 빈 Workspace ID             |
| Decomposition  | Task 없음                    |
| Query Planning | Query 없음                   |
| Search         | Candidate 없음               |
| Reading        | 읽을 수 있는 Document 없음        |
| Extraction     | Evidence 없음                |
| Claim Building | Claim 없음                   |
| Synthesis      | Task Graph 또는 Claim Set 없음 |
| Quality        | Report와 Workspace 식별자 불일치  |
| Result         | Quality가 다른 Report를 참조함    |

---

## 9. Test Baseline

Phase 9의 완료 여부는 다음 명령으로 검증한다.

```bash
python -m pytest -q
```

```bash
ruff check .
```

완료 기준:

```text
모든 테스트 통과
Ruff 오류 0개
Git Working Tree Clean
Local main과 origin/main 일치
```

최종 테스트 개수는 저장소의 전체 Regression Test 실행 결과를 기준으로 기록한다.

---

## 10. Strengths

### 10.1 명확한 단계 분리

각 연구 단계가 독립된 Schema와 Component로 분리되어 있다.

### 10.2 강한 데이터 검증

잘못된 ID, 중복 참조, 범위 불일치 및 단계 누락을 조기에 탐지한다.

### 10.3 완전한 추적 구조

최종 Claim에서 Source URL까지 역추적 가능하다.

### 10.4 교체 가능한 구성요소

실제 Search API, LLM 및 외부 Reader를 Protocol 구현으로 교체할 수 있다.

### 10.5 재현 가능한 Baseline

동일한 입력과 동일한 Component에서 동일한 결과가 생성된다.

### 10.6 Multi-Agent 확장 준비

현재 Pipeline Component를 향후 전문 Agent 역할로 분리할 수 있다.

---

## 11. Limitations

### 11.1 외부 검색 부재

현재 E2E Baseline은 Fake Component를 사용한다.

따라서 실제 인터넷 검색 품질, Search API 오류 및 Rate Limit은 검증하지 않았다.

### 11.2 실제 문서 파싱 부재

HTML, PDF, 표, 이미지, JavaScript 기반 페이지 및 접근 제한 문서 처리는 아직 포함하지 않는다.

### 11.3 LLM 추론 부재

Task Decomposition, Evidence Interpretation, Claim Building 및 Report Synthesis의 고급 추론은 아직 결정론적 또는 Fake 구현 수준이다.

### 11.4 장기 실행 상태 부재

Workspace는 구조화되어 있지만 데이터베이스 저장, Checkpoint, Resume 및 Background Job은 아직 구현하지 않았다.

### 11.5 단일 실패 경로

현재 Pipeline은 한 단계가 실패하면 전체 실행이 중단된다.

Retry, Partial Success, Fallback 및 Human Review Queue가 없다.

### 11.6 다중 에이전트 검증 부재

한 Agent의 결과를 다른 Agent가 독립적으로 검토하거나 반박하지 않는다.

---

## 12. Risk Register

| 위험             | 영향 | 현재 대응                  | 향후 대응                        |
| -------------- | -- | ---------------------- | ---------------------------- |
| 근거 없는 Claim    | 높음 | Citation-Evidence 검증   | Claim Reviewer Agent         |
| 낮은 품질 출처       | 높음 | Source Quality Score   | Source Critic Agent          |
| 단일 출처 의존       | 중간 | Source Diversity Score | Search Diversity Agent       |
| 상반된 근거 누락      | 높음 | Contradiction Handling | Debate and Review Loop       |
| 검색 실패          | 높음 | Empty Candidate Error  | Retry and Fallback           |
| 문서 읽기 실패       | 중간 | Read Status            | Reader Pool                  |
| LLM 비결정성       | 높음 | Deterministic Baseline | Evals and constrained output |
| 장기 실행 중단       | 높음 | 미구현                    | Persistence and Checkpoint   |
| Pipeline 결합 증가 | 중간 | Protocol DI            | Agent message contracts      |

---

## 13. Phase 10 Comparison Baseline

Phase 10은 Phase 9와 다음 기준으로 비교한다.

| 비교 항목  | Phase 9 Single Agent | Phase 10 목표            |
| ------ | -------------------- | ---------------------- |
| 역할 구조  | 하나의 Pipeline         | 전문 Agent 분리            |
| 실행     | 순차 실행                | 병렬 및 협업 가능             |
| 검토     | 단일 품질 평가             | 독립 Reviewer Agent      |
| 반론     | 단순 상태 검증             | Critic 및 Debate        |
| 실패 복구  | 즉시 중단                | Retry, Reassignment    |
| 메시지    | 함수 호출                | Agent Message Contract |
| 상태 관리  | 단일 Workspace         | Shared Workspace       |
| 승인     | 자동 반환                | Manager 승인             |
| 관찰 가능성 | Pipeline Result      | Agent Event 및 Trace    |
| 품질 개선  | 점수 계산                | 반복 수정 Loop             |

---

## 14. Phase 10 Entry Decision

Phase 9 Baseline은 다음 이유로 Phase 10 진입에 적합하다.

1. 전체 연구 Workflow가 End-to-End로 연결되었다.
2. 각 단계의 입력 및 출력 계약이 존재한다.
3. 구성요소를 Protocol로 교체할 수 있다.
4. Workspace가 공유 상태 역할을 할 수 있다.
5. Claim과 Evidence의 추적 구조가 완성되었다.
6. Report Quality를 정량적으로 평가할 수 있다.
7. 결정론적 Baseline과 Regression Test가 존재한다.

따라서 Phase 10에서는 기능을 새로 처음부터 만드는 대신 Phase 9 Component를 전문 Agent로 분리하고 협업 구조를 추가한다.

---

## 15. Phase 9 Final Status

```text
STATUS: COMPLETE

Single Research Agent Workflow:
- Request validation: complete
- Task decomposition: complete
- Query planning: complete
- Source candidate modeling: complete
- Source reading contract: complete
- Evidence modeling and extraction contract: complete
- Source quality evaluation: complete
- Claim and citation modeling: complete
- Central workspace: complete
- Deterministic synthesis: complete
- Final quality evaluation: complete
- Pipeline orchestration: complete
- End-to-end tests: complete
- Documentation: complete
- Baseline report: complete
```

---

## 16. Next Step

다음 단계:

```text
Phase 10 — Multi-Agent Research System
```

Phase 10에서는 Phase 9의 Single Pipeline을 다음과 같은 협업 구조로 확장한다.

```text
Research Manager
├── Search Agent
├── Source Reader Agent
├── Evidence Agent
├── Source Critic Agent
├── Claim Agent
├── Synthesis Agent
└── Quality Reviewer Agent
```

Phase 9의 Schema, Workspace, Report 및 Quality Evaluation은 Phase 10에서도 재사용한다.
