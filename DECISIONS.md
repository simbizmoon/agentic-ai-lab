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

---

## D-027 — 첫 Web Search Provider와 통합 방식

- 상태: 확정
- 날짜: 2026-08-06
- 근거 문서: `AIRA_SEARCH_PROVIDER_DECISION.md`

결정:

- AIRA Live Research Vertical Slice의 첫 Web Search Provider는
  Tavily Search API로 한다.
- 초기 구현은 Tavily Python SDK가 아니라 직접 REST 호출과 `httpx` Adapter를
  사용한다.
- `httpx`는 현재 가상환경에 설치되어 있더라도 전이 의존성에 기대지 않고
  `pyproject.toml`의 직접 Runtime Dependency로 선언한다.
- Tavily 전용 설정은 초기에는 전역 OpenAI 설정과 분리한다.
- 기본 환경변수는 `TAVILY_API_KEY`로 한다.
- 선택적 Project 추적에는 `TAVILY_PROJECT_ID`를 사용한다.
- 초기 Search 요청은 `search_depth=basic`, `auto_parameters=false`,
  `include_answer=false`, `include_raw_content=false`,
  `include_images=false`, `include_usage=true`를 사용한다.
- Search Provider는 Search Result와 Metadata만 반환하고,
  원문 수집은 별도 HTTP/HTML Source Reader가 담당한다.
- Tavily 전용 응답 객체는 AIRA Domain으로 노출하지 않는다.
- Brave Search API, SerpApi 및 OpenAI Built-in Web Search는
  후속 비교·확장 후보로 유지한다.
- 첫 구현에서는 복수 Provider, 자동 Fallback, Tavily Extract·Crawl·Research,
  Advanced Search 기본값 및 자동 Retry Loop를 제외한다.

## Live Research Evidence Chunking and Source Quality

- Live web documents no longer use the complete document as one evidence item.
- Live evidence is selected deterministically from paragraph-sized chunks.
- Each live source contributes at most three evidence items.
- Each evidence excerpt is limited to 1,200 characters.
- Evidence retains exact source-document character offsets for citation traceability.
- Code-like API examples receive a relevance penalty but are not categorically removed.
- Local-document research continues to use whole-document evidence.
- Live web sources use a separate deterministic quality evaluator.
- Source quality currently records authority, primary-source, recency, completeness, and traceability scores.
- Source-quality scores do not yet reorder or filter search candidates.

## Quality-Aware Live Source Selection

- `maximum_sources` now means the maximum number of readable documents used for evidence and reporting.
- Live search oversamples candidates up to three times `maximum_sources`, bounded by Tavily configuration.
- All discovered candidates may be read before final document selection.
- Successfully read documents are evaluated before evidence extraction.
- Final documents are ordered by source-quality score, authority, primary-source score, provider score, and original rank.
- Only selected documents contribute evidence, claims, citations, and source-quality evaluations.
- Local-document research retains its existing selection behavior.
- Source authority alone is insufficient for final selection; topical relevance and source diversity require a separate follow-up design.
---

## D-028 — Evidence-aware Source Backfill 및 최소 Source 품질 Gate

- 상태: 확정
- 날짜: 2026-08-06
- 적용 범위: Quality-aware Selector를 사용하는 Live Research Pipeline

### 문제

기존 Live Research Pipeline은 품질평가 후 `maximum_sources`만큼 문서를 먼저
선택한 뒤 선택된 문서에 대해서만 Evidence를 추출하였다.

이 구조에서는 선택된 문서가 `NO_EVIDENCE`를 반환해도 다음 순위 문서로
교체되지 않았다. 따라서 검색·읽기 후보가 충분히 존재하더라도 최종 보고서가
하나의 Evidence Source만 사용하는 문제가 발생하였다.

또한 단일 Source 보고서가 Claim 및 Citation Coverage 점수만으로
`excellent`, `passed=yes` 판정을 받을 수 있었다.

### 결정

- `maximum_sources`는 최초 선택 문서 수가 아니라 최종적으로 유효 Evidence를
  제공한 Source의 최대 개수로 해석한다.
- Quality-aware Selector는 품질 하한선을 통과한 전체 문서의 결정론적 순위를
  제공할 수 있어야 한다.
- Pipeline은 순위 문서를 하나씩 Evidence 추출기에 전달한다.
- `NO_EVIDENCE` 문서는 최종 Source quota를 소비하지 않는다.
- Evidence가 없는 문서가 나오면 다음 순위 문서로 Backfill한다.
- 다음 중 하나가 충족되면 Backfill을 종료한다.
  - 유효 Evidence Source 수가 `maximum_sources`에 도달함
  - 적격 후보를 모두 소진함
- 정규화된 URL이 같은 Source는 한 번만 시도하고 한 번만 계산한다.
- 최종 `document_set`에는 실제 Evidence를 제공한 문서만 포함한다.
- `source_quality_evaluations`도 최종 Evidence Source에 대응하는 평가만
  포함한다.
- Workspace metadata에는 최소한 다음을 기록한다.
  - `read_candidate_count`
  - `evidence_attempted_document_count`
  - `selected_document_count`
  - `evidence_source_count`
  - `backfilled_document_count`
  - `no_evidence_document_count`

### 최소 Evidence Source Gate

Quality-aware Selector가 활성화된 Live Pipeline에는 다음 기준을 적용한다.

```text
minimum_evidence_sources = min(2, maximum_sources)
```

- 실제 Evidence Source 수가 위 기준보다 적으면
  `LOW_SOURCE_DIVERSITY`를 `error`로 기록한다.
- 이 경우 점수 자체가 높더라도 최종 품질은 `passed=false`가 된다.
- `maximum_sources=1`인 요청은 Source 1개로 통과할 수 있다.
- 결정론적 Offline Baseline에는 이 Gate를 적용하지 않아 기존 호환성을
  유지한다.

### Evidence Noise 정책

- Markdown 문서 색인
- 다중 링크 카드 목록
- 코드 실행 예시
- 단순 함수 호출
- Navigation fragment
- 구조적 코드 블록

위 항목은 Claim을 직접 지원하는 Evidence로 사용하지 않는다.

Hard Filter를 약화하여 Source 수를 채우지 않는다. 깨끗한 Evidence를 제공하는
후보가 없으면 Source 부족 상태를 정직하게 실패로 보고한다.

### 검증 결과

- 관련 회귀 테스트: `25 passed`
- 전체 회귀 테스트: `4157 passed`
- Ruff: 통과
- `git diff --check`: 통과
- Live Research:
  - 읽은 후보: 9
  - Evidence 시도 문서: 4
  - 최종 Evidence Source: 1
  - `NO_EVIDENCE`: 3
  - Evidence noise: 없음
  - 품질 결과: `passed=false`
  - 품질 문제: `LOW_SOURCE_DIVERSITY/error`

### 이유

AIRA의 Source 개수는 검색결과나 읽은 문서 수가 아니라 실제 Claim을 지원하는
Evidence Source 수를 의미해야 한다.

근거가 부족한 경우 Source 수를 인위적으로 채우거나 품질을 통과시키는 것보다
추가 조사 필요성과 불확실성을 명시하는 것이 프로젝트의 Citation,
Evidence Sufficiency 및 신뢰성 원칙에 부합한다.

---

## D-029 — Evidence 부족 시 제한형 Supplemental Search Replanning

- 상태: 확정
- 날짜: 2026-08-07
- 적용 범위: Quality-aware Selector를 사용하는 Live Research Pipeline

### 문제

D-028에서 Evidence-aware Backfill과 최소 Evidence Source Gate를 도입한 뒤,
OpenAI Responses API 공식문서 조사에서는 깨끗한 Evidence Source를 하나만
확보하였다.

Pipeline은 Source 부족을 정직하게 `LOW_SOURCE_DIVERSITY/error`로
보고했지만, 근거가 부족할 때 검색 전략을 수정하여 한 번 더 조사하는 기능은
없었다.

기존 범용 `PlanningAgentLoop`, `ReplanningService`,
`ReplanContextService`를 연결하는 방안도 검토하였다. 그러나 이 구성은
실패한 실행계획 전체를 LLM으로 다시 작성하고 실행하는 범용 Planning
시스템이므로, 단순한 Evidence Source 보완에 사용하기에는 범위와 복잡성이
과도하였다.

### 결정

Live Research Pipeline에 Research 전용의 제한형 Replanning을 추가한다.

```text
최초 Query 계획
→ 최초 검색·읽기
→ Evidence-aware Ranking 및 Backfill
→ 최소 Evidence Source 충족 여부 확인
   ├─ 충족: 추가 검색 없이 종료
   └─ 부족:
      → Supplemental Query 1개 생성
      → 추가 검색 1회
      → 기존 후보와 중복 제거
      → 신규 후보 읽기
      → 초기·추가 문서 전체 재평가
      → Evidence-aware Backfill 재실행
      → 종료
```

### Supplemental Query Planner

`SupplementalResearchQueryPlanner`는 다음 원칙으로 동작한다.

- 결정론적으로 Query 한 개만 생성한다.
- 기존 Query가 참조한 동일 Research Task를 사용한다.
- Query ID는 `{request_id}-query-supplemental-001` 형식을 사용한다.
- Query 유형은 `OFFICIAL`로 설정한다.
- `OFFICIAL_DOCUMENTATION` Source Type을 우선 조건에 포함한다.
- 기존 Query와 동일한 정규화 Query Text가 생성되면
  `official guide concepts` 표현으로 중복을 피한다.
- 최대 검색결과 수는 `min(100, maximum_sources * 3)`으로 제한한다.
- metadata에 다음을 기록한다.
  - `planner=deterministic-supplemental`
  - `reason=low_source_diversity`
  - `replanning_round=1`

### Replanning Trigger

다음 조건을 모두 만족할 때만 추가 검색을 실행한다.

- Supplemental Query Planner가 주입되어 있음
- Quality-aware Document Selector가 활성화되어 있음
- `maximum_sources > 1`
- 현재 Evidence Source 수가 `min(2, maximum_sources)`보다 작음

따라서 Offline Pipeline, Selector가 없는 Pipeline, `maximum_sources=1`,
최초 검색에서 Evidence Source를 이미 두 개 이상 확보한 경우에는
Replanning을 실행하지 않는다.

### Candidate 병합 및 중복 제거

초기 후보와 Supplemental 후보는 정규화된 `source_id`와 URL을 기준으로
중복을 제거한다. URL 정규화에는 Scheme 및 Host 소문자화, 기본 Port 제거,
Fragment 제거, 불필요한 후행 Slash 정리가 포함된다.

중복 후보는 Reader로 전달하지 않는다.

### 전체 재평가

Supplemental 후보만 별도로 Evidence 추출하지 않는다.

```text
초기 읽은 문서
+
Supplemental 신규 문서
→ 전체 Source Quality Ranking
→ 전체 Evidence-aware Backfill 재실행
```

이 방식을 사용하면 보완 검색에서 발견된 더 직접적이고 높은 품질의 문서가
초기 검색 문서를 대체할 수 있다.

### 실행 한계

- Supplemental Query: 최대 1개
- 추가 검색 라운드: 최대 1회
- 총 검색 라운드: 최대 2회
- 무한 Retry 없음
- LLM 기반 Query 생성 없음
- 범용 Planning Loop 연결 없음

### Workspace Metadata

Supplemental Planner가 활성화된 Pipeline은 다음 metadata를 추가로 기록한다.

- `search_round_count`
- `replanning_triggered`
- `supplemental_query_count`
- `supplemental_candidate_count`
- `deduplicated_candidate_count`

기존 Evidence metadata도 계속 유지한다.

- `read_candidate_count`
- `evidence_attempted_document_count`
- `selected_document_count`
- `evidence_source_count`
- `backfilled_document_count`
- `no_evidence_document_count`

### Source Gate 정합성

Supplemental Search 후 최소 Evidence Source를 충족하면 기존 Quality
Evaluator가 생성한 `LOW_SOURCE_DIVERSITY` Issue를 제거한다.

동시에 Quality metadata에 다음을 기록한다.

- `minimum_evidence_sources`
- `actual_evidence_sources`
- `maximum_sources`

Source가 여전히 부족하면 `LOW_SOURCE_DIVERSITY/error`를 유지하고 최종
품질을 실패로 판정한다.

### 검증 결과

- Source 부족 시 Supplemental Search 1회 실행
- 초기 Source가 충분하면 추가 검색 없음
- 정규화 URL 중복 제거
- Supplemental Search 후 Source 확보 성공
- Supplemental Search 후에도 Evidence가 부족하면 실패 유지
- `maximum_sources=1`이면 Replanning 비활성화
- 동일 입력에서 동일 Query, Source, Evidence 순서 보장
- Live Runtime에 Supplemental Planner 주입
- 성공 후 오래된 `LOW_SOURCE_DIVERSITY` 제거

최종 전체 검증:

```text
4167 passed in 9.41s
Ruff: All checks passed
git diff --check: passed
```

### Live Research 결과

```text
search_round_count = 2
replanning_triggered = true
supplemental_query_count = 1
supplemental_candidate_count = 4
deduplicated_candidate_count = 5
read_candidate_count = 13
evidence_attempted_document_count = 5
selected_document_count = 2
evidence_source_count = 2
no_evidence_document_count = 3
report.source_count = 2
claim_count = 4
citation_count = 4
quality_score = 0.9163
minimum_evidence_sources = 2
actual_evidence_sources = 2
LOW_SOURCE_DIVERSITY = 없음
```

### 이유

