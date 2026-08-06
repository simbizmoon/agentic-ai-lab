# Agentic AI Lab — DECISIONS

## 문서 목적

본 문서는 Agentic AI Lab 및 AIRA(Agentic Intelligence Research Assistant)
프로젝트에서 확정된 주요 기술·제품·운영 결정을 기록한다.

과거 결정은 삭제하지 않고 상태를 변경하여 이력을 보존한다.

결정 상태는 다음과 같이 사용한다.

- `확정`: 현재 유효한 결정
- `수정 확정`: 기존 결정을 수정하여 현재 유효하게 유지
- `대체됨`: 후속 결정으로 대체되어 현재 적용하지 않음
- `완료 이력`: 과거 작업의 완료 기록으로 보존
- `완료된 Baseline`: 최종 제품은 아니지만 비교·테스트 기준으로 유지
- `보류`: 필요성이 확인될 때까지 적용하지 않음

AIRA의 최상위 제품 목표는 `AIRA_PROJECT_CHARTER.md`를 기준으로 한다.

---

## D-001 — 기본 운영체제

- 상태: 확정
- 날짜: 2026-07-23
- 결정: Ubuntu를 기본 개발환경으로 사용한다.

---

## D-002 — 프로젝트 경로

- 상태: 확정
- 날짜: 2026-07-23
- 경로: `/home/moon/Project/agentic-ai-lab`

---

## D-003 — 원격 저장소

- 상태: 확정
- 날짜: 2026-07-23
- 주소: `https://github.com/simbizmoon/agentic-ai-lab.git`
- 기본 브랜치: `main`

---

## D-004 — Python 환경

- 상태: 확정
- 날짜: 2026-07-23
- Python: 3.12
- 가상환경: `/home/moon/Project/agentic-ai-lab/.venv`

---

## D-005 — 기본 언어

- 상태: 확정
- 날짜: 2026-07-23
- 수업과 주요 문서: 한국어
- 코드 식별자와 기술 표준: 영어

---

## D-006 — 기본 애플리케이션 인터페이스

- 상태: 수정 확정
- 최초 날짜: 2026-08-03
- 수정 날짜: 2026-08-06
- 언어: Python
- 데이터 검증: Pydantic
- 초기 실행 인터페이스: CLI
- API Framework: FastAPI

결정:

- 초기 Single Research Agent는 CLI를 기본 실행 경로로 한다.
- FastAPI는 Agent Runtime이 안정된 이후 API 또는 UI 연동이 필요할 때 최소 범위로 도입한다.
- Domain Model, Research Pipeline 및 Agent Runtime은 FastAPI에 직접 의존하지 않는다.
- FastAPI를 사용하더라도 외부 인터페이스 계층으로 한정한다.

---

## D-007 — 에이전트 개발 순서

- 상태: 수정 확정
- 최초 날짜: 2026-07-23
- 수정 날짜: 2026-08-06

결정:

- 실제 LLM, Tool, 인터넷 및 로컬 자료 검색을 사용하는 Single Research Agent를 먼저 완성한다.
- Single Agent를 기본 실행 경로로 사용한다.
- Multi-Agent는 동일한 Evaluation Dataset에서 품질, 비용 또는 처리시간의 의미 있는 개선이 확인될 때만 선택적으로 사용한다.
- Agent 수 증가 자체를 프로젝트의 발전으로 간주하지 않는다.

---

## D-008 — 데이터 저장

- 상태: 수정 확정
- 최초 날짜: 2026-07-23
- 수정 날짜: 2026-08-06
- 소스와 기준 문서: Git 프로젝트
- Secret: Git에서 제외된 환경변수 또는 Secret 저장소

결정:

- 초기 실행 결과는 파일 기반 Markdown 및 JSON 저장을 기본으로 한다.
- 초기 Cache 후보는 Query 결과 Cache, Source 원문 Cache, Parsing Cache 및 Embedding Cache로 한다.
- SQLite는 실행 이력, 비용, Cache 및 연구 결과 조회 요구가 확인될 때 우선 도입한다.
- PostgreSQL은 실제 동시 사용자 또는 운영 요구가 확인될 때 도입한다.
- Redis는 Queue, Worker 또는 분산 Cache의 실제 필요성이 확인될 때까지 보류한다.
- 저장소 구현은 가능한 경우 교체 가능한 Repository 계약 뒤에 둔다.

