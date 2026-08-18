# AIRA PROJECT STATUS AND ROADMAP
## Agentic AI Lab — 전체 로드맵, 현재 진행상황, 향후 과제

- 기준일: 2026-08-18
- 프로젝트: Agentic AI Lab
- 제품명: AIRA (Agentic Intelligence Research Assistant)
- 개발 경로: `/home/moon/Project/agentic-ai-lab`
- 기본 브랜치: `main`
- 기본 개발환경: Ubuntu / Python 3.12 / `.venv`

---

# 1. 문서 목적

본 문서는 Agentic AI Lab 프로젝트의 전체 방향, 지금까지의 진행상황,
현재 AIRA의 실제 구현 수준, 남아 있는 핵심 과제 및 향후 실행 순서를
한눈에 확인하기 위한 상위 요약 문서이다.

세부 기준 문서:

- `AIRA_PROJECT_CHARTER.md`: 최상위 제품 목표와 원칙
- `MASTER.md`: 학습·개발 운영 원칙
- `ROADMAP.md`: 세부 진행 상태
- `DECISIONS.md`: 주요 설계 결정
- `LEARNING_LOG.md`: 학습과 실패 사례
- `AIRA_CURRENT_SYSTEM_GUIDE.md`: 현재 실제 기능과 사용법
- `AIRA_MULTI_AGENT_ROADMAP.md`: Multi-Agent 학습·구현 계획

본 문서는 위 문서를 대체하지 않는다.

---

# 2. 프로젝트의 최종 목표

AIRA는 단순 검색기나 요약기가 아니라, 사용자의 연구·조사 요청을 이해하고
인터넷 및 로컬 자료를 수집·검증·분석하여 근거 기반 연구 리포트를 생성하는
AI Research Agent를 목표로 한다.

최종 목표 흐름:

```text
사용자 요청 이해
→ 연구 목적과 범위 정의
→ 조사계획 수립
→ 인터넷/로컬 자료 검색
→ 자료 수집과 정규화
→ Evidence 추출
→ Source 품질 평가
→ 비교·분석
→ 부족한 정보 재검색
→ Claim 생성
→ Citation 검증
→ 위험·시사점·제안 도출
→ 최종 연구 리포트
```

장기 목표 범위:

- 인터넷 자료
- TXT / Markdown / PDF / HWP / HWPX
- 학술자료
- 공개 특허자료
- Hybrid RAG
- Memory
- Multi-Agent
- Evals
- Guardrails
- Cost / Budget
- MCP 또는 ChatGPT 연동
- Productization

---

# 3. 프로젝트 운영 원칙

기본 학습 순서:

```text
이론 설명
→ 작은 예제
→ 직접 실습
→ Codex 작업
→ 테스트
→ 실패 사례 분석
→ 평가
→ 학습 기록
```

핵심 설계 철학:

```text
작게 시작하지만 최종 목표는 축소하지 않는다.
새로 만들기 전에 기존 코드를 감사하고 재사용한다.
LLM은 의미 판단을, 코드는 실행·ID·provenance·검증을 담당한다.
비용은 사후 계산이 아니라 Agent 실행 제약으로 관리한다.
Agent 수 증가 자체를 발전으로 보지 않는다.
Multi-Agent는 Single-Agent 대비 이점이 입증될 때만 채택한다.
완벽함보다 cost-effectiveness와 Stop Rule을 우선한다.
```

---

# 4. 완료된 학습 Phase 0~13

## Phase 0 — 프로젝트 기반
- Ubuntu 개발환경
- Git / GitHub
- Python 가상환경
- 기준 문서
- Codex 기반 개발 흐름

## Phase 1 — Agentic AI 기초
- Chatbot / Workflow / Agent 차이
- Goal / State / Action / Observation
- Agent Loop
- Deterministic vs Probabilistic
- Human-in-the-loop

## Phase 2 — OpenAI API
- OpenAI Python SDK
- Responses API
- Secret
- Request / Response / Usage
- 오류 처리

## Phase 3 — Structured Outputs
- JSON Schema
- Pydantic
- Structured Outputs
- Validation
- 제한된 corrective retry

## Phase 4 — Tool Calling
- Tool 정의
- Tool Registry
- Dispatcher
- Argument validation
- Tool result 처리

## Phase 5 — Workflow / State
- 상태 모델
- 상태 전이
- 성공 / 실패 / 교정 경로
- Workflow와 Tool 통합

## Phase 6 — RAG
- Parsing
- Chunking
- Retrieval
- Evidence
- Citation 기반 응답

## Phase 7 — Memory
- Memory Schema
- 저장 / 검색 / 갱신
- Workflow State와 Memory 분리

## Phase 8 — Planning Agent
- Plan
- Task
- Dependency
- Replanning
- Stop Condition

## Phase 9 — Single Research Agent
- Research Request
- Task 분해
- Query 계획
- Source / Reader
- Evidence
- Claim / Citation
- Workspace
- Research Report

## Phase 10 — Multi-Agent Research 기초
과거 학습·구현 이력:
- Agent Role
- Capability
- Assignment
- Message
- Shared Workspace
- Delegation
- Sequential / Parallel
- Conflict Detection
- Revision

주의: 현재 Live Runtime의 기본 경로로 채택된 것은 아니다.

## Phase 11 — Evals / Guardrails / Reliability
- Eval Dataset
- Eval Runner
- Citation / Evidence / Claim 평가
- Regression
- Guardrails
- Retry / Timeout / Cancellation
- Reliability Metrics

## Phase 12 — Application / Persistence / Background Jobs
- Application Service
- Repository
- Job lifecycle
- Queue / Worker lease
- Retry scheduling
- Cancellation
- Idempotency

## Phase 13 — Practical AIRA Integration Baseline
- Offline Deterministic Research Baseline
- CLI Research
- 구조화 결과 저장
- Regression 비교 기준

---

# 5. 제품 통합 Stage 진행상황

## Stage 0 — Project Realignment
상태: 핵심 완료

- Project Charter
- 기준 문서 정렬
- 운영 원칙 정리
- Control Plane 확립

## Stage 1 — Existing Capability Audit
상태: 완료

핵심 결론:

```text
Rewrite보다 Integration-first
```

