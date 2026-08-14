# Agentic AI Lab — ROADMAP

## 1. 문서 목적

본 문서는 AIRA(Agentic Intelligence Research Assistant)의 현재 위치,
향후 제품 통합 Stage, Integration Work Item, 공통 Gate 및 완료 기준을 관리한다.

문서 역할은 다음과 같이 구분한다.

- `AIRA_PROJECT_CHARTER.md`: 최종 제품 목표와 최상위 원칙
- `MASTER.md`: 프로젝트 운영·개발·학습 원칙
- `DECISIONS.md`: 확정 결정과 변경 이력
- `ROADMAP.md`: 현재 위치와 향후 실행 순서
- `AIRA_PROJECT_AUDIT_REPORT.md`: 실제 저장소 감사 결과
- `AIRA_TARGET_ARCHITECTURE.md`: 목표 Runtime Architecture
- `AIRA_INTEGRATION_PLAN.md`: 구체적인 통합 Work Item

기존 Phase 0부터 Phase 13까지는 완료된 학습 및 구현 이력으로 보존한다.

향후 AIRA 제품 통합은 신규 Phase 번호보다 Stage와 Integration Work Item으로
관리한다.

---

## 2. 진행 상태 표기

- `[ ]` 시작 전
- `[~]` 진행 중
- `[x]` 완료
- `[!]` 보충 또는 재검증 필요
- `[-]` 보류
- `[?]` Existing Capability Audit에서 확인 필요

---

## 3. 현재 위치

- 기존 학습 Phase: Phase 0부터 Phase 13까지 완료
- 현재 제품 단계: Stage 3 핵심 Single-Agent Live Research 완료 → Stage 4 Local Document Expansion 진행 중
- 현재 상태: Live Research 기준선을 유지하면서 Local TXT/Markdown, text-based PDF 및 text-bearing HWPX
  Semantic Research Vertical Slices를 통합·검증 완료했다. Stage 4의 HWP binary 확장,
  scanned PDF/OCR 및 Integrated Web+Local RAG는 아직 진행 전이다.
- 현재 기준일: 2026-08-14
- 기본 개발 경로: `/home/moon/Project/agentic-ai-lab`
- 기본 실행 전략: LLM 기반 Single Research Agent 우선
- 기본 관리 방식:
  - ChatGPT `Agentic AI Lab` 프로젝트가 전체 프로젝트를 총괄한다.
  - Codex가 실제 저장소 감사·구현·테스트의 주 실행 도구를 담당한다.
  - 기존 코드를 감사하고 최대한 재사용한다.

현재 완료 또는 작성된 기준 문서:

- [x] `AIRA_PROJECT_CHARTER.md`
- [x] `DECISIONS.md` 재정렬
- [x] `MASTER.md` 재정렬
- [x] `ROADMAP.md` 재정렬
- [x] `AIRA_PROJECT_AUDIT_REPORT.md`
- [x] `AIRA_CAPABILITY_MATRIX.md`
- [x] `AIRA_TARGET_ARCHITECTURE.md`
- [x] `AIRA_INTEGRATION_PLAN.md`
- [x] `AIRA_SEARCH_PROVIDER_DECISION.md`

다음 문서 점검 순서:

- [ ] `CURRICULUM.md`
- [ ] `AGENTS.md`
- [ ] `README.md`
- [ ] `LEARNING_LOG.md`
- [ ] 기타 기존 핵심 문서

현재 검증 기준:

- 기준일: 2026-08-08
- Python: `3.12.3`
- pytest: `9.1.1`
- Ruff: `0.16.0`
- Step 6.5 최종 전체 Regression: `4468 passed in 10.19s`
- Ruff: `All checks passed`
- `git diff --cached --check`: 통과
- Step 6.5 Checkpoint Commit: `640df8a`
- Commit Message: `feat: add research run observability and latency metrics`
- `origin/main` Push 완료
- Research Run Observability, Structured Output Recovery, Evidence Semantic Usage
  계측 및 관련 Regression을 포함한 현재 Checkpoint가 전체 검증을 통과했다.

판정 원칙:

- 전체 테스트 통과는 코드 기준선의 안정성을 의미한다.
- Fake 또는 Stub 기반 테스트 통과가 실제 외부 API 실행을 의미하지는 않는다.
- Implemented, Tested, Runtime-connected 및 Production-ready 상태를 계속
  구분한다.

---

## 4. 완료된 기존 학습·구현 Phase

- [x] Phase 0 — 프로젝트 기반
- [x] Phase 1 — Agentic AI 기초
- [x] Phase 2 — OpenAI API 기초
- [x] Phase 3 — Structured Outputs와 데이터 검증
- [x] Phase 4 — Tool Calling
- [x] Phase 5 — Workflow와 상태 관리
- [x] Phase 6 — RAG
- [x] Phase 7 — Memory
- [x] Phase 8 — Planning Agent
- [x] Phase 9 — Single Research Agent
- [x] Phase 10 — 제한된 Multi-Agent Research
- [x] Phase 11 — Evals, Guardrails, Reliability
- [x] Phase 12 — Application, Persistence, Background Jobs
- [x] Phase 13 — Practical AIRA Integration and Delivery

위 Phase들은 다음 목적으로 유지한다.

- Agentic AI 핵심 개념 학습 이력
- 개별 Component 구현 이력
- Existing Capability Audit의 조사 대상
- 향후 AIRA 통합 시 재사용 가능한 코드 자산
- Regression 및 비교 기준

---

## 5. 기존 Phase 13 Baseline

### 상태

- 완료된 Baseline
- 최종 AIRA는 아님

### 유지 목적

- 결정론적 Offline Research Baseline
- Schema 검증
- Pipeline Regression Test
- 외부 API 없는 실행 경로
- 제한된 Fallback
- 향후 LLM 기반 AIRA와의 비교 기준

### 확인된 또는 확인이 필요한 한계

- [!] 인터넷 검색이 기본 Runtime에 연결되지 않음
- [!] 외부 LLM이 기본 실행 경로에 연결되지 않음
- [!] 기존 RAG와 Phase 13 Pipeline의 통합 부족
- [!] 동적 Tool 선택 제한
- [!] Evidence Sufficiency 기반 Replanning 제한
- [!] Memory의 실제 Runtime 연결 부족
- [!] Provider 교체 구조의 실제 Runtime 검증 부족
- [!] 다수 Source의 의미 기반 비교·충돌 분석 제한
- [!] Usage와 Cost 계산의 실제 Agent Budget 연결 여부 재확인 필요

---

## 6. 감사 대상인 기존 핵심 자산

다음 기능은 기존 Phase에서 구현되었거나 관련 코드와 테스트가 존재하는 것으로
기록되어 있다.

실제 재사용 여부는 Stage 1 Existing Capability Audit에서 확인한다.

각 항목은 다음 상태로 분류한다.

- Implemented
- Tested
- Runtime-connected
- Production-ready

### 6.1 LLM 및 OpenAI

- [?] OpenAI API Client
- [?] OpenAI Responses API 호출
- [?] OpenAI Python SDK
- [?] Client Factory
- [?] 환경변수와 Secret 처리
- [?] Structured Outputs
- [?] Tool Definition
- [?] Tool Call 처리
- [?] Tool Result 반환
- [?] Multi-turn Tool Loop
- [?] Retry와 Timeout
- [?] 실제 API Smoke Test
- [?] Fake 또는 Stub Client Test

### 6.2 Tool 및 Workflow

- [?] Tool Registry
- [?] Tool 입력·출력 검증
- [?] Tool Execution
- [?] Tool Permission
- [?] Workflow
- [?] State 관리
- [?] Scheduler
- [?] Retry
- [?] Cancellation
- [?] Failure Mapping
- [?] Idempotency

### 6.3 RAG 및 문서 처리

- [?] TXT Reader
- [?] Markdown Reader
- [?] PDF Reader
- [?] HWP 또는 HWPX 관련 구현
- [?] Document Normalization
- [?] Chunker
- [?] Keyword Search
- [?] Embedding Provider
- [?] Vector Retriever
- [?] Hybrid Retrieval
- [?] Reranker
- [?] Context Builder
- [?] Citation Evaluator
- [?] Abstention Evaluator
- [?] Grounded Answer 생성

### 6.4 Research Agent

- [?] Research Request
- [?] Task 분해
- [?] Search Query Planning
- [?] Source Search Port
- [?] Source Reader Port
- [?] Evidence 추출
- [?] Source 품질 평가
- [?] Claim 생성
- [?] Claim과 Citation 연결
- [?] Research Workspace
- [?] Report Synthesis
- [?] Single Research Agent
- [?] Multi-Agent Coordinator
- [?] Specialist Agent
- [?] Replanning
- [?] Agent Loop
- [?] 종료 조건

### 6.5 Memory

- [?] Working State
- [?] Memory Store
- [?] Memory Search
- [?] Context Builder
- [?] Deduplication
- [?] Relevance Policy
- [?] Sensitive Data Detection
- [?] Sanitization
- [?] Long-term Memory Policy

### 6.6 품질·안전·신뢰성

- [?] Evaluation Dataset
- [?] Evaluation Runner
- [?] Retrieval Eval
- [?] Citation Eval
- [?] Evidence Coverage Eval
- [?] Claim Support Eval
- [?] Guardrail
- [?] Prompt Injection 방어
- [?] Reliability Metrics
- [?] E2E Evaluation
- [?] Tracing

### 6.7 Usage 및 비용

- [?] API Usage 수집
- [?] Input Token 계산
- [?] Output Token 계산
- [?] Cached Token 처리
- [?] Model Price Registry
- [?] 가격 기준일 관리
- [?] 실행 전 예상비용
- [?] 실행 후 실제비용
- [?] 실행별 비용 저장
- [?] 누적비용 관리
- [?] Budget Guardrail
- [?] Budget 초과 중단
- [?] Search API 비용 확장 가능성

### 6.8 Application 및 Persistence

- [?] Execution Repository
- [?] Evaluation Repository
- [?] Guardrail Repository
- [?] Job Repository
- [?] Background Job Lifecycle
- [?] Queue와 Lease
- [?] Retry Scheduling
- [?] Cancellation Persistence
- [?] Research Application Service
- [?] Tool Application Service
- [?] Workflow Application Service
- [?] Reliability Query
- [?] Transaction Boundary
- [?] SQLite Adapter
- [?] FastAPI Adapter
- [?] CLI Composition Root

---

# 7. Stage 0 — Project Realignment and Source Preparation

## 목표

ChatGPT의 `Agentic AI Lab` 프로젝트를 AIRA 개발의 실제 Control Plane으로
준비하고, 최상위 기준 문서와 기존 프로젝트 문서를 정렬한다.