AIRA는 Evidence가 부족할 때 즉시 실패하는 데서 끝나지 않고, 제한된 비용과
명확한 종료 조건 안에서 한 번 더 조사할 수 있어야 한다.

Research 전용의 결정론적 Supplemental Search는 Evidence Sufficiency 개선,
비용과 호출 횟수 제한, 무한 Loop 방지, 결정론적 테스트 가능성, Offline
Baseline 호환성, 향후 확장 가능한 명확한 경계를 제공한다.

---

## D-030 — Research Result JSON에 계산된 품질 통과 여부 저장

- 상태: 확정
- 날짜: 2026-08-07
- 적용 범위: `ResearchResultWriter`가 생성하는 `result.json`

### 문제

`ResearchQualityEvaluation.passed`는 ERROR severity의 Quality Issue 존재 여부를
기준으로 계산되는 일반 `@property`이다.

Python 코드와 Markdown Report에서는 `quality.passed`를 직접 읽으므로
정상적으로 동작하였다. 그러나 `ResearchResultWriter`는
`result.model_dump_json(indent=2)`를 저장하므로 일반 `@property`인
`passed`가 JSON에 포함되지 않았다.

그 결과 외부 프로그램은 최종 품질 통과 여부를 직접 읽지 못하고 `issues`를
다시 해석해야 했다.

### 검토 대안

- Pydantic `computed_field`: 모든 직렬화 경로와 Schema가 변경됨
- 실제 `passed: bool` 필드: `issues`와 불일치할 수 있는 중복 상태 생성
- Writer에서 명시적 추가: 외부 JSON 계약만 제한적으로 확장

### 결정

`ResearchQualityEvaluation.passed`는 계산 속성으로 유지하고,
`ResearchResultWriter`가 만드는 `result.json`에만 다음 값을 추가한다.

```python
payload = result.model_dump(mode="json")
payload["quality"]["passed"] = result.quality.passed
```

### 외부 JSON 계약

성공한 품질 결과:

```json
{
  "quality": {
    "passed": true
  }
}
```

ERROR Issue가 있는 품질 결과:

```json
{
  "quality": {
    "passed": false
  }
}
```

### 결정 이유

- 모델 내부 계산 의미 유지
- `passed`와 `issues`의 상태 불일치 방지
- 일반 `model_dump()` 결과와 Schema 변경 방지
- 기존 결정론적 비교 테스트 영향 최소화
- 외부 CLI, 평가기, 후속 Agent가 Boolean을 직접 판독 가능

### 테스트

- Quality ERROR가 없으면 JSON의 `passed`가 `true`
- Quality ERROR가 있으면 JSON의 `passed`가 `false`
- Markdown 및 기존 JSON 필드는 그대로 유지
- 동일 실행 디렉터리 덮어쓰기 방지 동작 유지

### 검증 결과

```text
Writer 테스트: 3 passed
전체 pytest: 4168 passed in 15.61s
Ruff: All checks passed
git diff --check: passed
```

---

## D-031 — Live Research Provider Call·Credit·Latency Budget

- 상태: 확정
- 날짜: 2026-08-07
- 적용 범위: Live Research Search Adapter, Supplemental Search, Workspace Metadata

### 문제

제한형 Supplemental Search는 최대 한 번만 실행되지만, 실제 Provider 호출 수,
Credit 및 누적 Latency를 하나의 Budget으로 통제하지 않았다.

검색 라운드 수만 제한하면 Query 수 증가, Provider Credit 소비,
네트워크 지연 누적을 직접 제어할 수 없다.

### 결정

`ResearchSearchBudget`과 `ResearchSearchUsage`를 도입하고
`PipelineSourceSearchAdapter`가 하나의 Research Run 동안 Search Provider
사용량을 누적한다.

```text
ResearchSearchBudget
├─ maximum_provider_calls
├─ maximum_credits
├─ maximum_latency_ms
└─ default_credit_per_call

ResearchSearchUsage
├─ provider_call_count
├─ credit_used
├─ latency_used_ms
├─ unreported_credit_call_count
└─ blocked_query_count
```

### 호출 전 검사

다음 중 하나라도 만족하면 다음 Provider 호출을 시작하지 않는다.

- 누적 호출 수가 `maximum_provider_calls` 이상
- 누적 Credit과 기본 예상 Credit의 합이 `maximum_credits` 초과
- 누적 Latency가 `maximum_latency_ms` 이상

`maximum_latency_ms`는 이미 누적된 Provider Latency를 기준으로 다음 호출을
차단한다. 미래 호출의 실제 Latency는 사전에 알 수 없으므로 단일 호출 후
누적값이 한도를 초과할 수 있다.

### 호출 후 기록

Provider Result에서 다음 값을 누적한다.

- `duration_ms`
- `metadata["usage_credits"]`

Provider가 Credit을 보고하지 않거나 유효하지 않은 값을 보고하면
`default_credit_per_call`을 사용하고
`unreported_credit_call_count`를 증가시킨다.

### Supplemental Search

초기 검색과 Supplemental Search는 동일한 Search Adapter와 Budget을 공유한다.

Evidence가 부족해 Replanning이 발동하더라도 Budget이 소진된 경우
Supplemental Provider 호출을 실행하지 않는다.

Workspace Metadata에 다음을 기록한다.

- `search_provider_call_limit`
- `search_provider_call_count`
- `search_credit_limit`
- `search_credit_used`
- `search_credit_unreported_call_count`
- `search_latency_limit_ms`
- `search_latency_used_ms`
- `search_budget_exhausted`
- `search_blocked_query_count`
- `supplemental_search_blocked_by_budget`

### Live 기본값

```text
maximum_provider_calls = 2
maximum_credits = 2.0
maximum_latency_ms = Tavily timeout_seconds × 1000 × 2
default_credit_per_call = 1.0
```

호출자가 필요하면 `build_live_research_pipeline()`에 별도 Budget을 주입할 수 있다.

### 검증

- Provider Call 수 누적
- 보고 Credit 누적
- 미보고 Credit 기본값 적용
- Call Limit 사전 차단
- Credit Limit 사전 차단
- 누적 Latency 도달 후 차단
- Budget이 없는 기존 동작 유지
- Supplemental Search Budget 차단
- Workspace Metadata 기록
- Live Runtime 기본 및 사용자 지정 Budget

최종 전체 검증:

```text
4194 passed in 15.69s
Ruff: All checks passed
git diff --check: passed
```

실제 Live 검증:

```text
search_provider_call_count = 1
search_credit_used = 1.0
search_budget_exhausted = false
supplemental_search_blocked_by_budget = false
```

### 이유

AIRA의 Search 행동은 단순한 검색 횟수가 아니라 실제 외부 자원 사용량을
기준으로 제한되어야 한다.

명시적 Budget과 Usage를 분리하면 비용 예측, 실행 중단, 관측 가능성,
결정론적 테스트 및 향후 Provider별 과금 정책 확장이 가능하다.

---

## D-032 — Provider 독립적 Research Source Type 분류

- 상태: 확정
- 날짜: 2026-08-07
- 적용 범위: Tavily Candidate 정규화, Live Source Quality Evaluation

### 문제

Tavily Search 결과는 모든 Candidate를 다음 값으로 저장하였다.

```text
source_type = OTHER
```

따라서 공식 OpenAI Agents SDK 문서인
`openai.github.io/openai-agents-python`도 일반 웹사이트와 동일하게 평가되었다.

```text
authority = 0.50
primary = 0.45
overall = 0.6625
```

Quality-aware Document Selector는 최고 점수와의 차이가 0.12를 초과한 문서를
제외하므로 해당 공식 문서가 탈락했다.

그 결과 읽기에는 성공한 문서가 여러 개 있어도 최종 Evidence Source는
하나만 남고 `LOW_SOURCE_DIVERSITY/error`가 발생했다.

### 검토 대안

- Selector의 Quality Gap 완화
- Live Quality 점수 공식 완화
- Tavily 구현에 OpenAI Host 직접 하드코딩
- Provider 독립적인 URL Source Type Classifier 도입

### 결정

Provider와 분리된 `ResearchSourceTypeClassifier`를 도입하고,
Tavily Candidate 생성 시 주입된 Classifier로 `source_type`을 결정한다.

```text
Search Provider Result
→ ResearchSourceTypeClassifier
→ ResearchSourceCandidate.source_type
→ LiveWebSourceQualityEvaluator
→ QualityAwareDocumentSelector
```

### 분류 정책

- 명시적으로 등록한 정확한 Host: `OFFICIAL_DOCUMENTATION`
- `docs.`, `developer.`, `developers.`로 시작하는 Host: `OFFICIAL_DOCUMENTATION`
- `.gov`, `.go.kr` 및 중간 `.gov.`: `GOVERNMENT`
- `.edu`, `.ac.kr` 및 중간 `.edu.`: `ACADEMIC`
- 그 외: `OTHER`

### Trusted Host 정책

Live Runtime에서는 다음 정확한 Host만 추가로 신뢰한다.

```text
openai.github.io
```

모든 `*.github.io`를 신뢰하지 않는다.

예:

```text
openai.github.io
→ OFFICIAL_DOCUMENTATION

example.github.io
→ OTHER
```

### 변경하지 않은 영역

- Selector의 `maximum_quality_gap=0.12`
- Live Source Quality 가중치
- Evidence Extractor의 Hard Filter
- Minimum Evidence Source Gate
- Tavily Provider 응답 Schema

### 검증

- 정확한 Trusted Host 분류
- 다른 GitHub Pages Host 비신뢰
- 기존 공식 문서 Host Pattern
- 정부 및 교육 Domain Pattern
- Blank Trusted Host 거부
- Tavily Candidate 생성 시 주입 Classifier 사용
- 전체 Regression Test
- 실제 Tavily Live E2E

최종 Live 결과:

```text
read_candidate_count = 6
selected_document_count = 2
evidence_source_count = 2
search_round_count = 1
replanning_triggered = false
search_provider_call_count = 1
search_credit_used = 1.0
search_budget_exhausted = false
```

선택 Source:

```text
openai.github.io
source_type = official_documentation
overall quality = 0.9225

developers.openai.com
source_type = official_documentation
overall quality = 0.9225
```

최종 품질:

```text
overall_score = 0.9345
quality_level = excellent
passed = true
source_count = 2
```

최종 전체 검증:

```text
4194 passed in 15.69s
Ruff: All checks passed
git diff --check: passed
Live E2E exit code: 0
```

### 이유

공식 Source를 정확히 분류하지 못한 상태에서 Selector 기준을 완화하면
품질 정책 전체가 약해진다.

Source Type 정규화 계층을 추가하면 Provider가 반환한 Raw Result를
AIRA Domain Model로 정확히 변환하면서 기존 Quality Gate와 Evidence Gate를
그대로 유지할 수 있다.

---

## D-033 — Semantic Citation 판정은 연속 점수가 아니라 범주형 Support Level을 사용

- 상태: 확정
- 날짜: 2026-08-07
- 적용 범위: Single-Agent Live Research Semantic Citation Verification

### 문제

초기 Semantic Citation Verifier는 LLM이 반환한 `entailment_score`를 다음
임계값으로 직접 판정에 사용하였다.

```text
>= 0.80 → VERIFIED
>= 0.50 → NEEDS_REVISION
< 0.50  → REJECTED
```

실제 OpenAI 평가에서 의미 분석 rationale는 적절했지만 연속 점수는
일관되게 보정되지 않았다.

유사한 부분 지지 사례에서도 점수가 크게 달랐으며, 더 강한 과장이 더 높은
점수를 받는 사례도 확인되었다.

### 결정

정책 결정은 연속형 점수가 아니라 다음 범주형 Semantic Support Level을
기준으로 한다.

```text
fully_supported
partially_supported
unsupported
contradicted
```

결정 매핑은 코드가 결정론적으로 수행한다.

```text
fully_supported
→ VERIFIED

partially_supported
→ NEEDS_REVISION

unsupported
→ REJECTED

contradicted
→ REJECTED
```

`entailment_score`는 제거하지 않고 진단과 Eval을 위한 보조 신호로만 유지한다.

### Support Level 의미

```text
fully_supported
Evidence가 Claim의 중요한 모든 부분을 직접 지지한다.

partially_supported
핵심 subject와 predicate는 지지되지만 qualifier, frequency,
condition, scope, quantity 또는 secondary assertion 일부가
지원되지 않거나 과장되어 있다.

unsupported
Evidence가 Claim을 입증하기에 충분하지 않지만 Claim과 직접
충돌하지는 않는다.

contradicted
Evidence가 Claim의 중요한 부분과 동시에 참일 수 없는 내용을
명시적으로 말한다.
```

특히 다음 원칙을 적용한다.

```text
missing information != contradiction
```

### 구조

```text
Claim + Evidence
      ↓
OpenAI Semantic Judge
      ↓
SemanticCitationJudgment
├─ support_level
├─ entailment_score
├─ rationale
└─ issues
      ↓
deterministic mapping
      ↓
ResearchCitationDecision
```

`ResearchCitationVerification`에는 `support_level`을 typed field로 보존한다.

기존 Multi-Agent 계약과의 호환성을 위해 해당 필드는 현재 optional이며,
Semantic Citation 경로에서는 실제 값을 기록한다.

### 검증

- SemanticCitationJudgment Structured Output
- Support Level → Decision 결정론적 매핑
- Support Level/Decision 불일치 validator
- SemanticCitationVerificationService
- SingleResearchAgentPipeline 연결
- Live Runtime composition
- result.json Support Level 저장
- Golden Dataset 및 Blind Holdout 평가