확인:
- 기존 저장소에 Agentic Capability 다수 존재
- OpenAI Planning / Structured Output 존재
- Tool / Usage / Budget / Trace 기반 존재
- 기존 `aira research`는 Offline Deterministic Baseline
- 실제 Web Search / HTTP Reader / Live Runner가 첫 핵심 gap

## Stage 2 — Target Product / Architecture
상태: 핵심 완료

확정:
- Single-Agent 우선
- Live Research Vertical Slice 우선
- OpenAI 초기 사용 가능
- Provider 독립성 유지
- Tavily 초기 Search Provider
- CLI 우선
- DB / Queue / FastAPI는 필요 시 후순위

## Stage 3 — Minimal Intelligent Single Agent
상태: 핵심 구현 및 최적화 완료

현재 가장 성숙한 실제 Runtime:

```bash
aira research-live
```

---

# 6. 현재 Single-Agent Live Research의 구현 기능

현재 실행 흐름:

```text
Research Request
→ Query Planning
→ Tavily Search
→ HTTP/HTML Reader
→ Source Quality
→ Evidence Retrieval
→ RRF Hybrid Ranking
→ Semantic Evidence Relevance
→ Evidence Selection
→ Generative Claim
→ Semantic Citation Verification
→ Claim Relevance
→ Semantic Answer Coverage
→ Bounded Coverage Replanning
→ Report / JSON
→ Observability
```

## Live Web Search
- Tavily
- Provider call / credit / latency tracking
- Supplemental Search 최대 1회
- 총 Search Round 최대 2회
- 중복 URL 제거

## Source Quality
- Authority
- Primary-source
- Recency
- Completeness
- Traceability
- Source Type classification

## Evidence-aware Selection
- NO_EVIDENCE 문서는 source quota 미소비
- Backfill
- 최소 Evidence Source Gate
- Source diversity failure 탐지

## RRF Hybrid Retrieval
- Embedding Rank
- Lexical Rank
- Reciprocal Rank Fusion
- 의미 기반 Recall 개선

## Semantic Evidence Relevance
범주:
- directly_relevant
- partially_relevant
- irrelevant

## Generative Claim
핵심 원칙:

```text
Meaning by LLM
Provenance by code
```

## Semantic Citation Verification
범주:
- fully_supported
- partially_supported
- unsupported
- contradicted

## Claim Relevance
평가:

```text
Question + Objective
↕
Claim
```

## Semantic Answer Coverage
범주:
- fully_covered
- partially_covered
- insufficient

추가 기록:
- covered_aspects
- missing_aspects
- coverage_score

## Coverage-guided Replanning
- missing aspects 확인
- Supplemental Search
- 신규 Evidence 평가
- 필요 시 Source substitution
- Coverage Level 개선 없으면 rollback

## Budget
- max attempts
- max tokens
- max elapsed
- max provider calls
- graceful degradation

## Observability
- total elapsed
- search
- reader
- evidence semantic
- claim generation
- citation
- claim relevance
- answer coverage
- coverage round
- recorded tokens
- tracked calls

---

# 7. Step 6.6 Performance Optimization 완료

Observability 이후 측정된 LLM fan-out을 최적화했다.

주요 완료 작업:

- Incremental Coverage Reuse
- Document-level Evidence Reuse
- Novel Evidence Evaluation
- Source Substitution Gate
- Batched Evidence Relevance
- Batched Claim Relevance
- Batched Citation Verification
- Batched Claim Generation

대표 heavy-path 변화:

```text
Tracked LLM Calls
약 24
→
10
```

약 58% 감소.

대표 최종 Live Run:

```text
tracked calls = 10
recorded tokens = 27,248
elapsed = 163.7s
quality = 0.8845
passed = true
```

Token / latency는 실행 변동이 있으므로 동일 비율의 인과적 절감으로 일반화하지 않는다.

---

# 8. 현재 확인된 Single-Agent 한계

## 8.1 Coverage Replanning Query 정밀도
현재 가장 명확한 Known Limitation.

```text
실패 감지
→ 가능

정확한 복구
→ 항상 보장하지 않음
```

missing aspects를 찾더라도 보완 검색이 그 aspect를 직접 해결하는 Evidence를
항상 가져오지는 못한다.

## 8.2 General Web Research의 Domain 한계
현재 `research-live`는 범용 Web Research 중심이다.

착석행동관리 관련 선행특허 질문에서 실제 특허 대신
USPTO 특허 검색 안내 페이지를 가져온 실패 사례가 있었다.

그러나 평가 계층은 실패를 정확히 감지했다.

```text
quality.passed = false
answer coverage = insufficient
coverage score = 0.05
claim relevance = 3/3 irrelevant
```

즉:

```text
Retrieval
→ 실패

Failure Detection
→ 성공
```

## 8.3 Patent Research 전문 기능 부재
현재 없는 핵심 기능:

- KIPRIS / PATENTSCOPE 특허 Search Adapter
- IPC / CPC
- Patent Family
- Priority / Filing / Publication Date
- Patent Metadata normalization
- Claim element decomposition
- Claim Chart
- Novelty analysis
- Inventive-step analysis
- Citation network
- Prior-art coverage audit

따라서 현재 AIRA는 최종 선행기술조사 도구가 아니다.

## 8.4 Local Document 통합 미완성
최종 목표 대비 아직 Live 경로에서 충분히 통합되지 않은 영역:

- PDF 고도화
- HWP
- HWPX
- Internet + Local 통합
- Patent specification comparison

## 8.5 Cost Observability의 한계
현재 recorded tokens / calls / search credits는 측정하지만,
모든 stage의 input/output/cached token과 실제 model pricing을 결합한
완전한 Cost Ledger는 후속 과제다.

---

# 9. 현재 Stop Rule

2026-08-09 기준:

```text
Single-Agent Live Research micro-optimization
→ Deferred
```

이유:
- 핵심 Runtime 동작
- 주요 Evaluation 존재
- 실패 감지 가능
- Budget 존재
- Observability 존재
- 24 → 10 calls 최적화
- Regression 안정성
- 추가 미세조정의 ROI 감소

다시 여는 조건:
- 반복되는 실제 사용자 Failure
- Eval Dataset에서 구조적 병목
- 운영 비용/latency 위반
- Multi-Agent 비교 baseline 보정 필요

---

---

# 10. 2026-08-13 Rebaseline — 최근 Architecture / Runtime 평가 완료