## 상태

- [~] 진행 중

## Work Items

### 0.1 최상위 기준 문서

- [x] `AIRA_PROJECT_CHARTER.md` 작성
- [x] `DECISIONS.md` 수정
- [x] `MASTER.md` 수정
- [~] `ROADMAP.md` 수정

### 0.2 기존 핵심 문서 점검

- [ ] `CURRICULUM.md` 검토 및 수정
- [ ] `AGENTS.md` 검토 및 수정
- [ ] `README.md` 검토 및 수정
- [ ] `LEARNING_LOG.md` 검토 및 수정
- [ ] 기타 Phase·Lesson 상위 문서 목록 확인

### 0.3 ChatGPT Project 준비

- [ ] Project Instructions 작성
- [ ] ChatGPT Project에 등록할 Source 파일 목록 확정
- [ ] 파일 등록 순서 결정
- [ ] 최초 Audit 대화용 시작 Prompt 작성
- [ ] ChatGPT와 Codex의 작업 인계 형식 확정

### 0.4 Audit 준비

- [ ] 저장소 Inventory 명령 준비
- [ ] 감사 대상 디렉터리 목록 확정
- [ ] Capability Matrix Schema 확정
- [ ] Codex Audit Prompt 작성
- [ ] Audit 결과의 증거 기준 확정

## 완료 결과

- ChatGPT `Agentic AI Lab` 프로젝트가 AIRA 개발 Control Plane으로 준비됨
- 프로젝트 Source 목록 확정
- Project Instructions 확정
- 첫 시작 Prompt 확정
- Existing Capability Audit를 시작할 수 있음

---

# 8. Stage 1 — Existing Capability Audit

## 목표

`/home/moon/Project/agentic-ai-lab` 저장소의 실제 구현 상태를 사실에 근거해
감사하고 재사용·수정·재작성·보류 대상을 확정한다.

## 상태

- [x] 핵심 Existing Capability Audit 완료
- 세부 Component별 판정은 `AIRA_CAPABILITY_MATRIX.md`에서 관리한다.
- 아래 Work Item 목록의 `[ ]`는 미구현을 뜻하지 않으며, 원래 감사 범위를 보존한 것이다.
- 추가 확인이 필요한 항목은 후속 Architecture 및 Integration Work Item에서 다룬다.

## Work Items

### 1.1 저장소 전체 Inventory

- [ ] 디렉터리 Tree
- [ ] Python Package 구조
- [ ] 테스트 구조
- [ ] 설정 파일
- [ ] CLI Entry Point
- [ ] Composition Root
- [ ] 외부 의존성
- [ ] 환경변수
- [ ] Docker 관련 파일
- [ ] 문서와 코드 연결 관계

### 1.2 LLM 감사

- [ ] Responses API
- [ ] OpenAI SDK
- [ ] Structured Outputs
- [ ] Tool Calling
- [ ] Multi-turn Tool Loop
- [ ] 실제 API와 Fake Client 구분
- [ ] Usage 반환
- [ ] 오류 정규화
- [ ] Retry 및 Timeout

### 1.3 Tool과 Workflow 감사

- [ ] Tool Registry
- [ ] Tool 계약
- [ ] Tool 실행
- [ ] Permission
- [ ] Workflow
- [ ] Agent State
- [ ] Scheduler
- [ ] Retry
- [ ] Cancellation

### 1.4 RAG 감사

- [ ] Document Model
- [ ] Parser
- [ ] Chunker
- [ ] Keyword Search
- [ ] Embedding
- [ ] Retriever
- [ ] Hybrid Retrieval
- [ ] Reranking
- [ ] Context Builder
- [ ] Citation Grounding

### 1.5 Memory 감사

- [ ] Working State
- [ ] Memory Store
- [ ] Search
- [ ] Dedup
- [ ] Sanitizer
- [ ] Sensitive Data Policy
- [ ] Runtime 연결 여부

### 1.6 Planning 및 Research 감사

- [ ] Planning Agent
- [ ] Query Planning
- [ ] Replanning
- [ ] Single Research Agent
- [ ] Multi-Agent
- [ ] Evidence
- [ ] Claim
- [ ] Citation
- [ ] Report Writer
- [ ] 종료 조건

### 1.7 Evals·Guardrails·Tracing 감사

- [ ] Evaluation Dataset
- [ ] Evaluation Runner
- [ ] Guardrails
- [ ] Reliability
- [ ] Tracing
- [ ] E2E

### 1.8 Usage 및 비용 감사

- [ ] Token Usage
- [ ] Price Registry
- [ ] Cost Estimator
- [ ] Actual Cost
- [ ] Budget
- [ ] Budget Guardrail
- [ ] Cache
- [ ] Search API 비용 확장

### 1.9 Application 및 Persistence 감사

- [ ] CLI
- [ ] FastAPI
- [ ] Repository
- [ ] SQLite
- [ ] Background Job
- [ ] Queue
- [ ] Retry
- [ ] Cancellation
- [ ] Idempotency

### 1.10 실제 Runtime 추적

- [ ] CLI 입력부터 보고서 저장까지 호출 경로
- [ ] 실제 연결된 Module
- [ ] 구현되었으나 미연결된 Module
- [ ] 중복 또는 겹치는 구현
- [ ] 미사용 코드
- [ ] Baseline Runtime 한계

## 분류 기준

각 Component를 다음 중 하나로 결정한다.

- 그대로 재사용
- Adapter 추가
- 부분 수정
- 재작성
- 보류
- 폐기 후보

## 완료 결과

- [x] 저장소 핵심 Capability Inventory 완료
- [x] OpenAI Planning과 Structured Output 구현 확인
- [x] Research Task·Query·Source·Document Domain 구조 확인
- [x] Tool Registry, Plan 실행 및 Trace 기반 확인
- [x] 실제 OpenAI Usage 추출과 Token·Attempt·Time Budget 확인
- [x] Application Execution 및 Idempotency 기반 확인
- [x] 현재 `aira research`가 Offline Deterministic Baseline임을 확정
- [x] 실제 Web Search Adapter가 없음을 확인
- [x] 실제 HTTP/HTML Source Reader가 없음을 확인
- [x] Concrete Live Research Runner와 Composition Root가 없음을 확인
- [x] 전체 테스트 `4088 passed`
- [x] Ruff `All checks passed`
- [x] `AIRA_PROJECT_AUDIT_REPORT.md` 작성
- [x] `AIRA_CAPABILITY_MATRIX.md` 작성

Stage 1 결론:

```text
Rewrite가 아니라 Integration-first
→ Single-Agent Live Research Vertical Slice
→ 실제 Search와 Reader 우선
→ 기존 Capability 최대 재사용
```

---

# 9. Stage 2 — Target Product and Architecture

## 목표

기존 Audit 결과를 바탕으로 최소 Single-Agent부터 통합 AIRA까지의
목표 제품 구조와 Runtime Architecture를 확정한다.

## 상태

- [x] 핵심 Target Architecture 및 Integration 방향 확정
- 세부 문서 보강은 지속 관리 Track에서 수행한다.

## Work Items

### 2.1 Product Specification

- [ ] 주요 사용자
- [ ] 관심 분야 조사
- [ ] 연구주제 조사
- [ ] 선행특허 조사
- [ ] 인터넷 및 로컬 문서 통합
- [ ] 입력 Schema
- [ ] 출력 Report
- [ ] 기능 범위
- [ ] 비기능 요구사항
- [ ] 초기 범위와 확장 범위

### 2.2 Runtime Architecture

- [ ] Single-Agent 기본 흐름
- [ ] Composition Root
- [ ] Agent State
- [ ] Tool 계약
- [ ] LLM Provider 계약
- [ ] Search Provider 계약
- [ ] Local Document Adapter 계약
- [ ] Research Document Model
- [ ] RAG 통합 구조
- [ ] Evidence·Claim·Citation 구조
- [ ] Recommendation 구조
- [ ] Cost 및 Budget 구조
- [ ] Trace 구조
- [ ] Report Schema

### 2.3 Tool 및 Skill Registry

- [ ] 초기 Tool 목록
- [ ] Tool별 권한
- [ ] 비용 유형
- [ ] Retry와 Timeout
- [ ] 초기 Skill 후보
- [ ] Skill 도입 시점
- [ ] MCP/App 연결의 후순위 원칙

### 2.4 Integration Plan

- [ ] 재사용 순서
- [ ] Adapter 목록
- [ ] 수정 대상
- [ ] 재작성 대상
- [ ] 테스트 전략
- [ ] E2E 시나리오
- [ ] 비용 및 보안 Gate
- [ ] Codex Work Item 분할

## 완료 결과

- `AIRA_TARGET_PRODUCT_SPEC.md`
- `AIRA_TARGET_ARCHITECTURE.md`
- `AIRA_TOOL_SKILL_REGISTRY.md`
- `AIRA_INTEGRATION_PLAN.md`

---

# 10. Stage 3 — Minimal Intelligent Single Agent

## 목표

실제 LLM, Tool, 인터넷 또는 로컬 Source를 사용하여
처음부터 끝까지 보고서를 생성하는 최소 Single Research Agent를 완성한다.

## 상태

- [x] 핵심 Single-Agent Live Research 경로 완료 및 성능 최적화 Checkpoint 확보
- 추가 미세조정은 보류한다. 현재 Baseline을 유지한 채 다음 학습 초점은 Multi-Agent의 필요성, 패턴, 비용 및 구현 비교로 이동한다.

## Work Items

### 3.1 LLM Foundation

- [ ] 기존 OpenAI Responses API 코드 재사용
- [ ] Provider-independent Interface
- [ ] OpenAI Provider Adapter
- [ ] Deterministic Test Provider
- [ ] Structured Output
- [ ] Usage 및 오류 정규화

### 3.2 Research Request와 Planning

- [ ] 연구 요청 구조화
- [ ] 조사 목적
- [ ] 범위
- [ ] 하위 Task
- [ ] 검색 Query
- [ ] 완료 조건
- [ ] 비용 및 반복 제한

### 3.3 최소 Tool Set

- [ ] 하나의 인터넷 검색 Tool
- [ ] 웹페이지 Reader
- [ ] TXT Reader
- [ ] Markdown Reader
- [ ] 기본 PDF Reader
- [ ] Result 저장 Tool

### 3.4 Evidence와 평가

- [ ] Source 선택
- [ ] Evidence 추출
- [ ] 관련성 기본 평가
- [ ] 중요도 기본 평가
- [ ] 신뢰도 기본 평가
- [ ] Evidence Sufficiency

### 3.5 제한된 Agent Loop