### 이유

LLM은 설명형 reasoning에는 강하지만 연속형 숫자 calibration은 흔들릴 수 있다.

정책 결정을 명시적인 의미 범주로 제한하면 판단 의미를 명확히 하고,
코드가 최종 상태 전이를 결정론적으로 통제할 수 있다.

---

## D-034 — Semantic Citation Verification은 Evaluated Capability로 인정하되 Blocking Quality Gate는 보류

- 상태: 확정
- 날짜: 2026-08-07
- 적용 범위: Live Research Citation Verification 및 Evaluation

### 평가 과정

Semantic Citation Verifier는 다음 순서로 검증하였다.

```text
Controlled examples
→ Golden Dataset v1
→ Human Label Adjudication
→ Golden Dataset v2
→ Prompt v2
→ Blind Holdout v1
→ Live Research E2E
```

### Golden Dataset v1

초기 결과:

```text
cases = 16
correct = 13
accuracy = 81.25%
```

분석 과정에서 일부 Golden Label 자체가 불명확한 것을 확인하였다.

### Golden Dataset v2

Adjudication 후 20 Case로 확장하였다.

Prompt v1 결과:

```text
correct = 17 / 20
accuracy = 85%
false_fully_supported = 0
false_rejected = 2
```

Support Level 경계 규칙을 명확히 한 Prompt v2 결과:

```text
correct = 18 / 20
accuracy = 90%
false_fully_supported = 0
false_rejected = 1
```

Golden Dataset v2는 Prompt 개선에 사용되었으므로 최종 일반화 평가셋으로
사용하지 않는다.

### Blind Holdout v1

Prompt v2를 동결하고 새로운 20 Case Blind Holdout을 최초 실행하였다.

```text
cases = 20
correct = 19
accuracy = 95%
false_fully_supported = 0
false_rejected = 1
```

클래스별 결과:

```text
fully_supported      5 / 5
partially_supported  4 / 5
unsupported          5 / 5
contradicted         5 / 5
```

유일한 실패는 다음 범위 해석 사례였다.

```text
Claim:
The service is available at all times.

Evidence:
The service is available during business hours.

expected:
partially_supported

actual:
contradicted
```

Known Failure:

```text
Positive scoped evidence를 exclusive evidence로 과도하게
해석할 가능성이 있다.

"A에서 된다"
→ "A에서만 된다"

로 잘못 읽을 수 있다.
```

### Live Research E2E

전체 Regression:

```text
4245 passed in 16.27s
Ruff: All checks passed
git diff --check: passed
```

실제 Live Research:

```text
quality = 0.9345
citation_verification_count = 6
```

저장된 `result.json`:

```text
6 / 6 support_level = fully_supported
6 / 6 decision = verified
6 / 6 entailment_score = 1.0
```

현재 Deterministic Claim Builder는 다음 구조이므로:

```text
Claim.text = Evidence.excerpt
```

이 Live 결과는 Semantic discrimination 성능이 아니라 Runtime Wiring과
artifact persistence 검증으로 해석한다.

실제 Semantic 판별 성능의 근거는 Blind Holdout 결과이다.

### Capability 상태

```text
Implemented             = yes
Unit Tested             = yes
Pipeline Integrated     = yes
Live Runtime Connected  = yes
Live Verified           = yes
Golden Evaluated        = yes
Blind Holdout Evaluated = yes
Evaluated Capability    = yes

Blocking Quality Gate   = no
```

### Quality Gate 보류 이유

현재 Blind Holdout은 20 Case의 초기 평가이다.

또한 scoped positive evidence를 exclusive evidence로 해석하는 Known Failure가
확인되었다.

따라서 현재 Semantic Citation 결과는 관측·기록·평가에는 사용하지만,
Research 실행 전체를 차단하는 Blocking Quality Gate에는 아직 연결하지 않는다.

### 이유

Semantic Judge 자체의 불확실성과 Eval 데이터의 불확실성을 분리하고,
Development Dataset과 Blind Holdout을 구분해야 LLM-as-a-Judge의 실제
일반화 성능을 측정할 수 있다.

---
## D-035 — Generative Claim Construction 및 Bounded Execution

- 상태: 확정
- 날짜: 2026-08-07

결정:

- AIRA의 Live Research에서 `Claim.text = Evidence.excerpt`인 결정론적 Baseline을 실제 생성형 Claim 경로로 확장한다.
- 첫 Generative Claim Vertical Slice는 `1 Evidence → 1 Generated Claim`로 제한한다.
- LLM은 Claim의 의미 표현과 rationale만 생성하고, Claim ID, Citation ID, Evidence ID, Source ID, Document ID, 문자 범위 및 기타 provenance는 코드가 결정한다.
- 핵심 원칙은 `Meaning by LLM; provenance by code.`로 한다.
- 생성 Claim은 최초에는 `DRAFT` 상태로 생성하며, Semantic Citation Verification 결과와 Claim 상태 정책을 임의로 결합하지 않는다.
- Claim 생성 후 기존 Semantic Citation Verification을 실행하여 생성 문장이 연결된 Evidence에 의해 실제로 뒷받침되는지 평가한다.
- Live Runtime은 `GenerativePipelineClaimBuilder`를 주입하되, `build_live_research_pipeline()`은 기존 결정론적 Claim Builder를 fallback으로 유지한다.
- Generative Claim 호출에는 기존 `ExecutionBudget`과 `BudgetUsage`를 재사용한다. 별도의 Claim 전용 Budget schema는 만들지 않는다.
- Live Claim Generation의 초기 engineering default는 최대 생성 호출 8회, 최대 기록 Token 8,000, 최대 누적 생성시간 60초로 한다.
- Attempt ceiling은 호출 전에 적용하는 hard limit으로 한다.
- Token 및 elapsed-time ceiling은 성공한 호출의 usage를 기록한 뒤 적용한다. 해당 성공 Claim은 보존하고 이후 추가 Claim 생성을 중단한다.
- Budget 소진은 전체 Research 실패가 아니라 이미 생성된 Claim으로 계속 진행하는 graceful degradation으로 처리한다.
- Semantic Citation Verification 자체의 별도 Budget, multi-evidence Claim grouping, Claim type 자동 분류 및 blocking quality gate는 후속 Work Item으로 보류한다.

실제 검증 결과:

- 실제 OpenAI 모델을 사용한 Claim 생성 smoke test에서 Evidence와 다른 paraphrased Claim이 생성되었고 의미와 modality가 유지되었다.
- Live Research에서 생성된 Claim 3개 모두 Evidence 원문과 동일하지 않았으며, Semantic Citation Verification에서 3개 모두 `fully_supported`로 판정되었다.
- Controlled Live Runtime에서 Evidence 6개와 `max_attempts=3` 조건으로 Claim 3개만 생성되어 attempt ceiling이 실제로 작동함을 확인했다.
- Controlled Live Runtime에서 Evidence 6개와 `max_recorded_tokens=1` 조건으로 첫 성공 Claim 1개를 보존한 뒤 추가 생성이 중단되어 token ceiling과 graceful degradation이 실제로 작동함을 확인했다.
- 관련 Unit Test, 전체 pytest, Ruff 및 `git diff --check`를 통과했다.
---

## D-036 — Claim Relevance Evaluation을 Groundedness와 분리된 Evaluated Capability로 운영

- 상태: 확정
- 날짜: 2026-08-08
- 적용 범위: Single-Agent Live Research의 Generated Claim 품질 평가

### 문제

Semantic Citation Verification은 다음 질문을 평가한다.

```text
Claim이 연결된 Evidence에 의해 실제로 지지되는가?
```

그러나 Citation이 완전히 지지되더라도 Claim 자체가 사용자의 Research
Question과 Objective에 답하지 않을 수 있다.

실제 Live Research에서 Generated Claim 3개가 모두 연결 Evidence에 의해
지지되었지만, Research Question인 OpenAI Agents SDK의 Tool Calling
mechanism과 관련해서는 모두 `irrelevant`로 평가되는 사례가 확인되었다.

따라서 다음 두 품질 차원을 분리해야 한다.

```text
Groundedness:
Claim ↔ Evidence

Answer Relevance:
Question + Objective ↔ Claim
```

### 결정

- Claim Relevance Evaluation을 Semantic Citation Verification과 별도의
  Evaluated Capability로 운영한다.
- 입력은 `Question + Objective + Claim`으로 제한한다.
- Evidence Support, Source Authority, 사실의 참·거짓 및 외부 지식은
  Claim Relevance 판정에 사용하지 않는다.
- 판정 범주는 다음 세 단계로 한다.

```text
directly_relevant
partially_relevant
irrelevant
```

- 연속형 `relevance_score`는 진단용 보조 신호로 유지하고,
  범주 판정 자체를 점수 임계값으로 결정하지 않는다.
- Claim Relevance는 Claim 생성 이후, 최종 Workspace/Report 합성 전에
  평가한다.
- Live Runtime은 별도의 Claim Relevance Budget을 사용한다.
- 초기 Live engineering default는 최대 8회 평가, 최대 기록 Token 8,000,
  최대 누적 평가시간 60초로 한다.
- 현재 Claim Relevance 결과는 관측, 기록, Eval 및 실패 분석에 사용하되
  Blocking Quality Gate 또는 Claim 삭제/필터링에는 연결하지 않는다.

### 평가 결과

Prompt v2.1을 Development Dataset 평가 후 동결하였다.

Development Dataset:

```text
17 / 18 correct
accuracy = 94.44%
```

동결된 Prompt v2.1로 새로운 Blind Holdout v2를 평가하였다.

```text
17 / 18 correct
accuracy = 94.44%
false_direct = 1
false_irrelevant = 0
```

유일한 실패는 schema-definition 성격의 경계 사례에서
`partially_relevant`를 `directly_relevant`로 과대평가한 사례였다.

Blind Holdout 결과를 본 뒤 동일 Holdout에 맞춰 Prompt를 다시 수정하지 않았다.

### Production Integration 검증

Claim Relevance Evaluator를 Single Research Agent Pipeline과 Live Runtime에
연결하였다.

초기 Live Regression:

```text
Question:
How does the OpenAI Agents SDK support tool calling?

Objective:
Explain the concrete mechanism by which functions or tools are made
available to an agent and used during execution.

Generated Claims = 3
Semantic Citation = 3 / 3 fully_supported
Claim Relevance = 3 / 3 irrelevant
```

이 결과로 다음 사실을 확인하였다.

```text
Grounded != Relevant
```

즉 Citation 정확성만으로 Research Answer 품질을 판단할 수 없다.

### Capability 상태

```text
Implemented             = yes
Unit Tested             = yes
Pipeline Integrated     = yes
Live Runtime Connected  = yes
Golden Evaluated        = yes
Blind Holdout Evaluated = yes
Evaluated Capability    = yes

Blocking Quality Gate   = no
Claim Filtering         = no
```

### 이유

AIRA는 근거가 있는 문장을 만드는 것뿐 아니라 실제 Research Question에
답하는 문장을 만들어야 한다.

Groundedness와 Relevance를 독립된 평가 축으로 유지하면 검색, Evidence,
Claim Generation 및 Citation 중 어느 단계에서 품질이 떨어졌는지를
정확하게 진단할 수 있다.

---

## D-037 — Semantic Evidence Relevance와 RRF Hybrid Retrieval

- 상태: 확정
- 날짜: 2026-08-08
- 적용 범위: Live Research Evidence Retrieval 및 Final Evidence Selection

### 문제

D-036의 Live Regression에서 Generated Claim은 Evidence에 의해 완전히
지지되었지만 Research Question에는 관련되지 않았다.

Failure Localization 결과:

- Search Query 자체는 적절하였다.
- 선택된 Source Document 안에는 질문에 직접 답하는 Passage가 존재하였다.
- 기존 Paragraph Evidence Extractor는 Question 중심의 lexical overlap을
  기준으로 상위 Paragraph를 선택하였다.
- Objective가 Evidence Retrieval에 충분히 반영되지 않았다.
- 결과적으로 답이 문서 안에 존재해도 일반적인 소개 Paragraph가 선택되고
  실제 mechanism Passage가 누락될 수 있었다.

따라서 실패 원인을 `Semantic Evidence Relevance Gap`으로 정의하였다.

### 아키텍처 결정

Evidence Retrieval을 다음 단계로 분리한다.

```text
Document
→ Paragraph Candidate Generation
→ Embedding Ranking
→ Lexical Ranking
→ RRF Hybrid Shortlist
→ LLM Semantic Evidence Relevance
→ Precision-first Final Evidence Selection
→ Claim Generation
```

각 단계의 책임은 다음과 같다.

```text
Paragraph Candidate Generation
= provenance와 noise filtering을 유지하며 후보를 넓게 생성

Embedding + Lexical + RRF
= answer-bearing candidate를 놓치지 않는 Recall 단계

LLM Evidence Relevance
= Question + Objective 관점의 Precision 단계

Final Evidence Selection
= 평가된 Relevant Evidence를 최종 Evidence로 승격
```

### Semantic Evidence Relevance 판정

LLM Evidence Relevance 입력은 다음으로 제한한다.

```text
Question
Objective
Evidence Excerpt
```

외부 지식, Search, Source Authority, 사실 검증 및 Evidence Support 판단은
이 Evaluator의 책임이 아니다.

판정 범주는 다음 세 단계로 한다.

```text
directly_relevant
partially_relevant
irrelevant
```