기존 문서에서는 현재 위치를 Multi-Agent 진입 직전으로 기록했으나,
그 이후 동일 저장소 `/home/moon/Project/agentic-ai-lab`에서
Local LLM, Multi-Agent, Hybrid Architecture, Parallelism, Hardware 평가를 추가로 수행했다.

따라서 2026-08-13 현재의 공식 기준점은 다음과 같이 갱신한다.

```text
Single-Agent Live Research Baseline
→ COMPLETE

Semantic Evaluation / Coverage Replanning
→ COMPLETE

Performance Optimization
→ COMPLETE

Local LLM Benchmark / Integration
→ COMPLETE

OpenAI vs Local Bounded-worker Evaluation
→ COMPLETE

Local Multi-Agent Minimum
→ COMPLETE

Single vs Multi-Agent Evaluation
→ COMPLETE

Heterogeneous / Hybrid Architecture
→ COMPLETE

Bounded Parallelism / Runtime Scaling
→ COMPLETE

Hardware Upgrade Decision
→ COMPLETE
```

중요:

```text
이전 문서의
"현재 다음 단계 → Multi-Agent"
는 이제 Historical Checkpoint이다.
```

Multi-Agent 자체는 더 이상 다음 학습 목표가 아니다.
현재 공식 방향은 **실제 Research Capability 확장**이다.

---

# 11. 최근 완료된 Local LLM / Multi-Agent / Hybrid Track

## 11.1 Local LLM 후보 평가

현재 설치·평가된 주요 Local LLM:

```text
qwen3.5:4b
qwen3.5:9b
ministral-3:8b
llama3.1:8b
llama3.3:latest
```

현재 AIRA의 채택 Local bounded worker:

```text
qwen3.5:4b
```

채택 이유:

- 현재 RTX 3060 Ti 8 GiB에서 100% GPU 실행
- Semantic Citation / Claim Relevance / Answer Coverage 역할에서
  현재 비교 후보 중 가장 적절한 quality / latency / safety trade-off
- 더 큰 모델을 사용한다는 이유만으로 품질이 향상되지 않음

Qwen3.5-9B:

```text
13% CPU / 87% GPU
```

- 현재 8 GiB VRAM의 경계를 확인
- Qwen3.5-4B 대비 전체 bounded-role 품질 우위를 확보하지 못함
- 세 역할 benchmark 총 wall time 약 545.39 s
- Qwen3.5-4B 약 302.21 s 대비 약 1.80배

Ministral 3 8B:

```text
22% CPU / 78% GPU
```

- 4B 대비 전체 품질 우위를 확보하지 못함
- 세 역할 benchmark 총 wall time 약 501.90 s
- 4B 대비 약 1.66배

Llama 3.1 8B:

```text
100% GPU
```

- Hardware capacity probe
- 현재 production bounded worker 채택 근거로 사용하지 않음

---

## 11.2 현재 Local bounded worker 역할

Qwen3.5-4B를 범용 Main Agent로 사용하지 않는다.

현재 채택 역할:

```text
Semantic Citation Verification
Claim Relevance
Answer Coverage Review
Constrained Structured Output
Known Single-tool / bounded semantic task
```

현재 미채택 역할:

```text
Autonomous Research Planner
Unconstrained Long Planning
Policy-sensitive Orchestration
Final Authoritative Factual Verifier
```

핵심 원칙:

```text
작은 Local model은
검증된 bounded role에만 사용한다.
```

---

## 11.3 Single vs Multi-Agent 평가 결론

현재 공식 Runtime 정책:

```text
Single-Agent
→ DEFAULT

Multi-Agent
→ WORKLOAD-DEPENDENT ESCALATION
```

Multi-Agent는 Agent 수가 많다는 이유로 채택하지 않는다.

채택 조건:

- 역할 분리로 실제 품질 개선
- Context isolation
- Failure isolation
- Specialist reuse
- Parallel latency 이점
- 추가 비용보다 개선 가치가 큼

기존 Multi-Agent 실험에서
Single-Agent baseline은 기본 Runtime으로 유지하고,
Multi-Agent는 특정 workload에서만 선택적으로 escalation하는 것이
현재 가장 합리적인 결론으로 정리되었다.

---

## 11.4 현재 Hybrid Architecture

현재 권장 구조:

```text
Deterministic Control
        +
OpenAI / Stronger-model High-judgment Path
        +
Local Qwen3.5-4B Bounded Workers
```

대표 역할 분리:

### Deterministic

- Task decomposition where rules suffice
- Query planning where deterministic logic suffices
- Source quality logic
- Document selection
- Execution / ID / provenance
- Budget / guardrail / control path

### OpenAI / stronger model

- High-judgment evidence relevance
- Claim generation
- Ambiguous or difficult semantic escalation
- Stronger-model judgment where Local bounded worker is insufficient

### Local Qwen3.5-4B

- Semantic Citation
- Claim Relevance
- Answer Coverage Review

중요:

```text
AIRA는 Universal LLM Provider 하나에 모든 역할을 강제로 연결하지 않는다.
```

---

# 12. Parallelism / Runtime Scaling 현재 결론

Phase 11 평가에서 전체 Pipeline을 무조건 병렬화하지 않았다.

현재 허용 방향:

```text
Source Reading
→ bounded parallel

기타 dependency stage
→ 기본적으로 serial
```

실측 source reading:

```text
concurrency 1
→ baseline

concurrency 2
→ 약 2.47x real-HTTP speedup

concurrency 4
→ 약 2.68x real-HTTP speedup
```

현재 production-aligned 기본값:

```text
AIRA_SOURCE_READ_CONCURRENCY=2
```

현재 Local Qwen worker concurrency:

```text
1
```

병렬화를 architecture 발전의 목표로 보지 않는다.
실제 dependency / shared state / budget safety를 먼저 유지한다.

---

# 13. Hardware Upgrade Decision — COMPLETE

현재 시스템:

```text
CPU  Intel Core i5-9600KF
RAM  약 31 GiB
GPU  NVIDIA GeForce RTX 3060 Ti 8 GiB
```

Qwen3.5-4B current-worker headroom 실측:

```text
100% GPU
VRAM peak            4755 MiB
VRAM minimum free    3117 MiB
RAM minimum available 23975 MiB
GPU temperature max  74 C
GPU power max         199.49 W
```

최종 결정:

```text
CURRENT HARDWARE
→ KEEP

GPU UPGRADE
→ DEFER

CPU / RAM / PLATFORM UPGRADE
→ NO CURRENT EVIDENCE

QWEN3.5-4B
→ KEEP

OPENAI + LOCAL HYBRID
→ KEEP
```

Hardware upgrade는 영구 배제가 아니다.

다음 evidence가 생길 때만 다시 평가한다.

- 4B보다 명확히 우수한 Local model이 VRAM 때문에 제한됨
- 실제 concurrent Local-worker requirement가 확인됨
- production context/KV-cache pressure가 재현됨
- OpenAI 비용 증가로 Local 확대의 경제성이 실질적으로 변함
- profiler가 CPU/GPU/storage 병목을 확인함

---

# 14. 현재 프로젝트의 공식 위치

2026-08-13 현재:

```text
Agentic AI 기초
→ COMPLETE

Tool / Workflow / RAG / Memory / Planning 학습
→ 핵심 완료

Single-Agent Live Research
→ Baseline 확보

Semantic Evaluation
→ 핵심 구현

Coverage Replanning
→ 구현

Performance Optimization
→ 충분한 수준까지 완료

Multi-Agent 학습 / 최소 구현 / 비교
→ 완료

Local LLM 평가 / 통합
→ 완료

Hybrid Architecture
→ 완료

Parallelism
→ bounded source reading 채택

Hardware Evaluation
→ 완료

[현재]
→ 실제 Research Capability 확장
```

현재부터의 핵심 질문은:

```text
"Agent를 어떻게 더 많이 만들 것인가?"
```

가 아니라:

```text
"AIRA가 실제로 더 어려운 Research 문제를
어떻게 더 정확하게 해결하게 만들 것인가?"
```

이다.

---

# 15. 다음 최상위 목표 — AIRA vNext

## 목표 정의

AIRA vNext의 목표:

> 인터넷 자료와 사용자 로컬 문서, 향후 전문 데이터 소스를 함께 조사하고,
> Evidence / Claim / Citation / Coverage를 통합적으로 관리하여
> 검증 가능한 전문 연구 결과를 생성하는 Evidence-Grounded Research Platform.

현재 AIRA는 Web Research 쪽 baseline이 충분히 확보되었다.

다음 우선순위는 기존 architecture를 더 복잡하게 만드는 것이 아니라
**새로운 실제 정보원을 AIRA Evidence Pipeline에 연결하는 것**이다.

---

# 16. Historical vNext Planning Proposal — Stage A~I

> **Historical note — 2026-08-18:** 이 문서의 Stage A~I는 2026-08-13 당시의
> vNext planning proposal이다. 현재 제품 Stage 번호가 아니다.
> 공식 제품 Stage는 `AIRA_PROJECT_CHARTER.md`와 `ROADMAP.md`의 숫자형
> Stage 0~11을 사용하며, 현재 위치와 다음 실행 순서는 `ROADMAP.md`가 우선한다.

## Historical Stage A — Project Rebaseline

상태:

```text
CURRENT
```

목표:

- 현재 Repository의 실제 상태와 Project 문서를 일치시킨다.
- 과거 Multi-Agent 진입 직전 상태를 Historical Checkpoint로 전환한다.
- Phase 12 COMPLETE를 기준점으로 고정한다.
- 새 개발 세션이 과거 Roadmap으로 되돌아가지 않도록 한다.

필수 확인 문서:

```text
AIRA_PROJECT_CHARTER.md
MASTER.md
ROADMAP.md
DECISIONS.md
AIRA_CURRENT_SYSTEM_GUIDE.md
AIRA_CAPABILITY_MATRIX.md
RUNTIME_ARCHITECTURE.md
local-llm/BENCHMARK_RESULTS.md
local-llm/ROADMAP.md
local-llm/HARDWARE_UPGRADE_DECISION.md
AIRA_LLM_AND_AGENT_USER_MANUAL.md
```

Rebaseline 완료 기준:

```text
현재 Runtime
현재 Architecture
현재 Local/OpenAI 역할
현재 Hardware Decision
다음 Product Capability
```

가 모든 상위 문서에서 모순 없이 정렬되어 있어야 한다.

---

## Historical Stage B — Local Document Research Vertical Slice

## 우선순위

**NEXT PRODUCT CAPABILITY**

현재 Web Research 다음으로 가장 높은 우선순위다.

목표:

```text
Local File
→ Parse
→ Normalize
→ Chunk / Position Preservation
→ Retrieval
→ Evidence
→ Claim
→ Citation
→ Coverage
→ Report
```

초기 지원 순서 권장:

```text
1. TXT / Markdown
2. PDF
3. HWPX
4. HWP
```

중요:

- 기존 RAG / Evidence / Citation contract를 최대한 재사용한다.
- 파일 형식마다 별도의 Agent를 만들지 않는다.
- 먼저 unified `Document` / `Evidence` model에 연결한다.
- 위치 provenance(page / section / line 등)를 보존한다.

완료 기준 예:

- 로컬 문서 최소 1개를 실제 읽음
- 문서 내용을 Evidence로 변환
- Claim에 Local citation 연결
- 기존 Web-only path regression 없음
- failure / unsupported format을 명시적으로 기록

---

## Historical Stage C — Internet + Local Integrated Research

Local Document vertical slice 다음 단계.

목표:

```text
Web Source
        +
Local Document
        ↓
Unified Evidence Model
        ↓
Hybrid Retrieval / Ranking
        ↓
Evidence Selection
        ↓
Claim / Citation / Coverage
        ↓
Research Report
```

핵심 과제:

- Web / Local source provenance 통일
- 중복 Evidence 제거
- source type / authority 비교
- local-only / web-only / mixed query 지원
- cache / reuse
- cross-source contradiction detection

이 Stage가 완료되면 AIRA는
단순 Web Research Agent를 넘어
사용자 자료와 외부 자료를 함께 조사하는 Research System이 된다.

---

## Historical Stage D — Patent Research Vertical Slice

AIRA의 첫 전문 Domain Vertical 후보로 강하게 유지한다.

이유:

1. 현재 범용 Web Research가 실제 Patent 질문에서 retrieval failure를 보인 적이 있다.
2. Evaluation 계층은 그 failure를 탐지하는 데 성공했다.
3. Patent domain은 metadata / claim / priority / family 등 구조화된 전문 요구가 명확하다.
4. 실제 사용자 문제로 검증하기 좋다.