- [ ] Plan
- [ ] Tool Selection
- [ ] Execute
- [ ] Observe
- [ ] Update State
- [ ] Replan
- [ ] Complete 또는 Abstain
- [ ] 종료 이유

### 3.6 Report

- [ ] 자료 정리
- [ ] 요약
- [ ] 기본 비교
- [ ] 기본 분석
- [ ] Claim
- [ ] Citation
- [ ] 근거 기반 제안사항
- [ ] 한계와 불확실성
- [ ] Markdown
- [ ] JSON

### 3.7 Cost와 Trace

- [ ] Usage 기록
- [ ] 실제 비용 기록
- [ ] 최대 호출 수
- [ ] 최대 반복 수
- [ ] 실행당 비용 상한
- [ ] Trace 저장

## 완료 결과

- 실제 인터넷 또는 로컬 자료를 사용해 보고서를 생성하는 최소 Single Agent
- 실제 E2E 연구 예제
- 비용과 Trace가 포함된 실행 결과
- Phase 13 Baseline과 비교 결과

---

# 11. Stage 4 — Local Document Expansion

## 목표

사용자가 지정한 로컬 문서를 안전하게 읽고 원문 위치를 보존하여
인터넷 자료와 함께 분석할 수 있도록 한다.

## 상태

- [~] 진행 중
- [x] 초기 TXT/Markdown Semantic Research Vertical Slice 완료
- [x] text-based PDF vertical slice 완료
- [x] text-bearing HWPX vertical slice 완료
- [ ] scanned PDF/OCR, HWP binary 및 Integrated Web+Local 범위는 미완료

## Work Items

- [x] TXT
- [x] Markdown
- [x] PDF Text (`pypdf`)
- [ ] Scanned PDF 처리 전략
- [ ] HWP
- [x] HWPX (safe ZIP + defusedxml)
- [x] 파일 Metadata (`local_path`, `filename`)
- [x] Query provenance (`search_query_text`)
- [ ] Heading 또는 Section
- [x] PDF physical page number (single-section-contained evidence)
- [x] 문단 및 character range 위치 보존
- [ ] 줄 번호
- [ ] 표 처리
- [x] Citation character 위치 보존
- [x] Paragraph semantic evidence selection
- [x] Generated claim integration
- [x] Semantic citation/claim relevance/answer coverage integration
- [x] Deterministic mode backward compatibility
- [x] Deterministic + Semantic 실제 CLI smoke
- [ ] 허용된 경로
- [ ] 파일 크기 제한
- [ ] 민감문서 외부 전송 승인
- [x] PDF parser/encrypted/no-text 실패 처리
- [ ] 동일 문서 Hash와 Cache

## 완료 결과

- TXT/MD/PDF/HWPX를 공통 Research Document로 변환
- 원문 위치를 추적할 수 있는 Evidence
- 인터넷 Source와 통합 가능한 로컬 Source Adapter

---

# 12. Stage 5 — Internet Research Expansion

## 목표

일반 웹검색뿐 아니라 공식자료, 공개 PDF, 학술자료 및 특허자료를
조사 목적에 맞게 검색하고 평가한다.

## 상태

- [ ] 시작 전

## Work Items

### 5.1 일반 웹

- [ ] Search Provider
- [ ] Query
- [ ] Pagination
- [ ] Snippet
- [ ] 원문 Fetch
- [ ] HTML Parsing
- [ ] 중복 제거
- [ ] 실패 처리

### 5.2 공식자료

- [ ] 정부 및 공공기관
- [ ] 국제기구
- [ ] 기업 공식문서
- [ ] API Documentation
- [ ] Source 유형별 우선순위

### 5.3 공개 PDF

- [ ] PDF Download
- [ ] Metadata
- [ ] 페이지 위치
- [ ] 접근 실패
- [ ] 중복 문서

### 5.4 학술자료

- [ ] 공개 논문
- [ ] Preprint
- [ ] DOI 또는 식별자
- [ ] 발행일
- [ ] 저자
- [ ] 기관
- [ ] 원문 접근 상태

### 5.5 특허자료

- [ ] 한국어·영어 Query
- [ ] 동의어
- [ ] 기술 구성요소
- [ ] 분류코드
- [ ] 특허번호
- [ ] 우선일
- [ ] 출원일
- [ ] 공개일
- [ ] 출원인
- [ ] 청구항
- [ ] 법적 상태
- [ ] 관련도와 위험도

## 완료 결과

- 일반 웹·공식자료·학술자료·특허자료 검색 경로
- Source 유형별 Metadata와 평가
- 중복 제거와 우선순위화

---

# 13. Stage 6 — Integrated RAG

## 목표

인터넷 및 로컬 문서를 공통 구조로 처리하고,
Keyword와 Semantic Search를 결합하여 관련 Evidence만 LLM에 제공한다.

## 상태

- [ ] 시작 전

## Work Items

- [ ] 기존 Chunker 통합
- [ ] Chunk Metadata
- [ ] Keyword Search
- [ ] Embedding Provider
- [ ] Vector Retrieval
- [ ] Hybrid Retrieval
- [ ] Metadata Filter
- [ ] Reranker
- [ ] Context Builder
- [ ] Evidence Selection
- [ ] Citation 위치 검증
- [ ] Retrieval Cache
- [ ] Embedding Cache
- [ ] Retrieval Eval
- [ ] 비용 비교

## 완료 결과

- 인터넷과 로컬 문서를 함께 검색하는 Hybrid RAG
- 관련 Evidence 중심의 LLM Context
- Retrieval 품질 및 비용 평가

---

# 14. Stage 7 — Agent Loop and Verification

## 목표

AIRA가 Evidence의 충분성, Source 품질 및 자료 간 충돌을 판단하고
제한된 범위에서 조사계획을 수정하도록 한다.

## 상태

- [ ] 시작 전

## Work Items

### 7.1 Evidence Sufficiency

- [ ] Task별 Evidence Coverage
- [ ] 부족한 정보 식별
- [ ] 단일 Source 여부
- [ ] 공식 Source 여부
- [ ] 최신성 부족 여부

### 7.2 Replanning

- [ ] Query 수정
- [ ] 동의어 확장
- [ ] 다른 Source 유형 선택
- [ ] 추가 Source 읽기
- [ ] 최대 반복
- [ ] 종료 조건

### 7.3 Source Evaluation

- [ ] 관련성
- [ ] 중요도
- [ ] 신뢰도
- [ ] 최신성
- [ ] Evidence Strength
- [ ] Source 유형별 가중치

### 7.4 Cross-validation

- [ ] 독립 Source 비교
- [ ] Supporting Evidence
- [ ] Contradicting Evidence
- [ ] 단일 Source 경고
- [ ] 공식 확인 불가
- [ ] 추가 조사 필요

### 7.5 Claim 및 Recommendation 검증

- [ ] Claim Support
- [ ] 과도한 확장 탐지
- [ ] Citation 존재
- [ ] Citation 실제 지지 여부
- [ ] Recommendation Grounding
- [ ] Confidence
- [ ] Abstention

## 완료 결과

- 제한된 Agentic Research Loop
- 교차검증된 Claim
- 충돌 및 불확실성 표시
- 근거 기반 Recommendation

---

# 15. Stage 8 — Cost and Provider Optimization

## 목표

비용을 Agent 실행 제약으로 통합하고,
업무별로 더 저렴한 API 또는 로컬 LLM을 선택할 수 있도록 한다.

## 상태

- [ ] 시작 전

## Work Items

### 8.1 기존 비용 코드 통합

- [ ] Usage Collector
- [ ] Token Counter
- [ ] Model Price Registry
- [ ] 실행 전 예상비용
- [ ] 실행 후 실제비용
- [ ] 가격 기준일
- [ ] 실행별 비용
- [ ] 누적비용

### 8.2 Budget Guardrail

- [ ] 최대 LLM 호출
- [ ] 최대 Search 호출
- [ ] 최대 Tool 호출
- [ ] 최대 Source
- [ ] 최대 Chunk
- [ ] 최대 Token
- [ ] 최대 반복
- [ ] 최대 실행시간
- [ ] 실행당 비용
- [ ] 중단 또는 승인 요청

### 8.3 Cache

- [ ] Query Cache
- [ ] Source Cache
- [ ] Parsing Cache
- [ ] Embedding Cache
- [ ] Result Cache
- [ ] Cache 무효화

### 8.4 Provider 비교

- [ ] OpenAI Baseline
- [ ] 다른 상용 LLM
- [ ] OpenAI-compatible API
- [ ] Ollama
- [ ] 로컬 LLM
- [ ] Deterministic Test Provider

### 8.5 Model Routing

- [ ] Query 생성
- [ ] Search Result 분류
- [ ] Chunk 관련성
- [ ] Evidence 분석
- [ ] 충돌 분석
- [ ] 최종 Report
- [ ] 작업별 품질·비용 비교

## 완료 결과

- 실행 전·후 비용 추적
- 실제 Budget 중단
- Cache 기반 비용 절감
- Provider 교체 가능한 Runtime
- 저가 또는 로컬 LLM 적용 범위 결정

---

# 16. Stage 9 — Evals and Real Research Validation

## 목표

AIRA의 기능 수가 아니라 실제 연구 품질, 신뢰성, 비용 및 재현성을
동일한 평가 기준으로 검증한다.

## 상태

- [ ] 시작 전

## Work Items

### 9.1 Golden Dataset

- [ ] 관심 분야 조사
- [ ] 특정 기술 연구주제
- [ ] 공식 규정 조사
- [ ] 인터넷과 로컬 문서 통합
- [ ] 로컬 문서 비교
- [ ] 선행특허 조사

### 9.2 품질 평가

- [ ] Search Relevance
- [ ] Retrieval Relevance
- [ ] Evidence Coverage
- [ ] Source Quality
- [ ] Citation Accuracy
- [ ] Claim Support
- [ ] Contradiction Detection
- [ ] Hallucination Rate
- [ ] Recommendation Grounding
- [ ] Report Completeness
- [ ] Trace Completeness

### 9.3 운영 평가

- [ ] Latency
- [ ] Token Usage
- [ ] API Cost
- [ ] Reproducibility
- [ ] Failure Recovery
- [ ] Budget 동작
- [ ] 동일 요청 Regression

### 9.4 실제 사례

- [ ] Agentic AI 기술 동향
- [ ] 착석 상태 기반 행동관리 기술 조사
- [ ] 특허 명세서와 선행특허 통합 분석
- [ ] 추가 실제 사용자 과제

## 완료 결과

- Golden Dataset
- Baseline Score
- Regression 기준
- 실제 연구 보고서
- 품질·비용·처리시간 비교표

---

# 17. Stage 10 — Multi-Agent Experiment

## 목표