Score는 진단용으로 유지하되 범주를 Score threshold로 결정하지 않는다.

### Evaluation 결과

Golden Development Dataset v1:

```text
cases = 18
initial = 16 / 18
accuracy = 88.89%
false_direct = 2
false_irrelevant = 0
```

Input/measurement와 실제 enforcement/control을 구분하도록 Prompt를
v1.1로 개선한 뒤 Development Dataset 결과:

```text
18 / 18 correct
accuracy = 100%
```

이 100%는 Prompt 개선에 사용된 Development Dataset 결과이므로
일반화 성능으로 해석하지 않는다.

Prompt v1.1을 동결한 뒤 새로운 Blind Holdout v1을 평가하였다.

```text
cases = 18
correct = 16 / 18
accuracy = 88.89%
false_direct = 2
false_irrelevant = 0

directly_relevant  = 6 / 6
partially_relevant = 4 / 6
irrelevant         = 6 / 6
```

Blind Holdout 결과를 본 뒤 동일 Holdout에 맞춰 Prompt를 수정하지 않았다.

Semantic Evidence Relevance는 Evaluated Capability로 인정하지만
Blocking Quality Gate로 사용하지 않는다.

### Embedding-only Shortlist 실패

초기 Production Integration에서는 Embedding Semantic Shortlist의
`maximum_candidates=8`을 사용하였다.

실제 Live Failure Audit에서 Document의 68개 Paragraph Candidate 중
질문에 직접 답하는 핵심 Passage가 다음 순위에 있었다.

```text
Embedding rank 9:
built-in agent loop that invokes tools,
sends results back to the model,
and continues until a final result is produced.

Embedding rank 10:
function tools with automatic schema generation
and Pydantic-powered validation.

Embedding rank 11:
MCP server tools alongside native function tools.
```

따라서 Candidate Generation 실패가 아니라 Embedding-only Top-8의
Recall 부족임을 확인하였다.

특히 Embedding rank 10 Passage는 다음 값을 보였다.

```text
embedding_score = approximately 0.552
lexical_score   = approximately 0.726
```

즉 Embedding과 Lexical Signal이 서로 다른 강점을 가진다는 사실이
실제 문서에서 확인되었다.

### RRF Hybrid Shortlist 결정

Embedding Rank와 Lexical Rank를 Equal-weight Reciprocal Rank Fusion으로
결합한다.

초기 engineering default:

```text
rrf_k = 60
maximum_candidates = 8
weight = equal
score threshold = none
```

RRF는 두 Rank를 결합하여 Shortlist 순서를 결정한다.

기존 `semantic_score` metadata는 downstream diagnostics 호환성을 위해
Embedding cosine score를 그대로 유지한다.

실제 같은 68개 Candidate Simulation 결과:

```text
Core Passage                                      Embedding  Lexical  RRF

SDK general overview                                   1        3      1
function tools / schema / Pydantic                    10        1      5
built-in agent loop / invokes tools                    9        8      6
MCP + native function tools                           11       14     13
```

따라서 `maximum_candidates=8`을 증가시키지 않고도 핵심 Answer-bearing
Passage 두 개를 LLM Relevance Evaluator의 평가 범위 안으로 올릴 수 있었다.

### Precision-first Final Evidence Selection

Semantic Evaluation 이후 최종 Evidence Selection은 다음 정책을 사용한다.

1. `DIRECTLY_RELEVANT` 또는 `PARTIALLY_RELEVANT` Evidence가 하나 이상 있으면
   최종 Evidence는 해당 평가 완료 Evidence만 사용한다.
2. Relevant Evidence가 존재하는 경우 남은 Top-N을 `UNEVALUATED` Candidate로
   채우지 않는다.
3. Relevant Evidence가 하나도 없고 Budget exhaustion으로 일부 Candidate가
   평가되지 못한 경우에만 최고 `UNEVALUATED` Candidate 1개를 graceful
   fallback으로 허용한다.
4. 모든 Candidate가 평가되었고 모두 `IRRELEVANT`이면 `NO_EVIDENCE`로 처리한다.

이 정책은 Budget exhaustion을 의미적 `IRRELEVANT`와 동일시하지 않으면서도
평가되지 않은 CTA 또는 일반 소개문이 최종 Evidence로 승격되는 것을 방지한다.

### Live Regression 1 — Precision-first Selection

초기 수정 후 동일 Research Question Live Test:

```text
UNEVALUATED final evidence = 0
CTA final evidence = 0
Final Evidence = 3
All semantic_evaluated = true
All 3 = partially_relevant
```

Precision 문제는 개선되었지만 직접적인 function-tool mechanism Passage가
여전히 Embedding Top-8 밖에 있어 Recall 병목이 남아 있었다.

### Live Regression 2 — RRF Hybrid Retrieval

RRF Production Integration 후 동일 Research Question을 다시 실행하였다.

최종 Source:

```text
OpenAI Agents SDK official documentation
Title: Tools - OpenAI Agents SDK
```

Final Evidence:

```text
Evidence 1 = partially_relevant, score 0.55
Evidence 2 = directly_relevant,  score 0.88
Evidence 3 = partially_relevant, score 0.60

semantic_evaluated = true for all
UNEVALUATED = 0
CTA noise = 0
```

Generated Claims:

```text
Claim 1:
hosted tool search와 client-executed tool search의 사용 조건 및
standard Runner 제약

Claim 2:
ProgrammaticToolCallingTool과 agent가 expose해야 하는
programmatically callable/tool-search surface

Claim 3:
agent.as_tool을 사용하여 agent를 callable tool로 만들고
structured input/runtime options를 제공하는 mechanism
```

Semantic Citation Verification:

```text
3 / 3 decision = verified
3 / 3 support_level = fully_supported
3 / 3 entailment_score = 1.0
```

Claim Relevance Evaluation:

```text
Claim 1 = partially_relevant, score 0.50
Claim 2 = partially_relevant, score 0.60
Claim 3 = directly_relevant,  score 0.78
```

Deterministic Research Quality:

```text
overall_score = 0.8845
quality_level = high
passed = true
```

이 Quality Score는 현재 Semantic Evidence Relevance나 Claim Relevance를
Blocking Gate로 직접 사용하지 않으므로, 위 Semantic Evaluation 결과와
분리하여 해석한다.

### 최종 Regression Checkpoint

RRF Production 변경 후 관련 focused regression:

```text
26 passed
Ruff = passed
git diff --cached --check = passed
```

Step 5.12 문서 업데이트를 포함한 최종 Repository Regression:

```text
4431 passed in 16.41s
Ruff: All checks passed
git diff --cached --check: passed
```

따라서 D-036 및 D-037에 포함된 Claim Relevance, Semantic Evidence Relevance,
RRF Hybrid Retrieval 및 Precision-first Final Evidence Selection 변경은
전체 기존 Regression을 깨뜨리지 않은 상태로 확인되었다.

### Capability 상태

```text
Paragraph Candidate Exposure      = implemented
Embedding Semantic Ranking        = implemented
Lexical Ranking                   = implemented
RRF Hybrid Shortlist              = implemented
Semantic Evidence Relevance       = evaluated
Precision-first Final Selection   = implemented
Live Runtime Connected            = yes
Live Regression Verified          = yes

Blocking Quality Gate             = no
Automatic Claim Filtering         = no
```

### 이유

Embedding similarity는 문장의 의미적 유사성을 측정하지만 사용자의 질문에
직접 답하는 Passage를 항상 최상위로 정렬하지는 않는다.

Lexical Signal은 구체적인 함수명, API명, schema 및 mechanism 표현을 강하게
포착할 수 있지만 일반적으로 의미적 표현 변화에는 취약하다.

따라서 Recall 단계에서는 서로 다른 Signal을 RRF로 결합하고,
Precision 단계에서는 LLM Semantic Relevance를 사용한다.

이 구조는 특정 OpenAI Tool Calling 키워드를 Production 코드에 하드코딩하지
않으면서도 Answer-bearing Evidence의 Recall을 개선하고,
Groundedness와 Relevance를 독립적으로 평가할 수 있게 한다.


---

## D-038 — Semantic Answer Coverage 및 Coverage-guided Bounded Replanning

- 상태: 확정
- 날짜: 2026-08-08
- 적용 범위: Single-Agent Live Research의 최종 Claim Set 평가 및 제한형 보완 조사

### 문제

Claim Relevance는 개별 Claim이 Research Question과 Objective에 관련되는지를
평가하지만, 최종 Claim Set 전체가 사용자의 요구사항을 충분히 답하는지는
별도의 문제다.

다음은 서로 다른 품질 축이다.

```text
Citation Groundedness
= Claim이 Evidence에 의해 지지되는가?

Claim Relevance
= 개별 Claim이 Question/Object에 관련되는가?

Answer Coverage
= 최종 Claim Set 전체가 Question/Object의 요구사항을 충분히 다루는가?
```

### 결정

Semantic Answer Coverage를 별도의 Evaluated Capability로 도입한다.

입력:

```text
Question
Objective
Final Claim Set
```

외부 지식, 추가 Search, Evidence Support 및 사실 검증은 이 Evaluator의
책임이 아니다.

판정 범주:

```text
fully_covered
partially_covered
insufficient
```

`coverage_score`는 진단용이며 Replanning Trigger는 범주형
`coverage_level`을 기준으로 한다.

### Coverage-guided Bounded Replanning

`partially_covered` 또는 `insufficient`인 경우에만 Coverage Gap을 이용한
추가 검색을 최대 한 번 수행한다.

```text
Round 1
→ Answer Coverage
   ├─ fully_covered
   │  → 종료
   └─ partially_covered / insufficient
      → missing_aspects 기반 Coverage Query
      → 추가 Search 최대 1회
      → 신규 Document/Evidence 확인
      → 실제 신규 Evidence가 있을 때만 Claim Set 재구성
      → Citation / Relevance / Coverage 재평가
      → 무조건 종료
```

불변조건:

```text
coverage_replanning_attempt_count ∈ {0, 1}
FULLY_COVERED → retry 없음
duplicate-only → rebuild 없음
unreadable/no-evidence → 기존 결과 보존
budget exhausted → 안전 종료
Round 2 이후 추가 loop 없음
```

Search Provider Budget은 D-031의 동일 Run Budget을 공유하며
초기 Live 기본 Provider Call/Credit 상한은 Coverage Round를 포함하여
3회/3 Credit으로 확장한다.

### Live 검증

동일 Agents SDK Tool Calling 질문에서 실제 Live 실행으로 다음을 확인했다.

```text
initial coverage = partially_covered
coverage replanning = true
coverage query count = 1
new documents = 3
new evidence = 2
claims rebuilt = true
final coverage = fully_covered
provider calls = 2
```

Coverage 결과는 현재 품질 Score Blocking Gate에 직접 연결하지 않는다.

---

## D-039 — Research Run Observability는 Live Runtime opt-in 진단 계층으로 운영

- 상태: 확정
- 날짜: 2026-08-08
- 적용 범위: Single-Agent Research Pipeline 및 Live Runtime

### 문제

Live Research의 사용자 체감 실행시간이 길었지만 Search, Reading,
Evidence Retrieval, Claim Generation, Citation, Relevance, Coverage 중
어느 단계가 병목인지 정량적으로 구분할 수 없었다.

또한 Wall-clock 시간은 실행마다 달라지므로 항상 Pipeline Result에 포함하면
기존 결정론적 Regression을 깨뜨릴 수 있다.

### 결정

얇은 Pipeline 전용 `ResearchRunMetrics`를 사용한다.

관측 항목:

- 전체 실행시간
- Search Provider 호출 수
- Search Credit
- Search Latency
- Source Reading 시간
- Evidence Pipeline wall-clock
- Evidence Semantic Evaluator 호출 수·Token·시간
- Claim Generation 호출 수·Token·시간
- Semantic Citation 호출 수·Token·시간
- Claim Relevance 호출 수·Token·시간
- Answer Coverage 호출 수·Token·시간
- Coverage Round의 동일 항목

정책:

```text
Generic / deterministic pipeline
→ collect_run_metrics = false

Live Research runtime
→ collect_run_metrics = true
```

Observability는 Research 품질 판정, Replanning Trigger, Budget 의미 또는
Blocking Gate를 변경하지 않는다.

### 구현 과정에서 발견한 계측 결함

Observability 자체를 검증하면서 다음 오류를 발견하고 수정하였다.

- Citation `record_attempt()` 중복 호출로 Usage가 2배 누적됨
- Answer Coverage Service가 `_last_usage`를 기록하지만 `last_usage`를
  노출하지 않아 Metrics가 0으로 기록됨
- Evidence Semantic Reranker Usage가 Extraction metadata에 존재하지만
  Pipeline Adapter에서 합산·노출되지 않음

Citation 중복 수정 후 Stage wall-clock 합계는 전체 실행시간과 거의
일치하는 것이 확인되었다.

### 최종 Live Baseline

```text
total runtime = 591.871s
tracked LLM calls = 30
tracked tokens = 45,498
tracked LLM elapsed = 462.546s
search elapsed = 3.723s
```

결론:

```text
Search가 핵심 병목이 아니다.
Semantic Evaluation과 Coverage Round 재평가가 핵심 병목이다.
```

Embedding Provider는 현재 별도 Usage 계측이 없으므로
`tracked LLM calls`를 모든 AI API 호출 총계로 해석하지 않는다.

### 검증

```text
4468 passed in 10.19s
Ruff: All checks passed
git diff --cached --check: passed
commit: 640df8a
origin/main push: completed
```