목표 흐름:

```text
Patent Query
→ Patent Search Adapter
→ Patent Metadata Normalize
→ Claim Parse
→ Claim Element Decomposition
→ Evidence Mapping
→ Claim Chart
→ Novelty / Inventive-step Support Analysis
→ Citation / Source Audit
→ Prior-art Report
```

후보 데이터 소스:

- KIPRIS
- WIPO PATENTSCOPE
- Google Patents
- USPTO 공개자료
- EPO 공개자료

주의:

```text
특허 법률 판단을 LLM 단독으로 확정하지 않는다.
```

AIRA의 역할은
검색 / 구조화 / 비교 / 근거 추적 / 분석 지원이며,
법적 최종 판단과 전문 자문은 별도다.

---

## Historical Stage E — Advanced Cross-Source Verification

Internet + Local + Patent 등 여러 source가 결합되면
다음 검증 기능을 강화한다.

- Supporting Evidence
- Contradicting Evidence
- Conflicting Source Detection
- Claim-level Confidence
- Source agreement / disagreement
- Recommendation grounding
- Abstention

핵심 목표:

```text
"답을 생성한다"
보다
"왜 이 답을 믿을 수 있는가를 추적할 수 있다"
```

---

## Historical Stage F — Memory / Research Reuse

현재 Memory 학습·기반은 존재하지만
Live Research Product에 충분히 연결되어 있지 않다.

우선 적용 대상:

- 이전 Search 결과 재사용
- Source metadata cache
- Parsing cache
- Embedding cache
- Research artifact reuse
- Project-specific knowledge

Memory는 LLM의 자유로운 장기 기억이 아니라
**명시적 provenance와 lifecycle을 가진 Research Memory**로 유지한다.

---

## Historical Stage G — Cost Ledger / Provider Routing

현재:

- provider calls
- token 일부
- search credits
- latency

를 추적한다.

향후:

```text
input tokens
output tokens
cached tokens
actual model price
provider cost
search provider credit
local runtime cost proxy
```

를 결합한 Cost Ledger를 만든다.

이후에야 다음 Provider Routing을 더 정교하게 평가한다.

```text
Deterministic
vs
Local
vs
OpenAI
vs
other provider
```

비용 절감을 위해 품질을 무조건 Local로 이전하지 않는다.

---

## Historical Stage H — Skills / MCP / ChatGPT Integration

Core Research Capability가 충분히 안정된 뒤 진행한다.

후보 Skill:

- General Web Research
- Official Source Research
- Local Document Analysis
- Patent Prior-art Research
- Academic Research
- Cross-source Verification
- Project Document Audit

MCP / ChatGPT integration의 목표는
새로운 architecture를 만드는 것이 아니라
**AIRA Capability를 외부 interface에서 재사용하는 것**이다.

---

## Historical Stage I — Productization

필요성이 실제로 확인될 때 진행한다.

후보:

- CLI UX 개선
- Config system
- SQLite / persistence 강화
- FastAPI
- Background Jobs
- Docker runtime
- MCP
- ChatGPT integration
- Web UI
- 배포

현재도 다음은 선행 구현하지 않는다.

- Kubernetes
- 대규모 distributed worker
- 복잡한 RBAC
- 과도한 observability platform
- 상용 UI 우선 개발

---

# 25. Multi-Agent의 향후 위치

Multi-Agent는 별도 "다음 Phase"가 아니다.

앞으로 다음과 같이 사용한다.

```text
Single-Agent
→ DEFAULT

Multi-Agent
→ 필요성이 입증된 Stage 안에서 선택적 사용
```

예:

Patent Research에서 실제로:

```text
General Research Coordinator
Patent Search Specialist
Claim Analysis Specialist
Verifier
```

가 Single-Agent보다 품질 / failure isolation / context stability에서
의미 있게 우수하면 그때 채택한다.

즉:

```text
Problem
→ 요구사항
→ Single-Agent baseline
→ Multi-Agent experiment
→ Eval
→ 채택 또는 보류
```

순서를 유지한다.

---

# 26. Codex 운영 정책 — Usage 절약 우선

2026-08-13 현재 Codex를 다시 사용할 수 있다.

그러나 Codex Usage Limit을 중요한 개발 자원으로 취급한다.

기본 원칙:

```text
ChatGPT
→ Architect / Analyst / Reviewer

사용자 Terminal
→ Inspection / Test / Git / Simple Execution

Codex
→ Targeted Implementation Worker
```

---

## 26.1 ChatGPT 담당

- Architecture 설계
- Existing code audit 계획
- 변경 범위 결정
- interface / contract 설계
- experiment 설계
- benchmark 분석
- test strategy
- Codex prompt 작성
- 오류 로그 분석
- documentation
- 다음 단계 결정

---

## 26.2 사용자가 직접 Terminal에서 수행

- `git status`
- `git diff`
- `grep`
- `find`
- `sed`
- `cat`
- `pytest`
- `ruff`
- `ollama`
- smoke execution
- 결과 업로드

단순 조회를 위해 Codex를 사용하지 않는다.

---

## 26.3 Codex 사용 대상

Codex는 다음 경우에 우선 사용한다.

- 여러 파일을 동시에 수정해야 하는 구현
- 기존 contract를 따라가는 adapter 추가
- 신규 Vertical Slice 구현
- 복잡한 refactor
- 테스트 + 구현을 함께 수행하는 변경
- async / concurrency 문제
- repo-wide dependency를 실제 코드 수준에서 수정해야 하는 작업

---

## 26.4 Codex 사용 Level

```text
LEVEL 0
Codex 사용 안 함
→ 설계 / 문서 / inspection / 단순 command

LEVEL 1
작은 targeted patch
→ 파일 1~2개와 acceptance criteria를 미리 지정

LEVEL 2
중간 규모 feature
→ interface / test / implementation 범위를 ChatGPT가 먼저 확정

LEVEL 3
큰 repo-wide 작업
→ 정말 필요한 경우만
```

기본 운영:

```text
LEVEL 0 ~ LEVEL 1
```

---

## 26.5 Codex Usage 절감 방법

나쁜 요청:

```text
"Repository 전체를 분석해서
Local Document Research를 알아서 구현해줘."
```

이 방식은 Codex가 많은 Context와 Usage를 탐색에 소비한다.

권장 방식:

```text
ChatGPT가 먼저

1. 관련 파일 식별
2. 현재 contract 확인
3. 변경 boundary 정의
4. acceptance criteria 정의
5. 테스트 명령 정의

후

Codex에게 정확한 구현 범위만 전달
```

Codex Prompt 기본 형식:

```text
Repository:
...

Goal:
...

Inspect first:
...

Modify only:
...

Existing contracts to reuse:
...

Do not change:
...

Acceptance criteria:
...

Tests:
...

Return:
- changed files
- rationale
- test results
- remaining risks
```

---

# 27. Codex Reserve를 남겨야 하는 상황

Codex Usage는 다음 상황을 위해 남겨둔다.

- 복잡한 regression
- 많은 테스트의 동시 failure
- production bug
- difficult async/concurrency issue
- schema migration
- 대규모 refactor
- merge conflict
- 여러 subsystem을 함께 수정해야 하는 기능

단순 문서 변경이나 한 줄 수정에는 Codex를 사용하지 않는다.

---

# 28. 프로젝트 운영 방식

권장 ChatGPT 운영:

```text
ChatGPT Project
→ Agentic AI Lab 유지

기존 긴 대화
→ Historical Context

현재 Local/Hybrid/Hardware 대화
→ 완료된 Development Epoch

새 대화
→ AIRA vNext Development
```

즉:

```text
Project는 유지
Conversation은 새로 시작
Repository는 동일하게 유지
```

한다.

새 프로젝트를 만들지 않는다.

새 프로젝트는 향후 AIRA와 완전히 다른 제품이 분리될 때만 고려한다.

---

# 29. 다음 새 대화의 시작점

새 대화는 과거의:

```text
MA-0
Agent vs Tool vs Workflow vs Multi-Agent
```

부터 시작하지 않는다.

현재 시작점:

```text
Project Rebaseline
→ Local Document Research Vertical Slice
```

이다.

새 대화 첫 목표:

1. 현재 repository 상태 확인
2. 현재 architecture / docs consistency 확인
3. Local Document 기능의 기존 capability audit
4. 새로 만들지 않고 재사용 가능한 parser / RAG / evidence 기능 확인
5. 최소 Local Document Vertical Slice 설계
6. 필요한 경우에만 Codex targeted implementation

---

# 30. 새 대화 첫 Prompt 권장안

```text
본 프로젝트는 기존 Agentic AI Lab / AIRA 프로젝트의 연속 작업이다.

Repository:
  /home/moon/Project/agentic-ai-lab

중요:
이 프로젝트는 Multi-Agent 시작 단계가 아니다.
Single-Agent Live Research, Multi-Agent 비교, Local LLM,
OpenAI+Local Hybrid Architecture, bounded parallelism,
hardware evaluation까지 완료되었다.

현재 기본 결정:
- Single-Agent default
- Multi-Agent는 workload-dependent escalation
- Local bounded worker = qwen3.5:4b
- high-judgment path = OpenAI / stronger model
- Hybrid architecture 유지
- source reading concurrency default = 2
- current hardware 유지
- hardware upgrade deferred

이제 목표는 Agent architecture를 더 복잡하게 만드는 것이 아니라
AIRA의 실제 Research Capability를 확장하는 것이다.

다음 공식 개발 목표:
Local Document Research Vertical Slice

작업 원칙:
1. 추측하지 않는다.
2. 기존 코드를 먼저 감사하고 재사용한다.
3. 실제 코드 / schema / test / 실행 결과를 확인한 뒤 변경한다.
4. Codex는 Usage를 절약하기 위해 targeted implementation에만 사용한다.
5. ChatGPT는 architecture / audit / experiment / test strategy를 우선 담당한다.
6. 큰 구현 전에 변경 파일과 acceptance criteria를 먼저 확정한다.
7. commit/push 전에 targeted test → Ruff → full pytest → git diff --check를 통과한다.

먼저 코드를 작성하지 말고,
현재 repository에서 Local Document / RAG / Parsing / Evidence 관련
기존 capability를 감사하기 위한 정확한 inspection 명령부터 제시해라.
```

---

# 31. 향후 권장 실행 순서

```text
[CURRENT]

1. Project Rebaseline
2. Local Document Capability Audit
3. Local Document Research Vertical Slice
4. Internet + Local Integrated Research
5. Patent Research Vertical Slice
6. Advanced Cross-source Verification
7. Research Memory / Reuse
8. Cost Ledger / Provider Routing
9. Skills / MCP / ChatGPT Integration
10. Productization
```

Multi-Agent는 위 Stage 내부에서
실제 필요성이 증명될 때만 다시 연다.

---

# 32. 현재 의도적으로 하지 않는 것

- 새 Project 생성
- Multi-Agent architecture 확장 자체를 목표로 삼기
- Agent 수 늘리기
- 더 큰 Local LLM을 이유 없이 기본값으로 변경
- GPU / CPU / RAM 선제 업그레이드
- 모든 workload 병렬화
- PostgreSQL / Redis / RabbitMQ / Kubernetes 선행 도입
- Web UI 우선 개발
- 범용 autonomous organization 구현
- Codex에 repository 전체 탐색을 반복적으로 맡기기

---

# 33. 현재 프로젝트의 핵심 위험

## 33.1 Architecture 자체가 목적이 되는 것

현재는 충분한 Agent architecture 기반이 있다.

앞으로 성공 기준은:

```text
Agent 수
Architecture complexity
Framework 수
```

가 아니라:

```text
Research Quality
Evidence Coverage
Citation Accuracy
Failure Detection
Domain Capability
Latency
Cost
Reproducibility
```

이다.

---

## 33.2 Benchmark 과적합

Qwen3.5-4B 채택 결과를 포함하여
하나의 fixture에 반복 최적화하지 않는다.

새 capability마다:

- DEV
- HOLDOUT
- real-world failure cases

를 분리한다.

---

## 33.3 Domain specialization 없는 범용 Web 검색

Patent / Academic / Legal 등은
전문 Search Adapter 없이 일반 Web Search만으로 충분하지 않을 수 있다.

General Research와 Domain Research를 구분한다.

---

## 33.4 Semantic Judge 과신

Evaluator는 판단 도구이지 절대적 Truth source가 아니다.

계속:

- deterministic checks
- holdout
- regression
- human review

와 함께 사용한다.

---

## 33.5 Implemented와 Runtime-ready 혼동