Single-Agent 대비 역할 분리가 실제 이점을 제공하는지 평가한다.

## 상태

- [ ] 시작 전

## Work Items

- [ ] 역할 분리 후보 선정
- [ ] Research Coordinator
- [ ] Web Search Specialist
- [ ] Local Document Specialist
- [ ] Patent Search Specialist
- [ ] Evidence Analyst
- [ ] Claim Critic
- [ ] Verification Agent
- [ ] Report Writer
- [ ] 동일 Dataset 비교
- [ ] 품질 비교
- [ ] 비용 비교
- [ ] 처리시간 비교
- [ ] Context 안정성 비교
- [ ] 채택 또는 보류 결정

## 채택 조건

다음 중 하나 이상의 의미 있는 개선이 확인되어야 한다.

- Evidence Coverage 향상
- Citation Accuracy 향상
- Contradiction Detection 향상
- 복잡한 분석 품질 향상
- Context 관리 향상
- 처리시간 단축
- 비용 대비 성능 향상
- 실패 격리 향상

개선이 입증되지 않으면 Single-Agent를 기본 경로로 유지한다.

---

# 18. Stage 11 — Productization

## 목표

연구 품질이 검증된 AIRA를 실제로 사용·운영하기 위한 최소 제품 형태로 정리한다.

## 상태

- [ ] 시작 전

## Work Items

- [ ] CLI 사용성 개선
- [ ] 설정 파일
- [ ] 실행 Profile
- [ ] 결과 조회
- [ ] SQLite 필요성 검토
- [ ] FastAPI 필요성 검토
- [ ] Background Job 필요성 검토
- [ ] Dockerfile
- [ ] 필요한 경우 Docker Compose
- [ ] Secret 관리
- [ ] 로그
- [ ] 기본 Backup
- [ ] 사용자 가이드
- [ ] 개발자 운영 메모
- [ ] 알려진 제한
- [ ] MCP 또는 ChatGPT App 검토
- [ ] 배포 필요성 검토

## 완료 결과

- 재현 가능한 실행환경
- 사용자 가이드
- 운영 메모
- 필요에 맞는 최소 API 또는 Persistence
- ChatGPT 연동의 후속 방향

---

# 19. 지속 관리 Track

Stage와 별도로 다음 항목은 전체 기간 동안 지속적으로 관리한다.

## 19.1 Cost

- [ ] 기존 Usage 수집 코드 확인
- [ ] 기존 Token 계산 코드 확인
- [ ] Model Price Registry 확인
- [ ] 가격 기준일 기록
- [ ] 실행 전 예상비용
- [ ] 실행 후 실제비용
- [ ] Budget 초과 중단
- [ ] Search API 비용 확장
- [ ] Cache 효과 측정
- [ ] Provider별 비용 비교

## 19.2 Security and Privacy

- [ ] 로컬 파일 접근 범위
- [ ] Path Traversal 방지
- [ ] URL Scheme 검증
- [ ] 내부 네트워크 접근 제한
- [ ] Prompt Injection 방어
- [ ] Secret 관리
- [ ] 민감문서 외부 전송 승인
- [ ] 개인정보 Sanitization
- [ ] 데이터 삭제 승인

## 19.3 Evaluation

- [ ] Golden Dataset
- [ ] Stage별 Baseline
- [ ] Regression 기준
- [ ] Claim과 Citation 품질
- [ ] Cost와 Latency
- [ ] 실제 사용자 평가

## 19.4 Documentation

- [ ] 기준 문서 정합성
- [ ] Architecture 갱신
- [ ] Decisions 이력
- [ ] Work Item 결과
- [ ] 사용자 가이드
- [ ] 알려진 제한

## 19.5 Code Quality

- [ ] pytest
- [ ] Ruff
- [ ] `git diff --check`
- [ ] Type 검사 필요성
- [ ] 중복 코드
- [ ] 미사용 코드
- [ ] 의존성 관리

---

# 20. 공통 Stage Gate

각 Stage 또는 주요 Integration Work Item은 필요한 범위에서 다음 Gate를
통과해야 한다.

- [ ] 관련 기존 코드 Audit 완료
- [ ] 재사용·Adapter·수정·재작성 결정 기록
- [ ] Acceptance Criteria 충족
- [ ] Unit Test 통과
- [ ] Integration Test 통과
- [ ] 실제 E2E 또는 산출물 확인
- [ ] Ruff 통과
- [ ] `git diff --check` 통과
- [ ] Git Diff 검토
- [ ] 비용 영향 기록
- [ ] 보안 및 개인정보 영향 기록
- [ ] 관련 문서 갱신
- [ ] 사용자 승인
- [ ] 의미 있는 Commit

Fake 또는 Stub 테스트만 통과했다고 Production-ready로 분류하지 않는다.

---

# 21. 단계별 완료 기준

## 21.1 Project Control Plane 완료

- [ ] 기준 문서 정렬 완료
- [ ] ChatGPT Project Source 목록 확정
- [ ] Project Instructions 확정
- [ ] 첫 시작 Prompt 확정
- [ ] Codex 작업 인계 방식 확정
- [ ] Audit Prompt 확정
- [ ] Stage 1 시작 준비 완료

## 21.2 Minimal Single-Agent Core 완료

- [ ] LLM 기반 연구계획
- [ ] 최소 Tool 선택
- [ ] 인터넷 검색
- [ ] 웹페이지 읽기
- [ ] 로컬 TXT/Markdown 읽기
- [ ] 기본 PDF
- [ ] Evidence 추출
- [ ] Source 기본 평가
- [ ] Evidence 부족 시 제한된 Replanning
- [ ] Claim과 Citation
- [ ] 자료 정리·요약·비교·기본 분석
- [ ] 근거 기반 제안사항
- [ ] Markdown 및 JSON
- [ ] Usage·Cost·Trace
- [ ] 최대 반복 및 비용 제한
- [ ] 실제 E2E 연구 예제

## 21.3 Integrated AIRA 완료

- [ ] 인터넷과 로컬 자료 통합
- [ ] TXT, Markdown, PDF, HWP, HWPX
- [ ] 공통 Research Document
- [ ] Hybrid RAG
- [ ] Source 중요도·신뢰도·최신성
- [ ] Evidence 교차검증
- [ ] 충돌 분석
- [ ] Claim Support
- [ ] Recommendation Grounding
- [ ] Citation 검증
- [ ] Provider 교체
- [ ] Cache와 Budget
- [ ] Golden Dataset
- [ ] Regression 방지
- [ ] 실제 관심 분야·연구주제·선행특허 조사 검증

## 21.4 Multi-Agent 채택

Multi-Agent는 완료 조건이 아니라 선택적 채택 조건이다.

Single-Agent 대비 의미 있는 개선이 확인되지 않으면 보류한다.

---

# 22. 보류 Backlog

다음 항목은 현재 핵심 Stage의 선행조건이 아니다.

- [-] PostgreSQL 전환
- [-] Redis Queue
- [-] RabbitMQ
- [-] 분산 Worker
- [-] Kubernetes
- [-] 복잡한 인증과 RBAC
- [-] 협업 Workspace
- [-] 상용 수준 Web UI
- [-] 대규모 Observability
- [-] Prometheus·Grafana 전체 구성
- [-] OpenTelemetry 전체 구성
- [-] Nginx와 HTTPS 운영 구성
- [-] OCI 운영 배포
- [-] 대규모 CI/CD
- [-] 완전 자율 Multi-Agent 조직
- [-] 추가 분산 신뢰·암호화 하위 시스템
- [-] 외부 배포용 Plugin 패키지

다음은 후순위 Productization 후보이며 완전 보류 항목과 구분한다.

- [ ] MCP 또는 ChatGPT App
- [ ] FastAPI
- [ ] SQLite
- [ ] Background Job
- [ ] Docker Compose
- [ ] 제한된 Web UI

Backlog는 실제 사용 중 필요가 확인되고 사용자가 승인한 경우에만 진행한다.

---

# 23. 로드맵 운영 원칙

- 기존 Phase 0~13은 완료 이력으로 보존한다.
- 앞으로의 제품 통합은 Stage와 Work Item으로 관리한다.
- 새 기능보다 Existing Capability Audit를 우선한다.
- 새로 만들기 전에 기존 코드를 재사용할 수 있는지 확인한다.
- 기능 수 증가보다 실제 연구 품질과 비용 개선을 우선한다.
- 인터넷 검색과 로컬 문서 통합은 AIRA의 핵심 목표다.
- 비용은 사후 기록이 아니라 Agent 실행 제약이다.
- 초기에는 OpenAI를 사용할 수 있지만 Provider에 종속되지 않는다.
- 로컬 LLM은 동일한 Eval을 통과한 범위에서 단계적으로 사용한다.
- Multi-Agent는 평가로 이점이 입증된 경우에만 채택한다.
- 실제 코드·테스트·실행 결과가 문서의 주장보다 우선한다.
- 중요한 변경은 `DECISIONS.md`에 이력을 남긴다.
---

# 24. 2026-08-06 Live Research Evidence 품질 개선 완료 기록

## 작업 상태

- [x] 검색 결과 Overfetch
- [x] Query-aware Source Ranking
- [x] Source Quality Floor
- [x] 문서 관련성·유용성·Provider 점수 통합
- [x] Source Redundancy 완화
- [x] Query-aware Paragraph Evidence 추출
- [x] 코드·실행지시·색인·Navigation Evidence Hard Filter
- [x] 다중 Markdown 링크 목록 Hard Filter
- [x] `NO_EVIDENCE` 상태 정합성 수정
- [x] Evidence-aware Source Backfill
- [x] 최소 Evidence Source Quality Gate
- [x] Backfill 전용 결정론적 회귀 테스트
- [x] 실제 OpenAI 공식문서 Live Research 검증

## 확정된 실행 의미

```text
candidate_set
= 검색에서 발견한 후보 전체

read_document_set
= Reader가 읽기를 시도한 문서 전체

ranked eligible documents
= 품질 하한선을 통과한 결정론적 순위 문서

document_set
= 실제 Evidence를 하나 이상 제공한 최종 문서

evidence_set
= 최종 document_set에 연결된 Evidence

maximum_sources
= 최종 유효 Evidence Source의 최대 개수
```

## Live 검증 결과

연구 질문:

```text
OpenAI Responses API official documentation overview
```

조사 목적:

```text
Explain the Responses API using concise and authoritative web evidence.
```

최종 검증:

- 검색·읽기 후보: 9
- Evidence 추출 시도: 4
- 최종 Evidence Source: 1
- Evidence 수: 1
- `NO_EVIDENCE` 문서: 3
- Backfill 문서: 3
- 코드·링크 색인 노이즈: 없음
- 최종 품질 점수: 0.9565
- 최소 Source Gate: 실패
- 품질 결과: `passed=false`
- 품질 문제: `LOW_SOURCE_DIVERSITY/error`