---

## D-040 — Answer Coverage Structured Output Validation 실패는 1회 Corrective Retry로 복구

- 상태: 확정
- 날짜: 2026-08-08
- 적용 범위: OpenAI Answer Coverage Evaluator

### 문제

실제 Live 실행에서 Structured Output이 JSON 형태로는 생성되었지만
다음 교차 필드 의미 규칙을 위반하였다.

```text
coverage_level = fully_covered
missing_aspects != []
```

`AnswerCoverageJudgment`의 Pydantic validator가 이를 거부하여
`StructuredResponseValidationError`가 발생하고 전체 Live Pipeline이
중단되었다.

### 검토 대안

1. Validator를 느슨하게 한다.
2. `fully_covered`이면 코드가 `missing_aspects=[]`로 강제 정정한다.
3. 모순된 Structured Output을 실패로 간주하고 제한적으로 재요청한다.

### 결정

3번을 채택한다.

```text
Attempt 1
→ valid: 사용
→ schema validation failure:
   corrective retry 1회

Attempt 2
→ valid: 사용
→ invalid: 명시적 StructuredResponseValidationError
```

Corrective instruction은 동일한 Question, Objective, Claim Set을 사용하며
외부 지식을 추가하지 않는다.

기존 Schema validator는 유지한다.

코드는 모델의 모순된 결과를 임의로 `fully_covered`로 수정하지 않는다.

### 이유

Structured Output은 형식적 Schema를 따르더라도 필드 사이의 의미적
일관성을 항상 보장하지 않는다.

교차 필드 불변조건은 코드가 검증하고, 제한된 corrective retry로 복구하되,
반복 실패를 숨기지 않는 것이 AIRA의 검증·기록 원칙에 부합한다.

### 검증

- 첫 Validation 실패 후 두 번째 응답 성공 테스트
- 두 번째도 실패하면 명시적 오류 테스트
- Live Runtime 성공
- 전체 Regression 통과
- Corrective retry 횟수를 Usage/Observability에 반영

---

## D-041 — Single-Agent Micro-optimization 종료 기준과 Cost-effectiveness 우선 원칙

- 상태: 확정
- 날짜: 2026-08-09
- 적용 범위: AIRA 기능 최적화, 품질 개선 및 후속 Agent Architecture 실험

### 배경

Step 6.5 Observability 이후 Semantic LLM fan-out을 실제 측정하고,
Step 6.6에서 결과 재사용과 Batch Evaluation/Generation을 순차적으로
적용하였다.

Heavy-path re-baseline과 최종 Live Regression 비교:

```text
tracked LLM calls:
약 24 → 10

recorded tokens:
약 40.9K → 27,248

observed elapsed:
약 293s median → 163.709s

quality:
0.8845 유지
```

호출 수 감소는 구조적으로 확인되었으며, Token과 latency는 실행별 변동이
있으므로 동일 비율의 인과적 개선으로 일반화하지 않는다.

### 문제

추가 개선 후보는 계속 존재한다.

예:

- Coverage Replanning Query 고도화
- 추가 prompt tuning
- 세부 Cache 확대
- 10회 이하의 추가 API call reduction
- Semantic Quality Gate 조정
- 추가 Judge tuning

그러나 모든 작은 문제를 즉시 수정하면 다음 비용이 증가한다.

- 개발 시간
- 회귀 테스트 비용
- 설계 복잡성
- 관측 및 분석 시간
- 새로운 Capability 학습 지연
- 특정 benchmark에 대한 과최적화 위험

### 결정

AIRA는 기능 또는 성능을 무한히 미세조정하지 않는다.

각 주요 Work Item 또는 Stage에는 가능한 범위에서 다음을 명시한다.

```text
Goal
Acceptance Criteria
Measured Baseline
Known Limitations
Stop Rule
Reopen Conditions
```

다음 조건을 충족하면 해당 단계의 추가 미세조정을 보류할 수 있다.

1. 핵심 기능이 실제 Runtime에서 동작한다.
2. 기존 Regression을 깨뜨리지 않는다.
3. 주요 실패가 탐지·기록 가능하다.
4. 비용·호출·시간에 명시적 상한이 있다.
5. 현재 학습 또는 제품 목적에 충분한 Baseline이 확보된다.
6. 추가 개선의 예상 편익이 개발·검증 비용보다 명확히 크지 않다.

### 현재 적용

Step 6.6 이후 Single-Agent Live Research의 추가 micro-optimization은
보류한다.

현재 Baseline을 다음 목적에 사용한다.

- Multi-Agent 비교 기준
- 향후 Golden Dataset 평가 기준
- 실제 사용 Failure 재현 기준
- 향후 Provider/Model 비교 기준

Coverage Replanning이 topically related하지만 answer-bearing하지 않은
Evidence를 선택할 수 있다는 한계는 Known Limitation으로 유지한다.

이 한계는 현재 즉시 수정하지 않고 다음 조건에서 다시 연다.

- 실제 사용에서 반복적으로 나타남
- 평가 Dataset에서 의미 있는 실패율로 측정됨
- Multi-Agent 또는 다른 Architecture 비교에 영향을 줌
- 비용 대비 효과가 명확한 개선안이 확인됨

### 이유

AIRA 프로젝트의 목표는 특정 Single-Agent benchmark를 끝없이 최적화하는 것이
아니라 Agentic AI의 주요 Architecture와 Capability를 학습하고 실제 AIRA로
통합하는 것이다.

따라서 최적화의 최종 판단 기준은 절대적 완벽성이 아니라
`quality / cost / complexity / learning value`의 균형으로 한다.

---

## D-042 — 다음 학습 초점은 Multi-Agent의 필요성과 효과 검증

- 상태: 확정
- 날짜: 2026-08-09

결정:

- 현재 Single-Agent Live Research Baseline을 유지한다.
- 다음 주요 학습·설계 주제는 Multi-Agent System으로 이동한다.
- Multi-Agent는 Agent 수 증가 자체를 목표로 하지 않는다.
- 첫 질문은 구현 방법보다 `언제 Multi-Agent를 사용해야 하는가`로 한다.
- Single Agent + Tools, Agent-as-Tool, Handoff, Manager/Worker,
  Sequential Specialist, Parallel Specialist 및 Critic/Verifier 패턴을
  구분하여 학습한다.
- 구현 전 Single-Agent 대비 예상 이점과 추가 비용을 정의한다.
- 실제 채택은 동일 또는 유사한 평가 과제에서 품질, 비용, latency,
  context management, failure isolation 중 의미 있는 개선이 확인될 때만 한다.
- 구체적인 Multi-Agent 구현 Roadmap은 별도 문서화 작업에서 확정한다.

## D-043 — Qwen3.5-4B는 Bounded Small Worker로 채택하고 범용 Main Agent로 승격하지 않음

- 상태: 확정
- 날짜: 2026-08-13

결정:

- Qwen3.5-4B는 bounded small worker로 유지한다.
- Semantic Citation은 bounded first-pass verifier로 사용한다.
- Claim Relevance는 bounded classifier로 사용한다.
- Answer Coverage는 reviewer/critic으로 사용하되 authoritative final completeness
  judge로 사용하지 않는다.
- Local `fully_covered` 결과만으로 완전성을 확정하지 않는다.
- autonomous research planning, unconstrained long planning, policy-sensitive
  orchestration 및 final authoritative factual verification을 Qwen3.5-4B에 맡기지 않는다.

근거:

- Phase 5 role-specific benchmark
- Phase 7 OpenAI/local frozen comparison
- Local coverage optimistic bias 관찰

---

## D-044 — Single-Agent를 기본으로 유지하고 Multi-Agent는 Workload-dependent Escalation으로 사용

- 상태: 확정
- 날짜: 2026-08-13

결정:

```text
Single-Agent = default
Multi-Agent = workload-dependent escalation
```

Multi-Agent는 agent 수 증가 자체를 목표로 하지 않는다. 기존 deterministic
orchestrator와 bounded advisory reviewer를 재사용할 수 있으나, 동일 작업에서
품질·failure isolation·context management 또는 다른 명확한 편익이 있을 때만
승격한다.

Phase 9 frozen comparison에서 deterministic orchestration 자체의 추가 비용은 작은
fixture 기준으로 작았고, Qwen reviewer가 추가 latency의 대부분을 차지하였다.
절대 latency는 일반화하지 않는다.

---

## D-045 — Heterogeneous Hybrid Role Routing을 기본 확장 방향으로 채택

- 상태: 확정
- 날짜: 2026-08-13

AIRA는 하나의 universal LLM provider로 모든 역할을 처리하지 않는다.

현재 원칙:

- deterministic logic이 충분한 control/planning/selection은 deterministic으로 유지
- high-judgment 역할은 OpenAI/stronger model로 유지 또는 escalation
- 검증된 bounded semantic worker는 Local qwen3.5:4b 사용 가능

Phase 10 frozen comparison에서 OpenAI-heavy와 Hybrid 모두 6/6 pair가 성공했고,
Hybrid는 해당 benchmark에서 worker wall time을 약 64.2% 줄였다. 이 수치는
bounded substitution benchmark에 한정하며 live E2E 전체 latency로 일반화하지 않는다.

---

## D-046 — Source Reading만 Bounded Parallelism을 Production에 도입

- 상태: 확정
- 날짜: 2026-08-13

Phase 11 safety audit 결과:

- Source Search는 shared mutable usage/budget accounting 때문에 serial 유지
- Whole pipeline dependency chain은 serial 유지
- Multi-Agent dependency stages와 review loop는 dependency-sequential 유지
- Local qwen3.5 worker는 concurrency 1 유지
- 독립적인 I/O-bound Source Reading만 bounded parallelism을 허용

`PipelineSourceReaderAdapter`는 `maximum_concurrency`를 지원한다.

Production runtime contract:

```text
AIRA_SOURCE_READ_CONCURRENCY
live default = 2
allowed = 1..8
safe fallback = 1
aggressive benchmark option = 4
adapter-level default = 1
```

선택 이유:

- real HTTP에서 c=1 → c=2의 개선 폭이 큼
- c=2 → c=4의 추가 개선은 상대적으로 작음
- 1/2/4의 source별 성공/실패 semantics가 동일했음
- 안전한 fallback을 환경변수로 즉시 선택 가능

---

## D-047 — Phase 12 전까지 Hardware Upgrade 결론을 유보하고 실제 AIRA Workload를 기준으로 결정

- 상태: 확정
- 날짜: 2026-08-13

현재 하드웨어를 단순 사양 비교만으로 교체하지 않는다.

Phase 12에서 다음을 근거로 결정한다.

- 현재 8GB VRAM에서의 실제 worker/model 제약
- 8B/9B/20B급 후보의 품질 대비 runtime/VRAM 요구
- CPU/RAM 병목
- parallel agent requirement
- Local 확대와 OpenAI/Hybrid 유지의 비용·품질 차이

Phase 12 완료 전 특정 GPU, VRAM tier 또는 전체 platform upgrade를 확정하지 않는다.

### Deferred hardening

`PipelineSourceReaderAdapter.maximum_concurrency`의 production env 경로는 integer로
파싱되므로 현재 안전하지만, Python API 자체는 향후 모든 non-int 값(예: `1.5`)을
생성 시점에 명시적으로 거부하도록 강화할 수 있다. Phase 11 blocker는 아니다.

---

## D-048 — 현재 Hardware를 유지하고 Upgrade를 조건부 재평가로 유보

- 상태: 확정
- 날짜: 2026-08-13

결정:

```text
Current hardware
→ KEEP

GPU upgrade
→ DEFER

CPU / RAM / motherboard platform upgrade
→ NO CURRENT EVIDENCE

Qwen3.5-4B bounded local worker
→ KEEP

OpenAI + Local Hybrid architecture
→ KEEP
```

근거:

1. 현재 production-aligned Qwen3.5-4B bounded worker는 100% GPU로 실행된다.
2. Phase 12C에서 Qwen3.5-4B 세 역할 연속 workload의 VRAM peak는 4755 MiB였고,
   최소 free VRAM은 3117 MiB였다.
3. 같은 workload에서 system RAM 최소 available은 23975 MiB였으며 meaningful swap
   pressure는 관찰되지 않았다.
4. Qwen3.5-9B는 13% CPU / 87% GPU로 partial offload되었지만, 동일 role benchmark에서
   4B 대비 전반적 품질 우위를 보이지 않았고 세 역할 총 wall time은 545.39 s로
   4B의 302.21 s 대비 약 1.80배였다.
5. Ministral 3 8B는 22% CPU / 78% GPU로 partial offload되었고, 동일 benchmark에서
   4B 대비 전반적 품질 우위를 보이지 않았으며 총 wall time은 501.90 s로 약 1.66배였다.
6. Llama 3.1 8B Q4는 현재 GPU에서 100% GPU execution이 가능했으나 이는 hardware
   capacity probe였으며 production bounded-role quality 채택 근거로 사용하지 않는다.

따라서 더 큰 VRAM GPU가 larger model을 더 많이 GPU에 적재할 수 있다는 사실만으로
현재 AIRA의 품질 향상이 입증되지 않는다. 현재 workload에서 GPU, CPU, RAM 또는 전체
platform 교체 비용을 정당화할 evidence가 없다.

### Hardware 재평가 Trigger

다음 중 하나가 실제 evidence로 발생할 때 hardware 결정을 다시 연다.