항상 다음을 구분한다.

```text
Implemented
Tested
Runtime-connected
Live-verified
Production-ready
```

---

# 34. 2026-08-13 최상위 판단

```text
Agentic AI 핵심 학습
→ 상당 부분 완료

Single-Agent Live Research
→ 강한 Baseline 확보

Evaluation / Replanning / Budget / Observability
→ 핵심 기능 구현

Performance Optimization
→ 충분한 수준까지 완료

Multi-Agent
→ 학습 / 최소 구현 / 비교 완료
→ 기본 Runtime이 아니라 선택적 escalation

Local LLM
→ qwen3.5:4b bounded worker 채택

Hybrid Architecture
→ 확정

Parallelism
→ bounded source reading만 채택

Hardware
→ 현재 시스템 유지
→ upgrade deferred

현재 핵심 목표
→ Research Capability Expansion
```

---

# 35. 다음 즉시 실행 과제

현재 문서 갱신 후:

```text
1. 이 문서를 기존 Agentic AI Lab Project에 반영
2. 현재 긴 채팅은 완료된 Development Epoch로 종료
3. Agentic AI Lab Project에서 새 Conversation 시작
4. 새 대화 첫 Prompt 사용
5. Repository current baseline 확인
6. Local Document Capability Audit 시작
```

---

# 36. 한 줄 요약

현재 AIRA는:

> 실제 Web Research, Evidence/Claim/Citation/Coverage 평가,
> bounded replanning, Local LLM, Multi-Agent 비교,
> OpenAI+Local Hybrid, bounded parallelism 및 hardware 평가까지 완료했으며,
> 이제 Agent architecture 확장 자체가 아니라
> **Local Document와 Integrated Web + Local vertical slice를 완료했고, 이제 persistent Local Index / Embedding Hash Cache를 다음 우선순위로 진행한다.**

---

# 37. Historical Snapshot — 2026-08-16 Stage 4 Local Document Expansion baseline 완료

> 이 섹션은 Stage 4 closure 당시의 historical snapshot이다.
> Stage 4 결과 자체는 유효하지만 현재 제품 위치와 다음 실행 순서는 #39와 `ROADMAP.md`를 우선한다.

```text
Stage 4 Local Document Expansion baseline         COMPLETE
TXT / Markdown Local Research                     COMPLETE
Text-based PDF vertical slice                     COMPLETE
Text-bearing HWPX vertical slice                  COMPLETE
Local provenance and safety gates                 COMPLETE
Semantic external-send approval                   COMPLETE
Integrated Web + Local federated research         COMPLETE
Persistent Embedding Cache                        COMPLETE
Parsed Document Cache runtime integration         COMPLETE
Research Result Artifact Hardening                COMPLETE
Persistent Cache Lifecycle / Manual Maintenance   COMPLETE
```

Accepted Local format baseline:

- UTF-8 TXT
- Markdown (`.md`, `.markdown`)
- text-based PDF
- text-bearing HWPX

Unsupported but explicitly handled:

- scanned/image-only PDF → clear no-extractable-text failure
- HWP binary → unsupported
- DOCX → unsupported

Unsupported는 broken을 의미하지 않는다. Stage 4 goal인 safe Local reading, provenance
preservation 및 Web integration은 위 baseline으로 구현·검증되었다. Baseline completion은 모든
future Local format이나 hostile multi-user production hardening 완료를 뜻하지 않는다.

Follow-up classification (Stage 4 completion blocker가 아님):

SHOULD NOW:

- HWP binary support
- table-specialized parsing
- descriptor-bound source reading / TOCTOU hardening

DEFER:

- scanned PDF / OCR
- Markdown heading/section provenance
- sensitive-content classification/redaction
- persistent approval lifecycle

OUT OF SCOPE FOR STAGE 4:

- DOCX
- line-number provenance
- persistent vector retrieval/index
- Hybrid Retrieval
- Stage 5 general Web/patent expansion
- automatic cache TTL/LRU pruning
- advanced autonomous agent loop

Persistent retrieval/index와 Hybrid Retrieval은 Stage 6 boundary다. General Web/patent expansion은
Stage 5 boundary이며 Stage 4 closure는 Stage 5 또는 Stage 6 완료를 의미하지 않는다.

Latest accepted validation:

- full repository pytest: `5028 passed`
- Ruff: PASS
- `git diff --check`: PASS
- cache lifecycle isolated smoke: PASS
- cache repopulation smoke: PASS
- Stage 4 Local/Integrated real smokes: PASS

현재 다음 project step:

```text
Patent Research Vertical Slice
```

Real patent inputs가 OCR, HWP, table identity, hostile/shared filesystem 또는 강화된 privacy
workflow의 필요성을 입증하면 해당 follow-up을 다시 연다.

# 38. Historical Snapshot — 2026-08-18 Patent Planning-to-Execution live validation 완료

> 이 섹션은 Step 3C 시점의 historical snapshot이다. 현재 상태는 #39와 `ROADMAP.md`를 우선한다.

```text
Stage 4 Local Document Expansion baseline → COMPLETE
Stage 5 Internet Research Expansion        → IN PROGRESS
Patent Research Vertical Slice             → Step 3C COMPLETE
EPO provider foundation                    → COMPLETE
PatentResearchHandler                      → IMPLEMENTED / FINAL PASS
PatentSearchQueryPlan                      → IMPLEMENTED / FINAL PASS
Grounded technical concept planning        → IMPLEMENTED / FINAL PASS
Deterministic EPO CQL planning             → IMPLEMENTED / FINAL PASS
Patent planning → Handler/runtime           → IMPLEMENTED / FINAL PASS
Patent CLI/runtime                         → NOT YET IMPLEMENTED
Technical-relevance synthesis              → NOT YET IMPLEMENTED
```

Patent/EPO 단계:

```text
Step 1   FINAL PASS
Step 2A  FINAL PASS
Step 2B  FINAL PASS
Step 2C  FINAL PASS
Step 2D  FINAL PASS
```

실제 provider chain은 `OAuth → bounded CQL → /search/biblio → DOCDB identity → abstract → exact identity match → VERIFIED PatentSourceMetadata`까지 live-validated 되었다.

Provider 정책:

```text
EPO OPS = first structured patent provider
Tavily = supplementary Web context/discovery
KIPRIS Plus = Korean-specialized second-provider candidate
USPTO ODP = deferred
WIPO HTML = no first-slice parser
```