## 해석

Backfill은 정상 작동하였다.

다만 품질 하한선을 통과한 나머지 후보에서 Responses API 질문을 직접
지원하는 깨끗한 Evidence를 얻지 못했다. Pipeline은 문서 색인이나 코드 예시를
Evidence로 채택하지 않았으며, Source 수를 인위적으로 채우지 않고 단일 Source
상태를 품질 실패로 보고하였다.

이는 기능 실패가 아니라 Evidence Sufficiency 정책이 정상 작동한 결과다.

## 테스트 기준선

- 전체 pytest: `4157 passed`
- Ruff: `All checks passed`
- `git diff --check`: 통과
- Live E2E: 통과
- Backfill 및 Source Gate 회귀 테스트: 통과

## 다음 우선 과제

- [ ] 검색 Query 다양화 또는 제한된 Replanning으로 독립 Source Coverage 개선
- [ ] Evidence Sufficiency 결과를 Agent Loop의 추가 검색 결정과 연결
- [ ] 공식 API Reference 외의 독립된 공식 Guide Source 탐색 전략 검토
- [ ] Report의 영문 단수·복수 표현 개선
- [ ] Live Result JSON에서 계산 속성인 `passed` 노출 여부 검토

---

# 25. 2026-08-07 제한형 Supplemental Search Replanning 완료 기록

## 작업 상태

- [x] 기존 범용 Replanning Capability 감사
- [x] 범용 `PlanningAgentLoop` 비사용 결정
- [x] Research 전용 `SupplementalResearchQueryPlanner` 구현
- [x] 결정론적 Supplemental Query 생성
- [x] Evidence Source 부족 조건 연결
- [x] 추가 검색 최대 1회 제한
- [x] 초기 Source가 충분한 경우 조기 종료
- [x] `maximum_sources=1`인 경우 Replanning 비활성화
- [x] Source ID 및 정규화 URL 중복 제거
- [x] 중복 후보 Reader 호출 방지
- [x] 초기·추가 문서 전체 Ranking 재실행
- [x] Evidence-aware Backfill 재실행
- [x] Replanning metadata 기록
- [x] 성공 후 오래된 `LOW_SOURCE_DIVERSITY` 제거
- [x] Source 부족 시 품질 실패 유지
- [x] 결정론적 회귀 테스트
- [x] Live Runtime 구성 검증
- [x] 실제 Tavily Live Research 검증
- [x] 전체 pytest 및 Ruff 통과

## 확정된 실행 흐름

```text
Initial Query Planning
→ Initial Search
→ Initial Read
→ Quality Ranking
→ Evidence-aware Backfill
→ Evidence Sufficiency Check
   ├─ sufficient
   │  → Report and Quality Evaluation
   └─ insufficient
      → Supplemental Query Planning
      → Supplemental Search
      → URL and Source Deduplication
      → Read Novel Candidates
      → Merge All Read Documents
      → Full Quality Ranking
      → Evidence-aware Backfill
      → Report and Quality Evaluation
```

## 실행 한계

```text
maximum supplemental queries = 1
maximum supplemental search rounds = 1
maximum total search rounds = 2
```

## Live 검증 결과

- 총 검색 라운드: 2
- Replanning 실행: true
- Supplemental Query: 1
- Supplemental 신규 후보: 4
- 제거된 중복 후보: 5
- 전체 읽은 후보: 13
- Evidence 추출 시도 문서: 5
- 최종 Evidence Source: 2
- `NO_EVIDENCE` 문서: 3
- 최종 Claim: 4
- 최종 Citation: 4
- 최종 Quality Score: 0.9163
- 최소 Evidence Source: 2
- 실제 Evidence Source: 2
- `LOW_SOURCE_DIVERSITY`: 없음

## 테스트 기준선

```text
전체 pytest: 4167 passed in 9.41s
Ruff: All checks passed
git diff --check: passed
Live E2E: passed
```

## 다음 우선 과제

- [x] `result.json`에 계산 속성인 Quality `passed` 노출 완료
- [ ] Supplemental Query 품질 개선 기준 설계
- [ ] Provider 호출·Credit·Latency Budget 통합
- [ ] Citation 검증
- [ ] Golden Research Dataset 구축
- [ ] 동일 질문 반복 실행의 Live 변동성 평가
- [ ] 실제 관심 분야 또는 선행특허 조사 검증

---

# 26. 2026-08-07 Quality Passed JSON 직렬화 완료 기록

## 작업 상태

- [x] `ResearchQualityEvaluation.passed` 구현 방식 확인
- [x] Pydantic 2.13.4 직렬화 동작 확인
- [x] `result.json` 누락 원인 확인
- [x] `computed_field` 대안 검토
- [x] 실제 Boolean 필드 대안 검토
- [x] Writer 한정 직렬화 방식 결정
- [x] 성공 품질의 `passed=true` 저장
- [x] 실패 품질의 `passed=false` 저장
- [x] Writer 회귀 테스트 추가
- [x] 전체 pytest 통과
- [x] Ruff 통과
- [x] `git diff --check` 통과

## 확정된 구조

```text
ResearchQualityEvaluation
├─ issues
└─ passed (@property로 계산)

ResearchResultWriter
├─ result.model_dump(mode="json")
├─ payload["quality"]["passed"] 추가
└─ result.json 저장
```

## 영향 범위

변경 파일:

```text
app/research/research_result_writer.py
tests/test_research_result_writer.py
```

변경하지 않은 영역:

- `ResearchQualityEvaluation` Schema
- 일반 `model_dump()` 결과
- Pipeline 내부 품질 계산
- Markdown의 Passed 표시
- Offline 및 Live Pipeline 실행 의미

## 테스트 기준선

```text
Writer 테스트: 3 passed
전체 pytest: 4168 passed in 15.61s
Ruff: All checks passed
git diff --check: passed
```

## 다음 우선 과제

- [ ] Provider 호출·Credit·Latency Budget 통합
- [ ] Supplemental Query 품질 개선 기준 설계
- [ ] Citation 검증
- [ ] Golden Research Dataset 구축
- [ ] 동일 질문 반복 실행의 Live 변동성 평가
- [ ] 실제 관심 분야 또는 선행특허 조사 검증

---

# 27. 2026-08-07 Provider Budget 및 Source Type 정규화 완료 기록

## 작업 상태

- [x] Search Budget 및 Usage Schema 구현
- [x] Provider Call 수 제한
- [x] Provider Credit 제한
- [x] 미보고 Credit 기본값 적용
- [x] 누적 Provider Latency 제한
- [x] Budget 차단 Query 수 기록
- [x] Supplemental Search Budget 공유
- [x] Supplemental Search Budget 차단 상태 기록
- [x] Live Runtime 기본 Budget 구성
- [x] 사용자 지정 Search Budget 주입
- [x] Tavily Candidate Source Type 고정값 원인 분석
- [x] Provider 독립적 Source Type Classifier 구현
- [x] 정확한 Trusted Host 정책 구현
- [x] `openai.github.io` 공식 문서 분류
- [x] 다른 `*.github.io` 비신뢰 테스트
- [x] 정부·교육·공식 문서 Host Pattern 분류
- [x] Tavily Candidate 정규화 연결
- [x] 전체 pytest 통과
- [x] Ruff 통과
- [x] `git diff --check` 통과
- [x] 실제 Tavily Live E2E 통과

## 확정된 실행 흐름

```text
Query Planning
→ Provider Budget 사전 검사
→ Tavily Search
→ Provider Usage 누적
→ URL Source Type Classification
→ Candidate 정규화
→ HTTP/HTML Reading
→ Source Quality Evaluation
→ Evidence-aware Selection
→ Evidence Sufficiency Check
   ├─ sufficient
   │  → Report and Quality Evaluation
   └─ insufficient
      → Supplemental Query Planning
      → 동일 Provider Budget 사전 검사
      ├─ budget available
      │  → Supplemental Search
      └─ budget exhausted
         → Provider 호출 차단 및 실패 상태 기록
```

## Live 기본 Budget

```text
maximum_provider_calls = 2
maximum_credits = 2.0
maximum_latency_ms = timeout_seconds × 1000 × 2
default_credit_per_call = 1.0
```

## Source Type 정책

```text
explicit trusted host
→ OFFICIAL_DOCUMENTATION

docs.* / developer.* / developers.*
→ OFFICIAL_DOCUMENTATION

.gov / .go.kr
→ GOVERNMENT

.edu / .ac.kr
→ ACADEMIC

otherwise
→ OTHER
```

Live Trusted Host:

```text
openai.github.io
```

## Live 검증 결과

- 읽은 후보: 6
- 최종 선택 문서: 2
- 최종 Evidence Source: 2
- 검색 라운드: 1
- Replanning 실행: false
- Provider 호출: 1
- 사용 Credit: 1.0
- Search Budget 소진: false
- `openai.github.io`: `official_documentation`
- `developers.openai.com`: `official_documentation`
- 두 Source Quality: 각각 0.9225
- 최종 Quality Score: 0.9345
- Quality Level: excellent
- `passed=true`
- `LOW_SOURCE_DIVERSITY`: 없음

## 테스트 기준선

```text
전체 pytest: 4194 passed in 15.69s
Ruff: All checks passed
git diff --check: passed
Live E2E exit code: 0
```

## 다음 우선 과제

- [ ] Citation 검증
- [ ] Golden Research Dataset 구축
- [ ] 동일 질문 반복 실행의 Live 변동성 평가
- [ ] Source Type Classifier의 설정 외부화 기준 검토
- [ ] Provider별 Credit 단위 및 Usage 정합성 검증
- [ ] 실제 관심 분야 또는 선행특허 조사 검증

---

# 25. 2026-08-07 Semantic Citation Verification 평가 완료 기록

## 25.1 완료 범위

- [x] Claim과 Evidence 간 Semantic Citation Judgment Schema
- [x] OpenAI Responses API Structured Output 기반 Semantic Judge
- [x] 범주형 Semantic Support Level
- [x] Support Level → Citation Decision 결정론적 매핑
- [x] SemanticCitationVerificationService
- [x] Single-Agent Research Pipeline 연결
- [x] Live Runtime 연결
- [x] ResearchCitationVerification에 support_level 보존
- [x] result.json에 Semantic Citation 결과 저장
- [x] Golden Dataset v1
- [x] Golden Dataset v2 및 Label Adjudication
- [x] Semantic Citation Evaluation Runner
- [x] Confusion 및 오류 방향 측정
- [x] Blind Holdout v1
- [x] 실제 OpenAI Semantic Eval
- [x] Live Research E2E 재검증
- [x] 전체 Regression Test