- 현재 4B보다 명확한 role-specific quality 우위를 보이는 Local model이 VRAM에 의해 제한됨
- 실제 AIRA workload에서 concurrent Local worker / parallel agent 필요가 확정됨
- production context/KV-cache 사용 때문에 8 GiB VRAM pressure가 재현됨
- OpenAI/Hybrid operating cost 증가로 Local 확대의 경제성이 실질적으로 변함
- profiler가 CPU/GPU/storage를 end-to-end 병목으로 확인함

Phase 12 결과의 상세 evidence는 `local-llm/HARDWARE_UPGRADE_DECISION.md`와
`local-llm/BENCHMARK_RESULTS.md`에 기록한다.


---

## D-049 — Local Research는 deterministic 기본과 semantic 명시 모드로 운영

- 상태: 확정
- 날짜: 2026-08-14
- 적용 범위: `aira research` Local TXT/Markdown 실행 계약

### 배경

기존 `aira research`는 외부 Provider 없이 실행되는 offline deterministic 계약이며
CLI unit 및 subprocess E2E regression이 이 동작을 보호한다. Local semantic composition을
기본값으로 바꾸면 유효하지 않은 OpenAI 설정 때문에 기존 offline 사용이 실패한다.

CLI 의미는 다음과 같이 구분한다.

```text
research = 어떤 capability를 실행하는가 (Local Document Research)
mode     = Local 문서를 어떻게 분석하는가
```

### 결정

- `aira research`는 deterministic/offline 기본값을 유지한다.
- `aira research --mode deterministic`은 위 기본 명령과 동일하다.
- deterministic mode는 whole-document evidence와 deterministic claim builder를 유지할 수 있다.
- `aira research --mode semantic`은 명시적 opt-in Local Semantic Research이다.
- semantic mode는 paragraph semantic evidence와 generated claim을 사용한다.
- semantic mode 실패를 deterministic mode로 조용히 fallback하지 않는다.
- semantic Local의 embedding, evidence relevance, claim generation은 OpenAI high-judgment 역할로 유지한다.
- 기존 bounded-worker provider routing은 semantic citation, claim relevance, answer coverage에만 적용한다.
- `AIRA_RESEARCH_WORKER_PROVIDER=local`은 full-local research mode가 아니다.
- 첫 semantic Local 지원 형식은 UTF-8 TXT/Markdown (`.txt`, `.md`, `.markdown`)이다.
- PDF, scanned PDF/OCR, HWP, HWPX는 후속 Local Document Expansion 범위로 유지한다.

### 이유

- 기존 CLI와 artifact 동작의 backwards compatibility
- offline regression 계약 보존
- 기본 Local 실행에서 외부 Provider를 요구하지 않음
- Provider 사용과 실패를 silent behavior가 아니라 명시적 mode로 표현

### 역사적 결정과의 관계

과거 Local-document 경로가 whole-document evidence를 사용한다고 기록한 설명은
deterministic mode의 역사와 현재 계약으로 계속 유효하다. 다만 그 설명을 모든 Local
Research에 일반화하지 않는다. 새 semantic mode에서는 paragraph semantic evidence를
사용하며, 이 범위에서 기존 whole-document 설명을 명시적으로 한정한다.

### 검증

- deterministic CLI smoke: `report.md`, `result.json` 생성
- semantic CLI smoke: `report.md`, `result.json` 생성 및 relevant paragraph 선택
- semantic provenance: query text, local path, filename, character range 보존
- semantic integration: generated claim, citation verification, claim relevance, answer coverage
- full regression: `4643 passed`
- Ruff: `All checks passed`
- `git diff --check`: 통과

---

## D-050 — Local text-based PDF는 기존 Local Research 모드와 generic section provenance를 재사용

- 상태: 확정
- 날짜: 2026-08-14
- 적용 범위: Stage 4 Local PDF Text Vertical Slice

### 결정

- `aira research`와 `aira research --mode deterministic`은 text-based `.pdf`를 offline으로 처리한다.
- `aira research --mode semantic`도 text-based `.pdf`를 명시적 semantic 경로로 처리한다.
- PDF text extraction은 direct runtime dependency인 BSD-licensed `pypdf`를 사용한다.
- PDF는 physical page별 text를 추출하고 nonblank page를 prebuilt document section으로 보존한다.
- physical page number는 section `metadata["page_number"]`에 문자열로 기록한다.
- evidence range가 하나의 section에 완전히 포함될 때만 해당 section metadata를 evidence metadata로 병합한다.
- evidence가 여러 section/page에 걸치면 page를 추측하거나 첫 page를 선택하지 않는다.
- 기존 evidence metadata는 section metadata와 충돌할 때 우선한다.
- deterministic whole-document evidence는 여러 page를 포함할 수 있으므로 page number가 없을 수 있다.
- semantic PDF evidence와 citation은 동일한 exact character range를 유지한다.
- malformed, encrypted, no-text/image-only PDF는 명확히 실패하며 silent fallback이나 OCR을 수행하지 않는다.
- HTTP/Web PDF reading은 계속 지원하지 않는다.
- scanned PDF/OCR, HWP/HWPX 및 Integrated Web+Local RAG는 후속 범위이다.

### D-049와의 관계

D-049의 deterministic 기본, semantic opt-in, provider routing 및 no-silent-fallback 계약은
그대로 유지한다. D-049의 첫 지원 형식이 TXT/Markdown이라는 기록은 당시 vertical slice의
역사적 사실로 보존하며, D-050이 현재 Local 형식 범위를 text-based PDF까지 확장한다.

### 검증

- deterministic PDF CLI smoke: `pdf_text`, 3 page sections, exact whole-document citation
- semantic PDF CLI smoke: page 2 evidence만 선택, range `114..303`, `page_number="2"`
- semantic citation: evidence와 동일한 excerpt 및 `114..303` range
- scanned-like/no-text, encrypted, malformed PDF CLI/handler failure 검증
- targeted regression: `93 passed`
- full regression: `4678 passed`
- Ruff: `All checks passed`
- `git diff --check`: 통과


---

## D-051 — Local HWPX는 safe ZIP/XML extraction과 generic section provenance를 재사용

- 상태: 확정
- 날짜: 2026-08-14
- 적용 범위: Stage 4 Local HWPX Vertical Slice

### 결정

- HWP binary보다 ZIP/XML 기반 HWPX를 먼저 지원한다.
- XML safety를 위해 `defusedxml`을 direct runtime dependency로 사용한다.
- HWPX ZIP은 `extract()`/`extractall()` 없이 archive member를 직접 읽는다.
- absolute/traversal/duplicate member path, member count, individual size 및 total uncompressed size를 제한한다.
- `Contents/content.hpf` manifest와 spine으로 document reading order를 해석한다.
- manifest href는 package-root와 `content.hpf`-relative 후보 중 정확히 하나만 존재할 때 해석한다.
- 실제 Hancom package-root href (`Contents/section0.xml`)를 지원하고 ambiguous href는 거부한다.
- spine target XML root local-name이 `sec`인 document만 body section으로 분류한다.
- `header.xml`, `settings.xml` 및 arbitrary non-body XML은 body evidence에서 제외한다.
- paragraph text를 deterministic `"\n\n"` separator로 정규화한다.
- body provenance는 `hwpx_section_index`와 `hwpx_package_path`로 보존한다.
- blank body section은 package section count에는 남지만 nonblank `ResearchSourceDocumentSection`으로 만들지 않는다.
- Local adapter는 `.hwpx`를 `HWPX_TEXT`로 변환하며 deterministic/semantic CLI 모두 지원한다.
- 하나의 section에 완전히 포함된 evidence만 generic section metadata를 상속한다.
- HWP binary, OCR, table/image/layout-specific parsing 및 Integrated Web+Local RAG는 후속 범위이다.

### 검증

- real Hancom extractor/adapter smoke: `Contents/section0.xml`, range `0..96`, slice invariant 통과
- deterministic HWPX CLI: `hwpx_text`, evidence/citation `0..96`, section provenance 보존
- semantic HWPX CLI: section 2 evidence `114..303`, unrelated sections 제외
- semantic provenance: `hwpx_section_index="2"`, `hwpx_package_path="Contents/section1.xml"`
- generated claim 1개와 citation exact range 보존
- citation verification: verified / fully_supported, entailment/traceability/accuracy `1.0`
- malformed/no-text HWPX와 unsupported `.hwp` CLI failure 검증
- focused regression: `137 passed`
- full regression: `4722 passed`
- Ruff: `All checks passed`
- `git diff --check`: 통과

### 이전 결정과의 관계

D-049의 deterministic 기본/semantic opt-in 계약과 D-050의 generic section provenance
계약을 변경하지 않는다. D-051은 현재 Local 지원 형식을 text-bearing HWPX까지
확장하지만 HWP binary 또는 일반 ZIP/XML 문서 지원으로 범위를 넓히지 않는다.

---

## D-052 — Local 문서는 명시적 trust boundary와 실행 단위 external-send approval을 사용

- 상태: 확정
- 날짜: 2026-08-14
- 적용 범위: Stage 4 Local Document Safety Controls

### 결정

- `aira research`는 하나 이상의 repeatable `--allowed-root`를 요구한다.
- canonical allowed-root containment를 사용하고 string prefix 비교를 사용하지 않는다.
- leaf symlink를 거부하고 ancestor symlink escape는 canonical containment로 차단한다.
- raw local source 크기는 source당 32 MiB로 제한한다.
- raw file byte의 SHA-256과 size를 source/document provenance로 보존한다.
- deterministic Local Research는 external-send approval 없이 offline으로 실행한다.
- semantic Local Research는 명시적 `--approve-external-send`를 요구한다.
- 승인은 현재 실행에만 유효하며 모든 validated source의 canonical path, raw SHA-256 및 size에 묶인다.
- partial/extra/stale source approval을 허용하지 않으며 자동 재승인하거나 영구 저장하지 않는다.
- semantic document parsing 뒤 Settings/OpenAI client 및 external-provider component 구성 전에 동일한 `LocalDocumentAccessPolicy`로 source를 다시 fingerprint한다.
- path, size 또는 digest가 바뀌면 실행을 중단하고 새 승인을 요구한다.
- approval 자체를 evidence/citation metadata에 복제하지 않는다.

### 한계와 후속 범위

- 재검증은 practical approval-integrity check이며 descriptor-level TOCTOU를 해결하지 않는다.
- sensitive-content classification, redaction, persistent approval/cache는 후속 범위이다.
- research-live와 기존 OpenAI/Local bounded-worker routing은 변경하지 않는다.
- Stage 4는 계속 진행 중이다.

### 검증

- focused Local safety/approval regression: `110 passed`
- Local format/runtime regression: `48 passed`
- full regression: `4779 passed`
- deterministic real CLI smoke: approval 없이 report/result 생성
- semantic no-approval real CLI smoke: provider 실행 전 approval-required failure
- semantic approved real CLI smoke: relevant evidence `94..283`, exact citation, verified/fully_supported

---

## D-053 — Integrated Web + Local Research는 federated source core와 source-universe-aware selection을 사용

- 상태: 확정
- 날짜: 2026-08-15
- 적용 범위: Stage 4 Integrated Web + Local Federated Research Vertical Slice

### 배경

Web-only `research-live`와 Local-only `research` 경로는 이미 존재했지만, 하나의 연구
실행에서 두 source universe를 함께 조사하는 제품 경로가 필요했다. Web provider
score와 Local lexical score 및 source quality는 동일한 의미 체계가 아니므로 단순
cross-universe score 비교만으로 Local evidence를 탈락시키면 안 된다. 또한 Local
content가 external AI provider에 도달하기 전에는 D-052의 명시적 trust/approval
boundary가 유지되어야 한다.

### 결정

- normalized Web/Local candidate를 하나의 federated stream으로 결합한다.
- producer가 `research_origin=web|local`을 명시하고 reader 및 quality evaluator는 이
  origin만으로 routing한다. URL, hostname, storage mechanism으로 origin을 추론하지 않는다.
- per-query Web/Local rank를 deterministic하게 interleave하고 merged rank를 다시
  부여한다. source ID는 전체 set에서, normalized URL은 query 안에서 deduplicate한다.
- Tavily provider call/credit/latency만 search usage로 집계하고 Local in-memory retrieval은
  provider usage에 포함하지 않는다.
- 새 pipeline architecture를 만들지 않고 기존 `SingleResearchAgentPipeline`을 재사용한다.
- CLI는 `aira research-integrated`로 분리하고 `--mode`를 추가하지 않는다.
- Integrated approval purpose는 `integrated_web_local_research`로 하며
  `semantic_local_research`와 상호 대체할 수 없다.
- approval은 canonical path, raw SHA-256 및 raw size에 묶고, initial approval validation
  → `LocalDocumentAdapter.load_validated()` → same-policy fresh revalidation → approval
  revalidation을 통과한 뒤에만 Tavily/OpenAI/worker component를 구성한다.
- Integrated-only source-diversity selector는 `maximum_sources >= 2`이고 두 origin이 모두
  readable일 때 best eligible Web, best eligible Local, 기존 combined quality order 순으로
  evidence extraction 기회를 제공한다.
- 이는 citation quota가 아니다. `NO_EVIDENCE`는 기존 evidence-aware backfill로 다음
  document를 시도하며 irrelevant Local/Web source를 final report에 강제하지 않는다.
- `maximum_sources=1`은 기존 combined quality-aware order를 사용한다.
- 첫 real slice에서는 supplemental/coverage replanning을 활성화하지 않는다.
- generic persistent vector indexing, parsing/embedding cache 및 full persistent RAG는 이
  결정의 범위 밖에 둔다.