권장 도입 순서:

```text
파일 기반 저장
→ 필요성 검증
→ SQLite
→ 운영 및 동시성 요구 확인
→ PostgreSQL
```

---

## D-009 — 인간 승인

- 상태: 수정 확정
- 최초 날짜: 2026-07-23
- 수정 날짜: 2026-08-06

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

---

## D-010 — 기존 전체 Phase 구조

- 상태: 대체됨
- 최초 날짜: 2026-08-03
- 대체 결정: D-013
- 이유:
  - 실제 진행 결과 Phase 9부터 Phase 12까지 역할이 세분화되었다.
  - 현재 구현 상태와 최종 목표에 맞게 구조를 다시 정렬할 필요가 있었다.

---

## D-011 — Phase 3 보안 심화 기능 동결

- 상태: 확정
- 날짜: 2026-08-03

결정:

- Transparency Log
- Merkle Proof
- Witness Quorum
- Signed Gossip Bundle
- Trust Decision Receipt

위 기능은 현재 범위에서 동결한다.

재개 조건:

- 실제 운영 요구가 확인됨
- 구체적인 보안 위협 모델이 확인됨
- 해당 기능이 AIRA의 핵심 품질 또는 신뢰성을 실질적으로 개선함

---

## D-012 — 기존 프로젝트 범위 재설정

- 상태: 대체됨
- 최초 날짜: 2026-08-05
- 대체 날짜: 2026-08-06
- 대체 결정: D-016

기존 결정:

- 프로젝트를 Phase 13에서 종료한다.
- Phase 14 이후의 신규 Phase를 만들지 않는다.
- 로컬에서 실제 연구에 사용할 수 있는 최소 AIRA를 완성한다.

대체 이유:

- Phase 13 결과는 전체 프로젝트에서 구현된 Responses API, Tool, RAG, Memory, Planning, Multi-Agent 및 비용 관리 기능을 충분히 통합하지 못하였다.
- 사용자가 원래 목표로 한 인터넷 및 로컬 자료 통합 Research Agent와 현재 Runtime 사이에 중요한 차이가 확인되었다.
- 단순 구현 편의를 이유로 AIRA의 최종 목표를 로컬 문서 검색 및 결정론적 Pipeline으로 축소하지 않기로 하였다.

보류 유지 항목:

- 분산 Worker Cluster
- Redis 또는 RabbitMQ Queue
- Kubernetes
- 복잡한 조직·권한 시스템
- 대규모 Observability Stack
- 상용 수준 Web UI
- 완전 자율 Multi-Agent 조직

---

## D-013 — 기존 학습 Phase 구조

- 상태: 완료 이력
- 날짜: 2026-08-05

기존 Phase 구조:

0. 프로젝트 기반
1. Agentic AI 기초
2. OpenAI API 기초
3. Structured Outputs와 데이터 검증
4. Tool Calling
5. Workflow와 상태 관리
6. RAG
7. Memory
8. Planning Agent
9. Single Research Agent
10. 제한된 Multi-Agent Research
11. Evals, Guardrails, Reliability
12. Application, Persistence, Background Jobs
13. Practical AIRA Integration and Delivery

결정:

- Phase 0부터 Phase 13은 Agentic AI 핵심 구성요소를 학습하고 개별적으로 구현한 기존 교육·개발 과정으로 보존한다.
- 위 Phase 구조는 완료 이력이며 앞으로의 제품 통합 작업을 제한하지 않는다.
- 향후 AIRA 통합 작업은 신규 Phase 번호보다 `AIRA_PROJECT_CHARTER.md`의 Stage 구조와 Integration Work Item으로 관리한다.
- 기존 Phase 및 Lesson의 구현 결과는 Capability Audit의 대상이 된다.

---

## D-014 — 기존 Phase 13 AIRA MVP

- 상태: 완료된 Baseline
- 최초 날짜: 2026-08-05
- 재분류 날짜: 2026-08-06

기존 필수 결과:

- CLI 연구 실행
- 프로젝트 문서 또는 준비된 Source 입력
- Evidence, Claim, Citation 추적
- 근거 기반 보고서
- 기본 평가와 Guardrail
- 실행 및 결과 저장
- 핵심 실패 처리
- 실제 예제
- 사용자 가이드

재분류 결정:

- Phase 13에서 완성한 Local Research Runtime은 폐기하지 않는다.
- 해당 Runtime은 최종 AIRA가 아니라 결정론적 Offline Baseline, Schema 검증, Pipeline Regression Test, 외부 API 없는 테스트, 제한된 Fallback 및 향후 LLM 기반 Agent와의 비교 기준으로 유지한다.

확인된 주요 한계:

- 외부 LLM 기본 실행 경로 미연결
- 인터넷 검색 미지원
- 기존 RAG Runtime 미통합
- Memory 미통합
- 동적 Tool 선택 미지원
- Evidence 충분성에 따른 Replanning 미지원
- 복수 자료의 의미 기반 비교·충돌 분석 제한
- Provider 교체 구조의 실제 Runtime 검증 부족

PostgreSQL, Redis, Nginx, OCI 운영 배포는 실제 필요가 있을 때 별도 Backlog에서 결정한다.

---

## D-015 — 구현 단위 관리

- 상태: 수정 확정
- 최초 날짜: 2026-08-05
- 수정 날짜: 2026-08-06

결정:

- 향후 작업 수를 임의의 Lesson 개수로 제한하지 않는다.
- 하나의 작은 Schema 또는 Error Class만을 위한 독립 작업을 만들지 않는다.
- 각 Work Item은 사용자가 확인할 수 있는 기능, 통합 결과, 감사 결과 또는 의사결정을 생성해야 한다.
- 테스트 수 증가 자체를 목표로 하지 않는다.
- 기존 구현을 우선 재사용하고 중복 추상화를 금지한다.
- 각 Work Item은 Audit, Design, Implementation, Unit Test, Integration Test, E2E Test, Documentation 및 Acceptance Criteria 중 필요한 범위를 명확히 정의한다.
- 각 코드 변경 단위는 관련 테스트, Ruff 및 Git Diff 검토를 거친다.

---

## D-016 — AIRA 최상위 제품 목표

- 상태: 확정
- 날짜: 2026-08-06
- 기준 문서: `AIRA_PROJECT_CHARTER.md`

결정:

- AIRA는 사용자의 관심 분야, 연구주제 또는 선행특허 조사 요청을 처리하는 분석·제안형 AI Research Agent로 개발한다.
- AIRA는 인터넷 공개 자료와 사용자가 지정한 로컬 문서를 검색·수집한다.
- 로컬 문서의 초기 목표 형식은 TXT, Markdown, PDF, HWP 및 HWPX로 한다.
- 수집한 자료의 관련성, 중요도, 신뢰도, 최신성 및 증거 수준을 평가한다.
- 자료를 정리·요약·비교·분석하고, 일치점, 차이점, 충돌, 위험요소 및 시사점을 도출한다.
- 최종 결과에는 근거 기반 제안사항과 구조화된 연구 리포트를 포함한다.
- 모든 핵심 Claim에는 추적 가능한 Evidence와 Citation을 연결한다.
- 조사 범위, 검색 방법, 비용, 한계 및 남은 불확실성을 공개한다.
- AIRA를 단순 로컬 문서 검색기, 요약기 또는 고정형 Workflow로 정의하지 않는다.

---

## D-017 — Existing Capability Audit 우선

- 상태: 확정
- 날짜: 2026-08-06

결정:

- 신규 기능 구현 전에 기존 `agentic-ai-lab` 저장소를 감사한다.
- OpenAI Responses API, OpenAI Python SDK, Structured Outputs, Tool Calling, Tool Registry, Tool Execution Loop, Workflow, State, RAG, Chunking, Embedding, Retrieval, Citation, Memory, Planning Agent, Replanning, Single Research Agent, Multi-Agent, Evals, Guardrails, Tracing, Usage, Token, 비용 계산, Application, Persistence, Retry, Cancellation 및 Background Job을 우선 확인한다.
- 각 기능은 Implemented, Tested, Runtime-connected 및 Production-ready 상태를 구분하여 기록한다.
- 기존 구현이 사용 가능하면 우선 재사용한다.
- 직접 연결하기 어려운 경우 Adapter 추가를 우선 검토한다.
- 재작성은 기존 구현이 구조적으로 호환되지 않거나, 심각한 품질·보안 문제가 있거나, 재사용 비용이 더 크다는 근거가 확인될 때만 허용한다.
- 재작성, 보류 및 폐기 결정은 Audit Report 또는 본 문서에 기록한다.

---

## D-018 — 점진적 Single-Agent 개발

- 상태: 확정
- 날짜: 2026-08-06

결정:

- 실제로 처음부터 끝까지 동작하는 최소 LLM 기반 Single Research Agent를 먼저 완성한다.
- 초기 Agent는 최소한 다음 흐름을 지원한다.