## 25.2 현재 평가 결과

Golden Dataset v2 / Prompt v2:

```text
cases = 20
correct = 18
accuracy = 90%
false_fully_supported = 0
false_rejected = 1
```

Blind Holdout v1:

```text
cases = 20
correct = 19
accuracy = 95%
false_fully_supported = 0
false_rejected = 1
```

최종 전체 Regression:

```text
4245 passed in 16.27s
Ruff: All checks passed
git diff --check: passed
```

Live Research E2E:

```text
quality = 0.9345
citation_verifications = 6

support_level = fully_supported 6 / 6
decision = verified 6 / 6
```

## 25.3 현재 Capability 상태

```text
Semantic Citation Verification
→ Implemented
→ Tested
→ Live Verified
→ Evaluated
```

아직 Blocking Quality Gate에는 연결하지 않는다.

## 25.4 알려진 한계

```text
Positive scoped evidence:
"The service is available during business hours."

를

Exclusive evidence:
"The service is available only during business hours."

처럼 과도하게 해석할 가능성이 있다.
```

또한 현재 Live Research의 Deterministic Claim Builder는:

```text
Claim.text = Evidence.excerpt
```

이므로 실제 Live Citation은 대부분 의미적으로 자명한 검증이 된다.

따라서 Semantic Judge의 실질 성능 평가는 Live Claim 결과가 아니라
Golden Dataset과 Blind Holdout을 기준으로 한다.

## 25.5 다음 과제

- [ ] 더 큰 Semantic Citation Holdout Dataset
- [ ] 반복 실행을 통한 Judge 변동성 측정
- [ ] Class별 Precision/Recall 측정
- [ ] False Fully Supported 허용 기준 정의
- [ ] 실제 생성형 Claim Builder 도입 전 Existing Capability Audit
- [ ] 생성형 Claim과 Evidence 사이 Semantic Citation E2E
- [ ] Blocking Quality Gate 적용 조건 정의

---

# 28. Step 4 — Generative Claim Construction 완료

상태: **완료 — 2026-08-07**

## 목표

결정론적 `Claim.text = Evidence.excerpt` Baseline을 실제 생성형 Claim으로 확장하고, 생성된 Claim을 기존 provenance와 Semantic Citation Verification에 연결하며, OpenAI 호출 수·Token·시간을 bounded execution으로 제한한다.

## 완료 항목

- [x] Existing Capability Audit
- [x] `GeneratedClaimProposal` structured-output schema
- [x] `OpenAIEvidenceClaimGenerator`
- [x] `GenerativePipelineClaimBuilder`
- [x] `1 Evidence → 1 Generated Claim`
- [x] LLM 의미 생성과 코드 provenance 분리
- [x] 실제 OpenAI API smoke test
- [x] Live Research Runtime 연결
- [x] 생성 Claim과 Evidence 원문 비동일성 확인
- [x] Semantic Citation Verification 실제 연결
- [x] `ExecutionBudget` 재사용
- [x] Attempt ceiling
- [x] Token ceiling
- [x] Elapsed-time ceiling Unit Test
- [x] 성공한 over-budget Claim 보존
- [x] Graceful degradation
- [x] 전체 pytest
- [x] Ruff
- [x] `git diff --check`
- [x] 실제 Live Runtime attempt/token budget 검증

## 실제 E2E 확인

- Live 생성 Claim 3개 모두 `Claim.text != Evidence.excerpt`
- Semantic Citation Verification 3/3 `fully_supported`
- Attempt budget 실험: Evidence 6개 → Claim 3개
- Token budget 실험: Evidence 6개 → Claim 1개
- Budget 소진 후에도 Research Pipeline은 이미 생성한 Claim으로 정상 계속 진행

## 설계 경계

이번 Step에서는 다음을 의도적으로 포함하지 않는다.

- Multi-evidence Claim grouping
- Claim type 자동 분류
- Semantic Citation Verification 자체의 별도 Budget
- Claim relevance / Answer relevance blocking gate
- Multi-Agent 전환

## 다음 작업

**Step 5 — Claim Relevance / Answer Relevance Evaluation Existing Capability Audit**

Citation이 Evidence를 정확히 지지하는지와 별개로, 생성된 Claim이 사용자의 Research Question과 Objective에 실제로 답하는지를 평가하는 capability를 검토한다.

---

# 29. 2026-08-08 Step 5 — Claim / Evidence Relevance 통합 완료 기록

## 29.1 Claim Relevance Evaluation

상태: **완료**

완료 항목:

- [x] Existing Capability Audit
- [x] `ClaimRelevanceLevel`
- [x] Structured `ClaimRelevanceJudgment`
- [x] OpenAI Claim Relevance Evaluator
- [x] Golden Development Dataset
- [x] Blind Holdout Dataset
- [x] Prompt v2.1 동결
- [x] Single Research Pipeline 연결
- [x] Live Runtime 연결
- [x] 독립 Execution Budget
- [x] result.json persistence
- [x] 실제 Live Regression

평가 결과:

```text
Development Dataset:
17 / 18 = 94.44%

Blind Holdout v2:
17 / 18 = 94.44%
false_direct = 1
false_irrelevant = 0
```

초기 Live Failure:

```text
Generated Claims = 3
Semantic Citation = 3 / 3 fully_supported
Claim Relevance = 3 / 3 irrelevant
```

확정된 진단:

```text
Groundedness != Answer Relevance
```

Claim Relevance는 현재 Evaluated Capability이며 Blocking Quality Gate나
자동 Claim 필터링에는 연결하지 않는다.

## 29.2 Semantic Evidence Relevance

상태: **완료**

완료 항목:

- [x] `EvidenceRelevanceLevel`
- [x] Structured `EvidenceRelevanceJudgment`
- [x] OpenAI Evidence Relevance Evaluator
- [x] Golden Development Dataset
- [x] Prompt v1.1 동결
- [x] Blind Holdout v1
- [x] Paragraph Candidate Exposure
- [x] Embedding Semantic Shortlist
- [x] Semantic Evidence Reranker
- [x] Semantic-aware Evidence Extractor
- [x] Live Runtime DI
- [x] Live Handler Wiring
- [x] Precision-first Final Evidence Selection
- [x] Embedding-only shortlist coverage audit
- [x] RRF Hybrid Retrieval simulation
- [x] RRF Hybrid Retrieval production integration
- [x] Live Regression

평가 결과:

```text
Golden Development initial:
16 / 18 = 88.89%

Prompt v1.1 Development:
18 / 18 = 100%
(Development Dataset이므로 일반화 성능으로 해석하지 않음)

Blind Holdout v1:
16 / 18 = 88.89%
false_direct = 2
false_irrelevant = 0
```

## 29.3 Embedding-only Failure와 RRF 개선

실제 68개 Paragraph Candidate Audit에서 핵심 answer-bearing Passage는:

```text
built-in agent loop / invokes tools
Embedding rank = 9

function tools / automatic schema / Pydantic
Embedding rank = 10

MCP + native function tools
Embedding rank = 11
```

기존 `maximum_candidates=8`에서는 핵심 Passage가 Semantic Evaluator에
도달하지 못했다.

RRF Hybrid Simulation:

```text
Core Passage                              Embedding  Lexical  RRF

SDK general overview                           1        3      1
function tools / schema / Pydantic            10        1      5
built-in agent loop / invokes tools            9        8      6
MCP + native function tools                   11       14     13
```

확정된 초기 정책:

```text
Embedding Rank + Lexical Rank
→ Equal-weight Reciprocal Rank Fusion

rrf_k = 60
maximum_candidates = 8
score threshold = none
```

## 29.4 Precision-first Final Evidence Selection

정책:

```text
DIRECT 또는 PARTIAL Evidence가 존재
→ 평가 완료 Relevant Evidence만 최종 승격
→ UNEVALUATED backfill 금지

Relevant Evidence 없음 + Budget exhaustion
→ best UNEVALUATED 1개만 graceful fallback

모두 평가 완료 + 모두 IRRELEVANT
→ NO_EVIDENCE
```

## 29.5 최종 Live Regression

연구 질문:

```text
How does the OpenAI Agents SDK support tool calling?
```

목적:

```text
Explain the concrete mechanism by which functions or tools are made
available to an agent and used during execution.
```

최종 Source:

```text
OpenAI Agents SDK official documentation
Title: Tools - OpenAI Agents SDK
```

Final Evidence:

```text
1 x directly_relevant   (0.88)
2 x partially_relevant  (0.55, 0.60)

semantic_evaluated = true for all
UNEVALUATED = 0
CTA noise = 0
```

Semantic Citation Verification:

```text
3 / 3 verified
3 / 3 fully_supported
3 / 3 entailment_score = 1.0
```

Claim Relevance:

```text
Claim 1 = partially_relevant 0.50
Claim 2 = partially_relevant 0.60
Claim 3 = directly_relevant  0.78
```

Deterministic Quality:

```text
overall_score = 0.8845
quality_level = high
passed = true
```

주의:

현재 Deterministic Quality Score는 Semantic Evidence Relevance 또는 Claim
Relevance를 Blocking Gate로 직접 사용하지 않는다. 따라서 Semantic 평가 결과와
별도로 해석한다.

## 29.6 현재 Step 5 상태

```text
Claim Relevance Evaluation
→ Evaluated Capability

Semantic Evidence Relevance
→ Evaluated Capability

RRF Hybrid Retrieval
→ Implemented + Focused Tested + Live Verified

Precision-first Final Evidence Selection
→ Implemented + Live Verified

Semantic Citation Verification
→ Evaluated Capability

Blocking Semantic Quality Gate
→ Deferred
```

## 29.7 최종 Checkpoint

- [x] `DECISIONS.md` 최신화
- [x] `ROADMAP.md` 최신화
- [x] `LEARNING_LOG.md` 최신화
- [x] `AIRA_CAPABILITY_MATRIX.md` 최신화
- [x] Step 5.12 이후 전체 Repository pytest
- [x] 전체 Ruff
- [x] `git diff --cached --check`
- [x] 최종 Regression Checkpoint 기록
- [ ] 전체 Git Diff 최종 검토
- [ ] 의미 있는 Git Commit
- [ ] 다음 연구 품질 과제 선정

최종 검증:

```text
4431 passed in 16.41s
Ruff: All checks passed
git diff --cached --check: passed
```


---

# 30. 2026-08-08 Step 6.5 — Research Run Observability 및 Latency Baseline 완료

## 30.1 상태