첫 slice의 법적 경계는 bounded prior-art technical relevance다. Novelty/invalidity/obviousness/infringement/FTO/legal-status definitive conclusion은 아직 구현 범위가 아니다.

Step 3A Handler는 explicit CQL을 받아 exact request-bound EPO search result를 검증하고 `maximum_search_results`/`maximum_sources` bound 안에서 selected candidate를 동일 identity/order의 VERIFIED EPO record로 만든다. 자연어→CQL planning, technical-relevance synthesis, partial recovery, CLI/runtime은 아직 포함하지 않는다.

현재 검증은 focused `63 passed`, Patent/EPO affected `159 passed`, full repository `5170 passed`, Ruff/format/diff-check PASS이며 기존 real EPO smoke도 PASS다.

Step 3B1은 일반 Research query model과 EPO CQL을 분리하고, 1~2개의 explicit CQL candidate를 PRIMARY/ALTERNATE로 보존하는 bounded `PatentSearchQueryPlan` contract를 추가했다.

현재 Step 3B1 검증은 focused `45 passed`, Patent affected `154 passed`, full repository `5195 passed`, Ruff/format/diff-check PASS다.

Step 3B2는 natural-language `PatentResearchRequest`에서 자유로운 synonym/query expansion을 하지 않고, request에 이미 존재하는 technical terminology를 1~2개의 bounded `PatentTechnicalConcept`로 선택한다. 모든 term은 question/objective에 실제로 존재해야 하며, synonym invention, translation, CQL, IPC/CPC generation, patent metadata invention 및 legal conclusion을 허용하지 않는다.

Step 3B2 검증은 focused `66 passed`, Patent/OpenAI affected `212 passed`, full repository `5224 passed`, Ruff/format/diff-check PASS다. 실제 `gpt-5` Structured Outputs 1-call live smoke도 PASS했으며 2개 concept, request-grounding, response/request id 및 token usage 보존을 확인했다. Live smoke는 1599 total tokens, 20.426초를 기록했으며 이는 correctness blocker가 아닌 후속 optimization 관찰값으로 남긴다.

Step 3B3는 `PatentTechnicalConceptPlan`을 deterministic한 EPO CQL candidate로 렌더링한 뒤 기존 `PatentSearchQueryPlanner`를 통해 `PatentSearchQueryPlan`으로 재검증한다. term은 `ta all "<term>"`로 렌더링하고 concept 내부 clause는 `and`로 결합한다. `prior_art_cutoff_date`는 법률 판단이 아닌 exclusive publication-date retrieval filter `pd < YYYYMMDD`로만 사용한다.

Step 3B3 검증은 focused `53 passed`, Patent/EPO affected `158 passed`, full repository `5234 passed`, Ruff/format/diff-check PASS다. 실제 EPO OPS bounded live smoke도 PASS했으며 generated CQL `ta all "pressure sensor" and pd < 20260818`, `request_round_trip=True`, maximum result 1 및 bibliographic XML parsing을 확인했다.

Live smoke의 첫 결과는 seat occupancy와 무관한 intraocular pressure sensor 문헌이었다. 따라서 query syntax/provider acceptance와 retrieval relevance는 서로 다른 quality dimension으로 분리한다.

Step 3C는 planning-to-execution runtime을 연결했다. `PatentResearchPlanExecutor`는 PRIMARY를 먼저 실행하고, PRIMARY가 정상 완료되었으나 VERIFIED result가 0건일 때만 ALTERNATE를 한 번 실행한다. provider/transport/XML/identity/abstract failure는 fallback으로 숨기지 않고 fail-fast한다.

`PatentResearchRequest.maximum_bytes`는 request-bound `EpoOpsConfig.maximum_response_bytes`로 binding되며, OpenAI settings와 EPO credential/config는 분리 유지된다.

Step 3C 검증은 focused integration `166 passed`, Patent/EPO broader regression `178 passed`, full repository `5254 passed`, Ruff/format/diff-check PASS다. 실제 `gpt-5 → grounded concept → deterministic CQL → EPO OPS → abstract → VERIFIED record` end-to-end live smoke도 PASS했다.

최종 live smoke에서 `request_binding=True`, `verified_records=1`, `verification_state=verified`를 확인했고 첫 VERIFIED 문헌은 `CN121905049A`, publication date `2026-04-21`이었다.

다음 즉시 설계 과제는 **technical-relevance evidence/evaluation/synthesis boundary**다. VERIFIED source identity와 technical relevance 또는 legal conclusion은 계속 분리한다.

# 39. 2026-08-18 최신 상태 — Patent Step 3G 종료 및 문서 체계 단일화

> 현재 제품 위치는 `ROADMAP.md`를 authoritative source로 사용한다.
> 이 section은 과거 Stage A~I 계획과 #38 Step 3C snapshot 이후의 최신 상태를 기록한다.

```text
Stage 4 Local Document Expansion baseline → COMPLETE
Stage 5 Internet Research Expansion        → IN PROGRESS
Patent Research Vertical Slice             → Step 3G FINAL PASS
```

완료된 Patent first usable technical-research slice:

```text
EPO OPS structured provider                COMPLETE
PatentResearchHandler                      COMPLETE
Bounded query planning                     COMPLETE
Grounded technical concept planning        COMPLETE
Deterministic EPO CQL planning             COMPLETE
Planning-to-execution runtime              COMPLETE
VERIFIED metadata/abstract binding         COMPLETE
Technical relevance evidence/evaluation    COMPLETE
Patent synthesis/report verification       COMPLETE
aira research-patent CLI                   COMPLETE
Patent User Acceptance Test                FINAL PASS
```

최종 Step 3G 검증 기준:

```text
focused patent regression  = 66 passed
full repository regression = 5302 passed
Ruff                       = PASS
changed Python format      = PASS
git diff --check           = PASS
live UAT                   = PASS
```

현재 의미 경계:

```text
result status
≠ VERIFIED source identity
≠ TECHNICALLY RELEVANT evidence
≠ FULLY SUPPORTED synthesis
≠ LEGAL CONCLUSION
```

다음 공식 작업:

```text
Stage 5 — Internet Research Expansion
Patent Research Vertical Slice
Step 4A — Patent Metadata Expansion
```

Stage 5 전체는 아직 `IN PROGRESS`다.