```text
Research Request
→ LLM Research Planning
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

- 초기 버전은 전체 흐름의 실제 작동을 우선한다.
- PDF/HWP 고도화, Hybrid RAG, 교차검증, Memory, 전문 Skill, Persistence 및 Background Job은 실제 필요성과 평가 결과에 따라 단계적으로 추가한다.
- 각 기능은 Audit, 재사용 결정, 통합 설계, 구현, 테스트 및 실제 연구 평가를 거쳐 채택한다.
- Multi-Agent는 Single-Agent 대비 의미 있는 개선이 평가로 확인될 때만 도입한다.

---

## D-019 — LLM Provider 독립성

- 상태: 확정
- 날짜: 2026-08-06

결정:

- 초기 구현은 기존 OpenAI Responses API 또는 OpenAI SDK 코드를 활용할 수 있다.
- AIRA의 Domain Model, Research Pipeline, Tool System, RAG, Evidence, Claim, Citation, Report 및 Agent State는 OpenAI 전용 객체에 직접 의존하지 않는다.
- 공통 LLM Provider 계약을 정의하고 Provider별 Adapter를 사용한다.
- 후보 Provider는 OpenAI Responses API, 다른 상용 LLM API, OpenAI-compatible API, Ollama, 로컬 LLM Runtime 및 Deterministic Test Provider로 한다.
- 공통 Provider는 가능한 범위에서 Structured Output, Tool Call, Planning, Query 생성, Evidence 분석, Claim 및 제안사항 생성, Report 합성, Usage, 비용 추정 및 오류를 정규화한다.
- 모델 교체는 동일한 Evaluation Dataset에서 품질, 비용 및 처리시간을 비교한 뒤 결정한다.
- 저난도 반복 작업에는 장기적으로 저가 API 또는 로컬 LLM 사용을 검토한다.

---

## D-020 — Usage 및 비용 관리

- 상태: 확정
- 날짜: 2026-08-06

결정:

- 기존 Usage, Token 및 비용 계산 코드를 우선 감사하고 재사용한다.
- Token 계산, 실제 API Usage 수집, 입력·출력·캐시 Token 구분, 모델별 가격, 가격 기준일, 실행 전 예상비용, 실행 후 실제비용, 실행별·누적비용, Budget 초과 처리 및 검색 API 비용 확장 가능성을 구분하여 확인한다.
- Agent 실행에는 최대 LLM 호출 횟수, Search 호출 횟수, Tool 호출 횟수, Source 수, Chunk 수, 입력·출력 Token, 반복 횟수, 실행시간 및 실행당 비용 제한을 적용할 수 있어야 한다.
- Budget 초과 시 실행을 중단하거나 사용자 승인을 요구한다.
- 검색한 모든 문서 전체를 LLM에 보내지 않는다.
- 중복 제거, Metadata 필터링, Chunking, Keyword Search, Embedding Retrieval 및 Reranking을 통해 관련 Evidence만 LLM에 제공한다.
- 동일 Query, Source, Parsing 및 Embedding 결과의 Cache를 검토한다.
- 모델 가격은 변경 가능하므로 가격 정보의 기준일과 Source를 관리한다.

---

## D-021 — ChatGPT와 Codex 역할 분담

- 상태: 확정
- 날짜: 2026-08-06

결정:

- ChatGPT의 `Agentic AI Lab` 프로젝트는 프로젝트 최상위 목표, 기준 문서, Capability Audit, Target Architecture, 기술 의사결정, 작업 순서, Tool 및 Skill 설계, Codex 작업지시서, 테스트·Git Diff 검토 및 장기 프로젝트 문맥을 총괄한다.
- Codex는 로컬 저장소 탐색, 기존 코드 감사, 코드 구현, Adapter 및 Runtime Integration, 테스트 작성, Refactoring, Ruff 수정 및 Git Diff 작성의 주 실행 도구로 사용한다.
- Codex의 결과를 자동으로 승인하지 않는다.
- ChatGPT와 사용자는 기준 문서, 실제 코드, 테스트 결과 및 Git Diff를 근거로 결과를 검토한다.
- Codex Usage Limit이 소진된 기간에는 ChatGPT에서 문서 정리, Audit 설계, Target Architecture, Tool·Skill Registry 및 Codex용 작업지시서를 준비한다.

---

## D-022 — Tool, Skill, Plugin 및 MCP 도입 순서

- 상태: 확정
- 날짜: 2026-08-06

결정:

- Tool은 Agent가 외부 환경을 검색, 읽기, 분석 또는 저장하기 위해 호출하는 개별 실행 기능으로 정의한다.
- 각 Tool은 이름, 설명, 입력·출력 Schema, 권한, 비용, Timeout, Retry, 오류 및 Trace 정책을 가져야 한다.
- Skill은 검증된 여러 Tool과 판단 절차를 결합한 재사용 가능한 연구 방법으로 정의한다.
- 초기 Skill 후보는 General Web Research, Official Source Research, Academic Literature Review, Local Document Analysis, Cross-source Verification, Patent Prior-art Analysis 및 Project Document Consistency Audit로 한다.
- Tool과 Single-Agent Runtime이 안정된 이후 Skill을 정형화한다.
- Plugin, ChatGPT App 및 MCP 연결은 독립 실행 가능한 Single-Agent Runtime 완성 이후 검토한다.
- 장기적으로 ChatGPT와 로컬 AIRA Runtime의 안전한 연결을 위해 MCP 또는 App 구조를 검토할 수 있다.
- Plugin 또는 MCP 구현 자체를 초기 제품 목표보다 우선하지 않는다.

---

## D-023 — 프로젝트 운영 방식

- 상태: 확정
- 날짜: 2026-08-06

결정:

- 기존 Phase 0~13은 학습 및 구현 이력으로 유지한다.
- 앞으로의 제품 통합은 `AIRA_PROJECT_CHARTER.md`의 Stage와 Integration Work Item으로 관리한다.
- 각 Work Item은 기존 코드 감사부터 시작한다.
- 기능 추가 전 이미 구현되어 있는지, 테스트되어 있는지, 현재 Runtime에 연결되어 있는지, 실제 자료와 외부 API로 검증되었는지, Adapter로 재사용 가능한지를 확인한다.
- 기능 수의 증가보다 실제 연구 품질, Citation 정확도, 비용, 처리시간 및 재현성 개선을 우선한다.
- 중요한 설계 변경은 본 문서에 추가하고 변경 이력을 보존한다.

---

## D-024 — 프로젝트 문서 우선순위

- 상태: 확정
- 날짜: 2026-08-06

AIRA 제품 목표와 통합 개발에 관한 문서 우선순위는 다음과 같다.

1. `AIRA_PROJECT_CHARTER.md`
2. 향후 작성할 `AIRA_TARGET_PRODUCT_SPEC.md`
3. 향후 작성할 `AIRA_TARGET_ARCHITECTURE.md`
4. `DECISIONS.md`
5. `AIRA_PROJECT_AUDIT_REPORT.md`
6. 향후 작성할 `AIRA_INTEGRATION_PLAN.md`
7. 기존 `MASTER.md`
8. 기존 `ROADMAP.md`
9. 기존 `CURRICULUM.md`
10. 기존 Phase 및 Lesson 문서

적용 원칙:

- 하위 문서가 상위 문서와 충돌하면 임의로 수정하지 않고 충돌을 보고한다.
- 기존 코드의 사실관계는 문서의 주장보다 실제 코드, 테스트 및 실행 결과를 우선하여 확인한다.
- 문서 우선순위가 코드의 실제 구현 상태를 대체하지는 않는다.

---

## D-025 — 변경 관리

- 상태: 확정
- 날짜: 2026-08-06

AIRA의 핵심 목표 또는 주요 Architecture를 변경할 때에는 다음을 기록한다.

- 변경 이유
- 변경 전 내용
- 변경 후 내용
- 기존 코드에 미치는 영향
- 문서에 미치는 영향
- 일정 및 작업량 영향
- 비용 영향
- 보안 및 개인정보 영향
- 사용자 승인 여부와 날짜

단순 구현 편의를 이유로 AIRA의 최종 목표를 축소하지 않는다.

기술적, 비용적 또는 보안상 한계가 확인되면 그 사실을 명확히 기록하고 단계적 구현 범위를 조정할 수 있다.

---

## D-026 — Live Research Vertical Slice 우선 통합

- 상태: 확정
- 날짜: 2026-08-06
- 근거 문서:
  - `AIRA_PROJECT_AUDIT_REPORT.md`
  - `AIRA_CAPABILITY_MATRIX.md`

결정:

- Existing Capability Audit 결과, 기존 저장소는 Domain Schema, 검증,
  OpenAI Planning, Tool 실행 기반, Trace, Usage, Budget 및 Application
  실행관리 기능을 광범위하게 구현하고 있으며 현재 전체 테스트와 Ruff를
  통과한다.
- 현재 `aira research`는 최종 AIRA가 아니라 결정론적 Offline Research
  Baseline으로 유지한다.
- 첫 실제 제품 통합은 `Live Research Vertical Slice`로 수행한다.
- Vertical Slice는 하나의 연구 질문을 입력받아 실제 인터넷 자료를 검색하고,
  제한된 Source를 읽고, 실행별 폴더에 자료와 Metadata 및 실행정보를 저장한
  뒤 결과를 다시 읽을 수 있는 최소 End-to-End 경로를 의미한다.
- 첫 Vertical Slice는 Single-Agent 방식으로 구현한다.
- 첫 구현의 신규 핵심 기능은 다음으로 제한한다.
  1. 실제 Web Search Adapter
  2. 실제 HTTP/HTML Source Reader
  3. Source Artifact Writer
  4. Concrete Live Research Runner
  5. CLI Live 실행 경로
- 기존 `ResearchRequest`, Search Query, Source Candidate, Source Document,
  Search Port, Reader Port, Result Writer, Guardrail, Usage, Budget, Trace 및
  Application Execution Service를 우선 재사용한다.
- 범용 Planning Tool Loop는 첫 Vertical Slice의 필수 실행 경로에서 제외한다.
  실제 Search와 Reader가 검증된 후 연결 가치를 다시 평가한다.
- RAG, Memory, PDF/HWP/HWPX 고도화, Skill, MCP, Background Job 및
  Multi-Agent는 첫 Vertical Slice 완료 이후 평가 결과에 따라 통합한다.
- 신규 코드의 첫 목표는 기능 수가 아니라 다음 수직 경로의 실제 성공이다.

```text
Research Question
→ Limited Query Planning
→ Live Web Search
→ Limited Source Selection
→ HTTP/HTML Reading
→ Source and Metadata Storage
→ Usage, Error and Trace Storage
→ Re-readable Run Result
```

완료 조건:

- 실제 인터넷 검색 결과가 하나 이상 생성된다.
- 최소 하나의 실제 웹 문서 본문을 읽는다.
- 검색 Query, Source URL, 제목, Provider, 검색·수집 시각 및 오류 상태를
  실행별 폴더에 저장한다.
- Source 수와 Search 호출 수에 명시적인 상한을 둔다.
- Offline Baseline의 기존 테스트를 깨뜨리지 않는다.
- 전체 `pytest`와 Ruff가 통과한다.
- 실제 API 또는 네트워크 Smoke Test 결과를 Fake 기반 Unit Test와 구분하여
  기록한다.