### 검증

- focused Integrated selector/runtime/pipeline regression: `78 passed`
- Step 2A focused approval/CLI/runtime regression: `164 passed`
- Ruff: `All checks passed`
- `git diff --check`: 통과
- real Tavily Web search와 OpenAI semantic component가 포함된 CLI smoke 통과
- weak Local fixture는 extraction opportunity 뒤 `NO_EVIDENCE`를 반환했고 workspace는
  attempted `3`, selected/evidence sources `2`, backfilled `1`, no-evidence `1`을 기록했다.
- strong Local fixture는 final 3 evidence source(2 Web + 1 Local), 8 claims, 8 citations,
  quality `0.97 / excellent / passed`를 생성했고 Local evidence가 final claim/citation에
  실제 포함되었다.

### 결과와 후속 범위

- AIRA는 이제 Web와 Local 자료를 하나의 실행에서 조사하는 실제 federated research
  경로를 가진다.
- 이 완료 범위는 broader RAG의 foundation이며 persistent vector RAG 완료를 의미하지 않는다.
- persistent Local index/embedding hash cache, scanned PDF/OCR, HWP binary,
  sensitive-content classification/redaction, persistent approval, descriptor-level TOCTOU
  hardening 및 later replanning은 후속 작업이다.
- semantic evidence evaluation은 real smoke에서 지배적인 latency/cost 구간이었다.
- `OPENAI_TIMEOUT_SECONDS=30`, `OPENAI_MAX_RETRIES=2`는 evidence relevance 중
  `APITimeoutError`가 발생했고, 관측상 `120`/`0` smoke는 성공했다. `120`/`0`을 permanent
  default로 확정하지 않으며 timeout/retry policy는 별도 운영 결정으로 남긴다.

---

## D-054 — Persistent Local Embedding Cache Foundation

- 상태: 확정
- 날짜: 2026-08-16
- 적용 범위: Stage 4 Local Document Expansion — Persistent Embedding Cache

### 배경과 범위

Local Semantic Research는 동일한 query와 paragraph text를 반복해서 embedding할 수 있다.
이 비용을 줄이려면 재사용 가능한 persistence가 필요하지만, embedding cache와 parsed
document cache, persistent retrieval index 및 vector database는 서로 다른 책임이다.

이번 결정은 첫 persistent layer인 Persistent Embedding Cache와 Local Semantic runtime
integration만 승인한다. 이는 full persistent RAG/vector retrieval architecture 완료가 아니다.
Parsed Document Cache는 후속 Stage 4 work item이며 Persistent VectorStore/vector database는
Stage 6으로 보류한다. SQLite, SQLAlchemy, `aiosqlite` 또는 vector database를 도입하지 않는다.

### 결정

- embedding persistence를 `LocalDocumentAdapter` 또는 `VectorStore`의 책임으로 만들지 않고
  별도의 persistent cache layer로 둔다.
- file-backed content-addressed JSON entry를 기존 AIRA persistence 관례에 맞게 사용한다.
- embedding identity는 exact UTF-8 text SHA-256, embedding model name 및 dimensions로
  구성한다. source filesystem path는 embedding identity에 포함하지 않는다.
- cache entry는 strict/versioned Pydantic schema로 검증하며 `TextEmbedding` 재구성에 필요한
  model, dimensions 및 vector를 보존한다.
- maximum entry size, duplicate JSON key rejection, POSIX/`fcntl` locking, same-directory
  temporary file, flush + file `fsync`, mode `0600`, `os.replace`, parent-directory `fsync` 및
  symlink/path safety check를 적용한다.
- malformed JSON, invalid UTF-8, unsupported version/schema, cache key/text/model/dimension
  mismatch는 stale embedding을 반환하지 않고 cache miss로 처리한다.
- genuine filesystem read/write/locking failure와 unsafe path는 명시적 cache error로 처리한다.
- `CachingEmbeddingProvider`는 기존 `EmbeddingProvider`를 decorator/composition으로 감싼다.
  기존 `OpenAIEmbeddingProvider` 동작은 변경하지 않는다.
- 한 batch의 unique miss는 가능한 한 하나의 underlying provider batch로 전달하며 duplicate
  text는 중복 provider work를 만들지 않는다. 반환 순서와 model/dimension 계약을 보존한다.

### Cache directory

```text
absolute nonblank XDG_CACHE_HOME
→ $XDG_CACHE_HOME/aira/embeddings

unset or blank XDG_CACHE_HOME
→ ~/.cache/aira/embeddings
```

- relative nonblank `XDG_CACHE_HOME`은 current working directory 기준으로 해석하지 않고
  configuration error로 거부한다.
- resolver는 `Path`만 반환하고 directory 생성은 `FileEmbeddingCache`가 담당한다.

### Local Semantic integration과 safety ordering

```text
OpenAIEmbeddingProvider
→ CachingEmbeddingProvider
→ EmbeddingSemanticEvidenceShortlister
```

- decorator를 통과하는 동일한 query 및 candidate/paragraph text에 cache를 적용한다.
- deterministic Local Research는 cache를 생성하거나 열지 않는 offline 계약을 유지한다.
- Local access validation과 external-send approval을 cache/provider composition보다 먼저
  수행한다.
- fresh source revalidation과 approval revalidation 순서를 변경하지 않는다.
- cache hit는 `LocalDocumentAccessGate` 또는 external-send approval을 우회할 권한이 없다.

### 검증

- UTF-8 corruption correction 뒤 Step 1 focused tests: `57 passed`
- Step 2 Local Semantic integration focused tests: `74 passed`
- Ruff lint: `All checks passed`
- Ruff format check: 통과
- `git diff --check`: 통과
- offline persistent-provider test: first provider는 한 batch 호출, 새 provider/cache를 사용한
  second run은 identical text에 대해 provider call `[]`
- real `aira research --mode semantic` smoke는 동일 source/question/objective로 두 번 성공했다.
  - first run: `real 1m14.286s`, embedding JSON entry 정확히 3개
  - second run: `real 1m26.481s`, 동일한 3개 entry 유지, 추가 entry 없음
  - 두 실행 모두 `report.md`와 `result.json` 생성
- wall-clock time은 cache 성공 판정 기준으로 사용하지 않는다. embedding 이외 semantic
  OpenAI worker가 두 실행 모두 계속 수행되기 때문이다.

### 한계와 후속 범위

- 현재 구현은 POSIX/`fcntl` 기반 single-host cache이다.
- descriptor-level TOCTOU hardening은 보류한다.
- cache eviction, total-directory quota 및 lifecycle/maintenance policy는 아직 없다.
- corrupt entry는 삭제/quarantine하지 않고 miss로 남는다.
- hit/miss metrics subsystem은 아직 없다.
- Parsed Document Cache는 아직 없다.
- Integrated Web + Local path는 아직 이 cache에 연결되지 않았다.
- Persistent VectorStore/vector database는 Stage 6으로 보류한다.

### 최종 판정

Persistent Embedding Cache foundation과 Local Semantic integration을 accepted/verified로
확정한다. Stage 4 전체는 계속 `IN PROGRESS`이다.


---

## D-055 — Persistent Semantic Embedding Cache는 source origin이 아니라 semantic embedding identity 경계에서 공유한다

- 상태: 확정
- 날짜: 2026-08-16
- 적용 범위: Stage 4 Local Document Expansion — Shared Persistent Semantic Embedding Cache

### 배경

D-054는 Persistent Embedding Cache foundation과 첫 Local Semantic runtime integration을
승인했다. 후속 audit에서 Integrated Research는 Web와 Local document 모두에 하나의
`SemanticResearchEvidenceExtractor`와 `EmbeddingSemanticEvidenceShortlister`를 공유한다는
사실을 확인했다. 이 경계에서 Local-only cache를 강제하려면 origin-aware extractor router
또는 semantic extractor 이중화가 필요하며, 이는 embedding 계산 identity와 무관한
retrieval origin을 잘못된 abstraction layer에 주입한다.

### 결정

- Persistent embedding cache의 scope는 source origin이 아니라 semantic embedding
  identity 경계로 정한다.
- identity는 exact UTF-8 text SHA-256, embedding model name 및 dimensions로 유지한다.
- source path, URL, `research_origin`, execution ID, Local/Web mode, provider-client identity
  및 source ID는 identity에 포함하지 않는다.
- standalone Local Semantic, Integrated Local 및 Integrated Web 사이에서 동일한
  text/model/dimensions entry 재사용을 명시적으로 허용한다.
- Integrated semantic composition은 다음과 같다.

```text
SemanticResearchEvidenceExtractor
→ EmbeddingSemanticEvidenceShortlister
→ CachingEmbeddingProvider
  → FileEmbeddingCache
  → OpenAIEmbeddingProvider
```

- cache hit는 underlying embedding provider 호출 여부만 바꾼다. Tavily search와 usage/credit
  accounting, HTTP/HTML reading, `research_origin`, federation/interleave,
  source-diversity/backfill, provenance 및 claim/citation routing은 변경하지 않는다.
- `research-integrated`는 현재 Local source와 Integrated approval을 요구한다. standalone
  Web-only execution은 기존 `research-live`를 사용한다.

### Local safety ordering

```text
approval validation
→ LocalDocumentAdapter.load_validated()
→ fresh LocalDocumentAccessGate validation
→ approval revalidation
→ _build_pipeline()
→ cache/provider construction
→ semantic extraction
```

따라서 pre-existing cache entry는 Local approval이나 raw SHA/source revalidation을 우회할
수 없다. unapproved 또는 stale Local source는 cache lookup에 도달하지 않는다.

### Persistence security와 privacy

- cache directory는 `0700`, cache JSON entry와 lock file 및 temporary entry file은
  `0600`으로 유지한다.
- 새 directory와 기존 broader-mode directory를 `0700`으로 normalize한다.
- directory `chmod` 실패는 명시적 `EmbeddingCacheError`이며 symlink rejection은 유지한다.
- payload는 version, cache key, text SHA-256, model name, dimensions 및 embedding의
  model/dimensions/vector를 저장한다.
- raw source/query text, URL, local path, source ID, `research_origin` 및 execution mode는
  저장하지 않는다.
- 다만 embedding vector는 semantic information을 인코딩하며 SHA-256은 guessed-text
  confirmation에 사용될 수 있다. shared scope에서는 Web/query embedding hash와 vector도
  저장될 수 있다.

### Failure와 availability 정책

- cache는 mandatory/fail-closed이다.
- malformed JSON, invalid UTF-8, schema/version mismatch, identity mismatch 및 oversized
  stored entry는 cache miss로 처리한다.
- unsafe symlink/path, read/write/lock failure 및 `chmod`/`fsync`/`replace` failure는
  명시적 error로 유지한다.
- generic best-effort fallback은 도입하지 않는다. 현재 `EmbeddingCacheError` taxonomy는
  recoverable I/O failure와 security-significant failure를 안전하게 구분하지 못한다.
  향후 recoverable-vs-security error taxonomy가 마련되면 safe fallback을 재검토한다.

### 검증

- focused cache/handler suite: `82 passed`
- broader Integrated regression: `151 passed`
- Ruff, format check 및 `git diff --check`: 통과
- offline에서 새 cache/provider instance persistent hit, standalone Local → Integrated,
  Integrated Web → Integrated Local 재사용을 검증했다.
- 동일 text/model/dimensions는 source universe와 execution mode에 관계없이 같은 entry를
  재사용한다.

Real Integrated smoke는 isolated directory
`/tmp/aira-integrated-cache-smoke/xdg-cache/aira/embeddings`를 사용했다. 첫 실행은 embedding
JSON entry 87개를 만든 뒤 `OpenAIEvidenceRelevanceEvaluator`의 `APITimeoutError`로
종료했다. 이는 embedding persistence 이후의 downstream timeout이며 cache failure가 아니다.
당시 `OPENAI_TIMEOUT_SECONDS`와 `OPENAI_MAX_RETRIES`는 unset이어서 repository default
30 seconds/2 retries가 적용되었다.

재시도는 smoke isolation을 위해 shell에서만 일시적으로 `OPENAI_TIMEOUT_SECONDS=120`,
`OPENAI_MAX_RETRIES=0`을 사용했고 `report.md`와 `result.json`을 생성하며 성공했다. 이는
permanent default 또는 production policy 결정이 아니다. live Web result/paragraph가 실행마다
달라질 수 있어 entry는 `87 → 121`로 증가했으며, directory는 `0700`, JSON/lock file은
`0600`을 유지했다.

### D-054와의 관계

D-054는 foundation과 첫 Local Semantic integration 결정으로 그대로 유효하다. D-055는
runtime adoption scope를 Local-only에서 Local 및 Integrated Web+Local이 공유하는 semantic
embedding identity 경계로 일반화한다.


---

## D-056 — Local-derived research result artifact는 user-selected output root와 분리된 private execution boundary에서 저장한다

- 상태: 확정
- 날짜: 2026-08-16
- 적용 범위: Stage 4 — Research Result Artifact Hardening

### 배경과 audit 결과

Harden 이전 `ResearchResultWriter`는 다음 순서로 artifact를 저장했다.

```text
output root
→ execution_dir.mkdir()
→ report.md Path.write_text()
→ result.json Path.write_text()
```

명시적 `chmod`, atomic temporary file, `os.replace`, `fsync` 및 rollback이 없었다.
process umask `0002`인 실제 Integrated smoke에서 output root와 execution directory는
`0775`, `report.md`와 `result.json`은 `0664`였다. 이는 명시적인 AIRA policy가
아니라 umask에서 우연히 파생된 mode였다.