- [x] Research Run Metrics Schema
- [x] Live Runtime opt-in observability
- [x] Search Provider Call·Credit·Latency 계측
- [x] Source Reading 및 Evidence Pipeline wall-clock 계측
- [x] Claim Generation usage 계측
- [x] Semantic Citation Verification usage 계측
- [x] Claim Relevance usage 계측
- [x] Answer Coverage usage 계측
- [x] Evidence Semantic Evaluator usage 계측
- [x] Coverage Round 별도 계측
- [x] Answer Coverage Structured Output corrective retry
- [x] Citation usage 중복 누적 버그 수정
- [x] Answer Coverage `last_usage` 노출 누락 수정
- [x] Evidence Semantic usage adapter 전달 누락 수정
- [x] 전체 Regression
- [x] Ruff
- [x] `git diff --cached --check`
- [x] Commit 및 `origin/main` Push

## 30.2 Observability 정책

```text
Generic / deterministic pipeline
→ run_metrics 기본 비활성화

Live Research runtime
→ run_metrics 명시적 활성화
```

Wall-clock처럼 실행마다 달라지는 값이 결정론적 Pipeline JSON 비교를
깨뜨리지 않도록 Observability는 opt-in으로 운영한다.

Semantic 품질 판정 자체와 Observability를 분리한다.
Metrics는 진단·비용·성능 분석용이며 품질 Score나 Blocking Gate를
자동 변경하지 않는다.

## 30.3 Structured Output Recovery

Answer Coverage Structured Output이 Schema의 교차 필드 의미 규칙을
위반하는 Live Failure를 확인하였다.

대표 실패:

```text
coverage_level = fully_covered
missing_aspects != []
```

정책:

```text
첫 Structured Output
→ Schema Validation 성공: 사용
→ Validation 실패: corrective retry 최대 1회
→ 두 번째도 실패: 명시적 StructuredResponseValidationError
```

Validator를 느슨하게 하거나 모순된 결과를 코드가 임의로 FULL 판정으로
보정하지 않는다.

## 30.4 최종 Live Latency Baseline

질문:

```text
How does the OpenAI Agents SDK support tool calling?
```

목적:

```text
Explain the concrete mechanism by which functions or tools are made
available to an agent and used during execution.
```

최종 실행:

```text
total_elapsed_seconds = 591.871
tracked_llm_calls = 30
tracked_tokens = 45,498
tracked_llm_elapsed = 462.546
search_provider_calls = 2
search_elapsed_seconds = 3.723
```

Round 1:

```text
Evidence semantic:
2 calls / 4,192 tokens / 93.599s
Evidence pipeline wall-clock:
135.746s

Claim generation:
4 calls / 3,074 tokens / 21.468s

Citation verification:
4 calls / 4,104 tokens / 14.540s

Claim relevance:
4 calls / 8,148 tokens / 47.441s

Answer coverage:
1 call / 2,501 tokens / 22.219s
```

Coverage Round:

```text
Evidence semantic:
5 calls / 9,235 tokens / 37.076s
Evidence pipeline wall-clock:
81.357s

Citation verification:
5 calls / 5,488 tokens / 20.159s

Claim relevance:
3 calls / 6,255 tokens / 104.271s

Answer coverage:
2 calls / 2,501 tokens / 101.772s
```

최종 Answer Coverage:

```text
coverage_level = fully_covered
coverage_score = 0.93
missing_aspects = []
```

Timing accounting:

```text
accounted wall-clock = 559.166s
unattributed = 32.704s
```

## 30.5 성능 진단

확정된 결론:

```text
Search와 HTTP Reading은 핵심 병목이 아니다.
병목은 검색 이후 Semantic LLM Processing과 Coverage Round 재평가에 있다.
```

주요 개선 후보:

1. Coverage Round에서 기존 평가 결과 재사용
2. Claim Relevance Batch Evaluation
3. Citation Verification Batch Evaluation
4. Evidence Semantic Evaluator 호출 축소
5. Answer Coverage Structured Output 첫 시도 성공률 개선
6. 필요 시 병렬 실행 가능성 평가

Embedding Provider 호출은 현재 별도 Usage 계측 대상이 아니므로
`tracked_llm_calls`를 모든 AI API 호출 총계로 해석하지 않는다.

## 30.6 최종 Checkpoint

```text
pytest = 4468 passed in 10.19s
Ruff = All checks passed
git diff --cached --check = passed

commit = 640df8a
message = feat: add research run observability and latency metrics
branch = main
remote = origin/main
working tree = clean
```

## 30.7 다음 작업

**Step 6.6 — Performance Optimization**

최적화는 검색 Provider가 아니라 실제 측정에서 가장 비싼 Semantic Evaluation과
Coverage Round 재작업부터 검토한다.

---

# 31. 2026-08-09 Step 6.6 — Single-Agent Performance Optimization 완료 기록

## 31.1 목표

Step 6.5 Observability에서 확인된 Semantic LLM fan-out과 Coverage Round 재작업을
줄이되, 기존 Evidence→Claim provenance, Citation 의미, Relevance 평가,
Coverage 판정 및 Budget 계약을 깨뜨리지 않는 것을 목표로 하였다.

최적화 우선순위는 다음 원칙을 따랐다.

```text
1. 불필요한 호출 제거
2. 기존 결과 재사용
3. 독립 작업의 Batch 처리
4. 필요 시 병렬화·저가 모델을 후속 검토
```

## 31.2 완료된 최적화

- [x] Coverage Round Incremental Reuse
- [x] Evidence Semantic Usage 계측 정확도 보정
- [x] Per-run Document-level Evidence Reuse
- [x] Coverage Novel-document Evidence Evaluation
- [x] Coverage Novel-source Adoption
- [x] Coverage Substitution Acceptance Gate
- [x] Post-Optimization Performance Re-baseline
- [x] Document-local Batched Evidence Relevance Evaluation
- [x] Batched Claim Relevance Evaluation
- [x] Batched Semantic Citation Verification
- [x] Batched Evidence-to-Claim Generation
- [x] 전체 Regression
- [x] Ruff
- [x] `git diff --check`
- [x] Git Commit 및 `origin/main` Push

## 31.3 핵심 설계 원칙

Batching은 의미적 계약을 바꾸지 않는다.

```text
Evidence 1 → Claim 1
Evidence 2 → Claim 2
Evidence 3 → Claim 3
```

위 의미는 유지하면서 Transport/API 호출만 묶는다.

Claim ID, Citation ID, Evidence ID, Source ID, Document ID 및 provenance는
계속 코드가 결정한다.

```text
Meaning by LLM
Provenance by code
```

논리적 작업량과 실제 API 호출량도 분리한다.

```text
last_usage
= logical item usage

last_api_usage
= physical API call usage
```

## 31.4 성능 Baseline 변화

Step 6.6.4 heavy-path re-baseline:

```text
tracked LLM calls ≈ 24
recorded tokens ≈ 40.9K
total elapsed median ≈ 293s
quality = 0.8845
search calls = 2
```

최종 C1 Live Regression:

```text
tracked LLM calls = 10
recorded tokens = 27,248
total elapsed = 163.709s
quality = 0.8845
passed = true
search calls = 2
```

동일 heavy-path 계열에서 구조적으로 확인된 변화:

```text
tracked LLM calls
24 → 10
약 58.3% 감소
```

Token과 latency는 실행별 변동이 있으므로 동일 비율의 인과적 절감으로
일반화하지 않는다.

## 31.5 최종 Batch 구조

Round 1:

```text
Evidence Semantic        1
Claim Generation         1
Citation Verification    1
Claim Relevance          1
Answer Coverage          1
```

Coverage Round:

```text
Evidence Semantic        1
Claim Generation         1
Citation Verification    1
Claim Relevance          1
Answer Coverage          1
```

Coverage가 발생하는 heavy path의 tracked LLM call 구조는 총 10회까지
감소하였다.

## 31.6 품질 해석

최종 C1 Live Run:

```text
quality = 0.8845
passed = true
initial coverage = partially_covered
final coverage = partially_covered
```

Coverage Replanning은 신규 문서와 신규 Evidence를 확보했으나,
최종 Evidence가 function-tool 등록, argument/result 흐름 및 tool-call lifecycle을
충분히 포함하지 못하여 Coverage Level은 개선되지 않았다.

최종 Evidence는 다음 주제에 집중되어 있었다.

```text
Agents + tools + built-in loop
Agents as tools / handoffs
MCP tools alongside function tools
```

따라서 이 실행의 PARTIALLY_COVERED 결과는 Claim batching이 Evidence 의미를
훼손한 문제로 판단하지 않는다. Upstream retrieval/replanning quality의
알려진 한계로 기록한다.

## 31.7 Stop Rule 및 비용 대비 효과 판단

Single-Agent Live Research는 현재 다음 수준까지 확보하였다.

```text
Live Web Search
HTTP/HTML Reading
Source Quality
Evidence-aware Selection
RRF Hybrid Retrieval
Semantic Evidence Relevance
Generative Claim
Semantic Citation Verification
Claim Relevance
Answer Coverage
Bounded Coverage Replanning
Budget
Observability
Batch Optimization
```

추가 미세조정으로 일부 호출, prompt 또는 coverage behavior를 더 개선할 수
있지만 현재 단계에서는 개발·테스트·분석 시간의 한계비용이 커졌다고 판단한다.

따라서:

```text
추가 Single-Agent micro-optimization
→ Deferred

현재 성능 Baseline
→ 고정

다음 학습 초점
→ Multi-Agent가 언제 필요한지,
   어떤 패턴이 있는지,
   Single-Agent 대비 품질·비용 효과가 있는지 검증
```

으로 전환한다.

미세조정은 폐기하지 않으며 다음 조건에서 다시 연다.

- 실제 사용에서 반복되는 동일 failure pattern이 확인됨
- Golden Dataset에서 품질 병목이 측정됨
- 비용 또는 latency가 실제 운영 요구를 위반함
- Multi-Agent 비교를 위한 Single-Agent baseline 보정이 필요함

## 31.8 다음 문서 작업

- [~] 지금까지의 프로젝트 작업 문서 최신화
- [ ] 현재 구현된 AIRA 기능·사용법·한계·개선방향 사용자 문서화
- [ ] Multi-Agent 학습·구현 Roadmap 별도 정리

# 32. 2026-08-13 Local/Hybrid Architecture Track — Phase 6~11 완료 기준

> 이 섹션은 2026-08-13 현재 Local LLM / Multi-Agent / Hybrid / Runtime Scaling
> 트랙의 최신 authoritative status이다. 앞선 역사적 Phase/Stage 기록의 "다음 단계"가
> 이 섹션과 충돌하면 이 섹션을 현재 상태로 우선한다.

## 32.1 현재 공식 위치

```text
Phase 0  Repository / Baseline Audit             COMPLETE
Phase 1  Hardware / Storage Baseline             COMPLETE
Phase 2  Local LLM Candidate Research            COMPLETE
Phase 3  Runtime Evaluation and Selection        COMPLETE
Phase 4  First Local Model Execution             COMPLETE
Phase 5  Local Model Benchmark                   COMPLETE
Phase 6  Local LLM Adapter Integration           COMPLETE
Phase 7  OpenAI vs Local Single-Agent            COMPLETE
Phase 8  Local Multi-Agent Minimum               COMPLETE
Phase 9  Single vs Multi-Agent Evaluation        COMPLETE
Phase 10 Heterogeneous / Hybrid Architecture     COMPLETE
Phase 11 Parallelism / Runtime Scaling           COMPLETE
Phase 12 Hardware Upgrade Decision               COMPLETE
```

Phase 11 완료 커밋:

```text
5c30358 feat: add bounded parallel source reading
```

## 32.2 Phase 6 — Local LLM Adapter Integration

Qwen3.5-4B를 범용 Main Agent로 채택하지 않고, 검증된 bounded small-worker 역할에
생산 경로로 통합하였다.

현재 Local worker 역할:

- Semantic Citation Verification — bounded first-pass verifier
- Claim Relevance — bounded classifier
- Answer Coverage — reviewer / critic

Deterministic planning과 high-judgment 역할을 무리하게 Local로 이전하지 않는다.

## 32.3 Phase 7 — OpenAI vs Local Single-Agent

동일 AIRA Single-Agent 구조에서 bounded worker backend만 OpenAI와 Local로 비교하였다.

Frozen comparison 핵심 결과:

```text
Citation exact agreement       100%
Claim relevance exact agreement 83.3%
Coverage level agreement        50%
OpenAI worker mean             ~67.22s
Local worker mean              ~19.10s
Observed local wall reduction  ~71.6%
Observed speedup               ~3.52x
```

Local answer coverage는 낙관 편향이 관찰되어 `fully_covered` 단독 판정을 최종
completeness gate로 사용하지 않는다.

## 32.4 Phase 8 — Local Multi-Agent Minimum

기존 deterministic Multi-Agent orchestrator를 재사용하고 Qwen3.5-4B를 bounded
advisory quality reviewer로 연결하였다. Multi-Agent 자체를 기본 실행 경로로
승격하지 않았다.

## 32.5 Phase 9 — Single vs Multi-Agent

Frozen workload 비교 결과에 따라 현재 기본 정책을 다음과 같이 확정하였다.

```text
Single-Agent
→ default

Multi-Agent
→ workload-dependent escalation

Qwen3.5-4B
→ bounded advisory reviewer
```

작은 in-memory fixture에서 orchestration 자체의 추가 비용은 작았으나, Local
reviewer 호출이 대부분의 추가 latency를 차지하였다. 절대 latency는 일반화하지
않는다.

## 32.6 Phase 10 — Hybrid Role-Routed Architecture

현재 역할 정책의 핵심:

```text
Deterministic
- task decomposition
- query planning
- source quality
- document selection
- synthesis/control paths where deterministic logic is sufficient

OpenAI / stronger model escalation
- evidence relevance / claim generation 등 high-judgment 역할
- 필요 시 authoritative review

Local qwen3.5:4b
- semantic citation
- claim relevance
- answer coverage reviewer
```

OpenAI-heavy vs Hybrid frozen comparison에서는 모든 6 pair가 성공했고, Hybrid가
bounded local worker 세 역할을 대체하면서 worker wall time을 약 64.2% 줄였다.
이는 해당 benchmark 범위에 한정된 수치이다.

## 32.7 Phase 11 — Parallelism / Runtime Scaling

안전 감사 결과 전체 pipeline과 dependency stage를 무조건 병렬화하지 않았다.

현재 정책:

```text
Source Search
→ SERIAL 유지
  shared usage/budget 상태 때문에 병렬화 보류

Source Reading
→ BOUNDED PARALLEL 허용

Local Qwen workers
→ concurrency = 1 유지

Whole pipeline / Multi-Agent dependency chain
→ dependency-sequential 유지
```

Source Reading 실측:

```text
Synthetic, 8 candidates × 50ms
c=1  0.4013s
c=2  0.2011s  1.996x
c=4  0.1009s  3.977x

Real HTTP, 8 fixed URLs
c=1  mean 2.277s
c=2  mean 0.921s  2.472x
c=4  mean 0.851s  2.676x
```

1/2/4 모두 source별 성공/실패 상태가 동일했고, 성공 문서 character count도
동일하였다. 실제 8개 URL 중 6개 READ, 2개 `DocumentHttpError` 패턴이 모든
concurrency에서 동일했다.

Production contract:

```text
AIRA_SOURCE_READ_CONCURRENCY
adapter default = 1
live runtime default = 2
allowed = 1..8
safe fallback = 1
4 = aggressive benchmark option
```

Live smoke:

```text
quality = 0.9345
2 / 2 selected documents = read
ollama-local provenance observed
```

최종 regression:

```text
4635 passed in 16.70s
Ruff = All checks passed
git diff --check = clean
```

## 32.8 Phase 12 — Hardware Upgrade Decision — Evaluation Plan

Phase 12에서 평가한 대상은 다음과 같다. 최종 결과는 32.9에 기록한다.

평가 대상:

- 현재 RTX 3060 Ti 8GB / i5-9600KF / 약 31GiB RAM 유지 여부
- VRAM 증가의 실제 AIRA workload 편익
- Qwen3.5-9B, Ministral 3 8B 및 더 큰 comparator의 실행 가능성
- CPU/RAM platform 병목 여부
- Local 확대와 OpenAI/Hybrid 유지의 비용·품질 trade-off

Phase 12 평가 중에는 특정 GPU/플랫폼 구매를 선결론으로 확정하지 않았다.

## 32.9 Phase 12 — Hardware Upgrade Decision — COMPLETE

Phase 12는 실제 AIRA workload를 기준으로 현재 하드웨어 유지 여부를 검증했다.

현재 baseline:

```text
CPU  Intel Core i5-9600KF
RAM  약 31 GiB
GPU  NVIDIA GeForce RTX 3060 Ti 8 GiB
Local bounded worker  qwen3.5:4b Q4_K_M
```

Larger-model capacity 결과:

```text
qwen3.5:4b
→ 100% GPU

llama3.1:8b
→ 100% GPU
→ capacity probe only; production bounded-role quality 비교 대상 아님

qwen3.5:9b
→ 13% CPU / 87% GPU
→ 8 GiB VRAM 경계 확인

ministral-3:8b
→ 22% CPU / 78% GPU
→ 8 GiB VRAM에서 부분 CPU offload
```

동일한 세 production-aligned bounded-role benchmark에서 Qwen3.5-4B가 전체적인
quality / latency / safety trade-off에서 가장 적합했다.

```text
Total wall time, three role benchmarks
Qwen3.5-4B      302.21 s
Qwen3.5-9B      545.39 s  (~1.80x 4B)
Ministral 3 8B  501.90 s  (~1.66x 4B)
```

Qwen3.5-9B는 semantic-citation holdout 한 항목에서 개선을 보였지만 claim relevance와
answer coverage에서 전반적 우위를 확보하지 못했고, false-direct / false-full 오류도
관찰되었다. Ministral 3 8B 역시 4B를 대체할 품질 우위를 보이지 못했다.

Current-worker headroom 측정:

```text
Qwen3.5-4B = 100% GPU
VRAM peak = 4755 MiB
VRAM minimum free = 3117 MiB
RAM minimum available = 23975 MiB
GPU temperature max = 74 C
GPU power max = 199.49 W
```

최종 결정:

```text
KEEP current hardware
DEFER GPU upgrade
NO current evidence for RAM upgrade
NO current evidence for CPU/platform upgrade
KEEP Qwen3.5-4B bounded local worker
KEEP Hybrid architecture
```

Hardware upgrade는 영구 배제가 아니라 조건부 재평가 대상으로 남긴다. 더 큰 Local
model이 실제 AIRA role에서 명확한 품질 우위를 보이면서 VRAM에 의해 제한되거나,
실제 parallel Local-worker workload, context/KV-cache pressure, OpenAI 비용 구조 또는
profiler evidence가 현재 hardware를 병목으로 확인할 때 다시 평가한다.

**Phase 12 status: COMPLETE.**


# 33. 2026-08-14 Local Document Semantic Research Vertical Slices

> 이 섹션은 Stage 4 Local Document Expansion의 최신 authoritative status이다.
> Stage 4 전체 완료가 아니라 TXT/Markdown, text-based PDF 및 text-bearing HWPX vertical slice 완료를 기록한다.

## 33.1 상태

```text
Stage 4 Local Document Expansion
→ IN PROGRESS

Initial TXT/Markdown Semantic Vertical Slice
→ COMPLETE

Text-based PDF Vertical Slice
→ COMPLETE

Text-bearing HWPX Vertical Slice
→ COMPLETE
```

완료된 범위:

- UTF-8 `.txt`, `.md`, `.markdown`
- text-based `.pdf` (`pypdf` page-by-page extraction)
- text-bearing `.hwpx` (safe ZIP direct-read + `defusedxml`)
- nonblank physical page sections and `page_number` evidence provenance
- HWPX body-section provenance (`hwpx_section_index`, `hwpx_package_path`)
- 실제 Local in-memory source search와 reader
- `search_query_text` query provenance
- `local_path`와 `filename` provenance
- paragraph 및 exact character range 보존
- embedding + lexical RRF shortlist와 semantic evidence selection
- generated claim integration
- semantic citation, claim relevance, answer coverage integration
- `aira research` deterministic/offline 기본 계약 보존
- `--mode semantic` 명시적 opt-in
- deterministic 및 semantic 실제 CLI smoke에서 `report.md`/`result.json` 생성
- semantic smoke에서 whole document가 아닌 relevant paragraph 선택
- deterministic + semantic PDF CLI smoke and exact citation range verification
- malformed/encrypted/no-text PDF clear failure
- real Hancom HWPX adapter + deterministic CLI smoke (`0..96`)
- semantic HWPX section-2 evidence + exact citation (`114..303`)
- full regression `4722 passed`
- Ruff `All checks passed`, `git diff --check` 통과

미완료 범위:

- scanned PDF/OCR, HWP binary, DOCX
- line number provenance
- table-specialized parsing
- persistent indexing/embedding cache
- Web + Local unified Integrated RAG

현재 다음 제품 순서:

```text
Local Document expansion
→ Integrated Web+Local RAG
→ Patent Research Vertical Slice
```