### Data sensitivity

`report.md`에는 Local-derived evidence excerpt, Local filename/title, citation과
URL/pseudo-URL, derived claim/summary 및 quality information이 포함될 수 있다.

`result.json`은 complete `SingleResearchPipelineResult`와 `ResearchWorkspace`를
포함할 수 있어 더 민감하다. 여기에는 normalized Local document content, document
section/text, candidate snippet, Local filename, canonical `local_path`, raw source
SHA-256와 size, evidence excerpt/range, PDF/HWPX provenance, claim/citation,
question/objective, search/source/provider/evaluation metadata 및 run metrics가 포함될 수
있다. External-send approval object 자체는 serialization되지 않는다.

### 결정한 private boundary

```text
user-selected output root  → ResearchResultWriter가 mode를 변경하지 않음
new execution directory   → 0700
report.md                  → 0600
result.json                → 0600
temporary artifact files  → 0600
```

User output root는 의도적으로 shared일 수 있으므로 그대로 보존한다. 각 execution
directory를 private으로 만들면 artifact filename과 content를 보호하며, file `0600`은
surrounding root가 traversable한 경우에도 추가 방어를 제공한다.

### Execution ID 안전 계약

`execution_id`는 strip한 뒤 하나의 안전한 relative path component여야 한다. blank 또는
whitespace-only, `.`, `..`, absolute path, `/`, `\` 및 multi-component path를
거부한다. 기존 UUID-style ID는 유효하다.

### Hardened write algorithm

```text
execution ID validation
→ complete report/JSON serialization
→ output root preserve/create
→ execution directory creation (0700)
→ report temporary file preparation
  → fchmod 0600 before content write
  → write / flush / file fsync
→ result temporary file preparation (same policy)
→ final target validation
→ os.replace(report temp, report.md)
→ os.replace(result temp, result.json)
→ execution-directory fsync
```

두 temporary file을 모두 완성한 뒤에만 final artifact를 설치한다. report/result schema와
content, CLI message, provenance 및 research semantics는 변경하지 않았다.

### Failure, rollback 및 multi-file 한계

Preparation, replace 또는 final directory-`fsync` 실패 시 writer-owned temporary file과
writer가 설치한 final file을 제거한다. execution directory는 비어 있을 때만 제거하고
user-selected output root는 유지한다. Unknown content를 recursive delete하지 않으며 실패는
`ResearchResultWriteError`로 전달한다. 두 번째 replace 실패는 첫 artifact를 rollback하고,
directory `fsync` 실패는 두 final artifact를 rollback한다.

서로 다른 두 filesystem file은 일반적인 replace만으로 진정한 atomic multi-file
transaction을 제공할 수 없다. 두 `os.replace` 사이의 abrupt process/machine failure에는
artifact 하나만 관측되는 crash window가 남는다.

### Symlink와 TOCTOU

- 기존 execution directory와 execution-directory symlink는 거부한다.
- pre-existing final `report.md`/`result.json` target과 final-target symlink를 거부한다.
- focused symlink test에서 external target이 변경되지 않음을 검증했다.
- `openat()`/`O_NOFOLLOW` 같은 descriptor-level TOCTOU hardening은 구현하지 않았다.
- same-user 또는 privileged-process race는 이론적으로 남지만 새 `0700` execution
  directory가 일반적인 cross-user race exposure를 크게 줄인다.

### Security classification

Harden 전 기준으로 verified single-user Ubuntu workstation에서는
`B — hardening opportunity`였다. Multi-user/shared/server deployment에서는
`0775`/`0664` artifact를 통해 Local-derived data가 읽힐 수 있으므로 security defect가
될 수 있지만 critical vulnerability로 분류하지 않았다. D-056 이후 private-by-default
execution boundary는 구현 및 검증되었다.

### 검증

Codex implementation validation:

- ResearchResultWriter tests: `18 passed`
- affected writer/handlers/CLI suite: `98 passed`
- broader research regression: `104 passed`

Independent source re-audit:

- ResearchResultWriter tests: `18 passed`
- affected writer + Local + Integrated + Live + CLI suite: `90 passed`
- Ruff, format check 및 `git diff --check`: 통과

`98`과 `90`은 서로 다른 test-file 조합이며 모순이 아니다. Independent `90 passed`
rerun을 authoritative re-audit 결과로 사용한다.

### Real permission smoke

`/tmp/aira-result-permission-smoke`에서
`aira research --mode deterministic`를 실행해 다음을 확인했다.

- output root: `0775`, 의도대로 변경되지 않음
- execution directory: `0700`
- `report.md`: `0600`, 1099 bytes
- `result.json`: `0600`, 33474 bytes
- `source.md`: `0664`, user-created smoke input이며 writer artifact가 아님
- execution 성공 및 `result.json` parsing 성공

Parsed result의 top-level key는 `answer_coverage_evaluation`,
`citation_verifications`, `claim_relevance_evaluations`, `quality`, `report`,
`run_metrics`, `workspace`였다.

### D-055와의 관계

D-055는 persistent semantic embedding cache를 `0700`/`0600`으로 보호한다. D-056은
Local-derived workspace/evidence data가 포함될 수 있는 research result artifact라는 별도
persistence boundary를 보호한다. Cache privacy와 result artifact privacy는 서로 다른
concern이다.


---

## D-057 — Parsed Document Cache uses raw content + parser identity while filesystem/execution identity and authorization are reconstructed at runtime

- 상태: 확정
- 날짜: 2026-08-16
- 적용 범위: Stage 4 — Persistent Parsed Document Cache

### 배경

Local document를 반복 실행할 때 raw access validation과 semantic embedding 사이에서
TXT/Markdown decoding, PDF text/page extraction 및 HWPX ZIP/XML body-section parsing이
반복되었다. 이 parsing 결과를 재사용하려면 content-derived representation과 현재
filesystem/execution identity를 분리해야 한다. Path나 source ID를 cache payload에 넣으면
같은 bytes를 다른 안전한 path에서 재사용할 때 stale provenance가 발생할 수 있다.

따라서 `ParsedLocalDocument`를 path-neutral boundary로 정한다. 이 값은 normalized content,
`ResearchSourceContentType`, stable section content/range, PDF page provenance, HWPX body-section
provenance 및 format-derived metadata만 포함한다.

### Cache identity와 parser invalidation

Parsed cache identity는 canonical serialization한 다음 SHA-256으로 key를 계산하며 다음을
포함한다.

- raw document SHA-256
- raw file size
- parsed-cache schema version
- content type와 parser ID
- 명시적으로 bump 가능한 parser revision
- parser normalization/configuration identity
- output에 materially relevant한 dependency identity

현재 parser identity는 `aira-text`, `aira-markdown`, `aira-pdf-text`, `aira-hwpx-text`와
revision/configuration identity로 구분한다. PDF는 extraction output에 영향을 주는 `pypdf`
dependency identity를 포함한다. 전체 application version이나 Git commit은 사용하지 않는다.

다음 값은 identity와 persisted `ParsedLocalDocument`에서 의도적으로 제외한다.

- canonical `local_path`, filename 및 path-derived title
- source/document ID와 pseudo-URL
- request/task/query ID, candidate rank 및 input position
- `research_origin`, approval state, allowed roots 및 execution ID

같은 bytes와 같은 parser identity는 filesystem path와 무관하게 같은 entry를 사용한다.
`LocalDocumentAdapter`는 cache hit 뒤에도 현재 `LocalDocumentAccessResult`와 현재 input position을
사용해 path, filename, title, source ID, pseudo-URL, access metadata, origin 및 downstream
document identity를 매 실행마다 다시 만든다.

### Persistence와 concurrency

- Strict/frozen/versioned Pydantic envelope에 identity와 `ParsedLocalDocument`를 저장한다.
- File-backed UTF-8 JSON을 `$XDG_CACHE_HOME/aira/parsed-documents` 또는
  `~/.cache/aira/parsed-documents`에 저장한다.
- Directory는 `0700`, JSON entry, per-entry lock 및 temporary file은 `0600`이다.
- Same-directory private temporary file에 완성된 payload를 쓰고 file `fsync`, `os.replace`,
  directory `fsync` 순서로 저장한다.
- Lock은 global lock이 아니라 cache key별 POSIX `fcntl` lock이다.
- `CachingLocalDocumentParser`는 miss에서 exclusive entry lock을 획득한 뒤 cache를 다시
  확인하고 parsing과 persistence를 수행한다. 별도 process가 같은 key를 요청하면 기다린 뒤
  persisted hit를 사용하므로 same-key expensive parse를 중복하지 않는다. 서로 다른 key는
  하나의 global compute lock으로 직렬화되지 않는다.
- Locked entry handle의 unlocked `get`/`put`을 사용해 public method의 nested `flock`을
  피한다.

### Runtime safety ordering

`LocalDocumentAccessGate`와 external-send approval은 authoritative boundary이며 parsed cache는
non-authoritative optimization이다. Cache hit는 source read permission이나 external-send
permission이 아니다. Runtime ordering은 다음과 같다.

Deterministic Local:

```text
fresh LocalDocumentAccessGate validation
→ Parsed Document Cache lookup / parse
→ LocalDocumentAdapter current identity reconstruction
→ deterministic pipeline
```

Semantic Local:

```text
initial semantic approval validation
→ fresh LocalDocumentAccessGate validation
→ approval validation against fresh identity
→ Parsed Document Cache lookup / parse
→ LocalDocumentAdapter reconstruction
→ second fresh access validation
→ provider-near approval revalidation
→ embedding/provider composition
```

Integrated Local도 distinct Integrated approval purpose를 사용해 같은 Local ordering을
적용한다. Web source는 Local Parsed Document Cache를 사용하지 않는다. Integrated Web/Tavily
search, routing, accounting 및 provenance는 변경하지 않는다.

Raw source hashing은 cache hit에서도 계속 수행한다. Pre-existing entry는 missing/false,
wrong-purpose, partial/extra 또는 stale approval을 우회할 수 없다.

### Provenance와 failure 정책

- Same bytes/different path runtime test에서 parsing은 한 번만 수행했지만 두 번째 결과는 현재
  path, filename, source ID 및 pseudo-URL을 사용했다. 첫 path는 두 번째 record에 누출되지
  않았다.
- PDF cache hit는 physical `page_number`, page section ID 및 exact character slice를 유지한다.
- HWPX cache hit는 `hwpx_section_index`, `hwpx_package_path`, body-section order 및 exact slice를
  유지한다.
- Malformed JSON, invalid UTF-8, duplicate key, unsupported/schema-invalid payload, oversized stored
  entry 및 identity mismatch는 cache miss이며 parser가 재계산한다.
- Unsafe directory/entry/lock path, symlink 및 genuine stat/read/write/lock/`chmod`/`fsync`/
  `replace` failure는 명시적 `ParsedDocumentCacheError`이다.
- 성공적으로 parse했지만 serialized entry가 cache size bound를 초과한 경우에만
  `ParsedDocumentCacheEntryTooLargeError`를 잡아 valid parsed result를 uncached로 계속 사용한다.
  일반 cache error는 fallback으로 숨기지 않는다.
- Parser failure는 그대로 전달하며 final cache entry를 만들지 않는다.

### 다른 persistence layer와의 구분

```text
raw document bytes + parser identity
→ Parsed Document Cache
→ normalized evidence candidate text
→ exact text + embedding model/dimensions
→ Persistent Semantic Embedding Cache
→ retrieval/index layer (Stage 6)
```

Parsed cache는 format parsing을 피하고 embedding cache는 vector calculation을 피한다.
둘 다 어떤 document를 검색할지 결정하는 persistent VectorStore/vector database가 아니며,
persistent retrieval/index layer는 Stage 6 boundary로 유지한다.

### 검증

- Step 3 focused: `64 passed`
- Step 1–3 regression: `168 passed`
- Step 4 focused: `75 passed`
- full repository pytest: `4955 passed`
- full Ruff: 통과
- changed Python format: `14 files already formatted`
- `git diff --check`: 통과

Isolated deterministic smoke는 별도 `XDG_CACHE_HOME`을 사용했다. 첫 실행 뒤 parsed JSON
entry는 1개였고 동일 request의 두 번째 실행 뒤에도 1개였다. 두 실행 모두 report/result를
생성했다. Parsed cache directory는 `0700`, JSON과 per-entry lock은 `0600`이었다.

### 알려진 한계

- `openat()`/`O_NOFOLLOW` 기반 descriptor-level TOCTOU hardening은 아직 없다.
- POSIX/`fcntl` single-host 구현이며 portability boundary가 남는다.
- Parsed content encryption at rest는 제공하지 않는다.
- SHA-256 identity는 guessed-content confirmation에 사용될 수 있다.
- Total directory quota, eviction, lifecycle/maintenance command는 없다.
- Parser behavior가 바뀔 때 revision/config/dependency identity를 정확히 bump하는 discipline이
  필요하다.
- Whole normalized content와 section content가 JSON에서 중복되어 entry size가 커질 수 있다.
- Cache hit도 authoritative source size/SHA 검증을 위해 raw source hashing을 수행한다.

D-054와 D-055의 embedding cache foundation, D-056의 private result-artifact boundary를
변경하지 않는다. Parsed Document Cache core와 deterministic, semantic 및 Integrated Local
runtime integration을 accepted/verified로 확정하며 Stage 4 전체는 계속 `IN PROGRESS`이다.
